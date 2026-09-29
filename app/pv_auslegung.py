# PV-Auslegung (v13-PV, PLAN_V13 Phasen 76/77): aus dem PV-Erfassungsbogen
# werden Modulanzahl, Anlagenleistung, Strings und die Sigenergy-WR/Speicher-
# Kombination bestimmt; daraus entstehen die Angebotspositionen laut Blatt
# „Aktionen PV“ und die Reihenfolge laut „Angebotsaufbau PV“. Alle Rechen-
# werte stehen im Blatt „PV-Parameter“ der Logik-Excel.
#
# Dachbelegungstool (Zulieferung): liefert später Modulanzahl je Dachseite
# und Quer-Anteil. Bis dahin gelten die Interim-Felder PD12/PD13; das Tool
# schreibt künftig einfach dieselben Antwort-Schlüssel (dachbelegung_setzen).

import math
import re
from dataclasses import dataclass, field
from typing import Optional

from app import konfigurator as engine
from app.logik import ArtikelRef, Logik, _pv_zahl

# Fragen-IDs des PV-Bogens (Blatt „Fragen PV“)
ID_BELEGUNGSART = "PB01"     # Maximalbelegung | Bedarfsorientierte Belegung
ID_STROM_HAUSHALT = "PO06"
ID_STROM_WP = "PO07"         # Zahl oder „Aus WP-Erfassung ermitteln“
ID_WALLBOX = "PO08"
ID_STROM_WALLBOX = "PO09"
ID_DACHART = "PD01"
ID_GERUEST = "PD03"
ID_OPTIMIERER = "PD06"
ID_MEHRERE_SEITEN = "PD07"
ID_FLACHDACH_BELEGUNG = "PD11"
ID_MAX_MODULE = "PD12"       # Interim bis Dachbelegungstool
ID_QUER = "PD13"             # Interim: davon quer verlegte Module (Satteldach)
ID_SPEICHER = "PA10"
ID_HEMS = "PA11"
FRIONDO_PV = ("PA11", "PA12", "PA13")

MAXIMAL = "Maximalbelegung"
BEDARF = "Bedarfsorientierte Belegung"
AUS_WP = "Aus WP-Erfassung ermitteln"
# abgeleiteter WP-Stromverbrauch (kein Bogen-Feld, wird beim Speichern bzw.
# vor dem Erzeugen aus der WP-Erfassung des Vorgangs gesetzt)
SCHLUESSEL_WP_ABGELEITET = "_PO07_aus_wp"

KOMBI_MUSTER = re.compile(
    r"Sigenergy Hybrid System\s+(TP2|SigenStor)\s+(\d+)\s*/\s*(\d+)", re.I)


# --- Parameter --------------------------------------------------------------

def parameter(logik: Logik) -> dict:
    p = {name: wert for name, (wert, _b) in logik.pv_parameter.items()}

    def zahl(name, standard):
        wert = _pv_zahl(p.get(name))
        return standard if wert is None else wert

    def stufen(name, standard):
        roh = p.get(name) or ""
        werte = [_pv_zahl(t) for t in re.split(r";|,\s+", roh) if t.strip()]
        werte = [w for w in werte if w is not None]
        return sorted(werte) or standard

    return {
        "modul_kwp": zahl("Modulleistung", 0.455),
        "modul_voc": zahl("Modul-Leerlaufspannung", 36.19),
        "max_spannung": zahl("Max. Stringspannung", 1000),
        "faktor_hh": zahl("Faktor Haushalt", 1.3),
        "faktor_wp": zahl("Faktor Wärmepumpe", 1.5),
        "ertrag": zahl("Spezifischer Ertrag", 960),
        "jaz": zahl("JAZ-Umrechnung Gas/Öl → Strom", 3.5),
        "wr_faktor": zahl("WR-Faktor (kWp ÷ WR-Leistung)", 1.2),
        "stufen_tp2": stufen("WR-Stufen TP2", [6, 8, 10, 12]),
        "stufen_sigenstor": stufen("WR-Stufen SigenStor", [15, 17, 20, 25, 30]),
        "max_wr": zahl("Max. WR-Leistung", 30),
        "ev_pv": zahl("Eigenverbrauchsquote PV", 32),
        "ev_speicher": zahl("Eigenverbrauch Zuschlag Speicher", 33),
        "ev_hems": zahl("Eigenverbrauch Zuschlag HEMS", 10),
        "strompreis": zahl("Strompreis", 0.32),
        "verguetung": zahl("Einspeisevergütung", 0.078),
        "modul_hinweis": p.get("Hinweis nach Modulposition", ""),
    }


# --- WR/Speicher-Kombinationen aus dem Artikelstamm -------------------------

def kombis_laden(session) -> list[tuple[str, float, float, str]]:
    """(Serie, WR-kW, Speicher-Stufe, PV-Nr.) je aktivem Sigenergy-Hybrid-
    System; bei Dubletten (Musterangebot) gewinnt die kleinste PV-Nummer."""
    from app.import_pv import erste_zeile
    from app.models import Artikel, QUELLE_PV
    kombis: dict[tuple[str, float, float], str] = {}
    for a in (session.query(Artikel)
              .filter(Artikel.quelle == QUELLE_PV, Artikel.aktiv.is_(True))
              .order_by(Artikel.pos_nr)):
        m = KOMBI_MUSTER.search(erste_zeile(a.beschreibung))
        if not m:
            continue
        schluessel = ("TP2" if m.group(1).upper() == "TP2" else "SigenStor",
                      float(m.group(2)), float(m.group(3)))
        kombis.setdefault(schluessel, a.pos_nr)
    return [(s, wr, bat, nr) for (s, wr, bat), nr in sorted(kombis.items())]


# --- Auslegung ----------------------------------------------------------------

@dataclass
class Auslegung:
    belegungsart: str = ""
    max_module: Optional[int] = None
    quer: int = 0
    module: int = 0
    kwp: float = 0.0
    bedarf_kwh: Optional[float] = None
    bedarf_kwp: Optional[float] = None
    bedarf_module: Optional[int] = None
    herleitung: str = ""
    gedeckelt: bool = False
    seiten: int = 1
    max_je_string: int = 27
    strings: int = 0
    wr_bedarf_kw: float = 0.0
    wr_kw: Optional[float] = None
    serie: str = ""
    speicher_wunsch: Optional[float] = None
    speicher_stufe: Optional[float] = None
    kombi_nr: str = ""
    gruende: list[str] = field(default_factory=list)

    @property
    def kombi_text(self) -> str:
        if self.wr_kw is None or self.speicher_stufe is None:
            return ""
        return (f"{'Hybrid System TP2' if self.serie == 'TP2' else 'SigenStor'} "
                f"{int(self.wr_kw):02d}/{int(self.speicher_stufe):02d}")

    def als_dict(self) -> dict:
        return {"belegungsart": self.belegungsart, "module": self.module,
                "kwp": round(self.kwp, 3), "strings": self.strings,
                "quer": self.quer, "max_module": self.max_module,
                "wr_kw": self.wr_kw, "speicher_stufe": self.speicher_stufe,
                "kombi": self.kombi_text, "kombi_nr": self.kombi_nr,
                "gedeckelt": self.gedeckelt, "herleitung": self.herleitung,
                "bedarf_kwh": self.bedarf_kwh}


def _de(zahl: float, stellen: int = 0) -> str:
    text = f"{zahl:,.{stellen}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def wp_strom(antworten: dict, p: dict) -> tuple[Optional[float], str]:
    """Stromverbrauch der Wärmepumpe: Direktangabe hat Vorrang, sonst der aus
    der WP-Erfassung abgeleitete Wert (Gas-/Ölverbrauch ÷ JAZ)."""
    roh = antworten.get(ID_STROM_WP)
    if roh == AUS_WP:
        abgeleitet = antworten.get(SCHLUESSEL_WP_ABGELEITET)
        if isinstance(abgeleitet, dict) and abgeleitet.get("strom_kwh") is not None:
            return (float(abgeleitet["strom_kwh"]),
                    f"aus WP-Erfassung: {_de(abgeleitet['verbrauch_kwh'])} kWh ÷ "
                    f"{_de(p['jaz'], 1)}")
        return None, "WP-Erfassung ohne Verbrauch"
    wert = engine.zahl_parsen(roh)
    return (wert or 0.0), ""


def auslegen(logik: Logik, antworten: dict) -> Auslegung:
    p = parameter(logik)
    a = Auslegung(belegungsart=str(antworten.get(ID_BELEGUNGSART) or ""))
    max_roh = engine.zahl_parsen(antworten.get(ID_MAX_MODULE))
    a.max_module = int(max_roh) if max_roh else None
    if str(antworten.get(ID_DACHART) or "") == "Satteldach":
        a.quer = int(engine.zahl_parsen(antworten.get(ID_QUER)) or 0)

    if a.belegungsart == BEDARF:
        hh = engine.zahl_parsen(antworten.get(ID_STROM_HAUSHALT)) or 0.0
        wp, wp_info = wp_strom(antworten, p)
        wb = 0.0
        if antworten.get(ID_WALLBOX) == "Ja":
            wb = engine.zahl_parsen(antworten.get(ID_STROM_WALLBOX)) or 0.0
        if wp is None:
            a.gruende.append("WP-Stromverbrauch nicht ermittelbar (keine WP-Erfassung "
                             "mit Verbrauch im Vorgang)")
            wp = 0.0
        a.bedarf_kwh = hh * p["faktor_hh"] + wp * p["faktor_wp"] + wb
        a.bedarf_kwp = a.bedarf_kwh / p["ertrag"]
        a.bedarf_module = math.ceil(round(a.bedarf_kwp / p["modul_kwp"], 6))
        teile = [f"Haushalt {_de(hh)} kWh × {_de(p['faktor_hh'], 1)}"]
        if wp:
            teile.append(f"WP {_de(wp)} kWh × {_de(p['faktor_wp'], 1)}"
                         + (f" ({wp_info})" if wp_info else ""))
        if wb:
            teile.append(f"Wallbox {_de(wb)} kWh")
        a.herleitung = (f"Bedarf = {' + '.join(teile)} = {_de(a.bedarf_kwh)} kWh; "
                        f"÷ {_de(p['ertrag'])} kWh/kWp = {_de(a.bedarf_kwp, 2)} kWp; "
                        f"÷ {_de(p['modul_kwp'], 3)} kWp = {a.bedarf_module} Module")
        a.module = a.bedarf_module
        if a.max_module is not None and a.module > a.max_module:
            a.module = a.max_module
            a.gedeckelt = True
            a.herleitung += (f" – gedeckelt auf die Maximalbelegung von "
                             f"{a.max_module} Modulen")
    else:
        a.module = a.max_module or 0
        if a.belegungsart == MAXIMAL and a.max_module:
            a.herleitung = f"Maximalbelegung lt. Dachbelegung: {a.max_module} Module"
    if not a.max_module:
        a.gruende.append("Maximale Modulanzahl fehlt (Dachbelegung)")
    a.quer = min(a.quer, a.module)
    a.kwp = a.module * p["modul_kwp"]

    # Strings: max. Module je String aus Spannungsgrenze ÷ Leerlaufspannung
    a.max_je_string = max(1, int(p["max_spannung"] // p["modul_voc"]))
    a.seiten = 2 if antworten.get(ID_MEHRERE_SEITEN) == "Ja" else 1
    a.strings = (max(a.seiten, math.ceil(a.module / a.max_je_string))
                 if a.module else 0)

    # Wechselrichter/Speicher (Sigenergy)
    a.wr_bedarf_kw = a.kwp / p["wr_faktor"] if a.kwp else 0.0
    a.speicher_wunsch = engine.zahl_parsen(antworten.get(ID_SPEICHER))
    if a.module:
        _wr_waehlen(a, p, logik.pv_kombis)
    return a


def _wr_waehlen(a: Auslegung, p: dict, kombis) -> None:
    if a.wr_bedarf_kw > p["max_wr"]:
        a.gruende.append(f"WR-Bedarf über {_de(p['max_wr'])} kW")
        return
    stufen = ([("TP2", s) for s in p["stufen_tp2"]]
              + [("SigenStor", s) for s in p["stufen_sigenstor"]])
    passend = [(serie, s) for serie, s in stufen if s >= a.wr_bedarf_kw - 1e-9]
    if not passend:
        a.gruende.append(f"WR-Bedarf über {_de(p['max_wr'])} kW")
        return
    a.serie, a.wr_kw = min(passend, key=lambda t: t[1])
    if not a.speicher_wunsch:
        a.gruende.append("WR/Speicher-Kombination nicht im Sortiment "
                         "(kein Speicher angegeben)")
        return
    moeglich = sorted((bat, nr) for serie, wr, bat, nr in kombis
                      if serie == a.serie and wr == a.wr_kw
                      and bat >= a.speicher_wunsch - 1e-9)
    if not moeglich:
        a.gruende.append(
            f"WR/Speicher-Kombination nicht im Sortiment ({a.serie} "
            f"{int(a.wr_kw)} kW mit mind. {_de(a.speicher_wunsch, 1)} kWh)")
        return
    a.speicher_stufe, a.kombi_nr = moeglich[0]


def auslegungs_text(a: Auslegung) -> str:
    """Textzeile im Angebot + Protokoll: Module, kWp, Strings, WR/Speicher,
    Belegungsart mit Herleitung."""
    if not a.module:
        return ""
    teile = [f"{a.module} Module à {_de(a.kwp / a.module * 1000)} Wp = "
             f"{_de(a.kwp, 2)} kWp",
             f"{a.strings} String{'s' if a.strings != 1 else ''} "
             f"(max. {a.max_je_string} Module je String)"]
    if a.kombi_text:
        teile.append(f"Wechselrichter/Speicher: Sigenergy {a.kombi_text}")
    text = "Auslegung: " + " · ".join(teile)
    art = a.belegungsart or MAXIMAL
    text += f"\nBelegungsart: {art}"
    if a.herleitung:
        text += f"\n{a.herleitung}"
    return text


# --- Ampel ------------------------------------------------------------------

def ampel_gruende(logik: Logik, antworten: dict) -> list[str]:
    """Berechnete AMPEL-Gründe (die antwortbasierten kommen aus den
    AMPEL-Zeilen im Blatt „Aktionen PV“ über die Engine)."""
    if engine.naechste_frage(logik, antworten) is not None:
        return []   # Bogen unvollständig – Gründe erst bei vollständigem Bogen
    a = auslegen(logik, antworten)
    gruende = list(a.gruende)
    for aktion in logik.pv_aktionen:
        if aktion.frage == "Strings" and aktion.typ == "ampel":
            if a.strings and _bereich_trifft(aktion.antwort, a.strings):
                gruende.append(aktion.ampel_grund)
    return gruende


def _bereich_trifft(antwort: str, zahl: float) -> bool:
    return any(engine._bereich_passt(t, zahl) for t in _teile(antwort))


def _teile(antwort: str) -> list[str]:
    return [t.strip() for t in re.split(r"\s+/\s+", antwort) if t.strip()]


# --- WP-Verbrauch aus der WP-Erfassung des Vorgangs ---------------------------

def wp_ableitung_aktualisieren(session, erfassung, antworten: dict,
                               logik: Logik | None = None) -> Optional[float]:
    """Setzt SCHLUESSEL_WP_ABGELEITET, wenn PO07 = „Aus WP-Erfassung ermitteln“:
    Gas-/Ölverbrauch (A03, kWh) der WP-Erfassung desselben Vorgangs ÷ JAZ.
    Liefert den Stromverbrauch oder None (keine WP-Erfassung mit Zahl)."""
    import json

    from app.models import Erfassung
    antworten.pop(SCHLUESSEL_WP_ABGELEITET, None)
    if antworten.get(ID_STROM_WP) != AUS_WP:
        return None
    filter_ = [Erfassung.id != erfassung.id, Erfassung.sparte == "WP"]
    if erfassung.vorgang_id:
        filter_.append(Erfassung.vorgang_id == erfassung.vorgang_id)
    elif erfassung.lead_id:
        filter_.append(Erfassung.lead_id == erfassung.lead_id)
    else:
        filter_.append(Erfassung.kunde_id == erfassung.kunde_id)
    jaz = 3.5
    if logik is not None:
        jaz = parameter(logik)["jaz"]
    for wp in (session.query(Erfassung).filter(*filter_)
               .order_by(Erfassung.angelegt_am.desc())):
        verbrauch = engine.zahl_parsen(json.loads(wp.antworten_json or "{}").get("A03"))
        if verbrauch:
            strom = round(verbrauch / jaz, 2)
            antworten[SCHLUESSEL_WP_ABGELEITET] = {
                "erfassung_id": wp.id, "verbrauch_kwh": verbrauch, "strom_kwh": strom}
            return strom
    return None


def dachbelegung_setzen(antworten: dict, max_module: int, quer: int = 0) -> None:
    """Schnittstelle für das Dachbelegungstool (Zulieferung): schreibt die
    Modulanzahl bzw. den Quer-Anteil in dieselben Schlüssel wie die
    Interim-Felder PD12/PD13 – die Auslegung bleibt unverändert."""
    antworten[ID_MAX_MODULE] = float(max_module)
    if quer:
        antworten[ID_QUER] = float(quer)


# --- Positionen -------------------------------------------------------------

@dataclass
class PvArtikel:
    ref: str
    menge: float
    ep: bool
    quelle: str


def _menge(menge_roh: str, wert, a: Auslegung) -> float:
    roh = (menge_roh or "1").strip()
    zahl = engine.zahl_parsen(roh)
    if zahl is not None:
        return zahl
    klein = roh.lower()
    if "quer" in klein and ("module" in klein or "modul" in klein):
        return float(max(0, a.module - a.quer))      # „(Module − quer)“
    if "modul" in klein:
        return float(a.module)
    if "string" in klein:
        return float(a.strings)
    if "quer" in klein:
        return float(a.quer)
    antwortzahl = engine.zahl_parsen(wert)
    return float(antwortzahl) if antwortzahl is not None else 1.0


def _zusatz_ok(aktion, antworten: dict, logik: Logik) -> bool:
    b = aktion.zusatz_bedingung
    if b is None:
        return True
    dummy = engine.Frage("_", 0, "", "Auswahl", [], b, "")
    return engine.ist_sichtbar(dummy, antworten, logik.fragen, logik)


def artikel_ermitteln(logik: Logik, antworten: dict,
                      a: Auslegung) -> list[PvArtikel]:
    gewaehlt: list[PvArtikel] = []
    for frage in engine.sichtbare_fragen(logik, antworten):
        if frage.id not in antworten:
            continue
        wert = antworten[frage.id]
        if isinstance(wert, (dict, list)) or frage.typ in ("Freitext", "Freitext groß"):
            continue
        for aktion in logik.pv_aktionen:
            if aktion.frage != frage.id or aktion.typ != "normal":
                continue
            index = engine._teil_index(frage, aktion.antwort, wert, antworten,
                                       logik.fragen)
            if index is None or not _zusatz_ok(aktion, antworten, logik):
                continue
            for ref in engine.refs_fuer_treffer(aktion, index):
                menge = _menge(ref.menge, wert, a)
                if menge > 0:
                    gewaehlt.append(PvArtikel(ref.ref, menge, ref.ep, frage.id))
            break
    friondo_ja = any(antworten.get(f) == "Ja" for f in FRIONDO_PV)
    for aktion in logik.pv_aktionen:
        if aktion.typ != "normal" or not _zusatz_ok(aktion, antworten, logik):
            continue
        if aktion.frage == "Grundpaket" or (aktion.frage == "Gruppen-Trigger"
                                            and friondo_ja):
            for ref in aktion.artikel:
                menge = _menge(ref.menge, None, a)
                if menge > 0:
                    gewaehlt.append(PvArtikel(ref.ref, menge, ref.ep,
                                              aktion.frage.lower()))
        elif aktion.frage == "Strings" and a.strings:
            if _bereich_trifft(aktion.antwort, a.strings):
                for ref in aktion.artikel:
                    gewaehlt.append(PvArtikel(ref.ref, _menge(ref.menge, None, a),
                                              ref.ep, "strings"))
    if a.kombi_nr:
        gewaehlt.append(PvArtikel(a.kombi_nr, 1.0, False, "wr/speicher"))
    return gewaehlt


def _index_im_inhalt(inhalt: str, artikel: PvArtikel) -> int:
    if artikel.quelle == "wr/speicher":
        return inhalt.find("WR/Speicher")
    ref = artikel.ref
    if ref.isdigit():
        m = re.search(rf"\b{re.escape(ref)}\b", inhalt)
    else:
        m = re.search(rf"\b{re.escape(ref)}\b", inhalt)
    return m.start() if m else -1


def ueberschrift(block, a: Auslegung) -> str:
    u = block.ueberschrift
    if u.startswith("(ohne"):
        return ""
    if u.startswith("DYNAMISCH"):
        zitate = re.findall(r"'([^']+)'", u)
        u = zitate[0] if zitate else u
    return u.replace("{kWp}", _de(a.kwp, 2))


def positionen_zusammenstellen(logik: Logik, antworten: dict, session,
                               erfassung=None) -> list[dict]:
    """Positions-Snapshots des PV-Angebots in Blockreihenfolge (Blatt
    „Angebotsaufbau PV“); gleiche Artikel im selben Block werden addiert."""
    from app.models import Artikel
    if erfassung is not None:
        wp_ableitung_aktualisieren(session, erfassung, antworten, logik)
    a = auslegen(logik, antworten)
    p = parameter(logik)
    gewaehlt = artikel_ermitteln(logik, antworten, a)
    artikel_map = {x.pos_nr: x for x in
                   session.query(Artikel).filter(Artikel.aktiv.is_(True)) if x.pos_nr}
    bloecke = sorted(logik.pv_bloecke, key=lambda b: b.nr)
    zugeordnet = []
    for gw in gewaehlt:
        platz = None
        for block in bloecke:
            index = _index_im_inhalt(block.inhalt_roh, gw)
            if index >= 0:
                platz = (block.nr, index)
                break
        zugeordnet.append((platz or (bloecke[0].nr if bloecke else 1, 9999), gw))
    zugeordnet.sort(key=lambda t: t[0])
    positionen: list[dict] = []
    gesehen: dict[tuple[int, str], dict] = {}
    bloecke_map = {b.nr: b for b in bloecke}
    for (block_nr, _i), gw in zugeordnet:
        if (block_nr, gw.ref) in gesehen:
            gesehen[(block_nr, gw.ref)]["menge"] += gw.menge
            continue
        stamm = artikel_map.get(gw.ref)
        if stamm is None:
            continue
        beschreibung = stamm.beschreibung
        if gw.quelle == "grundpaket" and gw.ref == _modul_ref(logik) and p["modul_hinweis"]:
            beschreibung = beschreibung.rstrip() + "\n\n" + p["modul_hinweis"]
        block = bloecke_map.get(block_nr)
        eintrag = {
            "block_nr": block_nr,
            "gruppe": ueberschrift(block, a) if block else "",
            "pos_nr": stamm.pos_nr, "bezeichnung": stamm.bezeichnung,
            "beschreibung": beschreibung, "menge": gw.menge,
            "einheit": stamm.einheit, "e_preis_cent": stamm.e_preis_cent,
            "ep_flag": stamm.ep_flag or gw.ep, "ek_cent": stamm.ek_cent,
            "guid": stamm.guid,
        }
        gesehen[(block_nr, gw.ref)] = eintrag
        positionen.append(eintrag)
    # Auslegungszeile (0,00 €) am Ende von Block 1
    text = auslegungs_text(a)
    if text and positionen:
        erster = positionen[0]["block_nr"]
        letzte = max(i for i, x in enumerate(positionen) if x["block_nr"] == erster)
        positionen.insert(letzte + 1, {
            "block_nr": erster, "gruppe": positionen[letzte]["gruppe"],
            "pos_nr": "", "bezeichnung": "Auslegung der PV-Anlage",
            "beschreibung": text, "menge": 1.0, "einheit": "pauschal",
            "e_preis_cent": 0, "ep_flag": False, "ek_cent": 0, "guid": ""})
    for sort, x in enumerate(positionen, 1):
        x["sort"] = sort
    return positionen


def _modul_ref(logik: Logik) -> str:
    """Modulartikel = erste Referenz „× Modulanzahl“ im Grundpaket."""
    for aktion in logik.pv_aktionen:
        if aktion.frage == "Grundpaket":
            for ref in aktion.artikel:
                if "modul" in ref.menge.lower() and "quer" not in ref.menge.lower():
                    return ref.ref
    return ""


# --- Protokoll ----------------------------------------------------------------

def protokoll_zeilen(logik: Logik, antworten: dict) -> list[dict]:
    """Auslegungs-Zusammenfassung für das Konfigurationsprotokoll."""
    if engine.naechste_frage(logik, antworten) is not None:
        return []
    a = auslegen(logik, antworten)
    text = auslegungs_text(a)
    if not text:
        return []
    return [{"frage_id": "", "seite": "Auslegung", "frage": "Auslegung PV",
             "antwort": text.replace("\n", " · "), "ampel_grund": ""}]


# --- Wirtschaftlichkeit (Phase 78) -------------------------------------------

def wirtschaftlichkeit(logik: Logik, kwp: float, mit_speicher: bool,
                       mit_hems: bool, investition_cent: int) -> dict:
    """Beispielrechnung: Jahresertrag = kWp × spez. Ertrag; Eigenverbrauch =
    Ertrag × Quote (PV + Zuschlag Speicher + Zuschlag HEMS); Ersparnis =
    Eigenverbrauch × Strompreis + Einspeisung × Vergütung; Amortisation =
    Investition ÷ Ersparnis."""
    p = parameter(logik)
    ertrag = kwp * p["ertrag"]
    quote = p["ev_pv"] + (p["ev_speicher"] if mit_speicher else 0) \
        + (p["ev_hems"] if mit_hems else 0)
    quote = min(quote, 100.0)
    eigen = ertrag * quote / 100
    einspeisung = ertrag - eigen
    ersparnis = eigen * p["strompreis"] + einspeisung * p["verguetung"]
    investition = investition_cent / 100
    jahre = investition / ersparnis if ersparnis > 0 else None
    return {"kwp": kwp, "ertrag": ertrag, "quote": quote, "eigen": eigen,
            "einspeisung": einspeisung, "strompreis": p["strompreis"],
            "verguetung": p["verguetung"], "ersparnis_eigen": eigen * p["strompreis"],
            "ersparnis_einspeisung": einspeisung * p["verguetung"],
            "ersparnis": ersparnis, "investition": investition,
            "amortisation": jahre, "ev_pv": p["ev_pv"],
            "ev_speicher": p["ev_speicher"] if mit_speicher else 0,
            "ev_hems": p["ev_hems"] if mit_hems else 0}
