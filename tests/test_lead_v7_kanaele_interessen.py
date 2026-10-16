# Tests PLAN_LEAD_V7 (v37) Phase 199 – Agent L3: Kanäle WeLoveX/DAA, Interesse „PV vorhanden“,
# Inline-Interessen mit Plus, Deals-Board (Phase 200 Tests h/i/j/k):
#  (h) Migration migration_v37_kanaele setzt WELOVEX/DAA auf aktiv = 0 (Meldung je Kanal, zweiter
#      Lauf still, ASCII), ein Alt-Lead behält das Label („(nicht mehr wählbar)“ nur an diesem
#      Lead), die Filter-Selects in Hauptboard und Deals zeigen die Kanäle nicht mehr, die
#      Kanal-Pflegeseite bietet die Reaktivierung; Parameter hv_ausschluss/kanal_ad_regel werden
#      nur gemeldet, nicht geändert.
#  (i) Interesse „PV vorhanden“ (Code PVV, Merkmal): Sparten-Modul (codes/erfassungs_codes/
#      merkmale, {sparten} ohne PVV, {pv_vorhanden}), Kartei-Häkchen + Autospeichern mit Aktivität,
#      Schnellanlage, API (Text „PV vorhanden“), Parser, Filter-Chip, Boards-Badge, kein
#      Erfassungsstart (Sparten-Start ohne PVV, Lead.sparten, Mein-Tag-Helfer), keine Kompetenz-
#      prüfung, Pflichtfeld „Interesse“ nicht erfüllt, Vorbelegung A11 = Ja im WP-Bogen.
#  (j) Inline-Interessen: Plus statt Stift, Chips im Popover, Abwählen (POST mit Liste ohne PV)
#      mit Aktivität, HV-Ansicht, JS/CSS-Regeln (kein Timer, Escape, keine festen Farben).
#  (k) Deals-Board ohne „Bestätigung erneut“, ohne Spalte „Erfassung / Angebot“, ohne „Erfassung
#      starten“; alte Spaltenkonfiguration mit Key „angebot“ ohne Fehler; Route bleibt.
# Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE, diagnose/v37/data_L3); Testdaten tragen den Nachnamen
# „V37L3-Kunde“, Testbenutzer/-quellen das Präfix „V37L3“ – alles wird aufgeräumt, Parameter gesichert.
import json
import re
import time
import unittest
import warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import auth, lead_boards, lead_kanaele, lead_kartei, lead_mail, lead_parser, lead_v2, sparten
from app import leadmanagement as kern
from app import objekte as objekte_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, BenutzerEinstellung, Erfassung,
                        KommunikationLog, Kunde, Lead, LeadAktivitaet, LeadQuelle, Todo, Vertriebskanal,
                        Vorgang, VorgangObjekt, VorgangsNotiz, VotTermin, INTERESSE_CODES)
from app.routers import leads_api

BASIS = Path(__file__).resolve().parents[1]
PRAEFIX = "V37L3"
NACHNAME = "V37L3-Kunde"
PIN = "4321"
API_KEY = "v37l3-api-key"
PARAMETER = ("hv_ausschluss", "kanal_ad_regel", "pflichtfelder", "terminierung_aktiv")
KANAELE = ("WELOVEX", "DAA")


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
        s.query(Erfassung).filter_by(kunde_id=k.id).delete()
        s.delete(k)
    s.query(Lead).filter(Lead.monday_item_id.like(f"{PRAEFIX}-%")).delete(synchronize_session=False)
    s.query(LeadQuelle).filter(LeadQuelle.key.like("v37l3_%")).delete(synchronize_session=False)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(BenutzerEinstellung).filter_by(benutzer_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.query(VotTermin).filter_by(ad_id=b.id).delete()
        s.delete(b)
    s.commit()
    lead_kanaele.cache_leeren()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        mit_wiederholung(lambda: aufraeumen(cls.s))
        cls.gesichert = {n: kern.parameter_holen(cls.s, n, None) for n in PARAMETER}
        kern.parameter_setzen(cls.s, "pflichtfelder",
                              "anrede; nachname; telefon; strasse; plz; ort; vertriebskanal; interesse; objektart; ad_id")
        cls.s.commit()
        cls.admin = cls.s.get(Benutzer, 1)
        pin = auth.pin_hash(PIN)
        cls.ad = Benutzer(name=f"{PRAEFIX} AD", rolle="aussendienst", pin_hash=pin, email="v37l3-ad@test.local")
        cls.lm = Benutzer(name=f"{PRAEFIX} LM", rolle="leadmanagement", pin_hash=pin,
                          email="v37l3-lm@test.local", leadmanager=True)
        cls.hv = Benutzer(name=f"{PRAEFIX} HV", rolle="aussendienst", pin_hash=pin, email="v37l3-hv@test.local")
        cls.s.add_all([cls.ad, cls.lm, cls.hv])
        cls.s.flush()
        cls.s.add(AdProfil(benutzer_id=cls.ad.id, aktiv_terminierung=True, termin_dauer_min=90,
                           puffer_min=30, max_termine_tag=3, kompetenz_sparten=json.dumps(["WP"])))
        cls.s.add(AdProfil(benutzer_id=cls.hv.id, terminiert_selbst=True, aktiv_terminierung=True))
        cls.quelle_api = LeadQuelle(key="v37l3_api", name="V37L3 API", typ="website", aktiv=True, api_key=API_KEY)
        cls.s.add(cls.quelle_api)
        cls.s.commit()
        cls.client = TestClient(app, follow_redirects=False)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        # Kanal-Stammdaten sicherstellen (v35, idempotent) und den Zustand VOR v37 herstellen:
        # WELOVEX/DAA aktiv, ein Alt-Lead je Kanal
        mit_wiederholung(lambda: lead_kanaele.migration_v35_kanaele(cls.s))
        for name in KANAELE:
            zeile = lead_kanaele.kanal_zeile(cls.s, name)
            assert zeile is not None, name
            zeile.aktiv = True
        cls.s.commit()
        lead_kanaele.cache_leeren()
        cls.v_daa = cls.lead(1, kanal="DAA")
        cls.v_welovex = cls.lead(2, kanal="WELOVEX")
        cls.meldungen = mit_wiederholung(lambda: lead_kanaele.migration_v37_kanaele(cls.s))
        cls.s.commit()
        cls.meldungen_zweiter_lauf = lead_kanaele.migration_v37_kanaele(cls.s)
        cls.s.commit()
        cls.s.expire_all()

    @classmethod
    def tearDownClass(cls):
        mit_wiederholung(lambda: aufraeumen(cls.s))
        for name, wert in cls.gesichert.items():
            if wert is not None:
                kern.parameter_setzen(cls.s, name, wert)
        cls.s.commit()
        cls.s.close()

    @classmethod
    def lead(cls, nr, kanal=None, sparten_liste=("WP",), phase="neu", ad=True, **extra):
        quelle = cls.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"anrede": "Herr", "vorname": f"Lars{nr}", "nachname": f"{NACHNAME}-{nr}",
                 "strasse": "Im Knick 36", "plz": "47269", "ort": "Duisburg",
                 "telefon": f"0203 66{nr:04d}", "sparten": list(sparten_liste), "email": f"v37l3-{nr}@test.local"}
        vorgang, _ = kern.lead_anlegen(cls.s, daten, quelle, "api", entscheidung="neu")
        kunde = cls.s.get(Kunde, vorgang.kunde_id)
        vorgang.demo = False
        vorgang.lead_phase = phase
        kunde.objektart = "EFH"
        if kanal is not None:
            kunde.vertriebskanal = kanal
        if ad:
            vorgang.ad_id = cls.ad.id
        for k, v in extra.items():
            setattr(vorgang, k, v)
        cls.s.commit()
        cls.s.query(VorgangObjekt).filter_by(vorgang_id=vorgang.id).delete()
        objekte_modul.hauptobjekt(cls.s, vorgang.id, anlegen=True)
        cls.s.commit()
        return vorgang

    def termin(self, vorgang, status="geplant", typ="vot", tage=3):
        t = VotTermin(vorgang_id=vorgang.id, ad_id=self.ad.id, beginn=datetime.now() + timedelta(days=tage),
                      ende=datetime.now() + timedelta(days=tage, hours=1), status=status, typ=typ,
                      medium={"vot": "vor_ort", "telefon": "telefon", "online": "teams"}[typ])
        self.s.add(t)
        self.s.commit()
        return t

    def kunde(self, vorgang):
        self.s.expire_all()
        return self.s.get(Kunde, vorgang.kunde_id)

    def frisch(self, vorgang):
        self.s.expire_all()
        return self.s.get(Vorgang, vorgang.id)

    def zeile(self, name):
        self.s.expire_all()
        return lead_kanaele.kanal_zeile(self.s, name)

    def client_fuer(self, benutzer):
        c = TestClient(app, follow_redirects=False)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer.id))
        return c

    def json_post(self, url, daten, client=None):
        return (client or self.client).post(url, json=daten, headers={"Accept": "application/json"})

    def inline(self, vorgang_id, daten, client=None):
        return self.json_post(f"/lead-management/boards/zeile/{vorgang_id}", daten, client)

    def aktivitaeten(self, vorgang_id, typ="aenderung"):
        self.s.expire_all()
        return [a.text for a in self.s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang_id, typ=typ)
                .order_by(LeadAktivitaet.id)]

    def zeile_html(self, seite: str, vorgang) -> str:
        self.assertIn(f'data-vorgang="{vorgang.id}"', seite)
        return seite.split(f'data-vorgang="{vorgang.id}"', 1)[1].split("</tr>", 1)[0]


# --- (h) Kanäle WeLoveX und DAA -------------------------------------------------------------------

class A_Kanaele(Basis):
    def test_a_migration_deaktiviert_zweiter_lauf_still(self):
        for name in KANAELE:
            zeile = self.zeile(name)
            self.assertIsNotNone(zeile, name)
            self.assertFalse(zeile.aktiv, name)
            self.assertTrue(any(f"'{name}' deaktiviert" in m for m in self.meldungen), (name, self.meldungen))
            self.assertNotIn(name, kern.kanal_werte(self.s))
            self.assertNotIn(name, lead_kanaele.kanal_namen_sortiert(self.s, mit_unklar=True))
        self.assertEqual(self.meldungen_zweiter_lauf, [])
        self.assertEqual(lead_kanaele.migration_v37_kanaele(self.s), [])
        for m in self.meldungen:
            self.assertNotIn("→", m)
            m.encode("cp1252")
        # die v35-Migration legt die inaktiven Kanäle nicht erneut an (Zeile vorhanden, nur inaktiv)
        self.assertEqual([m for m in lead_kanaele.migration_v35_kanaele(self.s) if "angelegt" in m], [])
        self.s.commit()
        for name in KANAELE:
            self.assertFalse(self.zeile(name).aktiv, name)

    def test_b_altlead_behaelt_label_chips_weg(self):
        self.assertEqual(self.kunde(self.v_daa).vertriebskanal, "DAA")
        self.assertEqual(self.kunde(self.v_welovex).vertriebskanal, "WELOVEX")
        # Kanal-Optionen: nur am betroffenen Lead als „(nicht mehr wählbar)“
        optionen = lead_kanaele.kanal_optionen(self.s, "DAA")
        daa = [o for o in optionen if o["name"] == "DAA"]
        self.assertEqual(len(daa), 1)
        self.assertFalse(daa[0]["aktiv"])
        self.assertEqual(daa[0]["label"], "DAA (nicht mehr wählbar)")
        self.assertEqual([o for o in lead_kanaele.kanal_optionen(self.s, "") if o["name"] in KANAELE], [])
        wahl = {k["wert"]: k for k in lead_boards.kanal_auswahl(self.s, "DAA")}
        self.assertFalse(wahl["DAA"]["waehlbar"])
        self.assertNotIn("WELOVEX", lead_boards.kanal_auswahl(self.s, ""))
        # Hauptboard: Label am Alt-Lead sichtbar, Filter-Select ohne WELOVEX/DAA
        seite = self.client.get("/lead-management/hauptboard?q=" + NACHNAME + "-1").text
        zeile = self.zeile_html(seite, self.v_daa)
        self.assertIn(">DAA</span>", zeile)
        self.assertIn("DAA (nicht mehr wählbar)", zeile)
        filter_select = seite.split('<select name="kanal">', 1)[1].split("</select>", 1)[0]
        for name in KANAELE:
            self.assertNotIn(f'value="{name}"', filter_select, name)
        deals = self.client.get("/lead-management/terminiert").text
        filter_deals = deals.split('<select name="kanal">', 1)[1].split("</select>", 1)[0]
        for name in KANAELE:
            self.assertNotIn(f'value="{name}"', filter_deals, name)
        # die Kanalliste je Tabelle (Template) führt die inaktiven Kanäle nicht
        vorlage = seite.split("<template data-lm-kanal-optionen>", 1)[1].split("</template>", 1)[0]
        self.assertNotIn('value="WELOVEX"', vorlage)
        # Kartei: Dropdown zeigt den Kanal nur am betroffenen Lead als „(nicht mehr wählbar)“
        kartei = self.client.get(f"/lead-management/lead/{self.v_daa.id}").text
        self.assertIn("DAA (nicht mehr wählbar)", kartei)
        andere = self.client.get(f"/lead-management/lead/{self.v_welovex.id}").text
        self.assertNotIn("DAA", andere.split('name="vertriebskanal"', 1)[1].split("</select>", 1)[0])
        # Kanal-Pflegeseite: unter „nicht mehr wählbar“ mit Reaktivierung (bestehende Funktion)
        pflege = self.client.get("/lead-management/kanaele").text
        for name in KANAELE:
            zeile = self.zeile(name)
            self.assertIn(f"/lead-management/kanaele/{zeile.id}/aktivieren", pflege, name)

    def test_c_parameter_nur_gemeldet_nicht_geaendert(self):
        alt = kern.parameter_holen(self.s, "hv_ausschluss", "") or ""
        try:
            kern.parameter_setzen(self.s, "hv_ausschluss", "Enni; DAA; Messe")
            self.s.commit()
            self.assertEqual(lead_kanaele.parameter_treffer(self.s, "DAA"), ["hv_ausschluss"])
            self.assertEqual(lead_kanaele.parameter_treffer(self.s, "WELOVEX"), [])
            # Migration auf einem reaktivierten Kanal: Deaktivierung + Hinweis, Parameter bleibt
            self.zeile("DAA").aktiv = True
            self.s.commit()
            lead_kanaele.cache_leeren()
            meldungen = lead_kanaele.migration_v37_kanaele(self.s)
            self.s.commit()
            self.assertTrue(any("'DAA' deaktiviert" in m for m in meldungen), meldungen)
            self.assertTrue(any("Hinweis" in m and "hv_ausschluss" in m for m in meldungen), meldungen)
            self.assertEqual(kern.parameter_holen(self.s, "hv_ausschluss", ""), "Enni; DAA; Messe")
            self.assertFalse(self.zeile("DAA").aktiv)
            self.assertEqual(lead_kanaele.migration_v37_kanaele(self.s), [])
        finally:
            kern.parameter_setzen(self.s, "hv_ausschluss", alt)
            self.s.commit()


# --- (i) Interesse „PV vorhanden“ ------------------------------------------------------------------

class B_Interessen(Basis):
    def test_a_sparten_modul(self):
        self.assertEqual(sparten.SPARTEN, ("WP", "PV", "KL", "WB", "GW", "MS", "WA", "DMS"))
        self.assertEqual(sparten.INTERESSEN_MERKMALE, ("PVV",))
        self.assertEqual(sparten.INTERESSEN_ALLE, sparten.SPARTEN + ("PVV",))
        self.assertEqual(sparten.langname("PVV"), "PV vorhanden")
        self.assertEqual(sparten.codes("PVV,WP,PV"), ["WP", "PV", "PVV"])
        self.assertEqual(sparten.codes(["pvv"]), ["PVV"])
        self.assertEqual(sparten.erfassungs_codes("PVV,WP,PV"), ["WP", "PV"])
        self.assertEqual(sparten.erfassungs_codes("PVV"), [])
        self.assertEqual(sparten.merkmale("WP,PVV"), ["PVV"])
        self.assertTrue(sparten.pv_vorhanden("WP,PVV"))
        self.assertFalse(sparten.pv_vorhanden("WP,PV"))
        self.assertEqual(sparten.pv_vorhanden_text("WP,PVV"), "Sie haben bereits eine PV-Anlage")
        self.assertEqual(sparten.pv_vorhanden_text("WP"), "")
        # Kundentexte nennen das Merkmal nie
        self.assertEqual(sparten.sparten_text("WP,PVV"), "Wärmepumpe")
        self.assertEqual(sparten.sparten_text("WP,PVV", form="kurz"), "WP")
        self.assertEqual(sparten.sparten_text("PVV"), "")
        self.assertEqual(sparten.sparten_interesse("WP,PVV"), "Interesse an einer Wärmepumpe")
        self.assertEqual(sparten.sparten_interesse("PVV"), "Interesse an unseren Lösungen")
        self.assertFalse(sparten.ist_freitext_sparte("PVV"))
        self.assertNotIn("PVV", sparten.freitext_sparten())
        self.assertIn("PVV", sparten.langnamen_laden("").keys())
        # models: Häkchen-Liste kennt PVV, Lead.sparten (Erfassung) nicht
        self.assertIn("PVV", INTERESSE_CODES)
        self.assertEqual(Lead(interesse="WP,PVV").sparten, ["WP"])
        self.assertEqual(Lead(interesse="PVV").sparten, ["WP"])
        self.assertEqual(Lead(interesse="PVV,KL").interessen, ["KL", "PVV"])

    def test_b_kartei_haekchen_autospeichern_badge(self):
        v = self.lead(10)
        seite = self.client.get(f"/lead-management/lead/{v.id}").text
        block = seite.split('data-feld-gruppe="interesse"', 1)[1].split("</div>", 1)[0]
        self.assertIn('value="PVV"', block)
        self.assertIn("PV vorhanden", block)
        r = self.json_post(f"/lead-management/lead/{v.id}/feld", {"feld": "interesse", "wert": ["WP", "PVV"]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(self.kunde(v).interesse, "WP,PVV")
        self.assertTrue(any(t.startswith("Interesse") and "PVV" in t for t in self.aktivitaeten(v.id)),
                        self.aktivitaeten(v.id))
        # Hauptobjekt synchron, Kopf-Badge in der Kartei
        self.assertEqual(objekte_modul.vorgang_interessen(self.s, v.id), ["WP", "PVV"])
        seite = self.client.get(f"/lead-management/lead/{v.id}").text
        self.assertIn("chip-pvv", seite)
        self.assertIn('value="PVV" data-feld-teil="interesse" checked', seite)
        # Pflichtfeld „Interesse“: nur das Merkmal erfüllt es nicht
        r = self.json_post(f"/lead-management/lead/{v.id}/feld", {"feld": "interesse", "wert": ["PVV"]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.kunde(v).interesse, "PVV")
        self.assertIn("Interesse", lead_v2.pflichtfelder_offen(self.s, self.kunde(v), self.frisch(v)))
        self.assertIn("Interesse", lead_kartei.pflicht_offen_namen(self.s, self.kunde(v), self.frisch(v)))
        r = self.json_post(f"/lead-management/lead/{v.id}/feld", {"feld": "interesse", "wert": "WP,PVV"})
        self.assertTrue(r.json()["ok"], r.text)
        self.assertNotIn("Interesse", lead_v2.pflichtfelder_offen(self.s, self.kunde(v), self.frisch(v)))

    def test_c_schnellanlage_api_parser(self):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"anrede": "Frau", "vorname": "Schnell", "nachname": f"{NACHNAME}-schnell", "telefon": "0203 660901",
                 "strasse": "Im Knick 1", "plz": "47269", "ort": "Duisburg", "quelle_id": str(quelle.id),
                 "sparten": ["WP", "PVV"], "entscheidung": "neu"}
        r = self.client.post("/lead-management/neu", data=daten)
        self.assertEqual(r.status_code, 303, r.text[:300])
        kunde = self.s.query(Kunde).filter_by(nachname=f"{NACHNAME}-schnell").first()
        self.assertIsNotNone(kunde)
        self.assertEqual(kunde.interesse, "WP,PVV")
        # nur das Merkmal: keine Sparte → Fehlermeldung, kein Lead
        r = self.client.post("/lead-management/neu", data=dict(daten, nachname=f"{NACHNAME}-nur-pvv",
                                                               telefon="0203 660902", sparten=["PVV"]))
        self.assertEqual(r.status_code, 200)
        self.assertIn("Mindestens eine Sparte wählen.", r.text)
        self.assertIsNone(self.s.query(Kunde).filter_by(nachname=f"{NACHNAME}-nur-pvv").first())
        self.assertIn('value="PVV"', r.text)
        self.assertIn("PV vorhanden", r.text)
        # API: „PV vorhanden“ als Text, Code PVV
        self.assertEqual(leads_api._sparten_lesen(["WP", "PV vorhanden"]), ["WP", "PVV"])
        self.assertEqual(leads_api._sparten_lesen(["pvv", "Photovoltaik"]), ["PVV", "PV"])
        api = TestClient(app)
        r = api.post("/api/leads", json={"nachname": f"{NACHNAME}-api", "plz": "47269", "telefon": "0203 660903",
                                         "sparten": ["WP", "PV vorhanden"]}, headers={"X-Api-Key": API_KEY})
        self.assertEqual(r.status_code, 201, r.text)
        v = self.s.get(Vorgang, r.json()["vorgang_id"])
        self.assertEqual(self.kunde(v).interesse, "WP,PVV")
        r = api.post("/api/leads", json={"nachname": f"{NACHNAME}-api2", "plz": "47269", "telefon": "0203 660904",
                                         "sparten": "PV vorhanden"}, headers={"X-Api-Key": API_KEY})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertTrue(any(f.startswith("sparten") for f in r.json()["felder"]), r.text)
        # Parser (Formular-Standard „Sparte: …“)
        self.assertEqual(lead_parser._sparten_liste("WP, PV vorhanden"), ["WP", "PVV"])
        self.assertEqual(lead_parser._sparten_liste("Wärmepumpe; pvv"), ["WP", "PVV"])
        # Import (Schritt Zuordnung) und Schnellanlage nutzen dieselbe Häkchen-Liste inkl. PVV
        from app.routers import leadmanagement as lm_router
        self.assertIn(("PVV", "PV vorhanden"), lm_router.SPARTEN_WAHL)
        self.assertIn("PVV", lm_router.INTERESSEN)
        self.assertNotIn("PVV", lm_router.SPARTEN)

    def test_d_filter_boards_kein_erfassungsstart(self):
        v = self.lead(11, sparten_liste=("WP", "PVV"))
        self.assertEqual(self.kunde(v).interesse, "WP,PVV")
        ids = lambda f: {z["vorgang"].id for g in lead_boards.board_zeilen(self.s, self.admin, "hauptboard", f)["gruppen"]
                         for z in g["zeilen"]}
        self.assertIn(v.id, ids({"sparte": "PVV"}))
        self.assertNotIn(v.id, ids({"sparte": "KL"}))
        self.assertIn(v.id, ids(lead_boards.filter_aus_query({"sparte": "pvv"})))
        seite = self.client.get("/lead-management/hauptboard?q=" + NACHNAME + "-11").text
        sparte_select = seite.split('<select name="sparte">', 1)[1].split("</select>", 1)[0]
        self.assertIn('value="PVV"', sparte_select)
        self.assertIn("PV vorhanden", sparte_select)
        zeile = self.zeile_html(seite, v)
        self.assertIn("chip-pvv", zeile)
        self.assertIn("chip-merkmal", zeile)
        # Sparten-Start: kein Häkchen „PVV“, WP vorausgewählt
        r = self.client.get(f"/erfassung/sparten?kunde_id={v.kunde_id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn('name="sparte_WP"', r.text)
        self.assertNotIn("sparte_PVV", r.text)
        # Kompetenz: Merkmal wird übergangen (AD mit Kompetenz WP)
        profil = self.s.query(AdProfil).filter_by(benutzer_id=self.ad.id).first()
        ok, grund = lead_v2.kompetenz_passt(profil, ["WP", "PVV"])
        self.assertTrue(ok, grund)
        ok, grund = lead_v2.kompetenz_passt(profil, ["WP", "PVV", "KL"])
        self.assertFalse(ok)
        self.assertIn("KL", grund)
        self.assertNotIn("PVV", grund)
        # Mein-Tag-Helfer: Erfassungs-Sparten ohne Merkmal
        from app import mein_tag
        objekt = objekte_modul.hauptobjekt(self.s, v.id)
        self.assertEqual(mein_tag._objekt_sparten(objekt, ["WP"]), ["WP"])
        # Mails: {sparten} ohne PVV, {pv_vorhanden} gefüllt
        werte = lead_mail.werte_fuer(self.s, self.frisch(v))
        self.assertEqual(werte["sparten"], "Wärmepumpe")
        self.assertEqual(werte["sparten_interesse"], "Interesse an einer Wärmepumpe")
        self.assertEqual(werte["pv_vorhanden"], "Sie haben bereits eine PV-Anlage")
        self.assertNotIn("PVV", werte["sparten_hinweise"])
        self.assertNotIn("PV vorhanden", werte["sparten_hinweise"])
        self.assertIn("{pv_vorhanden}", lead_mail.PLATZHALTER_NEU)
        ohne = self.lead(12)
        self.assertEqual(lead_mail.werte_fuer(self.s, self.frisch(ohne))["pv_vorhanden"], "")

    def test_e_vorbelegung_wp_bogen_a11(self):
        v = self.lead(13, sparten_liste=("WP", "PVV"))
        kunde = self.kunde(v)
        self.assertEqual(lead_kartei.pv_vorhanden_vorbelegung(kunde, "WP"),
                         {"A11": {"wert": "Ja", "info": "aus Kundenkartei (Interesse „PV vorhanden“)"}})
        self.assertEqual(lead_kartei.pv_vorhanden_vorbelegung(kunde, "KL"), {})
        self.assertEqual(lead_kartei.pv_vorhanden_vorbelegung(self.kunde(self.lead(14)), "WP"), {})
        objekt = objekte_modul.hauptobjekt(self.s, v.id)
        self.assertEqual(lead_kartei.pv_vorhanden_vorbelegung(objekt, "WP")["A11"]["wert"], "Ja")
        # echter Sparten-Start (WP): A11 = Ja mit Kennzeichen „vorbelegt“
        r = self.client.post("/erfassung/sparten-start", data={"kunde_id": str(kunde.id), "lead_id": "0", "sparte_WP": "on"})
        self.assertEqual(r.status_code, 303, r.text[:300])
        erfassung = (self.s.query(Erfassung).filter_by(kunde_id=kunde.id, sparte="WP")
                     .order_by(Erfassung.id.desc()).first())
        self.assertIsNotNone(erfassung)
        self.assertEqual(json.loads(erfassung.antworten_json or "{}").get("A11"), "Ja")
        self.assertIn("A11", json.loads(erfassung.vorbelegt_json or "{}"))
        self.assertIn("PV vorhanden", json.loads(erfassung.vorbelegt_json or "{}")["A11"])


# --- (j) Inline-Interessen mit Plus ------------------------------------------------------------------

class C_InlinePlus(Basis):
    def test_a_plus_markup_und_abwaehlen_mit_aktivitaet(self):
        v = self.lead(20, sparten_liste=("WP", "PV"))
        seite = self.client.get("/lead-management/hauptboard?q=" + NACHNAME + "-20").text
        zeile = self.zeile_html(seite, v)
        self.assertIn('class="lm-popover" data-feld="interessen"', zeile)   # v35-Markup bleibt (Alt-Tests)
        popover = zeile.split('class="lm-popover" data-feld="interessen"', 1)[1].split("</details>", 1)[0]
        self.assertIn('data-plus="1"', popover)                               # Plus-Variante (CSS/JS)
        summary = popover.split("<summary", 1)[1].split("</summary>", 1)[0]
        self.assertIn('d="M5 12h14"', summary)            # Plus-Symbol (_symbole.html)
        self.assertNotIn("M17 3a2.85", summary)            # kein Stift (Pfad des Symbols „stift“)
        for s in sparten.INTERESSEN_ALLE:
            self.assertIn(f'value="{s}"', popover, s)
        self.assertIn("PV vorhanden", popover)
        self.assertIn('value="PV" checked', popover)
        self.assertIn("lm-popover-chip", popover)
        self.assertIn("lm-popover-ok", popover)
        # Abwählen: Liste ohne PV → Aktivität, Zeile ohne chip-pv
        r = self.inline(v.id, {"feld": "interessen", "wert": ["WP"], "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(self.kunde(v).interesse, "WP")
        self.assertNotIn("chip-pv ", r.json()["zeile_html"])
        self.assertNotIn('class="chip chip-pv chip', r.json()["zeile_html"])
        texte = self.aktivitaeten(v.id)
        self.assertTrue(any(t.startswith("Interesse") and "WP, PV" in t and "→" in t for t in texte), texte)
        # „PV vorhanden“ wählbar
        r = self.inline(v.id, {"feld": "interessen", "wert": ["WP", "PVV"], "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.kunde(v).interesse, "WP,PVV")
        self.assertIn("chip-pvv", r.json()["zeile_html"])
        self.assertIn('value="PVV" checked', r.json()["zeile_html"])
        self.assertEqual(len([t for t in self.aktivitaeten(v.id) if t.startswith("Interesse")]), 2)
        # derselbe Wert erneut → keine Aktivität
        r = self.inline(v.id, {"feld": "interessen", "wert": "WP,PVV", "board": "hauptboard"})
        self.assertTrue(r.json()["ok"])
        self.assertEqual(len([t for t in self.aktivitaeten(v.id) if t.startswith("Interesse")]), 2)
        # Lesesicht (Außendienst, fremder Lead): Badges ohne Plus
        fremd = self.lead(21, ad=False, sparten_liste=("WP", "PVV"))
        z = lead_boards.zeile_fuer(self.s, self.ad, fremd)
        self.assertIsNotNone(z)
        self.assertFalse(z["bearbeitbar"])

    def test_b_deals_und_hv_ansicht(self):
        v = self.lead(22, phase="terminiert", sparten_liste=("WP",))
        self.termin(v)
        deals = self.client.get("/lead-management/terminiert?q=" + NACHNAME + "-22").text
        zeile = self.zeile_html(deals, v)
        self.assertIn('data-plus="1"', zeile)
        self.assertIn('d="M5 12h14"', zeile)
        hv_lead = self.lead(23, ad=False, ad_id=self.hv.id)
        r = self.inline(hv_lead.id, {"feld": "interessen", "wert": ["WP", "PVV"], "board": "handelsvertreter",
                                     "zurueck": "/lead-management/handelsvertreter"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["board"], "handelsvertreter")
        self.assertIn('data-plus="1"', r.json()["zeile_html"])
        self.assertIn("chip-pvv", r.json()["zeile_html"])
        self.assertEqual(self.kunde(hv_lead).interesse, "WP,PVV")

    def test_c_skripte_und_regeln(self):
        js = (BASIS / "app" / "static" / "lm_boards.js").read_text(encoding="utf-8")
        self.assertIn("details.lm-popover[open] > summary", js)
        self.assertNotIn("popoverTimer", js)
        self.assertIn("popoverVerwerfen", js)
        self.assertIn("e.key !== 'Escape'", js)
        css = (BASIS / "app" / "static" / "lead_v37_l3.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,8}\b")
        for teil in (".chip-pvv", ".lm-popover[data-plus] > summary", ".lm-popover-chip input:checked + .chip",
                     "var(--status-grau)"):
            self.assertIn(teil, css, teil)
        basis = (BASIS / "app" / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn("lead_v37_l3.css", basis)
        tabelle = (BASIS / "app" / "templates" / "leadmanagement" / "_tabelle.html").read_text(encoding="utf-8")
        interessen = tabelle.split("{%- elif key == 'interessen' -%}", 1)[1].split("{%- elif key == 'objektart' -%}", 1)[0]
        self.assertIn("symbol('plus')", interessen)
        self.assertNotIn("symbol('stift')", interessen)
        self.assertNotIn("key == 'angebot'", tabelle)
        self.assertNotIn('action="/lead-management/termin/', tabelle)   # kein Formular „Bestätigung erneut“ mehr
        self.assertNotRegex(tabelle, r'\son[a-z]+="[^"]*tojson(?!\s*\|\s*forceescape)')


# --- (k) Deals-Board ---------------------------------------------------------------------------------

class D_Deals(Basis):
    def test_a_ohne_knopf_spalte_erfassung_starten(self):
        v = self.lead(30, phase="terminiert")
        t = self.termin(v)
        seite = self.client.get("/lead-management/terminiert?q=" + NACHNAME + "-30").text
        zeile = self.zeile_html(seite, v)
        self.assertIn('data-gruppe="angebotserstellung"', seite)
        for teil in ("Bestätigung erneut", "bestaetigung-erneut", "Erfassung starten", 'class="sp-angebot"',
                     f"/erfassung/sparten?kunde_id={v.kunde_id}", 'data-key="angebot"', "lm-mini-aktionen"):
            self.assertNotIn(teil, seite, teil)
        self.assertIn("lm-termin-link", zeile)   # Termin bleibt Anzeige + Link in die Kartei
        self.assertEqual([sp["key"] for sp in lead_boards.spalten_fuer(self.s, self.admin, "terminiert")],
                         [k for k, _, _ in lead_boards.SPALTEN])
        self.assertIs(lead_boards.SPALTEN_TERMINIERT, lead_boards.SPALTEN)
        self.assertNotIn("angebot", [k for k, _, _ in lead_boards.spalten_basis("terminiert")])
        # Route „Terminbestätigung erneut senden“ bleibt (Kartei, Block Termine)
        r = self.client.post(f"/lead-management/termin/{t.id}/bestaetigung-erneut", data={})
        self.assertNotEqual(r.status_code, 404, r.text[:200])
        self.assertIn(r.status_code, (200, 303))

    def test_b_alte_spaltenkonfiguration_ohne_fehler(self):
        alt = {"terminiert": {"spalten": [{"key": "lead", "sichtbar": True, "name": ""},
                                          {"key": "angebot", "sichtbar": True, "name": "Erf./Ang."},
                                          {"key": "status", "sichtbar": True, "name": ""},
                                          {"key": "telefon", "sichtbar": False, "name": ""}],
                              "sort": {"key": "angebot", "richtung": "auf"}}}
        lead_v2.einstellung_setzen(self.s, self.lm.id, lead_boards.EINSTELLUNG_KEY, alt)
        self.s.commit()
        spalten = lead_boards.spalten_fuer(self.s, self.lm, "terminiert")
        keys = [sp["key"] for sp in spalten]
        self.assertNotIn("angebot", keys)
        self.assertEqual(keys[:3], ["lead", "status", "telefon"])
        self.assertFalse(next(sp for sp in spalten if sp["key"] == "telefon")["sichtbar"])
        self.assertIsNone(lead_boards.sortierung_fuer(self.s, self.lm, "terminiert"))
        client = self.client_fuer(self.lm)
        self.lead(31, phase="terminiert")
        r = client.get("/lead-management/terminiert")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('data-key="angebot"', r.text)
        r = client.get("/lead-management/boards/spalten?board=terminiert")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("angebot", [sp["key"] for sp in r.json()["spalten"]])
        # Speichern über die Oberfläche filtert den alten Key heraus
        r = self.json_post("/lead-management/boards/spalten",
                           {"board": "terminiert", "spalten": [{"key": "lead", "sichtbar": True},
                                                               {"key": "angebot", "sichtbar": True},
                                                               {"key": "ort", "sichtbar": True}]}, client)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("angebot", [sp["key"] for sp in r.json()["spalten"]])


# --- (j) Browser: Plus-Popover in Chrome headless (DevTools, Muster test_lead_v6_boards.py) ---------

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT, CDP = 8142, 9352


class PlusPopoverImBrowser(Basis):
    """Echter Browser: Klick auf das Plus öffnet das Popover, Klick auf einen Chip wählt an/ab,
    Klick daneben speichert per fetch (Zeile ersetzt, neuer Chip sichtbar), Escape schließt ohne
    Speichern (Häkchen zurückgesetzt), Klick auf das Plus eines offenen Popovers speichert.
    Prüft damit auch die Laufzeit des geänderten lm_boards.js (keine Runtime-Ausnahmen)."""

    @classmethod
    def setUpClass(cls):
        import shutil  # noqa: F401
        import subprocess
        import tempfile
        import urllib.request
        if not Path(CHROME).exists():
            raise unittest.SkipTest("Chrome nicht installiert")
        try:
            import uvicorn
            import websockets  # noqa: F401
        except ImportError as fehler:
            raise unittest.SkipTest(f"Paket fehlt: {fehler}")
        super().setUpClass()
        import threading
        cls.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT,
                                                   log_level="warning", lifespan="off"))
        cls.thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.thread.start()
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/login", timeout=1)
                break
            except Exception:   # noqa: BLE001
                time.sleep(0.5)
        cls.profil = Path(tempfile.mkdtemp(prefix="chrome_v37_l3_"))
        cls.chrome = subprocess.Popen(
            [CHROME, "--headless=new", f"--remote-debugging-port={CDP}",
             f"--user-data-dir={cls.profil}", "--window-size=1366,900", "--no-first-run",
             "--disable-gpu", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.ws_url = ""
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{CDP}/json", timeout=2) as a:
                    seiten = json.loads(a.read().decode("utf-8"))
                cls.ws_url = next(s["webSocketDebuggerUrl"] for s in seiten if s.get("type") == "page")
                break
            except Exception:   # noqa: BLE001
                time.sleep(0.5)
        if not cls.ws_url:
            cls.tearDownClass()
            raise unittest.SkipTest("Chrome DevTools nicht erreichbar")

    @classmethod
    def tearDownClass(cls):
        import shutil
        import tempfile
        try:
            cls.chrome.kill()
        except Exception:   # noqa: BLE001
            pass
        if getattr(cls, "server", None) is not None:
            cls.server.should_exit = True
            cls.thread.join(timeout=10)
        shutil.rmtree(getattr(cls, "profil", Path(tempfile.gettempdir()) / "chrome_v37_l3_leer"), ignore_errors=True)
        super().tearDownClass()

    def _lauf(self, schritte):
        import asyncio
        import websockets
        basis = f"http://127.0.0.1:{PORT}"
        fehler: list[str] = []

        async def lauf():
            async with websockets.connect(self.ws_url, max_size=20_000_000) as ws:
                nr = [0]

                async def senden(methode, **params):
                    nr[0] += 1
                    await ws.send(json.dumps({"id": nr[0], "method": methode, "params": params}))
                    while True:
                        antwort = json.loads(await ws.recv())
                        if antwort.get("method") == "Runtime.exceptionThrown":
                            fehler.append(json.dumps(antwort["params"].get("exceptionDetails", {}))[:400])
                        if antwort.get("id") == nr[0]:
                            return antwort.get("result", {})

                async def oeffnen(pfad, cookie_id=1):
                    await senden("Network.setCookie", name=auth.COOKIE_NAME,
                                 value=auth.cookie_wert(cookie_id), url=basis)
                    await senden("Page.navigate", url=basis + pfad)
                    await asyncio.sleep(1.5)

                async def js(ausdruck):
                    r = await senden("Runtime.evaluate", expression=ausdruck, returnByValue=True,
                                     awaitPromise=True)
                    if "exceptionDetails" in r:
                        fehler.append(json.dumps(r["exceptionDetails"])[:400])
                    return r.get("result", {}).get("value")

                async def warten(sekunden):
                    await asyncio.sleep(sekunden)

                await senden("Network.enable")
                await senden("Runtime.enable")
                await schritte(oeffnen, js, warten)

        asyncio.run(lauf())
        return fehler

    def test_plus_popover_im_browser(self):
        v = self.lead(50, sparten_liste=("WP", "PV"))
        ergebnis = {}
        zeile = "document.querySelector('tr[data-vorgang=\"" + str(v.id) + "\"]')"
        popover = zeile + ".querySelector('details.lm-popover[data-feld=interessen]')"

        async def schritte(oeffnen, js, warten):
            await oeffnen(f"/lead-management/hauptboard?q={NACHNAME}-50")
            ergebnis["plus"] = await js("!!" + popover + ".querySelector('summary path[d=\"M5 12h14\"]')")
            # 1. Klick auf das Plus öffnet, Klick auf den Chip KL wählt an, Klick daneben speichert
            await js("(function(){var d=" + popover + "; d.querySelector('summary').click(); return d.open;})()")
            ergebnis["offen"] = await js(popover + ".open")
            await js("(function(){" + popover + ".querySelector('input[value=KL]').click(); return true;})()")
            ergebnis["kl_haken"] = await js(popover + ".querySelector('input[value=KL]').checked")
            await js("(function(){document.body.click(); return true;})()")
            await warten(1.8)
            ergebnis["chip_kl"] = await js("!!" + zeile + ".querySelector('.chip-kl')")
            ergebnis["zu_nach_speichern"] = await js("!" + popover + ".open")
            # 2. Escape: PV abwählen, Escape → geschlossen, Häkchen zurück, Chip bleibt
            await js("(function(){var d=" + popover + "; d.querySelector('summary').click();"
                     " var cb=d.querySelector('input[value=PV]'); cb.click();"
                     " cb.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true})); return true;})()")
            await warten(0.6)
            ergebnis["esc_zu"] = await js("!" + popover + ".open")
            ergebnis["esc_pv_haken"] = await js(popover + ".querySelector('input[value=PV]').checked")
            ergebnis["chip_pv_bleibt"] = await js("!!" + zeile + ".querySelector('.chip-pv')")
            # 3. Plus eines offenen Popovers: WB anhaken, Plus klicken → speichert und schließt
            await js("(function(){var d=" + popover + "; d.querySelector('summary').click();"
                     " d.querySelector('input[value=WB]').click(); d.querySelector('summary').click(); return true;})()")
            await warten(1.8)
            ergebnis["chip_wb"] = await js("!!" + zeile + ".querySelector('.chip-wb')")
            ergebnis["zu_nach_plus"] = await js("!" + popover + ".open")

        fehler = self._lauf(schritte)
        self.assertEqual(fehler, [], fehler)
        for key in ("plus", "offen", "kl_haken", "chip_kl", "zu_nach_speichern", "esc_zu", "esc_pv_haken",
                    "chip_pv_bleibt", "chip_wb", "zu_nach_plus"):
            self.assertTrue(ergebnis.get(key), (key, ergebnis))
        self.assertEqual(self.kunde(v).interesse, "WP,PV,KL,WB")
        self.assertEqual(len([t for t in self.aktivitaeten(v.id) if t.startswith("Interesse")]), 2)


if __name__ == "__main__":
    unittest.main()
