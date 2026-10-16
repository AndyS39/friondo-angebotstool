# v35-Nachtrag 16.10.2026 (Andreas, drei Punkte): (1) „Meine Termine“ mit Reiter „Vergangene Termine“;
# (2) Erfassungsübersicht des Außendienstes (/erfassung) mit Link in die Vorgangsakte je Erfassung;
# (3) Erfassungen durch den Außendienst löschbar (nur eigene, nicht mit verknüpftem Angebot).
import unittest
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from app import auth
from app.db import SessionLocal
from app.main import app
from app.models import Angebot, Benutzer, Erfassung, Kunde, Vorgang, VotTermin

PRAEFIX = "V35N2"


def _client(benutzer_id: int) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


class MeineTermineUndErfassungen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = SessionLocal()
        try:
            cls._aufraeumen(s)

            def benutzer(name):
                b = Benutzer(name=f"{PRAEFIX} {name}", rolle="aussendienst", aktiv=True,
                             email=f"{name.lower()}@v35n2.local", pin_hash=auth.pin_hash("4321"))
                s.add(b)
                s.flush()
                return b.id

            cls.ad_id = benutzer("Vertrieb")
            cls.fremd_id = benutzer("Fremd")
            kunde = Kunde(anrede="Frau", vorname="Vera", nachname=f"Vergangen{PRAEFIX}", strasse="Altweg 1",
                          plz="47051", ort="Duisburg", telefon="0203 111222", interesse="WP")
            s.add(kunde)
            s.flush()
            cls.kunde_id = kunde.id
            vorgang = Vorgang(kunde_id=kunde.id, lead_phase="erfasst", ad_id=cls.ad_id)
            s.add(vorgang)
            s.flush()
            cls.vorgang_id = vorgang.id
            gestern = datetime.combine(date.today() - timedelta(days=1), datetime.min.time()).replace(hour=10)
            vor_woche = gestern - timedelta(days=6)
            s.add_all([
                VotTermin(vorgang_id=vorgang.id, ad_id=cls.ad_id, beginn=gestern, status="erfolgt",
                          typ="vot", adresse="Altweg 1, 47051 Duisburg"),
                VotTermin(vorgang_id=vorgang.id, ad_id=cls.ad_id, beginn=vor_woche, status="no_show", typ="vot"),
                VotTermin(vorgang_id=vorgang.id, ad_id=cls.fremd_id, beginn=gestern.replace(hour=14),
                          status="erfolgt", typ="vot"),   # fremder Vertriebler – nicht in der Liste
                VotTermin(vorgang_id=vorgang.id, ad_id=cls.ad_id, beginn=gestern.replace(hour=16),
                          status="geplant", typ="sperrzeit"),   # Sperrzeit – nie in der Liste
            ])
            eigene = Erfassung(kunde_id=kunde.id, benutzer_id=cls.ad_id, vorgang_id=vorgang.id,
                               status="Abgesendet", sparte="WP")
            mit_angebot = Erfassung(kunde_id=kunde.id, benutzer_id=cls.ad_id, vorgang_id=vorgang.id,
                                    status="Abgesendet", sparte="PV")
            fremde = Erfassung(kunde_id=kunde.id, benutzer_id=cls.fremd_id, vorgang_id=vorgang.id,
                               status="Abgesendet", sparte="KL")
            s.add_all([eigene, mit_angebot, fremde])
            s.flush()
            angebot = Angebot(nummer=f"AN-{PRAEFIX}-0001", kunde_id=kunde.id, vorgang_id=vorgang.id,
                              vertriebler_id=cls.ad_id, status="Entwurf", datum=date.today(),
                              konfiguration_id=mit_angebot.id)
            s.add(angebot)
            s.flush()
            mit_angebot.angebot_id = angebot.id
            cls.eigene_id, cls.mit_angebot_id, cls.fremde_id_erf = eigene.id, mit_angebot.id, fremde.id
            s.commit()
        finally:
            s.close()

    @classmethod
    def _aufraeumen(cls, s):
        for k in s.query(Kunde).filter(Kunde.nachname.like(f"%{PRAEFIX}")).all():
            vorgang_ids = [v.id for v in s.query(Vorgang).filter(Vorgang.kunde_id == k.id)]
            if vorgang_ids:
                s.query(VotTermin).filter(VotTermin.vorgang_id.in_(vorgang_ids)).delete(synchronize_session=False)
            s.query(Erfassung).filter(Erfassung.kunde_id == k.id).delete(synchronize_session=False)
            s.query(Angebot).filter(Angebot.kunde_id == k.id).delete(synchronize_session=False)
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

    def test_reiter_vergangene_termine(self):
        ad = _client(self.ad_id)
        seite = ad.get("/lead-management/meine-termine?reiter=vergangen")
        self.assertEqual(seite.status_code, 200, seite.text[:300])
        html = seite.text
        self.assertIn('data-rolle="termine-reiter"', html)
        self.assertIn("Vergangene Termine (2)", html)          # erfolgt + No-Show, ohne fremden Termin/Sperrzeit
        self.assertIn(f"Vergangen{PRAEFIX}", html)
        self.assertIn("Erfolgt", html)
        self.assertIn("No-Show", html)
        self.assertIn(f'href="/vorgaenge/{self.vorgang_id}"', html)
        # eigene Erfassung des Vorgangs verlinkt (die mit Angebot bleibt in jeder Testreihenfolge bestehen)
        self.assertIn(f"/erfassung/{self.mit_angebot_id}/pruefen", html)
        self.assertNotIn(f"/erfassung/{self.fremde_id_erf}/pruefen", html)   # fremde Erfassung nicht verlinkt
        # Standard-Reiter zeigt Heute/Woche – die vergangenen Termine nicht
        aktuell = ad.get("/lead-management/meine-termine").text
        self.assertIn('data-rolle="termine-reiter"', aktuell)
        self.assertNotIn('data-rolle="vergangene-termine"', aktuell)
        # fremder Vertriebler sieht nur seinen eigenen vergangenen Termin
        fremd = _client(self.fremd_id).get("/lead-management/meine-termine?reiter=vergangen").text
        self.assertIn("Vergangene Termine (1)", fremd)

    def test_erfassungsuebersicht_mit_akte_link_und_loeschen(self):
        ad = _client(self.ad_id)
        html = ad.get("/erfassung").text
        self.assertIn(f'href="/vorgaenge/{self.vorgang_id}"', html)
        self.assertIn(f'action="/erfassung/{self.eigene_id}/loeschen"', html)
        self.assertNotIn(f'action="/erfassung/{self.mit_angebot_id}/loeschen"', html)   # Angebot verknüpft
        # Vorgangsakte aus der Übersicht erreichbar
        self.assertEqual(ad.get(f"/vorgaenge/{self.vorgang_id}").status_code, 200)

    def test_loeschen_regeln(self):
        ad = _client(self.ad_id)
        # mit Angebot: gesperrt
        r = ad.post(f"/erfassung/{self.mit_angebot_id}/loeschen")
        self.assertEqual(r.status_code, 303)
        self.assertIn("Angebot", r.headers["location"])
        # fremde Erfassung: gesperrt
        r = ad.post(f"/erfassung/{self.fremde_id_erf}/loeschen")
        self.assertEqual(r.status_code, 303)
        self.assertIn("eigene", r.headers["location"])
        s = SessionLocal()
        try:
            self.assertIsNotNone(s.get(Erfassung, self.mit_angebot_id))
            self.assertIsNotNone(s.get(Erfassung, self.fremde_id_erf))
        finally:
            s.close()
        # eigene ohne Angebot: gelöscht, Meldung auf der Übersicht
        r = ad.post(f"/erfassung/{self.eigene_id}/loeschen")
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/erfassung?meldung="))
        s = SessionLocal()
        try:
            self.assertIsNone(s.get(Erfassung, self.eigene_id))
        finally:
            s.close()
        self.assertIn("gelöscht", ad.get(r.headers["location"]).text)


if __name__ == "__main__":
    unittest.main()
