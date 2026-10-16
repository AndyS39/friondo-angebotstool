# v36 (PLAN_V22 Phase 193, Agent B2): Editor-Karte „Finanzierung (Cloover)“ – eigener Router (Präfix
# /angebote), damit routers/angebote.py nur punktuell berührt wird (Muster: angebote_elektro.py, v34).
#
# Routen (def, v27):
#   POST /angebote/{id}/cloover       Laufzeit (1–25 Jahre), Anzahlung (€) und Häkchen „Finanzierung im PDF
#                                     ausblenden“ speichern (wie wirtschaftlichkeit_ausblenden, v22) – nur
#                                     Entwurf/„Versand vorbereitet“ [ANNAHME]; danach Rate nachziehen, wenn
#                                     sich Laufzeit/Anzahlung änderten (Netz-I/O erst nach dem Commit).
#   POST /angebote/{id}/cloover/rate  „Rate neu berechnen“ → cloover.rate_aktualisieren(erzwingen=True),
#                                     Meldung mit Rate bzw. „Cloover-Rate nicht verfügbar: <Grund>“.
# Nur Innendienst/Admin (Basisrolle); Bearbeitungssperre wie die übrigen Editor-Routen; JSON bei
# Accept: application/json ({"ok", "meldung", …}), sonst Redirect in den Editor mit ?meldung=.
# Die Logik liegt in app/cloover.py; Netzaufrufe laufen über app/cloover_api.py ohne offene Sitzung.
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import anfrage, cloover, cloover_api, db
from app.db import get_session
from app.models import Angebot
from app.routers.angebote import _speichern, _sperr_umleitung

router = APIRouter(prefix="/angebote", tags=["angebote"])

MELDUNG_RECHTE = "Nur Innendienst/Admin dürfen die Finanzierung bearbeiten."
MELDUNG_STATUS = ("Finanzierung nur im Entwurf oder bei „Versand vorbereitet“ änderbar – bei versendeten "
                  "Angeboten über „Überarbeiten“ (neue Version).")
MELDUNG_LAUFZEIT = f"Laufzeit: bitte {cloover.LAUFZEIT_MIN}–{cloover.LAUFZEIT_MAX} Jahre eingeben."
MELDUNG_ANZAHLUNG = "Anzahlung: bitte nur die Zahl eingeben (z. B. 1.500,00)."


def _json_gewuenscht(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "")


def _antwort(request: Request, angebot_id: int, inhalt: dict, status_code: int = 200):
    if _json_gewuenscht(request):
        return JSONResponse(inhalt, status_code=status_code)
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(inhalt.get("meldung", ""))
                            + "#cloover-karte", status_code=303)


def _berechtigt(request: Request) -> bool:
    benutzer = getattr(request.state, "benutzer", None)
    return benutzer is not None and benutzer.basisrolle in ("admin", "innendienst")


def _rate_meldung(daten: dict) -> str:
    """Meldungstext aus dem Stand der Rate (nach rate_aktualisieren)."""
    if not daten:
        return "Angebot nicht gefunden."
    if daten.get("fehler"):
        text = cloover.MELDUNG_RATE_FEHLT.format(grund=daten["fehler"])
        if daten.get("rate_ohne_cent") is not None and daten.get("stand"):
            text += f" – letzte Rate {cloover.rate_satz(daten['rate_ohne_cent'])} (Stand {daten['stand']}) bleibt."
        return text
    if daten.get("rate_ohne_cent") is None:
        return "Cloover-Rate nicht verfügbar."
    text = f"Rate berechnet: {cloover.rate_satz(daten['rate_ohne_cent'])}"
    if daten.get("rate_mit_cent") is not None:
        text += f" ohne Förderung, {cloover.rate_satz(daten['rate_mit_cent'])} mit Förderung"
    return text + f" (Laufzeit {daten.get('laufzeit_jahre')} Jahre, Stand {daten.get('stand', '')})."


@router.post("/{angebot_id}/cloover")
def cloover_speichern(request: Request, angebot_id: int, session: Session = Depends(get_session)):
    """Laufzeit, Anzahlung und „Finanzierung im PDF ausblenden“ je Angebot speichern (Phase 193)."""
    if not _berechtigt(request):
        return _antwort(request, angebot_id, {"ok": False, "meldung": MELDUNG_RECHTE}, 403)
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    form = anfrage.formular(request)
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote?meldung=Angebot+nicht+gefunden", status_code=303)
    if angebot.extern or (angebot.status or "") not in cloover.STATUS_AENDERBAR:
        return _antwort(request, angebot_id, {"ok": False, "meldung": MELDUNG_STATUS}, 400)
    try:
        laufzeit = int(str(form.get("laufzeit") or "").strip())
    except ValueError:
        return _antwort(request, angebot_id, {"ok": False, "meldung": MELDUNG_LAUFZEIT}, 400)
    if not cloover.LAUFZEIT_MIN <= laufzeit <= cloover.LAUFZEIT_MAX:
        return _antwort(request, angebot_id, {"ok": False, "meldung": MELDUNG_LAUFZEIT}, 400)
    anzahlung_roh = str(form.get("anzahlung") or "").strip()
    anzahlung = cloover_api.eur_parsen(anzahlung_roh) if anzahlung_roh else 0
    if anzahlung is None or anzahlung < 0:
        return _antwort(request, angebot_id, {"ok": False, "meldung": MELDUNG_ANZAHLUNG}, 400)
    ausblenden = form.get("ausblenden") == "on"
    benutzer = request.state.benutzer
    vorher = cloover.json_lesen(angebot)
    geaendert = (vorher.get("laufzeit_jahre") != laufzeit or vorher.get("anzahlung_cent") != anzahlung)

    def aktion():
        a = session.get(Angebot, angebot_id)
        cloover.json_schreiben(a, laufzeit_jahre=laufzeit, anzahlung_cent=anzahlung, ausgeblendet=ausblenden)

    _speichern(session, aktion)
    meldung = (f"Finanzierung gespeichert: Laufzeit {laufzeit} Jahre, Anzahlung "
               f"{cloover_api.eur_text(anzahlung)} €" + (", im PDF ausgeblendet" if ausblenden else ""))
    daten = cloover.json_lesen(angebot)
    if geaendert and not ausblenden and cloover.rate_noetig(session, angebot):
        # Netz-I/O erst nach dem Commit und ohne gehaltene Verbindung (v27-Regel)
        db.verbindung_freigeben(session)
        daten = cloover.rate_aktualisieren(angebot_id, benutzer_id=getattr(benutzer, "id", None))
        meldung += " – " + _rate_meldung(daten)
    return _antwort(request, angebot_id, {"ok": True, "meldung": meldung, "cloover": daten})


@router.post("/{angebot_id}/cloover/rate")
def cloover_rate(request: Request, angebot_id: int, session: Session = Depends(get_session)):
    """Knopf „Rate neu berechnen“: Rate unabhängig vom gespeicherten Stand neu bei Cloover abfragen."""
    if not _berechtigt(request):
        return _antwort(request, angebot_id, {"ok": False, "meldung": MELDUNG_RECHTE}, 403)
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote?meldung=Angebot+nicht+gefunden", status_code=303)
    if angebot.extern or (angebot.status or "") not in cloover.STATUS_AENDERBAR:
        return _antwort(request, angebot_id, {"ok": False, "meldung": MELDUNG_STATUS}, 400)
    ok, grund = cloover.relevant(session, angebot)
    if not ok:
        return _antwort(request, angebot_id,
                        {"ok": False, "meldung": cloover.MELDUNG_RATE_FEHLT.format(grund=grund)}, 400)
    benutzer = request.state.benutzer
    # Netzaufruf ohne offene Datenbanksitzung (v27-Regel): alles Nötige liest rate_aktualisieren selbst
    db.verbindung_freigeben(session)
    daten = cloover.rate_aktualisieren(angebot_id, erzwingen=True, benutzer_id=getattr(benutzer, "id", None))
    meldung = _rate_meldung(daten)
    return _antwort(request, angebot_id, {"ok": not daten.get("fehler"), "meldung": meldung, "cloover": daten})
