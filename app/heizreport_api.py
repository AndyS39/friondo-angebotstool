# Heizreport-API (v15 Phase 80 vorbereitet, V4 / PLAN_PROJ_V4 Phase 93.1 als
# generischer, in der Parametrierung konfigurierbarer REST-Client).
#
# Die API-Dokumentation des Heizreport-Business-Accounts ist nicht öffentlich
# (docs/heizreport-api.md). Damit die Anbindung ohne Code-Änderung gelingt,
# sind Basis-URL, Auth-Art, Header-Name, Endpunkt-Pfade, HTTP-Methoden und das
# Feld-Mapping (JSON) Parameter der Projektierung:
#   heizreport_api_url          Basis-URL, z. B. https://heizreport.de/api/
#   heizreport_auth_art         header | bearer | basic | body
#   heizreport_auth_header      Header-Name bei „header“ (z. B. X-API-Key)
#                               bzw. JSON-Feld bei „body“ (z. B. apiKey)
#   heizreport_api_key          Schlüssel / Token / Passwort
#   heizreport_benutzer         Benutzername bei „basic“
#   heizreport_pfad_anlegen     z. B. „“ (Basis-URL) oder „projects“
#   heizreport_pfad_status      z. B. „projects/{projekt_key}“
#   heizreport_pfad_ergebnis    z. B. „projects/{projekt_key}/result“
#   heizreport_methode_anlegen / _status / _ergebnis   POST | GET
#   heizreport_mapping_hin      JSON {"zielfeld": "quelle"} – Quellen:
#       kunde.<attr> · projekt.<attr> · gewerk.<attr> · steckbrief.<feld> ·
#       fp.<FP-Key> · erfassung.<Frage-ID> · fest:<Text> · aktion:<Name>
#       (Punkte im Zielfeld erzeugen verschachtelte Objekte)
#   heizreport_mapping_zurueck  JSON {"projekt_key": "pfad.im.json",
#                                     "heizlast_kw": "pfad.im.json",
#                                     "status": "pfad"}
# Ohne Basis-URL + Schlüssel gilt die API als nicht konfiguriert – dann bleibt
# es beim Link (url_heizreport) + PDF-Upload in die Galerie.

import base64
import json
import urllib.error
import urllib.request
from datetime import datetime

from app import projektierung as kern

TIMEOUT = 20
PARAMETER = ("heizreport_api_url", "heizreport_auth_art", "heizreport_auth_header",
             "heizreport_api_key", "heizreport_benutzer", "heizreport_pfad_anlegen",
             "heizreport_pfad_status", "heizreport_pfad_ergebnis",
             "heizreport_methode_anlegen", "heizreport_methode_status",
             "heizreport_methode_ergebnis", "heizreport_mapping_hin",
             "heizreport_mapping_zurueck")

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


def p(session, name: str, standard: str = "") -> str:
    return kern.parameter_holen(session, name, standard).strip()


def konfiguriert(session) -> bool:
    return bool(p(session, "heizreport_api_url") and p(session, "heizreport_api_key"))


# --- HTTP -----------------------------------------------------------------------

def _url(session, pfad_name: str, projekt_key: str = "") -> str:
    basis = p(session, "heizreport_api_url")
    pfad = p(session, pfad_name).replace("{projekt_key}", projekt_key or "")
    if not pfad:
        return basis
    return basis.rstrip("/") + "/" + pfad.lstrip("/")


def _anfrage(session, url: str, methode: str = "GET",
             daten: dict | None = None) -> tuple[int, dict | str]:
    """HTTP-Aufruf mit konfigurierter Auth; liefert (Status, JSON oder Text).
    Wirft nie – Netzfehler werden zu Status 0 mit Fehlertext."""
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


def verbindung_testen(session) -> tuple[bool, str]:
    """Button „Verbindung testen“: GET auf die Basis-URL mit Auth."""
    if not p(session, "heizreport_api_url"):
        return False, "Keine Basis-URL hinterlegt."
    status, antwort = _anfrage(session, p(session, "heizreport_api_url"), "GET")
    auszug = (json.dumps(antwort, ensure_ascii=False) if isinstance(antwort, dict)
              else str(antwort))[:200]
    if status == 0:
        return False, f"Keine Verbindung: {auszug}"
    return 200 <= status < 500, f"HTTP {status} – {auszug}"


# --- Mapping ----------------------------------------------------------------------

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


# --- Aktionen ----------------------------------------------------------------------

def projekt_anlegen(session, gewerk, benutzer=None) -> tuple[bool, str]:
    """Legt das Projekt im Heizreport an (Mapping hin) und merkt sich den
    Projekt-Schlüssel aus der Antwort (Mapping zurück „projekt_key“)."""
    if not konfiguriert(session):
        return False, ("Heizreport-API nicht konfiguriert – Basis-URL und "
                       "Schlüssel in den Projektierung-Einstellungen hinterlegen.")
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
    kern.verlauf(session, gewerk.projekt_id,
                 f"Heizreport-Projekt angelegt (Schlüssel {gewerk.heizreport_projekt_key})",
                 benutzer=benutzer, gewerk_id=gewerk.id)
    session.flush()
    return True, f"Heizreport-Projekt {gewerk.heizreport_projekt_key} angelegt."


def ergebnis_holen(session, gewerk, benutzer=None) -> tuple[bool, str, float | None]:
    """Holt die Heizlast (kW) und schreibt kW + Datum + Quelle „Heizreport
    API“ ans Gewerk; die Aufgabe „Heizlastberechnung liegt vor“ wird erledigt."""
    from app.models import Aufgabe
    if not konfiguriert(session):
        return False, "Heizreport-API nicht konfiguriert.", None
    if not gewerk.heizreport_projekt_key:
        return False, "Noch kein Heizreport-Projekt angelegt.", None
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
    gewerk.heizlast_kw = kw
    gewerk.heizlast_datum = datetime.now()
    gewerk.heizlast_quelle = "Heizreport API"
    for aufgabe in (session.query(Aufgabe)
                    .filter(Aufgabe.gewerk_id == gewerk.id, Aufgabe.aktion_typ == "api",
                            Aufgabe.aktion_wert == "heizreport",
                            Aufgabe.status != "erledigt")):
        aufgabe.status = "erledigt"
        aufgabe.erledigt_am = datetime.now()
        aufgabe.erledigt_von = benutzer.id if benutzer else None
    text = f"{kw:g}".replace(".", ",")
    kern.verlauf(session, gewerk.projekt_id, f"Heizlast aus Heizreport übernommen: {text} kW",
                 benutzer=benutzer, gewerk_id=gewerk.id)
    session.flush()
    return True, f"Heizlast {text} kW übernommen.", kw
