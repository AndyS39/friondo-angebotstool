# v36 (PLAN_V22 Phase 194, Agent B3): öffentliche Token-Route der Cloover-PDF-Ablage (Anbieter
# `basis_url`): GET /oeffentlich/cloover/<token>.pdf liefert das abgelegte Angebots-PDF ohne Anmeldung –
# nur mit gültigem Token (32 Zeichen, Ablauf 180 Tage, Tabelle cloover_pdf_tokens), sonst 404; keine
# Verzeichnisliste, keine Kundennamen im Dateinamen. Freigeschaltet in auth.OFFENE_PFADE
# ("/oeffentlich/cloover") wie die Fern-Signatur; Cloover ruft die URL mit HEAD/GET ab (Starlette
# beantwortet HEAD für GET-Routen; FileResponse sendet dann nur die Kopfzeilen, Content-Type application/pdf).
from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app import cloover_pdf_ablage
from app.db import get_session

router = APIRouter(prefix="/oeffentlich")


def _nicht_gefunden():
    return PlainTextResponse("Nicht gefunden.", status_code=404,
                             headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


@router.api_route("/cloover/{token}.pdf", methods=["GET", "HEAD"])   # FastAPI ergänzt HEAD nicht von selbst
def cloover_pdf(request: Request, token: str, session: Session = Depends(get_session)):
    pfad = cloover_pdf_ablage.token_datei(session, token)
    if pfad is None:
        return _nicht_gefunden()
    return FileResponse(pfad, media_type="application/pdf", content_disposition_type="inline",
                        filename="Angebot.pdf",
                        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


@router.get("/cloover")
@router.get("/cloover/")
def cloover_liste_gesperrt():
    """Keine Verzeichnisliste – immer 404."""
    return _nicht_gefunden()
