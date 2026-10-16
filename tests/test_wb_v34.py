# Tests PLAN_V21 Phase 179 (v34, Agent W – Wallbox-Konfigurator, Stand Nachtrag + Ergänzung
# 15.10.2026): Kontrollfälle A–G über die ECHTEN Wege – Erfassung per Route anlegen
# (/erfassung/sparten-start → Weiche), Bogen hinterlegen, absenden (grün, Validierung), Angebot
# erzeugen (Route /erfassungen/<id>/angebot-erzeugen bzw. angebot_aufbau.angebot_anlegen),
# Positionen/Preise/Gruppen/Summen prüfen, PDF (Vortext, Komplettpaket aus der Excel-Textzeile,
# Vollmacht immer, kein Nachtext A/KfW/Wirtschaftlichkeit, keine Auslegungs-Position),
# Lieferschein, Protokoll-PDF (Seite „Auslegung“), Außendienst-Sicht ohne EK/DB, Parametrierung.
# Läuft gegen die Datenbank des Testaufrufs (Muster tests/test_kl_v24.py); die WB-Artikel kommen
# IMMER aus der Fixture tests/fixtures/wallbox/ (VK wie die Zulieferung, EK erfunden), Testkunde
# mit eigener E-Mail, Aufräumen am Ende.
import io
import json
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, angebotsprofile, anhaenge, auth, import_wallbox, pdf_export
from app import konfigurator as engine
from app import logik as logik_modul
from app import wb_auslegung
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, Artikel, Benutzer, Erfassung, Kunde, Textblock, Vorgang,
                        angebot_status_setzen, einstellung_setzen)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "wallbox"
TEST_EMAIL = "wb-v34@test.local"
AD_NAME = "V34W Aussendienst"
WB310 = "Mennekes AMTRON 4You 310 – 11 kW, 7,5 m Ladekabel"
WB560 = "Mennekes AMTRON 4You 560 – 11 kW, 7,5 m Ladekabel, MID-Zähler, App, OCPP"
GRUPPEN = ["Wallbox", "Installation und Anschluss", "Netzanmeldung"]
WB_NUMMERN = [f"WB{n:03d}" for n in range(1, 9)]
WB_FREITEXT_ALT = 10   # bestehende WB-Freitext-Erfassung der Dev-/Server-Kopie (Fall F), falls vorhanden
KOMPLETTPAKET_SATZ = "Die Zukunft der Energie beginnt bei Ihnen zuhause und wir begleiten Sie dabei."
AKTIONEN_ANZAHL = 13


def bogen(wallbox=WB310, leitung=10, erdarbeiten="Nein", erd_m="", montage="Wandmontage",
          durchbrueche=2, bemerkung="", s01="warm") -> dict:
    a = {"WB01": wallbox, "WB02": leitung, "WB03": erdarbeiten, "WB05": montage,
         "WB07": durchbrueche, "WB08": bemerkung, "S01": s01, "S02": ""}
    if erdarbeiten == "Ja":
        a["WB04"] = erd_m
    return a


FALL_B = bogen(WB560, 25, "Ja", 8, "Säule")            # 5.435,85 / 1.032,81 / 6.468,66
FALL_B2 = bogen(WB560, 25, "Ja", 8, "Säule", 4)        # 5.773,85 / 1.097,03 / 6.870,88
AUSLEGUNG_A = ("Wallbox: AMTRON 4You 310\n"
               "Leitungsverlegung gesamt: 10 m – bis 10 m enthalten, keine Mehrlänge\n"
               "Erdarbeiten: keine\nMontage: Wandmontage\n"
               "Durchbrüche: 2 (in der Anschlussvorbereitung enthalten)")
AUSLEGUNG_B = ("Wallbox: AMTRON 4You 560\n"
               "Leitungsverlegung gesamt: 25 m, davon 10 m enthalten, Mehrlänge 15 m\n"
               "Erdarbeiten: 8 m\nMontage: Säule (Fundament und Standsäule)\n"
               "Durchbrüche: 2 (in der Anschlussvorbereitung enthalten)")
AUSLEGUNG_B2 = AUSLEGUNG_B.rsplit("\n", 1)[0] + \
    "\nDurchbrüche: 4 (2 in der Anschlussvorbereitung enthalten, 2 zusätzlich)"


def pdf_text_aus_bytes(daten: bytes) -> str:
    import pypdf
    return "\n".join(s.extract_text() for s in pypdf.PdfReader(io.BytesIO(daten)).pages)


def mengen(positionen) -> dict:
    ergebnis: dict = {}
    for p in positionen:
        ergebnis[p.pos_nr] = ergebnis.get(p.pos_nr, 0) + p.menge
    return ergebnis


def aufraeumen(s):
    from app.models import GalerieDatei
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(GalerieDatei).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name == AD_NAME):
        s.delete(b)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        # immer der Fixture-Stand (VK = Zulieferung, EK erfunden) – auch wenn vorher die echte
        # Zulieferung importiert wurde (Abnahme-PDFs)
        import_wallbox.import_ausfuehren(cls.s, FIXTURES)
        komplettpaket = import_wallbox.komplettpaket_text(FIXTURES)
        angebotsprofile.seed_wb(cls.s, komplettpaket)
        vortext = cls.s.query(Textblock).filter_by(art="vortext", name="Friondo WB Standard").first()
        if vortext is not None and "## Komplettpaket Wallbox inkl. Montage" not in vortext.text:
            vortext.text = angebotsprofile.wb_vortext(komplettpaket)   # Altstand vor dem Nachtrag
        cls.s.commit()
        cls.logik_voll, cls.bericht = logik_modul.neu_einlesen(cls.s)
        cls.logik = logik_modul.logik_fuer_sparte(cls.logik_voll, "WB")
        aufraeumen(cls.s)
        cls.kunde = Kunde(anrede="Frau", vorname="Wanda", nachname="WB-Test v34",
                          strasse="Teststr. 7", plz="47139", ort="Duisburg", email=TEST_EMAIL,
                          telefon="0203 000000")
        cls.s.add(cls.kunde)
        cls.ad = Benutzer(name=AD_NAME, rolle="aussendienst", aktiv=True,
                          email="v34w-ad@test.local", pin_hash=auth.pin_hash("4321"))
        cls.s.add(cls.ad)
        cls.s.commit()
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    # -- echte Wege ---------------------------------------------------------------
    def erfassung_anlegen(self, antworten: dict | None, benutzer_id: int | None = None) -> Erfassung:
        """Erfassung über die Sparten-Startseite anlegen (wie der Außendienst) – der
        Sparten-Start leitet WB auf die Weiche (nicht mehr direkt in den Freitext)."""
        r = self.client.post("/erfassung/sparten-start",
                             data={"kunde_id": str(self.kunde.id), "sparte_WB": "on"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].endswith("/weiche"), r.headers["location"])
        self.s.expire_all()
        e = (self.s.query(Erfassung)
             .filter(Erfassung.kunde_id == self.kunde.id, Erfassung.sparte == "WB")
             .order_by(Erfassung.id.desc()).first())
        self.assertIsNotNone(e)
        self.assertEqual((e.konfigurator_typ, e.status, e.typ), ("WB", "Entwurf", "katalog"))
        if antworten is not None:
            e.antworten_json = json.dumps(antworten, ensure_ascii=False)
        if benutzer_id is not None:
            e.benutzer_id = benutzer_id
        self.s.commit()
        return e

    def absenden(self, e: Erfassung):
        r = self.client.post(f"/erfassung/{e.id}/absenden", follow_redirects=False)
        self.s.refresh(e)
        return r

    def angebot_erzeugen(self, e: Erfassung) -> Angebot:
        r = self.client.get(f"/erfassungen/{e.id}/angebot-erzeugen", follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.headers.get("location"))
        self.assertTrue(r.headers["location"].startswith("/angebote/"), r.headers["location"])
        self.s.refresh(e)
        self.assertIsNotNone(e.angebot_id)
        return self.s.get(Angebot, e.angebot_id)

    def angebot_direkt(self, antworten: dict) -> Angebot:
        return angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, antworten=antworten,
                                              logik=self.logik, sparte="WB")

    def pdf_text(self, angebot: Angebot) -> str:
        import pypdf
        pfad = pdf_export.pdf_fuer_angebot(self.s, angebot)
        text = "\n".join(s.extract_text() for s in pypdf.PdfReader(str(pfad)).pages)
        pfad.unlink(missing_ok=True)
        return text

    def pruefe_summen(self, angebot: Angebot, netto: int, ust: int, gesamt: int):
        su = angebot.summen()
        self.assertEqual(su["netto"], netto)
        # USt: Agent E stellt summen() auf kaufmännische Rundung um (R7) – die Plan-Werte
        # sind kaufmännisch gerechnet und beim Abschneiden identisch (± 0,01 € Toleranz)
        self.assertAlmostEqual(su["ust"], ust, delta=1)
        self.assertAlmostEqual(su["brutto"], gesamt, delta=1)
        self.assertEqual(su["endbetrag"], su["brutto"])


# --- Voraussetzungen ----------------------------------------------------------------

class Voraussetzungen(Basis):
    def test_logik_gruen_und_wb_sicht(self):
        self.assertTrue(self.bericht.ok, self.bericht.fehler)
        self.assertFalse(self.logik_voll.wb_artikel_fehlen)
        self.assertEqual(self.logik.sparte, "WB")
        self.assertEqual(len(self.logik.wb_aktionen), AKTIONEN_ANZAHL)
        self.assertEqual([b.ueberschrift for b in self.logik.wb_bloecke], GRUPPEN)
        for antworten in (bogen(), FALL_B, FALL_B2, bogen(WB560, 8), bogen(WB310, "12,4")):
            self.assertIsNone(engine.naechste_pflichtfrage(self.logik, antworten))
        self.assertIn(WB310, self.logik.fragen["WB01"].antworten)
        self.assertIn(WB560, self.logik.fragen["WB01"].antworten)

    def test_wb_artikel_importiert(self):
        wb = {a.pos_nr: a for a in self.s.query(Artikel)
              .filter(Artikel.quelle == import_wallbox.QUELLE_WB, Artikel.aktiv.is_(True))}
        self.assertEqual(sorted(wb), WB_NUMMERN)
        self.assertEqual({nr: wb[nr].e_preis_cent for nr in WB_NUMMERN},
                         {"WB001": 93850, "WB002": 139055, "WB003": 129720, "WB004": 0, "WB005": 4934,
                          "WB006": 12350, "WB007": 102000, "WB008": 16900})
        self.assertEqual((wb["WB007"].einheit, wb["WB008"].einheit), ("psl.", "Stück"))
        self.assertTrue(wb_auslegung.artikel_vorhanden(self.s))

    def test_textbloecke_vorhanden(self):
        namen = {(b.art, b.name) for b in self.s.query(Textblock)}
        for name in ("Friondo WB Standard", "Friondo WB Enni", "Friondo WB SWD", "Friondo WB Sparkasse DU"):
            self.assertIn(("nachtext", name), namen)
        self.assertIn(("vortext", "Friondo WB Standard"), namen)
        self.assertEqual(angebotsprofile.seed_wb(self.s, import_wallbox.komplettpaket_text(FIXTURES)), [])
        vortext = angebotsprofile.WB_VORTEXT                     # Entwurf (ohne Excel)
        self.assertTrue(vortext.startswith("## Ihre individuelle Wallbox zum Festpreis"))
        self.assertIn("## Komplettpaket Wallbox inkl. Montage", vortext)
        self.assertIn("{briefanrede}", vortext)
        self.assertIn("* Fördermittel-Check & Unterstützung – Wir prüfen für Sie mögliche Zuschüsse", vortext)
        self.assertTrue(vortext.endswith(angebotsprofile.WB_KOMPLETTPAKET_TEXT))
        # Textzeile der Excel: erste Zeile = Überschrift, Rest = Absatz
        aus_excel = angebotsprofile.wb_vortext("Komplettpaket Wallbox inkl. Montage\nZeile A\nZeile B")
        self.assertTrue(aus_excel.endswith("## Komplettpaket Wallbox inkl. Montage\n\nZeile A\nZeile B"))
        self.assertEqual(angebotsprofile.wb_vortext(""), vortext)
        block = self.s.query(Textblock).filter_by(art="vortext", name="Friondo WB Standard").first()
        self.assertIn("## Komplettpaket Wallbox inkl. Montage", block.text)
        self.assertIn(KOMPLETTPAKET_SATZ, block.text)          # wörtlich aus der Excel-Textzeile
        self.assertNotIn("?", block.text.split("## Komplettpaket")[1])
        nachtext = angebotsprofile.WB_STANDARD_NACHTEXT
        self.assertIn("{zahlungsbedingungen}", nachtext)
        self.assertIn("Rücktrittsrecht im Zusammenhang mit Technischer Feinplanung", nachtext)
        self.assertNotIn("Zahlungsoptionen", nachtext)
        self.assertNotIn("KfW", nachtext)
        self.assertNotIn("[WIRTSCHAFTLICHKEIT]", nachtext)
        self.assertNotIn("Kältetechnik", nachtext)


# --- Fall A: 310, 10 m, keine Erdarbeiten, Wandmontage, 2 Durchbrüche ------------------------

class FallA(Basis):
    ERWARTET = [("WB001", 1.0, 93850), ("WB003", 1.0, 129720), ("WB004", 1.0, 0)]

    def pruefe_angebot(self, angebot: Angebot):
        self.assertEqual((angebot.konfigurator_typ, angebot.ust_satz, angebot.kfw_json),
                         ("WB", 19.0, "{}"))
        pos = angebot.positionen
        self.assertEqual([(p.pos_nr, p.menge, p.e_preis_cent) for p in pos], self.ERWARTET)
        self.assertEqual([p.gruppe for p in pos], GRUPPEN)
        self.assertEqual([p.block_nr for p in pos], [1, 2, 3])
        self.assertFalse(any(p.ep_flag for p in pos))
        self.assertFalse(any(angebot_aufbau.ist_auslegungs_position(p) for p in pos))   # keine Auslegungszeile
        self.pruefe_summen(angebot, 223570, 42478, 266048)
        self.assertEqual(angebot.ust_bezeichnung, "19,00 % USt.")
        wb = json.loads(angebot.wb_json)
        self.assertEqual((wb["wallbox"], wb["wallbox_ref"], wb["leitung_m"], wb["mehrlaenge_m"],
                          wb["erdarbeiten"], wb["montage"], wb["durchbrueche"], wb["durchbrueche_zusatz"]),
                         ("AMTRON 4You 310", "WB001", 10.0, 0, False, "Wandmontage", 2, 0))
        self.assertEqual(angebot.auslegung_text, AUSLEGUNG_A)
        # kein Friondo Fit for Future, keine WP-Artikel
        self.assertFalse({"014", "015", "016", "017", "162"} & {p.pos_nr for p in pos})
        self.assertEqual(angebot.deckungsbeitrag()["db"], 223570 - 61120 - 41200)

    def test_fall_a_erfassung_weiche_absenden_angebot(self):
        e = self.erfassung_anlegen(None)
        # Weiche zeigt Katalog | Freitext (keine Umleitung in den Freitext mehr)
        r = self.client.get(f"/erfassung/{e.id}/weiche", follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Erfassungsbogen starten", r.text)
        self.assertIn("Freitext-Erfassung", r.text)
        # Seite 0: WB02 vorbelegt 10, WB07 vorbelegt 2, WB03 = Nein, WB05 = Wandmontage,
        # WB01 ohne Vorbelegung, WB04 vorhanden (per „Anzeigen wenn“ verborgen)
        r = self.client.get(f"/erfassung/{e.id}/seite/0")
        self.assertEqual(r.status_code, 200)
        self.assertIn('name="f_WB02"', r.text)
        self.assertIn('inputmode="decimal"', r.text)
        self.assertIn('value="10"', r.text)
        self.assertIn('placeholder="z. B. 12,5"', r.text)
        self.assertIn('name="f_WB04"', r.text)
        self.assertIn('name="f_WB07"', r.text)
        self.assertIn('value="2"', r.text)
        self.assertIn('placeholder="z. B. 2"', r.text)
        self.assertRegex(r.text, r'name="f_WB03" value="Nein"\s+checked')
        self.assertRegex(r.text, r'name="f_WB05" value="Wandmontage"\s+checked')
        self.assertNotRegex(r.text, r'name="f_WB01" value="[^"]*"\s+checked')
        # Bogen hinterlegen, Prüfseite, absenden → grün, „Neu“
        e.antworten_json = json.dumps(bogen(), ensure_ascii=False)
        self.s.commit()
        r = self.client.get(f"/erfassung/{e.id}/pruefen")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Auslegung", r.text)
        self.assertIn("keine Mehrlänge", r.text)
        self.assertIn("Durchbrüche", r.text)
        self.assertIn("Wandmontage", r.text)
        r = self.absenden(e)
        self.assertEqual(r.status_code, 200)
        self.assertEqual((e.ampel, e.status, e.gruende_text), ("gruen", "Neu", ""))
        self.assertEqual(engine.ampel_gruende(self.logik, bogen()), [])
        # Innendienst: Detail mit „Angebot erzeugen“ und „Erneut prüfen“, dann Angebot
        r = self.client.get(f"/erfassungen/{e.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Angebot erzeugen", r.text)
        self.assertIn("erneut-pruefen", r.text)
        angebot = self.angebot_erzeugen(e)
        self.pruefe_angebot(angebot)
        self.assertEqual((e.angebot_id, e.status), (angebot.id, "In Bearbeitung"))
        r = self.client.get(f"/angebote/{angebot.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("19,00 % USt.", r.text)
        for gruppe in GRUPPEN:
            self.assertIn(gruppe, r.text)
        self.assertLess(self.client.get(f"/erfassung/{e.id}/pruefen").status_code, 500)

    def test_fall_a_angebot_anlegen_direkt(self):
        self.pruefe_angebot(self.angebot_direkt(bogen()))

    def test_listen_akte_statistik_mit_wb_angebot(self):
        """Sparten-Badge WB unverändert: Angebotsliste, Erfassungsliste, Vorgangsakte und
        Statistik rendern mit einem WB-Angebot (kein Absturz, Nummer/Badge sichtbar)."""
        e = self.erfassung_anlegen(FALL_B)
        self.absenden(e)
        angebot = self.angebot_erzeugen(e)
        for pfad in ("/angebote", "/angebote?sparte=WB", "/erfassungen", "/statistik",
                     f"/vorgaenge/zu-angebot/{angebot.id}"):
            r = self.client.get(pfad, follow_redirects=True)
            self.assertEqual(r.status_code, 200, pfad)
        r = self.client.get("/angebote?sparte=WB")
        self.assertIn(angebot.nummer, r.text)
        r = self.client.get(f"/vorgaenge/zu-angebot/{angebot.id}", follow_redirects=True)
        self.assertIn(angebot.nummer, r.text)
        self.assertIn("Wallbox", r.text)

    def test_fall_a_pdf(self):
        angebot = self.angebot_direkt(bogen())
        text = self.pdf_text(angebot)
        # v36 (PLAN_V22 Phase 190): Layout v3 trägt den Deckblatt-Titel „Ihr individuelles Wallbox-
        # Angebot zum Festpreis“ (pdf_kontext.SPARTEN) statt der Vortext-Überschrift des TAIFUN-
        # Musters; fpdf2 (Rückfall) druckt weiter die Vortext-Überschrift – beide gelten
        flach_titel = " ".join(text.replace("-\n", "-").split())
        self.assertTrue("Ihre individuelle Wallbox zum Festpreis" in text
                        or "Ihr individuelles Wallbox-Angebot zum Festpreis" in flach_titel,
                        "Wallbox-Titel fehlt")
        flach = " ".join(text.split())
        self.assertIn("Komplettpaket Wallbox inkl. Montage", text)
        # aus der Excel-Textzeile (v36: der Browser-Druck bricht den Satz um – ohne Zeilenumbruch prüfen)
        self.assertIn("Die Zukunft der Energie beginnt bei Ihnen zuhause", flach)
        self.assertIn("Sehr geehrte Frau WB-Test v34", text)
        for gruppe in GRUPPEN:
            self.assertIn(gruppe, text)
        self.assertIn("19,00 % USt.", text)
        self.assertIn("2.235,70", text)
        self.assertIn("424,78", text)
        self.assertIn("2.660,48", text)
        # v36 (PLAN_V22 Phase 190): der Nachtext-Seitentitel „# Installationsvoraussetzungen“ entfällt im
        # Layout v3 – die Absätze stehen auf der Seite „Vertragsbedingungen“ der Design-Vorlage; fpdf2 druckt ihn
        self.assertTrue("Installationsvoraussetzungen" in text or "Vertragsbedingungen" in text,
                        "Seite mit den Vertragsbedingungen fehlt")
        self.assertIn("Rücktrittsrecht", text)
        self.assertIn("Vollmacht zur Beauftragung der SpotmyEnergy GmbH", text)   # Nachtext D immer
        self.assertIn("Voraussichtlicher Ausführungszeitraum", text)
        # Fall A ohne Säule/Durchbruch-Zusatz: diese Positionen fehlen
        self.assertNotIn("Fundament und Standsäule", text)
        self.assertNotIn("Bohrung/Durchbrüche", text)
        # kein Nachtext A, kein KfW-/Förderblock (der Vortext nennt wörtlich den
        # „Fördermittel-Check“ – deshalb die konkreten Block-Begriffe), keine Wirtschaftlichkeit
        # v36 (PLAN_V22 Phase 189/193): im Layout v3 trägt die Auftragsseite für alle Sparten des Profils
        # Standard – auch WB (`cloover_sparten`, Design-Vorlage angebot-wallbox.html) – die Karte
        # „FINANZIERUNG MIT CLOOVER“; seit Phase 193 hat „Friondo WB Standard“ auch im fpdf2-Rückfall einen
        # Nachtext A „Ihre Zahlungsoptionen bei Friondo“ mit dem Platzhalter [CLOOVER] (WB_STANDARD_NACHTEXT_V36)
        # – „Zahlungsoptionen“/„Cloover“ sind deshalb in keiner Engine mehr verboten (v34: kein Nachtext A)
        verboten_liste = ["KfW", "Förderbetrag", "Förderfähige",
                          "Eigenanteil", "Wirtschaftlichkeit", "So rechnet sich", "Beispielrate",
                          "Aufschiebende Bedingung", "Auslegung der", "Kältetechnik",
                          "{zahlungsbedingungen}", "Wärmepumpen-Angebot", "Grundförderung", "_x000D_"]
        for verboten in verboten_liste:
            self.assertNotIn(verboten, text, verboten)
        # Vollmacht-Anker: anhaenge + angebotsprofile (pdf_export._mit_vollmacht nutzt beide)
        self.assertTrue(anhaenge.vollmacht_erforderlich(angebot))
        self.assertTrue(angebotsprofile.vollmacht_erlaubt(self.s, angebot))
        self.assertTrue(pdf_export._mit_vollmacht(self.s, angebot))
        # Anhänge-Regel „wenn Sparte = WB“: Datenblatt (fehlt noch) + Unternehmenspräsentation
        dateien = {a.datei: a for a in anhaenge.fuer_angebot(self.logik_voll, angebot, "Standard")}
        self.assertIn("Mennekes AMTRON 4You Datenblatt.pdf", dateien)
        self.assertIn("Friondo Unternehmenspräsentation.pdf", dateien)
        self.assertNotIn("Bosch Climate 3200i.pdf", dateien)
        self.assertIn("Mennekes AMTRON 4You Datenblatt.pdf", anhaenge.fehlende_dateien(self.logik_voll))

    def test_fall_a_lieferschein_und_protokoll(self):
        angebot = self.angebot_direkt(bogen())
        angebot_status_setzen(angebot, "Angenommen")
        self.s.commit()
        r = self.client.get(f"/angebote/{angebot.id}/lieferschein.pdf")
        self.assertEqual(r.status_code, 200)
        text = pdf_text_aus_bytes(r.content)
        self.assertIn("L I E F E R S C H E I N", text)
        self.assertIn("Wallbox", text)
        self.assertIn("Anschlussvorbereitung", text)
        for verboten in ("€", "Netto", "Summe", "Rabatt"):
            self.assertNotIn(verboten, text, verboten)
        # Protokoll-PDF der Erfassung (Fall B2): Seite „Auslegung“ mit allen fünf Zeilen
        e = self.erfassung_anlegen(FALL_B2)
        self.absenden(e)
        r = self.client.get(f"/erfassungen/{e.id}/protokoll.pdf")
        self.assertEqual(r.status_code, 200)
        ptext = pdf_text_aus_bytes(r.content)
        for erwartet in ("Auslegung", "AMTRON 4You 560", "Mehrlänge 15 m", "Erdarbeiten", "8 m",
                         "Säule (Fundament und Standsäule)", "Durchbrüche", "2 zusätzlich"):
            self.assertIn(erwartet, ptext, erwartet)

    def test_versionen_und_kopien_behalten_wb_json(self):
        angebot = self.angebot_direkt(bogen())
        angebot_status_setzen(angebot, "Versendet")
        self.s.commit()
        version = angebot_aufbau.version_erzeugen(self.s, angebot)
        self.assertEqual((version.konfigurator_typ, version.ust_satz), ("WB", 19.0))
        self.assertEqual(json.loads(version.wb_json)["wallbox"], "AMTRON 4You 310")
        self.assertEqual(version.auslegung_text, angebot.auslegung_text)
        self.assertEqual(version.summen()["netto"], 223570)
        self.s.commit()
        r = self.client.post(f"/angebote/{version.id}/duplizieren", follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.headers.get("location"))
        self.s.expire_all()
        kopie_id = int(r.headers["location"].rstrip("/").split("/")[2].split("?")[0])
        kopie = self.s.get(Angebot, kopie_id)
        self.assertEqual(json.loads(kopie.wb_json)["wallbox_ref"], "WB001")
        self.assertEqual(kopie.summen()["netto"], 223570)


# --- Fall B / B2: 560, 25 m, Erdarbeiten 8 m, Säule (+ 4 Durchbrüche) -----------------------

class FallB(Basis):
    def test_fall_b(self):
        e = self.erfassung_anlegen(FALL_B)
        self.absenden(e)
        self.assertEqual((e.ampel, e.status), ("gruen", "Neu"))
        angebot = self.angebot_erzeugen(e)
        pos = angebot.positionen
        self.assertEqual([(p.pos_nr, p.menge, p.e_preis_cent) for p in pos],
                         [("WB002", 1.0, 139055), ("WB003", 1.0, 129720), ("WB005", 15.0, 4934),
                          ("WB006", 8.0, 12350), ("WB007", 1.0, 102000), ("WB004", 1.0, 0)])
        self.assertEqual(pos[2].gesamt_cent, 74010)      # 15 × 49,34
        self.assertEqual(pos[3].gesamt_cent, 98800)      # 8 × 123,50
        self.assertEqual([p.gruppe for p in pos],
                         ["Wallbox"] + ["Installation und Anschluss"] * 4 + ["Netzanmeldung"])
        self.assertEqual([p.einheit for p in pos], ["Stück", "psl.", "m", "m", "psl.", "psl."])
        self.pruefe_summen(angebot, 543585, 103281, 646866)
        wb = json.loads(angebot.wb_json)
        self.assertEqual((wb["wallbox"], wb["mehrlaenge_m"], wb["leitung_m"], wb["erdarbeiten_m"],
                          wb["montage"]), ("AMTRON 4You 560", 15, 25.0, 8, "Säule"))
        self.assertEqual(angebot.auslegung_text, AUSLEGUNG_B)
        text = self.pdf_text(angebot)
        for erwartet in ("5.435,85", "1.032,81", "6.468,66", "Vollmacht", "Fundament und Standsäule",
                         "Erdarbeiten"):
            self.assertIn(erwartet, text, erwartet)
        self.assertNotIn("Auslegung", text)
        self.assertNotIn("Bohrung/Durchbrüche", text)

    def test_fall_b2_durchbrueche(self):
        e = self.erfassung_anlegen(FALL_B2)
        r = self.client.get(f"/erfassung/{e.id}/pruefen")
        self.assertIn("2 zusätzlich", r.text)
        self.absenden(e)
        self.assertEqual((e.ampel, e.status), ("gruen", "Neu"))
        angebot = self.angebot_erzeugen(e)
        pos = angebot.positionen
        self.assertEqual([(p.pos_nr, p.menge, p.e_preis_cent) for p in pos],
                         [("WB002", 1.0, 139055), ("WB003", 1.0, 129720), ("WB008", 2.0, 16900),
                          ("WB005", 15.0, 4934), ("WB006", 8.0, 12350), ("WB007", 1.0, 102000),
                          ("WB004", 1.0, 0)])
        self.assertEqual(pos[2].gesamt_cent, 33800)      # 2 × 169,00
        self.assertEqual(pos[2].gruppe, "Installation und Anschluss")
        self.pruefe_summen(angebot, 577385, 109703, 687088)
        wb = json.loads(angebot.wb_json)
        self.assertEqual((wb["durchbrueche"], wb["durchbrueche_inklusive"], wb["durchbrueche_zusatz"]), (4, 2, 2))
        self.assertEqual(angebot.auslegung_text, AUSLEGUNG_B2)
        text = self.pdf_text(angebot)
        for erwartet in ("5.773,85", "1.097,03", "6.870,88", "Bohrung/Durchbrüche"):
            self.assertIn(erwartet, text, erwartet)


# --- Fall C/D: 560 + 8 m, 310 + 12,4 m; Erdarbeiten-Rundung ---------------------------------

class FallCD(Basis):
    def test_fall_c_ohne_meterpositionen(self):
        angebot = self.angebot_direkt(bogen(WB560, 8))
        self.assertEqual([p.pos_nr for p in angebot.positionen], ["WB002", "WB003", "WB004"])
        self.pruefe_summen(angebot, 268775, 51067, 319842)
        self.assertIn("keine Mehrlänge", angebot.auslegung_text)

    def test_fall_d_kaufmaennisch(self):
        e = self.erfassung_anlegen(bogen(WB310, "12,4"))
        self.absenden(e)
        self.assertEqual(e.ampel, "gruen")
        angebot = self.angebot_erzeugen(e)
        self.assertEqual(mengen(angebot.positionen),
                         {"WB001": 1.0, "WB003": 1.0, "WB005": 2.0, "WB004": 1.0})
        self.assertEqual(angebot.summen()["netto"], 233438)     # 2.235,70 + 2 × 49,34
        self.assertIn("Leitungsverlegung gesamt: 12,4 m, davon 10 m enthalten, Mehrlänge 2 m",
                      angebot.auslegung_text)

    def test_erdarbeiten_rundung_und_unabhaengig_von_montage(self):
        """Erdarbeiten „7,5“ m → 8 m (kaufmännisch); Wandmontage + Erdarbeiten → WB006 ohne WB007."""
        angebot = self.angebot_direkt(bogen(WB560, 10, "Ja", "7,5", "Wandmontage"))
        self.assertEqual(mengen(angebot.positionen),
                         {"WB002": 1.0, "WB003": 1.0, "WB006": 8.0, "WB004": 1.0})
        self.assertEqual(angebot.summen()["netto"], 139055 + 129720 + 8 * 12350)
        self.assertIn("Erdarbeiten: 8 m", angebot.auslegung_text)
        self.assertIn("Montage: Wandmontage", angebot.auslegung_text)

    def test_zahleneingabe_dezimalkomma_ueber_formular(self):
        """Seite 0 per Formular speichern: „12,4“/„7,5“ werden Zahlen, WB04 nur bei Erdarbeiten = Ja,
        WB01 Pflicht."""
        e = self.erfassung_anlegen(None)
        r = self.client.post(f"/erfassung/{e.id}/seite/0",
                             data={"f_WB01": WB310, "f_WB02": "12,4", "f_WB03": "Ja", "f_WB04": "7,5",
                                   "f_WB05": "Säule", "f_WB07": "3", "f_WB08": "", "richtung": "weiter"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.refresh(e)
        antworten = json.loads(e.antworten_json)
        self.assertEqual((antworten["WB01"], antworten["WB02"], antworten["WB03"], antworten["WB04"],
                          antworten["WB05"], antworten["WB07"], antworten["WB08"]),
                         (WB310, 12.4, "Ja", 7.5, "Säule", 3, ""))
        # Erdarbeiten = Nein: WB04 wird verworfen
        r = self.client.post(f"/erfassung/{e.id}/seite/0",
                             data={"f_WB01": WB310, "f_WB02": "12,4", "f_WB03": "Nein", "f_WB04": "7,5",
                                   "f_WB05": "Säule", "f_WB07": "3", "richtung": "weiter"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.refresh(e)
        self.assertNotIn("WB04", json.loads(e.antworten_json))
        # ohne Wallbox-Auswahl/Zahl bleibt die Seite mit Fehler stehen
        r = self.client.post(f"/erfassung/{e.id}/seite/0",
                             data={"f_WB01": "", "f_WB02": "", "f_WB03": "Nein", "f_WB05": "Wandmontage",
                                   "f_WB07": "2", "richtung": "weiter"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Bitte auswählen", r.text)
        self.assertIn("Bitte eine Zahl eingeben", r.text)


# --- Fall E/G: Pflichtangaben fehlen → Meldung; Warnung über 100 m ---------------------------

class FallE(Basis):
    def test_leitungslaenge_leer_meldung(self):
        e = self.erfassung_anlegen(bogen(WB310, ""))
        r = self.absenden(e)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Leitungslänge fehlt oder ist keine Zahl", r.text)
        self.assertEqual(e.status, "Entwurf")           # nicht abgesendet
        self.assertIsNone(e.abgesendet_am)
        e2 = self.erfassung_anlegen(bogen("", 12))
        r = self.absenden(e2)
        self.assertIn("Wallbox auswählen", r.text)
        self.assertEqual(e2.status, "Entwurf")

    def test_fall_g_erdarbeiten_ohne_meter(self):
        for erd_m in ("", 0):
            e = self.erfassung_anlegen(bogen(WB560, 25, "Ja", erd_m, "Säule"))
            r = self.absenden(e)
            self.assertEqual(r.status_code, 200)
            self.assertIn("Erdarbeiten: Meter fehlen", r.text)
            self.assertEqual(e.status, "Entwurf", erd_m)
        self.assertEqual(wb_auslegung.validierung(bogen(WB560, 25, "Ja", "", "Säule")),
                         ["Erdarbeiten: Meter fehlen"])
        # mit Metern geht es durch
        e = self.erfassung_anlegen(bogen(WB560, 25, "Ja", 3, "Säule"))
        r = self.absenden(e)
        self.assertEqual((r.status_code, e.ampel, e.status), (200, "gruen", "Neu"))

    def test_warnung_ueber_100_m_ohne_sperre(self):
        e = self.erfassung_anlegen(bogen(WB310, 120))
        r = self.client.get(f"/erfassung/{e.id}/pruefen")
        self.assertIn("Leitungslänge über 100 m – bitte prüfen", r.text)
        self.assertIn("Absenden", r.text)
        r = self.absenden(e)
        self.assertEqual((r.status_code, e.ampel, e.status), (200, "gruen", "Neu"))
        angebot = self.angebot_erzeugen(e)
        self.assertEqual(mengen(angebot.positionen)["WB005"], 110.0)
        self.assertIn("Leitungslänge über 100 m – bitte prüfen", angebot.auslegung_text)
        self.assertIn("Leitungslänge über 100 m – bitte prüfen",
                      engine.hinweise_aus_protokoll(json.loads(angebot.protokoll_json)))


# --- Fall F: Freitext-Weiche → unverändert Individuell / TAIFUN ---------------------------

class FallF(Basis):
    def test_freitext_weiche_bleibt_taifun(self):
        e = self.erfassung_anlegen(None)
        r = self.client.post(f"/erfassung/{e.id}/freitext",
                             data={"freitext": "Wallbox an der Garage, Zuleitung über Hof"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.s.refresh(e)
        self.assertEqual((e.typ, e.ampel, e.status), ("freitext", "orange", "In TAIFUN zu schreiben"))
        self.assertEqual(e.gruende_text, "vom Außendienst als individuell erfasst")
        # Innendienst: kein „Angebot erzeugen“, sondern Protokoll/Extern erledigt
        r = self.client.get(f"/erfassungen/{e.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Extern erledigt", r.text)
        self.assertNotIn(f"/erfassungen/{e.id}/angebot-erzeugen\"", r.text)
        # „Angebot erzeugen“ erzeugt für Freitext kein WB-Angebot aus dem Konfigurator
        r = self.client.get(f"/erfassungen/{e.id}/angebot-erzeugen", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.refresh(e)
        if e.angebot_id:
            a = self.s.get(Angebot, e.angebot_id)
            self.assertEqual(a.positionen, [])   # Freitext hat keine Antworten → keine Positionen

    def test_bestehende_wb_freitext_erfassung_unveraendert(self):
        alt = self.s.get(Erfassung, WB_FREITEXT_ALT)
        if alt is None or alt.sparte != "WB" or alt.typ != "freitext":
            self.skipTest("keine WB-Freitext-Erfassung mit dieser ID in der Testdatenbank")
        self.assertEqual((alt.ampel, alt.typ), ("orange", "freitext"))
        r = self.client.get(f"/erfassungen/{alt.id}")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Erfassungsbogen starten", r.text)
        self.s.refresh(alt)
        self.assertEqual(alt.typ, "freitext")


# --- Außendienst, Parametrierung ------------------------------------------------------------

class Aussendienst(Basis):
    def test_meine_angebote_ohne_ek_db(self):
        e = self.erfassung_anlegen(FALL_B2, benutzer_id=self.ad.id)
        self.absenden(e)
        angebot = self.angebot_erzeugen(e)
        angebot.vertriebler_id = self.ad.id
        self.s.commit()
        # DB laut Fixture-EK: 5.773,85 − (903,80 + 412,00 + 2 × 80,00 + 15 × 21,10 + 8 × 60,00 + 700,00)
        self.assertEqual(angebot.deckungsbeitrag()["db"], 280155)
        c = TestClient(app, follow_redirects=False)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(self.ad.id))
        r = c.get("/meine-angebote")
        self.assertEqual(r.status_code, 200)
        self.assertIn(angebot.nummer, r.text)
        r = c.get(f"/meine-angebote/{angebot.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("5.773,85", r.text)
        self.assertIn("6.870,88", r.text)
        self.assertIn("Installation und Anschluss", r.text)
        # nie EK/DB-Werte (die DB-Ampel als Farbe ist seit v10 bewusst Teil der AD-Rabatt-
        # Sicht – der Deckungsbeitrag 2.801,55 € und die EK-Beträge erscheinen nicht)
        for verboten in ("Deckungsbeitrag", "EK Material", "903,80", "412,00", "2.801,55",
                         "2.972,30", "ek_cent"):
            self.assertNotIn(verboten, r.text, verboten)
        # Außendienst sieht nie die Lesesicht/den Import (Parametrierung ist Innendienst/Admin)
        self.assertIn(c.get("/parametrierung/wb-logik").status_code, (303, 403, 404))
        self.assertIn(c.get("/parametrierung/artikel/wb-import").status_code, (303, 403, 404))
        # Sparten-Start zeigt WB ohne „(immer Freitext)“
        r = c.get(f"/erfassung/sparten?kunde_id={self.kunde.id}")
        self.assertEqual(r.status_code, 200)
        self.assertNotRegex(r.text, r"WB – Wallbox[^<]*<span class=\"dezent\">\(immer Freitext\)")
        self.assertRegex(r.text, r"GW – Gewerbe[^<]*<span class=\"dezent\">\(immer Freitext\)")


class OhneArtikel(Basis):
    """Rollout-Zustand ohne Zulieferung: Wallbox-Blätter da, aber kein WB-Artikel im Stamm →
    Logik-Bericht grün (nur Hinweis), WB-Sicht = reiner Bogen, Katalog-Erfassung landet in
    der TAIFUN-Warteschlange; die Weiche bleibt sichtbar."""

    def test_ohne_wb_artikel_warnung_und_taifun_schiene(self):
        wb_artikel = (self.s.query(Artikel)
                      .filter(Artikel.pos_nr.like("WB%"), Artikel.aktiv.is_(True)).all())
        for a in wb_artikel:
            a.aktiv = False
        self.s.commit()
        try:
            logik, bericht = logik_modul.neu_einlesen(self.s)
            self.assertTrue(bericht.ok, bericht.fehler)                 # kein Fehler → Bogen frei
            self.assertTrue(logik.wb_artikel_fehlen)
            self.assertTrue(any("Wallbox-Artikel (WB001–WB008) fehlen" in w for w in bericht.warnungen),
                            bericht.warnungen)
            self.assertFalse([f for f in bericht.fehler if "WB0" in f])
            sicht = logik_modul.logik_fuer_sparte(logik, "WB")
            self.assertEqual(sicht.aktionen, [])
            self.assertFalse(engine.ist_wb_konfigurator(sicht))
            # Katalog-Erfassung: Weiche bleibt, Absenden → reine Erfassung (TAIFUN)
            e = self.erfassung_anlegen(bogen(WB310, 10))
            r = self.client.get(f"/erfassung/{e.id}/weiche", follow_redirects=False)
            self.assertEqual(r.status_code, 200)
            r = self.absenden(e)
            self.assertEqual(r.status_code, 200)
            self.assertEqual((e.ampel, e.status), ("orange", "In TAIFUN zu schreiben"))
            self.assertIn("reine WB-Erfassung", e.gruende_text)
            r = self.client.get(f"/erfassungen/{e.id}")
            self.assertEqual(r.status_code, 200)
            # Lesesicht meldet den Zustand
            r = self.client.get("/parametrierung/wb-logik")
            self.assertIn("noch nicht im Artikelstamm", r.text)
            self.assertEqual(import_wallbox.fehlende_wb_artikel(self.s), WB_NUMMERN)
        finally:
            for a in wb_artikel:
                a.aktiv = True
            self.s.commit()
            logik, bericht = logik_modul.neu_einlesen(self.s)
        self.assertFalse(logik.wb_artikel_fehlen)
        self.assertTrue(engine.ist_wb_konfigurator(logik_modul.logik_fuer_sparte(logik, "WB")))


class Parametrierung(Basis):
    def test_lesesicht_und_links(self):
        r = self.client.get("/parametrierung/wb-logik")
        self.assertEqual(r.status_code, 200)
        for erwartet in ("Wallbox-Konfigurator – Logik (Lesesicht)", "Wallbox-Prüfungen ohne Fehler",
                         "leitung_inklusive_m", "durchbrueche_inklusive", "WB005", "WB008", "EK Material"):
            self.assertIn(erwartet, r.text, erwartet)          # Admin sieht EK
        if (import_wallbox.wb_ordner() / "WB Angebot Excel 1.xlsx").exists():
            self.assertNotIn("Dateien fehlen", r.text)          # Zulieferung liegt im Projektordner
        r = self.client.get("/parametrierung/logik")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Wallbox-Konfigurator (v34)", r.text)
        self.assertIn("WB-Parameter", r.text)
        self.assertIn("durchbruch_position", r.text)
        r = self.client.get("/parametrierung")
        self.assertIn("/parametrierung/wb-logik", r.text)
        r = self.client.get("/artikel")
        self.assertIn("/parametrierung/artikel/wb-import", r.text)
        self.assertIn("q=WB0", r.text)
        r = self.client.get("/artikel?q=WB0")
        self.assertIn("WB003", r.text)
        self.assertIn("WB008", r.text)
        r = self.client.get("/parametrierung/angebotstool")
        self.assertIn("db_ampel_rot_unter_WB", r.text)

    def test_dateien_fehlen_hinweis(self):
        """Ohne Zulieferung: Lesesicht und Import-Vorschau melden die fehlende Datei, der
        Import-POST kehrt mit Meldung zurück (Ordner per Mock leer)."""
        with tempfile.TemporaryDirectory() as leer, \
                mock.patch.object(import_wallbox, "wb_ordner", return_value=Path(leer)):
            r = self.client.get("/parametrierung/wb-logik")
            self.assertEqual(r.status_code, 200)
            self.assertIn("Dateien fehlen", r.text)
            self.assertIn("WB Angebot Excel 1.xlsx", r.text)
            r = self.client.get("/parametrierung/artikel/wb-import")
            self.assertEqual(r.status_code, 200)
            self.assertIn("Wallbox-Preislisten fehlen", r.text)
            r = self.client.post("/parametrierung/artikel/wb-import", data={"bestaetigt": "1"},
                                 follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("fehlen", r.headers["location"])

    def test_import_route_mit_fixtures(self):
        with mock.patch.object(import_wallbox, "wb_ordner", return_value=FIXTURES):
            r = self.client.get("/parametrierung/artikel/wb-import")
            self.assertEqual(r.status_code, 200)
            self.assertIn("Import-Protokoll", r.text)
            self.assertIn("Textzeilen ohne Position", r.text)
            self.assertIn("Komplettpaket Wallbox inkl. Montage", r.text)
            self.assertIn("das Blatt gilt", r.text)                 # Einheit WB007 psl.
            self.assertNotIn("Rückfrage 1", r.text)                 # eine Datei – kein Konfliktblock
            for ek in ("611,20", "903,80", "412,00", "Einkaufspreis"):
                self.assertNotIn(ek, r.text, ek)
            r = self.client.post("/parametrierung/artikel/wb-import", data={},
                                 follow_redirects=False)
            self.assertIn("Bitte+den+Hinweis", r.headers["location"])
            einstellung_setzen(self.s, "wb_guid_nachfuehren", "0")   # Live-Excel im Test nicht beschreiben
            self.s.commit()
            r = self.client.post("/parametrierung/artikel/wb-import", data={"bestaetigt": "1"},
                                 follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("/parametrierung/wb-logik", r.headers["location"])
            self.assertIn("Wallbox-Import+abgeschlossen", r.headers["location"])
            einstellung_setzen(self.s, "wb_guid_nachfuehren", "")
            self.s.commit()


if __name__ == "__main__":
    unittest.main()
