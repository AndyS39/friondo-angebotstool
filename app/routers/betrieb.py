# v27 (PLAN_V17 Phase 129/132): GET /health (ohne Anmeldung, nur Lesen) und
# Parametrierung → Betrieb (Admin): Kacheln Version/Commit, Uptime, Pool,
# Threads, WAL, Backup, Scheduler-Tabelle mit „jetzt ausführen“, Zugriffs-
# statistik (24 h), laufende Importe, Wartungshinweis setzen.

from datetime import datetime, timedelta
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import anfrage, betrieb, config, scheduler, zugriffslog
from app import db as db_modul
from app.db import get_session
from app.templating import render

router = APIRouter()


@router.get("/health")
def health_route():
    """JSON-Status für Wächter-Aufgabe, health-pruefen.ps1 und Monitoring;
    HTTP 503 bei status=fehler (Datenbank nicht erreichbar)."""
    daten = betrieb.health()
    return JSONResponse(betrieb.health_json(daten),
                        status_code=503 if daten["status"] == "fehler" else 200,
                        headers={"Cache-Control": "no-store"})


def _nur_admin(request: Request):
    benutzer = request.state.benutzer
    if benutzer is None or benutzer.rolle != "admin":
        return RedirectResponse("/parametrierung", status_code=303)
    return None


def _zurueck(meldung: str) -> RedirectResponse:
    return RedirectResponse("/parametrierung/betrieb?meldung=" + quote_plus(meldung),
                            status_code=303)


def scheduler_uebersicht(session: Session) -> list[dict]:
    """Läufe im Speicher (dieser Prozess) ergänzt um die Tabelle
    scheduler_status (Stand vor einem Neustart)."""
    from app.models import SchedulerStatus
    tabelle = {z.name: z for z in session.query(SchedulerStatus)}
    zeilen = []
    gesehen = set()
    for lauf in scheduler.status_liste():
        zeile = dict(lauf)
        alt = tabelle.get(lauf["name"])
        zeile["vor_neustart"] = False
        if alt is not None and lauf["letzter_start"] is None and alt.letzter_start is not None:
            zeile.update(letzter_start=alt.letzter_start, letzte_dauer_ms=alt.letzte_dauer_ms,
                         letzter_fehler=alt.letzter_fehler, letztes_ergebnis=alt.letztes_ergebnis,
                         laeufe=alt.laeufe, fehler=alt.fehler, vor_neustart=True)
        zeilen.append(zeile)
        gesehen.add(lauf["name"])
    for name, alt in sorted(tabelle.items()):
        if name in gesehen:
            continue
        zeilen.append({"name": name, "beschreibung": alt.beschreibung,
                       "intervall_s": alt.intervall_s, "taeglich_um": None,
                       "letzter_start": alt.letzter_start, "letzte_dauer_ms": alt.letzte_dauer_ms,
                       "letzter_fehler": alt.letzter_fehler, "letztes_ergebnis": alt.letztes_ergebnis,
                       "laeufe": alt.laeufe, "fehler": alt.fehler, "naechster_start": None,
                       "zustand": "nicht registriert (Tabelle)", "aktiv": False, "laeuft": False,
                       "ok": True, "ueberfaellig": False, "vor_neustart": True})
    return zeilen


def _uptime_text(sekunden: int) -> str:
    tage, rest = divmod(int(sekunden), 86400)
    stunden, rest = divmod(rest, 3600)
    minuten = rest // 60
    teile = []
    if tage:
        teile.append(f"{tage} Tag{'e' if tage != 1 else ''}")
    teile.append(f"{stunden} h {minuten} min")
    return " ".join(teile)


@router.get("/parametrierung/betrieb")
def betrieb_seite(request: Request, session: Session = Depends(get_session)):
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    daten = betrieb.health()
    zugriffe = zugriffslog.auswerten(24)
    laeufe = scheduler_uebersicht(session)
    wartung = betrieb.wartungshinweis(session)
    von_vorschlag, bis_vorschlag = betrieb.naechstes_wartungsfenster()
    return render(request, "konfiguration/betrieb.html", aktiv="/parametrierung",
                  health=daten, uptime_text=_uptime_text(daten["uptime_s"]),
                  pool=daten["pool"], pool_groesse=f"{db_modul.POOL_SIZE} + {db_modul.MAX_OVERFLOW}",
                  pool_timeout=db_modul.POOL_TIMEOUT,
                  threads=config.WORKER_THREADS, threads_gesetzt=betrieb.THREADS_GESETZT,
                  pool_invariante=betrieb.POOL_INVARIANTE,
                  wal_mb=daten["wal_mb"], backup=betrieb.backup_letztes(session),
                  backup_ziel=config.BACKUP_ZIEL,
                  laeufe=laeufe, zugriffe=zugriffe, importe=betrieb.laufende_importe(),
                  schreibsperre=dict(betrieb.SCHREIBSPERRE), prozess=daten["prozess"],
                  wartung=wartung, wartung_standard=betrieb.WARTUNG_STANDARD,
                  von_vorschlag=von_vorschlag.strftime("%Y-%m-%dT%H:%M"),
                  bis_vorschlag=bis_vorschlag.strftime("%Y-%m-%dT%H:%M"),
                  fehler_log=str(config.DATA_ORDNER / "fehler.log"),
                  zugriff_log=zugriffe["log_pfad"],
                  meldung=request.query_params.get("meldung", ""))


@router.post("/parametrierung/betrieb/lauf/{name}")
def lauf_ausfuehren(request: Request, name: str):
    """Knopf „jetzt ausführen“ – startet den Lauf in einem eigenen Thread
    (Single-Flight); Ergebnis, Dauer und Fehler erscheinen in der Tabelle."""
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    ergebnis = scheduler.im_hintergrund_ausfuehren(name)
    if not ergebnis["gestartet"]:
        return _zurueck(f"Lauf „{name}“ nicht gestartet: {ergebnis['grund']}.")
    return _zurueck(f"Lauf „{name}“ gestartet – Ergebnis und Dauer stehen gleich in der "
                    "Tabelle (Seite neu laden).")


@router.post("/parametrierung/betrieb/backup")
def backup_jetzt(request: Request):
    """„Backup jetzt“ – als Hintergrundlauf „backup“ (robocopy kann Minuten dauern)."""
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    if scheduler.holen("backup") is None:
        betrieb.scheduler_registrieren()
    ergebnis = scheduler.im_hintergrund_ausfuehren("backup")
    if not ergebnis["gestartet"]:
        return _zurueck("Backup nicht gestartet: " + ergebnis["grund"] + ".")
    return _zurueck("Backup gestartet – Ergebnis in der Kachel „Letztes Backup“ und in der "
                    "Scheduler-Tabelle (Seite neu laden).")


@router.post("/parametrierung/betrieb/pflege")
def pflege_jetzt(request: Request):
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    ergebnis = betrieb.pflege_lauf()
    return _zurueck(f"SQLite-Pflege ausgeführt: WAL {ergebnis['wal_mb_vorher']} MB → "
                    f"{ergebnis['wal_mb_nachher']} MB (eingespielt {ergebnis['eingespielt']}).")


@router.post("/parametrierung/betrieb/wartung")
def wartung_speichern(request: Request, session: Session = Depends(get_session)):
    """Wartungshinweis setzen (Banner für alle Rollen) oder entfernen."""
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    if form.get("loeschen") == "1":
        betrieb.wartung_loeschen(session)
        return _zurueck("Wartungshinweis entfernt.")
    try:
        hinweis = betrieb.wartung_setzen(session, form.get("von") or "", form.get("bis") or "",
                                         form.get("text") or "")
    except ValueError as problem:
        return _zurueck(str(problem))
    return _zurueck("Wartungshinweis gesetzt: " + (hinweis["banner"] if hinweis else ""))
