# Tests PLAN_LEAD_V2 Phase 110 (CLAUDE v23): persönliches Dashboard „Meine
# Arbeit“ (A1, F6, F16) und To-Dos (A2, F7). Laufen im Demo-Modus gegen die
# Entwicklungs-DB; Testleads tragen den Nachnamen „LeadV2D-Test“ (demo=1),
# Testbenutzer heißen „LeadV2D …“ – alles wird aufgeräumt.
import unittest
import warnings
from datetime import datetime, timedelta
from types import SimpleNamespace

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, benachrichtigungen, lead_dashboard, lead_todos, lead_uebersicht
from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, KommunikationLog, Kunde,
                        LeadAktivitaet, LeadQuelle, Todo, Vorgang, VorgangsNotiz,
                        VotTermin)

NACHNAME = "LeadV2D-Test"
PRAEFIX = "LeadV2D"


def inhalt(text: str) -> str:
    """Nur der Seiteninhalt – die Glocke in der Kopfzeile nennt ebenfalls Kundennamen."""
    return text.split("<main", 1)[-1]


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete()
            s.query(Todo).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.delete(k)
    s.query(Todo).filter(Todo.titel.like(f"{PRAEFIX}%")).delete(synchronize_session=False)
    s.query(Benachrichtigung).filter(Benachrichtigung.text.like(f"%{PRAEFIX}%")).delete(
        synchronize_session=False)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX} %")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(Todo).filter((Todo.an_benutzer_id == b.id) | (Todo.von_benutzer_id == b.id)).delete(
            synchronize_session=False)
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete(synchronize_session=False)
        s.delete(b)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.modus = kern.parameter_holen(cls.s, "lead_freigabe_modus", "admin")
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", "admin")
        cls.startseite_alt = kern.parameter_holen(cls.s, "lm_startseite", "")
        cls.s.commit()
        cls.admin = cls.s.get(Benutzer, 1)
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        # Testbenutzer: Innendienst (im Demo ohne Modul), Außendienst ohne
        # HV-Kennzeichen, Handelsvertreter (terminiert_selbst)
        cls.innen = cls.benutzer("LeadV2D Innen", "innendienst")
        cls.aussen = cls.benutzer("LeadV2D Aussen", "aussendienst")
        cls.hv = cls.benutzer("LeadV2D Vertreter", "aussendienst")
        cls.s.add(AdProfil(benutzer_id=cls.hv.id, terminiert_selbst=True, aktiv_terminierung=True))
        cls.s.add(AdProfil(benutzer_id=cls.aussen.id, terminiert_selbst=False))
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", cls.modus)
        kern.parameter_setzen(cls.s, "lm_startseite", cls.startseite_alt)
        cls.s.commit()
        cls.s.close()

    @classmethod
    def benutzer(cls, name, rolle):
        b = Benutzer(name=name, rolle=rolle, aktiv=True, pin_hash=auth.pin_hash("1234"))
        cls.s.add(b)
        cls.s.flush()
        return b

    @classmethod
    def anmelden(cls, benutzer):
        c = TestClient(app)
        c.post("/login", data={"benutzer_id": str(benutzer.id), "pin": "1234"})
        return c

    def lead(self, nr, **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}", "plz": "47139",
                 "ort": "Duisburg", "telefon": f"0203 88{nr:04d}", "sparten": ["WP"],
                 "email": f"v2d{nr}@test.local"}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        vorgang.demo = True
        vorgang.leadmanager_id = None
        vorgang.naechste_aktion_am = None
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def kunde(self, vorgang):
        return self.s.get(Kunde, vorgang.kunde_id)


class Dashboard(Basis):
    def test_rendert_alle_bloecke_und_beide_wiedervorlagen(self):
        jetzt = datetime.now()
        # Lead-Wiedervorlagen: fälliger Rückruf (mein Lead), kommende Zurückstellung (frei)
        v_rueckruf = self.lead(1, leadmanager_id=1, lead_phase="in_kontaktierung", versuch_nr=1,
                               naechste_aktion_am=jetzt - timedelta(hours=1))
        kern.aktivitaet(self.s, v_rueckruf.id, "anruf", "Anruf: Rückruf gewünscht",
                        ergebnis="rueckruf_gewuenscht")
        v_zurueck = self.lead(2, lead_phase="zurueckgestellt",
                              zurueckgestellt_bis=(jetzt + timedelta(days=3)).replace(
                                  hour=0, minute=0, second=0, microsecond=0),
                              zurueckgestellt_grund="Bauphase später")
        # Angebots-Wiedervorlage (Innendienst = NULL), fällig heute
        v_angebot = self.lead(3, leadmanager_id=1, lead_phase="angebot",
                              wiedervorlage_am=jetzt.replace(hour=0, minute=0, second=0, microsecond=0),
                              wiedervorlage_benutzer_id=None, verfolgung_ampel="heiss")
        # fremde Lead-Wiedervorlage (anderer Leadmanager) darf NICHT erscheinen
        v_fremd = self.lead(4, leadmanager_id=self.innen.id, lead_phase="in_kontaktierung",
                            naechste_aktion_am=jetzt - timedelta(hours=2))
        # zugeteilt + Telefongespräch morgen
        v_termin = self.lead(5, leadmanager_id=1, lead_phase="qualifiziert")
        morgen = (jetzt + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        self.s.add(VotTermin(vorgang_id=v_termin.id, ad_id=4, beginn=morgen,
                             ende=morgen + timedelta(minutes=30), status="geplant",
                             typ="telefon", medium="telefon", demo=True))
        # To-Do an mich, fällig gestern
        lead_todos.anlegen(self.s, self.innen, 1, f"{PRAEFIX} Unterlagen prüfen",
                           faellig_am=jetzt - timedelta(days=1), vorgang_id=v_termin.id)
        self.s.commit()

        daten = lead_dashboard.daten(self.s, self.admin)
        ids_lead = {z["vorgang"].id for z in daten["lead_wv"]}
        self.assertIn(v_rueckruf.id, ids_lead)
        self.assertIn(v_zurueck.id, ids_lead)
        self.assertNotIn(v_fremd.id, ids_lead)
        z_rueckruf = next(z for z in daten["lead_wv"] if z["vorgang"].id == v_rueckruf.id)
        self.assertTrue(z_rueckruf["faellig"] and z_rueckruf["ueberfaellig"])
        self.assertEqual(z_rueckruf["grund"], "Rückruf gewünscht")
        z_zurueck = next(z for z in daten["lead_wv"] if z["vorgang"].id == v_zurueck.id)
        self.assertTrue(z_zurueck["kommend"])
        self.assertIn("Bauphase später", z_zurueck["grund"])
        ids_angebot = {z["vorgang"].id for z in daten["angebot_wv"]}
        self.assertIn(v_angebot.id, ids_angebot)
        self.assertNotIn(v_rueckruf.id, ids_angebot)
        self.assertTrue(next(z for z in daten["angebot_wv"]
                             if z["vorgang"].id == v_angebot.id)["faellig"])
        # zugeteilt nach Phase – v25 (Phase 118/120): in_kontaktierung + qualifiziert
        # bilden EINE Gruppe „Kontaktiert“ (Label aus dem Blatt Status), daher
        # Suche über die Phasenliste der Gruppe statt über den Gruppenschlüssel
        gruppen = daten["zugeteilt"]["gruppen"]
        kontakt = next(g for g in gruppen if "qualifiziert" in g["phasen"])
        self.assertEqual(kontakt["name"], "Kontaktiert")
        self.assertIn(v_termin.id, [z["vorgang"].id for z in kontakt["zeilen"]])
        self.assertNotIn(v_zurueck.id, [z["vorgang"].id for g in gruppen for z in g["zeilen"]])
        # Termine meiner Leads inkl. Terminart
        termin_ids = {z["termin"].vorgang_id for z in daten["termine"]}
        self.assertIn(v_termin.id, termin_ids)
        self.assertEqual(next(z for z in daten["termine"]
                              if z["termin"].vorgang_id == v_termin.id)["typ"], "Telefongespräch")
        # Kacheln
        k = daten["kacheln"]
        self.assertGreaterEqual(k["faellig"], 2)       # Rückruf + Angebots-WV
        self.assertGreaterEqual(k["ueberfaellig"], 1)
        self.assertGreaterEqual(k["kommend"], 1)
        self.assertGreaterEqual(k["todos"], 1)
        self.assertGreaterEqual(k["todos_faellig"], 1)
        self.assertGreaterEqual(k["termine"], 1)
        self.assertTrue(daten["mit_demo"])

        seite = self.client.get("/lead-management/dashboard")
        self.assertEqual(seite.status_code, 200)
        for text in ("Meine Arbeit", "Lead-Wiedervorlagen", "Angebots-Wiedervorlagen",
                     "Mir zugeteilte Vorgänge", "Meine To-Dos", "Termine · nächste",
                     "Fällig heute", "Offene To-Dos", "inkl. Demo", "Telefongespräch",
                     "Rückruf gewünscht", "Bauphase später", f"{PRAEFIX} Unterlagen prüfen",
                     'href="/lead-management/uebersicht"', "Mehr …"):
            self.assertIn(text, seite.text, text)
        self.assertIn(self.kunde(v_rueckruf).anzeige_name, seite.text)
        self.assertIn(self.kunde(v_angebot).anzeige_name, seite.text)
        self.assertNotIn(self.kunde(v_fremd).anzeige_name, inhalt(seite.text))
        # Umschalter Team → Übersicht zeigt zurück
        ueber = self.client.get("/lead-management/uebersicht")
        self.assertIn('href="/lead-management/dashboard"', ueber.text)
        self.assertIn("Meine Arbeit", ueber.text)
        # Termine „alle“
        alle = self.client.get("/lead-management/dashboard?termine=alle")
        self.assertEqual(alle.status_code, 200)

    def test_schnellaktionen_wiedervorlage(self):
        jetzt = datetime.now()
        v = self.lead(11, leadmanager_id=1, lead_phase="in_kontaktierung", versuch_nr=2,
                      naechste_aktion_am=jetzt - timedelta(hours=1))
        neu = (jetzt + timedelta(days=2)).replace(hour=10, minute=30, second=0, microsecond=0)
        r = self.client.post(f"/lead-management/dashboard/wiedervorlage/{v.id}",
                             data={"art": "lead", "aktion": "verschieben",
                                   "datum": neu.strftime("%Y-%m-%dT%H:%M")},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/lead-management/dashboard"))
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).naechste_aktion_am, neu)
        r = self.client.post(f"/lead-management/dashboard/wiedervorlage/{v.id}",
                             data={"art": "lead", "aktion": "erledigt"}, follow_redirects=False)
        self.s.expire_all()
        self.assertIsNone(self.s.get(Vorgang, v.id).naechste_aktion_am)
        texte = [a.text for a in self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id)]
        self.assertTrue(any("Wiedervorlage verschoben" in t for t in texte))
        self.assertTrue(any("Wiedervorlage erledigt" in t for t in texte))
        # Zurückgestellt erledigt → zurück auf Neu
        v2 = self.lead(12, leadmanager_id=1, lead_phase="zurueckgestellt",
                       zurueckgestellt_bis=jetzt - timedelta(days=1), zurueckgestellt_grund="Sonstiges")
        self.client.post(f"/lead-management/dashboard/wiedervorlage/{v2.id}",
                         data={"art": "lead", "aktion": "erledigt"}, follow_redirects=False)
        self.s.expire_all()
        v2 = self.s.get(Vorgang, v2.id)
        self.assertEqual(v2.lead_phase, "neu")
        self.assertIsNone(v2.zurueckgestellt_bis)
        # Angebots-Wiedervorlage erledigt (verfolgung_setzen) und verschoben
        v3 = self.lead(13, leadmanager_id=1, lead_phase="angebot",
                       wiedervorlage_am=jetzt - timedelta(days=1), wiedervorlage_benutzer_id=None)
        self.client.post(f"/lead-management/dashboard/wiedervorlage/{v3.id}",
                         data={"art": "angebot", "aktion": "verschieben",
                               "datum": (jetzt + timedelta(days=5)).strftime("%Y-%m-%d")},
                         follow_redirects=False)
        self.s.expire_all()
        v3 = self.s.get(Vorgang, v3.id)
        self.assertEqual(v3.wiedervorlage_am.date(), (jetzt + timedelta(days=5)).date())
        self.assertIsNone(v3.wiedervorlage_benutzer_id)
        self.client.post(f"/lead-management/dashboard/wiedervorlage/{v3.id}",
                         data={"art": "angebot", "aktion": "erledigt"}, follow_redirects=False)
        self.s.expire_all()
        self.assertIsNone(self.s.get(Vorgang, v3.id).wiedervorlage_am)
        # Fremde Lead-Wiedervorlage (anderer Leadmanager): kein Zugriff für Nicht-Admin
        v4 = self.lead(14, leadmanager_id=self.innen.id, lead_phase="in_kontaktierung",
                       naechste_aktion_am=jetzt - timedelta(hours=1))
        meldung = lead_dashboard.wiedervorlage_aktion(self.s, v4, self.hv, "lead", "erledigt")
        self.assertIn("Kein Zugriff", meldung)
        self.assertIsNotNone(v4.naechste_aktion_am)

    def test_startseite_dashboard_standard(self):
        kern.parameter_setzen(self.s, "lm_startseite", "")
        self.s.commit()
        self.assertEqual(lead_uebersicht.startseite(self.s, SimpleNamespace(rolle="admin")), "dashboard")
        self.assertEqual(lead_uebersicht.startseite(self.s, SimpleNamespace(rolle="leadmanagement")),
                         "dashboard")
        for wert in ("hauptboard", "uebersicht", "anrufliste", "dashboard"):
            kern.parameter_setzen(self.s, "lm_startseite", wert)
            self.s.commit()
            self.assertEqual(lead_uebersicht.startseite(self.s, SimpleNamespace(rolle="admin")), wert)
        kern.parameter_setzen(self.s, "lm_startseite", "unsinn")
        self.s.commit()
        self.assertEqual(lead_uebersicht.startseite(self.s, SimpleNamespace(rolle="admin")), "dashboard")
        kern.parameter_setzen(self.s, "lm_startseite", "")
        self.s.commit()
        r = self.client.get("/lead-management", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/lead-management/dashboard"))

    def test_hv_variante_gefiltert(self):
        jetzt = datetime.now()
        eigen = self.lead(21, ad_id=self.hv.id, lead_phase="in_kontaktierung", versuch_nr=1,
                          naechste_aktion_am=jetzt - timedelta(hours=1))
        fremd = self.lead(22, leadmanager_id=1, lead_phase="in_kontaktierung",
                          naechste_aktion_am=jetzt - timedelta(hours=1))
        eigen_angebot = self.lead(23, ad_id=self.hv.id, lead_phase="angebot",
                                  wiedervorlage_am=jetzt - timedelta(days=1),
                                  wiedervorlage_benutzer_id=self.hv.id)
        fremd_angebot = self.lead(24, lead_phase="angebot", wiedervorlage_am=jetzt - timedelta(days=1),
                                  wiedervorlage_benutzer_id=None)
        morgen = (jetzt + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
        self.s.add(VotTermin(vorgang_id=eigen.id, ad_id=self.hv.id, beginn=morgen,
                             ende=morgen + timedelta(minutes=90), status="geplant", demo=True))
        self.s.add(VotTermin(vorgang_id=fremd.id, ad_id=4, beginn=morgen,
                             ende=morgen + timedelta(minutes=90), status="geplant", demo=True))
        self.s.commit()
        daten = lead_dashboard.daten(self.s, self.hv)
        self.assertTrue(daten["hv"])
        self.assertEqual({z["vorgang"].id for z in daten["lead_wv"]}, {eigen.id})
        self.assertEqual({z["vorgang"].id for z in daten["angebot_wv"]}, {eigen_angebot.id})
        self.assertEqual({z["termin"].vorgang_id for z in daten["termine"]}, {eigen.id})
        zugeteilt = {z["vorgang"].id for g in daten["zugeteilt"]["gruppen"] for z in g["zeilen"]}
        self.assertEqual(zugeteilt, {eigen.id, eigen_angebot.id})
        c = self.anmelden(self.hv)
        r = c.get("/lead-management", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/lead-management/dashboard"))
        seite = c.get("/lead-management/dashboard")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Handelsvertreter-Sicht", seite.text)
        self.assertIn(self.kunde(eigen).anzeige_name, seite.text)
        self.assertNotIn(self.kunde(fremd).anzeige_name, inhalt(seite.text))
        self.assertNotIn(self.kunde(fremd_angebot).anzeige_name, inhalt(seite.text))
        self.assertNotIn(">Team</a>", seite.text)   # Umschalter ohne Team-Sicht (F16)
        # Portal-Zähler für den HV (zugriff_erlaubt)
        z = lead_dashboard.portal_zaehler(self.hv)
        self.assertGreaterEqual(z["wv"], 2)

    def test_aussendienst_ohne_hv_weiterleitung_und_gate_404(self):
        c_ad = self.anmelden(self.aussen)
        r = c_ad.get("/lead-management/dashboard", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]),
                         (303, "/lead-management/meine-termine"))
        # Innendienst im Demo-Modus: 404 (Modul unsichtbar)
        c_id = self.anmelden(self.innen)
        self.assertEqual(c_id.get("/lead-management/dashboard").status_code, 404)
        self.assertEqual(c_id.get("/lead-management/todos").status_code, 404)
        self.assertEqual(c_id.post("/lead-management/todos/neu",
                                   data={"titel": f"{PRAEFIX} x", "an_benutzer_id": "1"}).status_code, 404)
        self.assertEqual(c_id.post("/lead-management/dashboard/wiedervorlage/1",
                                   data={"art": "lead", "aktion": "erledigt"}).status_code, 404)
        self.assertIsNone(lead_dashboard.portal_zaehler(self.innen))

    def test_portal_karte_zaehler(self):
        jetzt = datetime.now()
        self.lead(31, leadmanager_id=1, lead_phase="in_kontaktierung",
                  naechste_aktion_am=jetzt - timedelta(hours=1))
        z = lead_dashboard.portal_zaehler(self.admin)
        self.assertGreaterEqual(z["faellig"], 1)
        portal = self.client.get("/").text
        self.assertIn("Meine fälligen Wiedervorlagen/To-Dos", portal)


class ToDos(Basis):
    def test_anlegen_glocke_erledigen_aktivitaet(self):
        jetzt = datetime.now()
        v = self.lead(41, leadmanager_id=1, lead_phase="qualifiziert")
        faellig = (jetzt + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        r = self.client.post("/lead-management/todos/neu",
                             data={"vorgang_id": str(v.id), "titel": f"{PRAEFIX} Angebot nachfassen",
                                   "text": "Kunde will Vergleich", "faellig_am": faellig.strftime("%Y-%m-%dT%H:%M"),
                                   "an_benutzer_id": str(self.innen.id),
                                   "zurueck": "/lead-management/dashboard"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/lead-management/dashboard?meldung="))
        todo = self.s.query(Todo).filter_by(titel=f"{PRAEFIX} Angebot nachfassen").one()
        self.assertEqual((todo.an_benutzer_id, todo.von_benutzer_id, todo.status),
                         (self.innen.id, 1, "offen"))
        self.assertEqual(todo.faellig_am, faellig)
        self.assertEqual(todo.vorgang_id, v.id)
        # Glocke art=todo an den Empfänger – auch ohne Modul-Sichtbarkeit (Demo)
        glocke = (self.s.query(Benachrichtigung)
                  .filter(Benachrichtigung.benutzer_id == self.innen.id,
                          Benachrichtigung.art == "todo",
                          Benachrichtigung.text.like(f"%{PRAEFIX} Angebot nachfassen%")).one())
        self.assertIn("To-Do von Admin", glocke.text)
        self.assertIn(self.kunde(v).anzeige_name, glocke.text)
        self.assertEqual(glocke.link, f"/lead-management/todos#todo-{todo.id}")
        self.assertGreaterEqual(benachrichtigungen.ungelesen_anzahl(self.s, self.innen), 1)
        self.assertIn(glocke.id, [e.id for e in benachrichtigungen.letzte(self.s, self.innen)])
        # Aktivität am Vorgang
        texte = [a.text for a in self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id)]
        self.assertTrue(any(t.startswith(f"To-Do für {self.innen.name}") for t in texte))
        # in der Liste des Erstellers (von mir vergeben) und beim Empfänger (offen)
        self.assertIn(todo.id, [t.id for t in lead_todos.vergebene(self.s, 1)])
        self.assertIn(todo.id, [t.id for t in lead_todos.offene(self.s, self.innen.id)])
        self.assertIn(todo.id, [t.id for t in lead_todos.fuer_vorgang(self.s, v.id)])
        seite = self.client.get("/lead-management/todos?sicht=vergeben")
        self.assertIn(f"{PRAEFIX} Angebot nachfassen", seite.text)
        seite = self.client.get(f"/lead-management/todos?vorgang_id={v.id}")
        self.assertIn(f"{PRAEFIX} Angebot nachfassen", seite.text)
        # Empfänger erledigt (im Demo ohne Modul – Rechte am To-Do reichen)
        c_id = self.anmelden(self.innen)
        r = c_id.post(f"/lead-management/todos/{todo.id}/erledigt",
                      data={"zurueck": "/lead-management/meine-termine"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        todo = self.s.get(Todo, todo.id)
        self.assertEqual(todo.status, "erledigt")
        self.assertIsNotNone(todo.erledigt_am)
        texte = [a.text for a in self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id)]
        self.assertTrue(any(t.startswith("To-Do erledigt:") for t in texte))
        # Ersteller bekommt die Erledigt-Glocke
        self.assertTrue(self.s.query(Benachrichtigung)
                        .filter(Benachrichtigung.benutzer_id == 1, Benachrichtigung.art == "todo",
                                Benachrichtigung.text.like("To-Do erledigt von%")).count())
        self.assertIn(todo.id, [t.id for t in lead_todos.erledigte(self.s, self.innen.id)])
        self.assertNotIn(todo.id, [t.id for t in lead_todos.offene(self.s, self.innen.id)])
        # wieder öffnen
        c_id.post(f"/lead-management/todos/{todo.id}/offen", follow_redirects=False)
        self.s.expire_all()
        self.assertEqual(self.s.get(Todo, todo.id).status, "offen")

    def test_titel_pflicht_und_sortierung(self):
        with self.assertRaises(ValueError):
            lead_todos.anlegen(self.s, self.admin, self.innen.id, "   ")
        r = self.client.post("/lead-management/todos/neu",
                             data={"titel": "", "an_benutzer_id": str(self.innen.id)},
                             follow_redirects=False)
        self.assertIn("Titel", r.headers["location"])
        jetzt = datetime.now()
        spaet = lead_todos.anlegen(self.s, self.admin, self.admin.id, f"{PRAEFIX} spät",
                                   faellig_am=jetzt + timedelta(days=3))
        ohne = lead_todos.anlegen(self.s, self.admin, self.admin.id, f"{PRAEFIX} ohne Datum")
        frueh = lead_todos.anlegen(self.s, self.admin, self.admin.id, f"{PRAEFIX} früh",
                                   faellig_am=jetzt - timedelta(hours=2))
        self.s.commit()
        ids = [t.id for t in lead_todos.offene(self.s, self.admin.id) if t.titel.startswith(PRAEFIX)]
        self.assertEqual(ids[:2], [frueh.id, spaet.id])
        self.assertEqual(ids[-1], ohne.id)
        # selbst gesetzt → keine Glocke an mich selbst
        self.assertEqual(self.s.query(Benachrichtigung)
                         .filter(Benachrichtigung.benutzer_id == 1,
                                 Benachrichtigung.text.like(f"To-Do von%{PRAEFIX} früh%")).count(), 0)
        zeilen = lead_todos.zeilen(self.s, [frueh, spaet, ohne], jetzt)
        self.assertEqual([z["klasse"] for z in zeilen], ["faellig", "geplant", ""])
        self.assertEqual(lead_todos.faellig_parsen("2026-10-05"), datetime(2026, 10, 5, 9, 0))
        self.assertEqual(lead_todos.faellig_parsen("2026-10-05T14:30"), datetime(2026, 10, 5, 14, 30))
        self.assertIsNone(lead_todos.faellig_parsen("Quatsch"))

    def test_loeschen_nur_ersteller_oder_admin(self):
        todo = lead_todos.anlegen(self.s, self.admin, self.innen.id, f"{PRAEFIX} löschen")
        self.s.commit()
        self.assertFalse(lead_todos.darf_loeschen(self.innen, todo))   # Empfänger
        self.assertTrue(lead_todos.darf_loeschen(self.admin, todo))
        self.assertTrue(lead_todos.darf_erledigen(self.innen, todo))
        self.assertFalse(lead_todos.darf_sehen(self.hv, todo))
        c_id = self.anmelden(self.innen)
        self.assertEqual(c_id.post(f"/lead-management/todos/{todo.id}/loeschen").status_code, 404)
        c_hv = self.anmelden(self.hv)
        self.assertEqual(c_hv.post(f"/lead-management/todos/{todo.id}/erledigt").status_code, 404)
        r = self.client.post(f"/lead-management/todos/{todo.id}/loeschen", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIsNone(self.s.query(Todo).filter_by(id=todo.id).first())

    def test_glocke_fuer_aussendienst_im_demo_nicht_gefiltert(self):
        """To-Dos (art=todo) kommen beim Außendienst durch, obwohl art=lead im
        Demo-Modus weggefiltert wird."""
        vorher = benachrichtigungen.ungelesen_anzahl(self.s, self.aussen)
        kern.benachrichtigen(self.s, [self.aussen.id], f"{PRAEFIX} Lead-Glocke (gefiltert)",
                             "/lead-management/anrufliste")
        self.s.commit()
        self.assertEqual(benachrichtigungen.ungelesen_anzahl(self.s, self.aussen), vorher)
        todo = lead_todos.anlegen(self.s, self.admin, self.aussen.id, f"{PRAEFIX} Für den AD")
        self.s.commit()
        self.assertEqual(benachrichtigungen.ungelesen_anzahl(self.s, self.aussen), vorher + 1)
        glocke = (self.s.query(Benachrichtigung)
                  .filter(Benachrichtigung.benutzer_id == self.aussen.id,
                          Benachrichtigung.text.like(f"%{PRAEFIX} Für den AD%")).one())
        self.assertEqual(glocke.art, "todo")
        self.assertEqual(glocke.link, f"/lead-management/meine-termine#todo-{todo.id}")

    def test_fremder_vorgang_fuer_handelsvertreter_gesperrt(self):
        """Prüfung Phase 110: HV sieht über ?vorgang_id= keine fremden Kunden und
        kann an fremde Vorgänge kein To-Do (mit Aktivität) hängen; eigener
        Vorgang (ad_id) geht. Glocken-Link des HV zeigt auf die To-Do-Liste."""
        fremd = self.lead(51, leadmanager_id=1, lead_phase="qualifiziert")
        eigen = self.lead(52, ad_id=self.hv.id, lead_phase="qualifiziert")
        c_hv = self.anmelden(self.hv)
        seite = c_hv.get(f"/lead-management/todos?vorgang_id={fremd.id}")
        self.assertEqual(seite.status_code, 200)
        self.assertNotIn(self.kunde(fremd).anzeige_name, inhalt(seite.text))
        self.assertIn("Kein Zugriff auf diesen Vorgang", seite.text)
        r = c_hv.post("/lead-management/todos/neu",
                      data={"titel": f"{PRAEFIX} fremd", "an_benutzer_id": str(self.hv.id),
                            "vorgang_id": str(fremd.id)}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("kein+Zugriff", r.headers["location"])
        self.assertIsNone(self.s.query(Todo).filter_by(titel=f"{PRAEFIX} fremd").first())
        self.assertEqual(self.s.query(LeadAktivitaet).filter_by(vorgang_id=fremd.id)
                         .filter(LeadAktivitaet.text.like(f"%{PRAEFIX} fremd%")).count(), 0)
        r = c_hv.post("/lead-management/todos/neu",
                      data={"titel": f"{PRAEFIX} eigen", "an_benutzer_id": str(self.hv.id),
                            "vorgang_id": str(eigen.id)}, follow_redirects=False)
        self.assertIn("angelegt", r.headers["location"])
        todo = self.s.query(Todo).filter_by(titel=f"{PRAEFIX} eigen").one()
        self.assertEqual(todo.vorgang_id, eigen.id)
        seite = c_hv.get(f"/lead-management/todos?vorgang_id={eigen.id}")
        self.assertIn(self.kunde(eigen).anzeige_name, inhalt(seite.text))
        # Vorgang unbekannt → Hinweis statt 500
        r = c_hv.post("/lead-management/todos/neu",
                      data={"titel": f"{PRAEFIX} nix", "an_benutzer_id": str(self.hv.id),
                            "vorgang_id": "999999"}, follow_redirects=False)
        self.assertIn("nicht+gefunden", r.headers["location"])
        self.assertEqual(self.client.get("/lead-management/todos?vorgang_id=999999").status_code, 200)
        # Glocken-Ziel: HV → To-Do-Liste, Außendienst ohne HV → Meine Termine
        self.assertEqual(lead_todos.link_fuer(self.s, self.hv.id), "/lead-management/todos")
        self.assertEqual(lead_todos.link_fuer(self.s, self.aussen.id), "/lead-management/meine-termine")
        self.assertEqual(lead_todos.link_fuer(self.s, 1), "/lead-management/todos")

    def test_faellige_glocken_einmalig(self):
        todo = lead_todos.anlegen(self.s, self.admin, self.innen.id, f"{PRAEFIX} fällig jetzt",
                                  faellig_am=datetime.now() - timedelta(minutes=5))
        self.s.commit()
        self.assertGreaterEqual(lead_todos.faellige_glocken(self.s), 1)
        self.s.commit()
        abfrage = (self.s.query(Benachrichtigung)
                   .filter(Benachrichtigung.benutzer_id == self.innen.id,
                           Benachrichtigung.text.like(f"To-Do fällig: {PRAEFIX} fällig jetzt%")))
        self.assertEqual(abfrage.count(), 1)
        lead_todos.faellige_glocken(self.s)
        self.s.commit()
        self.assertEqual(abfrage.count(), 1)
        lead_todos.erledigen(self.s, todo, self.innen)
        self.s.commit()

    def test_meine_termine_zeigt_todos_fuer_aussendienst(self):
        """AD-Sicht erst bei Freigabe „alle“ – hier nur für diesen Test umgestellt."""
        todo = lead_todos.anlegen(self.s, self.admin, self.aussen.id, f"{PRAEFIX} AD-Aufgabe")
        self.s.commit()
        kern.parameter_setzen(self.s, "lead_freigabe_modus", "alle")
        self.s.commit()
        try:
            c_ad = self.anmelden(self.aussen)
            seite = c_ad.get("/lead-management/meine-termine")
            self.assertEqual(seite.status_code, 200)
            self.assertIn("Meine To-Dos", seite.text)
            self.assertIn(f"{PRAEFIX} AD-Aufgabe", seite.text)
            self.assertIn(f"/lead-management/todos/{todo.id}/erledigt", seite.text)
            r = c_ad.post(f"/lead-management/todos/{todo.id}/erledigt",
                          data={"zurueck": "/lead-management/meine-termine#todos"},
                          follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertTrue(r.headers["location"].startswith("/lead-management/meine-termine"))
            self.s.expire_all()
            self.assertEqual(self.s.get(Todo, todo.id).status, "erledigt")
        finally:
            kern.parameter_setzen(self.s, "lead_freigabe_modus", "admin")
            self.s.commit()
        # im Demo-Modus bleibt Meine Termine für den AD unsichtbar (404)
        self.assertEqual(self.anmelden(self.aussen).get("/lead-management/meine-termine").status_code, 404)


if __name__ == "__main__":
    unittest.main()
