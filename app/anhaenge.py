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


def profilname_fuer(session, angebot: Angebot) -> str:
    """v11 (Phase 67): Profilname des Angebots für die Anhangs-Regeln."""
    from app import angebotsprofile
    profil = angebotsprofile.profil_fuer_angebot(session, angebot)
    return profil.name if profil is not None else ""


def _antworten_aus_protokoll(angebot: Angebot) -> dict[str, str]:
    """Frage-ID -> Antworttext aus dem am Angebot gespeicherten Protokoll."""
    try:
        eintraege = json.loads(angebot.protokoll_json or "[]")
    except ValueError:
        return {}
    antworten = {e.get("frage_id"): e.get("antwort", "") for e in eintraege}
    # v13-PV (Phase 79): PV-Bogen fragt HEMS/iMSys/SpotDynamic als PA11–PA13 –
    # dieselben Anhangs- und Vollmacht-Regeln wie P01–P03 (WP)
    for pv_id, wp_id in (("PA11", "P01"), ("PA12", "P02"), ("PA13", "P03")):
        if pv_id in antworten and wp_id not in antworten:
            antworten[wp_id] = antworten[pv_id]
    return antworten


def fuer_angebot(logik: Logik, angebot: Angebot,
                 profil_name: str = "") -> list[AngebotsAnhang]:
    """Alle Anhänge, die nach den Regeln zu diesem Angebot mitgehen würden.
    v11 (Phase 67): profil_name filtert Anhänge mit "Nicht bei Profil"
    (z. B. Ratenkauf/SpotDynamic nicht bei Enni und SWD)."""
    antworten = _antworten_aus_protokoll(angebot)
    positionen = {p.pos_nr for p in angebot.positionen}
    ergebnis: list[AngebotsAnhang] = []
    for anhang in logik.anhaenge:
        if profil_name and any(profil_name.lower() == p.lower()
                               for p in anhang.nicht_bei_profil):
            continue
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
        elif anhang.art == "sparte":   # v13-PV: z. B. „wenn Sparte = PV“
            passt = (angebot.konfigurator_typ or "WP").upper() == anhang.antwort.upper()
        if not passt:
            continue
        pfad = config.ANLAGEN_ORDNER / anhang.datei
        ergebnis.append(AngebotsAnhang(anhang.datei, str(pfad), pfad.exists(),
                                       anhang.regel_roh))
    return ergebnis


def vollmacht_kreuze(angebot: Angebot) -> dict:
    """Vorbelegung der Ankreuzfelder auf der Vollmacht-Seite (v5-Nachtrag):
    Messstellenbetreiber bei iMSys (P02/Pos. 016), Stromlieferant bei
    SpotDynamic (P03/Pos. 017); Anmeldung/Inbetriebnahme immer, wenn die
    Seite ausgegeben wird."""
    positionen = {p.pos_nr for p in angebot.positionen}
    antworten = _antworten_aus_protokoll(angebot)
    return {
        "messstellenbetreiber": "016" in positionen or antworten.get("P02") == "Ja",
        "stromlieferant": "017" in positionen or antworten.get("P03") == "Ja",
        "anmeldung": True,
    }


def vollmacht_erforderlich(angebot: Angebot) -> bool:
    """Nachtext D (Vollmacht) nur, wenn iMSys (P02/Pos. 016) und/oder
    SpotDynamic (P03/Pos. 017) im Angebot sind."""
    positionen = {p.pos_nr for p in angebot.positionen}
    if positionen & {"016", "017"}:
        return True
    antworten = _antworten_aus_protokoll(angebot)
    return antworten.get("P02") == "Ja" or antworten.get("P03") == "Ja"
