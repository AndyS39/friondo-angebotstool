# Routing (v12, Phase 77): Fahrzeiten mit 90-Tage-Cache; Anbieter ors-Matrix,
# Google Route Matrix oder Luftlinie × 1,3 bei 45 km/h (Kennzeichen
# „geschätzt“). Matrix-Aufrufe werden je Assistenten-Lauf gebündelt.
# Alle Aufrufe Timeout 8 s, Fehler nie blockierend (Fallback Luftlinie).

import json
import math
import urllib.request
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import RoutingCache

TIMEOUT = 8
CACHE_TAGE = 90


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
    zeile = (session.query(RoutingCache)
             .filter(RoutingCache.von_key == _key(*von),
                     RoutingCache.nach_key == _key(*nach)).first())
    if zeile is None:
        zeile = RoutingCache(von_key=_key(*von), nach_key=_key(*nach))
        session.add(zeile)
    zeile.minuten = round(minuten, 1)
    zeile.km = round(km, 1)
    zeile.anbieter = anbieter
    zeile.gueltig_bis = datetime.now() + timedelta(days=CACHE_TAGE)
    session.flush()


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
    nicht gecachten Paare; Ergebnisse landen im routing_cache."""
    from app import geocoding
    from app import leadmanagement as kern
    quellen = [q for q in quellen if q and q[0] is not None][:50]
    ziele = [z for z in ziele if z and z[0] is not None][:50]
    if not quellen or not ziele:
        return
    fehlend = [(q, z) for q in quellen for z in ziele
               if q != z and _cache_lesen(session, q, z) is None]
    if not fehlend:
        return
    anbieter = kern.parameter_holen(session, "routing_anbieter", "luftlinie")
    ergebnis = None
    try:
        if anbieter == "ors" and kern.parameter_holen(session, "ors_api_key"):
            geocoding._zaehler(session, "ors_matrix")
            ergebnis = _ors_matrix(quellen, ziele,
                                   kern.parameter_holen(session, "ors_api_key"))
        elif anbieter == "google" and kern.parameter_holen(session,
                                                           "google_api_key"):
            geocoding._zaehler(session, "google_matrix")
            ergebnis = _google_matrix(
                quellen, ziele, kern.parameter_holen(session, "google_api_key"))
    except Exception:
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
                             (meter or 0) / 1000, anbieter)


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
    return {"minuten": round(minuten, 1), "km": round(km, 1),
            "geschaetzt": True}


def verbindung_testen(session: Session) -> str:
    """Parametrierung: Fahrzeit Duisburg Hbf → Moers Bahnhof anzeigen."""
    duisburg = (51.4297, 6.7762)
    moers = (51.4508, 6.6180)
    matrix_fuellen(session, [duisburg], [moers])
    ergebnis = fahrzeit(session, duisburg, moers)
    session.commit()
    return (f"Duisburg Hbf → Moers Bahnhof: {ergebnis['minuten']:.0f} Min, "
            f"{ergebnis['km']:.1f} km"
            + (" (geschätzt, Luftlinie)" if ergebnis["geschaetzt"] else ""))
