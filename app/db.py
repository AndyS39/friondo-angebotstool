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
    # (Ab Phase 1 kommen hier die Modell-Module hinzu, z. B. from app import models)
    Base.metadata.create_all(bind=engine)


def get_session():
    """FastAPI-Dependency: liefert eine Session und schließt sie nach dem Request."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
