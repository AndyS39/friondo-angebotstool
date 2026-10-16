"""v36 (PLAN_V22 Phase 188): Angebots-PDF aus Jinja2-HTML-Vorlagen per Browser-Druck.

Engine „html“: die Vorlagen unter app/templates/pdf/angebot/ werden mit dem Kontext aus app/pdf_kontext.py zu
HTML gerendert (alle Bilder/Schriften als file://-Pfade unter app/static/pdf/, keine externen Quellen), in einen
Temp-Ordner geschrieben und mit Playwright gedruckt – Browser: Edge (`channel="msedge"`, auf dem Windows Server
vorhanden), überschreibbar per `.env PDF_BROWSER_PFAD`, Rückfall Playwright-Chromium. Ein Browser-Prozess je
Dienst (Start beim ersten PDF, Neustart nach Fehler), höchstens PARALLEL gleichzeitige Drucke, TIMEOUT_S je PDF.
Der Druck läuft außerhalb der Datenbanksitzung (`angebot_pdf` gibt die Verbindung nach dem Kontext frei) und in
einem eigenen Thread mit Ereignisschleife (Playwright-Async-API – die Routen laufen im Threadpool).

Fehler lösen `PdfDruckFehler` aus; `pdf_export.pdf_fuer_angebot` (Phase 190) fällt dann auf fpdf2 zurück und
nennt den Grund in der Versand-Meldung. Schalter: Einstellung `pdf_engine` = html | fpdf2 (`engine(session)`).

Ergänzungen v36 Phase 190 (Agent A3, Kern unverändert): `browser_test(sparte, vollstaendig=)` druckt auf
Wunsch das Demo-Angebot über die Sparten-Vorlage und liefert die PDF-Bytes (Knopf „Test-PDF erzeugen“),
`letzten_test_merken`/`letzter_test` (Einstellung `pdf_letzter_test` → Go-live-Punkt, /health),
`dateien_pruefen` (Bilder/Schriften), `protokollieren`/`protokoll` (Einstellung `pdf_protokoll`),
`migration_v36_pdf_engine` (migrate.py-Hook: fpdf2, solange der Browser-Test fehlschlägt),
`html_rendern(..., static_url=)`/`angebot_html(..., static_url=)` für die HTML-Vorschau über HTTP.
"""
from __future__ import annotations

import asyncio
import atexit
import logging
import os
import threading
import time
import uuid
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import config

log = logging.getLogger("angebotstool.pdf")

APP = Path(__file__).resolve().parent
TEMPLATES = APP / "templates"
STATIC = APP / "static"
STATIC_URL = STATIC.as_uri()                       # file:///C:/.../app/static
TEMP_ORDNER = Path(config.DATA_ORDNER) / "tmp" / "pdf" if hasattr(config, "DATA_ORDNER") else APP.parent / "data" / "tmp" / "pdf"

ENGINE_HTML = "html"
ENGINE_FPDF2 = "fpdf2"
ENGINE_STANDARD = ENGINE_HTML
EINSTELLUNG_ENGINE = "pdf_engine"
EINSTELLUNG_DAUER = "pdf_letzte_druckdauer_ms"
# v36 Phase 190 (Agent A3): Ergebnis des letzten Browser-Tests (JSON, Go-live-Punkt + Parametrierung) und
# Änderungsprotokoll der Parametrierung „Angebots-PDF“ (letzte PROTOKOLL_MAX Zeilen, wie heizreport_protokoll)
EINSTELLUNG_LETZTER_TEST = "pdf_letzter_test"
EINSTELLUNG_PROTOKOLL = "pdf_protokoll"
PROTOKOLL_MAX = 30
ENGINE_NAMEN = {ENGINE_HTML: "HTML-Vorlagen + Browser-Druck (Layout v3)",
                ENGINE_FPDF2: "fpdf2 (bisheriges Layout, Rückfall)"}
# Dateien, die die Vorlagen brauchen (Parametrierung „Angebots-PDF“ meldet fehlende): Bilder relativ zu
# app/static/pdf/ (Quelle: pdf_kontext.SPARTEN/ZERTIFIKATE + feste Bilder) und die Nunito-Sans-Schrift
BILDER_FEST = ("bilder/logo.jpg", "bilder/award-2026.png", "bilder/team.jpg", "bilder/kfw.png")
SCHRIFTEN_ERWARTET = ("fonts/nunito-sans/nunito-sans.css", "fonts/nunito-sans/OFL.txt",
                      "fonts/nunito-sans/nunito-sans-latin.woff2",
                      "fonts/nunito-sans/nunito-sans-latin-ext.woff2")

PARALLEL = 2            # höchstens zwei gleichzeitige Drucke
TIMEOUT_S = 30          # je PDF
RAND_OBEN_MM = 10       # Randzone der Browser-Kopfzeile (identisch mit @page in angebot.css)
ZIELZEIT_S = 3.0        # Zielwert: WP-Angebot mit 25 Positionen


class PdfDruckFehler(RuntimeError):
    """Browser-Druck fehlgeschlagen (Browser fehlt, Absturz, Zeitüberschreitung) – Aufrufer nutzen fpdf2."""


# ----------------------------------------------------------------------------- Jinja
_env: Environment | None = None


def jinja_env() -> Environment:
    """Eigene Jinja-Umgebung für die PDF-Vorlagen (Filter euro/menge/de_datum der Web-Templates, autoescape)."""
    global _env
    if _env is None:
        env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]),
                          trim_blocks=False, lstrip_blocks=False)
        try:
            from app.templating import templates as web
            for name in ("euro", "menge", "de_datum", "de_datum_zeit"):
                if name in web.env.filters:
                    env.filters[name] = web.env.filters[name]
        except Exception:   # pragma: no cover – ohne Web-Templates (Skripte)
            pass
        env.globals["static"] = STATIC_URL
        _env = env
    return _env


def html_rendern(vorlage: str, kontext: dict, static_url: str | None = None, **extra) -> str:
    """Rendert eine Vorlage unter app/templates (z. B. „pdf/angebot/wp.html“) mit `kontext`.
    v36 Phase 190: `static_url` überschreibt die file://-Adresse – die HTML-Vorschau im Browser
    (GET /angebote/<id>/pdf.html) lädt Stylesheets/Bilder über den Web-Mount „/static“."""
    return jinja_env().get_template(vorlage).render(kontext=kontext, static=static_url or STATIC_URL,
                                                   **extra)


def vorlage_fuer(sparte: str) -> str:
    sparte = (sparte or "WP").upper()
    if sparte not in ("WP", "PV", "KL", "WB"):
        sparte = "WP"
    return f"pdf/angebot/{sparte.lower()}.html"


def vorlage_vorhanden(sparte: str) -> bool:
    """Liegt die Sparten-Vorlage (Phase 189, Agent A1) schon unter app/templates/pdf/angebot/?"""
    return (TEMPLATES / vorlage_fuer(sparte)).is_file()


def kopfzeile_html(kontext: dict) -> str:
    """Browser-Kopfvorlage auf allen Seiten: Angebot-Nr. · Kundenname links, SEITE x VON y rechts (7 pt, Grau,
    Systemschrift – Kopfvorlagen laden keine Webfonts); sitzt in der 10-mm-Randzone."""
    from html import escape
    nummer = escape(str(kontext.get("angebot", {}).get("nummer", "")))
    kunde = escape(str(kontext.get("kunde", {}).get("name", "")))
    links = f"Angebot-Nr. {nummer}" + (f" · {kunde}" if kunde else "")
    return (
        "<div style=\"width:100%;box-sizing:border-box;padding:0 16mm;margin-top:3.5mm;font-family:'Segoe UI',Arial,sans-serif;"
        "font-size:7pt;color:#6b6f85;display:flex;justify-content:space-between;-webkit-print-color-adjust:exact;\">"
        f"<span>{links}</span>"
        "<span style=\"letter-spacing:0.08em;\">SEITE <span class=\"pageNumber\"></span> VON <span class=\"totalPages\"></span></span>"
        "</div>")


# ----------------------------------------------------------------------------- Drucker (Playwright, eigener Thread)
class _Drucker:
    """Ein Browser je Prozess, bedient aus einem eigenen Thread mit asyncio-Schleife."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()
        self._pw = None
        self._browser = None
        self._sem: asyncio.Semaphore | None = None
        self.browser_pfad = ""
        self.browser_version = ""
        self.browser_kanal = ""
        self.letzte_dauer_ms = 0
        self.anzahl = 0
        self.fehler_anzahl = 0
        self.letzter_fehler = ""
        self.neustarts = 0

    # --- Thread/Schleife
    def _schleife(self) -> asyncio.AbstractEventLoop:
        with self._start_lock:
            if self._loop is None:
                loop = asyncio.new_event_loop()

                def laufen() -> None:
                    asyncio.set_event_loop(loop)
                    loop.run_forever()

                t = threading.Thread(target=laufen, name="pdf-drucker", daemon=True)
                t.start()
                self._loop, self._thread = loop, t
            return self._loop

    async def _browser_holen(self):
        if self._browser is not None and self._browser.is_connected():
            return self._browser
        from playwright.async_api import async_playwright
        if self._pw is None:
            self._pw = await async_playwright().start()
        if self._sem is None:
            self._sem = asyncio.Semaphore(PARALLEL)
        args = ["--allow-file-access-from-files", "--disable-gpu"]
        versuche = []
        pfad = (getattr(config, "PDF_BROWSER_PFAD", "") or "").strip()
        if pfad:
            versuche.append(("pfad", {"executable_path": pfad}))
        versuche.append(("msedge", {"channel": "msedge"}))
        versuche.append(("chromium", {}))
        fehler = []
        for kanal, opts in versuche:
            try:
                self._browser = await self._pw.chromium.launch(headless=True, args=args, **opts)
                self.browser_kanal = kanal
                self.browser_pfad = pfad if kanal == "pfad" else kanal
                self.browser_version = self._browser.version
                log.info("PDF-Browser gestartet: %s %s", kanal, self.browser_version)
                return self._browser
            except Exception as e:   # noqa: BLE001 – nächster Kandidat
                fehler.append(f"{kanal}: {str(e).splitlines()[0][:160]}")
        raise PdfDruckFehler("Kein Browser für den PDF-Druck gefunden (" + "; ".join(fehler) + ")")

    async def _neustart(self) -> None:
        self.neustarts += 1
        try:
            if self._browser is not None:
                await self._browser.close()
        except Exception:   # noqa: BLE001
            pass
        self._browser = None

    async def _drucken(self, html_pfad: Path, kopf_html: str, fuss_html: str, rand_mm: int) -> bytes:
        browser = await self._browser_holen()
        async with self._sem:
            context = await browser.new_context()
            try:
                page = await context.new_page()
                await page.goto(html_pfad.as_uri(), wait_until="load")
                await page.emulate_media(media="print")
                # Schriften (file://, variable woff2) sicher geladen
                await page.evaluate("document.fonts ? document.fonts.ready.then(() => true) : true")
                return await page.pdf(
                    format="A4", print_background=True, prefer_css_page_size=True,
                    display_header_footer=bool(kopf_html or fuss_html),
                    header_template=kopf_html or "<div></div>", footer_template=fuss_html or "<div></div>",
                    margin={"top": f"{rand_mm}mm", "right": "0mm", "bottom": "0mm", "left": "0mm"})
            finally:
                await context.close()

    async def _drucken_sicher(self, html_pfad: Path, kopf_html: str, fuss_html: str, rand_mm: int) -> bytes:
        try:
            return await self._drucken(html_pfad, kopf_html, fuss_html, rand_mm)
        except PdfDruckFehler:
            raise
        except Exception as e:   # noqa: BLE001 – Browser neu starten, Fehler melden
            await self._neustart()
            raise PdfDruckFehler(f"Browser-Druck fehlgeschlagen: {str(e).splitlines()[0][:200]}") from e

    # --- Synchrone Nahtstelle (Threadpool/Tests)
    def drucken(self, html: str, kopf_html: str = "", fuss_html: str = "", *, timeout_s: float = TIMEOUT_S,
                rand_mm: int = RAND_OBEN_MM) -> bytes:
        TEMP_ORDNER.mkdir(parents=True, exist_ok=True)
        pfad = TEMP_ORDNER / f"angebot-{uuid.uuid4().hex}.html"
        pfad.write_text(html, encoding="utf-8")
        start = time.perf_counter()
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._drucken_sicher(pfad, kopf_html, fuss_html, rand_mm), self._schleife())
            try:
                pdf = future.result(timeout=timeout_s)
            except TimeoutError:
                future.cancel()
                asyncio.run_coroutine_threadsafe(self._neustart(), self._schleife())
                raise PdfDruckFehler(f"Zeitüberschreitung beim Browser-Druck ({int(timeout_s)} s)")
        except PdfDruckFehler as e:
            self.fehler_anzahl += 1
            self.letzter_fehler = str(e)
            raise
        finally:
            try:
                pfad.unlink()
            except OSError:
                pass
        self.letzte_dauer_ms = int((time.perf_counter() - start) * 1000)
        self.anzahl += 1
        return pdf

    def schliessen(self) -> None:
        if self._loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._neustart(), self._loop).result(timeout=5)
            if self._pw is not None:
                asyncio.run_coroutine_threadsafe(self._pw.stop(), self._loop).result(timeout=5)
        except Exception:   # noqa: BLE001
            pass
        self._pw = None
        self._loop.call_soon_threadsafe(self._loop.stop)
        # v36 Phase 190 (A3): idempotent – ein zweiter Aufruf (Skript + atexit) legt sonst eine
        # Coroutine in die bereits gestoppte Schleife („Task was destroyed but it is pending“)
        self._loop = None
        self._thread = None
        self._sem = None

    def status(self) -> dict:
        return {"browser": self.browser_kanal, "browser_pfad": self.browser_pfad, "version": self.browser_version,
                "letzte_dauer_ms": self.letzte_dauer_ms, "anzahl": self.anzahl, "fehler": self.fehler_anzahl,
                "letzter_fehler": self.letzter_fehler, "neustarts": self.neustarts,
                "gestartet": self._browser is not None}


DRUCKER = _Drucker()
atexit.register(DRUCKER.schliessen)


def drucken(html: str, kopf_html: str = "", fuss_html: str = "", **opts) -> bytes:
    """HTML → PDF-Bytes (A4). Läuft nie mit offener Datenbanksitzung aufrufen – Kontext vorher lesen."""
    return DRUCKER.drucken(html, kopf_html, fuss_html, **opts)


def status() -> dict:
    return DRUCKER.status()


# ----------------------------------------------------------------------------- Engine-Schalter / Test
def engine(session) -> str:
    """Einstellung `pdf_engine` (html | fpdf2); unbekannte Werte → Standard."""
    from app.models import einstellung_holen
    wert = (einstellung_holen(session, EINSTELLUNG_ENGINE, ENGINE_STANDARD) or "").strip().lower()
    return wert if wert in (ENGINE_HTML, ENGINE_FPDF2) else ENGINE_STANDARD


def engine_setzen(session, wert: str) -> str:
    from app.models import einstellung_setzen
    wert = ENGINE_FPDF2 if (wert or "").strip().lower() == ENGINE_FPDF2 else ENGINE_HTML
    einstellung_setzen(session, EINSTELLUNG_ENGINE, wert)
    return wert


PROBESEITE = (
    "{% extends 'pdf/angebot/basis.html' %}{% block seiten %}"
    "<div class='pdf-seite'><div class='pdf-eyebrow'>Probe</div><h1>Browser-Druck</h1>"
    "<p>Angebots-PDF Layout v3 – Testseite ohne Kundendaten.</p></div>{% endblock %}")


def browser_test(sparte: str = "WP", *, vollstaendig: bool = False) -> dict:
    """Druckt eine Probeseite (ohne Datenbank): {ok, browser, version, pfad, dauer_ms, fehler, seiten,
    bytes, vorlage, pdf}. v36 Phase 190: `vollstaendig=True` (Knopf „Test-PDF erzeugen“ der
    Parametrierung) druckt das Demo-Angebot (`pdf_kontext.demo_kontext`) über die echte Sparten-Vorlage,
    sobald sie vorliegt – sonst die Probeseite; `pdf` sind die Bytes (für den Download), `vorlage` nennt
    den Weg. Fehler der Vorlage selbst (kein Browser-Fehler) kommen als ok=False mit `art = "vorlage"`;
    Browser-Fehler tragen `art = "browser"`. Nie mit offener Datenbanksitzung aufrufen (Prozess-I/O)."""
    from app import pdf_kontext
    kontext = pdf_kontext.demo_kontext(sparte if sparte in pdf_kontext.SPARTEN else "WP")
    start = time.perf_counter()
    vorlage = "Probeseite"
    try:
        if vollstaendig and vorlage_vorhanden(kontext["sparte"]):
            vorlage = f"Sparten-Vorlage {kontext['sparte']} (Demo-Angebot)"
            html = html_rendern(vorlage_fuer(kontext["sparte"]), kontext)
        else:
            html = jinja_env().from_string(PROBESEITE).render(kontext=kontext, static=STATIC_URL)
    except Exception as e:   # noqa: BLE001 – Fehler in der Vorlage (kein Browser-Fehler)
        st = DRUCKER.status()
        return {"ok": False, "art": "vorlage", "browser": st["browser"], "version": st["version"],
                "pfad": st["browser_pfad"], "dauer_ms": int((time.perf_counter() - start) * 1000),
                "fehler": f"Vorlage: {type(e).__name__}: {str(e)[:200]}", "seiten": 0, "bytes": 0,
                "vorlage": vorlage, "pdf": b""}
    try:
        pdf = drucken(html, kopfzeile_html(kontext))
        seiten = 0
        try:
            from pypdf import PdfReader
            import io
            seiten = len(PdfReader(io.BytesIO(pdf)).pages)
        except Exception:   # noqa: BLE001
            pass
        st = DRUCKER.status()
        return {"ok": True, "art": "", "browser": st["browser"], "version": st["version"],
                "pfad": st["browser_pfad"], "dauer_ms": int((time.perf_counter() - start) * 1000),
                "fehler": "", "seiten": seiten, "bytes": len(pdf), "vorlage": vorlage, "pdf": pdf}
    except PdfDruckFehler as e:
        st = DRUCKER.status()
        return {"ok": False, "art": "browser", "browser": st["browser"], "version": st["version"],
                "pfad": st["browser_pfad"], "dauer_ms": int((time.perf_counter() - start) * 1000),
                "fehler": str(e), "seiten": 0, "bytes": 0, "vorlage": vorlage, "pdf": b""}


# ----------------------------------------------------------------------------- Testergebnis, Dateien, Protokoll (v36 Phase 190, A3)
TEST_PDF_PFAD = TEMP_ORDNER / "angebots-pdf-test.pdf"   # letztes Test-PDF der Parametrierung (Download)


def letzten_test_merken(session, ergebnis: dict) -> dict:
    """Ergebnis eines Browser-Tests (ohne PDF-Bytes) als JSON in der Einstellung `pdf_letzter_test`
    – Quelle für den Go-live-Punkt „Angebots-PDF: Browser-Druck grün“ und die Parametrierungsseite."""
    import json
    from datetime import datetime

    from app.models import einstellung_setzen
    daten = {k: v for k, v in ergebnis.items() if k != "pdf"}
    daten["zeit"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    einstellung_setzen(session, EINSTELLUNG_LETZTER_TEST, json.dumps(daten, ensure_ascii=False))
    return daten


def letzter_test(session) -> dict | None:
    """Gespeichertes Ergebnis des letzten Browser-Tests (None = noch keiner)."""
    import json

    from app.models import einstellung_holen
    roh = einstellung_holen(session, EINSTELLUNG_LETZTER_TEST, "")
    if not roh:
        return None
    try:
        daten = json.loads(roh)
    except ValueError:
        return None
    return daten if isinstance(daten, dict) else None


def dateien_pruefen() -> dict:
    """Bilder und Schriften der Vorlagen unter app/static/pdf/: {fehlend: [..], vorhanden: n, gesamt: n}."""
    from app import pdf_kontext
    erwartet = list(BILDER_FEST)
    erwartet += [s["titelbild"] for s in pdf_kontext.SPARTEN.values()]
    erwartet += [bild for bild, _alt in pdf_kontext.ZERTIFIKATE]
    erwartet += list(SCHRIFTEN_ERWARTET)
    fehlend = [rel for rel in erwartet if not (STATIC / "pdf" / rel).is_file()]
    return {"fehlend": fehlend, "vorhanden": len(erwartet) - len(fehlend), "gesamt": len(erwartet)}


def vorlagen_stand() -> dict:
    """Welche Sparten-Vorlagen liegen vor (Phase 189, Agent A1)? {WP: bool, PV: bool, KL: bool, WB: bool}."""
    return {s: vorlage_vorhanden(s) for s in ("WP", "PV", "KL", "WB")}


def protokollieren(session, benutzer, aenderungen: list[str]) -> None:
    """Änderungen der Parametrierung „Angebots-PDF“ (Engine-Schalter, Test) – letzte PROTOKOLL_MAX Zeilen."""
    from datetime import datetime

    from app.models import einstellung_holen, einstellung_setzen
    if not aenderungen:
        return
    zeilen = [z for z in einstellung_holen(session, EINSTELLUNG_PROTOKOLL, "").splitlines() if z.strip()]
    wer = getattr(benutzer, "name", "") or "System"
    stempel = datetime.now().strftime("%d.%m.%Y %H:%M")
    zeilen.extend(f"{stempel} · {wer} · {text}" for text in aenderungen)
    einstellung_setzen(session, EINSTELLUNG_PROTOKOLL, "\n".join(zeilen[-PROTOKOLL_MAX:]))


def protokoll(session) -> str:
    from app.models import einstellung_holen
    return einstellung_holen(session, EINSTELLUNG_PROTOKOLL, "")


def migration_v36_pdf_engine(session) -> list[str]:
    """migrate.py-Hook (PLAN_V22 Phase 188, idempotent): Browser-Test beim Update/Start. Schlägt er fehl →
    `pdf_engine = fpdf2` (bisheriges Layout) mit Meldung; läuft er → die Einstellung wird nur angelegt, wenn
    sie fehlt (Standard html), eine vorhandene Wahl des Admins bleibt. Das Ergebnis landet in
    `pdf_letzter_test`; der zweite Lauf ohne Änderung meldet nichts. Der Browser-Test ist Prozess-I/O
    und läuft nach `verbindung_freigeben` (v27-Regel), danach nur eine kurze Schreibung."""
    from app import db
    from app.models import einstellung_holen, einstellung_setzen
    vorhanden = (einstellung_holen(session, EINSTELLUNG_ENGINE, "") or "").strip().lower()
    db.verbindung_freigeben(session)       # Browser-Druck ohne gehaltene Verbindung
    ergebnis = browser_test()
    letzten_test_merken(session, ergebnis)
    meldungen: list[str] = []
    dauer = f"{ergebnis['dauer_ms']} ms"
    if not ergebnis["ok"]:
        if vorhanden != ENGINE_FPDF2:
            einstellung_setzen(session, EINSTELLUNG_ENGINE, ENGINE_FPDF2)
            text = (f"Angebots-PDF: Browser-Druck nicht verfügbar ({ergebnis['fehler']}) – Engine auf "
                    f"fpdf2 gestellt (bisheriges Layout; Parametrierung → Angebots-PDF, "
                    f"scripts\\pdf-browser-pruefen.bat)")
            protokollieren(session, None, [f"pdf_engine: {vorhanden or 'leer'} → fpdf2 (Browser-Test "
                                           f"fehlgeschlagen: {ergebnis['fehler'][:120]})"])
            meldungen.append(text)
        return meldungen
    if not vorhanden:
        einstellung_setzen(session, EINSTELLUNG_ENGINE, ENGINE_HTML)
        protokollieren(session, None, [f"pdf_engine: html angelegt (Browser-Test ok, {dauer})"])
        meldungen.append(f"Angebots-PDF: Browser-Test ok ({ergebnis['browser']} {ergebnis['version']}, "
                         f"{dauer}) – Engine html (Layout v3) angelegt")
    return meldungen


# ----------------------------------------------------------------------------- Angebot
def pdf_aus_kontext(kontext: dict) -> bytes:
    """Rendert die Sparten-Vorlage mit einem fertigen Kontext und druckt – ohne Datenbank."""
    html = html_rendern(vorlage_fuer(kontext.get("sparte", "WP")), kontext)
    return drucken(html, kopfzeile_html(kontext))


def angebot_pdf(session, angebot, *, signatur: dict | None = None, fassung: str = "kunde",
                benutzer=None) -> bytes:
    """Angebots-PDF (Layout v3) für ein Angebot. Liest den Kontext (pdf_kontext.fuer_angebot), gibt die
    Datenbankverbindung frei und druckt außerhalb der Sitzung. Fehler → PdfDruckFehler.
    `benutzer` (v36 Nachtrag, A1-Vertrag): der aufrufende Benutzer – Ansprechpartner-Rückfall
    (vorbereitender Innendienstler), von „Versand vorbereiten“/Kombi übergeben, sonst None."""
    from app import db, pdf_kontext
    kontext = pdf_kontext.fuer_angebot(session, angebot, signatur=signatur, fassung=fassung,
                                       benutzer=benutzer)
    db.verbindung_freigeben(session)
    return pdf_aus_kontext(kontext)


def angebot_html(session, angebot, *, signatur: dict | None = None, fassung: str = "kunde",
                 static_url: str | None = None, benutzer=None) -> str:
    """Dieselbe Vorlage als HTML (Design-Abnahme im Browser, GET /angebote/<id>/pdf.html – Phase 190).
    `static_url="/static"` für die Auslieferung über HTTP (Bilder/Schriften über den Web-Mount)."""
    from app import pdf_kontext
    kontext = pdf_kontext.fuer_angebot(session, angebot, signatur=signatur, fassung=fassung,
                                       benutzer=benutzer)
    return html_rendern(vorlage_fuer(kontext.get("sparte", "WP")), kontext, static_url=static_url)
