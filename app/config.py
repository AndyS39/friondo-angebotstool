# Zentrale Konfiguration des Friondo Angebotstools.
# Werte können über die .env-Datei im Projektordner überschrieben werden.

import os
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

# Projektordner = Ordner oberhalb von app/
PROJEKT_ORDNER = Path(__file__).resolve().parent.parent

load_dotenv(PROJEKT_ORDNER / ".env")


def _pfad(env_name: str, standard: Path) -> Path:
    wert = os.getenv(env_name, "").strip()
    return Path(wert) if wert else standard


def _ganzzahl(env_name: str, standard: int) -> int:
    """v27: Zahlenwerte aus der .env (leer/ungültig = Standard)."""
    wert = os.getenv(env_name, "").strip()
    try:
        return int(wert) if wert else standard
    except ValueError:
        return standard


def _schalter(env_name: str) -> bool:
    return os.getenv(env_name, "").strip().lower() in ("1", "ja", "true", "an")


# v27 (PLAN_V17): Versionskennung für /health und die Betriebs-Seite
VERSION = "v27"


# --- Pfade ---------------------------------------------------------------
# Preisliste v2 mit EK-Spalten (führend seit Phase 11)
PREISLISTE_PFAD = _pfad(
    "PREISLISTE_PFAD",
    PROJEKT_ORDNER / "Artikel-Preislisten" / "Angebotserstellung Tool mit EK.xlsx",
)
# v13-PV (PLAN_V13 Phase 75): TAIFUN-Positionslisten der PV-Strecke
PV_PREISLISTEN_ORDNER = _pfad("PV_PREISLISTEN_ORDNER",
                              PROJEKT_ORDNER / "Artikel-Preislisten" / "PV")
# v24 (PLAN_V16 Phase 113): TAIFUN-Positionslisten der Klima-Strecke
KL_PREISLISTEN_ORDNER = _pfad("KL_PREISLISTEN_ORDNER",
                              PROJEKT_ORDNER / "Artikel-Preislisten" / "Klima")
# Seit Phase 35 ist die v5-Logik führend (A13 Anschlussleitung Pos. 103, SLS/ÜSS/APZ entfallen)
LOGIK_EXCEL_PFAD = _pfad("LOGIK_EXCEL_PFAD", PROJEKT_ORDNER / "konfigurator_logik_v5.xlsx")
LOGIK_EXCEL_V2_PFAD = LOGIK_EXCEL_PFAD  # Alias (Phase-11-Import nutzt diesen Namen)
LOGO_ORDNER = _pfad("LOGO_ORDNER", PROJEKT_ORDNER / "Layout - Logo")
DATA_ORDNER = _pfad("DATA_ORDNER", PROJEKT_ORDNER / "data")
ANLAGEN_ORDNER = _pfad("ANLAGEN_ORDNER", PROJEKT_ORDNER / "anlagen")  # Versand-Broschüren

# Logodateien (Ordner "Layout - Logo", Sichtung 08/2026):
#   Logo-01.png = Haupt-Logo: blaue Bildmarke + Schriftzug "Friondo GmbH" (Briefkopf S. 1)
#   Logo-02.png = Badge: nur die blaue Bildmarke (Folgeseiten rechts oben)
LOGO_HAUPT = LOGO_ORDNER / "Logo-01.png"
LOGO_BADGE = LOGO_ORDNER / "Logo-02.png"
REFERENZ_ANGEBOT_PDF = LOGO_ORDNER / "Angebot-Nr. AN250096.pdf"

# Ablageorte (werden beim Start angelegt)
ANGEBOTE_PDF_ORDNER = DATA_ORDNER / "angebote"
SIGNIERT_ORDNER = DATA_ORDNER / "angebote" / "signiert"
BACKUP_ORDNER = DATA_ORDNER / "backups"
# v27 (PLAN_V17 Phase 127/129): Protokolle (zugriff.log, dienst-*.log, smoke-*.txt)
LOG_ORDNER = DATA_ORDNER / "log"

# --- Betrieb (v27, PLAN_V17 Phase 128/129) -------------------------------
# Verbindungspool und Threadpool aus der .env (Standardwerte = Hotfix 06.10.2026);
# Invariante beim Start: Pool gesamt >= Threads + Scheduler + 5 (app.db.pool_invariante)
# Überlauf-Standard 70 (Plan: 40): mit WORKER_THREADS 64 und 12 Scheduler-Läufen
# verlangt die Invariante 64 + 12 + 5 = 81 Verbindungen – 20 + 40 = 60 wären zu wenig.
DB_POOL_SIZE = _ganzzahl("DB_POOL_SIZE", 20)
DB_POOL_OVERFLOW = _ganzzahl("DB_POOL_OVERFLOW", 70)
DB_POOL_TIMEOUT = _ganzzahl("DB_POOL_TIMEOUT", 10)
WORKER_THREADS = _ganzzahl("WORKER_THREADS", 64)
# Reverse-Proxy/HTTPS-Vorbereitung: Cookie secure+samesite=lax bei HTTPS_AKTIV=1;
# absolute Links (Mails, ICS, Signatur) aus BASIS_URL (Standard: bisherige feste Adresse)
HTTPS_AKTIV = _schalter("HTTPS_AKTIV")
BASIS_URL_AUS_ENV = bool(os.getenv("BASIS_URL", "").strip())
BASIS_URL = os.getenv("BASIS_URL", "").strip().rstrip("/") or "http://192.168.35.4:8000"
# Nächtliche Spiegelung der Sicherung (02:30 per Scheduler): Zielordner außerhalb
# des Servers (UNC oder Laufwerk); leer = nur lokale Sicherung, /health meldet warn
BACKUP_ZIEL = os.getenv("BACKUP_ZIEL", "").strip().strip('"')

# E-Signatur Fern-Modus (Phase 23): Token-Link-Route ist vorbereitet, aber
# standardmäßig deaktiviert – Aktivierung erst nach Entscheidung über den
# öffentlichen Zugang (PLAN_V2 Phase 16 Variante B) bzw. einen Signatur-Anbieter.
SIGNATUR_FERN_AKTIV = os.getenv("SIGNATUR_FERN_AKTIV", "").strip().lower() in ("1", "ja", "true")

# --- Datenbank -----------------------------------------------------------
# DB_PFAD_OVERRIDE: nur für migrate.py --db (Testlauf gegen eine Kopie)
DB_PFAD = _pfad("DB_PFAD_OVERRIDE", DATA_ORDNER / "angebotstool.db")
DB_URL = f"sqlite:///{DB_PFAD}"

# --- Fachliche Konstanten ------------------------------------------------
MWST_SATZ = Decimal("0.19")  # 19 % USt.

# Angebotsnummernkreis: AN-C-<JJ><NNNN>, Start AN-C-261000, danach +1;
# bei Jahreswechsel neues JJ und Zähler wieder ab 1000.
NUMMERNKREIS_PREFIX = "AN-C-"
NUMMERNKREIS_START_JJ = 26
NUMMERNKREIS_START_ZAEHLER = 1000

# KfW-Parameter gelten laut Logik-Excel bis zu diesem Datum (danach UI-Warnung).
KFW_GUELTIG_BIS = "2027-01-31"

# --- Sonstiges -----------------------------------------------------------
MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN", "").strip()
SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip()  # leer = auto (data/.session_secret)

# Microsoft Graph (Versand, Phase 17) – Einrichtung: docs/graph-einrichtung.md
GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID", "").strip()
GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID", "").strip()
