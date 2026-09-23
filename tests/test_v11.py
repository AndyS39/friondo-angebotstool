# Tests v11 (PLAN_V11, Phase 68): Team-Feedback – Kalkulation, Konfigurator,
# Editor, Profile. Start: venv\Scripts\python -m unittest tests.test_v11
import unittest

from app.db import SessionLocal, init_db
from app.logik import logik_einlesen
from app import angebot_aufbau
from app import anhaenge as anhaenge_modul
from app import konfigurator as engine
from app.models import Angebot, AngebotsPosition, Kunde
from app.routers.meine_angebote import _rabatt_lesen


class TestPufferUndCS8800(unittest.TestCase):
    """AN-C-261082 / AN-C-261127: Puffer-Doppelberechnung + CS8800-Reihenfolge."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.logik, bericht = logik_einlesen()
        assert not bericht.fehler, bericht.fehler
        cls.session = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.session.close()

    def test_awm6_mit_50l_position_und_bereinigter_pakettext(self):
        # Entscheidung 23.09.2026: Der 50-l-Puffer bleibt eine eigene Position
        # (Z15); dafür entfernt die Textregel die Pufferzeile aus den
        # Pakettexten 045–054 – keine doppelte Darstellung (AN-C-261082).
        antworten = {"A03": 12000, "N02": "Ja", "N03": "bis 200 l",
                     "N06": "50 l", "A10": "Nein"}
        refs = [a.ref for a in angebot_aufbau.artikel_ermitteln(self.logik, antworten)]
        self.assertIn("Z15", refs)
        self.assertIn("046", refs)
        refs2 = [a.ref for a in angebot_aufbau.artikel_ermitteln(
            self.logik, dict(antworten, N06="100 l"))]
        self.assertIn("Z16", refs2)

    def test_pakettexte_ohne_pufferzeile(self):
        from app.models import Artikel
        for pos in ("045", "046", "047", "048", "049",
                    "050", "051", "052", "053", "054"):
            artikel = (self.session.query(Artikel)
                       .filter(Artikel.pos_nr == pos, Artikel.aktiv.is_(True))
                       .first())
            self.assertIsNotNone(artikel, pos)
            self.assertNotIn("BST 50", artikel.beschreibung or "", pos)

    def test_textregel_zeile_entfernen(self):
        from app import import_preisliste
        text = "Zeile A\nPufferspeicher BST 50 Ehp, 540x530, Nutzinhalt 50 L\nZeile C"
        self.assertEqual(import_preisliste.zeile_entfernen(text, "Pufferspeicher BST 50"),
                         "Zeile A\nZeile C")

    def test_cs8800_reihenfolge_block1(self):
        antworten = {"A03": 32000, "N02": "Ja", "N08": "Weiß", "N07": "200 l",
                     "A10": "Nein"}
        block1 = [p["pos_nr"] for p in angebot_aufbau.positionen_zusammenstellen(
            self.logik, antworten, self.session) if p.get("block_nr") == 1]
        self.assertEqual(block1[0], "030")     # Außeneinheit Position 1
        self.assertEqual(block1[1], "056")     # Inneneinheit Position 2
        self.assertEqual(block1[2:4], ["Z17", "065"])   # danach Puffer/WW

    def test_cs8800_broschuere_bei_030_031(self):
        angebot = Angebot(nummer="TEST-V11-B", kunde_id=0)
        angebot.positionen.append(AngebotsPosition(sort=1, pos_nr="030",
                                                   menge=1, e_preis_cent=1))
        namen = {a.datei for a in anhaenge_modul.fuer_angebot(self.logik, angebot)}
        self.assertIn("Bosch CS8800iAW.pdf", namen)

    def test_textregel_bereich_geparst(self):
        # "Positionen 045–054" + "Zeile '…' aus der Beschreibung entfernen"
        import openpyxl

        from app import config, import_preisliste
        wb = openpyxl.load_workbook(config.LOGIK_EXCEL_PFAD, read_only=True)
        regeln = import_preisliste.lade_textregeln(wb)
        wb.close()
        for pos in ("045", "050", "054"):
            self.assertEqual(regeln.zeile_entfernen.get(pos),
                             "Pufferspeicher BST 50")


class TestFlaechenAuslegung(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.logik, bericht = logik_einlesen()
        assert not bericht.fehler, bericht.fehler

    def test_150qm_mal_60_ergibt_7kw_klasse(self):
        antworten = {"A03": "Verbrauch unbekannt", "A17": 150,
                     "A18": "Altbau – 60 W/m²", "A14": "Nein"}
        self.assertEqual(engine.flaechen_heizlast(antworten), 9.0)
        zeile = engine.leistungsklasse(self.logik, antworten)
        self.assertEqual(zeile.leistungsklasse, "7 kW")
        self.assertEqual(engine.flaechen_herleitung(antworten),
                         "Auslegung über Fläche: 150 m² × 60 W/m² = 9,0 kW")

    def test_ausserhalb_der_klassen_ampel(self):
        antworten = {"A03": "Verbrauch unbekannt", "A17": 300,
                     "A18": "Altbau unsaniert – 70 W/m²", "A14": "Nein"}
        self.assertIn("Leistungsklasse zu hoch",
                      engine.ampel_gruende(self.logik, antworten))

    def test_auslegungszeile_in_block1(self):
        session = SessionLocal()
        try:
            antworten = {"A03": "Verbrauch unbekannt", "A17": 150,
                         "A18": "Altbau – 60 W/m²", "A14": "Nein",
                         "N02": "Ja", "N03": "bis 200 l", "N06": "50 l",
                         "A10": "Nein"}
            positionen = angebot_aufbau.positionen_zusammenstellen(
                self.logik, antworten, session)
            zeilen = [p for p in positionen
                      if p["bezeichnung"] == "Auslegung der Wärmepumpe"]
            self.assertEqual(len(zeilen), 1)
            self.assertEqual(zeilen[0]["block_nr"], 1)
            self.assertEqual(zeilen[0]["e_preis_cent"], 0)
            self.assertIn("150 m² × 60 W/m²", zeilen[0]["beschreibung"])
        finally:
            session.close()


class TestDachzentraleEtagen(unittest.TestCase):
    """v11: D06-Etagen-Frage, Meterabfragen D07/D08, Vermerk-Position Z25."""

    @classmethod
    def setUpClass(cls):
        cls.logik, bericht = logik_einlesen()
        assert not bericht.fehler, bericht.fehler
        cls.session = SessionLocal()
        cls.basis = {"A03": 15000, "A04": "DG", "D01": "Nein", "D02": "Nein",
                     "N02": "Ja", "A10": "Nein"}

    @classmethod
    def tearDownClass(cls):
        cls.session.close()

    def test_andere_etage_meter_statt_pauschale(self):
        antworten = dict(self.basis, D06="Andere Etage (z. B. EG)",
                         D04="Ja", D07=6, D08=4)
        artikel = {(a.ref, a.menge) for a in
                   angebot_aufbau.artikel_ermitteln(self.logik, antworten)}
        self.assertIn(("139", 6.0), artikel)   # Heizung (Artikeltext VL/RL)
        self.assertIn(("140", 4.0), artikel)   # Warmwasser/Zirkulation
        self.assertFalse(any(ref == "141" for ref, _ in artikel))

    def test_gleiche_etage_pauschale_141(self):
        antworten = dict(self.basis, D06="Gleiche Etage (KG)")
        artikel = {a.ref for a in
                   angebot_aufbau.artikel_ermitteln(self.logik, antworten)}
        self.assertIn("141", artikel)
        self.assertFalse({"139", "140"} & artikel)

    def test_vermerk_position_z25(self):
        antworten = dict(self.basis, D06="Gleiche Etage (KG)")
        positionen = angebot_aufbau.positionen_zusammenstellen(
            self.logik, antworten, self.session)
        z25 = [p for p in positionen if p["pos_nr"] == "Z25"]
        self.assertEqual(len(z25), 1)
        self.assertEqual(z25[0]["block_nr"], 5)
        self.assertEqual(z25[0]["e_preis_cent"], 0)
        # Vermerke-Blatt liefert den Text nicht mehr doppelt
        self.assertEqual(engine.vermerke_fuer(self.logik, antworten), [])


class TestProfilAnhaenge(unittest.TestCase):
    def test_enni_ohne_ratenkauf_und_spotdynamic(self):
        logik, _ = logik_einlesen()
        angebot = Angebot(nummer="TEST-V11-A", kunde_id=0,
                          protokoll_json='[{"frage_id": "P03", "antwort": "Ja"}]')
        fuer_standard = {a.datei for a in
                         anhaenge_modul.fuer_angebot(logik, angebot, "Standard")}
        fuer_enni = {a.datei for a in
                     anhaenge_modul.fuer_angebot(logik, angebot, "Enni")}
        self.assertIn("Broschüre Ratenkauf.pdf", fuer_standard)
        self.assertIn("Friondo SpotDynamic.pdf", fuer_standard)
        self.assertFalse({"Broschüre Ratenkauf.pdf", "Friondo SpotDynamic.pdf"}
                         & fuer_enni)
        self.assertIn("Friondo Unternehmenspräsentation.pdf", fuer_enni)


class TestRabattEntfernen(unittest.TestCase):
    """v11: Eingabe 0 (oder leeres Feld) entfernt den Rabatt."""

    def test_null_und_leer_bedeuten_entfernen(self):
        for wert in ("0", "0,00", ""):
            cent, prozent, _, fehler = _rabatt_lesen(
                {"rabatt_wert": wert, "rabatt_typ": "betrag"})
            self.assertEqual((cent, prozent, fehler), (None, None, ""), wert)
        cent, prozent, _, fehler = _rabatt_lesen(
            {"rabatt_wert": "0", "rabatt_typ": "prozent"})
        self.assertEqual((cent, prozent, fehler), (None, None, ""))

    def test_gueltige_werte_bleiben_gueltig(self):
        cent, prozent, _, fehler = _rabatt_lesen(
            {"rabatt_wert": "500", "rabatt_typ": "betrag"})
        self.assertEqual((cent, fehler), (50000, ""))
        cent, prozent, _, fehler = _rabatt_lesen(
            {"rabatt_wert": "10", "rabatt_typ": "prozent"})
        self.assertEqual((prozent, fehler), (10.0, ""))

    def test_unsinn_bleibt_fehler(self):
        _, _, _, fehler = _rabatt_lesen(
            {"rabatt_wert": "abc", "rabatt_typ": "betrag"})
        self.assertTrue(fehler)


class TestKopierenUndLieferanschrift(unittest.TestCase):
    """v11 (Phase 66): Modellfelder der neuen Funktionen."""

    def test_neue_spalten_vorhanden(self):
        angebot = Angebot(nummer="TEST-V11-C", kunde_id=0)
        self.assertEqual(angebot.liefer_anschrift or "", "")
        self.assertEqual(angebot.kopie_von or "", "")

    def test_verbrauch_unbekannt_konstante(self):
        self.assertEqual(engine.VERBRAUCH_UNBEKANNT, "Verbrauch unbekannt")
        self.assertEqual(engine.ID_AUSLEGUNG_FLAECHE, "A17")
        self.assertEqual(engine.ID_GEBAEUDESTANDARD, "A18")


if __name__ == "__main__":
    unittest.main()
