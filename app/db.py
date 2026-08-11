# Datenbankanbindung (SQLite über SQLAlchemy).
# Die Modelle der einzelnen Phasen registrieren sich an Base; init_db() legt
# beim App-Start alle noch fehlenden Tabellen an.

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app import config

engine = create_engine(
    config.DB_URL,
    connect_args={"check_same_thread": False},  # FastAPI: Zugriff aus mehreren Threads
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Legt Datenordner und alle registrierten Tabellen an (idempotent)."""
    config.DATA_ORDNER.mkdir(parents=True, exist_ok=True)
    config.ANGEBOTE_PDF_ORDNER.mkdir(parents=True, exist_ok=True)
    config.BACKUP_ORDNER.mkdir(parents=True, exist_ok=True)
    # Modelle importieren, damit sie an Base registriert sind, bevor create_all läuft.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _spalten_ergaenzen()
    taegliches_backup()


def taegliches_backup(aufbewahrung_tage: int = 30) -> None:
    """Kopiert die SQLite-DB einmal pro Tag nach data/backups/ (beim App-Start);
    Backups älter als die Aufbewahrungsfrist werden entfernt."""
    import shutil
    from datetime import date, datetime, timedelta

    if not config.DB_PFAD.exists():
        return
    ziel = config.BACKUP_ORDNER / f"angebotstool-{date.today().isoformat()}.db"
    if not ziel.exists():
        shutil.copy2(config.DB_PFAD, ziel)
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
        "ek_cent": "INTEGER",
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
