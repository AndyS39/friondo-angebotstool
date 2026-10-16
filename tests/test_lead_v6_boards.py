# Tests PLAN_LEAD_V6 (v35, Agent B – Phase 186 ohne Objektfotos, Phase 187 Tests o/p/r):
# (o) Inline-Bearbeitung im Hauptboard – Interessen (Mehrfach), Vertriebskanal, Großkunde,
#     Objektart, Telefon, E-Mail, Teilgenommen – mit Aktivität (lead_kartei.feld_speichern) und
#     Rechten je Zeile (lead_v2.bearbeiten_erlaubt: Außendienst nur eigene Leads, Handelsvertreter
#     nur die eigene Gruppe), Zeile der Handelsvertreter-Ansicht (board=handelsvertreter),
#     Pflichtfeld-Verletzungen (rote Zelle, Kanal „?“);
# (p) gespeicherte Filter je Nutzer und Board (boards_filter): Standardfilter beim Öffnen,
#     URL-Parameter überschreiben ihn, ?filter=0 hebt ihn auf, Umbenennen/Löschen,
#     „für alle freigeben“ (Innendienst/Admin, schreibgeschützte Kopie bei den anderen);
# (r) Sofortsuche: „Kontaktiert“ mit EINER Suchleiste (Rufnummer „4711“ in q), Fragment-Route
#     ?fragment=1 der Boards und von Kontaktiert (JSON {ziele}), Filter-Chip aktualisiert die
#     Liste ohne Seitenneuladen, alle Seiten des Moduls mit data-lm-sofort; dazu ein Chrome-
#     headless-Test (DevTools, Muster test_v34_galerie.py) für Sofortsuche und Inline-Edit.
# Laufen gegen die DB-Kopie (DB_PFAD_OVERRIDE); Testdaten tragen den Nachnamen „V35B-Test“,
# Testbenutzer das Präfix „V35B “ – alles wird aufgeräumt (auch freigegebene Filter).
import asyncio
import json
import re
import shutil
import tempfile
import threading
import time
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, lead_boards, lead_info, lead_v2
from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Angebot, AngebotsNotiz, Benutzer, BenutzerEinstellung,
                        KommunikationLog, Kunde, LeadAktivitaet, LeadQuelle, Todo, Vorgang,
                        VorgangObjekt, VorgangsNotiz, VotTermin)

NACHNAME = "V35B-Test"
PRAEFIX = "V35B "
BASIS = Path(__file__).resolve().parents[1]
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT, CDP = 8141, 9351


def mit_wiederholung(funktion, versuche=12, pause=0.5):
    """SQLite kennt nur einen Schreiber – bei „database is locked“ kurz warten."""
    from sqlalchemy.exc import OperationalError
    for n in range(versuche):
        try:
            return funktion()
        except OperationalError as fehler:
            if "locked" not in str(fehler).lower() or n == versuche - 1:
                raise
            time.sleep(pause * (n + 1))


def geteilte_filter_aufraeumen(s):
    """Freigegebene Testfilter (globaler Eintrag benutzer_id 0) entfernen."""
    ablage = lead_boards._filter_ablage(s, lead_boards.FILTER_GLOBAL_BENUTZER, lead_boards.FILTER_GETEILT_KEY)
    geaendert = False
    for board, eintrag in list(ablage.items()):
        if not isinstance(eintrag, dict) or not isinstance(eintrag.get("filter"), list):
            continue
        vorher = len(eintrag["filter"])
        eintrag["filter"] = [f for f in eintrag["filter"]
                             if not str((f or {}).get("name", "")).startswith(PRAEFIX)]
        geaendert = geaendert or len(eintrag["filter"]) != vorher
    if geaendert:
        lead_v2.einstellung_setzen(s, lead_boards.FILTER_GLOBAL_BENUTZER, lead_boards.FILTER_GETEILT_KEY, ablage)


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            for tabelle in (LeadAktivitaet, KommunikationLog, VotTermin, VorgangObjekt, VorgangsNotiz, Todo):
                s.query(tabelle).filter_by(vorgang_id=v.id).delete()
            for a in s.query(Angebot).filter_by(vorgang_id=v.id):
                s.query(AngebotsNotiz).filter_by(angebot_id=a.id).delete()
                s.delete(a)
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(BenutzerEinstellung).filter_by(benutzer_id=b.id).delete()
        s.query(VotTermin).filter_by(ad_id=b.id).delete()
        s.delete(b)
    geteilte_filter_aufraeumen(s)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()

        def _aufraeumen():
            cls.s.rollback()
            aufraeumen(cls.s)
        mit_wiederholung(_aufraeumen)
        cls.client = TestClient(app)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        cls.admin = cls.s.get(Benutzer, 1)
        cls.parameter_alt = {name: kern.parameter_holen(cls.s, name, "") for name in
                             ("hv_gruppe_rene", "hv_gruppe_simon", "hv_gruppe_simon_mitglieder")}

        def _anlegen():
            cls.s.rollback()
            pin = auth.pin_hash("1234")
            cls.lm = Benutzer(name=f"{PRAEFIX}Claudia", vorname="Claudia", rolle="innendienst",
                              aktiv=True, leadmanager=True, pin_hash=pin)
            cls.lm2 = Benutzer(name=f"{PRAEFIX}Andrea", vorname="Andrea", rolle="innendienst",
                               aktiv=True, leadmanager=True, pin_hash=pin)
            cls.ad = Benutzer(name=f"{PRAEFIX}Horst", vorname="Horst", rolle="aussendienst",
                              aktiv=True, pin_hash=pin)
            cls.ad2 = Benutzer(name=f"{PRAEFIX}Detlef", vorname="Detlef", rolle="aussendienst",
                               aktiv=True, pin_hash=pin)
            cls.hv_rene = Benutzer(name=f"{PRAEFIX}Rene", vorname="René", rolle="aussendienst",
                                   aktiv=True, pin_hash=pin)
            cls.hv_simon = Benutzer(name=f"{PRAEFIX}Simon", vorname="Simon", rolle="aussendienst",
                                    aktiv=True, pin_hash=pin)
            cls.hv_paolo = Benutzer(name=f"{PRAEFIX}Paolo", vorname="Paolo", rolle="aussendienst",
                                    aktiv=True, pin_hash=pin)
            cls.s.add_all([cls.lm, cls.lm2, cls.ad, cls.ad2, cls.hv_rene, cls.hv_simon, cls.hv_paolo])
            cls.s.flush()
            for b in (cls.ad, cls.ad2):
                cls.s.add(AdProfil(benutzer_id=b.id, terminiert_selbst=False, aktiv_terminierung=True))
            for b in (cls.hv_rene, cls.hv_simon, cls.hv_paolo):
                cls.s.add(AdProfil(benutzer_id=b.id, terminiert_selbst=True, aktiv_terminierung=True))
            kern.parameter_setzen(cls.s, "hv_gruppe_rene", str(cls.hv_rene.id))
            kern.parameter_setzen(cls.s, "hv_gruppe_simon", str(cls.hv_simon.id))
            kern.parameter_setzen(cls.s, "hv_gruppe_simon_mitglieder", str(cls.hv_paolo.id))
            cls.s.commit()
        mit_wiederholung(_anlegen)

    @classmethod
    def tearDownClass(cls):
        def _aufraeumen():
            cls.s.rollback()
            aufraeumen(cls.s)
            for name, wert in cls.parameter_alt.items():
                kern.parameter_setzen(cls.s, name, wert)
            cls.s.commit()
        try:
            mit_wiederholung(_aufraeumen)
        finally:
            cls.s.close()

    def lead(self, nr, phase="neu", sparten=("WP",), telefon=None, **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}", "plz": "47139",
                 "ort": "Duisburg", "telefon": telefon or f"0203 55{nr:04d}", "sparten": list(sparten),
                 "email": f"v35b{nr}@test.local", "strasse": f"Teststraße {nr}"}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        vorgang.lead_phase = phase
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def frisch(self, vorgang):
        self.s.expire_all()
        return self.s.get(Vorgang, vorgang.id)

    def kunde(self, vorgang):
        self.s.expire_all()
        return self.s.get(Kunde, vorgang.kunde_id)

    def client_fuer(self, benutzer):
        c = TestClient(app)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer.id))
        return c

    def json_post(self, url, daten, client=None):
        return (client or self.client).post(url, json=daten, headers={"Accept": "application/json"})

    def zeile(self, vorgang_id, daten, client=None):
        return self.json_post(f"/lead-management/boards/zeile/{vorgang_id}", daten, client)

    def aktivitaeten(self, vorgang_id, typ="aenderung"):
        self.s.expire_all()
        return [a.text for a in self.s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang_id, typ=typ)
                .order_by(LeadAktivitaet.id)]


# --- (o) Inline-Bearbeitung ---------------------------------------------------------------------

class O_InlineEdit(Basis):
    def test_interessen_und_kanal_mit_aktivitaet(self):
        v = self.lead(101, sparten=("WP",))
        r = self.zeile(v.id, {"feld": "interessen", "wert": ["WP", "PV", "MS"], "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        self.assertTrue(j["ok"])
        self.assertIn("zeile_html", j)
        self.assertIn("chip-pv", j["zeile_html"])
        self.assertIn("chip-ms", j["zeile_html"])
        self.assertEqual(self.kunde(v).interesse, "WP,PV,MS")
        texte = self.aktivitaeten(v.id)
        self.assertTrue(any(t.startswith("Interesse") and "WP, PV, MS" in t for t in texte), texte)
        # derselbe Wert erneut → keine zweite Aktivität; auch als kommagetrennter Text
        r = self.zeile(v.id, {"feld": "interessen", "wert": "WP,PV,MS", "board": "hauptboard"})
        self.assertTrue(r.json()["ok"], r.text)
        self.assertEqual(len([t for t in self.aktivitaeten(v.id) if t.startswith("Interesse")]), 1)
        r = self.zeile(v.id, {"feld": "interessen", "wert": ["XX"], "board": "hauptboard"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("Interesse unbekannt", r.json()["meldung"])
        # Vertriebskanal aus dem Dropdown (Vertrag K: lead_boards.kanal_auswahl) mit Aktivität
        wahl = [k for k in lead_boards.kanal_auswahl(self.s) if k["waehlbar"] and k["wert"] != "?"]
        self.assertTrue(wahl)
        kanal = wahl[0]["wert"]
        r = self.zeile(v.id, {"feld": "kanal", "wert": kanal, "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.kunde(v).vertriebskanal, kanal)
        self.assertTrue(self.kunde(v).kanal_manuell)
        self.assertTrue(any(t.startswith("Vertriebskanal:") and kanal in t for t in self.aktivitaeten(v.id)))
        self.assertIn(f'data-aktuell="{kanal}"', r.json()["zeile_html"])
        r = self.zeile(v.id, {"feld": "kanal", "wert": "Gibt-es-nicht-V35B", "board": "hauptboard"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(self.kunde(v).vertriebskanal, kanal)
        # Hauptboard: Kanal-Auswahl hinter der Pille, Interessen-Popover, Textzellen, Objektart-Spalte im Katalog
        seite = self.client.get("/lead-management/hauptboard?q=" + NACHNAME + "-101").text
        zeile = seite.split(f'data-vorgang="{v.id}"', 1)[1].split("</tr>", 1)[0]
        for teil in ('data-feld="kanal"', 'class="lm-popover" data-feld="interessen"', 'data-lm-text="1"',
                     'data-feld="telefon"', 'data-feld="email"', 'lm-popover-ok', 'class="sp-telefon"',
                     'class="sp-kanal"', 'class="sp-lead"'):
            self.assertIn(teil, zeile, teil)
        self.assertIn("objektart", [k for k, _, _ in lead_boards.SPALTEN])
        self.assertFalse(next(s for k, _, s in lead_boards.SPALTEN if k == "objektart"))

    def test_grosskunde_objektart_telefon_email_teilgenommen(self):
        v = self.lead(102)
        r = self.zeile(v.id, {"feld": "grosskunde", "wert": "1", "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(self.kunde(v).grosskunde)
        self.assertIn("Großkunde", r.json()["zeile_html"])
        r = self.zeile(v.id, {"feld": "grosskunde", "wert": "", "board": "hauptboard"})
        self.assertTrue(r.json()["ok"])
        self.assertFalse(self.kunde(v).grosskunde)
        r = self.zeile(v.id, {"feld": "objektart", "wert": "MFH", "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.kunde(v).objektart, "MFH")
        self.assertTrue(any(t.startswith("Objektart:") for t in self.aktivitaeten(v.id)))
        self.assertEqual(self.zeile(v.id, {"feld": "objektart", "wert": "XYZ"}).status_code, 422)
        r = self.zeile(v.id, {"feld": "telefon", "wert": "0203 123456", "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.kunde(v).telefon, "0203 123456")
        self.assertIn("0203 123456", r.json()["zeile_html"])
        self.assertEqual(self.zeile(v.id, {"feld": "telefon", "wert": "abc"}).status_code, 422)
        self.assertEqual(self.kunde(v).telefon, "0203 123456")
        r = self.zeile(v.id, {"feld": "email", "wert": "v35b-neu@test.local", "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.kunde(v).email, "v35b-neu@test.local")
        self.assertEqual(self.zeile(v.id, {"feld": "email", "wert": "kaputt"}).status_code, 422)
        # Teilgenommen (Infoabend) über dieselbe Route
        r = self.zeile(v.id, {"feld": "teilgenommen", "wert": "ja", "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIs(self.frisch(v).teilgenommen, True)
        self.assertEqual(self.zeile(v.id, {"feld": "teilgenommen", "wert": "vielleicht"}).status_code, 422)
        # unbekanntes Feld bleibt abgewiesen
        self.assertEqual(self.zeile(v.id, {"feld": "nachname", "wert": "x"}).status_code, 422)

    def test_rechte_ad_eigene_zeile_und_hv_gruppe(self):
        eigen = self.lead(103, ad_id=self.ad.id)
        fremd = self.lead(104, ad_id=self.ad2.id)
        c_ad = self.client_fuer(self.ad)
        r = self.zeile(eigen.id, {"feld": "interessen", "wert": ["WP", "PV"], "board": "hauptboard"}, c_ad)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.kunde(eigen).interesse, "WP,PV")
        self.assertEqual(self.zeile(fremd.id, {"feld": "interessen", "wert": ["PV"]}, c_ad).status_code, 404)
        self.assertEqual(self.kunde(fremd).interesse, "WP")
        # Großkunde darf der Außendienst nicht setzen (Regel der Kartei)
        self.assertEqual(self.zeile(eigen.id, {"feld": "grosskunde", "wert": "1"}, c_ad).status_code, 422)
        # Handelsvertreter: René nur René-Leads, Simons Gruppe (Simon + Paolo) gegenseitig
        rene_lead = self.lead(105, ad_id=self.hv_rene.id)
        simon_lead = self.lead(106, ad_id=self.hv_simon.id)
        c_rene, c_paolo = self.client_fuer(self.hv_rene), self.client_fuer(self.hv_paolo)
        self.assertTrue(lead_v2.bearbeiten_erlaubt(self.s, self.hv_rene, rene_lead))
        self.assertFalse(lead_v2.bearbeiten_erlaubt(self.s, self.hv_rene, simon_lead))
        self.assertTrue(lead_v2.bearbeiten_erlaubt(self.s, self.hv_paolo, simon_lead))
        self.assertTrue(lead_boards.bearbeiten_erlaubt(self.s, self.lm, fremd))
        r = self.zeile(rene_lead.id, {"feld": "kanal", "wert": "", "board": "handelsvertreter",
                                      "zurueck": "/lead-management/handelsvertreter"}, c_rene)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.zeile(simon_lead.id, {"feld": "notiz", "wert": "x"}, c_rene).status_code, 404)
        r = self.zeile(simon_lead.id, {"feld": "notiz", "wert": "Gruppe Simon", "board": "handelsvertreter"}, c_paolo)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.kunde(simon_lead).notizen, "Gruppe Simon")
        # Zeilen der Boards tragen das Recht (z.bearbeitbar) – HV-Ansicht rendert die Inline-Felder nur dann
        z = lead_boards.zeile_fuer(self.s, self.hv_rene, rene_lead)
        self.assertIsNotNone(z)
        self.assertTrue(z["bearbeitbar"])

    def test_hv_ansicht_zeile_pflichtfelder_und_kanal_unklar(self):
        v = self.lead(107, ad_id=self.hv_rene.id)
        r = self.zeile(v.id, {"feld": "interessen", "wert": ["WP", "KL"], "board": "handelsvertreter",
                              "zurueck": "/lead-management/handelsvertreter?offen=1"})
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        self.assertEqual(j["board"], "handelsvertreter")
        self.assertIn('class="sp-hv"', j["zeile_html"])
        self.assertIn(f'data-vorgang="{v.id}"', j["zeile_html"])
        self.assertIn("chip-kl", j["zeile_html"])                 # Interessen sind in der HV-Ansicht sichtbar
        self.assertIn('class="lm-popover" data-feld="interessen"', j["zeile_html"])
        self.assertIn('name="ad_id"', j["zeile_html"])            # Vertreter-Spalte (hv_zuweisung)
        # HV-Ansicht: Inline-Felder, Sofortsuche, gespeicherte Filter
        seite = self.client.get("/lead-management/handelsvertreter?q=" + NACHNAME + "-107").text
        self.assertIn('data-lm-inline="handelsvertreter"', seite)
        self.assertIn('data-lm-sofort="1"', seite)
        self.assertIn('id="lm-filterspeicher"', seite)
        self.assertIn('data-lm-sofort-ziel="gruppen"', seite)
        # Pflichtfeld Außendienst fehlt → rote Zelle; Kanal „?“ → Kanal-Zelle rot + Hinweis
        ohne = self.lead(108)
        if "ad_id" in lead_v2.pflichtfelder(self.s):
            z = lead_boards.zeile_fuer(self.s, self.admin, ohne)
            self.assertIn("ad", z["pflicht_zellen"])
            seite = self.client.get("/lead-management/hauptboard?q=" + NACHNAME + "-108").text
            zeile = seite.split(f'data-vorgang="{ohne.id}"', 1)[1].split("</tr>", 1)[0]
            self.assertIn('class="sp-ad" data-pflicht="1"', zeile)
            self.assertIn('class="sp-lead"', zeile)           # Kundenname-Zelle bleibt unmarkiert
        kunde = self.kunde(ohne)
        kunde.vertriebskanal = "?"
        self.s.commit()
        z = lead_boards.zeile_fuer(self.s, self.admin, self.frisch(ohne))
        self.assertTrue(z["kanal_unklar"])
        self.assertIn("kanal", z["pflicht_zellen"])
        seite = self.client.get("/lead-management/hauptboard?q=" + NACHNAME + "-108").text
        zeile = seite.split(f'data-vorgang="{ohne.id}"', 1)[1].split("</tr>", 1)[0]
        self.assertIn("lm-kanal-unklar", zeile)
        self.assertIn("Vertriebskanal klären", zeile)
        self.assertIn('class="sp-kanal" data-pflicht="1"', zeile)


# --- (p) gespeicherte Filter --------------------------------------------------------------------

class P_GespeicherteFilter(Basis):
    def test_standardfilter_beim_oeffnen(self):
        pv = self.lead(201, sparten=("PV",))
        wp = self.lead(202, sparten=("WP",))
        c = self.client_fuer(self.lm)
        r = self.json_post("/lead-management/boards/filter",
                           {"board": "hauptboard", "aktion": "speichern", "name": f"{PRAEFIX}Nur PV",
                            "standard": True, "werte": {"q": NACHNAME, "sparte": "PV", "meldung": "weg",
                                                        "sort": {"key": "lead", "richtung": "ab"},
                                                        "gruppen_zu": ["pausiert"]}}, c)
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        self.assertTrue(j["ok"])
        f = next(x for x in j["filter"] if x["name"] == f"{PRAEFIX}Nur PV")
        self.assertTrue(f["standard"])
        self.assertEqual(j["standard_id"], f["id"])
        self.assertEqual(f["werte"]["sparte"], "PV")
        self.assertNotIn("meldung", f["werte"])
        self.assertEqual(f["werte"]["sort"], {"key": "lead", "richtung": "ab"})
        # Öffnen ohne Parameter: Standardfilter greift (nur PV-Lead, Name im Kopf, Gruppe Pausiert zu)
        seite = c.get("/lead-management/hauptboard").text
        self.assertIn(f"/lead-management/lead/{pv.id}", seite)
        self.assertNotIn(f"/lead-management/lead/{wp.id}", seite)
        self.assertIn(f"Filter „{PRAEFIX}Nur PV“", seite)
        self.assertIn('name="sparte"', seite)
        self.assertIn('<option value="PV" selected', seite)
        self.assertRegex(seite, r'<details class="lm-gruppe"\s+data-gruppe="pausiert"')
        # URL-Parameter überschreiben den Standardfilter; ?filter=0 hebt ihn auf
        seite = c.get("/lead-management/hauptboard?q=" + NACHNAME).text
        self.assertIn(f"/lead-management/lead/{wp.id}", seite)
        self.assertNotIn("Filter „", seite.split('id="lm-filterblock"')[0])
        seite = c.get("/lead-management/hauptboard?filter=0").text
        self.assertIn(f"/lead-management/lead/{wp.id}", seite)
        # Fragment-Antwort nutzt denselben Standardfilter
        j = c.get("/lead-management/hauptboard?fragment=1").json()
        self.assertIn(f"/lead-management/lead/{pv.id}", j["ziele"]["gruppen"])
        self.assertNotIn(f"/lead-management/lead/{wp.id}", j["ziele"]["gruppen"])
        # Standard aufheben, Umbenennen, Löschen
        r = self.json_post("/lead-management/boards/filter", {"board": "hauptboard", "aktion": "standard", "id": None}, c)
        self.assertTrue(r.json()["ok"], r.text)
        self.assertIsNone(r.json()["standard_id"])
        seite = c.get("/lead-management/hauptboard").text
        self.assertIn(f"/lead-management/lead/{wp.id}", seite)
        r = self.json_post("/lead-management/boards/filter",
                           {"board": "hauptboard", "aktion": "umbenennen", "id": f["id"], "name": f"{PRAEFIX}PV neu"}, c)
        self.assertTrue(r.json()["ok"], r.text)
        self.assertIn(f"{PRAEFIX}PV neu", [x["name"] for x in r.json()["filter"]])
        self.assertNotIn(f"{PRAEFIX}Nur PV", [x["name"] for x in r.json()["filter"]])
        # andere Nutzer sehen den eigenen Filter nicht
        fremd = self.client_fuer(self.lm2).get("/lead-management/boards/filter?board=hauptboard").json()["filter"]
        self.assertNotIn(f"{PRAEFIX}PV neu", [x["name"] for x in fremd])
        r = self.json_post("/lead-management/boards/filter", {"board": "hauptboard", "aktion": "loeschen", "id": f["id"]}, c)
        self.assertTrue(r.json()["ok"], r.text)
        self.assertNotIn(f"{PRAEFIX}PV neu", [x["name"] for x in r.json()["filter"]])
        self.assertEqual(self.json_post("/lead-management/boards/filter",
                                        {"board": "hauptboard", "aktion": "speichern", "name": "  ", "werte": {}}, c).status_code, 400)
        self.assertEqual(self.json_post("/lead-management/boards/filter",
                                        {"board": "gibt-es-nicht", "aktion": "speichern", "name": "x", "werte": {}}, c).status_code, 400)

    def test_freigabe_fuer_alle(self):
        self.lead(203, sparten=("KL",))
        c_lm, c_lm2 = self.client_fuer(self.lm), self.client_fuer(self.lm2)
        r = self.json_post("/lead-management/boards/filter",
                           {"board": "hauptboard", "aktion": "speichern", "name": f"{PRAEFIX}Team KL",
                            "werte": {"q": NACHNAME, "sparte": "KL"}}, c_lm)
        eigener = r.json()["filter"][0]
        r = self.json_post("/lead-management/boards/filter",
                           {"board": "hauptboard", "aktion": "freigeben", "id": eigener["id"]}, c_lm)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("für alle freigegeben", r.json()["meldung"])
        # bei der Freigebenden bleibt der Filter ein eigener (bearbeitbar), nicht doppelt
        self.assertEqual([f["geteilt"] for f in r.json()["filter"] if f["name"] == f"{PRAEFIX}Team KL"], [False])
        # andere Nutzer: schreibgeschützte Kopie (geteilt, nicht löschbar, nicht umbenennbar)
        j = c_lm2.get("/lead-management/boards/filter?board=hauptboard").json()
        geteilt = [f for f in j["filter"] if f["name"] == f"{PRAEFIX}Team KL"]
        self.assertEqual(len(geteilt), 1)
        g = geteilt[0]
        self.assertTrue(g["geteilt"])
        self.assertFalse(g["loeschbar"])
        self.assertEqual(g["von_name"], self.lm.name)
        self.assertEqual(g["werte"]["sparte"], "KL")
        self.assertEqual(self.json_post("/lead-management/boards/filter",
                                        {"board": "hauptboard", "aktion": "loeschen", "id": g["id"]}, c_lm2).status_code, 400)
        self.assertEqual(self.json_post("/lead-management/boards/filter",
                                        {"board": "hauptboard", "aktion": "umbenennen", "id": g["id"], "name": "x"}, c_lm2).status_code, 400)
        # … aber als eigener Standard nutzbar
        r = self.json_post("/lead-management/boards/filter", {"board": "hauptboard", "aktion": "standard", "id": g["id"]}, c_lm2)
        self.assertTrue(r.json()["ok"], r.text)
        seite = c_lm2.get("/lead-management/hauptboard").text
        self.assertIn(f"Filter „{PRAEFIX}Team KL“", seite)
        seite = c_lm2.get("/lead-management/hauptboard").text
        self.assertIn('<option value="KL" selected', seite)
        # die Seite zeigt die Leiste mit dem geteilten Eintrag (schreibgeschützt: kein Umbenennen-Knopf)
        block = seite.split('id="lm-filterliste"', 1)[1].split("</ul>", 1)[0]
        self.assertIn(f"{PRAEFIX}Team KL", block)
        self.assertIn('data-geteilt="1"', block)
        self.assertNotIn("lm-filter-umbenennen", block)
        # Außendienst darf nicht freigeben; Admin darf eine fremde Freigabe entfernen
        self.assertFalse(lead_boards.filter_freigabe_erlaubt(self.ad))
        self.assertTrue(lead_boards.filter_freigabe_erlaubt(self.lm))
        r = self.json_post("/lead-management/boards/filter",
                           {"board": "hauptboard", "aktion": "freigabe_entfernen", "id": g["id"]})
        self.assertEqual(r.status_code, 200, r.text)
        j = c_lm2.get("/lead-management/boards/filter?board=hauptboard").json()
        self.assertEqual([f for f in j["filter"] if f["name"] == f"{PRAEFIX}Team KL"], [])
        # der eigene Filter der Freigebenden bleibt, ohne Freigabe-Verweis
        j = c_lm.get("/lead-management/boards/filter?board=hauptboard").json()
        self.assertEqual([(f["name"], f["geteilt_id"]) for f in j["filter"] if f["name"] == f"{PRAEFIX}Team KL"],
                         [(f"{PRAEFIX}Team KL", None)])
        # Freigabe erneut → neue Kopie; Ersteller nimmt sie selbst zurück
        r = self.json_post("/lead-management/boards/filter",
                           {"board": "hauptboard", "aktion": "freigeben", "id": eigener["id"]}, c_lm)
        self.assertTrue(r.json()["ok"], r.text)
        r = self.json_post("/lead-management/boards/filter",
                           {"board": "hauptboard", "aktion": "freigabe_entfernen", "id": eigener["id"]}, c_lm)
        self.assertTrue(r.json()["ok"], r.text)
        self.assertEqual([f for f in c_lm2.get("/lead-management/boards/filter?board=hauptboard").json()["filter"]
                          if f["name"] == f"{PRAEFIX}Team KL"], [])

    def test_infoabend_und_hv_ansicht_mit_standardfilter(self):
        self.lead(204, ad_id=self.hv_rene.id)
        c = self.client_fuer(self.lm)
        for board, pfad, werte in (("info", "/lead-management/info-veranstaltung", {"q": NACHNAME, "status": "neu"}),
                                   ("handelsvertreter", "/lead-management/handelsvertreter", {"q": NACHNAME, "offen": "1"})):
            r = self.json_post("/lead-management/boards/filter",
                               {"board": board, "aktion": "speichern", "name": f"{PRAEFIX}{board}",
                                "standard": True, "werte": werte}, c)
            self.assertEqual(r.status_code, 200, r.text)
            seite = c.get(pfad).text
            self.assertIn(f"Filter „{PRAEFIX}{board}“", seite, pfad)
            self.assertIn(f'value="{NACHNAME}"', seite, pfad)
            self.assertNotIn("Filter „", c.get(pfad + "?filter=0").text.split('id="lm-filterblock"')[0], pfad)
        seite = c.get("/lead-management/handelsvertreter").text
        self.assertIn('name="offen" value="1"', seite)
        # Normierung: Schlüssel/Werte bereinigt, Query-Ersatz liefert Listen
        w = lead_boards.werte_normieren({"q": " x ", "kanal": ["A", "B"], "böse key": "1", "seite": "3",
                                         "grosskunde": True, "sort": {"key": "", "richtung": "ab"}})
        self.assertEqual(w, {"q": "x", "kanal": ["A", "B"], "grosskunde": "1"})
        fw = lead_boards.FilterWerte(w)
        self.assertEqual(fw.getlist("kanal"), ["A", "B"])
        self.assertEqual(fw.get("kanal"), "A")
        self.assertEqual(fw.get("fehlt", "std"), "std")


# --- (r) Sofortsuche ----------------------------------------------------------------------------

class R_Sofortsuche(Basis):
    def test_kontaktiert_eine_suchleiste_mit_rufnummer(self):
        v = self.lead(301, telefon="+49 203 770 4711")
        andere = self.lead(302, telefon="0203 123456")
        kern.aktivitaet(self.s, v.id, "anruf", "Anruf: Erreicht – Rückruf vereinbart",
                        benutzer=self.admin, ergebnis="erreicht")
        kern.aktivitaet(self.s, andere.id, "anruf", "Anruf: Mailbox", benutzer=self.admin, ergebnis="mailbox")
        self.s.commit()
        seite = self.client.get("/lead-management/kontaktiert").text
        inhalt = seite.split("<main", 1)[1]
        # eine Suchleiste: kein separates Rufnummernfeld, kein „Suchen“-Knopf außerhalb von noscript
        self.assertNotIn('name="telefon"', inhalt)
        self.assertEqual(inhalt.count('type="search" name="q"'), 1)
        self.assertNotIn("Suchen</button>", re.sub(r"<noscript>.*?</noscript>", "", inhalt, flags=re.S))
        self.assertIn('data-lm-sofort="1"', seite)
        self.assertIn("lm_sofort.js", seite)
        # „4711“ in der allgemeinen Suchleiste findet die Rufnummer (Endziffern, E.164)
        for eingabe in ("4711", "770 4711", "+49 203 770 / 4711"):
            seite = self.client.get("/lead-management/kontaktiert", params={"q": eingabe}).text
            self.assertIn(f"/lead-management/lead/{v.id}", seite, eingabe)
            self.assertNotIn(f"/lead-management/lead/{andere.id}", seite, eingabe)
            self.assertIn("endet mit", seite, eingabe)
        # Text sucht weiter Name/Notiz/E-Mail; der alte Parameter telefon= bleibt als Alias
        seite = self.client.get("/lead-management/kontaktiert?q=Rückruf+vereinbart").text
        self.assertIn(f"/lead-management/lead/{v.id}", seite)
        self.assertNotIn(f"/lead-management/lead/{andere.id}", seite)
        self.assertIn(f"/lead-management/lead/{v.id}", self.client.get("/lead-management/kontaktiert?q=v35b301").text)
        self.assertIn(f"/lead-management/lead/{v.id}", self.client.get("/lead-management/kontaktiert?telefon=4711").text)
        # Fragment-Route für die Sofortsuche: nur die Tauschbereiche als JSON
        r = self.client.get("/lead-management/kontaktiert?q=4711&fragment=1")
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertTrue(j["ok"])
        self.assertEqual(sorted(j["ziele"]), ["kopf", "liste", "seiten", "treffer"])
        self.assertIn(f"/lead-management/lead/{v.id}", j["ziele"]["treffer"])
        self.assertIn('data-lm-sofort-ziel="treffer"', j["ziele"]["treffer"])
        self.assertNotIn("<html", j["ziele"]["liste"])
        self.assertEqual(j["treffer"], 1)
        d = lead_boards.kontaktiert_daten(self.s, self.admin, q="4711")
        self.assertEqual([t["vorgang"].id for t in d["treffer"]], [v.id])

    def test_hauptboard_fragment_und_filter_chip(self):
        gross = self.lead(303)
        klein = self.lead(304)
        kunde = self.kunde(gross)
        kunde.grosskunde = True
        self.s.commit()
        seite = self.client.get("/lead-management/hauptboard").text
        self.assertIn('id="lm-filterform" data-lm-sofort="1"', seite)
        self.assertIn('data-lm-sofort-ziel="gruppen"', seite)
        # Dialog „Filter speichern“ liegt außerhalb des Filterformulars (kein <form> im <form>)
        formular = seite.split('id="lm-filterform"', 1)[1].split("</form>", 1)[0]
        self.assertNotIn("<form", formular)
        self.assertNotIn('id="dlg-filter"', formular)
        self.assertIn('id="dlg-filter"', seite)
        self.assertIn('id="lm-filterspeicher"', formular)
        self.assertIn('data-lm-sofort-ziel="kopf"', seite)
        self.assertNotIn('onchange="this.form.submit()"', seite)
        ohne_noscript = re.sub(r"<noscript>.*?</noscript>", "", seite, flags=re.S)
        self.assertNotIn("Filtern</button>", ohne_noscript)
        self.assertIn("lm_sofort.js", seite)
        self.assertIn("lm_v35_b.css", seite)
        # Chip „Großkunde“ → Route liefert das Fragment ohne Seitenneuladen (JSON)
        r = self.client.get("/lead-management/hauptboard", params={"grosskunde": "1", "q": NACHNAME, "fragment": "1"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("application/json", r.headers["content-type"])
        j = r.json()
        self.assertIn(f"/lead-management/lead/{gross.id}", j["ziele"]["gruppen"])
        self.assertNotIn(f"/lead-management/lead/{klein.id}", j["ziele"]["gruppen"])
        self.assertEqual(j["anzahl"], 1)
        self.assertEqual(j["gruppen"]["neu"], 1)
        self.assertIn("<b>1</b> Leads", j["ziele"]["kopf"])
        self.assertTrue(j["ziele"]["gruppen"].startswith('<div class="lm-gruppen"'))
        j = self.client.get("/lead-management/hauptboard", params={"q": NACHNAME, "fragment": "1"}).json()
        self.assertIn(f"/lead-management/lead/{klein.id}", j["ziele"]["gruppen"])
        # Deals-Board und Infoabend liefern dieselben Bereiche
        j = self.client.get("/lead-management/terminiert?fragment=1").json()
        self.assertEqual(sorted(j["ziele"]), ["gruppen", "kopf"])
        # fragment_ziele: verschachtelte gleiche Tags, mehrere Bereiche
        ziele = lead_boards.fragment_ziele('<div><div data-lm-sofort-ziel="a"><div>x<input></div></div>'
                                           '<span data-lm-sofort-ziel="b">y</span></div>')
        self.assertEqual(ziele, {"a": '<div data-lm-sofort-ziel="a"><div>x<input></div></div>',
                                 "b": '<span data-lm-sofort-ziel="b">y</span>'})

    def test_alle_seiten_des_moduls_mit_sofortsuche(self):
        seiten = {"/lead-management/hauptboard": "gruppen", "/lead-management/terminiert": "gruppen",
                  "/lead-management/kontaktiert": "liste", "/lead-management/info-veranstaltung": "gruppen",
                  "/lead-management/handelsvertreter": "gruppen", "/lead-management/anrufliste": "liste",
                  "/lead-management/board": "kanban", "/lead-management/todos": "todos"}
        for pfad, ziel in seiten.items():
            r = self.client.get(pfad)
            self.assertEqual(r.status_code, 200, pfad)
            self.assertIn('data-lm-sofort="1"', r.text, pfad)
            self.assertIn(f'data-lm-sofort-ziel="{ziel}"', r.text, pfad)
            self.assertIn("lm_sofort.js", r.text, pfad)
            ohne_noscript = re.sub(r"<noscript>.*?</noscript>", "", r.text.split("<main", 1)[1], flags=re.S)
            self.assertNotIn('onchange="this.form.submit()"', ohne_noscript, pfad)
            self.assertNotIn("Filtern</button>", ohne_noscript, pfad)
            self.assertNotIn("Suchen</button>", ohne_noscript, pfad)
            # kein Formular im Formular (Dialog „Filter speichern“ steht außerhalb)
            for form in re.findall(r"<form\b[^>]*data-lm-sofort[^>]*>(.*?)</form>", r.text, flags=re.S):
                self.assertNotIn("<form", form, pfad)
        karte = self.client.get("/lead-management/karte").text
        self.assertNotIn("Aktualisieren</button>", re.sub(r"<noscript>.*?</noscript>", "", karte, flags=re.S))
        self.assertIn("addEventListener('change'", karte)
        self.assertIn("Filter wirken sofort", karte)
        # Chip-Links: Anrufliste und To-Dos nennen die Parameter, die Links steuern
        self.assertIn('data-lm-sofort-links="meine,sla,versuche_min,rueckruf,frei,grosskunde,eingang_von,eingang_bis"',
                      self.client.get("/lead-management/anrufliste").text)
        self.assertIn('data-lm-sofort-links="sicht,faellig"', self.client.get("/lead-management/todos").text)
        self.assertIn('data-lm-sofort-links="offen"', self.client.get("/lead-management/handelsvertreter").text)
        # TAIFUN-Übergabeliste (Agent T): Status-Links als Sofortfilter
        r = self.client.get("/lead-management/taifun-uebergaben")
        if r.status_code == 200:
            self.assertIn('data-lm-sofort-links="status"', r.text)
            self.assertIn('data-lm-sofort-ziel="taifun-liste"', r.text)
            self.assertIn("lm_sofort.js", r.text)

    def test_skripte_und_regeln(self):
        js = (BASIS / "app" / "static" / "lm_sofort.js").read_text(encoding="utf-8")
        for teil in ("AbortController", "history.replaceState", "VERZOEGERUNG = 300", "fragment", "lm-sofort:geladen",
                     "/lead-management/boards/filter", "data-lm-sofort-links", "Escape"):
            self.assertIn(teil, js, teil)
        boards = (BASIS / "app" / "static" / "lm_boards.js").read_text(encoding="utf-8")
        for teil in ("window.lmInline", "lm-popover", "td[data-lm-text]", "data-lm-inline", "lm-sofort:geladen"):
            self.assertIn(teil, boards, teil)
        info = (BASIS / "app" / "static" / "lm_info.js").read_text(encoding="utf-8")
        self.assertIn("window.lmInline.senden", info)
        css = (BASIS / "app" / "static" / "lm_v35_b.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,8}\b")
        for teil in ("td[data-pflicht]", ".lm-popover-inhalt", ".lm-filtermenue", "td[data-lm-text]"):
            self.assertIn(teil, css, teil)
        tabelle = (BASIS / "app" / "templates" / "leadmanagement" / "_tabelle.html").read_text(encoding="utf-8")
        self.assertIn("data-werte=\"{{ f.werte | tojson | forceescape }}\"", tabelle)
        self.assertNotRegex(tabelle, r'\son[a-z]+="[^"]*tojson(?!\s*\|\s*forceescape)')
        # Infoabend-Zeile rendert die neuen Inline-Elemente über dasselbe Makro
        v = self.lead(305)
        v.veranstaltung_id = None
        self.s.commit()
        html = self.client.get("/lead-management/hauptboard?q=" + NACHNAME + "-305").text
        self.assertIn('class="lm-popover" data-feld="interessen"', html)
        # Spaltenkatalog: Objektart sortierbar
        z = lead_boards.zeile_fuer(self.s, self.admin, v)
        self.assertIsNone(lead_boards._sortier_wert(z, "objektart"))
        self.kunde(v).objektart = "EFH"
        self.s.commit()
        self.assertEqual(lead_boards._sortier_wert(lead_boards.zeile_fuer(self.s, self.admin, self.frisch(v)), "objektart"), "efh")
        self.assertEqual(lead_info.KONFIG_BOARD, "info")


# --- (r) Browser: Sofortsuche und Inline-Edit in Chrome headless (DevTools) --------------------

class SofortsucheImBrowser(Basis):
    """Echter Browser (Chrome headless + DevTools, Muster test_v34_galerie.py): Tippen im
    Suchfeld filtert die Tabelle ohne Enter und ohne Seitenneuladen (URL spiegelt den Filter),
    Interessen-Popover speichert per fetch und ersetzt die Zeile; „4711“ in Kontaktiert
    zeigt den Treffer ohne Enter."""

    @classmethod
    def setUpClass(cls):
        import subprocess
        import urllib.request
        if not Path(CHROME).exists():
            raise unittest.SkipTest("Chrome nicht installiert")
        try:
            import uvicorn
            import websockets  # noqa: F401
        except ImportError as fehler:
            raise unittest.SkipTest(f"Paket fehlt: {fehler}")
        super().setUpClass()
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
        cls.profil = Path(tempfile.mkdtemp(prefix="chrome_v35_b_"))
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
        try:
            cls.chrome.kill()
        except Exception:   # noqa: BLE001
            pass
        if getattr(cls, "server", None) is not None:
            cls.server.should_exit = True
            cls.thread.join(timeout=10)
        shutil.rmtree(getattr(cls, "profil", Path(tempfile.gettempdir()) / "chrome_v35_b_leer"), ignore_errors=True)
        super().tearDownClass()

    def _lauf(self, schritte):
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

    def test_sofortsuche_und_popover_im_browser(self):
        a = self.lead(401, sparten=("WP",))
        b = self.lead(402, sparten=("WP",))
        tel = self.lead(403, telefon="+49 203 770 4711")
        ergebnis = {}

        async def schritte(oeffnen, js, warten):
            await oeffnen(f"/lead-management/hauptboard?q={NACHNAME}")
            ergebnis["vorher"] = await js("document.querySelectorAll('tr[data-vorgang]').length")
            # Tippen ohne Enter: nach der Verzögerung nur noch Lead 401, URL spiegelt den Filter
            await js("(function(){var f=document.getElementById('lm-suche'); f.value='" + NACHNAME + "-401';"
                     " f.dispatchEvent(new Event('input', {bubbles:true})); return true;})()")
            await warten(1.6)
            ergebnis["ids"] = await js("Array.from(document.querySelectorAll('tr[data-vorgang]')).map(function(t){return parseInt(t.dataset.vorgang,10)})")
            ergebnis["url"] = await js("window.location.search")
            ergebnis["kopf"] = await js("document.querySelector('[data-lm-sofort-ziel=\"kopf\"]').textContent")
            # Popover: PV anhaken und übernehmen → Zeile per fetch ersetzt, Chip PV sichtbar
            await js("(function(){var d=document.querySelector('tr[data-vorgang=\"" + str(a.id) + "\"] details.lm-popover');"
                     " d.open=true; var cb=d.querySelector('input[value=PV]'); cb.checked=true;"
                     " d.querySelector('.lm-popover-ok').click(); return true;})()")
            await warten(1.6)
            ergebnis["chip"] = await js("!!document.querySelector('tr[data-vorgang=\"" + str(a.id) + "\"] .chip-pv')")
            ergebnis["popover_zu"] = await js("!document.querySelector('tr[data-vorgang=\"" + str(a.id) + "\"] details.lm-popover[open]')")
            # Kontaktiert: „4711“ tippen → Treffer ohne Enter
            await oeffnen("/lead-management/kontaktiert")
            await js("(function(){var f=document.getElementById('lm-suche'); f.value='4711';"
                     " f.dispatchEvent(new Event('input', {bubbles:true})); return true;})()")
            await warten(1.6)
            ergebnis["treffer"] = await js("!!document.querySelector('[data-lm-sofort-ziel=\"treffer\"] a[href=\"/lead-management/lead/" + str(tel.id) + "\"]')")
            ergebnis["kontaktiert_url"] = await js("window.location.search")

        fehler = self._lauf(schritte)
        self.assertEqual(fehler, [], fehler)
        self.assertGreaterEqual(ergebnis["vorher"], 3)
        self.assertEqual(ergebnis["ids"], [a.id], ergebnis)
        self.assertNotIn(b.id, ergebnis["ids"])
        self.assertIn("q=" + NACHNAME + "-401", ergebnis["url"])
        self.assertIn("1", ergebnis["kopf"])
        self.assertTrue(ergebnis["chip"], ergebnis)
        self.assertTrue(ergebnis["popover_zu"])
        self.assertEqual(self.kunde(a).interesse, "WP,PV")
        self.assertTrue(ergebnis["treffer"], ergebnis)
        self.assertIn("q=4711", ergebnis["kontaktiert_url"])


if __name__ == "__main__":
    unittest.main()
