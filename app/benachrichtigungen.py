# Benachrichtigungen (v11, Phase 69): Mail-Versand (sofort / Tagesdigest) über
# die bestehende Graph-Strecke, täglicher Fälligkeits-Lauf 07:00 und Digest
# 07:15. Die Glocken-Einträge selbst legt app/projektierung.py an
# (kern.benachrichtigen ruft hier sofort_versenden auf); dieses Modul liest
# sie für die Kopfzeile aus und verschickt die Mails.
# Grundsatz: Mail-Fehler werden protokolliert, blockieren das Tool aber nie.

import logging
import re
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app import config

# Fester Tool-Link im Firmennetz (Plan Phase 69)
BASIS_URL = config.BASIS_URL   # v27: aus der .env (BASIS_URL), Standard wie bisher
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
# v23 (Phase 110, F7): To-Dos nur über die Glocke – nie Sofort-/Digest-Mail
MAIL_FREIE_ARTEN = {"todo"}
ART_NAMEN["todo"] = "To-Do"


# --- Glocke (Kopfzeile) -----------------------------------------------------------

def _sichtbar_fuer(session: Session, benutzer) -> bool:
    """Demo-Filter: Projektierungs-Ereignisse nur, wenn das Modul für den
    Benutzer freigegeben ist (Admin bzw. freigabe_modus=alle)."""
    from app import projektierung as kern
    return kern.modul_sichtbar(session, benutzer)


def _lead_sichtbar_fuer(session: Session, benutzer) -> bool:
    from app import leadmanagement
    # Prozess-Fix 27.09.2026: der Aussendienst bekommt die Glocke
    # "Neuer VOT-Termin" (lead_ad_sicht), auch ohne volles Lead-Modul
    from app import lead_v2
    return (leadmanagement.lead_modul_sichtbar(session, benutzer)
            or leadmanagement.lead_ad_sicht(session, benutzer)
            # v23 (Phase 109, R-G5): Handelsvertreter sehen Lead-Glocken
            # (Zuweisung, Umverteilung, Termine) auch im Demo-Modus
            or lead_v2.ist_handelsvertreter(session, benutzer))


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
    from app.db import verbindung_freigeben
    absender = _absender(session)
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Absender ist gelesen;
    # der commit speichert die bereits angelegten Glocken-Einträge – wie bisher
    # beim commit des Aufrufers; msal kann das Token über das Netz erneuern)
    verbindung_freigeben(session)
    erfolg, fehler = graph_versand.text_mail_senden(empfaenger, betreff, text, absender)
    if not erfolg and absender != ABSENDER_FALLBACK:
        _protokollieren(session, f"Absender {absender} fehlgeschlagen ({fehler}) – "
                                 f"Fallback {ABSENDER_FALLBACK}")
        # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Protokollzeile
        # ist geschrieben; zweiter Versand über das Fallback-Postfach)
        verbindung_freigeben(session)
        erfolg, fehler = graph_versand.text_mail_senden(
            empfaenger, betreff, text, ABSENDER_FALLBACK)
    if not erfolg:
        _protokollieren(session, f"Mail an {empfaenger} fehlgeschlagen: {fehler}")
    return erfolg


def sofort_versenden(session: Session, benutzer_ids, text: str, link: str,
                     art: str = "") -> int:
    """Wird von kern.benachrichtigen für jeden Glocken-Eintrag aufgerufen:
    Benutzer mit Einstellung „sofort“ erhalten die Mail – seit v27 (PLAN_V17
    Phase 128) nicht mehr direkt, sondern über die Ausgangs-Warteschlange
    `mail_ausgang`: der Eintrag entsteht in derselben Transaktion wie die Glocke
    (kein Netzaufruf, kein Commit mitten in der Anfrage); der Scheduler-Lauf
    „mail-ausgang“ sendet nach dem Commit. Liefert die Anzahl eingereihter Mails."""
    if art in MAIL_FREIE_ARTEN:
        return 0   # F7: To-Dos ohne Mail
    from app.models import Benutzer, MailAusgang
    eingereiht = 0
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
        session.add(MailAusgang(empfaenger=benutzer.email[:300],
                                betreff=_betreff(session, text, art)[:300],
                                text=rumpf, art=(art or "")[:30], status="offen"))
        eingereiht += 1
    return eingereiht


# --- v27: Ausgangs-Warteschlange (Scheduler „mail-ausgang“, jede Minute) ----------------

MAIL_AUSGANG_VERSUCHE_MAX = 3
MAIL_AUSGANG_BLOCK = 50


def mail_ausgang_lauf() -> dict:
    """Offene Einträge der Warteschlange senden: lesen (kurze Sitzung) → Sitzung
    zu → Graph (mit Fallback-Absender wie mail_senden) → kurze Sitzung zum
    Zurückschreiben je Eintrag. Nach 3 Fehlversuchen bleibt ein Eintrag auf
    „fehler“ (Protokoll). Ohne Graph-Einrichtung werden offene Einträge als
    „fehler: Graph nicht eingerichtet“ abgelegt, damit nichts aufläuft."""
    from app import graph_versand
    from app.db import kurz
    from app.models import MailAusgang
    with kurz() as s:
        offen = [(m.id, m.empfaenger, m.betreff, m.text, int(m.versuche or 0))
                 for m in s.query(MailAusgang).filter(MailAusgang.status == "offen")
                 .order_by(MailAusgang.id).limit(MAIL_AUSGANG_BLOCK)]
        absender = _absender(s) if offen else ""
    ergebnis = {"gesendet": 0, "fehler": 0, "offen": max(0, len(offen))}
    if not offen:
        return ergebnis
    konfiguriert = graph_versand.konfiguriert()
    for eintrag_id, empfaenger, betreff, text, versuche in offen:
        fehler_text = ""
        erfolg = False
        if not konfiguriert:
            fehler_text = "Graph nicht eingerichtet"
        else:
            erfolg, fehler = graph_versand.text_mail_senden(empfaenger, betreff, text, absender)
            if not erfolg and absender != ABSENDER_FALLBACK:
                erfolg, fehler = graph_versand.text_mail_senden(
                    empfaenger, betreff, text, ABSENDER_FALLBACK)
            if not erfolg:
                fehler_text = str(fehler or "")[:500]
        with kurz() as s:
            m = s.get(MailAusgang, eintrag_id)
            if m is None:
                continue
            m.versuche = versuche + 1
            if erfolg:
                m.status, m.gesendet_am, m.fehler_text = "gesendet", datetime.now(), ""
                ergebnis["gesendet"] += 1
            else:
                m.fehler_text = fehler_text
                endgueltig = (not konfiguriert) or m.versuche >= MAIL_AUSGANG_VERSUCHE_MAX
                m.status = "fehler" if endgueltig else "offen"
                if endgueltig:
                    ergebnis["fehler"] += 1
                    _protokollieren(s, f"Mail an {empfaenger} fehlgeschlagen "
                                       f"({m.versuche} Versuche): {fehler_text}")
    ergebnis["offen"] = len(offen) - ergebnis["gesendet"] - ergebnis["fehler"]
    return ergebnis


def mail_ausgang_zaehler(session: Session) -> dict:
    """Für Betriebs-Seite und /health: offen und Fehler (letzte 24 h)."""
    from app.models import MailAusgang
    grenze = datetime.now() - timedelta(hours=24)
    return {"offen": session.query(MailAusgang).filter(MailAusgang.status == "offen").count(),
            "fehler_24h": session.query(MailAusgang).filter(
                MailAusgang.status == "fehler", MailAusgang.erstellt_am >= grenze).count()}


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
            eintraege = [e for e in eintraege if e.art not in MAIL_FREIE_ARTEN]   # v23 F7
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


# --- Scheduler (v27: am Rahmen app/scheduler.py registriert) -----------------------

_logger = logging.getLogger("angebotstool")


def _kurz(ergebnis: dict) -> str:
    """Ergebnis eines Teilschritts als kurzer Text für die Betriebs-Seite."""
    if ergebnis.get("uebersprungen"):
        return "übersprungen"
    return ", ".join(f"{k}={v}" for k, v in ergebnis.items())[:60]


def scheduler_lauf() -> dict:
    """Alle 5 Minuten: ab 07:00 der Fälligkeits-Lauf, ab 07:15 der Digest – die
    Datums-Schalter in den Funktionen sorgen dafür, dass beides nur einmal pro
    Tag läuft (auch nach einem Server-Neustart). v27 (PLAN_V17 Phase 128): beide
    Teilschritte je für sich abgesichert (ein Fehler blockiert den anderen
    nicht), Fehler stehen im Rückgabe-dict und im Datei-Log; eine Ausnahme gibt
    es nur, wenn alle ausgeführten Teilschritte scheiterten."""
    from app.db import kurz
    jetzt = datetime.now()
    ergebnis: dict = {}
    fehler: list[str] = []
    schritte = []
    if jetzt.hour >= 7:
        schritte.append(("faellig", taeglicher_lauf))
    if jetzt.hour > 7 or (jetzt.hour == 7 and jetzt.minute >= 15):
        schritte.append(("digest", digest_versenden))
    for name, funktion in schritte:
        try:
            # je Teilschritt eine kurze Sitzung; während der Graph-Mails hält sie
            # keine Verbindung (verbindung_freigeben in mail_senden)
            with kurz() as s:
                ergebnis[name] = _kurz(funktion(s))
        except Exception as problem:
            fehler.append(f"{name}: {type(problem).__name__}: {problem}"[:200])
            _logger.error("Benachrichtigungen – Teilschritt %s fehlgeschlagen: %s",
                          name, problem, exc_info=True)
    if not schritte:
        ergebnis["hinweis"] = "vor 07:00 nichts zu tun"
    if fehler:
        ergebnis["fehler"] = fehler
        ergebnis["hinweis"] = fehler[0]
        if len(fehler) == len(schritte):
            raise RuntimeError("; ".join(fehler)[:500])
    return ergebnis


def scheduler_starten() -> None:
    """v27 (PLAN_V17 Phase 128): registriert den 5-Minuten-Lauf nur noch am
    Scheduler-Rahmen (Startverzögerung 180 s wie bisher); Threads startet
    main.lifespan über scheduler.starten_alle()."""
    from app import scheduler
    scheduler.registrieren(
        "benachrichtigungen", 300, scheduler_lauf,
        beschreibung="Projektierung: Fälligkeits-Glocken ab 07:00, Tagesdigest-Mails ab 07:15",
        start_verzoegerung_s=180)
    # v27 (Phase 128): Sofort-Mails der Glocke aus der Warteschlange senden
    scheduler.registrieren(
        "mail-ausgang", 60, mail_ausgang_lauf,
        beschreibung="Sofort-Mails der Glocke aus der Warteschlange mail_ausgang senden",
        start_verzoegerung_s=90)
