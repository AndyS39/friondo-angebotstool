# v22 (PLAN_V15 Phase 103, „Fehlerprotokoll zuerst“): jede unbehandelte
# Ausnahme bekommt eine Fehler-Nr., wird zuerst mit Traceback in das
# rotierende Datei-Log data/fehler.log geschrieben und danach in die Tabelle
# fehlerprotokoll (Parametrierung → Fehlerprotokoll) eingetragen.
# Das Datei-Log ist die Primärquelle: die bestätigte Hauptursache der
# sporadischen 500er ist „database is locked“ – dann kann auch der
# Protokoll-INSERT scheitern. Keine Funktion hier wirft selbst.

import json
import logging
import logging.handlers
import re
import secrets
import threading
import time
import traceback as traceback_modul
from datetime import datetime
from urllib.parse import parse_qs

from app import config

logger = logging.getLogger("angebotstool")

LOG_DATEI = "fehler.log"
TRACEBACK_MAX = 20_000
FORMDATEN_MAX_BYTES = 64 * 1024
# Feldnamen, deren Werte im Protokoll maskiert werden (Teilstring, ohne
# Groß-/Kleinschreibung)
MASKIERTE_FELDER = ("pin", "passwort", "token")
_ANGEBOT_PFAD = re.compile(r"^/angebote/(\d+)(?:/|$)")
_sperre = threading.Lock()


def log_pfad():
    """Pfad des Datei-Logs (data/fehler.log)."""
    return config.DATA_ORDNER / LOG_DATEI


def logging_einrichten() -> logging.Logger:
    """Rotierendes Datei-Log (5 × 1 MB, UTF-8) einmalig einrichten – für den
    eigenen Logger „angebotstool“ und für „uvicorn.error“, damit auch die
    Tracebacks, die uvicorn selbst druckt, auffindbar sind (der Dienst läuft
    als geplante Aufgabe ohne Konsole). Idempotent."""
    with _sperre:
        try:
            pfad = log_pfad()
            config.DATA_ORDNER.mkdir(parents=True, exist_ok=True)
            handler = None
            for ziel in (logger, logging.getLogger("uvicorn.error")):
                if any(getattr(h, "baseFilename", "") == str(pfad)
                       for h in ziel.handlers):
                    continue
                if handler is None:
                    handler = logging.handlers.RotatingFileHandler(
                        pfad, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
                    handler.setFormatter(logging.Formatter(
                        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
                    handler.setLevel(logging.INFO)
                ziel.addHandler(handler)
            logger.setLevel(logging.INFO)
            # nicht bis zum Root-Logger durchreichen: uvicorn druckt die
            # Ausnahme ohnehin selbst auf die Konsole
            logger.propagate = False
        except Exception:
            pass
    return logger


def fehler_nr_erzeugen() -> str:
    """Fehler-Nr. im Format F-JJJJMMTT-HHMMSS-4hex, z. B. F-20260930-142501-a3f9."""
    return f"F-{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


def ist_datenbank_gesperrt(exc: BaseException) -> bool:
    """True bei sqlalchemy OperationalError „database is locked“ – dafür
    bekommt der Benutzer einen eigenen Hinweistext (erneut versuchen)."""
    try:
        from sqlalchemy.exc import OperationalError
        return isinstance(exc, OperationalError) and "locked" in str(exc).lower()
    except Exception:
        return False


def angebot_id_aus_pfad(pfad: str):
    """Angebots-ID aus „/angebote/<id>/…“ (sonst None)."""
    treffer = _ANGEBOT_PFAD.match(pfad or "")
    return int(treffer.group(1)) if treffer else None


def formdaten_parsen(body: bytes) -> dict:
    """application/x-www-form-urlencoded → dict (Mehrfachwerte als Liste);
    Felder mit „pin“/„passwort“/„token“ im Namen werden maskiert."""
    try:
        roh = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)
    except Exception:
        return {}
    ergebnis = {}
    for name, werte in roh.items():
        if any(m in name.lower() for m in MASKIERTE_FELDER):
            werte = ["***" for _ in werte]
        ergebnis[name] = werte[0] if len(werte) == 1 else werte
    return ergebnis


async def formdaten_puffern(request) -> dict | None:
    """Für die RollenMiddleware: Formdaten eines POST/PUT vor dem Endpunkt
    puffern, damit sie bei einer späteren Ausnahme noch vorliegen (nach
    ``await request.form()`` im Endpunkt ist der Body verbraucht; Starlettes
    _CachedRequest reicht den hier gelesenen Body an den Endpunkt weiter).
    Nur application/x-www-form-urlencoded bis 64 KB wird gelesen; Multipart
    (Uploads) wird nur mit seiner Größe vermerkt. Ein ClientDisconnect beim
    Lesen wird durchgereicht (der Handler antwortet dann ohne Protokoll)."""
    if request.method not in ("POST", "PUT", "PATCH"):
        return None
    inhaltstyp = (request.headers.get("content-type") or "").lower()
    laenge_text = request.headers.get("content-length") or ""
    laenge = int(laenge_text) if laenge_text.isdigit() else None
    if inhaltstyp.startswith("multipart/form-data"):
        return {"_multipart_bytes": laenge}
    if not inhaltstyp.startswith("application/x-www-form-urlencoded"):
        return None
    if laenge is None or laenge > FORMDATEN_MAX_BYTES:
        return {"_bytes": laenge, "_hinweis": "nicht gepuffert (Größe)"}
    body = await request.body()
    return formdaten_parsen(body)


def _anfrage_daten(request) -> dict:
    """Kontext der Anfrage einsammeln – jeder Teil einzeln abgesichert."""
    daten = dict(benutzer_id=None, benutzer_name="", rolle="", methode="",
                 pfad="", query="", formdaten="", angebot_id=None)
    try:
        daten["methode"] = (request.method or "")[:10]
        daten["pfad"] = request.url.path[:300]
        daten["query"] = (request.url.query or "")[:500]
        daten["angebot_id"] = angebot_id_aus_pfad(request.url.path)
    except Exception:
        pass
    try:
        benutzer = getattr(request.state, "benutzer", None)
        if benutzer is not None:
            daten["benutzer_id"] = getattr(benutzer, "id", None)
            daten["benutzer_name"] = (getattr(benutzer, "name", "") or "")[:200]
            daten["rolle"] = (getattr(benutzer, "rolle", "") or "")[:30]
    except Exception:
        pass
    try:
        formdaten = getattr(request.state, "formdaten", None)
        if formdaten:
            daten["formdaten"] = json.dumps(formdaten, ensure_ascii=False)[:FORMDATEN_MAX_BYTES]
    except Exception:
        pass
    return daten


def _traceback_text(exc: BaseException) -> str:
    try:
        text = "".join(traceback_modul.format_exception(type(exc), exc, exc.__traceback__))
    except Exception:
        text = f"{type(exc).__name__}: {exc}"
    if len(text) > TRACEBACK_MAX:
        text = "… (gekürzt) …\n" + text[-TRACEBACK_MAX:]
    return text


def _in_tabelle_schreiben(nr: str, daten: dict, exc: BaseException, tb_text: str) -> bool:
    """Tabelleneintrag in eigener Session; bei OperationalError (DB gesperrt)
    einmal 0,5 s warten und erneut versuchen. Liefert True bei Erfolg."""
    from sqlalchemy.exc import OperationalError

    from app.db import SessionLocal
    from app.models import Fehlerprotokoll

    for versuch in (1, 2):
        sitzung = SessionLocal()
        try:
            sitzung.add(Fehlerprotokoll(
                fehler_nr=nr, zeit=datetime.now(),
                benutzer_id=daten["benutzer_id"], benutzer_name=daten["benutzer_name"],
                rolle=daten["rolle"], methode=daten["methode"], pfad=daten["pfad"],
                query=daten["query"], formdaten=daten["formdaten"],
                fehlertyp=type(exc).__name__[:100], meldung=str(exc)[:500],
                traceback=tb_text, angebot_id=daten["angebot_id"], erledigt=False))
            sitzung.commit()
            return True
        except OperationalError as db_fehler:
            sitzung.rollback()
            if versuch == 1:
                time.sleep(0.5)
                continue
            logger.warning("Fehler-Nr. %s: Tabelleneintrag nicht möglich (%s) – "
                           "nur Datei-Log", nr, str(db_fehler).splitlines()[0][:200])
        except Exception as sonst:
            sitzung.rollback()
            logger.warning("Fehler-Nr. %s: Tabelleneintrag nicht möglich (%s: %s) – "
                           "nur Datei-Log", nr, type(sonst).__name__, str(sonst)[:200])
            return False
        finally:
            sitzung.close()
    return False


def eintragen(request, exc: BaseException) -> str:
    """Ausnahme protokollieren und die Fehler-Nr. liefern. Reihenfolge:
    Fehler-Nr. erzeugen → Datei-Log (mit Traceback) → Tabelleneintrag.
    Wirft niemals selbst."""
    try:
        nr = fehler_nr_erzeugen()
    except Exception:
        nr = "F-unbekannt"
    daten = _anfrage_daten(request)
    tb_text = _traceback_text(exc)
    try:
        logging_einrichten()
        logger.error(
            "Fehler-Nr. %s | %s %s%s | Benutzer %s (%s, ID %s) | Angebot %s | %s: %s\n"
            "Formdaten: %s\n%s",
            nr, daten["methode"], daten["pfad"],
            ("?" + daten["query"]) if daten["query"] else "",
            daten["benutzer_name"] or "-", daten["rolle"] or "-", daten["benutzer_id"],
            daten["angebot_id"], type(exc).__name__, str(exc)[:500],
            daten["formdaten"] or "-", tb_text)
    except Exception:
        pass
    try:
        _in_tabelle_schreiben(nr, daten, exc, tb_text)
    except Exception:
        pass
    return nr
