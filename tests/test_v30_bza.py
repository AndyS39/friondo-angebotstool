# v30 (PLAN_V18 Phase 148): BzA-Datenblatt – A20/„Nennleistung“ entfallen,
# Nennwärmeleistung als Zahl („9,5“ → „9,50 kW“), Zeile „Geplante förderfähige
# Kosten inkl. 10 % Puffer“ (Parameter bza_kosten_puffer_prozent, 0 = entfällt,
# übersteuerbar), kein Abschnitt 6 „Ersteller“, Parametrierungs-Seite
# „BzA-Datenblatt“. Räumt Kunden mit v30b-bza@test.local auf; der Puffer-
# Parameter wird am Ende auf den Wert von vorher zurückgesetzt.
import io
import json
import re
import unittest
import warnings

warnings.filterwarnings("ignore")

import pypdf
from fastapi.testclient import TestClient

from app import angebot_aufbau, bza_datenblatt
from app import konfigurator as engine
from app.db import SessionLocal, init_db
from app.logik import logik_einlesen
from app.main import app
from app.models import (Angebot, AngebotsPosition, Einstellung, Erfassung, Kunde,
                        Vorgang, einstellung_setzen)

TEST_EMAIL = "v30b-bza@test.local"
ANTWORTEN = {"O01": "EFH", "O05": 160, "A01": "Öl", "A02": 1985,
             "A03": 24000, "H02": "Fußbodenheizung", "N11": "Nein",
             "K02": "Öl-, Kohle-, Gasetagen- oder Nachtspeicherheizung, funktionstüchtig",
             "K03": 28000, "K04": "Nein"}
# Eine Position netto 23.823,53 € → 19 % USt 4.526,47 € → Endbetrag 28.350,00 €
NETTO_CENT_28350 = 2382353
PUFFER = bza_datenblatt.PUFFER_PARAMETER


def parameter_lesen(name: str):
    s = SessionLocal()
    try:
        zeile = s.query(Einstellung).filter(Einstellung.name == name).first()
        return None if zeile is None else zeile.wert
    finally:
        s.close()


def parameter_setzen(name: str, wert):
    """Parameter über eine frische Sitzung schreiben (None = Zeile entfernen)."""
    s = SessionLocal()
    try:
        if wert is None:
            s.query(Einstellung).filter(Einstellung.name == name).delete()
        else:
            einstellung_setzen(s, name, wert)
        s.commit()
    finally:
        s.close()


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.delete(v)
        s.delete(k)
    s.commit()


def pdf_flach(inhalt: bytes) -> str:
    text = "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(inhalt)).pages)
    return " ".join(text.split())


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        cls.puffer_vorher = parameter_lesen(PUFFER)
        parameter_setzen(PUFFER, "10")

    @classmethod
    def tearDownClass(cls):
        parameter_setzen(PUFFER, cls.puffer_vorher)
        aufraeumen(cls.s)
        cls.s.close()

    def kunde(self):
        k = Kunde(anrede="Herr", vorname="Bert", nachname="V30B BzA-Test",
                  strasse="Musterweg 12a", plz="47139", ort="Duisburg", email=TEST_EMAIL)
        self.s.add(k)
        self.s.flush()
        return k

    def tool_angebot(self, positionen, antworten=None, netto_cent=1000000):
        k = self.kunde()
        a = angebot_aufbau.angebot_anlegen(self.s, k.id, sparte="WP")
        for i, (nr, text) in enumerate(positionen, 1):
            a.positionen.append(AngebotsPosition(sort=i, pos_nr=nr, bezeichnung=text,
                                                 beschreibung=text, menge=1,
                                                 e_preis_cent=netto_cent))
        antworten = ANTWORTEN if antworten is None else antworten
        a.kfw_json = json.dumps(engine.kfw_daten(antworten))
        self.s.add(Erfassung(kunde_id=k.id, benutzer_id=1, sparte="WP",
                             angebot_id=a.id, status="Erledigt",
                             antworten_json=json.dumps(antworten)))
        self.s.commit()
        return a

    def werte(self, blatt):
        return {f.name: f for _, felder in blatt.abschnitte for f in felder}


class A20Entfernt(Basis):
    def test_a20_nicht_mehr_in_der_logik(self):
        from tests.test_regression import KONTROLL_SZENARIO
        logik, bericht = logik_einlesen()
        self.assertEqual(bericht.fehler, [])
        self.assertNotIn("A20", logik.fragen)
        self.assertEqual(engine.OPTIONALE_FRAGEN, {"O09", "O13"})
        # Kontrollszenario ohne A20 ist für „Angebot erzeugen“ vollständig
        szenario = {k: v for k, v in KONTROLL_SZENARIO.items() if k != "A20"}
        self.assertIsNone(engine.naechste_frage(logik, szenario))
        self.assertIsNone(engine.naechste_pflichtfrage(logik, szenario))
        self.assertEqual(engine.ampel_gruende(logik, szenario), [])
        # keine Vorbelegung/kein Sonderfall für A20 im Code
        for frage in logik.fragen.values():
            self.assertNotIn("A20", (frage.bedingung.frage_id or "") if frage.bedingung else "")

    def test_alte_erfassung_mit_a20_stuerzt_nicht_ab(self):
        """Bestands-Erfassungen tragen die alte Antwort weiter im JSON (keine
        Datenänderung): Protokoll und Datenblatt laufen, das Datenblatt zeigt
        keine Zeile „Nennleistung“ mehr; ein gespeichertes Angebots-Protokoll mit
        A20-Zeile wird im Editor weiter angezeigt."""
        logik, _ = logik_einlesen()
        antworten = {**ANTWORTEN, "A20": 22}
        protokoll = engine.protokoll(logik, antworten)
        self.assertNotIn("A20", {e["frage_id"] for e in protokoll})
        a = self.tool_angebot([("048", "WP 10 kW AWM")], antworten)
        a.protokoll_json = json.dumps(protokoll + [{
            "frage_id": "A20", "seite": "Alte Anlage",
            "frage": "Nennleistung der bestehenden Heizung in kW", "antwort": "22",
            "ampel_grund": ""}], ensure_ascii=False)
        self.s.commit()
        w = self.werte(bza_datenblatt.erstellen(self.s, a))
        self.assertNotIn("Nennleistung", w)
        self.assertEqual(w["Art des Wärmeerzeugers"].wert, "Ölheizung")
        self.assertEqual(w["Inbetriebnahme"].wert, "01.01.1985")
        editor = self.client.get(f"/angebote/{a.id}")
        self.assertEqual(editor.status_code, 200)
        self.assertIn("Nennleistung der bestehenden Heizung", editor.text)
        protokoll_pdf = self.client.get(f"/angebote/{a.id}/protokoll.pdf")
        self.assertEqual(protokoll_pdf.status_code, 200)


class Datenblatt(Basis):
    def test_kontrollwerte_puffer_und_ohne_abschnitt_6(self):
        a = self.tool_angebot([("048", "WP 10 kW AWM")], netto_cent=NETTO_CENT_28350)
        self.assertEqual(a.summen()["endbetrag"], 2835000)
        blatt = bza_datenblatt.erstellen(self.s, a)
        w = self.werte(blatt)
        self.assertEqual(w["Geplante förderfähige Kosten"].wert, "28.350,00 €")
        puffer = w["Geplante förderfähige Kosten inkl. 10 % Puffer"]
        self.assertEqual(puffer.wert, "31.185,00 €")
        self.assertEqual(puffer.schluessel, "kosten_puffer")
        self.assertEqual(puffer.hinweis, bza_datenblatt.PUFFER_HINWEIS)
        self.assertFalse(puffer.fehlt)
        # Reihenfolge in Abschnitt 4: Kosten → Puffer → nachrichtliche Zeilen
        kosten = next(felder for titel, felder in blatt.abschnitte if titel.startswith("4."))
        self.assertEqual([f.schluessel for f in kosten[:2]], ["kosten", "kosten_puffer"])
        # KfW rechnet weiter mit den echten Kosten (Höchstkostengrenze deckelt
        # bei 28.000 €) – der Puffer fließt nirgends in die Förderung ein
        from app import kfw
        from app import logik as logik_modul
        logik, _ = logik_modul.hole_logik(self.s)
        p, _ = kfw.parameter_lesen(logik)
        erg = kfw.ergebnis_fuer_angebot(
            p, kfw.eingaben_aus_antworten(json.loads(a.kfw_json), 2835000), a)
        self.assertEqual(w["nachrichtlich: davon förderfähig gemäß Höchstkostengrenze"].wert,
                         bza_datenblatt._euro(erg.foerderfaehig_cent))
        self.assertEqual(w["nachrichtlich: davon förderfähig gemäß Höchstkostengrenze"].wert,
                         "28.000,00 €")
        self.assertEqual(w["nachrichtlich: voraussichtlicher Zuschuss lt. Angebot"].wert,
                         bza_datenblatt._euro(erg.zuschuss_cent))
        # Abschnitte: 1–5, kein „6. Ersteller“
        titel = [t for t, _ in blatt.abschnitte]
        self.assertEqual([t[:2] for t in titel], ["1.", "2.", "3.", "4.", "5."])
        self.assertFalse([t for t in titel if "Ersteller" in t])
        for alt in ("Unternehmen", "Anschrift", "Handwerkskammer-Betriebsnummer",
                    "Ansprechpartner", "E-Mail", "Telefon", "Nennleistung"):
            self.assertNotIn(alt, w)
        # PDF-Text
        pdf = self.client.get(f"/angebote/{a.id}/bza-datenblatt.pdf")
        self.assertEqual(pdf.status_code, 200)
        flach = pdf_flach(pdf.content)
        self.assertIn("Geplante förderfähige Kosten 28.350,00 €", flach)
        self.assertIn("inkl. 10 % Puffer 31.185,00 €", flach)
        self.assertIn("Puffer für einen möglichen KfW-Ergänzungskredit", flach)
        self.assertNotIn("6. Ersteller", flach)
        self.assertIsNone(re.search(r"\b6\. ", flach))
        self.assertIsNone(re.search(r"\bNennleistung\b", flach))
        self.assertNotIn("1862718", flach)
        self.assertIn("keine KfW-Unterlage", flach)
        self.assertIn("5. Boni", flach)

    def test_nennwaermeleistung_eingaben(self):
        a = self.tool_angebot([("048", "WP 10 kW AWM")])
        for eingabe, erwartet in (("9,5", "9,50 kW"), ("9,5 kW", "9,50 kW"),
                                  ("9.5", "9,50 kW"), (" 12 KW ", "12,00 kW"),
                                  ("10,00", "10,00 kW")):
            blatt = bza_datenblatt.erstellen(self.s, a,
                                             uebersteuert={"nennwaermeleistung": eingabe})
            f = self.werte(blatt)["Nennwärmeleistung"]
            self.assertEqual(f.wert, erwartet, eingabe)
            self.assertEqual(blatt.eingabefehler, [], eingabe)
            self.assertNotIn("kW kW", f.wert)
        # Vorbelegung = Wert der BAFA-Anlage ohne Einheit; gleicher Wert = keine
        # Übersteuerung (kein Hinweis „manuell im Dialog geändert“)
        blatt = bza_datenblatt.erstellen(self.s, a, uebersteuert={"nennwaermeleistung": "10.00"})
        self.assertEqual(blatt.nennwaermeleistung_vorbelegung, "10.00")
        self.assertEqual(self.werte(blatt)["Nennwärmeleistung"].hinweis, "")
        # ungültig → Meldung, automatischer Wert bleibt
        blatt = bza_datenblatt.erstellen(self.s, a, uebersteuert={"nennwaermeleistung": "neun"})
        self.assertEqual(blatt.eingabefehler, ["Nennwärmeleistung: bitte nur die Zahl eingeben"])
        self.assertEqual(self.werte(blatt)["Nennwärmeleistung"].wert, "10,00 kW")
        self.assertEqual(bza_datenblatt.nennwaermeleistung_parsen("0"), None)
        self.assertEqual(bza_datenblatt.nennwaermeleistung_parsen(""), None)
        # Dialog: Zahlenfeld mit kW-Suffix, keine Ersteller-Auswahl, Meldung bei Fehler
        dialog = self.client.get(f"/angebote/{a.id}/bza-datenblatt")
        self.assertEqual(dialog.status_code, 200)
        feld = re.search(r'<input type="number" step="0\.01" min="0" inputmode="decimal"\s+'
                         r'name="f_nennwaermeleistung"[^>]*value="10\.00"', dialog.text)
        self.assertIsNotNone(feld)
        self.assertIn('class="feld-suffix dezent"', dialog.text)
        self.assertNotIn('name="ersteller"', dialog.text)
        self.assertNotIn("Ersteller", dialog.text)
        self.assertIn('data-kw="10.00"', dialog.text)
        fehler = self.client.get(f"/angebote/{a.id}/bza-datenblatt?f_nennwaermeleistung=neun")
        self.assertIn("Nennwärmeleistung: bitte nur die Zahl eingeben", fehler.text)
        self.assertIn('value="neun"', fehler.text)   # Eingabe bleibt zum Korrigieren stehen
        umleitung = self.client.get(f"/angebote/{a.id}/bza-datenblatt.pdf?f_nennwaermeleistung=neun",
                                    follow_redirects=False)
        self.assertEqual(umleitung.status_code, 303)
        self.assertIn("bitte+nur+die+Zahl", umleitung.headers["location"])
        self.assertIn("f_nennwaermeleistung=neun", umleitung.headers["location"])
        pdf = self.client.get(f"/angebote/{a.id}/bza-datenblatt.pdf?f_nennwaermeleistung=9,5")
        self.assertEqual(pdf.status_code, 200)
        flach = pdf_flach(pdf.content)
        self.assertIn("9,50 kW", flach)
        self.assertNotIn("10,00 kW", flach)
        self.assertIn("manuell im Dialog geändert", flach)

    def test_puffer_parameter_0_und_15(self):
        a = self.tool_angebot([("048", "WP 10 kW AWM")], netto_cent=NETTO_CENT_28350)
        try:
            parameter_setzen(PUFFER, "0")
            w = self.werte(bza_datenblatt.erstellen(self.s, a))
            self.assertFalse([n for n in w if "Puffer" in n])
            pdf = self.client.get(f"/angebote/{a.id}/bza-datenblatt.pdf")
            self.assertNotIn("Puffer", pdf_flach(pdf.content))
            parameter_setzen(PUFFER, "15")
            blatt = bza_datenblatt.erstellen(self.s, a)
            w = self.werte(blatt)
            self.assertEqual(blatt.puffer_prozent, 15.0)
            # 28.350 × 1,15 = 32.602,50 → kaufmännisch auf volle Euro: 32.603,00 €
            self.assertEqual(w["Geplante förderfähige Kosten inkl. 15 % Puffer"].wert,
                             "32.603,00 €")
            parameter_setzen(PUFFER, "12,5")
            w = self.werte(bza_datenblatt.erstellen(self.s, a))
            self.assertIn("Geplante förderfähige Kosten inkl. 12,5 % Puffer", w)
            self.assertEqual(bza_datenblatt.puffer_cent(2835000, 10), 3118500)
            self.assertEqual(bza_datenblatt.puffer_cent(1000050, 10), 1100100)   # 11.000,55 → 11.001
            self.assertEqual(bza_datenblatt.puffer_cent(1000040, 10), 1100000)   # 11.000,44 → 11.000
        finally:
            parameter_setzen(PUFFER, "10")

    def test_uebersteuerte_kosten_und_puffer(self):
        a = self.tool_angebot([("048", "WP 10 kW AWM")], netto_cent=NETTO_CENT_28350)
        w = self.werte(bza_datenblatt.erstellen(self.s, a, uebersteuert={"kosten": "30.000,00 €"}))
        self.assertEqual(w["Geplante förderfähige Kosten"].wert, "30.000,00 €")
        puffer = w["Geplante förderfähige Kosten inkl. 10 % Puffer"]
        self.assertEqual(puffer.wert, "33.000,00 €")
        self.assertIn("übersteuerten Kosten", puffer.hinweis)
        # Puffer selbst übersteuert → gewinnt
        w = self.werte(bza_datenblatt.erstellen(
            self.s, a, uebersteuert={"kosten": "30000", "kosten_puffer": "34.000,00 €"}))
        self.assertEqual(w["Geplante förderfähige Kosten inkl. 10 % Puffer"].wert, "34.000,00 €")
        self.assertEqual(w["Geplante förderfähige Kosten inkl. 10 % Puffer"].hinweis,
                         bza_datenblatt.HINWEIS_MANUELL)
        # KfW-Zeilen rechnen weiter mit den echten Kosten (wie ohne Übersteuerung)
        blatt = bza_datenblatt.erstellen(self.s, a)
        ohne = self.werte(blatt)
        for name in ("nachrichtlich: davon förderfähig gemäß Höchstkostengrenze",
                     "nachrichtlich: voraussichtlicher Zuschuss lt. Angebot"):
            self.assertEqual(w[name].wert, ohne[name].wert)
        # jedes Feld trägt einen eindeutigen Schlüssel, Puffer und Nennwärmeleistung dabei
        schluessel = [f.schluessel for _, felder in blatt.abschnitte for f in felder]
        self.assertEqual(len(schluessel), len(set(schluessel)))
        self.assertIn("kosten_puffer", schluessel)
        self.assertIn("nennwaermeleistung", schluessel)
        self.assertNotIn("ansprechpartner", schluessel)
        self.assertNotIn("nennleistung_alt", schluessel)
        # Gewerk-Seite nutzt dieselben Abschnitte (ohne Abschnitt 6)
        gruppen = [g for g, _ in bza_datenblatt.fuer_gewerk_seite(blatt)]
        self.assertEqual(len(gruppen), 5)
        self.assertFalse([g for g in gruppen if "Ersteller" in g])

    def test_parametrierung_seite_bza_datenblatt(self):
        seite = self.client.get("/parametrierung/bza-ersteller")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("BzA-Datenblatt", seite.text)
        self.assertIn('name="puffer_prozent"', seite.text)
        self.assertIn('value="10"', seite.text)
        for alt in ("Ersteller-Person", "1862718", "Arnold-Overbeck", "BzA-Ersteller"):
            self.assertNotIn(alt, seite.text)
        try:
            r = self.client.post("/parametrierung/bza-ersteller",
                                 data={"puffer_prozent": "12,5"}, follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("BzA-Datenblatt+gespeichert", r.headers["location"])
            self.assertEqual(parameter_lesen(PUFFER), "12.5")
            self.assertIn('value="12.5"', self.client.get("/parametrierung/bza-ersteller").text)
            r = self.client.post("/parametrierung/bza-ersteller",
                                 data={"puffer_prozent": "abc"}, follow_redirects=False)
            self.assertIn("zwischen+0+und+100", r.headers["location"])
            self.assertEqual(parameter_lesen(PUFFER), "12.5")
            r = self.client.post("/parametrierung/bza-ersteller",
                                 data={"puffer_prozent": "0"}, follow_redirects=False)
            self.assertEqual(parameter_lesen(PUFFER), "0")
        finally:
            parameter_setzen(PUFFER, "10")


if __name__ == "__main__":
    unittest.main()
