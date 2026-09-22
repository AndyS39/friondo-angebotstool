# Glocke in der Kopfzeile (v11, Phase 69): Klick auf einen Eintrag markiert
# ihn als gelesen und springt zum Link; „Alle gelesen“ räumt den Zähler.
# Für alle Rollen erreichbar (auch Außendienst – Pfad in AUSSENDIENST_PFADE).

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Benachrichtigung

router = APIRouter(prefix="/benachrichtigungen")


@router.get("/{eintrag_id}/oeffnen")
async def oeffnen(request: Request, eintrag_id: int,
                  session: Session = Depends(get_session)):
    benutzer = request.state.benutzer
    eintrag = session.get(Benachrichtigung, eintrag_id)
    if (benutzer is None or eintrag is None
            or eintrag.benutzer_id != benutzer.id):
        return RedirectResponse("/", status_code=303)
    if eintrag.gelesen_am is None:
        eintrag.gelesen_am = datetime.now()
        session.commit()
    ziel = eintrag.link or "/"
    if not ziel.startswith("/"):
        ziel = "/"   # nur interne Links – nie auf fremde Adressen umleiten
    return RedirectResponse(ziel, status_code=303)


@router.post("/alle-gelesen")
async def alle_gelesen(request: Request, session: Session = Depends(get_session)):
    benutzer = request.state.benutzer
    if benutzer is not None:
        jetzt = datetime.now()
        for eintrag in (session.query(Benachrichtigung)
                        .filter(Benachrichtigung.benutzer_id == benutzer.id,
                                Benachrichtigung.gelesen_am.is_(None))):
            eintrag.gelesen_am = jetzt
        session.commit()
    zurueck = request.headers.get("referer", "/")
    return RedirectResponse(zurueck if zurueck.startswith(("/", str(request.base_url)))
                            else "/", status_code=303)
