# Leads VOT (Phase 19 Liste; Phase 22 füllt sie per monday-Lesesync):
# Leads mit Vor-Ort-Termin und ohne abgesendete Erfassung, chronologisch.
# Außendienst sieht nur eigene, Innendienst/Admin alle.

from fastapi import APIRouter, Depends, Request
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
    benutzer = request.state.benutzer
    leads = offene_leads(session, benutzer)
    vertriebler = {b.id: b for b in session.query(Benutzer)}
    return render(request, "leads/liste.html", aktiv="/leads",
                  mobil=benutzer.rolle == "aussendienst",
                  leads=leads, vertriebler=vertriebler, benutzer=benutzer,
                  meldung=request.query_params.get("meldung", ""))
