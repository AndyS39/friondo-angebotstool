# Mail-Verlauf am Angebot (Phase 27): ruft alle 15 Minuten die Nachrichten der
# Angebots-Konversation über Microsoft Graph ab (nur lesend, delegiertes Token
# aus graph_versand). Zuordnung primär über die beim Versand gespeicherte
# conversationId; Fallback für ältere Angebote: Betreff enthält die AN-C-Nummer.

import json
import threading
import urllib.parse
import urllib.request
from datetime import datetime

from app.db import SessionLocal
from app.models import Angebot, AngebotsMail

SYNC_INTERVALL_SEKUNDEN = 15 * 60
GRAPH = "https://graph.microsoft.com/v1.0"
FELDER = "id,conversationId,subject,from,receivedDateTime,bodyPreview"

status: dict = {"letzter_lauf": None, "neu": 0, "fehler": []}


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


def nachrichten_je_konversation(token: str, conversation_id: str) -> list[dict]:
    filter_ = urllib.parse.quote(f"conversationId eq '{conversation_id}'")
    daten = _graph_get(f"/me/messages?$filter={filter_}"
                       f"&$select={FELDER}&$top=50", token)
    return daten.get("value", [])


def nachrichten_je_betreff(token: str, nummer: str) -> list[dict]:
    """Fallback ohne gespeicherte conversationId: Suche nach der AN-C-Nummer."""
    suche = urllib.parse.quote(f'"{nummer}"')
    daten = _graph_get(f"/me/messages?$search={suche}"
                       f"&$select={FELDER}&$top=50", token)
    return daten.get("value", [])


def nachrichten_verarbeiten(session, angebot: Angebot, nachrichten: list[dict],
                            eigenes_postfach: str) -> int:
    """Übernimmt neue Nachrichten in angebots_mails (Dedup über graph_id).
    Liefert die Zahl neu gespeicherter Nachrichten. Vom Scheduler und von den
    Tests (mit Mock-Daten) gemeinsam genutzt."""
    vorhanden = {m.graph_id for m in
                 session.query(AngebotsMail.graph_id)
                 .filter(AngebotsMail.angebot_id == angebot.id)}
    eigenes = (eigenes_postfach or "").lower()
    neu = 0
    for nachricht in nachrichten:
        graph_id = nachricht.get("id") or ""
        if not graph_id or graph_id in vorhanden:
            continue
        absender = (nachricht.get("from") or {}).get("emailAddress") or {}
        von_email = absender.get("address") or ""
        # Konversation kann ohne conversationId-Filter (Betreff-Suche) auch
        # Fremdtreffer liefern – die eigene Konversation sichern, falls bekannt
        if (angebot.graph_conversation_id
                and nachricht.get("conversationId")
                and nachricht["conversationId"] != angebot.graph_conversation_id):
            continue
        session.add(AngebotsMail(
            angebot_id=angebot.id,
            graph_id=graph_id,
            von_name=absender.get("name") or "",
            von_email=von_email,
            empfangen_am=_zeit_parsen(nachricht.get("receivedDateTime") or ""),
            betreff=nachricht.get("subject") or "",
            vorschau=nachricht.get("bodyPreview") or "",
            eingehend=bool(von_email) and von_email.lower() != eigenes,
        ))
        vorhanden.add(graph_id)
        neu += 1
    return neu


def sync() -> int:
    """Ein Abruflauf über alle versendeten/angenommenen Angebote."""
    from app import graph_versand

    token = graph_versand._token()
    postfach = graph_versand.angemeldeter_benutzer() or ""
    if token is None:
        return 0
    session = SessionLocal()
    neu_gesamt = 0
    fehler: list[str] = []
    try:
        angebote = (session.query(Angebot)
                    .filter(Angebot.status.in_(["Versendet", "Angenommen",
                                                "Abgelehnt"]),
                            Angebot.archiviert.is_(False))
                    .all())
        for angebot in angebote:
            try:
                if angebot.graph_conversation_id:
                    nachrichten = nachrichten_je_konversation(
                        token, angebot.graph_conversation_id)
                else:
                    nachrichten = nachrichten_je_betreff(token, angebot.nummer)
                neu_gesamt += nachrichten_verarbeiten(session, angebot,
                                                      nachrichten, postfach)
            except Exception as problem:
                fehler.append(f"{angebot.nummer}: {problem}")
        session.commit()
    finally:
        session.close()
    status.update(letzter_lauf=datetime.now(), neu=neu_gesamt, fehler=fehler)
    return neu_gesamt


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
                    status["fehler"] = [f"Mail-Abruf fehlgeschlagen: {problem}"]
            time.sleep(SYNC_INTERVALL_SEKUNDEN)

    threading.Thread(target=schleife, daemon=True).start()
