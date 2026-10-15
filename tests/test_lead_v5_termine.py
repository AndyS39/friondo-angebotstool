# Tests PLAN_LEAD_V5 (v31, Agent T) – Termine und Mails (Phase 160, Teile b, c, i, j, q,
# t, v, y, z sowie die Vertragsfunktionen für K und B):
#  (b) zweites Objekt, Termin je Objekt (Vormerken), „Terminierung“ bucht beide in
#      einem Schritt (terminierung_aktiv = an), vot_termine.objekt_id/adresse gesetzt,
#      Objekte ohne Termin bleiben offen („1 von 3 Objekten ohne Termin“)
#  (c) Terminbestätigung: gleicher Tag → eine Mail terminbestaetigung_objekte mit
#      {objektliste} und zwei ICS; verschiedene Tage → zwei Mails mit {objektadresse}
#  (i) {sparten}/{sparten_interesse} für WP, PV+KL, GW; Migration ersetzt „WP“ im
#      Vorlagentext (idempotent, zweiter Lauf ohne Meldung)
#  (j) Kaskade: Versuch 2 und 4 keine Mail, Versuch 5 disqualifiziert; nicht_erreicht
#      wird nie geplant, Altbestand storniert der Versand-Job
#  (q) kein Samstag in Vorschlägen, Kalender (5 Tage) und Wunschzeiten; manuelle
#      Buchung am Samstag nur mit Warnhinweis [ANNAHME]
#  (t) „Falsche Nummer“ sendet falsche_telefonnummer nur bei vorhandener E-Mail
#  (v) kranker Vertriebler wird nicht vorgeschlagen (Begründung „krank“), Umbuchung
#      ohne den Kranken (ohne_ad_id), teilweise Abwesenheit tagesgenau
#  (y) terminierung_aktiv = aus: Vorschläge vorhanden (Aktivität „Vorschläge berechnet“),
#      Vormerken/Buchen/Terminierung/Absagen/Vorab 403, kein Outlook-/Graph-Aufruf
#  (z) mail_versand_aktiv = aus: Eingang erzeugt Eintrag gesperrt, kein Graph-Aufruf,
#      Zähler gesperrte_anzahl, „Erneut senden“ erst nach Freischaltung
#  Verträge: vorlage_rendern (fehlende Pflichtdaten), in_warteschlange (fester Text),
#      objekt_termine, Routen mail/vorschau.json und mail/senden
# Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE); Testdaten tragen das Präfix „V31T“ und
# werden aufgeräumt; Graph/Outlook/Routing sind gemockt bzw. aus.
import json
import re
import unittest
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import abwesenheiten, auth, graph_versand, kalender, lead_mail, lead_termin, lead_v5
from app import leadmanagement as kern
from app import objekte as objekte_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, BenutzerAbwesenheit, Einstellung,
                        KommunikationLog, Kunde, LeadAktivitaet, LeadQuelle, Todo, Vorgang,
                        VorgangObjekt, VotTermin, einstellung_holen)

PRAEFIX = "V31T"
NACHNAME = f"{PRAEFIX}-Test"
# Bezugspunkt abseits aller echten Leads (Nordsee), 0.01° Breite ≈ 1,11 km
BASIS = (54.3, 7.6)
PARAMETER = ("lead_freigabe_modus", "terminierung_aktiv", "mail_versand_aktiv", "mail_modus",
             "mail_testadresse", "kalender_sync", "routing_anbieter", "score_aktiv",
             "hv_versandweg", "absender_lead_mails", "glocke_lead_arten", "versuche_max",
             "vorschlaege_anzahl", "kanal_ad_regel", "sparten_langnamen", "termin_konflikt_modus")
PROBE_VORLAGE = "lead_vorlage_v31tprobe"


def aufraeumen(s):
    s.rollback()
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangObjekt).filter_by(vorgang_id=v.id).delete()
            s.query(Todo).filter_by(vorgang_id=v.id).delete()
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            lead_termin.vorschlaege_cache_leeren(v.id)
            lead_termin._PROTOKOLL_ZEITEN.pop(v.id, None)
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(VotTermin).filter_by(ad_id=b.id).delete()
        s.query(BenutzerAbwesenheit).filter_by(benutzer_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.query(Einstellung).filter(Einstellung.name.like(
            f"lead_vorlage_{lead_mail.vertriebler_key(b.id)}%")).delete(synchronize_session=False)
        s.delete(b)
    s.query(Einstellung).filter(Einstellung.name.like(f"{PROBE_VORLAGE}%")).delete(synchronize_session=False)
    s.commit()
    lead_termin.vorschlaege_cache_leeren()


def meldung_aus(r) -> str:
    ort = r.headers.get("location", "")
    return unquote_plus(ort.split("meldung=", 1)[1].split("&", 1)[0]) if "meldung=" in ort else ""


def naechster_werktag(tage: int = 3, stunde: int = 10) -> datetime:
    tag = datetime.now().replace(hour=stunde, minute=0, second=0, microsecond=0) + timedelta(days=tage)
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    return tag


def naechster_samstag() -> datetime:
    tag = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
    while tag.weekday() != 5:
        tag += timedelta(days=1)
    return tag


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        cls.admin = cls.s.get(Benutzer, 1)
        cls.gesichert = {n: (z.wert if (z := cls.s.query(kern.LeadParameter).filter_by(name=n).first()) is not None
                             else None) for n in PARAMETER}
        for name, wert in (("lead_freigabe_modus", "alle"), ("terminierung_aktiv", "an"),
                           ("mail_versand_aktiv", "aus"), ("mail_modus", "protokoll"),
                           ("mail_testadresse", ""), ("kalender_sync", "aus"),
                           ("routing_anbieter", "luftlinie"), ("score_aktiv", "aus"),
                           ("hv_versandweg", "entwurf"), ("absender_lead_mails", "termin@friondo.de"),
                           ("glocke_lead_arten", "todo_zugewiesen,todo_aktualisiert"),
                           ("versuche_max", "5"), ("vorschlaege_anzahl", "3"), ("kanal_ad_regel", ""),
                           ("sparten_langnamen", ""), ("termin_konflikt_modus", "warnen")):
            kern.parameter_setzen(cls.s, name, wert)
        cls.s.commit()
        cls.horst = cls.ad("Horst", ["WP", "PV", "KL", "WB", "GW"], kombi=True, mfh=True, gewerbe=True,
                           gebiet=["47"], telefon="0203 111", email="v31t.horst@test.invalid")
        cls.rudi = cls.ad("Rudi", ["WP", "PV", "KL", "WB", "GW"], kombi=True, mfh=True, gewerbe=True,
                          gebiet=["47"], telefon="0203 222", email="v31t.rudi@test.invalid")
        cls.s.commit()
        # andere fällige Einträge der DB-Kopie während der Läufe aus dem Weg räumen
        cls.verschoben = {}
        for e in cls.s.query(KommunikationLog).filter(KommunikationLog.status == "geplant"):
            cls.verschoben[e.id] = e.geplant_am
            e.geplant_am = (e.geplant_am or datetime.now()) + timedelta(days=3650)
        cls.s.commit()
        lead_mail.scheduler_starten()

    @classmethod
    def tearDownClass(cls):
        cls.s.rollback()
        for eid, geplant in cls.verschoben.items():
            e = cls.s.get(KommunikationLog, eid)
            if e is not None:
                e.geplant_am = geplant
        for name, wert in cls.gesichert.items():
            if wert is None:
                cls.s.query(kern.LeadParameter).filter_by(name=name).delete(synchronize_session=False)
            else:
                kern.parameter_setzen(cls.s, name, wert)
        cls.s.commit()
        aufraeumen(cls.s)
        cls.s.close()

    @classmethod
    def ad(cls, name, sparten, kombi=False, mfh=False, gewerbe=False, gebiet=None,
           telefon="", email="", hv=False):
        b = Benutzer(name=f"{PRAEFIX} {name}", rolle="aussendienst", pin_hash=auth.pin_hash("482913"),
                     vorname=name, email=email, telefon=telefon, aktiv=True)
        cls.s.add(b)
        cls.s.flush()
        cls.s.add(AdProfil(
            benutzer_id=b.id, start_adresse="Duisburg", start_lat=BASIS[0], start_lon=BASIS[1],
            arbeitszeiten=json.dumps({t: ["08:00", "18:00"] for t in ("mo", "di", "mi", "do", "fr")}),
            termin_dauer_min=90, puffer_min=30, max_termine_tag=4,
            gebiet_plz_praefixe=json.dumps(gebiet or []), aktiv_terminierung=not hv,
            terminiert_selbst=hv, kompetenz_sparten=json.dumps(sparten),
            kompetenz_kombi=kombi, kompetenz_mfh=mfh, kompetenz_gewerbe=gewerbe))
        cls.s.flush()
        return b

    def setUp(self):
        self.s.rollback()
        lead_termin.vorschlaege_cache_leeren()
        self.schalter("terminierung_aktiv", "an")
        self.schalter("mail_versand_aktiv", "aus")

    def schalter(self, name, wert):
        kern.parameter_setzen(self.s, name, wert)
        self.s.commit()

    def lead(self, nr, sparten=("WP",), email=True, phase="qualifiziert", ad_id=None, **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"anrede": "Frau", "vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}",
                 "strasse": f"Teststraße {nr}", "plz": "47139", "ort": "Duisburg",
                 "telefon": f"0203 77{nr:04d}", "sparten": list(sparten)}
        if email:
            daten["email"] = f"v31t-{nr}@test.invalid"
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        kunde = self.s.get(Kunde, vorgang.kunde_id)
        kunde.vertriebskanal = "Standard"
        kunde.objektart = "EFH"
        vorgang.lead_phase = phase
        vorgang.ad_id = ad_id
        vorgang.lat, vorgang.lon, vorgang.geocode_status = BASIS[0], BASIS[1], "ok"
        for k, v in extra.items():
            setattr(vorgang, k, v)
        # verwaiste Objekte fremder (gelöschter) Vorgänge mit wiederverwendeter ID abräumen –
        # andere Testdateien löschen ihre Vorgänge ohne vorgang_objekte (Befund 13.10.2026,
        # objekte.objekte_loeschen soll an jeder Vorgangs-Löschung hängen)
        self.s.query(VorgangObjekt).filter_by(vorgang_id=vorgang.id).delete()
        haupt = objekte_modul.hauptobjekt(self.s, vorgang.id, anlegen=True, kunde=kunde)
        haupt.lat, haupt.lon, haupt.geocode_status = BASIS[0], BASIS[1], "ok"
        self.s.commit()
        return vorgang

    def objekt(self, vorgang, nr=2, interessen=("PV",), objektart="MFH", parteien=4, km_nord=2.0):
        o = objekte_modul.objekt_anlegen(self.s, vorgang, strasse=f"Objektweg {nr}", plz="47051",
                                         ort="Duisburg", bezeichnung=f"Objekt {nr}", objektart=objektart,
                                         parteien=parteien, interessen=list(interessen))
        o.lat, o.lon, o.geocode_status = BASIS[0] + km_nord / 111.0, BASIS[1], "ok"
        objekte_modul.hauptobjekt_sync(self.s, objekte_modul.hauptobjekt(self.s, vorgang.id))
        self.s.commit()
        return o

    def mails(self, vorgang_id):
        return [(m.vorlage_key, m.status) for m in
                self.s.query(KommunikationLog).filter_by(vorgang_id=vorgang_id).order_by(KommunikationLog.id)]

    def aktivitaeten(self, vorgang_id):
        return [a.text for a in self.s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang_id)
                .order_by(LeadAktivitaet.id)]

    def frisch(self, obj):
        self.s.expire_all()
        return self.s.get(type(obj), obj.id)

    def vormerken(self, vorgang, objekt, beginn, ad=None):
        ad = ad or self.horst
        r = self.client.post(f"/lead-management/lead/{vorgang.id}/termin/vormerken",
                             json={"objekt_id": objekt.id, "ad_id": ad.id,
                                   "beginn": beginn.strftime("%Y-%m-%dT%H:%M")},
                             headers={"Accept": "application/json"})
        return r


# --- (b) Termine je Objekt, Terminierung bucht alle ------------------------------------------

class B_ObjektTermine(Basis):
    def test_vormerken_je_objekt_und_terminierung_bucht_beide(self):
        v = self.lead(1, sparten=("WP",))
        haupt = objekte_modul.hauptobjekt(self.s, v.id)
        o2 = self.objekt(v, 2, interessen=("PV",))
        o3 = self.objekt(v, 3, interessen=("KL",), km_nord=4.0)
        # Vorschläge je Objekt – Vertrag: objekt_id, objekte, mehrere_objekte
        r = self.client.get(f"/lead-management/lead/{v.id}/termin/vorschlaege.json?objekt_id={o2.id}")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["status"], "ok", d)
        self.assertEqual((d["objekt_id"], d["mehrere_objekte"], len(d["objekte"])), (o2.id, True, 3))
        self.assertTrue(d["buchbar"])
        self.assertTrue(d["vorschlaege"])
        self.assertIn("vormerken_url", d)
        # Assistent fragt das Objekt ab
        r = self.client.get(f"/lead-management/lead/{v.id}/termin?objekt_id={o2.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Objekt wählen", r.text)
        self.assertIn(f"objekt_id={o3.id}", r.text)
        self.assertIn("Vormerken", r.text)
        # Buchen ohne Objekt bei mehreren Objekten → Rückfrage
        r = self.client.post(f"/lead-management/lead/{v.id}/termin",
                             data={"ad_id": str(self.horst.id), "beginn": naechster_werktag().strftime("%Y-%m-%dT%H:%M")},
                             follow_redirects=False)
        self.assertIn("Objekt", meldung_aus(r))
        # Vormerken je Objekt (Hauptobjekt + Objekt 2), Objekt 3 bleibt offen
        tag = naechster_werktag(3, 9)
        r1 = self.vormerken(v, haupt, tag)
        self.assertEqual(r1.status_code, 200, r1.text)
        d1 = r1.json()
        self.assertTrue(d1["ok"])
        self.assertEqual((d1["offen"], d1["gesamt"]), (2, 3))
        r2 = self.vormerken(v, o2, tag + timedelta(hours=3))
        self.assertTrue(r2.json()["ok"], r2.text)
        self.assertIn("1 von 3 Objekten ohne Termin", r2.json()["objekte_hinweis"])
        zeilen = lead_termin.objekt_termine(self.s, v)
        self.assertEqual([z["objekt"].id for z in zeilen], [haupt.id, o2.id, o3.id])
        self.assertEqual([z["vorgemerkt"] for z in zeilen], [True, True, False])
        self.assertEqual(zeilen[1]["termin"].adresse, "Objektweg 2, 47051 Duisburg")
        self.assertEqual(zeilen[1]["termin"].objekt_id, o2.id)
        self.assertEqual(lead_termin.bestaetigung_vorbelegung(lead_termin.vorgemerkte_objekttermine(self.s, v)), "eine")
        self.assertEqual(self.frisch(v).lead_phase, "qualifiziert")   # vorgemerkt kippt die Phase nicht
        # erneutes Vormerken desselben Objekts ersetzt den alten vorgemerkten Termin
        r1b = self.vormerken(v, haupt, tag + timedelta(hours=1), ad=self.rudi)
        self.assertTrue(r1b.json()["ok"])
        self.assertEqual(len(lead_termin.vorgemerkte_objekttermine(self.s, v)), 2)
        # Terminierung bucht beide in einem Schritt (Alias-Route, _speichern-Muster)
        with mock.patch.object(kalender, "termin_schreiben", return_value=False) as outlook:
            r = self.client.post(f"/lead-management/lead/{v.id}/termin/terminierung",
                                 json={"bestaetigung": "eine"}, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        self.assertIn("2 Objekttermine gebucht", r.json()["meldung"])
        self.assertIn("1 von 3 Objekten ohne Termin", r.json()["objekte_hinweis"])
        self.assertEqual(outlook.call_count, 2)
        v = self.frisch(v)
        self.assertEqual(v.lead_phase, "terminiert")
        self.assertEqual(v.ad_id, self.rudi.id)
        termine = lead_mail.objekttermine_aktiv(self.s, v)
        self.assertEqual([t.objekt_id for t in termine], [haupt.id, o2.id])
        self.assertTrue(all(t.status == "geplant" and t.adresse for t in termine))
        mails = self.mails(v.id)
        self.assertEqual([m for m in mails if m[0] == "terminbestaetigung_objekte"], [("terminbestaetigung_objekte", "geplant")])
        self.assertEqual(len([m for m in mails if m[0] == "terminerinnerung"]), 2)
        self.assertNotIn("terminbestaetigung", [m[0] for m in mails])
        # Terminierung ohne vorgemerkte Termine → Hinweis
        r = self.client.post(f"/lead-management/lead/{v.id}/termin/terminierung",
                             json={}, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 422)
        # Absage eines Objekttermins: der andere bleibt, Phase bleibt terminiert
        r = self.client.post(f"/lead-management/termin/{termine[1].id}/absagen",
                             data={"grund": "", "grund_text": "Objekt 2 später"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(self.frisch(termine[1]).status, "abgesagt")
        self.assertEqual(self.frisch(v).lead_phase, "terminiert")
        self.assertEqual([t.id for t in lead_mail.objekttermine_aktiv(self.s, v)], [termine[0].id])

    def test_ein_objekt_bucht_wie_bisher_mit_objektfeldern(self):
        v = self.lead(2)
        haupt = objekte_modul.hauptobjekt(self.s, v.id)
        beginn = naechster_werktag(4, 11)
        with mock.patch.object(kalender, "termin_schreiben", return_value=False):
            r = self.client.post(f"/lead-management/lead/{v.id}/termin",
                                 data={"ad_id": str(self.horst.id), "beginn": beginn.strftime("%Y-%m-%dT%H:%M"),
                                       "quelle": "assistent"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn("gebucht", meldung_aus(r))
        t = self.s.query(VotTermin).filter_by(vorgang_id=v.id).one()
        self.assertEqual((t.status, t.objekt_id, t.adresse), ("geplant", haupt.id, "Teststraße 2, 47139 Duisburg"))
        self.assertEqual(self.frisch(v).lead_phase, "terminiert")
        self.assertEqual([m[0] for m in self.mails(v.id) if m[0].startswith("termin")],
                         ["terminbestaetigung", "terminerinnerung"])


# --- (c) Terminbestätigung bei mehreren Objekten -------------------------------------------

class C_Terminbestaetigung(Basis):
    def _terminiert(self, nr, tag1, tag2):
        v = self.lead(nr, sparten=("WP",))
        haupt = objekte_modul.hauptobjekt(self.s, v.id)
        o2 = self.objekt(v, 2, interessen=("PV",))
        self.assertTrue(self.vormerken(v, haupt, tag1).json()["ok"])
        self.assertTrue(self.vormerken(v, o2, tag2, ad=self.rudi).json()["ok"])
        vorgemerkt = lead_termin.vorgemerkte_objekttermine(self.s, v)
        vorbelegung = lead_termin.bestaetigung_vorbelegung(vorgemerkt)
        with mock.patch.object(kalender, "termin_schreiben", return_value=False):
            r = self.client.post(f"/lead-management/lead/{v.id}/termin/terminierung",
                                 json={"bestaetigung": "auto"}, headers={"Accept": "application/json"})
        self.assertTrue(r.json()["ok"], r.text)
        return v, haupt, o2, vorbelegung

    def test_gleicher_tag_eine_mail_mit_objektliste_und_zwei_ics(self):
        tag = naechster_werktag(5, 9)
        v, haupt, o2, vorbelegung = self._terminiert(10, tag, tag + timedelta(hours=4))
        self.assertEqual(vorbelegung, "eine")
        eintrag = self.s.query(KommunikationLog).filter_by(vorgang_id=v.id, vorlage_key="terminbestaetigung_objekte").one()
        self.assertTrue(lead_mail.rendern(self.s, eintrag))
        self.s.commit()
        html = eintrag.body_html
        self.assertIn("Objekt 1", html)
        self.assertIn("Objekt 2", html)
        self.assertIn("Teststraße 10, 47139 Duisburg", html)
        self.assertIn("Objektweg 2, 47051 Duisburg", html)
        self.assertIn(self.horst.name, html)
        self.assertIn(self.rudi.name, html)
        self.assertIn("Wärmepumpe", html)
        self.assertIn("Photovoltaik", html)
        self.assertNotIn("{objektliste}", html)
        self.assertIn(tag.strftime("%d.%m.%Y"), eintrag.betreff)
        pfade = lead_mail.anhang_pfade(eintrag.anhang_pfad)
        self.assertEqual(len(pfade), 2)
        uids = set()
        for p in pfade:
            inhalt = Path(p).read_text(encoding="utf-8")
            self.assertIn("METHOD:REQUEST", inhalt)
            uids.add(re.search(r"UID:(\S+)", inhalt).group(1))
        self.assertEqual(len(uids), 2)
        inhalt2 = Path(pfade[1]).read_text(encoding="utf-8")
        self.assertIn("Objektweg 2", inhalt2)
        self.assertIn("Objekt 2", inhalt2)
        self.assertIn("Photovoltaik", inhalt2)
        self.assertNotIn("WP+PV", inhalt2)
        # Graph-Versand hängt beide ICS an (Mailsperre an → Versand mit Mock)
        self.schalter("mail_versand_aktiv", "an")
        gesendet = {}

        def graph(methode, pfad, token, daten=None):
            gesendet["nachricht"] = daten["message"]
            return {}
        with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                mock.patch.object(graph_versand, "_graph_aufruf", side_effect=graph):
            self.assertEqual(lead_mail.eintrag_verarbeiten(self.s, eintrag), "gesendet")
        self.s.commit()
        anhaenge = [a for a in gesendet["nachricht"]["attachments"] if a["name"].endswith(".ics")]
        self.assertEqual(len(anhaenge), 2)
        self.assertEqual(gesendet["nachricht"]["toRecipients"][0]["emailAddress"]["address"], f"v31t-10@test.invalid")
        # HV-Vorschau/.eml der Objektvorlage liefert beide ICS
        termine = lead_mail.objekttermine_aktiv(self.s, v)
        r = self.client.get(f"/lead-management/lead/{v.id}/termin/{termine[0].id}/vorschau?vorlage=terminbestaetigung_objekte")
        self.assertEqual(r.status_code, 200)
        self.assertIn("ICS Objekt 2", r.text)
        r = self.client.get(f"/lead-management/lead/{v.id}/termin/{termine[0].id}/vorschau?vorlage=terminbestaetigung_objekte&ics=1&nr=2")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Objektweg 2", r.text)

    def test_verschiedene_tage_je_objekt_eine_mail_mit_objektadresse(self):
        tag = naechster_werktag(6, 9)
        tag2 = naechster_werktag(8, 9) if naechster_werktag(8, 9).date() != tag.date() else tag + timedelta(days=1)
        while tag2.weekday() >= 5 or tag2.date() == tag.date():
            tag2 += timedelta(days=1)
        v, haupt, o2, vorbelegung = self._terminiert(11, tag, tag2)
        self.assertEqual(vorbelegung, "je_objekt")
        eintraege = (self.s.query(KommunikationLog).filter_by(vorgang_id=v.id, vorlage_key="terminbestaetigung")
                     .order_by(KommunikationLog.id).all())
        self.assertEqual(len(eintraege), 2)
        self.assertEqual(self.s.query(KommunikationLog).filter_by(vorgang_id=v.id, vorlage_key="terminbestaetigung_objekte").count(), 0)
        texte = []
        for e in eintraege:
            lead_mail.rendern(self.s, e)
            texte.append(e.body_html)
            self.assertEqual(len(lead_mail.anhang_pfade(e.anhang_pfad)), 1)
        self.s.commit()
        self.assertIn("Teststraße 11, 47139 Duisburg", texte[0])
        self.assertIn("Objektweg 2, 47051 Duisburg", texte[1])
        self.assertNotIn("Objektweg 2", texte[0])
        # {objektadresse} explizit: Vertriebler-Vorlage ohne Änderung nutzbar (Ein-Objekt = Kundenadresse)
        termine = lead_mail.objekttermine_aktiv(self.s, v)
        werte = lead_mail.werte_fuer(self.s, v, termine[1])
        self.assertEqual(werte["objektadresse"], "Objektweg 2, 47051 Duisburg")
        self.assertEqual(werte["adresse"], "Objektweg 2, 47051 Duisburg")
        v1 = self.lead(12)
        t1 = VotTermin(vorgang_id=v1.id, ad_id=self.horst.id, beginn=tag, ende=tag + timedelta(minutes=90),
                       status="geplant", typ="vot", objekt_id=objekte_modul.hauptobjekt(self.s, v1.id).id)
        self.s.add(t1)
        self.s.commit()
        self.assertEqual(lead_mail.werte_fuer(self.s, v1, t1)["objektadresse"], "Teststraße 12, 47139 Duisburg")
        # Bestätigung erneut: Auswahl mehrerer Objekttermine, zusammen = eine Mail
        r = self.client.post(f"/lead-management/termin/{termine[0].id}/bestaetigung-erneut",
                             data={"termin_ids": [str(termine[0].id), str(termine[1].id)], "zusammen": "1"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("2 Objekttermine", meldung_aus(r))
        self.assertEqual(self.s.query(KommunikationLog).filter_by(vorgang_id=v.id, vorlage_key="terminbestaetigung_objekte").count(), 1)
        self.assertEqual(self.frisch(termine[0]).ics_sequence, 1)


# --- (i) Sparten ausgeschrieben, Migration ------------------------------------------------

class I_Sparten(Basis):
    def test_platzhalter_sparten_und_sparten_interesse(self):
        faelle = {("WP",): ("Wärmepumpe", "Interesse an einer Wärmepumpe"),
                  ("PV", "KL"): ("Photovoltaik und Klimaanlage", "Interesse an Photovoltaik und einer Klimaanlage"),
                  ("GW",): ("Gewerbe", "Interesse an einer gewerblichen Lösung")}
        for nr, (sparten, (lang, interesse)) in enumerate(faelle.items(), start=20):
            v = self.lead(nr, sparten=sparten)
            werte = lead_mail.werte_fuer(self.s, v)
            self.assertEqual(werte["sparten"], lang)
            self.assertEqual(werte["sparten_interesse"], interesse)
        # Kontrollwert: Eingangsbestätigung WP+PV ohne Kürzel im Kundentext
        v = self.lead(23, sparten=("WP", "PV"))
        betreff, html, fehlende = lead_mail.vorlage_rendern(self.s, "eingangsbestaetigung", v)
        self.assertEqual(fehlende, [])
        self.assertIn("Wärmepumpe und Photovoltaik", html)
        text = lead_mail.html_zu_text(html)
        self.assertIsNone(re.search(r"\b(WP|PV)\b", text), text)
        # Objekt-Interessen zählen für den Termin des Objekts; ICS-Titel in Langform
        o2 = self.objekt(v, 2, interessen=("KL",))
        t = VotTermin(vorgang_id=v.id, ad_id=self.horst.id, beginn=naechster_werktag(), status="geplant",
                      typ="vot", objekt_id=o2.id, ende=naechster_werktag() + timedelta(minutes=90))
        self.s.add(t)
        self.s.commit()
        self.assertEqual(lead_mail.werte_fuer(self.s, v, t)["sparten"], "Klimaanlage")
        pfad = lead_mail.ics_erstellen(self.s, t, v)
        inhalt = Path(pfad).read_text(encoding="utf-8")
        self.assertIn("Klimaanlage", inhalt)
        self.assertNotIn("KL", inhalt.split("SUMMARY:", 1)[1].split("\r\n", 1)[0])
        # Zwischenüberschrift der Terminhinweise in Langform (Dubletten über Sparten
        # entfallen – mit dem Platzhalter „(Punkte folgen)“ bleibt nur der erste Block)
        bloecke = lead_mail.sparten_hinweise_punkte(["WP", "PV"])
        self.assertEqual(bloecke[0][0], "Wärmepumpe")
        self.assertTrue(all(b[0] not in ("WP", "PV") for b in bloecke))
        self.assertEqual(lead_mail.sparten_hinweise_punkte(["PV"])[0][0], "Photovoltaik")
        # Parameter sparten_langnamen übersteuert
        self.schalter("sparten_langnamen", json.dumps({"KL": "Klimagerät"}))
        try:
            self.assertEqual(lead_mail.werte_fuer(self.s, v, t)["sparten"], "Klimagerät")
        finally:
            self.schalter("sparten_langnamen", "")

    def test_migration_ersetzt_kuerzel_und_ist_idempotent(self):
        from app.models import einstellung_setzen
        einstellung_setzen(self.s, f"{PROBE_VORLAGE}_betreff", "Ihre WP-Anfrage: WP und PV")
        einstellung_setzen(self.s, f"{PROBE_VORLAGE}_text", "Danke für Ihre Anfrage (WP). WP+PV, KL/WB, {sparten}, WPL bleibt, GW.")
        self.s.commit()
        meldungen = lead_mail.migration_v31_mails(self.s)
        self.s.commit()
        probe = [m for m in meldungen if "v31tprobe" in m]
        self.assertEqual(len(probe), 2, meldungen)
        self.assertIn("WP → Wärmepumpe", probe[0])
        self.assertEqual(einstellung_holen(self.s, f"{PROBE_VORLAGE}_betreff", ""),
                         "Ihre WP-Anfrage: Wärmepumpe und Photovoltaik")
        self.assertEqual(einstellung_holen(self.s, f"{PROBE_VORLAGE}_text", ""),
                         "Danke für Ihre Anfrage (Wärmepumpe). Wärmepumpe und Photovoltaik, Klimaanlage und Wallbox, "
                         "{sparten}, WPL bleibt, Gewerbe.")
        zweiter = lead_mail.migration_v31_mails(self.s)
        self.s.commit()
        self.assertEqual([m for m in zweiter if "v31tprobe" in m or "Kürzel" in m], [])
        # neue Vorlagen vorhanden, nicht_erreicht ausgeblendet, im Baum nicht mehr angeboten
        self.assertTrue(lead_mail.vorlage_vorhanden(self.s, "terminbestaetigung_objekte"))
        self.assertTrue(lead_mail.vorlage_vorhanden(self.s, "falsche_telefonnummer"))
        self.assertIn("nicht_erreicht", lead_mail.VORLAGEN_AUSGEBLENDET)
        katalog = {e["key"] for kat in lead_mail.vorlagen_katalog(self.s) for e in kat["eintraege"]}
        self.assertNotIn("nicht_erreicht", katalog)
        self.assertIn("terminbestaetigung_objekte", katalog)
        self.assertIn("falsche_telefonnummer", katalog)
        r = self.client.get("/lead-management/vorlagen")
        self.assertEqual(r.status_code, 200)
        baum = r.text.split('class="lmv-baum', 1)[1].split("</nav>", 1)[0]
        self.assertNotIn("vorlage=nicht_erreicht", baum)
        self.assertIn("vorlage=terminbestaetigung_objekte", baum)
        self.assertIn("vorlage=falsche_telefonnummer", baum)
        r = self.client.get("/lead-management/vorlagen?vorlage=terminbestaetigung_objekte")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Beispielweg 2", r.text)   # Vorschau mit zwei Objektterminen
        self.assertIn("{objektliste}", r.text)


# --- (j) Kaskade ohne nicht_erreicht -------------------------------------------------------

class J_Kaskade(Basis):
    def test_versuch_2_und_4_keine_mail_versuch_5_disqualifiziert(self):
        v = self.lead(30, phase="in_kontaktierung")
        self.s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
        self.s.commit()
        for versuch in (1, 2, 3, 4):
            v.versuch_nr = versuch
            meldung = kern.kaskade_anwenden(self.s, v, self.admin)
            self.s.commit()
            self.assertNotIn("Mail geplant", meldung)
            self.assertEqual(self.mails(v.id), [], f"Versuch {versuch}")
        v.versuch_nr = 5
        kern.kaskade_anwenden(self.s, v, self.admin)
        self.s.commit()
        self.assertEqual(self.mails(v.id), [("disqualifiziert", "geplant")])
        self.assertEqual(self.frisch(v).lead_phase, "nicht_erreicht")
        # nicht_erreicht wird nie mehr geplant; Altbestand storniert der Versand-Job
        self.assertIsNone(kern.mail_planen(self.s, v, "nicht_erreicht"))
        alt = KommunikationLog(vorgang_id=v.id, kanal="mail", vorlage_key="nicht_erreicht",
                               an="v31t-30@test.invalid", status="geplant")
        self.s.add(alt)
        self.s.commit()
        self.assertEqual(lead_mail.eintrag_verarbeiten(self.s, alt), "storniert")
        self.assertIn("v31", alt.fehler_text)
        self.s.commit()
        # Migration storniert offene Altbestände mit Protokoll
        alt2 = KommunikationLog(vorgang_id=v.id, kanal="mail", vorlage_key="nicht_erreicht",
                                an="v31t-30@test.invalid", status="geplant")
        self.s.add(alt2)
        self.s.commit()
        meldungen = lead_mail.migration_v31_mails(self.s)
        self.s.commit()
        self.assertTrue(any("nicht_erreicht storniert" in m for m in meldungen), meldungen)
        self.assertEqual(self.frisch(alt2).status, "storniert")
        self.assertTrue(any("Nicht erreicht" in a for a in self.aktivitaeten(v.id)))


# --- (q) Montag bis Freitag ------------------------------------------------------------------

class Q_MontagBisFreitag(Basis):
    def test_kein_samstag_in_vorschlaegen_kalender_und_wunschzeiten(self):
        v = self.lead(40, wunschzeiten=json.dumps(["samstag", "vormittags"]))
        ergebnis = lead_termin.vorschlaege(self.s, v, anzahl=5)
        self.s.commit()
        self.assertTrue(ergebnis["vorschlaege"])
        self.assertTrue(all(x["beginn"].weekday() < 5 for x in ergebnis["vorschlaege"]))
        # Wunschzeit „samstag“ (aktiv = nein) wird ignoriert, „vormittags“ zählt
        fenster = lead_termin.wunschzeit_fenster(self.s, v)
        self.assertEqual([w.key for w in fenster], ["vormittags"])
        # Kalenderansicht Mo–Fr (5 Spalten) und Wochenkalender
        d = lead_termin.kalender_json(self.s, v, benutzer=self.admin, neu=True)
        self.assertEqual(len(d["tage"]), 5)
        self.assertTrue(all(datetime.strptime(t["datum"], "%Y-%m-%d").weekday() < 5 for t in d["tage"]))
        woche = lead_termin.kalender_woche(self.s, [self.horst.id])
        self.assertEqual(len(woche["tage"]), 5)
        r = self.client.get("/lead-management/kalender?alt=1")   # v33 (Phase 169): alte Wochenansicht
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Sa ", r.text.split("<thead", 1)[1].split("</thead>", 1)[0] if "<thead" in r.text else "")
        r = self.client.get(f"/lead-management/lead/{v.id}/termin")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Mo–Fr", r.text)
        self.assertNotIn("Mo–Sa", r.text)

    def test_manuelle_buchung_am_samstag_nur_mit_warnhinweis(self):
        v = self.lead(41)
        samstag = naechster_samstag()
        daten = {"quelle": "manuell", "ad_id": str(self.horst.id), "datum": samstag.strftime("%Y-%m-%d"),
                 "uhrzeit": "10:00"}
        r = self.client.post(f"/lead-management/lead/{v.id}/termin/manuell", data=daten, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Samstag", r.headers["location"])
        self.assertEqual(self.s.query(VotTermin).filter_by(vorgang_id=v.id).count(), 0)
        with mock.patch.object(kalender, "termin_schreiben", return_value=False):
            r = self.client.post(f"/lead-management/lead/{v.id}/termin/manuell", data=dict(daten, bestaetigt="1"),
                                 follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Samstag", meldung_aus(r))
        t = self.s.query(VotTermin).filter_by(vorgang_id=v.id).one()
        self.assertEqual((t.beginn.weekday(), t.status), (5, "geplant"))
        # Konflikt-JSON meldet den Samstag ebenfalls
        r = self.client.get(f"/lead-management/termin/konflikt?ad_id={self.horst.id}&vorgang_id={v.id}"
                            f"&beginn={samstag.strftime('%Y-%m-%dT%H:%M')}")
        self.assertTrue(any("Samstag" in t for t in r.json()["texte"]))


# --- (t) Falsche Telefonnummer -----------------------------------------------------------------

class T_FalscheNummer(Basis):
    def test_mail_nur_bei_vorhandener_email(self):
        ohne = self.lead(50, email=False)
        ok, meldung = lead_mail.falsche_nummer_mail(self.s, ohne, self.admin)
        self.assertFalse(ok)
        self.assertIn("Keine E-Mail-Adresse", meldung)
        self.assertEqual(self.mails(ohne.id), [])
        mit = self.lead(51, sparten=("WP",))
        ok, meldung = lead_mail.falsche_nummer_mail(self.s, mit, self.admin)
        self.s.commit()
        self.assertTrue(ok, meldung)
        self.assertIn("gesperrt", meldung)   # Mailsperre der Testphase
        eintrag = self.s.query(KommunikationLog).filter_by(vorgang_id=mit.id, vorlage_key="falsche_telefonnummer").one()
        self.assertEqual((eintrag.status, eintrag.absender, eintrag.erstellt_von),
                         ("geplant", "termin@friondo.de", self.admin.id))
        self.assertTrue(lead_mail.rendern(self.s, eintrag))
        self.assertEqual(eintrag.betreff, "Ihre Anfrage bei Friondo: wir erreichen Sie nicht")
        self.assertIn("Interesse an einer Wärmepumpe", eintrag.body_html)
        self.assertIn(self.admin.name, eintrag.body_html)   # {absender}
        self.assertIn("Friondo GmbH", eintrag.body_html)
        self.assertNotIn("{", eintrag.body_html)
        # Doppelversand-Schutz
        ok2, meldung2 = lead_mail.falsche_nummer_mail(self.s, mit, self.admin)
        self.assertFalse(ok2)
        self.assertIn("bereits geplant", meldung2)
        self.assertTrue(any("Falsche Telefonnummer" in a for a in self.aktivitaeten(mit.id)))
        # Versand-Job: gesperrt, kein Graph
        with mock.patch.object(graph_versand, "_graph_aufruf", side_effect=AssertionError("Graph aufgerufen")):
            self.assertEqual(lead_mail.eintrag_verarbeiten(self.s, eintrag), "gesperrt")
        self.s.commit()


# --- (v) Krankheit im Terminassistenten --------------------------------------------------------

class V_Krankheit(Basis):
    def test_kranker_vertriebler_wird_nicht_vorgeschlagen(self):
        v = self.lead(60)
        heute = date.today()
        ok, _, eintrag = abwesenheiten.anlegen(self.s, self.horst.id, "krankheit", heute, heute + timedelta(days=30),
                                               angelegt_von=self.admin.id)
        self.s.commit()
        self.assertTrue(ok)
        try:
            vorfilter = lead_termin.kandidaten(self.s, v, benutzer=self.admin)
            namen = [k["ad"].name for k in vorfilter["kandidaten"]]
            self.assertIn(self.rudi.name, namen)
            self.assertNotIn(self.horst.name, namen)
            grund = next(a["grund"] for a in vorfilter["ausgeschlossen"] if a["ad"].id == self.horst.id)
            self.assertIn("krank", grund)
            ergebnis = lead_termin.vorschlaege(self.s, v, anzahl=5)
            self.s.commit()
            self.assertTrue(ergebnis["vorschlaege"])
            self.assertTrue(all(x["ad"].id != self.horst.id for x in ergebnis["vorschlaege"]))
            r = self.client.get(f"/lead-management/lead/{v.id}/termin")
            self.assertIn("krank", r.text)
            # Umbuchung ohne den kranken Vertriebler (ohne_ad_id) schließt auch Rudi aus
            d = lead_termin.vorschlaege_json(self.s, v, benutzer=self.admin, ohne_ad_id=self.rudi.id)
            self.s.commit()
            self.assertTrue(all(x["ad_id"] not in (self.horst.id, self.rudi.id) for x in d["vorschlaege"]))
            r = self.client.get(f"/lead-management/lead/{v.id}/termin?ohne_ad_id={self.rudi.id}")
            self.assertEqual(r.status_code, 200)
            self.assertIn(f"ohne {self.rudi.name}", r.text)
        finally:
            self.s.query(BenutzerAbwesenheit).filter_by(id=eintrag.id).delete()
            self.s.commit()
            lead_termin.vorschlaege_cache_leeren()
        # teilweise Abwesenheit: nur die Tage im Zeitraum fehlen
        von = naechster_werktag(2).date()
        bis = von + timedelta(days=2)
        ok, _, eintrag = abwesenheiten.anlegen(self.s, self.horst.id, "urlaub", von, bis)
        self.s.commit()
        try:
            ergebnis = lead_termin.vorschlaege(self.s, v, nur_ad_id=self.horst.id, anzahl=5)
            self.s.commit()
            self.assertTrue(ergebnis["vorschlaege"])
            self.assertTrue(all(not (von <= x["beginn"].date() <= bis) for x in ergebnis["vorschlaege"]))
            self.assertTrue(any("abwesend" in g for g in ergebnis["kandidaten_info"][0]["gruende"]))
        finally:
            self.s.query(BenutzerAbwesenheit).filter_by(id=eintrag.id).delete()
            self.s.commit()
            lead_termin.vorschlaege_cache_leeren()


# --- (y) Testphase: Terminierung gesperrt ---------------------------------------------------------

class Y_Testphase(Basis):
    def test_vorschlaege_ja_buchen_403_kein_outlook(self):
        v = self.lead(70)
        self.schalter("terminierung_aktiv", "aus")
        self.schalter("kalender_sync", "an")
        beginn = naechster_werktag(3, 10)
        try:
            with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                    mock.patch.object(graph_versand, "_graph_aufruf", side_effect=AssertionError("Graph aufgerufen")) as graph, \
                    mock.patch.object(kalender, "frei_belegt", return_value=None):
                r = self.client.get(f"/lead-management/lead/{v.id}/termin/vorschlaege.json")
                d = r.json()
                self.assertEqual(d["status"], "ok", d)
                self.assertTrue(d["vorschlaege"])
                self.assertFalse(d["buchbar"])
                self.assertFalse(d["terminierung_aktiv"])
                self.assertEqual(d["testphase_hinweis"], lead_v5.TESTPHASE_HINWEIS)
                self.assertTrue(any(a.startswith("Vorschläge berechnet") for a in self.aktivitaeten(v.id)))
                r = self.client.get(f"/lead-management/lead/{v.id}/termin")
                self.assertEqual(r.status_code, 200)
                self.assertIn(lead_v5.TESTPHASE_HINWEIS, r.text)
                self.assertIn('disabled', r.text)
                json_kopf = {"Accept": "application/json"}
                daten = {"ad_id": self.horst.id, "beginn": beginn.strftime("%Y-%m-%dT%H:%M")}
                r = self.client.post(f"/lead-management/lead/{v.id}/termin/vormerken", json=daten, headers=json_kopf)
                self.assertEqual(r.status_code, 403)
                self.assertEqual(r.json(), {"ok": False, "meldung": lead_v5.TESTPHASE_HINWEIS, "testphase": True})
                r = self.client.post(f"/lead-management/lead/{v.id}/termin", data=daten, headers=json_kopf)
                self.assertEqual(r.status_code, 403)
                r = self.client.post(f"/lead-management/lead/{v.id}/termin/manuell",
                                     data=dict(daten, quelle="manuell"), follow_redirects=False)
                self.assertEqual(r.status_code, 303)
                self.assertEqual(meldung_aus(r), lead_v5.TESTPHASE_HINWEIS)
                r = self.client.post(f"/lead-management/lead/{v.id}/termin/terminierung", json={}, headers=json_kopf)
                self.assertEqual(r.status_code, 403)
                r = self.client.post(f"/lead-management/lead/{v.id}/termin/vorab",
                                     data={"typ": "telefon", "person_id": str(self.horst.id),
                                           "datum": beginn.strftime("%Y-%m-%d"), "uhrzeit": "10:00"},
                                     follow_redirects=False)
                self.assertEqual(r.status_code, 303)
                self.assertEqual(meldung_aus(r), lead_v5.TESTPHASE_HINWEIS)
                # Funktionen direkt: keine Termine, keine Phase, kein Outlook
                termin, meldung, _ = lead_termin.termin_anlegen(self.s, v, self.horst.id, beginn, benutzer=self.admin)
                self.assertIsNone(termin)
                self.assertEqual(meldung, lead_v5.TESTPHASE_HINWEIS)
                self.assertEqual(lead_termin.vorab_anlegen(self.s, v, "telefon", self.horst.id, beginn)[0], None)
                self.assertEqual(self.s.query(VotTermin).filter_by(vorgang_id=v.id).count(), 0)
                self.assertEqual(self.frisch(v).lead_phase, "qualifiziert")
                self.assertEqual(graph.call_count, 0)
                # vorhandener Termin: Absagen und Umbuchen gesperrt
                t = VotTermin(vorgang_id=v.id, ad_id=self.horst.id, beginn=beginn, ende=beginn + timedelta(minutes=90),
                              status="geplant", typ="vot", objekt_id=objekte_modul.hauptobjekt(self.s, v.id).id)
                self.s.add(t)
                self.s.commit()
                r = self.client.post(f"/lead-management/termin/{t.id}/absagen", data={"grund_text": "x"}, headers=json_kopf)
                self.assertEqual(r.status_code, 403)
                r = self.client.post(f"/lead-management/termin/{t.id}/verschieben",
                                     data={"beginn": (beginn + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")},
                                     follow_redirects=False)
                self.assertEqual(meldung_aus(r), lead_v5.TESTPHASE_HINWEIS)
                self.assertEqual(self.frisch(t).status, "geplant")
        finally:
            self.schalter("kalender_sync", "aus")
            self.schalter("terminierung_aktiv", "an")


# --- (z) Testphase: Mailsperre ---------------------------------------------------------------------

class Z_Mailsperre(Basis):
    def test_eingang_erzeugt_gesperrt_kein_graph(self):
        vorher = lead_mail.gesperrte_anzahl(self.s)
        v = self.lead(80, sparten=("WP", "PV"))
        self.assertEqual(self.mails(v.id), [("eingangsbestaetigung", "geplant")])
        eintrag = self.s.query(KommunikationLog).filter_by(vorgang_id=v.id).one()
        eintrag.geplant_am = datetime.now() - timedelta(minutes=1)
        self.s.commit()
        with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                mock.patch.object(graph_versand, "_graph_aufruf", side_effect=AssertionError("Graph aufgerufen")) as graph:
            from app import scheduler
            ergebnis = scheduler.ausfuehren("lead-mail")
        self.assertEqual(graph.call_count, 0)
        self.s.expire_all()
        eintrag = self.s.get(KommunikationLog, eintrag.id)
        self.assertEqual(eintrag.status, "gesperrt")
        self.assertEqual(eintrag.modus, "gesperrt")
        self.assertIn("Wärmepumpe und Photovoltaik", eintrag.body_html)   # gerendert, Vorschau sichtbar
        self.assertEqual(eintrag.fehler_text, lead_v5.MAILSPERRE_HINWEIS)
        self.assertFalse(self.frisch(v).mail_fehler)
        self.assertEqual(self.s.query(Benachrichtigung).filter(Benachrichtigung.art == "system",
                                                               Benachrichtigung.text.like(f"%{NACHNAME}-80%")).count(), 0)
        self.assertEqual(lead_mail.gesperrte_anzahl(self.s), vorher + 1)
        self.assertTrue(any("Mail gesperrt" in a for a in self.aktivitaeten(v.id)))
        # Warteschlangen-Seite zeigt den Status, erneut senden bleibt gesperrt
        r = self.client.get(f"/lead-management/lead/{v.id}/kommunikation")
        self.assertEqual(r.status_code, 200)
        self.assertIn("gesperrt", r.text)
        ok, meldung = lead_mail.erneut_senden(self.s, eintrag, self.admin)
        self.assertFalse(ok)
        self.assertIn(lead_v5.MAILSPERRE_HINWEIS, meldung)
        # Freischaltung: gesperrte Einträge werden nicht automatisch nachgesendet, „Erneut senden“
        # ist der bewusste Klick – Versand an den Kunden (mail_modus ist keine Steuerung mehr)
        self.schalter("mail_versand_aktiv", "an")
        self.schalter("mail_modus", "test")
        gesendet = {}

        def graph_ok(methode, pfad, token, daten=None):
            gesendet["an"] = daten["message"]["toRecipients"][0]["emailAddress"]["address"]
            gesendet["betreff"] = daten["message"]["subject"]
            return {}
        with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                mock.patch.object(graph_versand, "_graph_aufruf", side_effect=AssertionError("Graph aufgerufen")):
            from app import scheduler
            scheduler.ausfuehren("lead-mail")
        self.assertEqual(self.frisch(eintrag).status, "gesperrt")
        ok, meldung = lead_mail.erneut_senden(self.s, eintrag, self.admin)
        self.assertTrue(ok, meldung)
        self.s.commit()
        with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                mock.patch.object(graph_versand, "_graph_aufruf", side_effect=graph_ok):
            self.assertEqual(lead_mail.eintrag_verarbeiten(self.s, eintrag), "gesendet")
        self.s.commit()
        self.assertEqual(gesendet["an"], "v31t-80@test.invalid")
        self.assertNotIn("[TEST", gesendet["betreff"])
        self.schalter("mail_modus", "protokoll")


# --- Verträge mit K: vorlage_rendern, in_warteschlange, Routen -------------------------------------

class K_Vertrag(Basis):
    def test_vorlage_rendern_fehlende_und_in_warteschlange_fester_text(self):
        v = self.lead(90, sparten=("WP",))
        betreff, html, fehlende = lead_mail.vorlage_rendern(self.s, "terminbestaetigung", v, termin=None)
        self.assertTrue(any("Termin" in f for f in fehlende))
        ohne = self.lead(91, email=False)
        _, _, fehlende = lead_mail.vorlage_rendern(self.s, "eingangsbestaetigung", ohne)
        self.assertTrue(any("E-Mail" in f for f in fehlende))
        self.assertIsNone(lead_mail.in_warteschlange(self.s, ohne, "eingangsbestaetigung", "x", "y", benutzer=self.admin))
        # fester Text bleibt beim Rendern durch den Lauf erhalten
        eintrag = lead_mail.in_warteschlange(self.s, v, "disqualifiziert", "Mein Betreff",
                                             "Hallo {briefanrede} – nachbearbeitet.", benutzer=self.admin)
        self.s.commit()
        self.assertIsNotNone(eintrag)
        self.assertEqual((eintrag.kanal, eintrag.erstellt_von, eintrag.status), ("mail_fest", self.admin.id, "geplant"))
        lead_mail.rendern(self.s, eintrag)
        self.assertEqual(eintrag.betreff, "Mein Betreff")
        self.assertIn("nachbearbeitet", eintrag.body_html)
        self.assertEqual(lead_mail.eintrag_verarbeiten(self.s, eintrag), "gesperrt")
        self.s.commit()
        self.assertEqual(eintrag.betreff, "Mein Betreff")
        # Terminvorlage aus dem Dialog bekommt das ICS
        beginn = naechster_werktag(4, 14)
        t = VotTermin(vorgang_id=v.id, ad_id=self.horst.id, beginn=beginn, ende=beginn + timedelta(minutes=90),
                      status="geplant", typ="vot", objekt_id=objekte_modul.hauptobjekt(self.s, v.id).id,
                      adresse="Teststraße 90, 47139 Duisburg")
        self.s.add(t)
        self.s.commit()
        betreff, html, fehlende = lead_mail.vorlage_rendern(self.s, "terminbestaetigung", v, termin=t,
                                                            benutzer=self.admin)
        self.assertEqual(fehlende, [])
        self.assertIn(beginn.strftime("%d.%m.%Y"), betreff)
        e2 = lead_mail.in_warteschlange(self.s, v, "terminbestaetigung", betreff, html, termin=t, benutzer=self.admin)
        self.s.commit()
        self.assertTrue(e2.anhang_pfad and Path(e2.anhang_pfad).exists())
        # Routen des Kartei-Dialogs
        r = self.client.get(f"/lead-management/lead/{v.id}/mail/vorschau.json?vorlage=terminbestaetigung")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["fehlende"], [])
        self.assertEqual(d["termin_id"], t.id)
        self.assertTrue(d["anhaenge"])
        self.assertFalse(d["mail_versand_aktiv"])
        self.assertIn("terminbestaetigung_objekte", [x["key"] for x in d["vorlagen"]])
        r = self.client.get(f"/lead-management/lead/{v.id}/mail/vorschau.json?vorlage=falsche_telefonnummer")
        self.assertIn("Interesse an einer Wärmepumpe", r.json()["html"])
        r = self.client.post(f"/lead-management/lead/{v.id}/mail/senden",
                             json={"vorlage": "falsche_telefonnummer", "betreff": "Rückruf-Nummer?", "text": ""},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        e3 = self.s.get(KommunikationLog, r.json()["eintrag_id"])
        self.assertEqual((e3.betreff, e3.kanal, e3.vorlage_key), ("Rückruf-Nummer?", "mail_fest", "falsche_telefonnummer"))
        self.assertIn("Friondo GmbH", e3.body_html)
        r = self.client.post(f"/lead-management/lead/{ohne.id}/mail/senden",
                             json={"vorlage": "eingangsbestaetigung"}, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("E-Mail", r.json()["meldung"])

    def test_testphase_kontext_und_objekt_termine_leer(self):
        k = lead_termin.testphase_kontext(self.s)
        self.assertEqual(set(k), {"terminierung_aktiv", "testphase_hinweis", "mail_versand_aktiv", "mailsperre_hinweis"})
        v = self.lead(92)
        zeilen = lead_termin.objekt_termine(self.s, v)
        self.assertEqual(len(zeilen), 1)
        self.assertIsNone(zeilen[0]["termin"])
        self.assertEqual(lead_termin.objekte_hinweis(self.s, v), "")
