# v34 (PLAN_V21 Phase 180, Agent E): „Elektroarbeiten ins PV-Angebot (0 % USt)“ und „zurückholen“ –
# eigener Router (Präfix /angebote), damit routers/angebote.py nur punktuell berührt wird.
#
# Routen (def, v27): POST /angebote/{id}/elektro-ins-pv · POST /angebote/{id}/elektro-zurueckholen
# Nur Innendienst/Admin (Basisrolle); Bearbeitungssperre wie die übrigen Editor-Routen;
# eine Transaktion im _speichern-Muster (Rollback + eine Wiederholung bei „database is locked“);
# JSON bei Accept: application/json ({"ok", "meldung", …}), sonst Redirect in den Editor mit ?meldung=.
# Die Logik liegt in app/elektro_pv.py.
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import elektro_pv
from app.db import get_session
from app.models import Angebot
from app.routers.angebote import _speichern, _sperr_umleitung

router = APIRouter(prefix="/angebote", tags=["angebote"])


def _json_gewuenscht(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "")


def _antwort(request: Request, angebot_id: int, inhalt: dict, status_code: int = 200):
    if _json_gewuenscht(request):
        return JSONResponse(inhalt, status_code=status_code)
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(inhalt.get("meldung", "")),
                            status_code=303)


def _berechtigt(request: Request) -> bool:
    benutzer = getattr(request.state, "benutzer", None)
    return benutzer is not None and benutzer.basisrolle in ("admin", "innendienst")


@router.post("/{angebot_id}/elektro-ins-pv")
def elektro_ins_pv(request: Request, angebot_id: int,
                   session: Session = Depends(get_session)):
    """Elektro-Positionen des WP-/KL-/WB-Entwurfs ins PV-Angebot des Vorgangs übernehmen
    (Ursprung: Alternativ „im PV-Angebot enthalten“; PV: voll berechnete Kopien zu 0 % USt)."""
    if not _berechtigt(request):
        return _antwort(request, angebot_id,
                        {"ok": False, "meldung": "Nur Innendienst/Admin dürfen Elektroarbeiten übernehmen."},
                        403)
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote?meldung=Angebot+nicht+gefunden", status_code=303)
    if angebot.extern:
        return _antwort(request, angebot_id,
                        {"ok": False, "meldung": "Externer TAIFUN-Eintrag – keine Positionen vorhanden."}, 400)
    benutzer = request.state.benutzer
    ergebnis: dict = {}

    def aktion():
        ergebnis.clear()
        a = session.get(Angebot, angebot_id)
        pv = elektro_pv.pv_ziel(session, a)
        if pv is None:
            ergebnis.update(ok=False, anzahl=0, netto_cent=0, ersparnis_cent=0,
                            meldung=("Kein PV-Angebot im Status Entwurf/Versand vorbereitet in "
                                     "diesem Vorgang – Übernahme nicht möglich."))
            return
        anzahl, netto, ersparnis, meldung = elektro_pv.uebernehmen(session, a, pv, benutzer)
        ergebnis.update(ok=anzahl > 0, anzahl=anzahl, netto_cent=netto, ersparnis_cent=ersparnis,
                        meldung=meldung, pv_id=pv.id, pv_nummer=pv.nummer)

    _speichern(session, aktion)
    return _antwort(request, angebot_id, ergebnis, 200 if ergebnis.get("ok") else 409)


@router.post("/{angebot_id}/elektro-zurueckholen")
def elektro_zurueckholen(request: Request, angebot_id: int,
                         session: Session = Depends(get_session)):
    """Übernommene Elektro-Positionen aus dem PV-Angebot entfernen und das Alternativ-Kennzeichen
    im Ursprungsangebot aufheben (nur solange beide Angebote Entwurf/Versand vorbereitet sind;
    bei gelöschtem/überholtem/abgelehntem PV-Angebot werden nur die Kennzeichen gelöst)."""
    if not _berechtigt(request):
        return _antwort(request, angebot_id,
                        {"ok": False, "meldung": "Nur Innendienst/Admin dürfen Elektroarbeiten zurückholen."},
                        403)
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote?meldung=Angebot+nicht+gefunden", status_code=303)
    benutzer = request.state.benutzer
    ergebnis: dict = {}

    def aktion():
        ergebnis.clear()
        a = session.get(Angebot, angebot_id)
        anzahl, meldung = elektro_pv.zurueckholen(session, a, benutzer)
        ergebnis.update(ok=anzahl > 0, anzahl=anzahl, meldung=meldung)

    _speichern(session, aktion)
    return _antwort(request, angebot_id, ergebnis, 200 if ergebnis.get("ok") else 409)
