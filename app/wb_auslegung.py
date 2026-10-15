# Wallbox-Auslegung (v34, PLAN_V21 Phase 179, Stand Nachtrag + Ergänzung 15.10.2026): aus
# dem WB-Erfassungsbogen (Mennekes AMTRON 4You 310/560, Leitungsverlegung, Erdarbeiten,
# Wandmontage/Säule, Durchbrüche) entstehen die Angebotspositionen laut Blatt „Aktionen WB“
# in der Reihenfolge des Blatts „Angebotsaufbau WB“ (Vorbild: app/kl_auslegung.py).
#
# Fragen (Blatt „Fragen WB“): WB01 Wallbox → WB001/WB002; WB02 Leitungsverlegung gesamt in
# Metern – bis `leitung_inklusive_m` = 10 m in der Anschlussvorbereitung WB003 enthalten,
# Mehrlänge = WB02 − 10 m, kaufmännisch auf ganze Meter, nie unter 0 → WB005 × Mehrlänge;
# WB03 Erdarbeiten Ja/Nein mit WB04 Meter → WB006 × Meter (ganze Meter, 0/leer = Absende-
# Meldung „Erdarbeiten: Meter fehlen“; unabhängig von Wandmontage/Säule); WB05 Wandmontage |
# Säule → WB007 × 1 (psl.) bei Säule; WB07 Anzahl Durchbrüche – `durchbrueche_inklusive` = 2
# in der Anschlussvorbereitung enthalten, darüber WB008 × (WB07 − 2) (ganze Stück, nie
# unter 0); WB08 Bemerkung (nur Protokoll; WB06 ist unbelegt). Immer im Angebot: WB003 (psl.)
# und WB004 Netzanmeldung §14a (0,00 €). Keine AMPEL-Gründe (eine WB-Katalog-Erfassung ist
# immer grün); Leitungslänge über 100 m ist eine Warnung ohne Sperre. Keine Auslegungs-
# Position im Angebot – die Herleitung steht im Protokoll (Seite „Auslegung“) und in
# angebote.auslegung_text.
#
# Alle Rechenwerte stehen im Blatt „WB-Parameter“ der Logik-Excel; die Standardwerte im
# Code sind nur Fallback (parameter() meldet fehlende Zeilen). Kein DB-Zugriff außer in
# positionen_zusammenstellen / artikel_namen / artikel_vorhanden.
#
# Vereinbarte Schnittstelle zum Lader (app/logik.py, logik_fuer_sparte(…, "WB")):
#   wb_aktionen, wb_bloecke, wb_parameter (Name → (Wert, Bemerkung)), wb_artikel
#   (WB-Nr. → Ankerzeile), wb_artikel_nummern. Alle Zugriffe laufen über getattr
#   mit Standardwerten. Mengenwörter in den Aktionen: „× Mehrlänge“ (WB02), „× WB04“
#   (= Zahl der Frage WB04, ganze Meter), „× (WB07 − 2)“ (= Zahl der Frage WB07 minus 2,
#   ganze Stück, nie unter 0) – aufgelöst in _menge_aufloesen.

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from app import konfigurator as engine
from app.logik import FREITEXT_TYPEN

# Fragen-IDs des WB-Bogens (Blatt „Fragen WB“, Nachtrag + Ergänzung 15.10.2026)
ID_WALLBOX = "WB01"
ID_LEITUNG = "WB02"
ID_ERDARBEITEN = "WB03"
ID_ERDARBEITEN_M = "WB04"
ID_MONTAGE = "WB05"
ID_DURCHBRUECHE = "WB07"
ID_BEMERKUNG = "WB08"
ANTWORT_SAEULE = "Säule"
ANTWORT_WAND = "Wandmontage"

# Meldungen (wörtlich PLAN_V21 Phase 179 / Nachtrag)
MELDUNG_WALLBOX = "Wallbox auswählen"
MELDUNG_LEITUNG = "Leitungslänge fehlt oder ist keine Zahl"
MELDUNG_ERDARBEITEN = "Erdarbeiten: Meter fehlen"
MELDUNG_DURCHBRUECHE = "Durchbrüche: Anzahl fehlt oder ist keine Zahl"
WARNUNG_LEITUNG = "Leitungslänge über 100 m – bitte prüfen"
LEITUNG_WARNGRENZE_M = 100.0

# Pflichtzeilen des Blatts „WB-Parameter“ mit Standardwerten (nur Fallback –
# fehlende Zeilen meldet „Logik prüfen“ als Hinweis mit dem Standardwert)
STANDARD_WB_PARAMETER: dict[str, str] = {
    "leitung_inklusive_m": "10",
    "meterposition_leitung": "WB005",
    "erdarbeiten_position": "WB006",
    "fundament_position": "WB007",
    "durchbrueche_inklusive": "2",
    "durchbruch_position": "WB008",
    "wallbox_standard": "",
}
PFLICHT_WB_PARAMETER = list(STANDARD_WB_PARAMETER)


# --- Parameter (Blatt „WB-Parameter“) ------------------------------------------

def _parameter_roh(logik) -> dict[str, str]:
    roh = getattr(logik, "wb_parameter", None) or {}
    ergebnis: dict[str, str] = {}
    for name, eintrag in roh.items():
        wert = eintrag[0] if isinstance(eintrag, (tuple, list)) else eintrag
        ergebnis[str(name).strip()] = "" if wert is None else str(wert).strip()
    return ergebnis


def _zahl(wert) -> Optional[float]:
    """Parameterwert als Zahl: „10“ / „10,5“ / „10 m“ / „2 Stück“ / Excel-Float."""
    if isinstance(wert, (int, float)):
        return float(wert)
    text = re.sub(r"\s*(m|Stück|Stk\.?)\s*$", "", str(wert if wert is not None else "").strip())
    if not text:
        return None
    return engine.zahl_parsen(text)


def parameter(logik) -> dict:
    """Rechenwerte aus dem Blatt „WB-Parameter“; Standardwerte als Fallback,
    `fehlende` nennt die fehlenden Pflichtzeilen (Parametrierung zeigt sie an).
    `wallbox_standard` darf leer sein (keine Vorbelegung) und zählt dann nicht als
    fehlend, sofern die Zeile existiert."""
    roh = _parameter_roh(logik)
    vorhanden = set(getattr(logik, "wb_parameter", None) or {})
    fehlende = [name for name in PFLICHT_WB_PARAMETER
                if name not in vorhanden and not roh.get(name)]

    def zahl(name: str) -> float:
        wert = _zahl(roh.get(name))
        if wert is None or wert < 0:
            wert = float(STANDARD_WB_PARAMETER[name])
        return wert

    def text(name: str) -> str:
        return roh.get(name) or STANDARD_WB_PARAMETER[name]

    return {
        "leitung_inklusive_m": zahl("leitung_inklusive_m"),
        "meterposition_leitung": text("meterposition_leitung"),
        "erdarbeiten_position": text("erdarbeiten_position"),
        "fundament_position": text("fundament_position"),
        "durchbrueche_inklusive": int(zahl("durchbrueche_inklusive")),
        "durchbruch_position": text("durchbruch_position"),
        "wallbox_standard": roh.get("wallbox_standard") or "",
        "fehlende": fehlende,
    }


# --- Datenklasse ---------------------------------------------------------------

@dataclass
class Auslegung:
    wallbox: str = ""                 # Kurzname („AMTRON 4You 560“) für Protokoll/Texte
    wallbox_antwort: str = ""         # Option von WB01 wörtlich
    wallbox_ref: str = ""             # WB001 / WB002 laut Aktionen WB
    leitung_m: Optional[float] = None  # Eingabe WB02 (gesamt)
    leitung_inklusive_m: float = 10.0
    mehrlaenge_m: int = 0
    erdarbeiten: bool = False         # WB03 = Ja
    erdarbeiten_m: int = 0            # WB04, ganze Meter
    montage: str = ANTWORT_WAND       # WB05: „Wandmontage“ | „Säule“
    durchbrueche: int = 0             # WB07 gesamt (ganze Stück)
    durchbrueche_inklusive: int = 2   # in der Anschlussvorbereitung enthalten
    durchbrueche_zusatz: int = 0      # WB07 − inklusive, nie unter 0 → WB008
    positionen: list[str] = field(default_factory=list)   # WB-Refs in Blockreihenfolge
    warnungen: list[str] = field(default_factory=list)    # z. B. Leitungslänge über 100 m
    bemerkung: str = ""               # WB08 (nur Protokoll)

    @property
    def saeule(self) -> bool:
        return self.montage == ANTWORT_SAEULE

    def als_dict(self) -> dict:
        return {"wallbox": self.wallbox, "wallbox_antwort": self.wallbox_antwort,
                "wallbox_ref": self.wallbox_ref, "leitung_m": self.leitung_m,
                "leitung_inklusive_m": self.leitung_inklusive_m,
                "mehrlaenge_m": self.mehrlaenge_m, "erdarbeiten": self.erdarbeiten,
                "erdarbeiten_m": self.erdarbeiten_m, "montage": self.montage,
                "durchbrueche": self.durchbrueche,
                "durchbrueche_inklusive": self.durchbrueche_inklusive,
                "durchbrueche_zusatz": self.durchbrueche_zusatz,
                "positionen": list(self.positionen), "warnungen": list(self.warnungen),
                "bemerkung": self.bemerkung}


# --- Hilfen ----------------------------------------------------------------------

def _de(zahl, stellen: int = 0) -> str:
    """Deutsche Zahl: 25 · 12,4 · 1.234,56."""
    if zahl is None:
        return ""
    text = f"{float(zahl):,.{stellen}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def meter_text(zahl) -> str:
    """„25 m“ bei ganzen Metern, sonst „12,4 m“ (höchstens zwei Nachkommastellen)."""
    if zahl is None:
        return ""
    wert = float(zahl)
    if abs(wert - round(wert)) < 1e-9:
        return f"{_de(round(wert), 0)} m"
    text = f"{wert:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") + " m"


def wallbox_kurz(option: str) -> str:
    """Kurzname der Wallbox aus der WB01-Option: „Mennekes AMTRON 4You 560 – 11 kW, …“
    → „AMTRON 4You 560“ (Herstellername und Zusatz nach dem Gedankenstrich entfallen)."""
    text = re.split(r"\s+[–—-]\s+", str(option or "").strip(), maxsplit=1)[0].strip()
    return re.sub(r"^Mennekes\s+", "", text, flags=re.I).strip()


def ganze_zahl(wert) -> int:
    """Eingabe in ganze Meter/Stück: kaufmännisch gerundet (ROUND_HALF_UP: 8,5 → 9), nie
    unter 0, leer/keine Zahl → 0 [ANNAHME: ganze Meter wie Pos. 103 bei A13]."""
    zahl = engine.zahl_parsen(wert)
    if zahl is None or zahl <= 0:
        return 0
    return int(Decimal(str(zahl)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


ganze_meter = ganze_zahl


def mehrlaenge(leitung_m, inklusive_m: float) -> int:
    """Mehrlänge in ganzen Metern: Leitungsverlegung − inklusive Meter, kaufmännisch
    gerundet (12,4 − 10 = 2,4 → 2; 12,5 → 3), nie unter 0."""
    zahl = engine.zahl_parsen(leitung_m)
    if zahl is None:
        return 0
    rest = Decimal(str(zahl)) - Decimal(str(inklusive_m))
    if rest <= 0:
        return 0
    return int(rest.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _aktionen(logik) -> list:
    return list(getattr(logik, "wb_aktionen", None) or getattr(logik, "aktionen", None) or [])


def _zusatz_ok(aktion, antworten: dict, logik) -> bool:
    b = getattr(aktion, "zusatz_bedingung", None)
    if b is None:
        return True
    dummy = engine.Frage("_", 0, "", "Auswahl", [], b, "")
    return engine.ist_sichtbar(dummy, antworten, logik.fragen, logik)


def _menge_aufloesen(ref, antworten: dict, mehr: int) -> float:
    """Mengenwörter der WB-Aktionen: „Mehrlänge“ (= Mehrlänge aus WB02), „WB04“ (= Zahl der
    Frage WB04 in ganzen Metern), „(WB07 − 2)“ (= Zahl der Frage minus Abzug, ganze Stück,
    nie unter 0), sonst die Zahl („1“)."""
    roh = str(getattr(ref, "menge", "") or "1").strip()
    if "mehrl" in roh.lower():
        return float(mehr)
    m_abzug = re.fullmatch(r"\(?\s*(WB\d{2})\s*[−–-]\s*(\d+)\s*\)?", roh)
    if m_abzug:
        return float(max(0, ganze_zahl(antworten.get(m_abzug.group(1))) - int(m_abzug.group(2))))
    m_frage = re.fullmatch(r"\(?\s*(WB\d{2})\s*\)?", roh)
    if m_frage:
        return float(ganze_zahl(antworten.get(m_frage.group(1))))
    m = re.match(r"\s*(\d+(?:[.,]\d+)?)", roh)
    zahl = engine.zahl_parsen(m.group(1)) if m else None
    return float(zahl) if zahl is not None else 1.0


# --- Auslegung -------------------------------------------------------------------

def auslegen(logik, antworten: dict) -> Auslegung:
    """Wallbox (WB01 → Aktionszeile → WB-Ref), Leitungsverlegung (WB02) mit Mehrlänge,
    Erdarbeiten (WB03/WB04), Montage (WB05), Durchbrüche (WB07) und die Positionsliste in
    Blockreihenfolge; Warnung ab 100 m."""
    p = parameter(logik)
    a = Auslegung(leitung_inklusive_m=p["leitung_inklusive_m"],
                  durchbrueche_inklusive=p["durchbrueche_inklusive"])
    a.wallbox_antwort = str(antworten.get(ID_WALLBOX) or "").strip()
    a.wallbox = wallbox_kurz(a.wallbox_antwort)
    a.leitung_m = engine.zahl_parsen(antworten.get(ID_LEITUNG))
    a.mehrlaenge_m = mehrlaenge(a.leitung_m, a.leitung_inklusive_m)
    a.erdarbeiten = str(antworten.get(ID_ERDARBEITEN) or "").strip() == "Ja"
    a.erdarbeiten_m = ganze_zahl(antworten.get(ID_ERDARBEITEN_M)) if a.erdarbeiten else 0
    montage = str(antworten.get(ID_MONTAGE) or "").strip()
    a.montage = ANTWORT_SAEULE if montage == ANTWORT_SAEULE else (montage or ANTWORT_WAND)
    a.durchbrueche = ganze_zahl(antworten.get(ID_DURCHBRUECHE))
    a.durchbrueche_zusatz = max(0, a.durchbrueche - a.durchbrueche_inklusive)
    a.bemerkung = str(antworten.get(ID_BEMERKUNG) or "").strip()
    if a.leitung_m is not None and a.leitung_m > LEITUNG_WARNGRENZE_M:
        a.warnungen.append(WARNUNG_LEITUNG)
    gewaehlt = artikel_ermitteln(logik, antworten, a)
    for g in gewaehlt:
        if g.quelle == ID_WALLBOX and not a.wallbox_ref:
            a.wallbox_ref = g.ref
    a.positionen = [g.ref for g in _in_blockreihenfolge(logik, gewaehlt)]
    return a


# --- Positionen ------------------------------------------------------------------

@dataclass
class WbArtikel:
    ref: str
    menge: float
    ep: bool
    quelle: str          # Frage-ID („WB01“, „WB02“, „WB03“, „WB05“, „WB07“) oder „grundpaket“


def artikel_ermitteln(logik, antworten: dict, a: Optional[Auslegung] = None) -> list[WbArtikel]:
    """Gewählte Artikel: Aktionen WB je sichtbarer beantworteter Frage (WB01 → Wallbox,
    WB02 „über 10“ → WB005 × Mehrlänge, WB03 = Ja → WB006 × WB04, WB05 = Säule → WB007,
    WB07 „über 2“ → WB008 × (WB07 − 2)) plus die Grundpaket-Zeilen (WB003
    Anschlussvorbereitung, WB004 Netzanmeldung). Mengenwörter werden aufgelöst; Menge 0 →
    keine Position. Alle passenden Zeilen einer Frage zählen (je Artikel eine Zeile)."""
    p = parameter(logik)
    inklusive = a.leitung_inklusive_m if a is not None else p["leitung_inklusive_m"]
    mehr = mehrlaenge(antworten.get(ID_LEITUNG), inklusive)
    aktionen = _aktionen(logik)
    gewaehlt: list[WbArtikel] = []
    fragen = getattr(logik, "fragen", None) or {}
    for frage in engine.sichtbare_fragen(logik, antworten) if fragen else []:
        if frage.id not in antworten:
            continue
        wert = antworten[frage.id]
        if isinstance(wert, (dict, list)) or frage.typ in FREITEXT_TYPEN:
            continue
        for aktion in aktionen:
            if aktion.frage != frage.id or aktion.typ != "normal":
                continue
            index = engine._teil_index(frage, aktion.antwort, wert, antworten, fragen)
            if index is None or not _zusatz_ok(aktion, antworten, logik):
                continue
            for ref in engine.refs_fuer_treffer(aktion, index):
                menge = _menge_aufloesen(ref, antworten, mehr)
                if menge > 0:
                    gewaehlt.append(WbArtikel(ref.ref, menge, bool(ref.ep), frage.id))
    for aktion in aktionen:
        if aktion.typ != "normal" or str(aktion.frage).strip().lower() not in ("grundpaket", "immer"):
            continue
        if not _zusatz_ok(aktion, antworten, logik):
            continue
        for ref in aktion.artikel:
            menge = _menge_aufloesen(ref, antworten, mehr)
            if menge > 0:
                gewaehlt.append(WbArtikel(ref.ref, menge, bool(ref.ep), "grundpaket"))
    return gewaehlt


def _bloecke(logik) -> list:
    bloecke = getattr(logik, "wb_bloecke", None) or getattr(logik, "bloecke", None) or []
    return sorted((b for b in bloecke if "Summenblock" not in str(b.ueberschrift)),
                  key=lambda b: b.nr)


def _index_im_inhalt(inhalt: str, ref: str) -> int:
    m = re.search(rf"\b{re.escape(ref)}\b", inhalt or "")
    return m.start() if m else -1


def ueberschrift(block) -> str:
    if block is None:
        return ""
    u = str(block.ueberschrift or "")
    if u.startswith("(ohne"):
        return ""
    if u.startswith("DYNAMISCH"):
        zitate = re.findall(r"'([^']+)'", u)
        return zitate[0] if zitate else u
    return u


def _in_blockreihenfolge(logik, gewaehlt: list[WbArtikel]) -> list[WbArtikel]:
    """Sortierung nach Blatt „Angebotsaufbau WB“ (Block, Position der WB-Nr. im Inhalt);
    nicht genannte Artikel landen am Ende des letzten Blocks."""
    bloecke = _bloecke(logik)
    letzter = bloecke[-1].nr if bloecke else 99
    zugeordnet = []
    for lauf, gw in enumerate(gewaehlt):
        platz = (letzter, 9999)
        for block in bloecke:
            index = _index_im_inhalt(block.inhalt_roh, gw.ref)
            if index >= 0:
                platz = (block.nr, index)
                break
        zugeordnet.append((platz[0], platz[1], lauf, gw))
    zugeordnet.sort(key=lambda t: t[:3])
    return [t[3] for t in zugeordnet]


def positionen_bauen(logik, antworten: dict, artikel_map: dict) -> list[dict]:
    """Positions-Snapshots ohne DB-Zugriff (artikel_map: pos_nr → Artikel-Stamm):
    Blockzuordnung über die WB-Nummern im Inhalt des Blatts „Angebotsaufbau WB“,
    gleiche Artikel im selben Block addiert, Gruppen-Überschriften aus den Blöcken,
    KEINE Auslegungszeile (v34 Phase 180)."""
    gewaehlt = artikel_ermitteln(logik, antworten)
    bloecke = _bloecke(logik)
    bloecke_map = {b.nr: b for b in bloecke}
    letzter = bloecke[-1].nr if bloecke else 99
    positionen: list[dict] = []
    gesehen: dict[tuple[int, str], dict] = {}
    for gw in _in_blockreihenfolge(logik, gewaehlt):
        block_nr = letzter
        for block in bloecke:
            if _index_im_inhalt(block.inhalt_roh, gw.ref) >= 0:
                block_nr = block.nr
                break
        schluessel = (block_nr, gw.ref)
        if schluessel in gesehen:
            gesehen[schluessel]["menge"] += gw.menge
            gesehen[schluessel]["ep_flag"] = gesehen[schluessel]["ep_flag"] or gw.ep
            continue
        stamm = artikel_map.get(gw.ref)
        if stamm is None:
            continue   # Logik prüfen meldet fehlende Artikel in der Parametrierung
        eintrag = {
            "block_nr": block_nr,
            "gruppe": ueberschrift(bloecke_map.get(block_nr)),
            "pos_nr": stamm.pos_nr, "bezeichnung": stamm.bezeichnung,
            "beschreibung": stamm.beschreibung, "menge": gw.menge,
            "einheit": stamm.einheit, "e_preis_cent": stamm.e_preis_cent,
            "ep_flag": bool(stamm.ep_flag or gw.ep), "ek_cent": stamm.ek_cent,
            "guid": stamm.guid,
        }
        gesehen[schluessel] = eintrag
        positionen.append(eintrag)
    for sort, x in enumerate(positionen, 1):
        x["sort"] = sort
    return positionen


def artikel_vorhanden(session) -> bool:
    """Gibt es mindestens einen aktiven WB-Artikel im Artikelstamm (Import gelaufen)?"""
    from app.models import Artikel
    return (session.query(Artikel.id)
            .filter(Artikel.aktiv.is_(True), Artikel.pos_nr.like("WB%")).first()) is not None


def positionen_zusammenstellen(logik, antworten: dict, session,
                               erfassung=None) -> list[dict]:
    """Positions-Snapshots des Wallbox-Angebots in Blockreihenfolge (Blatt
    „Angebotsaufbau WB“) – Artikelstamm aus der Datenbank."""
    from app.models import Artikel
    artikel_map = {x.pos_nr: x for x in
                   session.query(Artikel).filter(Artikel.aktiv.is_(True),
                                                 Artikel.pos_nr.like("WB%")) if x.pos_nr}
    return positionen_bauen(logik, antworten, artikel_map)


# --- Validierung / Warnungen -------------------------------------------------------

def validierung(antworten: dict, logik=None) -> list[str]:
    """Meldungen für das Absenden (blockieren): Wallbox gewählt (WB01), Leitungsverlegung
    vorhanden und eine Zahl ≥ 0 (WB02), bei Erdarbeiten (WB03 = Ja) Meter > 0 (WB04),
    Anzahl Durchbrüche vorhanden (WB07). Die Warnung ab 100 m blockiert nicht."""
    meldungen: list[str] = []
    if not str(antworten.get(ID_WALLBOX) or "").strip():
        meldungen.append(MELDUNG_WALLBOX)
    zahl = engine.zahl_parsen(antworten.get(ID_LEITUNG))
    if zahl is None or zahl < 0:
        meldungen.append(MELDUNG_LEITUNG)
    if (str(antworten.get(ID_ERDARBEITEN) or "").strip() == "Ja"
            and ganze_zahl(antworten.get(ID_ERDARBEITEN_M)) <= 0):
        meldungen.append(MELDUNG_ERDARBEITEN)
    durchbrueche = engine.zahl_parsen(antworten.get(ID_DURCHBRUECHE))
    if ID_DURCHBRUECHE in antworten and (durchbrueche is None or durchbrueche < 0):
        meldungen.append(MELDUNG_DURCHBRUECHE)
    return meldungen


def warnungen(antworten: dict, logik=None) -> list[str]:
    """Nicht blockierende Hinweise: Leitungslänge über 100 m – bitte prüfen
    [ANNAHME: Warnung, keine Sperre]."""
    zahl = engine.zahl_parsen(antworten.get(ID_LEITUNG))
    if zahl is not None and zahl > LEITUNG_WARNGRENZE_M:
        return [WARNUNG_LEITUNG]
    return []


# --- Protokoll -------------------------------------------------------------------

def leitungs_text(a: Auslegung) -> str:
    """„Leitungsverlegung gesamt: 25 m, davon 10 m enthalten, Mehrlänge 15 m“ (wörtlich
    Nachtrag 15.10.2026); ohne Mehrlänge: „Leitungsverlegung gesamt: 8 m – bis 10 m
    enthalten, keine Mehrlänge“."""
    if a.leitung_m is None:
        return "Leitungsverlegung: keine Angabe"
    gesamt = meter_text(a.leitung_m)
    inkl = meter_text(a.leitung_inklusive_m)
    if a.mehrlaenge_m > 0:
        return (f"Leitungsverlegung gesamt: {gesamt}, davon {inkl} enthalten, "
                f"Mehrlänge {meter_text(a.mehrlaenge_m)}")
    return f"Leitungsverlegung gesamt: {gesamt} – bis {inkl} enthalten, keine Mehrlänge"


def erdarbeiten_text(a: Auslegung) -> str:
    if a.erdarbeiten and a.erdarbeiten_m > 0:
        return f"Erdarbeiten: {meter_text(a.erdarbeiten_m)}"
    if a.erdarbeiten:
        return "Erdarbeiten: Meter fehlen"
    return "Erdarbeiten: keine"


def montage_text(a: Auslegung) -> str:
    return ("Montage: Säule (Fundament und Standsäule)" if a.saeule
            else "Montage: Wandmontage")


def durchbrueche_text(a: Auslegung) -> str:
    """„Durchbrüche: 4 (2 in der Anschlussvorbereitung enthalten, 2 zusätzlich)“ (wörtlich
    Ergänzung 15.10.2026); ohne Zusatz: „Durchbrüche: 2 (in der Anschlussvorbereitung
    enthalten)“ [ANNAHME]."""
    if a.durchbrueche_zusatz > 0:
        return (f"Durchbrüche: {a.durchbrueche} ({a.durchbrueche_inklusive} in der "
                f"Anschlussvorbereitung enthalten, {a.durchbrueche_zusatz} zusätzlich)")
    return f"Durchbrüche: {a.durchbrueche} (in der Anschlussvorbereitung enthalten)"


def protokoll_zeilen(a: Auslegung) -> list[str]:
    """Textzeilen der Auslegung (Seite „Auslegung“ des Protokoll-PDFs und
    angebote.auslegung_text): Wallbox, Leitungsverlegung, Erdarbeiten, Montage, Durchbrüche,
    ggf. Warnung."""
    zeilen = [f"Wallbox: {a.wallbox or 'keine Angabe'}", leitungs_text(a), erdarbeiten_text(a),
              montage_text(a), durchbrueche_text(a)]
    zeilen.extend(a.warnungen)
    return zeilen


def auslegungs_text(a: Auslegung) -> str:
    """Text für angebote.auslegung_text (Editor „Auslegung (intern)“, Phase 180 –
    Vertrag mit angebot_aufbau.auslegungs_text_fuer): die Protokollzeilen."""
    return "\n".join(protokoll_zeilen(a))


def protokoll_eintraege(logik, antworten: dict) -> list[dict]:
    """Seite „Auslegung“ des Konfigurationsprotokolls (Einträge ohne Frage-ID wie bei
    PV/KL) – leer, solange der Bogen unvollständig ist."""
    if engine.naechste_pflichtfrage(logik, antworten) is not None:
        return []
    a = auslegen(logik, antworten)

    def zeile(frage: str, antwort: str, grund: str = "") -> dict:
        return {"frage_id": "", "seite": "Auslegung", "frage": frage,
                "antwort": antwort, "ampel_grund": grund}

    def nach_doppelpunkt(text: str) -> str:
        return text.split(": ", 1)[1] if ": " in text else text

    eintraege = [zeile("Wallbox", a.wallbox or "keine Angabe"),
                 zeile("Leitungsverlegung gesamt", nach_doppelpunkt(leitungs_text(a))),
                 zeile("Erdarbeiten", nach_doppelpunkt(erdarbeiten_text(a))),
                 zeile("Montage", nach_doppelpunkt(montage_text(a))),
                 zeile("Durchbrüche", nach_doppelpunkt(durchbrueche_text(a)))]
    for warnung in a.warnungen:
        eintraege.append(zeile("Hinweis", warnung))
    return eintraege


def artikel_namen(session) -> dict[str, str]:
    """WB-Nr. → erste Zeile des Artikeltexts (Anzeige in der Parametrierung)."""
    from app.models import Artikel
    namen = {}
    for a in session.query(Artikel).filter(Artikel.aktiv.is_(True), Artikel.pos_nr.like("WB%")):
        namen[a.pos_nr] = (a.bezeichnung or "").strip() or (
            a.beschreibung.splitlines()[0] if a.beschreibung else "")
    return namen
