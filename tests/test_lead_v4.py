# Tests PLAN_LEAD_V4 (v29, Phase 144 – Agent L1): Teile (a)–(h) und (m).
# (a) HV-Login (Cookie v2, PIN-Wechsel erledigt): Icon-Leiste nur vier Einträge,
#     gesperrte Seiten (Hauptboard/Deals/Kontaktiert/Infoabend/Anrufliste/Vorlagen …)
#     leiten IMMER mit 303 auf die HV-Ansicht mit Hinweis um (Nachtrag 08.10.2026,
#     Antwort Andreas – vorher 404 ohne Referer), Gate HINTER der v27-Middleware
#     (PIN-Pflichtwechsel zuerst); (b) Karte für HV nur eigene Pins;
# (c) Sammelaktion „An Handelsvertreter verschieben“ an René und an Simon,
#     Ausschluss-Lead (Kanal Enni) übersprungen und gemeldet, keine Glocke;
# (d) Flyout-Markup vorhanden, kein overflow-x in der Nav-Spalte;
# (e) Spaltenbreite speichern/zurücksetzen nur für den Nutzer; (f) Dashboard
#     „Hallo, <Vorname>“ ohne „Ohne nächsten Schritt“/„Angebots-Wiedervorlagen“/
#     „Termine 7 Tage“, Wiedervorlage in 30 Tagen unter „Kommende“, Maps-Link;
# (g) Glocke nur To-Dos: Lead-Eingang und Zuweisung ohne Glocke, To-Do-Zuweisung
#     und Fremd-Erledigung mit Glocke, eigene Erledigung ohne, Betriebsglocke
#     art system bleibt im Zähler, Art per Parameter wieder einschaltbar;
# (h) Eingangsdatum „TT.MM.JJJJ, HH:MM Uhr“ in der Kartei (Kopf + Kundeninfo);
# (m) drei Vorschläge, erster „Ideal“, Kalenderspalten = Kandidaten, weitere
#     Kalender per Auswahl, kalender.json ohne gehaltene Verbindung, HV-Sperrzeit.
# Läuft gegen die (kopierte) Entwicklungs-DB; Testdaten tragen das Präfix
# „LeadV4L1“ und werden aufgeräumt; Routing luftlinie, Kalender-Sync aus
# (bzw. gemockt), Mail-Modus protokoll – kein Netzzugriff.
import json
import re
import time
import unittest
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import auth, benachrichtigungen, db, lead_boards, lead_dashboard, lead_glocken, lead_termin, lead_todos, lead_v2
from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, BenutzerEinstellung, KommunikationLog,
                        Kunde, LeadAktivitaet, LeadQuelle, Todo, Vorgang, VotTermin)

PRAEFIX = "LeadV4L1"
NACHNAME = "LeadV4L1-Test"
BASIS = (54.3, 7.6)                      # Bezugspunkt abseits aller echten Leads (Nordsee)
PROJEKT = Path(__file__).resolve().parents[1]
HV_GESPERRT = ["/lead-management/hauptboard", "/lead-management/terminiert",
               "/lead-management/kontaktiert", "/lead-management/info-veranstaltung",
               "/lead-management/anrufliste", "/lead-management/vorlagen",
               "/lead-management/board", "/lead-management/kalender",
               "/lead-management/uebersicht", "/lead-management/statistik",
               "/lead-management/statistik/kanal", "/lead-management/posteingang",
               "/lead-management/import", "/lead-management/neu",
               "/lead-management/boards/haupt", "/lead-management/kommunikation"]
# Seiten des V1-Routers (routers/leadmanagement.py, eigenes Demo-Gate _gate): sie
# leiten erst um, wenn _gate als erste Zeile lead_v2.hv_umleitung(request, session)
# aufruft (Vorschlag LC 4.1); bis dahin antwortet dort das Demo-Gate mit 404
HV_GESPERRT_V1 = ["/lead-management/anrufliste", "/lead-management/board",
                  "/lead-management/kalender", "/lead-management/uebersicht",
                  "/lead-management/statistik", "/lead-management/statistik/kanal",
                  "/lead-management/posteingang", "/lead-management/import",
                  "/lead-management/neu", "/lead-management/kommunikation"]


def mit_wiederholung(funktion, versuche=12, pause=0.5):
    for n in range(versuche):
        try:
            return funktion()
        except OperationalError as fehler:
            if "locked" not in str(fehler).lower() or n == versuche - 1:
                raise
            time.sleep(pause * (n + 1))


def naechster_werktag(tage_voraus: int = 3) -> datetime:
    tag = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tag += timedelta(days=tage_voraus)
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    return tag


def nav_html(seite: str) -> str:
    return seite.split('<nav class="lm-leiste', 1)[1].split("</nav>", 1)[0]


def nav_keys(seite: str) -> list[str]:
    return re.findall(r'class="lm-leiste-eintrag[^"]*"[^>]*data-key="([^"]+)"', nav_html(seite))


def inhalt(seite: str) -> str:
    """Nur der Seiteninhalt (ohne Kopfzeile/Glocke/Navigation)."""
    return seite.split("<main", 1)[1] if "<main" in seite else seite


def aufraeumen(s):
    s.rollback()
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.query(Todo).filter_by(vorgang_id=v.id).delete()
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            s.delete(v)
        s.delete(k)
    s.query(Todo).filter(Todo.titel.like(f"{PRAEFIX}%")).delete(synchronize_session=False)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(BenutzerEinstellung).filter_by(benutzer_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.query(VotTermin).filter_by(ad_id=b.id).delete()          # Sperrzeiten (vorgang_id 0)
        s.query(Todo).filter((Todo.an_benutzer_id == b.id) | (Todo.von_benutzer_id == b.id)).delete(
            synchronize_session=False)
        s.delete(b)
    s.commit()


class Basis(unittest.TestCase):
    PARAMETER = ("lead_freigabe_modus", "score_aktiv", "routing_anbieter", "kalender_sync",
                 "kalender_testpostfach", "mail_modus", "hv_ausschluss", "hv_gruppe_rene",
                 "hv_gruppe_simon", "vorschlaege_anzahl", "routen_start", lead_glocken.PARAMETER,
                 "hv_standard_benutzer", "kanal_ad_regel")

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        mit_wiederholung(lambda: aufraeumen(cls.s))
        cls.gesichert = {n: kern.parameter_holen(cls.s, n, "") for n in cls.PARAMETER}
        # „Weitere Kalender“ des Admins (ID 1) sichern und leeren – die Tests setzen sie
        cls.alt_weitere = lead_v2.einstellung_holen(cls.s, 1, lead_termin.EINSTELLUNG_WEITERE, None)
        lead_v2.einstellung_setzen(cls.s, 1, lead_termin.EINSTELLUNG_WEITERE, [])
        cls.s.commit()

        def _vorbereiten():
            cls.s.rollback()
            # Benutzer: Admin „Claudia“ (Vorname), zweiter Admin, HV Paolo/René/Simon, Innendienst
            cls.claudia = cls.benutzer("Castro", rolle="admin", vorname="Claudia")
            cls.zweiter = cls.benutzer("Admin B", rolle="admin")
            cls.innen = cls.benutzer("Innen", rolle="innendienst")
            cls.horst = cls.ad("Horst", ["WP", "PV", "KL", "WB"], kombi=True, mfh=True)
            cls.rudi = cls.ad("Rudi", ["WP", "PV"], kombi=True)
            cls.karl = cls.ad("Karl", ["PV"])          # keine WP-Kompetenz → kein Kandidat
            cls.paolo = cls.ad("Paolo Di Blasi", ["WP", "PV", "KL", "WB"], kombi=True, mfh=True,
                               terminiert_selbst=True)
            cls.rene = cls.ad("Rene Golaschewski HV", ["WP", "PV", "KL", "WB"], kombi=True,
                              terminiert_selbst=True)
            cls.simon = cls.ad("Simon O Grady HV", ["WP", "PV", "KL", "WB"], kombi=True,
                               terminiert_selbst=True)
            kern.parameter_setzen(cls.s, "lead_freigabe_modus", "admin")
            kern.parameter_setzen(cls.s, "score_aktiv", "aus")
            kern.parameter_setzen(cls.s, "routing_anbieter", "luftlinie")
            kern.parameter_setzen(cls.s, "kalender_sync", "aus")
            kern.parameter_setzen(cls.s, "mail_modus", "protokoll")
            kern.parameter_setzen(cls.s, "kanal_ad_regel", "")
            kern.parameter_setzen(cls.s, "hv_ausschluss", "Empfehlung; Messe; Sparkasse Duisburg; SWD; Enni")
            kern.parameter_setzen(cls.s, "hv_gruppe_rene", str(cls.rene.id))
            kern.parameter_setzen(cls.s, "hv_gruppe_simon", f"{cls.simon.id},{cls.paolo.id}")
            kern.parameter_setzen(cls.s, "hv_standard_benutzer", str(cls.simon.id))
            kern.parameter_setzen(cls.s, "vorschlaege_anzahl", "3")
            kern.parameter_setzen(cls.s, "routen_start", "Arnold-Overbeck-Straße 63-65, 47139 Duisburg")
            kern.parameter_setzen(cls.s, lead_glocken.PARAMETER, ",".join(lead_glocken.STANDARD_ARTEN))
            cls.s.commit()
        mit_wiederholung(_vorbereiten)
        cls.admin = cls.s.get(Benutzer, 1)
        cls.client = cls.cookie_client(cls.admin)
        cls.client_claudia = cls.cookie_client(cls.claudia)
        cls.client2 = cls.cookie_client(cls.zweiter)
        cls.client_paolo = cls.cookie_client(cls.paolo)
        lead_termin.vorschlaege_cache_leeren()

    @classmethod
    def tearDownClass(cls):
        def _aufraeumen():
            aufraeumen(cls.s)
            for n, w in cls.gesichert.items():
                kern.parameter_setzen(cls.s, n, w)
            lead_v2.einstellung_setzen(cls.s, 1, lead_termin.EINSTELLUNG_WEITERE, cls.alt_weitere or [])
            cls.s.commit()
        try:
            mit_wiederholung(_aufraeumen)
        finally:
            lead_termin.vorschlaege_cache_leeren()
            cls.s.close()

    # --- Stammdaten-Helfer -----------------------------------------------------------

    @classmethod
    def benutzer(cls, name, rolle="aussendienst", **extra):
        b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                     email=f"{name.lower().replace(' ', '')}@lv4.local", telefon="0203 1",
                     pin_hash=auth.pin_hash("4321"), **extra)
        cls.s.add(b)
        cls.s.flush()
        return b

    @classmethod
    def ad(cls, name, sparten, kombi=False, mfh=False, terminiert_selbst=False):
        b = cls.benutzer(name)
        cls.s.add(AdProfil(
            benutzer_id=b.id, start_adresse="Duisburg", start_lat=BASIS[0], start_lon=BASIS[1],
            arbeitszeiten=json.dumps({t: ["08:00", "18:00"] for t in ("mo", "di", "mi", "do", "fr")}),
            termin_dauer_min=90, puffer_min=30, max_termine_tag=3,
            gebiet_plz_praefixe=json.dumps([]), aktiv_terminierung=True,
            terminiert_selbst=terminiert_selbst, kompetenz_sparten=json.dumps(sparten),
            kompetenz_kombi=kombi, kompetenz_mfh=mfh, kompetenz_gewerbe=False))
        cls.s.flush()
        return b

    @staticmethod
    def cookie_client(benutzer):
        c = TestClient(app)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer.id))
        return c

    def lead(self, nr, phase="neu", kanal=None, geo=True, eingang=None, **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"anrede": "Herr", "vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}",
                 "plz": "47139", "ort": "Duisburg", "telefon": f"0203 88{nr:04d}",
                 "sparten": ["WP"], "strasse": "Teststraße 1", "email": f"v4l1-{nr}@test.local"}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        kunde = self.s.get(Kunde, vorgang.kunde_id)
        kunde.objektart = "EFH"
        if kanal is not None:
            kunde.vertriebskanal = kanal
        vorgang.demo = True
        vorgang.lead_phase = phase
        vorgang.naechste_aktion_am = None
        vorgang.leadmanager_id = None
        if geo:
            vorgang.lat, vorgang.lon, vorgang.geocode_status = BASIS[0], BASIS[1], "ok"
        if eingang is not None:
            vorgang.eingang_am = eingang
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def kunde(self, vorgang):
        return self.s.get(Kunde, vorgang.kunde_id)

    def frisch(self, vorgang):
        self.s.expire_all()
        return self.s.get(Vorgang, vorgang.id)

    def glocken(self, benutzer, text_wie: str = "%"):
        return (self.s.query(Benachrichtigung)
                .filter(Benachrichtigung.benutzer_id == benutzer.id,
                        Benachrichtigung.text.like(text_wie)).all())


# --- (a) HV-Login, Menü, 404-Gate ------------------------------------------------------

class A_HandelsvertreterSicht(Basis):
    def test_menue_vier_eintraege_und_404_gate(self):
        eigen = self.lead(1, ad_id=self.paolo.id)
        fremd = self.lead(2, ad_id=self.horst.id)
        r = self.client_paolo.get("/lead-management/dashboard")
        self.assertEqual(r.status_code, 200, r.text[:300])
        self.assertEqual(nav_keys(r.text), ["dashboard", "karte", "todos", "handelsvertreter"])
        self.assertNotIn('id="lm-mehr"', r.text)
        self.assertIn("Hallo, ", r.text)
        # Login-Ziel bleibt die HV-Ansicht (Modul-Einstieg → Dashboard, v23)
        r = self.client_paolo.get("/lead-management", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/lead-management/dashboard"))
        # gesperrte Seiten: Nachtrag 08.10.2026 (Antwort Andreas) – IMMER 303 auf die
        # HV-Ansicht mit Hinweis, auch ohne Referer (Lesezeichen/Mail-Link) und für
        # JSON-Routen; vorher 404 ohne Referer
        ziel = "/lead-management/handelsvertreter?meldung="
        v1_umgeleitet = "hv_umleitung" in (PROJEKT / "app" / "routers" / "leadmanagement.py").read_text(encoding="utf-8")
        for pfad in HV_GESPERRT:
            r = self.client_paolo.get(pfad, follow_redirects=False)
            if r.status_code == 404 and pfad in HV_GESPERRT_V1 and not v1_umgeleitet:
                continue   # V1-Demo-Gate ohne hv_umleitung (siehe HV_GESPERRT_V1)
            self.assertEqual(r.status_code, 303, pfad)
            self.assertTrue(r.headers["location"].startswith(ziel), (pfad, r.headers["location"]))
            self.assertIn("Diese Seite gibt es in der Handelsvertreter-Sicht nicht",
                          unquote_plus(r.headers["location"]), pfad)
        r = self.client_paolo.get("/lead-management/boards/haupt", follow_redirects=False,
                                  headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 303)
        # Direktlink aus dem Tool (Referer derselben Instanz) → dasselbe Ziel
        r = self.client_paolo.get("/lead-management/hauptboard", follow_redirects=False,
                                  headers={"referer": "http://testserver/lead-management/dashboard"})
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith(ziel))
        self.assertIn("Handelsvertreter-Sicht", unquote_plus(r.headers["location"]))
        # die Zielseite zeigt den Hinweis als Meldung
        seite = self.client_paolo.get(r.headers["location"])
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Diese Seite gibt es in der Handelsvertreter-Sicht nicht", seite.text)
        # erlaubt: Karte, To-Dos, Handelsvertreter, eigene Kartei + Assistent; fremde Kartei 404
        for pfad in ("/lead-management/karte", "/lead-management/todos",
                     "/lead-management/handelsvertreter", f"/lead-management/lead/{eigen.id}",
                     f"/lead-management/lead/{eigen.id}/termin",
                     f"/lead-management/lead/{eigen.id}/termin/kalender.json",
                     "/lead-management/boards/spalten?board=handelsvertreter"):
            r = self.client_paolo.get(pfad)
            self.assertEqual(r.status_code, 200, pfad)
            if '<nav class="lm-leiste' in r.text:
                self.assertEqual(nav_keys(r.text), ["dashboard", "karte", "todos", "handelsvertreter"], pfad)
                self.assertEqual(nav_html(r.text).count('aria-current="page"'), 1, pfad)
        self.assertEqual(self.client_paolo.get(f"/lead-management/lead/{fremd.id}").status_code, 404)
        # Kartei für HV: Innendienst nur Anzeige (kein Select), Autospeichern des Feldes abgewiesen
        kartei = self.client_paolo.get(f"/lead-management/lead/{eigen.id}").text
        self.assertNotIn('name="leadmanager_id"', kartei)
        self.assertIn('name="ad_id"', kartei)
        r = self.client_paolo.post(f"/lead-management/lead/{eigen.id}/feld",
                                   json={"feld": "leadmanager_id", "wert": str(self.innen.id)})
        self.assertEqual(r.status_code, 400)
        self.assertIsNone(self.frisch(eigen).leadmanager_id)
        # Innendienst/Admin sehen die volle Leiste
        self.assertEqual(nav_keys(self.client.get("/lead-management/dashboard").text)[:9],
                         ["dashboard", "hauptboard", "terminiert", "kontaktiert", "karte", "info",
                          "todos", "handelsvertreter", "mehr"])

    def test_gate_hinter_der_middleware(self):
        """v27: erst Login/PIN-Pflichtwechsel, dann das HV-Gate (303 auf die HV-Ansicht)."""
        anonym = TestClient(app)
        r = anonym.get("/lead-management/hauptboard", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/login"))
        self.paolo.pin_wechsel_noetig = True
        self.s.commit()
        try:
            r = self.client_paolo.get("/lead-management/hauptboard", follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertEqual(r.headers["location"], auth.PIN_WECHSEL_PFAD)
        finally:
            self.paolo.pin_wechsel_noetig = False
            self.s.commit()
        # Nachtrag 08.10.2026: nach dem PIN-Wechsel greift das Gate – 303 auf die HV-Ansicht
        r = self.client_paolo.get("/lead-management/hauptboard", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/lead-management/handelsvertreter?meldung="))
        self.assertTrue(lead_v2.hv_sicht(self.s, self.paolo))
        self.assertFalse(lead_v2.hv_sicht(self.s, self.admin))
        self.assertTrue(lead_v2.hv_pfad_gesperrt("/lead-management/statistik/kanal"))
        self.assertFalse(lead_v2.hv_pfad_gesperrt("/lead-management/boards/zeile/5"))


# --- (b) Karte für HV ---------------------------------------------------------------------

class B_KarteHV(Basis):
    def test_karte_nur_eigene_pins(self):
        eigen = self.lead(10, ad_id=self.paolo.id)
        fremd = self.lead(11, ad_id=self.horst.id)
        self.s.add(VotTermin(vorgang_id=eigen.id, ad_id=self.paolo.id, beginn=naechster_werktag(2) + timedelta(hours=10),
                             ende=naechster_werktag(2) + timedelta(hours=11, minutes=30), lat=BASIS[0], lon=BASIS[1],
                             status="geplant", typ="vot", demo=True))
        self.s.add(VotTermin(vorgang_id=fremd.id, ad_id=self.horst.id, beginn=naechster_werktag(2) + timedelta(hours=14),
                             ende=naechster_werktag(2) + timedelta(hours=15, minutes=30), lat=BASIS[0], lon=BASIS[1],
                             status="geplant", typ="vot", demo=True))
        self.s.commit()
        seite = self.client_paolo.get("/lead-management/karte")
        self.assertEqual(seite.status_code, 200)
        self.assertNotIn('name="ad_id"', seite.text)             # Filter Vertriebler ausgeblendet
        self.assertNotIn('name="leadmanager_id"', seite.text)
        self.assertIn('name="phase"', seite.text)
        self.assertIn('name="sparte"', seite.text)
        self.assertIn(f'data-lat="{BASIS[0]}"', seite.text)         # Mittelpunkt = eigene Leads
        pins = self.client_paolo.get("/lead-management/karte/daten").json()["pins"]
        leads = {p["vorgang_id"] for p in pins if p["art"] == "lead"}
        termine = {p["vorgang_id"] for p in pins if p["art"] == "termin"}
        starts = {p["ad"] for p in pins if p["art"] == "start"}
        self.assertIn(eigen.id, leads)
        self.assertNotIn(fremd.id, leads)
        self.assertIn(eigen.id, termine)
        self.assertNotIn(fremd.id, termine)
        self.assertEqual(starts, {self.paolo.name})
        # Innendienst/Admin unverändert: beide Leads
        pins_admin = self.client.get("/lead-management/karte/daten").json()["pins"]
        self.assertTrue({eigen.id, fremd.id} <= {p["vorgang_id"] for p in pins_admin if p["art"] == "lead"})


# --- (c) Sammelaktion „An Handelsvertreter verschieben“ -----------------------------------

class C_SammelaktionHV(Basis):
    def test_an_simon_und_rene_mit_ausschluss(self):
        a = self.lead(20)
        b = self.lead(21, ad_id=self.horst.id)
        c = self.lead(22, ad_id=self.rene.id)
        enni = self.lead(23, kanal="Enni")
        ids = [a.id, b.id, c.id, enni.id]
        self.assertIn(("hv_verschieben", "An Handelsvertreter verschieben"),
                      [(x["key"], x["titel"]) for x in lead_boards.sammelaktionen_fuer("hauptboard")])
        self.assertIn("hv_verschieben", [x["key"] for x in lead_boards.sammelaktionen_fuer("terminiert")])
        self.assertIn("hv_verschieben", [x["key"] for x in lead_boards.sammelaktionen_fuer("info")])
        glocken_vorher = len(self.glocken(self.simon))
        r = self.client.post("/lead-management/boards/sammelaktion",
                             data={"board": "hauptboard", "aktion": "hv_verschieben", "ziel": "simon",
                                   "ids": [str(i) for i in ids]}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        meldung = unquote_plus(r.headers["location"].split("meldung=", 1)[1])
        self.assertIn("3 verschoben, 1 übersprungen: Kanal Enni", meldung)
        self.assertNotIn("fehler=1", r.headers["location"])
        for v in (a, b, c):
            self.assertEqual(self.frisch(v).ad_id, self.simon.id, v.id)
        self.assertIsNone(self.frisch(enni).ad_id)
        # Aktivität je Lead („von X an Y“ beim Umhängen), keine Glocke (Phase 141)
        texte = [x.text for x in self.s.query(LeadAktivitaet).filter_by(vorgang_id=c.id)]
        self.assertTrue(any(t.startswith(f"Zugewiesen an {self.simon.name}") and f"(vorher {self.rene.name})" in t
                            for t in texte), texte)
        self.assertEqual(len(self.glocken(self.simon)), glocken_vorher)
        # die drei stehen in Simons HV-Sicht
        hv_seite = self.cookie_client(self.simon).get("/lead-management/handelsvertreter").text
        for v in (a, b, c):
            self.assertIn(f'data-vorgang="{v.id}"', hv_seite)
        self.assertNotIn(f'data-vorgang="{enni.id}"', hv_seite)
        # Ziel René (JSON-Variante), umgehängt von Simon
        r = self.client.post("/lead-management/boards/sammelaktion",
                             json={"board": "hauptboard", "aktion": "hv_verschieben", "ziel": "rene", "ids": [a.id]},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("1 verschoben", r.json()["meldung"])
        self.assertEqual(self.frisch(a).ad_id, self.rene.id)
        # Gesamtsicht: Filter „Gruppe“
        seite = self.client.get(f"/lead-management/handelsvertreter?gruppe=rene").text
        self.assertIn(f'data-vorgang="{a.id}"', seite)
        self.assertNotIn(f'data-vorgang="{b.id}"', seite)
        seite = self.client.get(f"/lead-management/handelsvertreter?gruppe=simon").text
        self.assertIn(f'data-vorgang="{b.id}"', seite)
        self.assertNotIn(f'data-vorgang="{a.id}"', seite)
        self.assertIn('name="gruppe"', seite)
        # Hauptboard zeigt die zwei Ziel-Schaltflächen mit den Namen aus der Benutzerverwaltung
        board = self.client.get("/lead-management/hauptboard").text
        self.assertIn('id="lm-sammel-hv"', board)
        self.assertEqual(re.findall(r'data-ziel="([^"]+)"', board), ["rene", "simon"])
        self.assertIn(f"{self.simon.name} (verteilt an sein Team)", board)
        # ohne Ziel-Parameter: klare Meldung, Außendienst darf nicht
        ok, text = lead_boards.sammelaktion_ausfuehren(self.s, self.admin, "hauptboard", "hv_verschieben", [b.id], {})
        self.assertFalse(ok)
        self.assertIn("Ziel-Handelsvertreter nicht gesetzt", text)
        ok, text = lead_boards.sammelaktion_ausfuehren(self.s, self.paolo, "hauptboard", "hv_verschieben", [b.id], {"ziel": "rene"})
        self.assertFalse(ok)
        self.s.rollback()


# --- (d) Flyout --------------------------------------------------------------------------

class D_Flyout(Basis):
    def test_flyout_markup_und_css(self):
        seite = self.client.get("/lead-management/hauptboard").text
        leiste = nav_html(seite)
        self.assertIn('<details class="lm-leiste-mehr', leiste)
        self.assertIn('id="lm-mehr"', leiste)
        self.assertIn('class="lm-leiste-menue" role="menu" aria-label="Mehr" data-flyout="1"', leiste)
        self.assertGreaterEqual(leiste.count('role="menuitem"'), 11)
        self.assertIn("/static/lm_nav.js", seite)
        css = (PROJEKT / "app" / "static" / "lead_v2.css").read_text(encoding="utf-8")
        # letzte Regel für .lm-leiste: overflow visible – kein horizontales Scrollen in der Spalte
        regeln = re.findall(r"(?m)^\.lm-leiste \{([^}]*)\}", css)
        self.assertTrue(regeln)
        self.assertIn("overflow: visible", regeln[-1])
        self.assertNotIn("overflow-x: auto", regeln[-1])
        self.assertNotIn("overflow-x: scroll", regeln[-1])
        flyout = re.findall(r"\.lm-leiste-mehr\[open\] \.lm-leiste-menue \{([^}]*)\}", css)
        self.assertIn("position: fixed", flyout[-1])
        self.assertIn("z-index: 45", flyout[-1])            # unter dem Wartungsbanner (50)
        self.assertIn("min-width: 240px", flyout[-1])
        js = (PROJEKT / "app" / "static" / "lm_nav.js").read_text(encoding="utf-8")
        self.assertIn("Escape", js)
        self.assertIn("lm-flyout-oben", js)
        # HV: kein „Mehr …“/Flyout
        self.assertNotIn('data-flyout', nav_html(self.client_paolo.get("/lead-management/dashboard").text))


# --- (e) Spaltenbreite je Nutzer ----------------------------------------------------------

class E_Spaltenbreite(Basis):
    def breite(self, client, key, board="hauptboard"):
        r = client.get(f"/lead-management/boards/spalten?board={board}")
        self.assertEqual(r.status_code, 200)
        return next(sp["breite"] for sp in r.json()["spalten"] if sp["key"] == key)

    def test_speichern_zuruecksetzen_nur_fuer_den_nutzer(self):
        for c in (self.client_claudia, self.client2):
            c.post("/lead-management/boards/spalten", json={"board": "hauptboard", "zuruecksetzen": True})
        r = self.client_claudia.post("/lead-management/boards/spalten",
                                     json={"board": "hauptboard", "breite": {"key": "notiz", "px": 300}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["meldung"], "Spaltenbreite gespeichert.")
        self.assertEqual(self.breite(self.client_claudia, "notiz"), 300)
        self.assertIsNone(self.breite(self.client2, "notiz"))              # nur dieser Nutzer
        self.assertIsNone(self.breite(self.client_claudia, "notiz", board="terminiert"))   # nur dieses Board
        # Grenzen 60–600 px
        self.client_claudia.post("/lead-management/boards/spalten", json={"board": "hauptboard", "breite": {"key": "ort", "px": 2000}})
        self.assertEqual(self.breite(self.client_claudia, "ort"), 600)
        self.client_claudia.post("/lead-management/boards/spalten", json={"board": "hauptboard", "breite": {"key": "ort", "px": 10}})
        self.assertEqual(self.breite(self.client_claudia, "ort"), 60)
        # Markup: <colgroup> mit der Breite, Ziehgriff im Spaltenkopf
        self.lead(30)
        seite = self.client_claudia.get("/lead-management/hauptboard").text
        self.assertIn('<col data-key="notiz" style="width:300px" class="lm-col-breite">', seite)
        self.assertIn('data-lm-breiten="1"', seite)
        self.assertIn('class="lm-th-griff" data-key="notiz"', seite)
        self.assertNotIn('style="width:300px"', self.client2.get("/lead-management/hauptboard").text)
        # Doppelklick = Standard (px null), Zurücksetzen räumt alles
        r = self.client_claudia.post("/lead-management/boards/spalten", json={"board": "hauptboard", "breite": {"key": "notiz", "px": None}})
        self.assertEqual(r.json()["meldung"], "Standardbreite.")
        self.assertIsNone(self.breite(self.client_claudia, "notiz"))
        self.assertEqual(self.breite(self.client_claudia, "ort"), 60)
        self.client_claudia.post("/lead-management/boards/spalten", json={"board": "hauptboard", "zuruecksetzen": True})
        self.assertIsNone(self.breite(self.client_claudia, "ort"))
        # ungültig
        r = self.client_claudia.post("/lead-management/boards/spalten", json={"board": "hauptboard", "breite": {"px": 100}})
        self.assertEqual(r.status_code, 400)
        # Struktur in benutzer_einstellungen (v25-Einträge ohne Breite = Standard)
        self.client_claudia.post("/lead-management/boards/spalten", json={"board": "hauptboard", "breite": {"key": "email", "px": 120}})
        self.s.expire_all()
        konfig = lead_v2.einstellung_holen(self.s, self.claudia.id, lead_boards.EINSTELLUNG_KEY, {})
        email = next(sp for sp in konfig["hauptboard"]["spalten"] if sp["key"] == "email")
        self.assertEqual(email["breite"], 120)
        self.assertTrue(all("breite" not in sp for sp in konfig["hauptboard"]["spalten"] if sp["key"] != "email"))
        self.client_claudia.post("/lead-management/boards/spalten", json={"board": "hauptboard", "zuruecksetzen": True})


# --- (f) Dashboard „Hallo, <Vorname>“ -------------------------------------------------------

class F_Dashboard(Basis):
    def test_hallo_vorname_bloecke_kommende_maps(self):
        jetzt = datetime.now()
        in30 = (jetzt + timedelta(days=30)).replace(hour=10, minute=0, second=0, microsecond=0)
        kommend = self.lead(40, phase="in_kontaktierung", leadmanager_id=self.claudia.id, naechste_aktion_am=in30)
        heute = self.lead(41, phase="in_kontaktierung", leadmanager_id=self.claudia.id,
                          naechste_aktion_am=jetzt - timedelta(hours=1))
        r = self.client_claudia.get("/lead-management/dashboard")
        self.assertEqual(r.status_code, 200, r.text[:300])
        seite = inhalt(r.text)
        self.assertIn("<h1>Hallo, Claudia", seite)
        self.assertNotIn("Meine Arbeit <", seite)
        for weg in ("Ohne nächsten Schritt", "Angebots-Wiedervorlagen", "Termine 7 Tage", 'id="ohne-schritt"'):
            self.assertNotIn(weg, seite, weg)
        for da in ("Fällig heute", "Kommende Wiedervorlagen", "Offene To-Dos", "Routenplaner",
                   "Meine Termine", 'id="kommende"', 'id="faellig"', 'id="todos"'):
            self.assertIn(da, seite, da)
        # Wiedervorlage in 30 Tagen (außerhalb des alten 7-Tage-Horizonts) unter „Kommende“
        kommende = seite.split('id="kommende"', 1)[1].split('id="todos"', 1)[0]
        self.assertIn(self.kunde(kommend).anzeige_name, kommende)
        self.assertIn(in30.strftime("%d.%m.%Y"), kommende)
        self.assertNotIn(self.kunde(heute).anzeige_name, kommende)
        faellig = seite.split('id="faellig"', 1)[1].split('id="kommende"', 1)[0]
        self.assertIn(self.kunde(heute).anzeige_name, faellig)
        # Maps-Link exakt wie im Plan (Start, Ziel leer, neuer Tab)
        link = re.search(r'id="lm-routen-link" href="([^"]+)"', seite).group(1).replace("&amp;", "&")
        self.assertEqual(link, "https://www.google.com/maps/dir/?api=1&origin=Arnold-Overbeck-Stra%C3%9Fe+63-65,+47139+Duisburg&travelmode=driving")
        self.assertIn('target="_blank"', seite)
        # Nachtrag 08.10.2026 (Antwort Andreas): „Mir zugeteilte Vorgänge“ ist vom
        # Dashboard entfernt (Block und Kontext); lead_dashboard.zugeteilte bleibt als Funktion
        self.assertNotIn("Mir zugeteilte Vorgänge", seite)
        self.assertNotIn('id="zugeteilt"', seite)
        # Daten: Vorname sonst Name, Kacheln nur die drei Zahlen (+ Mails mit Fehler)
        daten = lead_dashboard.daten(self.s, self.claudia)
        self.assertEqual(daten["anrede"], "Claudia")
        self.assertEqual(lead_dashboard.anrede_name(self.zweiter), self.zweiter.name)
        self.assertIn(kommend.id, [z["vorgang"].id for z in daten["lead_wv_kommend"]])
        self.assertEqual(set(daten["kacheln"]) >= {"faellig", "kommend", "todos", "mails_fehler"}, True)
        self.assertNotIn("ohne_schritt", daten["kacheln"])
        self.assertNotIn("angebot_wv", daten)
        self.assertNotIn("zugeteilt", daten)
        self.assertGreaterEqual(lead_dashboard.zugeteilte(self.s, self.claudia, False)["gesamt"], 2)
        # Gruppierung nach Datum, „mehr anzeigen“ ab 10 Zeilen
        gruppen = lead_dashboard.kommende_gruppieren(daten["lead_wv_kommend"])
        self.assertEqual([g["datum"] for g in gruppen], sorted({g["datum"] for g in gruppen}))
        for n in range(42, 54):
            self.lead(n, phase="in_kontaktierung", leadmanager_id=self.claudia.id,
                      naechste_aktion_am=in30 + timedelta(days=n - 40))
        seite = inhalt(self.client_claudia.get("/lead-management/dashboard").text)
        self.assertIn("weitere anzeigen", seite)
        self.assertIn('class="lm-kommende-mehr"', seite)
        # Routenplaner-Start aus dem Parameter
        kern.parameter_setzen(self.s, "routen_start", "Königstraße 1, 47798 Krefeld")
        self.s.commit()
        try:
            seite = inhalt(self.client_claudia.get("/lead-management/dashboard").text)
            self.assertIn("origin=K%C3%B6nigstra%C3%9Fe+1,+47798+Krefeld", seite)
        finally:
            kern.parameter_setzen(self.s, "routen_start", "Arnold-Overbeck-Straße 63-65, 47139 Duisburg")
            self.s.commit()
        # HV-Dashboard: Sperrzeiten-Formular, Meine Termine
        hv = inhalt(self.client_paolo.get("/lead-management/dashboard").text)
        self.assertIn('id="lm-sperrzeit-form"', hv)
        self.assertIn("Meine Sperrzeiten", hv)


# --- (g) Glocke nur To-Dos -----------------------------------------------------------------

class G_Glocke(Basis):
    def test_nur_todo_glocken_und_betriebsglocke_bleibt(self):
        a, b = self.claudia, self.innen
        vorher_a, vorher_b = len(self.glocken(a)), len(self.glocken(b))
        # Lead-Eingang (lead_anlegen) → keine Glocke (Art lead_eingang abgeschaltet)
        v = self.lead(60, leadmanager_id=b.id)
        v2 = self.lead(61)
        self.assertEqual(len(self.glocken(b, "Neuer Lead:%")), 0)
        # Zuweisung AD/Leadmanager → keine Glocke, Aktivität bleibt
        lead_v2.ad_zuweisen(self.s, v2, self.horst.id, benutzer=a)
        lead_v2.leadmanager_zuweisen(self.s, v2, b.id, benutzer=a)
        self.s.commit()
        self.assertEqual(len(self.glocken(self.horst, "Lead zugewiesen:%")), 0)
        self.assertEqual(len(self.glocken(b, "Lead übernommen:%")), 0)
        self.assertTrue(any(x.text.startswith("Zugewiesen an") for x in
                            self.s.query(LeadAktivitaet).filter_by(vorgang_id=v2.id)))
        # To-Do von A an B → Glocke bei B (Zähler 1)
        todo = lead_todos.anlegen(self.s, a, b.id, f"{PRAEFIX} Unterlagen prüfen", vorgang_id=v.id)
        self.s.commit()
        self.assertEqual(len(self.glocken(b, "To-Do von%")), 1)
        self.assertEqual(benachrichtigungen.ungelesen_anzahl(self.s, b), vorher_b + 1)
        # B erledigt → Glocke bei A; A erledigt eigenes To-Do → keine Glocke
        lead_todos.erledigen(self.s, todo, b)
        self.s.commit()
        self.assertEqual(len(self.glocken(a, "To-Do erledigt von%")), 1)
        eigen = lead_todos.anlegen(self.s, a, a.id, f"{PRAEFIX} eigenes To-Do")
        lead_todos.erledigen(self.s, eigen, a)
        self.s.commit()
        self.assertEqual(len(self.glocken(a, f"%{PRAEFIX} eigenes To-Do%")), 0)
        # B öffnet A's To-Do wieder → Glocke todo_aktualisiert bei A
        lead_todos.wieder_oeffnen(self.s, todo, b)
        self.s.commit()
        self.assertEqual(len(self.glocken(a, "To-Do wieder geöffnet von%")), 1)
        # Betriebsglocke art system bleibt im Zähler
        self.s.add(Benachrichtigung(benutzer_id=a.id, text=f"{PRAEFIX} Betriebswarnung", link="/parametrierung/betrieb", art="system"))
        self.s.commit()
        self.assertEqual(benachrichtigungen.ungelesen_anzahl(self.s, a), vorher_a + 3)
        self.assertIn(f"{PRAEFIX} Betriebswarnung", [e.text for e in benachrichtigungen.letzte(self.s, a, 20)])
        # Fälligkeits-Scheduler meldet nur To-Do-Fälligkeiten (an den Empfänger)
        faellig = lead_todos.anlegen(self.s, a, b.id, f"{PRAEFIX} fällig", faellig_am=datetime.now() - timedelta(minutes=5))
        self.s.commit()
        self.assertGreaterEqual(lead_todos.faellige_glocken(self.s), 1)
        self.s.commit()
        self.assertEqual(len(self.glocken(b, f"To-Do fällig: {PRAEFIX} fällig%")), 1)
        # Art „zuweisung“ per Parameter wieder einschaltbar
        kern.parameter_setzen(self.s, lead_glocken.PARAMETER, "todo_zugewiesen,todo_aktualisiert,zuweisung")
        self.s.commit()
        try:
            self.assertTrue(lead_glocken.glocke_erlaubt(self.s, "zuweisung"))
            lead_v2.ad_zuweisen(self.s, v2, self.rudi.id, benutzer=a)
            self.s.commit()
            self.assertEqual(len(self.glocken(self.rudi, "Lead zugewiesen:%")), 1)
        finally:
            kern.parameter_setzen(self.s, lead_glocken.PARAMETER, ",".join(lead_glocken.STANDARD_ARTEN))
            self.s.commit()
        self.assertFalse(kern.benachrichtigen(self.s, [a.id], f"{PRAEFIX} ohne Art", "/x"))
        self.assertEqual(len(self.glocken(a, f"{PRAEFIX} ohne Art")), 0)


# --- (h) Eingangsdatum in der Kartei ---------------------------------------------------------

class H_Eingangsdatum(Basis):
    def test_format_kopf_und_kundeninfo(self):
        eingang = datetime(2026, 10, 7, 14, 5)
        v = self.lead(70, eingang=eingang)
        seite = inhalt(self.client.get(f"/lead-management/lead/{v.id}").text)
        self.assertEqual(seite.count("07.10.2026, 14:05 Uhr"), 2)        # Kopf + Kundeninfo-Block
        self.assertNotIn("07.10.2026 14:05<", seite)
        self.assertEqual(seite.count("data-eingang"), 2)
        # Boards behalten das kurze Datum
        board = self.client.get("/lead-management/hauptboard").text
        zeile = board.split(f'data-vorgang="{v.id}"', 1)[1].split("</tr>", 1)[0]
        self.assertIn(">07.10.2026<", zeile)
        self.assertNotIn("14:05 Uhr", zeile)
        # Vertrag L2: Hinweisbalken-Include und E-Mail-Markierung
        self.assertIn("lead_mail", open(PROJEKT / "app" / "routers" / "lm_kartei.py", encoding="utf-8").read())
        v.email_status = "ungueltig"
        v.email_status_grund = "Unzustellbar (Test)"
        v.mail_fehler = True
        v.mail_fehler_text = "Senderecht fehlt (Test)"
        self.s.commit()
        seite = inhalt(self.client.get(f"/lead-management/lead/{v.id}").text)
        self.assertIn("lk-feld-email-ungueltig", seite)
        self.assertIn("Unzustellbar (Test)", seite)
        board = self.client.get("/lead-management/hauptboard").text
        zeile = board.split(f'data-vorgang="{v.id}"', 1)[0].rsplit("<tr ", 1)[1] + board.split(f'data-vorgang="{v.id}"', 1)[1].split("</tr>", 1)[0]
        self.assertIn("lm-rang0", zeile)
        self.assertLess(zeile.index("E-Mail falsch"), zeile.index("Mail nicht gesendet"))
        # Rang 0 steht in der Gruppe ganz oben
        gruppe = board.split('data-gruppe="neu"', 1)[1].split("</details>", 1)[0]
        self.assertEqual(re.findall(r'data-vorgang="(\d+)"', gruppe)[0], str(v.id))
        v.email_status = None
        v.mail_fehler = False
        self.s.commit()


# --- (m) Terminassistent: drei Vorschläge, Ideal, Kalenderansicht ----------------------------

class M_Terminassistent(Basis):
    def setUp(self):
        lead_termin.vorschlaege_cache_leeren()
        lead_v2.einstellung_setzen(self.s, 1, lead_termin.EINSTELLUNG_WEITERE, [])
        self.s.commit()

    def tearDown(self):
        lead_v2.einstellung_setzen(self.s, 1, lead_termin.EINSTELLUNG_WEITERE, [])
        self.s.commit()
        lead_termin.vorschlaege_cache_leeren()

    def test_drei_vorschlaege_ideal_kalender_weitere(self):
        v = self.lead(80)
        j = self.client.get(f"/lead-management/lead/{v.id}/termin/vorschlaege.json?neu=1").json()
        self.assertEqual(j["status"], "ok", j)
        self.assertEqual(j["anzahl"], 3)
        self.assertEqual(len(j["vorschlaege"]), 3)
        self.assertTrue(j["vorschlaege"][0]["ideal"])
        self.assertTrue(j["vorschlaege"][0]["ideal_grund"].startswith("Ideal:"))
        self.assertFalse(any(x["ideal"] for x in j["vorschlaege"][1:]))
        kandidaten = [k["ad_id"] for k in j["kandidaten"]]
        self.assertTrue({self.horst.id, self.rudi.id} <= set(kandidaten))
        self.assertNotIn(self.paolo.id, kandidaten)        # HV kein Kandidat für den Innendienst
        self.assertNotIn(self.karl.id, kandidaten)         # keine WP-Kompetenz
        # Parameter 5 → fünf; Standard 3 gilt auch im Block Termine der Kartei
        kern.parameter_setzen(self.s, "vorschlaege_anzahl", "5")
        self.s.commit()
        try:
            j5 = self.client.get(f"/lead-management/lead/{v.id}/termin/vorschlaege.json?neu=1").json()
            self.assertEqual((j5["anzahl"], len(j5["vorschlaege"])), (5, 5))
        finally:
            kern.parameter_setzen(self.s, "vorschlaege_anzahl", "3")
            self.s.commit()
        lead_termin.vorschlaege_cache_leeren()
        kartei = self.client.get(f"/lead-management/lead/{v.id}").text
        self.assertIn("Top 3 des Assistenten", kartei)
        # Assistent: Vorschlag 1 mit Rahmen/Badge „Ideal“, Kalender-Markup, Weitere Kalender
        seite = self.client.get(f"/lead-management/lead/{v.id}/termin").text
        self.assertEqual(seite.count('class="vorschlag-karte lmt-vorschlag'), 3)
        self.assertEqual(seite.count("lmt-ideal-badge"), 1)
        self.assertIn('data-ideal="1"', seite.split('data-nr="1"', 1)[0].rsplit("<div", 1)[1] + seite.split('data-nr="1"', 1)[1][:20])
        self.assertIn('id="lmt-kalender"', seite)
        self.assertIn('id="lmt-weitere"', seite)
        self.assertIn(f'data-url="/lead-management/lead/{v.id}/termin/kalender.json"', seite)
        self.assertNotIn("graph.microsoft.com", seite)
        # kalender.json: Spalten = Kandidaten, Standardwoche = Woche des ersten Vorschlags
        k = self.client.get(f"/lead-management/lead/{v.id}/termin/kalender.json").json()
        self.assertEqual([sp["ad_id"] for sp in k["spalten"]], kandidaten)
        self.assertTrue(all(sp["kandidat"] for sp in k["spalten"]))
        self.assertEqual(len(k["tage"]), 6)
        self.assertEqual(k["raster"]["schritt"], 15)
        erster = datetime.strptime(j["vorschlaege"][0]["beginn"], "%Y-%m-%dT%H:%M")
        montag = (erster - timedelta(days=erster.weekday())).strftime("%Y-%m-%d")
        self.assertEqual(k["woche"], montag)
        self.assertEqual([x["ideal"] for x in k["vorschlaege"]], [True, False, False])
        self.assertFalse(k["sync"])
        self.assertTrue(all(sp["belegt"] == [] for sp in k["spalten"]))
        # Wochenwechsel + Cache
        k2 = self.client.get(f"/lead-management/lead/{v.id}/termin/kalender.json?woche={k['naechste']}").json()
        self.assertEqual(k2["woche"], k["naechste"])
        self.assertFalse(k2["aus_cache"])
        self.assertTrue(self.client.get(f"/lead-management/lead/{v.id}/termin/kalender.json?woche={k['naechste']}").json()["aus_cache"])
        # Weitere Kalender: HV Paolo und Karl (ohne WP-Kompetenz) ergänzen → zusätzliche
        # Spalten „außerhalb der Vorauswahl“, je Nutzer gemerkt
        r = self.client.post(f"/lead-management/lead/{v.id}/termin/kalender/auswahl",
                             json={"ids": [self.paolo.id, self.karl.id]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["ids"], [self.paolo.id, self.karl.id])
        k3 = self.client.get(f"/lead-management/lead/{v.id}/termin/kalender.json").json()
        extra = {sp["ad_id"]: sp for sp in k3["spalten"] if not sp["kandidat"]}
        self.assertEqual(set(extra), {self.paolo.id, self.karl.id})
        self.assertTrue(extra[self.paolo.id]["hv"])
        self.assertIn("Handelsvertreter", extra[self.paolo.id]["grund"])
        self.assertIn("Kompetenz", extra[self.karl.id]["grund"])
        self.assertEqual([sp["ad_id"] for sp in k3["spalten"]][:len(kandidaten)], kandidaten)
        self.assertEqual(lead_termin.weitere_kalender_holen(self.s, self.admin), [self.paolo.id, self.karl.id])
        self.assertEqual(lead_termin.weitere_kalender_holen(self.s, self.zweiter), [])
        k_andere = self.client2.get(f"/lead-management/lead/{v.id}/termin/kalender.json").json()
        self.assertNotIn(self.paolo.id, [sp["ad_id"] for sp in k_andere["spalten"]])
        seite = self.client.get(f"/lead-management/lead/{v.id}/termin").text
        self.assertIn('<optgroup label="Weitere Kalender (außerhalb der Vorauswahl)" id="lmt-weitere-optgroup" >', seite)
        self.assertIn(f'value="{self.karl.id}" data-ausserhalb="1"', seite)
        self.assertIn('id="lmt-ausserhalb"', seite)
        # Buchung außerhalb der Vorauswahl: Warnhinweis (Grund) + Bestätigung nötig, dann vorgemerkt
        slot = naechster_werktag(5) + timedelta(hours=10)
        daten = {"datum": slot.strftime("%Y-%m-%d"), "uhrzeit": "10:00", "ad_id": str(self.karl.id)}
        r = self.client.post(f"/lead-management/lead/{v.id}/termin/manuell", data=daten, follow_redirects=False)
        ziel = unquote_plus(r.headers["location"])
        self.assertIn("Konflikte", ziel)
        self.assertIn("warnung=Außerhalb der Vorauswahl: Sparte(n) WP nicht in der Kompetenz", ziel)
        r = self.client.post(f"/lead-management/lead/{v.id}/termin/manuell", data={**daten, "bestaetigt": "1"},
                             follow_redirects=False)
        self.assertTrue(r.headers["location"].startswith(f"/lead-management/lead/{v.id}?meldung="), r.headers["location"])
        self.assertEqual(self.s.query(VotTermin).filter_by(vorgang_id=v.id, ad_id=self.karl.id).count(), 1)
        # ohne Auswahl bleibt Karl nicht wählbar
        self.client.post(f"/lead-management/lead/{v.id}/termin/kalender/auswahl", json={"ids": []})
        self.assertEqual(lead_termin.weitere_kalender_holen(self.s, self.admin), [])
        r = self.client.post(f"/lead-management/lead/{v.id}/termin/manuell",
                             data={**daten, "uhrzeit": "14:00"}, follow_redirects=False)
        self.assertIn("nicht wählbar", unquote_plus(r.headers["location"]))

    def test_kalender_json_ohne_gehaltene_verbindung(self):
        """Outlook-Abruf (kalender_sync an, Graph gemockt auf Ebene des Netzaufrufs)
        läuft ohne offene Sitzung: im Moment des Graph-Aufrufs ist keine Pool-
        Verbindung entnommen – weder in den Vorschlägen noch in der Kalenderansicht."""
        v = self.lead(81)
        kern.parameter_setzen(self.s, "kalender_sync", "an")
        kern.parameter_setzen(self.s, "kalender_testpostfach", "test@example.invalid")
        self.s.commit()
        belegungen = []

        def graph_mock(methode, pfad, token, daten=None):
            belegungen.append(db.engine.pool.checkedout())
            return {"value": []}
        try:
            with mock.patch("app.kalender._token", return_value="t"), \
                    mock.patch("app.graph_versand._graph_aufruf", side_effect=graph_mock):
                k = self.client.get(f"/lead-management/lead/{v.id}/termin/kalender.json?neu=1").json()
        finally:
            kern.parameter_setzen(self.s, "kalender_sync", "aus")
            kern.parameter_setzen(self.s, "kalender_testpostfach", self.gesichert["kalender_testpostfach"])
            self.s.commit()
            lead_termin.vorschlaege_cache_leeren()
        self.assertTrue(k["sync"])
        self.assertTrue(belegungen, "Outlook-Abruf wurde nicht aufgerufen")
        self.assertEqual(max(belegungen), 0, belegungen)
        self.assertTrue(all(sp["outlook"] for sp in k["spalten"]))
        self.assertEqual(db.engine.pool.checkedout(), 0)

    def test_hv_nur_eigener_kalender_und_sperrzeit(self):
        v = self.lead(82, ad_id=self.paolo.id)
        k = self.client_paolo.get(f"/lead-management/lead/{v.id}/termin/kalender.json?neu=1").json()
        self.assertEqual([sp["ad_id"] for sp in k["spalten"]], [self.paolo.id])
        self.assertTrue(k["hv"])
        self.assertTrue(all(not sp["outlook"] for sp in k["spalten"]))
        self.assertEqual(self.client_paolo.post(f"/lead-management/lead/{v.id}/termin/kalender/auswahl",
                                                json={"ids": [self.horst.id]}).status_code, 403)
        j = self.client_paolo.get(f"/lead-management/lead/{v.id}/termin/vorschlaege.json?neu=1").json()
        self.assertEqual(j["status"], "ok", j)
        erster = datetime.strptime(j["vorschlaege"][0]["beginn"], "%Y-%m-%dT%H:%M")
        # Sperrzeit über den ersten Vorschlag → Slot fällt weg (Sperrzeit = belegter Slot)
        r = self.client_paolo.post("/lead-management/dashboard/sperrzeit",
                                   data={"datum": erster.strftime("%Y-%m-%d"), "von": erster.strftime("%H:%M"),
                                         "bis": (erster + timedelta(hours=2)).strftime("%H:%M"), "bemerkung": "privat"},
                                   follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn("Sperrzeit", unquote_plus(r.headers["location"]))
        sperr = self.s.query(VotTermin).filter_by(ad_id=self.paolo.id, typ="sperrzeit").all()
        self.assertEqual(len(sperr), 1)
        self.assertEqual((sperr[0].vorgang_id, sperr[0].grund_text, sperr[0].status), (0, "privat", "geplant"))
        j2 = self.client_paolo.get(f"/lead-management/lead/{v.id}/termin/vorschlaege.json?neu=1").json()
        self.assertNotIn(j["vorschlaege"][0]["beginn"], [x["beginn"] for x in j2["vorschlaege"]])
        k2 = self.client_paolo.get(f"/lead-management/lead/{v.id}/termin/kalender.json?neu=1").json()
        sperr_json = [t for t in k2["spalten"][0]["termine"] if t["typ"] == "sperrzeit"]
        self.assertEqual(len(sperr_json), 1)
        self.assertEqual(sperr_json[0]["text"], "Sperrzeit: privat")
        # Dashboard zeigt die Sperrzeit; Löschen nur durch den HV selbst
        hv = inhalt(self.client_paolo.get("/lead-management/dashboard").text)
        self.assertIn("privat", hv)
        self.assertEqual(self.client2.post(f"/lead-management/dashboard/sperrzeit/{sperr[0].id}/loeschen",
                                           follow_redirects=False).status_code, 303)
        self.assertEqual(self.cookie_client(self.rene).post(f"/lead-management/dashboard/sperrzeit/{sperr[0].id}/loeschen",
                                                            follow_redirects=False).status_code, 303)
        self.assertEqual(self.s.query(VotTermin).filter_by(id=sperr[0].id).count(), 0)   # Admin darf löschen
        # Nachtrag 08.10.2026 (Antwort Andreas): Admin/Innendienst dürfen Sperrzeiten eines
        # HV anlegen – benutzer_id = Ziel-HV (ohne Ziel: Meldung), erstellt_von = Innendienst
        r = self.client.post("/lead-management/dashboard/sperrzeit",
                             data={"datum": "2030-01-01", "von": "08:00", "bis": "09:00"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Handelsvertreter wählen", unquote_plus(r.headers["location"]))
        r = self.client.post("/lead-management/dashboard/sperrzeit",
                             data={"datum": "2030-01-01", "von": "08:00", "bis": "09:00", "bemerkung": "Urlaub",
                                   "benutzer_id": str(self.paolo.id),
                                   "zurueck": "/lead-management/handelsvertreter#sperrzeiten"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertTrue(r.headers["location"].startswith("/lead-management/handelsvertreter"))
        self.assertIn(f"für {self.paolo.name} eingetragen (von {self.admin.name})", unquote_plus(r.headers["location"]))
        self.s.expire_all()   # SQLite vergibt die gelöschte ID neu – Identity-Map nicht wiederverwenden
        fremd = self.s.query(VotTermin).filter_by(ad_id=self.paolo.id, typ="sperrzeit", grund_text="Urlaub").one()
        self.assertEqual((fremd.erstellt_von, fremd.vorgang_id), (self.admin.id, 0))
        # HV-Übersicht des Innendienstes: Formular + Liste je Vertreter mit „eingetragen von“
        hv_seite = self.client.get("/lead-management/handelsvertreter").text
        self.assertIn('id="lm-sperrzeit-form-hv"', hv_seite)
        self.assertIn(f'<option value="{self.paolo.id}">{self.paolo.name}</option>', hv_seite)
        self.assertIn(f'data-sperrzeit="{fremd.id}"', hv_seite)
        self.assertIn(f"eingetragen von {self.admin.name}", hv_seite)
        self.assertIn("Urlaub", hv_seite)
        # … und im Dashboard des HV
        hv = inhalt(self.client_paolo.get("/lead-management/dashboard").text)
        self.assertIn(f"eingetragen von {self.admin.name}", hv)
        # Ziel muss ein Handelsvertreter sein; angestellter AD darf gar nicht; ein HV legt
        # nur eigene an (benutzer_id wird ignoriert); die HV-Übersicht zeigt dem HV kein Formular
        r = self.client.post("/lead-management/dashboard/sperrzeit",
                             data={"datum": "2030-01-02", "von": "08:00", "bis": "09:00", "benutzer_id": str(self.horst.id)},
                             follow_redirects=False)
        self.assertIn("kein Handelsvertreter", unquote_plus(r.headers["location"]))
        self.assertEqual(self.cookie_client(self.horst).post("/lead-management/dashboard/sperrzeit",
                                                             data={"datum": "2030-01-02", "von": "08:00", "bis": "09:00",
                                                                   "benutzer_id": str(self.paolo.id)},
                                                             follow_redirects=False).status_code, 404)
        self.client_paolo.post("/lead-management/dashboard/sperrzeit",
                               data={"datum": "2030-01-03", "von": "08:00", "bis": "09:00", "bemerkung": "eigene",
                                     "benutzer_id": str(self.rene.id)}, follow_redirects=False)
        self.s.expire_all()
        eigene = self.s.query(VotTermin).filter_by(typ="sperrzeit", grund_text="eigene").one()
        self.assertEqual((eigene.ad_id, eigene.erstellt_von), (self.paolo.id, self.paolo.id))
        self.assertNotIn('id="lm-sperrzeit-form-hv"', self.client_paolo.get("/lead-management/handelsvertreter").text)
        # Löschen aus der HV-Übersicht (gleiche Route, zurueck = Übersicht)
        r = self.client.post(f"/lead-management/dashboard/sperrzeit/{fremd.id}/loeschen",
                             data={"zurueck": "/lead-management/handelsvertreter#sperrzeiten"}, follow_redirects=False)
        self.assertTrue(r.headers["location"].startswith("/lead-management/handelsvertreter"))
        self.assertEqual(self.s.query(VotTermin).filter_by(id=fremd.id).count(), 0)
        # Terminkalender des Innendienstes (Sperrzeit ohne Vorgang) rendert
        self.client_paolo.post("/lead-management/dashboard/sperrzeit",
                               data={"datum": erster.strftime("%Y-%m-%d"), "von": "13:00", "bis": "14:00"},
                               follow_redirects=False)
        self.assertEqual(self.client.get(f"/lead-management/kalender?ad_id={self.paolo.id}").status_code, 200)

    def test_sperrzeit_exakt_ohne_puffer(self):
        """Nachtrag 08.10.2026 (Antwort Andreas): eine Sperrzeit zählt exakt von–bis –
        ein Vorschlag direkt an der Sperrzeit-Grenze bleibt erlaubt, eine Überlappung
        nicht; die manuelle Konfliktprüfung meldet an der Grenze keinen Puffer."""
        v = self.lead(83, ad_id=self.paolo.id)
        j = self.client_paolo.get(f"/lead-management/lead/{v.id}/termin/vorschlaege.json?neu=1").json()
        self.assertEqual(j["status"], "ok", j)
        erster = j["vorschlaege"][0]
        beginn = datetime.strptime(erster["beginn"], "%Y-%m-%dT%H:%M")
        ende = datetime.strptime(erster["ende"], "%Y-%m-%dT%H:%M")
        # Sperrzeit beginnt genau am Ende von Vorschlag 1 (vom Innendienst eingetragen)
        r = self.client.post("/lead-management/dashboard/sperrzeit",
                             data={"datum": ende.strftime("%Y-%m-%d"), "von": ende.strftime("%H:%M"),
                                   "bis": (ende + timedelta(hours=1)).strftime("%H:%M"),
                                   "bemerkung": "Grenze", "benutzer_id": str(self.paolo.id)},
                             follow_redirects=False)
        self.assertIn("eingetragen", unquote_plus(r.headers["location"]))
        j2 = self.client_paolo.get(f"/lead-management/lead/{v.id}/termin/vorschlaege.json?neu=1").json()
        self.assertIn(erster["beginn"], [x["beginn"] for x in j2["vorschlaege"]], j2)
        k = lead_termin.konflikte(self.s, self.paolo.id, beginn, ende)
        self.assertEqual((k["voll"], k["puffer"]), ([], []))
        self.assertFalse(k["sperren"])
        # dieselbe Sperrzeit 15 Minuten früher → Überschneidung: Vorschlag entfällt, Buchung gesperrt
        self.s.expire_all()
        sperr = self.s.query(VotTermin).filter_by(ad_id=self.paolo.id, typ="sperrzeit", grund_text="Grenze").one()
        sperr.beginn = ende - timedelta(minutes=15)
        self.s.commit()
        lead_termin.vorschlaege_cache_leeren()
        j3 = self.client_paolo.get(f"/lead-management/lead/{v.id}/termin/vorschlaege.json?neu=1").json()
        self.assertNotIn(erster["beginn"], [x["beginn"] for x in j3["vorschlaege"]])
        k = lead_termin.konflikte(self.s, self.paolo.id, beginn, ende)
        self.assertEqual([t.id for t in k["voll"]], [sperr.id])
        self.assertTrue(k["sperren"])
        self.assertTrue(any("Sperrzeit" in t for t in k["texte"]))
        # Vergleich: ein Kundentermin direkt an der Grenze verletzt weiter den Mindestpuffer
        self.s.delete(sperr)
        self.s.add(VotTermin(vorgang_id=v.id, ad_id=self.paolo.id, beginn=ende, ende=ende + timedelta(minutes=90),
                             status="geplant", typ="vot", demo=True))
        self.s.commit()
        k = lead_termin.konflikte(self.s, self.paolo.id, beginn, ende)
        self.assertEqual(k["voll"], [])
        self.assertEqual(len(k["puffer"]), 1)
        lead_termin.vorschlaege_cache_leeren()


# --- Vertrag L2: Warteschlangen-Seite --------------------------------------------------------

class W_Warteschlange(Basis):
    def test_seite_mit_statusfilter_und_erneut_senden(self):
        v = self.lead(90)
        self.s.add(KommunikationLog(vorgang_id=v.id, vorlage_key="eingangsbestaetigung", an="v4l1-90@test.local",
                                    betreff="Test", body_html="<p>x</p>", status="fehler",
                                    fehler_text="Senderecht fehlt (Test)", modus="protokoll"))
        self.s.commit()
        eintrag = self.s.query(KommunikationLog).filter_by(vorgang_id=v.id, status="fehler").one()
        r = self.client.get("/lead-management/kommunikation?status=fehler")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'data-eintrag="{eintrag.id}"', r.text)
        self.assertIn(f'action="/lead-management/mail/{eintrag.id}/erneut"', r.text)
        self.assertIn("lm-mailstatus-fehler", r.text)
        self.assertIn("Senderecht fehlt (Test)", r.text)
        self.assertNotIn(f'data-eintrag="{eintrag.id}"', self.client.get("/lead-management/kommunikation?status=gesendet").text)
        self.assertIn(f'data-eintrag="{eintrag.id}"', self.client.get("/lead-management/kommunikation").text)
        # Dashboard-Kachel „Mails mit Fehler“ nur bei > 0
        self.assertIn("Mails mit Fehler", inhalt(self.client.get("/lead-management/dashboard").text))
        self.assertGreaterEqual(lead_dashboard.mails_mit_fehler(self.s), 1)
        # Nachtrag 08.10.2026: HV-Sicht → 303 auf die HV-Ansicht, sobald das V1-Demo-Gate
        # lead_v2.hv_umleitung aufruft (Vorschlag LC 4.1); bis dahin 404 (siehe HV_GESPERRT_V1)
        r = self.client_paolo.get("/lead-management/kommunikation", follow_redirects=False)
        if "hv_umleitung" in (PROJEKT / "app" / "routers" / "leadmanagement.py").read_text(encoding="utf-8"):
            self.assertEqual(r.status_code, 303)
            self.assertTrue(r.headers["location"].startswith("/lead-management/handelsvertreter?meldung="))
        else:
            self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
