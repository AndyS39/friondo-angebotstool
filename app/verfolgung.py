# v32 (PLAN_V19 Phase 163): Verfolgungsstatus je Vorgang (fünf Stufen), Dialog
# „Nächster Schritt“ nach dem Anruf (Abgelehnt · Bestellung kommt · Nochmal anrufen),
# „Bestellung angekündigt“ (Heiße Kunden, ID-Kachel, ID-Glocke) und die Migration der
# Ablehnungsgründe des Angebotstools auf die fünf Lead-Gründe.
#
# Vertrag (Agent N schreibt; M (Mein Tag / Versand-Hook / Angebotsliste), die Suche
# (app/suche.py per getattr) und die Router nutzen):
#   STATUS, STATUS_TEXTE, STATUS_FARBEN, status_text(status) -> str
#   filter_anwenden(abfrage, status, vorgaenge_map=None)
#       – SQLAlchemy-Query auf `Vorgang` (Filter direkt) oder auf `Angebot` (Join über
#         angebote.vorgang_id); eine LISTE von Angeboten/Vorgängen wird in Python gefiltert
#         (Angebote brauchen dazu `vorgaenge_map` {id: Vorgang} oder ein Attribut
#         `vorgang`). Unbekannter Status → unverändert zurück.
#   heisse_vorgaenge(session, benutzer_id=None) -> list[Vorgang]
#       – Hot-Ampel heiß ODER Status bestellung_angekuendigt, ohne Demo, nicht archiviert;
#         mit benutzer_id nur „eigene“ Vorgänge (vorgaenge.gehoert_benutzer).
#   setzen(session, vorgang, status, benutzer=None, text="") -> bool
#       – setzt nur vorgaenge.verfolgung_status (kein Nebeneffekt auf Ampel/Wiedervorlage);
#         `text` schreibt zusätzlich eine System-Notiz in den Chat. True = geändert.
#   ableiten(session, vorgang) -> str  und  nach_angebotsstatus(session, angebot, benutzer=None)
#       – Status aus den Angeboten des Vorgangs (Annahme-/Signatur-/Ablehnungsweg).
#   naechster_schritt(session, vorgang, schritt, benutzer, grund_id=None, freitext="",
#                     wann="", datum=None, notiz="", heute=None) -> (ok, meldung, daten)
#   rueckgaengig(session, vorgang, token, benutzer) -> (ok, meldung, daten)
#   dialog_kontext(session, vorgang, zurueck="") -> dict  (Variablen des Partials
#       templates/vorgaenge/_naechster_schritt.html: vorgang, gruende, naechster_3wt, ziel)
#   aktive_gruende(session), bestellung_angekuendigt_anzahl(session) (ID-Kachel)
#   migration_v32_verfolgung(session) -> list[str]  (idempotent, migrate.py ruft sie auf)
#
# Wiedervorlagen laufen über den Vertrag von Agent M (`nachfassen.wiedervorlage_setzen`);
# solange das Modul fehlt, setzt der Rückfall hier die Spalten direkt. Reine
# Datenbankarbeit – Netzaufrufe (monday-Wert, Outlook-Storno) liegen in den gerufenen
# Bestandsfunktionen, die die Sitzung vorher freigeben (v27-Regel).
from __future__ import annotations

import secrets
import threading
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app import werktage
from app.models import (AblehnungsGrund, Angebot, AngebotsNotiz, Benachrichtigung,
                        Benutzer, Erfassung, Kunde, Vorgang, angebot_status_setzen,
                        einstellung_holen, einstellung_setzen)

STATUS = ("versendet", "nachgefasst", "bestellung_angekuendigt", "angenommen", "abgelehnt")
STATUS_TEXTE = {
    "versendet": "Versendet",
    "nachgefasst": "Nachgefasst",
    "bestellung_angekuendigt": "Bestellung angekündigt",
    "angenommen": "Angenommen",
    "abgelehnt": "Abgelehnt",
}
# Farbstufe je Status (Status-Tokens v30: --status-<farbe>); das Makro verfolgung_chip
# in _komponenten.html nutzt die Klasse .vf-<status> aus app/static/verfolgung.css
STATUS_FARBEN = {
    "versendet": "blau",
    "nachgefasst": "grau",
    "bestellung_angekuendigt": "orange",
    "angenommen": "gruen",
    "abgelehnt": "rot",
}
SCHRITTE = ("abgelehnt", "bestellung", "nochmal")
NOCHMAL_WERKTAGE = 3            # Entscheidung 13.10.2026: „Nochmal anrufen“ in 3 Werktagen
BESTELLUNG_WERKTAGE = 7         # [ANNAHME] Bestellung angekündigt → Wiedervorlage heute + 7 Werktage
WIEDERVORLAGE_ART_NOCHMAL = "nochmal_anrufen"
WIEDERVORLAGE_ART_BESTELLUNG = "bestellung_angekuendigt"
GLOCKE_ART = "verfolgung"       # ID-Glocke „Bestellung angekündigt“ – ohne Mail (direkt angelegt)
HERKUNFT = "Verfolgung"         # Kennzeichen der System-Notizen (wie vorgaenge.verfolgung_setzen)
RUECKGAENGIG_SEKUNDEN = 10      # [ANNAHME] Anzeige des Rückgängig-Links (wie Lead-Dashboard v31)
RUECKGAENGIG_GUELTIG_S = 600    # der Server hält den Schnappschuss 10 Minuten
WOCHENTAGE_KURZ = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")

# Die fünf Ablehnungsgründe = Lead-Gründe „verloren“ aus leadmanagement_logik_v1.xlsx
# (Blatt Gruende, Schreibweise der Excel; der Plan nennt sie klein geschrieben – beide
# Pflegeorte sollen dieselben Texte tragen, deshalb die Excel-Schreibweise; Abgleich
# gegen die Excel bei der Migration mit Meldung)
GRUENDE_V32 = ("Zu teuer", "Kein Interesse mehr", "Bleibt bei Öl/Gas",
               "Woanders unterschrieben", "Sonstiges")
GRUENDE_FREITEXT_PFLICHT = ("Sonstiges",)
AUTO_GRUND = "90 Tage Ablauf"   # Systemgrund des Prüflaufs (app/ablauf_pruefung.AUTO_GRUND)
MIGRATION_MARKER = "migration_v32_ablehnungsgruende"
_ANGEBOT_VERSENDET = ("Versendet", "Versendet (extern)")


# --- Status-Texte, Filter, Listen ------------------------------------------------------

def status_text(status: str | None) -> str:
    """Anzeigetext der Stufe; unbekannt/leer → leerer Text (Suche nutzt den Rückfall)."""
    return STATUS_TEXTE.get((status or "").strip(), "")


def status_farbe(status: str | None) -> str:
    return STATUS_FARBEN.get((status or "").strip(), "grau")


def filter_anwenden(abfrage, status: str, vorgaenge_map: dict | None = None):
    """Verfolgungsfilter der Angebotsliste (M ruft es im Router): siehe Modulkopf."""
    status = (status or "").strip()
    if status not in STATUS:
        return abfrage
    beschreibungen = getattr(abfrage, "column_descriptions", None)
    if beschreibungen is not None:                      # SQLAlchemy-Query
        entitaet = beschreibungen[0].get("entity") if beschreibungen else None
        if entitaet is Vorgang:
            return abfrage.filter(Vorgang.verfolgung_status == status)
        if entitaet is Angebot:
            return (abfrage.join(Vorgang, Vorgang.id == Angebot.vorgang_id)
                    .filter(Vorgang.verfolgung_status == status))
        return abfrage
    ergebnis = []                                        # Liste von Objekten
    for element in abfrage:
        if isinstance(element, Vorgang):
            wert = element.verfolgung_status
        else:
            vorgang = None
            if vorgaenge_map is not None:
                vorgang = vorgaenge_map.get(getattr(element, "vorgang_id", None))
            if vorgang is None:
                vorgang = getattr(element, "vorgang", None)
            wert = getattr(vorgang, "verfolgung_status", "") if vorgang is not None else ""
        if (wert or "") == status:
            ergebnis.append(element)
    return ergebnis


def _basis_abfrage(session: Session):
    from app import leadmanagement
    abfrage = leadmanagement.ohne_demo(session.query(Vorgang))
    try:   # v31 (Phase 154): Archiv ist eine Lead-Sicht – Mein Tag/Heiße Kunden ebenso
        from app import lead_archiv
        abfrage = lead_archiv.filter_aktiv(abfrage)
    except (ImportError, AttributeError):
        pass
    return abfrage


def heisse_vorgaenge(session: Session, benutzer_id: int | None = None) -> list[Vorgang]:
    """Block „Heiße Kunden“ (Mein Tag): Hot-Ampel heiß oder Bestellung angekündigt –
    nächste Wiedervorlage zuerst, ohne Wiedervorlage danach (jüngste zuerst)."""
    abfrage = _basis_abfrage(session).filter(
        (Vorgang.verfolgung_ampel == "heiss")
        | (Vorgang.verfolgung_status == "bestellung_angekuendigt"))
    vorgaenge = abfrage.all()
    if benutzer_id:
        from app import vorgaenge as vorgaenge_modul
        vorgaenge = [v for v in vorgaenge
                     if vorgaenge_modul.gehoert_benutzer(session, v, benutzer_id)]
    vorgaenge.sort(key=lambda v: (v.wiedervorlage_am is None,
                                  v.wiedervorlage_am or datetime.max, -v.id))
    return vorgaenge


def bestellung_angekuendigt_anzahl(session: Session) -> int:
    """ID-Kachel „Bestellung angekündigt“ (Startseite): Anzahl Vorgänge mit dem Status."""
    return (_basis_abfrage(session)
            .filter(Vorgang.verfolgung_status == "bestellung_angekuendigt").count())


def aktive_gruende(session: Session) -> list[AblehnungsGrund]:
    return (session.query(AblehnungsGrund)
            .filter(AblehnungsGrund.aktiv.is_(True))
            .order_by(AblehnungsGrund.sort, AblehnungsGrund.id).all())


def grund_pruefen(session: Session, grund_id, freitext: str = "") -> tuple[AblehnungsGrund | None, str]:
    """Grund aus der Angebotstool-Liste (nur aktive) + Pflicht-Freitext prüfen."""
    try:
        nummer = int(grund_id or 0)
    except (TypeError, ValueError):
        nummer = 0
    grund = session.get(AblehnungsGrund, nummer) if nummer else None
    if grund is None or not grund.aktiv:
        return None, "Bitte einen Grund der Ablehnung wählen."
    if grund.freitext_pflicht and not (freitext or "").strip():
        return None, f"Beim Grund „{grund.name}“ ist der Freitext Pflicht."
    return grund, ""


# --- Status setzen / ableiten ----------------------------------------------------------

def _system_notiz(session: Session, vorgang: Vorgang, text: str, benutzer=None):
    """System-Aktivität im Notizen-Chat (Autor „System“, Kennzeichen Verfolgung; der
    auslösende Benutzer steht im Text) – keine zweite Notizspur."""
    from app import notizen
    name = getattr(benutzer, "name", "") or ""
    voll = f"{text} ({name})" if name else text
    return notizen.notiz_anlegen(session, vorgang.id, None, voll, herkunft=HERKUNFT)


def setzen(session: Session, vorgang: Vorgang, status: str, benutzer=None,
           text: str = "") -> bool:
    status = (status or "").strip()
    if vorgang is None or status not in STATUS:
        return False
    geaendert = (vorgang.verfolgung_status or "") != status
    vorgang.verfolgung_status = status
    if text:
        _system_notiz(session, vorgang, text, benutzer)
    session.flush()
    return geaendert


def _angebote_des_vorgangs(session: Session, vorgang_id: int) -> list[Angebot]:
    return (session.query(Angebot)
            .filter(Angebot.vorgang_id == vorgang_id, Angebot.archiviert.is_(False),
                    Angebot.status != "Überholt").all())


def ableiten(session: Session, vorgang: Vorgang) -> str:
    """Stufe aus den Angeboten des Vorgangs (nicht archiviert, nicht überholt):
    Angenommen → angenommen; sonst offenes Versendetes → versendet (bestehendes
    nachgefasst / bestellung_angekuendigt bleibt stehen); sonst nur Abgelehnte →
    abgelehnt; sonst leer (Entwürfe zählen nicht)."""
    angebote = _angebote_des_vorgangs(session, vorgang.id)
    aktuell = (vorgang.verfolgung_status or "").strip()
    if any(a.status == "Angenommen" for a in angebote):
        return "angenommen"
    if any(a.status in _ANGEBOT_VERSENDET for a in angebote):
        return aktuell if aktuell in ("nachgefasst", "bestellung_angekuendigt") else "versendet"
    if any(a.status == "Abgelehnt" for a in angebote):
        return "abgelehnt"
    return ""


def nach_angebotsstatus(session: Session, angebot: Angebot, benutzer=None) -> str:
    """Nach einem Statuswechsel am Angebot (Annahme-/Signaturweg, ID-Dialog „Grund der
    Ablehnung“, AD-Statuswechsel, Versand): Vorgangsstufe nachziehen. Liefert die Stufe."""
    if angebot is None or not angebot.vorgang_id:
        return ""
    vorgang = session.get(Vorgang, angebot.vorgang_id)
    if vorgang is None:
        return ""
    status = ableiten(session, vorgang)
    if status:
        setzen(session, vorgang, status, benutzer)
    return status


# --- Wiedervorlage (Vertrag M: nachfassen.wiedervorlage_setzen) ------------------------

def _datum(wert) -> date | None:
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    roh = str(wert or "").strip()
    for muster in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(roh, muster).date()
        except ValueError:
            continue
    return None


def datum_text(tag: date | None) -> str:
    """„Mi 14.10.“ – Wochentag kurz + Tag.Monat."""
    tag = _datum(tag)
    if tag is None:
        return ""
    return f"{WOCHENTAGE_KURZ[tag.weekday()]} {tag.strftime('%d.%m.')}"


def naechster_3wt(heute: date | None = None) -> date:
    return werktage.plus_werktage(_datum(heute) or date.today(), NOCHMAL_WERKTAGE)


def wiedervorlage_setzen(session: Session, vorgang: Vorgang, datum, benutzer_id, art: str) -> None:
    """Vertrag M (`nachfassen.wiedervorlage_setzen`) per getattr; Rückfall setzt die
    bestehenden Spalten wiedervorlage_am (ohne Uhrzeit), wiedervorlage_benutzer_id,
    wiedervorlage_art direkt."""
    tag = _datum(datum)
    try:
        from app import nachfassen
        funktion = getattr(nachfassen, "wiedervorlage_setzen", None)
    except ImportError:
        funktion = None
    if funktion is not None:
        funktion(session, vorgang, tag, benutzer_id, art)
        return
    vorgang.wiedervorlage_am = (datetime(tag.year, tag.month, tag.day) if tag else None)
    vorgang.wiedervorlage_benutzer_id = benutzer_id
    vorgang.wiedervorlage_art = (art or "")[:30]


def wiedervorlage_leeren(vorgang: Vorgang) -> None:
    vorgang.wiedervorlage_am = None
    vorgang.wiedervorlage_benutzer_id = None
    vorgang.wiedervorlage_art = ""


def _verantwortlicher(vorgang: Vorgang, benutzer) -> int | None:
    """Der AD ruft an (Entscheidung 13.10.2026): Verantwortlicher = AD des Vorgangs, sonst
    der handelnde Außendienstler, sonst der bisherige Verantwortliche (None = Innendienst)."""
    if getattr(vorgang, "ad_id", None):
        return vorgang.ad_id
    if benutzer is not None and getattr(benutzer, "rolle", "") == "aussendienst":
        return benutzer.id
    return vorgang.wiedervorlage_benutzer_id


# --- Rückgängig (Schnappschuss je Schritt, 10 Minuten im Speicher) ---------------------

_SCHNAPPSCHUESSE: dict[str, dict] = {}
_SPERRE = threading.Lock()


def _schnappschuss(session: Session, vorgang: Vorgang, schritt: str, benutzer) -> dict:
    angebote = [{"id": a.id, "status": a.status, "grund": a.ablehnungsgrund,
                 "grund_text": a.ablehnungsgrund_text, "abgelehnt_am": a.abgelehnt_am}
                for a in _angebote_des_vorgangs(session, vorgang.id)]
    erfassungen = [{"id": e.id, "status": e.status}
                   for e in session.query(Erfassung).filter(Erfassung.vorgang_id == vorgang.id)]
    return {"zeit": datetime.now(), "vorgang_id": vorgang.id, "schritt": schritt,
            "benutzer_id": getattr(benutzer, "id", None),
            "vorgang": {"verfolgung_status": vorgang.verfolgung_status,
                        "verfolgung_ampel": vorgang.verfolgung_ampel,
                        "wiedervorlage_am": vorgang.wiedervorlage_am,
                        "wiedervorlage_benutzer_id": vorgang.wiedervorlage_benutzer_id,
                        "wiedervorlage_art": vorgang.wiedervorlage_art,
                        "lead_phase": vorgang.lead_phase,
                        "naechste_aktion_am": vorgang.naechste_aktion_am,
                        "zurueckgestellt_bis": vorgang.zurueckgestellt_bis},
            "angebote": angebote, "erfassungen": erfassungen, "glocken": []}


def _schnappschuss_merken(daten: dict) -> str:
    token = secrets.token_urlsafe(18)
    grenze = datetime.now() - timedelta(seconds=RUECKGAENGIG_GUELTIG_S)
    with _SPERRE:
        for alt in [k for k, v in _SCHNAPPSCHUESSE.items() if v["zeit"] < grenze]:
            _SCHNAPPSCHUESSE.pop(alt, None)
        _SCHNAPPSCHUESSE[token] = daten
    return token


def _schnappschuss_holen(token: str) -> dict | None:
    with _SPERRE:
        daten = _SCHNAPPSCHUESSE.pop(token or "", None)
    if daten is None:
        return None
    if daten["zeit"] < datetime.now() - timedelta(seconds=RUECKGAENGIG_GUELTIG_S):
        return None
    return daten


# --- Die drei Wege ---------------------------------------------------------------------

def _innendienst_ids(session: Session) -> list[int]:
    """[ANNAHME] Empfänger der Glocke „Bestellung angekündigt“: alle aktiven Benutzer der
    Rolle Innendienst; gibt es keinen, die Admins."""
    aktive = session.query(Benutzer).filter(Benutzer.aktiv.is_(True)).all()
    ids = [b.id for b in aktive if b.rolle == "innendienst"]
    return ids or [b.id for b in aktive if b.rolle == "admin"]


def _glocke_innendienst(session: Session, vorgang: Vorgang, kunde) -> list[int]:
    """Glocke direkt anlegen (ohne kern.benachrichtigen → keine Sofort-Mail in
    mail_ausgang; Vorschlag an M: GLOCKE_ART in benachrichtigungen.MAIL_FREIE_ARTEN,
    damit auch der Tagesdigest sie überspringt). Liefert die IDs der Einträge."""
    name = getattr(kunde, "anzeige_name", "") or f"Vorgang {vorgang.id}"
    text = f"Bestellung angekündigt: {name}"[:500]
    link = f"/vorgaenge/{vorgang.id}"
    eintraege = []
    for bid in _innendienst_ids(session):
        eintrag = Benachrichtigung(benutzer_id=bid, text=text, link=link, art=GLOCKE_ART)
        session.add(eintrag)
        eintraege.append(eintrag)
    session.flush()
    return [e.id for e in eintraege]


def _angebote_ablehnen_v8(session: Session, vorgang: Vorgang, grund: str, text: str,
                          benutzer) -> int:
    """Vorgänge ohne Lead-Phase: nur der v8-Angebotsweg – alle versendeten, nicht
    überholten Angebote des Vorgangs auf Abgelehnt mit Grund (Angebotsnotiz, Erfassung
    erledigt, monday-Wert wie routers/angebote.status_aendern)."""
    anzahl = 0
    for angebot in _angebote_des_vorgangs(session, vorgang.id):
        if angebot.status not in _ANGEBOT_VERSENDET:
            continue
        angebot.ablehnungsgrund = (grund or "")[:100]
        angebot.ablehnungsgrund_text = (text or "")[:500]
        angebot_status_setzen(angebot, "Abgelehnt")
        session.add(AngebotsNotiz(
            angebot_id=angebot.id, benutzer_name=getattr(benutzer, "name", "") or "System",
            text="Abgelehnt – Grund: " + angebot.ablehnungsgrund
                 + (f" ({angebot.ablehnungsgrund_text})" if angebot.ablehnungsgrund_text else "")
                 + " · Nächster Schritt"))
        erfassung = session.query(Erfassung).filter(Erfassung.angebot_id == angebot.id).first()
        if erfassung is not None and erfassung.status != "Erledigt (extern)":
            erfassung.status = "Erledigt"
        anzahl += 1
        try:
            from app import monday_rueckspielung
            monday_rueckspielung.wert_aktualisieren(session, angebot, "Ablehnung")
        except Exception:
            pass
    session.flush()
    return anzahl


def naechster_schritt(session: Session, vorgang: Vorgang, schritt: str, benutzer,
                      grund_id=None, freitext: str = "", wann: str = "", datum=None,
                      notiz: str = "", heute: date | None = None) -> tuple[bool, str, dict]:
    """Die drei Wege des Dialogs (Phase 163). Rückgabe (ok, meldung, daten) – daten
    für die JSON-Antwort: status, status_text, ampel, wiedervorlage_am (TT.MM.JJJJ oder
    leer), schritt, rueckgaengig {token, sekunden}. Kein Commit – der Aufrufer committet
    (Route über das _speichern-Muster)."""
    schritt = (schritt or "").strip()
    freitext = (freitext or "").strip()
    notiz = (notiz or "").strip()
    heute = _datum(heute) or date.today()
    if vorgang is None:
        return False, "Vorgang nicht gefunden.", {}
    if schritt not in SCHRITTE:
        return False, "Unbekannter Schritt.", {}
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang.kunde_id else None
    grund = None
    neues_datum = None
    if schritt == "abgelehnt":
        grund, fehler = grund_pruefen(session, grund_id, freitext)
        if grund is None:
            return False, fehler, {}
    elif schritt == "nochmal":
        wann = (wann or "3wt").strip()
        if wann == "3wt":
            neues_datum = naechster_3wt(heute)
        elif wann == "datum":
            neues_datum = _datum(datum)
            if neues_datum is None:
                return False, "Bitte ein Datum (TT.MM.JJJJ) angeben.", {}
            if neues_datum < heute:
                return False, "Das Datum liegt in der Vergangenheit.", {}
        else:
            return False, "Bitte „In 3 Werktagen“ oder ein Datum wählen.", {}
    else:
        neues_datum = werktage.plus_werktage(heute, BESTELLUNG_WERKTAGE)

    schnappschuss = _schnappschuss(session, vorgang, schritt, benutzer)
    # Notiz der Karte zuerst (ein Chat-Eintrag), danach die System-Aktivität
    if notiz:
        from app import notizen
        notizen.notiz_anlegen(session, vorgang.id, benutzer, notiz,
                              herkunft=notizen.herkunft_fuer(benutzer))
    if schritt == "abgelehnt":
        if vorgang.lead_phase:
            # Ablehnung über EINEN Weg (Einfügung 13.10.2026): kern.lead_verloren setzt
            # Verloren, lehnt offene Angebote ab (lead_boards.angebote_ablehnen) und spielt
            # den Wert nach monday zurück
            from app import leadmanagement as kern
            kern.lead_verloren(session, vorgang, grund.name, freitext, benutzer=benutzer)
        else:
            _angebote_ablehnen_v8(session, vorgang, grund.name, freitext, benutzer)
        wiedervorlage_leeren(vorgang)
        vorgang.verfolgung_ampel = "kalt"
        setzen(session, vorgang, "abgelehnt", benutzer)
        text = f"Kunde hat abgelehnt: {grund.name}" + (f" – {freitext}" if freitext else "")
        meldung = f"Abgelehnt gespeichert: {grund.name}."
    elif schritt == "bestellung":
        wiedervorlage_setzen(session, vorgang, neues_datum, _verantwortlicher(vorgang, benutzer),
                             WIEDERVORLAGE_ART_BESTELLUNG)
        vorgang.verfolgung_ampel = "heiss"
        setzen(session, vorgang, "bestellung_angekuendigt", benutzer)
        schnappschuss["glocken"] = _glocke_innendienst(session, vorgang, kunde)
        text = f"Bestellung angekündigt – Wiedervorlage am {neues_datum.strftime('%d.%m.%Y')}"
        meldung = (f"Bestellung angekündigt – Wiedervorlage am "
                   f"{datum_text(neues_datum)} gesetzt.")
    else:
        wiedervorlage_setzen(session, vorgang, neues_datum, _verantwortlicher(vorgang, benutzer),
                             WIEDERVORLAGE_ART_NOCHMAL)
        setzen(session, vorgang, "nachgefasst", benutzer)
        text = f"Nochmal anrufen am {neues_datum.strftime('%d.%m.%Y')}"
        meldung = f"Nochmal anrufen am {datum_text(neues_datum)} gespeichert."
    _system_notiz(session, vorgang, text, benutzer)
    session.flush()
    token = _schnappschuss_merken(schnappschuss)
    return True, meldung, {
        "schritt": schritt,
        "status": vorgang.verfolgung_status,
        "status_text": status_text(vorgang.verfolgung_status),
        "ampel": vorgang.verfolgung_ampel or "",
        "wiedervorlage_am": (vorgang.wiedervorlage_am.strftime("%d.%m.%Y")
                             if vorgang.wiedervorlage_am else ""),
        "rueckgaengig": {"token": token, "sekunden": RUECKGAENGIG_SEKUNDEN},
    }


def rueckgaengig(session: Session, vorgang: Vorgang, token: str, benutzer) -> tuple[bool, str, dict]:
    """[ANNAHME] Rückgängig-Link (10 s) wie im Lead-Dashboard: stellt Stufe, Ampel,
    Wiedervorlage, Lead-Phase und – bei „Abgelehnt“ – die Angebots-/Erfassungsstatus aus
    dem Schnappschuss wieder her, entfernt die ID-Glocken des Schritts und schreibt eine
    System-Notiz. Abgesagte VOT-Termine/stornierte Lead-Mails (lead_verloren) werden nicht
    wiederhergestellt (Hinweis in der Meldung)."""
    daten = _schnappschuss_holen(token)
    if daten is None or vorgang is None or daten["vorgang_id"] != vorgang.id:
        return False, "Rückgängig nicht mehr möglich (abgelaufen).", {}
    for feld, wert in daten["vorgang"].items():
        setattr(vorgang, feld, wert)
    wiederhergestellt = 0
    for a in daten["angebote"]:
        angebot = session.get(Angebot, a["id"])
        if angebot is None or angebot.status == a["status"]:
            continue
        angebot.status = a["status"]
        angebot.ablehnungsgrund = a["grund"] or ""
        angebot.ablehnungsgrund_text = a["grund_text"] or ""
        angebot.abgelehnt_am = a["abgelehnt_am"]
        session.add(AngebotsNotiz(
            angebot_id=angebot.id, benutzer_name=getattr(benutzer, "name", "") or "System",
            text=f"Ablehnung rückgängig gemacht – Status wieder „{angebot.status}“"))
        wiederhergestellt += 1
        if angebot.status in _ANGEBOT_VERSENDET:
            try:
                from app import monday_rueckspielung
                monday_rueckspielung.wert_aktualisieren(session, angebot, "Ablehnung rückgängig")
            except Exception:
                pass
    for e in daten["erfassungen"]:
        erfassung = session.get(Erfassung, e["id"])
        if erfassung is not None and erfassung.status != e["status"]:
            erfassung.status = e["status"]
    for gid in daten.get("glocken") or []:
        glocke = session.get(Benachrichtigung, gid)
        if glocke is not None:
            session.delete(glocke)
    if daten["schritt"] == "abgelehnt" and vorgang.lead_phase:
        from app import leadmanagement as kern
        kern.aktivitaet(session, vorgang.id, "status",
                        "Ablehnung rückgängig gemacht (Nächster Schritt)", benutzer=benutzer)
    namen = {"abgelehnt": "Abgelehnt", "bestellung": "Bestellung angekündigt",
             "nochmal": "Nochmal anrufen"}
    _system_notiz(session, vorgang, f"Rückgängig: „{namen.get(daten['schritt'], daten['schritt'])}“ zurückgenommen",
                  benutzer)
    session.flush()
    meldung = "Rückgängig gemacht."
    if daten["schritt"] == "abgelehnt" and daten["vorgang"].get("lead_phase"):
        meldung += " Abgesagte Termine oder gestoppte Lead-Mails bleiben abgesagt."
    return True, meldung, {
        "schritt": daten["schritt"],
        "status": vorgang.verfolgung_status or "",
        "status_text": status_text(vorgang.verfolgung_status),
        "ampel": vorgang.verfolgung_ampel or "",
        "wiedervorlage_am": (vorgang.wiedervorlage_am.strftime("%d.%m.%Y")
                             if vorgang.wiedervorlage_am else ""),
        "angebote": wiederhergestellt,
    }


# --- Kontext für das Partial -----------------------------------------------------------

def dialog_kontext(session: Session, vorgang: Vorgang, zurueck: str = "",
                   heute: date | None = None) -> dict:
    """Variablen für `{% include "vorgaenge/_naechster_schritt.html" %}`: vorgang,
    gruende (aktive Angebotstool-Gründe), naechster_3wt {datum, text „Mi 14.10.“, iso},
    ziel (Rücksprung ohne JavaScript), heute_iso (min des Datumsfelds)."""
    heute = _datum(heute) or date.today()
    tag = naechster_3wt(heute)
    return {"vorgang": vorgang, "gruende": aktive_gruende(session),
            "naechster_3wt": {"datum": tag, "text": datum_text(tag), "iso": tag.isoformat()},
            "ziel": zurueck or f"/vorgaenge/{vorgang.id}", "heute_iso": heute.isoformat()}


# --- Migration (migrate.py: ("app.verfolgung", "migration_v32_verfolgung")) ------------

def _gruende_migrieren(session: Session) -> list[str]:
    """Einmalig (Marker): die fünf Gründe anlegen/aktivieren, Reihenfolge 1–5,
    „Sonstiges“ mit Pflicht-Freitext; andere Gründe deaktivieren [ANNAHME] außer dem
    Systemgrund „90 Tage Ablauf“. Vorhandene Gründe werden unabhängig von der
    Groß-/Kleinschreibung erkannt (Startwert „Sonstiges“ bleibt derselbe Datensatz)."""
    if einstellung_holen(session, MIGRATION_MARKER, "") == "erledigt":
        return []
    alle = session.query(AblehnungsGrund).order_by(AblehnungsGrund.sort, AblehnungsGrund.id).all()
    nach_name = {}
    for g in alle:
        nach_name.setdefault((g.name or "").strip().casefold(), g)
    neu, aktiviert, deaktiviert = [], [], []
    fuenf = []
    for nr, name in enumerate(GRUENDE_V32, start=1):
        grund = nach_name.get(name.casefold())
        if grund is None:
            grund = AblehnungsGrund(name=name, aktiv=True, sort=nr,
                                    freitext_pflicht=name in GRUENDE_FREITEXT_PFLICHT)
            session.add(grund)
            neu.append(name)
        else:
            if not grund.aktiv:
                aktiviert.append(grund.name)
            grund.aktiv = True
            grund.sort = nr
            grund.freitext_pflicht = name in GRUENDE_FREITEXT_PFLICHT
            grund.name = name
        fuenf.append(grund)
    session.flush()
    fuenf_ids = {g.id for g in fuenf}
    naechste = len(GRUENDE_V32) + 1
    for g in alle:
        if g.id in fuenf_ids:
            continue
        g.sort = naechste
        naechste += 1
        if (g.name or "").strip().casefold() == AUTO_GRUND.casefold():
            continue
        if g.aktiv:
            g.aktiv = False
            deaktiviert.append(g.name)
    einstellung_setzen(session, MIGRATION_MARKER, "erledigt")
    session.flush()
    meldung = (f"Ablehnungsgründe (v32): {len(neu)} angelegt"
               + (f" ({', '.join(neu)})" if neu else "")
               + f", {len(aktiviert)} aktiviert, {len(deaktiviert)} deaktiviert"
               + (f" ({', '.join(deaktiviert)})" if deaktiviert else "")
               + " – Reihenfolge 1–5, „Sonstiges“ mit Pflicht-Freitext")
    meldungen = [meldung]
    # Abgleich mit dem zweiten Pflegeort (Blatt Gruende, Phase verloren) – nur Hinweis
    try:
        from app import leadmanagement_logik
        excel = [g.grund.strip() for g in leadmanagement_logik.hole_logik().gruende_der_phase("verloren")]
        if [t.casefold() for t in excel] != [t.casefold() for t in GRUENDE_V32]:
            meldungen.append("Ablehnungsgründe (v32): Blatt Gruende „verloren“ weicht von den "
                             f"fünf Angebotstool-Gründen ab – Excel: {', '.join(excel)}")
    except Exception as problem:   # noqa: BLE001 – Excel fehlt: Migration läuft trotzdem
        meldungen.append(f"Ablehnungsgründe (v32): Abgleich mit der Lead-Excel nicht möglich ({problem})")
    return meldungen


def _status_migrieren(session: Session) -> list[str]:
    """vorgaenge.verfolgung_status aus dem Angebotsstatus füllen – nur wo leer
    (idempotent: der zweite Lauf findet nichts Neues)."""
    gefuellt = 0
    zaehler: dict[str, int] = {}
    kandidaten = (session.query(Vorgang)
                  .filter((Vorgang.verfolgung_status.is_(None)) | (Vorgang.verfolgung_status == "")).all())
    if not kandidaten:
        return []
    ids = [v.id for v in kandidaten]
    je_vorgang: dict[int, list[Angebot]] = {}
    for a in (session.query(Angebot)
              .filter(Angebot.vorgang_id.in_(ids), Angebot.archiviert.is_(False),
                      Angebot.status != "Überholt")):
        je_vorgang.setdefault(a.vorgang_id, []).append(a)
    for vorgang in kandidaten:
        angebote = je_vorgang.get(vorgang.id, [])
        if any(a.status == "Angenommen" for a in angebote):
            status = "angenommen"
        elif any(a.status in _ANGEBOT_VERSENDET for a in angebote):
            status = "versendet"
        elif any(a.status == "Abgelehnt" for a in angebote):
            status = "abgelehnt"
        else:
            continue
        vorgang.verfolgung_status = status
        zaehler[status] = zaehler.get(status, 0) + 1
        gefuellt += 1
    if not gefuellt:
        return []
    session.flush()
    teile = ", ".join(f"{STATUS_TEXTE[s]} {n}" for s, n in zaehler.items())
    return [f"Verfolgungsstatus (v32): {gefuellt} Vorgang/Vorgänge aus dem Angebotsstatus "
            f"gefüllt ({teile})"]


def migration_v32_verfolgung(session: Session) -> list[str]:
    """Idempotent: zweiter Lauf ohne Meldung (Gründe über Marker, Status nur wo leer)."""
    meldungen = _gruende_migrieren(session)
    meldungen += _status_migrieren(session)
    return meldungen
