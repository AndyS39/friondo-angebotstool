# Regressionstest Phase 12: Kontroll-Szenario gegen die in PLAN_V2 fixierten
# Werte. Erdleitung: Eingabe 8 m -> berechnet 5 m. Erwartet:
# Netto 29.629,37 · USt 5.629,58 · Brutto 35.258,95 · Zuschuss 19.600,00 ·
# Eigenanteil 15.658,95.
# Start: venv\Scripts\python -m unittest discover -s tests
import unittest
from decimal import Decimal

from app import angebot_aufbau, kfw
from app import konfigurator as engine
from app.db import SessionLocal, init_db
from app.logik import logik_einlesen

# v5-stabiles Kontroll-Szenario (KG-Fall): E04–E06 (SLS/ÜSS/APZ) werden seit
# Logik v5 nicht mehr abgefragt; neu ist A13 (Anschlussleitung Inneneinheit,
# Pos. 103 × [Eingabe − 5]) – mit 4 m entsteht keine Position, die Summen
# entsprechen weiterhin exakt den in PLAN_V2/V3 fixierten Werten.
KONTROLL_SZENARIO = {
    # Objektdaten
    "O01": "EFH", "O02": 1995, "O03": 1, "O04": "Nein", "O05": 180,
    "O06": "Ja", "O08": "",
    # Alte Anlage (Öl-Zweig, Erdleitung 8 m, Kunststofftank 5.000 L)
    "A01": "Öl", "A02": 2001, "A03": 15000, "A04": "KG", "A05": 8,
    "A07": "Ja", "A08": "Kunststoff", "A09": "bis 5.000 L",
    "A10": "Nein", "A11": "Nein", "A12": "", "A13": 4,
    # Neue Anlage (7-kW-AWM-Paket, 50-l-Puffer, Garagendach ohne Bitumen)
    "N01": "Luft/Wasser", "N02": "Ja", "N03": "bis 200 l",
    "N04": "Garagendach", "N05": "Nein", "N06": "50 l",
    # Heizverteilung (2 Heizkreise, 1 Heizkörper S, 2 Verteiler mit je 4 Gruppen)
    "H01": "2", "H02": "Heizkörper und Fußbodenheizung",
    "H03": "Ja", "H04": {"S": 1, "M": 0, "L": 0, "XL": 0},
    "H05": "Nein", "H06": 2, "H07": [4, 4],
    # Elektro/ZV (v5: SLS/ÜSS/APZ entfallen)
    "E01": "KG", "E02": "Nein",
    # Friondo (HEMS ja)
    "P01": "Ja", "P02": "Nein", "P03": "Nein",
    # Förderung: 45.000 € Einkommen, Kind -> 35.000 -> +30 %; Satz 76 -> Deckel 70
    "K02": "Öl-, Kohle-, Gasetagen- oder Nachtspeicherheizung, funktionstüchtig",
    "K03": 45000, "K04": "Ja",
}


class TestKontrollSzenario(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.logik, bericht = logik_einlesen()
        assert not bericht.fehler, f"Logik v2 fehlerhaft: {bericht.fehler}"
        cls.session = SessionLocal()
        cls.positionen = angebot_aufbau.positionen_zusammenstellen(
            cls.logik, KONTROLL_SZENARIO, cls.session)

    def _netto_cent(self):
        return sum(round(p["menge"] * p["e_preis_cent"])
                   for p in self.positionen if not p["ep_flag"])

    def test_ampel_gruen(self):
        self.assertEqual(engine.ampel_gruende(self.logik, KONTROLL_SZENARIO), [])

    def test_katalog_vollstaendig(self):
        self.assertIsNone(engine.naechste_frage(self.logik, KONTROLL_SZENARIO))

    def test_erdleitung_8m_ergibt_5m(self):
        mengen = [p["menge"] for p in self.positionen if p["pos_nr"] == "102"]
        self.assertEqual(mengen, [5.0])

    def test_a13_4m_keine_anschlussleitung(self):
        # Logik v5: 4 m − 5 m < 0 -> keine Pos. 103
        self.assertEqual([p for p in self.positionen if p["pos_nr"] == "103"], [])

    def test_a13_8m_ergibt_3m_pos_103(self):
        # Logik v5: 8 m − 5 m = 3 m × 89,00 € = 267,00 € netto zusätzlich
        antworten = dict(KONTROLL_SZENARIO, A13=8)
        positionen = angebot_aufbau.positionen_zusammenstellen(self.logik, antworten, self.session)
        p103 = [p for p in positionen if p["pos_nr"] == "103"]
        self.assertEqual([p["menge"] for p in p103], [3.0])
        netto = sum(round(p["menge"] * p["e_preis_cent"]) for p in positionen if not p["ep_flag"])
        self.assertEqual(netto, 2962937 + 26700)   # 29.896,37 €
        self.assertIsNone(engine.naechste_frage(self.logik, antworten))

    def test_sls_uess_apz_nicht_mehr_abgefragt(self):
        self.assertNotIn("E04", self.logik.fragen)
        self.assertNotIn("E05", self.logik.fragen)
        self.assertNotIn("E06", self.logik.fragen)

    def test_summen(self):
        netto = self._netto_cent()
        ust = int(Decimal(netto) * Decimal("0.19"))
        self.assertEqual(netto, 2962937)            # 29.629,37 €
        self.assertEqual(ust, 562958)               # 5.629,58 €
        self.assertEqual(netto + ust, 3525895)      # 35.258,95 €

    def test_kfw(self):
        parameter, warnungen = kfw.parameter_lesen(self.logik)
        self.assertEqual(warnungen, [])
        brutto = self._netto_cent() + int(Decimal(self._netto_cent()) * Decimal("0.19"))
        eingaben = kfw.eingaben_aus_antworten(
            engine.kfw_daten(KONTROLL_SZENARIO), brutto)
        ergebnis = kfw.berechnen(parameter, eingaben)
        self.assertEqual(ergebnis.zuschuss_cent, 1960000)      # 19.600,00 €
        self.assertEqual(ergebnis.eigenanteil_cent, 1565895)   # 15.658,95 €
        self.assertIn("70 %", ergebnis.satz_text)
        self.assertIn("KfW 458", ergebnis.programm)

    def test_erdleitung_3m_ergibt_keine_position(self):
        antworten = dict(KONTROLL_SZENARIO, A05=3)
        positionen = angebot_aufbau.positionen_zusammenstellen(
            self.logik, antworten, self.session)
        self.assertEqual([p for p in positionen if p["pos_nr"] == "102"], [])

    def test_klima_vorbelegung_aus_energietraeger(self):
        frage = self.logik.fragen["K02"]
        self.assertEqual(engine.vorbelegung(frage, KONTROLL_SZENARIO),
                         frage.antworten[0])   # Öl -> Option 1
        gas_alt = dict(KONTROLL_SZENARIO, A01="Gas", A02=2001)
        self.assertEqual(engine.vorbelegung(frage, gas_alt), frage.antworten[1])
        gas_neu = dict(KONTROLL_SZENARIO, A01="Gas", A02=2020)
        self.assertEqual(engine.vorbelegung(frage, gas_neu), frage.antworten[2])

    def test_ampel_statt_abbruch(self):
        antworten = dict(KONTROLL_SZENARIO, A01="Nachtspeicher")
        del antworten["A07"], antworten["A08"], antworten["A09"]
        gruende = engine.ampel_gruende(self.logik, antworten)
        self.assertEqual(gruende, ["aktuelle Heizung nicht konfigurierbar"])
        # Katalog läuft trotzdem vollständig durch
        self.assertIsNone(engine.naechste_frage(self.logik, antworten))

    def test_keine_zv_artikel_mehr(self):
        # SLS/ÜSS/APZ-Komponenten stecken in Pos. 011 – 149/150/153 bleiben ungenutzt
        nummern = {p["pos_nr"] for p in self.positionen}
        self.assertFalse(nummern & {"149", "150", "153"})


class TestDachzentrale(unittest.TestCase):
    """Neuer v3-Testfall lt. PLAN_V3 Phase 20: alte Anlage im DG."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.logik, bericht = logik_einlesen()
        assert not bericht.fehler, bericht.fehler
        cls.session = SessionLocal()
        cls.antworten = dict(KONTROLL_SZENARIO)
        cls.antworten.update({
            "A04": "DG", "D01": "Nein", "D02": "Nein", "D03": "Nein",
            "D04": "Ja", "D05": {"Heizung VL/RL (m)": 6,
                                 "Trinkwasser TWK/TWW/Zirkulation (m)": 4},
            "A05": 8,   # Erdleitung wird gefragt (DG und D01 = Nein)
        })
        cls.positionen = angebot_aufbau.positionen_zusammenstellen(
            cls.logik, cls.antworten, cls.session)

    def _mengen(self, pos_nr):
        return [p["menge"] for p in self.positionen if p["pos_nr"] == pos_nr]

    def test_dg_artikel(self):
        self.assertEqual(self._mengen("163"), [1.0])     # immer bei A04 = DG
        self.assertEqual(self._mengen("139"), [6.0])     # Heizung 6 m
        self.assertEqual(self._mengen("140"), [4.0])     # Trinkwasser 4 m
        self.assertEqual(self._mengen("141"), [])        # D03 = Nein

    def test_bloecke(self):
        block_163 = [p["block_nr"] for p in self.positionen if p["pos_nr"] == "163"]
        self.assertEqual(block_163, [5])
        self.assertEqual([p["block_nr"] for p in self.positionen
                          if p["pos_nr"] in ("139", "140")], [2, 2])

    def test_erdleitung_gefragt_fassade_nicht(self):
        fragen = self.logik.fragen
        self.assertTrue(engine.ist_sichtbar(fragen["A05"], self.antworten, fragen))
        self.assertFalse(engine.ist_sichtbar(fragen["A06"], self.antworten, fragen))
        self.assertEqual(self._mengen("102"), [5.0])     # 8 − 3
        self.assertEqual(self._mengen("134"), [])

    def test_fassade_bei_d01_ja(self):
        antworten = dict(self.antworten, D01="Ja")
        for entfaellt in ("D02", "D03", "D04", "D05", "A05"):
            antworten.pop(entfaellt, None)
        fragen = self.logik.fragen
        self.assertTrue(engine.ist_sichtbar(fragen["A06"], antworten, fragen))
        self.assertFalse(engine.ist_sichtbar(fragen["A05"], antworten, fragen))

    def test_ampel_grund_15(self):
        antworten = dict(self.antworten, D04="Nein")
        antworten.pop("D05", None)
        gruende = engine.ampel_gruende(self.logik, antworten)
        self.assertTrue(any("Dachzentrale" in g for g in gruende))

    def test_katalog_vollstaendig(self):
        self.assertIsNone(engine.naechste_frage(self.logik, self.antworten))
        self.assertEqual(engine.ampel_gruende(self.logik, self.antworten), [])


class TestRabatt(unittest.TestCase):
    """Phase 21: Kontroll-Szenario + 500 € Rabatt lt. PLAN_V3."""

    @classmethod
    def setUpClass(cls):
        from app.models import Angebot, AngebotsPosition
        init_db()
        cls.logik, bericht = logik_einlesen()
        assert not bericht.fehler
        session = SessionLocal()
        positionen = angebot_aufbau.positionen_zusammenstellen(
            cls.logik, KONTROLL_SZENARIO, session)
        cls.angebot = Angebot(nummer="TEST-RABATT", kunde_id=0)
        for p in positionen:
            cls.angebot.positionen.append(AngebotsPosition(**p))

    def test_summen_mit_500_euro_brutto_rabatt(self):
        # Phase 26: Netto → USt → Gesamt-Betrag → − Rabatt (brutto) → = Endbetrag
        self.angebot.rabatt_cent = 50000
        self.angebot.rabatt_prozent = None
        s = self.angebot.summen()
        self.assertEqual(s["netto"], 2962937)
        self.assertEqual(s["ust"], 562958)                  # 5.629,58 €
        self.assertEqual(s["brutto"], 3525895)              # 35.258,95 €
        self.assertEqual(s["rabatt"], 50000)
        self.assertEqual(s["endbetrag"], 3475895)           # 34.758,95 €

    def test_kfw_mit_rabatt(self):
        self.angebot.rabatt_cent = 50000
        self.angebot.rabatt_prozent = None
        parameter, _ = kfw.parameter_lesen(self.logik)
        eingaben = kfw.eingaben_aus_antworten(
            engine.kfw_daten(KONTROLL_SZENARIO), self.angebot.summen()["endbetrag"])
        ergebnis = kfw.berechnen(parameter, eingaben)
        self.assertEqual(ergebnis.zuschuss_cent, 1960000)     # Deckel weiter erreicht
        self.assertEqual(ergebnis.eigenanteil_cent, 1515895)  # 15.158,95 €

    def test_prozent_rabatt_vom_brutto(self):
        self.angebot.rabatt_cent = None
        self.angebot.rabatt_prozent = 10.0
        s = self.angebot.summen()
        self.assertEqual(s["rabatt"], 352590)   # 10 % von 35.258,95, kaufmännisch
        self.assertEqual(s["endbetrag"], 3173305)

    def test_deckungsbeitrag_sinkt_um_netto_anteil(self):
        # DB sinkt um den Netto-Anteil des Brutto-Rabatts (÷ 1,19)
        self.angebot.rabatt_cent = None
        self.angebot.rabatt_prozent = None
        ohne = self.angebot.deckungsbeitrag()
        self.angebot.rabatt_cent = 50000
        mit = self.angebot.deckungsbeitrag()
        self.assertEqual(mit["rabatt"], 42017)              # 500 ÷ 1,19 = 420,17 €
        self.assertEqual(mit["db"], ohne["db"] - 42017)

    def test_ohne_rabatt_unveraendert(self):
        self.angebot.rabatt_cent = None
        self.angebot.rabatt_prozent = None
        s = self.angebot.summen()
        self.assertEqual(s["rabatt"], 0)
        self.assertEqual(s["endbetrag"], 3525895)


if __name__ == "__main__":
    unittest.main()
