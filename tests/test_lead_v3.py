# Integrationstests PLAN_LEAD_V3 Phase 121 (CLAUDE v25, Agent E): die Plan-Fälle
# (a) zwei Benutzer / Spaltenkonfiguration wirkt nur beim ersten,
# (b) Standardspalten ohne Anrede/Vorname/Nachname mit „Kundenname“,
# (c) Anrufliste als EINE Liste (Sortierung SLA → fällig → zurückgestellt →
#     Eingang) mit Filter „Vertriebskanal“,
# (d) Label „Kontaktiert“ für beide Kontakt-Phasen, Kanban eine Spalte,
# (e) Autospeichern (Wert + Aktivität, ungültige PLZ → Fehler und alter Wert),
# (f) Kartei ohne Score/Quelle/Einwilligung/Qualifizierung,
# (g) Terminvorschläge im Block Termine, Hinweise Adresse/HV,
# (h) Terminassistent ohne Handelsvertreter für den Innendienst, mit für den HV,
# (i) „Nicht erreicht“ ohne wiedervorlage_am, Versuch +1, Mail am 2., Sperre,
# (j) score_aktiv = aus: kein Score im Eingang, Pipeline ohne Score,
# (k) To-Dos-Seite,
# plus die fünf Kontrollwerte des Plans, alle Lead-Routen inkl. „Mehr …“ als
# Admin (200/303) und konsistente Nav-Keys. Die Detailtests der Phasen liegen in
# tests/test_lead_v3_boards/anruf/kartei/phase120.py – hier wird das Zusammenspiel
# geprüft. Laufen im Demo-Modus gegen die Entwicklungs-DB; Testleads tragen den
# Nachnamen „LeadV3E-Test“, Testbenutzer das Präfix „LeadV3E “ – alles wird
# aufgeräumt, Parameter und die Spaltenkonfiguration von Benutzer 1 werden
# gesichert und wiederhergestellt.
import json
import pathlib
import re
import time
import unittest
import warnings
from datetime import datetime, timedelta
from unittest import mock
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app import auth, lead_anrufliste, lead_boards, lead_info, lead_kartei, lead_termin, lead_todos, lead_v2
from app import leadmanagement as kern
from app import leadmanagement_logik
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (ANRUF_ERGEBNIS_NAMEN, AdProfil, Angebot, AngebotsNotiz,
                        Benachrichtigung, Benutzer, BenutzerEinstellung, InfoVeranstaltung,
                        KommunikationLog, Kunde, LeadAktivitaet, LeadQualifizierung,
                        LeadQuelle, Todo, Vorgang, VorgangsNotiz, VotTermin)

NACHNAME = "LeadV3E-Test"
PRAEFIX = "LeadV3E "
KEY = lead_boards.EINSTELLUNG_KEY
BASIS = (54.3, 7.6)                      # Bezugspunkt abseits aller echten Leads (Nordsee)
KASKADEN_MAILS = ("nicht_erreicht", "disqualifiziert", "nurture")
SCORE_MUSTER = re.compile(r"\bScore\b|\bKlasse [ABC]\b|score_klasse|Score-Klasse")
PROJEKT = pathlib.Path(__file__).resolve().parents[1]

# Vertrag v25 (Briefing): Icon-Leiste + „Mehr …“ – Key, Pfad
NAV_HAUPT = [("dashboard", "/lead-management/dashboard"),
             ("hauptboard", "/lead-management/hauptboard"),
             ("terminiert", "/lead-management/terminiert"),
             ("kontaktiert", "/lead-management/kontaktiert"),
             ("karte", "/lead-management/karte"),
             ("info", "/lead-management/info-veranstaltung"),
             ("todos", "/lead-management/todos"),
             ("handelsvertreter", "/lead-management/handelsvertreter")]
NAV_MEHR = [("anrufliste", "/lead-management/anrufliste"),
            ("board", "/lead-management/board"),
            ("kalender", "/lead-management/kalender"),
            ("vorlagen", "/lead-management/vorlagen"),
            ("uebersicht", "/lead-management/uebersicht"),
            ("statistik", "/lead-management/statistik"),
            ("kanal_report", "/lead-management/statistik/kanal"),
            ("posteingang", "/lead-management/posteingang"),
            ("import", "/lead-management/import"),
            ("neu", "/lead-management/neu"),
            ("lead-einstellungen", "/parametrierung/lead-einstellungen")]
NAV_KEYS = {k for k, _ in NAV_HAUPT} | {k for k, _ in NAV_MEHR} | {"tabelle", "info-veranstaltung"}
# weitere GET-Einstiege des Moduls ohne Pfadparameter (V1 + V2)
WEITERE_PFADE = ["/lead-management", "/lead-management/boards/haupt",
                 "/lead-management/anruf/meine", "/lead-management/anruf/suche?q=0203",
                 "/lead-management/info-veranstaltung/termine",
                 "/lead-management/handelsvertreter/dashboard",
                 "/lead-management/todos/neu",
                 "/lead-management/karte/daten", "/lead-management/adressen",
                 "/lead-management/cockpit", "/lead-management/boards/spalten?board=hauptboard",
                 "/lead-management/boards/spalten?board=terminiert"]


def mit_wiederholung(funktion, versuche=12, pause=0.5):
    """SQLite kennt nur einen Schreiber – bei parallelen Läufen kurz warten."""
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
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.query(LeadQualifizierung).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete()
            s.query(Todo).filter_by(vorgang_id=v.id).delete()
            for a in s.query(Angebot).filter_by(vorgang_id=v.id):
                s.query(AngebotsNotiz).filter_by(angebot_id=a.id).delete()
                s.delete(a)
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            s.delete(v)
        s.delete(k)
    s.query(Todo).filter(Todo.titel.like(f"{PRAEFIX}%")).delete(synchronize_session=False)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(BenutzerEinstellung).filter_by(benutzer_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.query(Todo).filter((Todo.an_benutzer_id == b.id) | (Todo.von_benutzer_id == b.id)).delete(
            synchronize_session=False)
        s.delete(b)
    s.commit()


def inhalt(seite: str) -> str:
    """Nur der Seiteninhalt (ohne Kopfzeile/Glocke/Navigation)."""
    return seite.split("<main", 1)[-1]


def nav_html(seite: str) -> str:
    return seite.split('<nav class="lm-leiste"', 1)[1].split("</nav>", 1)[0]


def aktive_nav_keys(seite: str) -> list[str]:
    """data-key aller mit aria-current="page" markierten Nav-Elemente."""
    return re.findall(r'aria-current="page"\s*data-key="([^"]+)"', nav_html(seite)) + \
        re.findall(r'data-key="([^"]+)"\s*aria-current="page"', nav_html(seite))


def thead_html(seite: str) -> str:
    return seite.split("<thead>", 1)[1].split("</thead>", 1)[0]


def zeile_html(seite: str, vorgang_id: int) -> str:
    teile = seite.split(f'data-vorgang="{vorgang_id}"', 1)
    return teile[1].split("</tr>", 1)[0] if len(teile) > 1 else ""


class Basis(unittest.TestCase):
    PARAMETER = ("lead_freigabe_modus", "score_aktiv", "ohne_schritt_tage",
                 "kanal_ad_regel", "routing_anbieter", "kalender_sync", "mail_modus")

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        mit_wiederholung(lambda: aufraeumen(cls.s))
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        cls.gesichert = {n: kern.parameter_holen(cls.s, n, "") for n in cls.PARAMETER}
        cls.alt_spalten = lead_v2.einstellung_holen(cls.s, 1, KEY, None)

        def _vorbereiten():
            cls.s.rollback()
            kern.parameter_setzen(cls.s, "lead_freigabe_modus", "admin")
            kern.parameter_setzen(cls.s, "score_aktiv", "aus")
            kern.parameter_setzen(cls.s, "ohne_schritt_tage", "2")
            kern.parameter_setzen(cls.s, "kanal_ad_regel", "")
            kern.parameter_setzen(cls.s, "routing_anbieter", "luftlinie")
            kern.parameter_setzen(cls.s, "kalender_sync", "aus")
            kern.parameter_setzen(cls.s, "mail_modus", "protokoll")
            cls.s.execute(text("DELETE FROM benutzer_einstellungen WHERE benutzer_id = 1 AND key = :k"),
                          {"k": KEY})
            # zweiter Admin (Benutzer B), Innendienst, angestellter AD, Handelsvertreter
            cls.zweiter = cls.benutzer("Admin B", rolle="admin")
            cls.innen = cls.benutzer("Innen", rolle="innendienst")
            cls.horst = cls.ad("Horst", ["WP", "PV", "KL", "WB"], kombi=True, mfh=True)
            cls.hv = cls.ad("Hv", ["WP", "PV", "KL", "WB"], kombi=True, mfh=True,
                            terminiert_selbst=True)
            cls.s.commit()
        mit_wiederholung(_vorbereiten)
        cls.admin = cls.s.get(Benutzer, 1)
        cls.client2 = TestClient(app)
        cls.client2.post("/login", data={"benutzer_id": str(cls.zweiter.id), "pin": "4321"})
        lead_termin.vorschlaege_cache_leeren()

    @classmethod
    def tearDownClass(cls):
        def _aufraeumen():
            aufraeumen(cls.s)
            for n, w in cls.gesichert.items():
                kern.parameter_setzen(cls.s, n, w)
            cls.s.execute(text("DELETE FROM benutzer_einstellungen WHERE benutzer_id = 1 AND key = :k"),
                          {"k": KEY})
            if cls.alt_spalten is not None:
                lead_v2.einstellung_setzen(cls.s, 1, KEY, cls.alt_spalten)
            cls.s.commit()
        try:
            mit_wiederholung(_aufraeumen)
        finally:
            lead_termin.vorschlaege_cache_leeren()
            cls.s.close()

    # --- Stammdaten-Helfer -----------------------------------------------------------

    @classmethod
    def benutzer(cls, name, rolle="aussendienst", **extra):
        b = Benutzer(name=f"{PRAEFIX}{name}", rolle=rolle, aktiv=True,
                     email=f"{name.lower().replace(' ', '')}@lv3e.local", telefon="0203 1",
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

    def lead(self, nr, phase="neu", anrede="", strasse="Teststraße 1", kanal=None,
             versuche=0, eingang=None, email=True, geo=True, **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"anrede": anrede, "vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}",
                 "plz": "47139", "ort": "Duisburg", "telefon": f"0203 77{nr:04d}",
                 "sparten": ["WP"], "strasse": strasse}
        if email:
            daten["email"] = f"v3e{nr}@test.local"
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        kunde = self.s.get(Kunde, vorgang.kunde_id)
        kunde.objektart = "EFH"
        if kanal is not None:
            kunde.vertriebskanal = kanal
        vorgang.demo = True
        vorgang.lead_phase = phase
        vorgang.naechste_aktion_am = None
        if geo:
            vorgang.lat, vorgang.lon, vorgang.geocode_status = BASIS[0], BASIS[1], "ok"
        if eingang is not None:
            vorgang.eingang_am = eingang
        vorgang.versuch_nr = versuche
        for _ in range(versuche):
            kern.aktivitaet(self.s, vorgang.id, "anruf", "Anruf: Nicht erreicht",
                            benutzer=self.admin, ergebnis="nicht_erreicht")
        if versuche and phase == "neu":
            vorgang.lead_phase = "in_kontaktierung"
        if versuche:
            vorgang.erstkontakt_am = min((vorgang.eingang_am or datetime.now())
                                         + timedelta(minutes=10), datetime.now())
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def kunde(self, vorgang):
        self.s.expire_all()
        return self.s.get(Kunde, vorgang.kunde_id)

    def anrufe(self, vorgang_id):
        self.s.expire_all()
        return (self.s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang_id, typ="anruf")
                .order_by(LeadAktivitaet.id).all())

    def aktivitaeten(self, vorgang, typ):
        self.s.expire_all()
        return (self.s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang.id, typ=typ)
                .order_by(LeadAktivitaet.id).all())

    def mails(self, vorgang_id):
        self.s.expire_all()
        return [(m.vorlage_key, m.status) for m in
                self.s.query(KommunikationLog).filter_by(vorgang_id=vorgang_id)
                .order_by(KommunikationLog.id) if m.vorlage_key in KASKADEN_MAILS]

    def meldung(self, antwort) -> str:
        ziel = antwort.headers.get("location", "")
        return unquote_plus(ziel.split("meldung=", 1)[1]) if "meldung=" in ziel else ""

    def json_post(self, url, daten, client=None):
        return (client or self.client).post(url, json=daten, headers={"Accept": "application/json"})

    def spalten_json(self, client=None, board="hauptboard"):
        r = (client or self.client).get(f"/lead-management/boards/spalten?board={board}")
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def reset(self, client=None, board="hauptboard"):
        r = self.json_post("/lead-management/boards/spalten", {"board": board, "zuruecksetzen": True}, client)
        self.assertEqual(r.status_code, 200, r.text)

    def feld(self, vorgang, feld, wert, client=None):
        return (client or self.client).post(f"/lead-management/lead/{vorgang.id}/feld",
                                            json={"feld": feld, "wert": wert})

    def kartei(self, vorgang, client=None, **params):
        url = f"/lead-management/lead/{vorgang.id}"
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        return (client or self.client).get(url)

    def kartei_eigen(self, seite: str) -> str:
        """Eigenes Markup der Kartei (Kopf bis vor die Dialoge/Makros)."""
        start = seite.index('<header class="karte lk-kopf')
        return seite[start:seite.index("<dialog", start)]

    def vorschlaege_block(self, seite: str) -> str:
        return seite.split('id="lk-vorschlaege"', 1)[1].split("</ol>", 1)[0]

    def vorschlaege_json(self, vorgang, client=None, neu=False):
        r = (client or self.client).get(f"/lead-management/lead/{vorgang.id}/termin/vorschlaege.json"
                                        + ("?neu=1" if neu else ""))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def anrufdaten(self, **params):
        f = lead_anrufliste.filter_aus_query({"meine": "0", **params})
        return lead_anrufliste.daten(self.s, None, f)


# --- 0. App-Start, alle Lead-Routen, Nav-Keys ---------------------------------------------

class Routen(Basis):
    def test_alle_lead_routen_als_admin_200_oder_303(self):
        v = self.lead(1)
        pfade = [p for _, p in NAV_HAUPT] + [p for _, p in NAV_MEHR] + WEITERE_PFADE + [
            f"/lead-management/lead/{v.id}", f"/lead-management/lead/{v.id}?tab=termin",
            f"/lead-management/lead/{v.id}?tab=anrufe", f"/lead-management/lead/{v.id}?tab=timeline",
            f"/lead-management/lead/{v.id}/termin", f"/lead-management/lead/{v.id}/termin/vorab",
            f"/lead-management/lead/{v.id}/termin/vorschlaege.json",
            f"/lead-management/lead/{v.id}/kommunikation",
            f"/lead-management/lead/{v.id}/qualifizierung/WP",
            f"/lead-management/anruf/{v.id}/vorschlag",
            f"/lead-management/todos?vorgang_id={v.id}",
            f"/vorgaenge/{v.id}"]
        for pfad in pfade:
            r = self.client.get(pfad, follow_redirects=False)
            self.assertIn(r.status_code, (200, 303), (pfad, r.status_code))
            if r.status_code == 303:
                ziel = r.headers["location"]
                r2 = self.client.get(ziel, follow_redirects=False)
                self.assertEqual(r2.status_code, 200, (pfad, ziel, r2.status_code))
        # Plan-Pfad des Hauptboards leitet (mit Query) auf /hauptboard
        r = self.client.get("/lead-management/boards/haupt?q=x", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/lead-management/hauptboard?q=x"))
        # Qualifizierungsroute bleibt erreichbar, zeigt bei score_aktiv aus den Hinweis
        seite = self.client.get(f"/lead-management/lead/{v.id}/qualifizierung/WP").text
        self.assertIn("Qualifizierung ist abgeschaltet", seite)
        # „Meine Termine“ ist die Seite des Außendienstes (F6): im Demo-Modus 404 (Plan 81),
        # bei Freigabe „alle“ für den angestellten AD erreichbar
        ad_client = self.cookie_client(self.horst)
        self.assertEqual(ad_client.get("/lead-management/meine-termine", follow_redirects=False).status_code, 404)
        with mock.patch.object(kern, "freigabe_modus", return_value="alle"):
            r = ad_client.get("/lead-management/meine-termine", follow_redirects=False)
        self.assertEqual(r.status_code, 200, r.status_code)

    def test_nav_keys_aller_seiten_konsistent(self):
        v = self.lead(2)
        # Kanban (GET /board) markiert das gezeigte Board (lm_nav(board)), nicht den
        # „Mehr …“-Eintrag – der Umschalter Tabelle | Anrufliste | Kanban gehört zum Board
        erwartet = [(p, k) for k, p in NAV_HAUPT] + [(p, k) for k, p in NAV_MEHR if k != "board"] + [
            ("/lead-management/board", "hauptboard"),
            (f"/lead-management/lead/{v.id}", "hauptboard"),
            (f"/lead-management/lead/{v.id}/qualifizierung/WP", "hauptboard"),
            (f"/lead-management/lead/{v.id}/termin", "kalender"),
            ("/lead-management/anruf/meine", "anrufliste"),
            ("/lead-management/anruf/suche?q=0203", "anrufliste"),
            ("/lead-management/info-veranstaltung/termine", "info"),
            ("/lead-management/cockpit", "uebersicht"),
            ("/lead-management/board?board=terminiert", "terminiert"),
        ]
        for pfad, key in erwartet:
            r = self.client.get(pfad, follow_redirects=True)
            self.assertEqual(r.status_code, 200, pfad)
            if '<nav class="lm-leiste"' not in r.text:
                continue                                   # z. B. Parametrierung ohne Modul-Leiste
            aktiv = aktive_nav_keys(r.text)
            self.assertEqual(aktiv, [key], (pfad, aktiv))
            # genau EIN aktiver Eintrag in der Leiste (Hauptleiste oder „Mehr …“-Menü)
            leiste = nav_html(r.text)
            self.assertEqual(leiste.count('aria-current="page"'), 1, pfad)
        # Reihenfolge der Icon-Leiste wie im Plan
        leiste = nav_html(self.client.get("/lead-management/hauptboard").text)
        keys = re.findall(r'class="lm-leiste-eintrag[^"]*"[^>]*data-key="([^"]+)"', leiste)
        self.assertEqual(keys[:8], [k for k, _ in NAV_HAUPT])
        self.assertEqual(keys[8], "mehr")
        namen = re.findall(r'class="lm-leiste-eintrag[^"]*" title="[^"]+"\s+aria-label="([^"]+)"', leiste)[:8]
        self.assertEqual(namen, ["Mein Dashboard", "Hauptboard", "Deals", "Kontaktiert", "Karte",
                                 "Infoabend", "To-Dos", "Handelsvertreter"])
        # alle Aufrufer von lm_nav in den Lead-Templates nutzen Vertragskeys
        ordner = PROJEKT / "app" / "templates" / "leadmanagement"
        for datei in sorted(ordner.glob("*.html")):
            for key in re.findall(r"lm_nav\('([^']+)'\)", datei.read_text(encoding="utf-8")):
                self.assertIn(key, NAV_KEYS, (datei.name, key))


# --- (a) zwei Benutzer, Spaltenkonfiguration nur beim ersten (Kontrollwert 4) ------------

class A_ZweiBenutzerSpalten(Basis):
    def setUp(self):
        self.reset(self.client)
        self.reset(self.client2)

    def tearDown(self):
        self.reset(self.client)
        self.reset(self.client2)

    def test_a_umbenennen_verschieben_ausblenden_wirkt_nur_bei_a(self):
        self.lead(10)
        standard = [x["key"] for x in self.spalten_json(self.client)["spalten"]]
        # Benutzer A: „Telefon“ an Position 2, „Ort“ ausblenden, „Notiz“ → „Bemerkung“
        a = self.spalten_json(self.client)["spalten"]
        neu = ([x for x in a if x["key"] == "lead"] + [x for x in a if x["key"] == "telefon"]
               + [x for x in a if x["key"] not in ("lead", "telefon")])
        liste = [{"key": x["key"], "sichtbar": x["sichtbar"] and x["key"] != "ort", "name": x["name"]}
                 for x in neu]
        r = self.json_post("/lead-management/boards/spalten", {"board": "hauptboard", "spalten": liste})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["meldung"], "Spalten gespeichert.")
        r = self.json_post("/lead-management/boards/spalten",
                           {"board": "hauptboard", "umbenennen": {"key": "notiz", "name": "Bemerkung"}})
        self.assertEqual(r.json()["meldung"], "Spalte umbenannt.")
        # A sieht seine Konfiguration …
        sp_a = self.spalten_json(self.client)["spalten"]
        self.assertEqual([x["key"] for x in sp_a][:2], ["lead", "telefon"])
        self.assertFalse(next(x for x in sp_a if x["key"] == "ort")["sichtbar"])
        self.assertEqual(next(x for x in sp_a if x["key"] == "notiz")["titel"], "Bemerkung")
        kopf_a = thead_html(self.client.get("/lead-management/hauptboard").text)
        self.assertLess(kopf_a.index('<th class="sp-telefon"'), kopf_a.index('<th class="sp-status"'))
        self.assertNotIn('<th class="sp-ort"', kopf_a)
        self.assertIn(">Bemerkung</span>", kopf_a)
        self.assertNotIn(">Notiz</span>", kopf_a)
        # … Benutzer B den unveränderten Standard
        sp_b = self.spalten_json(self.client2)["spalten"]
        self.assertEqual([x["key"] for x in sp_b], standard)
        self.assertTrue(next(x for x in sp_b if x["key"] == "ort")["sichtbar"])
        self.assertEqual(next(x for x in sp_b if x["key"] == "notiz")["titel"], "Notiz")
        self.assertTrue(all(x["name"] == "" for x in sp_b))
        kopf_b = thead_html(self.client2.get("/lead-management/hauptboard").text)
        self.assertLess(kopf_b.index('<th class="sp-status"'), kopf_b.index('<th class="sp-telefon"'))
        self.assertIn('<th class="sp-ort"', kopf_b)
        self.assertIn(">Notiz</span>", kopf_b)
        self.assertNotIn("Bemerkung", kopf_b)
        # gespeichert nur unter Benutzer 1 (benutzer_einstellungen, Key boards_spalten)
        roh = lead_v2.einstellung_holen(self.s, 1, KEY)["hauptboard"]
        self.assertEqual(roh["spalten"][1]["key"], "telefon")
        self.assertEqual(next(x for x in roh["spalten"] if x["key"] == "notiz")["name"], "Bemerkung")
        roh_b = (lead_v2.einstellung_holen(self.s, self.zweiter.id, KEY, None) or {}).get("hauptboard") or {}
        self.assertFalse(roh_b.get("spalten"))                       # B: kein eigener Eintrag (Standard)
        self.assertFalse(roh_b.get("sort"))
        # Deals-Board von A bleibt eigenständig; Zurücksetzen stellt A den Standard wieder her
        self.assertEqual(next(x for x in lead_boards.spalten_fuer(self.s, self.admin, "terminiert")
                              if x["key"] == "notiz")["titel"], "Notiz")
        self.reset(self.client)
        self.assertEqual([x["key"] for x in self.spalten_json(self.client)["spalten"]], standard)


# --- (b) Standardspalten ohne Anrede/Vorname/Nachname -------------------------------------

class B_Standardspalten(Basis):
    def test_b_standard_ohne_namensspalten_kundenname_voll(self):
        self.reset(self.client2)
        for board in ("hauptboard", "terminiert"):
            sp = lead_boards.spalten_fuer(self.s, self.zweiter, board)
            self.assertEqual(sp[0]["key"], "lead")
            self.assertEqual(sp[0]["titel"], "Kundenname")
            self.assertTrue(sp[0]["sichtbar"])
            for key in ("anrede", "vorname", "nachname"):
                eintrag = next(x for x in sp if x["key"] == key)
                self.assertFalse(eintrag["sichtbar"], (board, key))       # ausgeblendet, einblendbar
            self.assertNotIn("score", [x["key"] for x in sp])
        herr = self.lead(20, anrede="Herr")
        ohne = self.lead(21)
        self.assertEqual(lead_boards.kundenname(self.kunde(herr)), f"Herr V20 {NACHNAME}-20")
        self.assertEqual(lead_boards.kundenname(self.kunde(ohne)), f"V21 {NACHNAME}-21")
        seite = self.client2.get(f"/lead-management/hauptboard?q={NACHNAME}").text
        kopf = thead_html(seite)
        self.assertIn('<th class="sp-lead"', kopf)
        for key in ("anrede", "vorname", "nachname", "score"):
            self.assertNotIn(f'<th class="sp-{key}"', kopf, key)
        self.assertIn(f"Herr V20 {NACHNAME}-20", seite)
        self.assertIn(f">V21 {NACHNAME}-21<", seite)
        # Spaltenwähler bietet die drei Spalten an (Häkchen leer)
        for key in ("anrede", "vorname", "nachname"):
            self.assertRegex(seite, rf'<input type="checkbox" data-key="{key}"\s*>')
        # in der Kundenkartei bleiben die drei Felder sichtbar ([ANNAHME] des Plans)
        kartei = self.kartei(herr).text
        for name in ("anrede", "vorname", "nachname"):
            self.assertIn(f'data-feld="{name}"', kartei)


# --- (c) Anrufliste: eine Liste, Sortierung, Filter Vertriebskanal -------------------------

class C_Anrufliste(Basis):
    def test_c_eine_liste_sortierung_und_kanalfilter(self):
        jetzt = datetime.now()
        rot = self.lead(30, eingang=jetzt - timedelta(days=3))                     # SLA rot
        wv = self.lead(31, versuche=1, eingang=jetzt - timedelta(days=1),
                       naechste_aktion_am=jetzt - timedelta(hours=2))               # WV fällig
        zur = self.lead(32, versuche=1, eingang=jetzt - timedelta(days=5), phase="zurueckgestellt",
                        zurueckgestellt_bis=jetzt - timedelta(hours=1), zurueckgestellt_grund="Urlaub")
        rest_alt = self.lead(33, versuche=1, eingang=jetzt - timedelta(days=2))    # erfüllt, Rest
        rest_neu = self.lead(34, eingang=jetzt - timedelta(minutes=1))             # SLA grün, Rest
        d = self.anrufdaten(q=NACHNAME)
        self.assertNotIn("gruppen", d)                                              # keine Gruppen mehr
        ids = [z["vorgang"].id for z in d["zeilen"]]
        for v in (rot, wv, zur, rest_alt, rest_neu):
            self.assertIn(v.id, ids)
        rang = {z["vorgang"].id: z["rang"] for z in d["zeilen"]}
        self.assertEqual([rang[v.id] for v in (rot, wv, zur, rest_alt, rest_neu)], [0, 2, 3, 4, 4])
        pos = {v.id: ids.index(v.id) for v in (rot, wv, zur, rest_alt, rest_neu)}
        self.assertLess(pos[rot.id], pos[wv.id])
        self.assertLess(pos[wv.id], pos[zur.id])
        self.assertLess(pos[zur.id], pos[rest_alt.id])
        self.assertLess(pos[rest_alt.id], pos[rest_neu.id])                        # Eingang: älteste zuerst
        self.assertTrue(all(len(z["_sortierung"]) <= 3 for z in d["zeilen"]))       # keine Score-Komponente
        # Seite: keine Gruppenköpfe, Sortierhinweis, Reihenfolge wie in den Daten
        seite = inhalt(self.client.get(f"/lead-management/anrufliste?meine=0&q={NACHNAME}").text)
        for text_ in ("Jetzt dran", "Weiter versuchen", "Neu heute", "Wiedervorlagen fällig",
                      "Sonstige offene", "lm-gruppe-kopf"):
            self.assertNotIn(text_, seite, text_)
        self.assertIn('class="lm-sortierung"', seite)
        html_pos = {v.id: seite.index(f'data-vorgang="{v.id}"') for v in (rot, wv, zur, rest_alt, rest_neu)}
        self.assertEqual(sorted(html_pos, key=html_pos.get),
                         [rot.id, wv.id, zur.id, rest_alt.id, rest_neu.id])
        # Filter Vertriebskanal (Mehrfach) statt Quelle/Einzelquelle, Kanal-Badge in der Zeile
        enni = self.lead(35, kanal="Enni")
        swd = self.lead(36, kanal="SWD")
        nur_enni = {z["vorgang"].id for z in self.anrufdaten(q=NACHNAME, kanal="Enni")["zeilen"]}
        self.assertIn(enni.id, nur_enni)
        self.assertNotIn(swd.id, nur_enni)
        self.assertNotIn(rot.id, nur_enni)
        beide = {z["vorgang"].id for z in self.anrufdaten(q=NACHNAME, kanal=["Enni", "SWD"])["zeilen"]}
        self.assertTrue({enni.id, swd.id} <= beide)
        self.assertNotIn(rot.id, beide)
        seite = inhalt(self.client.get(f"/lead-management/anrufliste?meine=0&q={NACHNAME}&kanal=Enni&kanal=SWD").text)
        self.assertIn(f'data-vorgang="{enni.id}"', seite)
        self.assertIn(f'data-vorgang="{swd.id}"', seite)
        self.assertNotIn(f'data-vorgang="{rot.id}"', seite)
        self.assertIn('name="kanal" value="Enni" checked', seite)
        self.assertIn('class="lm-kanal mit-farbe" style="--f:', seite)
        for text_ in ('name="quelle_typ"', 'name="quelle_id"', "Einzelquelle", "quelle_badge"):
            self.assertNotIn(text_, seite, text_)
        # Alt-Links der Übersicht (quelle_id/kampagne_id) bleiben fehlerfrei
        self.assertEqual(self.client.get("/lead-management/anrufliste?quelle_id=1&kampagne_id=0").status_code, 200)


# --- (d) Label „Kontaktiert“, Kanban eine Spalte (Kontrollwert 5) -------------------------

class D_LabelKontaktiert(Basis):
    def test_d_label_beider_phasen_kanban_und_trichter(self):
        logik = leadmanagement_logik.hole_logik()
        self.assertEqual(logik.status_zeile("in_kontaktierung").label, "Kontaktiert")
        self.assertEqual(logik.status_zeile("qualifiziert").label, "Kontaktiert")
        labels = lead_boards.phasen_labels(logik)
        self.assertEqual((labels["in_kontaktierung"], labels["qualifiziert"]), ("Kontaktiert", "Kontaktiert"))
        self.assertEqual(lead_boards.phasen_mit_label(logik, "in_kontaktierung"),
                         {"in_kontaktierung", "qualifiziert"})
        self.assertEqual((logik.board_label("hauptboard"), logik.board_label("terminiert")),
                         ("Hauptboard", "Deals"))
        jetzt = datetime.now()
        ik = self.lead(40, phase="in_kontaktierung", versuche=1, erstkontakt_am=jetzt)
        q = self.lead(41, phase="qualifiziert", versuche=1, erstkontakt_am=jetzt)
        q.lead_phase = "qualifiziert"
        self.s.commit()
        # Hauptboard: beide Zeilen tragen das Status-Label „Kontaktiert“
        seite = self.client.get(f"/lead-management/hauptboard?q={NACHNAME}").text
        for v in (ik, q):
            zeile = zeile_html(seite, v.id)
            self.assertIn(">Kontaktiert</span>", zeile, v.lead_phase)
            self.assertNotIn(">Qualifiziert<", zeile)
            self.assertNotIn(">In Kontaktierung<", zeile)
        # Auswahlfelder führen das Label „Kontaktiert“ nur einmal (qualifiziert = doppelt)
        status_wahl = {e["key"]: e for e in lead_boards.auswahl_listen(self.s)["status_wahl"]}
        self.assertEqual(status_wahl["in_kontaktierung"]["label"], "Kontaktiert")
        self.assertFalse(status_wahl["in_kontaktierung"]["doppelt"])
        self.assertTrue(status_wahl["qualifiziert"]["doppelt"])
        self.assertEqual(status_wahl["qualifiziert"]["gleiche"], ["in_kontaktierung"])
        self.assertEqual(sum(1 for e in status_wahl.values() if e["label"] == "Kontaktiert" and not e["doppelt"]), 1)
        # Kanban Hauptboard: Spalten Neu · Kontaktiert (keine Spalte Qualifiziert)
        kanban = inhalt(self.client.get(f"/lead-management/board?board=hauptboard&q={NACHNAME}").text)
        self.assertIn("<h1>Kanban · Hauptboard", kanban)
        spalten = re.findall(r'class="kanban-spalte" data-phase="([^"]+)"', kanban)
        self.assertEqual(spalten, ["neu", "kontaktiert"])
        self.assertNotIn('data-phase="qualifiziert"', kanban)
        self.assertNotIn('data-phase="in_kontaktierung"', kanban)
        self.assertIn("<h3>Kontaktiert (", kanban)
        spalte = kanban.split('data-phase="kontaktiert"', 1)[1]
        for v in (ik, q):
            self.assertIn(f'href="/lead-management/lead/{v.id}"', spalte, v.lead_phase)
        # Kanban Deals: Terminiert · Erfasst · Angebot · Gewonnen (+ Verloren), Überschrift „Deals“
        deals = inhalt(self.client.get("/lead-management/board?board=terminiert").text)
        self.assertIn("<h1>Kanban · Deals", deals)
        self.assertEqual(re.findall(r'class="kanban-spalte" data-phase="([^"]+)"', deals),
                         ["terminiert", "erfasst", "angebot", "gewonnen", "verloren"])
        # Trichter: Stufe „Kontaktiert“ = Summe beider Phasen, keine Stufe „qualifiziert“
        daten = kern.statistik_leads(self.s, jetzt - timedelta(days=1), jetzt + timedelta(days=1),
                                     {"demo": True})
        namen = [s["name"] for s in daten["trichter"]]
        self.assertEqual(namen[:2], ["Eingang", "Kontaktiert"])
        self.assertNotIn("qualifiziert", namen)
        self.assertEqual(daten["kontaktiert_label"], "Kontaktiert")
        kontaktiert = next(s for s in daten["trichter"] if s["name"] == "Kontaktiert")
        self.assertGreaterEqual(kontaktiert["anzahl"], 2)
        self.assertGreaterEqual(daten["kontaktiert_phasen"]["in_kontaktierung"], 1)
        self.assertGreaterEqual(daten["kontaktiert_phasen"]["qualifiziert"], 1)
        statistik = inhalt(self.client.get("/lead-management/statistik").text)
        self.assertIn("Kontaktiert", statistik)
        self.assertNotIn("Score-Verteilung", statistik)


# --- (e) Autospeichern ----------------------------------------------------------------------

class E_Autospeichern(Basis):
    def test_e_feld_speichern_aktivitaet_und_ungueltige_plz(self):
        v = self.lead(50)
        alt = self.kunde(v).telefon
        r = self.feld(v, "telefon", " 0203 / 11 22 33 ")
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["wert"], "0203 / 11 22 33")
        self.assertIsInstance(d["pflicht_offen"], list)
        self.assertEqual(d["pflicht_anzahl"], len(d["pflicht_offen"]))
        self.assertEqual(self.kunde(v).telefon, "0203 / 11 22 33")
        akt = self.aktivitaeten(v, "aenderung")
        self.assertEqual(len(akt), 1)
        self.assertEqual(akt[0].text, f"Telefon: „{alt}“ → „0203 / 11 22 33“")       # Alt → Neu
        self.assertIn(f"Telefon: „{alt}“ → „0203 / 11 22 33“", self.kartei(v, tab="timeline").text)
        # gleicher Wert erneut → keine neue Aktivität
        d = self.feld(v, "telefon", "0203 / 11 22 33").json()
        self.assertFalse(d["geaendert"])
        self.assertEqual(len(self.aktivitaeten(v, "aenderung")), 1)
        # ungültige PLZ → Fehler, alter Wert bleibt, keine Aktivität
        r = self.feld(v, "plz", "12")
        self.assertEqual(r.status_code, 400)
        d = r.json()
        self.assertFalse(d["ok"])
        self.assertEqual(d["meldung"], "PLZ muss aus 5 Ziffern bestehen.")
        self.assertEqual(d["wert"], "47139")
        self.assertEqual(self.kunde(v).plz, "47139")
        self.assertEqual(len(self.aktivitaeten(v, "aenderung")), 1)
        # Select-Feld (Anrede) und Pflichtfeld-Zähler
        d = self.feld(v, "anrede", "Frau").json()
        self.assertTrue(d["ok"])
        self.assertEqual(self.kunde(v).anrede, "Frau")
        # kein Speichern-Button im Kundeninfo-Block, Felder tragen data-feld
        kartei = self.kartei(v).text
        block = kartei.split('id="lk-stammdaten"', 1)[1].split("</form>", 1)[0]
        block = re.sub(r"<noscript>.*?</noscript>", "", block, flags=re.S)   # Fallback ohne JavaScript
        self.assertNotIn('type="submit"', block)
        self.assertNotIn(">Speichern<", block)
        self.assertIn('data-feld="plz"', block)
        self.assertIn('class="lk-feld-status"', block)
        self.assertIn(f'data-feld-url="/lead-management/lead/{v.id}/feld"', kartei)
        # Rechte: Außendienst (angestellt) nur lesend
        ad_client = self.cookie_client(self.horst)
        r = self.feld(v, "ort", "Krefeld", client=ad_client)
        self.assertIn(r.status_code, (403, 404))
        self.assertEqual(self.kunde(v).ort, "Duisburg")


# --- (f) Kartei ohne Score/Quelle/Einwilligung/Qualifizierung -------------------------------

class F_Kartei(Basis):
    def test_f_kartei_aufbau_ohne_entfernte_bloecke(self):
        v = self.lead(60, anrede="Herr", score_punkte=42, score_klasse="B", einwilligung_werbung=True)
        r = self.kartei(v)
        self.assertEqual(r.status_code, 200)
        seite = r.text
        eigen = self.kartei_eigen(seite)
        for weg in ("Score", "Einwilligung", "Qualifizierung", "Quelle", "Kampagne", "42 · B",
                    'id="tab-qualifizierung"', 'name="quelle_id"', 'name="einwilligung_werbung"',
                    'class="karte lk-links"', 'class="lk-rechts"'):
            self.assertNotIn(weg, eigen, weg)
        self.assertIsNone(SCORE_MUSTER.search(eigen), SCORE_MUSTER.search(eigen))
        # Aufbau: Statuskette → Button Terminierung → Kundeninfo → Reiter → Blöcke
        kette = eigen.index('class="lk-statuskette"')
        self.assertLess(kette, eigen.index('id="lk-kundeninfo"'))
        self.assertLess(eigen.index('id="lk-kundeninfo"'), eigen.index('role="tablist"'))
        self.assertLess(eigen.index('role="tablist"'), eigen.index('id="lk-bloecke"'))
        self.assertIn("Terminierung", eigen)
        self.assertIn(">Kontaktiert<", eigen)                       # Statuskette mit Label aus dem Blatt Status
        self.assertNotIn(">Qualifiziert<", eigen)
        # Reiter Termin · Anrufnotizen · E-Mail-Verlauf · Timeline, Termin als Standard
        tabs = re.findall(r'id="tab-([a-z]+)"', eigen)
        self.assertEqual(tabs, ["termin", "anrufe", "mails", "timeline"])
        self.assertIn('id="tab-termin" class="lk-tab" data-tab="termin"', eigen)
        self.assertRegex(eigen, r'id="tab-termin"[^>]*aria-selected="true"')
        # Blöcke Termine · Angebote · Erfassungen · Projekt · Anhänge · To-Dos
        self.assertEqual(re.findall(r'data-bereich="([a-z]+)"', eigen),
                         ["termine", "angebote", "erfassungen", "projekt", "anhaenge", "todos"])
        # Kundeninfo: Anrede/Vorname/Nachname sichtbar, Wunschzeiten bleiben, Eingangsdatum nur Anzeige
        for name in ("anrede", "vorname", "nachname", "telefon", "email", "strasse", "plz", "ort",
                     "vertriebskanal", "objektart"):
            self.assertIn(f'data-feld="{name}"', eigen, name)
        self.assertIn("Wunschzeit", eigen)
        self.assertIn("Eingang", eigen)
        # Lead-Kopf der Vorgangsakte ohne Score
        akte = inhalt(self.client.get(f"/vorgaenge/{v.id}").text)
        self.assertNotIn("42 · B", akte)
        self.assertIsNone(SCORE_MUSTER.search(akte), SCORE_MUSTER.search(akte))


# --- (g) Terminvorschläge im Block Termine (Kontrollwerte 2 und 3) --------------------------

class G_Terminvorschlaege(Basis):
    def setUp(self):
        lead_termin.vorschlaege_cache_leeren()

    def test_g_adresse_fehlt_dann_vorschlaege_ohne_neuladen(self):
        v = self.lead(70, strasse="")                              # Demo-Lead ohne Adresse
        block = self.vorschlaege_block(self.kartei(v).text)
        self.assertIn('data-zustand="adresse_fehlt"', block)
        self.assertIn("Adresse fehlt", block)
        self.assertNotIn("Vormerken", block)
        d = self.vorschlaege_json(v)
        self.assertEqual(d["status"], "adresse_fehlt")
        self.assertEqual(d["vorschlaege"], [])
        self.assertIn("Adresse fehlt", d["hinweis"])
        # Kontrollwert 2: Straße per Autospeichern → Cache verworfen, Vorschläge ohne Seitenneuladen
        r = self.feld(v, "strasse", "Sonnenwall 1")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["adresse_vollstaendig"])
        start = time.monotonic()
        d = self.vorschlaege_json(v)
        self.assertLess(time.monotonic() - start, 10)
        self.assertNotEqual(d["status"], "adresse_fehlt")
        self.assertIn(d["status"], ("ok", "keine"))
        self.assertFalse(d["aus_cache"])
        if d["status"] == "ok":
            self.assertTrue(1 <= len(d["vorschlaege"]) <= 5)
            for e in d["vorschlaege"]:
                for key in ("ad_id", "ad_name", "beginn", "beginn_text", "begruendung", "umweg_min"):
                    self.assertIn(key, e)
            self.assertNotIn(self.hv.id, {e["ad_id"] for e in d["vorschlaege"]})   # kein HV für den Innendienst
        # Block in der Kartei lädt jetzt (Platzhalter-Text, Button „Vormerken“ kommt per JS)
        block = self.vorschlaege_block(self.kartei(v).text)
        self.assertIn('data-zustand="laden"', block)
        self.assertIn("Vorschläge werden berechnet …", block)
        self.assertIn(f'data-url="/lead-management/lead/{v.id}/termin/vorschlaege.json"', block)
        self.assertIn(f'data-buchen="/lead-management/lead/{v.id}/termin"', block)
        self.assertIn("Alle Vorschläge / manuell", self.kartei(v).text)
        # zweiter Abruf aus dem Cache (10 Minuten je Lead)
        self.assertTrue(self.vorschlaege_json(v)["aus_cache"])

    def test_g_hv_lead_hinweis_fuer_innendienst_vorschlaege_fuer_den_hv(self):
        v = self.lead(71, ad_id=self.hv.id)
        hinweis = f"Lead liegt bei {self.hv.name} (Handelsvertreter), Terminierung durch den Vertreter"
        block = self.vorschlaege_block(self.kartei(v).text)
        self.assertIn('data-zustand="hv_lead"', block)
        self.assertIn(hinweis, block)
        d = self.vorschlaege_json(v)
        self.assertEqual((d["status"], d["hv_name"], d["vorschlaege"]), ("hv_lead", self.hv.name, []))
        self.assertEqual(d["hinweis"], hinweis)
        # der Handelsvertreter selbst: Vorschläge nur für sich
        hv_client = self.cookie_client(self.hv)
        self.assertIn('data-zustand="laden"', self.vorschlaege_block(self.kartei(v, client=hv_client).text))
        d = self.vorschlaege_json(v, client=hv_client)
        self.assertIn(d["status"], ("ok", "keine"))
        self.assertEqual([k["ad_id"] for k in d.get("kandidaten", [])], [self.hv.id])
        self.assertTrue(all(e["ad_id"] == self.hv.id for e in d["vorschlaege"]))
        # Lesesicht (angestellter AD) ohne Vorschlagsblock
        seite = self.kartei(v, client=self.cookie_client(self.horst)).text
        self.assertNotIn('id="lk-vorschlaege"', seite)

    def test_g_kontrollwert_rene_golaschewski(self):
        rene = next((b for b in self.s.query(Benutzer).filter(Benutzer.aktiv.is_(True))
                     if "golaschewski" in b.name.lower()), None)
        if rene is None or not lead_v2.ist_handelsvertreter(self.s, rene):
            self.skipTest("René Golaschewski ist in dieser DB kein gekennzeichneter Handelsvertreter")
        v = self.lead(72, ad_id=rene.id)
        # Innendienst (Admin im Demo-Modus): HV-Hinweis im Block Termine
        block = self.vorschlaege_block(self.kartei(v).text)
        self.assertIn('data-zustand="hv_lead"', block)
        self.assertIn(f"Lead liegt bei {rene.name} (Handelsvertreter), Terminierung durch den Vertreter", block)
        erg = lead_termin.kandidaten(self.s, v, benutzer=self.innen)
        self.assertEqual(erg["hv_lead"].id, rene.id)
        self.assertNotIn(rene.id, {k["ad"].id for k in erg["kandidaten"]})
        # René selbst: Vorschläge nur für sich
        erg = lead_termin.kandidaten(self.s, v, benutzer=rene)
        self.assertEqual([k["ad"].id for k in erg["kandidaten"]], [rene.id])
        d = self.vorschlaege_json(v, client=self.cookie_client(rene))
        self.assertIn(d["status"], ("ok", "keine"))
        self.assertTrue(all(e["ad_id"] == rene.id for e in d["vorschlaege"]))


# --- (h) Terminassistent: kein HV für den Innendienst, der HV selbst schon -----------------

class H_Assistent(Basis):
    def test_h_kandidaten_und_vorschlaege(self):
        v = self.lead(80)
        for benutzer in (self.innen, self.admin, None):
            erg = lead_termin.kandidaten(self.s, v, benutzer=benutzer)
            ids = {k["ad"].id for k in erg["kandidaten"]}
            self.assertIn(self.horst.id, ids)
            self.assertNotIn(self.hv.id, ids)
            hv_eintrag = next(a for a in erg["ausgeschlossen"] if a["ad"].id == self.hv.id)
            self.assertEqual(hv_eintrag["grund"], "Handelsvertreter terminieren ihre Leads selbst")
            self.assertTrue(hv_eintrag["manuell_erlaubt"])           # manuelle Buchung bleibt möglich
            self.assertIsNone(erg["hv_lead"])
        erg = lead_termin.kandidaten(self.s, v, benutzer=self.hv)
        self.assertEqual([k["ad"].id for k in erg["kandidaten"]], [self.hv.id])
        vorschlaege = lead_termin.vorschlaege(self.s, v, benutzer=self.innen)
        self.assertNotIn(self.hv.id, {x["ad"].id for x in vorschlaege["vorschlaege"]})
        vorschlaege_hv = lead_termin.vorschlaege(self.s, v, benutzer=self.hv)
        self.assertTrue(all(x["ad"].id == self.hv.id for x in vorschlaege_hv["vorschlaege"]))
        # Assistent-Seite: Begründung sichtbar, HV nur unter „nur manuell“
        seite = inhalt(self.client.get(f"/lead-management/lead/{v.id}/termin").text)
        self.assertIn("Handelsvertreter terminieren ihre Leads selbst", seite)
        self.assertIn('<optgroup label="Handelsvertreter (nur manuell)">', seite)
        self.assertNotIn("Score C – Termin trotzdem buchen?", seite)


# --- (i) Nicht erreicht ohne Dialog/Wiedervorlage (Kontrollwert 1) ---------------------------

class I_NichtErreicht(Basis):
    def test_i_versuche_mails_und_sperre(self):
        maximal = kern.versuche_max(self.s)
        self.assertGreaterEqual(maximal, 5)
        v = self.lead(90)
        self.assertIsNone(v.naechste_aktion_am)
        # 1. Versuch: Zeitstempel jetzt, kein wiedervorlage_am, keine Mail
        vor = datetime.now()
        r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "nicht_erreicht"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(self.meldung(r), "Nicht erreicht protokolliert (Versuch 1).")
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual((v.versuch_nr, v.lead_phase), (1, "in_kontaktierung"))
        self.assertIsNone(v.naechste_aktion_am)
        akt = self.anrufe(v.id)[-1]
        self.assertEqual(akt.ergebnis, "nicht_erreicht")
        self.assertIsNone(akt.naechste_aktion_am)
        self.assertLessEqual(abs((akt.zeitpunkt - vor).total_seconds()), 60)
        self.assertEqual(self.mails(v.id), [])
        # 2. Versuch: Mail nicht_erreicht geplant; mitgesendetes wiedervorlage_am wird ignoriert
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "nicht_erreicht", "wiedervorlage_am": "2031-01-01T10:00"},
                             follow_redirects=False)
        self.assertEqual(self.meldung(r), "Nicht erreicht protokolliert (Versuch 2) – Mail geplant.")
        self.s.expire_all()
        self.assertIsNone(self.s.get(Vorgang, v.id).naechste_aktion_am)
        self.assertEqual(self.mails(v.id), [("nicht_erreicht", "geplant")])
        # 3. Versuch (Kontrollwert 1): Aktivität mit Zeitstempel, WV leer, 3 Punkte orange, keine Mail
        r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "nicht_erreicht"},
                             follow_redirects=False)
        self.assertEqual(self.meldung(r), "Nicht erreicht protokolliert (Versuch 3).")
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.versuch_nr, 3)
        self.assertIsNone(v.naechste_aktion_am)
        self.assertEqual(self.mails(v.id), [("nicht_erreicht", "geplant")])     # keine neue Mail
        akt = self.anrufe(v.id)[-1]
        akt.zeitpunkt = datetime.now().replace(hour=14, minute=5, second=0, microsecond=0)
        self.s.commit()
        self.assertEqual(len(self.anrufe(v.id)), 3)
        zeile = zeile_html(self.client.get(f"/lead-management/anrufliste?meine=0&q={NACHNAME}").text, v.id)
        self.assertIn("lm-dots warn", zeile)
        self.assertIn("3×", zeile)
        self.assertIn("14:05", zeile)
        anrufnotizen = inhalt(self.kartei(v, tab="anrufe").text)
        self.assertIn("14:05", anrufnotizen)
        self.assertIn("Nicht erreicht", anrufnotizen)
        # kein Dialog mehr: weder Kartei noch Anrufliste rendern dlg-nichterreicht
        self.assertNotIn('id="dlg-nichterreicht"', self.kartei(v).text)
        self.assertNotIn('id="dlg-nichterreicht"', self.client.get("/lead-management/anrufliste").text)
        self.assertIn('id="lm-direkt-form"', self.kartei(v).text)
        # 4. Versuch: zweite Mail (erste gilt als versendet); dann bis zur Sperre
        for m in self.s.query(KommunikationLog).filter_by(vorgang_id=v.id, vorlage_key="nicht_erreicht"):
            m.status = "protokolliert"
        self.s.commit()
        r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "mailbox"},
                             follow_redirects=False)
        self.assertEqual(self.meldung(r), "Mailbox protokolliert (Versuch 4) – Mail geplant.")
        for _ in range(5, maximal):
            self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "nicht_erreicht"},
                             follow_redirects=False)
        r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "nicht_erreicht"},
                             follow_redirects=False)
        self.assertIn(f"Nicht erreicht protokolliert (Versuch {maximal})", self.meldung(r))
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual((v.versuch_nr, v.lead_phase), (maximal, "nicht_erreicht"))
        self.assertIsNone(v.naechste_aktion_am)
        offen = {k for k, status in self.mails(v.id) if status == "geplant"}
        self.assertTrue({"disqualifiziert"} <= offen)
        self.assertNotIn("nurture", offen)          # v29 (Phase 142): Nurture entfällt
        self.assertTrue(lead_anrufliste.versuche_gesperrt(self.s, v))
        # Sperre nach dem letzten Versuch: kein weiterer Zähler, keine Aktivität
        r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "nicht_erreicht"},
                             follow_redirects=False)
        self.assertEqual(self.meldung(r), lead_anrufliste.SPERRE_MELDUNG)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).versuch_nr, maximal)
        self.assertEqual(len(self.anrufe(v.id)), maximal)
        # Kaskaden-Vorschlag bleibt erreichbar, setzt aber nichts
        self.assertEqual(self.client.get(f"/lead-management/anruf/{v.id}/vorschlag").status_code, 200)
        # „Erreicht“ führt bei score_aktiv aus in die Kartei, Reiter Termin
        w = self.lead(91)
        r = self.client.post(f"/lead-management/anruf/{w.id}", data={"ergebnis": "erreicht"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith(f"/lead-management/lead/{w.id}?tab=termin"),
                        r.headers["location"])


# --- (j) score_aktiv = aus ------------------------------------------------------------------

class J_ScoreAus(Basis):
    def test_j_eingang_ohne_score_pipeline_ohne_score_keine_anzeige(self):
        self.assertFalse(lead_v2.score_aktiv(self.s))
        v = self.lead(100)
        self.assertIsNone(v.score_punkte)
        self.assertIsNone(v.score_klasse)
        self.assertEqual(self.s.query(LeadQualifizierung).filter_by(vorgang_id=v.id).count(), 0)
        self.assertEqual(kern.score_berechnen(self.s, v), (0, ""))
        self.assertEqual(kern.erfassungs_vorbelegung(self.s, v), {})
        # Pipeline-Wert: nur Phasen-Quote – Score/Klasse ändern nichts
        quote = int(kern.parameter_holen(self.s, "quote_neu", "0"))
        erwartung = kern.erwartungswert(self.s, self.kunde(v)) * quote // 100
        self.assertGreater(erwartung, 0)
        v.score_klasse, v.score_punkte = "A", 95
        self.s.commit()
        mit_a = kern.pipeline_wert(self.s)
        v.score_klasse, v.score_punkte = "C", 1
        self.s.commit()
        mit_c = kern.pipeline_wert(self.s)
        v.lead_phase = "unqualifiziert"
        self.s.commit()
        ohne = kern.pipeline_wert(self.s)
        v.lead_phase = "neu"
        self.s.commit()
        self.assertEqual(mit_a, mit_c)
        self.assertEqual(mit_a - ohne, erwartung)
        # keine Score-/Klassenanzeige: Hauptboard (keine Spalte), Anrufliste, Kanban, Dashboard, HV-Ansicht
        self.reset(self.client)
        for pfad in (f"/lead-management/hauptboard?q={NACHNAME}", f"/lead-management/anrufliste?meine=0&q={NACHNAME}",
                     f"/lead-management/board?q={NACHNAME}", "/lead-management/dashboard",
                     "/lead-management/handelsvertreter", "/lead-management/statistik"):
            seite = inhalt(self.client.get(pfad).text)
            self.assertIsNone(SCORE_MUSTER.search(seite), (pfad, SCORE_MUSTER.search(seite)))
        self.assertNotIn('<th class="sp-score"', self.client.get(f"/lead-management/hauptboard?q={NACHNAME}").text)
        self.assertNotIn("score", [x["key"] for x in lead_boards.spalten_fuer(self.s, self.admin, "hauptboard")])
        # Spalte Score nur bei score_aktiv an im Katalog
        self.assertIn("score", [k for k, _, _ in lead_boards.spalten_basis("hauptboard", score=True)])
        self.assertNotIn("score", [k for k, _, _ in lead_boards.spalten_basis("hauptboard", score=False)])
        # Lead-Einstellungen führen den Schalter (Standard aus) und ohne_schritt_tage
        einstellungen = self.client.get("/parametrierung/lead-einstellungen").text
        self.assertIn('name="score_aktiv"', einstellungen)
        self.assertNotIn('name="ohne_schritt_tage"', einstellungen)   # v29 (Phase 141): ausgeblendet


# --- (k) To-Dos-Seite ------------------------------------------------------------------------

class K_Todos(Basis):
    def test_k_seite_navigation_anlegen_erledigen(self):
        r = self.client.get("/lead-management/todos")
        self.assertEqual(r.status_code, 200)
        seite = r.text
        self.assertEqual(aktive_nav_keys(seite), ["todos"])
        self.assertIn("<h1>To-Dos", seite)
        for text_ in ("Meine offenen", "Von mir vergeben", "Erledigt", "Neues To-Do",
                      'action="/lead-management/todos/neu"', 'name="an_benutzer_id"'):
            self.assertIn(text_, seite, text_)
        # anlegen (an Benutzer B, mit Vorgangsbezug), erscheint unter „Von mir vergeben“ und bei B
        v = self.lead(110)
        titel = f"{PRAEFIX}Rückruf vorbereiten"
        r = self.client.post("/lead-management/todos/neu",
                             data={"titel": titel, "an_benutzer_id": str(self.zweiter.id),
                                   "vorgang_id": str(v.id), "text": "Testauftrag",
                                   "zurueck": "/lead-management/todos?sicht=vergeben"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn(titel, self.client.get("/lead-management/todos?sicht=vergeben").text)
        seite_b = self.client2.get("/lead-management/todos").text
        self.assertIn(titel, seite_b)
        self.assertIn(f"/lead-management/lead/{v.id}", seite_b)
        todo = self.s.query(Todo).filter_by(titel=titel).one()
        self.assertEqual((todo.an_benutzer_id, todo.vorgang_id, todo.status), (self.zweiter.id, v.id, "offen"))
        # Block To-Dos in der Kartei zeigt den Auftrag
        self.assertIn(titel, self.kartei(v).text)
        # erledigen durch B → Sicht „Erledigt“
        r = self.client2.post(f"/lead-management/todos/{todo.id}/erledigt",
                              data={"zurueck": "/lead-management/todos?sicht=erledigt"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        self.assertEqual(self.s.get(Todo, todo.id).status, "erledigt")
        self.assertIn(titel, inhalt(self.client2.get("/lead-management/todos?sicht=erledigt").text))
        # (nur der Seiteninhalt – die Glocke in der Kopfzeile nennt den Auftrag weiter)
        self.assertNotIn(titel, inhalt(self.client2.get("/lead-management/todos?sicht=meine").text))
        # Dashboard-Kachel verlinkt auf die To-Dos-Seite
        self.assertIn("/lead-management/todos", self.client.get("/lead-management/dashboard").text)


# --- (l) Prüfung F (Agent F): Befunde der adversarialen Prüfung der Phasen 118–120 ----------
# Spalten je Nutzer auch im Infoabend und in der HV-Ansicht (Plan: „Spalten der
# Boards (Hauptboard, Deals, Infoabend, Handelsvertreter) je Nutzer“), Sticky-
# Filterblock des Infoabends, To-Do-Filter fällig/alle, Icon-Leiste der Kartei
# markiert das Board des Leads, Phasen-Label der Bestandshinweise aus dem Blatt Status.

def kopf_vor_zeile(seite: str, vorgang_id: int) -> str:
    """<thead> der Tabelle, in der die Zeile des Vorgangs steht."""
    teil = seite[:seite.index(f'data-vorgang="{vorgang_id}"')]
    return teil[teil.rindex("<thead>"):]


class L_Pruefung(Basis):
    BOARDS = ("info", "handelsvertreter")

    def setUp(self):
        for board in self.BOARDS:
            self.reset(self.client, board)
            self.reset(self.client2, board)

    def tearDown(self):
        for board in self.BOARDS:
            self.reset(self.client, board)
            self.reset(self.client2, board)

    def spalten_mit(self, board, **sichtbar):
        liste = self.spalten_json(board=board)["spalten"]
        return [{"key": x["key"], "sichtbar": sichtbar.get(x["key"], x["sichtbar"]), "name": x["name"]}
                for x in liste]

    def test_l_infoabend_spalten_je_nutzer_und_sticky_filter(self):
        lead_info.veranstaltungen_anlegen(self.s)
        self.s.commit()
        veranst = (self.s.query(InfoVeranstaltung).filter(InfoVeranstaltung.archiviert.is_(False),
                                                            InfoVeranstaltung.beginn > datetime.now())
                   .order_by(InfoVeranstaltung.beginn).first())
        self.assertIsNotNone(veranst)
        v = self.lead(120, veranstaltung_id=veranst.id)
        seite = self.client.get("/lead-management/info-veranstaltung").text
        self.assertIn(f'data-vorgang="{v.id}"', seite)
        # Filterblock sticky außerhalb des scrollenden Tabellen-Containers, Spaltenwähler darin
        i_filter, i_tabellen = seite.index('id="lm-filterblock"'), seite.index('id="lm-tabellen"')
        self.assertLess(i_filter, i_tabellen)
        block = seite[i_filter:i_tabellen]
        for teil in ('id="li-filterform"', 'id="lm-spaltenwahl"', 'id="lm-spaltenliste"', 'id="lm-spalten-reset"'):
            self.assertIn(teil, block, teil)
        self.assertNotIn("li-tabelle", block)
        self.assertIn('data-lm-spalten-board="info"', seite)
        self.assertIn('id="lm-daten"', seite)
        # Spaltenköpfe mit Werkzeugen; Kundenname und Status fest, Infoabend-Spalten ohne Werkzeuge
        kopf = kopf_vor_zeile(seite, v.id)
        self.assertRegex(kopf, r'data-key="lead"[^>]*draggable="false"')
        self.assertRegex(kopf, r'data-key="status"[^>]*draggable="false"')
        self.assertRegex(kopf, r'data-key="telefon"[^>]*draggable="true"')
        self.assertIn('class="lm-th-stift" data-key="telefon"', kopf)
        self.assertIn('<th class="sp-ergebnis">Ergebnis</th>', kopf)
        for key in ("ergebnis", "teilgenommen", "veranstaltung"):
            self.assertNotIn(f'data-key="{key}"', kopf, key)
        # eigene Konfiguration des Infoabends: umbenennen, ausblenden, Sortierung merken
        r = self.json_post("/lead-management/boards/spalten",
                           {"board": "info", "umbenennen": {"key": "telefon", "name": "Rufnummer"}})
        self.assertEqual(r.status_code, 200, r.text)
        r = self.json_post("/lead-management/boards/spalten",
                           {"board": "info", "spalten": self.spalten_mit("info", ort=False)})
        self.assertEqual(r.status_code, 200, r.text)
        r = self.json_post("/lead-management/boards/spalten",
                           {"board": "info", "sort": {"key": "eingang", "richtung": "auf"}})
        self.assertEqual(r.json()["sort"], {"key": "eingang", "richtung": "auf"})
        seite = self.client.get("/lead-management/info-veranstaltung").text
        kopf = kopf_vor_zeile(seite, v.id)
        self.assertIn(">Rufnummer</span>", kopf)
        self.assertNotIn('<th class="sp-ort"', kopf)
        self.assertRegex(kopf, r'data-key="eingang"[^>]*aria-sort="ascending"')
        info = lead_info.spalten_fuer(self.s, 1, True)
        self.assertEqual(next(x for x in info if x["key"] == "telefon")["titel"], "Rufnummer")
        self.assertFalse(next(x for x in info if x["key"] == "ort")["sichtbar"])
        self.assertEqual([x["key"] for x in info][:4], ["lead", "status", "ergebnis", "teilgenommen"])
        self.assertEqual(lead_info.sortierung_fuer(self.s, self.admin), {"key": "eingang", "richtung": "auf"})
        # Hauptboard des Nutzers bleibt unberührt, Benutzer B sieht im Infoabend den Standard
        haupt = thead_html(self.client.get(f"/lead-management/hauptboard?q={NACHNAME}").text)
        self.assertIn(">Telefon</span>", haupt)
        self.assertIn('<th class="sp-ort"', haupt)
        self.assertNotIn("aria-sort", haupt)
        kopf_b = kopf_vor_zeile(self.client2.get("/lead-management/info-veranstaltung").text, v.id)
        self.assertIn(">Telefon</span>", kopf_b)
        self.assertIn('<th class="sp-ort"', kopf_b)
        self.assertNotIn("Rufnummer", kopf_b)
        # Zurücksetzen stellt den Standard wieder her
        self.reset(self.client, "info")
        kopf = kopf_vor_zeile(self.client.get("/lead-management/info-veranstaltung").text, v.id)
        self.assertIn(">Telefon</span>", kopf)
        self.assertIn('<th class="sp-ort"', kopf)

    def test_l_hv_ansicht_spalten_je_nutzer(self):
        v = self.lead(121, ad_id=self.hv.id)
        seite = self.client.get("/lead-management/handelsvertreter").text
        self.assertIn(f'data-vorgang="{v.id}"', seite)
        for teil in ('data-lm-spalten-board="handelsvertreter"', 'id="lm-filterblock"',
                     'id="lm-spaltenwahl"', 'id="lm-spalten-reset"', 'id="lm-daten"'):
            self.assertIn(teil, seite, teil)
        kopf = kopf_vor_zeile(seite, v.id)
        self.assertRegex(kopf, r'data-key="lead"[^>]*draggable="false"')
        self.assertIn('class="lm-th-stift" data-key="ort"', kopf)
        self.assertIn('<th class="sp-hv">Vertreter</th>', kopf)
        zeile = zeile_html(seite, v.id)
        self.assertIn('class="sp-lead"', zeile)
        self.assertIn('class="sp-hv"', zeile)
        # Standard der HV-Ansicht = v23-Spalten (Außendienst = Spalte „Vertreter“, Innendienst,
        # Notiz, Straße, E-Mail, Wiedervorlage ausgeblendet, aber einblendbar)
        standard = self.spalten_json(board="handelsvertreter")["spalten"]
        self.assertEqual({x["key"] for x in standard if x["sichtbar"]},
                         {"lead", "status", "kanal", "versuche", "letzter_kontakt", "eingang",
                          "ort", "interessen", "telefon", "termin"})
        self.assertIn("ad", {x["key"] for x in standard if not x["sichtbar"]})
        self.assertNotIn('<th class="sp-ad"', kopf)                       # kein doppelter Außendienst
        self.assertNotIn('class="sp-ad"', zeile)
        # umbenennen + ausblenden nur in der HV-Ansicht dieses Nutzers
        r = self.json_post("/lead-management/boards/spalten",
                           {"board": "handelsvertreter", "umbenennen": {"key": "ort", "name": "Stadt"}})
        self.assertEqual(r.status_code, 200, r.text)
        r = self.json_post("/lead-management/boards/spalten",
                           {"board": "handelsvertreter", "spalten": self.spalten_mit("handelsvertreter", telefon=False, email=True)})
        self.assertEqual(r.status_code, 200, r.text)
        seite = self.client.get("/lead-management/handelsvertreter").text
        kopf = kopf_vor_zeile(seite, v.id)
        self.assertIn(">Stadt</span>", kopf)
        self.assertNotIn('<th class="sp-telefon"', kopf)
        self.assertIn('<th class="sp-email"', kopf)                       # eingeblendet
        sichtbar = [x for x in self.spalten_json(board="handelsvertreter")["spalten"] if x["sichtbar"]]
        self.assertFalse(any(x["key"] == "telefon" for x in sichtbar))
        zeile = zeile_html(seite, v.id)
        self.assertEqual(zeile.count("<td"), len(sichtbar) + 1)          # Spalten + Vertreter
        self.assertEqual(kopf.count("<th "), len(sichtbar) + 1)         # („<thead>“ zählt nicht)
        haupt = thead_html(self.client.get(f"/lead-management/hauptboard?q={NACHNAME}").text)
        self.assertIn(">Ort</span>", haupt)
        self.assertNotIn("Stadt", haupt)
        self.assertIn('<th class="sp-telefon"', haupt)
        kopf_b = kopf_vor_zeile(self.client2.get("/lead-management/handelsvertreter").text, v.id)
        self.assertIn(">Ort</span>", kopf_b)
        self.assertNotIn("Stadt", kopf_b)
        # der Handelsvertreter selbst (nur eigene Leads) bekommt dieselben Werkzeuge
        seite_hv = self.cookie_client(self.hv).get("/lead-management/handelsvertreter").text
        self.assertIn('data-lm-spalten-board="handelsvertreter"', seite_hv)
        self.assertIn(f'data-vorgang="{v.id}"', seite_hv)
        self.assertIn('class="lm-th-stift" data-key="ort"', kopf_vor_zeile(seite_hv, v.id))

    def test_l_todos_filter_faellig_alle(self):
        jetzt = datetime.now()
        faellig = lead_todos.anlegen(self.s, self.admin, self.admin.id, f"{PRAEFIX}Überfällig",
                                     faellig_am=jetzt - timedelta(hours=1))
        spaeter = lead_todos.anlegen(self.s, self.admin, self.admin.id, f"{PRAEFIX}Nächste Woche",
                                     faellig_am=jetzt + timedelta(days=5))
        ohne = lead_todos.anlegen(self.s, self.admin, self.admin.id, f"{PRAEFIX}Ohne Datum")
        self.s.commit()
        alle = inhalt(self.client.get("/lead-management/todos").text)
        for t in (faellig, spaeter, ohne):
            self.assertIn(t.titel, alle)
        self.assertIn('href="/lead-management/todos?sicht=meine&faellig=1"', alle)
        self.assertRegex(alle, r">Fällig <span class=\"n rot\">\d+</span>")
        nur = inhalt(self.client.get("/lead-management/todos?faellig=1").text)
        self.assertIn(faellig.titel, nur)
        self.assertNotIn(spaeter.titel, nur)
        self.assertNotIn(ohne.titel, nur)
        self.assertIn("nur fällige", nur)
        self.assertIn('name="faellig" value="1"', nur)                    # Suche behält den Filter
        # Sicht-Links behalten den Filter; ohne fällige in der Sicht „Erledigt“ leer
        self.assertIn('href="/lead-management/todos?sicht=vergeben&faellig=1"', nur)
        erledigt = inhalt(self.client.get("/lead-management/todos?sicht=erledigt&faellig=1").text)
        self.assertIn("Keine fälligen To-Dos.", erledigt)

    def test_l_kartei_markiert_board_des_leads(self):
        neu = self.lead(122)
        deal = self.lead(123, phase="terminiert")
        self.assertEqual(aktive_nav_keys(self.kartei(neu).text), ["hauptboard"])
        self.assertEqual(aktive_nav_keys(self.kartei(deal).text), ["terminiert"])

    def test_l_bestandshinweis_mit_label_aus_dem_blatt_status(self):
        alt = self.lead(124, phase="qualifiziert")
        neu = self.lead(125)
        text_ = lead_info.bestand_hinweis_schreiben(
            self.s, neu, {"kunde": self.kunde(alt), "vorgang": alt, "phase": "qualifiziert"}, self.admin)
        self.s.commit()
        self.assertIn("(Phase Kontaktiert)", text_)
        self.assertNotIn("Qualifiziert", text_)
        hinweise = lead_info.bestand_hinweise(self.s, [neu.id])
        self.assertEqual(hinweise[neu.id]["phase"], "Kontaktiert")

    def test_l_spaltenwerkzeuge_statisch(self):
        js = (PROJEKT / "app" / "static" / "lm_boards.js").read_text(encoding="utf-8")
        for teil in ("[data-lm-spalten-board]", "nurSpalten", "draggable') === 'false'",
                     "document.getElementById('li-meldung')"):
            self.assertIn(teil, js, teil)
        tabelle = (PROJEKT / "app" / "templates" / "leadmanagement" / "_tabelle.html").read_text(encoding="utf-8")
        self.assertIn("macro spalten_kopf(spalten, ctx, fest=('lead',))", tabelle)
        self.assertEqual(lead_info.KONFIG_BOARD, "info")
        self.assertIn(lead_info.KONFIG_BOARD, lead_boards.KONFIG_BOARDS)
        from app import lead_handelsvertreter
        self.assertIn(lead_handelsvertreter.KONFIG_BOARD, lead_boards.KONFIG_BOARDS)


if __name__ == "__main__":
    unittest.main()
