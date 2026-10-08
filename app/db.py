# Datenbankanbindung (SQLite über SQLAlchemy).
# Die Modelle der einzelnen Phasen registrieren sich an Base; init_db() legt
# beim App-Start alle noch fehlenden Tabellen an.

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app import config

# Hotfix 06.10.2026 (Verbindungspool): auf dem Server trat
# „QueuePool limit of size 5 overflow 10 reached, connection timed out,
# timeout 30.00“ auf – Verbindungen wurden während Netz-I/O gehalten und die
# RollenMiddleware hielt je Anfrage eine zweite. Größerer Pool, kurzer Timeout
# (Anfragen scheitern nach 10 s mit klarer Meldung statt 30 s zu hängen) und die
# Regel „keine offene Sitzung während Netz-I/O“ (verbindung_freigeben unten).
# v27 (PLAN_V17 Phase 128): Werte aus der .env (DB_POOL_SIZE, DB_POOL_OVERFLOW,
# DB_POOL_TIMEOUT), Standard wie im Hotfix.
POOL_SIZE = config.DB_POOL_SIZE
MAX_OVERFLOW = config.DB_POOL_OVERFLOW
POOL_TIMEOUT = config.DB_POOL_TIMEOUT

engine = create_engine(
    config.DB_URL,
    connect_args={"check_same_thread": False},  # FastAPI: Zugriff aus mehreren Threads
    pool_size=POOL_SIZE, max_overflow=MAX_OVERFLOW, pool_timeout=POOL_TIMEOUT,
)


def pool_status() -> str:
    """Belegung des Verbindungspools, z. B. „Pool size: 20  Connections in
    pool: 3 Current Overflow: -17 Current Checked out connections: 2“ – für
    Fehlerprotokoll und Parametrierung → Fehlerprotokoll."""
    try:
        return engine.pool.status()
    except Exception as fehler:   # Pool ohne status() (z. B. StaticPool)
        return f"Pool-Status nicht verfügbar ({type(fehler).__name__})"


def pool_kennzahlen() -> dict:
    """v27: Pool-Belegung als Zahlen für /health und die Betriebs-Seite."""
    try:
        pool = engine.pool
        belegt = int(pool.checkedout())
        ueberlauf = max(0, int(pool.overflow()))
    except Exception:
        belegt, ueberlauf = 0, 0
    maximum = POOL_SIZE + MAX_OVERFLOW
    return {"size": POOL_SIZE, "checked_out": belegt, "overflow": ueberlauf,
            "maximum": maximum, "timeout_s": POOL_TIMEOUT,
            "prozent": round(100.0 * belegt / maximum, 1) if maximum else 0.0}


def pool_invariante(anzahl_scheduler: int) -> tuple[bool, str]:
    """v27 (Phase 128): beim Start geprüft und protokolliert – der Pool muss
    alle Worker-Threads, alle Scheduler-Läufe und 5 Reserve-Verbindungen
    gleichzeitig bedienen können."""
    gesamt = POOL_SIZE + MAX_OVERFLOW
    noetig = config.WORKER_THREADS + int(anzahl_scheduler) + 5
    ok = gesamt >= noetig
    return ok, (f"Pool {gesamt} (= {POOL_SIZE} + {MAX_OVERFLOW} Überlauf) "
                f"{'≥' if ok else '<'} Threads {config.WORKER_THREADS} + "
                f"Scheduler {anzahl_scheduler} + 5 = {noetig}")


@contextmanager
def kurz():
    """v27 (PLAN_V17 Phase 128) – kurze Sitzung für Scheduler und Hilfsfunktionen:
    ``with db.kurz() as s:`` committet bei Erfolg, rollt bei einer Ausnahme
    zurück und schließt immer. Muster für Hintergrundläufe: lesen → Sitzung
    schließen → Netzaufruf → neue kurze Sitzung zum Zurückschreiben. Anfragen
    behalten die Dependency get_session."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def wal_groesse_mb() -> float:
    """Größe der SQLite-WAL-Datei (angebotstool.db-wal) in MB – 0, wenn keine da."""
    try:
        pfad = Path(str(config.DB_PFAD) + "-wal")
        return round(pfad.stat().st_size / 1_000_000, 2) if pfad.exists() else 0.0
    except OSError:
        return 0.0


def wal_pflege() -> dict:
    """v27 (Phase 128) SQLite-Pflege, nächtlich 02:40 per Scheduler:
    ``PRAGMA wal_checkpoint(TRUNCATE)`` (WAL in die Datei einspielen und auf 0
    kürzen) und ``PRAGMA optimize`` (Statistiken für den Abfrageplaner).
    Liefert busy/log/checkpointed des Checkpoints und die WAL-Größe danach."""
    vorher = wal_groesse_mb()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as v:
        zeile = v.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        v.exec_driver_sql("PRAGMA optimize")
    busy, log_seiten, eingespielt = (zeile or (None, None, None))[:3]
    return {"busy": busy, "wal_seiten": log_seiten, "eingespielt": eingespielt,
            "wal_mb_vorher": vorher, "wal_mb_nachher": wal_groesse_mb()}


def verbindung_freigeben(session) -> None:
    """Hotfix 06.10.2026 – Regel „keine offene Sitzung während Netz-I/O“:
    unmittelbar VOR einem Netzaufruf (Graph/msal, Routing, Geocoding,
    Heizreport, monday) aufrufen, nachdem alle benötigten Daten gelesen sind.
    Der commit beendet die laufende Transaktion und gibt die Pool-Verbindung
    frei; die Session bleibt nutzbar (expire_on_commit=False → geladene Objekte
    behalten ihre Werte), die nächste Abfrage holt sich wieder eine
    Verbindung. Bereits vorgenommene Änderungen werden dabei gespeichert –
    deshalb erst nach dem Lesen, nie mitten in einer halb fertigen Änderung
    aufrufen. Hintergrundläufe mit eigener Session schließen sie stattdessen
    (session.close()) und öffnen fürs Zurückschreiben eine neue."""
    if session is None:
        return
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise


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

    config.LOG_ORDNER.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _spalten_ergaenzen()
    indizes_anlegen()
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
    "teams": {
        "leiter_id": "INTEGER",                                 # v15 Phase 75
        "farbe": "VARCHAR(20) NOT NULL DEFAULT ''",             # v15 Phase 75
        "outlook_adresse": "VARCHAR(200) NOT NULL DEFAULT ''",  # v15 Phase 75
    },
    "projekt_termine": {
        "outlook_fehler": "VARCHAR(300) NOT NULL DEFAULT ''", # v15 Phase 81
        "graph_conversation_id": "VARCHAR(200)",              # v15 Phase 81
        "kunden_antwort_am": "DATETIME",                      # v15 Phase 81
        "dauer_tage": "INTEGER",                                # v15 Phase 75
        "ganztaegig": "BOOLEAN NOT NULL DEFAULT 1",             # v15 Phase 75
        "outlook_event_id": "VARCHAR(200) NOT NULL DEFAULT ''", # v15 Phase 75
        "bestaetigt_am": "DATETIME",                            # v15 Phase 75
        "bestaetigt_quelle": "VARCHAR(20) NOT NULL DEFAULT ''", # v15 Phase 75
        "zweck": "VARCHAR(10) NOT NULL DEFAULT ''",            # v28 Phase 135
    },
    "projekt_subs": {
        "graph_conversation_id": "VARCHAR(200)",               # v15 Phase 79
        "angefragt_am": "DATETIME",                            # v15 Phase 79
        "antwort_am": "DATETIME",                              # v15 Phase 79
    },
    "galerie_dateien": {
        "sparte": "VARCHAR(5) NOT NULL DEFAULT 'WP'",          # 27.09.2026
    },
    "aufgaben": {
        "aktion_typ": "VARCHAR(20) NOT NULL DEFAULT ''",       # v15 Phase 78
        "aktion_wert": "VARCHAR(300) NOT NULL DEFAULT ''",     # v15 Phase 78
        "optionen": "VARCHAR(300) NOT NULL DEFAULT ''",        # v15 Phase 78
        "auswahl": "VARCHAR(100) NOT NULL DEFAULT ''",         # v15 Phase 78
        "sichtbar_wenn": "VARCHAR(100) NOT NULL DEFAULT ''",   # V4 Phase 91.2
        "entfaellt_grund": "VARCHAR(300) NOT NULL DEFAULT ''",   # v28 Phase 133
    },
    "aufgabenpaket_instanzen": {
        "version": "VARCHAR(5) NOT NULL DEFAULT 'v2'",         # v15 Phase 78
    },
    "gewerke": {
        "auftragsdaten_am": "DATETIME",                        # V3 Phase 84
        "bestand_import_id": "INTEGER",                        # V3 Phase 85
        "bza_id": "VARCHAR(100)",                              # V4 Phase 92
        "bza_erstellt_am": "DATETIME",
        "bza_gesendet_am": "DATETIME",
        "bza_datei_id": "INTEGER",
        "kfw_antragsnummer": "VARCHAR(60)",
        "kfw_zusage_am": "DATETIME",
        "heizreport_projekt_key": "VARCHAR(60)",               # V4 Phase 93.1
        "heizlast_quelle": "VARCHAR(60)",                      # V4 Phase 93.1
        "heizreport_angelegt_am": "DATETIME",                  # v26 Phase 122
        "heizreport_pdf_am": "DATETIME",                       # v26 Phase 122
        "fp_antworten_json": "TEXT NOT NULL DEFAULT '{}'",     # v15 Phase 80
        "fp_vorbelegt_json": "TEXT NOT NULL DEFAULT '{}'",     # v15 Phase 80
        "fp_seite_index": "INTEGER NOT NULL DEFAULT 0",        # v15 Phase 80
        "fp_abgeschlossen_am": "DATETIME",                     # v15 Phase 80
        "zaehlerwechsel_termin": "DATETIME",                   # v15 Phase 78
        "feinplanung_erfasst": "BOOLEAN NOT NULL DEFAULT 0",   # v15 Phase 74
        "feinplanung_erfasst_am": "DATETIME",                  # v15 Phase 74
        "wp_team_id": "INTEGER",                               # v15 Phase 75
        "elektro_team_id": "INTEGER",                          # v15 Phase 75
        "sub_team_id": "INTEGER",                              # v15 Phase 75
    },
    "artikel": {
        "lieferant_artnr": "VARCHAR(50) NOT NULL DEFAULT ''",  # v15 Phase 80
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
        "ust_satz": "FLOAT NOT NULL DEFAULT 19",                 # v13-PV Phase 75
        "pv_json": "TEXT NOT NULL DEFAULT ''",                   # v13-PV Phase 76/78
        "kl_json": "TEXT NOT NULL DEFAULT ''",                   # v24 Phase 114 (Klima)
        "liefer_anschrift": "VARCHAR(300) NOT NULL DEFAULT ''",   # v11 Phase 66
        "kopie_von": "VARCHAR(30) NOT NULL DEFAULT ''",           # v11 Phase 66
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
        "wirtschaftlichkeit_ausblenden": "BOOLEAN NOT NULL DEFAULT 0",   # v22 Phase 102
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
        "kfw_gefoerdert": "VARCHAR(10) NOT NULL DEFAULT ''",   # V3 Phase 84
        "bestand": "BOOLEAN NOT NULL DEFAULT 0",                # V3 Phase 85
        # v20 (Phase 98): strukturierte Anschriften
        "rechnung_zusatz": "VARCHAR(200) NOT NULL DEFAULT ''",
        "liefer_name": "VARCHAR(200) NOT NULL DEFAULT ''",
        "liefer_zusatz": "VARCHAR(200) NOT NULL DEFAULT ''",
        "liefer_strasse": "VARCHAR(200) NOT NULL DEFAULT ''",
        "liefer_plz": "VARCHAR(10) NOT NULL DEFAULT ''",
        "liefer_ort": "VARCHAR(100) NOT NULL DEFAULT ''",
    },
    # v21 (PLAN_LEAD_V1.1 Phase 87): Auto-Anlage aus dem Eingang
    "lead_quellen": {"auto_angelegt": "BOOLEAN NOT NULL DEFAULT 0"},
    # v23 (Lead-Management V2, Phase 104)
    "vot_termine": {
        "typ": "VARCHAR(10) NOT NULL DEFAULT 'vot'",
        "medium": "VARCHAR(10) NOT NULL DEFAULT 'vor_ort'",
        "ics_uid": "VARCHAR(100)",
        "ics_sequence": "INTEGER NOT NULL DEFAULT 0",
    },
    "ad_profile": {
        "terminiert_selbst": "BOOLEAN NOT NULL DEFAULT 0",
        "kompetenz_sparten": "VARCHAR(100) NOT NULL DEFAULT '[]'",
        "kompetenz_kombi": "BOOLEAN NOT NULL DEFAULT 0",
        "kompetenz_mfh": "BOOLEAN NOT NULL DEFAULT 0",
        "kompetenz_gewerbe": "BOOLEAN NOT NULL DEFAULT 0",
    },
    "lead_aktivitaeten": {
        "call_id": "VARCHAR(100)",
        "richtung": "VARCHAR(5)",
        "nebenstelle": "VARCHAR(20)",
    },
    "kampagnen": {"auto_angelegt": "BOOLEAN NOT NULL DEFAULT 0"},
    # V3 (Phase 84): Herkunft der Steckbrief-Werte
    "steckbrief_werte": {
        "quelle": "VARCHAR(20) NOT NULL DEFAULT ''",
    },
    "benutzer": {
        # v27 (PLAN_V17 Phase 130): Login-Härtung – nur additiv, v26 liest weiter
        # pin_hash (Rollback-Sicherheit, Phase 132)
        "pin_hash_v2": "VARCHAR(200)",
        "fehlversuche": "INTEGER NOT NULL DEFAULT 0",
        "gesperrt_bis": "DATETIME",
        "pin_wechsel_noetig": "BOOLEAN NOT NULL DEFAULT 0",
        "sitzungszaehler": "INTEGER NOT NULL DEFAULT 0",
        "letzter_login": "DATETIME",
        # v29 (PLAN_LEAD_V4): Vorname, Infotext, Bild des Vertrieblers
        "vorname": "VARCHAR(100) NOT NULL DEFAULT ''",
        "infotext": "TEXT NOT NULL DEFAULT ''",
        "bild_datei": "VARCHAR(300) NOT NULL DEFAULT ''",
        "buchungslink": "VARCHAR(500)",                         # v23 Phase 104
        "nebenstelle": "VARCHAR(20)",                           # v23 Phase 104
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
        "ad_id": "INTEGER",                                     # v23 Phase 104
        "vorab_angebot": "BOOLEAN NOT NULL DEFAULT 0",          # v23 Phase 104
        "veranstaltung_id": "INTEGER",                          # v23 Phase 104
        "teilgenommen": "BOOLEAN",                              # v23 Phase 104
        # v29 (PLAN_LEAD_V4 Phase 142): Bounce / Mail nicht gesendet
        "email_status": "VARCHAR(10)",
        "email_status_am": "DATETIME",
        "email_status_grund": "VARCHAR(300) NOT NULL DEFAULT ''",
        "mail_fehler": "BOOLEAN NOT NULL DEFAULT 0",
        "mail_fehler_am": "DATETIME",
        "mail_fehler_vorlage": "VARCHAR(50) NOT NULL DEFAULT ''",
        "mail_fehler_text": "VARCHAR(500) NOT NULL DEFAULT ''",
    },
    "kunden": {
        "objektart": "VARCHAR(10)",                             # v23 Phase 104
        "parteien": "INTEGER",                                  # v23 Phase 104
        # v20 (Phase 98): Standard-Anschriften
        "rechnung_name": "VARCHAR(200) NOT NULL DEFAULT ''",
        "rechnung_zusatz": "VARCHAR(200) NOT NULL DEFAULT ''",
        "rechnung_strasse": "VARCHAR(200) NOT NULL DEFAULT ''",
        "rechnung_plz": "VARCHAR(10) NOT NULL DEFAULT ''",
        "rechnung_ort": "VARCHAR(100) NOT NULL DEFAULT ''",
        "liefer_name": "VARCHAR(200) NOT NULL DEFAULT ''",
        "liefer_zusatz": "VARCHAR(200) NOT NULL DEFAULT ''",
        "liefer_strasse": "VARCHAR(200) NOT NULL DEFAULT ''",
        "liefer_plz": "VARCHAR(10) NOT NULL DEFAULT ''",
        "liefer_ort": "VARCHAR(100) NOT NULL DEFAULT ''",
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
    # v29 (PLAN_LEAD_V4 Phase 142): Absender und Versuchszähler der Lead-Mail-Warteschlange
    "kommunikation_log": {
        "absender": "VARCHAR(200) NOT NULL DEFAULT ''",
        "versuche": "INTEGER NOT NULL DEFAULT 0",
    },
    # v27 (Phase 128): Geocoding-Backoff für Adressen mit Status „fehler“
    "geocode_cache": {"versuche": "INTEGER NOT NULL DEFAULT 0"},
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


# v27 (PLAN_V17 Phase 128): Indizes der häufigsten Abfragen (Indexprüfung mit
# EXPLAIN QUERY PLAN, scripts/index_pruefung.py). Format: (Indexname, Tabelle,
# Spaltenliste); CREATE INDEX IF NOT EXISTS ist idempotent und nur additiv –
# v26 läuft auf einer Datenbank mit diesen Indizes unverändert.
_INDIZES = [
    ("ix_v27_vorgaenge_lead_phase", "vorgaenge", "lead_phase"),
    ("ix_v27_angebote_status", "angebote", "status"),
    ("ix_v27_angebote_archiviert_status", "angebote", "archiviert, status"),
    ("ix_v27_erfassungen_status", "erfassungen", "status"),
    ("ix_v27_erfassungen_archiviert", "erfassungen", "archiviert"),
    ("ix_v27_erfassungen_angebot_id", "erfassungen", "angebot_id"),
    ("ix_v27_lead_aktivitaeten_vorgang_zeit", "lead_aktivitaeten", "vorgang_id, erstellt_am"),
    ("ix_v27_benachrichtigungen_benutzer_gelesen", "benachrichtigungen", "benutzer_id, gelesen_am"),
    ("ix_v27_vot_termine_beginn", "vot_termine", "beginn"),
    ("ix_v27_vot_termine_status_typ", "vot_termine", "status, typ"),
    ("ix_v27_vorgaenge_wiedervorlage", "vorgaenge", "wiedervorlage_am"),
    ("ix_v27_vorgaenge_naechste_aktion", "vorgaenge", "naechste_aktion_am"),
    ("ix_v27_leads_benutzer", "leads", "benutzer_id"),
    ("ix_v27_leads_vot_datum", "leads", "vot_datum"),
    ("ix_v27_aufgaben_status", "aufgaben", "status"),
    ("ix_v27_aufgaben_verantwortlich_status", "aufgaben", "verantwortlich_id, status"),
    ("ix_v27_login_protokoll_benutzer_zeit", "login_protokoll", "benutzer_id, zeit"),
]


def vorhandene_indizes() -> set[str]:
    from sqlalchemy import text
    with engine.connect() as v:
        return {z[0] for z in v.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index'"))}


def indizes_anlegen() -> list[str]:
    """Fehlende Indizes anlegen (idempotent); liefert die neu angelegten
    Indizes (für migrate.py und die Gesamtübersicht). Zwei Quellen:
    (1) die im Modell deklarierten Indizes (`index=True`) – für Spalten, die
    nachträglich per ALTER TABLE kamen (z. B. erfassungen.vorgang_id,
    angebote.vorgang_id), hat create_all sie nie angelegt (Befund der
    Indexprüfung v27: volle Scans in Vorgangsakte und Kundenkartei);
    (2) die Liste _INDIZES aus der Indexprüfung (EXPLAIN QUERY PLAN)."""
    from sqlalchemy import text
    vorher = vorhandene_indizes()
    neu = []
    with engine.begin() as v:
        tabellen = {z[0] for z in v.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table'"))}
        for tabelle in Base.metadata.sorted_tables:
            if tabelle.name not in tabellen:
                continue
            for index in tabelle.indexes:
                if index.name in vorher:
                    continue
                index.create(v, checkfirst=True)
                neu.append(f"{index.name} ON {tabelle.name} "
                           f"({', '.join(s.name for s in index.columns)})")
        for name, tabelle, spalten in _INDIZES:
            if tabelle not in tabellen or name in vorher:
                continue
            vorhanden = {z[1] for z in v.execute(text(f"PRAGMA table_info({tabelle})"))}
            if not all(s.strip() in vorhanden for s in spalten.split(",")):
                continue
            v.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {tabelle} ({spalten})"))
            neu.append(f"{name} ON {tabelle} ({spalten})")
    return neu


def get_session():
    """FastAPI-Dependency: liefert eine Session und schließt sie nach dem Request."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
