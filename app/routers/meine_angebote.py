# „Meine Angebote“ (v8, Phase 49): der Außendienst sieht die eigenen Angebote
# read-only – Kundenpreise (Brutto/Endbetrag) und PDF-Download ja, aber ohne
# EK/DB, ohne Editor, ohne Versand und ohne Löschen.

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.db import get_session
from app.models import Angebot, Erfassung, Kunde
from app.templating import render

router = APIRouter(prefix="/meine-angebote")


def _eigene_angebote(session: Session, benutzer_id: int) -> list[Angebot]:
    """Angebote des Außendienstlers: über die verknüpfte Erfassung, sonst
    über das Vertriebler-Feld (manuelle Angebote)."""
    ids = {e.angebot_id for e in session.query(Erfassung)
           .filter(Erfassung.benutzer_id == benutzer_id,
                   Erfassung.angebot_id.isnot(None))}
    ids |= {a.id for a in session.query(Angebot)
            .filter(Angebot.vertriebler_id == benutzer_id)}
    if not ids:
        return []
    return (session.query(Angebot).options(joinedload(Angebot.positionen))
            .filter(Angebot.id.in_(ids), Angebot.archiviert.is_(False))
            .order_by(Angebot.nummer.desc()).all())


def _gehoert_mir(session: Session, angebot: Angebot, benutzer_id: int) -> bool:
    if angebot.vertriebler_id == benutzer_id:
        return True
    return (session.query(Erfassung)
            .filter(Erfassung.angebot_id == angebot.id,
                    Erfassung.benutzer_id == benutzer_id).count() > 0)


@router.get("")
async def liste(request: Request, session: Session = Depends(get_session)):
    benutzer = request.state.benutzer
    angebote = _eigene_angebote(session, benutzer.id)
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_([a.kunde_id for a in angebote] or [0]))}
    from datetime import datetime
    return render(request, "angebote/meine.html", aktiv=None, mobil=True,
                  benutzer=benutzer, angebote=angebote, kunden=kunden,
                  heute=datetime.now())


@router.get("/{angebot_id}/pdf")
async def pdf_anzeigen(request: Request, angebot_id: int,
                       session: Session = Depends(get_session)):
    """PDF des eigenen Angebots (Kundenansicht – enthält ohnehin keine EKs)."""
    benutzer = request.state.benutzer
    angebot = session.get(Angebot, angebot_id)
    if (angebot is None or angebot.extern
            or not _gehoert_mir(session, angebot, benutzer.id)):
        return RedirectResponse("/meine-angebote", status_code=303)
    from app import pdf_export
    pfad = pdf_export.pdf_fuer_angebot(session, angebot)
    return FileResponse(pfad, media_type="application/pdf",
                        content_disposition_type="inline",
                        filename=f"{angebot.nummer}.pdf")
