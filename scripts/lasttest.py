# v27 (PLAN_V17 Phase 127 Lastmodell + Phase 131): Lasttest mit virtuellen Nutzern
# gegen eine DB-KOPIE (diagnose\test_v27\data) über ECHTE HTTP-Anfragen (httpx,
# ein Thread je virtuellem Nutzer). Der Server wird als Subprozess gestartet
# (scripts\lasttest_server.py: uvicorn auf Port 8001, Lifespan + Scheduler,
# externe Dienste mit simulierter Latenz) und am Ende wieder beendet.
#
# Lastmodell (Phase 127, Zahlen [ANNAHME] – Andreas bestätigt): 50 Nutzer, davon
# 35 gleichzeitig aktiv – Rollenmix der Aktiven 15 Außendienst mobil : 12 Innendienst
# : 6 Lead-Management : 4 Projektierung/Montage (der Plan nennt 15+12+6+4 = 37 bei
# „etwa 35“; das Skript skaliert den Mix auf 70 % von --nutzer), die übrigen Nutzer
# sind angemeldete „Leser“ (alle 60–120 s eine Einstiegsseite). Denkzeit 5–15 s je
# Schritt, feste Zufallssaat (--seed), Dauer 20 Minuten.
#
# Profile (--profil): normal (Lastmodell, 50 Nutzer, 20 min) · schreibsturm (20
# Innendienst-Nutzer ändern gleichzeitig je 10 Positionen in 20 verschiedenen
# Angeboten, danach Soll/Ist-Prüfung je Position aus der Kopie) · stress (Lastmodell
# × 2 = 100 Nutzer, 10 min, nur Reserve-Faktor).
#
# Messung je Route (normalisiert, z. B. GET /angebote/{id}): Anzahl, p50, p95, p99,
# max, Fehler (HTTP 5xx, Timeouts, Verbindungsfehler); parallel alle 10 s GET /health
# (Pool-Spitze, WAL, Schreibsperre, RSS, CPU); am Ende Gegenprobe aus der zugriff.log
# der Kopie (Server-Sicht), Fehlerprotokoll/fehler.log der Kopie, Zielwerte Phase 131.
#
# Aufruf (aus dem Projektordner; nie gegen das Live-Verzeichnis data\):
#   venv\Scripts\python scripts\lasttest.py --frisch --nutzer 10 --dauer 2      (Probelauf)
#   venv\Scripts\python scripts\lasttest.py --frisch --profil normal            (Lauf 1/2)
#   venv\Scripts\python scripts\lasttest.py --frisch --profil schreibsturm
#   venv\Scripts\python scripts\lasttest.py --frisch --profil stress
#   Parameter: --nutzer N · --dauer MIN · --port 8001 · --data diagnose\test_v27\data ·
#   --seed 27 · --latenz 2.0 · --denkzeit 5-15 · --benutzer rolle=id[+id],… ·
#   --bericht PFAD (Markdown) · --frisch (Kopie neu + migrate ×2) · --nur-kopie ·
#   --kalender aus|an · --ohne-ad-profile · --ohne-server (laufenden Server nutzen)
# Ausgaben: diagnose\test_v27\lasttest_<zeit>.md (Bericht), lasttest_<zeit>.json
# (Rohdaten), server_<zeit>.log (Serverkonsole), migrate_lauf1/2.txt (bei --frisch).
# Exit-Code 0 = Zielwerte erfüllt (bzw. Schreibsturm ohne Verlust), 1 = nicht
# erfüllt, 2 = Bedienfehler/Abbruch, 3 = Tool-Fehler im Lastgenerator.
import argparse
import collections
import io
import json
import os
import random
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import warnings
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

try:
    import httpx
except ImportError:   # pragma: no cover
    print("httpx fehlt (requirements: Entwicklung) – venv\\Scripts\\pip install httpx")
    raise SystemExit(2)

PYTHON = PROJEKT / "venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)
QUELLE_DB = PROJEKT / "diagnose" / "angebotstool.db"       # Server-Kopie vom 03.10.2026
ARBEITSORDNER = PROJEKT / "diagnose" / "test_v27"
STANDARD_DATA = ARBEITSORDNER / "data"
SERVER_SKRIPT = PROJEKT / "scripts" / "lasttest_server.py"

# --- Lastmodell Phase 127 [ANNAHME] ----------------------------------------------------
ROLLEN_GEWICHTE = collections.OrderedDict(
    [("aussendienst", 15), ("innendienst", 12), ("leadmanagement", 6), ("projektierung", 4)])
ROLLEN_NAMEN = {"aussendienst": "Außendienst mobil", "innendienst": "Innendienst",
                "leadmanagement": "Lead-Management", "projektierung": "Projektierung",
                "montage": "Montage", "schreibsturm": "Innendienst (Schreibsturm)"}
AKTIV_ANTEIL = 35 / 50
PROFILE = {
    "normal": {"nutzer": 50, "dauer": 20, "denkzeit": (5.0, 15.0)},
    "schreibsturm": {"nutzer": 20, "dauer": 10, "denkzeit": (1.0, 3.0)},   # [ANNAHME] Denkzeit
    "stress": {"nutzer": 100, "dauer": 10, "denkzeit": (5.0, 15.0)},
}
LESER_PAUSE = (60.0, 120.0)          # [ANNAHME] angemeldete, nicht aktive Nutzer
SCHREIBSTURM_POSITIONEN = 10

# --- Zielwerte Phase 131 [ANNAHME] -----------------------------------------------------
ZIELWERTE_MS = collections.OrderedDict([
    ("liste_akte", 1500), ("editor_aktion", 1000), ("angebots_pdf", 4000),
    ("protokoll_pdf", 3000), ("terminvorschlaege", 6000)])
GRUPPEN_NAMEN = {"liste_akte": "Listen und Akten", "editor_aktion": "Editor-Aktionen",
                 "angebots_pdf": "Angebots-PDF", "protokoll_pdf": "Protokoll-PDF",
                 "terminvorschlaege": "Terminvorschläge", "sonstige": "übrige Schritte"}
POOL_SPITZE_MAX_PROZENT = 60.0
FEHLERQUOTE_MAX_PROZENT = 0.1
GRUPPEN_REGELN = [   # (Methode, Muster auf den normalisierten Pfad, Gruppe)
    ("GET", r"^/angebote/\{id\}/pdf$", "angebots_pdf"),
    ("GET", r"^/erfassungen/\{id\}/protokoll\.pdf$", "protokoll_pdf"),
    ("GET", r"^/lead-management/lead/\{id\}/termin/vorschlaege\.json$", "terminvorschlaege"),
    ("POST", r"^/angebote/\{id\}/(position/\{pid\}/(menge|aendern|entfernen|text)"
             r"|sortierung|gruppe|neu-nummerieren|sperre|sperre-frei)$", "editor_aktion"),
    ("GET", r"^(/|/erfassung|/erfassungen|/erfassungen/\{id\}|/angebote|/angebote/\{id\}"
            r"|/vorgaenge|/vorgaenge/\{id\}|/leads|/lead-management/hauptboard"
            r"|/lead-management/terminiert|/lead-management/lead/\{id\}|/projektierung"
            r"|/projektierung/projekt/\{id\}|/montage|/montage/einsatz/\{id\})$", "liste_akte"),
]

ANFRAGE_TIMEOUT_S = 90.0
HEALTH_INTERVALL_S = 10.0
SERVER_START_WARTEN_S = 120.0
FORTSCHRITT_ALLE_S = 30.0

# Vollständiger WP-Erfassungsbogen (Kontroll-Szenario aus tests/test_regression.py,
# Ampel grün) – Werte je Frage-ID; fehlende Fragen bekommen Standardwerte.
WP_ANTWORTEN = {
    "O01": "EFH", "O02": 1995, "O03": 1, "O04": "Nein", "O05": 180,
    "O06": "Ja", "O08": "", "O13": "",
    "A01": "Öl", "A02": 2001, "A03": 15000, "A04": "KG", "A05": 8,
    "A07": "Ja", "A08": "Kunststoff", "A09": "bis 5.000 L",
    "A10": "Nein", "A11": "Nein", "A12": "", "A13": 4,
    "A14": "Nein", "A16": "Nein", "A20": 18,
    "N01": "Luft/Wasser", "N02": "Ja", "N03": "bis 200 l",
    "N04": "Garagendach", "N05": "Nein", "N06": "50 l",
    "N09": "Nein", "N10": 0, "N11": "Nein",
    "H01": "2", "H02": "Heizkörper und Fußbodenheizung",
    "H03": "Ja", "H04": {"S": 1, "M": 0, "L": 0, "XL": 0},
    "H05": "Nein", "H06": 2, "H07": [4, 4],
    "E01": "KG", "E02": "Nein", "E04": "Nein",
    "S01": "warm", "S02": "",
    "P01": "Ja", "P02": "Nein", "P03": "Nein",
    "K02": "Öl-, Kohle-, Gasetagen- oder Nachtspeicherheizung, funktionstüchtig",
    "K03": 45000, "K04": "Ja",
}
ANRUF_ERGEBNISSE = ("nicht_erreicht", "nicht_erreicht", "mailbox", "erreicht")   # [ANNAHME] Mix


# ======================================================================================
# Argumente, Kopie, Umgebung
# ======================================================================================

def argumente() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lasttest v27: virtuelle Nutzer gegen die DB-Kopie (echte HTTP-Anfragen)")
    parser.add_argument("--profil", choices=sorted(PROFILE), default="normal")
    parser.add_argument("--nutzer", type=int, default=None, help="virtuelle Nutzer gesamt")
    parser.add_argument("--dauer", type=float, default=None, help="Dauer in Minuten")
    parser.add_argument("--denkzeit", default=None, help="Denkzeit je Schritt in s, z. B. 5-15")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--data", default=str(STANDARD_DATA),
                        help="Ordner der DB-KOPIE (wird DATA_ORDNER; muss unter diagnose\\ liegen)")
    parser.add_argument("--seed", type=int, default=27)
    parser.add_argument("--latenz", type=float, default=2.0,
                        help="simulierte Latenz je externem Aufruf im Server (s)")
    parser.add_argument("--benutzer", default="",
                        help="feste Benutzer je Rolle, z. B. aussendienst=4+7,leadmanagement=1")
    parser.add_argument("--bericht", default="", help="Markdown-Bericht (Standard: "
                        "diagnose\\test_v27\\lasttest_<zeit>.md)")
    parser.add_argument("--frisch", action="store_true",
                        help="DB-Kopie neu aus diagnose\\angebotstool.db erzeugen + migrate ×2")
    parser.add_argument("--nur-kopie", action="store_true", help="nur die Kopie erzeugen")
    parser.add_argument("--kalender", choices=("aus", "an"), default="aus",
                        help="kalender_sync in der Kopie (Outlook-Frei/Belegt gemockt)")
    parser.add_argument("--ohne-ad-profile", action="store_true",
                        help="Server legt keine AD-Profile [ANNAHME] an")
    parser.add_argument("--ohne-server", action="store_true",
                        help="keinen Server starten – laufenden Server auf --port nutzen")
    parser.add_argument("--timeout", type=float, default=ANFRAGE_TIMEOUT_S,
                        help="Timeout je Anfrage in s")
    parser.add_argument("--health-intervall", type=float, default=HEALTH_INTERVALL_S)
    parser.add_argument("--ohne-aufwaermen", action="store_true",
                        help="keine Aufwärm-Anfragen vor der Messung")
    args = parser.parse_args()
    vorgabe = PROFILE[args.profil]
    if args.nutzer is None:
        args.nutzer = vorgabe["nutzer"]
    if args.dauer is None:
        args.dauer = vorgabe["dauer"]
    if args.denkzeit is None:
        args.denkzeit_s = vorgabe["denkzeit"]
    else:
        teile = [t for t in re.split(r"[-–,; ]+", args.denkzeit.strip()) if t]
        try:
            von = float(teile[0].replace(",", "."))
            bis = float(teile[1].replace(",", ".")) if len(teile) > 1 else von
        except (ValueError, IndexError):
            parser.error("--denkzeit erwartet z. B. 5-15")
        args.denkzeit_s = (min(von, bis), max(von, bis))
    if args.nutzer < 1:
        parser.error("--nutzer muss ≥ 1 sein")
    return args


def kopie_erzeugen(daten: Path) -> list[dict]:
    """DB-Kopie per sqlite3-Backup-API aus diagnose\\angebotstool.db, dann
    migrate.py --db zweimal (DATA_ORDNER = Kopie, damit Backup/Log der
    Migration ebenfalls in der Kopie landen). Liefert die Ausgaben."""
    if not QUELLE_DB.exists():
        raise SystemExit(f"Quelle fehlt: {QUELLE_DB}")
    ziel_ordner = daten.parent
    for alt in (daten, ziel_ordner / "backup_ziel"):
        if alt.exists():
            shutil.rmtree(alt)
    daten.mkdir(parents=True, exist_ok=True)
    ziel = daten / "angebotstool.db"
    quelle = sqlite3.connect(f"file:{QUELLE_DB.as_posix()}?mode=ro", uri=True)
    sicherung = sqlite3.connect(ziel)
    try:
        quelle.backup(sicherung)
    finally:
        sicherung.close()
        quelle.close()
    print(f"Kopie erzeugt: {ziel} ({ziel.stat().st_size / 1_000_000:.1f} MB) aus {QUELLE_DB}")
    ausgaben = []
    env = dict(os.environ, DATA_ORDNER=str(daten), PYTHONIOENCODING="utf-8")
    env.pop("DB_PFAD_OVERRIDE", None)
    for lauf in (1, 2):
        ergebnis = subprocess.run(
            [str(PYTHON), "migrate.py", "--db", str(ziel)], cwd=str(PROJEKT), env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        text = (ergebnis.stdout or "") + (ergebnis.stderr or "")
        (ziel_ordner / f"migrate_lauf{lauf}.txt").write_text(text, encoding="utf-8")
        ausgaben.append({"lauf": lauf, "exit": ergebnis.returncode, "ausgabe": text})
        print(f"migrate.py Lauf {lauf}: Exit {ergebnis.returncode}")
        print("  " + text.strip().replace("\n", "\n  "))
        if ergebnis.returncode != 0:
            raise SystemExit(f"migrate.py Lauf {lauf} fehlgeschlagen")
    return ausgaben


def umgebung_setzen(daten: Path) -> None:
    """MUSS vor dem ersten `from app import …` laufen (config liest beim Import)."""
    os.environ["DATA_ORDNER"] = str(daten)
    os.environ.pop("DB_PFAD_OVERRIDE", None)
    os.environ["MONDAY_API_TOKEN"] = "lasttest"
    os.environ["GRAPH_CLIENT_ID"] = "lasttest"
    os.environ["GRAPH_TENANT_ID"] = "lasttest"
    os.environ["BACKUP_ZIEL"] = str(daten.parent / "backup_ziel")


def datenordner_pruefen(daten: Path) -> None:
    if daten == (PROJEKT / "data").resolve():
        raise SystemExit("Abbruch: --data zeigt auf das Live-Verzeichnis data\\ – nur Kopien erlaubt.")
    try:
        daten.relative_to((PROJEKT / "diagnose").resolve())
    except ValueError:
        raise SystemExit(f"Abbruch: --data muss unter {PROJEKT / 'diagnose'} liegen (Schutz).")


# ======================================================================================
# Datenpools aus der Kopie (nur lesend, sqlite3)
# ======================================================================================

def _sql(verbindung, sql: str, hinweise: list[str]) -> list:
    try:
        return verbindung.execute(sql).fetchall()
    except sqlite3.OperationalError as problem:
        hinweise.append(f"Abfrage fehlgeschlagen ({problem}): {sql[:80]}")
        return []


def pools_lesen(db_pfad: Path) -> dict:
    hinweise: list[str] = []
    v = sqlite3.connect(f"file:{db_pfad.as_posix()}?mode=ro", uri=True)
    try:
        benutzer = _sql(v, "SELECT id, name, rolle FROM benutzer WHERE aktiv=1 ORDER BY id", hinweise)
        leads = _sql(v, "SELECT id, benutzer_id FROM leads WHERE vot_datum IS NOT NULL "
                        "AND ausgeblendet=0 AND benutzer_id IS NOT NULL ORDER BY vot_datum DESC",
                     hinweise)
        erfassungen = _sql(v, "SELECT id FROM erfassungen WHERE sparte='WP' AND typ='katalog' "
                              "AND archiviert=0 AND status<>'Entwurf' AND angebot_id IS NOT NULL "
                              "ORDER BY id", hinweise)
        angebote = _sql(v, "SELECT id, status FROM angebote WHERE extern=0 AND archiviert=0 "
                           "AND status<>'Überholt' ORDER BY CASE WHEN status='Entwurf' THEN 0 "
                           "ELSE 1 END, id DESC", hinweise)
        # Lead-Vorgänge mit Koordinaten zuerst (Terminvorschläge rechnen dann mit
        # Fahrzeit-Matrix = Netzaufruf); Vorgänge mit geocode_status „fehler“ liefern
        # Vorschläge ohne Routing und wären kein Latenz-Test [ANNAHME]
        vorgaenge = _sql(v, "SELECT v.id FROM vorgaenge v JOIN kunden k ON k.id=v.kunde_id "
                            "WHERE v.lead_phase IN ('neu','in_kontaktierung','qualifiziert',"
                            "'terminiert') AND v.demo=0 AND k.plz<>'' AND v.lat IS NOT NULL "
                            "ORDER BY v.id DESC", hinweise)
        if len(vorgaenge) < 20:
            vorgaenge += _sql(v, "SELECT v.id FROM vorgaenge v JOIN kunden k ON k.id=v.kunde_id "
                                 "WHERE v.lead_phase IN ('neu','in_kontaktierung','qualifiziert',"
                                 "'terminiert') AND v.demo=0 AND k.plz<>'' AND v.lat IS NULL "
                                 "ORDER BY v.id DESC", hinweise)
        projekte = _sql(v, "SELECT id, vorgang_id FROM projekte ORDER BY id", hinweise)
        termine = _sql(v, "SELECT id, team_id FROM projekt_termine WHERE beginn IS NOT NULL "
                          "ORDER BY id", hinweise)
    finally:
        v.close()
    leads_je_ad: dict[int, list[int]] = {}
    for lead_id, benutzer_id in leads:
        leads_je_ad.setdefault(int(benutzer_id), []).append(int(lead_id))
    return {
        "benutzer": [(int(i), str(n), str(r)) for i, n, r in benutzer],
        "leads_je_ad": leads_je_ad,
        "erfassungen": [int(z[0]) for z in erfassungen],
        "angebote": [(int(z[0]), str(z[1])) for z in angebote],
        "vorgaenge_lm": [int(z[0]) for z in vorgaenge],
        "projekte": [(int(z[0]), int(z[1]) if z[1] is not None else None) for z in projekte],
        "termine": [(int(z[0]), int(z[1]) if z[1] is not None else None) for z in termine],
        "hinweise": hinweise,
    }


def benutzer_je_rolle(pools: dict, fest: str) -> tuple[dict, list[str]]:
    """Alle aktiven Benutzer je Hauptrolle (virtuelle Nutzer werden reihum
    verteilt), überschreibbar per --benutzer rolle=id+id. Rollen ohne Person in
    der Kopie fallen auf Admins zurück (Hinweis im Bericht)."""
    alle = pools["benutzer"]
    nach_id = {b[0]: b for b in alle}
    vorgaben: dict[str, list[int]] = {}
    for teil in (fest or "").split(","):
        if "=" in teil:
            rolle, ids = teil.split("=", 1)
            vorgaben[rolle.strip()] = [int(x) for x in re.split(r"[+ ]+", ids.strip()) if x.isdigit()]
    admins = [b for b in alle if b[2] == "admin"]
    hinweise: list[str] = []
    ergebnis: dict[str, list[tuple]] = {}
    for rolle in ("aussendienst", "innendienst", "leadmanagement", "projektierung", "montage"):
        if rolle in vorgaben:
            liste = [nach_id[i] for i in vorgaben[rolle] if i in nach_id]
            fehlend = [i for i in vorgaben[rolle] if i not in nach_id]
            if fehlend:
                hinweise.append(f"--benutzer {rolle}: IDs {fehlend} nicht aktiv/vorhanden – ignoriert")
        else:
            liste = [b for b in alle if b[2] == rolle]
            if rolle == "aussendienst":
                mit_leads = [b for b in liste if pools["leads_je_ad"].get(b[0])]
                if mit_leads:
                    liste = mit_leads
                elif liste:
                    hinweise.append("kein Außendienstler mit offenen Leads VOT – Szenario läuft ohne Lead")
        if not liste:
            liste = admins
            hinweise.append(f"keine aktive Person mit Hauptrolle „{rolle}“ in der Kopie – "
                            f"Admins übernehmen die Rolle [ANNAHME]")
        ergebnis[rolle] = liste
    ergebnis["schreibsturm"] = (ergebnis["innendienst"] + [a for a in admins
                                                           if a not in ergebnis["innendienst"]])
    return ergebnis, hinweise


def verteilen(anzahl: int, gewichte: dict) -> dict:
    """Ganzzahlige Verteilung nach Gewichten (größte Reste)."""
    summe = float(sum(gewichte.values())) or 1.0
    roh = {k: anzahl * g / summe for k, g in gewichte.items()}
    ergebnis = {k: int(w) for k, w in roh.items()}
    rest = anzahl - sum(ergebnis.values())
    for k in sorted(roh, key=lambda k: (roh[k] - int(roh[k]), gewichte[k]), reverse=True):
        if rest <= 0:
            break
        ergebnis[k] += 1
        rest -= 1
    return ergebnis


def nutzer_planen(args, personen: dict) -> tuple[list[dict], dict]:
    """Liste der virtuellen Nutzer: Rolle, Art (aktiv/leser), reale Person."""
    plan: list[dict] = []
    if args.profil == "schreibsturm":
        aktiv = {"schreibsturm": args.nutzer}
        leser: dict = {}
    else:
        n_aktiv = max(1, int(round(args.nutzer * AKTIV_ANTEIL))) if args.nutzer > 1 else 1
        aktiv = verteilen(n_aktiv, ROLLEN_GEWICHTE)
        leser = verteilen(args.nutzer - n_aktiv, ROLLEN_GEWICHTE)
        # Projektierung/Montage: etwa ein Viertel Montage [ANNAHME]
        montage = int(round(aktiv.get("projektierung", 0) / 4.0))
        if montage and personen.get("montage"):
            aktiv["projektierung"] -= montage
            aktiv["montage"] = montage
    zaehler: dict[str, int] = collections.Counter()
    nr = 0
    for art, verteilung in (("aktiv", aktiv), ("leser", leser)):
        for rolle, anzahl in verteilung.items():
            liste = personen.get(rolle) or personen.get("innendienst") or []
            for _ in range(anzahl):
                if not liste:
                    continue
                person = liste[zaehler[rolle] % len(liste)]
                zaehler[rolle] += 1
                nr += 1
                plan.append({"nr": nr, "rolle": rolle, "art": art,
                             "benutzer_id": person[0], "benutzer_name": person[1],
                             "benutzer_rolle": person[2]})
    uebersicht = {"aktiv": dict(aktiv), "leser": dict(leser)}
    return plan, uebersicht


# ======================================================================================
# Hilfsfunktionen: Routen-Muster, Gruppen, Perzentile, Formulare, Testfoto
# ======================================================================================

def muster(pfad: str) -> str:
    """/angebote/123/position/45/menge → /angebote/{id}/position/{pid}/menge."""
    pfad = (pfad or "/").split("?", 1)[0]
    pfad = re.sub(r"/\d+(?=/|$)", "/{id}", pfad)
    pfad = re.sub(r"/[0-9a-f]{20,}(?=/|$)", "/{token}", pfad)
    return pfad.replace("/seite/{id}", "/seite/{nr}").replace("/position/{id}/", "/position/{pid}/")


def gruppe_fuer(methode: str, pfad_muster: str) -> str:
    for m, rx, gruppe in GRUPPEN_REGELN:
        if methode == m and re.match(rx, pfad_muster):
            return gruppe
    return "sonstige"


def perzentil(werte: list, anteil: float) -> int:
    if not werte:
        return 0
    werte = sorted(werte)
    index = min(len(werte) - 1, max(0, int(round(anteil * (len(werte) - 1)))))
    return int(werte[index])


def pfad_aus_location(location: str) -> str:
    location = location or ""
    if location.startswith("http://") or location.startswith("https://"):
        rest = location.split("://", 1)[1]
        location = rest[rest.find("/"):] if "/" in rest else "/"
    return location


class SeitenParser(HTMLParser):
    """Formulare (action, method, Felder) einer HTML-Seite + Fragebogen-Fehlerfelder."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.formulare: list[dict] = []
        self.fehlerfelder: set[str] = set()
        self._form = None
        self._select = None
        self._textarea = None
        self._frage = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self._form = {"action": a.get("action") or "", "method": (a.get("method") or "get").lower(),
                          "felder": []}
            self.formulare.append(self._form)
        elif tag == "div" and a.get("data-frage"):
            self._frage = a.get("data-frage")
        elif tag == "p" and "feldfehler" in (a.get("class") or ""):
            if self._frage:
                self.fehlerfelder.add(self._frage)
        elif tag == "input" and self._form is not None:
            self._form["felder"].append({
                "name": a.get("name") or "", "typ": (a.get("type") or "text").lower(),
                "wert": a.get("value") if a.get("value") is not None else "",
                "checked": "checked" in a, "inputmode": a.get("inputmode") or ""})
        elif tag == "select" and self._form is not None:
            self._select = {"name": a.get("name") or "", "typ": "select", "optionen": [],
                            "wert": "", "checked": False, "inputmode": ""}
            self._form["felder"].append(self._select)
        elif tag == "option" and self._select is not None:
            wert = a.get("value") if a.get("value") is not None else ""
            self._select["optionen"].append(wert)
            if "selected" in a:
                self._select["wert"] = wert
        elif tag == "textarea" and self._form is not None:
            self._textarea = {"name": a.get("name") or "", "typ": "textarea", "wert": "",
                              "checked": False, "inputmode": ""}
            self._form["felder"].append(self._textarea)

    def handle_endtag(self, tag):
        if tag == "form":
            self._form = None
        elif tag == "select":
            self._select = None
        elif tag == "textarea":
            self._textarea = None

    def handle_data(self, data):
        if self._textarea is not None:
            self._textarea["wert"] += data


def seite_parsen(html: str) -> SeitenParser:
    parser = SeitenParser()
    try:
        parser.feed(html or "")
    except Exception:
        pass
    return parser


def formular_finden(parser: SeitenParser, action_teil: str) -> dict | None:
    for form in parser.formulare:
        if action_teil in form["action"]:
            return form
    return None


def felder_gruppieren(form: dict) -> dict:
    """Radios zu Gruppen zusammenfassen: name → {typ, optionen, wert, checked}."""
    gruppen: dict[str, dict] = collections.OrderedDict()
    for feld in form["felder"]:
        name = feld["name"]
        if not name:
            continue
        if feld["typ"] == "radio":
            g = gruppen.setdefault(name, {"typ": "radio", "optionen": [], "wert": "", "inputmode": ""})
            g["optionen"].append(feld["wert"])
            if feld["checked"]:
                g["wert"] = feld["wert"]
        elif feld["typ"] == "select":
            gruppen[name] = {"typ": "select", "optionen": feld["optionen"], "wert": feld["wert"],
                             "inputmode": ""}
        else:
            gruppen[name] = {"typ": feld["typ"], "optionen": [], "wert": feld["wert"],
                             "inputmode": feld.get("inputmode", ""), "checked": feld.get("checked")}
    return gruppen


def fragebogen_ausfuellen(form: dict, versuch: int = 0, fehlerfelder: set | None = None) -> dict:
    """Formulardaten für eine Seite des Erfassungsbogens: bekannte Antworten aus
    WP_ANTWORTEN, sonst erste Option / Standardwert; Fehlerfelder beim
    Wiederholversuch mit anderer Option bzw. Standardwert."""
    fehlerfelder = fehlerfelder or set()
    daten: dict[str, str] = {}
    heute = datetime.now()
    for name, feld in felder_gruppieren(form).items():
        typ = feld["typ"]
        if typ in ("file", "submit", "button", "checkbox", "image", "reset"):
            continue
        if not name.startswith("f_"):
            daten[name] = feld["wert"] or ""
            continue
        kennung = name[2:]
        fehlerhaft = kennung in fehlerfelder or kennung.split("_", 1)[0] in fehlerfelder
        if typ in ("radio", "select"):
            optionen = [o for o in feld["optionen"] if o != ""] or feld["optionen"]
            if not optionen:
                continue
            wunsch = WP_ANTWORTEN.get(kennung)
            index = optionen.index(wunsch) if isinstance(wunsch, str) and wunsch in optionen else 0
            if fehlerhaft and versuch:
                index = (index + versuch) % len(optionen)
            daten[name] = optionen[index]
        elif typ == "date":
            wunsch = WP_ANTWORTEN.get(kennung, "")
            if fehlerhaft and versuch:
                wunsch = (heute + timedelta(days=14)).strftime("%Y-%m-%d")
            daten[name] = str(wunsch or "")
        elif typ == "hidden":
            daten[name] = feld["wert"] or ""
        else:   # text, textarea, number
            numerisch = feld.get("inputmode") in ("decimal", "numeric") or typ == "number"
            basis, _, rest = kennung.partition("_")
            if rest:   # Mengenmaske f_<ID>_<Option> / Wiederholfeld f_<ID>_<i>
                wunsch = WP_ANTWORTEN.get(basis)
                if isinstance(wunsch, dict):
                    wert = wunsch.get(rest, 0)
                elif isinstance(wunsch, list):
                    i = int(rest) if rest.isdigit() else 0
                    wert = wunsch[i - 1] if 0 < i <= len(wunsch) else 1
                else:
                    wert = 1
            elif kennung in WP_ANTWORTEN:
                wert = WP_ANTWORTEN[kennung]
            else:
                wert = 10 if numerisch else "Lasttest"
            if fehlerhaft and versuch:
                wert = 10 if numerisch else "Lasttest"
            daten[name] = str(wert)
    daten["richtung"] = "weiter"
    return daten


def testfoto_erzeugen(ziel: int = 2_000_000) -> bytes:
    """JPEG mit rund 2 MB (Rauschen, 3000 × 2250 px – die Galerie verkleinert
    auf 2000 px, wie bei einem Handyfoto). Ohne Pillow: Pseudo-Datei."""
    try:
        from PIL import Image
    except ImportError:
        return b"\xff\xd8\xff\xe0" + random.Random(1).randbytes(ziel - 6) + b"\xff\xd9"
    kanaele = [Image.effect_noise((3000, 2250), 30 + 15 * i) for i in range(3)]
    bild = Image.merge("RGB", kanaele)
    lo, hi, bestes = 3, 95, b""
    for _ in range(7):
        q = (lo + hi) // 2
        puffer = io.BytesIO()
        bild.save(puffer, "JPEG", quality=q)
        inhalt = puffer.getvalue()
        if not bestes or abs(len(inhalt) - ziel) < abs(len(bestes) - ziel):
            bestes = inhalt
        if len(inhalt) < ziel:
            lo = q + 1
        else:
            hi = q - 1
        if lo > hi:
            break
    return bestes


# ======================================================================================
# Messung, Lauf-Zustand, Health-Wächter
# ======================================================================================

class LaufEnde(Exception):
    """Deadline erreicht – das laufende Szenario bricht beim nächsten Denkschritt ab."""


class Lauf:
    """Gemeinsamer Zustand aller Nutzer-Threads (Deadline, Proben, Zähler)."""

    def __init__(self, args, pools: dict, foto: bytes):
        self.args = args
        self.pools = pools
        self.foto = foto
        self.basis_url = f"http://127.0.0.1:{args.port}"
        self.stop = threading.Event()
        self.deadline = None
        self.sperre = threading.Lock()
        self.proben: list[tuple] = []
        self.zaehler: collections.Counter = collections.Counter()
        self.tool_fehler: list[str] = []
        self.schreibsturm_soll: dict[int, float] = {}
        self.schreibsturm_fehler: list[str] = []
        # frisch vom Außendienst abgesendete Erfassungen → Innendienst „Angebot erzeugen“
        self.neue_erfassungen: collections.deque = collections.deque()

    def starten(self, dauer_min: float) -> None:
        self.deadline = time.monotonic() + dauer_min * 60.0

    def aktiv(self) -> bool:
        return not self.stop.is_set() and (self.deadline is None or time.monotonic() < self.deadline)

    def aufnehmen(self, name: str, gruppe: str, status: int, dauer_ms: int, fehler: str,
                  rolle: str, nutzer: int) -> None:
        with self.sperre:
            self.proben.append((time.time(), name, gruppe, status, dauer_ms, fehler, rolle, nutzer))

    def zaehlen(self, schluessel: str, n: int = 1) -> None:
        with self.sperre:
            self.zaehler[schluessel] += n

    def tool_fehler_melden(self, text: str) -> None:
        with self.sperre:
            if len(self.tool_fehler) < 50:
                self.tool_fehler.append(text)
            self.zaehler["tool_fehler"] += 1


class HealthWaechter(threading.Thread):
    """GET /health alle N Sekunden – Pool-Spitze, WAL, Schreibsperre, RSS, CPU."""

    def __init__(self, lauf: Lauf, intervall: float):
        super().__init__(name="health", daemon=True)
        self.lauf = lauf
        self.intervall = intervall
        self.proben: list[dict] = []

    def einmal(self, client) -> dict:
        t0 = time.perf_counter()
        probe = {"zeit": datetime.now().strftime("%H:%M:%S")}
        try:
            r = client.get("/health")
            probe["http"] = r.status_code
            probe["dauer_ms"] = int((time.perf_counter() - t0) * 1000)
            d = r.json()
            pool = d.get("pool") or {}
            prozess = d.get("prozess") or {}
            probe.update({
                "status": d.get("status"), "gruende": d.get("gruende") or [],
                "pool_checked_out": pool.get("checked_out"), "pool_maximum": pool.get("maximum"),
                "pool_size": pool.get("size"), "pool_prozent": pool.get("prozent"),
                "wal_mb": d.get("wal_mb"), "db_ms": d.get("db_ms"),
                "schreibsperre_max_ms": d.get("schreibsperre_max_ms"),
                "schreibsperre_locked": d.get("schreibsperre_locked"),
                "rss_mb": prozess.get("rss_mb"), "cpu_s": prozess.get("cpu_s"),
                "threads_aktiv": prozess.get("threads"), "threads": d.get("threads"),
                "importe": d.get("importe") or [],
                "scheduler_fehler": [s.get("name") for s in (d.get("scheduler") or [])
                                     if not s.get("ok")],
                "version": d.get("version"), "commit": d.get("commit"),
                "scheduler_anzahl": len(d.get("scheduler") or []),
                "uptime_s": d.get("uptime_s"),
            })
        except Exception as problem:
            probe["fehler"] = f"{type(problem).__name__}: {problem}"[:200]
            probe["dauer_ms"] = int((time.perf_counter() - t0) * 1000)
        return probe

    def run(self):
        client = httpx.Client(base_url=self.lauf.basis_url, timeout=httpx.Timeout(30.0, connect=10.0))
        try:
            while not self.lauf.stop.is_set():
                self.proben.append(self.einmal(client))
                self.lauf.stop.wait(self.intervall)
        finally:
            client.close()


# ======================================================================================
# Virtuelle Nutzer und Szenarien
# ======================================================================================

class Nutzer(threading.Thread):
    def __init__(self, plan: dict, lauf: Lauf, cookie: str):
        super().__init__(name=f"nutzer-{plan['nr']}", daemon=True)
        self.plan = plan
        self.nr = plan["nr"]
        self.rolle = plan["rolle"]
        self.art = plan["art"]
        self.benutzer_id = plan["benutzer_id"]
        self.lauf = lauf
        self.rng = random.Random(f"{lauf.args.seed}-{self.nr}")
        from app import auth
        self.client = httpx.Client(
            base_url=lauf.basis_url, follow_redirects=False,
            timeout=httpx.Timeout(lauf.args.timeout, connect=10.0),
            headers={"Cookie": f"{auth.COOKIE_NAME}={cookie}",
                     "User-Agent": f"Friondo-Lasttest/1.0 (Nutzer {self.nr}, {self.rolle})"})
        self.angebot_id: int | None = None          # Schreibsturm
        self.leads: list[int] = []
        self.szenarien = 0

    # --- Grundfunktionen ---------------------------------------------------------------

    def denken(self, von: float | None = None, bis: float | None = None) -> None:
        """Denkzeit; nach der Deadline endet das Szenario hier (LaufEnde) –
        kein Durchhetzen der Restschritte ohne Denkzeit."""
        if von is None:
            von, bis = self.lauf.args.denkzeit_s
        dauer = self.rng.uniform(von, bis if bis is not None else von)
        ende = time.monotonic() + dauer
        while True:
            if not self.lauf.aktiv():
                raise LaufEnde()
            rest = ende - time.monotonic()
            if rest <= 0:
                return
            time.sleep(min(0.5, rest))

    def anfrage(self, methode: str, pfad: str, name: str | None = None, **kw):
        """Eine HTTP-Anfrage messen; liefert die Antwort oder None (Timeout/Verbindung)."""
        pfad = pfad_aus_location(pfad)
        name = name or f"{methode} {muster(pfad)}"
        gruppe = gruppe_fuer(name.split(" ", 1)[0], name.split(" ", 1)[1])
        t0 = time.perf_counter()
        antwort, status, fehler = None, 0, ""
        try:
            antwort = self.client.request(methode, pfad, **kw)
            status = antwort.status_code
        except httpx.TimeoutException:
            fehler = "timeout"
        except httpx.HTTPError as problem:
            fehler = "verbindung"
            self.lauf.zaehlen("verbindungsfehler_detail:" + type(problem).__name__)
        dauer_ms = int((time.perf_counter() - t0) * 1000)
        if antwort is not None and status >= 500:
            fehler = "5xx"
            text = ""
            try:
                text = antwort.text[:400]
            except Exception:
                pass
            if "kurz belegt" in text or "database is locked" in text.lower():
                fehler = "5xx_locked"
            elif "ausgelastet" in text or "QueuePool" in text or "TimeoutError" in text:
                fehler = "5xx_pool"
        self.lauf.aufnehmen(name, gruppe, status, dauer_ms, fehler, self.rolle, self.nr)
        return antwort

    def get(self, pfad: str, name: str | None = None, **kw):
        return self.anfrage("GET", pfad, name, **kw)

    def post(self, pfad: str, name: str | None = None, **kw):
        return self.anfrage("POST", pfad, name, **kw)

    def folgen(self, antwort, hops: int = 3):
        """Weiterleitungen wie ein Browser folgen (jede Station wird gemessen)."""
        while antwort is not None and antwort.status_code in (301, 302, 303, 307, 308) and hops > 0:
            ziel = pfad_aus_location(antwort.headers.get("location", ""))
            if not ziel:
                break
            antwort = self.get(ziel)
            hops -= 1
        return antwort

    @staticmethod
    def ok(antwort) -> bool:
        return antwort is not None and antwort.status_code == 200

    @staticmethod
    def location(antwort) -> str:
        if antwort is None or antwort.status_code not in (301, 302, 303, 307, 308):
            return ""
        return pfad_aus_location(antwort.headers.get("location", ""))

    def run(self):
        try:
            if self.rolle == "schreibsturm":
                self.szenario_schreibsturm()
                return
            while self.lauf.aktiv():
                try:
                    if self.art == "leser":
                        self.szenario_leser()
                    else:
                        getattr(self, f"szenario_{self.rolle}")()
                    self.szenarien += 1
                    self.lauf.zaehlen(f"szenario:{self.rolle}")
                    self.denken()
                except LaufEnde:
                    self.lauf.zaehlen("szenario_bei_laufende_abgebrochen")
                    break
                except Exception:
                    self.lauf.tool_fehler_melden(
                        f"Nutzer {self.nr} ({self.rolle}):\n" + traceback.format_exc()[-2500:])
                    try:
                        self.denken(5, 10)
                    except LaufEnde:
                        break
        finally:
            try:
                self.client.close()
            except Exception:
                pass

    # --- Szenarien ---------------------------------------------------------------------

    def szenario_leser(self) -> None:
        """Angemeldet, aber nicht aktiv: alle 60–120 s eine Einstiegsseite [ANNAHME]."""
        pfad = {"aussendienst": "/erfassung", "montage": "/montage"}.get(self.rolle, "/")
        self.folgen(self.get(pfad))
        self.denken(*LESER_PAUSE)

    def szenario_aussendienst(self) -> None:
        """Leads VOT öffnen → Erfassung starten → Bogen (alle Seiten) → Absenden →
        Protokoll-PDF (Route /erfassungen/{id}/protokoll.pdf [ANNAHME: im mobilen
        Bogen gibt es keinen Link, die Route ist für den AD erreichbar])."""
        self.get("/leads", "GET /leads")
        self.denken()
        if not self.leads:
            self.leads = list(self.lauf.pools["leads_je_ad"].get(self.benutzer_id, []))
            self.rng.shuffle(self.leads)
        if not self.leads:
            self.lauf.zaehlen("ad_ohne_leads")
            self.get("/erfassung", "GET /erfassung")
            return
        lead_id = self.leads.pop()
        r = self.get(f"/leads/{lead_id}/erfassen", "GET /leads/{id}/erfassen")
        ziel = self.location(r)
        if "/erfassung/sparten" not in ziel:
            self.lauf.zaehlen("ad_erfassen_umgeleitet")
            return
        sparten = self.get(ziel, "GET /erfassung/sparten")
        if not self.ok(sparten):
            return
        form = formular_finden(seite_parsen(sparten.text), "sparten-start")
        kunde_id = ""
        if form is not None:
            for feld in form["felder"]:
                if feld["name"] == "kunde_id":
                    kunde_id = feld["wert"]
        if not kunde_id:
            self.lauf.zaehlen("ad_sparten_ohne_kunde")
            return
        self.denken()
        r = self.post("/erfassung/sparten-start", "POST /erfassung/sparten-start",
                      data={"kunde_id": kunde_id, "lead_id": str(lead_id), "sparte_WP": "on"})
        ziel = self.location(r)
        treffer = re.match(r"^/erfassung/(\d+)/", ziel)
        if not treffer:
            self.lauf.zaehlen("ad_start_fehlgeschlagen")
            return
        erfassung_id = int(treffer.group(1))
        self.get(ziel)                                   # Startweiche
        self.denken()
        if not self.fragebogen(erfassung_id):
            return
        self.denken()
        r = self.post(f"/erfassung/{erfassung_id}/absenden", "POST /erfassung/{id}/absenden")
        if r is not None and r.status_code in (302, 303):
            self.lauf.zaehlen("ad_absenden_unvollstaendig")
            self.folgen(r)
            return
        if self.ok(r):
            with self.lauf.sperre:
                self.lauf.neue_erfassungen.append(erfassung_id)
        self.denken()
        self.get(f"/erfassungen/{erfassung_id}/protokoll.pdf", "GET /erfassungen/{id}/protokoll.pdf")

    def fragebogen(self, erfassung_id: int) -> bool:
        """Alle Seiten des Katalog-Bogens ausfüllen (Formular aus dem HTML lesen)."""
        pfad = f"/erfassung/{erfassung_id}/seite/0"
        for _ in range(20):
            seite = self.get(pfad, "GET /erfassung/{id}/seite/{nr}")
            if not self.ok(seite):
                self.lauf.zaehlen("ad_seite_nicht_ladbar")
                return False
            parser = seite_parsen(seite.text)
            form = formular_finden(parser, "/seite/")
            if form is None:
                self.lauf.zaehlen("ad_seite_ohne_formular")
                return False
            fehlerfelder: set[str] = set()
            antwort = None
            for versuch in range(3):
                daten = fragebogen_ausfuellen(form, versuch, fehlerfelder)
                self.denken()
                antwort = self.post(pfad, "POST /erfassung/{id}/seite/{nr}", data=daten)
                if antwort is None:
                    return False
                if antwort.status_code in (302, 303):
                    break
                if antwort.status_code == 200:      # Pflichtfeld-Fehler: Seite neu gerendert
                    self.lauf.zaehlen("formularfehler")
                    parser = seite_parsen(antwort.text)
                    form = formular_finden(parser, "/seite/") or form
                    fehlerfelder = set(parser.fehlerfelder)
                    continue
                return False
            else:
                self.lauf.zaehlen("fragebogen_abgebrochen")
                return False
            ziel = self.location(antwort)
            if "/pruefen" in ziel:
                self.get(ziel, "GET /erfassung/{id}/pruefen")
                return True
            if "/seite/" not in ziel:
                self.lauf.zaehlen("fragebogen_umgeleitet")
                return False
            pfad = ziel
        self.lauf.zaehlen("fragebogen_zu_viele_seiten")
        return False

    def szenario_innendienst(self) -> None:
        """Erfassungsliste → Angebot erzeugen → Editor mit 10 Positionsänderungen
        (jede Änderung lädt wie im Browser den Editor neu) → PDF → Versand
        vorbereiten (Graph gemockt) → Vorgangsakte."""
        self.get("/erfassungen", "GET /erfassungen")
        self.denken()
        # bevorzugt eine frisch vom Außendienst abgesendete Erfassung (vollständig
        # für die aktuelle Logik), sonst eine aus dem Pool der Kopie
        with self.lauf.sperre:
            erfassung_id = (self.lauf.neue_erfassungen.popleft()
                            if self.lauf.neue_erfassungen else None)
        if erfassung_id is not None:
            self.lauf.zaehlen("id_erfassung_vom_aussendienst")
        elif self.lauf.pools["erfassungen"]:
            erfassung_id = self.rng.choice(self.lauf.pools["erfassungen"])
        angebot_id = None
        vorgang_id = None
        if erfassung_id is not None:
            self.get(f"/erfassungen/{erfassung_id}", "GET /erfassungen/{id}")
            self.denken()
            r = self.get(f"/erfassungen/{erfassung_id}/angebot-erzeugen",
                         "GET /erfassungen/{id}/angebot-erzeugen")
            ziel = self.location(r)
            treffer = re.match(r"^/angebote/(\d+)$", ziel)
            if treffer:
                angebot_id = int(treffer.group(1))
                self.lauf.zaehlen("id_angebot_erzeugt")
            else:
                grund = ziel.split("?", 1)[0]
                if "fehlen+Antworten" in ziel or "fehlen Antworten" in ziel:
                    grund += " (Antworten unvollständig für die aktuelle Logik)"
                self.lauf.zaehlen(f"id_angebot_erzeugen_fallback:{grund}")
        if angebot_id is None:
            angebote = self.lauf.pools["angebote"]
            if not angebote:
                self.lauf.zaehlen("id_ohne_angebote")
                return
            angebot_id = self.rng.choice(angebote)[0]
        editor = self.get(f"/angebote/{angebot_id}", "GET /angebote/{id}")
        if not self.ok(editor):
            self.lauf.zaehlen("id_editor_nicht_ladbar")
            return
        positionen = list(dict.fromkeys(
            re.findall(rf"/angebote/{angebot_id}/position/(\d+)/aendern", editor.text)))
        treffer = re.search(r'href="/vorgaenge/(\d+)"', editor.text)
        if treffer:
            vorgang_id = int(treffer.group(1))
        self.denken()
        for i, pid in enumerate(self.rng.sample(positionen, min(10, len(positionen)))):
            if not self.lauf.aktiv():
                return
            r = self.post(f"/angebote/{angebot_id}/position/{pid}/menge",
                          "POST /angebote/{id}/position/{pid}/menge",
                          data={"menge": str(1 + (i % 3))})
            self.folgen(r)
            self.denken()
        self.get(f"/angebote/{angebot_id}/pdf", "GET /angebote/{id}/pdf")
        self.denken()
        r = self.post(f"/angebote/{angebot_id}/email", "POST /angebote/{id}/email")
        self.folgen(r)
        self.denken()
        if vorgang_id is not None:
            self.get(f"/vorgaenge/{vorgang_id}", "GET /vorgaenge/{id}")
            self.denken()
        self.post(f"/angebote/{angebot_id}/sperre-frei", "POST /angebote/{id}/sperre-frei")

    def szenario_leadmanagement(self) -> None:
        """Hauptboard → Kundenkartei → Terminvorschläge (?neu=1, Routing gemockt)
        → Anrufergebnis → Board Deals."""
        self.get("/lead-management/hauptboard", "GET /lead-management/hauptboard")
        self.denken()
        pool = self.lauf.pools["vorgaenge_lm"]
        if not pool:
            self.lauf.zaehlen("lm_ohne_vorgaenge")
            return
        vorgang_id = self.rng.choice(pool)
        self.get(f"/lead-management/lead/{vorgang_id}", "GET /lead-management/lead/{id}")
        self.denken(2, 4)      # die Kartei lädt die Vorschläge direkt nach dem Seitenaufbau
        r = self.get(f"/lead-management/lead/{vorgang_id}/termin/vorschlaege.json?neu=1",
                     "GET /lead-management/lead/{id}/termin/vorschlaege.json",
                     headers={"Accept": "application/json"})
        if self.ok(r):
            try:   # Zustand der Vorschläge zählen (ok = gerechnet, hv_lead/adresse_fehlt = sofort)
                self.lauf.zaehlen("vorschlaege_status:" + str(r.json().get("status")))
            except Exception:
                self.lauf.zaehlen("vorschlaege_status:kein_json")
        self.denken()
        r = self.post(f"/lead-management/anruf/{vorgang_id}", "POST /lead-management/anruf/{id}",
                      data={"ergebnis": self.rng.choice(ANRUF_ERGEBNISSE), "notiz": "Lasttest",
                            "dauer_sek": str(self.rng.randint(15, 180)),
                            "zurueck": f"/lead-management/lead/{vorgang_id}"})
        self.folgen(r)
        self.denken()
        self.get("/lead-management/terminiert", "GET /lead-management/terminiert")

    def szenario_projektierung(self) -> None:
        """Board → Projektakte → Aufgabe erledigen (fetch/JSON) → Galerie-Upload 2 MB."""
        self.get("/projektierung", "GET /projektierung")
        self.denken()
        projekte = self.lauf.pools["projekte"]
        if not projekte:
            self.lauf.zaehlen("proj_ohne_projekte")
            return
        projekt_id, vorgang_id = self.rng.choice(projekte)
        akte = self.get(f"/projektierung/projekt/{projekt_id}", "GET /projektierung/projekt/{id}")
        if not self.ok(akte):
            self.lauf.zaehlen("proj_akte_nicht_ladbar")
            return
        aufgaben = re.findall(r"/projektierung/aufgabe/(\d+)/erledigt-umschalten", akte.text)
        treffer = re.search(r"/vorgaenge/(\d+)/galerie/upload", akte.text)
        if treffer:
            vorgang_id = int(treffer.group(1))
        self.denken()
        if aufgaben:
            self.post(f"/projektierung/aufgabe/{self.rng.choice(aufgaben)}/erledigt-umschalten",
                      "POST /projektierung/aufgabe/{id}/erledigt-umschalten",
                      headers={"Accept": "application/json"})
            self.denken()
        if vorgang_id is None:
            self.lauf.zaehlen("proj_ohne_vorgang")
            return
        r = self.post(f"/vorgaenge/{vorgang_id}/galerie/upload", "POST /vorgaenge/{id}/galerie/upload",
                      data={"ordner": "Allgemein", "sparte": "WP", "bemerkung": "Lasttest",
                            "zurueck": f"/projektierung/projekt/{projekt_id}"},
                      files={"dateien": (f"lasttest-{self.nr}-{self.szenarien}.jpg",
                                         self.lauf.foto, "image/jpeg")})
        self.folgen(r)

    def szenario_montage(self) -> None:
        """Meine Einsätze → Einsatz → Montage-Aufgabe erledigt → Foto 2 MB."""
        liste = self.get("/montage", "GET /montage")
        self.denken()
        termine = []
        if self.ok(liste):
            termine = [int(t) for t in re.findall(r"/montage/einsatz/(\d+)", liste.text)]
        if not termine:
            termine = [t[0] for t in self.lauf.pools["termine"]]
        if not termine:
            self.lauf.zaehlen("montage_ohne_einsaetze")
            return
        termin_id = self.rng.choice(termine)
        einsatz = self.get(f"/montage/einsatz/{termin_id}", "GET /montage/einsatz/{id}")
        if not self.ok(einsatz):
            self.lauf.zaehlen("montage_einsatz_nicht_ladbar")
            return
        aufgaben = re.findall(r"/montage/aufgabe/(\d+)/erledigt", einsatz.text)
        self.denken()
        if aufgaben:
            self.post(f"/montage/aufgabe/{self.rng.choice(aufgaben)}/erledigt",
                      "POST /montage/aufgabe/{id}/erledigt",
                      data={"termin_id": str(termin_id)}, headers={"Accept": "application/json"})
            self.denken()
        r = self.post(f"/montage/einsatz/{termin_id}/foto", "POST /montage/einsatz/{id}/foto",
                      files={"datei": (f"lasttest-{self.nr}-{self.szenarien}.jpg",
                                       self.lauf.foto, "image/jpeg")})
        self.folgen(r)

    def szenario_schreibsturm(self) -> None:
        """Eigenes Angebot im Editor öffnen und 10 Positionen (Menge) ändern;
        Soll-Werte werden für die Soll/Ist-Prüfung gemerkt."""
        try:
            angebot_id = self.angebot_id
            editor = self.get(f"/angebote/{angebot_id}", "GET /angebote/{id}")
            if not self.ok(editor):
                self.lauf.schreibsturm_fehler.append(
                    f"Nutzer {self.nr}: Editor /angebote/{angebot_id} nicht ladbar")
                return
            positionen = list(dict.fromkeys(
                re.findall(rf"/angebote/{angebot_id}/position/(\d+)/aendern", editor.text)))
            if len(positionen) < SCHREIBSTURM_POSITIONEN:
                self.lauf.zaehlen("schreibsturm_wenig_positionen")
            auswahl = self.rng.sample(positionen, min(SCHREIBSTURM_POSITIONEN, len(positionen)))
            self.denken()
            for i, pid in enumerate(auswahl):
                if not self.lauf.aktiv():
                    return
                wert = 2 + ((i + self.nr) % 9)
                r = self.post(f"/angebote/{angebot_id}/position/{pid}/menge",
                              "POST /angebote/{id}/position/{pid}/menge", data={"menge": str(wert)})
                if r is not None and r.status_code in (302, 303):
                    with self.lauf.sperre:
                        self.lauf.schreibsturm_soll[int(pid)] = float(wert)
                else:
                    self.lauf.schreibsturm_fehler.append(
                        f"Nutzer {self.nr}: Position {pid} Antwort "
                        f"{r.status_code if r is not None else 'keine'}")
                self.folgen(r)
                self.denken()
            self.post(f"/angebote/{angebot_id}/sperre-frei", "POST /angebote/{id}/sperre-frei")
            self.szenarien += 1
        except Exception:
            self.lauf.tool_fehler_melden(
                f"Nutzer {self.nr} (schreibsturm):\n" + traceback.format_exc()[-2500:])


# ======================================================================================
# Server-Steuerung
# ======================================================================================

def port_belegt(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def server_starten(args, daten: Path, log_pfad: Path):
    if port_belegt(args.port):
        raise SystemExit(f"Port {args.port} ist belegt – läuft noch ein Server? (oder --ohne-server)")
    befehl = [str(PYTHON), str(SERVER_SKRIPT), "--port", str(args.port), "--data", str(daten),
              "--latenz", str(args.latenz), "--kalender", args.kalender]
    if args.ohne_ad_profile:
        befehl.append("--ohne-ad-profile")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    log = log_pfad.open("ab")
    proc = subprocess.Popen(befehl, cwd=str(PROJEKT), stdout=log, stderr=subprocess.STDOUT,
                            env=env, creationflags=flags)
    proc._lasttest_log = log   # type: ignore[attr-defined]
    return proc


def server_beenden(proc, timeout_s: float = 30.0) -> str:
    if proc is None:
        return "kein Server gestartet"
    if proc.poll() is not None:
        return f"Server war bereits beendet (Exit {proc.returncode})"
    try:
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
        proc.wait(timeout=timeout_s)
        ergebnis = f"Server sauber beendet (Exit {proc.returncode})"
    except Exception:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except Exception:
            pass
        ergebnis = "Server hart beendet (kill)"
    log = getattr(proc, "_lasttest_log", None)
    if log is not None:
        try:
            log.close()
        except Exception:
            pass
    return ergebnis


def auf_health_warten(basis_url: str, proc, sekunden: float) -> dict:
    ende = time.monotonic() + sekunden
    letzter_fehler = ""
    with httpx.Client(base_url=basis_url, timeout=httpx.Timeout(10.0, connect=2.0)) as client:
        while time.monotonic() < ende:
            if proc is not None and proc.poll() is not None:
                raise SystemExit(f"Server vorzeitig beendet (Exit {proc.returncode}) – "
                                 "siehe server_<zeit>.log")
            try:
                r = client.get("/health")
                if r.status_code == 200:
                    return r.json()
                letzter_fehler = f"HTTP {r.status_code}"
            except Exception as problem:
                letzter_fehler = type(problem).__name__
            time.sleep(1.0)
    raise SystemExit(f"Server antwortet nicht auf /health ({letzter_fehler})")


# ======================================================================================
# Auswertung
# ======================================================================================

def statistik(proben: list[tuple], schluessel_index: int) -> dict:
    """Je Route (Index 1) bzw. Gruppe (Index 2): Anzahl, p50/p95/p99/max, Fehler."""
    je: dict[str, dict] = {}
    for probe in proben:
        _zeit, name, gruppe, status, dauer_ms, fehler, _rolle, _nutzer = probe
        schluessel = probe[schluessel_index]
        e = je.setdefault(schluessel, {"dauern": [], "fehler_5xx": 0, "timeouts": 0,
                                       "verbindung": 0, "locked": 0, "pool": 0,
                                       "status": collections.Counter()})
        e["dauern"].append(dauer_ms)
        e["status"][status] += 1
        if fehler.startswith("5xx"):
            e["fehler_5xx"] += 1
            if fehler == "5xx_locked":
                e["locked"] += 1
            if fehler == "5xx_pool":
                e["pool"] += 1
        elif fehler == "timeout":
            e["timeouts"] += 1
        elif fehler == "verbindung":
            e["verbindung"] += 1
    ergebnis = {}
    for schluessel, e in je.items():
        d = e["dauern"]
        ergebnis[schluessel] = {
            "anzahl": len(d), "p50": perzentil(d, 0.50), "p95": perzentil(d, 0.95),
            "p99": perzentil(d, 0.99), "max": max(d) if d else 0,
            "mittel": int(sum(d) / len(d)) if d else 0,
            "fehler_5xx": e["fehler_5xx"], "timeouts": e["timeouts"],
            "verbindung": e["verbindung"], "locked": e["locked"], "pool": e["pool"],
            "status": {str(k): v for k, v in sorted(e["status"].items(), key=lambda kv: str(kv[0]))},
        }
    return ergebnis


def zugriffslog_auswerten(pfad: Path, start: datetime, ende: datetime, top: int = 15) -> dict:
    """Server-Sicht aus data\\log\\zugriff.log der Kopie (Zeilen im Laufzeitfenster)."""
    ergebnis = {"pfad": str(pfad), "gesamt": 0, "fehler_5xx": 0, "pool_spitze": 0,
                "pool_spitze_zeit": "", "ueber_2s": 0, "routen": [], "vorhanden": pfad.exists()}
    if not pfad.exists():
        return ergebnis
    von = start.strftime("%Y-%m-%dT%H:%M:%S")
    bis = ende.strftime("%Y-%m-%dT%H:%M:%S.999")
    je_route: dict[str, list[int]] = {}
    fehler_je_route: collections.Counter = collections.Counter()
    try:
        with pfad.open("r", encoding="utf-8", errors="replace") as f:
            for zeile in f:
                teile = zeile.rstrip("\n").split(" | ")
                if len(teile) != 8:
                    continue
                zeit, _bid, _rolle, methode, weg, status, dauer, pool = teile
                if zeit < von or zeit > bis:
                    continue
                try:
                    dauer_ms, status_nr, pool_nr = int(dauer), int(status), int(pool)
                except ValueError:
                    continue
                ergebnis["gesamt"] += 1
                route = f"{methode} {muster(weg)}"
                je_route.setdefault(route, []).append(dauer_ms)
                if dauer_ms > 2000:
                    ergebnis["ueber_2s"] += 1
                if status_nr >= 500:
                    ergebnis["fehler_5xx"] += 1
                    fehler_je_route[route] += 1
                if pool_nr > ergebnis["pool_spitze"]:
                    ergebnis["pool_spitze"], ergebnis["pool_spitze_zeit"] = pool_nr, zeit
    except OSError as problem:
        ergebnis["fehler"] = str(problem)
    for route, werte in sorted(je_route.items(), key=lambda kv: -len(kv[1]))[:top]:
        ergebnis["routen"].append({"route": route, "anzahl": len(werte),
                                   "p50": perzentil(werte, 0.5), "p95": perzentil(werte, 0.95),
                                   "max": max(werte), "fehler": fehler_je_route[route]})
    minuten = max(1.0, (ende - start).total_seconds() / 60.0)
    ergebnis["pro_minute"] = round(ergebnis["gesamt"] / minuten, 1)
    ergebnis["anteil_ueber_2s"] = (round(100.0 * ergebnis["ueber_2s"] / ergebnis["gesamt"], 2)
                                   if ergebnis["gesamt"] else 0.0)
    return ergebnis


def fehlerlog_auswerten(pfad: Path, start: datetime) -> dict:
    """data\\fehler.log der Kopie ab Laufbeginn: Fehler-Nummern (ohne Benutzer-/
    Formdaten), Zähler für „database is locked“, TimeoutError/QueuePool,
    Scheduler-Fehler je Lauf."""
    ergebnis = {"pfad": str(pfad), "vorhanden": pfad.exists(), "eintraege": [],
                "locked": 0, "locked_anfragen": 0, "timeout_error": 0, "queuepool": 0,
                "scheduler_fehler": collections.Counter(), "zeilen": 0}
    if not pfad.exists():
        return ergebnis
    von = start.strftime("%Y-%m-%d %H:%M:%S")
    kopf = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
    im_fenster = False
    try:
        with pfad.open("r", encoding="utf-8", errors="replace") as f:
            for zeile in f:
                treffer = kopf.match(zeile)
                if treffer:
                    im_fenster = treffer.group(1) >= von
                if not im_fenster:
                    continue
                ergebnis["zeilen"] += 1
                klein = zeile.lower()
                if "database is locked" in klein:
                    ergebnis["locked"] += 1
                if "timeouterror" in klein:
                    ergebnis["timeout_error"] += 1
                if "queuepool" in klein:
                    ergebnis["queuepool"] += 1
                if "Fehler-Nr. F-" in zeile and treffer:
                    teile = [t.strip() for t in zeile.split(" | ")]
                    nr = re.search(r"(F-\d{8}-\d{6}-[0-9a-f]{4})", zeile)
                    stelle = teile[1].split("?", 1)[0] if len(teile) > 1 else ""
                    typ = ""
                    if len(teile) >= 5:
                        typ = teile[4].split(":", 1)[0].strip()[:60]
                    elif len(teile) >= 3:
                        typ = teile[2][:80]
                    if nr:
                        ergebnis["eintraege"].append(
                            {"nr": nr.group(1), "stelle": stelle[:120], "typ": typ,
                             "zeit": treffer.group(1), "anfrage": stelle.startswith(("GET", "POST"))})
                        if "database is locked" in klein and stelle.startswith(("GET", "POST")):
                            ergebnis["locked_anfragen"] += 1
                sched = re.search(r"Scheduler (\S+) \(", zeile)
                if sched and treffer:
                    ergebnis["scheduler_fehler"][sched.group(1)] += 1
    except OSError as problem:
        ergebnis["fehler"] = str(problem)
    ergebnis["scheduler_fehler"] = dict(ergebnis["scheduler_fehler"])
    return ergebnis


def fehlerprotokoll_lesen(db_pfad: Path, start: datetime) -> list[dict]:
    try:
        v = sqlite3.connect(f"file:{db_pfad.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        zeilen = v.execute("SELECT fehler_nr, zeit, methode, pfad, fehlertyp FROM fehlerprotokoll "
                           "WHERE zeit >= ? ORDER BY id", (start.strftime("%Y-%m-%d %H:%M:%S"),)
                           ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        v.close()
    return [{"nr": z[0], "zeit": str(z[1])[:19], "methode": z[2], "pfad": muster(z[3] or ""),
             "typ": z[4]} for z in zeilen]


def schreibsturm_pruefen(db_pfad: Path, soll: dict[int, float]) -> dict:
    ergebnis = {"positionen": len(soll), "korrekt": 0, "abweichungen": []}
    if not soll:
        return ergebnis
    v = sqlite3.connect(f"file:{db_pfad.as_posix()}?mode=ro", uri=True)
    try:
        ids = list(soll)
        ist: dict[int, float] = {}
        for i in range(0, len(ids), 500):
            block = ids[i:i + 500]
            platz = ",".join("?" * len(block))
            for pid, menge in v.execute(
                    f"SELECT id, menge FROM angebotspositionen WHERE id IN ({platz})", block):
                ist[int(pid)] = float(menge) if menge is not None else float("nan")
    finally:
        v.close()
    for pid, wert in soll.items():
        if pid in ist and abs(ist[pid] - wert) < 1e-6:
            ergebnis["korrekt"] += 1
        else:
            ergebnis["abweichungen"].append({"position": pid, "soll": wert, "ist": ist.get(pid)})
    return ergebnis


def zielwerte_pruefen(gruppen: dict, gesamt: dict, health: list[dict], zugriff: dict,
                      fehlerlog: dict, pool_maximum: int | None) -> list[dict]:
    zeilen = []
    for gruppe, ziel in ZIELWERTE_MS.items():
        s = gruppen.get(gruppe)
        if s is None or s["anzahl"] == 0:
            zeilen.append({"kriterium": f"p95 {GRUPPEN_NAMEN[gruppe]}", "ziel": f"≤ {ziel} ms",
                           "ist": "keine Messung", "ok": None})
        else:
            zeilen.append({"kriterium": f"p95 {GRUPPEN_NAMEN[gruppe]}", "ziel": f"≤ {ziel} ms",
                           "ist": f"{s['p95']} ms (n = {s['anzahl']}, p50 {s['p50']} ms)",
                           "ok": s["p95"] <= ziel})
    timeouts_client = gesamt["timeouts"]
    timeouts_server = fehlerlog.get("timeout_error", 0) + fehlerlog.get("queuepool", 0)
    zeilen.append({"kriterium": "TimeoutError (Pool) / Client-Timeouts", "ziel": "0",
                   "ist": f"Server {timeouts_server} · Client {timeouts_client}",
                   "ok": timeouts_client == 0 and timeouts_server == 0})
    locked_ui = gesamt["locked"] + fehlerlog.get("locked_anfragen", 0)
    zeilen.append({"kriterium": "„database is locked“ an der Oberfläche", "ziel": "0",
                   "ist": f"{locked_ui} (fehler.log gesamt {fehlerlog.get('locked', 0)}, "
                          f"davon Anfragen {fehlerlog.get('locked_anfragen', 0)})",
                   "ok": locked_ui == 0})
    spitze_health = max((p.get("pool_checked_out") or 0) for p in health) if health else 0
    spitze = max(spitze_health, zugriff.get("pool_spitze", 0))
    if pool_maximum:
        prozent = 100.0 * spitze / pool_maximum
        zeilen.append({"kriterium": "Pool-Spitze", "ziel": f"≤ {POOL_SPITZE_MAX_PROZENT:.0f} % "
                       f"von {pool_maximum}", "ist": f"{spitze} ({prozent:.1f} %)",
                       "ok": prozent <= POOL_SPITZE_MAX_PROZENT})
    else:
        zeilen.append({"kriterium": "Pool-Spitze", "ziel": f"≤ {POOL_SPITZE_MAX_PROZENT:.0f} %",
                       "ist": f"{spitze} (Maximum unbekannt)", "ok": None})
    anzahl = gesamt["anzahl"]
    fehler = gesamt["fehler_5xx"] + gesamt["timeouts"] + gesamt["verbindung"]
    quote = 100.0 * fehler / anzahl if anzahl else 0.0
    zeilen.append({"kriterium": "Fehlerquote (5xx + Timeouts + Verbindungsfehler)",
                   "ziel": f"< {FEHLERQUOTE_MAX_PROZENT} %", "ist": f"{quote:.3f} % ({fehler} von {anzahl})",
                   "ok": quote < FEHLERQUOTE_MAX_PROZENT if anzahl else None})
    return zeilen


# ======================================================================================
# Bericht
# ======================================================================================

def ms(wert) -> str:
    return "–" if wert is None else f"{int(wert):,}".replace(",", ".")


def bewertung(ok) -> str:
    return "erfüllt" if ok else ("**nicht erfüllt**" if ok is False else "offen")


def bericht_markdown(d: dict) -> str:
    args = d["lauf"]
    z = []
    kopf = (f"### Lauf {args['start_text']} – Profil {args['profil']}, {args['nutzer']} Nutzer "
            f"({args['aktiv_gesamt']} aktiv), {args['dauer_min']:g} min")
    z.append(f"<!-- lasttest.py {args['zeit']} -->")
    z.append(kopf)
    z.append("")
    mix = ", ".join(f"{n} {ROLLEN_NAMEN.get(r, r)}" for r, n in args["verteilung"]["aktiv"].items() if n)
    leser = sum(args["verteilung"]["leser"].values())
    z.append(f"- Lastmodell: {mix}" + (f"; dazu {leser} angemeldete Leser" if leser else "")
             + f" · Denkzeit {args['denkzeit'][0]:g}–{args['denkzeit'][1]:g} s · Seed {args['seed']} "
             f"· Latenz je externem Aufruf {args['latenz']:g} s · Port {args['port']}")
    s = d["server"]
    z.append(f"- Server: {s.get('version', '?')} · Commit {s.get('commit', '?')} · Pool "
             f"{s.get('pool_size', '?')} (max {s.get('pool_maximum', '?')}) · Threads {s.get('threads', '?')} "
             f"· Scheduler {s.get('scheduler_anzahl', '?')} Läufe · DATA_ORDNER `{args['data']}`")
    z.append("- Benutzer je Rolle: " + "; ".join(
        f"{ROLLEN_NAMEN.get(r, r)} = {', '.join(str(i) for i in ids)}" for r, ids in args["benutzer"].items() if ids))
    for h in args.get("hinweise", []):
        z.append(f"- Hinweis: {h}")
    g = d["gesamt"]
    z.append(f"- Anfragen gesamt: {g['anzahl']} ({g['pro_minute']:.1f}/min) · 5xx {g['fehler_5xx']} "
             f"· Timeouts {g['timeouts']} · Verbindungsfehler {g['verbindung']} · Szenarien "
             f"{d['szenarien']} · Tool-Fehler {d['tool_fehler_anzahl']} · Laufzeit "
             f"{args['laufzeit_min']:.1f} min ({args['start_text']} – {args['ende_text']})")
    z.append("")
    z.append("**Antwortzeiten je Route (Client-Sicht, Millisekunden)**")
    z.append("")
    z.append("| Route | Anzahl | p50 | p95 | p99 | max | 5xx | Timeout | Verb. |")
    z.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name, s in sorted(d["routen"].items(), key=lambda kv: (-kv[1]["anzahl"], kv[0])):
        z.append(f"| `{name}` | {s['anzahl']} | {ms(s['p50'])} | {ms(s['p95'])} | {ms(s['p99'])} "
                 f"| {ms(s['max'])} | {s['fehler_5xx']} | {s['timeouts']} | {s['verbindung']} |")
    z.append("")
    z.append("**Zielwerte Phase 131 [ANNAHME]**")
    z.append("")
    z.append("| Kriterium | Ziel | Ist | Ergebnis |")
    z.append("|---|---|---|---|")
    for zeile in d["zielwerte"]:
        z.append(f"| {zeile['kriterium']} | {zeile['ziel']} | {zeile['ist']} | {bewertung(zeile['ok'])} |")
    z.append("")
    z.append("**Gruppen (p95 nach Kriterium)**")
    z.append("")
    z.append("| Gruppe | Anzahl | p50 | p95 | p99 | max | 5xx |")
    z.append("|---|---:|---:|---:|---:|---:|---:|")
    for gruppe in list(ZIELWERTE_MS) + ["sonstige"]:
        s = d["gruppen"].get(gruppe)
        if s:
            z.append(f"| {GRUPPEN_NAMEN[gruppe]} | {s['anzahl']} | {ms(s['p50'])} | {ms(s['p95'])} "
                     f"| {ms(s['p99'])} | {ms(s['max'])} | {s['fehler_5xx']} |")
    z.append("")
    h = d["health_zusammenfassung"]
    z.append(f"**Betrieb (/health alle {args['health_intervall']:g} s, {h['proben']} Proben)**: "
             f"Pool-Spitze {h['pool_spitze']} von {h['pool_maximum']} ({h['pool_prozent']:.1f} %) · "
             f"WAL max {h['wal_max_mb']} MB · Schreibsperre max {h['schreibsperre_max_ms']} ms, "
             f"locked {h['schreibsperre_locked']} · RSS max {h['rss_max_mb']} MB · CPU "
             f"{h['cpu_s']} s · /health p95 {h['health_p95_ms']} ms · Status: {h['status']}"
             + (f" · Scheduler mit Fehler: {', '.join(h['scheduler_fehler'])}" if h["scheduler_fehler"] else ""))
    zl = d["zugriffslog"]
    z.append("")
    if zl.get("vorhanden"):
        z.append(f"**Server-Sicht (zugriff.log der Kopie)**: {zl['gesamt']} Anfragen "
                 f"({zl['pro_minute']}/min) · 5xx {zl['fehler_5xx']} · Pool-Spitze zu Anfragebeginn "
                 f"{zl['pool_spitze']} · Anteil > 2 s {zl['anteil_ueber_2s']} %")
        z.append("")
        z.append("| Route (Server) | Anzahl | p50 | p95 | max | 5xx |")
        z.append("|---|---:|---:|---:|---:|---:|")
        for r in zl["routen"]:
            z.append(f"| `{r['route']}` | {r['anzahl']} | {ms(r['p50'])} | {ms(r['p95'])} "
                     f"| {ms(r['max'])} | {r['fehler']} |")
    else:
        z.append("**Server-Sicht**: zugriff.log der Kopie nicht gefunden.")
    z.append("")
    fl = d["fehlerlog"]
    fp = d["fehlerprotokoll"]
    z.append(f"**Fehlerprotokoll der Kopie**: {len(fp)} neue Tabelleneinträge · fehler.log: "
             f"{len(fl['eintraege'])} Fehler-Nummern, „database is locked“ {fl['locked']} "
             f"(Anfragen {fl['locked_anfragen']}), TimeoutError {fl['timeout_error']}, QueuePool "
             f"{fl['queuepool']}"
             + (f" · Scheduler-Fehler: " + ", ".join(f"{k} ×{v}" for k, v in fl["scheduler_fehler"].items())
                if fl["scheduler_fehler"] else ""))
    for e in fl["eintraege"][:30]:
        z.append(f"- {e['nr']} · {e['stelle']} · {e['typ']}")
    if len(fl["eintraege"]) > 30:
        z.append(f"- … {len(fl['eintraege']) - 30} weitere (siehe JSON)")
    if d.get("schreibsturm") is not None:
        st = d["schreibsturm"]
        z.append("")
        z.append(f"**Schreibsturm (Soll/Ist je Position aus der Kopie)**: {st['positionen']} "
                 f"Positionen geändert · {st['korrekt']} korrekt · {len(st['abweichungen'])} "
                 f"Abweichungen · 5xx bei Editor-Aktionen: "
                 f"{d['gruppen'].get('editor_aktion', {}).get('fehler_5xx', 0)} · "
                 f"nicht bestätigte Änderungen: {len(st.get('fehler', []))}")
        for a in st["abweichungen"][:20]:
            z.append(f"- Position {a['position']}: Soll {a['soll']:g}, Ist {a['ist']}")
        for f in st.get("fehler", [])[:10]:
            z.append(f"- {f}")
    if d.get("reserve") is not None:
        r = d["reserve"]
        z.append("")
        z.append(f"**Reserve-Faktor (Stressstufe, Ziel-p95 ÷ Ist-p95 je Gruppe; > 1 = Reserve) "
                 f"[ANNAHME]**: " + ", ".join(f"{GRUPPEN_NAMEN[k]} {v:.2f}" for k, v in r["faktoren"].items())
                 + f" · Minimum {r['minimum']:.2f} · Pool-Reserve {r['pool']:.2f}")
    zaehler = {k: v for k, v in d["zaehler"].items() if not k.startswith("szenario:")}
    if zaehler:
        z.append("")
        z.append("Zähler: " + ", ".join(f"{k} = {v}" for k, v in sorted(zaehler.items())))
    if d["tool_fehler"]:
        z.append("")
        z.append(f"**Tool-Fehler im Lastgenerator ({d['tool_fehler_anzahl']})** – erster:")
        z.append("```")
        z.append(d["tool_fehler"][0][-1500:])
        z.append("```")
    z.append("")
    z.append(f"Rohdaten: `{d['dateien']['json']}` · Serverkonsole: `{d['dateien']['server_log']}`")
    return "\n".join(z) + "\n"


def health_zusammenfassen(proben: list[dict], pool_maximum_vorgabe) -> dict:
    gueltig = [p for p in proben if "pool_checked_out" in p]
    spitze = max((p.get("pool_checked_out") or 0) for p in gueltig) if gueltig else 0
    maximum = next((p.get("pool_maximum") for p in gueltig if p.get("pool_maximum")), None) or pool_maximum_vorgabe or 0
    dauern = [p["dauer_ms"] for p in proben if "dauer_ms" in p]
    status = collections.Counter(p.get("status") or ("fehler" if "fehler" in p else "?") for p in proben)
    scheduler_fehler = sorted({n for p in gueltig for n in (p.get("scheduler_fehler") or [])})
    cpu = [p.get("cpu_s") for p in gueltig if p.get("cpu_s") is not None]
    return {
        "proben": len(proben), "pool_spitze": spitze, "pool_maximum": maximum,
        "pool_prozent": (100.0 * spitze / maximum) if maximum else 0.0,
        "wal_max_mb": max((p.get("wal_mb") or 0) for p in gueltig) if gueltig else 0,
        "schreibsperre_max_ms": max((p.get("schreibsperre_max_ms") or 0) for p in gueltig) if gueltig else 0,
        "schreibsperre_locked": max((p.get("schreibsperre_locked") or 0) for p in gueltig) if gueltig else 0,
        "rss_max_mb": max((p.get("rss_mb") or 0) for p in gueltig) if gueltig else 0,
        "cpu_s": (round(max(cpu) - min(cpu), 1) if len(cpu) > 1 else (cpu[0] if cpu else 0)),
        "health_p95_ms": perzentil(dauern, 0.95),
        "status": ", ".join(f"{k} ×{v}" for k, v in status.items()),
        "scheduler_fehler": scheduler_fehler,
    }


# ======================================================================================
# Hauptprogramm
# ======================================================================================

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass
    args = argumente()
    daten = Path(args.data).resolve()
    datenordner_pruefen(daten)
    ARBEITSORDNER.mkdir(parents=True, exist_ok=True)
    migrate_ausgaben: list[dict] = []
    if args.frisch or not (daten / "angebotstool.db").exists():
        if not args.ohne_server and port_belegt(args.port):
            raise SystemExit(f"Port {args.port} ist belegt – Kopie wird nicht ersetzt, solange "
                             "ein Server darauf läuft.")
        migrate_ausgaben = kopie_erzeugen(daten)
        if args.nur_kopie:
            return 0
    elif args.nur_kopie:
        print("Kopie vorhanden – --nur-kopie ohne --frisch tut nichts.")
        return 0

    # --- erst jetzt App-Importe (config liest DATA_ORDNER beim Import) ---
    umgebung_setzen(daten)
    from app import auth, config
    db_pfad = daten / "angebotstool.db"
    if Path(config.DB_PFAD).resolve() != db_pfad:
        raise SystemExit(f"Abbruch: config.DB_PFAD = {config.DB_PFAD}, erwartet {db_pfad}")
    auth._geheimnis()          # .session_secret der Kopie vor dem Serverstart anlegen

    pools = pools_lesen(db_pfad)
    personen, hinweise = benutzer_je_rolle(pools, args.benutzer)
    hinweise = pools["hinweise"] + hinweise
    plan, verteilung = nutzer_planen(args, personen)
    if not plan:
        raise SystemExit("keine virtuellen Nutzer planbar (keine aktiven Benutzer in der Kopie?)")
    if args.profil == "schreibsturm":
        angebote = [a[0] for a in pools["angebote"]]
        if len(angebote) < len(plan):
            hinweise.append(f"nur {len(angebote)} bearbeitbare Angebote für {len(plan)} Nutzer – "
                            "Angebote werden mehrfach verwendet (Sperre!)")
        rng = random.Random(args.seed)
        rng.shuffle(angebote)
        for i, p in enumerate(plan):
            p["angebot_id"] = angebote[i % len(angebote)] if angebote else None

    zeit = datetime.now().strftime("%Y%m%d-%H%M%S")
    server_log = ARBEITSORDNER / f"server_{zeit}.log"
    json_pfad = ARBEITSORDNER / f"lasttest_{zeit}.json"
    bericht_pfad = Path(args.bericht).resolve() if args.bericht else ARBEITSORDNER / f"lasttest_{zeit}.md"
    print(f"Lasttest v27 · Profil {args.profil} · {len(plan)} Nutzer "
          f"(aktiv {verteilung['aktiv']}, Leser {verteilung['leser']}) · {args.dauer:g} min · "
          f"Denkzeit {args.denkzeit_s[0]:g}–{args.denkzeit_s[1]:g} s · Seed {args.seed}")
    print(f"  Kopie: {db_pfad}")
    print("  Benutzer: " + "; ".join(f"{r} = {[b[0] for b in ids]}" for r, ids in personen.items()
                                     if r != "schreibsturm" or args.profil == "schreibsturm"))
    for h in hinweise:
        print(f"  Hinweis: {h}")

    foto = testfoto_erzeugen()
    print(f"  Testfoto: {len(foto) / 1_000_000:.2f} MB JPEG")
    lauf = Lauf(args, pools, foto)
    proc = None
    exit_code = 0
    start = datetime.now()
    health = HealthWaechter(lauf, args.health_intervall)
    nutzer: list[Nutzer] = []
    try:
        if not args.ohne_server:
            print(f"  Server wird gestartet (Log {server_log}) …")
            proc = server_starten(args, daten, server_log)
        health_start = auf_health_warten(lauf.basis_url, proc, SERVER_START_WARTEN_S)
        print(f"  Server bereit: {health_start.get('version')} Commit {health_start.get('commit')} · "
              f"Pool {health_start.get('pool', {}).get('size')} (max "
              f"{health_start.get('pool', {}).get('maximum')}) · Threads {health_start.get('threads')} "
              f"· Scheduler {len(health_start.get('scheduler') or [])} · Status {health_start.get('status')}")
        cookies = {}
        for p in plan:
            if p["benutzer_id"] not in cookies:
                cookies[p["benutzer_id"]] = auth.cookie_wert(p["benutzer_id"])
        for p in plan:
            n = Nutzer(p, lauf, cookies[p["benutzer_id"]])
            n.angebot_id = p.get("angebot_id")
            nutzer.append(n)
        if not args.ohne_aufwaermen:
            # Aufwärmen (nicht gemessen): Logik-Excel, Templates, Caches wie bei
            # einem Server, der schon eine Weile läuft [ANNAHME]
            gesehen = set()
            for n in nutzer:
                if n.benutzer_id in gesehen:
                    continue
                gesehen.add(n.benutzer_id)
                pfade = {"aussendienst": ["/erfassung", "/leads"], "montage": ["/montage"],
                         "leadmanagement": ["/lead-management/hauptboard"],
                         "projektierung": ["/projektierung"]}.get(n.rolle, ["/", "/erfassungen"])
                if n.rolle in ("innendienst", "schreibsturm") and pools["erfassungen"]:
                    pfade.append(f"/erfassungen/{pools['erfassungen'][0]}")
                for pfad in pfade:
                    try:
                        n.client.get(pfad)
                    except Exception:
                        pass
            print("  Aufwärmen abgeschlossen")
        start = datetime.now()
        lauf.starten(args.dauer)
        health.start()
        for n in nutzer:
            n.start()
            time.sleep(0.05)       # gestaffelter Start (nicht alle zur gleichen Sekunde)
        letzte_ausgabe = time.monotonic()
        while lauf.aktiv() and any(n.is_alive() for n in nutzer):
            time.sleep(1.0)
            if time.monotonic() - letzte_ausgabe >= FORTSCHRITT_ALLE_S:
                letzte_ausgabe = time.monotonic()
                with lauf.sperre:
                    anzahl = len(lauf.proben)
                    fehler = sum(1 for p in lauf.proben if p[5])
                letzte = health.proben[-1] if health.proben else {}
                rest = max(0.0, (lauf.deadline - time.monotonic()) / 60.0)
                print(f"  {datetime.now():%H:%M:%S} · {anzahl} Anfragen · {fehler} Fehler · "
                      f"Pool {letzte.get('pool_checked_out', '?')} · RSS {letzte.get('rss_mb', '?')} MB · "
                      f"Rest {rest:.1f} min · Threads aktiv {sum(1 for n in nutzer if n.is_alive())}",
                      flush=True)
    except KeyboardInterrupt:
        print("\nAbbruch durch Benutzer – Teilbericht wird geschrieben.")
        exit_code = 2
    except SystemExit as problem:
        print(f"Abbruch: {problem}")
        exit_code = 2
        lauf.stop.set()
        if proc is not None:
            print("  " + server_beenden(proc))
        return exit_code
    finally:
        lauf.stop.set()
    for n in nutzer:
        n.join(timeout=args.timeout + 5)
    health_ende = None
    try:
        with httpx.Client(base_url=lauf.basis_url, timeout=15.0) as c:
            health_ende = c.get("/health").json()
    except Exception:
        pass
    if health.is_alive():
        health.join(timeout=15)
    ende = datetime.now()
    server_status = server_beenden(proc) if proc is not None else "laufender Server bleibt bestehen"
    print(f"  {server_status}")

    # --- Auswertung -------------------------------------------------------------------
    with lauf.sperre:
        proben = list(lauf.proben)
    routen = statistik(proben, 1)
    gruppen = statistik(proben, 2)
    alle = statistik([(0, "alle", "alle", p[3], p[4], p[5], p[6], p[7]) for p in proben], 1).get(
        "alle", {"anzahl": 0, "fehler_5xx": 0, "timeouts": 0, "verbindung": 0, "locked": 0, "pool": 0,
                 "p50": 0, "p95": 0, "p99": 0, "max": 0, "mittel": 0, "status": {}})
    laufzeit_min = max(1e-6, (ende - start).total_seconds() / 60.0)
    alle["pro_minute"] = alle["anzahl"] / laufzeit_min
    pool_maximum = (health_ende or health_start or {}).get("pool", {}).get("maximum")
    zugriff = zugriffslog_auswerten(config.LOG_ORDNER / "zugriff.log", start, ende)
    fehlerlog = fehlerlog_auswerten(daten / "fehler.log", start)
    protokoll = fehlerprotokoll_lesen(db_pfad, start)
    zielwerte = zielwerte_pruefen(gruppen, alle, health.proben, zugriff, fehlerlog, pool_maximum)
    schreibsturm = None
    if args.profil == "schreibsturm":
        schreibsturm = schreibsturm_pruefen(db_pfad, lauf.schreibsturm_soll)
        schreibsturm["fehler"] = list(lauf.schreibsturm_fehler)
    reserve = None
    if args.profil == "stress":
        faktoren = {g: (ziel / gruppen[g]["p95"]) for g, ziel in ZIELWERTE_MS.items()
                    if g in gruppen and gruppen[g]["p95"] > 0}
        hz = health_zusammenfassen(health.proben, pool_maximum)
        reserve = {"faktoren": faktoren, "minimum": min(faktoren.values()) if faktoren else 0.0,
                   "pool": (POOL_SPITZE_MAX_PROZENT / hz["pool_prozent"]) if hz["pool_prozent"] else 0.0}
    hs = health_start if "health_start" in locals() else {}
    daten_json = {
        "lauf": {
            "zeit": zeit, "profil": args.profil, "nutzer": len(plan),
            "aktiv_gesamt": sum(verteilung["aktiv"].values()), "verteilung": verteilung,
            "dauer_min": args.dauer, "laufzeit_min": laufzeit_min,
            "denkzeit": list(args.denkzeit_s), "seed": args.seed, "latenz": args.latenz,
            "port": args.port, "data": str(daten), "kalender": args.kalender,
            "health_intervall": args.health_intervall,
            "start": start.isoformat(timespec="seconds"), "ende": ende.isoformat(timespec="seconds"),
            "start_text": start.strftime("%d.%m.%Y %H:%M:%S"), "ende_text": ende.strftime("%H:%M:%S"),
            "benutzer": {r: [b[0] for b in ids] for r, ids in personen.items()
                         if r != "schreibsturm" or args.profil == "schreibsturm"},
            "plan": plan, "hinweise": hinweise, "server_status": server_status,
            "migrate": migrate_ausgaben,
        },
        "server": {"version": hs.get("version"), "commit": hs.get("commit"),
                   "pool_size": (hs.get("pool") or {}).get("size"),
                   "pool_maximum": (hs.get("pool") or {}).get("maximum"),
                   "threads": hs.get("threads"), "scheduler_anzahl": len(hs.get("scheduler") or []),
                   "health_start": hs, "health_ende": health_ende},
        "gesamt": alle, "routen": routen, "gruppen": gruppen, "zielwerte": zielwerte,
        "health": health.proben, "health_zusammenfassung": health_zusammenfassen(health.proben, pool_maximum),
        "zugriffslog": zugriff, "fehlerlog": fehlerlog, "fehlerprotokoll": protokoll,
        "schreibsturm": schreibsturm, "reserve": reserve,
        "szenarien": sum(n.szenarien for n in nutzer), "zaehler": dict(lauf.zaehler),
        "tool_fehler": lauf.tool_fehler, "tool_fehler_anzahl": lauf.zaehler.get("tool_fehler", 0),
        "anfragen": [[datetime.fromtimestamp(p[0]).strftime("%H:%M:%S.%f")[:-3], p[1], p[2], p[3],
                      p[4], p[5], p[6], p[7]] for p in proben],
        "dateien": {"json": str(json_pfad), "server_log": str(server_log), "bericht": str(bericht_pfad)},
    }
    json_pfad.write_text(json.dumps(daten_json, ensure_ascii=False, indent=1, default=str),
                         encoding="utf-8")
    text = bericht_markdown(daten_json)
    bericht_pfad.parent.mkdir(parents=True, exist_ok=True)
    bericht_pfad.write_text(text, encoding="utf-8")
    print()
    print(text)
    print(f"Bericht: {bericht_pfad}")
    print(f"JSON:    {json_pfad}")
    if exit_code:
        return exit_code
    if lauf.zaehler.get("tool_fehler"):
        return 3
    if args.profil == "schreibsturm":
        ok = (schreibsturm is not None and not schreibsturm["abweichungen"]
              and gruppen.get("editor_aktion", {}).get("fehler_5xx", 0) == 0)
        return 0 if ok else 1
    return 0 if all(z["ok"] is not False for z in zielwerte) else 1


if __name__ == "__main__":
    raise SystemExit(main())
