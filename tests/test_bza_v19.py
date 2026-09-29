# Tests PLAN_V14 als Phasen 95–97 (CLAUDE v19): BAFA-Stammdaten, neue
# Erfassungsfragen, BzA-Datenblatt (PDF) am Tool- und TAIFUN-WP-Angebot,
# KfW-gefördert am externen Eintrag. Räumt Kunden mit bza-v19@test.local auf.
import json
import unittest
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, bza_datenblatt
from app.db import SessionLocal, init_db
from app.logik import bafa_fuer_positionen, logik_einlesen
from app.main import app
from app.models import (Angebot, AngebotsPosition, Erfassung, Kunde, Vorgang,
                        angebot_status_setzen)

TEST_EMAIL = "bza-v19@test.local"
ANTWORTEN = {"O01": "EFH", "O05": 160, "A01": "Öl", "A02": 1985, "A20": 22,
             "A03": 24000, "H02": "Fußbodenheizung", "N11": "Nein",
             "K02": "Öl-, Kohle-, Gasetagen- oder Nachtspeicherheizung, funktionstüchtig",
             "K03": 28000, "K04": "Nein"}


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

    def kunde(self):
        k = Kunde(anrede="Herr", vorname="Bert", nachname="BzA-V19-Test",
                  strasse="Musterweg 12a", plz="47139", ort="Duisburg", email=TEST_EMAIL)
        self.s.add(k)
        self.s.flush()
        return k

    def tool_angebot(self, positionen, antworten=None, sparte="WP"):
        k = self.kunde()
        a = angebot_aufbau.angebot_anlegen(self.s, k.id, sparte=sparte)
        for i, (nr, text) in enumerate(positionen, 1):
            a.positionen.append(AngebotsPosition(sort=i, pos_nr=nr, bezeichnung=text,
                                                 beschreibung=text, menge=1,
                                                 e_preis_cent=1000000))
        antworten = ANTWORTEN if antworten is None else antworten
        from app import konfigurator as engine
        a.kfw_json = json.dumps(engine.kfw_daten(antworten))
        self.s.add(Erfassung(kunde_id=k.id, benutzer_id=1, sparte=sparte,
                             angebot_id=a.id, status="Erledigt",
                             antworten_json=json.dumps(antworten)))
        self.s.commit()
        return a

    def werte(self, blatt):
        return {f.name: f for _, felder in blatt.abschnitte for f in felder}


class Phase95Stammdaten(Basis):
    def test_logik_gruen_und_bafa(self):
        logik, bericht = logik_einlesen()
        self.assertEqual(bericht.fehler, [])
        self.assertEqual(bafa_fuer_positionen(logik, {"048"}).nummer, "16019892")
        self.assertEqual(bafa_fuer_positionen(logik, {"030", "055"}).nummer, "16019200")
        self.assertEqual(bafa_fuer_positionen(logik, {"031", "056"}).nummer, "16019199")
        self.assertIn("vorrat:hybrox21", {a.schluessel for a in logik.bafa_anlagen})
        self.assertIsNone(bafa_fuer_positionen(logik, {"065"}))

    def test_neue_fragen(self):
        from app import konfigurator as engine
        logik, _ = logik_einlesen()
        self.assertIn("Inbetriebnahmejahr", logik.fragen["A02"].text)
        self.assertEqual(logik.fragen["A20"].seite, "Alte Anlage")
        self.assertEqual(logik.fragen["N11"].antworten, ["Ja", "Nein"])
        self.assertEqual(engine.vorbelegung(logik.fragen["N11"], {}), "Nein")
        # Heizflächen = bestehende Frage H02 (keine Doppelfrage)
        self.assertIn("Fußbodenheizung", logik.fragen["H02"].antworten)

    def test_ersteller_parametrierung(self):
        seite = self.client.get("/parametrierung/bza-ersteller")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("1862718", seite.text)
        self.assertIn("Arnold-Overbeck-Str. 63-65", seite.text)


class Phase96Datenblatt(Basis):
    def test_paket_048_ffh_oel_1985(self):
        a = self.tool_angebot([("048", "WP 10 kW AWM"), ("120", "Demontage Altanlage")])
        blatt = bza_datenblatt.erstellen(self.s, a,
                                         ersteller=self.s.get(__import__("app.models", fromlist=["x"]).Benutzer, 1))
        w = self.werte(blatt)
        self.assertEqual(w["Anlagennummer (BAFA-Liste)"].wert, "16019892")
        self.assertIn("Compress CS3800iAW 10 OM-T", w["Gerätebezeichnung"].wert)
        self.assertEqual(w["Nennwärmeleistung"].wert, "10,00 kW")
        self.assertEqual(w["Vorlauftemperatur"].wert, "35 °C")
        self.assertEqual(w["Straße"].wert, "Musterweg")
        self.assertEqual(w["Hausnummer"].wert, "12a")
        self.assertEqual(w["Inbetriebnahme"].wert, "01.01.1985")
        self.assertEqual(w["Nennleistung"].wert, "22 kW")
        self.assertEqual(w["Art des Wärmeerzeugers"].wert, "Ölheizung")
        self.assertEqual(w["Im Zuge der Sanierung ausgebaut"].wert, "Ja")
        self.assertEqual(w["Kategorie Klimageschwindigkeitsbonus"].wert,
                         bza_datenblatt.KLIMA_KATEGORIE_OEL)
        self.assertTrue(w["Einkommensbonus"].wert.startswith("Ja – Stufe 40"))
        self.assertEqual(w["Wohneinheiten im Gebäude nach Abschluss des Vorhabens"].wert, "1")
        # Kosten = Endbetrag + nachrichtliche Werte aus dem Förder-Editor
        endbetrag = a.summen()["endbetrag"]
        self.assertEqual(w["Geplante förderfähige Kosten"].wert,
                         bza_datenblatt._euro(endbetrag))
        from app import kfw
        from app import logik as logik_modul
        logik, _ = logik_modul.hole_logik(self.s)
        p, _ = kfw.parameter_lesen(logik)
        e = kfw.eingaben_aus_antworten(json.loads(a.kfw_json), endbetrag)
        erg = kfw.ergebnis_fuer_angebot(p, e, a)
        self.assertEqual(w["nachrichtlich: davon förderfähig gemäß Höchstkostengrenze"].wert,
                         bza_datenblatt._euro(erg.foerderfaehig_cent))
        self.assertEqual(w["nachrichtlich: voraussichtlicher Zuschuss lt. Angebot"].wert,
                         bza_datenblatt._euro(erg.zuschuss_cent))
        self.assertEqual(w["Handwerkskammer-Betriebsnummer"].wert, "1862718")

    def test_klasse15_hk_fbh_und_fehlendes_jahr(self):
        antworten = {**ANTWORTEN, "H02": "Heizkörper und Fußbodenheizung"}
        antworten.pop("A02")
        a = self.tool_angebot([("030", "Außeneinheit weiß"), ("055", "AWMB")], antworten)
        w = self.werte(bza_datenblatt.erstellen(self.s, a))
        self.assertEqual(w["Anlagennummer (BAFA-Liste)"].wert, "16019200")
        self.assertIn("PRÜFPUNKT", w["Anlagennummer (BAFA-Liste)"].hinweis)
        self.assertEqual(w["Vorlauftemperatur"].wert, "55 °C")
        self.assertTrue(w["Inbetriebnahme"].fehlt)
        self.assertIn("Jahr fehlt", w["Inbetriebnahme"].wert)
        self.assertEqual(w["Im Zuge der Sanierung ausgebaut"].wert, "Nein")

    def test_pdf_und_buttons(self):
        a = self.tool_angebot([("048", "WP 10 kW AWM")])
        editor = self.client.get(f"/angebote/{a.id}").text
        self.assertIn("BzA-Datenblatt (PDF)", editor)
        dialog = self.client.get(f"/angebote/{a.id}/bza-datenblatt")
        self.assertEqual(dialog.status_code, 200)
        self.assertIn("16019892", dialog.text)
        pdf = self.client.get(f"/angebote/{a.id}/bza-datenblatt.pdf?we=1&ersteller=1")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertIn(f"BzA-Datenblatt-{a.nummer}.pdf", pdf.headers["content-disposition"])
        import io

        import pypdf
        text = "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(pdf.content)).pages)
        self.assertIn("keine KfW-Unterlage", text)
        self.assertIn("16019892", text)
        # PV-Angebot: kein Button, Route leitet um
        pv = self.tool_angebot([("PV001", "Modul")], {}, sparte="PV")
        self.assertNotIn("BzA-Datenblatt (PDF)", self.client.get(f"/angebote/{pv.id}").text)
        umleitung = self.client.get(f"/angebote/{pv.id}/bza-datenblatt", follow_redirects=False)
        self.assertEqual(umleitung.status_code, 303)

    def test_taifun_wp_geraet_pflicht_und_kfw_gefoerdert(self):
        k = self.kunde()
        erf = Erfassung(kunde_id=k.id, benutzer_id=1, sparte="WP", konfigurator_typ="WP",
                        status="In TAIFUN zu schreiben", typ="katalog",
                        antworten_json=json.dumps(ANTWORTEN))
        self.s.add(erf)
        self.s.commit()
        # „Extern erledigt“ mit KfW-gefördert = ja
        antwort = self.client.post(f"/erfassungen/{erf.id}/extern-erledigt",
                                   data={"taifun_nummer": "AN26V019", "endbetrag": "30.000,00",
                                         "datum": datetime.now().strftime("%Y-%m-%d"),
                                         "kfw_gefoerdert": "ja"}, follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        self.s.expire_all()
        a = self.s.get(Angebot, self.s.get(Erfassung, erf.id).angebot_id)
        self.assertEqual(a.kfw_gefoerdert, "ja")
        seite = self.client.get(f"/angebote/{a.id}").text
        self.assertIn("KfW-gefördert", seite)
        self.assertIn("BzA-Datenblatt (PDF)", seite)
        # ohne Gerät → zurück in den Dialog
        ohne = self.client.get(f"/angebote/{a.id}/bza-datenblatt.pdf", follow_redirects=False)
        self.assertEqual(ohne.status_code, 303)
        self.assertIn("bza-datenblatt", ohne.headers["location"])
        mit = self.client.get(f"/angebote/{a.id}/bza-datenblatt.pdf?geraet=049")
        self.assertTrue(mit.content.startswith(b"%PDF"))
        blatt = bza_datenblatt.erstellen(self.s, a, geraet_schluessel="049")
        w = self.werte(blatt)
        self.assertEqual(w["Anlagennummer (BAFA-Liste)"].wert, "16019894")
        self.assertEqual(w["Geplante förderfähige Kosten"].wert, "30.000,00 €")
        self.assertTrue(w["nachrichtlich: voraussichtlicher Zuschuss lt. Angebot"].wert
                        .endswith("€"))
        # nachträglich ändern
        self.client.post(f"/angebote/{a.id}/kfw-gefoerdert", data={"kfw_gefoerdert": "nein"})
        self.s.expire_all()
        self.assertEqual(self.s.get(Angebot, a.id).kfw_gefoerdert, "nein")

    def test_gewerk_seite_nutzt_generator(self):
        from app import projektierung as kern
        from app.models import Gewerk, Projekt
        a = self.tool_angebot([("048", "WP 10 kW AWM")])
        angebot_status_setzen(a, "Angenommen")
        self.s.commit()
        projekt = kern.projekt_anlegen(self.s, a, projektleiter_id=1)
        gewerk = kern.gewerk_anlegen(self.s, projekt, a, "WP")
        self.s.commit()
        try:
            seite = self.client.get(f"/projektierung/gewerk/{gewerk.id}/bza")
            self.assertEqual(seite.status_code, 200)
            self.assertIn("3. Geplante Wärmeversorgung", seite.text)
            self.assertIn("16019892", seite.text)
            self.assertIn("Stand BzA / KfW", seite.text)
            self.assertIn("Datenblatt-PDF", seite.text)
        finally:
            from tests.test_projektierung_v4 import aufraeumen as v4_aufraeumen
            import tests.test_projektierung_v4 as v4
            alt, v4.TEST_EMAIL = v4.TEST_EMAIL, TEST_EMAIL
            try:
                v4_aufraeumen(self.s)
            finally:
                v4.TEST_EMAIL = alt


if __name__ == "__main__":
    unittest.main()
