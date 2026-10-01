# v22 (PLAN_V15 Phase 103): Fehlerprotokoll – unbehandelte Ausnahmen bekommen
# eine Fehler-Nr. (Datei-Log + Tabelle), der Benutzer eine lesbare Seite bzw.
# im Editor eine Umleitung mit Meldung; Ansicht Parametrierung → Fehlerprotokoll.
# Test-Routen werden zur Laufzeit registriert und wieder entfernt; Testeinträge
# (Traceback enthält „v22-Test“) werden aufgeräumt.
import json
import unittest
import warnings

warnings.filterwarnings("ignore")

from fastapi import Request
from fastapi.testclient import TestClient

from app import fehlerprotokoll
from app.db import SessionLocal, init_db
from app.main import app
from app.models import Fehlerprotokoll

TEST_MARKE = "v22-Test"
TEST_PFAD_GET = "/v22-test-fehler"
TEST_PFAD_POST = "/angebote/{angebot_id}/v22-test-fehler"
TEST_ANGEBOT_ID = 987654321


def aufraeumen(s):
    s.query(Fehlerprotokoll).filter(
        Fehlerprotokoll.traceback.contains(TEST_MARKE)).delete(synchronize_session=False)
    s.query(Fehlerprotokoll).filter(
        Fehlerprotokoll.pfad.contains("v22-test-fehler")).delete(synchronize_session=False)
    s.commit()


async def _wirft_get(request: Request):
    raise RuntimeError(TEST_MARKE)


async def _wirft_post(request: Request, angebot_id: int):
    await request.form()          # Body im Endpunkt verbrauchen – wie im echten Editor
    raise RuntimeError(TEST_MARKE + " POST")


async def _wirft_gesperrt(request: Request):
    from sqlalchemy.exc import OperationalError
    raise OperationalError("INSERT INTO angebote", {}, Exception("database is locked"))


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.routen = [TEST_PFAD_GET, TEST_PFAD_POST, TEST_PFAD_GET + "-gesperrt"]
        app.add_api_route(TEST_PFAD_GET, _wirft_get, methods=["GET"])
        app.add_api_route(TEST_PFAD_POST, _wirft_post, methods=["POST"])
        app.add_api_route(TEST_PFAD_GET + "-gesperrt", _wirft_gesperrt, methods=["GET"])
        cls.client = TestClient(app, raise_server_exceptions=False)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()
        app.router.routes[:] = [r for r in app.router.routes
                                if getattr(r, "path", "") not in cls.routen]

    def _eintrag(self, nr):
        self.s.expire_all()
        return self.s.query(Fehlerprotokoll).filter(Fehlerprotokoll.fehler_nr == nr).first()

    @staticmethod
    def _nr_aus(text):
        import re
        treffer = re.search(r"F-\d{8}-\d{6}-[0-9a-f]{4}", text)
        return treffer.group(0) if treffer else None


class Handler(Basis):
    def test_get_html_seite_und_tabelleneintrag(self):
        r = self.client.get(TEST_PFAD_GET)
        self.assertEqual(r.status_code, 500)
        self.assertIn("Fehler-Nr.", r.text)
        self.assertIn("Fehlerprotokoll", r.text)
        self.assertIn("text/html", r.headers["content-type"])
        nr = self._nr_aus(r.text)
        self.assertIsNotNone(nr, "Fehler-Nr. fehlt auf der Seite")
        e = self._eintrag(nr)
        self.assertIsNotNone(e, "kein Tabelleneintrag")
        self.assertEqual(e.fehlertyp, "RuntimeError")
        self.assertIn(TEST_MARKE, e.traceback)
        self.assertIn(TEST_MARKE, e.meldung)
        self.assertEqual(e.benutzer_id, 1)
        self.assertEqual(e.methode, "GET")
        self.assertEqual(e.pfad, TEST_PFAD_GET)
        self.assertIsNone(e.angebot_id)
        self.assertFalse(e.erledigt)
        # (e) Datei-Log enthält die Fehler-Nr. samt Traceback
        log = fehlerprotokoll.log_pfad().read_text(encoding="utf-8", errors="replace")
        self.assertIn(nr, log)
        self.assertIn(TEST_MARKE, log)

    def test_post_im_editor_umleitung_mit_formdaten(self):
        pfad = TEST_PFAD_POST.format(angebot_id=TEST_ANGEBOT_ID)
        r = self.client.post(pfad, data={"pin": "1234", "notiz": "hallo", "passwort_neu": "x",
                                         "token_abc": "t", "menge": ["1", "2"]},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        ort = r.headers["location"]
        self.assertTrue(ort.startswith(f"/angebote/{TEST_ANGEBOT_ID}?meldung="), ort)
        self.assertIn("Fehler-Nr", ort)
        nr = self._nr_aus(ort)
        e = self._eintrag(nr)
        self.assertIsNotNone(e)
        self.assertEqual(e.angebot_id, TEST_ANGEBOT_ID)
        self.assertEqual(e.methode, "POST")
        form = json.loads(e.formdaten)
        self.assertEqual(form["pin"], "***")
        self.assertEqual(form["passwort_neu"], "***")
        self.assertEqual(form["token_abc"], "***")
        self.assertEqual(form["notiz"], "hallo")
        self.assertEqual(form["menge"], ["1", "2"])
        self.assertNotIn("1234", e.formdaten)

    def test_json_antwort(self):
        r = self.client.get(TEST_PFAD_GET, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 500)
        daten = r.json()
        self.assertFalse(daten["ok"])
        self.assertTrue(daten["fehler_nr"].startswith("F-"))
        self.assertIn(daten["fehler_nr"], daten["meldung"])
        self.assertIsNotNone(self._eintrag(daten["fehler_nr"]))

    def test_datenbank_gesperrt_sondertext(self):
        from sqlalchemy.exc import OperationalError
        self.assertTrue(fehlerprotokoll.ist_datenbank_gesperrt(
            OperationalError("x", {}, Exception("database is locked"))))
        self.assertFalse(fehlerprotokoll.ist_datenbank_gesperrt(RuntimeError("locked")))
        r = self.client.get(TEST_PFAD_GET + "-gesperrt")
        self.assertEqual(r.status_code, 500)
        self.assertIn("kurz belegt", r.text)
        nr = self._nr_aus(r.text)
        e = self._eintrag(nr)
        self.assertIsNotNone(e)
        self.assertEqual(e.fehlertyp, "OperationalError")
        # aufräumen (Traceback enthält keine Test-Marke)
        self.s.delete(e)
        self.s.commit()

    def test_fehlerseite_ohne_anmeldung(self):
        """render() muss auch ohne Benutzer funktionieren (OFFENE_PFADE-Fehler)."""
        anonym = TestClient(app, raise_server_exceptions=False)
        r = anonym.get(TEST_PFAD_GET, follow_redirects=False)
        # nicht angemeldet → Middleware leitet zum Login um, kein Fehler
        self.assertEqual(r.status_code, 303)
        # direkt den Handler prüfen: Request ohne state.benutzer
        from app.main import unbehandelte_ausnahme
        scope = {"type": "http", "method": "GET", "path": "/x", "query_string": b"",
                 "headers": [], "scheme": "http", "server": ("test", 80),
                 "app": app, "router": app.router}
        antwort = unbehandelte_ausnahme(Request(scope), RuntimeError(TEST_MARKE + " anonym"))
        self.assertEqual(antwort.status_code, 500)
        self.assertIn(b"Fehler-Nr.", antwort.body)

    def test_client_disconnect_ohne_protokoll(self):
        from starlette.requests import ClientDisconnect
        from app.main import unbehandelte_ausnahme
        vorher = self.s.query(Fehlerprotokoll).count()
        scope = {"type": "http", "method": "POST", "path": "/x", "query_string": b"",
                 "headers": [], "app": app}
        antwort = unbehandelte_ausnahme(Request(scope), ClientDisconnect())
        self.assertEqual(antwort.status_code, 400)
        self.s.expire_all()
        self.assertEqual(self.s.query(Fehlerprotokoll).count(), vorher)


class Ansicht(Basis):
    def test_liste_erledigt_leeren(self):
        r = self.client.get(TEST_PFAD_GET)
        nr = self._nr_aus(r.text)
        e = self._eintrag(nr)
        self.assertIsNotNone(e)

        r = self.client.get("/parametrierung/fehlerprotokoll")
        self.assertEqual(r.status_code, 200)
        self.assertIn(nr, r.text)
        self.assertIn("RuntimeError", r.text)
        self.assertIn("fehler.log", r.text)
        self.assertIn("Als erledigt markieren", r.text)
        # Filter: Pfad-Teilstring + nur offene
        r = self.client.get("/parametrierung/fehlerprotokoll?offen=1&pfad=v22-test")
        self.assertIn(nr, r.text)
        r = self.client.get("/parametrierung/fehlerprotokoll?pfad=gibt-es-nicht-xyz")
        self.assertNotIn(nr, r.text)

        r = self.client.post(f"/parametrierung/fehlerprotokoll/{e.id}/erledigt",
                             data={"offen": "1", "pfad": "v22"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("offen=1", r.headers["location"])
        self.assertTrue(self._eintrag(nr).erledigt)
        r = self.client.get("/parametrierung/fehlerprotokoll?offen=1")
        self.assertNotIn(nr, r.text)

        r = self.client.post("/parametrierung/fehlerprotokoll/leeren", data={},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIsNone(self._eintrag(nr))

    def test_uebersicht_link(self):
        r = self.client.get("/parametrierung")
        self.assertEqual(r.status_code, 200)
        self.assertIn('href="/parametrierung/fehlerprotokoll"', r.text)


class Helfer(unittest.TestCase):
    def test_fehler_nr_format(self):
        import re
        nr = fehlerprotokoll.fehler_nr_erzeugen()
        self.assertRegex(nr, r"^F-\d{8}-\d{6}-[0-9a-f]{4}$")

    def test_formdaten_parsen_maskiert(self):
        form = fehlerprotokoll.formdaten_parsen(b"pin=1234&Passwort=x&api_token=y&a=1&a=2&leer=")
        self.assertEqual(form, {"pin": "***", "Passwort": "***", "api_token": "***",
                                "a": ["1", "2"], "leer": ""})

    def test_angebot_id_aus_pfad(self):
        self.assertEqual(fehlerprotokoll.angebot_id_aus_pfad("/angebote/42/positionen"), 42)
        self.assertEqual(fehlerprotokoll.angebot_id_aus_pfad("/angebote/42"), 42)
        self.assertIsNone(fehlerprotokoll.angebot_id_aus_pfad("/angebote"))
        self.assertIsNone(fehlerprotokoll.angebot_id_aus_pfad("/kunden/42"))


if __name__ == "__main__":
    unittest.main()
