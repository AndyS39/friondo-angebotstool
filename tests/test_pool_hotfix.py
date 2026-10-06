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
import threading
import time
import unittest
import warnings
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from sqlalchemy.exc import TimeoutError as PoolTimeout
from starlette.requests import Request

from app import auth, db, fehlerprotokoll, lead_termin, routing
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


if __name__ == "__main__":
    unittest.main()
