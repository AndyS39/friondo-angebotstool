# Kontrollwerte PLAN_V15 Phase 100 (Wirtschaftlichkeit PV, v22) – reiner
# Rechenkern, keine DB. Toleranz ± 1 € bzw. ± 0,1 %-Punkt.
# Seit 01.10.2026 gilt das Saisonmodell (Monatsprofile, PLAN_V15 Anhang B);
# die Werte des Jahresmodells aus Anhang A sind damit überholt.
import unittest

from app import wirtschaftlichkeit as w

PARAM = dict(ertrag=950, strompreis=0.33, verguetung=0.078, steigerung=0.03,
             degradation=0.004, betriebskosten=100, jahre=20, zyklen=250,
             wirkungsgrad=0.90, direkt_hh=0.35, direkt_wp=0.20, direkt_wb=0.30,
             hems_hh=0.05, hems_wp=0.15, hems_wb=0.20, spot_preis=0.18,
             szenarien=[0.01, 0.03, 0.05], co2_faktor=380, co2_auto=120, co2_baum=12.5)
ANLAGE = dict(kwp=10.92, module=24, speicher_kwh=10, hems=True, spot=True,
              hh_kwh=4500, wp_kwh=4500, wb_kwh=0, investition_eur=24900, startjahr=2027)


class Kontrollwerte(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = w.berechnen(PARAM, ANLAGE)

    def eur(self, ist, soll):
        self.assertAlmostEqual(ist, soll, delta=1.0)

    def prozent(self, ist, soll):
        self.assertAlmostEqual(ist * 100, soll, delta=0.1)

    def test_jahr1_energiebilanz(self):
        j1 = self.e["j1"]
        for k, soll in (("prod", 10374), ("direkt", 2922), ("sp_in", 2479),
                        ("sp_out", 2232), ("netz", 3847), ("einsp", 4973)):
            self.assertAlmostEqual(j1[k], soll, delta=1.0, msg=k)
        self.prozent(j1["ev_quote"], 52.1)
        self.prozent(j1["autarkie"], 57.3)
        self.prozent(j1["solaranteil_wp"], 48.9)
        self.prozent(j1["solaranteil_wp_ohne_hems"], 38.7)

    def test_monate_jahr1(self):
        monate = self.e["monate_j1"]
        self.assertEqual(len(monate), 12)
        j1 = self.e["j1"]
        for k in ("prod", "direkt", "sp_out", "netz", "einsp", "last"):
            self.assertAlmostEqual(sum(m[k] for m in monate), j1[k], delta=0.5, msg=k)
        # Winter: Netzbezug hoch, Sommer: kein Netzbezug (Speicher deckt die Nacht)
        self.assertGreater(monate[0]["netz"], 800)
        self.assertGreater(monate[11]["netz"], 800)
        self.assertEqual(round(monate[5]["netz"]), 0)
        self.assertEqual(round(monate[6]["netz"]), 0)
        # Direktverbrauch nie über 90 % der Monatsproduktion, im Winter klein
        for m in monate:
            self.assertLessEqual(m["direkt"], 0.9 * m["prod"] + 0.01)
        self.assertGreater(monate[2]["direkt"], 2 * monate[0]["direkt"])

    def test_vollausbau(self):
        e = self.e
        self.eur(e["ersparnis_1"], 2565)
        self.eur(e["monat"], 214)
        self.eur(e["summe_ersparnis"], 66256)
        self.eur(e["summe_ohne"], 79805)
        self.eur(e["summe_mit"], 13549)
        self.eur(e["gewinn_ende"], 41356)
        self.assertEqual(e["break_even"], 9)
        self.assertEqual(e["break_even_jahr"], 2035)
        self.assertEqual((e["startjahr"], e["endjahr"]), (2027, 2046))
        self.assertAlmostEqual(e["faktor"], 2.66, delta=0.005)

    def test_kumuliert(self):
        soll = [-22335, -19704, -17007, -14241, -11404, -8494, -5508, -2444, 700,
                3927, 7239, 10640, 14131, 17716, 21397, 25177, 29060, 33049, 37147, 41356]
        ist = [z["kum"] for z in self.e["jahre"]]
        self.assertEqual(len(ist), 20)
        for i, (a, b) in enumerate(zip(ist, soll)):
            self.assertAlmostEqual(a, b, delta=1.0, msg=f"Jahr {i + 1}")

    def test_treppe(self):
        t = self.e["treppe"]
        self.assertEqual([s["schluessel"] for s in t], ["pv", "speicher", "hems", "spot"])
        for stufe, j1, summe, be in zip(t, (1261, 1835, 1988, 2565),
                                        (29599, 46277, 50628, 66256), (18, 12, 12, 9)):
            self.eur(stufe["ersparnis_1"], j1)
            self.eur(stufe["summe"], summe)
            self.assertEqual(stufe["break_even"], be)
        self.assertIsNone(t[0]["delta"])
        self.eur(t[1]["delta"], 573)
        self.eur(t[3]["delta"], 577)
        self.assertEqual(t[1]["name"], "+ Speicher 10 kWh")
        self.assertIsNone(self.e["spot_hinweis"])

    def test_treppe_ohne_spot_und_speicher(self):
        e = w.berechnen(PARAM, dict(ANLAGE, spot=False))
        self.assertEqual([s["schluessel"] for s in e["treppe"]], ["pv", "speicher", "hems"])
        self.eur(e["spot_hinweis"]["delta_1"], 577)
        self.eur(e["spot_hinweis"]["ersparnis_1"], 2565)
        e = w.berechnen(PARAM, dict(ANLAGE, speicher_kwh=0, hems=False))
        self.assertEqual([s["schluessel"] for s in e["treppe"]], ["pv", "spot"])
        self.assertEqual(e["j1"]["sp_out"], 0)

    def test_szenarien(self):
        s = self.e["szenarien"]
        self.assertEqual([round(x["steigerung"], 2) for x in s], [0.01, 0.03, 0.05])
        for stufe, summe, be in zip(s, (55241, 66256, 80322), (10, 9, 9)):
            self.eur(stufe["summe"], summe)
            self.assertEqual(stufe["break_even"], be)

    def test_co2(self):
        c = self.e["co2"]
        self.assertAlmostEqual(c["t_jahr"], 3.94, delta=0.005)
        self.assertAlmostEqual(c["t_gesamt"], 75.9, delta=0.05)
        self.assertAlmostEqual(c["km"], 32851, delta=1)
        self.assertAlmostEqual(c["baeume"], 315, delta=0.5)

    def test_vorteil_jahr1_und_heizen(self):
        v = self.e["vorteil"]
        self.eur(v["stromkosten_heute"], 2970)
        self.eur(v["netzbezug"], 1269)
        self.eur(v["einspeisung"], 388)
        self.eur(v["spot_vorteil"], 577)
        self.assertAlmostEqual(v["spot_differenz"], 0.15, places=6)
        self.eur(v["betriebskosten"], 100)
        self.eur(v["summe"], 2565)
        h = self.e["heizen"]
        self.prozent(h["anteil_pv"], 48.9)
        self.eur(h["kosten_ohne_pv"], 1485)
        self.eur(h["kosten_mit_pv"], 759)
        self.assertIsNone(w.berechnen(PARAM, dict(ANLAGE, wp_kwh=0))["heizen"])

    def test_saisonmodell_gegen_jahresmodell(self):
        """Flache Profile (alle Monate gleich) reproduzieren das alte
        Jahresmodell (Anhang A) – das Saisonmodell ist eine Verfeinerung."""
        flach = [1 / 12] * 12
        p = dict(PARAM, profil_pv=flach, profil_hh=flach, profil_wp=flach, profil_wb=flach)
        e = w.berechnen(p, ANLAGE)
        j1 = e["j1"]
        self.assertAlmostEqual(j1["direkt"], 3375, delta=1.0)
        self.assertAlmostEqual(j1["sp_out"], 2500, delta=1.0)
        self.assertAlmostEqual(j1["netz"], 3125, delta=1.0)
        self.eur(e["ersparnis_1"], 2637)
        self.eur(e["summe_ersparnis"], 68675)
        self.assertEqual(e["break_even"], 9)

    def test_kein_break_even(self):
        e = w.berechnen(PARAM, dict(ANLAGE, investition_eur=500000))
        self.assertIsNone(e["break_even"])
        self.assertIsNone(e["break_even_jahr"])
        self.assertLess(e["gewinn_ende"], 0)


class Parameter(unittest.TestCase):
    def test_standard_bei_fehlenden_zeilen(self):
        p, fehlende = w.parameter_lesen({"Strompreis": ("0,32", ""), "Spezifischer Ertrag": ("960", "")})
        self.assertEqual((p["strompreis"], p["ertrag"], p["steigerung"], p["jahre"]),
                         (0.32, 960, 0.03, 20))
        self.assertIn("Strompreissteigerung", fehlende)
        self.assertNotIn("Strompreis", fehlende)

    def test_prozent_und_listen(self):
        p, fehlende = w.parameter_lesen({
            "Strompreissteigerung": ("3", ""), "Degradation": ("0,4 %", ""),
            "Speicher Wirkungsgrad": ("90", ""), "Direktanteil Haushalt": ("35", ""),
            "Szenarien Strompreissteigerung": ("1; 3; 5", ""),
            "Betrachtungszeitraum": ("20", ""), "Montagedauer-Text": ("Montage in 1 Tag", ""),
            "CO₂ Baum": ("12,5", "")})
        self.assertAlmostEqual(p["steigerung"], 0.03)
        self.assertAlmostEqual(p["degradation"], 0.004)
        self.assertAlmostEqual(p["wirkungsgrad"], 0.9)
        self.assertAlmostEqual(p["direkt_hh"], 0.35)
        self.assertEqual(p["szenarien"], [0.01, 0.03, 0.05])
        self.assertEqual(p["montage_text"], "Montage in 1 Tag")
        self.assertEqual(p["co2_baum"], 12.5)
        self.assertNotIn("Szenarien Strompreissteigerung", fehlende)

    def test_unlesbarer_wert_faellt_auf_standard(self):
        p, fehlende = w.parameter_lesen({"Betriebskosten": ("viel", "")})
        self.assertEqual(p["betriebskosten"], 100.0)
        self.assertIn("Betriebskosten", fehlende)

    def test_monatsprofile(self):
        p, fehlende = w.parameter_lesen({
            "Monatsprofil PV": ("2,5; 4,5; 10; 11; 12,5; 13; 13; 11,5; 9,5; 7; 3,5; 2", ""),
            "Monatsprofil Haushalt": ("1; 1; 1; 1; 1; 1; 1; 1; 1; 1; 1", ""),   # nur 11 Werte
            "Monatsprofil Wärmepumpe": ("10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10", "")})
        self.assertAlmostEqual(sum(p["profil_pv"]), 1.0)
        self.assertAlmostEqual(p["profil_pv"][0], 0.025)
        self.assertIn("Monatsprofil Haushalt", fehlende)         # Standard greift
        self.assertAlmostEqual(p["profil_hh"][11], 10.1 / 100, places=4)
        self.assertAlmostEqual(p["profil_wp"][0], 1 / 12)
        self.assertIn("Monatsprofil Wallbox", fehlende)
        self.assertAlmostEqual(sum(w.STANDARD["profil_wp"]), 1.0)
        self.assertEqual(len(w.NEUE_PARAMETER_ZEILEN), 24)

    def test_neue_zeilen_vollstaendig(self):
        namen = {z[0] for z in w.NEUE_PARAMETER_ZEILEN}
        for name, _schl, _art in w.PARAMETER_ZEILEN:
            if name not in ("Spezifischer Ertrag", "Strompreis", "Einspeisevergütung"):
                self.assertIn(name, namen)


class PdfEinbindung(unittest.TestCase):
    """Phase 101/102: die drei Seiten im PV-PDF (Profile, Altfälle, Häkchen,
    keine Leerseite, Seitenzahl +3) – gegen die Entwicklungs-DB."""

    @classmethod
    def setUpClass(cls):
        import warnings
        warnings.filterwarnings("ignore")
        from app import logik as logik_modul
        from app.db import SessionLocal, init_db
        from app.models import Kunde
        from tests.test_pv_v13 import TEST_EMAIL, aufraeumen
        init_db()
        cls.s = SessionLocal()
        cls.email = TEST_EMAIL.replace("pv-v13", "pv-v22")
        cls.aufraeumen = staticmethod(aufraeumen)
        cls._aufraeumen()
        cls.kunde = Kunde(anrede="Familie", vorname="", nachname="Mustermann v22",
                          strasse="Musterstraße 12", plz="47139", ort="Duisburg",
                          email=cls.email)
        cls.s.add(cls.kunde)
        cls.s.commit()
        voll, _ = logik_modul.neu_einlesen(cls.s)
        cls.logik = logik_modul.logik_fuer_sparte(voll, "PV")

    @classmethod
    def _aufraeumen(cls):
        from app.models import Angebot, Erfassung, Kunde, Vorgang
        for k in cls.s.query(Kunde).filter(Kunde.email == cls.email):
            for a in cls.s.query(Angebot).filter_by(kunde_id=k.id):
                cls.s.delete(a)
            for e in cls.s.query(Erfassung).filter_by(kunde_id=k.id):
                cls.s.delete(e)
            for v in cls.s.query(Vorgang).filter_by(kunde_id=k.id):
                cls.s.delete(v)
            cls.s.delete(k)
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        cls._aufraeumen()
        cls.s.close()

    def angebot(self, **zusatz):
        from app import angebot_aufbau
        from tests.test_pv_v13 import pv_basis
        antworten = pv_basis(PD12=24, PA10=10, PA11="Ja", PA13="Ja", PO06=4500, PO07=4500)
        antworten.update(zusatz)
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, antworten=antworten,
                                           logik=self.logik, sparte="PV")
        self.s.commit()
        return a

    def seiten(self, angebot):
        import pypdf
        from app import pdf_export
        pfad = pdf_export.pdf_fuer_angebot(self.s, angebot)
        seiten = [(s.extract_text() or "") for s in pypdf.PdfReader(str(pfad)).pages]
        pfad.unlink(missing_ok=True)
        return seiten

    @staticmethod
    def _wirtschaftlichkeitsseiten(seiten):
        return [s for s in seiten if "Seite 1 von 3" in s or "Seite 2 von 3" in s
                or "Seite 3 von 3" in s]

    def test_drei_seiten_ohne_leerseite(self):
        a = self.angebot()
        seiten = self.seiten(a)
        w = self._wirtschaftlichkeitsseiten(seiten)
        self.assertEqual(len(w), 3)
        text = "\n".join(seiten).replace("\n", " ")
        for erwartet in ("So rechnet sich Ihre Energielösung", "IHRE ERSPARNIS IN 20 JAHREN",
                         "Break-even", "Was Sie Jahr für Jahr sparen", "SpotDynamic",
                         "Heizen mit Sonnenstrom", "So sicher ist Ihre Rechnung",
                         "Ihr Beitrag zum Klima", "SO GEHT ES WEITER", "Montage in 1–2 Tagen",
                         f"zu Angebot {a.nummer}"):
            self.assertIn(erwartet, text, erwartet)
        self.assertNotIn("Ihre Beispielrechnung", text)
        # keine (fast) leere Seite im ganzen PDF
        for i, s in enumerate(seiten, 1):
            self.assertGreater(len(s.strip()), 200, f"Seite {i} fast leer")
        # ohne Häkchen: genau 3 Seiten mehr als mit Häkchen
        a.wirtschaftlichkeit_ausblenden = True
        self.s.commit()
        seiten_ohne = self.seiten(a)
        self.assertEqual(len(seiten) - len(seiten_ohne), 3)
        self.assertFalse(self._wirtschaftlichkeitsseiten(seiten_ohne))
        a.wirtschaftlichkeit_ausblenden = False
        self.s.commit()

    def test_altfall_ohne_auslegung(self):
        a = self.angebot()
        a.pv_json = ""
        self.s.commit()
        seiten = self.seiten(a)
        self.assertFalse(self._wirtschaftlichkeitsseiten(seiten))
        for s in seiten:
            self.assertGreater(len(s.strip()), 200)
        # Altbestand: pv_json ohne Verbrauchsdaten → Fallback über die Erfassung
        import json
        from app import pdf_export
        from app.models import Erfassung
        from tests.test_pv_v13 import pv_basis
        alt = {"kwp": 10.92, "module": 24, "speicher_stufe": 10.0}
        a.pv_json = json.dumps(alt)
        erf = Erfassung(kunde_id=self.kunde.id, benutzer_id=1, sparte="PV",
                        konfigurator_typ="PV", angebot_id=a.id,
                        antworten_json=json.dumps(pv_basis(PO06=3000, PO07=2000,
                                                           PO08="Ja", PO09=1500, PA10=8)))
        self.s.add(erf)
        self.s.commit()
        daten = pdf_export.wirtschaftlichkeit_fuer(self.s, a)
        self.assertEqual((daten["anlage"]["hh_kwh"], daten["anlage"]["wp_kwh"],
                          daten["anlage"]["wb_kwh"], daten["anlage"]["speicher_kwh"]),
                         (3000.0, 2000.0, 1500.0, 8.0))
        self.assertEqual(daten["anlage"]["startjahr"], a.datum.year + 1)
        self.assertEqual(len(self._wirtschaftlichkeitsseiten(self.seiten(a))), 3)

    def test_varianten_ohne_wp_speicher_spot(self):
        # ohne WP/Wallbox, ohne SpotDynamic → Karte „Ihr Verbrauch“ + Hinweiszeile
        a = self.angebot(PO07=0, PA13="Nein")
        text = "\n".join(self.seiten(a)).replace("\n", " ")
        self.assertIn("Ihr Verbrauch", text)
        self.assertNotIn("Heizen mit Sonnenstrom", text)
        self.assertNotIn("Amortisation 0 Jahre", text)
        # ohne Speicher (PA10 = 0 → keine Kombi, aber Auslegung bleibt)
        b = self.angebot(PA10=0, PA11="Nein", PA13="Nein")
        for p in list(b.positionen):
            if "Sigenergy" in (p.beschreibung or ""):
                self.s.delete(p)
        self.s.commit()
        seiten = self.seiten(b)
        self.assertEqual(len(self._wirtschaftlichkeitsseiten(seiten)), 3)
        text = "\n".join(seiten).replace("\n", " ")
        self.assertIn("nicht enthalten", text)
        self.assertNotIn("+ Speicher", text)

    def test_profile_zeigen_die_seiten(self):
        from app.models import Profil
        for name in ("Enni", "SWD", "Sparkasse DU"):
            profil = self.s.query(Profil).filter(Profil.name == name).first()
            self.assertIsNotNone(profil, name)
            a = self.angebot()
            a.profil_id = profil.id
            self.s.commit()
            seiten = self.seiten(a)
            self.assertEqual(len(self._wirtschaftlichkeitsseiten(seiten)), 3, name)
            for s in seiten:
                self.assertGreater(len(s.strip()), 200, name)

    def test_langer_kundenname_bricht_nicht(self):
        from app.models import Kunde
        k = Kunde(anrede="Firma", firma="Wohnungsbaugesellschaft Musterstadt am Niederrhein "
                  "Verwaltungs- und Beteiligungs-GmbH & Co. KG", nachname="Muster",
                  strasse="Sehr lange Straßenbezeichnung an der Ruhrpromenade 1234a",
                  plz="47139", ort="Duisburg-Meiderich-Beeck", email=self.email)
        self.s.add(k)
        self.s.commit()
        from app import angebot_aufbau
        from tests.test_pv_v13 import pv_basis
        a = angebot_aufbau.angebot_anlegen(
            self.s, k.id, antworten=pv_basis(PD12=24, PA10=10, PO06=4500, PO07=4500),
            logik=self.logik, sparte="PV")
        self.s.commit()
        seiten = self.seiten(a)
        self.assertEqual(len(self._wirtschaftlichkeitsseiten(seiten)), 3)
        self.assertIn("…", "\n".join(seiten))

    def test_textblock_migration_idempotent(self):
        from app import angebotsprofile
        from app.models import Textblock
        block = Textblock(art="nachtext", name="Friondo PV Testblock v22",
                          text="# A\n---\n[BEISPIELRECHNUNG]\n---\n# B")
        self.s.add(block)
        self.s.commit()
        try:
            # erster Lauf stellt den Testblock (und ggf. noch nicht migrierte
            # Bestandsblöcke der Entwicklungs-DB) um, zweiter Lauf findet nichts
            meldung = angebotsprofile.migriere_pv_platzhalter(self.s)
            self.assertEqual(len(meldung), 1)
            self.assertRegex(meldung[0], r"^\d+ PV-Textblöcke auf \[WIRTSCHAFTLICHKEIT\] umgestellt$")
            self.s.commit()
            self.assertIn("[WIRTSCHAFTLICHKEIT]", self.s.get(Textblock, block.id).text)
            self.assertNotIn("[BEISPIELRECHNUNG]", self.s.get(Textblock, block.id).text)
            self.assertEqual(angebotsprofile.migriere_pv_platzhalter(self.s), [])
            self.assertEqual(angebotsprofile._PV_BEISPIEL, "[WIRTSCHAFTLICHKEIT]")
            self.assertIn("[WIRTSCHAFTLICHKEIT]", angebotsprofile.PV_STANDARD_NACHTEXT)
        finally:
            self.s.delete(self.s.get(Textblock, block.id))
            self.s.commit()

    def test_alias_beispielrechnung(self):
        from app import pdf_export
        self.assertIs(pdf_export.beispielrechnung_fuer, pdf_export.wirtschaftlichkeit_fuer)
        self.assertIn("[BEISPIELRECHNUNG]", pdf_export.PLATZHALTER_WIRTSCHAFTLICHKEIT)


if __name__ == "__main__":
    unittest.main()
