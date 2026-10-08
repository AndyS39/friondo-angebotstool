# Tests PLAN_LEAD_V2 Phase 107 (CLAUDE v23): Anruf-Workflow & Telefonie –
# Ergebnis mit Dauer, Sperre ab versuche_max, Kaskaden-Auskunft (JSON),
# Kein Interesse Pflichtgrund, Meine Anrufe, Rufnummernsuche E.164,
# Dauer-Korrektur, Fälligkeits-Glocke einmalig, Doppelversand-Schutz,
# Versuchs-Punkte, Handelsvertreter-Gate.
# v25 (PLAN_LEAD_V3 Phase 120): der „Nicht erreicht“-Dialog ist entfallen –
# das Feld wiedervorlage_am wird ignoriert, die Kaskade setzt keine
# Wiedervorlage mehr (Test „Dialog-Zeitpunkt überschreibt die Kaskade“ wurde
# dafür zu „wiedervorlage_am wird ignoriert“; Punkte-Test prüft dlg-rueckruf
# statt dlg-nichterreicht). Laufen im Demo-Modus gegen die Entwicklungs-DB;
# Testleads tragen den Nachnamen „LeadV2A-Test“ und werden aufgeräumt.
import unittest
import warnings
from datetime import datetime, timedelta
from types import SimpleNamespace
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, lead_anrufliste, leadmanagement_logik
from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, KommunikationLog, Kunde,
                        LeadAktivitaet, LeadQuelle, Vorgang)

NACHNAME = "LeadV2A-Test"


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like("LeadV2A %")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
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
        cls.admin = cls.s.get(Benutzer, 1)

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", cls.modus)
        cls.s.commit()
        cls.s.close()

    def lead(self, nr, versuche=0, telefon=None, email=None, **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}", "plz": "47139",
                 "ort": "Duisburg", "telefon": telefon or f"0203 88{nr:04d}", "sparten": ["WP"]}
        if email:
            daten["email"] = email
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        vorgang.demo = True
        vorgang.versuch_nr = versuche
        for i in range(versuche):
            kern.aktivitaet(self.s, vorgang.id, "anruf", "Anruf: Nicht erreicht",
                            benutzer=self.admin, ergebnis="nicht_erreicht")
        if versuche:
            vorgang.lead_phase = "in_kontaktierung"
            vorgang.erstkontakt_am = datetime.now() - timedelta(days=versuche)
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def anrufe(self, vorgang_id):
        return (self.s.query(LeadAktivitaet)
                .filter_by(vorgang_id=vorgang_id, typ="anruf")
                .order_by(LeadAktivitaet.id).all())

    def meldung(self, antwort) -> str:
        ziel = antwort.headers.get("location", "")
        return unquote_plus(ziel.split("meldung=", 1)[1]) if "meldung=" in ziel else ""


class Ergebnis(Basis):
    def test_dauer_wird_gespeichert_und_cti_felder(self):
        v = self.lead(1)
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "mailbox", "dauer_sek": "95", "notiz": "AB"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/lead-management/anrufliste"))
        self.assertIn("Dauer 01:35", self.meldung(r))
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.versuch_nr, 1)
        akt = self.anrufe(v.id)[-1]
        self.assertEqual(akt.dauer_sek, 95)
        self.assertEqual(akt.richtung, "aus")
        self.assertEqual(akt.benutzer_id, 1)
        self.assertEqual(akt.naechste_aktion_am, v.naechste_aktion_am)
        # Dauer als mm:ss und ohne Dauer
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "besetzt", "dauer_sek": "02:05"},
                             follow_redirects=False)
        self.s.expire_all()
        self.assertEqual(self.anrufe(v.id)[-1].dauer_sek, 125)
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "mailbox", "dauer_sek": ""}, follow_redirects=False)
        self.s.expire_all()
        self.assertIsNone(self.anrufe(v.id)[-1].dauer_sek)
        self.assertEqual(self.s.get(Vorgang, v.id).versuch_nr, 3)

    def test_zurueck_nur_relativ(self):
        v = self.lead(2)
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "mailbox", "zurueck": "/lead-management/lead/%d" % v.id},
                             follow_redirects=False)
        self.assertTrue(r.headers["location"].startswith(f"/lead-management/lead/{v.id}?meldung="))
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "mailbox", "zurueck": "https://boese.example/x"},
                             follow_redirects=False)
        self.assertTrue(r.headers["location"].startswith("/lead-management/anrufliste"))
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "mailbox", "zurueck": "//boese.example"},
                             follow_redirects=False)
        self.assertTrue(r.headers["location"].startswith("/lead-management/anrufliste"))

    def test_sperre_ab_versuche_max(self):
        maximal = kern.versuche_max(self.s)
        v = self.lead(3, versuche=maximal, lead_phase="nicht_erreicht",
                      naechste_aktion_am=datetime.now() + timedelta(days=30))
        self.assertTrue(lead_anrufliste.versuche_gesperrt(self.s, v))
        for ergebnis in ("nicht_erreicht", "besetzt", "mailbox"):
            r = self.client.post(f"/lead-management/anruf/{v.id}",
                                 data={"ergebnis": ergebnis}, follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("Höchstzahl erreicht", self.meldung(r))
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.versuch_nr, maximal)              # kein weiterer Zähler
        self.assertEqual(len(self.anrufe(v.id)), maximal)    # keine neue Aktivität
        self.assertEqual(v.lead_phase, "nicht_erreicht")
        # Reaktiviert (Zähler bleibt) → weiterhin gesperrt, Rückruf aber möglich
        v.lead_phase = "in_kontaktierung"
        self.s.commit()
        self.assertTrue(lead_anrufliste.versuche_gesperrt(self.s, v))
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "rueckruf_gewuenscht",
                                   "rueckruf_am": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT10:00")},
                             follow_redirects=False)
        self.assertIn("Rückruf", self.meldung(r))
        # Buttons in der Anrufliste gesperrt (Phase-Filter zeigt den Lead)
        seite = self.client.get("/lead-management/anrufliste?meine=0&phase=in_kontaktierung").text
        zeile = seite.split(f'data-vorgang="{v.id}"', 1)[1].split("</details>", 1)[0]
        self.assertIn("disabled", zeile)
        self.assertIn(lead_anrufliste.SPERRE_MELDUNG, zeile)
        self.assertIn("Versuche</span>", zeile)

    def test_vorschlag_json(self):
        v1 = self.lead(4, versuche=1)
        r = self.client.get(f"/lead-management/anruf/{v1.id}/vorschlag",
                            headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        logik = leadmanagement_logik.hole_logik()
        stufe2 = logik.stufe(2)
        self.assertEqual(d["stufe"], 2)
        self.assertEqual(d["regel"], stufe2.wiedervorlage_nach)
        self.assertEqual(d["aktion"], stufe2.aktion)
        self.assertFalse(d["letzte"])
        self.assertFalse(d["gesperrt"])
        self.assertEqual(d["versuche_max"], kern.versuche_max(self.s))
        zeit = datetime.strptime(d["zeitpunkt"], "%Y-%m-%dT%H:%M")
        self.assertEqual(zeit, kern.kaskade_zeitpunkt(self.s, stufe2.wiedervorlage_nach,
                                                      datetime.now()).replace(second=0, microsecond=0))
        self.assertTrue(d["zeitpunkt_text"])
        # vorletzter → letzte Stufe (disqualifiziert; v29: ohne Nurture +30, kein Zeitpunkt)
        v4 = self.lead(5, versuche=kern.versuche_max(self.s) - 1)
        d = self.client.get(f"/lead-management/anruf/{v4.id}/vorschlag").json()
        self.assertTrue(d["letzte"])
        self.assertEqual(d["aktion"], "mail_disqualifiziert")
        self.assertIn("Disqualifiziert", d["aktion_text"])
        self.assertIsNone(d["zeitpunkt"])
        # gesperrt
        v5 = self.lead(6, versuche=kern.versuche_max(self.s))
        d = self.client.get(f"/lead-management/anruf/{v5.id}/vorschlag").json()
        self.assertTrue(d["gesperrt"])
        self.assertIsNone(d["zeitpunkt"])
        self.assertEqual(d["sperre_meldung"], lead_anrufliste.SPERRE_MELDUNG)
        self.assertEqual(self.client.get("/lead-management/anruf/99999999/vorschlag").status_code, 404)

    def test_wiedervorlage_am_wird_ignoriert(self):
        """v25 (PLAN_LEAD_V3 Phase 120, vorher „Dialog-Zeitpunkt überschreibt die
        Kaskade“): kein Dialog mehr – ein mitgesendetes wiedervorlage_am wird
        ignoriert, die Kaskade setzt keine Wiedervorlage, Mails bleiben an der
        Versuchsnummer, die letzte Stufe leert naechste_aktion_am (Nurture +30)."""
        v = self.lead(7, email="v2a7@test.local")
        wunsch = (datetime.now() + timedelta(days=3)).replace(hour=10, minute=30, second=0, microsecond=0)
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "nicht_erreicht",
                                   "wiedervorlage_am": wunsch.strftime("%Y-%m-%dT%H:%M"),
                                   "notiz": "Nachbar sagt: im Urlaub"},
                             follow_redirects=False)
        self.assertEqual(self.meldung(r), "Nicht erreicht protokolliert (Versuch 1).")
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertIsNone(v.naechste_aktion_am)
        self.assertEqual(v.versuch_nr, 1)
        self.assertEqual(v.lead_phase, "in_kontaktierung")
        akt = self.anrufe(v.id)[-1]
        self.assertIsNone(akt.naechste_aktion_am)
        self.assertIn("im Urlaub", akt.text)
        # Stufe 2 → Mail nicht_erreicht geplant, weiterhin keine Wiedervorlage
        r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "nicht_erreicht"},
                             follow_redirects=False)
        self.assertEqual(self.meldung(r), "Nicht erreicht protokolliert (Versuch 2) – Mail geplant.")
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertIsNone(v.naechste_aktion_am)
        mails = [m.vorlage_key for m in self.s.query(KommunikationLog).filter_by(vorgang_id=v.id)
                 if m.vorlage_key != "eingangsbestaetigung"]
        self.assertEqual(mails, ["nicht_erreicht"])
        # Letzte Stufe: Phase Nicht erreicht, keine Wiedervorlage; v29 (PLAN_LEAD_V4
        # Phase 142): Nurture entfällt – nur noch disqualifiziert, kein Eintrag +30 Tage
        v2 = self.lead(8, versuche=kern.versuche_max(self.s) - 1, email="v2a8@test.local")
        wunsch2 = (datetime.now() + timedelta(days=45)).replace(hour=9, minute=0, second=0, microsecond=0)
        r = self.client.post(f"/lead-management/anruf/{v2.id}",
                             data={"ergebnis": "mailbox",
                                   "wiedervorlage_am": wunsch2.strftime("%Y-%m-%dT%H:%M")},
                             follow_redirects=False)
        self.assertIn("Lead steht auf „Nicht erreicht“", self.meldung(r))
        self.s.expire_all()
        v2 = self.s.get(Vorgang, v2.id)
        self.assertEqual(v2.lead_phase, "nicht_erreicht")
        self.assertIsNone(v2.naechste_aktion_am)
        self.assertEqual(self.s.query(KommunikationLog)
                         .filter_by(vorgang_id=v2.id, vorlage_key="nurture").count(), 0)
        self.assertEqual(self.s.query(KommunikationLog)
                         .filter_by(vorgang_id=v2.id, vorlage_key="disqualifiziert").count(), 1)
        self.assertTrue(lead_anrufliste.versuche_gesperrt(self.s, v2))

    def test_kein_interesse_pflichtgrund(self):
        v = self.lead(9)
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "kein_interesse", "grund": ""}, follow_redirects=False)
        self.assertIn("Grund", self.meldung(r))
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.versuch_nr, 0)                     # nichts protokolliert
        self.assertEqual(v.lead_phase, "neu")
        self.assertEqual(len(self.anrufe(v.id)), 0)
        logik = leadmanagement_logik.hole_logik()
        gruende = logik.gruende_der_phase("unqualifiziert")
        sonstiges = next(g for g in gruende if g.freitext_pflicht)
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "kein_interesse", "grund": sonstiges.grund},
                             follow_redirects=False)
        self.assertIn("Freitext", self.meldung(r))
        normal = next(g for g in gruende if not g.freitext_pflicht)
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "kein_interesse", "grund": normal.grund,
                                   "dauer_sek": "40"}, follow_redirects=False)
        self.assertIn("unqualifiziert", self.meldung(r))
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.lead_phase, "unqualifiziert")
        self.assertEqual(v.unqualifiziert_grund, normal.grund)
        self.assertEqual(v.versuch_nr, 1)
        self.assertEqual(self.anrufe(v.id)[-1].dauer_sek, 40)


class MeineAnrufe(Basis):
    def test_liste_nur_eigene(self):
        eigen = self.lead(10)
        fremd = self.lead(11)
        self.client.post(f"/lead-management/anruf/{eigen.id}",
                         data={"ergebnis": "erreicht", "dauer_sek": "130"}, follow_redirects=False)
        kern.aktivitaet(self.s, fremd.id, "anruf", "Anruf: Mailbox", ergebnis="mailbox",
                        benutzer=SimpleNamespace(id=999999))
        self.s.commit()
        zeilen = lead_anrufliste.anrufe_liste(self.s, 1, zeitraum="heute")
        ids = {z["vorgang"].id for z in zeilen}
        self.assertIn(eigen.id, ids)
        self.assertNotIn(fremd.id, ids)
        treffer = next(z for z in zeilen if z["vorgang"].id == eigen.id)
        self.assertEqual(treffer["dauer"], "02:10")
        self.assertEqual(treffer["ergebnis_name"], "Erreicht")
        self.assertEqual(treffer["tel_href"], "tel:+4920388" + f"{10:04d}")
        seite = self.client.get("/lead-management/anruf/meine?zeitraum=heute").text
        seite = seite.split("<tbody>", 1)[1]          # ohne Glocken-Dropdown der Kopfzeile
        self.assertIn(f"{NACHNAME}-10", seite)
        self.assertNotIn(f"{NACHNAME}-11", seite)
        self.assertIn("02:10", seite)
        self.assertIn(f"/lead-management/lead/{eigen.id}", seite)
        self.assertIn('href="tel:+49', seite)
        # Team-Sicht (Admin) zeigt auch fremde; Filter Ergebnis und Suche nach Nummer
        alle = self.client.get("/lead-management/anruf/meine?zeitraum=heute&alle=1").text
        self.assertIn(f"{NACHNAME}-11", alle.split("<tbody>", 1)[1])
        gefiltert = lead_anrufliste.anrufe_liste(self.s, None, zeitraum="heute", ergebnis="mailbox")
        self.assertIn(fremd.id, {z["vorgang"].id for z in gefiltert})
        self.assertNotIn(eigen.id, {z["vorgang"].id for z in gefiltert})
        suche = lead_anrufliste.anrufe_liste(self.s, None, zeitraum="heute", q="+49 203 88" + f"{11:04d}")
        self.assertEqual({z["vorgang"].id for z in suche}, {fremd.id})
        summen = lead_anrufliste.anrufe_summen(zeilen)
        self.assertEqual(summen["erreicht"], sum(1 for z in zeilen if z["ergebnis"] == "erreicht"))
        self.assertIn("Meine Anrufe", self.client.get("/lead-management/anrufliste?meine=0").text)

    def test_zeitraum_grenzen(self):
        jetzt = datetime(2026, 10, 2, 15, 0)
        von, bis = lead_anrufliste.zeitraum_grenzen("heute", jetzt=jetzt)
        self.assertEqual((von, bis), (datetime(2026, 10, 2), None))
        von, bis = lead_anrufliste.zeitraum_grenzen("7", jetzt=jetzt)
        self.assertEqual(von, datetime(2026, 9, 26))
        von, bis = lead_anrufliste.zeitraum_grenzen("30", "2026-09-01", "2026-09-10", jetzt=jetzt)
        self.assertEqual((von, bis), (datetime(2026, 9, 1), datetime(2026, 9, 11)))
        self.assertEqual(lead_anrufliste.zeitraum_grenzen("alle", jetzt=jetzt), (None, None))


class Rufnummernsuche(Basis):
    def test_normalisierung_und_href(self):
        z = lead_anrufliste._ziffern
        self.assertEqual(z("0203 7791234"), "492037791234")
        self.assertEqual(z("+49 203 7791234"), "492037791234")
        self.assertEqual(z("0049 203 7791234"), "492037791234")
        self.assertEqual(z("+49 (0)203 7791234"), "492037791234")
        self.assertEqual(z("0203 / 77 91 - 234"), "492037791234")
        self.assertEqual(z(""), "")
        self.assertEqual(lead_anrufliste.tel_href("0203 / 77 91 234"), "tel:+49203779 1234".replace(" ", ""))
        self.assertEqual(lead_anrufliste.tel_href(""), "")

    def test_suche_findet_schreibweisen(self):
        v = self.lead(12, telefon="+49 203 7791234")
        for eingabe in ("0203 7791234", "+49 203 7791234", "0049 203 7791234", "+49 (0)203 7791234",
                        "0203/7791234"):
            r = self.client.get("/lead-management/anruf/suche", params={"q": eingabe},
                                follow_redirects=False)
            self.assertEqual(r.status_code, 303, eingabe)
            self.assertEqual(r.headers["location"], f"/lead-management/lead/{v.id}", eingabe)
        # zu kurz, nichts gefunden, Liste erzwingen
        r = self.client.get("/lead-management/anruf/suche?q=0203+77")
        self.assertIn("mindestens", r.text)
        r = self.client.get("/lead-management/anruf/suche?q=0203+7799999")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Keine Rufnummer", r.text)
        r = self.client.get("/lead-management/anruf/suche?q=0203+7791234&liste=1")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f"{NACHNAME}-12", r.text)
        self.assertIn(f"/lead-management/lead/{v.id}", r.text)
        # zweiter Kunde mit derselben Nummer → Trefferliste
        k2 = Kunde(vorname="V13", nachname=f"{NACHNAME}-13", telefon="0203 7791234",
                   plz="47139", ort="Duisburg", interesse="PV")
        self.s.add(k2)
        self.s.flush()
        v2 = Vorgang(kunde_id=k2.id, lead_phase="neu", demo=True, eingang_am=datetime.now(),
                     eingang_art="api")
        self.s.add(v2)
        self.s.commit()
        r = self.client.get("/lead-management/anruf/suche?q=02037791234", follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertIn(f"{NACHNAME}-12", r.text)
        self.assertIn(f"{NACHNAME}-13", r.text)
        ergebnis = lead_anrufliste.rufnummer_suchen(self.s, "0203 7791234")
        self.assertEqual({t["kunde"].id for t in ergebnis["treffer"]}, {v.kunde_id, k2.id})
        self.assertTrue(all(t["vorgang"] is not None for t in ergebnis["treffer"]))
        # Suchfeld in der Anrufliste
        self.assertIn('action="/lead-management/anruf/suche"',
                      self.client.get("/lead-management/anrufliste?meine=0").text)


class DauerKorrektur(Basis):
    def test_korrektur_eigener_eintrag_und_protokoll(self):
        v = self.lead(14)
        self.client.post(f"/lead-management/anruf/{v.id}",
                         data={"ergebnis": "mailbox", "dauer_sek": "20"}, follow_redirects=False)
        self.s.expire_all()
        akt = self.anrufe(v.id)[-1]
        r = self.client.post(f"/lead-management/anruf/aktivitaet/{akt.id}/dauer",
                             data={"dauer_sek": "02:05"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("02:05", self.meldung(r))
        self.assertTrue(r.headers["location"].startswith("/lead-management/anruf/meine"))
        self.s.expire_all()
        self.assertEqual(self.s.get(LeadAktivitaet, akt.id).dauer_sek, 125)
        system = [a for a in self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id, typ="system")
                  if "Anrufdauer korrigiert" in a.text]
        self.assertEqual(len(system), 1)
        self.assertIn("00:20 → 02:05", system[0].text)
        self.assertEqual(system[0].benutzer_id, 1)
        # JSON-Antwort (v17-Muster)
        r = self.client.post(f"/lead-management/anruf/aktivitaet/{akt.id}/dauer",
                             data={"dauer_sek": "300", "zurueck": "/lead-management/anrufliste"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True, "dauer_sek": 300, "dauer": "05:00"})
        r = self.client.post(f"/lead-management/anruf/aktivitaet/{akt.id}/dauer",
                             data={"dauer_sek": "abc"}, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])
        # Fremder Eintrag: nur Admin – ein Innendienstler darf nicht; kein Anruf-Typ auch nicht
        fremd = SimpleNamespace(id=424242, rolle="innendienst")
        fehler = lead_anrufliste.dauer_korrigieren(self.s, akt, 10, fremd)
        self.assertIn("eigene", fehler)
        self.assertEqual(lead_anrufliste.dauer_korrigieren(self.s, system[0], 10, self.admin),
                         "Nur Anruf-Einträge haben eine Dauer.")
        self.assertEqual(lead_anrufliste.dauer_korrigieren(self.s, akt, 300, self.admin), "")
        self.assertEqual(self.client.post("/lead-management/anruf/aktivitaet/99999999/dauer",
                                          data={"dauer_sek": "5"}, follow_redirects=False).status_code, 303)
        self.s.rollback()

    def test_dauer_lesen_und_text(self):
        self.assertEqual(lead_anrufliste.dauer_lesen("95"), 95)
        self.assertEqual(lead_anrufliste.dauer_lesen("1:02:03"), 3723)
        self.assertEqual(lead_anrufliste.dauer_lesen("99999"), lead_anrufliste.DAUER_MAX_SEK)
        self.assertIsNone(lead_anrufliste.dauer_lesen(""))
        self.assertIsNone(lead_anrufliste.dauer_lesen("-5"))
        self.assertIsNone(lead_anrufliste.dauer_lesen("x"))
        self.assertEqual(lead_anrufliste.dauer_text(3723), "1:02:03")
        self.assertEqual(lead_anrufliste.dauer_text(None), "–")


class Glocke(Basis):
    def _anzahl(self, vorgang_id, benutzer_id=1):
        # nur die Fälligkeits-Glocken (lead_anlegen meldet „Neuer Lead“ mit demselben Link)
        return (self.s.query(Benachrichtigung)
                .filter(Benachrichtigung.link == f"/lead-management/lead/{vorgang_id}",
                        Benachrichtigung.benutzer_id == benutzer_id,
                        Benachrichtigung.text.like("%fällig%")).count())

    def test_faelligkeit_einmalig(self):
        # v29 (PLAN_LEAD_V4 Phase 141 „Glocke nur To-Dos“): die Wiedervorlage-Glocke ist
        # standardmäßig gesperrt (art wiedervorlage) – für diesen Dedup-Test wird die
        # Art über glocke_lead_arten wieder eingeschaltet und danach zurückgesetzt
        arten_vorher = kern.parameter_holen(self.s, "glocke_lead_arten", "")
        kern.parameter_setzen(self.s, "glocke_lead_arten",
                              "todo_zugewiesen,todo_aktualisiert,wiedervorlage")
        self.s.commit()

        def zuruecksetzen():
            self.s.rollback()
            kern.parameter_setzen(self.s, "glocke_lead_arten", arten_vorher)
            self.s.commit()
        self.addCleanup(zuruecksetzen)
        faellig = datetime.now() - timedelta(hours=1)
        v = self.lead(15, versuche=2, leadmanager_id=1, naechste_aktion_am=faellig)
        spaeter = self.lead(16, versuche=1, leadmanager_id=1,
                            naechste_aktion_am=datetime.now() + timedelta(hours=3))
        self.assertGreaterEqual(lead_anrufliste.faellige_wiedervorlagen_melden(self.s), 1)
        self.s.commit()
        self.assertEqual(self._anzahl(v.id), 1)
        self.assertEqual(self._anzahl(spaeter.id), 0)
        glocke = (self.s.query(Benachrichtigung)
                  .filter(Benachrichtigung.link == f"/lead-management/lead/{v.id}",
                          Benachrichtigung.text.like("%fällig%")).one())
        self.assertEqual(glocke.art, "lead")
        self.assertIn("Nächster Versuch fällig", glocke.text)
        self.assertIn(f"{NACHNAME}-15", glocke.text)
        # zweiter Lauf: nichts Neues (Dedup über Aktivität typ system)
        lead_anrufliste.faellige_wiedervorlagen_melden(self.s)
        self.s.commit()
        self.assertEqual(self._anzahl(v.id), 1)
        system = [a for a in self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id, typ="system")
                  if a.text.startswith(lead_anrufliste.WV_GEMELDET_TEXT)]
        self.assertEqual(len(system), 1)
        self.assertEqual(system[0].naechste_aktion_am, faellig)
        # Anrufliste rendern löst die Meldung ebenfalls aus (ohne Hook)
        self.client.get("/lead-management/anrufliste?meine=0")
        self.assertEqual(self._anzahl(v.id), 1)
        # neue Fälligkeit (Rückrufwunsch) → genau eine weitere Glocke
        neu = (datetime.now() - timedelta(minutes=5)).replace(microsecond=0)
        kern.aktivitaet(self.s, v.id, "anruf", "Anruf: Rückruf gewünscht", benutzer=self.admin,
                        ergebnis="rueckruf_gewuenscht", naechste_aktion_am=neu)
        v = self.s.get(Vorgang, v.id)
        v.naechste_aktion_am = neu
        self.s.commit()
        self.assertEqual(lead_anrufliste.faellige_wiedervorlagen_melden(self.s), 1)
        self.s.commit()
        self.assertEqual(self._anzahl(v.id), 2)
        self.assertIn("Rückruf gewünscht fällig",
                      self.s.query(Benachrichtigung)
                      .filter(Benachrichtigung.link == f"/lead-management/lead/{v.id}")
                      .order_by(Benachrichtigung.id.desc()).first().text)
        # freier Lead → Leitung (Admin), Text „ohne Leadmanager“
        frei = self.lead(17, versuche=1, leadmanager_id=None,
                         naechste_aktion_am=datetime.now() - timedelta(minutes=1))
        lead_anrufliste.faellige_wiedervorlagen_melden(self.s)
        self.s.commit()
        self.assertGreaterEqual(self._anzahl(frei.id), 1)
        self.assertIn("ohne Leadmanager",
                      self.s.query(Benachrichtigung)
                      .filter(Benachrichtigung.link == f"/lead-management/lead/{frei.id}",
                              Benachrichtigung.text.like("%fällig%")).first().text)
        # zurückgestellt bleibt Sache des Tageslaufs
        zurueck = self.lead(18, lead_phase="zurueckgestellt", leadmanager_id=1,
                            zurueckgestellt_bis=datetime.now() - timedelta(days=1),
                            naechste_aktion_am=datetime.now() - timedelta(days=1))
        lead_anrufliste.faellige_wiedervorlagen_melden(self.s)
        self.s.commit()
        self.assertEqual(self._anzahl(zurueck.id), 0)


class Doppelversand(Basis):
    def test_schutz(self):
        v = self.lead(19, email="v2a19@test.local")
        kern.mail_planen(self.s, v, "nicht_erreicht")
        self.assertTrue(lead_anrufliste.mail_bereits_geplant(self.s, v.id, "nicht_erreicht"))
        self.assertIsNone(lead_anrufliste.mail_planen_einmalig(self.s, v, "nicht_erreicht"))
        # v23 Phase 112: kern.mail_planen schützt jetzt selbst (Hook 107) – Doppel am
        # Schutz vorbei anlegen, um doppelversand_bereinigen zu prüfen
        self.s.add(KommunikationLog(vorgang_id=v.id, kanal="mail", vorlage_key="nicht_erreicht",
                                    an="v2a19@test.local", status="geplant", modus="protokoll"))
        self.s.flush()
        self.assertEqual(lead_anrufliste.doppelversand_bereinigen(self.s, v.id), 1)
        self.s.commit()
        offen = [m for m in self.s.query(KommunikationLog).filter_by(vorgang_id=v.id, vorlage_key="nicht_erreicht")]
        self.assertEqual(sorted(m.status for m in offen), ["geplant", "storniert"])
        self.assertIn("Doppelversand", next(m for m in offen if m.status == "storniert").fehler_text)
        # Kaskade über die Route: nach Stufe 2 genau EIN offener nicht_erreicht-Eintrag
        v2 = self.lead(20, versuche=1, email="v2a20@test.local")
        self.client.post(f"/lead-management/anruf/{v2.id}", data={"ergebnis": "nicht_erreicht"},
                         follow_redirects=False)
        geplant = [m for m in self.s.query(KommunikationLog)
                   .filter_by(vorgang_id=v2.id, vorlage_key="nicht_erreicht", status="geplant")]
        self.assertEqual(len(geplant), 1)
        self.assertEqual(geplant[0].modus, "protokoll")      # Sendesperre im Demo

    def test_storno_bei_kontakt(self):
        """C4-d (Prüfer): Kontakt hergestellt → offene Kaskaden-Mails werden
        storniert, Termin-Mails und bereits protokollierte bleiben unberührt."""
        def offen(vorgang_id):
            return sorted((m.vorlage_key, m.status) for m in
                          self.s.query(KommunikationLog).filter_by(vorgang_id=vorgang_id)
                          if m.vorlage_key != "eingangsbestaetigung")
        # Erreicht: nicht_erreicht + disqualifiziert offen → beide storniert, Hinweis im
        # fehler_text (v29: nurture entfällt – mail_planen liefert dafür None)
        v = self.lead(24, versuche=2, email="v2a24@test.local")
        kern.mail_planen(self.s, v, "nicht_erreicht")
        self.assertIsNone(kern.mail_planen(self.s, v, "nurture", geplant_am=datetime.now() + timedelta(days=30)))
        kern.mail_planen(self.s, v, "disqualifiziert")
        # v23 Phase 112: zweiter Eintrag direkt (mail_planen dedupliziert offene Einträge)
        fertig = KommunikationLog(vorgang_id=v.id, kanal="mail", vorlage_key="nicht_erreicht",
                                  an="v2a24@test.local", status="protokolliert", modus="protokoll")
        self.s.add(fertig)                                   # schon „gesendet“ → bleibt
        self.s.commit()
        r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "erreicht"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        self.assertEqual(offen(v.id), [("disqualifiziert", "storniert"), ("nicht_erreicht", "protokolliert"),
                                       ("nicht_erreicht", "storniert")])
        storno = next(m for m in self.s.query(KommunikationLog).filter_by(vorgang_id=v.id, status="storniert"))
        self.assertIn("Kunde erreicht", storno.fehler_text)
        # Kein Interesse und Rückruf gewünscht stornieren ebenfalls, Meldung nennt die Anzahl
        logik = leadmanagement_logik.hole_logik()
        grund = next(g for g in logik.gruende_der_phase("unqualifiziert") if not g.freitext_pflicht)
        v2 = self.lead(25, versuche=1, email="v2a25@test.local")
        kern.mail_planen(self.s, v2, "disqualifiziert")
        self.s.commit()
        r = self.client.post(f"/lead-management/anruf/{v2.id}",
                             data={"ergebnis": "kein_interesse", "grund": grund.grund},
                             follow_redirects=False)
        self.assertIn("1 geplante Mail storniert", self.meldung(r))
        self.s.expire_all()
        self.assertEqual(offen(v2.id), [("disqualifiziert", "storniert")])
        v3 = self.lead(26, versuche=1, email="v2a26@test.local")
        kern.mail_planen(self.s, v3, "nicht_erreicht")
        self.s.commit()
        r = self.client.post(f"/lead-management/anruf/{v3.id}",
                             data={"ergebnis": "rueckruf_gewuenscht",
                                   "rueckruf_am": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT09:00")},
                             follow_redirects=False)
        self.assertIn("storniert", self.meldung(r))
        self.s.expire_all()
        self.assertEqual(offen(v3.id), [("nicht_erreicht", "storniert")])
        # Direktaufruf: nur die Kaskaden-Vorlagen, nichts mit Termin-Bezug
        self.assertEqual(lead_anrufliste.offene_mails_stornieren(self.s, v3.id), 0)
        # v29: ohne nurture (Vorlage entfällt)
        self.assertEqual(lead_anrufliste.VORGANGS_MAILS, ("nicht_erreicht", "disqualifiziert"))

    def test_rueckruf_ohne_datum_bleibt_folgenlos(self):
        """Pflichtfeld fehlt → 303 mit Meldung, Zähler/Phase unverändert (Rollback)."""
        v = self.lead(27)
        for daten in ({"ergebnis": "rueckruf_gewuenscht"},
                      {"ergebnis": "rueckruf_gewuenscht", "rueckruf_am": "kaputt"}):
            r = self.client.post(f"/lead-management/anruf/{v.id}", data=daten, follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("Pflicht", self.meldung(r))
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual((v.versuch_nr, v.lead_phase, v.erstkontakt_am), (0, "neu", None))
        self.assertEqual(len(self.anrufe(v.id)), 0)


class TelefonLink(Basis):
    def test_makro_e164(self):
        """Makro telefon_link (_komponenten.html): href wie lead_anrufliste.tel_href."""
        from app.templating import templates
        env = templates.env
        vorlage = env.from_string('{% from "_komponenten.html" import telefon_link %}{{ telefon_link(nummer, text, klasse) }}')
        for roh in ("0203 / 77 91 - 234", "+49 203 7791234", "0049 203 7791234", "+49 (0)203 7791234",
                    "0203.7791234"):
            html = vorlage.render(nummer=roh, text="", klasse="lm-tel")
            self.assertIn('href="tel:+492037791234"', html, roh)
            self.assertIn(f"{roh}</a>", html, roh)             # Anzeige bleibt roh
            self.assertIn('class="lm-tel"', html)
            self.assertIn("<svg", html)                        # lokales Symbol, kein CDN
        self.assertEqual(vorlage.render(nummer="", text="", klasse="x").strip(), "")
        self.assertEqual(vorlage.render(nummer=None, text="", klasse="x").strip(), "")
        self.assertIn("</svg> Anrufen</a>", vorlage.render(nummer="0203 1", text="Anrufen", klasse="lk-aktion"))
        # Stoppuhr-Skript bedient auch die Kartei-Anzeige ([data-stoppuhr], Phase 106)
        import pathlib
        js = (pathlib.Path(__file__).resolve().parent.parent / "app" / "static"
              / "lm_anruf.js").read_text(encoding="utf-8")
        self.assertIn("[data-stoppuhr]", js)
        self.assertIn("a[href^=\"tel:\"]", js)
        self.assertIn("lm-anruf-form", js)


class Punkte(Basis):
    def test_makro_mit_und_ohne_versuche(self):
        v = self.lead(21, versuche=2, naechste_aktion_am=datetime.now() - timedelta(minutes=1))
        self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "besetzt"},
                         follow_redirects=False)
        seite = self.client.get("/lead-management/anrufliste?meine=0&phase=in_kontaktierung").text
        zeile = seite.split(f'data-vorgang="{v.id}"', 1)[1].split('class="wer"', 1)[0]
        self.assertIn('class="lm-dots', zeile)
        self.assertEqual(zeile.count("e-nicht_erreicht"), 2)
        self.assertEqual(zeile.count("e-besetzt"), 1)
        self.assertIn("Besetzt · ", zeile)                   # Tooltip Ergebnis · Benutzer
        self.assertIn(self.admin.name, zeile)
        self.assertEqual(zeile.count("<i class=\"\"></i>"), 2)
        self.assertIn("3×", zeile)
        # Kopfblock der Akte ruft das Makro ohne Liste auf → exakt wie v21
        akte = self.client.get(f"/vorgaenge/{v.id}").text
        self.assertEqual(akte.count('<i class="v"></i>'), 3)
        self.assertIn('class="lm-dots warn"', akte)
        # Legende und Tasten unverändert, Stoppuhr-Markup vorhanden (v25: Rückruf-
        # Dialog statt des entfallenen Nicht-erreicht-Dialogs)
        for text in ("Tasten 1 Erreicht · 2 Nicht erreicht · 3 Besetzt · 4 Mailbox · 5 Rückruf · 6 Falsche Nummer · 7 Kein Interesse",
                     'id="lead-panel"', "lm-menue", 'class="lm-stoppuhr"', 'name="dauer_sek"',
                     "lm-anruf-form", "/static/lm_anruf.js", 'id="dlg-rueckruf"',
                     'href="tel:+49203'):
            self.assertIn(text, seite, text)
        punkte = lead_anrufliste.versuche_fuer_punkte(self.s, self.anrufe(v.id))
        self.assertEqual([p["ergebnis"] for p in punkte], ["nicht_erreicht", "nicht_erreicht", "besetzt"])
        self.assertTrue(all(p["benutzer_name"] == self.admin.name for p in punkte))


class HandelsvertreterGate(Basis):
    def test_hv_nur_eigene_leads(self):
        hv = Benutzer(name="LeadV2A Vertreter", rolle="aussendienst", aktiv=True,
                      pin_hash=auth.pin_hash("1234"), email="hv-v2a@test.local")
        self.s.add(hv)
        self.s.flush()
        self.s.add(AdProfil(benutzer_id=hv.id, terminiert_selbst=True))
        self.s.commit()
        eigen = self.lead(22, ad_id=hv.id)
        fremd = self.lead(23)
        c2 = TestClient(app)
        c2.post("/login", data={"benutzer_id": str(hv.id), "pin": "1234"})
        self.assertEqual(c2.post(f"/lead-management/anruf/{fremd.id}", data={"ergebnis": "mailbox"},
                                 follow_redirects=False).status_code, 404)
        r = c2.post(f"/lead-management/anruf/{eigen.id}",
                    data={"ergebnis": "mailbox", "dauer_sek": "7",
                          "zurueck": f"/lead-management/lead/{eigen.id}"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, eigen.id).versuch_nr, 1)
        self.assertEqual(self.anrufe(eigen.id)[-1].benutzer_id, hv.id)
        self.assertEqual(c2.get(f"/lead-management/anruf/{fremd.id}/vorschlag").status_code, 404)
        self.assertEqual(c2.get(f"/lead-management/anruf/{eigen.id}/vorschlag").status_code, 200)
        # v29 (PLAN_LEAD_V4 Phase 140, HV-Sicht – Agent L1): Anrufliste inkl. „Meine
        # Anrufe“ und Rufnummernsuche sind für Handelsvertreter per URL gesperrt
        # (vorher: nur eigene Aktivitäten/Leads). Nachtrag 08.10.2026 (Antwort Andreas):
        # gesperrte Seiten leiten immer mit 303 auf die HV-Ansicht um (statt 404).
        # Innendienst sieht beides weiter.
        for pfad, params in (("/lead-management/anruf/meine", {"zeitraum": "heute"}),
                             ("/lead-management/anruf/suche", {"q": f"0203 88{22:04d}"})):
            r = c2.get(pfad, params=params, follow_redirects=False)
            self.assertEqual(r.status_code, 303, pfad)
            self.assertTrue(r.headers["location"].startswith("/lead-management/handelsvertreter?meldung="), pfad)
        meine = self.client.get("/lead-management/anruf/meine?zeitraum=heute&alle=1")
        self.assertEqual(meine.status_code, 200)
        self.assertIn(f"{NACHNAME}-22", meine.text.split("<tbody>", 1)[1])
        r = self.client.get("/lead-management/anruf/suche", params={"q": f"0203 88{22:04d}"},
                            follow_redirects=False)
        self.assertEqual(r.headers.get("location"), f"/lead-management/lead/{eigen.id}")


if __name__ == "__main__":
    unittest.main()
