# v27 (PLAN_V17 Phase 129/132): /health, Betriebs-Seite, Scheduler-Rahmen,
# Zugriffsprotokoll, Backup-Lauf mit Spiegelung, SQLite-Pflege, Wartungsbanner,
# Indizes, Formular-Helfer. Läuft gegen die Entwicklungs-DB ohne Netz.
import json
import shutil
import tempfile
import threading
import time
import unittest
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import anfrage, auth, betrieb, config, db, scheduler, zugriffslog
from app.db import SessionLocal, init_db
from app.main import app
from app.models import Einstellung, SchedulerStatus, einstellung_holen


def admin_client() -> TestClient:
    c = TestClient(app)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
    return c


class Health(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_health_ohne_login(self):
        r = TestClient(app).get("/health")
        self.assertIn(r.status_code, (200, 503))
        daten = r.json()
        for feld in ("status", "version", "commit", "db", "db_ms", "pool", "scheduler",
                     "backup_letztes", "wal_mb", "uptime_s", "gruende"):
            self.assertIn(feld, daten)
        self.assertEqual(daten["version"], config.VERSION)
        self.assertEqual(daten["db"], "ok")
        self.assertEqual(r.status_code, 200)
        self.assertIn(daten["status"], ("ok", "warn"))
        self.assertEqual(set(daten["pool"]) >= {"size", "checked_out", "overflow"}, True)
        self.assertEqual(r.headers.get("cache-control"), "no-store")

    def test_health_warn_bei_vollem_pool_und_altem_backup(self):
        with mock.patch.object(db, "pool_kennzahlen", return_value={
                "size": 20, "checked_out": 50, "overflow": 30, "maximum": 60,
                "timeout_s": 10, "prozent": 83.3}):
            daten = betrieb.health()
        self.assertEqual(daten["status"], "warn")
        self.assertTrue(any("Pool" in g for g in daten["gruende"]), daten["gruende"])
        alt = {"lokal_zeit": datetime.now() - timedelta(hours=30), "ziel_zeit": None,
               "ziel_status": "fehler", "ziel_text": "", "ziel": "X:\\ziel"}
        with mock.patch.object(betrieb, "backup_letztes", return_value=alt):
            daten = betrieb.health()
        self.assertIn("letztes Backup > 26 h", daten["gruende"])
        self.assertIn("Backup-Spiegelung fehlgeschlagen", daten["gruende"])

    def test_health_fehler_ohne_datenbank(self):
        with mock.patch.object(betrieb.sqlite3, "connect", side_effect=RuntimeError("Datenbank weg")):
            daten = betrieb.health()
        self.assertEqual(daten["status"], "fehler")
        r = TestClient(app).get("/health")   # echte DB ist wieder da
        self.assertEqual(r.status_code, 200)

    def test_health_pool_erschoepft_ist_warnung_nicht_fehler(self):
        voll = {"size": 20, "checked_out": 90, "overflow": 70, "maximum": 90,
                "timeout_s": 10, "prozent": 100.0}
        with mock.patch.object(db, "pool_kennzahlen", return_value=voll):
            daten = betrieb.health()
        self.assertEqual(daten["status"], "warn")
        self.assertIn("Pool erschöpft (alle Verbindungen belegt)", daten["gruende"])
        self.assertEqual(daten["db"], "ok")

    def test_wache_glocke_hoechstens_einmal_je_stunde(self):
        warnung = {"status": "warn", "gruende": ["kein Backup-Ziel"]}
        betrieb._glocke_zuletzt["zeit"] = None
        with mock.patch.object(betrieb, "health", return_value=warnung), \
                mock.patch.object(betrieb, "admins_benachrichtigen", return_value=1) as glocke:
            erg1 = betrieb.wache_lauf()
            erg2 = betrieb.wache_lauf()
        self.assertEqual((erg1["glocke"], erg2["glocke"]), (1, 0))
        self.assertEqual(glocke.call_count, 1)
        betrieb._glocke_zuletzt["zeit"] = None


class BetriebsSeite(unittest.TestCase):
    def test_nur_admin(self):
        c = TestClient(app)
        self.assertEqual(c.get("/parametrierung/betrieb", follow_redirects=False).status_code, 303)

    def test_seite_zeigt_kacheln_scheduler_und_zugriffe(self):
        c = admin_client()
        c.get("/angebote")   # erzeugt eine Zugriffszeile
        r = c.get("/parametrierung/betrieb")
        self.assertEqual(r.status_code, 200)
        for text in ("Version / Commit", "Uptime", "Pool (aktuell / Spitze 24 h)", "Threads",
                     "WAL-Datei", "Letztes Backup", "Hintergrundläufe", "Zugriffe der letzten 24 h",
                     "Wartungshinweis", "Laufende Importe", "Top 20 Routen"):
            self.assertIn(text, r.text)
        # die Auswertung ist 60 s zwischengespeichert – frisch nachrechnen
        erg = zugriffslog.auswerten(24, erzwingen=True)
        self.assertGreater(erg["gesamt"], 0)
        self.assertTrue(erg["routen"] and erg["langsamste"])
        self.assertIn("MB RAM", r.text)
        self.assertNotIn("? MB RAM", r.text)

    def test_lauf_jetzt_ausfuehren(self):
        scheduler.registrieren("v27-test-lauf", 60, lambda: {"ok": 1}, beschreibung="Test")
        try:
            c = admin_client()
            r = c.post("/parametrierung/betrieb/lauf/v27-test-lauf", follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("gestartet", r.headers["location"])
            lauf = scheduler.holen("v27-test-lauf")
            for _ in range(50):          # Hintergrund-Thread, höchstens 5 s warten
                if lauf.laeufe >= 1 and not lauf.sperre.locked():
                    break
                time.sleep(0.1)
            self.assertEqual(lauf.laeufe, 1)
            self.assertEqual(lauf.zustand, "ok")
            r = c.post("/parametrierung/betrieb/lauf/gibt-es-nicht", follow_redirects=False)
            self.assertIn("unbekannter", r.headers["location"])
        finally:
            scheduler._LAEUFE.pop("v27-test-lauf", None)
            with db.kurz() as s:
                s.query(SchedulerStatus).filter_by(name="v27-test-lauf").delete()


class Wartung(unittest.TestCase):
    def tearDown(self):
        with db.kurz() as s:
            betrieb.wartung_loeschen(s)

    def test_banner_fuer_alle_rollen_und_wortlaut(self):
        c = admin_client()
        heute = datetime.now().strftime("%Y-%m-%d")
        r = c.post("/parametrierung/betrieb/wartung",
                   data={"von": f"{heute}T18:30", "bis": f"{heute}T23:59"},
                   follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        r = c.get("/angebote")
        self.assertIn("Wartung heute von 18:30 bis 23:59 Uhr – bitte Arbeit bis dahin speichern. "
                      "Das Tool ist in dieser Zeit kurz nicht erreichbar.", r.text)
        self.assertIn('id="wartung-banner"', r.text)
        self.assertIn("wartung-banner", c.get("/login").text)   # auch ohne Anmeldung sichtbar
        r = c.post("/parametrierung/betrieb/wartung", data={"loeschen": "1"},
                   follow_redirects=False)
        self.assertNotIn("wartung-banner", c.get("/angebote").text)

    def test_abgelaufenes_fenster_verschwindet(self):
        with db.kurz() as s:
            betrieb.wartung_setzen(s, datetime.now() - timedelta(hours=2),
                                   datetime.now() - timedelta(hours=1))
            self.assertIsNone(betrieb.wartungshinweis(s))
        with self.assertRaises(ValueError):
            with db.kurz() as s:
                betrieb.wartung_setzen(s, "2026-10-06T19:00", "2026-10-06T18:00")

    def test_naechstes_standardfenster_dienstag(self):
        von, bis = betrieb.naechstes_wartungsfenster(datetime(2026, 10, 7, 12, 0))   # Mittwoch
        self.assertEqual((von.weekday(), von.hour, von.minute, bis.hour, bis.minute),
                         (1, 18, 30, 19, 30))
        self.assertEqual(von.date(), datetime(2026, 10, 13).date())
        von, bis = betrieb.naechstes_wartungsfenster(datetime(2026, 10, 6, 12, 0))   # Dienstag vor 18:30
        self.assertEqual(von.date(), datetime(2026, 10, 6).date())


class SchedulerRahmen(unittest.TestCase):
    def setUp(self):
        self.namen = []

    def tearDown(self):
        for name in self.namen:
            scheduler._LAEUFE.pop(name, None)
        with db.kurz() as s:
            s.query(SchedulerStatus).filter(SchedulerStatus.name.like("v27-rahmen-%")).delete(
                synchronize_session=False)

    def _registrieren(self, name, funktion, **kw):
        self.namen.append(name)
        return scheduler.registrieren(name, 60, funktion, **kw)

    def test_lauf_zaehlt_misst_und_schreibt_status(self):
        self._registrieren("v27-rahmen-a", lambda: {"zeilen": [1, 2, 3], "ok": True})
        erg = scheduler.ausfuehren("v27-rahmen-a")
        self.assertFalse(erg["uebersprungen"])
        self.assertTrue(erg["ok"])
        lauf = scheduler.holen("v27-rahmen-a")
        self.assertEqual((lauf.laeufe, lauf.fehler, lauf.zustand), (1, 0, "ok"))
        self.assertIn("zeilen=3", lauf.letztes_ergebnis)
        with db.kurz() as s:
            zeile = s.query(SchedulerStatus).filter_by(name="v27-rahmen-a").one()
            self.assertEqual(zeile.laeufe, 1)
            self.assertIsNotNone(zeile.letzter_start)

    def test_fehler_wird_vermerkt_und_nicht_geworfen(self):
        def kaputt():
            raise ValueError("absichtlich")
        self._registrieren("v27-rahmen-b", kaputt)
        erg = scheduler.ausfuehren("v27-rahmen-b")
        self.assertFalse(erg["ok"])
        self.assertIn("ValueError: absichtlich", erg["fehler"])
        lauf = scheduler.holen("v27-rahmen-b")
        self.assertEqual((lauf.laeufe, lauf.fehler, lauf.zustand), (1, 1, "fehler"))
        self.assertFalse(lauf.als_dict()["ok"])

    def test_single_flight(self):
        gestartet = threading.Event()
        def langsam():
            gestartet.set()
            time.sleep(0.8)
        self._registrieren("v27-rahmen-c", langsam)
        t = threading.Thread(target=scheduler.ausfuehren, args=("v27-rahmen-c",))
        t.start()
        gestartet.wait(2)
        zweiter = scheduler.ausfuehren("v27-rahmen-c")
        t.join()
        self.assertTrue(zweiter["uebersprungen"])
        self.assertEqual(zweiter["grund"], "läuft bereits")
        self.assertEqual(scheduler.holen("v27-rahmen-c").laeufe, 1)

    def test_inaktiv_mit_grund_und_manuell_trotzdem(self):
        zaehler = {"n": 0}
        def lauf():
            zaehler["n"] += 1
        self._registrieren("v27-rahmen-d", lauf, aktiv=lambda: "kein Token")
        erg = scheduler.ausfuehren("v27-rahmen-d")
        self.assertTrue(erg["uebersprungen"])
        self.assertEqual(zaehler["n"], 0)
        self.assertIn("inaktiv (kein Token)", scheduler.holen("v27-rahmen-d").als_dict()["zustand"])
        erg = scheduler.jetzt_ausfuehren("v27-rahmen-d")
        self.assertFalse(erg["uebersprungen"])
        self.assertEqual(zaehler["n"], 1)

    def test_taeglich_um_und_ueberfaellig(self):
        lauf = self._registrieren("v27-rahmen-e", lambda: None, taeglich_um="02:30")
        self.assertEqual(lauf.intervall_effektiv_s, 24 * 3600)
        ziel = scheduler._naechste_tageszeit("02:30", datetime(2026, 10, 6, 3, 0))
        self.assertEqual(ziel, datetime(2026, 10, 7, 2, 30))
        ziel = scheduler._naechste_tageszeit("02:30", datetime(2026, 10, 6, 1, 0))
        self.assertEqual(ziel, datetime(2026, 10, 6, 2, 30))
        kurz = self._registrieren("v27-rahmen-f", lambda: None)
        kurz.intervall_s = 10
        self.assertFalse(kurz.ueberfaellig())
        kurz.registriert_am = datetime.now() - timedelta(seconds=10 * 2 + 31 + 5)
        self.assertTrue(kurz.ueberfaellig())
        kurz.aktiv = lambda: False
        self.assertFalse(kurz.ueberfaellig())

    def test_threads_starten_und_stoppen(self):
        lauf = self._registrieren("v27-rahmen-g", lambda: None, start_verzoegerung_s=600)
        vorher = threading.active_count()
        with mock.patch.object(scheduler, "JITTER_MAX_S", 0):
            gestartet = scheduler.starten_alle()
        self.assertGreaterEqual(gestartet, 1)
        self.assertTrue(lauf.thread.is_alive())
        scheduler.stoppen(timeout_s=2)
        self.assertIsNone(lauf.thread)
        self.assertLessEqual(threading.active_count(), vorher + len(scheduler.alle()))


class Zugriffslog(unittest.TestCase):
    def test_route_normalisieren(self):
        self.assertEqual(zugriffslog.route_normalisieren("/angebote/123/pdf"), "/angebote/{id}/pdf")
        self.assertEqual(zugriffslog.route_normalisieren("/lead-management/lead/7"),
                         "/lead-management/lead/{id}")
        self.assertEqual(zugriffslog.route_normalisieren("/signatur/extern/" + "a" * 32),
                         "/signatur/extern/{token}")

    def test_auswertung_aus_datei(self):
        ordner = Path(tempfile.mkdtemp(prefix="v27zugriff"))
        try:
            jetzt = datetime.now()
            zeilen = []
            for i in range(30):
                zeilen.append(zugriffslog.TRENNER.join([
                    (jetzt - timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%S.000"),
                    "1", "admin", "GET", f"/angebote/{i}", "200", str(100 + i * 100), str(i % 5)]))
            zeilen.append(zugriffslog.TRENNER.join([
                jetzt.strftime("%Y-%m-%dT%H:%M:%S.000"), "2", "innendienst", "POST",
                "/angebote/5/pdf", "500", "4500", "7"]))
            zeilen.append(zugriffslog.TRENNER.join([
                (jetzt - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%S.000"), "2",
                "innendienst", "GET", "/alt", "200", "10", "0"]))   # außerhalb 24 h
            (ordner / zugriffslog.LOG_DATEI).write_text("\n".join(zeilen) + "\n", encoding="utf-8")
            with mock.patch.object(zugriffslog, "log_pfad", return_value=ordner / zugriffslog.LOG_DATEI):
                erg = zugriffslog.auswerten(24, erzwingen=True)
            self.assertEqual(erg["gesamt"], 31)
            self.assertEqual(erg["fehler_5xx"], 1)
            self.assertEqual(erg["pool_spitze"], 7)
            routen = {r["route"]: r for r in erg["routen"]}
            self.assertEqual(routen["GET /angebote/{id}"]["anzahl"], 30)
            self.assertEqual(routen["GET /angebote/{id}"]["p50"], 1500)
            self.assertGreaterEqual(routen["GET /angebote/{id}"]["p95"], 2800)
            self.assertEqual(erg["langsamste"][0]["dauer_ms"], 4500)
            self.assertGreater(erg["anteil_ueber_2s"], 0)
        finally:
            shutil.rmtree(ordner, ignore_errors=True)
            zugriffslog._cache["wert"] = None

    def test_middleware_schreibt_zeile(self):
        c = admin_client()
        c.get("/kunden")
        text = zugriffslog.log_pfad().read_text(encoding="utf-8", errors="replace")
        letzte = [z for z in text.splitlines() if "| GET | /kunden |" in z]
        self.assertTrue(letzte, "keine Zugriffszeile für /kunden")
        teile = letzte[-1].split(zugriffslog.TRENNER)
        self.assertEqual((teile[1], teile[2], teile[5]), ("1", "admin", "200"))
        self.assertTrue(teile[6].isdigit())


class Backup(unittest.TestCase):
    def test_backup_lauf_mit_spiegelung(self):
        ziel = Path(tempfile.mkdtemp(prefix="v27backup"))
        try:
            with mock.patch.object(betrieb, "_robocopy", wraps=betrieb._robocopy) as rc:
                erg = betrieb.backup_lauf(ziel=str(ziel), melden=False)
            self.assertEqual(erg["status"], "ok", erg)
            self.assertTrue(erg["lokal"])
            self.assertTrue((ziel / "backups").exists())
            self.assertTrue(any((ziel / "backups").glob("angebotstool-*.db")))
            self.assertGreaterEqual(rc.call_count, 1)
            with db.kurz() as s:
                wert = einstellung_holen(s, "backup_letztes", "")
            self.assertIn("|ok|", wert)
            letztes = betrieb.backup_letztes()
            self.assertEqual(letztes["ziel_status"], "ok")
            self.assertIsNotNone(letztes["lokal_zeit"])
        finally:
            shutil.rmtree(ziel, ignore_errors=True)

    def test_backup_ohne_ziel_und_mit_fehler(self):
        erg = betrieb.backup_lauf(ziel="", melden=False)
        self.assertEqual(erg["status"], "kein Ziel")
        with mock.patch.object(betrieb, "_robocopy", side_effect=OSError("Ziel weg")), \
                mock.patch.object(betrieb, "admins_benachrichtigen", return_value=1) as glocke, \
                mock.patch("app.fehlerprotokoll.eintragen_text", return_value="F-x") as fp:
            erg = betrieb.backup_lauf(ziel=str(Path(tempfile.gettempdir()) / "v27_nix"), melden=True)
        self.assertEqual(erg["status"], "fehler")
        self.assertEqual(glocke.call_count, 1)
        self.assertEqual(fp.call_count, 1)
        with db.kurz() as s:
            self.assertIn("|fehler|", einstellung_holen(s, "backup_letztes", ""))
        betrieb.backup_lauf(ziel="", melden=False)   # Zustand bereinigen

    def test_sqlite_pflege(self):
        erg = db.wal_pflege()
        self.assertIn("eingespielt", erg)
        self.assertLessEqual(erg["wal_mb_nachher"], max(erg["wal_mb_vorher"], 0.1))

    def test_indizes_vorhanden(self):
        vorhanden = db.vorhandene_indizes()
        for name, _tabelle, _spalten in db._INDIZES:
            self.assertIn(name, vorhanden, name)
        self.assertEqual(db.indizes_anlegen(), [])   # idempotent


class Formularhelfer(unittest.TestCase):
    def test_formular_und_json_in_def_route(self):
        c = admin_client()
        r = c.post("/parametrierung/betrieb/wartung", data={"loeschen": "1"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(anfrage.formular.__name__, "formular")

    def test_keine_async_routen_mehr(self):
        import inspect
        async_routen = [r.path for r in app.routes
                        if getattr(r, "endpoint", None) is not None
                        and inspect.iscoroutinefunction(r.endpoint)
                        and not r.path.startswith(("/docs", "/redoc", "/openapi"))]
        self.assertEqual(async_routen, [])


class MailAusgangWarteschlange(unittest.TestCase):
    """v27 (Phase 128): Sofort-Mails der Glocke landen in mail_ausgang (gleiche
    Transaktion, kein Netz); der Lauf „mail-ausgang“ sendet ohne offene Sitzung."""
    NAME = "V27 Mailausgang Test"

    def setUp(self):
        from app.models import Benutzer, MailAusgang
        with db.kurz() as s:
            s.query(MailAusgang).filter(MailAusgang.empfaenger == "v27-ausgang@test.local").delete()
            s.query(Benutzer).filter(Benutzer.name == self.NAME).delete()
            b = Benutzer(name=self.NAME, rolle="admin", pin_hash=auth.pin_hash("482913"),
                         email="v27-ausgang@test.local", benachrichtigung_mail="sofort", aktiv=True)
            s.add(b)
            s.flush()
            self.benutzer_id = b.id

    def tearDown(self):
        from app.models import Benachrichtigung, Benutzer, MailAusgang
        with db.kurz() as s:
            s.query(MailAusgang).filter(MailAusgang.empfaenger == "v27-ausgang@test.local").delete()
            s.query(Benachrichtigung).filter(Benachrichtigung.benutzer_id == self.benutzer_id).delete()
            s.query(Benutzer).filter(Benutzer.id == self.benutzer_id).delete()

    def test_glocke_reiht_ein_und_lauf_sendet_ohne_sitzung(self):
        from app import benachrichtigungen, graph_versand
        from app import projektierung as kern
        from app.models import MailAusgang
        gesehen = []
        with mock.patch.object(graph_versand, "text_mail_senden") as senden:
            s = SessionLocal()
            try:
                kern.benachrichtigen(s, [self.benutzer_id], "V27 Testglocke", "/parametrierung/betrieb",
                                     art="system")
                self.assertEqual(senden.call_count, 0)   # kein Netz in der Anfrage
                s.flush()   # autoflush=False – Eintrag vor der Zählung schreiben
                self.assertEqual(s.query(MailAusgang).filter_by(
                    empfaenger="v27-ausgang@test.local", status="offen").count(), 1)
                s.commit()
            finally:
                s.close()

        basis = db.engine.pool.checkedout()   # fremde Sitzungen anderer Tests

        def mail(empfaenger, betreff, text, absender):
            gesehen.append((db.engine.pool.checkedout() - basis, empfaenger, betreff))
            return True, ""
        with mock.patch.object(graph_versand, "konfiguriert", return_value=True), \
                mock.patch.object(graph_versand, "text_mail_senden", side_effect=mail):
            erg = benachrichtigungen.mail_ausgang_lauf()
        self.assertEqual(erg["gesendet"], 1, erg)
        self.assertEqual(gesehen[0][0], 0, "Sitzung während des Netzaufrufs offen")
        self.assertEqual(gesehen[0][1], "v27-ausgang@test.local")
        with db.kurz() as s:
            m = s.query(MailAusgang).filter_by(empfaenger="v27-ausgang@test.local").one()
            self.assertEqual((m.status, m.versuche), ("gesendet", 1))
            self.assertIsNotNone(m.gesendet_am)
            self.assertEqual(benachrichtigungen.mail_ausgang_zaehler(s)["offen"], 0)

    def test_fehlversuche_und_graph_fehlt(self):
        from app import benachrichtigungen, graph_versand
        from app.models import MailAusgang
        with db.kurz() as s:
            s.add(MailAusgang(empfaenger="v27-ausgang@test.local", betreff="B", text="T", art="system"))
        with mock.patch.object(graph_versand, "konfiguriert", return_value=True), \
                mock.patch.object(graph_versand, "text_mail_senden", return_value=(False, "kaputt")):
            for _ in range(3):
                erg = benachrichtigungen.mail_ausgang_lauf()
        self.assertEqual(erg["fehler"], 1, erg)
        with db.kurz() as s:
            m = s.query(MailAusgang).filter_by(empfaenger="v27-ausgang@test.local").one()
            self.assertEqual((m.status, m.versuche), ("fehler", 3))
            self.assertIn("kaputt", m.fehler_text)
            s.add(MailAusgang(empfaenger="v27-ausgang@test.local", betreff="B2", text="T", art="system"))
        with mock.patch.object(graph_versand, "konfiguriert", return_value=False):
            erg = benachrichtigungen.mail_ausgang_lauf()
        self.assertEqual(erg["fehler"], 1)
        with db.kurz() as s:
            m = s.query(MailAusgang).filter_by(betreff="B2").one()
            self.assertEqual(m.status, "fehler")
            self.assertIn("Graph nicht eingerichtet", m.fehler_text)


if __name__ == "__main__":
    unittest.main()
