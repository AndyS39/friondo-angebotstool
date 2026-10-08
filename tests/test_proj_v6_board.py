# v28 (PLAN_PROJ_V6 Phase 134): Board – volle Breite (Marker-Klasse pj-voll),
# Dummy-Scrollbalken, Dialog „Phase ändern“ am Board, POST …/phase-drop mit JSON,
# GET …/waechter?ziel= (begruendung_pflicht je Modus). Browser-Kontrollwerte
# (Board-Höhe, scrollLeft synchron, Karte wandert) prüft das Chrome-headless-Skript
# diagnose/v28_patches/p1_screenshots.py (Playwright ist nicht installiert).
# Nachtrag 08.10.2026 (Antwort Andreas): volle Breite für ALLE main.breit-Seiten
# (style.css), Board-Mindesthöhe 480 px nur ab 900 px Viewport-Höhe, sonst 320 px –
# Kontrollwerte (kein Seiten-Scroll 1366×768, kein waagerechter Scroll Portal/Lead)
# misst diagnose/v28_patches/pb_kontrolle.py.
import unittest
import warnings

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import projektierung as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import Gewerk, ProjektVerlauf
from tests.test_proj_v6_waechter import Basis as _Basis, parameter

TEST_EMAIL = "v28p1-waechter@test.local"


class Board(_Basis):
    def test_seiten_volle_breite_und_board_bausteine(self):
        g = self.gewerk_neu()
        for pfad in ("/projektierung", "/projektierung/liste", "/projektierung/kalender",
                     "/projektierung/termine", "/projektierung/meine-aufgaben",
                     f"/projektierung/projekt/{g.projekt_id}"):
            r = self.client.get(pfad)
            self.assertEqual(r.status_code, 200, pfad)
            self.assertIn('main class="breit pj-voll"', r.text, pfad)
        r = self.client.get("/projektierung")
        self.assertIn('id="pj-hscroll"', r.text)
        self.assertIn('id="dlg-phase-board"', r.text)
        self.assertIn('id="dlg-termin-board"', r.text)
        self.assertIn("data-pj-phase-fetch", r.text)
        self.assertIn("öffnet den Dialog", r.text)
        self.assertIn("blockieren im Modus „warnen“ nicht", r.text)
        self.assertIn('data-phase="auftragseingang"', r.text)        # Kacheln mit Phase
        self.assertIn(f'data-gewerk="{g.id}"', r.text)              # Chip je Gewerk
        self.assertNotIn('id="teamdialog"', r.text)                  # alter Dialog weg
        # Angebotstool-/Lead-Seiten tragen main.breit ohne den Marker pj-voll
        # (seit dem Nachtrag 08.10.2026 ebenfalls volle Breite über style.css)
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("pj-voll", r.text)

    def test_phase_drop_json_warnen_und_sperren(self):
        g, offen = self.planung_mit_drei_offenen()
        r = self.client.get(f"/projektierung/gewerk/{g.id}/waechter?ziel=montagevorbereitung")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len([p for p in r.json()["offen"] if p["aufgabe_id"]]), 3)
        self.assertFalse(r.json()["begruendung_pflicht"])
        r = self.client.post(f"/projektierung/gewerk/{g.id}/phase-drop",
                             data={"phase": "montagevorbereitung", "begruendung": ""},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200)
        daten = r.json()
        self.assertTrue(daten["ok"])
        self.assertEqual(daten["phase"], "montagevorbereitung")
        self.assertIn("projekt_status", daten)
        self.s.expire_all()
        self.assertEqual(self.s.get(Gewerk, g.id).phase, "montagevorbereitung")
        self.assertTrue(self.s.query(ProjektVerlauf).filter(
            ProjektVerlauf.gewerk_id == g.id,
            ProjektVerlauf.text.like("%mit offenen Punkten: Planungs-Pakete: 3 von%")).count())
        # zurück nach planung ohne Begründung → 400
        r = self.client.post(f"/projektierung/gewerk/{g.id}/phase-drop",
                             data={"phase": "planung"}, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])
        r = self.client.post(f"/projektierung/gewerk/{g.id}/phase-drop",
                             data={"phase": "planung", "begruendung": "zurück für Test"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200)
        # Modus sperren: Drop mit offenen Punkten ohne Begründung → 400 mit Wächter-Text
        parameter("waechter_modus", "sperren")
        r = self.client.get(f"/projektierung/gewerk/{g.id}/waechter?ziel=montage")
        self.assertTrue(r.json()["begruendung_pflicht"])
        r = self.client.post(f"/projektierung/gewerk/{g.id}/phase-drop",
                             data={"phase": "montagevorbereitung"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Wächter:", r.json()["meldung"])
        # klassischer POST (ohne Accept JSON) → Redirect aufs Board mit Meldung
        r = self.client.post(f"/projektierung/gewerk/{g.id}/phase-drop",
                             data={"phase": "montagevorbereitung"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/projektierung?meldung="))

    def test_auftragseingang_spalten_als_eine_phase(self):
        g = self.gewerk_neu()
        g.phase = "feinplanung_vot"
        self.s.commit()
        r = self.client.post(f"/projektierung/gewerk/{g.id}/phase-drop",
                             data={"phase": "auftragseingang_unterminiert",
                                   "begruendung": "zurück"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        self.assertEqual(self.s.get(Gewerk, g.id).phase, "auftragseingang")
        r = self.client.get(f"/projektierung/gewerk/{g.id}/waechter?ziel=auftragseingang_terminiert")
        self.assertEqual(r.json()["ziel"], "auftragseingang")


if __name__ == "__main__":
    unittest.main()
