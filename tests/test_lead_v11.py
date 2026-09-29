# Tests PLAN_LEAD_V1.1 (Phasen 87–89, CLAUDE v21): Quelle · Kampagne · Kanal,
# Übersicht, Anrufliste neu. Laufen im Demo-Modus gegen die Entwicklungs-DB;
# Testleads tragen den Nachnamen „LeadV11-Test“ und werden aufgeräumt.
import json
import unittest
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Benutzer, Kampagne, Kunde, LeadAktivitaet, LeadQuelle,
                        Vorgang)

NACHNAME = "LeadV11-Test"


def aufraeumen(s):
    from app.models import LeadPosteingang, VotTermin
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(LeadPosteingang).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.delete(k)
    for q in s.query(LeadQuelle).filter(LeadQuelle.key.like("lp-test-%")):
        s.delete(q)
    for k in s.query(Kampagne).filter(Kampagne.name.like("lp-test-%")):
        s.delete(k)
    s.query(LeadPosteingang).filter(LeadPosteingang.graph_id.like("v11-%")).delete()
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        cls.modus = kern.parameter_holen(cls.s, "lead_freigabe_modus", "admin")
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", "admin")
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", cls.modus)
        cls.s.commit()
        cls.s.close()

    def lead(self, nr: int, quelle_key="website", versuche=0, eingang=None,
             sla_erfuellt=False, kampagne_id=None, **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key=quelle_key).first()
        daten = {"vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}", "plz": "47139",
                 "ort": "Duisburg", "telefon": f"0203 99{nr:04d}", "sparten": ["WP"]}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api",
                                       kampagne_id=kampagne_id, entscheidung="neu")
        if eingang is not None:
            vorgang.eingang_am = eingang
        for i in range(versuche):
            vorgang.versuch_nr = i + 1
            kern.aktivitaet(self.s, vorgang.id, "anruf", "Anruf: Nicht erreicht",
                            ergebnis="nicht_erreicht")
        if versuche:
            vorgang.lead_phase = "in_kontaktierung"
            vorgang.erstkontakt_am = vorgang.eingang_am + timedelta(minutes=10)
        if sla_erfuellt and not vorgang.erstkontakt_am:
            vorgang.erstkontakt_am = vorgang.eingang_am + timedelta(minutes=5)
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang


class Phase87Quellen(Basis):
    def test_parser_auto_anlage_und_utm(self):
        from app import lead_parser
        mail = ("Nachname: LeadV11-Test-P1\nPLZ: 47139\nTelefon: 0203 555001\n"
                "Sparte: WP\nutm_campaign: lp-test-utm\n")
        self.assertEqual(lead_parser.mail_verarbeiten(
            self.s, "v11-1", "agentur@test.local", "[LEAD] lp-test-neu lp-test-kampagne",
            mail), "lead")
        quelle = self.s.query(LeadQuelle).filter_by(key="lp-test-neu").one()
        self.assertTrue(quelle.auto_angelegt)
        self.assertEqual(quelle.typ, "landingpage")
        kampagne = self.s.query(Kampagne).filter_by(name="lp-test-kampagne").one()
        self.assertTrue(kampagne.auto_angelegt)
        self.assertEqual(kampagne.quelle_id, quelle.id)
        v1 = (self.s.query(Vorgang).join(Kunde, Kunde.id == Vorgang.kunde_id)
              .filter(Kunde.nachname == "LeadV11-Test-P1").one())
        self.assertEqual((v1.quelle_id, v1.kampagne_id), (quelle.id, kampagne.id))
        # zweiter Eingang hängt an derselben Kampagne (kein Doppel)
        mail2 = mail.replace("P1", "P2").replace("555001", "555002")
        lead_parser.mail_verarbeiten(self.s, "v11-2", "agentur@test.local",
                                     "[LEAD] lp-test-neu lp-test-kampagne", mail2)
        self.assertEqual(self.s.query(Kampagne).filter_by(name="lp-test-kampagne").count(), 1)
        # Glocke an Admin
        from app.models import Benachrichtigung
        self.assertTrue(self.s.query(Benachrichtigung)
                        .filter(Benachrichtigung.text.like("Neue Quelle aus Eingang: lp-test-neu%"))
                        .count())
        # ohne Kampagne im Betreff → utm_campaign: Treffer über kampagnen.name
        self.s.add(Kampagne(name="lp-test-utm", quelle_id=quelle.id, aktiv=True))
        self.s.commit()
        mail3 = mail.replace("P1", "P3").replace("555001", "555003")
        lead_parser.mail_verarbeiten(self.s, "v11-3", "agentur@test.local",
                                     "[LEAD] lp-test-neu", mail3)
        v3 = (self.s.query(Vorgang).join(Kunde, Kunde.id == Vorgang.kunde_id)
              .filter(Kunde.nachname == "LeadV11-Test-P3").one())
        self.assertEqual(v3.kampagne_id,
                         self.s.query(Kampagne).filter_by(name="lp-test-utm").one().id)
        # Badge in der Quellenpflege
        seite = self.client.get("/parametrierung/lead-quellen").text
        self.assertIn("neu · automatisch angelegt", seite)
        self.assertIn("→ Profil", seite)
        # einmal speichern → Badge weg
        self.client.post("/parametrierung/lead-quellen",
                         data={"art": "quelle", "id": str(quelle.id), "name": "lp-test-neu",
                               "typ": "landingpage", "kanal": "Standard", "aktiv": "on"})
        self.s.expire_all()
        self.assertFalse(self.s.get(LeadQuelle, quelle.id).auto_angelegt)
        self.assertIsNone(self.s.get(LeadQuelle, quelle.id).kanal)

    def test_api_utm_und_kanal(self):
        import secrets
        quelle = self.s.query(LeadQuelle).filter_by(key="partner_enni").one()
        quelle.api_key = quelle.api_key or secrets.token_hex(8)
        quelle.kanal = "Enni"
        self.s.commit()
        antwort = self.client.post("/api/leads", headers={"X-Api-Key": quelle.api_key},
                                   json={"nachname": f"{NACHNAME}-A1", "plz": "47139",
                                         "telefon": "0203 555101", "sparten": ["WP"],
                                         "utm_campaign": "lp-test-api"})
        self.assertEqual(antwort.status_code, 201)
        v = self.s.get(Vorgang, antwort.json()["vorgang_id"])
        kampagne = self.s.query(Kampagne).filter_by(name="lp-test-api").one()
        self.assertEqual(v.kampagne_id, kampagne.id)
        self.assertEqual(kampagne.utm_campaign, "lp-test-api")
        kunde = self.s.get(Kunde, v.kunde_id)
        self.assertEqual(kunde.vertriebskanal, "Enni")
        from app import angebotsprofile
        self.assertEqual(angebotsprofile.profil_fuer_kanal(self.s, kunde.vertriebskanal)
                         .regel_kennung, "enni")
        # manueller Kanal am Kunden bleibt bei weiterem Eingang
        kunde.vertriebskanal, kunde.kanal_manuell = "SWD", True
        self.s.commit()
        self.client.post("/api/leads", headers={"X-Api-Key": quelle.api_key},
                         json={"nachname": f"{NACHNAME}-A1", "plz": "47139",
                               "telefon": "0203 555101", "sparten": ["PV"]})
        self.s.expire_all()
        self.assertEqual(self.s.get(Kunde, kunde.id).vertriebskanal, "SWD")

    def test_fallback_unbekannt(self):
        quelle, kid = kern.quelle_kampagne_aufloesen(self.s)
        self.assertEqual((quelle.key, kid), ("unbekannt", None))
        self.assertIn("Enni", kern.kanal_werte(self.s))
        self.assertEqual(kern.kanal_werte(self.s)[0], "Standard")


if __name__ == "__main__":
    unittest.main()
