# v27-Nachtrag 07.10.2026 (Antworten von Andreas): Pflichtfragen-Wächter für
# Bestands-Erfassungen, Admin-Zugang „Als Benutzer anmelden“, PIN-Mindestlänge 4,
# Geocoding-Obergrenze, Wartungsfenster 22:30–23:30, Mail-Abgleich 90 Tage.
import unittest
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, betrieb, db, geocoding, mail_sync
from app import konfigurator as engine
from app.db import SessionLocal, init_db
from app.logik import logik_einlesen
from app.main import app
from app.models import Benutzer, GeocodeCache, LoginProtokoll
from tests.test_regression import KONTROLL_SZENARIO


def admin_client() -> TestClient:
    c = TestClient(app)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
    return c


class Pflichtfragen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.logik, bericht = logik_einlesen()
        assert not bericht.fehler, bericht.fehler

    def test_optionale_fragen_blockieren_nicht(self):
        antworten = dict(KONTROLL_SZENARIO)
        self.assertIsNone(engine.naechste_frage(self.logik, antworten))
        for frage_id in engine.OPTIONALE_FRAGEN:
            antworten.pop(frage_id, None)
        # der Bogen meldet die fehlende optionale Frage weiterhin …
        offen = engine.naechste_frage(self.logik, antworten)
        if offen is not None:
            self.assertTrue(engine.ist_optional(offen), offen.id)
        # … der Wächter für „Angebot erzeugen“ nicht mehr
        self.assertIsNone(engine.naechste_pflichtfrage(self.logik, antworten))
        # eine echte Pflichtfrage bleibt ein Hindernis
        pflicht = next(f for f in engine.sichtbare_fragen(self.logik, antworten)
                       if not engine.ist_optional(f))
        antworten.pop(pflicht.id)
        self.assertEqual(engine.naechste_pflichtfrage(self.logik, antworten).id, pflicht.id)


class AdminZugang(unittest.TestCase):
    NAME = "V27N Zugangstest"

    def setUp(self):
        init_db()
        with db.kurz() as s:
            s.query(Benutzer).filter(Benutzer.name == self.NAME).delete()
            b = Benutzer(name=self.NAME, rolle="innendienst", pin_hash=auth.pin_hash("4711"),
                         aktiv=True, pin_wechsel_noetig=False)
            s.add(b)
            s.flush()
            self.benutzer_id = b.id

    def tearDown(self):
        with db.kurz() as s:
            s.query(LoginProtokoll).filter(LoginProtokoll.benutzer_id == self.benutzer_id).delete()
            s.query(Benutzer).filter(Benutzer.id == self.benutzer_id).delete()

    def test_admin_meldet_sich_als_benutzer_an(self):
        c = admin_client()
        r = c.post(f"/benutzer/{self.benutzer_id}/anmelden-als", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/angebotstool")
        cookie = r.cookies.get(auth.COOKIE_NAME)
        self.assertIsNotNone(cookie)
        self.assertEqual(auth.cookie_pruefen(cookie)[0], self.benutzer_id)
        with db.kurz() as s:
            zeile = (s.query(LoginProtokoll).filter(LoginProtokoll.benutzer_id == self.benutzer_id)
                     .order_by(LoginProtokoll.id.desc()).first())
            self.assertTrue(zeile.erfolg)
            self.assertTrue(zeile.grund.startswith("admin_zugang:"))
        # mit dem Cookie ist man der Benutzer
        c2 = TestClient(app)
        c2.cookies.set(auth.COOKIE_NAME, cookie)
        self.assertIn(self.NAME, c2.get("/angebotstool").text)

    def test_nicht_bei_offenem_pflichtwechsel_und_nicht_fuer_innendienst(self):
        with db.kurz() as s:
            s.get(Benutzer, self.benutzer_id).pin_wechsel_noetig = True
        r = admin_client().post(f"/benutzer/{self.benutzer_id}/anmelden-als", follow_redirects=False)
        self.assertIn("Pflicht-PIN-Wechsel", r.headers["location"] and
                      __import__("urllib.parse").parse.unquote_plus(r.headers["location"]))
        # Innendienst erreicht /benutzer gar nicht (Middleware)
        with db.kurz() as s:
            s.get(Benutzer, self.benutzer_id).pin_wechsel_noetig = False
        c = TestClient(app)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(self.benutzer_id))
        r = c.post(f"/benutzer/{self.benutzer_id}/anmelden-als", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/")


class Entscheidungen(unittest.TestCase):
    def test_pin_mindestlaenge_vier(self):
        self.assertEqual(auth.PIN_MINDESTLAENGE_NEU, 4)
        self.assertIsNone(auth.pin_regel_pruefen("4718"))
        self.assertIsNotNone(auth.pin_regel_pruefen("471"))
        self.assertIsNotNone(auth.pin_regel_pruefen("1234"))   # Sperrliste

    def test_wartungsfenster_dienstag_2230(self):
        von, bis = betrieb.naechstes_wartungsfenster(datetime(2026, 10, 7, 12, 0))
        self.assertEqual((von.weekday(), von.hour, von.minute, bis.hour, bis.minute), (1, 22, 30, 23, 30))
        self.assertEqual(betrieb.WARTUNG_STANDARD, "Dienstag 22:30–23:30")

    def test_geocoding_gibt_nach_zehn_versuchen_auf(self):
        cache = GeocodeCache(adresse_norm="v27n test", status="fehler", versuche=10,
                             stand=datetime.now() - timedelta(days=30))
        self.assertFalse(geocoding.erneut_faellig(cache))
        cache.versuche = 3
        self.assertTrue(geocoding.erneut_faellig(cache))
        cache.stand = datetime.now()
        self.assertFalse(geocoding.erneut_faellig(cache))

    def test_mail_abgleich_fenster(self):
        self.assertEqual(mail_sync.ABGLEICH_TAGE, 90)


if __name__ == "__main__":
    unittest.main()
