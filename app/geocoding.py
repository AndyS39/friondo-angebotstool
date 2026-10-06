# Geocoding (v12, Phase 77): Adresse → Koordinaten mit Cache; Anbieter laut
# lead_parameter routing_anbieter (ors / google / luftlinie=Nominatim).
# Nominatim: max. 1 Anfrage/s, fester User-Agent, countrycodes=de.
# Alle Aufrufe Timeout 8 s; Fehler blockieren nie (status=fehler → Liste
# „Adresse prüfen“ mit manueller Pin-Setzung).
# v27 (PLAN_V17 Phase 128): Backoff für Adressen mit Status „fehler“ (Spalte
# geocode_cache.versuche: nach dem 1. Fehlversuch 1 h, nach dem 2. 6 h, ab dem
# 3. 24 h Pause; Erfolg setzt versuche auf 0 – gilt auch für die direkten
# Aufrufe aus Kundenkartei/Terminvorschlägen, dort kostet eine Adresse in der
# Pause nur eine Cache-Abfrage). Der Hintergrundlauf ist am Scheduler-Rahmen
# registriert und arbeitet je Adresse in kurzen Sitzungen: lesen → Sitzung zu →
# Netz → kurze Sitzung schreiben → Commit (Block = eine Adresse). Befund v27:
# Vorgänge mit geocode_status „fehler“ wurden bisher nie wieder angefasst,
# Termin- und AD-Startadressen mit Fehlstatus dagegen alle 5 Minuten erneut
# beim Anbieter angefragt – beides regelt jetzt der Backoff.

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

# v27 (Phase 128): Pausen nach dem 1., 2. und ab dem 3. Fehlversuch
BACKOFF_PAUSEN = (timedelta(hours=1), timedelta(hours=6), timedelta(hours=24))
LAUF_LIMIT = 25            # Adressen je Bereich und Lauf (wie bisher)
TERMIN_HORIZONT_TAGE = 60
OFFENE_PHASEN = ("neu", "in_kontaktierung", "qualifiziert", "terminiert")


def adresse_normalisieren(adresse: str) -> str:
    return re.sub(r"\s+", " ", (adresse or "").strip().lower())[:300]


def backoff_pause(versuche: int) -> timedelta:
    """Pause nach `versuche` Fehlversuchen: 1 h, 6 h, ab dem dritten 24 h."""
    versuche = int(versuche or 0)
    if versuche <= 0:
        return timedelta(0)
    return BACKOFF_PAUSEN[min(versuche, len(BACKOFF_PAUSEN)) - 1]


def erneut_faellig(cache: GeocodeCache | None, jetzt: datetime | None = None) -> bool:
    """Darf eine Adresse wieder beim Anbieter angefragt werden? True ohne
    Cache-Zeile, bei Status ok/manuell (wird ohnehin aus dem Cache bedient),
    ohne gezählte Fehlversuche (Bestand vor v27) oder nach Ablauf der Pause."""
    if cache is None or cache.status != "fehler":
        return True
    versuche = int(cache.versuche or 0)
    if versuche <= 0 or cache.stand is None:
        return True
    return (jetzt or datetime.now()) >= cache.stand + backoff_pause(versuche)


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


# --- v27: drei Phasen je Adresse (lesen → Netz ohne Sitzung → schreiben) ------------

def vorbereiten(session: Session, adresse: str) -> dict:
    """Lesephase (kurze Sitzung): Cache-Treffer, Backoff-Pause oder Auftrag für
    den Anbieter. Liefert {"norm", "adresse", "treffer": (lat, lon, status) |
    None, "backoff": bool, "anbieter", "schluessel", "versuche"}. Ohne Treffer
    ist der Tageszähler bereits erhöht (der Aufrufer committet bzw. gibt frei)."""
    from app import leadmanagement as kern
    norm = adresse_normalisieren(adresse)
    auftrag = {"norm": norm, "adresse": adresse, "treffer": None, "backoff": False,
               "anbieter": "", "schluessel": "", "versuche": 0}
    if not norm:
        auftrag["treffer"] = (None, None, "fehler")
        return auftrag
    cache = (session.query(GeocodeCache)
             .filter(GeocodeCache.adresse_norm == norm).first())
    if cache is not None and cache.status in ("ok", "manuell"):
        auftrag["treffer"] = (cache.lat, cache.lon, "ok")
        return auftrag
    if not erneut_faellig(cache):
        # Backoff: in der Pause kein Anbieter-Aufruf, Status bleibt „fehler“
        auftrag["treffer"] = (None, None, "fehler")
        auftrag["backoff"] = True
        return auftrag
    auftrag["versuche"] = int(cache.versuche or 0) if cache is not None else 0
    anbieter = kern.parameter_holen(session, "routing_anbieter", "luftlinie")
    ors_key = kern.parameter_holen(session, "ors_api_key")
    google_key = kern.parameter_holen(session, "google_api_key")
    if anbieter == "ors" and ors_key:
        benutzt, schluessel = "ors", ors_key
    elif anbieter == "google" and google_key:
        benutzt, schluessel = "google", google_key
    else:
        benutzt, schluessel = "nominatim", ""
    _zaehler(session, f"{benutzt}_geocode" if benutzt != "nominatim" else "nominatim")
    auftrag.update(anbieter=benutzt, schluessel=schluessel)
    return auftrag


def anbieter_aufrufen(auftrag: dict) -> tuple[float, float] | None:
    """Netzphase – OHNE Sitzung (bis zu TIMEOUT Sekunden, Nominatim wartet
    zusätzlich auf den 1-s-Takt). Fehler → None (Status fehler, Backoff)."""
    try:
        if auftrag["anbieter"] == "ors":
            return _ors(auftrag["adresse"], auftrag["schluessel"])
        if auftrag["anbieter"] == "google":
            return _google(auftrag["adresse"], auftrag["schluessel"])
        return _nominatim(auftrag["adresse"])
    except Exception:
        return None


def ergebnis_schreiben(session: Session, auftrag: dict,
                       ergebnis: tuple[float, float] | None
                       ) -> tuple[float | None, float | None, str]:
    """Schreibphase (kurze Sitzung): Upsert der Cache-Zeile. Erfolg setzt
    versuche auf 0, ein Fehlversuch zählt hoch (Backoff 1 h / 6 h / 24 h).
    Hotfix 06.10.2026: Upsert statt Lesen+Einfügen – parallele Anfragen für
    dieselbe Adresse liefen sonst in „UNIQUE constraint failed“ (adresse_norm)."""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    werte = {"anbieter": auftrag["anbieter"], "stand": datetime.now()}
    if ergebnis is not None:
        werte.update(lat=ergebnis[0], lon=ergebnis[1], status="ok", versuche=0)
    else:
        werte.update(status="fehler", versuche=int(auftrag.get("versuche", 0)) + 1)
    anweisung = sqlite_insert(GeocodeCache).values(adresse_norm=auftrag["norm"], **werte)
    session.execute(anweisung.on_conflict_do_update(
        index_elements=["adresse_norm"], set_=werte))
    cache = (session.query(GeocodeCache)
             .filter(GeocodeCache.adresse_norm == auftrag["norm"])
             .populate_existing().first())
    if cache is not None and cache.status in ("ok", "manuell"):
        return cache.lat, cache.lon, "ok"
    return None, None, "fehler"


def geokodieren(session: Session, adresse: str) -> tuple[float | None, float | None, str]:
    """Cache → Anbieter. Liefert (lat, lon, status ok|fehler). Aufruf mit
    Request-Session (Kundenkartei, Terminassistent, AD-Profil): vor dem Netz-
    aufruf wird die Verbindung freigegeben (Hotfix 06.10.2026); der v27-Backoff
    gilt hier ebenso – eine Adresse in der Fehlerpause kostet nur eine
    Cache-Abfrage und verschlechtert die Antwortzeit nicht."""
    auftrag = vorbereiten(session, adresse)
    if auftrag["treffer"] is not None:
        return auftrag["treffer"]
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Cache-Zeile,
    # Anbieter und Schlüssel sind gelesen; der Zähler ist mit dem commit
    # gespeichert) – der Geocoder braucht bis zu TIMEOUT Sekunden
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    ergebnis = anbieter_aufrufen(auftrag)
    return ergebnis_schreiben(session, auftrag, ergebnis)


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
    cache.versuche = 0   # v27: Backoff zurücksetzen
    session.flush()


def _adresse_text(strasse, plz, ort) -> str:
    return ", ".join(x for x in (strasse or "", f"{plz or ''} {ort or ''}".strip()) if x)


def lead_adresse(session: Session, vorgang) -> str:
    from app.models import Kunde
    kunde = session.get(Kunde, vorgang.kunde_id)
    if kunde is None:
        return ""
    return _adresse_text(kunde.strasse, kunde.plz, kunde.ort)


# --- Hintergrundlauf (alle 5 Minuten, Scheduler-Rahmen) -------------------------------

def _cache_zeilen(session: Session, normen: list[str]) -> dict[str, GeocodeCache]:
    zeilen: dict[str, GeocodeCache] = {}
    for i in range(0, len(normen), 400):   # Grenze der SQLite-Hostparameter
        for cache in (session.query(GeocodeCache)
                      .filter(GeocodeCache.adresse_norm.in_(normen[i:i + 400]))):
            zeilen[cache.adresse_norm] = cache
    return zeilen


def _offene_leads(session: Session, limit: int) -> list[tuple[int, str]]:
    """(vorgang_id, adresse) offener Leads ohne Koordinaten: zuerst die noch nie
    versuchten, dann – mit dem Rest des Limits – die mit Status „fehler“, deren
    Backoff-Pause abgelaufen ist (vor v27 wurden diese nie wieder versucht)."""
    from app.models import Kunde, Vorgang
    basis = (session.query(Vorgang.id, Vorgang.geocode_status, Kunde.strasse,
                           Kunde.plz, Kunde.ort)
             .outerjoin(Kunde, Kunde.id == Vorgang.kunde_id)
             .filter(Vorgang.lead_phase.in_(OFFENE_PHASEN), Vorgang.lat.is_(None)))
    neue = (basis.filter((Vorgang.geocode_status.is_(None))
                         | (Vorgang.geocode_status == ""))
            .order_by(Vorgang.id).limit(limit).all())
    ergebnis = [(z[0], _adresse_text(z[2], z[3], z[4])) for z in neue]
    rest = limit - len(ergebnis)
    if rest <= 0:
        return ergebnis
    fehlgeschlagen = [(z[0], _adresse_text(z[2], z[3], z[4])) for z in
                      basis.filter(Vorgang.geocode_status == "fehler")
                      .order_by(Vorgang.id).all()]
    if not fehlgeschlagen:
        return ergebnis
    zeilen = _cache_zeilen(session, [adresse_normalisieren(a) for _, a in fehlgeschlagen])
    jetzt = datetime.now()
    for vorgang_id, adresse in fehlgeschlagen:
        if erneut_faellig(zeilen.get(adresse_normalisieren(adresse)), jetzt):
            ergebnis.append((vorgang_id, adresse))
            if len(ergebnis) >= limit:
                break
    return ergebnis


def _offene_termine(session: Session, limit: int) -> list[tuple[int, str]]:
    """(termin_id, adresse) der Termine der nächsten 60 Tage ohne Koordinaten."""
    from app.models import VotTermin
    grenze = datetime.now() + timedelta(days=TERMIN_HORIZONT_TAGE)
    return [(z[0], z[1]) for z in
            session.query(VotTermin.id, VotTermin.adresse)
            .filter(VotTermin.lat.is_(None), VotTermin.adresse != "",
                    VotTermin.beginn.isnot(None), VotTermin.beginn <= grenze)
            .order_by(VotTermin.id).limit(limit).all()]


def _offene_profile(session: Session) -> list[tuple[int, str]]:
    """(profil_id, start_adresse) der AD-Profile ohne Startkoordinaten."""
    from app.models import AdProfil
    return [(z[0], z[1]) for z in
            session.query(AdProfil.id, AdProfil.start_adresse)
            .filter(AdProfil.start_lat.is_(None), AdProfil.start_adresse != "")
            .order_by(AdProfil.id).all()]


def _einzeln(adresse: str, schreiben) -> str:
    """EINE Adresse nach dem v27-Muster: kurze Sitzung lesen → Sitzung zu →
    Netz → kurze Sitzung: Cache-Zeile und Ziel schreiben → Commit.
    `schreiben(s, lat, lon, status)` trägt das Ergebnis am Vorgang/Termin/
    Profil ein. Liefert ok | fehler | backoff."""
    from app.db import kurz
    with kurz() as s:
        auftrag = vorbereiten(s, adresse)
    ergebnis = None
    if auftrag["treffer"] is None:
        ergebnis = anbieter_aufrufen(auftrag)   # Netz ohne Sitzung
    with kurz() as s:
        if auftrag["treffer"] is None:
            lat, lon, status = ergebnis_schreiben(s, auftrag, ergebnis)
        else:
            lat, lon, status = auftrag["treffer"]
        schreiben(s, lat, lon, status)
    return "backoff" if auftrag["backoff"] else status


def hintergrund_lauf(limit: int = LAUF_LIMIT) -> dict:
    """Alle 5 Minuten: offene Leads (neu … terminiert), Termine der nächsten
    60 Tage und AD-Startadressen geokodieren; Fehler → geocode_status=fehler.
    v27 (PLAN_V17 Phase 128): IDs und Adressen je Bereich in einer kurzen
    Sitzung lesen, dann je Adresse lesen → Netz → schreiben → Commit; keine
    Sitzung während Netz-I/O, Schreibsperre je Adresse nur Millisekunden."""
    from app.db import kurz
    from app.models import AdProfil, Vorgang, VotTermin
    zaehler = {"ok": 0, "fehler": 0, "backoff": 0, "termine": 0, "profile": 0}
    with kurz() as s:
        leads = _offene_leads(s, limit)
    for vorgang_id, adresse in leads:
        def vorgang_schreiben(s, lat, lon, status, _id=vorgang_id):
            vorgang = s.get(Vorgang, _id)
            if vorgang is not None:
                vorgang.lat, vorgang.lon = lat, lon
                vorgang.geocode_status = status
        zaehler[_einzeln(adresse, vorgang_schreiben)] += 1
    with kurz() as s:
        termine = _offene_termine(s, limit)
    for termin_id, adresse in termine:
        def termin_schreiben(s, lat, lon, status, _id=termin_id):
            termin = s.get(VotTermin, _id)
            if termin is not None and status == "ok":
                termin.lat, termin.lon = lat, lon
        if _einzeln(adresse, termin_schreiben) == "ok":
            zaehler["termine"] += 1
    with kurz() as s:
        profile = _offene_profile(s)
    for profil_id, adresse in profile:
        def profil_schreiben(s, lat, lon, status, _id=profil_id):
            profil = s.get(AdProfil, _id)
            if profil is not None and status == "ok":
                profil.start_lat, profil.start_lon = lat, lon
        if _einzeln(adresse, profil_schreiben) == "ok":
            zaehler["profile"] += 1
    return zaehler


def scheduler_lauf() -> dict:
    return hintergrund_lauf()


def scheduler_starten() -> None:
    """v27 (PLAN_V17 Phase 128): registriert den 5-Minuten-Lauf nur noch am
    Scheduler-Rahmen (Startverzögerung 300 s wie bisher); Threads startet
    main.lifespan über scheduler.starten_alle()."""
    from app import scheduler
    scheduler.registrieren(
        "geocoding", 300, scheduler_lauf,
        beschreibung="Adressen offener Leads, Termine (60 Tage) und AD-Startadressen "
                     "geokodieren – Backoff 1 h/6 h/24 h bei Fehlern",
        start_verzoegerung_s=300)
