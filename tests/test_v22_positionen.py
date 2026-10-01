# v22 (PLAN_V15 Phase 103): Positionsrouten unter „database is locked“ und
# mit fehlerhaften Sortier-Payloads – der sporadische Internal Server Error
# beim Löschen/Verschieben wird abgefangen (Wiederholung bzw. Meldung mit
# Fehler-Nr. aus dem Fehlerprotokoll). Sperre wird über eine zweite
# sqlite3-Verbindung (BEGIN IMMEDIATE) in einem Thread simuliert.
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
from app.models import Angebot, AngebotsPosition, Fehlerprotokoll, Kunde

TEST_EMAIL = "v22-positionen@test.local"


def _sperre_halten(sekunden: float, bereit: threading.Event) -> None:
    verbindung = sqlite3.connect(str(config.DB_PFAD), isolation_level=None, timeout=30)
    try:
        verbindung.execute("BEGIN IMMEDIATE")
        bereit.set()
        time.sleep(sekunden)
        verbindung.execute("ROLLBACK")
    finally:
        verbindung.close()


class PositionenUnterSperre(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        cls._aufraeumen()
        cls.kunde = Kunde(anrede="Herr", vorname="Max", nachname="Positionen v22",
                          strasse="Teststr. 1", plz="47139", ort="Duisburg", email=TEST_EMAIL)
        cls.s.add(cls.kunde)
        cls.s.commit()
        cls.client = TestClient(app, raise_server_exceptions=False)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})

    @classmethod
    def _aufraeumen(cls):
        for k in cls.s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
            for a in cls.s.query(Angebot).filter_by(kunde_id=k.id):
                cls.s.delete(a)
            cls.s.delete(k)
        cls.s.query(Fehlerprotokoll).filter(
            Fehlerprotokoll.pfad.like("%/position/%") | Fehlerprotokoll.pfad.like("%/sortierung")
        ).delete(synchronize_session=False)
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        cls._aufraeumen()
        cls.s.close()

    def angebot(self, anzahl=3):
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id)
        for i in range(1, anzahl + 1):
            a.positionen.append(AngebotsPosition(sort=i, pos_nr=f"T{i:02d}", bezeichnung=f"Test {i}",
                                                 menge=1, e_preis_cent=1000 * i, block_nr=1,
                                                 gruppe="Gruppe A"))
        self.s.commit()
        return a

    def test_loeschen_unter_kurzer_sperre_wiederholt(self):
        """Sperre 6,5 s > busy_timeout 5 s: erster Versuch scheitert, die
        Wiederholung nach 0,7 s kommt durch → Position gelöscht, kein 500."""
        a = self.angebot()
        pid = a.positionen[0].id
        bereit = threading.Event()
        t = threading.Thread(target=_sperre_halten, args=(6.5, bereit))
        t.start()
        bereit.wait(5)
        start = time.time()
        r = self.client.post(f"/angebote/{a.id}/position/{pid}/entfernen", follow_redirects=False)
        dauer = time.time() - start
        t.join()
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], f"/angebote/{a.id}")
        self.s.expire_all()
        self.assertIsNone(self.s.get(AngebotsPosition, pid))
        self.assertGreater(dauer, 4.5)     # hat auf die Sperre gewartet

    def test_loeschen_unter_langer_sperre_meldung_statt_500(self):
        """Sperre 13 s: beide Versuche scheitern → globaler Handler:
        303 mit Meldung „Datenbank kurz belegt“ + Fehlerprotokoll-Eintrag."""
        a = self.angebot()
        pid = a.positionen[1].id
        bereit = threading.Event()
        t = threading.Thread(target=_sperre_halten, args=(13, bereit))
        t.start()
        bereit.wait(5)
        r = self.client.post(f"/angebote/{a.id}/position/{pid}/entfernen", follow_redirects=False)
        t.join()
        self.assertEqual(r.status_code, 303)
        ort = r.headers["location"]
        self.assertTrue(ort.startswith(f"/angebote/{a.id}?meldung="), ort)
        self.assertIn("Datenbank+kurz+belegt", ort)
        self.assertIn("Fehler-Nr", ort)
        self.s.expire_all()
        self.assertIsNotNone(self.s.get(AngebotsPosition, pid))    # nicht gelöscht
        eintrag = (self.s.query(Fehlerprotokoll)
                   .filter(Fehlerprotokoll.pfad == f"/angebote/{a.id}/position/{pid}/entfernen")
                   .order_by(Fehlerprotokoll.id.desc()).first())
        self.assertIsNotNone(eintrag)
        self.assertEqual(eintrag.angebot_id, a.id)
        self.assertIn("locked", (eintrag.meldung or "").lower())
        # Editor danach normal erreichbar
        self.assertEqual(self.client.get(f"/angebote/{a.id}").status_code, 200)

    def test_sortierung_payloads(self):
        a = self.angebot()
        ids = [p.id for p in a.positionen]
        # Unicode-Ziffer und doppelte Minus: kein 500, Rückmeldung statt stillem Ignorieren
        r = self.client.post(f"/angebote/{a.id}/sortierung",
                             data={"reihenfolge": "²," + ",".join(map(str, ids))},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        r = self.client.post(f"/angebote/{a.id}/sortierung",
                             data={"reihenfolge": ",".join(map(str, ids[:-1]))},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Reihenfolge+nicht", r.headers["location"])
        # gültige Umsortierung mit ungültigem ziel_block → Reihenfolge übernommen
        neu = [ids[2], ids[0], ids[1]]
        r = self.client.post(f"/angebote/{a.id}/sortierung",
                             data={"reihenfolge": ",".join(map(str, neu)),
                                   "bewegt_id": str(ids[2]), "ziel_block": "--5",
                                   "ziel_gruppe": "Gruppe A"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], f"/angebote/{a.id}")
        self.s.expire_all()
        self.assertEqual([p.id for p in self.s.get(Angebot, a.id).positionen], neu)
        # gelöschte Position im Payload → Meldung, keine Änderung
        self.client.post(f"/angebote/{a.id}/position/{ids[0]}/entfernen", follow_redirects=False)
        r = self.client.post(f"/angebote/{a.id}/sortierung",
                             data={"reihenfolge": ",".join(map(str, neu))}, follow_redirects=False)
        self.assertIn("Reihenfolge+nicht", r.headers["location"])
        # letzte Positionen löschen → Editor bleibt erreichbar
        for pid in ids[1:]:
            self.client.post(f"/angebote/{a.id}/position/{pid}/entfernen", follow_redirects=False)
        self.assertEqual(self.client.get(f"/angebote/{a.id}").status_code, 200)

    def test_signiertes_pdf_altpfad(self):
        """Voll-Crawl 30.09.: signierte_datei mit fremdem absoluten Pfad →
        Meldung statt RuntimeError/500; Datei im Signatur-Ordner wird gefunden."""
        from app import config
        from app.routers.signatur import signierte_datei_pfad
        a = self.angebot(1)
        a.signierte_datei = r"C:\Users\Andreas\Documents\Claude\alt\data\angebote\signiert\gibt-es-nicht.pdf"
        self.s.commit()
        r = self.client.get(f"/signatur/{a.id}/signiert.pdf", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Signierte+PDF-Datei+nicht+gefunden", r.headers["location"])
        config.SIGNIERT_ORDNER.mkdir(parents=True, exist_ok=True)
        datei = config.SIGNIERT_ORDNER / "v22-test-signiert.pdf"
        datei.write_bytes(b"%PDF-1.4 test")
        try:
            self.assertEqual(signierte_datei_pfad(r"C:\anderer\rechner\v22-test-signiert.pdf"), datei)
            a.signierte_datei = r"C:\anderer\rechner\v22-test-signiert.pdf"
            self.s.commit()
            r = self.client.get(f"/signatur/{a.id}/signiert.pdf")
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.content.startswith(b"%PDF"))
        finally:
            datei.unlink(missing_ok=True)

    def test_aendern_unter_kurzer_sperre(self):
        a = self.angebot()
        pid = a.positionen[0].id
        bereit = threading.Event()
        t = threading.Thread(target=_sperre_halten, args=(6.5, bereit))
        t.start()
        bereit.wait(5)
        r = self.client.post(f"/angebote/{a.id}/position/{pid}/aendern",
                             data={"anzeige_nr": "", "menge": "2", "e_preis": "", "rabatt_wert": "",
                                   "rabatt_typ": "betrag", "ep_flag": "on"},
                             follow_redirects=False)
        t.join()
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], f"/angebote/{a.id}")
        self.s.expire_all()
        p = self.s.get(AngebotsPosition, pid)
        self.assertEqual((p.menge, p.ep_flag), (2.0, True))


if __name__ == "__main__":
    unittest.main()
