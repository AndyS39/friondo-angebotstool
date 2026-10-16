# Routing (v12, Phase 77): Fahrzeiten mit 90-Tage-Cache; Anbieter ors-Matrix,
# Google Route Matrix oder Luftlinie × 1,3 bei 45 km/h (Kennzeichen
# „geschätzt“). Matrix-Aufrufe werden je Assistenten-Lauf gebündelt.
# Alle Aufrufe Timeout 8 s, Fehler nie blockierend (Fallback Luftlinie).
#
# v37 (PLAN_LEAD_V7 Phase 198, Agent L2) – „Route in Kilometern“:
#  - Der openrouteservice-Key kommt aus der .env (config.ORS_API_KEY, Vorrang); der alte
#    Lead-Parameter ors_api_key bleibt als Rückfall (ors_schluessel / ors_schluessel_quelle).
#    Ohne Key bleibt alles Luftlinie × 1,3 mit Kennzeichen „geschätzt“ – Hinweis
#    „ORS_API_KEY fehlt“ in Parametrierung und Prüfpunkt.
#  - Anzeigeformat überall gleich (strecke_text): „18,4 km · 24 Min“ vom Dienst,
#    „ca. 24 km · 31 Min (geschätzt)“ bei Ausfall/ohne Key.
#  - Tageskontingent routing_kontingent_tag (Standard 2000 [ANNAHME: Free-Plan-Limit laut
#    Briefing – Rückfrage im Bericht], Zähler aufrufe_ors_matrix_<Datum> wie bisher über
#    geocoding._zaehler, best effort); ab 80 % Hinweis in den Lead-Einstellungen, ab 100 %
#    kein Matrix-Aufruf mehr am selben Tag (Schätzung statt HTTP 403) [ANNAHME].
#  - Prüfpunkt „Routing-Dienst antwortet“ (dienst_pruefen): Matrix 1×1 Duisburg → Bochum nach
#    verbindung_freigeben, Ergebnis als Text; Migration migration_v37_routing setzt den
#    Anbieter einmalig auf „ors“, sobald ein Key vorliegt (idempotent; Hook in migrate.py
#    durch den Orchestrator).
# Netz nie mit offener Sitzung (Wächter tests/test_v27_sitzungen.py): matrix_fuellen und
# dienst_pruefen geben die Verbindung vor dem HTTP-Aufruf frei.

import json
import logging
import math
import urllib.request
from datetime import datetime, timedelta

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import config
from app.models import RoutingCache

TIMEOUT = 8
CACHE_TAGE = 90
# v37: Tageskontingent der Matrix-Aufrufe (Lead-Parameter routing_kontingent_tag)
KONTINGENT_PARAMETER = "routing_kontingent_tag"
KONTINGENT_STANDARD = 2000          # [ANNAHME] laut Briefing (ORS Free-Plan) – Rückfrage im Bericht
KONTINGENT_WARNUNG_PROZENT = 80
ZAEHLER_DIENST = "ors_matrix"       # Schlüssel des Tageszählers (geocoding._zaehler)
PRUEFUNG_PARAMETER = "routing_pruefung"     # letztes Ergebnis des Prüfpunkts (Text)
KEY_FEHLT_TEXT = "ORS_API_KEY fehlt – Fahrzeiten werden als Luftlinie × 1,3 geschätzt"
# Prüfpunkt: Duisburg (Innenhafen) → Bochum (Hauptbahnhof), eine Matrixzelle
PRUEF_VON = (51.4344, 6.7623)
PRUEF_NACH = (51.4786, 7.2234)
_logger = logging.getLogger("angebotstool.routing")


def _key(lat: float, lon: float) -> str:
    return f"{lat:.4f},{lon:.4f}"


def luftlinie_km(von: tuple, nach: tuple) -> float:
    """Haversine in Kilometern."""
    lat1, lon1 = von
    lat2, lon2 = nach
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def _geschaetzt(von: tuple, nach: tuple) -> tuple[float, float]:
    """Luftlinie × 1,3 bei 45 km/h → (minuten, km)."""
    km = luftlinie_km(von, nach) * 1.3
    return km / 45 * 60, km


# --- v37: Schlüssel, Anbieter, Kontingent --------------------------------------------------

def ors_schluessel(session: Session | None = None) -> str:
    """openrouteservice-Key: .env (ORS_API_KEY) hat Vorrang, sonst der Lead-Parameter
    ors_api_key (Rückfall, Parametrierung → Lead-Routing); leer = kein Dienst."""
    if config.ORS_API_KEY:
        return config.ORS_API_KEY
    if session is None:
        return ""
    from app import leadmanagement as kern
    return (kern.parameter_holen(session, "ors_api_key", "") or "").strip()


def ors_schluessel_quelle(session: Session | None = None) -> str:
    """„env“ | „parameter“ | „“ – für die Anzeige (der Key selbst erscheint nirgends)."""
    if config.ORS_API_KEY:
        return "env"
    return "parameter" if (session is not None and ors_schluessel(session)) else ""


def google_schluessel(session: Session) -> str:
    from app import leadmanagement as kern
    return (kern.parameter_holen(session, "google_api_key", "") or "").strip()


def anbieter(session: Session) -> str:
    """Lead-Parameter routing_anbieter (ors | google | luftlinie)."""
    from app import leadmanagement as kern
    return (kern.parameter_holen(session, "routing_anbieter", "luftlinie") or "luftlinie").strip().lower()


def dienst_aktiv(session: Session) -> bool:
    """Liefert der konfigurierte Anbieter echte Straßenkilometer (Anbieter + Schlüssel)?"""
    a = anbieter(session)
    if a == "ors":
        return bool(ors_schluessel(session))
    if a == "google":
        return bool(google_schluessel(session))
    return False


def kontingent(session: Session) -> int:
    from app import leadmanagement as kern
    try:
        wert = int(str(kern.parameter_holen(session, KONTINGENT_PARAMETER,
                                            str(KONTINGENT_STANDARD))).strip() or KONTINGENT_STANDARD)
    except ValueError:
        wert = KONTINGENT_STANDARD
    return max(1, wert)


def aufrufe_heute(session: Session, dienst: str = ZAEHLER_DIENST, tag=None) -> int:
    """Tageszähler des Dienstes (Parameter aufrufe_<dienst>_<JJJJ-MM-TT>, geocoding._zaehler)."""
    from app import leadmanagement as kern
    tag = tag or datetime.now().date()
    try:
        return int(kern.parameter_holen(session, f"aufrufe_{dienst}_{tag.isoformat()}", "0") or 0)
    except ValueError:
        return 0


def kontingent_status(session: Session) -> dict:
    """{aufrufe, kontingent, prozent, warnung (≥ 80 %), erschoepft (≥ 100 %), text} für
    Lead-Einstellungen, Lead-Routing und den Rückfall in matrix_fuellen."""
    aufrufe = aufrufe_heute(session)
    grenze = kontingent(session)
    prozent = int(round(aufrufe * 100 / grenze)) if grenze else 0
    warnung = prozent >= KONTINGENT_WARNUNG_PROZENT
    erschoepft = aufrufe >= grenze
    if erschoepft:
        text = (f"Tageskontingent erreicht ({aufrufe}/{grenze} Matrix-Aufrufe) – bis Mitternacht "
                "werden Fahrzeiten geschätzt")
    elif warnung:
        text = f"{prozent} % des Tageskontingents verbraucht ({aufrufe}/{grenze} Matrix-Aufrufe)"
    else:
        text = f"{aufrufe}/{grenze} Matrix-Aufrufe heute ({prozent} %)"
    return {"aufrufe": aufrufe, "kontingent": grenze, "prozent": prozent,
            "warnung": warnung, "erschoepft": erschoepft, "text": text}


# --- Anzeigeformat -------------------------------------------------------------------------

def km_text(km: float) -> str:
    """„18,4 km“ (eine Nachkommastelle, deutsches Komma)."""
    return f"{float(km or 0):.1f}".replace(".", ",") + " km"


def min_text(minuten: float) -> str:
    return f"{int(round(float(minuten or 0)))} Min"


def strecke_text(ergebnis: dict | None) -> str:
    """Einheitliche Anzeige (Plan Phase 198): vom Dienst „18,4 km · 24 Min“, geschätzt
    „ca. 24 km · 31 Min (geschätzt)“; ohne Werte leer."""
    if not ergebnis:
        return ""
    km = float(ergebnis.get("km") or 0)
    minuten = float(ergebnis.get("minuten") or 0)
    if ergebnis.get("geschaetzt"):
        return f"ca. {int(round(km))} km · {min_text(minuten)} (geschätzt)"
    return f"{km_text(km)} · {min_text(minuten)}"


# --- Cache ---------------------------------------------------------------------------------

def _cache_lesen(session: Session, von: tuple, nach: tuple):
    zeile = (session.query(RoutingCache)
             .filter(RoutingCache.von_key == _key(*von),
                     RoutingCache.nach_key == _key(*nach)).first())
    if (zeile is not None and zeile.gueltig_bis is not None
            and zeile.gueltig_bis > datetime.now()):
        return zeile
    return None


def _cache_schreiben(session: Session, von: tuple, nach: tuple,
                     minuten: float, km: float, anbieter: str) -> None:
    """Hotfix 06.10.2026: Upsert statt Lesen+Einfügen – parallele Anfragen
    (z. B. mehrere Kundenkarteien mit Terminvorschlägen) fügten dasselbe Paar
    gleichzeitig ein und liefen in „UNIQUE constraint failed“; ON CONFLICT
    aktualisiert die Zeile des anderen. Danach die Zeile frisch laden, damit
    ein ggf. schon geladenes (abgelaufenes) Objekt die neuen Werte trägt."""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    werte = {"minuten": round(minuten, 1), "km": round(km, 1), "anbieter": anbieter,
             "gueltig_bis": datetime.now() + timedelta(days=CACHE_TAGE)}
    anweisung = sqlite_insert(RoutingCache).values(
        von_key=_key(*von), nach_key=_key(*nach), **werte)
    try:
        session.execute(anweisung.on_conflict_do_update(
            index_elements=["von_key", "nach_key"], set_=werte))
    except OperationalError as fehler:
        # v30-Nachtrag 12.10.2026 (Entscheidung 21): der Cache ist best effort –
        # viele gleichzeitige Anfragen (Terminvorschläge mehrerer Karteien) schreiben
        # dieselben Paare; hält ein anderer Schreiber die SQLite-Sperre länger als
        # busy_timeout, bleibt der Eintrag aus (die Anfrage rechnet mit dem Wert im
        # Speicher weiter) statt mit 500 „database is locked“ abzubrechen.
        if "locked" not in str(fehler).lower():
            raise
        logging.getLogger("angebotstool").warning(
            "Routing-Cache: Datenbank belegt – Eintrag %s → %s übersprungen",
            _key(*von), _key(*nach))
        return
    (session.query(RoutingCache)
     .filter(RoutingCache.von_key == _key(*von), RoutingCache.nach_key == _key(*nach))
     .populate_existing().first())


# --- HTTP-Nahtstellen (in Tests gemockt) ---------------------------------------------------

def _ors_matrix(quellen: list[tuple], ziele: list[tuple],
                schluessel: str) -> tuple[list, list] | None:
    orte = [[lon, lat] for lat, lon in quellen] + [[lon, lat] for lat, lon in ziele]
    rumpf = json.dumps({
        "locations": orte,
        "sources": list(range(len(quellen))),
        "destinations": list(range(len(quellen), len(orte))),
        "metrics": ["duration", "distance"],
    }).encode()
    anfrage = urllib.request.Request(
        "https://api.openrouteservice.org/v2/matrix/driving-car", data=rumpf,
        headers={"Authorization": schluessel,
                 "Content-Type": "application/json",
                 "User-Agent": "Friondo-Tool/1.0"})
    with urllib.request.urlopen(anfrage, timeout=TIMEOUT) as antwort:
        daten = json.loads(antwort.read())
    return daten.get("durations"), daten.get("distances")


def _google_matrix(quellen: list[tuple], ziele: list[tuple],
                   schluessel: str) -> tuple[list, list] | None:
    import urllib.parse
    url = ("https://maps.googleapis.com/maps/api/distancematrix/json?"
           + urllib.parse.urlencode({
               "origins": "|".join(f"{lat},{lon}" for lat, lon in quellen),
               "destinations": "|".join(f"{lat},{lon}" for lat, lon in ziele),
               "key": schluessel}))
    anfrage = urllib.request.Request(url, headers={"User-Agent": "Friondo-Tool/1.0"})
    with urllib.request.urlopen(anfrage, timeout=TIMEOUT) as antwort:
        daten = json.loads(antwort.read())
    dauern, strecken = [], []
    for zeile in daten.get("rows", []):
        dauern.append([(e.get("duration", {}).get("value"))
                       for e in zeile.get("elements", [])])
        strecken.append([(e.get("distance", {}).get("value"))
                         for e in zeile.get("elements", [])])
    return dauern, strecken


def matrix_fuellen(session: Session, quellen: list[tuple],
                   ziele: list[tuple]) -> None:
    """EIN gebündelter Matrix-Aufruf (≤ 50 Punkte je Seite) für alle noch
    nicht gecachten Paare; Ergebnisse landen im routing_cache.
    v37: Key aus der .env (ors_schluessel), Tageskontingent – ist es erreicht, bleibt der
    Aufruf aus (fahrzeit() schätzt je Paar) [ANNAHME]."""
    from app import geocoding
    quellen = [q for q in quellen if q and q[0] is not None][:50]
    ziele = [z for z in ziele if z and z[0] is not None][:50]
    if not quellen or not ziele:
        return
    fehlend = [(q, z) for q in quellen for z in ziele
               if q != z and _cache_lesen(session, q, z) is None]
    if not fehlend:
        return
    benutzt = anbieter(session)
    ors_key = ors_schluessel(session)
    google_key = google_schluessel(session)
    if benutzt == "ors" and ors_key:
        if kontingent_status(session)["erschoepft"]:
            _logger.warning("Routing: Tageskontingent erreicht – Fahrzeiten werden geschätzt")
            return
        geocoding._zaehler(session, ZAEHLER_DIENST)
    elif benutzt == "google" and google_key:
        geocoding._zaehler(session, "google_matrix")
    else:
        return   # Luftlinie: kein Netzaufruf, fahrzeit() schätzt je Paar
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Parameter und
    # Cache sind gelesen; der Zähler ist mit dem commit gespeichert)
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    ergebnis = None
    try:
        if benutzt == "ors":
            ergebnis = _ors_matrix(quellen, ziele, ors_key)
        else:
            ergebnis = _google_matrix(quellen, ziele, google_key)
    except Exception as fehler:   # noqa: BLE001 – Fallback Luftlinie, nie blockierend
        _logger.warning("Routing-Matrix (%s) fehlgeschlagen: %s", benutzt, fehler)
        ergebnis = None
    if ergebnis is None or ergebnis[0] is None:
        return   # fahrzeit() fällt je Paar auf die Luftlinie zurück
    dauern, strecken = ergebnis
    for i, q in enumerate(quellen):
        for j, z in enumerate(ziele):
            if q == z:
                continue
            try:
                sekunden = dauern[i][j]
                meter = (strecken[i][j] if strecken else None)
            except (IndexError, TypeError):
                continue
            if sekunden is None:
                continue
            _cache_schreiben(session, q, z, sekunden / 60,
                             (meter or 0) / 1000, benutzt)
    # Lasttest 08.10.2026 (v29): die Cache-Zeilen sofort festschreiben – sonst hält
    # die Anfrage (Terminvorschläge rechnen danach noch Sekunden) die SQLite-
    # Schreibsperre bis zu ihrem Ende und andere Schreiber laufen in „database
    # is locked“ (busy_timeout 5 s). Der Cache ist eigenständige Nutzdaten.
    verbindung_freigeben(session)


def fahrzeit(session: Session, von: tuple | None,
             nach: tuple | None) -> dict:
    """(minuten, km, geschaetzt) – Cache, sonst Luftlinie (nie blockierend);
    echte Werte kommen über matrix_fuellen in den Cache."""
    if (von is None or nach is None or von[0] is None or nach[0] is None):
        return {"minuten": 0.0, "km": 0.0, "geschaetzt": True}
    if von == nach:
        return {"minuten": 0.0, "km": 0.0, "geschaetzt": False}
    zeile = _cache_lesen(session, von, nach)
    if zeile is not None:
        return {"minuten": zeile.minuten, "km": zeile.km,
                "geschaetzt": zeile.anbieter == "luftlinie"}
    minuten, km = _geschaetzt(von, nach)
    _cache_schreiben(session, von, nach, minuten, km, "luftlinie")
    # v33 (PLAN_V20 Phase 172, Vorschlag A 4c): wie in matrix_fuellen den Cache-Eintrag sofort
    # festschreiben, damit die (GET-)Sitzung der Terminvorschläge die SQLite-Schreibsperre nicht
    # bis zum Ende der Berechnung hält (nur im Cache-Miss-Pfad)
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    return {"minuten": round(minuten, 1), "km": round(km, 1),
            "geschaetzt": True}


def strecke(session: Session, von: tuple | None, nach: tuple | None) -> dict:
    """fahrzeit() plus fertiger Anzeigetext (Schlüssel text) – für Templates/JSON."""
    ergebnis = fahrzeit(session, von, nach)
    ergebnis["text"] = strecke_text(ergebnis) if (von and nach and von[0] is not None
                                                  and nach[0] is not None) else ""
    return ergebnis


def verbindung_testen(session: Session) -> str:
    """Parametrierung (v12): Fahrzeit Duisburg Hbf → Moers Bahnhof anzeigen."""
    duisburg = (51.4297, 6.7762)
    moers = (51.4508, 6.6180)
    matrix_fuellen(session, [duisburg], [moers])
    ergebnis = fahrzeit(session, duisburg, moers)
    session.commit()
    return (f"Duisburg Hbf → Moers Bahnhof: {ergebnis['minuten']:.0f} Min, "
            f"{ergebnis['km']:.1f} km"
            + (" (geschätzt, Luftlinie)" if ergebnis["geschaetzt"] else ""))


# --- v37: Prüfpunkt „Routing-Dienst antwortet“ ---------------------------------------------

def dienst_pruefen(session: Session, benutzer=None) -> tuple[bool, str]:
    """Prüfpunkt der Parametrierung (POST …/lead-routing/test, Admin): Matrix 1×1
    Duisburg → Bochum direkt beim Dienst (unabhängig vom Cache), nach
    verbindung_freigeben; Ergebnis „Routing-Dienst antwortet: Duisburg → Bochum 28,0 km ·
    31 Min“ oder ein Fehlertext; ohne Key „ORS_API_KEY fehlt …“. Das Ergebnis wird als
    Parameter routing_pruefung gemerkt (best effort, eigene kurze Transaktion)."""
    from app import geocoding
    from app import leadmanagement as kern
    from app.db import verbindung_freigeben
    ors_key = ors_schluessel(session)
    google_key = google_schluessel(session)
    benutzt = anbieter(session)
    if benutzt == "google" and google_key and not ors_key:
        schluessel, dienst = google_key, "google"
    elif ors_key:
        schluessel, dienst = ors_key, "ors"
    else:
        ok, text = False, KEY_FEHLT_TEXT
        _pruefung_merken(session, ok, text)
        return ok, text
    if kontingent_status(session)["erschoepft"]:
        ok, text = False, kontingent_status(session)["text"]
        _pruefung_merken(session, ok, text)
        return ok, text
    geocoding._zaehler(session, ZAEHLER_DIENST if dienst == "ors" else "google_matrix")
    verbindung_freigeben(session)
    try:
        ergebnis = (_ors_matrix([PRUEF_VON], [PRUEF_NACH], schluessel) if dienst == "ors"
                    else _google_matrix([PRUEF_VON], [PRUEF_NACH], schluessel))
    except Exception as fehler:   # noqa: BLE001 – Fehlertext statt Absturz
        ok, text = False, f"Routing-Dienst antwortet nicht ({dienst}): {_fehlertext(fehler)}"
        _pruefung_merken(session, ok, text)
        return ok, text
    try:
        sekunden = ergebnis[0][0][0]
        meter = ergebnis[1][0][0] if ergebnis[1] else None
    except (TypeError, IndexError, KeyError):
        sekunden, meter = None, None
    if sekunden is None:
        ok, text = False, f"Routing-Dienst ({dienst}) ohne Ergebnis – Antwort unvollständig"
        _pruefung_merken(session, ok, text)
        return ok, text
    werte = {"minuten": sekunden / 60, "km": (meter or 0) / 1000, "geschaetzt": False}
    _cache_schreiben(session, PRUEF_VON, PRUEF_NACH, werte["minuten"], werte["km"], dienst)
    ok, text = True, f"Routing-Dienst antwortet ({dienst}): Duisburg → Bochum {strecke_text(werte)}"
    _pruefung_merken(session, ok, text)
    return ok, text


def _fehlertext(fehler: Exception) -> str:
    import urllib.error
    if isinstance(fehler, urllib.error.HTTPError):
        if fehler.code in (401, 403):
            return f"HTTP {fehler.code} – Key abgelehnt oder Kontingent erschöpft"
        return f"HTTP {fehler.code}"
    text = str(fehler) or fehler.__class__.__name__
    return text[:160]


def _pruefung_merken(session: Session, ok: bool, text: str) -> None:
    """Letztes Prüfergebnis als Lead-Parameter (Anzeige in den Lead-Einstellungen)."""
    from app import leadmanagement as kern
    try:
        kern.parameter_setzen(session, PRUEFUNG_PARAMETER,
                              f"{datetime.now():%d.%m.%Y %H:%M} · {'OK' if ok else 'Fehler'} · {text}"[:500])
        session.commit()
    except Exception:   # noqa: BLE001 – best effort
        session.rollback()


def letzte_pruefung(session: Session) -> str:
    from app import leadmanagement as kern
    return kern.parameter_holen(session, PRUEFUNG_PARAMETER, "") or ""


def einstellungen_kontext(session: Session) -> dict:
    """Abschnitt „Routing“ in Lead-Einstellungen und Lead-Routing: Key-Status aus der .env
    (nie der Wert), Anbieter, Zähler/Kontingent, 80-%-Hinweis, letztes Prüfergebnis."""
    quelle = ors_schluessel_quelle(session)
    benutzt = anbieter(session)
    status = kontingent_status(session)
    if quelle == "env":
        key_text = "ORS_API_KEY in der .env vorhanden"
    elif quelle == "parameter":
        key_text = "Key nur im Lead-Parameter ors_api_key (Rückfall) – besser in die .env (ORS_API_KEY)"
    else:
        key_text = KEY_FEHLT_TEXT
    hinweis = ""
    if quelle and benutzt != "ors":
        hinweis = (f"Anbieter steht auf „{benutzt}“ – mit vorhandenem Key setzt die Migration beim "
                   "nächsten Update „ors“; sofort unter Lead-Routing umstellen.")
    return {"key_quelle": quelle, "key_vorhanden": bool(quelle), "key_text": key_text,
            "anbieter": benutzt, "aktiv": dienst_aktiv(session), "hinweis": hinweis,
            "zaehler": status, "letzte_pruefung": letzte_pruefung(session),
            "kontingent_parameter": KONTINGENT_PARAMETER,
            "warnung_prozent": KONTINGENT_WARNUNG_PROZENT}


def migration_v37_routing(session: Session) -> list[str]:
    """Idempotent (Hook in migrate.py durch den Orchestrator): liegt ein ORS-Key vor
    (.env oder Parameter) und steht routing_anbieter noch auf „luftlinie“, wird „ors“
    gesetzt; der Parameter routing_kontingent_tag bekommt seinen Standard, wenn er fehlt.
    Ohne Key bleibt „luftlinie“ + Hinweis (keine Änderung)."""
    from app import leadmanagement as kern
    from app.models import LeadParameter
    meldungen = []
    if session.query(LeadParameter).filter(LeadParameter.name == KONTINGENT_PARAMETER).first() is None:
        kern.parameter_setzen(session, KONTINGENT_PARAMETER, str(KONTINGENT_STANDARD))
        meldungen.append(f"Routing (v37): Parameter {KONTINGENT_PARAMETER} = {KONTINGENT_STANDARD} angelegt")
    if ors_schluessel(session) and anbieter(session) == "luftlinie":
        kern.parameter_setzen(session, "routing_anbieter", "ors")
        meldungen.append("Routing (v37): routing_anbieter luftlinie -> ors (ORS-Key vorhanden)")
    elif not ors_schluessel(session) and anbieter(session) == "luftlinie":
        meldungen.append("Routing (v37): ORS_API_KEY fehlt - Anbieter bleibt luftlinie (geschaetzt)")
    return meldungen
