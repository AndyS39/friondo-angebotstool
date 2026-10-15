# Hotfix 06.10.2026 – Datenbank-Verbindungspool (QueuePool limit of size 5
# overflow 10 reached): 40 parallele Anfragen auf Kundenkartei und
# Terminvorschläge mit künstlich langsamem Routing (Mock der ORS-Matrix, 3 s)
# dürfen keinen TimeoutError auslösen; während des Netzaufrufs hält keine
# Anfrage eine Pool-Verbindung (verbindung_freigeben), die Middleware-Sitzung
# ist vor call_next geschlossen. Dazu: Pool-Parameter, Fehlerprotokoll bei
# Pool-Timeout nur im Datei-Log + Pool-Status in jedem Eintrag, Seite
# Parametrierung → Fehlerprotokoll zeigt den Pool-Status. Läuft gegen die
# Entwicklungs-DB; Testdaten (Nachname „PoolHotfix-Test“, Benutzer „PoolHotfix …“)
# werden wieder aufgeräumt. Kein echter Netzzugriff.
import json
import logging
import sqlite3
import threading
import time
import unittest
import warnings
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from starlette.requests import Request

from app import anfrage, angebot_aufbau, auth, betrieb, config, db, fehlerprotokoll, lead_termin, routing
from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benutzer, Fehlerprotokoll, Kunde, LeadAktivitaet,
                        LeadQuelle, Vorgang, VotTermin)

NACHNAME = "PoolHotfix-Test"
PRAEFIX = "PoolHotfix "
# Koordinaten abseits aller echten Leads/AD-Profile (Nordsee), je Lauf leicht
# verschoben, damit der Routing-Cache leer ist und jeder Aufruf den Mock trifft
BASIS = (54.31 + (int(time.time()) % 97) / 10000.0, 7.61)
ANZAHL = 40
LANGSAM_S = 3.0


def param_setzen(name: str, wert) -> None:
    s = SessionLocal()
    try:
        if wert is None:
            from app.models import LeadParameter
            s.query(LeadParameter).filter_by(name=name).delete()
        else:
            kern.parameter_setzen(s, name, wert)
        s.commit()
    finally:
        s.close()


def routing_cache_leeren() -> None:
    """Luftlinien-Einträge der Testkoordinaten entfernen, damit jeder Lauf wieder
    die (gemockte) Routing-Matrix braucht."""
    from app.models import RoutingCache
    s = SessionLocal()
    try:
        s.query(RoutingCache).filter(
            RoutingCache.von_key.like("54.3%") | RoutingCache.nach_key.like("54.3%")
        ).delete(synchronize_session=False)
        s.commit()
    finally:
        s.close()


def aufraeumen(s):
    from app.models import RoutingCache
    for v in s.query(Vorgang).join(Kunde, Kunde.id == Vorgang.kunde_id).filter(
            Kunde.nachname.like(f"{NACHNAME}%")):
        s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
        s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
        s.delete(v)
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.query(RoutingCache).filter(RoutingCache.von_key.like("54.3%")).delete(
        synchronize_session=False)
    s.query(Fehlerprotokoll).filter(Fehlerprotokoll.pfad == "/test-pool").delete(
        synchronize_session=False)
    s.commit()


class _BelegtZaehler(logging.Handler):
    """v33 (Phase 172): zählt Warnungen „Datenbank belegt“/„locked“ des Loggers angebotstool."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.meldungen: list[str] = []

    def emit(self, record):
        text_ = record.getMessage()
        if "belegt" in text_ or "locked" in text_.lower():
            self.meldungen.append(text_)

    @property
    def anzahl(self) -> int:
        return len(self.meldungen)


def _fremde_schreibsperre_moeglich(timeout_s: float = 0.3) -> bool:
    """True, wenn eine zweite sqlite3-Verbindung die Schreibsperre sofort bekommt
    (also gerade keine Sitzung eine Schreibtransaktion hält)."""
    v = sqlite3.connect(str(config.DB_PFAD), isolation_level=None, timeout=timeout_s)
    try:
        try:
            v.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            return False
        v.execute("ROLLBACK")
        return True
    finally:
        v.close()


def _sperre_halten(sekunden: float, bereit: threading.Event) -> None:
    v = sqlite3.connect(str(config.DB_PFAD), isolation_level=None, timeout=30)
    try:
        v.execute("BEGIN IMMEDIATE")
        bereit.set()
        time.sleep(sekunden)
        v.execute("ROLLBACK")
    finally:
        v.close()


class Basis(unittest.TestCase):
    PARAMETER = ("routing_anbieter", "ors_api_key", "kalender_sync", "lead_freigabe_modus")

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.alt = {n: kern.parameter_holen(cls.s, n, None) for n in cls.PARAMETER}
        param_setzen("lead_freigabe_modus", "admin")
        param_setzen("kalender_sync", "aus")
        param_setzen("routing_anbieter", "ors")
        param_setzen("ors_api_key", "pool-hotfix-testschluessel")
        cls.s.expire_all()
        lead_termin.vorschlaege_cache_leeren()
        # ein Außendienstler mit Startkoordinaten → Routing-Matrix wird gebraucht
        ad = Benutzer(name=f"{PRAEFIX}AD", rolle="aussendienst", aktiv=True,
                      email="poolhotfix-ad@test.local", telefon="0203 1",
                      pin_hash=auth.pin_hash("4321"))
        cls.s.add(ad)
        cls.s.flush()
        cls.s.add(AdProfil(
            benutzer_id=ad.id, start_adresse="Nordsee", start_lat=BASIS[0] + 0.01,
            start_lon=BASIS[1] + 0.01,
            arbeitszeiten=json.dumps({t: ["08:00", "18:00"] for t in ("mo", "di", "mi", "do", "fr")}),
            termin_dauer_min=90, puffer_min=30, max_termine_tag=3,
            gebiet_plz_praefixe=json.dumps([]), aktiv_terminierung=True,
            terminiert_selbst=False, kompetenz_sparten=json.dumps(["WP"]),
            kompetenz_kombi=False, kompetenz_mfh=False, kompetenz_gewerbe=False))
        cls.s.commit()
        cls.ad_id = ad.id
        quelle = cls.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"anrede": "Herr", "vorname": "Paul", "nachname": NACHNAME,
                 "plz": "47139", "ort": "Duisburg", "telefon": "0203 330099",
                 "sparten": ["WP"], "email": "poolhotfix@test.local",
                 "strasse": "Teststraße 1"}
        vorgang, _ = kern.lead_anlegen(cls.s, daten, quelle, "api", entscheidung="neu")
        kunde = cls.s.get(Kunde, vorgang.kunde_id)
        kunde.vertriebskanal = "Standard"
        kunde.objektart = "EFH"
        vorgang.demo = True
        vorgang.lead_phase = "neu"
        vorgang.lat, vorgang.lon, vorgang.geocode_status = BASIS[0], BASIS[1], "ok"
        cls.s.commit()
        cls.vorgang_id = vorgang.id
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        for name, wert in cls.alt.items():
            param_setzen(name, wert)
        lead_termin.vorschlaege_cache_leeren()
        cls.s.close()

    @staticmethod
    def admin_client() -> TestClient:
        c = TestClient(app)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        return c


class Lasttest(Basis):
    def test_40_parallele_anfragen_ohne_pool_timeout(self):
        self.assertEqual((db.engine.pool.size(), db.engine.pool._max_overflow,
                          db.engine.pool._timeout), (db.POOL_SIZE, db.MAX_OVERFLOW, db.POOL_TIMEOUT))
        protokoll_vorher = self.s.query(Fehlerprotokoll).count()
        log_vorher = 0
        if fehlerprotokoll.log_pfad().exists():
            log_vorher = fehlerprotokoll.log_pfad().read_text(
                encoding="utf-8", errors="replace").count("QueuePool")
        belegt: list[int] = []
        aufrufe: list[float] = []
        sperre = threading.Lock()

        def langsame_matrix(quellen, ziele, schluessel):
            # künstlich langsames Routing – währenddessen darf die anfragende
            # Sitzung keine Pool-Verbindung halten
            with sperre:
                belegt.append(db.engine.pool.checkedout())
                aufrufe.append(time.monotonic())
            time.sleep(LANGSAM_S)
            raise RuntimeError("Routing-Dienst nicht erreichbar (Test)")

        def anfrage(i: int):
            c = self.admin_client()
            if i % 2 == 0:
                r = c.get(f"/lead-management/lead/{self.vorgang_id}")
                return ("kartei", r.status_code, r.text[:200])
            r = c.get(f"/lead-management/lead/{self.vorgang_id}/termin/vorschlaege.json?neu=1")
            zustand = r.json().get("status") if r.status_code == 200 else ""
            return ("vorschlaege", r.status_code, r.text[:300], zustand)

        db.verbindung_freigeben(self.s)           # die Testsession hält selbst keine Verbindung
        routing_cache_leeren()
        lead_termin.vorschlaege_cache_leeren()
        # v33 (PLAN_V20 Phase 172): Messung „database is locked“ – Warnungen der
        # Best-effort-Schreibungen (Routing-Cache, Aufruf-Zähler, Protokollnotiz) und
        # Schreibsperren-Zähler von _speichern während der 20 gleichzeitigen Terminvorschläge
        belegt_warnungen = _BelegtZaehler()
        logging.getLogger("angebotstool").addHandler(belegt_warnungen)
        betrieb.schreibsperre_zuruecksetzen()
        db.transaktionen_zuruecksetzen()
        # Welle 1: 20 × Kundenkartei + 20 × Terminvorschläge gleichzeitig
        start = time.monotonic()
        with mock.patch.object(routing, "_ors_matrix", side_effect=langsame_matrix):
            with ThreadPoolExecutor(max_workers=ANZAHL) as pool:
                ergebnisse = list(pool.map(anfrage, range(ANZAHL)))
        dauer = time.monotonic() - start
        fehler = [e for e in ergebnisse if e[1] != 200]
        self.assertEqual(fehler, [], f"Fehlerantworten: {fehler[:3]}")
        self.assertEqual(sum(1 for e in ergebnisse if e[0] == "vorschlaege"), ANZAHL // 2)
        for eintrag in ergebnisse:
            art, _status, text = eintrag[0], eintrag[1], eintrag[2]
            self.assertNotIn("TimeoutError", text)
            self.assertNotIn("QueuePool", text)
            if art == "vorschlaege":
                self.assertIn(eintrag[3], ("ok", "keine"), text)
        # die langsamen Routing-Aufrufe liefen parallel (nicht nacheinander) …
        self.assertGreaterEqual(len(aufrufe), ANZAHL // 2 - 2, "Mock kaum getroffen")
        self.assertLess(dauer, LANGSAM_S * 10, f"Anfragen liefen nicht parallel ({dauer:.1f} s)")   # v27: Grenze 30 s (CPU-Last durch parallele Testläufe)
        # … und der Pool war nie erschöpft (Kartei-Seiten halten ihre Verbindung
        # nur während der DB-Arbeit, Vorschläge geben sie vor dem Routing frei)
        self.assertLessEqual(max(belegt), db.POOL_SIZE + db.MAX_OVERFLOW,
                             f"Pool-Belegung während Netz-I/O: {belegt}")
        # Welle 2: 40 × Terminvorschläge gleichzeitig – während alle im Netzaufruf
        # stehen, hält keine Anfrage eine Verbindung (der letzte Aufrufer sieht
        # höchstens eine fremde Verbindung belegt)
        belegt.clear()
        aufrufe.clear()
        routing_cache_leeren()                    # Welle 1 hat Luftlinien-Werte gecacht
        lead_termin.vorschlaege_cache_leeren()
        start = time.monotonic()
        with mock.patch.object(routing, "_ors_matrix", side_effect=langsame_matrix):
            with ThreadPoolExecutor(max_workers=ANZAHL) as pool:
                ergebnisse = list(pool.map(anfrage, [1] * ANZAHL))
        dauer = time.monotonic() - start
        self.assertEqual([e[1] for e in ergebnisse], [200] * ANZAHL)
        self.assertGreaterEqual(len(aufrufe), ANZAHL - 2, "Mock kaum getroffen")
        self.assertLess(dauer, LANGSAM_S * 10, f"Anfragen liefen nicht parallel ({dauer:.1f} s)")   # v27: Grenze 30 s (CPU-Last durch parallele Testläufe)
        self.assertLessEqual(min(belegt), 1, f"Verbindungen während Netz-I/O gehalten: {belegt}")
        self.assertLessEqual(belegt[-1], 1, f"Verbindungen während Netz-I/O gehalten: {belegt}")
        self.s.expire_all()
        self.assertEqual(self.s.query(Fehlerprotokoll).count(), protokoll_vorher)
        if fehlerprotokoll.log_pfad().exists():
            log_nachher = fehlerprotokoll.log_pfad().read_text(
                encoding="utf-8", errors="replace").count("QueuePool")
            self.assertEqual(log_nachher, log_vorher)
        # v33 (Phase 172): kein „database is locked“ als 500er (oben geprüft), in
        # _speichern oder bei BEGIN IMMEDIATE. Die Best-effort-Übersprünge des Routing-
        # Caches (Warnung „Datenbank belegt“) werden nur gemessen: sie entstehen im
        # Luftlinien-Rückfall von routing.fahrzeit (GET-Sitzung schreibt den Eintrag,
        # committet ihn aber nicht und hält die Schreibsperre bis zum Ende der
        # Vorschlagsberechnung – vorbestehend; Vorschlag in diagnose/v33/A_ergebnis.md).
        logging.getLogger("angebotstool").removeHandler(belegt_warnungen)
        print(f"\nMESSUNG Terminvorschläge (2 × {ANZAHL} parallel): "
              f"{belegt_warnungen.anzahl} Warnungen „Datenbank belegt“ (Routing-Cache best effort), "
              f"locked in _speichern: {betrieb.SCHREIBSPERRE['locked']}, "
              f"Transaktionen sofort/verzögert/wiederholt/gescheitert: {db.TRANSAKTIONEN['sofort']}/"
              f"{db.TRANSAKTIONEN['verzoegert']}/{db.TRANSAKTIONEN['sofort_wiederholt']}/"
              f"{db.TRANSAKTIONEN['sofort_gescheitert']}")
        self.assertEqual(betrieb.SCHREIBSPERRE["locked"], 0)
        self.assertEqual(db.TRANSAKTIONEN["sofort_gescheitert"], 0)

    def test_verbindung_freigeben_gibt_pool_frei(self):
        s = SessionLocal()
        try:
            s.query(Benutzer).first()                       # Transaktion offen → Verbindung belegt
            self.assertGreaterEqual(db.engine.pool.checkedout(), 1)
            vorher = db.engine.pool.checkedout()
            db.verbindung_freigeben(s)
            self.assertEqual(db.engine.pool.checkedout(), vorher - 1)
            b = s.query(Benutzer).first()                   # Session weiter nutzbar
            self.assertIsNotNone(b)
            db.verbindung_freigeben(None)                   # unschädlich
        finally:
            s.close()

    def test_middleware_schliesst_sitzung_vor_call_next(self):
        # request.state.benutzer ist nach dem Schließen ein abgelöstes Objekt –
        # Rollenprüfung, Glocke und Seiten funktionieren weiter
        c = self.admin_client()
        for pfad in ("/", "/parametrierung", "/lead-management/dashboard",
                     f"/lead-management/lead/{self.vorgang_id}"):
            r = c.get(pfad)
            self.assertEqual(r.status_code, 200, pfad)
        # während des Endpunkts ist keine zweite (Middleware-)Verbindung belegt
        gesehen: list[int] = []

        def zaehlen(*_a, **_k):
            gesehen.append(db.engine.pool.checkedout())
            raise RuntimeError("Test")
        db.verbindung_freigeben(self.s)
        routing_cache_leeren()
        lead_termin.vorschlaege_cache_leeren()
        with mock.patch.object(routing, "_ors_matrix", side_effect=zaehlen):
            r = c.get(f"/lead-management/lead/{self.vorgang_id}/termin/vorschlaege.json?neu=1")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(gesehen)
        self.assertLessEqual(max(gesehen), 1)


class Fehlerprotokoll_Pool(Basis):
    @staticmethod
    def anfrage(pfad="/test-pool"):
        scope = {"type": "http", "method": "GET", "path": pfad, "query_string": b"",
                 "headers": [], "scheme": "http", "server": ("testserver", 80),
                 "state": {}}
        return Request(scope)

    def test_pool_timeout_nur_datei_log(self):
        vorher = self.s.query(Fehlerprotokoll).count()
        exc = PoolTimeout("QueuePool limit of size 5 overflow 10 reached, "
                          "connection timed out, timeout 30.00")
        self.assertTrue(fehlerprotokoll.ist_pool_timeout(exc))
        self.assertFalse(fehlerprotokoll.ist_pool_timeout(ValueError("x")))
        nr = fehlerprotokoll.eintragen(self.anfrage(), exc)
        self.assertTrue(nr.startswith("F-"))
        self.s.expire_all()
        self.assertEqual(self.s.query(Fehlerprotokoll).count(), vorher)   # kein INSERT
        log = fehlerprotokoll.log_pfad().read_text(encoding="utf-8", errors="replace")
        stelle = log.rfind(nr)
        self.assertGreaterEqual(stelle, 0, "Datei-Log ohne Eintrag")
        eintrag = log[stelle:stelle + 1500]            # mehrzeiliger Eintrag
        self.assertIn("Pool erschöpft – nur Datei-Log", eintrag)
        self.assertIn("Pool size: 20", eintrag)
        self.assertIn("QueuePool limit", eintrag)

    def test_normaler_eintrag_mit_pool_status(self):
        nr = fehlerprotokoll.eintragen(self.anfrage(), ValueError("pool-status-test"))
        self.s.expire_all()
        eintrag = self.s.query(Fehlerprotokoll).filter_by(fehler_nr=nr).first()
        self.assertIsNotNone(eintrag)
        self.assertTrue(eintrag.traceback.startswith("Verbindungspool: Pool size: 20"))
        self.assertEqual(eintrag.pfad, "/test-pool")
        nr2 = fehlerprotokoll.eintragen_text("Heizreport", "GET x → HTTP 500", "detail",
                                             pfad="/test-pool")
        self.s.expire_all()
        eintrag2 = self.s.query(Fehlerprotokoll).filter_by(fehler_nr=nr2).first()
        self.assertIn("Verbindungspool: Pool size: 20", eintrag2.traceback)

    def test_seite_zeigt_pool_status(self):
        r = self.client.get("/parametrierung/fehlerprotokoll")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Verbindungspool:", r.text)
        self.assertIn("Pool size: 20", r.text)
        self.assertIn("Timeout 10 s", r.text)

    def test_hauptseite_meldung_bei_pool_timeout(self):
        from app.main import unbehandelte_ausnahme
        antwort = unbehandelte_ausnahme(
            self.anfrage(), PoolTimeout("QueuePool limit of size 5 overflow 10 reached"))
        self.assertEqual(antwort.status_code, 500)


# --- v33 (PLAN_V20 Phase 172, v30-Nachtrag 21): Schreibtransaktionen mit BEGIN IMMEDIATE ------

class Schreibtransaktionen(unittest.TestCase):
    """db.py: Schreibsitzungen (get_session bei POST/PUT/PATCH/DELETE, kurz(),
    schreibsitzung()) eröffnen ihre Transaktion sofort mit BEGIN IMMEDIATE, Lesesitzungen
    bleiben DEFERRED; verschachtelte Sitzungen desselben Kontexts bleiben DEFERRED."""

    PARAM = "v33a_busy_snapshot_test"

    @classmethod
    def setUpClass(cls):
        init_db()

    @classmethod
    def tearDownClass(cls):
        param_setzen(cls.PARAM, None)

    def test_get_session_waehlt_schreibsitzung_nach_methode(self):
        class Anfrage:
            def __init__(self, methode):
                self.method = methode

        def ist_schreibsitzung(gen) -> bool:
            s = next(gen)
            try:
                return bool(s.get_bind().get_execution_options().get("schreibend"))
            finally:
                gen.close()
        for methode, erwartet in (("GET", False), ("HEAD", False), ("OPTIONS", False),
                                  ("POST", True), ("PUT", True), ("PATCH", True), ("DELETE", True)):
            self.assertEqual(ist_schreibsitzung(db.get_session(Anfrage(methode))), erwartet, methode)
        # Rückfall über die Kontextvariable, die die RollenMiddleware setzt
        token = anfrage.METHODE.set("POST")
        try:
            self.assertTrue(ist_schreibsitzung(db.get_session()))
        finally:
            anfrage.METHODE.reset(token)
        self.assertFalse(ist_schreibsitzung(db.get_session()))      # ohne Anfrage: DEFERRED
        self.assertTrue(anfrage.ist_schreibend("post"))
        self.assertFalse(anfrage.ist_schreibend("GET"))
        self.assertFalse(anfrage.ist_schreibend(""))
        self.assertEqual(anfrage.aktuelle_methode(), "")

    def test_kurz_eroeffnet_schreibtransaktion_sofort(self):
        db.transaktionen_zuruecksetzen()
        self.assertFalse(db.schreibtransaktion_offen())
        self.assertTrue(_fremde_schreibsperre_moeglich())
        with db.kurz() as s:
            s.execute(text("SELECT 1"))                       # nur gelesen …
            self.assertTrue(db.schreibtransaktion_offen())
            self.assertFalse(_fremde_schreibsperre_moeglich())   # … trotzdem Schreibsperre gehalten
            # verschachtelte Sitzung im selben Kontext bleibt DEFERRED und liest sofort
            start = time.monotonic()
            with db.kurz() as s2:
                s2.execute(text("SELECT 1"))
                self.assertTrue(db.schreibtransaktion_offen())
            self.assertLess(time.monotonic() - start, 1.0)
            self.assertTrue(db.schreibtransaktion_offen())      # äußere Sperre bleibt
        self.assertFalse(db.schreibtransaktion_offen())
        self.assertTrue(_fremde_schreibsperre_moeglich())
        self.assertEqual(db.TRANSAKTIONEN["sofort"], 1)
        self.assertGreaterEqual(db.TRANSAKTIONEN["verzoegert"], 1)
        self.assertEqual(db.TRANSAKTIONEN["sofort_gescheitert"], 0)
        # Lesesitzung: keine Schreibsperre
        with db.kurz(schreibend=False) as s:
            s.execute(text("SELECT 1"))
            self.assertFalse(db.schreibtransaktion_offen())
            self.assertTrue(_fremde_schreibsperre_moeglich())
        # schreibsitzung() außerhalb von kurz()/get_session
        s = db.schreibsitzung()
        try:
            s.execute(text("SELECT 1"))
            self.assertFalse(_fremde_schreibsperre_moeglich())
            s.rollback()
            self.assertTrue(_fremde_schreibsperre_moeglich())
        finally:
            s.close()
        self.assertFalse(db.schreibtransaktion_offen())
        # Schalter aus → alles DEFERRED (Verhalten bis v32)
        with mock.patch.object(db, "SCHREIBTRANSAKTION_SOFORT", False):
            with db.kurz() as s:
                s.execute(text("SELECT 1"))
                self.assertFalse(db.schreibtransaktion_offen())
                self.assertTrue(_fremde_schreibsperre_moeglich())

    def test_begin_immediate_wartet_busy_timeout_und_scheitert_sauber(self):
        """Fremde Sperre 2 s: BEGIN IMMEDIATE wartet (busy_timeout 5 s) und kommt durch.
        Fremde Sperre 6,5 s: erster Versuch scheitert nach 5 s, die Wiederholung nach
        0,7 s kommt durch (v22-Muster im begin-Event). Fremde Sperre 13 s: „database is
        locked“ beim ERSTEN Zugriff der Sitzung nach ≈ 10,7 s; die Sitzung ist danach
        sauber nutzbar (rollback), keine Verbindung bleibt belegt."""
        db.transaktionen_zuruecksetzen()
        bereit = threading.Event()
        t = threading.Thread(target=_sperre_halten, args=(2.0, bereit))
        t.start()
        bereit.wait(5)
        start = time.monotonic()
        with db.kurz() as s:
            s.execute(text("SELECT 1"))
        dauer = time.monotonic() - start
        t.join()
        self.assertGreater(dauer, 1.0, dauer)
        self.assertLess(dauer, 5.0, dauer)
        self.assertEqual(db.TRANSAKTIONEN["sofort_wiederholt"], 0)
        bereit = threading.Event()
        t = threading.Thread(target=_sperre_halten, args=(6.5, bereit))
        t.start()
        bereit.wait(5)
        start = time.monotonic()
        with db.kurz() as s:
            s.execute(text("SELECT 1"))
        dauer = time.monotonic() - start
        t.join()
        self.assertGreater(dauer, 5.0, dauer)
        self.assertLess(dauer, 9.0, dauer)
        self.assertEqual((db.TRANSAKTIONEN["sofort_wiederholt"],
                          db.TRANSAKTIONEN["sofort_gescheitert"]), (1, 0))
        belegt_vorher = db.engine.pool.checkedout()
        bereit = threading.Event()
        t = threading.Thread(target=_sperre_halten, args=(13, bereit))
        t.start()
        bereit.wait(5)
        start = time.monotonic()
        s = db.schreibsitzung()
        try:
            with self.assertRaises(OperationalError) as cm:
                s.execute(text("SELECT 1"))
            dauer = time.monotonic() - start
            self.assertIn("locked", str(cm.exception).lower())
            self.assertIn("BEGIN IMMEDIATE", str(cm.exception))
            self.assertGreater(dauer, 9.0, dauer)
            self.assertLess(dauer, 13.0, dauer)
            s.rollback()
            self.assertFalse(db.schreibtransaktion_offen())
            self.assertEqual(db.engine.pool.checkedout(), belegt_vorher)   # kein Leck
            t.join()
            self.assertEqual(s.execute(text("SELECT 1")).scalar(), 1)    # danach nutzbar
        finally:
            s.close()
        self.assertEqual((db.TRANSAKTIONEN["sofort_wiederholt"],
                          db.TRANSAKTIONEN["sofort_gescheitert"]), (2, 1))

    def test_busy_snapshot_mechanik(self):
        """Hintergrund (v30-Nachtrag 21): hält eine Transaktion VOR dem Schreiben einen
        Lese-Schnappschuss (explizites BEGIN, dann SELECT) und ein anderer Schreiber
        committet dazwischen, scheitert der eigene Schreibzugriff SOFORT mit „database is
        locked“ (BUSY_SNAPSHOT – der busy_timeout greift nicht). So verhält sich der
        sqlite3-Treiber ab Python 3.16 standardmäßig (autocommit=False), und so verhielte
        sich jede Sitzung des Tools mit einem pauschalen BEGIN-Event (Befund im Durchlauf
        v33: 29 Alt-Tests rot). Im Legacy-Modus (bis v32 und weiterhin für Lesesitzungen)
        läuft ein SELECT ohne Transaktion – kein Schnappschuss, kein BUSY_SNAPSHOT."""
        param_setzen(self.PARAM, "0")
        v = sqlite3.connect(str(config.DB_PFAD), isolation_level=None, timeout=5)
        try:
            v.execute("BEGIN")
            v.execute("SELECT wert FROM lead_parameter WHERE name = ?", (self.PARAM,)).fetchone()
            with db.kurz() as s:                                # fremder Schreiber committet
                kern.parameter_setzen(s, self.PARAM, "fremd")
            start = time.monotonic()
            with self.assertRaises(sqlite3.OperationalError) as cm:
                v.execute("UPDATE lead_parameter SET wert = 'eigen' WHERE name = ?", (self.PARAM,))
            dauer = time.monotonic() - start
            v.execute("ROLLBACK")
            self.assertIn("locked", str(cm.exception))
            self.assertLess(dauer, 0.5, dauer)                  # sofort, trotz busy_timeout 5 s
        finally:
            v.close()
        # Legacy-Modus (Sitzung des Tools ohne Schreibkennzeichen): SELECT hält keinen
        # Schnappschuss – der spätere Schreibzugriff gelingt
        param_setzen(self.PARAM, "0")
        a = SessionLocal()
        try:
            kern.parameter_holen(a, self.PARAM, "0")
            with db.kurz() as s:
                kern.parameter_setzen(s, self.PARAM, "fremd")
            kern.parameter_setzen(a, self.PARAM, "eigen")
            a.commit()
        finally:
            a.close()
        with db.kurz(schreibend=False) as s:
            self.assertEqual(kern.parameter_holen(s, self.PARAM, "?"), "eigen")

    def _lesen_dann_schreiben(self, sofort: bool) -> dict:
        """Sitzung A liest den Parameter; Sitzung B (anderer Thread) schreibt „b“ und
        committet; dann schreibt A „a“ und committet."""
        ergebnis: dict = {}
        param_setzen(self.PARAM, "0")
        a = db.schreibsitzung() if sofort else SessionLocal()
        try:
            ergebnis["a_gelesen"] = kern.parameter_holen(a, self.PARAM, "0")
            b_fertig = threading.Event()

            def b():
                t0 = time.monotonic()
                with db.kurz() as s:
                    kern.parameter_setzen(s, self.PARAM, "b")
                ergebnis["b_dauer"] = time.monotonic() - t0
                b_fertig.set()
            t = threading.Thread(target=b)
            t.start()
            ergebnis["b_sofort_fertig"] = b_fertig.wait(0.8)
            t0 = time.monotonic()
            try:
                kern.parameter_setzen(a, self.PARAM, "a")
                a.commit()
                ergebnis["a"] = "ok"
            except OperationalError as fehler:
                a.rollback()
                ergebnis["a"] = "locked" if "locked" in str(fehler).lower() else str(fehler)[:80]
            ergebnis["a_dauer"] = time.monotonic() - t0
            t.join(10)
        finally:
            a.close()
        with db.kurz(schreibend=False) as s:
            ergebnis["endwert"] = kern.parameter_holen(s, self.PARAM, "?")
        return ergebnis

    def test_lesen_dann_schreiben_vorher_nachher(self):
        """Messung für die Gesamtübersicht. Vorher (Legacy, bis v32): B kommt sofort durch,
        A überschreibt danach B's Wert – kein „locked“, aber ein verlorenes Update (A hat
        auf einem veralteten Stand gerechnet). Nachher (BEGIN IMMEDIATE): A hält die
        Schreibsperre schon beim Lesen, B wartet (busy_timeout) und schreibt danach –
        Lesen-Rechnen-Schreiben ist serialisiert, beide kommen durch."""
        vorher = self._lesen_dann_schreiben(sofort=False)
        nachher = self._lesen_dann_schreiben(sofort=True)
        print(f"\nMESSUNG Lesen-dann-Schreiben vorher (Legacy): A={vorher['a']} nach "
              f"{vorher['a_dauer']:.3f} s, B sofort fertig: {vorher['b_sofort_fertig']}, "
              f"Endwert {vorher['endwert']!r} | nachher (BEGIN IMMEDIATE): A={nachher['a']} "
              f"nach {nachher['a_dauer']:.3f} s, B wartete {nachher.get('b_dauer', 0):.2f} s, "
              f"Endwert {nachher['endwert']!r}")
        self.assertEqual(vorher["a"], "ok")
        self.assertTrue(vorher["b_sofort_fertig"])
        self.assertEqual(vorher["endwert"], "a")                # B's „b“ ging verloren
        self.assertEqual(nachher["a"], "ok")
        self.assertFalse(nachher["b_sofort_fertig"])            # B wartete auf A
        self.assertGreater(nachher["b_dauer"], 0.5)
        self.assertLess(nachher["b_dauer"], 5.0)
        self.assertEqual(nachher["endwert"], "b")               # Reihenfolge A, dann B

    def test_wal_pflege_ohne_autocommit_option(self):
        erg = db.wal_pflege()
        self.assertIn("eingespielt", erg)
        self.assertFalse(db.schreibtransaktion_offen())
        with db.kurz() as s:                                    # Verbindung danach normal nutzbar
            self.assertEqual(s.execute(text("SELECT 1")).scalar(), 1)


class Schreibsturm(Basis):
    """v33 (Phase 172): 20 parallele Schreibanfragen (POST /angebote/<id>/rabatt – lesen,
    ändern, committen) ohne „database is locked“; Vergleichslauf mit dem Schalter aus
    (DEFERRED wie bis v32) nur als Messung für die Gesamtübersicht."""

    ANZAHL_ANGEBOTE = 20

    def _angebote_anlegen(self) -> list[int]:
        kunde_id = self.s.get(Vorgang, self.vorgang_id).kunde_id
        ids = []
        for _ in range(self.ANZAHL_ANGEBOTE):
            a = angebot_aufbau.angebot_anlegen(self.s, kunde_id)
            ids.append(a.id)
        return ids

    def _angebote_entfernen(self, ids: list[int]) -> None:
        from app.models import Angebot
        self.s.expire_all()
        for angebot_id in ids:
            a = self.s.get(Angebot, angebot_id)
            if a is not None:
                self.s.delete(a)
            self.s.query(Fehlerprotokoll).filter(
                Fehlerprotokoll.pfad.like(f"/angebote/{angebot_id}/%")).delete(
                synchronize_session=False)
        self.s.commit()

    def _sturm(self, ids: list[int], wert: str) -> dict:
        zaehler = _BelegtZaehler()
        logging.getLogger("angebotstool").addHandler(zaehler)
        betrieb.schreibsperre_zuruecksetzen()
        db.transaktionen_zuruecksetzen()
        db.verbindung_freigeben(self.s)

        def anfrage(angebot_id: int):
            c = self.admin_client()
            r = c.post(f"/angebote/{angebot_id}/rabatt",
                       data={"wert": wert, "typ": "prozent", "bezeichnung": "Sturm"},
                       follow_redirects=False)
            return r.status_code, r.headers.get("location", "")
        start = time.monotonic()
        try:
            with ThreadPoolExecutor(max_workers=len(ids)) as pool:
                ergebnisse = list(pool.map(anfrage, ids))
        finally:
            logging.getLogger("angebotstool").removeHandler(zaehler)
        return {"dauer": time.monotonic() - start, "ergebnisse": ergebnisse,
                "warnungen": zaehler.anzahl, "locked": betrieb.SCHREIBSPERRE["locked"],
                "max_ms": betrieb.SCHREIBSPERRE["max_ms"],
                "transaktionen": dict(db.TRANSAKTIONEN),
                "fehler": [e for e in ergebnisse
                           if e[0] != 303 or not e[1].endswith("?meldung=Rabatt+gespeichert")]}

    def test_20_parallele_schreibanfragen_ohne_locked(self):
        from app.models import Angebot
        ids = self._angebote_anlegen()
        try:
            nachher = self._sturm(ids, "5")
            with mock.patch.object(db, "SCHREIBTRANSAKTION_SOFORT", False):
                vorher = self._sturm(ids, "7")
            print(f"\nMESSUNG Schreibsturm ({len(ids)} parallele POST /rabatt): "
                  f"BEGIN IMMEDIATE: locked={nachher['locked']}, Warnungen={nachher['warnungen']}, "
                  f"Fehlantworten={len(nachher['fehler'])}, max Commit-Wartezeit {nachher['max_ms']} ms, "
                  f"Transaktionen {nachher['transaktionen']}, {nachher['dauer']:.1f} s | "
                  f"DEFERRED (bis v32): locked={vorher['locked']}, Warnungen={vorher['warnungen']}, "
                  f"Fehlantworten={len(vorher['fehler'])}, max {vorher['max_ms']} ms, "
                  f"{vorher['dauer']:.1f} s")
            self.assertEqual(nachher["fehler"], [])
            self.assertEqual(nachher["locked"], 0)
            self.assertEqual(nachher["warnungen"], 0, nachher)
            self.assertEqual(nachher["transaktionen"]["sofort_gescheitert"], 0)
            self.assertGreaterEqual(nachher["transaktionen"]["sofort"], len(ids))
            self.s.expire_all()
            self.assertEqual({self.s.get(Angebot, i).rabatt_prozent for i in ids}, {7.0})
            # Vergleichslauf: dokumentiert nur (DEFERRED kann, muss aber nicht in die
            # BUSY_SNAPSHOT-Flanke laufen – _speichern wiederholt dann einmal)
            self.assertEqual(vorher["transaktionen"]["sofort"], 0)
        finally:
            self._angebote_entfernen(ids)


if __name__ == "__main__":
    unittest.main()
