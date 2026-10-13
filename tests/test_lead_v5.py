# v31/v32 (PLAN_LEAD_V5 / PLAN_V19): Fundament des Durchlaufs – Werktage und
# NRW-Feiertage (app/werktage.py), Sparten-Langformen (app/sparten.py),
# 5-Minuten-Rundung und Freischaltungs-Schalter (app/lead_v5.py), Abwesenheiten
# (app/abwesenheiten.py) und die Idempotenz der v31-Migrationen (zweiter Lauf ohne
# Änderungen). Die fachlichen Tests je Bereich liegen in test_lead_v5_*.py.
import unittest
from datetime import date, datetime, timedelta

from app import abwesenheiten, lead_v5, objekte, sparten, werktage
from app.db import SessionLocal
from app.models import Benutzer


class WerktageTests(unittest.TestCase):
    def test_ostern_und_feiertage_2026(self):
        self.assertEqual(werktage.ostersonntag(2026), date(2026, 4, 5))
        feiertage = werktage.feiertage_nrw(2026)
        for tag in (date(2026, 1, 1), date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 1),
                    date(2026, 5, 14), date(2026, 5, 25), date(2026, 6, 4), date(2026, 10, 3),
                    date(2026, 11, 1), date(2026, 12, 25), date(2026, 12, 26)):
            self.assertIn(tag, feiertage, tag)
            self.assertTrue(werktage.ist_feiertag(tag), tag)
        self.assertFalse(werktage.ist_feiertag(date(2026, 10, 13)))

    def test_werktag(self):
        self.assertTrue(werktage.ist_werktag(date(2026, 10, 13)))    # Dienstag
        self.assertFalse(werktage.ist_werktag(date(2026, 10, 10)))   # Samstag
        self.assertFalse(werktage.ist_werktag(date(2026, 10, 11)))   # Sonntag
        self.assertFalse(werktage.ist_werktag(date(2026, 10, 3)))    # Feiertag (Samstag)

    def test_plus_werktage_kontrollwerte(self):
        # PLAN_V19 Phase 162: Fr + 3 Werktage = Mi; der Plan nennt „Fr 10.10.2026“,
        # tatsächlich ist der 10.10.2026 ein Samstag (Rückfrage) – beide Fälle enden
        # am Mi 14.10.2026. Mi 30.09. + 3 = Mo 05.10. (Tag der Deutschen Einheit),
        # Do 17.12. + 3 = Di 22.12.
        self.assertEqual(werktage.plus_werktage(date(2026, 10, 9), 3), date(2026, 10, 14))
        self.assertEqual(werktage.plus_werktage(date(2026, 10, 10), 3), date(2026, 10, 14))
        self.assertEqual(werktage.plus_werktage(date(2026, 9, 30), 3), date(2026, 10, 5))
        self.assertEqual(werktage.plus_werktage(date(2026, 12, 17), 3), date(2026, 12, 22))
        self.assertEqual(werktage.plus_werktage(date(2026, 10, 9), 5), date(2026, 10, 16))
        self.assertEqual(werktage.plus_werktage(date(2026, 10, 13), 0), date(2026, 10, 13))

    def test_naechster_werktag(self):
        self.assertEqual(werktage.naechster_werktag(date(2026, 10, 10)), date(2026, 10, 12))
        self.assertEqual(werktage.naechster_werktag(date(2026, 10, 13)), date(2026, 10, 13))
        self.assertEqual(werktage.naechster_werktag(date(2026, 10, 3)), date(2026, 10, 5))


class SpartenTests(unittest.TestCase):
    def test_codes_und_langformen(self):
        self.assertEqual(sparten.SPARTEN, ("WP", "PV", "KL", "WB", "GW", "MS", "WA", "DMS"))
        self.assertEqual(sparten.codes("WP,PV"), ["WP", "PV"])
        self.assertEqual(sparten.codes(""), [])
        self.assertEqual(sparten.sparten_text("WP,PV"), "Wärmepumpe und Photovoltaik")
        self.assertEqual(sparten.sparten_text("WP"), "Wärmepumpe")
        self.assertEqual(sparten.sparten_text("WP,PV,KL"), "Wärmepumpe, Photovoltaik und Klimaanlage")
        self.assertEqual(sparten.sparten_text("WP,PV", form="kurz"), "WP und PV")

    def test_interesse_saetze(self):
        self.assertEqual(sparten.sparten_interesse("WP"), "Interesse an einer Wärmepumpe")
        self.assertEqual(sparten.sparten_interesse("PV,KL"),
                         "Interesse an Photovoltaik und einer Klimaanlage")
        self.assertEqual(sparten.sparten_interesse("GW"), "Interesse an einer gewerblichen Lösung")
        for code in ("MS", "WA", "DMS"):
            self.assertTrue(sparten.sparten_interesse(code).startswith("Interesse an"), code)

    def test_freitext_sparten(self):
        for code in ("WB", "GW", "MS", "WA", "DMS"):
            self.assertTrue(sparten.ist_freitext_sparte(code), code)
        for code in ("WP", "PV", "KL"):
            self.assertFalse(sparten.ist_freitext_sparte(code), code)


class LeadV5Tests(unittest.TestCase):
    def test_runden_5min(self):
        self.assertEqual(lead_v5.runden_5min(datetime(2026, 10, 13, 14, 7)),
                         datetime(2026, 10, 13, 14, 5))
        self.assertEqual(lead_v5.runden_5min(datetime(2026, 10, 13, 14, 8)),
                         datetime(2026, 10, 13, 14, 10))
        self.assertEqual(lead_v5.runden_5min(datetime(2026, 10, 13, 14, 0, 30)),
                         datetime(2026, 10, 13, 14, 0))
        self.assertEqual(lead_v5.runden_5min(datetime(2026, 10, 13, 23, 59)),
                         datetime(2026, 10, 14, 0, 0))

    def test_schalter_standard_aus(self):
        s = SessionLocal()
        try:
            self.assertIn("terminierung_aktiv", lead_v5.SCHALTER)
            self.assertIn("mail_versand_aktiv", lead_v5.SCHALTER)
            self.assertIsInstance(lead_v5.schalter(s, "terminierung_aktiv"), bool)
            self.assertIsInstance(lead_v5.terminierung_aktiv(s), bool)
            self.assertIsInstance(lead_v5.mail_versand_aktiv(s), bool)
            self.assertFalse(lead_v5.schalter(s, "gibt_es_nicht"))
        finally:
            s.close()

    def test_migrationen_zweiter_lauf_ohne_aenderungen(self):
        s = SessionLocal()
        try:
            objekte.migration_v31_objekte(s)
            lead_v5.migration_v31_lead(s)
            s.commit()
            self.assertFalse(objekte.migration_v31_objekte(s))
            self.assertFalse(lead_v5.migration_v31_lead(s))
            s.commit()
        finally:
            s.close()


class AbwesenheitenTests(unittest.TestCase):
    PRAEFIX = "V5ABW"

    def setUp(self):
        self.s = SessionLocal()
        self.s.query(Benutzer).filter(Benutzer.name == f"{self.PRAEFIX} Vertriebler").delete()
        b = Benutzer(name=f"{self.PRAEFIX} Vertriebler", rolle="aussendienst", aktiv=True)
        self.s.add(b)
        self.s.commit()
        self.benutzer_id = b.id

    def tearDown(self):
        try:
            from app.models import BenutzerAbwesenheit
            self.s.query(BenutzerAbwesenheit).filter(
                BenutzerAbwesenheit.benutzer_id == self.benutzer_id).delete()
            self.s.query(Benutzer).filter(Benutzer.id == self.benutzer_id).delete()
            self.s.commit()
        finally:
            self.s.close()

    def test_anlegen_pruefen_beenden(self):
        heute = date.today()
        ok, meldung, eintrag = abwesenheiten.anlegen(
            self.s, self.benutzer_id, "krankheit", heute, heute + timedelta(days=3), "Test")
        self.assertTrue(ok, meldung)
        self.s.commit()
        self.assertTrue(abwesenheiten.ist_abwesend(self.s, self.benutzer_id, heute + timedelta(days=1)))
        self.assertFalse(abwesenheiten.ist_abwesend(self.s, self.benutzer_id, heute + timedelta(days=10)))
        self.assertEqual(abwesenheiten.hinweis_text(eintrag, "Max Muster"), "Krankheit: Max Muster")
        aktive = abwesenheiten.aktive(self.s, heute + timedelta(days=1))
        self.assertTrue(any(e.benutzer_id == self.benutzer_id for e in aktive))
        abwesenheiten.beenden(self.s, eintrag.id, heute)
        self.s.commit()
        self.assertFalse(abwesenheiten.ist_abwesend(self.s, self.benutzer_id, heute + timedelta(days=1)))
        ok, meldung, _ = abwesenheiten.anlegen(self.s, self.benutzer_id, "falsch", heute, None)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
