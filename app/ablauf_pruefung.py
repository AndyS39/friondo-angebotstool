# 90-Tage-Prüflauf (v8, Phase 51): versendete Angebote (Tool + extern) ohne
# Annahme/Ablehnung werden nach Ablauf der eingestellten Frist automatisch auf
# „Abgelehnt“ mit Grund „90 Tage Ablauf“ gesetzt – außer eine Wiedervorlage
# liegt in der Zukunft. Läuft täglich (Scheduler) und einmal beim Start;
# jeder Lauf wird protokolliert (Einstellung + Notiz je Angebot).

import threading
from datetime import datetime, timedelta

AUTO_GRUND = "90 Tage Ablauf"
_STATUS = ["Versendet", "Versendet (extern)"]


def kandidaten(session, jetzt: datetime | None = None):
    """Angebote, die der nächste Lauf ablehnen würde (Trockenmodus)."""
    from app.models import Angebot, einstellung_holen
    jetzt = jetzt or datetime.now()
    tage = int(einstellung_holen(session, "ablehnung_auto_tage", "90") or 90)
    grenze = jetzt - timedelta(days=tage)
    return [a for a in session.query(Angebot)
            .filter(Angebot.status.in_(_STATUS),
                    Angebot.versendet_am.isnot(None),
                    Angebot.versendet_am < grenze)
            if not (a.wiedervorlage_am and a.wiedervorlage_am > jetzt)], tage


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


_scheduler_laeuft = False


def scheduler_starten() -> None:
    """Täglicher Lauf: erster Durchgang kurz nach dem Start, danach alle 24 h.
    Fehler blockieren das Tool nie."""
    global _scheduler_laeuft
    if _scheduler_laeuft:
        return
    _scheduler_laeuft = True

    def schleife():
        import time
        time.sleep(120)   # dem Serverstart Zeit lassen
        while True:
            try:
                lauf()
            except Exception:
                pass
            time.sleep(24 * 60 * 60)

    threading.Thread(target=schleife, daemon=True,
                     name="ablauf-pruefung").start()
