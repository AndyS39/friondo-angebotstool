# v30 (PLAN_V18 Phase 145): Benutzer-Einstellungen, die jede Rolle selbst setzt.
# Bisher nur die Darstellung (Gerät · Hell · Dunkel) aus dem Umschalter im
# Kopfzeilen-Menü (base.html). JSON-Aufruf aus navigation.js; ohne JavaScript
# kommt ein normales Formular und die Antwort ist eine Umleitung zurück.
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import anfrage, darstellung
from app.db import get_session

router = APIRouter(prefix="/einstellungen")


def _zurueck_ziel(request: Request) -> str:
    """Nur eigene Seiten als Umleitungsziel (Referer ohne Host-Anteil)."""
    referer = request.headers.get("referer", "") or ""
    pfad = referer.split("://", 1)[-1]
    pfad = pfad[pfad.find("/"):] if "/" in pfad else "/"
    return pfad if pfad.startswith("/") and not pfad.startswith("//") else "/"


@router.post("/darstellung")
def darstellung_speichern(request: Request, session: Session = Depends(get_session)):
    """Speichert die Darstellung je Benutzer (benutzer_einstellungen, Key
    darstellung) und setzt das Cookie, das die Middleware vor dem Rendern liest."""
    benutzer = request.state.benutzer
    json_aufruf = "application/json" in (request.headers.get("content-type") or "")
    if json_aufruf:
        daten = anfrage.json_lesen(request) or {}
    else:
        daten = anfrage.formular(request)
    wert = daten.get("wert") or daten.get("darstellung") or ""
    gueltig = str(wert).strip().lower() in darstellung.WERTE
    wert = darstellung.speichern(session, benutzer.id, wert)
    session.commit()
    if json_aufruf or "application/json" in (request.headers.get("accept") or ""):
        antwort = JSONResponse({"ok": True, "darstellung": wert,
                                "hinweis": "" if gueltig else "Unbekannter Wert – auf „Gerät“ gesetzt."})
    else:
        antwort = RedirectResponse(_zurueck_ziel(request), status_code=303)
    darstellung.cookie_setzen(antwort, wert)
    return antwort
