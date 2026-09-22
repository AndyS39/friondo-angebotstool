# Datenbankanbindung (SQLite über SQLAlchemy).
# Die Modelle der einzelnen Phasen registrieren sich an Base; init_db() legt
# beim App-Start alle noch fehlenden Tabellen an.

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app import config

engine = create_engine(
    config.DB_URL,
    connect_args={"check_same_thread": False},  # FastAPI: Zugriff aus mehreren Threads
)


@event.listens_for(engine, "connect")
def _sqlite_einstellen(verbindung, _):
    """WAL-Modus: Leser blockieren Schreiber nicht (mehrere gleichzeitige
    Benutzer + Hintergrund-Syncs). Der Modus ist in der DB-Datei persistent,
    das Setzen je Verbindung ist idempotent; busy_timeout überbrückt kurze
    Schreibkonflikte statt sofort 'database is locked' zu werfen."""
    zeiger = verbindung.cursor()
    zeiger.execute("PRAGMA journal_mode=WAL")
    zeiger.execute("PRAGMA synchronous=NORMAL")
    zeiger.execute("PRAGMA busy_timeout=5000")
    zeiger.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Legt Datenordner und alle registrierten Tabellen an (idempotent)."""
    config.DATA_ORDNER.mkdir(parents=True, exist_ok=True)
    config.ANGEBOTE_PDF_ORDNER.mkdir(parents=True, exist_ok=True)
    config.SIGNIERT_ORDNER.mkdir(parents=True, exist_ok=True)
    config.BACKUP_ORDNER.mkdir(parents=True, exist_ok=True)
    # Modelle importieren, damit sie an Base registriert sind, bevor create_all läuft.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _spalten_ergaenzen()
    taegliches_backup()


def taegliches_backup(aufbewahrung_tage: int = 30) -> None:
    """Sichert die SQLite-DB einmal pro Tag nach data/backups/ (beim App-Start);
    Backups älter als die Aufbewahrungsfrist werden entfernt. Seit dem
    WAL-Modus über die SQLite-Backup-API statt Dateikopie: eine reine Kopie
    der .db-Datei würde noch nicht eingespielte Änderungen aus der
    -wal-Datei verlieren."""
    import sqlite3
    from datetime import date, datetime, timedelta

    if not config.DB_PFAD.exists():
        return
    ziel = config.BACKUP_ORDNER / f"angebotstool-{date.today().isoformat()}.db"
    if not ziel.exists():
        quelle = sqlite3.connect(config.DB_PFAD)
        sicherung = sqlite3.connect(ziel)
        try:
            quelle.backup(sicherung)
        finally:
            sicherung.close()
            quelle.close()
    grenze = datetime.now() - timedelta(days=aufbewahrung_tage)
    for alt in config.BACKUP_ORDNER.glob("angebotstool-*.db"):
        if datetime.fromtimestamp(alt.stat().st_mtime) < grenze:
            alt.unlink(missing_ok=True)


# Nachträglich eingeführte Spalten (SQLite: create_all ergänzt keine Spalten).
# Format: Tabelle -> {Spaltenname: SQL-Typdefinition}
_NACHTRAEGLICHE_SPALTEN = {
    "artikel": {
        "artikelnummer": "VARCHAR(50) NOT NULL DEFAULT ''",
        "multi": "FLOAT",
        "ek_cent": "INTEGER",
        "ek_datum": "VARCHAR(20) NOT NULL DEFAULT ''",
    },
    "angebotspositionen": {
        "alternativ": "BOOLEAN NOT NULL DEFAULT 0",     # v10 Kombi-Versand
        "alternativ_zu": "VARCHAR(200) NOT NULL DEFAULT ''",
        "sonderpreis": "BOOLEAN NOT NULL DEFAULT 0",
        "ek_cent": "INTEGER",
        "guid": "VARCHAR(40)",
        "anzeige_nr": "VARCHAR(10) NOT NULL DEFAULT ''",
        "original_preis_cent": "INTEGER",
        "rabatt_prozent": "FLOAT",
        "rabatt_cent": "INTEGER",
        "bauseits": "BOOLEAN NOT NULL DEFAULT 0",
    },
    "angebote": {
        "projekt_gewerk_id": "INTEGER",     # v11 Projektierung
        "vorgang_id": "INTEGER",            # v10 Vorgangsakte
        "extern_pdf_pfad": "VARCHAR(300) NOT NULL DEFAULT ''",   # v10 TAIFUN-PDF
        "extern_pdf_am": "DATETIME",
        "rabatt_cent": "INTEGER",
        "rabatt_prozent": "FLOAT",
        "rabatt_bezeichnung": "VARCHAR(200) NOT NULL DEFAULT ''",
        "signiert_am": "DATETIME",
        "signatur_name": "VARCHAR(200) NOT NULL DEFAULT ''",
        "signatur_protokoll": "TEXT NOT NULL DEFAULT ''",
        "signierte_datei": "VARCHAR(300) NOT NULL DEFAULT ''",
        "signatur_token": "VARCHAR(64)",
        "signatur_token_gueltig_bis": "DATETIME",
        "graph_conversation_id": "VARCHAR(200)",
        "archiviert": "BOOLEAN NOT NULL DEFAULT 0",
        "monday_rueck_status": "VARCHAR(20) NOT NULL DEFAULT ''",
        "monday_rueck_protokoll": "TEXT NOT NULL DEFAULT ''",
        "konfigurator_typ": "VARCHAR(10) NOT NULL DEFAULT 'WP'",
        "vertriebler_id": "INTEGER",
        "foerderung_manuell_cent": "INTEGER",
        "foerderung_ausblenden": "BOOLEAN NOT NULL DEFAULT 0",
        "extern": "BOOLEAN NOT NULL DEFAULT 0",
        "taifun_nummer": "VARCHAR(30) NOT NULL DEFAULT ''",
        "extern_endbetrag_cent": "INTEGER",
        "foerder_grund_prozent": "FLOAT",
        "foerder_klima_prozent": "FLOAT",
        "foerder_einkommen_prozent": "FLOAT",
        "foerder_hoechstkosten_cent": "INTEGER",
        "rechnung_name": "VARCHAR(200) NOT NULL DEFAULT ''",
        "rechnung_strasse": "VARCHAR(200) NOT NULL DEFAULT ''",
        "rechnung_plz": "VARCHAR(10) NOT NULL DEFAULT ''",
        "rechnung_ort": "VARCHAR(100) NOT NULL DEFAULT ''",
        "ablehnungsgrund": "VARCHAR(100) NOT NULL DEFAULT ''",
        "ablehnungsgrund_text": "VARCHAR(500) NOT NULL DEFAULT ''",
        "vermerke_json": "TEXT NOT NULL DEFAULT '[]'",
        "vorgaenger_id": "INTEGER",
        "profil_id": "INTEGER",
        "vortext_text": "TEXT NOT NULL DEFAULT ''",
        "verfolgung_ampel": "VARCHAR(10) NOT NULL DEFAULT ''",
        "wiedervorlage_am": "DATETIME",
        "versendet_am": "DATETIME",
        "angenommen_am": "DATETIME",
        "abgelehnt_am": "DATETIME",
    },
    "benutzer": {
        "email": "VARCHAR(200) NOT NULL DEFAULT ''",
        "rollen": "VARCHAR(100) NOT NULL DEFAULT ''",           # v11 Mehrfachrollen
        "kalkulation_sichtbar": "BOOLEAN NOT NULL DEFAULT 0",   # v11
        "benachrichtigung_mail": "VARCHAR(10) NOT NULL DEFAULT 'aus'",  # v11
        "telefon": "VARCHAR(50) NOT NULL DEFAULT ''",           # v11 Phase 70
        "lm_aktiv": "BOOLEAN NOT NULL DEFAULT 0",               # v12 Lead-Management
        "lm_arbeitszeit": "VARCHAR(20)",                        # v12
    },
    # v12 (Lead-Management, Phase 73): Lead-Kopf am Vorgang – alle nullable
    "vorgaenge": {
        "lead_phase": "VARCHAR(20)",
        "quelle_id": "INTEGER",
        "kampagne_id": "INTEGER",
        "utm_source": "VARCHAR(200)",
        "utm_medium": "VARCHAR(200)",
        "utm_campaign": "VARCHAR(200)",
        "utm_content": "VARCHAR(200)",
        "eingang_am": "DATETIME",
        "eingang_art": "VARCHAR(10)",
        "anfrage_text": "TEXT",
        "anfrage_rohdaten": "TEXT",
        "erstkontakt_am": "DATETIME",
        "erreicht_am": "DATETIME",
        "terminiert_am": "DATETIME",
        "leadmanager_id": "INTEGER",
        "score_punkte": "INTEGER",
        "score_klasse": "VARCHAR(1)",
        "wunschzeiten": "VARCHAR(300)",
        "lat": "FLOAT",
        "lon": "FLOAT",
        "geocode_status": "VARCHAR(10)",
        "einwilligung_werbung": "BOOLEAN",
        "einwilligung_werbung_am": "DATETIME",
        "einwilligung_quelle": "VARCHAR(20)",
        "zurueckgestellt_bis": "DATETIME",
        "zurueckgestellt_grund": "VARCHAR(200)",
        "unqualifiziert_grund": "VARCHAR(200)",
        "unqualifiziert_text": "VARCHAR(500)",
        "versuch_nr": "INTEGER NOT NULL DEFAULT 0",
        "naechste_aktion_am": "DATETIME",
        "loeschen_am": "DATETIME",
        "demo": "BOOLEAN NOT NULL DEFAULT 0",
    },
    "kunden": {
        "interesse": "VARCHAR(50) NOT NULL DEFAULT ''",
        "kanal_manuell": "BOOLEAN NOT NULL DEFAULT 0",
        "vertriebskanal": "VARCHAR(100) NOT NULL DEFAULT ''",
    },
    "leads": {
        "interesse": "VARCHAR(50) NOT NULL DEFAULT ''",
        "ausgeblendet": "BOOLEAN NOT NULL DEFAULT 0",
        "ausgeblendet_grund": "VARCHAR(300) NOT NULL DEFAULT ''",
        "ausgeblendet_am": "DATETIME",
        "benutzer_manuell": "BOOLEAN NOT NULL DEFAULT 0",
        "vertriebskanal": "VARCHAR(100) NOT NULL DEFAULT ''",
        "ausgeblendet_sparten": "VARCHAR(50) NOT NULL DEFAULT ''",
        "kanal_manuell": "BOOLEAN NOT NULL DEFAULT 0",
        "angelegt_am": "DATETIME",
    },
    "erfassungen": {
        "vorbelegt_json": "TEXT",   # v12 Phase 76: aus Qualifizierung
        "vorgang_id": "INTEGER",            # v10 Vorgangsakte
        "konfigurator_typ": "VARCHAR(10) NOT NULL DEFAULT 'WP'",
        "archiviert": "BOOLEAN NOT NULL DEFAULT 0",
        "typ": "VARCHAR(10) NOT NULL DEFAULT 'katalog'",
        "freitext": "TEXT NOT NULL DEFAULT ''",
        "sparte": "VARCHAR(4) NOT NULL DEFAULT 'WP'",
        "lead_id": "INTEGER",
    },
    "monday_quellen": {
        "rueck_modus": "VARCHAR(10) NOT NULL DEFAULT 'aus'",
        "rueck_status_spalte": "VARCHAR(100) NOT NULL DEFAULT ''",
        "rueck_status_wert": "VARCHAR(100) NOT NULL DEFAULT 'Angebot versendet'",
        "rueck_gruppe_id": "VARCHAR(100) NOT NULL DEFAULT ''",
        "rueck_wert_spalte": "VARCHAR(100) NOT NULL DEFAULT ''",
        "rueck_wert_basis": "VARCHAR(10) NOT NULL DEFAULT 'brutto'",
    },
}


def _spalten_ergaenzen() -> None:
    """Leichte Migration: fehlende Spalten per ALTER TABLE ergänzen (idempotent)."""
    from sqlalchemy import text

    with engine.begin() as verbindung:
        for tabelle, spalten in _NACHTRAEGLICHE_SPALTEN.items():
            vorhanden = {zeile[1] for zeile in
                         verbindung.execute(text(f"PRAGMA table_info({tabelle})"))}
            for name, typdef in spalten.items():
                if name not in vorhanden:
                    verbindung.execute(
                        text(f"ALTER TABLE {tabelle} ADD COLUMN {name} {typdef}"))


def get_session():
    """FastAPI-Dependency: liefert eine Session und schließt sie nach dem Request."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
