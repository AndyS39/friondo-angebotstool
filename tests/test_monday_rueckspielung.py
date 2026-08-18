# monday-Rückspielung (Phase 32) mit gemockter API: Status-/Gruppen-Modus,
# Deal-Wert brutto/netto, übersprungen ohne Lead/aus, Fehler + Protokoll.
import datetime
import json
import unittest
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import monday_rueckspielung, monday_sync
from app.db import Base
from app.models import (Angebot, AngebotsPosition, Erfassung, Kunde, Lead,
                        MondayQuelle)


class TestRueckspielung(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = sessionmaker(bind=engine)()
        kunde = Kunde(nachname="Beispiel"); self.s.add(kunde); self.s.commit()
        self.angebot = Angebot(nummer="AN-C-260050", kunde_id=kunde.id, status="Versendet",
                               datum=datetime.datetime(2026, 8, 1), rabatt_cent=50000)
        self.angebot.positionen = [AngebotsPosition(sort=1, bezeichnung="x", menge=1,
                                                    e_preis_cent=1000000)]  # 10.000 netto
        self.s.add(self.angebot); self.s.commit()
        erf = Erfassung(kunde_id=kunde.id, benutzer_id=1, angebot_id=self.angebot.id,
                        antworten_json="{}")
        self.s.add(erf); self.s.commit()
        self.lead = Lead(monday_item_id="4711", board_id="5080725439",
                         board_name="Deals", erfassung_id=erf.id)
        self.quelle = MondayQuelle(board_id="5080725439", board_name="Deals",
                                   rueck_modus="status", rueck_status_spalte="deal_stage",
                                   rueck_status_wert="Angebot versendet",
                                   rueck_wert_spalte="numbers_1", rueck_wert_basis="brutto")
        self.s.add_all([self.lead, self.quelle]); self.s.commit()
        self.aufrufe = []

    def _fake_api(self, query, variablen=None):
        self.aufrufe.append((query, variablen))
        return {}

    def test_status_und_deal_wert_brutto(self):
        with mock.patch.object(monday_sync, "_api", side_effect=self._fake_api):
            ok = monday_rueckspielung.uebertragen(self.s, self.angebot)
        self.assertTrue(ok)
        self.assertEqual(self.angebot.monday_rueck_status, "ok")
        self.assertEqual(len(self.aufrufe), 1)
        query, var = self.aufrufe[0]
        self.assertIn("change_multiple_column_values", query)
        self.assertEqual((var["board"], var["item"]), ("5080725439", "4711"))
        werte = json.loads(var["werte"])
        self.assertEqual(werte["deal_stage"], {"label": "Angebot versendet"})
        # 10.000 netto + 19 % = 11.900 − 500 Rabatt = 11.400,00 Endbetrag
        self.assertEqual(werte["numbers_1"], "11400.00")
        self.assertIn("OK", self.angebot.monday_rueck_protokoll)
        self.assertIn("Deal-Wert 11400.00 (brutto)", self.angebot.monday_rueck_protokoll)

    def test_deal_wert_netto(self):
        self.quelle.rueck_wert_basis = "netto"; self.s.commit()
        with mock.patch.object(monday_sync, "_api", side_effect=self._fake_api):
            monday_rueckspielung.uebertragen(self.s, self.angebot)
        self.assertEqual(json.loads(self.aufrufe[0][1]["werte"])["numbers_1"], "10000.00")

    def test_gruppen_modus(self):
        self.quelle.rueck_modus = "gruppe"; self.quelle.rueck_gruppe_id = "group_xyz"
        self.s.commit()
        with mock.patch.object(monday_sync, "_api", side_effect=self._fake_api):
            monday_rueckspielung.uebertragen(self.s, self.angebot)
        # erst Deal-Wert (Spaltenwerte), dann Verschieben
        self.assertEqual(len(self.aufrufe), 2)
        self.assertIn("change_multiple_column_values", self.aufrufe[0][0])
        self.assertNotIn("deal_stage", json.loads(self.aufrufe[0][1]["werte"]))
        self.assertIn("move_item_to_group", self.aufrufe[1][0])
        self.assertEqual(self.aufrufe[1][1]["gruppe"], "group_xyz")
        self.assertEqual(self.angebot.monday_rueck_status, "ok")

    def test_uebersprungen_wenn_aus(self):
        self.quelle.rueck_modus = "aus"; self.s.commit()
        with mock.patch.object(monday_sync, "_api", side_effect=self._fake_api):
            ok = monday_rueckspielung.uebertragen(self.s, self.angebot)
        self.assertTrue(ok)
        self.assertEqual(self.aufrufe, [])
        self.assertEqual(self.angebot.monday_rueck_status, "uebersprungen")
        self.assertIn("nicht aktiviert", self.angebot.monday_rueck_protokoll)

    def test_uebersprungen_ohne_lead(self):
        self.s.delete(self.lead); self.s.commit()
        with mock.patch.object(monday_sync, "_api", side_effect=self._fake_api):
            ok = monday_rueckspielung.uebertragen(self.s, self.angebot)
        self.assertTrue(ok)
        self.assertEqual(self.angebot.monday_rueck_status, "uebersprungen")
        self.assertIn("kein monday-Lead", self.angebot.monday_rueck_protokoll)

    def test_fehler_blockiert_nicht_und_protokolliert(self):
        def kaputt(query, variablen=None):
            raise RuntimeError("Kein monday-API-Token")
        with mock.patch.object(monday_sync, "_api", side_effect=kaputt):
            ok = monday_rueckspielung.uebertragen(self.s, self.angebot)
        self.assertFalse(ok)
        self.assertEqual(self.angebot.monday_rueck_status, "fehler")
        self.assertIn("FEHLER: Kein monday-API-Token", self.angebot.monday_rueck_protokoll)
        # bei_versand darf nie werfen
        with mock.patch.object(monday_sync, "_api", side_effect=kaputt):
            monday_rueckspielung.bei_versand(self.s, self.angebot)
        # Retry mit funktionierender API → ok, Protokoll hat mehrere Zeilen
        with mock.patch.object(monday_sync, "_api", side_effect=self._fake_api):
            self.assertTrue(monday_rueckspielung.uebertragen(self.s, self.angebot))
        self.assertEqual(self.angebot.monday_rueck_status, "ok")
        self.assertEqual(len(self.angebot.monday_rueck_protokoll.splitlines()), 3)


if __name__ == "__main__":
    unittest.main()
