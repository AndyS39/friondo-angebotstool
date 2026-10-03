# Klima-Auslegung (v24, PLAN_V16 Phase 114): aus dem KL-Erfassungsbogen
# (Bosch Climate, Single-/Multi-Split) werden je Raum Kühllast und Innengeräte-
# Klasse bestimmt, je Außengerät das Gerät (Single-Set aus der Paketmatrix bzw.
# kleinstes Multi-Außengerät, dessen Kombinationsliste die Klassen-Codes
# freigibt), die Montagepauschale aus der Montagematrix und die §14a-Anmeldung.
# Daraus entstehen die Angebotspositionen laut Blatt „Aktionen KL“ in der
# Reihenfolge des Blatts „Angebotsaufbau KL“ (Muster: app/pv_auslegung.py).
#
# Alle Rechenwerte stehen im Blatt „KL-Parameter“ der Logik-Excel; die
# Standardwerte im Code sind nur Fallback (parameter() meldet fehlende Zeilen).
# Kein DB-Zugriff außer in positionen_zusammenstellen / artikel_namen.
#
# Vereinbarte Schnittstelle zum Lader (app/logik.py, logik_fuer_sparte(…, "KL")):
#   kl_aktionen, kl_bloecke, kl_paket (serie, typ single|multi_innen|multi_aussen,
#   klasse, kuehllast, artikel, bemerkung, nicht_im_sortiment), kl_kombis
#   (Außengerät → Anzahl → {„9+9+12“ …}), kl_kombi_artikel (Außengerät → KL-Nr.),
#   kl_montage ((Innengeräte, Außengeräte) → KL-Nr.), kl_parameter (Name →
#   (Wert, Bemerkung)). Alle Zugriffe laufen über getattr mit Standardwerten.

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from app import konfigurator as engine
from app.logik import FREITEXT_TYPEN

# Fragen-IDs des KL-Bogens (Blatt „Fragen KL“); Raumfragen als Klone „KR08#1“ …
ID_GEBAEUDEART = "KO01"
ID_EIGENTUEMER = "KO03"
ID_ANZAHL_AUSSEN = "KO04"
ID_ANZAHL_RAEUME = "KO05"
ID_SERIE = "KO06"
ID_WLAN = "KO08"
ID_RAUMNAME = "KR01"
ID_LAGE = "KR02"
ID_HAUPTZWECK = "KR03"
ID_MONTAGEORT_INNEN = "KR04"
ID_ENTFERNUNG = "KR05"
ID_ZUORDNUNG = "KR07"
ID_FLAECHE = "KR08"
ID_HOEHE = "KR09"
ID_WAERMELAST = "KR10"
ID_MONTAGEORT_AUSSEN = "KA01"
ID_MONTAGEHOEHE = "KA02"
ID_STROM = "KE01"
ID_ZULEITUNG = "KE02"
ID_ERREICHBARKEIT = "KZ01"

MAX_RAEUME = engine.MAX_WIEDERHOLUNGEN          # 12 (Obergrenze der Raum-Klone)
STANDARDSERIE = "Climate 3200i (Standard)"
P14A_REF_STANDARD = "KL003"
AUSLEGUNGSZEILE = "Auslegung der Klimaanlage"

# --- Texte (wörtlich PLAN_V16 Phase 114) --------------------------------------

G1 = "Kühllast über {max} kW: {raum} ({kw} kW) – Raum teilen oder Sonderlösung"
G2 = "Klasse {code} in Serie {serie} nicht verfügbar – Serie wechseln"
G3 = "Multi-Split in Serie {serie} nicht verfügbar"
G4 = "Multi-Split-Kombination {codes} an Außengerät {n} nicht freigegeben (Bosch Tab. 7)"
G5 = "Mehr als {max} Innengeräte an Außengerät {n}"
G6 = "Montagekombination {innen} Innengeräte / {aussen} Außengeräte nicht hinterlegt"
G7 = "Leitungslänge über 15 m: {raum} – max. Leitungslänge der Serie prüfen"
G8 = "Elektrozuleitung über 15 m"
GEWERBE_AMPEL = "Gewerbeobjekt – individuelle Auslegung"

MELDUNG_AUSSEN_OHNE_RAUM = ("Außengerät {n} hat keinen zugeordneten Raum – Zuordnung (KR07) "
                            "prüfen oder Anzahl Außengeräte anpassen.")
MELDUNG_FLAECHE_FEHLT = "Raum {nr}: Raumfläche fehlt"
# Zusatzprüfung (nicht im Plan, eigene Formulierung): KO04 wurde nach der
# Raumzuordnung verkleinert – der Raum hängt an einem Außengerät, das es nicht gibt
MELDUNG_ZUORDNUNG_ZU_HOCH = ("Raum {nr}: Zuordnung zum Außengerät {k} – es gibt nur "
                             "{anzahl} Außengerät(e) (KO04)")

HINWEIS_EIGENTUEMER = "Zustimmung des Eigentümers einholen"
HINWEIS_GEWERBE = "Gewerbeobjekt – Auslegung prüfen"
HINWEIS_INNENWAND = ("{raum}: Innengerät an Innenwand – Leitungsführung und "
                     "Kondensatablauf prüfen")
HINWEIS_HEIZEN = "{raum}: Heizbetrieb als Hauptzweck – Serie 7000i/8000i empfohlen"
HINWEIS_FLACHDACH = ("Flachdach – keine Dachdurchführung, Leitungsführung über "
                     "Attika/Fassade prüfen")
HINWEIS_UNKLAR = "Montageort Außengerät klären"
HINWEIS_HOEHE = "Montagehöhe über 4 m ohne Gerüst/Bühne prüfen"
HINWEIS_STROM = "Stromversorgung am Außengerät prüfen"
HINWEIS_RAEUME = "Mehr als 12 Räume – Rest händisch"


# --- Parameter (Blatt „KL-Parameter“) -----------------------------------------

PFLICHT_KL_PARAMETER = [
    "W/m² normal", "W/m² stark",
    "Höhenfaktor bis 2,5 m", "Höhenfaktor 2,5–3 m", "Höhenfaktor über 3 m",
    "Klasse 9 bis", "Klasse 12 bis", "Klasse 18 bis", "Klasse 24 bis",
    "Leitung je Innengerät inklusive", "Meterposition Zusatzleitung", "Standardserie",
    "Max. Innengeräte je Außengerät", "Max. Außengeräte", "§14a-Außengeräte",
    "Gewerbe-Verhalten", "Rollgerüst VK",
]
STANDARD_HOEHENFAKTOR = {"bis 2,5 m": 1.0, "2,5–3 m": 1.1, "über 3 m": 1.2}
STANDARD_KLASSEN = [("9", 2.6), ("12", 3.5), ("18", 5.3), ("24", 7.0)]
STANDARD_P14A = ["CL5000M 105/4 E", "CL5000M 125/5 E"]


def _zahl(wert) -> Optional[float]:
    """Parameterwert als Zahl: 1,1 / 1.1 / 60 / Excel-Float."""
    if isinstance(wert, (int, float)):
        return float(wert)
    text = str(wert if wert is not None else "").strip()
    if not text:
        return None
    text = re.sub(r"\s*(kW|W/m²|m|€.*|%)$", "", text).strip()
    return engine.zahl_parsen(text)


def _parameter_roh(logik) -> dict[str, str]:
    roh = getattr(logik, "kl_parameter", None) or {}
    ergebnis: dict[str, str] = {}
    for name, eintrag in roh.items():
        wert = eintrag[0] if isinstance(eintrag, (tuple, list)) else eintrag
        ergebnis[str(name).strip()] = "" if wert is None else str(wert).strip()
    return ergebnis


def _norm(text) -> str:
    """Vergleichsform: Kleinschreibung, Gedankenstrich = Bindestrich, keine Leerzeichen."""
    return re.sub(r"\s+", "", str(text or "").lower().replace("–", "-").replace("—", "-"))


def parameter(logik) -> dict:
    """Rechenwerte aus dem Blatt „KL-Parameter“; Standardwerte als Fallback,
    `fehlende` nennt die fehlenden Pflichtzeilen (Parametrierung zeigt sie an)."""
    roh = _parameter_roh(logik)
    fehlende = [name for name in PFLICHT_KL_PARAMETER if not roh.get(name)]

    def zahl(name, standard):
        wert = _zahl(roh.get(name))
        return standard if wert is None else wert

    def text(name, standard):
        return roh.get(name) or standard

    hoehenfaktor: dict[str, float] = {}
    for name, wert in roh.items():
        if name.startswith("Höhenfaktor"):
            faktor = _zahl(wert)
            antwort = name[len("Höhenfaktor"):].strip()
            if faktor is not None and antwort:
                hoehenfaktor[antwort] = faktor
    if not hoehenfaktor:
        hoehenfaktor = dict(STANDARD_HOEHENFAKTOR)

    klassen: list[tuple[str, float]] = []
    for name, wert in roh.items():
        m = re.match(r"Klasse\s+(\d+)\s+bis", name)
        grenze = _zahl(wert) if m else None
        if m and grenze is not None:
            klassen.append((m.group(1), grenze))
    klassen.sort(key=lambda t: t[1])
    if not klassen:
        klassen = list(STANDARD_KLASSEN)

    p14a_roh = text("§14a-Außengeräte", "; ".join(STANDARD_P14A))
    p14a = [t.strip() for t in re.split(r"[;\n]", p14a_roh) if t.strip()]
    return {
        "w_qm_normal": zahl("W/m² normal", 60.0),
        "w_qm_stark": zahl("W/m² stark", 90.0),
        "hoehenfaktor": hoehenfaktor,
        "klassen": klassen,
        "leitung_inklusive_m": zahl("Leitung je Innengerät inklusive", 5.0),
        "meterposition": text("Meterposition Zusatzleitung", "KL017"),
        "standardserie": text("Standardserie", STANDARDSERIE),
        "max_innen_je_aussen": int(zahl("Max. Innengeräte je Außengerät", 5)),
        "max_aussen": int(zahl("Max. Außengeräte", 3)),
        "p14a_geraete": p14a,
        "gewerbe_verhalten": text("Gewerbe-Verhalten", "Hinweis"),
        "rollgeruest_vk": zahl("Rollgerüst VK", 499.0),
        "fehlende": fehlende,
    }


# --- Datenklassen ---------------------------------------------------------------

@dataclass
class Raum:
    nr: int
    name: str = ""
    flaeche: Optional[float] = None
    hoehe: str = ""                 # Antwort KR09 (Protokoll)
    hoehenfaktor: float = 1.0
    waermelast: str = ""            # Antwort KR10 (Protokoll)
    w_qm: float = 60.0
    kuehllast_kw: float = 0.0
    klasse: Optional[str] = None
    nennleistung_kw: Optional[float] = None
    artikel: list[str] = field(default_factory=list)   # Innengerät bei Multi-Split
    aussengeraet_nr: int = 1
    grund: str = ""

    @property
    def label(self) -> str:
        return f"Raum {self.nr} {self.name}".rstrip()

    def als_dict(self) -> dict:
        return {"nr": self.nr, "name": self.name, "flaeche": self.flaeche,
                "hoehe": self.hoehe, "hoehenfaktor": self.hoehenfaktor,
                "waermelast": self.waermelast, "w_qm": self.w_qm,
                "kuehllast_kw": self.kuehllast_kw, "klasse": self.klasse,
                "nennleistung_kw": self.nennleistung_kw, "artikel": list(self.artikel),
                "aussengeraet_nr": self.aussengeraet_nr, "grund": self.grund}


@dataclass
class Aussengeraet:
    nr: int
    raeume: list[int] = field(default_factory=list)    # Raum-Nummern
    typ: str = ""                                      # „single“ | „multi“
    kombination: str = ""                              # „9+9+9“ (Multi)
    artikel: list[str] = field(default_factory=list)   # KL-Refs (Set bzw. Außen + Innen)
    geraet: str = ""                                   # Bezeichnung laut Logik („CL5000M 79/3 E“)
    bezeichnung: str = ""                              # 1. Zeile des Artikels (aus der DB)
    p14a: bool = False
    grund: str = ""

    @property
    def anzeige(self) -> str:
        return self.bezeichnung or self.geraet or " + ".join(self.artikel)

    def als_dict(self) -> dict:
        return {"nr": self.nr, "raeume": list(self.raeume), "typ": self.typ,
                "kombination": self.kombination, "artikel": list(self.artikel),
                "geraet": self.geraet, "bezeichnung": self.bezeichnung,
                "p14a": self.p14a, "grund": self.grund}


@dataclass
class Auslegung:
    serie: str = ""
    raeume: list[Raum] = field(default_factory=list)
    aussengeraete: list[Aussengeraet] = field(default_factory=list)
    innengeraete_gesamt: int = 0
    aussengeraete_gesamt: int = 0
    montage_ref: str = ""
    ampeln: list[str] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)
    leitung_inklusive_m: float = 5.0

    @property
    def serie_kurz(self) -> str:
        return serie_kurz(self.serie)

    def als_dict(self) -> dict:
        return {"serie": self.serie, "raeume": [r.als_dict() for r in self.raeume],
                "aussengeraete": [g.als_dict() for g in self.aussengeraete],
                "innengeraete_gesamt": self.innengeraete_gesamt,
                "aussengeraete_gesamt": self.aussengeraete_gesamt,
                "montage_ref": self.montage_ref, "ampeln": list(self.ampeln),
                "hinweise": list(self.hinweise),
                "leitung_inklusive_m": self.leitung_inklusive_m}


# --- Hilfen ---------------------------------------------------------------------

def _de(zahl, stellen: int = 0) -> str:
    """Deutsche Zahl: 1,50 · 25,0 · 1.234,56."""
    if zahl is None:
        return ""
    text = f"{float(zahl):,.{stellen}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def serie_kurz(serie: str) -> str:
    return re.sub(r"\s*\(Standard\)", "", str(serie or "")).strip()


def _ganzzahl(wert, standard: int) -> int:
    zahl = engine.zahl_parsen(wert)
    return int(zahl) if zahl is not None else standard


def _innengeraete(n: int) -> str:
    return f"{n} Innengerät" if n == 1 else f"{n} Innengeräte"


def _aussengeraete(n: int) -> str:
    return f"{n} Außengerät" if n == 1 else f"{n} Außengeräte"


def kuehllast(flaeche: float, hoehenfaktor: float, w_qm: float) -> float:
    """Kühllast in kW = Fläche × Höhenfaktor × W/m² ÷ 1000, kaufmännisch auf
    2 Stellen gerundet (Decimal – keine Binärrundungsfehler: 30 × 1,1 × 90 = 2,97)."""
    wert = (Decimal(str(flaeche)) * Decimal(str(hoehenfaktor)) * Decimal(str(w_qm))
            / Decimal(1000))
    return float(wert.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def klasse_fuer(kw: float, klassen: list[tuple[str, float]]) -> Optional[str]:
    """Kleinste Klasse, deren Grenze ≥ Kühllast ist; None = über der größten Grenze."""
    for code, grenze in klassen:
        if kw <= grenze + 1e-9:
            return code
    return None


def _hoehenfaktor(antwort: str, p: dict) -> float:
    tabelle = p["hoehenfaktor"]
    if antwort in tabelle:
        return tabelle[antwort]
    ziel = _norm(antwort)
    for name, faktor in tabelle.items():
        if ziel and _norm(name) == ziel:
            return faktor
    return 1.0


def _typ_norm(typ: str) -> str:
    t = str(typ or "").lower()
    if "innen" in t:
        return "multi_innen"
    if "multi" in t:
        return "multi_aussen"
    if "single" in t:
        return "single"
    return t


def _paketzeilen(logik, serie: str) -> list:
    ziel = _norm(serie)
    return [z for z in (getattr(logik, "kl_paket", None) or [])
            if _norm(getattr(z, "serie", "")) == ziel]


def _paket_zeile(zeilen: list, typ: str, klasse: str):
    for z in zeilen:
        if _typ_norm(getattr(z, "typ", "")) != typ:
            continue
        codes = [t.strip() for t in re.split(r"[/|,]", str(getattr(z, "klasse", "")))]
        if klasse in codes:
            return z
    return None


def _nennleistung(zeile, p: dict, code: str) -> Optional[float]:
    """Nennleistung des Innengeräts: Zahl aus der Spalte „Kühllast je Raum“
    („bis 2,6 kW“), sonst die Klassengrenze."""
    m = re.search(r"(\d+(?:[.,]\d+)?)", str(getattr(zeile, "kuehllast", "") or ""))
    if m:
        wert = engine.zahl_parsen(m.group(1))
        if wert:
            return wert
    for c, grenze in p["klassen"]:
        if c == code:
            return grenze
    return None


def _kombis_fuer(logik, name: str, anzahl: int) -> set[str]:
    kombis = getattr(logik, "kl_kombis", None) or {}
    je_anzahl = kombis.get(name) or {}
    freigegeben = je_anzahl.get(anzahl)
    if freigegeben is None:
        freigegeben = je_anzahl.get(str(anzahl), set())
    return {"+".join(sorted(str(k).split("+"), key=_code_sort)) for k in freigegeben}


def _code_sort(code: str):
    zahl = engine.zahl_parsen(code)
    return (0, zahl) if zahl is not None else (1, code)


def _geraet_name(logik, ref: str, zeile, serie: str, multi: bool = True) -> str:
    """Bezeichnung des Außengeräts laut Blatt „Kombinationen KL“: über
    kl_kombi_artikel (KL-Nr. → Name); bei Multi-Außengeräten zusätzlich Fallback
    über die Klasse als ganzes Token („53/2“ → „CL5000M 53/2 E“, Serie 7000 →
    CL7000M). Single-Sets haben keine Kombinationszeile → leer."""
    kombi_artikel = getattr(logik, "kl_kombi_artikel", None) or {}
    for name, nr in kombi_artikel.items():
        if nr == ref:
            return name
    if not multi:
        return ""
    klasse = str(getattr(zeile, "klasse", "") or "").strip()
    if not klasse:
        return ""
    muster = re.compile(rf"(?<![\d/]){re.escape(klasse)}(?![\d/])")
    kombis = getattr(logik, "kl_kombis", None) or {}
    siebentausend = "7000" in str(serie)
    treffer = [name for name in kombis if muster.search(str(name))]
    for name in treffer:
        if ("7000" in str(name)) == siebentausend:
            return name
    return treffer[0] if treffer else ""


def _in_p14a(p: dict, *kandidaten: str) -> bool:
    for eintrag in p["p14a_geraete"]:
        ziel = _norm(eintrag)
        if ziel and any(ziel in _norm(k) for k in kandidaten if k):
            return True
    return False


def _ampel_aus_zeile(zeile, standard: str, **platzhalter) -> str:
    """Ampel-Grund einer Paketmatrix-Zeile „nicht im Sortiment“: Text aus der
    Bemerkung nach „→ AMPEL: “ (Lader: KlPaketZeile.grund) mit den Platzhaltern
    <Code>/<Serie>; ohne Bemerkung der wörtliche Standardtext G2/G3 (PLAN_V16
    Phase 114: „Text aus der Bemerkung nach „→ AMPEL: ““ – Prozesswissen in
    der Excel, Code nur Fallback)."""
    text = ""
    if zeile is not None:
        text = str(getattr(zeile, "ampel_grund", "") or getattr(zeile, "grund", "") or "").strip()
    if not text:
        return standard
    for name, wert in platzhalter.items():
        text = text.replace(f"<{name}>", str(wert))
    return text


# --- Auslegung ------------------------------------------------------------------

def _raum_auslegen(i: int, antworten: dict, p: dict) -> Raum:
    raum = Raum(nr=i, name=str(antworten.get(f"{ID_RAUMNAME}#{i}") or "").strip())
    raum.flaeche = engine.zahl_parsen(antworten.get(f"{ID_FLAECHE}#{i}"))
    raum.hoehe = str(antworten.get(f"{ID_HOEHE}#{i}") or "")
    raum.hoehenfaktor = _hoehenfaktor(raum.hoehe, p)
    raum.waermelast = str(antworten.get(f"{ID_WAERMELAST}#{i}") or "")
    raum.w_qm = (p["w_qm_stark"] if raum.waermelast.lower().startswith("stark")
                 else p["w_qm_normal"])
    raum.aussengeraet_nr = _ganzzahl(antworten.get(f"{ID_ZUORDNUNG}#{i}"), 1)
    if raum.flaeche is None or raum.flaeche <= 0:
        raum.flaeche = None
        raum.grund = MELDUNG_FLAECHE_FEHLT.format(nr=i)
        return raum
    raum.kuehllast_kw = kuehllast(raum.flaeche, raum.hoehenfaktor, raum.w_qm)
    raum.klasse = klasse_fuer(raum.kuehllast_kw, p["klassen"])
    if raum.klasse is None:
        raum.grund = G1.format(max=_de(p["klassen"][-1][1], 1), raum=raum.label,
                               kw=_de(raum.kuehllast_kw, 2))
    return raum


def _aussengeraet_auslegen(n: int, raeume: list[Raum], serie: str, logik, p: dict,
                           zeilen: list, namen: dict[str, str]) -> Aussengeraet:
    g = Aussengeraet(nr=n, raeume=[r.nr for r in raeume])
    if not raeume:
        g.grund = MELDUNG_AUSSEN_OHNE_RAUM.format(n=n)
        return g
    if len(raeume) == 1:
        g.typ = "single"
        raum = raeume[0]
        if raum.klasse is None:
            return g                      # Grund steht am Raum (G1 / Fläche fehlt)
        zeile = _paket_zeile(zeilen, "single", raum.klasse)
        if zeile is None or getattr(zeile, "nicht_im_sortiment", False):
            g.grund = _ampel_aus_zeile(zeile, G2.format(code=raum.klasse, serie=serie_kurz(serie)),
                                       Code=raum.klasse, Serie=serie_kurz(serie))
            return g
        g.artikel = list(getattr(zeile, "artikel", []) or [])
        raum.nennleistung_kw = _nennleistung(zeile, p, raum.klasse)
        g.geraet = (_geraet_name(logik, g.artikel[0], zeile, serie, multi=False)
                    if g.artikel else "")
        g.bezeichnung = namen.get(g.artikel[0], "") if g.artikel else ""
        g.p14a = _in_p14a(p, g.geraet, g.bezeichnung)
        return g

    g.typ = "multi"
    if len(raeume) > p["max_innen_je_aussen"]:
        g.grund = G5.format(max=p["max_innen_je_aussen"], n=n)
        return g
    multi_aussen = [z for z in zeilen if _typ_norm(getattr(z, "typ", "")) == "multi_aussen"]
    if not multi_aussen or all(getattr(z, "nicht_im_sortiment", False) for z in multi_aussen):
        g.grund = _ampel_aus_zeile(multi_aussen[0] if multi_aussen else None,
                                   G3.format(serie=serie_kurz(serie)), Serie=serie_kurz(serie))
        return g
    codes: list[str] = []
    vollstaendig = True
    for raum in raeume:
        if raum.klasse is None:
            vollstaendig = False
            continue
        zeile = _paket_zeile(zeilen, "multi_innen", raum.klasse)
        if zeile is None or getattr(zeile, "nicht_im_sortiment", False):
            grund = _ampel_aus_zeile(zeile, G2.format(code=raum.klasse, serie=serie_kurz(serie)),
                                     Code=raum.klasse, Serie=serie_kurz(serie))
            raum.grund = raum.grund or grund
            g.grund = g.grund or grund
            vollstaendig = False
            continue
        raum.artikel = list(getattr(zeile, "artikel", []) or [])
        raum.nennleistung_kw = _nennleistung(zeile, p, raum.klasse)
        codes.append(raum.klasse)
    if codes:
        g.kombination = "+".join(sorted(codes, key=_code_sort))
    if not vollstaendig:
        return g
    for zeile in multi_aussen:                      # Blattreihenfolge = klein → groß
        if getattr(zeile, "nicht_im_sortiment", False):
            continue
        refs = list(getattr(zeile, "artikel", []) or [])
        if not refs:
            continue
        name = _geraet_name(logik, refs[0], zeile, serie)
        if g.kombination in _kombis_fuer(logik, name, len(codes)):
            g.artikel = [refs[0]]
            g.geraet = name
            g.bezeichnung = namen.get(refs[0], "")
            g.p14a = _in_p14a(p, name, g.bezeichnung)
            return g
    g.grund = G4.format(codes=g.kombination, n=n)
    return g


def auslegen(logik, antworten: dict, artikel_namen: Optional[dict[str, str]] = None) -> Auslegung:
    """Rechenweg PLAN_V16 Phase 114 / Anhang A. `artikel_namen` (KL-Nr. → 1. Zeile
    des Artikels) füllt die Gerätebezeichnungen – ohne DB bleibt die Logik-
    Bezeichnung („CL5000M 79/3 E“)."""
    p = parameter(logik)
    namen = artikel_namen or {}
    serie = str(antworten.get(ID_SERIE) or "").strip() or p["standardserie"]
    a = Auslegung(serie=serie, leitung_inklusive_m=p["leitung_inklusive_m"])
    anzahl_aussen = max(1, _ganzzahl(antworten.get(ID_ANZAHL_AUSSEN), 1))
    anzahl_raeume = max(0, _ganzzahl(antworten.get(ID_ANZAHL_RAEUME), 0))
    for i in range(1, min(anzahl_raeume, MAX_RAEUME) + 1):
        a.raeume.append(_raum_auslegen(i, antworten, p))
    a.innengeraete_gesamt = len(a.raeume)
    a.aussengeraete_gesamt = anzahl_aussen
    zeilen = _paketzeilen(logik, serie)
    for n in range(1, anzahl_aussen + 1):
        a.aussengeraete.append(_aussengeraet_auslegen(
            n, [r for r in a.raeume if r.aussengeraet_nr == n], serie, logik, p,
            zeilen, namen))

    montage = getattr(logik, "kl_montage", None) or {}
    schluessel = (a.innengeraete_gesamt, anzahl_aussen)
    a.montage_ref = str(montage.get(schluessel) or montage.get(f"{schluessel[0]}/{schluessel[1]}")
                        or "")

    def merken(grund: str):
        if grund and grund not in a.ampeln:
            a.ampeln.append(grund)

    for raum in a.raeume:
        merken(raum.grund)
    for g in a.aussengeraete:
        merken(g.grund)
    if a.raeume and not a.montage_ref:
        merken(G6.format(innen=a.innengeraete_gesamt, aussen=anzahl_aussen))
    for raum in a.raeume:
        if str(antworten.get(f"{ID_ENTFERNUNG}#{raum.nr}") or "").lower().startswith("über"):
            merken(G7.format(raum=raum.label))
        if raum.aussengeraet_nr > anzahl_aussen:
            merken(MELDUNG_ZUORDNUNG_ZU_HOCH.format(nr=raum.nr, k=raum.aussengeraet_nr,
                                                    anzahl=anzahl_aussen))
    if (str(antworten.get(ID_STROM) or "") != "Ja"
            and str(antworten.get(ID_ZULEITUNG) or "").lower().startswith("über")):
        merken(G8)
    if (str(antworten.get(ID_GEBAEUDEART) or "") == "Gewerbe"
            and str(p["gewerbe_verhalten"]).strip().upper() == "AMPEL"):
        merken(GEWERBE_AMPEL)
    a.hinweise = fachliche_hinweise(logik, antworten)
    return a


# --- Texte ------------------------------------------------------------------------

def auslegungs_text(a: Auslegung) -> str:
    """Beschreibung der Auslegungszeile (Block 3) und Protokoll – wörtlich PLAN_V16."""
    if not a.raeume:
        return ""
    zeilen = [f"Auslegung Klimaanlage – Serie Bosch {a.serie_kurz}"]
    for r in a.raeume:
        if r.flaeche is None:
            zeilen.append(f"Raum {r.nr} „{r.name}“: Raumfläche fehlt")
            continue
        kopf = (f"Raum {r.nr} „{r.name}“: {_de(r.flaeche, 1)} m² × {_de(r.hoehenfaktor, 1)} × "
                f"{_de(r.w_qm, 0)} W/m² = {_de(r.kuehllast_kw, 2)} kW")
        if r.klasse is None:
            zeilen.append(f"{kopf} → über der größten Innengeräte-Klasse, Außengerät "
                          f"{r.aussengeraet_nr}")
            continue
        nenn = f"{_de(r.nennleistung_kw, 1)} kW" if r.nennleistung_kw else f"Klasse {r.klasse}"
        zeilen.append(f"{kopf} → Innengerät {nenn} (Klasse {r.klasse}), Außengerät "
                      f"{r.aussengeraet_nr}")
    for g in a.aussengeraete:
        if not g.raeume:
            continue
        art = "Single-Split" if g.typ == "single" else f"Multi-Split, Kombination {g.kombination}"
        geraet = g.anzeige or ("nicht ermittelt" if g.grund else "")
        zeilen.append(f"Außengerät {g.nr}: {geraet}, {art}, {_innengeraete(len(g.raeume))}")
    zeilen.append(f"Montage: {_innengeraete(a.innengeraete_gesamt)} / "
                  f"{_aussengeraete(a.aussengeraete_gesamt)} (Pauschale). Leitungslänge bis "
                  f"{_de(a.leitung_inklusive_m, 0)} m je Innengerät enthalten.")
    zeilen.append("Auslegung nach Raumfläche; verbindliche Festlegung in der technischen "
                  "Feinplanung vor Ort.")
    return "\n".join(zeilen)


# --- Ampel / Hinweise / Validierung ------------------------------------------------

def ampel_gruende(logik, antworten: dict) -> list[str]:
    """Berechnete AMPEL-Gründe G1–G8 (+ Gewerbe-AMPEL laut Parameter und die
    Validierungsmeldungen) – erst bei vollständigem Bogen (wie PV)."""
    if engine.naechste_frage(logik, antworten) is not None:
        return []
    return list(auslegen(logik, antworten).ampeln)


def _raum_nummern(antworten: dict) -> list[int]:
    anzahl = _ganzzahl(antworten.get(ID_ANZAHL_RAEUME), 0)
    if anzahl > 0:
        return list(range(1, min(anzahl, MAX_RAEUME) + 1))
    nummern = set()
    for key in antworten:
        m = re.fullmatch(r"KR\d{2}#(\d+)", str(key))
        if m:
            nummern.add(int(m.group(1)))
    return sorted(nummern)


def _hinweise_aus_aktionen(logik, antworten: dict) -> Optional[list[tuple[str, str]]]:
    """Fachliche Hinweise aus den Zeilen „Hinweis: <Text>“ des Blatts „Aktionen KL“
    (Lader: typ „hinweis“, Text in ampel_grund) in Blattreihenfolge: die Antwort
    der Frage bzw. ihrer Raum-Klone trifft die Zeile (konfigurator._teil_index),
    die Zusatzbedingung ist erfüllt, Platzhalter <Nr>/<Name> je Raum-Klon
    (konfigurator._klon_platzhalter). Liefert [(Frage-ID, Text)]; None, wenn die
    Logik keine Hinweiszeilen mit Text kennt – dann gelten die Texte im Code
    (Prozesswissen in der Excel, Code nur Fallback; Regel 3 des Briefings)."""
    aktionen = [a for a in _aktionen(logik)
                if getattr(a, "typ", "") == "hinweis"
                and str(getattr(a, "ampel_grund", "") or "").strip()]
    if not aktionen or not getattr(logik, "fragen", None):
        return None
    sichtbar: dict[str, list] = {}
    for frage in engine.sichtbare_fragen(logik, antworten):
        if frage.id in antworten:
            sichtbar.setdefault(frage.id.split("#")[0], []).append(frage)
    ergebnis: list[tuple[str, str]] = []
    for aktion in aktionen:
        for frage in sichtbar.get(aktion.frage, []):
            wert = antworten.get(frage.id)
            if isinstance(wert, (dict, list)) or frage.typ in FREITEXT_TYPEN:
                continue
            if engine._teil_index(frage, aktion.antwort, wert, antworten, logik.fragen) is None:
                continue
            if not _zusatz_ok(aktion, antworten, logik):
                continue
            ergebnis.append((aktion.frage,
                             engine._klon_platzhalter(aktion.ampel_grund.strip(), frage.id,
                                                      antworten)))
    return ergebnis


def fachliche_hinweise(logik, antworten: dict) -> list[str]:
    """Fachliche Hinweise am Vorgang (keine Ampel), Texte wörtlich PLAN_V16:
    aus den Zeilen „Hinweis: <Text>“ des Blatts „Aktionen KL“ (Blattreihenfolge),
    ohne solche Zeilen aus den Konstanten im Code; KO01 = Gewerbe wird bei
    Parameter „Gewerbe-Verhalten“ = AMPEL zur Ampel statt zum Hinweis, „Mehr als
    12 Räume“ rechnet der Code (Obergrenze der Raum-Klone). Funktioniert mit
    Roh-Antworten und mit den Anzeige-Strings des Protokolls."""
    p = parameter(logik)
    hinweise: list[str] = []

    def merken(text: str):
        if text not in hinweise:
            hinweise.append(text)

    gewerbe_ampel = str(p["gewerbe_verhalten"]).strip().upper() == "AMPEL"
    aus_excel = _hinweise_aus_aktionen(logik, antworten) if logik is not None else None
    if aus_excel is not None:
        for frage_id, text in aus_excel:
            if frage_id == ID_GEBAEUDEART and gewerbe_ampel:
                continue
            merken(text)
        if _ganzzahl(antworten.get(ID_ANZAHL_RAEUME), 0) > MAX_RAEUME:
            merken(HINWEIS_RAEUME)
        return hinweise

    if str(antworten.get(ID_EIGENTUEMER) or "").startswith("Nein, Zustimmung noch nicht"):
        merken(HINWEIS_EIGENTUEMER)
    if str(antworten.get(ID_GEBAEUDEART) or "") == "Gewerbe" and not gewerbe_ampel:
        merken(HINWEIS_GEWERBE)
    for i in _raum_nummern(antworten):
        label = f"Raum {i} {str(antworten.get(f'{ID_RAUMNAME}#{i}') or '').strip()}".rstrip()
        if str(antworten.get(f"{ID_MONTAGEORT_INNEN}#{i}") or "") == "Innenwand":
            merken(HINWEIS_INNENWAND.format(raum=label))
        if str(antworten.get(f"{ID_HAUPTZWECK}#{i}") or "").startswith("regelmäßig heizen"):
            merken(HINWEIS_HEIZEN.format(raum=label))
    ka01 = str(antworten.get(ID_MONTAGEORT_AUSSEN) or "")
    if "Flachdach" in ka01:
        merken(HINWEIS_FLACHDACH)
    if "unklar" in ka01.lower():
        merken(HINWEIS_UNKLAR)
    if (str(antworten.get(ID_MONTAGEHOEHE) or "").lower().startswith("über")
            and str(antworten.get(ID_ERREICHBARKEIT) or "").lower().startswith("vom boden")):
        merken(HINWEIS_HOEHE)
    if str(antworten.get(ID_STROM) or "") == "Unklar":
        merken(HINWEIS_STROM)
    if _ganzzahl(antworten.get(ID_ANZAHL_RAEUME), 0) > MAX_RAEUME:
        merken(HINWEIS_RAEUME)
    return hinweise


def validierung(logik, antworten: dict) -> list[str]:
    """Meldungen für das Absenden (blockieren): jedes Außengerät 1 … KO04 hat
    mindestens einen Raum; Raumfläche KR08 > 0 je Raum."""
    a = auslegen(logik, antworten)
    meldungen: list[str] = []
    for g in a.aussengeraete:
        if not g.raeume:
            meldungen.append(MELDUNG_AUSSEN_OHNE_RAUM.format(n=g.nr))
    for r in a.raeume:
        if r.flaeche is None:
            meldungen.append(MELDUNG_FLAECHE_FEHLT.format(nr=r.nr))
    for r in a.raeume:
        if r.aussengeraet_nr > a.aussengeraete_gesamt:
            meldungen.append(MELDUNG_ZUORDNUNG_ZU_HOCH.format(
                nr=r.nr, k=r.aussengeraet_nr, anzahl=a.aussengeraete_gesamt))
    return meldungen


# --- Positionen -----------------------------------------------------------------

@dataclass
class KlArtikel:
    ref: str
    menge: float
    ep: bool
    quelle: str          # Frage-ID (ggf. Klon), „grundpaket“, „montage“, „aussengeraet<n>“,
                         # „innengeraet“, „§14a“
    reihe: int = 0       # Außengerät-/Raum-Reihenfolge innerhalb gleicher Textposition


def _aktionen(logik) -> list:
    return list(getattr(logik, "kl_aktionen", None) or getattr(logik, "aktionen", None) or [])


def _zusatz_ok(aktion, antworten: dict, logik) -> bool:
    b = getattr(aktion, "zusatz_bedingung", None)
    if b is None:
        return True
    dummy = engine.Frage("_", 0, "", "Auswahl", [], b, "")
    return engine.ist_sichtbar(dummy, antworten, logik.fragen, logik)


def _als_ep(aktion) -> bool:
    return bool(re.search(r"\bals EP\b", str(getattr(aktion, "aktion_roh", "") or "")))


def _menge(ref, aktion, a: Auslegung) -> float:
    """Mengenwörter der KL-Aktionen: „× 5“ · „× Innengeräte“ (= Σ Räume) ·
    „× Außengeräte“ (= KO04) · „… je Außengerät“ (× KO04, steht am Zeilenende
    und landet beim Parser nur in der letzten Referenz) · „je Raum“ ergibt sich
    aus den Raum-Klonen (Aktion greift je Klon, Mengen werden addiert)."""
    roh = re.sub(r"\s*als EP.*$", "", str(getattr(ref, "menge", "") or "1")).strip()
    roh_klein = roh.lower()
    zeile_klein = str(getattr(aktion, "aktion_roh", "") or "").lower()
    m = re.match(r"\s*(\d+(?:[.,]\d+)?)", roh)
    basis = engine.zahl_parsen(m.group(1)) if m else None
    if basis is None:
        basis = 1.0
    if "innengerät" in roh_klein or "innengeraet" in roh_klein:
        basis *= a.innengeraete_gesamt
    elif ("außengerät" in roh_klein or "aussengerät" in roh_klein
            or "je außengerät" in zeile_klein):
        basis *= a.aussengeraete_gesamt
    return float(basis)


def _p14a_ref(aktionen: list) -> str:
    for aktion in aktionen:
        if str(getattr(aktion, "frage", "")).startswith("§14a"):
            for ref in getattr(aktion, "artikel", []) or []:
                return ref.ref
    return P14A_REF_STANDARD


def artikel_ermitteln(logik, antworten: dict, a: Auslegung) -> list[KlArtikel]:
    """Gewählte Artikel: Aktionen KL (je Frage bzw. je Raum-Klon), Grundpaket,
    Außengeräte/Sets und Innengeräte der Auslegung, Montagepauschale, §14a.
    Aktionen vom Typ „hinweis“ erzeugen keine Position."""
    aktionen = _aktionen(logik)
    gewaehlt: list[KlArtikel] = []
    for frage in engine.sichtbare_fragen(logik, antworten):
        if frage.id not in antworten:
            continue
        wert = antworten[frage.id]
        if isinstance(wert, (dict, list)) or frage.typ in FREITEXT_TYPEN:
            continue
        basis_id = frage.id.split("#")[0]
        for aktion in aktionen:
            if aktion.frage != basis_id or aktion.typ != "normal":
                continue
            index = engine._teil_index(frage, aktion.antwort, wert, antworten, logik.fragen)
            if index is None or not _zusatz_ok(aktion, antworten, logik):
                continue
            for ref in engine.refs_fuer_treffer(aktion, index):
                menge = _menge(ref, aktion, a)
                if menge > 0:
                    gewaehlt.append(KlArtikel(ref.ref, menge, ref.ep or _als_ep(aktion),
                                              frage.id))
            break
    for aktion in aktionen:
        if aktion.typ != "normal" or aktion.frage != "Grundpaket":
            continue
        if not _zusatz_ok(aktion, antworten, logik):
            continue
        for ref in aktion.artikel:
            menge = _menge(ref, aktion, a)
            if menge > 0:
                gewaehlt.append(KlArtikel(ref.ref, menge, ref.ep or _als_ep(aktion),
                                          "grundpaket"))
    for g in a.aussengeraete:
        # 1. Referenz = Außengerät/Set („aussengeraet<n>“, Block 3 in Außengerät-
        # Reihenfolge), weitere Referenzen der Paketmatrix-Zelle (7000i-Single:
        # „KL043 … + KL041“) = Innengerät, sortiert wie die übrigen Innengeräte
        for lauf, ref in enumerate(g.artikel):
            quelle = f"aussengeraet{g.nr}" if lauf == 0 else f"aussengeraet{g.nr}/innen"
            gewaehlt.append(KlArtikel(ref, 1.0, False, quelle, g.nr))
    for r in a.raeume:
        for ref in r.artikel:
            gewaehlt.append(KlArtikel(ref, 1.0, False, "innengeraet", r.aussengeraet_nr))
    if a.montage_ref:
        gewaehlt.append(KlArtikel(a.montage_ref, 1.0, False, "montage"))
    ref14 = _p14a_ref(aktionen)
    for g in a.aussengeraete:
        if g.p14a:
            gewaehlt.append(KlArtikel(ref14, 1.0, False, "§14a", g.nr))
    return gewaehlt


def _index_im_inhalt(inhalt: str, ref: str) -> int:
    m = re.search(rf"\b{re.escape(ref)}\b", inhalt or "")
    return m.start() if m else -1


def _bloecke(logik) -> list:
    bloecke = getattr(logik, "kl_bloecke", None) or getattr(logik, "bloecke", None) or []
    return sorted((b for b in bloecke if "Summenblock" not in str(b.ueberschrift)),
                  key=lambda b: b.nr)


def _gruppen_block(bloecke: list):
    """Block 3 „Klimaanlage Bosch“ = erster Block mit echter Überschrift,
    sonst der letzte Block."""
    for b in bloecke:
        if b.ueberschrift and not b.ueberschrift.startswith("(ohne"):
            return b
    return bloecke[-1] if bloecke else None


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


def _namen_aus(artikel_map: dict) -> dict[str, str]:
    """KL-Nr. → „Bezeichnung der 1. Zeile des Artikels“ (PLAN_V16 Phase 114).
    Der Klima-Import (app/import_klima.py) legt die erste Textzeile als
    `bezeichnung` ab und den Rest als `beschreibung` – anders als der PV-Import
    (dort ist `bezeichnung` leer und die 1. Zeile steht in `beschreibung`), daher
    zuerst die Bezeichnung, sonst die erste Zeile der Beschreibung."""
    from app.import_pv import erste_zeile
    namen = {}
    for nr, stamm in artikel_map.items():
        if str(nr).startswith("KL"):
            namen[nr] = (str(getattr(stamm, "bezeichnung", "") or "").strip()
                         or erste_zeile(getattr(stamm, "beschreibung", "") or ""))
    return namen


def positionen_bauen(logik, antworten: dict, artikel_map: dict) -> list[dict]:
    """Positions-Snapshots ohne DB-Zugriff (artikel_map: pos_nr → Artikel-Stamm):
    Blockzuordnung über die KL-Nummern im Inhalt des Blatts „Angebotsaufbau KL“,
    gleiche Artikel im selben Block addiert, EP aus der Aktion, Gruppe
    „Klimaanlage Bosch“ aus Block 3, Auslegungszeile als letzte Zeile von Block 3."""
    a = auslegen(logik, antworten, _namen_aus(artikel_map))
    gewaehlt = artikel_ermitteln(logik, antworten, a)
    bloecke = _bloecke(logik)
    gruppe = _gruppen_block(bloecke)
    erster_nr = bloecke[0].nr if bloecke else 1
    gruppe_nr = gruppe.nr if gruppe is not None else erster_nr
    zugeordnet: list[list] = []
    for lauf, gw in enumerate(gewaehlt):
        platz = None
        for block in bloecke:
            index = _index_im_inhalt(block.inhalt_roh, gw.ref)
            if index >= 0:
                platz = (block.nr, index)
                break
        if platz is None:
            # nicht im Inhalt genannt: Geräte/Gateway/Garantie in die Gruppe, Rest Block 1
            if gw.quelle.startswith(("aussengeraet", "innengeraet", "grundpaket")):
                platz = (gruppe_nr, 9999)
            else:
                platz = (erster_nr, 9999)
        zugeordnet.append([platz[0], platz[1], gw.reihe, lauf, gw])
    # Außengeräte/Sets in Außengerät-Reihenfolge (PLAN_V16 Phase 114): alle Geräte
    # eines Blocks teilen sich die Textposition des zuerst im Blatt genannten
    # Geräts, danach entscheidet die Außengerät-Nummer (reihe) – sonst stünde das
    # Single-Set KL034 von Außengerät 2 vor dem Multi-Außengerät KL037 von Außengerät 1
    anker: dict[int, int] = {}
    for eintrag in zugeordnet:
        if re.fullmatch(r"aussengeraet\d+", eintrag[4].quelle):
            anker[eintrag[0]] = min(anker.get(eintrag[0], eintrag[1]), eintrag[1])
    for eintrag in zugeordnet:
        if re.fullmatch(r"aussengeraet\d+", eintrag[4].quelle):
            eintrag[1] = anker[eintrag[0]]
    zugeordnet.sort(key=lambda t: tuple(t[:4]))
    bloecke_map = {b.nr: b for b in bloecke}
    positionen: list[dict] = []
    gesehen: dict[tuple[int, str], dict] = {}
    for block_nr, _i, _r, _l, gw in zugeordnet:
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
    text = auslegungs_text(a)
    if text:
        in_gruppe = [i for i, x in enumerate(positionen) if x["block_nr"] == gruppe_nr]
        stelle = (in_gruppe[-1] + 1) if in_gruppe else len(positionen)
        positionen.insert(stelle, {
            "block_nr": gruppe_nr, "gruppe": ueberschrift(gruppe),
            "pos_nr": "", "bezeichnung": AUSLEGUNGSZEILE,
            "beschreibung": text, "menge": 1.0, "einheit": "psl.",
            "e_preis_cent": 0, "ep_flag": False, "ek_cent": 0, "guid": ""})
    for sort, x in enumerate(positionen, 1):
        x["sort"] = sort
    return positionen


def artikel_namen(session) -> dict[str, str]:
    """KL-Nr. → erste Zeile des Artikeltexts (Gerätebezeichnung in Auslegungszeile/
    kl_json)."""
    from app.models import Artikel
    artikel_map = {x.pos_nr: x for x in
                   session.query(Artikel).filter(Artikel.aktiv.is_(True),
                                                 Artikel.pos_nr.like("KL%"))}
    return _namen_aus(artikel_map)


def positionen_zusammenstellen(logik, antworten: dict, session,
                               erfassung=None) -> list[dict]:
    """Positions-Snapshots des Klima-Angebots in Blockreihenfolge (Blatt
    „Angebotsaufbau KL“) – Artikelstamm aus der Datenbank."""
    from app.models import Artikel
    artikel_map = {x.pos_nr: x for x in
                   session.query(Artikel).filter(Artikel.aktiv.is_(True)) if x.pos_nr}
    return positionen_bauen(logik, antworten, artikel_map)


# --- Protokoll ------------------------------------------------------------------

def protokoll_zeilen(logik, antworten: dict) -> list[dict]:
    """Seite „Auslegung“ des Konfigurationsprotokolls: je Raum Fläche/Höhe/
    Wärmelast/Kühllast/Klasse/Außengerät, je Außengerät Gerät + Kombination,
    Montage. Leer, solange der Bogen unvollständig ist (wie PV)."""
    if engine.naechste_frage(logik, antworten) is not None:
        return []
    a = auslegen(logik, antworten)
    if not a.raeume:
        return []

    def zeile(frage: str, antwort: str, grund: str = "") -> dict:
        return {"frage_id": "", "seite": "Auslegung", "frage": frage,
                "antwort": antwort, "ampel_grund": grund}

    zeilen = [zeile("Auslegung Klimaanlage", f"Serie Bosch {a.serie_kurz}")]
    for r in a.raeume:
        if r.flaeche is None:
            zeilen.append(zeile(r.label, "Raumfläche fehlt", r.grund))
            continue
        teile = [f"Fläche {_de(r.flaeche, 1)} m²",
                 f"Deckenhöhe {r.hoehe or '–'} (Faktor {_de(r.hoehenfaktor, 1)})",
                 f"Wärmelast {r.waermelast.split(' (')[0] if r.waermelast else '–'} "
                 f"({_de(r.w_qm, 0)} W/m²)",
                 f"Kühllast {_de(r.kuehllast_kw, 2)} kW"]
        if r.klasse is not None:
            nenn = f" (Innengerät {_de(r.nennleistung_kw, 1)} kW)" if r.nennleistung_kw else ""
            teile.append(f"Klasse {r.klasse}{nenn}")
        else:
            teile.append("Klasse: über der größten Klasse")
        teile.append(f"Außengerät {r.aussengeraet_nr}")
        zeilen.append(zeile(r.label, " · ".join(teile), r.grund))
    for g in a.aussengeraete:
        if not g.raeume:
            zeilen.append(zeile(f"Außengerät {g.nr}", "kein Raum zugeordnet", g.grund))
            continue
        art = "Single-Split" if g.typ == "single" else f"Multi-Split, Kombination {g.kombination}"
        raeume = ", ".join(str(n) for n in g.raeume)
        zeilen.append(zeile(f"Außengerät {g.nr}",
                            f"{g.anzeige or 'nicht ermittelt'} · {art} · "
                            f"{_innengeraete(len(g.raeume))} (Raum {raeume})", g.grund))
    montage = (f"{_innengeraete(a.innengeraete_gesamt)} / "
               f"{_aussengeraete(a.aussengeraete_gesamt)} – "
               + (f"Pauschale {a.montage_ref}" if a.montage_ref else "nicht hinterlegt"))
    zeilen.append(zeile("Montage", montage,
                        "" if a.montage_ref else G6.format(innen=a.innengeraete_gesamt,
                                                           aussen=a.aussengeraete_gesamt)))
    return zeilen
