# Benachrichtigungen (v11, Phase 69): Mail-Versand (sofort / Tagesdigest) über
# die bestehende Graph-Strecke, täglicher Fälligkeits-Lauf 07:00 und Digest
# 07:15. Die Glocken-Einträge selbst legt app/projektierung.py an
# (kern.benachrichtigen ruft hier sofort_versenden auf); dieses Modul liest
# sie für die Kopfzeile aus und verschickt die Mails.
# Grundsatz: Mail-Fehler werden protokolliert, blockieren das Tool aber nie.

import re
import threading
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

# Fester Tool-Link im Firmennetz (Plan Phase 69)
BASIS_URL = "http://192.168.35.4:8000"
ABSENDER_STANDARD = "projektierung@friondo.de"
ABSENDER_FALLBACK = "angebot@friondo.de"

# Ereignis-Namen für den Mail-Betreff „[Friondo] <Ereignis> – PR-… <Kunde>“
ART_NAMEN = {
    "aufgabe": "Neue Aufgabe",
    "erwaehnung": "Erwähnung",
    "faellig": "Fällige Aufgaben",
    "phase": "Phasenwechsel",
    "freigabe": "Freigabe",
    "gewerk": "Neues Gewerk",
    "kommentar": "Kommentar",
}
# In V1 stammen alle Ereignisse aus der Projektierung – im Demo-Modus
# (freigabe_modus=admin) sieht/erhält sie nur die Rolle Admin (Plan Phase 70).
PROJEKT_ARTEN = set(ART_NAMEN)
# v12: Ereignisse des Lead-Moduls, gleicher Demo-Filter über lead_freigabe_modus
LEAD_ARTEN = {"lead"}
ART_NAMEN["lead"] = "Lead-Management"


# --- Glocke (Kopfzeile) -----------------------------------------------------------

def _sichtbar_fuer(session: Session, benutzer) -> bool:
    """Demo-Filter: Projektierungs-Ereignisse nur, wenn das Modul für den
    Benutzer freigegeben ist (Admin bzw. freigabe_modus=alle)."""
    from app import projektierung as kern
    return kern.modul_sichtbar(session, benutzer)


def _lead_sichtbar_fuer(session: Session, benutzer) -> bool:
    from app import leadmanagement
    return leadmanagement.lead_modul_sichtbar(session, benutzer)


def _gefiltert(session: Session, benutzer, abfrage):
    from app.models import Benachrichtigung
    if not _sichtbar_fuer(session, benutzer):
        abfrage = abfrage.filter(~Benachrichtigung.art.in_(PROJEKT_ARTEN))
    if not _lead_sichtbar_fuer(session, benutzer):
        abfrage = abfrage.filter(~Benachrichtigung.art.in_(LEAD_ARTEN))
    return abfrage


def letzte(session: Session, benutzer, anzahl: int = 20) -> list:
    """Die letzten Einträge für das Glocken-Dropdown (Demo-Filter aktiv)."""
    from app.models import Benachrichtigung
    if benutzer is None:
        return []
    abfrage = _gefiltert(session, benutzer,
                         session.query(Benachrichtigung)
                         .filter(Benachrichtigung.benutzer_id == benutzer.id))
    return abfrage.order_by(Benachrichtigung.erstellt_am.desc()).limit(anzahl).all()


def ungelesen_anzahl(session: Session, benutzer) -> int:
    from app.models import Benachrichtigung
    if benutzer is None:
        return 0
    abfrage = _gefiltert(session, benutzer,
                         session.query(Benachrichtigung)
                         .filter(Benachrichtigung.benutzer_id == benutzer.id,
                                 Benachrichtigung.gelesen_am.is_(None)))
    return abfrage.count()


# --- Mail-Strecke -----------------------------------------------------------------

def _protokollieren(session: Session, zeile: str) -> None:
    """Letzte 20 Zeilen Mail-Protokoll in projektierung_parameter (wie das
    Protokoll des 90-Tage-Laufs in den Einstellungen)."""
    from app import projektierung as kern
    stempel = datetime.now().strftime("%d.%m.%Y %H:%M")
    bisher = kern.parameter_holen(session, "mail_protokoll", "")
    zeilen = ([f"{stempel} · {zeile}"] + bisher.splitlines())[:20]
    kern.parameter_setzen(session, "mail_protokoll", "\n".join(zeilen))


def _absender(session: Session) -> str:
    from app import projektierung as kern
    return (kern.parameter_holen(session, "absender_postfach", "")
            or ABSENDER_STANDARD).strip()


def _betreff(session: Session, text: str, art: str) -> str:
    """„[Friondo] <Ereignis> – PR-… <Kunde>“; PR-Nummer aus dem Text, Kunde
    über das Projekt."""
    from app.models import Kunde, Projekt
    betreff = f"[Friondo] {ART_NAMEN.get(art, 'Benachrichtigung')}"
    treffer = re.search(r"PR-\d{6}", text or "")
    if treffer:
        betreff += f" – {treffer.group(0)}"
        projekt = (session.query(Projekt)
                   .filter(Projekt.nummer == treffer.group(0)).first())
        if projekt is not None and projekt.kunde_id:
            kunde = session.get(Kunde, projekt.kunde_id)
            if kunde is not None:
                betreff += f" {kunde.anzeige_name}"
    return betreff


def mail_senden(session: Session, empfaenger: str, betreff: str, text: str) -> bool:
    """Eine Text-Mail über Graph; erst mit dem eingestellten Absender-Postfach,
    bei fehlender „Senden als“-Berechtigung Fallback auf angebot@friondo.de.
    Fehler landen im Protokoll, es wird nie eine Ausnahme geworfen."""
    from app import graph_versand
    absender = _absender(session)
    erfolg, fehler = graph_versand.text_mail_senden(empfaenger, betreff, text, absender)
    if not erfolg and absender != ABSENDER_FALLBACK:
        _protokollieren(session, f"Absender {absender} fehlgeschlagen ({fehler}) – "
                                 f"Fallback {ABSENDER_FALLBACK}")
        erfolg, fehler = graph_versand.text_mail_senden(
            empfaenger, betreff, text, ABSENDER_FALLBACK)
    if not erfolg:
        _protokollieren(session, f"Mail an {empfaenger} fehlgeschlagen: {fehler}")
    return erfolg


def sofort_versenden(session: Session, benutzer_ids, text: str, link: str,
                     art: str = "") -> None:
    """Wird von kern.benachrichtigen für jeden Glocken-Eintrag aufgerufen:
    Benutzer mit Einstellung „sofort“ erhalten die Mail direkt."""
    from app.models import Benutzer
    for bid in benutzer_ids:
        benutzer = session.get(Benutzer, bid)
        if (benutzer is None or not benutzer.aktiv
                or benutzer.benachrichtigung_mail != "sofort"):
            continue
        if art in PROJEKT_ARTEN and not _sichtbar_fuer(session, benutzer):
            continue   # Demo-Modus: keine Projektierungs-Mails an Nicht-Admins
        if art in LEAD_ARTEN and not _lead_sichtbar_fuer(session, benutzer):
            continue   # v12: gleicher Demo-Filter für das Lead-Modul
        if not benutzer.email:
            _protokollieren(session, f"{benutzer.name}: keine E-Mail-Adresse "
                                     "hinterlegt – Sofort-Mail übersprungen")
            continue
        rumpf = (f"{text}\n\nLink: {BASIS_URL}{link}\n\n"
                 "Diese Nachricht wurde automatisch vom Friondo Angebotstool "
                 "erzeugt (Einstellung im Benutzerprofil: sofort).")
        mail_senden(session, benutzer.email, _betreff(session, text, art), rumpf)


# --- Täglicher Fälligkeits-Lauf (07:00) -------------------------------------------

def taeglicher_lauf(session: Session | None = None, erzwingen: bool = False) -> dict:
    """Bündelt je Benutzer die heute fälligen und überfälligen offenen
    Aufgaben zu EINEM Glocken-Eintrag (Mail je nach Profil über die normale
    Sofort-Strecke). Läuft höchstens einmal pro Tag (Datums-Schalter)."""
    from app import projektierung as kern
    from app.db import SessionLocal
    from app.models import Aufgabe, Benutzer, Gewerk
    eigen = session is None
    if eigen:
        session = SessionLocal()
    try:
        heute = date.today()
        if (not erzwingen
                and kern.parameter_holen(session, "faellig_lauf_datum") == heute.isoformat()):
            return {"uebersprungen": True}
        morgen = datetime(heute.year, heute.month, heute.day) + timedelta(days=1)
        offene = (session.query(Aufgabe)
                  .filter(Aufgabe.status.notin_(("erledigt", "entfaellt")),
                          Aufgabe.verantwortlich_id.isnot(None),
                          Aufgabe.faellig_am.isnot(None),
                          Aufgabe.faellig_am < morgen).all())
        laufende = {g.id for g in session.query(Gewerk)
                    .filter(Gewerk.phase.notin_(("abgeschlossen", "storniert")))}
        je_benutzer: dict[int, dict[str, int]] = {}
        for a in offene:
            if a.gewerk_id not in laufende:
                continue
            eimer = je_benutzer.setdefault(a.verantwortlich_id,
                                           {"heute": 0, "ueberfaellig": 0})
            if a.faellig_am.date() == heute:
                eimer["heute"] += 1
            else:
                eimer["ueberfaellig"] += 1
        benachrichtigt = 0
        for bid, eimer in je_benutzer.items():
            benutzer = session.get(Benutzer, bid)
            if benutzer is None or not benutzer.aktiv:
                continue
            if not _sichtbar_fuer(session, benutzer):
                continue   # Demo-Modus: nur Admins
            teile = []
            if eimer["ueberfaellig"]:
                teile.append(f"{eimer['ueberfaellig']} Aufgabe(n) überfällig")
            if eimer["heute"]:
                teile.append(f"{eimer['heute']} Aufgabe(n) heute fällig")
            kern.benachrichtigen(session, [bid], "Projektierung: " + ", ".join(teile),
                                 "/projektierung/meine-aufgaben", art="faellig")
            benachrichtigt += 1
        kern.parameter_setzen(session, "faellig_lauf_datum", heute.isoformat())
        session.commit()
        return {"benachrichtigt": benachrichtigt}
    finally:
        if eigen:
            session.close()


# --- Tagesdigest (07:15) ----------------------------------------------------------

def digest_versenden(session: Session | None = None, erzwingen: bool = False) -> dict:
    """Eine Sammel-Mail je Benutzer mit Einstellung „digest“: alle
    Benachrichtigungen der letzten 24 Stunden. Höchstens einmal pro Tag."""
    from app import projektierung as kern
    from app.db import SessionLocal
    from app.models import Benachrichtigung, Benutzer
    eigen = session is None
    if eigen:
        session = SessionLocal()
    try:
        heute = date.today()
        if (not erzwingen
                and kern.parameter_holen(session, "digest_datum") == heute.isoformat()):
            return {"uebersprungen": True}
        seit = datetime.now() - timedelta(hours=24)
        versendet = 0
        for benutzer in (session.query(Benutzer)
                         .filter(Benutzer.aktiv.is_(True),
                                 Benutzer.benachrichtigung_mail == "digest")):
            eintraege = (session.query(Benachrichtigung)
                         .filter(Benachrichtigung.benutzer_id == benutzer.id,
                                 Benachrichtigung.erstellt_am >= seit)
                         .order_by(Benachrichtigung.erstellt_am).all())
            if not _sichtbar_fuer(session, benutzer):
                eintraege = [e for e in eintraege if e.art not in PROJEKT_ARTEN]
            if not _lead_sichtbar_fuer(session, benutzer):
                eintraege = [e for e in eintraege if e.art not in LEAD_ARTEN]
            if not eintraege:
                continue
            if not benutzer.email:
                _protokollieren(session, f"{benutzer.name}: keine E-Mail-Adresse "
                                         "hinterlegt – Digest übersprungen")
                continue
            zeilen = [f"- {e.text}" + (f"\n  {BASIS_URL}{e.link}" if e.link else "")
                      for e in eintraege]
            rumpf = ("Deine Benachrichtigungen der letzten 24 Stunden:\n\n"
                     + "\n".join(zeilen)
                     + "\n\nDiese Übersicht wurde automatisch vom Friondo "
                       "Angebotstool erzeugt (Einstellung im Benutzerprofil: "
                       "Tagesdigest).")
            if mail_senden(session, benutzer.email,
                           f"[Friondo] Tagesübersicht – {len(eintraege)} "
                           "Benachrichtigung(en)", rumpf):
                versendet += 1
        kern.parameter_setzen(session, "digest_datum", heute.isoformat())
        session.commit()
        return {"versendet": versendet}
    finally:
        if eigen:
            session.close()


# --- Scheduler (Muster wie ablauf_pruefung) ----------------------------------------

_scheduler_laeuft = False


def scheduler_starten() -> None:
    """Prüft alle 5 Minuten: ab 07:00 der Fälligkeits-Lauf, ab 07:15 der
    Digest – die Datums-Schalter sorgen dafür, dass beides nur einmal pro Tag
    läuft (auch nach einem Server-Neustart). Fehler blockieren das Tool nie."""
    global _scheduler_laeuft
    if _scheduler_laeuft:
        return
    _scheduler_laeuft = True

    def schleife():
        import time
        time.sleep(180)   # dem Serverstart Zeit lassen
        while True:
            try:
                jetzt = datetime.now()
                if jetzt.hour >= 7:
                    taeglicher_lauf()
                if jetzt.hour > 7 or (jetzt.hour == 7 and jetzt.minute >= 15):
                    digest_versenden()
            except Exception:
                pass
            time.sleep(300)

    threading.Thread(target=schleife, daemon=True,
                     name="benachrichtigungen").start()
