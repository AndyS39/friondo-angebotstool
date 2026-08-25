# Leads VOT (Phase 19 Liste; Phase 22 füllt sie per monday-Lesesync):
# Leads mit Vor-Ort-Termin und ohne abgesendete Erfassung, chronologisch.
# Außendienst sieht nur eigene, Innendienst/Admin alle.

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Benutzer, Erfassung, Lead
from app.templating import render

router = APIRouter(prefix="/leads")


def erfasste_sparten(session: Session, leads) -> dict[int, set[str]]:
    """v8: je Lead die Sparten mit abgesendeter Erfassung (Entwürfe zählen nicht)."""
    ids = [l.id for l in leads]
    if not ids:
        return {}
    ergebnis: dict[int, set[str]] = {}
    for e in (session.query(Erfassung)
              .filter(Erfassung.lead_id.in_(ids), Erfassung.status != "Entwurf")):
        ergebnis.setdefault(e.lead_id, set()).add(e.sparte or "WP")
    return ergebnis


def sparten_chips(lead, erfasst: set[str]) -> list[tuple[str, str]]:
    """v8: Chip-Status je Interesse – (Sparte, erfasst|ausgeblendet|offen)."""
    ausgeblendet = set(lead.ausgeblendete_sparten)
    return [(s, "erfasst" if s in erfasst
             else ("ausgeblendet" if s in ausgeblendet else "offen"))
            for s in lead.sparten]


def offene_leads(session: Session, benutzer=None, ausgeblendet: bool = False):
    """Offene Leads (VOT-Datum): seit v8 verlässt ein Lead die Liste erst,
    wenn ALLE Interessen (Sparten) erfasst oder ausgeblendet sind. Standard
    ohne ganz ausgeblendete; ausgeblendet=True liefert nur diese."""
    abfrage = (session.query(Lead)
               .filter(Lead.vot_datum.isnot(None))
               .filter(Lead.ausgeblendet.is_(ausgeblendet)))
    if benutzer is not None and benutzer.rolle == "aussendienst":
        abfrage = abfrage.filter(Lead.benutzer_id == benutzer.id)
    kandidaten = abfrage.order_by(Lead.vot_datum).all()
    erfasst = erfasste_sparten(session, kandidaten)
    if ausgeblendet:
        return kandidaten
    return [l for l in kandidaten
            if any(status == "offen"
                   for _, status in sparten_chips(l, erfasst.get(l.id, set())))]


@router.get("")
async def liste(request: Request, q: str = "", interesse: str = "",
                vertriebler_id: int = 0, lead_status: str = "", sortierung: str = "termin",
                ansicht: str = "", kanal: str = "", session: Session = Depends(get_session)):
    from app import monday_sync
    benutzer = request.state.benutzer
    ausgeblendet = ansicht == "ausgeblendet"   # Filter „Ausgeblendet“ (v5-Nachtrag)
    alle = offene_leads(session, benutzer, ausgeblendet=ausgeblendet)
    vertriebler = {b.id: b for b in session.query(Benutzer)}
    # Auswahlwerte für die Filter aus der ungefilterten Liste
    status_werte = sorted({l.status_text for l in alle if l.status_text})
    kanal_werte = sorted({l.vertriebskanal for l in alle if l.vertriebskanal})
    # Warnhinweis (v6): offene Leads ohne Vertriebler-Zuordnung (nur Büro)
    ohne_ad = 0 if (ausgeblendet or benutzer.rolle == "aussendienst") else sum(
        1 for l in alle if not l.benutzer_id)
    vertriebler_werte = sorted({l.benutzer_id for l in alle if l.benutzer_id},
                               key=lambda i: vertriebler[i].name if i in vertriebler else "")
    leads = alle
    if q:
        suchwort = q.lower()
        leads = [l for l in leads
                 if suchwort in l.anzeige_name.lower()
                 or suchwort in (l.ort or "").lower()
                 or suchwort in (l.plz or "")]
    if interesse:   # Filter nach Interesse (Phase 33)
        leads = [l for l in leads if interesse in l.interessen]
    # Filter Vertriebler + Status (v5, Phase 35) – kombinierbar mit Suche
    if vertriebler_id:
        leads = [l for l in leads if l.benutzer_id == vertriebler_id]
    if lead_status:
        leads = [l for l in leads if l.status_text == lead_status]
    if kanal:   # Vertriebskanal (v6)
        leads = [l for l in leads if l.vertriebskanal == kanal]
    # Sortierung (v5): Termin (Standard), Vertriebler, Status – jeweils dann Termin
    if sortierung == "vertriebler":
        leads.sort(key=lambda l: ((vertriebler[l.benutzer_id].name if l.benutzer_id in vertriebler
                                   else l.monday_person or "zzz").lower(), l.vot_datum or datetime.max))
    elif sortierung == "status":
        leads.sort(key=lambda l: ((l.status_text or "zzz").lower(), l.vot_datum or datetime.max))
    else:
        sortierung = "termin"
        leads.sort(key=lambda l: l.vot_datum or datetime.max)
    aussendienst = (session.query(Benutzer)
                    .filter(Benutzer.rolle == "aussendienst", Benutzer.aktiv.is_(True))
                    .order_by(Benutzer.name).all())
    # v8: Status-Chips je Interesse („WP ✓ · PV offen“)
    erfasst = erfasste_sparten(session, leads)
    chips = {l.id: sparten_chips(l, erfasst.get(l.id, set())) for l in leads}
    return render(request, "leads/liste.html", aktiv="/leads",
                  mobil=benutzer.rolle == "aussendienst", aussendienst=aussendienst,
                  chips=chips,
                  leads=leads, vertriebler=vertriebler, benutzer=benutzer,
                  q=q, interesse=interesse, vertriebler_id=vertriebler_id,
                  lead_status=lead_status, sortierung=sortierung, ansicht=ansicht,
                  ausgeblendet=ausgeblendet, kanal=kanal, kanal_werte=kanal_werte,
                  ohne_ad=ohne_ad,
                  status_werte=status_werte, vertriebler_werte=vertriebler_werte,
                  sync_status=monday_sync.status,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/sync")
async def jetzt_aktualisieren(request: Request, session: Session = Depends(get_session)):
    """Button „Jetzt aktualisieren“ – Fehler werden angezeigt, blockieren nichts."""
    from urllib.parse import quote_plus

    from app import monday_sync
    ergebnis = monday_sync.sync(session)
    if ergebnis["fehler"]:
        meldung = "Sync mit Hinweisen: " + " · ".join(ergebnis["fehler"])[:300]
    else:
        meldung = f"Sync abgeschlossen – {ergebnis['anzahl']} Leads aktualisiert."
    return RedirectResponse(f"/leads?meldung={quote_plus(meldung)}", status_code=303)


@router.post("/{lead_id}/vertriebler")
async def vertriebler_aendern(request: Request, lead_id: int,
                              session: Session = Depends(get_session)):
    """Innendienst/Admin ordnet den Lead einem anderen Außendienstler zu
    (v5-Nachtrag); der monday-Sync überschreibt das beim nächsten Lauf nur,
    wenn sich die Personen-Spalte in monday ändert – daher wird zusätzlich
    die Personen-Zuordnung nicht angefasst, nur dieser Lead."""
    from urllib.parse import quote_plus
    benutzer = request.state.benutzer
    if benutzer.rolle == "aussendienst":
        return RedirectResponse("/leads", status_code=303)
    lead = session.get(Lead, lead_id)
    if lead is None:
        return RedirectResponse("/leads", status_code=303)
    form = await request.form()
    wert = form.get("benutzer_id") or ""
    if wert.isdigit() and int(wert) > 0:
        lead.benutzer_id = int(wert)
        lead.benutzer_manuell = True    # Sync überschreibt nicht mehr
    else:
        lead.benutzer_id = None
        lead.benutzer_manuell = False   # zurück zur monday-Zuordnung beim nächsten Sync
    session.commit()
    neuer = session.get(Benutzer, lead.benutzer_id) if lead.benutzer_id else None
    return RedirectResponse("/leads?meldung=" + quote_plus(
        f"{lead.anzeige_name} → Vertriebler: {neuer.name if neuer else 'nicht zugeordnet'}"),
        status_code=303)


@router.post("/{lead_id}/ausblenden")
async def ausblenden(request: Request, lead_id: int,
                     session: Session = Depends(get_session)):
    """Lead aus „Leads VOT“ nehmen (optional mit Grund); nicht löschen – der
    Sync lässt das Kennzeichen stehen, der Lead taucht nicht erneut auf."""
    from urllib.parse import quote_plus
    benutzer = request.state.benutzer
    lead = session.get(Lead, lead_id)
    if lead is None or (benutzer.rolle == "aussendienst" and lead.benutzer_id != benutzer.id):
        return RedirectResponse("/leads", status_code=303)
    form = await request.form()
    lead.ausgeblendet = True
    lead.ausgeblendet_grund = (form.get("grund") or "").strip()[:300]
    lead.ausgeblendet_am = datetime.now()
    session.commit()
    return RedirectResponse("/leads?meldung=" + quote_plus(
        f"{lead.anzeige_name} ausgeblendet – über die Ansicht „Ausgeblendet“ zurückholbar."),
        status_code=303)


@router.post("/{lead_id}/sparte-ausblenden")
async def sparte_ausblenden(request: Request, lead_id: int,
                            session: Session = Depends(get_session)):
    """v8: eine einzelne Sparte (Interesse) des Leads ausblenden bzw.
    zurückholen – der Lead bleibt sichtbar, solange andere Sparten offen sind."""
    from urllib.parse import quote_plus

    from app.models import interesse_text
    benutzer = request.state.benutzer
    lead = session.get(Lead, lead_id)
    if lead is None or (benutzer.rolle == "aussendienst" and lead.benutzer_id != benutzer.id):
        return RedirectResponse("/leads", status_code=303)
    form = await request.form()
    sparte = (form.get("sparte") or "").strip().upper()
    if sparte not in lead.sparten:
        return RedirectResponse("/leads", status_code=303)
    ausgeblendet = set(lead.ausgeblendete_sparten)
    if sparte in ausgeblendet:
        ausgeblendet.discard(sparte)
        meldung = f"{lead.anzeige_name}: Sparte {sparte} wieder offen."
    else:
        ausgeblendet.add(sparte)
        meldung = f"{lead.anzeige_name}: Sparte {sparte} ausgeblendet."
    lead.ausgeblendet_sparten = interesse_text(ausgeblendet)
    session.commit()
    return RedirectResponse("/leads?meldung=" + quote_plus(meldung), status_code=303)


@router.post("/{lead_id}/zurueckholen")
async def zurueckholen(request: Request, lead_id: int,
                       session: Session = Depends(get_session)):
    from urllib.parse import quote_plus
    benutzer = request.state.benutzer
    lead = session.get(Lead, lead_id)
    if lead is None or (benutzer.rolle == "aussendienst" and lead.benutzer_id != benutzer.id):
        return RedirectResponse("/leads", status_code=303)
    lead.ausgeblendet = False
    lead.ausgeblendet_grund = ""
    lead.ausgeblendet_am = None
    session.commit()
    return RedirectResponse("/leads?meldung=" + quote_plus(
        f"{lead.anzeige_name} wieder in Leads VOT."), status_code=303)


@router.get("/{lead_id}/erfassen")
async def erfassen(request: Request, lead_id: int,
                   session: Session = Depends(get_session)):
    """Klick auf den Lead: Erfassung mit dem (per Sync angelegten) Kunden
    starten, Lead ↔ Kunde ↔ Erfassung verknüpfen."""
    benutzer = request.state.benutzer
    lead = session.get(Lead, lead_id)
    if lead is None:
        return RedirectResponse("/leads", status_code=303)
    if benutzer.rolle == "aussendienst" and lead.benutzer_id != benutzer.id:
        return RedirectResponse("/leads", status_code=303)

    # Kunde ist seit Phase 24 schon per Sync angelegt; Abgleich hier als Fallback
    from app.monday_sync import kunde_fuer_lead
    kunde = kunde_fuer_lead(session, lead)

    if lead.erfassung_id:
        erfassung = session.get(Erfassung, lead.erfassung_id)
        if erfassung is not None and erfassung.status == "Entwurf":
            session.commit()
            return RedirectResponse(
                f"/erfassung/{erfassung.id}/seite/{erfassung.seite_index}",
                status_code=303)
    erfassung = Erfassung(kunde_id=kunde.id, benutzer_id=benutzer.id,
                          lead_id=lead.id)   # v8: n:1-Verknüpfung je Sparte
    session.add(erfassung)
    session.flush()
    lead.erfassung_id = erfassung.id
    session.commit()
    return RedirectResponse(f"/erfassung/{erfassung.id}/weiche", status_code=303)
