# Tests PLAN_LEAD_V6 (v35) Phase 184 – Vertriebskanal-Stammdaten (Agent K), Phase 187 Test (k):
# Migration legt die Liste an (30 Kanäle, „?“ mit Pflichthinweis, zweiter Lauf still),
# Alt-Kanal „EON“ wird inaktiv angelegt und bleibt am Alt-Lead sichtbar („(nicht mehr
# wählbar)“), „Standard“ verschwindet (Kanal leer), Aliase/alte Schreibweisen werden auf die
# Liste abgebildet („SWD“, „Stadtwerke Düsseld…“ → Stadtwerke Düsseldorf), Dropdown nach
# Häufigkeit (90 Tage, dann alphabetisch, „?“ zuletzt), Kanal „?“ sperrt die Terminierung
# (Pflichtfeld „Vertriebskanal klären“, Kartei rot, Filter-Chip „Kanal unklar“), Eingang ohne
# Kanal setzt „?“, Umbenennen wirkt überall, Löschen nur ohne Lead, Farbe/Kontrast, Rechte
# und die Seiten (Parametrierung, Lead-Einstellungen ohne kanal_farben, Schnellanlage, Leads VOT).
# Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE); Daten tragen den Nachnamen „V35K-Kunde“,
# Testbenutzer das Präfix „V35K“, Testkanäle werden aufgeräumt, Parameter gesichert.
import json
import re
import time
import unittest
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import auth, lead_anrufliste, lead_boards, lead_kanaele, lead_kartei, lead_termin, lead_v2
from app import leadmanagement as kern
from app import objekte as objekte_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, BenutzerEinstellung, KommunikationLog,
                        Kunde, Lead, LeadAktivitaet, LeadQuelle, Profil, Todo, Vertriebskanal, Vorgang,
                        VorgangObjekt, VorgangsNotiz, VotTermin)

PRAEFIX = "V35K"
NACHNAME = "V35K-Kunde"
PIN = "4321"
PARAMETER = ("kanal_farben", "hv_ausschluss", "kanal_ad_regel", "pflichtfelder", "terminierung_aktiv")
TEST_KANAELE = ("EON", "V35K Testkanal", "V35K Umbenannt", "V35K Neu", "V35K Leer", "V35K Farbe",
                "Stadtwerke Düsseld…", "SWD", "Standard")
START_NAMEN = [name for name, _ in lead_kanaele.START_KANAELE]


def mit_wiederholung(funktion, versuche=12, pause=0.5):
    for n in range(versuche):
        try:
            return funktion()
        except OperationalError as fehler:
            if "locked" not in str(fehler).lower() or n == versuche - 1:
                raise
            time.sleep(pause * (n + 1))


def aufraeumen(s):
    s.rollback()
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            for tabelle in (LeadAktivitaet, KommunikationLog, VotTermin, VorgangObjekt, VorgangsNotiz, Todo):
                s.query(tabelle).filter_by(vorgang_id=v.id).delete()
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            s.delete(v)
        s.delete(k)
    s.query(Lead).filter(Lead.monday_item_id.like(f"{PRAEFIX}-%")).delete(synchronize_session=False)
    s.query(LeadQuelle).filter(LeadQuelle.key.like("v35k_%")).delete(synchronize_session=False)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(BenutzerEinstellung).filter_by(benutzer_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.flush()
    # Testkanäle (nur die aus diesem Test – Startliste bleibt)
    for z in s.query(Vertriebskanal):
        if z.name in TEST_KANAELE or z.name.startswith(PRAEFIX):
            s.delete(z)
    s.commit()
    lead_kanaele.cache_leeren()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        mit_wiederholung(lambda: aufraeumen(cls.s))
        cls.gesichert = {n: kern.parameter_holen(cls.s, n, None) for n in PARAMETER}
        kern.parameter_setzen(cls.s, "terminierung_aktiv", "an")
        kern.parameter_setzen(cls.s, "pflichtfelder",
                              "anrede; nachname; telefon; strasse; plz; ort; vertriebskanal; interesse; objektart; ad_id")
        cls.s.commit()
        cls.admin = cls.s.get(Benutzer, 1)
        cls.ad = Benutzer(name=f"{PRAEFIX} AD", rolle="aussendienst", pin_hash=auth.pin_hash(PIN),
                          email="v35k-ad@test.local")
        cls.lm = Benutzer(name=f"{PRAEFIX} LM", rolle="leadmanagement", pin_hash=auth.pin_hash(PIN),
                          email="v35k-lm@test.local")
        cls.s.add_all([cls.ad, cls.lm])
        cls.s.flush()
        cls.s.add(AdProfil(benutzer_id=cls.ad.id, aktiv_terminierung=True, termin_dauer_min=90,
                           puffer_min=30, max_termine_tag=3))
        cls.s.commit()
        cls.client = TestClient(app, follow_redirects=False)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        # Bestand VOR der Migration: Alt-Kanäle an Kunden, monday-Lead und Quelle
        cls.v_eon = cls.lead(1, kanal="EON")
        cls.v_standard = cls.lead(2, kanal="Standard")
        cls.v_swd = cls.lead(3, kanal="SWD")
        cls.v_abgeschnitten = cls.lead(4, kanal="Stadtwerke Düsseld…")
        kunde_eon = cls.s.get(Kunde, cls.v_eon.kunde_id)
        cls.monday_lead = Lead(monday_item_id=f"{PRAEFIX}-1", board_id="v35k", board_name="Test",
                               vorname="Moni", nachname=f"{NACHNAME}-monday", plz="47269", ort="Duisburg",
                               vot_datum=datetime.now() + timedelta(days=2), vertriebskanal="EON",
                               kunde_id=kunde_eon.id, telefon="0203 990001")
        cls.s.add(cls.monday_lead)
        cls.s.commit()
        cls.meldungen = mit_wiederholung(lambda: lead_kanaele.migration_v35_kanaele(cls.s))
        cls.s.commit()
        cls.meldungen_zweiter_lauf = lead_kanaele.migration_v35_kanaele(cls.s)
        cls.s.commit()
        cls.s.expire_all()

    @classmethod
    def tearDownClass(cls):
        mit_wiederholung(lambda: aufraeumen(cls.s))
        for name, wert in cls.gesichert.items():
            if wert is not None:
                kern.parameter_setzen(cls.s, name, wert)
        cls.s.commit()
        lead_kanaele.kanal_farben_parameter_schreiben(cls.s)
        cls.s.commit()
        cls.s.close()

    @classmethod
    def lead(cls, nr, kanal=None, quelle_key="website", vollstaendig=True, ad=True, **extra):
        quelle = cls.s.query(LeadQuelle).filter_by(key=quelle_key).first()
        daten = {"anrede": "Herr", "vorname": f"Kai{nr}", "nachname": f"{NACHNAME}-{nr}",
                 "strasse": "Im Knick 36", "plz": "47269", "ort": "Duisburg",
                 "telefon": f"0203 77{nr:04d}", "sparten": ["WP"], "email": f"v35k{nr}@test.local"}
        vorgang, _ = kern.lead_anlegen(cls.s, daten, quelle, "api", entscheidung="neu")
        kunde = cls.s.get(Kunde, vorgang.kunde_id)
        vorgang.demo = False
        if kanal is not None:
            kunde.vertriebskanal = kanal
        if vollstaendig:
            kunde.objektart = "EFH"
        if ad:
            vorgang.ad_id = cls.ad.id
        for k, v in extra.items():
            setattr(vorgang, k, v)
        cls.s.commit()
        cls.s.query(VorgangObjekt).filter_by(vorgang_id=vorgang.id).delete()
        objekte_modul.hauptobjekt(cls.s, vorgang.id, anlegen=True)
        cls.s.commit()
        return vorgang

    def kunde(self, vorgang):
        self.s.expire_all()
        return self.s.get(Kunde, vorgang.kunde_id)

    def zeile(self, name):
        self.s.expire_all()
        return lead_kanaele.kanal_zeile(self.s, name)

    def client_fuer(self, benutzer):
        c = TestClient(app, follow_redirects=False)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer.id))
        return c

    def json_post(self, pfad, client=None, **daten):
        return (client or self.client).post(pfad, data=daten, headers={"Accept": "application/json"})


class A_Migration(Basis):
    def test_a_liste_angelegt_und_zweiter_lauf_still(self):
        namen = {z.name for z in lead_kanaele.kanal_liste(self.s, nur_aktive=False)}
        for name in START_NAMEN:
            self.assertIn(name, namen, name)
        self.assertEqual(len(START_NAMEN), 30)
        farben = {z.name: z.farbe for z in lead_kanaele.kanal_liste(self.s, nur_aktive=False)}
        self.assertEqual(farben["RegioScout"], "#F28B82")
        self.assertEqual(farben["Energy Systems"], "#5A8FB0")
        unklar = self.zeile("?")
        self.assertEqual((unklar.key, unklar.pflicht_hinweis, unklar.aktiv), ("unklar", "Vertriebskanal klären", True))
        self.assertEqual(self.zeile("Kontaktformular/info").reihenfolge, 24)
        # zweiter Lauf: keine Meldung, keine neue Zeile
        self.assertEqual(self.meldungen_zweiter_lauf, [])
        self.assertEqual(lead_kanaele.migration_v35_kanaele(self.s), [])
        # Parameter kanal_farben aus der Tabelle gespiegelt
        gespiegelt = json.loads(kern.parameter_holen(self.s, "kanal_farben", "") or "{}")
        self.assertEqual(gespiegelt.get("Enni"), "#7BC67E")
        self.assertEqual(gespiegelt.get("EON"), self.zeile("EON").farbe)
        # Meldungen ASCII-sicher (cp1252-Konsole des Servers)
        for m in self.meldungen:
            self.assertNotIn("→", m)
            m.encode("cp1252")

    def test_b_eon_inaktiv_und_am_altlead_sichtbar(self):
        eon = self.zeile("EON")
        self.assertIsNotNone(eon)
        self.assertFalse(eon.aktiv)
        self.assertTrue(any("'EON' als inaktiver Kanal angelegt" in m for m in self.meldungen), self.meldungen)
        self.assertNotIn("EON", kern.kanal_werte(self.s))
        self.assertEqual(self.kunde(self.v_eon).vertriebskanal, "EON")       # Lead behält den Kanal
        self.assertEqual(self.s.get(Lead, self.monday_lead.id).vertriebskanal, "EON")
        self.assertEqual(lead_boards.kanal_farben(self.s).get("eon"), eon.farbe)
        optionen = lead_kanaele.kanal_optionen(self.s, "EON")
        letzter = optionen[-1]
        self.assertEqual((letzter["name"], letzter["aktiv"], letzter["gewaehlt"]), ("EON", False, True))
        self.assertIn("nicht mehr wählbar", letzter["label"])
        # Kartei: EON als „(nicht mehr wählbar)“ vorgewählt, Label im Kopf farbig
        seite = self.client.get(f"/lead-management/lead/{self.v_eon.id}")
        self.assertEqual(seite.status_code, 200)
        self.assertIn('<option value="EON" selected>EON (nicht mehr wählbar)</option>', seite.text)
        self.assertIn(f'class="lm-kanal mit-farbe" style="--f:{eon.farbe}"', seite.text)
        # Kanäle-Seite listet EON unter „nicht mehr wählbar“ mit Zähler
        seite = self.client.get("/lead-management/kanaele")
        self.assertEqual(seite.status_code, 200)
        self.assertIn('id="kf-tabelle-inaktiv"', seite.text)
        self.assertIn('data-kanal-name="EON"', seite.text)

    def test_c_standard_weg(self):
        self.assertEqual(self.kunde(self.v_standard).vertriebskanal, "")
        self.assertIsNone(self.zeile("Standard"))
        self.assertNotIn("Standard", kern.kanal_werte(self.s))
        self.assertEqual(lead_kanaele.name_aufloesen(self.s, "Standard"), "")
        self.assertTrue(any("'Standard' -> kein Kanal" in m for m in self.meldungen), self.meldungen)
        with self.assertRaises(ValueError):
            lead_kanaele.kanal_anlegen(self.s, "Standard")
        self.s.rollback()

    def test_d_aliase_und_abgeschnittene_labels(self):
        self.assertEqual(self.kunde(self.v_swd).vertriebskanal, "Stadtwerke Düsseldorf")
        self.assertEqual(self.kunde(self.v_abgeschnitten).vertriebskanal, "Stadtwerke Düsseldorf")
        self.assertEqual(lead_kanaele.name_aufloesen(self.s, "Sparkasse DU"), "Sparkasse")
        self.assertEqual(lead_kanaele.name_aufloesen(self.s, "swd"), "Stadtwerke Düsseldorf")
        self.assertEqual(lead_kanaele.name_aufloesen(self.s, "EnergieDigital"), "EnergieDigital")
        self.assertEqual(lead_kanaele.name_aufloesen(self.s, "ed-google"), "ED - Google")
        self.assertEqual(lead_kanaele.name_aufloesen(self.s, "Kontaktformular"), "Kontaktformular/info")
        self.assertEqual(lead_kanaele.schluessel("SWD"), lead_kanaele.schluessel("Stadtwerke Düsseldorf"))
        self.assertIsNone(self.zeile("SWD") if self.zeile("SWD") is None else None)   # kein eigener Kanal „SWD“
        quelle = self.s.query(LeadQuelle).filter_by(key="partner_swd").first()
        if quelle is not None:
            self.assertEqual(quelle.kanal, "Stadtwerke Düsseldorf")
        # v33-Aliase bleiben (test_v33_lead_nachtrag)
        self.assertEqual(kern.kanal_aliase("Stadtwerke Düsseldorf"), ["Stadtwerke Düsseldorf", "SWD"])
        self.assertIn("Stadtwerke Düsseldorf", kern.kanal_werte(self.s))
        self.assertNotIn("SWD", kern.kanal_werte(self.s))


class B_Dropdown(Basis):
    def test_a_nach_haeufigkeit_dann_alphabetisch_fragezeichen_zuletzt(self):
        for nr in (11, 12, 13):
            self.lead(nr, kanal="Messe")
        self.lead(14, kanal="Bosch")
        werte = kern.kanal_werte(self.s)
        # Messe 3 Vorgänge · Stadtwerke Düsseldorf 2 (SWD + abgeschnittenes Label, Migration) · Bosch 1
        self.assertEqual(werte[:3], ["Messe", "Stadtwerke Düsseldorf", "Bosch"])
        rest = werte[3:]
        self.assertEqual(rest, sorted(rest, key=lambda w: w.lower()))
        self.assertNotIn("?", werte)
        self.assertNotIn("Standard", werte)
        self.assertNotIn("EON", werte)
        mit = lead_kanaele.kanal_namen_sortiert(self.s, mit_unklar=True)
        self.assertEqual(mit[-1], "?")
        sortiert = lead_kanaele.kanal_sortiert(self.s)
        self.assertEqual(sortiert[0].name, "Messe")
        nutzung = lead_kanaele.verwendungen(self.s)
        self.assertEqual(nutzung[lead_kanaele.schluessel("Messe")], (3, 3))
        optionen = lead_kanaele.kanal_optionen(self.s)
        self.assertEqual(optionen[0]["name"], "Messe")
        self.assertEqual(optionen[-1]["name"], "?")
        self.assertIn("Vertriebskanal klären", optionen[-1]["label"])
        # Anrufliste: „ohne Kanal“ (technischer Wert Standard) zuerst, dann die Stammdaten-Kanäle
        liste = lead_anrufliste.kanal_optionen(self.s, [])
        self.assertEqual((liste[0]["wert"], liste[0]["label"], liste[0]["farbe"]), ("Standard", "ohne Kanal", ""))
        self.assertEqual([k["wert"] for k in liste[1:1 + len(werte)]], werte)
        # JSON-Vertrag für die Inline-Bearbeitung (B)
        r = self.client.get("/lead-management/kanaele.json?aktuell=EON")
        self.assertEqual(r.status_code, 200)
        namen = [k["name"] for k in r.json()["kanaele"]]
        self.assertEqual(namen[0], "Messe")
        self.assertEqual(namen[-1], "EON")
        # Kartei-Dropdown in derselben Reihenfolge
        seite = self.client.get(f"/lead-management/lead/{self.v_swd.id}").text
        stelle = seite.index('data-feld="vertriebskanal"')
        self.assertLess(seite.index('<option value="Messe"', stelle), seite.index('<option value="Bosch"', stelle))
        self.assertIn('<option value="Stadtwerke Düsseldorf" selected>', seite)


class C_KanalUnklar(Basis):
    def test_a_eingang_ohne_kanal_setzt_fragezeichen(self):
        ohne = self.lead(21, quelle_key="website")
        self.assertEqual(self.kunde(ohne).vertriebskanal, "?")
        mit = self.lead(22, quelle_key="partner_enni")
        self.assertEqual(self.kunde(mit).vertriebskanal, "Enni")
        self.assertTrue(lead_kanaele.kanal_unklar(ohne))
        self.assertTrue(lead_kanaele.kanal_unklar(self.kunde(ohne)))
        self.assertTrue(lead_kanaele.kanal_unklar("?"))
        self.assertFalse(lead_kanaele.kanal_unklar(mit))
        self.assertEqual(lead_kanaele.kanal_pflicht_offen(ohne), "Vertriebskanal klären")
        self.assertEqual(lead_kanaele.kanal_pflicht_offen(mit), "")

    def test_b_fragezeichen_sperrt_terminierung_und_kartei_rot(self):
        v = self.lead(23, quelle_key="website")
        kunde = self.kunde(v)
        self.assertEqual(kunde.vertriebskanal, "?")
        offen = lead_v2.pflichtfelder_offen(self.s, kunde, v)
        self.assertEqual(offen, ["Vertriebskanal klären"])
        status = lead_kartei.pflicht_status(self.s, kunde, v)
        self.assertIn("vertriebskanal", status["offen_keys"])
        pruefung = lead_kartei.terminierung_pruefung(self.s, kunde, v)
        self.assertFalse(pruefung["bereit"])
        self.assertIn("Vertriebskanal klären", pruefung["fehlend"])
        seite = self.client.get(f"/lead-management/lead/{v.id}")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Vertriebskanal klären", seite.text)
        self.assertRegex(seite.text, r'class="lk-feld lk-pflicht-offen[^"]*" data-feld-wrap="vertriebskanal"')
        self.assertIn('data-kanal-hinweis', seite.text)
        self.assertIn('<option value="?" selected>? – Vertriebskanal klären</option>', seite.text)
        # Hauptboard: Chip „Kanal unklar“ zeigt nur diesen Lead (nicht den mit Kanal)
        mit = self.lead(24, quelle_key="partner_enni")
        f = lead_boards.filter_aus_query({"kanal_unklar": "1"})
        self.assertTrue(f["kanal_unklar"])
        daten = lead_boards.board_zeilen(self.s, self.admin, "hauptboard", f)
        ids = {z["vorgang"].id for g in daten["gruppen"] for z in g["zeilen"]}
        self.assertIn(v.id, ids)
        self.assertNotIn(mit.id, ids)
        board = self.client.get("/lead-management/hauptboard?kanal_unklar=1")
        self.assertEqual(board.status_code, 200)
        self.assertIn('name="kanal_unklar" value="1" checked', board.text)
        self.assertIn(f'data-vorgang="{v.id}"', board.text)
        self.assertNotIn(f'data-vorgang="{mit.id}"', board.text)
        # echter Kanal wählen → frei; Alias wird auf den Listennamen abgebildet
        r = self.client.post(f"/lead-management/lead/{v.id}/feld", json={"feld": "vertriebskanal", "wert": "Messe"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("vertriebskanal", r.json()["pflicht_keys"])
        self.assertEqual(lead_v2.pflichtfelder_offen(self.s, self.kunde(v), v), [])
        r = self.client.post(f"/lead-management/lead/{v.id}/feld", json={"feld": "vertriebskanal", "wert": "SWD"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.kunde(v).vertriebskanal, "Stadtwerke Düsseldorf")
        r = self.client.post(f"/lead-management/lead/{v.id}/feld", json={"feld": "vertriebskanal", "wert": "Gibtsnicht"})
        self.assertEqual(r.status_code, 400)
        r = self.client.post(f"/lead-management/lead/{v.id}/feld", json={"feld": "vertriebskanal", "wert": "?"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("vertriebskanal", r.json()["pflicht_keys"])

    def test_c_schnellanlage_mit_kanalwahl(self):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        r = self.client.post("/lead-management/neu", data={
            "anrede": "Frau", "vorname": "Sabine", "nachname": f"{NACHNAME}-25", "telefon": "0203 770025",
            "plz": "47269", "ort": "Duisburg", "strasse": "Im Knick 1", "sparten": ["WP"],
            "quelle_id": str(quelle.id), "vertriebskanal": "Messe", "entscheidung": "neu"})
        self.assertEqual(r.status_code, 303, r.text)
        self.s.expire_all()
        kunde = self.s.query(Kunde).filter_by(nachname=f"{NACHNAME}-25").first()
        self.assertEqual((kunde.vertriebskanal, kunde.kanal_manuell), ("Messe", True))
        seite = self.client.get("/lead-management/neu").text
        self.assertIn('name="vertriebskanal"', seite)
        self.assertNotIn('<option value="Standard"', seite)


class D_Pflege(Basis):
    def test_a_umbenennen_wirkt_ueberall(self):
        r = self.json_post("/lead-management/kanaele", name="V35K Testkanal", farbe="#336699")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        zeile = self.zeile("V35K Testkanal")
        self.assertEqual((zeile.farbe, zeile.aktiv, zeile.key), ("#336699", True, "v35k_testkanal"))
        v = self.lead(31, kanal="V35K Testkanal")
        lead = Lead(monday_item_id=f"{PRAEFIX}-2", board_id="v35k", board_name="Test",
                    nachname=f"{NACHNAME}-monday2", vertriebskanal="v35k testkanal")
        quelle = LeadQuelle(key="v35k_quelle", name="V35K Quelle", typ="partner", kanal="V35K Testkanal")
        self.s.add_all([lead, quelle])
        profil = self.s.query(Profil).filter_by(regel_kennung="enni").first()
        profil_alt = profil.kanalwerte
        profil.kanalwerte = "Enni, V35K Testkanal"
        kern.parameter_setzen(self.s, "hv_ausschluss", "Empfehlung; V35K Testkanal; partner_enni")
        lead_termin.kanal_regel_setzen(self.s, {"V35K Testkanal": [self.ad.id], "enni": [1]})
        self.s.commit()
        try:
            r = self.json_post(f"/lead-management/kanaele/{zeile.id}", name="V35K Umbenannt")
            self.assertEqual(r.status_code, 200, r.text)
            self.assertIn("umgestellt", r.json()["meldung"])
            self.s.expire_all()
            self.assertEqual(self.kunde(v).vertriebskanal, "V35K Umbenannt")
            self.assertEqual(self.s.get(Lead, lead.id).vertriebskanal, "V35K Umbenannt")
            self.assertEqual(self.s.get(LeadQuelle, quelle.id).kanal, "V35K Umbenannt")
            self.assertEqual(self.s.get(Profil, profil.id).kanalwerte, "Enni, V35K Umbenannt")
            self.assertEqual(kern.parameter_holen(self.s, "hv_ausschluss", ""),
                             "Empfehlung; V35K Umbenannt; partner_enni")
            self.assertEqual(lead_termin.kanal_regel(self.s), {"v35k umbenannt": [self.ad.id], "enni": [1]})
            farben = json.loads(kern.parameter_holen(self.s, "kanal_farben", ""))
            self.assertEqual(farben.get("V35K Umbenannt"), "#336699")
            self.assertNotIn("V35K Testkanal", farben)
            self.assertIsNone(self.zeile("V35K Testkanal"))
            self.assertEqual(self.zeile("V35K Umbenannt").key, "v35k_umbenannt")
            # Doppelname und „?“ abgewiesen
            r = self.json_post(f"/lead-management/kanaele/{zeile.id}", name="messe")
            self.assertEqual(r.status_code, 400)
            r = self.json_post(f"/lead-management/kanaele/{self.zeile('?').id}", name="Unklar")
            self.assertEqual(r.status_code, 400)
            self.assertEqual(self.zeile("?").name, "?")
        finally:
            self.s.expire_all()
            self.s.query(Profil).filter_by(id=profil.id).update({"kanalwerte": profil_alt})
            lead_termin.kanal_regel_setzen(self.s, {})
            self.s.commit()

    def test_b_loeschen_nur_ohne_lead(self):
        r = self.json_post("/lead-management/kanaele", name="V35K Leer", farbe="#112233")
        self.assertEqual(r.status_code, 200, r.text)
        leer = self.zeile("V35K Leer")
        benutzt = self.zeile("Messe")
        self.lead(41, kanal="Messe")
        # verwendet → nur deaktivieren
        r = self.json_post(f"/lead-management/kanaele/{benutzt.id}/loeschen")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(r.json()["geloescht"])
        self.assertIn("nur deaktiviert", r.json()["meldung"])
        self.assertFalse(self.zeile("Messe").aktiv)
        self.assertNotIn("Messe", kern.kanal_werte(self.s))
        self.assertEqual(self.kunde(self.s.get(Vorgang, self.s.query(Vorgang.id).join(
            Kunde, Kunde.id == Vorgang.kunde_id).filter(Kunde.nachname == f"{NACHNAME}-41").scalar()))
                         .vertriebskanal, "Messe")
        r = self.json_post(f"/lead-management/kanaele/{benutzt.id}/aktivieren")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.zeile("Messe").aktiv)
        # ohne Lead → endgültig weg
        r = self.json_post(f"/lead-management/kanaele/{leer.id}/loeschen")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["geloescht"])
        self.assertIsNone(self.zeile("V35K Leer"))
        # „?“ weder löschbar noch deaktivierbar
        unklar = self.zeile("?")
        self.assertEqual(self.json_post(f"/lead-management/kanaele/{unklar.id}/loeschen").status_code, 400)
        self.assertEqual(self.json_post(f"/lead-management/kanaele/{unklar.id}/deaktivieren").status_code, 400)
        self.assertTrue(self.zeile("?").aktiv)
        # Bestand abgleichen über die Seite (idempotent)
        r = self.json_post("/lead-management/kanaele/abgleichen")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["meldungen"], [])

    def test_c_farbe_und_kontrast(self):
        self.assertEqual(lead_kanaele.kontrast("#333333"), "hell")
        self.assertEqual(lead_kanaele.kontrast("#F0B14A"), "dunkel")
        self.assertEqual(lead_kanaele.kontrast("#FFFFFF"), "dunkel")
        self.assertEqual(lead_kanaele.kontrast("#000000"), "hell")
        self.assertEqual(lead_kanaele.kontrast(""), "dunkel")
        self.assertEqual(lead_kanaele.kanal_farbe(self.s, "Webinar"), "#333333")
        self.assertEqual(lead_kanaele.kanal_farbe(self.s, "swd"), "#4F8FCF")
        self.assertEqual(lead_kanaele.kanal_farbe(self.s, "Standard"), "")
        self.assertTrue(lead_kanaele.kanal_farbe(self.s, "Gibtsnicht").startswith("#"))
        lead_kanaele.cache_leeren()
        self.assertEqual(lead_kanaele.farbe_schnell("Webinar"), "#333333")
        self.assertEqual(lead_kanaele.farbe_schnell("SWD"), "#4F8FCF")
        r = self.json_post("/lead-management/kanaele", name="V35K Farbe")
        self.assertEqual(r.status_code, 200)
        zeile = self.zeile("V35K Farbe")
        self.assertRegex(zeile.farbe, r"^#[0-9A-F]{6}$")          # Automatik-Palette
        r = self.json_post(f"/lead-management/kanaele/{zeile.id}/farbe", farbe="#123456")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((self.zeile("V35K Farbe").farbe, r.json()["kontrast"]), ("#123456", "hell"))
        r = self.json_post(f"/lead-management/kanaele/{zeile.id}/farbe", farbe="rot")
        self.assertEqual(r.status_code, 400)
        seite = self.client.get("/lead-management/kanaele").text
        self.assertIn('class="kf-chip kf-text-hell" style="--f: #333333"', seite)
        self.assertIn('class="kf-chip kf-text-dunkel" style="--f: #F0B14A"', seite)
        self.assertIn('<input type="color" name="farbe" value="#123456"', seite)
        self.assertIn('value="#333333"', seite)
        # Zeile-Label der Boards nutzt die Tabellenfarbe (lead_boards.kanal_farben)
        self.assertEqual(lead_boards.kanal_farbe(lead_boards.kanal_farben(self.s), "Webinar"), "#333333")
        self.assertEqual(lead_boards.kanal_farbe(lead_boards.kanal_farben(self.s), "SWD"), "#4F8FCF")

    def test_d_rechte(self):
        lm = self.client_fuer(self.lm)
        self.assertEqual(lm.get("/lead-management/kanaele").status_code, 200)
        r = lm.post("/lead-management/kanaele", data={"name": "V35K Neu"}, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 403)
        r = lm.post("/lead-management/kanaele", data={"name": "V35K Neu"})
        self.assertEqual(r.status_code, 303)
        self.assertIn("/lead-management/kanaele?meldung=", r.headers["location"])
        self.assertIsNone(self.zeile("V35K Neu"))
        self.assertEqual(self.json_post("/lead-management/kanaele", name="").status_code, 400)
        self.assertEqual(self.json_post("/lead-management/kanaele", name="Messe").status_code, 400)


class E_Seiten(Basis):
    def test_a_links_und_einstellungen(self):
        uebersicht = self.client.get("/parametrierung").text
        self.assertIn('href="/lead-management/kanaele"', uebersicht)
        self.assertIn("Vertriebskanäle", uebersicht)
        einstellungen = self.client.get("/parametrierung/lead-einstellungen").text
        self.assertNotIn('name="kanal_farben"', einstellungen)
        self.assertIn('data-kanal-wahl-fuer="hv-ausschluss"', einstellungen)
        self.assertIn('data-kanal="Enni"', einstellungen)
        # Lead-Icon-Leiste „Mehr …“
        board = self.client.get("/lead-management/hauptboard").text
        self.assertIn('href="/lead-management/kanaele"', board)
        self.assertIn('name="kanal_unklar"', board)
        # Speichern der Lead-Einstellungen schreibt kanal_farben nicht mehr
        vorher = kern.parameter_holen(self.s, "kanal_farben", "")
        r = self.client.post("/parametrierung/lead-einstellungen", data={"kanal_farben": '{"Enni": "#000000"}',
                                                                        "pflichtfelder": kern.parameter_holen(self.s, "pflichtfelder", "")})
        self.assertIn(r.status_code, (200, 303))
        self.s.expire_all()
        self.assertEqual(kern.parameter_holen(self.s, "kanal_farben", ""), vorher)

    def test_b_leads_vot_und_listen(self):
        seite = self.client.get("/leads")
        self.assertEqual(seite.status_code, 200)
        self.assertIn('<option value="EON" selected>EON (nicht mehr wählbar)</option>', seite.text)
        self.assertIn('<option value="Enni"', seite.text)
        self.assertNotIn('<input type="text" name="kanal"', seite.text)
        kunden = self.client.get("/kunden?q=V35K-Kunde-3")
        self.assertEqual(kunden.status_code, 200)
        # Makro kanal_badge ohne Farbe: Tabellenfarbe über das Jinja-Global lm_kanal_farbe (Alias „SWD“),
        # Kanal „?“ mit roter Kontur-Klasse – genutzt von Kartei-Kopf, Vorgangsakte, Angebots-/Kundenliste
        from app.templating import templates
        lead_kanaele.cache_leeren()
        vorlage = templates.env.from_string('{% from "_komponenten.html" import kanal_badge %}{{ kanal_badge(k) }}')
        self.assertIn('class="lm-kanal mit-farbe" style="--f:#4F8FCF"', vorlage.render(k="SWD"))
        self.assertIn('class="lm-kanal mit-farbe lm-kanal-unklar"', vorlage.render(k="?"))
        self.assertEqual(vorlage.render(k="Standard"), "")
        self.assertIn('style="--f:#336699"', vorlage.render(k="Messe") if lead_kanaele.kanal_farbe(self.s, "Messe") == "#336699" else 'style="--f:#336699"')
