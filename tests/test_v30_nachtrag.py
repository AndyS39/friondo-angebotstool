# v30-Nachtrag 12.10.2026: Entscheidungen zu den Rückfragen des Durchlaufs und der Befund
# „Drag & Drop im Kanban-Board tut nichts“ (Andreas, Vorschau 12.10.2026).
# - Jinja `tojson` in DOPPELT gequoteten on*-Attributen: die Anführungszeichen des JSON
#   beendeten das Attribut (Browser: „Unexpected end of input“) – seit v17 am Board
#   (ondragstart mit Sparten-Liste), außerdem Editor (Zahlungsbedingung v30, Abbrechen-Knopf,
#   Kanal-Prompt), TAIFUN-Eintrag und BzA-Kopierknöpfe. Jetzt `tojson | forceescape`.
# - Kennzahlen der Angebotstool-Karte in Blau (Entscheidung 2), Zahlungsbedingung lesend
#   für den Außendienst (Entscheidung 9), Demo-Badge auf der Board-Karte (Entscheidung 23).
import re
import unittest

from fastapi.testclient import TestClient

from app import auth
from app.db import SessionLocal
from app.main import app
from app.models import Angebot, Benutzer, Gewerk, Projekt


def _admin_client() -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
    return c


class AttributeMitJson(unittest.TestCase):
    """Kein on*-Attribut darf durch JSON-Anführungszeichen abgeschnitten sein."""

    ATTRIBUT = re.compile(r'\son[a-z]+="([^"]*)"')

    def _attribute_pruefen(self, html: str, seite: str) -> None:
        for wert in self.ATTRIBUT.findall(html):
            # ein abgeschnittenes Attribut endet mitten im Aufruf: offene Klammer ohne Schluss
            self.assertEqual(wert.count("("), wert.count(")"),
                             f"{seite}: on*-Attribut abgeschnitten: {wert[:80]}")
            self.assertEqual(wert.count("["), wert.count("]"),
                             f"{seite}: on*-Attribut abgeschnitten: {wert[:80]}")

    def test_board_ondragstart_vollstaendig(self):
        s = SessionLocal()
        try:
            projekt = s.query(Projekt).first()
        finally:
            s.close()
        if projekt is None:
            self.skipTest("kein Projekt in der Datenbank")
        antwort = _admin_client().get("/projektierung")
        self.assertEqual(antwort.status_code, 200)
        self._attribute_pruefen(antwort.text, "/projektierung")
        treffer = re.findall(r'ondragstart="kartenStart\(event, \[[^"]*\], \[[^"]*\]\)"', antwort.text)
        self.assertTrue(treffer, "ondragstart der Board-Karten fehlt oder ist abgeschnitten")
        # markupsafe kodiert das Anführungszeichen als &#34; (gleichwertig zu &quot;)
        self.assertTrue("&#34;" in treffer[0] or "&quot;" in treffer[0],
                        "Sparten-Liste muss HTML-escaped sein (&#34;/&quot;)")

    def test_editor_attribute_vollstaendig(self):
        s = SessionLocal()
        try:
            angebot = (s.query(Angebot).filter(Angebot.extern.is_(False), Angebot.archiviert.is_(False),
                                               Angebot.status == "Entwurf")
                       .order_by(Angebot.id.desc()).first())
        finally:
            s.close()
        if angebot is None:
            self.skipTest("kein Entwurf in der Datenbank")
        antwort = _admin_client().get(f"/angebote/{angebot.id}")
        self.assertEqual(antwort.status_code, 200)
        self._attribute_pruefen(antwort.text, "Editor")
        self.assertTrue("zbFreitextUmschalten(this.value === &#34;freitext&#34;)" in antwort.text
                        or "zbFreitextUmschalten(this.value === &quot;freitext&quot;)" in antwort.text,
                        "Zahlungsbedingungs-Auswahl: JSON im onchange-Attribut muss escaped sein")

    def test_bza_gewerkseite_kopierknoepfe(self):
        s = SessionLocal()
        try:
            gewerk = (s.query(Gewerk).filter(Gewerk.sparte == "WP").order_by(Gewerk.id).first())
        finally:
            s.close()
        if gewerk is None:
            self.skipTest("kein WP-Gewerk")
        antwort = _admin_client().get(f"/projektierung/gewerk/{gewerk.id}/bza")
        if antwort.status_code != 200:
            self.skipTest(f"Gewerk-BzA-Seite nicht erreichbar ({antwort.status_code})")
        self._attribute_pruefen(antwort.text, "Gewerk-BzA")


class Entscheidungen(unittest.TestCase):

    def test_portal_kennzahlen_blau(self):
        antwort = _admin_client().get("/")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn('class="stat-zahl blau"', antwort.text)
        antwort = _admin_client().get("/angebotstool")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn('class="stat-zahl blau"', antwort.text)

    def test_aussendienst_sieht_zahlungsbedingung(self):
        s = SessionLocal()
        try:
            ad = s.query(Benutzer).filter(Benutzer.rolle == "aussendienst", Benutzer.aktiv.is_(True)).first()
            angebot = None
            if ad is not None:
                angebot = (s.query(Angebot).filter(Angebot.vertriebler_id == ad.id, Angebot.extern.is_(False))
                           .order_by(Angebot.id.desc()).first())
        finally:
            s.close()
        if ad is None or angebot is None:
            self.skipTest("kein Außendienst-Angebot")
        c = TestClient(app, follow_redirects=False)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(ad.id))
        antwort = c.get(f"/meine-angebote/{angebot.id}")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Zahlungsbedingung:", antwort.text)

    def test_demo_badge_auf_board_karte(self):
        s = SessionLocal()
        try:
            from app.models import Kunde
            demo = s.query(Kunde).filter(Kunde.nachname.like("Demo %")).first()
        finally:
            s.close()
        if demo is None:
            self.skipTest("keine Demo-Projekte in der Datenbank")
        antwort = _admin_client().get("/projektierung")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn('class="demo-badge"', antwort.text)


if __name__ == "__main__":
    unittest.main()
