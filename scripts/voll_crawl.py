# Voll-Crawl („Gesamtsuche nach Abstürzen“, PLAN_GESAMT Teil C / STATUS-GESAMT 4.1):
# ruft ALLE GET-Seiten des Tools mit ALLEN IDs einer Datenbank-Kopie für mehrere
# Rollen über den FastAPI-TestClient auf und protokolliert jede unbehandelte
# Ausnahme (HTTP 500) mit vollständigem Traceback. Redirects (303 der Rollen-
# Middleware), 404 und Validierungsfehler zählen NICHT als Absturz.
#
# Aufruf (aus dem Projektordner, immer gegen eine KOPIE der Datenbank):
#   venv\Scripts\python scripts\voll_crawl.py --data diagnose\test_v22\data
#       [--rollen admin,innendienst,aussendienst,montage]   Hauptrollen (benutzer.rolle)
#       [--max-ids N]        höchstens N IDs je Tabelle (0 = alle)
#       [--benutzer rolle=id,...]   feste Benutzer-IDs statt „erster aktiver je Rolle“
#       [--bericht PFAD]     Berichtsdatei (Standard: <data>\..\crawl_bericht.txt)
#       [--fremd-ids]        zusätzlich je Route eine nicht vorhandene ID aufrufen
#
# --data ist der Ordner mit angebotstool.db (vorher mit migrate.py --db migrieren!).
# Er wird als DATA_ORDNER gesetzt, damit auch PDFs, Backups und .session_secret
# dort landen – das Live-Verzeichnis data\ wird nie angefasst (Schutz eingebaut).
# Externe Dienste sind abgeklemmt: MONDAY_API_TOKEN/GRAPH_CLIENT_ID leer, dazu
# Patches auf geocoding.geokodieren, monday_sync._api, graph_versand.konfiguriert
# und urllib.request.urlopen (Sicherheitsnetz gegen jeden Netzaufruf).
#
# Anmeldung: signiertes Sitzungs-Cookie (auth.cookie_wert) – kein PIN nötig.
# Ohne Lifespan (kein `with TestClient`), damit keine Scheduler-Threads starten.
# Exit-Code 0 = keine Abstürze, 1 = Abstürze, 2 = Bedienfehler.
import argparse
import collections
import itertools
import os
import sqlite3
import sys
import time
import traceback
import urllib.error
import warnings
from datetime import datetime
from pathlib import Path
from unittest import mock

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))
# Starlette 1.x meldet httpx als veraltet (httpx2) – für den Crawl unerheblich
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*httpx2.*")

STANDARD_ROLLEN = "admin,innendienst,aussendienst,montage"
FORTSCHRITT_ALLE = 2000

# Pfadparameter → Tabelle (Spalte id)
PARAM_TABELLEN = {
    "angebot_id": "angebote",
    "erfassung_id": "erfassungen",
    "vorgang_id": "vorgaenge",
    "kunde_id": "kunden",
    "lead_id": "leads",
    "projekt_id": "projekte",
    "gewerk_id": "gewerke",
    "aufgabe_id": "aufgaben",
    "termin_id": "projekt_termine",
    "datei_id": "galerie_dateien",
    "dokument_id": "projekt_dokumente",
    "benutzer_id": "benutzer",
    "konfig_id": "konfigurationen",
    "artikel_id": "artikel",
}
# eintrag_id hängt vom Router ab
EINTRAG_TABELLEN = {
    "/benachrichtigungen": "benachrichtigungen",
    "/lead-management": "lead_posteingang",
}
FRAGEBOGEN_SEITEN = list(range(0, 9))          # nr 0..8 (Route klemmt selbst)
SIGNATUR_CIDS = ["logo"]

# GET-Routen mit Nebenwirkungen (legen Datensätze an, löschen die Sitzung,
# rufen externe Dienste) – werden übersprungen.
AUSGESCHLOSSEN = {
    "/erfassungen/{erfassung_id}/angebot-erzeugen": "erzeugt ein Angebot",
    "/erfassungen/{erfassung_id}/manuelles-angebot": "erzeugt ein Angebot",
    "/angebote/aus-konfiguration/{konfig_id}": "erzeugt ein Angebot",
    "/angebote/neu": "erzeugt ein Angebot",
    "/vorgaenge/zu-lead/{lead_id}": "legt einen Vorgang an",
    "/vorgaenge/zu-erfassung/{erfassung_id}": "legt einen Vorgang an",
    "/vorgaenge/zu-angebot/{angebot_id}": "legt einen Vorgang an",
    "/leads/{lead_id}/erfassen": "legt eine Erfassung an",
    "/projektierung/angebot/{angebot_id}/projekt": "legt ein Projekt an",
    "/benachrichtigungen/{eintrag_id}/oeffnen": "markiert als gelesen + Redirect",
    "/logout": "löscht die Sitzung",
    "/parametrierung/monday": "ruft die monday-API",
    "/versand": "Graph-Statusseite (externer Dienst)",
}

ABSTUERZE: list[dict] = []          # vom Exception-Handler + Client befüllt
KONTEXT = {"rolle": "", "benutzer": ""}


def argumente() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Voll-Crawl: alle GET-Seiten × alle IDs × Rollen (Absturzsuche)")
    parser.add_argument("--data", required=True,
                        help="Ordner mit der DB-KOPIE angebotstool.db (wird DATA_ORDNER)")
    parser.add_argument("--rollen", default=STANDARD_ROLLEN,
                        help=f"Kommaliste der Hauptrollen (Standard: {STANDARD_ROLLEN})")
    parser.add_argument("--max-ids", type=int, default=0,
                        help="höchstens N IDs je Tabelle (0 = alle)")
    parser.add_argument("--benutzer", default="",
                        help="feste Benutzer je Rolle, z. B. admin=1,montage=24")
    parser.add_argument("--bericht", default="",
                        help="Berichtsdatei (Standard: <data>\\..\\crawl_bericht.txt)")
    parser.add_argument("--fremd-ids", action="store_true",
                        help="zusätzlich je Route eine nicht vorhandene ID aufrufen")
    parser.add_argument("--max-kombis", type=int, default=5000,
                        help="Obergrenze je Route bei mehreren Pfadparametern")
    return parser.parse_args()


def umgebung_setzen(daten: Path) -> None:
    """MUSS vor dem ersten `from app import …` laufen (config liest beim Import)."""
    os.environ["DATA_ORDNER"] = str(daten)
    os.environ.pop("DB_PFAD_OVERRIDE", None)
    os.environ["MONDAY_API_TOKEN"] = ""
    os.environ["GRAPH_CLIENT_ID"] = ""
    os.environ["GRAPH_TENANT_ID"] = ""


def ids_lesen(db_pfad: Path, tabelle: str, spalte: str = "id",
              bedingung: str = "") -> list:
    """IDs direkt per sqlite3 (nur lesend) – unabhängig von den ORM-Modellen."""
    verbindung = sqlite3.connect(f"file:{db_pfad.as_posix()}?mode=ro", uri=True)
    try:
        vorhanden = verbindung.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabelle,)
        ).fetchone()
        if not vorhanden:
            return []
        sql = f"SELECT {spalte} FROM {tabelle}"
        if bedingung:
            sql += f" WHERE {bedingung}"
        sql += f" ORDER BY {spalte}"
        return [zeile[0] for zeile in verbindung.execute(sql)]
    finally:
        verbindung.close()


def routen_sammeln(routen) -> list:
    """Rekursiv alle APIRoute-Objekte (FastAPI ≥ 0.140 kapselt include_router
    in _IncludedRouter mit .original_router)."""
    from fastapi.routing import APIRoute
    ergebnis = []
    for route in routen:
        original = getattr(route, "original_router", None)
        if original is not None:
            ergebnis.extend(routen_sammeln(original.routes))
        elif isinstance(route, APIRoute):
            ergebnis.append(route)
    return ergebnis


def formular_namen() -> list[str]:
    """Schlüssel des Blatts „Formulare“ (so stehen sie in der Montage-URL)."""
    try:
        from app import projektierung_logik
        namen = list(projektierung_logik.FORMULAR_NAMEN.keys())
        try:
            logik = projektierung_logik.hole_logik()
            for name in logik.formulare:
                if name not in namen:
                    namen.append(name)
        except Exception:
            pass
        return namen
    except Exception:
        return ["montagebericht", "inbetriebnahme", "abnahme"]


def sparten() -> list[str]:
    try:
        from app.leadmanagement_logik import SPARTEN
        return list(SPARTEN)
    except Exception:
        return ["WP", "PV", "KL", "WB"]


def parameter_werte(name: str, pfad: str, db_pfad: Path, max_ids: int,
                    fremd_ids: bool, cache: dict) -> list | None:
    """Werteliste für einen Pfadparameter; None = unbekannter Parameter."""
    schluessel = (name, pfad.split("/")[1] if name == "eintrag_id" else "")
    if schluessel in cache:
        return cache[schluessel]
    werte: list | None
    if name in PARAM_TABELLEN:
        werte = ids_lesen(db_pfad, PARAM_TABELLEN[name])
    elif name == "eintrag_id":
        tabelle = next((t for praefix, t in EINTRAG_TABELLEN.items()
                        if pfad.startswith(praefix)), None)
        werte = ids_lesen(db_pfad, tabelle) if tabelle else None
    elif name == "nr":
        werte = list(FRAGEBOGEN_SEITEN)
    elif name == "sparte":
        werte = sparten()
    elif name == "name":
        werte = formular_namen()
    elif name == "token":
        werte = ids_lesen(db_pfad, "angebote", "signatur_token",
                          "signatur_token IS NOT NULL AND signatur_token <> ''")
    elif name == "cid":
        werte = list(SIGNATUR_CIDS)
    else:
        werte = None
    if werte is not None and max_ids and len(werte) > max_ids:
        werte = werte[:max_ids]
    if (werte is not None and fremd_ids
            and (name in PARAM_TABELLEN or name == "eintrag_id")):
        werte = werte + [(max(werte) if werte else 0) + 100000]
    cache[schluessel] = werte
    return werte


def pfade_erzeugen(routen, db_pfad: Path, max_ids: int, fremd_ids: bool,
                   max_kombis: int) -> tuple[list[tuple[str, str]], list[str], list[str]]:
    """Liefert (Liste (Routenmuster, konkreter Pfad), übersprungene Routen,
    Routen ohne Werte)."""
    import re
    cache: dict = {}
    pfade: list[tuple[str, str]] = []
    uebersprungen: list[str] = []
    ohne_werte: list[str] = []
    for route in sorted(routen, key=lambda r: r.path):
        muster = route.path
        if muster in AUSGESCHLOSSEN:
            uebersprungen.append(f"{muster}  ({AUSGESCHLOSSEN[muster]})")
            continue
        parameter = re.findall(r"{(\w+)}", muster)
        if not parameter:
            pfade.append((muster, muster))
            continue
        listen = []
        unbekannt = None
        for name in parameter:
            werte = parameter_werte(name, muster, db_pfad, max_ids, fremd_ids, cache)
            if werte is None:
                unbekannt = name
                break
            listen.append(werte)
        if unbekannt is not None:
            uebersprungen.append(f"{muster}  (unbekannter Parameter {{{unbekannt}}})")
            continue
        if any(len(liste) == 0 for liste in listen):
            ohne_werte.append(muster)
            continue
        anzahl = 0
        for kombination in itertools.product(*listen):
            if anzahl >= max_kombis:
                break
            pfad = muster
            for name, wert in zip(parameter, kombination):
                pfad = pfad.replace("{" + name + "}", str(wert))
            pfade.append((muster, pfad))
            anzahl += 1
    return pfade, uebersprungen, ohne_werte


def benutzer_je_rolle(db_pfad: Path, rollen: list[str], fest: str) -> dict:
    """Erster aktiver Benutzer je Hauptrolle (benutzer.rolle), überschreibbar
    per --benutzer rolle=id."""
    verbindung = sqlite3.connect(f"file:{db_pfad.as_posix()}?mode=ro", uri=True)
    try:
        zeilen = verbindung.execute(
            "SELECT id, name, rolle FROM benutzer WHERE aktiv=1 ORDER BY id").fetchall()
    finally:
        verbindung.close()
    nach_id = {z[0]: z for z in zeilen}
    vorgaben = {}
    for teil in (fest or "").split(","):
        if "=" in teil:
            rolle, kennung = teil.split("=", 1)
            vorgaben[rolle.strip()] = int(kennung.strip())
    ergebnis = {}
    for rolle in rollen:
        if rolle in vorgaben and vorgaben[rolle] in nach_id:
            ergebnis[rolle] = nach_id[vorgaben[rolle]]
            continue
        treffer = next((z for z in zeilen if z[2] == rolle), None)
        ergebnis[rolle] = treffer      # None = keine Person mit dieser Rolle
    return ergebnis


def absturz_handler_registrieren(app) -> None:
    """Exception-Handler für alle unbehandelten Ausnahmen: Traceback merken,
    500 als Klartext zurückgeben. Starlette übernimmt den zuletzt registrierten
    Handler für Exception/500 in die ServerErrorMiddleware (build_middleware_stack
    läuft erst beim ersten Request)."""
    from fastapi.responses import PlainTextResponse

    vorher = app.exception_handlers.get(Exception) or app.exception_handlers.get(500)
    if vorher is not None:
        print(f"Hinweis: vorhandener 500-Handler {getattr(vorher, '__name__', vorher)} "
              "wird für den Crawl überschrieben.")

    async def handler(request, exc):
        text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        ABSTUERZE.append({
            "rolle": KONTEXT["rolle"], "benutzer": KONTEXT["benutzer"],
            "methode": request.method, "pfad": request.url.path,
            "typ": type(exc).__name__, "meldung": str(exc)[:300],
            "traceback": text, "quelle": "Exception-Handler"})
        return PlainTextResponse(f"Absturz im Crawl: {type(exc).__name__}: {exc}",
                                 status_code=500)

    if app.middleware_stack is not None:
        raise SystemExit("Middleware-Stack schon gebaut – Handler würde nicht greifen.")
    app.add_exception_handler(Exception, handler)


def traceback_kern(eintrag: dict) -> str:
    """Fehlerzeile + Ort: bevorzugt der letzte Frame unter app/ (ohne die
    Rollen-Middleware in auth.py, die jede Ausnahme nur durchreicht), sonst
    der letzte Frame überhaupt (z. B. starlette/responses.py)."""
    zeilen = eintrag["traceback"].rstrip().splitlines()
    fehlerzeile = zeilen[-1] if zeilen else f"{eintrag['typ']}: {eintrag['meldung']}"
    frames = [z.strip() for z in zeilen if z.strip().startswith("File ")]
    app_frames = [f for f in frames if "\\app\\" in f or "/app/" in f]
    ohne_middleware = [f for f in app_frames
                       if "auth.py" not in f or "dispatch" not in f]
    ort = (ohne_middleware or app_frames or frames or [""])[-1]
    ort = ort.replace(str(PROJEKT) + "\\", "").replace("venv\\Lib\\site-packages\\", "")
    return f"{fehlerzeile}  [{ort}]" if ort else fehlerzeile


def bericht_schreiben(pfad: Path, kopf: list[str], zusammenfassung: list[str],
                      status_zeilen: list[str], absturz_zeilen: list[str]) -> None:
    teile = ["VOLL-CRAWL – BERICHT", "=" * 70, *kopf, "",
             "ZUSAMMENFASSUNG", "-" * 70, *zusammenfassung, "",
             "STATUSVERTEILUNG", "-" * 70, *status_zeilen, "",
             f"ABSTÜRZE ({len(ABSTUERZE)})", "-" * 70, *absturz_zeilen, ""]
    if ABSTUERZE:
        teile += ["VOLLSTÄNDIGE TRACEBACKS", "=" * 70]
        for nr, a in enumerate(ABSTUERZE, 1):
            teile += [f"[{nr}] {a['rolle']} (Benutzer {a['benutzer']}) · "
                      f"{a['methode']} {a['pfad']} · {a['typ']} · Quelle: {a['quelle']}",
                      "-" * 70, a["traceback"].rstrip(), ""]
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("\n".join(teile), encoding="utf-8")


def main() -> int:
    try:   # Umlaute auf der Windows-Konsole; zeilenweise auch bei Umleitung in Datei
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass
    args = argumente()
    daten = Path(args.data).resolve()
    db_pfad = daten / "angebotstool.db"
    if not db_pfad.exists():
        print(f"Fehler: {db_pfad} nicht gefunden.")
        return 2
    if daten == (PROJEKT / "data").resolve():
        print("Abbruch: --data zeigt auf das Live-Verzeichnis data\\ – nur Kopien erlaubt.")
        return 2
    umgebung_setzen(daten)

    # --- erst jetzt App-Importe (config liest DATA_ORDNER beim Import) ---
    from fastapi.testclient import TestClient

    from app import auth, config, geocoding, graph_versand, monday_sync
    from app.main import app

    if Path(config.DB_PFAD).resolve() != db_pfad:
        print(f"Abbruch: config.DB_PFAD = {config.DB_PFAD}, erwartet {db_pfad}")
        return 2

    rollen = [r.strip() for r in args.rollen.split(",") if r.strip()]
    personen = benutzer_je_rolle(db_pfad, rollen, args.benutzer)
    for rolle in rollen:
        if personen[rolle] is None:
            print(f"Hinweis: kein aktiver Benutzer mit Rolle „{rolle}“ – Rolle entfällt.")
    rollen = [r for r in rollen if personen[r] is not None]
    if not rollen:
        print("Fehler: keine Rolle mit Benutzer.")
        return 2

    routen = routen_sammeln(app.routes)
    get_routen = [r for r in routen if "GET" in (r.methods or set())]
    pfade, uebersprungen, ohne_werte = pfade_erzeugen(
        get_routen, db_pfad, args.max_ids, args.fremd_ids, args.max_kombis)
    gesamt = len(pfade) * len(rollen)

    absturz_handler_registrieren(app)

    bericht_pfad = (Path(args.bericht).resolve() if args.bericht
                    else daten.parent / "crawl_bericht.txt")
    start = datetime.now()
    kopf = [f"Start: {start:%d.%m.%Y %H:%M:%S}",
            f"Datenbank: {db_pfad}",
            f"DATA_ORDNER: {config.DATA_ORDNER}",
            f"GET-Routen: {len(get_routen)} "
            f"(ohne Parameter {sum(1 for r in get_routen if '{' not in r.path)}, "
            f"mit Parameter {sum(1 for r in get_routen if '{' in r.path)})",
            f"konkrete Pfade je Rolle: {len(pfade)} · Rollen: {len(rollen)} · "
            f"geplante Aufrufe: {gesamt}",
            f"max-ids: {args.max_ids or 'alle'} · fremd-ids: {args.fremd_ids}",
            "Rollen/Benutzer: " + ", ".join(
                f"{r}={personen[r][0]} ({personen[r][1]})" for r in rollen),
            f"Formularnamen: {formular_namen()} · Sparten: {sparten()}",
            "",
            f"Ausgeschlossene Routen ({len(uebersprungen)}):",
            *[f"  - {z}" for z in uebersprungen],
            f"Routen ohne Werte in der Kopie – 0 Aufrufe ({len(ohne_werte)}):",
            *[f"  - {z}" for z in ohne_werte]]
    print("\n".join(kopf))
    print()

    statistik: dict[str, collections.Counter] = {r: collections.Counter() for r in rollen}
    langsam: list[tuple[float, str, str]] = []
    aufrufe = 0
    t0 = time.perf_counter()

    patches = [
        mock.patch.object(geocoding, "geokodieren", return_value=(None, None, "fehler")),
        mock.patch.object(monday_sync, "_api",
                          side_effect=RuntimeError("monday-API im Crawl gesperrt")),
        mock.patch.object(graph_versand, "konfiguriert", return_value=False),
        mock.patch("urllib.request.urlopen",
                   side_effect=urllib.error.URLError("externe Aufrufe im Crawl gesperrt")),
    ]
    for p in patches:
        p.start()
    try:
        for rolle in rollen:
            kennung, name, _ = personen[rolle]
            KONTEXT["rolle"] = rolle
            KONTEXT["benutzer"] = f"{kennung} {name}"
            client = TestClient(app, raise_server_exceptions=False,
                                follow_redirects=False)
            client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(kennung))
            print(f"Rolle {rolle} – Benutzer {kennung} ({name}) – {len(pfade)} Pfade")
            for muster, pfad in pfade:
                vorher = len(ABSTUERZE)
                t1 = time.perf_counter()
                try:
                    antwort = client.get(pfad)
                    status = antwort.status_code
                    koerper = antwort.text[:300] if status >= 500 else ""
                except Exception as exc:
                    status = 0
                    koerper = ""
                    if len(ABSTUERZE) == vorher:
                        ABSTUERZE.append({
                            "rolle": rolle, "benutzer": KONTEXT["benutzer"],
                            "methode": "GET", "pfad": pfad,
                            "typ": type(exc).__name__, "meldung": str(exc)[:300],
                            "traceback": traceback.format_exc(),
                            "quelle": "TestClient-Ausnahme"})
                dauer = time.perf_counter() - t1
                if dauer > 3:
                    langsam.append((dauer, rolle, pfad))
                if status >= 500 and len(ABSTUERZE) == vorher:
                    ABSTUERZE.append({
                        "rolle": rolle, "benutzer": KONTEXT["benutzer"],
                        "methode": "GET", "pfad": pfad,
                        "typ": f"HTTP {status}", "meldung": koerper,
                        "traceback": f"HTTP {status} ohne Ausnahme – Antwort:\n{koerper}",
                        "quelle": "Statuscode"})
                statistik[rolle][status] += 1
                aufrufe += 1
                if aufrufe % FORTSCHRITT_ALLE == 0:
                    laufzeit = time.perf_counter() - t0
                    rest = (gesamt - aufrufe) * laufzeit / aufrufe
                    print(f"  {aufrufe:>6}/{gesamt} Aufrufe · {rolle} · "
                          f"{laufzeit / 60:.1f} min · {len(ABSTUERZE)} Abstürze · "
                          f"Rest ≈ {rest / 60:.1f} min", flush=True)
            client.close()
    except KeyboardInterrupt:
        print("\nAbbruch durch Benutzer – Teilbericht wird geschrieben.")
    finally:
        for p in patches:
            p.stop()

    laufzeit = time.perf_counter() - t0
    gesamt_statistik = collections.Counter()
    for zaehler in statistik.values():
        gesamt_statistik.update(zaehler)

    zusammenfassung = [
        f"{aufrufe} Aufrufe · {len(ABSTUERZE)} Abstürze · Rollen "
        + ", ".join(rollen) + f" · Laufzeit {laufzeit / 60:.1f} min ({laufzeit:.0f} s)"]
    status_zeilen = ["gesamt: " + ", ".join(
        f"{s}={n}" for s, n in sorted(gesamt_statistik.items(), key=lambda x: str(x[0])))]
    for rolle in rollen:
        status_zeilen.append(f"{rolle:>13}: " + ", ".join(
            f"{s}={n}" for s, n in sorted(statistik[rolle].items(), key=lambda x: str(x[0]))))
    if langsam:
        langsam.sort(reverse=True)
        status_zeilen.append("")
        status_zeilen.append(f"langsame Aufrufe > 3 s ({len(langsam)}), Top 10:")
        status_zeilen += [f"  {d:5.1f} s  {r:<13} {p}" for d, r, p in langsam[:10]]
    absturz_zeilen = [
        f"{a['rolle']:<13} {a['methode']} {a['pfad']} · {a['typ']}: {traceback_kern(a)}"
        for a in ABSTUERZE]

    print()
    print("\n".join(zusammenfassung))
    print("\n".join(status_zeilen))
    if ABSTUERZE:
        print(f"\nAbstürze ({len(ABSTUERZE)}):")
        print("\n".join(absturz_zeilen))
    bericht_schreiben(bericht_pfad, kopf, zusammenfassung, status_zeilen, absturz_zeilen)
    print(f"\nBericht: {bericht_pfad}")
    return 1 if ABSTUERZE else 0


if __name__ == "__main__":
    raise SystemExit(main())
