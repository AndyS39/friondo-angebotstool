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


# --- Phase 76 ---------------------------------------------------------------

def bedarf_fall(max_module=40, **zusatz) -> dict:
    """Plan-Beispiel: HH 4.000 + WP aus 20.000 kWh Gas + WB 2.500."""
    return pv_basis(PB01="Bedarfsorientierte Belegung", PO06=4000,
                    PO07="Aus WP-Erfassung ermitteln", PO08="Ja", PO09=2500,
                    PD12=max_module, PD07="Ja",
                    **{pv_auslegung.SCHLUESSEL_WP_ABGELEITET:
                       {"erfassung_id": 0, "verbrauch_kwh": 20000,
                        "strom_kwh": round(20000 / 3.5, 2)}}, **zusatz)


class Phase76Auslegung(Basis):
    def test_bedarfsauslegung_plan_beispiel(self):
        a = pv_auslegung.auslegen(self.logik, bedarf_fall())
        self.assertAlmostEqual(a.bedarf_kwh, 16271.43, delta=0.05)
        self.assertAlmostEqual(a.bedarf_kwp, 16.95, delta=0.005)
        self.assertEqual((a.bedarf_module, a.module, a.gedeckelt), (38, 38, False))
        self.assertAlmostEqual(a.kwp, 17.29, places=2)
        self.assertIn("16.271 kWh", a.herleitung)

    def test_deckel_maximalbelegung(self):
        a = pv_auslegung.auslegen(self.logik, bedarf_fall(max_module=30))
        self.assertEqual((a.module, a.gedeckelt), (30, True))
        self.assertIn("gedeckelt", pv_auslegung.auslegungs_text(a))

    def test_strings(self):
        a = pv_auslegung.auslegen(self.logik, bedarf_fall())      # 38 Module, 2 Seiten
        self.assertEqual((a.max_je_string, a.strings), (27, 2))
        a = pv_auslegung.auslegen(self.logik, pv_basis(PD12=60))  # 1 Seite
        self.assertEqual(a.strings, 3)
        a = pv_auslegung.auslegen(self.logik, pv_basis(PD12=10, PD07="Ja"))
        self.assertEqual(a.strings, 2)

    def test_wr_und_speicher(self):
        # 38 Module = 17,29 kWp ÷ 1,2 = 14,4 kW → SigenStor 15; Speicher 10 → 15/10
        a = pv_auslegung.auslegen(self.logik, bedarf_fall(PA10=10))
        self.assertEqual((a.serie, a.wr_kw, a.speicher_stufe, a.kombi_nr),
                         ("SigenStor", 15.0, 10.0, "PV089"))
        a = pv_auslegung.auslegen(self.logik, bedarf_fall(PA10=11))
        self.assertEqual((a.speicher_stufe, a.kombi_nr), (12.0, "PV090"))
        # Musterangebot AN261699: 13 Module (5,92 kWp) → TP2 06/06
        a = pv_auslegung.auslegen(self.logik, pv_basis(PD12=13, PA10=6))
        self.assertEqual((a.kombi_text, a.kombi_nr), ("Hybrid System TP2 06/06", "PV071"))
        # 18 Module (8,19 kWp) ÷ 1,2 = 6,8 → TP2 08; Speicher 10 → 08/10
        a = pv_auslegung.auslegen(self.logik, pv_basis(PD12=18, PA10=10))
        self.assertEqual(a.kombi_nr, "PV073")

    def test_ampel_gruende(self):
        gruende = engine.ampel_gruende(self.logik, pv_basis(PD12=80))  # 36,4 kWp
        self.assertTrue(any("WR-Bedarf über 30" in g for g in gruende), gruende)
        gruende = engine.ampel_gruende(self.logik, pv_basis(PD12=13, PA10=25))
        self.assertTrue(any("nicht im Sortiment" in g for g in gruende), gruende)
        self.assertIn("Dachart nicht konfigurierbar",
                      engine.ampel_gruende(self.logik, pv_basis(PD01="Sonstige")))
        self.assertTrue(engine.ampel_gruende(self.logik, pv_basis(PD03="Vollgerüst")))
        self.assertTrue(engine.ampel_gruende(self.logik, pv_basis(PD03="Sonstiges")))
        self.assertEqual(engine.ampel_gruende(self.logik, pv_basis()), [])
        # Belegungsart-Konflikt: Bedarf ohne Maximalangabe (Dachbelegung = 0)
        self.assertIn("Maximale Modulanzahl fehlt (Dachbelegung)",
                      engine.ampel_gruende(self.logik, bedarf_fall(max_module=0)))

    def test_protokoll_mit_auslegung(self):
        prot = engine.protokoll(self.logik, bedarf_fall())
        zeile = [e for e in prot if e["frage"] == "Auslegung PV"]
        self.assertTrue(zeile)
        self.assertIn("38 Module", zeile[0]["antwort"])
        self.assertIn("SigenStor 15/", zeile[0]["antwort"])


# --- Phase 77 ---------------------------------------------------------------

def mengen(positionen) -> dict:
    ergebnis: dict = {}
    for p in positionen:
        if p["pos_nr"]:
            ergebnis[p["pos_nr"]] = ergebnis.get(p["pos_nr"], 0) + p["menge"]
    return ergebnis


class Phase77Positionen(Basis):
    def pos(self, antworten):
        return pv_auslegung.positionen_zusammenstellen(self.logik, antworten, self.s)

    def test_maximalbelegung_quer(self):
        pos = self.pos(pv_basis(PD12=30, PD13=4, PA10=10))
        m = mengen(pos)
        self.assertEqual((m["PV001"], m["PV162"], m["PV013"], m["PV163"]),
                         (30, 26, 4, 30))
        self.assertEqual(pos[0]["pos_nr"], "PV001")                 # Pos. 1 Module
        self.assertEqual(pos[1]["pos_nr"], "PV079")   # Pos. 2: 13,65 kWp ÷ 1,2 → TP2 12/10
        self.assertIn("Die angebotenen PV-Modultypen", pos[0]["beschreibung"])
        self.assertTrue(pos[0]["gruppe"].startswith("Komplettpaket 13,65 kWp PV-Anlage"))
        self.assertEqual(m["PV161"], 2)                            # 30 Module → 2 Strings
        self.assertEqual(m["PV169"], 1)                            # DC-ÜSS 2 MPPT
        self.assertEqual(m["PV164"], 1)                            # Fanggerüst
        for immer in ("PV065", "PV167", "PV170", "PV171"):
            self.assertIn(immer, m)
        self.assertTrue([p for p in pos if p["pos_nr"] == "PV065"][0]["ep_flag"])
        zeile = [p for p in pos if p["bezeichnung"] == "Auslegung der PV-Anlage"]
        self.assertTrue(zeile and zeile[0]["e_preis_cent"] == 0)
        self.assertNotIn("PV010", m)                               # keine Optimierer
        self.assertNotIn("014", m)

    def test_walm_flach_tigo(self):
        m = mengen(self.pos(pv_basis(PD01="Walmdach", PD12=20)))
        self.assertEqual((m["PV162"], m.get("PV013", 0)), (20, 0))
        m = mengen(self.pos(pv_basis(PD01="Flachdach", PD11="Süd", PD12=20)))
        self.assertEqual(m["PV014"], 20)
        self.assertNotIn("PV162", m)
        m = mengen(self.pos(pv_basis(PD05="Ja", PD06=5)))
        self.assertEqual(m["PV010"], 5)

    def test_elektro_kette(self):
        m = mengen(self.pos(pv_basis(PA02="Ja", PA03="2-Feld", PA07="Ja")))
        self.assertIn("PV123", m)
        self.assertNotIn("PV132", m)          # UV nur ohne neue ZV
        m = mengen(self.pos(pv_basis(PA02="Nein", PA07="Ja", PA15="Ja", PA08="Nein")))
        self.assertEqual((m.get("PV132"), m.get("PV052"), m.get("PV049")), (1, 1, 1))
        self.assertTrue(engine.ampel_gruende(self.logik,
                                             pv_basis(PA02="Ja", PA03="Sonstige")))
        self.assertTrue(engine.ampel_gruende(self.logik,
                                             pv_basis(PA02="Ja", PA03="4-Feld")))

    def test_dc_ueberspannungsschutz(self):
        # Strings 3 (60 Module, 1 Seite) → Typ 2, 3 MPPT
        m = mengen(self.pos(pv_basis(PD12=60, PA10=10)))
        self.assertEqual((m.get("PV023"), m.get("PV169")), (1, None))
        # Strings 4 (100 Module) → 2 × 2 MPPT (WR-Ampel wegen 45,5 kWp)
        a = pv_auslegung.auslegen(self.logik, pv_basis(PD12=100))
        self.assertEqual(a.strings, 4)
        m = mengen(self.pos(pv_basis(PD12=100)))
        self.assertEqual(m.get("PV169"), 2)
        gruende = engine.ampel_gruende(self.logik, pv_basis(PD12=130))
        self.assertTrue(any("mehr als 4 Strings" in g for g in gruende), gruende)

    def test_fit_for_future_und_enni(self):
        m = mengen(self.pos(pv_basis(PA11="Ja", PA12="Ja")))
        self.assertEqual({k: m.get(k) for k in ("014", "015", "016", "017")},
                         {"014": 1, "015": 1, "016": 1, "017": None})
        from app import angebotsprofile
        kunde = Kunde(nachname="PV-Test v13 Enni", email=TEST_EMAIL,
                      vertriebskanal="Enni Energie")
        self.s.add(kunde)
        self.s.commit()
        angebot = angebot_aufbau.angebot_anlegen(
            self.s, kunde.id, antworten=pv_basis(PA11="Ja"), logik=self.logik,
            sparte="PV")
        nummern = {p.pos_nr: p for p in angebot.positionen}
        self.assertEqual(nummern["015"].e_preis_cent, angebotsprofile.ENNI_SONDERPREIS_CENT)
        self.assertNotIn("014", nummern)
        self.assertIn("162", nummern)
        self.assertEqual(angebot.ust_satz, 0.0)
        self.assertEqual(angebot.kfw_json, "{}")

    def test_kombi_pv_wp(self):
        from app import kombi_versand
        vorgang = Vorgang(kunde_id=self.kunde.id)
        self.s.add(vorgang)
        self.s.flush()
        wp = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id)
        pv = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, sparte="PV")
        stamm = {a.pos_nr: a for a in self.s.query(Artikel)
                 .filter(Artikel.pos_nr.in_(["104", "PV123"]))}
        for angebot, nr in ((wp, "104"), (pv, "PV123")):
            angebot.vorgang_id = vorgang.id
            angebot.positionen.append(AngebotsPosition(
                sort=1, pos_nr=nr, bezeichnung=stamm[nr].bezeichnung,
                beschreibung=stamm[nr].beschreibung, menge=1,
                e_preis_cent=stamm[nr].e_preis_cent))
        self.s.commit()
        self.assertEqual(kombi_versand.doppelte_artikel([wp, pv]), ["104/PV123"])
        hinweise = kombi_versand.gewerke_hinweise(self.s, vorgang, [wp, pv])
        self.assertTrue(any("(PV)" in h and "ins WP-Angebot" in h for h in hinweise), hinweise)
        self.assertTrue(any("(WP)" in h and "ins PV-Angebot" in h for h in hinweise), hinweise)


# --- Phase 78 ---------------------------------------------------------------

class Phase78PdfWirtschaftlichkeit(Basis):
    def test_wirtschaftlichkeit_zahlen(self):
        w = pv_auslegung.wirtschaftlichkeit(self.logik, 13.65, True, False, 2000000)
        self.assertAlmostEqual(w["ertrag"], 13104.0)
        self.assertEqual(w["quote"], 65)
        self.assertAlmostEqual(w["ersparnis"], 8517.6 * 0.32 + 4586.4 * 0.078, places=2)
        self.assertAlmostEqual(w["amortisation"], 20000 / w["ersparnis"], places=3)
        w_hems = pv_auslegung.wirtschaftlichkeit(self.logik, 13.65, True, True, 2000000)
        self.assertEqual(w_hems["quote"], 75)

    def test_pv_pdf(self):
        import pypdf
        angebot = angebot_aufbau.angebot_anlegen(
            self.s, self.kunde.id, antworten=pv_basis(PD12=30, PA10=10, PA11="Ja"),
            logik=self.logik, sparte="PV")
        pfad = pdf_export.pdf_fuer_angebot(self.s, angebot)
        text = "\n".join(s.extract_text() for s in pypdf.PdfReader(str(pfad)).pages)
        pfad.unlink(missing_ok=True)
        su = angebot.summen()
        self.assertEqual((su["ust"], su["brutto"]), (0, su["netto"]))
        self.assertIn("Umsatzsteuer 0 % (§ 12 Abs. 3 UStG)", text)
        self.assertIn("Ihr individuelles PV-Angebot zum Festpreis", text)
        self.assertIn("Komplettpaket 13,65 kWp PV-Anlage", text)
        self.assertIn("Anwendung des Nullsteuersatzes", text)
        self.assertIn("Ihre Beispielrechnung", text)
        self.assertIn("13.104 kWh", text)
        self.assertIn("Amortisation", text)
        self.assertIn("keine Garantie", text)
        self.assertNotIn("KfW-Förderung", text)
        self.assertNotIn("Eigenanteil", text)
        self.assertIn("Auslegung: 30 Module", text)

    def test_db_schwellen_je_sparte(self):
        from app.models import db_schwellen, einstellung_setzen
        allgemein = db_schwellen(self.s)
        self.assertEqual(db_schwellen(self.s, "PV"), allgemein)     # Start: PV wie WP
        einstellung_setzen(self.s, "db_ampel_rot_unter_PV", "3000")
        einstellung_setzen(self.s, "db_ampel_gruen_ueber_PV", "4000")
        self.s.commit()
        try:
            self.assertEqual(db_schwellen(self.s, "PV"), (3000, 4000))
            self.assertEqual(db_schwellen(self.s, "WP"), allgemein)
            from app.routers.meine_angebote import _db_ampel
            self.assertEqual(_db_ampel(self.s, 350000, "PV"), "orange")
            self.assertEqual(_db_ampel(self.s, 450000, "PV"), "gruen")
        finally:
            einstellung_setzen(self.s, "db_ampel_rot_unter_PV", "")
            einstellung_setzen(self.s, "db_ampel_gruen_ueber_PV", "")
            self.s.commit()


# --- Phase 79 ---------------------------------------------------------------

class Phase79Prozess(Basis):
    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})

    def neue_erfassung(self, antworten, status="Entwurf"):
        e = Erfassung(kunde_id=self.kunde.id, benutzer_id=1, sparte="PV",
                      konfigurator_typ="PV", status=status,
                      antworten_json=json.dumps(antworten, ensure_ascii=False))
        self.s.add(e)
        self.s.commit()
        return e

    def test_absenden_gruen_und_angebot_erzeugen(self):
        e = self.neue_erfassung(pv_basis(PD12=18, PA10=10, PA11="Ja"))
        r = self.client.post(f"/erfassung/{e.id}/absenden", follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.s.refresh(e)
        self.assertEqual((e.ampel, e.status), ("gruen", "Neu"))
        r = self.client.get(f"/erfassungen/{e.id}/angebot-erzeugen", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.refresh(e)
        angebot = self.s.get(Angebot, e.angebot_id)
        self.assertEqual((angebot.konfigurator_typ, angebot.ust_satz), ("PV", 0.0))
        self.assertIn("PV073", {p.pos_nr for p in angebot.positionen})   # TP2 08/10
        # Anhänge/Vollmacht über die PA-Fragen (HEMS-Broschüre bei PA11 = Ja)
        from app import anhaenge
        dateien = [x.datei for x in anhaenge.fuer_angebot(self.logik_voll, angebot)]
        self.assertIn("Friondo HEMS.pdf", dateien)
        self.assertFalse(anhaenge.vollmacht_erforderlich(angebot))
        # Editor öffnet PV-Angebot mit 0-%-Zeile
        r = self.client.get(f"/angebote/{angebot.id}")
        self.assertIn("Umsatzsteuer 0 % (§ 12 Abs. 3 UStG)", r.text)
        self.assertIn("kein KfW-Förderblock", r.text)

    def test_detailseite_mit_auslegung(self):
        """Bugfix 30.09.2026: Erfassungs-Detail einer vollständigen PV-
        Katalog-Erfassung warf 500 (Abschnitt „Auslegung“ ist keine
        Bogenseite, seiten.index(...) → ValueError)."""
        e = self.neue_erfassung(pv_basis(PD12=18, PA10=10))
        from app import konfigurator as engine
        self.assertIn("Auslegung", {p["seite"] for p in engine.protokoll(
            self.logik, json.loads(e.antworten_json))})
        r = self.client.get(f"/erfassungen/{e.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Auslegung PV", r.text)
        self.assertIn("berechnet", r.text)
        # Protokoll-PDF und Prüfseite mit derselben Erfassung
        self.assertEqual(self.client.get(f"/erfassungen/{e.id}/protokoll.pdf").status_code, 200)
        self.assertLess(self.client.get(f"/erfassung/{e.id}/pruefen").status_code, 500)

    def test_ampel_orange_bleibt_individuell(self):
        e = self.neue_erfassung(pv_basis(PD03="Vollgerüst"))
        self.client.post(f"/erfassung/{e.id}/absenden", follow_redirects=False)
        self.s.refresh(e)
        self.assertEqual((e.ampel, e.status), ("orange", "Individuell – zu prüfen"))

    def test_altfall_erneut_pruefen(self):
        alt = {k: v for k, v in pv_basis().items()
               if k not in ("PB01", "PO06", "PO07", "PO08", "PD12", "PD13", "PA15")}
        alt["PO04"] = 9000
        e = self.neue_erfassung(alt, status="In TAIFUN zu schreiben")
        r = self.client.post(f"/erfassungen/{e.id}/erneut-pruefen", follow_redirects=False)
        self.s.refresh(e)
        self.assertEqual(e.status, "In TAIFUN zu schreiben")        # unberührt
        self.assertIn("unvollst", r.headers["location"])
        # PO04 bleibt im Protokoll des Altfalls sichtbar
        self.assertIn("PO04", {x["frage_id"] for x in engine.protokoll(self.logik, alt)})
        e.antworten_json = json.dumps(dict(alt, PB01="Maximalbelegung", PO06=4000, PO07=0,
                                           PO08="Nein", PD12=20, PD13=0, PA15="Nein"))
        self.s.commit()
        self.client.post(f"/erfassungen/{e.id}/erneut-pruefen", follow_redirects=False)
        self.s.refresh(e)
        self.assertEqual((e.ampel, e.status), ("gruen", "Neu"))

    def test_vollmacht_bei_pa12(self):
        angebot = angebot_aufbau.angebot_anlegen(
            self.s, self.kunde.id, antworten=pv_basis(PA12="Ja"), logik=self.logik,
            sparte="PV")
        from app import anhaenge
        self.assertTrue(anhaenge.vollmacht_erforderlich(angebot))


# --- Phase 80 ---------------------------------------------------------------

class Phase80Lieferschein(Basis):
    def pdf_text(self, antwort) -> str:
        import io

        import pypdf
        return "\n".join(s.extract_text() for s in
                         pypdf.PdfReader(io.BytesIO(antwort.content)).pages)

    def test_lieferschein_ohne_preise(self):
        client = TestClient(app)
        client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        angebot = angebot_aufbau.angebot_anlegen(
            self.s, self.kunde.id, antworten=pv_basis(PD12=20, PA10=10), logik=self.logik,
            sparte="PV")
        angebot.positionen.append(AngebotsPosition(
            sort=90, pos_nr="PV017", beschreibung="Demontage PV-Module ALTERNATIV",
            menge=3, e_preis_cent=8060, alternativ=True))
        angebot.positionen.append(AngebotsPosition(
            sort=91, pos_nr="PV022", beschreibung="SAT Anlage versetzen BAUSEITS",
            menge=1, e_preis_cent=39500, bauseits=True))
        self.s.commit()
        r = client.get(f"/angebote/{angebot.id}/lieferschein.pdf", follow_redirects=False)
        self.assertEqual(r.status_code, 303)                   # nur „Angenommen“
        angebot.status = "Angenommen"
        self.s.commit()
        r = client.get(f"/angebote/{angebot.id}/lieferschein.pdf")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f"LS-{angebot.nummer}.pdf", r.headers.get("content-disposition", ""))
        text = self.pdf_text(r)
        self.assertIn("L I E F E R S C H E I N", text)
        self.assertIn("Ware vollständig erhalten", text)
        self.assertIn("Ausführungsort: Teststr. 1, 47139 Duisburg", text)
        self.assertIn("Solar Fabrik Mono S4", text)
        self.assertIn("20,00", text)                               # Menge Module
        for verboten in ("€", "Netto", "Summe", "Rabatt", "Förder", "Energy Gateway",
                         "ALTERNATIV", "BAUSEITS", "Auslegung der PV-Anlage", "87,75"):
            self.assertNotIn(verboten, text)
        # Button im Editor
        r = client.get(f"/angebote/{angebot.id}")
        self.assertIn("Lieferschein (PDF)", r.text)

    def test_lieferschein_wp(self):
        from tests.test_regression import KONTROLL_SZENARIO
        client = TestClient(app)
        client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        angebot = angebot_aufbau.angebot_anlegen(
            self.s, self.kunde.id, antworten=dict(KONTROLL_SZENARIO), logik=self.logik_voll)
        angebot.status = "Angenommen"
        self.s.commit()
        r = client.get(f"/angebote/{angebot.id}/lieferschein.pdf")
        self.assertEqual(r.status_code, 200)
        text = self.pdf_text(r)
        self.assertIn("L I E F E R S C H E I N", text)
        self.assertNotIn("€", text)


# --- Phase 81 (Abnahme) -----------------------------------------------------

class Phase81Abnahme(Basis):
    def test_kombi_wp_pv_alternativ_hems(self):
        """WP- und PV-Angebot im selben Vorgang mit HEMS (Pos. 015): voll in
        beiden → Doppelungs-Warnung; HEMS im WP-Angebot als Alternativ
        („im PV-Angebot enthalten“) → keine Warnung, WP-Summe ohne HEMS."""
        from app import kombi_versand
        from tests.test_regression import KONTROLL_SZENARIO
        vorgang = Vorgang(kunde_id=self.kunde.id)
        self.s.add(vorgang)
        self.s.flush()
        wp = angebot_aufbau.angebot_anlegen(
            self.s, self.kunde.id, antworten=dict(KONTROLL_SZENARIO, P01="Ja"),
            logik=self.logik_voll)
        pv = angebot_aufbau.angebot_anlegen(
            self.s, self.kunde.id, antworten=pv_basis(PA11="Ja"), logik=self.logik,
            sparte="PV")
        wp.vorgang_id = pv.vorgang_id = vorgang.id
        hems_wp = [p for p in wp.positionen if p.pos_nr == "015"][0]
        hems_wp.e_preis_cent = 94900          # HEMS mit Preis → Doppelung sichtbar
        self.s.commit()
        self.assertIn("015", kombi_versand.doppelte_artikel([wp, pv]))
        netto_vorher = wp.summen()["netto"]
        hems_wp.alternativ = True
        hems_wp.alternativ_zu = f"PV-Angebot {pv.nummer}"
        self.s.commit()
        self.assertNotIn("015", kombi_versand.doppelte_artikel([wp, pv]))
        self.assertEqual(wp.summen()["netto"], netto_vorher - 94900)
        self.assertEqual(pv.summen()["ust"], 0)
        self.assertEqual(wp.summen()["ust"], int(wp.summen()["netto"] * 19 / 100))
