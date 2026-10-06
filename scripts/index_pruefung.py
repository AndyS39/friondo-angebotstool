# v27 (PLAN_V17 Phase 128): Indexprüfung der häufigsten Abfragen mit
# EXPLAIN QUERY PLAN. Ruft die genannten Seiten über den TestClient gegen eine
# DB-KOPIE auf, fängt jede SQL-Abfrage ab (SQLAlchemy-Event) und lässt SQLite
# den Abfrageplan erklären. Gemeldet werden volle Tabellen-Scans („SCAN <tabelle>“)
# auf Tabellen mit mehr als --min-zeilen Zeilen, gruppiert nach Seite.
#
# Aufruf: venv\Scripts\python scripts\index_pruefung.py --data diagnose\test_v27_index\data
#         [--seiten /angebote,/erfassungen,...] [--min-zeilen 100] [--bericht PFAD]
# Die Kopie vorher mit migrate.py --db migrieren. Nie gegen data\ (Schutz wie voll_crawl).
import argparse
import os
import re
import sqlite3
import sys
import warnings
from collections import defaultdict
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))
warnings.filterwarnings("ignore")

STANDARD_SEITEN = [
    "/angebote", "/angebote?archiv=1", "/erfassungen", "/vorgaenge", "/vorgaenge/{vorgang_id}",
    "/leads", "/kunden", "/lead-management/hauptboard", "/lead-management/deals",
    "/lead-management/anrufliste", "/lead-management/dashboard", "/lead-management/todos",
    "/lead-management/lead/{vorgang_id}", "/projektierung", "/projektierung/liste",
    "/projektierung/termine", "/projektierung/meine-aufgaben", "/benachrichtigungen",
    "/angebote/{angebot_id}", "/statistik", "/montage",
]
_SCAN = re.compile(r"\bSCAN (?:TABLE )?(\w+)")


def argumente():
    p = argparse.ArgumentParser(description="EXPLAIN QUERY PLAN der häufigsten Seiten")
    p.add_argument("--data", required=True, help="Ordner mit der DB-KOPIE (wird DATA_ORDNER)")
    p.add_argument("--seiten", default="", help="Kommaliste von Pfaden (Standard: Liste im Skript)")
    p.add_argument("--min-zeilen", type=int, default=100)
    p.add_argument("--bericht", default="")
    p.add_argument("--rolle", default="admin")
    return p.parse_args()


def main() -> int:
    a = argumente()
    daten = Path(a.data).resolve()
    if "diagnose" not in daten.parts:
        print("Abbruch: --data muss unter diagnose\\ liegen (nie die Live-Datenbank).")
        return 2
    os.environ["DATA_ORDNER"] = str(daten)
    os.environ.pop("DB_PFAD_OVERRIDE", None)
    os.environ["MONDAY_API_TOKEN"] = ""
    os.environ["GRAPH_CLIENT_ID"] = ""
    from sqlalchemy import event
    from fastapi.testclient import TestClient
    from app import auth, db
    from app.main import app

    db_pfad = daten / "angebotstool.db"
    roh = sqlite3.connect(f"file:{db_pfad.as_posix()}?mode=ro", uri=True)
    zeilen_je_tabelle = {}
    for (name,) in roh.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        zeilen_je_tabelle[name] = roh.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]

    def erste_id(tabelle):
        z = roh.execute(f"SELECT id FROM {tabelle} ORDER BY id DESC LIMIT 1").fetchone()
        return z[0] if z else None

    ids = {"vorgang_id": erste_id("vorgaenge"), "angebot_id": erste_id("angebote")}
    benutzer_id = roh.execute(
        "SELECT id FROM benutzer WHERE rolle=? AND aktiv=1 ORDER BY id LIMIT 1", (a.rolle,)).fetchone()
    if benutzer_id is None:
        print(f"Kein aktiver Benutzer mit Rolle {a.rolle} in der Kopie.")
        return 2
    benutzer_id = benutzer_id[0]

    gesammelt: list[tuple[str, str, tuple]] = []
    aktuelle_seite = {"pfad": ""}

    @event.listens_for(db.engine, "before_cursor_execute")
    def _mitschreiben(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            gesammelt.append((aktuelle_seite["pfad"], statement, parameters))

    client = TestClient(app)
    client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    seiten = [s.strip() for s in a.seiten.split(",") if s.strip()] or STANDARD_SEITEN
    status_je_seite = {}
    for seite in seiten:
        pfad = seite
        for name, wert in ids.items():
            if "{" + name + "}" in pfad:
                if wert is None:
                    pfad = None
                    break
                pfad = pfad.replace("{" + name + "}", str(wert))
        if pfad is None:
            continue
        aktuelle_seite["pfad"] = seite
        try:
            r = client.get(pfad, follow_redirects=False)
            status_je_seite[seite] = r.status_code
        except Exception as problem:
            status_je_seite[seite] = f"Fehler {type(problem).__name__}"

    # EXPLAIN QUERY PLAN je Abfrage (dedupliziert nach Statement)
    befunde: dict[str, list[tuple[str, str]]] = defaultdict(list)
    gesehen = set()
    scans_je_tabelle: dict[str, int] = defaultdict(int)
    for seite, statement, parameter in gesammelt:
        schluessel = (seite, statement)
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        try:
            if isinstance(parameter, dict):
                plan = roh.execute("EXPLAIN QUERY PLAN " + statement, parameter).fetchall()
            else:
                plan = roh.execute("EXPLAIN QUERY PLAN " + statement, tuple(parameter or ())).fetchall()
        except Exception as problem:
            befunde[seite].append(("?", f"EXPLAIN fehlgeschlagen: {problem}"[:120]))
            continue
        for zeile in plan:
            detail = str(zeile[-1])
            treffer = _SCAN.search(detail)
            if not treffer:
                continue
            tabelle = treffer.group(1)
            if tabelle.startswith(("sqlite_", "TEMP", "temp")) or "SUBQUERY" in detail:
                continue
            if zeilen_je_tabelle.get(tabelle, 0) < a.min_zeilen:
                continue
            kurz = re.sub(r"\s+", " ", statement.split("FROM", 1)[1] if "FROM" in statement else statement)
            befunde[seite].append((tabelle, kurz[:160]))
            scans_je_tabelle[tabelle] += 1

    zeilen = ["INDEXPRÜFUNG (EXPLAIN QUERY PLAN)", f"Datenbank: {db_pfad}",
              f"Seiten: {len(status_je_seite)} · Abfragen: {len(gesehen)} · Schwelle {a.min_zeilen} Zeilen", ""]
    zeilen.append("Seiten-Status: " + ", ".join(f"{s} {st}" for s, st in status_je_seite.items()))
    zeilen.append("")
    zeilen.append("Scans je Tabelle (Anzahl Abfragen mit vollem Scan):")
    for tabelle, n in sorted(scans_je_tabelle.items(), key=lambda kv: -kv[1]):
        zeilen.append(f"  {tabelle:28s} {n:4d}   ({zeilen_je_tabelle.get(tabelle, 0)} Zeilen)")
    zeilen.append("")
    for seite, liste in befunde.items():
        zeilen.append(f"== {seite}")
        for tabelle, kurz in liste:
            zeilen.append(f"  SCAN {tabelle}: … FROM {kurz}")
    bericht = "\n".join(zeilen)
    print(bericht)
    if a.bericht:
        Path(a.bericht).write_text(bericht, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
