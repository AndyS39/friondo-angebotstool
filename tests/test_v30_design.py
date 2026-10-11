# Tests v30 (PLAN_V18 Phasen 145/146/152, Agent D1): Design v2 – Token-Wächter,
# Gleichheit von Dunkel- und Media-Block, data-theme aus Cookie/Einstellung
# (Middleware + POST /einstellungen/darstellung), Kontrast der Token-Paare
# (WCAG-Luminanz, ≥ 4,5 : 1 bzw. ≥ 3 : 1 dezent) in beiden Modi, Makros
# status_badge/avatar, Portal-Begrüßung und „PDF unverändert“ (kein Token-Zugriff
# aus dem fpdf2-Code, Angebots-PDF zweimal gerendert byteidentisch).
# Läuft gegen die Entwicklungs-DB (DB_PFAD_OVERRIDE); Einstellungen des
# Testbenutzers werden am Ende zurückgesetzt.
import ast
import datetime
import re
import tempfile
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, darstellung
from app.db import SessionLocal
from app.main import app
from app.models import Angebot, Benutzer, BenutzerEinstellung, Kunde
from app.templating import templates

PROJEKT = Path(__file__).resolve().parents[1]
STATIC = PROJEKT / "app" / "static"
TEMPLATES = PROJEKT / "app" / "templates"
STYLE = STATIC / "style.css"
HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
TOKEN_ENDE = "* { box-sizing: border-box; }"
PDF_MODULE = ["pdf_export", "protokoll_pdf", "lieferschein_pdf", "bza_datenblatt",
              "wirtschaftlichkeit_pdf", "steckbrief_pdf"]
TOKEN_PAARE_TEXT = [          # (Vordergrund, Hintergrund) ≥ 4,5 : 1
    ("--text", "--flaeche"), ("--text", "--flaeche-karte"), ("--text", "--flaeche-abgesetzt"),
    ("--text", "--flaeche-hover"), ("--text-titel", "--flaeche"), ("--text-titel", "--flaeche-karte"),
    ("--text-invers", "--flaeche-erhoeht"), ("--akzent-text", "--akzent"), ("--akzent-text", "--akzent-hover"),
    ("--link", "--flaeche-karte"), ("--link", "--flaeche"),
    ("--text-auf-farbe", "--status-rot"), ("--text-auf-farbe", "--status-gruen"),
    ("--text-auf-farbe", "--status-orange"), ("--text-auf-farbe", "--status-blau"),
    ("--text-auf-farbe", "--status-grau"), ("--text-auf-farbe", "--status-violett"),
    ("--sparte-wp", "--flaeche-karte"), ("--sparte-pv", "--flaeche-karte"),
    ("--sparte-kl", "--flaeche-karte"), ("--sparte-wb", "--flaeche-karte"),
] + [(f"--status-{f}", f"--status-{f}-bg") for f in ("gruen", "orange", "rot", "blau", "grau", "violett")]
TOKEN_PAARE_DEZENT = [        # ≥ 3 : 1
    ("--text-dezent", "--flaeche"), ("--text-dezent", "--flaeche-karte"), ("--text-dezent", "--flaeche-abgesetzt"),
    ("--akzent", "--flaeche-karte"), ("--fokus", "--flaeche"),
] + [(f"--avatar-{n}", "--flaeche-karte") for n in range(1, 9)] + [(f"--avatar-text", f"--avatar-{n}") for n in range(1, 9)]


# --- Hilfen -----------------------------------------------------------------------
def _style_teile() -> tuple[str, str]:
    text = STYLE.read_text(encoding="utf-8")
    kopf, rest = text.split(TOKEN_ENDE, 1)
    return kopf, rest


def _block(text: str, anfang: str) -> str:
    """Inhalt der ersten geschweiften Klammer nach `anfang`."""
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


def _hex_zu_rgb(wert: str) -> tuple[float, float, float]:
    wert = wert.strip().lstrip("#")
    if len(wert) == 3:
        wert = "".join(c * 2 for c in wert)
    return tuple(int(wert[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _luminanz(rgb) -> float:
    def kanal(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (kanal(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def kontrast(vorder: str, hinter: str) -> float:
    l1, l2 = _luminanz(_hex_zu_rgb(vorder)), _luminanz(_hex_zu_rgb(hinter))
    hell, dunkel = max(l1, l2), min(l1, l2)
    return (hell + 0.05) / (dunkel + 0.05)


def _aufloesen(tokens: dict, name: str, tiefe: int = 0) -> str:
    wert = tokens[name]
    m = re.fullmatch(r"var\((--[\w-]+)\)", wert)
    if m and tiefe < 5:
        return _aufloesen(tokens, m.group(1), tiefe + 1)
    return wert


def _fest_erlaubt(zeilen: list[str], i: int) -> bool:
    return "fest:" in zeilen[i] or (i > 0 and "fest:" in zeilen[i - 1])


def _benutzer(rolle: str) -> Benutzer:
    s = SessionLocal()
    try:
        b = s.query(Benutzer).filter(Benutzer.rolle == rolle, Benutzer.aktiv.is_(True)).order_by(Benutzer.id).first()
        assert b is not None, f"kein aktiver Benutzer mit Rolle {rolle}"
        return b
    finally:
        s.close()


def _einstellung_loeschen(benutzer_id: int) -> None:
    s = SessionLocal()
    try:
        s.query(BenutzerEinstellung).filter(BenutzerEinstellung.benutzer_id == benutzer_id,
                                            BenutzerEinstellung.key == darstellung.KEY).delete()
        s.commit()
    finally:
        s.close()


def _theme(html: str) -> str | None:
    m = re.search(r'<html lang="de"(?: data-theme="(\w+)")?>', html)
    assert m, "kein <html>-Tag"
    return m.group(1)


# --- (a) Token-Wächter ---------------------------------------------------------------
class TokenWaechter(unittest.TestCase):
    def test_keine_hex_farben_in_css_ausserhalb_der_token_bloecke(self):
        verstoesse = []
        for datei in sorted(STATIC.glob("*.css")):
            text = datei.read_text(encoding="utf-8")
            if datei.name == "style.css":
                kopf, rest = _style_teile()
                versatz = kopf.count("\n")
                zeilen = rest.split("\n")
            else:
                versatz, zeilen = 0, text.split("\n")
            for i, zeile in enumerate(zeilen):
                if HEX.search(zeile) and not _fest_erlaubt(zeilen, i):
                    verstoesse.append(f"{datei.name}:{versatz + i + 1}: {zeile.strip()[:80]}")
        self.assertEqual(verstoesse, [], "Hex-Farben außerhalb der Token-Blöcke ohne „fest:“:\n" + "\n".join(verstoesse))

    def test_keine_hex_farben_in_templates(self):
        verstoesse = []
        for datei in sorted(TEMPLATES.rglob("*.html")):
            zeilen = datei.read_text(encoding="utf-8").split("\n")
            for i, zeile in enumerate(zeilen):
                if HEX.search(zeile) and not _fest_erlaubt(zeilen, i):
                    verstoesse.append(f"{datei.relative_to(TEMPLATES)}:{i + 1}: {zeile.strip()[:80]}")
        self.assertEqual(verstoesse, [], "Hex-Farben in Templates ohne „fest:“:\n" + "\n".join(verstoesse))

    def test_symbole_ohne_feste_fuellfarben(self):
        text = (TEMPLATES / "_symbole.html").read_text(encoding="utf-8")
        for attribut in re.findall(r'(?:fill|stroke)="([^"]+)"', text):
            self.assertIn(attribut, ("none", "currentColor"), attribut)

    def test_fest_ausnahmen_dokumentiert(self):
        """Jede „fest:“-Ausnahme (Kommentar /* fest: … */, {# fest: … #}, // fest: …) trägt einen
        Grund mit mindestens zwei Wörtern."""
        marker = re.compile(r"(?:/\*|\{#|//)\s*fest:(.*)")
        gefunden = 0
        for datei in list(STATIC.glob("*.css")) + list(TEMPLATES.rglob("*.html")):
            for zeile in datei.read_text(encoding="utf-8").split("\n"):
                m = marker.search(zeile)
                if m:
                    gefunden += 1
                    grund = m.group(1).replace("*/", "").replace("#}", "").strip()
                    self.assertTrue(len(grund.split()) >= 2, f"{datei.name}: Grund fehlt: {zeile.strip()}")
        self.assertGreater(gefunden, 3)


# --- (b) Dunkel- und Media-Block identisch ------------------------------------------
class TokenBloecke(unittest.TestCase):
    def setUp(self):
        self.kopf, _ = _style_teile()

    def test_drei_bloecke_vorhanden(self):
        self.assertIn(":root {", self.kopf)
        self.assertIn(':root[data-theme="dunkel"]', self.kopf)
        self.assertIn("@media (prefers-color-scheme: dark)", self.kopf)
        self.assertIn(':root:not([data-theme="hell"])', self.kopf)

    def test_dunkel_und_media_block_gleich(self):
        dunkel = _tokens(_block(self.kopf, ':root[data-theme="dunkel"]'))
        media = _tokens(_block(self.kopf, ':root:not([data-theme="hell"])'))
        self.assertGreater(len(dunkel), 40)
        self.assertEqual(sorted(dunkel), sorted(media), "Token-Namen der beiden Dunkel-Blöcke weichen ab")
        unterschiede = {k: (dunkel[k], media[k]) for k in dunkel if dunkel[k] != media[k]}
        self.assertEqual(unterschiede, {})

    def test_dunkel_block_definiert_alle_semantischen_tokens_des_hell_blocks(self):
        hell = _tokens(_block(self.kopf, ":root {"))
        dunkel = _tokens(_block(self.kopf, ':root[data-theme="dunkel"]'))
        for name in ("--flaeche", "--flaeche-karte", "--flaeche-erhoeht", "--flaeche-hover", "--flaeche-abgesetzt",
                     "--linie", "--linie-stark", "--text", "--text-dezent", "--text-titel", "--text-invers", "--link",
                     "--akzent", "--akzent-hover", "--akzent-text", "--akzent-flaeche", "--akzent-glanz", "--fokus",
                     "--schatten-1", "--schatten-2", "--text-auf-farbe", "--sparte-wp", "--avatar-1", "--avatar-text"):
            self.assertIn(name, hell, name)
            self.assertIn(name, dunkel, name)
        for name in hell:
            if name.startswith(("--status-", "--q-", "--pj-")) and name not in ("--pj-surface", "--pj-accent"):
                self.assertIn(name, dunkel, f"{name} fehlt im Dunkel-Block")
        # Aliase bleiben erhalten (Bestand)
        for alias in ("--friondo-blau", "--friondo-blau-dunkel", "--friondo-blau-hell", "--friondo-dunkel",
                      "--grau-hell", "--grau-linie", "--g-50", "--g-700"):
            self.assertIn(alias, hell, alias)

    def test_keine_doppelten_root_bloecke_unterhalb(self):
        _, rest = _style_teile()
        self.assertNotIn(":root {", rest, "alter :root-Block unterhalb der Token-Blöcke")
        self.assertNotIn("--q-website: #", rest)
        self.assertNotIn("--pj-surface: #", rest)


# --- (d) Kontrast der Token-Paare ---------------------------------------------------
class Kontrast(unittest.TestCase):
    def setUp(self):
        kopf, _ = _style_teile()
        hell = _tokens(_block(kopf, ":root {"))
        dunkel = dict(hell)
        dunkel.update(_tokens(_block(kopf, ':root[data-theme="dunkel"]')))
        self.modi = {"hell": hell, "dunkel": dunkel}

    def _pruefen(self, paare, minimum):
        verstoesse = []
        for modus, tokens in self.modi.items():
            for vorder, hinter in paare:
                v, h = _aufloesen(tokens, vorder), _aufloesen(tokens, hinter)
                self.assertTrue(v.startswith("#") and h.startswith("#"), f"{modus}: {vorder}/{hinter} nicht als Hex auflösbar ({v}/{h})")
                wert = kontrast(v, h)
                if wert < minimum:
                    verstoesse.append(f"{modus}: {vorder} auf {hinter} = {wert:.2f} : 1 (< {minimum})")
        self.assertEqual(verstoesse, [], "\n".join(verstoesse))

    def test_text_auf_flaechen_mindestens_4_5(self):
        self._pruefen(TOKEN_PAARE_TEXT, 4.5)

    def test_dezenter_text_mindestens_3(self):
        self._pruefen(TOKEN_PAARE_DEZENT, 3.0)

    def test_rechenweg_wcag(self):
        self.assertAlmostEqual(kontrast("#ffffff", "#000000"), 21.0, places=2)
        self.assertAlmostEqual(kontrast("#777777", "#ffffff"), 4.48, places=2)
        self.assertEqual(kontrast("#fff", "#ffffff"), 1.0)

    def test_theme_color_entspricht_tokens(self):
        hell, dunkel = self.modi["hell"], self.modi["dunkel"]
        self.assertEqual(darstellung.THEME_COLOR["hell"], _aufloesen(hell, "--flaeche-erhoeht"))
        self.assertEqual(darstellung.THEME_COLOR["dunkel"], _aufloesen(dunkel, "--flaeche"))


# --- (c) data-theme aus Cookie bzw. Einstellung -------------------------------------
class DataTheme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = _benutzer("admin")
        _einstellung_loeschen(cls.admin.id)

    @classmethod
    def tearDownClass(cls):
        _einstellung_loeschen(cls.admin.id)

    def client(self, benutzer_id=None) -> TestClient:
        c = TestClient(app, raise_server_exceptions=True, follow_redirects=False)
        if benutzer_id:
            c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
        return c

    def test_login_ohne_cookie_ohne_attribut_mit_cookie_dunkel(self):
        c = self.client()
        r = c.get("/login")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(_theme(r.text))
        self.assertEqual(r.text.count('name="theme-color"'), 2, "bei Gerät zwei theme-color-Einträge mit Media-Query")
        c.cookies.set(darstellung.COOKIE, "dunkel")
        r = c.get("/login")
        self.assertEqual(_theme(r.text), "dunkel")
        self.assertIn(f'content="{darstellung.THEME_COLOR["dunkel"]}"', r.text)
        c.cookies.set(darstellung.COOKIE, "hell")
        self.assertEqual(_theme(c.get("/login").text), "hell")
        c.cookies.set(darstellung.COOKIE, "quatsch")
        self.assertIsNone(_theme(c.get("/login").text))

    def test_einstellung_je_benutzer_ueberstimmt_cookie_und_setzt_cookie_nach(self):
        _einstellung_loeschen(self.admin.id)
        c = self.client(self.admin.id)
        r = c.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(_theme(r.text))
        self.assertIn("darstellung-chip", r.text)
        self.assertIn("navigation.js", r.text)
        r = c.post("/einstellungen/darstellung", json={"wert": "dunkel"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["darstellung"], "dunkel")
        self.assertIn("darstellung=dunkel", r.headers.get("set-cookie", ""))
        s = SessionLocal()
        try:
            self.assertEqual(darstellung.lesen(s, self.admin.id), "dunkel")
        finally:
            s.close()
        self.assertEqual(_theme(c.get("/").text), "dunkel")
        # Cookie „hell“ (anderer Browser = frischer Client ohne das Server-Cookie) wird durch
        # die Einstellung überstimmt, die Antwort zieht das Cookie nach
        c2 = self.client(self.admin.id)
        c2.cookies.set(darstellung.COOKIE, "hell")
        r = c2.get("/angebote")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(_theme(r.text), "dunkel")
        self.assertIn("darstellung=dunkel", r.headers.get("set-cookie", ""))
        # ohne Cookie (neuer Browser) ebenfalls dunkel + Cookie gesetzt
        c3 = self.client(self.admin.id)
        r = c3.get("/")
        self.assertEqual(_theme(r.text), "dunkel")
        self.assertIn("darstellung=dunkel", r.headers.get("set-cookie", ""))
        # zurück auf „Gerät“: kein Attribut mehr, Cookie geraet
        r = c.post("/einstellungen/darstellung", json={"wert": "geraet"})
        self.assertEqual(r.json()["darstellung"], "geraet")
        self.assertIn("darstellung=geraet", r.headers.get("set-cookie", ""))
        self.assertIsNone(_theme(c.get("/").text))
        # unbekannter Wert → Gerät mit Hinweis
        r = c.post("/einstellungen/darstellung", json={"wert": "neon"})
        self.assertEqual(r.json()["darstellung"], "geraet")
        self.assertTrue(r.json()["hinweis"])

    def test_formular_ohne_javascript_leitet_zurueck(self):
        c = self.client(self.admin.id)
        r = c.post("/einstellungen/darstellung", data={"darstellung": "hell"},
                   headers={"referer": "http://testserver/angebote?status=Versendet"})
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/angebote?status=Versendet")
        self.assertIn("darstellung=hell", r.headers.get("set-cookie", ""))
        c.post("/einstellungen/darstellung", json={"wert": "geraet"})

    def test_alle_rollen_duerfen_umschalten(self):
        s = SessionLocal()
        try:
            benutzer = s.query(Benutzer).filter(Benutzer.aktiv.is_(True)).all()
            ids = {}
            for b in benutzer:
                ids.setdefault(b.rolle, b.id)
        finally:
            s.close()
        for rolle, bid in ids.items():
            c = self.client(bid)
            r = c.post("/einstellungen/darstellung", json={"wert": "hell"})
            self.assertEqual(r.status_code, 200, rolle)
            _einstellung_loeschen(bid)

    def test_ohne_anmeldung_keine_speicherung(self):
        c = self.client()
        r = c.post("/einstellungen/darstellung", json={"wert": "dunkel"})
        self.assertIn(r.status_code, (303, 401, 403))


# --- Bausteine: Makros, Portal, Seiten in beiden Modi -------------------------------
class Bausteine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = _benutzer("admin")
        cls.env = templates.env

    def test_status_badge_pille_mit_punkt(self):
        t = self.env.from_string('{% from "_komponenten.html" import status_badge %}{{ status_badge("Versendet") }}')
        html = t.render()
        self.assertIn('class="abzeichen status-versendet"', html)
        self.assertIn("abzeichen-punkt", html)
        self.assertIn("Versendet", html)
        self.assertIn("status-angenommen", self.env.from_string(
            '{% from "_komponenten.html" import status_badge %}{{ status_badge("Erledigt (extern)") }}').render().replace("status-erledigt", "status-angenommen"))

    def test_avatar_initialen_und_farbe_aus_id(self):
        t = self.env.from_string('{% from "_komponenten.html" import avatar %}{{ avatar(name, id) }}')
        html = t.render(name="René Gerner", id=17)
        self.assertIn('class="avatar avatar-2"', html)     # 17 % 8 + 1
        self.assertIn(">RG<", html)
        self.assertIn('title="René Gerner"', html)
        self.assertIn(">AS<", t.render(name="Andreas Scheelen", id=0))
        self.assertIn(">?<", t.render(name="", id=None))
        self.assertIn("avatar-1", t.render(name="", id=None))
        self.assertIn(">MA<", t.render(name="Max", id=3))            # ein Wort → zwei Buchstaben
        self.assertIn("avatar-4", t.render(name="Max", id=3))
        self.assertEqual(t.render(name="Anna Lena Berg", id=8), t.render(name="Anna Lena Berg", id=16))

    def test_portal_begruessung_vorname_datum_kw(self):
        c = TestClient(app, raise_server_exceptions=True, follow_redirects=False)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(self.admin.id))
        r = c.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("portal-begruessung", r.text)
        self.assertRegex(r.text, r"Guten (Morgen|Tag|Abend)")
        jetzt = datetime.datetime.now()
        self.assertIn(f"KW {jetzt.isocalendar()[1]}", r.text)
        self.assertIn(jetzt.strftime("%d.%m.%Y"), r.text)
        vorname = (self.admin.vorname or self.admin.name.split(" ")[0]).strip()
        self.assertIn(f", {vorname}", r.text)
        self.assertIn("portal-karten", r.text)       # drei Bereiche wie bisher
        self.assertNotIn("Willkommen bei Friondo", r.text)

    def test_gruss_nach_uhrzeit(self):
        t = self.env.get_template("index.html")
        quelle = (TEMPLATES / "index.html").read_text(encoding="utf-8")
        self.assertIn("stunde < 11", quelle)
        self.assertIn("stunde < 18", quelle)
        self.assertIsNotNone(t)

    def test_seiten_in_beiden_modi(self):
        """Kernseiten des Angebotstools rendern mit Cookie hell und dunkel (data-theme korrekt)."""
        s = SessionLocal()
        try:
            angebot = (s.query(Angebot).filter(Angebot.archiviert.is_(False), Angebot.vorgang_id.isnot(None))
                       .order_by(Angebot.id.desc()).first())
        finally:
            s.close()
        pfade = ["/", "/angebotstool", "/angebote", "/erfassungen", "/leads", "/statistik", "/parametrierung",
                 "/parametrierung/betrieb", "/parametrierung/fehlerprotokoll", "/benutzer", "/kunden", "/artikel"]
        if angebot:
            pfade += [f"/angebote/{angebot.id}", f"/vorgaenge/{angebot.vorgang_id}"]
        try:
            for modus in ("hell", "dunkel"):
                c = TestClient(app, raise_server_exceptions=True, follow_redirects=False)
                c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(self.admin.id))
                # angemeldet zählt die gespeicherte Wahl (Middleware), nicht das Cookie allein
                self.assertEqual(c.post("/einstellungen/darstellung", json={"wert": modus}).status_code, 200)
                for pfad in pfade:
                    r = c.get(pfad)
                    self.assertEqual(r.status_code, 200, f"{modus} {pfad}")
                    self.assertEqual(_theme(r.text), modus, pfad)
                    self.assertIn("style.css", r.text)
        finally:
            _einstellung_loeschen(self.admin.id)

    def test_fehlerseite_und_leerzustand(self):
        t = self.env.get_template("fehler.html")
        self.assertIn("fehler-seite", (TEMPLATES / "fehler.html").read_text(encoding="utf-8"))
        self.assertIsNotNone(t)
        css = STYLE.read_text(encoding="utf-8")
        for klasse in (".fehler-seite", ".leer-zustand", ".avatar", ".abzeichen-punkt", ".kachel.stat::before",
                       ".portal-begruessung", ".darstellung-chip.aktiv", ".zurueck-knopf", ".wartung-banner"):
            self.assertIn(klasse, css, klasse)


# --- (e) PDF unverändert -------------------------------------------------------------
class PdfUnveraendert(unittest.TestCase):
    def test_pdf_module_ohne_templates_und_tokens(self):
        """Die fpdf2-Module lesen weder style.css noch importieren sie templating/darstellung."""
        for name in PDF_MODULE:
            pfad = PROJEKT / "app" / f"{name}.py"
            self.assertTrue(pfad.exists(), name)
            quelle = pfad.read_text(encoding="utf-8")
            self.assertNotIn("style.css", quelle, name)
            self.assertNotIn("var(--", quelle, name)
            baum = ast.parse(quelle)
            for knoten in ast.walk(baum):
                if isinstance(knoten, ast.Import):
                    namen = [a.name for a in knoten.names]
                elif isinstance(knoten, ast.ImportFrom):
                    namen = [f"{knoten.module or ''}.{a.name}" for a in knoten.names]
                else:
                    continue
                for n in namen:
                    self.assertNotIn("templating", n, f"{name} importiert {n}")
                    self.assertNotIn("darstellung", n, f"{name} importiert {n}")
                    self.assertNotIn("jinja", n.lower(), f"{name} importiert {n}")

    def test_montage_formular_pdfs_ohne_templates(self):
        for pfad in (PROJEKT / "app").glob("*.py"):
            quelle = pfad.read_text(encoding="utf-8")
            if "from fpdf import" not in quelle and "import fpdf" not in quelle:
                continue
            self.assertNotIn("style.css", quelle, pfad.name)
            self.assertNotIn("from app.templating", quelle, pfad.name)
            self.assertNotIn("from app import templating", quelle, pfad.name)

    def test_angebots_pdf_zweimal_byteidentisch(self):
        from app import angebotsprofile, pdf_export
        s = SessionLocal()
        try:
            angebot = (s.query(Angebot).filter(Angebot.extern.is_(False), Angebot.archiviert.is_(False))
                       .order_by(Angebot.id.desc()).first())
            if angebot is None:
                self.skipTest("kein Angebot in der Datenbank")
            kunde = s.get(Kunde, angebot.kunde_id)
            ergebnisse = []
            with tempfile.TemporaryDirectory() as ordner:
                for lauf in (1, 2):
                    ziel = Path(ordner) / f"kontrolle_{lauf}.pdf"
                    pdf_export.erzeuge_pdf(
                        angebot, kunde, pdf_export._kfw_ergebnis_fuer(s, angebot),
                        mit_vollmacht=pdf_export._mit_vollmacht(s, angebot), ziel=ziel,
                        vortext_text=angebotsprofile.vortext_fuer_angebot(s, angebot),
                        nachtext_text=angebotsprofile.nachtext_fuer_angebot(s, angebot),
                        ersetzt_hinweis=pdf_export._ersetzt_hinweis(s, angebot),
                        wirtschaftlichkeit=pdf_export.wirtschaftlichkeit_fuer(s, angebot))
                    daten = ziel.read_bytes()
                    daten = re.sub(rb"/CreationDate\s*\([^)]*\)", b"", daten)
                    daten = re.sub(rb"/ModDate\s*\([^)]*\)", b"", daten)
                    daten = re.sub(rb"/ID\s*\[[^\]]*\]", b"", daten)
                    ergebnisse.append(daten)
            self.assertEqual(ergebnisse[0], ergebnisse[1], "Angebots-PDF nicht reproduzierbar")
            self.assertGreater(len(ergebnisse[0]), 10_000)
        finally:
            s.close()


if __name__ == "__main__":
    unittest.main()
