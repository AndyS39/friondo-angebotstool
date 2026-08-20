# Leads ausblenden (v5-Nachtrag): der monday-Sync darf das Kennzeichen nicht
# zurücksetzen – ein ausgeblendeter Lead taucht nach dem Sync nicht erneut auf.
import unittest
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import monday_sync
from app.db import Base
from app.models import Lead, MondayQuelle


class TestLeadAusblenden(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = sessionmaker(bind=engine)()
        self.quelle = MondayQuelle(board_id="B1", board_name="Deals", gruppen_titel="Terminiert")
        self.s.add(self.quelle)
        self.s.add(Lead(monday_item_id="4711", board_id="B1", vorname="Erika", nachname="Beispiel",
                        plz="47441", ausgeblendet=True, ausgeblendet_grund="Kunde hat abgesagt"))
        self.s.commit()

    def test_sync_laesst_ausgeblendet_stehen(self):
        items = [{"id": "4711", "name": "Erika Beispiel",
                  "column_values": [{"id": "vot", "text": "2026-09-01 10:00"},
                                    {"id": "ort", "text": "47441 Moers"}]}]
        with mock.patch.object(monday_sync, "_items_der_gruppe", return_value=("Deals", items)), \
                mock.patch.object(monday_sync, "_mapping", return_value={"vot_datum": "vot", "ort": "ort"}):
            anzahl = monday_sync._quelle_syncen(self.s, self.quelle, {})
        self.s.commit()
        self.assertEqual(anzahl, 1)
        lead = self.s.query(Lead).filter_by(monday_item_id="4711").one()
        self.assertTrue(lead.ausgeblendet)                     # bleibt ausgeblendet
        self.assertEqual(lead.ausgeblendet_grund, "Kunde hat abgesagt")
        self.assertEqual(lead.ort, "Moers")                     # Stammdaten trotzdem aktualisiert
        self.assertIsNotNone(lead.vot_datum)

    def test_sync_respektiert_manuelle_zuordnung(self):
        # Innendienst hat den Vertriebler im Tool geändert (benutzer_manuell):
        # der Sync darf ihn nicht mehr aus der monday-Personen-Spalte setzen
        lead = self.s.query(Lead).filter_by(monday_item_id="4711").one()
        lead.benutzer_id = 99
        lead.benutzer_manuell = True
        self.quelle.fester_benutzer_id = 5   # würde sonst greifen
        self.s.commit()
        items = [{"id": "4711", "name": "Erika Beispiel",
                  "column_values": [{"id": "p", "text": "Rene Golaschewski"}]}]
        with mock.patch.object(monday_sync, "_items_der_gruppe", return_value=("Deals", items)),                 mock.patch.object(monday_sync, "_mapping", return_value={"verantwortlicher": "p"}):
            monday_sync._quelle_syncen(self.s, self.quelle, {})
        self.s.commit()
        lead = self.s.query(Lead).filter_by(monday_item_id="4711").one()
        self.assertEqual(lead.benutzer_id, 99)          # manuelle Zuordnung bleibt
        self.assertEqual(lead.monday_person, "Rene Golaschewski")   # Anzeige aktuell

    def test_offene_leads_ohne_ausgeblendete(self):
        from app.routers.leads import offene_leads
        import datetime
        self.s.add(Lead(monday_item_id="4712", board_id="B1", vorname="Max", nachname="Offen",
                        vot_datum=datetime.datetime(2026, 9, 2)))
        lead = self.s.query(Lead).filter_by(monday_item_id="4711").one()
        lead.vot_datum = datetime.datetime(2026, 9, 1)
        self.s.commit()
        self.assertEqual([l.nachname for l in offene_leads(self.s)], ["Offen"])
        self.assertEqual([l.nachname for l in offene_leads(self.s, ausgeblendet=True)], ["Beispiel"])


if __name__ == "__main__":
    unittest.main()
