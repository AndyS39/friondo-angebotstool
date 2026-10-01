# Tests PLAN_V15 v22, Phase 102 + 103 (Feedback-Runde Editor):
# Häkchen „Wirtschaftlichkeit im PDF ausblenden“ (PV), Gruppen-Überschrift je
# Angebot editierbar, Anker auf die neue Position, Einheit „psl.“ der
# WP-Auslegungszeile (+ Migrationsquery), zentraler Scroll-Merker.
# Laufen gegen die Entwicklungs-DB; Testdaten (Kunde v22-editor@test.local)
# werden am Ende wieder entfernt.
import re
import unittest
import warnings
from pathlib import Path
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, import_pv, pdf_export
from app import logik as logik_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (QUELLE_PV, Angebot, AngebotsPosition, Artikel, Erfassung,
                        Kunde, LeadAktivitaet, Vorgang, angebot_status_setzen)
from tests.test_pv_v13 import pv_basis
from tests.test_regression import KONTROLL_SZENARIO

TEST_EMAIL = "v22-editor@test.local"
PROJEKT = Path(__file__).resolve().parent.parent
AUSLEGUNG = "Auslegung der Wärmepumpe"


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
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
        cls.logik_voll, bericht = logik_modul.neu_einlesen(cls.s)
        assert bericht.ok, bericht.fehler
        cls.logik_pv = logik_modul.logik_fuer_sparte(cls.logik_voll, "PV")
        aufraeumen(cls.s)
        cls.kunde = Kunde(anrede="Herr", vorname="Egon", nachname="Editor v22",
                          strasse="Teststr. 22", plz="47139", ort="Duisburg",
                          email=TEST_EMAIL)
        cls.s.add(cls.kunde)
        cls.s.commit()
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def post(self, pfad, **daten):
        r = self.client.post(pfad, data=daten, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text[:300])
        return unquote_plus(r.headers["location"])

    def pv_angebot(self, **zusatz):
        a = angebot_aufbau.angebot_anlegen(
            self.s, self.kunde.id, antworten=pv_basis(PD12=20, PA10=10, **zusatz),
            logik=self.logik_pv, sparte="PV")
        self.s.commit()
        return a

    def wp_angebot(self):
        a = angebot_aufbau.angebot_anlegen(
            self.s, self.kunde.id, antworten=dict(KONTROLL_SZENARIO), logik=self.logik_voll)
        self.s.commit()
        return a


# --- Phase 102: Wirtschaftlichkeit im PDF ausblenden ---------------------------

class Wirtschaftlichkeit(Basis):
    def test_haekchen_pv(self):
        a = self.pv_angebot()
        self.assertFalse(a.wirtschaftlichkeit_ausblenden)
        self.assertIsNotNone(pdf_export.wirtschaftlichkeit_fuer(self.s, a))
        ziel = self.post(f"/angebote/{a.id}/wirtschaftlichkeit", ausblenden="on")
        self.assertIn("Wirtschaftlichkeit im PDF ausgeblendet", ziel)
        self.s.expire_all()
        self.assertTrue(a.wirtschaftlichkeit_ausblenden)
        self.assertIsNone(pdf_export.wirtschaftlichkeit_fuer(self.s, a))
        html = self.client.get(f"/angebote/{a.id}").text
        self.assertIn("Wirtschaftlichkeit im PDF ausblenden", html)
        self.assertIn(f'action="/angebote/{a.id}/wirtschaftlichkeit"', html)
        self.assertIn("Wirtschaftlichkeit wird im PDF nicht angezeigt", html)
        # Duplizieren übernimmt das Häkchen
        ziel = self.post(f"/angebote/{a.id}/duplizieren")
        dup = self.s.get(Angebot, int(re.search(r"/angebote/(\d+)", ziel).group(1)))
        self.assertTrue(dup.wirtschaftlichkeit_ausblenden)
        # Überarbeiten (neue Version) übernimmt das Häkchen
        angebot_status_setzen(a, "Versendet")
        self.s.commit()
        ziel = self.post(f"/angebote/{a.id}/ueberarbeiten")
        version = self.s.get(Angebot, int(re.search(r"/angebote/(\d+)", ziel).group(1)))
        self.assertEqual(version.vorgaenger_id, a.id)
        self.assertTrue(version.wirtschaftlichkeit_ausblenden)
        # wieder einblenden (Checkbox nicht gesendet)
        ziel = self.post(f"/angebote/{version.id}/wirtschaftlichkeit")
        self.assertIn("wieder eingeblendet", ziel)
        self.s.expire_all()
        self.assertFalse(version.wirtschaftlichkeit_ausblenden)
        self.assertIsNotNone(pdf_export.wirtschaftlichkeit_fuer(self.s, version))

    def test_wp_unveraendert(self):
        wp = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id)
        self.s.commit()
        self.post(f"/angebote/{wp.id}/wirtschaftlichkeit", ausblenden="on")
        self.s.expire_all()
        self.assertFalse(wp.wirtschaftlichkeit_ausblenden)
        html = self.client.get(f"/angebote/{wp.id}").text
        self.assertNotIn("Wirtschaftlichkeit im PDF ausblenden", html)


# --- Phase 103: Gruppen-Überschrift je Angebot ---------------------------------

class GruppenUeberschrift(Basis):
    def test_umbenennen_nur_ein_block(self):
        import pypdf
        a = self.wp_angebot()
        bloecke = sorted({p.block_nr for p in a.positionen})
        self.assertGreaterEqual(len(bloecke), 2, bloecke)
        alt = next(p.gruppe for p in a.positionen if p.block_nr == 1)
        self.assertTrue(alt)
        andere_vorher = {p.id: p.gruppe for p in a.positionen if p.block_nr != 1}
        self.assertTrue(andere_vorher)
        neu = "Neue Überschrift v22"
        ziel = self.post(f"/angebote/{a.id}/gruppe", block_nr="1", alt=alt, neu=f"  {neu}  ")
        self.assertIn("Überschrift gespeichert", ziel)
        self.s.expire_all()
        self.assertEqual({p.gruppe for p in a.positionen if p.block_nr == 1}, {neu})
        self.assertEqual({p.id: p.gruppe for p in a.positionen if p.block_nr != 1},
                         andere_vorher)
        # PDF druckt die neue Überschrift
        pfad = pdf_export.pdf_fuer_angebot(self.s, a)
        text = "\n".join(s.extract_text() or "" for s in pypdf.PdfReader(str(pfad)).pages)
        pfad.unlink(missing_ok=True)
        self.assertIn(neu, text)
        self.assertNotIn(alt, text)
        # Editor: ✎-Link + verstecktes Formular mit Originaltext
        html = self.client.get(f"/angebote/{a.id}").text
        self.assertIn("✎</a>", html)
        self.assertIn(f'action="/angebote/{a.id}/gruppe"', html)
        self.assertIn(f'name="alt" value="{neu}"', html)
        self.assertIn(f'name="neu" maxlength="300" value="{neu}"', html)
        self.assertIn("function gruppeBearbeiten", html)
        # leerer Text entfernt die Überschrift, Editor bietet „+ Überschrift“
        ziel = self.post(f"/angebote/{a.id}/gruppe", block_nr="1", alt=neu, neu="")
        self.assertIn("Überschrift entfernt", ziel)
        self.s.expire_all()
        self.assertEqual({p.gruppe for p in a.positionen if p.block_nr == 1}, {""})
        self.assertEqual({p.id: p.gruppe for p in a.positionen if p.block_nr != 1},
                         andere_vorher)
        html = self.client.get(f"/angebote/{a.id}").text
        self.assertIn("+ Überschrift", html)
        # Ungültiger Block: keine Änderung, kein Fehler
        self.post(f"/angebote/{a.id}/gruppe", block_nr="x", alt="", neu="Egal")
        self.s.expire_all()
        self.assertEqual({p.gruppe for p in a.positionen if p.block_nr == 1}, {""})


# --- Phase 103: Anker auf die neue Position ------------------------------------

class PositionNeu(Basis):
    def test_redirect_mit_anker(self):
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id)
        self.s.commit()
        ziel = self.post(f"/angebote/{a.id}/position-neu", bezeichnung="Freitext v22",
                         beschreibung="Testzeile", menge="1", e_preis="10,00")
        self.s.expire_all()
        neu = a.positionen[-1]
        self.assertEqual(neu.bezeichnung, "Freitext v22")
        self.assertEqual(ziel, f"/angebote/{a.id}#pos{neu.id}")
        artikel = self.s.query(Artikel).filter(Artikel.aktiv.is_(True)).first()
        ziel = self.post(f"/angebote/{a.id}/position-neu", artikel_id=str(artikel.id))
        self.s.expire_all()
        self.assertEqual(a.positionen[-1].pos_nr, artikel.pos_nr)
        self.assertTrue(ziel.endswith(f"#pos{a.positionen[-1].id}"), ziel)
        # Formular-ID im Editor vorhanden
        html = self.client.get(f"/angebote/{a.id}").text
        self.assertIn(f'id="pos{neu.id}"', html)


# --- Phase 103: Einheit „psl.“ der Auslegungszeile ----------------------------

class AuslegungEinheit(Basis):
    def test_neue_angebote_psl(self):
        a = self.wp_angebot()
        zeilen = [p for p in a.positionen if p.bezeichnung == AUSLEGUNG]
        self.assertEqual(len(zeilen), 1)
        self.assertEqual(zeilen[0].einheit, "psl.")

    def test_migrationsquery(self):
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id)
        a.positionen.append(AngebotsPosition(
            sort=1, block_nr=1, gruppe="", bezeichnung=AUSLEGUNG,
            beschreibung="Altbestand", menge=1, einheit="pauschal", e_preis_cent=0))
        a.positionen.append(AngebotsPosition(
            sort=2, block_nr=1, gruppe="", bezeichnung="Andere Zeile",
            beschreibung="bleibt", menge=1, einheit="pauschal", e_preis_cent=100))
        self.s.commit()
        # derselbe Query wie in migrate.py (_daten, v22-Block), hier auf das
        # Testangebot eingeschränkt, damit der Bestand der Entwicklungs-DB
        # nicht vom Test angefasst wird
        n = (self.s.query(AngebotsPosition)
             .filter(AngebotsPosition.angebot_id == a.id,
                     AngebotsPosition.bezeichnung == AUSLEGUNG,
                     AngebotsPosition.einheit == "pauschal")
             .update({"einheit": "psl."}, synchronize_session=False))
        self.s.commit()
        self.assertEqual(n, 1)
        self.s.expire_all()
        self.assertEqual([(p.bezeichnung, p.einheit) for p in a.positionen],
                         [(AUSLEGUNG, "psl."), ("Andere Zeile", "pauschal")])
        # Quelle von migrate.py enthält den Block
        quelle = (PROJEKT / "migrate.py").read_text(encoding="utf-8")
        self.assertIn('_AP.einheit == "pauschal"', quelle)
        self.assertIn('{"einheit": "psl."}', quelle)


# --- Phase 103: Scroll-Merker zentral in projektierung.js ---------------------

class ScrollMerker(unittest.TestCase):
    def test_regex_und_editor(self):
        js = (PROJEKT / "app" / "static" / "projektierung.js").read_text(encoding="utf-8")
        m = re.search(r"const bereich = (.+);", js)
        self.assertIsNotNone(m)
        self.assertIn("angebote", m.group(1))
        self.assertIn(r"\d+", m.group(1))            # nur /angebote/<id>, nicht die Liste
        html = (PROJEKT / "app" / "templates" / "angebote" / "editor.html").read_text(encoding="utf-8")
        self.assertNotIn("editor-scroll-", html)
        css = (PROJEKT / "app" / "static" / "style.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.zeilenform \{[^}]*scroll-margin-top")


if __name__ == "__main__":
    unittest.main()
