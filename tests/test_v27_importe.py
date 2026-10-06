# Tests v27 (PLAN_V17 Phase 128, Agent D): Importe in Blöcken (Commit je 200
# Zeilen), Wiederholbarkeit nach Abbruch, laufende Importe im Betriebs-Status
# (betrieb.import_markieren), Hinweis „Dauer etwa <n> s …“ mit Bestätigung in
# den Import-Routen und Dauer-Einstellung nach einem Lauf.
#
# Läuft gegen die Entwicklungs-DB (Login Benutzer 1, Admin, PIN 1234). Testdaten
# tragen das Präfix „V27D“ (Artikel V27D…, Kunden mit E-Mail v27d@test.local,
# Bestandsimporte „V27D …“) und werden am Ende entfernt; geänderte Einstellungen
# import_dauer_* werden auf den vorherigen Stand zurückgesetzt. Die echten
# Importe (PV/Klima) laufen idempotent gegen den vorhandenen Artikelstamm – wie
# in tests/test_pv_v13.py und tests/test_kl_v24_import.py. Kein Netzzugriff.
import io
import re
import threading
import time
import unittest
import warnings
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import bestandsimport, betrieb, import_klima, import_preisliste, import_pv
from app import logik as logik_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, Artikel, Benutzer, Bestandsimport, Einstellung, Gewerk,
                        Kunde, QUELLE_PREISLISTE, einstellung_holen, einstellung_setzen)

PRAEFIX = "V27D"
TEST_EMAIL = "v27d@test.local"
ZEILEN = 450                      # > 400 Zeilen laut Briefing
HINWEIS_REGEX = re.compile(r"Dauer etwa \d+ s – während des Imports können Speichern-Aktionen "
                           r"anderer Nutzer kurz warten; empfohlen außerhalb der Kernzeit")
DAUER_NAMEN = [f"import_dauer_{k}" for k in import_preisliste.IMPORT_DAUER_STANDARD]


def artikel_dicts(anzahl: int) -> list[dict]:
    """Artikel-Dicts wie aus import_preisliste.lese_dateien (GUID-Anker)."""
    return [{
        "guid": f"{PRAEFIX}-{i:04d}", "pos_nr": f"{PRAEFIX}{i:04d}",
        "kategorie": "V27D Testkategorie", "bezeichnung": "",
        "beschreibung": f"V27D Testartikel {i}\nZeile 2", "menge_standard": 1.0,
        "einheit": "Stk", "e_preis_cent": 100 * i, "ep_flag": False,
        "quelle": QUELLE_PREISLISTE, "artikelnummer": "", "multi": None,
        "ek_cent": None, "ek_datum": "",
    } for i in range(1, anzahl + 1)]


def anzahl_v27d_artikel(s) -> int:
    return s.query(Artikel).filter(Artikel.pos_nr.like(f"{PRAEFIX}%")).count()


def artikel_aufraeumen() -> None:
    s = SessionLocal()
    try:
        s.query(Artikel).filter(Artikel.pos_nr.like(f"{PRAEFIX}%")
                                | Artikel.guid.like(f"{PRAEFIX}-%")).delete(
            synchronize_session=False)
        s.commit()
    finally:
        s.close()


def bestand_aufraeumen() -> None:
    """Kunden/Projekte/Angebote des Bestandsimport-Tests und die Import-Protokolle
    „V27D …“ entfernen (Muster tests/test_projektierung_v4.aufraeumen)."""
    from app.models import (Aufgabe, AufgabenpaketInstanz, Erfassung, GalerieDatei, Projekt,
                            ProjektDokument, ProjektMail, ProjektTermin, ProjektVerlauf,
                            SteckbriefWert, UglBestellung, Vorgang)
    s = SessionLocal()
    try:
        for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
            for p in s.query(Projekt).filter_by(kunde_id=k.id):
                for g in s.query(Gewerk).filter_by(projekt_id=p.id):
                    s.query(UglBestellung).filter_by(gewerk_id=g.id).delete()
                    s.query(Aufgabe).filter_by(gewerk_id=g.id).delete()
                    s.query(AufgabenpaketInstanz).filter_by(gewerk_id=g.id).delete()
                    s.query(SteckbriefWert).filter_by(gewerk_id=g.id).delete()
                    s.delete(g)
                s.query(ProjektTermin).filter_by(projekt_id=p.id).delete()
                s.query(ProjektVerlauf).filter_by(projekt_id=p.id).delete()
                s.query(ProjektDokument).filter_by(projekt_id=p.id).delete()
                s.query(ProjektMail).filter_by(projekt_id=p.id).delete()
                s.delete(p)
            for a in s.query(Angebot).filter_by(kunde_id=k.id):
                s.delete(a)
            for e in s.query(Erfassung).filter_by(kunde_id=k.id):
                s.delete(e)
            for v in s.query(Vorgang).filter_by(kunde_id=k.id):
                s.query(GalerieDatei).filter_by(vorgang_id=v.id).delete()
                s.delete(v)
            s.delete(k)
        s.query(Bestandsimport).filter(Bestandsimport.dateiname.like(f"{PRAEFIX}%")).delete(
            synchronize_session=False)
        s.commit()
    finally:
        s.close()


def dauer_sichern() -> dict[str, str | None]:
    s = SessionLocal()
    try:
        return {name: (z.wert if (z := s.query(Einstellung).filter_by(name=name).first())
                       else None) for name in DAUER_NAMEN}
    finally:
        s.close()


def dauer_zuruecksetzen(stand: dict[str, str | None]) -> None:
    s = SessionLocal()
    try:
        for name, wert in stand.items():
            if wert is None:
                s.query(Einstellung).filter_by(name=name).delete()
            else:
                einstellung_setzen(s, name, wert)
        s.commit()
    finally:
        s.close()


def dauer_setzen(name: str, wert: str) -> None:
    s = SessionLocal()
    try:
        einstellung_setzen(s, name, wert)
        s.commit()
    finally:
        s.close()


def dauer_lesen(name: str) -> str:
    s = SessionLocal()
    try:
        return einstellung_holen(s, name, "")
    finally:
        s.close()


def commit_spion(session):
    """Spy auf session.commit (echter Commit läuft weiter)."""
    return mock.patch.object(session, "commit", wraps=session.commit)


def projektleiter_name() -> str:
    s = SessionLocal()
    try:
        return s.get(Benutzer, 1).name
    finally:
        s.close()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.dauer_vorher = dauer_sichern()
        artikel_aufraeumen()
        bestand_aufraeumen()

    @classmethod
    def tearDownClass(cls):
        artikel_aufraeumen()
        bestand_aufraeumen()
        dauer_zuruecksetzen(cls.dauer_vorher)


# --- (a)+(b) Blockbildung und Wiederholbarkeit ----------------------------------

class Blockbildung(Basis):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.echt = import_preisliste.lese_dateien()      # einmal die echten Dateien

    def _gemockt(self):
        """Testartikel ZUERST (Block 1 = 200 Testartikel), dann die echten Zeilen –
        so deaktiviert der Lauf nichts aus dem echten Bestand."""
        return import_preisliste.ImportErgebnis(
            artikel=artikel_dicts(ZEILEN) + list(self.echt.artikel),
            warnungen=list(self.echt.warnungen))

    def test_preisliste_bloecke_abbruch_wiederholbar(self):
        gesamt = ZEILEN + len(self.echt.artikel)
        s = SessionLocal()
        try:
            # inaktive Preislisten-Artikel sind nicht Sache dieses Tests – der Lauf mit
            # den echten Zeilen darf sie nicht vermehren (nichts wird deaktiviert)
            inaktiv_vorher = s.query(Artikel).filter(
                Artikel.quelle == QUELLE_PREISLISTE, Artikel.aktiv.is_(False)).count()
            with mock.patch.object(import_preisliste, "lese_dateien", side_effect=self._gemockt):
                # (a) Commit mindestens zeilen // 200 mal
                with commit_spion(s) as spion:
                    diff, meldung = import_preisliste.import_ausfuehren(s)
                self.assertGreaterEqual(spion.call_count, gesamt // import_preisliste.BLOCK)
                self.assertGreaterEqual(spion.call_count, 2)
                self.assertEqual(anzahl_v27d_artikel(s), ZEILEN)
                self.assertGreaterEqual(len(diff.neu), ZEILEN)
                self.assertIn("neu", meldung)
                # (b) zweiter Lauf: gleiche Zeilenzahl, keine Dubletten
                diff2, meldung2 = import_preisliste.import_ausfuehren(s)
                self.assertEqual(anzahl_v27d_artikel(s), ZEILEN)
                self.assertEqual(len(diff2.neu), 0)
                self.assertTrue(meldung2.startswith("0 neu"), meldung2)
                guids = [g for (g,) in s.query(Artikel.guid)
                         .filter(Artikel.guid.like(f"{PRAEFIX}-%"))]
                self.assertEqual(len(guids), len(set(guids)))
                # Abbruch nach Block 1: alles entfernen, zweiter Commit scheitert
                artikel_aufraeumen()
                s.expire_all()
                echter_commit = s.commit
                zustand = {"n": 0}

                def abbruch_commit():
                    zustand["n"] += 1
                    if zustand["n"] == 2:
                        raise RuntimeError("V27D Abbruch nach Block 1")
                    echter_commit()

                with mock.patch.object(s, "commit", side_effect=abbruch_commit):
                    with self.assertRaises(RuntimeError):
                        import_preisliste.import_ausfuehren(s)
                s.rollback()
                self.assertNotIn("Preisliste", [i["name"] for i in betrieb.laufende_importe()])
                self.assertEqual(anzahl_v27d_artikel(s), import_preisliste.BLOCK)
                # Wiederholung holt den Rest nach – ohne Doppelanlage
                diff3, _ = import_preisliste.import_ausfuehren(s)
                self.assertEqual(anzahl_v27d_artikel(s), ZEILEN)
                self.assertEqual(len(diff3.neu), ZEILEN - import_preisliste.BLOCK)
                self.assertEqual(s.query(Artikel).filter(Artikel.quelle == QUELLE_PREISLISTE,
                                                         Artikel.aktiv.is_(False)).count(),
                                 inaktiv_vorher)
        finally:
            s.close()
            artikel_aufraeumen()

    def test_pv_bloecke_wiederholbar(self):
        """Echter PV-Import (idempotent) mit kleiner Blockgröße: Commit je Block,
        zweiter Lauf ohne Doppel."""
        s = SessionLocal()
        try:
            vorher = s.query(Artikel).filter(Artikel.quelle == "pv").count()
            with mock.patch.object(import_pv, "BLOCK", 20):
                with commit_spion(s) as spion:
                    diff, _ = import_pv.import_ausfuehren(s)
                zeilen = len(diff.neu) + len(diff.geaendert) + diff.unveraendert
                self.assertGreaterEqual(spion.call_count, zeilen // 20)
                nachher = s.query(Artikel).filter(Artikel.quelle == "pv").count()
                self.assertEqual(nachher, vorher + len(diff.neu))
                diff2, meldung2 = import_pv.import_ausfuehren(s)
            self.assertEqual(len(diff2.neu), 0)
            self.assertIn("0 neu", meldung2)
            self.assertEqual(s.query(Artikel).filter(Artikel.quelle == "pv").count(), nachher)
        finally:
            s.close()

    def test_klima_bloecke_wiederholbar(self):
        s = SessionLocal()
        try:
            with mock.patch.object(import_klima, "BLOCK", 10):
                with commit_spion(s) as spion:
                    diff, _ = import_klima.import_ausfuehren(s)
                zeilen = len(diff.neu) + len(diff.geaendert) + diff.unveraendert
                self.assertGreaterEqual(spion.call_count, zeilen // 10)
                diff2, meldung2 = import_klima.import_ausfuehren(s)
            self.assertEqual(len(diff2.neu), 0)
            self.assertIn("0 neu", meldung2)
            self.assertEqual(s.query(Artikel).filter(Artikel.quelle == import_klima.QUELLE_KL,
                                                     Artikel.aktiv.is_(True)).count(), 50)
        finally:
            s.close()


def bestand_datei(zeilen: list[dict]) -> bytes:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(bestandsimport.vorlage_bytes()))
    ws = wb["Projekte"]
    ws.delete_rows(2, 1)                       # Beispielzeile raus
    titel = [t for _, t, _, _ in bestandsimport.SPALTEN]
    for werte in zeilen:
        ws.append([werte.get(t, "") for t in titel])
    puffer = io.BytesIO()
    wb.save(puffer)
    return puffer.getvalue()


def bestand_zeilen(anzahl: int, pl_name: str) -> list[dict]:
    return [{"Kunde Anrede": "Herr", "Vorname": f"Tim{i}", "Nachname": f"{PRAEFIX} Bestand {i}",
             "Straße": "Teststr. 1", "PLZ": "47139", "Ort": "Duisburg", "E-Mail": TEST_EMAIL,
             "Sparte": "WP", "TAIFUN-Angebotsnummer": f"{PRAEFIX}{i:03d}",
             "Auftragswert brutto": "1.000,00", "Auftragsdatum": "01.09.2026",
             "Projektleiter (Name)": pl_name, "Phase": "Auftragseingang"}
            for i in range(1, anzahl + 1)]


class BestandBlockbildung(Basis):
    def test_bestand_bloecke_abbruch_wiederholbar(self):
        s = SessionLocal()
        try:
            pl = projektleiter_name()
            zeilen = bestandsimport.einlesen(bestand_datei(bestand_zeilen(5, pl)))[0]
            bestandsimport.pruefen(s, zeilen)
            self.assertTrue(all(z.ok for z in zeilen), [z.fehler for z in zeilen])
            with mock.patch.object(bestandsimport, "BLOCK", 2):
                # Abbruch nach Block 1 (2 Zeilen): zweiter Commit scheitert
                echter_commit = s.commit
                zustand = {"n": 0}

                def abbruch_commit():
                    zustand["n"] += 1
                    if zustand["n"] == 2:
                        raise RuntimeError("V27D Abbruch nach Block 1")
                    echter_commit()

                with mock.patch.object(s, "commit", side_effect=abbruch_commit):
                    with self.assertRaises(RuntimeError):
                        bestandsimport.importieren(s, zeilen, f"{PRAEFIX} abbruch.xlsx")
                s.rollback()
                self.assertNotIn("Bestandsimport",
                                 [i["name"] for i in betrieb.laufende_importe()])
                imp_abbruch = (s.query(Bestandsimport)
                               .filter(Bestandsimport.dateiname == f"{PRAEFIX} abbruch.xlsx").one())
                self.assertEqual(imp_abbruch.angelegt, 2)          # Zwischenstand gespeichert
                self.assertIsNone(imp_abbruch.abgeschlossen_am)
                self.assertEqual(s.query(Angebot).filter(
                    Angebot.taifun_nummer.like(f"{PRAEFIX}%")).count(), 2)
                # Wiederholung: Commit je Block, Upsert über TAIFUN-Nummer + Sparte
                zeilen = bestandsimport.einlesen(bestand_datei(bestand_zeilen(5, pl)))[0]
                bestandsimport.pruefen(s, zeilen)
                with commit_spion(s) as spion:
                    imp = bestandsimport.importieren(s, zeilen, f"{PRAEFIX} voll.xlsx")
                    s.commit()
                self.assertGreaterEqual(spion.call_count, 5 // 2 + 1)
                self.assertEqual((imp.angelegt, imp.aktualisiert), (3, 2))
                self.assertIsNotNone(imp.abgeschlossen_am)
                self.assertEqual(s.query(Angebot).filter(
                    Angebot.taifun_nummer.like(f"{PRAEFIX}%")).count(), 5)
                self.assertEqual(s.query(Kunde).filter(Kunde.email == TEST_EMAIL).count(), 5)
                # dritter Lauf: nur aktualisieren, keine neuen Gewerke
                gewerke = s.query(Gewerk).count()
                zeilen = bestandsimport.einlesen(bestand_datei(bestand_zeilen(5, pl)))[0]
                bestandsimport.pruefen(s, zeilen)
                imp3 = bestandsimport.importieren(s, zeilen, f"{PRAEFIX} dritter.xlsx")
                s.commit()
                self.assertEqual((imp3.angelegt, imp3.aktualisiert), (0, 5))
                self.assertEqual(s.query(Gewerk).count(), gewerke)
        finally:
            s.close()
            bestand_aufraeumen()


# --- (c) laufende Importe --------------------------------------------------------

class LaufendeImporte(Basis):
    def test_import_markieren_im_thread(self):
        s0 = SessionLocal()
        try:
            echt = logik_modul.logik_einlesen()
        finally:
            s0.close()
        client = TestClient(app)

        def langsam():
            time.sleep(1.5)
            return echt

        fehler: list = []

        def lauf():
            s = SessionLocal()
            try:
                with mock.patch.object(logik_modul, "logik_einlesen", side_effect=langsam):
                    logik_modul.neu_einlesen(s)
            except Exception as problem:       # pragma: no cover – nur Diagnose
                fehler.append(problem)
            finally:
                s.close()

        faden = threading.Thread(target=lauf)
        faden.start()
        time.sleep(0.5)
        waehrend = [i["name"] for i in betrieb.laufende_importe()]
        health = client.get("/health").json()
        faden.join(15)
        self.assertEqual(fehler, [])
        self.assertIn("Logik-Excel", waehrend)
        self.assertIn("Logik-Excel", health.get("importe", []))
        self.assertNotIn("Logik-Excel", [i["name"] for i in betrieb.laufende_importe()])

    def test_namen_der_fuenf_importe(self):
        """Die Modulfunktionen melden die Namen aus dem Briefing (echte, idempotente
        Läufe; der Bestandsimport ohne Zeilen wird zurückgerollt)."""
        gesehen = []
        echt = betrieb.import_markieren

        def spion(name):
            gesehen.append(name)
            return echt(name)

        with mock.patch.object(betrieb, "import_markieren", side_effect=spion):
            s = SessionLocal()
            try:
                import_preisliste.import_ausfuehren(s)
                import_pv.import_ausfuehren(s)
                import_klima.import_ausfuehren(s)
                logik_modul.neu_einlesen(s)
                bestandsimport.importieren(s, [], f"{PRAEFIX} leer.xlsx")
                s.rollback()
            finally:
                s.close()
        self.assertEqual(gesehen, ["Preisliste", "PV-Positionslisten", "Klima-Positionslisten",
                                   "Logik-Excel", "Bestandsimport"])


# --- (d)+(e) Routen: Hinweis, Bestätigung, Dauer -------------------------------------

class Routen(Basis):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})

    def test_hinweis_und_bestaetigungsfeld_auf_jeder_importseite(self):
        dauer_setzen("import_dauer_preisliste", "7")
        for name in DAUER_NAMEN[1:]:
            dauer_zuruecksetzen({name: None})
        erwartet = {
            "/artikel/import": "Dauer etwa 7 s",              # Dauer des letzten Laufs
            "/artikel/import-pv": "Dauer etwa 10 s",          # Standard PV
            "/parametrierung/artikel/kl-import": "Dauer etwa 10 s",   # Standard Klima
            "/parametrierung/logik": "Dauer etwa 15 s",       # Standard Logik
            "/parametrierung/bestandsimport": "Dauer etwa 30 s",      # Standard Bestand
            "/parametrierung/kl-logik": "Dauer etwa 10 s",
        }
        for pfad, text in erwartet.items():
            r = self.client.get(pfad)
            self.assertEqual(r.status_code, 200, pfad)
            self.assertRegex(r.text, HINWEIS_REGEX, pfad)
            self.assertIn(text, r.text, pfad)
            if pfad != "/parametrierung/bestandsimport":      # Häkchen erst in der Vorschau
                self.assertIn('name="bestaetigt"', r.text, pfad)
        # Bestandsimport: Häkchen in der Vorschau (POST mit Datei)
        pl = projektleiter_name()
        r = self.client.post("/parametrierung/bestandsimport/vorschau",
                             files={"datei": (f"{PRAEFIX} vorschau.xlsx",
                                              io.BytesIO(bestand_datei(bestand_zeilen(1, pl))))})
        self.assertEqual(r.status_code, 200)
        self.assertIn('name="bestaetigt"', r.text)
        self.assertRegex(r.text, HINWEIS_REGEX)
        kennung = re.search(r'name="kennung" value="(\w+)"', r.text).group(1)
        self.client.post("/parametrierung/bestandsimport/ausfuehren",
                         data={"kennung": kennung, "abbrechen": "1"}, follow_redirects=False)

    def test_post_ohne_bestaetigung_abgewiesen(self):
        faelle = [
            ("/artikel/import", import_preisliste, "import_ausfuehren", "/artikel/import?meldung="),
            ("/artikel/import-pv", import_pv, "import_ausfuehren", "/artikel/import-pv?meldung="),
            ("/parametrierung/artikel/kl-import", import_klima, "import_ausfuehren",
             "/parametrierung/logik?meldung="),
            ("/parametrierung/neu-einlesen", logik_modul, "neu_einlesen",
             "/parametrierung/logik?meldung="),
        ]
        for pfad, modul, funktion, ziel in faelle:
            with mock.patch.object(modul, funktion) as nicht_aufgerufen:
                r = self.client.post(pfad, follow_redirects=False)
            self.assertEqual(r.status_code, 303, pfad)
            self.assertTrue(r.headers["location"].startswith(ziel), (pfad, r.headers["location"]))
            self.assertIn("Bitte+den+Hinweis+best", r.headers["location"], pfad)
            nicht_aufgerufen.assert_not_called()
        # Neu einlesen von der Übersicht aus: Meldung dort (Referer-Rücksprung bleibt)
        with mock.patch.object(logik_modul, "neu_einlesen") as nicht_aufgerufen:
            r = self.client.post("/parametrierung/neu-einlesen",
                                 headers={"referer": "http://testserver/parametrierung"},
                                 follow_redirects=False)
        self.assertTrue(r.headers["location"].startswith("/parametrierung?meldung=Bitte"))
        nicht_aufgerufen.assert_not_called()
        # Bestandsimport: gültige Vorschau, POST ohne Häkchen → kein Import
        pl = projektleiter_name()
        r = self.client.post("/parametrierung/bestandsimport/vorschau",
                             files={"datei": (f"{PRAEFIX} ohne.xlsx",
                                              io.BytesIO(bestand_datei(bestand_zeilen(1, pl))))})
        kennung = re.search(r'name="kennung" value="(\w+)"', r.text).group(1)
        s = SessionLocal()
        try:
            vorher = s.query(Bestandsimport).count()
            r = self.client.post("/parametrierung/bestandsimport/ausfuehren",
                                 data={"kennung": kennung, "dateiname": f"{PRAEFIX} ohne.xlsx"},
                                 follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("Bitte+den+Hinweis+best", r.headers["location"])
            self.assertEqual(s.query(Bestandsimport).count(), vorher)
            self.assertEqual(s.query(Kunde).filter(Kunde.email == TEST_EMAIL).count(), 0)
        finally:
            s.close()
        # Abbrechen braucht keine Bestätigung und räumt die Datei weg
        r = self.client.post("/parametrierung/bestandsimport/ausfuehren",
                             data={"kennung": kennung, "abbrechen": "1"}, follow_redirects=False)
        self.assertIn("abgebrochen", r.headers["location"])

    def test_dauer_einstellung_nach_lauf(self):
        dauer_zuruecksetzen({"import_dauer_preisliste": None, "import_dauer_logik": None,
                             "import_dauer_klima": None})
        # Preisliste: Lauf gemockt (0,2 s) → Einstellung gesetzt, Redirect wie bisher
        def schnell(session):
            time.sleep(0.2)
            return import_preisliste.Diff(), "0 neu, 0 geändert, 0 unverändert, 0 deaktiviert"

        with mock.patch.object(import_preisliste, "import_ausfuehren", side_effect=schnell):
            r = self.client.post("/artikel/import", data={"bestaetigt": "1"},
                                 follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/artikel?meldung=Import+abgeschlossen"))
        self.assertTrue(dauer_lesen("import_dauer_preisliste").isdigit())
        self.assertGreaterEqual(int(dauer_lesen("import_dauer_preisliste")), 1)
        # Logik-Excel: echter Lauf über die Route
        r = self.client.post("/parametrierung/neu-einlesen", data={"bestaetigt": "1"},
                             headers={"referer": "http://testserver/parametrierung/logik"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("/parametrierung/logik?meldung=Parametrierung+neu+eingelesen",
                      r.headers["location"])
        self.assertTrue(dauer_lesen("import_dauer_logik").isdigit())
        # Klima: echter Lauf (idempotent) über die Route mit Häkchen
        r = self.client.post("/parametrierung/artikel/kl-import", data={"bestaetigt": "on"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Klima-Import+abgeschlossen", r.headers["location"])
        self.assertTrue(dauer_lesen("import_dauer_klima").isdigit())
        # Die Seite zeigt danach die gemessene Dauer
        n = dauer_lesen("import_dauer_klima")
        self.assertIn(f"Dauer etwa {n} s", self.client.get("/parametrierung/artikel/kl-import").text)

    def test_hilfsfunktionen(self):
        s = SessionLocal()
        try:
            dauer_zuruecksetzen({"import_dauer_bestand": None})
            self.assertEqual(import_preisliste.import_dauer(s, "bestand"), 30)
            einstellung_setzen(s, "import_dauer_bestand", "kaputt")
            s.commit()
            self.assertEqual(import_preisliste.import_dauer(s, "bestand"), 30)
            einstellung_setzen(s, "import_dauer_bestand", "0")
            s.commit()
            self.assertEqual(import_preisliste.import_dauer(s, "bestand"), 1)
            self.assertTrue(import_preisliste.import_bestaetigt({"bestaetigt": "1"}))
            self.assertTrue(import_preisliste.import_bestaetigt({"bestaetigt": "on"}))
            self.assertFalse(import_preisliste.import_bestaetigt({"bestaetigt": "0"}))
            self.assertFalse(import_preisliste.import_bestaetigt({}))
            start = time.perf_counter() - 3.4
            self.assertEqual(import_preisliste.import_dauer_merken(s, "bestand", start), 3)
            self.assertEqual(einstellung_holen(s, "import_dauer_bestand", ""), "3")
            self.assertRegex(import_preisliste.import_hinweis(s, "bestand"), HINWEIS_REGEX)
            self.assertEqual(set(import_preisliste.import_hinweise(s)),
                             {"preisliste", "pv", "klima", "logik", "bestand", "monday"})
        finally:
            s.close()


if __name__ == "__main__":
    unittest.main()
