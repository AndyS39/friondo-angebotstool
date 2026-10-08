# Infoabend (v23, PLAN_LEAD_V2 Phase 104/111, Abschnitt I; bis v24 „Info-Veranstaltung“ –
# seit v25 heißt die Seite „Infoabend“, Parameter info_*, Tabelle info_veranstaltungen und
# Quelle info_veranstaltung bleiben):
# Terminregel „jeden Monat am 1. Donnerstag 18:00 Uhr in Krefeld“ mit
# NRW-Feiertagsregel (fällt der Termin auf einen gesetzlichen Feiertag, eine
# Woche später). Feste und bewegliche Feiertage werden berechnet (Osterformel
# nach Gauß/Lichtenberg), nichts wird von Hand gepflegt. Parameter:
# info_wochentag (0=Mo … 3=Do), info_woche (1 = erster), info_uhrzeit,
# info_ort, info_rollierend_monate, info_vorlauf_tage (A-8).
# Phase 111 ergänzt Board, Gruppen, Sammelaktionen und API-Zuordnung.

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

STANDARD_ORT = "Friondo, Königstraße 102-104, 47798 Krefeld"


def ostersonntag(jahr: int) -> date:
    """Gauß/Lichtenberg (gregorianisch)."""
    k = jahr // 100
    m = 15 + (3 * k + 3) // 4 - (8 * k + 13) // 25
    s = 2 - (3 * k + 3) // 4
    a = jahr % 19
    d = (19 * a + m) % 30
    r = (d + a // 11) // 29
    og = 21 + d - r
    sz = 7 - (jahr + jahr // 4 + s) % 7
    oe = 7 - (og - sz) % 7
    tag = og + oe   # Ostersonntag als März-Datum (kann > 31 sein)
    return date(jahr, 3, 1) + timedelta(days=tag - 1)


def feiertage_nrw(jahr: int) -> dict:
    """Gesetzliche Feiertage in Nordrhein-Westfalen."""
    ostern = ostersonntag(jahr)
    return {
        date(jahr, 1, 1): "Neujahr",
        ostern - timedelta(days=2): "Karfreitag",
        ostern + timedelta(days=1): "Ostermontag",
        date(jahr, 5, 1): "Tag der Arbeit",
        ostern + timedelta(days=39): "Christi Himmelfahrt",
        ostern + timedelta(days=50): "Pfingstmontag",
        ostern + timedelta(days=60): "Fronleichnam",
        date(jahr, 10, 3): "Tag der Deutschen Einheit",
        date(jahr, 11, 1): "Allerheiligen",
        date(jahr, 12, 25): "1. Weihnachtstag",
        date(jahr, 12, 26): "2. Weihnachtstag",
    }


def ist_feiertag(tag: date) -> str:
    return feiertage_nrw(tag.year).get(tag, "")


def regel_termin(jahr: int, monat: int, wochentag: int = 3, woche: int = 1,
                 uhrzeit: str = "18:00") -> tuple:
    """(Termin, verschoben): n-ter Wochentag des Monats; Feiertag → +7 Tage
    (so oft nötig). verschoben=True, wenn die Feiertagsregel griff."""
    erster = date(jahr, monat, 1)
    versatz = (wochentag - erster.weekday()) % 7
    tag = erster + timedelta(days=versatz + 7 * (max(1, woche) - 1))
    verschoben = False
    while ist_feiertag(tag):
        tag += timedelta(days=7)
        verschoben = True
    try:
        stunde, minute = (int(x) for x in uhrzeit.split(":")[:2])
    except ValueError:
        stunde, minute = 18, 0
    return datetime(tag.year, tag.month, tag.day, stunde, minute), verschoben


def termine_ab(start: date, monate: int, wochentag: int = 3, woche: int = 1,
               uhrzeit: str = "18:00") -> list:
    """Regeltermine der nächsten <monate> Monate ab dem Monat von <start>."""
    ergebnis = []
    jahr, monat = start.year, start.month
    for _ in range(max(0, monate)):
        ergebnis.append(regel_termin(jahr, monat, wochentag, woche, uhrzeit))
        monat += 1
        if monat > 12:
            monat = 1
            jahr += 1
    return ergebnis


def parameter(session: Session) -> dict:
    from app import leadmanagement as kern

    def _int(name, standard):
        try:
            return int(kern.parameter_holen(session, name, str(standard)))
        except ValueError:
            return standard
    return {
        "wochentag": min(6, max(0, _int("info_wochentag", 3))),
        "woche": min(4, max(1, _int("info_woche", 1))),
        "uhrzeit": kern.parameter_holen(session, "info_uhrzeit", "18:00") or "18:00",
        "ort": kern.parameter_holen(session, "info_ort", STANDARD_ORT) or STANDARD_ORT,
        "monate": max(1, _int("info_rollierend_monate", 12)),
        "vorlauf_tage": max(0, _int("info_vorlauf_tage", 3)),
    }


def veranstaltungen_anlegen(session: Session, ab=None, monate=None) -> int:
    """Rollierend fehlende Veranstaltungen anlegen (idempotent; Schlüssel =
    Beginn). Erstbestand laut Plan: Oktober 2026 bis einschließlich August
    2027 (11 Termine) – ab Oktober 2026 oder dem aktuellen Monat, je nachdem
    was später ist, immer <info_rollierend_monate> Monate voraus."""
    from app.models import InfoVeranstaltung
    p = parameter(session)
    heute = date.today()
    start = ab or max(date(2026, 10, 1), heute.replace(day=1))
    anzahl_monate = monate if monate is not None else p["monate"]
    # Erstbestand bis August 2027 sicherstellen (I2), danach rollierend
    ende_minimum = date(2027, 8, 1)
    monate_bis_min = ((ende_minimum.year - start.year) * 12
                      + ende_minimum.month - start.month + 1)
    anzahl_monate = max(anzahl_monate, monate_bis_min)
    # Phase 111: Schlüssel = Beginn ODER Monat – eine manuell verschobene
    # Veranstaltung (Termine-Pflege) darf nicht als Regeltermin erneut entstehen
    vorhanden = set()
    monate_belegt = set()
    for v in session.query(InfoVeranstaltung):
        vorhanden.add(v.beginn)
        monate_belegt.add((v.beginn.year, v.beginn.month))
    neu = 0
    for beginn, verschoben in termine_ab(start, anzahl_monate, p["wochentag"],
                                         p["woche"], p["uhrzeit"]):
        if beginn in vorhanden or (beginn.year, beginn.month) in monate_belegt:
            continue
        session.add(InfoVeranstaltung(
            beginn=beginn, ort=p["ort"], verschoben=verschoben,
            titel="Infoabend " + beginn.strftime("%d.%m.%Y")))
        neu += 1
    session.flush()
    return neu


def naechste_veranstaltung(session: Session, ab=None, vorlauf_tage=None):
    """Nächste Veranstaltung ab <ab> + Vorlauf (A-8); legt bei Bedarf
    rollierend nach. Phase 111: entscheidet nur nach dem Datum (das Archiv-
    Kennzeichen spielt keine Rolle) – bei Eingang = jetzt scheiden vergangene
    Termine ohnehin aus, und die Kontrollregel „27.09. → 01.10.“ bleibt auch
    nach der Archivierung vergangener Termine gültig."""
    from app.models import InfoVeranstaltung
    p = parameter(session)
    ab = ab or datetime.now()
    tage = p["vorlauf_tage"] if vorlauf_tage is None else vorlauf_tage
    grenze = ab + timedelta(days=tage)
    treffer = (session.query(InfoVeranstaltung)
               .filter(InfoVeranstaltung.beginn >= grenze)
               .order_by(InfoVeranstaltung.beginn).first())
    if treffer is None:
        veranstaltungen_anlegen(session, ab=grenze.date())
        treffer = (session.query(InfoVeranstaltung)
                   .filter(InfoVeranstaltung.beginn >= grenze)
                   .order_by(InfoVeranstaltung.beginn).first())
    return treffer


def archivieren(session: Session, stichtag=None) -> int:
    """Vergangene Veranstaltungen archivieren (Filter „Archiv“, I2)."""
    from app.models import InfoVeranstaltung
    stichtag = stichtag or datetime.now()
    anzahl = 0
    for v in (session.query(InfoVeranstaltung)
              .filter(InfoVeranstaltung.archiviert.is_(False),
                      InfoVeranstaltung.beginn < stichtag - timedelta(hours=6))):
        v.archiviert = True
        anzahl += 1
    session.flush()
    return anzahl


# Kontrollliste aus PLAN_LEAD_V2 (I2) – Test prüft dagegen
KONTROLLTERMINE = ["01.10.2026", "05.11.2026", "03.12.2026", "07.01.2027",
                   "04.02.2027", "04.03.2027", "01.04.2027", "13.05.2027",
                   "03.06.2027", "01.07.2027", "05.08.2027"]


# =====================================================================================
# Phase 111 – Board Infoabend (I2/I3), Zuordnung Lead → Veranstaltung (I4,
# A-8 [OFFEN 1]), Abgleich „Kunde bereits im System“ (I5), Sammelaktionen (H3).
# Leads dieses Boards sind normale Vorgänge: Quelle info_veranstaltung (Typ
# veranstaltung) bzw. vorgaenge.veranstaltung_id gesetzt. Lead-Phasen bleiben
# unverändert; nach Terminierung erscheinen sie zusätzlich im Board Deals.
# Der Bestandsverweis (I5) ist KEINE neue Spalte, sondern eine Aktivität vom Typ
# „hinweis“ („Kunde bereits im System: Vorgang #… (Phase …)“), die das Board
# ausliest – so bleibt app/models.py unberührt.
# =====================================================================================

import re as _re
import unicodedata as _unicodedata

WOCHENTAGE_KURZ = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
HINWEIS_TYP = "hinweis"
HINWEIS_PRAEFIX = "Kunde bereits im System"
_HINWEIS_MUSTER = _re.compile(r"Vorgang #(\d+)")
GRUPPE_OHNE = "ohne"
TEILGENOMMEN_WERTE = {"ja": True, "nein": False, "leer": None, "": None,
                      "1": True, "0": False, "true": True, "false": False}


def _lead_boards():
    """Phase-105-Modul (Tabelle A3, Status-Logik, Sammelaktions-Registry) –
    optional: fehlt es, arbeitet das Board mit eigenen einfachen Helfern."""
    try:
        from app import lead_boards
        return lead_boards
    except Exception:
        return None


def _logik():
    from app import leadmanagement_logik
    return leadmanagement_logik.hole_logik()


# --- Quelle / Datum ---------------------------------------------------------------------

def ist_info_quelle(quelle) -> bool:
    """Quelle vom Typ veranstaltung (QUELLEN_GRUPPEN) oder Startquelle
    info_veranstaltung – steuert Zuordnung (I4) und Abgleich (I5)."""
    if quelle is None:
        return False
    from app import leadmanagement as kern
    if (getattr(quelle, "key", "") or "") == "info_veranstaltung":
        return True
    if (getattr(quelle, "typ", "") or "") == "veranstaltung":
        return True
    return kern.quelle_gruppe(quelle) == "veranstaltung"


def datum_lesen(text) -> date | None:
    """YYYY-MM-DD (API) oder DD.MM.YYYY; auch Zeitstempel mit Uhrzeit."""
    roh = str(text or "").strip()
    if not roh:
        return None
    roh = roh.replace("T", " ")
    for muster in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y %H:%M",
                   "%d.%m.%Y"):
        try:
            return datetime.strptime(roh, muster).date()
        except ValueError:
            continue
    return None


def zeitpunkt_lesen(text) -> datetime | None:
    roh = str(text or "").strip().replace("T", " ")
    for muster in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M", "%Y-%m-%d",
                   "%d.%m.%Y"):
        try:
            return datetime.strptime(roh, muster)
        except ValueError:
            continue
    return None


def titel(v) -> str:
    """„Do 05.11.2026 18:00“ – Gruppenkopf, Dropdown, Aktivitäten."""
    if v is None or v.beginn is None:
        return "–"
    b = v.beginn
    return f"{WOCHENTAGE_KURZ[b.weekday()]} {b.strftime('%d.%m.%Y %H:%M')}"


def veranstaltung_am_tag(session: Session, tag: date):
    """Veranstaltung mit Beginn an diesem Kalendertag (API-Feld veranstaltung);
    nicht archivierte zuerst."""
    from app.models import InfoVeranstaltung
    von = datetime(tag.year, tag.month, tag.day)
    bis = von + timedelta(days=1)
    return (session.query(InfoVeranstaltung)
            .filter(InfoVeranstaltung.beginn >= von, InfoVeranstaltung.beginn < bis)
            .order_by(InfoVeranstaltung.archiviert, InfoVeranstaltung.beginn).first())


def kommende(session: Session, anzahl: int = 6) -> list:
    """Die nächsten Veranstaltungen (für 422-Hinweise und Dropdowns)."""
    from app.models import InfoVeranstaltung
    return (session.query(InfoVeranstaltung)
            .filter(InfoVeranstaltung.archiviert.is_(False),
                    InfoVeranstaltung.beginn >= datetime.now() - timedelta(hours=6))
            .order_by(InfoVeranstaltung.beginn).limit(anzahl).all())


def veranstaltung_wahl(session: Session) -> list:
    """Dropdown „Veranstaltung“ je Lead: alle nicht archivierten, aufsteigend."""
    from app.models import InfoVeranstaltung
    return (session.query(InfoVeranstaltung)
            .filter(InfoVeranstaltung.archiviert.is_(False))
            .order_by(InfoVeranstaltung.beginn).all())


def naechste_nach(session: Session, aktuelle):
    """Die Veranstaltung nach <aktuelle> (nicht archiviert); legt rollierend nach."""
    from app.models import InfoVeranstaltung
    if aktuelle is None:
        return naechste_veranstaltung(session, ab=datetime.now())
    abfrage = (session.query(InfoVeranstaltung)
               .filter(InfoVeranstaltung.beginn > aktuelle.beginn,
                       InfoVeranstaltung.archiviert.is_(False))
               .order_by(InfoVeranstaltung.beginn))
    treffer = abfrage.first()
    if treffer is None:
        folgemonat = (aktuelle.beginn.replace(day=1) + timedelta(days=32)).replace(day=1)
        veranstaltungen_anlegen(session, ab=folgemonat.date())
        treffer = abfrage.first()
    return treffer


# --- Zuordnung Lead → Veranstaltung (I3/I4) --------------------------------------------

def veranstaltung_zuordnen(session: Session, vorgang, veranstaltung, benutzer=None,
                           grund: str = "") -> str:
    """veranstaltung_id setzen (None = Zuordnung aufheben) + Aktivität je Lead.
    Liefert eine Meldung; bei unveränderter Zuordnung ohne Aktivität."""
    from app import leadmanagement as kern
    from app.models import InfoVeranstaltung
    alt = session.get(InfoVeranstaltung, vorgang.veranstaltung_id) \
        if vorgang.veranstaltung_id else None
    neu_id = veranstaltung.id if veranstaltung is not None else None
    if vorgang.veranstaltung_id == neu_id:
        return f"Veranstaltung ist bereits {titel(veranstaltung)}." if veranstaltung \
            else "Keine Veranstaltung zugeordnet."
    vorgang.veranstaltung_id = neu_id
    if veranstaltung is not None and alt is not None:
        text = f"Veranstaltung geändert: {titel(alt)} → {titel(veranstaltung)}"
    elif veranstaltung is not None:
        text = f"Veranstaltung: {titel(veranstaltung)}"
    else:
        text = f"Veranstaltung aufgehoben (vorher {titel(alt)})"
    if grund:
        text += f" ({grund})"
    kern.aktivitaet(session, vorgang.id, "status", text, benutzer=benutzer)
    session.flush()
    return text + "."


def zuordnen_bei_eingang(session: Session, vorgang, quelle, eingang=None, benutzer=None):
    """A-8 [OFFEN 1]: Lead einer Info-Quelle ohne Veranstaltung bekommt die
    nächste Veranstaltung ab Eingang + info_vorlauf_tage. Für API, Parser,
    Schnellanlage und Import (hook_edits) gleich. Liefert die Veranstaltung
    oder None (keine Info-Quelle / schon zugeordnet)."""
    if vorgang is None or vorgang.veranstaltung_id or not ist_info_quelle(quelle):
        return None
    ab = eingang or vorgang.eingang_am or datetime.now()
    if isinstance(ab, date) and not isinstance(ab, datetime):
        ab = datetime(ab.year, ab.month, ab.day)
    v = naechste_veranstaltung(session, ab=ab)
    if v is None:
        return None
    veranstaltung_zuordnen(session, vorgang, v, benutzer=benutzer,
                           grund=f"Standardregel: nächste ab Eingang + "
                                 f"{parameter(session)['vorlauf_tage']} Tage Vorlauf")
    return v


def in_naechste_verschieben(session: Session, vorgang, benutzer=None) -> tuple:
    """Sammelaktion I3: veranstaltung_id auf die Veranstaltung NACH der aktuellen
    (ohne Zuordnung: die nächste ab heute). (ok, meldung)."""
    from app.models import InfoVeranstaltung
    aktuelle = session.get(InfoVeranstaltung, vorgang.veranstaltung_id) \
        if vorgang.veranstaltung_id else None
    ziel = naechste_nach(session, aktuelle)
    if ziel is None:
        return False, "Keine folgende Veranstaltung vorhanden."
    meldung = veranstaltung_zuordnen(session, vorgang, ziel, benutzer=benutzer,
                                     grund="Sammelaktion: in die nächste Veranstaltung verschoben")
    return True, meldung


def teilgenommen_lesen(wert) -> tuple:
    """Formular-/JSON-Wert → (gueltig, bool|None)."""
    if isinstance(wert, bool):
        return True, wert
    if wert is None:
        return True, None
    schluessel = str(wert).strip().lower()
    if schluessel in TEILGENOMMEN_WERTE:
        return True, TEILGENOMMEN_WERTE[schluessel]
    return False, None


def teilgenommen_setzen(session: Session, vorgang, wert, benutzer=None) -> str:
    """Spalte „Teilgenommen“ (I3): Ja/Nein/leer, Aktivität typ status."""
    from app import leadmanagement as kern
    text = {True: "Ja", False: "Nein", None: "offen"}[wert]
    if vorgang.teilgenommen == wert and (vorgang.teilgenommen is None) == (wert is None):
        return f"Teilgenommen ist bereits „{text}“."
    vorgang.teilgenommen = wert
    kern.aktivitaet(session, vorgang.id, "status",
                    f"Teilgenommen: {text}" if wert is not None
                    else "Teilgenommen zurückgesetzt (offen)", benutzer=benutzer)
    session.flush()
    return f"Teilgenommen: {text}."


# --- Abgleich I5: (E-Mail ODER Telefon) UND Nachname ------------------------------------

def _nachname_normal(text: str) -> str:
    t = _unicodedata.normalize("NFKD", str(text or ""))
    t = "".join(c for c in t if not _unicodedata.combining(c))
    t = t.lower().replace("ß", "ss")
    return _re.sub(r"[^a-z0-9]", "", t)


def bestand_abgleich(session: Session, telefon: str = "", email: str = "",
                     nachname: str = "", ausser_vorgang_id=None, ausser_kunde_id=None):
    """Treffer = (E-Mail gleich ODER Telefon E.164 gleich) UND Nachname gleich
    (normalisiert) gegen Kunden MIT Vorgängen. Demo-Vorgänge zählen nur im
    Demo-Modus mit (bei lead_freigabe_modus = alle werden sie ignoriert).
    Liefert {kunde, vorgang (jüngster), phase} oder None. Kein Zusammenführen."""
    from app import leadmanagement as kern
    from app.models import Kunde, Vorgang
    name_norm = _nachname_normal(nachname)
    tel_norm = kern.telefon_normalisieren(telefon or "")
    mail_norm = (email or "").strip().lower()
    if not name_norm or not (tel_norm or mail_norm):
        return None
    demo_ignorieren = not kern.demo_aktiv(session)
    kandidaten = []
    for kunde in session.query(Kunde).filter(Kunde.aktiv.is_(True)):
        if ausser_kunde_id and kunde.id == ausser_kunde_id:
            continue
        if _nachname_normal(kunde.nachname) != name_norm:
            continue
        mail_ok = bool(mail_norm) and (kunde.email or "").strip().lower() == mail_norm
        tel_ok = bool(tel_norm) and kern.telefon_normalisieren(kunde.telefon or "") == tel_norm
        if mail_ok or tel_ok:
            kandidaten.append(kunde)
    if not kandidaten:
        return None
    abfrage = session.query(Vorgang).filter(Vorgang.kunde_id.in_([k.id for k in kandidaten]))
    if ausser_vorgang_id:
        abfrage = abfrage.filter(Vorgang.id != ausser_vorgang_id)
    if demo_ignorieren:
        abfrage = kern.ohne_demo(abfrage)
    vorgang = abfrage.order_by(Vorgang.angelegt_am.desc()).first()
    if vorgang is None:
        return None
    kunde = next(k for k in kandidaten if k.id == vorgang.kunde_id)
    return {"kunde": kunde, "vorgang": vorgang, "phase": vorgang.lead_phase or ""}


def bestand_hinweis_schreiben(session: Session, vorgang, treffer: dict, benutzer=None) -> str:
    """Aktivität typ hinweis am NEUEN Vorgang: „Kunde bereits im System:
    Vorgang #… (Phase …)“ – das Board liest sie als roten Hinweis (I5)."""
    from app import leadmanagement as kern
    alt = treffer["vorgang"]
    # v25: Phasen-Label aus dem Blatt Status (beide Kontakt-Phasen „Kontaktiert“)
    phase = _status_label(_logik(), alt.lead_phase)[0] if alt.lead_phase else "ohne Lead-Phase"
    kunde = treffer.get("kunde")
    text = (f"{HINWEIS_PRAEFIX}: Vorgang #{alt.id} (Phase {phase})"
            + (f" – {kunde.anzeige_name}" if kunde is not None else ""))
    kern.aktivitaet(session, vorgang.id, HINWEIS_TYP, text, benutzer=benutzer)
    session.flush()
    return text


def bestand_hinweise(session: Session, vorgang_ids) -> dict:
    """Jüngster Bestandshinweis je Vorgang: {vorgang_id: {vorgang_id, text, phase,
    link}} – aus den Aktivitäten (kein Schema-Zusatz)."""
    from app.models import LeadAktivitaet, Vorgang
    ids = {i for i in vorgang_ids if i} or {0}
    ergebnis = {}
    logik = _logik()   # v25: Phasen-Label aus dem Blatt Status
    for a in (session.query(LeadAktivitaet)
              .filter(LeadAktivitaet.vorgang_id.in_(ids), LeadAktivitaet.typ == HINWEIS_TYP)
              .order_by(LeadAktivitaet.zeitpunkt)):
        treffer = _HINWEIS_MUSTER.search(a.text or "")
        if treffer is None or not (a.text or "").startswith(HINWEIS_PRAEFIX):
            continue
        ziel_id = int(treffer.group(1))
        ziel = session.get(Vorgang, ziel_id)
        ergebnis[a.vorgang_id] = {
            "vorgang_id": ziel_id, "text": a.text, "zeitpunkt": a.zeitpunkt,
            "phase": (_status_label(logik, ziel.lead_phase)[0] if ziel.lead_phase else "")
            if ziel is not None else "",
            "link": f"/lead-management/lead/{ziel_id}" if (ziel is not None and ziel.lead_phase)
            else f"/vorgaenge/{ziel_id}",
        }
    return ergebnis


def bestand_hinweis(session: Session, vorgang) -> dict | None:
    return bestand_hinweise(session, [vorgang.id]).get(vorgang.id)


# --- Board: Gruppen je Veranstaltung (I2/I3) --------------------------------------------

def filter_aus_query(q) -> dict:
    def _int(name):
        wert = str(q.get(name, "") or "")
        return int(wert) if wert.isdigit() else None
    return {
        "q": (q.get("q", "") or "").strip(),
        "archiv": q.get("archiv", "") == "1",
        "veranstaltung_id": _int("veranstaltung_id"),
        "teilgenommen": (q.get("teilgenommen", "") or "").strip().lower(),
        "status": (q.get("status", "") or "").strip(),
        "sparte": (q.get("sparte", "") or "").strip().upper(),
        "meine": q.get("meine", "") == "1",
    }


def _status_label(logik, phase: str) -> tuple:
    lb = _lead_boards()
    if lb is not None:
        return lb.status_label(logik, phase)
    from app.models import LEAD_PHASEN_NAMEN
    zeile = logik.status_zeile(phase or "")
    if zeile is not None:
        return zeile.label or LEAD_PHASEN_NAMEN.get(phase, phase), zeile.farbe or "#9aa4b2"
    return LEAD_PHASEN_NAMEN.get(phase, phase or "–"), "#9aa4b2"


def _punkte(anrufe: list, maximum: int, benutzer_map: dict) -> list:
    lb = _lead_boards()
    if lb is not None:
        return lb.versuche_punkte(anrufe, maximum, benutzer_map)
    from app.models import ANRUF_ERGEBNIS_NAMEN
    maximum = max(1, maximum)
    letzte = anrufe[-maximum:] if len(anrufe) > maximum else anrufe
    punkte = [{"klasse": "grau", "titel": a.zeitpunkt.strftime("%d.%m.%Y %H:%M") + " · "
               + ANRUF_ERGEBNIS_NAMEN.get(a.ergebnis or "", a.ergebnis or "Anruf")}
              for a in letzte]
    while len(punkte) < maximum:
        punkte.append({"klasse": "", "titel": "noch kein Versuch"})
    return punkte


def _kanal_farbe(session: Session, kanal: str) -> str:
    lb = _lead_boards()
    if lb is not None:
        return lb.kanal_farbe(lb.kanal_farben(session), kanal)
    return "#8e44ad" if (kanal or "").strip() else ""


def _suche_passt(kunde, suche: str) -> bool:
    if not suche:
        return True
    from app import leadmanagement as kern
    text = " ".join((kunde.vorname or "", kunde.nachname or "", kunde.firma or "",
                     kunde.ort or "", kunde.plz or "", kunde.email or "",
                     kunde.telefon or "")).lower()
    if suche.lower() in text:
        return True
    ziffern = _re.sub(r"[^\d+]", "", suche)
    if len(ziffern) >= 4 and kunde.telefon:
        return kern.telefon_normalisieren(suche) in kern.telefon_normalisieren(kunde.telefon)
    return False


def board_daten(session: Session, benutzer, f: dict | None = None) -> dict:
    """Gruppen je Veranstaltung mit Zeilen im Format der Board-Tabelle (A3,
    leadmanagement/_tabelle.html) plus Info-Felder (veranstaltung, teilgenommen,
    hinweis, vergangen). Leads = Vorgänge mit veranstaltung_id oder mit Quelle
    vom Typ veranstaltung (Gruppe „ohne Veranstaltung“). Handelsvertreter sehen
    nur eigene Leads (ad_id). Filter archiv: vergangene (archivierte)
    Veranstaltungen statt der kommenden."""
    from app import lead_v2
    from app import leadmanagement as kern
    from app.models import (Benutzer, InfoVeranstaltung, Kunde, LeadAktivitaet, LeadQuelle,
                            Vorgang, VotTermin, ANRUF_ERGEBNIS_NAMEN)
    f = f or {}
    logik = _logik()
    jetzt = datetime.now()
    hv = lead_v2.ist_handelsvertreter(session, benutzer)
    quellen = {q.id: q for q in session.query(LeadQuelle)}
    info_quellen = {qid for qid, q in quellen.items() if ist_info_quelle(q)}
    abfrage = (session.query(Vorgang)
               .filter(Vorgang.lead_phase.isnot(None))
               .filter((Vorgang.veranstaltung_id.isnot(None))
                       | (Vorgang.quelle_id.in_(info_quellen or {0}))))
    if hv:
        abfrage = abfrage.filter(Vorgang.ad_id == benutzer.id)
    elif f.get("meine") and benutzer is not None:
        abfrage = abfrage.filter(Vorgang.leadmanager_id == benutzer.id)
    vorgaenge = abfrage.all()
    ids = {v.id for v in vorgaenge} or {0}
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({v.kunde_id for v in vorgaenge} or {0}))}
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    mehrfach: dict = {}
    for (kid,) in session.query(Vorgang.kunde_id).filter(
            Vorgang.kunde_id.in_({v.kunde_id for v in vorgaenge} or {0})):
        mehrfach[kid] = mehrfach.get(kid, 0) + 1
    termine: dict = {}
    for t in (session.query(VotTermin).filter(VotTermin.vorgang_id.in_(ids))
              .order_by(VotTermin.beginn)):
        termine.setdefault(t.vorgang_id, []).append(t)
    kontakt_typen = ("anruf", "mail_aus", "mail_ein", "whatsapp")
    kontakt_art = {"anruf": "Anruf", "mail_aus": "E-Mail ausgehend",
                   "mail_ein": "E-Mail eingehend", "whatsapp": "WhatsApp"}
    anrufe: dict = {}
    kontakte: dict = {}
    letzte_status: dict = {}
    for a in (session.query(LeadAktivitaet).filter(LeadAktivitaet.vorgang_id.in_(ids))
              .order_by(LeadAktivitaet.zeitpunkt)):
        if a.typ == "anruf":
            anrufe.setdefault(a.vorgang_id, []).append(a)
        if a.typ in kontakt_typen:
            kontakte[a.vorgang_id] = a
        if a.typ == "status":
            letzte_status[a.vorgang_id] = a
    hinweise = bestand_hinweise(session, ids)
    maximum = kern.versuche_max(session)
    suche = f.get("q", "")
    archiv = bool(f.get("archiv"))

    veranstaltungen = {v.id: v for v in session.query(InfoVeranstaltung)}
    zeilen_je: dict = {}
    for v in vorgaenge:
        kunde = kunden.get(v.kunde_id)
        if kunde is None:
            continue
        veranst = veranstaltungen.get(v.veranstaltung_id) if v.veranstaltung_id else None
        gruppe_key = f"v{veranst.id}" if veranst is not None else GRUPPE_OHNE
        # Archiv-Sicht: nur Leads archivierter Veranstaltungen; sonst nur aktive
        if veranst is not None and bool(veranst.archiviert) != archiv:
            continue
        if veranst is None and archiv:
            continue
        if f.get("veranstaltung_id") and (veranst is None or veranst.id != f["veranstaltung_id"]):
            continue
        if f.get("status") and v.lead_phase != f["status"]:
            continue
        tg = f.get("teilgenommen", "")
        if tg == "ja" and v.teilgenommen is not True:
            continue
        if tg == "nein" and v.teilgenommen is not False:
            continue
        if tg == "offen" and v.teilgenommen is not None:
            continue
        sparten = [s.strip() for s in (kunde.interesse or "").split(",") if s.strip()]
        if f.get("sparte") and f["sparte"] not in sparten:
            continue
        if not _suche_passt(kunde, suche):
            continue
        eigene = termine.get(v.id, [])
        aktiver_vot = next((t for t in eigene if (t.typ or "vot") == "vot"
                            and t.status in ("geplant", "bestaetigt")), None)
        vorab = next((t for t in eigene if (t.typ or "vot") in ("telefon", "online")
                      and t.status in ("geplant", "bestaetigt", "vorgemerkt")), None)
        naechster = next((t for t in eigene if t.status in ("geplant", "bestaetigt", "vorgemerkt")
                          and (t.beginn is None or t.beginn >= jetzt - timedelta(hours=3))), None) \
            or aktiver_vot or vorab
        liste = anrufe.get(v.id, [])
        label, farbe = _status_label(logik, v.lead_phase)
        board, gruppe = logik.board_fuer(v.lead_phase or "neu")
        kontakt = kontakte.get(v.id)
        letzter_status = letzte_status.get(v.id)
        zurueck = bool(letzter_status is not None
                       and (letzter_status.text or "").startswith("Wiedervorlage fällig")
                       and (not liste or liste[-1].zeitpunkt < letzter_status.zeitpunkt))
        zeile = {
            "vorgang": v, "kunde": kunde, "gruppe": gruppe_key, "board": "info",
            "lead_board": board, "lead_gruppe": gruppe,
            "status_label": label, "status_farbe": farbe,
            "kanal": kunde.vertriebskanal or "",
            "kanal_farbe": _kanal_farbe(session, kunde.vertriebskanal),
            "sparten": sparten, "sparten_status": {s: "offen" for s in sparten},
            "versuche": len(liste), "punkte": _punkte(liste, maximum, benutzer_map),
            "gesperrt": kern.versuche_gesperrt(session, v),
            "letzter": kontakt,
            "letzter_art": (kontakt_art.get(kontakt.typ, kontakt.typ)
                            + (" · " + ANRUF_ERGEBNIS_NAMEN.get(kontakt.ergebnis, kontakt.ergebnis)
                               if kontakt.typ == "anruf" and kontakt.ergebnis else "")) if kontakt else "",
            "letzter_benutzer": benutzer_map.get(kontakt.benutzer_id) if kontakt else None,
            "eingang": v.eingang_am or v.angelegt_am,
            "ad": benutzer_map.get(v.ad_id), "leadmanager": benutzer_map.get(v.leadmanager_id),
            "hv_grund": lead_v2.hv_ausgeschlossen(session, v, kunde),
            "termin": naechster, "termin_ad": benutzer_map.get(naechster.ad_id) if naechster else None,
            "telefongespraech": vorab is not None and gruppe == "neu", "vorab": vorab,
            "vor_termin": (v.lead_phase == "verloren"
                           and not any((t.typ or "vot") == "vot" for t in eigene)),
            "wiedervorlage": (v.zurueckgestellt_bis if v.lead_phase == "zurueckgestellt"
                              else v.naechste_aktion_am or v.wiedervorlage_am),
            "weitere": max(0, mehrfach.get(v.kunde_id, 1) - 1),
            "monday": v.eingang_art == "monday", "quelle": quellen.get(v.quelle_id),
            "zurueck": zurueck, "angebote": [], "erfassungen": [], "offene_angebote": [],
            # Info-Felder (I3/I5)
            "veranstaltung": veranst, "teilgenommen": v.teilgenommen,
            "vergangen": veranst is not None and veranst.beginn <= jetzt,
            "hinweis": hinweise.get(v.id),
            "terminiert": aktiver_vot is not None or (v.lead_phase or "") in
            ("terminiert", "erfasst", "angebot", "gewonnen"),
        }
        zeilen_je.setdefault(gruppe_key, []).append(zeile)

    # Gruppen: kommende (aufsteigend) bzw. archivierte (absteigend) Veranstaltungen,
    # ohne Filter auch leere Gruppen (I2: sofort sichtbar, einklappbar)
    if archiv:
        reihe = sorted((v for v in veranstaltungen.values() if v.archiviert),
                       key=lambda v: v.beginn, reverse=True)
    else:
        reihe = sorted((v for v in veranstaltungen.values() if not v.archiviert),
                       key=lambda v: v.beginn)
    if f.get("veranstaltung_id"):
        reihe = [v for v in reihe if v.id == f["veranstaltung_id"]]
    gruppen = []
    offen_gesetzt = 0
    sort = f.get("sort") if isinstance(f, dict) else None   # v25: gemerkte Sortierung (Board „info“)
    for v in reihe:
        zeilen = zeilen_je.get(f"v{v.id}", [])
        zeilen.sort(key=lambda z: z["eingang"] or jetzt, reverse=True)
        _zeilen_sortieren(zeilen, sort, jetzt)
        eingeklappt = not zeilen if archiv else (not zeilen and offen_gesetzt >= 2)
        if zeilen or not eingeklappt:
            offen_gesetzt += 1
        gruppen.append({
            "key": f"v{v.id}", "veranstaltung": v, "titel": titel(v), "ort": v.ort or "",
            "verschoben": bool(v.verschoben), "notiz": v.notiz or "",
            "vergangen": v.beginn <= jetzt, "zeilen": zeilen, "eingeklappt": eingeklappt,
            "teilgenommen_ja": sum(1 for z in zeilen if z["teilgenommen"] is True),
            "teilgenommen_nein": sum(1 for z in zeilen if z["teilgenommen"] is False),
            "teilgenommen_offen": sum(1 for z in zeilen if z["teilgenommen"] is None),
            "hinweise": sum(1 for z in zeilen if z["hinweis"]),
        })
    ohne = zeilen_je.get(GRUPPE_OHNE, [])
    if ohne and not archiv:
        ohne.sort(key=lambda z: z["eingang"] or jetzt, reverse=True)
        _zeilen_sortieren(ohne, sort, jetzt)
        gruppen.insert(0, {
            "key": GRUPPE_OHNE, "veranstaltung": None, "titel": "Ohne Veranstaltung",
            "ort": "", "verschoben": False, "notiz": "", "vergangen": False, "zeilen": ohne,
            "eingeklappt": False, "teilgenommen_ja": 0, "teilgenommen_nein": 0,
            "teilgenommen_offen": len(ohne), "hinweise": sum(1 for z in ohne if z["hinweis"]),
        })
    return {"gruppen": gruppen, "jetzt": jetzt, "hv": hv, "archiv": archiv,
            "anzahl": sum(len(g["zeilen"]) for g in gruppen), "versuche_max": maximum}


def zeile_fuer(session: Session, benutzer, vorgang) -> dict | None:
    """Eine Zeile nach einer Änderung (Teilgenommen, Veranstaltung, Inline-Feld)."""
    from app.models import InfoVeranstaltung
    veranst = session.get(InfoVeranstaltung, vorgang.veranstaltung_id) \
        if vorgang.veranstaltung_id else None
    daten = board_daten(session, benutzer, {"archiv": bool(veranst is not None and veranst.archiviert)})
    for g in daten["gruppen"]:
        for z in g["zeilen"]:
            if z["vorgang"].id == vorgang.id:
                return z
    return None


def tabellen_kontext(session: Session, benutzer) -> dict:
    """ctx für leadmanagement/_tabelle.html (Phase 105) bzw. die Rückfall-
    Tabelle: Auswahllisten, Gründe, Rechte, Veranstaltungen."""
    from app import lead_v2
    from app import leadmanagement as kern
    from app.models import LEAD_PHASEN
    lb = _lead_boards()
    hv = lead_v2.ist_handelsvertreter(session, benutzer)
    logik = _logik()
    if lb is not None:
        listen = lb.auswahl_listen(session)
    else:
        status = []
        for phase in LEAD_PHASEN:
            label, farbe = _status_label(logik, phase)
            status.append({"key": phase, "label": label, "farbe": farbe,
                           "setzbar": phase not in ("terminiert", "erfasst", "angebot", "gewonnen"),
                           "grund": {"zurueckgestellt": "zurueckgestellt",
                                     "unqualifiziert": "unqualifiziert",
                                     "verloren": "verloren"}.get(phase, "")})
        listen = {"ad_wahl": [], "lm_wahl": [], "status_wahl": status, "kanaele": [],
                  "gruende": {phase: [{"grund": g.grund, "freitext": g.freitext_pflicht}
                                      for g in logik.gruende_der_phase(phase)]
                              for phase in ("zurueckgestellt", "unqualifiziert", "verloren")}}
    jetzt = datetime.now()
    return {
        "board": "info", "jetzt": jetzt, "heute": jetzt.date(), "hv": hv,
        "nur_lesen": False,
        "sammel": not hv and benutzer is not None and benutzer.rolle != "aussendienst",
        "erzwingen": benutzer is not None and benutzer.rolle in ("admin", "innendienst"),
        "versuche_max": kern.versuche_max(session),
        "veranstaltungen": veranstaltung_wahl(session),
        "unq_gruende": logik.gruende_der_phase("unqualifiziert"),
        "zurueck_gruende": logik.gruende_der_phase("zurueckgestellt"),
        **listen,
    }


# Spalten des Info-Boards: wie Hauptboard (Konfiguration je Nutzer aus Phase 105,
# wenn vorhanden) + Ergebnis-Buttons, Teilgenommen, Veranstaltung
SPALTEN_INFO = [("ergebnis", "Ergebnis", True), ("teilgenommen", "Teilgenommen", True),
                ("veranstaltung", "Veranstaltung", True)]
SPALTEN_RUECKFALL = [
    ("lead", "Lead", True), ("status", "Status", True), ("kanal", "Vertriebskanal", True),
    ("versuche", "Kontaktversuche", True), ("letzter_kontakt", "Letzter Kontakt", True),
    ("eingang", "Eingangsdatum", True), ("ort", "Ort", True), ("interessen", "Interessen", True),
    ("telefon", "Telefon", True), ("email", "E-Mail", True), ("termin", "Vor-Ort-Termin", True),
]


# Board-Key der Spaltenkonfiguration je Nutzer (lead_boards.KONFIG_BOARDS; der
# Katalog ist der des Hauptboards, die Einstellungen – Reihenfolge, Sichtbarkeit,
# eigene Namen, gemerkte Sortierung – gelten nur für den Infoabend)
KONFIG_BOARD = "info"


def spalten_fuer(session: Session, benutzer_id: int, tabelle_makro: bool) -> list:
    """Spalten des Infoabends: Hauptboard-Katalog in der Konfiguration des
    Nutzers für das Board „info“ (v25: eigene Konfiguration, nicht die des
    Hauptboards) + Ergebnis, Teilgenommen (nach Status) und Veranstaltung
    (hinten); Kundenname und Status bleiben vorn."""
    lb = _lead_boards()
    if tabelle_makro and lb is not None:
        basis = lb.spalten_fuer(session, benutzer_id, KONFIG_BOARD)
    else:
        basis = [{"key": k, "titel": t, "sichtbar": s} for k, t, s in SPALTEN_RUECKFALL]
    rest = [sp for sp in basis if sp["key"] not in ("lead", "status")]
    vorn = [sp for sp in basis if sp["key"] == "lead"] + [sp for sp in basis if sp["key"] == "status"]
    ergebnis, teil, veranst = ({"key": k, "titel": t, "sichtbar": s} for k, t, s in SPALTEN_INFO)
    return vorn + [ergebnis, teil] + rest + [veranst]


def sortierung_fuer(session: Session, benutzer) -> dict | None:
    """Gemerkte Sortierung des Nutzers für den Infoabend ({key, richtung} oder
    None) – lead_boards.sortierung_fuer mit dem Board-Key „info“."""
    lb = _lead_boards()
    if lb is None:
        return None
    try:
        return lb.sortierung_fuer(session, benutzer, KONFIG_BOARD)
    except Exception:
        return None


def _zeilen_sortieren(zeilen: list, sort: dict | None, jetzt) -> None:
    """Gruppe nach der gemerkten Spalte sortieren (lead_boards.zeilen_sortieren);
    ohne gemerkte Sortierung bleibt die Infoabend-Reihenfolge (Eingang neueste
    zuerst) unverändert."""
    if not sort:
        return
    lb = _lead_boards()
    if lb is None:
        return
    try:
        lb.zeilen_sortieren(zeilen, sort, jetzt)
    except Exception:
        pass


# --- Sammelaktionen (H3) – Registrierung in der Registry von Phase 105 ----------------

def _sammel_naechste(session: Session, vorgaenge: list, params: dict, benutzer) -> tuple:
    from app.models import Kunde
    ok, fehler = 0, []
    for v in vorgaenge:
        erfolg, meldung = in_naechste_verschieben(session, v, benutzer=benutzer)
        if erfolg:
            ok += 1
        else:
            kunde = session.get(Kunde, v.kunde_id)
            fehler.append(f"{kunde.anzeige_name if kunde else v.id}: {meldung}")
    return ok, fehler


def _sammel_teilgenommen(session: Session, vorgaenge: list, params: dict, benutzer) -> tuple:
    gueltig, wert = teilgenommen_lesen(params.get("teilgenommen", params.get("wert", "")))
    if not gueltig:
        return 0, ["Teilgenommen: Wert ja | nein | leer erwartet"]
    ok = 0
    for v in vorgaenge:
        teilgenommen_setzen(session, v, wert, benutzer=benutzer)
        ok += 1
    return ok, []


def _sammel_status(session: Session, vorgaenge: list, params: dict, benutzer) -> tuple:
    """Status ändern (H3) über lead_boards.status_setzen (Pflichtgründe, Angebote
    bei Verloren); Präfix „Sammelaktion –“ in der Aktivität je Lead."""
    from app.models import Kunde
    lb = _lead_boards()
    if lb is None:
        return 0, ["Status ändern ist ohne das Board-Modul (Phase 105) nicht verfügbar"]
    handler = getattr(lb, "_sammel_status", None)
    if callable(handler):
        return handler(session, vorgaenge, params, benutzer)
    ok, fehler = 0, []
    for v in vorgaenge:
        erfolg, meldung = lb.status_setzen(session, v, params.get("status", ""), benutzer=benutzer,
                                           grund=params.get("grund", ""),
                                           grund_text=params.get("grund_text", ""),
                                           bis=params.get("bis"), quelle="Sammelaktion")
        if erfolg:
            ok += 1
        else:
            kunde = session.get(Kunde, v.kunde_id)
            fehler.append(f"{kunde.anzeige_name if kunde else v.id}: {meldung}")
    return ok, fehler


def _sammel_hv(session: Session, vorgaenge: list, params: dict, benutzer) -> tuple:
    """v29 (PLAN_LEAD_V4 Phase 140): „An Handelsvertreter verschieben“ – derselbe
    Handler wie auf Hauptboard/Deals (lead_boards._sammel_hv_verschieben:
    Ziele hv_gruppe_rene/_simon, Ausschluss F14, Aktivität je Lead, keine Glocke)."""
    lb = _lead_boards()
    if lb is None:
        return 0, ["Verschieben an Handelsvertreter ist ohne das Board-Modul (Phase 105) nicht verfügbar"]
    return lb._sammel_hv_verschieben(session, vorgaenge, params, benutzer)


SAMMELAKTIONEN_INFO = [
    ("status", "Status ändern", _sammel_status),
    ("naechste", "In die nächste Veranstaltung verschieben", _sammel_naechste),
    ("teilgenommen", "Teilgenommen setzen", _sammel_teilgenommen),
    # v29 (Phase 140): Sammelaktion „An Handelsvertreter verschieben“ auch im Infoabend
    ("hv_verschieben", "An Handelsvertreter verschieben", _sammel_hv),
]


def sammelaktionen_registrieren() -> None:
    lb = _lead_boards()
    if lb is None:
        return
    for key, titel_, handler in SAMMELAKTIONEN_INFO:
        lb.sammelaktion_registrieren("info", key, titel_, handler)


def sammelaktionen() -> list:
    return [{"key": k, "titel": t} for k, t, _ in SAMMELAKTIONEN_INFO]


def sammelaktion_ausfuehren(session: Session, benutzer, aktion: str, ids, params: dict | None = None) -> tuple:
    """Je Lead eine Aktivität (Handler); Meldung mit Zählern. Nutzt die
    Registry/Zugriffsprüfung von Phase 105, sonst eigene Schleife."""
    from app import lead_v2
    from app.models import Vorgang
    params = params or {}
    lb = _lead_boards()
    if lb is not None:
        sammelaktionen_registrieren()
        return lb.sammelaktion_ausfuehren(session, benutzer, "info", aktion, list(ids or []), params)
    if benutzer is None or benutzer.rolle == "aussendienst":
        return False, "Sammelaktionen sind für den Außendienst nicht freigegeben."
    eintrag = next((e for e in SAMMELAKTIONEN_INFO if e[0] == aktion), None)
    if eintrag is None:
        return False, f"Sammelaktion „{aktion}“ gibt es auf diesem Board nicht."
    sauber = []
    for wert in ids or []:
        try:
            sauber.append(int(wert))
        except (TypeError, ValueError):
            continue
    if not sauber:
        return False, "Keine Leads markiert."
    vorgaenge = [v for v in session.query(Vorgang).filter(Vorgang.id.in_(sauber))
                 if lead_v2.zugriff_erlaubt(session, benutzer, v)]
    if not vorgaenge:
        return False, "Keine zugänglichen Leads markiert."
    ergebnis = eintrag[2](session, vorgaenge, params, benutzer)
    session.flush()
    ok, fehler = ergebnis[0], ergebnis[1]
    if len(ergebnis) >= 3 and ergebnis[2]:      # v29: eigene Meldung des Handlers
        return ok > 0, f"{eintrag[1]}: {ergebnis[2]}"
    meldung = f"{eintrag[1]}: {ok} von {len(vorgaenge)} Leads geändert."
    if fehler:
        meldung += f" {len(fehler)} übersprungen: " + "; ".join(fehler[:5])
    return ok > 0, meldung


# --- Veranstaltungs-Pflege (Termine-Seite) ----------------------------------------------

def termine_liste(session: Session) -> list:
    """Alle Veranstaltungen mit Zählern (Leads, Teilgenommen) für die Pflegeseite."""
    from app.models import InfoVeranstaltung, Vorgang
    zaehler: dict = {}
    for v in session.query(Vorgang).filter(Vorgang.veranstaltung_id.isnot(None)):
        z = zaehler.setdefault(v.veranstaltung_id, {"leads": 0, "ja": 0, "nein": 0})
        z["leads"] += 1
        if v.teilgenommen is True:
            z["ja"] += 1
        elif v.teilgenommen is False:
            z["nein"] += 1
    jetzt = datetime.now()
    ergebnis = []
    for v in session.query(InfoVeranstaltung).order_by(InfoVeranstaltung.beginn):
        z = zaehler.get(v.id, {"leads": 0, "ja": 0, "nein": 0})
        ergebnis.append({"v": v, "titel": titel(v), "vergangen": v.beginn <= jetzt, **z})
    return ergebnis


def veranstaltung_verschieben(session: Session, veranstaltung, neuer_beginn: datetime,
                              benutzer=None) -> str:
    """Manuell verschieben (Pflege): neuer Beginn, Notizzeile; Leads behalten
    ihre veranstaltung_id. Liefert Fehlertext oder ''."""
    from app.models import InfoVeranstaltung
    if neuer_beginn is None:
        return "Datum/Uhrzeit nicht lesbar."
    if neuer_beginn == veranstaltung.beginn:
        return "Der Termin ist unverändert."
    doppelt = (session.query(InfoVeranstaltung)
               .filter(InfoVeranstaltung.beginn == neuer_beginn,
                       InfoVeranstaltung.id != veranstaltung.id).first())
    if doppelt is not None:
        return f"Zu diesem Zeitpunkt gibt es bereits eine Veranstaltung (#{doppelt.id})."
    alt = titel(veranstaltung)
    veranstaltung.beginn = neuer_beginn
    veranstaltung.titel = "Infoabend " + neuer_beginn.strftime("%d.%m.%Y")
    wer = f", {benutzer.name}" if benutzer is not None else ""
    zeile = (f"Manuell verschoben: {alt} → {titel(veranstaltung)} "
             f"({datetime.now().strftime('%d.%m.%Y %H:%M')}{wer})")
    veranstaltung.notiz = ((veranstaltung.notiz or "").rstrip() + "\n" + zeile).strip()
    if veranstaltung.archiviert and neuer_beginn > datetime.now():
        veranstaltung.archiviert = False
    session.flush()
    return ""


def veranstaltung_anlegen_manuell(session: Session, beginn: datetime, ort: str = "",
                                  benutzer=None):
    """Zusätzliche Veranstaltung außerhalb der Regel (Pflege). (veranstaltung, fehler)."""
    from app.models import InfoVeranstaltung
    if beginn is None:
        return None, "Datum/Uhrzeit nicht lesbar."
    if session.query(InfoVeranstaltung).filter(InfoVeranstaltung.beginn == beginn).first():
        return None, "Zu diesem Zeitpunkt gibt es bereits eine Veranstaltung."
    v = InfoVeranstaltung(beginn=beginn, ort=(ort or parameter(session)["ort"])[:300],
                          titel="Infoabend " + beginn.strftime("%d.%m.%Y"),
                          verschoben=False, archiviert=beginn <= datetime.now(),
                          erstellt_von=benutzer.id if benutzer is not None else None,
                          notiz=f"Manuell angelegt ({datetime.now().strftime('%d.%m.%Y %H:%M')})")
    session.add(v)
    session.flush()
    return v, ""
