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


def offene_leads(session: Session, benutzer=None):
    abfrage = (session.query(Lead)
               .outerjoin(Erfassung, Lead.erfassung_id == Erfassung.id)
               .filter(Lead.vot_datum.isnot(None))
               .filter(or_(Lead.erfassung_id.is_(None),
                           Erfassung.status == "Entwurf")))
    if benutzer is not None and benutzer.rolle == "aussendienst":
        abfrage = abfrage.filter(Lead.benutzer_id == benutzer.id)
    return abfrage.order_by(Lead.vot_datum).all()


@router.get("")
async def liste(request: Request, q: str = "", interesse: str = "",
                vertriebler_id: int = 0, lead_status: str = "", sortierung: str = "termin",
                session: Session = Depends(get_session)):
    from app import monday_sync
    benutzer = request.state.benutzer
    alle = offene_leads(session, benutzer)
    vertriebler = {b.id: b for b in session.query(Benutzer)}
    # Auswahlwerte für die Filter aus der ungefilterten Liste
    status_werte = sorted({l.status_text for l in alle if l.status_text})
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
    # Sortierung (v5): Termin (Standard), Vertriebler, Status – jeweils dann Termin
    if sortierung == "vertriebler":
        leads.sort(key=lambda l: ((vertriebler[l.benutzer_id].name if l.benutzer_id in vertriebler
                                   else l.monday_person or "zzz").lower(), l.vot_datum or datetime.max))
    elif sortierung == "status":
        leads.sort(key=lambda l: ((l.status_text or "zzz").lower(), l.vot_datum or datetime.max))
    else:
        sortierung = "termin"
        leads.sort(key=lambda l: l.vot_datum or datetime.max)
    return render(request, "leads/liste.html", aktiv="/leads",
                  mobil=benutzer.rolle == "aussendienst",
                  leads=leads, vertriebler=vertriebler, benutzer=benutzer,
                  q=q, interesse=interesse, vertriebler_id=vertriebler_id,
                  lead_status=lead_status, sortierung=sortierung,
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
    erfassung = Erfassung(kunde_id=kunde.id, benutzer_id=benutzer.id)
    session.add(erfassung)
    session.flush()
    lead.erfassung_id = erfassung.id
    session.commit()
    return RedirectResponse(f"/erfassung/{erfassung.id}/seite/0", status_code=303)
