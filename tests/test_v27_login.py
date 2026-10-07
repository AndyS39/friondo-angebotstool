# Tests PLAN_V17 Phase 130 (v27): Login-Härtung – Alt-Hash-Login mit stiller
# Umstellung, Fehlversuchssperre und Freigabe (Ablauf / „Sperre aufheben“),
# Cookie-Ablauf und „Alle Sitzungen beenden“, Pflicht-PIN-Wechsel mit Regeln,
# Sitzungsdauer je Rolle und Häkchen, Benutzerverwaltung (PIN-Regeln, Filter,
# Letzter Login, Hinweise, Einstellungen-Block), CSV-Import mit 50 Benutzern und
# Fehlerfällen, Login-Protokoll-Seite, Rollen-Regression Außendienst/Montage,
# IP-Grenze. Läuft gegen die Entwicklungs-DB; Testdaten tragen das Präfix
# „V27B “ und werden wieder aufgeräumt. Der Admin (ID 1) wird nicht verändert.
import html as html_modul
import re
import unittest
import warnings
from datetime import datetime, timedelta
from types import SimpleNamespace
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, benutzer_import
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Benutzer, Einstellung, LoginProtokoll, Team, TeamMitglied,
                        einstellung_holen, einstellung_setzen)

PRAEFIX = "V27B "
ALTE_PIN = "1234"             # Alt-Hash (SHA-256), bestehende PINs bleiben gültig
GUELTIGE_PIN = "482913"       # besteht alle Regeln
ZWEITE_PIN = "739146"
EINSTELLUNGEN = ("sitzung_stunden_buero", "sitzung_tage_mobil",
                 "pin_mindestlaenge", "pin_sperrliste")
MAX_AGE = re.compile(r"max-age=(\d+)", re.I)


def aufraeumen(s):
    s.rollback()
    from app import lead_termin
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(TeamMitglied).filter_by(benutzer_id=b.id).delete()
        s.query(LoginProtokoll).filter_by(benutzer_id=b.id).delete()
        try:
            if lead_termin.kanal_regel_fuer_ad(s, b.id):
                lead_termin.kanal_regel_ad_setzen(s, b.id, [])
        except Exception:
            pass
        s.delete(b)
    for t in s.query(Team).filter(Team.name.like(f"{PRAEFIX}%")):
        s.query(TeamMitglied).filter_by(team_id=t.id).delete()
        s.delete(t)
    # Protokollzeilen gelöschter Testbenutzer (benutzer_id = NULL, Name bleibt)
    s.query(LoginProtokoll).filter(LoginProtokoll.benutzer_name.like(f"{PRAEFIX}%")).delete(
        synchronize_session=False)
    s.commit()


def zeile(html: str, benutzer_id: int) -> str:
    """Nur die Hauptzeile eines Benutzers (bis zu seiner Detailzeile)."""
    start = html.index(f'id="zeile-{benutzer_id}"')
    ende = html.index(f'id="details-{benutzer_id}"', start)
    return html[start:ende]


def max_age(antwort) -> int:
    treffer = MAX_AGE.search(antwort.headers.get("set-cookie", ""))
    return int(treffer.group(1)) if treffer else -1


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.admin = TestClient(app)
        cls.admin.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        cls.team = Team(name=f"{PRAEFIX}Montage", typ="montage", aktiv=True, erstellt_von=1)
        cls.s.add(cls.team)
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def setUp(self):
        auth.ip_zaehler_zuruecksetzen()

    def benutzer_anlegen(self, name, rolle="innendienst", pin=ALTE_PIN, **felder):
        """Testbenutzer wie in v26: nur pin_hash (SHA-256), pin_hash_v2 leer."""
        if rolle == "aussendienst":
            felder.setdefault("email", f"{name.lower().replace(' ', '.')}@example.invalid")
        b = Benutzer(name=f"{PRAEFIX}{name}", rolle=rolle, pin_hash=auth.pin_hash(pin), **felder)
        self.s.add(b)
        self.s.commit()
        # SQLite vergibt IDs gelöschter Benutzer neu – verwaiste Protokollzeilen
        # früherer Testbenutzer (andere Testdateien löschen ihre Benutzer ohne
        # Protokoll) würden sonst Zähler und Fehlversuchsfenster verfälschen
        self.s.query(LoginProtokoll).filter_by(benutzer_id=b.id).delete()
        self.s.commit()
        return b

    def neu_laden(self, benutzer):
        self.s.commit()
        self.s.refresh(benutzer)
        return benutzer

    def login(self, client, benutzer, pin, **extra):
        daten = {"benutzer_id": str(benutzer.id), "pin": pin}
        daten.update(extra)
        return client.post("/login", data=daten, follow_redirects=False)

    def protokoll(self, benutzer):
        return [p.grund for p in self.s.query(LoginProtokoll)
                .filter_by(benutzer_id=benutzer.id).order_by(LoginProtokoll.id)]


class LoginHaertung(Basis):
    def test_alt_hash_login_stille_umstellung(self):
        b = self.benutzer_anlegen("Althash")
        self.assertFalse(b.pin_hash_v2)
        c = TestClient(app)
        r = self.login(c, b, ALTE_PIN)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/angebotstool")
        cookie = c.cookies.get(auth.COOKIE_NAME)
        self.assertTrue(cookie)
        self.assertTrue(cookie.startswith(auth.COOKIE_VERSION + ":"))
        geprueft = auth.cookie_pruefen(cookie)
        self.assertIsNotNone(geprueft)
        self.assertEqual(geprueft[0], b.id)
        self.neu_laden(b)
        self.assertTrue((b.pin_hash_v2 or "").startswith(auth.PBKDF2_KENNUNG + "$"))
        self.assertIsNotNone(b.letzter_login)
        self.assertEqual(b.pin_hash, auth.pin_hash(ALTE_PIN))   # v26-Spalte unverändert
        self.assertTrue(auth.pin_pruefen(b, ALTE_PIN))
        self.assertEqual(self.protokoll(b), ["ok"])
        self.assertEqual(c.get("/angebote", follow_redirects=False).status_code, 200)
        self.assertEqual(c.get("/login").status_code, 200)   # Login-Seite rendert weiter

    def test_login_formular_haekchen(self):
        html = TestClient(app).get("/login").text
        self.assertIn('name="angemeldet_bleiben"', html)
        self.assertIn("Auf diesem Gerät angemeldet bleiben", html)
        self.assertIn("login_v27.css", html)
        # Fehlermeldung bleibt HTTP 200 mit dem Text aus auth
        r = TestClient(app).post("/login", data={"benutzer_id": "0", "pin": "1"},
                                 follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertIn(auth.PIN_FALSCH_TEXT, r.text)

    def test_sperre_nach_fuenf_fehlversuchen_und_freigabe(self):
        b = self.benutzer_anlegen("Sperre")
        c = TestClient(app)
        for _ in range(auth.MAX_FEHLVERSUCHE - 1):
            r = self.login(c, b, "000000")
            self.assertEqual(r.status_code, 200)
            self.assertIn(auth.PIN_FALSCH_TEXT, r.text)
            self.assertNotIn(auth.SPERRE_TEXT, r.text)
        r = self.login(c, b, "000000")             # 5. Fehlversuch → Sperre, wörtlich
        self.assertEqual(r.status_code, 200)
        self.assertIn(auth.SPERRE_TEXT, r.text)
        r = self.login(c, b, ALTE_PIN)             # richtige PIN, aber gesperrt
        self.assertEqual(r.status_code, 200)
        self.assertIn(auth.SPERRE_TEXT, r.text)
        self.neu_laden(b)
        self.assertIsNotNone(b.gesperrt_bis)
        self.assertGreater(b.gesperrt_bis, datetime.now())
        gruende = self.protokoll(b)
        self.assertEqual(gruende.count("pin_falsch"), auth.MAX_FEHLVERSUCHE)
        self.assertEqual(gruende[-1], "gesperrt")
        # Freigabe nach Ablauf: gesperrt_bis in der Vergangenheit → Login ok
        b.gesperrt_bis = datetime.now() - timedelta(minutes=1)
        self.s.commit()
        r = self.login(c, b, ALTE_PIN)
        self.assertEqual(r.status_code, 303)
        self.neu_laden(b)
        self.assertIsNone(b.gesperrt_bis)
        self.assertEqual(b.fehlversuche, 0)
        self.assertEqual(self.protokoll(b)[-1], "ok")
        # erneut sperren → Benutzerliste zeigt Hinweis + Knopf, Admin hebt auf
        for _ in range(auth.MAX_FEHLVERSUCHE):
            self.login(c, b, "000000")
        self.neu_laden(b)
        self.assertIsNotNone(b.gesperrt_bis)
        z = zeile(self.admin.get("/benutzer").text, b.id)
        self.assertIn("gesperrt bis", z)
        self.assertIn(f'action="/benutzer/{b.id}/sperre-aufheben"', z)
        r = self.admin.post(f"/benutzer/{b.id}/sperre-aufheben", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Sperre", unquote_plus(r.headers["location"]))
        self.neu_laden(b)
        self.assertIsNone(b.gesperrt_bis)
        self.assertEqual(b.fehlversuche, 0)
        r = self.login(c, b, ALTE_PIN)
        self.assertEqual(r.status_code, 303)
        self.assertNotIn("gesperrt bis", zeile(self.admin.get("/benutzer").text, b.id))

    def test_cookie_ablauf_und_alle_sitzungen_beenden(self):
        b = self.benutzer_anlegen("Cookie", "aussendienst")
        c = TestClient(app)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(b.id, dauer_s=-5))
        r = c.get("/erfassung", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/login")
        c = TestClient(app)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(b.id))
        self.assertEqual(c.get("/erfassung", follow_redirects=False).status_code, 200)
        # Admin: „Alle Sitzungen beenden“ → altes Cookie ungültig
        r = self.admin.post(f"/benutzer/{b.id}/sitzungen-beenden", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Sitzungen", unquote_plus(r.headers["location"]))
        self.neu_laden(b)
        self.assertEqual(b.sitzungszaehler, 1)
        r = c.get("/erfassung", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/login")
        # neues Login trägt den neuen Zähler
        c2 = TestClient(app)
        r = self.login(c2, b, ALTE_PIN)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(auth.cookie_pruefen(c2.cookies.get(auth.COOKIE_NAME))[1], 1)
        self.assertEqual(c2.get("/erfassung", follow_redirects=False).status_code, 200)
        # Ein Admin beendet die eigenen Sitzungen → andere Geräte raus, dieses
        # Gerät bleibt über ein frisches Cookie angemeldet (eigener Test-Admin,
        # der Entwicklungs-Admin ID 1 bleibt unangetastet)
        admin2 = self.benutzer_anlegen("Admin Zwei", "admin")
        geraet_a = TestClient(app)
        geraet_b = TestClient(app)
        self.login(geraet_a, admin2, ALTE_PIN)
        self.login(geraet_b, admin2, ALTE_PIN)
        self.assertEqual(geraet_b.get("/benutzer", follow_redirects=False).status_code, 200)
        r = geraet_a.post(f"/benutzer/{admin2.id}/sitzungen-beenden", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("dieses Gerät bleibt angemeldet", unquote_plus(r.headers["location"]))
        self.assertIn("set-cookie", r.headers)
        self.assertEqual(geraet_a.get("/benutzer", follow_redirects=False).status_code, 200)
        r = geraet_b.get("/benutzer", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/login")

    def test_pflichtwechsel_pin(self):
        b = self.benutzer_anlegen("Wechsel", pin=GUELTIGE_PIN, pin_wechsel_noetig=True)
        c = TestClient(app)
        r = self.login(c, b, GUELTIGE_PIN)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], auth.PIN_WECHSEL_PFAD)
        r = c.get("/angebote", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/pin-wechsel")
        r = c.get("/pin-wechsel")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f"mindestens {auth.pin_mindestlaenge(self.s)} Ziffern", r.text)
        self.assertIn("Start-PIN gilt nur", r.text)

        def wechsel(alt, neu, neu2=None):
            return c.post("/pin-wechsel", data={"pin_alt": alt, "pin_neu": neu,
                                                "pin_neu2": neu if neu2 is None else neu2},
                          follow_redirects=False)

        # zu einfach: Sperrliste, Wiederholung, Zahlenfolge, Jahreszahl, zu kurz
        for schlecht in ("123456", "111111", "7777777", "234567", "198512", "12345"):
            erwartet = auth.pin_regel_pruefen(schlecht, self.s)
            self.assertIsNotNone(erwartet, schlecht)
            r = wechsel(GUELTIGE_PIN, schlecht)
            self.assertEqual(r.status_code, 200, schlecht)
            self.assertIn(erwartet, r.text, schlecht)
        r = wechsel("000000", ZWEITE_PIN)
        self.assertIn("aktuelle PIN ist falsch", r.text)
        r = wechsel(GUELTIGE_PIN, ZWEITE_PIN, "739147")
        self.assertIn("nicht zweimal gleich", r.text)
        r = wechsel(GUELTIGE_PIN, GUELTIGE_PIN)
        self.assertIn("unterscheiden", r.text)
        self.neu_laden(b)
        self.assertTrue(b.pin_wechsel_noetig)
        self.assertTrue(auth.pin_pruefen(b, GUELTIGE_PIN))
        # gültig → Flag weg, beide Hash-Spalten, Startseite der Rolle
        r = wechsel(GUELTIGE_PIN, ZWEITE_PIN)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/angebotstool")
        self.neu_laden(b)
        self.assertFalse(b.pin_wechsel_noetig)
        self.assertEqual(b.pin_hash, auth.pin_hash(ZWEITE_PIN))
        self.assertTrue(b.pin_hash_v2.startswith(auth.PBKDF2_KENNUNG + "$"))
        self.assertTrue(auth.pin_pruefen(b, ZWEITE_PIN))
        self.assertFalse(auth.pin_pruefen(b, GUELTIGE_PIN))
        self.assertEqual(c.get("/angebote", follow_redirects=False).status_code, 200)
        # freiwilliger Wechsel bleibt erreichbar (ohne Pflicht-Hinweis)
        r = c.get("/pin-wechsel")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Start-PIN gilt nur", r.text)

    def test_sitzungsdauer_haekchen(self):
        ad = self.benutzer_anlegen("Dauer AD", "aussendienst")
        innen = self.benutzer_anlegen("Dauer Innen", "innendienst")
        r = self.login(TestClient(app), ad, ALTE_PIN, angemeldet_bleiben="on")
        self.assertEqual(r.status_code, 303)
        self.assertEqual(max_age(r), 30 * 24 * 3600)
        self.assertEqual(max_age(r), auth.sitzungsdauer_s(self.s, ad, True))
        r = self.login(TestClient(app), ad, ALTE_PIN)
        self.assertEqual(max_age(r), 12 * 3600)
        r = self.login(TestClient(app), innen, ALTE_PIN, angemeldet_bleiben="on")
        self.assertEqual(max_age(r), 12 * 3600)
        # Ablauf im Cookie passt zur max-age
        c = TestClient(app)
        self.login(c, ad, ALTE_PIN, angemeldet_bleiben="on")
        ablauf = int(c.cookies.get(auth.COOKIE_NAME).split(":")[2])
        self.assertAlmostEqual(ablauf, int(datetime.now().timestamp()) + 30 * 86400, delta=60)

    def test_ip_grenze(self):
        inaktiv = self.benutzer_anlegen("IP inaktiv", aktiv=False)
        c = TestClient(app)
        for _ in range(auth.IP_MAX_VERSUCHE):
            r = self.login(c, inaktiv, ALTE_PIN)
            self.assertEqual(r.status_code, 200)
            self.assertIn(auth.PIN_FALSCH_TEXT, r.text)
            self.assertNotIn(auth.IP_SPERRE_TEXT, r.text)
        r = self.login(c, inaktiv, ALTE_PIN)       # 31. Versuch
        self.assertEqual(r.status_code, 200)
        self.assertIn(auth.IP_SPERRE_TEXT, r.text)
        gruende = self.protokoll(inaktiv)
        self.assertEqual(gruende.count("inaktiv"), auth.IP_MAX_VERSUCHE)
        self.assertEqual(gruende[-1], "ip_limit")
        auth.ip_zaehler_zuruecksetzen()
        r = self.login(c, inaktiv, ALTE_PIN)
        self.assertIn(auth.PIN_FALSCH_TEXT, r.text)

    def test_rollen_regression_aussendienst_und_montage(self):
        ad = self.benutzer_anlegen("Rollen AD", "aussendienst")
        c = TestClient(app)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(ad.id))
        for pfad in ("/angebote", "/artikel", "/parametrierung", "/benutzer",
                     "/benutzer/login-protokoll", "/angebotstool"):
            r = c.get(pfad, follow_redirects=False)
            self.assertEqual(r.status_code, 303, pfad)
            self.assertEqual(r.headers["location"], "/erfassung", pfad)
        r = c.get("/pin-wechsel")
        self.assertEqual(r.status_code, 200)
        self.assertIn("PIN ändern", r.text)
        r = c.post("/pin-wechsel", data={"pin_alt": "0000", "pin_neu": ZWEITE_PIN,
                                         "pin_neu2": ZWEITE_PIN}, follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertIn("aktuelle PIN ist falsch", r.text)
        montage = self.benutzer_anlegen("Rollen Montage", "montage")
        c2 = TestClient(app)
        c2.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(montage.id))
        self.assertEqual(c2.get("/pin-wechsel").status_code, 200)
        r = c2.get("/angebote", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/montage")


class Benutzerverwaltung(Basis):
    def test_anlegen_und_aendern_mit_pin_regeln(self):
        name = f"{PRAEFIX}Neu"
        daten = {"name": name, "rolle": "innendienst", "email": "", "pin": "123",   # zu kurz (Mindestlänge 4 seit 07.10.2026)
                 "pin_wechsel": "on"}
        r = self.admin.post("/benutzer/neu", data=daten, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("mindestens", unquote_plus(r.headers["location"]))
        self.assertIsNone(self.s.query(Benutzer).filter_by(name=name).first())
        daten["pin"] = "123456"
        r = self.admin.post("/benutzer/neu", data=daten, follow_redirects=False)
        self.assertIn("Sperrliste", unquote_plus(r.headers["location"]))
        daten["pin"] = GUELTIGE_PIN
        r = self.admin.post("/benutzer/neu", data=daten, follow_redirects=False)
        self.assertIn("Benutzer+angelegt", r.headers["location"])
        self.s.expire_all()
        b = self.s.query(Benutzer).filter_by(name=name).one()
        self.assertTrue(b.pin_wechsel_noetig)
        self.assertEqual(b.pin_hash, auth.pin_hash(GUELTIGE_PIN))
        self.assertTrue(b.pin_hash_v2.startswith(auth.PBKDF2_KENNUNG + "$"))
        self.assertTrue(auth.pin_pruefen(b, GUELTIGE_PIN))
        self.assertIn("PIN-Wechsel offen", zeile(self.admin.get("/benutzer").text, b.id))
        # ohne Häkchen → kein Pflichtwechsel
        r = self.admin.post("/benutzer/neu", data={"name": f"{PRAEFIX}Neu2", "rolle": "innendienst",
                                                   "email": "", "pin": ZWEITE_PIN},
                            follow_redirects=False)
        self.assertIn("Benutzer+angelegt", r.headers["location"])
        self.s.expire_all()
        b2 = self.s.query(Benutzer).filter_by(name=f"{PRAEFIX}Neu2").one()
        self.assertFalse(b2.pin_wechsel_noetig)
        # Ändern: Admin-Reset mit Regeln
        aendern = {"name": name, "rolle": "innendienst", "email": "", "aktiv": "on",
                   "pin": "111111", "pin_wechsel": "on"}
        r = self.admin.post(f"/benutzer/{b.id}/aendern", data=aendern, follow_redirects=False)
        self.assertIn("PIN:", unquote_plus(r.headers["location"]))
        self.neu_laden(b)
        self.assertTrue(auth.pin_pruefen(b, GUELTIGE_PIN))      # unverändert
        aendern["pin"] = ZWEITE_PIN
        r = self.admin.post(f"/benutzer/{b.id}/aendern", data=aendern, follow_redirects=False)
        self.assertIn("Gespeichert", r.headers["location"])
        self.neu_laden(b)
        self.assertTrue(b.pin_wechsel_noetig)
        self.assertEqual(b.pin_hash, auth.pin_hash(ZWEITE_PIN))
        self.assertTrue(auth.pin_pruefen(b, ZWEITE_PIN))
        # Reset ohne Häkchen → Flag aus; leere PIN → nichts an der PIN geändert
        aendern.pop("pin_wechsel")
        aendern["pin"] = GUELTIGE_PIN
        self.admin.post(f"/benutzer/{b.id}/aendern", data=aendern, follow_redirects=False)
        self.neu_laden(b)
        self.assertFalse(b.pin_wechsel_noetig)
        self.assertTrue(auth.pin_pruefen(b, GUELTIGE_PIN))
        aendern["pin"] = ""
        aendern["pin_wechsel"] = "on"
        self.admin.post(f"/benutzer/{b.id}/aendern", data=aendern, follow_redirects=False)
        self.neu_laden(b)
        self.assertFalse(b.pin_wechsel_noetig)
        self.assertTrue(auth.pin_pruefen(b, GUELTIGE_PIN))

    def test_loeschen_entkoppelt_protokoll(self):
        # SQLite vergibt IDs neu: beim Löschen verlieren die Protokollzeilen die
        # Benutzer-ID (Name bleibt als Historie), damit sie keinem späteren
        # Benutzer mit derselben ID zugerechnet werden
        b = self.benutzer_anlegen("Loeschen")
        self.login(TestClient(app), b, ALTE_PIN)
        self.assertEqual(self.protokoll(b), ["ok"])
        kennung = b.id
        r = self.admin.post(f"/benutzer/{kennung}/loeschen", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("gelöscht", unquote_plus(r.headers["location"]))
        self.s.expire_all()
        self.assertIsNone(self.s.get(Benutzer, kennung))
        self.assertEqual(self.s.query(LoginProtokoll).filter_by(benutzer_id=kennung).count(), 0)
        reste = self.s.query(LoginProtokoll).filter_by(benutzer_name=f"{PRAEFIX}Loeschen").all()
        self.assertEqual([p.grund for p in reste], ["ok"])
        self.assertIsNone(reste[0].benutzer_id)

    def test_liste_filter_letzter_login_hinweise(self):
        ad = self.benutzer_anlegen("Filter AD", "aussendienst",
                                   letzter_login=datetime(2026, 10, 1, 8, 30))
        innen = self.benutzer_anlegen("Filter Innen", aktiv=False)
        gesperrt = self.benutzer_anlegen("Filter Gesperrt",
                                         gesperrt_bis=datetime.now() + timedelta(minutes=10))
        offen = self.benutzer_anlegen("Filter Offen", "montage", pin_wechsel_noetig=True)
        html = self.admin.get("/benutzer").text
        self.assertIn("Letzter Login", html)
        self.assertIn("01.10.2026 08:30", zeile(html, ad.id))
        self.assertIn("noch nie", zeile(html, innen.id))
        self.assertIn("gesperrt bis", zeile(html, gesperrt.id))
        self.assertIn(f'action="/benutzer/{gesperrt.id}/sperre-aufheben"', zeile(html, gesperrt.id))
        self.assertIn("PIN-Wechsel offen", zeile(html, offen.id))
        self.assertNotIn("PIN-Wechsel offen", zeile(html, ad.id))
        self.assertNotIn("gesperrt bis", zeile(html, ad.id))
        self.assertNotIn("sperre-aufheben", zeile(html, ad.id))
        self.assertIn(f'action="/benutzer/{ad.id}/sitzungen-beenden"', html)
        self.assertIn('href="/benutzer/import"', html)
        self.assertIn('href="/benutzer/login-protokoll"', html)
        self.assertIn('id="einstellungen"', html)
        self.assertIn('name="pin_wechsel" checked', html)
        # Filter Rolle + aktiv
        html = self.admin.get("/benutzer?rolle=aussendienst&aktiv=1").text
        self.assertIn(ad.name, html)
        self.assertNotIn(innen.name, html)
        self.assertNotIn(gesperrt.name, html)
        self.assertIn('value="aussendienst" selected', html)
        html = self.admin.get("/benutzer?aktiv=0").text
        self.assertIn(innen.name, html)
        self.assertNotIn(ad.name, html)
        html = self.admin.get("/benutzer?rolle=unsinn&aktiv=7").text   # ungültig = alle
        self.assertIn(ad.name, html)
        self.assertIn(innen.name, html)

    def test_einstellungen_block(self):
        vorher = {e.name: e.wert for e in self.s.query(Einstellung)
                  .filter(Einstellung.name.in_(EINSTELLUNGEN))}
        try:
            r = self.admin.post("/benutzer/einstellungen",
                                data={"sitzung_stunden_buero": "8", "sitzung_tage_mobil": "14",
                                      "pin_mindestlaenge": "8",
                                      "pin_sperrliste": "12345678; 87654321,abc 12345678"},
                                follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("Einstellungen+gespeichert", r.headers["location"])
            s2 = SessionLocal()
            try:
                self.assertEqual(einstellung_holen(s2, "sitzung_stunden_buero", ""), "8")
                self.assertEqual(einstellung_holen(s2, "sitzung_tage_mobil", ""), "14")
                self.assertEqual(einstellung_holen(s2, "pin_mindestlaenge", ""), "8")
                self.assertEqual(einstellung_holen(s2, "pin_sperrliste", ""), "12345678,87654321")
                self.assertEqual(auth.pin_mindestlaenge(s2), 8)
                self.assertEqual(auth.sitzungsdauer_s(s2, SimpleNamespace(rolle="aussendienst"), True),
                                 14 * 86400)
                self.assertEqual(auth.sitzungsdauer_s(s2, SimpleNamespace(rolle="innendienst"), True),
                                 8 * 3600)
                self.assertIn("mindestens 8", auth.pin_regel_pruefen(GUELTIGE_PIN, s2))
                self.assertEqual(len(benutzer_import.start_pin(s2)), 8)
            finally:
                s2.close()
            html = TestClient(app).get("/login").text
            self.assertIn("14 Tage", html)
            self.assertIn("8 Stunden", html)
            html = self.admin.get("/benutzer").text
            self.assertIn('value="14"', html)
            self.assertIn("12345678,87654321", html)
            self.assertIn("mind. 8 Ziffern", html)
            # unplausible Werte → Fehlermeldung, nichts geändert
            for falsch in ({"pin_mindestlaenge": "3"}, {"pin_mindestlaenge": "13"},
                           {"sitzung_tage_mobil": "0"}, {"sitzung_stunden_buero": "abc"}):
                daten = {"sitzung_stunden_buero": "8", "sitzung_tage_mobil": "14",
                         "pin_mindestlaenge": "8", "pin_sperrliste": "12345678,87654321"}
                daten.update(falsch)
                r = self.admin.post("/benutzer/einstellungen", data=daten, follow_redirects=False)
                self.assertEqual(r.status_code, 303)
                self.assertIn("nicht gespeichert", unquote_plus(r.headers["location"]), falsch)
            s3 = SessionLocal()
            try:
                self.assertEqual(einstellung_holen(s3, "pin_mindestlaenge", ""), "8")
                self.assertEqual(einstellung_holen(s3, "sitzung_tage_mobil", ""), "14")
            finally:
                s3.close()
        finally:
            s4 = SessionLocal()
            try:
                for name in EINSTELLUNGEN:
                    if name in vorher:
                        einstellung_setzen(s4, name, vorher[name])
                    else:
                        s4.query(Einstellung).filter(Einstellung.name == name).delete()
                s4.commit()
            finally:
                s4.close()

    def test_login_protokoll_seite(self):
        b = self.benutzer_anlegen("Protokoll")
        c = TestClient(app)
        self.login(c, b, "000000")      # Fehlversuch
        self.login(c, b, ALTE_PIN)      # Erfolg
        html = self.admin.get("/benutzer/login-protokoll").text
        self.assertIn("Anmeldeversuche 24 h", html)
        self.assertIn("Fehlversuche 24 h", html)
        self.assertIn(b.name, html)
        html = self.admin.get(f"/benutzer/login-protokoll?benutzer_id={b.id}").text
        zeilen = re.findall(r'<tr id="lp-\d+">(.*?)</tr>', html, re.S)
        self.assertEqual(len(zeilen), 2)
        self.assertTrue(all(b.name in z for z in zeilen))
        self.assertIn("PIN falsch", zeilen[1])        # neueste zuerst
        self.assertIn(">OK<", zeilen[0])
        self.assertIn("testclient", html)            # IP-Kurzform des TestClient
        html = self.admin.get(f"/benutzer/login-protokoll?benutzer_id={b.id}&nur_fehler=1").text
        zeilen = re.findall(r'<tr id="lp-\d+">(.*?)</tr>', html, re.S)
        self.assertEqual(len(zeilen), 1)
        self.assertIn("PIN falsch", zeilen[0])
        self.assertNotIn(">OK<", zeilen[0])
        # gesperrter Benutzer oben mit „Sperre aufheben“ (zurück zum Protokoll)
        b.gesperrt_bis = datetime.now() + timedelta(minutes=10)
        self.s.commit()
        html = self.admin.get("/benutzer/login-protokoll").text
        self.assertIn("Aktuell gesperrte Benutzer", html)
        self.assertIn(f'action="/benutzer/{b.id}/sperre-aufheben"', html)
        self.assertIn('name="zurueck" value="protokoll"', html)
        r = self.admin.post(f"/benutzer/{b.id}/sperre-aufheben", data={"zurueck": "protokoll"},
                            follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/benutzer/login-protokoll?meldung="))
        self.neu_laden(b)
        self.assertIsNone(b.gesperrt_bis)
        self.assertNotIn(f'action="/benutzer/{b.id}/sperre-aufheben"',
                         self.admin.get("/benutzer/login-protokoll").text)
        # Parametrierung verlinkt genau diesen Pfad; Innendienst kommt nicht hinein
        self.assertIn('href="/benutzer/login-protokoll"', self.admin.get("/parametrierung").text)
        innen = self.benutzer_anlegen("Protokoll Innen")
        c2 = TestClient(app)
        c2.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(innen.id))
        r = c2.get("/benutzer/login-protokoll", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/")


class CsvImport(Basis):
    def csv_50(self):
        kanaele = benutzer_import.kanal_werte_import(self.s)
        self.kanal = kanaele[0] if kanaele else ""
        zeilen = ["Name;Rolle;E-Mail;Team;Vertriebskanal"]
        rollen = ["Innendienst", "Außendienst", "Montage", "Projektierung", "aussendienst"]
        for i in range(1, 51):
            rolle = rollen[i % 5]
            ad = rolle.lower() in ("außendienst", "aussendienst")
            email = f"v27b.import{i}@example.invalid" if (ad or i % 3 == 0) else ""
            team = self.team.name if rolle == "Montage" else ""
            kanal = self.kanal if (ad and i % 2 == 0) else ""
            zeilen.append(f"{PRAEFIX}Import {i:02d};{rolle};{email};{team};{kanal}")
        return "\r\n".join(zeilen) + "\r\n"

    def importierte(self):
        self.s.expire_all()
        return (self.s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}Import %"))
                .order_by(Benutzer.name).all())

    def test_import_50_vorschau_und_ausfuehren(self):
        from app import lead_termin
        text = self.csv_50()
        self.assertEqual(self.importierte(), [])
        # Vorschau per Datei-Upload (UTF-8 mit BOM) – legt nichts an
        r = self.admin.post("/benutzer/import", data={"aktion": "vorschau"},
                            files={"datei": ("benutzer.csv", ("﻿" + text).encode("utf-8"),
                                             "text/csv")})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text.count('<td class="pruefung ok">OK</td>'), 50)
        self.assertIn("50 Benutzer jetzt anlegen", r.text)
        self.assertIn('name="aktion" value="ausfuehren"', r.text)
        self.assertEqual(self.importierte(), [])
        # CSV-Text wandert im Formular zum zweiten POST
        treffer = re.search(r'<textarea name="csv_text"[^>]*>(.*?)</textarea>', r.text, re.S)
        self.assertIsNotNone(treffer)
        csv_text = html_modul.unescape(treffer.group(1))
        r = self.admin.post("/benutzer/import", data={"aktion": "ausfuehren", "csv_text": csv_text})
        self.assertEqual(r.status_code, 200)
        self.assertIn("50 Benutzer angelegt", r.text)
        self.assertIn("nur einmal angezeigt", r.text)
        paare = re.findall(r"<tr>\s*<td>(.*?)</td>\s*<td>.*?</td>\s*"
                           r'<td class="start-pin">(\d+)</td>', r.text, re.S)
        self.assertEqual(len(paare), 50)
        angelegt = self.importierte()
        self.assertEqual(len(angelegt), 50)
        je_name = {b.name: b for b in angelegt}
        for name, pin in paare:
            b = je_name[html_modul.unescape(name)]
            self.assertIsNone(auth.pin_regel_pruefen(pin, self.s), pin)
            self.assertTrue(b.pin_wechsel_noetig)
            self.assertTrue(auth.pin_pruefen(b, pin))
            self.assertEqual(b.pin_hash, auth.pin_hash(pin))
            self.assertNotIn(pin, b.pin_hash_v2)
        rollen = {b.rolle for b in angelegt}
        self.assertEqual(rollen, {"innendienst", "aussendienst", "montage", "projektierung"})
        for b in angelegt:
            mitglied = [m.team_id for m in self.s.query(TeamMitglied).filter_by(benutzer_id=b.id)]
            self.assertEqual(mitglied, [self.team.id] if b.rolle == "montage" else [])
            if b.rolle == "aussendienst":
                self.assertTrue(b.email)
                nummer = int(b.name.rsplit(" ", 1)[1])
                erwartet = [self.kanal.lower()] if (self.kanal and nummer % 2 == 0) else []
                self.assertEqual(lead_termin.kanal_regel_fuer_ad(self.s, b.id), erwartet)
        # Start-PIN → Login → Pflichtwechsel; keine PIN im Protokoll
        name, pin = paare[0]
        b = je_name[html_modul.unescape(name)]
        r = self.login(TestClient(app), b, pin)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/pin-wechsel")
        # zweiter Import derselben Datei → alle Namen „bereits vorhanden“
        r = self.admin.post("/benutzer/import", data={"aktion": "vorschau", "csv_text": csv_text})
        self.assertEqual(r.text.count("Name bereits vorhanden"), 50)
        self.assertNotIn('value="ausfuehren"', r.text)

    def test_import_fehler_blockieren(self):
        admin_name = self.s.get(Benutzer, 1).name
        text = ("Name;Rolle;E-Mail;Team;Vertriebskanal\n"
                f"{PRAEFIX}Fehler Doppelt;Innendienst;;;\n"
                f"{PRAEFIX}Fehler Doppelt;Innendienst;;;\n"
                f"{admin_name};Innendienst;;;\n"
                f"{PRAEFIX}Fehler Rolle;Chef;;;\n"
                f"{PRAEFIX}Fehler AD;Außendienst;;;\n"
                f"{PRAEFIX}Fehler Team;Montage;;Gibt es nicht;\n"
                f"{PRAEFIX}Fehler Kanal;Innendienst;;;Enni\n"
                f"{PRAEFIX}Fehler Mail;Innendienst;keine-mail;;\n"
                f"{PRAEFIX}Fehler OK;Innendienst;;;\n")
        r = self.admin.post("/benutzer/import", data={"aktion": "vorschau", "csv_text": text})
        self.assertEqual(r.status_code, 200)
        for erwartet in ("Name doppelt in der Datei", "Name bereits vorhanden", "Rolle unbekannt",
                         "E-Mail-Adresse Pflicht", "Team unbekannt",
                         "Vertriebskanal nur für Außendienst", "E-Mail-Adresse ist ungültig"):
            self.assertIn(erwartet, r.text, erwartet)
        # erste „Doppelt“-Zeile und „Fehler OK“ sind in Ordnung – trotzdem ist alles blockiert
        self.assertEqual(r.text.count('<td class="pruefung ok">OK</td>'), 2)
        self.assertIn("Es wird nichts angelegt", r.text)
        self.assertNotIn('value="ausfuehren"', r.text)
        # Ausführen trotz Fehlern → blockiert, nichts angelegt
        r = self.admin.post("/benutzer/import", data={"aktion": "ausfuehren", "csv_text": text})
        self.assertEqual(r.status_code, 200)
        self.assertIn("nicht ausgeführt", r.text)
        self.assertEqual(self.s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}Fehler%")).count(), 0)
        # unbekannter Kanal beim Außendienst
        r = self.admin.post("/benutzer/import", data={
            "aktion": "vorschau",
            "csv_text": f"Name;Rolle;E-Mail;Team;Vertriebskanal\n{PRAEFIX}Kanal AD;Außendienst;k@example.invalid;;GibtEsNicht\n"})
        self.assertIn("Vertriebskanal unbekannt", r.text)
        # Kopfzeile fehlt / Datei leer
        r = self.admin.post("/benutzer/import", data={"aktion": "vorschau",
                                                      "csv_text": "Max;Innendienst;;;\n"})
        self.assertIn("Kopfzeile unvollständig", r.text)
        r = self.admin.post("/benutzer/import", data={"aktion": "vorschau", "csv_text": "   "})
        self.assertIn("Bitte eine CSV-Datei auswählen", r.text)
        # Komma-Trennung und Rollenschlüssel sind erlaubt
        r = self.admin.post("/benutzer/import", data={
            "aktion": "vorschau", "csv_text": f"Name,Rolle,E-Mail\n{PRAEFIX}Komma,innendienst,\n"})
        self.assertEqual(r.text.count('<td class="pruefung ok">OK</td>'), 1)
        self.assertIn("1 Benutzer jetzt anlegen", r.text)

    def test_vorlage_und_formular(self):
        r = self.admin.get("/benutzer/import/vorlage.csv")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["content-type"].startswith("text/csv"))
        self.assertTrue(r.content.startswith("﻿".encode("utf-8")))
        self.assertTrue(r.text.lstrip("﻿").startswith("Name;Rolle;E-Mail;Team;Vertriebskanal"))
        zeilen, fehler = benutzer_import.csv_lesen(r.text)
        self.assertEqual(fehler, [])
        self.assertEqual(len(zeilen), 4)
        r = self.admin.get("/benutzer/import")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Vorschau anzeigen", r.text)
        self.assertIn('href="/benutzer/import/vorlage.csv"', r.text)


class ImportFunktionen(unittest.TestCase):
    def test_csv_lesen_varianten(self):
        zeilen, fehler = benutzer_import.csv_lesen(
            "﻿Name,Rolle,E-Mail\r\nMax,innendienst,MAX@x.de\r\n\r\n")
        self.assertEqual(fehler, [])
        self.assertEqual(len(zeilen), 1)
        self.assertEqual((zeilen[0].name, zeilen[0].rolle_roh, zeilen[0].email, zeilen[0].nr),
                         ("Max", "innendienst", "max@x.de", 2))
        zeilen, fehler = benutzer_import.csv_lesen("Name;Rolle;E-Mail;Team;Vertriebskanal\n"
                                                   "A;Montage;;Team X;\n")
        self.assertEqual(fehler, [])
        self.assertEqual(zeilen[0].team, "Team X")
        _, fehler = benutzer_import.csv_lesen("Max;Innendienst\n")
        self.assertTrue(fehler and "Kopfzeile unvollständig" in fehler[0])
        _, fehler = benutzer_import.csv_lesen("")
        self.assertTrue(fehler and "leer" in fehler[0])
        _, fehler = benutzer_import.csv_lesen("Name;Rolle;E-Mail\n")
        self.assertTrue(fehler and "keine Benutzerzeile" in fehler[0])
        text = benutzer_import.text_dekodieren(
            "Name;Rolle;E-Mail\nJörg Müller;Außendienst;j@x.de\n".encode("cp1252"))
        self.assertIn("Jörg Müller", text)
        self.assertEqual(benutzer_import.text_dekodieren("﻿Name".encode("utf-8")), "Name")

    def test_rolle_zuordnen_und_start_pin(self):
        self.assertEqual(benutzer_import.rolle_zuordnen("Außendienst"), "aussendienst")
        self.assertEqual(benutzer_import.rolle_zuordnen("aussendienst"), "aussendienst")
        self.assertEqual(benutzer_import.rolle_zuordnen("Lead Management"), "leadmanagement")
        self.assertEqual(benutzer_import.rolle_zuordnen("ADMIN"), "admin")
        self.assertIsNone(benutzer_import.rolle_zuordnen("Chef"))
        self.assertIsNone(benutzer_import.rolle_zuordnen(""))
        for _ in range(20):
            pin = benutzer_import.start_pin(None)
            self.assertEqual(len(pin), 6)
            self.assertIsNone(auth.pin_regel_pruefen(pin, None))


if __name__ == "__main__":
    unittest.main()
