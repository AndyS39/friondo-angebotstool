# Geocoding (v12, Phase 77): Adresse → Koordinaten mit Cache; Anbieter laut
# lead_parameter routing_anbieter (ors / google / luftlinie=Nominatim).
# Nominatim: max. 1 Anfrage/s, fester User-Agent, countrycodes=de.
# Alle Aufrufe Timeout 8 s; Fehler blockieren nie (status=fehler → Liste
# „Adresse prüfen“ mit manueller Pin-Setzung).

import json
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import GeocodeCache

TIMEOUT = 8
USER_AGENT = "Friondo-Tool/1.0 (info@friondo.de)"
_nominatim_sperre = threading.Lock()
_nominatim_zuletzt = [0.0]


def adresse_normalisieren(adresse: str) -> str:
    return re.sub(r"\s+", " ", (adresse or "").strip().lower())[:300]


def _zaehler(session: Session, dienst: str) -> None:
    """Tageszähler der externen Aufrufe (Anzeige in der Parametrierung)."""
    from app import leadmanagement as kern
    schluessel = f"aufrufe_{dienst}_{datetime.now().date().isoformat()}"
    try:
        stand = int(kern.parameter_holen(session, schluessel, "0"))
    except ValueError:
        stand = 0
    kern.parameter_setzen(session, schluessel, str(stand + 1))


def _abrufen(url: str, kopf: dict | None = None) -> dict | list:
    anfrage = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                   **(kopf or {})})
    with urllib.request.urlopen(anfrage, timeout=TIMEOUT) as antwort:
        return json.loads(antwort.read())


def _nominatim(adresse: str) -> tuple[float, float] | None:
    with _nominatim_sperre:   # Nutzungsrichtlinie: max. 1 Anfrage je Sekunde
        wartezeit = 1.0 - (time.monotonic() - _nominatim_zuletzt[0])
        if wartezeit > 0:
            time.sleep(wartezeit)
        _nominatim_zuletzt[0] = time.monotonic()
    daten = _abrufen("https://nominatim.openstreetmap.org/search?"
                     + urllib.parse.urlencode({"q": adresse, "format": "json",
                                               "limit": 1,
                                               "countrycodes": "de"}))
    if daten:
        return float(daten[0]["lat"]), float(daten[0]["lon"])
    return None


def _ors(adresse: str, schluessel: str) -> tuple[float, float] | None:
    daten = _abrufen("https://api.openrouteservice.org/geocode/search?"
                     + urllib.parse.urlencode({"api_key": schluessel,
                                               "text": adresse,
                                               "boundary.country": "DE",
                                               "size": 1}))
    treffer = daten.get("features") or []
    if treffer:
        lon, lat = treffer[0]["geometry"]["coordinates"]
        return float(lat), float(lon)
    return None


def _google(adresse: str, schluessel: str) -> tuple[float, float] | None:
    daten = _abrufen("https://maps.googleapis.com/maps/api/geocode/json?"
                     + urllib.parse.urlencode({"address": adresse,
                                               "region": "de",
                                               "key": schluessel}))
    treffer = daten.get("results") or []
    if treffer:
        ort = treffer[0]["geometry"]["location"]
        return float(ort["lat"]), float(ort["lng"])
    return None


def geokodieren(session: Session, adresse: str) -> tuple[float | None, float | None, str]:
    """Cache → Anbieter. Liefert (lat, lon, status ok|fehler)."""
    from app import leadmanagement as kern
    norm = adresse_normalisieren(adresse)
    if not norm:
        return None, None, "fehler"
    cache = (session.query(GeocodeCache)
             .filter(GeocodeCache.adresse_norm == norm).first())
    if cache is not None and cache.status in ("ok", "manuell"):
        return cache.lat, cache.lon, "ok"
    anbieter = kern.parameter_holen(session, "routing_anbieter", "luftlinie")
    ergebnis = None
    benutzt = "nominatim"
    try:
        if anbieter == "ors" and kern.parameter_holen(session, "ors_api_key"):
            benutzt = "ors"
            _zaehler(session, "ors_geocode")
            ergebnis = _ors(adresse, kern.parameter_holen(session, "ors_api_key"))
        elif anbieter == "google" and kern.parameter_holen(session, "google_api_key"):
            benutzt = "google"
            _zaehler(session, "google_geocode")
            ergebnis = _google(adresse,
                               kern.parameter_holen(session, "google_api_key"))
        else:
            _zaehler(session, "nominatim")
            ergebnis = _nominatim(adresse)
    except Exception:
        ergebnis = None
    if cache is None:
        cache = GeocodeCache(adresse_norm=norm)
        session.add(cache)
    cache.anbieter = benutzt
    cache.stand = datetime.now()
    if ergebnis is not None:
        cache.lat, cache.lon = ergebnis
        cache.status = "ok"
        session.flush()
        return cache.lat, cache.lon, "ok"
    cache.status = "fehler"
    session.flush()
    return None, None, "fehler"


def pin_setzen(session: Session, adresse: str, lat: float, lon: float) -> None:
    """Manuelle Pin-Setzung („Adresse prüfen“): Status manuell überschreibt."""
    norm = adresse_normalisieren(adresse)
    cache = (session.query(GeocodeCache)
             .filter(GeocodeCache.adresse_norm == norm).first())
    if cache is None:
        cache = GeocodeCache(adresse_norm=norm)
        session.add(cache)
    cache.lat, cache.lon = lat, lon
    cache.status = "manuell"
    cache.anbieter = "manuell"
    cache.stand = datetime.now()
    session.flush()


def lead_adresse(session: Session, vorgang) -> str:
    from app.models import Kunde
    kunde = session.get(Kunde, vorgang.kunde_id)
    if kunde is None:
        return ""
    return ", ".join(x for x in (kunde.strasse,
                                 f"{kunde.plz} {kunde.ort}".strip()) if x)


def hintergrund_lauf(session: Session | None = None, limit: int = 25) -> dict:
    """Alle 5 Minuten: offene Leads (neu … terminiert), Termine der nächsten
    60 Tage und AD-Startadressen geokodieren; Fehler → geocode_status=fehler."""
    from app.db import SessionLocal
    from app.models import AdProfil, Vorgang, VotTermin
    eigen = session is None
    if eigen:
        session = SessionLocal()
    zaehler = {"ok": 0, "fehler": 0}
    try:
        offen = (session.query(Vorgang)
                 .filter(Vorgang.lead_phase.in_(
                     ("neu", "in_kontaktierung", "qualifiziert", "terminiert")),
                         Vorgang.lat.is_(None),
                         (Vorgang.geocode_status.is_(None))
                         | (Vorgang.geocode_status == ""))
                 .limit(limit).all())
        for vorgang in offen:
            adresse = lead_adresse(session, vorgang)
            lat, lon, status = geokodieren(session, adresse)
            vorgang.lat, vorgang.lon = lat, lon
            vorgang.geocode_status = status
            zaehler["ok" if status == "ok" else "fehler"] += 1
        grenze = datetime.now() + timedelta(days=60)
        for termin in (session.query(VotTermin)
                       .filter(VotTermin.lat.is_(None),
                               VotTermin.adresse != "",
                               VotTermin.beginn.isnot(None),
                               VotTermin.beginn <= grenze)
                       .limit(limit)):
            lat, lon, status = geokodieren(session, termin.adresse)
            if status == "ok":
                termin.lat, termin.lon = lat, lon
        for profil in (session.query(AdProfil)
                       .filter(AdProfil.start_lat.is_(None),
                               AdProfil.start_adresse != "")):
            lat, lon, status = geokodieren(session, profil.start_adresse)
            if status == "ok":
                profil.start_lat, profil.start_lon = lat, lon
        session.commit()
        return zaehler
    finally:
        if eigen:
            session.close()


_scheduler_laeuft = False


def scheduler_starten() -> None:
    global _scheduler_laeuft
    if _scheduler_laeuft:
        return
    _scheduler_laeuft = True

    def schleife():
        time.sleep(300)
        while True:
            try:
                hintergrund_lauf()
            except Exception:
                pass
            time.sleep(300)

    threading.Thread(target=schleife, daemon=True, name="geocoding").start()
