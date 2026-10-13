# v32 (PLAN_V19 Phase 162): Werktagsrechner – Montag bis Freitag ohne gesetzliche
# Feiertage in Nordrhein-Westfalen. Die Feiertagslogik stand seit v23 in
# app/lead_info.py (Info-Veranstaltung, Gauß/Lichtenberg-Osterformel) und ist hierher
# gezogen; lead_info importiert sie von hier (keine zweite Fassung).
from datetime import date, datetime, timedelta


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
    """Name des Feiertags oder leer."""
    if isinstance(tag, datetime):
        tag = tag.date()
    return feiertage_nrw(tag.year).get(tag, "")


def ist_werktag(tag: date) -> bool:
    """Montag bis Freitag und kein NRW-Feiertag."""
    if isinstance(tag, datetime):
        tag = tag.date()
    return tag.weekday() < 5 and not ist_feiertag(tag)


def plus_werktage(datum, n: int) -> date:
    """`datum` plus `n` Werktage (n ≥ 0; 0 = das Datum selbst, auch wenn es kein
    Werktag ist). Kontrollwerte (PLAN_V19): Fr 10.10.2026 + 3 = Mi 15.10.2026;
    Mi 30.09.2026 + 3 = Di 06.10.2026 (3.10. Feiertag, Wochenende);
    Do 17.12.2026 + 3 = Di 22.12.2026."""
    if isinstance(datum, datetime):
        datum = datum.date()
    tag = datum
    rest = max(0, int(n))
    while rest > 0:
        tag = tag + timedelta(days=1)
        if ist_werktag(tag):
            rest -= 1
    return tag


def naechster_werktag(datum) -> date:
    """Das Datum selbst, wenn es ein Werktag ist, sonst der nächste Werktag."""
    if isinstance(datum, datetime):
        datum = datum.date()
    tag = datum
    while not ist_werktag(tag):
        tag = tag + timedelta(days=1)
    return tag
