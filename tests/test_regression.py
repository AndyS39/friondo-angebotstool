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

KONTROLL_SZENARIO = {
    # Objektdaten
    "O01": "EFH", "O02": 1995, "O03": 1, "O04": "Nein", "O05": 180,
    "O06": "Ja", "O08": "",
    # Alte Anlage (Öl-Zweig, Erdleitung 8 m)
    "A01": "Öl", "A02": 2001, "A03": 15000, "A04": "KG", "A05": 8,
    "A07": "Ja", "A08": "Kunststoff", "A09": "bis 5.000 L",
    "A10": "Nein", "A11": "Nein", "A12": "",
    # Neue Anlage (7-kW-AWM-Paket, 50-l-Puffer, Boden)
    "N01": "Luft/Wasser", "N02": "Ja", "N03": "bis 200 l",
    "N04": "Boden", "N06": "50 l",
    # Heizverteilung (1 Heizkreis, 1 Heizkörper S, 2 Verteiler mit 4/6 Gruppen)
    "H01": "1", "H02": "Heizkörper und Fußbodenheizung",
    "H03": "Ja", "H04": {"S": 1, "M": 0, "L": 0, "XL": 0},
    "H05": "Nein", "H06": 2, "H07": [4, 6],
    # Elektro/ZV (Nachrüst-Checkliste komplett)
    "E01": "KG", "E02": "Nein", "E04": "Nein", "E05": "Nein", "E06": "Nein",
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


if __name__ == "__main__":
    unittest.main()
