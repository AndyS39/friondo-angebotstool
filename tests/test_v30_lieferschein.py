# v30 (PLAN_V18 Phase 149): Lieferschein mit vollständigen Langtexten (keine
# Kürzung, 7,5 pt, Seitenumbruch in langen Texten, Tabellenkopf je Seite) und
# EP-Folgepositionen (Parameter lieferschein_folgepositionen, Standard
# „014: 015, 016, 017“; Editor-Hinweis „folgt auf dem Lieferschein Pos. 014“).
# Kontrollangebot aus tests/test_regression.KONTROLL_SZENARIO (Netto 30.245,43 €).
# Räumt Kunden mit v30b-lieferschein@test.local auf; der Parameter wird am Ende
# auf den Wert von vorher zurückgesetzt.
import io
import unittest
import warnings

warnings.filterwarnings("ignore")

import pypdf
from fastapi.testclient import TestClient

from app import angebot_aufbau, lieferschein_pdf
from app.db import SessionLocal, init_db
from app.logik import logik_einlesen
from app.main import app
from app.models import (Angebot, AngebotsPosition, Einstellung, Erfassung, Kunde,
                        Vorgang, angebot_status_setzen, einstellung_setzen)
from tests.test_regression import KONTROLL_SZENARIO

TEST_EMAIL = "v30b-lieferschein@test.local"
PARAMETER = lieferschein_pdf.FOLGEPOSITIONEN_PARAMETER
ZUSATZ = {"016": "Friondo iMSys V30B", "017": "Friondo SpotDynamic V30B"}


def parameter_lesen():
    s = SessionLocal()
    try:
        zeile = s.query(Einstellung).filter(Einstellung.name == PARAMETER).first()
        return None if zeile is None else zeile.wert
    finally:
        s.close()


def parameter_setzen(wert):
    s = SessionLocal()
    try:
        if wert is None:
            s.query(Einstellung).filter(Einstellung.name == PARAMETER).delete()
        else:
            einstellung_setzen(s, PARAMETER, wert)
        s.commit()
    finally:
        s.close()


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


def pdf_text(inhalt: bytes) -> str:
    return "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(inhalt)).pages)


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.logik, bericht = logik_einlesen()
        assert not bericht.fehler, bericht.fehler
        cls.kunde = Kunde(anrede="Frau", vorname="Lisa", nachname="V30B Lieferschein",
                          strasse="Teststr. 1", plz="47139", ort="Duisburg", email=TEST_EMAIL)
        cls.s.add(cls.kunde)
        cls.s.commit()
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        cls.parameter_vorher = parameter_lesen()
        parameter_setzen(lieferschein_pdf.FOLGEPOSITIONEN_STANDARD)

    @classmethod
    def tearDownClass(cls):
        parameter_setzen(cls.parameter_vorher)
        aufraeumen(cls.s)
        cls.s.close()

    def kontrollangebot(self) -> Angebot:
        """Kontrollangebot (014 + 015 normal) + 016/017 als normale Positionen,
        Status Angenommen (Lieferschein nur dort)."""
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id,
                                           antworten=dict(KONTROLL_SZENARIO), logik=self.logik)
        self.assertEqual(a.summen()["netto"], 3024543)
        nummern = {p.pos_nr for p in a.positionen}
        self.assertIn("014", nummern)
        self.assertIn("015", nummern)
        sort = max(p.sort for p in a.positionen)
        for nr, text in ZUSATZ.items():
            if nr not in nummern:
                sort += 1
                a.positionen.append(AngebotsPosition(
                    sort=sort, pos_nr=nr, bezeichnung=text, beschreibung=f"{text}\nZeile 2",
                    menge=1, einheit="psl.", e_preis_cent=100, block_nr=10))
        for p in a.positionen:
            if p.pos_nr in ("014", "015", "016", "017"):
                p.ep_flag = p.alternativ = p.bauseits = False
        angebot_status_setzen(a, "Angenommen")
        self.s.commit()
        return a

    def position(self, angebot, nr):
        return next(p for p in angebot.positionen if p.pos_nr == nr)

    def nummern(self, angebot, regeln=None):
        regeln = lieferschein_pdf.folgepositionen_lesen(self.s) if regeln is None else regeln
        return [p.pos_nr for _n, p in lieferschein_pdf.lieferschein_positionen(angebot, regeln)]

    def lieferschein(self, angebot) -> str:
        r = self.client.get(f"/angebote/{angebot.id}/lieferschein.pdf")
        self.assertEqual(r.status_code, 200)
        return pdf_text(r.content)


class Folgepositionen(Basis):
    def test_parameter_parsen(self):
        self.assertEqual(lieferschein_pdf.folgepositionen_parsen(
            lieferschein_pdf.FOLGEPOSITIONEN_STANDARD), {"014": ["015", "016", "017"]})
        self.assertEqual(lieferschein_pdf.folgepositionen_parsen(
            "014: 015, 016, 017\n020: 021 022; 030:031,030\nquatsch\n: 040"),
            {"014": ["015", "016", "017"], "020": ["021", "022"], "030": ["031"]})
        self.assertEqual(lieferschein_pdf.folgepositionen_parsen(""), {})
        self.assertEqual(lieferschein_pdf.folgepositionen_text(self.s),
                         lieferschein_pdf.FOLGEPOSITIONEN_STANDARD)

    def test_014_normal_alle_vier(self):
        a = self.kontrollangebot()
        nummern = self.nummern(a)
        for nr in ("014", "015", "016", "017"):
            self.assertIn(nr, nummern)
        text = self.lieferschein(a)
        self.assertIn("Friondo iMSys V30B", text)
        self.assertIn("Friondo SpotDynamic V30B", text)
        self.assertIn("L I E F E R S C H E I N", text)
        self.assertIn("Ware vollständig erhalten", text)
        # keine Preise/Summen – die vollständigen Artikeltexte dürfen „€“ enthalten
        # (z. B. „Paket Basic 39,90 €/a“ im Text von Pos. 014), die Preisspalten nicht
        for verboten in ("E-Preis", "G-Preis", "Netto-Summe", "Gesamt-Betrag", "30.245,43",
                         "35.992,06", "Rabatt", "USt."):
            self.assertNotIn(verboten, text, verboten)
        self.assertIn("Paket Basic 39,90 €/a", text)   # Langtext von 014 vollständig
        self.assertEqual(lieferschein_pdf.folge_hinweise(a, {"014": ["015", "016", "017"]}),
                         {self.position(a, nr).id: "014" for nr in ("015", "016", "017")})

    def test_014_ep_ohne_folgepositionen(self):
        a = self.kontrollangebot()
        self.position(a, "014").ep_flag = True
        self.s.commit()
        nummern = self.nummern(a)
        for nr in ("014", "015", "016", "017"):
            self.assertNotIn(nr, nummern)
        self.assertGreater(len(nummern), 10)   # übrige Positionen bleiben
        text = self.lieferschein(a)
        self.assertNotIn("Friondo iMSys V30B", text)
        self.assertNotIn("Friondo SpotDynamic V30B", text)
        self.assertEqual(lieferschein_pdf.entfallende_folgepositionen(
            a, {"014": ["015", "016", "017"]}), {"015": "014", "016": "014", "017": "014"})
        # Alternativ bzw. bauseits wirken genauso
        self.position(a, "014").ep_flag = False
        self.position(a, "014").alternativ = True
        self.s.commit()
        self.assertFalse({"014", "015", "016", "017"} & set(self.nummern(a)))
        self.position(a, "014").alternativ = False
        self.position(a, "014").bauseits = True
        self.s.commit()
        self.assertFalse({"014", "015", "016", "017"} & set(self.nummern(a)))

    def test_014_fehlt_015_bleibt(self):
        a = self.kontrollangebot()
        self.s.delete(self.position(a, "014"))
        self.s.commit()
        self.s.refresh(a)
        nummern = self.nummern(a)
        self.assertNotIn("014", nummern)
        for nr in ("015", "016", "017"):
            self.assertIn(nr, nummern)
        self.assertEqual(lieferschein_pdf.folge_hinweise(a, {"014": ["015", "016", "017"]}), {})

    def test_parameter_leer_keine_abhaengigkeit(self):
        a = self.kontrollangebot()
        self.position(a, "014").ep_flag = True
        self.s.commit()
        try:
            parameter_setzen("")
            self.assertEqual(lieferschein_pdf.folgepositionen_text(self.s), "")
            self.assertEqual(lieferschein_pdf.folgepositionen_lesen(self.s), {})
            nummern = self.nummern(a)
            self.assertNotIn("014", nummern)
            for nr in ("015", "016", "017"):
                self.assertIn(nr, nummern)
            self.assertIn("Friondo iMSys V30B", self.lieferschein(a))
            # ohne übergebene Regeln liest die Funktion den Parameter selbst
            self.assertIn("015", [p.pos_nr for _n, p in lieferschein_pdf.lieferschein_positionen(a)])
        finally:
            parameter_setzen(lieferschein_pdf.FOLGEPOSITIONEN_STANDARD)

    def test_editor_hinweis_nur_anzeige(self):
        a = self.kontrollangebot()
        a.status = "Entwurf"
        self.s.commit()
        seite = self.client.get(f"/angebote/{a.id}")
        self.assertEqual(seite.status_code, 200)
        self.assertEqual(seite.text.count("folgt auf dem Lieferschein Pos. 014"), 3)
        # keine automatische EP-Änderung
        self.s.expire_all()
        self.assertFalse(any(self.position(a, nr).ep_flag for nr in ("015", "016", "017")))
        # ohne Hauptposition kein Hinweis
        self.s.delete(self.position(a, "014"))
        self.s.commit()
        self.assertNotIn("folgt auf dem Lieferschein", self.client.get(f"/angebote/{a.id}").text)

    def test_parametrierung_angebotstool(self):
        seite = self.client.get("/parametrierung/angebotstool")
        self.assertEqual(seite.status_code, 200)
        self.assertIn('name="lieferschein_folgepositionen"', seite.text)
        self.assertIn("Lieferschein: abhängige Positionen", seite.text)
        self.assertIn("014: 015, 016, 017", seite.text)
        try:
            r = self.client.post("/parametrierung/einstellungen",
                                 data={"lieferschein_formular": "1",
                                       "lieferschein_folgepositionen": "014: 015,016 ; 020: 021"},
                                 headers={"referer": "http://testserver/parametrierung/angebotstool"},
                                 follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertEqual(parameter_lesen(), "014: 015, 016\n020: 021")
            self.assertEqual(lieferschein_pdf.folgepositionen_lesen(self.s),
                             {"014": ["015", "016"], "020": ["021"]})
            r = self.client.post("/parametrierung/einstellungen",
                                 data={"lieferschein_formular": "1",
                                       "lieferschein_folgepositionen": ""},
                                 follow_redirects=False)
            self.assertEqual(parameter_lesen(), "")
        finally:
            parameter_setzen(lieferschein_pdf.FOLGEPOSITIONEN_STANDARD)


class Langtexte(Basis):
    def test_zwoelf_zeilen_vollstaendig(self):
        a = self.kontrollangebot()
        zeilen = [f"Zeile {i:02d} V30B Beschreibung vollständig" for i in range(1, 13)]
        a.positionen.append(AngebotsPosition(
            sort=max(p.sort for p in a.positionen) + 1, pos_nr="Z99", bezeichnung="Langtext V30B",
            beschreibung="\n".join(zeilen), menge=2, einheit="Stk", e_preis_cent=100))
        self.s.commit()
        text = self.lieferschein(a)
        for zeile in zeilen:
            self.assertIn(zeile, text)
        self.assertNotIn("…", text)
        self.assertIn("Langtext V30B", text)
        self.assertIn("2,00", text)
        # Konstanten der Kürzung sind weg, _kurztext kürzt nicht mehr
        self.assertFalse(hasattr(lieferschein_pdf, "MAX_BESCHREIBUNG_ZEILEN"))
        self.assertFalse(hasattr(lieferschein_pdf, "MAX_BESCHREIBUNG_ZEICHEN"))
        titel, rest = lieferschein_pdf._kurztext(a.positionen[-1])
        self.assertEqual(titel, "Langtext V30B")
        self.assertEqual(rest.splitlines(), zeilen)

    def test_positionstext(self):
        p = AngebotsPosition(bezeichnung="Titel", beschreibung="Titel\n\nA\nB\n")
        self.assertEqual(lieferschein_pdf._positionstext(p), ("Titel", "A\nB"))
        p = AngebotsPosition(bezeichnung="", beschreibung="(Optionale Position)\nErste\nZweite")
        self.assertEqual(lieferschein_pdf._positionstext(p), ("Erste", "Zweite"))
        p = AngebotsPosition(bezeichnung="", beschreibung="Nur eine Zeile")
        self.assertEqual(lieferschein_pdf._positionstext(p), ("Nur eine Zeile", ""))
        self.assertIs(lieferschein_pdf._kurztext, lieferschein_pdf._positionstext)

    def test_lange_texte_ueber_seitenumbruch(self):
        a = self.kontrollangebot()
        sort = max(p.sort for p in a.positionen)
        for n in range(1, 9):
            sort += 1
            a.positionen.append(AngebotsPosition(
                sort=sort, pos_nr=f"L{n:02d}", bezeichnung=f"Langposition {n} V30B",
                beschreibung="\n".join(f"Position {n} Zeile {z:02d} – Beschreibungstext, der "
                                       "vollständig auf dem Lieferschein erscheint"
                                       for z in range(1, 41)),
                menge=1, einheit="Stk", e_preis_cent=100))
        self.s.commit()
        r = self.client.get(f"/angebote/{a.id}/lieferschein.pdf")
        self.assertEqual(r.status_code, 200)
        leser = pypdf.PdfReader(io.BytesIO(r.content))
        self.assertGreater(len(leser.pages), 2)
        seiten = [p.extract_text() for p in leser.pages]
        for seite in seiten:
            self.assertIn("L I E F E R S C H E I N", seite)
        # Tabellenkopf auf jeder Seite mit Positionen (letzte Seite ggf. nur Unterschrift)
        for seite in seiten[:-1]:
            self.assertIn("Bezeichnung", seite)
        text = "\n".join(seiten)
        for n in range(1, 9):
            self.assertIn(f"Langposition {n} V30B", text)
            self.assertIn(f"Position {n} Zeile 40", text)
        self.assertIn("Ware vollständig erhalten", seiten[-1])
        for verboten in ("E-Preis", "G-Preis", "Netto-Summe", "Gesamt-Betrag", "30.245,43"):
            self.assertNotIn(verboten, text, verboten)


if __name__ == "__main__":
    unittest.main()
