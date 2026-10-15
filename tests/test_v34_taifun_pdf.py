# v34 (PLAN_V21 Phase 180, Agent V): TAIFUN-Angebots-PDF per Drag & Drop – Textextraktion mit
# pypdf (app/taifun_pdf.py), Felderkennung (Nummer AN\d{6} hinter „ANGEBOT - Nr.:“, Datum der
# ersten Seite, „Gesamt-Betrag € …“ bzw. „= Endbetrag“, Sparte nur als Vorschlag), JSON-Route
# POST /angebote/extern/pdf-lesen, Dialog „Extern erledigt“ mit PDF (Eintrag + Galerie
# „Allgemein“), Ersetzen am TAIFUN-Eintrag mit Sicherheitsabfrage und „übernehmen“-Häkchen.
# Das Muster AN261737 liegt nicht im Projektordner (Kundendaten) – die Tests bauen ein
# synthetisches PDF im TAIFUN-Layout mit fpdf2; Datei ohne Textebene → „Kein Text im PDF gefunden“.
import datetime
import io
import json
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from fpdf import FPDF
from sqlalchemy import func

from app import auth, config, taifun_pdf
from app import vorgaenge as vorgaenge_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsNotiz, Benutzer, Erfassung, GalerieDatei, Kunde, Vorgang,
                        VorgangsNotiz)

TEST_EMAIL = "v34v-taifunpdf@test.local"
PRAEFIX = "V34V "


def taifun_pdf_bytes(nummer="AN261737", datum="17.09.2026", gesamt="4.315,23", endbetrag=None,
                     text="Komplettpaket Wallbox inkl. Montage", zweite_seite=True,
                     ohne_text=False) -> bytes:
    """Synthetisches PDF im TAIFUN-Layout (fpdf2, Kernschrift mit cp1252 für „€“)."""
    pdf = FPDF()
    pdf.core_fonts_encoding = "cp1252"
    pdf.add_page()
    if ohne_text:
        return bytes(pdf.output())
    pdf.set_font("Helvetica", size=10)
    zeilen = ["Friondo GmbH - Arnold-Overbeck-Str. 63-65 - 47139 Duisburg",
              f"ANGEBOT - Nr.: {nummer}", f"Datum : {datum}", "Kunden-Nr.: 10234",
              text, "Pos. Bezeichnung Menge Einheit E-Preis G-Preis",
              "001 Anschlussvorbereitung Ladestation 1,00 psl. 1.297,20 1.297,20",
              "Netto-Betrag € 2.235,70", "19,00 % USt. € 424,78", f"Gesamt-Betrag € {gesamt}"]
    if endbetrag:
        zeilen += ["- Rabatt € 100,00", f"= Endbetrag € {endbetrag}"]
    for zeile in zeilen:
        pdf.cell(0, 6, zeile, new_x="LMARGIN", new_y="NEXT")
    if zweite_seite:
        pdf.add_page()
        pdf.cell(0, 6, "Seite 2 - Datum : 01.01.2020 - Wärmepumpe Wärmepumpe Wärmepumpe",
                 new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


class Textextraktion(unittest.TestCase):
    def test_felder_aus_taifun_layout(self):
        text = taifun_pdf.text_lesen(taifun_pdf_bytes())
        self.assertIn("AN261737", text)
        self.assertIn(taifun_pdf.SEITEN_TRENNER, text)          # zwei Seiten
        felder = taifun_pdf.felder_erkennen(text)
        self.assertEqual(felder["nummer"], "AN261737")
        self.assertEqual(felder["datum"], "2026-09-17")          # Datum der ERSTEN Seite
        self.assertEqual(felder["endbetrag_cent"], 431523)
        self.assertEqual(felder["sparte"], "WB")                  # Schlagwort Wallbox (1. Seite)
        self.assertEqual(felder["hinweise"], [])
        werte = taifun_pdf.formular_werte(text)
        self.assertEqual((werte["nummer"], werte["datum"], werte["endbetrag"], werte["sparte"]),
                         ("AN261737", "2026-09-17", "4.315,23", "WB"))
        self.assertTrue(werte["text_gefunden"])
        self.assertEqual(werte["pruefen"], "aus PDF gelesen – bitte prüfen")

    def test_endbetrag_nach_rabatt_geht_vor(self):
        text = taifun_pdf.text_lesen(taifun_pdf_bytes(endbetrag="4.215,23"))
        self.assertEqual(taifun_pdf.felder_erkennen(text)["endbetrag_cent"], 421523)

    def test_datei_ohne_text_und_kein_pdf(self):
        self.assertEqual(taifun_pdf.text_lesen(taifun_pdf_bytes(ohne_text=True)), "")
        felder = taifun_pdf.felder_erkennen("")
        self.assertEqual((felder["nummer"], felder["datum"], felder["endbetrag_cent"], felder["sparte"]),
                         ("", "", None, ""))
        self.assertEqual(felder["hinweise"], [taifun_pdf.HINWEIS_KEIN_TEXT])
        werte = taifun_pdf.formular_werte("")
        self.assertFalse(werte["text_gefunden"])
        self.assertIn("Kein Text im PDF gefunden", werte["hinweis"])
        self.assertEqual(taifun_pdf.text_lesen(b"kein pdf"), "")
        self.assertEqual(taifun_pdf.text_lesen(b"%PDF-1.4 kaputt"), "")
        self.assertFalse(taifun_pdf.ist_pdf(b"hallo"))
        self.assertTrue(taifun_pdf.ist_pdf(b"%PDF-1.7 x"))
        self.assertEqual(taifun_pdf.groesse_pruefen(taifun_pdf.MAX_BYTES), "")
        self.assertIn("20 MB", taifun_pdf.groesse_pruefen(taifun_pdf.MAX_BYTES + 1))

    def test_nicht_erkanntes_bleibt_leer(self):
        text = "Irgendein Angebotstext ohne Nummer und ohne Datum\fSeite 2 Datum : 02.02.2026"
        felder = taifun_pdf.felder_erkennen(text)
        self.assertEqual((felder["nummer"], felder["datum"], felder["endbetrag_cent"]), ("", "", None))
        self.assertTrue(any("Angebotsnummer nicht erkannt" in h for h in felder["hinweise"]))
        self.assertTrue(any("Datum nicht erkannt" in h for h in felder["hinweise"]))
        # Nummer ohne Beschriftung: Vorschlag + Hinweis
        felder = taifun_pdf.felder_erkennen("Ihr Angebot AN250123 vom Datum : 1.2.2026 Gesamt-Betrag 999,99 €")
        self.assertEqual(felder["nummer"], "AN250123")
        self.assertEqual(felder["datum"], "2026-02-01")
        self.assertEqual(felder["endbetrag_cent"], 99999)
        self.assertTrue(any("ohne Beschriftung" in h for h in felder["hinweise"]))
        # Sparten-Gleichstand → leer mit Hinweis
        felder = taifun_pdf.felder_erkennen("Wallbox und Wärmepumpe")
        self.assertEqual(felder["sparte"], "")
        self.assertTrue(any("Mehrere Sparten" in h for h in felder["hinweise"]))
        self.assertEqual(taifun_pdf.betrag_in_cent("1.234,50"), 123450)
        self.assertIsNone(taifun_pdf.betrag_in_cent("12,345"))
        self.assertEqual(taifun_pdf.cent_als_text(123450), "1.234,50")
        self.assertEqual(taifun_pdf.cent_als_text(None), "")


def _aufraeumen(s):
    s.rollback()
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.query(AngebotsNotiz).filter(AngebotsNotiz.angebot_id == a.id).delete()
            if a.extern_pdf_pfad:
                Path(a.extern_pdf_pfad).unlink(missing_ok=True)
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            for g in s.query(GalerieDatei).filter_by(vorgang_id=v.id):
                (config.DATA_ORDNER / g.pfad).unlink(missing_ok=True)
                s.delete(g)
            s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == v.id).delete()
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.delete(b)
    s.commit()


class Routen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        _aufraeumen(cls.s)
        cls.kunde = Kunde(anrede="Herr", vorname="Tim", nachname=f"{PRAEFIX}Taifun",
                          strasse="Testweg 4", plz="47139", ort="Duisburg", email=TEST_EMAIL)
        cls.s.add(cls.kunde)
        cls.s.commit()
        cls.client = TestClient(app)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))

    @classmethod
    def tearDownClass(cls):
        _aufraeumen(cls.s)
        cls.s.close()

    def _datei(self, inhalt: bytes, name="AN261737.pdf", typ="application/pdf"):
        return {"pdf_datei": (name, io.BytesIO(inhalt), typ)}

    def _neuer_kunde(self):
        """Je Test ein eigener Kunde (= eigener Vorgang, eigene Galerie – die Zähler der
        Galerie wären sonst über die Tests hinweg kumuliert)."""
        k = Kunde(anrede="Herr", vorname="Tim", nachname=f"{PRAEFIX}Taifun {self._testMethodName}",
                  strasse="Testweg 4", plz="47139", ort="Duisburg", email=TEST_EMAIL)
        self.s.add(k)
        self.s.commit()
        return k

    def test_pdf_lesen_json(self):
        antwort = self.client.post("/angebote/extern/pdf-lesen", files=self._datei(taifun_pdf_bytes()))
        self.assertEqual(antwort.status_code, 200)
        daten = antwort.json()
        self.assertTrue(daten["ok"])
        self.assertEqual((daten["nummer"], daten["datum"], daten["endbetrag"], daten["sparte"]),
                         ("AN261737", "2026-09-17", "4.315,23", "WB"))
        self.assertEqual(daten["dateiname"], "AN261737.pdf")
        # Scan ohne Textebene
        daten = self.client.post("/angebote/extern/pdf-lesen",
                                 files=self._datei(taifun_pdf_bytes(ohne_text=True))).json()
        self.assertTrue(daten["ok"])
        self.assertFalse(daten["text_gefunden"])
        self.assertEqual((daten["nummer"], daten["datum"], daten["endbetrag"]), ("", "", ""))
        self.assertIn("Kein Text im PDF gefunden", daten["hinweis"])
        # kein PDF / keine Datei
        self.assertEqual(self.client.post("/angebote/extern/pdf-lesen",
                                          files=self._datei(b"nur text", "x.txt", "text/plain")).status_code, 415)
        self.assertEqual(self.client.post("/angebote/extern/pdf-lesen", data={}).status_code, 400)

    def test_pdf_lesen_rollen(self):
        s = self.s
        ad = Benutzer(id=(s.query(func.max(Benutzer.id)).scalar() or 0) + 1000,
                      name=f"{PRAEFIX}AD", rolle="aussendienst", aktiv=True,
                      email="v34v-taifun-ad@test.local", pin_hash=auth.pin_hash("4321"))
        s.add(ad)
        s.commit()
        try:
            client = TestClient(app, follow_redirects=False)
            client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(ad.id))
            antwort = client.post("/angebote/extern/pdf-lesen", files=self._datei(taifun_pdf_bytes()))
            # die Rollen-Pfadtabelle (auth.py) leitet den Außendienst schon um (303);
            # die Route selbst antwortet 403 – beides ist „kein Zugriff“
            self.assertIn(antwort.status_code, (303, 403))
            self.assertNotIn("AN261737", antwort.text)
        finally:
            s.delete(ad)
            s.commit()

    def _erfassung(self, sparte="WB"):
        e = Erfassung(kunde_id=self._neuer_kunde().id, benutzer_id=1, typ="freitext", sparte=sparte,
                      konfigurator_typ=sparte, status="In TAIFUN zu schreiben", ampel="orange",
                      freitext="Wallbox am Carport", antworten_json="{}",
                      abgesendet_am=datetime.datetime.now())
        self.s.add(e)
        self.s.commit()
        return e

    def test_dialog_zeigt_drop_zone(self):
        e = self._erfassung()
        seite = self.client.get(f"/erfassungen/{e.id}")
        self.assertEqual(seite.status_code, 200)
        self.assertIn('data-taifun-dropzone', seite.text)
        self.assertIn('data-modus="dialog"', seite.text)
        self.assertIn('enctype="multipart/form-data"', seite.text)
        self.assertIn('data-tp-feld="nummer"', seite.text)
        self.assertIn('data-tp-feld="datum"', seite.text)
        self.assertIn('data-tp-feld="endbetrag"', seite.text)
        self.assertIn('data-taifun-sparte data-sparte="WB"', seite.text)
        self.assertIn("/static/taifun_pdf.js", seite.text)
        self.assertIn("TAIFUN-Angebot (PDF) hierher ziehen", seite.text)

    def test_extern_erledigt_mit_pdf(self):
        e = self._erfassung()
        antwort = self.client.post(
            f"/erfassungen/{e.id}/extern-erledigt",
            data={"taifun_nummer": "AN261737", "endbetrag": "4.315,23", "datum": "2026-09-17"},
            files=self._datei(taifun_pdf_bytes()), follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        self.assertIn("Galerie", antwort.headers["location"].replace("%E2%80%9E", "„"))
        self.s.expire_all()
        e = self.s.get(Erfassung, e.id)
        a = self.s.get(Angebot, e.angebot_id)
        self.assertTrue(a.extern and a.extern_pdf_pfad)
        self.assertTrue(Path(a.extern_pdf_pfad).exists())
        self.assertIsNotNone(a.extern_pdf_am)
        self.assertEqual((a.taifun_nummer, a.extern_endbetrag_cent, a.konfigurator_typ),
                         ("AN261737", 431523, "WB"))
        self.assertEqual(a.status, "Versendet (extern)")
        self.assertEqual(e.status, "Erledigt (extern)")
        self.assertIn("TAIFUN-PDF hinterlegt", e.aenderungs_protokoll)
        galerie = (self.s.query(GalerieDatei)
                   .filter(GalerieDatei.vorgang_id == a.vorgang_id).all())
        self.assertEqual([(g.ordner, g.quelle, g.sparte) for g in galerie],
                         [("Allgemein", "extern_erledigt", "WB")])
        self.assertEqual(galerie[0].dateiname, "AN261737.pdf")
        self.assertTrue((config.DATA_ORDNER / galerie[0].pfad).exists())
        # TAIFUN-Seite zeigt die Drop-Zone zum Ersetzen statt des Datei-Knopfs
        seite = self.client.get(f"/angebote/{a.id}")
        self.assertEqual(seite.status_code, 200)
        self.assertIn('data-modus="eintrag"', seite.text)
        self.assertIn('data-ersetzen="1"', seite.text)
        self.assertIn("PDF ansehen", seite.text)
        self.assertIn('name="uebernehmen_nummer"', seite.text)
        self.assertNotIn('<input type="file" name="pdf_datei" accept="application/pdf">', seite.text)

    def test_extern_erledigt_ohne_pdf_und_kein_pdf(self):
        e = self._erfassung("KL")
        # kein PDF → wie v7 (ohne Galerie-Eintrag)
        antwort = self.client.post(
            f"/erfassungen/{e.id}/extern-erledigt",
            data={"taifun_nummer": "", "endbetrag": "1.000,00", "datum": "2026-10-01"},
            follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        self.s.expire_all()
        a = self.s.get(Angebot, self.s.get(Erfassung, e.id).angebot_id)
        self.assertEqual(a.extern_pdf_pfad, "")
        self.assertEqual(self.s.query(GalerieDatei).filter_by(vorgang_id=a.vorgang_id).count(), 0)
        # Nicht-PDF wird abgewiesen, Erfassung bleibt offen
        e2 = self._erfassung("PV")
        antwort = self.client.post(
            f"/erfassungen/{e2.id}/extern-erledigt",
            data={"taifun_nummer": "AN1", "endbetrag": "1.000,00", "datum": "2026-10-01"},
            files=self._datei(b"kein pdf", "x.pdf"), follow_redirects=False)
        self.assertIn("kein+PDF", antwort.headers["location"])
        self.s.expire_all()
        self.assertIsNone(self.s.get(Erfassung, e2.id).angebot_id)

    def _taifun_eintrag(self):
        a = Angebot(nummer="EXT-V34V-PDF", kunde_id=self._neuer_kunde().id, extern=True,
                    status="Versendet (extern)", datum=datetime.datetime(2026, 9, 1),
                    konfigurator_typ="WB", extern_endbetrag_cent=100000, taifun_nummer="")
        self.s.add(a)
        self.s.flush()
        a.nummer = f"EXT-V34V-{a.id}"
        vorgaenge_modul.vorgang_fuer_angebot(self.s, a)
        self.s.commit()
        return a

    def test_eintrag_pdf_ersetzen_mit_uebernahme(self):
        a = self._taifun_eintrag()
        # 1. Upload ohne vorhandenes PDF: keine Bestätigung nötig, keine Übernahme gewählt
        antwort = self.client.post(f"/angebote/{a.id}/taifun-pdf",
                                   data={"zurueck": f"/vorgaenge/{a.vorgang_id}#angebot-{a.id}"},
                                   files=self._datei(taifun_pdf_bytes()), follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        ziel = antwort.headers["location"]
        self.assertTrue(ziel.startswith(f"/vorgaenge/{a.vorgang_id}?meldung="), ziel)
        self.assertTrue(ziel.endswith(f"#angebot-{a.id}"), ziel)
        self.s.expire_all()
        a = self.s.get(Angebot, a.id)
        self.assertTrue(a.extern_pdf_pfad and Path(a.extern_pdf_pfad).exists())
        self.assertEqual((a.taifun_nummer, a.extern_endbetrag_cent), ("", 100000))   # nichts übernommen
        self.assertEqual(self.s.query(GalerieDatei).filter_by(vorgang_id=a.vorgang_id).count(), 1)
        # 2. erneut ohne Bestätigung → abgewiesen (JSON 409), nichts geändert
        antwort = self.client.post(f"/angebote/{a.id}/taifun-pdf",
                                   files=self._datei(taifun_pdf_bytes(nummer="AN261738")),
                                   headers={"Accept": "application/json"})
        self.assertEqual(antwort.status_code, 409)
        self.assertFalse(antwort.json()["ok"])
        self.assertIn("bestätigen", antwort.json()["meldung"])
        # 3. mit Bestätigung + Häkchen je Feld → Werte aus dem NEUEN PDF
        antwort = self.client.post(
            f"/angebote/{a.id}/taifun-pdf",
            data={"bestaetigt": "1", "uebernehmen_nummer": "1", "uebernehmen_datum": "1",
                  "uebernehmen_endbetrag": "1"},
            files=self._datei(taifun_pdf_bytes(nummer="AN261738", datum="20.09.2026",
                                               gesamt="5.000,00", endbetrag="4.900,00")),
            headers={"Accept": "application/json"})
        self.assertEqual(antwort.status_code, 200, antwort.text)
        daten = antwort.json()
        self.assertTrue(daten["ok"])
        self.assertIn("PDF ersetzt", daten["meldung"])
        self.assertIn("Nummer AN261738", daten["meldung"])
        self.s.expire_all()
        a = self.s.get(Angebot, a.id)
        self.assertEqual(a.taifun_nummer, "AN261738")
        self.assertEqual(a.datum.strftime("%d.%m.%Y"), "20.09.2026")
        self.assertEqual(a.extern_endbetrag_cent, 490000)
        notizen = [n.text for n in self.s.query(AngebotsNotiz).filter_by(angebot_id=a.id)]
        self.assertTrue(any("TAIFUN-PDF ersetzt" in t and "AN261738" in t for t in notizen), notizen)
        self.assertEqual(self.s.query(GalerieDatei).filter_by(vorgang_id=a.vorgang_id).count(), 2)
        # 4. Häkchen gesetzt, aber im PDF nicht erkennbar → unverändert + Hinweis
        antwort = self.client.post(
            f"/angebote/{a.id}/taifun-pdf",
            data={"bestaetigt": "1", "uebernehmen_nummer": "1"},
            files=self._datei(taifun_pdf_bytes(ohne_text=True)),
            headers={"Accept": "application/json"})
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Nicht im PDF erkannt (unverändert): Nummer", antwort.json()["meldung"])
        self.s.expire_all()
        self.assertEqual(self.s.get(Angebot, a.id).taifun_nummer, "AN261738")
        # 5. kein PDF → 415 (JSON) bzw. Meldung
        antwort = self.client.post(f"/angebote/{a.id}/taifun-pdf", data={"bestaetigt": "1"},
                                   files=self._datei(b"kein pdf"), headers={"Accept": "application/json"})
        self.assertEqual(antwort.status_code, 415)
        # Angebotsliste und Akte zeigen die Drop-Zone am TAIFUN-Eintrag
        liste = self.client.get("/angebote?q=EXT-V34V")
        self.assertEqual(liste.status_code, 200)
        self.assertIn(f'action="/angebote/{a.id}/taifun-pdf"', liste.text)
        self.assertIn('data-modus="eintrag"', liste.text)
        akte = self.client.get(f"/vorgaenge/{a.vorgang_id}")
        self.assertIn(f'action="/angebote/{a.id}/taifun-pdf"', akte.text)


class UploadRegel(unittest.TestCase):
    """Die neuen Upload-Routen lesen das Formular vor dem ersten Datenbankzugriff
    (Wächter tests/test_v33_fundament.py::UploadRoutenOhneSchreibsperre – hier als Vorprüfung)."""

    def test_formular_vor_sitzung(self):
        quelle = Path(__file__).resolve().parents[1] / "app" / "routers" / "erfassungsliste.py"
        text = quelle.read_text(encoding="utf-8")
        start = text.index("def extern_erledigt(")
        rumpf = text[start:text.index("\n@router", start)]
        self.assertLess(rumpf.index("anfrage.formular(request)"), rumpf.index("session.get("))
        quelle = Path(__file__).resolve().parents[1] / "app" / "routers" / "taifun_pdf.py"
        text = quelle.read_text(encoding="utf-8")
        self.assertNotIn("Depends(get_session)", text)     # ganz ohne Sitzung


if __name__ == "__main__":
    unittest.main()
