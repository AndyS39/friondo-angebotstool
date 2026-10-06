# v27 (PLAN_V17 Phase 131): Server für den Lasttest – startet das Angebotstool
# per uvicorn auf einem eigenen Port (Standard 8001) gegen die DB-KOPIE
# diagnose\test_v27\data, MIT Lifespan (alle Scheduler laufen im Normaltakt mit),
# Pool-/Thread-Werten wie der Server (Standard aus app.config bzw. .env).
#
# Externe Dienste sind abgeklemmt, antworten aber mit SIMULIERTER LATENZ
# (--latenz, Standard 2 s), damit die Sitzungsdisziplin („keine offene Sitzung
# während Netz-I/O“) unter realen Wartezeiten geprüft wird:
#   routing._ors_matrix / _google_matrix   → plausible Matrix (Luftlinie × 1,3) nach 2 s
#   geocoding._nominatim / _ors / _google  → Koordinaten im Raum Duisburg nach 2 s
#   graph_versand._graph_aufruf            → Graph-Antwort (leere Listen, Entwurf-ID) nach 2 s
#   graph_versand._token / kalender._token → fester Pseudo-Token (ohne Wartezeit, wie
#                                            der msal-Cache); konfiguriert() → True
#   mail_sync._graph_get                   → {"value": []} nach 2 s
#   monday_sync._api                       → leere Boards nach 2 s (MONDAY_API_TOKEN="lasttest")
#   heizreport_api._roh_anfrage            → HTTP 200 mit leerem JSON nach 2 s
#   urllib.request.urlopen                 → wirft (Sicherheitsnetz gegen JEDEN echten Netzaufruf)
#   graph_versand._app (msal)              → wirft (Sicherheitsnetz)
# Die Mocks werden per unittest.mock.patch VOR uvicorn.run(app) im selben Prozess
# gesetzt. Fehlt ein Name (Modul umgebaut), wird das gemeldet, der Start läuft
# weiter – das urlopen-Sicherheitsnetz verhindert trotzdem jeden echten Zugriff.
#
# Vorbereitung der Kopie (einmal je Start, idempotent; --ohne-vorbereitung schaltet ab):
#   Lead-Parameter parser_modus=an (2-Minuten-Postfachlauf aktiv, Graph gemockt),
#   routing_anbieter=ors + ors_api_key=lasttest (Terminvorschläge rufen die Matrix),
#   kalender_sync laut --kalender (Standard aus, wie in der Server-Kopie),
#   [ANNAHME] AD-Profile mit Startkoordinaten für alle aktiven Außendienstler ohne
#   Profil (--ohne-ad-profile schaltet ab) – ohne Profile hätten die Terminvorschläge
#   keine Kandidaten und damit keinen Netzaufruf.
#
# Aufruf (normalerweise durch scripts\lasttest.py als Subprozess):
#   venv\Scripts\python scripts\lasttest_server.py [--port 8001] [--data diagnose\test_v27\data]
#       [--latenz 2.0] [--kalender aus|an] [--ohne-ad-profile] [--ohne-vorbereitung]
#       [--log-level info]
# Nie gegen das Live-Verzeichnis data\ – --data muss unter diagnose\ liegen (Schutz eingebaut).
import argparse
import hashlib
import json
import math
import os
import sys
import threading
import time
import urllib.error
from pathlib import Path
from unittest import mock

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

STANDARD_DATA = PROJEKT / "diagnose" / "test_v27" / "data"
PSEUDO_TOKEN = "lasttest-token"
LATENZ = [2.0]                      # Sekunden je gemocktem Netzaufruf
ZAEHLER = {"aufrufe": 0}
_zaehler_sperre = threading.Lock()
# Startkoordinaten der AD-Profile [ANNAHME]: Raum Duisburg, je Profil leicht versetzt
DUISBURG = (51.4344, 6.7623)
STANDARD_ARBEITSZEITEN = {t: ["08:00", "18:00"] for t in ("mo", "di", "mi", "do", "fr")}


def argumente() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lasttest-Server: uvicorn gegen die DB-Kopie, externe Dienste mit Latenz gemockt")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--data", default=str(STANDARD_DATA),
                        help="Ordner mit der DB-KOPIE angebotstool.db (wird DATA_ORDNER)")
    parser.add_argument("--latenz", type=float, default=2.0,
                        help="simulierte Latenz je externem Aufruf in Sekunden (Standard 2)")
    parser.add_argument("--kalender", choices=("aus", "an"), default="aus",
                        help="Lead-Parameter kalender_sync in der Kopie (Standard aus)")
    parser.add_argument("--ohne-ad-profile", action="store_true",
                        help="keine AD-Profile für Außendienstler ohne Profil anlegen")
    parser.add_argument("--ohne-vorbereitung", action="store_true",
                        help="Kopie nicht anfassen (keine Parameter, keine Profile)")
    parser.add_argument("--log-level", default="info")
    return parser.parse_args()


def umgebung_setzen(daten: Path) -> None:
    """MUSS vor dem ersten `from app import …` laufen (config liest beim Import)."""
    os.environ["DATA_ORDNER"] = str(daten)
    os.environ.pop("DB_PFAD_OVERRIDE", None)
    os.environ["MONDAY_API_TOKEN"] = "lasttest"
    os.environ["GRAPH_CLIENT_ID"] = "lasttest"
    os.environ["GRAPH_TENANT_ID"] = "lasttest"
    # Spiegelung der Sicherung nie nach außen: Zielordner neben der Kopie
    os.environ["BACKUP_ZIEL"] = str(daten.parent / "backup_ziel")


# --- Mocks (Latenz) ----------------------------------------------------------------

def _warten() -> None:
    with _zaehler_sperre:
        ZAEHLER["aufrufe"] += 1
    if LATENZ[0] > 0:
        time.sleep(LATENZ[0])


def _koordinaten(adresse: str) -> tuple[float, float]:
    """Deterministische Koordinaten im Raum Duisburg/Niederrhein je Adresse."""
    h = int(hashlib.sha256((adresse or "").encode("utf-8", "replace")).hexdigest()[:10], 16)
    lat = 51.25 + (h % 1000) / 1000.0 * 0.40
    lon = 6.55 + ((h // 1000) % 1000) / 1000.0 * 0.45
    return round(lat, 6), round(lon, 6)


def _luftlinie_km(von: tuple, nach: tuple) -> float:
    r = 6371.0
    lat1, lon1 = math.radians(von[0]), math.radians(von[1])
    lat2, lon2 = math.radians(nach[0]), math.radians(nach[1])
    a = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def mock_nominatim(adresse: str):
    _warten()
    return _koordinaten(adresse)


def mock_geocode_mit_schluessel(adresse: str, schluessel: str):
    _warten()
    return _koordinaten(adresse)


def mock_matrix(quellen: list, ziele: list, schluessel: str):
    """Plausible Matrix: Straße = Luftlinie × 1,3, Tempo 50 km/h."""
    _warten()
    dauern, strecken = [], []
    for q in quellen:
        zeile_d, zeile_s = [], []
        for z in ziele:
            km = _luftlinie_km(q, z) * 1.3
            zeile_s.append(round(km * 1000.0, 1))
            zeile_d.append(round(km / 50.0 * 3600.0, 1))
        dauern.append(zeile_d)
        strecken.append(zeile_s)
    return dauern, strecken


def mock_graph_aufruf(methode: str, pfad: str, token: str, daten: dict | None = None) -> dict:
    _warten()
    nr = ZAEHLER["aufrufe"]
    pfad = pfad or ""
    if methode.upper() == "POST":
        if "/attachments" in pfad or pfad.endswith("/send") or pfad.endswith("/sendMail"):
            return {}
        if "/messages" in pfad:
            return {"id": f"lasttest-nachricht-{nr}",
                    "webLink": "https://outlook.office.com/lasttest",
                    "conversationId": f"lasttest-konversation-{nr}"}
        if "/events" in pfad:
            return {"id": f"lasttest-ereignis-{nr}"}
        return {"id": f"lasttest-{nr}"}
    if methode.upper() in ("PATCH", "DELETE"):
        return {}
    return {"value": []}


def mock_graph_get(pfad: str, token: str) -> dict:
    _warten()
    return {"value": []}


def mock_token():
    return PSEUDO_TOKEN


def mock_angemeldet():
    return "lasttest@friondo.local"


def mock_konfiguriert(*_a, **_k) -> bool:
    return True


def _monday_titel() -> list[str]:
    """Gruppentitel der monday-Quellen aus der Kopie (für „leere Boards“)."""
    try:
        from app.db import SessionLocal
        from app.models import MondayQuelle
        s = SessionLocal()
        try:
            titel = sorted({(q.gruppen_titel or "").strip() for q in s.query(MondayQuelle)})
        finally:
            s.close()
        return [t for t in titel if t] or ["Terminiert"]
    except Exception:
        return ["Terminiert"]


MONDAY_TITEL: list[str] = []


def mock_monday_api(query: str, variablen: dict | None = None) -> dict:
    _warten()
    text = query or ""
    if "items_page" in text:
        return {"boards": [{"groups": [{"items_page": {"cursor": None, "items": []}}]}]}
    if "columns" in text:
        return {"boards": [{"columns": []}]}
    if "groups" in text:
        return {"boards": [{"name": "Lasttest-Board",
                            "groups": [{"id": f"g{i}", "title": t}
                                       for i, t in enumerate(MONDAY_TITEL or ["Terminiert"])]}]}
    if "mutation" in text:
        return {"change_multiple_column_values": {"id": "0"},
                "change_column_value": {"id": "0"}, "create_item": {"id": "0"}}
    return {"boards": []}


def mock_heizreport(methode: str, url: str, kopf: dict, koerper, timeout: float):
    _warten()
    return 200, b'{"status": "ok", "data": []}', {"Content-Type": "application/json"}


def sperre_urlopen(*_a, **_k):
    raise urllib.error.URLError("Lasttest: externe Aufrufe sind gesperrt (urlopen)")


def sperre_msal(*_a, **_k):
    raise RuntimeError("Lasttest: msal/Device-Flow ist gesperrt")


def patches_setzen() -> tuple[list, list, list]:
    """Alle Mocks setzen; liefert (aktive Patches, gesetzte Namen, fehlende Namen)."""
    from app import geocoding, graph_versand, heizreport_api, kalender, mail_sync, monday_sync, routing
    plan = [
        (routing, "_ors_matrix", mock_matrix),
        (routing, "_google_matrix", mock_matrix),
        (geocoding, "_nominatim", mock_nominatim),
        (geocoding, "_ors", mock_geocode_mit_schluessel),
        (geocoding, "_google", mock_geocode_mit_schluessel),
        (graph_versand, "_graph_aufruf", mock_graph_aufruf),
        (graph_versand, "_token", mock_token),
        (graph_versand, "angemeldeter_benutzer", mock_angemeldet),
        (graph_versand, "konfiguriert", mock_konfiguriert),
        (graph_versand, "_app", sperre_msal),
        (kalender, "_token", mock_token),
        (mail_sync, "_graph_get", mock_graph_get),
        (monday_sync, "_api", mock_monday_api),
        (heizreport_api, "_roh_anfrage", mock_heizreport),
    ]
    patches, gesetzt, fehlend = [], [], []
    for modul, name, ersatz in plan:
        if hasattr(modul, name):
            p = mock.patch.object(modul, name, ersatz)
            p.start()
            patches.append(p)
            gesetzt.append(f"{modul.__name__}.{name}")
        else:
            fehlend.append(f"{modul.__name__}.{name}")
    p = mock.patch("urllib.request.urlopen", side_effect=sperre_urlopen)
    p.start()
    patches.append(p)
    gesetzt.append("urllib.request.urlopen (Sicherheitsnetz)")
    return patches, gesetzt, fehlend


# --- Vorbereitung der Kopie ------------------------------------------------------

def kopie_vorbereiten(kalender: str, ad_profile: bool) -> list[str]:
    """Parameter und [ANNAHME]-Testdaten in der Kopie (idempotent)."""
    from app import leadmanagement as kern
    from app.db import SessionLocal
    from app.models import AdProfil, Benutzer
    meldungen: list[str] = []
    werte = {
        "parser_modus": "an",                 # 2-Minuten-Postfachlauf aktiv (Graph gemockt)
        "routing_anbieter": "ors",            # Terminvorschläge rufen die (gemockte) Matrix
        "ors_api_key": "lasttest",
        "kalender_sync": kalender,
        "kalender_testpostfach": "lasttest-kalender@friondo.local",
    }
    s = SessionLocal()
    try:
        for name, wert in werte.items():
            alt = kern.parameter_holen(s, name, "")
            if alt != wert:
                kern.parameter_setzen(s, name, wert)
                meldungen.append(f"Lead-Parameter {name}: {alt!r} → {wert!r}")
        if ad_profile:
            profile = {p.benutzer_id: p for p in s.query(AdProfil)}
            ads = [b for b in s.query(Benutzer).filter(Benutzer.aktiv.is_(True))
                   .order_by(Benutzer.id) if b.rolle == "aussendienst"]
            for i, b in enumerate(ads):
                lat = round(DUISBURG[0] + ((i * 37) % 11 - 5) * 0.012, 6)
                lon = round(DUISBURG[1] + ((i * 53) % 13 - 6) * 0.015, 6)
                profil = profile.get(b.id)
                if profil is None:
                    s.add(AdProfil(
                        benutzer_id=b.id, start_adresse="Lasttest-Startadresse",
                        start_lat=lat, start_lon=lon,
                        arbeitszeiten=json.dumps(STANDARD_ARBEITSZEITEN),
                        termin_dauer_min=90, puffer_min=30, max_termine_tag=3,
                        gebiet_plz_praefixe="[]", aktiv_terminierung=True,
                        terminiert_selbst=False,
                        kompetenz_sparten=json.dumps(["WP", "PV", "KL", "WB", "GW"]),
                        kompetenz_kombi=True, kompetenz_mfh=True, kompetenz_gewerbe=True))
                    meldungen.append(f"AD-Profil angelegt für Benutzer {b.id} [ANNAHME]")
                elif profil.start_lat is None:
                    # migrate.py legt Profile nur mit Kompetenzen an – ohne Startpunkt
                    # gäbe es keine Fahrzeit-Matrix (kein Netzaufruf) [ANNAHME]
                    profil.start_lat, profil.start_lon = lat, lon
                    profil.start_adresse = profil.start_adresse or "Lasttest-Startadresse"
                    if not profil.arbeitszeiten or profil.arbeitszeiten == "{}":
                        profil.arbeitszeiten = json.dumps(STANDARD_ARBEITSZEITEN)
                    meldungen.append(f"AD-Profil {b.id}: Startkoordinaten ergänzt [ANNAHME]")
        s.commit()
    finally:
        s.close()
    return meldungen


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass
    args = argumente()
    daten = Path(args.data).resolve()
    if daten == (PROJEKT / "data").resolve():
        print("Abbruch: --data zeigt auf das Live-Verzeichnis data\\ – nur Kopien erlaubt.")
        return 2
    try:
        daten.relative_to((PROJEKT / "diagnose").resolve())
    except ValueError:
        print(f"Abbruch: --data muss unter {PROJEKT / 'diagnose'} liegen (Schutz).")
        return 2
    if not (daten / "angebotstool.db").exists():
        print(f"Abbruch: {daten / 'angebotstool.db'} fehlt – zuerst scripts\\lasttest.py --frisch.")
        return 2
    LATENZ[0] = max(0.0, float(args.latenz))
    umgebung_setzen(daten)

    from app import config
    if Path(config.DB_PFAD).resolve() != (daten / "angebotstool.db").resolve():
        print(f"Abbruch: config.DB_PFAD = {config.DB_PFAD}, erwartet {daten / 'angebotstool.db'}")
        return 2
    from app.db import init_db
    init_db()
    meldungen = []
    if not args.ohne_vorbereitung:
        meldungen = kopie_vorbereiten(args.kalender, not args.ohne_ad_profile)
    global MONDAY_TITEL
    MONDAY_TITEL = _monday_titel()
    patches, gesetzt, fehlend = patches_setzen()

    import uvicorn
    from app.main import app
    print("LASTTEST-SERVER v27")
    print(f"  DATA_ORDNER: {config.DATA_ORDNER}")
    print(f"  Datenbank:   {config.DB_PFAD}")
    print(f"  Pool: {config.DB_POOL_SIZE} + {config.DB_POOL_OVERFLOW} Überlauf, Timeout "
          f"{config.DB_POOL_TIMEOUT} s · Threads {config.WORKER_THREADS}")
    print(f"  Latenz je externem Aufruf: {LATENZ[0]:.1f} s · kalender_sync={args.kalender}")
    print(f"  Mocks ({len(gesetzt)}): " + ", ".join(gesetzt))
    if fehlend:
        print(f"  WARNUNG – nicht gefundene Mock-Ziele ({len(fehlend)}): " + ", ".join(fehlend)
              + " (urlopen-Sicherheitsnetz bleibt aktiv)")
    for m in meldungen:
        print(f"  Vorbereitung: {m}")
    print(f"  Start uvicorn auf http://{args.host}:{args.port} (Lifespan + Scheduler aktiv)")
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level,
                    access_log=True)
    finally:
        for p in patches:
            try:
                p.stop()
            except Exception:
                pass
        print(f"LASTTEST-SERVER beendet · gemockte externe Aufrufe: {ZAEHLER['aufrufe']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
