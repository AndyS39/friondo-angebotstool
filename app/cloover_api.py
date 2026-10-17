"""v36 (PLAN_V22 Phase 192): Client für die Cloover Partners API – Schnittstelle (Fundament des Orchestrators),
Umsetzung durch Agent B1 nach dem Vorbild app/heizreport_api.py.

Regeln: der API-Key steht NUR in der .env (`CLOOVER_API_KEY`, config.CLOOVER_API_KEY) und wird nie geloggt,
nie ins Fehlerprotokoll geschrieben, nie angezeigt (Parametrierung: „gesetzt/fehlt“). Ohne Key ist das Modul
aus (`konfiguriert()` False, `modus()` "aus") – alle Aufrufer verhalten sich wie ohne Cloover. Jeder Netzaufruf
läuft ohne offene Datenbanksitzung (Aufrufer lesen vorher, `db.verbindung_freigeben`), Timeout 20 s, JSON;
HTTP-Nahtstelle `_roh_anfrage` (in Tests gemockt). Alle Anfragen tragen `userEmail` (Cloover-Konto, unter dem
das Projekt geführt wird; Standard Parameter `cloover_standard_email`). `inflateTransactionFee` immer false.

Aufbau (Agent B1):
  - Parameter der Parametrierung → Cloover (`PARAMETER_START`, `p()`, typisierte Leser `laufzeit_jahre`,
    `anzahlung_cent`, `optionen`, `laufzeit_von_bis`, `sparten`, `kl_typ`, `standard_email`,
    `user_email_fuer`), Änderungsprotokoll `cloover_protokoll`, letzter Verbindungstest `cloover_letzter_test`.
  - Modus `aus | test | live`: `modus(session)` liest und merkt den Wert prozessweit (`_MODUS_CACHE`), damit
    der sitzungslose Client vor jedem Netzaufruf prüfen kann, ob das Modul aus ist – ohne Key immer „aus“,
    „live“ nur mit Live-URL. Modus „aus“ = kein einziger Aufruf von `_roh_anfrage`.
  - HTTP: `_roh_anfrage(methode, pfad, body)` (urllib, Header X-API-Key, JSON, Timeout 20 s; wirft nie –
    Netzfehler/Timeout = Status 0), `_anfrage()` = Vorprüfung + Fehlerprotokoll („Cloover“, ohne Key, Körper nur
    als Feldnamen), `fehler_meldung()` = Nutzer-Meldungen laut Plan.
  - `rate_berechnen` (v2, Rückfall v1 bei 4xx wegen des Anlagentyps, Rundung kaufmännisch auf Cent),
    `projekt_anlegen` (POST /api/projects → HTTP 201), `projekt_status` (GET /api/projects/{id}),
    `verbindung_testen` (v1-Beispielrate 10.000 € / 2.000 € / 10 Jahre + v2-Probe je aktiver Sparte),
    `assets_fuer` (genau ein Asset je Angebot: Netto nach Gesamtrabatt, USt-Satz, Förderung, capacity).
"""
from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from app import config

TEST_URL = config.CLOOVER_TEST_URL
TIMEOUT_S = 20
MODI = ("aus", "test", "live")
EINSTELLUNG_MODUS = "cloover_modus"
EINSTELLUNG_STANDARD_EMAIL = "cloover_standard_email"
ASSET_TYPEN = {"WP": "Heat pump", "PV": "Solar", "WB": "Wallbox", "KL": "Energetic Renovation"}   # KL [ANNAHME B2]
# Anlagentypen laut Swagger (Befund 15.10.2026) – Auswahlliste für `cloover_kl_typ`
ASSET_TYPEN_API = ("Heat pump", "Solar", "Battery", "Wallbox", "Energetic Renovation")
SPARTEN_REIHENFOLGE = ("WP", "PV", "KL", "WB")     # Reihenfolge in Parametrierung, Probe und Protokoll
KEINE_SPARTEN = "-"                               # gespeicherter Wert „keine Sparte“ (leer = Standard)
OPTIONEN_API = ("Cash", "Financing", "ClooverPay")
SPARTEN_NAMEN = {"WP": "Wärmepumpe", "PV": "Photovoltaik", "KL": "Klima", "WB": "Wallbox"}
WB_CAPACITY_KW = 11                     # Plan Phase 192: Wallbox → capacity 11
LAUFZEIT_MIN_API, LAUFZEIT_MAX_API = 1, 25   # durationInYears laut Swagger 1–25

PFAD_RATE_V2 = "/api/price-calculator/v2"
PFAD_RATE_V1 = "/api/price-calculator"
PFAD_PROJEKTE = "/api/projects"

# Parameter der Parametrierung → Cloover (Tabelle einstellungen; leer = Standard)
PARAMETER_START = {
    EINSTELLUNG_MODUS: "test",
    EINSTELLUNG_STANDARD_EMAIL: "c.castro@friondo.de",   # bestätigt für Test (Plan)
    "cloover_laufzeit_jahre": "20",
    "cloover_anzahlung_eur": "0",
    "cloover_optionen": "Cash,Financing",                # [ANNAHME, Rückfrage B3]
    "cloover_laufzeit_min": "1",                         # [ANNAHME] financingDuration.start
    "cloover_laufzeit_max": "20",                        # [ANNAHME] financingDuration.end
    "cloover_sparten": "WP,PV,KL,WB",
    "cloover_kl_typ": "Energetic Renovation",            # [ANNAHME, Rückfrage B2]
}
EINSTELLUNG_LETZTER_TEST = "cloover_letzter_test"
EINSTELLUNG_PROTOKOLL = "cloover_protokoll"
PROTOKOLL_MAX = 30

MELDUNG_KEY_FEHLT = "Cloover: kein API-Key in der .env (CLOOVER_API_KEY) – Modul aus"
MELDUNG_MODUS_AUS = "Cloover: Modul aus (cloover_modus = aus)"
MELDUNG_KEY_ABGELEHNT = "Cloover: API-Key abgelehnt"
MELDUNG_NICHT_ERREICHBAR = "Cloover nicht erreichbar – später erneut versuchen"
MELDUNG_TEST_KEY_ABGELEHNT = "Cloover erreichbar, aber Key abgelehnt (HTTP 401)"
# Nachtrag 17.10.2026 (Rückfrage 8): der Verbindungstest läuft auch im Modus „aus“, sobald der Key gesetzt ist
# (Zusatz im Ergebnis) – bis v38 brach er mit dem Hinweis „Modus auf test stellen“ ab
ZUSATZ_TEST_MODUS_AUS = "Modus „aus“ – Raten und Projekte bleiben abgeschaltet"
# 4xx-Status, bei denen v2 wegen der Eingabe (Anlagentyp) scheitert und v1 greift [ANNAHME: alle
# Eingabefehler außer 401/403/429 – ein falscher Anlagentyp kommt je nach Server als 400 oder 422]
RUECKFALL_STATUS = (400, 404, 405, 409, 415, 422)

# Beispiel-Assets der v2-Probe des Verbindungstests (ein Asset je aktiver Sparte; KL-Typ aus dem Parameter)
PROBE_ASSETS = {
    "WP": {"priceInfo": {"price": 35992.06, "vatPercentage": 19, "subsidy": 16500, "currency": "EUR"},
           "capacity": 7},
    "PV": {"priceInfo": {"price": 20000, "vatPercentage": 0, "subsidy": 0, "currency": "EUR"},
           "capacity": 10},
    "KL": {"priceInfo": {"price": 6518.66, "vatPercentage": 19, "subsidy": 0, "currency": "EUR"},
           "capacity": 3.5},
    "WB": {"priceInfo": {"price": 2235.7, "vatPercentage": 19, "subsidy": 0, "currency": "EUR"},
           "capacity": WB_CAPACITY_KW},
}

_MODUS_CACHE: dict[str, str | None] = {"wert": None}
_cache_sperre = threading.Lock()
_KW_MUSTER = re.compile(r"(\d+(?:[.,]\d+)?)\s*kW", re.IGNORECASE)


class ClooverFehler(RuntimeError):
    """Fehler der Cloover-API mit Nutzer-Meldung („Cloover: <message>“) – ohne Key, ohne Kundendaten."""

    def __init__(self, meldung: str, status: int = 0):
        super().__init__(meldung)
        self.status = status
        self.meldung = meldung


# --- Konfiguration / Modus -----------------------------------------------------------------

def konfiguriert() -> bool:
    """True, sobald `CLOOVER_API_KEY` in der .env gesetzt ist."""
    return bool(config.CLOOVER_API_KEY)


def basis_url() -> str:
    return config.CLOOVER_BASIS_URL or TEST_URL


def ist_test_url() -> bool:
    return basis_url().rstrip("/") == TEST_URL.rstrip("/")


def p(session, name: str, standard: str | None = None) -> str:
    """Parameter der Parametrierung → Cloover (Tabelle einstellungen); leer = Standard aus PARAMETER_START."""
    from app.models import einstellung_holen
    if standard is None:
        standard = PARAMETER_START.get(name, "")
    return (einstellung_holen(session, name, standard) or "").strip()


def modus_gespeichert(session) -> str:
    """Roh gespeicherter Modus (aus | test | live) – unabhängig von Key und Basis-URL."""
    wert = (p(session, EINSTELLUNG_MODUS) or "test").lower()
    return wert if wert in MODI else "test"


def modus(session) -> str:
    """aus | test | live – ohne Key immer „aus“; „live“ nur mit Live-URL (sonst „test“).
    Merkt den wirksamen Wert prozessweit, damit der sitzungslose Client ihn vor jedem Netzaufruf kennt."""
    wert = modus_gespeichert(session)
    if wert == "live" and ist_test_url():
        wert = "test"
    with _cache_sperre:
        _MODUS_CACHE["wert"] = wert        # Merker ohne Key-Stand – den prüft jeder Aufruf live
    return "aus" if not konfiguriert() else wert


def modus_setzen(session, wert: str) -> tuple[bool, str]:
    """Modus speichern (Parametrierung). „live“ nur mit Live-URL in der .env – sonst (False, Meldung),
    nichts gespeichert. Der Aufrufer committet."""
    from app.models import einstellung_setzen
    wert = (wert or "").strip().lower()
    if wert not in MODI:
        return False, f"Unbekannter Modus „{wert}“ – erlaubt: aus, test, live."
    if wert == "live" and ist_test_url():
        return False, ("Modus „live“ nur mit Live-URL (CLOOVER_BASIS_URL in der .env – zurzeit die "
                       "Test-URL) – Modus nicht geändert.")
    einstellung_setzen(session, EINSTELLUNG_MODUS, wert)
    modus(session)     # Cache nachziehen
    return True, ""


def cache_leeren() -> None:
    """Prozessweiten Modus-Merker verwerfen (Tests, Parametrierung)."""
    with _cache_sperre:
        _MODUS_CACHE["wert"] = None


def _modus_aktuell() -> str:
    """Modus für den sitzungslosen Client: Merker, sonst einmal über eine kurze Lesesitzung –
    die Sitzung ist geschlossen, bevor ein Netzaufruf folgt."""
    if not konfiguriert():
        return "aus"
    with _cache_sperre:
        wert = _MODUS_CACHE["wert"]
    if wert is not None:
        return wert
    from app import db
    with db.kurz(schreibend=False) as s:
        wert = modus(s)
    return wert if konfiguriert() else "aus"


# --- Typisierte Parameter ------------------------------------------------------------------

def _ganzzahl(text: str, standard: int, von: int, bis: int) -> int:
    try:
        wert = int(str(text or "").strip())
    except ValueError:
        return standard
    return min(bis, max(von, wert))


def eur_parsen(text) -> int | None:
    """Deutsches Geldformat („1.500,00“, „1500“, „1500.5“) → Cent; None bei Unlesbarem."""
    roh = str(text if text is not None else "").strip().replace("€", "").replace(" ", "")
    if not roh:
        return None
    if "," in roh:
        roh = roh.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", roh):
        roh = roh.replace(".", "")
    try:
        return int((Decimal(roh) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except Exception:   # noqa: BLE001 – InvalidOperation u. a.
        return None


def eur_text(cent: int | None) -> str:
    """Cent → „1.234,56“ (ohne Währungszeichen)."""
    if cent is None:
        return ""
    vz = "-" if cent < 0 else ""
    e, c = divmod(abs(int(cent)), 100)
    return f"{vz}{e:,}".replace(",", ".") + f",{c:02d}"


def standard_email(session) -> str:
    return p(session, EINSTELLUNG_STANDARD_EMAIL)


def user_email_fuer(session, benutzer=None) -> str:
    """Cloover-Konto für Anfragen: `benutzer.cloover_email` des vorbereitenden Innendienstlers/Admins,
    sonst das Standard-Konto der Parametrierung [ANNAHME Plan Phase 192]."""
    eigenes = (getattr(benutzer, "cloover_email", "") or "").strip() if benutzer is not None else ""
    if eigenes and getattr(benutzer, "basisrolle", "") in ("innendienst", "admin"):
        return eigenes
    return standard_email(session)


def laufzeit_jahre(session) -> int:
    return _ganzzahl(p(session, "cloover_laufzeit_jahre"), 20, LAUFZEIT_MIN_API, LAUFZEIT_MAX_API)


def anzahlung_cent(session) -> int:
    wert = eur_parsen(p(session, "cloover_anzahlung_eur"))
    return max(0, wert or 0)


def optionen(session) -> list[str]:
    """financingOption[] für Projekte – nur bekannte Werte, Reihenfolge wie OPTIONEN_API."""
    gewaehlt = {o.strip() for o in p(session, "cloover_optionen").split(",") if o.strip()}
    liste = [o for o in OPTIONEN_API if o in gewaehlt]
    return liste or [o for o in OPTIONEN_API if o in PARAMETER_START["cloover_optionen"].split(",")]


def laufzeit_von_bis(session) -> tuple[int, int]:
    von = _ganzzahl(p(session, "cloover_laufzeit_min"), 1, LAUFZEIT_MIN_API, LAUFZEIT_MAX_API)
    bis = _ganzzahl(p(session, "cloover_laufzeit_max"), 20, LAUFZEIT_MIN_API, LAUFZEIT_MAX_API)
    if von > bis:
        von, bis = bis, von
    return von, bis


def sparten(session) -> list[str]:
    """Sparten mit Cloover-Rate/-Projekt in fester Reihenfolge (leer gespeichert = Standard alle vier,
    KEINE_SPARTEN = keine)."""
    gewaehlt = {s.strip().upper() for s in p(session, "cloover_sparten").split(",") if s.strip()}
    return [s for s in SPARTEN_REIHENFOLGE if s in gewaehlt]


def kl_typ(session) -> str:
    wert = p(session, "cloover_kl_typ")
    return wert if wert in ASSET_TYPEN_API else PARAMETER_START["cloover_kl_typ"]


def asset_typ(session, sparte: str) -> str | None:
    """Anlagentyp je Sparte (KL aus dem Parameter); None für Sparten ohne Cloover-Typ (GW, MS, …)."""
    sparte = (sparte or "").upper()
    if sparte == "KL":
        return kl_typ(session)
    return ASSET_TYPEN.get(sparte)


# --- Letzter Test, Protokoll ---------------------------------------------------------------

def letzten_test_merken(session, ok: bool, text: str) -> dict:
    from app.models import einstellung_setzen
    daten = {"ok": bool(ok), "text": (text or "")[:2000], "zeit": datetime.now().strftime("%d.%m.%Y %H:%M")}
    einstellung_setzen(session, EINSTELLUNG_LETZTER_TEST, json.dumps(daten, ensure_ascii=False))
    return daten


def letzter_test(session) -> dict | None:
    from app.models import einstellung_holen
    roh = einstellung_holen(session, EINSTELLUNG_LETZTER_TEST, "")
    if not roh:
        return None
    try:
        daten = json.loads(roh)
    except ValueError:
        return None
    return daten if isinstance(daten, dict) else None


def protokollieren(session, benutzer, aenderungen: list[str]) -> None:
    """Änderungen der Parametrierung → Cloover – letzte 30 Zeilen; der Key wird hier nie gesetzt,
    Einträge nennen ihn nur als „gesetzt/fehlt“."""
    if not aenderungen:
        return
    from app.models import einstellung_holen, einstellung_setzen
    zeilen = [z for z in einstellung_holen(session, EINSTELLUNG_PROTOKOLL, "").splitlines() if z.strip()]
    wer = getattr(benutzer, "name", "") or "System"
    stempel = datetime.now().strftime("%d.%m.%Y %H:%M")
    zeilen.extend(f"{stempel} · {wer} · {_maskieren(text)}" for text in aenderungen)
    einstellung_setzen(session, EINSTELLUNG_PROTOKOLL, "\n".join(zeilen[-PROTOKOLL_MAX:]))


def protokoll(session) -> str:
    from app.models import einstellung_holen
    return einstellung_holen(session, EINSTELLUNG_PROTOKOLL, "")


# --- HTTP (eine Nahtstelle für Tests: _roh_anfrage) ------------------------------------------

def _maskieren(text) -> str:
    """Key-Wert aus jedem Text entfernen (Fehlerprotokoll, Meldungen, Protokoll)."""
    text = str(text if text is not None else "")
    geheim = config.CLOOVER_API_KEY
    if geheim and geheim in text:
        text = text.replace(geheim, "***")
    return text


def _json_dict(body: bytes) -> dict:
    """Antwort-Body → Dict; leer/ungültig → {}; JSON-Liste → {"liste": [...]}."""
    text = (body or b"").decode("utf-8", "replace").strip()
    if not text:
        return {}
    try:
        daten = json.loads(text)
    except ValueError:
        return {"text": text[:500]}
    if isinstance(daten, dict):
        return daten
    if isinstance(daten, list):
        return {"liste": daten}
    return {"wert": daten}


def _roh_anfrage(methode: str, pfad: str, body: dict | None = None) -> tuple[int, dict]:
    """HTTP-Nahtstelle: ein Aufruf gegen basis_url() + pfad mit `X-API-Key`, JSON hin und zurück,
    Timeout 20 s. Liefert (Status, JSON-Dict); wirft nie – Netzfehler/Timeout/URLError = Status 0 mit
    {"error": <Text>}. Tests mocken diese Funktion."""
    url = basis_url().rstrip("/") + "/" + pfad.lstrip("/")
    kopf = {"X-API-Key": config.CLOOVER_API_KEY, "Accept": "application/json"}
    koerper = None
    if body is not None:
        koerper = json.dumps(body, ensure_ascii=False).encode("utf-8")
        kopf["Content-Type"] = "application/json"
    anfrage = urllib.request.Request(url, data=koerper, headers=kopf, method=methode.upper())
    try:
        # Primitiver Netzaufruf – der Wächter tests/test_v27_sitzungen.py erkennt damit die ganze
        # Aufrufkette (rate_berechnen, projekt_anlegen, …) als Netz-I/O: Aufrufer geben vorher frei
        with urllib.request.urlopen(anfrage, timeout=TIMEOUT_S) as antwort:
            return antwort.status, _json_dict(antwort.read())
    except urllib.error.HTTPError as fehler:
        try:
            daten = _json_dict(fehler.read())
        except Exception:   # noqa: BLE001
            daten = {}
        return fehler.code, daten
    except Exception as fehler:   # noqa: BLE001 – Netz, DNS, Timeout, URLError
        return 0, {"error": _maskieren(str(fehler))[:300]}


def _message(antwort) -> str:
    """Fehlertext aus dem Antwortblock {message, error} (auch Listen/Unterblöcke)."""
    if not isinstance(antwort, dict):
        return ""
    for key in ("message", "error", "detail", "text"):
        wert = antwort.get(key)
        if isinstance(wert, (list, tuple)):
            wert = "; ".join(str(w) for w in wert if w)
        elif isinstance(wert, dict):
            wert = wert.get("message") or wert.get("error") or json.dumps(wert, ensure_ascii=False)
        if wert:
            return _maskieren(str(wert))[:300]
    return ""


def fehler_meldung(status: int, antwort) -> str:
    """Nutzer-Meldung aus Status + Fehlerblock {message, error} (Plan Phase 192)."""
    text = _message(antwort)
    if status == 401:
        return MELDUNG_KEY_ABGELEHNT
    if status == 403:
        return "Cloover: Zugriff verweigert (HTTP 403)" + (f": {text}" if text else "")
    if status == 422:
        return f"Cloover: Eingabe abgelehnt ({text or 'HTTP 422'})"
    if status == 429:
        return "Cloover: zu viele Anfragen (HTTP 429) – später erneut versuchen"
    if status == 0 or status >= 500:
        return MELDUNG_NICHT_ERREICHBAR
    if status == 404:
        return "Cloover: nicht gefunden (HTTP 404)" + (f": {text}" if text else "")
    return f"Cloover: {text or f'HTTP {status}'}"


def _feldnamen(wert, praefix: str = "") -> list[str]:
    """Nur die Feldnamen eines Request-Bodys (nie Werte) – für das Fehlerprotokoll."""
    namen: list[str] = []
    if isinstance(wert, dict):
        for key, inhalt in wert.items():
            voll = f"{praefix}.{key}" if praefix else str(key)
            namen.append(voll)
            namen.extend(_feldnamen(inhalt, voll))
    elif isinstance(wert, (list, tuple)):
        if wert:
            namen.extend(_feldnamen(wert[0], praefix + "[]"))
    return namen


def _fehler_protokollieren(methode: str, pfad: str, status: int, antwort, body) -> None:
    """Fehlgeschlagener Aufruf → Fehlerprotokoll (Fehlertyp „Cloover“): ohne Header/Key, Körper nur als
    Feldnamen, Antwort nur als Fehlertext. Wirft nie."""
    try:
        from app import fehlerprotokoll
        detail = "Felder: " + (", ".join(_feldnamen(body)) if body else "–")
        text = _message(antwort)
        if text:
            detail += "\nAntwort: " + text
        elif status == 0:
            detail += "\nAntwort: keine (Netzfehler/Timeout)"
        fehlerprotokoll.eintragen_text("Cloover", _maskieren(f"{methode.upper()} {pfad} → HTTP {status}"),
                                       _maskieren(detail), pfad=pfad[:300])
    except Exception:   # noqa: BLE001
        pass


def _anfrage(methode: str, pfad: str, body: dict | None = None, *, modus_pruefen: bool = True) -> tuple[int, dict]:
    """Vorprüfung (Key, Modus) + Aufruf + Fehlerprotokoll bei Status 0/4xx/5xx. Liefert (Status, Antwort);
    das Werten übernimmt der Aufrufer (`_pruefen`). `modus_pruefen=False` nur für den Verbindungstest
    (Nachtrag 17.10.2026: er läuft auch im Modus „aus“) – der Key bleibt immer Pflicht."""
    if not konfiguriert():
        raise ClooverFehler(MELDUNG_KEY_FEHLT)
    if modus_pruefen and _modus_aktuell() == "aus":
        raise ClooverFehler(MELDUNG_MODUS_AUS)
    status, antwort = _roh_anfrage(methode, pfad, body)
    if not isinstance(antwort, dict):
        antwort = {}
    if status == 0 or status >= 400:
        _fehler_protokollieren(methode, pfad, status, antwort, body)
    return status, antwort


def _pruefen(status: int, antwort: dict, erlaubt=(200, 201)) -> None:
    if status not in erlaubt:
        raise ClooverFehler(fehler_meldung(status, antwort), status)


# --- Beträge ---------------------------------------------------------------------------------

def _eur(cent: int | None):
    """Cent → EUR mit 2 Stellen für den Body (ganze Beträge als int: 20000, sonst 35992.06)."""
    betrag = (Decimal(int(cent or 0)) / 100).quantize(Decimal("0.01"))
    return int(betrag) if betrag == betrag.to_integral_value() else float(betrag)


def _rate_cent(wert) -> int | None:
    """monthlyPayment (ungerundet, z. B. 93,3582) → Cent kaufmännisch (9336)."""
    if wert is None or wert == "":
        return None
    try:
        betrag = Decimal(str(wert).replace(",", "."))
    except Exception:   # noqa: BLE001
        return None
    return int((betrag * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _wert(antwort: dict, *namen):
    """Erster vorhandener Schlüssel – auch im Unterblock `data` [ANNAHME: Antwort flach oder unter data]."""
    quellen = [antwort]
    if isinstance(antwort.get("data"), dict):
        quellen.append(antwort["data"])
    for quelle in quellen:
        for name in namen:
            if name in quelle and quelle[name] is not None:
                return quelle[name]
    return None


def _laufzeit_pruefen(laufzeit_jahre) -> int:
    try:
        laufzeit = int(laufzeit_jahre)
    except (TypeError, ValueError):
        raise ClooverFehler("Cloover: Laufzeit fehlt") from None
    if not LAUFZEIT_MIN_API <= laufzeit <= LAUFZEIT_MAX_API:
        raise ClooverFehler(f"Cloover: Laufzeit {laufzeit} Jahre außerhalb von "
                            f"{LAUFZEIT_MIN_API}–{LAUFZEIT_MAX_API} Jahren")
    return laufzeit


# --- Rate ------------------------------------------------------------------------------------

def _rate_v1(brutto_cent: int, laufzeit: int, anzahlung_cent: int, user_email: str, *,
             modus_pruefen: bool = True) -> tuple[int, dict]:
    body = {"totalCostOfInstallation": _eur(brutto_cent), "userEmail": user_email,
            "durationInYears": laufzeit, "downPayment": _eur(anzahlung_cent), "currency": "EUR"}
    return _anfrage("POST", PFAD_RATE_V1, body, modus_pruefen=modus_pruefen)


def rate_berechnen(assets: list[dict], laufzeit_jahre: int, anzahlung_cent: int, user_email: str, *,
                   brutto_cent: int | None = None, rueckfall: bool = True,
                   modus_pruefen: bool = True) -> dict:
    """POST /api/price-calculator/v2 (Rückfall v1 bei abgelehntem Anlagentyp) →
    {rate_ohne_cent, rate_mit_cent | None, quelle "v2"|"v1", antwort, laufzeit_jahre, anzahlung_cent}.
    Rückfall v1 (`totalCostOfInstallation` = `brutto_cent`, der Endbetrag brutto) nur, wenn v2 mit einem
    Status aus RUECKFALL_STATUS antwortet, `rueckfall` True ist und `brutto_cent` übergeben wurde; dann
    zusätzlich `v2_fehler` (Meldung der v2-Antwort). Rundung kaufmännisch auf Cent (93,3582 → 9336).
    Kein Netz mit offener Sitzung: die Funktion bekommt keine Session – der Aufrufer gibt vorher frei."""
    laufzeit = _laufzeit_pruefen(laufzeit_jahre)
    anzahlung = max(0, int(anzahlung_cent or 0))
    if not user_email:
        raise ClooverFehler("Cloover: userEmail fehlt (Cloover-Konto in der Parametrierung eintragen)")
    body = {"userEmail": user_email, "country": "Germany", "projectAssets": list(assets or []),
            "durationInYears": laufzeit, "downPayment": _eur(anzahlung), "inflateTransactionFee": False}
    status, antwort = _anfrage("POST", PFAD_RATE_V2, body, modus_pruefen=modus_pruefen)
    if status in (200, 201):
        rate_ohne = _rate_cent(_wert(antwort, "monthlyPayment"))
        if rate_ohne is None:
            raise ClooverFehler("Cloover: Antwort ohne monthlyPayment", status)
        return {"rate_ohne_cent": rate_ohne,
                "rate_mit_cent": _rate_cent(_wert(antwort, "monthlyPaymentAfterSubsidies")),
                "quelle": "v2", "antwort": antwort, "laufzeit_jahre": laufzeit, "anzahlung_cent": anzahlung}
    if rueckfall and brutto_cent is not None and status in RUECKFALL_STATUS:
        v2_fehler = fehler_meldung(status, antwort)
        status1, antwort1 = _rate_v1(int(brutto_cent), laufzeit, anzahlung, user_email, modus_pruefen=modus_pruefen)
        _pruefen(status1, antwort1)
        rate_ohne = _rate_cent(_wert(antwort1, "monthlyPayment"))
        if rate_ohne is None:
            raise ClooverFehler("Cloover: Antwort ohne monthlyPayment", status1)
        return {"rate_ohne_cent": rate_ohne, "rate_mit_cent": None, "quelle": "v1", "antwort": antwort1,
                "laufzeit_jahre": laufzeit, "anzahlung_cent": anzahlung, "v2_fehler": v2_fehler}
    raise ClooverFehler(fehler_meldung(status, antwort), status)


# --- Projekt ---------------------------------------------------------------------------------

def _feld(daten: dict, *namen) -> str:
    """Erster gefüllter Wert aus einem Dict mit deutschen oder API-Schlüsseln."""
    for name in namen:
        wert = (daten or {}).get(name)
        if wert not in (None, ""):
            return str(wert).strip()
    return ""


def projekt_anlegen(kunde: dict, adresse: dict, assets: list[dict], laufzeit_von_bis: tuple[int, int],
                    optionen: list[str], pdf_urls: list[str], user_email: str) -> dict:
    """POST /api/projects → {projekt_id, checkout_link, financial_offer, antwort} (HTTP 201).
    `kunde`: vorname/nachname/email/telefon (oder firstName/lastName/email/phone), `adresse`:
    strasse/ort/plz (oder street/city/postalCode) – alle Kundenfelder sind bei Cloover Pflicht."""
    customer = {"firstName": _feld(kunde, "firstName", "vorname"), "lastName": _feld(kunde, "lastName", "nachname"),
                "email": _feld(kunde, "email", "e_mail"), "phone": _feld(kunde, "phone", "telefon"),
                "type": "Individual"}
    fehlend = [name for name, wert in customer.items() if not wert]
    if fehlend:
        raise ClooverFehler("Cloover: Kundendaten unvollständig (fehlt: " + ", ".join(fehlend) + ")")
    projekt_adresse = {"street": _feld(adresse, "street", "strasse"), "city": _feld(adresse, "city", "ort"),
                       "postalCode": _feld(adresse, "postalCode", "plz"), "country": "Germany"}
    fehlend = [name for name in ("street", "city", "postalCode") if not projekt_adresse[name]]
    if fehlend:
        raise ClooverFehler("Cloover: Adresse unvollständig (fehlt: " + ", ".join(fehlend) + ")")
    if not assets:
        raise ClooverFehler("Cloover: keine Anlage (projectAssets) für das Projekt")
    gewaehlt = [o for o in OPTIONEN_API if o in {str(x).strip() for x in (optionen or [])}]
    if not gewaehlt:
        raise ClooverFehler("Cloover: keine Finanzierungsoption gewählt (Parametrierung → Cloover)")
    urls = [str(u).strip() for u in (pdf_urls or []) if str(u or "").strip()]
    if not urls:
        raise ClooverFehler("Cloover: offerPDF fehlt – öffentlich abrufbare URL des Angebots-PDFs nötig")
    von, bis = laufzeit_von_bis
    von = _laufzeit_pruefen(von)
    bis = _laufzeit_pruefen(bis)
    if von > bis:
        von, bis = bis, von
    if not user_email:
        raise ClooverFehler("Cloover: userEmail fehlt (Cloover-Konto in der Parametrierung eintragen)")
    body = {"userEmail": user_email, "customer": customer, "projectAddress": projekt_adresse,
            "projectAssets": list(assets), "financingDuration": {"start": von, "end": bis},
            "financingOption": gewaehlt, "offerPDF": urls, "inflateTransactionFee": False}
    status, antwort = _anfrage("POST", PFAD_PROJEKTE, body)
    _pruefen(status, antwort, erlaubt=(200, 201))
    projekt_id = _wert(antwort, "project_id", "projectId", "id")
    checkout_link = _wert(antwort, "checkout_link", "checkoutLink", "checkout_url")
    if projekt_id in (None, "") or not checkout_link:
        raise ClooverFehler("Cloover: Antwort ohne project_id/checkout_link", status)
    return {"projekt_id": str(projekt_id), "checkout_link": str(checkout_link),
            "financial_offer": _wert(antwort, "financial_offer", "financialOffer"), "antwort": antwort}


def projekt_status(projekt_id: str) -> dict:
    """GET /api/projects/{id} → {id, status, primary_signed_contract, secondary_signed_contract,
    contract_signed_date, financing_option_chosen, antwort}; unbekannte status-Werte roh (Rückfrage B8)."""
    kennung = str(projekt_id or "").strip()
    if not kennung:
        raise ClooverFehler("Cloover: Projekt-ID fehlt")
    pfad = f"{PFAD_PROJEKTE}/{urllib.parse.quote(kennung, safe='')}"
    status, antwort = _anfrage("GET", pfad)
    if status == 404:
        raise ClooverFehler(f"Cloover: Projekt {kennung} nicht gefunden (HTTP 404)", 404)
    _pruefen(status, antwort, erlaubt=(200,))
    return {"id": str(_wert(antwort, "id", "project_id", "projectId") or kennung),
            "status": _wert(antwort, "status"),
            "primary_signed_contract": _wert(antwort, "primary_signed_contract", "primarySignedContract"),
            "secondary_signed_contract": _wert(antwort, "secondary_signed_contract", "secondarySignedContract"),
            "contract_signed_date": _wert(antwort, "contract_signed_date", "contractSignedDate"),
            "financing_option_chosen": _wert(antwort, "financing_option_chosen", "financingOptionChosen"),
            "antwort": antwort}


# --- Verbindungstest -------------------------------------------------------------------------

def verbindung_testen(session) -> tuple[bool, str]:
    """Verbindungstest der Parametrierung: v1-Beispielrate 10.000 € brutto / 2.000 € Anzahlung / 10 Jahre
    → „Verbindung OK · Beispielrate 93,36 €/Monat (Test-Umgebung)“ (Zusatz nur bei Test-URL) bzw.
    „Cloover erreichbar, aber Key abgelehnt (HTTP 401)“ bzw. Fehlertext; danach v2-Probe mit einem Asset je
    aktiver Sparte („Klima: Typ Energetic Renovation akzeptiert“ / „… abgelehnt: <message>“). Ergebnis in
    `cloover_letzter_test`. Liest alles vor dem ersten Netzaufruf und gibt die Verbindung frei.
    Nachtrag 17.10.2026 (Rückfrage 8): läuft auch im Modus „aus“ (Key gesetzt) – dann mit dem Zusatz
    „Modus „aus“ – Raten und Projekte bleiben abgeschaltet“; nur der fehlende Key bricht ab."""
    from app.db import verbindung_freigeben
    if not konfiguriert():
        return False, MELDUNG_KEY_FEHLT
    modus_aus = modus(session) == "aus"
    email = standard_email(session)
    aktive = sparten(session)
    typ_kl = kl_typ(session)
    laufzeit = laufzeit_jahre(session)
    verbindung_freigeben(session)
    try:
        status, antwort = _rate_v1(1_000_000, 10, 200_000, email, modus_pruefen=False)
    except ClooverFehler as fehler:
        return False, fehler.meldung
    if status == 401:
        ok, text = False, MELDUNG_TEST_KEY_ABGELEHNT
    elif status not in (200, 201):
        ok, text = False, fehler_meldung(status, antwort)
    else:
        rate = _rate_cent(_wert(antwort, "monthlyPayment"))
        if rate is None:
            ok, text = False, "Cloover: Antwort ohne monthlyPayment"
        else:
            ok = True
            text = f"Verbindung OK · Beispielrate {eur_text(rate)} €/Monat"
            if ist_test_url():
                text += " (Test-Umgebung)"
    if ok:
        teile = []
        for sparte in aktive:
            typ = typ_kl if sparte == "KL" else ASSET_TYPEN[sparte]
            asset = dict(PROBE_ASSETS[sparte], type=typ)
            name = SPARTEN_NAMEN[sparte]
            try:
                rate_berechnen([asset], laufzeit, 0, email, rueckfall=False, modus_pruefen=False)
                teile.append(f"{name}: Typ {typ} akzeptiert")
            except ClooverFehler as fehler:
                grund = fehler.meldung[len("Cloover: "):] if fehler.meldung.startswith("Cloover: ") else fehler.meldung
                teile.append(f"{name}: Typ {typ} abgelehnt: {grund}")
        if teile:
            text += " · " + " · ".join(teile)
        if modus_aus:
            text += " · " + ZUSATZ_TEST_MODUS_AUS
    letzten_test_merken(session, ok, text)
    return ok, text


# --- Anlagen aus dem Angebot ---------------------------------------------------------------

def _kw_aus_text(text) -> float | None:
    m = _KW_MUSTER.search(str(text or ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _zahl(wert) -> float | None:
    if wert in (None, ""):
        return None
    try:
        return float(str(wert).replace(",", "."))
    except ValueError:
        return None


def _glatt(wert: float | None):
    """7.0 → 7, 12.5 bleibt 12.5 (JSON ohne überflüssige Nachkommastelle)."""
    if wert is None:
        return None
    wert = round(float(wert), 3)
    return int(wert) if float(wert).is_integer() else wert


def _volle_positionen(angebot) -> set[str]:
    return {(pos.pos_nr or "").strip() for pos in angebot.positionen
            if pos.pos_nr and not pos.ep_flag and not pos.bauseits and not pos.alternativ}


def _wp_kapazitaet(session, angebot) -> tuple[float | None, str]:
    """kW der Leistungsklasse eines WP-Angebots: (1) Steckbrief des verknüpften Gewerks
    (`leistungsklasse`, z. B. „7 kW (CS3800i)“ – auch manuell korrigiert), (2) Leistungsklasse aus den
    Erfassungs-/Konfigurationsantworten (`konfigurator.leistungsklasse`, Paketmatrix), (3) Nennleistung
    der BAFA-Anlage zur Paket-Position (Blatt „BAFA-Anlagen“, 045–054 / 15+055/056), (4) Zahl vor „kW“
    im Konfigurationsprotokoll/Auslegungstext. Liefert (kW | None, Quelle)."""
    from app.models import Erfassung, Konfiguration, SteckbriefWert
    gewerk_id = getattr(angebot, "projekt_gewerk_id", None)
    if gewerk_id:
        zeile = (session.query(SteckbriefWert)
                 .filter(SteckbriefWert.gewerk_id == gewerk_id, SteckbriefWert.feld == "leistungsklasse")
                 .first())
        kw = _kw_aus_text(zeile.wert if zeile is not None else "")
        if kw:
            return kw, "steckbrief"
    antworten: dict = {}
    erfassung = (session.query(Erfassung).filter(Erfassung.angebot_id == angebot.id)
                 .order_by(Erfassung.id.desc()).first())
    if erfassung is not None:
        try:
            antworten = json.loads(erfassung.antworten_json or "{}") or {}
        except ValueError:
            antworten = {}
    if not antworten and getattr(angebot, "konfiguration_id", None):
        konfiguration = session.get(Konfiguration, angebot.konfiguration_id)
        if konfiguration is not None:
            try:
                antworten = json.loads(konfiguration.antworten_json or "{}") or {}
            except ValueError:
                antworten = {}
    logik = None
    try:
        from app import logik as logik_modul
        logik, _bericht = logik_modul.hole_logik(session)
    except Exception:   # noqa: BLE001 – Logik-Excel nicht lesbar: weiter mit den Textquellen
        logik = None
    if antworten and logik is not None:
        try:
            from app import konfigurator
            zeile = konfigurator.leistungsklasse(logik, antworten)
        except Exception:   # noqa: BLE001
            zeile = None
        kw = _kw_aus_text(zeile.leistungsklasse if zeile is not None else "")
        if kw:
            return kw, "erfassung"
    if logik is not None:
        try:
            from app import logik as logik_modul
            anlage = logik_modul.bafa_fuer_positionen(logik, _volle_positionen(angebot))
        except Exception:   # noqa: BLE001
            anlage = None
        if anlage is not None and anlage.kw:
            return float(anlage.kw), "bafa"
    for text in (getattr(angebot, "auslegung_text", "") or "", getattr(angebot, "protokoll_json", "") or ""):
        m = re.search(r"Leistungsklasse[^0-9]{0,60}?(\d+(?:[.,]\d+)?)\s*kW", text)
        if m:
            kw = _zahl(m.group(1))
            if kw:
                return kw, "protokoll"
    return None, ""


def kapazitaet_fuer(session, angebot) -> tuple[float | None, str]:
    """capacity je Sparte: WP kW der Leistungsklasse (siehe _wp_kapazitaet), PV kWp aus pv_json,
    KL Σ Kühllast kW aus kl_json (2 Stellen), WB 11. Liefert (Wert | None, Quelle)."""
    sparte = (getattr(angebot, "konfigurator_typ", "") or "WP").upper()
    if sparte == "WP":
        return _wp_kapazitaet(session, angebot)
    if sparte == "PV":
        try:
            daten = json.loads(getattr(angebot, "pv_json", "") or "{}") or {}
        except ValueError:
            daten = {}
        kwp = _zahl(daten.get("kwp")) if isinstance(daten, dict) else None
        return (round(kwp, 3), "pv_json") if kwp else (None, "")
    if sparte == "KL":
        try:
            daten = json.loads(getattr(angebot, "kl_json", "") or "{}") or {}
        except ValueError:
            daten = {}
        raeume = daten.get("raeume") if isinstance(daten, dict) else None
        summe = sum((_zahl(r.get("kuehllast_kw")) or 0.0) for r in (raeume or []) if isinstance(r, dict))
        return (round(summe, 2), "kl_json") if summe > 0 else (None, "")
    if sparte == "WB":
        return float(WB_CAPACITY_KW), "fest"
    return None, ""


def foerderung_cent(session, angebot) -> int:
    """Förderbetrag (subsidy) eines WP-Angebots in Cent aus kfw_json über pdf_export._kfw_ergebnis_fuer –
    0 ohne Förderblock, bei `foerderung_ausblenden` und für PV/KL/WB; eine manuell festgelegte Förderung
    (v6/v8-Overrides) zählt."""
    if (getattr(angebot, "konfigurator_typ", "") or "WP").upper() != "WP":
        return 0
    try:
        from app import pdf_export
        ergebnis = pdf_export._kfw_ergebnis_fuer(session, angebot)
    except Exception:   # noqa: BLE001 – Förderung unbekannt → 0 (Rate ohne Förderung bleibt richtig)
        ergebnis = None
    if ergebnis is None:
        return 0
    return max(0, int(getattr(ergebnis, "zuschuss_cent", 0) or 0))


def assets_fuer(session, angebot) -> list[dict]:
    """Genau ein Asset je Angebot (Typ je Sparte – KL aus `cloover_kl_typ`; price = Netto nach Gesamtrabatt
    = summen()["netto_nach_rabatt"] in EUR, vatPercentage = USt-Satz des Angebots (19 | 0), subsidy =
    Förderbetrag bei WP (sonst 0), currency EUR, capacity sofern ermittelbar [ANNAHME: ohne Wert entfällt
    der Schlüssel]). Sparten ohne Cloover-Typ (GW, MS, WA, DMS) liefern []. Beträge nur aus Angebot.summen().
    Kontrollwerte: WP Endbetrag 42.830,55 €, Förderung 16.500,00 € → price 35992.06, vatPercentage 19,
    subsidy 16500; PV 20.000,00 € (0 %) → price 20000, vatPercentage 0, subsidy 0."""
    sparte = (getattr(angebot, "konfigurator_typ", "") or "WP").upper()
    typ = asset_typ(session, sparte)
    if typ is None or getattr(angebot, "extern", False):
        return []
    summen = angebot.summen()
    ust = angebot.ust_prozent
    vat = int(ust) if ust == ust.to_integral_value() else float(ust)
    asset = {"type": typ,
             "priceInfo": {"price": _eur(summen["netto_nach_rabatt"]), "vatPercentage": vat,
                           "subsidy": _eur(foerderung_cent(session, angebot)), "currency": "EUR"}}
    kapazitaet, _quelle = kapazitaet_fuer(session, angebot)
    if kapazitaet is not None:
        asset["capacity"] = _glatt(kapazitaet)
    return [asset]
