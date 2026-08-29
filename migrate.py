# Datenbank-Migration (v5): sammelt alle Schema- und Datenänderungen an
# einer Stelle. Idempotent – mehrfaches Ausführen richtet keinen Schaden an.
# Wird von update.bat nach jedem git pull ausgeführt; beim App-Start läuft
# der Schema-Teil (init_db) zusätzlich, damit auch ein manueller Start ohne
# update.bat eine passende Datenbank vorfindet.
#
# Aufruf:  venv\Scripts\python migrate.py            (echte DB laut config)
#          venv\Scripts\python migrate.py --db PFAD  (z. B. Kopie zum Testen)

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _schema() -> list[str]:
    """Tabellen anlegen + nachträgliche Spalten ergänzen (siehe app.db)."""
    from app import db
    from sqlalchemy import text

    vorher = {}
    with db.engine.begin() as v:
        for tabelle in db._NACHTRAEGLICHE_SPALTEN:
            vorher[tabelle] = {z[1] for z in
                               v.execute(text(f"PRAGMA table_info({tabelle})"))}
    db.init_db()
    meldungen = []
    with db.engine.begin() as v:
        for tabelle, spalten in db._NACHTRAEGLICHE_SPALTEN.items():
            jetzt = {z[1] for z in v.execute(text(f"PRAGMA table_info({tabelle})"))}
            for name in spalten:
                if name in jetzt and name not in vorher.get(tabelle, set()):
                    meldungen.append(f"Spalte ergänzt: {tabelle}.{name}")
    return meldungen


def _daten() -> list[str]:
    """Datenmigrationen – jede prüft selbst, ob sie schon gelaufen ist."""
    from app.db import SessionLocal
    from app.models import einstellung_holen, einstellung_setzen

    meldungen = []
    session = SessionLocal()
    try:
        # Phase 30: bisheriger fester Mailtext wird zur Standard-Vorlage
        if einstellung_holen(session, "mail_vorlage_standard_betreff", "") == "":
            from app import mail_vorlagen
            einstellung_setzen(session, "mail_vorlage_standard_betreff",
                               mail_vorlagen.STANDARD_BETREFF)
            einstellung_setzen(session, "mail_vorlage_standard_text",
                               mail_vorlagen.STANDARD_TEXT)
            meldungen.append("Standard-E-Mail-Vorlage angelegt")
        # Phase 31: BCC-Vorbelegung
        if einstellung_holen(session, "mail_bcc", "") == "":
            einstellung_setzen(session, "mail_bcc", "info@friondo.de")
            meldungen.append("BCC-Adresse vorbelegt (info@friondo.de)")
        # v6 (Phase 37): Bestandsleads ohne Vertriebler erneut zuordnen –
        # Personen-Zuordnungen griffen bisher erst beim nächsten Sync-Lauf;
        # zusätzlich Matching über die Benutzer-E-Mail. Idempotent: fasst nur
        # Leads ohne benutzer_id und ohne manuelle Zuordnung an.
        from app import monday_sync
        from app.models import Lead
        nachgezogen = 0
        for lead in (session.query(Lead)
                     .filter(Lead.benutzer_id.is_(None),
                             Lead.benutzer_manuell.is_(False))):
            neu_id = monday_sync._benutzer_fuer_person(session, lead.monday_person)
            if neu_id:
                lead.benutzer_id = neu_id
                nachgezogen += 1
        if nachgezogen:
            meldungen.append(f"{nachgezogen} Bestandsleads dem Vertriebler zugeordnet")
        # v6 (Phase 41): Statistik-Zeitstempel für Bestandsdaten (Näherung:
        # Angebotsdatum als Statuszeitpunkt; Lead-Anlage = aktualisiert_am)
        from app.models import Angebot
        gestempelt = 0
        for a in session.query(Angebot).filter(Angebot.status.in_(
                ["Versendet", "Angenommen", "Abgelehnt"])):
            if a.versendet_am is None:
                a.versendet_am = a.datum; gestempelt += 1
            if a.status == "Angenommen" and a.angenommen_am is None:
                a.angenommen_am = a.signiert_am or a.datum
            if a.status == "Abgelehnt" and a.abgelehnt_am is None:
                a.abgelehnt_am = a.datum
        if gestempelt:
            meldungen.append(f"{gestempelt} Bestandsangebote mit Status-Zeitpunkt (Näherung: Angebotsdatum)")
        leads_ohne = 0
        for lead in session.query(Lead).filter(Lead.angelegt_am.is_(None)):
            lead.angelegt_am = lead.aktualisiert_am
            leads_ohne += 1
        if leads_ohne:
            meldungen.append(f"{leads_ohne} Bestandsleads mit Anlagedatum (Näherung: aktualisiert_am)")
        # v7 (Phase 45): Bestandsdaten reaktivieren – alle in v6 als
        # „Individuell“ markierten (auto-archivierten) Erfassungen werden zur
        # sichtbaren Arbeitsliste „In TAIFUN zu schreiben“ und entarchiviert.
        # Idempotent: nach dem ersten Lauf existiert der Status nicht mehr.
        from datetime import datetime as _dt

        from app.models import Erfassung
        reaktiviert = 0
        for e in session.query(Erfassung).filter(Erfassung.status == "Individuell"):
            e.status = "In TAIFUN zu schreiben"
            e.archiviert = False
            e.aenderungs_protokoll = (
                (e.aenderungs_protokoll + "\n" if e.aenderungs_protokoll else "")
                + f"{_dt.now().strftime('%d.%m.%Y %H:%M')} · Migration v7: aus "
                  "„Individuell“ (Archiv) reaktiviert – in TAIFUN zu schreiben")
            reaktiviert += 1
        if reaktiviert:
            meldungen.append(f"{reaktiviert} Individuell-Erfassungen reaktiviert "
                             "(jetzt „In TAIFUN zu schreiben“, entarchiviert)")
        # ---------------- v8 (Phasen 47–52) ----------------
        # Schema-Nachzüge laufen wie immer über db._NACHTRAEGLICHE_SPALTEN.
        # Hinweis Förderung: der v6-Gesamt-Override (foerderung_manuell_cent)
        # bleibt bestehen und wird weiter als Gesamtwert angezeigt; die neuen
        # Baustein-Overrides ersetzen nur das Eingabefeld im Editor.
        # v8 (Phase 49): Erfassungen rückwirkend mit ihrem Lead verknüpfen
        # (Multi-Sparten braucht die n:1-Verknüpfung Erfassung → Lead)
        verknuepft = 0
        for lead in session.query(Lead).filter(Lead.erfassung_id.isnot(None)):
            e = session.get(Erfassung, lead.erfassung_id)
            if e is not None and e.lead_id is None:
                e.lead_id = lead.id
                verknuepft += 1
        if verknuepft:
            meldungen.append(f"{verknuepft} Erfassungen mit ihrem Lead verknüpft (Multi-Sparten)")
        # v8 (Phase 49): Tab-Fix – in v7 automatisch archivierte
        # „Erledigt (extern)“-Fälle einmalig zurückholen (Archiv nur manuell);
        # der Einstellungs-Schalter verhindert, dass später manuell
        # archivierte Fälle bei erneuten Läufen wieder auftauchen.
        if einstellung_holen(session, "migration_v8_extern_archiv", "") != "erledigt":
            zurueck = 0
            for e in session.query(Erfassung).filter(
                    Erfassung.status == "Erledigt (extern)",
                    Erfassung.archiviert.is_(True)):
                e.archiviert = False
                zurueck += 1
            einstellung_setzen(session, "migration_v8_extern_archiv", "erledigt")
            if zurueck:
                meldungen.append(f"{zurueck} Erledigt-(extern)-Erfassungen aus dem "
                                 "Archiv in den Reiter „Erledigt“ zurückgeholt")
        # v8 (Phase 51): Startwerte der Ablehnungsgründe (nur wenn Tabelle leer)
        from app.models import ABLEHNUNGSGRUND_STARTWERTE, AblehnungsGrund
        if session.query(AblehnungsGrund).count() == 0:
            for sort, name in enumerate(ABLEHNUNGSGRUND_STARTWERTE):
                session.add(AblehnungsGrund(name=name, sort=sort))
            meldungen.append(f"{len(ABLEHNUNGSGRUND_STARTWERTE)} Ablehnungsgründe vorbelegt")
        # ---------------- v9 (Phasen 53–58) ----------------
        # Phase 53: Textblöcke (Nach-/Vortexte) + Angebotsprofile anlegen;
        # Pos.-162-Text auf den Enni-Wortlaut aktualisieren (Preis bleibt)
        from app import angebotsprofile
        meldungen += angebotsprofile.seed(session)
        from app.models import Artikel
        artikel_162 = (session.query(Artikel)
                       .filter(Artikel.pos_nr == "162", Artikel.aktiv.is_(True)).first())
        if (artikel_162 is not None
                and artikel_162.bezeichnung != angebotsprofile.POS_162_BEZEICHNUNG):
            artikel_162.bezeichnung = angebotsprofile.POS_162_BEZEICHNUNG
            artikel_162.beschreibung = angebotsprofile.POS_162_TEXT
            meldungen.append("Pos.-162-Text auf enni.flexstrom-Wortlaut aktualisiert "
                             f"(Preis unverändert: {artikel_162.e_preis_cent / 100:.2f} €)")
        session.commit()
    finally:
        session.close()
    return meldungen


def main() -> int:
    parser = argparse.ArgumentParser(description="Friondo Angebotstool – DB-Migration")
    parser.add_argument("--db", help="Pfad zu einer SQLite-Datei (Standard: data/angebotstool.db)")
    argumente = parser.parse_args()
    if argumente.db:
        import os
        os.environ["DB_PFAD_OVERRIDE"] = str(Path(argumente.db).resolve())

    from app import config
    print(f"Datenbank: {config.DB_PFAD}")
    meldungen = _schema() + _daten()
    if meldungen:
        for m in meldungen:
            print(" -", m)
    else:
        print(" - keine Änderungen nötig (bereits aktuell)")
    print("Migration abgeschlossen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
