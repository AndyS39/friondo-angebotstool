# Tests v24 (PLAN_V16 Phase 115, Agent D): KL-Textblöcke („Friondo KL …“),
# Profil-Auswahl der KL-Texte, Positionsregeln bei Klima-Angeboten (kein
# Friondo Fit for Future), Angebots-PDF ohne Förderblock/Wirtschaftlichkeit/
# Vollmacht, Lieferschein ohne Preise mit Gruppe, Protokoll-PDF mit Seite
# „Auslegung“. Laufen gegen die Entwicklungs-DB wie tests/test_pv_v13.py
# (Testkunde mit eigener E-Mail, Aufräumen am Ende). Das KL-Angebot wird
# manuell angelegt (konfigurator_typ „KL“, ust_satz 19, Positionen wie
# Kontrollfall A) – unabhängig von app/kl_auslegung.py (Agent C).
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from app import angebot_aufbau, angebotsprofile, config, lieferschein_pdf, pdf_export
from app import protokoll_pdf as protokoll_modul
from app.db import SessionLocal, init_db
from app.models import (Angebot, AngebotsPosition, Erfassung, Kunde, Profil,
                        Textblock, Vorgang)

TEST_EMAIL = "kl-v24-texte@test.local"
KL_NAMEN = ("Friondo KL Standard", "Friondo KL Enni", "Friondo KL SWD",
            "Friondo KL Sparkasse DU")


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


def pdf_text(pfad) -> str:
    import pypdf
    return "\n".join(s.extract_text() for s in pypdf.PdfReader(str(pfad)).pages)


def block_text(s, art: str, name: str) -> str:
    block = s.query(Textblock).filter(Textblock.art == art, Textblock.name == name).first()
    return block.text if block is not None else ""


def position(**felder) -> AngebotsPosition:
    werte = {"block_nr": 1, "gruppe": "", "beschreibung": "", "menge": 1.0,
             "einheit": "Stück", "e_preis_cent": 0, "ep_flag": False, "ek_cent": None}
    werte.update(felder)
    return AngebotsPosition(**werte)


# Positionen wie Kontrollfall A (PLAN_V16 Phase 116): Netto 6.518,66 €
FALL_A_POSITIONEN = [
    dict(sort=1, block_nr=1, pos_nr="KL023", einheit="psl.", e_preis_cent=317800,
         ek_cent=72400, bezeichnung="Montagepauschale – 3 Innengeräte, 1 Außengerät",
         beschreibung="Diese Leistung besteht aus folgenden Positionen"),
    dict(sort=2, block_nr=2, pos_nr="KL008", einheit="psl.", e_preis_cent=49800,
         ek_cent=23000, bezeichnung="Elektroinstallation Außengerät mit Einzelabsicherung"),
    dict(sort=3, block_nr=3, gruppe="Klimaanlage Bosch", pos_nr="KL038",
         e_preis_cent=196624, ek_cent=120480,
         bezeichnung="BOSCH CL5000M 79/3 E Multisplit-Außeneinheit 7,9 kW"),
    dict(sort=4, block_nr=3, gruppe="Klimaanlage Bosch", pos_nr="KL026", menge=3.0,
         e_preis_cent=29214, ek_cent=17088,
         bezeichnung="BOSCH CL3200iU W 26 E Inneneinheit 2,6 kW"),
    dict(sort=5, block_nr=3, gruppe="Klimaanlage Bosch", pos_nr="KL013", menge=3.0,
         e_preis_cent=8250, ek_cent=5600, ep_flag=True,
         bezeichnung="BOSCH Internet-Gateway WLAN G 10 CL-1"),
    dict(sort=6, block_nr=3, gruppe="Klimaanlage Bosch", pos_nr="KL049", einheit="psl.",
         e_preis_cent=0, ek_cent=0,
         bezeichnung="Erweiterung Systemgarantie – BOSCH Systemgarantie 5 Jahre"),
    dict(sort=7, block_nr=3, gruppe="Klimaanlage Bosch", pos_nr="", einheit="psl.",
         e_preis_cent=0, ek_cent=0, bezeichnung="Auslegung der Klimaanlage",
         beschreibung=("Auslegung Klimaanlage – Serie Bosch Climate 3200i\n"
                       "Raum 1 „Wohnzimmer“: 25,0 m² × 1,0 × 60 W/m² = 1,50 kW → "
                       "Innengerät 2,6 kW (Klasse 9), Außengerät 1\n"
                       "Außengerät 1: BOSCH CL5000M 79/3 E Multisplit-Außeneinheit "
                       "7,9 kW, Multi-Split, Kombination 9+9+9, 3 Innengeräte")),
]


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.kunde = Kunde(anrede="Herr", vorname="Kurt", nachname="KL-Test v24",
                          strasse="Teststr. 2", plz="47139", ort="Duisburg",
                          email=TEST_EMAIL)
        cls.s.add(cls.kunde)
        cls.s.commit()
        angebotsprofile.seed_kl(cls.s)   # wie migrate.py (v24-Block)
        cls.s.commit()
        cls.profile = {p.regel_kennung: p for p in cls.s.query(Profil)}

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def kl_angebot(self, positionen=FALL_A_POSITIONEN) -> Angebot:
        angebot = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, sparte="KL")
        for felder in positionen:
            angebot.positionen.append(position(**felder))
        self.s.commit()
        return angebot


# --- Textblöcke -------------------------------------------------------------

class Textbloecke(Basis):
    def test_seed_kl_idempotent(self):
        namen = {n for _a, n, _t in angebotsprofile.KL_SEED_BLOECKE}
        self.assertEqual(namen, set(KL_NAMEN))                 # vier Blöcke (Namen)
        self.assertEqual(len(angebotsprofile.KL_SEED_BLOECKE), 5)   # Standard: Vor- + Nachtext
        vorher = self.s.query(Textblock).filter(Textblock.name.like("Friondo KL %")).count()
        self.assertEqual(vorher, 5)
        self.assertEqual(angebotsprofile.seed_kl(self.s), [])  # zweiter Lauf: nichts
        self.s.commit()
        self.assertEqual(self.s.query(Textblock)
                         .filter(Textblock.name.like("Friondo KL %")).count(), 5)
        for name in KL_NAMEN:
            self.assertTrue(block_text(self.s, "nachtext", name).strip(), name)
        self.assertTrue(block_text(self.s, "vortext", "Friondo KL Standard").strip())
        for name in KL_NAMEN[1:]:
            self.assertEqual(block_text(self.s, "vortext", name), "")

    def test_vortext_kl(self):
        t = angebotsprofile.KL_VORTEXT
        self.assertTrue(t.startswith("## Ihr individuelles Klimaanlagen-Angebot zum Festpreis\n"
                                     "## Angenehmes Raumklima – kühlen im Sommer, heizen in "
                                     "der Übergangszeit"))
        self.assertIn("{briefanrede}", t)
        self.assertIn("Split-Klimaanlage von Bosch", t)
        # [Haken] wie bei PV: "- " = Haken-Zeile, "* " = Haken mit fettem Anfang bis " – "
        haken = [z for z in t.splitlines() if z.startswith(("- ", "* "))]
        self.assertEqual(len(haken), 8)
        self.assertIn("- Ihre individuelle Klimaanlage – ausgelegt auf Ihre Räume", haken)
        self.assertIn("* Fachgerechte Kältetechnik – Montage, Dichtheitsprüfung und "
                      "Inbetriebnahme durch geschultes Fachpersonal nach den Vorgaben der "
                      "F-Gase-Verordnung.", haken)
        self.assertIn("* Effizienz & Komfort – Inverter-Technik mit hoher Energieeffizienz, "
                      "leiser Betrieb und auf Wunsch Steuerung per App.", haken)
        self.assertIn("**Wir sind auf Wärmepumpen und Klimatechnik spezialisiert und gehören "
                      "in der Region zu den führenden Anbietern.**", t)
        self.assertIn("Lassen Sie uns gemeinsam für ein angenehmes Raumklima sorgen!", t)
        self.assertTrue(t.endswith("Ihr Friondo-Team"))
        for verboten in ("Fördermittel", "Wärmepumpen-Angebot", "VDI 4650", "PV-Anlage"):
            self.assertNotIn(verboten, t)

    def test_nachtext_kl_standard(self):
        t = angebotsprofile.KL_STANDARD_NACHTEXT
        # Nachtext A KL – drei Änderungen
        self.assertIn("Investieren Sie jetzt in Ihre Klimalösung – ohne hohe Einmalzahlung", t)
        self.assertNotIn("Energie- oder Wärmelösung", t)
        self.assertNotIn("ab 250 € pro Monat", t)
        self.assertNotIn("ab 129 € pro Monat", t)
        self.assertNotIn("Planbare Monatsraten", t)
        self.assertNotIn("Beispielrate", t)
        self.assertIn("„Dank Cloover konnten wir unsere Anlage einfach, fair und transparent "
                      "finanzieren.“", t)
        self.assertNotIn("unsere Wärmepumpe", t)
        # Nachtext B KL – Kältetechnik statt KfW, direkt nach „Zahlung“
        self.assertIn("### Hinweis zur Kältetechnik\nDie angebotenen Geräte arbeiten mit dem "
                      "Kältemittel R32.", t)
        self.assertIn("F-Gase-Verordnung (EU) 2024/573", t)
        self.assertIn("bis 5 m je Innengerät enthalten", t)
        self.assertNotIn("KfW", t)
        self.assertNotIn("Heizungsförderung", t)
        self.assertLess(t.index("### Zahlung"), t.index("### Hinweis zur Kältetechnik"))
        self.assertLess(t.index("### Hinweis zur Kältetechnik"),
                        t.index("Wir halten uns freibleibend 30 Tage"))
        for pflicht in ("### Haftungsbegrenzung", "### Rücktrittsrecht im Zusammenhang mit "
                        "Technischer Feinplanung", "https://friondo.de/AGB",
                        "https://friondo.de/Datenschutz"):
            self.assertIn(pflicht, t)
        # Nachtext C KL – ohne aufschiebende Bedingung, Ausführungszeitraum
        self.assertIn("Voraussichtlicher Ausführungszeitraum: ______________", t)
        self.assertNotIn("Aufschiebende Bedingung", t)
        self.assertNotIn("Voraussichtliches Datum der Umsetzung", t)
        self.assertNotIn("Bewilligungszeitraum", t)
        self.assertTrue(t.rstrip().endswith("[UNTERSCHRIFT]"))
        # kein Wirtschaftlichkeits-Platzhalter, keine Vollmacht, kein Nullsteuersatz
        for verboten in ("[WIRTSCHAFTLICHKEIT]", "[BEISPIELRECHNUNG]", "Vollmacht",
                         "Nullsteuersatz", "Wärmepumpe"):
            self.assertNotIn(verboten, t)
        # drei Seiten: Zahlungsoptionen | Installationsvoraussetzungen | Schlussseite
        seiten = t.split("\n---\n")
        self.assertEqual(len(seiten), 3)
        self.assertTrue(seiten[0].startswith("# Ihre Zahlungsoptionen bei Friondo"))
        self.assertTrue(seiten[1].startswith("# Installationsvoraussetzungen"))
        self.assertTrue(seiten[2].startswith("Wir sichern Ihnen"))

    def test_nachtexte_profile(self):
        bloecke = {(a, n): t for a, n, t in angebotsprofile.KL_SEED_BLOECKE}
        for name in KL_NAMEN:
            t = bloecke[("nachtext", name)]
            for pflicht in ("### Hinweis zur Kältetechnik", "### Zahlung",
                            "Voraussichtlicher Ausführungszeitraum: ______________",
                            "[UNTERSCHRIFT]", "https://friondo.de/AGB"):
                self.assertIn(pflicht, t, name)
            for verboten in ("KfW", "[WIRTSCHAFTLICHKEIT]", "Aufschiebende Bedingung",
                             "Vollmacht", "Heizkörper-Check", "Wärmepumpe", "Netzbetreiber"):
                self.assertNotIn(verboten, t, name)
        enni = bloecke[("nachtext", "Friondo KL Enni")]
        swd = bloecke[("nachtext", "Friondo KL SWD")]
        sparkasse = bloecke[("nachtext", "Friondo KL Sparkasse DU")]
        # Enni/SWD ohne Nachtext A (wie WP): kein Cloover-Block
        for t in (enni, swd):
            self.assertNotIn("Cloover", t)
            self.assertNotIn("Investieren Sie jetzt", t)
        self.assertIn("## Barkauf oder Enni Contracting", enni)
        self.assertIn("gewünschte Klimaanlage", enni)
        self.assertIn("## Barkauf oder Contracting", swd)
        self.assertIn("# Installationsvoraussetzungen", swd)
        # Sparkasse DU mit eigenem Nachtext (Finanzierungs-Kopf) wie WP
        self.assertIn("## Finanzierung mit Sparkasse Duisburg", sparkasse)
        self.assertNotIn("Cloover", sparkasse)
        self.assertIn("gewünschte Klimaanlage", sparkasse)

    def test_kl_block_je_profil(self):
        s = self.s
        if not {"standard", "enni", "swd", "sparkasse"} <= set(self.profile):
            self.skipTest("Angebotsprofile fehlen in der Entwicklungs-DB")
        standard = block_text(s, "nachtext", "Friondo KL Standard")
        self.assertEqual(angebotsprofile._kl_block(s, "nachtext", None), standard)
        self.assertEqual(angebotsprofile._kl_block(s, "nachtext", self.profile["standard"]),
                         standard)
        for kennung, name in (("enni", "Friondo KL Enni"), ("swd", "Friondo KL SWD"),
                              ("sparkasse", "Friondo KL Sparkasse DU")):
            self.assertEqual(angebotsprofile._kl_block(s, "nachtext", self.profile[kennung]),
                             block_text(s, "nachtext", name), kennung)
            self.assertNotEqual(block_text(s, "nachtext", name), standard)
            # Vortext: nur „Friondo KL Standard“ – Kanal-Profile fallen darauf zurück
            self.assertEqual(angebotsprofile._kl_block(s, "vortext", self.profile[kennung]),
                             block_text(s, "vortext", "Friondo KL Standard"))

    def test_texte_fuer_kl_angebot(self):
        s = self.s
        angebot = self.kl_angebot(positionen=[])
        self.assertEqual(angebot.konfigurator_typ, "KL")
        self.assertEqual(angebot.ust_satz, 19.0)
        self.assertEqual(angebot.ust_bezeichnung, "19,00 % USt.")
        self.assertTrue(angebotsprofile.ist_kl(angebot))
        self.assertFalse(angebotsprofile.ist_pv(angebot))
        self.assertEqual(angebotsprofile.nachtext_fuer_angebot(s, angebot),
                         block_text(s, "nachtext", "Friondo KL Standard"))
        self.assertEqual(angebotsprofile.vortext_fuer_angebot(s, angebot),
                         block_text(s, "vortext", "Friondo KL Standard"))
        if "enni" in self.profile:
            angebot.profil_id = self.profile["enni"].id
            self.assertEqual(angebotsprofile.nachtext_fuer_angebot(s, angebot),
                             block_text(s, "nachtext", "Friondo KL Enni"))
            self.assertEqual(angebotsprofile.vortext_fuer_angebot(s, angebot),
                             block_text(s, "vortext", "Friondo KL Standard"))
            angebot.profil_id = None
        # Override am Angebot gewinnt (wie WP/PV)
        angebot.vortext_text = "Eigener Vortext"
        self.assertEqual(angebotsprofile.vortext_fuer_angebot(s, angebot), "Eigener Vortext")
        angebot.vortext_text = ""
        s.commit()
        # WP-/PV-Angebote unverändert
        wp = angebot_aufbau.angebot_anlegen(s, self.kunde.id)
        self.assertFalse(angebotsprofile.ist_kl(wp))
        self.assertNotIn("Klimaanlagen-Angebot", angebotsprofile.vortext_fuer_angebot(s, wp))
        self.assertNotIn("Hinweis zur Kältetechnik",
                         angebotsprofile.nachtext_fuer_angebot(s, wp))


# --- Positionsregeln --------------------------------------------------------

class Positionsregeln(Basis):
    def _angebot(self, typ: str) -> Angebot:
        """Angebot nur im Speicher (kein DB-Schreiben)."""
        angebot = Angebot(nummer=f"TEST-{typ}", kunde_id=self.kunde.id,
                          konfigurator_typ=typ, ust_satz=19.0)
        angebot.positionen.append(position(sort=1, pos_nr="KL020", einheit="psl.",
                                           e_preis_cent=158700,
                                           bezeichnung="Montagepauschale – 1 Innengerät"))
        angebot.positionen.append(position(sort=2, pos_nr="014", e_preis_cent=0,
                                           bezeichnung="Friondo Fit for Future"))
        angebot.positionen.append(position(sort=3, pos_nr="015", e_preis_cent=94900,
                                           bezeichnung="Friondo HEMS"))
        return angebot

    def test_kl_keine_wp_artikel(self):
        if not {"enni", "swd"} <= set(self.profile):
            self.skipTest("Profile Enni/SWD fehlen")
        for kennung in ("enni", "swd", "standard"):
            angebot = self._angebot("KL")
            meldungen = angebotsprofile.positionsregeln_anwenden(
                self.s, angebot, self.profile.get(kennung))
            self.assertEqual(meldungen, [], kennung)
            nummern = [p.pos_nr for p in angebot.positionen]
            self.assertEqual(nummern, ["KL020", "014", "015"], kennung)   # unverändert
            self.assertNotIn("162", nummern)
            hems = angebot.positionen[2]
            self.assertEqual(hems.e_preis_cent, 94900)                      # kein Sonderpreis
            self.assertFalse(hems.sonderpreis)
        # Gegenprobe WP: Enni entfernt 014, setzt den HEMS-Sonderpreis
        wp = self._angebot("WP")
        meldungen = angebotsprofile.positionsregeln_anwenden(self.s, wp, self.profile["enni"])
        self.assertTrue(meldungen)
        self.assertNotIn("014", [p.pos_nr for p in wp.positionen])
        self.assertEqual(wp.positionen[1].e_preis_cent, angebotsprofile.ENNI_SONDERPREIS_CENT)

    def test_regeln_beschreibung_kl(self):
        if "enni" not in self.profile:
            self.skipTest("Profil Enni fehlt")
        kl = self._angebot("KL")
        text = angebotsprofile.regeln_beschreibung_fuer_angebot(kl, self.profile["enni"])
        self.assertIn("Klima-Angebot", text)
        self.assertIn("CC", text)
        wp = self._angebot("WP")
        self.assertEqual(angebotsprofile.regeln_beschreibung_fuer_angebot(wp, self.profile["enni"]),
                         angebotsprofile.regeln_beschreibung(self.profile["enni"]))


# --- PDFs -------------------------------------------------------------------

class Pdf(Basis):
    def test_kl_angebot_pdf(self):
        angebot = self.kl_angebot()
        su = angebot.summen()
        self.assertEqual(su["netto"], 651866)                 # Kontrollfall A
        pfad = pdf_export.pdf_fuer_angebot(self.s, angebot)
        text = pdf_text(pfad)
        pfad.unlink(missing_ok=True)
        flach = text.replace("\n", " ")
        # Vortext KL, Gruppe, EP-Zeile, Auslegungszeile, 19 % USt
        self.assertIn("Ihr individuelles Klimaanlagen-Angebot zum Festpreis", text)
        self.assertIn("Klimaanlage Bosch", text)
        self.assertIn("EP.", text)
        self.assertIn("Auslegung der Klimaanlage", text)
        self.assertIn("19,00 % USt.", text)
        self.assertIn("6.518,66", text)
        self.assertIn("Netto-Summe", text)
        # KL-Nachtexte
        self.assertIn("Hinweis zur Kältetechnik", flach)
        self.assertIn("Voraussichtlicher Ausführungszeitraum", flach)
        self.assertIn("Ihre Zahlungsoptionen bei Friondo", flach)
        self.assertIn("Unterschrift des Auftraggebers", flach)
        # kein Förderblock, keine Wirtschaftlichkeit, keine Vollmacht, kein KfW-Text
        for verboten in ("KfW", "Eigenanteil", "voraussichtliche Förderung", "Vollmacht",
                         "So rechnet sich Ihre Energielösung", "Aufschiebende Bedingung",
                         "Nullsteuersatz", "Fördermittel-Check", "Beispielrate",
                         "ab 250 € pro Monat"):
            self.assertNotIn(verboten, flach, verboten)
        self.assertFalse(pdf_export.foerderblock_moeglich(angebot))
        self.assertFalse(pdf_export._mit_vollmacht(self.s, angebot))
        self.assertIsNone(pdf_export.wirtschaftlichkeit_fuer(self.s, angebot))

    def test_kl_lieferschein(self):
        angebot = self.kl_angebot()
        angebot.status = "Angenommen"
        self.s.commit()
        ziel = config.ANGEBOTE_PDF_ORDNER / "lieferscheine" / f"LS-{angebot.nummer}-test.pdf"
        pfad = lieferschein_pdf.erzeuge_lieferschein(angebot, self.kunde, ziel=ziel)
        text = pdf_text(pfad)
        Path(pfad).unlink(missing_ok=True)
        self.assertIn("L I E F E R S C H E I N", text)
        self.assertIn("Klimaanlage Bosch", text)                   # Gruppen-Überschrift
        self.assertIn("CL5000M 79/3 E", text)
        self.assertIn("3,00", text)                                 # Menge Innengeräte
        self.assertIn("Ware vollständig erhalten", text)
        # („USt-IdNr.“ steht in der Fußzeile jedes PDFs – daher „% USt“/„USt.“)
        for verboten in ("€", "Netto", "Summe", "% USt", "USt.", "Rabatt", "Förder",
                         "Internet-Gateway",                      # EP-Position entfällt
                         "Auslegung der Klimaanlage",             # reine Textzeile entfällt
                         "1.966,24", "3.178,00"):
            self.assertNotIn(verboten, text, verboten)
        nummern = [p.pos_nr for _n, p in lieferschein_pdf.lieferschein_positionen(angebot)]
        self.assertEqual(nummern, ["KL023", "KL008", "KL038", "KL026", "KL049"])

    def test_protokoll_pdf_seite_auslegung(self):
        # Einträge wie aus konfigurator.protokoll + kl_auslegung.protokoll_zeilen
        protokoll = [
            {"frage_id": "KO06", "seite": "Objekt & Anlage", "frage": "Geräteserie",
             "antwort": "Climate 3200i (Standard)", "ampel_grund": ""},
            {"frage_id": "KO04", "seite": "Objekt & Anlage", "frage": "Anzahl Außengeräte",
             "antwort": "2", "ampel_grund": ""},
            {"frage_id": "KR08#1", "seite": "Räume", "frage": "Raumfläche in m²",
             "antwort": "25", "ampel_grund": ""},
            {"frage_id": "", "seite": "Auslegung", "frage": "Raum 1 „Wohnzimmer“",
             "antwort": "25,0 m² · bis 2,5 m · normal · Kühllast 1,50 kW · Klasse 9 · "
                        "Außengerät 1", "ampel_grund": ""},
            {"frage_id": "", "seite": "Auslegung", "frage": "Außengerät 1",
             "antwort": "CL5000M 79/3 E · Multi-Split · Kombination 9+9+9", "ampel_grund": ""},
            {"frage_id": "", "seite": "Auslegung", "frage": "Montage",
             "antwort": "5 Innengeräte / 2 Außengeräte",
             "ampel_grund": "Montagekombination 5 Innengeräte / 2 Außengeräte nicht hinterlegt"},
        ]
        gruende = sorted({e["ampel_grund"] for e in protokoll if e["ampel_grund"]})
        pfad = protokoll_modul.erzeuge_protokoll_pdf(
            "protokoll-kl-v24-test.pdf", "Erfassung KL · Test",
            [("Sparte", "KL"), ("Kunde", "KL-Test v24")], protokoll, gruende)
        text = pdf_text(pfad)
        Path(pfad).unlink(missing_ok=True)
        flach = text.replace("\n", " ")
        self.assertIn("Abfrageprotokoll", text)
        for seite in ("Objekt & Anlage", "Räume", "Auslegung"):
            self.assertIn(seite, text)
        self.assertIn("Kombination 9+9+9", flach)
        self.assertIn("Kühllast 1,50 kW", flach)
        self.assertIn("KR08#1 · Raumfläche", flach)
        self.assertIn("AMPEL – individuell: Montagekombination 5 Innengeräte / 2 Außengeräte "
                      "nicht hinterlegt", flach)
        self.assertIn("Ampel: Individuell – Montagekombination", flach)
        # Auslegungszeilen ohne Frage-ID: kein „ · Raum 1“-Artefakt der Beschriftung
        self.assertNotIn(" · Raum 1", flach)


# --- Anhänge ----------------------------------------------------------------

class Anhaenge(Basis):
    """Die Anhangsregel „wenn Sparte = KL“ (PLAN_V16 Phase 115) braucht keinen
    neuen Code: app/logik.py liest „wenn Sparte = <Kürzel>“ als art „sparte“
    (v13-PV), Platzhalterzeilen „(…)“ werden übersprungen, und
    app/anhaenge.py vergleicht mit angebot.konfigurator_typ."""

    def test_regel_sparte_kl_lesbar(self):
        import openpyxl
        from app import logik as logik_modul
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Anhänge"
        ws.append(["Datei (in anlagen/)", "Regel", "Bemerkung", "Nicht bei Profil"])
        ws.append(["(Bosch Climate Broschüre – Zulieferung)", "wenn Sparte = KL",
                   "v24: Datei nach Lieferung in anlagen/ legen", ""])
        ws.append(["Bosch Climate Broschüre.pdf", "wenn Sparte = KL", "v24", ""])
        bericht = logik_modul.Pruefbericht()
        anhaenge = logik_modul._anhaenge_einlesen(wb, bericht)
        self.assertEqual([a.datei for a in anhaenge], ["Bosch Climate Broschüre.pdf"])
        self.assertEqual((anhaenge[0].art, anhaenge[0].antwort), ("sparte", "KL"))
        self.assertFalse([w for w in bericht.warnungen if "nicht lesbar" in w])

    def test_anhang_nur_bei_kl_angebot(self):
        from types import SimpleNamespace
        from app import anhaenge
        from app.logik import Anhang
        logik = SimpleNamespace(
            anhaenge=[Anhang("Bosch Climate Broschüre.pdf", "wenn Sparte = KL", "sparte",
                             antwort="KL"),
                      Anhang("Friondo Unternehmenspräsentation.pdf", "immer", "immer"),
                      Anhang("Broschüre Ratenkauf.pdf", "immer", "immer",
                             nicht_bei_profil=["Enni", "SWD"])],
            fragen={})
        kl = self.kl_angebot(positionen=[])
        wp = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id)
        self.s.commit()
        dateien_kl = [a.datei for a in anhaenge.fuer_angebot(logik, kl)]
        dateien_wp = [a.datei for a in anhaenge.fuer_angebot(logik, wp)]
        self.assertIn("Bosch Climate Broschüre.pdf", dateien_kl)
        self.assertNotIn("Bosch Climate Broschüre.pdf", dateien_wp)
        # „immer“ und die Profil-Ausnahme (Ratenkauf nicht bei Enni/SWD) unverändert
        self.assertIn("Friondo Unternehmenspräsentation.pdf", dateien_kl)
        self.assertIn("Broschüre Ratenkauf.pdf", dateien_kl)
        self.assertNotIn("Broschüre Ratenkauf.pdf",
                         [a.datei for a in anhaenge.fuer_angebot(logik, kl, "Enni")])


if __name__ == "__main__":
    unittest.main()
