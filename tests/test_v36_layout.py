# Tests PLAN_V22 Phase 189 (v36, Agent A1 – Seitenaufbau und Datenbindung des Angebots-PDFs, Layout v3):
# Kontext `pdf_kontext.fuer_angebot` je Sparte (Kontrollangebote WP 30.245,43 € netto, KL Fall A, WB Fall B,
# PV-Basisbogen), Empfängerblock-Varianten (v20), Kennzeichen EP/bauseits/Alternativ/Rabatt/Endbetrag/
# Förderzeilen, 0 %-Zeile PV, KfW-Teilbaum nur mit Förderblock, Vollmacht-Regel, Karte 2 je Profil,
# Knopf-Variante ohne/mit BASIS_URL, Wirtschaftlichkeit nur PV, Parser (Vortext/Nachtext), Migration
# migration_v36_texte (idempotent), gerendertes HTML je Sparte (keine externen Ressourcen, kein <script>,
# keine Hex-Farben) und – mit Browser – PDF-Textvergleiche (pypdf) inkl. „SEITE 2 VON n“.
# Läuft gegen die Datenbank des Testaufrufs (DB-Kopie über DB_PFAD_OVERRIDE/DATA_ORDNER); Testkunde mit
# eigener E-Mail, Aufräumen am Ende. Browser-Tests überspringen ohne Edge/Chromium.
import io
import json
import re
import unittest
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

warnings.filterwarnings("ignore")

from app import angebot_aufbau, angebotsprofile, config, pdf_export, pdf_html, pdf_kontext, zahlungsbedingungen
from app import logik as logik_modul
from app.db import SessionLocal, init_db
from app.models import (Angebot, AngebotsPosition, Benutzer, Einstellung, Kunde, Profil, Textblock, Vorgang,
                        einstellung_holen, einstellung_setzen)
from tests.test_kl_v24 import fall_a as kl_fall_a
from tests.test_pv_v13 import pv_basis
from tests.test_regression import KONTROLL_SZENARIO
from tests.test_wb_v34 import FALL_B as WB_FALL_B

TEST_EMAIL = "v36-layout@test.local"
TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates" / "pdf" / "angebot"
EIGENE_TEMPLATES = ["basis.html", "_fuss.html", "deckblatt.html", "ueberblick.html", "positionen.html",
                    "auftrag.html", "_cloover.html", "bedingungen.html", "vollmacht.html",
                    "wp.html", "pv.html", "kl.html", "wb.html"]
HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
PNG_1PX = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
           "60e6kgAAAABJRU5ErkJggg==")
BROWSER = pdf_html.browser_test()   # einmal je Modul (Edge/Chromium auf dem Dev-PC)


def _modul(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


HAT_KFW = _modul("app.pdf_kontext_kfw")
HAT_WIRTSCHAFTLICHKEIT = _modul("app.pdf_kontext_wirtschaftlichkeit")


def pdf_text(daten: bytes) -> list[str]:
    import pypdf
    return [s.extract_text() or "" for s in pypdf.PdfReader(io.BytesIO(daten)).pages]


def aufraeumen(s) -> None:
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.delete(v)
        s.delete(k)
    s.commit()


def schluessel_rekursiv(obj, gefunden: set | None = None) -> set:
    gefunden = set() if gefunden is None else gefunden
    if isinstance(obj, dict):
        for k, v in obj.items():
            gefunden.add(str(k))
            schluessel_rekursiv(v, gefunden)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            schluessel_rekursiv(v, gefunden)
    return gefunden


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        cls.logik, _ = logik_modul.hole_logik(cls.s)
        aufraeumen(cls.s)
        cls.kunde = Kunde(anrede="Herr", vorname="Max", nachname="V36-Layout-Test", strasse="Musterstraße 12",
                          plz="47139", ort="Duisburg", email=TEST_EMAIL, telefon="0203 1234567")
        cls.s.add(cls.kunde)
        cls.s.commit()
        # WP-Kontrollangebot (Netto 30.245,43 €) + 500 € Gesamtrabatt
        cls.wp = angebot_aufbau.angebot_anlegen(cls.s, cls.kunde.id, antworten=KONTROLL_SZENARIO, logik=cls.logik)
        cls.wp.rabatt_cent = 50000
        cls.wp.rabatt_bezeichnung = "Aktionsnachlass"
        # zweites WP-Angebot für Kennzeichen/Anschriften/Profile/Versionen
        cls.wp2 = angebot_aufbau.angebot_anlegen(cls.s, cls.kunde.id, antworten=KONTROLL_SZENARIO, logik=cls.logik)
        cls.kl = angebot_aufbau.angebot_anlegen(cls.s, cls.kunde.id, antworten=kl_fall_a(),
                                                logik=logik_modul.logik_fuer_sparte(cls.logik, "KL"), sparte="KL")
        cls.pv = angebot_aufbau.angebot_anlegen(cls.s, cls.kunde.id, antworten=pv_basis(),
                                                logik=logik_modul.logik_fuer_sparte(cls.logik, "PV"), sparte="PV")
        cls.logik_wb = logik_modul.logik_fuer_sparte(cls.logik, "WB")
        cls.wb = (angebot_aufbau.angebot_anlegen(cls.s, cls.kunde.id, antworten=WB_FALL_B, logik=cls.logik_wb,
                                                 sparte="WB") if cls.logik_wb is not None else None)
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def kontext(self, angebot, **kw) -> dict:
        return pdf_kontext.fuer_angebot(self.s, angebot, **kw)

    def html(self, angebot, **kw) -> str:
        kontext = self.kontext(angebot, **kw)
        return pdf_html.html_rendern(pdf_html.vorlage_fuer(kontext["sparte"]), kontext)


# --- Kontext ------------------------------------------------------------------------------------------
class KontextWP(Basis):
    def test_kontrollwerte_summen_mit_rabatt_und_foerderung(self):
        k = self.kontext(self.wp)
        s = k["summen"]
        self.assertEqual((s["netto"], s["ust"], s["gesamt"]), ("30.245,43 €", "5.746,63 €", "35.992,06 €"))
        self.assertEqual(s["ust_text"], "19,00 % USt.")
        # Minus nur im Label, Betrag ohne Minus (Vorlage, Abnahme A4 Nr. 10)
        self.assertEqual(s["rabatt"], {"text": "− Rabatt Aktionsnachlass", "betrag": "500,00 €"})
        self.assertEqual(s["endbetrag"], "35.492,06 €")
        self.assertTrue(s["hat_foerderung"] and s["hat_rabatt"])
        ergebnis = pdf_export._kfw_ergebnis_fuer(self.s, self.wp)
        self.assertIsNotNone(ergebnis)
        self.assertEqual(s["foerderung"]["betrag"], pdf_kontext._euro(ergebnis.zuschuss_cent))
        self.assertFalse(any(z["betrag"].startswith("−") for z in s["zeilen"]))
        self.assertEqual(s["eigenanteil"], pdf_kontext._euro(ergebnis.eigenanteil_cent))
        self.assertEqual(s["box"]["titel"], "= Ihr Eigenanteil")
        self.assertEqual(s["box"]["betrag"], s["eigenanteil"])
        self.assertEqual(s["box"]["hinweis"], pdf_kontext.EIGENANTEIL_HINWEIS)
        texte = [z["text"] for z in s["zeilen"]]
        self.assertEqual(texte[:5], ["Netto-Summe", "19,00 % USt.", "Gesamt-Betrag", "− Rabatt Aktionsnachlass",
                                     "= Endbetrag"])
        self.assertRegex(texte[5], r"^− voraussichtliche KfW-Förderung \(\d+ %\)$")
        # Förderquote = Anteil des Zuschusses an der Angebotssumme (wie der Untertitel der KfW-Seite), nicht
        # der nominale Fördersatz
        quote = round(ergebnis.zuschuss_cent / (ergebnis.zuschuss_cent + ergebnis.eigenanteil_cent) * 100)
        if k["kfw"]:
            self.assertEqual(s["foerderung"]["prozent"], str(k["kfw"]["foerderquote"]))
        else:
            self.assertEqual(s["foerderung"]["prozent"], str(quote))
        self.assertTrue(s["zeilen"][5]["blau"])
        self.assertTrue(s["zeilen"][2]["linie"] and s["zeilen"][2]["fett"])

    def test_struktur_laut_vertrag(self):
        k = self.kontext(self.wp)
        for key in ("sparte", "sparte_name", "eyebrow", "titel", "untertitel", "titelbild", "fassung", "angebot",
                    "firma", "kunde", "empfaenger", "ansprechpartner", "ueberblick", "gruppen", "hinweise",
                    "summen", "kfw", "wirtschaftlichkeit", "auftrag", "bedingungen", "vollmacht", "signatur"):
            self.assertIn(key, k, key)
        self.assertEqual(k["sparte"], "WP")
        self.assertEqual(k["titel"], "Ihr individuelles Wärmepumpen-Angebot zum Festpreis")
        self.assertEqual(k["angebot"]["nummer"], self.wp.nummer)
        self.assertEqual(k["angebot"]["gueltig_bis"],
                         (self.wp.datum + timedelta(days=pdf_kontext.BINDEFRIST_TAGE)).strftime("%d.%m.%Y"))
        self.assertEqual(k["angebot"]["profil"], "standard")
        self.assertEqual(k["kunde"]["name"], "Max V36-Layout-Test")        # Kopfzeile ohne Anrede
        self.assertEqual(k["kunde"]["briefanrede"], "Sehr geehrter Herr V36-Layout-Test,")
        self.assertEqual(k["empfaenger"]["zeilen"], ["Herr Max V36-Layout-Test", "Musterstraße 12", "47139 Duisburg"])
        self.assertIsNone(k["empfaenger"]["ausfuehrungsort"])
        self.assertIsNone(k["empfaenger"]["lieferanschrift"])
        self.assertEqual(k["firma"]["fuss"][3]["titel"], "BANKVERBINDUNG")
        self.assertEqual(len(k["firma"]["fuss"][3]["zeilen"]), 2)        # je Bank eine Zeile
        self.assertEqual(len(k["firma"]["zertifikate"]), 5)
        self.assertEqual(k["firma"]["award_link"], pdf_kontext.AWARD_LINK)
        self.assertEqual(k["auftrag"]["einleitung"], pdf_kontext.AUFTRAG_EINLEITUNG)
        self.assertTrue(k["auftrag"]["cloover_block"])
        self.assertIsNotNone(k["auftrag"]["aufschiebende_bedingung"])
        self.assertTrue(k["auftrag"]["umsetzungsdatum"])
        self.assertIsNone(k["vollmacht"])          # Kontroll-Szenario ohne P02/P03 (016/017)
        self.assertIsNone(k["wirtschaftlichkeit"])

    def test_positionen_nummerierung_und_gruppen(self):
        k = self.kontext(self.wp)
        nummern = [p["nr"] for g in k["gruppen"] for p in g["positionen"]]
        self.assertEqual(nummern, self.wp.nummerierung())
        self.assertEqual(len(nummern), len(self.wp.positionen))
        self.assertTrue(all(g["titel"] for g in k["gruppen"]))
        erste = k["gruppen"][0]["positionen"][0]
        self.assertEqual(erste["menge"], "1,00")
        self.assertNotIn("€", erste["einzelpreis"])            # Tabelle ohne €-Zeichen (Kopf: EUR, netto)
        self.assertTrue(erste["bezeichnung"])
        for g in k["gruppen"]:
            for p in g["positionen"]:
                self.assertIn(p["kennzeichen"], ("", "ep", "bauseits", "alternativ"))
                for z in p["zeilen"]:
                    self.assertIn("punkt", z)
                    self.assertFalse(z["text"].startswith(("- ", "• ", "– ")))

    @unittest.skipUnless(HAT_KFW, "pdf_kontext_kfw (Agent A2) fehlt")
    def test_kfw_teilbaum_nur_mit_foerderblock(self):
        k = self.kontext(self.wp)
        self.assertIsNotNone(k["kfw"])
        self.assertEqual(k["summen"]["foerderung"]["prozent"], str(k["kfw"]["foerderquote"]))
        self.wp.foerderung_ausblenden = True
        try:
            k = self.kontext(self.wp)
            self.assertIsNone(k["kfw"])
            self.assertFalse(k["summen"]["hat_foerderung"])
            self.assertEqual(k["summen"]["box"]["titel"], "= Endbetrag")
            self.assertEqual(k["summen"]["box"]["betrag"], "35.492,06 €")
            self.assertNotIn("Förderung", " ".join(z["text"] for z in k["summen"]["zeilen"]))
        finally:
            self.wp.foerderung_ausblenden = False

    def test_kein_ek_oder_db_im_kontext(self):
        for angebot in (self.wp, self.pv, self.kl):
            for fassung in ("kunde", "intern"):
                k = self.kontext(angebot, fassung=fassung)
                keys = schluessel_rekursiv(k)
                for verboten in ("ek_cent", "ek", "deckungsbeitrag", "db", "db_prozent", "marge"):
                    self.assertNotIn(verboten, keys, f"{verboten} in {angebot.nummer} ({fassung})")
                self.assertNotIn("Deckungsbeitrag", json.dumps(k, ensure_ascii=False, default=str))


class KontextKennzeichen(Basis):
    """Zweites WP-Angebot: EP, bauseits, Alternativ (Hinweiskasten + „im PV-Angebot“), Positionsrabatt."""

    def test_kennzeichen(self):
        p = list(self.wp2.positionen)
        self.assertGreaterEqual(len(p), 6)
        p[1].ep_flag = True
        p[2].bauseits = True
        p[3].alternativ = True
        p[3].alternativ_zu = "PV-Angebot AN-C-999999"
        p[4].rabatt_prozent = 10.0
        try:
            k = self.kontext(self.wp2)
            eintraege = {e["nr"]: e for g in k["gruppen"] for e in g["positionen"]}
            n = self.wp2.nummerierung()
            self.assertEqual(eintraege[n[1]]["kennzeichen"], "ep")
            self.assertEqual(eintraege[n[1]]["gesamtpreis"], "EP.")
            self.assertEqual(eintraege[n[1]]["einzelpreis"], pdf_kontext._betrag_tabelle(p[1].e_preis_cent))
            self.assertEqual(eintraege[n[2]]["kennzeichen"], "bauseits")
            self.assertEqual((eintraege[n[2]]["einzelpreis"], eintraege[n[2]]["gesamtpreis"]), ("bauseits", "bauseits"))
            alt = eintraege[n[3]]
            self.assertEqual(alt["kennzeichen"], "alternativ")
            self.assertEqual(alt["gesamtpreis"], "im PV-Angebot")
            self.assertEqual(alt["hinweiskasten"], "Die folgenden Positionen sind bereits in Ihrem Angebot "
                                                   "AN-C-999999 (PV) enthalten und werden dort berechnet.")
            self.assertTrue(any(z["dezent"] and z["text"].startswith("Hinweis: Diese Position ist im parallel")
                                for z in alt["zeilen"]))
            gruppe = next(g for g in k["gruppen"] if any(e["nr"] == n[3] for e in g["positionen"]))
            self.assertEqual(gruppe["alternativ_hinweis"], alt["hinweiskasten"])
            rab = eintraege[n[4]]
            self.assertEqual(rab["rabatt_text"],
                             f"− Rabatt 10 % ({pdf_kontext._euro(p[4].rabatt_effektiv_cent)})")
            self.assertEqual(rab["gesamtpreis"], pdf_kontext._betrag_tabelle(p[4].gesamt_cent))
            # Summen folgen Angebot.summen(): EP/bauseits/Alternativ zählen nicht, Positionsrabatt zählt
            self.assertEqual(k["summen"]["netto"], pdf_kontext._euro(self.wp2.summen()["netto"]))
            self.assertLess(self.wp2.summen()["netto"], self.wp.summen()["netto"])
        finally:
            p[1].ep_flag = False
            p[2].bauseits = False
            p[3].alternativ = False
            p[3].alternativ_zu = ""
            p[4].rabatt_prozent = None
            self.s.commit()

    def test_empfaenger_varianten_v20(self):
        a = self.wp2
        a.rechnung_name, a.rechnung_strasse, a.rechnung_plz, a.rechnung_ort = "Erika Beispiel", "Rechnungsweg 1", "47441", "Moers"
        try:
            k = self.kontext(a)
            self.assertEqual(k["empfaenger"]["zeilen"], ["Erika Beispiel", "Rechnungsweg 1", "47441 Moers"])
            self.assertEqual(k["empfaenger"]["ausfuehrungsort"], "Musterstraße 12, 47139 Duisburg")
            self.assertIsNone(k["empfaenger"]["lieferanschrift"])
            a.liefer_name, a.liefer_strasse, a.liefer_plz, a.liefer_ort = "", "Lagerstraße 5", "47139", "Duisburg"
            k = self.kontext(a)
            self.assertEqual(k["empfaenger"]["lieferanschrift"],
                             "Herr Max V36-Layout-Test, Lagerstraße 5, 47139 Duisburg")
            # nur Zusatz: Ansprechpartner bleibt, Zusatz als Zeile, kein Ausführungsort
            a.rechnung_name, a.rechnung_strasse, a.rechnung_plz, a.rechnung_ort = "", "", "", ""
            a.rechnung_zusatz = "c/o Hausverwaltung"
            a.liefer_strasse = a.liefer_plz = a.liefer_ort = ""
            k = self.kontext(a)
            self.assertEqual(k["empfaenger"]["zeilen"],
                             ["Herr Max V36-Layout-Test", "c/o Hausverwaltung", "Musterstraße 12", "47139 Duisburg"])
            self.assertIsNone(k["empfaenger"]["ausfuehrungsort"])
        finally:
            a.rechnung_name = a.rechnung_strasse = a.rechnung_plz = a.rechnung_ort = a.rechnung_zusatz = ""
            a.liefer_name = a.liefer_strasse = a.liefer_plz = a.liefer_ort = ""
            self.s.commit()

    def test_karte2_je_profil(self):
        a = self.wp2
        profile = {p.regel_kennung: p for p in self.s.query(Profil)}
        erwartet = {"enni": ("ENNI CONTRACTING", "Barkauf oder Enni Contracting"),
                    "swd": ("CONTRACTING", "Barkauf oder Contracting"),
                    "sparkasse": ("FINANZIERUNG MIT SPARKASSE DUISBURG", "Barkauf oder Finanzierung")}
        try:
            for kennung, (titel, untertitel) in erwartet.items():
                self.assertIn(kennung, profile, "Profil fehlt in der Datenbank")
                a.profil_id = profile[kennung].id
                k = self.kontext(a)
                self.assertEqual(k["angebot"]["profil"], kennung)
                self.assertEqual(k["auftrag"]["karte2"]["art"], kennung)
                self.assertEqual(k["auftrag"]["karte2"]["titel"], titel)
                self.assertEqual(k["auftrag"]["karte2"]["untertitel"], untertitel)
                self.assertFalse(k["auftrag"]["cloover_block"])
                self.assertIsNone(k["auftrag"]["cloover"])
                self.assertEqual(k["auftrag"]["karte2"]["knopf_text"], "")
                # Cloover-Slogan nur im Cloover-Block des Profils Standard (Abnahme A4 Nr. 12)
                self.assertFalse(any(pdf_kontext.ist_slogan(a) for a in k["auftrag"]["karte2"]["absaetze"]))
                self.assertNotIn(pdf_kontext.SLOGAN, self.html(a))
                if kennung == "sparkasse":
                    self.assertEqual(k["auftrag"]["karte2"]["absaetze"], ["Finanzierung mit Sparkasse Duisburg"])
                else:
                    self.assertEqual(k["auftrag"]["karte2"]["absaetze"], [])
                    self.assertEqual(k["auftrag"]["karte2"]["text"], "")
                if kennung in ("enni", "sparkasse"):
                    titel_liste = [x["titel"] for x in k["bedingungen"]["abschnitte"]]
                    self.assertIn("Unsere Leistungen", titel_liste)
                if kennung in ("enni", "swd"):
                    self.assertIsNone(k["vollmacht"])
            a.profil_id = profile["standard"].id
            k = self.kontext(a)
            self.assertEqual(k["auftrag"]["karte2"]["art"], "cloover")
            self.assertEqual(k["auftrag"]["karte2"]["titel"], "FINANZIERUNG MIT CLOOVER")
            self.assertTrue(k["auftrag"]["cloover_block"])
            if k["auftrag"]["cloover"] is None:
                self.assertEqual(k["auftrag"]["karte2"]["text"], "Monatsrate auf Anfrage")
                self.assertEqual(k["auftrag"]["karte2"]["knopf_text"], "")
        finally:
            a.profil_id = None
            self.s.commit()

    def test_karte1_knopf_ohne_und_mit_basis_url(self):
        a = self.wp2
        k = self.kontext(a)
        self.assertEqual(k["auftrag"]["karte1"]["knopf_text"], "Per E-Mail beauftragen ›")
        self.assertEqual(k["auftrag"]["karte1"]["knopf_url"], f"mailto:angebot@friondo.de?subject=Auftrag%20{a.nummer}")
        self.assertFalse(k["auftrag"]["karte1"]["online"])
        self.assertEqual(k["auftrag"]["karte1"]["text"],
                         "Eine Anzahlung von 50% des Angebotsbetrags ist spätestens 14 Tage vor Arbeitsbeginn zu "
                         "zahlen. Die Restzahlung wird mit der Schlussrechnungsstellung fällig.")
        alt = einstellung_holen(self.s, "signatur_fern_aktiv", "0")
        a.signatur_token = "v36testtoken"
        a.signatur_token_gueltig_bis = datetime.now() + timedelta(days=1)
        try:
            einstellung_setzen(self.s, "signatur_fern_aktiv", "1")
            self.s.commit()
            with mock.patch.object(config, "BASIS_URL_AUS_ENV", True), \
                    mock.patch.object(config, "BASIS_URL", "https://tool.example"):
                k = self.kontext(a)
                self.assertEqual(k["auftrag"]["karte1"]["knopf_text"], "Jetzt online beauftragen ›")
                self.assertEqual(k["auftrag"]["karte1"]["knopf_url"], "https://tool.example/signatur/extern/v36testtoken")
                self.assertTrue(k["auftrag"]["karte1"]["online"])
                a.signatur_token_gueltig_bis = datetime.now() - timedelta(minutes=1)   # abgelaufen → E-Mail
                k = self.kontext(a)
                self.assertEqual(k["auftrag"]["karte1"]["knopf_text"], "Per E-Mail beauftragen ›")
            # BASIS_URL nicht aus der .env → immer E-Mail, auch mit Token
            a.signatur_token_gueltig_bis = datetime.now() + timedelta(days=1)
            with mock.patch.object(config, "BASIS_URL_AUS_ENV", False):
                self.assertEqual(self.kontext(a)["auftrag"]["karte1"]["knopf_text"], "Per E-Mail beauftragen ›")
        finally:
            einstellung_setzen(self.s, "signatur_fern_aktiv", alt)
            a.signatur_token = None
            a.signatur_token_gueltig_bis = None
            self.s.commit()

    def test_version_kopie_und_ansprechpartner(self):
        a = self.wp2
        ad = (self.s.query(Benutzer).filter(Benutzer.rolle == "aussendienst", Benutzer.aktiv.is_(True))
              .order_by(Benutzer.id).first())
        self.assertIsNotNone(ad)
        alt_telefon = ad.telefon
        a.vorgaenger_id = self.wp.id
        a.kopie_von = "AN-C-000001"
        a.vertriebler_id = ad.id
        ad.telefon = "0170 0000000"
        try:
            k = self.kontext(a)
            self.assertEqual(k["angebot"]["version_von"],
                             {"nummer": self.wp.nummer, "datum": self.wp.datum.strftime("%d.%m.%Y")})
            self.assertEqual(k["angebot"]["ersetzt_hinweis"],
                             f"Ersetzt Angebot {self.wp.nummer} vom {self.wp.datum.strftime('%d.%m.%Y')}")
            self.assertEqual(k["angebot"]["kopie_von"], "AN-C-000001")
            self.assertEqual(k["ansprechpartner"], {"name": ad.name, "telefon": "0170 0000000"})
            ad.telefon = ""
            self.assertEqual(self.kontext(a)["ansprechpartner"]["telefon"], "")     # Zeile entfällt
            a.vertriebler_id = None
            self.assertEqual(self.kontext(a)["ansprechpartner"]["name"], "")
            innendienst = Benutzer(name="V36 Innendienst", rolle="innendienst", telefon="0203 1")
            self.assertEqual(self.kontext(a, benutzer=innendienst)["ansprechpartner"],
                             {"name": "V36 Innendienst", "telefon": "0203 1"})
        finally:
            a.vorgaenger_id = None
            a.kopie_von = ""
            a.vertriebler_id = None
            ad.telefon = alt_telefon
            self.s.commit()

    def test_vollmacht_regel(self):
        self.assertIsNone(self.kontext(self.wp)["vollmacht"])
        self.assertIsNone(self.kontext(self.kl)["vollmacht"])
        a = self.wp2
        extra = AngebotsPosition(sort=999, block_nr=9, gruppe="Friondo fit for future", pos_nr="016",
                                 bezeichnung="Friondo iMSys", beschreibung="", menge=1, einheit="psl.",
                                 e_preis_cent=0)
        a.positionen.append(extra)
        try:
            v = self.kontext(a)["vollmacht"]
            self.assertIsNotNone(v)
            self.assertEqual(v["titel"], pdf_kontext.VOLLMACHT_TITEL)
            self.assertEqual([f["wert"] for f in v["verbrauchsstelle"]],
                             ["Max V36-Layout-Test", "Musterstraße 12, 47139 Duisburg", "", "0203 1234567", TEST_EMAIL])
            self.assertEqual(v["kaestchen"], pdf_kontext.VOLLMACHT_KAESTCHEN)
            self.assertEqual(len(v["sepa_zeilen"]), 4)
            self.assertEqual(len(v["unterschriften"]), 3)
        finally:
            a.positionen.remove(extra)
            self.s.commit()
        # PV: Vollmacht nur mit 017
        self.assertIsNone(self.kontext(self.pv)["vollmacht"]) if not any(
            p.pos_nr in ("016", "017") for p in self.pv.positionen) else None
        spot = AngebotsPosition(sort=999, block_nr=9, gruppe="", pos_nr="017", bezeichnung="SpotDynamic",
                                beschreibung="", menge=1, einheit="psl.", e_preis_cent=0)
        self.pv.positionen.append(spot)
        try:
            self.assertIsNotNone(self.kontext(self.pv)["vollmacht"])
        finally:
            self.pv.positionen.remove(spot)
            self.s.commit()


class KontextSparten(Basis):
    def test_pv_null_prozent_und_wirtschaftlichkeit(self):
        k = self.kontext(self.pv)
        self.assertEqual(k["sparte"], "PV")
        self.assertEqual(k["angebot"]["ust_satz"], 0)
        self.assertEqual(k["summen"]["ust_text"], "0,00 % USt. (§ 12 Abs. 3 UStG)")
        self.assertEqual(k["summen"]["ust"], "0,00 €")
        self.assertEqual(k["summen"]["box"]["titel"], "Gesamt-Betrag")
        self.assertEqual(k["summen"]["gesamt"], k["summen"]["netto"])
        self.assertFalse(k["summen"]["hat_foerderung"])
        self.assertIsNone(k["kfw"])
        self.assertTrue(any("Nullsteuersatz" in f for f in k["bedingungen"]["fussnoten"]))
        self.assertIsNone(k["auftrag"]["aufschiebende_bedingung"])
        self.assertFalse(k["auftrag"]["umsetzungsdatum"])
        if HAT_WIRTSCHAFTLICHKEIT and (self.pv.pv_json or "").strip():
            self.assertIsNotNone(k["wirtschaftlichkeit"])
            self.pv.wirtschaftlichkeit_ausblenden = True
            try:
                self.assertIsNone(self.kontext(self.pv)["wirtschaftlichkeit"])
            finally:
                self.pv.wirtschaftlichkeit_ausblenden = False
        # Wirtschaftlichkeit nie bei WP/KL
        self.assertIsNone(self.kontext(self.wp)["wirtschaftlichkeit"])
        self.assertIsNone(self.kontext(self.kl)["wirtschaftlichkeit"])

    def test_kl_fall_a_kontrollwerte(self):
        k = self.kontext(self.kl)
        self.assertEqual(k["sparte"], "KL")
        self.assertEqual((k["summen"]["netto"], k["summen"]["ust"], k["summen"]["gesamt"]),
                         ("6.518,66 €", "1.238,55 €", "7.757,21 €"))
        self.assertEqual(k["summen"]["box"], {"titel": "Gesamt-Betrag", "betrag": "7.757,21 €", "hinweis": ""})
        self.assertEqual([z["text"] for z in k["summen"]["zeilen"]], ["Netto-Summe", "19,00 % USt."])
        self.assertIsNone(k["kfw"])
        self.assertIsNone(k["vollmacht"])
        self.assertIn("Hinweis zur Kältetechnik", [a["titel"] for a in k["bedingungen"]["abschnitte"]])
        self.assertTrue(k["auftrag"]["ausfuehrungszeitraum"])
        self.assertIsNone(k["auftrag"]["aufschiebende_bedingung"])
        self.assertEqual(k["titel"], "Ihr individuelles Klimaanlagen-Angebot zum Festpreis")

    def test_wb_fall_b_kontrollwerte(self):
        if self.wb is None:
            self.skipTest("WB-Konfigurator ohne importierte WB-Artikel")
        k = self.kontext(self.wb)
        self.assertEqual(k["sparte"], "WB")
        self.assertEqual((k["summen"]["netto"], k["summen"]["ust"], k["summen"]["gesamt"]),
                         ("5.435,85 €", "1.032,81 €", "6.468,66 €"))
        self.assertEqual([g["titel"] for g in k["gruppen"]], ["Wallbox", "Installation und Anschluss", "Netzanmeldung"])
        self.assertIsNotNone(k["vollmacht"])          # WB: Vollmacht immer (v34)
        self.assertIsNone(k["kfw"])
        self.assertTrue(k["auftrag"]["ausfuehrungszeitraum"])
        self.assertNotIn("Hinweis zur KfW-Förderung", [a["titel"] for a in k["bedingungen"]["abschnitte"]])

    def test_seitentitel_der_nachtexte_als_zwischenueberschrift(self):
        """Nachtrag H6: „# Installationsvoraussetzungen“ wird blaue Zwischenüberschrift (Ebene 1, ohne eigene
        Absätze), „# Ihre Zahlungsoptionen bei Friondo“ entfällt (Seite des Layouts)."""
        for angebot in (self.wp, self.kl, self.wb):
            if angebot is None:
                continue
            abschnitte = self.kontext(angebot)["bedingungen"]["abschnitte"]
            titel = [a["titel"] for a in abschnitte]
            self.assertEqual(titel[:2], ["Installationsvoraussetzungen", "Haftungsbegrenzung"], angebot.nummer)
            self.assertEqual(abschnitte[0]["ebene"], 1)
            self.assertEqual(abschnitte[0]["absaetze"], [])
            self.assertEqual(abschnitte[1]["ebene"], 2)
            self.assertFalse(any("Zahlungsoptionen" in t for t in titel), angebot.nummer)
            html = self.html(angebot)
            self.assertIn('class="pdf-bed-abschnitt pdf-bed-ebene1"', html)
            self.assertNotIn("Ihre Zahlungsoptionen bei Friondo", html)
        # Enni: „# Installationsvoraussetzungen“ gibt es dort nicht – stattdessen die „###“-Abschnitte der A-Seite
        enni = pdf_kontext.nachtext_parsen(angebotsprofile.ENNI_NACHTEXT)
        self.assertEqual([a["titel"] for a in enni["abschnitte"]][:3],
                         ["Unsere Leistungen", "Installationsvoraussetzungen", "Haftungsbegrenzung"])
        self.assertEqual([a["ebene"] for a in enni["abschnitte"]][:3], [2, 2, 2])
        self.assertTrue(all(a["absaetze"] or a["ebene"] == 1 for a in enni["abschnitte"]))

    def test_bedingungen_schluss_mit_links(self):
        k = self.kontext(self.wp)
        b = k["bedingungen"]
        self.assertEqual([a["titel"] for a in b["abschnitte"]],
                         ["Installationsvoraussetzungen", "Haftungsbegrenzung",
                          "Rücktrittsrecht im Zusammenhang mit Technischer Feinplanung",
                          "Zahlung", "Hinweis zur KfW-Förderung"])
        zahlung = next(a for a in b["abschnitte"] if a["titel"] == "Zahlung")
        self.assertEqual(zahlung["absaetze"], [zahlungsbedingungen.fuer_angebot(self.s, self.wp)[1]])
        urls = [l["url"] for l in b["schluss"]["links"]]
        self.assertEqual(urls, ["https://friondo.de/AGB", "https://friondo.de/Datenschutz"])
        texte = ["".join(t["text"] for t in a) for a in b["schluss"]["absaetze"]]
        self.assertTrue(texte[0].startswith("Wir halten uns freibleibend 30 Tage"))
        self.assertEqual(b["schluss"]["gruss"], ["Mit freundlichen Grüßen", "Ihr Friondo-Team"])
        self.assertFalse(any("Sollte Ihnen das Angebot zusagen" in t for t in texte))
        self.assertFalse(any("[UNTERSCHRIFT]" in t for t in texte))


class Parser(unittest.TestCase):
    def test_vortext_standard_wp(self):
        u = pdf_kontext.vortext_parsen(angebotsprofile.STANDARD_VORTEXT, "Sehr geehrter Herr Mustermann,")
        self.assertEqual(u["anrede"], "Sehr geehrter Herr Mustermann,")
        self.assertEqual(len(u["einleitung"]), 2)
        self.assertTrue(u["einleitung"][0].startswith("vielen Dank für Ihr Vertrauen"))
        self.assertEqual([e["titel"] for e in u["enthalten"]],
                         ["Ihre individuelle Wärmepumpe", "Detaillierte Installationsleistungen",
                          "Transparent und Festpreis", "Unser Rundum-Sorglos-Service"])
        self.assertEqual(u["warum_titel"], "Warum Friondo?")
        self.assertEqual(len(u["warum"]), 5)
        self.assertEqual(u["warum"][0]["titel"], "Fachkompetenz & Qualität")
        self.assertEqual([s["fett"] for s in u["schluss"]], [True, False])
        self.assertEqual(u["gruss"], ["Ihr Friondo-Team"])
        self.assertFalse(any("Festpreis" in a for a in u["einleitung"]))   # Titelzeilen → Deckblatt

    def test_vortext_v36_pv_kl_wb(self):
        for text, schluss in ((angebotsprofile.PV_VORTEXT_V36, "Ihren eigenen Strom erzeugen!"),
                              (angebotsprofile.KL_VORTEXT_V36, "für Ihr Wohlfühlklima sorgen!"),
                              (angebotsprofile.WB_VORTEXT_V36, "Ihr Zuhause zur Ladestation machen!")):
            u = pdf_kontext.vortext_parsen(text, "Sehr geehrte Damen und Herren,")
            self.assertEqual(len(u["einleitung"]), 1)
            self.assertEqual(len(u["enthalten"]), 4)
            self.assertEqual(len(u["warum"]), 5)
            self.assertEqual(len(u["schluss"]), 1)
            self.assertTrue(u["schluss"][0]["text"].endswith(schluss))
            self.assertEqual(u["gruss"], ["Ihr Friondo-Team"])
        alt = pdf_kontext.vortext_parsen(angebotsprofile.PV_VORTEXT, "Sehr geehrte Damen und Herren,")
        self.assertEqual(alt["gruss"], ["Mit herzlichen Grüßen,", "Ihr Friondo-Team"])

    def test_nachtext_standard_enni_sparkasse(self):
        std = pdf_kontext.nachtext_parsen(zahlungsbedingungen.text_einsetzen(
            angebotsprofile.STANDARD_NACHTEXT, zahlungsbedingungen.STANDARD_ABSATZ))
        self.assertEqual([a["titel"] for a in std["abschnitte"]],
                         ["Installationsvoraussetzungen", "Haftungsbegrenzung",
                          "Rücktrittsrecht im Zusammenhang mit Technischer Feinplanung",
                          "Zahlung", "Hinweis zur KfW-Förderung"])
        self.assertTrue(std["aufschiebende_bedingung"].startswith("Dieser Vertrag tritt"))
        self.assertTrue(std["umsetzungsdatum"])
        self.assertNotIn("Sofort starten", [a["titel"] for a in std["abschnitte"]])   # Cloover-Block = Design
        self.assertEqual(std["fussnoten"], [])
        enni = pdf_kontext.nachtext_parsen(zahlungsbedingungen.text_einsetzen(
            angebotsprofile.ENNI_NACHTEXT, zahlungsbedingungen.STANDARD_ABSATZ))
        self.assertEqual(enni["karte2_untertitel"], "Barkauf oder Enni Contracting")
        self.assertEqual(enni["karte2_absaetze"], [pdf_kontext.SLOGAN])
        self.assertEqual([a["titel"] for a in enni["abschnitte"]][:2], ["Unsere Leistungen", "Installationsvoraussetzungen"])
        sparkasse = pdf_kontext.nachtext_parsen(angebotsprofile.SPARKASSE_NACHTEXT)
        self.assertEqual(sparkasse["karte2_absaetze"], [pdf_kontext.SLOGAN, "Finanzierung mit Sparkasse Duisburg"])
        kl = pdf_kontext.nachtext_parsen(angebotsprofile.KL_STANDARD_NACHTEXT)
        self.assertTrue(kl["ausfuehrungszeitraum"])
        self.assertIsNone(kl["aufschiebende_bedingung"])
        pv = pdf_kontext.nachtext_parsen(angebotsprofile.PV_STANDARD_NACHTEXT)
        self.assertEqual(len(pv["fussnoten"]), 1)
        self.assertNotIn("[WIRTSCHAFTLICHKEIT]", json.dumps(pv, ensure_ascii=False))

    def test_summen_kontext_varianten(self):
        s = {"netto": 2000000, "ust": 0, "brutto": 2000000, "rabatt": 0, "endbetrag": 2000000}
        k = pdf_kontext.summen_kontext(s, 0, "", None)
        self.assertEqual([z["text"] for z in k["zeilen"]], ["Netto-Summe", "0,00 % USt. (§ 12 Abs. 3 UStG)"])
        self.assertEqual(k["box"], {"titel": "Gesamt-Betrag", "betrag": "20.000,00 €", "hinweis": ""})
        s = {"netto": 2000000, "ust": 0, "brutto": 2000000, "rabatt": 100000, "endbetrag": 1900000}
        k = pdf_kontext.summen_kontext(s, 0, "", None)
        self.assertEqual([z["text"] for z in k["zeilen"]], ["Netto-Summe", "0,00 % USt. (§ 12 Abs. 3 UStG)",
                                                             "Gesamt-Betrag", "− Rabatt"])
        self.assertEqual(k["box"], {"titel": "= Endbetrag", "betrag": "19.000,00 €", "hinweis": ""})
        self.assertEqual(pdf_kontext.kurzsatz("Satz eins. Satz zwei. Satz drei."), "Satz eins. Satz zwei.")
        self.assertEqual(pdf_kontext._prozent_text(55.0), "55")
        self.assertEqual(pdf_kontext._prozent_text(49.6), "49,6")
        self.assertEqual(k["box"]["betrag"], "19.000,00 €")
        self.assertEqual(k["rabatt"]["betrag"], "1.000,00 €")                  # Minus nur im Label
        for variante in ("Saubere Energie. Faire Raten. Maximale Freiheit.", "Saubere Energie – Faire Raten – "
                         "Maximale Freiheit", "saubere energie, faire raten, maximale freiheit!"):
            self.assertTrue(pdf_kontext.ist_slogan(variante), variante)
        self.assertFalse(pdf_kontext.ist_slogan("Finanzierung mit Sparkasse Duisburg"))
        self.assertFalse(pdf_kontext.ist_slogan(""))


class Migration(Basis):
    def test_migration_v36_texte_idempotent(self):
        s = self.s
        marker = s.query(Einstellung).filter(Einstellung.name == angebotsprofile.MARKER_V36_TEXTE).first()
        if marker is not None:
            self.skipTest("Migration v36 lief in dieser Datenbank bereits")
        vorher = {b.name: b.text for b in s.query(Textblock).filter(Textblock.art == "vortext")}
        try:
            meldungen = angebotsprofile.migration_v36_texte(s)
            s.commit()
            self.assertTrue(meldungen)
            for _sparte, name, neu in angebotsprofile.V36_VORTEXTE:
                block = s.query(Textblock).filter(Textblock.art == "vortext", Textblock.name == name).first()
                self.assertEqual(block.text, neu)
                if name in vorher and vorher[name].strip() != neu.strip():
                    hist = (s.query(Textblock).filter(Textblock.art == "vortext",
                                                      Textblock.name == name + angebotsprofile.V36_HISTORIE_SUFFIX)
                            .first())
                    self.assertIsNotNone(hist, name)
                    self.assertEqual(hist.text, vorher[name])
            wp = s.query(Textblock).filter(Textblock.art == "vortext", Textblock.name == "Friondo Standard").first()
            self.assertEqual(wp.text, vorher.get("Friondo Standard"))      # WP = heutiger Text
            self.assertEqual(angebotsprofile.migration_v36_texte(s), [])      # zweiter Lauf stumm
            # Angebot nutzt den neuen Text
            u = self.kontext(self.pv)["ueberblick"]
            self.assertTrue(u["schluss"][0]["text"].endswith("Ihren eigenen Strom erzeugen!"))
        finally:
            for _sparte, name, _neu in angebotsprofile.V36_VORTEXTE:
                block = s.query(Textblock).filter(Textblock.art == "vortext", Textblock.name == name).first()
                hist = (s.query(Textblock).filter(Textblock.art == "vortext",
                                                  Textblock.name == name + angebotsprofile.V36_HISTORIE_SUFFIX)
                        .first())
                if block is not None and name in vorher:
                    block.text = vorher[name]
                elif block is not None:
                    s.delete(block)
                if hist is not None:
                    s.delete(hist)
            s.query(Einstellung).filter(Einstellung.name == angebotsprofile.MARKER_V36_TEXTE).delete()
            s.commit()


# --- HTML ------------------------------------------------------------------------------------------------
class Html(Basis):
    def test_html_je_sparte(self):
        for angebot in (self.wp, self.pv, self.kl, self.wb):
            if angebot is None:
                continue
            html = self.html(angebot)
            for text in ("Festpreisangebot", "Alle Preise in EUR, netto", "Ihr Angebot im Überblick",
                         "Das Friondo-Team", "Auftragserteilung", "Vertragsbedingungen",
                         "Mitgliedschaften &amp; Zertifizierungen", angebot.nummer, "Mehr dazu im Interview"):
                self.assertIn(text, html, f"{angebot.nummer}: {text}")
            self.assertIn(f'class="pdf-sparte-{angebot.konfigurator_typ.lower()}"', html)
        self.assertIn("Vollmacht zur Beauftragung", self.html(self.wb)) if self.wb else None
        self.assertNotIn("Vollmacht zur Beauftragung", self.html(self.kl))
        self.assertIn("Hinweis zur Kältetechnik", self.html(self.kl))
        self.assertIn("0,00 % USt. (§ 12 Abs. 3 UStG)", self.html(self.pv))
        wp = self.html(self.wp)
        self.assertIn("− voraussichtliche KfW-Förderung", wp)
        self.assertIn("= Ihr Eigenanteil", wp)
        self.assertIn("Aufschiebende Bedingung:", wp)
        self.assertIn("Voraussichtliches Datum der Umsetzung:", wp)
        self.assertIn("Finanzierung mit Cloover", wp)
        if HAT_KFW and self.kontext(self.wp)["kfw"]:
            self.assertIn("Ihre KfW-Förderung", wp)
        self.assertNotIn("Ihre KfW-Förderung", self.html(self.pv))

    def test_html_ohne_externe_ressourcen_und_script(self):
        for angebot in (self.wp, self.pv):
            html = self.html(angebot)
            self.assertNotIn("<script", html.lower())
            for quelle in re.findall(r'(?:src|href)="([^"]+)"', html):
                if quelle.startswith(("https://", "http://")):
                    # Verweise (Award, AGB, Datenschutz, Cloover) sind erlaubt – aber nur als <a href>
                    self.assertTrue(re.search(r'<a [^>]*href="' + re.escape(quelle) + '"', html), quelle)
                else:
                    self.assertTrue(quelle.startswith(("file://", "mailto:", "data:")), quelle)
            self.assertNotIn("url(http", html)

    def test_templates_ohne_hex_farben(self):
        for name in EIGENE_TEMPLATES:
            text = (TEMPLATES / name).read_text(encoding="utf-8")
            self.assertFalse(HEX.search(text), f"Hex-Farbe in {name}")
            self.assertNotIn("<script", text)

    def test_signatur_im_html(self):
        signatur = {"bild_data_url": PNG_1PX, "name": "Max Mustermann", "zeitstempel": "16.10.2026 14:30",
                    "geraet": "Test"}
        html = self.html(self.wp, signatur=signatur)
        self.assertIn("Max Mustermann · signiert am 16.10.2026 14:30", html)
        self.assertIn(f'<img src="{PNG_1PX}"', html)
        self.assertNotIn("signiert am", self.html(self.wp))

    def test_demo_kontext_spiegelt_echte_struktur(self):
        echt = self.kontext(self.wp)
        for sparte in ("WP", "PV", "KL", "WB"):
            demo = pdf_kontext.demo_kontext(sparte)
            self.assertEqual(set(demo.keys()), set(echt.keys()), sparte)
            for key in ("angebot", "kunde", "empfaenger", "ueberblick", "summen", "auftrag", "bedingungen"):
                self.assertEqual(set(demo[key].keys()), set(echt[key].keys()), f"{sparte}: {key}")
            self.assertEqual(set(demo["gruppen"][0]["positionen"][0].keys()),
                             set(echt["gruppen"][0]["positionen"][0].keys()))
            self.assertNotIn("V36-Layout", json.dumps(demo, ensure_ascii=False))
            html = pdf_html.html_rendern(pdf_html.vorlage_fuer(sparte), demo)
            self.assertIn("Max Mustermann", html)
        self.assertEqual(pdf_kontext.demo_kontext("WP")["summen"]["endbetrag"], "42.830,55 €")


# --- PDF (Browser) --------------------------------------------------------------------------------------
@unittest.skipUnless(BROWSER["ok"], f"Browser-Druck nicht verfügbar: {BROWSER.get('fehler')}")
class Pdf(Basis):
    def test_pdf_je_sparte(self):
        erwartungen = {
            "WP": ["Netto-Summe", "30.245,43 €", "5.746,63 €", "35.992,06 €", "− Rabatt Aktionsnachlass",
                   "= Endbetrag", "35.492,06 €", "voraussichtliche KfW-Förderung", "= Ihr Eigenanteil",
                   "Auftragserteilung", "Aufschiebende Bedingung", "Vertragsbedingungen",
                   "Installationsvoraussetzungen"],
            "PV": ["0,00 % USt. (§ 12 Abs. 3 UStG)", "Gesamt-Betrag", "Vertragsbedingungen"],
            "KL": ["6.518,66 €", "1.238,55 €", "7.757,21 €", "Hinweis zur Kältetechnik"],
            "WB": ["5.435,85 €", "6.468,66 €", "Vollmacht zur Beauftragung", "SEPA-Lastschriftmandat",
                   "Installationsvoraussetzungen"],
        }
        for angebot in (self.wp, self.pv, self.kl, self.wb):
            if angebot is None:
                continue
            kontext = self.kontext(angebot)
            pdf = pdf_html.pdf_aus_kontext(kontext)
            self.assertLessEqual(len(pdf), 2_500_000, f"{angebot.nummer}: PDF zu groß")
            seiten = pdf_text(pdf)
            self.assertGreaterEqual(len(seiten), 5, angebot.nummer)
            gesamt = "\n".join(seiten)
            for text in erwartungen[angebot.konfigurator_typ]:
                self.assertIn(text, gesamt, f"{angebot.nummer}: {text}")
            self.assertRegex(seiten[1].replace("\n", " "), rf"SEITE\s*2\s*VON\s*{len(seiten)}")
            self.assertIn(angebot.nummer, seiten[0])
            self.assertIn("Ihr Angebot im Überblick", seiten[1])
            if angebot.konfigurator_typ == "KL":
                self.assertNotIn("Vollmacht zur Beauftragung", gesamt)
            if angebot.konfigurator_typ == "PV":
                self.assertNotIn("Ihre KfW-Förderung", gesamt)
                if kontext["wirtschaftlichkeit"]:
                    self.assertNotIn("Auf einen Blick", seiten[0])
            if angebot.konfigurator_typ == "WP" and kontext["kfw"]:
                self.assertIn("Ihre KfW-Förderung", gesamt)

    def test_pdf_kennzeichen_und_signatur(self):
        p = list(self.wp2.positionen)
        p[1].ep_flag = True
        p[2].bauseits = True
        p[3].alternativ = True
        p[3].alternativ_zu = "PV-Angebot AN-C-999999"
        p[4].rabatt_prozent = 10.0
        try:
            signatur = {"bild_data_url": PNG_1PX, "name": "Max Mustermann", "zeitstempel": "16.10.2026 14:30",
                        "geraet": "Test"}
            pdf = pdf_html.pdf_aus_kontext(self.kontext(self.wp2, signatur=signatur))
            gesamt = "\n".join(pdf_text(pdf))
            for text in ("EP.", "bauseits", "im PV-Angebot", "AN-C-999999 (PV) enthalten", "− Rabatt 10 %",
                         "Max Mustermann · signiert am 16.10.2026 14:30", "Unterschrift des Auftraggebers"):
                self.assertIn(text, gesamt, text)
        finally:
            p[1].ep_flag = False
            p[2].bauseits = False
            p[3].alternativ = False
            p[3].alternativ_zu = ""
            p[4].rabatt_prozent = None
            self.s.commit()


if __name__ == "__main__":
    unittest.main()
