# v32 (PLAN_V19 Phase 164): Kundensuche im Hauptmenü – Vorschläge (JSON für das
# Suchfeld in base.html / suche.js) und Trefferseite. Logik in app/suche.py.
# Rollen: Admin, Innendienst, Lead-Management, Außendienst (nur eigene Kunden);
# Montage und Projektierung erhalten 403. Keine Netzaufrufe, Sitzung nur über
# get_session (v27).
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import suche
from app.db import get_session
from app.templating import render

router = APIRouter()
GESPERRT_TEXT = "Für diese Rolle gibt es keine Kundensuche."


def _begriff(q: str) -> str:
    return " ".join((q or "").split())[:100]


@router.get("/suche.json")
def suche_json(request: Request, q: str = "", session: Session = Depends(get_session)):
    benutzer = request.state.benutzer
    if not suche.darf_suchen(benutzer):
        return JSONResponse({"ok": False, "meldung": GESPERRT_TEXT, "treffer": []},
                            status_code=403)
    begriff = _begriff(q)
    treffer = suche.suchen(session, begriff, benutzer, limit=suche.MAX_VORSCHLAEGE)
    return JSONResponse({"ok": True, "q": begriff, "treffer": treffer,
                         "mehr": ("/suche?q=" + quote(begriff)) if treffer else ""})


@router.get("/suche")
def suche_seite(request: Request, q: str = "", session: Session = Depends(get_session)):
    benutzer = request.state.benutzer
    begriff = _begriff(q)
    if not suche.darf_suchen(benutzer):
        antwort = render(request, "suche.html", q=begriff, treffer=[], gesperrt=True,
                         max_seite=suche.MAX_SEITE)
        antwort.status_code = 403
        return antwort
    treffer = []
    if len(begriff) >= suche.MIN_ZEICHEN:
        treffer = suche.suchen(session, begriff, benutzer, limit=suche.MAX_SEITE)
    return render(request, "suche.html", q=begriff, treffer=treffer, gesperrt=False,
                  max_seite=suche.MAX_SEITE)
