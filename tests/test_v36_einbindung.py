# v36 (PLAN_V22 Phase 190, Agent A3): Einbindung der neuen PDF-Engine in alle PDF-Wege – jede Route
# liefert ein PDF im Layout v3 (Magic %PDF, Kopfzeile „SEITE 1 VON n“), HTML-Vorschau
# GET /angebote/<id>/pdf.html nur Innendienst/Admin (Außendienst Umleitung/403, kein EK/DB im HTML),
# Vor-Ort-Signatur durch erneutes Rendern (Bild auf der Unterschriftslinie, „signiert am“ im PDF-Text),
# Rückfall-Schalter fpdf2 (altes Layout, kein Hinweis) und automatischer Rückfall mit Grund in der
# Versand-/Kombi-Meldung (Graph gemockt wie tests/test_v34_kombi.py), Kombi-Versand mit zwei PDFs im
# neuen Layout. Tests, die den echten Kontext (pdf_kontext.fuer_angebot, Agent A1) UND den Browser
# brauchen, werden übersprungen, solange eines fehlt – der Orchestrator lässt sie nach A1 erneut laufen.
# Läuft gegen DB_PFAD_OVERRIDE (Kopie), räumt eigene Daten auf (Testbasis tests/v34_e_basis.py).
import base64
import io
import re
import unittest
import warnings
from datetime import datetime
from types import SimpleNamespace
from unittest import mock
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import auth, config, db, graph_versand, kombi_versand, pdf_export, pdf_html, pdf_kontext
from app.main import app
from app.models import Angebot, AngebotsPosition, einstellung_holen, einstellung_setzen
from app.routers import angebote as angebote_router
from app.routers.signatur import fern_token_ausstellen
from tests.v34_e_basis import PV_MODULE, Basis, pdf_text

BROWSER = pdf_html.browser_test()
BROWSER_OK = BROWSER["ok"]


def _kontext_probe() -> tuple[bool, str]:
    """Liefert pdf_kontext.fuer_angebot (Phase 189, Agent A1) schon einen Kontext? Probe an einem
    Angebot der DB-Kopie – nur lesend."""
    try:
        with db.kurz(schreibend=False) as s:
            angebot = (s.query(Angebot).filter(Angebot.extern.is_(False), Angebot.konfigurator_typ == "WP")
                       .order_by(Angebot.id).first())
            if angebot is None:
                return False, "kein WP-Angebot in der DB-Kopie"
            kontext = pdf_kontext.fuer_angebot(s, angebot)
        return isinstance(kontext, dict) and "gruppen" in kontext, "Kontext ohne gruppen"
    except NotImplementedError as fehler:
        return False, str(fehler)
    except Exception as fehler:   # noqa: BLE001 – halbfertiger Kontext
        return False, f"{type(fehler).__name__}: {fehler}"


KONTEXT_OK, KONTEXT_GRUND = _kontext_probe()
LAYOUT_OK = BROWSER_OK and KONTEXT_OK and pdf_html.vorlage_vorhanden("WP")
LAYOUT_GRUND = (f"Browser: {BROWSER['fehler'] or 'ok'} · Kontext: {KONTEXT_GRUND or 'ok'} · "
                f"Vorlage WP: {'ja' if pdf_html.vorlage_vorhanden('WP') else 'fehlt'}")


def _png_data_url() -> str:
    from PIL import Image, ImageDraw
    bild = Image.new("RGBA", (260, 90), (255, 255, 255, 0))
    ImageDraw.Draw(bild).line([(10, 70), (70, 20), (130, 70), (220, 25)], fill=(20, 20, 60, 255), width=5)
    puffer = io.BytesIO()
    bild.save(puffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(puffer.getvalue()).decode("ascii")


def _text(daten: bytes) -> str:
    return "\n".join((s.extract_text() or "") for s in PdfReader(io.BytesIO(daten)).pages)


class _Engine(Basis):
    """Basis + Engine-Schalter: jeder Test startet mit Engine html, Sicherung am Ende."""
    EMAIL = "v36a3-einbindung@test.local"
    NACHNAME = "V36A3 Einbindung"
    AD_NAME = "V36A3 Einbindung-AD"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with db.kurz(schreibend=False) as s:
            cls.engine_vorher = einstellung_holen(s, pdf_html.EINSTELLUNG_ENGINE, "")

    @classmethod
    def _spuren_loeschen(cls):
        """Verlaufsnotizen (AngebotsNotiz) und Rückfall-Merker der eigenen Angebote entfernen – die
        Testbasis löscht nur die Angebote; SQLite vergibt IDs neu, stehengebliebene Notizen „durch
        Kombi-Versand“ würden sonst in tests/test_v34_kombi.py an fremden Angeboten auftauchen."""
        from app.models import AngebotsNotiz
        cls.s.rollback()
        for a in cls.s.query(Angebot).filter_by(kunde_id=cls.kunde.id):
            cls.s.query(AngebotsNotiz).filter(AngebotsNotiz.angebot_id == a.id).delete(
                synchronize_session=False)
            pdf_export._rueckfall_loeschen(a.id)
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        cls._spuren_loeschen()
        with db.kurz() as s:
            einstellung_setzen(s, pdf_html.EINSTELLUNG_ENGINE, cls.engine_vorher)
        super().tearDownClass()

    def setUp(self):
        self._spuren_loeschen()
        super().setUp()
        with db.kurz() as s:
            pdf_html.engine_setzen(s, "html")

    def _engine(self, wert: str) -> None:
        with db.kurz() as s:
            pdf_html.engine_setzen(s, wert)

    def _graph_mocks(self, aufrufe: dict):
        """Graph wie in tests/test_v34_kombi.py gemockt – kein Netz, Entwurf „erfolgreich“."""
        def fake_entwurf(kunde, angebot_, pdf_pfad, betreff, text, **kw):
            aufrufe.update(kw, betreff=betreff, text=text, pdf=pdf_pfad, angebot=angebot_)
            return True, "Entwurf im Postfach abgelegt – Test.", "https://outlook/x", "konv-v36-a3"

        return (mock.patch.object(graph_versand, "konfiguriert", return_value=True),
                mock.patch.object(graph_versand, "verbunden", return_value=True),
                mock.patch.object(graph_versand, "angemeldeter_benutzer", return_value="ida@friondo.de"),
                mock.patch.object(graph_versand, "entwurf_erstellen", side_effect=fake_entwurf),
                mock.patch("app.anhaenge.fuer_angebot", return_value=[]))


# ----------------------------------------------------------------------------- Routen (echter Druck)
@unittest.skipUnless(LAYOUT_OK, LAYOUT_GRUND)
class PdfRouten(_Engine):
    def _pdf_pruefen(self, antwort, nummer: str):
        self.assertEqual(antwort.status_code, 200, antwort.text[:200])
        self.assertTrue(antwort.content.startswith(b"%PDF"))
        text = _text(antwort.content)
        self.assertIn("SEITE 1 VON", text)        # Kopfzeile der neuen Engine
        self.assertIn(nummer, text)
        return text

    def test_alle_pdf_routen_neue_engine(self):
        wp = self.wp_entwurf()
        # Editor-Vorschau/Download (Innendienst/Admin)
        self._pdf_pruefen(self.client.get(f"/angebote/{wp.id}/pdf"), wp.nummer)
        self.assertEqual(pdf_export.letzter_rueckfall(wp.id), "")
        # Signatur-Vorschau (Vor-Ort-Modus)
        self._pdf_pruefen(self.client.get(f"/signatur/{wp.id}/pdf"), wp.nummer)
        # Außendienst „Meine Angebote“ (eigenes Angebot über vertriebler_id)
        text = self._pdf_pruefen(self.ad_client().get(f"/meine-angebote/{wp.id}/pdf"), wp.nummer)
        self.assertNotIn("Deckungsbeitrag", text)
        # Fern-Signatur-Anzeige (Token-Link, ohne Anmeldung)
        with db.kurz() as s:
            einstellung_setzen(s, "signatur_fern_aktiv", "1")
            a = s.get(Angebot, wp.id)
            token = fern_token_ausstellen(s, a)
        try:
            self._pdf_pruefen(TestClient(app).get(f"/signatur/extern/{token}/pdf"), wp.nummer)
        finally:
            with db.kurz() as s:
                einstellung_setzen(s, "signatur_fern_aktiv", "0")
        # Kombi-Anhang und Projektablage/Nachfassen nutzen dieselbe Funktion
        pfad = kombi_versand.pdf_fuer(self.s, self.neu(wp.id))
        self.assertIn("SEITE 1 VON", pdf_text(pfad))
        self.assertEqual(pfad, pdf_export.pdf_zielpfad(wp))

    def test_html_vorschau_nur_innendienst_admin(self):
        wp = self.wp_entwurf()
        r = self.client.get(f"/angebote/{wp.id}/pdf.html")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["content-type"].startswith("text/html"))
        html = r.text
        self.assertIn("<html", html)
        self.assertIn(wp.nummer, html)
        self.assertIn('href="/static/pdf/angebot.css"', html)      # Web-Mount statt file://
        self.assertNotIn("file:///", html)
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("Deckungsbeitrag", html)
        self.assertNotRegex(html, r"\bEK\b")
        self.assertNotIn("ek_cent", html)
        # Editor verlinkt die Vorschau (nur Innendienst/Admin)
        editor = self.client.get(f"/angebote/{wp.id}").text
        self.assertIn(f'href="/angebote/{wp.id}/pdf.html"', editor)
        # Außendienst: Middleware leitet um (kein Inhalt), Route selbst antwortet 403
        r = self.ad_client().get(f"/angebote/{wp.id}/pdf.html", follow_redirects=False)
        self.assertIn(r.status_code, (303, 403))
        self.assertNotIn("<html", r.text)
        anfrage = SimpleNamespace(state=SimpleNamespace(benutzer=self.ad), query_params={})
        antwort = angebote_router.pdf_html_vorschau(anfrage, wp.id, self.s)
        self.assertEqual(antwort.status_code, 403)
        # interne Fassung und Demo-Signaturzeile
        r = self.client.get(f"/angebote/{wp.id}/pdf.html?fassung=intern&signatur=demo")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Max Mustermann", r.text)

    def test_html_vorschau_externer_eintrag(self):
        extern = Angebot(nummer="EXT-V36A3", kunde_id=self.kunde.id, extern=True, status="Versendet (extern)",
                         datum=datetime.now(), konfigurator_typ="WP", extern_endbetrag_cent=100,
                         vorgang_id=self.vorgang.id)
        self.s.add(extern)
        self.s.commit()
        r = self.client.get(f"/angebote/{extern.id}/pdf.html", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Externer+Eintrag+ohne+PDF", r.headers["location"])


# ----------------------------------------------------------------------------- Signatur (echter Druck)
@unittest.skipUnless(LAYOUT_OK, LAYOUT_GRUND)
class Signatur(_Engine):
    def test_vor_ort_signatur_rendert_neu(self):
        wp = self.wp_entwurf()
        daten_url = _png_data_url()
        # HTML mit Signatur: Bild als data:-URL im Dokument, Zeile „signiert am“
        signatur = pdf_export.signatur_dict(base64.b64decode(daten_url.split(",", 1)[1]), "Erika Beispiel",
                                            datetime(2026, 10, 16, 14, 30), "Tablet")
        html = pdf_html.angebot_html(self.s, self.neu(wp.id), signatur=signatur)
        self.assertIn(daten_url[:60], html)
        self.assertIn("Erika Beispiel", html)
        self.assertIn("16.10.2026 14:30", html)
        # Vor-Ort-Signatur über die Route (Admin)
        r = self.client.post(f"/signatur/{wp.id}", data={"name": "Erika Beispiel", "signatur": daten_url})
        self.assertEqual(r.status_code, 200, r.text[:300])
        a = self.neu(wp.id)
        self.assertEqual(a.status, "Angenommen")
        self.assertEqual(a.signatur_name, "Erika Beispiel")
        self.assertIn("Unterzeichner: Erika Beispiel", a.signatur_protokoll)
        pfad = config.SIGNIERT_ORDNER / f"{wp.nummer}-signiert.pdf"
        try:
            self.assertEqual(a.signierte_datei, str(pfad))
            self.assertTrue(pfad.is_file())
            daten = pfad.read_bytes()
            self.assertTrue(daten.startswith(b"%PDF"))
            text = _text(daten)
            self.assertIn("SEITE 1 VON", text)
            self.assertIn("signiert am", text)
            self.assertIn("Erika Beispiel", text)
            self.assertEqual(pdf_export.letzter_rueckfall(wp.id), "")
            # signiertes PDF ist über die Route abrufbar
            r = self.client.get(f"/signatur/{wp.id}/signiert.pdf")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.content[:5], b"%PDF-")
        finally:
            pfad.unlink(missing_ok=True)


# ----------------------------------------------------------------------------- Benutzer + Fern-Signatur-Token (Nachtrag, ohne Browser)
class BenutzerUndToken(_Engine):
    """Nachtrag 16.10.2026 (5)/(6): der angemeldete Benutzer geht aus „Versand vorbereiten“ (Einzel +
    Kombi) und der HTML-Vorschau bis in pdf_kontext.fuer_angebot (Ansprechpartner-Rückfall); der
    Fern-Signatur-Token entsteht bei aktiver Fern-Signatur und BASIS_URL aus der .env VOR dem Druck
    (Knopf „Jetzt online beauftragen“), sonst wie bisher erst danach für die Mail (PDF-Knopf mailto)."""

    def setUp(self):
        super().setUp()
        with db.kurz() as s:
            einstellung_setzen(s, "signatur_fern_aktiv", "0")

    @classmethod
    def tearDownClass(cls):
        with db.kurz() as s:
            einstellung_setzen(s, "signatur_fern_aktiv", "0")
        super().tearDownClass()

    def _fern(self, an: bool) -> None:
        with db.kurz() as s:
            einstellung_setzen(s, "signatur_fern_aktiv", "1" if an else "0")

    def test_benutzer_bis_in_den_kontext(self):
        wp = self.wp_entwurf()
        pv = self.pv_entwurf()
        gesehen = []

        def fake_pdf(session, angebot, *, signatur=None, fassung="kunde", benutzer=None):
            gesehen.append((angebot.id, getattr(benutzer, "id", None)))
            return b"%PDF-1.4 x"

        aufrufe = {}
        mocks = self._graph_mocks(aufrufe)
        with mocks[0], mocks[1], mocks[2], mocks[3], mocks[4], \
                mock.patch.object(pdf_html, "angebot_pdf", side_effect=fake_pdf):
            r = self.client.post(f"/angebote/{wp.id}/email", follow_redirects=False)        # Einzel
            self.assertEqual(r.status_code, 303)
            r = self.client.post(f"/vorgaenge/{self.vorgang.id}/kombi-versand",            # Kombi
                                 data={"angebot_ids": [str(wp.id), str(pv.id)]}, follow_redirects=False)
            self.assertEqual(r.status_code, 303)
        self.assertEqual(gesehen, [(wp.id, 1), (wp.id, 1), (pv.id, 1)])      # Admin (ID 1) als Benutzer
        # HTML-Vorschau übergibt den angemeldeten Benutzer und den Web-Mount
        kw_gesehen = {}

        def fake_html(session, angebot, **kw):
            kw_gesehen.update(kw)
            return "<html><body>Vorschau</body></html>"

        with mock.patch.object(pdf_html, "angebot_html", side_effect=fake_html):
            r = self.client.get(f"/angebote/{wp.id}/pdf.html")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((kw_gesehen["benutzer"].id, kw_gesehen["static_url"], kw_gesehen["fassung"]),
                         (1, "/static", "kunde"))
        # Einstiegspunkte und Engine reichen `benutzer` bis in pdf_kontext.fuer_angebot durch
        with mock.patch.object(pdf_html, "angebot_pdf", side_effect=fake_pdf):
            pdf_export.pdf_fuer_angebot(self.s, self.neu(wp.id), benutzer=self.ad)
            pfad = pdf_export.signiertes_pdf_erzeugen(self.s, self.neu(wp.id), b"\x89PNG" + b"\x00" * 300,
                                                      "Max", datetime(2026, 10, 16, 14, 30), benutzer=self.ad)
        pfad.unlink(missing_ok=True)
        self.assertEqual(gesehen[-2:], [(wp.id, self.ad.id), (wp.id, self.ad.id)])
        kontext_kw = {}

        def fake_kontext(session, angebot, **kw):
            kontext_kw.update(kw)
            return pdf_kontext.demo_kontext("WP")

        with mock.patch.object(pdf_kontext, "fuer_angebot", side_effect=fake_kontext), \
                mock.patch.object(pdf_html, "pdf_aus_kontext", return_value=b"%PDF-1.4 y"):
            pdf_html.angebot_pdf(self.s, self.neu(wp.id), benutzer=self.ad)
        self.assertIs(kontext_kw["benutzer"], self.ad)
        with mock.patch.object(pdf_kontext, "fuer_angebot", side_effect=fake_kontext):
            pdf_html.angebot_html(self.s, self.neu(wp.id), benutzer=self.ad, static_url="/static")
        self.assertIs(kontext_kw["benutzer"], self.ad)
        # ohne Übergabe (übrige Aufrufer): None – Rückfall wie heute
        with mock.patch.object(pdf_html, "angebot_pdf", side_effect=fake_pdf):
            self.client.get(f"/angebote/{wp.id}/pdf")
        self.assertEqual(gesehen[-1], (wp.id, None))

    def test_token_vor_dem_druck_mit_basis_url(self):
        wp = self.wp_entwurf()
        self._fern(True)
        beim_druck = {}

        def fake_pdf(session, angebot, *, signatur=None, fassung="kunde", benutzer=None):
            beim_druck["token"] = angebot.signatur_token
            beim_druck["gueltig"] = angebot.signatur_token_gueltig_bis
            beim_druck["in_db"] = session.query(Angebot).filter_by(id=angebot.id).one().signatur_token
            return b"%PDF-1.4 x"

        aufrufe = {}
        mocks = self._graph_mocks(aufrufe)
        with mock.patch.object(config, "BASIS_URL_AUS_ENV", True), \
                mock.patch.object(config, "BASIS_URL", "https://angebot.friondo.de"), \
                mocks[0], mocks[1], mocks[2], mocks[3], mocks[4], \
                mock.patch.object(pdf_html, "angebot_pdf", side_effect=fake_pdf):
            r = self.client.post(f"/angebote/{wp.id}/email", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        token = beim_druck["token"]
        self.assertTrue(token, "Token lag beim Druck nicht vor")
        self.assertEqual(beim_druck["in_db"], token)          # vor dem Druck committet
        self.assertGreater(beim_druck["gueltig"], datetime.now())
        a = self.neu(wp.id)
        self.assertEqual(a.signatur_token, token)             # kein zweiter Token nach dem Druck
        self.assertIn(f"https://angebot.friondo.de/signatur/extern/{token}", aufrufe["text"])
        self.assertEqual(a.status, "Versand vorbereitet")
        # mit echtem Kontext: Knopf „Jetzt online beauftragen“ trägt den Link
        if KONTEXT_OK and pdf_html.vorlage_vorhanden("WP"):
            with mock.patch.object(config, "BASIS_URL_AUS_ENV", True), \
                    mock.patch.object(config, "BASIS_URL", "https://angebot.friondo.de"):
                html = pdf_html.angebot_html(self.s, a, static_url="/static", benutzer=None)
            self.assertIn(f"https://angebot.friondo.de/signatur/extern/{token}", html)
            self.assertIn("Jetzt online beauftragen", html)
            self.assertNotIn("Per E-Mail beauftragen", html)

    def test_token_ohne_basis_url_erst_nach_dem_druck(self):
        wp = self.wp_entwurf()
        self._fern(True)
        beim_druck = {}

        def fake_pdf(session, angebot, *, signatur=None, fassung="kunde", benutzer=None):
            beim_druck["token"] = angebot.signatur_token
            return b"%PDF-1.4 x"

        aufrufe = {}
        mocks = self._graph_mocks(aufrufe)
        with mock.patch.object(config, "BASIS_URL_AUS_ENV", False), \
                mocks[0], mocks[1], mocks[2], mocks[3], mocks[4], \
                mock.patch.object(pdf_html, "angebot_pdf", side_effect=fake_pdf):
            r = self.client.post(f"/angebote/{wp.id}/email", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIsNone(beim_druck["token"])                 # wie bisher: Token erst nach dem Druck
        a = self.neu(wp.id)
        self.assertTrue(a.signatur_token)
        self.assertIn(f"/signatur/extern/{a.signatur_token}", aufrufe["text"])   # Mail-Link wie bisher
        if KONTEXT_OK and pdf_html.vorlage_vorhanden("WP"):
            with mock.patch.object(config, "BASIS_URL_AUS_ENV", False):
                html = pdf_html.angebot_html(self.s, a, static_url="/static")
            self.assertIn("Per E-Mail beauftragen", html)      # ohne BASIS_URL aus der .env: mailto
            self.assertNotIn("/signatur/extern/", html)
        # Fern-Signatur aus: gar kein Token
        self._fern(False)
        wp2 = self.pv_entwurf()
        with mock.patch.object(config, "BASIS_URL_AUS_ENV", True), \
                mocks[0], mocks[1], mocks[2], mocks[3], mocks[4], \
                mock.patch.object(pdf_html, "angebot_pdf", side_effect=fake_pdf):
            self.client.post(f"/angebote/{wp2.id}/email", follow_redirects=False)
        self.assertIsNone(beim_druck["token"])
        self.assertIsNone(self.neu(wp2.id).signatur_token)


# ----------------------------------------------------------------------------- Rückfall (ohne Browser)
class Rueckfall(_Engine):
    def test_schalter_fpdf2_altes_layout_alle_routen(self):
        wp = self.wp_entwurf()
        self._engine("fpdf2")
        with mock.patch.object(pdf_html, "angebot_pdf") as m:
            r = self.client.get(f"/angebote/{wp.id}/pdf")
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.content.startswith(b"%PDF"))
            self.assertNotIn("SEITE 1 VON", _text(r.content))
            r = self.ad_client().get(f"/meine-angebote/{wp.id}/pdf")
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("SEITE 1 VON", _text(r.content))
        m.assert_not_called()
        self.assertEqual(pdf_export.letzter_rueckfall(wp.id), "")

    def test_versand_meldung_nennt_rueckfall(self):
        wp = self.wp_entwurf()
        aufrufe = {}
        mocks = self._graph_mocks(aufrufe)
        with mocks[0], mocks[1], mocks[2], mocks[3], mocks[4], \
                mock.patch.object(pdf_html, "angebot_pdf",
                                  side_effect=pdf_html.PdfDruckFehler("Browser fehlt (Test)")):
            r = self.client.post(f"/angebote/{wp.id}/email", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        ziel = unquote_plus(r.headers["location"])
        self.assertIn("PDF im alten Layout erzeugt (Browser-Druck fehlgeschlagen: Browser fehlt (Test))", ziel)
        self.assertIn("versand=1", ziel)
        self.assertEqual(aufrufe["pdf"], pdf_export.pdf_zielpfad(wp))
        self.assertTrue(aufrufe["pdf"].read_bytes().startswith(b"%PDF"))
        self.assertEqual(self.neu(wp.id).status, "Versand vorbereitet")
        # gelungener Druck danach → kein Hinweis mehr
        with mocks[0], mocks[1], mocks[2], mocks[3], mocks[4], \
                mock.patch.object(pdf_html, "angebot_pdf", return_value=b"%PDF-1.4 v3"):
            r = self.client.post(f"/angebote/{wp.id}/email", follow_redirects=False)
        self.assertNotIn("alten Layout", unquote_plus(r.headers["location"]))
        # Schalter fpdf2: altes Layout ohne Hinweis
        self._engine("fpdf2")
        with mocks[0], mocks[1], mocks[2], mocks[3], mocks[4]:
            r = self.client.post(f"/angebote/{wp.id}/email", follow_redirects=False)
        self.assertNotIn("alten Layout", unquote_plus(r.headers["location"]))

    def test_kombi_meldung_nennt_rueckfall_je_angebot(self):
        wp = self.wp_entwurf()
        pv = self.pv_entwurf()
        aufrufe = {}
        mocks = self._graph_mocks(aufrufe)
        with mocks[0], mocks[1], mocks[2], mocks[3], mocks[4], \
                mock.patch.object(pdf_html, "angebot_pdf",
                                  side_effect=pdf_html.PdfDruckFehler("Zeitüberschreitung (Test)")):
            r = self.client.post(f"/vorgaenge/{self.vorgang.id}/kombi-versand",
                                 data={"angebot_ids": [str(wp.id), str(pv.id)]}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        ziel = unquote_plus(r.headers["location"])
        self.assertIn("Kombi-Entwurf für", ziel)
        for nummer in (wp.nummer, pv.nummer):
            self.assertIn(f"{nummer}: PDF im alten Layout erzeugt (Browser-Druck fehlgeschlagen: "
                          "Zeitüberschreitung (Test))", ziel)
        self.assertEqual(len(aufrufe["weitere_anhaenge"]), 1)


# ----------------------------------------------------------------------------- Archiv (Nachtrag 16.10.2026, ohne Browser)
class Archiv(_Engine):
    """Entscheidung Orchestrator (Plan Phase 190 „Archiv bleibt“): bei Status Versendet, Angenommen,
    Abgelehnt, Überholt (und Versendet (extern)) bleibt eine vorhandene Datei unter data/angebote/
    unverändert – kein Neu-Rendern, egal welche Engine; Entwurf und „Versand vorbereitet“ rendern je
    Aufruf neu; fehlende Altbestands-Dateien werden einmal erzeugt."""

    def _status(self, angebot_id: int, status: str) -> Angebot:
        a = self.neu(angebot_id)
        a.status = status
        self.s.commit()
        return a

    def test_versendet_bleibt_byteidentisch(self):
        wp = self.wp_entwurf()
        zaehler = {"n": 0}

        def fake(session, angebot, *, signatur=None, fassung="kunde", **kw):
            zaehler["n"] += 1
            return b"%PDF-1.4 render " + str(zaehler["n"]).encode()

        with mock.patch.object(pdf_html, "angebot_pdf", side_effect=fake):
            pfad = pdf_export.pdf_fuer_angebot(self.s, wp)       # Entwurf → gerendert (1)
            self.assertEqual(pfad.read_bytes(), b"%PDF-1.4 render 1")
            a = self._status(wp.id, "Versendet")
            self.assertEqual(pdf_export.pdf_eingefroren(a), pfad)
            vorher = (pfad.read_bytes(), pfad.stat().st_mtime_ns)
            pdf_export._rueckfall_merken(a.id, "alt")
            self.assertEqual(pdf_export.pdf_fuer_angebot(self.s, a), pfad)   # kein Render
            self.assertEqual((pfad.read_bytes(), pfad.stat().st_mtime_ns), vorher)
            self.assertEqual(zaehler["n"], 1)
            self.assertEqual(pdf_export.letzter_rueckfall(a.id), "")       # kein Hinweis
            for status in ("Angenommen", "Abgelehnt", "Überholt", "Versendet (extern)"):
                a = self._status(wp.id, status)
                self.assertEqual(pdf_export.pdf_fuer_angebot(self.s, a), pfad, status)
                self.assertEqual(pfad.read_bytes(), b"%PDF-1.4 render 1", status)
            self.assertEqual(zaehler["n"], 1)
            # Route liefert dieselbe Archivdatei
            a = self._status(wp.id, "Versendet")
            r = self.client.get(f"/angebote/{wp.id}/pdf")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.content, b"%PDF-1.4 render 1")
            # Engine fpdf2: ebenfalls keine Neuerzeugung
            self._engine("fpdf2")
            self.assertEqual(pdf_export.pdf_fuer_angebot(self.s, self.neu(wp.id)).read_bytes(),
                             b"%PDF-1.4 render 1")
            self._engine("html")
            # Altbestand ohne Datei: einmal erzeugen, danach eingefroren
            pfad.unlink()
            self.assertIsNone(pdf_export.pdf_eingefroren(self.neu(wp.id)))
            self.assertEqual(pdf_export.pdf_fuer_angebot(self.s, self.neu(wp.id)).read_bytes(),
                             b"%PDF-1.4 render 2")
            self.assertEqual(pdf_export.pdf_fuer_angebot(self.s, self.neu(wp.id)).read_bytes(),
                             b"%PDF-1.4 render 2")
            self.assertEqual(zaehler["n"], 2)
            # leere Datei gilt nicht als Archiv
            pfad.write_bytes(b"")
            self.assertEqual(pdf_export.pdf_fuer_angebot(self.s, self.neu(wp.id)).read_bytes(),
                             b"%PDF-1.4 render 3")
            # „Versand vorbereitet“ rendert wieder je Aufruf
            a = self._status(wp.id, "Versand vorbereitet")
            self.assertEqual(pdf_export.pdf_fuer_angebot(self.s, a).read_bytes(), b"%PDF-1.4 render 4")
            self.assertEqual(pdf_export.pdf_fuer_angebot(self.s, a).read_bytes(), b"%PDF-1.4 render 5")
        pfad.unlink(missing_ok=True)

    def test_entwurf_wird_neu_gerendert(self):
        wp = self.wp_entwurf()
        with mock.patch.object(pdf_html, "angebot_pdf", side_effect=[b"%PDF-1.4 a", b"%PDF-1.4 b"]):
            pfad = pdf_export.pdf_fuer_angebot(self.s, wp)
            self.assertEqual(pfad.read_bytes(), b"%PDF-1.4 a")
            self.assertIsNone(pdf_export.pdf_eingefroren(wp))
            self.assertEqual(pdf_export.pdf_fuer_angebot(self.s, wp).read_bytes(), b"%PDF-1.4 b")
        # signierte PDFs bleiben eigene Dateien – das Archiv-Kennzeichen gilt nur für data/angebote/<Nr>.pdf
        self.assertEqual(pdf_export.signiert_zielpfad(wp).parent, config.SIGNIERT_ORDNER)
        pfad.unlink(missing_ok=True)


# ----------------------------------------------------------------------------- Kombi-Versand (echter Druck)
@unittest.skipUnless(LAYOUT_OK, LAYOUT_GRUND)
class Kombi(_Engine):
    def test_kombi_zwei_pdfs_neues_layout(self):
        wp = self.wp_entwurf()
        pv = self.pv_entwurf()
        aufrufe = {}

        def fake_entwurf(kunde, angebot_, pdf_pfad, betreff, text, **kw):
            aufrufe.update(kw, betreff=betreff, pdf=pdf_pfad, angebot=angebot_)
            return True, "Entwurf im Postfach abgelegt – Test.", "https://outlook/x", "konv-v36-kombi"

        with mock.patch.object(graph_versand, "konfiguriert", return_value=True), \
                mock.patch.object(graph_versand, "verbunden", return_value=True), \
                mock.patch.object(graph_versand, "angemeldeter_benutzer", return_value="ida@friondo.de"), \
                mock.patch.object(graph_versand, "entwurf_erstellen", side_effect=fake_entwurf), \
                mock.patch("app.anhaenge.fuer_angebot", return_value=[]):
            r = self.client.post(f"/vorgaenge/{self.vorgang.id}/kombi-versand",
                                 data={"angebot_ids": [str(wp.id), str(pv.id)]}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        ziel = unquote_plus(r.headers["location"])
        self.assertIn("Kombi-Entwurf für", ziel)
        self.assertNotIn("alten Layout", ziel)
        pdfs = [aufrufe["pdf"]] + list(aufrufe["weitere_anhaenge"])
        self.assertEqual(sorted(p.name for p in pdfs), sorted([f"{wp.nummer}.pdf", f"{pv.nummer}.pdf"]))
        for pfad in pdfs:
            self.assertTrue(pfad.read_bytes().startswith(b"%PDF"))
            self.assertIn("SEITE 1 VON", pdf_text(pfad))
        pv_text = pdf_text(aufrufe["pdf"] if aufrufe["pdf"].name == f"{pv.nummer}.pdf"
                           else aufrufe["weitere_anhaenge"][0])
        self.assertIn("0,00 % USt", pv_text)
        self.assertEqual((self.neu(wp.id).status, self.neu(pv.id).status),
                         ("Versand vorbereitet", "Versand vorbereitet"))


if __name__ == "__main__":
    unittest.main()
