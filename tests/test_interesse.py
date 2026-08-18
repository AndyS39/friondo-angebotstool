# Interesse (Phase 33): monday-Labels -> Codes, kanonische Reihenfolge, Filter.
import unittest

from app import monday_sync
from app.models import interesse_liste, interesse_text


class TestInteresse(unittest.TestCase):
    def test_monday_labels_zu_codes(self):
        self.assertEqual(monday_sync.interesse_aus_text("Klimaanlage, WP, HEMS"), "WP,KL")
        self.assertEqual(monday_sync.interesse_aus_text("Wärmepumpe"), "WP")
        self.assertEqual(monday_sync.interesse_aus_text("PV, Wallbox, WP MFH"), "WP,PV,WB")
        self.assertEqual(monday_sync.interesse_aus_text("Gewerbe, FBH"), "")
        self.assertEqual(monday_sync.interesse_aus_text(""), "")

    def test_kanonische_reihenfolge_und_dedup(self):
        self.assertEqual(interesse_liste("wb,pv,pv, wp"), ["WP", "PV", "WB"])
        self.assertEqual(interesse_text(["KL", "WP", "unsinn"]), "WP,KL")
        self.assertEqual(interesse_liste(""), [])


if __name__ == "__main__":
    unittest.main()
