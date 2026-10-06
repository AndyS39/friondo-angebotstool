# BzA (V4, PLAN_PROJ_V4 Phase 92): Bestätigung zum Antrag der KfW-Förderung.
# Erfassung am Gewerk (BzA-ID, Datum, PDF in den Galerie-Ordner „Förderung“)
# und Kundenmail „BzA“ (Vorlage in der Parametrierung, Versand über Graph
# als projektierung@ – Fallback angebot@ –, CC Projektleiter). Im Demo-Modus
# der Projektierung (freigabe_modus = admin) geht die Mail ausschließlich an
# die Test-Adresse der Projektierung; ist keine hinterlegt, wird nicht versendet.

import json
from datetime import datetime

from app import projektierung as kern

GALERIE_ORDNER = "Förderung"

BETREFF_STANDARD = ("Ihre Bestätigung zum Antrag (BzA) für die Förderung Ihrer "
                    "Wärmepumpe – {projektnummer}")
TEXT_STANDARD = (
    "{briefanrede}\n\n"
    "anbei erhalten Sie Ihre Bestätigung zum Antrag (BzA) für die Förderung "
    "Ihrer neuen Wärmepumpe.\n\n"
    "So geht es weiter:\n"
    "1. Registrieren bzw. melden Sie sich im KfW-Zuschussportal an: {link_kfw}\n"
    "2. Stellen Sie dort den Antrag mit Ihrer BzA-ID: {bza_id}\n"
    "3. Wichtig: Bitte stellen Sie den Antrag vor Beginn der Arbeiten.\n\n"
    "Der voraussichtliche Zuschuss beträgt {foerderbetrag}.\n\n"
    "Bitte senden Sie uns nach der Antragstellung kurz Ihre KfW-Antragsnummer "
    "zurück – dann können wir alles Weitere für Sie vorbereiten.\n\n"
    "Bei Rückfragen erreichen Sie {ansprechpartner_friondo} unter den bekannten "
    "Kontaktdaten.\n\n"
    "Mit freundlichen Grüßen\n{ansprechpartner_friondo}\nFriondo GmbH")


def mail_aktiv(session) -> bool:
    """30.09.2026: BzA-Kundenmail per Häkchen in den Projektierung-
    Einstellungen abschaltbar (Standard: an)."""
    return kern.parameter_holen(session, "bza_mail_aktiv", "an") != "aus"


def ohne_mail_abschliessen(session, gewerk, benutzer=None) -> tuple[bool, str]:
    """BzA-Aufgabe ohne Kundenmail erledigen (Kunde erhält die BzA auf
    anderem Weg oder der Versand ist abgeschaltet)."""
    from app.models import Aufgabe
    if not gewerk.bza_id:
        return False, "Bitte zuerst die BzA erfassen (ID + PDF)."
    for aufgabe in (session.query(Aufgabe)
                    .filter(Aufgabe.gewerk_id == gewerk.id, Aufgabe.aktion_typ == "bza",
                            Aufgabe.aktion_wert != "kfw", Aufgabe.status != "erledigt")):
        aufgabe.status = "erledigt"
        aufgabe.erledigt_am = datetime.now()
        aufgabe.erledigt_von = benutzer.id if benutzer else None
    kern.verlauf(session, gewerk.projekt_id,
                 f"BzA {gewerk.bza_id} ohne Kundenmail abgeschlossen",
                 benutzer=benutzer, gewerk_id=gewerk.id)
    session.flush()
    return True, f"BzA {gewerk.bza_id} ohne Kundenmail abgeschlossen."


def _angebot(session, gewerk):
    from app.models import Angebot
    return session.get(Angebot, gewerk.angebot_id) if gewerk.angebot_id else None


def ist_gefoerdert(session, gewerk) -> bool | None:
    """True = Förderblock im Tool-Angebot aktiv (KfW-Daten, nicht
    ausgeblendet); False = Tool-Angebot ohne Förderung; None = unbekannt
    (TAIFUN-Auftrag, an dem „KfW-gefördert“ noch nicht beantwortet ist).
    V3 (Phase 84) / Phase 96: TAIFUN-Einträge tragen kfw_gefoerdert ja/nein."""
    angebot = _angebot(session, gewerk)
    if angebot is None:
        return None
    if angebot.extern:
        return {"ja": True, "nein": False}.get((angebot.kfw_gefoerdert or "").lower())
    try:
        kfw_daten = json.loads(angebot.kfw_json or "{}")
    except ValueError:
        kfw_daten = {}
    return bool(kfw_daten.get("O01")) and not angebot.foerderung_ausblenden


def foerderbetrag_cent(session, gewerk) -> int | None:
    """Voraussichtlicher Zuschuss aus dem Förder-Editor (None = unbekannt)."""
    angebot = _angebot(session, gewerk)
    if angebot is None or angebot.extern or not ist_gefoerdert(session, gewerk):
        return None
    from app import kfw
    from app import logik as logik_modul
    try:
        kfw_daten = json.loads(angebot.kfw_json or "{}")
        logik, _ = logik_modul.hole_logik(session)
        parameter, _ = kfw.parameter_lesen(logik)
        eingaben = kfw.eingaben_aus_antworten(kfw_daten, angebot.summen()["endbetrag"])
        if eingaben is None:
            return None
        return kfw.ergebnis_fuer_angebot(parameter, eingaben, angebot).zuschuss_cent
    except Exception:
        return None


def erfassen(session, gewerk, bza_id: str, datum: datetime | None,
             dateiname: str, inhalt: bytes, benutzer=None) -> tuple[bool, str]:
    """BzA-ID (Pflicht) + PDF (Pflicht) → Galerie „Förderung“, Felder am
    Gewerk, Verlaufseintrag."""
    from app import galerie
    bza_id = (bza_id or "").strip()[:100]
    if not bza_id:
        return False, "Bitte die BzA-ID aus dem Portal eintragen (Pflicht)."
    if not inhalt or not (dateiname or "").lower().endswith(".pdf"):
        return False, "Bitte das BzA-PDF hochladen (Pflicht, Dateityp PDF)."
    angebot = _angebot(session, gewerk)
    if angebot is None or not angebot.vorgang_id:
        return False, "Kein Vorgang am Auftrag – Ablage in der Galerie nicht möglich."
    datei = galerie.speichern(session, angebot.vorgang_id, GALERIE_ORDNER,
                              dateiname, inhalt, benutzer=benutzer,
                              bemerkung=f"BzA {bza_id}", quelle="formular",
                              sparte=gewerk.sparte)
    if datei is None:
        return False, "PDF konnte nicht gespeichert werden."
    gewerk.bza_id = bza_id
    gewerk.bza_erstellt_am = datum or datetime.now()
    gewerk.bza_datei_id = datei.id
    kern.verlauf(session, gewerk.projekt_id,
                 f"BzA erfasst: ID {bza_id} vom "
                 f"{gewerk.bza_erstellt_am.strftime('%d.%m.%Y')} (PDF in Galerie "
                 f"„{GALERIE_ORDNER}“)", benutzer=benutzer, gewerk_id=gewerk.id)
    session.flush()
    return True, f"BzA {bza_id} erfasst."


def platzhalter(session, gewerk) -> dict[str, str]:
    from app.models import Benutzer, Kunde, Projekt
    from app.templating import euro
    projekt = session.get(Projekt, gewerk.projekt_id)
    kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
    leiter = (session.get(Benutzer, projekt.projektleiter_id)
              if projekt and projekt.projektleiter_id else None)
    betrag = foerderbetrag_cent(session, gewerk)
    return {
        "briefanrede": kunde.briefanrede if kunde else "Sehr geehrte Damen und Herren,",
        "kunde": kunde.anzeige_name if kunde else "",
        "projektnummer": projekt.nummer if projekt else "",
        "bza_id": gewerk.bza_id or "–",
        "link_kfw": kern.parameter_holen(session, "url_kfw_zuschussportal", "")
        or "(Link zum KfW-Zuschussportal)",
        "foerderbetrag": euro(betrag) if betrag else "",
        "ansprechpartner_friondo": leiter.name if leiter else "Ihr Friondo-Team",
    }


def mail_entwurf(session, gewerk) -> tuple[str, str, str]:
    """(Empfänger, Betreff, Text) – Zeilen mit {foerderbetrag} entfallen,
    wenn kein Betrag bekannt ist."""
    from app.models import Kunde, Projekt
    daten = platzhalter(session, gewerk)
    vorlage = kern.parameter_holen(session, "bza_mail_text", "") or TEXT_STANDARD
    if not daten["foerderbetrag"]:
        vorlage = "\n".join(z for z in vorlage.split("\n") if "{foerderbetrag}" not in z)
        while "\n\n\n" in vorlage:
            vorlage = vorlage.replace("\n\n\n", "\n\n")
    betreff = kern.sub_mail_text(
        kern.parameter_holen(session, "bza_mail_betreff", "") or BETREFF_STANDARD, daten)
    projekt = session.get(Projekt, gewerk.projekt_id)
    kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
    return ((kunde.email if kunde else "") or "", betreff,
            kern.sub_mail_text(vorlage, daten))


def empfaenger_pruefen(session, empfaenger: str) -> tuple[str, str]:
    """(tatsächlicher Empfänger, Hinweis). Demo-Modus → Test-Adresse."""
    if kern.freigabe_modus(session) == "admin":
        test = kern.parameter_holen(session, "projekt_testadresse", "").strip()
        if not test:
            return "", ("Demo-Modus: keine Test-Adresse hinterlegt (Parametrierung → "
                        "Projektierung-Einstellungen) – die BzA-Mail wird nicht versendet.")
        return test, f"Demo-Modus: Versand an die Test-Adresse {test} statt an den Kunden."
    return empfaenger, ""


def mail_senden(session, gewerk, betreff: str, text: str,
                benutzer=None) -> tuple[bool, str]:
    from pathlib import Path

    from app import benachrichtigungen, config, graph_versand
    from app.models import Aufgabe, Benutzer, GalerieDatei, Projekt, ProjektMail
    kunde_mail, _b, _t = mail_entwurf(session, gewerk)
    if not mail_aktiv(session):
        return False, ("Der Versand der BzA-Kundenmail ist abgeschaltet "
                       "(Parametrierung → Projektierung-Einstellungen).")
    if not gewerk.bza_id or not gewerk.bza_datei_id:
        return False, "Bitte zuerst die BzA erfassen (ID + PDF)."
    empfaenger, hinweis = empfaenger_pruefen(session, kunde_mail)
    if not empfaenger:
        return False, hinweis or "Der Kunde hat keine E-Mail-Adresse."
    datei = session.get(GalerieDatei, gewerk.bza_datei_id)
    pfad = config.DATA_ORDNER / datei.pfad if datei is not None else None
    if pfad is None or not Path(pfad).exists():
        return False, "BzA-PDF nicht gefunden – bitte erneut erfassen."
    projekt = session.get(Projekt, gewerk.projekt_id)
    cc = []
    if projekt and projekt.projektleiter_id:
        leiter = session.get(Benutzer, projekt.projektleiter_id)
        if leiter is not None and leiter.email:
            cc.append(leiter.email)
    absender = benachrichtigungen._absender(session)
    anhang = (f"BzA_{projekt.nummer if projekt else ''}.pdf", Path(pfad).read_bytes(),
              "application/pdf")
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Empfänger, PDF,
    # Absender und CC sind gelesen; der Versand läuft über mehrere Graph-Aufrufe)
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    ok, fehler, _konversation = graph_versand.mail_mit_anhaengen_senden(
        empfaenger, betreff, text, [anhang], cc=cc, absender=absender)
    if not ok:
        return False, fehler
    gewerk.bza_gesendet_am = datetime.now()
    session.add(ProjektMail(
        projekt_id=gewerk.projekt_id,
        graph_id=f"bza-{gewerk.id}-{datetime.now():%Y%m%d%H%M%S}",
        von_name=benutzer.name if benutzer else "Angebotstool", von_email=absender,
        empfangen_am=datetime.now(), betreff=betreff, vorschau=text[:500],
        eingehend=False))
    for aufgabe in (session.query(Aufgabe)
                    .filter(Aufgabe.gewerk_id == gewerk.id, Aufgabe.aktion_typ == "bza",
                            Aufgabe.aktion_wert != "kfw",
                            Aufgabe.status != "erledigt")):
        aufgabe.status = "erledigt"
        aufgabe.erledigt_am = datetime.now()
        aufgabe.erledigt_von = benutzer.id if benutzer else None
    kern.verlauf(session, gewerk.projekt_id,
                 f"BzA-Mail an {empfaenger} gesendet (BzA {gewerk.bza_id})"
                 + (" – Demo-Test-Adresse" if hinweis else ""),
                 benutzer=benutzer, gewerk_id=gewerk.id)
    session.flush()
    return True, f"BzA-Mail an {empfaenger} gesendet." + (f" {hinweis}" if hinweis else "")


def kfw_setzen(session, gewerk, antragsnummer: str, zusage_am: datetime | None,
               benutzer=None) -> str:
    """KfW-Antragsnummer/Zusage (kein Wächter – CEO-Review Entscheidung 2
    offen); erledigt die Aufgabe „KfW-Antragsnummer/Zusage eingetragen“,
    sobald eine Antragsnummer vorliegt."""
    from app.models import Aufgabe
    gewerk.kfw_antragsnummer = (antragsnummer or "").strip()[:60]
    gewerk.kfw_zusage_am = zusage_am
    if gewerk.kfw_antragsnummer:
        for aufgabe in (session.query(Aufgabe)
                        .filter(Aufgabe.gewerk_id == gewerk.id,
                                Aufgabe.aktion_typ == "bza",
                                Aufgabe.aktion_wert == "kfw",
                                Aufgabe.status != "erledigt")):
            aufgabe.status = "erledigt"
            aufgabe.erledigt_am = datetime.now()
            aufgabe.erledigt_von = benutzer.id if benutzer else None
    kern.verlauf(session, gewerk.projekt_id,
                 f"KfW-Antragsnummer {gewerk.kfw_antragsnummer or '–'}"
                 + (f", Zusage vom {zusage_am.strftime('%d.%m.%Y')}" if zusage_am else ""),
                 benutzer=benutzer, gewerk_id=gewerk.id)
    session.flush()
    return "KfW-Daten gespeichert."
