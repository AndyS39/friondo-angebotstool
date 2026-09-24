# Screenshots der Kernseiten für das Design-Update (PLAN_V12, Phase 74).
# Aufruf: venv\Scripts\python scripts\design_screenshots.py vorher|nachher
# Startet eine eigene Tool-Instanz auf Port 8123, meldet sich als Admin an
# (signiertes Cookie) und legt PNGs unter docs/design-v12/ ab. Nur lesend –
# einzig für die mobile Erfassung wird ein Entwurf angelegt und wieder gelöscht.
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from app import auth                                     # noqa: E402
from app.db import SessionLocal                          # noqa: E402
from app.models import Angebot, Erfassung, Kunde         # noqa: E402

PORT = 8123
BASIS = f"http://127.0.0.1:{PORT}"
ZIEL = PROJEKT / "docs" / "design-v12"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def server_starten() -> subprocess.Popen:
    prozess = subprocess.Popen(
        [str(PROJEKT / "venv" / "Scripts" / "python.exe"), "-m", "uvicorn",
         "app.main:app", "--port", str(PORT), "--log-level", "warning"],
        cwd=str(PROJEKT))
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{BASIS}/login", timeout=1)
            return prozess
        except Exception:
            time.sleep(0.5)
    prozess.terminate()
    raise SystemExit("Server startet nicht")


def ziele_ermitteln(session) -> dict:
    angebot = (session.query(Angebot)
               .filter(Angebot.extern.is_(False), Angebot.archiviert.is_(False),
                       Angebot.vorgang_id.isnot(None))
               .order_by(Angebot.id.desc()).first())
    return {"angebot_id": angebot.id if angebot else None,
            "vorgang_id": angebot.vorgang_id if angebot else None}


def main() -> int:
    praefix = sys.argv[1] if len(sys.argv) > 1 else "vorher"
    ZIEL.mkdir(parents=True, exist_ok=True)
    session = SessionLocal()
    ziele = ziele_ermitteln(session)
    # temporäre Erfassung für die mobile Ansicht (wird wieder gelöscht)
    kunde = session.query(Kunde).first()
    erfassung = Erfassung(kunde_id=kunde.id, benutzer_id=1, status="Entwurf",
                          antworten_json="{}")
    session.add(erfassung)
    session.commit()
    erfassung_id = erfassung.id
    session.close()

    prozess = server_starten()
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME, headless=True)
            cookie = {"name": auth.COOKIE_NAME, "value": auth.cookie_wert(1),
                      "url": BASIS}

            desktop = browser.new_context(viewport={"width": 1440, "height": 900})
            desktop.add_cookies([cookie])
            seiten = [("portal", "/"),
                      ("startseite", "/angebotstool"),
                      ("angebotsliste", "/angebote")]
            if ziele["vorgang_id"]:
                seiten.append(("vorgangsakte", f"/vorgaenge/{ziele['vorgang_id']}"))
            if ziele["angebot_id"]:
                seiten.append(("editor", f"/angebote/{ziele['angebot_id']}"))
            seiten.append(("parametrierung", "/parametrierung"))
            for name, pfad in seiten:
                blatt = desktop.new_page()
                blatt.goto(BASIS + pfad, wait_until="networkidle")
                blatt.screenshot(path=str(ZIEL / f"{praefix}-{name}.png"),
                                 full_page=True)
                blatt.close()
                print("OK", name)

            mobil = browser.new_context(
                viewport={"width": 390, "height": 844}, is_mobile=True,
                device_scale_factor=2)
            mobil.add_cookies([cookie])
            blatt = mobil.new_page()
            blatt.goto(f"{BASIS}/erfassung/{erfassung_id}/seite/0",
                       wait_until="networkidle")
            blatt.screenshot(path=str(ZIEL / f"{praefix}-erfassung-mobil.png"),
                             full_page=True)
            blatt.close()
            print("OK erfassung-mobil")
            browser.close()
    finally:
        prozess.terminate()
        session = SessionLocal()
        rest = session.get(Erfassung, erfassung_id)
        if rest is not None:
            session.delete(rest)
        session.commit()
        session.close()
    print("fertig:", praefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
