# v31 (PLAN_LEAD_V5 Phase 154): Archivieren von Leads als LEAD-SICHT (Einfügung AT-Chat
# 13.10.2026) – vorgaenge.archiviert_am/archiviert_von blenden den Vorgang aus Lead-Boards,
# Anrufliste, Kanban, Karte, Dashboard und Lead-Kennzahlen aus; Angebotsliste,
# Erfassungsliste, Vorgangsakte, Angebotstool-Statistik, Projektierung und monday-
# Rückspielung zeigen den Vorgang unverändert (Vorgangsakte mit Banner + „Wiederherstellen“,
# Agent AT). Kein endgültiges Löschen; der Löschlauf (loeschlauf) bleibt unberührt.
# Zeitraum-Kennzahlen (Statistik, Kanal-Report) zählen archivierte Leads für die
# Vergangenheit weiter [ANNAHME].
#
# Vertrag (gemeinsames Briefing v31, Agent B schreibt – AT nutzt):
#   ist_archiviert(vorgang) -> bool
#   archivieren(session, vorgang | id | [vorgaenge/ids], benutzer)
#       einzelner Vorgang → (ok, grund); Liste → (archiviert: list[Vorgang],
#       uebersprungen: list[(id, grund)]) – Sperre bei aktivem Termin, offener Erfassung,
#       offenem Angebot (sperrgrund). Aktivität je Lead.
#   wiederherstellen(session, vorgang, benutzer) -> (ok, grund)
#   filter_aktiv(abfrage) -> abfrage.filter(Vorgang.archiviert_am IS NULL)
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Angebot, Erfassung, Vorgang, VotTermin

# aktiver Termin = jeder Kundentermin (VOT, Telefon, Online), der noch bevorsteht
TERMIN_AKTIV = ("geplant", "bestaetigt", "vorgemerkt")
ANGEBOT_OFFEN = ("Entwurf", "Versand vorbereitet", "Versendet", "Versendet (extern)", "Individuell")
GRUND_TERMIN = "aktiver Termin"
GRUND_ERFASSUNG = "offene Erfassung"
GRUND_ANGEBOT = "offenes Angebot"
AKTIVITAET_ARCHIVIERT = "Archiviert (Lead-Sicht)"
AKTIVITAET_WIEDERHERGESTELLT = "Wiederhergestellt (aus dem Archiv)"


def ist_archiviert(vorgang) -> bool:
    return bool(vorgang is not None and getattr(vorgang, "archiviert_am", None))


def filter_aktiv(abfrage):
    """SQLAlchemy-Filter für Boards, Listen, Kennzahlen: nur nicht archivierte Vorgänge."""
    return abfrage.filter(Vorgang.archiviert_am.is_(None))


def sperrgrund(session: Session, vorgang: Vorgang) -> str:
    """Leerer Text = archivierbar; sonst der erste Sperrgrund (Termin vor Erfassung vor
    Angebot – Reihenfolge wie im Plan)."""
    if (session.query(VotTermin)
            .filter(VotTermin.vorgang_id == vorgang.id, VotTermin.status.in_(TERMIN_AKTIV),
                    VotTermin.typ != "sperrzeit").count()):
        return GRUND_TERMIN
    for e in (session.query(Erfassung)
              .filter(Erfassung.vorgang_id == vorgang.id, Erfassung.archiviert.is_(False))):
        if not (e.status or "").startswith("Erledigt"):
            return GRUND_ERFASSUNG
    if (session.query(Angebot)
            .filter(Angebot.vorgang_id == vorgang.id, Angebot.archiviert.is_(False),
                    Angebot.status.in_(ANGEBOT_OFFEN)).count()):
        return GRUND_ANGEBOT
    return ""


def _vorgang(session: Session, wert) -> Vorgang | None:
    if isinstance(wert, Vorgang):
        return wert
    try:
        return session.get(Vorgang, int(wert))
    except (TypeError, ValueError):
        return None


def archivieren_einen(session: Session, vorgang: Vorgang, benutzer=None) -> tuple[bool, str]:
    """Einen Vorgang archivieren: (ok, grund) – grund = Sperrgrund bzw. „bereits archiviert“."""
    from app import leadmanagement as kern
    if vorgang is None:
        return False, "Vorgang nicht gefunden"
    if ist_archiviert(vorgang):
        return False, "bereits archiviert"
    grund = sperrgrund(session, vorgang)
    if grund:
        return False, grund
    vorgang.archiviert_am = datetime.now()
    vorgang.archiviert_von = benutzer.id if benutzer is not None else None
    kern.aktivitaet(session, vorgang.id, "status", AKTIVITAET_ARCHIVIERT, benutzer=benutzer)
    session.flush()
    return True, ""


def archivieren(session: Session, vorgaenge, benutzer=None):
    """Liste → (archiviert, uebersprungen[(id, grund)]); einzelner Vorgang/ID → (ok, grund)."""
    if not isinstance(vorgaenge, (list, tuple, set)):
        return archivieren_einen(session, _vorgang(session, vorgaenge), benutzer)
    archiviert, uebersprungen = [], []
    for wert in vorgaenge:
        v = _vorgang(session, wert)
        if v is None:
            uebersprungen.append((wert, "Vorgang nicht gefunden"))
            continue
        ok, grund = archivieren_einen(session, v, benutzer)
        if ok:
            archiviert.append(v)
        else:
            uebersprungen.append((v.id, grund))
    return archiviert, uebersprungen


def wiederherstellen(session: Session, vorgang, benutzer=None) -> tuple[bool, str]:
    """Archiv-Kennzeichen entfernen (Vorgangsakte-Banner, Sammelaktion „Wiederherstellen“)."""
    from app import leadmanagement as kern
    vorgang = _vorgang(session, vorgang)
    if vorgang is None:
        return False, "Vorgang nicht gefunden"
    if not ist_archiviert(vorgang):
        return False, "nicht archiviert"
    vorgang.archiviert_am = None
    vorgang.archiviert_von = None
    kern.aktivitaet(session, vorgang.id, "status", AKTIVITAET_WIEDERHERGESTELLT, benutzer=benutzer)
    session.flush()
    return True, ""


def archiv_text(session: Session, vorgang) -> str:
    """„Archiviert am 13.10.2026 14:05 von Andreas Scheelen“ für Banner und Tooltips."""
    if not ist_archiviert(vorgang):
        return ""
    from app.models import Benutzer
    wer = session.get(Benutzer, vorgang.archiviert_von) if vorgang.archiviert_von else None
    text = f"Archiviert am {vorgang.archiviert_am.strftime('%d.%m.%Y %H:%M')}"
    return text + (f" von {wer.name}" if wer is not None else "")


def meldung(archiviert: list, uebersprungen: list) -> str:
    """„2 archiviert, 1 übersprungen: aktiver Termin“ (Gründe ohne Dubletten)."""
    text = f"{len(archiviert)} archiviert"
    if uebersprungen:
        gruende = list(dict.fromkeys(g for _, g in uebersprungen))
        text += f", {len(uebersprungen)} übersprungen: " + ", ".join(gruende)
    return text
