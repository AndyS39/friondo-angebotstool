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
    # v23 (Phase 104, C4): nach dem letzten Versuch der Kaskade (Stufe 5);
    # Texte laut F9 Platzhalter – Andreas ersetzt sie in der Vorlagenpflege
    "disqualifiziert": (
        "Disqualifiziert / Nicht erreicht",
        "Ihre Anfrage bei Friondo – wir konnten Sie nicht erreichen",
        "{briefanrede},\n\n"
        "wir haben in den vergangenen Wochen mehrfach versucht, Sie zu Ihrer "
        "Anfrage ({sparten}) telefonisch zu erreichen – leider ohne Erfolg. "
        "Wir schließen den Vorgang daher vorerst ab.\n\n"
        "Sollte das Thema für Sie weiterhin aktuell sein, melden Sie sich "
        "jederzeit gern: {rueckruf_telefon} oder einfach als Antwort auf "
        "diese E-Mail. Ihr Ansprechpartner ist {vertriebler}.\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    # v23 (Phase 104, F12): Online-Termin per Teams – Kunde wählt den Slot
    # über den Outlook-Buchungslink des Kollegen
    "online_termin_einladung": (
        "Online-Termin (Teams) – Einladung",
        "Ihr Online-Termin mit Friondo – bitte Wunschzeit wählen",
        "{briefanrede},\n\n"
        "gern besprechen wir Ihre Fragen zu {sparten} vorab in einem kurzen "
        "Online-Termin (Microsoft Teams) mit {kollege}.\n\n"
        "Wählen Sie hier einfach einen passenden Zeitpunkt: {buchungslink}\n\n"
        "Sie erhalten anschließend automatisch eine Kalendereinladung mit dem "
        "Teams-Link.\n\n"
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
    # v23 (Phase 108, E3/E4): Absage durch Friondo mit Storno-ICS
    # (METHOD:CANCEL, gleiche UID) – der Kundenkalender entfernt den Eintrag
    "terminabsage": (
        "Terminabsage",
        "Ihr Termin am {termin_datum} um {termin_uhrzeit} Uhr wurde abgesagt",
        "{briefanrede},\n\n"
        "Ihr Vor-Ort-Termin am {termin_datum} um {termin_uhrzeit} Uhr mit "
        "{vertriebler} muss leider entfallen. Die Absage für Ihren Kalender "
        "liegt bei.\n\n"
        "Wir melden uns in Kürze mit einem neuen Terminvorschlag. Wenn Sie "
        "selbst einen Wunschtermin haben, erreichen Sie uns unter "
        "{rueckruf_telefon} oder einfach als Antwort auf diese E-Mail: "
        "{link_rueckruf}\n\n"
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
    from app.leadmanagement import wunschzeiten_liste
    wunschzeiten = ", ".join(wunschzeiten_liste(vorgang))
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
        # v23 (Phase 104): Rückruf-Telefon (Leadmanager, sonst Parameter
        # rueckruf_telefon), Kollege + Buchungslink für Online-Termine (F12)
        "rueckruf_telefon": (leadmanager.telefon if leadmanager and leadmanager.telefon
                             else _parameter(session, "rueckruf_telefon")),
        "kollege": vertriebler.name if vertriebler else "einem Kollegen",
        "buchungslink": (getattr(vertriebler, "buchungslink", "") or "")
                        if vertriebler else "",
    }


def _parameter(session: Session, name: str, standard: str = "") -> str:
    from app import leadmanagement as kern
    return kern.parameter_holen(session, name, standard)


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


def _ics_text(text: str) -> str:
    """Textwert nach RFC 5545 maskieren (Backslash, Semikolon, Komma, Zeilen)."""
    return ((text or "").replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\r\n", "\n").replace("\n", "\\n"))


def _ics_falten(zeile: str, breite: int = 74) -> str:
    """Zeilen länger als 75 Zeichen falten (Fortsetzung mit Leerzeichen)."""
    if len(zeile) <= breite:
        return zeile
    teile = [zeile[:breite]]
    rest = zeile[breite:]
    while rest:
        teile.append(" " + rest[:breite - 1])
        rest = rest[breite - 1:]
    return "\r\n".join(teile)


ICS_TYP_TITEL = {"vot": "Vor-Ort-Termin", "telefon": "Telefongespräch",
                 "online": "Online-Termin (Teams)"}


def ics_erstellen(session: Session, termin: VotTermin, vorgang: Vorgang,
                  methode: str = "REQUEST") -> str | None:
    """ICS-Anhang (Organizer = Absender-Postfach). v23 (Phase 108, E4):
    UID aus vot_termine.ics_uid (beim ersten Mal friondo-vot-{id}@friondo.de),
    SEQUENCE aus ics_sequence, Titel mit Sparten, LOCATION Kundenadresse,
    DESCRIPTION mit Berater + Telefon, Absage-Hinweis und Rückruf-Telefon,
    VALARM 24 h; methode="CANCEL" erzeugt die Storno-ICS (STATUS:CANCELLED,
    gleiche UID). Bestehende Aufrufer (rendern) bleiben unverändert."""
    from app import config
    kunde = session.get(Kunde, vorgang.kunde_id)
    if termin is None or termin.beginn is None or kunde is None:
        return None
    methode = "CANCEL" if str(methode).upper() == "CANCEL" else "REQUEST"
    ordner = config.DATA_ORDNER / "lead_ics"
    ordner.mkdir(parents=True, exist_ok=True)
    absender = _absender(session)
    ende = termin.ende or termin.beginn
    if not getattr(termin, "ics_uid", None):
        termin.ics_uid = f"friondo-vot-{termin.id}@friondo.de"
        session.flush()
    sequence = int(getattr(termin, "ics_sequence", 0) or 0)
    sparten = "+".join(s.strip() for s in (kunde.interesse or "").split(",")
                       if s.strip()) or "Ihre Anfrage"
    typ = getattr(termin, "typ", "vot") or "vot"
    titel = f"{ICS_TYP_TITEL.get(typ, 'Vor-Ort-Termin')} Friondo – {sparten}"
    if methode == "CANCEL":
        titel = "Abgesagt: " + titel
    berater = session.get(Benutzer, termin.ad_id) if termin.ad_id else None
    leadmanager = (session.get(Benutzer, vorgang.leadmanager_id)
                   if vorgang.leadmanager_id else None)
    rueckruf = ((leadmanager.telefon if leadmanager and leadmanager.telefon else "")
                or _parameter(session, "rueckruf_telefon") or "")
    adresse = termin.adresse or ""
    if typ == "vot" and not adresse:
        from app import geocoding
        adresse = geocoding.lead_adresse(session, vorgang)
    zeilen = []
    if methode == "CANCEL":
        zeilen.append("Dieser Termin wurde abgesagt. Wir melden uns mit einem neuen Vorschlag.")
    if berater is not None:
        zeilen.append(f"Ihr Berater: {berater.name}"
                      + (f", Telefon {berater.telefon}" if berater.telefon else ""))
    if typ == "vot":
        zeilen.append("Bitte halten Sie Heizkostenabrechnung, Stromrechnung und "
                      "Grundriss bereit (Zugang zu Heizungsraum und Zählerschrank).")
    if methode != "CANCEL":
        zeilen.append("Falls Sie den Termin nicht wahrnehmen können, sagen Sie bitte "
                      "rechtzeitig ab" + (f": Telefon {rueckruf}" if rueckruf else "")
                      + f" oder per E-Mail an {absender}.")
    elif rueckruf:
        zeilen.append(f"Rückfragen: Telefon {rueckruf} oder per E-Mail an {absender}.")
    beschreibung = "\n".join(zeilen)
    inhalt_zeilen = [
        "BEGIN:VCALENDAR",
        "PRODID:-//Friondo//Angebotstool//DE",
        "VERSION:2.0",
        f"METHOD:{methode}",
        "BEGIN:VEVENT",
        f"UID:{termin.ics_uid}",
        f"SEQUENCE:{sequence}",
        f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%S')}",
        f"DTSTART:{termin.beginn.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND:{ende.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:{_ics_text(titel)}",
        f"LOCATION:{_ics_text(adresse)}",
        f"DESCRIPTION:{_ics_text(beschreibung)}",
        f"STATUS:{'CANCELLED' if methode == 'CANCEL' else 'CONFIRMED'}",
        f"ORGANIZER;CN=Friondo:mailto:{absender}",
        f"ATTENDEE;CN={_ics_text(kunde.anzeige_name)};RSVP=FALSE:mailto:{kunde.email}",
    ]
    if methode != "CANCEL":
        inhalt_zeilen += ["BEGIN:VALARM", "TRIGGER:-PT24H", "ACTION:DISPLAY",
                          f"DESCRIPTION:{_ics_text('Erinnerung: ' + titel)}",
                          "END:VALARM"]
    inhalt_zeilen += ["END:VEVENT", "END:VCALENDAR", ""]
    inhalt = "\r\n".join(_ics_falten(z) for z in inhalt_zeilen)
    name = f"vot_{termin.id}.ics" if methode != "CANCEL" else f"vot_{termin.id}_storno.ics"
    pfad = ordner / name
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


def ics_methode(inhalt: bytes | str) -> str:
    """MIME-Methode eines ICS-Inhalts (REQUEST | CANCEL) aus der METHOD-Zeile."""
    text = inhalt.decode("utf-8", "ignore") if isinstance(inhalt, bytes) else (inhalt or "")
    return "CANCEL" if "METHOD:CANCEL" in text.upper() else "REQUEST"


def _graph_senden(session: Session, an: str, betreff: str, body_html: str,
                  anhang_pfad: str | None) -> tuple[bool, str]:
    """HTML-Mail (+ ICS) über Graph; Absender leads@, Fallback angebot@."""
    from app import graph_versand
    token = graph_versand._token()
    if token is None:
        return False, "Nicht bei Microsoft angemeldet"
    anhaenge = []
    if anhang_pfad and Path(anhang_pfad).exists():
        ics_bytes = Path(anhang_pfad).read_bytes()
        anhaenge.append({
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": Path(anhang_pfad).name,
            # v23 (Phase 108, E4): Storno-ICS mit MIME-Methode CANCEL, damit
            # Outlook/Apple den Kundeneintrag entfernen statt ihn zu ergänzen
            "contentType": f"text/calendar; method={ics_methode(ics_bytes)}",
            "contentBytes": base64.b64encode(ics_bytes).decode(),
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
    # Prozess-Fix 27.09.2026: Termin-Mails nur fuer aktive, kuenftige
    # Termine - Umbuchung/No-Show stornieren zwar (leadmanagement.
    # geplante_mails_stornieren), aber diese Pruefung faengt auch alle
    # Altbestaende und Randfaelle ab
    if eintrag.termin_id and eintrag.vorlage_key in ("terminerinnerung",
                                                     "terminbestaetigung"):
        from app.models import VotTermin
        termin = session.get(VotTermin, eintrag.termin_id)
        if (termin is None or termin.status not in ("geplant", "bestaetigt")
                or (eintrag.vorlage_key == "terminerinnerung"
                    and termin.beginn is not None
                    and termin.beginn < datetime.now())):
            eintrag.status = "storniert"
            eintrag.fehler_text = "Termin nicht mehr aktiv"
            return "storniert"
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
