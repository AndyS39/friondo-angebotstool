# Konfigurator-Engine (Phase 4): wertet die eingelesene Logik gegen die
# gespeicherten Antworten aus – Sichtbarkeit, nächste Frage, Aktions-Matching
# (inkl. Zahlenbereiche und ABBRUCH), Leistungsklasse und Paketauflösung.

import re
from typing import Optional

from app.logik import (Aktion, ArtikelRef, Frage, Logik, PaketZeile,
                       _alias_aufloesen)


# --- Zahlen ---------------------------------------------------------------

def zahl_parsen(text) -> Optional[float]:
    """Deutsche Zahleneingabe: '8.000' -> 8000, '12,5' -> 12.5, '' -> None."""
    if text is None:
        return None
    t = str(text).strip().replace(" ", "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def _bereich_passt(text: str, zahl: float) -> bool:
    """Prüft Zahlenbereiche aus Aktionszeilen: '0 – 8.000 kWh', 'über 14', 'bis 4', 'ab 9.000'."""
    m = re.search(r"([\d.]+)\s*[–-]\s*([\d.]+)", text)
    if m:
        von = zahl_parsen(m.group(1))
        bis = zahl_parsen(m.group(2))
        return von <= zahl <= bis
    m = re.search(r"über\s*([\d.]+)", text)
    if m:
        return zahl > zahl_parsen(m.group(1))
    m = re.search(r"\bbis\s*([\d.]+)", text)
    if m:
        return zahl <= zahl_parsen(m.group(1))
    m = re.search(r"\bab\s*([\d.]+)", text)
    if m:
        return zahl >= zahl_parsen(m.group(1))
    return True  # freie Beschreibung ("Meterzahl", "Anzahl") passt auf jede Zahl


# --- Sichtbarkeit ---------------------------------------------------------

def ist_selbstnutzung(antworten: dict) -> bool:
    """EFH immer; MFH nur wenn F32 = Ja; Gewerbe nie."""
    f30 = str(antworten.get("F30") or "")
    if f30.startswith("Einfamilienhaus"):
        return True
    if f30.startswith("Mehrfamilienhaus"):
        return antworten.get("F32") == "Ja"
    return False


def ist_sichtbar(frage: Frage, antworten: dict, fragen: dict[str, Frage]) -> bool:
    b = frage.bedingung
    if b is None or b.art == "immer":
        return True
    if b.art == "selbstnutzung":
        return ist_selbstnutzung(antworten)
    if b.art == "ausgefuellt":
        wert = antworten.get(b.frage_id)
        return wert is not None and str(wert) != ""
    if b.art == "antwort":
        wert = antworten.get(b.frage_id)
        if wert is None:
            return False
        ziel = fragen.get(b.frage_id)
        optionen = ziel.antworten if ziel else []
        erlaubt = {_alias_aufloesen(w, optionen) or w for w in b.werte}
        return str(wert) in erlaubt
    return False


def sichtbare_fragen(logik: Logik, antworten: dict) -> list[Frage]:
    return [f for f in sorted(logik.fragen.values(), key=lambda f: f.reihenfolge)
            if ist_sichtbar(f, antworten, logik.fragen)]


def naechste_frage(logik: Logik, antworten: dict) -> Optional[Frage]:
    for frage in sichtbare_fragen(logik, antworten):
        if frage.id not in antworten:
            return frage
    return None


# --- Aktions-Matching -----------------------------------------------------

def _antwort_passt(frage: Frage, aktions_antwort: str, wert, antworten: dict,
                   fragen: dict[str, Frage]) -> bool:
    if frage.typ == "Auswahl":
        wert = str(wert)
        teile = [t.strip() for t in re.split(r"\s+oder\s+|\s*/\s*", aktions_antwort)]
        if any(_alias_aufloesen(t, frage.antworten) == wert for t in teile
               if _alias_aufloesen(t, frage.antworten)):
            return True
        if "," in aktions_antwort and frage.bedingung and frage.bedingung.frage_id:
            vorne, hinten = (t.strip() for t in aktions_antwort.split(",", 1))
            eltern = fragen.get(frage.bedingung.frage_id)
            eltern_wert = str(antworten.get(frage.bedingung.frage_id) or "")
            if (eltern and _alias_aufloesen(hinten, frage.antworten) == wert
                    and _alias_aufloesen(vorne, eltern.antworten) == eltern_wert):
                return True
        return False
    # Zahlenfragen: Bereichsprüfung
    zahl = wert if isinstance(wert, (int, float)) else zahl_parsen(wert)
    if zahl is None:
        return False
    return _bereich_passt(aktions_antwort, zahl)


def aktion_finden(logik: Logik, frage: Frage, wert, antworten: dict) -> Optional[Aktion]:
    for aktion in logik.aktionen:
        if aktion.frage != frage.id:
            continue
        if _antwort_passt(frage, aktion.antwort, wert, antworten, logik.fragen):
            return aktion
    return None


def abbruch_pruefen(logik: Logik, frage: Frage, wert, antworten: dict) -> Optional[str]:
    """Liefert die ABBRUCH-Meldung, falls die Antwort zum Abbruch führt."""
    if frage.typ == "Wiederholfeld je Verteiler" and isinstance(wert, list):
        for einzel in wert:
            aktion = aktion_finden(logik, frage, einzel, antworten)
            if aktion and aktion.typ == "abbruch":
                return aktion.abbruch_meldung
        return None
    aktion = aktion_finden(logik, frage, wert, antworten)
    if aktion and aktion.typ == "abbruch":
        return aktion.abbruch_meldung
    return None


def abbruch_status(logik: Logik, antworten: dict) -> Optional[str]:
    """Prüft alle sichtbaren beantworteten Fragen auf ABBRUCH (für Statusneuberechnung)."""
    for frage in sichtbare_fragen(logik, antworten):
        if frage.id not in antworten:
            continue
        meldung = abbruch_pruefen(logik, frage, antworten[frage.id], antworten)
        if meldung:
            return meldung
    return None


# --- Leistungsklasse und Paketauflösung -----------------------------------

def leistungsklasse(logik: Logik, antworten: dict) -> Optional[PaketZeile]:
    verbrauch = antworten.get("F02")
    if verbrauch is None:
        return None
    zahl = verbrauch if isinstance(verbrauch, (int, float)) else zahl_parsen(verbrauch)
    if zahl is None:
        return None
    for zeile in logik.pakete:
        if zeile.verbrauch_von is not None and zeile.verbrauch_von <= zahl <= zeile.verbrauch_bis:
            return zeile
    return None


def paket_aufloesen(logik: Logik, antworten: dict) -> Optional[list[ArtikelRef]]:
    """Paketauflösung erst wenn F02 und F03 (ggf. F04) beantwortet sind."""
    zeile = leistungsklasse(logik, antworten)
    if zeile is None or "F03" not in antworten:
        return None
    if antworten["F03"] == "Nein":
        return zeile.ohne_ww
    f04 = str(antworten.get("F04") or "")
    if f04.startswith("bis 200"):
        return zeile.ww_bis_200
    if f04.startswith("300"):
        return zeile.ww_300
    return None


# --- Anzeige / Protokoll --------------------------------------------------

def antwort_anzeige(frage: Frage, wert) -> str:
    if isinstance(wert, dict):     # Mengenmaske F17
        return ", ".join(f"{k}: {int(v)}" for k, v in wert.items())
    if isinstance(wert, list):     # Wiederholfelder F20
        return ", ".join(f"Verteiler {i}: {int(v)} Gruppen"
                         for i, v in enumerate(wert, 1))
    if wert in (None, ""):
        return "– keine Angabe –"
    if isinstance(wert, float) and wert == int(wert):
        return str(int(wert))
    return str(wert)


def protokoll(logik: Logik, antworten: dict) -> list[dict]:
    """Konfigurationsprotokoll: alle sichtbaren beantworteten Fragen mit Antwort."""
    eintraege = []
    for frage in sichtbare_fragen(logik, antworten):
        if frage.id not in antworten:
            continue
        eintraege.append({
            "frage_id": frage.id,
            "frage": frage.text,
            "antwort": antwort_anzeige(frage, antworten[frage.id]),
        })
    return eintraege
