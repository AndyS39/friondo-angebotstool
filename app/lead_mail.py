# Kundenkommunikation des Lead-Managements (v12, Phase 78) MIT SENDESPERRE:
# Vorlagen (Gruppe Lead-Management), Warteschlange kommunikation_log,
# Versand-Job jede Minute. mail_modus: protokoll (rendern, NICHT senden),
# test (an mail_testadresse mit [TEST …]-Präfix), live (nur zulässig bei
# lead_freigabe_modus = alle – sonst wird wie protokoll verarbeitet).
# Absender leads@friondo.de (Fallback angebot@ wie bei der Projektierung).

import base64
import threading
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Benutzer, KommunikationLog, Kunde, LeadQuelle, Vorgang, VotTermin

ABSENDER_FALLBACK = "angebot@friondo.de"
BASIS_URL = "http://192.168.35.4:8000"

# Starttexte (sachlich, Sie-Form); {schluessel}: (Name, Betreff, Text)
VORLAGEN_START = {
    "eingangsbestaetigung": (
        "Eingangsbestätigung",
        "Ihre Anfrage bei Friondo – wir melden uns in Kürze",
        "{briefanrede},\n\n"
        "vielen Dank für Ihre Anfrage ({sparten}). Wir haben sie erhalten und "
        "melden uns innerhalb der nächsten Stunden telefonisch bei Ihnen, um "
        "die nächsten Schritte zu besprechen.\n\n"
        "Falls Sie vorab Fragen haben, antworten Sie einfach auf diese "
        "E-Mail oder nutzen Sie den Rückruf-Link: {link_rueckruf}\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    "nicht_erreicht": (
        "Nicht erreicht",
        "Wir haben Sie leider nicht erreicht",
        "{briefanrede},\n\n"
        "wir haben mehrfach versucht, Sie telefonisch zu Ihrer Anfrage "
        "({sparten}) zu erreichen – leider ohne Erfolg.\n\n"
        "Rufen Sie uns gern zurück oder antworten Sie mit Ihrer Wunschzeit "
        "auf diese E-Mail: {link_rueckruf}\n"
        "Ihr Ansprechpartner: {leadmanager} {leadmanager_telefon}\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    "terminbestaetigung": (
        "Terminbestätigung",
        "Ihr Vor-Ort-Termin am {termin_datum} um {termin_uhrzeit} Uhr",
        "{briefanrede},\n\n"
        "wir bestätigen Ihren Vor-Ort-Termin:\n\n"
        "Datum: {termin_datum}, {termin_uhrzeit} Uhr (ca. {termin_dauer} "
        "Minuten)\nIhr Berater: {vertriebler} {vertriebler_telefon}\n\n"
        "Damit der Termin für Sie den größten Nutzen hat, legen Sie bitte "
        "bereit:\n"
        "- letzte Heizkostenabrechnung\n"
        "- aktuelle Stromrechnung\n"
        "- Grundriss, falls vorhanden\n"
        "- Zugang zum Heizungsraum und zum Zählerschrank\n\n"
        "Den Termin finden Sie im Anhang für Ihren Kalender.\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    "terminerinnerung": (
        "Terminerinnerung",
        "Erinnerung: Ihr Termin morgen um {termin_uhrzeit} Uhr",
        "{briefanrede},\n\n"
        "wir erinnern an Ihren Vor-Ort-Termin am {termin_datum} um "
        "{termin_uhrzeit} Uhr mit {vertriebler}.\n\n"
        "Sollte etwas dazwischenkommen, geben Sie uns bitte kurz Bescheid: "
        "{link_rueckruf}\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    "terminaenderung": (
        "Terminänderung",
        "Ihr Termin wurde verlegt: {termin_datum}, {termin_uhrzeit} Uhr",
        "{briefanrede},\n\n"
        "Ihr Vor-Ort-Termin wurde verlegt. Neuer Termin:\n\n"
        "Datum: {termin_datum}, {termin_uhrzeit} Uhr\n"
        "Ihr Berater: {vertriebler} {vertriebler_telefon}\n\n"
        "Der aktualisierte Kalendereintrag liegt bei. Falls der neue Termin "
        "nicht passt, melden Sie sich bitte kurz: {link_rueckruf}\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    "nurture": (
        "Nurture",
        "Ihre Anfrage bei Friondo – dürfen wir uns wieder melden?",
        "{briefanrede},\n\n"
        "vor einiger Zeit haben Sie sich für {sparten} interessiert. Wir "
        "konnten Sie damals leider nicht erreichen.\n\n"
        "Wenn das Thema für Sie wieder aktuell ist, freuen wir uns über "
        "eine kurze Rückmeldung: {link_rueckruf}\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
}

PLATZHALTER_NEU = ["{sparten}", "{quelle}", "{termin_datum}", "{termin_uhrzeit}",
                   "{termin_dauer}", "{vertriebler}", "{vertriebler_telefon}",
                   "{leadmanager}", "{leadmanager_telefon}", "{wunschzeiten}",
                   "{link_rueckruf}", "{briefanrede}"]


def vorlage_laden(session: Session, schluessel: str,
                  sparte: str = "") -> tuple[str, str]:
    """(Betreff, Text): je Sparte, sonst allgemein, sonst Startwert."""
    from app.models import einstellung_holen
    if sparte:
        betreff = einstellung_holen(
            session, f"lead_vorlage_{schluessel}_{sparte}_betreff", "")
        text = einstellung_holen(
            session, f"lead_vorlage_{schluessel}_{sparte}_text", "")
        if betreff and text:
            return betreff, text
    betreff = einstellung_holen(session, f"lead_vorlage_{schluessel}_betreff", "")
    text = einstellung_holen(session, f"lead_vorlage_{schluessel}_text", "")
    if betreff and text:
        return betreff, text
    _, start_betreff, start_text = VORLAGEN_START.get(
        schluessel, ("", "Friondo", ""))
    return start_betreff, start_text


def vorlagen_vorbelegen(session: Session) -> int:
    """Starttexte als Einstellungen anlegen (idempotent, migrate.py)."""
    from app.models import einstellung_holen, einstellung_setzen
    neu = 0
    for schluessel, (_, betreff, text) in VORLAGEN_START.items():
        if not einstellung_holen(session, f"lead_vorlage_{schluessel}_betreff", ""):
            einstellung_setzen(session, f"lead_vorlage_{schluessel}_betreff", betreff)
            einstellung_setzen(session, f"lead_vorlage_{schluessel}_text", text)
            neu += 1
    return neu


def werte_fuer(session: Session, vorgang: Vorgang,
               termin: VotTermin | None = None) -> dict:
    import json as json_modul
    kunde = session.get(Kunde, vorgang.kunde_id)
    quelle = session.get(LeadQuelle, vorgang.quelle_id) if vorgang.quelle_id else None
    leadmanager = (session.get(Benutzer, vorgang.leadmanager_id)
                   if vorgang.leadmanager_id else None)
    vertriebler = (session.get(Benutzer, termin.ad_id)
                   if termin is not None and termin.ad_id else None)
    if kunde is None:
        return {}
    if kunde.anrede == "Frau":
        briefanrede = f"Sehr geehrte Frau {kunde.nachname}"
    elif kunde.anrede == "Herr":
        briefanrede = f"Sehr geehrter Herr {kunde.nachname}"
    else:
        briefanrede = "Guten Tag"
    try:
        wunschzeiten = ", ".join(json_modul.loads(vorgang.wunschzeiten or "[]"))
    except ValueError:
        wunschzeiten = ""
    absender = _absender(session)
    return {
        "briefanrede": briefanrede,
        "name": kunde.anzeige_name,
        "sparten": (kunde.interesse or "").replace(",", ", ") or "Ihre Anfrage",
        "quelle": quelle.name if quelle else "",
        "termin_datum": termin.beginn.strftime("%d.%m.%Y") if termin and termin.beginn else "",
        "termin_uhrzeit": termin.beginn.strftime("%H:%M") if termin and termin.beginn else "",
        "termin_dauer": str(int((termin.ende - termin.beginn).total_seconds() // 60))
                        if termin and termin.beginn and termin.ende else "90",
        "vertriebler": vertriebler.name if vertriebler else "Ihr Friondo-Berater",
        "vertriebler_telefon": f"({vertriebler.telefon})"
                               if vertriebler and vertriebler.telefon else "",
        "leadmanager": leadmanager.name if leadmanager else "das Friondo-Team",
        "leadmanager_telefon": f"({leadmanager.telefon})"
                               if leadmanager and leadmanager.telefon else "",
        "wunschzeiten": wunschzeiten,
        "link_rueckruf": (f"mailto:{absender}?subject="
                          f"R%C3%BCckruf%20V{vorgang.id}"),
    }


def _absender(session: Session) -> str:
    from app import leadmanagement as kern
    return (kern.parameter_holen(session, "absender_postfach",
                                 "leads@friondo.de") or "leads@friondo.de").strip()


def _einsetzen(text: str, werte: dict) -> str:
    for schluessel, wert in werte.items():
        text = text.replace("{" + schluessel + "}", str(wert))
    return text


def _als_html(text: str) -> str:
    import html
    return "<p>" + html.escape(text).replace("\n\n", "</p><p>") \
        .replace("\n", "<br>") + "</p>"


def ics_erstellen(session: Session, termin: VotTermin, vorgang: Vorgang) -> str | None:
    """ICS-Anhang (METHOD:REQUEST, Organizer = Absender-Postfach)."""
    from app import config
    kunde = session.get(Kunde, vorgang.kunde_id)
    if termin is None or termin.beginn is None or kunde is None:
        return None
    ordner = config.DATA_ORDNER / "lead_ics"
    ordner.mkdir(parents=True, exist_ok=True)
    absender = _absender(session)
    ende = termin.ende or termin.beginn
    inhalt = "\r\n".join([
        "BEGIN:VCALENDAR",
        "PRODID:-//Friondo//Angebotstool//DE",
        "VERSION:2.0",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:friondo-vot-{termin.id}@friondo.de",
        f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%S')}",
        f"DTSTART:{termin.beginn.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND:{ende.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:Vor-Ort-Termin Friondo",
        f"LOCATION:{(termin.adresse or '').replace(',', '\\,')}",
        f"ORGANIZER;CN=Friondo:mailto:{absender}",
        f"ATTENDEE;CN={kunde.anzeige_name}:mailto:{kunde.email}",
        "END:VEVENT",
        "END:VCALENDAR", ""])
    pfad = ordner / f"vot_{termin.id}.ics"
    pfad.write_text(inhalt, encoding="utf-8")
    return str(pfad)


def rendern(session: Session, eintrag: KommunikationLog) -> bool:
    """Betreff/HTML in den Eintrag rendern; False bei fehlendem Vorgang."""
    vorgang = session.get(Vorgang, eintrag.vorgang_id)
    if vorgang is None:
        return False
    termin = session.get(VotTermin, eintrag.termin_id) if eintrag.termin_id else None
    kunde = session.get(Kunde, vorgang.kunde_id)
    sparte = ""
    if kunde is not None and kunde.interesse:
        sparte = kunde.interesse.split(",")[0].strip()
    betreff, text = vorlage_laden(session, eintrag.vorlage_key, sparte)
    werte = werte_fuer(session, vorgang, termin)
    eintrag.betreff = _einsetzen(betreff, werte)[:300]
    eintrag.body_html = _einsetzen(_als_html(text), werte)
    if eintrag.vorlage_key in ("terminbestaetigung", "terminaenderung") \
            and termin is not None:
        eintrag.anhang_pfad = ics_erstellen(session, termin, vorgang)
    return True


def _graph_senden(session: Session, an: str, betreff: str, body_html: str,
                  anhang_pfad: str | None) -> tuple[bool, str]:
    """HTML-Mail (+ ICS) über Graph; Absender leads@, Fallback angebot@."""
    from app import graph_versand
    token = graph_versand._token()
    if token is None:
        return False, "Nicht bei Microsoft angemeldet"
    anhaenge = []
    if anhang_pfad and Path(anhang_pfad).exists():
        anhaenge.append({
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": Path(anhang_pfad).name,
            "contentType": "text/calendar; method=REQUEST",
            "contentBytes": base64.b64encode(
                Path(anhang_pfad).read_bytes()).decode(),
        })
    def _senden(absender):
        nachricht = {
            "subject": betreff,
            "body": {"contentType": "html", "content": body_html},
            "toRecipients": [{"emailAddress": {"address": an}}],
            "from": {"emailAddress": {"address": absender}},
        }
        if anhaenge:
            nachricht["attachments"] = anhaenge
        graph_versand._graph_aufruf("POST", "/me/sendMail", token,
                                    {"message": nachricht,
                                     "saveToSentItems": False})
    absender = _absender(session)
    try:
        _senden(absender)
        return True, ""
    except Exception as fehler:
        if absender != ABSENDER_FALLBACK:
            try:
                _senden(ABSENDER_FALLBACK)
                return True, ""
            except Exception as fehler2:
                return False, str(fehler2)
        return False, str(fehler)


def eintrag_verarbeiten(session: Session, eintrag: KommunikationLog) -> str:
    """Einen fälligen Eintrag nach mail_modus verarbeiten (Plan 78)."""
    from app import leadmanagement as kern
    vorgang = session.get(Vorgang, eintrag.vorgang_id)
    if vorgang is None or not rendern(session, eintrag):
        eintrag.status = "fehler"
        eintrag.fehler_text = "Vorgang fehlt"
        return "fehler"
    # Nurture nur mit Werbe-Einwilligung (§7 UWG); Terminorganisation und
    # Eingangsbestätigung sind von der Anfrage gedeckt
    if eintrag.vorlage_key == "nurture" and not vorgang.einwilligung_werbung:
        eintrag.status = "fehler"
        eintrag.fehler_text = "Keine Werbe-Einwilligung – Nurture übersprungen"
        return "fehler"
    modus = kern.parameter_holen(session, "mail_modus", "protokoll")
    # Sendesperre: live ist nur bei lead_freigabe_modus = alle zulässig
    if modus == "live" and kern.demo_aktiv(session):
        modus = "protokoll"
    eintrag.modus = modus
    if modus == "protokoll":
        eintrag.status = "protokolliert"
        eintrag.gesendet_am = None
    elif modus == "test":
        testadresse = kern.parameter_holen(session, "mail_testadresse", "")
        if not testadresse:
            eintrag.status = "fehler"
            eintrag.fehler_text = "mail_modus=test ohne mail_testadresse"
            return "fehler"
        erfolg, fehler = _graph_senden(
            session, testadresse,
            f"[TEST an {eintrag.an}] {eintrag.betreff}"[:300],
            eintrag.body_html, eintrag.anhang_pfad)
        if not erfolg:
            eintrag.status = "fehler"
            eintrag.fehler_text = fehler[:500]
            return "fehler"
        eintrag.status = "gesendet"
        eintrag.gesendet_am = datetime.now()
    else:   # live
        erfolg, fehler = _graph_senden(session, eintrag.an, eintrag.betreff,
                                       eintrag.body_html, eintrag.anhang_pfad)
        if not erfolg:
            eintrag.status = "fehler"
            eintrag.fehler_text = fehler[:500]
            return "fehler"
        eintrag.status = "gesendet"
        eintrag.gesendet_am = datetime.now()
    kern.aktivitaet(session, vorgang.id, "mail_aus",
                    f"Mail {eintrag.vorlage_key} ({eintrag.status}, "
                    f"{modus}): {eintrag.betreff}")
    return eintrag.status


def versand_job(session: Session | None = None) -> dict:
    """Jede Minute: fällige Einträge (status=geplant, geplant_am erreicht)."""
    from app.db import SessionLocal
    eigen = session is None
    if eigen:
        session = SessionLocal()
    zaehler = {"protokolliert": 0, "gesendet": 0, "fehler": 0}
    try:
        for eintrag in (session.query(KommunikationLog)
                        .filter(KommunikationLog.status == "geplant",
                                KommunikationLog.geplant_am <= datetime.now())
                        .limit(50)):
            try:
                ergebnis = eintrag_verarbeiten(session, eintrag)
            except Exception as problem:
                eintrag.status = "fehler"
                eintrag.fehler_text = str(problem)[:500]
                ergebnis = "fehler"
            zaehler[ergebnis] = zaehler.get(ergebnis, 0) + 1
        session.commit()
        return zaehler
    finally:
        if eigen:
            session.close()


_scheduler_laeuft = False


def scheduler_starten() -> None:
    global _scheduler_laeuft
    if _scheduler_laeuft:
        return
    _scheduler_laeuft = True

    def schleife():
        import time
        time.sleep(150)
        while True:
            try:
                versand_job()
            except Exception:
                pass
            time.sleep(60)

    threading.Thread(target=schleife, daemon=True, name="lead-mail").start()
