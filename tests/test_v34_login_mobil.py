# v34 (PLAN_V21 Phase 181, Agent M): „Auf diesem Gerät angemeldet bleiben“ am Handy –
# Cookie-Attribute je Rolle und Gerät. Ursache (Nachweis diagnose/v34/M_ergebnis.md): das
# Häkchen galt seit v27-Nachtrag 2 nur für Außendienst/Montage (auth.MOBILE_ROLLEN), Admin/
# Innendienst bekamen am Handy immer 12 h, das Cookie trug nur Max-Age (kein Expires).
# Soll: Häkchen für ALLE Rollen auf Mobilgeräten (User-Agent Mobile/Android/iPhone/iPad ODER
# Formularfeld mobil=1), 30 Tage (sitzung_tage_mobil), Cookie mit Max-Age UND Expires,
# SameSite=Lax, HttpOnly, Path=/, Secure nur bei HTTPS_AKTIV; Verlängerung nur beim Login;
# Büro-Rollen am PC 12 h; Außendienst/Montage wie v27 auf jedem Gerät 30 Tage.
import re
import unittest
import warnings
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, config
from app.db import SessionLocal, init_db
from app.main import app
from app.models import Benutzer, LoginProtokoll

PRAEFIX = "V34M-Login "
PIN = "48152"
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
ANDROID = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/129.0 Mobile Safari/537.36")
IPAD = ("Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.5 Mobile/15E148 Safari/604.1")
PC = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/129.0 Safari/537.36")
TAG_30 = 30 * 24 * 3600
STD_12 = 12 * 3600


def sitzungs_cookie(antwort) -> dict:
    """Attribute des Sitzungs-Cookies aus dem Set-Cookie-Header (max-age, expires, secure …)."""
    kopf = antwort.headers
    alle = kopf.get_list("set-cookie") if hasattr(kopf, "get_list") else kopf.getlist("set-cookie")
    for header in alle:
        if header.startswith(auth.COOKIE_NAME + "="):
            jar = SimpleCookie()
            jar.load(header)
            morsel = jar[auth.COOKIE_NAME]
            return {"wert": morsel.value, "max_age": morsel["max-age"], "expires": morsel["expires"],
                    "secure": bool(morsel["secure"]), "httponly": bool(morsel["httponly"]),
                    "samesite": morsel["samesite"], "path": morsel["path"], "roh": header}
    return {}


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        cls.aufraeumen()
        cls.benutzer = {}
        for rolle in ("admin", "innendienst", "aussendienst", "montage", "projektierung"):
            b = Benutzer(name=f"{PRAEFIX}{rolle}", rolle=rolle, aktiv=True,
                         email=f"v34m-login-{rolle}@example.invalid")
            auth.pin_setzen(b, PIN)
            cls.s.add(b)
            cls.benutzer[rolle] = b
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        cls.aufraeumen()
        cls.s.close()

    @classmethod
    def aufraeumen(cls):
        for b in cls.s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
            cls.s.query(LoginProtokoll).filter(LoginProtokoll.benutzer_id == b.id).delete()
            cls.s.delete(b)
        cls.s.commit()

    def setUp(self):
        auth.ip_zaehler_zuruecksetzen()

    def login(self, rolle: str, ua: str, haekchen: bool = True, **extra):
        daten = {"benutzer_id": str(self.benutzer[rolle].id), "pin": PIN}
        if haekchen:
            daten["angemeldet_bleiben"] = "on"
        daten.update(extra)
        c = TestClient(app)
        r = c.post("/login", data=daten, headers={"User-Agent": ua}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text[:300])
        return r, c


class CookieJeRolleUndGeraet(Basis):
    def test_admin_handy_haekchen_30_tage_mit_expires(self):
        """Kontrollwert des Plans: Admin am Handy, Häkchen → Max-Age=2592000 + Expires, ohne Secure."""
        r, c = self.login("admin", IPHONE)
        ck = sitzungs_cookie(r)
        self.assertEqual(int(ck["max_age"]), TAG_30, ck["roh"])
        self.assertTrue(ck["expires"], ck["roh"])
        ablauf = parsedate_to_datetime(ck["expires"])
        self.assertAlmostEqual(ablauf, datetime.now(timezone.utc) + timedelta(seconds=TAG_30),
                               delta=timedelta(minutes=2))
        self.assertFalse(ck["secure"], ck["roh"])
        self.assertTrue(ck["httponly"], ck["roh"])
        self.assertEqual(ck["samesite"].lower(), "lax", ck["roh"])
        self.assertEqual(ck["path"], "/", ck["roh"])
        # Ablauf im signierten Cookie-Wert passt zu Max-Age (cookie_pruefen akzeptiert ihn)
        kennung, zaehler = auth.cookie_pruefen(ck["wert"])
        self.assertEqual(kennung, self.benutzer["admin"].id)
        ablauf_wert = int(ck["wert"].split(":")[2])
        self.assertAlmostEqual(ablauf_wert, int(datetime.now().timestamp()) + TAG_30, delta=120)
        # mit dem Cookie ist der Admin angemeldet
        self.assertEqual(c.get("/angebotstool", headers={"User-Agent": IPHONE}).status_code, 200)

    def test_buero_rollen_am_pc_12_stunden(self):
        for rolle in ("admin", "innendienst", "projektierung"):
            r, _ = self.login(rolle, PC, haekchen=True)
            self.assertEqual(int(sitzungs_cookie(r)["max_age"]), STD_12, rolle)
            r, _ = self.login(rolle, PC, haekchen=False)
            self.assertEqual(int(sitzungs_cookie(r)["max_age"]), STD_12, rolle)
            self.assertTrue(sitzungs_cookie(r)["expires"], rolle)   # Expires auch bei 12 h

    def test_innendienst_android_ipad_und_formularfeld(self):
        r, _ = self.login("innendienst", ANDROID)
        self.assertEqual(int(sitzungs_cookie(r)["max_age"]), TAG_30)
        r, _ = self.login("innendienst", IPAD)
        self.assertEqual(int(sitzungs_cookie(r)["max_age"]), TAG_30)
        # PC-User-Agent, aber das Skript der Anmeldeseite meldet mobil=1 (Breite < 600 px / Touch)
        r, _ = self.login("innendienst", PC, mobil="1")
        self.assertEqual(int(sitzungs_cookie(r)["max_age"]), TAG_30)
        # Handy ohne Häkchen bleibt bei 12 h
        r, _ = self.login("innendienst", ANDROID, haekchen=False)
        self.assertEqual(int(sitzungs_cookie(r)["max_age"]), STD_12)
        # mobil=0 am PC: keine Verlängerung
        r, _ = self.login("innendienst", PC, mobil="0")
        self.assertEqual(int(sitzungs_cookie(r)["max_age"]), STD_12)

    def test_aussendienst_und_montage_unveraendert(self):
        """v27 bleibt: Außendienst/Montage mit Häkchen auf JEDEM Gerät 30 Tage."""
        r, _ = self.login("aussendienst", PC)
        self.assertEqual(int(sitzungs_cookie(r)["max_age"]), TAG_30)
        r, _ = self.login("montage", IPAD)
        self.assertEqual(int(sitzungs_cookie(r)["max_age"]), TAG_30)
        r, _ = self.login("aussendienst", IPHONE, haekchen=False)
        self.assertEqual(int(sitzungs_cookie(r)["max_age"]), STD_12)

    def test_secure_nur_bei_https(self):
        with mock.patch.object(config, "HTTPS_AKTIV", True):
            r, _ = self.login("admin", IPHONE)
        self.assertTrue(sitzungs_cookie(r)["secure"], sitzungs_cookie(r)["roh"])
        r, _ = self.login("admin", IPHONE)
        self.assertFalse(sitzungs_cookie(r)["secure"])

    def test_keine_verlaengerung_je_anfrage(self):
        """Sliding nur beim Login: eine normale Seite setzt das Sitzungs-Cookie nicht neu."""
        r, c = self.login("admin", IPHONE)
        seite = c.get("/angebotstool", headers={"User-Agent": IPHONE})
        self.assertEqual(seite.status_code, 200)
        self.assertEqual(sitzungs_cookie(seite), {}, seite.headers.get_list("set-cookie"))

    def test_parameter_sitzung_tage_mobil(self):
        """Dauer kommt aus sitzung_tage_mobil / sitzung_stunden_buero (auth.sitzungsdauer_s)."""
        admin = self.benutzer["admin"]
        self.assertEqual(auth.sitzungsdauer_s(self.s, admin, True, mobil=True), TAG_30)
        self.assertEqual(auth.sitzungsdauer_s(self.s, admin, True, mobil=False), STD_12)
        self.assertEqual(auth.sitzungsdauer_s(self.s, admin, False, mobil=True), STD_12)
        self.assertEqual(auth.sitzungsdauer_s(self.s, self.benutzer["montage"], True), TAG_30)


class Anmeldeseite(Basis):
    def test_haekchen_fuer_alle_rollen_auf_mobilgeraet(self):
        html = TestClient(app).get("/login", headers={"User-Agent": IPHONE}).text
        self.assertIn('data-mobil-geraet="1"', html)
        self.assertIn('name="mobil" id="login-mobil" value="1"', html)
        self.assertIn("Auf diesem Gerät angemeldet bleiben", html)
        self.assertIn("Als App auf dem Home-Bildschirm bitte dort anmelden.", html)
        self.assertIn("für alle Rollen", html)
        # Skript: Breite < 600 px / Touch meldet mobil=1, Block für alle Rollen sichtbar
        self.assertIn("window.innerWidth < 600", html)
        self.assertIn("rolleMobil || mobil", html)
        # Markierung der v27-Mobilrollen bleibt (Außendienst/Montage auch am PC)
        self.assertRegex(html, r'<option value="\d+" data-mobil="1">')

    def test_pc_ohne_mobilkennzeichen(self):
        html = TestClient(app).get("/login", headers={"User-Agent": PC}).text
        self.assertIn('data-mobil-geraet="0"', html)
        self.assertIn('name="mobil" id="login-mobil" value=""', html)

    def test_fehlermeldung_behaelt_geraet(self):
        r = TestClient(app).post("/login", data={"benutzer_id": str(self.benutzer["admin"].id),
                                                 "pin": "0000", "angemeldet_bleiben": "on"},
                                 headers={"User-Agent": IPHONE}, follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertIn('data-mobil-geraet="1"', r.text)
        self.assertIn('value="on"\n                               checked', r.text)


class Helfer(unittest.TestCase):
    def test_ist_mobilgeraet(self):
        self.assertTrue(auth.ist_mobilgeraet(IPHONE))
        self.assertTrue(auth.ist_mobilgeraet(ANDROID))
        self.assertTrue(auth.ist_mobilgeraet(IPAD))
        self.assertFalse(auth.ist_mobilgeraet(PC))
        self.assertFalse(auth.ist_mobilgeraet(""))
        self.assertFalse(auth.ist_mobilgeraet(None))
        self.assertTrue(auth.ist_mobilgeraet(PC, "1"))
        self.assertTrue(auth.ist_mobilgeraet(PC, "on"))
        self.assertFalse(auth.ist_mobilgeraet(PC, "0"))
        self.assertFalse(auth.ist_mobilgeraet(PC, ""))
        # iPad im Desktop-Modus meldet sich als Mac – nur das Formularfeld hilft
        mac = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.5 Safari/605.1.15"
        self.assertFalse(auth.ist_mobilgeraet(mac))
        self.assertTrue(auth.ist_mobilgeraet(mac, "1"))

    def test_cookie_wert_fuer_tests_und_crawl_unveraendert(self):
        wert = auth.cookie_wert(1)
        self.assertEqual(wert.split(":")[0], auth.COOKIE_VERSION)
        self.assertEqual(auth.cookie_pruefen(wert)[0], 1)
        c = TestClient(app)
        c.cookies.set(auth.COOKIE_NAME, wert)
        self.assertEqual(c.get("/angebotstool").status_code, 200)

    def test_cookie_setzen_expires_passt_zu_max_age(self):
        from fastapi.responses import Response
        antwort = Response()
        benutzer = Benutzer(name="x", rolle="admin")
        benutzer.id = 1
        auth.cookie_setzen(antwort, benutzer, 3600)
        ck = sitzungs_cookie(antwort)
        self.assertEqual(int(ck["max_age"]), 3600)
        ablauf = parsedate_to_datetime(ck["expires"])
        self.assertAlmostEqual(ablauf, datetime.now(timezone.utc) + timedelta(hours=1),
                               delta=timedelta(minutes=2))
        self.assertRegex(ck["roh"], r"expires=\w{3}, \d\d \w{3} \d{4} \d\d:\d\d:\d\d GMT")


if __name__ == "__main__":
    unittest.main()
