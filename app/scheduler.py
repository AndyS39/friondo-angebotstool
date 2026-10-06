# v27 (PLAN_V17 Phase 128): gemeinsamer Rahmen für alle Hintergrundläufe.
# Jeder Lauf hat einen Namen, ein Intervall (oder eine feste Tageszeit), eine
# Single-Flight-Sperre (kein zweiter Start, solange der vorige läuft), einen
# Zufallsversatz von 0–30 s beim ersten Start (nicht alle Läufe zur gleichen
# Sekunde), Laufzeitmessung, letzten Fehler und Zähler. Der Status steht im
# Speicher (für /health) und in der Tabelle scheduler_status (Parametrierung →
# Betrieb, „jetzt ausführen“ je Lauf).
#
# Regeln (CLAUDE.md, Fachliche Regeln → Betrieb): jede neue Hintergrundaufgabe
# wird hier registriert – kein eigener threading.Thread mehr in den Modulen.
# Ein Lauf hält nie eine Sitzung während Netz-I/O (db.kurz() zum Lesen, dann
# Sitzung zu, dann Netz, dann neue kurze Sitzung zum Zurückschreiben) und nie
# länger als 2 s ohne Netz-I/O; große Mengen in Blöcken mit Commit je Block.
#
# Die bestehenden Module behalten ihr Verhalten: Läufe mit Tages-Schaltern
# (07:00-Lauf, Digest 07:15, Löschlauf 03:00) bleiben 5-Minuten-Läufe mit
# Datumsprüfung in der Funktion; neue Läufe (Backup 02:30, SQLite-Pflege 02:40)
# nutzen taeglich_um.

import logging
import random
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

logger = logging.getLogger("angebotstool")

JITTER_MAX_S = 30          # Zufallsversatz beim ersten Start
SCHRITT_S = 5              # Wartezeit wird in kleinen Schritten geschlafen (sauberes Stoppen)
FEHLER_MAX = 500


@dataclass
class Lauf:
    name: str
    intervall_s: int
    funktion: Callable[[], object]
    beschreibung: str = ""
    start_verzoegerung_s: int = 0
    taeglich_um: Optional[str] = None            # "02:30" → einmal täglich
    aktiv: Optional[Callable[[], object]] = None  # () -> True | False | "Grund" (inaktiv)
    sperre: threading.Lock = field(default_factory=threading.Lock)
    registriert_am: datetime = field(default_factory=datetime.now)
    letzter_start: Optional[datetime] = None
    letztes_ende: Optional[datetime] = None
    letzte_dauer_ms: Optional[int] = None
    letzter_fehler: str = ""
    letztes_ergebnis: str = ""
    laeufe: int = 0
    fehler: int = 0
    naechster_start: Optional[datetime] = None
    zustand: str = "wartet"
    thread: Optional[threading.Thread] = None

    @property
    def intervall_effektiv_s(self) -> int:
        return 24 * 3600 if self.taeglich_um else int(self.intervall_s)

    def ist_aktiv(self) -> tuple[bool, str]:
        """(aktiv, Grund) – aktiv-Callable darf False oder einen Grund-Text liefern."""
        if self.aktiv is None:
            return True, ""
        try:
            ergebnis = self.aktiv()
        except Exception as problem:
            return False, f"Prüfung fehlgeschlagen: {problem}"[:200]
        if ergebnis is True or ergebnis is None:
            return True, ""
        if ergebnis is False:
            return False, "inaktiv"
        return False, str(ergebnis)[:200]

    def ueberfaellig(self, jetzt: Optional[datetime] = None,
                     aktiv: Optional[bool] = None) -> bool:
        """Für /health: mehr als zwei Intervalle ohne Lauf (ab Registrierung
        bzw. ab dem letzten Start); inaktive Läufe zählen nicht. `aktiv` kann
        vom Aufrufer durchgereicht werden (Agent-A-Hinweis: ist_aktiv() öffnet
        bei lead-parser eine kurze Sitzung – nur einmal je Statusabfrage)."""
        if aktiv is None:
            aktiv, _ = self.ist_aktiv()
        if not aktiv:
            return False
        jetzt = jetzt or datetime.now()
        basis = self.letzter_start or self.registriert_am
        toleranz = timedelta(seconds=2 * self.intervall_effektiv_s
                             + self.start_verzoegerung_s + JITTER_MAX_S)
        return jetzt - basis > toleranz

    def als_dict(self) -> dict:
        aktiv, grund = self.ist_aktiv()
        ueberfaellig = self.ueberfaellig(aktiv=aktiv)
        return {
            "name": self.name, "beschreibung": self.beschreibung,
            "intervall_s": self.intervall_effektiv_s, "taeglich_um": self.taeglich_um,
            "letzter_start": self.letzter_start, "letzte_dauer_ms": self.letzte_dauer_ms,
            "letzter_fehler": self.letzter_fehler, "letztes_ergebnis": self.letztes_ergebnis,
            "laeufe": self.laeufe, "fehler": self.fehler,
            "naechster_start": self.naechster_start,
            "zustand": self.zustand if aktiv else f"inaktiv ({grund})",
            "aktiv": aktiv, "laeuft": self.sperre.locked(),
            "ok": not self.letzter_fehler and not ueberfaellig,
            "ueberfaellig": ueberfaellig,
        }


_LAEUFE: dict[str, Lauf] = {}
_registrier_sperre = threading.Lock()
_stop = threading.Event()
_gestartet = False


def registrieren(name: str, intervall_s: int, funktion: Callable[[], object], *,
                 beschreibung: str = "", start_verzoegerung_s: int = 0,
                 taeglich_um: Optional[str] = None,
                 aktiv: Optional[Callable[[], object]] = None) -> Lauf:
    """Lauf anmelden (idempotent: gleicher Name → Funktion/Parameter werden
    aktualisiert, Zähler bleiben). Gestartet wird erst mit starten_alle()."""
    with _registrier_sperre:
        lauf = _LAEUFE.get(name)
        if lauf is None:
            lauf = Lauf(name=name, intervall_s=int(intervall_s), funktion=funktion)
            _LAEUFE[name] = lauf
        lauf.intervall_s = int(intervall_s)
        lauf.funktion = funktion
        lauf.beschreibung = beschreibung or lauf.beschreibung
        lauf.start_verzoegerung_s = int(start_verzoegerung_s)
        lauf.taeglich_um = taeglich_um
        lauf.aktiv = aktiv
        if _gestartet and (lauf.thread is None or not lauf.thread.is_alive()):
            _thread_starten(lauf)
        return lauf


def holen(name: str) -> Optional[Lauf]:
    return _LAEUFE.get(name)


def alle() -> list[Lauf]:
    return [_LAEUFE[n] for n in sorted(_LAEUFE)]


def anzahl() -> int:
    return len(_LAEUFE)


def status_liste() -> list[dict]:
    return [lauf.als_dict() for lauf in alle()]


def _naechste_tageszeit(uhrzeit: str, jetzt: Optional[datetime] = None) -> datetime:
    jetzt = jetzt or datetime.now()
    stunde, minute = (int(t) for t in uhrzeit.split(":")[:2])
    ziel = jetzt.replace(hour=stunde, minute=minute, second=0, microsecond=0)
    if ziel <= jetzt:
        ziel += timedelta(days=1)
    return ziel


def ausfuehren(name: str, ausloeser: str = "scheduler") -> dict:
    """Einen Lauf jetzt ausführen (Single-Flight). Liefert
    {"ok": bool, "uebersprungen": bool, "grund": str, "dauer_ms": int,
    "ergebnis": str, "fehler": str}. Fehler werden protokolliert
    (data/fehler.log) und am Lauf vermerkt, nie geworfen."""
    lauf = _LAEUFE.get(name)
    if lauf is None:
        return {"ok": False, "uebersprungen": True, "grund": "unbekannter Lauf",
                "dauer_ms": 0, "ergebnis": "", "fehler": ""}
    aktiv, grund = lauf.ist_aktiv()
    if not aktiv and ausloeser == "scheduler":
        lauf.zustand = f"inaktiv ({grund})"
        _status_schreiben(lauf)
        return {"ok": True, "uebersprungen": True, "grund": grund, "dauer_ms": 0,
                "ergebnis": "", "fehler": ""}
    if not lauf.sperre.acquire(blocking=False):
        return {"ok": True, "uebersprungen": True, "grund": "läuft bereits",
                "dauer_ms": 0, "ergebnis": "", "fehler": ""}
    try:
        lauf.letzter_start = datetime.now()
        lauf.zustand = "läuft"
        start = time.perf_counter()
        fehler_text = ""
        ergebnis_text = ""
        try:
            ergebnis = lauf.funktion()
            ergebnis_text = _ergebnis_text(ergebnis)
        except Exception as problem:
            fehler_text = f"{type(problem).__name__}: {problem}"[:FEHLER_MAX]
            try:
                logger.error("Scheduler %s (%s): %s\n%s", name, ausloeser, fehler_text,
                             traceback.format_exc()[-4000:])
            except Exception:
                pass
        dauer_ms = int((time.perf_counter() - start) * 1000)
        lauf.letztes_ende = datetime.now()
        lauf.letzte_dauer_ms = dauer_ms
        lauf.letzter_fehler = fehler_text
        lauf.letztes_ergebnis = ergebnis_text
        lauf.laeufe += 1
        if fehler_text:
            lauf.fehler += 1
        lauf.zustand = "fehler" if fehler_text else "ok"
        _status_schreiben(lauf)
        return {"ok": not fehler_text, "uebersprungen": False, "grund": "",
                "dauer_ms": dauer_ms, "ergebnis": ergebnis_text, "fehler": fehler_text}
    finally:
        lauf.sperre.release()


def jetzt_ausfuehren(name: str) -> dict:
    """Knopf „jetzt ausführen“ (Parametrierung → Betrieb): läuft synchron im
    aufrufenden Thread, auch wenn der Lauf gerade „inaktiv“ wäre."""
    return ausfuehren(name, ausloeser="manuell")


def im_hintergrund_ausfuehren(name: str) -> dict:
    """Manueller Start in einem eigenen Thread (Befund B10: lange Läufe wie
    monday-Vollabgleich oder Backup belegen sonst minutenlang einen
    Worker-Thread der Anfrage). Liefert sofort {"gestartet": bool, "grund": str};
    Ergebnis und Dauer stehen danach am Lauf (Betriebs-Seite, scheduler_status)."""
    lauf = _LAEUFE.get(name)
    if lauf is None:
        return {"gestartet": False, "grund": "unbekannter Lauf"}
    if lauf.sperre.locked():
        return {"gestartet": False, "grund": "läuft bereits"}
    threading.Thread(target=ausfuehren, args=(name, "manuell"), daemon=True,
                     name=f"manuell-{name}").start()
    return {"gestartet": True, "grund": ""}


def _ergebnis_text(ergebnis) -> str:
    if ergebnis is None:
        return ""
    if isinstance(ergebnis, dict):
        teile = []
        for k, v in list(ergebnis.items())[:8]:
            if isinstance(v, (list, tuple, set)):
                v = f"{len(v)}"
            teile.append(f"{k}={v}")
        return ", ".join(teile)[:300]
    return str(ergebnis)[:300]


def _status_schreiben(lauf: Lauf) -> None:
    """Tabelle scheduler_status fortschreiben – kurze Sitzung, wirft nie."""
    try:
        from app.db import kurz
        from app.models import SchedulerStatus
        with kurz() as s:
            zeile = s.query(SchedulerStatus).filter_by(name=lauf.name).first()
            if zeile is None:
                zeile = SchedulerStatus(name=lauf.name)
                s.add(zeile)
            zeile.beschreibung = (lauf.beschreibung or "")[:200]
            zeile.intervall_s = lauf.intervall_effektiv_s
            zeile.letzter_start = lauf.letzter_start
            zeile.letzte_dauer_ms = lauf.letzte_dauer_ms
            zeile.letzter_fehler = (lauf.letzter_fehler or "")[:500]
            zeile.letztes_ergebnis = (lauf.letztes_ergebnis or "")[:300]
            zeile.laeufe = lauf.laeufe
            zeile.fehler = lauf.fehler
            zeile.naechster_start = lauf.naechster_start
            zeile.zustand = (lauf.zustand or "")[:100]
    except Exception:
        pass


def _warten(sekunden: float) -> None:
    """Schlafen in kleinen Schritten, damit stoppen() greift."""
    ende = time.monotonic() + max(0.0, sekunden)
    while not _stop.is_set():
        rest = ende - time.monotonic()
        if rest <= 0:
            return
        time.sleep(min(SCHRITT_S, rest))


def _schleife(lauf: Lauf) -> None:
    versatz = lauf.start_verzoegerung_s + random.uniform(0, JITTER_MAX_S)
    if lauf.taeglich_um:
        lauf.naechster_start = _naechste_tageszeit(lauf.taeglich_um)
    else:
        lauf.naechster_start = datetime.now() + timedelta(seconds=versatz)
        _warten(versatz)
    while not _stop.is_set():
        if lauf.taeglich_um:
            ziel = lauf.naechster_start or _naechste_tageszeit(lauf.taeglich_um)
            _warten((ziel - datetime.now()).total_seconds())
            if _stop.is_set():
                break
            ausfuehren(lauf.name)
            lauf.naechster_start = _naechste_tageszeit(lauf.taeglich_um)
            _status_schreiben(lauf)
        else:
            ausfuehren(lauf.name)
            lauf.naechster_start = datetime.now() + timedelta(seconds=lauf.intervall_s)
            _warten(lauf.intervall_s)


def _thread_starten(lauf: Lauf) -> None:
    lauf.thread = threading.Thread(target=_schleife, args=(lauf,), daemon=True,
                                   name=f"scheduler-{lauf.name}")
    lauf.thread.start()


def starten_alle() -> int:
    """Alle registrierten Läufe starten (je Lauf ein Daemon-Thread; idempotent).
    Liefert die Anzahl der gestarteten Threads."""
    global _gestartet
    _stop.clear()
    _gestartet = True
    gestartet = 0
    for lauf in alle():
        if lauf.thread is None or not lauf.thread.is_alive():
            _thread_starten(lauf)
            gestartet += 1
    return gestartet


def stoppen(timeout_s: float = 2.0) -> None:
    """Beim Herunterfahren: Threads beenden (laufende Funktionen laufen zu Ende)."""
    global _gestartet
    _stop.set()
    for lauf in alle():
        if lauf.thread is not None and lauf.thread.is_alive():
            lauf.thread.join(timeout=timeout_s)
        lauf.thread = None
    _gestartet = False


def zuruecksetzen_fuer_tests() -> None:
    """Nur für Tests: alle Registrierungen und Threads verwerfen."""
    stoppen(timeout_s=0.5)
    _LAEUFE.clear()
    _stop.clear()
