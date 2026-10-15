# Zentraler Planungskalender – v33 (PLAN_V20 Phase 169, Agent K). Router mit Präfix /kalender:
#   GET  /kalender                    Seite (Template kalender/zentral.html, Daten nachgelagert)
#   GET  /kalender/daten.json         Einträge je Quelle (?von=&bis=&personen=1,2&ansicht=)
#   POST /kalender/verschieben        Drag: Tool-Termin verschieben (JSON, Konflikte → Bestätigung)
#   POST /kalender/einstellung        Gruppen/Wochenende/Ansicht je Nutzer und Einstieg merken
#   GET  /kalender/suche.json         Doppelklick: Kunde/Lead bzw. Projekt für den neuen Termin
# Rechte: auth.py lässt /kalender für Admin, Innendienst, Projektierung, Lead-Management und
# Montage (Basisrollen) durch; Montage-/Service-Benutzer sehen nur sich und ihr Team (read-only).
# v27-Regeln: def-Routen, anfrage.json_lesen, kein Netzaufruf (Belegtzeiten nur aus der Tabelle).
import time
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import anfrage
from app import kalender_zentral as kern
from app.db import get_session
from app.templating import render

router = APIRouter(prefix="/kalender")


def _benutzer(request: Request):
    return getattr(request.state, "benutzer", None)


def _json_daten(request: Request) -> dict:
    try:
        daten = anfrage.json_lesen(request)
    except Exception:   # noqa: BLE001 – kein/ungültiges JSON → Formular
        daten = None
    if not isinstance(daten, dict):
        try:
            daten = dict(anfrage.formular(request))
        except Exception:   # noqa: BLE001
            daten = {}
    return daten


@router.get("")
def seite(request: Request, session: Session = Depends(get_session)):
    """Seite /kalender – Vorbelegung nach Einstieg (?gruppe=projektierung|vertrieb|alle),
    ?person=<id> (nur diese Person), ?datum=YYYY-MM-DD, ?ansicht=tag|woche|monat, ?q=."""
    benutzer = _benutzer(request)
    if benutzer is None:
        return RedirectResponse("/login", status_code=303)
    q = request.query_params
    kontext = kern.seiten_kontext(session, benutzer, gruppe_param=q.get("gruppe", ""),
                                  person_param=q.get("person", ""), datum_param=q.get("datum", ""),
                                  ansicht_param=q.get("ansicht", ""), q=q.get("q", ""))
    aktiv = {"projektierung": "/projektierung", "vertrieb": "/lead-management"}.get(
        kontext["einstieg"], "/kalender")
    return render(request, "kalender/zentral.html", aktiv=aktiv, benutzer=benutzer,
                  meldung=q.get("meldung", ""), **kontext)


@router.get("/daten.json")
def daten_json(request: Request, von: str = "", bis: str = "", personen: str = "",
               ansicht: str = "woche", session: Session = Depends(get_session)):
    """Einträge aller Quellen für die Personen im Zeitraum (von/bis einschließlich)."""
    benutzer = _benutzer(request)
    if benutzer is None:
        return JSONResponse({"ok": False, "meldung": "Nicht angemeldet."}, status_code=401)
    ids = [p for p in (personen or "").replace(";", ",").split(",") if p.strip()]
    if not von:
        von = datetime.now().strftime("%Y-%m-%d")
    antwort = kern.daten(session, benutzer, von, bis or von, ids,
                         ansicht if ansicht in kern.ANSICHTEN else "woche")
    antwort["ok"] = True
    return JSONResponse(antwort)


@router.post("/verschieben")
def verschieben(request: Request, session: Session = Depends(get_session)):
    """Drag: {quelle, id, beginn, ende?, person_id?, bestaetigt?} → {ok, meldung, konflikte,
    bestaetigung_noetig?}. Schreibt über die Kernfunktionen der Module (Rollback + eine
    Wiederholung bei „database is locked“ – Muster _speichern)."""
    benutzer = _benutzer(request)
    if benutzer is None:
        return JSONResponse({"ok": False, "meldung": "Nicht angemeldet."}, status_code=401)
    daten = _json_daten(request)
    bestaetigt = str(daten.get("bestaetigt") or "").lower() in ("1", "true", "ja", "yes")
    antwort = None
    for versuch in range(2):
        try:
            antwort = kern.verschieben(session, benutzer, daten.get("quelle"), daten.get("id"),
                                       daten.get("beginn"), daten.get("ende"),
                                       daten.get("person_id"), bestaetigt)
            if antwort.get("ok"):
                session.commit()
            else:
                session.rollback()
            break
        except OperationalError as fehler:
            session.rollback()
            if "locked" not in str(fehler).lower() or versuch == 1:
                antwort = {"ok": False, "meldung": "Datenbank kurz belegt – bitte erneut versuchen.",
                           "konflikte": []}
                break
            time.sleep(0.7)
    status = 200 if antwort.get("ok") or antwort.get("bestaetigung_noetig") else 400
    if antwort.get("meldung") == kern.KEIN_RECHT or antwort.get("meldung") == kern.NUR_LESEN_TEXT:
        status = 403
    return JSONResponse(antwort, status_code=status)


@router.post("/einstellung")
def einstellung(request: Request, session: Session = Depends(get_session)):
    """Auswahl je Nutzer merken: {einstieg, gruppen[], wochenende, ansicht}."""
    benutzer = _benutzer(request)
    if benutzer is None:
        return JSONResponse({"ok": False, "meldung": "Nicht angemeldet."}, status_code=401)
    daten = _json_daten(request)
    gruppen = daten.get("gruppen")
    if isinstance(gruppen, str):
        gruppen = [g for g in gruppen.split(",") if g]
    wochenende = daten.get("wochenende")
    if wochenende is not None:
        wochenende = str(wochenende).lower() in ("1", "true", "ja", "yes")
    eintrag = kern.auswahl_speichern(session, benutzer, str(daten.get("einstieg") or "alle"),
                                     gruppen if isinstance(gruppen, list) else None,
                                     wochenende, daten.get("ansicht"))
    session.commit()
    return JSONResponse({"ok": True, "auswahl": eintrag})


@router.get("/suche.json")
def suche_json(request: Request, q: str = "", art: str = "lead", person: str = "",
               beginn: str = "", session: Session = Depends(get_session)):
    """Doppelklick auf freie Fläche: Treffer mit Link in den Termin-Dialog des Moduls."""
    benutzer = _benutzer(request)
    if benutzer is None:
        return JSONResponse({"ok": False, "treffer": []}, status_code=401)
    treffer = kern.suche(session, benutzer, q, art, person_id=person, beginn=beginn)
    return JSONResponse({"ok": True, "treffer": treffer})
