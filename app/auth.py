# Leichtgewichtige Anmeldung (Phase 13): Benutzerliste + PIN, signiertes
# Session-Cookie, Rollen-Durchsetzung per Middleware.
# Außendienst sieht ausschließlich die mobile Erfassung – nie Preise, EK,
# Deckungsbeitrag oder den Angebotsbereich.
#
# v27 (PLAN_V17 Phase 130, Login-Härtung für 50 Nutzer): PBKDF2-PIN-Hash in der
# neuen Spalte pin_hash_v2 (pin_hash bleibt für v26 stehen und wird bei jeder
# PIN-Änderung mitgeschrieben – Rollback-Sicherheit), PIN-Regeln (Mindestlänge,
# Sperrliste, Muster), Fehlversuchssperre je Benutzer und je IP, Login-Protokoll,
# signiertes Cookie mit Ablauf und Sitzungszähler („Alle Sitzungen beenden“),
# Pflicht-PIN-Wechsel beim ersten Login. Phase 127/128: die Middleware läuft mit
# ihrer Datenbankarbeit im Threadpool, schließt die Sitzung VOR call_next
# (Hotfix 06.10.2026) und schreibt je Anfrage eine Zeile ins Zugriffsprotokoll.

import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timedelta

from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import ClientDisconnect

from app import config
from app.db import SessionLocal
from app.models import Benutzer

COOKIE_NAME = "angebotstool_sitzung"
COOKIE_VERSION = "v2"

# Pfade ohne Anmeldung; Außendienst-Pfade; Admin-exklusive Pfade
# /signatur/extern ist die (standardmäßig deaktivierte) Kunden-Fernsignatur
OFFENE_PFADE = ("/login", "/logout", "/static", "/signatur/extern",
                # v12 (Lead-Management, Phase 75): REST-Eingang mit eigenem
                # API-Key-Schutz statt Session-Cookie
                "/api/leads",
                # v27 (Phase 129): Betriebs-Status ohne Anmeldung (nur Lesen)
                "/health")
# v27 (Phase 130): Pflicht-PIN-Wechsel – für jede Rolle erreichbar
PIN_WECHSEL_PFAD = "/pin-wechsel"
AUSSENDIENST_PFADE = ("/erfassung", "/leads", "/signatur", "/statistik",
                      "/meine-angebote", "/vorgaenge", "/benachrichtigungen",
                      # v12 (Phase 81): AD-Sicht des Lead-Moduls (Meine
                      # Termine, No-Show/Verschieben) – Routen prüfen selbst
                      "/lead-management",
                      "/login", "/logout", "/static", PIN_WECHSEL_PFAD)
ADMIN_PFADE = ("/benutzer",)
BUERO_ROLLEN = ("admin", "innendienst")
# v11 (Phase 70): Hauptrolle projektierung – Projektierung voll, Angebote/
# Erfassungen/Kunden nur lesend, Parametrierung nur die drei Projektierungs-
# Stammseiten. Hauptrolle montage – ausschließlich der mobile /montage-Bereich.
PROJEKTIERUNG_PFADE = ("/projektierung", "/montage", "/benachrichtigungen",
                       "/kunden", "/erfassungen", "/angebote",
                       "/parametrierung/projektierung-logik",
                       "/parametrierung/teams", "/parametrierung/subunternehmer",
                       "/parametrierung/stuecklisten",       # V4 Phase 93.2
                       "/login", "/logout", "/static", PIN_WECHSEL_PFAD)
PROJEKTIERUNG_SCHREIBEN = ("/projektierung", "/montage", "/benachrichtigungen",
                           "/parametrierung", "/login", "/logout", PIN_WECHSEL_PFAD)
MONTAGE_PFADE = ("/montage", "/benachrichtigungen", "/login", "/logout", "/static",
                 PIN_WECHSEL_PFAD)
# v15 (Phase 82): Montage erreicht die Vorgangs-Galerie (ansehen + Upload –
# die Datei-/Upload-Routen prüfen selbst über galerie.darf_hochladen, dass
# der Vorgang zu einem eigenen Team-Einsatz gehört); löschen/verschieben
# bleiben gesperrt
_MONTAGE_GALERIE = re.compile(r"^/vorgaenge/(galerie/datei/\d+|\d+/galerie/upload)$")
# v13 (Phase 80): Lieferschein (ohne Preise) ist ebenfalls lesend erlaubt
_ANGEBOTE_LESEPFAD = re.compile(r"^/angebote(/\d+/(pdf|lieferschein\.pdf))?$")
# v12 (Phase 81): Hauptrolle leadmanagement – Lead-Modul voll, Kunden
# lesend/schreibend, Vorgangsakte, Angebote nur Liste+PDF, Erfassungen lesend;
# Parametrierung nur Quellen & Kampagnen + Steuerdatei (Plan 81)
LEADMANAGEMENT_PFADE = ("/lead-management", "/api/leads", "/benachrichtigungen",
                        "/kunden", "/vorgaenge", "/erfassungen", "/angebote",
                        "/parametrierung/lead-quellen",
                        "/parametrierung/lead-logik",
                        "/login", "/logout", "/static", PIN_WECHSEL_PFAD)
LEADMANAGEMENT_SCHREIBEN = ("/lead-management", "/api/leads",
                            "/benachrichtigungen", "/kunden", "/vorgaenge",
                            "/parametrierung", "/login", "/logout", PIN_WECHSEL_PFAD)

# --- v27 Login-Härtung: Konstanten und Texte (Plan-Wortlaut) --------------------
PBKDF2_RUNDEN = 200_000
PBKDF2_KENNUNG = "pbkdf2_sha256"
PIN_MINDESTLAENGE_NEU = 4          # Antwort Andreas 07.10.2026: mindestens 4 (Parameter pin_mindestlaenge)
PIN_MINDESTLAENGE_ALT = 4          # bestehende PINs bleiben gültig
PIN_SPERRLISTE_STANDARD = ("123456,111111,000000,654321,112233,121212,123123,"
                           "222222,333333,444444,555555,666666,777777,888888,"
                           "999999,123456789,1234,0000,1111")
MAX_FEHLVERSUCHE = 5
SPERRE_MINUTEN = 15
FEHLVERSUCH_FENSTER_MINUTEN = 15
IP_MAX_VERSUCHE = 30
IP_FENSTER_MINUTEN = 15
SITZUNG_STUNDEN_BUERO = 12         # [ANNAHME] Parameter sitzung_stunden_buero
SITZUNG_TAGE_MOBIL = 30            # [ANNAHME] Parameter sitzung_tage_mobil
MOBILE_ROLLEN = ("aussendienst", "montage")
LOGIN_PROTOKOLL_TAGE = 90
SPERRE_TEXT = ("Zu viele Fehlversuche – bitte in 15 Minuten erneut versuchen "
               "oder den Admin um eine neue PIN bitten.")
IP_SPERRE_TEXT = ("Zu viele Anmeldeversuche von diesem Gerät – bitte in "
                  "15 Minuten erneut versuchen.")
PIN_FALSCH_TEXT = "Benutzer oder PIN falsch."

_ip_versuche: dict[str, deque] = {}
_ip_sperre = threading.Lock()


def _geheimnis() -> bytes:
    """Signierschlüssel: aus .env (SESSION_SECRET) oder persistent aus data/."""
    aus_env = getattr(config, "SESSION_SECRET", "") or ""
    if aus_env:
        return aus_env.encode()
    pfad = config.DATA_ORDNER / ".session_secret"
    if not pfad.exists():
        config.DATA_ORDNER.mkdir(parents=True, exist_ok=True)
        pfad.write_text(secrets.token_hex(32), encoding="ascii")
    return pfad.read_text(encoding="ascii").strip().encode()


# --- PIN-Hash ---------------------------------------------------------------------

def pin_hash(pin: str) -> str:
    """Alter SHA-256-Hash (Spalte pin_hash) – bleibt für v26 lesbar."""
    return hashlib.sha256(("friondo:" + pin).encode()).hexdigest()


def pin_hash_v2(pin: str, salz_hex: str | None = None) -> str:
    """v27: PBKDF2-HMAC-SHA256, 200.000 Runden, 16-Byte-Salz je Benutzer;
    Format pbkdf2_sha256$<Runden>$<Salz hex>$<Hash hex>."""
    salz_hex = salz_hex or secrets.token_hex(16)
    ableitung = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salz_hex),
                                    PBKDF2_RUNDEN)
    return f"{PBKDF2_KENNUNG}${PBKDF2_RUNDEN}${salz_hex}${ableitung.hex()}"


def pin_pruefen(benutzer, pin: str) -> bool:
    """pin_hash_v2 gesetzt → PBKDF2, sonst SHA-256 wie bisher."""
    pin = pin or ""
    v2 = getattr(benutzer, "pin_hash_v2", None) or ""
    if v2:
        try:
            kennung, runden, salz_hex, erwartet = v2.split("$", 3)
            if kennung != PBKDF2_KENNUNG:
                return False
            ableitung = hashlib.pbkdf2_hmac("sha256", pin.encode(),
                                            bytes.fromhex(salz_hex), int(runden))
            return hmac.compare_digest(ableitung.hex(), erwartet)
        except (ValueError, TypeError):
            return False
    return bool(benutzer.pin_hash) and hmac.compare_digest(benutzer.pin_hash, pin_hash(pin))


def pin_setzen(benutzer, pin: str) -> None:
    """Neue PIN speichern – BEIDE Spalten (Rückweg auf v26, Phase 132)."""
    benutzer.pin_hash_v2 = pin_hash_v2(pin)
    benutzer.pin_hash = pin_hash(pin)
    benutzer.fehlversuche = 0
    benutzer.gesperrt_bis = None


def _einstellung(session, name: str, standard: str) -> str:
    if session is None:
        return standard
    try:
        from app.models import einstellung_holen
        return einstellung_holen(session, name, standard)
    except Exception:
        return standard


def pin_mindestlaenge(session=None) -> int:
    try:
        return max(PIN_MINDESTLAENGE_ALT, int(_einstellung(session, "pin_mindestlaenge",
                                                        str(PIN_MINDESTLAENGE_NEU))))
    except ValueError:
        return PIN_MINDESTLAENGE_NEU


def pin_sperrliste(session=None) -> set[str]:
    text = _einstellung(session, "pin_sperrliste", PIN_SPERRLISTE_STANDARD)
    return {t.strip() for t in text.replace(";", ",").split(",") if t.strip()}


def pin_regel_pruefen(pin: str, session=None) -> str | None:
    """Regeln für NEUE PINs (Phase 130): nur Ziffern, Mindestlänge (Standard 6),
    nicht in der Sperrliste, keine Wiederholung einer Ziffer, keine auf-/
    absteigende Folge, kein Geburtsjahr-Muster (19xx/20xx). Liefert den
    Fehlertext oder None."""
    pin = (pin or "").strip()
    mindest = pin_mindestlaenge(session)
    if not pin.isdigit():
        return "Die PIN darf nur Ziffern enthalten."
    if len(pin) < mindest:
        return f"Die PIN muss mindestens {mindest} Ziffern haben."
    if pin in pin_sperrliste(session):
        return "Diese PIN ist zu einfach (Sperrliste) – bitte eine andere wählen."
    if len(set(pin)) == 1:
        return "Diese PIN ist zu einfach (eine Ziffer wiederholt)."
    if pin in "0123456789012345" or pin in "9876543210987654":
        return "Diese PIN ist zu einfach (Zahlenfolge)."
    for i in range(len(pin) - 3):
        block = pin[i:i + 4]
        if (block.startswith("19") or block.startswith("20")) and 1920 <= int(block) <= 2030:
            return "Diese PIN enthält ein Jahreszahl-Muster (Geburtsjahr) – bitte eine andere wählen."
    return None


# --- Login-Prüfung mit Sperre und Protokoll ----------------------------------------

def ip_kurzform(ip: str) -> str:
    """IPv4 a.b.c.x, IPv6 die ersten drei Gruppen – keine vollständige Adresse."""
    ip = (ip or "").strip()
    if not ip:
        return "-"
    if "." in ip and ip.count(".") == 3:
        teile = ip.split(".")
        return ".".join(teile[:3]) + ".x"
    if ":" in ip:
        return ":".join(ip.split(":")[:3]) + ":…"
    return ip[:20]


def client_ip(request) -> str:
    try:
        if request.client is not None and request.client.host:
            return request.client.host
    except Exception:
        pass
    return ""


def _ip_frei(ip: str) -> bool:
    """True, wenn die IP noch Versuche frei hat: höchstens 30 FEHLVERSUCHE je
    15 Minuten [ANNAHME: Plan nennt „Login-Versuche“; gezählt werden nur
    Fehlversuche, damit 50 Nutzer hinter einer gemeinsamen Adresse (Proxy ohne
    Forwarded-Header, Terminal-Server) sich nicht gegenseitig aussperren]."""
    jetzt = time.monotonic()
    with _ip_sperre:
        liste = _ip_versuche.setdefault(ip or "-", deque())
        grenze = jetzt - IP_FENSTER_MINUTEN * 60
        while liste and liste[0] < grenze:
            liste.popleft()
        return len(liste) < IP_MAX_VERSUCHE


def _ip_fehlversuch(ip: str) -> None:
    with _ip_sperre:
        _ip_versuche.setdefault(ip or "-", deque()).append(time.monotonic())


def ip_zaehler_zuruecksetzen() -> None:
    """Nur für Tests."""
    with _ip_sperre:
        _ip_versuche.clear()


def _protokollieren(session: Session, benutzer, ip: str, erfolg: bool, grund: str) -> None:
    from app.models import LoginProtokoll
    session.add(LoginProtokoll(
        zeit=datetime.now(), benutzer_id=getattr(benutzer, "id", None),
        benutzer_name=(getattr(benutzer, "name", "") or "")[:200],
        ip_kurz=ip_kurzform(ip), erfolg=bool(erfolg), grund=(grund or "")[:100]))


def login_pruefen(session: Session, benutzer, pin: str, ip: str = "") -> tuple[bool, str]:
    """Phase 130: PIN prüfen mit Fehlversuchssperre (5 Fehlversuche in 15 Minuten →
    15 Minuten Sperre), IP-Grenze (30 Versuche je 15 Minuten), Login-Protokoll
    und stiller Umstellung des Hashes auf PBKDF2. Committet selbst.
    Liefert (ok, Fehlertext)."""
    from app.models import LoginProtokoll
    jetzt = datetime.now()
    if not _ip_frei(ip):
        _protokollieren(session, benutzer, ip, False, "ip_limit")
        session.commit()
        return False, IP_SPERRE_TEXT
    if benutzer is None or not benutzer.aktiv:
        _ip_fehlversuch(ip)
        _protokollieren(session, benutzer, ip, False, "inaktiv" if benutzer else "unbekannt")
        session.commit()
        return False, PIN_FALSCH_TEXT
    if benutzer.gesperrt_bis is not None and benutzer.gesperrt_bis > jetzt:
        _ip_fehlversuch(ip)
        _protokollieren(session, benutzer, ip, False, "gesperrt")
        session.commit()
        return False, SPERRE_TEXT
    if pin_pruefen(benutzer, pin):
        benutzer.fehlversuche = 0
        benutzer.gesperrt_bis = None
        benutzer.letzter_login = jetzt
        if not benutzer.pin_hash_v2:
            benutzer.pin_hash_v2 = pin_hash_v2(pin)   # stille Umstellung
        _protokollieren(session, benutzer, ip, True, "ok")
        session.commit()
        return True, ""
    benutzer.fehlversuche = int(benutzer.fehlversuche or 0) + 1
    _ip_fehlversuch(ip)
    _protokollieren(session, benutzer, ip, False, "pin_falsch")
    session.flush()
    fenster = jetzt - timedelta(minutes=FEHLVERSUCH_FENSTER_MINUTEN)
    # ein erfolgreicher Login setzt das Fenster zurück (Agent-B-Hinweis R4):
    # nur Fehlversuche seit dem letzten erfolgreichen Login zählen
    if benutzer.letzter_login is not None and benutzer.letzter_login > fenster:
        fenster = benutzer.letzter_login
    im_fenster = (session.query(LoginProtokoll)
                  .filter(LoginProtokoll.benutzer_id == benutzer.id,
                          LoginProtokoll.erfolg.is_(False),
                          LoginProtokoll.grund == "pin_falsch",
                          LoginProtokoll.zeit >= fenster).count())
    if im_fenster >= MAX_FEHLVERSUCHE:
        benutzer.gesperrt_bis = jetzt + timedelta(minutes=SPERRE_MINUTEN)
        session.commit()
        return False, SPERRE_TEXT
    session.commit()
    return False, PIN_FALSCH_TEXT


def sperre_aufheben(benutzer) -> None:
    benutzer.fehlversuche = 0
    benutzer.gesperrt_bis = None


def login_protokoll_aufraeumen(session: Session, tage: int = LOGIN_PROTOKOLL_TAGE) -> int:
    from app.models import LoginProtokoll
    grenze = datetime.now() - timedelta(days=tage)
    return (session.query(LoginProtokoll).filter(LoginProtokoll.zeit < grenze)
            .delete(synchronize_session=False))


# --- Sitzungs-Cookie (v2: Ablauf + Sitzungszähler) ----------------------------------

def sitzungsdauer_s(session, benutzer, angemeldet_bleiben: bool = False) -> int:
    """Büro-Rollen 12 h; Außendienst/Montage mit Häkchen „Auf diesem Gerät
    angemeldet bleiben“ 30 Tage (Parameter sitzung_stunden_buero /
    sitzung_tage_mobil, Parametrierung → Benutzer)."""
    try:
        stunden = int(_einstellung(session, "sitzung_stunden_buero", str(SITZUNG_STUNDEN_BUERO)))
    except ValueError:
        stunden = SITZUNG_STUNDEN_BUERO
    try:
        tage = int(_einstellung(session, "sitzung_tage_mobil", str(SITZUNG_TAGE_MOBIL)))
    except ValueError:
        tage = SITZUNG_TAGE_MOBIL
    rolle = getattr(benutzer, "rolle", "")
    if angemeldet_bleiben and rolle in MOBILE_ROLLEN:
        return max(1, tage) * 24 * 3600
    return max(1, stunden) * 3600


def _signatur(nutzlast: str) -> str:
    return hmac.new(_geheimnis(), nutzlast.encode(), hashlib.sha256).hexdigest()


def _sitzungszaehler(benutzer_id: int) -> int:
    sitzung = SessionLocal()
    try:
        benutzer = sitzung.get(Benutzer, int(benutzer_id))
        return int(getattr(benutzer, "sitzungszaehler", 0) or 0) if benutzer else 0
    finally:
        sitzung.close()


def cookie_wert(benutzer_id: int, dauer_s: int | None = None,
                zaehler: int | None = None) -> str:
    """Signierter Cookie-Wert v2:<id>:<Ablauf Unixzeit>:<Sitzungszähler>:<HMAC>.
    Ohne Angaben: 12 h, Zähler des Benutzers (Tests, Crawl, Abnahme)."""
    if dauer_s is None:
        dauer_s = SITZUNG_STUNDEN_BUERO * 3600
    if zaehler is None:
        zaehler = _sitzungszaehler(benutzer_id)
    ablauf = int(time.time()) + int(dauer_s)
    nutzlast = f"{int(benutzer_id)}:{ablauf}:{int(zaehler)}"
    return f"{COOKIE_VERSION}:{nutzlast}:{_signatur(nutzlast)}"


def cookie_setzen(antwort, benutzer, dauer_s: int) -> None:
    """Cookie mit Ablauf, httponly, samesite=lax; secure bei HTTPS_AKTIV=1."""
    antwort.set_cookie(COOKIE_NAME,
                       cookie_wert(benutzer.id, dauer_s,
                                   int(getattr(benutzer, "sitzungszaehler", 0) or 0)),
                       httponly=True, max_age=int(dauer_s), samesite="lax",
                       secure=bool(config.HTTPS_AKTIV))


def cookie_pruefen(wert: str) -> tuple[int, int] | None:
    """(Benutzer-ID, Sitzungszähler) bei gültiger Signatur und Ablauf, sonst
    None. Cookies der v26-Form (id:signatur) werden abgewiesen – einmal neu
    anmelden nach dem Update."""
    if not wert:
        return None
    teile = wert.split(":")
    if len(teile) != 5 or teile[0] != COOKIE_VERSION:
        return None
    _, kennung, ablauf, zaehler, signatur = teile
    if not (kennung.isdigit() and ablauf.isdigit() and zaehler.isdigit()):
        return None
    nutzlast = f"{kennung}:{ablauf}:{zaehler}"
    if not hmac.compare_digest(signatur, _signatur(nutzlast)):
        return None
    if int(ablauf) < int(time.time()):
        return None
    return int(kennung), int(zaehler)


def benutzer_aus_cookie(wert: str, session: Session):
    geprueft = cookie_pruefen(wert)
    if geprueft is None:
        return None
    kennung, zaehler = geprueft
    benutzer = session.get(Benutzer, kennung)
    if benutzer is None or not benutzer.aktiv:
        return None
    if int(getattr(benutzer, "sitzungszaehler", 0) or 0) != zaehler:
        return None   # „Alle Sitzungen beenden“ durch den Admin
    return benutzer


def alle_sitzungen_beenden(benutzer) -> None:
    benutzer.sitzungszaehler = int(getattr(benutzer, "sitzungszaehler", 0) or 0) + 1


def standardbenutzer_anlegen() -> None:
    """Beim Start: ohne Benutzer wäre das Tool ausgesperrt – Admin (PIN 1234) anlegen.
    Migration Phase 18: gibt es noch keinen Benutzer mit Rolle admin, wird der
    Benutzer „Admin“ auf die neue Admin-Rolle gehoben."""
    session = SessionLocal()
    try:
        if session.query(Benutzer).count() == 0:
            session.add(Benutzer(name="Admin", rolle="admin",
                                 pin_hash=pin_hash("1234"), pin_wechsel_noetig=True))
            session.commit()
        elif not session.query(Benutzer).filter(Benutzer.rolle == "admin").count():
            admin = session.query(Benutzer).filter(Benutzer.name == "Admin").first()
            if admin is not None:
                admin.rolle = "admin"
                session.commit()
    finally:
        session.close()


# --- Middleware -----------------------------------------------------------------

class RollenMiddleware(BaseHTTPMiddleware):
    """Setzt request.state.benutzer und erzwingt die Rollen-Sicht:
    Außendienst nur /erfassung, Innendienst alles.
    v27: Datenbankarbeit im Threadpool (blockiert die Event-Loop nicht),
    höchstens EINE Verbindung je Anfrage (Sitzung vor call_next zu),
    Zugriffsprotokoll mit Dauer, Wartungsbanner, Pflicht-PIN-Wechsel."""

    @staticmethod
    def _laden(request: Request):
        """Läuft im Threadpool: Benutzer, Glocke, Modul-Schalter, Wartungshinweis.
        Die Sitzung wird hier geschlossen – vor call_next."""
        pfad = request.url.path
        session = SessionLocal()
        try:
            benutzer = benutzer_aus_cookie(request.cookies.get(COOKIE_NAME, ""), session)
            request.state.benutzer = benutzer
            # v11 (Phase 69): Glocke in der Kopfzeile – Zähler + letzte 20
            # für jede gerenderte Seite (Fehler blockieren die Seite nie)
            request.state.glocke_ungelesen = 0
            request.state.glocke_liste = []
            request.state.lead_modul_ok = False
            request.state.lead_ad_ok = False
            request.state.lead_hv_ok = False
            request.state.wartung = None
            request.state.lm_demo_badge = None
            if benutzer is not None and not pfad.startswith("/static"):
                # v27 (Befund B7): Demo-Badge der Lead-Icon-Leiste hier lesen statt
                # im Jinja-Global mit eigener Sitzung (zweite Verbindung je Lead-Seite)
                try:
                    from app import leadmanagement as kern
                    request.state.lm_demo_badge = {
                        "aktiv": kern.demo_aktiv(session),
                        "text": kern.parameter_holen(session, "demo_badge_text",
                                                     "Demo · Coming soon")}
                except Exception:
                    pass
                try:
                    from app import benachrichtigungen as glocke_modul
                    request.state.glocke_ungelesen = (
                        glocke_modul.ungelesen_anzahl(session, benutzer))
                    request.state.glocke_liste = (
                        glocke_modul.letzte(session, benutzer, 20))
                except Exception:
                    pass
                # v12 (Phase 73): steuert Menüpunkt + Reiter des Lead-Moduls
                try:
                    from app import leadmanagement
                    request.state.lead_modul_ok = (
                        leadmanagement.lead_modul_sichtbar(session, benutzer))
                    request.state.lead_ad_ok = (
                        leadmanagement.lead_ad_sicht(session, benutzer))
                    # v23 (Phase 109): Handelsvertreter-Sicht (Kennzeichen am AD-Profil,
                    # A-1) – steuert die Menüeinträge „Meine Leads“/„Mein Dashboard“
                    from app import lead_v2
                    request.state.lead_hv_ok = lead_v2.ist_handelsvertreter(session, benutzer)
                except Exception:
                    pass
                # Design-Fix 27.09.2026: Projektierung fehlte im Hauptmenü
                try:
                    from app import projektierung
                    request.state.projektierung_ok = (
                        projektierung.modul_sichtbar(session, benutzer))
                except Exception:
                    pass
            # v27 (Phase 132): Wartungsbanner für alle Rollen (60 s zwischengespeichert)
            if not pfad.startswith("/static"):
                try:
                    from app import betrieb
                    request.state.wartung = betrieb.wartungshinweis_aktuell(session=session)
                except Exception:
                    pass
            return benutzer
        finally:
            # Hotfix 06.10.2026 (Verbindungspool): die Middleware-Sitzung wird
            # NACH den Rollen-, Glocken- und Modulabfragen und VOR call_next
            # geschlossen – sonst hält jede laufende Anfrage eine zweite
            # Pool-Verbindung für ihre gesamte Dauer. request.state.benutzer
            # bleibt als abgelöstes Objekt mit allen Spalten nutzbar
            # (expire_on_commit=False; Benutzer hat keine Relationships).
            session.close()

    async def dispatch(self, request: Request, call_next):
        pfad = request.url.path
        start = time.perf_counter()
        pool_belegt = 0
        try:
            from app.db import engine
            pool_belegt = int(engine.pool.checkedout())
        except Exception:
            pass
        status = 500
        request.state.benutzer = None
        try:
            # v22 (Phase 103): Formdaten vor dem Endpunkt puffern, damit das
            # Fehlerprotokoll sie bei einer Ausnahme noch kennt (PIN/Passwort
            # maskiert, nur Formulare bis 64 KB; ClientDisconnect reicht durch)
            request.state.formdaten = None
            try:
                from app import fehlerprotokoll
                request.state.formdaten = await fehlerprotokoll.formdaten_puffern(request)
            except ClientDisconnect:
                raise
            except Exception:
                pass
            benutzer = await run_in_threadpool(self._laden, request)
            # v27: Kontext für Jinja-Globals ohne Request (reicht in den Worker-Thread)
            from app import anfrage
            anfrage.KONTEXT.set({"lm_demo_badge": getattr(request.state, "lm_demo_badge", None)})
            antwort = await self._weiterleiten(request, benutzer, pfad, call_next)
            status = antwort.status_code
            return antwort
        finally:
            if not pfad.startswith(("/static", "/health")):
                try:
                    from app import zugriffslog
                    benutzer = getattr(request.state, "benutzer", None)
                    zugriffslog.eintragen(
                        getattr(benutzer, "id", None), getattr(benutzer, "rolle", "") or "",
                        request.method, pfad, status,
                        int((time.perf_counter() - start) * 1000), pool_belegt)
                except Exception:
                    pass

    async def _weiterleiten(self, request: Request, benutzer, pfad: str, call_next):
        if pfad.startswith(OFFENE_PFADE):
            return await call_next(request)
        if benutzer is None:
            return RedirectResponse("/login", status_code=303)
        # v27 (Phase 130): Pflichtwechsel der PIN beim ersten Login / nach Admin-Reset
        if (getattr(benutzer, "pin_wechsel_noetig", False)
                and not pfad.startswith(PIN_WECHSEL_PFAD)):
            return RedirectResponse(PIN_WECHSEL_PFAD, status_code=303)
        if benutzer.rolle == "projektierung":
            # "/" bleibt erreichbar: Landeplatz im Demo-Modus (Portal
            # zeigt die nicht anklickbare Projektierungs-Karte)
            if pfad != "/" and not pfad.startswith(PROJEKTIERUNG_PFADE):
                return RedirectResponse("/projektierung", status_code=303)
            if (request.method != "GET"
                    and not pfad.startswith(PROJEKTIERUNG_SCHREIBEN)):
                return RedirectResponse("/projektierung", status_code=303)
            # Angebote nur lesend: Liste + PDF (kein Editor, kein EK/DB)
            if pfad.startswith("/angebote") and not _ANGEBOTE_LESEPFAD.match(pfad):
                return RedirectResponse("/angebote", status_code=303)
        elif benutzer.rolle == "montage":
            # Bugfix 27.09.2026: auch "/" umleiten - das Portal hat fuer
            # die Rolle Montage nichts Klickbares (Handy-Login strandete)
            if (not pfad.startswith(MONTAGE_PFADE)
                    and not _MONTAGE_GALERIE.match(pfad)):
                return RedirectResponse("/montage", status_code=303)
        elif benutzer.rolle == "leadmanagement":
            if pfad != "/" and not pfad.startswith(LEADMANAGEMENT_PFADE):
                return RedirectResponse("/lead-management", status_code=303)
            if (request.method != "GET"
                    and not pfad.startswith(LEADMANAGEMENT_SCHREIBEN)):
                return RedirectResponse("/lead-management", status_code=303)
            # Angebote nur Liste + PDF (kein Editor, kein EK/DB)
            if pfad.startswith("/angebote") and not _ANGEBOTE_LESEPFAD.match(pfad):
                return RedirectResponse("/angebote", status_code=303)
        elif benutzer.rolle not in BUERO_ROLLEN and not pfad.startswith(AUSSENDIENST_PFADE):
            return RedirectResponse("/erfassung", status_code=303)
        if benutzer.rolle == "innendienst" and pfad.startswith(ADMIN_PFADE):
            return RedirectResponse("/", status_code=303)
        return await call_next(request)
