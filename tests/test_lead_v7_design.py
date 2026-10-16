# Tests v37 (PLAN_LEAD_V7 Phasen 196/197, Agent L1): Kartei-Review (kein Badge „monday“, kein
# SLA-Chip im Kopf, Notizblock mit „Senden“/„Diktieren“ rechts neben dem Textfeld) und Design v3
# des Lead-Moduls (Wrapper <body data-modul="lead"> nur für Lead-Seiten, Token-Block in
# lead_v2.css mit den Kontrollwerten des Plans, Dunkelwerte in beiden Mechaniken, keine festen
# Farben in Lead-Templates/-CSS, Badge „PV vorhanden“ über --sparte-pvv, Angebotstool/Kalender
# bleiben Design v2) sowie eine Chrome-headless-Prüfung (DevTools) des Notizblock-Rasters bei
# 1366 px und 390 px und der Kontrollwerte Seite #F6F8FA · Karte 12 px · Primärbutton #2F72B5 ·
# Schrift 14 px · Dunkelmodus #0F1A26. Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE); Testdaten
# tragen den Nachnamen-Präfix „V37L1“ und werden aufgeräumt.
import json
import re
import time
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, darstellung
from app import leadmanagement as kern
from app import objekte as objekte_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Benachrichtigung, BenutzerEinstellung, KommunikationLog, Kunde, LeadAktivitaet,
                        LeadQuelle, Todo, Vorgang, VorgangObjekt, VorgangsNotiz, VotTermin)

NACHNAME = "V37L1"
PROJEKT = Path(__file__).resolve().parents[1]
STATIC = PROJEKT / "app" / "static"
TEMPLATES = PROJEKT / "app" / "templates"
LEAD_CSS = STATIC / "lead_v2.css"
HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
V3_ANFANG, V3_ENDE = "/* v3-tokens-anfang */", "/* v3-tokens-ende */"
LEAD_CSS_DATEIEN = ["lead_v2.css", "lead_v29.css", "lm_v35_b.css", "lm_v35_k.css", "lm_v35_r.css", "lm_v35_t.css",
                    "lead_v37_l2.css", "lead_v37_l3.css"]


def _block(text: str, anfang: str) -> str:
    i = text.index(anfang)
    i = text.index("{", i) + 1
    tiefe, j = 1, i
    while tiefe:
        if text[j] == "{":
            tiefe += 1
        elif text[j] == "}":
            tiefe -= 1
        j += 1
    return text[i:j - 1]


def _tokens(block: str) -> dict[str, str]:
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", block)}


def _v3() -> str:
    text = LEAD_CSS.read_text(encoding="utf-8")
    return text.split(V3_ANFANG, 1)[1].split(V3_ENDE, 1)[0]


def _ohne_v3(text: str) -> str:
    if V3_ANFANG not in text:
        return text
    vor, rest = text.split(V3_ANFANG, 1)
    return vor + rest.split(V3_ENDE, 1)[1]


def _fest(zeilen, i) -> bool:
    return "fest:" in zeilen[i] or (i > 0 and "fest:" in zeilen[i - 1])


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangObjekt).filter_by(vorgang_id=v.id).delete()
            s.query(Todo).filter_by(vorgang_id=v.id).delete()
            s.query(Benachrichtigung).filter(Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            s.delete(v)
        s.delete(k)
    s.commit()


def _einstellung_loeschen(benutzer_id: int) -> None:
    s = SessionLocal()
    try:
        s.query(BenutzerEinstellung).filter(BenutzerEinstellung.benutzer_id == benutzer_id,
                                            BenutzerEinstellung.key == darstellung.KEY).delete()
        s.commit()
    finally:
        s.close()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app, follow_redirects=False)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def lead(self, nr, eingang_art="monday", **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"anrede": "Herr", "vorname": f"Demo{nr}", "nachname": f"{NACHNAME}-Muster-{nr}",
                 "strasse": "Beispielweg 1", "plz": "47269", "ort": "Duisburg",
                 "telefon": f"0203 5559{nr:03d}", "email": f"v37l1-{nr}@beispiel.de", "sparten": ["WP"]}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        vorgang.demo = True
        vorgang.eingang_art = eingang_art
        kunde = self.s.get(Kunde, vorgang.kunde_id)
        kunde.vertriebskanal = "Enni"
        kunde.objektart = "EFH"
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        self.s.query(VorgangObjekt).filter_by(vorgang_id=vorgang.id).delete()
        objekte_modul.hauptobjekt(self.s, vorgang.id, anlegen=True)
        self.s.commit()
        return vorgang

    def kartei(self, vorgang, **params):
        url = f"/lead-management/lead/{vorgang.id}"
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, url)
        return r.text


# --- (a) Phase 196: Kartei-Review --------------------------------------------------------------

class A_KarteiReview(Basis):
    def test_a_kopf_ohne_monday_badge_und_ohne_sla_chip(self):
        v = self.lead(1, eingang_art="monday")
        seite = self.kartei(v)
        kopf = seite.split('<header class="karte lk-kopf', 1)[1].split("</header>", 1)[0]
        self.assertNotIn('<span class="abzeichen">monday</span>', kopf)
        self.assertNotIn(">monday</span>", kopf)
        self.assertNotIn("sla-chip", seite)
        self.assertNotIn("SLA:", kopf)
        # die Quelle bleibt: Eingangszeile im Kopf (Text + Tooltip) und Kundeninfo-Block
        self.assertIn('title="Eingangsdatum · monday"', kopf)
        self.assertIn("(monday)", kopf)
        info = seite.split('id="lk-kundeninfo"', 1)[1].split('id="lk-verlauf"', 1)[0]
        self.assertIn("(monday)", info)
        # Rest der Kopfzeile bleibt: Phasenkette, Versuche, Pflichtfeld-Zähler, Schnellaktionen,
        # Terminierung, Nachbearbeitung, Vorgangsakte
        for text in ('class="lk-statuskette"', "Versuche:", 'id="lk-pflicht-zaehler"', 'class="lk-schnell"',
                     'id="lk-terminierung-knopf"', "Nachbearbeitung", "Vorgangsakte", "Eingang "):
            self.assertIn(text, kopf, text)
        # Template-Regel: keine Badge-Zeile mehr, kein SLA-Zweig
        quelle = (TEMPLATES / "leadmanagement" / "kartei.html").read_text(encoding="utf-8")
        self.assertNotIn("""{% if vorgang.eingang_art == 'monday' %}<span class="abzeichen">monday</span>""", quelle)
        self.assertNotIn("lead_kontext.sla", quelle)
        # SLA bleibt in der Anrufliste
        self.assertIn("sla-chip", (TEMPLATES / "leadmanagement" / "anrufliste.html").read_text(encoding="utf-8"))

    def test_b_notizblock_markup_und_raster(self):
        v = self.lead(2)
        seite = self.kartei(v)
        oben = seite.split('id="lk-oben"', 1)[1].split('id="lk-kundeninfo"', 1)[0]
        notizen = oben.split('<section class="karte lk-notizen"', 1)[1].split("</section>", 1)[0]
        self.assertIn('class="notiz-eingabe chat-eingabe nc-eingabe"', notizen)
        self.assertIn("<textarea", notizen)
        self.assertIn('rows="4"', notizen)                       # mindestens 3 Zeilen, wächst mit (Makro-JS)
        self.assertIn('<button class="knopf" type="submit">Senden</button>', notizen)
        self.assertIn("diktat-knopf", notizen)
        self.assertIn("Diktieren", notizen)
        self.assertIn("Diktat: bitte das Mikrofon Ihrer Handy-Tastatur verwenden", notizen)
        pos = [notizen.index(m) for m in ("<textarea", ">Senden<", "diktat-knopf", "Handy-Tastatur")]
        self.assertEqual(pos, sorted(pos), "Textfeld → Senden → Diktieren → Hinweis")
        self.assertIn('id="lk-todos"', oben, "To-Dos bleiben rechts daneben (v31)")
        # Raster in lead_v2.css (Phase 196): Textfeld Spalte 1 über drei Zeilen, Knöpfe Spalte 2
        css = LEAD_CSS.read_text(encoding="utf-8")
        block = css.split("Phase 196", 1)[1]
        self.assertIn(".lk-v5 .lk-notizen .nc-eingabe { display: grid; grid-template-columns: minmax(0, 1fr) minmax(136px, max-content)", block)
        self.assertIn("textarea { grid-column: 1; grid-row: 1 / span 3; width: 100%;", block)
        self.assertIn(".lk-v5 .lk-notizen .nc-eingabe > .knopf { grid-column: 2; grid-row: 1;", block)
        self.assertIn(".lk-v5 .lk-notizen .nc-eingabe .diktat-block { grid-column: 2; grid-row: 2; display: flex; flex-direction: column;", block)
        self.assertIn("min-height: calc(3 * 1.45em + 16px)", block)
        mobil = block.split("@media (max-width: 900px)", 1)[1]
        self.assertIn("textarea { grid-column: 1 / -1; grid-row: 1; }", mobil)
        self.assertIn("> .knopf { grid-column: 1; grid-row: 2; }", mobil)
        self.assertIn(".diktat-block { grid-column: 2; grid-row: 2; }", mobil)
        # das Makro bleibt allgemein (Vorgangsakte, Projektakte, Montage) – keine Kartei-Klasse darin
        self.assertNotIn("lk-notizen", (TEMPLATES / "_komponenten.html").read_text(encoding="utf-8"))


# --- (b) Phase 197: Wrapper nur für das Lead-Modul -----------------------------------------------

class B_Wrapper(Basis):
    def test_a_lead_seiten_mit_wrapper_andere_ohne(self):
        v = self.lead(3)
        mit = ["/lead-management/hauptboard", "/lead-management/terminiert", "/lead-management/dashboard",
               "/lead-management/todos", "/lead-management/karte", "/lead-management/vorlagen",
               "/lead-management/anrufliste", "/lead-management/kontaktiert", "/lead-management/info-veranstaltung",
               "/lead-management/handelsvertreter", "/lead-management/kanaele", "/lead-management/kalender?alt=1",
               f"/lead-management/lead/{v.id}", f"/lead-management/lead/{v.id}/termin",
               "/parametrierung/lead-einstellungen", "/parametrierung/lead-routing"]
        ohne = ["/", "/angebote", "/erfassungen", "/kunden", "/leads", "/kalender", "/vorgaenge",
                f"/vorgaenge/{v.id}", "/parametrierung"]
        for pfad in mit:
            r = self.client.get(pfad)
            self.assertEqual(r.status_code, 200, pfad)
            self.assertIn('<body data-modul="lead"', r.text, pfad)
        for pfad in ohne:
            r = self.client.get(pfad)
            self.assertEqual(r.status_code, 200, pfad)
            self.assertNotIn("data-modul=", r.text, f"{pfad} bleibt Design v2")

    def test_b_regel_in_base_html(self):
        quelle = (TEMPLATES / "base.html").read_text(encoding="utf-8")
        self.assertIn("request.url.path.startswith('/lead-management')", quelle)
        self.assertIn("request.url.path.startswith('/parametrierung/lead-')", quelle)
        self.assertIn("lead_modul | default(false)", quelle)
        self.assertIn('<body{% if lead_modul %} data-modul="lead"{% endif %}', quelle)
        self.assertIn("lead_v2.css", quelle)


# --- (c) Phase 197: Tokens, Kontrollwerte, Wächter ------------------------------------------------

class C_TokensUndWaechter(unittest.TestCase):
    def setUp(self):
        self.v3 = _v3()
        self.hell = _tokens(_block(self.v3, '[data-modul="lead"] {'))
        self.schrift = _tokens(_block(self.v3, '[data-modul="lead"] main {'))
        self.dunkel = _tokens(_block(self.v3, ':root[data-theme="dunkel"] [data-modul="lead"] {'))
        self.media = _tokens(_block(self.v3, ':root:not([data-theme="hell"]) [data-modul="lead"] {'))

    def test_a_kontrollwerte_hell(self):
        erwartet = {"--flaeche": "#f6f8fa", "--flaeche-karte": "#ffffff", "--akzent": "#2f72b5", "--akzent-hover": "#245c95",
                    "--lm3-akzent-hell": "#4489c9", "--akzent-flaeche": "#e3edf7", "--lm3-akzent-linie": "#8db4de",
                    "--text": "#0e2338", "--lm3-text-zweit": "#33414f", "--text-dezent": "#687186", "--linie": "#dce4eb",
                    "--lm3-feld": "#eef1f5", "--flaeche-abgesetzt": "#ecf0f5", "--lm3-orange": "#ffa500",
                    "--lm3-orange-text": "#a85400", "--lm3-orange-flaeche": "#fff1d6", "--r-s": "8px", "--r-m": "12px",
                    "--r-l": "14px", "--lm3-r-kachel": "18px", "--schatten-1": "0 1px 4px rgba(0, 0, 0, 0.08)",
                    "--lm-aktiv-bg": "var(--akzent)", "--lm-aktiv-fg": "var(--akzent-text)"}
        for name, wert in erwartet.items():
            self.assertEqual(self.hell.get(name), wert, name)
        self.assertEqual(self.schrift["--t-m"], "14px")
        self.assertEqual(self.schrift["--t-s"], "13px")
        self.assertEqual(self.schrift["--t-xs"], "12px")
        self.assertEqual(self.schrift["--lm3-t-klein"], "11px")
        self.assertEqual(self.schrift["--t-l"], "16px")
        self.assertEqual(self.schrift["--lm3-t-h2"], "18px")
        self.assertEqual(self.schrift["--t-xl"], "22px")
        self.assertEqual(self.schrift["--lm3-t-kennzahl"], "32px")
        self.assertIn('"Inter", "Open Sans", system-ui', self.schrift["--lm3-schrift"])
        self.assertEqual(self.schrift["--schrift"], "var(--lm3-schrift)")
        # keine Webfont-Datei und kein @font-face aus dem Netz (v14-Regel)
        text = LEAD_CSS.read_text(encoding="utf-8")
        self.assertNotIn("@import", text)
        self.assertNotIn("fonts.googleapis", text)

    def test_b_dunkel_abgeleitet_in_beiden_mechaniken(self):
        erwartet = {"--flaeche": "#0f1a26", "--flaeche-karte": "#16243a", "--linie": "#2a3b52", "--text": "#e8eef5",
                    "--text-dezent": "#9aa8ba", "--akzent": "#2f72b5", "--akzent-text": "#ffffff", "--link": "#8db4de",
                    "--lm3-orange": "#ffa500", "--lm3-orange-flaeche": "#3a2a0e", "--sparte-pvv": None}
        for name, wert in erwartet.items():
            if wert is None:
                continue
            self.assertEqual(self.dunkel.get(name), wert, name)
            self.assertEqual(self.media.get(name), wert, f"{name} im Geräte-Block")
        self.assertEqual(self.dunkel, self.media)
        for name, wert in self.hell.items():
            if wert.startswith("#") or wert.startswith("rgba("):
                self.assertIn(name, self.dunkel, f"Dunkelwert fehlt: {name}")
        pvv_hell = _tokens(_block(self.v3, ":root {"))
        pvv_dunkel = _tokens(_block(self.v3, ':root[data-theme="dunkel"] {'))
        pvv_media = _tokens(_block(self.v3, ':root:not([data-theme="hell"]) {'))
        self.assertEqual(pvv_hell["--sparte-pvv"], "#1f7a72")
        self.assertEqual(pvv_dunkel["--sparte-pvv"], "#6fd6c8")
        self.assertEqual(pvv_dunkel, pvv_media)

    def test_c_keine_festen_farben_in_lead_templates_und_css(self):
        verstoesse = []
        dateien = sorted((TEMPLATES / "leadmanagement").glob("*.html")) + sorted((TEMPLATES / "konfiguration").glob("lead_*.html"))
        dateien += [TEMPLATES / "base.html", TEMPLATES / "_komponenten.html", TEMPLATES / "_nav.html"]
        for datei in dateien:
            if not datei.exists():
                continue
            zeilen = datei.read_text(encoding="utf-8").split("\n")
            for i, zeile in enumerate(zeilen):
                if HEX.search(zeile) and not _fest(zeilen, i):
                    verstoesse.append(f"{datei.name}:{i + 1}")
        for name in LEAD_CSS_DATEIEN:
            datei = STATIC / name
            self.assertTrue(datei.exists(), name)
            zeilen = _ohne_v3(datei.read_text(encoding="utf-8")).split("\n")
            for i, zeile in enumerate(zeilen):
                if HEX.search(zeile) and not _fest(zeilen, i):
                    verstoesse.append(f"{name}:{i + 1}: {zeile.strip()[:60]}")
        self.assertEqual(verstoesse, [], "feste Farben ohne „fest:“:\n" + "\n".join(verstoesse))
        # Hex-Werte liegen ausschließlich im v3-Token-Block
        self.assertGreater(len(HEX.findall(self.v3)), 60)

    def test_d_badge_pv_vorhanden_ueber_sparte_pvv(self):
        l3 = (STATIC / "lead_v37_l3.css").read_text(encoding="utf-8")
        self.assertIn(".chip-pvv { --chip-farbe: var(--sparte-pvv", l3)
        self.assertIn(".abzeichen.interesse-pvv { --chip-farbe: var(--sparte-pvv", l3)
        self.assertNotIn(".chip-pvv { --chip-farbe: var(--status-grau); }", l3)

    def test_e_regeln_fuer_dashboard_boards_kartei(self):
        css = LEAD_CSS.read_text(encoding="utf-8").split("Phase 197", 1)[1]
        for regel in ('@media (min-width: 1200px) { [data-modul="lead"] .lm-dash-kacheln-v4 { grid-template-columns: repeat(3, minmax(0, 1fr)); } }',
                      'border-radius: var(--lm3-r-kachel)',
                      '.stat-zahl { font-size: var(--lm3-t-kennzahl); font-weight: 800;',
                      '[data-modul="lead"] .lm-tabelle td, [data-modul="lead"] .hv-tabelle td { height: 40px;',
                      '[data-modul="lead"] .lk-tab { border-radius: 999px;',
                      '[data-modul="lead"] .lmt-ideal-badge { background: var(--lm3-orange); color: var(--lm3-orange-text-auf);',
                      '[data-modul="lead"] .lk-vorschlag.lk-ideal, [data-modul="lead"] .lmt-vorschlag.lmt-ideal { border: 2px solid var(--lm3-orange);',
                      '[data-modul="lead"] .lk-anruf-knoepfe { display: grid;',
                      'min-height: 44px;',
                      '[data-modul="lead"] .lm-filterblock .lm-suchleiste',
                      '[data-modul="lead"] main { font-family: var(--lm3-schrift); font-size: var(--t-m);'):
            self.assertIn(regel, css, regel)
        # Kopfzeile bleibt v2: keine Regel für .kopfleiste im v3-Block, --flaeche-erhoeht nicht überschrieben
        self.assertNotIn(".kopfleiste", css)
        self.assertNotIn("--flaeche-erhoeht:", self.v3)
        self.assertNotIn("--text-invers:", self.v3)

    def test_f_tojson_nur_mit_forceescape_in_lead_templates(self):
        for datei in sorted((TEMPLATES / "leadmanagement").glob("*.html")):
            text = datei.read_text(encoding="utf-8")
            for treffer in re.findall(r'\son[a-z]+="([^"]*)"', text):
                if "tojson" in treffer:
                    self.assertIn("forceescape", treffer, f"{datei.name}: {treffer[:80]}")


# --- (d) Chrome headless: Notizblock-Raster und Kontrollwerte (DevTools, Muster test_lead_v7_kanaele_interessen) ---

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT, CDP = 8144, 9354


class D_ImBrowser(Basis):
    @classmethod
    def setUpClass(cls):
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
        cls.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning", lifespan="off"))
        cls.thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.thread.start()
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/login", timeout=1)
                break
            except Exception:   # noqa: BLE001
                time.sleep(0.5)
        cls.profil = Path(tempfile.mkdtemp(prefix="chrome_v37_l1_"))
        cls.chrome = subprocess.Popen(
            [CHROME, "--headless=new", f"--remote-debugging-port={CDP}", f"--user-data-dir={cls.profil}",
             "--window-size=1366,900", "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
             "--no-first-run", "--disable-gpu", "about:blank"],
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
        shutil.rmtree(getattr(cls, "profil", Path(tempfile.gettempdir()) / "chrome_v37_l1_leer"), ignore_errors=True)
        _einstellung_loeschen(1)
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
                            if "error" in antwort:
                                return {"error": antwort["error"]}
                            return antwort.get("result", {})

                async def oeffnen(pfad, mobil=False, schema="light"):
                    # Chrome headless folgt dem Farbschema des Systems – für reproduzierbare Messungen wird
                    # prefers-color-scheme ausdrücklich emuliert (hell; „dark“ prüft die Geräte-Mechanik)
                    antwort = await senden("Emulation.setEmulatedMedia", media="",
                                           features=[{"name": "prefers-color-scheme", "value": schema}])
                    if "error" in antwort:
                        fehler.append("setEmulatedMedia: " + json.dumps(antwort["error"])[:200])
                    # frische Cookies je Aufruf – das Cookie „darstellung“, das der Server nach einer Wahl
                    # setzt, darf nicht in den nächsten Test hineinwirken
                    await senden("Network.clearBrowserCookies")
                    await senden("Network.setCookie", name=auth.COOKIE_NAME, value=auth.cookie_wert(1), url=basis)
                    breite, hoehe = (390, 844) if mobil else (1366, 900)
                    await senden("Emulation.setDeviceMetricsOverride", width=breite, height=hoehe,
                                 deviceScaleFactor=2 if mobil else 1, mobile=mobil)
                    await senden("Page.navigate", url=basis + pfad)
                    await asyncio.sleep(1.6)

                async def js(ausdruck):
                    r = await senden("Runtime.evaluate", expression=ausdruck, returnByValue=True, awaitPromise=True)
                    if "exceptionDetails" in r:
                        fehler.append(json.dumps(r["exceptionDetails"])[:400])
                    return r.get("result", {}).get("value")

                await senden("Network.enable")
                await senden("Runtime.enable")
                await senden("Page.enable")
                await schritte(oeffnen, js)

        asyncio.run(lauf())
        return fehler

    MESSUNG = """(function(){
        var f=document.querySelector('.lk-notizen .nc-eingabe'); var ta=f.querySelector('textarea');
        var s=f.querySelector('button[type=submit]'); var d=f.querySelector('.diktat-knopf');
        var r=function(e){var b=e.getBoundingClientRect();return {l:b.left,r:b.right,t:b.top,b:b.bottom,w:b.width,h:b.height};};
        var cs=getComputedStyle; var main=document.querySelector('main');
        return {ta:r(ta), s:r(s), d:r(d), form:r(f), grid:cs(f).display, body_bg:cs(document.body).backgroundColor,
                main_font:cs(main).fontSize, font_family:cs(main).fontFamily, knopf_bg:cs(s).backgroundColor,
                knopf_radius:cs(s).borderRadius, karte_radius:cs(document.querySelector('div.lk-terminierung.karte')).borderRadius,
                tab_radius:cs(document.querySelector('.lk-tab')).borderRadius, modul:document.body.getAttribute('data-modul'),
                theme:document.documentElement.getAttribute('data-theme')||'', h1_font:cs(document.querySelector('.lk-name')).fontSize,
                prefers_dark:matchMedia('(prefers-color-scheme: dark)').matches};
    })()"""

    def test_notizblock_raster_und_kontrollwerte(self):
        v = self.lead(9)
        ergebnis = {}
        pfad = f"/lead-management/lead/{v.id}"

        async def schritte(oeffnen, js):
            await oeffnen(pfad)
            ergebnis["desktop"] = await js(self.MESSUNG)
            await oeffnen(pfad, mobil=True)
            ergebnis["mobil"] = await js(self.MESSUNG)

        fehler = self._lauf(schritte)
        self.assertEqual(fehler, [], fehler)
        d = ergebnis["desktop"]
        self.assertEqual(d["modul"], "lead")
        self.assertEqual(d["grid"], "grid")
        # Textfeld links über die volle Restbreite, Knöpfe rechts daneben: Senden über Diktieren
        self.assertLessEqual(d["ta"]["r"], d["s"]["l"] + 1, d)
        self.assertLessEqual(d["ta"]["r"], d["d"]["l"] + 1, d)
        self.assertGreater(d["ta"]["w"], 0.6 * d["form"]["w"], d)
        self.assertGreaterEqual(d["ta"]["h"], 3 * 14 * 1.45, "mindestens 3 Zeilen")
        self.assertLess(d["s"]["t"], d["d"]["t"], "Senden über Diktieren")
        self.assertGreaterEqual(d["d"]["t"], d["s"]["b"] - 1, "untereinander, nicht nebeneinander")
        # Kontrollwerte des Plans (Hellmodus): Seite #F6F8FA, Karte 12 px, Primärbutton #2F72B5, Schrift 14 px
        self.assertFalse(d["prefers_dark"], d)
        self.assertEqual(d["body_bg"], "rgb(246, 248, 250)", d)
        self.assertEqual(d["karte_radius"], "12px")
        self.assertEqual(d["knopf_bg"], "rgb(47, 114, 181)")
        self.assertEqual(d["knopf_radius"], "8px")
        self.assertEqual(d["main_font"], "14px")
        self.assertEqual(d["h1_font"], "22px")
        self.assertIn("Inter", d["font_family"])
        self.assertEqual(d["tab_radius"], "999px")
        self.assertEqual(d["theme"], "")
        # 390 px: Textfeld oben über die volle Breite, darunter beide Knöpfe nebeneinander
        m = ergebnis["mobil"]
        self.assertGreaterEqual(m["s"]["t"], m["ta"]["b"] - 1, m)
        self.assertGreaterEqual(m["d"]["t"], m["ta"]["b"] - 1, m)
        self.assertLess(abs(m["s"]["t"] - m["d"]["t"]), 3, "Knöpfe nebeneinander")
        self.assertLessEqual(m["s"]["r"], m["d"]["l"] + 1, m)
        self.assertGreater(m["ta"]["w"], 0.9 * m["form"]["w"], m)

    def test_dunkelmodus_beide_mechaniken(self):
        """Ausdrückliche Wahl „dunkel“ (data-theme vor dem Rendern) und „Gerät entscheidet“ mit
        dunklem Farbschema liefern dieselben v3-Werte; „Gerät“ mit hellem Schema bleibt hell."""
        v = self.lead(10)
        pfad = f"/lead-management/lead/{v.id}"
        ergebnis = {}
        try:
            async def geraet(oeffnen, js):
                await oeffnen(pfad, schema="dark")
                ergebnis["geraet_dunkel"] = await js(self.MESSUNG)
                await oeffnen(pfad, schema="light")
                ergebnis["geraet_hell"] = await js(self.MESSUNG)
            fehler = self._lauf(geraet)
            self.assertEqual(fehler, [], fehler)
            self.assertEqual(self.client.post("/einstellungen/darstellung", json={"wert": "dunkel"}).status_code, 200)

            async def gewaehlt(oeffnen, js):
                await oeffnen(pfad, schema="light")
                ergebnis["gewaehlt_dunkel"] = await js(self.MESSUNG)
            fehler = self._lauf(gewaehlt)
        finally:
            self.client.post("/einstellungen/darstellung", json={"wert": "geraet"})
            _einstellung_loeschen(1)
        self.assertEqual(fehler, [], fehler)
        g = ergebnis["geraet_dunkel"]
        self.assertEqual(g["theme"], "")                    # keine Wahl: Media-Block entscheidet
        self.assertEqual(g["body_bg"], "rgb(15, 26, 38)")   # Seite #0F1A26
        self.assertEqual(ergebnis["geraet_hell"]["body_bg"], "rgb(246, 248, 250)")
        d = ergebnis["gewaehlt_dunkel"]
        self.assertEqual(d["theme"], "dunkel")              # vor dem Rendern am <html> (Middleware)
        self.assertEqual(d["body_bg"], "rgb(15, 26, 38)")
        self.assertEqual(d["knopf_bg"], "rgb(47, 114, 181)", "Blau unverändert")
        self.assertEqual(d["main_font"], "14px")
        self.assertEqual(d["karte_radius"], "12px")


if __name__ == "__main__":
    unittest.main()
