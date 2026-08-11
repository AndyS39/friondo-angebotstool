# Testfälle KfW-Berechnung (Phase 6) – Erwartungswerte exakt nach der Referenz
# foerderrechner-website.html durchgerechnet. Start: venv\Scripts\python -m unittest discover -s tests
import unittest
from datetime import date

from app.kfw import (KfwEingaben, berechnen, eingaben_aus_antworten,
                     gueltigkeits_warnung, parameter_lesen)
from app.logik import logik_einlesen


def _parameter():
    logik, _ = logik_einlesen()
    p, warnungen = parameter_lesen(logik)
    assert not warnungen, f"KfW-Parameter unvollständig: {warnungen}"
    return p


P = _parameter()


class TestParameter(unittest.TestCase):
    def test_parameter_aus_excel(self):
        self.assertEqual(P.grund_prozent, 30)
        self.assertEqual(P.klima_prozent, 16)
        self.assertEqual(P.einkommens_stufen, [(40, 30000), (30, 40000), (10, 50000)])
        self.assertEqual(P.kind_freibetrag_eur, 10000)
        self.assertEqual((P.deckel_prozent, P.deckel_erhoeht_prozent), (70, 80))
        self.assertEqual(P.efh_max_eur, 28000)
        self.assertEqual((P.mfh_basis_eur, P.mfh_je_we_2_6_eur, P.mfh_ab_7_eur),
                         (28000, 15000, 8000))
        self.assertEqual(P.gw_stufen, [(197, 150, 400), (118, 400, 1000), (79, 1000, None)])
        self.assertEqual(P.gueltig_bis, date(2027, 1, 31))
        self.assertIn("KfW 458", P.programm_wohn)
        self.assertIn("KfW 522", P.programm_gewerbe)

    def test_gueltigkeitswarnung(self):
        self.assertIsNone(gueltigkeits_warnung(P, date(2026, 8, 8)))
        self.assertIsNotNone(gueltigkeits_warnung(P, date(2027, 2, 1)))


class TestEfh(unittest.TestCase):
    def test_1_deckel_80_bei_einkommensbonus_40(self):
        # 30+16+40 = 86 % -> gedeckelt auf 80 %; Kosten über Höchstkosten
        e = KfwEingaben("efh", 3000000, klima_bonus=True, einkommen_eur=28000)
        r = berechnen(P, e)
        self.assertEqual(r.foerderfaehig_cent, 2800000)
        self.assertEqual(r.zuschuss_cent, 2240000)          # 28.000 × 80 %
        self.assertEqual(r.eigenanteil_cent, 760000)
        self.assertTrue(any("gedeckelt" in z[1] for z in r.zeilen))

    def test_2_nur_grundfoerderung(self):
        e = KfwEingaben("efh", 2500000)
        r = berechnen(P, e)
        self.assertEqual(r.zuschuss_cent, 750000)           # 25.000 × 30 %
        self.assertEqual(r.eigenanteil_cent, 1750000)

    def test_3_kind_freibetrag_und_deckel_70(self):
        # 45.000 - 10.000 = 35.000 -> +30 %; 30+16+30 = 76 -> Deckel 70
        e = KfwEingaben("efh", 2800000, klima_bonus=True, einkommen_eur=45000, kind=True)
        r = berechnen(P, e)
        self.assertEqual(r.zuschuss_cent, 1960000)          # 28.000 × 70 %
        self.assertIn("70 %", r.satz_text)

    def test_4_einkommensbonus_10(self):
        # 50.500 - 10.000 = 40.500 -> +10 %; Satz 56 %
        e = KfwEingaben("efh", 2000000, klima_bonus=True, einkommen_eur=50500, kind=True)
        r = berechnen(P, e)
        self.assertEqual(r.zuschuss_cent, 1120000)          # 20.000 × 56 %
        self.assertIn("56 %", r.satz_text)

    def test_5_cent_rundung(self):
        # 9.999,99 × 30 % = 2.999,997 -> 3.000,00 (kaufmännisch wie Referenz)
        e = KfwEingaben("efh", 999999)
        r = berechnen(P, e)
        self.assertEqual(r.zuschuss_cent, 300000)
        self.assertEqual(r.eigenanteil_cent, 699999)


class TestMfh(unittest.TestCase):
    def test_6_mfh_anteilige_boni(self):
        # 4 WE: Höchstkosten 73.000; Boni 56 %-Punkte -> begrenzt auf 50;
        # Grund 21.900 + (73.000/4) × 50 % = 9.125 -> 31.025; eff. Satz 42,5 %
        e = KfwEingaben("mfh", 8000000, wohneinheiten=4, mfh_selbst=True,
                        klima_bonus=True, einkommen_eur=30000)
        r = berechnen(P, e)
        self.assertEqual(r.hoechstkosten_cent, 7300000)
        self.assertEqual(r.zuschuss_cent, 3102500)
        self.assertEqual(r.eigenanteil_cent, 4897500)
        self.assertIn("42,5 %", r.satz_text)
        self.assertTrue(any("anteilig" in h for h in r.hinweise))

    def test_7_mfh_ohne_selbstnutzung(self):
        # 8 WE: 28.000 + 5×15.000 + 2×8.000 = 119.000; nur Grundförderung
        e = KfwEingaben("mfh", 12000000, wohneinheiten=8, mfh_selbst=False,
                        klima_bonus=True, einkommen_eur=25000)
        r = berechnen(P, e)
        self.assertEqual(r.hoechstkosten_cent, 11900000)
        self.assertEqual(r.zuschuss_cent, 3570000)
        self.assertIn("30 %", r.satz_text)

    def test_8_mfh_minimal(self):
        # 2 WE, selbst genutzt, keine Boni: 43.000 Höchstkosten, Grund 12.900
        e = KfwEingaben("mfh", 5000000, wohneinheiten=2, mfh_selbst=True)
        r = berechnen(P, e)
        self.assertEqual(r.hoechstkosten_cent, 4300000)
        self.assertEqual(r.zuschuss_cent, 1290000)


class TestGewerbe(unittest.TestCase):
    def test_9_gewerbe_klein(self):
        e = KfwEingaben("nwg", 3000000, flaeche_m2=120)
        r = berechnen(P, e)
        self.assertEqual(r.hoechstkosten_cent, 2800000)
        self.assertEqual(r.zuschuss_cent, 840000)
        self.assertIn("KfW 522", r.programm)

    def test_10_gewerbe_flaechenstaffel(self):
        # 500 m²: 28.000 + 197×250 + 118×100 = 89.050
        e = KfwEingaben("nwg", 10000000, flaeche_m2=500)
        r = berechnen(P, e)
        self.assertEqual(r.hoechstkosten_cent, 8905000)
        self.assertEqual(r.zuschuss_cent, 2671500)

    def test_11_gewerbe_gross(self):
        # 1.200 m²: 28.000 + 197×250 + 118×600 + 79×200 = 163.850
        e = KfwEingaben("nwg", 20000000, flaeche_m2=1200)
        r = berechnen(P, e)
        self.assertEqual(r.hoechstkosten_cent, 16385000)
        self.assertEqual(r.zuschuss_cent, 4915500)

    def test_12_deckel_hinweis(self):
        e = KfwEingaben("nwg", 5000000, flaeche_m2=100)
        r = berechnen(P, e)
        self.assertTrue(any("übersteigen" in h for h in r.hinweise))


class TestEingaben(unittest.TestCase):
    def test_ableitung_aus_v2_antworten(self):
        # MFH: WE aus O03, Selbstnutzung aus K01
        e = eingaben_aus_antworten({
            "O01": "MFH", "O03": 4, "K01": "Ja",
            "K02": "Gas- oder Biomasseheizung, mind. 20 Jahre, funktionstüchtig",
            "K03": 35000, "K04": "Ja",
        }, 1000000)
        self.assertEqual(e.objekt, "mfh")
        self.assertTrue(e.mfh_selbst and e.klima_bonus and e.kind)
        self.assertEqual(e.wohneinheiten, 4)
        # EFH-Arten: Selbstnutzung automatisch, Klima-Option 3 zählt nicht
        e2 = eingaben_aus_antworten({"O01": "REH",
                                     "K02": "Andere / jüngere Heizung / Neubau",
                                     "K03": ""}, 1)
        self.assertEqual(e2.objekt, "efh")
        self.assertTrue(e2.mfh_selbst)
        self.assertFalse(e2.klima_bonus)
        self.assertEqual(e2.einkommen_eur, 0)
        # Gewerbe: Fläche aus O05, nie Selbstnutzung
        e3 = eingaben_aus_antworten({"O01": "Gewerbe", "O05": 500}, 1)
        self.assertEqual(e3.objekt, "nwg")
        self.assertEqual(e3.flaeche_m2, 500)
        self.assertFalse(e3.mfh_selbst)


if __name__ == "__main__":
    unittest.main()
