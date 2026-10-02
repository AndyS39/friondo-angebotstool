# Info-Veranstaltung (v23, PLAN_LEAD_V2 Phase 104/111, Abschnitt I):
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
    vorhanden = {v.beginn for v in session.query(InfoVeranstaltung)}
    neu = 0
    for beginn, verschoben in termine_ab(start, anzahl_monate, p["wochentag"],
                                         p["woche"], p["uhrzeit"]):
        if beginn in vorhanden:
            continue
        session.add(InfoVeranstaltung(
            beginn=beginn, ort=p["ort"], verschoben=verschoben,
            titel="Info-Veranstaltung " + beginn.strftime("%d.%m.%Y")))
        neu += 1
    session.flush()
    return neu


def naechste_veranstaltung(session: Session, ab=None, vorlauf_tage=None):
    """Nächste (nicht archivierte) Veranstaltung ab <ab> + Vorlauf (A-8);
    legt bei Bedarf rollierend nach."""
    from app.models import InfoVeranstaltung
    p = parameter(session)
    ab = ab or datetime.now()
    tage = p["vorlauf_tage"] if vorlauf_tage is None else vorlauf_tage
    grenze = ab + timedelta(days=tage)
    treffer = (session.query(InfoVeranstaltung)
               .filter(InfoVeranstaltung.beginn >= grenze,
                       InfoVeranstaltung.archiviert.is_(False))
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
