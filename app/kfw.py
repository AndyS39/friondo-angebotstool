# KfW-Förderberechnung (Phase 6) – exakt nach Blatt "KfW" der Logik-Excel.
# Die Rechenlogik ist deckungsgleich mit der Referenz foerderrechner-website.html
# (Testfälle in tests/test_kfw.py müssen identische Ergebnisse liefern).

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from app.logik import Logik


def _rund_cent(wert: float) -> int:
    """Wie Math.round(v*100)/100 der Referenz: kaufmännisch auf Cent (halb aufwärts)."""
    return int(math.floor(wert + 0.5))


# Fallback, falls die Logik-Excel keinen eigenen Disclaimer-Text pflegt (v2)
STANDARD_DISCLAIMER = (
    "Unverbindliche Beispielrechnung der Friondo GmbH auf Basis der BEG-Richtlinie, "
    "Konditionen ab 21.07.2026. Maßgeblich sind allein die Förderzusage der KfW "
    "und die jeweils gültige Richtlinie.")


def _zahl(text: str) -> Optional[float]:
    m = re.search(r"[\d.]+(?:,\d+)?", text)
    if not m:
        return None
    return float(m.group(0).replace(".", "").replace(",", "."))


# --- Parameter aus der Logik-Excel ---------------------------------------

@dataclass
class KfwParameter:
    grund_prozent: float = 30
    klima_prozent: float = 16
    einkommens_stufen: list[tuple[float, float]] = field(default_factory=list)  # (Prozent, Einkommensgrenze)
    kind_freibetrag_eur: float = 10000
    deckel_prozent: float = 70
    deckel_erhoeht_prozent: float = 80
    efh_max_eur: float = 28000
    mfh_basis_eur: float = 28000
    mfh_je_we_2_6_eur: float = 15000
    mfh_ab_7_eur: float = 8000
    gw_basis_eur: float = 28000
    gw_stufen: list[tuple[float, float, Optional[float]]] = field(default_factory=list)  # (€/m², von, bis)
    gueltig_bis: Optional[date] = None
    programm_wohn: str = "KfW 458 (Wohngebäude)"
    programm_gewerbe: str = "KfW 522 (Nichtwohngebäude)"
    disclaimer: str = ""


def parameter_lesen(logik: Logik) -> tuple[KfwParameter, list[str]]:
    """Liest die KfW-Parameter aus dem eingelesenen Blatt; Warnungen bei Lücken."""
    p = KfwParameter()
    warnungen: list[str] = []
    kfw = logik.kfw

    def wert(name: str) -> str:
        return kfw.get(name, ("", ""))[0]

    if (z := _zahl(wert("Grundförderung"))) is not None:
        p.grund_prozent = z
    if (z := _zahl(wert("Klimageschwindigkeits-Bonus"))) is not None:
        p.klima_prozent = z

    # v2: eine Zeile "40 % (≤ 30.000 €) · 30 % (≤ 40.000 €) · 10 % (≤ 50.000 €)";
    # Kind-Freibetrag steht in der Bemerkung derselben Zeile
    bonus_wert, bonus_bem = kfw.get("Einkommensbonus", ("", ""))
    for m in re.finditer(r"([\d.]+)\s*%\s*\(≤\s*([\d.]+)", bonus_wert):
        p.einkommens_stufen.append((_zahl(m.group(1)), _zahl(m.group(2))))
    if not p.einkommens_stufen:
        p.einkommens_stufen = [(40, 30000), (30, 40000), (10, 50000)]
        warnungen.append("KfW: Einkommensbonus-Stufen nicht lesbar – Standardwerte verwendet.")
    p.einkommens_stufen.sort(key=lambda s: s[1])
    m = re.search(r"Kind-Freibetrag\s*([\d.]+)", bonus_bem)
    if m:
        p.kind_freibetrag_eur = _zahl(m.group(1))

    # v2: "70 % · 80 % bei 40er-Einkommensbonus"
    deckel_werte = [_zahl(t) for t in re.findall(r"([\d.]+)\s*%", wert("Fördersatz-Deckel"))]
    if deckel_werte:
        p.deckel_prozent = deckel_werte[0]
        p.deckel_erhoeht_prozent = deckel_werte[1] if len(deckel_werte) > 1 else deckel_werte[0]
    if (z := _zahl(wert("Höchstkosten EFH"))) is not None:
        p.efh_max_eur = z

    # "28.000 € + 15.000 € je WE 2–6 + 8.000 € ab der 7. WE"
    mfh_zahlen = re.findall(r"[\d.]+(?:,\d+)?\s*€", wert("Höchstkosten MFH"))
    if len(mfh_zahlen) >= 3:
        p.mfh_basis_eur = _zahl(mfh_zahlen[0])
        p.mfh_je_we_2_6_eur = _zahl(mfh_zahlen[1])
        p.mfh_ab_7_eur = _zahl(mfh_zahlen[2])
    else:
        warnungen.append("KfW: Höchstkosten MFH nicht lesbar – Standardwerte verwendet.")

    # "28.000 € bis 150 m²; +197 €/m² (151–400 m²); +118 €/m² (401–1.000 m²); +79 €/m² (ab 1.001 m²)"
    gw = wert("Höchstkosten Gewerbe")
    if (z := _zahl(gw)) is not None:
        p.gw_basis_eur = z
    basis_bis = _zahl(gw.split(";")[0].split("bis")[-1]) if "bis" in gw else 150
    stufen = []
    letzte_grenze = basis_bis or 150
    for m in re.finditer(r"\+\s*([\d.]+)\s*€/m²\s*\((?:([\d.]+)\s*[–-]\s*([\d.]+)|ab\s*([\d.]+))", gw):
        satz = _zahl(m.group(1))
        if m.group(4):
            stufen.append((satz, letzte_grenze, None))
        else:
            bis = _zahl(m.group(3))
            stufen.append((satz, letzte_grenze, bis))
            letzte_grenze = bis
    if stufen:
        p.gw_stufen = stufen
    else:
        p.gw_stufen = [(197, 150, 400), (118, 400, 1000), (79, 1000, None)]
        warnungen.append("KfW: Höchstkosten Gewerbe nicht lesbar – Standardwerte verwendet.")

    m = re.search(r"bis\s*(\d{2})\.(\d{2})\.(\d{4})", wert("Gültigkeit der Konditionen"))
    if m:
        p.gueltig_bis = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    else:
        warnungen.append("KfW: Gültigkeit der Konditionen nicht lesbar.")

    # v2: "Programm ;; Wohngebäude KfW 458 · Gewerbe KfW 522 (nur Grundförderung)"
    programm_text = wert("Programm")
    if (m := re.search(r"Wohngebäude\s*(KfW\s*\d+)", programm_text)):
        p.programm_wohn = f"{m.group(1)} (Wohngebäude)"
    if (m := re.search(r"Gewerbe\s*(KfW\s*\d+)", programm_text)):
        p.programm_gewerbe = f"{m.group(1)} (Nichtwohngebäude)"
    p.disclaimer = wert("Disclaimer") or STANDARD_DISCLAIMER
    return p, warnungen


def gueltigkeits_warnung(p: KfwParameter, heute: Optional[date] = None) -> Optional[str]:
    heute = heute or date.today()
    if p.gueltig_bis and heute > p.gueltig_bis:
        return (f"Die hinterlegten KfW-Konditionen galten bis "
                f"{p.gueltig_bis.strftime('%d.%m.%Y')} – bitte im Blatt „KfW“ der "
                "Logik-Excel prüfen und aktualisieren!")
    return None


# --- Eingaben und Berechnung ----------------------------------------------

@dataclass
class KfwEingaben:
    objekt: str                 # "efh" | "mfh" | "nwg"
    kosten_cent: int            # Kosten der Maßnahme = Angebotssumme brutto
    wohneinheiten: int = 0      # MFH
    flaeche_m2: float = 0       # Gewerbe (Nettogrundfläche)
    mfh_selbst: bool = False    # F32
    klima_bonus: bool = False   # F34 Option 1/2
    einkommen_eur: float = 0    # F35 (0 = keine Angabe)
    kind: bool = False          # F36


@dataclass
class KfwErgebnis:
    programm: str
    zeilen: list[tuple[str, str, bool]]     # (Bezeichnung, Wert, hervorgehoben)
    satz_text: str
    hoechstkosten_cent: int
    foerderfaehig_cent: int
    zuschuss_cent: int
    eigenanteil_cent: int
    hinweise: list[str]
    disclaimer: str


def ergebnis_mit_override(ergebnis: "KfwErgebnis", manuell_cent,
                          kosten_cent: int) -> "KfwErgebnis":
    """v6: manuell überschriebener Zuschuss (Angebot.foerderung_manuell_cent).
    Ersetzt Zuschuss + Eigenanteil und kennzeichnet die Darstellung als
    „manuell festgelegt“; None lässt das Ergebnis unverändert."""
    if manuell_cent is None:
        return ergebnis
    from dataclasses import replace
    zuschuss = max(0, int(manuell_cent))
    eigenanteil = max(0, kosten_cent - zuschuss)
    zeilen = []
    for name, wert, fett in ergebnis.zeilen:
        if name == "KfW-Zuschuss":
            zeilen.append(("KfW-Zuschuss (manuell festgelegt)", _euro(zuschuss), True))
        elif name == "Eigenanteil des Kunden":
            zeilen.append((name, _euro(eigenanteil), fett))
        else:
            zeilen.append((name, wert, fett))
    return replace(ergebnis, zeilen=zeilen, zuschuss_cent=zuschuss,
                   eigenanteil_cent=eigenanteil,
                   satz_text=ergebnis.satz_text + " · Zuschuss manuell festgelegt")


@dataclass
class FoerderBausteine:
    """v8: einzelne Förder-Overrides aus dem Editor; None = automatisch."""
    grund_prozent: Optional[float] = None
    klima_prozent: Optional[float] = None
    einkommen_prozent: Optional[float] = None
    hoechstkosten_cent: Optional[int] = None

    @property
    def aktiv(self) -> bool:
        return any(w is not None for w in (self.grund_prozent, self.klima_prozent,
                                           self.einkommen_prozent, self.hoechstkosten_cent))


def bausteine_aus_angebot(angebot) -> FoerderBausteine:
    return FoerderBausteine(angebot.foerder_grund_prozent,
                            angebot.foerder_klima_prozent,
                            angebot.foerder_einkommen_prozent,
                            angebot.foerder_hoechstkosten_cent)


def ergebnis_fuer_angebot(p: KfwParameter, e: KfwEingaben, angebot) -> "KfwErgebnis":
    """v8: Berechnung mit Baustein-Overrides des Angebots; ein Alt-Override
    (foerderung_manuell_cent, v6) wird weiterhin als Gesamtwert angewendet."""
    ergebnis = berechnen(p, e, bausteine_aus_angebot(angebot))
    return ergebnis_mit_override(ergebnis, angebot.foerderung_manuell_cent,
                                 e.kosten_cent)


def eingaben_aus_antworten(kfw_daten: dict, kosten_cent: int) -> Optional[KfwEingaben]:
    """Ableitung lt. Blatt "KfW" (v2): Gebäudetyp aus der Objektart O01
    (EFH/REH/RMH → EFH mit automatischer Selbstnutzung; 2FH/MFH → MFH mit
    WE aus O03 und Selbstnutzung aus K01; Gewerbe → Nichtwohngebäude mit
    Fläche aus O05), Klima-Bonus aus K02, Einkommen K03, Kind K04."""
    objektart = str(kfw_daten.get("O01") or "")
    if objektart in ("EFH", "REH", "RMH"):
        objekt = "efh"
        mfh_selbst = True
    elif objektart in ("2FH", "MFH"):
        objekt = "mfh"
        mfh_selbst = kfw_daten.get("K01") == "Ja"
    elif objektart.startswith("Gewerbe"):
        objekt = "nwg"
        mfh_selbst = False
    else:
        return None
    k02 = str(kfw_daten.get("K02") or "")
    klima = bool(k02) and not k02.startswith("Andere")
    einkommen = kfw_daten.get("K03")
    return KfwEingaben(
        objekt=objekt,
        kosten_cent=kosten_cent,
        wohneinheiten=int(float(kfw_daten.get("O03") or 0)),
        flaeche_m2=float(kfw_daten.get("O05") or 0),
        mfh_selbst=mfh_selbst,
        klima_bonus=klima,
        einkommen_eur=float(einkommen) if einkommen not in (None, "") else 0,
        kind=kfw_daten.get("K04") == "Ja",
    )


def _euro(cent: int) -> str:
    vz = "-" if cent < 0 else ""
    cent = abs(cent)
    e, c = divmod(cent, 100)
    return f"{vz}{e:,.0f}".replace(",", ".") + f",{c:02d} €"


def _prozent(zahl: float) -> str:
    if zahl == int(zahl):
        return str(int(zahl))
    return f"{zahl}".replace(".", ",")


def hoechstkosten_cent(p: KfwParameter, e: KfwEingaben) -> int:
    if e.objekt == "efh":
        return int(round(p.efh_max_eur * 100))
    if e.objekt == "mfh":
        n = max(e.wohneinheiten, 1)
        eur = (p.mfh_basis_eur + p.mfh_je_we_2_6_eur * min(n - 1, 5)
               + p.mfh_ab_7_eur * max(n - 6, 0))
        return int(round(eur * 100))
    eur = p.gw_basis_eur
    for satz, von, bis in p.gw_stufen:
        if e.flaeche_m2 > von:
            obergrenze = min(e.flaeche_m2, bis) if bis else e.flaeche_m2
            eur += satz * (obergrenze - von)
    return int(round(eur * 100))


def berechnen(p: KfwParameter, e: KfwEingaben,
              bausteine: Optional["FoerderBausteine"] = None) -> KfwErgebnis:
    b = bausteine if (bausteine and bausteine.aktiv) else None
    selbstnutzung = e.objekt == "efh" or (e.objekt == "mfh" and e.mfh_selbst)
    cap_cent = (b.hoechstkosten_cent if b and b.hoechstkosten_cent is not None
                else hoechstkosten_cent(p, e))
    foerderf_cent = min(e.kosten_cent, cap_cent)

    einkommen = max(0.0, e.einkommen_eur - (p.kind_freibetrag_eur if e.kind else 0)) \
        if e.einkommen_eur > 0 else 0.0
    eink_bonus = 0.0
    if selbstnutzung and e.einkommen_eur > 0:
        for prozent, grenze in p.einkommens_stufen:
            if einkommen <= grenze:
                eink_bonus = prozent
                break
    hoechste_stufe = max(s[0] for s in p.einkommens_stufen)
    deckel = p.deckel_erhoeht_prozent if eink_bonus == hoechste_stufe else p.deckel_prozent
    klima_bonus = p.klima_prozent if (selbstnutzung and e.klima_bonus) else 0.0

    # v8: Baustein-Overrides ersetzen die jeweils berechneten Werte
    if b is not None:
        if b.grund_prozent is not None:
            from dataclasses import replace as _replace
            p = _replace(p, grund_prozent=b.grund_prozent)
        if b.klima_prozent is not None:
            klima_bonus = b.klima_prozent
        if b.einkommen_prozent is not None:
            eink_bonus = b.einkommen_prozent

    zeilen: list[tuple[str, str, bool]] = []
    hinweise: list[str] = []

    if e.objekt == "efh":
        satz_roh = p.grund_prozent + klima_bonus + eink_bonus
        satz = min(satz_roh, deckel)
        zuschuss_cent = _rund_cent(foerderf_cent * satz / 100)
        zeilen.append(("Grundförderung", f"{_prozent(p.grund_prozent)} %", False))
        zeilen.append(("Klimageschwindigkeits-Bonus",
                       f"+{_prozent(klima_bonus)} %" if klima_bonus else "–", False))
        zeilen.append(("Einkommensbonus",
                       f"+{_prozent(eink_bonus)} %" if eink_bonus else "–", False))
        zeilen.append(("Fördersatz gesamt",
                       f"{_prozent(satz)} %" + (" (gedeckelt)" if satz_roh > deckel else ""), True))
        if satz_roh > deckel:
            hinweise.append(f"Die Boni ergäben rechnerisch {_prozent(satz_roh)} %, der "
                            f"Fördersatz ist jedoch auf {_prozent(deckel)} % gedeckelt.")
        satz_text = (f"Fördersatz: {_prozent(satz)} % von "
                     f"{_euro(foerderf_cent)} förderfähigen Kosten")
    elif e.objekt == "mfh":
        grund_cent = _rund_cent(foerderf_cent * p.grund_prozent / 100)
        bonus_rate = min(klima_bonus + eink_bonus, deckel - p.grund_prozent)
        anteil_cent = foerderf_cent / e.wohneinheiten if e.wohneinheiten > 0 else 0
        bonus_cent = _rund_cent(anteil_cent * bonus_rate / 100) if e.mfh_selbst else 0
        zuschuss_cent = grund_cent + bonus_cent
        zeilen.append((f"Grundförderung ({_prozent(p.grund_prozent)} %)",
                       _euro(grund_cent), False))
        if e.mfh_selbst:
            zeilen.append((f"Boni selbstgenutzte WE ({_prozent(bonus_rate)} % anteilig)",
                           _euro(bonus_cent) if bonus_cent else "–", False))
            if klima_bonus + eink_bonus > bonus_rate:
                hinweise.append(
                    f"Die Boni ergäben rechnerisch {_prozent(klima_bonus + eink_bonus)} %-Punkte, "
                    f"sind aber auf {_prozent(bonus_rate)} %-Punkte "
                    f"(Gesamtdeckel {_prozent(deckel)} %) begrenzt.")
            if bonus_cent > 0:
                hinweise.append(
                    f"Boni sind anteilig für die selbst bewohnte Wohneinheit gerechnet "
                    f"(förderfähige Kosten ÷ {e.wohneinheiten} WE) – Näherung, maßgeblich "
                    "ist die KfW-Berechnung im Antrag.")
        eff_satz = (round(zuschuss_cent / foerderf_cent * 1000) / 10
                    if foerderf_cent > 0 else p.grund_prozent)
        satz_text = (f"Effektiver Fördersatz: {_prozent(eff_satz)} % von "
                     f"{_euro(foerderf_cent)} förderfähigen Kosten")
    else:  # Gewerbe
        zuschuss_cent = _rund_cent(foerderf_cent * p.grund_prozent / 100)
        zeilen.append(("Grundförderung", f"{_prozent(p.grund_prozent)} %", True))
        hinweise.append(f"Gewerbeobjekt: Antrag über {p.programm_gewerbe.split(' (')[0]} "
                        "(Unternehmen), nur Grundförderung – Boni sind hier nicht möglich.")
        satz_text = (f"Fördersatz: {_prozent(p.grund_prozent)} % von "
                     f"{_euro(foerderf_cent)} förderfähigen Kosten")

    zeilen.append((f"Förderfähige Kosten (max. {_euro(cap_cent)})",
                   _euro(foerderf_cent), False))
    zeilen.append(("KfW-Zuschuss", _euro(zuschuss_cent), True))
    eigenanteil_cent = max(0, e.kosten_cent - zuschuss_cent)
    zeilen.append(("Eigenanteil des Kunden", _euro(eigenanteil_cent), False))

    if e.kosten_cent > cap_cent:
        hinweise.append(f"Die Kosten übersteigen die förderfähigen Höchstkosten von "
                        f"{_euro(cap_cent)} – der Betrag darüber wird nicht bezuschusst.")

    # v8: Kennzeichnung, welche Bausteine manuell überschrieben wurden
    if b is not None:
        angepasst = [name for name, wert in (
            ("Grundförderung", b.grund_prozent), ("Klima-Bonus", b.klima_prozent),
            ("Einkommensbonus", b.einkommen_prozent),
            ("Höchstkosten", b.hoechstkosten_cent)) if wert is not None]
        satz_text += " · Förderung manuell angepasst"
        hinweise.append("Förderung manuell angepasst: " + ", ".join(angepasst) + ".")

    programm = p.programm_gewerbe if e.objekt == "nwg" else p.programm_wohn
    return KfwErgebnis(
        programm=f"Antrag: {programm}",
        zeilen=zeilen,
        satz_text=satz_text,
        hoechstkosten_cent=cap_cent,
        foerderfaehig_cent=foerderf_cent,
        zuschuss_cent=zuschuss_cent,
        eigenanteil_cent=eigenanteil_cent,
        hinweise=hinweise,
        disclaimer=p.disclaimer,
    )
