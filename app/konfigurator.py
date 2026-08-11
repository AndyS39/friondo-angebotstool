# Konfigurator-Engine (Phase 4, ab Phase 12 auf Logik v2 umgestellt):
# Sichtbarkeit, nächste Frage, Aktions-Matching (inkl. Zahlenbereiche,
# Slash-Listen mit paarweiser Artikel-Zuordnung), AMPEL-Auswertung statt
# Abbruch, Leistungsklasse, Paketauflösung, KfW-Ableitungen und Vorbelegungen.

import re
from datetime import date
from typing import Optional

from app.logik import (Aktion, ArtikelRef, Frage, Logik, PaketZeile,
                       FREITEXT_TYPEN, _alias_aufloesen, antwort_teile)

# Zentrale Fragen-IDs der Logik v2
ID_VERBRAUCH = "A03"          # Leistungsklasse
ID_WARMWASSER = "N02"
ID_WW_GROESSE = "N03"
ID_WIEDERHOL_ANZAHL = "H06"   # Anzahl Heizkreisverteiler -> Felder in H07
ID_OBJEKTART = "O01"
ID_WOHNEINHEITEN = "O03"
ID_FLAECHE = "O05"
ID_SELBSTNUTZUNG = "K01"
ID_ENERGIETRAEGER = "A01"
ID_HEIZUNG_BAUJAHR = "A02"
FRIONDO_FRAGEN = ("P01", "P02", "P03")

EFH_ARTEN = ("EFH", "REH", "RMH")


# --- Zahlen ---------------------------------------------------------------

def zahl_parsen(text) -> Optional[float]:
    """Deutsche Zahleneingabe: '8.000' -> 8000, '12,5' -> 12.5, '' -> None."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
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
    """Zahlenbereiche aus Aktionszeilen: '0 – 8.000 kWh', 'über 14', 'bis 4', 'ab 9.000'."""
    m = re.search(r"([\d.]+)\s*[–-]\s*([\d.]+)", text)
    if m:
        return zahl_parsen(m.group(1)) <= zahl <= zahl_parsen(m.group(2))
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
    """KfW-Ableitung lt. Blatt "KfW": EFH/REH/RMH automatisch Ja,
    2FH/MFH nach K01, Gewerbe nie."""
    objektart = str(antworten.get(ID_OBJEKTART) or "")
    if objektart in EFH_ARTEN:
        return True
    if objektart in ("2FH", "MFH"):
        return antworten.get(ID_SELBSTNUTZUNG) == "Ja"
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

def _teil_index(frage: Frage, aktions_antwort: str, wert, antworten: dict,
                fragen: dict[str, Frage]) -> Optional[int]:
    """Liefert den Index des passenden Teils einer (Slash-)Antwortliste
    oder None, wenn die Aktionszeile nicht passt."""
    teile = antwort_teile(aktions_antwort)

    if frage.typ == "Auswahl":
        wert = str(wert)
        for i, teil in enumerate(teile):
            if _alias_aufloesen(teil, frage.antworten) == wert:
                return i
        if "," in aktions_antwort and frage.bedingung and frage.bedingung.frage_id:
            vorne, hinten = (t.strip() for t in aktions_antwort.split(",", 1))
            eltern = fragen.get(frage.bedingung.frage_id)
            eltern_wert = str(antworten.get(frage.bedingung.frage_id) or "")
            if (eltern and _alias_aufloesen(hinten, frage.antworten) == str(wert)
                    and _alias_aufloesen(vorne, eltern.antworten) == eltern_wert):
                return 0
        return None

    zahl = wert if isinstance(wert, (int, float)) else zahl_parsen(wert)
    if zahl is None:
        return None
    for i, teil in enumerate(teile):
        if _bereich_passt(teil, zahl):
            return i
    return None


def aktion_finden(logik: Logik, frage: Frage, wert,
                  antworten: dict) -> Optional[tuple[Aktion, int]]:
    """Findet die passende Aktionszeile samt Teil-Index (für paarweise Listen)."""
    for aktion in logik.aktionen:
        if aktion.frage != frage.id:
            continue
        index = _teil_index(frage, aktion.antwort, wert, antworten, logik.fragen)
        if index is not None:
            return aktion, index
    return None


def refs_fuer_treffer(aktion: Aktion, teil_index: int) -> list[ArtikelRef]:
    """Paarweise Zuordnung: '50 l / 100 l / 200 l' -> 'Z15 / Z16 / Z17 ×1'
    liefert genau den Artikel des passenden Teils; sonst alle Referenzen."""
    teile = antwort_teile(aktion.antwort)
    if len(teile) > 1 and len(aktion.artikel) == len(teile):
        return [aktion.artikel[teil_index]]
    return list(aktion.artikel)


# --- AMPEL-Auswertung (v2: keine Abbrüche) --------------------------------

def ampel_gruende(logik: Logik, antworten: dict) -> list[str]:
    """Alle AMPEL-Gründe der sichtbaren beantworteten Fragen (Reihenfolge stabil)."""
    gruende: list[str] = []

    def merken(grund: str):
        if grund and grund not in gruende:
            gruende.append(grund)

    for frage in sichtbare_fragen(logik, antworten):
        if frage.id not in antworten:
            continue
        wert = antworten[frage.id]
        if frage.typ == "Wiederholfeld" and isinstance(wert, list):
            for einzel in wert:
                treffer = aktion_finden(logik, frage, einzel, antworten)
                if treffer and treffer[0].typ == "ampel":
                    merken(treffer[0].ampel_grund)
            continue
        if isinstance(wert, (dict, list)) or frage.typ in FREITEXT_TYPEN:
            continue
        treffer = aktion_finden(logik, frage, wert, antworten)
        if treffer and treffer[0].typ == "ampel":
            merken(treffer[0].ampel_grund)
    return gruende


# --- Leistungsklasse und Paketauflösung -----------------------------------

def leistungsklasse(logik: Logik, antworten: dict) -> Optional[PaketZeile]:
    zahl = zahl_parsen(antworten.get(ID_VERBRAUCH))
    if zahl is None:
        return None
    for zeile in logik.pakete:
        if zeile.verbrauch_von is not None and zeile.verbrauch_von <= zahl <= zeile.verbrauch_bis:
            return zeile
    return None


def paket_aufloesen(logik: Logik, antworten: dict) -> Optional[list[ArtikelRef]]:
    zeile = leistungsklasse(logik, antworten)
    if zeile is None or ID_WARMWASSER not in antworten:
        return None
    if antworten[ID_WARMWASSER] == "Nein":
        return zeile.ohne_ww
    groesse = str(antworten.get(ID_WW_GROESSE) or "")
    if groesse.startswith("bis 200"):
        return zeile.ww_bis_200
    if groesse.startswith("300"):
        return zeile.ww_300
    return None


# --- Vorbelegungen (Blatt "KfW" / Fragen-Hinweise) -------------------------

def vorbelegung(frage: Frage, antworten: dict) -> Optional[str]:
    """Vorbelegte Werte: O03 (WE aus Objektart) und K02 (Klima aus A01+A02)."""
    if frage.id == ID_WOHNEINHEITEN:
        objektart = str(antworten.get(ID_OBJEKTART) or "")
        if objektart in EFH_ARTEN:
            return "1"
        if objektart == "2FH":
            return "2"
        return None
    if frage.id == "K02" and len(frage.antworten) >= 3:
        energietraeger = str(antworten.get(ID_ENERGIETRAEGER) or "")
        if energietraeger in ("Öl", "Nachtspeicher"):
            return frage.antworten[0]
        baujahr = zahl_parsen(antworten.get(ID_HEIZUNG_BAUJAHR))
        if energietraeger == "Gas" and baujahr and (date.today().year - baujahr) >= 20:
            return frage.antworten[1]
        return frage.antworten[2]
    return None


# --- Anzeige / Protokoll --------------------------------------------------

def antwort_anzeige(frage: Frage, wert) -> str:
    if isinstance(wert, dict):     # Mengenmaske
        return ", ".join(f"{k}: {int(v)}" for k, v in wert.items())
    if isinstance(wert, list):     # Wiederholfelder
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
            "seite": frage.seite,
            "frage": frage.text,
            "antwort": antwort_anzeige(frage, antworten[frage.id]),
        })
    return eintraege


def kfw_daten(antworten: dict) -> dict:
    """KfW-relevante Antworten für die Ablage am Angebot (Ableitung in kfw.py)."""
    return {schluessel: antworten.get(schluessel)
            for schluessel in ("O01", "O03", "O05", "K01", "K02", "K03", "K04")
            if schluessel in antworten}
