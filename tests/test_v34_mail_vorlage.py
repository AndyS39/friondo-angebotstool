# v34 (PLAN_V21 Phase 180, Agent V): E-Mail-Vorlage je Sparte – Befund „Klima-Mailtext wird beim
# Versand nicht gezogen“. Ursache: mail_vorlagen.vorlage_laden nahm IMMER die Vorlage des
# Außendienstlers, sobald eine hinterlegt war (WP-Wortlaut) – die Sparten-Vorlage KL/PV/WB kam nie
# zum Zug. Neue Reihenfolge (Entscheidung R6): WP unverändert AD → WP-Sparte → Standard;
# PV/KL/WB: Sparten-Vorlage → AD-Vorlage → Standard. Reproduktion in einer In-Memory-DB plus
# Versand-Route mit gemocktem Graph (nie eine echte Mail).
import datetime
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import angebot_aufbau, auth, config, graph_versand, mail_vorlagen
from app.db import Base, SessionLocal, init_db
from app.main import app
from app.models import Angebot, AngebotsPosition, Benutzer, Erfassung, Kunde, Vorgang

TEST_EMAIL = "v34v-mailvorlage@test.local"
PRAEFIX = "V34V "


class Reihenfolge(unittest.TestCase):
    """Reihenfolge je Sparte (In-Memory-DB, keine Route)."""

    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = sessionmaker(bind=engine)()
        self.kunde = Kunde(anrede="Frau", vorname="Erika", nachname="Beispiel")
        self.ad = Benutzer(name="Rene Golaschewski", rolle="aussendienst", email="rene@friondo.de")
        self.s.add_all([self.kunde, self.ad])
        self.s.commit()
        self.kl = self._angebot("AN-C-260201", "KL")
        self.wp = self._angebot("AN-C-260202", "WP")
        self.pv = self._angebot("AN-C-260203", "PV")
        # WB-Angebot direkt angelegt (konfigurator_typ WB, 19 % USt – Briefing V)
        self.wb = self._angebot("AN-C-260204", "WB")
        # Sparten-Vorlagen wie nach migrate.py (KL/PV/WB abgeleitet, WP = Standard)
        mail_vorlagen.migration_sparten(self.s)
        # AD-Vorlage mit WP-Wortlaut – genau die Konstellation des Befunds
        mail_vorlagen.vorlage_speichern(self.s, self.ad.id, "Rene: Wärmepumpe {angebotsnummer}",
                                        "Moin {vorname}, Ihre Wärmepumpe.")
        self.s.commit()

    def _angebot(self, nummer, sparte):
        a = Angebot(nummer=nummer, kunde_id=self.kunde.id, konfigurator_typ=sparte,
                    datum=datetime.datetime(2026, 10, 1), ust_satz=0.0 if sparte == "PV" else 19.0,
                    kfw_json="{}")
        a.positionen = [AngebotsPosition(sort=1, bezeichnung="x", menge=1, e_preis_cent=100000)]
        self.s.add(a)
        self.s.commit()
        self.s.add(Erfassung(kunde_id=self.kunde.id, benutzer_id=self.ad.id,
                             angebot_id=a.id, antworten_json="{}"))
        self.s.commit()
        return a

    def test_kl_mit_ad_vorlage_nimmt_sparten_vorlage(self):
        # Befund reproduziert: vor v34 kam hier „Vorlage Rene Golaschewski“ (WP-Wortlaut)
        betreff, text, quelle = mail_vorlagen.mail_fuer_angebot(self.s, self.kl, self.kunde, "Ida")
        self.assertEqual(quelle, "Sparten-Vorlage KL")
        self.assertEqual(betreff, "Ihr Klimaanlagen-Angebot AN-C-260201 der Friondo GmbH")
        self.assertIn("einer Klimaanlage der Friondo GmbH", text)
        self.assertNotIn("Wärmepumpe", text)
        self.assertNotIn("Moin", text)

    def test_wp_mit_ad_vorlage_bleibt_ad_vorlage(self):
        betreff, text, quelle = mail_vorlagen.mail_fuer_angebot(self.s, self.wp, self.kunde, "Ida")
        self.assertEqual(quelle, "Vorlage Rene Golaschewski")
        self.assertEqual(betreff, "Rene: Wärmepumpe AN-C-260202")
        self.assertEqual(text, "<p>Moin Erika, Ihre Wärmepumpe.</p>")

    def test_wb_nimmt_wb_vorlage(self):
        betreff, _, quelle = mail_vorlagen.mail_fuer_angebot(self.s, self.wb, self.kunde)
        self.assertEqual(quelle, "Sparten-Vorlage WB")
        self.assertEqual(betreff, mail_vorlagen.sparten_vorlage_laden(self.s, "WB")[0]
                         .replace("{angebotsnummer}", "AN-C-260204"))

    def test_pv_nimmt_pv_vorlage(self):
        betreff, _, quelle = mail_vorlagen.mail_fuer_angebot(self.s, self.pv, self.kunde)
        self.assertEqual((quelle, betreff),
                         ("Sparten-Vorlage PV", "Ihr PV-Angebot AN-C-260203 der Friondo GmbH"))

    def test_ohne_sparten_vorlage_greift_die_ad_vorlage(self):
        # KL-Sparten-Vorlage entfernt → nächste Stufe ist die AD-Vorlage, dann der Standard
        mail_vorlagen.sparten_vorlage_speichern(self.s, "KL", "", "")
        self.s.commit()
        self.assertEqual(mail_vorlagen.mail_fuer_angebot(self.s, self.kl, self.kunde)[2],
                         "Vorlage Rene Golaschewski")
        mail_vorlagen.vorlage_speichern(self.s, self.ad.id, "", "")
        self.s.commit()
        self.assertEqual(mail_vorlagen.mail_fuer_angebot(self.s, self.kl, self.kunde)[2],
                         "Standard-Vorlage")

    def test_vorlage_laden_direkt(self):
        self.assertEqual(mail_vorlagen.SPARTEN_VORLAGE_ZUERST, ("PV", "KL", "WB"))
        # ohne Sparte (Parametrierung, Abnahme): AD-Vorlage wie v5
        self.assertEqual(mail_vorlagen.vorlage_laden(self.s, self.ad.id)[2], "Vorlage Rene Golaschewski")
        self.assertEqual(mail_vorlagen.vorlage_laden(self.s, None)[2], "Standard-Vorlage")
        self.assertEqual(mail_vorlagen.vorlage_laden(self.s, self.ad.id, "WP")[2], "Vorlage Rene Golaschewski")
        for sparte in ("KL", "PV", "WB"):
            self.assertEqual(mail_vorlagen.vorlage_laden(self.s, self.ad.id, sparte)[2],
                             f"Sparten-Vorlage {sparte}", sparte)
        # unbekannte Sparte → AD, dann Standard
        self.assertEqual(mail_vorlagen.vorlage_laden(self.s, self.ad.id, "XX")[2], "Vorlage Rene Golaschewski")
        self.assertEqual(mail_vorlagen.vorlage_laden(self.s, None, "XX")[2], "Standard-Vorlage")
        # Sparten-Vorlage mit nur einem Feld: Rückfall je Feld auf den Standard
        mail_vorlagen.sparten_vorlage_speichern(self.s, "WB", "Nur Betreff WB", "")
        self.s.commit()
        betreff, text, quelle = mail_vorlagen.vorlage_laden(self.s, self.ad.id, "WB")
        self.assertEqual((betreff, quelle), ("Nur Betreff WB", "Sparten-Vorlage WB"))
        self.assertEqual(text, mail_vorlagen.standard_vorlage_laden(self.s)[1])

    def test_kombi_versand_behaelt_eigene_vorlage(self):
        betreff, text = mail_vorlagen.kombi_mail_fuer_vorgang(self.s, [self.kl, self.wp], self.kunde, "Ida")
        self.assertEqual(betreff, "Ihre Angebote AN-C-260201, AN-C-260202 – Friondo GmbH")
        self.assertIn("KL-Angebot AN-C-260201", text)
        self.assertNotIn("Moin", text)


class VersandRoute(unittest.TestCase):
    """POST /angebote/{id}/email: KL-Angebot eines Außendienstlers MIT eigener Vorlage →
    Meldung nennt „Sparten-Vorlage KL“; WP-Angebot desselben AD → AD-Vorlage (Kontrollwert
    des Plans). Graph und PDF gemockt."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        cls._aufraeumen(cls.s)
        from sqlalchemy import func
        cls.ad = Benutzer(id=(cls.s.query(func.max(Benutzer.id)).scalar() or 0) + 1000,
                          name=f"{PRAEFIX}Vertriebler", rolle="aussendienst",
                          email="v34v-ad@test.local", pin_hash=auth.pin_hash("4321"), aktiv=True)
        cls.kunde = Kunde(anrede="Herr", vorname="Kurt", nachname=f"{PRAEFIX}Klima",
                          strasse="Teststr. 2", plz="47139", ort="Duisburg", email=TEST_EMAIL)
        cls.s.add_all([cls.ad, cls.kunde])
        cls.s.commit()
        mail_vorlagen.migration_sparten(cls.s)
        mail_vorlagen.vorlage_speichern(cls.s, cls.ad.id, "AD-Betreff {angebotsnummer}",
                                        "AD-Text zur Wärmepumpe {vorname}")
        cls.s.commit()
        cls.client = TestClient(app)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))

    @classmethod
    def tearDownClass(cls):
        cls._aufraeumen(cls.s)
        cls.s.close()

    @staticmethod
    def _aufraeumen(s):
        s.rollback()
        for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
            mail_vorlagen.vorlage_speichern(s, b.id, "", "")
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

    def _versand(self, sparte):
        angebot = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, sparte=sparte)
        self.s.add(Erfassung(kunde_id=self.kunde.id, benutzer_id=self.ad.id, angebot_id=angebot.id,
                             antworten_json="{}", sparte=sparte, konfigurator_typ=sparte,
                             status="Erledigt"))
        self.s.commit()
        aufrufe = {}

        def fake_entwurf(kunde, angebot_, pdf_pfad, betreff, text, **kw):
            aufrufe.update(kw, betreff=betreff, text=text)
            return True, "Entwurf im Postfach abgelegt – Test.", "https://outlook/x", "konv-v34"

        with tempfile.TemporaryDirectory() as ordner:
            pdf = Path(ordner) / f"{angebot.nummer}.pdf"
            pdf.write_bytes(b"%PDF-1.4 test")
            with mock.patch.object(graph_versand, "konfiguriert", return_value=True), \
                    mock.patch.object(graph_versand, "angemeldeter_benutzer", return_value="ida@friondo.de"), \
                    mock.patch.object(graph_versand, "entwurf_erstellen", side_effect=fake_entwurf), \
                    mock.patch("app.pdf_export.pdf_fuer_angebot", return_value=pdf), \
                    mock.patch("app.anhaenge.fuer_angebot", return_value=[]), \
                    mock.patch.object(config, "ANLAGEN_ORDNER", Path(ordner)):
                antwort = self.client.post(f"/angebote/{angebot.id}/email", follow_redirects=False)
        self.s.expire_all()
        return angebot, antwort, aufrufe

    def test_kl_mit_ad_vorlage_meldung_sparten_vorlage(self):
        angebot, antwort, aufrufe = self._versand("KL")
        self.assertEqual(antwort.status_code, 303)
        ziel = unquote_plus(antwort.headers["location"])
        self.assertIn("Sparten-Vorlage KL", ziel)
        self.assertNotIn("AD-Betreff", aufrufe["betreff"])
        self.assertEqual(aufrufe["betreff"], f"Ihr Klimaanlagen-Angebot {angebot.nummer} der Friondo GmbH")
        self.assertNotIn("Wärmepumpe", aufrufe["text"])
        self.assertEqual(self.s.get(Angebot, angebot.id).status, "Versand vorbereitet")

    def test_wp_desselben_ad_nimmt_ad_vorlage(self):
        angebot, antwort, aufrufe = self._versand("WP")
        self.assertEqual(antwort.status_code, 303)
        ziel = unquote_plus(antwort.headers["location"])
        self.assertIn(f"Vorlage {PRAEFIX}Vertriebler", ziel)
        self.assertEqual(aufrufe["betreff"], f"AD-Betreff {angebot.nummer}")
        self.assertIn("AD-Text zur Wärmepumpe Kurt", aufrufe["text"])


if __name__ == "__main__":
    unittest.main()
