# v27 (PLAN_V17 Phase 128) – Scheduler-Rahmen für alle acht Hintergrundläufe,
# Sitzungsdisziplin, Blöcke mit Commit, Geocoding-Backoff.
# (a) acht scheduler_starten() registrieren genau die acht Namen, ohne Threads
# (b) Single-Flight: ein laufender Lauf wird beim zweiten ausfuehren übersprungen
# (c) Pflichttest: 1.000 Geocoding-Adressen halten die Schreibsperre nie > 1 s
#     (paralleler Schreiber misst seine Commit-Dauer)
# (d) Backoff: Adresse mit Status fehler wird in der Pause nicht erneut abgefragt,
#     danach schon; Erfolg setzt versuche=0
# (e) Status-Tabelle scheduler_status, Fehler eines Laufs, Schleife lebt weiter
# (f) aktiv-Bedingung: ohne monday-Token „inaktiv (kein monday-Token)“
# Dazu: Blöcke (lead_mail je Eintrag, monday je 200 Items), Teilschritt-
# Absicherung (mail-sync, leadmanagement), Löschlauf-Kandidaten per Mengenabfrage.
# Läuft gegen die Entwicklungs-DB; Testdaten tragen das Präfix „V27A“ und werden
# wieder entfernt; Parameter werden über frische Sitzungen gesetzt und
# zurückgesetzt. Kein echter Netzzugriff (Geocoder, Graph und monday gemockt).
import inspect
import threading
import time
import unittest

import pytest
from datetime import datetime, timedelta
from unittest import mock

from app import (ablauf_pruefung, benachrichtigungen, betrieb, config, db,
                 geocoding, graph_versand, lead_anrufliste, lead_mail,
                 lead_parser, lead_todos, leadmanagement, mail_sync,
                 monday_sync, scheduler)
from app.db import init_db
from app.models import (Angebot, GeocodeCache, KommunikationLog, Kunde, Lead,
                        LeadAktivitaet, LeadParameter, SchedulerStatus,
                        Vorgang, VotTermin)

PRAEFIX = "V27A"
ACHT = {"monday-sync", "mail-sync", "ablauf-pruefung", "benachrichtigungen",
        "lead-parser", "leadmanagement", "geocoding", "lead-mail",
        "mail-ausgang"}   # v27: Ausgangs-Warteschlange (benachrichtigungen.scheduler_starten)
MODULE = (monday_sync, mail_sync, ablauf_pruefung, benachrichtigungen,
          lead_parser, leadmanagement, geocoding, lead_mail)
ERWARTET = {   # Name: (Intervall s, Startverzögerung s)
    "monday-sync": (900, 0), "mail-sync": (900, 0), "ablauf-pruefung": (86400, 120),
    "benachrichtigungen": (300, 180), "lead-parser": (120, 240),
    "leadmanagement": (300, 200), "geocoding": (300, 300), "lead-mail": (60, 150),
    "mail-ausgang": (60, 90),
}


_BASIS = {"wert": 0}


@pytest.fixture(autouse=True, scope="module")
def _pool_basis():
    """Verbindungen, die andere Testmodule offen halten, nicht mitzählen."""
    _BASIS["wert"] = db.engine.pool.checkedout()
    yield


def belegt() -> int:
    """Aktuell aus dem Pool entnommene Verbindungen (relativ zur Modul-Basis)."""
    return db.engine.pool.checkedout() - _BASIS["wert"]


def alle_registrieren() -> None:
    for modul in MODULE:
        modul.scheduler_starten()


def param_holen(name: str):
    with db.kurz() as s:
        zeile = s.query(LeadParameter).filter_by(name=name).first()
        return zeile.wert if zeile is not None else None


def param_setzen(name: str, wert) -> None:
    with db.kurz() as s:
        if wert is None:
            s.query(LeadParameter).filter_by(name=name).delete(synchronize_session=False)
        else:
            leadmanagement.parameter_setzen(s, name, wert)


class Basis(unittest.TestCase):
    """Registry frisch aufsetzen; am Ende wieder den Startzustand herstellen
    (keine Threads – starten_alle() ruft nur main.lifespan)."""

    @classmethod
    def setUpClass(cls):
        init_db()
        with db.kurz() as s:
            cls.status_vorher = {z.name for z in s.query(SchedulerStatus)}
        scheduler.zuruecksetzen_fuer_tests()
        alle_registrieren()

    @classmethod
    def tearDownClass(cls):
        scheduler.zuruecksetzen_fuer_tests()
        alle_registrieren()
        betrieb.scheduler_registrieren()
        with db.kurz() as s:
            for zeile in s.query(SchedulerStatus):
                if zeile.name.startswith("v27a-") or (
                        zeile.name in ACHT and zeile.name not in cls.status_vorher):
                    s.delete(zeile)


# --- (a) Registrierung, (b) Single-Flight, (f) aktiv ---------------------------------

class Registrierung(Basis):
    def test_acht_laeufe_ohne_threads(self):
        scheduler.zuruecksetzen_fuer_tests()
        vorher = threading.active_count()
        alle_registrieren()
        self.assertEqual({lauf.name for lauf in scheduler.alle()}, ACHT)
        self.assertEqual(threading.active_count(), vorher, "Module dürfen keine Threads starten")
        self.assertEqual(scheduler.anzahl(), len(ACHT))
        alle_registrieren()                                   # idempotent
        self.assertEqual(scheduler.anzahl(), len(ACHT))
        for name, (intervall, verzoegerung) in ERWARTET.items():
            lauf = scheduler.holen(name)
            self.assertIsNotNone(lauf, name)
            self.assertEqual((lauf.intervall_s, lauf.start_verzoegerung_s),
                             (intervall, verzoegerung), name)
            self.assertTrue(lauf.beschreibung, f"{name}: Beschreibung fehlt")
            self.assertIsNone(lauf.thread)
        for modul in MODULE:
            quelle = inspect.getsource(modul)
            self.assertNotIn("threading.Thread(", quelle, modul.__name__)
            self.assertNotIn("_scheduler_laeuft", quelle, modul.__name__)
            self.assertNotIn("_scheduler_gestartet", quelle, modul.__name__)

    def test_single_flight(self):
        gestartet = threading.Event()

        def lang():
            gestartet.set()
            time.sleep(1.0)
            return {"ok": 1}

        scheduler.registrieren("v27a-lang", 60, lang, beschreibung="Single-Flight-Test")
        ergebnisse: dict = {}
        faden = threading.Thread(
            target=lambda: ergebnisse.update(erster=scheduler.ausfuehren("v27a-lang")))
        faden.start()
        self.assertTrue(gestartet.wait(2))
        zweiter = scheduler.ausfuehren("v27a-lang")
        faden.join(5)
        self.assertTrue(zweiter["uebersprungen"])
        self.assertEqual(zweiter["grund"], "läuft bereits")
        self.assertFalse(ergebnisse["erster"]["uebersprungen"])
        self.assertTrue(ergebnisse["erster"]["ok"])
        lauf = scheduler.holen("v27a-lang")
        self.assertEqual((lauf.laeufe, lauf.fehler, lauf.letztes_ergebnis), (1, 0, "ok=1"))

    def test_aktiv_bedingungen(self):
        with mock.patch.object(config, "MONDAY_API_TOKEN", ""):
            eintrag = next(z for z in scheduler.status_liste() if z["name"] == "monday-sync")
            self.assertEqual(eintrag["zustand"], "inaktiv (kein monday-Token)")
            self.assertFalse(eintrag["aktiv"])
            self.assertFalse(eintrag["ueberfaellig"])
            ergebnis = scheduler.ausfuehren("monday-sync")      # Scheduler-Auslöser
            self.assertTrue(ergebnis["uebersprungen"])
            self.assertEqual(ergebnis["grund"], "kein monday-Token")
        with mock.patch.object(config, "MONDAY_API_TOKEN", "v27a-test"):
            self.assertEqual(scheduler.holen("monday-sync").ist_aktiv(), (True, ""))
        with mock.patch.object(config, "GRAPH_CLIENT_ID", ""):
            self.assertEqual(scheduler.holen("mail-sync").ist_aktiv(),
                             (False, "Graph nicht eingerichtet"))
        with mock.patch.object(config, "GRAPH_CLIENT_ID", "v27a-client"):
            self.assertEqual(scheduler.holen("mail-sync").ist_aktiv(), (True, ""))
        original = leadmanagement.parameter_holen

        def parser(session, name, standard=""):
            return "aus" if name == "parser_modus" else original(session, name, standard)
        with mock.patch.object(leadmanagement, "parameter_holen", side_effect=parser):
            self.assertEqual(scheduler.holen("lead-parser").ist_aktiv(), (False, "Parser aus"))

        def parser_an(session, name, standard=""):
            return "an" if name == "parser_modus" else original(session, name, standard)
        with mock.patch.object(leadmanagement, "parameter_holen", side_effect=parser_an):
            self.assertEqual(scheduler.holen("lead-parser").ist_aktiv(), (True, ""))
        self.assertEqual(belegt(), 0, "aktiv-Prüfungen lassen keine Verbindung offen")


# --- (e) Status-Tabelle, Fehler, Schleife lebt weiter -------------------------------

def _geocoding_leer():
    """Geocoding-Lauf ohne Dev-Daten und ohne Netz (Bereiche leer, Anbieter verboten)."""
    verboten = mock.Mock(side_effect=AssertionError("echter Geocoder-Aufruf"))
    return [mock.patch.object(geocoding, "_offene_leads", return_value=[]),
            mock.patch.object(geocoding, "_offene_termine", return_value=[]),
            mock.patch.object(geocoding, "_offene_profile", return_value=[]),
            mock.patch.object(geocoding, "_nominatim", verboten),
            mock.patch.object(geocoding, "_ors", verboten),
            mock.patch.object(geocoding, "_google", verboten)]


class Statustabelle(Basis):
    def test_status_zeile_fehler_und_weiterlauf(self):
        import contextlib
        with contextlib.ExitStack() as stapel:
            for patch in _geocoding_leer():
                stapel.enter_context(patch)
            ergebnis = scheduler.ausfuehren("geocoding")
        self.assertFalse(ergebnis["uebersprungen"])
        self.assertTrue(ergebnis["ok"], ergebnis)
        self.assertIn("ok=0", ergebnis["ergebnis"])
        with db.kurz() as s:
            zeile = s.query(SchedulerStatus).filter_by(name="geocoding").one()
            self.assertGreaterEqual(zeile.laeufe, 1)
            self.assertEqual(zeile.letzter_fehler, "")
            self.assertEqual(zeile.intervall_s, 300)
            self.assertIsNotNone(zeile.letzter_start)
        lauf = scheduler.holen("geocoding")
        fehler_vorher, laeufe_vorher = lauf.fehler, lauf.laeufe
        with mock.patch.object(geocoding, "hintergrund_lauf",
                               side_effect=RuntimeError("V27A Testfehler")):
            ergebnis2 = scheduler.ausfuehren("geocoding")   # wirft nie
        self.assertFalse(ergebnis2["ok"])
        self.assertIn("V27A Testfehler", ergebnis2["fehler"])
        self.assertEqual((lauf.fehler, lauf.laeufe), (fehler_vorher + 1, laeufe_vorher + 1))
        self.assertIn("V27A Testfehler", lauf.letzter_fehler)
        self.assertEqual(lauf.zustand, "fehler")
        with db.kurz() as s:
            zeile = s.query(SchedulerStatus).filter_by(name="geocoding").one()
            self.assertIn("V27A Testfehler", zeile.letzter_fehler)
            self.assertGreaterEqual(zeile.fehler, 1)
        # der nächste Lauf läuft normal weiter
        with contextlib.ExitStack() as stapel:
            for patch in _geocoding_leer():
                stapel.enter_context(patch)
            ergebnis3 = scheduler.ausfuehren("geocoding")
        self.assertTrue(ergebnis3["ok"])
        self.assertEqual(lauf.letzter_fehler, "")
        self.assertEqual(lauf.zustand, "ok")

    def test_schleife_lebt_nach_fehler_weiter(self):
        aufrufe: list[int] = []

        def wackelig():
            aufrufe.append(1)
            if len(aufrufe) == 1:
                raise RuntimeError("V27A erster Durchgang scheitert")
            return {"durchgang": len(aufrufe)}

        lauf = scheduler.registrieren("v27a-schleife", 1, wackelig, beschreibung="Schleifen-Test")
        with mock.patch.object(scheduler, "JITTER_MAX_S", 0):
            scheduler._thread_starten(lauf)                 # nur dieser eine Lauf
            ende = time.monotonic() + 10
            while lauf.laeufe < 2 and time.monotonic() < ende:
                time.sleep(0.05)
        scheduler.stoppen(timeout_s=3)
        self.assertGreaterEqual(lauf.laeufe, 2, "Schleife nach dem Fehler stehen geblieben")
        self.assertEqual(lauf.fehler, 1)
        self.assertEqual(lauf.letzter_fehler, "")           # letzter Durchgang ok
        self.assertTrue(lauf.thread is None or not lauf.thread.is_alive())
        scheduler.zuruecksetzen_fuer_tests()
        alle_registrieren()


# --- (d) Geocoding-Backoff -----------------------------------------------------------

class Backoff(Basis):
    ADRESSE = f"{PRAEFIX} Backoffweg 1, 47051 Duisburg"

    def setUp(self):
        self.norm = geocoding.adresse_normalisieren(self.ADRESSE)
        self._cache_loeschen()

    def tearDown(self):
        self._cache_loeschen()

    def _cache_loeschen(self):
        with db.kurz() as s:
            s.query(GeocodeCache).filter_by(adresse_norm=self.norm).delete(
                synchronize_session=False)

    def _cache(self):
        with db.kurz() as s:
            return s.query(GeocodeCache).filter_by(adresse_norm=self.norm).one()

    def _stand_setzen(self, delta: timedelta):
        with db.kurz() as s:
            s.query(GeocodeCache).filter_by(adresse_norm=self.norm).one().stand = \
                datetime.now() - delta

    def test_pausen(self):
        self.assertEqual(geocoding.backoff_pause(0), timedelta(0))
        self.assertEqual(geocoding.backoff_pause(1), timedelta(hours=1))
        self.assertEqual(geocoding.backoff_pause(2), timedelta(hours=6))
        self.assertEqual(geocoding.backoff_pause(3), timedelta(hours=24))
        self.assertEqual(geocoding.backoff_pause(9), timedelta(hours=24))
        jetzt = datetime.now()
        self.assertTrue(geocoding.erneut_faellig(None))
        zeile = GeocodeCache(adresse_norm="x", status="fehler", versuche=1,
                             stand=jetzt - timedelta(minutes=10))
        self.assertFalse(geocoding.erneut_faellig(zeile, jetzt))
        zeile.stand = jetzt - timedelta(hours=2)
        self.assertTrue(geocoding.erneut_faellig(zeile, jetzt))
        zeile.versuche = 0                       # Bestand vor v27: sofort wieder dran
        zeile.stand = jetzt
        self.assertTrue(geocoding.erneut_faellig(zeile, jetzt))
        zeile.status = "ok"
        self.assertTrue(geocoding.erneut_faellig(zeile, jetzt))

    def test_fehleradresse_pause_und_erfolg(self):
        with db.kurz() as s:
            s.add(GeocodeCache(adresse_norm=self.norm, status="fehler", anbieter="nominatim",
                               versuche=1, stand=datetime.now() - timedelta(minutes=10)))
        aufrufe: list[tuple[str, int]] = []
        antwort = {"wert": None}

        def anbieter(adresse, *_args):
            aufrufe.append((adresse, belegt()))
            return antwort["wert"]

        with mock.patch.object(geocoding, "_nominatim", side_effect=anbieter), \
                mock.patch.object(geocoding, "_ors", side_effect=anbieter), \
                mock.patch.object(geocoding, "_google", side_effect=anbieter), \
                mock.patch.object(geocoding, "_zaehler"):
            # 1 Fehlversuch, 10 min alt → Pause 1 h: kein Anbieter-Aufruf
            with db.kurz() as s:
                self.assertEqual(geocoding.geokodieren(s, self.ADRESSE), (None, None, "fehler"))
            self.assertEqual(aufrufe, [])
            self.assertEqual(self._cache().versuche, 1)
            # nach 2 h: erneuter Versuch, scheitert → versuche 2, Pause 6 h
            self._stand_setzen(timedelta(hours=2))
            with db.kurz() as s:
                self.assertEqual(geocoding.geokodieren(s, self.ADRESSE), (None, None, "fehler"))
            self.assertEqual(len(aufrufe), 1)
            self.assertEqual(aufrufe[0][1], 0, "keine Verbindung während des Netzaufrufs")
            cache = self._cache()
            self.assertEqual((cache.status, cache.versuche), ("fehler", 2))
            self.assertLess(datetime.now() - cache.stand, timedelta(minutes=1))
            # 2 Versuche: nach 2 h noch Pause, nach 7 h wieder dran – diesmal Erfolg
            self._stand_setzen(timedelta(hours=2))
            with db.kurz() as s:
                geocoding.geokodieren(s, self.ADRESSE)
            self.assertEqual(len(aufrufe), 1)
            self._stand_setzen(timedelta(hours=7))
            antwort["wert"] = (51.43, 6.76)
            with db.kurz() as s:
                self.assertEqual(geocoding.geokodieren(s, self.ADRESSE), (51.43, 6.76, "ok"))
            self.assertEqual(len(aufrufe), 2)
            cache = self._cache()
            self.assertEqual((cache.status, cache.versuche, cache.lat), ("ok", 0, 51.43))
            # ok-Treffer kommen aus dem Cache
            with db.kurz() as s:
                self.assertEqual(geocoding.geokodieren(s, self.ADRESSE), (51.43, 6.76, "ok"))
            self.assertEqual(len(aufrufe), 2)

    def test_hintergrundlauf_versucht_fehler_vorgaenge_nach_pause(self):
        """Befund v27: Vorgänge mit geocode_status „fehler“ wurden nie wieder
        angefasst – jetzt nach Ablauf der Pause (hier: Bestand ohne versuche)."""
        with db.kurz() as s:
            kunde = Kunde(nachname=f"{PRAEFIX} Backoff", vorname="Test",
                          strasse=f"{PRAEFIX} Backoffweg 1", plz="47051", ort="Duisburg")
            s.add(kunde)
            s.flush()
            vorgang = Vorgang(kunde_id=kunde.id, lead_phase="neu", geocode_status="fehler",
                              demo=True)
            s.add(vorgang)
            s.flush()
            vorgang_id, kunde_id = vorgang.id, kunde.id
            s.add(GeocodeCache(adresse_norm=self.norm, status="fehler", anbieter="nominatim",
                               versuche=0, stand=datetime.now()))
        try:
            with db.kurz() as s:
                offene = geocoding._offene_leads(s, 1000)
            self.assertIn((vorgang_id, self.ADRESSE), offene)
            self._stand_setzen(timedelta(0))
            with db.kurz() as s:
                s.query(GeocodeCache).filter_by(adresse_norm=self.norm).one().versuche = 2
            with db.kurz() as s:
                offene = geocoding._offene_leads(s, 1000)
            self.assertNotIn((vorgang_id, self.ADRESSE), offene, "in der 6-h-Pause nicht dran")
            # Pause abgelaufen → Lauf versucht erneut, Erfolg → Koordinaten am Vorgang
            self._stand_setzen(timedelta(hours=7))
            with mock.patch.object(geocoding, "_offene_termine", return_value=[]), \
                    mock.patch.object(geocoding, "_offene_profile", return_value=[]), \
                    mock.patch.object(geocoding, "_offene_leads",
                                      return_value=[(vorgang_id, self.ADRESSE)]), \
                    mock.patch.object(geocoding, "_nominatim", return_value=(51.5, 6.7)), \
                    mock.patch.object(geocoding, "_ors", return_value=(51.5, 6.7)), \
                    mock.patch.object(geocoding, "_google", return_value=(51.5, 6.7)), \
                    mock.patch.object(geocoding, "_zaehler"):
                ergebnis = geocoding.hintergrund_lauf(limit=5)
            self.assertEqual(ergebnis["ok"], 1)
            with db.kurz() as s:
                vorgang = s.get(Vorgang, vorgang_id)
                self.assertEqual((vorgang.lat, vorgang.lon, vorgang.geocode_status),
                                 (51.5, 6.7, "ok"))
            self.assertEqual(self._cache().versuche, 0)
        finally:
            with db.kurz() as s:
                s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang_id).delete(
                    synchronize_session=False)
                s.query(Vorgang).filter_by(id=vorgang_id).delete(synchronize_session=False)
                s.query(Kunde).filter_by(id=kunde_id).delete(synchronize_session=False)


# --- (c) Pflichttest: 1.000 Adressen, Schreibsperre nie länger als 1 s --------------

class Schreibsperre(Basis):
    ANZAHL = 1000
    ZAEHLER = [f"aufrufe_{d}_{datetime.now().date().isoformat()}"
               for d in ("ors_geocode", "google_geocode", "nominatim")]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.zaehler_alt = {name: param_holen(name) for name in cls.ZAEHLER}
        cls._aufraeumen()
        with db.kurz() as s:
            kunde = Kunde(nachname=f"{PRAEFIX} Schreibsperre", vorname="Test",
                          strasse="Testweg 1", plz="47051", ort="Duisburg")
            s.add(kunde)
            s.flush()
            vorgang = Vorgang(kunde_id=kunde.id, lead_phase="verloren", demo=True)
            s.add(vorgang)
            s.flush()
            cls.kunde_id, cls.vorgang_id = kunde.id, vorgang.id
            beginn = datetime(2020, 1, 1, 8, 0)
            s.add_all([VotTermin(vorgang_id=vorgang.id, beginn=beginn,
                                 ende=beginn + timedelta(hours=1), status="abgesagt",
                                 adresse=f"{PRAEFIX} Teststraße {i}, 47051 Duisburg",
                                 demo=True)
                       for i in range(cls.ANZAHL)])

    @classmethod
    def tearDownClass(cls):
        cls._aufraeumen()
        for name, wert in cls.zaehler_alt.items():
            param_setzen(name, wert)
        param_setzen("v27a_schreiber", None)
        super().tearDownClass()

    @classmethod
    def _aufraeumen(cls):
        with db.kurz() as s:
            for vorgang in s.query(Vorgang).join(Kunde, Kunde.id == Vorgang.kunde_id).filter(
                    Kunde.nachname == f"{PRAEFIX} Schreibsperre"):
                s.query(VotTermin).filter_by(vorgang_id=vorgang.id).delete(
                    synchronize_session=False)
                s.delete(vorgang)
            s.query(Kunde).filter_by(nachname=f"{PRAEFIX} Schreibsperre").delete(
                synchronize_session=False)
            s.query(GeocodeCache).filter(GeocodeCache.adresse_norm.like(
                f"{PRAEFIX.lower()} teststraße %")).delete(synchronize_session=False)

    def _nur_test_termine(self, session, limit):
        return [(z[0], z[1]) for z in
                session.query(VotTermin.id, VotTermin.adresse)
                .filter(VotTermin.vorgang_id == self.vorgang_id, VotTermin.lat.is_(None))
                .order_by(VotTermin.id).limit(limit)]

    def test_1000_adressen_schreibsperre_unter_1s(self):
        stop = threading.Event()
        messungen: list[float] = []
        schreibfehler: list[str] = []

        def schreiber():
            """Alle 50 ms eine Zeile schreiben und committen; gemessen wird die
            gesamte Dauer inkl. Warten auf die Schreibsperre (busy_timeout 5 s)."""
            while not stop.is_set():
                start = time.perf_counter()
                try:
                    with db.kurz() as s:
                        zeile = s.query(LeadParameter).filter_by(name="v27a_schreiber").first()
                        if zeile is None:
                            s.add(LeadParameter(name="v27a_schreiber", wert="1"))
                        else:
                            zeile.wert = str(int(zeile.wert) + 1)
                except Exception as problem:
                    schreibfehler.append(repr(problem))
                messungen.append((time.perf_counter() - start) * 1000)
                stop.wait(0.05)

        def anbieter(adresse, *_args):
            time.sleep(0.005)                         # 5 ms je Adresse
            return 51.43, 6.76

        faden = threading.Thread(target=schreiber, daemon=True, name="v27a-schreiber")
        faden.start()
        try:
            with mock.patch.object(geocoding, "_offene_leads", return_value=[]), \
                    mock.patch.object(geocoding, "_offene_profile", return_value=[]), \
                    mock.patch.object(geocoding, "_offene_termine",
                                      side_effect=self._nur_test_termine), \
                    mock.patch.object(geocoding, "_nominatim", side_effect=anbieter), \
                    mock.patch.object(geocoding, "_ors", side_effect=anbieter), \
                    mock.patch.object(geocoding, "_google", side_effect=anbieter):
                start = time.perf_counter()
                ergebnis = geocoding.hintergrund_lauf(limit=self.ANZAHL)
                dauer_s = time.perf_counter() - start
        finally:
            stop.set()
            faden.join(10)
        self.assertEqual(ergebnis["termine"], self.ANZAHL, ergebnis)
        self.assertEqual(schreibfehler, [])
        self.assertGreaterEqual(len(messungen), 20, f"Schreiber kaum gelaufen ({dauer_s:.1f} s)")
        print(f"\nGeocoding {self.ANZAHL} Adressen in {dauer_s:.1f} s – Schreiber: "
              f"{len(messungen)} Commits, max {max(messungen):.0f} ms, "
              f"Mittel {sum(messungen) / len(messungen):.1f} ms")
        self.assertLess(max(messungen), 1000.0,
                        f"Schreibsperre {max(messungen):.0f} ms (Lauf {dauer_s:.1f} s)")
        with db.kurz() as s:
            self.assertEqual(s.query(VotTermin).filter(VotTermin.vorgang_id == self.vorgang_id,
                                                       VotTermin.lat.is_(None)).count(), 0)
            cache = s.query(GeocodeCache).filter(GeocodeCache.adresse_norm.like(
                f"{PRAEFIX.lower()} teststraße %"))
            self.assertEqual(cache.count(), self.ANZAHL)
            self.assertEqual(cache.filter(GeocodeCache.status == "ok",
                                          GeocodeCache.versuche == 0).count(), self.ANZAHL)

    def test_keine_verbindung_waehrend_netz(self):
        """Sitzungsdisziplin des Laufs: beim Anbieter-Aufruf hält der Prozess
        keine Pool-Verbindung (lesen → Sitzung zu → Netz → kurze Sitzung)."""
        messungen: list[int] = []
        # drei Test-Termine ohne Koordinaten und ohne Cache-Zeile (unabhängig von
        # der Reihenfolge zum 1.000er-Lauf)
        with db.kurz() as s:
            termine = (s.query(VotTermin).filter_by(vorgang_id=self.vorgang_id)
                       .order_by(VotTermin.id).limit(3).all())
            normen = [geocoding.adresse_normalisieren(t.adresse) for t in termine]
            for termin in termine:
                termin.lat = termin.lon = None
            s.query(GeocodeCache).filter(GeocodeCache.adresse_norm.in_(normen)).delete(
                synchronize_session=False)

        def anbieter(adresse, *_args):
            messungen.append(belegt())
            return None                                # Fehlversuch → Backoff-Zeile

        def drei(session, limit):
            return self._nur_test_termine(session, 3)
        with mock.patch.object(geocoding, "_offene_leads", return_value=[]), \
                mock.patch.object(geocoding, "_offene_profile", return_value=[]), \
                mock.patch.object(geocoding, "_offene_termine", side_effect=drei), \
                mock.patch.object(geocoding, "_nominatim", side_effect=anbieter), \
                mock.patch.object(geocoding, "_ors", side_effect=anbieter), \
                mock.patch.object(geocoding, "_google", side_effect=anbieter):
            ergebnis = geocoding.hintergrund_lauf(limit=3)
        self.assertEqual(ergebnis["termine"], 0)
        self.assertEqual(messungen, [0, 0, 0], messungen)
        with db.kurz() as s:
            zeilen = s.query(GeocodeCache).filter(GeocodeCache.adresse_norm.in_(normen))
            self.assertEqual(zeilen.filter(GeocodeCache.status == "fehler",
                                           GeocodeCache.versuche == 1).count(), 3)
            zeilen.delete(synchronize_session=False)


# --- Blöcke: lead_mail je Eintrag, monday je 200 Items ---------------------------------

class LeadMailBloecke(Basis):
    AN = "v27a@test.local"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._aufraeumen()
        with db.kurz() as s:
            kunde = Kunde(nachname=f"{PRAEFIX} Mail", vorname="Test", anrede="Herr",
                          email=cls.AN, interesse="WP")
            s.add(kunde)
            s.flush()
            vorgang = Vorgang(kunde_id=kunde.id, lead_phase="neu", demo=True)
            s.add(vorgang)
            s.flush()
            cls.kunde_id, cls.vorgang_id = kunde.id, vorgang.id

    @classmethod
    def tearDownClass(cls):
        cls._aufraeumen()
        super().tearDownClass()

    @classmethod
    def _aufraeumen(cls):
        with db.kurz() as s:
            s.query(KommunikationLog).filter_by(an=cls.AN).delete(synchronize_session=False)
            for kunde in s.query(Kunde).filter_by(nachname=f"{PRAEFIX} Mail"):
                for vorgang in s.query(Vorgang).filter_by(kunde_id=kunde.id):
                    s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang.id).delete(
                        synchronize_session=False)
                    s.delete(vorgang)
                s.delete(kunde)

    def _eintrag(self, vorgang_id: int, schluessel: str = "eingangsbestaetigung") -> int:
        with db.kurz() as s:
            eintrag = KommunikationLog(vorgang_id=vorgang_id, vorlage_key=schluessel, an=self.AN,
                                       status="geplant",
                                       geplant_am=datetime.now() - timedelta(minutes=1))
            s.add(eintrag)
            s.flush()
            return eintrag.id

    def test_commit_je_eintrag_und_fehler_isoliert(self):
        ids = [self._eintrag(self.vorgang_id) for _ in range(3)]
        kaputt = self._eintrag(-1)                   # Vorgang fehlt → fehler
        original = leadmanagement.parameter_holen

        def protokoll(session, name, standard=""):
            return "protokoll" if name == "mail_modus" else original(session, name, standard)

        echtes_rendern = lead_mail.rendern

        def rendern(session, eintrag):
            if eintrag.id == ids[1]:
                raise RuntimeError("V27A Render-Fehler")
            return echtes_rendern(session, eintrag)

        with mock.patch.object(leadmanagement, "parameter_holen", side_effect=protokoll), \
                mock.patch.object(lead_mail, "rendern", side_effect=rendern):
            zaehler = lead_mail.versand_job()
        # (≥: parallel laufende Tests anderer Agenten können eigene Einträge planen)
        self.assertGreaterEqual(zaehler["protokolliert"], 2, zaehler)
        self.assertGreaterEqual(zaehler["fehler"], 2, zaehler)
        with db.kurz() as s:                           # frische Sitzung: alles committet
            stand = {e.id: (e.status, e.fehler_text) for e in
                     s.query(KommunikationLog).filter_by(an=self.AN)}
        self.assertEqual(stand[ids[0]][0], "protokolliert")
        self.assertEqual(stand[ids[2]][0], "protokolliert")
        self.assertEqual(stand[ids[1]], ("fehler", "V27A Render-Fehler"))
        self.assertEqual(stand[kaputt], ("fehler", "Vorgang fehlt"))
        # ein erneuter Lauf fasst die Einträge nicht mehr an
        self.assertEqual(lead_mail._eintrag_in_sitzung(ids[1]), "")
        self.assertEqual(lead_mail._eintrag_in_sitzung(kaputt), "")

    def test_keine_verbindung_waehrend_graph_versand(self):
        eintrag_id = self._eintrag(self.vorgang_id)
        original = leadmanagement.parameter_holen

        def testmodus(session, name, standard=""):
            if name == "mail_modus":
                return "test"
            if name == "mail_testadresse":
                return self.AN
            return original(session, name, standard)
        messungen: list[tuple[str, int]] = []

        def token():
            messungen.append(("token", belegt()))
            return "tok"

        def graph(methode, pfad, tok, daten=None):
            messungen.append((methode, belegt()))
            return {}
        with mock.patch.object(leadmanagement, "parameter_holen", side_effect=testmodus), \
                mock.patch.object(leadmanagement, "demo_aktiv", return_value=False), \
                mock.patch.object(graph_versand, "_token", side_effect=token), \
                mock.patch.object(graph_versand, "_graph_aufruf", side_effect=graph):
            ergebnis = lead_mail._eintrag_in_sitzung(eintrag_id)   # nur dieser Eintrag
        self.assertEqual(ergebnis, "gesendet")
        self.assertEqual(messungen, [("token", 0), ("POST", 0)], messungen)
        with db.kurz() as s:
            self.assertEqual(s.get(KommunikationLog, eintrag_id).status, "gesendet")


class MondayBloecke(Basis):
    BOARD = "v27a-board"

    def tearDown(self):
        with db.kurz() as s:
            s.query(Lead).filter_by(board_id=self.BOARD).delete(synchronize_session=False)
            s.query(monday_sync.MondayQuelle).filter_by(board_id=self.BOARD).delete(
                synchronize_session=False)

    def test_commit_je_block(self):
        from app import vorgaenge
        items = [{"id": f"v27a-{i}", "name": f"{PRAEFIX}Vorname Nachname{i}",
                  "column_values": []} for i in range(5)]
        quelle = monday_sync.MondayQuelle(board_id=self.BOARD, board_name="", gruppen_titel="T",
                                          aktiv=True)
        with db.kurz() as s:
            s.add(quelle)
            s.flush()
            s.commit = mock.Mock(wraps=s.commit)
            with mock.patch.object(monday_sync, "BLOCK_GROESSE", 2), \
                    mock.patch.object(monday_sync, "kunde_fuer_lead"), \
                    mock.patch.object(vorgaenge, "vorgang_fuer_lead"):
                anzahl = monday_sync._items_schreiben(s, quelle, {}, "V27A Board", items, {})
            self.assertEqual(anzahl, 5)
            self.assertEqual(s.commit.call_count, 2)           # nach Item 2 und 4
            s.delete(quelle)
        with db.kurz() as s:
            self.assertEqual(s.query(Lead).filter_by(board_id=self.BOARD).count(), 5)

    def test_scheduler_lauf_bewertet_quellenfehler(self):
        with mock.patch.object(monday_sync, "sync", return_value={
                "anzahl": 0, "quellen": 2, "quellen_fehler": 2,
                "fehler": ["A: kaputt", "B: kaputt"]}) as lauf:
            with self.assertRaises(RuntimeError) as kontext:
                monday_sync.scheduler_lauf()
            lauf.assert_called_once_with(markieren=False)
        self.assertIn("Alle monday-Quellen", str(kontext.exception))
        with mock.patch.object(monday_sync, "sync", return_value={
                "anzahl": 7, "quellen": 2, "quellen_fehler": 1, "fehler": ["B: kaputt"]}):
            ergebnis = monday_sync.scheduler_lauf()
        self.assertEqual((ergebnis["anzahl"], ergebnis["quellen"], len(ergebnis["fehler"])),
                         (7, 2, 1))
        self.assertEqual(ergebnis["hinweis"], "B: kaputt")

    def test_manueller_vollabgleich_als_import_markiert(self):
        gesehen: list[list[str]] = []

        def bloecke(fehler):
            gesehen.append([i["name"] for i in betrieb.laufende_importe()])
            return 0, 0, 0
        with mock.patch.object(monday_sync, "_sync_in_bloecken", side_effect=bloecke):
            monday_sync.sync(markieren=False)
            monday_sync.sync()
        self.assertEqual(gesehen, [[], ["monday-Sync"]])
        self.assertEqual(betrieb.laufende_importe(), [])


# --- Teilschritte: mail-sync und leadmanagement --------------------------------------

class Teilschritte(Basis):
    def test_mail_sync_alle_vier_scheitern(self):
        knall = mock.Mock(side_effect=RuntimeError("V27A kaputt"))
        with mock.patch.object(mail_sync, "sync", knall), \
                mock.patch.object(mail_sync, "_sub_antworten", knall), \
                mock.patch.object(mail_sync, "_outlook_ruecklauf", knall), \
                mock.patch.object(mail_sync, "_terminantworten", knall):
            ergebnis = scheduler.jetzt_ausfuehren("mail-sync")   # auch ohne Graph
        self.assertEqual(knall.call_count, 4, "ein Fehler darf die anderen nicht blockieren")
        self.assertFalse(ergebnis["ok"])
        self.assertIn("Alle Teilschritte fehlgeschlagen", ergebnis["fehler"])
        self.assertIn("Terminantworten fehlgeschlagen", ergebnis["fehler"])
        self.assertEqual(len(mail_sync.status["fehler"]), 4)

    def test_mail_sync_ein_teilschritt_scheitert(self):
        with mock.patch.object(mail_sync, "sync", return_value=0), \
                mock.patch.object(mail_sync, "_sub_antworten",
                                  side_effect=RuntimeError("V27A Sub")), \
                mock.patch.object(mail_sync, "_outlook_ruecklauf", return_value=0), \
                mock.patch.object(mail_sync, "_terminantworten", return_value=0):
            ergebnis = scheduler.jetzt_ausfuehren("mail-sync")
        self.assertTrue(ergebnis["ok"], ergebnis)
        self.assertIn("fehler=1", ergebnis["ergebnis"])
        self.assertIn("V27A Sub", ergebnis["ergebnis"])
        self.assertEqual(scheduler.holen("mail-sync").letzter_fehler, "")

    def test_leadmanagement_teilschritte_mit_bloecken(self):
        aufrufe: dict = {}

        def wiedervorlagen(session, jetzt=None, block=0):
            aufrufe["wv"] = block
            return 0

        def glocken(session, jetzt=None, block=0):
            aufrufe["todo"] = block
            raise RuntimeError("V27A To-Do kaputt")

        with mock.patch.object(lead_anrufliste, "faellige_wiedervorlagen_melden",
                               side_effect=wiedervorlagen), \
                mock.patch.object(lead_todos, "faellige_glocken", side_effect=glocken), \
                mock.patch.object(leadmanagement, "taeglicher_lauf_leads",
                                  return_value={"uebersprungen": True}), \
                mock.patch.object(leadmanagement, "loeschlauf",
                                  return_value={"uebersprungen": True}):
            ergebnis = scheduler.jetzt_ausfuehren("leadmanagement")
        self.assertTrue(ergebnis["ok"], ergebnis)
        self.assertEqual(aufrufe, {"wv": leadmanagement.BLOCK_GROESSE,
                                   "todo": leadmanagement.BLOCK_GROESSE})
        self.assertIn("wiedervorlagen=0", ergebnis["ergebnis"])
        self.assertIn("fehler=1", ergebnis["ergebnis"])
        self.assertIn("todos: RuntimeError: V27A To-Do kaputt", ergebnis["ergebnis"])
        self.assertEqual(belegt(), 0)


# --- Löschlauf: Kandidaten per Mengenabfrage ------------------------------------------

class Loeschlauf(Basis):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._aufraeumen()
        alt = datetime.now() - timedelta(days=400)
        with db.kurz() as s:
            cls.ids = {}
            for name, phase, zeitpunkt, angenommen in (
                    ("alt", "verloren", alt, False),
                    ("frisch", "verloren", datetime.now(), False),
                    ("auftrag", "nicht_erreicht", alt, True),
                    ("offen", "neu", alt, False)):
                kunde = Kunde(nachname=f"{PRAEFIX} Loeschlauf {name}", vorname="Test")
                s.add(kunde)
                s.flush()
                vorgang = Vorgang(kunde_id=kunde.id, lead_phase=phase, demo=True,
                                  eingang_am=alt, angelegt_am=alt)
                s.add(vorgang)
                s.flush()
                s.add(LeadAktivitaet(vorgang_id=vorgang.id, typ="notiz", text="V27A",
                                     zeitpunkt=zeitpunkt))
                if angenommen:
                    s.add(Angebot(nummer=f"V27A-{vorgang.id}", kunde_id=kunde.id,
                                  vorgang_id=vorgang.id, status="Angenommen"))
                cls.ids[name] = vorgang.id

    @classmethod
    def tearDownClass(cls):
        cls._aufraeumen()
        super().tearDownClass()

    @classmethod
    def _aufraeumen(cls):
        with db.kurz() as s:
            for kunde in s.query(Kunde).filter(Kunde.nachname.like(f"{PRAEFIX} Loeschlauf %")):
                for vorgang in s.query(Vorgang).filter_by(kunde_id=kunde.id):
                    s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang.id).delete(
                        synchronize_session=False)
                    s.query(Angebot).filter_by(vorgang_id=vorgang.id).delete(
                        synchronize_session=False)
                    s.delete(vorgang)
                s.delete(kunde)

    def test_kandidaten_trockenlauf(self):
        with db.kurz() as s:
            ergebnis = leadmanagement.loeschlauf(s, trocken=True)
        kandidaten = set(ergebnis["kandidaten"])
        self.assertIn(self.ids["alt"], kandidaten)
        self.assertNotIn(self.ids["frisch"], kandidaten)       # letzte Aktivität neu
        self.assertNotIn(self.ids["auftrag"], kandidaten)      # angenommenes Angebot
        self.assertNotIn(self.ids["offen"], kandidaten)        # Phase neu
        with db.kurz() as s:                                   # Trockenlauf schreibt nichts
            self.assertEqual(s.get(Kunde, s.get(Vorgang, self.ids["alt"]).kunde_id).nachname,
                             f"{PRAEFIX} Loeschlauf alt")


if __name__ == "__main__":
    unittest.main()
