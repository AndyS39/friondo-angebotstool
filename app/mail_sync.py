# Mail-Abgleich (Phase 27/31): alle 15 Minuten über Microsoft Graph, nur lesend.
#  1) Versand-Erkennung: Angebote im Status „Versand vorbereitet“ – taucht in der
#     Konversation der Angebots-Mail eine GESENDETE Nachricht (kein Entwurf) auf,
#     springt der Status automatisch auf „Versendet“ (löst die monday-Rück-
#     spielung aus, Phase 32).
#  2) Mail-Verlauf: Nachrichten der Konversation (Antworten des Kunden) werden
#     dem Angebot zugeordnet; Fallback ohne conversationId: Betreff mit AN-C-Nr.
# Postfach: das Versand-Postfach angebot@friondo.de (Parametrierung
# mail_postfach; leer = eigenes Postfach /me). Delegiertes Token aus graph_versand.

import json
import threading
import urllib.parse
import urllib.request
from datetime import datetime

from app.db import SessionLocal
from app.models import Angebot, AngebotsMail, einstellung_holen

SYNC_INTERVALL_SEKUNDEN = 15 * 60
GRAPH = "https://graph.microsoft.com/v1.0"
FELDER = "id,conversationId,subject,from,receivedDateTime,sentDateTime,bodyPreview,isDraft"

status: dict = {"letzter_lauf": None, "neu": 0, "versendet": 0, "fehler": []}


def _graph_get(pfad: str, token: str) -> dict:
    anfrage = urllib.request.Request(
        GRAPH + pfad,
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(anfrage) as antwort:
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
                     eigene: set[str]) -> bool:
    """Phase 31: Liegt in der Konversation eine gesendete (nicht-Entwurf)
    Nachricht von uns vor? Dann Status „Versendet“ setzen. True = umgestellt."""
    if angebot.status != "Versand vorbereitet":
        return False
    for n in nachrichten:
        if n.get("isDraft"):
            continue
        absender = ((n.get("from") or {}).get("emailAddress") or {}).get("address", "")
        if absender and absender.lower() in eigene and n.get("sentDateTime"):
            from app.models import angebot_status_setzen
            angebot_status_setzen(angebot, "Versendet")
            return True
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
    Angebote (nicht archiviert)."""
    from app import graph_versand

    token = graph_versand._token()
    if token is None:
        return 0
    konto = graph_versand.angemeldeter_benutzer() or ""
    session = SessionLocal()
    neu_gesamt = versendet_gesamt = 0
    fehler: list[str] = []
    try:
        postfach = einstellung_holen(session, "mail_postfach", "angebot@friondo.de")
        absender = einstellung_holen(session, "mail_absender", "angebot@friondo.de")
        eigene = _eigene_adressen(konto, postfach, absender)
        angebote = (session.query(Angebot)
                    .filter(Angebot.status.in_(["Versand vorbereitet", "Versendet",
                                                "Angenommen", "Abgelehnt"]),
                            Angebot.archiviert.is_(False))
                    .all())
        for angebot in angebote:
            try:
                if angebot.graph_conversation_id:
                    nachrichten = nachrichten_je_konversation(
                        token, angebot.graph_conversation_id, postfach)
                else:
                    nachrichten = nachrichten_je_betreff(token, angebot.nummer, postfach)
                if versand_erkennen(session, angebot, nachrichten, eigene):
                    versendet_gesamt += 1
                    session.commit()
                    _nach_versand(session, angebot)
                neu_gesamt += nachrichten_verarbeiten(session, angebot, nachrichten, eigene)
            except Exception as problem:
                fehler.append(f"{angebot.nummer}: {problem}")
        session.commit()
    finally:
        session.close()
    status.update(letzter_lauf=datetime.now(), neu=neu_gesamt,
                  versendet=versendet_gesamt, fehler=fehler)
    return neu_gesamt


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


# --- Hintergrund-Scheduler (alle 15 Minuten) ------------------------------

_scheduler_gestartet = False


def scheduler_starten() -> None:
    global _scheduler_gestartet
    if _scheduler_gestartet:
        return
    _scheduler_gestartet = True

    def schleife():
        import time
        from app import graph_versand
        while True:
            if graph_versand.konfiguriert():
                try:
                    sync()
                except Exception as problem:   # nie durchschlagen lassen
                    status["fehler"] = [f"Mail-Abgleich fehlgeschlagen: {problem}"]
            time.sleep(SYNC_INTERVALL_SEKUNDEN)

    threading.Thread(target=schleife, daemon=True).start()
