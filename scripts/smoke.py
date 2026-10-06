# Smoke-Test nach jedem Update (v27, PLAN_V17 Phase 132) – nur Standardbibliothek (urllib, sqlite3).
#
# Aufruf im Projektordner (normalerweise über scripts\smoke.bat, das update.bat am Ende aufruft):
#   venv\Scripts\python.exe scripts\smoke.py [--basis http://127.0.0.1:8000] [--pin PIN] [--warten 30]
#       [--zeitlimit 3.0] [--admin-id 1] [--db PFAD] [--log-ordner PFAD] [--cookie WERT] [--ohne-datei]
# Ablauf:
#   1. /health muss antworten (bis --warten Sekunden nach einem Start) und status ok oder warn liefern –
#      Status und Gründe werden ausgegeben; fehler bzw. HTTP 503 = Fehlschlag.
#   2. Mit dem Admin-Sitzungscookie (auth.cookie_wert, kein PIN nötig – wie Crawl und Abnahme) je
#      HTTP 200 und Antwortzeit < --zeitlimit: Startseite /, /erfassungen, /angebote,
#      /vorgaenge/<jüngste ID>, /angebote/<jüngstes Tool-Angebot mit Positionen>/pdf (muss ein PDF
#      sein), /lead-management/hauptboard, /projektierung. Die IDs kommen nur lesend per sqlite3 aus
#      der Datenbank. 303 auf /login = Fehlschlag (Cookie/Anmeldung defekt). Liegt eine Seite über dem
#      Zeitlimit, wird sie einmal wiederholt (Kaltstart nach dem Update) und die bessere Zeit gewertet.
#   3. Optional --pin: echter Login per POST /login (Benutzer --admin-id) – erwartet 303 mit
#      Sitzungscookie; die PIN erscheint nie in Ausgabe oder Protokoll.
# Ergebnis als Tabelle auf der Konsole und in data\log\smoke-<JJJJ-MM-TT_HHMM>.txt.
# Exit-Code 0 = bestanden, 1 = Fehlschlag (Hinweis rollback.bat), 2 = Bedienfehler.
import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

COOKIE_NAME = "angebotstool_sitzung"
ROLLBACK_HINWEIS = ("Rückweg: rollback.bat (Code + Datenbank aus der Sicherung, mit Rückfrage) "
                    "oder rollback.bat --nur-code (nur Code, Datenbank bleibt).")


class OhneUmleitung(urllib.request.HTTPRedirectHandler):
    """3xx nicht folgen – eine Umleitung auf /login ist ein Fehlschlag, kein Erfolg."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(OhneUmleitung)


def abrufen(url: str, cookie: str = "", daten: bytes | None = None, timeout: float = 20.0):
    """(HTTP-Status oder None, Header als dict, Rumpf, Sekunden, Fehlertext)"""
    kopf = {"User-Agent": "friondo-smoke/v27", "Cache-Control": "no-cache"}
    if cookie:
        kopf["Cookie"] = f"{COOKIE_NAME}={cookie}"
    if daten is not None:
        kopf["Content-Type"] = "application/x-www-form-urlencoded"
    anfrage = urllib.request.Request(url, data=daten, headers=kopf)
    t0 = time.perf_counter()
    try:
        with OPENER.open(anfrage, timeout=timeout) as antwort:
            rumpf = antwort.read()
            return antwort.status, dict(antwort.headers.items()), rumpf, time.perf_counter() - t0, ""
    except urllib.error.HTTPError as fehler:
        try:
            rumpf = fehler.read()
        except Exception:
            rumpf = b""
        header = dict(fehler.headers.items()) if fehler.headers else {}
        return fehler.code, header, rumpf, time.perf_counter() - t0, ""
    except Exception as fehler:          # URLError, Timeout, ConnectionReset
        return None, {}, b"", time.perf_counter() - t0, f"{type(fehler).__name__}: {fehler}"


def header_wert(header: dict, name: str) -> str:
    for k, v in header.items():
        if k.lower() == name.lower():
            return v
    return ""


def health_pruefen(basis: str, warten: int, timeout: float):
    ende = time.monotonic() + warten
    while True:
        status, header, rumpf, dauer, fehler = abrufen(basis + "/health", timeout=timeout)
        if status is not None or time.monotonic() >= ende:
            break
        time.sleep(1)
    daten = {}
    if rumpf:
        try:
            daten = json.loads(rumpf.decode("utf-8"))
        except Exception:
            daten = {}
    return status, daten, dauer, fehler


def ids_lesen(db_pfad: Path):
    """Jüngster Vorgang und jüngstes Tool-Angebot mit Positionen – nur lesend."""
    uri = "file:" + urllib.request.pathname2url(str(db_pfad)) + "?mode=ro"
    verbindung = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        vorgang = verbindung.execute("SELECT MAX(id) FROM vorgaenge").fetchone()[0]
        angebot = verbindung.execute(
            "SELECT a.id FROM angebote a WHERE COALESCE(a.extern, 0) = 0 "
            "AND EXISTS (SELECT 1 FROM angebotspositionen p WHERE p.angebot_id = a.id) "
            "ORDER BY a.id DESC LIMIT 1").fetchone()
    finally:
        verbindung.close()
    return vorgang, (angebot[0] if angebot else None)


def admin_cookie(admin_id: int) -> str:
    """Signiertes Sitzungscookie des Admins über den Projektcode (kein PIN nötig)."""
    global COOKIE_NAME
    from app import auth
    COOKIE_NAME = getattr(auth, "COOKIE_NAME", COOKIE_NAME)
    return auth.cookie_wert(admin_id)


def seite_pruefen(basis: str, pfad: str, cookie: str, zeitlimit: float, pdf: bool = False):
    """→ (HTTP-Status, Sekunden, ok, Text)"""
    status, header, rumpf, dauer, fehler = abrufen(basis + pfad, cookie)
    versuch = 1
    if status == 200 and dauer >= zeitlimit:
        status2, header2, rumpf2, dauer2, fehler2 = abrufen(basis + pfad, cookie)
        if status2 == 200 and dauer2 < dauer:
            status, header, rumpf, dauer, versuch = status2, header2, rumpf2, dauer2, 2
    if status is None:
        return None, dauer, False, "keine Antwort – " + fehler
    if status == 303 or status == 302 or status == 307:
        ziel = header_wert(header, "Location")
        if ziel.startswith("/login"):
            return status, dauer, False, "Umleitung auf /login – Sitzungscookie abgelehnt (Anmeldung defekt?)"
        return status, dauer, False, f"Umleitung auf {ziel or '?'}"
    if status != 200:
        return status, dauer, False, f"HTTP {status}"
    if pdf and not rumpf.startswith(b"%PDF"):
        return status, dauer, False, "Antwort ist kein PDF"
    if dauer >= zeitlimit:
        return status, dauer, False, f"zu langsam ({dauer:.1f} s >= {zeitlimit:g} s, {versuch}. Versuch)"
    text = "OK"
    if pdf:
        text += f" (PDF, {len(rumpf) // 1024} KB)"
    if versuch == 2:
        text += " (2. Versuch – Kaltstart)"
    return status, dauer, True, text


def login_pruefen(basis: str, admin_id: int, pin: str):
    daten = urllib.parse.urlencode({"benutzer_id": admin_id, "pin": pin}).encode()
    status, header, rumpf, dauer, fehler = abrufen(basis + "/login", daten=daten)
    if status is None:
        return None, dauer, False, "keine Antwort – " + fehler
    ziel = header_wert(header, "Location")
    cookie = header_wert(header, "Set-Cookie")
    if status == 303 and COOKIE_NAME in cookie and not ziel.startswith("/login"):
        return status, dauer, True, f"OK (Weiterleitung {ziel})"
    if status == 200:
        return status, dauer, False, "Anmeldeseite erneut – Benutzer oder PIN falsch / Konto gesperrt"
    return status, dauer, False, f"HTTP {status}, Weiterleitung {ziel or '-'}"


def tabelle(zeilen: list[tuple]) -> list[str]:
    breite = max(len(z[0]) for z in zeilen)
    kopf = f"{'Prüfung':<{breite}} | HTTP | Zeit    | Ergebnis"
    trenner = "-" * breite + "-+------+---------+-" + "-" * 40
    ausgabe = [kopf, trenner]
    for name, status, dauer, ok, text in zeilen:
        http = "-" if status is None else str(status)
        zeit = "-" if dauer is None else f"{dauer:5.2f} s"
        ausgabe.append(f"{name:<{breite}} | {http:<4} | {zeit:>7} | {'OK  ' if ok else 'FEHL'} {text}")
    return ausgabe


def main() -> int:
    parser = argparse.ArgumentParser(description="Friondo Angebotstool – Smoke-Test nach dem Update")
    parser.add_argument("--basis", default="http://127.0.0.1:8000", help="Adresse des Tools")
    parser.add_argument("--pin", default="", help="zusätzlich echten Login prüfen (PIN nie im Protokoll)")
    parser.add_argument("--warten", type=int, default=30, help="Sekunden auf /health warten (Start)")
    parser.add_argument("--zeitlimit", type=float, default=3.0, help="Antwortzeit je Seite in Sekunden")
    parser.add_argument("--admin-id", type=int, default=1, help="Benutzer-ID des Admins (Cookie/Login)")
    parser.add_argument("--db", default="", help="SQLite-Datei für die IDs (Standard: Datenbank des Tools)")
    parser.add_argument("--log-ordner", default="", help="Zielordner des Protokolls (Standard: data\\log)")
    parser.add_argument("--cookie", default="", help="fertiger Sitzungscookie statt auth.cookie_wert")
    parser.add_argument("--ohne-datei", action="store_true", help="kein Protokoll schreiben")
    args = parser.parse_args()
    basis = args.basis.rstrip("/")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    try:
        from app import config
        db_pfad = Path(args.db) if args.db else config.DB_PFAD
        log_ordner = Path(args.log_ordner) if args.log_ordner else config.LOG_ORDNER
    except Exception:
        db_pfad = Path(args.db) if args.db else PROJEKT / "data" / "angebotstool.db"
        log_ordner = Path(args.log_ordner) if args.log_ordner else PROJEKT / "data" / "log"
    if not db_pfad.exists():
        print(f"Bedienfehler: Datenbank {db_pfad} nicht gefunden (--db).")
        return 2

    start = datetime.now()
    zeilen: list[tuple] = []
    kopfzeilen = [f"Smoke-Test Friondo Angebotstool – {start:%d.%m.%Y %H:%M} – Basis {basis}"]

    # 1) /health
    status, daten, dauer, fehler = health_pruefen(basis, args.warten, timeout=10)
    gruende = "; ".join(str(g) for g in daten.get("gruende", []) or [])
    h_status = str(daten.get("status", ""))
    if status is None:
        zeilen.append(("/health", None, dauer, False, "keine Antwort – " + fehler))
    elif status == 404:
        zeilen.append(("/health", status, dauer, False, "HTTP 404 – Fassung ohne /health (vor v27)?"))
    elif status == 503 or h_status == "fehler":
        zeilen.append(("/health", status, dauer, False, f"fehler: {gruende or 'Datenbank nicht erreichbar'}"))
    elif h_status in ("ok", "warn"):
        text = "OK" if h_status == "ok" else f"OK (warn: {gruende})"
        zeilen.append(("/health", status, dauer, True, text))
    else:
        zeilen.append(("/health", status, dauer, False, f"unerwartete Antwort (Status „{h_status}“)"))
    if daten:
        kopfzeilen.append(f"Version {daten.get('version', '?')} · Commit {daten.get('commit', '?')} · "
                          f"/health {h_status or '?'}" + (f" ({gruende})" if gruende else ""))

    # 2) Seiten mit Admin-Cookie
    cookie = args.cookie
    if not cookie and zeilen[-1][3]:
        try:
            cookie = admin_cookie(args.admin_id)
        except Exception as problem:
            zeilen.append(("Admin-Cookie", None, None, False,
                           f"auth.cookie_wert fehlgeschlagen: {type(problem).__name__}: {problem}"))
    if cookie:
        try:
            vorgang_id, angebot_id = ids_lesen(db_pfad)
        except Exception as problem:
            vorgang_id, angebot_id = None, None
            zeilen.append(("IDs aus der Datenbank", None, None, False, f"{type(problem).__name__}: {problem}"))
        pruefungen = [("Startseite /", "/", False), ("Erfassungsliste /erfassungen", "/erfassungen", False),
                      ("Angebotsliste /angebote", "/angebote", False)]
        if vorgang_id:
            pruefungen.append((f"Vorgangsakte /vorgaenge/{vorgang_id}", f"/vorgaenge/{vorgang_id}", False))
        else:
            zeilen.append(("Vorgangsakte", None, None, False, "kein Vorgang in der Datenbank"))
        if angebot_id:
            pruefungen.append((f"Angebots-PDF /angebote/{angebot_id}/pdf", f"/angebote/{angebot_id}/pdf", True))
        else:
            zeilen.append(("Angebots-PDF", None, None, False, "kein Tool-Angebot mit Positionen in der Datenbank"))
        pruefungen += [("Hauptboard /lead-management/hauptboard", "/lead-management/hauptboard", False),
                       ("Projektierung /projektierung", "/projektierung", False)]
        for name, pfad, pdf in pruefungen:
            status, dauer, ok, text = seite_pruefen(basis, pfad, cookie, args.zeitlimit, pdf=pdf)
            zeilen.append((name, status, dauer, ok, text))
    elif zeilen[-1][3]:
        zeilen.append(("Seitenprüfungen", None, None, False, "kein Sitzungscookie – übersprungen"))

    # 3) optional echter Login
    if args.pin:
        status, dauer, ok, text = login_pruefen(basis, args.admin_id, args.pin)
        zeilen.append((f"Login POST /login (Benutzer {args.admin_id})", status, dauer, ok, text))

    fehlschlaege = [z for z in zeilen if not z[3]]
    ausgabe = kopfzeilen + [""] + tabelle(zeilen) + [""]
    if fehlschlaege:
        ausgabe.append(f"Ergebnis: FEHLGESCHLAGEN ({len(fehlschlaege)} von {len(zeilen)} Prüfungen). {ROLLBACK_HINWEIS}")
    else:
        ausgabe.append(f"Ergebnis: BESTANDEN ({len(zeilen)}/{len(zeilen)} Prüfungen, "
                       f"Dauer {(datetime.now() - start).total_seconds():.0f} s).")

    if not args.ohne_datei:
        try:
            log_ordner.mkdir(parents=True, exist_ok=True)
            protokoll = log_ordner / f"smoke-{start:%Y-%m-%d_%H%M}.txt"
            protokoll.write_text("\n".join(ausgabe) + "\n", encoding="utf-8")
            ausgabe.append(f"Protokoll: {protokoll}")
        except Exception as problem:
            ausgabe.append(f"Protokoll konnte nicht geschrieben werden: {problem}")
    print("\n".join(ausgabe))
    return 1 if fehlschlaege else 0


if __name__ == "__main__":
    sys.exit(main())
