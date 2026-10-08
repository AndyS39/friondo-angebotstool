# Tests PLAN_LEAD_V3 Phase 118 (CLAUDE v25, Agent A): Navigation (Reihenfolge,
# Keys, Tooltips, aktiver Eintrag, „Mehr …“-Einstiege alle erreichbar),
# Bezeichnungen „Deals“ (statt Board „Terminiert“) und „Infoabend“ (statt
# „Info-Veranstaltung“), Spaltenkonfiguration je Nutzer (zwei Benutzer:
# verschieben, umbenennen, aus-/einblenden, Sortierung gemerkt, Zurücksetzen;
# Standard ohne Anrede/Vorname/Nachname mit fester Spalte „Kundenname“;
# v23-Listen bleiben lesbar), Score nur bei score_aktiv, Sticky-Filterleiste
# (Struktur + CSS/JS), Kanban mit EINER Spalte „Kontaktiert“, Phasen-Label
# „Kontaktiert“ für in_kontaktierung und qualifiziert.
# Laufen im Demo-Modus gegen die Entwicklungs-DB; Testleads tragen den
# Nachnamen „LeadV3B-Test“, Testbenutzer das Präfix „LeadV3B “ – alles wird
# aufgeräumt; die Spaltenkonfiguration von Benutzer 1 wird gesichert und
# am Ende wiederhergestellt.
import pathlib
import re
import unittest
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from sqlalchemy import text

from app import auth, lead_boards, lead_info, lead_v2, leadmanagement_logik
from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Angebot, AngebotsNotiz, Benutzer, BenutzerEinstellung,
                        KommunikationLog, Kunde, LeadAktivitaet, LeadQuelle, Vorgang,
                        VotTermin, LEAD_PHASEN)
from app.routers import lm_boards as router
from app.templating import templates

NACHNAME = "LeadV3B-Test"
BASIS = pathlib.Path(__file__).resolve().parents[1]
KEY = lead_boards.EINSTELLUNG_KEY

# Vertrag v25 (Briefing): Keys und Reihenfolge der Icon-Leiste und von „Mehr …“
NAV_HAUPT = [("dashboard", "Mein Dashboard", "/lead-management/dashboard"),
             ("hauptboard", "Hauptboard", "/lead-management/hauptboard"),
             ("terminiert", "Deals", "/lead-management/terminiert"),
             ("kontaktiert", "Kontaktiert", "/lead-management/kontaktiert"),
             ("karte", "Karte", "/lead-management/karte"),
             ("info", "Infoabend", "/lead-management/info-veranstaltung"),
             ("todos", "To-Dos", "/lead-management/todos"),
             ("handelsvertreter", "Handelsvertreter", "/lead-management/handelsvertreter")]
NAV_MEHR = [("anrufliste", "/lead-management/anrufliste"), ("board", "/lead-management/board"),
            ("kalender", "/lead-management/kalender"), ("vorlagen", "/lead-management/vorlagen"),
            ("uebersicht", "/lead-management/uebersicht"), ("statistik", "/lead-management/statistik"),
            ("kanal_report", "/lead-management/statistik/kanal"),
            ("posteingang", "/lead-management/posteingang"), ("import", "/lead-management/import"),
            ("neu", "/lead-management/neu"), ("lead-einstellungen", "/parametrierung/lead-einstellungen")]
NAV_LEGACY = {"tabelle": "hauptboard", "info-veranstaltung": "info"}
STANDARD_KEYS = [k for k, _, _ in lead_boards.SPALTEN]

RE_HAUPT = re.compile(r'<a href="([^"]+)" class="lm-leiste-eintrag[^"]*" title="([^"]+)"\s+'
                      r'aria-label="([^"]+)"\s*(aria-current="page")?\s*data-key="([^"]+)"', re.S)
RE_MEHR = re.compile(r'<a href="([^"]+)" class="([^"]*)" data-key="([^"]+)"\s*(aria-current="page")?')


def mit_wiederholung(funktion, versuche=12, pause=0.5):
    """SQLite kennt nur einen Schreiber: laufen andere Tests/Agenten parallel
    gegen die Entwicklungs-DB, kommt „database is locked“ – kurz warten."""
    import time
    from sqlalchemy.exc import OperationalError
    for n in range(versuche):
        try:
            return funktion()
        except OperationalError as fehler:
            if "locked" not in str(fehler).lower() or n == versuche - 1:
                raise
            time.sleep(pause * (n + 1))


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            for a in s.query(Angebot).filter_by(vorgang_id=v.id):
                s.query(AngebotsNotiz).filter_by(angebot_id=a.id).delete()
                s.delete(a)
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like("LeadV3B %")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(BenutzerEinstellung).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.commit()


def nav_html(seite: str) -> str:
    return seite.split('<nav class="lm-leiste"', 1)[1].split("</nav>", 1)[0]


def mehr_html(seite: str) -> str:
    return nav_html(seite).split('class="lm-leiste-menue"', 1)[1].split("</details>", 1)[0]


def thead_html(seite: str) -> str:
    """Erster Tabellenkopf der Seite (alle Gruppen haben dieselben Spalten)."""
    return seite.split("<thead>", 1)[1].split("</thead>", 1)[0]


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
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        cls.modus = kern.parameter_holen(cls.s, "lead_freigabe_modus", "admin")
        cls.score = kern.parameter_holen(cls.s, "score_aktiv", "aus")
        # Spaltenkonfiguration von Benutzer 1 sichern – die Tests starten vom Standard
        cls.alt_spalten = lead_v2.einstellung_holen(cls.s, 1, KEY, None)

        def _anlegen():
            cls.s.rollback()
            kern.parameter_setzen(cls.s, "lead_freigabe_modus", "admin")
            kern.parameter_setzen(cls.s, "score_aktiv", "aus")
            cls.s.execute(text("DELETE FROM benutzer_einstellungen WHERE benutzer_id = 1 AND key = :k"),
                          {"k": KEY})
            # zweiter Admin (Demo-Modus: nur Admins und Handelsvertreter sehen das Modul)
            cls.zweiter = Benutzer(name="LeadV3B Admin", rolle="admin", aktiv=True,
                                   pin_hash=auth.pin_hash("1234"))
            cls.hv = Benutzer(name="LeadV3B HV", rolle="aussendienst", aktiv=True,
                              pin_hash=auth.pin_hash("1234"))
            cls.s.add_all([cls.zweiter, cls.hv])
            cls.s.flush()
            cls.s.add(AdProfil(benutzer_id=cls.hv.id, terminiert_selbst=True, aktiv_terminierung=True))
            cls.s.commit()
        mit_wiederholung(_anlegen)
        cls.admin = cls.s.get(Benutzer, 1)
        cls.client2 = TestClient(app)
        cls.client2.post("/login", data={"benutzer_id": str(cls.zweiter.id), "pin": "1234"})

    @classmethod
    def tearDownClass(cls):
        def _aufraeumen():
            cls.s.rollback()
            aufraeumen(cls.s)
            kern.parameter_setzen(cls.s, "lead_freigabe_modus", cls.modus)
            kern.parameter_setzen(cls.s, "score_aktiv", cls.score)
            cls.s.execute(text("DELETE FROM benutzer_einstellungen WHERE benutzer_id = 1 AND key = :k"),
                          {"k": KEY})
            if cls.alt_spalten is not None:
                lead_v2.einstellung_setzen(cls.s, 1, KEY, cls.alt_spalten)
            cls.s.commit()
        try:
            mit_wiederholung(_aufraeumen)
        finally:
            cls.s.close()

    def lead(self, nr, phase="neu", anrede="", quelle_key="website", **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key=quelle_key).first()
        daten = {"anrede": anrede, "vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}",
                 "plz": "47139", "ort": "Duisburg", "telefon": f"0203 93{nr:04d}",
                 "sparten": ["WP"], "email": f"v3b{nr}@test.local"}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        vorgang.demo = True
        vorgang.lead_phase = phase
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def termin(self, vorgang, typ="vot", status="geplant", tage=3):
        t = VotTermin(vorgang_id=vorgang.id, ad_id=4, beginn=datetime.now() + timedelta(days=tage),
                      ende=datetime.now() + timedelta(days=tage, hours=1), status=status,
                      typ=typ, medium={"vot": "vor_ort", "telefon": "telefon", "online": "teams"}[typ],
                      demo=True)
        self.s.add(t)
        self.s.commit()
        return t

    def json_post(self, url, daten, client=None):
        return (client or self.client).post(url, json=daten, headers={"Accept": "application/json"})

    def spalten_json(self, client=None, board="hauptboard"):
        r = (client or self.client).get(f"/lead-management/boards/spalten?board={board}")
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def reset(self, client=None, board="hauptboard"):
        r = self.json_post("/lead-management/boards/spalten", {"board": board, "zuruecksetzen": True}, client)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()


# --- 1. Navigation ---------------------------------------------------------------------------

class Navigation(Basis):
    def test_reihenfolge_keys_tooltips_aktiv(self):
        seite = self.client.get("/lead-management/hauptboard").text
        nav = nav_html(seite)
        treffer = RE_HAUPT.findall(nav)
        self.assertEqual([t[4] for t in treffer], [k for k, _, _ in NAV_HAUPT])
        self.assertEqual([t[0] for t in treffer], [p for _, _, p in NAV_HAUPT])
        self.assertEqual([t[2] for t in treffer], [n for _, n, _ in NAV_HAUPT])
        for pfad, tooltip, name, aktiv, key in treffer:
            self.assertTrue(tooltip.startswith(name + " – "), (key, tooltip))     # Tooltip = Bezeichnung
            self.assertEqual(bool(aktiv), key == "hauptboard", key)              # aktiver Eintrag
        # lokale SVG-Icons: ein Symbol je Eintrag + „Mehr …“, keine externen Quellen
        self.assertGreaterEqual(nav.count('<svg class="symbol-svg"'), len(NAV_HAUPT) + 1 + len(NAV_MEHR))
        self.assertNotIn("http", nav.replace("http://localhost", ""))
        self.assertIn('aria-label="Mehr"', nav)
        self.assertIn("Mehr …", nav)
        self.assertNotIn("lm-leiste-mehr aktiv", nav)
        # „Mehr …“: Reihenfolge und Pfade laut Vertrag
        mehr = RE_MEHR.findall(mehr_html(seite))
        self.assertEqual([m[2] for m in mehr], [k for k, _ in NAV_MEHR])
        self.assertEqual([m[0] for m in mehr], [p for _, p in NAV_MEHR])
        for name in ("Anrufliste", "Kanban", "Kalender", "E-Mail-Vorlagen", "Übersicht",
                     "Statistik Leads", "Kanal-Report", "Posteingang unklar", "Import",
                     "Schnellanlage", "Lead-Einstellungen"):
            self.assertIn(name, mehr_html(seite), name)
        # Seite unter „Mehr …“: Aufklapper und Menüeintrag markiert
        vorlagen = self.client.get("/lead-management/vorlagen").text
        self.assertIn('class="lm-leiste-mehr aktiv"', nav_html(vorlagen))
        self.assertIn('class="aktiv" data-key="vorlagen" aria-current="page"', mehr_html(vorlagen))
        # Kontaktiert-Seite markiert ihren Eintrag; To-Dos-Seite ihren (v25: Key todos)
        self.assertIn('aria-current="page" data-key="kontaktiert"',
                      self.client.get("/lead-management/kontaktiert").text)
        self.assertIn('aria-current="page" data-key="todos"',
                      self.client.get("/lead-management/todos").text)
        # Demo-Badge und JS-Einbindung bleiben
        self.assertIn("lm-leiste-demo", nav)
        self.assertIn("/static/lm_boards.js", seite)

    def test_alle_einstiege_erreichbar(self):
        pfade = [p for _, _, p in NAV_HAUPT] + [p for _, p in NAV_MEHR] + ["/lead-management/boards/haupt"]
        for pfad in pfade:
            r = self.client.get(pfad, follow_redirects=False)
            self.assertIn(r.status_code, (200, 303), pfad)
            if r.status_code == 303:
                ziel = r.headers["location"]
                self.assertEqual(self.client.get(ziel, follow_redirects=False).status_code, 200, (pfad, ziel))
        r = self.client.get("/lead-management/boards/haupt?q=x", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/lead-management/hauptboard?q=x")

    def test_makro_markiert_jeden_key(self):
        vorlage = templates.env.from_string(
            "{% from 'leadmanagement/_nav.html' import lm_nav %}{{ lm_nav(k) }}")
        for key, _, _ in NAV_HAUPT:
            html = vorlage.render(k=key, css_version="t")
            self.assertIn(f'aria-current="page" data-key="{key}"', html, key)
            self.assertNotIn("lm-leiste-mehr aktiv", html, key)
        for key, _ in NAV_MEHR:
            html = vorlage.render(k=key, css_version="t")
            self.assertIn('class="lm-leiste-mehr aktiv"', html, key)
            self.assertIn(f'class="aktiv" data-key="{key}" aria-current="page"', html, key)
        for alt, neu in NAV_LEGACY.items():
            self.assertIn(f'aria-current="page" data-key="{neu}"', vorlage.render(k=alt, css_version="t"), alt)
        # unbekannter Key: „Mehr …“ markiert, Seite rendert trotzdem
        html = vorlage.render(k="unbekannt", css_version="t")
        self.assertIn('class="lm-leiste-mehr aktiv"', html)
        self.assertNotIn('aria-current="page"', html)

    def test_aufrufer_nutzen_vertragskeys(self):
        """Alle lm_nav('…')-Aufrufer im Modul verwenden Keys des v25-Vertrags
        (oder einen Jinja-Ausdruck wie `board`); Altlast: cockpit.html ('cockpit',
        V1-Seite ohne eigenen Einstieg) landet bewusst unter „Mehr …“."""
        bekannt = {k for k, _, _ in NAV_HAUPT} | {k for k, _ in NAV_MEHR} | set(NAV_LEGACY) | {"cockpit"}
        ordner = BASIS / "app" / "templates" / "leadmanagement"
        gefunden = {}
        for datei in sorted(ordner.glob("*.html")):
            for key in re.findall(r"lm_nav\('([^']+)'\)", datei.read_text(encoding="utf-8")):
                gefunden[datei.name] = key
                self.assertIn(key, bekannt, f"{datei.name}: lm_nav('{key}')")
        self.assertEqual(gefunden.get("kontaktiert.html"), "kontaktiert")
        self.assertEqual(gefunden.get("todos.html"), "todos")
        self.assertEqual(gefunden.get("vorlagen.html"), "vorlagen")

    def test_untere_leiste_und_symbole(self):
        css = (BASIS / "app" / "static" / "lead_v2.css").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 900px)", css)
        self.assertIn(".lm-leiste { top: auto; bottom: 0;", css)        # untere Icon-Zeile (v23)
        symbole = (BASIS / "app" / "templates" / "_symbole.html").read_text(encoding="utf-8")
        for name in ("deals", "aufgaben", "einstellungen", "zuruecksetzen", "dashboard", "karte",
                     "gruppe", "nutzer", "mehr", "kanban", "spalten", "stift"):
            self.assertIn(f"name == '{name}'", symbole, name)


# --- 2. Bezeichnungen Deals / Infoabend --------------------------------------------------------

class Bezeichnungen(Basis):
    def test_deals_statt_terminiert_als_boardname(self):
        logik = leadmanagement_logik.hole_logik()
        self.assertEqual(logik.board_label("terminiert"), "Deals")
        self.assertEqual(lead_boards.board_label("terminiert"), "Deals")
        self.assertEqual(lead_boards.board_label("hauptboard"), "Hauptboard")
        self.assertEqual(lead_boards.board_info("terminiert")["titel"], "Deals")
        self.assertEqual(lead_boards.board_info("terminiert")["key"], "terminiert")   # Pfad bleibt
        # Phasen-Label der Lead-Phase terminiert bleibt „Terminiert“
        self.assertEqual(lead_boards.status_label(logik, "terminiert")[0], "Terminiert")
        v = self.lead(801, "terminiert")
        self.termin(v)
        seite = self.client.get("/lead-management/terminiert").text
        self.assertIn("<title>Deals – Lead-Management</title>", seite)
        self.assertIn("<h1>Deals", seite)
        self.assertIn('aria-label="Deals"', seite)
        self.assertNotIn('aria-label="Terminiert"', seite)
        self.assertNotIn("Board Terminiert", seite)
        self.assertNotIn("Board „Terminiert“", seite)
        self.assertNotIn("Terminiert", nav_html(seite))
        self.assertIn('title="Lead-Phase Terminiert">Terminiert</span>', seite)   # Phase bleibt
        # Kanban-Überschrift und Board-Umschalter
        kanban = self.client.get("/lead-management/board?board=terminiert").text
        self.assertIn("Kanban · Deals", kanban)
        self.assertIn('href="/lead-management/board?board=terminiert">Deals</a>', kanban)
        self.assertNotIn("Kanban · Terminiert", kanban)
        # Meldung „Lead liegt jetzt im Board „Deals““ nach Inline-Änderung aus dem Hauptboard
        r = self.json_post(f"/lead-management/boards/zeile/{v.id}",
                           {"feld": "notiz", "wert": "V3B", "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("Board „Deals“", r.json().get("verschoben", ""))
        # Sammelaktions-Redirect nennt nur den Pfad (Key bleibt terminiert)
        self.assertEqual([x["key"] for x in lead_boards.sammelaktionen_fuer("terminiert")], ["hv_verschieben"])   # v29

    def test_infoabend_statt_info_veranstaltung(self):
        lead_info.veranstaltungen_anlegen(self.s)
        self.s.commit()
        naechste = lead_info.naechste_veranstaltung(self.s)
        self.assertIsNotNone(naechste)
        if self.s.query(LeadQuelle).filter_by(key="info_veranstaltung").first() is None:
            kern.quellen_vorbelegen(self.s)
            self.s.commit()
        v = self.lead(811, quelle_key="info_veranstaltung")
        v.veranstaltung_id = naechste.id
        self.s.commit()
        r = self.client.get("/lead-management/info-veranstaltung")
        self.assertEqual(r.status_code, 200)
        seite = r.text
        self.assertIn("<title>Infoabend – Lead-Management</title>", seite)
        self.assertIn("<h1>Infoabend", seite)
        self.assertIn('aria-label="Infoabend"', seite)
        self.assertIn("Infoabend " + naechste.beginn.strftime("%d.%m.%Y"), seite)   # Gruppenüberschrift
        self.assertIn(f"/lead-management/lead/{v.id}", seite)
        self.assertNotIn("<h1>Info-Veranstaltung", seite)
        self.assertNotIn("Info-Veranstaltung –", seite)
        self.assertNotIn("Info-Veranstaltung", nav_html(seite))
        termine = self.client.get("/lead-management/info-veranstaltung/termine").text
        self.assertIn("<h1>Infoabend · Termine", termine)
        # Parameter-Keys und Quelle bleiben
        self.assertEqual(kern.parameter_holen(self.s, "info_uhrzeit"), "18:00")
        self.assertIsNotNone(self.s.query(LeadQuelle).filter_by(key="info_veranstaltung").first())
        # neu angelegte Veranstaltungen tragen den Titel „Infoabend <Datum>“
        neu, meldung = lead_info.veranstaltung_anlegen_manuell(
            self.s, datetime(2031, 3, 6, 18, 0), benutzer=self.admin)
        try:
            self.assertIsNotNone(neu, meldung)
            self.assertEqual(neu.titel, "Infoabend 06.03.2031")
        finally:
            if neu is not None:
                self.s.delete(neu)
            self.s.commit()


# --- 3. Spaltenkonfiguration je Nutzer --------------------------------------------------------

class Spalten(Basis):
    def setUp(self):
        self.reset(self.client)
        self.reset(self.client2)

    def test_standard_ohne_namensspalten_mit_kundenname(self):
        sp = lead_boards.spalten_fuer(self.s, self.zweiter, "hauptboard")
        self.assertEqual([x["key"] for x in sp], STANDARD_KEYS)
        self.assertEqual(sp[0], {"key": "lead", "titel": "Kundenname", "standard": "Kundenname",
                                 "name": "", "sichtbar": True, "breite": None})   # v29: breite je Spalte
        for key in ("anrede", "vorname", "nachname"):
            self.assertFalse(next(x for x in sp if x["key"] == key)["sichtbar"], key)
        self.assertNotIn("score", [x["key"] for x in sp])
        # „Anrede Vorname Nachname“ – Anrede nur wenn gesetzt
        herr = self.lead(901, anrede="Herr")
        ohne = self.lead(902)
        self.assertEqual(lead_boards.kundenname(self.s.get(Kunde, herr.kunde_id)), f"Herr V901 {NACHNAME}-901")
        self.assertEqual(lead_boards.kundenname(self.s.get(Kunde, ohne.kunde_id)), f"V902 {NACHNAME}-902")
        self.assertEqual(lead_boards.kundenname(Kunde(firma="Firma X", vorname="A", nachname="B")), "Firma X (A B)")
        self.assertEqual(lead_boards.kundenname(None), "")
        seite = self.client2.get("/lead-management/hauptboard").text
        kopf = thead_html(seite)
        self.assertIn('<th class="sp-lead"', kopf)
        self.assertIn(">Kundenname</span>", kopf)
        for key in ("anrede", "vorname", "nachname", "score"):
            self.assertNotIn(f'<th class="sp-{key}"', kopf, key)
        self.assertIn(f"Herr V901 {NACHNAME}-901", seite)
        self.assertIn(f">V902 {NACHNAME}-902<", seite)
        # Spaltenwähler: Namensspalten einblendbar (Häkchen leer), Kundenname fest
        self.assertRegex(seite, r'<li data-key="anrede" class="">\s*<label><input type="checkbox" data-key="anrede"\s*>')
        self.assertRegex(seite, r'<li data-key="lead" class="fest">\s*<label><input type="checkbox" data-key="lead" checked disabled>')
        self.assertIn('id="lm-spalten-reset"', seite)
        self.assertIn("Zurücksetzen", seite)
        # einblenden per Spaltenliste (Häkchen) wirkt nur für diesen Nutzer
        liste = [{"key": k, "sichtbar": s or k in ("anrede", "vorname", "nachname"), "name": ""}
                 for k, _, s in lead_boards.SPALTEN]
        r = self.json_post("/lead-management/boards/spalten", {"board": "hauptboard", "spalten": liste}, self.client2)
        self.assertEqual(r.json()["meldung"], "Spalten gespeichert.")
        kopf2 = thead_html(self.client2.get("/lead-management/hauptboard").text)
        self.assertIn('<th class="sp-anrede"', kopf2)
        self.assertNotIn('<th class="sp-anrede"', thead_html(self.client.get("/lead-management/hauptboard").text))

    def test_v23_liste_mit_sichtbaren_namensspalten_bleibt(self):
        # v23 speicherte eine Liste [[key, sichtbar]] – sichtbare Namensspalten bleiben sichtbar
        lead_v2.einstellung_setzen(self.s, self.zweiter.id, KEY, {"hauptboard": [
            ["lead", True], ["anrede", True], ["vorname", True], ["nachname", True], ["status", True],
            ["telefon", False]]})
        self.s.commit()
        sp = lead_boards.spalten_fuer(self.s, self.zweiter.id, "hauptboard")
        self.assertEqual([x["key"] for x in sp][:5], ["lead", "anrede", "vorname", "nachname", "status"])
        self.assertTrue(all(x["sichtbar"] for x in sp[:5]))
        self.assertFalse(next(x for x in sp if x["key"] == "telefon")["sichtbar"])
        self.assertEqual(len(sp), len(STANDARD_KEYS))                      # Rest hängt hinten
        self.assertIsNone(lead_boards.sortierung_fuer(self.s, self.zweiter.id, "hauptboard"))
        self.lead(911)
        kopf = thead_html(self.client2.get("/lead-management/hauptboard").text)
        self.assertIn('<th class="sp-anrede"', kopf)
        self.assertIn('<th class="sp-nachname"', kopf)
        self.assertNotIn('<th class="sp-telefon"', kopf)
        # auch [{key, sichtbar}] und kaputte Einträge werden gelesen
        n = lead_boards._konfig_normieren([{"key": "ort", "sichtbar": False}, ["x"], None, {"sichtbar": True}])
        self.assertEqual(n, {"spalten": [{"key": "ort", "sichtbar": False, "name": "", "breite": None}], "sort": None})
        n = lead_boards._konfig_normieren({"spalten": [{"key": "ort", "name": " Stadt "}],
                                            "sort": {"key": "ort", "richtung": "ab"}})
        self.assertEqual(n["spalten"], [{"key": "ort", "sichtbar": True, "name": "Stadt", "breite": None}])
        self.assertEqual(n["sort"], {"key": "ort", "richtung": "ab"})
        self.assertEqual(lead_boards._konfig_normieren("unsinn"), {"spalten": [], "sort": None})

    def test_zwei_benutzer_verschieben_und_umbenennen(self):
        # Benutzer A verschiebt „Telefon“ an Position 2 und benennt „Notiz“ in „Bemerkung“ um
        a = self.spalten_json(self.client)["spalten"]
        self.assertEqual([x["key"] for x in a], STANDARD_KEYS)
        neu = [x for x in a if x["key"] == "lead"] + [x for x in a if x["key"] == "telefon"] \
            + [x for x in a if x["key"] not in ("lead", "telefon")]
        r = self.json_post("/lead-management/boards/spalten",
                           {"board": "hauptboard",
                            "spalten": [{"key": x["key"], "sichtbar": x["sichtbar"], "name": x["name"]} for x in neu]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["meldung"], "Spalten gespeichert.")
        r = self.json_post("/lead-management/boards/spalten",
                           {"board": "hauptboard", "umbenennen": {"key": "notiz", "name": "Bemerkung"}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["meldung"], "Spalte umbenannt.")
        a2 = self.spalten_json(self.client)["spalten"]
        self.assertEqual([x["key"] for x in a2][:3], ["lead", "telefon", "anrede"])
        notiz = next(x for x in a2 if x["key"] == "notiz")
        self.assertEqual((notiz["titel"], notiz["name"], notiz["standard"]), ("Bemerkung", "Bemerkung", "Notiz"))
        # gespeicherte Struktur (Vertrag v25)
        roh = lead_v2.einstellung_holen(self.s, 1, KEY)["hauptboard"]
        self.assertEqual(set(roh), {"spalten", "sort"})
        self.assertEqual(roh["spalten"][1], {"key": "telefon", "sichtbar": True, "name": ""})
        self.assertEqual(next(x for x in roh["spalten"] if x["key"] == "notiz")["name"], "Bemerkung")
        self.lead(921)
        seite_a = self.client.get("/lead-management/hauptboard").text
        kopf_a = thead_html(seite_a)
        self.assertLess(kopf_a.index('<th class="sp-telefon"'), kopf_a.index('<th class="sp-status"'))
        self.assertIn('data-standard="Notiz" data-name="Bemerkung"', kopf_a)
        self.assertIn(">Bemerkung</span>", kopf_a)
        self.assertNotIn(">Notiz</span>", kopf_a)
        self.assertIn('<span class="lm-sp-name">Bemerkung</span> <small title="Standardname">(Notiz)</small>', seite_a)
        zellen_a = seite_a.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        self.assertLess(zellen_a.index('class="sp-telefon"'), zellen_a.index('class="sp-status"'))
        # Benutzer B sieht den Standard unverändert
        b = self.spalten_json(self.client2)["spalten"]
        self.assertEqual([x["key"] for x in b], STANDARD_KEYS)
        self.assertEqual(next(x for x in b if x["key"] == "notiz")["titel"], "Notiz")
        self.assertTrue(all(x["name"] == "" for x in b))
        seite_b = self.client2.get("/lead-management/hauptboard").text
        kopf_b = thead_html(seite_b)
        self.assertLess(kopf_b.index('<th class="sp-status"'), kopf_b.index('<th class="sp-telefon"'))
        self.assertNotIn("Bemerkung", seite_b)
        # Deals-Board von A bleibt eigenständig (Standardreihenfolge, Spalte Erfassung / Angebot)
        d = lead_boards.spalten_fuer(self.s, self.admin, "terminiert")
        self.assertIn("angebot", [x["key"] for x in d])
        self.assertNotEqual([x["key"] for x in d][1], "telefon")
        self.assertEqual(next(x for x in d if x["key"] == "notiz")["titel"], "Notiz")
        # leerer Name = Standard
        r = self.json_post("/lead-management/boards/spalten",
                           {"board": "hauptboard", "umbenennen": {"key": "notiz", "name": "   "}})
        notiz = next(x for x in r.json()["spalten"] if x["key"] == "notiz")
        self.assertEqual((notiz["titel"], notiz["name"]), ("Notiz", ""))
        # Umbenennen einer Spalte ohne gespeicherten Eintrag (Benutzer B) hält die Reihenfolge
        r = self.json_post("/lead-management/boards/spalten",
                           {"board": "hauptboard", "umbenennen": {"key": "ort", "name": "Stadt"}}, self.client2)
        self.assertEqual([x["key"] for x in r.json()["spalten"]], STANDARD_KEYS)
        self.assertEqual(next(x for x in r.json()["spalten"] if x["key"] == "ort")["titel"], "Stadt")
        # Kundenname bleibt vorn, auch wenn die Liste ihn verschiebt; unbekannte Keys fallen weg
        r = self.json_post("/lead-management/boards/spalten",
                           {"board": "hauptboard", "spalten": [{"key": "ort", "sichtbar": True},
                                                                {"key": "lead", "sichtbar": False},
                                                                {"key": "fremd", "sichtbar": True}]}, self.client2)
        keys = [x["key"] for x in r.json()["spalten"]]
        self.assertEqual(keys[:2], ["lead", "ort"])
        self.assertTrue(r.json()["spalten"][0]["sichtbar"])
        self.assertNotIn("fremd", keys)
        # Fehlerfälle: unbekanntes Board, umbenennen ohne Key, Sortierung kaputt
        self.assertEqual(self.json_post("/lead-management/boards/spalten", {"board": "x", "zuruecksetzen": True}).status_code, 400)
        self.assertEqual(self.json_post("/lead-management/boards/spalten", {"board": "hauptboard", "umbenennen": {"name": "x"}}).status_code, 400)
        self.assertEqual(self.json_post("/lead-management/boards/spalten", {"board": "hauptboard", "sort": "auf"}).status_code, 400)

    def test_sortierung_gemerkt(self):
        jetzt = datetime.now()
        alt = self.lead(931, eingang_am=jetzt - timedelta(days=2))
        neu = self.lead(932, eingang_am=jetzt - timedelta(days=1))
        r = self.json_post("/lead-management/boards/spalten",
                           {"board": "hauptboard", "sort": {"key": "eingang", "richtung": "auf"}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["meldung"], "Sortierung gemerkt.")
        self.assertEqual(r.json()["sort"], {"key": "eingang", "richtung": "auf"})
        self.assertEqual(self.spalten_json(self.client)["sort"], {"key": "eingang", "richtung": "auf"})
        self.assertEqual(lead_boards.sortierung_fuer(self.s, 1, "hauptboard"), {"key": "eingang", "richtung": "auf"})
        seite = self.client.get("/lead-management/hauptboard").text
        self.assertLess(seite.index(f"/lead-management/lead/{alt.id}"), seite.index(f"/lead-management/lead/{neu.id}"))
        self.assertRegex(thead_html(seite), r'data-key="eingang"[^>]*aria-sort="ascending"')
        self.assertIn('"sort": {"key": "eingang", "richtung": "auf"}', seite)     # lm-daten für das JS
        r = self.json_post("/lead-management/boards/spalten",
                           {"board": "hauptboard", "sort": {"key": "eingang", "richtung": "ab"}})
        seite = self.client.get("/lead-management/hauptboard").text
        self.assertLess(seite.index(f"/lead-management/lead/{neu.id}"), seite.index(f"/lead-management/lead/{alt.id}"))
        self.assertRegex(thead_html(seite), r'data-key="eingang"[^>]*aria-sort="descending"')
        # Benutzer B: keine Sortierung gemerkt, Standard (Eingang neueste zuerst)
        self.assertIsNone(self.spalten_json(self.client2)["sort"])
        seite_b = self.client2.get("/lead-management/hauptboard").text
        self.assertNotIn("aria-sort=", thead_html(seite_b))
        self.assertLess(seite_b.index(f"/lead-management/lead/{neu.id}"), seite_b.index(f"/lead-management/lead/{alt.id}"))
        # Sortierung bleibt beim Umbenennen/Verschieben erhalten; sort: null löscht sie
        self.json_post("/lead-management/boards/spalten", {"board": "hauptboard", "umbenennen": {"key": "ort", "name": "Stadt"}})
        self.assertEqual(self.spalten_json(self.client)["sort"]["key"], "eingang")
        r = self.json_post("/lead-management/boards/spalten", {"board": "hauptboard", "sort": None})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(self.spalten_json(self.client)["sort"])
        # unbekannte Sortierspalte wird nicht gemerkt
        self.json_post("/lead-management/boards/spalten", {"board": "hauptboard", "sort": {"key": "unsinn", "richtung": "auf"}})
        self.assertIsNone(self.spalten_json(self.client)["sort"])
        # Sortierhelfer: leere Werte immer ans Ende, Text/Zahl/Datum
        zeilen = [{"kunde": Kunde(nachname="b"), "vorgang": Vorgang(), "eingang": jetzt - timedelta(days=1), "versuche": 2},
                  {"kunde": Kunde(nachname="a"), "vorgang": Vorgang(), "eingang": None, "versuche": 5},
                  {"kunde": Kunde(nachname="c"), "vorgang": Vorgang(), "eingang": jetzt, "versuche": 0}]
        lead_boards.zeilen_sortieren(zeilen, {"key": "eingang", "richtung": "auf"}, jetzt)
        self.assertEqual([z["kunde"].nachname for z in zeilen], ["b", "c", "a"])
        lead_boards.zeilen_sortieren(zeilen, {"key": "versuche", "richtung": "ab"}, jetzt)
        self.assertEqual([z["kunde"].nachname for z in zeilen], ["a", "b", "c"])
        lead_boards.zeilen_sortieren(zeilen, {"key": "lead", "richtung": "auf"}, jetzt)
        self.assertEqual([z["kunde"].nachname for z in zeilen], ["a", "b", "c"])
        # ohne gemerkte Sortierung: Eingang neueste zuerst (Zeilen ohne Eingang zählen wie „jetzt“)
        zeilen[0]["eingang"] = jetzt - timedelta(days=3)
        lead_boards.zeilen_sortieren(zeilen, None, jetzt)
        self.assertEqual([z["kunde"].nachname for z in zeilen], ["c", "b", "a"])

    def test_zuruecksetzen(self):
        self.json_post("/lead-management/boards/spalten",
                       {"board": "hauptboard", "spalten": [{"key": "ort", "sichtbar": True}, {"key": "telefon", "sichtbar": False}]})
        self.json_post("/lead-management/boards/spalten", {"board": "hauptboard", "umbenennen": {"key": "notiz", "name": "Bemerkung"}})
        self.json_post("/lead-management/boards/spalten", {"board": "hauptboard", "sort": {"key": "ort", "richtung": "ab"}})
        vorher = self.spalten_json(self.client)
        self.assertEqual([x["key"] for x in vorher["spalten"]][:2], ["lead", "ort"])
        self.assertIsNotNone(vorher["sort"])
        r = self.json_post("/lead-management/boards/spalten", {"board": "hauptboard", "zuruecksetzen": True})
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        self.assertEqual(j["meldung"], "Spalten zurückgesetzt.")
        self.assertEqual([x["key"] for x in j["spalten"]], STANDARD_KEYS)
        self.assertTrue(all(x["name"] == "" and x["titel"] == x["standard"] for x in j["spalten"]))
        self.assertTrue(next(x for x in j["spalten"] if x["key"] == "telefon")["sichtbar"])
        self.assertFalse(next(x for x in j["spalten"] if x["key"] == "anrede")["sichtbar"])
        self.assertIsNone(j["sort"])
        self.assertEqual(lead_v2.einstellung_holen(self.s, 1, KEY)["hauptboard"], {"spalten": [], "sort": None})
        # Zurücksetzen gilt nur für das Board des Aufrufers: Deals-Konfiguration bleibt
        self.json_post("/lead-management/boards/spalten", {"board": "terminiert", "umbenennen": {"key": "angebot", "name": "Doku"}})
        self.json_post("/lead-management/boards/spalten", {"board": "hauptboard", "zuruecksetzen": True})
        self.assertEqual(next(x for x in self.spalten_json(self.client, "terminiert")["spalten"] if x["key"] == "angebot")["titel"], "Doku")
        self.reset(self.client, "terminiert")

    def test_score_nur_bei_aktivem_scoring(self):
        self.assertFalse(lead_v2.score_aktiv(self.s))
        v = self.lead(941, "in_kontaktierung", score_punkte=42, score_klasse="A")
        kern.aktivitaet(self.s, v.id, "anruf", "Anruf: Erreicht", benutzer=self.admin, ergebnis="erreicht")
        self.s.commit()
        self.assertNotIn("score", [x["key"] for x in lead_boards.spalten_fuer(self.s, 1, "hauptboard")])
        self.assertNotIn("score", [x["key"] for x in self.spalten_json(self.client)["spalten"]])
        self.assertEqual([k for k, _, _ in lead_boards.spalten_basis("terminiert", score=False)],
                         [k for k, _, _ in lead_boards.SPALTEN_TERMINIERT])
        for pfad in ("/lead-management/hauptboard", "/lead-management/terminiert",
                     "/lead-management/board?board=hauptboard", "/lead-management/board?board=terminiert",
                     "/lead-management/kontaktiert?q=" + NACHNAME + "-941"):
            seite = self.client.get(pfad).text
            self.assertIn(f"/lead-management/lead/{v.id}", seite) if "kontaktiert" in pfad or "hauptboard" in pfad else None
            for muster in ("sp-score", 'data-key="score"', "Score-Klasse", 'name="klasse"',
                           "Klasse <strong>", ">Score<", "42 Punkte"):
                self.assertNotIn(muster, seite, (pfad, muster))
        # gemerkte Score-Sortierung ruht, solange der Score aus ist
        kern.parameter_setzen(self.s, "score_aktiv", "an")
        self.s.commit()
        try:
            sp = lead_boards.spalten_fuer(self.s, 1, "hauptboard")
            keys = [x["key"] for x in sp]
            self.assertIn("score", keys)
            self.assertEqual(keys.index("score"), keys.index("status") + 1)
            self.assertIn("score", [x["key"] for x in self.spalten_json(self.client)["spalten"]])
            r = self.json_post("/lead-management/boards/spalten", {"board": "hauptboard", "sort": {"key": "score", "richtung": "ab"}})
            self.assertEqual(r.json()["sort"], {"key": "score", "richtung": "ab"})
            seite = self.client.get("/lead-management/hauptboard").text
            self.assertIn('<th class="sp-score"', seite)
            self.assertIn("Score-Klasse A", seite)
            self.assertIn('name="klasse"', self.client.get("/lead-management/board?board=hauptboard").text)
        finally:
            kern.parameter_setzen(self.s, "score_aktiv", "aus")
            self.s.commit()
        self.assertIsNone(lead_boards.sortierung_fuer(self.s, 1, "hauptboard"))
        self.assertNotIn("sp-score", self.client.get("/lead-management/hauptboard").text)
        self.assertEqual(lead_v2.einstellung_holen(self.s, 1, KEY)["hauptboard"]["sort"]["key"], "score")   # bleibt gespeichert
        self.reset(self.client)

    def test_sticky_filterleiste_und_spaltenwerkzeuge(self):
        self.lead(951)
        seite = self.client.get("/lead-management/hauptboard").text
        i_filter, i_tabellen = seite.index('id="lm-filterblock"'), seite.index('id="lm-tabellen"')
        self.assertLess(i_filter, i_tabellen)
        block = seite[i_filter:i_tabellen]
        for teil in ('id="lm-filterform"', 'id="lm-suche"', 'name="status"', 'name="kanal"',
                     'id="lm-spaltenwahl"', 'id="lm-spaltenliste"', 'id="lm-spalten-reset"',
                     'id="lm-sammelform"', " Spalten</summary>"):
            self.assertIn(teil, block, teil)
        self.assertNotIn('class="tabelle lm-tabelle"', block)     # Tabellen liegen außerhalb des Filterblocks
        self.assertIn('class="tabelle lm-tabelle"', seite[i_tabellen:])
        kopf = thead_html(seite)
        self.assertIn('class="sp-lead" data-sort="lead" data-key="lead"', kopf)
        self.assertRegex(kopf, r'data-key="lead"[^>]*draggable="false"')
        self.assertRegex(kopf, r'data-key="status"[^>]*draggable="true"')
        self.assertIn('class="lm-th-stift" data-key="status"', kopf)
        self.assertIn("Klick sortiert (auf/ab, wird gemerkt)", kopf)
        self.assertIn("Ziehen verschiebt die Spalte", kopf)
        css = (BASIS / "app" / "static" / "lead_v2.css").read_text(encoding="utf-8")
        self.assertIn(".lm-filterblock { position: sticky; top: var(--lm-kopf-fest, 0px);", css)
        self.assertIn(".lm-tabellen { overflow: auto;", css)
        self.assertIn(".lm-tabelle thead th { position: sticky; top: 0;", css)
        self.assertIn(".lm-th-ziel-vor", css)
        self.assertIn(".lm-sp-platzhalter", css)
        js = (BASIS / "app" / "static" / "lm_boards.js").read_text(encoding="utf-8")
        for teil in ("'--lm-kopf'", "'--lm-kopf-fest'", "--lm-tabellen-hoehe", "'dragstart'", "'dragover'", "'drop'",
                     "/lead-management/boards/spalten", "umbenennen:", "zuruecksetzen: true", "sort: { key: key"):
            self.assertIn(teil, js, teil)

    def test_spalten_fuer_benutzer_oder_id_und_infoabend(self):
        mit_objekt = lead_boards.spalten_fuer(self.s, self.hv, "hauptboard")
        mit_id = lead_boards.spalten_fuer(self.s, self.hv.id, "hauptboard")
        self.assertEqual(mit_objekt, mit_id)
        self.assertEqual(mit_objekt[0]["titel"], "Kundenname")
        self.assertEqual(lead_boards.spalten_fuer(self.s, None, "info")[0]["key"], "lead")
        self.assertEqual(lead_boards.KONFIG_BOARDS, ("hauptboard", "terminiert", "info", "handelsvertreter"))
        # Infoabend nutzt die Hauptboard-Spalten des Nutzers (+ Ergebnis, Teilgenommen, Veranstaltung)
        info = lead_info.spalten_fuer(self.s, 1, True)
        self.assertEqual([x["key"] for x in info][:4], ["lead", "status", "ergebnis", "teilgenommen"])
        self.assertEqual(info[0]["titel"], "Kundenname")
        self.assertEqual(info[-1]["key"], "veranstaltung")
        self.assertNotIn("score", [x["key"] for x in info])
        # Handelsvertreter: eigene Spaltenkonfiguration getrennt (v29: Hauptboard für die
        # HV-Sicht gesperrt – die HV-Ansicht nutzt den Board-Key handelsvertreter;
        # Nachtrag 08.10.2026: 303 auf die HV-Ansicht statt 404)
        c_hv = TestClient(app)
        c_hv.post("/login", data={"benutzer_id": str(self.hv.id), "pin": "1234"})
        r = c_hv.get("/lead-management/hauptboard", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/lead-management/handelsvertreter?meldung="))
        self.assertEqual(c_hv.get("/lead-management/handelsvertreter").status_code, 200)
        r = self.json_post("/lead-management/boards/spalten", {"board": "hauptboard", "umbenennen": {"key": "ort", "name": "Stadt"}}, c_hv)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(next(x for x in self.spalten_json(self.client)["spalten"] if x["key"] == "ort")["titel"], "Ort")


# --- 4. Kanban ---------------------------------------------------------------------------------

class Kanban(Basis):
    def test_eine_spalte_kontaktiert(self):
        a = self.lead(961, "in_kontaktierung")
        b = self.lead(962, "qualifiziert")
        c = self.lead(963, "neu")
        self.assertEqual(router.KANBAN_SPALTEN["hauptboard"], ["neu", "kontaktiert"])
        self.assertEqual(router.KANBAN_ZUSAMMEN, {"kontaktiert": ("in_kontaktierung", "qualifiziert")})
        seite = self.client.get("/lead-management/board?board=hauptboard").text
        self.assertIn('data-phase="kontaktiert"', seite)
        self.assertIn('data-phase="neu"', seite)
        for phase in ("in_kontaktierung", "qualifiziert"):
            self.assertNotIn(f'data-phase="{phase}"', seite, phase)
        self.assertIn("<h3>Kontaktiert (", seite)
        self.assertNotIn(">Qualifiziert (", seite)
        self.assertNotIn(">In Kontaktierung (", seite)
        spalten = seite.split('class="kanban-spalte"')
        kontaktiert = next(sp for sp in spalten if 'data-phase="kontaktiert"' in sp)
        neu = next(sp for sp in spalten if 'data-phase="neu"' in sp)
        for v in (a, b):
            self.assertIn(f"/lead-management/lead/{v.id}", kontaktiert)
            self.assertNotIn(f"/lead-management/lead/{v.id}", neu)
        self.assertIn(f"/lead-management/lead/{c.id}", neu)
        self.assertNotIn(f"/lead-management/lead/{c.id}", kontaktiert)
        # Zusammenfassung: Zähler summiert, Karten nach Eingang neueste zuerst
        jetzt = datetime.now()
        k1 = {"vorgang": Vorgang(eingang_am=jetzt - timedelta(days=2))}
        k2 = {"vorgang": Vorgang(eingang_am=jetzt - timedelta(days=1))}
        sp, koepfe = router.kanban_spalten_zusammenfassen(
            {"neu": [], "in_kontaktierung": [k1], "qualifiziert": [k2]},
            {"neu": {"anzahl": 0, "summe": None}, "in_kontaktierung": {"anzahl": 1, "summe": None},
             "qualifiziert": {"anzahl": 1, "summe": None}})
        self.assertEqual(sp["kontaktiert"], [k2, k1])
        self.assertEqual(koepfe["kontaktiert"], {"anzahl": 2, "summe": None})
        self.assertIn("in_kontaktierung", sp)                       # interne Phasen bleiben
        sp, koepfe = router.kanban_spalten_zusammenfassen(
            {"in_kontaktierung": [k1], "qualifiziert": []},
            {"in_kontaktierung": {"anzahl": 1, "summe": 500}, "qualifiziert": {"anzahl": 0, "summe": 250}})
        self.assertEqual(koepfe["kontaktiert"]["summe"], 750)
        # Deals-Kanban unverändert, Seitenzustände weiter zuschaltbar
        deals = self.client.get("/lead-management/board?board=terminiert").text
        for phase in ("terminiert", "erfasst", "angebot", "gewonnen", "verloren"):
            self.assertIn(f'data-phase="{phase}"', deals, phase)
        self.assertNotIn('data-phase="kontaktiert"', deals)
        seiten = self.client.get("/lead-management/board?board=hauptboard&seiten=1").text
        self.assertIn('data-phase="zurueckgestellt"', seiten)
        self.assertIn('data-phase="kontaktiert"', seiten)


# --- 5. Phasen-Labels aus dem Blatt Status -----------------------------------------------------

class Labels(Basis):
    def test_kontaktiert_fuer_beide_kontaktphasen(self):
        logik = leadmanagement_logik.hole_logik()
        labels = lead_boards.phasen_labels(logik)
        self.assertEqual(set(labels), set(LEAD_PHASEN))
        self.assertEqual(labels["in_kontaktierung"], "Kontaktiert")
        self.assertEqual(labels["qualifiziert"], "Kontaktiert")
        self.assertEqual(labels["neu"], "Neu")
        self.assertEqual(logik.status_zeile("qualifiziert").label, "Kontaktiert")
        self.assertEqual(lead_boards.status_label(logik, "in_kontaktierung"),
                         lead_boards.status_label(logik, "qualifiziert"))
        self.assertEqual(lead_boards.phasen_mit_label(logik, "qualifiziert"), {"in_kontaktierung", "qualifiziert"})
        self.assertEqual(lead_boards.phasen_mit_label(logik, "neu"), {"neu"})
        self.assertEqual(lead_boards.phasen_mit_label(logik, ""), set())
        a = self.lead(971, "in_kontaktierung")
        b = self.lead(972, "qualifiziert")
        kern.aktivitaet(self.s, b.id, "anruf", "Anruf: Erreicht", benutzer=self.admin, ergebnis="erreicht")
        self.s.commit()
        daten = lead_boards.board_zeilen(self.s, self.admin, "hauptboard", {"q": NACHNAME + "-97"})
        zeilen = {z["vorgang"].id: z for g in daten["gruppen"] for z in g["zeilen"]}
        self.assertEqual(zeilen[a.id]["status_label"], "Kontaktiert")
        self.assertEqual(zeilen[b.id]["status_label"], "Kontaktiert")
        self.assertEqual(zeilen[a.id]["status_farbe"], zeilen[b.id]["status_farbe"])
        # Status-Filter trifft beide Phasen desselben Labels
        for status in ("in_kontaktierung", "qualifiziert"):
            daten = lead_boards.board_zeilen(self.s, self.admin, "hauptboard", {"status": status, "q": NACHNAME + "-97"})
            self.assertEqual({z["vorgang"].id for g in daten["gruppen"] for z in g["zeilen"]}, {a.id, b.id}, status)
        # Auswahllisten: Label nur einmal, zweite Phase als „doppelt“ markiert
        wahl = {s["key"]: s for s in lead_boards.auswahl_listen(self.s)["status_wahl"]}
        self.assertFalse(wahl["in_kontaktierung"]["doppelt"])
        self.assertTrue(wahl["qualifiziert"]["doppelt"])
        self.assertEqual(wahl["qualifiziert"]["gleiche"], ["in_kontaktierung"])
        seite = self.client.get("/lead-management/hauptboard").text
        for alt in (">Qualifiziert<", ">In Kontaktierung<", "Lead-Phase Qualifiziert", "Lead-Phase In Kontaktierung"):
            self.assertNotIn(alt, seite, alt)
        filter_select = seite.split('<select name="status">', 1)[1].split("</select>", 1)[0]
        self.assertEqual(filter_select.count(">Kontaktiert</option>"), 1)
        self.assertIn('value="in_kontaktierung"', filter_select)
        self.assertNotIn('value="qualifiziert"', filter_select)
        # Inline-Select eines qualifizierten Leads: „Kontaktiert“ genau einmal (= aktueller Wert)
        zeile_b = seite.split(f'<tr data-vorgang="{b.id}"', 1)[1].split("</tr>", 1)[0]
        select_b = zeile_b.split('data-feld="status"', 1)[1].split("</select>", 1)[0]
        self.assertEqual(select_b.count(">Kontaktiert</option>"), 1)
        self.assertIn('value="qualifiziert" data-grund="" selected', select_b)
        self.assertNotIn('value="in_kontaktierung"', select_b)
        self.assertIn('title="Lead-Phase Kontaktiert">Kontaktiert</span>', zeile_b)
        # Reiter Kontaktiert: Abzeichen aus dem Blatt Status
        kontaktiert = self.client.get("/lead-management/kontaktiert?q=" + NACHNAME + "-972").text
        self.assertIn('<span class="abzeichen">Kontaktiert</span>', kontaktiert)
        self.assertNotIn(">Qualifiziert<", kontaktiert)
        # Kanban-Spaltenkopf trägt dasselbe Label
        self.assertIn("<h3>Kontaktiert (", self.client.get("/lead-management/board").text)
        # Zuordnung Phase → Board → Gruppe bleibt unverändert
        tabelle = {z["phase"]: (z["board"], z["gruppe"], z["label"]) for z in lead_boards.zuordnung_tabelle(logik)}
        self.assertEqual(tabelle["in_kontaktierung"], ("hauptboard", "neu", "Kontaktiert"))
        self.assertEqual(tabelle["qualifiziert"], ("hauptboard", "neu", "Kontaktiert"))
        self.assertEqual(tabelle["terminiert"], ("terminiert", "angebotserstellung", "Terminiert"))


if __name__ == "__main__":
    unittest.main()
