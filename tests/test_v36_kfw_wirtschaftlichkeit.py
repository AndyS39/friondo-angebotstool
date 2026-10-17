# v36 (PLAN_V22 Phase 189, Agent A2): Kontext-Teilbäume `kfw` (Seite „Ihre KfW-Förderung“) und
# `wirtschaftlichkeit` (drei PV-Seiten) des Angebots-PDFs im Layout v3 – app/pdf_kontext_kfw.py,
# app/pdf_kontext_wirtschaftlichkeit.py, Partials app/templates/pdf/angebot/kfw.html und
# wirtschaftlichkeit.html, Stylesheets app/static/pdf/angebot_kfw.css / angebot_wirtschaftlichkeit.css.
# Prüft: Förderwerte identisch mit pdf_export._kfw_ergebnis_fuer (WP-Kontrollangebot aus
# tests/test_regression.KONTROLL_SZENARIO), Positionsnummern dynamisch, Deckel-Satz nur bei gedeckelten
# Boni, manuelle Förderung ohne Kennzeichen, Förderblock ausgeblendet → None, MFH-Zusatz, PV-Kontext mit den
# v22-Kontrollwerten (tests/test_wirtschaftlichkeit_v22.py) und Varianten, gerendertes HTML je Partial,
# PDF-Druck mit pypdf-Textprüfung (nur mit Browser), keine Hex-Farbe in den Templates.
# Läuft gegen DB_PFAD_OVERRIDE (Kopie), räumt eigene Daten auf, kein Netzzugriff.
import io
import json
import re
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from pypdf import PdfReader

from app import angebot_aufbau, import_pv, pdf_export, pdf_html, pdf_kontext, pdf_kontext_kfw
from app import kfw as kfw_modul
from app import logik as logik_modul
from app import pdf_kontext_wirtschaftlichkeit as pkw
from app import wirtschaftlichkeit
from app.db import SessionLocal, init_db
from app.models import Angebot, Artikel, Erfassung, Kunde, QUELLE_PV, Vorgang, VorgangsNotiz
from tests.test_pv_v13 import pv_basis
from tests.test_regression import KONTROLL_SZENARIO

PROJEKT = Path(__file__).resolve().parents[1]
TEMPLATES = PROJEKT / "app" / "templates" / "pdf" / "angebot"
BILDER = PROJEKT / "diagnose" / "v36" / "A2_bilder"
EMAIL = "v36-a2@test.local"
HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
BROWSER = pdf_html.browser_test()   # einmal je Modul: Edge/Chromium für den Druck vorhanden?

VORLAGE_KFW = ("{% extends 'pdf/angebot/basis.html' %}{% block seiten %}"
               "{% include 'pdf/angebot/kfw.html' %}{% endblock %}")
VORLAGE_WI = ("{% extends 'pdf/angebot/basis.html' %}{% block seiten %}"
              "{% include 'pdf/angebot/wirtschaftlichkeit.html' %}{% endblock %}")


def _texte(obj) -> list[str]:
    """Alle Zeichenketten eines Kontext-Teilbaums (rekursiv) – für Wortprüfungen."""
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [t for v in obj.values() for t in _texte(v)]
    if isinstance(obj, (list, tuple)):
        return [t for v in obj for t in _texte(v)]
    return []


def _aufraeumen(s) -> None:
    for k in s.query(Kunde).filter(Kunde.email == EMAIL):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete(synchronize_session=False)
            s.delete(v)
        s.delete(k)
    s.commit()


def _rendern(vorlage: str, kontext: dict) -> str:
    return pdf_html.jinja_env().from_string(vorlage).render(kontext=kontext, static=pdf_html.STATIC_URL)


def _pdf_seiten(html: str, kontext: dict) -> list[str]:
    pdf = pdf_html.drucken(html, pdf_html.kopfzeile_html(kontext))
    return [(seite.extract_text() or "").replace("\n", " ") for seite in PdfReader(io.BytesIO(pdf)).pages], pdf


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        _aufraeumen(cls.s)
        cls.kunde = Kunde(anrede="Familie", vorname="", nachname="V36-A2 Muster", strasse="Teststr. 1",
                          plz="47139", ort="Duisburg", email=EMAIL)
        cls.s.add(cls.kunde)
        cls.s.commit()
        if cls.s.query(Artikel).filter(Artikel.quelle == QUELLE_PV).count() == 0:
            import_pv.import_ausfuehren(cls.s)
        cls.logik_voll, bericht = logik_modul.neu_einlesen(cls.s)
        assert bericht.ok, bericht.fehler
        cls.logik_pv = logik_modul.logik_fuer_sparte(cls.logik_voll, "PV")

    @classmethod
    def tearDownClass(cls):
        _aufraeumen(cls.s)
        cls.s.close()

    def wp_angebot(self, **zusatz) -> Angebot:
        antworten = dict(KONTROLL_SZENARIO)
        antworten.update(zusatz)
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, antworten=antworten, logik=self.logik_voll)
        self.s.commit()
        return a

    def pv_angebot(self, **zusatz) -> Angebot:
        antworten = pv_basis(PD12=24, PA10=10, PA11="Ja", PA13="Ja", PO06=4500, PO07=4500)
        antworten.update(zusatz)
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, antworten=antworten, logik=self.logik_pv,
                                           sparte="PV")
        self.s.commit()
        return a

    def neu(self, angebot: Angebot) -> Angebot:
        self.s.expire_all()
        return self.s.get(Angebot, angebot.id)


# --- (1) KfW-Kontext -----------------------------------------------------------------------
class KfwKontext(Basis):
    def test_kontrollangebot_werte_wie_kfw_ergebnis(self):
        a = self.wp_angebot()
        self.assertEqual(a.summen()["netto"], 3024543)                     # Kontrollwert unverändert
        ergebnis = pdf_export._kfw_ergebnis_fuer(self.s, a)
        k = pdf_kontext_kfw.kontext(self.s, a)
        self.assertIsNotNone(k)
        self.assertEqual(k["zuschuss"], kfw_modul._euro(ergebnis.zuschuss_cent))
        self.assertEqual(k["eigenanteil"], kfw_modul._euro(ergebnis.eigenanteil_cent))
        self.assertEqual((k["zuschuss"], k["eigenanteil"]), ("19.600,00 €", "16.392,06 €"))
        self.assertEqual(k["angebotssumme"], "35.992,06 €")
        self.assertEqual(k["angebotssumme_zusatz"], "(inkl. 19 % USt.)")
        self.assertEqual((k["hoechstkosten"], k["foerderfaehig"]), ("28.000,00 €", "28.000,00 €"))
        self.assertEqual(k["eyebrow"], "ANTRAG: KFW 458 (WOHNGEBÄUDE)")
        self.assertEqual(k["programm"], "KfW 458 (Wohngebäude)")
        self.assertEqual(k["titel"], "Ihre KfW-Förderung")
        self.assertEqual(k["foerdersatz"], "70 %")
        # Bausteine: angewandte Sätze (Einkommensbonus 30 % → 24 % durch den Deckel 70 %), Summe = Zuschuss
        self.assertEqual([(b["name"], b["prozent_text"], b["betrag"]) for b in k["bausteine"]],
                         [("Grundförderung", "30 %", "8.400,00 €"),
                          ("Klimageschwindigkeits-Bonus", "16 %", "4.480,00 €"),
                          ("Einkommensbonus", "24 %", "6.720,00 €")])
        self.assertTrue(all(b["mfh_zusatz"] == "" for b in k["bausteine"]))
        self.assertEqual(k["bausteine"][0]["klammer"], "(30 %)")
        # Balken: Anteile an der Angebotssumme, Summe 100, Eigenanteil als letztes Segment
        self.assertEqual([b["name"] for b in k["balken"]], ["Grund", "Klima", "Einkommen", "Ihr Eigenanteil"])
        self.assertEqual(sum(b["prozent"] for b in k["balken"]), 100)
        self.assertEqual(k["foerderquote"] + k["eigenquote"], 100)
        self.assertEqual(k["foerderquote"], sum(b["prozent"] for b in k["balken"][:-1]))
        self.assertEqual(k["untertitel"], f"{k['foerderquote']} % zahlt die KfW – {k['eigenquote']} % bleiben für Sie")
        self.assertEqual(k["balken"][-1]["betrag"], "16.392,06 €")
        # Deckel-Satz und Höchstkosten-Satz wörtlich aus app/kfw.py, Disclaimer mit Angebotsdatum
        self.assertEqual(k["deckel_satz"],
                         "Die Boni ergäben rechnerisch 76 %, der Fördersatz ist jedoch auf 70 % gedeckelt.")
        self.assertIn(k["deckel_satz"], k["hinweise"])
        self.assertTrue(any(h.startswith("Die Kosten übersteigen die förderfähigen Höchstkosten von 28.000,00 €")
                            for h in k["hinweise"]))
        datum = a.datum.strftime("%d.%m.%Y")
        self.assertEqual(k["konditionen_ab"], datum)
        self.assertIn(f"Konditionen ab {datum}", k["disclaimer"])
        self.assertNotIn("21.07.2026", k["disclaimer"])
        self.assertTrue(k["disclaimer"].startswith("Unverbindliche Beispielrechnung der Friondo GmbH"))
        self.assertFalse(k["manuell"])
        self.assertFalse(k["mfh"])
        self.assertEqual(k["bild"], "bilder/kfw.png")
        # Wortlaute der Vorlage
        self.assertEqual([s["titel"] for s in k["schritte"]],
                         ["Angebot annehmen", "Friondo erstellt die Unterlagen", "Antrag im KfW-Portal",
                          "Förderzusage der KfW", "Installation durch Friondo", "Nachweis & Auszahlung"])
        self.assertEqual(k["gut_zu_wissen"][0],
                         "Gefördert wird über das Programm „Heizungsförderung für Privatpersonen – Wohngebäude“ (KfW 458).")
        self.assertEqual(k["antrag_unterlagen"][1], "Die BzA-ID aus der Bestätigung zum Antrag von Friondo")

    def test_positionsnummern_dynamisch(self):
        a = self.wp_angebot()
        nummern = dict(zip((p.pos_nr for p in a.positionen), a.nummerierung()))
        self.assertIn("012", nummern)       # BzA-Position (ANTRAG BEG EM)
        self.assertIn("008", nummern)       # hydraulischer Abgleich
        k = pdf_kontext_kfw.kontext(self.s, a)
        self.assertEqual((k["pos_bza"], k["pos_hydraulik"]), (nummern["012"], nummern["008"]))
        self.assertNotEqual(k["pos_bza"], "017")
        self.assertTrue(k["schritte"][1]["text"].endswith(f"– kostenfrei, Pos. {nummern['012']}."))
        self.assertEqual(k["gut_zu_wissen"][1], f"Der hydraulische Abgleich (Pos. {nummern['008']}) ist "
                                                "Fördervoraussetzung und im Angebot enthalten.")
        # eigene Positionsnummer (v5) wird übernommen
        bza = next(p for p in a.positionen if p.pos_nr == "012")
        bza.anzeige_nr = "050"
        self.s.commit()
        k = pdf_kontext_kfw.kontext(self.s, self.neu(a))
        self.assertEqual(k["pos_bza"], "050")
        # Positionen fehlen → Klammerzusatz entfällt, Wortlaut sonst unverändert
        b = self.wp_angebot()
        for p in list(b.positionen):
            if p.pos_nr in ("012", "008"):
                self.s.delete(p)
        self.s.commit()
        k = pdf_kontext_kfw.kontext(self.s, self.neu(b))
        self.assertIsNone(k["pos_bza"])
        self.assertIsNone(k["pos_hydraulik"])
        self.assertTrue(k["schritte"][1]["text"].endswith("Bestätigung zum Antrag (BzA) – kostenfrei."))
        self.assertEqual(k["gut_zu_wissen"][1],
                         "Der hydraulische Abgleich ist Fördervoraussetzung und im Angebot enthalten.")
        self.assertNotIn("Pos.", " ".join(_texte(k["schritte"]) + k["gut_zu_wissen"]))

    def test_positionsnummern_rueckfall_ueber_titel(self):
        a = self.wp_angebot()
        for p in a.positionen:
            if p.pos_nr in ("012", "008"):
                p.pos_nr = ""                     # z. B. Freitext-/editierte Position ohne Artikelnummer
        self.s.commit()
        a = self.neu(a)
        nummern = dict(zip((p.titel for p in a.positionen), a.nummerierung()))
        k = pdf_kontext_kfw.kontext(self.s, a)
        self.assertEqual(k["pos_bza"], next(nr for titel, nr in nummern.items() if "BzA" in titel))
        self.assertEqual(k["pos_hydraulik"],
                         next(nr for titel, nr in nummern.items() if titel.startswith("Hydraulischer Abgleich")))

    def test_ausgeblendet_und_andere_sparten_liefern_none(self):
        a = self.wp_angebot()
        self.assertIsNotNone(pdf_kontext_kfw.kontext(self.s, a))
        a.foerderung_ausblenden = True
        self.s.commit()
        self.assertIsNone(pdf_kontext_kfw.kontext(self.s, self.neu(a)))
        a.foerderung_ausblenden = False
        a.kfw_json = "{}"                               # WP ohne KfW-Daten (manuelles Angebot)
        self.s.commit()
        self.assertIsNone(pdf_kontext_kfw.kontext(self.s, self.neu(a)))
        pv = self.pv_angebot()
        self.assertIsNone(pdf_kontext_kfw.kontext(self.s, pv))
        kl = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, sparte="KL")
        self.s.commit()
        self.assertIsNone(pdf_kontext_kfw.kontext(self.s, kl))

    def test_mfh_zusatz(self):
        a = self.wp_angebot(O01="MFH", O03=3, K01="Ja")
        ergebnis = pdf_export._kfw_ergebnis_fuer(self.s, a)
        k = pdf_kontext_kfw.kontext(self.s, a)
        self.assertTrue(k["mfh"])
        self.assertEqual(k["wohneinheiten"], 3)
        self.assertEqual([b["name"] for b in k["bausteine"]],
                         ["Grundförderung", "Klimageschwindigkeits-Bonus", "Einkommensbonus"])
        self.assertEqual(k["bausteine"][0]["klammer"], "(30 %)")
        self.assertEqual(k["bausteine"][1]["mfh_zusatz"], "(16 % anteilig WE)")
        self.assertEqual(k["bausteine"][1]["klammer"], "(16 % anteilig WE)")
        self.assertRegex(k["bausteine"][2]["mfh_zusatz"], r"^\(\d+ % anteilig WE\)$")
        # Beträge wörtlich aus den v9-Zeilen des KfW-Ergebnisses, Summe = Zuschuss
        zeilen = {name.split(" (")[0]: wert for name, wert, _f in ergebnis.zeilen}
        for b in k["bausteine"]:
            self.assertEqual(b["betrag"], zeilen[b["name"]])
        summe = sum(int(round(kfw_modul._zahl(b["betrag"]) * 100)) for b in k["bausteine"])
        self.assertEqual(summe, ergebnis.zuschuss_cent)
        self.assertTrue(any(h.startswith("Boni sind anteilig für die selbst bewohnte Wohneinheit gerechnet")
                            for h in k["hinweise"]))
        self.assertIn("%-Punkte", k["deckel_satz"])
        self.assertEqual(k["eigenquote"], 100 - k["foerderquote"])
        self.assertEqual(sum(b["prozent"] for b in k["balken"]), 100)

    def test_gewerbe_kfw_522_wortlaute(self):
        """Nachtrag 17.10.2026 (Rückfrage 6): Nichtwohngebäude drucken die KfW-Seite mit dem Programm
        „Heizungsförderung für Unternehmen – Nichtwohngebäude“ (KfW 522), nur Grundförderung, ohne
        Privatpersonen-/§-35c-/Einkommensbonus-Wortlaute; EFH bleibt beim Wortlaut der Vorlage."""
        a = self.wp_angebot(O01="Gewerbe", O05=500)
        k = pdf_kontext_kfw.kontext(self.s, a)
        self.assertIsNotNone(k)
        self.assertTrue(k["nwg"])
        self.assertFalse(k["mfh"])
        self.assertEqual(k["objekt"], "nwg")
        self.assertEqual(k["eyebrow"], "ANTRAG: KFW 522 (NICHTWOHNGEBÄUDE)")
        self.assertEqual(k["programm"], "KfW 522 (Nichtwohngebäude)")
        self.assertEqual(k["gut_zu_wissen"][0], "Gefördert wird über das Programm „Heizungsförderung für "
                                               "Unternehmen – Nichtwohngebäude“ (KfW 522).")
        texte = " ".join(k["gut_zu_wissen"] + k["antrag_unterlagen"])
        for verboten in ("Privatpersonen", "KfW 458", "§ 35c", "Für den Einkommensbonus", "selbstgenutzten Wohneinheit",
                         "Einkommensteuerbescheide"):
            self.assertNotIn(verboten, texte, verboten)
        self.assertIn("Grundförderung", texte)
        self.assertIn("zum Unternehmen", texte)
        self.assertEqual([b["name"] for b in k["bausteine"]], ["Grundförderung"])
        self.assertTrue(any(h.startswith("Gewerbeobjekt: Antrag über KfW 522") for h in k["hinweise"]), k["hinweise"])
        self.assertEqual(k["eigenquote"], 100 - k["foerderquote"])
        # EFH-Kontrolle: Wortlaut der Vorlage unverändert
        e = pdf_kontext_kfw.kontext(self.s, self.wp_angebot())
        self.assertFalse(e["nwg"])
        self.assertIn("Heizungsförderung für Privatpersonen – Wohngebäude“ (KfW 458)", e["gut_zu_wissen"][0])
        self.assertEqual(e["antrag_unterlagen"], list(pdf_kontext_kfw.ANTRAG_UNTERLAGEN))

    def test_manuelle_foerderung_ohne_kennzeichen(self):
        a = self.wp_angebot()
        a.foerder_einkommen_prozent = 10.0                   # v8-Baustein-Übersteuerung: 30 + 16 + 10 = 56 %
        self.s.commit()
        a = self.neu(a)
        ergebnis = pdf_export._kfw_ergebnis_fuer(self.s, a)
        self.assertIn("manuell", ergebnis.satz_text)         # heutiges Ergebnis trägt das Kennzeichen …
        k = pdf_kontext_kfw.kontext(self.s, a)
        self.assertTrue(k["manuell"])                        # … der Kontext nur das Flag
        self.assertFalse([t for t in _texte({x: v for x, v in k.items() if x != "manuell"}) if "manuell" in t.lower()])
        self.assertEqual(k["zuschuss"], kfw_modul._euro(ergebnis.zuschuss_cent))
        self.assertEqual(k["bausteine"][2]["prozent_text"], "10 %")
        self.assertEqual(k["foerdersatz"], "56 %")
        self.assertIsNone(k["deckel_satz"])                  # nicht gedeckelt → kein Deckel-Satz
        self.assertFalse([h for h in k["hinweise"] if "gedeckelt" in h or "begrenzt" in h])
        # v6-Alt-Override (Gesamtzuschuss): ein Baustein, keine Aufschlüsselung, kein Kennzeichen
        a.foerder_einkommen_prozent = None
        a.foerderung_manuell_cent = 1500000
        self.s.commit()
        k = pdf_kontext_kfw.kontext(self.s, self.neu(a))
        self.assertTrue(k["manuell"])
        self.assertEqual(k["zuschuss"], "15.000,00 €")
        self.assertEqual([(b["name"], b["betrag"], b["klammer"]) for b in k["bausteine"]],
                         [("KfW-Zuschuss", "15.000,00 €", "")])
        self.assertEqual([b["name"] for b in k["balken"]], ["KfW-Zuschuss", "Ihr Eigenanteil"])
        self.assertFalse([t for t in _texte({x: v for x, v in k.items() if x != "manuell"}) if "manuell" in t.lower()])

    def test_deckel_satz_nur_bei_gedeckelten_boni(self):
        a = self.wp_angebot(K03=0)                            # ohne Einkommensbonus: 30 + 16 = 46 % < 70 %
        k = pdf_kontext_kfw.kontext(self.s, a)
        self.assertIsNone(k["deckel_satz"])
        self.assertEqual([b["name"] for b in k["bausteine"]], ["Grundförderung", "Klimageschwindigkeits-Bonus"])
        self.assertEqual([b["name"] for b in k["balken"]], ["Grund", "Klima", "Ihr Eigenanteil"])
        self.assertEqual(k["foerdersatz"], "46 %")

    def test_demo_struktur_und_zahlen(self):
        a = self.wp_angebot()
        echt = pdf_kontext_kfw.kontext(self.s, a)
        d = pdf_kontext_kfw.demo()
        self.assertEqual(sorted(d), sorted(echt))
        self.assertEqual((d["angebotssumme"], d["zuschuss"], d["eigenanteil"]),
                         ("42.830,55 €", "16.500,00 €", "26.330,55 €"))
        self.assertEqual(sum(b["prozent"] for b in d["balken"]), 100)
        self.assertEqual([b["betrag"] for b in d["bausteine"]], ["9.000,00 €", "4.800,00 €", "2.700,00 €"])
        self.assertFalse(d["manuell"])
        self.assertFalse([t for t in _texte(d) if "manuell" in t.lower()])
        # pdf_kontext.demo_kontext bindet den Teilbaum ein
        self.assertEqual(pdf_kontext.demo_kontext("WP")["kfw"]["zuschuss"], "16.500,00 €")
        self.assertIsNone(pdf_kontext.demo_kontext("KL")["kfw"])


# --- (2) Wirtschaftlichkeits-Kontext -----------------------------------------------------------
class WirtschaftlichkeitKontext(Basis):
    def test_vollausbau_aus_wirtschaftlichkeit_fuer(self):
        a = self.pv_angebot()
        daten = pdf_export.wirtschaftlichkeit_fuer(self.s, a)
        self.assertIsNotNone(daten)
        e = daten["ergebnis"]
        w = pkw.kontext(self.s, a)
        self.assertIsNotNone(w)
        self.assertEqual(len(w["seiten"]), 3)
        self.assertEqual([s["nr"] for s in w["seiten"]], [1, 2, 3])
        s1, s2, s3 = w["seite1"], w["seite2"], w["seite3"]
        self.assertEqual(s1["meta"], f"zu Angebot {a.nummer} · Duisburg, {a.datum.strftime('%d.%m.%Y')}")
        self.assertFalse([s for s in w["seiten"] if "Seite" in s["meta"]])   # keine innere Seitenzählung
        self.assertEqual(s1["titel"], "So rechnet sich Ihre Energielösung")
        self.assertIn("Familie V36-A2 Muster", s1["subline"])
        self.assertIn("Teststr. 1, 47139 Duisburg", s1["subline"])
        self.assertIn("4.500 kWh Haushaltsstrom und 4.500 kWh Wärmepumpenstrom", s1["subline"])
        self.assertEqual(s1["hero"]["betrag"], pkw._eur100(e["summe_ersparnis"]))
        self.assertEqual(s1["hero"]["eyebrow"], f"IHRE ERSPARNIS IN {e['n']} JAHREN")
        self.assertEqual(s1["hero"]["kacheln"][0]["wert"], f"{e['break_even']} Jahre")
        self.assertEqual(s1["hero"]["kacheln"][1]["wert"], pkw._prozent(e["j1"]["autarkie"]))
        self.assertEqual(len(s1["amortisation"]["balken"]), e["n"])
        self.assertEqual(s1["amortisation"]["chip"]["text"], f"Break-even {e['break_even_jahr']}")
        self.assertEqual(s1["amortisation"]["balken"][-1]["kum_text"], "+" + pkw._eur(e["jahre"][-1]["kum"]))
        self.assertEqual([sum(seg["prozent"] for seg in z["segmente"]) for z in s1["strom"]["zeilen"]], [100, 100])
        self.assertEqual(s2["vorteil"]["summe"]["betrag"], pkw._eur(e["vorteil"]["summe"]))
        self.assertEqual([z["name"] for z in s2["vorteil"]["zeilen"]],
                         ["Stromkosten heute", "Netzbezug neu", "Einspeisung", "SpotDynamic", "Betriebskosten"])
        self.assertEqual(s2["rechts"]["art"], "heizen")
        self.assertEqual(s2["rechts"]["titel"], "Heizen mit Sonnenstrom")
        self.assertEqual([st["name"] for st in s2["treppe"]["stufen"]], [st["name"] for st in e["treppe"]])
        self.assertIsNone(s2["treppe"]["hinweis"])
        self.assertEqual(s2["treppe"]["spalten"], len(e["treppe"]))
        self.assertEqual(len(s3["szenarien"]["saeulen"]), len(e["szenarien"]))
        self.assertEqual([k["label"] for k in s3["klima"]["kacheln"]],
                         ["pro Jahr vermieden", f"in {e['n']} Jahren", "Autofahrt pro Jahr", "gleiche Wirkung"])
        self.assertTrue(s3["klima"]["kacheln"][0]["wert"].endswith("t CO₂"))
        self.assertEqual(s3["annahmen"]["schritte"][0], "Angebot annehmen")
        self.assertEqual(s3["annahmen"]["weiter_eyebrow"], "SO GEHT ES WEITER")
        self.assertEqual(w["kopf"]["nummer"], a.nummer)

    def test_varianten_ohne_wp_speicher_spot(self):
        a = self.pv_angebot(PO07=0, PA13="Nein")             # ohne Wärmepumpe, ohne SpotDynamic
        w = pkw.kontext(self.s, a)
        s2 = w["seite2"]
        self.assertEqual(s2["rechts"]["art"], "verbrauch")
        self.assertEqual(s2["rechts"]["titel"], "Ihr Verbrauch")
        self.assertNotIn("Heizen mit Sonnenstrom", _texte(w))
        self.assertNotIn("SpotDynamic", [z["name"] for z in s2["vorteil"]["zeilen"]])
        self.assertNotIn("+ SpotDynamic", [st["name"] for st in s2["treppe"]["stufen"]])
        self.assertIsNotNone(s2["treppe"]["hinweis"])        # Netzbezug > 0 → Hinweis-Spalte
        self.assertEqual(s2["treppe"]["hinweis"]["name"], "+ SpotDynamic")
        self.assertEqual(s2["treppe"]["spalten"], len(s2["treppe"]["stufen"]) + 1)
        self.assertIn("Amortisation", " ".join(sz["amort"] for sz in w["seite3"]["szenarien"]["saeulen"]))
        self.assertNotIn("Amortisation 0 Jahre", _texte(w))
        # ohne Speicher (PA10 = 0, Sigenergy-Positionen entfernt): keine Speicher-Stufe, „nicht enthalten“
        b = self.pv_angebot(PA10=0, PA11="Nein", PA13="Nein")
        for p in list(b.positionen):
            if "Sigenergy" in (p.beschreibung or ""):
                self.s.delete(p)
        self.s.commit()
        w = pkw.kontext(self.s, self.neu(b))
        self.assertFalse([st for st in w["seite2"]["treppe"]["stufen"] if st["name"].startswith("+ Speicher")])
        speicher = next(z for z in w["seite3"]["annahmen"]["links"] if z["name"] == "Speicher")
        self.assertEqual(speicher["wert"], "nicht enthalten")
        self.assertNotIn("Sigenergy Speicher", w["seite1"]["subline"])

    def test_none_faelle(self):
        a = self.pv_angebot()
        self.assertIsNotNone(pkw.kontext(self.s, a))
        a.wirtschaftlichkeit_ausblenden = True
        self.s.commit()
        self.assertIsNone(pkw.kontext(self.s, self.neu(a)))
        a.wirtschaftlichkeit_ausblenden = False
        a.pv_json = ""
        self.s.commit()
        self.assertIsNone(pkw.kontext(self.s, self.neu(a)))     # ohne Auslegung
        self.assertIsNone(pkw.kontext(self.s, self.wp_angebot()))

    def test_demo_kontrollwerte_v22(self):
        d = pkw.demo()
        s1, s2, s3 = d["seite1"], d["seite2"], d["seite3"]
        self.assertEqual(s1["hero"]["betrag"], "66.300 €")
        self.assertTrue(s1["hero"]["text"].startswith("Das 2,7-Fache Ihrer Investition von 24.900 €"))
        self.assertEqual([k["wert"] for k in s1["hero"]["kacheln"]], ["9 Jahre", "57 %", "214 €/Monat"])
        self.assertEqual(s1["amortisation"]["chip"]["text"], "Break-even 2035")
        self.assertEqual(s1["amortisation"]["start_text"], "Start 2027: Investition 24.900 €")
        self.assertEqual(s1["amortisation"]["balken"][-1]["kum_text"], "+41.356 €")
        self.assertEqual([t["text"] for t in s1["amortisation"]["satz"]],
                         ["Ab 2035 arbeitet die Anlage nur noch für Sie: ", "rund 41.400 € Gewinn bis 2046", "."])
        self.assertEqual([k["wert"] for k in s2["kosten"]["kacheln"]], ["79.800 €", "13.500 €", "66.300 €"])
        self.assertEqual([z["betrag"] for z in s2["vorteil"]["zeilen"]],
                         ["2.970 €", "− 1.269 €", "+ 388 €", "+ 577 €", "− 100 €"])
        self.assertEqual(s2["vorteil"]["summe"]["betrag"], "2.565 €")
        self.assertEqual([st["name"] for st in s2["treppe"]["stufen"]],
                         ["PV-Anlage allein", "+ Speicher 10 kWh", "+ Friondo HEMS", "+ SpotDynamic"])
        self.assertEqual([st["betrag"] for st in s2["treppe"]["stufen"]],
                         ["1.261 €", "1.835 €", "1.988 €", "2.565 €"])
        self.assertEqual([st["delta"] for st in s2["treppe"]["stufen"]], ["Basis", "+ 573 €", "+ 154 €", "+ 577 €"])
        self.assertEqual([sz["summe"] for sz in s3["szenarien"]["saeulen"]], ["55.200 €", "66.300 €", "80.300 €"])
        self.assertEqual([sz["amort"] for sz in s3["szenarien"]["saeulen"]],
                         ["Amortisation 10 Jahre", "Amortisation 9 Jahre", "Amortisation 9 Jahre"])
        self.assertEqual([sz["note"] for sz in s3["szenarien"]["saeulen"]],
                         ["vorsichtig gerechnet", "Ihre Rechnung", "bei stark steigenden Preisen"])
        self.assertEqual([k["wert"] for k in s3["klima"]["kacheln"]], ["3,9 t CO₂", "76 t CO₂", "32.900 km", "315 Bäume"])
        self.assertEqual(s3["annahmen"]["schritte"][2], "Montage in 1–2 Tagen")
        self.assertIn("Familie Mustermann", s1["subline"])
        self.assertEqual(pdf_kontext.demo_kontext("PV")["wirtschaftlichkeit"]["seite1"]["hero"]["betrag"], "66.300 €")
        self.assertIsNone(pdf_kontext.demo_kontext("WP")["wirtschaftlichkeit"])

    def test_rechenkern_unveraendert(self):
        e = wirtschaftlichkeit.berechnen(pkw.DEMO_PARAM, pkw.DEMO_ANLAGE)
        self.assertAlmostEqual(e["summe_ersparnis"], 66256, delta=1.0)
        self.assertEqual((e["break_even"], e["break_even_jahr"]), (9, 2035))


# --- (3) Gerendertes HTML ---------------------------------------------------------------------
class Rendering(Basis):
    def test_kfw_partial_demo(self):
        kontext = pdf_kontext.demo_kontext("WP")
        html = _rendern(VORLAGE_KFW, kontext)
        self.assertEqual(html.count('class="pdf-seite'), 1)
        for text in ("ANTRAG: KFW 458 (WOHNGEBÄUDE)", "Ihre KfW-Förderung", "zahlt die KfW", "Angebotssumme 42.830,55 €",
                     "Förderfähig bis 30.000,00 €", "KfW-Zuschuss gesamt", "= Eigenanteil", "So läuft Ihre Förderung ab",
                     "Friondo erstellt die Unterlagen", "kostenfrei, Pos. 018.", "Gut zu wissen",
                     "Das brauchen Sie für den Antrag", "(Pos. 007)", "pdf/bilder/kfw.png", "angebot_kfw.css"):
            self.assertIn(text, html, text)
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("manuell", html.lower())

    def test_kfw_partial_echtes_angebot(self):
        a = self.wp_angebot()
        kontext = pdf_kontext.demo_kontext("WP")
        kontext["kfw"] = pdf_kontext_kfw.kontext(self.s, a)
        html = _rendern(VORLAGE_KFW, kontext)
        for text in ("19.600,00 €", "16.392,06 €", "35.992,06 €", "Einkommensbonus (24 %)",
                     "gedeckelt", f"Pos. {kontext['kfw']['pos_bza']}."):
            self.assertIn(text, html, text)

    def test_wirtschaftlichkeit_partial_demo(self):
        kontext = pdf_kontext.demo_kontext("PV")
        html = _rendern(VORLAGE_WI, kontext)
        self.assertEqual(html.count('class="pdf-seite'), 3)
        for text in ("WIRTSCHAFTLICHKEITSBETRACHTUNG", "So rechnet sich Ihre Energielösung", "IHRE ERSPARNIS IN 20 JAHREN",
                     "66.300 €", "Break-even 2035", "Was Sie Jahr für Jahr sparen", "Heizen mit Sonnenstrom",
                     "Was jeder Baustein bringt", "So sicher ist Ihre Rechnung", "Drei Strompreis-Szenarien",
                     "Ihr Beitrag zum Klima", "CO₂", "SO GEHT ES WEITER", "Montage in 1–2 Tagen",
                     "angebot_wirtschaftlichkeit.css"):
            self.assertIn(text, html, text)
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

    def test_keine_hex_farben_in_den_partials(self):
        for name in ("kfw.html", "wirtschaftlichkeit.html"):
            text = (TEMPLATES / name).read_text(encoding="utf-8")
            self.assertFalse(HEX.findall(text), name)
            self.assertNotIn("{% extends", text)


# --- (4) Browser-Druck ------------------------------------------------------------------------
@unittest.skipUnless(BROWSER["ok"], f"kein Browser für den PDF-Druck: {BROWSER.get('fehler')}")
class Druck(Basis):
    def test_kfw_seite_eine_seite(self):
        kontext = pdf_kontext.demo_kontext("WP")
        seiten, pdf = _pdf_seiten(_rendern(VORLAGE_KFW, kontext), kontext)
        BILDER.mkdir(parents=True, exist_ok=True)
        (BILDER / "test-kfw-demo.pdf").write_bytes(pdf)
        self.assertEqual(len(seiten), 1)
        text = seiten[0]
        for erwartet in ("Ihre KfW-Förderung", "KfW-Zuschuss gesamt", "16.500,00 €", "26.330,55 €",
                         "So läuft Ihre Förderung ab", "GUT ZU WISSEN", "Pos. 018", "SEITE 1 VON 1"):
            self.assertIn(erwartet, text, erwartet)

    def test_wirtschaftlichkeit_drei_seiten(self):
        kontext = pdf_kontext.demo_kontext("PV")
        seiten, pdf = _pdf_seiten(_rendern(VORLAGE_WI, kontext), kontext)
        BILDER.mkdir(parents=True, exist_ok=True)
        (BILDER / "test-wirtschaftlichkeit-demo.pdf").write_bytes(pdf)
        self.assertEqual(len(seiten), 3)
        self.assertIn("So rechnet sich Ihre Energielösung", seiten[0])
        self.assertNotIn("Seite 1 von 3", seiten[0])                      # nur die Dokument-Seitenzahl
        self.assertIn("SEITE 1 VON 3", seiten[0])
        self.assertIn("Break-even 2035", seiten[0])
        self.assertIn("Was Sie Jahr für Jahr sparen", seiten[1])
        self.assertIn("Heizen mit Sonnenstrom", seiten[1])
        self.assertIn("So sicher ist Ihre Rechnung", seiten[2])
        self.assertIn("SO GEHT ES WEITER", seiten[2])
        self.assertIn("SEITE 3 VON 3", seiten[2])
        for i, s in enumerate(seiten, 1):
            self.assertGreater(len(s.strip()), 400, f"Seite {i} fast leer")

    def test_wirtschaftlichkeit_variante_ohne_wp_speicher_spot(self):
        anlage = dict(pkw.DEMO_ANLAGE, wp_kwh=0, speicher_kwh=0, hems=False, spot=False)
        daten = {"anlage": anlage, "param": pkw.DEMO_PARAM, "fehlende_parameter": [],
                 "ergebnis": wirtschaftlichkeit.berechnen(pkw.DEMO_PARAM, anlage)}
        kontext = pdf_kontext.demo_kontext("PV")
        kontext["wirtschaftlichkeit"] = pkw.aufbereiten(daten, pkw.demo()["kopf"])
        seiten, pdf = _pdf_seiten(_rendern(VORLAGE_WI, kontext), kontext)
        (BILDER / "test-wirtschaftlichkeit-variante.pdf").write_bytes(pdf)
        self.assertEqual(len(seiten), 3)
        self.assertIn("Ihr Verbrauch", seiten[1])
        self.assertNotIn("Heizen mit Sonnenstrom", seiten[1])
        self.assertIn("sprechen Sie uns an", seiten[1])
        self.assertIn("nicht enthalten", seiten[2])


if __name__ == "__main__":
    unittest.main()
