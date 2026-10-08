# v29 (PLAN_LEAD_V4 Phase 142): Lauf `lead-mail-abruf` (120 s, Scheduler-Rahmen) –
# Antworten und Unzustellbarkeitsberichte (Bounces) aus dem Lead-Absender-
# Postfach absender_lead_mails (termin@friondo.de) abrufen und dem Vorgang
# zuordnen. leads@friondo.de bleibt ausschließlich Parser-Eingang (lead_parser,
# Lauf lead-parser) und wird hier nicht angefasst.
#
# Sitzungsdisziplin (v27): Parameter in einer kurzen Sitzung lesen → Sitzung zu →
# Graph (Token, Posteingang) OHNE Sitzung → je Nachricht eine kurze Sitzung zum
# Zurückschreiben (Commit) → danach PATCH isRead ohne Sitzung. Höchstens
# BLOCK_GROESSE (50) Nachrichten je Lauf.
#
# Zuordnung einer Nachricht zu Vorgang/Eintrag (keine Konversations-ID am
# Warteschlangen-Eintrag – /me/sendMail liefert keine; Vorschlag im Bericht:
# Spalte kommunikation_log.graph_conversation_id für v30):
#   Bounce: Original-Empfänger aus Kopfzeilen/Text (im Testmodus die echte
#           Adresse aus dem Betreff-Präfix „[TEST an …]“) → jüngster gesendeter
#           Eintrag an diese Adresse (Betreff bevorzugt) → Vorgang; sonst Kunde
#           mit dieser E-Mail → jüngster Vorgang.
#   Antwort: Absenderadresse → gesendeter Eintrag an diese Adresse → Vorgang;
#           Betreff „Rückruf V<Nr>“; sonst Kunde mit dieser E-Mail.
# Nicht zuordenbare Nachrichten landen in „Posteingang unklar“ (LeadPosteingang,
# status offen). Im Demo-Modus (lead_freigabe_modus = admin) werden nur
# Nachrichten verarbeitet, die zu Demo-Leads gehören – alles andere bleibt
# ungelesen liegen [ANNAHME: „im Demo-Modus Testpostfach“ = nur Testverkehr
# der Demo-Leads, echte Leads werden im Demo nie verändert].
#
# Erkennung eines Bounces: Absender postmaster@/MAILER-DAEMON/Exchange-System-
# adresse oder Betreff „Unzustellbar“/„Undeliverable“/„Delivery Status
# Notification (Failure)“/„Delivery has failed“/„Nicht zugestellt“; reine
# Verzögerungsmeldungen (delay/verzögert) zählen nicht.

import html as html_modul
import logging
import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import KommunikationLog, Kunde, LeadPosteingang, Vorgang

_logger = logging.getLogger("angebotstool")

INTERVALL_S = 120
START_VERZOEGERUNG_S = 270
BLOCK_GROESSE = 50
NICHT_ANGEMELDET = "Nicht bei Microsoft angemeldet"

NDR_ABSENDER = ("postmaster@", "mailer-daemon@", "microsoftexchange", "noreply@mail.")
NDR_BETREFF = ("unzustellbar", "undeliverable", "delivery status notification",
               "delivery has failed", "nicht zugestellt", "mail delivery failed",
               "zustellung fehlgeschlagen", "delivery failure", "returned mail")
NDR_KEIN_BOUNCE = ("delay", "verzöger", "delayed")
_ADRESSE = re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+", re.UNICODE)
_BETREFF_PRAEFIXE = re.compile(
    r"^\s*(?:(?:aw|re|wg|fw|fwd|antw|unzustellbar|undeliverable|nicht zugestellt)\s*:\s*)+",
    re.IGNORECASE)
_TEST_PRAEFIX = re.compile(r"\[TEST an ([^\]\s]+)\]", re.IGNORECASE)


# --- Erkennung und Normalisierung ----------------------------------------------------

def html_zu_text(inhalt: str) -> str:
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", inhalt or "")
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return html_modul.unescape(text)


def ist_ndr(absender: str, betreff: str) -> bool:
    a = (absender or "").strip().lower()
    b = (betreff or "").strip().lower()
    if any(t in b for t in NDR_KEIN_BOUNCE) and not any(t in b for t in ("fail", "fehl")):
        return False
    return (any(a.startswith(p) or p in a for p in NDR_ABSENDER)
            or any(b.startswith(p) or p in b for p in NDR_BETREFF))


def betreff_normal(betreff: str) -> str:
    """Betreff ohne AW:/RE:/Unzustellbar:-Präfixe und [TEST an …], klein."""
    text = _TEST_PRAEFIX.sub("", betreff or "")
    text = _BETREFF_PRAEFIXE.sub("", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def test_praefix_adresse(betreff: str) -> str:
    """Im Testmodus trägt die Tool-Mail „[TEST an <Kundenadresse>]“ im Betreff –
    der Bounce/die Antwort zitiert ihn; daraus die echte Adresse holen."""
    treffer = _TEST_PRAEFIX.search(betreff or "")
    return treffer.group(1).strip().lower() if treffer else ""


def ndr_empfaenger(text: str, kopfzeilen: dict | None, eigene: set[str]) -> str:
    """Original-Empfänger eines Unzustellbarkeitsberichts: Kopfzeile
    X-MS-Exchange-…/Original-Recipient, sonst Muster im Text („an x@y konnte
    nicht zugestellt werden“, „Delivery has failed to these recipients: x@y“),
    sonst die erste fremde Adresse im Text."""
    kopfzeilen = kopfzeilen or {}
    for name in ("x-ms-exchange-original-recipient", "original-recipient", "final-recipient"):
        wert = kopfzeilen.get(name, "")
        treffer = _ADRESSE.search(wert or "")
        if treffer and treffer.group(0).lower() not in eigene:
            return treffer.group(0).lower()
    text = text or ""
    muster = [r"(?:an|to)\s+<?([\w.+'-]+@[\w-]+(?:\.[\w-]+)+)>?\s+(?:konnte|could|was|wurde)",
              r"recipients?(?: or groups)?\s*:?\s*<?([\w.+'-]+@[\w-]+(?:\.[\w-]+)+)>?",
              r"empf[äa]nger[^\n]*?:\s*<?([\w.+'-]+@[\w-]+(?:\.[\w-]+)+)>?",
              r"mailto:([\w.+'-]+@[\w-]+(?:\.[\w-]+)+)"]
    for m in muster:
        for treffer in re.finditer(m, text, re.IGNORECASE):
            adresse = treffer.group(1).lower().rstrip(".")
            if adresse not in eigene:
                return adresse
    for treffer in _ADRESSE.finditer(text):
        adresse = treffer.group(0).lower().rstrip(".")
        if adresse not in eigene and not adresse.startswith(("postmaster@", "mailer-daemon@")):
            return adresse
    return ""


# --- Zuordnung ------------------------------------------------------------------------

def eintrag_finden(session: Session, adresse: str, betreff: str = "") -> KommunikationLog | None:
    """Jüngster gesendeter (oder protokollierter) Warteschlangen-Eintrag an die
    Adresse; bei mehreren bevorzugt der mit passendem Betreff."""
    adresse = (adresse or "").strip().lower()
    if not adresse:
        return None
    kandidaten = (session.query(KommunikationLog)
                  .filter(KommunikationLog.an.ilike(adresse),
                          KommunikationLog.status.in_(("gesendet", "protokolliert", "fehler")))
                  .order_by(KommunikationLog.id.desc()).limit(25).all())
    if not kandidaten:
        return None
    gesucht = betreff_normal(betreff)
    if gesucht:
        for e in kandidaten:
            eigener = betreff_normal(e.betreff)
            if eigener and (eigener in gesucht or gesucht in eigener):
                return e
    return kandidaten[0]


def vorgang_zu_adresse(session: Session, adresse: str) -> Vorgang | None:
    adresse = (adresse or "").strip().lower()
    if not adresse:
        return None
    kunden = [k.id for k in session.query(Kunde.id).filter(Kunde.email.ilike(adresse))]
    if not kunden:
        return None
    return (session.query(Vorgang).filter(Vorgang.kunde_id.in_(kunden))
            .order_by(Vorgang.id.desc()).first())


def _nachricht_felder(nachricht: dict) -> tuple[str, str, str, str, datetime | None]:
    graph_id = nachricht.get("id", "") or ""
    absender = ((nachricht.get("from") or {}).get("emailAddress") or {}).get("address", "") or ""
    betreff = nachricht.get("subject", "") or ""
    body = nachricht.get("body") or {}
    inhalt = body.get("content", "") if isinstance(body, dict) else str(body or "")
    if (isinstance(body, dict) and str(body.get("contentType", "")).lower() == "html") \
            or re.search(r"<[a-z][^>]*>", inhalt or ""):
        inhalt = html_zu_text(inhalt)
    empfangen = None
    roh = nachricht.get("receivedDateTime") or ""
    if roh:
        try:
            empfangen = datetime.fromisoformat(roh.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            empfangen = None
    return graph_id, absender.strip(), betreff, inhalt or "", empfangen


def nachricht_verarbeiten(session: Session, nachricht: dict, *, demo: bool,
                          eigene: set[str], kopfzeilen: dict | None = None) -> str:
    """Eine Nachricht → bounce | antwort | unklar | bekannt | uebersprungen.
    `uebersprungen` = im Demo-Modus kein Demo-Lead (bleibt ungelesen)."""
    from app import lead_mail
    graph_id, absender, betreff, text, empfangen = _nachricht_felder(nachricht)
    if not graph_id:
        return "uebersprungen"
    if session.query(LeadPosteingang).filter(LeadPosteingang.graph_id == graph_id).count():
        return "bekannt"
    if ist_ndr(absender, betreff):
        adresse = ndr_empfaenger(text, kopfzeilen, eigene | {absender.lower()})
        echte = test_praefix_adresse(betreff) or test_praefix_adresse(text) or adresse
        eintrag = eintrag_finden(session, echte, betreff)
        vorgang = session.get(Vorgang, eintrag.vorgang_id) if eintrag is not None else None
        if vorgang is None:
            vorgang = vorgang_zu_adresse(session, echte)
        if vorgang is None:
            if demo:
                return "uebersprungen"
            session.add(LeadPosteingang(graph_id=graph_id, absender=absender,
                                        betreff=betreff[:300], body=text[:8000],
                                        empfangen_am=empfangen, status="offen"))
            session.flush()
            return "unklar"
        if demo and not vorgang.demo:
            return "uebersprungen"
        grund = betreff_normal(betreff)[:120] or "Unzustellbarkeitsbericht"
        lead_mail.bounce_verbuchen(session, vorgang, echte or (eintrag.an if eintrag else ""),
                                   f"Unzustellbar – {grund}", eintrag)
        session.add(LeadPosteingang(graph_id=graph_id, absender=absender,
                                    betreff=betreff[:300], body=text[:8000],
                                    empfangen_am=empfangen, status="angelegt",
                                    vorgang_id=vorgang.id))
        session.flush()
        return "bounce"
    # Kundenantwort
    adresse = absender.lower()
    eintrag = eintrag_finden(session, adresse, betreff)
    vorgang = session.get(Vorgang, eintrag.vorgang_id) if eintrag is not None else None
    if vorgang is None:
        treffer = re.search(r"Rückruf\s+V(\d+)", betreff or "", re.IGNORECASE)
        if treffer:
            vorgang = session.get(Vorgang, int(treffer.group(1)))
    if vorgang is None:
        vorgang = vorgang_zu_adresse(session, adresse)
    if vorgang is None:
        if demo:
            return "uebersprungen"
        session.add(LeadPosteingang(graph_id=graph_id, absender=absender,
                                    betreff=betreff[:300], body=text[:8000],
                                    empfangen_am=empfangen, status="offen"))
        session.flush()
        return "unklar"
    if demo and not vorgang.demo:
        return "uebersprungen"
    lead_mail.kundenantwort_verbuchen(session, vorgang, absender, betreff, text,
                                      graph_id=graph_id, empfangen_am=empfangen)
    return "antwort"


# --- Scheduler-Lauf ------------------------------------------------------------------

def graph_aktiv():
    """aktiv-Bedingung: Graph in der .env eingerichtet (GRAPH_CLIENT_ID)."""
    from app import graph_versand
    return True if graph_versand.konfiguriert() else "Graph nicht eingerichtet"


def scheduler_lauf() -> dict:
    """Ein Abruf: Parameter (kurze Sitzung) → Token + Posteingang ohne Sitzung →
    je Nachricht kurze Sitzung mit Commit → isRead ohne Sitzung. Fehler des
    Postfach-Abrufs werden hochgeworfen (Datei-Log, Betriebs-Seite); „nicht
    angemeldet“ ist ein Zustand, kein Fehler."""
    from app import graph_versand, lead_mail
    from app import leadmanagement as kern
    from app.db import kurz
    with kurz() as s:
        postfach = lead_mail.absender(s)
        demo = kern.demo_aktiv(s)
    # eigene Adressen (werden als Original-Empfänger eines Bounces ausgeschlossen);
    # die Testadresse gehört bewusst NICHT dazu – im Testmodus ist sie der
    # Empfänger, die echte Kundenadresse steht im Betreff-Präfix [TEST an …]
    eigene = {postfach.lower()}
    token = graph_versand._token()
    if token is None:
        return {"ergebnis": NICHT_ANGEMELDET}
    nachrichten = graph_versand.postfach_ungelesen(token, postfach, top=BLOCK_GROESSE)
    zaehler = {"bounce": 0, "antwort": 0, "unklar": 0, "bekannt": 0, "uebersprungen": 0,
               "gelesen": len(nachrichten)}
    for nachricht in nachrichten:
        ergebnis = "uebersprungen"
        try:
            with kurz() as s:
                ergebnis = nachricht_verarbeiten(s, nachricht, demo=demo, eigene=eigene)
        except Exception as problem:
            _logger.error("lead-mail-abruf: Nachricht %s nicht verarbeitet: %s",
                          nachricht.get("id", "?"), problem, exc_info=True)
            zaehler["fehler"] = zaehler.get("fehler", 0) + 1
            continue
        zaehler[ergebnis] = zaehler.get(ergebnis, 0) + 1
        if ergebnis != "uebersprungen":
            graph_versand.nachricht_gelesen_markieren(token, postfach, nachricht.get("id", ""))
    return zaehler


def scheduler_starten() -> None:
    """Registriert den 2-Minuten-Lauf am Scheduler-Rahmen (aktiv nur mit
    eingerichtetem Graph; im Demo-Modus nur Testverkehr der Demo-Leads);
    Threads startet main.lifespan über scheduler.starten_alle()."""
    from app import scheduler
    scheduler.registrieren(
        "lead-mail-abruf", INTERVALL_S, scheduler_lauf,
        beschreibung="Antworten und Unzustellbarkeitsberichte aus dem Lead-Absender-Postfach "
                     "(termin@) abrufen und dem Vorgang zuordnen",
        start_verzoegerung_s=START_VERZOEGERUNG_S, aktiv=graph_aktiv)
