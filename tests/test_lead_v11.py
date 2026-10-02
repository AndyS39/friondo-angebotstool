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


class Phase88Uebersicht(Basis):
    def test_zaehlung_und_seite(self):
        from app import lead_uebersicht
        jetzt = datetime.now()
        heute = jetzt.replace(hour=9, minute=0, second=0, microsecond=0)
        if heute > jetzt:
            heute = jetzt - timedelta(minutes=1)
        self.lead(801, "website", eingang=heute)
        self.lead(802, "landingpage", eingang=heute - timedelta(days=2))
        self.lead(803, "portal", eingang=heute - timedelta(days=2), versuche=3)
        self.lead(804, "telefon", eingang=heute - timedelta(days=20), versuche=4,
                  naechste_aktion_am=jetzt - timedelta(hours=1))
        von = heute.replace(hour=0) - timedelta(days=13)
        morgen = heute.replace(hour=0) + timedelta(days=1)
        je_typ = kern.eingaenge_zaehlen(self.s, von, morgen, "typ")
        self.assertGreaterEqual(je_typ.get("website", 0), 1)
        self.assertGreaterEqual(je_typ.get("landingpage", 0), 1)
        tage = lead_uebersicht.eingaenge_je_tag(self.s, jetzt)
        summe_balken = sum(t["summe"] for t in tage["tage"])
        self.assertEqual(summe_balken, sum(je_typ.values()))
        k = lead_uebersicht.kpis(self.s, jetzt)
        self.assertGreaterEqual(k["heute"], 1)
        self.assertGreaterEqual(k["drei_versuche"], 2)
        self.assertGreaterEqual(k["vier_versuche"], 1)
        self.assertGreaterEqual(k["jetzt_dran"], 1)
        kontakt = {z["titel"]: z["n"] for z in lead_uebersicht.kontaktstatus(k["_offene"])}
        self.assertGreaterEqual(kontakt["3 Versuche"], 1)
        self.assertGreaterEqual(kontakt["4+ Versuche"], 1)
        tab = lead_uebersicht.tabelle(self.s, jetzt, "30")
        self.assertEqual(tab["summe"]["zeitraum"],
                         kern.eingaenge_zaehlen(self.s, tab["von"], morgen).get("gesamt", 0))
        # Seite, Umschalter, Cockpit-Redirect, Nav, Statistik-Tabelle + CSV
        seite = self.client.get("/lead-management/uebersicht")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Eingänge je Tag", seite.text)
        self.assertIn("Kontaktstatus der offenen Leads", seite.text)
        self.assertIn("Termin-Rückmeldung offen", seite.text)      # Cockpit-Block
        self.assertIn('href="/lead-management/uebersicht"', seite.text)
        self.assertNotIn(">Cockpit<", seite.text)
        self.assertIn("Woche", self.client.get("/lead-management/uebersicht?zeitraum=woche").text)
        r = self.client.get("/lead-management/cockpit", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]),
                         (303, "/lead-management/uebersicht"))
        r = self.client.get("/lead-management", follow_redirects=False)
        # v23 (Phase 110): Modul-Einstieg ohne lm_startseite = persönliches Dashboard
        self.assertEqual(r.headers["location"], "/lead-management/dashboard")
        stat = self.client.get("/lead-management/statistik").text
        self.assertIn("Eingänge je Woche × Quellen-Typ", stat)
        csv = self.client.get("/lead-management/statistik?export=wochen")
        self.assertTrue(csv.text.startswith("﻿Woche;ab;"))
        # Portal-Karte mit den neuen Kacheln
        portal = self.client.get("/").text
        self.assertIn("Eingänge heute", portal)
        self.assertIn("Jetzt dran", portal)
        # Innendienst im Demo: 404
        from app.models import Benutzer
        innen = self.s.query(Benutzer).filter_by(rolle="innendienst", aktiv=True).first()
        if innen is not None:
            c2 = TestClient(app)
            c2.post("/login", data={"benutzer_id": str(innen.id), "pin": "1234"})
            self.assertEqual(c2.get("/lead-management/uebersicht").status_code, 404)

    def test_startseite_nach_rolle(self):
        from types import SimpleNamespace

        from app import lead_uebersicht
        kern.parameter_setzen(self.s, "lm_startseite", "")
        # v23 (Phase 110): leer = Dashboard „Meine Arbeit“ für alle Rollen
        self.assertEqual(lead_uebersicht.startseite(self.s, SimpleNamespace(rolle="admin")),
                         "dashboard")
        self.assertEqual(lead_uebersicht.startseite(
            self.s, SimpleNamespace(rolle="leadmanagement")), "dashboard")
        kern.parameter_setzen(self.s, "lm_startseite", "uebersicht")
        self.assertEqual(lead_uebersicht.startseite(self.s, SimpleNamespace(rolle="admin")),
                         "uebersicht")
        kern.parameter_setzen(self.s, "lm_startseite", "anrufliste")
        self.assertEqual(lead_uebersicht.startseite(self.s, SimpleNamespace(rolle="admin")),
                         "anrufliste")
        kern.parameter_setzen(self.s, "lm_startseite", "")
        self.s.commit()


class Phase89Anrufliste(Basis):
    def test_gruppen_chips_satz(self):
        from app import lead_anrufliste
        jetzt = datetime.now()
        # SLA rot ohne Versuch (Eingang vor 3 Arbeitstagen), Rückruf fällig,
        # Kaskade fällig mit 3 Versuchen, neu heute grün, zurückgestellt fällig
        rot = self.lead(901, "website", eingang=jetzt - timedelta(days=3))
        rueck = self.lead(902, "portal", eingang=jetzt - timedelta(days=1), versuche=1,
                          naechste_aktion_am=jetzt - timedelta(minutes=30))
        kern.aktivitaet(self.s, rueck.id, "anruf", "Anruf: Rückruf gewünscht",
                        ergebnis="rueckruf_gewuenscht", naechste_aktion_am=rueck.naechste_aktion_am)
        rueck.versuch_nr = 2
        weiter = self.lead(903, "landingpage", eingang=jetzt - timedelta(days=2), versuche=3,
                           naechste_aktion_am=jetzt - timedelta(hours=2))
        neu = self.lead(904, "telefon", eingang=jetzt - timedelta(minutes=5))
        zur = self.lead(905, "partner_enni", eingang=jetzt - timedelta(days=10),
                        versuche=1, lead_phase="zurueckgestellt",
                        zurueckgestellt_bis=jetzt - timedelta(hours=1),
                        zurueckgestellt_grund="Bauphase später")
        self.s.commit()
        f = lead_anrufliste.filter_aus_query({"meine": "0"})
        d = lead_anrufliste.daten(self.s, None, f)
        gruppen = {g["key"]: [z["vorgang"].id for z in g["zeilen"]] for g in d["gruppen"]}
        self.assertIn(rot.id, gruppen["dran"])
        self.assertIn(rueck.id, gruppen["dran"])
        self.assertIn(weiter.id, gruppen["weiter"])
        self.assertIn(neu.id, gruppen["neu"])
        self.assertIn(zur.id, gruppen["wiedervorlage"])
        # Reihenfolge Jetzt dran: SLA rot vor Rückruf
        self.assertLess(gruppen["dran"].index(rot.id), gruppen["dran"].index(rueck.id))
        # Sätze
        satz = {z["vorgang"].id: " · ".join(t for t, _ in z["satz"])
                for g in d["gruppen"] for z in g["zeilen"]}
        self.assertIn("noch nicht angerufen", satz[rot.id])
        self.assertIn("Rückruf gewünscht", satz[rueck.id])
        self.assertIn("3× nicht erreicht", satz[weiter.id])
        self.assertIn("nächster Versuch", satz[weiter.id])
        self.assertIn("zurückgestellt", satz[zur.id])
        self.assertIn("heute fällig", satz[zur.id])
        # Chips zählen wie die Filter treffen
        self.assertEqual(d["zaehler"]["arbeitsliste"], d["offen"])
        for chip, param in (("sla_rot", {"sla": "rot"}), ("drei", {"versuche_min": "3"}),
                            ("rueckruf", {"rueckruf": "heute"}), ("frei", {"frei": "1"})):
            g = lead_anrufliste.daten(self.s, None, lead_anrufliste.filter_aus_query(
                {"meine": "0", **param}))
            self.assertEqual(d["zaehler"][chip], g["offen"], chip)
        # Filter aus der Übersicht
        g = lead_anrufliste.daten(self.s, None, lead_anrufliste.filter_aus_query(
            {"meine": "0", "versuche": "3"}))
        self.assertTrue(all((z["vorgang"].versuch_nr or 0) == 3
                            for gr in g["gruppen"] for z in gr["zeilen"]))
        self.assertIn(weiter.id, [z["vorgang"].id for gr in g["gruppen"] for z in gr["zeilen"]])
        g = lead_anrufliste.daten(self.s, None, lead_anrufliste.filter_aus_query(
            {"meine": "0", "quelle_typ": "portal"}))
        self.assertTrue(all(z["quelle_gruppe"] == "portal" for gr in g["gruppen"] for z in gr["zeilen"]))
        # Seite: Chips, Gruppenköpfe, Punkte, ⋯-Menü, Panel, Legende
        seite = self.client.get("/lead-management/anrufliste?meine=0").text
        for text in ("Jetzt dran", "Weiter versuchen", "Neu heute", "Wiedervorlagen fällig",
                     "Sonstige offene", 'class="lm-dots', "lm-menue", 'id="lead-panel"',
                     "Tasten 1 Erreicht", "Arbeitsliste <b>"):
            self.assertIn(text, seite)
        # Kopfblock zeigt dieselben Punkte
        akte = self.client.get(f"/vorgaenge/{weiter.id}").text
        self.assertIn("Kontaktstatus:", akte)
        self.assertIn("3× nicht erreicht", akte)
        self.assertEqual(akte.count('<i class="v"></i>'), 3)
        # Tasten/Buttons: Ergebnis-Route unverändert
        r = self.client.post(f"/lead-management/anruf/{neu.id}", data={"ergebnis": "mailbox"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, neu.id).versuch_nr, 1)


if __name__ == "__main__":
    unittest.main()
