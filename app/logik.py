# Logik-Import (Phase 3): Parser für konfigurator_logik.xlsx
# (Blätter Fragen, Aktionen, Paketmatrix, Angebotsaufbau, KfW) plus Validierung.
# Die geparste Logik wird im Prozess gecacht; "Konfiguration neu einlesen"
# ersetzt den Cache. Die inhaltliche Auswertung (Fragenfluss, KfW-Rechnung)
# folgt in den Phasen 4–6 – hier geht es um Struktur, Referenzen, Bedingungen.

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
    "Mengenmaske (4 Zahlenfelder)",
    "Wiederholfeld je Verteiler",
}

ZAHLEN_TYPEN = {"Zahleneingabe", "Betragseingabe",
                "Mengenmaske (4 Zahlenfelder)", "Wiederholfeld je Verteiler"}

# Aktionszeilen, die keine einzelne Frage betreffen
SPEZIAL_AKTIONEN = {"Gruppen-Trigger", "Grundpaket", "F30–F36", "F30-F36"}


# --- Datenstrukturen ------------------------------------------------------

@dataclass
class Bedingung:
    roh: str
    art: str                      # immer | antwort | ausgefuellt | selbstnutzung | friondo_ja
    frage_id: Optional[str] = None
    werte: list[str] = field(default_factory=list)


@dataclass
class Frage:
    id: str
    reihenfolge: int
    text: str
    typ: str
    antworten: list[str]
    bedingung: Optional[Bedingung]
    hinweis: str


@dataclass
class ArtikelRef:
    ref: str                      # "045" oder "Z01"
    menge: str = "1"              # roh: "1", "2", "eingegebene Meter", "Anzahl Verteiler", ...
    ep: bool = False


@dataclass
class Aktion:
    frage: str                    # "F01" oder Spezialschlüssel (Gruppen-Trigger, Grundpaket, ...)
    antwort: str                  # roh, z. B. "Gas", "Kunststoff, bis 3.000 L", "Meterzahl"
    aktion_roh: str
    typ: str                      # abbruch | normal
    abbruch_meldung: str
    artikel: list[ArtikelRef]
    bemerkung: str


@dataclass
class PaketZeile:
    leistungsklasse: str
    verbrauch_roh: str
    verbrauch_von: Optional[int]
    verbrauch_bis: Optional[int]
    ww_bis_200: list[ArtikelRef]
    ohne_ww: list[ArtikelRef]
    ww_300: list[ArtikelRef]


@dataclass
class AngebotsBlock:
    nr: int
    ueberschrift: str
    inhalt_roh: str
    wann: Optional[Bedingung]
    refs: list[ArtikelRef]


@dataclass
class Logik:
    fragen: dict[str, Frage]
    aktionen: list[Aktion]
    pakete: list[PaketZeile]
    bloecke: list[AngebotsBlock]
    kfw: dict[str, tuple[str, str]]         # Parameter -> (Wert, Bemerkung)
    geladen_am: datetime


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

    for m in re.finditer(r"Pos\.\s*((?:\d{1,3}(?:\s*\(EP\))?\s*(?:[,/]\s*)?)+)", text):
        nummern = re.findall(r"(\d{1,3})(\s*\(EP\))?", m.group(1))
        rest = text[m.end():]
        m_menge = re.match(r"\s*×\s*([\wäöüÄÖÜß. ]+)", rest)
        menge = m_menge.group(1).strip() if (m_menge and len(nummern) == 1) else "1"
        menge = re.sub(r"\s*als EP.*$", "", menge).strip() or "1"
        ep_nach = bool(re.match(r"[^+·]*als EP", rest))
        for nummer, ep in nummern:
            refs.append(ArtikelRef(nummer.zfill(3), menge, bool(ep) or ep_nach))

    for m in re.finditer(r"\bZ(\d{2})\b(?:\s*[–-]\s*Z(\d{2}))?", text):
        von, bis = int(m.group(1)), int(m.group(2) or m.group(1))
        rest = text[m.end():]
        m_menge = re.match(r"\s*×\s*([\wäöüÄÖÜß. ]+)", rest)
        menge = m_menge.group(1).strip() if (m_menge and von == bis) else "1"
        for n in range(von, bis + 1):
            refs.append(ArtikelRef(f"Z{n:02d}", menge, False))
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
    m = re.match(r"nur wenn F(\d+)\s+ausgefüllt$", text)
    if m:
        return Bedingung(text, "ausgefuellt", f"F{m.group(1)}")
    m = re.match(r"nur wenn F(\d+)\s*=\s*(.+)$", text)
    if m:
        werte = [w.strip() for w in m.group(2).split(" oder ")]
        return Bedingung(text, "antwort", f"F{m.group(1)}", werte)
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

    logik = Logik(fragen, aktionen, pakete, bloecke, kfw, datetime.now())
    _querbezuege_pruefen(logik, bericht)
    return logik, bericht


def _fragen_einlesen(wb, bericht: Pruefbericht) -> dict[str, Frage]:
    fragen: dict[str, Frage] = {}
    for zeile, row in enumerate(wb["Fragen"].iter_rows(min_row=2, values_only=True), 2):
        fid, reihenfolge, text, typ, antworten, anzeigen, hinweis = (_zelle(v) for v in row[:7])
        if not fid:
            continue
        if fid in fragen:
            bericht.fehler.append(f"Fragen Zeile {zeile}: ID {fid} doppelt vergeben.")
            continue
        if typ not in FRAGE_TYPEN:
            bericht.fehler.append(f"Fragen {fid}: unbekannter Typ „{typ}“.")
        optionen = [a.strip() for a in antworten.split("|") if a.strip()] if antworten else []
        if typ == "Auswahl" and not optionen:
            bericht.fehler.append(f"Fragen {fid}: Auswahl ohne Antwortmöglichkeiten.")
        bedingung = bedingung_parsen(anzeigen)
        if bedingung is None:
            bericht.fehler.append(
                f"Fragen {fid}: Bedingung „{anzeigen}“ nicht parsebar.")
        try:
            nr = int(float(reihenfolge))
        except ValueError:
            bericht.fehler.append(f"Fragen {fid}: Reihenfolge „{reihenfolge}“ keine Zahl.")
            nr = 0
        fragen[fid] = Frage(fid, nr, text, typ, optionen, bedingung, hinweis)
    return fragen


def _aktionen_einlesen(wb, bericht: Pruefbericht) -> list[Aktion]:
    aktionen = []
    for row in wb["Aktionen"].iter_rows(min_row=2, values_only=True):
        frage, antwort, aktion_roh, bemerkung = (_zelle(v) for v in row[:4])
        if not frage:
            continue
        if aktion_roh.startswith("ABBRUCH"):
            typ = "abbruch"
            meldung = aktion_roh.split(":", 1)[1].strip() if ":" in aktion_roh else aktion_roh
        else:
            typ = "normal"
            meldung = ""
        aktionen.append(Aktion(frage, antwort, aktion_roh, typ, meldung,
                               refs_extrahieren(aktion_roh), bemerkung))
    return aktionen


def _paketmatrix_einlesen(wb, bericht: Pruefbericht) -> list[PaketZeile]:
    pakete = []
    for row in wb["Paketmatrix"].iter_rows(min_row=2, values_only=True):
        klasse, verbrauch, ww200, ohne_ww, ww300 = (_zelle(v) for v in row[:5])
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
        zeile = PaketZeile(klasse, verbrauch, von, bis,
                           refs_extrahieren(ww200), refs_extrahieren(ohne_ww),
                           refs_extrahieren(ww300))
        for spalte, refs in (("WW bis 200 l", zeile.ww_bis_200),
                             ("ohne Warmwasser", zeile.ohne_ww), ("WW 300 l", zeile.ww_300)):
            if not refs:
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
        try:
            block_nr = int(float(nr))
        except ValueError:
            bericht.fehler.append(f"Angebotsaufbau: Blocknummer „{nr}“ keine Zahl.")
            continue
        bedingung = bedingung_parsen(wann)
        if bedingung is None:
            bericht.fehler.append(
                f"Angebotsaufbau Block {block_nr}: Bedingung „{wann}“ nicht parsebar.")
        bloecke.append(AngebotsBlock(block_nr, ueberschrift, inhalt,
                                     bedingung, refs_extrahieren(inhalt)))
    return bloecke


PFLICHT_KFW_PARAMETER = [
    "Gültigkeit der Konditionen", "Grundförderung", "Klimageschwindigkeits-Bonus",
    "Einkommensbonus Stufe 1", "Einkommensbonus Stufe 2", "Einkommensbonus Stufe 3",
    "Kind-Freibetrag", "Fördersatz-Deckel", "Fördersatz-Deckel erhöht",
    "Höchstkosten EFH", "Höchstkosten MFH", "Höchstkosten Gewerbe",
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

def _antwort_pruefen(frage: Frage, antwort: str, fragen: dict[str, Frage]) -> Optional[str]:
    """Prüft, ob eine Antwort/Bedingung aus dem Blatt Aktionen zur Frage passt.
    Liefert einen Fehlertext oder None."""
    if frage.typ in ZAHLEN_TYPEN and frage.typ != "Mengenmaske (4 Zahlenfelder)":
        return None  # freie Beschreibungen/Bereiche bei Zahlenfragen erlaubt
    if frage.typ == "Mengenmaske (4 Zahlenfelder)":
        m = re.match(r"Anzahl\s+(\S+)$", antwort)
        if m and m.group(1) in frage.antworten:
            return None
        return f"„{antwort}“ passt nicht zur Mengenmaske ({' | '.join(frage.antworten)})."

    # Auswahl: "A", "A oder B", "A / B", "Bedingungsfrage-Wert, eigener Wert"
    teile = re.split(r"\s+oder\s+|\s*/\s*", antwort)
    if all(_alias_aufloesen(t.strip(), frage.antworten) for t in teile):
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


def _querbezuege_pruefen(logik: Logik, bericht: Pruefbericht) -> None:
    fragen = logik.fragen

    # Bedingungen der Fragen: referenzierte Frage + Werte müssen existieren
    for frage in fragen.values():
        b = frage.bedingung
        if b is None or b.art not in ("antwort", "ausgefuellt"):
            continue
        if b.frage_id not in fragen:
            bericht.fehler.append(
                f"Fragen {frage.id}: Bedingung verweist auf unbekannte Frage {b.frage_id}.")
            continue
        ziel = fragen[b.frage_id]
        if b.art == "antwort" and ziel.typ == "Auswahl":
            for wert in b.werte:
                if _alias_aufloesen(wert, ziel.antworten) is None:
                    bericht.fehler.append(
                        f"Fragen {frage.id}: Bedingungswert „{wert}“ ist keine Option von {ziel.id}.")

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
    # F30–F36 sind über die Sammelzeile "F30–F36" (KfW-Angaben) abgedeckt.
    sammelbereich = {f"F{n}" for n in range(30, 37)
                     if any(a.frage in ("F30–F36", "F30-F36") for a in logik.aktionen)}
    for frage in fragen.values():
        if frage.typ != "Auswahl" or frage.id in sammelbereich:
            continue
        abgedeckt = set()
        for aktion in logik.aktionen:
            if aktion.frage != frage.id:
                continue
            for teil in re.split(r"\s+oder\s+|\s*/\s*|,", aktion.antwort):
                option = _alias_aufloesen(teil.strip(), frage.antworten)
                if option:
                    abgedeckt.add(option)
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
            bericht.fehler.append(
                f"Artikel {('Pos. ' + ref) if not ref.startswith('Z') else ref} "
                f"fehlt im Artikelstamm – referenziert in: {'; '.join(sorted(set(quellen)))}.")


# --- Cache / öffentliche API ---------------------------------------------

_cache: dict = {"logik": None, "bericht": None}


def neu_einlesen(session: Session) -> tuple[Logik, Pruefbericht]:
    logik, bericht = logik_einlesen()
    artikel_pruefen(logik, session, bericht)
    _cache["logik"], _cache["bericht"] = logik, bericht
    return logik, bericht


def hole_logik(session: Session) -> tuple[Logik, Pruefbericht]:
    if _cache["logik"] is None:
        return neu_einlesen(session)
    return _cache["logik"], _cache["bericht"]
