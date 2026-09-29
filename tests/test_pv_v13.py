# Tests PLAN_V13 (PV-Konfigurator, Steuersatz je Angebot, Lieferschein).
# Laufen gegen die Entwicklungs-DB wie die übrigen Tests und räumen ihre
# Testdaten (Kunde „PV-Test v13“) am Ende wieder auf.
import json
import unittest
import warnings

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, import_preisliste, import_pv, pdf_export
from app import konfigurator as engine
from app import logik as logik_modul
from app import pv_auslegung
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Artikel, Erfassung, Kunde,
                        QUELLE_PV, Vorgang)

TEST_EMAIL = "pv-v13@test.local"


def pv_basis(**zusatz) -> dict:
    """Vollständiger PV-Bogen (Maximalbelegung, Satteldach, Fanggerüst …)."""
    antworten = {
        "PB01": "Maximalbelegung", "PO01": "EFH", "PO02": 1995, "PO03": "",
        "PO06": 4000, "PO07": 0, "PO08": "Nein", "PO05": "",
        "PD01": "Satteldach", "PD12": 30, "PD13": 0, "PD02": "Ja",
        "PD03": "Fanggerüst", "PD04": 6, "PD05": "Nein", "PD07": "Nein",
        "PD08": 12, "PD09": 13.65, "PD10": "",
        "PA01": "KG", "PA02": "Nein", "PA04": "Nein", "PA07": "Nein", "PA15": "Nein",
        "PA08": "Ja", "PA09": 10, "PA10": 10, "PA11": "Nein", "PA12": "Nein",
        "PA13": "Nein", "PA14": "", "S01": "warm", "S02": "",
    }
    antworten.update(zusatz)
    return antworten


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
        if cls.s.query(Artikel).filter(Artikel.quelle == QUELLE_PV).count() == 0:
            import_pv.import_ausfuehren(cls.s)
        cls.logik_voll, cls.bericht = logik_modul.neu_einlesen(cls.s)
        cls.logik = logik_modul.logik_fuer_sparte(cls.logik_voll, "PV")
        aufraeumen(cls.s)
        cls.kunde = Kunde(anrede="Herr", vorname="Paul", nachname="PV-Test v13",
                          strasse="Teststr. 1", plz="47139", ort="Duisburg",
                          email=TEST_EMAIL)
        cls.s.add(cls.kunde)
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()


# --- Phase 75 ---------------------------------------------------------------

class Phase75Fundament(Basis):
    def test_validierung_gruen(self):
        self.assertTrue(self.bericht.ok, self.bericht.fehler)

    def test_pv_artikel_import(self):
        pv = self.s.query(Artikel).filter(Artikel.quelle == QUELLE_PV,
                                          Artikel.aktiv.is_(True)).all()
        self.assertEqual(len(pv), 176)
        nach_nr = {a.pos_nr: a for a in pv}
        self.assertIn("Solar Fabrik Mono S4", nach_nr["PV001"].beschreibung)
        self.assertEqual(nach_nr["PV001"].e_preis_cent, 8775)
        self.assertEqual(nach_nr["PV001"].ek_cent, 6500)
        self.assertTrue(nach_nr["PV166"].ep_flag)          # Muster: Gateway „EP.“
        self.assertTrue(nach_nr["PV071"].beschreibung.startswith(
            "Sigenergy Hybrid System TP2 06/06"))
        # wiederholbar: zweiter Lauf ändert nichts
        diff = import_pv.berechne_diff(self.s)
        self.assertEqual((len(diff.neu), len(diff.geaendert), len(diff.entfallen)),
                         (0, 0, 0))

    def test_wp_import_fasst_pv_nicht_an(self):
        ergebnis = import_preisliste.lese_dateien()
        diff = import_preisliste.berechne_diff(self.s, ergebnis)
        self.assertFalse([a for a in diff.entfallen if a.quelle == QUELLE_PV])

    def test_ust_je_angebot(self):
        wp = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id)
        pv = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, sparte="PV")
        self.assertEqual((wp.ust_satz, pv.ust_satz), (19.0, 0.0))
        self.assertEqual(pv.konfigurator_typ, "PV")
        for a in (wp, pv):
            a.positionen.append(AngebotsPosition(sort=1, pos_nr="PV001", menge=10,
                                                 e_preis_cent=10000, ek_cent=6000))
        self.s.commit()
        su_wp, su_pv = wp.summen(), pv.summen()
        self.assertEqual((su_wp["netto"], su_wp["ust"], su_wp["brutto"]),
                         (100000, 19000, 119000))
        self.assertEqual((su_pv["netto"], su_pv["ust"], su_pv["brutto"],
                          su_pv["endbetrag"]), (100000, 0, 100000, 100000))
        # Rabatt bei 0 %: brutto = netto → DB sinkt um den vollen Rabatt
        pv.rabatt_cent = 5000
        self.assertEqual(pv.summen()["endbetrag"], 95000)
        self.assertEqual(pv.deckungsbeitrag()["db"], 100000 - 5000 - 60000)
        wp.rabatt_cent = 11900
        self.assertEqual(wp.deckungsbeitrag()["rabatt"], 10000)
        self.assertEqual(pv.ust_bezeichnung, "Umsatzsteuer 0 % (§ 12 Abs. 3 UStG)")
        self.assertEqual(wp.ust_bezeichnung, "19,00 % USt.")

    def test_bogen_pv(self):
        fragen = self.logik.fragen
        self.assertEqual(self.logik.seiten[0], "Belegung")
        for fid in ("PB01", "PO06", "PO07", "PO08", "PO09", "PA15", "PD11", "PD12", "PD13"):
            self.assertIn(fid, fragen)
        self.assertIn("Gaube", fragen["PD06"].text)
        # PO04 nur noch für Alt-Erfassungen sichtbar
        self.assertFalse(engine.ist_sichtbar(fragen["PO04"], {}, fragen))
        self.assertTrue(engine.ist_sichtbar(fragen["PO04"], {"PO04": 8000}, fragen))
        self.assertIsNone(engine.naechste_frage(self.logik, pv_basis()))

    def test_bogen_wp_aus_erfassung(self):
        client = TestClient(app)
        client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        vorgang = Vorgang(kunde_id=self.kunde.id)
        self.s.add(vorgang)
        self.s.flush()
        pv_e = Erfassung(kunde_id=self.kunde.id, benutzer_id=1, sparte="PV",
                         konfigurator_typ="PV", vorgang_id=vorgang.id)
        self.s.add(pv_e)
        self.s.commit()
        seite = self.logik.seiten.index("Objektdaten")
        daten = {"f_PO01": "EFH", "f_PO02": "1990", "f_PO03": "", "f_PO06": "4000",
                 "f_PO07_alt": "Aus WP-Erfassung ermitteln", "f_PO08": "Nein",
                 "f_PO05": "", "richtung": "weiter"}
        r = client.post(f"/erfassung/{pv_e.id}/seite/{seite}", data=daten,
                        follow_redirects=False)
        self.assertEqual(r.status_code, 200)        # Hinweis: keine WP-Erfassung
        self.assertIn("Keine WP-Erfassung", r.text)
        wp_e = Erfassung(kunde_id=self.kunde.id, benutzer_id=1, sparte="WP",
                         vorgang_id=vorgang.id,
                         antworten_json=json.dumps({"A03": 20000}))
        self.s.add(wp_e)
        self.s.commit()
        r = client.post(f"/erfassung/{pv_e.id}/seite/{seite}", data=daten,
                        follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.refresh(pv_e)
        antworten = json.loads(pv_e.antworten_json)
        self.assertEqual(antworten[pv_auslegung.SCHLUESSEL_WP_ABGELEITET]["strom_kwh"],
                         round(20000 / 3.5, 2))
