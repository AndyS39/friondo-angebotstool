# Heizreport-API (v15 Phase 80 vorbereitet, V4 / PLAN_PROJ_V4 Phase 93.1 als
# generischer REST-Client; v26 / PLAN_PROJ_V5 Phasen 122–124: öffentliche
# Kunden-API v2 als Standardmodus).
#
# Modus (Parameter heizreport_modus): „v2“ (Standard) | „generisch“.
#
# Modus v2 – feste Endpunkte der öffentlichen Heizreport-Kunden-API
# (docs/heizreport/openapi.json, API-Version 2.4.0):
#   Basis-URL https://heizreport.net/api/v2, Authorization: Bearer <Token>
#   (Token = Parameter heizreport_api_key), Accept/Content-Type JSON, Timeout 20 s.
#   GET / (Version) · GET /health · GET /reports · POST /reports/with-data ·
#   GET /reports/{key} · PATCH /reports/{key} · GET /reports/{key}/results ·
#   GET /reports/{key}/pdf?type=heizreport. Nie /api/v1, nie Schlüssel raten –
#   der Schlüssel kommt immer aus projektHeader.key.
#   Ratenlimit: prozessweite Warteschlange (Lock + Zeitstempel) mit mindestens
#   600 ms Abstand; bei HTTP 429 Retry-After (mindestens 1 s) abwarten und genau
#   einmal wiederholen. Jeder fehlgeschlagene Aufruf landet im Fehlerprotokoll
#   (v22) OHNE Authorization-Header und ohne Tokenwert.
#   Weitere Parameter: heizreport_kennzahlen (JSON, Phase 123 – leer = die
#   Kennzahlen-Felder werden nicht gesendet), heizreport_pdf_ordner (Galerie-
#   Ordner für das Heizreport-PDF), heizreport_pfad_heizlast (Punktpfad zur
#   Gesamtheizlast in W in der results-Antwort), url_heizreport (Portal-Link).
#
# Modus generisch – der v17-Client bleibt unverändert erhalten:
#   heizreport_api_url, heizreport_auth_art, heizreport_auth_header,
#   heizreport_api_key, heizreport_benutzer, heizreport_pfad_*/_methode_*,
#   heizreport_mapping_hin/_zurueck (siehe docs/heizreport-api.md, Abschnitt 1).
#
# Die Heizlastberechnung selbst bleibt im Heizreport-Portal (Räume, U-Werte,
# Heizflächen); Räume per API und der Webhook sind Stufe 2.

import base64
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from app import projektierung as kern

TIMEOUT = 20
DOWNLOAD_TIMEOUT = 60
BASIS_V2 = "https://heizreport.net/api/v2"
PDF_HOST = "heizreport.net"
ABSTAND_S = 0.6                      # Mindestabstand authentifizierter Aufrufe
RETRY_AFTER_MIN_S = 1.0
MAX_BODY_BYTES = 64 * 1024
MODI = ("v2", "generisch")

PARAMETER = ("heizreport_api_url", "heizreport_auth_art", "heizreport_auth_header",
             "heizreport_api_key", "heizreport_benutzer", "heizreport_pfad_anlegen",
             "heizreport_pfad_status", "heizreport_pfad_ergebnis",
             "heizreport_methode_anlegen", "heizreport_methode_status",
             "heizreport_methode_ergebnis", "heizreport_mapping_hin",
             "heizreport_mapping_zurueck")
# v26: Parameter des Modus v2 (Token = heizreport_api_key wie bisher)
PARAMETER_V2 = ("heizreport_modus", "heizreport_kennzahlen", "heizreport_pdf_ordner",
                "heizreport_pfad_heizlast", "url_heizreport")
PDF_ORDNER_STANDARD = "Montagedokumente"
# [ANNAHME A-5] Pfad zur Gebäude-Gesamtheizlast (W) in der results-Antwort –
# die openapi.json beschreibt results.summary nur als „Zusammenfassung“; der
# Pfad ist am Referenzprojekt zu bestätigen (Parameter heizreport_pfad_heizlast).
# Löst der Pfad nicht auf, gilt die Summe der Raumheizlasten (A-5, Ersatz).
PFAD_HEIZLAST_STANDARD = "results.summary.heatLoad"
PFAD_HEIZLAST_KANDIDATEN = (
    "results.summary.heatLoad", "results.summary.totalHeatLoad",
    "results.summary.heatingLoad", "results.summary.heizlast",
    "results.summary.heatLoadTotal", "results.summary.buildingHeatLoad",
    "results.header.heatLoad", "results.header.heizlast")
PROTOKOLL_PARAMETER = "heizreport_protokoll"
PROTOKOLL_MAX = 30

MAPPING_HIN_START = json.dumps({
    "action": "aktion:createProject",
    "projekt.name": "projekt.nummer",
    "adresse.strasse": "projekt.ausfuehrung_strasse",
    "adresse.plz": "projekt.ausfuehrung_plz",
    "adresse.ort": "projekt.ausfuehrung_ort",
    "kunde.name": "kunde.anzeige_name",
    "kunde.email": "kunde.email",
    "gebaeude.art": "erfassung.O01",
    "gebaeude.baujahr": "erfassung.O02",
    "gebaeude.flaeche": "erfassung.O05",
}, ensure_ascii=False, indent=1)
MAPPING_ZURUECK_START = json.dumps({
    "projekt_key": "data.projektKey",
    "heizlast_kw": "data.heizlast",
    "status": "status",
}, indent=1)

# Kennzahlen (Phase 123): Vorlage des Parameters heizreport_kennzahlen –
# null = unbekannt = Feld wird nicht gesendet. Kein Wert ist im Code vorbelegt.
KENNZAHLEN_VORLAGE = {
    "art_heizung": {"Gas": None, "Öl": None, "Nachtspeicher": None, "Sonstiges": None},
    "verbrauch_einheit": {"Gas": None, "Öl": None, "Nachtspeicher": None, "Sonstiges": None},
    "alter_heizung": [{"bis_jahr": None, "code": None}],
    "trinkwasser": {"Ja": None, "Nein": None},
    "solar_art": {"Ja, soll übernommen werden": None, "Ja, soll stillgelegt werden": None},
}
KENNZAHLEN_FELDER = (
    ("projektArtHeizung", "art_heizung", "Heizungsart 1–6 je Energieträger (A01)"),
    ("projektJahresverbrauch", "verbrauch_einheit",
     "Verbrauch A03 nur bei bestätigter Einheit kWh je Energieträger"),
    ("projektAlterHeizung", "alter_heizung", "Altersklasse 1–3 nach Jahresgrenzen (A02)"),
    ("projektTrinkwasser", "trinkwasser", "Trinkwasser 1–3 nach N02 (Warmwasser über WP)"),
    ("projektWaermeerzeugerSolarArt", "solar_art", "Solarart 1–2 nach A10"),
)

# Nutzer-Meldungen (Phase 122, wörtlich laut Plan)
MELDUNG_401 = "Token ungültig oder Kunde gesperrt – Token in der Parametrierung prüfen"
MELDUNG_403 = "Lizenz oder Berechtigung fehlt (Heizreport-Konto prüfen)"
MELDUNG_404 = "Projekt nicht gefunden – gehört einem anderen Konto oder wurde gelöscht"
MELDUNG_NICHT_ERREICHBAR = ("Heizreport vorübergehend nicht erreichbar – später "
                            "erneut versuchen")
MELDUNG_429 = "Heizreport: Ratenlimit erreicht (HTTP 429) – später erneut versuchen"
MELDUNG_TOKEN_ABGELEHNT = "Heizreport erreichbar, aber Token abgelehnt (HTTP 401)"
MELDUNG_NICHT_BERECHENBAR = ("Heizreport-Projekt noch nicht berechenbar – Räume und "
                             "Heizflächen im Heizreport-Portal erfassen, dann erneut "
                             "abrufen")
MELDUNG_ANLAGE_UNKLAR = ("Anlage unklar – im Heizreport-Portal prüfen, dann Schlüssel "
                         "von Hand eintragen")
MELDUNG_PDF_RUECKFRAGE = ("Bei Heizreport wird ein weiteres Dokument erzeugt – trotzdem "
                          "erneut abrufen?")
MELDUNG_OHNE_PLZ = "Ausführungsort ohne PLZ – Ausführungsort am Projekt ergänzen"
HV_ERGEBNIS_QUELLE = "Heizreport API"
VERLAUF_ART_HINWEIS = "hinweis"

_sperre = threading.Lock()
_letzter_aufruf = [0.0]


def p(session, name: str, standard: str = "") -> str:
    return kern.parameter_holen(session, name, standard).strip()


def modus(session) -> str:
    wert = p(session, "heizreport_modus", "v2").lower()
    return wert if wert in MODI else "v2"


def token(session) -> str:
    return p(session, "heizreport_api_key")


def konfiguriert(session) -> bool:
    """v2: Token gesetzt; generisch: Basis-URL + Schlüssel."""
    if modus(session) == "v2":
        return bool(token(session))
    return bool(p(session, "heizreport_api_url") and p(session, "heizreport_api_key"))


# --- Uhr / Warteschlange (testbar: _uhr und _schlafen werden gepatcht) --------------

def _uhr() -> float:
    return time.monotonic()


def _schlafen(sekunden: float) -> None:
    time.sleep(sekunden)


def _warten() -> None:
    """Prozessweite Warteschlange: authentifizierte Aufrufe mit mindestens
    ABSTAND_S Abstand (Lock hält die Reihenfolge, der Zeitstempel den Abstand)."""
    with _sperre:
        jetzt = _uhr()
        rest = _letzter_aufruf[0] + ABSTAND_S - jetzt
        if rest > 0:
            _schlafen(rest)
        _letzter_aufruf[0] = _uhr()


# --- HTTP (eine Nahtstelle für Tests: _roh_anfrage) ------------------------------------

def _roh_anfrage(methode: str, url: str, kopf: dict, koerper: bytes | None,
                 timeout: float) -> tuple[int, bytes, dict]:
    """Ein HTTP-Aufruf; liefert (Status, Body-Bytes, Antwort-Header). Wirft nie –
    Netzfehler/Timeout werden zu Status 0 mit dem Fehlertext als Body."""
    anfrage = urllib.request.Request(url, data=koerper, headers=kopf,
                                     method=methode.upper())
    try:
        with urllib.request.urlopen(anfrage, timeout=timeout) as antwort:
            return antwort.status, antwort.read(), dict(antwort.headers or {})
    except urllib.error.HTTPError as fehler:
        try:
            body = fehler.read()
        except Exception:
            body = b""
        return fehler.code, body, dict(fehler.headers or {})
    except Exception as fehler:          # Netz, DNS, Timeout
        return 0, str(fehler).encode("utf-8", "replace"), {}


def _json_oder_text(body: bytes):
    text = (body or b"").decode("utf-8", "replace")
    try:
        return json.loads(text)
    except ValueError:
        return text[:500]


def _retry_after(kopf: dict, antwort) -> float:
    sekunden = RETRY_AFTER_MIN_S
    for name, wert in (kopf or {}).items():
        if str(name).lower() == "retry-after":
            try:
                sekunden = max(sekunden, float(str(wert).strip()))
            except ValueError:
                pass
    if isinstance(antwort, dict):
        try:
            sekunden = max(sekunden, float((antwort.get("details") or {}).get("retryAfter") or 0))
        except (TypeError, ValueError):
            pass
    return sekunden


def _maskieren(text: str, geheim: str) -> str:
    text = str(text or "")
    if geheim and geheim in text:
        text = text.replace(geheim, "***")
    return text


def _protokollieren(session, methode: str, url: str, status: int, antwort) -> None:
    """Fehlgeschlagener Aufruf → Fehlerprotokoll (v22), ohne Authorization-Header
    und ohne Tokenwert. Wirft nie."""
    try:
        from app import fehlerprotokoll
        geheim = token(session)
        auszug = (json.dumps(antwort, ensure_ascii=False) if isinstance(antwort, dict)
                  else str(antwort))[:500]
        fehlerprotokoll.eintragen_text(
            "Heizreport", f"{methode.upper()} {url} → HTTP {status}",
            _maskieren(auszug, geheim), pfad=urllib.parse.urlsplit(url).path[:300])
    except Exception:
        pass


def _anfrage_v2(session, methode: str, pfad: str, daten: dict | None = None,
                query: dict | None = None, mit_token: bool = True) -> tuple[int, object]:
    """Authentifizierter v2-Aufruf über die Warteschlange; 429 → Retry-After
    abwarten und genau einmal wiederholen. Liefert (Status, JSON oder Text)."""
    url = BASIS_V2.rstrip("/") + "/" + pfad.lstrip("/") if pfad not in ("", "/") else BASIS_V2
    if query:
        url += "?" + urllib.parse.urlencode(query)
    kopf = {"Accept": "application/json"}
    geheim = token(session) if mit_token else ""
    if geheim:
        kopf["Authorization"] = f"Bearer {geheim}"
    koerper = None
    if daten is not None:
        koerper = json.dumps(daten, ensure_ascii=False).encode("utf-8")
        kopf["Content-Type"] = "application/json"
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Token und Body
    # sind gelesen; Warteschlange + Timeout 20 s dürfen keine Pool-Verbindung halten)
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    status = 0
    antwort = ""
    for versuch in (1, 2):
        if mit_token:
            _warten()
        status, body, antwort_kopf = _roh_anfrage(methode, url, kopf, koerper, TIMEOUT)
        antwort = _json_oder_text(body)
        if status != 429:
            break
        if versuch == 1:
            _schlafen(_retry_after(antwort_kopf, antwort))
    if status == 0 or status >= 400:
        _protokollieren(session, methode, url, status, antwort)
    return status, antwort


def fehler_meldung(status: int, antwort) -> str:
    """Nutzer-Meldung aus Status + Fehlerblock {status, error, details}."""
    fehler = antwort.get("error") if isinstance(antwort, dict) else ""
    details = antwort.get("details") if isinstance(antwort, dict) else {}
    feld = (details or {}).get("field") if isinstance(details, dict) else ""
    if status == 401:
        return f"Heizreport: {MELDUNG_401}"
    if status == 403:
        return f"Heizreport: {MELDUNG_403}"
    if status == 404:
        return f"Heizreport: {MELDUNG_404}"
    if status == 429:
        return MELDUNG_429
    if status == 0 or status >= 500:
        return MELDUNG_NICHT_ERREICHBAR
    text = str(fehler or (antwort if isinstance(antwort, str) else "") or f"HTTP {status}")[:300]
    if feld:
        return f"Heizreport: {text} (Feld {feld})"
    return f"Heizreport: {text}"


# --- Verbindungstest -------------------------------------------------------------------

def _verbindung_testen_v2(session) -> tuple[bool, str]:
    status, health = _anfrage_v2(session, "GET", "/health", mit_token=False)
    if status != 200:
        return False, fehler_meldung(status, health)
    status, info = _anfrage_v2(session, "GET", "/", mit_token=False)
    version = (info.get("version") if isinstance(info, dict) else "") or "?"
    status, liste = _anfrage_v2(session, "GET", "/reports")
    if status == 401:
        return False, MELDUNG_TOKEN_ABGELEHNT
    if status != 200 or not isinstance(liste, dict):
        return False, fehler_meldung(status, liste)
    gruppen = {g: len(liste.get(g) or []) for g in ("projekte", "leads", "api", "archiv")}
    return True, (f"Verbindung OK · API-Version {version} · {sum(gruppen.values())} eigene "
                  f"Projekte (Gruppen: projekte {gruppen['projekte']}, leads {gruppen['leads']}, "
                  f"api {gruppen['api']}, archiv {gruppen['archiv']})")


def verbindung_testen(session) -> tuple[bool, str]:
    """Button „Verbindung testen“: v2 = Health → Version → Projektliste;
    generisch = GET auf die Basis-URL mit Auth."""
    if modus(session) == "v2":
        return _verbindung_testen_v2(session)
    if not p(session, "heizreport_api_url"):
        return False, "Keine Basis-URL hinterlegt."
    status, antwort = _anfrage(session, p(session, "heizreport_api_url"), "GET")
    auszug = (json.dumps(antwort, ensure_ascii=False) if isinstance(antwort, dict)
              else str(antwort))[:200]
    if status == 0:
        return False, f"Keine Verbindung: {auszug}"
    return 200 <= status < 500, f"HTTP {status} – {auszug}"


# --- Generischer Client (v17) – unverändert ------------------------------------------

def _url(session, pfad_name: str, projekt_key: str = "") -> str:
    basis = p(session, "heizreport_api_url")
    pfad = p(session, pfad_name).replace("{projekt_key}", projekt_key or "")
    if not pfad:
        return basis
    return basis.rstrip("/") + "/" + pfad.lstrip("/")


def _anfrage(session, url: str, methode: str = "GET",
             daten: dict | None = None) -> tuple[int, dict | str]:
    """HTTP-Aufruf mit konfigurierter Auth (Modus generisch); liefert (Status,
    JSON oder Text). Wirft nie – Netzfehler werden zu Status 0 mit Fehlertext."""
    art = (p(session, "heizreport_auth_art", "header") or "header").lower()
    schluessel = p(session, "heizreport_api_key")
    kopf = {"Accept": "application/json"}
    daten = dict(daten or {})
    if art == "bearer":
        kopf["Authorization"] = f"Bearer {schluessel}"
    elif art == "basic":
        roh = f"{p(session, 'heizreport_benutzer')}:{schluessel}".encode()
        kopf["Authorization"] = "Basic " + base64.b64encode(roh).decode()
    elif art == "body":
        daten[p(session, "heizreport_auth_header", "apiKey") or "apiKey"] = schluessel
    else:
        kopf[p(session, "heizreport_auth_header", "X-API-Key") or "X-API-Key"] = schluessel
    koerper = None
    if methode.upper() != "GET" or (art == "body" and daten):
        koerper = json.dumps(daten, ensure_ascii=False).encode("utf-8")
        kopf["Content-Type"] = "application/json"
    anfrage = urllib.request.Request(url, data=koerper, headers=kopf,
                                     method=methode.upper())
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    try:
        with urllib.request.urlopen(anfrage, timeout=TIMEOUT) as antwort:
            status, text = antwort.status, antwort.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as fehler:
        status, text = fehler.code, fehler.read().decode("utf-8", "replace")
    except Exception as fehler:   # Netz, DNS, Timeout
        return 0, str(fehler)
    try:
        return status, json.loads(text)
    except ValueError:
        return status, text[:500]


def _json_parameter(session, name: str, start: str) -> dict:
    try:
        wert = json.loads(p(session, name) or start)
        return wert if isinstance(wert, dict) else {}
    except ValueError:
        return {}


def _quelle(session, gewerk, quelle: str):
    from app.models import Kunde, Projekt
    quelle = (quelle or "").strip()
    if quelle.startswith("fest:"):
        return quelle[5:]
    if quelle.startswith("aktion:"):
        return quelle[7:]
    objekt, _, feld = quelle.partition(".")
    projekt = session.get(Projekt, gewerk.projekt_id)
    if objekt == "projekt":
        return getattr(projekt, feld, None) if projekt else None
    if objekt == "kunde":
        kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
        return getattr(kunde, feld, None) if kunde else None
    if objekt == "gewerk":
        return getattr(gewerk, feld, None)
    if objekt == "steckbrief":
        werte = kern.steckbrief_daten(session, [gewerk.id])[gewerk.id]
        return werte[feld].wert if feld in werte else None
    if objekt == "fp":
        return kern.fp_antworten(gewerk).get(feld)
    if objekt == "erfassung":
        antworten, _pos, _prof = kern._steckbrief_quellen(session, gewerk)
        return antworten.get(feld)
    return None


def _setzen(ziel: dict, pfad: str, wert) -> None:
    teile = [t for t in pfad.split(".") if t]
    for teil in teile[:-1]:
        ziel = ziel.setdefault(teil, {})
    if teile:
        ziel[teile[-1]] = wert


def _lesen(daten, pfad: str):
    for teil in [t for t in (pfad or "").split(".") if t]:
        if isinstance(daten, dict):
            daten = daten.get(teil)
        elif isinstance(daten, list) and teil.isdigit() and int(teil) < len(daten):
            daten = daten[int(teil)]
        else:
            return None
    return daten


def daten_hin(session, gewerk) -> dict:
    daten: dict = {}
    for ziel, quelle in _json_parameter(session, "heizreport_mapping_hin",
                                        MAPPING_HIN_START).items():
        wert = _quelle(session, gewerk, str(quelle))
        if wert not in (None, ""):
            _setzen(daten, ziel, wert if isinstance(wert, (int, float)) else str(wert))
    return daten


def _projekt_anlegen_generisch(session, gewerk, benutzer=None) -> tuple[bool, str]:
    status, antwort = _anfrage(session, _url(session, "heizreport_pfad_anlegen"),
                               p(session, "heizreport_methode_anlegen", "POST") or "POST",
                               daten_hin(session, gewerk))
    if not 200 <= status < 300:
        return False, f"Heizreport: Anlage fehlgeschlagen (HTTP {status}): {str(antwort)[:200]}"
    zurueck = _json_parameter(session, "heizreport_mapping_zurueck", MAPPING_ZURUECK_START)
    schluessel = (_lesen(antwort, zurueck.get("projekt_key", ""))
                  if isinstance(antwort, dict) else None)
    if schluessel in (None, ""):
        return False, ("Heizreport: Projekt angelegt, aber kein Projekt-Schlüssel in der "
                       "Antwort – Mapping „projekt_key“ prüfen.")
    gewerk.heizreport_projekt_key = str(schluessel)[:60]
    gewerk.heizreport_angelegt_am = datetime.now()
    kern.verlauf(session, gewerk.projekt_id,
                 f"Heizreport-Projekt angelegt (Schlüssel {gewerk.heizreport_projekt_key})",
                 benutzer=benutzer, gewerk_id=gewerk.id)
    session.flush()
    return True, f"Heizreport-Projekt {gewerk.heizreport_projekt_key} angelegt."


def _ergebnis_holen_generisch(session, gewerk, benutzer=None) -> tuple[bool, str, float | None]:
    status, antwort = _anfrage(
        session, _url(session, "heizreport_pfad_ergebnis", gewerk.heizreport_projekt_key),
        p(session, "heizreport_methode_ergebnis", "GET") or "GET",
        {"projektKey": gewerk.heizreport_projekt_key})
    if not 200 <= status < 300 or not isinstance(antwort, dict):
        return (False, f"Heizreport: Abruf fehlgeschlagen (HTTP {status}): "
                       f"{str(antwort)[:200]}", None)
    zurueck = _json_parameter(session, "heizreport_mapping_zurueck", MAPPING_ZURUECK_START)
    roh = _lesen(antwort, zurueck.get("heizlast_kw", ""))
    try:
        kw = float(str(roh).replace(",", "."))
    except (TypeError, ValueError):
        return False, ("Heizreport: noch keine Heizlast im Ergebnis (Projekt beim Kunden "
                       "noch offen?) – Mapping „heizlast_kw“ prüfen."), None
    _heizlast_uebernehmen(session, gewerk, kw, benutzer)
    text = f"{kw:g}".replace(".", ",")
    kern.verlauf(session, gewerk.projekt_id, f"Heizlast aus Heizreport übernommen: {text} kW",
                 benutzer=benutzer, gewerk_id=gewerk.id)
    session.flush()
    return True, f"Heizlast {text} kW übernommen.", kw


# --- Kennzahlen (Phase 123) ---------------------------------------------------------------

def kennzahlen_roh(session) -> str:
    return p(session, "heizreport_kennzahlen")


def kennzahlen(session) -> dict:
    """Parameter heizreport_kennzahlen als dict (Vorlage-Struktur, fehlende
    Teile leer). Ungültiges JSON → leer (= nichts wird gesendet)."""
    roh = kennzahlen_roh(session)
    if not roh:
        return {}
    try:
        wert = json.loads(roh)
    except ValueError:
        return {}
    return wert if isinstance(wert, dict) else {}


def kennzahlen_pruefen(text: str) -> str:
    """Validierung der Eingabe in der Parametrierung: leer erlaubt, sonst ein
    JSON-Objekt; Codes müssen Zahlen/null sein, Einheiten kWh/l/m3/null.
    Liefert einen Fehlertext oder „“."""
    text = (text or "").strip()
    if not text:
        return ""
    try:
        wert = json.loads(text)
    except ValueError as fehler:
        return f"Kennzahlen: kein gültiges JSON ({fehler})"
    if not isinstance(wert, dict):
        return "Kennzahlen: oberste Ebene muss ein JSON-Objekt sein"
    for schluessel in ("art_heizung", "trinkwasser", "solar_art"):
        block = wert.get(schluessel)
        if block is not None and not isinstance(block, dict):
            return f"Kennzahlen: „{schluessel}“ muss ein Objekt sein"
        for k, v in (block or {}).items():
            if v is not None and not isinstance(v, (int, float)) and not str(v).strip().isdigit():
                return f"Kennzahlen: „{schluessel}.{k}“ muss eine Zahl oder null sein"
    einheiten = wert.get("verbrauch_einheit")
    if einheiten is not None and not isinstance(einheiten, dict):
        return "Kennzahlen: „verbrauch_einheit“ muss ein Objekt sein"
    for k, v in (einheiten or {}).items():
        if v is not None and str(v).strip() not in ("kWh", "l", "m3"):
            return f"Kennzahlen: „verbrauch_einheit.{k}“ muss kWh, l, m3 oder null sein"
    alter = wert.get("alter_heizung")
    if alter is not None and not isinstance(alter, list):
        return "Kennzahlen: „alter_heizung“ muss eine Liste von {bis_jahr, code} sein"
    for eintrag in alter or []:
        if not isinstance(eintrag, dict):
            return "Kennzahlen: Einträge in „alter_heizung“ müssen Objekte sein"
    return ""


def _code(block, schluessel: str):
    """Kennzahl aus einem Block (Zahl/numerischer Text), None = unbekannt."""
    if not isinstance(block, dict):
        return None
    wert = block.get(schluessel)
    if wert is None or str(wert).strip() == "":
        return None
    try:
        return int(str(wert).strip())
    except ValueError:
        return None


def _alterscode(liste, jahr: int | None):
    if jahr is None or not isinstance(liste, list):
        return None
    eintraege = []
    for e in liste:
        if not isinstance(e, dict) or e.get("code") is None:
            continue
        bis = e.get("bis_jahr")
        try:
            bis = int(bis) if bis not in (None, "") else None
            code = int(e.get("code"))
        except (TypeError, ValueError):
            continue
        eintraege.append((bis, code))
    for bis, code in sorted(eintraege, key=lambda t: (t[0] is None, t[0] or 0)):
        if bis is None or jahr <= bis:
            return code
    return None


def kennzahlen_vorschau(session) -> list[dict]:
    """Für die Parametrierung: welche API-Felder würden derzeit gesendet?"""
    kz = kennzahlen(session)
    zeilen = []
    for feld, block, erklaerung in KENNZAHLEN_FELDER:
        werte = kz.get(block)
        if block == "alter_heizung":
            aktiv = [e for e in (werte or []) if isinstance(e, dict) and e.get("code") is not None]
            text = (", ".join(f"bis {e.get('bis_jahr') or '∞'} → {e.get('code')}" for e in aktiv)
                    if aktiv else "")
        elif block == "verbrauch_einheit":
            aktiv = {k: v for k, v in (werte or {}).items() if v}
            text = ", ".join(f"{k}: {v}" for k, v in aktiv.items()) if aktiv else ""
            if aktiv and "kWh" not in aktiv.values():
                text += " (nur kWh wird gesendet – l/m3 bleiben Klartext)"
        else:
            aktiv = {k: v for k, v in (werte or {}).items() if v is not None and str(v).strip() != ""}
            text = ", ".join(f"{k} → {v}" for k, v in aktiv.items()) if aktiv else ""
        zeilen.append({"feld": feld, "erklaerung": erklaerung,
                       "gesendet": bool(text), "text": text or "wird nicht gesendet (Kennzahl unbekannt)"})
    return zeilen


# --- Datenaufbereitung v2 (Phase 123) -----------------------------------------------------

_HAUSNUMMER = re.compile(r"^(?P<strasse>.*?\S)[\s,]+(?P<nr>\d+\s*[a-zA-Z]?(?:\s*[-–/]\s*\d+\s*[a-zA-Z]?)?)\s*$")


def strasse_trennen(text: str) -> tuple[str, str]:
    """[ANNAHME A-2] Straße und Hausnummer trennen: letzter Block aus Ziffer +
    optionalem Buchstaben/Zusatz (12, 12a, 12-14) = Hausnummer, Rest = Straße;
    nicht trennbar → alles in strasse."""
    text = " ".join((text or "").split())
    if not text:
        return "", ""
    m = _HAUSNUMMER.match(text)
    if not m:
        return text, ""
    nr = re.sub(r"\s+", "", m.group("nr"))
    return m.group("strasse").strip(" ,"), nr


def _zahl(text) -> float | None:
    if text in (None, ""):
        return None
    try:
        return float(str(text).strip().replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _jahr(text) -> int | None:
    zahl = _zahl(text)
    if zahl is None:
        return None
    jahr = int(zahl)
    return jahr if 1000 <= jahr <= 2100 else None


def _steckbrief_wert(session, gewerk, feld: str) -> str:
    werte = kern.steckbrief_daten(session, [gewerk.id]).get(gewerk.id, {})
    return (werte[feld].wert or "").strip() if feld in werte else ""


def projektdaten_v2(session, gewerk) -> dict:
    """Body {"projectData": {…}} für POST /reports/with-data (nur skalare
    Werte, leere Werte weggelassen). Feldbelegung laut Plan Phase 123; die
    Kennzahlen-Felder nur über den Parameter heizreport_kennzahlen."""
    from app.models import Angebot, Kunde, Projekt
    projekt = session.get(Projekt, gewerk.projekt_id)
    kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
    angebot = session.get(Angebot, gewerk.angebot_id) if gewerk.angebot_id else None
    antworten, _pos, _prof = kern._steckbrief_quellen(session, gewerk)
    kz = kennzahlen(session)
    d: dict = {}

    def text(wert) -> str:
        return " ".join(str(wert).split()) if wert not in (None, "") else ""

    nachname = text(getattr(kunde, "nachname", ""))
    vorname = text(getattr(kunde, "vorname", ""))
    name_teile = ", ".join(t for t in (nachname, vorname) if t)
    pr = text(getattr(projekt, "nummer", ""))
    d["projektName"] = (f"{name_teile} – {pr}" if name_teile and pr else name_teile or pr)[:120]
    plz = text(getattr(projekt, "ausfuehrung_plz", ""))
    if plz:
        d["projektPostleitzahl"] = plz
    baujahr = _jahr(antworten.get("O02"))
    if baujahr is not None:
        d["projektBaujahr"] = baujahr
    a01 = text(antworten.get("A01"))
    a02 = text(antworten.get("A02"))
    a03 = text(antworten.get("A03"))
    a10 = text(antworten.get("A10"))
    n02 = text(antworten.get("N02"))
    a14 = text(antworten.get("A14"))
    a15 = text(antworten.get("A15"))
    # Kennzahlen – nur wenn im Parameter bestätigt, sonst weglassen (Klartext in bemerkungen)
    code = _code(kz.get("art_heizung"), a01) if a01 else None
    if code is not None:
        d["projektArtHeizung"] = code
    einheit = (kz.get("verbrauch_einheit") or {}).get(a01) if a01 else None
    verbrauch = _zahl(a03)
    if einheit == "kWh" and verbrauch is not None:
        # [ANNAHME A-3] nur kWh wird unverändert gesendet; l/m3 nicht umgerechnet
        d["projektJahresverbrauch"] = int(verbrauch) if verbrauch == int(verbrauch) else verbrauch
    alter = _alterscode(kz.get("alter_heizung"), _jahr(a02))
    if alter is not None:
        d["projektAlterHeizung"] = alter
    tw = _code(kz.get("trinkwasser"), n02) if n02 else None
    if tw is not None:
        d["projektTrinkwasser"] = tw
    if a10.startswith("Ja"):
        d["projektWaermeerzeugerSolarStatus"] = True
        solar = _code(kz.get("solar_art"), a10)
        if solar is not None:
            d["projektWaermeerzeugerSolarArt"] = solar
    # Kunde
    for api_feld, attr in (("anrede", "anrede"), ("vorname", "vorname"), ("name", "nachname"),
                           ("telefon", "telefon"), ("email", "email")):
        wert = text(getattr(kunde, attr, ""))
        if wert:
            d[api_feld] = wert
    # Ausführungsort (Adresse)
    strasse, hausnummer = strasse_trennen(getattr(projekt, "ausfuehrung_strasse", ""))
    if strasse:
        d["strasse"] = strasse
    if hausnummer:
        d["hausnummer"] = hausnummer
    if plz:
        d["plz"] = plz
    ort = text(getattr(projekt, "ausfuehrung_ort", ""))
    if ort:
        d["ort"] = ort
    # Bemerkungen (wörtlich laut Plan, Teile ohne Wert entfallen)
    teile = []
    if pr:
        teile.append(f"Friondo {pr}")
    if angebot is not None and angebot.nummer:
        teile.append(f"Angebot {angebot.nummer}")
    klasse = _steckbrief_wert(session, gewerk, "leistungsklasse")
    if klasse:
        teile.append(f"verkauft: {klasse}")
    alt = []
    if a01:
        alt.append(f"Energieträger alt: {a01}")
    if a02:
        alt.append(f"Baujahr Heizung {a02}")
    if verbrauch is not None:
        alt.append(f"Verbrauch {a03} kWh")
    if alt:
        teile.append(", ".join(alt))
    if n02:
        teile.append(f"Warmwasser über WP: {n02}")
    if a10:
        teile.append(f"Solarthermie: {a10}")
    if a14 == "Ja" and a15:
        teile.append(f"Heizlast lt. Erfassung: {a15} kW")
    if teile:
        d["bemerkungen"] = " · ".join(teile)
    return {"projectData": d}


def gesendete_felder(body: dict) -> list[str]:
    return sorted((body or {}).get("projectData", {}).keys())


# --- Aktionen an der Aufgabe „Heizlastberechnung liegt vor“ ------------------------------

_SCHLUESSEL = re.compile(r"^[A-Za-z]{9}$")


def _aufgaben_erledigen(session, gewerk, benutzer=None) -> None:
    from app.models import Aufgabe
    for aufgabe in (session.query(Aufgabe)
                    .filter(Aufgabe.gewerk_id == gewerk.id, Aufgabe.aktion_typ == "api",
                            Aufgabe.aktion_wert == "heizreport",
                            Aufgabe.status != "erledigt")):
        aufgabe.status = "erledigt"
        aufgabe.erledigt_am = datetime.now()
        aufgabe.erledigt_von = benutzer.id if benutzer else None


def projekt_anlegen(session, gewerk, benutzer=None) -> tuple[bool, str]:
    """Projekt im Heizreport anlegen (v2: POST /reports/with-data, Erfolg =
    HTTP 201, Schlüssel aus projektHeader.key). Nicht idempotent: bei Timeout
    kein zweiter POST, sondern Suche in GET /reports nach projektName."""
    if not konfiguriert(session):
        return False, ("Heizreport-API nicht konfiguriert – Token unter Parametrierung → "
                       "Heizreport hinterlegen.")
    if modus(session) != "v2":
        return _projekt_anlegen_generisch(session, gewerk, benutzer)
    if gewerk.heizreport_projekt_key:
        return False, (f"Heizreport-Projekt {gewerk.heizreport_projekt_key} ist bereits "
                       "verknüpft – zuerst die Verknüpfung lösen.")
    body = projektdaten_v2(session, gewerk)
    if not body["projectData"].get("projektPostleitzahl"):
        return False, MELDUNG_OHNE_PLZ
    if len(json.dumps(body, ensure_ascii=False).encode("utf-8")) >= MAX_BODY_BYTES:
        return False, "Heizreport: Projektdaten zu groß (über 64 KiB)"
    status, antwort = _anfrage_v2(session, "POST", "/reports/with-data", body)
    if status == 201 and isinstance(antwort, dict):
        schluessel = str(((antwort.get("projektHeader") or {}).get("key")) or "").strip()
        if not _SCHLUESSEL.match(schluessel):
            return False, ("Heizreport: Projekt angelegt, aber kein gültiger Schlüssel in "
                           "projektHeader.key – im Portal prüfen und Schlüssel eintragen.")
        gewerk.heizreport_projekt_key = schluessel
        gewerk.heizreport_angelegt_am = datetime.now()
        felder = ", ".join(gesendete_felder(body))
        kern.verlauf(session, gewerk.projekt_id,
                     f"Heizreport-Projekt {schluessel} angelegt (vorbelegt: {felder})",
                     benutzer=benutzer, gewerk_id=gewerk.id)
        session.flush()
        return True, f"Heizreport-Projekt {schluessel} angelegt."
    if status == 0:
        gesucht = body["projectData"].get("projektName", "")
        status2, liste = _anfrage_v2(session, "GET", "/reports")
        treffer = _projekt_suchen(liste, gesucht) if status2 == 200 else ""
        if treffer:
            gewerk.heizreport_projekt_key = treffer
            gewerk.heizreport_angelegt_am = datetime.now()
            kern.verlauf(session, gewerk.projekt_id,
                         f"Heizreport-Projekt {treffer} nach Timeout gefunden",
                         benutzer=benutzer, gewerk_id=gewerk.id)
            session.flush()
            return True, f"Heizreport-Projekt {treffer} nach Timeout gefunden."
        return False, MELDUNG_ANLAGE_UNKLAR
    return False, fehler_meldung(status, antwort)


def _projekt_suchen(liste, projekt_name: str) -> str:
    if not isinstance(liste, dict) or not projekt_name:
        return ""
    for gruppe in ("projekte", "leads", "api", "archiv"):
        for eintrag in liste.get(gruppe) or []:
            if isinstance(eintrag, dict) and str(eintrag.get("projektName") or "") == projekt_name:
                schluessel = str(eintrag.get("projektKey") or "")
                if _SCHLUESSEL.match(schluessel):
                    return schluessel
    return ""


def schluessel_eintragen(session, gewerk, schluessel: str, benutzer=None) -> tuple[bool, str]:
    """Schlüssel von Hand (9 Buchstaben), geprüft über GET /reports/{key}."""
    schluessel = (schluessel or "").strip()
    if not _SCHLUESSEL.match(schluessel):
        return False, "Schlüssel abgelehnt – ein Heizreport-Schlüssel hat genau 9 Buchstaben."
    if gewerk.heizreport_projekt_key:
        return False, (f"Heizreport-Projekt {gewerk.heizreport_projekt_key} ist bereits "
                       "verknüpft – zuerst die Verknüpfung lösen.")
    if not konfiguriert(session) or modus(session) != "v2":
        return False, "Heizreport-API (v2) nicht konfiguriert."
    status, antwort = _anfrage_v2(session, "GET", f"/reports/{schluessel}")
    if status == 404:
        return False, f"Schlüssel abgelehnt – {MELDUNG_404}"
    if status != 200:
        return False, fehler_meldung(status, antwort)
    gewerk.heizreport_projekt_key = schluessel
    gewerk.heizreport_angelegt_am = datetime.now()
    kern.verlauf(session, gewerk.projekt_id,
                 f"Heizreport-Schlüssel {schluessel} von Hand eingetragen",
                 benutzer=benutzer, gewerk_id=gewerk.id)
    session.flush()
    return True, f"Heizreport-Projekt {schluessel} verknüpft."


def verknuepfung_loesen(session, gewerk, begruendung: str, benutzer=None) -> tuple[bool, str]:
    begruendung = " ".join((begruendung or "").split())
    if not begruendung:
        return False, "Begründung ist Pflicht."
    if not gewerk.heizreport_projekt_key:
        return False, "Kein Heizreport-Projekt verknüpft."
    alt = gewerk.heizreport_projekt_key
    gewerk.heizreport_projekt_key = None
    gewerk.heizreport_angelegt_am = None
    kern.verlauf(session, gewerk.projekt_id,
                 f"Heizreport-Verknüpfung gelöst: {begruendung}"
                 + f" (bisher {alt})",
                 benutzer=benutzer, gewerk_id=gewerk.id)
    session.flush()
    return True, f"Verknüpfung zu Heizreport-Projekt {alt} gelöst."


# --- Heizlast zurückholen, Abgleich (Phase 124) --------------------------------------------

def kw_runden(watt: float) -> float:
    return float(Decimal(str(watt / 1000.0)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _numerisch(wert) -> float | None:
    if isinstance(wert, bool):
        return None
    if isinstance(wert, (int, float)):
        return float(wert)
    if isinstance(wert, str):
        try:
            return float(wert.strip().replace(",", "."))
        except ValueError:
            return None
    return None


_RAUM_SCHLUESSEL = ("heatLoad", "heatingLoad", "heizlast", "heatLoadTotal", "total", "value")


def _raum_heizlast(eintrag) -> float | None:
    if isinstance(eintrag, dict):
        for schluessel in _RAUM_SCHLUESSEL:
            if schluessel in eintrag:
                zahl = _numerisch(eintrag[schluessel])
                if zahl is not None:
                    return zahl
        return None
    return _numerisch(eintrag)


def _raumsumme(results) -> float | None:
    """[ANNAHME A-5] Ersatz: Summe der Raumheizlasten in W aus den Raumstrukturen
    (results.roomHeatLoads, sonst results.floorHeatingBalance.groups[].rooms[])."""
    if not isinstance(results, dict):
        return None
    raeume = results.get("roomHeatLoads")
    werte = []
    if isinstance(raeume, list):
        werte = [w for w in (_raum_heizlast(r) for r in raeume) if w is not None]
    elif isinstance(raeume, dict):
        werte = [w for w in (_raum_heizlast(r) for r in raeume.values()) if w is not None]
    if werte:
        return float(sum(werte))
    fbh = results.get("floorHeatingBalance")
    if isinstance(fbh, dict):
        werte = [_numerisch(r.get("heatingLoad"))
                 for g in (fbh.get("groups") or []) if isinstance(g, dict)
                 for r in (g.get("rooms") or []) if isinstance(r, dict)]
        werte = [w for w in werte if w is not None]
        if werte:
            return float(sum(werte))
    return None


def heizlast_aus_ergebnis(antwort: dict, pfad: str = "") -> tuple[float | None, str]:
    """Gesamtheizlast des Gebäudes in W aus der results-Antwort: zuerst der
    konfigurierte Punktpfad, dann die bekannten Kandidaten, zuletzt die
    Raumsumme [A-5]. Liefert (Watt, Herkunft)."""
    if not isinstance(antwort, dict):
        return None, ""
    for kandidat in [pfad] + [k for k in PFAD_HEIZLAST_KANDIDATEN if k != pfad]:
        if not kandidat:
            continue
        zahl = _numerisch(_lesen(antwort, kandidat))
        if zahl is not None and zahl > 0:
            return zahl, kandidat
    summe = _raumsumme(antwort.get("results"))
    if summe is not None and summe > 0:
        return summe, "Summe der Raumheizlasten"
    return None, ""


def klasse_fuer_heizlast(session, kw: float):
    """Leistungsklasse laut Paketmatrix (Heizlast-Spalte, dieselbe Zuordnung
    wie konfigurator.leistungsklasse; die Heizlast-Spalte ist die
    Unterdimensionierungs-Matrix aus v8). None = keine Zeile passt."""
    from app import logik as logik_modul
    logik, _bericht = logik_modul.hole_logik(session)
    for zeile in logik.pakete:
        if (zeile.heizlast_von is not None and zeile.heizlast_bis is not None
                and zeile.heizlast_von <= kw <= zeile.heizlast_bis):
            return zeile.leistungsklasse
    return None


def _klasse_kw(text: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*kW", text or "")
    return float(m.group(1).replace(",", ".")) if m else None


def heizlast_abgleichen(session, gewerk, kw: float, benutzer=None) -> str:
    """Abgleich Heizreport-Heizlast ↔ verkaufte Leistungsklasse (Steckbrief).
    Abweichung → Hinweis (Verlauf art=hinweis, Text wörtlich laut Plan);
    gleiche Klasse → Verlauf „Heizlast passt zur verkauften Klasse“.
    Liefert den Hinweistext oder „“."""
    verkauft = _steckbrief_wert(session, gewerk, "leistungsklasse")
    if not verkauft:
        kern.verlauf(session, gewerk.projekt_id,
                     "Heizlast aus Heizreport: keine verkaufte Leistungsklasse im Steckbrief – "
                     "kein Abgleich", benutzer=benutzer, gewerk_id=gewerk.id)
        return ""
    klasse = klasse_fuer_heizlast(session, kw)
    kw_text = f"{kw:.1f}".replace(".", ",")
    verkauft_kw = _klasse_kw(verkauft)
    klasse_kw = _klasse_kw(klasse or "")
    if klasse is not None and verkauft_kw is not None and klasse_kw == verkauft_kw:
        kern.verlauf(session, gewerk.projekt_id, "Heizlast passt zur verkauften Klasse",
                     benutzer=benutzer, gewerk_id=gewerk.id)
        return ""
    klasse_text = klasse or "keine Leistungsklasse der Paketmatrix"
    hinweis = (f"Heizlast {kw_text} kW laut Heizreport → Leistungsklasse {klasse_text}; "
               f"verkauft: {verkauft} – Auslegung prüfen (Nachtrag oder Freigabe)")
    kern.verlauf(session, gewerk.projekt_id, hinweis, benutzer=benutzer,
                 gewerk_id=gewerk.id, art=VERLAUF_ART_HINWEIS)
    return hinweis


def letzter_hinweis(session, gewerk) -> str:
    from app.models import ProjektVerlauf
    eintrag = (session.query(ProjektVerlauf)
               .filter(ProjektVerlauf.gewerk_id == gewerk.id,
                       ProjektVerlauf.art == VERLAUF_ART_HINWEIS)
               .order_by(ProjektVerlauf.id.desc()).first())
    return eintrag.text if eintrag is not None else ""


def _fp_vorbelegen(session, gewerk, kw: float) -> None:
    """[ANNAHME A-6] FP-L01/FP-L02 mit kW und „Heizreport“ vorbelegen, solange
    sie noch nicht beantwortet sind (Badge „aus Heizreport“)."""
    antworten = kern.fp_antworten(gewerk)
    try:
        vorbelegt = json.loads(gewerk.fp_vorbelegt_json or "{}")
    except ValueError:
        vorbelegt = {}
    neu = False
    if not str(antworten.get("FP-L01") or "").strip():
        antworten["FP-L01"] = f"{kw:.1f}"
        vorbelegt["FP-L01"] = "aus Heizreport"
        neu = True
    if not str(antworten.get("FP-L02") or "").strip():
        antworten["FP-L02"] = "Heizreport"
        vorbelegt["FP-L02"] = "aus Heizreport"
        neu = True
    if neu:
        gewerk.fp_antworten_json = json.dumps(antworten, ensure_ascii=False)
        gewerk.fp_vorbelegt_json = json.dumps(vorbelegt, ensure_ascii=False)


def _heizlast_uebernehmen(session, gewerk, kw: float, benutzer=None) -> None:
    gewerk.heizlast_kw = kw
    gewerk.heizlast_datum = datetime.now()
    gewerk.heizlast_quelle = HV_ERGEBNIS_QUELLE
    _aufgaben_erledigen(session, gewerk, benutzer)


def ergebnis_holen(session, gewerk, benutzer=None) -> tuple[bool, str, float | None]:
    """„Heizlast abrufen“: GET /reports/{key}/results ohne Zusatzparameter;
    Gesamtheizlast in W → kW (eine Nachkommastelle, kaufmännisch) ans Gewerk,
    Quelle „Heizreport API“, Aufgabe erledigt, Abgleich mit der verkauften
    Leistungsklasse, FP-L01/L02 vorbelegt."""
    if not konfiguriert(session):
        return False, "Heizreport-API nicht konfiguriert.", None
    if not gewerk.heizreport_projekt_key:
        return False, "Noch kein Heizreport-Projekt angelegt.", None
    if modus(session) != "v2":
        return _ergebnis_holen_generisch(session, gewerk, benutzer)
    status, antwort = _anfrage_v2(session, "GET", f"/reports/{gewerk.heizreport_projekt_key}/results")
    if status == 422 and isinstance(antwort, dict) and (
            (antwort.get("details") or {}).get("type") == "calculation_unavailable"):
        return False, MELDUNG_NICHT_BERECHENBAR, None
    if status != 200 or not isinstance(antwort, dict):
        return False, fehler_meldung(status, antwort), None
    watt, herkunft = heizlast_aus_ergebnis(antwort, p(session, "heizreport_pfad_heizlast",
                                                       PFAD_HEIZLAST_STANDARD))
    if watt is None:
        schluessel = ", ".join(sorted((antwort.get("results") or {}).keys())
                               if isinstance(antwort.get("results"), dict) else [])
        return False, ("Heizreport: keine Gesamtheizlast im Ergebnis gefunden – Parameter "
                       "heizreport_pfad_heizlast (Parametrierung → Heizreport) prüfen"
                       + (f"; vorhandene Ergebnisschlüssel: {schluessel}" if schluessel else "")), None
    kw = kw_runden(watt)
    _heizlast_uebernehmen(session, gewerk, kw, benutzer)
    kw_text = f"{kw:.1f}".replace(".", ",")
    kern.verlauf(session, gewerk.projekt_id, f"Heizlast aus Heizreport übernommen: {kw_text} kW",
                 benutzer=benutzer, gewerk_id=gewerk.id)
    hinweis = heizlast_abgleichen(session, gewerk, kw, benutzer)
    _fp_vorbelegen(session, gewerk, kw)
    session.flush()
    meldung = f"Heizlast {kw_text} kW übernommen (Heizreport, {herkunft})."
    if hinweis:
        meldung += " " + hinweis
    return True, meldung, kw


# --- PDF ablegen (Phase 124) ---------------------------------------------------------------

def _pdf_url_pruefen(url: str) -> str:
    """Signierter Link: absolut mit https://heizreport.net/ oder relativ zum
    Server-Ursprung; andere Hosts werden abgelehnt (kein Token dorthin)."""
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("/"):
        return f"https://{PDF_HOST}{url}"
    teile = urllib.parse.urlsplit(url)
    if teile.scheme != "https" or teile.hostname is None:
        return ""
    if teile.hostname != PDF_HOST and not teile.hostname.endswith("." + PDF_HOST):
        return ""
    return url


def _pdf_dateiname(session, vorgang_id: int, sparte: str, ordner: str, basis: str) -> str:
    from app.models import GalerieDatei
    vorhanden = {d.dateiname for d in session.query(GalerieDatei)
                 .filter(GalerieDatei.vorgang_id == vorgang_id,
                         GalerieDatei.sparte == sparte, GalerieDatei.ordner == ordner)}
    name = f"{basis}.pdf"
    zaehler = 2
    while name in vorhanden:
        name = f"{basis}-{zaehler}.pdf"
        zaehler += 1
    return name


def pdf_ablegen(session, gewerk, benutzer=None, bestaetigt: bool = False) -> tuple[bool, str, str]:
    """„Heizreport-PDF ablegen“: GET /reports/{key}/pdf?type=heizreport erzeugt bei
    Heizreport ein Dokument (keine folgenlose Leseoperation) – ist
    heizreport_pdf_am gesetzt, zuerst Sicherheitsabfrage. Der signierte Link
    wird sofort ohne Token geladen und nicht gespeichert.
    Liefert (ok, Meldung, Zustand) – Zustand „rueckfrage“ = Bestätigung nötig."""
    from app import galerie
    from app.models import Projekt
    if not konfiguriert(session) or modus(session) != "v2":
        return False, "Heizreport-API (v2) nicht konfiguriert.", "fehler"
    if not gewerk.heizreport_projekt_key:
        return False, "Noch kein Heizreport-Projekt angelegt.", "fehler"
    if gewerk.heizreport_pdf_am and not bestaetigt:
        return False, MELDUNG_PDF_RUECKFRAGE, "rueckfrage"
    projekt = session.get(Projekt, gewerk.projekt_id)
    if projekt is None or not projekt.vorgang_id:
        return False, "Projekt ohne Vorgang – keine Galerie für die Ablage.", "fehler"
    status, antwort = _anfrage_v2(session, "GET",
                                  f"/reports/{gewerk.heizreport_projekt_key}/pdf",
                                  query={"type": "heizreport"})
    if status != 200 or not isinstance(antwort, dict):
        return False, fehler_meldung(status, antwort), "fehler"
    datei = antwort.get("file") if isinstance(antwort.get("file"), dict) else {}
    url = _pdf_url_pruefen(datei.get("url") or antwort.get("linkToDocument") or "")
    if not url:
        return False, "Heizreport: Antwort ohne gültigen PDF-Link (file.url / linkToDocument).", "fehler"
    # Download OHNE Authorization-Header (signierter, zeitlich begrenzter Link);
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    dl_status, inhalt, _kopf = _roh_anfrage("GET", url, {"Accept": "application/pdf,*/*"},
                                            None, DOWNLOAD_TIMEOUT)
    if dl_status != 200 or not inhalt:
        _protokollieren(session, "GET", url.split("?", 1)[0], dl_status, "PDF-Download fehlgeschlagen")
        return False, f"Heizreport-PDF konnte nicht geladen werden (HTTP {dl_status}).", "fehler"
    ordner = p(session, "heizreport_pdf_ordner", PDF_ORDNER_STANDARD) or PDF_ORDNER_STANDARD
    if ordner not in galerie.ordner_liste(session, gewerk.sparte):
        ordner = PDF_ORDNER_STANDARD
    basis = f"Heizreport-{projekt.nummer}-{gewerk.sparte}-{datetime.now():%Y%m%d}"
    name = _pdf_dateiname(session, projekt.vorgang_id, galerie.sparte_pruefen(gewerk.sparte),
                          ordner, basis)
    eintrag = galerie.speichern(session, projekt.vorgang_id, ordner, name, inhalt,
                                benutzer=benutzer, bemerkung="Heizreport-PDF (API)",
                                quelle="heizreport", sparte=gewerk.sparte)
    if eintrag is None:
        return False, "Heizreport-PDF konnte nicht in der Galerie abgelegt werden.", "fehler"
    gewerk.heizreport_pdf_am = datetime.now()
    _aufgaben_erledigen(session, gewerk, benutzer)
    kern.verlauf(session, gewerk.projekt_id, f"Heizreport-PDF abgelegt ({ordner}/{eintrag.dateiname})",
                 benutzer=benutzer, gewerk_id=gewerk.id)
    session.flush()
    return True, f"Heizreport-PDF abgelegt: {ordner}/{eintrag.dateiname}", "ok"


# --- Kontext für Aufgabe/Akte + Protokoll der Parametrierung ------------------------------

def aufgaben_kontext(session, gewerk) -> dict:
    """Kontext der Heizlast-Aufgabe und des Akte-Blocks (Template)."""
    if gewerk is None:
        return {"modus": modus(session), "konfiguriert": konfiguriert(session), "v2": False}
    return {
        "modus": modus(session), "v2": modus(session) == "v2",
        "konfiguriert": konfiguriert(session),
        "key": gewerk.heizreport_projekt_key or "",
        "angelegt_am": gewerk.heizreport_angelegt_am,
        "pdf_am": gewerk.heizreport_pdf_am,
        "portal_url": p(session, "url_heizreport"),
        "hinweis": letzter_hinweis(session, gewerk),
    }


def protokollieren(session, benutzer, aenderungen: list[str]) -> None:
    """Änderungen der Heizreport-Parametrierung (ohne Tokenwert) – letzte 30."""
    if not aenderungen:
        return
    zeilen = [z for z in p(session, PROTOKOLL_PARAMETER).splitlines() if z.strip()]
    wer = getattr(benutzer, "name", "") or "System"
    stempel = datetime.now().strftime("%d.%m.%Y %H:%M")
    zeilen.extend(f"{stempel} · {wer} · {text}" for text in aenderungen)
    kern.parameter_setzen(session, PROTOKOLL_PARAMETER, "\n".join(zeilen[-PROTOKOLL_MAX:]))


def protokoll(session) -> str:
    return p(session, PROTOKOLL_PARAMETER)
