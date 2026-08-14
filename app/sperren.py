# Einfache Bearbeitungssperre für den Angebots-Editor: Öffnet ein Benutzer
# ein Angebot, sehen andere den Hinweis „Wird gerade von X bearbeitet" und
# können nur lesen. Die Sperre lebt im Arbeitsspeicher (ein Serverprozess),
# läuft ohne Verlängerung nach TTL_SEKUNDEN ab und wird vom offenen Editor
# alle 2 Minuten per Heartbeat verlängert; ein Neustart räumt alles auf.

import threading
import time

TTL_SEKUNDEN = 5 * 60

_schutz = threading.Lock()
_sperren: dict[int, dict] = {}   # angebot_id -> {benutzer_id, name, zeit}


def _abgelaufen(eintrag: dict) -> bool:
    return time.monotonic() - eintrag["zeit"] > TTL_SEKUNDEN


def erwerben(angebot_id: int, benutzer_id: int, name: str) -> dict | None:
    """Sperre holen bzw. die eigene verlängern. Liefert None bei Erfolg,
    sonst {benutzer_id, name} des Benutzers, der das Angebot gerade hält."""
    with _schutz:
        eintrag = _sperren.get(angebot_id)
        if eintrag is not None and not _abgelaufen(eintrag) \
                and eintrag["benutzer_id"] != benutzer_id:
            return {"benutzer_id": eintrag["benutzer_id"], "name": eintrag["name"]}
        _sperren[angebot_id] = {"benutzer_id": benutzer_id, "name": name,
                                "zeit": time.monotonic()}
        return None


def inhaber(angebot_id: int) -> dict | None:
    """Aktiver Sperrinhaber oder None (abgelaufene Einträge zählen nicht)."""
    with _schutz:
        eintrag = _sperren.get(angebot_id)
        if eintrag is None or _abgelaufen(eintrag):
            return None
        return {"benutzer_id": eintrag["benutzer_id"], "name": eintrag["name"]}


def verlaengern(angebot_id: int, benutzer_id: int) -> bool:
    """Heartbeat des offenen Editors; nur der Inhaber kann verlängern."""
    with _schutz:
        eintrag = _sperren.get(angebot_id)
        if eintrag is None or _abgelaufen(eintrag) \
                or eintrag["benutzer_id"] != benutzer_id:
            return False
        eintrag["zeit"] = time.monotonic()
        return True


def freigeben(angebot_id: int, benutzer_id: int) -> None:
    """Sperre freigeben (beim Verlassen der Seite); nur die eigene."""
    with _schutz:
        eintrag = _sperren.get(angebot_id)
        if eintrag is not None and eintrag["benutzer_id"] == benutzer_id:
            del _sperren[angebot_id]


def gesperrt_fuer(angebot_id: int, benutzer_id: int) -> dict | None:
    """Für POST-Routen: hält ein ANDERER Benutzer die Sperre? Dann dessen Info."""
    halter = inhaber(angebot_id)
    if halter is not None and halter["benutzer_id"] != benutzer_id:
        return halter
    return None
