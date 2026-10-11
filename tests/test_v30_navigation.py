# v30 (PLAN_V18 Phase 147): Zurück-Navigation „eine Ansicht zurück“.
# Teil 1 (TestClient): Knopf nur auf Detail-/Bearbeitungsseiten, Standard-
# Rücksprungseite je Route, navigation.js eingebunden; Teil 2 (Headless-Chrome,
# Ersatz für den Playwright-Lauf): Verlauf im sessionStorage – Vorgangsakte →
# Angebot → Zurück landet in der Vorgangsakte; Angebot → „Speichern“ (Umleitung
# auf dieselbe Seite) → Zurück landet in der Vorgangsakte; Direktaufruf → Zurück =
# Angebotsliste. Teil 2 läuft nur, wenn Chrome installiert ist (sonst skip).
import asyncio
import base64
import json
import os
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from fastapi.testclient import TestClient

from app import auth
from app.db import SessionLocal
from app.main import app
from app.models import Angebot, Erfassung

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT, CDP = 8138, 9348
STANDARD_RE = re.compile(r'data-zurueck-standard="([^"]+)"')


def _ziele():
    s = SessionLocal()
    try:
        angebot = (s.query(Angebot)
                   .filter(Angebot.archiviert.is_(False), Angebot.vorgang_id.isnot(None))
                   .order_by(Angebot.id.desc()).first())
        erfassung = s.query(Erfassung).order_by(Erfassung.id.desc()).first()
        return (angebot.id if angebot else None, angebot.vorgang_id if angebot else None,
                erfassung.id if erfassung else None)
    finally:
        s.close()


class ZurueckKnopfSeiten(unittest.TestCase):
    """Teil 1: Markup aus base.html (Knopf, Ausnahmen, Standardziele)."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, follow_redirects=False)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        cls.angebot_id, cls.vorgang_id, cls.erfassung_id = _ziele()

    def _standard(self, pfad: str):
        antwort = self.client.get(pfad)
        self.assertEqual(antwort.status_code, 200, pfad)
        treffer = STANDARD_RE.findall(antwort.text)
        return treffer[0] if treffer else None

    def test_startseite_und_modulstartseiten_ohne_knopf(self):
        for pfad in ("/", "/angebotstool", "/projektierung", "/montage"):
            antwort = self.client.get(pfad)
            if antwort.status_code == 200:
                self.assertNotIn("zurueck-knopf", antwort.text, pfad)

    def test_login_ohne_knopf(self):
        ohne = TestClient(app, follow_redirects=False)
        antwort = ohne.get("/login")
        self.assertEqual(antwort.status_code, 200)
        self.assertNotIn("zurueck-knopf", antwort.text)

    def test_erfassungsbogen_ohne_knopf(self):
        if not self.erfassung_id:
            self.skipTest("keine Erfassung in der Datenbank")
        ad = TestClient(app, follow_redirects=False)
        ad.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(3))
        for pfad in (f"/erfassung/{self.erfassung_id}/pruefen", "/erfassung"):
            antwort = ad.get(pfad)
            if antwort.status_code == 200:
                self.assertNotIn("zurueck-knopf", antwort.text, pfad)
        antwort = self.client.get(f"/erfassung/{self.erfassung_id}/pruefen")
        if antwort.status_code == 200:
            self.assertNotIn("zurueck-knopf", antwort.text)

    def test_angebot_standard_angebotsliste(self):
        if not self.angebot_id:
            self.skipTest("kein Angebot")
        self.assertEqual(self._standard(f"/angebote/{self.angebot_id}"), "/angebote")

    def test_vorgangsakte_standard_leads(self):
        if not self.vorgang_id:
            self.skipTest("kein Vorgang")
        self.assertEqual(self._standard(f"/vorgaenge/{self.vorgang_id}"), "/leads")

    def test_parametrierung_unterseite(self):
        self.assertEqual(self._standard("/parametrierung/betrieb"), "/parametrierung")

    def test_eingebettete_seite_ohne_knopf(self):
        if not self.vorgang_id:
            self.skipTest("kein Vorgang")
        antwort = self.client.get(f"/vorgaenge/{self.vorgang_id}?einbett=1")
        self.assertEqual(antwort.status_code, 200)
        self.assertNotIn("zurueck-knopf", antwort.text)

    def test_navigation_js_eingebunden(self):
        antwort = self.client.get("/angebote")
        self.assertIn("/static/navigation.js", antwort.text)
        js = self.client.get("/static/navigation.js")
        self.assertEqual(js.status_code, 200)
        self.assertIn("friondo_verlauf", js.text)
        self.assertIn("data-zurueck-standard", js.text)


@unittest.skipUnless(Path(CHROME).exists(), "Chrome nicht installiert")
class ZurueckVerlaufImBrowser(unittest.TestCase):
    """Teil 2: echter Browser (Chrome headless + DevTools-Protokoll) gegen einen
    uvicorn-Server im Thread (lifespan aus – keine Hintergrundläufe)."""

    @classmethod
    def setUpClass(cls):
        import subprocess
        import uvicorn
        cls.angebot_id, cls.vorgang_id, _ = _ziele()
        if not cls.angebot_id:
            raise unittest.SkipTest("kein Angebot mit Vorgang")
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
        cls.profil = Path(tempfile.mkdtemp(prefix="chrome_v30_nav_"))
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
        cls.server.should_exit = True
        cls.thread.join(timeout=10)
        shutil.rmtree(cls.profil, ignore_errors=True)

    def _ablauf(self):
        import websockets
        basis = f"http://127.0.0.1:{PORT}"
        akte = f"/vorgaenge/{self.vorgang_id}"
        angebot = f"/angebote/{self.angebot_id}"
        ergebnis = {}

        async def lauf():
            async with websockets.connect(self.ws_url, max_size=20_000_000) as ws:
                nr = [0]

                async def senden(methode, **params):
                    nr[0] += 1
                    await ws.send(json.dumps({"id": nr[0], "method": methode, "params": params}))
                    while True:
                        antwort = json.loads(await ws.recv())
                        if antwort.get("id") == nr[0]:
                            return antwort.get("result", {})

                async def oeffnen(pfad):
                    await senden("Page.navigate", url=basis + pfad)
                    await asyncio.sleep(1.2)

                async def js(ausdruck):
                    r = await senden("Runtime.evaluate", expression=ausdruck, returnByValue=True)
                    return r.get("result", {}).get("value")

                async def zurueck_klicken():
                    await js("document.querySelector('[data-zurueck-standard]').click()")
                    await asyncio.sleep(1.2)
                    return await js("location.pathname + location.search")

                await senden("Network.enable")
                await senden("Network.setCookie", name=auth.COOKIE_NAME,
                             value=auth.cookie_wert(1), url=basis)
                # Fall 1: Vorgangsakte → Angebot → Zurück = Vorgangsakte
                await oeffnen(akte)
                await js("sessionStorage.removeItem('friondo_verlauf')")
                await oeffnen(akte)
                await oeffnen(angebot)
                ergebnis["verlauf"] = await js("sessionStorage.getItem('friondo_verlauf')")
                ergebnis["fall1"] = await zurueck_klicken()
                # Fall 2: Angebot → Speichern (Umleitung auf dieselbe Seite) → Zurück = Vorgangsakte
                await oeffnen(angebot)
                await oeffnen(angebot)   # Neuladen/Redirect nach POST: oberster Eintrag bleibt
                ergebnis["fall2"] = await zurueck_klicken()
                # Fall 3: Direktaufruf (leerer Verlauf) → Zurück = Angebotsliste
                await js("sessionStorage.removeItem('friondo_verlauf')")
                await oeffnen(angebot)
                ergebnis["fall3"] = await zurueck_klicken()
                # Startseite hat keinen Knopf
                await oeffnen("/")
                ergebnis["start"] = await js("!!document.querySelector('[data-zurueck-standard]')")

        asyncio.run(lauf())
        return ergebnis, akte, angebot

    def test_eine_ansicht_zurueck(self):
        ergebnis, akte, angebot = self._ablauf()
        self.assertIn(angebot, ergebnis["verlauf"] or "")
        self.assertEqual(ergebnis["fall1"], akte, ergebnis)
        self.assertEqual(ergebnis["fall2"], akte, ergebnis)
        self.assertEqual(ergebnis["fall3"], "/angebote", ergebnis)
        self.assertFalse(ergebnis["start"])


if __name__ == "__main__":
    unittest.main()
