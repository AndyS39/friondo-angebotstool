# v30 (PLAN_V18 Phase 150): Zahlungsbedingungen je Angebot – Modul
# app/zahlungsbedingungen.py (Einträge, Standard, Freitext, Migration mit
# Platzhalter {zahlungsbedingungen} in den Nachtexten), Auswahl im Editor
# (POST /angebote/<id>/zahlungsbedingung), PDF-Nachtext, E-Mail-Platzhalter
# {zahlungsbedingung}, Parametrierungs-Seite. Kontrollangebot aus
# tests/test_regression.KONTROLL_SZENARIO (Netto 30.245,43 € bleibt unverändert).
# Räumt Kunden mit v30b-zahlung@test.local, Test-Textblöcke und Test-Einträge auf.
import io
import unittest
import warnings

warnings.filterwarnings("ignore")

import pypdf
from fastapi.testclient import TestClient

from app import angebot_aufbau, angebotsprofile, kfw, mail_vorlagen, pdf_export
from app import konfigurator as engine
from app import zahlungsbedingungen as zb
from app.db import SessionLocal, init_db
from app.logik import logik_einlesen
from app.main import app
from app.models import (Angebot, Einstellung, Erfassung, Kunde, Textblock, Vorgang,
                        Zahlungsbedingung, einstellung_holen, einstellung_setzen)
from tests.test_regression import KONTROLL_SZENARIO

TEST_EMAIL = "v30b-zahlung@test.local"
TEST_BLOCK = "V30B Testblock"
TEST_NAME = "V30B Testeintrag"


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.delete(v)
        s.delete(k)
    s.query(Textblock).filter(Textblock.name.like(f"{TEST_BLOCK}%")).delete(synchronize_session=False)
    s.query(Zahlungsbedingung).filter(Zahlungsbedingung.name.like(f"{TEST_NAME}%")).delete(
        synchronize_session=False)
    s.commit()


def pdf_flach(pfad) -> str:
    text = "\n".join(p.extract_text() for p in pypdf.PdfReader(str(pfad)).pages)
    return " ".join(text.split())


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.logik, bericht = logik_einlesen()
        assert not bericht.fehler, bericht.fehler
        cls.kunde = Kunde(anrede="Frau", vorname="Zita", nachname="V30B Zahlung",
                          strasse="Teststr. 1", plz="47139", ort="Duisburg", email=TEST_EMAIL)
        cls.s.add(cls.kunde)
        cls.s.commit()
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        # Voraussetzung: migrate.py (migration_v30_zahlung) ist auf der Test-DB gelaufen
        assert cls.s.query(Zahlungsbedingung).count() >= 3, "migrate.py zuerst ausführen"

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def kontrollangebot(self) -> Angebot:
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id,
                                           antworten=dict(KONTROLL_SZENARIO), logik=self.logik)
        self.s.commit()
        self.assertEqual(a.summen()["netto"], 3024543)
        return a

    def pdf(self, angebot) -> str:
        self.s.expire_all()
        return pdf_flach(pdf_export.pdf_fuer_angebot(self.s, self.s.get(Angebot, angebot.id)))


class Modul(Basis):
    def test_standard_eintraege_und_tabelle(self):
        self.assertEqual([e[0] for e in zb.STANDARD_EINTRAEGE],
                         ["standard", "montagetag_50", "anzahlung_80_skonto"])
        self.assertTrue(zb.STANDARD_ABSATZ.startswith("Eine Anzahlung von 50% des Angebotsbetrags "
                                                      "ist spätestens 14 Tage vor Arbeitsbeginn"))
        self.assertIn("am Tag der Montage", zb.STANDARD_EINTRAEGE[1][2])
        self.assertIn("gewähren wir 2% Skonto auf den Anzahlungsbetrag", zb.STANDARD_EINTRAEGE[2][2])
        eintraege = {z.schluessel: z for z in zb.alle(self.s)}
        for schluessel, name, text in zb.STANDARD_EINTRAEGE:
            self.assertIn(schluessel, eintraege)
            self.assertEqual(eintraege[schluessel].name, name)
            self.assertEqual(eintraege[schluessel].text, text)
        self.assertEqual(sum(1 for z in zb.alle(self.s) if z.standard), 1)   # genau ein Standard
        self.assertEqual(zb.standard(self.s).schluessel, "standard")
        self.assertTrue(all(z.aktiv for z in eintraege.values()))
        # zweiter Lauf der Migration: stumm
        self.assertEqual(zb.migration_v30_zahlung(self.s), [])
        self.s.commit()
        for name, _wert in zb.PARAMETER_STANDARD:
            self.assertIsNotNone(self.s.query(Einstellung).filter(Einstellung.name == name).first())

    def test_seed_konstanten_und_db_bloecke_tragen_platzhalter(self):
        for art, name, text in (angebotsprofile.SEED_BLOECKE + angebotsprofile.PV_SEED_BLOECKE
                                + angebotsprofile.KL_SEED_BLOECKE):
            if art != "nachtext":
                continue
            self.assertIn("### Zahlung\n{zahlungsbedingungen}", text, name)
            self.assertNotIn("Anzahlung von 50%", text, name)
        self.assertIn(zb.PLATZHALTER, angebotsprofile.STANDARD_NACHTEXT)
        self.assertEqual(angebotsprofile.PLATZHALTER_ZAHLUNG, zb.PLATZHALTER)
        # alle Standard-Nachtexte der Datenbank (WP/PV/KL je Profil) sind umgestellt
        bloecke = (self.s.query(Textblock).filter(Textblock.art == "nachtext",
                                                  Textblock.name.like("Friondo %")).all())
        self.assertGreaterEqual(len(bloecke), 12)
        for b in bloecke:
            self.assertIn(zb.PLATZHALTER, b.text, b.name)
            self.assertNotIn("Anzahlung von 50%", b.text, b.name)
        self.assertFalse([n for n in zb.bloecke_ohne_platzhalter(self.s) if n.startswith("Friondo ")])

    def test_migration_ersetzt_und_meldet(self):
        marker_vorher = einstellung_holen(self.s, zb.MARKER_NACHTEXTE, "")
        mit_abstand = ("# Installationsvoraussetzungen\n### Zahlung\nEine Anzahlung von 50% des "
                       "Angebotsbetrags ist spätestens 14 Tage vor\nArbeitsbeginn zu zahlen.  Die "
                       "Restzahlung wird mit der Schlussrechnungsstellung fällig.\nDie Rechnung "
                       "erhalten Sie im Anschluss zur Installation.\n\n### Weiter\nText")
        a = Textblock(art="nachtext", name=f"{TEST_BLOCK} A", text=mit_abstand)
        b = Textblock(art="nachtext", name=f"{TEST_BLOCK} B", text="### Zahlung\nEigener Text.")
        c = Textblock(art="nachtext", name=f"{TEST_BLOCK} C", text="### Zahlung\n{zahlungsbedingungen}")
        d = Textblock(art="vortext", name=f"{TEST_BLOCK} D", text=zb.STANDARD_ABSATZ)
        self.s.add_all([a, b, c, d])
        self.s.commit()
        try:
            einstellung_setzen(self.s, zb.MARKER_NACHTEXTE, "")   # Erstlauf simulieren
            self.s.commit()
            meldungen = zb.migration_v30_zahlung(self.s)
            self.s.commit()
            self.assertEqual(self.s.get(Textblock, a.id).text,
                             "# Installationsvoraussetzungen\n### Zahlung\n{zahlungsbedingungen}"
                             "\n\n### Weiter\nText")
            self.assertEqual(self.s.get(Textblock, b.id).text, "### Zahlung\nEigener Text.")
            self.assertEqual(self.s.get(Textblock, c.id).text, "### Zahlung\n{zahlungsbedingungen}")
            self.assertEqual(self.s.get(Textblock, d.id).text, zb.STANDARD_ABSATZ)   # Vortext unberührt
            self.assertTrue(any(f"„{TEST_BLOCK} A“" in m and "eingesetzt" in m for m in meldungen), meldungen)
            offen = [m for m in meldungen if "NICHT wörtlich gefunden" in m]
            self.assertEqual(len(offen), 1, meldungen)
            self.assertIn(f"„{TEST_BLOCK} B“", offen[0])
            self.assertNotIn(f"„{TEST_BLOCK} C“", offen[0])
            self.assertIn(f"{TEST_BLOCK} B", zb.bloecke_ohne_platzhalter(self.s))
            # zweiter Lauf: stumm (Marker gesetzt, nichts mehr zu ersetzen)
            self.assertEqual(zb.migration_v30_zahlung(self.s), [])
            self.assertEqual(einstellung_holen(self.s, zb.MARKER_NACHTEXTE, ""), "erledigt")
        finally:
            einstellung_setzen(self.s, zb.MARKER_NACHTEXTE, marker_vorher or "erledigt")
            for block in (a, b, c, d):
                self.s.delete(block)
            self.s.commit()

    def test_fuer_angebot_und_rendering(self):
        a = Angebot(nummer="V30B-TEST", kunde_id=0)
        self.assertEqual(zb.fuer_angebot(self.s, a), ("Standard", zb.STANDARD_ABSATZ))
        a.zahlungsbedingung_key = "anzahlung_80_skonto"
        name, text = zb.fuer_angebot(self.s, a)
        self.assertEqual(name, "80 % Anzahlung, 2 % Skonto")
        self.assertIn("80% des Angebotsbetrags", text)
        a.zahlungsbedingung_key, a.zahlungsbedingung_text = "freitext", "Zahlung nach Vereinbarung."
        self.assertEqual(zb.fuer_angebot(self.s, a), (zb.FREITEXT_NAME, "Zahlung nach Vereinbarung."))
        a.zahlungsbedingung_text = "   "
        self.assertEqual(zb.fuer_angebot(self.s, a)[0], "Standard")   # leerer Freitext → Standard
        a.zahlungsbedingung_key, a.zahlungsbedingung_text = "gibtsnicht", ""
        self.assertEqual(zb.fuer_angebot(self.s, a)[0], "Standard")
        self.assertEqual(zb.text_einsetzen("### Zahlung\n{zahlungsbedingungen}\nX", "A\nB"),
                         "### Zahlung\nA\nB\nX")
        self.assertEqual(zb.platzhalter_einsetzen("### Zahlung\n" + zb.STANDARD_ABSATZ.replace(" ", "\n")),
                         ("### Zahlung\n{zahlungsbedingungen}", True))
        self.assertEqual(zb.platzhalter_einsetzen("kein Absatz"), ("kein Absatz", False))
        ziel = Angebot(nummer="V30B-ZIEL", kunde_id=0)
        zb.uebernehmen(ziel, a)
        self.assertEqual((ziel.zahlungsbedingung_key, ziel.zahlungsbedingung_text), ("gibtsnicht", ""))

    def test_pflege_funktionen(self):
        standard_vorher = zb.standard(self.s)
        neu = zb.anlegen(self.s, f"{TEST_NAME} 100 % vorab", "Vorkasse 100%.")
        self.s.commit()
        try:
            self.assertEqual(neu.schluessel, "v30b_testeintrag_100_prozent_vorab")
            self.assertTrue(neu.aktiv)
            self.assertFalse(neu.standard)
            zweiter = zb.anlegen(self.s, f"{TEST_NAME} 100 % vorab", "Nochmal.")
            self.assertEqual(zweiter.schluessel, "v30b_testeintrag_100_prozent_vorab_2")
            self.assertIn(neu, zb.aktive(self.s))
            zb.aktiv_setzen(self.s, neu, False)
            self.assertNotIn(neu, zb.aktive(self.s))
            with self.assertRaises(ValueError):
                zb.aktiv_setzen(self.s, standard_vorher, False)
            with self.assertRaises(ValueError):
                zb.anlegen(self.s, "   ", "x")
            zb.standard_setzen(self.s, zweiter)
            self.assertEqual(sum(1 for z in zb.alle(self.s) if z.standard), 1)
            self.assertEqual(zb.standard(self.s).id, zweiter.id)
            zb.standard_setzen(self.s, standard_vorher)
            self.assertEqual(zb.standard(self.s).id, standard_vorher.id)
            zb.speichern(self.s, neu, f"{TEST_NAME} neu", "Neuer Text")
            self.assertEqual((neu.name, neu.text), (f"{TEST_NAME} neu", "Neuer Text"))
        finally:
            zb.standard_setzen(self.s, standard_vorher)
            self.s.commit()
            aufraeumen(self.s)


class PdfUndEditor(Basis):
    def test_kontrollangebot_standard_im_pdf(self):
        a = self.kontrollangebot()
        text = self.pdf(a)
        self.assertIn("50% des Angebotsbetrags ist spätestens 14 Tage", text)
        self.assertIn("Zahlung Eine Anzahlung von 50%", text)   # Überschrift bleibt
        self.assertNotIn("{zahlungsbedingungen}", text)
        self.assertNotIn("80% des Angebotsbetrags", text)
        # Editor zeigt Name und Dropdown (Standard vorgewählt)
        seite = self.client.get(f"/angebote/{a.id}").text
        self.assertIn("Zahlungsbedingung: <strong>Standard</strong>", seite)
        self.assertIn('name="key"', seite)
        self.assertIn('<option value="standard" selected>Standard (Standard)</option>', seite)
        self.assertIn('value="freitext"', seite)

    def test_auswahl_3_und_summen_unveraendert(self):
        a = self.kontrollangebot()
        endbetrag_vorher = a.summen()["endbetrag"]
        r = self.client.post(f"/angebote/{a.id}/zahlungsbedingung",
                             data={"key": "anzahlung_80_skonto", "text": ""}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Zahlungsbedingung%3A+80+%25+Anzahlung", r.headers["location"])
        self.s.expire_all()
        a = self.s.get(Angebot, a.id)
        self.assertEqual(a.zahlungsbedingung_key, "anzahlung_80_skonto")
        text = self.pdf(a)
        self.assertIn("80% des Angebotsbetrags", text)
        self.assertIn("2% Skonto", text)
        self.assertNotIn("50% des Angebotsbetrags", text)
        self.assertIn("Netto-Summe 30.245,43", text.replace("€", "").replace("  ", " "))
        self.assertEqual(a.summen()["netto"], 3024543)
        self.assertEqual(a.summen()["endbetrag"], endbetrag_vorher)
        parameter, _ = kfw.parameter_lesen(self.logik)
        eingaben = kfw.eingaben_aus_antworten(engine.kfw_daten(KONTROLL_SZENARIO), a.summen()["endbetrag"])
        self.assertEqual(kfw.ergebnis_fuer_angebot(parameter, eingaben, a).zuschuss_cent, 1960000)
        seite = self.client.get(f"/angebote/{a.id}").text
        self.assertIn("Zahlungsbedingung: <strong>80 % Anzahlung, 2 % Skonto</strong>", seite)
        self.assertIn('<option value="anzahlung_80_skonto" selected>', seite)
        # Standard-Eintrag → leer gespeichert (leer = Standard)
        self.client.post(f"/angebote/{a.id}/zahlungsbedingung", data={"key": "standard"})
        self.s.expire_all()
        self.assertEqual(self.s.get(Angebot, a.id).zahlungsbedingung_key, "")
        # unbekannter Schlüssel → Meldung, nichts geändert
        r = self.client.post(f"/angebote/{a.id}/zahlungsbedingung", data={"key": "gibtsnicht"},
                             follow_redirects=False)
        self.assertIn("unbekannter", r.headers["location"])
        self.s.expire_all()
        self.assertEqual(self.s.get(Angebot, a.id).zahlungsbedingung_key, "")

    def test_freitext_woertlich(self):
        a = self.kontrollangebot()
        r = self.client.post(f"/angebote/{a.id}/zahlungsbedingung",
                             data={"key": "freitext", "text": ""}, follow_redirects=False)
        self.assertIn("abweichenden+Text", r.headers["location"])
        r = self.client.post(f"/angebote/{a.id}/zahlungsbedingung",
                             data={"key": "freitext", "text": "Zahlung nach Vereinbarung."},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        a = self.s.get(Angebot, a.id)
        self.assertEqual((a.zahlungsbedingung_key, a.zahlungsbedingung_text),
                         ("freitext", "Zahlung nach Vereinbarung."))
        text = self.pdf(a)
        self.assertIn("Zahlung Zahlung nach Vereinbarung.", text)
        self.assertNotIn("50% des Angebotsbetrags", text)
        seite = self.client.get(f"/angebote/{a.id}").text
        self.assertIn("Zahlungsbedingung: <strong>Abweichend (Freitext)</strong>", seite)
        self.assertIn("Zahlung nach Vereinbarung.", seite)
        self.assertNotIn('<span id="zb-freitext" hidden>', seite)

    def test_nur_im_entwurf(self):
        a = self.kontrollangebot()
        from app.models import angebot_status_setzen
        angebot_status_setzen(a, "Versendet")
        self.s.commit()
        r = self.client.post(f"/angebote/{a.id}/zahlungsbedingung",
                             data={"key": "anzahlung_80_skonto"}, follow_redirects=False)
        self.assertIn("nur+im+Entwurf", r.headers["location"])
        self.s.expire_all()
        self.assertEqual(self.s.get(Angebot, a.id).zahlungsbedingung_key, "")
        seite = self.client.get(f"/angebote/{a.id}").text
        self.assertIn("Zahlungsbedingung: <strong>Standard</strong>", seite)
        self.assertNotIn('name="key"', seite)
        self.assertIn("nur im Entwurf änderbar", seite)

    def test_mail_platzhalter(self):
        a = self.kontrollangebot()
        a.zahlungsbedingung_key = "anzahlung_80_skonto"
        self.s.commit()
        werte = mail_vorlagen.werte_fuer_angebot(self.s, a, self.kunde)
        self.assertEqual(werte["zahlungsbedingung"], "80 % Anzahlung, 2 % Skonto")
        self.assertIn("{zahlungsbedingung}", [p for p, _ in mail_vorlagen.PLATZHALTER])
        self.assertEqual(mail_vorlagen.unbekannte_platzhalter("x {zahlungsbedingung} y"), [])
        self.assertEqual(mail_vorlagen.einsetzen("Zahlung: {zahlungsbedingung}", werte),
                         "Zahlung: 80 % Anzahlung, 2 % Skonto")
        self.assertIn("{zahlungsbedingung}", self.client.get("/parametrierung/vorlagen").text)

    def test_parametrierung_seite(self):
        seite = self.client.get("/parametrierung/zahlungsbedingungen")
        self.assertEqual(seite.status_code, 200)
        for erwartet in ("80 % Anzahlung, 2 % Skonto", "50 % am Montagetag", "{zahlungsbedingungen}",
                         'name="aktion" value="neu"', "Als Standard"):
            self.assertIn(erwartet, seite.text)
        standard_vorher = zb.standard(self.s)
        try:
            r = self.client.post("/parametrierung/zahlungsbedingungen",
                                 data={"aktion": "neu", "name": f"{TEST_NAME} Seite", "text": "Text A"},
                                 follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("angelegt", r.headers["location"])
            self.s.expire_all()
            neu = self.s.query(Zahlungsbedingung).filter_by(name=f"{TEST_NAME} Seite").one()
            self.assertIn(f"?id={neu.id}", r.headers["location"])
            self.assertIn("Text A", self.client.get(f"/parametrierung/zahlungsbedingungen?id={neu.id}").text)
            self.client.post("/parametrierung/zahlungsbedingungen",
                             data={"aktion": "speichern", "id": str(neu.id),
                                   "name": f"{TEST_NAME} Seite 2", "text": "Text B"})
            self.s.expire_all()
            self.assertEqual((neu.name, neu.text), (f"{TEST_NAME} Seite 2", "Text B"))
            self.client.post("/parametrierung/zahlungsbedingungen",
                             data={"aktion": "standard", "id": str(neu.id)})
            self.s.expire_all()
            self.assertTrue(neu.standard)
            self.assertEqual(sum(1 for z in zb.alle(self.s) if z.standard), 1)
            # Standard lässt sich nicht deaktivieren
            r = self.client.post("/parametrierung/zahlungsbedingungen",
                                 data={"aktion": "umschalten", "id": str(neu.id)}, follow_redirects=False)
            self.assertIn("nicht+deaktiviert", r.headers["location"])
            self.s.expire_all()
            self.assertTrue(neu.aktiv)
            self.client.post("/parametrierung/zahlungsbedingungen",
                             data={"aktion": "standard", "id": str(standard_vorher.id)})
            self.client.post("/parametrierung/zahlungsbedingungen",
                             data={"aktion": "umschalten", "id": str(neu.id)})
            self.s.expire_all()
            self.assertFalse(neu.aktiv)
            self.assertTrue(standard_vorher.standard)
            # deaktivierter Eintrag erscheint nicht im Editor-Dropdown
            a = self.kontrollangebot()
            self.assertNotIn(f"{TEST_NAME} Seite 2", self.client.get(f"/angebote/{a.id}").text)
            r = self.client.post(f"/angebote/{a.id}/zahlungsbedingung", data={"key": neu.schluessel},
                                 follow_redirects=False)
            self.assertIn("deaktivierter", r.headers["location"])
        finally:
            zb.standard_setzen(self.s, standard_vorher)
            self.s.commit()
            aufraeumen(self.s)


if __name__ == "__main__":
    unittest.main()
