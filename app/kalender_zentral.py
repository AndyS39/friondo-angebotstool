# Zentraler Planungskalender `/kalender` – v33 (PLAN_V20 Phase 169, Agent K).
#
# Eine Zeile je Mitarbeiter, Zeitachse waagerecht im 15-Minuten-Raster zwischen den
# Parametern kalender_tagesbeginn/kalender_tagesende (Lead-Parameter, 07:00–18:00).
# Mitarbeiter-Gruppen aus Basisrolle, Kennzeichen und Gewerk (app/rollen.py):
#   Außendienst · Handelsvertreter · Projektierung · Montage Heizung · Montage Elektro ·
#   Service Heizung · Service Elektro · Innendienst
# Quellen der Einträge (je Quelle EINE Abfrage, nie Graph im Request):
#   vot         vot_termine (VOT, Vorab-Gespräche telefon/online, Sperrzeiten; nur offene Status)
#   projekt     projekt_termine über Besetzung/Person (Montage, Elektro, Sub, Feinplanung,
#               Abnahme, Sonstiges) – Vertrag S: projektierung.termine_fuer_personen, sonst
#               Rückfall auf projekt_termine + termin_besetzung (+ Team-Mitglieder ohne Besetzung)
#   service     Terminart service (Phase 168), auch am Vorgang ohne Projekt (projekt_id 0)
#   abwesenheit benutzer_abwesenheiten (Krankheit/Urlaub, graue Balken)
#   belegt      outlook_belegt (nur Zeit + „belegt“, nie ein Betreff) – Vertrag O:
#               outlook_sync.belegt, sonst Rückfall auf die Tabelle
# Drag verschiebt Tool-Termine über die Kernfunktionen der Module (lead_termin.termin_anlegen
# mit umbuchen_id bzw. projektierung.termin_verschieben – Vertrag S, sonst Rückfall);
# Konflikte kommen als Liste zurück und werden erst nach Bestätigung übergangen.
# Auswahl je Nutzer: benutzer_einstellungen Key `kalender_gruppen` (JSON je Einstieg
# projektierung | vertrieb | alle: gruppen, wochenende, ansicht).
import inspect
import json
import time
from datetime import date, datetime, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app import leadmanagement as lead_kern
from app import lead_v2
from app.models import (AdProfil, Benutzer, Kunde, OutlookBelegt, Projekt, ProjektTermin,
                        TeamMitglied, TerminBesetzung, Vorgang, VotTermin, TERMIN_TYP_NAMEN)

GRUPPEN = (
    ("aussendienst", "Außendienst"),
    ("handelsvertreter", "Handelsvertreter"),
    ("projektierung", "Projektierung"),
    ("montage_heizung", "Montage Heizung"),
    ("montage_elektro", "Montage Elektro"),
    ("service_heizung", "Service Heizung"),
    ("service_elektro", "Service Elektro"),
    ("innendienst", "Innendienst"),
)
GRUPPEN_NAMEN = dict(GRUPPEN)
GRUPPEN_REIHENFOLGE = {key: i for i, (key, _) in enumerate(GRUPPEN)}
MONTAGE_GRUPPEN = ("montage_heizung", "montage_elektro", "service_heizung", "service_elektro")
VERTRIEB_GRUPPEN = ("aussendienst", "handelsvertreter")
EINSTIEGE = ("projektierung", "vertrieb", "alle")
EINSTIEG_GRUPPEN = {
    "projektierung": ("projektierung",) + MONTAGE_GRUPPEN,   # Monteure + Projektierer
    "vertrieb": VERTRIEB_GRUPPEN,                             # AD + HV
    "alle": tuple(key for key, _ in GRUPPEN),
}
EINSTELLUNG_KEY = "kalender_gruppen"
ANSICHTEN = ("tag", "woche", "monat")
RASTER_MIN = 15
TAGESBEGINN_STANDARD = "07:00"
TAGESENDE_STANDARD = "18:00"
MAX_TAGE = 62            # Monat + Rand
MAX_PERSONEN = 300
SUCHE_MAX = 8
# offene VOT-Status (geplant | bestaetigt | unbestaetigt | vorgemerkt) – erfolgt/abgesagt/
# no_show/verschoben bleiben draußen [Briefing: nur offene Status]
OFFENE_VOT_STATUS = ("geplant", "bestaetigt", "unbestaetigt", "vorgemerkt")
VOT_DAUER_STANDARD_MIN = 90
VORAB_DAUER_STANDARD_MIN = 30
# Anzeigenamen je Art (Farbklasse = "kz-" + art, kalender_zentral.css)
ART_NAMEN = {
    "vot": "Vor-Ort-Termin", "telefon": "Telefongespräch", "online": "Online-Termin (Teams)",
    "sperrzeit": "Sperrzeit",
    "montage": "Montage (WP)", "elektro": "Elektro-Montage", "sub": "Sub-Einsatz",
    "feinplanung": "Feinplanung VOT", "abnahme": "Abnahme", "sonstige": "Sonstiges",
    "service": "Service-Einsatz",
    "krankheit": "Krankheit", "urlaub": "Urlaub", "abwesenheit": "Abwesenheit",
    "belegt": "Outlook belegt",
}
ABWESENHEIT_ARTEN = ("krankheit", "urlaub")
KEIN_RECHT = "Keine Berechtigung, diesen Termin zu verschieben."
NUR_LESEN_TEXT = "Montage- und Service-Benutzer sehen den Kalender nur lesend."


# --- Zeit-Helfer --------------------------------------------------------------------

def _tag(wert) -> date | None:
    if wert is None or wert == "":
        return None
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    text = str(wert).strip()[:10]
    for muster in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, muster).date()
        except ValueError:
            continue
    return None


def _zeit(wert) -> datetime | None:
    """YYYY-MM-DDTHH:MM (auch mit Sekunden/Leerzeichen) → datetime, sonst None."""
    if isinstance(wert, datetime):
        return wert
    text = str(wert or "").strip().replace(" ", "T")
    for muster in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:len("YYYY-MM-DDTHH:MM:SS")], muster)
        except ValueError:
            continue
    return None


def _iso(zeit: datetime | None) -> str:
    return zeit.strftime("%Y-%m-%dT%H:%M") if zeit else ""


def viertelstunde(zeit: datetime) -> datetime:
    """Auf das 15-Minuten-Raster runden (kaufmännisch)."""
    minute = int(round(zeit.minute / RASTER_MIN)) * RASTER_MIN
    basis = zeit.replace(second=0, microsecond=0, minute=0)
    return basis + timedelta(minutes=minute)


def _minuten(text: str, standard: str) -> int:
    roh = (text or standard or "").strip()
    try:
        stunde, _, minute = roh.partition(":")
        wert = int(stunde) * 60 + int(minute or 0)
    except ValueError:
        stunde, _, minute = standard.partition(":")
        wert = int(stunde) * 60 + int(minute or 0)
    return max(0, min(24 * 60, wert))


def tageszeiten(session: Session) -> tuple[int, int]:
    """(Beginn, Ende) der Zeitachse in Minuten aus kalender_tagesbeginn/-ende."""
    von = _minuten(lead_kern.parameter_holen(session, "kalender_tagesbeginn", TAGESBEGINN_STANDARD),
                   TAGESBEGINN_STANDARD)
    bis = _minuten(lead_kern.parameter_holen(session, "kalender_tagesende", TAGESENDE_STANDARD),
                   TAGESENDE_STANDARD)
    if bis <= von:
        von, bis = _minuten(TAGESBEGINN_STANDARD, TAGESBEGINN_STANDARD), _minuten(TAGESENDE_STANDARD, TAGESENDE_STANDARD)
    return von, bis


def zeitraum(ansicht: str, datum) -> tuple[date, date]:
    """Erster und letzter Tag (einschließlich) der Ansicht um `datum`."""
    tag = _tag(datum) or date.today()
    if ansicht == "tag":
        return tag, tag
    if ansicht == "monat":
        von = tag.replace(day=1)
        naechster = (von.replace(year=von.year + 1, month=1) if von.month == 12
                     else von.replace(month=von.month + 1))
        return von, naechster - timedelta(days=1)
    von = tag - timedelta(days=tag.weekday())
    return von, von + timedelta(days=6)


# --- Gruppen und Personen -----------------------------------------------------------

def gruppe_von(benutzer) -> str:
    """Gruppe eines Benutzers aus Basisrolle, Kennzeichen und Gewerk. Basisrolle montage
    ohne Gewerk → „Montage Heizung“ [ANNAHME]; Leadmanagement (Basisrolle) zählt zum
    Innendienst [eigene Annahme, Rückfrage]."""
    basis = benutzer.basisrolle
    if basis == "aussendienst":
        return "handelsvertreter" if benutzer.hat_kennzeichen("handelsvertreter") else "aussendienst"
    if basis == "projektierung":
        return "projektierung"
    if basis == "montage":
        gewerk = benutzer.gewerk or "heizung"
        if gewerk not in ("heizung", "elektro"):
            gewerk = "heizung"
        return f"{'service' if benutzer.hat_kennzeichen('service') else 'montage'}_{gewerk}"
    return "innendienst"


def nur_lesen(benutzer) -> bool:
    """Montage-/Service-Benutzer (Basisrolle montage): nur sich selbst und das eigene Team,
    read-only."""
    return benutzer is not None and benutzer.basisrolle == "montage"


def eigene_teams(session: Session, benutzer) -> list[int]:
    return [m.team_id for m in session.query(TeamMitglied)
            .filter(TeamMitglied.benutzer_id == benutzer.id)]


def personen_katalog(session: Session, benutzer=None) -> list[dict]:
    """Alle aktiven Benutzer mit Gruppe, sortiert nach Gruppe und Name. Für Montage-/
    Service-Benutzer nur sie selbst und die Mitglieder ihrer Teams."""
    alle = [b for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True))]
    erlaubt = None
    if benutzer is not None and nur_lesen(benutzer):
        teams = eigene_teams(session, benutzer)
        erlaubt = {benutzer.id}
        if teams:
            erlaubt |= {m.benutzer_id for m in session.query(TeamMitglied)
                        .filter(TeamMitglied.team_id.in_(teams))}
    katalog = []
    for b in alle:
        if erlaubt is not None and b.id not in erlaubt:
            continue
        gruppe = gruppe_von(b)
        katalog.append({"id": b.id, "name": b.name, "gruppe": gruppe,
                        "gruppe_name": GRUPPEN_NAMEN[gruppe],
                        "rolle": b.rollen_name})
    katalog.sort(key=lambda p: (GRUPPEN_REIHENFOLGE.get(p["gruppe"], 99), p["name"].lower()))
    return katalog


def erlaubte_ids(session: Session, benutzer) -> set[int] | None:
    """None = alle Personen erlaubt; sonst die Menge (Montage/Service)."""
    if benutzer is None or not nur_lesen(benutzer):
        return None
    return {p["id"] for p in personen_katalog(session, benutzer)}


def einstieg_bestimmen(parameter: str, benutzer) -> str:
    """Einstieg aus ?gruppe= bzw. der Basisrolle: projektierung | vertrieb | alle | eigene."""
    p = (parameter or "").strip().lower()
    if p in EINSTIEGE:
        return p
    if benutzer is None:
        return "alle"
    if nur_lesen(benutzer):
        return "eigene"
    basis = benutzer.basisrolle
    if basis == "projektierung":
        return "projektierung"
    if basis in ("leadmanagement", "aussendienst"):
        return "vertrieb"
    return "alle"


def standard_gruppen(einstieg: str) -> list[str]:
    return list(EINSTIEG_GRUPPEN.get(einstieg, EINSTIEG_GRUPPEN["alle"]))


def auswahl_laden(session: Session, benutzer, einstieg: str) -> dict:
    """Gemerkte Auswahl je Nutzer und Einstieg (kalender_gruppen), sonst Standard."""
    standard = {"gruppen": standard_gruppen(einstieg), "wochenende": False, "ansicht": "woche",
                "gemerkt": False}
    if benutzer is None or einstieg == "eigene":
        return standard
    gespeichert = lead_v2.einstellung_holen(session, benutzer.id, EINSTELLUNG_KEY, None)
    if isinstance(gespeichert, list):                     # Altform: nur Gruppen
        gespeichert = {einstieg: {"gruppen": gespeichert}}
    if not isinstance(gespeichert, dict):
        return standard
    eintrag = gespeichert.get(einstieg)
    if not isinstance(eintrag, dict):
        return standard
    gruppen = [g for g in (eintrag.get("gruppen") or []) if g in GRUPPEN_NAMEN]
    ansicht = eintrag.get("ansicht") if eintrag.get("ansicht") in ANSICHTEN else "woche"
    return {"gruppen": gruppen if gruppen else standard["gruppen"],
            "wochenende": bool(eintrag.get("wochenende")), "ansicht": ansicht, "gemerkt": True}


def auswahl_speichern(session: Session, benutzer, einstieg: str, gruppen=None,
                      wochenende=None, ansicht=None) -> dict:
    """Auswahl je Einstieg fortschreiben (nur übergebene Felder); liefert den Eintrag."""
    if einstieg not in EINSTIEGE:
        einstieg = "alle"
    gespeichert = lead_v2.einstellung_holen(session, benutzer.id, EINSTELLUNG_KEY, None)
    if isinstance(gespeichert, list):
        gespeichert = {"alle": {"gruppen": gespeichert}}
    if not isinstance(gespeichert, dict):
        gespeichert = {}
    eintrag = dict(gespeichert.get(einstieg) or {})
    if gruppen is not None:
        eintrag["gruppen"] = [g for g in gruppen if g in GRUPPEN_NAMEN]
    if wochenende is not None:
        eintrag["wochenende"] = bool(wochenende)
    if ansicht in ANSICHTEN:
        eintrag["ansicht"] = ansicht
    gespeichert[einstieg] = eintrag
    lead_v2.einstellung_setzen(session, benutzer.id, EINSTELLUNG_KEY, gespeichert)
    return eintrag


# --- Rechte -------------------------------------------------------------------------

def darf_lead_termine(session: Session, benutzer) -> bool:
    """VOT/Vorab verschieben wie im Lead-Modul: Admin, Innendienst, Leadmanagement
    (Modul sichtbar) – der zuständige AD nur den eigenen Termin (siehe _vot_recht)."""
    return benutzer is not None and lead_kern.lead_modul_sichtbar(session, benutzer)


def darf_projekt_termine(session: Session, benutzer) -> bool:
    """Projekt-/Service-Termine verschieben wie in der Projektierung (Schreibrollen)."""
    if benutzer is None or nur_lesen(benutzer):
        return False
    from app import projektierung
    if not projektierung.modul_sichtbar(session, benutzer):
        return False
    return any(benutzer.hat_rolle(r) for r in ("admin", "innendienst", "projektierung"))


def _vot_recht(session: Session, benutzer, termin: VotTermin, lead_ok: bool) -> bool:
    if benutzer is None or nur_lesen(benutzer):
        return False
    if (termin.typ or "vot") == "sperrzeit" or termin.quelle == "monday":
        return False
    if termin.status not in OFFENE_VOT_STATUS:
        return False
    if lead_ok:
        return True
    return benutzer.basisrolle == "aussendienst" and termin.ad_id == benutzer.id


# --- Einträge -----------------------------------------------------------------------

def _eintrag(key: str, nr, quelle: str, art: str, beginn, ende, personen, kunde: str = "",
             ort: str = "", text: str = "", link: str = "", ganztaegig: bool = False,
             verschiebbar: bool = False, status: str = "", zusatz: dict | None = None) -> dict:
    e = {"key": key, "id": nr, "quelle": quelle, "art": art,
         "art_name": ART_NAMEN.get(art, art),
         "beginn": _iso(beginn), "ende": _iso(ende), "ganztaegig": bool(ganztaegig),
         "kunde": kunde or "", "ort": ort or "", "text": text or "", "link": link or "",
         "personen": [int(p) for p in personen if p],
         "farbe_klasse": f"kz-{art}" + (" kz-vorgemerkt" if status == "vorgemerkt" else "")
                         + (" kz-unbestaetigt" if status == "unbestaetigt" else "")
                         + (" kz-erfolgt" if status == "erfolgt" else ""),
         "verschiebbar": bool(verschiebbar), "status": status or ""}
    if zusatz:
        e.update(zusatz)
    return e


def _kunden_text(kunde) -> str:
    return kunde.anzeige_name if kunde is not None else ""


def _vot_eintraege(session: Session, benutzer, ids: list[int], von_dt: datetime,
                   bis_dt: datetime, lead_ok: bool) -> list[dict]:
    """VOT, Vorab-Gespräche und Sperrzeiten der Personen (eine Abfrage + Vorgänge/Kunden)."""
    if not ids:
        return []
    termine = (session.query(VotTermin)
               .filter(VotTermin.ad_id.in_(ids),
                       # Nachtrag 15.10.2026 (K-R3): erfolgte Termine bleiben als Rückschau sichtbar
                       # (gedämpft, nicht verschiebbar – _vot_recht verlangt einen offenen Status)
                       VotTermin.status.in_(OFFENE_VOT_STATUS + ("erfolgt",)),
                       VotTermin.beginn.isnot(None),
                       VotTermin.beginn < bis_dt,
                       VotTermin.beginn >= von_dt - timedelta(days=1))
               .order_by(VotTermin.beginn).all())
    if not termine:
        return []
    profile = {p.benutzer_id: p for p in session.query(AdProfil)
               .filter(AdProfil.benutzer_id.in_({t.ad_id for t in termine}))}
    vorgang_ids = {t.vorgang_id for t in termine if t.vorgang_id}
    vorgaenge = ({v.id: v for v in session.query(Vorgang).filter(Vorgang.id.in_(vorgang_ids))}
                 if vorgang_ids else {})
    kunden_ids = {v.kunde_id for v in vorgaenge.values()}
    kunden = ({k.id: k for k in session.query(Kunde).filter(Kunde.id.in_(kunden_ids))}
              if kunden_ids else {})
    hv_id = None
    try:
        from app import lead_termin
        hv_id = lead_termin.hv_nur_eigene(session, benutzer)
    except Exception:   # noqa: BLE001 – Lead-Modul ohne Kandidatenlogik
        hv_id = None
    ergebnis = []
    for t in termine:
        typ = t.typ or "vot"
        profil = profile.get(t.ad_id)
        if typ == "vot":
            dauer = timedelta(minutes=(profil.termin_dauer_min if profil is not None
                                       and profil.termin_dauer_min else VOT_DAUER_STANDARD_MIN))
        else:
            dauer = timedelta(minutes=VORAB_DAUER_STANDARD_MIN)
        ende = t.ende or (t.beginn + dauer)
        if ende <= von_dt:
            continue
        v = vorgaenge.get(t.vorgang_id)
        k = kunden.get(v.kunde_id) if v is not None else None
        if typ == "sperrzeit":
            text = "Sperrzeit" + (f": {t.grund_text}" if t.grund_text else "")
            link = "/lead-management/handelsvertreter#sperrzeiten" if lead_ok else "/lead-management/dashboard"
            ergebnis.append(_eintrag(f"vot-{t.id}", t.id, "vot", "sperrzeit", t.beginn, ende,
                                     [t.ad_id], text=text, link=link, status=t.status))
            continue
        ort = ""
        if t.adresse:
            ort = t.adresse.split(",")[-1].strip() if "," in t.adresse else t.adresse
        elif k is not None:
            ort = k.ort or ""
        recht = _vot_recht(session, benutzer, t, lead_ok) and (not hv_id or t.ad_id == hv_id)
        link = f"/lead-management/lead/{t.vorgang_id}?tab=termin" if t.vorgang_id else ""
        text = ART_NAMEN.get(typ, typ) + (" (vorgemerkt)" if t.status == "vorgemerkt" else "")
        ergebnis.append(_eintrag(f"vot-{t.id}", t.id, "vot", typ, t.beginn, ende, [t.ad_id],
                                 kunde=_kunden_text(k), ort=ort, text=text, link=link,
                                 verschiebbar=recht, status=t.status,
                                 zusatz={"vorgang_id": t.vorgang_id, "monday": t.quelle == "monday"}))
    return ergebnis


def _projekt_rueckfall(session: Session, ids: list[int], von_dt: datetime,
                       bis_dt: datetime) -> list[dict]:
    """Rückfall ohne Vertrag S: projekt_termine + termin_besetzung (+ person_id, Team-
    Mitglieder bei Terminen ohne Besetzung) in einer Abfrage; Felder wie der Vertrag
    (id, art, art_name, beginn, ende, kunde, ort, link, besetzung_ids, gewerk_id, projekt_id)."""
    from app import projektierung as pj
    id_menge = set(ids)
    zeilen = (session.query(ProjektTermin, TerminBesetzung.benutzer_id)
              .outerjoin(TerminBesetzung, TerminBesetzung.termin_id == ProjektTermin.id)
              .filter(ProjektTermin.beginn.isnot(None),
                      ProjektTermin.beginn < bis_dt,
                      or_(ProjektTermin.ende >= von_dt,
                          and_(ProjektTermin.ende.is_(None), ProjektTermin.beginn >= von_dt)))
              .order_by(ProjektTermin.beginn, ProjektTermin.id).all())
    termine: dict[int, ProjektTermin] = {}
    besetzung: dict[int, list[int]] = {}
    for t, bid in zeilen:
        termine.setdefault(t.id, t)
        besetzung.setdefault(t.id, [])
        if bid and bid not in besetzung[t.id]:
            besetzung[t.id].append(bid)
    # Termine ohne Besetzung: Team-Mitglieder (wie das Montage-Backend)
    ohne = {t.team_id for t in termine.values() if not besetzung[t.id] and t.team_id}
    mitglieder: dict[int, list[int]] = {}
    if ohne:
        for m in session.query(TeamMitglied).filter(TeamMitglied.team_id.in_(ohne)).order_by(TeamMitglied.id):
            mitglieder.setdefault(m.team_id, []).append(m.benutzer_id)
    treffer = []
    for t in termine.values():
        personen = list(besetzung[t.id])
        if not personen and t.team_id:
            personen = list(mitglieder.get(t.team_id, []))
        if t.person_id and t.person_id not in personen:
            personen.append(t.person_id)
        if not (set(personen) & id_menge):
            continue
        art = pj.termin_art(t)
        treffer.append({"termin": t, "id": t.id, "art": art, "art_name": pj.TERMIN_ARTEN[art][2],
                        "beginn": t.beginn, "ende": t.ende, "besetzung_ids": personen,
                        "gewerk_id": t.gewerk_id, "projekt_id": t.projekt_id,
                        "vorgang_id": getattr(t, "vorgang_id", None),
                        "ganztaegig": bool(t.ganztaegig), "kunde": "", "ort": "", "link": "",
                        "anlass": getattr(t, "anlass", "") or "",
                        "service_gewerk": getattr(t, "service_gewerk", "") or "",
                        "kunde_bestaetigt": bool(t.kunde_bestaetigt)})
    # Kunde/Ort/Link in je einer Abfrage nachladen
    projekt_ids = {z["projekt_id"] for z in treffer if z["projekt_id"]}
    projekte = ({p.id: p for p in session.query(Projekt).filter(Projekt.id.in_(projekt_ids))}
                if projekt_ids else {})
    vorgang_ids = {z["vorgang_id"] for z in treffer if not z["projekt_id"] and z["vorgang_id"]}
    vorgaenge = ({v.id: v for v in session.query(Vorgang).filter(Vorgang.id.in_(vorgang_ids))}
                 if vorgang_ids else {})
    kunden_ids = ({p.kunde_id for p in projekte.values()} | {v.kunde_id for v in vorgaenge.values()})
    kunden = ({k.id: k for k in session.query(Kunde).filter(Kunde.id.in_(kunden_ids))}
              if kunden_ids else {})
    for z in treffer:
        p = projekte.get(z["projekt_id"])
        if p is not None:
            k = kunden.get(p.kunde_id)
            z["kunde"] = _kunden_text(k)
            z["ort"] = p.ausfuehrung_ort or (k.ort if k is not None else "")
            z["nummer"] = p.nummer
            z["link"] = f"/projektierung/projekt/{p.id}#termin-{z['id']}"
        else:
            v = vorgaenge.get(z["vorgang_id"])
            k = kunden.get(v.kunde_id) if v is not None else None
            z["kunde"] = _kunden_text(k)
            z["ort"] = k.ort if k is not None else ""
            z["link"] = f"/vorgaenge/{v.id}#termine" if v is not None else ""
    return treffer


def _projekt_eintraege(session: Session, benutzer, ids: list[int], von_dt: datetime,
                       bis_dt: datetime, projekt_ok: bool) -> list[dict]:
    """Projekt- und Service-Termine – Vertrag S (projektierung.termine_fuer_personen) mit
    Rückfall; Mehrfachbesetzung = ein Eintrag mit mehreren Personen (erscheint in jeder Zeile)."""
    if not ids:
        return []
    from app import projektierung as pj
    liefern = getattr(pj, "termine_fuer_personen", None)
    rohe = None
    if callable(liefern):
        try:
            rohe = liefern(session, list(ids), von_dt, bis_dt)
        except Exception:   # noqa: BLE001 – Vertrag unvollständig → Rückfall
            rohe = None
    if rohe is None:
        rohe = _projekt_rueckfall(session, ids, von_dt, bis_dt)
    ergebnis = []
    for z in rohe:
        art = z.get("art") or "sonstige"
        beginn = _zeit(z.get("beginn")) if not isinstance(z.get("beginn"), datetime) else z["beginn"]
        if beginn is None:
            continue
        ende = z.get("ende")
        ende = _zeit(ende) if ende and not isinstance(ende, datetime) else ende
        ganztaegig = z.get("ganztaegig")
        if ganztaegig is None:
            ganztaegig = beginn.time() == datetime.min.time() and (ende is None or ende.time() == datetime.min.time())
        if ganztaegig:
            # Balken über ganze Tage: Ende als exklusiver Folgetag 00:00
            ende_anzeige = datetime.combine((ende or beginn).date(), datetime.min.time()) + timedelta(days=1)
        else:
            ende_anzeige = ende or (beginn + timedelta(hours=1))
        if ende_anzeige <= von_dt or beginn >= bis_dt:
            continue
        # Vertrag S liefert personen_ids (Besetzung ∪ Person); Rückfall: besetzung_ids
        personen = [int(p) for p in (z.get("personen_ids") or z.get("besetzung_ids")
                                     or z.get("personen") or []) if p]
        if not personen:
            continue
        quelle = "service" if art == "service" else "projekt"
        text = z.get("art_name") or ART_NAMEN.get(art, art)
        if art == "service":
            from app import projektierung as _pj
            anlaesse = dict(getattr(_pj, "SERVICE_ANLAESSE", ()))
            gewerk = {"heizung": "Heizung", "elektro": "Elektro"}.get(z.get("service_gewerk") or "", "")
            teile = [gewerk, anlaesse.get(z.get("anlass") or "", z.get("anlass") or "")]
            text += " · " + " · ".join(t for t in teile if t) if any(teile) else ""
        nummer = z.get("nummer") or ""
        if nummer:
            text = f"{nummer} · {text}"
        if z.get("kunde_bestaetigt") is False and art in ("montage", "elektro", "sub"):
            text += " · Kunde unbestätigt"
        status = "unbestaetigt" if (art in ("montage", "elektro", "sub")
                                    and z.get("kunde_bestaetigt") is False) else ""
        ergebnis.append(_eintrag(f"{quelle}-{z['id']}", z["id"], quelle, art, beginn, ende_anzeige,
                                 personen, kunde=z.get("kunde") or "", ort=z.get("ort") or "",
                                 text=text, link=z.get("link") or "", ganztaegig=bool(ganztaegig),
                                 verschiebbar=projekt_ok, status=status,
                                 zusatz={"projekt_id": z.get("projekt_id"),
                                         "gewerk_id": z.get("gewerk_id")}))
    return ergebnis


def _abwesenheit_eintraege(session: Session, benutzer, ids: list[int], von: date,
                           bis: date) -> list[dict]:
    """Krankheit/Urlaub als graue Balken (eine Abfrage über abwesenheiten.je_benutzer)."""
    if not ids:
        return []
    from app import abwesenheiten
    je_benutzer = abwesenheiten.je_benutzer(session, ids)
    link = "/benutzer" if (benutzer is not None
                           and benutzer.basisrolle in ("admin", "innendienst")) else ""
    ergebnis = []
    for bid, eintraege in je_benutzer.items():
        for e in eintraege:
            if e.von > bis or (e.bis is not None and e.bis < von):
                continue
            art = e.art if e.art in ABWESENHEIT_ARTEN else "abwesenheit"
            anzeige_von = datetime.combine(max(e.von, von), datetime.min.time())
            anzeige_bis = datetime.combine(min(e.bis or bis, bis), datetime.min.time()) + timedelta(days=1)
            text = ART_NAMEN.get(art, "Abwesenheit")
            if e.bis is None:
                text += " (offenes Ende)"
            if e.bemerkung and link:
                text += f": {e.bemerkung}"
            ergebnis.append(_eintrag(f"abw-{e.id}", e.id, "abwesenheit", art, anzeige_von, anzeige_bis,
                                     [bid], text=text, link=link, ganztaegig=True,
                                     zusatz={"von": e.von.isoformat(),
                                             "bis": e.bis.isoformat() if e.bis else ""}))
    return ergebnis


def belegt_laden(session: Session, ids: list[int], von_dt: datetime,
                 bis_dt: datetime) -> dict[int, list[tuple[datetime, datetime]]]:
    """Outlook-Belegtzeiten aus dem Cache – Vertrag O (outlook_sync.belegt), sonst die
    Tabelle outlook_belegt; nie ein Graph-Aufruf."""
    if not ids:
        return {}
    try:
        from app import outlook_sync
        liefern = getattr(outlook_sync, "belegt", None)
    except ImportError:
        liefern = None
    if callable(liefern):
        try:
            daten = liefern(session, list(ids), von_dt, bis_dt)
            if isinstance(daten, dict):
                return {int(k): [(a, b) for a, b in v] for k, v in daten.items()}
        except Exception:   # noqa: BLE001 – Vertrag unvollständig → Tabelle lesen
            pass
    ergebnis: dict[int, list] = {}
    for z in (session.query(OutlookBelegt)
              .filter(OutlookBelegt.benutzer_id.in_(ids),
                      OutlookBelegt.von < bis_dt, OutlookBelegt.bis > von_dt)
              .order_by(OutlookBelegt.von)):
        ergebnis.setdefault(z.benutzer_id, []).append((z.von, z.bis))
    return ergebnis


def _belegt_eintraege(session: Session, ids: list[int], von_dt: datetime,
                      bis_dt: datetime) -> list[dict]:
    ergebnis = []
    nr = 0
    for bid, zeiten in belegt_laden(session, ids, von_dt, bis_dt).items():
        for b_von, b_bis in zeiten:
            if b_von is None or b_bis is None or b_bis <= von_dt or b_von >= bis_dt:
                continue
            nr += 1
            ganztaegig = (b_bis - b_von) >= timedelta(hours=23, minutes=59)
            ergebnis.append(_eintrag(f"belegt-{bid}-{nr}", nr, "belegt", "belegt", b_von, b_bis,
                                     [bid], text="belegt", ganztaegig=ganztaegig))
    return ergebnis


def daten(session: Session, benutzer, von, bis, personen_ids, ansicht: str = "woche") -> dict:
    """Antwort für GET /kalender/daten.json: alle Einträge der Personen im Zeitraum
    (von/bis einschließlich, Tage). Keine Betreffs fremder Outlook-Einträge."""
    start = time.perf_counter()
    von_tag, bis_tag = _tag(von), _tag(bis)
    if von_tag is None:
        von_tag = date.today()
    if bis_tag is None or bis_tag < von_tag:
        bis_tag = von_tag
    if (bis_tag - von_tag).days > MAX_TAGE:
        bis_tag = von_tag + timedelta(days=MAX_TAGE)
    von_dt = datetime.combine(von_tag, datetime.min.time())
    bis_dt = datetime.combine(bis_tag, datetime.min.time()) + timedelta(days=1)
    ids = []
    for p in personen_ids or []:
        try:
            nr = int(p)
        except (TypeError, ValueError):
            continue
        if nr and nr not in ids:
            ids.append(nr)
    erlaubt = erlaubte_ids(session, benutzer)
    if erlaubt is not None:
        ids = [i for i in ids if i in erlaubt]
    ids = ids[:MAX_PERSONEN]
    lead_ok = darf_lead_termine(session, benutzer)
    projekt_ok = darf_projekt_termine(session, benutzer)
    eintraege = []
    eintraege += _vot_eintraege(session, benutzer, ids, von_dt, bis_dt, lead_ok)
    eintraege += _projekt_eintraege(session, benutzer, ids, von_dt, bis_dt, projekt_ok)
    eintraege += _abwesenheit_eintraege(session, benutzer, ids, von_tag, bis_tag)
    eintraege += _belegt_eintraege(session, ids, von_dt, bis_dt)
    eintraege.sort(key=lambda e: (e["beginn"], e["quelle"], str(e["id"])))
    raster_von, raster_bis = tageszeiten(session)
    heute = date.today()
    tage = []
    tag = von_tag
    while tag <= bis_tag:
        tage.append({"datum": tag.isoformat(), "wochentag": tag.weekday(),
                     "wochenende": tag.weekday() >= 5, "heute": tag == heute})
        tag += timedelta(days=1)
    return {"von": von_tag.isoformat(), "bis": bis_tag.isoformat(), "ansicht": ansicht,
            "tage": tage, "raster": {"von": raster_von, "bis": raster_bis, "schritt": RASTER_MIN},
            "personen": ids, "eintraege": eintraege,
            "nur_lesen": nur_lesen(benutzer),
            "rechte": {"lead": lead_ok, "projekt": projekt_ok},
            "dauer_ms": round((time.perf_counter() - start) * 1000, 1)}


# --- Verschieben (Drag) ---------------------------------------------------------------

def _antwort(ok: bool, meldung: str, konflikte=None, **weitere) -> dict:
    a = {"ok": bool(ok), "meldung": meldung, "konflikte": list(konflikte or [])}
    a.update(weitere)
    return a


def _vot_verschieben(session: Session, benutzer, termin: VotTermin, beginn: datetime,
                     person_id: int | None, bestaetigt: bool) -> dict:
    from app import lead_termin, lead_v5
    lead_ok = darf_lead_termine(session, benutzer)
    if not _vot_recht(session, benutzer, termin, lead_ok):
        if termin.quelle == "monday":
            return _antwort(False, "monday-Termin – bitte in monday ändern.")
        if (termin.typ or "vot") == "sperrzeit":
            return _antwort(False, "Sperrzeiten werden in „Meine Termine“ gepflegt.")
        if termin.status not in OFFENE_VOT_STATUS:
            return _antwort(False, "Termin ist nicht mehr aktiv.")
        return _antwort(False, KEIN_RECHT)
    if not lead_v5.terminierung_aktiv(session):
        return _antwort(False, lead_v5.TESTPHASE_HINWEIS)
    vorgang = session.get(Vorgang, termin.vorgang_id)
    if vorgang is None:
        return _antwort(False, "Vorgang des Termins fehlt.")
    ad_id = int(person_id or termin.ad_id or 0)
    if not ad_id:
        return _antwort(False, "Kein Vertriebler am Termin.")
    hv_id = lead_termin.hv_nur_eigene(session, benutzer)
    if hv_id and ad_id != hv_id:
        return _antwort(False, "Handelsvertreter buchen nur den eigenen Kalender.")
    if not lead_ok and ad_id != benutzer.id:
        return _antwort(False, "Der Termin kann nur im eigenen Kalender bleiben.")
    beginn = viertelstunde(beginn)
    typ = termin.typ or "vot"
    kunde = session.get(Kunde, vorgang.kunde_id)
    person = session.get(Benutzer, ad_id)
    if person is None or not person.aktiv:
        return _antwort(False, "Person nicht gefunden oder inaktiv.")
    if typ != "vot":
        # Vorab-Gespräch (Telefon/Teams): Zeit direkt ändern – wie lm_termin.termin_verschieben
        from app import kalender as kalender_modul
        dauer_standard = lead_termin._int(lead_termin.parameter(session, "vorab_dauer_min", "30"), 30)
        dauer = ((termin.ende - termin.beginn) if termin.ende and termin.beginn
                 else timedelta(minutes=dauer_standard))
        alt = termin.beginn
        war_vorgemerkt = termin.status == lead_termin.STATUS_VORGEMERKT
        termin.beginn, termin.ende, termin.ad_id = beginn, beginn + dauer, ad_id
        if war_vorgemerkt:
            termin.status = "geplant"
        name = TERMIN_TYP_NAMEN.get(typ, typ)
        lead_kern.aktivitaet(session, vorgang.id, "termin",
                             f"{name} im Mitarbeiter-Kalender verschoben: "
                             f"{alt:%d.%m.%Y %H:%M} → {beginn:%d.%m.%Y %H:%M} ({person.name})",
                             benutzer=benutzer)
        if kunde is not None:
            lead_kern.benachrichtigen(session, [person.id],
                                      f"{name} {beginn:%d.%m. %H:%M}: {kunde.anzeige_name}",
                                      f"/lead-management/lead/{vorgang.id}", art="terminaenderung")
        session.flush()
        # bestehender Outlook-Hook (O reiht nur noch Aufträge ein; Sitzung wird darin freigegeben)
        kalender_modul.termin_aendern(session, termin, vorgang, kunde, person)
        return _antwort(True, f"{name} verschoben auf {beginn:%d.%m.%Y %H:%M}.")
    objekt = lead_termin.objekt_holen(session, vorgang, termin.objekt_id, anlegen=False)
    lead_ort = lead_termin.objekt_ort(session, vorgang, objekt)
    # Nachtrag 15.10.2026 (K-R6): Drag in die Zeile eines anderen Vertrieblers = Umbuchung mit
    # Terminänderungs-Mail an den Kunden – nur nach ausdrücklicher Bestätigung
    if ad_id != int(termin.ad_id or 0) and not bestaetigt:
        return _antwort(False, f"Vertriebler wechseln zu {person.name}? Der Termin wird umgebucht, "
                        "der Kunde erhält eine Terminänderungs-Mail.", [], bestaetigung_noetig=True)
    k = lead_termin.konflikte(session, ad_id, beginn, lead_ort=lead_ort, ignorieren_id=termin.id)
    if k["sperren"]:
        return _antwort(False, "Nicht möglich – " + "; ".join(k["texte"]), k["texte"])
    if k["warnen"] and not bestaetigt:
        return _antwort(False, "Konflikte – bitte bestätigen.", k["texte"], bestaetigung_noetig=True)
    war_gebucht = termin.status in lead_termin.AKTIVE_STATUS
    alt_beginn = termin.beginn
    neu, meldung, vorgemerkt = lead_termin.termin_anlegen(
        session, vorgang, ad_id, beginn, benutzer=benutzer, quelle="manuell",
        umbuchen_id=termin.id, objekt_id=termin.objekt_id)
    if neu is None:
        session.rollback()
        return _antwort(False, meldung)
    lead_kern.aktivitaet(session, vorgang.id, "termin",
                         f"Vor-Ort-Termin im Mitarbeiter-Kalender verschoben: "
                         f"{alt_beginn:%d.%m.%Y %H:%M} → {beginn:%d.%m.%Y %H:%M} ({person.name})",
                         benutzer=benutzer)
    if war_gebucht and alt_beginn and alt_beginn > datetime.now():
        lead_termin.slot_frei_melden(session, termin, benutzer=benutzer)
    text = ("Termin umgebucht." if not vorgemerkt else meldung)
    if k["warnen"]:
        text += " Hinweis: " + "; ".join(k["texte"]) + "."
    return _antwort(True, text, k["texte"] if k["warnen"] else [], neu_id=neu.id)


def _projekt_termin_setzen(session: Session, termin: ProjektTermin, beginn: datetime,
                           ende: datetime | None, benutzer) -> tuple[bool, str, list[str]]:
    """Rückfall ohne Vertrag S: Zeitraum setzen, Fälligkeiten nachberechnen, Verlauf."""
    from app import projektierung as pj
    from app.models import Gewerk
    alt_text = pj.termin_zeitraum_text(termin)
    termin.beginn, termin.ende = beginn, ende
    termin.dauer_tage = max(1, ((termin.ende or termin.beginn).date() - termin.beginn.date()).days + 1)
    gewerk = session.get(Gewerk, termin.gewerk_id) if termin.gewerk_id else None
    nachberechnet = pj.faelligkeiten_nachberechnen(session, gewerk) if gewerk is not None else 0
    konflikte: list[str] = []
    if termin.team_id and termin.typ == "montage":
        konflikte += pj.team_konflikte(session, termin.team_id, beginn, ende or beginn,
                                       ausser_termin_id=termin.id)
    konflikte += pj.person_konflikte(session, pj.besetzung_ids(session, termin.id), beginn,
                                     ende or beginn, ausser_termin_id=termin.id)
    if termin.projekt_id:
        pj.verlauf(session, termin.projekt_id,
                   f"Termin {pj.termin_art_name(termin)} im Mitarbeiter-Kalender verschoben: "
                   f"{alt_text} → {pj.termin_zeitraum_text(termin)}"
                   + (f" – {nachberechnet} Fälligkeiten nachberechnet" if nachberechnet else ""),
                   benutzer=benutzer, gewerk_id=termin.gewerk_id)
    elif getattr(termin, "vorgang_id", None):
        from app import notizen
        try:
            notizen.notiz_anlegen(session, termin.vorgang_id, benutzer,
                                  f"Service-Einsatz im Mitarbeiter-Kalender verschoben: {alt_text} → "
                                  f"{pj.termin_zeitraum_text(termin)}", herkunft="projektierung")
        except Exception:   # noqa: BLE001 – Verlauf am Vorgang ist Beiwerk
            pass
    session.flush()
    return True, f"Termin verschoben auf {pj.termin_zeitraum_text(termin)}.", konflikte


def _projekt_verschieben(session: Session, benutzer, termin: ProjektTermin, beginn: datetime,
                         ende: datetime | None, person_id: int | None, bestaetigt: bool) -> dict:
    from app import projektierung as pj
    if not darf_projekt_termine(session, benutzer):
        return _antwort(False, KEIN_RECHT)
    if termin.beginn is None:
        return _antwort(False, "Termin ohne Datum.")
    personen = set(pj.besetzung_ids(session, termin.id))
    if termin.person_id:
        personen.add(termin.person_id)
    if person_id and personen and person_id not in personen:
        return _antwort(False, "Besetzung bitte in der Projektakte ändern – der Termin bleibt bei "
                               "seinen Personen.")
    dauer = (termin.ende - termin.beginn) if termin.ende else None
    if termin.ganztaegig:
        neu_beginn = datetime.combine(beginn.date(), datetime.min.time())
    else:
        neu_beginn = viertelstunde(beginn)
    if ende is not None and not termin.ganztaegig:
        neu_ende = viertelstunde(ende) if ende > neu_beginn else None
    else:
        neu_ende = (neu_beginn + dauer) if dauer is not None else None
    if neu_beginn == termin.beginn and neu_ende == termin.ende:
        return _antwort(True, "Termin unverändert.")
    konflikte: list[str] = []
    if termin.team_id and termin.typ == "montage":
        konflikte += pj.team_konflikte(session, termin.team_id, neu_beginn, neu_ende or neu_beginn,
                                       ausser_termin_id=termin.id)
    konflikte += pj.person_konflikte(session, list(personen), neu_beginn, neu_ende or neu_beginn,
                                     ausser_termin_id=termin.id)
    if konflikte and not bestaetigt:
        return _antwort(False, "Konflikte – bitte bestätigen.", konflikte, bestaetigung_noetig=True)
    verschieben = getattr(pj, "termin_verschieben", None)
    vertrag = False
    if callable(verschieben):
        try:
            parameter = inspect.signature(verschieben).parameters
            vertrag = "ende" in parameter and "beginn" in parameter
        except (TypeError, ValueError):
            vertrag = False
    if vertrag:
        ergebnis = verschieben(session, termin, neu_beginn, neu_ende, benutzer)
        try:
            ok, meldung, weitere = ergebnis
        except (TypeError, ValueError):
            ok, meldung, weitere = True, str(ergebnis), []
        if not ok:
            return _antwort(False, meldung or "Verschieben nicht möglich.", weitere)
        return _antwort(True, meldung or "Termin verschoben.", list(weitere or []) or konflikte)
    ok, meldung, weitere = _projekt_termin_setzen(session, termin, neu_beginn, neu_ende, benutzer)
    # bestehender Outlook-Hook wie beim Kalender-Drop der Projektierung (best effort; die
    # Funktion gibt die Sitzung vor dem Netzaufruf frei – O reiht künftig nur Aufträge ein)
    try:
        from app import outlook_kalender
        outlook_kalender.event_senden(session, termin)
    except Exception:   # noqa: BLE001
        pass
    return _antwort(ok, meldung, weitere or konflikte)


def verschieben(session: Session, benutzer, quelle: str, termin_id, beginn, ende=None,
                person_id=None, bestaetigt: bool = False) -> dict:
    """Drag im Kalender: Tool-Termin verschieben (Rechte wie im Modul). Antwort
    {ok, meldung, konflikte[, bestaetigung_noetig]} – der Aufrufer committet bei ok."""
    if benutzer is None or nur_lesen(benutzer):
        return _antwort(False, NUR_LESEN_TEXT if benutzer is not None else KEIN_RECHT)
    beginn_dt = _zeit(beginn)
    if beginn_dt is None:
        return _antwort(False, "Neuer Beginn fehlt oder ist nicht lesbar.")
    ende_dt = _zeit(ende) if ende else None
    try:
        nr = int(termin_id)
    except (TypeError, ValueError):
        return _antwort(False, "Termin nicht gefunden.")
    try:
        person = int(person_id) if person_id not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        person = None
    quelle = (quelle or "").strip().lower()
    if quelle == "vot":
        termin = session.get(VotTermin, nr)
        if termin is None:
            return _antwort(False, "Termin nicht gefunden.")
        return _vot_verschieben(session, benutzer, termin, beginn_dt, person, bool(bestaetigt))
    if quelle in ("projekt", "service"):
        termin = session.get(ProjektTermin, nr)
        if termin is None:
            return _antwort(False, "Termin nicht gefunden.")
        return _projekt_verschieben(session, benutzer, termin, beginn_dt, ende_dt, person,
                                    bool(bestaetigt))
    if quelle in ("abwesenheit", "belegt"):
        return _antwort(False, "Abwesenheiten und Outlook-Belegtzeiten lassen sich hier nicht "
                               "verschieben.")
    return _antwort(False, "Unbekannte Terminquelle.")


# --- Doppelklick: Ziel-Dialog des Moduls (Lead-Assistent, Projektakte, Vorgangsakte) ------

def neu_art(gruppe: str) -> str:
    """Welche Suche der Doppelklick für eine Gruppe öffnet: lead | projekt | vorgang."""
    if gruppe in VERTRIEB_GRUPPEN or gruppe == "innendienst":
        return "lead"
    if gruppe in ("service_heizung", "service_elektro"):
        return "vorgang"
    return "projekt"


def suche(session: Session, benutzer, q: str, art: str, person_id=None, beginn=None) -> list[dict]:
    """Treffer für den Doppelklick: Kunden/Leads über app.suche (Rechte des Moduls), Projekte
    über Nummer/Kunde; jeder Treffer trägt den Link in den passenden Termin-Dialog mit
    vorbelegtem Datum und Person (Query-Parameter)."""
    q = " ".join((q or "").split())
    art = (art or "lead").strip().lower()
    if len(q) < 2 or benutzer is None or nur_lesen(benutzer):
        return []
    beginn_dt = _zeit(beginn)
    person = int(person_id) if str(person_id or "").isdigit() else None
    datum = beginn_dt.strftime("%Y-%m-%d") if beginn_dt else ""
    uhrzeit = beginn_dt.strftime("%H:%M") if beginn_dt else ""
    treffer = []
    if art in ("lead", "vorgang"):
        from app import suche as suche_modul
        if not suche_modul.darf_suchen(benutzer):
            return []
        for t in suche_modul.suchen(session, q, benutzer, limit=SUCHE_MAX):
            if not t.get("vorgang_id"):
                continue
            if art == "vorgang":
                link = f"/vorgaenge/{t['vorgang_id']}?termin_neu=service&beginn={datum}&uhrzeit={uhrzeit}"
                link += f"&person={person}" if person else ""
                link += "#termine"
            else:
                link = f"/lead-management/lead/{t['vorgang_id']}/termin?ad_id={person or ''}"
                link += f"&woche={datum}&beginn={datum}T{uhrzeit}" if datum else ""
            treffer.append({"name": t["name"], "ort": " ".join(x for x in (t.get("plz"), t.get("ort")) if x),
                            "zusatz": t.get("verfolgung_text") or "", "link": link})
        return treffer
    if art == "projekt":
        if not darf_projekt_termine(session, benutzer):
            return []
        muster = f"%{q}%"
        zeilen = (session.query(Projekt, Kunde)
                  .join(Kunde, Kunde.id == Projekt.kunde_id)
                  .filter(or_(Projekt.nummer.ilike(muster), Kunde.nachname.ilike(muster),
                              Kunde.firma.ilike(muster), Kunde.vorname.ilike(muster),
                              Projekt.ausfuehrung_ort.ilike(muster)))
                  .order_by(Projekt.id.desc()).limit(SUCHE_MAX).all())
        for p, k in zeilen:
            link = (f"/projektierung/projekt/{p.id}?termin_neu=1&beginn={datum}&uhrzeit={uhrzeit}"
                    + (f"&person={person}" if person else "") + "#termine")
            treffer.append({"name": f"{p.nummer} · {k.anzeige_name}", "ort": p.ausfuehrung_ort or k.ort or "",
                            "zusatz": p.status_cache or "", "link": link})
    return treffer


def seiten_kontext(session: Session, benutzer, gruppe_param: str = "", person_param: str = "",
                   datum_param: str = "", ansicht_param: str = "", q: str = "") -> dict:
    """Kontext der Seite /kalender: Katalog, Gruppen mit Zählern, Vorbelegung, Raster."""
    einstieg = einstieg_bestimmen(gruppe_param, benutzer)
    katalog = personen_katalog(session, benutzer)
    auswahl = auswahl_laden(session, benutzer, einstieg)
    zaehler: dict[str, int] = {key: 0 for key, _ in GRUPPEN}
    for p in katalog:
        zaehler[p["gruppe"]] = zaehler.get(p["gruppe"], 0) + 1
    person_id = int(person_param) if str(person_param or "").isdigit() else None
    person = next((p for p in katalog if p["id"] == person_id), None) if person_id else None
    gruppen = list(auswahl["gruppen"])
    if person is not None and person["gruppe"] not in gruppen:
        gruppen.append(person["gruppe"])
    if einstieg == "eigene":
        gruppen = sorted({p["gruppe"] for p in katalog}, key=lambda g: GRUPPEN_REIHENFOLGE.get(g, 99))
    ansicht = ansicht_param if ansicht_param in ANSICHTEN else auswahl["ansicht"]
    datum = _tag(datum_param) or date.today()
    raster_von, raster_bis = tageszeiten(session)
    return {
        "einstieg": einstieg,
        "personen": katalog,
        "gruppen": [{"key": key, "name": name, "anzahl": zaehler.get(key, 0),
                     "neu_art": neu_art(key)} for key, name in GRUPPEN],
        "auswahl": {"gruppen": gruppen, "wochenende": auswahl["wochenende"], "ansicht": ansicht,
                    "datum": datum.isoformat(), "person": person_id if person else None,
                    "q": (q or "").strip()[:60], "einstieg": einstieg, "gemerkt": auswahl["gemerkt"]},
        "raster": {"von": raster_von, "bis": raster_bis, "schritt": RASTER_MIN},
        "nur_lesen": nur_lesen(benutzer),
        "rechte": {"lead": darf_lead_termine(session, benutzer),
                   "projekt": darf_projekt_termine(session, benutzer)},
        "heute": date.today().isoformat(),
    }
