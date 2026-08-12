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


# --- Pfade ---------------------------------------------------------------
# Preisliste v2 mit EK-Spalten (führend seit Phase 11)
PREISLISTE_PFAD = _pfad(
    "PREISLISTE_PFAD",
    PROJEKT_ORDNER / "Artikel-Preislisten" / "Angebotserstellung Tool mit EK.xlsx",
)
# Seit Phase 20 ist die v3-Logik führend (Dachzentrale, OR-Bedingungen, Rabatt-Summenblock)
LOGIK_EXCEL_PFAD = _pfad("LOGIK_EXCEL_PFAD", PROJEKT_ORDNER / "konfigurator_logik_v3.xlsx")
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
BACKUP_ORDNER = DATA_ORDNER / "backups"

# --- Datenbank -----------------------------------------------------------
DB_PFAD = DATA_ORDNER / "angebotstool.db"
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
