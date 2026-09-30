# Tests Phase 98 (CLAUDE v20, PLAN_GESAMT B4): Rechnungs-/Lieferanschrift an
# Angebot und Kunde, PDF-Empfängerblock, Lieferschein, Entwurfs-Regel.
# Räumt Kunden mit anschriften-v20@test.local auf.
import unittest
import warnings

warnings.filterwarnings("ignore")

import pypdf
from fastapi.testclient import TestClient

from app import angebot_aufbau, anschriften, pdf_export
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Kunde, Vorgang,
                        angebot_status_setzen)

TEST_EMAIL = "anschriften-v20@test.local"


def aufraeumen(s):
    from app import config
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            (config.ANGEBOTE_PDF_ORDNER / f"{a.nummer}.pdf").unlink(missing_ok=True)
            s.delete(a)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.delete(v)
        s.delete(k)
    s.commit()


class Anschriften(unittest.TestCase):
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

    def kunde(self, **extra):
        k = Kunde(anrede="Herr", vorname="Hans", nachname="Anschrift-V20",
                  strasse="Ausführungsweg 5", plz="47139", ort="Duisburg",
                  email=TEST_EMAIL, **extra)
        self.s.add(k)
        self.s.commit()
        return k

    def angebot(self, kunde):
        a = angebot_aufbau.angebot_anlegen(self.s, kunde.id)
        a.positionen.append(AngebotsPosition(sort=1, pos_nr="047", bezeichnung="WP",
                                             beschreibung="WP", menge=1,
                                             e_preis_cent=100000))
        self.s.commit()
        return a

    def pdf_text(self, a):
        pfad = pdf_export.pdf_fuer_angebot(self.s, self.s.get(Angebot, a.id))
        return pypdf.PdfReader(str(pfad)).pages[0].extract_text()

    def test_alt_text_parsen(self):
        w = anschriften.alt_text_parsen("Contracting GmbH, Lager 2, Hafenstr. 9, 47119 Duisburg")
        self.assertEqual((w["name"], w["zusatz"], w["strasse"], w["plz"], w["ort"]),
                         ("Contracting GmbH", "Lager 2", "Hafenstr. 9", "47119", "Duisburg"))
        # Bugfix 30.09.2026: nicht sicher Erkennbares bleibt Zusatz
        self.assertEqual(anschriften.alt_text_parsen("nur Text")["zusatz"], "nur Text")
        w = anschriften.alt_text_parsen("Musterweg 5, 12345 Ort, Hinterhaus")
        self.assertEqual((w["name"], w["strasse"], w["plz"], w["ort"], w["zusatz"]),
                         ("", "Musterweg 5", "12345", "Ort", "Hinterhaus"))
        w = anschriften.alt_text_parsen("Musterweg 5, D-12345 Musterstadt")
        self.assertEqual((w["strasse"], w["plz"], w["ort"]), ("Musterweg 5", "12345", "Musterstadt"))
        w = anschriften.alt_text_parsen("Lagerweg 7 47138 Duisburg")
        self.assertEqual((w["strasse"], w["plz"], w["ort"]), ("Lagerweg 7", "47138", "Duisburg"))
        w = anschriften.alt_text_parsen("bitte beim Nachbarn Müller abgeben")
        self.assertEqual((w["name"], w["strasse"], w["zusatz"]),
                         ("", "", "bitte beim Nachbarn Müller abgeben"))

    def test_standardfall_unveraendert(self):
        k = self.kunde()
        a = self.angebot(k)
        zeilen, abw = anschriften.empfaenger(a, k)
        self.assertFalse(abw)
        self.assertEqual(zeilen, ["Herr Hans Anschrift-V20", "Ausführungsweg 5", "47139 Duisburg"])
        self.assertEqual(anschriften.lieferzeile(a, k), "")
        text = self.pdf_text(a)
        self.assertNotIn("Lieferanschrift", text)
        self.assertNotIn("Ausführungsort", text)

    def test_kunden_standard_und_pdf(self):
        k = self.kunde(rechnung_name="Hausverwaltung Rhein GmbH",
                       rechnung_zusatz="z. Hd. Frau Meier",
                       rechnung_strasse="Königstr. 1", rechnung_plz="47051",
                       rechnung_ort="Duisburg",
                       liefer_name="Lager Friondo", liefer_strasse="Hafenstr. 9",
                       liefer_plz="47119", liefer_ort="Duisburg")
        a = self.angebot(k)
        self.assertEqual(a.rechnung_name, "Hausverwaltung Rhein GmbH")
        self.assertEqual(a.liefer_strasse, "Hafenstr. 9")
        text = self.pdf_text(a)
        self.assertIn("Hausverwaltung Rhein GmbH", text)
        self.assertIn("z. Hd. Frau Meier", text)
        self.assertIn("Ausführungsort: Ausführungsweg 5, 47139 Duisburg", text)
        self.assertIn("Lieferanschrift: Lager Friondo, Hafenstr. 9, 47119 Duisburg", text)
        self.assertIn("Sehr geehrter Herr Anschrift-V20,", text)   # Anrede bleibt
        # Lieferschein adressiert an die Lieferanschrift
        angebot_status_setzen(a, "Angenommen")
        self.s.commit()
        ls = self.client.get(f"/angebote/{a.id}/lieferschein.pdf")
        import io
        ls_text = pypdf.PdfReader(io.BytesIO(ls.content)).pages[0].extract_text()
        self.assertTrue(ls_text.find("Lager Friondo") < ls_text.find("L I E F E R"))

    def test_editor_nur_im_entwurf_und_version(self):
        k = self.kunde()
        a = self.angebot(k)
        seite = self.client.get(f"/angebote/{a.id}").text
        self.assertIn("Rechnungsanschrift", seite)
        self.assertIn("Lieferanschrift", seite)
        daten = {"rechnung_name": "Firma Abweich", "rechnung_zusatz": "",
                 "rechnung_strasse": "Ausführungsweg 5", "rechnung_plz": "47139",
                 "rechnung_ort": "Duisburg", "liefer_name": "Hans Anschrift-V20",
                 "liefer_zusatz": "", "liefer_strasse": "Anderer Weg 1",
                 "liefer_plz": "47051", "liefer_ort": "Duisburg"}
        self.client.post(f"/angebote/{a.id}/anschriften", data=daten)
        self.s.expire_all()
        a = self.s.get(Angebot, a.id)
        self.assertEqual(a.liefer_strasse, "Anderer Weg 1")
        zeilen, abw = anschriften.empfaenger(a, k)
        self.assertEqual(zeilen[0], "Firma Abweich")   # Name ersetzt Kundennamen
        self.assertFalse(abw)                           # Adresse gleich → kein Ausführungsort
        # versendet → gesperrt
        angebot_status_setzen(a, "Versendet")
        self.s.commit()
        antwort = self.client.post(f"/angebote/{a.id}/anschriften",
                                   data={**daten, "liefer_strasse": "Neu 2"},
                                   follow_redirects=False)
        self.assertIn("Entwurf", antwort.headers["location"].replace("+", " ")
                      .replace("%C3%BC", "ü"))
        self.s.expire_all()
        self.assertEqual(self.s.get(Angebot, a.id).liefer_strasse, "Anderer Weg 1")
        # Überarbeiten → Version übernimmt die Anschriften
        version = angebot_aufbau.neue_version(self.s, self.s.get(Angebot, a.id)) \
            if hasattr(angebot_aufbau, "neue_version") else None
        if version is None:
            self.client.post(f"/angebote/{a.id}/ueberarbeiten")
            self.s.expire_all()
            version = (self.s.query(Angebot).filter(Angebot.vorgaenger_id == a.id).first())
        self.assertIsNotNone(version)
        self.assertEqual((version.liefer_strasse, version.rechnung_name),
                         ("Anderer Weg 1", "Firma Abweich"))

    def test_vorgangsakte_standard(self):
        k = self.kunde()
        a = self.angebot(k)
        from app import vorgaenge
        vorgang = vorgaenge.vorgang_fuer_angebot(self.s, a)
        self.s.commit()
        akte = self.client.get(f"/vorgaenge/{vorgang.id}").text
        self.assertIn("Standard für neue Erfassungen/Angebote", akte)
        # gleiche Werte wie Ausführungsort → nicht gespeichert
        self.client.post(f"/vorgaenge/{vorgang.id}/anschriften", data={
            "rechnung_name": "Herr Hans Anschrift-V20", "rechnung_strasse": "Ausführungsweg 5",
            "rechnung_plz": "47139", "rechnung_ort": "Duisburg",
            "liefer_name": "Hans Hausmeister", "liefer_strasse": "Keller 1",
            "liefer_plz": "47139", "liefer_ort": "Duisburg"})
        self.s.expire_all()
        k = self.s.get(Kunde, k.id)
        self.assertEqual(k.rechnung_strasse, "")
        self.assertEqual(k.liefer_strasse, "Keller 1")
        # Vorbelegung neuer Erfassungen
        vor = anschriften.erfassung_vorbelegung(k)
        self.assertNotIn("O06", vor)
        self.assertEqual(vor["O13"], "Hans Hausmeister, Keller 1, 47139 Duisburg")
        k.rechnung_strasse, k.rechnung_plz, k.rechnung_ort = "Postfach 7", "47001", "Duisburg"
        self.assertEqual(anschriften.erfassung_vorbelegung(k)["O06"], "Nein")
        self.s.rollback()


if __name__ == "__main__":
    unittest.main()
