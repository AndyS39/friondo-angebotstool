# Regressionstests v8 (Phase 52): Heizlast-Vorrang, neue WP-Artikelwege,
# Rechnungsanschrift im PDF, Wiederholgruppe (Klima), Ablehnungsgrund,
# 90-Tage-Prüflauf im Trockenmodus.
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import pypdf

from app import ablauf_pruefung, angebot_aufbau, pdf_export
from app import konfigurator as engine
from app.db import SessionLocal, init_db
from app.logik import logik_einlesen, logik_fuer_sparte
from app.models import Angebot, AngebotsPosition, Kunde
from tests.test_regression import KONTROLL_SZENARIO


class TestV8(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        cls.logik, bericht = logik_einlesen()
        assert not bericht.fehler, bericht.fehler

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def test_heizlast_hat_vorrang_vor_kwh(self):
        # 8,4 kW → 7-kW-Paket, obwohl die kWh-Angabe (5.000) 4 kW ergäbe
        antworten = dict(KONTROLL_SZENARIO, A03=5000, A14="Ja", A15="8,4")
        zeile = engine.leistungsklasse(self.logik, antworten)
        self.assertEqual(zeile.leistungsklasse, "7 kW")
        # kWh über 31.000 löst mit gültiger Heizlast keine AMPEL aus
        antworten = dict(KONTROLL_SZENARIO, A03=35000, A14="Ja", A15="8,4")
        self.assertEqual(engine.ampel_gruende(self.logik, antworten), [])
        # ab 16 kW → AMPEL Leistungsklasse zu hoch
        antworten = dict(KONTROLL_SZENARIO, A14="Ja", A15="17")
        self.assertTrue(any("Leistungsklasse" in g
                            for g in engine.ampel_gruende(self.logik, antworten)))

    def test_unterverteilung_mit_mid(self):
        antworten = dict(KONTROLL_SZENARIO, E04="Ja", E05="Ja")
        pos = angebot_aufbau.positionen_zusammenstellen(self.logik, antworten, self.s)
        nummern = {p["pos_nr"]: p for p in pos}
        self.assertIn("152", nummern)
        self.assertIn("Z23", nummern)
        self.assertEqual(nummern["152"]["block_nr"], 7)

    def test_waermemengenzaehler_ohne_ep(self):
        antworten = dict(KONTROLL_SZENARIO, O01="2FH", O03=2, K01="Ja",
                         H08="Ja", H09=3)
        self.assertIsNone(engine.naechste_frage(self.logik, antworten))
        pos = [p for p in angebot_aufbau.positionen_zusammenstellen(
            self.logik, antworten, self.s) if p["pos_nr"] == "096"]
        self.assertEqual(len(pos), 1)
        self.assertEqual(pos[0]["menge"], 3)
        self.assertFalse(pos[0]["ep_flag"])   # kein EP trotz EP-Flag im Stamm

    def test_stemmarbeiten_im_oel_zweig(self):
        antworten = dict(KONTROLL_SZENARIO, A08="Stahl", A09="bis 5.000 L", A16="Ja")
        pos = [p for p in angebot_aufbau.positionen_zusammenstellen(
            self.logik, antworten, self.s) if p["pos_nr"] == "126"]
        self.assertEqual(len(pos), 1)
        self.assertEqual(pos[0]["block_nr"], 5)

    def test_rechnungsanschrift_im_pdf(self):
        kunde = Kunde(anrede="Herr", vorname="Emil", nachname="Achtfall",
                      strasse="Baustelle 3", plz="47441", ort="Moers")
        angebot = Angebot(nummer="AN-C-V8TEST", datum=datetime(2026, 8, 26),
                          rechnung_name="Acht GmbH", rechnung_strasse="Bürostr. 8",
                          rechnung_plz="40210", rechnung_ort="Düsseldorf")
        angebot.positionen = [AngebotsPosition(sort=1, bezeichnung="Pos",
                                               menge=1, einheit="Stck",
                                               e_preis_cent=10000, gruppe="")]
        with tempfile.TemporaryDirectory() as ordner:
            pfad = Path(ordner) / "v8.pdf"
            pdf_export.erzeuge_pdf(angebot, kunde, kfw_ergebnis=None,
                                   mit_vollmacht=False, ziel=pfad)
            text = pypdf.PdfReader(str(pfad)).pages[0].extract_text()
        self.assertIn("Acht GmbH", text)
        self.assertIn("Bürostr. 8", text)
        self.assertIn("Ausführungsort: Baustelle 3, 47441 Moers", text)
        self.assertNotIn("Kunden-Nr", text)

    def test_klima_wiederholgruppe(self):
        kl = logik_fuer_sparte(self.logik, "KL")
        antworten = {"KO01": "EFH", "KO02": 1985, "KO03": "Ja",
                     "KO04": "2", "KO05": 3}
        sichtbar = engine.sichtbare_fragen(kl, antworten)
        kr01 = [f for f in sichtbar if f.id.startswith("KR01#")]
        self.assertEqual([f.id for f in kr01], ["KR01#1", "KR01#2", "KR01#3"])
        # KR07: Optionen dynamisch auf die Anzahl Außengeräte (2) begrenzt
        kr07 = [f for f in sichtbar if f.id == "KR07#1"][0]
        self.assertEqual(kr07.antworten, ["1", "2"])
        # Reihenfolge: Raum 1 komplett vor Raum 2, alles vor KA01
        ids = [f.id for f in sichtbar]
        self.assertLess(ids.index("KR07#1"), ids.index("KR01#2"))
        self.assertLess(ids.index("KR07#3"), ids.index("KA01"))

    def test_ww300_pos065_nur_einmal(self):
        # Bugfix: Pos. 065 kam bei N03 = "300 l" doppelt (Aktionszeile +
        # Paketmatrix-Spalte "WW 300 l") – die Matrix ist die einzige Quelle
        antworten = dict(KONTROLL_SZENARIO, N03="300 l")
        pos = [p for p in angebot_aufbau.positionen_zusammenstellen(
            self.logik, antworten, self.s) if p["pos_nr"] == "065"]
        self.assertEqual(len(pos), 1)
        self.assertEqual(pos[0]["menge"], 1)
        # die Aktionszeile trägt keine eigene Artikel-Anweisung mehr
        n03 = [a for a in self.logik.aktionen
               if a.frage == "N03" and a.antwort == "300 l"]
        self.assertEqual(n03[0].artikel, [])
        # und die übrigen Matrix-Spalten sind frei von Doppelquellen
        _, bericht = logik_einlesen()
        self.assertFalse([w for w in bericht.warnungen
                          if "Doppelte Artikelquelle" in w], bericht.warnungen)

    def test_doppelquellen_warnung(self):
        # Der Wächter meldet, wenn ein Matrix-Artikel zusätzlich über eine
        # Aktionszeile käme (künstlich nachgestellt)
        import copy

        from app import logik as logik_modul
        from app.logik import Aktion, ArtikelRef, Pruefbericht
        kopie = copy.copy(self.logik)
        kopie.aktionen = list(self.logik.aktionen) + [
            Aktion("N03", "300 l", "Artikel: Pos. 065 ×1", "normal", "",
                   [ArtikelRef("065")], "")]
        bericht = Pruefbericht()
        logik_modul._doppelquellen_pruefen(kopie, bericht)
        self.assertTrue(any("Doppelte Artikelquelle" in w and "065" in w
                            for w in bericht.warnungen), bericht.warnungen)

    def test_prueflauf_trockenmodus(self):
        kunde = Kunde(nachname="PruefV8")
        self.s.add(kunde); self.s.commit()
        alt = angebot_aufbau.angebot_anlegen(self.s, kunde.id)
        alt.status = "Versendet"
        alt.versendet_am = datetime.now() - timedelta(days=200)
        geschuetzt = angebot_aufbau.angebot_anlegen(self.s, kunde.id)
        geschuetzt.status = "Versendet"
        geschuetzt.versendet_am = datetime.now() - timedelta(days=200)
        geschuetzt.wiedervorlage_am = datetime.now() + timedelta(days=5)
        self.s.commit()
        try:
            ergebnis = ablauf_pruefung.lauf(self.s, trocken=True)
            self.assertIn(alt.nummer, ergebnis["nummern"])
            self.assertNotIn(geschuetzt.nummer, ergebnis["nummern"])
            # Trockenmodus ändert nichts
            self.s.expire_all()
            self.assertEqual(self.s.get(Angebot, alt.id).status, "Versendet")
        finally:
            self.s.delete(self.s.get(Angebot, alt.id))
            self.s.delete(self.s.get(Angebot, geschuetzt.id))
            self.s.delete(self.s.get(Kunde, kunde.id))
            self.s.commit()


if __name__ == "__main__":
    unittest.main()
