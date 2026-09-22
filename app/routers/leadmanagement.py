# Lead-Management V1 (v12) – Router unter /lead-management (Ziel der
# bestehenden Startportal-Karte). Der Plan nennt /leads; dort liegt aber die
# unveränderliche Leads-VOT-Liste (Leitplanke 2) – Entscheidung in
# docs/leadmanagement-entscheidungen.md. /api/leads (Phase 75) bleibt wie geplant.
# Demo-Schalter: Nicht-Sichtbare bekommen auf der Einstiegsseite die alte
# Platzhalterseite (Verhalten wie bisher), auf allen anderen Routen 404.

from datetime import datetime, timedelta
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import leadmanagement as kern
from app.db import get_session
from app.models import (Benutzer, Kampagne, Kunde, LeadAktivitaet,
                        LeadQualifizierung, LeadQuelle, Vorgang, VotTermin,
                        ANRUF_ERGEBNIS_NAMEN, LEAD_PHASEN, LEAD_PHASEN_NAMEN)
from app.templating import render

router = APIRouter(prefix="/lead-management")


def _gate(request: Request, session: Session) -> None:
    """404 statt 403 – im Demo-Modus soll das Modul unsichtbar sein."""
    if not kern.lead_modul_sichtbar(session, request.state.benutzer):
        raise HTTPException(status_code=404)


@router.get("")
async def startseite(request: Request, session: Session = Depends(get_session)):
    """Einstieg: Sichtbare landen auf der Anrufliste (Phase 76); alle anderen
    sehen die alte Platzhalterseite – exakt wie vor dem Modul."""
    if not kern.lead_modul_sichtbar(session, request.state.benutzer):
        return render(request, "platzhalter.html", aktiv=None,
                      titel="Lead-Management",
                      hinweis="Dieser Bereich ist im Aufbau (Coming soon). "
                              "Die Lead-Arbeit läuft bis dahin wie gewohnt über "
                              "das Angebotstool (Leads VOT).")
    return RedirectResponse("/lead-management/anrufliste", status_code=303)


@router.get("/anrufliste")
async def anrufliste(request: Request, session: Session = Depends(get_session)):
    """Arbeitsliste des Leadmanagements (Phase 76 baut sie voll aus)."""
    _gate(request, session)
    return render(request, "leadmanagement/anrufliste.html",
                  aktiv="/lead-management",
                  zeilen=[], filter_werte={}, phasen_namen=LEAD_PHASEN_NAMEN,
                  ergebnis_namen=ANRUF_ERGEBNIS_NAMEN,
                  meldung=request.query_params.get("meldung", ""))
