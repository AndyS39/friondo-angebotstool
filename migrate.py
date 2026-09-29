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
        from app.models import Artikel
        meldungen += angebotsprofile.seed(session)
        # v8/v9: neue Zusatzartikel (Z23 MID-Zähler, Z24 Solar-Rückbau) müssen
        # im Artikelstamm liegen, sonst blockiert die Logik-Validierung –
        # fehlen sie, läuft der Preislisten-/Zusatzartikel-Import automatisch.
        # v13: ebenso Z25 (Vermerk Heizungsumverlegung, referenziert in
        # Aktionen D01 + Angebotsaufbau Block 5) und Z26 (Elektroarbeiten im
        # PV-Angebot) – ohne diesen Schritt blockierte die Validierung nach
        # dem Server-Update, weil update.bat keinen Import ausführt
        fehlend = [nr for nr in ("Z23", "Z24", "Z25", "Z26")
                   if session.query(Artikel).filter(Artikel.pos_nr == nr,
                                                    Artikel.aktiv.is_(True)).count() == 0]
        if fehlend:
            try:
                from app import import_preisliste
                _, import_meldung = import_preisliste.import_ausfuehren(session)
                meldungen.append(f"Zusatzartikel {', '.join(fehlend)} fehlten – "
                                 f"Preislisten-Import ausgeführt ({import_meldung})")
            except Exception as problem:
                meldungen.append(f"WARNUNG: Zusatzartikel {', '.join(fehlend)} fehlen "
                                 f"und der Import schlug fehl: {problem} – bitte "
                                 "Artikel → Preisliste importieren ausführen!")
        # v13-PV (PLAN_V13 Phase 75): PV-Artikel (PV001 …), auf die die Blätter
        # „Aktionen PV“/„Angebotsaufbau PV“ verweisen, müssen im Stamm liegen –
        # fehlen welche, läuft der PV-Positionslisten-Import automatisch
        # (update.bat führt sonst keinen Import aus → roter Validierungsfehler)
        try:
            from app import logik as _logik
            _l, _b = _logik.logik_einlesen()
            pv_refs = sorted(r for r in _logik.artikel_referenzen(_l) if r.startswith("PV"))
        except Exception:
            pv_refs = []
        vorhandene_pv = {nr for (nr,) in session.query(Artikel.pos_nr)
                         .filter(Artikel.pos_nr.like("PV%"), Artikel.aktiv.is_(True))}
        pv_fehlend = [r for r in pv_refs if r not in vorhandene_pv]
        if pv_fehlend:
            try:
                from app import import_pv
                _, pv_meldung = import_pv.import_ausfuehren(session)
                meldungen.append(f"PV-Artikel fehlten ({len(pv_fehlend)}, z. B. "
                                 f"{pv_fehlend[0]}) – PV-Positionslisten-Import "
                                 f"ausgeführt ({pv_meldung})")
            except Exception as problem:
                meldungen.append(f"WARNUNG: PV-Artikel fehlen und der PV-Import schlug "
                                 f"fehl: {problem} – bitte Artikel → PV-Positionslisten "
                                 "importieren ausführen!")
        session.commit()
        artikel_162 = (session.query(Artikel)
                       .filter(Artikel.pos_nr == "162", Artikel.aktiv.is_(True)).first())
        if (artikel_162 is not None
                and artikel_162.bezeichnung != angebotsprofile.POS_162_BEZEICHNUNG):
            artikel_162.bezeichnung = angebotsprofile.POS_162_BEZEICHNUNG
            artikel_162.beschreibung = angebotsprofile.POS_162_TEXT
            meldungen.append("Pos.-162-Text auf enni.flexstrom-Wortlaut aktualisiert "
                             f"(Preis unverändert: {artikel_162.e_preis_cent / 100:.2f} €)")
        session.commit()
        # ---------------- v10 (Phasen 59–63) ----------------
        # Phase 59: Vorgänge rückwirkend erzeugen (je Lead ein Vorgang;
        # Erfassungen/Angebote ohne Lead am Kunden-Vorgang) – idempotent
        from app import vorgaenge
        meldungen += vorgaenge.bestands_migration(session)
        session.commit()
        # Phase 60: Verfolgung auf Vorgangsebene – je Vorgang die heißeste
        # Angebots-Ampel und die früheste ZUKÜNFTIGE Wiedervorlage übernehmen;
        # die alten Angebots-Felder bleiben lesbar stehen (stillgelegt).
        # Verantwortlicher: leer = Innendienst-Sicht (bisher pflegte der ID
        # die Verfolgung; der Ersteller wurde nie protokolliert).
        from app.models import Vorgang
        if einstellung_holen(session, "migration_v10_verfolgung", "") != "erledigt":
            rang = {"heiss": 3, "warm": 2, "kalt": 1, "": 0}
            uebernommen = 0
            jetzt = _dt.now()
            for vorgang in session.query(Vorgang):
                beste = ""
                frueheste = None
                for a in session.query(Angebot).filter(Angebot.vorgang_id == vorgang.id):
                    if rang.get(a.verfolgung_ampel or "", 0) > rang.get(beste, 0):
                        beste = a.verfolgung_ampel
                    if (a.wiedervorlage_am and a.wiedervorlage_am > jetzt
                            and (frueheste is None or a.wiedervorlage_am < frueheste)):
                        frueheste = a.wiedervorlage_am
                geaendert = False
                if beste and not vorgang.verfolgung_ampel:
                    vorgang.verfolgung_ampel = beste
                    geaendert = True
                if frueheste is not None and vorgang.wiedervorlage_am is None:
                    vorgang.wiedervorlage_am = frueheste
                    geaendert = True
                uebernommen += geaendert
            einstellung_setzen(session, "migration_v10_verfolgung", "erledigt")
            if uebernommen:
                meldungen.append(f"Verfolgung auf Vorgangsebene übernommen "
                                 f"({uebernommen} Vorgänge; Ampel = heißeste, "
                                 "Wiedervorlage = früheste zukünftige)")
        # Phase 62: Deal-Werte werden NICHT automatisch nach monday
        # geschrieben – der Innendienst sichtet den Trockenlauf und bestätigt:
        # scripts\monday_deal_werte.py (bzw. --ausfuehren). Einmaliger Hinweis.
        if einstellung_holen(session, "migration_v10_dealwerte_hinweis", "") != "erledigt":
            einstellung_setzen(session, "migration_v10_dealwerte_hinweis", "erledigt")
            meldungen.append("HINWEIS: monday-Deal-Werte laufen jetzt als "
                             "VORGANGSSUMME – Bestand einmalig prüfen/schreiben mit "
                             "scripts\\monday_deal_werte.py (Trockenlauf, dann --ausfuehren)")
        # Phase 61: Startwerte Kombi-Versand (Vorlage + Gewerke-Artikel)
        from app import kombi_versand as kombi_modul
        if einstellung_holen(session, "gewerke_artikel", "") == "":
            einstellung_setzen(session, "gewerke_artikel",
                               kombi_modul.GEWERKE_ARTIKEL_START)
            meldungen.append("Gewerkeübergreifende Artikel vorbelegt "
                             f"({kombi_modul.GEWERKE_ARTIKEL_START})")
        # Phase 60: bestehende Verfolgungs-Notizen der Angebote als
        # Alt-Einträge in den Vorgangs-Chat kopieren (mit Herkunftsvermerk)
        from app.models import AngebotsNotiz, VorgangsNotiz
        if einstellung_holen(session, "migration_v10_notizen", "") != "erledigt":
            kopiert = 0
            nummern = {a.id: (a.nummer, a.vorgang_id)
                       for a in session.query(Angebot)}
            for notiz in session.query(AngebotsNotiz).order_by(AngebotsNotiz.angelegt_am):
                nummer, vorgang_id = nummern.get(notiz.angebot_id, ("?", None))
                if vorgang_id is None:
                    continue
                session.add(VorgangsNotiz(
                    vorgang_id=vorgang_id, benutzer_id=None,
                    benutzer_name=notiz.benutzer_name or "?",
                    zeit=notiz.angelegt_am, text=notiz.text,
                    herkunft=f"Angebot {nummer} (migriert)"))
                kopiert += 1
            einstellung_setzen(session, "migration_v10_notizen", "erledigt")
            if kopiert:
                meldungen.append(f"{kopiert} Angebots-Notizen in den "
                                 "Vorgangs-Chat übernommen (Alt-Einträge)")
        session.commit()
        # ---------------- v11: Projektierung V1 (Phasen 64–72) ----------------
        # Phase 64: Parameter vorbelegen (Storno-Gründe, Ordnervorlage,
        # Demo-Schalter) + Mehrfachrollen-Backfill (rollen = bisherige rolle)
        import json as _json

        from app import projektierung
        if projektierung.parameter_holen(session, "storno_gruende", "") == "":
            projektierung.parameter_setzen(
                session, "storno_gruende",
                _json.dumps(projektierung.STORNO_GRUENDE_STANDARD, ensure_ascii=False))
            meldungen.append("Projektierung: Storno-Gründe vorbelegt")
        if projektierung.parameter_holen(session, "ordnervorlage", "") == "":
            projektierung.parameter_setzen(
                session, "ordnervorlage",
                _json.dumps(projektierung.ORDNERVORLAGE_STANDARD, ensure_ascii=False))
            meldungen.append("Projektierung: Ordnervorlage vorbelegt (Konzept 3.5)")
        if projektierung.parameter_holen(session, "freigabe_modus", "") == "":
            projektierung.parameter_setzen(session, "freigabe_modus", "admin")
            meldungen.append("Projektierung: Demo-Modus aktiv (freigabe_modus = admin)")
        if projektierung.parameter_holen(session, "absender_postfach", "") == "":
            projektierung.parameter_setzen(session, "absender_postfach",
                                           "projektierung@friondo.de")
        from app.models import Benutzer as _Benutzer
        rollen_befuellt = 0
        for b in session.query(_Benutzer).filter(_Benutzer.rollen == ""):
            b.rollen = b.rolle
            rollen_befuellt += 1
        if rollen_befuellt:
            meldungen.append(f"{rollen_befuellt} Benutzer auf Mehrfachrollen "
                             "umgestellt (rollen = bisherige Rolle)")
        session.commit()
        # Phase 66: Altbestand – alle angenommenen Angebote ohne Gewerk →
        # Projekt + Gewerk (Phase Feinplanung); Angebote desselben Vorgangs
        # werden zu EINEM Projekt zusammengefasst (Schalter-idempotent).
        # Läuft auch im Demo-Modus sofort, damit die Demo echte Daten zeigt.
        meldungen += projektierung.altbestand_migrieren(session)
        session.commit()

        # ---------------- v12: Lead-Management V1 (Phasen 73–82) ----------------
        from app import leadmanagement
        from app.models import einstellung_holen, einstellung_setzen
        neu = leadmanagement.parameter_vorbelegen(session)
        if neu:
            meldungen.append(f"Lead-Parameter vorbelegt ({neu} Startwerte, "
                             "lead_freigabe_modus=admin)")
        session.commit()
        # Bestehende (gesyncte) Vorgänge: Eingangsdaten + abgeleitete
        # Lead-Phase (Schalter-idempotent; liest monday nur mit)
        if einstellung_holen(session, "migration_v12_leads", "") != "erledigt":
            anzahl = leadmanagement.nach_sync(session)
            einstellung_setzen(session, "migration_v12_leads", "erledigt")
            session.commit()
            meldungen.append(f"Lead-Phase für {anzahl} bestehende Vorgänge "
                             "abgeleitet (Badge monday)")
        # Phase 75: Startquellen + Parser-Standardregel (idempotent)
        from app import lead_parser
        neu_q = leadmanagement.quellen_vorbelegen(session)
        if neu_q:
            meldungen.append(f"{neu_q} Lead-Startquellen angelegt")
        if lead_parser.standardregel_anlegen(session):
            meldungen.append("Parser-Regel Formular-Standard angelegt")
        # Phase 78: Starttexte der sechs Lead-Vorlagen
        from app import lead_mail
        neue_vorlagen = lead_mail.vorlagen_vorbelegen(session)
        if neue_vorlagen:
            meldungen.append(f"{neue_vorlagen} Lead-Mail-Vorlagen vorbelegt")
        session.commit()

        # ---------------- v15: Projektierung V2 (Phase 74) ----------------
        # Neue Kanban-Phasen je Gewerk: bestehende Gewerke einmalig umziehen
        # (feinplanung → auftragseingang bzw. planung, wenn die Feinplanung
        # bereits erfasst wurde; die übrigen Phasen 1:1 laut Plan) und den
        # Projektstatus neu ableiten. Verlaufseintrag je geändertem Gewerk.
        if einstellung_holen(session, "migration_projv2_phasen", "") != "erledigt":
            from app.models import Gewerk as _Gewerk
            from app.models import Projekt as _Projekt
            mapping = {"feinplanung_abgeschlossen": "montagevorbereitung",
                       "montage_geplant": "montagevorbereitung",
                       "in_ausfuehrung": "montage",
                       "abnahme_offen": "abnahme_freigabe"}
            umgezogen = 0
            for g in session.query(_Gewerk):
                if g.phase == "feinplanung":
                    neu_phase = ("planung" if g.feinplanung_erfasst
                                 else "auftragseingang")
                elif g.phase in mapping:
                    neu_phase = mapping[g.phase]
                else:
                    continue
                alt_phase = g.phase
                g.phase = neu_phase
                projektierung.verlauf(
                    session, g.projekt_id,
                    f"Phase migriert (V2): {alt_phase} → {neu_phase} "
                    f"(Gewerk {g.sparte})", gewerk_id=g.id)
                umgezogen += 1
            session.flush()
            for p in session.query(_Projekt):
                projektierung.projektstatus_berechnen(session, p)
            einstellung_setzen(session, "migration_projv2_phasen", "erledigt")
            session.commit()
            meldungen.append(f"Projektierung V2: {umgezogen} Gewerke auf die "
                             "neuen Kanban-Phasen migriert")
        # Phase 76: Galerie am Vorgang – Altbestand aus data/projekte umziehen
        if einstellung_holen(session, "migration_projv2_galerie", "") != "erledigt":
            from app import galerie as galerie_modul
            umgezogen_g = galerie_modul.altbestand_migrieren(session)
            einstellung_setzen(session, "migration_projv2_galerie", "erledigt")
            session.commit()
            if umgezogen_g:
                meldungen.append(f"Projektierung V2: {umgezogen_g} Dokumente in "
                                 "die Vorgangs-Galerie umgezogen")
        # Phase 75: Team-Stammdaten (Montageteam 1-10, Subteam 1-5), idempotent
        neue_teams = projektierung.teams_vorbelegen(session)
        if neue_teams:
            session.commit()
            meldungen.append(f"Projektierung V2: {neue_teams} Teams angelegt "
                             "(Montageteam 1-10, Subteam 1-5)")
        # 27.09.2026 (Andreas): Paket "Foerderung" entfaellt komplett;
        # "BnD nach Abnahme erstellt" wandert ins Paket Abnahme & Freigabe.
        # Bestand: Foerderungs-Instanzen samt Aufgaben loeschen (erledigter
        # BnD-Status wird in die neue Aufgabe uebernommen).
        if einstellung_holen(session, "migration_bnd_abnahme", "") != "erledigt":
            from app.models import Aufgabe as _Aufgabe
            from app.models import AufgabenpaketInstanz as _Instanz
            from app.models import Gewerk as _GewerkBnd
            geloescht = ergaenzt = 0
            bnd_status: dict[int, tuple] = {}
            for instanz in (session.query(_Instanz)
                            .filter(_Instanz.paket_key == "foerderung")):
                for aufgabe in (session.query(_Aufgabe)
                                .filter(_Aufgabe.paket_instanz_id == instanz.id)):
                    if "BnD" in (aufgabe.titel or ""):
                        bnd_status[instanz.gewerk_id] = (
                            aufgabe.status, aufgabe.erledigt_am,
                            aufgabe.erledigt_von)
                    session.delete(aufgabe)
                    geloescht += 1
                session.delete(instanz)
            session.flush()
            # BnD-Aufgabe an bestehende aktive Abnahme-&-Freigabe-Instanzen
            for instanz in (session.query(_Instanz)
                            .filter(_Instanz.paket_key == "abnahme_freigabe",
                                    _Instanz.version != "v1",
                                    _Instanz.deaktiviert_am.is_(None))):
                vorhanden = (session.query(_Aufgabe)
                             .filter(_Aufgabe.paket_instanz_id == instanz.id,
                                     _Aufgabe.titel
                                     == "BnD nach Abnahme erstellt").count())
                if vorhanden:
                    continue
                status, erledigt_am, erledigt_von = bnd_status.get(
                    instanz.gewerk_id, ("offen", None, None))
                gewerk = session.get(_GewerkBnd, instanz.gewerk_id)
                if gewerk is None:
                    continue
                session.add(_Aufgabe(
                    gewerk_id=instanz.gewerk_id,
                    projekt_id=gewerk.projekt_id,
                    paket_instanz_id=instanz.id,
                    titel="BnD nach Abnahme erstellt",
                    beschreibung="Bestätigung nach Durchführung (KfW) – "
                                 "nur bei gefördertem Auftrag, sonst auf "
                                 "„entfällt“ setzen.",
                    rolle="projektierer", pflicht=True, reihenfolge=6,
                    faellig_regel="M+10", status=status,
                    erledigt_am=erledigt_am, erledigt_von=erledigt_von))
                ergaenzt += 1
            einstellung_setzen(session, "migration_bnd_abnahme", "erledigt")
            session.commit()
            meldungen.append(f"Foerderungs-Paket aufgeloest: {geloescht} "
                             f"Aufgaben entfernt, BnD-Punkt an {ergaenzt} "
                             "Abnahme-Pakete gehaengt")
        # 27.09.2026 (Andreas): V1-Aufgabenpakete restlos entfernen - die
        # erste Bereinigung liess abgeschlossene/stornierte Gewerke aus,
        # die Doppelung verwirrte in der Demo
        if einstellung_holen(session, "migration_v1_restlos", "") != "erledigt":
            from app.models import Gewerk as _GewerkV1b
            weg = 0
            for g in session.query(_GewerkV1b):
                weg += projektierung.v1_aufgaben_entfernen(session, g)
            einstellung_setzen(session, "migration_v1_restlos", "erledigt")
            session.commit()
            if weg:
                meldungen.append(f"V1-Restbestand entfernt ({weg} Aufgaben)")
        # 27.09.2026 (Andreas, Nachtrag): "Abweichungen zum Angebot geprueft,
        # ggf. Nachtrag" als Pflicht-Schritt 5 im Paket Abnahme & Freigabe -
        # bestehende Instanzen bekommen die Aufgabe, Rechnung/BnD ruecken
        # in der Reihenfolge auf 6/7
        if einstellung_holen(session, "migration_abweichung_abnahme", "") != "erledigt":
            from app.models import Aufgabe as _AufgAbw
            from app.models import AufgabenpaketInstanz as _InstAbw
            from app.models import Gewerk as _GewAbw
            ergaenzt = 0
            for instanz in (session.query(_InstAbw)
                            .filter(_InstAbw.paket_key == "abnahme_freigabe",
                                    _InstAbw.version != "v1",
                                    _InstAbw.deaktiviert_am.is_(None))):
                gewerk = session.get(_GewAbw, instanz.gewerk_id)
                if gewerk is None or gewerk.phase in ("abgeschlossen",
                                                      "storniert"):
                    continue
                aufgaben = (session.query(_AufgAbw)
                            .filter(_AufgAbw.paket_instanz_id == instanz.id)
                            .all())
                if any(a.titel.startswith("Abweichungen zum Angebot")
                       for a in aufgaben):
                    continue
                for a in aufgaben:
                    if a.titel == "Rechnung freigegeben":
                        a.reihenfolge = 6
                    elif a.titel == "BnD nach Abnahme erstellt":
                        a.reihenfolge = 7
                session.add(_AufgAbw(
                    gewerk_id=instanz.gewerk_id, projekt_id=gewerk.projekt_id,
                    paket_instanz_id=instanz.id,
                    titel="Abweichungen zum Angebot geprüft, ggf. Nachtrag",
                    beschreibung="Mehr-/Minderleistungen aus der Montage mit "
                                 "dem Auftrag abgleichen, bevor die Rechnung "
                                 "freigegeben wird.",
                    rolle="projektierer", pflicht=True, reihenfolge=5,
                    faellig_regel="M+4"))
                ergaenzt += 1
            einstellung_setzen(session, "migration_abweichung_abnahme",
                               "erledigt")
            session.commit()
            meldungen.append(f"Abnahme & Freigabe: Abweichungs-Pruefung an "
                             f"{ergaenzt} Gewerke gehaengt")
        # 27.09.2026 (Andreas): Alt-Gewerke bereinigen - V1-Aufgabenpakete
        # entfernen und das Paket Abnahme & Freigabe auf die vollen sechs
        # Schritte auffuellen (alte v2-Instanzen aus der V1-Aera waren leer,
        # die BnD-Migration haengte dort nur den einen Punkt an)
        if einstellung_holen(session, "migration_v1_bereinigung", "") != "erledigt":
            from app import projektierung_logik as _pl
            from app.models import Aufgabe as _AufgabeV1
            from app.models import AufgabenpaketInstanz as _InstanzV1
            from app.models import Gewerk as _GewerkV1
            logik = _pl.hole_logik(session)
            paket_ab = logik.pakete.get("abnahme_freigabe")
            v1_weg = aufgefuellt = 0
            for g in session.query(_GewerkV1).filter(
                    ~_GewerkV1.phase.in_(["abgeschlossen", "storniert"])):
                v1_weg += projektierung.v1_aufgaben_entfernen(session, g)
                if paket_ab is None:
                    continue
                instanz = (session.query(_InstanzV1)
                           .filter(_InstanzV1.gewerk_id == g.id,
                                   _InstanzV1.paket_key == "abnahme_freigabe",
                                   _InstanzV1.version != "v1",
                                   _InstanzV1.deaktiviert_am.is_(None)).first())
                if instanz is None:
                    if projektierung.paket_aktivieren(
                            session, g, paket_ab, quelle="migration") is not None:
                        aufgefuellt += 1
                    continue
                vorhanden = {a.titel for a in
                             session.query(_AufgabeV1)
                             .filter(_AufgabeV1.paket_instanz_id == instanz.id)}
                fehlt = [sch for sch in paket_ab.schritte
                         if sch.titel not in vorhanden]
                for schritt in fehlt:
                    session.add(_AufgabeV1(
                        gewerk_id=g.id, projekt_id=g.projekt_id,
                        paket_instanz_id=instanz.id, titel=schritt.titel,
                        beschreibung=schritt.beschreibung, rolle=schritt.rolle,
                        pflicht=schritt.pflicht, reihenfolge=schritt.nr,
                        faellig_regel=schritt.faellig_regel,
                        aktion_typ=schritt.aktion_typ or "",
                        aktion_wert=schritt.aktion_wert or "",
                        optionen=schritt.optionen or ""))
                if fehlt:
                    aufgefuellt += 1
            einstellung_setzen(session, "migration_v1_bereinigung", "erledigt")
            session.commit()
            meldungen.append(f"Alt-Gewerke bereinigt: {v1_weg} V1-Aufgaben "
                             f"entfernt, Abnahme & Freigabe an {aufgefuellt} "
                             "Gewerken aufgefuellt")
        # Phase 78: Aufgabenpakete v2 – Bestandsinstanzen der ersetzten Pakete
        # als V1 kennzeichnen (Knopf „V1-Aufgaben entfernen" räumt später auf)
        # und die neuen IMMER-Pakete an offenen Gewerken zusätzlich aktivieren
        if einstellung_holen(session, "migration_projv2_pakete", "") != "erledigt":
            from app import projektierung_logik as _pl
            from app.models import AufgabenpaketInstanz as _Instanz
            from app.models import Gewerk as _Gewerk
            ersetzt = {"feinplanung_wp", "elektroplanung_wp", "beschaffung_wp",
                       "spotdynamic_imsys", "fundament_gala",
                       "oeltank_entsorgung", "lift_kran", "dach_statik",
                       "auftragseingang", "montagevorbereitung", "foerderung"}
            alte = 0
            for instanz in session.query(_Instanz):
                if (instanz.version or "") != "v1" and instanz.paket_key in ersetzt:
                    instanz.version = "v1"
                    alte += 1
            session.flush()
            logik = _pl.hole_logik(session)
            aktiviert = 0
            if not logik.fehler:
                for g in session.query(_Gewerk).filter(
                        ~_Gewerk.phase.in_(["abgeschlossen", "storniert"])):
                    for paket in logik.immer_pakete(g.sparte):
                        if projektierung.paket_aktivieren(
                                session, g, paket, quelle="migration") is not None:
                            aktiviert += 1
            einstellung_setzen(session, "migration_projv2_pakete", "erledigt")
            session.commit()
            meldungen.append(f"Projektierung V2: {alte} Paket-Instanzen als V1 "
                             f"markiert, {aktiviert} v2-Pakete aktiviert")
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
