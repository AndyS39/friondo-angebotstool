# v32 (PLAN_V19 Phase 164): Allgemeine Kundensuche im Hauptmenü.
# „Mül“ findet „Müller“, „Peter M“ findet „Peter Müller“, „Krefeld“ findet Kunden in
# Krefeld, „4711“ findet +49 203 … 4711; Außendienst findet fremde Kunden nicht;
# Montage (und Projektierung) erhalten 403; Treffer enthalten keine EK-/DB-Felder;
# Antwortzeit unter 300 ms; Suchfeld in der Kopfzeile (nicht auf Login, nicht
# eingebettet, nicht im Erfassungsbogen); Trefferseite /suche.
import statistics
import time
import unittest

from fastapi.testclient import TestClient

from app import auth, suche
from app.db import SessionLocal
from app.main import app
from app.models import Benutzer, Kunde, Vorgang

PRAEFIX = "V32S"
ERLAUBTE_FELDER = {"kunde_id", "name", "vorname", "nachname", "firma", "plz", "ort",
                   "sparten", "verfolgung", "verfolgung_text", "vorgang_id", "link"}


def _client(benutzer_id: int) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


class SucheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = SessionLocal()
        try:
            cls._aufraeumen(s)

            def benutzer(name, rolle):
                b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                             email=f"{name.lower().replace(' ', '')}@v32.local",
                             pin_hash=auth.pin_hash("4321"))
                s.add(b)
                s.flush()
                return b.id

            cls.ad_id = benutzer("Aussendienst", "aussendienst")
            cls.ad2_id = benutzer("Aussendienst Zwei", "aussendienst")
            cls.montage_id = benutzer("Montage", "montage")
            cls.projektierung_id = benutzer("Projektierung", "projektierung")

            mueller = Kunde(anrede="Herr", vorname="Peter", nachname=f"Müller{PRAEFIX}",
                            strasse="Testweg 1", plz="47798", ort=f"Krefeld{PRAEFIX}",
                            telefon="+49 203 555 4711", interesse="WP,PV")
            schmidt = Kunde(anrede="Frau", vorname="Anna", nachname=f"Schmidt{PRAEFIX}",
                            strasse="Testweg 2", plz="47051", ort="Duisburg",
                            telefon="0203 9999 1234", interesse="KL")
            ohne = Kunde(anrede="Herr", vorname="Olaf", nachname=f"Ohnevorgang{PRAEFIX}",
                         plz="47051", ort="Duisburg", telefon="", interesse="")
            s.add_all([mueller, schmidt, ohne])
            s.flush()
            cls.mueller_id, cls.schmidt_id, cls.ohne_id = mueller.id, schmidt.id, ohne.id
            v1 = Vorgang(kunde_id=mueller.id, lead_phase="neu", ad_id=cls.ad_id,
                         verfolgung_status="bestellung_angekuendigt")
            v2 = Vorgang(kunde_id=schmidt.id, lead_phase="neu", ad_id=cls.ad2_id)
            s.add_all([v1, v2])
            s.flush()
            cls.v1_id, cls.v2_id = v1.id, v2.id
            s.commit()
        finally:
            s.close()
        cls.admin = _client(1)

    @classmethod
    def _aufraeumen(cls, s):
        kunden = s.query(Kunde).filter(Kunde.nachname.like(f"%{PRAEFIX}")).all()
        for k in kunden:
            s.query(Vorgang).filter(Vorgang.kunde_id == k.id).delete(synchronize_session=False)
            s.delete(k)
        s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX} %")).delete(synchronize_session=False)
        s.commit()

    @classmethod
    def tearDownClass(cls):
        s = SessionLocal()
        try:
            cls._aufraeumen(s)
        finally:
            s.close()

    # --- JSON-Route -------------------------------------------------------------
    def _json(self, client, q):
        antwort = client.get("/suche.json", params={"q": q}, headers={"Accept": "application/json"})
        self.assertEqual(antwort.status_code, 200, antwort.text[:200])
        daten = antwort.json()
        self.assertTrue(daten["ok"])
        return daten["treffer"]

    def _ids(self, treffer):
        return [t["kunde_id"] for t in treffer]

    def test_mindestens_zwei_zeichen(self):
        self.assertEqual(self._json(self.admin, "M"), [])
        self.assertEqual(self._json(self.admin, " "), [])

    def test_nachname_vorname_nachname_ort_endziffern(self):
        self.assertIn(self.mueller_id, self._ids(self._json(self.admin, "Mül")))
        self.assertIn(self.mueller_id, self._ids(self._json(self.admin, "Peter M")))
        self.assertIn(self.mueller_id, self._ids(self._json(self.admin, f"Krefeld{PRAEFIX}")))
        self.assertIn(self.mueller_id, self._ids(self._json(self.admin, "4711")))
        self.assertNotIn(self.schmidt_id, self._ids(self._json(self.admin, "4711")))
        # Schreibweise egal, auch komplette Rufnummer
        self.assertIn(self.mueller_id, self._ids(self._json(self.admin, "mül")))
        self.assertIn(self.mueller_id, self._ids(self._json(self.admin, "0203 555 4711")))
        # weniger als vier Ziffern: keine Rufnummernsuche
        self.assertEqual(self._json(self.admin, "471"), [])

    def test_hoechstens_acht_vorschlaege_und_rang(self):
        treffer = self._json(self.admin, "Mü")
        self.assertLessEqual(len(treffer), suche.MAX_VORSCHLAEGE)
        # Nachname-Treffer kommen vor Ort-Treffern
        treffer = self._json(self.admin, PRAEFIX.lower())
        self.assertEqual(treffer, [], "Präfix ist kein Wortanfang – keine Treffer")

    def test_trefferinhalt_ohne_ek_db(self):
        treffer = self._json(self.admin, "Mül")
        t = next(x for x in treffer if x["kunde_id"] == self.mueller_id)
        self.assertEqual(set(t.keys()), ERLAUBTE_FELDER)
        self.assertEqual(t["name"], f"Müller{PRAEFIX}, Peter")
        self.assertEqual(t["sparten"], ["WP", "PV"])
        self.assertEqual(t["verfolgung_text"], "Bestellung angekündigt")
        self.assertEqual(t["link"], f"/vorgaenge/{self.v1_id}")
        for verboten in ("ek", "db", "preis", "marge", "einkauf"):
            self.assertFalse(any(verboten in k.lower() for k in t.keys()), verboten)

    def test_link_kundenakte_ohne_offenen_vorgang(self):
        treffer = self._json(self.admin, f"Ohnevorgang{PRAEFIX}")
        t = next(x for x in treffer if x["kunde_id"] == self.ohne_id)
        self.assertEqual(t["link"], f"/kunden/{self.ohne_id}/bearbeiten")
        self.assertIsNone(t["vorgang_id"])

    def test_aussendienst_nur_eigene_kunden(self):
        ad = _client(self.ad_id)
        self.assertIn(self.mueller_id, self._ids(self._json(ad, "Mül")))
        self.assertNotIn(self.schmidt_id, self._ids(self._json(ad, "Schmidt")))
        self.assertNotIn(self.ohne_id, self._ids(self._json(ad, "Ohnevorgang")))
        self.assertEqual(self._ids(self._json(ad, "1234")), [])
        ad2 = _client(self.ad2_id)
        self.assertIn(self.schmidt_id, self._ids(self._json(ad2, "Schmidt")))
        self.assertNotIn(self.mueller_id, self._ids(self._json(ad2, "Mül")))

    def test_montage_und_projektierung_403(self):
        for benutzer_id in (self.montage_id, self.projektierung_id):
            c = _client(benutzer_id)
            antwort = c.get("/suche.json", params={"q": "Mül"}, headers={"Accept": "application/json"})
            self.assertEqual(antwort.status_code, 403, benutzer_id)
            self.assertFalse(antwort.json()["ok"])
            seite = c.get("/suche", params={"q": "Mül"})
            self.assertEqual(seite.status_code, 403, benutzer_id)
            self.assertNotIn(f"Müller{PRAEFIX}", seite.text)

    def test_ohne_anmeldung_umleitung(self):
        c = TestClient(app, follow_redirects=False)
        self.assertEqual(c.get("/suche.json", params={"q": "Mül"}).status_code, 303)

    def test_antwortzeit_unter_300_ms(self):
        self._json(self.admin, "Mül")   # Aufwärmen
        zeiten = []
        for q in ("Mül", "Peter M", "Krefeld", "4711", "Mül"):
            start = time.perf_counter()
            self._json(self.admin, q)
            zeiten.append((time.perf_counter() - start) * 1000)
        median = statistics.median(zeiten)
        print(f"\nSuche: Median {median:.0f} ms, Maximum {max(zeiten):.0f} ms (Dev-Datenbank)")
        self.assertLess(median, 300, zeiten)

    # --- Trefferseite und Kopfzeile ----------------------------------------------
    def test_trefferseite(self):
        antwort = self.admin.get("/suche", params={"q": "Mül"})
        self.assertEqual(antwort.status_code, 200)
        self.assertIn(f"Müller{PRAEFIX}, Peter", antwort.text)
        self.assertIn(f"/vorgaenge/{self.v1_id}", antwort.text)
        self.assertIn("Bestellung angekündigt", antwort.text)
        self.assertIn('class="zurueck-leiste"', antwort.text)
        leer = self.admin.get("/suche", params={"q": "Zzzzqqq"})
        self.assertEqual(leer.status_code, 200)
        self.assertIn("Keine Treffer", leer.text)
        kurz = self.admin.get("/suche", params={"q": "M"})
        self.assertEqual(kurz.status_code, 200)
        self.assertIn("mindestens zwei Zeichen", kurz.text)

    def test_suchfeld_in_der_kopfzeile(self):
        start = self.admin.get("/")
        self.assertEqual(start.status_code, 200)
        self.assertIn('class="kopf-suche"', start.text)
        self.assertIn("Kunde suchen …", start.text)
        self.assertIn("/static/suche.js", start.text)
        self.assertIn("/static/suche.css", start.text)
        self.assertIn('data-suche-json="/suche.json"', start.text)
        # eingebettet (Anrufliste-Panel) und Login ohne Suchfeld
        self.assertNotIn('class="kopf-suche"', self.admin.get("/?einbett=1").text)
        login = TestClient(app, follow_redirects=False).get("/login")
        self.assertEqual(login.status_code, 200)
        self.assertNotIn('class="kopf-suche"', login.text)
        # Außendienst: Startseite mit Suchfeld, Erfassungsbogen ohne
        ad = _client(self.ad_id)
        erfassung = ad.get("/erfassung")
        self.assertEqual(erfassung.status_code, 200)
        self.assertIn('class="kopf-suche"', erfassung.text)
        # v33 (PLAN_V20 Phase 173, Protokoll A.5): untere Leiste des Außendienstes (mobil);
        # v38 (PLAN_V23 Phase 204): der Eintrag „Kunden“ ist durch „Vergangene Termine“ ersetzt –
        # die Suche bleibt über die Lupe der Kopfzeile erreichbar; Innendienst/Montage ohne Leiste
        self.assertIn('class="mt-leiste"', erfassung.text)
        self.assertNotIn("data-mt-leiste-kunden", erfassung.text)
        self.assertIn('href="/leads/vergangene"', erfassung.text)
        self.assertNotIn("Kunden</a>", erfassung.text)
        self.assertNotIn("mt-leiste", self.admin.get("/").text)
        # Montage: kein Suchfeld
        montage = _client(self.montage_id).get("/montage")
        self.assertEqual(montage.status_code, 200)
        self.assertNotIn('class="kopf-suche"', montage.text)

    def test_suchlogik_direkt(self):
        s = SessionLocal()
        try:
            admin = s.get(Benutzer, 1)
            treffer = suche.suchen(s, "Peter Mül", admin, limit=3)
            self.assertTrue(any(t["kunde_id"] == self.mueller_id for t in treffer))
            self.assertLessEqual(len(treffer), 3)
            self.assertTrue(suche.ist_rufnummer("+49 203 4711"))
            self.assertFalse(suche.ist_rufnummer("Müller 4711"))
            self.assertFalse(suche.ist_rufnummer("471"))
        finally:
            s.close()


if __name__ == "__main__":
    unittest.main()
