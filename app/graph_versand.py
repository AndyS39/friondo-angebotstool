# Microsoft Graph – Versand, Entwürfe, Postfach-Abruf (Phase 17/27/28/31, v11, v15, v29).
# v33 (PLAN_V20 Phase 166): zwei Betriebsmodi
#  - „anwendung“ (Standard nach grünem Verbindungstest): Client-Credentials-Token der
#    App-Registrierung (Anwendungsberechtigungen Mail.Send, Mail.ReadWrite,
#    Calendars.ReadWrite + Exchange-Zugriffsgruppe Friondo-Tool-Zugriff); ALLE Aufrufe
#    laufen über /users/<postfach>/… – Versand direkt am Funktionspostfach (sendMail an
#    angebot@/termin@/projektierung@, kein „Senden als“, kein from-Feld), Entwürfe des
#    Angebotsversands im Postfach angebot@, Abruf der Antworten aus angebot@/termin@,
#    Kalender der Mitarbeiter. Keine persönliche Anmeldung mehr nötig.
#  - „delegiert“ (Rückfallebene, heutiger Weg unverändert): Device-Code-Anmeldung einer
#    Person, /me/… mit from = Funktionspostfach („Senden als“), Entwürfe im Postfach der
#    angemeldeten Person.
# Die Postfach-Entscheidung fällt HIER (versand_pfad/basis_pfad) – Aufrufer übergeben nur
# absender=<Funktionspostfach>. Jeder Aufrufer gibt seine Datenbanksitzung vor dem
# Netzaufruf frei (v27-Regel). Einrichtung durch die IT: docs/graph-einrichtung.md.

import base64
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from app import config
from app.models import Angebot, Kunde

# Delegierte Berechtigungen (Modus delegiert, docs/graph-einrichtung.md „Übergangsweg“):
#  Mail.ReadWrite / Mail.Read  – Entwurf im eigenen Postfach, Mail-Verlauf
#  Mail.Send                   – Info-Mail nach Fern-Signatur (Phase 28)
#  *.Shared (Phase 31)         – Zugriff auf das freigegebene Postfach
#                                angebot@friondo.de (Versand-Erkennung,
#                                Antworten der Kunden); setzt „Vollzugriff“
#                                auf das Postfach durch den M365-Admin voraus
SCOPES = ["Mail.ReadWrite", "Mail.Read", "Mail.Send",
          "Mail.ReadWrite.Shared", "Mail.Send.Shared"]
GRAPH = "https://graph.microsoft.com/v1.0"

# --- v33 (PLAN_V20 Phase 166): Betriebsmodus „anwendung“ | „delegiert“ -------------------
# anwendung = Client-Credentials-Token (Anwendungsberechtigungen Mail.Send, Mail.ReadWrite,
# Calendars.ReadWrite + Exchange-Zugriffsgruppe friondo-tool-zugriff@), alle Aufrufe über
# /users/<postfach>/…; delegiert = heutiger Weg (Device-Code-Anmeldung einer Person, /me/…).
# Der Modus ist erst „anwendung“, wenn das Geheimnis in der .env steht UND der
# Verbindungstest (Versand-Seite) grün war – gespeichert in der Einstellung graph_modus.
MODUS_ANWENDUNG = "anwendung"
MODUS_DELEGIERT = "delegiert"
EINSTELLUNG_MODUS = "graph_modus"
EINSTELLUNG_LETZTER_TEST = "graph_letzter_test"     # JSON: Zeit, Modus, Ergebnis je Postfach
SCOPE_ANWENDUNG = ["https://graph.microsoft.com/.default"]
ZUGRIFFSGRUPPE = "Friondo-Tool-Zugriff"
ZUGRIFFSGRUPPE_ADRESSE = "friondo-tool-zugriff@friondo.de"
STANDARD_POSTFACH = "angebot@friondo.de"
TOKEN_RESERVE_S = 300          # Erneuerung fünf Minuten vor Ablauf
MELDUNG_403_PAUSE_S = 3600     # Fehlerprotokoll höchstens einmal je Postfach und Stunde
GEHEIMNIS_WARN_TAGE = 30       # /health warn + Go-live rot, wenn das Geheimnis ≤ 30 Tage gilt
VERBINDUNGSTEST_TIMEOUT_S = 20
ART_FUNKTIONSPOSTFACH = "funktionspostfach"
ART_MITARBEITER = "mitarbeiter"
# Basisrollen, deren aktive Benutzer (mit E-Mail) Termine/Besetzungen tragen und damit ein
# Postfach in der Zugriffsgruppe brauchen (Kalender je Mitarbeiter, Phase 170)
MITARBEITER_BASISROLLEN = ("aussendienst", "projektierung", "montage", "innendienst")
TEXT_NICHT_ANGEMELDET = "Nicht bei Microsoft angemeldet"
TEXT_ANWENDUNG_FEHLER = "Anmeldung der Anwendung fehlgeschlagen"
KONTO_ANWENDUNG = f"Anwendung ({ZUGRIFFSGRUPPE})"   # Rückgabe von angemeldeter_benutzer()
_modus_cache: str | None = None
_app_token: dict = {"wert": "", "ablauf": 0.0, "fehler": ""}
_app_sperre = threading.Lock()
_verweigert: dict[str, float] = {}      # postfach (klein) → Zeit der letzten 403-Meldung
_letzter_erfolg: dict[str, float] = {}  # postfach (klein) → Zeit des letzten erfolgreichen Aufrufs


class GraphZugriffVerweigert(Exception):
    """HTTP 403 – Postfach nicht in der Zugriffsgruppe (Modus anwendung)."""

    def __init__(self, postfach: str, pfad: str = ""):
        self.postfach = postfach
        self.pfad = pfad
        super().__init__(f"Postfach {postfach} ist nicht in der Zugriffsgruppe {ZUGRIFFSGRUPPE}")


def anwendung_konfiguriert() -> bool:
    """Geheimnis (oder Zertifikat) plus Mandant und Client-ID vorhanden."""
    return bool(config.GRAPH_CLIENT_ID and config.GRAPH_TENANT_ID
                and (config.GRAPH_CLIENT_SECRET
                     or (config.GRAPH_ZERTIFIKAT_PFAD and config.GRAPH_ZERTIFIKAT_THUMBPRINT)))


def _modus_lesen(session=None) -> str:
    from app.models import einstellung_holen
    if session is not None:
        wert = einstellung_holen(session, EINSTELLUNG_MODUS, MODUS_DELEGIERT)
    else:
        try:
            from app.db import kurz
            with kurz(schreibend=False) as s:   # v33 (Phase 172): nur lesen - keine Schreibtransaktion
                wert = einstellung_holen(s, EINSTELLUNG_MODUS, MODUS_DELEGIERT)
        except Exception:   # noqa: BLE001 – ohne Datenbank gilt der Rückfallweg
            wert = MODUS_DELEGIERT
    return MODUS_ANWENDUNG if (wert or "").strip().lower() == MODUS_ANWENDUNG else MODUS_DELEGIERT


def modus(session=None) -> str:
    """Wirksamer Modus: „anwendung“ nur mit Geheimnis UND grünem Verbindungstest
    (Einstellung), sonst „delegiert“."""
    global _modus_cache
    if not anwendung_konfiguriert():
        return MODUS_DELEGIERT
    if _modus_cache is None:
        _modus_cache = _modus_lesen(session)
    return _modus_cache


def modus_setzen(session, wert: str) -> str:
    """Einstellung graph_modus schreiben (Verbindungstest grün → anwendung)."""
    global _modus_cache
    from app.models import einstellung_setzen
    wert = MODUS_ANWENDUNG if (wert or "").strip().lower() == MODUS_ANWENDUNG else MODUS_DELEGIERT
    einstellung_setzen(session, EINSTELLUNG_MODUS, wert)
    _modus_cache = None
    return wert


def modus_cache_leeren() -> None:
    global _modus_cache
    _modus_cache = None
    with _app_sperre:
        _app_token.update(wert="", ablauf=0.0, fehler="")


def modus_grund(session=None) -> str:
    """Warum der Modus nicht „anwendung“ ist (leer, wenn er es ist) – Verbindungs-Seite."""
    if not anwendung_konfiguriert():
        if config.GRAPH_CLIENT_ID and config.GRAPH_TENANT_ID:
            return "Geheimnis fehlt (.env: GRAPH_CLIENT_SECRET oder GRAPH_ZERTIFIKAT_PFAD + THUMBPRINT)"
        return "App-Registrierung fehlt (.env: GRAPH_CLIENT_ID, GRAPH_TENANT_ID, GRAPH_CLIENT_SECRET)"
    if modus(session) == MODUS_ANWENDUNG:
        return ""
    return "Verbindungstest offen – „Verbindung testen“ muss für alle Funktionspostfächer grün sein"


def modus_name(wert: str | None = None) -> str:
    return "Anwendung" if (wert or modus()) == MODUS_ANWENDUNG else "Delegiert"


def _confidential_app():
    """MSAL ConfidentialClientApplication (Geheimnis oder Zertifikat) – nur Modus anwendung."""
    import msal
    autoritaet = f"https://login.microsoftonline.com/{config.GRAPH_TENANT_ID}"
    if config.GRAPH_CLIENT_SECRET:
        berechtigung = config.GRAPH_CLIENT_SECRET
    else:
        berechtigung = {"private_key": Path(config.GRAPH_ZERTIFIKAT_PFAD).read_text(encoding="utf-8"),
                        "thumbprint": config.GRAPH_ZERTIFIKAT_THUMBPRINT}
    return msal.ConfidentialClientApplication(config.GRAPH_CLIENT_ID, authority=autoritaet,
                                              client_credential=berechtigung)


def _token_anwendung() -> str | None:
    """Client-Credentials-Token mit Cache im Prozess (Erneuerung TOKEN_RESERVE_S vor
    Ablauf). Netzaufruf – der Aufrufer hat die Datenbanksitzung vorher freigegeben
    (v27-Regel). Scheitert die Anmeldung, steht der Grund in token_fehler()."""
    with _app_sperre:
        if _app_token["wert"] and _app_token["ablauf"] - TOKEN_RESERVE_S > time.time():
            return _app_token["wert"]
    try:
        ergebnis = _confidential_app().acquire_token_for_client(scopes=SCOPE_ANWENDUNG)
    except Exception as fehler:   # noqa: BLE001 – kein Token = Aufrufer meldet „nicht verbunden“
        with _app_sperre:
            _app_token.update(wert="", ablauf=0.0,
                              fehler=f"{type(fehler).__name__}: {fehler}"[:300])
        return None
    ergebnis = ergebnis or {}
    token = ergebnis.get("access_token")
    if not token:
        with _app_sperre:
            _app_token.update(wert="", ablauf=0.0,
                              fehler=str(ergebnis.get("error_description") or ergebnis.get("error")
                                         or "kein Token in der Antwort")[:300])
        return None
    with _app_sperre:
        _app_token.update(wert=token, ablauf=time.time() + int(ergebnis.get("expires_in", 3600)),
                          fehler="")
    return token


def token_fehler() -> str:
    """Letzter Fehler der Anwendungs-Anmeldung (leer, wenn die letzte Anmeldung gelang)."""
    with _app_sperre:
        return _app_token.get("fehler", "")


def app_token_verwerfen() -> None:
    """Zwischengespeichertes Anwendungs-Token verwerfen (Verbindungstest holt ein frisches)."""
    with _app_sperre:
        _app_token.update(wert="", ablauf=0.0)


def standard_postfach(session=None) -> str:
    """Funktionspostfach des Angebotsversands (Einstellung mail_absender, Standard angebot@)."""
    from app.models import einstellung_holen
    try:
        if session is not None:
            return einstellung_holen(session, "mail_absender", STANDARD_POSTFACH) or STANDARD_POSTFACH
        from app.db import kurz
        with kurz(schreibend=False) as s:   # v33 (Phase 172): nur lesen - keine Schreibtransaktion
            return einstellung_holen(s, "mail_absender", STANDARD_POSTFACH) or STANDARD_POSTFACH
    except Exception:   # noqa: BLE001
        return STANDARD_POSTFACH


def basis_pfad(postfach: str = "", session=None) -> str:
    """Graph-Basis je Postfach: Modus anwendung immer /users/<postfach> (ohne Angabe das
    Funktionspostfach des Versands), Modus delegiert /users/<postfach> für fremde
    Postfächer und /me für das angemeldete Konto."""
    if modus(session) == MODUS_ANWENDUNG:
        ziel = (postfach or "").strip() or standard_postfach(session)
        return f"/users/{urllib.parse.quote(ziel)}"
    return f"/users/{urllib.parse.quote(postfach)}" if postfach else "/me"


def versand_pfad(absender: str = "", session=None) -> tuple[str, str]:
    """(Graph-Basis, from-Adresse) für einen Versand: Modus anwendung → sendMail direkt am
    Funktionspostfach (/users/<absender>, KEIN from-Feld); Modus delegiert → /me mit
    from = absender („Senden als“, heutiger Weg)."""
    if modus(session) == MODUS_ANWENDUNG:
        return basis_pfad(absender, session), ""
    return "/me", (absender or "").strip()


def postfach_aus_pfad(pfad: str) -> str:
    """Postfach-Adresse aus einem Graph-Pfad /users/<adresse>/… (leer bei /me)."""
    teile = (pfad or "").split("/")
    if len(teile) > 2 and teile[1] == "users":
        return urllib.parse.unquote(teile[2]).strip().lower()
    return ""


def nicht_verbunden_text(session=None) -> str:
    """Fehlertext ohne Token – je Modus (Aufrufer geben ihn an Oberfläche/Protokoll weiter)."""
    if modus(session) == MODUS_ANWENDUNG:
        return (f"{TEXT_ANWENDUNG_FEHLER}: {token_fehler() or 'kein Token'} – "
                "Verbindungstest unter „Versand“ ausführen.")
    return f"{TEXT_NICHT_ANGEMELDET} – bitte unter „Versand“ anmelden."


def verbunden(session=None) -> bool:
    """Ist Graph nutzbar? Modus anwendung: Geheimnis + grüner Verbindungstest (Einstellung);
    Modus delegiert: eine Person ist angemeldet. Kein Netzaufruf im Modus anwendung;
    im Modus delegiert kann msal das Token über das Netz erneuern – die übergebene
    Sitzung wird deshalb vorher freigegeben (v27-Regel)."""
    if modus(session) == MODUS_ANWENDUNG:
        return True
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    return angemeldeter_benutzer() is not None


def zugriff_verweigert_merken(postfach: str, pfad: str = "") -> bool:
    """403 → Fehlerprotokoll, höchstens einmal je Postfach und Stunde. True = neu gemeldet."""
    schluessel = (postfach or "?").strip().lower()
    jetzt = time.time()
    letzte = _verweigert.get(schluessel, 0.0)
    _verweigert[schluessel] = jetzt
    if jetzt - letzte < MELDUNG_403_PAUSE_S:
        return False
    try:
        from app import fehlerprotokoll
        fehlerprotokoll.eintragen_text(
            "Graph", f"Postfach {schluessel} ist nicht in der Zugriffsgruppe {ZUGRIFFSGRUPPE}",
            detail=f"HTTP 403 bei {pfad}" if pfad else "HTTP 403", pfad=pfad)
    except Exception:   # noqa: BLE001 – das Protokoll darf den Aufruf nie zusätzlich stören
        pass
    return True


def zugriff_verweigert_liste() -> list[tuple[str, float]]:
    """(postfach, zeit) der zuletzt mit 403 abgewiesenen Postfächer (Verbindungs-Seite)."""
    return sorted(_verweigert.items(), key=lambda kv: kv[0])


def zugriff_verweigert_leeren() -> None:
    _verweigert.clear()


def erfolg_merken(pfad: str) -> None:
    """Erfolgreicher Graph-Aufruf → Zeit je Postfach (Verbindungs-Seite „letzte erfolgreiche
    Aufrufe“; Modul-Dict, gilt seit dem Prozessstart)."""
    schluessel = postfach_aus_pfad(pfad) or "(angemeldetes Konto)"
    _letzter_erfolg[schluessel] = time.time()
    if schluessel in _verweigert:
        _verweigert.pop(schluessel, None)   # Zugriff wieder da → aus der 403-Liste


def letzte_erfolge() -> dict[str, float]:
    return dict(_letzter_erfolg)


def erfolge_leeren() -> None:
    _letzter_erfolg.clear()


def geheimnis_ablauf_datum():
    """Ablaufdatum des Geheimnisses (GRAPH_GEHEIMNIS_ABLAUF, JJJJ-MM-TT), None ohne Datum."""
    from datetime import date
    roh = (config.GRAPH_GEHEIMNIS_ABLAUF or "").strip()
    if not roh:
        return None
    try:
        return date.fromisoformat(roh[:10])
    except ValueError:
        return None


def geheimnis_ablauf_tage() -> int | None:
    """Tage bis zum Ablauf des Geheimnisses (GRAPH_GEHEIMNIS_ABLAUF), None ohne Datum."""
    from datetime import date
    datum = geheimnis_ablauf_datum()
    return (datum - date.today()).days if datum is not None else None


def geheimnis_warnung() -> str:
    """Warntext für /health und Betriebs-Seite (leer, wenn > 30 Tage oder kein Datum)."""
    tage = geheimnis_ablauf_tage()
    if tage is None or tage > GEHEIMNIS_WARN_TAGE:
        return ""
    if tage < 0:
        return f"Graph-Geheimnis ist seit {-tage} Tagen abgelaufen"
    if tage == 0:
        return "Graph-Geheimnis läuft heute ab"
    return f"Graph-Geheimnis läuft in {tage} Tagen ab"


def mandant_maskiert() -> str:
    """Mandant (GRAPH_TENANT_ID) auf die ersten 8 Zeichen maskiert – nie im Klartext."""
    wert = (config.GRAPH_TENANT_ID or "").strip()
    if not wert:
        return "–"
    return wert[:8] + "…" if len(wert) > 8 else wert


def migration_v33_graph(session) -> list:
    """migrate.py-Hook: Einstellung graph_modus anlegen (Startwert delegiert – anwendung
    erst nach grünem Verbindungstest)."""
    from app.models import einstellung_holen, einstellung_setzen
    if einstellung_holen(session, EINSTELLUNG_MODUS, "") == "":
        einstellung_setzen(session, EINSTELLUNG_MODUS, MODUS_DELEGIERT)
        return ["Graph (v33): Einstellung graph_modus = delegiert angelegt (anwendung erst "
                "nach grünem Verbindungstest unter /versand)"]
    return []


# --- Modus delegiert: Device-Code-Anmeldung einer Person (Rückfallebene) ----------------

_token_cache = None
_flow_status: dict = {"laeuft": False, "user_code": "", "verification_uri": "",
                      "fehler": ""}


def konfiguriert() -> bool:
    return bool(config.GRAPH_CLIENT_ID)


def _cache_pfad() -> Path:
    return config.DATA_ORDNER / ".graph_token.json"


def _app():
    import msal
    global _token_cache
    if _token_cache is None:
        _token_cache = msal.SerializableTokenCache()
        if _cache_pfad().exists():
            _token_cache.deserialize(_cache_pfad().read_text(encoding="utf-8"))
    autoritaet = (f"https://login.microsoftonline.com/"
                  f"{config.GRAPH_TENANT_ID or 'organizations'}")
    return msal.PublicClientApplication(config.GRAPH_CLIENT_ID,
                                        authority=autoritaet,
                                        token_cache=_token_cache)


def _cache_speichern():
    if _token_cache is not None and _token_cache.has_state_changed:
        config.DATA_ORDNER.mkdir(parents=True, exist_ok=True)
        _cache_pfad().write_text(_token_cache.serialize(), encoding="utf-8")


def angemeldeter_benutzer() -> str | None:
    """Name/E-Mail des angemeldeten Kontos, wenn ein gültiges Token vorliegt.
    v33: im Modus anwendung gibt es kein persönliches Konto – Rückgabe ist das feste
    Kennzeichen KONTO_ANWENDUNG (nicht None), damit die Versand-Routen („bitte zuerst
    anmelden“) ohne Anmeldung einer Person weiterlaufen; neue Prüfungen nutzen verbunden()."""
    if not konfiguriert():
        return None
    if modus() == MODUS_ANWENDUNG:
        return KONTO_ANWENDUNG
    return delegiertes_konto()


def delegiertes_konto() -> str | None:
    """Angemeldetes Konto des Device-Code-Wegs – unabhängig vom Modus (Verbindungs-Seite).
    Best effort: scheitert msal (kein Netz zur Anmeldestelle, defekter Token-Cache), gilt
    „nicht angemeldet“ – die Verbindungs-Seite muss immer rendern."""
    if not konfiguriert():
        return None
    try:
        app = _app()
        konten = app.get_accounts()
        if not konten:
            return None
        ergebnis = app.acquire_token_silent(SCOPES, account=konten[0])
        _cache_speichern()
    except Exception:   # noqa: BLE001 – msal-Fehler = kein angemeldetes Konto
        return None
    if ergebnis and "access_token" in ergebnis:
        return konten[0].get("username", "angemeldet")
    return None


def _token() -> str | None:
    """v33: Modus anwendung → Client-Credentials-Token; sonst (delegiert) das Token des
    angemeldeten Kontos wie bisher."""
    if modus() == MODUS_ANWENDUNG:
        return _token_anwendung()
    app = _app()
    konten = app.get_accounts()
    if not konten:
        return None
    ergebnis = app.acquire_token_silent(SCOPES, account=konten[0])
    _cache_speichern()
    if ergebnis and "access_token" in ergebnis:
        return ergebnis["access_token"]
    return None


def anmeldung_starten() -> dict:
    """Startet den Device-Code-Flow; das Polling läuft in einem Hintergrund-Thread."""
    if _flow_status["laeuft"]:
        return _flow_status
    app = _app()
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        _flow_status.update(laeuft=False, fehler=flow.get("error_description",
                                                          "Device-Flow fehlgeschlagen"))
        return _flow_status
    _flow_status.update(laeuft=True, user_code=flow["user_code"],
                        verification_uri=flow.get("verification_uri",
                                                  "https://microsoft.com/devicelogin"),
                        fehler="")

    def warten():
        try:
            ergebnis = app.acquire_token_by_device_flow(flow)  # blockiert bis Anmeldung/Timeout
            if "access_token" not in (ergebnis or {}):
                _flow_status["fehler"] = (ergebnis or {}).get("error_description",
                                                              "Anmeldung nicht abgeschlossen")
            _cache_speichern()
        except Exception as fehler:
            _flow_status["fehler"] = str(fehler)
        finally:
            _flow_status["laeuft"] = False

    threading.Thread(target=warten, daemon=True).start()
    return _flow_status


def anmeldestatus() -> dict:
    return dict(_flow_status)


def abmelden() -> None:
    global _token_cache
    _token_cache = None
    _cache_pfad().unlink(missing_ok=True)


# --- Entwurf im Postfach --------------------------------------------------

def signatur_absatz(signatur_link: str) -> str:
    """Wird bei aktiver Fern-Signatur (Phase 28) an den Mailtext angehängt
    (seit v6 als HTML-Absatz)."""
    if not signatur_link:
        return ""
    return ("<p>Sie möchten das Angebot direkt annehmen? Unter folgendem Link "
            "können Sie bequem online unterschreiben (auch am Smartphone):<br>"
            f'<a href="{signatur_link}">{signatur_link}</a></p>')


def _graph_aufruf(methode: str, pfad: str, token: str, daten: dict | None = None,
                  timeout: int = 60) -> dict:
    anfrage = urllib.request.Request(
        GRAPH + pfad,
        data=json.dumps(daten).encode() if daten is not None else None,
        method=methode,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    # v22: Timeout, damit ein hängender Graph-Aufruf keinen Hintergrundlauf
    # (und damit die SQLite-Schreibsperre) unbegrenzt hält
    try:
        with urllib.request.urlopen(anfrage, timeout=timeout) as antwort:
            inhalt = antwort.read()
    except urllib.error.HTTPError as fehler:
        # v33 (Phase 166): 403 = Postfach nicht in der Zugriffsgruppe → Fehlerprotokoll
        # (einmal je Postfach und Stunde), danach weiter als Ausnahme für den Aufrufer
        if fehler.code == 403:
            postfach = postfach_aus_pfad(pfad)
            zugriff_verweigert_merken(postfach, pfad)
            raise GraphZugriffVerweigert(postfach or "(angemeldetes Konto)", pfad) from fehler
        raise
    erfolg_merken(pfad)   # v33: „letzte erfolgreiche Aufrufe je Postfach“ (Verbindungs-Seite)
    return json.loads(inhalt) if inhalt else {}


# --- v29 (PLAN_LEAD_V4 Phase 142): Postfach-Abruf für den Lauf lead-mail-abruf ---
# Nur additiv: Antworten und Unzustellbarkeitsberichte aus dem Lead-Absender-
# Postfach (termin@friondo.de). v33: Basis über basis_pfad – Modus anwendung immer
# /users/<postfach> (Zugriffsgruppe), Modus delegiert wie bisher Shared Mailbox mit
# Lesezugriff bzw. /me. Alle drei Funktionen laufen ohne Datenbanksitzung (der
# Aufrufer liest vorher mit db.kurz() und schreibt danach in einer neuen).

def postfach_ungelesen(token: str, postfach: str, top: int = 50) -> list[dict]:
    """Ungelesene Nachrichten des Posteingangs (Postfach `postfach`, leer = eigenes bzw.
    im Modus anwendung das Funktionspostfach) mit Betreff, Absender, Empfängern, Body."""
    basis = basis_pfad(postfach)
    antwort = _graph_aufruf(
        "GET", f"{basis}/mailFolders/inbox/messages?$top={int(top)}"
               "&$filter=isRead eq false"
               "&$select=id,subject,from,toRecipients,receivedDateTime,body,bodyPreview,"
               "conversationId,internetMessageId", token)
    return antwort.get("value", [])


def nachricht_kopfzeilen(token: str, postfach: str, nachricht_id: str) -> dict:
    """Internet-Kopfzeilen einer Nachricht ({name (klein): wert}), z. B.
    in-reply-to, references, x-ms-exchange-message-is-ndr."""
    basis = basis_pfad(postfach)
    antwort = _graph_aufruf("GET", f"{basis}/messages/{urllib.parse.quote(nachricht_id)}"
                                   "?$select=internetMessageHeaders", token)
    return {str(k.get("name", "")).lower(): str(k.get("value", ""))
            for k in antwort.get("internetMessageHeaders", []) or []}


def nachricht_gelesen_markieren(token: str, postfach: str, nachricht_id: str) -> bool:
    """isRead = true (damit die Nachricht beim nächsten Lauf nicht erneut kommt)."""
    basis = basis_pfad(postfach)
    try:
        _graph_aufruf("PATCH", f"{basis}/messages/{urllib.parse.quote(nachricht_id)}",
                      token, {"isRead": True})
        return True
    except Exception:
        return False


def info_mail_senden(betreff: str, text: str) -> bool:
    """Sendet eine kurze Info-Mail an das eigene Postfach (Fern-Signatur,
    Phase 28). Best effort: ohne Anmeldung/Berechtigung einfach False.
    v33: Modus anwendung → vom Funktionspostfach (angebot@) an dasselbe Postfach."""
    token = _token()
    if token is None:
        return False
    if modus() == MODUS_ANWENDUNG:
        empfaenger = standard_postfach()
        basis = basis_pfad("")
    else:
        app = _app()
        konten = app.get_accounts()
        if not konten:
            return False
        empfaenger = konten[0].get("username", "")
        basis = "/me"
    if not empfaenger:
        return False
    try:
        _graph_aufruf("POST", f"{basis}/sendMail", token, {
            "message": {
                "subject": betreff,
                "body": {"contentType": "text", "content": text},
                "toRecipients": [{"emailAddress": {"address": empfaenger}}],
            },
            "saveToSentItems": False,
        })
        return True
    except Exception:
        return False


def text_mail_senden(empfaenger: str, betreff: str, text: str,
                     absender: str = "") -> tuple[bool, str]:
    """Kurze Text-Mail direkt versenden (v11, Phase 69 – Benachrichtigungen).
    absender = Funktionspostfach: Modus anwendung → sendMail direkt an
    /users/<absender> (ohne Absender das Funktionspostfach des Versands); Modus
    delegiert → /me/sendMail mit from = absender („Senden als“, braucht die
    Berechtigung durch den M365-Admin). Liefert (erfolg, fehlertext) – wirft nie."""
    token = _token()
    if token is None:
        return False, nicht_verbunden_text()
    basis, von = versand_pfad(absender)
    nachricht = {
        "subject": betreff,
        "body": {"contentType": "text", "content": text},
        "toRecipients": [{"emailAddress": {"address": empfaenger}}],
    }
    if von:
        nachricht["from"] = {"emailAddress": {"address": von}}
    try:
        _graph_aufruf("POST", f"{basis}/sendMail", token,
                      {"message": nachricht, "saveToSentItems": False})
        return True, ""
    except Exception as fehler:
        return False, str(fehler)


def _rueckfall_sinnvoll(absender: str) -> bool:
    """Zweiter Versuch ohne expliziten Absender: Modus delegiert immer (angemeldetes
    Konto statt „Senden als“); Modus anwendung nur, wenn das Funktionspostfach des
    Versands (angebot@) ein anderes Postfach ist als das gescheiterte."""
    if modus() != MODUS_ANWENDUNG:
        return True
    return (absender or "").strip().lower() != standard_postfach().strip().lower()


def _anhang_daten(name: str, inhalt: bytes, mime: str, cid: str = "") -> dict:
    daten = {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "name": name,
        "contentType": mime,
        "contentBytes": base64.b64encode(inhalt).decode(),
    }
    if cid:   # v33 (PLAN_V20 Phase 176, Vorschlag N 4a): Inline-Bild der Signatur, im HTML über cid: referenziert
        daten["contentId"] = cid
        daten["isInline"] = True
    return daten


def mail_mit_anhaengen_senden(empfaenger: str, betreff: str, text: str,
                              anhaenge: list[tuple[str, bytes, str]] | None = None,
                              cc: list[str] | None = None,
                              absender: str = "") -> tuple[bool, str, str]:
    """v15 (Phase 79, Sub-Mails): Direktversand mit Anhängen als Bytes.
    Läuft über Entwurf + Einzel-Anhänge + /send, damit die conversationId
    für die Antwort-Erkennung bekannt ist. Liefert (erfolg, fehlertext,
    conversation_id) – wirft nie. v33: Modus anwendung → Entwurf und Versand
    direkt am Postfach /users/<absender> (projektierung@ …, kein from-Feld);
    schlägt das fehl, folgt ein zweiter Versuch über das Funktionspostfach des
    Versands (angebot@) bzw. im Modus delegiert über das angemeldete Postfach."""
    token = _token()
    if token is None:
        return False, nicht_verbunden_text(), ""

    def _versuch(von: str) -> tuple[bool, str, str]:
        basis, absender_feld = versand_pfad(von)
        nachricht = {
            "subject": betreff,
            "body": {"contentType": "text", "content": text},
            "toRecipients": [{"emailAddress": {"address": empfaenger}}],
        }
        if cc:
            nachricht["ccRecipients"] = [{"emailAddress": {"address": a}}
                                         for a in cc if a]
        if absender_feld:
            nachricht["from"] = {"emailAddress": {"address": absender_feld}}
        entwurf = _graph_aufruf("POST", f"{basis}/messages", token, nachricht)
        nachricht_id = entwurf["id"]
        for name, inhalt, mime in anhaenge or []:
            _graph_aufruf("POST", f"{basis}/messages/{nachricht_id}/attachments",
                          token, _anhang_daten(name, inhalt, mime))
        _graph_aufruf("POST", f"{basis}/messages/{nachricht_id}/send", token, {})
        return True, "", entwurf.get("conversationId", "")

    try:
        return _versuch(absender)
    except Exception as fehler:
        if absender and _rueckfall_sinnvoll(absender):
            try:
                return _versuch("")
            except Exception as zweiter:
                return False, f"Versand fehlgeschlagen: {zweiter}", ""
        return False, f"Versand fehlgeschlagen: {fehler}", ""


def mail_senden_als(postfach: str, empfaenger, betreff: str, html: str,
                    anhaenge: list[tuple[str, bytes, str]] | None = None,
                    cc: list[str] | None = None,
                    text_alternativ: str = "",
                    inline_bilder: list[tuple[str, bytes, str, str]] | None = None) -> tuple[bool, str, str]:
    """v33 (Vertrag G → N, Nachfass-Mail aus dem AD-Postfach): HTML-Mail aus einem
    beliebigen Postfach der Zugriffsgruppe senden – Entwurf + Anhänge + /send am Postfach
    `postfach` (Modus anwendung: /users/<postfach>). Im Modus delegiert nur erlaubt, wenn
    `postfach` leer ist oder dem angemeldeten Konto entspricht (dann /me), sonst
    (False, "Nur im Modus Anwendung …", ""). anhaenge = [(name, bytes, mime)],
    empfaenger = Adresse oder Liste; text_alternativ wird als Textkörper genommen, wenn
    html leer ist. Liefert (ok, fehler, conversation_id) – wirft nie."""
    postfach = (postfach or "").strip()
    empfaenger_liste = [empfaenger] if isinstance(empfaenger, str) else list(empfaenger or [])
    empfaenger_liste = [a.strip() for a in empfaenger_liste if a and a.strip()]
    if not empfaenger_liste:
        return False, "Kein Empfänger angegeben.", ""
    if modus() == MODUS_ANWENDUNG:
        basis = basis_pfad(postfach)
    else:
        konto = (delegiertes_konto() or "").strip().lower()
        if postfach and postfach.lower() != konto:
            return (False, f"Nur im Modus Anwendung möglich – der Versand aus dem Postfach "
                           f"{postfach} braucht den Zugriff als Anwendung (Verbindungstest "
                           "unter „Versand“).", "")
        basis = "/me"
    token = _token()
    if token is None:
        return False, nicht_verbunden_text(), ""
    if html:
        body = {"contentType": "html", "content": html}
    else:
        body = {"contentType": "text", "content": text_alternativ or ""}
    nachricht = {
        "subject": betreff,
        "body": body,
        "toRecipients": [{"emailAddress": {"address": a}} for a in empfaenger_liste],
    }
    if cc:
        nachricht["ccRecipients"] = [{"emailAddress": {"address": a}} for a in cc if a]
    try:
        entwurf = _graph_aufruf("POST", f"{basis}/messages", token, nachricht)
        nachricht_id = entwurf["id"]
        # v33 (Phase 176, N 4a): Inline-Bilder [(name, bytes, mime, cid)] vor den Dateianhängen
        for name, inhalt, mime, cid in inline_bilder or []:
            _graph_aufruf("POST", f"{basis}/messages/{nachricht_id}/attachments",
                          token, _anhang_daten(name, inhalt, mime, cid))
        for name, inhalt, mime in anhaenge or []:
            _graph_aufruf("POST", f"{basis}/messages/{nachricht_id}/attachments",
                          token, _anhang_daten(name, inhalt, mime))
        _graph_aufruf("POST", f"{basis}/messages/{nachricht_id}/send", token, {})
        return True, "", entwurf.get("conversationId", "")
    except Exception as fehler:
        ziel = postfach or "dem angemeldeten Konto"
        return False, f"Versand aus {ziel} fehlgeschlagen: {fehler}"[:500], ""


def entwurf_erstellen(kunde: Kunde, angebot: Angebot, pdf_pfad: Path,
                      betreff: str, text: str,
                      weitere_anhaenge: list[Path] | None = None,
                      fehlende_anhaenge: list[str] | None = None,
                      cc: list[str] | None = None, bcc: list[str] | None = None,
                      absender: str = "",
                      inline_bilder: list[tuple[str, Path, str]] | None = None,
                      empfaenger_leer: bool = False
                      ) -> tuple[bool, str, str, str]:
    """Legt den Entwurf mit Anhängen ab. v33 (Phase 166): Modus anwendung → im
    Funktionspostfach angebot@ (bzw. `absender`), Ordner Entwürfe – jeder Innendienstler
    sieht ihn in Outlook im eingeblendeten Postfach und sendet von dort; die Signatur
    des vorbereitenden ID-Benutzers steckt bereits im HTML (v6), CC/BCC wie bisher.
    Modus delegiert (heutiger Weg): Entwurf im Postfach des angemeldeten Mitarbeiters
    mit from = absender („Senden als“). Betreff/Text kommen aus den Vorlagen
    (Phase 30). Liefert (erfolg, meldung, weblink, conversation_id)."""
    if not kunde.email and not empfaenger_leer:
        return False, ("Der Kunde hat keine E-Mail-Adresse – bitte zuerst in der "
                       "Kundenverwaltung ergänzen."), "", ""
    token = _token()
    if token is None:
        return False, nicht_verbunden_text(), "", ""
    try:
        basis, von = versand_pfad(absender)
        nachricht = {
            "subject": betreff,
            # v6: HTML-Mail; text ist bereits fertiges HTML (Vorlage + Signatur)
            "body": {"contentType": "html", "content": text},
            # v9 (SWD-Profil): Empfänger bewusst leer lassen – der Innendienst
            # trägt den Kontakt manuell in Outlook ein
            "toRecipients": ([] if empfaenger_leer
                             else [{"emailAddress": {"address": kunde.email}}]),
        }
        if cc:
            nachricht["ccRecipients"] = [{"emailAddress": {"address": a}} for a in cc]
        if bcc:
            nachricht["bccRecipients"] = [{"emailAddress": {"address": a}} for a in bcc]
        if von:
            # „Senden als“ (Modus delegiert) – Outlook zeigt den Entwurf mit diesem Absender an
            nachricht["from"] = {"emailAddress": {"address": von}}
        entwurf = _graph_aufruf("POST", f"{basis}/messages", token, nachricht)
        nachricht_id = entwurf["id"]
        # Inline-Bilder der Signatur (v6): als CID-Anhänge, unsichtbar in der
        # Anhangsliste, referenziert über cid: im HTML
        for cid, pfad, mime in (inline_bilder or []):
            _graph_aufruf("POST", f"{basis}/messages/{nachricht_id}/attachments", token, {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": Path(pfad).name,
                "contentType": mime,
                "contentId": cid,
                "isInline": True,
                "contentBytes": base64.b64encode(Path(pfad).read_bytes()).decode(),
            })
        for pfad in [pdf_pfad] + list(weitere_anhaenge or []):
            _graph_aufruf("POST", f"{basis}/messages/{nachricht_id}/attachments", token, {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": Path(pfad).name,
                "contentBytes": base64.b64encode(Path(pfad).read_bytes()).decode(),
            })
        weblink = entwurf.get("webLink", "")
        if von:
            meldung = ("Entwurf im Postfach abgelegt – bitte in Outlook prüfen und senden. "
                       "Der Status springt nach dem Senden automatisch auf „Versendet“.")
        else:
            ziel = (absender or "").strip() or standard_postfach()
            meldung = (f"Entwurf im Postfach {ziel} (Ordner Entwürfe) abgelegt – bitte in "
                       "Outlook im eingeblendeten Postfach prüfen und von dort senden. "
                       "Der Status springt nach dem Senden automatisch auf „Versendet“.")
        if fehlende_anhaenge:
            meldung += (" Achtung, fehlende Anhang-Dateien im Ordner anlagen/: "
                        + ", ".join(fehlende_anhaenge))
        return True, meldung, weblink, entwurf.get("conversationId", "")
    except Exception as fehler:
        return False, (f"Entwurf konnte nicht erstellt werden: {fehler}. "
                       "Alternativ das PDF herunterladen und manuell versenden."), "", ""


# --- v33 (Phase 166): Verbindungs-Seite – Postfach-Liste und Verbindungstest -----------

def benoetigte_postfaecher(session) -> list[dict]:
    """Alle Postfächer, die das Tool anfasst (Abgleich mit der Zugriffsgruppe):
    Funktionspostfächer aus Einstellungen/Parametern (Angebotsversand, Versand-Erkennung,
    Lead-Mails, Lead-Parser, Projektierung, Testpostfach, gemeinsamer Montagekalender,
    Team-Kalender) und alle aktiven Benutzer mit E-Mail der Basisrollen Außendienst,
    Projektierung, Montage, Innendienst (Termine/Besetzungen → Kalender je Person);
    Handelsvertreter ohne Friondo-Postfach ausgenommen. Je Eintrag: postfach, name, art
    (funktionspostfach | mitarbeiter), pruefung (inbox | kalender), benutzer_id.
    Nur Datenbank, kein Netz."""
    from app import leadmanagement as lead_kern
    from app import projektierung as projekt_kern
    from app import rollen as rollen_modul
    from app.models import AdProfil, Benutzer, Team, einstellung_holen
    eintraege: dict[str, dict] = {}

    def merken(adresse, name: str, art: str, pruefung: str, benutzer_id=None) -> None:
        adresse = (adresse or "").strip()
        if "@" not in adresse:
            return
        schluessel = adresse.lower()
        vorhanden = eintraege.get(schluessel)
        if vorhanden is not None:
            if name not in vorhanden["name"]:
                vorhanden["name"] += " · " + name
            if vorhanden["benutzer_id"] is None:
                vorhanden["benutzer_id"] = benutzer_id
            return
        eintraege[schluessel] = {"postfach": adresse, "name": name, "art": art,
                                 "pruefung": pruefung, "benutzer_id": benutzer_id}

    merken(einstellung_holen(session, "mail_absender", STANDARD_POSTFACH) or STANDARD_POSTFACH,
           "Angebotsversand – Entwürfe und Absender", ART_FUNKTIONSPOSTFACH, "inbox")
    merken(einstellung_holen(session, "mail_postfach", STANDARD_POSTFACH) or STANDARD_POSTFACH,
           "Angebotsversand – Versand-Erkennung und Mail-Verlauf", ART_FUNKTIONSPOSTFACH, "inbox")
    merken(lead_kern.parameter_holen(session, "absender_lead_mails", "termin@friondo.de"),
           "Lead-Mails – Absender, Antworten und Unzustellbarkeitsberichte",
           ART_FUNKTIONSPOSTFACH, "inbox")
    merken(lead_kern.parameter_holen(session, "absender_postfach", "leads@friondo.de"),
           "Lead-Parser – Eingangspostfach", ART_FUNKTIONSPOSTFACH, "inbox")
    merken(projekt_kern.parameter_holen(session, "absender_postfach", "projektierung@friondo.de")
           or "projektierung@friondo.de",
           "Projektierung – Benachrichtigungen, Sub-, Termin- und BzA-Mails",
           ART_FUNKTIONSPOSTFACH, "inbox")
    merken(lead_kern.parameter_holen(session, "kalender_testpostfach", ""),
           "Testpostfach Terminassistent (Demo/Test)", ART_FUNKTIONSPOSTFACH, "kalender")
    if projekt_kern.parameter_holen(session, "outlook_kalender_modus", "postfach") == "kategorien":
        merken(projekt_kern.parameter_holen(session, "outlook_kalender_adresse", ""),
               "Gemeinsamer Montagekalender (Kategorien je Team)", ART_FUNKTIONSPOSTFACH, "kalender")
    for team in session.query(Team).filter(Team.aktiv.is_(True)).order_by(Team.name):
        merken(team.outlook_adresse, f"Team-Kalender {team.name}", ART_FUNKTIONSPOSTFACH, "kalender")
    # Mitarbeiter mit Terminen/Besetzungen (Kalender je Person, Phase 170)
    domain = standard_postfach(session).split("@")[-1].strip().lower()
    profile = {p.benutzer_id: p for p in session.query(AdProfil)}
    personen = []
    for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True)).order_by(Benutzer.name):
        email = (b.email or "").strip()
        if "@" not in email:
            continue
        if not set(b.basisrollen) & set(MITARBEITER_BASISROLLEN):
            continue
        profil = profile.get(b.id)
        adresse = email
        if profil is not None and (profil.kalender_postfach or "").strip():
            adresse = profil.kalender_postfach.strip()   # abweichendes Kalender-Postfach (v12)
        hv = (b.basisrolle == "aussendienst"
              and (b.hat_kennzeichen("handelsvertreter")
                   or bool(profil is not None and profil.terminiert_selbst)))
        if hv and not adresse.lower().endswith("@" + domain):
            continue   # Handelsvertreter ohne Friondo-Postfach (OFFEN 3 aus V4)
        personen.append((b, adresse, hv))
    for b, adresse, hv in personen:
        rolle = rollen_modul.name_von(b.rolle)
        merken(adresse, f"{b.name} ({rolle}{', Handelsvertreter' if hv and 'vertreter' not in rolle.lower() else ''})",
               ART_MITARBEITER, "kalender", b.id)
    return list(eintraege.values())


def _postfach_pruefen(token: str, eintrag: dict) -> dict:
    """Ein Postfach lesend prüfen: Funktionspostfach → Posteingangs-Ordner, Mitarbeiter →
    Kalender (jeweils nur $select=id). Netzaufruf ohne Sitzung."""
    ziel = f"/users/{urllib.parse.quote(eintrag['postfach'])}"
    if eintrag.get("pruefung") == "kalender":
        pfad = f"{ziel}/calendar?$select=id"
    else:
        pfad = f"{ziel}/mailFolders/inbox?$select=id"
    try:
        _graph_aufruf("GET", pfad, token, timeout=VERBINDUNGSTEST_TIMEOUT_S)
        return {"ok": True, "grund": ""}
    except GraphZugriffVerweigert:
        return {"ok": False, "grund": f"nicht in der Zugriffsgruppe {ZUGRIFFSGRUPPE} (HTTP 403)"}
    except urllib.error.HTTPError as fehler:
        if fehler.code == 404:
            return {"ok": False, "grund": "Postfach unbekannt (HTTP 404) – Adresse prüfen"}
        if fehler.code == 401:
            return {"ok": False, "grund": "Token abgelehnt (HTTP 401) – Berechtigungen und "
                                         "Administratorzustimmung prüfen"}
        return {"ok": False, "grund": f"HTTP {fehler.code}"}
    except Exception as fehler:   # noqa: BLE001 – Netzfehler, Timeout
        return {"ok": False, "grund": f"{type(fehler).__name__}: {fehler}"[:200]}


def verbindungstest(session) -> list[dict]:
    """Knopf „Verbindung testen“ (POST /versand/test): liest mit der Sitzung die Postfach-
    Liste, gibt die Sitzung frei, holt ein frisches Anwendungs-Token und prüft je
    Funktionspostfach den Posteingang und je Mitarbeiter den Kalender. Ergebnis je
    Postfach (postfach, ok, grund, art, name, pruefung). Danach: alle Funktionspostfächer
    grün → graph_modus = anwendung, sonst delegiert [eigene Annahme: rote Mitarbeiter-
    Postfächer (neue Mitarbeiter noch nicht in der Gruppe) werden gelistet, schalten den
    Modus aber nicht zurück – sonst würde ein fehlender Monteur den Mailversand des ganzen
    Tools auf die Rückfallebene zwingen]. Ergebnis und Zeit in der Einstellung
    graph_letzter_test."""
    from datetime import datetime
    from app.db import verbindung_freigeben
    from app.models import einstellung_setzen
    plan = benoetigte_postfaecher(session)
    verbindung_freigeben(session)
    ergebnisse: list[dict] = []
    token = None
    if not anwendung_konfiguriert():
        grund = modus_grund()
        ergebnisse = [dict(e, ok=False, grund=grund) for e in plan]
    else:
        app_token_verwerfen()
        token = _token_anwendung()
        if token is None:
            grund = f"{TEXT_ANWENDUNG_FEHLER}: {token_fehler() or 'kein Token'}"
            ergebnisse = [dict(e, ok=False, grund=grund) for e in plan]
        else:
            for eintrag in plan:
                ergebnisse.append(dict(eintrag, **_postfach_pruefen(token, eintrag)))
    pflicht = [e for e in ergebnisse if e["art"] == ART_FUNKTIONSPOSTFACH]
    gruen = bool(token) and bool(pflicht) and all(e["ok"] for e in pflicht)
    neuer_modus = modus_setzen(session, MODUS_ANWENDUNG if gruen else MODUS_DELEGIERT)
    einstellung_setzen(session, EINSTELLUNG_LETZTER_TEST, json.dumps({
        "zeit": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "modus": neuer_modus,
        "gruen": gruen,
        "ergebnisse": [{"postfach": e["postfach"], "ok": e["ok"], "grund": e["grund"],
                        "art": e["art"], "pruefung": e.get("pruefung", "")} for e in ergebnisse],
    }, ensure_ascii=False))
    session.commit()
    return ergebnisse


def letzter_test(session) -> dict | None:
    """Ergebnis des letzten Verbindungstests (Einstellung graph_letzter_test) oder None."""
    from datetime import datetime
    from app.models import einstellung_holen
    roh = einstellung_holen(session, EINSTELLUNG_LETZTER_TEST, "")
    if not roh:
        return None
    try:
        daten = json.loads(roh)
    except ValueError:
        return None
    try:
        daten["zeit_dt"] = datetime.strptime(daten.get("zeit", ""), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        daten["zeit_dt"] = None
    daten["je_postfach"] = {e["postfach"].lower(): e for e in daten.get("ergebnisse", [])}
    return daten
