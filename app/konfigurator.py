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
ID_VERBRAUCH = "A03"          # Leistungsklasse (kWh)
ID_HEIZLAST_BEKANNT = "A14"   # v8: Heizlast hat Vorrang vor der kWh-Zuordnung
ID_HEIZLAST = "A15"
ID_WARMWASSER = "N02"
ID_WW_GROESSE = "N03"
ID_WIEDERHOL_ANZAHL = "H06"   # Anzahl Heizkreisverteiler -> Felder in H07
ID_OBJEKTART = "O01"
ID_WOHNEINHEITEN = "O03"
ID_FLAECHE = "O05"
ID_SELBSTNUTZUNG = "K01"
ID_ENERGIETRAEGER = "A01"
ID_SOLARTHERMIE = "A10"       # v9: Übernahme steuert die Warmwasser-Schiene
SOLAR_UEBERNAHME = "Ja, soll übernommen werden"
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
    # v9: Bereiche auch mit Dezimal-Kommas ('16,0 – 18,5', 'ab 18,6')
    m = re.search(r"(\d[\d.,]*)\s*[–-]\s*(\d[\d.,]*)", text)
    if m:
        return zahl_parsen(m.group(1)) <= zahl <= zahl_parsen(m.group(2))
    m = re.search(r"über\s*(\d[\d.,]*)", text)
    if m:
        return zahl > zahl_parsen(m.group(1))
    m = re.search(r"\bbis\s*(\d[\d.,]*)", text)
    if m:
        return zahl <= zahl_parsen(m.group(1))
    m = re.search(r"\bab\s*(\d[\d.,]*)", text)
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


def _term_erfuellt(frage_id: str, werte: list[str], antworten: dict,
                   fragen: dict[str, Frage]) -> bool:
    wert = antworten.get(frage_id)
    if wert is None:
        return False
    ziel = fragen.get(frage_id)
    optionen = ziel.antworten if ziel else []
    erlaubt = {_alias_aufloesen(w, optionen) or w for w in werte}
    return str(wert) in erlaubt


def ist_sichtbar(frage: Frage, antworten: dict, fragen: dict[str, Frage],
                 logik: "Logik | None" = None) -> bool:
    b = frage.bedingung
    if b is None or b.art == "immer":
        return True
    if b.art == "klasse":
        # v9: sichtbar nur, wenn die ermittelte Leistungsklasse passt
        if logik is None:
            return False
        zeile = leistungsklasse(logik, antworten)
        return zeile is not None and zeile.leistungsklasse in b.werte
    if b.art == "selbstnutzung":
        return ist_selbstnutzung(antworten)
    if b.art == "ausgefuellt":
        wert = antworten.get(b.frage_id)
        return wert is not None and str(wert) != ""
    if b.art == "antwort":
        return _term_erfuellt(b.frage_id, b.werte, antworten, fragen)
    if b.art == "klauseln":
        # ODER über Klauseln, UND innerhalb einer Klausel (v3)
        return any(all(_term_erfuellt(fid, werte, antworten, fragen)
                       for fid, werte in klausel)
                   for klausel in b.klauseln)
    return False


MAX_WIEDERHOLUNGEN = 12   # v8: Obergrenze je Wiederholgruppe (z. B. Räume)


def _wiederhol_klone(frage: Frage, antworten: dict,
                     fragen: dict[str, Frage]) -> list[Frage]:
    """v8: Fragen einer Wiederholgruppe („je Raum (KO05)“) je Zähler klonen.
    Klon-IDs: „KR01#1“, „KR01#2“ … – normale Fragen für Seite, Prüfung und
    Protokoll. Ein Hinweis wie „… Optionen wie … (KO04)“ begrenzt die
    Auswahl dynamisch auf den Wert der referenzierten Zählfrage."""
    from dataclasses import replace as _replace
    b = frage.bedingung
    anzahl = int(zahl_parsen(antworten.get(b.frage_id)) or 0)
    anzahl = max(0, min(anzahl, MAX_WIEDERHOLUNGEN))
    optionen = frage.antworten
    m = re.search(r"Optionen wie .*\(([A-Z]{1,2}\d{2})\)", frage.hinweis)
    if m:
        limit = int(zahl_parsen(antworten.get(m.group(1))) or len(optionen))
        optionen = optionen[:max(1, limit)]
    # Sortierung: Raum 1 komplett, dann Raum 2 … – alle Klone liegen zwischen
    # der ersten Gruppenfrage und der nächsten regulären Frage
    gruppe = [f for f in fragen.values()
              if f.bedingung and f.bedingung.art == "wiederholgruppe"
              and f.bedingung.frage_id == b.frage_id]
    basis = min(f.reihenfolge for f in gruppe)
    breite = len(gruppe) * MAX_WIEDERHOLUNGEN + 1
    idx = sorted(f.reihenfolge for f in gruppe).index(frage.reihenfolge)
    klone = []
    for i in range(1, anzahl + 1):
        klone.append(_replace(
            frage, id=f"{frage.id}#{i}",
            text=f"Raum {i}: {frage.text}",
            reihenfolge=basis + ((i - 1) * len(gruppe) + idx) / breite,
            antworten=list(optionen),
            bedingung=None))
    return klone


def _frage_unterdrueckt(frage: Frage, logik: Logik, antworten: dict) -> bool:
    """v9-Sonderregeln jenseits der Excel-Bedingungen: Die WW-Größenfrage N03
    entfällt bei der Serie CS8800i (Klasse 15: Warmwasser fix über Pos. 065)."""
    if frage.id == ID_WW_GROESSE:
        # Solarthermie-Übernahme: Warmwasser über den bivalenten 390-l-Speicher
        if str(antworten.get(ID_SOLARTHERMIE) or "") == SOLAR_UEBERNAHME:
            return True
        zeile = leistungsklasse(logik, antworten)
        if zeile is not None and zeile.leistungsklasse == "15 kW":
            return True
    return False


def sichtbare_fragen(logik: Logik, antworten: dict) -> list[Frage]:
    ergebnis: list[Frage] = []
    for f in sorted(logik.fragen.values(), key=lambda f: f.reihenfolge):
        if f.bedingung is not None and f.bedingung.art == "wiederholgruppe":
            ergebnis.extend(_wiederhol_klone(f, antworten, logik.fragen))
            continue
        if _frage_unterdrueckt(f, logik, antworten):
            continue
        if ist_sichtbar(f, antworten, logik.fragen, logik):
            ergebnis.append(f)
    ergebnis.sort(key=lambda f: f.reihenfolge)
    return ergebnis


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

    # v8: bei bekannter Heizlast mit Matrix-Treffer entscheidet die Heizlast –
    # eine kWh-Angabe über 31.000 löst dann keine AMPEL mehr aus
    heizlast_greift = (heizlast_wert(antworten) is not None
                       and leistungsklasse(logik, antworten) is not None)
    for frage in sichtbare_fragen(logik, antworten):
        if frage.id not in antworten:
            continue
        if frage.id == ID_VERBRAUCH and heizlast_greift:
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

def heizlast_wert(antworten: dict) -> Optional[float]:
    """v8: angegebene Heizlast in kW (nur wenn A14 = Ja), sonst None."""
    if str(antworten.get(ID_HEIZLAST_BEKANNT) or "") != "Ja":
        return None
    return zahl_parsen(antworten.get(ID_HEIZLAST))


def leistungsklasse(logik: Logik, antworten: dict) -> Optional[PaketZeile]:
    # v8: eine bekannte Heizlast hat Vorrang vor der kWh-Zuordnung;
    # ab 16 kW passt keine Zeile mehr (AMPEL über die Aktionszeile zu A15)
    heizlast = heizlast_wert(antworten)
    if heizlast is not None:
        for zeile in logik.pakete:
            if (zeile.heizlast_von is not None
                    and zeile.heizlast_von <= heizlast <= zeile.heizlast_bis):
                return zeile
        return None
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
    solar_uebernahme = (str(antworten.get(ID_SOLARTHERMIE) or "")
                        == SOLAR_UEBERNAHME)
    if zeile.leistungsklasse == "15 kW":
        # v9 (Serie CS8800i): Außeneinheit (030/031) und Inneneinheit
        # (AWMB 055 / AWE 056 + Puffer) kommen über die Farb-/Pufferfragen;
        # aus der Matrix kommt nur das fixe Warmwasser (Pos. 065 bei N02 = Ja).
        # Solarthermie-Übernahme: bivalenter 390-l-Speicher (069) statt 065.
        if solar_uebernahme:
            return [ArtikelRef("069")]
        return [ArtikelRef("065")] if antworten[ID_WARMWASSER] == "Ja" else []
    if solar_uebernahme:
        # v9: Übernahme erzwingt die AWE-Variante + Pos. 069 (kein 065/067) –
        # das Warmwasser läuft über den bivalenten Solarspeicher, auch wenn
        # N02 = Nein erfasst wurde (fachlicher Hinweis macht darauf aufmerksam)
        return list(zeile.ohne_ww) + [ArtikelRef("069")]
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
    """Vorbelegte Werte: O03 (2 bei 2FH; Frage nur noch bei 2FH/MFH sichtbar)
    und K02 (Klima aus A01+A02)."""
    if frage.id == ID_WOHNEINHEITEN:
        if str(antworten.get(ID_OBJEKTART) or "") == "2FH":
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


def ampel_je_frage(logik: Logik, antworten: dict) -> dict[str, str]:
    """Frage-ID -> AMPEL-Grund für alle Antworten, die „individuell“ auslösten."""
    gruende: dict[str, str] = {}
    heizlast_greift = (heizlast_wert(antworten) is not None
                       and leistungsklasse(logik, antworten) is not None)
    for frage in sichtbare_fragen(logik, antworten):
        if frage.id not in antworten:
            continue
        if frage.id == ID_VERBRAUCH and heizlast_greift:
            continue   # v8: Heizlast hat Vorrang vor der kWh-AMPEL
        wert = antworten[frage.id]
        if frage.typ == "Wiederholfeld" and isinstance(wert, list):
            for einzel in wert:
                treffer = aktion_finden(logik, frage, einzel, antworten)
                if treffer and treffer[0].typ == "ampel":
                    gruende[frage.id] = treffer[0].ampel_grund
            continue
        if isinstance(wert, (dict, list)) or frage.typ in FREITEXT_TYPEN:
            continue
        treffer = aktion_finden(logik, frage, wert, antworten)
        if treffer and treffer[0].typ == "ampel":
            gruende[frage.id] = treffer[0].ampel_grund
    return gruende


def protokoll(logik: Logik, antworten: dict) -> list[dict]:
    """Konfigurationsprotokoll: alle sichtbaren beantworteten Fragen mit Antwort;
    AMPEL-Auslöser tragen ihren Grund (Phase 25)."""
    gruende = ampel_je_frage(logik, antworten)
    eintraege = []
    for frage in sichtbare_fragen(logik, antworten):
        if frage.id not in antworten:
            continue
        eintraege.append({
            "frage_id": frage.id,
            "seite": frage.seite,
            "frage": frage.text,
            "antwort": antwort_anzeige(frage, antworten[frage.id]),
            "ampel_grund": gruende.get(frage.id, ""),
        })
    return eintraege


def kfw_daten(antworten: dict) -> dict:
    """KfW-relevante Antworten für die Ablage am Angebot (Ableitung in kfw.py)."""
    return {schluessel: antworten.get(schluessel)
            for schluessel in ("O01", "O03", "O05", "K01", "K02", "K03", "K04")
            if schluessel in antworten}


def fachliche_hinweise(antworten: dict) -> list[str]:
    """v9: generische fachliche Hinweise am Vorgang (keine Blockade) –
    funktioniert mit Roh-Antworten UND mit den Anzeige-Strings aus dem
    Konfigurationsprotokoll (frage_id -> antwort)."""
    hinweise: list[str] = []
    if str(antworten.get(ID_SOLARTHERMIE) or "") == SOLAR_UEBERNAHME:
        if str(antworten.get(ID_WARMWASSER) or "") == "Nein":
            hinweise.append(
                "Widerspruch: Solarthermie-Übernahme erfasst, aber „Warmwasser "
                "über WP = Nein“ – Pos. 069 (bivalenter 390-l-Solarspeicher) "
                "wurde übernommen, bitte prüfen.")
        else:
            hinweise.append(
                "Warmwasser läuft über den bivalenten 390-l-Solarspeicher "
                "(Pos. 069) – Solarthermie-Übernahme.")
    return hinweise


def hinweise_aus_protokoll(protokoll: list[dict]) -> list[str]:
    """Fachliche Hinweise aus dem gespeicherten Konfigurationsprotokoll."""
    antworten = {e.get("frage_id"): e.get("antwort") for e in protokoll}
    return fachliche_hinweise(antworten)


def vermerke_fuer(logik: Logik, antworten: dict) -> list[str]:
    """v9: zutreffende Angebotsvermerke (Blatt "Vermerke") als Textliste."""
    ergebnis = []
    for vermerk in logik.vermerke:
        b = vermerk.bedingung
        if b is None:
            continue
        if b.art == "immer":
            ergebnis.append(vermerk.text)
        elif b.art == "antwort" and _term_erfuellt(b.frage_id, b.werte,
                                                   antworten, logik.fragen):
            ergebnis.append(vermerk.text)
        elif b.art == "klauseln" and any(
                all(_term_erfuellt(fid, werte, antworten, logik.fragen)
                    for fid, werte in klausel) for klausel in b.klauseln):
            ergebnis.append(vermerk.text)
    return ergebnis
