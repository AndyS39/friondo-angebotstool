# v36 (PLAN_V22 Phase 194, Agent B3): Cloover-Projekt am Angebot – Knöpfe des Editor-Blocks
# templates/angebote/_cloover_projekt.html (Innendienst/Admin):
#   POST /angebote/{id}/cloover/projekt   „Projekt anlegen“ nachholen (Voraussetzungen, Fassung A ablegen,
#                                         POST /api/projects, Fassung B ersetzen – cloover_projekt.anlegen_fuer)
#   POST /angebote/{id}/cloover/status    „Status jetzt abrufen“ (GET /api/projects/{id}, Badge/Glocke/Notiz)
# Netz-I/O nur nach verbindung_freigeben (v27-Regel); JSON-Antwort bei Accept application/json, sonst
# Redirect in den Editor (#cloover). Der Außendienst sieht den Block nur lesend (keine Routen).
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import cloover, cloover_projekt, sperren
from app.db import get_session, verbindung_freigeben
from app.models import Angebot

router = APIRouter(prefix="/angebote")


def _json_gewuenscht(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "")


def _antwort(request: Request, angebot_id: int, ok: bool, meldung: str, **zusatz):
    if _json_gewuenscht(request):
        return JSONResponse({"ok": ok, "meldung": meldung, **zusatz}, status_code=200 if ok else 400)
    return RedirectResponse(f"/angebote/{angebot_id}?meldung={quote_plus(meldung)}#cloover", status_code=303)


def _pruefen(request: Request, session: Session, angebot_id: int):
    """(angebot, fehlerantwort) – Rolle Innendienst/Admin, Tool-Angebot, keine fremde Bearbeitungssperre."""
    benutzer = request.state.benutzer
    if benutzer is None or benutzer.basisrolle not in ("admin", "innendienst"):
        if _json_gewuenscht(request):
            return None, JSONResponse({"ok": False, "meldung": "Nur Innendienst/Admin."}, status_code=403)
        return None, RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return None, _antwort(request, angebot_id, False, "Angebot nicht gefunden.")
    if angebot.extern:
        return None, _antwort(request, angebot_id, False, "TAIFUN-Eintrag – kein Cloover-Projekt im Tool.")
    halter = sperren.gesperrt_fuer(angebot_id, benutzer.id)
    if halter is not None:
        return None, _antwort(request, angebot_id, False,
                              f"Keine Änderung möglich – wird gerade von {halter['name']} bearbeitet.")
    return angebot, None


@router.post("/{angebot_id}/cloover/projekt")
def projekt_anlegen(request: Request, angebot_id: int, session: Session = Depends(get_session)):
    """Knopf „Projekt anlegen“ (Nachholen nach behobenen Voraussetzungen oder Cloover-Fehler)."""
    angebot, fehler = _pruefen(request, session, angebot_id)
    if fehler is not None:
        return fehler
    benutzer = request.state.benutzer
    ok, meldung = cloover_projekt.anlegen_fuer(session, angebot, benutzer, fassung_b=True)
    return _antwort(request, angebot_id, ok, meldung,
                    projekt_id=cloover.json_lesen(angebot).get("projekt_id") or "")


@router.post("/{angebot_id}/cloover/status")
def status_abrufen(request: Request, angebot_id: int, session: Session = Depends(get_session)):
    """Knopf „Status jetzt abrufen“: Sitzung freigeben, dann GET /api/projects/{id} über
    cloover_projekt.status_abrufen_fuer (eigene kurze Sitzungen)."""
    angebot, fehler = _pruefen(request, session, angebot_id)
    if fehler is not None:
        return fehler
    benutzer = request.state.benutzer
    verbindung_freigeben(session)
    ergebnis = cloover_projekt.status_abrufen_fuer(angebot.id, benutzer)
    return _antwort(request, angebot_id, ergebnis["ok"], ergebnis["meldung"],
                    geaendert=bool(ergebnis.get("geaendert")), status=ergebnis.get("status") or "")
