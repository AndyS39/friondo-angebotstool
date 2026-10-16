# v36 (PLAN_V22 Phase 194, Agent B3): Parametrierung → Cloover → Abschnitt „PDF-Ablage“ (Partial
# konfiguration/_cloover_ablage.html, eingebunden von konfiguration/cloover.html – Agent B1).
#   POST /parametrierung/cloover/ablage        Anbieter (sharepoint | basis_url | keine), SharePoint-Site,
#                                             Ordner speichern (Protokoll cloover_protokoll)
#   POST /parametrierung/cloover/ablage-test   „Test-PDF ablegen und prüfen“: kleines fpdf2-PDF ohne
#                                             Kundendaten ablegen, HEAD ohne Anmeldung prüfen, Ersetzen
#                                             prüfen; Ergebnis in cloover_ablage_letzter_test
# Nur Admin (403 wie die übrige Cloover-Seite); Netz-I/O nur nach verbindung_freigeben (v27-Regel).
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import anfrage, cloover_api, cloover_pdf_ablage
from app.db import get_session, verbindung_freigeben

router = APIRouter(prefix="/parametrierung")

SEITE = "/parametrierung/cloover"
ANKER = "#ablage"


def _nur_admin(request: Request):
    benutzer = request.state.benutzer
    if benutzer is None or benutzer.basisrolle != "admin":
        return PlainTextResponse("Nur Admin.", status_code=403)
    return None


def _zurueck(meldung: str = "") -> RedirectResponse:
    ziel = SEITE + ("?ablage=" + quote_plus(meldung) if meldung else "") + ANKER
    return RedirectResponse(ziel, status_code=303)


@router.post("/cloover/ablage")
def ablage_speichern(request: Request, session: Session = Depends(get_session)):
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    aenderungen = cloover_pdf_ablage.speichern(session, form)
    cloover_api.protokollieren(session, request.state.benutzer, aenderungen)
    session.commit()
    return _zurueck("PDF-Ablage gespeichert." if aenderungen else "PDF-Ablage: keine Änderungen.")


@router.post("/cloover/ablage-test")
def ablage_testen(request: Request, session: Session = Depends(get_session)):
    """Formularstand zuerst übernehmen, dann Test-PDF ablegen und prüfen (Netz nach Freigabe)."""
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    aenderungen = cloover_pdf_ablage.speichern(session, form)
    cloover_api.protokollieren(session, request.state.benutzer, aenderungen)
    session.commit()
    verbindung_freigeben(session)
    ok, text = cloover_pdf_ablage.test_ablage(session)
    cloover_api.protokollieren(session, request.state.benutzer,
                               [("Test-PDF ok: " if ok else "Test-PDF fehlgeschlagen: ") + text[:160]])
    session.commit()
    return _zurueck(text)
