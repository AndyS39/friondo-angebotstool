# Logik-Import (Phase 3): Parser für konfigurator_logik.xlsx
# (Blätter Fragen, Aktionen, Paketmatrix, Angebotsaufbau, KfW) plus Validierung.
# Die geparste Logik wird im Prozess gecacht; "Konfiguration neu einlesen"
# ersetzt den Cache. Die inhaltliche Auswertung (Fragenfluss, KfW-Rechnung)
# folgt in den Phasen 4–6 – hier geht es um Struktur, Referenzen, Bedingungen.
# v13: PV-Konfigurator (Blätter „Aktionen PV“, „Angebotsaufbau PV“, „PV-Parameter“).
# v24 (PLAN_V16 Phase 113): Klimakonfigurator – Blätter „Aktionen KL“,
# „Angebotsaufbau KL“, „Paketmatrix KL“, „Kombinationen KL“, „Montagematrix KL“,
# „KL-Parameter“, „KL-Artikel“ (_kl_einlesen/_kl_pruefen, Felder kl_* der Logik,
# Sicht logik_fuer_sparte(logik, "KL")); Rechenweg in app/kl_auslegung.py.

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import openpyxl
from sqlalchemy.orm import Session

from app import config
from app.models import Artikel

FRAGE_TYPEN = {
    "Auswahl",
    "Zahleneingabe",
    "Betragseingabe",
    "Mengenmaske",
    "Wiederholfeld",
    "Freitext",
    "Freitext groß",
    "Datum",            # v8: Datumseingabe (z. B. Wiedervorlage der Einschätzung)
}

# Alt-/Varianten-Schreibweisen werden beim Einlesen normalisiert
TYP_ALIASE = {
    "Mengenmaske (4 Zahlenfelder)": "Mengenmaske",
    "Mengenmaske (2 Zahlenfelder)": "Mengenmaske",
    "Wiederholfeld je Verteiler": "Wiederholfeld",
}

ZAHLEN_TYPEN = {"Zahleneingabe", "Betragseingabe", "Mengenmaske", "Wiederholfeld"}

FREITEXT_TYPEN = {"Freitext", "Freitext groß"}

# Aktionszeilen, die keine einzelne Frage betreffen
SPEZIAL_AKTIONEN = {"Gruppen-Trigger", "Grundpaket", "Ampel-Auswertung",
                    "O01–O08 / K01–K04", "O01-O08 / K01-K04"}


# --- Datenstrukturen ------------------------------------------------------

@dataclass
class Bedingung:
    roh: str
    # immer | antwort | ausgefuellt | selbstnutzung | friondo_ja | klauseln |
    # wiederholgruppe (v8: „je Raum (KO05)“ – Frage wiederholt sich je Zähler)
    art: str
    frage_id: Optional[str] = None
    werte: list[str] = field(default_factory=list)
    # v3: ODER-verknüpfte Klauseln, jede Klausel = UND-Liste von (frage_id, werte),
    # z. B. "nur wenn A04 = KG oder EG, oder (A04 = DG und D01 = Nein)"
    klauseln: list[list[tuple[str, list[str]]]] = field(default_factory=list)


@dataclass
class Frage:
    id: str
    reihenfolge: int
    text: str
    typ: str
    antworten: list[str]
    bedingung: Optional[Bedingung]
    hinweis: str
    seite: str = ""          # Kategorie-Seite der mobilen Erfassung (v2)


@dataclass
class ArtikelRef:
    ref: str                      # "045" oder "Z01"
    menge: str = "1"              # roh: "1", "2", "eingegebene Meter", "Anzahl Verteiler", ...
    ep: bool = False
    kein_ep: bool = False         # v8: "(kein EP)" – überschreibt das EP-Flag des Artikelstamms


@dataclass
class Aktion:
    frage: str                    # "A01" oder Spezialschlüssel (Gruppen-Trigger, Grundpaket, ...)
    antwort: str                  # roh, z. B. "Gas", "Kunststoff, bis 3.000 L", "50 l / 100 l / 200 l"
    aktion_roh: str
    typ: str                      # ampel | normal
    ampel_grund: str              # Klartext-Grund bei AMPEL-Antworten (v2: kein Abbruch)
    artikel: list[ArtikelRef]
    bemerkung: str
    # v13-PV: optionale Zusatzbedingung (Blatt „Aktionen PV“, Spalte E),
    # z. B. „nur wenn PA02 = Nein“ – die Zeile greift nur, wenn sie erfüllt ist
    zusatz_bedingung: Optional["Bedingung"] = None


@dataclass
class PaketZeile:
    leistungsklasse: str
    verbrauch_roh: str
    verbrauch_von: Optional[int]
    verbrauch_bis: Optional[int]
    ww_bis_200: list[ArtikelRef]
    ohne_ww: list[ArtikelRef]
    ww_300: list[ArtikelRef]
    # v8: Heizlast-Spalte (kW, Dezimalzahlen) – hat bei Bekanntsein Vorrang
    heizlast_roh: str = ""
    heizlast_von: Optional[float] = None
    heizlast_bis: Optional[float] = None


@dataclass
class AngebotsBlock:
    nr: int
    ueberschrift: str
    inhalt_roh: str
    wann: Optional[Bedingung]
    refs: list[ArtikelRef]


@dataclass
class KlPaketZeile:
    """v24 (PLAN_V16 Phase 113): Zeile des Blatts „Paketmatrix KL“ – Serie (KO06),
    Typ single | multi_innen | multi_aussen, Klasse roh („9“, „18 / 24“, „53/2“),
    Kühllast-/Innengeräte-Spalte roh, alle KL-Nummern der Artikelzelle in
    Reihenfolge; „nicht im Sortiment“ → Ampel (Grund aus der Bemerkung nach „→ AMPEL: “)."""
    serie: str
    typ: str
    klasse: str
    kuehllast: str
    artikel: list[str]
    bemerkung: str
    nicht_im_sortiment: bool = False
    typ_roh: str = ""
    artikel_roh: str = ""
    ampel_grund: str = ""


@dataclass
class Anhang:
    datei: str                              # Dateiname im Ordner anlagen/
    regel_roh: str
    art: str                                # immer | frage | position | unbekannt
    frage_id: str = ""
    antwort: str = ""
    positionen: list[str] = field(default_factory=list)
    bemerkung: str = ""
    # v11 (Phase 67): Profile, bei denen der Anhang NICHT mitgeht
    # (Spalte "Nicht bei Profil", kommagetrennt, z. B. "Enni, SWD")
    nicht_bei_profil: list[str] = field(default_factory=list)


@dataclass
class Vermerk:
    """v9: bedingter Angebotsvermerk (Blatt "Vermerke") – Text erscheint als
    Absatz im PDF, wenn die Bedingung auf die Antworten zutrifft."""
    text: str
    bedingung: Optional[Bedingung]
    platzierung: str = "Ende Positionsteil"


@dataclass
class BafaAnlage:
    """v19 (PLAN_V14 Phase 95): Zeile des Blatts "BAFA-Anlagen" – Schlüssel
    = WP-Paket-Position ("045") bzw. Klasse + Inneneinheit ("15+055");
    "vorrat:…" = Stammdaten ohne Konfigurator-Anbindung."""
    schluessel: str
    nummer: str
    hersteller: str
    bezeichnung: str
    kw: Optional[float]
    kaeltemittel: str = ""
    netzdienlich: str = ""
    ee_anzeige: str = ""
    hinweis: str = ""

    @property
    def anzeige(self) -> str:
        return f"{self.bezeichnung} · BAFA {self.nummer}"


@dataclass
class Logik:
    fragen: dict[str, Frage]
    aktionen: list[Aktion]
    pakete: list[PaketZeile]
    bloecke: list[AngebotsBlock]
    kfw: dict[str, tuple[str, str]]         # Parameter -> (Wert, Bemerkung)
    geladen_am: datetime
    anhaenge: list[Anhang] = field(default_factory=list)
    # v8: reine Erfassungsbögen je Sparte (Blätter "Fragen PV" / "Fragen KL"),
    # ohne Artikel-Aktionen – laufen über die TAIFUN-Schiene
    sparten_fragen: dict[str, dict[str, Frage]] = field(default_factory=dict)
    vermerke: list[Vermerk] = field(default_factory=list)   # v9
    # v13-PV (PLAN_V13): PV-Konfigurator – Blätter „Aktionen PV“,
    # „Angebotsaufbau PV“, „PV-Parameter“; sparte kennzeichnet die Sicht
    # aus logik_fuer_sparte; pv_kombis = WR/Speicher-Kombis aus dem
    # Artikelstamm (Serie, WR-kW, Speicher-Stufe, PV-Nr.)
    pv_aktionen: list[Aktion] = field(default_factory=list)
    pv_bloecke: list[AngebotsBlock] = field(default_factory=list)
    pv_parameter: dict[str, tuple[str, str]] = field(default_factory=dict)
    # v22: Einheit je PV-Parameter (nur Anzeige in der Parametrierung)
    pv_parameter_einheit: dict[str, str] = field(default_factory=dict)
    sparte: str = "WP"
    pv_kombis: list[tuple[str, float, float, str]] = field(default_factory=list)
    bafa_anlagen: list[BafaAnlage] = field(default_factory=list)   # v19
    # v24 (PLAN_V16 Phase 113): Klimakonfigurator – Blätter „Aktionen KL“,
    # „Angebotsaufbau KL“, „Paketmatrix KL“, „Kombinationen KL“,
    # „Montagematrix KL“, „KL-Parameter“, „KL-Artikel“ (vereinbarte Schnittstelle
    # zu app/kl_auslegung.py, siehe diagnose/v24_agenten_briefing.md)
    kl_aktionen: list[Aktion] = field(default_factory=list)
    kl_bloecke: list[AngebotsBlock] = field(default_factory=list)
    kl_paket: list[KlPaketZeile] = field(default_factory=list)
    # Außengerät-Bezeichnung → Anzahl Innengeräte → {„9+9+12“, …} (Codes aufsteigend)
    kl_kombis: dict[str, dict[int, set[str]]] = field(default_factory=dict)
    kl_kombi_artikel: dict[str, str] = field(default_factory=dict)   # Außengerät → KL-Nr.
    kl_montage: dict[tuple[int, int], str] = field(default_factory=dict)  # (Innen, Außen) → KL-Nr.
    kl_montage_zeilen: list[dict] = field(default_factory=list)   # Rohzeilen (Lesesicht)
    kl_montage_ampel: str = ""                                    # Bemerkung „alle anderen“
    kl_parameter: dict[str, tuple[str, str]] = field(default_factory=dict)
    kl_parameter_einheit: dict[str, str] = field(default_factory=dict)
    kl_artikel: dict[str, str] = field(default_factory=dict)      # GUID → KL-Nr. (Pinning)
    kl_artikel_nummern: list[str] = field(default_factory=list)   # alle KL-Nr. des Blatts
    kl_artikel_zeilen: list[dict] = field(default_factory=list)   # Rohzeilen (Lesesicht)

    @property
    def seiten(self) -> list[str]:
        """Seiten der mobilen Erfassung in Blatt-Reihenfolge."""
        ergebnis: list[str] = []
        for frage in sorted(self.fragen.values(), key=lambda f: f.reihenfolge):
            if frage.seite and frage.seite not in ergebnis:
                ergebnis.append(frage.seite)
        return ergebnis


@dataclass
class Pruefbericht:
    fehler: list[str] = field(default_factory=list)
    warnungen: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.fehler


# --- Referenzen und Bedingungen parsen ------------------------------------

def refs_extrahieren(text: str) -> list[ArtikelRef]:
    """Extrahiert Artikel-Referenzen: 'Pos. 045', Listen ('Pos. 003, 005, 007 (EP)'),
    Slash-Listen ('Pos. 149 / 150 / 153'), Z-Artikel inkl. Bereichen ('Z01–Z14')."""
    if not text:
        return []
    refs: list[ArtikelRef] = []

    menge_muster = r"\s*×\s*(\([^)]*\)|[\wäöüÄÖÜß. ]+)"   # auch "(Eingabe − 3)"
    gefunden: list[tuple[int, ArtikelRef]] = []

    for m in re.finditer(r"Pos\.\s*((?:\d{1,3}(?:\s*\(EP\))?\s*(?:[,/]\s*)?)+)", text):
        nummern = re.findall(r"(\d{1,3})(\s*\(EP\))?", m.group(1))
        rest = text[m.end():]
        m_menge = re.match(menge_muster, rest)
        menge = m_menge.group(1).strip() if m_menge else "1"
        menge = re.sub(r"\s*als EP.*$", "", menge).strip() or "1"
        ep_nach = bool(re.match(r"[^+·]*als EP", rest))
        kein_ep = bool(re.match(r"[^+·]*\(kein EP\)", rest))   # v8: EP-Flag unterdrücken
        for i, (nummer, ep) in enumerate(nummern):
            gefunden.append((m.start() + i,
                             ArtikelRef(nummer.zfill(3), menge, bool(ep) or ep_nach,
                                        kein_ep)))

    # v13-PV: PV-Artikel „PV013“, optional „(EP)“ und Menge „× Modulanzahl“
    for m in re.finditer(r"\bPV(\d{3})\b(\s*\(EP\))?", text):
        rest = text[m.end():]
        m_menge = re.match(menge_muster, rest)
        menge = m_menge.group(1).strip() if m_menge else "1"
        gefunden.append((m.start(), ArtikelRef(f"PV{m.group(1)}", menge,
                                               bool(m.group(2)))))

    # v24 (PLAN_V16 Phase 113): Klima-Artikel „KL013“, optional „(EP)“; Menge als
    # Zahl („× 5“) oder Mengenwort („× Innengeräte“ = Σ Räume, „× Außengeräte“ =
    # KO04) – Mengenwörter bleiben als Text in ArtikelRef.menge und werden in
    # app/kl_auslegung.py aufgelöst. „… als EP“ setzt das EP-Flag (wie WP);
    # Zeilen-Suffixe „je Außengerät“ / „je betroffenem Außengerät“ / „je Raum“
    # hängen nur an der letzten Referenz der Zeile und gelten laut Plan für die
    # ganze Zeile (kl_auslegung liest sie aus aktion_roh) – hier nur abschneiden.
    for m in re.finditer(r"\bKL(\d{3})\b(\s*\(EP\))?", text):
        rest = text[m.end():]
        m_menge = re.match(menge_muster, rest)
        menge = m_menge.group(1).strip() if m_menge else "1"
        menge = re.sub(r"\s+(als EP|je)\b.*$", "", menge).strip() or "1"
        ep_nach = bool(re.match(r"[^+·]*\bals EP\b", rest))
        gefunden.append((m.start(), ArtikelRef(f"KL{m.group(1)}", menge,
                                               bool(m.group(2)) or ep_nach)))

    for m in re.finditer(r"\bZ(\d{2})\b(?:\s*[–-]\s*Z(\d{2}))?", text):
        von, bis = int(m.group(1)), int(m.group(2) or m.group(1))
        rest = text[m.end():]
        m_menge = re.match(menge_muster, rest)
        menge = m_menge.group(1).strip() if (m_menge and von == bis) else "1"
        for n in range(von, bis + 1):
            gefunden.append((m.start() + (n - von),
                             ArtikelRef(f"Z{n:02d}", menge, False)))

    # Reihenfolge wie im Text – wichtig für die paarweise Zuordnung zu Slash-Listen
    gefunden.sort(key=lambda t: t[0])
    refs.extend(ref for _, ref in gefunden)
    return refs


def bedingung_parsen(roh) -> Optional[Bedingung]:
    """Parst 'Anzeigen wenn' / 'Wann'; None bei nicht parsebarer Bedingung."""
    text = str(roh or "").strip()
    if text in ("", "immer", "–", "-"):
        return Bedingung(text, "immer")
    if re.match(r"nur bei Selbstnutzung", text):
        return Bedingung(text, "selbstnutzung")
    if re.search(r"Friondo-Ja", text):
        return Bedingung(text, "friondo_ja")
    # v8: Wiederholgruppe – „je Raum (KO05)“: Fragen wiederholen sich so oft,
    # wie die referenzierte Zählfrage angibt
    m = re.match(r"je\s+\S+\s*\(([A-Z]{1,2}\d{2})\)$", text)
    if m:
        return Bedingung(text, "wiederholgruppe", m.group(1))
    # v9: klassenabhängige Fragen – „nur wenn Klasse = 15 kW“ bzw.
    # „nur wenn Klasse = 4 kW oder 6 kW …“ (ermittelte Leistungsklasse)
    m = re.match(r"nur wenn Klasse\s*=\s*(.+)$", text)
    if m:
        return Bedingung(text, "klasse",
                         werte=[w.strip() for w in m.group(1).split(" oder ")])
    m = re.match(r"nur wenn ([A-Z]{1,2}\d{2})\s+ausgefüllt$", text)
    if m:
        return Bedingung(text, "ausgefuellt", m.group(1))
    m = re.match(r"nur wenn (.+)$", text)
    if m:
        # ", oder " trennt ODER-Klauseln; innerhalb einer Klausel trennt " und ";
        # " oder " ohne Komma trennt Werte derselben Frage ("KG oder EG")
        klauseln: list[list[tuple[str, list[str]]]] = []
        for klausel_text in re.split(r",\s*oder\s+", m.group(1)):
            klausel_text = klausel_text.strip()
            if klausel_text.startswith("(") and klausel_text.endswith(")"):
                klausel_text = klausel_text[1:-1].strip()
            terme: list[tuple[str, list[str]]] = []
            for teil in re.split(r"\s+und\s+", klausel_text):
                tm = re.match(r"([A-Z]{1,2}\d{2})\s*=\s*(.+)$", teil.strip())
                if tm is None:
                    return None
                terme.append((tm.group(1),
                              [w.strip() for w in tm.group(2).split(" oder ")]))
            klauseln.append(terme)
        if len(klauseln) == 1 and len(klauseln[0]) == 1:
            frage_id, werte = klauseln[0][0]
            return Bedingung(text, "antwort", frage_id, werte)
        return Bedingung(text, "klauseln", klauseln=klauseln)
    return None


def _alias_aufloesen(wert: str, optionen: list[str]) -> Optional[str]:
    """Antwort-Alias auf eine Option abbilden:
    - 'beides' -> Option mit ' und '
    - eindeutiger Präfix, z. B. 'Mehrfamilienhaus' -> 'Mehrfamilienhaus (2+ WE)'"""
    if wert in optionen:
        return wert
    if wert.lower() == "beides":
        for option in optionen:
            if " und " in option:
                return option
    praefix_treffer = [o for o in optionen if o.startswith(wert)]
    if len(praefix_treffer) == 1:
        return praefix_treffer[0]
    return None


# --- Excel einlesen -------------------------------------------------------

def _zelle(wert) -> str:
    return str(wert).strip() if wert is not None else ""


def logik_einlesen() -> tuple[Logik, Pruefbericht]:
    bericht = Pruefbericht()
    wb = openpyxl.load_workbook(config.LOGIK_EXCEL_PFAD, data_only=True)

    for blatt in ("Fragen", "Aktionen", "Paketmatrix", "Angebotsaufbau", "KfW"):
        if blatt not in wb.sheetnames:
            bericht.fehler.append(f"Blatt „{blatt}“ fehlt in der Logik-Excel.")
    if bericht.fehler:
        return Logik({}, [], [], [], {}, datetime.now()), bericht

    fragen = _fragen_einlesen(wb, bericht)
    aktionen = _aktionen_einlesen(wb, bericht)
    pakete = _paketmatrix_einlesen(wb, bericht)
    bloecke = _angebotsaufbau_einlesen(wb, bericht)
    kfw = _kfw_einlesen(wb, bericht)
    anhaenge = _anhaenge_einlesen(wb, bericht)

    # v8: reine Erfassungsbögen PV/KL (eigene Blätter, ohne Artikel-Aktionen)
    sparten_fragen: dict[str, dict[str, Frage]] = {}
    for sparte, blatt in (("PV", "Fragen PV"), ("KL", "Fragen KL")):
        if blatt not in wb.sheetnames:
            bericht.warnungen.append(
                f"Blatt „{blatt}“ fehlt – die {sparte}-Erfassung läuft nur als Freitext.")
            continue
        sparten_fragen[sparte] = _fragen_einlesen(wb, bericht, blatt)

    logik = Logik(fragen, aktionen, pakete, bloecke, kfw, datetime.now(), anhaenge,
                  sparten_fragen, _vermerke_einlesen(wb, bericht))
    logik.bafa_anlagen = _bafa_einlesen(wb, bericht)   # v19 (PLAN_V14 Phase 95)
    _querbezuege_pruefen(logik, bericht)
    for sparte, sfragen in sparten_fragen.items():
        _bedingungen_pruefen(sfragen, bericht, f"Fragen {sparte}")
    _pv_einlesen(wb, logik, bericht)   # v13-PV
    _kl_einlesen(wb, logik, bericht)   # v24 Klimakonfigurator
    return logik, bericht


# --- v13-PV: PV-Konfigurator ------------------------------------------------

# Spezialzeilen im Blatt „Aktionen PV“ (keine Frage des Bogens)
PV_SPEZIAL = {"Grundpaket", "Gruppen-Trigger", "Strings", "WR/Speicher",
              "Ampel-Auswertung"}

PFLICHT_PV_PARAMETER = [
    "Modulleistung", "Modul-Leerlaufspannung", "Max. Stringspannung",
    "Faktor Haushalt", "Faktor Wärmepumpe", "Spezifischer Ertrag",
    "JAZ-Umrechnung Gas/Öl → Strom", "WR-Faktor (kWp ÷ WR-Leistung)",
    "WR-Stufen TP2", "WR-Stufen SigenStor", "Max. WR-Leistung",
    "Eigenverbrauchsquote PV", "Eigenverbrauch Zuschlag Speicher",
    "Eigenverbrauch Zuschlag HEMS", "Strompreis", "Einspeisevergütung",
]


def _pv_einlesen(wb, logik: Logik, bericht: Pruefbericht) -> None:
    """Blätter „Aktionen PV“ (Frage · Antwort · Aktion · Bemerkung ·
    Zusatzbedingung), „Angebotsaufbau PV“ (wie „Angebotsaufbau“) und
    „PV-Parameter“ (Parameter · Wert · Einheit · Bemerkung). Fehlen sie,
    bleibt PV ein reiner Erfassungsbogen (TAIFUN-Schiene)."""
    if "Aktionen PV" not in wb.sheetnames:
        return
    for blatt in ("Angebotsaufbau PV", "PV-Parameter"):
        if blatt not in wb.sheetnames:
            bericht.fehler.append(f"Blatt „{blatt}“ fehlt (Pflicht zu „Aktionen PV“).")
            return
    for row in wb["Aktionen PV"].iter_rows(min_row=2, values_only=True):
        frage, antwort, aktion_roh, bemerkung, zusatz = (
            _zelle(v) for v in (tuple(row) + (None,) * 5)[:5])
        if not frage:
            continue
        if aktion_roh.startswith("AMPEL"):
            m = re.search(r"Grund:\s*(.+)$", aktion_roh)
            typ, grund = "ampel", (m.group(1).strip() if m else aktion_roh)
        else:
            typ, grund = "normal", ""
        zusatz_b = None
        if zusatz:
            zusatz_b = bedingung_parsen(zusatz)
            if zusatz_b is None:
                bericht.fehler.append(
                    f"Aktionen PV {frage}: Zusatzbedingung „{zusatz}“ nicht parsebar.")
        logik.pv_aktionen.append(Aktion(frage, antwort, aktion_roh, typ, grund,
                                        refs_extrahieren(aktion_roh), bemerkung,
                                        zusatz_b))
    for row in wb["Angebotsaufbau PV"].iter_rows(min_row=2, values_only=True):
        nr, ueberschrift, inhalt, wann = (_zelle(v) for v in (tuple(row) + (None,) * 4)[:4])
        if not nr:
            continue
        try:
            block_nr = int(float(nr))
        except ValueError:
            continue   # Erläuterungszeilen (z. B. „Nachtexte“)
        bedingung = bedingung_parsen(wann)
        if bedingung is None:
            bericht.fehler.append(
                f"Angebotsaufbau PV Block {block_nr}: Bedingung „{wann}“ nicht parsebar.")
        logik.pv_bloecke.append(AngebotsBlock(block_nr, ueberschrift, inhalt,
                                              bedingung, refs_extrahieren(inhalt)))
    for row in wb["PV-Parameter"].iter_rows(min_row=2, values_only=True):
        name, wert, einheit, bemerkung = (_zelle(v) for v in (tuple(row) + (None,) * 4)[:4])
        if name:
            logik.pv_parameter[name] = (wert, bemerkung)
            logik.pv_parameter_einheit[name] = einheit
    _pv_pruefen(logik, bericht)


def _pv_pruefen(logik: Logik, bericht: Pruefbericht) -> None:
    fragen = logik.sparten_fragen.get("PV", {})
    for name in PFLICHT_PV_PARAMETER:
        if name not in logik.pv_parameter:
            bericht.fehler.append(f"PV-Parameter: „{name}“ fehlt.")
            continue
        wert = logik.pv_parameter[name][0]
        teile = [t for t in re.split(r"[;,]\s+|\s*;\s*", wert) if t] if "Stufen" in name else [wert]
        for teil in teile:
            if _pv_zahl(teil) is None:
                bericht.fehler.append(f"PV-Parameter „{name}“: „{wert}“ ist keine Zahl.")
                break
    # v22 (PLAN_V15 Phase 102): Parameter der Wirtschaftlichkeit – fehlende
    # Zeilen blockieren nicht (Standardwert im Code), werden aber mit dem
    # Standardwert als Hinweis gemeldet; vorhandene, unlesbare Werte sind Fehler
    from app import wirtschaftlichkeit
    _param, fehlende = wirtschaftlichkeit.parameter_lesen(logik.pv_parameter)
    neue_namen = {zeile[0] for zeile in wirtschaftlichkeit.NEUE_PARAMETER_ZEILEN}
    for name in fehlende:
        if name not in neue_namen:
            continue        # Ertrag/Strompreis/Vergütung sind bereits Pflicht (oben)
        if name in logik.pv_parameter:
            bericht.fehler.append(
                f"PV-Parameter „{name}“: „{logik.pv_parameter[name][0]}“ ist nicht lesbar.")
        else:
            bericht.warnungen.append(
                f"PV-Parameter „{name}“ fehlt – Standardwert "
                f"{wirtschaftlichkeit.standardwert_text(name)} wird verwendet "
                "(Wirtschaftlichkeit v22).")
    for aktion in logik.pv_aktionen:
        if aktion.frage in PV_SPEZIAL:
            continue
        if aktion.frage not in fragen:
            bericht.fehler.append(
                f"Aktionen PV: unbekannte Frage „{aktion.frage}“ (Antwort „{aktion.antwort}“).")
            continue
        problem = _antwort_pruefen(fragen[aktion.frage], aktion.antwort, fragen)
        if problem:
            bericht.fehler.append(f"Aktionen PV {aktion.frage}: {problem}")
        b = aktion.zusatz_bedingung
        if b is not None:
            terme = ([(b.frage_id, b.werte)] if b.art == "antwort"
                     else [t for k in b.klauseln for t in k])
            for fid, _werte in terme:
                if fid not in fragen:
                    bericht.fehler.append(
                        f"Aktionen PV {aktion.frage}: Zusatzbedingung verweist auf "
                        f"unbekannte Frage {fid}.")
    # Doppler-Schutz (wie _doppelquellen_pruefen bei WP): ein Artikel aus
    # Grundpaket/Gruppen-Trigger darf nicht zusätzlich über eine Fragezeile
    # kommen – er würde sonst doppelt berechnet
    immer_refs = {r.ref: a.frage for a in logik.pv_aktionen
                  if a.frage in ("Grundpaket", "Gruppen-Trigger") for r in a.artikel}
    for aktion in logik.pv_aktionen:
        if aktion.typ != "normal" or aktion.frage in PV_SPEZIAL:
            continue
        for ref in aktion.artikel:
            if ref.ref in immer_refs:
                bericht.warnungen.append(
                    f"Doppelte Artikelquelle PV: {ref.ref} kommt über „{immer_refs[ref.ref]}“ "
                    f"UND über die Aktionszeile {aktion.frage} („{aktion.antwort}“) – "
                    "der Artikel würde doppelt im Angebot landen.")
    # jede Auswahl-Option der PV-Fragen, die eine Aktionszeile hat, vollständig?
    for frage in fragen.values():
        zeilen = [a for a in logik.pv_aktionen if a.frage == frage.id]
        if frage.typ != "Auswahl" or not zeilen:
            continue
        abgedeckt = {o for a in zeilen for t in [a.antwort] + antwort_teile(a.antwort)
                     if (o := _alias_aufloesen(t, frage.antworten))}
        fehlend = [o for o in frage.antworten if o not in abgedeckt]
        if fehlend:
            bericht.warnungen.append(
                f"Aktionen PV {frage.id}: keine Aktionszeile für Option(en) {', '.join(fehlend)}.")


def _pv_zahl(text) -> Optional[float]:
    t = str(text or "").strip().replace(" ", "").replace("%", "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


# --- v24 (PLAN_V16 Phase 113): Klimakonfigurator ---------------------------------

# Spezialzeilen im Blatt „Aktionen KL“ (keine Frage des Bogens): „Grundpaket“
# (Systemgarantie, Montagepauschale), „Auslegung“ (Dokumentation des Rechenwegs –
# ausgewertet in app/kl_auslegung.py), „§14a“ (Parameterliste), „Händisch“
# (nur im Editor)
KL_SPEZIAL = {"Grundpaket", "Auslegung", "§14a", "Händisch", "Gruppen-Trigger",
              "Ampel-Auswertung"}

# zulässige Klassen-Codes im Blatt „Kombinationen KL“ (Bosch; Code 7 wird nicht
# vergeben, bleibt der Vollständigkeit halber zulässig)
KL_CODES = ("7", "9", "12", "18", "24")

# Typ-Spalte der Paketmatrix KL → Schnittstellenwert
KL_PAKET_TYPEN = {
    "single": "single",
    "multi-innengerät": "multi_innen", "multi-innengeraet": "multi_innen",
    "multi innengerät": "multi_innen", "multi_innen": "multi_innen",
    "multi-außengerät": "multi_aussen", "multi-aussengerät": "multi_aussen",
    "multi außengerät": "multi_aussen", "multi_aussen": "multi_aussen",
    "multi": "multi_aussen",
}

# Pflichtzeilen des Blatts „KL-Parameter“ (Namen wörtlich aus
# docs/KL-Logik-Entwurf.xlsx) mit ihren Standardwerten. Die Werte im Code sind
# nur Fallback: fehlt eine Zeile, meldet die Validierung sie als Hinweis mit dem
# Standardwert (wie die Wirtschaftlichkeits-Parameter PV v22); ein vorhandener,
# unlesbarer Zahlenwert ist ein Fehler.
STANDARD_KL_PARAMETER: dict[str, str] = {
    "W/m² normal": "60",
    "W/m² stark": "90",
    "Höhenfaktor bis 2,5 m": "1,0",
    "Höhenfaktor 2,5–3 m": "1,1",
    "Höhenfaktor über 3 m": "1,2",
    "Klasse 9 bis": "2,6",
    "Klasse 12 bis": "3,5",
    "Klasse 18 bis": "5,3",
    "Klasse 24 bis": "7,0",
    "Leitung je Innengerät inklusive": "5",
    "Meterposition Zusatzleitung": "KL017",
    "Standardserie": "Climate 3200i (Standard)",
    "Max. Innengeräte je Außengerät": "5",
    "Max. Außengeräte": "3",
    "§14a-Außengeräte": "CL5000M 105/4 E; CL5000M 125/5 E",
    "Gewerbe-Verhalten": "Hinweis",
    "Rollgerüst VK": "499",
}
PFLICHT_KL_PARAMETER = list(STANDARD_KL_PARAMETER)
KL_TEXT_PARAMETER = ("Meterposition Zusatzleitung", "Standardserie",
                     "§14a-Außengeräte", "Gewerbe-Verhalten")
KL_ZAHL_PARAMETER = [n for n in PFLICHT_KL_PARAMETER if n not in KL_TEXT_PARAMETER]
KL_PFLICHT_BLAETTER = ("Angebotsaufbau KL", "Paketmatrix KL", "Kombinationen KL",
                       "Montagematrix KL", "KL-Parameter", "KL-Artikel")
# Fragen, ohne die der Rechenkern (app/kl_auslegung.py) nicht arbeiten kann
KL_PFLICHT_FRAGEN = ("KO04", "KO05", "KO06", "KO08", "KR01", "KR07", "KR08",
                     "KR09", "KR10")


def kl_standardwert_text(name: str) -> str:
    """Standardwert eines KL-Parameters als Anzeigetext (Parametrierung)."""
    return STANDARD_KL_PARAMETER.get(name, "")


def kl_parameter_fehlende(logik: Logik) -> list[str]:
    """Pflichtzeilen des Blatts „KL-Parameter“ ohne Wert (Parametrierung zeigt
    sie mit dem Standardwert an)."""
    return [name for name in PFLICHT_KL_PARAMETER
            if not str(logik.kl_parameter.get(name, ("", ""))[0]).strip()]


def _kl_zahl(text) -> Optional[float]:
    """Parameterwert als Zahl: „1,1“ / „1.1“ / „60“ / „2,6 kW“ / „499 € netto“."""
    t = re.sub(r"\s*(kW|W/m²|m|€.*|%)\s*$", "", str(text or "").strip())
    return _pv_zahl(t)


def _kl_ganzzahl(text: str) -> Optional[int]:
    """„3“ / „3.0“ → 3; sonst None (Montagematrix, Kombinationen)."""
    m = re.fullmatch(r"(\d+)(?:[.,]0+)?", str(text or "").strip())
    return int(m.group(1)) if m else None


def _kl_einlesen(wb, logik: Logik, bericht: Pruefbericht) -> None:
    """Blätter des Klimakonfigurators. Fehlt „Aktionen KL“, bleibt KL ein reiner
    Erfassungsbogen (TAIFUN-Schiene); mit „Aktionen KL“ sind die übrigen
    KL-Blätter Pflicht (wie „Angebotsaufbau PV“/„PV-Parameter“ bei PV)."""
    if "Aktionen KL" not in wb.sheetnames:
        return
    fehlend = [blatt for blatt in KL_PFLICHT_BLAETTER if blatt not in wb.sheetnames]
    if fehlend:
        for blatt in fehlend:
            bericht.fehler.append(f"Blatt „{blatt}“ fehlt (Pflicht zu „Aktionen KL“).")
        return
    _kl_aktionen_einlesen(wb, logik, bericht)
    _kl_aufbau_einlesen(wb, logik, bericht)
    _kl_parameter_einlesen(wb, logik)
    _kl_paketmatrix_einlesen(wb, logik, bericht)
    _kl_kombinationen_einlesen(wb, logik, bericht)
    _kl_montagematrix_einlesen(wb, logik, bericht)
    _kl_artikel_einlesen(wb, logik, bericht)
    _kl_pruefen(logik, bericht)


def _kl_aktionen_einlesen(wb, logik: Logik, bericht: Pruefbericht) -> None:
    """Blatt „Aktionen KL“ (Frage · Antwort · Aktion · Bemerkung · Zusatzbedingung).
    Schreibweisen (PLAN_V16 Phase 113): „Artikel: KL017 × 5“ · „Artikel: KL013 ×
    Innengeräte als EP“ · „Artikel: KL004 ×1 · KL005 ×1 · KL006 ×1 je Außengerät“ ·
    „AMPEL: individuell – Grund: <Text>“ · „Hinweis: <Text>“ (fachlicher Hinweis am
    Vorgang, keine Position, keine Ampel → typ „hinweis“, ampel_grund = Text) · „–“."""
    for row in wb["Aktionen KL"].iter_rows(min_row=2, values_only=True):
        frage, antwort, aktion_roh, bemerkung, zusatz = (
            _zelle(v) for v in (tuple(row) + (None,) * 5)[:5])
        if not frage:
            continue
        m_hinweis = re.match(r"(?:Fachlicher\s+Hinweis|Protokollhinweis|Hinweis)\s*:\s*(.+)$",
                             aktion_roh, re.S)
        if aktion_roh.startswith("AMPEL"):
            m = re.search(r"Grund:\s*(.+)$", aktion_roh)
            typ, grund = "ampel", (m.group(1).strip() if m else aktion_roh)
            refs = refs_extrahieren(aktion_roh)
        elif m_hinweis:
            typ, grund, refs = "hinweis", m_hinweis.group(1).strip(), []
        else:
            typ, grund = "normal", ""
            # „… lt. Blatt „Montagematrix KL““ / „… lt. Blatt „Paketmatrix KL““ sind
            # Dokumentation – die Zuordnung rechnet app/kl_auslegung.py; Nummern im
            # Text wären nur erläuternd (wie „lt. Paketmatrix“ bei WP)
            refs = [] if re.search(r"\blt\.\s", aktion_roh) else refs_extrahieren(aktion_roh)
        zusatz_b = None
        if zusatz:
            zusatz_b = bedingung_parsen(zusatz)
            if zusatz_b is None:
                bericht.fehler.append(
                    f"Aktionen KL {frage}: Zusatzbedingung „{zusatz}“ nicht parsebar.")
        logik.kl_aktionen.append(Aktion(frage, antwort, aktion_roh, typ, grund, refs,
                                        bemerkung, zusatz_b))


def _kl_aufbau_einlesen(wb, logik: Logik, bericht: Pruefbericht) -> None:
    """Blatt „Angebotsaufbau KL“ (Block · Überschrift · Inhalt · Wann) – nur Zeilen
    mit Blocknummer; Erläuterungszeilen (Auslegungszeile, Summenblock, Nachtexte,
    Anhänge, Protokoll) bleiben Dokumentation. Die Reihenfolge der KL-Nummern im
    Inhalt ist die Sortierung im Block (kl_auslegung._index_im_inhalt)."""
    for row in wb["Angebotsaufbau KL"].iter_rows(min_row=2, values_only=True):
        nr, ueberschrift, inhalt, wann = (_zelle(v) for v in (tuple(row) + (None,) * 4)[:4])
        if not nr:
            continue
        try:
            block_nr = int(float(nr))
        except ValueError:
            continue
        bedingung = bedingung_parsen(wann)
        if bedingung is None:
            bericht.fehler.append(
                f"Angebotsaufbau KL Block {block_nr}: Bedingung „{wann}“ nicht parsebar.")
        refs = refs_extrahieren(inhalt)
        if not refs:
            bericht.fehler.append(
                f"Angebotsaufbau KL Block {block_nr}: Inhalt nennt keine KL-Nummer "
                "(jede Position muss ausdrücklich stehen, z. B. „KL020 · KL021 …“).")
        logik.kl_bloecke.append(AngebotsBlock(block_nr, ueberschrift, inhalt, bedingung, refs))


def _kl_parameter_einlesen(wb, logik: Logik) -> None:
    """Blatt „KL-Parameter“ (Parameter · Wert · Einheit · Bemerkung)."""
    for row in wb["KL-Parameter"].iter_rows(min_row=2, values_only=True):
        name, wert, einheit, bemerkung = (_zelle(v) for v in (tuple(row) + (None,) * 4)[:4])
        if name:
            logik.kl_parameter[name] = (wert, bemerkung)
            logik.kl_parameter_einheit[name] = einheit


def _kl_paketmatrix_einlesen(wb, logik: Logik, bericht: Pruefbericht) -> None:
    """Blatt „Paketmatrix KL“ (Serie · Typ · Klasse / Außengerät · Kühllast je Raum ·
    Artikel · Bemerkung). Artikelzelle „KL033 (…) + KL029 (…)“ = zwei Positionen;
    „nicht im Sortiment“ → Ampel mit dem Grund aus der Bemerkung nach „→ AMPEL: “."""
    for zeile, row in enumerate(wb["Paketmatrix KL"].iter_rows(min_row=2, values_only=True), 2):
        serie, typ_roh, klasse, kuehllast, artikel_roh, bemerkung = (
            _zelle(v) for v in (tuple(row) + (None,) * 6)[:6])
        if not serie:
            continue
        typ = KL_PAKET_TYPEN.get(typ_roh.lower())
        if typ is None:
            bericht.fehler.append(
                f"Paketmatrix KL Zeile {zeile} ({serie}): unbekannter Typ „{typ_roh}“ "
                "(erwartet Single, Multi-Innengerät, Multi-Außengerät oder Multi).")
            typ = typ_roh.lower()
        artikel = re.findall(r"\bKL\d{3}\b", artikel_roh)
        nicht = "nicht im sortiment" in artikel_roh.lower()
        m = re.search(r"AMPEL:\s*(.+)$", bemerkung)
        grund = m.group(1).strip() if m else ""
        if not artikel and not nicht:
            bericht.fehler.append(
                f"Paketmatrix KL {serie} / {typ_roh} / {klasse}: Spalte „Artikel“ ohne "
                "KL-Referenz (oder „nicht im Sortiment“).")
        elif nicht and not grund:
            bericht.warnungen.append(
                f"Paketmatrix KL {serie} / {typ_roh} / {klasse}: „nicht im Sortiment“ ohne "
                "„→ AMPEL: <Grund>“ in der Bemerkung – es gilt der Standardgrund G2/G3.")
        logik.kl_paket.append(KlPaketZeile(serie, typ, klasse, kuehllast, artikel, bemerkung,
                                           nicht, typ_roh, artikel_roh, grund))


def _kl_kombinationen_einlesen(wb, logik: Logik, bericht: Pruefbericht) -> None:
    """Blatt „Kombinationen KL“ (Außengerät · Artikel · Anzahl Innengeräte ·
    Kombination · Quelle). Codes werden aufsteigend numerisch normalisiert
    („12+9“ → „9+12“); nur die Codes 7/9/12/18/24 sind zulässig."""
    for zeile, row in enumerate(wb["Kombinationen KL"].iter_rows(min_row=2, values_only=True), 2):
        name, artikel, anzahl_roh, kombi_roh = (
            _zelle(v) for v in (tuple(row) + (None,) * 4)[:4])
        if not name:
            continue
        codes = [c for c in re.split(r"\s*\+\s*", kombi_roh.strip()) if c]
        ungueltig = [c for c in codes if c not in KL_CODES]
        if not codes or ungueltig:
            bericht.fehler.append(
                f"Kombinationen KL Zeile {zeile} ({name}): Kombination „{kombi_roh}“ enthält "
                f"unzulässige Codes ({', '.join(ungueltig) if ungueltig else 'leer'}) – "
                f"erlaubt sind nur {'/'.join(KL_CODES)}.")
            continue
        anzahl = _kl_ganzzahl(anzahl_roh)
        if anzahl is None:
            bericht.fehler.append(
                f"Kombinationen KL Zeile {zeile} ({name}): „Anzahl Innengeräte“ "
                f"„{anzahl_roh}“ ist keine ganze Zahl.")
            continue
        if anzahl != len(codes):
            bericht.fehler.append(
                f"Kombinationen KL Zeile {zeile} ({name}): Anzahl Innengeräte {anzahl} passt "
                f"nicht zur Kombination „{kombi_roh}“ ({len(codes)} Codes).")
            continue
        schluessel = "+".join(sorted(codes, key=int))
        logik.kl_kombis.setdefault(name, {}).setdefault(anzahl, set()).add(schluessel)
        if artikel:
            if re.fullmatch(r"KL\d{3}", artikel) is None:
                bericht.fehler.append(
                    f"Kombinationen KL Zeile {zeile} ({name}): Artikel „{artikel}“ ist "
                    "keine KL-Nummer.")
            elif logik.kl_kombi_artikel.get(name, artikel) != artikel:
                bericht.fehler.append(
                    f"Kombinationen KL {name}: unterschiedliche Artikel "
                    f"({logik.kl_kombi_artikel[name]} und {artikel}, Zeile {zeile}).")
            else:
                logik.kl_kombi_artikel[name] = artikel


def _kl_montagematrix_einlesen(wb, logik: Logik, bericht: Pruefbericht) -> None:
    """Blatt „Montagematrix KL“ (Innengeräte gesamt · Außengeräte (KO04) · Position ·
    VK netto · Bemerkung) – nur Zahlenzeilen; die Sammelzeile „alle anderen … AMPEL“
    liefert den dokumentierten Ampel-Text (G6 rechnet app/kl_auslegung.py)."""
    for zeile, row in enumerate(wb["Montagematrix KL"].iter_rows(min_row=2, values_only=True), 2):
        innen, aussen, position, vk, bemerkung = (
            _zelle(v) for v in (tuple(row) + (None,) * 5)[:5])
        if not innen and not position:
            continue
        logik.kl_montage_zeilen.append({"innen": innen, "aussen": aussen, "position": position,
                                        "vk": vk, "bemerkung": bemerkung})
        n_innen, n_aussen = _kl_ganzzahl(innen), _kl_ganzzahl(aussen)
        if n_innen is None or n_aussen is None:
            if position.upper().startswith("AMPEL") or innen.lower().startswith("alle"):
                logik.kl_montage_ampel = bemerkung
            else:
                bericht.warnungen.append(
                    f"Montagematrix KL Zeile {zeile}: „{innen} / {aussen}“ ist keine "
                    "Zahlenzeile – ignoriert.")
            continue
        if re.fullmatch(r"KL\d{3}", position) is None:
            bericht.fehler.append(
                f"Montagematrix KL {n_innen}/{n_aussen}: Position „{position}“ ist keine KL-Nummer.")
            continue
        schluessel = (n_innen, n_aussen)
        if schluessel in logik.kl_montage:
            bericht.fehler.append(
                f"Montagematrix KL: Kombination {n_innen} Innengeräte / {n_aussen} Außengeräte "
                f"doppelt (Zeile {zeile}: {position}, zuvor {logik.kl_montage[schluessel]}).")
            continue
        logik.kl_montage[schluessel] = position


def _kl_artikel_einlesen(wb, logik: Logik, bericht: Pruefbericht) -> None:
    """Blatt „KL-Artikel“ (KL-Nr. · Datei · Pos. in Datei · GUID · Bezeichnung (1. Zeile)
    · VK netto (€) · EK (€) · EP): GUID → KL-Nr. (Pinning für app/import_klima.py)
    und die Liste aller KL-Nummern (Referenzprüfung; KL050 steht ohne GUID)."""
    zeilen = wb["KL-Artikel"].iter_rows(values_only=True)
    kopf = [_zelle(z) for z in next(zeilen, [])]
    if "KL-Nr." not in kopf or "GUID" not in kopf:
        bericht.fehler.append("KL-Artikel: Kopfzeile ohne die Spalten „KL-Nr.“ und „GUID“.")
        return
    spalten = {name: kopf.index(name) for name in kopf if name}

    def wert(row, name) -> str:
        i = spalten.get(name)
        return _zelle(row[i]) if i is not None and i < len(row) else ""

    for zeile, row in enumerate(zeilen, 2):
        row = tuple(row)
        nr, guid = wert(row, "KL-Nr."), wert(row, "GUID")
        if not nr:
            continue
        if re.fullmatch(r"KL\d{3}", nr) is None:
            bericht.fehler.append(f"KL-Artikel Zeile {zeile}: „{nr}“ ist keine KL-Nummer.")
            continue
        if nr in logik.kl_artikel_nummern:
            bericht.fehler.append(f"KL-Artikel: Nummer {nr} doppelt (Zeile {zeile}).")
            continue
        logik.kl_artikel_nummern.append(nr)
        if guid.startswith("{"):
            if guid in logik.kl_artikel:
                bericht.fehler.append(
                    f"KL-Artikel: GUID {guid} doppelt ({logik.kl_artikel[guid]} und {nr}).")
            else:
                logik.kl_artikel[guid] = nr
        logik.kl_artikel_zeilen.append({
            "nr": nr, "datei": wert(row, "Datei"), "pos": wert(row, "Pos. in Datei"),
            "guid": guid, "bezeichnung": wert(row, "Bezeichnung (1. Zeile)"),
            "vk": wert(row, "VK netto (€)"), "ek": wert(row, "EK (€)"), "ep": wert(row, "EP")})


def kl_referenzen(logik: Logik) -> dict[str, list[str]]:
    """Alle KL-Referenzen der Klima-Blätter mit Fundstellen (Validierung gegen das
    Blatt „KL-Artikel“ und den Artikelstamm)."""
    fundstellen: dict[str, list[str]] = {}

    def merken(ref: str, quelle: str):
        fundstellen.setdefault(ref, []).append(quelle)

    for aktion in logik.kl_aktionen:
        for ref in aktion.artikel:
            merken(ref.ref, f"Aktionen KL {aktion.frage} („{aktion.antwort}“)")
    for block in logik.kl_bloecke:
        for ref in block.refs:
            merken(ref.ref, f"Angebotsaufbau KL Block {block.nr}")
    for zeile in logik.kl_paket:
        for ref in zeile.artikel:
            merken(ref, f"Paketmatrix KL {zeile.serie} / {zeile.typ_roh} / {zeile.klasse}")
    for (innen, aussen), ref in logik.kl_montage.items():
        merken(ref, f"Montagematrix KL {innen}/{aussen}")
    for name, ref in logik.kl_kombi_artikel.items():
        merken(ref, f"Kombinationen KL {name}")
    meter = str(logik.kl_parameter.get("Meterposition Zusatzleitung", ("", ""))[0]).strip()
    if re.fullmatch(r"KL\d{3}", meter):
        merken(meter, "KL-Parameter „Meterposition Zusatzleitung“")
    return fundstellen


def _kl_pruefen(logik: Logik, bericht: Pruefbericht) -> None:
    """Validierung des Klimakonfigurators (Parametrierung → „Logik prüfen“):
    Pflichtparameter (fehlend = Hinweis mit Standardwert, unlesbar = Fehler),
    Aktionen gegen den Bogen „Fragen KL“ (Frage/Antwort/Zusatzbedingung), jede
    KL-Referenz in Aktionen, Angebotsaufbau, Paketmatrix, Montagematrix und
    Kombinationen existiert im Blatt „KL-Artikel“, Kombinationen nur Codes
    7/9/12/18/24 (beim Einlesen), Montagematrix ohne Doppelzeilen (beim Einlesen),
    Hinweis von KR07 enthält „Optionen wie … (KO04)“ (steuert _wiederhol_klone)."""
    fragen = logik.sparten_fragen.get("KL", {})
    nummern = set(logik.kl_artikel_nummern)

    # Bogen: Fragen, die der Rechenkern braucht
    for fid in KL_PFLICHT_FRAGEN:
        if fid not in fragen:
            bericht.fehler.append(
                f"Fragen KL: Frage {fid} fehlt – der Klimakonfigurator (app/kl_auslegung.py) "
                "braucht sie.")
    kr07 = fragen.get("KR07")
    if kr07 is not None and not re.search(r"Optionen wie .*\(KO04\)", kr07.hinweis or ""):
        bericht.fehler.append(
            "Fragen KL KR07: Hinweis muss „es erscheinen nur so viele Optionen wie "
            "Außengeräte (KO04)“ enthalten – er begrenzt die Auswahl je Raum auf KO04.")

    # Parameter
    for name in PFLICHT_KL_PARAMETER:
        wert = str(logik.kl_parameter.get(name, ("", ""))[0]).strip()
        if not wert:
            bericht.warnungen.append(
                f"KL-Parameter „{name}“ fehlt – Standardwert {kl_standardwert_text(name)} "
                "wird verwendet (Klima v24).")
            continue
        if name in KL_ZAHL_PARAMETER and _kl_zahl(wert) is None:
            bericht.fehler.append(f"KL-Parameter „{name}“: „{wert}“ ist keine Zahl.")
    grenzen = [(_kl_zahl(logik.kl_parameter[n][0]) or 0.0) for n in
               ("Klasse 9 bis", "Klasse 12 bis", "Klasse 18 bis", "Klasse 24 bis")
               if n in logik.kl_parameter and _kl_zahl(logik.kl_parameter[n][0]) is not None]
    if grenzen != sorted(grenzen):
        bericht.fehler.append(
            "KL-Parameter: die Klassengrenzen „Klasse 9 bis“ … „Klasse 24 bis“ müssen "
            "aufsteigend sein.")
    serie = str(logik.kl_parameter.get("Standardserie", ("", ""))[0]).strip()
    if serie and "KO06" in fragen and _alias_aufloesen(serie, fragen["KO06"].antworten) is None:
        bericht.fehler.append(
            f"KL-Parameter „Standardserie“: „{serie}“ ist keine Option von KO06 "
            f"({' | '.join(fragen['KO06'].antworten)}).")
    gewerbe = str(logik.kl_parameter.get("Gewerbe-Verhalten", ("", ""))[0]).strip()
    if gewerbe and gewerbe not in ("Hinweis", "AMPEL"):
        bericht.fehler.append(
            f"KL-Parameter „Gewerbe-Verhalten“: „{gewerbe}“ – erlaubt sind „Hinweis“ oder „AMPEL“.")

    # Aktionen: Frage bekannt, Antwort plausibel, Zusatzbedingung auflösbar
    for aktion in logik.kl_aktionen:
        b = aktion.zusatz_bedingung
        if b is not None:
            terme = ([(b.frage_id, b.werte)] if b.art == "antwort"
                     else [t for k in b.klauseln for t in k])
            for fid, werte in terme:
                if fid not in fragen:
                    bericht.fehler.append(
                        f"Aktionen KL {aktion.frage}: Zusatzbedingung verweist auf "
                        f"unbekannte Frage {fid}.")
                    continue
                if fragen[fid].typ != "Auswahl":
                    continue
                for wert in werte:
                    if _alias_aufloesen(wert, fragen[fid].antworten) is None:
                        bericht.fehler.append(
                            f"Aktionen KL {aktion.frage}: Zusatzbedingungswert „{wert}“ ist "
                            f"keine Option von {fid}.")
        if aktion.frage in KL_SPEZIAL:
            continue
        if aktion.frage not in fragen:
            bericht.fehler.append(
                f"Aktionen KL: unbekannte Frage „{aktion.frage}“ (Antwort „{aktion.antwort}“).")
            continue
        problem = _antwort_pruefen(fragen[aktion.frage], aktion.antwort, fragen)
        if problem:
            bericht.fehler.append(f"Aktionen KL {aktion.frage}: {problem}")
    # Doppler-Schutz (wie PV): Grundpaket-Artikel nicht zusätzlich über eine Fragezeile
    immer_refs = {r.ref: a.frage for a in logik.kl_aktionen
                  if a.frage == "Grundpaket" for r in a.artikel}
    for aktion in logik.kl_aktionen:
        if aktion.typ != "normal" or aktion.frage in KL_SPEZIAL:
            continue
        for ref in aktion.artikel:
            if ref.ref in immer_refs:
                bericht.warnungen.append(
                    f"Doppelte Artikelquelle KL: {ref.ref} kommt über „{immer_refs[ref.ref]}“ "
                    f"UND über die Aktionszeile {aktion.frage} („{aktion.antwort}“) – "
                    "der Artikel würde doppelt im Angebot landen.")
    # Abdeckung: Auswahl-Fragen mit Positions-/Ampel-Zeilen brauchen je Option eine
    # Zeile; Fragen, die nur Hinweis-/Dokumentationszeilen haben (KO01, KO03, KO06,
    # KR03, KR04, KA02), bleiben ohne Vollabdeckung (Entwurf nennt nur die Fälle
    # mit Wirkung)
    for frage in fragen.values():
        zeilen = [a for a in logik.kl_aktionen if a.frage == frage.id]
        if frage.typ != "Auswahl" or not zeilen:
            continue
        if not any(a.typ == "ampel" or (a.typ == "normal" and a.artikel) for a in zeilen):
            continue
        abgedeckt = {o for a in zeilen for t in [a.antwort] + antwort_teile(a.antwort)
                     if (o := _alias_aufloesen(t, frage.antworten))}
        fehlend = [o for o in frage.antworten if o not in abgedeckt]
        if fehlend:
            bericht.warnungen.append(
                f"Aktionen KL {frage.id}: keine Aktionszeile für Option(en) {', '.join(fehlend)}.")

    # Referenzen: jede KL-Nummer der Klima-Blätter steht im Blatt „KL-Artikel“
    for ref, quellen in sorted(kl_referenzen(logik).items()):
        if ref not in nummern:
            bericht.fehler.append(
                f"KL-Referenz {ref} fehlt im Blatt „KL-Artikel“ – referenziert in: "
                f"{'; '.join(sorted(set(quellen)))}.")
    # Paketmatrix: Multi-Außengeräte brauchen Kombinationszeilen, sonst nie ein Treffer
    for zeile in logik.kl_paket:
        if zeile.typ != "multi_aussen" or zeile.nicht_im_sortiment:
            continue
        for ref in zeile.artikel:
            if ref not in logik.kl_kombi_artikel.values():
                bericht.warnungen.append(
                    f"Paketmatrix KL {zeile.serie} / {zeile.klasse}: Außengerät {ref} hat keine "
                    "Zeile im Blatt „Kombinationen KL“ – Multi-Split mit diesem Gerät wird "
                    "immer zur Ampel (G4).")
    if not logik.kl_montage:
        bericht.fehler.append("Montagematrix KL: keine Zahlenzeile (Innengeräte / Außengeräte → "
                              "KL-Nummer) – jede Montage würde zur Ampel.")
    if not logik.kl_paket:
        bericht.fehler.append("Paketmatrix KL: keine Zeile – kein Gerät kann zugeordnet werden.")
    if not logik.kl_bloecke:
        bericht.fehler.append("Angebotsaufbau KL: kein Block mit Nummer.")


def _anhaenge_einlesen(wb, bericht: Pruefbericht) -> list[Anhang]:
    """Blatt "Anhänge": Datei · Regel · Bemerkung.
    Regeln: 'immer' | 'wenn <Frage> = <Antwort>' | 'wenn Pos. <Nr> im Angebot'."""
    if "Anhänge" not in wb.sheetnames:
        bericht.warnungen.append("Blatt „Anhänge“ fehlt – es werden keine Anhänge geregelt.")
        return []
    anhaenge = []
    for zeile in wb["Anhänge"].iter_rows(min_row=2, values_only=True):
        datei, regel, bemerkung, nicht_bei = (tuple(zeile) + (None,) * 4)[:4]
        datei = _zelle(datei)
        regel = _zelle(regel)
        if not datei or datei.startswith("("):
            continue  # Platzhalterzeile
        eintrag = Anhang(datei, regel, "unbekannt", bemerkung=_zelle(bemerkung),
                         nicht_bei_profil=[p.strip() for p in
                                           _zelle(nicht_bei).split(",") if p.strip()])
        if regel == "immer":
            eintrag.art = "immer"
        elif (m := re.match(r"wenn\s+Sparte\s*=\s*(\w+)$", regel)):
            eintrag.art = "sparte"          # v13-PV: Anhang je Sparte (z. B. PV)
            eintrag.antwort = m.group(1)
        elif (m := re.match(r"wenn\s+([A-Z]\d{2})\s*=\s*(.+)$", regel)):
            eintrag.art = "frage"
            eintrag.frage_id = m.group(1)
            eintrag.antwort = m.group(2).strip()
        elif (m := re.match(r"wenn\s+(?:WP-Paket\s+)?Pos\.\s*([\d–\-\s]+)\s+im Angebot", regel)):
            eintrag.art = "position"
            teil = m.group(1).strip()
            m_bereich = re.match(r"(\d{1,3})\s*[–-]\s*(\d{1,3})$", teil)
            if m_bereich:
                eintrag.positionen = [f"{n:03d}" for n in
                                      range(int(m_bereich.group(1)), int(m_bereich.group(2)) + 1)]
            else:
                eintrag.positionen = [n.zfill(3) for n in re.findall(r"\d{1,3}", teil)]
        else:
            bericht.warnungen.append(f"Anhänge: Regel „{regel}“ für {datei} nicht lesbar.")
        anhaenge.append(eintrag)
    return anhaenge


def _bafa_einlesen(wb, bericht: Pruefbericht) -> list[BafaAnlage]:
    """v19: Blatt "BAFA-Anlagen" (Schlüssel · Nummer · Hersteller ·
    Gerätebezeichnung · kW · Kältemittel · Netzdienlichkeit · E/E-Anzeige ·
    Hinweis). Fehlt das Blatt, gibt es eine Warnung – das BzA-Datenblatt
    markiert Gerät/Nummer dann als „fehlt“."""
    if "BAFA-Anlagen" not in wb.sheetnames:
        bericht.warnungen.append("Blatt „BAFA-Anlagen“ fehlt – BzA-Datenblatt ohne "
                                 "Anlagennummern.")
        return []
    anlagen: list[BafaAnlage] = []
    gesehen: set[str] = set()
    for row in wb["BAFA-Anlagen"].iter_rows(min_row=2, values_only=True):
        werte = [_zelle(v) for v in (tuple(row) + (None,) * 9)[:9]]
        schluessel, nummer = werte[0], werte[1]
        if not schluessel:
            continue
        if schluessel in gesehen:
            bericht.warnungen.append(f"BAFA-Anlagen: Schlüssel {schluessel} doppelt.")
            continue
        gesehen.add(schluessel)
        if not nummer.isdigit():
            bericht.warnungen.append(f"BAFA-Anlagen: Nummer für {schluessel} fehlt/ungültig.")
        try:
            kw = float(str(row[4]).replace(",", ".")) if row[4] not in (None, "") else None
        except (TypeError, ValueError):
            kw = None
        anlagen.append(BafaAnlage(schluessel, nummer, werte[2], werte[3], kw,
                                  werte[5], werte[6], werte[7], werte[8]))
    return anlagen


def bafa_fuer_positionen(logik: Logik, positionen: set[str]) -> Optional[BafaAnlage]:
    """Gerät zum Angebot: Paket-Position 045–054 direkt; Klasse 15 (030/031)
    über die Inneneinheit 055/056. Alternativ-/EP-Positionen zählen nicht
    (Aufrufer übergibt nur voll berechnete Positionen)."""
    nach = {a.schluessel: a for a in logik.bafa_anlagen}
    for nr in sorted(positionen):
        if nr in nach and not nr.startswith(("15+", "vorrat")):
            return nach[nr]
    if positionen & {"030", "031"}:
        for innen in ("055", "056"):
            if innen in positionen and f"15+{innen}" in nach:
                return nach[f"15+{innen}"]
    return None


def _vermerke_einlesen(wb, bericht: Pruefbericht) -> list["Vermerk"]:
    """v9: Blatt "Vermerke" (Text · Bedingung · Platzierung); fehlt das Blatt,
    gibt es schlicht keine Vermerke."""
    if "Vermerke" not in wb.sheetnames:
        return []
    vermerke = []
    for text, bedingung_roh, platzierung in wb["Vermerke"].iter_rows(min_row=2,
                                                                     values_only=True):
        text = _zelle(text)
        if not text:
            continue
        bedingung = bedingung_parsen(bedingung_roh)
        if bedingung is None:
            bericht.fehler.append(
                f"Vermerke: Bedingung nicht parsebar: {bedingung_roh!r}")
        vermerke.append(Vermerk(text, bedingung,
                                _zelle(platzierung) or "Ende Positionsteil"))
    return vermerke


def _fragen_einlesen(wb, bericht: Pruefbericht, blatt: str = "Fragen") -> dict[str, Frage]:
    """v2-Layout: Seite · ID · Fragetext · Typ · Antworten · Anzeigen wenn · Hinweis.
    Die Reihenfolge ergibt sich aus der Zeilenfolge im Blatt. Seit v8 auch für
    die Sparten-Blätter „Fragen PV“ / „Fragen KL“."""
    fragen: dict[str, Frage] = {}
    for zeile, row in enumerate(wb[blatt].iter_rows(min_row=2, values_only=True), 2):
        seite, fid, text, typ, antworten, anzeigen, hinweis = (_zelle(v) for v in row[:7])
        if not fid:
            continue
        if fid in fragen:
            bericht.fehler.append(f"{blatt} Zeile {zeile}: ID {fid} doppelt vergeben.")
            continue
        typ = TYP_ALIASE.get(typ, typ)
        if typ not in FRAGE_TYPEN:
            bericht.fehler.append(f"{blatt} {fid}: unbekannter Typ „{typ}“.")
        if not seite:
            bericht.fehler.append(f"{blatt} {fid}: Spalte „Seite“ ist leer.")
        optionen = [a.strip() for a in antworten.split("|") if a.strip()] if antworten else []
        if typ == "Auswahl" and not optionen:
            bericht.fehler.append(f"{blatt} {fid}: Auswahl ohne Antwortmöglichkeiten.")
        bedingung = bedingung_parsen(anzeigen)
        if bedingung is None:
            bericht.fehler.append(
                f"{blatt} {fid}: Bedingung „{anzeigen}“ nicht parsebar.")
        fragen[fid] = Frage(fid, len(fragen) + 1, text, typ, optionen, bedingung,
                            hinweis, seite)
    return fragen


def _aktionen_einlesen(wb, bericht: Pruefbericht) -> list[Aktion]:
    aktionen = []
    for row in wb["Aktionen"].iter_rows(min_row=2, values_only=True):
        frage, antwort, aktion_roh, bemerkung = (_zelle(v) for v in row[:4])
        if not frage:
            continue
        if aktion_roh.startswith("AMPEL"):
            # "AMPEL: individuell – Grund: <Text>" → Flag statt Abbruch
            typ = "ampel"
            m = re.search(r"Grund:\s*(.+)$", aktion_roh)
            grund = m.group(1).strip() if m else aktion_roh
        else:
            typ = "normal"
            grund = ""
        # Verweist die Zeile auf die Paketmatrix („… lt. Paketmatrix …“), ist
        # die Matrix die EINZIGE Artikelquelle – Positionsnummern im Text sind
        # nur erläuternd (Bugfix: Pos. 065 kam sonst doppelt ins Angebot).
        refs = ([] if "lt. Paketmatrix" in aktion_roh
                else refs_extrahieren(aktion_roh))
        aktionen.append(Aktion(frage, antwort, aktion_roh, typ, grund,
                               refs, bemerkung))
    return aktionen


def _paketmatrix_einlesen(wb, bericht: Pruefbericht) -> list[PaketZeile]:
    pakete = []
    for row in wb["Paketmatrix"].iter_rows(min_row=2, values_only=True):
        klasse, verbrauch, ww200, ohne_ww, ww300 = (_zelle(v) for v in row[:5])
        heizlast = _zelle(row[5]) if len(row) > 5 else ""
        if not klasse:
            continue
        von = bis = None
        m = re.match(r"([\d.]+)\s*[–-]\s*([\d.]+)\s*kWh", verbrauch)
        if m:
            von = int(m.group(1).replace(".", ""))
            bis = int(m.group(2).replace(".", ""))
        else:
            bericht.fehler.append(
                f"Paketmatrix {klasse}: Verbrauchsbereich „{verbrauch}“ nicht parsebar.")
        # v8: Heizlast-Spalte „bis 5,9 kW“ / „6,0 – 7,9 kW“ (Dezimal mit Komma)
        h_von = h_bis = None
        if heizlast:
            def _dez(t):
                return float(t.replace(".", "").replace(",", "."))
            if (m := re.match(r"([\d.,]+)\s*[–-]\s*([\d.,]+)", heizlast)):
                h_von, h_bis = _dez(m.group(1)), _dez(m.group(2))
            elif (m := re.match(r"bis\s*([\d.,]+)", heizlast)):
                h_von, h_bis = 0.0, _dez(m.group(1))
            else:
                bericht.fehler.append(
                    f"Paketmatrix {klasse}: Heizlast „{heizlast}“ nicht parsebar.")
        zeile = PaketZeile(klasse, verbrauch, von, bis,
                           refs_extrahieren(ww200), refs_extrahieren(ohne_ww),
                           refs_extrahieren(ww300), heizlast, h_von, h_bis)
        for spalte, refs, roh in (("WW bis 200 l", zeile.ww_bis_200, ww200),
                                  ("ohne Warmwasser", zeile.ohne_ww, ohne_ww),
                                  ("WW 300 l", zeile.ww_300, ww300)):
            # v9: „lt. …“-Zellen (Serie CS8800i: Artikel kommen aus den
            # Puffer-/Farbfragen) brauchen keine eigene Referenz
            if not refs and "lt. " not in roh:
                bericht.fehler.append(
                    f"Paketmatrix {klasse}: Spalte „{spalte}“ ohne Artikel-Referenz.")
        pakete.append(zeile)
    return pakete


def _angebotsaufbau_einlesen(wb, bericht: Pruefbericht) -> list[AngebotsBlock]:
    bloecke = []
    for row in wb["Angebotsaufbau"].iter_rows(min_row=2, values_only=True):
        nr, ueberschrift, inhalt, wann = (_zelle(v) for v in row[:4])
        if not nr:
            continue
        if nr == "Nachtexte":
            continue  # Vollmacht-Bedingung (Nachtext D) – wird in pdf_export ausgewertet
        try:
            block_nr = int(float(nr))
        except ValueError:
            bericht.fehler.append(f"Angebotsaufbau: Blocknummer „{nr}“ keine Zahl.")
            continue
        bedingung = bedingung_parsen(wann)
        if bedingung is None:
            bericht.fehler.append(
                f"Angebotsaufbau Block {block_nr}: Bedingung „{wann}“ nicht parsebar.")
        refs = refs_extrahieren(inhalt)
        # v2-Schreibweise: nach "Pos. 005 · 006 · 007 (EP)" stehen weitere Nummern
        # ohne "Pos."-Präfix – nackte dreistellige Token ergänzen
        vorhanden = {r.ref for r in refs}
        for m in re.finditer(r"\b(\d{3})\b", inhalt):
            if m.group(1) not in vorhanden:
                refs.append(ArtikelRef(m.group(1), "1", False))
                vorhanden.add(m.group(1))
        bloecke.append(AngebotsBlock(block_nr, ueberschrift, inhalt, bedingung, refs))
    return bloecke


PFLICHT_KFW_PARAMETER = [
    "Gültigkeit der Konditionen", "Grundförderung", "Klimageschwindigkeits-Bonus",
    "Einkommensbonus", "Fördersatz-Deckel",
    "Höchstkosten EFH", "Höchstkosten MFH", "Höchstkosten Gewerbe",
    "ABLEITUNG Gebäudetyp", "ABLEITUNG Klima-Vorbelegung (K02)",
]


def _kfw_einlesen(wb, bericht: Pruefbericht) -> dict[str, tuple[str, str]]:
    kfw = {}
    for row in wb["KfW"].iter_rows(min_row=2, values_only=True):
        parameter, wert, bemerkung = (_zelle(v) for v in row[:3])
        if parameter:
            kfw[parameter] = (wert, bemerkung)
    for pflicht in PFLICHT_KFW_PARAMETER:
        if pflicht not in kfw:
            bericht.fehler.append(f"KfW: Parameter „{pflicht}“ fehlt.")
    gueltigkeit = kfw.get("Gültigkeit der Konditionen", ("", ""))[0]
    if gueltigkeit and not re.search(r"\d{2}\.\d{2}\.\d{4}\s*bis\s*\d{2}\.\d{2}\.\d{4}",
                                     gueltigkeit):
        bericht.warnungen.append(
            f"KfW: Gültigkeit „{gueltigkeit}“ nicht als Zeitraum (TT.MM.JJJJ bis TT.MM.JJJJ) lesbar.")
    return kfw


# --- Querbezüge validieren ------------------------------------------------

def antwort_teile(text: str) -> list[str]:
    """Zerlegt Slash-/oder-Listen aus Aktionszeilen. Slash nur mit Leerzeichen
    ringsum trennen, damit Optionswerte wie 'Luft/Wasser' erhalten bleiben."""
    return [t.strip() for t in re.split(r"\s+oder\s+|\s+/\s+", text) if t.strip()]


def _antwort_pruefen(frage: Frage, antwort: str, fragen: dict[str, Frage]) -> Optional[str]:
    """Prüft, ob eine Antwort/Bedingung aus dem Blatt Aktionen zur Frage passt.
    Liefert einen Fehlertext oder None."""
    if frage.typ == "Mengenmaske":
        # z. B. "Anzahl S / M / L / XL": erster Teil trägt das "Anzahl"-Präfix
        teile = antwort_teile(antwort)
        groessen = [re.sub(r"^Anzahl\s+", "", t) for t in teile]
        if groessen and all(g in frage.antworten for g in groessen):
            return None
        return f"„{antwort}“ passt nicht zur Mengenmaske ({' | '.join(frage.antworten)})."
    if frage.typ in ZAHLEN_TYPEN or frage.typ in FREITEXT_TYPEN:
        return None  # freie Beschreibungen/Bereiche erlaubt

    # Auswahl: "A", "A oder B", "A / B / C", "Bedingungsfrage-Wert, eigener Wert"
    teile = antwort_teile(antwort)
    if all(_alias_aufloesen(t, frage.antworten) for t in teile):
        return None
    if "," in antwort:
        vorne, hinten = (t.strip() for t in antwort.split(",", 1))
        eltern_optionen = []
        if frage.bedingung and frage.bedingung.frage_id in fragen:
            eltern_optionen = fragen[frage.bedingung.frage_id].antworten
        if (_alias_aufloesen(hinten, frage.antworten)
                and _alias_aufloesen(vorne, eltern_optionen)):
            return None
    return f"Antwort „{antwort}“ ist keine bekannte Option ({' | '.join(frage.antworten)})."


def _bedingungen_pruefen(fragen: dict[str, Frage], bericht: Pruefbericht,
                         kontext: str = "Fragen") -> None:
    """Bedingungen eines Fragen-Satzes: referenzierte Fragen + Werte müssen
    existieren (v8: auch für die Sparten-Blätter, inkl. Wiederholgruppen)."""
    for frage in fragen.values():
        b = frage.bedingung
        if b is None:
            continue
        terme: list[tuple[str, list[str]]] = []
        if b.art in ("antwort",):
            terme = [(b.frage_id, b.werte)]
        elif b.art in ("ausgefuellt", "wiederholgruppe"):
            terme = [(b.frage_id, [])]
        elif b.art == "klauseln":
            terme = [t for klausel in b.klauseln for t in klausel]
        for frage_id, werte in terme:
            if frage_id not in fragen:
                bericht.fehler.append(
                    f"{kontext} {frage.id}: Bedingung verweist auf unbekannte Frage {frage_id}.")
                continue
            ziel = fragen[frage_id]
            if ziel.typ != "Auswahl":
                continue
            for wert in werte:
                if _alias_aufloesen(wert, ziel.antworten) is None:
                    bericht.fehler.append(
                        f"{kontext} {frage.id}: Bedingungswert „{wert}“ ist keine Option von {ziel.id}.")


def _doppelquellen_pruefen(logik: Logik, bericht: Pruefbericht) -> None:
    """Bugfix-Wächter: Ein Artikel, der in einer Paketmatrix-Spalte steht,
    darf nicht zusätzlich über eine normale Aktionszeile hinzukommen – sonst
    landet er doppelt im Angebot (so kam Pos. 065 bei WW 300 l zweimal).
    Geprüft werden ALLE Matrix-Spalten gegen alle Aktionszeilen mit Artikeln."""
    matrix_refs: dict[str, list[str]] = {}
    for paket in logik.pakete:
        for spalte, refs in (("WW bis 200 l", paket.ww_bis_200),
                             ("ohne Warmwasser", paket.ohne_ww),
                             ("WW 300 l", paket.ww_300)):
            for ref in refs:
                matrix_refs.setdefault(ref.ref, []).append(
                    f"{paket.leistungsklasse}/{spalte}")
    for aktion in logik.aktionen:
        if aktion.typ != "normal":
            continue
        for ref in aktion.artikel:
            if ref.ref in matrix_refs:
                bericht.warnungen.append(
                    f"Doppelte Artikelquelle: {('Pos. ' + ref.ref) if not ref.ref.startswith('Z') else ref.ref} "
                    f"kommt über die Aktionszeile {aktion.frage} („{aktion.antwort}“) UND "
                    f"über die Paketmatrix ({', '.join(sorted(set(matrix_refs[ref.ref])))}) – "
                    "der Artikel würde doppelt im Angebot landen. Die Paketmatrix ist "
                    "die einzige Quelle; Aktionszeile bitte auf „… lt. Paketmatrix“ umstellen.")
        # v11 (AN-C-261082, Entscheidung 23.09.2026): Der 50-l-Puffer bleibt
        # eine eigene Position (Z15); die Doppel-DARSTELLUNG wird stattdessen
        # über die Textregel gelöst, die die Pufferzeile aus den Pakettexten
        # 045–054 entfernt (Blatt "Textregeln", greift bei jedem Re-Import).


def _querbezuege_pruefen(logik: Logik, bericht: Pruefbericht) -> None:
    fragen = logik.fragen
    _bedingungen_pruefen(fragen, bericht)
    _doppelquellen_pruefen(logik, bericht)

    # Anhänge: referenzierte Fragen/Antworten müssen existieren
    for anhang in logik.anhaenge:
        if anhang.art != "frage":
            continue
        if anhang.frage_id not in fragen:
            bericht.fehler.append(
                f"Anhänge {anhang.datei}: unbekannte Frage {anhang.frage_id}.")
        elif (fragen[anhang.frage_id].typ == "Auswahl"
              and _alias_aufloesen(anhang.antwort, fragen[anhang.frage_id].antworten) is None):
            bericht.fehler.append(
                f"Anhänge {anhang.datei}: „{anhang.antwort}“ ist keine Option von {anhang.frage_id}.")

    # Aktionen: Frage bekannt, Antwort plausibel
    for aktion in logik.aktionen:
        if aktion.frage in SPEZIAL_AKTIONEN:
            continue
        if aktion.frage not in fragen:
            bericht.fehler.append(
                f"Aktionen: unbekannte Frage „{aktion.frage}“ (Antwort „{aktion.antwort}“).")
            continue
        problem = _antwort_pruefen(fragen[aktion.frage], aktion.antwort, fragen)
        if problem:
            bericht.fehler.append(f"Aktionen {aktion.frage}: {problem}")

    # Abgedeckte Antworten: jede Auswahl-Option sollte eine Aktionszeile haben.
    # Sammelzeilen wie "O01–O08 / K01–K04" decken ganze ID-Bereiche ab.
    sammelbereich: set[str] = set()
    for aktion in logik.aktionen:
        for praefix, von, bis in re.findall(r"([A-Z])(\d{2})[–-]\1(\d{2})", aktion.frage):
            sammelbereich.update(f"{praefix}{n:02d}"
                                 for n in range(int(von), int(bis) + 1))
    for frage in fragen.values():
        if frage.typ != "Auswahl" or frage.id in sammelbereich:
            continue
        # Kombinationslogik (z. B. A09 „Stahl, bis 5.000 L“ = Antwort der
        # Bedingungsfrage A08 + eigene Antwort): die Zeile deckt die eigene
        # Option nur für diese Eltern-Option ab – geprüft wird die ganze Matrix.
        eltern = (fragen.get(frage.bedingung.frage_id)
                  if frage.bedingung and frage.bedingung.frage_id else None)
        eltern_optionen = (frage.bedingung.werte or eltern.antworten) if eltern else []
        abgedeckt: set[str] = set()                       # Optionen ohne Eltern-Bezug
        kombi: dict[str, set[str]] = {}                   # Eltern-Option -> eigene Optionen
        for aktion in logik.aktionen:
            if aktion.frage != frage.id:
                continue
            kombiniert = False
            if "," in aktion.antwort and eltern is not None:
                vorne, hinten = (x.strip() for x in aktion.antwort.split(",", 1))
                e_opt = _alias_aufloesen(vorne, eltern.antworten)
                o_opt = _alias_aufloesen(hinten, frage.antworten)
                if e_opt and o_opt:
                    kombi.setdefault(e_opt, set()).add(o_opt)
                    kombiniert = True
            if kombiniert:
                continue
            for teil in [aktion.antwort] + antwort_teile(aktion.antwort):
                option = _alias_aufloesen(teil, frage.antworten)
                if option:
                    abgedeckt.add(option)
        if kombi:
            # je Eltern-Option, unter der die Frage gestellt wird, muss jede
            # eigene Option entweder kombiniert oder allgemein abgedeckt sein
            for e_opt in eltern_optionen:
                fehlend = [o for o in frage.antworten
                           if o not in abgedeckt and o not in kombi.get(e_opt, set())]
                if fehlend:
                    bericht.warnungen.append(
                        f"Aktionen {frage.id}: keine Aktionszeile für „{e_opt}, …“ bei "
                        f"Option(en) {', '.join(fehlend)}.")
            continue
        fehlend = [o for o in frage.antworten if o not in abgedeckt]
        if fehlend:
            bericht.warnungen.append(
                f"Aktionen {frage.id}: keine Aktionszeile für Option(en) {', '.join(fehlend)}.")


def artikel_referenzen(logik: Logik) -> dict[str, list[str]]:
    """Alle referenzierten Artikel mit Fundstellen (für die Validierung gegen die DB)."""
    fundstellen: dict[str, list[str]] = {}

    def merken(refs: list[ArtikelRef], quelle: str):
        for ref in refs:
            fundstellen.setdefault(ref.ref, []).append(quelle)

    for aktion in logik.aktionen:
        merken(aktion.artikel, f"Aktionen {aktion.frage} („{aktion.antwort}“)")
        merken(refs_extrahieren(aktion.bemerkung), f"Aktionen {aktion.frage} (Bemerkung)")
    for paket in logik.pakete:
        merken(paket.ww_bis_200, f"Paketmatrix {paket.leistungsklasse}")
        merken(paket.ohne_ww, f"Paketmatrix {paket.leistungsklasse}")
        merken(paket.ww_300, f"Paketmatrix {paket.leistungsklasse}")
    for block in logik.bloecke:
        merken(block.refs, f"Angebotsaufbau Block {block.nr}")
    for aktion in logik.pv_aktionen:   # v13-PV
        merken(aktion.artikel, f"Aktionen PV {aktion.frage} („{aktion.antwort}“)")
    for block in logik.pv_bloecke:
        merken(block.refs, f"Angebotsaufbau PV Block {block.nr}")
    for ref, quellen in kl_referenzen(logik).items():   # v24 Klima
        fundstellen.setdefault(ref, []).extend(quellen)
    return fundstellen


def artikel_pruefen(logik: Logik, session: Session, bericht: Pruefbericht) -> None:
    """Prüft, ob alle referenzierten Positionen/Z-Artikel als aktive Artikel existieren."""
    vorhanden = {pos for (pos,) in session.query(Artikel.pos_nr)
                 .filter(Artikel.aktiv.is_(True)) if pos}
    if not vorhanden:
        bericht.warnungen.append(
            "Artikelstamm ist leer – bitte zuerst die Preisliste importieren "
            "(Artikel → Preisliste importieren).")
        return
    for ref, quellen in sorted(artikel_referenzen(logik).items()):
        if ref not in vorhanden:
            if ref.startswith("PV"):
                hinweis = " – bitte Artikel → PV-Positionslisten importieren"
            elif ref.startswith("KL"):     # v24 Klima
                hinweis = " – bitte Artikel → Klima-Positionslisten importieren"
            else:
                hinweis = ""
            bericht.fehler.append(
                f"Artikel {ref if not ref.isdigit() else 'Pos. ' + ref} "
                f"fehlt im Artikelstamm – referenziert in: {'; '.join(sorted(set(quellen)))}"
                f"{hinweis}.")
    # v13-PV: WR/Speicher-Kombinationen aus den importierten PV-Artikeln
    if logik.pv_aktionen:
        from app import pv_auslegung
        logik.pv_kombis = pv_auslegung.kombis_laden(session)
        if not logik.pv_kombis:
            bericht.warnungen.append(
                "PV: keine Sigenergy-WR/Speicher-Kombinationen im Artikelstamm – "
                "PV-Angebote werden individuell (Artikel → PV-Positionslisten importieren).")


def logik_fuer_sparte(logik: Logik, sparte: str) -> Optional[Logik]:
    """v8: Sicht auf die Logik für eine Sparte. WP = die volle Logik;
    PV/KL = reiner Erfassungsbogen (eigene Fragen, keine Aktionen/Pakete);
    WB oder unbekannt = None (nur Freitext möglich)."""
    if sparte in ("", "WP"):
        return logik
    fragen = logik.sparten_fragen.get(sparte)
    if not fragen:
        return None
    if sparte == "PV" and logik.pv_aktionen:
        # v13-PV: PV ist jetzt ein Konfigurator (Aktionen + Aufbau + Parameter)
        return Logik(fragen, logik.pv_aktionen, [], logik.pv_bloecke, logik.kfw,
                     logik.geladen_am, logik.anhaenge,
                     pv_aktionen=logik.pv_aktionen, pv_bloecke=logik.pv_bloecke,
                     pv_parameter=logik.pv_parameter,
                     pv_parameter_einheit=logik.pv_parameter_einheit, sparte="PV",
                     pv_kombis=logik.pv_kombis)
    if sparte == "KL" and logik.kl_aktionen:
        # v24 (PLAN_V16 Phase 113): KL ist ein Konfigurator, sobald „Aktionen KL“
        # existiert – Aktionen/Blöcke der Klima-Blätter, alle kl_*-Felder, Anhänge
        # („wenn Sparte = KL“) und KfW-Parameter (Gebäudetyp-Ableitung) der Voll-Logik
        return Logik(fragen, logik.kl_aktionen, [], logik.kl_bloecke, logik.kfw,
                     logik.geladen_am, logik.anhaenge, sparte="KL",
                     kl_aktionen=logik.kl_aktionen, kl_bloecke=logik.kl_bloecke,
                     kl_paket=logik.kl_paket, kl_kombis=logik.kl_kombis,
                     kl_kombi_artikel=logik.kl_kombi_artikel, kl_montage=logik.kl_montage,
                     kl_montage_zeilen=logik.kl_montage_zeilen,
                     kl_montage_ampel=logik.kl_montage_ampel,
                     kl_parameter=logik.kl_parameter,
                     kl_parameter_einheit=logik.kl_parameter_einheit,
                     kl_artikel=logik.kl_artikel, kl_artikel_nummern=logik.kl_artikel_nummern,
                     kl_artikel_zeilen=logik.kl_artikel_zeilen)
    return Logik(fragen, [], [], [], logik.kfw, logik.geladen_am, [], sparte=sparte)


# --- Cache / öffentliche API ---------------------------------------------

_cache: dict = {"logik": None, "bericht": None}


def neu_einlesen(session: Session) -> tuple[Logik, Pruefbericht]:
    # v27 (PLAN_V17 Phase 128): „Logik neu einlesen“ erscheint während des Laufs im
    # Betriebs-Status und in /health. Das Einlesen schreibt nichts in die Datenbank
    # (Logik liegt im Speicher-Cache, artikel_pruefen/kombis_laden lesen nur) –
    # deshalb gibt es hier keinen Schreibpfad und keine Blockbildung.
    from app import betrieb
    with betrieb.import_markieren("Logik-Excel"):
        logik, bericht = logik_einlesen()
        artikel_pruefen(logik, session, bericht)
    _cache["logik"], _cache["bericht"] = logik, bericht
    return logik, bericht


def hole_logik(session: Session) -> tuple[Logik, Pruefbericht]:
    if _cache["logik"] is None:
        return neu_einlesen(session)
    return _cache["logik"], _cache["bericht"]
