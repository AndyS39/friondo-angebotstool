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
from app import anfrage   # v27: Formular/JSON in def-Routen
from app import import_preisliste   # v27: Hinweis/Bestätigung monday-Vollabgleich

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
def liste(request: Request, q: str = "", interesse: str = "",
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
    # Prozess-Fix 27.09.2026: VOT liegt in der Vergangenheit, aber keine
    # Sparte ist erfasst - vorher stand so ein Lead wochenlang unauffaellig
    # als "Terminiert" in der Liste
    jetzt = datetime.now()
    ueberfaellige = [l for l in leads
                     if l.vot_datum is not None and l.vot_datum < jetzt]
    if ansicht == "ueberfaellig":
        leads = ueberfaellige
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
                  ohne_ad=ohne_ad, ueberfaellig_anzahl=len(ueberfaellige),
                  heute=datetime.now(),
                  status_werte=status_werte, vertriebler_werte=vertriebler_werte,
                  sync_status=monday_sync.status,
                  # v27 (Phase 128): Hinweistext vor dem monday-Vollabgleich
                  monday_hinweis=import_preisliste.import_hinweis(session, "monday"),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/sync")
def jetzt_aktualisieren(request: Request, session: Session = Depends(get_session)):
    """Button „Jetzt aktualisieren“ – Fehler werden angezeigt, blockieren nichts.
    v27 (PLAN_V17 Phase 128): Vollabgleich ist ein Import – Hinweis mit Bestätigung
    (Feld bestaetigt), Dauer wird als import_dauer_monday gemerkt, der Lauf steht
    währenddessen im Betriebs-Status (monday_sync.sync markiert ihn)."""
    import time
    from urllib.parse import quote_plus

    from app import monday_sync
    if not import_preisliste.import_bestaetigt(anfrage.formular(request)):
        return RedirectResponse(
            "/leads?meldung=" + quote_plus(import_preisliste.HINWEIS_BESTAETIGEN), status_code=303)
    start = time.perf_counter()
    ergebnis = monday_sync.sync(session)
    import_preisliste.import_dauer_merken(session, "monday", start)
    if ergebnis["fehler"]:
        meldung = "Sync mit Hinweisen: " + " · ".join(ergebnis["fehler"])[:300]
    else:
        meldung = f"Sync abgeschlossen – {ergebnis['anzahl']} Leads aktualisiert."
    return RedirectResponse(f"/leads?meldung={quote_plus(meldung)}", status_code=303)


@router.post("/{lead_id}/vertriebler")
def vertriebler_aendern(request: Request, lead_id: int,
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
    form = anfrage.formular(request)
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
def ausblenden(request: Request, lead_id: int,
                     session: Session = Depends(get_session)):
    """Lead aus „Leads VOT“ nehmen (optional mit Grund); nicht löschen – der
    Sync lässt das Kennzeichen stehen, der Lead taucht nicht erneut auf."""
    from urllib.parse import quote_plus
    benutzer = request.state.benutzer
    lead = session.get(Lead, lead_id)
    if lead is None or (benutzer.rolle == "aussendienst" and lead.benutzer_id != benutzer.id):
        return RedirectResponse("/leads", status_code=303)
    form = anfrage.formular(request)
    lead.ausgeblendet = True
    lead.ausgeblendet_grund = (form.get("grund") or "").strip()[:300]
    lead.ausgeblendet_am = datetime.now()
    session.commit()
    return RedirectResponse("/leads?meldung=" + quote_plus(
        f"{lead.anzeige_name} ausgeblendet – über die Ansicht „Ausgeblendet“ zurückholbar."),
        status_code=303)


@router.post("/{lead_id}/kanal")
def kanal_aendern(request: Request, lead_id: int,
                        session: Session = Depends(get_session)):
    """v9: Vertriebskanal manuell setzen (Vorrang vor dem monday-Sync);
    wirkt auf Lead UND Kunden. Leer = zurück zur Sync-Automatik."""
    from urllib.parse import quote_plus

    from app.models import Kunde
    benutzer = request.state.benutzer
    if benutzer.rolle == "aussendienst":
        return RedirectResponse("/leads", status_code=303)
    lead = session.get(Lead, lead_id)
    if lead is None:
        return RedirectResponse("/leads", status_code=303)
    form = anfrage.formular(request)
    kanal = (form.get("kanal") or "").strip()[:100]
    lead.vertriebskanal = kanal
    lead.kanal_manuell = bool(kanal)
    kunde = session.get(Kunde, lead.kunde_id) if lead.kunde_id else None
    if kunde is not None:
        kunde.vertriebskanal = kanal
        kunde.kanal_manuell = bool(kanal)
    # v23 (Phase 109, G4): Vorgang des Leads auf Ausschlusskanal prüfen
    try:
        from app import lead_handelsvertreter
        from app.models import Vorgang
        vorgang = session.query(Vorgang).filter(Vorgang.lead_id == lead.id).first()
        if vorgang is not None:
            lead_handelsvertreter.kanalwechsel_pruefen(session, vorgang, request.state.benutzer)
    except Exception:
        pass
    session.commit()
    return RedirectResponse("/leads?meldung=" + quote_plus(
        f"{lead.anzeige_name}: Kanal "
        + (f"manuell auf „{kanal}“ gesetzt (Sync überschreibt nicht mehr)."
           if kanal else "zurück auf Sync-Automatik.")), status_code=303)


@router.post("/{lead_id}/sparte-ausblenden")
def sparte_ausblenden(request: Request, lead_id: int,
                            session: Session = Depends(get_session)):
    """v8: eine einzelne Sparte (Interesse) des Leads ausblenden bzw.
    zurückholen – der Lead bleibt sichtbar, solange andere Sparten offen sind."""
    from urllib.parse import quote_plus

    from app.models import interesse_text
    benutzer = request.state.benutzer
    lead = session.get(Lead, lead_id)
    if lead is None or (benutzer.rolle == "aussendienst" and lead.benutzer_id != benutzer.id):
        return RedirectResponse("/leads", status_code=303)
    form = anfrage.formular(request)
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
def zurueckholen(request: Request, lead_id: int,
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
def erfassen(request: Request, lead_id: int,
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
    kunde_fuer_lead(session, lead)
    session.commit()
    # v8: erst die Sparten-Auswahl (Lead-Interessen vorausgewählt); dort sind
    # auch offene Entwürfe des Leads zum Fortsetzen verlinkt
    return RedirectResponse(f"/erfassung/sparten?lead_id={lead.id}", status_code=303)
