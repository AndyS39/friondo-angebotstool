# v30 (PLAN_V18 Phase 149): Regressionstest zu Fehler F-20261002-073115-9c9e
# („Überarbeiten → Version .2 → Duplizieren“). Befund (Reproduktion auf der
# DB-Kopie, diagnose/v30/B_ergebnis.md): ohne Sperre läuft der Ablauf fehlerfrei
# (alle Kennzeichen übernommen); mit gehaltener SQLite-Schreibsperre starb die
# Route duplizieren ohne die v22-Wiederholung an „database is locked“ (INSERT INTO
# angebote in angebot_anlegen) → Fehler-Nr. Seit v30 laufen duplizieren,
# ueberarbeiten und kopieren über _speichern (Rollback + eine Wiederholung).
# Sperre wie in tests/test_v22_positionen.py über eine zweite sqlite3-Verbindung
# (BEGIN IMMEDIATE) in einem Thread. Räumt Kunden mit v30b-duplizieren@test.local
# und die eigenen Fehlerprotokoll-Einträge auf.
import sqlite3
import threading
import time
import unittest
import warnings

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, config
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Fehlerprotokoll, Kunde, Vorgang,
                        angebot_status_setzen)

TEST_EMAIL = "v30b-duplizieren@test.local"
KENNZEICHEN = (
    {"alternativ": True, "alternativ_zu": "PV-Angebot AN-C-999999"},
    {"bauseits": True},
    {"ep_flag": True},
    {"rabatt_prozent": 10.0},
    {"anzeige_nr": "A7", "sonderpreis": True, "original_preis_cent": 50000},
    {},
)


def _sperre_halten(sekunden: float, bereit: threading.Event) -> None:
    verbindung = sqlite3.connect(str(config.DB_PFAD), isolation_level=None, timeout=30)
    try:
        verbindung.execute("BEGIN IMMEDIATE")
        bereit.set()
        time.sleep(sekunden)
        verbindung.execute("ROLLBACK")
    finally:
        verbindung.close()


def kennzeichen(angebot):
    return [(p.pos_nr, bool(p.ep_flag), bool(p.bauseits), bool(p.alternativ), p.alternativ_zu,
             p.anzeige_nr, p.rabatt_prozent, bool(p.sonderpreis), p.original_preis_cent,
             p.e_preis_cent, p.menge, p.beschreibung)
            for p in angebot.positionen]


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        cls._aufraeumen()
        cls.kunde = Kunde(anrede="Herr", vorname="Dirk", nachname="V30B Duplizieren",
                          strasse="Teststr. 1", plz="47139", ort="Duisburg", email=TEST_EMAIL)
        cls.s.add(cls.kunde)
        cls.s.commit()
        cls.client = TestClient(app, raise_server_exceptions=False)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})

    @classmethod
    def _aufraeumen(cls):
        ids = []
        for k in cls.s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
            for a in cls.s.query(Angebot).filter_by(kunde_id=k.id):
                ids.append(a.id)
                cls.s.delete(a)
            for v in cls.s.query(Vorgang).filter_by(kunde_id=k.id):
                cls.s.delete(v)
            cls.s.delete(k)
        for k in cls.s.query(Kunde).filter(Kunde.nachname == "V30B Kopie-Zielkunde"):
            for a in cls.s.query(Angebot).filter_by(kunde_id=k.id):
                ids.append(a.id)
                cls.s.delete(a)
            for v in cls.s.query(Vorgang).filter_by(kunde_id=k.id):
                cls.s.delete(v)
            cls.s.delete(k)
        for angebot_id in ids:
            cls.s.query(Fehlerprotokoll).filter(
                Fehlerprotokoll.pfad.like(f"/angebote/{angebot_id}/%")).delete(
                synchronize_session=False)
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        cls._aufraeumen()
        cls.s.close()

    def angebot(self, status="Versendet"):
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id)
        for i, extra in enumerate(KENNZEICHEN, 1):
            a.positionen.append(AngebotsPosition(
                sort=i, pos_nr=f"9{i:02d}", bezeichnung=f"P{i}", beschreibung=f"Text {i}\nZeile 2",
                menge=1.5, einheit="Stk", e_preis_cent=100000 * i, block_nr=1,
                gruppe="Gruppe V30B", **extra))
        a.zahlungsbedingung_key = "anzahlung_80_skonto"
        a.zahlungsbedingung_text = ""
        a.rabatt_cent = 50000
        a.rabatt_bezeichnung = "Treuerabatt"
        if status != "Entwurf":
            angebot_status_setzen(a, status)
        self.s.commit()
        return a

    def version_von(self, original) -> Angebot:
        self.s.expire_all()
        return self.s.query(Angebot).filter(Angebot.vorgaenger_id == original.id).one()

    def protokoll_eintraege(self, angebot_id):
        return (self.s.query(Fehlerprotokoll)
                .filter(Fehlerprotokoll.pfad.like(f"/angebote/{angebot_id}/%")).all())


class UeberarbeitenDuplizieren(Basis):
    def test_ueberarbeiten_dann_duplizieren_der_version(self):
        a = self.angebot()
        r = self.client.post(f"/angebote/{a.id}/ueberarbeiten", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        version = self.version_von(a)
        self.assertEqual(version.nummer, f"{a.stamm_nummer}.2")
        self.assertEqual(version.status, "Entwurf")
        self.assertEqual(self.s.get(Angebot, a.id).status, "Überholt")
        self.assertEqual(kennzeichen(version), kennzeichen(a))
        self.assertEqual((version.zahlungsbedingung_key, version.zahlungsbedingung_text),
                         ("anzahlung_80_skonto", ""))
        # Duplizieren der Version .2
        r = self.client.post(f"/angebote/{version.id}/duplizieren", follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        ort = r.headers["location"]
        self.assertTrue(ort.endswith("?meldung=Angebot+dupliziert"), ort)
        self.assertNotIn("Fehler-Nr", ort)
        neu_id = int(ort.split("/angebote/")[1].split("?")[0])
        self.s.expire_all()
        neu = self.s.get(Angebot, neu_id)
        self.assertIsNotNone(neu)
        # eigene Nummer aus dem Nummernkreis – keine „.2“, nicht die Stammnummer
        self.assertNotIn(".", neu.nummer)
        self.assertNotEqual(neu.nummer, version.nummer)
        self.assertNotEqual(neu.stamm_nummer, version.stamm_nummer)
        self.assertEqual(neu.status, "Entwurf")
        self.assertIsNone(neu.vorgaenger_id)
        self.assertEqual(neu.kunde_id, a.kunde_id)
        # alle Positionen und Kennzeichen, Zahlungsbedingung, Summen
        self.assertEqual(len(neu.positionen), len(KENNZEICHEN))
        self.assertEqual(kennzeichen(neu), kennzeichen(version))
        self.assertEqual(neu.summen()["netto"], version.summen()["netto"])
        self.assertEqual((neu.zahlungsbedingung_key, neu.zahlungsbedingung_text),
                         ("anzahlung_80_skonto", ""))
        self.assertEqual(neu.kfw_json, version.kfw_json)
        # Editor und PDF des Duplikats laufen, kein Fehlerprotokoll-Eintrag
        self.assertEqual(self.client.get(f"/angebote/{neu.id}").status_code, 200)
        self.assertEqual(self.client.get(f"/angebote/{neu.id}/pdf").status_code, 200)
        for angebot_id in (a.id, version.id, neu.id):
            self.assertEqual(self.protokoll_eintraege(angebot_id), [])
        # Duplizieren des überholten Originals geht ebenfalls
        r = self.client.post(f"/angebote/{a.id}/duplizieren", follow_redirects=False)
        self.assertTrue(r.headers["location"].endswith("?meldung=Angebot+dupliziert"))

    def test_freitext_wandert_in_version_duplikat_und_kopie(self):
        a = self.angebot()
        a.zahlungsbedingung_key = "freitext"
        a.zahlungsbedingung_text = "Zahlung nach Vereinbarung."
        self.s.commit()
        self.client.post(f"/angebote/{a.id}/ueberarbeiten", follow_redirects=False)
        version = self.version_von(a)
        self.assertEqual((version.zahlungsbedingung_key, version.zahlungsbedingung_text),
                         ("freitext", "Zahlung nach Vereinbarung."))
        r = self.client.post(f"/angebote/{version.id}/duplizieren", follow_redirects=False)
        dup = self.s.get(Angebot, int(r.headers["location"].split("/angebote/")[1].split("?")[0]))
        self.assertEqual((dup.zahlungsbedingung_key, dup.zahlungsbedingung_text),
                         ("freitext", "Zahlung nach Vereinbarung."))
        r = self.client.post(f"/angebote/{version.id}/kopieren",
                             data={"kunde_suche": "", "neu_anrede": "Frau", "neu_vorname": "Karla",
                                   "neu_nachname": "V30B Kopie-Zielkunde", "neu_plz": "47051",
                                   "neu_ort": "Duisburg"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Kopie+von", r.headers["location"])
        kopie = self.s.get(Angebot, int(r.headers["location"].split("/angebote/")[1].split("?")[0]))
        self.assertEqual((kopie.zahlungsbedingung_key, kopie.zahlungsbedingung_text),
                         ("freitext", "Zahlung nach Vereinbarung."))
        self.assertEqual(kopie.kopie_von, version.nummer)
        self.assertEqual(len(kopie.positionen), len(KENNZEICHEN))
        self.assertNotEqual(kopie.kunde_id, a.kunde_id)


class UnterSchreibsperre(Basis):
    def test_duplizieren_kurze_sperre_wiederholt(self):
        """Sperre 6,5 s > busy_timeout 5 s: erster Versuch scheitert, die
        Wiederholung nach 0,7 s kommt durch → Duplikat da, kein 500, kein Eintrag."""
        a = self.angebot()
        self.client.post(f"/angebote/{a.id}/ueberarbeiten", follow_redirects=False)
        version = self.version_von(a)
        bereit = threading.Event()
        t = threading.Thread(target=_sperre_halten, args=(6.5, bereit))
        t.start()
        bereit.wait(5)
        start = time.time()
        r = self.client.post(f"/angebote/{version.id}/duplizieren", follow_redirects=False)
        dauer = time.time() - start
        t.join()
        self.assertEqual(r.status_code, 303)
        ort = r.headers["location"]
        self.assertTrue(ort.endswith("?meldung=Angebot+dupliziert"), ort)
        self.assertGreater(dauer, 4.5)     # hat auf die Sperre gewartet
        self.s.expire_all()
        neu = self.s.get(Angebot, int(ort.split("/angebote/")[1].split("?")[0]))
        self.assertEqual(kennzeichen(neu), kennzeichen(version))
        self.assertEqual(self.protokoll_eintraege(version.id), [])

    def test_duplizieren_lange_sperre_meldung_statt_500(self):
        """Sperre 13 s: beide Versuche scheitern → globaler Handler: 303 zurück in
        den Editor mit „Datenbank kurz belegt …“ + Fehlerprotokoll-Eintrag (so
        entstand F-20261002-073115-9c9e); kein halbes Duplikat."""
        a = self.angebot()
        self.client.post(f"/angebote/{a.id}/ueberarbeiten", follow_redirects=False)
        version = self.version_von(a)
        vorher = self.s.query(Angebot).filter(Angebot.kunde_id == self.kunde.id).count()
        bereit = threading.Event()
        t = threading.Thread(target=_sperre_halten, args=(13, bereit))
        t.start()
        bereit.wait(5)
        r = self.client.post(f"/angebote/{version.id}/duplizieren", follow_redirects=False)
        t.join()
        self.assertEqual(r.status_code, 303)
        ort = r.headers["location"]
        self.assertTrue(ort.startswith(f"/angebote/{version.id}?meldung="), ort)
        self.assertIn("Datenbank+kurz+belegt", ort)
        self.assertIn("Fehler-Nr", ort)
        self.s.expire_all()
        self.assertEqual(self.s.query(Angebot).filter(Angebot.kunde_id == self.kunde.id).count(),
                         vorher)
        eintraege = self.protokoll_eintraege(version.id)
        self.assertEqual(len(eintraege), 1)
        self.assertEqual(eintraege[0].pfad, f"/angebote/{version.id}/duplizieren")
        self.assertIn("locked", (eintraege[0].meldung or "").lower())
        self.assertEqual(self.client.get(f"/angebote/{version.id}").status_code, 200)

    def test_ueberarbeiten_und_kopieren_kurze_sperre(self):
        a = self.angebot()
        bereit = threading.Event()
        t = threading.Thread(target=_sperre_halten, args=(6.5, bereit))
        t.start()
        bereit.wait(5)
        r = self.client.post(f"/angebote/{a.id}/ueberarbeiten", follow_redirects=False)
        t.join()
        self.assertEqual(r.status_code, 303)
        self.assertIn("als+Entwurf+erstellt", r.headers["location"])
        version = self.version_von(a)
        self.assertEqual(kennzeichen(version), kennzeichen(a))
        self.assertEqual(self.protokoll_eintraege(a.id), [])
        bereit = threading.Event()
        t = threading.Thread(target=_sperre_halten, args=(6.5, bereit))
        t.start()
        bereit.wait(5)
        r = self.client.post(f"/angebote/{version.id}/kopieren",
                             data={"kunde_suche": "", "neu_nachname": "V30B Kopie-Zielkunde",
                                   "neu_plz": "47051", "neu_ort": "Duisburg"},
                             follow_redirects=False)
        t.join()
        self.assertEqual(r.status_code, 303)
        self.assertIn("Kopie+von", r.headers["location"])
        self.assertEqual(self.protokoll_eintraege(version.id), [])


if __name__ == "__main__":
    unittest.main()
