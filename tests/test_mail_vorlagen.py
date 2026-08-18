# Tests für E-Mail-Vorlagen (Phase 30): Platzhalter, Vorlage je AD, Standard.
import datetime
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import mail_vorlagen
from app.db import Base
from app.models import Angebot, AngebotsPosition, Benutzer, Erfassung, Kunde


class TestMailVorlagen(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = sessionmaker(bind=engine)()
        self.kunde = Kunde(anrede="Frau", vorname="Erika", nachname="Beispiel")
        self.ad = Benutzer(name="Rene Golaschewski", rolle="aussendienst",
                           email="rene@friondo.de")
        self.s.add_all([self.kunde, self.ad]); self.s.commit()
        self.angebot = Angebot(nummer="AN-C-260042", kunde_id=self.kunde.id,
                               datum=datetime.datetime(2026, 8, 1))
        self.angebot.positionen = [AngebotsPosition(sort=1, bezeichnung="x",
                                                    menge=1, e_preis_cent=1000000)]
        self.s.add(self.angebot); self.s.commit()
        self.s.add(Erfassung(kunde_id=self.kunde.id, benutzer_id=self.ad.id,
                             angebot_id=self.angebot.id, antworten_json="{}"))
        self.s.commit()

    def test_platzhalter_werden_ersetzt(self):
        werte = mail_vorlagen.werte_fuer_angebot(self.s, self.angebot, self.kunde, "Anna ID")
        self.assertEqual(werte["anrede"], "Sehr geehrte Frau Beispiel,")
        self.assertEqual(werte["angebotsnummer"], "AN-C-260042")
        self.assertEqual(werte["endbetrag"], "11.900,00 €")      # 10.000 netto + 19 %
        self.assertEqual(werte["gueltig_bis"], "31.08.2026")
        self.assertEqual(werte["vertriebler"], "Rene Golaschewski")
        self.assertEqual(werte["absender"], "Anna ID")
        text = mail_vorlagen.einsetzen("Hallo {vorname} {nachname}, {angebotsnummer} von {vertriebler}", werte)
        self.assertEqual(text, "Hallo Erika Beispiel, AN-C-260042 von Rene Golaschewski")

    def test_unbekannte_platzhalter_bleiben_stehen(self):
        werte = mail_vorlagen.werte_fuer_angebot(self.s, self.angebot, self.kunde)
        self.assertEqual(mail_vorlagen.einsetzen("{unsinn} {vorname}", werte), "{unsinn} Erika")
        self.assertEqual(mail_vorlagen.unbekannte_platzhalter("{unsinn} {vorname} {x_y}"),
                         ["{unsinn}", "{x_y}"])

    def test_standard_ohne_eigene_vorlage(self):
        betreff, text, quelle = mail_vorlagen.mail_fuer_angebot(self.s, self.angebot, self.kunde)
        self.assertEqual(quelle, "Standard-Vorlage")
        self.assertIn("AN-C-260042", betreff)
        self.assertIn("Sehr geehrte Frau Beispiel,", text)
        self.assertNotIn("{", text)   # alle Platzhalter ersetzt

    def test_vorlage_des_ad_greift(self):
        mail_vorlagen.vorlage_speichern(self.s, self.ad.id, "Angebot {angebotsnummer} – Rene",
                                        "Moin {vorname},\n{vertriebler}")
        self.s.commit()
        betreff, text, quelle = mail_vorlagen.mail_fuer_angebot(self.s, self.angebot, self.kunde)
        self.assertEqual(quelle, "Vorlage Rene Golaschewski")
        self.assertEqual(betreff, "Angebot AN-C-260042 – Rene")
        self.assertEqual(text, "Moin Erika,\nRene Golaschewski")
        # entfernen → Standard
        mail_vorlagen.vorlage_speichern(self.s, self.ad.id, "", "")
        self.s.commit()
        self.assertEqual(mail_vorlagen.mail_fuer_angebot(self.s, self.angebot, self.kunde)[2],
                         "Standard-Vorlage")

    def test_standard_vorlage_ueberschreibbar(self):
        mail_vorlagen.vorlage_speichern(self.s, None, "Neu {angebotsnummer}", "Text {absender}")
        self.s.commit()
        betreff, text, quelle = mail_vorlagen.mail_fuer_angebot(self.s, self.angebot, self.kunde, "Ida")
        self.assertEqual((betreff, text, quelle), ("Neu AN-C-260042", "Text Ida", "Standard-Vorlage"))


if __name__ == "__main__":
    unittest.main()
