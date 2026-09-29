# Tests PLAN_PROJ_V3 (Phasen 84–86): Auftragsdaten für TAIFUN-Aufträge,
# Bestandsimport, Go-live-Hilfen. Laufen gegen die Entwicklungs-DB und räumen
# ihre Testdaten (Kunden mit E-Mail projekt-v3@test.local) wieder auf.
import io
import unittest
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import projektierung as kern
from app import projektierung_logik
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, Aufgabe, AufgabenpaketInstanz, Gewerk, Kunde,
                        Projekt, ProjektDokument, ProjektTermin, ProjektVerlauf,
                        SteckbriefWert, Vorgang, angebot_status_setzen)
from tests.test_projektierung_v4 import aufraeumen as _aufraeumen_v4

TEST_EMAIL = "projekt-v3@test.local"
MINI_PDF = (b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")


def aufraeumen(s):
    import tests.test_projektierung_v4 as v4
    alt = v4.TEST_EMAIL
    v4.TEST_EMAIL = TEST_EMAIL
    try:
        for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
            for p in s.query(Projekt).filter_by(kunde_id=k.id):
                s.query(ProjektDokument).filter_by(projekt_id=p.id).delete()
        s.commit()
        _aufraeumen_v4(s)
    finally:
        v4.TEST_EMAIL = alt


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def taifun_angebot(self, sparte="WP", pdf=False):
        kunde = Kunde(anrede="Frau", vorname="Tina", nachname="Taifun-V3-Test",
                      strasse="Hafenstr. 1", plz="47119", ort="Duisburg",
                      email=TEST_EMAIL, telefon="0203 2")
        self.s.add(kunde)
        self.s.flush()
        angebot = Angebot(nummer="EXT-tmp", kunde_id=kunde.id, extern=True,
                          taifun_nummer="AN261234", extern_endbetrag_cent=2500000,
                          datum=datetime.now(), konfigurator_typ=sparte)
        self.s.add(angebot)
        self.s.flush()
        angebot.nummer = f"EXT-{angebot.id}"
        angebot_status_setzen(angebot, "Angenommen")
        self.s.commit()
        return angebot


class Phase84Auftragsdaten(Basis):
    def test_felder_aus_blatt(self):
        logik = projektierung_logik.hole_logik(self.s, erzwingen=True)
        self.assertEqual(logik.fehler, [])
        felder = {f.feld: f for f in logik.auftragsdaten_felder("WP")}
        self.assertEqual(felder["hersteller"].typ, "auswahl")
        self.assertIn("Vaillant", felder["hersteller"].optionen)
        self.assertEqual(felder["oeltank"].typ, "ja_nein")
        self.assertEqual(felder["leistungsklasse"].typ, "zahl")
        self.assertIn("wallbox", {f.feld for f in logik.auftragsdaten_felder("PV")})
        # zusätzliche Felder erscheinen im Steckbrief der Akte
        self.assertIn("serie_modell", [f for f, _ in kern.steckbrief_felder("WP")])

    def test_taifun_projekt_mit_auftragsdaten(self):
        angebot = self.taifun_angebot()
        # Anlage über den Dialog → Weiterleitung auf die Auftragsdaten
        antwort = self.client.post(f"/projektierung/angebot/{angebot.id}/projekt",
                                   data={"projekt_wahl": "neu", "sparte_WP": "on",
                                         "projektleiter_id": "1", "strasse": "Hafenstr. 1",
                                         "plz": "47119", "ort": "Duisburg"},
                                   follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        self.assertIn("/auftragsdaten", antwort.headers["location"])
        self.s.expire_all()
        gewerk = self.s.query(Gewerk).filter(Gewerk.angebot_id == angebot.id).one()
        seite = self.client.get(f"/projektierung/gewerk/{gewerk.id}/auftragsdaten")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Angebots-PDF (Pflicht)", seite.text)
        self.assertIn("KfW-gefördert", seite.text)
        # ohne PDF → abgewiesen
        ohne = self.client.post(f"/projektierung/gewerk/{gewerk.id}/auftragsdaten",
                                data={f"g{gewerk.id}__hersteller": "Bosch"},
                                follow_redirects=False)
        self.assertIn("Pflicht", ohne.headers["location"].replace("%20", " ")
                      .replace("+", " "))
        p = f"g{gewerk.id}__"
        daten = {p + "hersteller": "Vaillant", p + "serie_modell": "aroTHERM plus",
                 p + "leistungsklasse": "10", p + "innengeraet": "uniTOWER",
                 p + "oeltank": "ja", p + "oeltank_groesse": "3.000",
                 p + "oeltank_material": "Stahl, Kellerzugang", p + "folierung": "ja",
                 p + "zaehlerschrank": "3-Feld", p + "stemmarbeiten": "ja",
                 p + "erdleitung_m": "12", "kfw_gefoerdert": "ja"}
        mit = self.client.post(f"/projektierung/gewerk/{gewerk.id}/auftragsdaten",
                               data=daten,
                               files={"pdf_datei": ("AN261234.pdf", io.BytesIO(MINI_PDF),
                                                    "application/pdf")},
                               follow_redirects=False)
        self.assertEqual(mit.status_code, 303)
        self.s.expire_all()
        gewerk = self.s.get(Gewerk, gewerk.id)
        angebot = self.s.get(Angebot, angebot.id)
        self.assertIsNotNone(gewerk.auftragsdaten_am)
        self.assertTrue(angebot.extern_pdf_pfad)
        self.assertEqual(angebot.kfw_gefoerdert, "ja")
        werte = kern.steckbrief_daten(self.s, [gewerk.id])[gewerk.id]
        self.assertEqual(werte["hersteller"].wert, "Vaillant")
        self.assertEqual(werte["hersteller"].quelle, "auftragsdaten")
        self.assertFalse(werte["hersteller"].manuell)
        self.assertEqual(werte["oeltank_groesse"].wert, "3000")
        # Sub-Mail-Platzhalter
        platz = kern.sub_mail_platzhalter(self.s, gewerk)
        self.assertEqual(platz["geraet"], "Vaillant · aroTHERM plus · 10 · uniTOWER")
        self.assertEqual(platz["oeltank"], "ja · 3000 · Stahl, Kellerzugang")
        self.assertIn("12 m", platz["erdarbeiten"])
        self.assertTrue(platz["stemmarbeiten"].startswith("Stemmarbeiten sind"))
        # BzA: gefördert = ja → Buttons (kein „unbekannt“ mehr)
        from app import bza
        self.assertIs(bza.ist_gefoerdert(self.s, gewerk), True)
        # PDF auch in der Galerie „Allgemein“
        from app.models import GalerieDatei
        projekt = self.s.get(Projekt, gewerk.projekt_id)
        self.assertTrue(self.s.query(GalerieDatei).filter_by(
            vorgang_id=projekt.vorgang_id, ordner="Allgemein").count())
        # Material-Aufgabe: Hinweis statt UGL-Button
        akte = self.client.get(f"/projektierung/projekt/{projekt.id}").text
        self.assertIn("Auftragsdaten bearbeiten", akte)
        material = (self.s.query(Aufgabe).filter(Aufgabe.gewerk_id == gewerk.id,
                                                Aufgabe.aktion_wert == "ugl_collin").first())
        if material is not None:
            self.assertIn("Bestellung aus TAIFUN-Positionen", akte)
        # „Neu ableiten“ überschreibt Auftragsdaten nicht …
        kern.steckbrief_ableiten(self.s, gewerk)
        self.s.commit()
        self.assertEqual(kern.steckbrief_daten(self.s, [gewerk.id])[gewerk.id]
                         ["hersteller"].wert, "Vaillant")
        # … die FP-Erfassung schon (fp_frage-Regel FP-O01 → oeltank)
        kern.steckbrief_ableiten(self.s, gewerk, fp_antworten={"FP-O01": "Nein"})
        self.s.commit()
        oel = kern.steckbrief_daten(self.s, [gewerk.id])[gewerk.id]["oeltank"]
        self.assertEqual((oel.wert, oel.quelle), ("nein", ""))

    def test_steckbrief_schritte_nachziehen(self):
        """Schritte mit steckbrief:-Bedingung (z. B. Folierung) entstehen nach
        dem Speichern der Auftragsdaten nachträglich."""
        logik = projektierung_logik.hole_logik(self.s)
        bedingte = [(p.key, sch.nr, sch.sichtbar_wenn) for p in logik.pakete.values()
                    for sch in p.schritte
                    if (sch.sichtbar_wenn or "").lower().startswith("steckbrief:")
                    and p.sparte in ("ALLE", "WP")]
        if not bedingte:
            self.skipTest("keine steckbrief-abhängigen Schritte im Blatt")
        angebot = self.taifun_angebot()
        projekt = kern.projekt_anlegen(self.s, angebot, projektleiter_id=1)
        gewerk = kern.gewerk_anlegen(self.s, projekt, angebot, "WP")
        self.s.commit()
        key, nr, bedingung = bedingte[0]
        feld, _, soll = bedingung[len("steckbrief:"):].partition("=")
        instanz = (self.s.query(AufgabenpaketInstanz)
                   .filter_by(gewerk_id=gewerk.id, paket_key=key).first())
        if instanz is None:
            self.skipTest("Paket mit bedingtem Schritt ist kein IMMER-Paket")
        vorher = {a.reihenfolge for a in self.s.query(Aufgabe)
                  .filter_by(paket_instanz_id=instanz.id)}
        self.assertNotIn(nr, vorher)
        feld_def = next((f for f in kern.auftragsdaten_felder(self.s, "WP")
                         if f.feld == feld.strip()), None)
        if feld_def is None:
            self.skipTest("Bedingungsfeld nicht im Auftragsdaten-Formular")
        kern.auftragsdaten_speichern(self.s, gewerk, {feld.strip(): soll.strip()})
        self.s.commit()
        nachher = {a.reihenfolge for a in self.s.query(Aufgabe)
                   .filter_by(paket_instanz_id=instanz.id)}
        self.assertIn(nr, nachher)

    def test_tool_angebot_ohne_auftragsdaten(self):
        """Tool-Angebote kennen keine Auftragsdaten-Seite."""
        from tests.test_projektierung_v4 import Basis as V4
        gewerk = V4.gewerk_neu(self)
        projekt = self.s.get(Projekt, gewerk.projekt_id)
        self.s.get(Kunde, projekt.kunde_id).email = TEST_EMAIL   # Aufräumen
        self.s.commit()
        antwort = self.client.get(f"/projektierung/gewerk/{gewerk.id}/auftragsdaten",
                                  follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        self.assertNotIn("/auftragsdaten", antwort.headers["location"])

    def test_pdf_stub(self):
        self.assertEqual(kern.auftragsdaten_aus_pdf(b"%PDF"), {})


if __name__ == "__main__":
    unittest.main()
