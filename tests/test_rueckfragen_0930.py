# Tests zu den Antworten auf die Rückfragen vom 30.09.2026:
# Kunden-Dubletten zusammenführen, BzA-Kundenmail per Häkchen, Standard-Sub je
# Typ in der Go-live-Checkliste, Standard-Anschriften auch für den Außendienst.
# Räumt Kunden mit rueckfragen-0930@test.local auf.
import json
import unittest
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau
from app import projektierung as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Benutzer, Erfassung, Kunde,
                        Subunternehmer, Vorgang, angebot_status_setzen,
                        einstellung_holen, einstellung_setzen)

TEST_EMAIL = "rueckfragen-0930@test.local"


def aufraeumen(s):
    import tests.test_projektierung_v4 as v4
    alt, v4.TEST_EMAIL = v4.TEST_EMAIL, TEST_EMAIL
    try:
        v4.aufraeumen(s)
    finally:
        v4.TEST_EMAIL = alt
    for k in s.query(Kunde).filter(Kunde.nachname.like("Dublette-0930%")):
        for modell in (Angebot, Erfassung, Vorgang):
            s.query(modell).filter(modell.kunde_id == k.id).delete()
        s.delete(k)
    s.query(Subunternehmer).filter(Subunternehmer.firma.like("Test-Sub-0930%")).delete()
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


class Dubletten(Basis):
    def setUp(self):
        from app import kunden_dubletten
        self.protokoll_vorher = einstellung_holen(self.s, kunden_dubletten.PROTOKOLL, "")

    def tearDown(self):
        from app import kunden_dubletten
        einstellung_setzen(self.s, kunden_dubletten.PROTOKOLL, self.protokoll_vorher)
        self.s.commit()

    def test_gruppen_und_zusammenfuehren(self):
        from app import kunden_dubletten
        a = Kunde(anrede="Herr", vorname="Dieter", nachname="Dublette-0930", plz="47139",
                  strasse="Hafenstr. 1", ort="Duisburg", interesse="WP")
        b = Kunde(anrede="Herr", vorname="Dieter", nachname="Dublette-0930", plz="47139",
                  strasse="Hafenstraße 1", telefon="0203 1", email="d@test.local",
                  interesse="PV", notizen="aus monday")
        c = Kunde(vorname="Dora", nachname="Dublette-0930-anders", plz="47139")
        self.s.add_all([a, b, c])
        self.s.commit()
        a_id, b_id = a.id, b.id
        angebot = angebot_aufbau.angebot_anlegen(self.s, b.id)
        self.s.add(Erfassung(kunde_id=b.id, benutzer_id=1, sparte="PV", status="Entwurf"))
        self.s.add(Vorgang(kunde_id=b.id))
        self.s.commit()
        gruppe = next(g for g in kunden_dubletten.gruppen(self.s)
                      if any(e["kunde"].id == a.id for e in g["kunden"]))
        self.assertEqual(gruppe["vorschlag"], a.id)                   # ältester
        self.assertEqual({e["kunde"].id for e in gruppe["kunden"]}, {a.id, b.id})
        self.assertFalse(gruppe["strasse_abweichend"])                 # Str./Straße gleich
        seite = self.client.get("/parametrierung/kunden-dubletten")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Dublette-0930", seite.text)
        antwort = self.client.post("/parametrierung/kunden-dubletten",
                                   data={"haupt_id": str(a.id), "dublette_id": [str(b.id)]},
                                   follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        self.s.expire_all()
        self.assertIsNone(self.s.get(Kunde, b_id))
        a = self.s.get(Kunde, a_id)
        self.assertEqual((a.telefon, a.email, a.strasse), ("0203 1", "d@test.local", "Hafenstr. 1"))
        self.assertEqual(set(a.interesse.split(",")), {"WP", "PV"})
        self.assertIn("aus monday", a.notizen)
        self.assertEqual(self.s.get(Angebot, angebot.id).kunde_id, a.id)
        self.assertEqual(self.s.query(Erfassung).filter_by(kunde_id=a.id).count(), 1)
        self.assertIn(f"#{b_id} → #{a_id}",
                      einstellung_holen(self.s, kunden_dubletten.PROTOKOLL, ""))
        # anderer Kunde (anderer Vorname) bleibt unberührt, Fremdgruppe abgewiesen
        self.assertIsNotNone(self.s.get(Kunde, c.id))
        with self.assertRaises(ValueError):
            kunden_dubletten.zusammenfuehren(self.s, a.id, [c.id])
        self.s.rollback()

    def test_strasse_abweichend_nicht_vorausgewaehlt(self):
        from app import kunden_dubletten
        a = Kunde(vorname="Egon", nachname="Dublette-0930-Str", plz="47051", strasse="A-Weg 1")
        b = Kunde(vorname="Egon", nachname="Dublette-0930-Str", plz="47051", strasse="B-Weg 9")
        self.s.add_all([a, b])
        self.s.commit()
        gruppe = next(g for g in kunden_dubletten.gruppen(self.s)
                      if any(e["kunde"].id == a.id for e in g["kunden"]))
        self.assertTrue(gruppe["strasse_abweichend"])
        seite = self.client.get("/parametrierung/kunden-dubletten").text
        self.assertIn("Straße abweichend", seite)


class BzaMail(Basis):
    def setUp(self):
        self.vorher = kern.parameter_holen(self.s, "bza_mail_aktiv", "")

    def tearDown(self):
        kern.parameter_setzen(self.s, "bza_mail_aktiv", self.vorher or "an")
        self.s.commit()

    def _gewerk(self):
        from tests.test_projektierung_v4 import Basis as V4
        import tests.test_projektierung_v4 as v4
        alt, v4.TEST_EMAIL = v4.TEST_EMAIL, TEST_EMAIL
        try:
            return V4.gewerk_neu(self, kfw={"O01": "EFH", "K01": "Ja"})
        finally:
            v4.TEST_EMAIL = alt

    def test_haekchen_aus_erledigt_ohne_mail(self):
        import io

        from app import bza
        from app.models import Aufgabe
        gewerk = self._gewerk()
        # Einstellung per Formular abschalten
        self.client.post("/parametrierung/projektierung-einstellungen",
                         data={"bza_mail_dabei": "1", "freigabe_modus": kern.freigabe_modus(self.s)})
        self.s.expire_all()
        self.assertFalse(bza.mail_aktiv(self.s))
        akte = self.client.get(f"/projektierung/projekt/{gewerk.projekt_id}").text
        self.assertIn("Die BzA-Kundenmail ist abgeschaltet", akte)
        pdf = b"%PDF-1.4\n%%EOF\n"
        self.client.post(f"/projektierung/gewerk/{gewerk.id}/bza-erfassen",
                         data={"bza_id": "BZA-0930", "datum": "2026-09-30", "sofort_senden": "on"},
                         files={"datei": ("bza.pdf", io.BytesIO(pdf), "application/pdf")},
                         follow_redirects=False)
        self.s.expire_all()
        bza_aufgaben = (self.s.query(Aufgabe).filter(Aufgabe.gewerk_id == gewerk.id,
                                                     Aufgabe.aktion_typ == "bza",
                                                     Aufgabe.aktion_wert != "kfw").all())
        self.assertTrue(bza_aufgaben)
        self.assertTrue(all(a.status == "erledigt" for a in bza_aufgaben))
        ok, meldung = bza.mail_senden(self.s, self.s.get(type(gewerk), gewerk.id), "B", "T")
        self.assertFalse(ok)
        self.assertIn("abgeschaltet", meldung)
        # wieder an: Standard, Einstellungsseite zeigt das Häkchen
        self.client.post("/parametrierung/projektierung-einstellungen",
                         data={"bza_mail_dabei": "1", "bza_mail_aktiv": "on",
                               "freigabe_modus": kern.freigabe_modus(self.s)})
        self.s.expire_all()
        self.assertTrue(bza.mail_aktiv(self.s))
        self.assertIn('name="bza_mail_aktiv"', self.client.get(
            "/parametrierung/projektierung-einstellungen").text)

    def test_ohne_mail_abschliessen(self):
        from app.models import Aufgabe
        gewerk = self._gewerk()
        gewerk.bza_id = "BZA-0930-B"
        self.s.commit()
        r = self.client.post(f"/projektierung/gewerk/{gewerk.id}/bza-ohne-mail",
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        self.assertTrue(all(a.status == "erledigt" for a in self.s.query(Aufgabe)
                            .filter(Aufgabe.gewerk_id == gewerk.id, Aufgabe.aktion_typ == "bza",
                                    Aufgabe.aktion_wert != "kfw")))


class GoLiveStandardSub(Basis):
    def test_standard_sub_je_typ(self):
        from app import golive, projektierung_logik, sub_mail
        typen = projektierung_logik.sub_typen(self.s)
        vorher = kern.parameter_holen(self.s, "sub_standards", "{}")
        try:
            kern.parameter_setzen(self.s, "sub_standards", "{}")
            subs = []
            for i, typ in enumerate(typen):
                sub = Subunternehmer(firma=f"Test-Sub-0930-{i}", typ=typ, aktiv=True,
                                     email=f"sub{i}@test.local")
                self.s.add(sub)
                subs.append(sub)
            self.s.flush()
            punkt = lambda: next(p for p in golive.pruefen(self.s) if p.titel.startswith("Standard-Sub"))
            self.assertFalse(punkt().ok)                    # aktive Subs, aber kein Standard
            for sub in subs:
                sub_mail.standard_sub_setzen(self.s, sub.typ, sub.id)
            self.assertTrue(punkt().ok)
            subs[0].email = ""                              # Standard ohne E-Mail zählt nicht
            self.assertFalse(punkt().ok)
            self.assertIn(typen[0], punkt().detail)
        finally:
            kern.parameter_setzen(self.s, "sub_standards", vorher)
            self.s.rollback()


class AnschriftenAussendienst(Basis):
    def test_ad_pflegt_eigene(self):
        from app import vorgaenge
        ad = (self.s.query(Benutzer).filter(Benutzer.rolle == "aussendienst",
                                            Benutzer.aktiv.is_(True)).first())
        if ad is None:
            self.skipTest("kein Außendienst-Benutzer in der Test-DB")
        kunde = Kunde(anrede="Frau", vorname="Ada", nachname="Anschrift-0930", plz="47139",
                      strasse="Weg 1", ort="Duisburg", email=TEST_EMAIL)
        self.s.add(kunde)
        self.s.flush()
        a = angebot_aufbau.angebot_anlegen(self.s, kunde.id)
        a.vertriebler_id = ad.id
        vorgang = vorgaenge.vorgang_fuer_angebot(self.s, a)
        self.s.commit()
        c = TestClient(app)
        from app import auth
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(ad.id))
        if not vorgaenge.gehoert_benutzer(self.s, vorgang, ad.id):
            self.skipTest("Vorgang wird dem AD über andere Wege zugeordnet")
        akte = c.get(f"/vorgaenge/{vorgang.id}")
        self.assertEqual(akte.status_code, 200)
        self.assertIn("Standard für neue Erfassungen/Angebote", akte.text)
        c.post(f"/vorgaenge/{vorgang.id}/anschriften",
               data={"liefer_name": "Nachbar", "liefer_strasse": "Nebenweg 2",
                     "liefer_plz": "47139", "liefer_ort": "Duisburg"})
        self.s.expire_all()
        self.assertEqual(self.s.get(Kunde, kunde.id).liefer_strasse, "Nebenweg 2")
        # fremder Vorgang: abgewiesen
        fremd = Kunde(vorname="Fritz", nachname="Anschrift-0930-fremd", plz="47051",
                      email=TEST_EMAIL)
        self.s.add(fremd)
        self.s.flush()
        fv = Vorgang(kunde_id=fremd.id)
        self.s.add(fv)
        self.s.commit()
        if not vorgaenge.gehoert_benutzer(self.s, fv, ad.id):
            c.post(f"/vorgaenge/{fv.id}/anschriften", data={"liefer_strasse": "X 1",
                                                           "liefer_plz": "1", "liefer_ort": "Y"})
            self.s.expire_all()
            self.assertEqual(self.s.get(Kunde, fremd.id).liefer_strasse, "")


if __name__ == "__main__":
    unittest.main()
