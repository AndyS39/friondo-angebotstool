# Tests PLAN_LEAD_V3 Phase 118/120 (CLAUDE v25, Agent B): Anrufliste als EINE
# durchgehend sortierte Liste ohne Gruppen (SLA rot → SLA gelb → fällige
# Wiedervorlagen/Rückrufe nach Uhrzeit → Zurückgestellte mit erreichtem Datum →
# Rest nach Eingang), Filter „Vertriebskanal“ (Mehrfach) mit farbigem Kanal-Badge,
# kein Quelle-Select, Phasen-Label „Kontaktiert“ aus dem Blatt Status;
# „Nicht erreicht“ / „Mailbox“ / „Besetzt“ ohne Dialog und ohne Wiedervorlage
# (Versuch +1 mit Zeitstempel, Mails bei Versuch 2/4/letzter, Sperre ab
# versuche_max), „Erreicht“ → Kundenkartei Reiter Termin (score_aktiv aus),
# Tasten/Buttons/Dialoge im HTML, tolerierte Alt-Parameter der Übersichts-Links.
# Laufen im Demo-Modus gegen die Entwicklungs-DB; Testleads tragen den
# Nachnamen „LeadV3A-Test“ und werden aufgeräumt.
import pathlib
import unittest
import warnings
from datetime import datetime, timedelta
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import lead_anrufliste, lead_v2, leadmanagement_logik
from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Benachrichtigung, Benutzer, KommunikationLog, Kunde, LeadAktivitaet,
                        LeadQuelle, Vorgang)

NACHNAME = "LeadV3A-Test"
KASKADEN_MAILS = ("nicht_erreicht", "disqualifiziert", "nurture")


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            s.delete(v)
        s.delete(k)
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
        cls.score = kern.parameter_holen(cls.s, "score_aktiv", "aus")
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", "admin")
        kern.parameter_setzen(cls.s, "score_aktiv", "aus")
        cls.s.commit()
        cls.admin = cls.s.get(Benutzer, 1)

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", cls.modus)
        kern.parameter_setzen(cls.s, "score_aktiv", cls.score)
        cls.s.commit()
        cls.s.close()

    def lead(self, nr, versuche=0, kanal=None, eingang=None, email=None, **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}", "plz": "47139",
                 "ort": "Duisburg", "telefon": f"0203 86{nr:04d}", "sparten": ["WP"]}
        if email:
            daten["email"] = email
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        vorgang.demo = True
        if eingang is not None:
            vorgang.eingang_am = eingang
        vorgang.versuch_nr = versuche
        for _ in range(versuche):
            kern.aktivitaet(self.s, vorgang.id, "anruf", "Anruf: Nicht erreicht",
                            benutzer=self.admin, ergebnis="nicht_erreicht")
        if versuche:
            vorgang.lead_phase = "in_kontaktierung"
            vorgang.erstkontakt_am = min((vorgang.eingang_am or datetime.now())
                                         + timedelta(minutes=10), datetime.now())
        if kanal is not None:
            self.s.get(Kunde, vorgang.kunde_id).vertriebskanal = kanal
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def anrufe(self, vorgang_id):
        return (self.s.query(LeadAktivitaet)
                .filter_by(vorgang_id=vorgang_id, typ="anruf")
                .order_by(LeadAktivitaet.id).all())

    def mails(self, vorgang_id):
        return [(m.vorlage_key, m.status) for m in
                self.s.query(KommunikationLog).filter_by(vorgang_id=vorgang_id)
                .order_by(KommunikationLog.id) if m.vorlage_key in KASKADEN_MAILS]

    def meldung(self, antwort) -> str:
        ziel = antwort.headers.get("location", "")
        return unquote_plus(ziel.split("meldung=", 1)[1]) if "meldung=" in ziel else ""

    def daten(self, **params):
        f = lead_anrufliste.filter_aus_query({"meine": "0", **params})
        return lead_anrufliste.daten(self.s, None, f)

    def seite(self, extra=""):
        return self.client.get(f"/lead-management/anrufliste?meine=0&q={NACHNAME}{extra}").text

    def eingang_sla_gelb(self) -> datetime:
        """Eingangszeitpunkt, der jetzt genau zwischen sla_gruen_min und
        sla_gelb_min Arbeitsminuten liegt (unabhängig von Tageszeit/Wochentag)."""
        jetzt = datetime.now()
        try:
            gruen = int(kern.parameter_holen(self.s, "sla_gruen_min", "30"))
            gelb = int(kern.parameter_holen(self.s, "sla_gelb_min", "60"))
        except ValueError:
            gruen, gelb = 30, 60
        ziel = (gruen + gelb) // 2
        for minuten in range(ziel, 10 * 24 * 60):
            von = jetzt - timedelta(minutes=minuten)
            if kern.arbeitsminuten(self.s, von, jetzt) == ziel:
                return von
        self.skipTest("kein Eingangszeitpunkt für SLA gelb bestimmbar")


class Sortierung(Basis):
    def test_eine_liste_ohne_gruppen_in_reihenfolge(self):
        jetzt = datetime.now()
        rot = self.lead(1, eingang=jetzt - timedelta(days=3))                 # SLA rot, kein Versuch
        gelb = self.lead(2, eingang=self.eingang_sla_gelb())                   # SLA gelb
        wv = self.lead(3, versuche=2, eingang=jetzt - timedelta(days=1),      # manuelle WV fällig
                       naechste_aktion_am=jetzt - timedelta(hours=2))
        rueck = self.lead(4, versuche=1, eingang=jetzt - timedelta(days=1),
                          naechste_aktion_am=jetzt - timedelta(minutes=30))   # Rückruf fällig
        kern.aktivitaet(self.s, rueck.id, "anruf", "Anruf: Rückruf gewünscht", benutzer=self.admin,
                        ergebnis="rueckruf_gewuenscht", naechste_aktion_am=rueck.naechste_aktion_am)
        rueck.versuch_nr = 2
        zur = self.lead(5, versuche=1, eingang=jetzt - timedelta(days=5), lead_phase="zurueckgestellt",
                        zurueckgestellt_bis=jetzt - timedelta(hours=1), zurueckgestellt_grund="Urlaub")
        rest_alt = self.lead(6, versuche=1, eingang=jetzt - timedelta(days=2))   # erfüllt, keine WV
        rest_neu = self.lead(7, eingang=jetzt - timedelta(minutes=1))            # SLA grün
        spaeter = self.lead(8, versuche=1, eingang=jetzt - timedelta(days=1),
                            naechste_aktion_am=jetzt + timedelta(days=2))       # WV in der Zukunft → Rest
        self.s.commit()
        d = self.daten()
        self.assertNotIn("gruppen", d)
        ids = [z["vorgang"].id for z in d["zeilen"]]
        for v in (rot, gelb, wv, rueck, zur, rest_alt, rest_neu, spaeter):
            self.assertIn(v.id, ids)
        rang = {z["vorgang"].id: z["rang"] for z in d["zeilen"]}
        self.assertEqual([rang[v.id] for v in (rot, gelb, wv, rueck, zur, rest_alt, rest_neu, spaeter)],
                         [0, 1, 2, 2, 3, 4, 4, 4])
        pos = {v.id: ids.index(v.id) for v in (rot, gelb, wv, rueck, zur, rest_alt, rest_neu, spaeter)}
        # SLA rot → SLA gelb → fällig nach Uhrzeit (WV −2h vor Rückruf −30 min) →
        # zurückgestellt → Rest nach Eingang (älteste zuerst)
        self.assertLess(pos[rot.id], pos[gelb.id])
        self.assertLess(pos[gelb.id], pos[wv.id])
        self.assertLess(pos[wv.id], pos[rueck.id])
        self.assertLess(pos[rueck.id], pos[zur.id])
        self.assertLess(pos[zur.id], pos[rest_alt.id])
        self.assertLess(pos[rest_alt.id], pos[spaeter.id])
        self.assertLess(pos[spaeter.id], pos[rest_neu.id])
        # keine Score-Komponente: Sortierschlüssel enthält nur Rang + Zeiten
        self.assertTrue(all(len(z["_sortierung"]) <= 3 for z in d["zeilen"]))
        # Kontaktstatus-Sätze
        satz = {z["vorgang"].id: " · ".join(t for t, _ in z["satz"]) for z in d["zeilen"]}
        self.assertIn("noch nicht angerufen", satz[rot.id])
        self.assertIn("Rückruf gewünscht", satz[rueck.id])
        self.assertIn("Wiedervorlage", satz[wv.id])
        self.assertNotIn("nächster Versuch", satz[wv.id])
        self.assertIn("heute fällig", satz[zur.id])
        # Seite: keine Gruppenköpfe, Reihenfolge wie in den Daten, Sortierhinweis
        seite = self.seite()
        inhalt = seite.split("<main", 1)[1]
        for text in ("Jetzt dran", "Weiter versuchen", "Neu heute", "Wiedervorlagen fällig",
                     "Sonstige offene", "lm-gruppe-kopf", "<details open", "<summary class=\"lm-gruppe"):
            self.assertNotIn(text, inhalt, text)
        self.assertIn('class="lm-sortierung"', inhalt)
        self.assertIn("SLA rot", inhalt)
        html_pos = {v.id: inhalt.index(f'data-vorgang="{v.id}"') for v in (rot, gelb, wv, rueck, zur, rest_alt, rest_neu)}
        self.assertEqual(sorted(html_pos, key=html_pos.get),
                         [rot.id, gelb.id, wv.id, rueck.id, zur.id, rest_alt.id, rest_neu.id])
        self.assertIn(f'data-vorgang="{rot.id}" data-rang="0"', inhalt)
        # Chips zählen weiter wie die Filter treffen
        self.assertEqual(d["zaehler"]["arbeitsliste"], d["offen"])
        for chip, param in (("sla_rot", {"sla": "rot"}), ("drei", {"versuche_min": "3"}),
                            ("rueckruf", {"rueckruf": "heute"}), ("frei", {"frei": "1"})):
            self.assertEqual(d["zaehler"][chip], self.daten(**param)["offen"], chip)


class KanalFilter(Basis):
    def test_mehrfachauswahl_badge_und_kein_quelle_select(self):
        enni = self.lead(11, kanal="Enni")
        swd = self.lead(12, kanal="SWD")
        ohne = self.lead(13)
        alle = {z["vorgang"].id for z in self.daten()["zeilen"]}
        self.assertTrue({enni.id, swd.id, ohne.id} <= alle)
        # Mehrfach: Dict mit Liste, Mehrfach-Parameter (?kanal=A&kanal=B) und „A,B“
        for kanal in (["Enni", "SWD"], "Enni,SWD", ["enni, swd"]):
            ids = {z["vorgang"].id for z in self.daten(kanal=kanal)["zeilen"]}
            self.assertIn(enni.id, ids, kanal)
            self.assertIn(swd.id, ids, kanal)
            self.assertNotIn(ohne.id, ids, kanal)
        nur_enni = {z["vorgang"].id for z in self.daten(kanal="Enni")["zeilen"]}
        self.assertIn(enni.id, nur_enni)
        self.assertNotIn(swd.id, nur_enni)
        # „Standard“ = Kunden ohne Vertriebskanal
        standard = {z["vorgang"].id for z in self.daten(kanal="Standard")["zeilen"]}
        self.assertIn(ohne.id, standard)
        self.assertNotIn(enni.id, standard)
        # Optionen: kern.kanal_werte (Standard zuerst) + Kanäle der Liste, Farben, aktiv
        d = self.daten(kanal=["Enni"])
        werte = [k["wert"] for k in d["kanaele"]]
        self.assertEqual(werte[0], "Standard")
        self.assertEqual(werte[:len(kern.kanal_werte(self.s))], kern.kanal_werte(self.s))
        self.assertIn("SWD", werte)
        je_wert = {k["wert"]: k for k in d["kanaele"]}
        self.assertTrue(je_wert["Enni"]["aktiv"])
        self.assertFalse(je_wert["SWD"]["aktiv"])
        self.assertEqual(je_wert["Standard"]["farbe"], "")
        self.assertTrue(je_wert["Enni"]["farbe"].startswith("#"))
        # Zeile: Kanal-Badge farbig (--f), kein Quelle-Badge
        zeile = next(z for z in d["zeilen"] if z["vorgang"].id == enni.id)
        self.assertEqual(zeile["kanal"], "Enni")
        self.assertEqual(zeile["kanal_farbe"], je_wert["Enni"]["farbe"])
        seite = self.seite("&kanal=Enni&kanal=SWD")
        inhalt = seite.split("<main", 1)[1]
        self.assertIn(f'data-vorgang="{enni.id}"', inhalt)
        self.assertIn(f'data-vorgang="{swd.id}"', inhalt)
        self.assertNotIn(f'data-vorgang="{ohne.id}"', inhalt)
        self.assertIn('class="lm-kanal mit-farbe" style="--f:' + je_wert["Enni"]["farbe"], inhalt)
        self.assertIn('name="kanal" value="Enni" checked', inhalt)
        self.assertIn('name="kanal" value="SWD" checked', inhalt)
        self.assertIn("Vertriebskanal: Enni, SWD", inhalt)
        self.assertIn('class="lm-mehrfach aktiv"', inhalt)
        for text in ('name="quelle_typ"', 'name="quelle_id"', "Einzelquelle", "Quelle: alle",
                     "lm-quelle", "quelle_badge"):
            self.assertNotIn(text, inhalt, text)
        self.assertIn('class="lm-mehrfach "', self.seite().split("<main", 1)[1])


class NichtErreichtOhneDialog(Basis):
    def test_versuch_mit_zeitstempel_ohne_wiedervorlage_mails_und_sperre(self):
        maximal = kern.versuche_max(self.s)
        wv = (datetime.now() + timedelta(days=3)).replace(second=0, microsecond=0)
        v = self.lead(21, email="v3a21@test.local", naechste_aktion_am=wv)   # manuelle Wiedervorlage
        # 1. Versuch: Nicht erreicht – Zeitstempel jetzt, Wiedervorlage unverändert, keine Mail
        vor = datetime.now()
        r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "nicht_erreicht"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/lead-management/anrufliste"))
        self.assertEqual(self.meldung(r), "Nicht erreicht protokolliert (Versuch 1).")
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.versuch_nr, 1)
        self.assertEqual(v.lead_phase, "in_kontaktierung")
        self.assertEqual(v.naechste_aktion_am, wv)
        akt = self.anrufe(v.id)[-1]
        self.assertEqual(akt.ergebnis, "nicht_erreicht")
        self.assertIsNone(akt.naechste_aktion_am)
        self.assertLessEqual(abs((akt.zeitpunkt - vor).total_seconds()), 60)
        self.assertEqual(akt.richtung, "aus")
        self.assertEqual(self.mails(v.id), [])
        # 2. Versuch: Mailbox – ein mitgesendetes wiedervorlage_am wird ignoriert, Mail geplant
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "mailbox", "wiedervorlage_am": "2031-01-01T10:00",
                                   "dauer_sek": "12"}, follow_redirects=False)
        self.assertIn("Mailbox protokolliert (Versuch 2) – Mail geplant.", self.meldung(r))
        self.assertIn("Dauer 00:12", self.meldung(r))
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.naechste_aktion_am, wv)
        self.assertEqual(self.anrufe(v.id)[-1].dauer_sek, 12)
        self.assertIsNone(self.anrufe(v.id)[-1].naechste_aktion_am)
        self.assertEqual(self.mails(v.id), [("nicht_erreicht", "geplant")])
        # 3. Versuch: Besetzt – keine Mail, Kontrollwert 3 Punkte orange
        r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "besetzt"},
                             follow_redirects=False)
        self.assertEqual(self.meldung(r), "Besetzt protokolliert (Versuch 3).")
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.versuch_nr, 3)
        self.assertEqual(v.naechste_aktion_am, wv)
        self.assertEqual(self.mails(v.id), [("nicht_erreicht", "geplant")])
        punkte = lead_anrufliste.versuche_fuer_punkte(self.s, self.anrufe(v.id))
        self.assertEqual([p["ergebnis"] for p in punkte], ["nicht_erreicht", "mailbox", "besetzt"])
        zeile = self.seite().split(f'data-vorgang="{v.id}"', 1)[1].split('class="wer"', 1)[0]
        self.assertIn('class="lm-dots warn je-ergebnis"', zeile)
        self.assertIn('<small class="lm-warn">3×</small>', zeile)
        # Versuch 4: zweite Mail nicht_erreicht (die erste gilt als versendet)
        for m in self.s.query(KommunikationLog).filter_by(vorgang_id=v.id, vorlage_key="nicht_erreicht"):
            m.status = "protokolliert"
        self.s.commit()
        if maximal > 4:
            r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "nicht_erreicht"},
                                 follow_redirects=False)
            self.assertIn("(Versuch 4) – Mail geplant.", self.meldung(r))
            self.s.expire_all()
            self.assertEqual(self.mails(v.id), [("nicht_erreicht", "protokolliert"),
                                                ("nicht_erreicht", "geplant")])
            for n in range(5, maximal):
                self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "nicht_erreicht"},
                                 follow_redirects=False)
        # letzter Versuch: Phase Nicht erreicht, disqualifiziert + Nurture +30, WV geleert
        r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "nicht_erreicht"},
                             follow_redirects=False)
        m = self.meldung(r)
        self.assertIn(f"Nicht erreicht protokolliert (Versuch {maximal})", m)
        self.assertIn("Kaskade ausgeschöpft, Lead steht auf „Nicht erreicht“", m)
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.versuch_nr, maximal)
        self.assertEqual(v.lead_phase, "nicht_erreicht")
        self.assertIsNone(v.naechste_aktion_am)
        offen = {k for k, status in self.mails(v.id) if status == "geplant"}
        self.assertTrue({"disqualifiziert", "nurture"} <= offen)
        nurture = self.s.query(KommunikationLog).filter_by(vorgang_id=v.id, vorlage_key="nurture").one()
        self.assertGreater(nurture.geplant_am, datetime.now() + timedelta(days=29))
        self.assertTrue(lead_anrufliste.versuche_gesperrt(self.s, v))
        # Sperre: kein weiterer Zähler, keine Aktivität
        for ergebnis in ("nicht_erreicht", "mailbox", "besetzt"):
            r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": ergebnis},
                                 follow_redirects=False)
            self.assertEqual(self.meldung(r), lead_anrufliste.SPERRE_MELDUNG)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).versuch_nr, maximal)
        self.assertEqual(len(self.anrufe(v.id)), maximal)

    def test_kontrollwert_drei_versuche_letzter_nicht_erreicht(self):
        """Plan-Kontrollwert: Demo-Lead mit 3 Versuchen, letzter „Nicht erreicht“ →
        Aktivität mit Zeitstempel, wiedervorlage leer, 3 Punkte orange, keine Mail."""
        v = self.lead(22, versuche=2, email="v3a22@test.local")
        for m in self.s.query(KommunikationLog).filter_by(vorgang_id=v.id):
            if m.vorlage_key in KASKADEN_MAILS:
                self.s.delete(m)
        self.s.commit()
        vor = datetime.now().replace(microsecond=0)
        r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "nicht_erreicht"},
                             follow_redirects=False)
        self.assertEqual(self.meldung(r), "Nicht erreicht protokolliert (Versuch 3).")
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        akt = self.anrufe(v.id)[-1]
        self.assertGreaterEqual(akt.zeitpunkt, vor)
        self.assertIsNone(akt.naechste_aktion_am)
        self.assertIsNone(v.naechste_aktion_am)
        self.assertEqual(v.versuch_nr, 3)
        self.assertEqual(self.mails(v.id), [])          # Mail nur bei Versuch 2, 4 und 5
        punkte = lead_anrufliste.versuche_fuer_punkte(self.s, self.anrufe(v.id))
        self.assertEqual(len(punkte), 3)
        zeile = self.seite().split(f'data-vorgang="{v.id}"', 1)[1].split('class="wer"', 1)[0]
        self.assertIn('lm-dots warn', zeile)
        self.assertIn("3×", zeile)
        # Satz ohne „nächster Versuch“ – es gibt keine automatische Wiedervorlage
        satz = " · ".join(t for t, _ in next(z for z in self.daten()["zeilen"]
                                             if z["vorgang"].id == v.id)["satz"])
        self.assertIn("3× nicht erreicht", satz)
        self.assertNotIn("nächster Versuch", satz)
        self.assertNotIn("Wiedervorlage", satz)


class Erreicht(Basis):
    def test_redirect_kartei_oder_bogen(self):
        v = self.lead(31)
        self.assertFalse(lead_v2.score_aktiv(self.s))
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "erreicht", "dauer_sek": "61"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith(f"/lead-management/lead/{v.id}?tab=termin"),
                        r.headers["location"])
        self.assertIn("Erreicht protokolliert (Versuch 1)", self.meldung(r))
        self.assertIn("Dauer 01:01", self.meldung(r))
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertIsNotNone(v.erreicht_am)
        self.assertEqual(v.versuch_nr, 1)
        self.assertEqual(self.client.get(r.headers["location"]).status_code, 200)
        # score_aktiv an → wie v23 in den Qualifizierungsbogen
        kern.parameter_setzen(self.s, "score_aktiv", "an")
        self.s.commit()
        try:
            v2 = self.lead(32)
            r = self.client.post(f"/lead-management/anruf/{v2.id}", data={"ergebnis": "erreicht"},
                                 follow_redirects=False)
            self.assertEqual(r.headers["location"], f"/lead-management/lead/{v2.id}/qualifizierung/WP")
        finally:
            kern.parameter_setzen(self.s, "score_aktiv", "aus")
            self.s.commit()


class Oberflaeche(Basis):
    def test_tasten_buttons_dialoge_und_vorschlag_route(self):
        v = self.lead(41)
        seite = self.seite()
        inhalt = seite.split("<main", 1)[1]
        zeile = inhalt.split(f'data-vorgang="{v.id}"', 1)[1].split('<aside', 1)[0]
        # Nicht erreicht / Mailbox / Besetzt = normale Ergebnis-Buttons im lm-anruf-form
        for text in ('name="ergebnis" value="erreicht"', 'name="ergebnis" value="nicht_erreicht"',
                     'name="ergebnis" value="mailbox"', 'name="ergebnis" value="besetzt"',
                     'name="ergebnis" value="falsche_nummer"', "keine automatische Wiedervorlage",
                     "dialogOeffnen('rueckruf'", "dialogOeffnen('keininteresse'",
                     'class="lm-stoppuhr"', 'name="dauer_sek"'):
            self.assertIn(text, zeile, text)
        self.assertNotIn("dialogOeffnen('nichterreicht'", zeile)
        for text in ('"2": "nicht_erreicht"', '"4": "mailbox"', '"3": "besetzt"',
                     "Tasten 1 Erreicht · 2 Nicht erreicht · 3 Besetzt · 4 Mailbox · 5 Rückruf · 6 Falsche Nummer · 7 Kein Interesse",
                     'id="dlg-rueckruf"', 'id="dlg-keininteresse"', 'id="dlg-zurueck"',
                     'id="dlg-reaktivieren"', 'id="lm-direkt-form"', "dialogDirekt",
                     "/static/lm_anruf.js", 'id="lead-panel"', "lm-menue", "öffnet die Kundenkartei, Reiter Termin"):
            self.assertIn(text, inhalt, text)
        for text in ('id="dlg-nichterreicht"', "lmVorschlagLaden", "/vorschlag",
                     'name="wiedervorlage_am"', "Kaskaden-Vorschlag", 'name="klasse"',
                     'class="klasse"', 'Qualifizierungsbogen'):
            self.assertNotIn(text, inhalt, text)
        self.assertIn("ohne-klasse", inhalt)
        # Phase-Select mit Labels aus dem Blatt Status: beide Kontakt-Phasen → eine Option
        logik = leadmanagement_logik.hole_logik()
        optionen = dict(lead_anrufliste.phasen_optionen(logik))
        wert = next(w for w in optionen if "in_kontaktierung" in w)
        self.assertIn("qualifiziert", wert.split(","))
        self.assertEqual(optionen[wert], logik.status_zeile("in_kontaktierung").label)
        self.assertEqual(optionen[wert], "Kontaktiert")
        self.assertIn(f'<option value="{wert}"', inhalt)
        self.assertNotIn(">Qualifiziert<", inhalt)
        # Kaskaden-Auskunft bleibt erreichbar (wird nicht mehr aufgerufen)
        r = self.client.get(f"/lead-management/anruf/{v.id}/vorschlag")
        self.assertEqual(r.status_code, 200)
        self.assertIn("hinweis", r.json())
        self.assertEqual(r.json()["stufe"], 1)
        # Stoppuhr-Skript: Direktversand-Helfer, kein Vorschlag mehr
        js = (pathlib.Path(__file__).resolve().parent.parent / "app" / "static"
              / "lm_anruf.js").read_text(encoding="utf-8")
        self.assertIn("ergebnisSenden", js)
        self.assertIn("lm-anruf-form", js)
        self.assertNotIn("/vorschlag`", js)
        # Makro bleibt für Kartei/Infoabend kompatibel: dialogOeffnen('nichterreicht') sendet direkt
        from app.templating import templates
        html = templates.env.from_string(
            '{% from "leadmanagement/anruf_dialoge.html" import anruf_dialoge %}'
            '{{ anruf_dialoge([], [], "/lead-management/lead/5?tab=anrufe") }}').render()
        self.assertIn('id="lm-direkt-form"', html)
        self.assertIn("nichterreicht: 'nicht_erreicht'", html)
        self.assertIn('name="zurueck" value="/lead-management/lead/5?tab=anrufe"', html)
        self.assertNotIn('id="dlg-nichterreicht"', html)
        self.assertIn('id="dlg-rueckruf"', html)

    def test_alte_parameter_der_uebersichtslinks_toleriert(self):
        v = self.lead(42, versuche=1, naechste_aktion_am=datetime.now() - timedelta(minutes=5))
        f = lead_anrufliste.filter_aus_query({"meine": "0", "gruppe": "dran", "klasse": ""})
        self.assertEqual(f["gruppe"], "dran")
        ohne = {z["vorgang"].id for z in self.daten()["zeilen"]}
        mit = {z["vorgang"].id for z in self.daten(gruppe="dran")["zeilen"]}
        self.assertEqual(ohne, mit)                       # gruppe wird ignoriert
        self.assertIn(v.id, mit)
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        for url in (f"/lead-management/anrufliste?gruppe=dran",
                    f"/lead-management/anrufliste?meine=0&quelle_id={quelle.id}&kampagne_id=0",
                    "/lead-management/anrufliste?meine=0&quelle_typ=portal",
                    "/lead-management/anrufliste?meine=0&klasse=A&kanal=&phase=in_kontaktierung,qualifiziert",
                    "/lead-management/anrufliste?meine=0&sla=rot&gruppe=weiter"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
        # quelle_id / quelle_typ filtern weiter (Abzeichen statt Select)
        r = self.client.get(f"/lead-management/anrufliste?meine=0&quelle_id={quelle.id}&q={NACHNAME}")
        self.assertIn(f"Quelle: {quelle.name}", r.text)
        self.assertIn(f'data-vorgang="{v.id}"', r.text)
        r = self.client.get(f"/lead-management/anrufliste?meine=0&quelle_typ=portal&q={NACHNAME}")
        self.assertIn("Quellen-Typ: Lead-Portale", r.text)
        self.assertNotIn(f'data-vorgang="{v.id}"', r.text)
        self.assertNotIn("nur „Jetzt dran“", r.text)
        # Rufnummernsuche zeigt das Status-Label „Kontaktiert“
        r = self.client.get(f"/lead-management/anruf/suche?q=0203+86{42:04d}&liste=1")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Kontaktiert", r.text.split("<tbody>", 1)[1])
        self.assertNotIn("In Kontaktierung", r.text.split("<tbody>", 1)[1])


if __name__ == "__main__":
    unittest.main()
