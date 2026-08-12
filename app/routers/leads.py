# Leads VOT (Phase 19 Liste; Phase 22 füllt sie per monday-Lesesync):
# Leads mit Vor-Ort-Termin und ohne abgesendete Erfassung, chronologisch.
# Außendienst sieht nur eigene, Innendienst/Admin alle.

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
async def liste(request: Request, session: Session = Depends(get_session)):
    from app import monday_sync
    benutzer = request.state.benutzer
    leads = offene_leads(session, benutzer)
    vertriebler = {b.id: b for b in session.query(Benutzer)}
    return render(request, "leads/liste.html", aktiv="/leads",
                  mobil=benutzer.rolle == "aussendienst",
                  leads=leads, vertriebler=vertriebler, benutzer=benutzer,
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
    """Klick auf den Lead: Kunde anlegen/abgleichen (Name + PLZ), Erfassung
    starten, Lead ↔ Kunde ↔ Erfassung verknüpfen."""
    import re as _re

    from app.models import Kunde
    benutzer = request.state.benutzer
    lead = session.get(Lead, lead_id)
    if lead is None:
        return RedirectResponse("/leads", status_code=303)
    if benutzer.rolle == "aussendienst" and lead.benutzer_id != benutzer.id:
        return RedirectResponse("/leads", status_code=303)

    # Duplikatabgleich: Nachname+Vorname (normalisiert) + PLZ
    def normal(text):
        return _re.sub(r"\s+", " ", (text or "").strip().lower())

    kunde = None
    if lead.kunde_id:
        kunde = session.get(Kunde, lead.kunde_id)
    if kunde is None:
        for kandidat in session.query(Kunde).filter(Kunde.plz == lead.plz):
            if (normal(kandidat.nachname) == normal(lead.nachname)
                    and normal(kandidat.vorname) == normal(lead.vorname)):
                kunde = kandidat
                break
    if kunde is None:
        kunde = Kunde(anrede=lead.anrede, vorname=lead.vorname,
                      nachname=lead.nachname, strasse=lead.strasse,
                      plz=lead.plz, ort=lead.ort, telefon=lead.telefon,
                      email=lead.email)
        session.add(kunde)
        session.flush()
    lead.kunde_id = kunde.id

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
