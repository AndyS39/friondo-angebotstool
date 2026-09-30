# Regressionstests zur Fehlersuche vom 30.09.2026 (Daten im neuen Format):
# Anschriften (Standard darf versendete Angebote nicht ändern, Erfassung
# gewinnt, Zusatz behält den Ansprechpartner), Version/Duplikat behalten die
# Positions-Kennzeichen, Zahleneingabe ohne inf/nan, robuste Lead-Daten
# (Wunschzeiten, API mit Zahlen, Budget im deutschen Format), storniertes
# Gewerk ohne Auftragsdaten-Absturz, Dubletten ohne Mischanschrift.
import json
import unittest
import warnings

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, anschriften
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Erfassung, Kampagne, Kunde,
                        LeadAktivitaet, LeadQuelle, Vorgang, angebot_status_setzen)

TEST_EMAIL = "sweep-0930@test.local"


def aufraeumen(s):
    import tests.test_projektierung_v4 as v4
    alt, v4.TEST_EMAIL = v4.TEST_EMAIL, TEST_EMAIL
    try:
        v4.aufraeumen(s)
    finally:
        v4.TEST_EMAIL = alt
    for k in s.query(Kunde).filter(Kunde.nachname.like("Sweep-0930%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        for modell in (Angebot, Erfassung):
            for o in s.query(modell).filter(modell.kunde_id == k.id):
                s.delete(o)
        s.delete(k)
    s.query(Kampagne).filter(Kampagne.name.like("sweep-0930%")).delete()
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def kunde(self, nr, **extra):
        k = Kunde(anrede="Herr", vorname="Max", nachname=f"Sweep-0930-{nr}",
                  strasse="Musterstraße 5", plz="47051", ort="Duisburg",
                  email=TEST_EMAIL, **extra)
        self.s.add(k)
        self.s.commit()
        return k


class Anschriften(Basis):
    def test_standard_aendert_bestehende_angebote_nicht(self):
        k = self.kunde(1)
        a = angebot_aufbau.angebot_anlegen(self.s, k.id)
        angebot_status_setzen(a, "Versendet")
        self.s.commit()
        vorher = (anschriften.empfaenger(a, k), anschriften.lieferzeile(a, k),
                  anschriften.zeilen(anschriften.lieferung(a, k)))
        k.rechnung_name, k.rechnung_strasse = "Neue Rechnungs GmbH", "Rechnungsweg 9"
        k.rechnung_plz, k.rechnung_ort = "40210", "Düsseldorf"
        k.liefer_name, k.liefer_strasse, k.liefer_plz, k.liefer_ort = (
            "Lager Nord", "Lagerweg 1", "47138", "Duisburg")
        self.s.commit()
        self.assertEqual(vorher, (anschriften.empfaenger(a, k), anschriften.lieferzeile(a, k),
                                  anschriften.zeilen(anschriften.lieferung(a, k))))
        # neue manuelle Angebote übernehmen den Standard
        neu = angebot_aufbau.angebot_anlegen(self.s, k.id)
        self.assertEqual((neu.rechnung_name, neu.liefer_strasse),
                         ("Neue Rechnungs GmbH", "Lagerweg 1"))
        # die Akte zeigt den Standard weiterhin
        self.assertEqual(anschriften.standard_rechnung(k)["strasse"], "Rechnungsweg 9")

    def test_erfassung_gewinnt_gegen_standard(self):
        from types import SimpleNamespace
        k = self.kunde(2, rechnung_name="Standard GmbH", rechnung_strasse="Stdweg 1",
                       rechnung_plz="40210", rechnung_ort="Düsseldorf",
                       liefer_name="Lager", liefer_strasse="Lagerweg 1",
                       liefer_plz="47138", liefer_ort="Duisburg")
        leer = lambda: SimpleNamespace(**{f"{p}_{f}": "" for p in ("rechnung", "liefer")
                                          for f in anschriften.FELDER}, liefer_anschrift="")
        a = leer()   # WP-Bogen: O06 = Ja, O13 leer → kein Standard
        anschriften.angebot_vorbelegen(a, k, {"O06": "Ja", "O13": ""})
        self.assertEqual((a.rechnung_name, a.liefer_strasse), ("", ""))
        a = leer()   # Bogen ohne diese Fragen (PV) → Standard
        anschriften.angebot_vorbelegen(a, k, {"PB01": "Maximalbelegung"})
        self.assertEqual((a.rechnung_name, a.liefer_strasse), ("Standard GmbH", "Lagerweg 1"))
        a = leer()   # unveränderte O13-Vorbelegung → exakt die Standard-Felder
        anschriften.angebot_vorbelegen(a, k, {"O06": "Ja",
                                              "O13": anschriften.erfassung_vorbelegung(k)["O13"]})
        self.assertEqual((a.liefer_name, a.liefer_strasse, a.liefer_plz),
                         ("Lager", "Lagerweg 1", "47138"))

    def test_zusatz_behaelt_ansprechpartner(self):
        k = self.kunde(3, firma="Varianten GmbH")
        a = angebot_aufbau.angebot_anlegen(self.s, k.id)
        a.rechnung_zusatz = "Abteilung Technik"
        zeilen, abw = anschriften.empfaenger(a, k)
        self.assertEqual(zeilen, ["Varianten GmbH", "Herr Max Sweep-0930-3", "Abteilung Technik",
                                  "Musterstraße 5", "47051 Duisburg"])
        self.assertFalse(abw)

    def test_kunde_ohne_adresse_und_lange_anschrift(self):
        import io

        import pypdf

        from app import pdf_export
        k = Kunde(anrede="Herr", vorname="Ohne", nachname="Sweep-0930-4", email=TEST_EMAIL)
        self.s.add(k)
        self.s.commit()
        a = angebot_aufbau.angebot_anlegen(self.s, k.id)
        a.positionen.append(AngebotsPosition(sort=1, pos_nr="047", bezeichnung="WP",
                                             beschreibung="WP", menge=1, e_preis_cent=100000))
        a.rechnung_name = "Sehr lange Firma " * 8
        a.rechnung_zusatz = "Zusatzzeile " * 12
        a.rechnung_strasse, a.rechnung_plz, a.rechnung_ort = "Rechnungsweg 1", "12345", "Stadt"
        angebot_status_setzen(a, "Angenommen")
        self.s.commit()
        seite = pypdf.PdfReader(str(pdf_export.pdf_fuer_angebot(self.s, a))).pages[0]
        text = seite.extract_text()
        self.assertNotIn("Ausführungsort:", text)          # Kunde ohne Adresse
        self.assertLess(text.find("Rechnungsweg 1"), text.find("A N G E B O T"))
        ls = self.client.get(f"/angebote/{a.id}/lieferschein.pdf")
        ls_text = pypdf.PdfReader(io.BytesIO(ls.content)).pages[0].extract_text()
        self.assertNotIn("Ausführungsort:", ls_text)


class Positionen(Basis):
    def _angebot(self, nr):
        k = self.kunde(nr)
        a = angebot_aufbau.angebot_anlegen(self.s, k.id)
        for i, extra in enumerate(({"alternativ": True}, {"bauseits": True},
                                   {"rabatt_prozent": 10.0}, {}), 1):
            a.positionen.append(AngebotsPosition(sort=i, pos_nr=f"90{i}", bezeichnung=f"P{i}",
                                                 beschreibung=f"P{i}", menge=1,
                                                 e_preis_cent=100000, **extra))
        self.s.commit()
        return a

    def test_version_und_duplikat_behalten_kennzeichen(self):
        a = self._angebot(5)
        summe = a.summen()["endbetrag"]
        angebot_status_setzen(a, "Versendet")
        self.s.commit()
        self.client.post(f"/angebote/{a.id}/duplizieren")
        self.client.post(f"/angebote/{a.id}/ueberarbeiten")
        self.s.expire_all()
        version = self.s.query(Angebot).filter(Angebot.vorgaenger_id == a.id).one()
        self.assertEqual(version.summen()["endbetrag"], summe)
        self.assertEqual([bool(p.alternativ) for p in version.positionen],
                         [True, False, False, False])
        duplikat = (self.s.query(Angebot)
                    .filter(Angebot.kunde_id == a.kunde_id, Angebot.id != a.id,
                            Angebot.id != version.id).order_by(Angebot.id.desc()).first())
        self.assertEqual(duplikat.summen()["endbetrag"], summe)
        self.assertEqual([(bool(p.alternativ), bool(p.bauseits), p.rabatt_prozent or 0)
                          for p in duplikat.positionen],
                         [(True, False, 0), (False, True, 0), (False, False, 10.0), (False, False, 0)])


class Eingaben(Basis):
    def test_zahl_parsen_nur_endliche_zahlen(self):
        from app.konfigurator import zahl_parsen
        for wert in ("inf", "-inf", "nan", "1e400", float("inf"), float("nan")):
            self.assertIsNone(zahl_parsen(wert), wert)
        self.assertEqual(zahl_parsen("8.000"), 8000.0)
        self.assertEqual(zahl_parsen("12,5"), 12.5)

    def test_budget_deutsches_format(self):
        r = self.client.post("/parametrierung/lead-quellen",
                             data={"art": "kampagne", "name": "sweep-0930-kampagne",
                                   "budget": "1.500,00"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        self.assertEqual(self.s.query(Kampagne).filter_by(name="sweep-0930-kampagne")
                         .one().budget_cent, 150000)


class Lead(Basis):
    def test_kaputte_wunschzeiten_und_api_mit_zahlen(self):
        import secrets

        from app import lead_anrufliste, leadmanagement as kern
        quelle = self.s.query(LeadQuelle).filter_by(key="website").one()
        quelle.api_key = quelle.api_key or secrets.token_hex(8)
        self.s.commit()
        # Agentur sendet PLZ/Telefon als Zahl, Sparten als Text
        r = self.client.post("/api/leads", headers={"X-Api-Key": quelle.api_key},
                             json={"nachname": "Sweep-0930-Lead", "plz": 47139,
                                   "telefon": 2039955001, "sparten": "wp, PV",
                                   "wunschzeiten": 5})
        self.assertIn(r.status_code, (201, 409), r.text)
        v = self.s.get(Vorgang, r.json()["vorgang_id"])
        self.assertEqual(self.s.get(Kunde, v.kunde_id).plz, "47139")
        # ein Datensatz mit kaputten Wunschzeiten darf die Liste nicht kippen
        for kaputt in ("5", '"abends"', "{kaputt", '{"a": 1}'):
            v.wunschzeiten = kaputt
            self.s.commit()
            kern.wunschzeiten_liste(v)
            d = lead_anrufliste.daten(self.s, None, lead_anrufliste.filter_aus_query({"meine": "0"}))
            self.assertGreaterEqual(d["offen"], 1)
            self.assertEqual(self.client.get("/lead-management/anrufliste?meine=0").status_code, 200)
            self.assertEqual(self.client.get(f"/vorgaenge/{v.id}").status_code, 200)
            self.assertLess(self.client.get(f"/lead-management/lead/{v.id}/termin").status_code, 500)
        # ungültige Filterwerte in der URL
        for url in ("/lead-management/board?quelle_id=abc",
                    "/lead-management/statistik?quelle_id=abc&kampagne_id=x&leadmanager_id=x&ad_id=x",
                    "/lead-management/anrufliste?meine=0&versuche=x&eingang_von=kaputt"):
            self.assertEqual(self.client.get(url).status_code, 200, url)


class Projektierung(Basis):
    def test_auftragsdaten_storniertes_gewerk(self):
        from datetime import datetime

        from app import projektierung as kern
        k = self.kunde(7)
        a = Angebot(nummer="EXT-sweep", kunde_id=k.id, extern=True, taifun_nummer="AN26SW01",
                    extern_endbetrag_cent=2000000, datum=datetime.now(), konfigurator_typ="WP")
        self.s.add(a)
        self.s.flush()
        a.nummer = f"EXT-{a.id}"
        angebot_status_setzen(a, "Angenommen")
        self.s.commit()
        projekt = kern.projekt_anlegen(self.s, a, projektleiter_id=1)
        gewerk = kern.gewerk_anlegen(self.s, projekt, a, "WP")
        gewerk.phase = "storniert"
        self.s.commit()
        r = self.client.get(f"/projektierung/gewerk/{gewerk.id}/auftragsdaten",
                            follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn(f"/projektierung/projekt/{projekt.id}", r.headers["location"])


class Dubletten(Basis):
    def test_keine_mischanschrift(self):
        from app import kunden_dubletten
        from app.models import einstellung_holen, einstellung_setzen
        protokoll = einstellung_holen(self.s, kunden_dubletten.PROTOKOLL, "")
        a = Kunde(vorname="Mia", nachname="Sweep-0930-Dub", plz="47139", strasse="Weg 1",
                  rechnung_name="Nur Name GmbH")
        b = Kunde(vorname="Mia", nachname="Sweep-0930-Dub", plz="47139", strasse="Weg 1",
                  rechnung_name="Andere GmbH", rechnung_strasse="Anderer Weg 9",
                  rechnung_plz="40210", rechnung_ort="Düsseldorf",
                  liefer_strasse="Lagerweg 1", liefer_plz="47138", liefer_ort="Duisburg")
        self.s.add_all([a, b])
        self.s.commit()
        a_id = a.id
        kunden_dubletten.zusammenfuehren(self.s, a.id, [b.id])
        einstellung_setzen(self.s, kunden_dubletten.PROTOKOLL, protokoll)
        self.s.commit()
        a = self.s.get(Kunde, a_id)
        # Rechnung: Hauptdatensatz hatte schon Werte → Gruppe bleibt unverändert
        self.assertEqual((a.rechnung_name, a.rechnung_strasse), ("Nur Name GmbH", ""))
        # Lieferung: beim Hauptdatensatz leer → als ganze Gruppe übernommen
        self.assertEqual((a.liefer_strasse, a.liefer_plz, a.liefer_ort),
                         ("Lagerweg 1", "47138", "Duisburg"))


if __name__ == "__main__":
    unittest.main()
