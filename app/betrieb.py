# v27 (PLAN_V17 Phase 129/132): Betrieb – /health, Betriebs-Seite,
# Wartungshinweis (Banner), nächtliche Sicherung mit Spiegelung nach
# BACKUP_ZIEL, SQLite-Pflege, Admin-Glocke bei Warnungen, laufende Importe,
# Schreibsperren-Messung. Keine Funktion hier hält eine Sitzung während
# Netz-/Datei-I/O (Spiegelung läuft ohne Sitzung; Ergebnis danach kurz
# geschrieben).

import ctypes
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from app import config

START_ZEIT = datetime.now()
_START_MONO = time.monotonic()
THREADS_GESETZT: int | None = None       # tatsächlich gesetzter Threadpool (lifespan)
POOL_INVARIANTE: tuple[bool, str] | None = None

BACKUP_AUFBEWAHRUNG_LOKAL_TAGE = 30
BACKUP_AUFBEWAHRUNG_ZIEL_TAGE = 90
BACKUP_WARN_STUNDEN = 26
POOL_WARN_PROZENT = 70
ADMIN_GLOCKE_ABSTAND_S = 3600
WARTUNG_STANDARD = "Dienstag 22:30–23:30"   # Antwort Andreas 07.10.2026
WARTUNG_STANDARD_WOCHENTAG = 1               # 0 = Montag
WARTUNG_STANDARD_VON = "22:30"
WARTUNG_STANDARD_BIS = "23:30"

_wartung_cache = {"stand": 0.0, "wert": None}
_wartung_sperre = threading.Lock()
_glocke_zuletzt = {"zeit": None}
_IMPORTE: dict[str, datetime] = {}
_importe_sperre = threading.Lock()
SCHREIBSPERRE = {"max_ms": 0, "max_zeit": None, "locked": 0, "messungen": 0}
_schreib_sperre = threading.Lock()


# --- Kennzahlen -------------------------------------------------------------------

def uptime_s() -> int:
    return int(time.monotonic() - _START_MONO)


def commit_hash() -> str:
    """Kurzer Commit-Hash aus .git (ohne Git-Programm): HEAD → Ref → Datei/packed-refs."""
    try:
        git = config.PROJEKT_ORDNER / ".git"
        kopf = (git / "HEAD").read_text(encoding="utf-8").strip()
        if kopf.startswith("ref:"):
            ref = kopf.split(":", 1)[1].strip()
            ref_datei = git / ref
            if ref_datei.exists():
                return ref_datei.read_text(encoding="utf-8").strip()[:7]
            packed = git / "packed-refs"
            if packed.exists():
                for zeile in packed.read_text(encoding="utf-8").splitlines():
                    teile = zeile.split()
                    if len(teile) == 2 and teile[1] == ref:
                        return teile[0][:7]
            return "?"
        return kopf[:7]
    except Exception:
        return "?"


def prozess_kennzahlen() -> dict:
    """RSS (Arbeitsspeicher) in MB und verbrauchte CPU-Sekunden des Prozesses –
    Windows über psapi, sonst resource; wirft nie."""
    rss_mb = None
    try:
        if sys.platform == "win32":
            class _PMC(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = _PMC()
            pmc.cb = ctypes.sizeof(_PMC)
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            kernel32.GetCurrentProcess.restype = ctypes.c_void_p
            psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PMC),
                                                   ctypes.c_uint32]
            psapi.GetProcessMemoryInfo.restype = ctypes.c_int
            handle = kernel32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                rss_mb = round(pmc.WorkingSetSize / 1_000_000, 1)
        else:
            import resource
            rss_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000, 1)
    except Exception:
        pass
    try:
        zeiten = os.times()
        cpu_s = round(zeiten.user + zeiten.system, 1)
    except Exception:
        cpu_s = None
    return {"rss_mb": rss_mb, "cpu_s": cpu_s, "threads": threading.active_count()}


def schreibsperre_messen(dauer_ms: int, locked: bool = False) -> None:
    """Aus routers/angebote._speichern: Wartezeit beim Commit (Schreibsperre)."""
    with _schreib_sperre:
        SCHREIBSPERRE["messungen"] += 1
        if locked:
            SCHREIBSPERRE["locked"] += 1
        if dauer_ms > SCHREIBSPERRE["max_ms"]:
            SCHREIBSPERRE["max_ms"] = int(dauer_ms)
            SCHREIBSPERRE["max_zeit"] = datetime.now()


def schreibsperre_zuruecksetzen() -> None:
    with _schreib_sperre:
        SCHREIBSPERRE.update(max_ms=0, max_zeit=None, locked=0, messungen=0)


# --- laufende Importe -----------------------------------------------------------------

@contextmanager
def import_markieren(name: str):
    """Phase 128: ``with betrieb.import_markieren("Preisliste"):`` – der Import
    erscheint solange im Betriebs-Status und in /health."""
    with _importe_sperre:
        _IMPORTE[name] = datetime.now()
    try:
        yield
    finally:
        with _importe_sperre:
            _IMPORTE.pop(name, None)


def laufende_importe() -> list[dict]:
    with _importe_sperre:
        return [{"name": n, "seit": z, "sekunden": int((datetime.now() - z).total_seconds())}
                for n, z in sorted(_IMPORTE.items(), key=lambda kv: kv[1])]


# --- Wartungshinweis (Phase 132) ----------------------------------------------------------

def _zeit_lesen(text: str):
    for muster in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime((text or "").strip(), muster)
        except ValueError:
            continue
    return None


def banner_text(von: datetime, bis: datetime) -> str:
    """Wortlaut Plan: „Wartung heute von <von> bis <bis> Uhr – bitte Arbeit bis
    dahin speichern. Das Tool ist in dieser Zeit kurz nicht erreichbar.“
    (liegt das Fenster nicht heute: „Wartung am <Datum> von …“)."""
    wann = "heute" if von.date() == datetime.now().date() else f"am {von:%d.%m.}"
    return (f"Wartung {wann} von {von:%H:%M} bis {bis:%H:%M} Uhr – bitte Arbeit bis dahin "
            "speichern. Das Tool ist in dieser Zeit kurz nicht erreichbar.")


def wartungshinweis(session) -> dict | None:
    """Aktiver Hinweis aus den Einstellungen wartung_von/wartung_bis/wartung_text
    (abgelaufen = None)."""
    from app.models import einstellung_holen
    von = _zeit_lesen(einstellung_holen(session, "wartung_von", ""))
    bis = _zeit_lesen(einstellung_holen(session, "wartung_bis", ""))
    if von is None or bis is None or bis < datetime.now():
        return None
    text = einstellung_holen(session, "wartung_text", "") or banner_text(von, bis)
    return {"von": von, "bis": bis, "text": text, "banner": banner_text(von, bis),
            "laeuft": von <= datetime.now() <= bis}


def wartungshinweis_aktuell(erzwingen: bool = False, session=None) -> dict | None:
    """Für die Middleware: 60 s zwischengespeichert; liest mit der übergebenen
    Sitzung (Middleware) oder einer eigenen kurzen – nie zwei Verbindungen
    gleichzeitig (Befund B8 der Inventur)."""
    jetzt = time.monotonic()
    with _wartung_sperre:
        if not erzwingen and jetzt - _wartung_cache["stand"] < 60:
            return _wartung_cache["wert"]
    eigen = session is None
    if eigen:
        from app.db import SessionLocal
        session = SessionLocal()
    try:
        wert = wartungshinweis(session)
    except Exception:
        wert = None
    finally:
        if eigen:
            session.close()
    with _wartung_sperre:
        _wartung_cache.update(stand=jetzt, wert=wert)
    return wert


def wartung_setzen(session, von, bis, text: str = "") -> dict | None:
    from app.models import einstellung_setzen
    von_dt = von if isinstance(von, datetime) else _zeit_lesen(von)
    bis_dt = bis if isinstance(bis, datetime) else _zeit_lesen(bis)
    if von_dt is None or bis_dt is None or bis_dt <= von_dt:
        raise ValueError("Wartungsfenster: „von“ und „bis“ müssen gültig sein und bis > von.")
    einstellung_setzen(session, "wartung_von", von_dt.strftime("%Y-%m-%dT%H:%M"))
    einstellung_setzen(session, "wartung_bis", bis_dt.strftime("%Y-%m-%dT%H:%M"))
    einstellung_setzen(session, "wartung_text", (text or "").strip()[:300])
    session.commit()
    return wartungshinweis_aktuell(erzwingen=True)


def wartung_loeschen(session) -> None:
    from app.models import einstellung_setzen
    for name in ("wartung_von", "wartung_bis", "wartung_text"):
        einstellung_setzen(session, name, "")
    session.commit()
    wartungshinweis_aktuell(erzwingen=True)


def naechstes_wartungsfenster(jetzt: datetime | None = None) -> tuple[datetime, datetime]:
    """Standardfenster Dienstag 22:30–23:30 (Andreas 07.10.2026): nächster Dienstag
    (heute, falls das Fenster noch nicht vorbei ist)."""
    jetzt = jetzt or datetime.now()
    tage = (WARTUNG_STANDARD_WOCHENTAG - jetzt.weekday()) % 7
    von_h, von_m = (int(t) for t in WARTUNG_STANDARD_VON.split(":"))
    bis_h, bis_m = (int(t) for t in WARTUNG_STANDARD_BIS.split(":"))
    tag = (jetzt + timedelta(days=tage)).date()
    von = datetime.combine(tag, datetime.min.time()).replace(hour=von_h, minute=von_m)
    bis = datetime.combine(tag, datetime.min.time()).replace(hour=bis_h, minute=bis_m)
    if bis <= jetzt:
        von += timedelta(days=7)
        bis += timedelta(days=7)
    return von, bis


# --- Backup (Phase 129) -------------------------------------------------------------------

def backup_letztes(session=None) -> dict:
    """Letzte Sicherung: Zeit der jüngsten lokalen Datei data\\backups\\
    angebotstool-*.db plus Ergebnis der letzten Spiegelung (Einstellung
    backup_letztes = „<Zeit>|<ok|fehler|kein Ziel>|<Text>“)."""
    juengste = None
    try:
        dateien = sorted(config.BACKUP_ORDNER.glob("angebotstool-*.db"),
                         key=lambda p: p.stat().st_mtime)
        if dateien:
            juengste = datetime.fromtimestamp(dateien[-1].stat().st_mtime)
    except OSError:
        pass
    ziel_zeit, ziel_status, ziel_text = None, "", ""
    eigen = session is None
    if eigen:
        from app.db import SessionLocal
        session = SessionLocal()
    try:
        from app.models import einstellung_holen
        wert = einstellung_holen(session, "backup_letztes", "")
        if wert:
            teile = wert.split("|", 2)
            ziel_zeit = _zeit_lesen(teile[0]) if teile else None
            ziel_status = teile[1] if len(teile) > 1 else ""
            ziel_text = teile[2] if len(teile) > 2 else ""
    except Exception:
        pass
    finally:
        if eigen:
            session.close()
    return {"lokal_zeit": juengste, "ziel_zeit": ziel_zeit, "ziel_status": ziel_status,
            "ziel_text": ziel_text, "ziel": config.BACKUP_ZIEL}


def _robocopy(quelle: Path, ziel: Path, log: Path, spiegeln: bool) -> tuple[bool, str]:
    """robocopy (Exit-Code < 8 = ok); ohne robocopy (Linux/Tests) shutil."""
    ziel.mkdir(parents=True, exist_ok=True)
    programm = shutil.which("robocopy")
    if programm:
        befehl = [programm, str(quelle), str(ziel), "/E", "/R:2", "/W:5", "/NP",
                  "/NFL", "/NDL", "/NJH", f"/LOG+:{log}"]
        if spiegeln:
            befehl.insert(3, "/MIR")
        ergebnis = subprocess.run(befehl, capture_output=True, text=True, timeout=3600)
        return ergebnis.returncode < 8, f"robocopy {quelle.name}: Exit {ergebnis.returncode}"
    shutil.copytree(quelle, ziel, dirs_exist_ok=True)
    return True, f"kopiert {quelle.name}"


def _ziel_aufraeumen(ziel: Path, tage: int) -> int:
    grenze = datetime.now() - timedelta(days=tage)
    entfernt = 0
    for datei in ziel.glob("angebotstool-*.db"):
        try:
            if datetime.fromtimestamp(datei.stat().st_mtime) < grenze:
                datei.unlink()
                entfernt += 1
        except OSError:
            pass
    return entfernt


def backup_lauf(ziel: str | None = None, melden: bool = True) -> dict:
    """Nächtlich 02:30 per Scheduler (und „Backup jetzt“ auf der Betriebs-Seite):
    (a) SQLite-Backup-API nach data\\backups (30 Tage), (b) Spiegelung von
    backups, angebote (inkl. signiert), projekte und .env nach BACKUP_ZIEL
    (robocopy, Log data\\backups\\ziel.log, Aufbewahrung am Ziel 90 Tage),
    (c) Ergebnis in Einstellung backup_letztes; Fehlschlag → Glocke an Admins
    + Fehlerprotokoll. Ohne Ziel bleibt es bei der lokalen Sicherung."""
    from app.db import kurz, taegliches_backup
    from app.models import einstellung_setzen
    start = datetime.now()
    ergebnis = {"lokal": False, "ziel": ziel if ziel is not None else config.BACKUP_ZIEL,
                "status": "", "schritte": [], "fehler": ""}
    try:
        taegliches_backup(BACKUP_AUFBEWAHRUNG_LOKAL_TAGE)
        ergebnis["lokal"] = True
        ergebnis["schritte"].append("lokale Sicherung ok")
    except Exception as problem:
        ergebnis["fehler"] = f"lokale Sicherung: {problem}"
    zielordner = ergebnis["ziel"]
    if not zielordner:
        ergebnis["status"] = "kein Ziel" if not ergebnis["fehler"] else "fehler"
    elif not ergebnis["fehler"]:
        ziel_pfad = Path(zielordner)
        log = config.BACKUP_ORDNER / "ziel.log"
        try:
            ziel_pfad.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as f:
                f.write(f"\n=== Backup {start:%d.%m.%Y %H:%M} → {ziel_pfad} ===\n")
            for name, spiegeln in (("backups", False), ("angebote", True), ("projekte", True)):
                quelle = config.DATA_ORDNER / name
                if not quelle.exists():
                    ergebnis["schritte"].append(f"{name} fehlt – übersprungen")
                    continue
                ok, text = _robocopy(quelle, ziel_pfad / name, log, spiegeln)
                ergebnis["schritte"].append(text)
                if not ok:
                    ergebnis["fehler"] = text
                    break
            if not ergebnis["fehler"]:
                env = config.PROJEKT_ORDNER / ".env"
                if env.exists():
                    shutil.copy2(env, ziel_pfad / ".env")
                    ergebnis["schritte"].append(".env kopiert")
                entfernt = _ziel_aufraeumen(ziel_pfad / "backups", BACKUP_AUFBEWAHRUNG_ZIEL_TAGE)
                if entfernt:
                    ergebnis["schritte"].append(f"{entfernt} alte Sicherung(en) am Ziel entfernt")
        except Exception as problem:
            ergebnis["fehler"] = f"Spiegelung: {problem}"
        ergebnis["status"] = "fehler" if ergebnis["fehler"] else "ok"
    else:
        ergebnis["status"] = "fehler"
    text = "; ".join(ergebnis["schritte"])
    if ergebnis["fehler"]:
        text = ergebnis["fehler"] + (" | " + text if text else "")
    try:
        with kurz() as s:
            einstellung_setzen(s, "backup_letztes",
                               f"{start:%Y-%m-%dT%H:%M}|{ergebnis['status']}|{text[:200]}")
    except Exception:
        pass
    if ergebnis["fehler"] and melden:
        try:
            from app import fehlerprotokoll
            fehlerprotokoll.eintragen_text("Backup", ergebnis["fehler"], text, "/parametrierung/betrieb")
        except Exception:
            pass
        admins_benachrichtigen(f"Backup fehlgeschlagen: {ergebnis['fehler'][:200]}")
    return ergebnis


# --- Glocke an Admins ----------------------------------------------------------------

def admins_benachrichtigen(text: str, link: str = "/parametrierung/betrieb") -> int:
    """Glocke an alle aktiven Admins (kurze Sitzung); liefert die Anzahl."""
    try:
        from app import projektierung as kern
        from app.db import kurz
        from app.models import Benutzer
        with kurz() as s:
            ids = [b.id for b in s.query(Benutzer)
                   .filter(Benutzer.aktiv.is_(True), Benutzer.rolle == "admin")]
            if ids:
                kern.benachrichtigen(s, ids, text[:500], link, art="system")
            return len(ids)
    except Exception:
        return 0


# --- /health (Phase 129) ------------------------------------------------------------------

def health() -> dict:
    """Status ok | warn | fehler mit Gründen. warn: Pool > 70 % belegt, ein
    Scheduler > 2 Intervalle ohne Lauf, letztes Backup > 26 h, kein
    Backup-Ziel, Spiegelung fehlgeschlagen, Pool-Invariante verletzt;
    fehler: Datenbank nicht erreichbar (HTTP 503)."""
    from app import db, scheduler
    jetzt = datetime.now()
    gruende: list[str] = []
    db_ok, db_ms = True, None
    # Datenbank-Probe über eine eigene sqlite3-Verbindung (nicht über den Pool):
    # ein erschöpfter Pool darf /health nicht 10 s blockieren und nicht als
    # „fehler“ (503 → Wächter-Neustart) erscheinen – das ist eine Warnung
    try:
        t0 = time.perf_counter()
        probe = sqlite3.connect(str(config.DB_PFAD), timeout=2)
        try:
            probe.execute("SELECT 1").fetchone()
        finally:
            probe.close()
        db_ms = int((time.perf_counter() - t0) * 1000)
    except Exception as problem:
        db_ok = False
        gruende.append(f"Datenbank: {type(problem).__name__}: {str(problem)[:120]}")
    pool = db.pool_kennzahlen()
    if pool["checked_out"] >= pool["maximum"]:
        gruende.append("Pool erschöpft (alle Verbindungen belegt)")
    elif pool["prozent"] > POOL_WARN_PROZENT:
        gruende.append(f"Pool {pool['prozent']} % belegt")
    laeufe = scheduler.status_liste()
    for lauf in laeufe:
        if lauf["ueberfaellig"]:
            gruende.append(f"Scheduler „{lauf['name']}“ ohne Lauf")
    backup = backup_letztes() if db_ok else {"lokal_zeit": None, "ziel_zeit": None,
                                              "ziel_status": "", "ziel_text": "",
                                              "ziel": config.BACKUP_ZIEL}
    if not config.BACKUP_ZIEL:
        gruende.append("kein Backup-Ziel")
    letzte = backup["lokal_zeit"]
    if letzte is None or jetzt - letzte > timedelta(hours=BACKUP_WARN_STUNDEN):
        gruende.append("letztes Backup > 26 h" if letzte else "noch kein Backup")
    if backup["ziel_status"] == "fehler":
        gruende.append("Backup-Spiegelung fehlgeschlagen")
    if POOL_INVARIANTE is not None and not POOL_INVARIANTE[0]:
        gruende.append("Pool-Invariante verletzt")
    mail_ausgang = {"offen": None, "fehler_24h": None}
    if db_ok:
        try:
            from app import benachrichtigungen
            from app.db import kurz
            with kurz() as s:
                mail_ausgang = benachrichtigungen.mail_ausgang_zaehler(s)
            if (mail_ausgang["offen"] or 0) > 50:
                gruende.append(f"Mail-Ausgang: {mail_ausgang['offen']} Mails offen")
        except Exception:
            pass
    status = "fehler" if not db_ok else ("warn" if gruende else "ok")
    return {
        "status": status, "version": config.VERSION, "commit": commit_hash(),
        "db": "ok" if db_ok else "fehler", "db_ms": db_ms,
        "pool": {"size": pool["size"], "checked_out": pool["checked_out"],
                 "overflow": pool["overflow"], "maximum": pool["maximum"],
                 "prozent": pool["prozent"]},
        "threads": THREADS_GESETZT or config.WORKER_THREADS,
        "scheduler": [{"name": l["name"], "letzter_start": l["letzter_start"],
                       "ok": l["ok"], "zustand": l["zustand"]} for l in laeufe],
        "backup_letztes": backup["lokal_zeit"], "backup_ziel": backup["ziel"],
        "backup_ziel_status": backup["ziel_status"], "backup_ziel_zeit": backup["ziel_zeit"],
        "wal_mb": db.wal_groesse_mb(), "uptime_s": uptime_s(),
        "importe": [i["name"] for i in laufende_importe()],
        "mail_ausgang": mail_ausgang,
        "schreibsperre_max_ms": SCHREIBSPERRE["max_ms"],
        "schreibsperre_locked": SCHREIBSPERRE["locked"],
        "prozess": prozess_kennzahlen(),
        "gruende": gruende, "zeit": jetzt,
    }


def health_json(daten: dict) -> dict:
    """datetime → ISO-Text (für JSONResponse)."""
    def wandeln(wert):
        if isinstance(wert, datetime):
            return wert.strftime("%Y-%m-%dT%H:%M:%S")
        if isinstance(wert, dict):
            return {k: wandeln(v) for k, v in wert.items()}
        if isinstance(wert, list):
            return [wandeln(v) for v in wert]
        return wert
    return wandeln(daten)


def wache_lauf() -> dict:
    """Scheduler alle 5 Minuten: bei warn/fehler eine Admin-Glocke (höchstens
    eine je Stunde) – Zwischenstand, bis die IT ein Monitoring anbindet."""
    daten = health()
    ergebnis = {"status": daten["status"], "gruende": len(daten["gruende"]), "glocke": 0}
    if daten["status"] == "ok":
        return ergebnis
    zuletzt = _glocke_zuletzt["zeit"]
    if zuletzt is not None and (datetime.now() - zuletzt).total_seconds() < ADMIN_GLOCKE_ABSTAND_S:
        return ergebnis
    text = ("Betriebswarnung: " + "; ".join(daten["gruende"]))[:500]
    ergebnis["glocke"] = admins_benachrichtigen(text)
    _glocke_zuletzt["zeit"] = datetime.now()
    return ergebnis


def pflege_lauf() -> dict:
    """Scheduler 02:40: WAL-Checkpoint (TRUNCATE) + PRAGMA optimize."""
    from app import db
    return db.wal_pflege()


def login_protokoll_lauf() -> dict:
    from app import auth
    from app.db import kurz
    with kurz() as s:
        return {"entfernt": auth.login_protokoll_aufraeumen(s)}


def scheduler_registrieren() -> None:
    """Läufe des Betriebs beim Start anmelden (main.lifespan)."""
    from app import scheduler
    scheduler.registrieren("backup", 24 * 3600, backup_lauf, taeglich_um="02:30",
                           beschreibung="Sicherung + Spiegelung nach BACKUP_ZIEL")
    scheduler.registrieren("sqlite-pflege", 24 * 3600, pflege_lauf, taeglich_um="02:40",
                           beschreibung="WAL-Checkpoint (TRUNCATE) + PRAGMA optimize")
    scheduler.registrieren("betrieb-wache", 300, wache_lauf, start_verzoegerung_s=120,
                           beschreibung="Health-Prüfung, Admin-Glocke bei Warnung (max. 1/h)")
    scheduler.registrieren("login-protokoll", 24 * 3600, login_protokoll_lauf,
                           taeglich_um="03:10",
                           beschreibung="Login-Protokoll älter als 90 Tage entfernen")
