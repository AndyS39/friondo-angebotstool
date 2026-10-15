# v34 (PLAN_V21 Phase 180, Entscheidung R7): USt-Rundung wie TAIFUN – Angebot.summen() rundet
# die Umsatzsteuer kaufmännisch (ROUND_HALF_UP) statt abzuschneiden (seit Phase 26 int()).
# Kontrollwerte: KL-Fall A 6.518,66 € netto → USt 1.238,55 € / Gesamt 7.757,21 € (bis v33
# 1.238,54 / 7.757,20); KL-Fall B 5.495,00 → 1.044,05 (exakt, unverändert); WP-Kontrollwert
# 30.245,43 → 5.746,63 (unverändert); 0 % USt → 0. Rabatt-/KfW-Logik, rabatt_netto und
# netto_nach_rabatt (v33 Phase 172) unverändert. Editor, Liste, PDF, Mail-Platzhalter und
# monday-Deal-Wert nutzen ausschließlich summen() – geprüft am Fall-A-Betrag.
import unittest
import warnings

warnings.filterwarnings("ignore")

from app import mail_vorlagen, monday_rueckspielung, pdf_export
from app.models import Angebot, AngebotsPosition
from tests.v34_e_basis import Basis, pdf_text


def _angebot(netto_cent: int, ust_satz: float = 19.0, **felder) -> Angebot:
    """Transientes Angebot (ohne DB) mit einer Position zum Nettobetrag."""
    a = Angebot(nummer="AN-C-TEST", kunde_id=0, ust_satz=ust_satz, **felder)
    a.positionen.append(AngebotsPosition(sort=1, pos_nr="T1", bezeichnung="Test",
                                         menge=1.0, e_preis_cent=netto_cent, ek_cent=0))
    return a


class Rundung(unittest.TestCase):
    def test_fall_a_kaufmaennisch(self):
        su = _angebot(651866).summen()
        self.assertEqual((su["netto"], su["ust"], su["brutto"], su["endbetrag"]),
                         (651866, 123855, 775721, 775721))

    def test_fall_b_exakt_unveraendert(self):
        su = _angebot(549500).summen()
        self.assertEqual((su["ust"], su["brutto"]), (104405, 653905))

    def test_wp_kontrollwert_unveraendert(self):
        su = _angebot(3024543).summen()
        self.assertEqual((su["ust"], su["brutto"]), (574663, 3599206))   # 5.746,63 / 35.992,06

    def test_halbe_cent_werden_aufgerundet(self):
        # 1,50 € × 19 % = 0,285 € → 29 Cent (HALF_UP); Abschneiden 28, HALF_EVEN 28
        self.assertEqual(_angebot(150).summen()["ust"], 29)
        # 0,29 € × 19 % = 0,0551 € → 6 Cent (Abschneiden: 5)
        self.assertEqual(_angebot(29).summen()["ust"], 6)
        # 0,13 € × 19 % = 0,0247 € → 2 Cent (unter der Hälfte: abrunden)
        self.assertEqual(_angebot(13).summen()["ust"], 2)

    def test_null_prozent(self):
        su = _angebot(651866, ust_satz=0.0).summen()
        self.assertEqual((su["ust"], su["brutto"]), (0, 651866))

    def test_rabatt_logik_unveraendert(self):
        a = _angebot(2_000_000, rabatt_prozent=5.0)
        su = a.summen()
        self.assertEqual((su["ust"], su["brutto"]), (380_000, 2_380_000))
        self.assertEqual(su["rabatt"], 119_000)                     # 5 % vom Gesamt-Betrag
        self.assertEqual(su["endbetrag"], 2_261_000)
        self.assertEqual(su["rabatt_netto"], 100_000)               # 119.000 ÷ 1,19
        self.assertEqual(su["netto_nach_rabatt"], 1_900_000)
        b = _angebot(2_000_000, ust_satz=0.0, rabatt_prozent=5.0)
        self.assertEqual((b.summen()["rabatt"], b.summen()["endbetrag"]), (100_000, 1_900_000))

    def test_extern_unveraendert(self):
        a = Angebot(nummer="AN-C-EXT", kunde_id=0, extern=True, extern_endbetrag_cent=775721)
        self.assertEqual(a.summen()["endbetrag"], 775721)


class Darstellung(Basis):
    EMAIL = "v34e-ust@test.local"
    NACHNAME = "V34E Ust"
    AD_NAME = "V34E Ust-AD"

    def _fall_a(self, status="Entwurf"):
        return self.angebot("KL", [dict(sort=1, block_nr=3, gruppe="Klimaanlage Bosch",
                                        pos_nr="KL038", bezeichnung="Multisplit-Außeneinheit",
                                        beschreibung="Fall A gesamt", menge=1.0, einheit="Stück",
                                        e_preis_cent=651866, ek_cent=400_000)], status)

    def test_editor_pdf_liste(self):
        a = self._fall_a()
        html = self.client.get(f"/angebote/{a.id}").text
        self.assertIn("1.238,55 €", html)
        self.assertIn("7.757,21 €", html)
        self.assertNotIn("1.238,54", html)
        text = pdf_text(pdf_export.pdf_fuer_angebot(self.s, a))
        self.assertIn("1.238,55", text)
        self.assertIn("7.757,21", text)
        self.assertNotIn("7.757,20", text)
        liste = self.client.get(f"/angebote?q={self.NACHNAME.replace(' ', '+')}").text
        self.assertIn("7.757,21 €", liste)

    def test_mail_platzhalter_und_monday(self):
        a = self._fall_a()
        werte = mail_vorlagen.werte_fuer_angebot(self.s, a, self.kunde)
        self.assertEqual(werte["endbetrag"], "7.757,21 €")
        self.assertEqual(monday_rueckspielung._betrag(a, "brutto"), "7757.21")
        self.assertEqual(monday_rueckspielung._betrag(a, "netto"), "6518.66")


if __name__ == "__main__":
    unittest.main()
