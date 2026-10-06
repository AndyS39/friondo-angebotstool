# 90-Tage-Prüflauf (v8, Phase 51): versendete Angebote (Tool + extern) ohne
# Annahme/Ablehnung werden nach Ablauf der eingestellten Frist automatisch auf
# „Abgelehnt“ mit Grund „90 Tage Ablauf“ gesetzt – außer eine Wiedervorlage
# liegt in der Zukunft. Läuft täglich (Scheduler) und einmal beim Start;
# jeder Lauf wird protokolliert (Einstellung + Notiz je Angebot).
# v27 (PLAN_V17 Phase 128): am Scheduler-Rahmen (app/scheduler.py) registriert
# statt eigenem Thread; der Lauf arbeitet in einer kurzen Sitzung (db.kurz).

from datetime import datetime, timedelta

AUTO_GRUND = "90 Tage Ablauf"
_STATUS = ["Versendet", "Versendet (extern)"]


def kandidaten(session, jetzt: datetime | None = None):
    """Angebote, die der nächste Lauf ablehnen würde (Trockenmodus).
    v10 (Phase 60): eine zukünftige VORGANGS-Wiedervorlage schützt ALLE
    Angebote des Vorgangs; die alten Angebots-Wiedervorlagen schützen
    weiterhin (stillgelegter Bestand)."""
    from app.models import Angebot, Vorgang, einstellung_holen
    jetzt = jetzt or datetime.now()
    tage = int(einstellung_holen(session, "ablehnung_auto_tage", "90") or 90)
    grenze = jetzt - timedelta(days=tage)
    geschuetzte_vorgaenge = {v.id for v in session.query(Vorgang)
                             .filter(Vorgang.wiedervorlage_am.isnot(None),
                                     Vorgang.wiedervorlage_am > jetzt)}
    return [a for a in session.query(Angebot)
            .filter(Angebot.status.in_(_STATUS),
                    Angebot.versendet_am.isnot(None),
                    Angebot.versendet_am < grenze)
            if not (a.wiedervorlage_am and a.wiedervorlage_am > jetzt)
            and a.vorgang_id not in geschuetzte_vorgaenge], tage


def lauf(session=None, trocken: bool = False) -> dict:
    """Ein Prüflauf. trocken=True zählt nur, ändert nichts."""
    from app.db import SessionLocal
    from app.models import (AngebotsNotiz, Erfassung, angebot_status_setzen,
                            einstellung_holen, einstellung_setzen)
    eigen = session is None
    if eigen:
        session = SessionLocal()
    try:
        faellig, tage = kandidaten(session)
        if trocken:
            return {"anzahl": len(faellig), "tage": tage,
                    "nummern": [a.nummer for a in faellig]}
        for a in faellig:
            angebot_status_setzen(a, "Abgelehnt")
            try:   # Prozess-Fix 27.09.2026: Lead-Phase mitziehen
                from app import leadmanagement
                leadmanagement.phase_neu_berechnen(session, a.vorgang_id)
            except Exception:
                pass
            a.ablehnungsgrund = AUTO_GRUND
            session.add(AngebotsNotiz(
                angebot_id=a.id, benutzer_name="Prüflauf",
                text=f"Automatisch abgelehnt – {tage} Tage ohne Annahme/Ablehnung "
                     "und keine Wiedervorlage in der Zukunft."))
            erfassung = (session.query(Erfassung)
                         .filter(Erfassung.angebot_id == a.id).first())
            if erfassung is not None and erfassung.status != "Erledigt (extern)":
                erfassung.status = "Erledigt"
        zeile = (f"{datetime.now().strftime('%d.%m.%Y %H:%M')} · "
                 f"{len(faellig)} Angebot(e) automatisch abgelehnt (Frist {tage} Tage)")
        bisher = einstellung_holen(session, "ablehnung_auto_protokoll", "")
        zeilen = ([zeile] + bisher.splitlines())[:20]
        einstellung_setzen(session, "ablehnung_auto_protokoll", "\n".join(zeilen))
        session.commit()
        return {"anzahl": len(faellig), "tage": tage,
                "nummern": [a.nummer for a in faellig]}
    finally:
        if eigen:
            session.close()


def scheduler_lauf() -> dict:
    """v27 (PLAN_V17 Phase 128): ein Prüflauf in einer kurzen Sitzung – reine
    Datenbankarbeit ohne Netz-I/O, wenige Kandidaten je Tag (ein Commit)."""
    from app.db import kurz
    with kurz() as s:
        return lauf(s)


def scheduler_starten() -> None:
    """v27 (PLAN_V17 Phase 128): registriert den täglichen Lauf nur noch am
    Scheduler-Rahmen (erster Durchgang 120 s nach dem Start, danach alle 24 h);
    Threads startet ausschließlich main.lifespan über scheduler.starten_alle().
    Fehler protokolliert der Rahmen (data/fehler.log, Betriebs-Seite)."""
    from app import scheduler
    scheduler.registrieren(
        "ablauf-pruefung", 24 * 60 * 60, scheduler_lauf,
        beschreibung="90-Tage-Prüflauf: versendete Angebote ohne Reaktion auf Abgelehnt setzen",
        start_verzoegerung_s=120)
