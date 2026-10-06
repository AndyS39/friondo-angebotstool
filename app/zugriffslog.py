# v27 (PLAN_V17 Phase 127): Zugriffsprotokoll mit Dauer – Messbasis für den
# Lasttest und die Zugriffsstatistik unter Parametrierung → Betrieb.
# Die RollenMiddleware schreibt je Anfrage eine Zeile nach data\log\zugriff.log
# (RotatingFileHandler 10 × 10 MB): Zeit | Benutzer-ID | Rolle | Methode |
# Pfad ohne Query | Status | Dauer ms | Pool-Checkouts zu Beginn.
# Keine Formdaten, keine Namen. /static und /health werden nicht protokolliert.

import logging
import logging.handlers
import re
import threading
import time
from datetime import datetime, timedelta

from app import config

LOG_DATEI = "zugriff.log"
MAX_BYTES = 10_000_000
ANZAHL_DATEIEN = 10
TRENNER = " | "
LANGSAM_MS = 2000               # Anteil der Anfragen über 2 s
CACHE_SEKUNDEN = 60             # Auswertung wird 60 s zwischengespeichert
AUSWERTUNG_MAX_BYTES = 40_000_000   # höchstens die jüngsten 40 MB einlesen

_logger = logging.getLogger("angebotstool.zugriff")
_logger.propagate = False
_sperre = threading.Lock()
_eingerichtet = False
_cache = {"stand": 0.0, "stunden": None, "wert": None}
_ID_SEGMENT = re.compile(r"/\d+(?=/|$)")
_TOKEN_SEGMENT = re.compile(r"/[0-9a-f]{20,}(?=/|$)")


def log_pfad():
    return config.LOG_ORDNER / LOG_DATEI


def einrichten() -> logging.Logger:
    """Rotierendes Datei-Log einmalig einrichten (idempotent, wirft nie)."""
    global _eingerichtet
    with _sperre:
        if _eingerichtet:
            return _logger
        try:
            config.LOG_ORDNER.mkdir(parents=True, exist_ok=True)
            pfad = log_pfad()
            if not any(getattr(h, "baseFilename", "") == str(pfad) for h in _logger.handlers):
                handler = logging.handlers.RotatingFileHandler(
                    pfad, maxBytes=MAX_BYTES, backupCount=ANZAHL_DATEIEN, encoding="utf-8")
                handler.setFormatter(logging.Formatter("%(message)s"))
                _logger.addHandler(handler)
            _logger.setLevel(logging.INFO)
            _eingerichtet = True
        except Exception:
            pass
    return _logger


def eintragen(benutzer_id, rolle: str, methode: str, pfad: str, status: int,
              dauer_ms: int, pool_checkouts: int) -> None:
    """Eine Zeile schreiben (wirft nie)."""
    try:
        if not _eingerichtet:
            einrichten()
        zeile = TRENNER.join([
            datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3],
            str(benutzer_id if benutzer_id is not None else "-"),
            (rolle or "-")[:20],
            (methode or "-")[:8],
            (pfad or "/")[:300].replace("|", "_"),
            str(int(status)),
            str(int(dauer_ms)),
            str(int(pool_checkouts)),
        ])
        _logger.info(zeile)
    except Exception:
        pass


def route_normalisieren(pfad: str) -> str:
    """/angebote/123/pdf → /angebote/{id}/pdf (Zahlen und lange Hex-Tokens)."""
    pfad = _ID_SEGMENT.sub("/{id}", pfad or "/")
    return _TOKEN_SEGMENT.sub("/{token}", pfad)


def _perzentil(werte: list[int], anteil: float) -> int:
    if not werte:
        return 0
    werte = sorted(werte)
    index = min(len(werte) - 1, max(0, int(round(anteil * (len(werte) - 1)))))
    return werte[index]


def _zeilen_lesen(seit: datetime):
    """Zeilen aller Log-Dateien (älteste zuerst), höchstens die jüngsten
    AUSWERTUNG_MAX_BYTES; liefert geparste Tupel ab `seit`."""
    pfad = log_pfad()
    dateien = [pfad.parent / f"{LOG_DATEI}.{n}" for n in range(ANZAHL_DATEIEN, 0, -1)]
    dateien.append(pfad)
    budget = AUSWERTUNG_MAX_BYTES
    gewaehlt = []
    for datei in reversed(dateien):
        if not datei.exists():
            continue
        groesse = datei.stat().st_size
        if budget - groesse < 0 and gewaehlt:
            break
        gewaehlt.append(datei)
        budget -= groesse
    seit_text = seit.strftime("%Y-%m-%dT%H:%M:%S")
    for datei in reversed(gewaehlt):
        try:
            with datei.open("r", encoding="utf-8", errors="replace") as f:
                for zeile in f:
                    if zeile[:19] < seit_text:
                        continue
                    teile = zeile.rstrip("\n").split(TRENNER)
                    if len(teile) != 8:
                        continue
                    yield teile
        except OSError:
            continue


def auswerten(stunden: int = 24, top: int = 20, erzwingen: bool = False) -> dict:
    """Zugriffsstatistik der letzten `stunden`: Anfragen gesamt und je Minute,
    p50/p95 je Route (Top 20 nach Anzahl), Anteil > 2 s, langsamste 20
    Anfragen, Pool-Spitze, 5xx-Zähler. Ergebnis 60 s zwischengespeichert."""
    jetzt = time.monotonic()
    if (not erzwingen and _cache["wert"] is not None and _cache["stunden"] == stunden
            and jetzt - _cache["stand"] < CACHE_SEKUNDEN):
        return _cache["wert"]
    seit = datetime.now() - timedelta(hours=stunden)
    je_route: dict[str, list[int]] = {}
    fehler_je_route: dict[str, int] = {}
    langsamste: list[tuple] = []
    gesamt = 0
    ueber_2s = 0
    fehler_5xx = 0
    pool_spitze = 0
    pool_spitze_zeit = ""
    erste_zeit = None
    letzte_zeit = None
    for zeit, benutzer_id, rolle, methode, pfad, status, dauer, pool in _zeilen_lesen(seit):
        try:
            dauer_ms = int(dauer)
            status_nr = int(status)
            pool_nr = int(pool)
        except ValueError:
            continue
        gesamt += 1
        erste_zeit = erste_zeit or zeit
        letzte_zeit = zeit
        route = f"{methode} {route_normalisieren(pfad)}"
        je_route.setdefault(route, []).append(dauer_ms)
        if dauer_ms > LANGSAM_MS:
            ueber_2s += 1
        if status_nr >= 500:
            fehler_5xx += 1
            fehler_je_route[route] = fehler_je_route.get(route, 0) + 1
        if pool_nr > pool_spitze:
            pool_spitze, pool_spitze_zeit = pool_nr, zeit
        if len(langsamste) < top or dauer_ms > langsamste[-1][0]:
            langsamste.append((dauer_ms, zeit, route, status_nr, benutzer_id, rolle))
            langsamste.sort(key=lambda t: -t[0])
            del langsamste[top:]
    routen = []
    for route, werte in sorted(je_route.items(), key=lambda kv: -len(kv[1]))[:top]:
        routen.append({
            "route": route, "anzahl": len(werte),
            "p50": _perzentil(werte, 0.50), "p95": _perzentil(werte, 0.95),
            "max": max(werte), "fehler": fehler_je_route.get(route, 0),
        })
    minuten = max(1.0, stunden * 60.0)
    if erste_zeit and letzte_zeit and letzte_zeit > erste_zeit:
        try:
            spanne = (datetime.strptime(letzte_zeit[:19], "%Y-%m-%dT%H:%M:%S")
                      - datetime.strptime(erste_zeit[:19], "%Y-%m-%dT%H:%M:%S"))
            minuten = max(1.0, spanne.total_seconds() / 60.0)
        except ValueError:
            pass
    ergebnis = {
        "stunden": stunden, "gesamt": gesamt,
        "pro_minute": round(gesamt / minuten, 2) if gesamt else 0.0,
        "anteil_ueber_2s": round(100.0 * ueber_2s / gesamt, 2) if gesamt else 0.0,
        "ueber_2s": ueber_2s, "fehler_5xx": fehler_5xx,
        "routen": routen,
        "langsamste": [{"dauer_ms": d, "zeit": z, "route": r, "status": s,
                        "benutzer_id": b, "rolle": ro}
                       for d, z, r, s, b, ro in langsamste],
        "pool_spitze": pool_spitze, "pool_spitze_zeit": pool_spitze_zeit,
        "erste_zeit": erste_zeit, "letzte_zeit": letzte_zeit,
        "log_pfad": str(log_pfad()),
    }
    _cache.update(stand=jetzt, stunden=stunden, wert=ergebnis)
    return ergebnis
