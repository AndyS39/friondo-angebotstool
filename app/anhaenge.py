# Anhänge-Bibliothek (Phase 15): wertet das Blatt "Anhänge" der Logik-Excel
# gegen ein Angebot aus. Regeln: 'immer' | 'wenn <Frage> = <Antwort>' |
# 'wenn Pos. <Nr> im Angebot'. Fehlende Dateien führen zu Warnungen, nie zu
# Abstürzen.

import json
from dataclasses import dataclass

from app import config
from app.logik import Logik, _alias_aufloesen
from app.models import Angebot


@dataclass
class AngebotsAnhang:
    datei: str
    pfad: str
    vorhanden: bool
    regel: str


def _antworten_aus_protokoll(angebot: Angebot) -> dict[str, str]:
    """Frage-ID -> Antworttext aus dem am Angebot gespeicherten Protokoll."""
    try:
        eintraege = json.loads(angebot.protokoll_json or "[]")
    except ValueError:
        return {}
    return {e.get("frage_id"): e.get("antwort", "") for e in eintraege}


def fuer_angebot(logik: Logik, angebot: Angebot) -> list[AngebotsAnhang]:
    """Alle Anhänge, die nach den Regeln zu diesem Angebot mitgehen würden."""
    antworten = _antworten_aus_protokoll(angebot)
    positionen = {p.pos_nr for p in angebot.positionen}
    ergebnis: list[AngebotsAnhang] = []
    for anhang in logik.anhaenge:
        passt = False
        if anhang.art == "immer":
            passt = True
        elif anhang.art == "frage":
            wert = antworten.get(anhang.frage_id, "")
            frage = logik.fragen.get(anhang.frage_id)
            soll = anhang.antwort
            if frage is not None:
                soll = _alias_aufloesen(anhang.antwort, frage.antworten) or anhang.antwort
            passt = wert == soll
        elif anhang.art == "position":
            passt = bool(positionen & set(anhang.positionen))
        if not passt:
            continue
        pfad = config.ANLAGEN_ORDNER / anhang.datei
        ergebnis.append(AngebotsAnhang(anhang.datei, str(pfad), pfad.exists(),
                                       anhang.regel_roh))
    return ergebnis


def vollmacht_erforderlich(angebot: Angebot) -> bool:
    """Nachtext D (Vollmacht) nur, wenn iMSys (P02/Pos. 016) und/oder
    SpotDynamic (P03/Pos. 017) im Angebot sind."""
    positionen = {p.pos_nr for p in angebot.positionen}
    if positionen & {"016", "017"}:
        return True
    antworten = _antworten_aus_protokoll(angebot)
    return antworten.get("P02") == "Ja" or antworten.get("P03") == "Ja"
