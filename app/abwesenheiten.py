# v31 (PLAN_LEAD_V5 Phase 158): Abwesenheiten eines Benutzers (Art „krankheit“, als
# Dropdown-Wert vorbereitet „urlaub“ [ANNAHME: gleiche Wirkung]). Wirkung: der
# Terminassistent schlägt den Vertriebler im Zeitraum nicht vor (lead_termin), seine
# Vor-Ort-Termine und Vorab-Gespräche im Zeitraum stehen in der Innendienst-Sicht
# „Fällig heute“ mit rotem Hinweis „Krankheit: <Name>“ (lead_dashboard). Pflege in der
# Benutzerverwaltung (Admin/Innendienst) und auf „Mein Dashboard“ (eigener Eintrag).
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import BenutzerAbwesenheit

ARTEN = (("krankheit", "Krankheit"), ("urlaub", "Urlaub"))
ARTEN_NAMEN = dict(ARTEN)


def _tag(wert) -> date | None:
    if wert is None or wert == "":
        return None
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    text = str(wert).strip()
    for muster in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, muster).date()
        except ValueError:
            continue
    return None


def anlegen(session: Session, benutzer_id: int, art: str, von, bis, bemerkung: str = "",
            angelegt_von: int | None = None) -> tuple[bool, str, BenutzerAbwesenheit | None]:
    """Legt einen Eintrag an; bis leer = offenes Ende. Liefert (ok, meldung, eintrag)."""
    art = (art or "krankheit").strip().lower()
    if art not in ARTEN_NAMEN:
        return False, "Unbekannte Abwesenheitsart.", None
    von_tag, bis_tag = _tag(von), _tag(bis)
    if von_tag is None:
        return False, "Bitte ein Von-Datum angeben.", None
    if bis_tag is not None and bis_tag < von_tag:
        return False, "Das Bis-Datum liegt vor dem Von-Datum.", None
    eintrag = BenutzerAbwesenheit(benutzer_id=int(benutzer_id), art=art, von=von_tag, bis=bis_tag,
                                  bemerkung=(bemerkung or "").strip()[:300], angelegt_von=angelegt_von)
    session.add(eintrag)
    session.flush()
    return True, f"{ARTEN_NAMEN[art]} eingetragen.", eintrag


def beenden(session: Session, eintrag_id: int, bis=None) -> bool:
    """Setzt das Ende (Standard heute); liefert False, wenn der Eintrag fehlt."""
    eintrag = session.get(BenutzerAbwesenheit, int(eintrag_id))
    if eintrag is None:
        return False
    eintrag.bis = _tag(bis) or date.today()
    session.flush()
    return True


def aktive(session: Session, tag=None) -> list[BenutzerAbwesenheit]:
    """Alle Einträge, die am Tag (Standard heute) gelten."""
    tag = _tag(tag) or date.today()
    return [e for e in session.query(BenutzerAbwesenheit).order_by(BenutzerAbwesenheit.von)
            if e.von <= tag and (e.bis is None or e.bis >= tag)]


def im_zeitraum(session: Session, benutzer_id: int, von, bis) -> list[BenutzerAbwesenheit]:
    """Einträge eines Benutzers, die den Zeitraum von..bis (Tage) überschneiden."""
    von_tag, bis_tag = _tag(von), _tag(bis) or _tag(von)
    if von_tag is None:
        return []
    return [e for e in session.query(BenutzerAbwesenheit)
            .filter(BenutzerAbwesenheit.benutzer_id == int(benutzer_id))
            .order_by(BenutzerAbwesenheit.von)
            if e.von <= bis_tag and (e.bis is None or e.bis >= von_tag)]


def ist_abwesend(session: Session, benutzer_id: int, tag) -> BenutzerAbwesenheit | None:
    """Eintrag, der am Tag (date/datetime/Text) gilt, sonst None – für den
    Terminassistenten (Ausschluss mit Begründung) und die Fällig-heute-Hinweise."""
    tag = _tag(tag)
    if tag is None or not benutzer_id:
        return None
    for e in im_zeitraum(session, benutzer_id, tag, tag):
        return e
    return None


def hinweis_text(eintrag: BenutzerAbwesenheit | None, name: str) -> str:
    """„Krankheit: <Name>“ (Phase 158) bzw. „Urlaub: <Name>“."""
    if eintrag is None:
        return ""
    return f"{ARTEN_NAMEN.get(eintrag.art, eintrag.art.title())}: {name}"


def je_benutzer(session: Session, benutzer_ids=None) -> dict[int, list[BenutzerAbwesenheit]]:
    """Alle Einträge je Benutzer (für Listen in der Benutzerverwaltung)."""
    abfrage = session.query(BenutzerAbwesenheit).order_by(BenutzerAbwesenheit.von.desc())
    if benutzer_ids:
        abfrage = abfrage.filter(BenutzerAbwesenheit.benutzer_id.in_(list(benutzer_ids)))
    ergebnis: dict[int, list] = {}
    for e in abfrage:
        ergebnis.setdefault(e.benutzer_id, []).append(e)
    return ergebnis
