# Screenshots der Kernseiten für das Design v2 (v30, PLAN_V18 Phase 152 – vorher
# Phase 74/PLAN_V12 mit Playwright). Ohne Playwright: Chrome headless + DevTools-
# Protokoll über `websockets` (Muster diagnose/v28_patches/vorher_screenshots.py).
#
# Aufruf (Projektordner):
#   venv\Scripts\python scripts\design_screenshots.py vorher|nachher --modus hell|dunkel
#       [--port 8123] [--cdp 9333] [--db <DB-Kopie>] [--data <DATA_ORDNER>]
#       [--seiten portal,login,…] [--ziel docs/design-v30]
#
# Ohne --server startet das Skript eine eigene Tool-Instanz auf --port (Standard 8123)
# gegen die Datenbank aus --db bzw. DB_PFAD_OVERRIDE (Vererbung an den Testserver);
# mit --server http://127.0.0.1:8000 läuft es gegen einen bereits laufenden Server
# (z. B. den des Orchestrators). Der Modus wird über das Cookie `darstellung`
# (hell | dunkel) gesetzt; die Anmeldung läuft über das signierte Sitzungs-Cookie
# (auth.cookie_wert) – Admin für die Büro-Seiten, Montage-Benutzer für den Einsatz
# (390 px), Außendienst für die mobile Erfassung (390 px, temporärer Entwurf, wird
# wieder gelöscht), /login ohne Anmeldung. Desktop 1440×900, ganze Seite.
# Ziel: docs/design-v30/<seite>-<praefix>-<modus>.png. Nur Demo-Daten; EK/DB-Spalten
# werden vor der Aufnahme per eingefügtem <style> ausgeblendet (Runtime.evaluate).
import argparse
import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DESKTOP = (1440, 900)
MOBIL = (390, 844)
MAX_HOEHE = 5000
# EK-/DB-Angaben (Innendienst-Sicht) vor der Aufnahme ausblenden – nie im Bild
STYLE_OHNE_EK = (
    ".db-box, .db-rot, .db-orange, .db-gruen, th[title*='Deckungsbeitrag'], "
    "label:has(input[name='ek_preis']), .ek, .ek-spalte, [data-ek], "
    # v33 (Phase 174): Tabellen im Lead-Board-Layout – DB-/EK-Spalten und die DB-Summe der Angebotsliste
    ".sp-db, .sp-ek, .sp-db_ampel, th[data-key='db'], th[data-key='ek'], th[data-key='db_ampel'], .sp-db-summe "
    "{ visibility: hidden !important; }"
)
# Reihenfolge und Rollen der Seiten (Phase 152): name → (Rolle, Pfad oder Ermittler, mobil)
SEITEN = ["portal", "angebotsliste", "editor", "vorgangsakte", "hauptboard", "kartei",
          "projektboard", "projektakte", "montage-einsatz", "erfassung-mobil", "login",
          # v31/v32 (13.10.2026): Lead-Dashboard, Benutzerverwaltung, Lead-Einstellungen,
          # Leads VOT / Mein Tag (Desktop + Handy), Kundensuche
          "lead-dashboard", "benutzer", "lead-einstellungen", "leads-vot", "mein-tag-mobil",
          "suche", "angebotsliste-verfolgung",
          # v33 (PLAN_V20 Phase 177): Verbindungs-Seite, Rollen, Kalender je Modul, Service-Backend,
          # Tabellen (Erfassungen, Kunden, Meine Angebote), Mein Tag Wiedervorlage mobil
          "versand", "rollen", "kalender-projektierung", "kalender-vertrieb", "kalender-tag",
          "kalender-monat", "kalender-montage-mobil", "service-backend",
          "montage-backend", "erfassungen", "kunden", "meine-angebote", "parametrierung",
          "wiedervorlage-mobil",
          # v34 (PLAN_V21 Phase 182): Login mobil, Galerie-Sammelbox mobil, Wallbox-Editor/-Erfassung
          "login-mobil", "vorgangsakte-mobil", "editor-wb", "erfassung-wb-mobil",
          # v35 (PLAN_LEAD_V6 Phase 187): Vertriebskanäle, TAIFUN-Übergabeliste, Mein Profil, Kontaktiert
          "kanaele", "taifun-uebergaben", "profil", "profil-mobil", "kontaktiert"]


def argumente() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Design-Screenshots (Chrome headless + DevTools)")
    p.add_argument("praefix", nargs="?", default="vorher", choices=["vorher", "nachher"])
    p.add_argument("--modus", default="hell", choices=["hell", "dunkel"])
    p.add_argument("--port", type=int, default=8123, help="Port der eigenen Tool-Instanz")
    p.add_argument("--server", default="", help="laufender Server statt eigener Instanz, z. B. http://127.0.0.1:8000")
    p.add_argument("--cdp", type=int, default=9333, help="Chrome-DevTools-Port")
    p.add_argument("--db", default="", help="DB-Kopie (setzt DB_PFAD_OVERRIDE, vererbt an den Testserver)")
    p.add_argument("--data", default="", help="DATA_ORDNER für den Testserver")
    p.add_argument("--seiten", default="", help="Komma-Liste der Seiten (Standard: alle)")
    p.add_argument("--ziel", default=str(PROJEKT / "docs" / "design-v30"))
    p.add_argument("--chrome", default=CHROME)
    return p.parse_args()


def warten(url: str, sekunden: int = 60) -> None:
    for _ in range(sekunden * 2):
        try:
            with urllib.request.urlopen(url, timeout=2) as a:
                if a.status < 500:
                    return
        except Exception:   # noqa: BLE001
            time.sleep(0.5)
    raise SystemExit(f"Server {url} nicht erreichbar")


def holen(basis: str, pfad: str, cookie: str, cookie_name: str) -> str:
    """HTML einer Seite (für die Ermittlung von IDs aus Links)."""
    anfrage = urllib.request.Request(basis + pfad, headers={"Cookie": f"{cookie_name}={cookie}"})
    try:
        with urllib.request.urlopen(anfrage, timeout=20) as a:
            return a.read().decode("utf-8", "replace")
    except Exception as e:   # noqa: BLE001
        print("  (Seite nicht lesbar:", pfad, e, ")")
        return ""


def erster_link(html: str, muster: str) -> str | None:
    m = re.search(muster, html)
    return m.group(1) if m else None


def modus_setzen(basis: str, cookie: str, cookie_name: str, modus: str) -> bool:
    """Angemeldete Benutzer folgen ihrer gespeicherten Wahl (Middleware), nicht dem
    Cookie – darum wird der Modus je Rolle über POST /einstellungen/darstellung
    gesetzt (und am Ende wieder zurückgestellt)."""
    daten = json.dumps({"wert": modus}).encode("utf-8")
    anfrage = urllib.request.Request(basis + "/einstellungen/darstellung", data=daten, method="POST",
                                     headers={"Cookie": f"{cookie_name}={cookie}",
                                              "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(anfrage, timeout=20) as a:
            return a.status == 200
    except Exception as e:   # noqa: BLE001
        print("  (Darstellung nicht gesetzt:", e, ")")
        return False


def einstellungen_merken(ids: dict) -> dict:
    """Gespeicherte Darstellung je Benutzer (None = nie gewählt) für die Rückstellung."""
    from app import darstellung
    from app.db import SessionLocal
    session = SessionLocal()
    try:
        return {rolle: darstellung.lesen(session, bid) for rolle, bid in ids.items()}
    finally:
        session.close()


def einstellungen_zuruecksetzen(ids: dict, vorher: dict) -> None:
    from app import darstellung
    from app.db import SessionLocal
    from app.models import BenutzerEinstellung
    session = SessionLocal()
    try:
        for rolle, bid in ids.items():
            alt = vorher.get(rolle)
            if alt:
                darstellung.speichern(session, bid, alt)
            else:
                session.query(BenutzerEinstellung).filter(BenutzerEinstellung.benutzer_id == bid,
                                                          BenutzerEinstellung.key == darstellung.KEY).delete()
        session.commit()
    finally:
        session.close()


def benutzer_je_rolle(session) -> dict:
    """Erste aktive Benutzer-ID je Rolle (admin, montage, aussendienst)."""
    from app.models import Benutzer
    rollen = {}
    for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True)).order_by(Benutzer.id).all():
        rollen.setdefault(b.rolle, b.id)
    # v32 (13.10.2026): für „Mein Tag“ den Außendienstler mit den meisten offenen
    # Vor-Ort-Terminen nehmen (sonst zeigt die mobile Aufnahme nur den Leerzustand)
    try:
        from sqlalchemy import text as _text
        # v33 (M 4.2): zuerst ein Außendienstler mit Terminen HEUTE („Als Nächstes“ + Zeitstrahl im Bild),
        # sonst wie bisher der mit den meisten offenen Terminen
        zeile = session.execute(_text(
            "SELECT b.id FROM benutzer b JOIN vot_termine t ON t.ad_id=b.id "
            "WHERE b.aktiv=1 AND b.rolle IN ('aussendienst','handelsvertreter') "
            "AND t.status IN ('geplant','bestaetigt','unbestaetigt') AND date(t.beginn)=date('now','localtime') "
            "GROUP BY b.id ORDER BY COUNT(*) DESC LIMIT 1")).fetchone() or session.execute(_text(
            "SELECT b.id FROM benutzer b JOIN vorgaenge v ON v.ad_id=b.id "
            "JOIN vot_termine t ON t.vorgang_id=v.id "
            "WHERE b.aktiv=1 AND b.rolle='aussendienst' AND t.status IN ('geplant','terminiert','unbestaetigt') "
            "GROUP BY b.id ORDER BY COUNT(*) DESC LIMIT 1")).fetchone()
        if zeile:
            rollen["aussendienst"] = int(zeile[0])
    except Exception:   # noqa: BLE001 – ältere Kopien ohne die Tabellen
        pass
    ergebnis = {"admin": rollen.get("admin", 1), "montage": rollen.get("montage", 2),
                "aussendienst": rollen.get("aussendienst", 3)}
    # v33: Service-Variante (Rolle service_heizung/service_elektro) fuer das Service-Backend
    for rolle, bid in rollen.items():
        if str(rolle).startswith("service_"):
            ergebnis["service"] = bid
            break
    return ergebnis


def ziele_ermitteln(basis: str, cookies: dict, cookie_name: str) -> dict:
    """IDs über die Listen-/Board-Seiten (funktioniert auch gegen fremde Server)."""
    admin = cookies["admin"]
    ziele = {}
    liste = holen(basis, "/angebote", admin, cookie_name)
    ziele["angebot_id"] = erster_link(liste, r'href="/angebote/(\d+)"')
    ziele["vorgang_id"] = erster_link(liste, r'href="/vorgaenge/(\d+)"')
    if not ziele["vorgang_id"]:
        ziele["vorgang_id"] = erster_link(holen(basis, "/vorgaenge", admin, cookie_name), r'href="/vorgaenge/(\d+)"')
    board = holen(basis, "/lead-management/hauptboard", admin, cookie_name)
    ziele["lead_id"] = erster_link(board, r'href="/lead-management/lead/(\d+)"')
    projekte = holen(basis, "/projektierung", admin, cookie_name)
    ziele["projekt_id"] = (erster_link(projekte, r'href="/projektierung/projekt/(\d+)"')
                           or erster_link(holen(basis, "/projektierung/liste", admin, cookie_name),
                                          r'href="/projektierung/projekt/(\d+)"'))
    einsaetze = holen(basis, "/montage", cookies["montage"], cookie_name)
    ziele["termin_id"] = erster_link(einsaetze, r'href="/montage/einsatz/(\d+)"')
    # v34: Wallbox-Angebot/-Erfassung aus der DB-Kopie (nur lokal; gegen fremde Server leer)
    ziele["wb_angebot_id"] = ziele["wb_erfassung_id"] = 0
    try:
        from app.db import SessionLocal
        from app.models import Angebot, Erfassung
        s = SessionLocal()
        try:
            a = (s.query(Angebot).filter(Angebot.konfigurator_typ == "WB", Angebot.extern.is_(False))
                 .order_by(Angebot.id.desc()).first())
            ziele["wb_angebot_id"] = a.id if a else 0
            e = (s.query(Erfassung).filter(Erfassung.sparte == "WB", Erfassung.typ == "katalog")
                 .order_by(Erfassung.id.desc()).first())
            ziele["wb_erfassung_id"] = e.id if e else 0
        finally:
            s.close()
    except Exception:   # noqa: BLE001
        pass
    return ziele


def erfassung_anlegen(benutzer_id: int) -> int:
    from app.db import SessionLocal
    from app.models import Erfassung, Kunde
    session = SessionLocal()
    try:
        kunde = session.query(Kunde).order_by(Kunde.id).first()
        if kunde is None:
            return 0
        erfassung = Erfassung(kunde_id=kunde.id, benutzer_id=benutzer_id, status="Entwurf",
                              antworten_json="{}")
        session.add(erfassung)
        session.commit()
        return erfassung.id
    finally:
        session.close()


def erfassung_loeschen(erfassung_id: int) -> None:
    if not erfassung_id:
        return
    from app.db import SessionLocal
    from app.models import Erfassung
    session = SessionLocal()
    try:
        rest = session.get(Erfassung, erfassung_id)
        if rest is not None:
            session.delete(rest)
            session.commit()
    finally:
        session.close()


def seitenliste(ziele: dict, cookies: dict, erfassung_id: int) -> list[tuple[str, str, str | None, bool]]:
    """(name, pfad, cookie oder None, mobil)."""
    admin, montage, ad = cookies["admin"], cookies["montage"], cookies["aussendienst"]
    liste = [("portal", "/", admin, False),
             ("angebotsliste", "/angebote", admin, False)]
    if ziele.get("angebot_id"):
        liste.append(("editor", f"/angebote/{ziele['angebot_id']}", admin, False))
    if ziele.get("vorgang_id"):
        liste.append(("vorgangsakte", f"/vorgaenge/{ziele['vorgang_id']}", admin, False))
    liste.append(("hauptboard", "/lead-management/hauptboard", admin, False))
    if ziele.get("lead_id"):
        liste.append(("kartei", f"/lead-management/lead/{ziele['lead_id']}", admin, False))
    liste.append(("projektboard", "/projektierung", admin, False))
    if ziele.get("projekt_id"):
        liste.append(("projektakte", f"/projektierung/projekt/{ziele['projekt_id']}", admin, False))
    if ziele.get("termin_id"):
        liste.append(("montage-einsatz", f"/montage/einsatz/{ziele['termin_id']}", montage, True))
    if erfassung_id:
        liste.append(("erfassung-mobil", f"/erfassung/{erfassung_id}/seite/0", ad, True))
    liste.append(("login", "/login", None, False))
    # v31/v32
    liste.append(("lead-dashboard", "/lead-management/dashboard", admin, False))
    liste.append(("benutzer", "/benutzer", admin, False))
    liste.append(("lead-einstellungen", "/parametrierung/lead-einstellungen", admin, False))
    liste.append(("leads-vot", "/leads", admin, False))
    liste.append(("mein-tag-mobil", "/leads", ad, True))
    liste.append(("suche", "/suche?q=M%C3%BC", admin, False))
    liste.append(("angebotsliste-verfolgung", "/angebote?verfolgung=versendet", admin, False))
    # v33
    liste.append(("versand", "/versand", admin, False))
    liste.append(("rollen", "/parametrierung/rollen", admin, False))
    liste.append(("kalender-projektierung", "/kalender?gruppe=projektierung", admin, False))
    liste.append(("kalender-vertrieb", "/kalender?gruppe=vertrieb", admin, False))
    liste.append(("kalender-tag", "/kalender?gruppe=alle&ansicht=tag", admin, False))
    liste.append(("kalender-monat", "/kalender?gruppe=projektierung&ansicht=monat", admin, False))
    liste.append(("kalender-montage-mobil", "/kalender", montage, True))
    if cookies.get("service"):
        liste.append(("service-backend", "/montage", cookies["service"], True))
    liste.append(("montage-backend", "/montage", montage, True))
    liste.append(("erfassungen", "/erfassungen", admin, False))
    liste.append(("kunden", "/kunden", admin, False))
    liste.append(("meine-angebote", "/meine-angebote", ad, False))
    liste.append(("parametrierung", "/parametrierung", admin, False))
    liste.append(("wiedervorlage-mobil", "/leads/wiedervorlagen", ad, True))
    # v34 (PLAN_V21 Phase 182)
    liste.append(("login-mobil", "/login", None, True))
    if ziele.get("vorgang_id"):
        liste.append(("vorgangsakte-mobil", f"/vorgaenge/{ziele['vorgang_id']}", admin, True))
    if ziele.get("wb_angebot_id"):
        liste.append(("editor-wb", f"/angebote/{ziele['wb_angebot_id']}", admin, False))
    if ziele.get("wb_erfassung_id"):
        liste.append(("erfassung-wb-mobil", f"/erfassung/{ziele['wb_erfassung_id']}/seite/0", admin, True))
    # v35 (PLAN_LEAD_V6 Phase 187)
    liste.append(("kanaele", "/lead-management/kanaele", admin, False))
    liste.append(("taifun-uebergaben", "/lead-management/taifun-uebergaben", admin, False))
    liste.append(("profil", "/einstellungen/profil", admin, False))
    liste.append(("profil-mobil", "/einstellungen/profil", ad, True))
    liste.append(("kontaktiert", "/lead-management/kontaktiert", admin, False))
    return liste


async def aufnehmen(ws_url: str, basis: str, cookie_name: str, modus: str, seiten: list,
                    ziel: Path, praefix: str) -> list[str]:
    import websockets
    fertig = []
    async with websockets.connect(ws_url, max_size=80_000_000) as ws:
        nr = [0]
        ereignisse = []

        async def senden(methode: str, **params):
            nr[0] += 1
            await ws.send(json.dumps({"id": nr[0], "method": methode, "params": params}))
            while True:
                antwort = json.loads(await ws.recv())
                if antwort.get("id") == nr[0]:
                    if "error" in antwort:
                        raise RuntimeError(f"{methode}: {antwort['error']}")
                    return antwort.get("result", {})
                ereignisse.append(antwort.get("method"))

        async def laden(url: str, timeout: float = 15.0) -> None:
            ereignisse.clear()
            await senden("Page.navigate", url=url)
            ende = time.monotonic() + timeout
            while time.monotonic() < ende:
                if "Page.loadEventFired" in ereignisse:
                    break
                try:
                    nachricht = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
                    ereignisse.append(nachricht.get("method"))
                except asyncio.TimeoutError:
                    continue
            await asyncio.sleep(0.6)

        await senden("Page.enable")
        await senden("Network.enable")
        for name, pfad, cookie, mobil in seiten:
            await senden("Network.clearBrowserCookies")
            await senden("Network.setCookie", name="darstellung", value=modus, url=basis)
            if cookie:
                await senden("Network.setCookie", name=cookie_name, value=cookie, url=basis)
            breite, hoehe = MOBIL if mobil else DESKTOP
            await senden("Emulation.setDeviceMetricsOverride", width=breite, height=hoehe,
                         deviceScaleFactor=2 if mobil else 1, mobile=mobil)
            await laden(basis + pfad)
            await senden("Runtime.evaluate", expression=(
                "(function(){var s=document.createElement('style');s.textContent="
                + json.dumps(STYLE_OHNE_EK) + ";document.head.appendChild(s);"
                "document.querySelectorAll('details.menue[open]').forEach(function(d){d.open=false});"
                "return document.documentElement.getAttribute('data-theme')||'';})()"))
            metrik = await senden("Page.getLayoutMetrics")
            inhalt = metrik.get("cssContentSize") or metrik.get("contentSize") or {}
            voll_hoehe = int(min(max(inhalt.get("height", hoehe), hoehe), MAX_HOEHE))
            bild = await senden("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                                clip={"x": 0, "y": 0, "width": breite, "height": voll_hoehe, "scale": 1})
            datei = ziel / f"{name}-{praefix}-{modus}.png"
            datei.write_bytes(base64.b64decode(bild["data"]))
            print(f"OK {name:16s} {pfad:45s} {breite}x{voll_hoehe} -> {datei.name}")
            fertig.append(name)
    return fertig


def main() -> int:
    args = argumente()
    if args.db:
        os.environ["DB_PFAD_OVERRIDE"] = str(Path(args.db).resolve())
    if args.data:
        os.environ["DATA_ORDNER"] = str(Path(args.data).resolve())
    from app import auth, config
    from app.db import SessionLocal

    ziel = Path(args.ziel)
    ziel.mkdir(parents=True, exist_ok=True)
    basis = args.server.rstrip("/") if args.server else f"http://127.0.0.1:{args.port}"
    gewuenscht = [s.strip() for s in args.seiten.split(",") if s.strip()] or SEITEN

    session = SessionLocal()
    try:
        rollen = benutzer_je_rolle(session)
    finally:
        session.close()
    cookies = {rolle: auth.cookie_wert(bid) for rolle, bid in rollen.items()}

    server = None
    chrome = None
    profil = Path(tempfile.mkdtemp(prefix="design_chrome_"))
    erfassung_id = 0
    einstellungen_vorher = einstellungen_merken(rollen)
    try:
        if not args.server:
            umgebung = dict(os.environ, PYTHONIOENCODING="utf-8")
            server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                       "--port", str(args.port), "--log-level", "warning"],
                                      cwd=str(PROJEKT), env=umgebung)
        warten(basis + "/login")
        for rolle, cookie in cookies.items():
            modus_setzen(basis, cookie, auth.COOKIE_NAME, args.modus)
        ziele = ziele_ermitteln(basis, cookies, auth.COOKIE_NAME)
        if "erfassung-mobil" in gewuenscht:
            erfassung_id = erfassung_anlegen(rollen["aussendienst"])
        seiten = [s for s in seitenliste(ziele, cookies, erfassung_id) if s[0] in gewuenscht]
        fehlend = [s for s in gewuenscht if s not in [n for n, *_ in seiten]]
        if fehlend:
            print("übersprungen (kein Ziel in den Daten):", ", ".join(fehlend))

        chrome = subprocess.Popen([args.chrome, "--headless=new", f"--remote-debugging-port={args.cdp}",
                                   f"--user-data-dir={profil}", "--window-size=1440,900",
                                   "--no-first-run", "--disable-gpu", "--hide-scrollbars", "about:blank"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws_url = ""
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{args.cdp}/json", timeout=2) as a:
                    tabs = json.loads(a.read().decode("utf-8"))
                ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t.get("type") == "page")
                break
            except Exception:   # noqa: BLE001
                time.sleep(0.5)
        if not ws_url:
            raise SystemExit("Chrome DevTools nicht erreichbar")
        fertig = asyncio.run(aufnehmen(ws_url, basis, auth.COOKIE_NAME, args.modus, seiten, ziel, args.praefix))
        print(f"fertig: {args.praefix}/{args.modus} – {len(fertig)} Bilder in {ziel} (Version {config.VERSION})")
        return 0
    finally:
        if chrome is not None:
            chrome.kill()
            chrome.wait(timeout=10)
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
        erfassung_loeschen(erfassung_id)
        einstellungen_zuruecksetzen(rollen, einstellungen_vorher)
        shutil.rmtree(profil, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
