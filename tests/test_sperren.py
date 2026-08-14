# Tests für die Bearbeitungssperre des Angebots-Editors.
import unittest
from unittest import mock

from app import sperren


class TestSperren(unittest.TestCase):
    def setUp(self):
        sperren._sperren.clear()

    def test_erster_bekommt_sperre_zweiter_liest_nur(self):
        self.assertIsNone(sperren.erwerben(1, 10, "Anna"))
        halter = sperren.erwerben(1, 20, "Bernd")
        self.assertEqual(halter, {"benutzer_id": 10, "name": "Anna"})
        self.assertEqual(sperren.gesperrt_fuer(1, 20)["name"], "Anna")
        self.assertIsNone(sperren.gesperrt_fuer(1, 10))   # Inhaber selbst frei

    def test_eigener_aufruf_verlaengert(self):
        sperren.erwerben(1, 10, "Anna")
        self.assertIsNone(sperren.erwerben(1, 10, "Anna"))   # eigene Sperre ok
        self.assertTrue(sperren.verlaengern(1, 10))
        self.assertFalse(sperren.verlaengern(1, 20))          # fremde nicht

    def test_freigeben_nur_eigene(self):
        sperren.erwerben(1, 10, "Anna")
        sperren.freigeben(1, 20)                              # fremde: wirkungslos
        self.assertIsNotNone(sperren.inhaber(1))
        sperren.freigeben(1, 10)
        self.assertIsNone(sperren.inhaber(1))
        self.assertIsNone(sperren.erwerben(1, 20, "Bernd"))   # jetzt frei

    def test_ablauf_nach_ttl(self):
        sperren.erwerben(1, 10, "Anna")
        with mock.patch("app.sperren.time.monotonic",
                        return_value=sperren._sperren[1]["zeit"]
                        + sperren.TTL_SEKUNDEN + 1):
            self.assertIsNone(sperren.inhaber(1))             # abgelaufen
            self.assertFalse(sperren.verlaengern(1, 10))      # zu spät
            self.assertIsNone(sperren.erwerben(1, 20, "Bernd"))  # übernehmbar
        self.assertEqual(sperren.inhaber(1)["benutzer_id"], 20)

    def test_verschiedene_angebote_unabhaengig(self):
        sperren.erwerben(1, 10, "Anna")
        self.assertIsNone(sperren.erwerben(2, 20, "Bernd"))
        self.assertEqual(sperren.inhaber(1)["benutzer_id"], 10)
        self.assertEqual(sperren.inhaber(2)["benutzer_id"], 20)


if __name__ == "__main__":
    unittest.main()
