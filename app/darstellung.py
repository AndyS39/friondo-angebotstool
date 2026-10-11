# v30 (PLAN_V18 Phase 145): Darstellung Hell/Dunkel je Benutzer.
# Werte: geraet (Standard – prefers-color-scheme entscheidet), hell, dunkel.
# Gespeichert in benutzer_einstellungen (Key "darstellung", JSON-Text wie die
# übrigen Benutzereinstellungen) und als Cookie "darstellung" (1 Jahr,
# samesite=lax), damit die Middleware den Modus VOR dem Rendern in das
# <html data-theme>-Tag schreibt (kein Aufblitzen des falschen Modus).
# Die Login-Seite kennt keinen Benutzer und liest nur das Cookie.
import json

from sqlalchemy.orm import Session

from app.models import BenutzerEinstellung

KEY = "darstellung"
COOKIE = "darstellung"
COOKIE_MAX_AGE = 365 * 24 * 3600
WERTE = ("geraet", "hell", "dunkel")
STANDARD = "geraet"
NAMEN = {"geraet": "Gerät", "hell": "Hell", "dunkel": "Dunkel"}
# <meta name="theme-color"> je Modus: Hell = Kopfzeile der Friondo-CI,
# Dunkel = Seitenfläche der Vorlage (docs/design-v30/vorlage)
THEME_COLOR = {"hell": "#1b2a5e", "dunkel": "#070d1a"}


def normalisieren(wert) -> str:
    """Unbekannte oder leere Werte → Standard (Gerät)."""
    wert = str(wert or "").strip().lower()
    return wert if wert in WERTE else STANDARD


def lesen(session: Session, benutzer_id: int):
    """Gespeicherte Wahl des Benutzers oder None (nie gewählt)."""
    zeile = (session.query(BenutzerEinstellung)
             .filter(BenutzerEinstellung.benutzer_id == benutzer_id,
                     BenutzerEinstellung.key == KEY).first())
    if zeile is None or not zeile.wert:
        return None
    try:
        wert = json.loads(zeile.wert)
    except ValueError:
        wert = zeile.wert
    wert = str(wert or "").strip().lower()
    return wert if wert in WERTE else None


def speichern(session: Session, benutzer_id: int, wert) -> str:
    """Wahl speichern (anlegen oder überschreiben); liefert den normalisierten Wert.
    Committet nicht selbst."""
    wert = normalisieren(wert)
    zeile = (session.query(BenutzerEinstellung)
             .filter(BenutzerEinstellung.benutzer_id == benutzer_id,
                     BenutzerEinstellung.key == KEY).first())
    if zeile is None:
        zeile = BenutzerEinstellung(benutzer_id=benutzer_id, key=KEY,
                                    erstellt_von=benutzer_id)
        session.add(zeile)
    zeile.wert = json.dumps(wert)
    session.flush()
    return wert


def aus_cookie(request) -> str:
    """Cookie-Wert (vor der Anmeldung die einzige Quelle)."""
    try:
        return normalisieren(request.cookies.get(COOKIE, ""))
    except Exception:   # noqa: BLE001 – kein Request-Objekt (Tests ohne Middleware)
        return STANDARD


def cookie_setzen(antwort, wert) -> None:
    antwort.set_cookie(COOKIE, normalisieren(wert), max_age=COOKIE_MAX_AGE,
                       samesite="lax", path="/")


def html_theme(wert) -> str:
    """Wert für <html data-theme>: leer bei „Gerät“ (dann entscheidet die
    Media-Query in style.css), sonst hell | dunkel."""
    wert = normalisieren(wert)
    return "" if wert == STANDARD else wert
