# Kunden-Terminbestaetigung (v15, Phase 81): Mail an den Kunden mit dem
# Montagetermin (Vorlage in der Parametrierung, Platzhalter wie bei den
# Sub-Mails); die Kundenantwort setzt einen Vorschlag "Kunde hat bestaetigt"
# (ein Klick in der Akte) – das manuelle Haekchen bleibt.

from datetime import datetime

from app import projektierung as kern

BETREFF_STANDARD = "Ihr Montagetermin · {termin} · Friondo"
TEXT_STANDARD = (
    "Guten Tag {kunde},\n\n"
    "wir haben Ihren Montagetermin eingeplant:\n\n"
    "Termin: {termin}\nTeam: {team}\n\n"
    "Zur Vorbereitung: {vorbereitung}\n\n"
    "Bitte antworten Sie kurz auf diese Mail, um den Termin zu bestätigen.\n\n"
    "Mit freundlichen Grüßen\n{ansprechpartner_friondo}\nFriondo GmbH")
VORBEREITUNG_STANDARD = ("Bitte halten Sie den Zugang zum Heizungsraum und "
                         "zum Aufstellort des Außengeräts frei.")


def platzhalter(session, termin) -> dict[str, str]:
    from app.models import Benutzer, Gewerk, Kunde, Projekt, Team
    projekt = session.get(Projekt, termin.projekt_id)
    kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
    team = session.get(Team, termin.team_id) if termin.team_id else None
    gewerk = session.get(Gewerk, termin.gewerk_id) if termin.gewerk_id else None
    leiter = (session.get(Benutzer, projekt.projektleiter_id)
              if projekt and projekt.projektleiter_id else None)
    text = termin.beginn.strftime("%A, %d.%m.%Y") if termin.beginn else "–"
    if termin.ende and termin.beginn and termin.ende.date() != termin.beginn.date():
        text += " – " + termin.ende.strftime("%d.%m.%Y")
    tage = {"Monday": "Montag", "Tuesday": "Dienstag", "Wednesday": "Mittwoch",
            "Thursday": "Donnerstag", "Friday": "Freitag",
            "Saturday": "Samstag", "Sunday": "Sonntag"}
    for en, de in tage.items():
        text = text.replace(en, de)
    return {
        "kunde": kunde.anzeige_name if kunde else "–",
        "termin": text,
        "team": team.name if team else "unser Montageteam",
        "sparte": gewerk.sparte if gewerk else "",
        "projektnummer": projekt.nummer if projekt else "",
        "ansprechpartner_friondo": leiter.name if leiter else "Friondo-Team",
        "vorbereitung": kern.parameter_holen(session, "terminmail_vorbereitung",
                                             VORBEREITUNG_STANDARD),
    }


def senden(session, termin, benutzer=None) -> tuple[bool, str]:
    from app import benachrichtigungen, graph_versand
    from app.models import Kunde, Projekt, ProjektMail
    projekt = session.get(Projekt, termin.projekt_id)
    kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
    if kunde is None or not (kunde.email or "").strip():
        return False, "Der Kunde hat keine E-Mail-Adresse."
    daten = platzhalter(session, termin)
    betreff = kern.sub_mail_text(
        kern.parameter_holen(session, "terminmail_betreff", BETREFF_STANDARD),
        daten)
    text = kern.sub_mail_text(
        kern.parameter_holen(session, "terminmail_text", TEXT_STANDARD),
        daten)
    absender = benachrichtigungen._absender(session)
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Empfänger, Texte
    # und Absender sind gelesen; der Versand läuft über mehrere Graph-Aufrufe)
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    ok, fehler, conversation_id = graph_versand.mail_mit_anhaengen_senden(
        kunde.email, betreff, text, absender=absender)
    if not ok:
        return False, fehler
    termin.graph_conversation_id = conversation_id or None
    session.add(ProjektMail(
        projekt_id=termin.projekt_id, graph_id=f"termin-{termin.id}-"
        f"{datetime.now():%Y%m%d%H%M%S}",
        von_name=benutzer.name if benutzer else "Angebotstool",
        von_email=absender,
        empfangen_am=datetime.now(), betreff=betreff,
        vorschau=text[:500], eingehend=False))
    kern.verlauf(session, termin.projekt_id,
                 f"Terminbestätigung an {kunde.anzeige_name} gesendet "
                 f"({daten['termin']})", benutzer=benutzer,
                 gewerk_id=termin.gewerk_id)
    session.flush()
    return True, f"Terminmail an {kunde.email} gesendet."


def antworten_abgleichen() -> int:
    """Kundenantworten auf Terminmails (Konversation) – setzt
    kunden_antwort_am; die Akte schlägt dann „Kunde hat bestätigt“ vor."""
    from app import benachrichtigungen, graph_versand, mail_sync
    from app.db import SessionLocal, verbindung_freigeben
    from app.models import Benutzer, Projekt, ProjektMail, ProjektTermin
    token = graph_versand._token()
    if token is None:
        return 0
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben – das angemeldete
    # Konto wird wie das Token VOR der Sitzung ermittelt (msal kann es über
    # das Netz erneuern)
    konto = (graph_versand.angemeldeter_benutzer() or "").lower()
    session = SessionLocal()
    neu_gesamt = 0
    try:
        postfach = benachrichtigungen._absender(session)
        eigene = {postfach.lower(), konto}
        for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True)):
            if b.email:
                eigene.add(b.email.lower())
        offene = (session.query(ProjektTermin)
                  .filter(ProjektTermin.graph_conversation_id.isnot(None),
                          ProjektTermin.kunde_bestaetigt.is_(False)).all())
        for termin in offene:
            # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (vor JEDEM
            # Graph-Abruf; der commit speichert die Antworten des vorherigen
            # Termins – wie bisher am Ende des Laufs)
            verbindung_freigeben(session)
            try:
                nachrichten = mail_sync.nachrichten_je_konversation(
                    token, termin.graph_conversation_id, postfach)
            except Exception:
                continue
            for nachricht in nachrichten:
                graph_id = nachricht.get("id") or ""
                if not graph_id or nachricht.get("isDraft"):
                    continue
                if session.query(ProjektMail).filter(
                        ProjektMail.graph_id == graph_id).first() is not None:
                    continue
                absender = ((nachricht.get("from") or {})
                            .get("emailAddress") or {})
                von_email = absender.get("address") or ""
                eingehend = bool(von_email) and von_email.lower() not in eigene
                session.add(ProjektMail(
                    projekt_id=termin.projekt_id, graph_id=graph_id,
                    von_name=absender.get("name") or "",
                    von_email=von_email,
                    empfangen_am=mail_sync._zeit_parsen(
                        nachricht.get("receivedDateTime")
                        or nachricht.get("sentDateTime") or ""),
                    betreff=nachricht.get("subject") or "",
                    vorschau=nachricht.get("bodyPreview") or "",
                    eingehend=eingehend))
                neu_gesamt += 1
                if eingehend and termin.kunden_antwort_am is None:
                    termin.kunden_antwort_am = datetime.now()
                    projekt = session.get(Projekt, termin.projekt_id)
                    if projekt is not None:
                        kern.benachrichtigen(
                            session, [projekt.projektleiter_id],
                            f"Kunde hat auf die Terminmail zu "
                            f"{projekt.nummer} geantwortet",
                            f"/projektierung/projekt/{projekt.id}",
                            art="termin")
        session.commit()
    finally:
        session.close()
    return neu_gesamt
