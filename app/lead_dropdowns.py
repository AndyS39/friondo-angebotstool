# v31 (PLAN_LEAD_V5 Phase 156): Zuständigen-Auswahl des Lead-Moduls – EINE Quelle für
# alle Innendienst-/Leadmanager- und Außendienst-Dropdowns (Kartei, Inline-Edit der
# Boards, Sammelaktionen, Filter, Anrufliste, Schnellanlage, Import, Statistik).
#
# Vertrag (gemeinsames Briefing v31, Agent B schreibt – K und T nutzen):
#   leadmanager_auswahl(session, aktuell_id=None) -> list[(id, name, waehlbar)]
#       nur Benutzer mit Häkchen benutzer.leadmanager UND aktiv, sortiert nach Vorname
#       (Benutzer.vorname, sonst erster Namensteil); der aktuell zugewiesene Nicht-
#       Leadmanager (aktuell_id) steht als „<Name> (nicht mehr wählbar)“ mit
#       waehlbar=False am Ende – bestehende Zuweisungen bleiben gültig.
#   ad_auswahl(session, vorgang) -> list[(id, name)]
#       angestellte Außendienstler (Rolle aussendienst, aktiv, OHNE AD-Profil-Kennzeichen
#       terminiert_selbst); liegt der Lead bereits bei einem Handelsvertreter
#       (vorgaenge.ad_id in einer HV-Gruppe), nur dessen Gruppe: René → nur René,
#       Simon-Gruppe → Simon plus Mitglieder (Parameter hv_gruppe_simon_mitglieder,
#       leer = alle HV außer René [ANNAHME]). Wechsel zwischen den Gruppen oder zurück
#       zum angestellten AD nur über die Sammelaktionen (v23/v29).
# Die Kompetenz-/Kanalregeln des Terminassistenten (lead_termin.kandidaten) sind davon
# unberührt.
from sqlalchemy.orm import Session

from app.models import AdProfil, Benutzer, Vorgang

NICHT_WAEHLBAR = " (nicht mehr wählbar)"


def _vorname(benutzer: Benutzer) -> str:
    """Sortierschlüssel: Vorname aus der Benutzerverwaltung, sonst erster Namensteil."""
    vorname = (getattr(benutzer, "vorname", "") or "").strip()
    if vorname:
        return vorname.lower()
    teile = (benutzer.name or "").strip().split()
    return (teile[0] if teile else "").lower()


def leadmanager_auswahl(session: Session, aktuell_id: int | None = None) -> list[tuple[int, str, bool]]:
    """Innendienst-/Leadmanager-Dropdown: nur Benutzer mit Häkchen „Leadmanager“ (aktiv),
    nach Vorname; der aktuelle Nicht-Leadmanager hängt als nicht wählbar an."""
    benutzer = [b for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
                if getattr(b, "leadmanager", False)]
    benutzer.sort(key=lambda b: (_vorname(b), (b.name or "").lower()))
    liste = [(b.id, b.name, True) for b in benutzer]
    if aktuell_id and aktuell_id not in {b.id for b in benutzer}:
        aktuell = session.get(Benutzer, int(aktuell_id))
        if aktuell is not None:
            liste.append((aktuell.id, f"{aktuell.name}{NICHT_WAEHLBAR}", False))
    return liste


def leadmanager_ids(session: Session) -> set[int]:
    """IDs der wählbaren Leadmanager (für Filter und Round-Robin)."""
    return {b_id for b_id, _, waehlbar in leadmanager_auswahl(session) if waehlbar}


def _hv_ids(session: Session) -> set[int]:
    return {p.benutzer_id for p in session.query(AdProfil)
            .filter(AdProfil.terminiert_selbst.is_(True))}


def angestellte_ad(session: Session) -> list[Benutzer]:
    """Aktive Außendienstler ohne Handelsvertreter-Kennzeichen, nach Name."""
    hv = _hv_ids(session)
    return [b for b in session.query(Benutzer)
            .filter(Benutzer.aktiv.is_(True), Benutzer.rolle == "aussendienst")
            .order_by(Benutzer.name)
            if b.id not in hv]


def hv_gruppe_mitglieder(session: Session, key: str) -> list[int]:
    """Benutzer-IDs einer HV-Gruppe in Dropdown-Reihenfolge (Ziel zuerst):
    rene → hv_gruppe_rene; simon → hv_gruppe_simon plus hv_gruppe_simon_mitglieder
    (leer = alle aktiven Handelsvertreter außer der René-Gruppe [ANNAHME])."""
    from app import lead_v2
    from app import leadmanagement as kern
    gruppen = lead_v2.hv_gruppen(session)
    if key == "rene":
        return list(dict.fromkeys(gruppen.get("rene", [])))
    if key != "simon":
        return []
    ids = list(gruppen.get("simon", []))
    roh = kern.parameter_holen(session, "hv_gruppe_simon_mitglieder", "") or ""
    mitglieder = [int(t) for t in roh.replace(";", ",").split(",") if t.strip().isdigit()]
    if not mitglieder:
        rene = set(gruppen.get("rene", []))
        mitglieder = sorted(b for b in _hv_ids(session) if b not in rene)
    for m in mitglieder:
        if m not in ids:
            ids.append(m)
    return ids


def hv_gruppe_fuer(session: Session, benutzer_id: int | None) -> str:
    """Gruppe („rene“ | „simon“ | „“) eines Handelsvertreters – auch über die
    Mitgliederliste der Simon-Gruppe."""
    if not benutzer_id:
        return ""
    if benutzer_id in hv_gruppe_mitglieder(session, "rene"):
        return "rene"
    if benutzer_id in hv_gruppe_mitglieder(session, "simon"):
        return "simon"
    return ""


def ad_auswahl(session: Session, vorgang: Vorgang | None) -> list[tuple[int, str]]:
    """Außendienst-Dropdown: angestellte AD; liegt der Lead bei einem HV, nur dessen
    Gruppe (René → René; Simon-Gruppe → Simon + Mitglieder). Ein HV außerhalb beider
    Gruppen steht allein in der Liste [ANNAHME]."""
    ad_id = getattr(vorgang, "ad_id", None) if vorgang is not None else None
    hv = _hv_ids(session)
    if ad_id and ad_id in hv:
        gruppe = hv_gruppe_fuer(session, ad_id)
        ids = hv_gruppe_mitglieder(session, gruppe) if gruppe else [ad_id]
        if ad_id not in ids:
            ids = [ad_id] + ids
        benutzer = {b.id: b for b in session.query(Benutzer).filter(Benutzer.id.in_(ids))}
        return [(i, benutzer[i].name) for i in ids
                if i in benutzer and (benutzer[i].aktiv or i == ad_id)]
    liste = [(b.id, b.name) for b in angestellte_ad(session)]
    if ad_id and ad_id not in {i for i, _ in liste}:
        aktuell = session.get(Benutzer, int(ad_id))
        if aktuell is not None:
            liste.append((aktuell.id, f"{aktuell.name}{NICHT_WAEHLBAR}"))
    return liste


def ad_auswahl_dicts(session: Session, vorgang: Vorgang | None = None) -> list[dict]:
    """Dropdown-Einträge als Dicts {id, name, hv} für Templates (Boards, Filter)."""
    hv = _hv_ids(session)
    return [{"id": i, "name": n, "hv": i in hv} for i, n in ad_auswahl(session, vorgang)]


def leadmanager_auswahl_dicts(session: Session, aktuell_id: int | None = None) -> list[dict]:
    return [{"id": i, "name": n, "waehlbar": w} for i, n, w in leadmanager_auswahl(session, aktuell_id)]
