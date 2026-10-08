# Tests v27-Nachtrag 2 (PLAN_V17, Nachtrag 06.10.2026 – Agent N): Anhänge Klima
# (Blatt „Anhänge“ mit „Bosch Climate 3200i.pdf“, Regel „immer“ unabhängig von
# Sparte/Profil, tolerante Dateisuche), E-Mail-Vorlage je Sparte (Ableitung,
# Migration, Reihenfolge AD → Sparte → Standard, Versand-Route, Parametrierung)
# und die neue Anmeldeseite (zweispaltig, Häkchen nur Außendienst/Montage,
# Fehlermeldung unter dem Knopf). Die Versand- und Seiten-Tests laufen gegen die
# Entwicklungs-DB (DB_PFAD_OVERRIDE); Testdaten tragen das Präfix „V27N “ bzw. die
# Test-E-Mail und werden wieder aufgeräumt. Graph und PDF sind gemockt – es wird
# nie eine echte Mail erzeugt.
import datetime
import re
import tempfile
import unittest
import unicodedata
import warnings
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import angebot_aufbau, anhaenge, auth, config, graph_versand, mail_vorlagen
from app import logik as logik_modul
from app.db import Base, SessionLocal, init_db
from app.logik import Anhang
from app.main import app
from app.models import (Angebot, AngebotsPosition, Benutzer, Erfassung, Kunde, Vorgang,
                        einstellung_holen, einstellung_setzen)

PRAEFIX = "V27N "
TEST_EMAIL = "v27n-nachtrag2@test.local"
UNTERNEHMEN = "Friondo Unternehmenspräsentation.pdf"
RATENKAUF = "Broschüre Ratenkauf.pdf"
BOSCH_KL = "Bosch Climate 3200i.pdf"
ERWARTET_KL_STANDARD = [UNTERNEHMEN, RATENKAUF, BOSCH_KL]


def blatt_anhaenge() -> list[Anhang]:
    """Die Anhangsregeln der Live-Excel (nur das Blatt, ohne volle Logik)."""
    import openpyxl
    wb = openpyxl.load_workbook(config.LOGIK_EXCEL_PFAD, read_only=True, data_only=True)
    try:
        return logik_modul._anhaenge_einlesen(wb, logik_modul.Pruefbericht())
    finally:
        wb.close()


def fake_logik(eintraege=None):
    return SimpleNamespace(anhaenge=eintraege if eintraege is not None else blatt_anhaenge(),
                           fragen={})


def angebot_objekt(sparte: str) -> Angebot:
    """Transientes Angebot (ohne DB) für die Anhangsregeln."""
    return Angebot(nummer=f"AN-C-{sparte}", konfigurator_typ=sparte, protokoll_json="[]")


def fake_dateien(ordner: Path, namen) -> None:
    for name in namen:
        (ordner / name).write_bytes(b"%PDF-1.4 test " + name.encode("utf-8"))


def aufraeumen(s):
    s.rollback()
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.delete(b)
    s.commit()


# --- 1. Anhänge Klima ---------------------------------------------------------------

class AnhaengeKlima(unittest.TestCase):
    def test_blatt_anhaenge_bosch_climate(self):
        eintraege = blatt_anhaenge()
        self.assertFalse([a for a in eintraege if a.datei.startswith("(Bosch Climate")])
        bosch = [a for a in eintraege if a.datei == BOSCH_KL]
        self.assertEqual(len(bosch), 1)
        self.assertEqual((bosch[0].art, bosch[0].antwort, bosch[0].regel_roh),
                         ("sparte", "KL", "wenn Sparte = KL"))
        self.assertEqual(bosch[0].bemerkung, "Gerätebroschüre Bosch Climate 3200i (v27)")
        self.assertEqual(bosch[0].nicht_bei_profil, [])
        # Datei liegt seit 06.10.2026 im Ordner anlagen/
        self.assertTrue((config.ANLAGEN_ORDNER / BOSCH_KL).exists())
        # „immer“-Zeilen unverändert
        immer = [a.datei for a in eintraege if a.art == "immer"]
        self.assertEqual(immer, [UNTERNEHMEN, RATENKAUF])

    def test_kl_versand_anhaenge_je_profil(self):
        logik = fake_logik()
        with tempfile.TemporaryDirectory() as ordner:
            ordner = Path(ordner)
            fake_dateien(ordner, [a.datei for a in logik.anhaenge])
            with mock.patch.object(config, "ANLAGEN_ORDNER", ordner):
                kl = anhaenge.fuer_angebot(logik, angebot_objekt("KL"), "Standard")
                self.assertEqual([a.datei for a in kl], ERWARTET_KL_STANDARD)
                self.assertTrue(all(a.vorhanden for a in kl))
                self.assertTrue(all(Path(a.pfad).parent == ordner for a in kl))
                for profil in ("Enni", "SWD"):
                    dateien = [a.datei for a in anhaenge.fuer_angebot(logik, angebot_objekt("KL"), profil)]
                    self.assertEqual(dateien, [UNTERNEHMEN, BOSCH_KL], profil)
                # WP/PV unverändert: keine Klima-Broschüre, „immer“-Anhänge wie bisher
                for sparte in ("WP", "PV"):
                    dateien = [a.datei for a in anhaenge.fuer_angebot(logik, angebot_objekt(sparte), "Standard")]
                    self.assertEqual(dateien, [UNTERNEHMEN, RATENKAUF], sparte)
                # ohne Profilname (Alt-DB ohne Profile): Ratenkauf bleibt dabei
                self.assertIn(RATENKAUF, [a.datei for a in anhaenge.fuer_angebot(logik, angebot_objekt("KL"))])

    def test_immer_regel_unabhaengig_von_reihenfolge_sparte_und_profil(self):
        # Sparten-Zeile VOR der „immer“-Zeile, Profil SWD: „immer“ bleibt
        logik = fake_logik([Anhang(BOSCH_KL, "wenn Sparte = KL", "sparte", antwort="KL"),
                            Anhang(UNTERNEHMEN, "immer", "immer"),
                            Anhang(RATENKAUF, "immer", "immer", nicht_bei_profil=["Enni", "SWD"])])
        with tempfile.TemporaryDirectory() as ordner:
            ordner = Path(ordner)
            fake_dateien(ordner, [UNTERNEHMEN, RATENKAUF, BOSCH_KL])
            with mock.patch.object(config, "ANLAGEN_ORDNER", ordner):
                for sparte, profil in (("KL", "SWD"), ("KL", "Standard"), ("WP", "Enni"), ("PV", "")):
                    dateien = [a.datei for a in anhaenge.fuer_angebot(logik, angebot_objekt(sparte), profil)]
                    self.assertIn(UNTERNEHMEN, dateien, (sparte, profil))
                    self.assertEqual(BOSCH_KL in dateien, sparte == "KL", (sparte, profil))

    def test_tolerante_dateisuche_und_fehlende_dateien(self):
        logik = fake_logik()
        with tempfile.TemporaryDirectory() as ordner:
            ordner = Path(ordner)
            # Umlaut in Normalform NFD (z. B. nach Kopie über macOS/OneDrive) und
            # andere Groß-/Kleinschreibung – beides wird gefunden
            fake_dateien(ordner, [unicodedata.normalize("NFD", UNTERNEHMEN),
                                  "bosch climate 3200i.PDF", RATENKAUF])
            with mock.patch.object(config, "ANLAGEN_ORDNER", ordner):
                kl = {a.datei: a for a in anhaenge.fuer_angebot(logik, angebot_objekt("KL"), "Standard")}
                self.assertEqual(set(kl), set(ERWARTET_KL_STANDARD))
                self.assertTrue(all(a.vorhanden for a in kl.values()))
                self.assertTrue(Path(kl[UNTERNEHMEN].pfad).exists())
                self.assertTrue(Path(kl[UNTERNEHMEN].pfad).samefile(
                    ordner / unicodedata.normalize("NFD", UNTERNEHMEN)))
                # NTFS findet den Namen schon case-insensitiv (Pfad behält die Excel-
                # Schreibweise); auf case-sensitiven Systemen liefert die tolerante
                # Suche die tatsächliche Datei – in beiden Fällen dieselbe Datei
                self.assertTrue(Path(kl[BOSCH_KL].pfad).samefile(ordner / "bosch climate 3200i.PDF"))
                # fehlende Dateien des Blatts: HEMS, SpotDynamic, CS3800, CS8800
                fehlend = anhaenge.fehlende_dateien(logik)
                self.assertNotIn(UNTERNEHMEN, fehlend)
                self.assertNotIn(BOSCH_KL, fehlend)
                self.assertIn("Friondo HEMS.pdf", fehlend)
            # echter Ordner: alle Klima-Anhänge vorhanden, CS8800 fehlt weiterhin (Zulieferung)
            fehlend = anhaenge.fehlende_dateien(logik)
            self.assertFalse(set(fehlend) & set(ERWARTET_KL_STANDARD), fehlend)
            # Datei fehlt → vorhanden=False, Pfad zeigt auf den erwarteten Namen
            with tempfile.TemporaryDirectory() as leer:
                with mock.patch.object(config, "ANLAGEN_ORDNER", Path(leer)):
                    kl = anhaenge.fuer_angebot(logik, angebot_objekt("KL"), "Standard")
                    self.assertEqual([a.datei for a in kl if not a.vorhanden], ERWARTET_KL_STANDARD)


# --- 2. E-Mail-Vorlage je Sparte ----------------------------------------------------

class SpartenVorlagen(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = sessionmaker(bind=engine)()
        self.kunde = Kunde(anrede="Frau", vorname="Erika", nachname="Beispiel")
        self.ad = Benutzer(name="Rene Golaschewski", rolle="aussendienst", email="rene@friondo.de")
        self.s.add_all([self.kunde, self.ad])
        self.s.commit()
        self.kl = self._angebot("AN-C-260101", "KL")
        self.wp = self._angebot("AN-C-260102", "WP")
        self.pv = self._angebot("AN-C-260103", "PV")

    def _angebot(self, nummer, sparte):
        a = Angebot(nummer=nummer, kunde_id=self.kunde.id, konfigurator_typ=sparte,
                    datum=datetime.datetime(2026, 10, 1), ust_satz=19.0 if sparte != "PV" else 0.0,
                    kfw_json="{}")
        a.positionen = [AngebotsPosition(sort=1, bezeichnung="x", menge=1, e_preis_cent=100000)]
        self.s.add(a)
        self.s.commit()
        self.s.add(Erfassung(kunde_id=self.kunde.id, benutzer_id=self.ad.id,
                             angebot_id=a.id, antworten_json="{}"))
        self.s.commit()
        return a

    def test_ableitung_kl_pv_wb_wp(self):
        b, t, weg = mail_vorlagen.sparten_vorlage_ableiten(
            mail_vorlagen.STANDARD_BETREFF, mail_vorlagen.STANDARD_TEXT, "KL")
        self.assertEqual(b, "Ihr Klimaanlagen-Angebot {angebotsnummer} der Friondo GmbH")
        self.assertIn("Interesse an einer Klimaanlage der Friondo GmbH", t)
        self.assertNotIn("Wärmepumpe", t)
        self.assertEqual(weg, [])
        b, t, _ = mail_vorlagen.sparten_vorlage_ableiten(
            mail_vorlagen.STANDARD_BETREFF, mail_vorlagen.STANDARD_TEXT, "PV")
        self.assertEqual(b, "Ihr PV-Angebot {angebotsnummer} der Friondo GmbH")
        self.assertIn("Interesse an einer PV-Anlage der Friondo GmbH", t)
        self.assertNotIn("Wärmepumpe", t)
        # Plan-Wortlaut ohne Bindestrich
        self.assertEqual(mail_vorlagen.sparten_vorlage_ableiten("Wärmepumpenangebot", "x", "KL")[0],
                         "Klimaanlagenangebot")
        self.assertEqual(mail_vorlagen.sparten_vorlage_ableiten("Wärmepumpenangebot", "x", "PV")[0],
                         "PV-Angebot")
        # WB und WP: unveränderte Kopie
        for sparte in ("WB", "WP"):
            self.assertEqual(mail_vorlagen.sparten_vorlage_ableiten(
                mail_vorlagen.STANDARD_BETREFF, mail_vorlagen.STANDARD_TEXT, sparte),
                (mail_vorlagen.STANDARD_BETREFF, mail_vorlagen.STANDARD_TEXT, []))

    def test_saetze_mit_foerderplatzhaltern_entfernt(self):
        text = ("{briefanrede}\n\nvielen Dank für Ihr Interesse an einer Wärmepumpe. "
                "Ihr Eigenanteil nach Förderung beträgt z. B. {eigenanteil}. "
                "Die Förderung liegt bei {foerderung}! Anbei Ihr Angebot {angebotsnummer}.\n\n"
                "Förderung: {foerderung}\n\nMit freundlichen Grüßen")
        b, t, weg = mail_vorlagen.sparten_vorlage_ableiten("Angebot {eigenanteil}", text, "KL")
        self.assertEqual(b, "Angebot")
        self.assertEqual(t, "{briefanrede}\n\nvielen Dank für Ihr Interesse an einer Klimaanlage. "
                            "Anbei Ihr Angebot {angebotsnummer}.\n\nMit freundlichen Grüßen")
        self.assertEqual(weg, ["Ihr Eigenanteil nach Förderung beträgt z. B. {eigenanteil}.",
                               "Die Förderung liegt bei {foerderung}!",
                               "Förderung: {foerderung}"])
        # HTML-Vorlage (v6): Satz über Inline-Tags hinweg, leerer Absatz fällt weg
        html = ("<p>{briefanrede}</p><p>Text zur Wärmepumpe.<br>Ihr Eigenanteil beträgt "
                "<strong>{eigenanteil}</strong>. Weiter geht es.</p><p>Förderung: {foerderung}</p>")
        _, t, weg = mail_vorlagen.sparten_vorlage_ableiten("B", html, "PV")
        self.assertEqual(t, "<p>{briefanrede}</p><p>Text zur PV-Anlage.<br>Weiter geht es.</p>")
        self.assertEqual(weg, ["Ihr Eigenanteil beträgt {eigenanteil}.", "Förderung: {foerderung}"])
        for p in mail_vorlagen.NUR_WP_PLATZHALTER:
            self.assertNotIn(p, t)

    def test_migration_sparten_idempotent(self):
        # eigene WB-Vorlage vorab: bleibt unverändert
        mail_vorlagen.sparten_vorlage_speichern(self.s, "WB", "WB eigen", "WB Text")
        meldungen = mail_vorlagen.migration_sparten(self.s)
        self.s.commit()
        self.assertEqual(einstellung_holen(self.s, mail_vorlagen.MIGRATION_MARKER, ""), "erledigt")
        self.assertTrue(any(m.startswith("E-Mail-Vorlage KL (Klimaanlage)") for m in meldungen), meldungen)
        self.assertTrue(any("WB: eigene Vorlage vorhanden" in m for m in meldungen), meldungen)
        self.assertEqual(mail_vorlagen.sparten_vorlage_laden(self.s, "WB"), ("WB eigen", "WB Text"))
        self.assertEqual(mail_vorlagen.sparten_vorlage_laden(self.s, "KL")[0],
                         "Ihr Klimaanlagen-Angebot {angebotsnummer} der Friondo GmbH")
        self.assertEqual(mail_vorlagen.sparten_vorlage_laden(self.s, "PV")[0],
                         "Ihr PV-Angebot {angebotsnummer} der Friondo GmbH")
        # Nachtrag 08.10.2026 (Antwort Andreas): WP bekommt keine Kopie – WP = Standard-Vorlage
        self.assertIsNone(mail_vorlagen.sparten_vorlage_laden(self.s, "WP"))
        self.assertEqual(mail_vorlagen.sparten_status(self.s),
                         {"WP": False, "PV": True, "KL": True, "WB": True})
        self.assertEqual(einstellung_holen(self.s, mail_vorlagen.MIGRATION_MARKER_WP, ""), "erledigt")
        # zweiter Lauf: keine Meldungen, nichts geändert
        self.assertEqual(mail_vorlagen.migration_sparten(self.s), [])
        # eine vom ersten Durchlauf (vor dem Nachtrag) angelegte, unveränderte WP-Kopie wird
        # einmalig entfernt; eine von Hand geänderte WP-Vorlage bleibt
        mail_vorlagen.sparten_vorlage_speichern(self.s, "WP", mail_vorlagen.STANDARD_BETREFF,
                                                mail_vorlagen.STANDARD_TEXT)
        einstellung_setzen(self.s, mail_vorlagen.MIGRATION_MARKER_WP, "")
        meldungen = mail_vorlagen.migration_sparten(self.s)
        self.assertTrue(any("WP: unveränderte Kopie" in m for m in meldungen), meldungen)
        self.assertIsNone(mail_vorlagen.sparten_vorlage_laden(self.s, "WP"))
        mail_vorlagen.sparten_vorlage_speichern(self.s, "WP", "WP eigen", "WP eigener Text")
        einstellung_setzen(self.s, mail_vorlagen.MIGRATION_MARKER_WP, "")
        self.assertEqual(mail_vorlagen.migration_sparten(self.s), [])
        self.assertEqual(mail_vorlagen.sparten_vorlage_laden(self.s, "WP"), ("WP eigen", "WP eigener Text"))
        mail_vorlagen.sparten_vorlage_speichern(self.s, "WP", "", "")
        # Migration folgt der GEÄNDERTEN Standard-Vorlage (frische DB)
        s2 = sessionmaker(bind=create_engine("sqlite:///:memory:"))()
        Base.metadata.create_all(s2.get_bind())
        einstellung_setzen(s2, "mail_vorlage_standard_betreff", "Wärmepumpenangebot {angebotsnummer}")
        einstellung_setzen(s2, "mail_vorlage_standard_text",
                           "Hallo, Ihre Wärmepumpe. Eigenanteil: {eigenanteil}. Danke.")
        meldungen = mail_vorlagen.migration_sparten(s2)
        self.assertEqual(mail_vorlagen.sparten_vorlage_laden(s2, "KL"),
                         ("Klimaanlagenangebot {angebotsnummer}", "Hallo, Ihre Klimaanlage. Danke."))
        self.assertIn("E-Mail-Vorlage KL: Satz entfernt: „Eigenanteil: {eigenanteil}.“", meldungen)
        # Nachtrag 08.10.2026: WP ohne Kopie – der Standard gilt
        self.assertIsNone(mail_vorlagen.sparten_vorlage_laden(s2, "WP"))

    def test_reihenfolge_ad_sparte_standard(self):
        # ohne Sparten-Vorlage: Standard (wie v5)
        betreff, text, quelle = mail_vorlagen.mail_fuer_angebot(self.s, self.kl, self.kunde)
        self.assertEqual(quelle, "Standard-Vorlage")
        self.assertTrue(betreff.startswith("Ihr Wärmepumpen-Angebot AN-C-260101"))
        mail_vorlagen.migration_sparten(self.s)
        self.s.commit()
        # KL → Sparten-Vorlage KL, ohne Eigenanteil
        betreff, text, quelle = mail_vorlagen.mail_fuer_angebot(self.s, self.kl, self.kunde, "Ida")
        self.assertEqual(quelle, "Sparten-Vorlage KL")
        self.assertEqual(betreff, "Ihr Klimaanlagen-Angebot AN-C-260101 der Friondo GmbH")
        self.assertIn("einer Klimaanlage der Friondo GmbH", text)
        self.assertNotIn("Eigenanteil", text)
        self.assertNotIn("Wärmepumpe", text)
        self.assertNotIn("{", text)
        # WP unverändert (Inhalt = Standard-Vorlage)
        betreff, text, quelle = mail_vorlagen.mail_fuer_angebot(self.s, self.wp, self.kunde, "Ida")
        self.assertEqual(quelle, "Standard-Vorlage")   # Nachtrag 08.10.2026: WP = Standard, keine Kopie
        self.assertEqual(betreff, "Ihr Wärmepumpen-Angebot AN-C-260102 der Friondo GmbH")
        werte = mail_vorlagen.werte_fuer_angebot(self.s, self.wp, self.kunde, "Ida")
        self.assertEqual(text, mail_vorlagen.einsetzen_html(
            mail_vorlagen.als_html(mail_vorlagen.STANDARD_TEXT), werte))
        # PV → Sparten-Vorlage PV
        betreff, _, quelle = mail_vorlagen.mail_fuer_angebot(self.s, self.pv, self.kunde)
        self.assertEqual((quelle, betreff), ("Sparten-Vorlage PV",
                                             "Ihr PV-Angebot AN-C-260103 der Friondo GmbH"))
        # AD-Vorlage geht vor der Sparten-Vorlage
        mail_vorlagen.vorlage_speichern(self.s, self.ad.id, "Rene: {angebotsnummer}", "Moin {vorname}")
        self.s.commit()
        betreff, text, quelle = mail_vorlagen.mail_fuer_angebot(self.s, self.kl, self.kunde)
        self.assertEqual((quelle, betreff, text),
                         ("Vorlage Rene Golaschewski", "Rene: AN-C-260101", "<p>Moin Erika</p>"))
        mail_vorlagen.vorlage_speichern(self.s, self.ad.id, "", "")
        # Sparten-Vorlage entfernt → Standard
        mail_vorlagen.sparten_vorlage_speichern(self.s, "KL", "", "")
        self.s.commit()
        self.assertEqual(mail_vorlagen.mail_fuer_angebot(self.s, self.kl, self.kunde)[2],
                         "Standard-Vorlage")
        self.assertFalse(mail_vorlagen.sparten_status(self.s)["KL"])
        # vorlage_laden ohne Sparte (Parametrierung, Abnahme) unverändert
        self.assertEqual(mail_vorlagen.vorlage_laden(self.s, None)[2], "Standard-Vorlage")
        self.assertEqual(mail_vorlagen.vorlage_laden(self.s, None, "PV")[2], "Sparten-Vorlage PV")
        self.assertEqual(mail_vorlagen.vorlage_laden(self.s, None, "XX")[2], "Standard-Vorlage")

    def test_platzhalter_pv_kl_leer_wp_unveraendert(self):
        for angebot in (self.kl, self.pv):
            werte = mail_vorlagen.werte_fuer_angebot(self.s, angebot, self.kunde)
            self.assertEqual((werte["eigenanteil"], werte["foerderung"]), ("", ""), angebot.nummer)
        werte = mail_vorlagen.werte_fuer_angebot(self.s, self.wp, self.kunde)
        self.assertEqual((werte["eigenanteil"], werte["foerderung"]), ("–", "–"))

    def test_kombi_versand_behaelt_eigene_vorlage(self):
        mail_vorlagen.migration_sparten(self.s)
        self.s.commit()
        betreff, text = mail_vorlagen.kombi_mail_fuer_vorgang(self.s, [self.kl, self.wp], self.kunde, "Ida")
        self.assertEqual(betreff, "Ihre Angebote AN-C-260101, AN-C-260102 – Friondo GmbH")
        self.assertIn("KL-Angebot AN-C-260101", text)
        self.assertIn("WP-Angebot AN-C-260102", text)
        self.assertNotIn("Klimaanlagen-Angebot", betreff)


class VersandRoute(unittest.TestCase):
    """POST /angebote/{id}/email mit gemocktem Graph: Sparten-Vorlage + Anhänge."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.kunde = Kunde(anrede="Herr", vorname="Kurt", nachname=f"{PRAEFIX}Klima",
                          strasse="Teststr. 2", plz="47139", ort="Duisburg", email=TEST_EMAIL)
        cls.s.add(cls.kunde)
        cls.s.commit()
        # Sparten-Vorlagen wie nach migrate.py (idempotent)
        mail_vorlagen.migration_sparten(cls.s)
        cls.s.commit()
        cls.client = TestClient(app)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def _versand(self, sparte: str):
        angebot = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, sparte=sparte)
        self.s.commit()
        aufrufe = {}

        def fake_entwurf(kunde, angebot_, pdf_pfad, betreff, text, **kw):
            aufrufe.update(kw, betreff=betreff, text=text, pdf=pdf_pfad)
            return True, "Entwurf im Postfach abgelegt – Test.", "https://outlook/x", "konv-n"

        with tempfile.TemporaryDirectory() as ordner:
            ordner = Path(ordner)
            fake_dateien(ordner, [a.datei for a in blatt_anhaenge()])
            pdf = ordner / f"{angebot.nummer}.pdf"
            pdf.write_bytes(b"%PDF-1.4 test")
            with mock.patch.object(graph_versand, "konfiguriert", return_value=True), \
                    mock.patch.object(graph_versand, "angemeldeter_benutzer", return_value="ida@friondo.de"), \
                    mock.patch.object(graph_versand, "entwurf_erstellen", side_effect=fake_entwurf), \
                    mock.patch("app.pdf_export.pdf_fuer_angebot", return_value=pdf), \
                    mock.patch.object(config, "ANLAGEN_ORDNER", ordner):
                antwort = self.client.post(f"/angebote/{angebot.id}/email", follow_redirects=False)
        self.s.expire_all()
        return angebot, antwort, aufrufe

    def test_kl_entwurf_sparten_vorlage_und_drei_anhaenge(self):
        angebot, antwort, aufrufe = self._versand("KL")
        self.assertEqual(antwort.status_code, 303)
        ziel = unquote_plus(antwort.headers["location"])
        self.assertIn("versand=1", ziel)
        self.assertIn("Sparten-Vorlage KL", ziel)
        self.assertEqual(aufrufe["betreff"], f"Ihr Klimaanlagen-Angebot {angebot.nummer} der Friondo GmbH")
        self.assertIn("einer Klimaanlage der Friondo GmbH", aufrufe["text"])
        self.assertNotIn("Eigenanteil", aufrufe["text"])
        self.assertNotIn("Wärmepumpe", aufrufe["text"])
        self.assertEqual([p.name for p in aufrufe["weitere_anhaenge"]], ERWARTET_KL_STANDARD)
        self.assertEqual(aufrufe["fehlende_anhaenge"], [])
        self.assertEqual(self.s.get(Angebot, angebot.id).status, "Versand vorbereitet")

    def test_wp_versand_unveraendert(self):
        angebot, antwort, aufrufe = self._versand("WP")
        self.assertEqual(antwort.status_code, 303)
        self.assertEqual(aufrufe["betreff"], f"Ihr Wärmepumpen-Angebot {angebot.nummer} der Friondo GmbH")
        self.assertIn("einer Wärmepumpe der Friondo GmbH", aufrufe["text"])
        self.assertEqual([p.name for p in aufrufe["weitere_anhaenge"]], [UNTERNEHMEN, RATENKAUF])
        self.assertNotIn(BOSCH_KL, [p.name for p in aufrufe["weitere_anhaenge"]])


class VorlagenSeite(unittest.TestCase):
    """Parametrierung → E-Mail-Vorlagen: Reiter je Sparte, Speichern, Entfernen."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        mail_vorlagen.migration_sparten(cls.s)
        cls.s.commit()
        cls.client = TestClient(app)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def test_reiter_speichern_entfernen(self):
        vorher = mail_vorlagen.sparten_vorlage_laden(self.s, "KL")
        try:
            r = self.client.get("/parametrierung/vorlagen")
            self.assertEqual(r.status_code, 200)
            for sp in mail_vorlagen.SPARTEN:
                self.assertIn(f'href="/parametrierung/vorlagen?sparte={sp}"', r.text)
            self.assertIn("Standard-Vorlage", r.text)
            self.assertIn("Vorlage der Sparte", r.text)
            r = self.client.get("/parametrierung/vorlagen?sparte=KL")
            self.assertEqual(r.status_code, 200)
            self.assertIn("Sparten-Vorlage KL (Klimaanlage)", r.text)
            self.assertIn('name="sparte" value="KL"', r.text)
            self.assertIn("Klimaanlagen-Angebot {angebotsnummer}", r.text)
            self.assertIn("Sparten-Vorlage entfernen", r.text)
            # unbekannte Sparte → Standard-Reiter
            r = self.client.get("/parametrierung/vorlagen?sparte=XY")
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("Sparten-Vorlage XY", r.text)
            # speichern
            r = self.client.post("/parametrierung/vorlagen",
                                 data={"sparte": "KL", "benutzer_id": "0", "aktion": "speichern",
                                       "betreff": f"{PRAEFIX}Klima {{angebotsnummer}}",
                                       "text": f"{PRAEFIX}Text {{vorname}}"},
                                 follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertTrue(r.headers["location"].startswith("/parametrierung/vorlagen?sparte=KL&meldung="))
            self.assertIn("Sparten-Vorlage KL gespeichert", unquote_plus(r.headers["location"]))
            s2 = SessionLocal()
            try:
                self.assertEqual(mail_vorlagen.sparten_vorlage_laden(s2, "KL"),
                                 (f"{PRAEFIX}Klima {{angebotsnummer}}", f"{PRAEFIX}Text {{vorname}}"))
            finally:
                s2.close()
            self.assertIn(f"{PRAEFIX}Klima", self.client.get("/parametrierung/vorlagen?sparte=KL").text)
            # leer → Fehlermeldung, nichts geändert
            r = self.client.post("/parametrierung/vorlagen",
                                 data={"sparte": "KL", "benutzer_id": "0", "betreff": "", "text": "x"},
                                 follow_redirects=False)
            self.assertIn("nicht leer", unquote_plus(r.headers["location"]))
            # entfernen → Standard gilt
            r = self.client.post("/parametrierung/vorlagen",
                                 data={"sparte": "KL", "benutzer_id": "0", "aktion": "entfernen"},
                                 follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("Sparten-Vorlage KL entfernt", unquote_plus(r.headers["location"]))
            s3 = SessionLocal()
            try:
                self.assertIsNone(mail_vorlagen.sparten_vorlage_laden(s3, "KL"))
                self.assertEqual(mail_vorlagen.vorlage_laden(s3, None, "KL")[2], "Standard-Vorlage")
            finally:
                s3.close()
            self.assertIn("noch keine eigene", self.client.get("/parametrierung/vorlagen?sparte=KL").text)
        finally:
            s4 = SessionLocal()
            try:
                if vorher is not None:
                    mail_vorlagen.sparten_vorlage_speichern(s4, "KL", vorher[0], vorher[1])
                else:
                    mail_vorlagen.sparten_vorlage_speichern(s4, "KL", "", "")
                s4.commit()
            finally:
                s4.close()


# --- 3. Anmeldeseite -----------------------------------------------------------------

OPTION = re.compile(r'<option value="(\d+)"( data-mobil="1")?>([^<]*) \((\w+)\)</option>')


class Anmeldeseite(unittest.TestCase):
    def test_zweispaltig_mit_logo_foto_und_haekchen(self):
        html = TestClient(app).get("/login").text
        for erwartet in ('class="login-buehne"', 'class="login-spalte"', 'class="login-foto"',
                         '/static/anmeldung-energiehaus.jpg', 'class="login-logo" src="/static/logo.png"',
                         "<h1>Anmeldung</h1>", 'name="benutzer_id"', 'name="pin"',
                         'name="angemeldet_bleiben"', "Auf diesem Gerät angemeldet bleiben",
                         'id="login-bleiben-block"', "login_v27.css", '<main class="login-main">',
                         'class="kopfleiste"', 'class="fusszeile"'):
            self.assertIn(erwartet, html, erwartet)
        # Häkchen-Markierung nur für Außendienst/Montage (auth.MOBILE_ROLLEN)
        optionen = OPTION.findall(html)
        self.assertTrue(optionen)
        rollen = {rolle for _, _, _, rolle in optionen}
        self.assertTrue(rollen & set(auth.MOBILE_ROLLEN), rollen)
        self.assertTrue(rollen - set(auth.MOBILE_ROLLEN), rollen)
        for _, markiert, name, rolle in optionen:
            self.assertEqual(bool(markiert), rolle in auth.MOBILE_ROLLEN, name)

    def test_fehlermeldung_unter_dem_knopf(self):
        r = TestClient(app).post("/login", data={"benutzer_id": "0", "pin": "1"},
                                 follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertIn(auth.PIN_FALSCH_TEXT, r.text)
        self.assertIn('class="meldung fehler login-fehler" role="alert"', r.text)
        self.assertLess(r.text.index("Anmelden</button>"), r.text.index(auth.PIN_FALSCH_TEXT))
        self.assertIn('class="login-buehne"', r.text)

    def test_foto_und_styles(self):
        c = TestClient(app)
        r = c.get("/static/anmeldung-energiehaus.jpg")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["content-type"].startswith("image/jpeg"))
        self.assertTrue(300_000 < len(r.content) < 600_000, len(r.content))
        css = c.get("/static/login_v27.css").text
        block = css[css.index("v27-Nachtrag 2"):css.index("Häkchen „angemeldet bleiben“ unter der PIN")]
        for erwartet in ("main.login-main", ".login-buehne", "grid-template-columns",
                         "object-fit: cover", "@media (max-width: 900px)", "@media (max-width: 500px)",
                         "max-height: 180px", "var(--friondo-blau)", "var(--friondo-dunkel)"):
            self.assertIn(erwartet, block, erwartet)
        # Farben nur über Tokens (plus Weiß), keine externen Schriften/CDNs
        self.assertEqual(set(re.findall(r"#[0-9a-fA-F]{3,6}\b", block)), {"#fff"})
        self.assertNotIn("@import", css)
        self.assertNotIn("http", block)
        self.assertNotIn("@font-face", css)


if __name__ == "__main__":
    unittest.main()
