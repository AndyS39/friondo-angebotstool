# v36 (PLAN_V22 Phase 188/190, Agent A3): PDF-Engine `app/pdf_html.py` (Browser-Druck) und ihre
# Einbindung – Wächter-Ausschnitt (Browser-Druck = Prozess-I/O, nie mit offener Sitzung), Semaphore/
# Timeout des Druckers (gemockter Browser), Rückfall auf fpdf2 bei fehlendem Browser bzw. fehlendem
# Kontext (Fehlerprotokoll „PDF“ + Merker für die Versand-Meldung), Dateigröße ≤ 2,5 MB, Seitenzahl
# „SEITE 2 VON n“ auf Seite 2 (pypdf), eingebettete Schriften, keine externen Quellen im HTML, Migration
# `migration_v36_pdf_engine` (fpdf2 bei fehlgeschlagenem Test, idempotent), Parametrierungsseite (Admin
# 200, Innendienst Umleitung), /health-Felder, Go-live-Punkt 13. Browser-Tests laufen echt (Edge auf dem
# Dev-PC) und werden ohne Browser übersprungen. Läuft gegen DB_PFAD_OVERRIDE (Kopie); eigene
# Einstellungen werden am Ende zurückgesetzt.
import asyncio
import io
import re
import threading
import time
import unittest
import warnings
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import func

from app import auth, betrieb, config, db, golive, pdf_export, pdf_html, pdf_kontext
from app.db import SessionLocal, init_db
from app.main import app
from app.models import Angebot, Benutzer, Fehlerprotokoll, einstellung_holen, einstellung_setzen

BROWSER = pdf_html.browser_test()      # einmal je Modul (startet den Browser-Prozess)
BROWSER_OK = BROWSER["ok"]
MAX_BYTES = int(2.5 * 1024 * 1024)
TEST_NAME = "V36A3 Innendienst"

PROBE_ZWEI_SEITEN = (
    "{% extends 'pdf/angebot/basis.html' %}{% block seiten %}"
    "<div class='pdf-seite'><h1>Seite eins – Probe</h1><p>Umlaute: Ärger Öl Übung ß – Zahlen 1.234,56 €</p></div>"
    "<div class='pdf-seite'><h1>Seite zwei – Probe</h1><p>Zweite Seite für die Seitenzahl.</p></div>"
    "{% endblock %}")


def _pdf_text(daten: bytes) -> list[str]:
    return [(s.extract_text() or "") for s in PdfReader(io.BytesIO(daten)).pages]


def _schriften(daten: bytes) -> list[tuple[str, str, bool]]:
    """(Subtype, Name, eingebettet) je Font-Objekt. Chromium/Skia bettet die variable Nunito Sans als
    Type3-Schrift (Glyphen als Zeichenprozeduren, ohne BaseFont) ein; Type0/TrueType-Schriften gelten als
    eingebettet, wenn der FontDescriptor eine FontFile trägt."""
    ergebnis = []
    for seite in PdfReader(io.BytesIO(daten)).pages:
        fonts = (seite.get("/Resources") or {}).get("/Font") or {}
        for key in fonts:
            obj = fonts[key].get_object()
            subtype = str(obj.get("/Subtype"))
            name = str(obj.get("/BaseFont") or "")
            eingebettet = subtype == "/Type3"
            beschreiber = obj.get("/FontDescriptor")
            nachkommen = obj.get("/DescendantFonts")
            if nachkommen:
                d0 = nachkommen[0].get_object()
                name = name or str(d0.get("/BaseFont") or "")
                beschreiber = d0.get("/FontDescriptor")
            if beschreiber is not None:
                b = beschreiber.get_object()
                eingebettet = eingebettet or any(k in b for k in ("/FontFile", "/FontFile2", "/FontFile3"))
            ergebnis.append((subtype, name, eingebettet))
    return ergebnis


def _einstellung_sichern(namen) -> dict:
    with db.kurz(schreibend=False) as s:
        return {n: einstellung_holen(s, n, "") for n in namen}


def _einstellung_zurueck(werte: dict) -> None:
    with db.kurz() as s:
        for n, w in werte.items():
            einstellung_setzen(s, n, w)


# ----------------------------------------------------------------------------- Wächter
class Waechter(unittest.TestCase):
    """Der Browser-Druck zählt im v27-Wächter als Prozess-I/O: Aufrufkette drucken → pdf_aus_kontext →
    browser_test ist „unsicher“, pdf_html.angebot_pdf gibt die Sitzung vor dem Druck frei (erlaubt)."""

    def test_druck_als_prozess_io_erkannt(self):
        from tests.test_v27_sitzungen import verstoesse_suchen
        verstoesse, unsicher = verstoesse_suchen()
        for name in ("pdf_html.drucken", "pdf_html._Drucker.drucken", "pdf_html.pdf_aus_kontext",
                     "pdf_html.browser_test"):
            self.assertIn(name, unsicher)
        self.assertNotIn("pdf_html.angebot_pdf", unsicher)
        self.assertNotIn("pdf_export.pdf_fuer_angebot", unsicher)
        self.assertNotIn("pdf_html.migration_v36_pdf_engine", unsicher)
        self.assertEqual(verstoesse, [], "\n".join(verstoesse))

    def test_angebot_pdf_druckt_ohne_offene_sitzung(self):
        """Freigabe (commit) VOR dem Druck – zum Druckzeitpunkt hält die Sitzung keine Transaktion."""
        init_db()
        s = SessionLocal()
        try:
            angebot = s.query(Angebot).filter(Angebot.extern.is_(False)).first()
            self.assertIsNotNone(angebot)
            s.query(Angebot).count()          # Sitzung benutzt
            zustand = {}

            def fake_druck(kontext):
                zustand["in_transaktion"] = s.in_transaction()
                zustand["sparte"] = kontext.get("sparte")
                return b"%PDF-1.4 fake"

            with mock.patch.object(pdf_kontext, "fuer_angebot",
                                   return_value=pdf_kontext.demo_kontext("WP")), \
                    mock.patch.object(pdf_html, "pdf_aus_kontext", side_effect=fake_druck):
                daten = pdf_html.angebot_pdf(s, angebot)
            self.assertEqual(daten, b"%PDF-1.4 fake")
            self.assertFalse(zustand["in_transaktion"], "Sitzung während des Drucks noch offen")
            self.assertEqual(zustand["sparte"], "WP")
        finally:
            s.close()


# ----------------------------------------------------------------------------- Drucker (gemockter Browser)
class _Zaehler:
    def __init__(self):
        self.lock = threading.Lock()
        self.aktiv = 0
        self.maximum = 0
        self.aufrufe = 0


class _FakePage:
    def __init__(self, dauer: float, zaehler: _Zaehler):
        self.dauer = dauer
        self.zaehler = zaehler

    async def goto(self, url, wait_until=None):
        return None

    async def emulate_media(self, media=None):
        return None

    async def evaluate(self, js):
        return True

    async def pdf(self, **kw):
        with self.zaehler.lock:
            self.zaehler.aktiv += 1
            self.zaehler.aufrufe += 1
            self.zaehler.maximum = max(self.zaehler.maximum, self.zaehler.aktiv)
        try:
            await asyncio.sleep(self.dauer)
        finally:
            with self.zaehler.lock:
                self.zaehler.aktiv -= 1
        return b"%PDF-1.4 fake " + str(kw.get("format")).encode()


class _FakeContext:
    def __init__(self, page):
        self.page = page

    async def new_page(self):
        return self.page

    async def close(self):
        return None


class _FakeBrowser:
    version = "fake 1.0"

    def __init__(self, dauer: float, zaehler: _Zaehler):
        self.dauer = dauer
        self.zaehler = zaehler
        self.geschlossen = 0

    def is_connected(self):
        return True

    async def new_context(self):
        return _FakeContext(_FakePage(self.dauer, self.zaehler))

    async def close(self):
        self.geschlossen += 1


def _drucker_mit_fake(dauer: float):
    """Eigener _Drucker (nicht der globale) mit gemocktem Browser; der echte Browser bleibt unberührt."""
    d = pdf_html._Drucker()
    zaehler = _Zaehler()
    browser = _FakeBrowser(dauer, zaehler)

    async def holen():
        if d._sem is None:
            d._sem = asyncio.Semaphore(pdf_html.PARALLEL)
        d._browser = browser
        d.browser_kanal, d.browser_version = "fake", browser.version
        return browser

    d._browser_holen = holen
    return d, zaehler, browser


class Drucker(unittest.TestCase):
    def test_semaphore_hoechstens_zwei_parallel(self):
        d, zaehler, _ = _drucker_mit_fake(0.4)
        try:
            ergebnisse = []
            fehler = []

            def lauf():
                try:
                    ergebnisse.append(d.drucken("<html><body>x</body></html>"))
                except Exception as e:   # noqa: BLE001
                    fehler.append(e)

            threads = [threading.Thread(target=lauf) for _ in range(4)]
            start = time.perf_counter()
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=20)
            dauer = time.perf_counter() - start
            self.assertEqual(fehler, [])
            self.assertEqual(len(ergebnisse), 4)
            self.assertTrue(all(e.startswith(b"%PDF-1.4 fake A4") for e in ergebnisse))
            self.assertEqual(zaehler.maximum, pdf_html.PARALLEL, "Semaphore greift nicht")
            self.assertGreaterEqual(dauer, 0.75, f"vier Drucke in {dauer:.2f} s – liefen zu viele parallel")
            self.assertEqual(d.anzahl, 4)
            self.assertGreater(d.letzte_dauer_ms, 0)
        finally:
            d.schliessen()

    def test_timeout_wirft_pdfdruckfehler_und_startet_neu(self):
        d, zaehler, browser = _drucker_mit_fake(3.0)
        try:
            with self.assertRaises(pdf_html.PdfDruckFehler) as cm:
                d.drucken("<html></html>", timeout_s=0.5)
            self.assertIn("Zeitüberschreitung", str(cm.exception))
            self.assertEqual(d.fehler_anzahl, 1)
            self.assertIn("Zeitüberschreitung", d.letzter_fehler)
            # Neustart des Browsers läuft im Drucker-Thread an
            for _ in range(50):
                if d.neustarts >= 1 and browser.geschlossen >= 1:
                    break
                time.sleep(0.05)
            self.assertGreaterEqual(d.neustarts, 1)
            self.assertGreaterEqual(browser.geschlossen, 1)
            self.assertIn("Zeitüberschreitung", d.status()["letzter_fehler"])
            # keine HTML-Reste im Temp-Ordner
            self.assertEqual(list(pdf_html.TEMP_ORDNER.glob("angebot-*.html")), [])
        finally:
            d.schliessen()

    def test_browser_fehlt_liefert_pdfdruckfehler(self):
        d = pdf_html._Drucker()

        async def holen():
            raise pdf_html.PdfDruckFehler("Kein Browser für den PDF-Druck gefunden (Test)")

        d._browser_holen = holen
        try:
            with self.assertRaises(pdf_html.PdfDruckFehler) as cm:
                d.drucken("<html></html>", timeout_s=5)
            self.assertIn("Kein Browser", str(cm.exception))
            self.assertEqual(d.fehler_anzahl, 1)
        finally:
            d.schliessen()


# ----------------------------------------------------------------------------- Rückfall fpdf2
class Rueckfall(unittest.TestCase):
    """pdf_export.pdf_fuer_angebot / signiertes_pdf_erzeugen: Engine html mit fehlgeschlagenem Druck →
    fpdf2-PDF, Fehlerprotokoll „PDF“, Merker letzter_rueckfall; Schalter fpdf2 → kein Hinweis."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        cls.angebot = (cls.s.query(Angebot)
                       .filter(Angebot.extern.is_(False), Angebot.konfigurator_typ == "WP")
                       .order_by(Angebot.id).first())
        assert cls.angebot is not None, "kein WP-Angebot in der DB-Kopie"
        cls.sicherung = _einstellung_sichern([pdf_html.EINSTELLUNG_ENGINE])

    @classmethod
    def tearDownClass(cls):
        cls.s.close()
        _einstellung_zurueck(cls.sicherung)
        pdf_export._rueckfall_loeschen(cls.angebot.id)

    def setUp(self):
        self.s.rollback()
        pdf_html.engine_setzen(self.s, "html")
        self.s.commit()
        pdf_export._rueckfall_loeschen(self.angebot.id)

    def _fehlerprotokoll(self) -> int:
        return (self.s.query(Fehlerprotokoll)
                .filter(Fehlerprotokoll.fehlertyp == "PDF",
                        Fehlerprotokoll.meldung.like(f"{self.angebot.nummer}:%")).count())

    def test_druckfehler_faellt_auf_fpdf2_zurueck(self):
        vorher = self._fehlerprotokoll()
        with mock.patch.object(pdf_html, "angebot_pdf",
                               side_effect=pdf_html.PdfDruckFehler("Kein Browser (Test)")) as m:
            pfad = pdf_export.pdf_fuer_angebot(self.s, self.angebot)
        self.assertEqual(m.call_count, 1)
        self.assertTrue(pfad.is_file())
        self.assertEqual(pfad, pdf_export.pdf_zielpfad(self.angebot))
        self.assertTrue(pfad.read_bytes().startswith(b"%PDF"))
        self.assertNotIn("SEITE 1 VON", "\n".join(_pdf_text(pfad.read_bytes())))   # altes Layout
        self.assertEqual(pdf_export.letzter_rueckfall(self.angebot.id),
                         "PDF im alten Layout erzeugt (Browser-Druck fehlgeschlagen: Kein Browser (Test))")
        self.s.expire_all()
        self.assertEqual(self._fehlerprotokoll(), vorher + 1)
        eintrag = (self.s.query(Fehlerprotokoll).filter(Fehlerprotokoll.fehlertyp == "PDF")
                   .order_by(Fehlerprotokoll.id.desc()).first())
        self.assertIn("Rückfall auf fpdf2", eintrag.meldung)
        self.assertEqual(eintrag.pfad, f"/angebote/{self.angebot.id}/pdf")
        self.assertIsNotNone(pdf_export.rueckfall_details(self.angebot.id))

    def test_fehlender_kontext_faellt_zurueck(self):
        with mock.patch.object(pdf_html, "angebot_pdf", side_effect=NotImplementedError("Phase 189 fehlt")):
            pfad = pdf_export.pdf_fuer_angebot(self.s, self.angebot)
        self.assertTrue(pfad.is_file())
        self.assertIn("Layout v3 noch nicht verfügbar", pdf_export.letzter_rueckfall(self.angebot.id))

    def test_vorlagenfehler_faellt_zurueck_mit_traceback(self):
        vorher = self._fehlerprotokoll()
        with mock.patch.object(pdf_html, "angebot_pdf", side_effect=KeyError("gruppen")):
            pfad = pdf_export.pdf_fuer_angebot(self.s, self.angebot)
        self.assertTrue(pfad.is_file())
        self.assertIn("Vorlage/Kontext: KeyError", pdf_export.letzter_rueckfall(self.angebot.id))
        self.s.expire_all()
        self.assertEqual(self._fehlerprotokoll(), vorher + 1)
        eintrag = (self.s.query(Fehlerprotokoll).filter(Fehlerprotokoll.fehlertyp == "PDF")
                   .order_by(Fehlerprotokoll.id.desc()).first())
        self.assertIn("Traceback", eintrag.traceback or "")

    def test_erfolg_schreibt_bytes_und_loescht_merker(self):
        pdf_export._rueckfall_merken(self.angebot.id, "alt")
        with mock.patch.object(pdf_html, "angebot_pdf", return_value=b"%PDF-1.4 v36 layout") as m:
            pfad = pdf_export.pdf_fuer_angebot(self.s, self.angebot)
        m.assert_called_once()
        self.assertEqual(pfad.read_bytes(), b"%PDF-1.4 v36 layout")
        self.assertEqual(pdf_export.letzter_rueckfall(self.angebot.id), "")
        self.assertIsNone(pdf_export.rueckfall_details(self.angebot.id))

    def test_schalter_fpdf2_alter_weg_ohne_hinweis(self):
        pdf_export._rueckfall_merken(self.angebot.id, "alt")
        pdf_html.engine_setzen(self.s, "fpdf2")
        self.s.commit()
        self.assertEqual(pdf_html.engine(self.s), "fpdf2")
        with mock.patch.object(pdf_html, "angebot_pdf") as m:
            pfad = pdf_export.pdf_fuer_angebot(self.s, self.angebot)
        m.assert_not_called()
        self.assertTrue(pfad.read_bytes().startswith(b"%PDF"))
        self.assertEqual(pdf_export.letzter_rueckfall(self.angebot.id), "")   # Schalter = kein Hinweis
        # unbekannte Werte fallen auf den Standard html zurück
        einstellung_setzen(self.s, pdf_html.EINSTELLUNG_ENGINE, "irgendwas")
        self.s.commit()
        self.assertEqual(pdf_html.engine(self.s), "html")

    def test_signatur_dict_und_signiertes_pdf(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 300
        zeit = datetime(2026, 10, 16, 14, 30)
        d = pdf_export.signatur_dict(png, " Max Mustermann ", zeit, "Tablet " * 40)
        self.assertTrue(d["bild_data_url"].startswith("data:image/png;base64,iVBOR"))
        self.assertEqual(d["name"], "Max Mustermann")
        self.assertEqual(d["zeitstempel"], "16.10.2026 14:30")
        self.assertEqual(len(d["geraet"]), 150)
        aufrufe = {}

        def fake(session, angebot, *, signatur=None, fassung="kunde", **kw):
            aufrufe["signatur"] = signatur
            aufrufe["benutzer"] = kw.get("benutzer")
            return b"%PDF-1.4 signiert"

        with mock.patch.object(pdf_html, "angebot_pdf", side_effect=fake):
            pfad = pdf_export.signiertes_pdf_erzeugen(self.s, self.angebot, png, "Max Mustermann", zeit,
                                                      geraet="Tablet")
        try:
            self.assertEqual(pfad, config.SIGNIERT_ORDNER / f"{self.angebot.nummer}-signiert.pdf")
            self.assertEqual(pfad.read_bytes(), b"%PDF-1.4 signiert")
            self.assertEqual(aufrufe["signatur"]["name"], "Max Mustermann")
            self.assertEqual(aufrufe["signatur"]["geraet"], "Tablet")
            self.assertEqual(pdf_export.letzter_rueckfall(self.angebot.id), "")
            # Rückfall des signierten PDFs → fpdf2-Weg mit eingebettetem Bild (Phase 23), Merker gesetzt
            with mock.patch.object(pdf_html, "angebot_pdf",
                                   side_effect=pdf_html.PdfDruckFehler("weg (Test)")):
                pfad2 = pdf_export.signiertes_pdf_erzeugen(self.s, self.angebot, _png_bytes(), "Max",
                                                           zeit, geraet="Tablet")
            self.assertEqual(pfad2, pfad)
            self.assertTrue(pfad2.read_bytes().startswith(b"%PDF"))
            self.assertIn("weg (Test)", pdf_export.letzter_rueckfall(self.angebot.id))
        finally:
            pfad.unlink(missing_ok=True)


def _png_bytes() -> bytes:
    """Kleines echtes PNG (Pillow) – Signaturbild für die Tests."""
    from PIL import Image, ImageDraw
    bild = Image.new("RGBA", (240, 80), (255, 255, 255, 0))
    ImageDraw.Draw(bild).line([(10, 60), (60, 20), (120, 60), (200, 20)], fill=(20, 20, 60, 255), width=4)
    puffer = io.BytesIO()
    bild.save(puffer, format="PNG")
    return puffer.getvalue()


# ----------------------------------------------------------------------------- Druck (echter Browser)
@unittest.skipUnless(BROWSER_OK, f"kein Browser für den PDF-Druck: {BROWSER['fehler']}")
class Druck(unittest.TestCase):
    def test_probeseite_groesse_seitenzahl_schriften(self):
        kontext = pdf_kontext.demo_kontext("WP")
        html = pdf_html.jinja_env().from_string(PROBE_ZWEI_SEITEN).render(kontext=kontext,
                                                                          static=pdf_html.STATIC_URL)
        daten = pdf_html.drucken(html, pdf_html.kopfzeile_html(kontext))
        self.assertTrue(daten.startswith(b"%PDF"))
        self.assertLessEqual(len(daten), MAX_BYTES)
        seiten = _pdf_text(daten)
        self.assertEqual(len(seiten), 2)
        self.assertIn("SEITE 1 VON 2", seiten[0])
        self.assertIn("SEITE 2 VON 2", seiten[1])
        self.assertIn("Angebot-Nr. AN-C-269999", seiten[1])
        self.assertIn("Ärger Öl Übung ß", seiten[0])
        schriften = _schriften(daten)
        self.assertTrue(schriften)
        self.assertTrue(all(e for _s, _n, e in schriften),
                        f"nicht eingebettete Schrift: {[(s, n) for s, n, e in schriften if not e]}")
        # Chromium bettet die variable Nunito Sans als Type3 ein (Befund A3) – mindestens eine Type3-
        # Schrift (Seiteninhalt) neben der Systemschrift der Kopfzeile
        self.assertTrue(any(s == "/Type3" or "Nunito" in n for s, n, _e in schriften), schriften)
        st = pdf_html.status()
        self.assertTrue(st["gestartet"])
        self.assertGreater(st["letzte_dauer_ms"], 0)

    @unittest.skipUnless(pdf_html.vorlage_vorhanden("WP"), "Sparten-Vorlage WP (Agent A1) fehlt noch")
    def test_demo_angebot_ueber_sparten_vorlage(self):
        daten = pdf_html.pdf_aus_kontext(pdf_kontext.demo_kontext("WP"))
        self.assertLessEqual(len(daten), MAX_BYTES, f"{len(daten)} Bytes")
        seiten = _pdf_text(daten)
        self.assertGreaterEqual(len(seiten), 4)
        self.assertIn(f"SEITE 2 VON {len(seiten)}", seiten[1])
        self.assertTrue(all(e for _s, _n, e in _schriften(daten)))

    def test_browser_test_vollstaendig_liefert_pdf(self):
        ergebnis = pdf_html.browser_test("WP", vollstaendig=True)
        self.assertTrue(ergebnis["ok"], ergebnis["fehler"])
        self.assertTrue(ergebnis["pdf"].startswith(b"%PDF"))
        self.assertEqual(len(ergebnis["pdf"]), ergebnis["bytes"])
        self.assertIn(ergebnis["vorlage"], ("Probeseite", "Sparten-Vorlage WP (Demo-Angebot)"))
        if pdf_html.vorlage_vorhanden("WP"):
            self.assertEqual(ergebnis["vorlage"], "Sparten-Vorlage WP (Demo-Angebot)")
        self.assertGreaterEqual(ergebnis["seiten"], 1)
        self.assertEqual(ergebnis["browser"], BROWSER["browser"])


class Html(unittest.TestCase):
    def _quellen_pruefen(self, html: str):
        self.assertNotIn("<script", html.lower())
        for quelle in re.findall(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", html):
            if quelle.startswith(("mailto:", "#", "data:")):
                continue
            tag_ok = quelle.startswith(("file://", "/static/"))
            if not tag_ok:
                # <a href> auf friondo.de/Award ist ein Link, keine geladene Quelle – geladene Quellen
                # (link/img/script) dürfen nur file:// bzw. /static sein
                self.assertNotRegex(html, r"<(link|img|script|source)[^>]*\b(src|href)=[\"']" + re.escape(quelle),
                                    f"externe Quelle geladen: {quelle}")
        self.assertNotRegex(html, r"url\(\s*[\"']?https?://", "externe URL in einem Style")

    def test_probeseite_ohne_externe_quellen(self):
        kontext = pdf_kontext.demo_kontext("WP")
        html = pdf_html.jinja_env().from_string(pdf_html.PROBESEITE).render(kontext=kontext,
                                                                            static=pdf_html.STATIC_URL)
        self.assertIn("file:///", html)
        self.assertIn("/pdf/angebot.css", html)
        self._quellen_pruefen(html)
        # HTML-Vorschau über HTTP: static_url=/static
        web = pdf_html.html_rendern("pdf/angebot/basis.html", kontext, static_url="/static")
        self.assertIn('href="/static/pdf/angebot.css"', web)
        self.assertNotIn("file:///", web)

    @unittest.skipUnless(pdf_html.vorlage_vorhanden("WP"), "Sparten-Vorlage WP (Agent A1) fehlt noch")
    def test_sparten_vorlagen_ohne_externe_quellen_und_ohne_ek(self):
        for sparte in ("WP", "PV", "KL", "WB"):
            if not pdf_html.vorlage_vorhanden(sparte):
                continue
            html = pdf_html.html_rendern(pdf_html.vorlage_fuer(sparte), pdf_kontext.demo_kontext(sparte))
            self._quellen_pruefen(html)
            self.assertNotIn("Deckungsbeitrag", html)
            self.assertNotRegex(html, r"\bEK\b")

    def test_dateien_und_vorlagen_stand(self):
        d = pdf_html.dateien_pruefen()
        self.assertEqual(d["gesamt"], d["vorhanden"] + len(d["fehlend"]))
        self.assertGreaterEqual(d["gesamt"], 17)
        self.assertEqual(d["fehlend"], [], d["fehlend"])
        self.assertEqual(set(pdf_html.vorlagen_stand()), {"WP", "PV", "KL", "WB"})


# ----------------------------------------------------------------------------- Migration
class Migration(unittest.TestCase):
    NAMEN = (pdf_html.EINSTELLUNG_ENGINE, pdf_html.EINSTELLUNG_LETZTER_TEST, pdf_html.EINSTELLUNG_PROTOKOLL)

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.sicherung = _einstellung_sichern(cls.NAMEN)

    @classmethod
    def tearDownClass(cls):
        _einstellung_zurueck(cls.sicherung)

    @staticmethod
    def _ergebnis(ok: bool, fehler: str = "") -> dict:
        return {"ok": ok, "art": "" if ok else "browser", "browser": "msedge" if ok else "",
                "version": "155.0" if ok else "", "pfad": "msedge", "dauer_ms": 123, "fehler": fehler,
                "seiten": 1 if ok else 0, "bytes": 100 if ok else 0, "vorlage": "Probeseite", "pdf": b"%PDF"}

    def _lauf(self, ergebnis: dict) -> list[str]:
        with mock.patch.object(pdf_html, "browser_test", return_value=ergebnis):
            with db.kurz() as s:
                return pdf_html.migration_v36_pdf_engine(s)

    def _engine(self) -> str:
        with db.kurz(schreibend=False) as s:
            return einstellung_holen(s, pdf_html.EINSTELLUNG_ENGINE, "")

    def test_fehlgeschlagener_test_setzt_fpdf2_idempotent(self):
        _einstellung_zurueck({n: "" for n in self.NAMEN})
        meldungen = self._lauf(self._ergebnis(False, "Kein Browser für den PDF-Druck gefunden (x)"))
        self.assertEqual(len(meldungen), 1)
        self.assertIn("Browser-Druck nicht verfügbar (Kein Browser für den PDF-Druck gefunden (x))", meldungen[0])
        self.assertIn("Engine auf fpdf2 gestellt", meldungen[0])
        self.assertEqual(self._engine(), "fpdf2")
        with db.kurz(schreibend=False) as s:
            test = pdf_html.letzter_test(s)
            self.assertFalse(test["ok"])
            self.assertIn("Kein Browser", test["fehler"])
            self.assertNotIn("pdf", test)
            self.assertIn("pdf_engine: leer → fpdf2", pdf_html.protokoll(s))
        # zweiter Lauf: keine Änderung, keine Meldung
        self.assertEqual(self._lauf(self._ergebnis(False, "weiter weg")), [])
        self.assertEqual(self._engine(), "fpdf2")

    def test_erfolgreicher_test_legt_html_an_und_laesst_wahl(self):
        _einstellung_zurueck({n: "" for n in self.NAMEN})
        meldungen = self._lauf(self._ergebnis(True))
        self.assertEqual(len(meldungen), 1)
        self.assertIn("Browser-Test ok (msedge 155.0, 123 ms)", meldungen[0])
        self.assertEqual(self._engine(), "html")
        self.assertEqual(self._lauf(self._ergebnis(True)), [])       # idempotent
        # Wahl des Admins bleibt
        _einstellung_zurueck({pdf_html.EINSTELLUNG_ENGINE: "fpdf2"})
        self.assertEqual(self._lauf(self._ergebnis(True)), [])
        self.assertEqual(self._engine(), "fpdf2")
        with db.kurz(schreibend=False) as s:
            self.assertTrue(pdf_html.letzter_test(s)["ok"])

    def test_migration_gibt_sitzung_vor_dem_test_frei(self):
        zustand = {}
        s = SessionLocal()
        try:
            s.query(Angebot).count()

            def test_mit_pruefung():
                zustand["in_transaktion"] = s.in_transaction()
                return self._ergebnis(True)

            with mock.patch.object(pdf_html, "browser_test", side_effect=test_mit_pruefung):
                pdf_html.migration_v36_pdf_engine(s)
            s.commit()
        finally:
            s.close()
        self.assertFalse(zustand["in_transaktion"])


# ----------------------------------------------------------------------------- Seiten, /health, Go-live
class Seiten(unittest.TestCase):
    NAMEN = (pdf_html.EINSTELLUNG_ENGINE, pdf_html.EINSTELLUNG_LETZTER_TEST, pdf_html.EINSTELLUNG_PROTOKOLL)

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.sicherung = _einstellung_sichern(cls.NAMEN)
        cls.s = SessionLocal()
        cls.s.query(Benutzer).filter(Benutzer.name == TEST_NAME).delete(synchronize_session=False)
        cls.innen = Benutzer(id=(cls.s.query(func.max(Benutzer.id)).scalar() or 0) + 500, name=TEST_NAME,
                             rolle="innendienst", aktiv=True, email="v36a3-innen@test.local",
                             pin_hash=auth.pin_hash("4321"))
        cls.s.add(cls.innen)
        cls.s.commit()
        cls.admin = TestClient(app)
        cls.admin.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        cls.id_client = TestClient(app)
        cls.id_client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(cls.innen.id))

    @classmethod
    def tearDownClass(cls):
        cls.s.rollback()
        cls.s.query(Benutzer).filter(Benutzer.name == TEST_NAME).delete(synchronize_session=False)
        cls.s.commit()
        cls.s.close()
        _einstellung_zurueck(cls.sicherung)

    def test_parametrierungsseite_admin_und_innendienst(self):
        r = self.admin.get("/parametrierung/angebots-pdf")
        self.assertEqual(r.status_code, 200)
        for text in ("Angebots-PDF", "Engine", "Browser", "Test-PDF erzeugen", "Bilder und Schriften",
                     'name="pdf_engine"', "scripts\\pdf-browser-pruefen.bat"):
            self.assertIn(text, r.text, text)
        # Innendienst: Umleitung auf die Parametrierung (Konvention _nur_admin, kein Inhalt)
        r = self.id_client.get("/parametrierung/angebots-pdf", follow_redirects=False)
        self.assertIn(r.status_code, (303, 403))
        self.assertNotIn("Test-PDF erzeugen", r.text)
        # Verteilerseite: Karte „Angebotstool“ trägt den Eintrag (nur Admin)
        self.assertIn('href="/parametrierung/angebots-pdf"', self.admin.get("/parametrierung").text)
        self.assertNotIn('href="/parametrierung/angebots-pdf"', self.id_client.get("/parametrierung").text)

    def test_schalter_speichern_mit_protokoll(self):
        _einstellung_zurueck({pdf_html.EINSTELLUNG_ENGINE: "html", pdf_html.EINSTELLUNG_PROTOKOLL: ""})
        r = self.admin.post("/parametrierung/angebots-pdf", data={"pdf_engine": "fpdf2"},
                            follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("fpdf2", r.headers["location"])
        with db.kurz(schreibend=False) as s:
            self.assertEqual(pdf_html.engine(s), "fpdf2")
            self.assertIn("pdf_engine: html → fpdf2", pdf_html.protokoll(s))
        r = self.admin.post("/parametrierung/angebots-pdf", data={"pdf_engine": "fpdf2"},
                            follow_redirects=False)
        self.assertIn("Keine+%C3%84nderungen", r.headers["location"])
        r = self.admin.post("/parametrierung/angebots-pdf", data={"pdf_engine": "xyz"}, follow_redirects=False)
        self.assertIn("Unbekannte", r.headers["location"])
        # Innendienst darf nicht schalten
        r = self.id_client.post("/parametrierung/angebots-pdf", data={"pdf_engine": "html"},
                                follow_redirects=False)
        self.assertIn(r.status_code, (303, 403))
        with db.kurz(schreibend=False) as s:
            self.assertEqual(pdf_html.engine(s), "fpdf2")
        seite = self.admin.get("/parametrierung/angebots-pdf").text
        self.assertIn('value="fpdf2" checked', seite)
        self.assertIn("Änderungsprotokoll", seite)

    def test_test_pdf_knopf_und_download(self):
        ergebnis = {"ok": True, "art": "", "browser": "msedge", "version": "155.0", "pfad": "msedge",
                    "dauer_ms": 321, "fehler": "", "seiten": 3, "bytes": 5, "vorlage": "Probeseite",
                    "pdf": b"%PDF-1.4 test"}
        with mock.patch.object(pdf_html, "browser_test", return_value=ergebnis) as m:
            r = self.admin.post("/parametrierung/angebots-pdf/test", data={"sparte": "PV"},
                                follow_redirects=False)
        m.assert_called_once_with("PV", vollstaendig=True)
        self.assertEqual(r.status_code, 303)
        ort = r.headers["location"]
        self.assertIn("Test-PDF+erzeugt", ort)
        self.assertIn("321+ms", ort)
        self.assertEqual(pdf_html.TEST_PDF_PFAD.read_bytes(), b"%PDF-1.4 test")
        r = self.admin.get("/parametrierung/angebots-pdf/test.pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"%PDF-1.4 test")
        with db.kurz(schreibend=False) as s:
            test = pdf_html.letzter_test(s)
            self.assertTrue(test["ok"])
            self.assertEqual(test["dauer_ms"], 321)
            self.assertIn("Test-PDF ok", pdf_html.protokoll(s))
        self.assertIn("Letzter Browser-Test", self.admin.get("/parametrierung/angebots-pdf").text)
        # Fehlschlag: Meldung „fehlgeschlagen“, letzter Test nicht ok
        schlecht = dict(ergebnis, ok=False, art="browser", fehler="Kein Browser (Test)", pdf=b"")
        with mock.patch.object(pdf_html, "browser_test", return_value=schlecht):
            r = self.admin.post("/parametrierung/angebots-pdf/test", data={}, follow_redirects=False)
        self.assertIn("fehlgeschlagen", r.headers["location"])
        with db.kurz(schreibend=False) as s:
            self.assertFalse(pdf_html.letzter_test(s)["ok"])

    def test_health_felder_und_betriebsseite(self):
        _einstellung_zurueck({pdf_html.EINSTELLUNG_ENGINE: "html"})
        daten = betrieb.health()
        self.assertEqual(daten["pdf_engine"], "html")
        self.assertIsInstance(daten["pdf_letzte_druckdauer_ms"], int)
        self.assertIn("pdf_browser", daten)
        r = TestClient(app).get("/health")
        js = r.json()
        for feld in ("pdf_engine", "pdf_browser", "pdf_letzte_druckdauer_ms", "pdf_letzter_test_ok"):
            self.assertIn(feld, js, feld)
        self.assertEqual(js["pdf_engine"], "html")
        # Engine html + letzter Test fehlgeschlagen → warn-Grund
        with db.kurz() as s:
            pdf_html.letzten_test_merken(s, {"ok": False, "fehler": "Kein Browser (Test)", "dauer_ms": 1})
        daten = betrieb.health()
        self.assertTrue(any("Angebots-PDF" in g for g in daten["gruende"]), daten["gruende"])
        self.assertIs(daten["pdf_letzter_test_ok"], False)
        with db.kurz() as s:
            pdf_html.letzten_test_merken(s, dict(ok=True, fehler="", dauer_ms=5, browser="msedge", version="1"))
        daten = betrieb.health()
        self.assertFalse(any("Angebots-PDF" in g for g in daten["gruende"]), daten["gruende"])
        r = self.admin.get("/parametrierung/betrieb")
        self.assertEqual(r.status_code, 200)
        self.assertIn('id="kachel-angebots-pdf"', r.text)
        self.assertIn("Angebots-PDF", r.text)

    def test_golive_punkt_13(self):
        _einstellung_zurueck({pdf_html.EINSTELLUNG_ENGINE: "html", pdf_html.EINSTELLUNG_LETZTER_TEST: ""})
        punkte = golive.pruefen(self.s)
        self.assertEqual(len(punkte), 13)
        punkt = punkte[-1]
        self.assertEqual(punkt.titel, "Angebots-PDF: Browser-Druck grün")
        self.assertFalse(punkt.ok)
        self.assertIn("noch nicht ausgeführt", punkt.detail)
        self.assertEqual(punkt.link, "/parametrierung/angebots-pdf")
        with db.kurz() as s:
            pdf_html.letzten_test_merken(s, dict(ok=True, fehler="", dauer_ms=77, browser="msedge",
                                                 version="155.0"))
        self.s.expire_all()
        punkt = golive.pdf_punkt(self.s)
        self.assertTrue(punkt.ok)
        self.assertIn("msedge 155.0, 77 ms", punkt.detail)
        self.assertIn("Engine html", punkt.detail)
        with db.kurz() as s:
            pdf_html.engine_setzen(s, "fpdf2")
        self.s.expire_all()
        punkt = golive.pdf_punkt(self.s)
        self.assertFalse(punkt.ok)
        self.assertIn("fpdf2", punkt.detail)
        with db.kurz() as s:
            pdf_html.engine_setzen(s, "html")
            pdf_html.letzten_test_merken(s, dict(ok=False, fehler="Kein Browser", dauer_ms=1))
        self.s.expire_all()
        punkt = golive.pdf_punkt(self.s)
        self.assertFalse(punkt.ok)
        self.assertIn("fehlgeschlagen: Kein Browser", punkt.detail)
        seite = self.admin.get("/parametrierung/golive")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Angebots-PDF: Browser-Druck grün", seite.text)


if __name__ == "__main__":
    unittest.main()
