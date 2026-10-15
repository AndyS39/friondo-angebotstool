# v33 (PLAN_V20 Phase 172): Rabatt bei 0 % USt – Kontrollwerte und Darstellung – sowie
# angebot_anlegen(commit=False) (v30-Nachtrag 22).
# Befund der Reproduktion (diagnose/v33/A_ergebnis.md, Abschnitt 7): rechnerisch griff der
# Gesamtrabatt bei 0 % schon vor v33 (Angebot.summen() rechnet brutto = netto und zieht den
# Rabatt ab, der DB sinkt um den vollen Rabatt); er fehlte nur in der Darstellung – die
# Angebotsliste zeigt je Zeile den Gesamt-Betrag VOR Rabatt (bei 0 % exakt den Nettobetrag),
# die Beschriftungen („Abzug vom Brutto-Gesamtbetrag“, „€ (brutto)“) banden ihn scheinbar an
# die USt. Kontrollwerte: PV 20.000,00 € netto, 0 % USt, Rabatt 5 % → Endbetrag 19.000,00 €,
# DB −1.000,00 € gegenüber ohne Rabatt; Rabatt 500 € → 19.500,00 €; WP (19 %) und
# Positionsrabatte unverändert. Läuft gegen DB_PFAD_OVERRIDE (Kopie); räumt den Kunden
# v33a-rabatt@test.local und den Benutzer „V33A Rabatt-AD“ wieder auf. Kein Netzzugriff.
import re
import unittest
import warnings
from datetime import datetime, timedelta
from unittest import mock
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import text

from app import angebot_aufbau, auth, db, mail_vorlagen, monday_rueckspielung, pdf_export
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Benutzer, Fehlerprotokoll, Kunde,
                        RabattFreigabe, Vorgang, angebot_status_setzen)
from app.routers import statistik

TEST_EMAIL = "v33a-rabatt@test.local"
AD_NAME = "V33A Rabatt-AD"
NETTO = 2_000_000          # 20.000,00 € netto
EK = 1_200_000             # 12.000,00 € EK → DB ohne Rabatt 8.000,00 €


def aufraeumen(s):
    ad_ids = [b.id for b in s.query(Benutzer).filter(Benutzer.name == AD_NAME)]
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.query(RabattFreigabe).filter_by(angebot_id=a.id).delete(synchronize_session=False)
            s.query(Fehlerprotokoll).filter(
                Fehlerprotokoll.pfad.like(f"/angebote/{a.id}/%")).delete(synchronize_session=False)
            s.delete(a)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.delete(v)
        s.delete(k)
    for bid in ad_ids:
        s.query(Benutzer).filter_by(id=bid).delete(synchronize_session=False)
    s.commit()


def summenblock(html: str) -> list[str]:
    """Zeilen des Summenblocks (Editor / Meine Angebote) als Klartext."""
    m = re.search(r'<table class="tabelle zusammenfassung[^"]*">(.*?)</table>', html, re.S)
    if not m:
        return []
    zeilen = []
    for z in re.findall(r"<tr>(.*?)</tr>", m.group(1), re.S):
        zeilen.append(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", z)).strip())
    return zeilen


def pdf_summenzeilen(pfad) -> list[str]:
    text_ = "\n".join((seite.extract_text() or "") for seite in PdfReader(str(pfad)).pages)
    return [z.strip() for z in text_.splitlines()
            if any(w in z for w in ("Netto-Summe", "Umsatzsteuer", "USt.", "Gesamt-Betrag",
                                    "Rabatt", "Endbetrag"))]


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.kunde = Kunde(anrede="Herr", vorname="Paul", nachname="V33A Rabatt",
                          strasse="Teststr. 1", plz="47139", ort="Duisburg", email=TEST_EMAIL)
        cls.ad = Benutzer(name=AD_NAME, rolle="aussendienst", aktiv=True,
                          email="v33a-rabatt-ad@test.local", pin_hash=auth.pin_hash("4321"))
        cls.s.add_all([cls.kunde, cls.ad])
        cls.s.commit()
        cls.client = TestClient(app, raise_server_exceptions=False)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def ad_client(self) -> TestClient:
        c = TestClient(app, raise_server_exceptions=False)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(self.ad.id))
        return c

    def angebot(self, sparte="PV", ek=EK, status="Entwurf", bezeichnung="Aktionsrabatt") -> Angebot:
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, sparte=sparte)
        a.positionen.append(AngebotsPosition(
            sort=1, pos_nr="V33A1", bezeichnung="Anlage komplett", beschreibung="Test",
            menge=1, einheit="psl.", e_preis_cent=NETTO, ek_cent=ek, block_nr=1, gruppe="Anlage"))
        a.vertriebler_id = self.ad.id
        a.rabatt_bezeichnung = bezeichnung
        if status != "Entwurf":
            angebot_status_setzen(a, status)
        self.s.commit()
        return a

    def neu_laden(self, angebot_id: int) -> Angebot:
        self.s.expire_all()
        return self.s.get(Angebot, angebot_id)


# --- Kontrollwerte ------------------------------------------------------------------------

class Kontrollwerte(Basis):
    def test_pv_0_prozent_rabatt_5_prozent(self):
        a = self.angebot()
        self.assertEqual((a.ust_satz, a.konfigurator_typ), (0.0, "PV"))
        ohne = a.summen()
        self.assertEqual((ohne["netto"], ohne["ust"], ohne["brutto"], ohne["rabatt"],
                          ohne["endbetrag"]), (NETTO, 0, NETTO, 0, NETTO))
        db_ohne = a.deckungsbeitrag()["db"]
        self.assertEqual(db_ohne, NETTO - EK)
        a.rabatt_prozent = 5.0
        su = a.summen()
        self.assertEqual(su["ust"], 0)
        self.assertEqual(su["brutto"], NETTO)                 # Gesamt-Betrag = Netto bei 0 %
        self.assertEqual(su["rabatt"], 100_000)               # 5 % von 20.000,00 €
        self.assertEqual(su["endbetrag"], 1_900_000)          # Kontrollwert 19.000,00 €
        self.assertEqual(su["rabatt_netto"], 100_000)         # bei 0 % der volle Rabatt
        self.assertEqual(su["netto_nach_rabatt"], 1_900_000)
        db_ = a.deckungsbeitrag()
        self.assertEqual(db_["db"], db_ohne - 100_000)        # DB −1.000,00 €
        self.assertEqual(db_["rabatt"], 100_000)
        self.assertEqual(db_["vk"], 1_900_000)

    def test_pv_0_prozent_rabatt_500_euro(self):
        a = self.angebot()
        a.rabatt_cent = 50_000
        su = a.summen()
        self.assertEqual((su["rabatt"], su["endbetrag"], su["rabatt_netto"]),
                         (50_000, 1_950_000, 50_000))          # Kontrollwert 19.500,00 €
        self.assertEqual(a.deckungsbeitrag()["db"], NETTO - EK - 50_000)

    def test_wp_19_prozent_unveraendert(self):
        a = self.angebot(sparte="WP")
        self.assertEqual(a.ust_satz, 19.0)
        a.rabatt_prozent = 5.0
        su = a.summen()
        self.assertEqual((su["netto"], su["ust"], su["brutto"]), (NETTO, 380_000, 2_380_000))
        self.assertEqual(su["rabatt"], 119_000)               # 5 % vom Gesamt-Betrag 23.800,00 €
        self.assertEqual(su["endbetrag"], 2_261_000)
        self.assertEqual(su["rabatt_netto"], 100_000)         # 1.190,00 € ÷ 1,19
        self.assertEqual(a.deckungsbeitrag()["db"], NETTO - EK - 100_000)
        a.rabatt_prozent = None
        a.rabatt_cent = 50_000
        su = a.summen()
        self.assertEqual((su["rabatt"], su["endbetrag"], su["rabatt_netto"]),
                         (50_000, 2_330_000, 42_017))          # 500 € ÷ 1,19 = 420,17 €
        self.assertEqual(a.deckungsbeitrag()["db"], NETTO - EK - 42_017)
        self.assertEqual(a.deckungsbeitrag()["rabatt"], 42_017)

    def test_positionsrabatt_unveraendert(self):
        a = self.angebot()
        p = a.positionen[0]
        p.rabatt_prozent = 10.0                               # Positionsrabatt: 2.000,00 €
        self.assertEqual(p.rabatt_effektiv_cent, 200_000)
        self.assertEqual(p.gesamt_cent, 1_800_000)
        self.assertEqual(a.summen()["netto"], 1_800_000)
        a.rabatt_prozent = 5.0                                # Gesamtrabatt auf 18.000,00 €
        su = a.summen()
        self.assertEqual((su["rabatt"], su["endbetrag"]), (90_000, 1_710_000))
        self.assertEqual(a.deckungsbeitrag()["db"], 1_800_000 - 90_000 - EK)

    def test_rabatt_nie_ueber_gesamtbetrag_und_extern(self):
        a = self.angebot()
        a.rabatt_cent = 3_000_000
        su = a.summen()
        self.assertEqual((su["rabatt"], su["endbetrag"]), (NETTO, 0))
        a.rabatt_cent = None
        a.rabatt_prozent = 100.0
        self.assertEqual(a.summen()["endbetrag"], 0)
        extern = Angebot(nummer="V33A-EXT", kunde_id=self.kunde.id, extern=True,
                         extern_endbetrag_cent=123_456, rabatt_cent=500)
        su = extern.summen()
        self.assertEqual((su["brutto"], su["rabatt"], su["endbetrag"], su["rabatt_netto"]),
                         (123_456, 0, 123_456, 0))
        self.assertEqual(extern.deckungsbeitrag()["db"], 0)


# --- Darstellung: Editor, PDF, Liste, Meine Angebote, {endbetrag}, monday, Statistik -----

class Darstellung(Basis):
    def test_editor_0_prozent_ohne_zusatz_brutto(self):
        a = self.angebot()
        a.rabatt_prozent = 5.0
        self.s.commit()
        r = self.client.get(f"/angebote/{a.id}")
        self.assertEqual(r.status_code, 200)
        zeilen = summenblock(r.text)
        self.assertEqual(zeilen[0], "Netto-Summe 20.000,00 €")
        self.assertTrue(zeilen[1].startswith("Umsatzsteuer 0 % (§ 12 Abs. 3 UStG)"), zeilen[1])
        self.assertIn("Gesamt-Betrag 20.000,00 €", zeilen)
        self.assertIn("− Rabatt (Aktionsrabatt) 1.000,00 €", zeilen)
        self.assertIn("= Endbetrag 19.000,00 €", zeilen)
        self.assertNotIn("Brutto-Gesamtbetrag", r.text)
        self.assertNotIn("(brutto)", r.text)
        self.assertIn("Abzug vom Gesamtbetrag (nach USt) = Endbetrag", r.text)
        # DB-Box: DB um den vollen Rabatt niedriger (intern)
        self.assertIn("7.000,00 €", r.text)

    def test_editor_19_prozent_darstellung_unveraendert(self):
        a = self.angebot(sparte="WP")
        a.rabatt_cent = 50_000
        self.s.commit()
        r = self.client.get(f"/angebote/{a.id}")
        zeilen = summenblock(r.text)
        self.assertIn("Gesamt-Betrag 23.800,00 €", zeilen)
        self.assertIn("− Rabatt (Aktionsrabatt) 500,00 €", zeilen)
        self.assertIn("= Endbetrag 23.300,00 €", zeilen)

    def test_pdf_0_prozent(self):
        a = self.angebot()
        a.rabatt_prozent = 5.0
        self.s.commit()
        zeilen = pdf_summenzeilen(pdf_export.pdf_fuer_angebot(self.s, a))
        self.assertIn("Netto-Summe € 20.000,00", zeilen)
        self.assertIn("Umsatzsteuer 0 % (§ 12 Abs. 3 UStG) € 0,00", zeilen)
        self.assertIn("Gesamt-Betrag € 20.000,00", zeilen)
        self.assertIn("− Rabatt (Aktionsrabatt) € 1.000,00", zeilen)
        self.assertIn("= Endbetrag € 19.000,00", zeilen)
        self.assertFalse([z for z in zeilen if "brutto" in z.lower()], zeilen)
        a.rabatt_prozent = None
        a.rabatt_cent = 50_000
        self.s.commit()
        zeilen = pdf_summenzeilen(pdf_export.pdf_fuer_angebot(self.s, a))
        self.assertIn("− Rabatt (Aktionsrabatt) € 500,00", zeilen)
        self.assertIn("= Endbetrag € 19.500,00", zeilen)
        # PDF über die Route (Sperre/Rechte) läuft
        self.assertEqual(self.client.get(f"/angebote/{a.id}/pdf").status_code, 200)

    def test_angebotsliste_endbetrag(self):
        a = self.angebot()
        a.rabatt_prozent = 5.0
        self.s.commit()
        r = self.client.get("/angebote?q=V33A+Rabatt")
        self.assertEqual(r.status_code, 200)
        self.assertIn(a.nummer, r.text)
        # Summenzeile der gefilterten Liste: Endbetrag nach Rabatt
        self.assertIn("19.000,00 €", r.text)

    def test_meine_angebote_ad_darstellung(self):
        a = self.angebot()
        a.rabatt_prozent = 5.0
        self.s.commit()
        c = self.ad_client()
        r = c.get("/meine-angebote")
        self.assertEqual(r.status_code, 200)
        self.assertIn("19.000,00 €", r.text)
        r = c.get(f"/meine-angebote/{a.id}")
        self.assertEqual(r.status_code, 200)
        zeilen = summenblock(r.text)
        self.assertIn("Gesamt-Betrag 20.000,00 €", zeilen)
        self.assertIn("− Rabatt (Aktionsrabatt) 1.000,00 €", zeilen)
        self.assertIn("= Endbetrag 19.000,00 €", zeilen)
        self.assertNotIn("(brutto)", r.text)
        self.assertIn("Abzug vom Gesamtbetrag nach USt", r.text)
        self.assertNotIn("Deckungsbeitrag", r.text)     # AD sieht weiterhin keinen DB

    def test_mail_platzhalter_endbetrag(self):
        a = self.angebot()
        a.rabatt_prozent = 5.0
        self.s.commit()
        werte = mail_vorlagen.werte_fuer_angebot(self.s, a, self.kunde)
        self.assertEqual(werte["endbetrag"], "19.000,00 €")
        self.assertEqual((werte["foerderung"], werte["eigenanteil"]), ("", ""))   # PV: kein KfW
        a.rabatt_prozent = None
        a.rabatt_cent = 50_000
        self.assertEqual(mail_vorlagen.werte_fuer_angebot(self.s, a, self.kunde)["endbetrag"],
                         "19.500,00 €")

    def test_monday_deal_wert(self):
        a = self.angebot(status="Versendet")
        a.rabatt_prozent = 5.0
        self.s.commit()
        self.assertEqual(monday_rueckspielung._betrag(a, "brutto"), "19000.00")
        self.assertEqual(monday_rueckspielung._betrag(a, "brutto", self.s), "19000.00")
        self.assertEqual(monday_rueckspielung.vorgangssumme_cent(self.s, a, "brutto"), 1_900_000)
        # Basis „netto“ (Parametrierung je Quelle, im Bestand nicht genutzt): seit dem v33-Nachtrag
        # 15.10.2026 (Entscheidung A-R1) Netto NACH Rabatt (summen()["netto_nach_rabatt"]) –
        # bei 0 % USt also derselbe Wert wie „brutto“
        self.assertEqual(monday_rueckspielung._betrag(a, "netto"), "19000.00")

    def test_statistik_summe_versendet(self):
        von = datetime.now() - timedelta(days=1)
        bis = datetime.now() + timedelta(days=1)
        vorher = statistik.kennzahlen(self.s, von, bis)
        a = self.angebot()
        a.rabatt_prozent = 5.0
        angebot_status_setzen(a, "Versendet")
        self.s.commit()
        nachher = statistik.kennzahlen(self.s, von, bis)
        self.assertEqual(nachher["je_sparte"]["PV"]["summe_versendet"]
                         - vorher["je_sparte"]["PV"]["summe_versendet"], 1_900_000)
        self.assertEqual(nachher["gesamt"]["summe_versendet"] - vorher["gesamt"]["summe_versendet"],
                         1_900_000)
        self.assertEqual(nachher["gesamt"]["db"] - vorher["gesamt"]["db"], NETTO - EK - 100_000)


# --- Routen: Innendienst-Rabatt und AD-Rabatt bei 0 % -------------------------------------

class Routen(Basis):
    def test_rabatt_route_innendienst(self):
        a = self.angebot()
        r = self.client.post(f"/angebote/{a.id}/rabatt",
                             data={"wert": "5", "typ": "prozent", "bezeichnung": "Aktion"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].endswith("?meldung=Rabatt+gespeichert"),
                        r.headers["location"])
        a = self.neu_laden(a.id)
        self.assertEqual((a.rabatt_prozent, a.rabatt_cent, a.rabatt_bezeichnung), (5.0, None, "Aktion"))
        self.assertEqual(a.summen()["endbetrag"], 1_900_000)
        r = self.client.post(f"/angebote/{a.id}/rabatt",
                             data={"wert": "500,00", "typ": "betrag", "bezeichnung": ""},
                             follow_redirects=False)
        self.assertTrue(r.headers["location"].endswith("?meldung=Rabatt+gespeichert"))
        a = self.neu_laden(a.id)
        self.assertEqual((a.rabatt_prozent, a.rabatt_cent), (None, 50_000))
        self.assertEqual(a.summen()["endbetrag"], 1_950_000)
        # ungültig: nichts geändert
        r = self.client.post(f"/angebote/{a.id}/rabatt", data={"wert": "abc", "typ": "betrag"},
                             follow_redirects=False)
        self.assertIn("Ung%C3%BCltiger+Rabattbetrag", r.headers["location"])
        r = self.client.post(f"/angebote/{a.id}/rabatt", data={"wert": "150", "typ": "prozent"},
                             follow_redirects=False)
        self.assertIn("Ung%C3%BCltiger+Prozentwert", r.headers["location"])
        self.assertEqual(self.neu_laden(a.id).rabatt_cent, 50_000)
        # 0 bzw. leer entfernt den Rabatt
        r = self.client.post(f"/angebote/{a.id}/rabatt", data={"wert": "0", "typ": "prozent"},
                             follow_redirects=False)
        self.assertTrue(r.headers["location"].endswith("?meldung=Rabatt+entfernt"))
        a = self.neu_laden(a.id)
        self.assertEqual((a.rabatt_prozent, a.rabatt_cent), (None, None))
        self.assertEqual(a.summen()["endbetrag"], NETTO)
        r = self.client.post(f"/angebote/{a.id}/rabatt", data={"wert": "", "typ": "betrag",
                                                               "bezeichnung": "Notiz"},
                             follow_redirects=False)
        self.assertTrue(r.headers["location"].endswith("?meldung=Rabatt+gespeichert"))
        a = self.neu_laden(a.id)
        self.assertEqual((a.rabatt_prozent, a.rabatt_cent, a.rabatt_bezeichnung), (None, None, "Notiz"))
        self.assertEqual(self.client.get(f"/angebote/{a.id}").status_code, 200)

    def test_rabatt_route_wiederholt_bei_sperre(self):
        """_speichern-Muster: erster Versuch scheitert an einer fremden Schreibsperre
        (6,5 s > busy_timeout), die Wiederholung kommt durch."""
        import sqlite3
        import threading
        import time

        from app import config
        a = self.angebot()
        bereit = threading.Event()

        def sperre():
            v = sqlite3.connect(str(config.DB_PFAD), isolation_level=None, timeout=30)
            try:
                v.execute("BEGIN IMMEDIATE")
                bereit.set()
                time.sleep(6.5)
                v.execute("ROLLBACK")
            finally:
                v.close()
        t = threading.Thread(target=sperre)
        t.start()
        bereit.wait(5)
        start = time.time()
        r = self.client.post(f"/angebote/{a.id}/rabatt", data={"wert": "5", "typ": "prozent"},
                             follow_redirects=False)
        dauer = time.time() - start
        t.join()
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].endswith("?meldung=Rabatt+gespeichert"),
                        r.headers["location"])
        self.assertGreater(dauer, 4.5)
        self.assertEqual(self.neu_laden(a.id).rabatt_prozent, 5.0)

    def test_ad_rabatt_0_prozent(self):
        a = self.angebot(ek=100)                      # DB-Ampel bleibt grün
        c = self.ad_client()
        r = c.post(f"/meine-angebote/{a.id}/rabatt",
                   data={"rabatt_wert": "5", "rabatt_typ": "prozent", "rabatt_bezeichnung": "AD"},
                   follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("übernommen", unquote_plus(r.headers["location"]))
        a = self.neu_laden(a.id)
        self.assertEqual(a.rabatt_prozent, 5.0)
        self.assertEqual(a.summen()["endbetrag"], 1_900_000)
        self.assertEqual(a.deckungsbeitrag()["rabatt"], 100_000)
        r = c.get(f"/meine-angebote/{a.id}")
        self.assertIn("= Endbetrag 19.000,00 €", summenblock(r.text))


# --- angebot_anlegen(commit=False) in der Transaktion des Aufrufers (v30-Nachtrag 22) ------

class AngebotAnlegenOhneCommit(Basis):
    def test_commit_false_bleibt_in_der_transaktion(self):
        s2 = SessionLocal()
        try:
            a = angebot_aufbau.angebot_anlegen(s2, self.kunde.id, sparte="PV", commit=False)
            self.assertIsNotNone(a.id)                         # geflusht, Nummer vergeben
            self.assertTrue(s2.in_transaction())
            nummer = a.nummer
            # andere Sitzung sieht das Angebot nicht (nicht committet)
            self.assertIsNone(self.s.query(Angebot).filter_by(nummer=nummer).first())
            s2.rollback()                                       # z. B. Wiederholung in _speichern
            self.assertIsNone(s2.query(Angebot).filter_by(nummer=nummer).first())
            b = angebot_aufbau.angebot_anlegen(s2, self.kunde.id, sparte="PV", commit=False)
            s2.commit()
            self.s.expire_all()
            self.assertIsNotNone(self.s.query(Angebot).filter_by(nummer=b.nummer).first())
        finally:
            s2.close()

    def test_commit_false_nummernkollision_ueber_savepoint(self):
        """Schreibsitzung (BEGIN IMMEDIATE, wie POST-Routen über _speichern): die Kollision
        wird im SAVEPOINT abgefangen, ein vorher in derselben Transaktion angelegter
        Vorgang überlebt."""
        vorhanden = self.angebot()                              # belegt seine Nummer
        vorgaenge_vorher = self.s.query(Vorgang).filter_by(kunde_id=self.kunde.id).count()
        s2 = db.schreibsitzung()
        try:
            echt = angebot_aufbau.naechste_angebotsnummer(s2)
            self.assertTrue(db.schreibtransaktion_offen())
            s2.add(Vorgang(kunde_id=self.kunde.id))
            s2.flush()
            with mock.patch.object(angebot_aufbau, "naechste_angebotsnummer",
                                   side_effect=[vorhanden.nummer, vorhanden.nummer, echt]):
                a = angebot_aufbau.angebot_anlegen(s2, self.kunde.id, sparte="PV", commit=False)
            self.assertEqual(a.nummer, echt)
            self.assertTrue(s2.in_transaction())
            self.assertTrue(db.schreibtransaktion_offen())      # äußere Transaktion lebt noch
            s2.commit()
            self.s.expire_all()
            self.assertEqual(self.s.query(Angebot).filter_by(nummer=echt).count(), 1)
            self.assertEqual(self.s.query(Angebot).filter_by(nummer=vorhanden.nummer).count(), 1)
            self.assertEqual(self.s.query(Vorgang).filter_by(kunde_id=self.kunde.id).count(),
                             vorgaenge_vorher + 1)
        finally:
            s2.close()

    def test_commit_false_kollision_in_legacy_sitzung(self):
        """Sitzung ohne Schreibkennzeichen (Legacy-Modus, erst das INSERT eröffnet die
        Transaktion): Kollision → rollback + nächste Nummer, Angebot bleibt uncommittet."""
        vorhanden = self.angebot()
        s2 = SessionLocal()
        try:
            echt = angebot_aufbau.naechste_angebotsnummer(s2)
            with mock.patch.object(angebot_aufbau, "naechste_angebotsnummer",
                                   side_effect=[vorhanden.nummer, echt]):
                a = angebot_aufbau.angebot_anlegen(s2, self.kunde.id, sparte="PV", commit=False)
            self.assertEqual(a.nummer, echt)
            self.assertIsNone(self.s.query(Angebot).filter_by(nummer=echt).first())
            s2.commit()
            self.s.expire_all()
            self.assertEqual(self.s.query(Angebot).filter_by(nummer=echt).count(), 1)
        finally:
            s2.close()

    def test_commit_true_wie_bisher(self):
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, sparte="PV")
        self.assertFalse(self.s.in_transaction())              # selbst committet
        self.assertEqual(self.s.execute(text("SELECT count(*) FROM angebote WHERE id = :i"),
                                        {"i": a.id}).scalar(), 1)

    def test_duplizieren_und_kopieren_in_einer_transaktion(self):
        a = self.angebot(status="Versendet")
        a.rabatt_prozent = 5.0
        self.s.commit()
        vorher = self.s.query(Angebot).filter_by(kunde_id=self.kunde.id).count()
        r = self.client.post(f"/angebote/{a.id}/duplizieren", follow_redirects=False)
        self.assertTrue(r.headers["location"].endswith("?meldung=Angebot+dupliziert"),
                        r.headers["location"])
        self.s.expire_all()
        self.assertEqual(self.s.query(Angebot).filter_by(kunde_id=self.kunde.id).count(), vorher + 1)
        dup = self.s.get(Angebot, int(r.headers["location"].split("/angebote/")[1].split("?")[0]))
        self.assertEqual((dup.ust_satz, dup.konfigurator_typ), (0.0, "PV"))
        self.assertEqual(dup.summen()["netto"], NETTO)
        # Duplizieren übernimmt den Gesamtrabatt nicht (wie bisher) – Kopieren schon
        self.assertIsNone(dup.rabatt_prozent)
        r = self.client.post(f"/angebote/{a.id}/kopieren",
                             data={"kunde_suche": "", "neu_nachname": "V33A Kopie-Ziel",
                                   "neu_plz": "47051", "neu_ort": "Duisburg",
                                   "neu_email": TEST_EMAIL},
                             follow_redirects=False)
        self.assertIn("Kopie+von", r.headers["location"])
        kopie = self.s.get(Angebot, int(r.headers["location"].split("/angebote/")[1].split("?")[0]))
        self.assertEqual(kopie.rabatt_prozent, 5.0)
        self.assertEqual(kopie.summen()["endbetrag"], 1_900_000)
        self.assertNotEqual(kopie.kunde_id, self.kunde.id)
        for angebot_id in (a.id, dup.id, kopie.id):
            self.assertEqual(self.s.query(Fehlerprotokoll).filter(
                Fehlerprotokoll.pfad.like(f"/angebote/{angebot_id}/%")).count(), 0)


if __name__ == "__main__":
    unittest.main()
