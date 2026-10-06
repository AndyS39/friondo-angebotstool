# Mail-Abgleich (Phase 27/31): alle 15 Minuten über Microsoft Graph, nur lesend.
#  1) Versand-Erkennung: Angebote im Status „Versand vorbereitet“ – taucht in der
#     Konversation der Angebots-Mail eine GESENDETE Nachricht (kein Entwurf) auf,
#     springt der Status automatisch auf „Versendet“ (löst die monday-Rück-
#     spielung aus, Phase 32).
#  2) Mail-Verlauf: Nachrichten der Konversation (Antworten des Kunden) werden
#     dem Angebot zugeordnet; Fallback ohne conversationId: Betreff mit AN-C-Nr.
# Postfach: das Versand-Postfach angebot@friondo.de (Parametrierung
# mail_postfach; leer = eigenes Postfach /me). Delegiertes Token aus graph_versand.
# v27 (PLAN_V17 Phase 128): der 15-Minuten-Lauf ist am Scheduler-Rahmen
# registriert (aktiv nur mit eingerichtetem Graph); sync() liest in einer kurzen
# Sitzung, ruft Graph OHNE Sitzung und schreibt je Angebot in einer kurzen
# Sitzung mit Commit zurück. Die vier Teilschritte (Mail-Abgleich, Sub-
# Antworten, Outlook-Rücklauf, Terminantworten) sind je für sich abgesichert.

import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime

from app.models import Angebot, AngebotsMail, einstellung_holen

_logger = logging.getLogger("angebotstool")

SYNC_INTERVALL_SEKUNDEN = 15 * 60
GRAPH = "https://graph.microsoft.com/v1.0"
FELDER = "id,conversationId,subject,from,receivedDateTime,sentDateTime,bodyPreview,isDraft"

status: dict = {"letzter_lauf": None, "neu": 0, "versendet": 0, "fehler": []}


def _graph_get(pfad: str, token: str) -> dict:
    anfrage = urllib.request.Request(
        GRAPH + pfad,
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(anfrage, timeout=60) as antwort:   # v22: Timeout
        return json.loads(antwort.read())


def _zeit_parsen(wert: str) -> datetime | None:
    """Graph liefert z. B. 2026-08-14T09:30:00Z."""
    if not wert:
        return None
    try:
        return datetime.fromisoformat(wert.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _basis(postfach: str) -> str:
    """Graph-Pfadbasis: Shared Mailbox angebot@ oder eigenes Postfach."""
    return f"/users/{urllib.parse.quote(postfach)}" if postfach else "/me"


def nachrichten_je_konversation(token: str, conversation_id: str,
                                postfach: str = "") -> list[dict]:
    filter_ = urllib.parse.quote(f"conversationId eq '{conversation_id}'")
    daten = _graph_get(f"{_basis(postfach)}/messages?$filter={filter_}"
                       f"&$select={FELDER}&$top=50", token)
    return daten.get("value", [])


def nachrichten_je_betreff(token: str, nummer: str, postfach: str = "") -> list[dict]:
    """Fallback ohne gespeicherte conversationId: Suche nach der AN-C-Nummer."""
    suche = urllib.parse.quote(f'"{nummer}"')
    daten = _graph_get(f"{_basis(postfach)}/messages?$search={suche}"
                       f"&$select={FELDER}&$top=50", token)
    return daten.get("value", [])


def _eigene_adressen(*adressen: str) -> set[str]:
    return {a.lower() for a in adressen if a}


def versand_erkennen(session, angebot: Angebot, nachrichten: list[dict],
                     eigene: set[str], protokoll: list | None = None) -> bool:
    """Phase 31: Liegt in der Konversation eine gesendete (nicht-Entwurf)
    Nachricht von uns vor? Dann Status „Versendet“ setzen. True = umgestellt.
    v11 (AN-C-261083): jeder Prüflauf wird protokolliert – auch WARUM eine
    Mail nicht als Versand zählte (Entwurf, fremder Absender, kein Sendedatum)."""
    if angebot.status != "Versand vorbereitet":
        return False

    def merken(ergebnis: str) -> None:
        if protokoll is not None:
            protokoll.append({
                "zeit": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "angebot": angebot.nummer,
                "nachrichten": len(nachrichten),
                "ergebnis": ergebnis})

    if not nachrichten:
        merken("keine Nachrichten zur Konversation/Nummer gefunden")
        return False
    gruende = []
    for n in nachrichten:
        absender = ((n.get("from") or {}).get("emailAddress") or {}).get("address", "")
        if n.get("isDraft"):
            gruende.append(f"{absender or '?'}: noch Entwurf")
            continue
        if not n.get("sentDateTime"):
            gruende.append(f"{absender or '?'}: kein Sendedatum")
            continue
        if not absender or absender.lower() not in eigene:
            gruende.append(f"{absender or '?'}: nicht als eigene Adresse erkannt")
            continue
        from app.models import angebot_status_setzen
        angebot_status_setzen(angebot, "Versendet")
        # Prozess-Fix 27.09.2026: Lead-Phase mitziehen (Pipeline zeigte
        # sonst nach automatisch erkanntem Versand weiter "erfasst")
        try:
            from app import leadmanagement
            leadmanagement.phase_neu_berechnen(session, angebot.vorgang_id)
        except Exception:
            pass
        merken(f"als versendet erkannt (Absender {absender})")
        return True
    merken("nicht erkannt – " + "; ".join(gruende[:4]))
    return False


def nachrichten_verarbeiten(session, angebot: Angebot, nachrichten: list[dict],
                            eigenes_postfach: str | set[str]) -> int:
    """Übernimmt neue Nachrichten in angebots_mails (Dedup über graph_id);
    Entwürfe werden nicht gespeichert. Liefert die Zahl neuer Nachrichten."""
    vorhanden = {m.graph_id for m in
                 session.query(AngebotsMail.graph_id)
                 .filter(AngebotsMail.angebot_id == angebot.id)}
    eigene = (_eigene_adressen(eigenes_postfach) if isinstance(eigenes_postfach, str)
              else {a.lower() for a in eigenes_postfach})
    neu = 0
    for nachricht in nachrichten:
        graph_id = nachricht.get("id") or ""
        if not graph_id or graph_id in vorhanden or nachricht.get("isDraft"):
            continue
        absender = (nachricht.get("from") or {}).get("emailAddress") or {}
        von_email = absender.get("address") or ""
        # Betreff-Suche kann Fremdtreffer liefern – bekannte Konversation sichern
        if (angebot.graph_conversation_id
                and nachricht.get("conversationId")
                and nachricht["conversationId"] != angebot.graph_conversation_id):
            continue
        session.add(AngebotsMail(
            angebot_id=angebot.id,
            graph_id=graph_id,
            von_name=absender.get("name") or "",
            von_email=von_email,
            empfangen_am=_zeit_parsen(nachricht.get("receivedDateTime")
                                      or nachricht.get("sentDateTime") or ""),
            betreff=nachricht.get("subject") or "",
            vorschau=nachricht.get("bodyPreview") or "",
            eingehend=bool(von_email) and von_email.lower() not in eigene,
        ))
        vorhanden.add(graph_id)
        neu += 1
    return neu


def sync() -> int:
    """Ein Abgleichlauf: Versand-Erkennung + Mail-Verlauf über alle offenen
    Angebote (nicht archiviert). v27 (PLAN_V17 Phase 128): Token und Konto vor
    jeder Sitzung; Lesephase (Postfach, eigene Adressen, Angebotsliste) in
    einer kurzen Sitzung; je Angebot der Graph-Abruf OHNE Sitzung und danach
    eine kurze Sitzung zum Zurückschreiben mit Commit (Block = ein Angebot);
    das Erkennungs-Protokoll zum Schluss in einer kurzen Sitzung."""
    from app import graph_versand
    from app.db import kurz

    token = graph_versand._token()
    if token is None:
        return 0
    konto = graph_versand.angemeldeter_benutzer() or ""
    neu_gesamt = versendet_gesamt = 0
    fehler: list[str] = []
    erkennungs_protokoll: list[dict] = []
    with kurz() as s:
        postfach = einstellung_holen(s, "mail_postfach", "angebot@friondo.de")
        absender = einstellung_holen(s, "mail_absender", "angebot@friondo.de")
        eigene = _eigene_adressen(konto, postfach, absender)
        # v11 (AN-C-261083): Auch die Postfächer der Benutzer zählen als eigene
        # Absender – „Senden im Auftrag“ trägt sonst die persönliche Adresse
        # und der Versand wurde nie erkannt.
        from app.models import Benutzer
        for b in s.query(Benutzer).filter(Benutzer.aktiv.is_(True)):
            if b.email:
                eigene.add(b.email.lower())
        angebote = [(z[0], z[1], z[2]) for z in
                    s.query(Angebot.id, Angebot.nummer, Angebot.graph_conversation_id)
                    .filter(Angebot.status.in_(["Versand vorbereitet", "Versendet",
                                                "Angenommen", "Abgelehnt"]),
                            Angebot.archiviert.is_(False))
                    .order_by(Angebot.id).all()]
    for angebot_id, nummer, conversation_id in angebote:
        try:
            if conversation_id:
                nachrichten = nachrichten_je_konversation(token, conversation_id, postfach)
            else:
                nachrichten = nachrichten_je_betreff(token, nummer, postfach)
            with kurz() as s:
                angebot = s.get(Angebot, angebot_id)
                if angebot is None or angebot.archiviert:
                    continue   # inzwischen archiviert/gelöscht
                if versand_erkennen(s, angebot, nachrichten, eigene,
                                    erkennungs_protokoll):
                    versendet_gesamt += 1
                    s.commit()
                    _nach_versand(s, angebot)
                neu_gesamt += nachrichten_verarbeiten(s, angebot, nachrichten, eigene)
        except Exception as problem:
            fehler.append(f"{nummer}: {problem}")
    with kurz() as s:
        _protokoll_sichern(s, erkennungs_protokoll)
    status.update(letzter_lauf=datetime.now(), neu=neu_gesamt,
                  versendet=versendet_gesamt, fehler=fehler,
                  erkennung=erkennungs_protokoll)
    return neu_gesamt


def _protokoll_sichern(session, eintraege: list[dict]) -> None:
    """v11: Erkennungs-Protokoll persistent halten (letzte 50 Einträge) –
    einsehbar in der Parametrierung, überlebt Neustarts."""
    if not eintraege:
        return
    from app.models import einstellung_setzen
    try:
        alt = json.loads(einstellung_holen(session, "versand_erkennung_protokoll", "[]"))
    except ValueError:
        alt = []
    einstellung_setzen(session, "versand_erkennung_protokoll",
                       json.dumps((alt + eintraege)[-50:], ensure_ascii=False))
    session.commit()


def _nach_versand(session, angebot: Angebot) -> None:
    """Folgeaktionen nach automatisch erkanntem Versand: Erfassung erledigt,
    monday-Rückspielung (Phase 32) – Fehler blockieren nie."""
    from app.models import Erfassung
    for erfassung in session.query(Erfassung).filter(Erfassung.angebot_id == angebot.id):
        erfassung.status = "Erledigt"
    session.commit()
    try:
        from app import monday_rueckspielung
        monday_rueckspielung.bei_versand(session, angebot)
    except Exception as problem:   # Modul fehlt oder Rückspielung schlägt fehl
        status.setdefault("fehler", []).append(f"monday {angebot.nummer}: {problem}")


# --- Hintergrund-Scheduler (alle 15 Minuten, v27 am Rahmen registriert) ------

def graph_aktiv():
    """aktiv-Bedingung des Laufs: Graph in der .env eingerichtet (GRAPH_CLIENT_ID)."""
    from app import graph_versand
    return True if graph_versand.konfiguriert() else "Graph nicht eingerichtet"


def _sub_antworten() -> int:
    from app import sub_mail                      # v15 (Phase 79): Antworten auf Sub-Anfragen
    return sub_mail.antworten_abgleichen()


def _outlook_ruecklauf() -> int:
    from app import outlook_kalender              # v15 (Phase 81): Outlook → Tool
    return outlook_kalender.ruecklesen()


def _terminantworten() -> int:
    from app import terminmail                    # v15 (Phase 81): Kunden-Terminantworten
    return terminmail.antworten_abgleichen()


def scheduler_lauf() -> dict:
    """15-Minuten-Lauf: Mail-Abgleich, Sub-Antworten, Outlook-Rücklauf,
    Terminantworten – jeder Teilschritt für sich abgesichert (ein Fehler
    blockiert die anderen nicht). v27 (PLAN_V17 Phase 128): Fehler werden nicht
    mehr verschluckt, sondern im Rückgabe-dict genannt (fehler = Anzahl,
    hinweis = erster Fehler), im Datei-Log protokolliert und – wenn ALLE vier
    Teilschritte scheiterten – als Ausnahme hochgeworfen (Lauf = fehler)."""
    schritte = (("mail-abgleich", "Mail-Abgleich fehlgeschlagen", sync),
                ("sub-antworten", "Sub-Antworten fehlgeschlagen", _sub_antworten),
                ("outlook-ruecklauf", "Outlook-Rücklauf fehlgeschlagen", _outlook_ruecklauf),
                ("terminantworten", "Terminantworten fehlgeschlagen", _terminantworten))
    ergebnis: dict = {}
    fehler: list[str] = []
    for name, meldung, funktion in schritte:
        try:
            ergebnis[name] = funktion()
        except Exception as problem:
            text = f"{meldung}: {type(problem).__name__}: {problem}"[:300]
            fehler.append(text)
            _logger.error("Mail-Sync – Teilschritt %s: %s", name, text, exc_info=True)
            if name == "mail-abgleich":
                status["fehler"] = [text]            # wie bisher: Anzeige in der Parametrierung
            else:
                status.setdefault("fehler", []).append(text)
    if fehler:
        ergebnis["fehler"] = fehler
        ergebnis["hinweis"] = fehler[0][:120]
        if len(fehler) == len(schritte):
            raise RuntimeError("Alle Teilschritte fehlgeschlagen – " + "; ".join(fehler)[:450])
    return ergebnis


def scheduler_starten() -> None:
    """v27 (PLAN_V17 Phase 128): registriert den 15-Minuten-Lauf nur noch am
    Scheduler-Rahmen (aktiv nur mit eingerichtetem Graph); Threads startet
    main.lifespan über scheduler.starten_alle()."""
    from app import scheduler
    scheduler.registrieren(
        "mail-sync", SYNC_INTERVALL_SEKUNDEN, scheduler_lauf,
        beschreibung="Graph-Mailabgleich: Versand-Erkennung, Mail-Verlauf, Sub-/Terminantworten, "
                     "Outlook-Rücklauf",
        aktiv=graph_aktiv)
