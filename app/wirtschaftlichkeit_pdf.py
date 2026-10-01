# Wirtschaftlichkeitsseiten PV (v22, PLAN_V15 Phase 101): drei feste A4-
# Seiten im PV-Angebots-PDF, gezeichnet mit fpdf2-Primitiven (rect, line,
# cell/multi_cell) nach der visuellen Referenz docs/wirtschaftlichkeit-mockup/
# seite1-3.html (794 × 1123 px = A4, 1 px = 0,2646 mm = 0,75 pt). Daten kommen
# aus pdf_export.wirtschaftlichkeit_fuer (Rechenkern app/wirtschaftlichkeit.py).
# Schrift Poppins (app/static/pdf/fonts, SIL OFL), Fallback Arial mit
# Log-Warnung. Kein Seitenumbruch innerhalb der drei Seiten (Auto-Page-Break
# aus, danach wieder an); Fußzeile wie im übrigen Angebot (fpdf2 ruft
# footer() automatisch), Kopf kompakt über AngebotsPdf.kompakt_kopf.

from __future__ import annotations

import logging
from pathlib import Path

from fpdf.enums import XPos, YPos

log = logging.getLogger(__name__)

ASSETS = Path(__file__).resolve().parent / "static" / "pdf"
FONTS = ASSETS / "fonts"

# Farben (RGB) laut Plan
NAVY = (27, 42, 94)
NAVY_HELL = (36, 54, 110)
BLAU = (63, 134, 198)
BLAU_DUNKEL = (50, 110, 165)
TINT = (234, 242, 250)
TINT2 = (201, 216, 234)
SONNE = (240, 165, 0)
SONNE_DUNKEL = (154, 103, 0)
GRAU_FLAECHE = (213, 219, 229)
KARTE = (246, 248, 251)
LINIE = (223, 227, 234)
TEXT = (27, 31, 42)
GRAU_TEXT = (90, 98, 112)
WEISS = (255, 255, 255)
HERO_EYEBROW = (159, 184, 220)
HERO_HELL = (196, 210, 236)

LINKS = 20.0          # linker Rand
BREITE = 170.0        # Inhaltsbreite
RECHTS = LINKS + BREITE
INNEN = 7.0           # Innenabstand der Karten
RADIUS = 3.0
MM_JE_PT = 25.4 / 72

EYEBROWS = ("WIRTSCHAFTLICHKEITSBETRACHTUNG", "IHRE ERSPARNIS IM DETAIL",
            "SICHERHEIT & TRANSPARENZ")


# --- Schrift -----------------------------------------------------------------

_POPPINS = {
    "r": ("Poppins", "", "Poppins-Regular.ttf"),
    "m": ("PoppinsMedium", "", "Poppins-Medium.ttf"),
    "s": ("PoppinsSemiBold", "", "Poppins-SemiBold.ttf"),
    "b": ("Poppins", "B", "Poppins-Bold.ttf"),
}
_ARIAL = {"r": ("Arial", ""), "m": ("Arial", ""), "s": ("Arial", "B"), "b": ("Arial", "B")}


def fonts_laden(pdf) -> dict:
    """Poppins einmal je PDF-Instanz registrieren; fehlt eine Datei →
    Arial-Fallback (Warnung ins Log, kein Abbruch)."""
    if getattr(pdf, "_wf_fonts", None):
        return pdf._wf_fonts
    dateien = {k: FONTS / v[2] for k, v in _POPPINS.items()}
    fehlend = [str(p.name) for p in dateien.values() if not p.exists()]
    if fehlend:
        log.warning("Poppins-Schriften fehlen (%s) – Wirtschaftlichkeitsseiten in Arial",
                    ", ".join(fehlend))
        pdf._wf_fonts = dict(_ARIAL)
        return pdf._wf_fonts
    try:
        for k, (familie, stil, datei) in _POPPINS.items():
            pdf.add_font(familie, stil, dateien[k])
        pdf._wf_fonts = {k: (v[0], v[1]) for k, v in _POPPINS.items()}
    except Exception as problem:   # defekte Datei o. ä.
        log.warning("Poppins konnte nicht geladen werden (%s) – Fallback Arial", problem)
        pdf._wf_fonts = dict(_ARIAL)
    return pdf._wf_fonts


def _font(pdf, art: str, groesse: float) -> None:
    familie, stil = fonts_laden(pdf)[art]
    pdf.set_font(familie, stil, groesse)


# --- Zahlenformate -------------------------------------------------------------

def _zahl(wert: float, stellen: int = 0) -> str:
    """Tausenderpunkt, Komma; negative Beträge mit „−“ (U+2212)."""
    text = f"{abs(wert):,.{stellen}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if round(wert, stellen) < 0 else "") + text


def _eur(wert: float, stellen: int = 0) -> str:
    return f"{_zahl(wert, stellen)} €"


def _eur100(wert: float) -> str:
    return _eur(round(wert / 100) * 100)


def _prozent(anteil: float | None) -> str:
    return "–" if anteil is None else f"{_zahl(anteil * 100)} %"


def _ct(preis_eur: float) -> str:
    """0,33 €/kWh → „33 ct“, 0,078 → „7,8 ct“."""
    ct = preis_eur * 100
    return f"{_zahl(ct, 0 if abs(ct - round(ct)) < 0.05 else 1)} ct"


def _prozentzahl(anteil: float) -> str:
    """0,004 → „0,4“, 0,03 → „3“."""
    p = anteil * 100
    return _zahl(p, 0 if abs(p - round(p)) < 0.005 else 1)


def _kwh(wert: float) -> str:
    return f"{_zahl(wert)} kWh"


def _jahre(be) -> str:
    return "–" if be is None else str(be)


# --- Zeichenhilfen ----------------------------------------------------------------

def _h(pt: float, faktor: float = 1.4) -> float:
    """Zeilenhöhe in mm für eine Schriftgröße in pt."""
    return pt * MM_JE_PT * faktor


def _karte(pdf, x: float, y: float, w: float, h: float, fuellung=WEISS,
           rand=LINIE, radius: float = RADIUS) -> None:
    pdf.set_fill_color(*fuellung)
    if rand is not None:
        pdf.set_draw_color(*rand)
        pdf.set_line_width(0.3)
        stil = "DF"
    else:
        stil = "F"
    pdf.rect(x, y, w, h, style=stil, round_corners=True, corner_radius=radius)


def _text(pdf, x: float, y: float, w: float, text: str, art: str = "r",
          groesse: float = 9, farbe=TEXT, align: str = "L", h: float | None = None,
          markdown: bool = False, faktor: float = 1.4) -> float:
    """Mehrzeiliger Text an fester Position; liefert die y-Position darunter."""
    _font(pdf, art, groesse)
    pdf.set_text_color(*farbe)
    pdf.set_xy(x, y)
    zeilenhoehe = h if h is not None else _h(groesse, faktor)
    pdf.multi_cell(w, zeilenhoehe, text, align=align, new_x=XPos.LEFT, new_y=YPos.NEXT,
                   markdown=markdown)
    return pdf.get_y()


def _zeile(pdf, x: float, y: float, w: float, text: str, art: str = "r",
           groesse: float = 9, farbe=TEXT, align: str = "L", h: float | None = None) -> None:
    """Einzeilig (cell) – für rechtsbündige Zahlen und Labels."""
    _font(pdf, art, groesse)
    pdf.set_text_color(*farbe)
    pdf.set_xy(x, y)
    pdf.cell(w, h if h is not None else _h(groesse, 1.2), text, align=align)


def _zeile_co2(pdf, x: float, y: float, w: float, text: str, art: str = "r",
               groesse: float = 9, farbe=TEXT, align: str = "L", h: float | None = None) -> None:
    """Einzeiliger Text mit „CO₂“: Poppins hat keine tiefgestellte 2, daher
    wird sie als kleinere, abgesenkte Ziffer gezeichnet."""
    if "CO₂" not in text:
        _zeile(pdf, x, y, w, text, art, groesse, farbe, align, h)
        return
    vor, nach = text.split("CO₂", 1)
    hh = h if h is not None else _h(groesse, 1.2)
    klein = groesse * 0.62
    _font(pdf, art, groesse)
    pdf.set_text_color(*farbe)
    w_vor = pdf.get_string_width(vor + "CO")
    w_nach = pdf.get_string_width(nach)
    _font(pdf, art, klein)
    w_2 = pdf.get_string_width("2") + 0.2
    gesamt = w_vor + w_2 + w_nach
    if align == "R":
        x0 = x + w - gesamt
    elif align == "C":
        x0 = x + (w - gesamt) / 2
    else:
        x0 = x
    _font(pdf, art, groesse)
    pdf.set_xy(x0, y)
    pdf.cell(w_vor, hh, vor + "CO")
    _font(pdf, art, klein)
    pdf.set_xy(x0 + w_vor, y + hh * 0.22)
    pdf.cell(w_2, hh, "2")
    _font(pdf, art, groesse)
    pdf.set_xy(x0 + w_vor + w_2, y)
    pdf.cell(w_nach, hh, nach)


def _zeilen(pdf, w: float, text: str, art: str, groesse: float) -> int:
    _font(pdf, art, groesse)
    return len(pdf.multi_cell(w, _h(groesse), text, dry_run=True, output="LINES"))


def _kuerzen(pdf, w: float, text: str, art: str, groesse: float) -> str:
    """Einzeiligen Text mit „…“ auf die Breite kürzen."""
    _font(pdf, art, groesse)
    if pdf.get_string_width(text) <= w:
        return text
    while text and pdf.get_string_width(text + "…") > w:
        text = text[:-1].rstrip()
    return text + "…"


def _kartentitel(pdf, x: float, y: float, w: float, titel: str, rechts: str = "") -> float:
    """Kartenüberschrift (Navy, halbfett 12 pt) + rechtsbündige Meta-Zeile (grau)."""
    _zeile(pdf, x, y, w, titel, "s", 12, NAVY)
    if rechts:
        _zeile(pdf, x, y + 0.6, w, rechts, "r", 8.5, GRAU_TEXT, align="R")
    return y + 7.5


def _kachel(pdf, x: float, y: float, w: float, h: float, wert: str, label: str,
            fuellung, wert_farbe, label_farbe, wert_pt: float = 18,
            label_pt: float = 8, rand=None) -> None:
    _karte(pdf, x, y, w, h, fuellung, rand)
    _zeile(pdf, x + 4, y + 2.5, w - 8, wert, "b", wert_pt, wert_farbe,
           h=_h(wert_pt, 1.15))
    _text(pdf, x + 4, y + 2.5 + _h(wert_pt, 1.15) + 0.5, w - 8, label, "r", label_pt,
          label_farbe, faktor=1.3)


def _eyebrow(pdf, x: float, y: float, w: float, text: str, farbe=BLAU_DUNKEL,
             groesse: float = 8) -> None:
    _font(pdf, "b", groesse)
    pdf.set_text_color(*farbe)
    pdf.set_char_spacing(0.75)
    pdf.set_xy(x, y)
    pdf.cell(w, _h(groesse, 1.2), text)
    pdf.set_char_spacing(0)


def _legende_punkt(pdf, x: float, y: float, farbe, text: str, groesse: float = 9) -> float:
    """Farbpunkt + Text; liefert x hinter dem Text."""
    pdf.set_fill_color(*farbe)
    d = 3.2
    pdf.rect(x, y + (_h(groesse, 1.2) - d) / 2, d, d, style="F", round_corners=True,
             corner_radius=1)
    _zeile(pdf, x + d + 2, y, 80, text, "r", groesse, TEXT)
    _font(pdf, "r", groesse)
    return x + d + 2 + pdf.get_string_width(text) + 6


def _gestapelter_balken(pdf, x: float, y: float, w: float, h: float,
                        teile: list[tuple[float, tuple]], text_pt: float = 9) -> None:
    """Segmente (Anteil 0…1, Farbe) nebeneinander, Prozent mittig; Prozentwerte
    werden so gerundet, dass sie sich zu 100 ergänzen."""
    teile = [(max(0.0, a), f) for a, f in teile]
    summe = sum(a for a, _ in teile) or 1.0
    anteile = [a / summe for a, _ in teile]
    prozente = [int(round(a * 100)) for a in anteile]
    diff = 100 - sum(prozente)
    if prozente:
        groesster = max(range(len(prozente)), key=lambda i: prozente[i])
        prozente[groesster] += diff
    pdf.set_fill_color(*GRAU_FLAECHE)
    pdf.rect(x, y, w, h, style="F", round_corners=True, corner_radius=1.5)
    links = x
    for (anteil, farbe), prozent in zip(zip(anteile, [f for _, f in teile]), prozente):
        breite = w * anteil
        if breite <= 0:
            continue
        pdf.set_fill_color(*farbe)
        pdf.rect(links, y, breite, h, style="F")
        if breite >= 9:
            hell = farbe in (SONNE, BLAU, NAVY, BLAU_DUNKEL)
            _zeile(pdf, links, y, breite, f"{prozent} %", "b", text_pt,
                   WEISS if hell else NAVY, align="C", h=h)
        links += breite
    # runde Ecken am Rand nachziehen (Hintergrund der Seite/Karte ist weiß)
    pdf.set_draw_color(*WEISS)
    pdf.set_line_width(0.6)
    pdf.rect(x, y, w, h, style="D", round_corners=True, corner_radius=1.5)


# --- Kopfzeile ----------------------------------------------------------------------

def kompakter_kopf(pdf, kopf: dict) -> None:
    """Kompakter Seitenkopf (nur diese drei Seiten): Logo rechts oben, links
    Eyebrow (Blau dunkel, 8 pt fett, Zeichenabstand +1) und Meta-Zeile."""
    logo = ASSETS / "friondo_logo.png"
    if logo.exists():
        pdf.image(logo, x=RECHTS - 29, y=10.5, w=29)
    _eyebrow(pdf, LINKS, 11.2, 120, kopf.get("eyebrow", ""))
    _zeile(pdf, LINKS, 16.2, 130, kopf.get("zeile", ""), "r", 9, GRAU_TEXT)
    pdf.set_y(27)


# --- Einstieg -------------------------------------------------------------------------

def seiten_zeichnen(pdf, daten: dict) -> None:
    """Zeichnet die drei Seiten in das laufende Angebots-PDF (eigene Seiten;
    Kopf kompakt, Fußzeile automatisch)."""
    fonts_laden(pdf)
    kopf = daten.get("kopf") or {}
    zeichner = (_seite1, _seite2, _seite3)
    pdf.set_auto_page_break(False)
    try:
        for i, (eyebrow, fn) in enumerate(zip(EYEBROWS, zeichner), 1):
            pdf.kompakt_kopf = {
                "eyebrow": eyebrow,
                "zeile": (f"zu Angebot {kopf.get('nummer', '')} · {kopf.get('ort', '')}, "
                          f"{kopf.get('datum', '')} · Seite {i} von {len(zeichner)}"),
            }
            pdf.add_page()
            fn(pdf, daten)
    finally:
        pdf.kompakt_kopf = None
        pdf.set_auto_page_break(True, 42)
        pdf.set_char_spacing(0)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.set_draw_color(0, 0, 0)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_line_width(0.2)


def _h1(pdf, titel: str, subline: str, max_zeilen: int = 3) -> None:
    _text(pdf, LINKS, 27, BREITE, titel, "b", 22.5, NAVY, faktor=1.15)
    y = 38.0
    while _zeilen(pdf, BREITE, subline, "r", 10) > max_zeilen and "…" not in subline:
        # Kunde/Adresse kürzen: Segment nach „für “ bis zum Punkt
        if " für " in subline and ". " in subline:
            kopf, rest = subline.split(" für ", 1)
            wer, rest2 = rest.split(". ", 1)
            wer = wer[: max(10, len(wer) - 12)].rstrip(" ,") + "…"
            subline = f"{kopf} für {wer}. {rest2}"
        else:
            break
    _text(pdf, LINKS, y, BREITE, subline, "r", 10, GRAU_TEXT, faktor=1.45)


def _bausteine_text(a: dict) -> str:
    teile = [f"PV-Anlage {_zahl(a['kwp'], 2)} kWp mit {a['module']} Modulen"]
    if a["speicher_kwh"] > 0:
        teile.append(f"Sigenergy Speicher {_zahl(a['speicher_kwh'])} kWh")
    if a["hems"]:
        teile.append("Friondo HEMS")
    if a["spot"]:
        teile.append("Friondo SpotDynamic")
    return " · ".join(teile)


def _verbrauchsbasis(a: dict) -> str:
    teile = []
    if a["hh_kwh"]:
        teile.append(f"{_kwh(a['hh_kwh'])} Haushaltsstrom")
    if a["wp_kwh"]:
        teile.append(f"{_kwh(a['wp_kwh'])} Wärmepumpenstrom")
    if a["wb_kwh"]:
        teile.append(f"{_kwh(a['wb_kwh'])} Wallbox-Strom")
    if not teile:
        return ""
    if len(teile) == 1:
        return teile[0]
    return ", ".join(teile[:-1]) + " und " + teile[-1]


# --- Seite 1: Auf einen Blick ---------------------------------------------------------

def _seite1(pdf, daten: dict) -> None:
    e = daten["ergebnis"]
    a = e["anlage"]
    p = e["param"]
    kopf = daten.get("kopf") or {}
    wer = kopf.get("kunde", "")
    adresse = kopf.get("adresse", "")
    fuer = ", ".join(t for t in (wer, adresse) if t)
    basis = _verbrauchsbasis(a)
    subline = _bausteine_text(a)
    if fuer:
        subline += f" — für {fuer}."
    else:
        subline += "."
    if basis:
        subline += f" Grundlage: {basis} pro Jahr."
    _h1(pdf, "So rechnet sich Ihre Energielösung", subline)

    # Hero-Karte
    y0 = 57.0
    _karte(pdf, LINKS, y0, BREITE, 61, NAVY, None)
    xi = LINKS + INNEN
    wi = BREITE - 2 * INNEN
    _eyebrow(pdf, xi, y0 + INNEN, 84, f"IHRE ERSPARNIS IN {e['n']} JAHREN", HERO_EYEBROW)
    _zeile(pdf, xi, y0 + INNEN + 5, 84, _eur100(e["summe_ersparnis"]), "b", 43, WEISS,
           h=_h(43, 1.0))
    faktor = e["faktor"]
    faktor_text = (f"Das {_zahl(faktor, 1)}-Fache Ihrer Investition von "
                   f"{_eur(a['investition_eur'])} – vermiedene Stromkosten plus "
                   f"Einspeisevergütung, bei nur {_prozentzahl(p['steigerung'])} % "
                   "Strompreissteigerung pro Jahr." if faktor is not None else
                   "Vermiedene Stromkosten plus Einspeisevergütung, bei nur "
                   f"{_prozentzahl(p['steigerung'])} % Strompreissteigerung pro Jahr.")
    _text(pdf, xi + 86, y0 + INNEN + 1, wi - 86, faktor_text, "r", 10, WEISS, faktor=1.4)
    # drei Kacheln
    ky = y0 + 32
    kh = 22.0
    gap = 4.0
    kw = (wi - 2 * gap) / 3
    be = e["break_even"]
    kacheln = [
        (f"{be} Jahre" if be else "über " + str(e["n"]) + " J.",
         "bis sich die Anlage bezahlt gemacht hat" if be
         else "Amortisation liegt außerhalb der Betrachtung"),
        (_prozent(e["j1"]["autarkie"]), "Ihres Stroms kommen vom eigenen Dach"),
        (f"{_zahl(e['monat'])} €/Monat", "Ersparnis – schon im ersten Jahr"),
    ]
    for i, (wert, label) in enumerate(kacheln):
        _kachel(pdf, xi + i * (kw + gap), ky, kw, kh, wert, label, NAVY_HELL, WEISS,
                HERO_HELL, 18, 8)

    # Karte „Wann sich Ihre Anlage bezahlt macht“
    y1 = 122.0
    _karte(pdf, LINKS, y1, BREITE, 74)
    y = _kartentitel(pdf, xi, y1 + INNEN, wi, "Wann sich Ihre Anlage bezahlt macht",
                     "Kumulierte Ersparnis abzüglich Investition, in €")
    start = e["startjahr"]
    _zeile(pdf, xi, y, wi, f"Start {start or ''}: Investition {_eur(a['investition_eur'])}",
           "r", 8, GRAU_TEXT)
    _kum_balken(pdf, xi, y + 4, wi, e)
    be_jahr = e["break_even_jahr"]
    if be and be_jahr:
        satz = (f"Ab {be_jahr} arbeitet die Anlage nur noch für Sie: "
                f"**rund {_eur100(e['gewinn_ende'])} Gewinn bis {e['endjahr']}**.")
    else:
        satz = (f"Innerhalb von {e['n']} Jahren erreicht die Anlage "
                f"{_eur(e['gewinn_ende'])} – die Amortisation liegt jenseits des "
                "Betrachtungszeitraums.")
    _text(pdf, xi, y1 + 74 - INNEN - 4.6, wi, satz, "r", 9, TEXT, markdown=True, faktor=1.25)

    # Karte „Woher Ihr Strom kommt“
    y2 = 200.0
    _karte(pdf, LINKS, y2, BREITE, 56)
    y = _kartentitel(pdf, xi, y2 + INNEN, wi,
                     "Woher Ihr Strom kommt – und wohin Ihr Solarstrom geht",
                     "Jahr 1, in kWh")
    j1 = e["j1"]
    label_w = 52.0
    bx = xi + label_w + 3
    bw = wi - label_w - 3
    bh = 8.0
    # Solarstrom-Balken
    _zeile(pdf, xi, y, label_w, f"Solarstrom {_kwh(j1['prod'])}", "b", 9, TEXT)
    _zeile(pdf, xi, y + 4.2, label_w, f"aus {_zahl(a['kwp'], 2)} kWp", "r", 9, TEXT)
    prod = j1["prod"] or 1.0
    _gestapelter_balken(pdf, bx, y, bw, bh, [
        (j1["direkt"] / prod, SONNE), (j1["sp_in"] / prod, BLAU),
        (j1["einsp"] / prod, GRAU_FLAECHE)])
    y += bh + 3.5
    teile = [t for t, kwh in (("Haushalt", a["hh_kwh"]), ("Wärmepumpe", a["wp_kwh"]),
                              ("Wallbox", a["wb_kwh"])) if kwh]
    _zeile(pdf, xi, y, label_w, f"Verbrauch {_kwh(j1['last'])}", "b", 9, TEXT)
    _zeile(pdf, xi, y + 4.2, label_w, " + ".join(teile) or "Verbrauch", "r", 9, TEXT)
    last = j1["last"] or 1.0
    _gestapelter_balken(pdf, bx, y, bw, bh, [
        (j1["direkt"] / last, SONNE), (j1["sp_out"] / last, BLAU),
        (j1["netz"] / last, GRAU_FLAECHE)])
    y += bh + 3.5
    x = xi
    x = _legende_punkt(pdf, x, y, SONNE, "Direkt von der Sonne")
    x = _legende_punkt(pdf, x, y, BLAU, "Über den Speicher")
    _legende_punkt(pdf, x, y, GRAU_FLAECHE, "Ins Netz bzw. aus dem Netz")
    y += 6
    satz = (f"Sie nutzen **{_prozent(j1['ev_quote'])} Ihres Solarstroms selbst** "
            f"(Eigenverbrauch) und decken **{_prozent(j1['autarkie'])} Ihres Bedarfs "
            "vom eigenen Dach** (Autarkie).")
    _text(pdf, xi, y, wi, satz, "r", 10, TEXT, markdown=True, faktor=1.4)


def _jahres_labels(n: int) -> set[int]:
    labels = {j for j in range(1, n + 1) if (j - 1) % 3 == 0}
    labels = {j for j in labels if j == n or n - j >= 2}
    labels.add(n)
    return labels


def _kum_balken(pdf, x: float, y: float, w: float, e: dict) -> None:
    """Balken je Jahr (kum_j): positiv Blau nach oben, negativ Tint 2 nach
    unten, Nulllinie Navy; Positivbereich 24 mm, Negativbereich 11 mm
    (Verhältnis wie im Mockup, damit Labels und Schlusssatz in die Karte
    passen), gemeinsame Skala."""
    jahre = e["jahre"]
    n = len(jahre)
    pos_max = max((z["kum"] for z in jahre if z["kum"] > 0), default=0.0)
    neg_max = max((-z["kum"] for z in jahre if z["kum"] < 0), default=0.0)
    skala = min(24 / pos_max if pos_max else float("inf"),
                11 / neg_max if neg_max else float("inf"))
    if skala == float("inf"):
        skala = 0.0
    y_null = y + 24
    slot = w / n
    balken = slot * 0.78
    labels = _jahres_labels(n)
    be = e["break_even"]
    for z in jahre:
        j = z["jahr"]
        bx = x + (j - 1) * slot + (slot - balken) / 2
        h = abs(z["kum"]) * skala
        if z["kum"] >= 0:
            pdf.set_fill_color(*BLAU)
            if h > 0.2:
                pdf.rect(bx, y_null - h, balken, h, style="F", round_corners=True,
                         corner_radius=0.8)
        else:
            pdf.set_fill_color(*TINT2)
            pdf.rect(bx, y_null, balken, h, style="F", round_corners=True, corner_radius=0.8)
        if j in labels:
            _zeile(pdf, bx - slot, y_null + 12, balken + 2 * slot,
                   str(z.get("kalenderjahr") or j), "r", 8, GRAU_TEXT, align="C")
        if j == n:
            _zeile(pdf, bx - 20, y_null - h - 5, balken + 20,
                   ("+" if z["kum"] >= 0 else "") + _eur(z["kum"]), "b", 9, NAVY, align="R")
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.3)
    pdf.line(x, y_null, x + w, y_null)
    if be:
        cx = x + (be - 1) * slot + slot / 2
        chip_text = f"Break-even {e['break_even_jahr']}"
        _font(pdf, "b", 9)
        chip_w, chip_h = pdf.get_string_width(chip_text) + 7, 6.5
        # nie über die rechte Innenkante und nicht unter das Endlabel des
        # letzten Balkens (Kollision bei spätem Break-even)
        cx0 = min(max(cx - chip_w / 2, x), x + w - 1.3 * slot - chip_w)
        cx0 = max(cx0, x)
        # über die höchsten Balken im Chip-Bereich heben
        j_von = max(1, int((cx0 - x) / slot) + 1)
        j_bis = min(n, int((cx0 + chip_w - x) / slot) + 1)
        hoechster = max((jahre[j - 1]["kum"] * skala for j in range(j_von, j_bis + 1)
                         if jahre[j - 1]["kum"] > 0), default=0.0)
        chip_y = min(y_null - 9.5, y_null - hoechster - chip_h - 1.5)
        chip_y = max(chip_y, y - 1)
        _karte(pdf, cx0, chip_y, chip_w, chip_h, SONNE, None, 3.2)
        _zeile(pdf, cx0, chip_y, chip_w, chip_text, "b", 9, NAVY, align="C", h=chip_h)


# --- Seite 2: Ersparnis im Detail -------------------------------------------------------

def _seite2(pdf, daten: dict) -> None:
    e = daten["ergebnis"]
    a = e["anlage"]
    p = e["param"]
    _h1(pdf, "Was Sie Jahr für Jahr sparen",
        f"Ihre Stromkosten über {e['n']} Jahre – ohne Anlage und mit Ihrer Friondo-"
        "Energielösung. Dazu: wie sich Ihr Vorteil im ersten Jahr zusammensetzt und "
        "was jeder Baustein des Systems beiträgt.")
    xi = LINKS + INNEN
    wi = BREITE - 2 * INNEN

    # Karte „Ihre Stromkosten pro Jahr“
    y0 = 57.0
    _karte(pdf, LINKS, y0, BREITE, 76)
    y = _kartentitel(pdf, xi, y0 + INNEN, wi, "Ihre Stromkosten pro Jahr",
                     f"ohne Anlage vs. mit Friondo, in €, Strompreis "
                     f"+{_prozentzahl(p['steigerung'])} % p. a.")
    mit_text = ("Mit Friondo (Netzbezug zu SpotDynamic-Preisen abzüglich Einspeisung)"
                if a["spot"] else "Mit Friondo (Netzbezug abzüglich Einspeisung)")
    x = _legende_punkt(pdf, xi, y, NAVY, "Ohne Anlage")
    _legende_punkt(pdf, x, y, BLAU, mit_text)
    y += 6
    _kosten_balken(pdf, xi, y, wi, e)
    ky = y0 + 76 - INNEN - 16
    gap = 4.0
    kw = (wi - 2 * gap) / 3
    kacheln = [
        (_eur100(e["summe_ohne"]), f"ohne Anlage in {e['n']} Jahren", KARTE, NAVY, GRAU_TEXT),
        (_eur100(e["summe_mit"]), f"mit Friondo in {e['n']} Jahren", TINT, BLAU_DUNKEL,
         BLAU_DUNKEL),
        (_eur100(e["summe_ersparnis"]), f"Ihr Vorteil in {e['n']} Jahren", NAVY, WEISS,
         HERO_HELL),
    ]
    for i, (wert, label, fuellung, wf, lf) in enumerate(kacheln):
        _kachel(pdf, xi + i * (kw + gap), ky, kw, 16, wert, label, fuellung, wf, lf, 14, 8)

    # Karte links „Ihr Vorteil im ersten Jahr“
    y1 = 138.0
    lw = 87.0
    _karte(pdf, LINKS, y1, lw, 63)
    xl = LINKS + INNEN
    wl = lw - 2 * INNEN
    y = _kartentitel(pdf, xl, y1 + INNEN, wl, "Ihr Vorteil im ersten Jahr")
    _zeile(pdf, xl, y - 1.5, wl, "kWh × Preis = Betrag", "r", 8.5, GRAU_TEXT)
    y += 4
    v = e["vorteil"]
    ct = _ct(v["preis"])
    zeilen = [
        ("Stromkosten heute", f"{_zahl(v['last'])} × {ct}", _eur(v["stromkosten_heute"])),
        ("Netzbezug neu", f"{_zahl(v['netz'])} × {ct}", "− " + _eur(v["netzbezug"])),
        ("Einspeisung", f"{_zahl(v['einsp'])} × {_ct(p['verguetung'])}",
         "+ " + _eur(v["einspeisung"])),
    ]
    if a["spot"]:
        zeilen.append(("SpotDynamic", f"{_zahl(v['netz'])} × −{_ct(v['spot_differenz'])}",
                       "+ " + _eur(v["spot_vorteil"])))
    zeilen.append(("Betriebskosten", "pauschal", "− " + _eur(v["betriebskosten"])))
    verfuegbar = (y1 + 63 - INNEN) - y
    zh = min(6.6, verfuegbar / (len(zeilen) + 1))
    spalten = (wl * 0.45, wl * 0.31, wl * 0.24)
    for name, rechnung, betrag in zeilen:
        _zeile(pdf, xl, y, spalten[0], name, "r", 8.5, TEXT, h=zh)
        _zeile(pdf, xl + spalten[0], y, spalten[1], rechnung, "r", 8, GRAU_TEXT, h=zh)
        _zeile(pdf, xl + spalten[0] + spalten[1], y, spalten[2], betrag, "b", 9, NAVY,
               align="R", h=zh)
        pdf.set_draw_color(*LINIE)
        pdf.set_line_width(0.25)
        pdf.line(xl, y + zh, xl + wl, y + zh)
        y += zh
    _zeile(pdf, xl, y, spalten[0], "Ihr Vorteil Jahr 1", "b", 9, NAVY, h=zh)
    _zeile(pdf, xl + spalten[0], y, spalten[1], f"{_zahl(e['monat'])} €/Monat", "r", 8,
           GRAU_TEXT, h=zh)
    _zeile(pdf, xl + spalten[0] + spalten[1], y, spalten[2], _eur(v["summe"]), "b", 10,
           NAVY, align="R", h=zh)

    # Karte rechts
    xr = LINKS + lw + 4
    wr = BREITE - lw - 4
    _karte(pdf, xr, y1, wr, 63)
    xri = xr + INNEN
    wri = wr - 2 * INNEN
    h = e["heizen"]
    if h:
        y = _kartentitel(pdf, xri, y1 + INNEN, wri, "Heizen mit Sonnenstrom")
        y = _text(pdf, xri, y - 1.5, wri, f"Wärmepumpe: **{_kwh(h['wp_kwh'])} Strom/Jahr**",
                  "r", 8.5, TEXT, markdown=True, faktor=1.3) + 1.2
        anteil = h["anteil_pv"]
        bh = 8.0
        pdf.set_fill_color(*GRAU_FLAECHE)
        pdf.rect(xri, y, wri, bh, style="F", round_corners=True, corner_radius=1.5)
        pdf.set_fill_color(*SONNE)
        pdf.rect(xri, y, wri * anteil, bh, style="F", round_corners=True, corner_radius=1.5)
        _zeile(pdf, xri, y, wri * anteil, f"{_prozent(anteil)} vom Dach", "b", 9, WEISS,
               align="C", h=bh)
        _zeile(pdf, xri + wri * anteil, y, wri * (1 - anteil),
               f"{_prozent(1 - anteil)} Netz", "b", 9, NAVY, align="C", h=bh)
        y += bh + 2.5
        kw2 = (wri - 3) / 2
        _kachel(pdf, xri, y, kw2, 15, _eur(h["kosten_ohne_pv"]),
                "Heizstrom pro Jahr ohne PV", KARTE, NAVY, GRAU_TEXT, 13, 7.5)
        _kachel(pdf, xri + kw2 + 3, y, kw2, 15, _eur(h["kosten_mit_pv"]),
                "Heizstrom pro Jahr mit PV", TINT, BLAU_DUNKEL, BLAU_DUNKEL, 13, 7.5)
        y += 15 + 2
        if a["hems"]:
            satz = ("Friondo HEMS lässt die Wärmepumpe bevorzugt bei Sonne laufen: "
                    f"Solaranteil am Heizstrom {_prozent(h['anteil_mit_hems'])} statt "
                    f"{_prozent(h['anteil_ohne_hems'])}.")
        else:
            satz = (f"Mit Friondo HEMS stiege der Solaranteil auf "
                    f"{_prozent(h['anteil_mit_hems'])}.")
        _text(pdf, xri, y, wri, satz, "r", 8, TEXT, faktor=1.3)
    else:
        y = _kartentitel(pdf, xri, y1 + INNEN, wri, "Ihr Verbrauch")
        y = _text(pdf, xri, y - 1, wri, f"Gesamt: **{_kwh(e['j1']['last'])} Strom pro Jahr**",
                  "r", 8.5, TEXT, markdown=True, faktor=1.3) + 1.5
        last = e["j1"]["last"] or 1.0
        hh, wb = a["hh_kwh"], a["wb_kwh"]
        bh = 8.0
        pdf.set_fill_color(*GRAU_FLAECHE)
        pdf.rect(xri, y, wri, bh, style="F", round_corners=True, corner_radius=1.5)
        pdf.set_fill_color(*SONNE)
        pdf.rect(xri, y, wri * hh / last, bh, style="F", round_corners=True, corner_radius=1.5)
        _zeile(pdf, xri, y, wri * hh / last, f"{_prozent(hh / last)} Haushalt", "b", 9,
               WEISS, align="C", h=bh)
        if wb:
            _zeile(pdf, xri + wri * hh / last, y, wri * wb / last,
                   f"{_prozent(wb / last)} Wallbox", "b", 9, NAVY, align="C", h=bh)
        y += bh + 3
        kw2 = (wri - 3) / 2
        _kachel(pdf, xri, y, kw2, 15, _kwh(hh), "Haushalt pro Jahr", KARTE, NAVY,
                GRAU_TEXT, 13, 7.5)
        _kachel(pdf, xri + kw2 + 3, y, kw2, 15, _kwh(wb) if wb else _kwh(e["j1"]["netz"]),
                "Wallbox pro Jahr" if wb else "Netzbezug mit PV", TINT,
                BLAU_DUNKEL, BLAU_DUNKEL, 13, 7.5)
        y += 15 + 2
        _text(pdf, xri, y, wri, "Ohne Wärmepumpe im Verbrauch – die Rechnung berücksichtigt "
              "Haushalt" + (" und Wallbox." if wb else "."), "r", 8, TEXT, faktor=1.3)

    # Karte „Was jeder Baustein bringt“
    y2 = 205.0
    _karte(pdf, LINKS, y2, BREITE, 51)
    y = _kartentitel(pdf, xi, y2 + INNEN, wi, "Was jeder Baustein bringt",
                     "Ersparnis im ersten Jahr, in €")
    _treppe(pdf, xi, y, wi, y2 + 51 - INNEN, e)


def _kosten_balken(pdf, x: float, y: float, w: float, e: dict) -> None:
    jahre = e["jahre"]
    n = len(jahre)
    maximum = max(max(z["ohne"], z["mit"], 0.0) for z in jahre) or 1.0
    skala = 28 / maximum
    y_null = y + 28
    slot = w / n
    bw = slot * 0.36
    labels = _jahres_labels(n)
    for z in jahre:
        j = z["jahr"]
        bx = x + (j - 1) * slot + slot * 0.1
        h_ohne = max(0.0, z["ohne"]) * skala
        h_mit = max(0.0, z["mit"]) * skala
        pdf.set_fill_color(*NAVY)
        if h_ohne > 0.2:
            pdf.rect(bx, y_null - h_ohne, bw, h_ohne, style="F", round_corners=True,
                     corner_radius=0.7)
        pdf.set_fill_color(*BLAU)
        if h_mit > 0.2:
            pdf.rect(bx + bw + slot * 0.08, y_null - h_mit, bw, h_mit, style="F",
                     round_corners=True, corner_radius=0.7)
        if j in labels:
            _zeile(pdf, bx - slot, y_null + 1, 3 * slot, str(z.get("kalenderjahr") or j),
                   "r", 8, GRAU_TEXT, align="C")
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.3)
    pdf.line(x, y_null, x + w, y_null)


def _treppe(pdf, x: float, y: float, w: float, unten: float, e: dict) -> None:
    stufen = e["treppe"]
    farben = [TINT2, BLAU, BLAU_DUNKEL, NAVY]
    n = len(stufen)
    if n == 0:
        return
    hinweis = e.get("spot_hinweis")
    if hinweis and hinweis["delta_1"] < 1:
        hinweis = None            # ohne Netzbezug bringt SpotDynamic nichts
    # fehlt SpotDynamic: vierte Säule entfällt, ihr Platz trägt die Hinweiszeile
    slots = n + 1 if hinweis else n
    gap = 5.0
    cw = (w - gap * (slots - 1)) / slots
    maximum = max(s["ersparnis_1"] for s in stufen) or 1.0
    h_max = 15.0
    y_basis = y + 5 + h_max
    for i, s in enumerate(stufen):
        cx = x + i * (cw + gap)
        h = max(6.0, max(0.0, s["ersparnis_1"]) / maximum * h_max)
        farbe = farben[min(i, len(farben) - 1)]
        pdf.set_fill_color(*farbe)
        pdf.rect(cx, y_basis - h, cw, h, style="F", round_corners=True, corner_radius=1.5)
        hell = farbe != TINT2
        _zeile(pdf, cx, y_basis - h, cw, _eur(s["ersparnis_1"]), "b", 10,
               WEISS if hell else NAVY, align="C", h=h)
        if i == 0:
            _zeile(pdf, cx, y_basis - h - 4.5, cw, "Basis", "r", 8, GRAU_TEXT, align="C")
        elif s["delta"] is not None:
            _zeile(pdf, cx, y_basis - h - 4.5, cw, "+ " + _eur(s["delta"]), "b", 8,
                   SONNE_DUNKEL, align="C")
        _zeile(pdf, cx, y_basis + 1.5, cw, s["name"], "b", 9, NAVY)
        be = s["break_even"]
        detail = (f"{e['n']} Jahre: {_eur100(s['summe'])} · "
                  + (f"amortisiert nach {be} J." if be else "keine Amortisation"))
        _text(pdf, cx, y_basis + 6.5, cw, detail, "r", 8, GRAU_TEXT, faktor=1.3)
    pdf.set_draw_color(*LINIE)
    pdf.set_line_width(0.3)
    pdf.line(x, y_basis, x + w, y_basis)
    if hinweis:
        hx = x + n * (cw + gap)
        _karte(pdf, hx, y_basis - h_max - 1, cw, h_max + 1, KARTE, None, 1.5)
        _text(pdf, hx + 2.5, y_basis - h_max + 1, cw - 5,
              f"Mit Friondo SpotDynamic zusätzlich rund **+ {_eur(hinweis['delta_1'])}/Jahr**",
              "r", 8, SONNE_DUNKEL, markdown=True, faktor=1.3)
        _zeile(pdf, hx, y_basis + 1.5, cw, "+ SpotDynamic", "b", 9, SONNE_DUNKEL)
        _text(pdf, hx, y_basis + 6.5, cw, "sprechen Sie uns an", "r", 8, GRAU_TEXT, faktor=1.3)


# --- Seite 3: Sicherheit & Transparenz ---------------------------------------------------

def _seite3(pdf, daten: dict) -> None:
    e = daten["ergebnis"]
    a = e["anlage"]
    p = e["param"]
    _h1(pdf, "So sicher ist Ihre Rechnung",
        "Was passiert, wenn der Strompreis kaum steigt? Was bringt Ihre Anlage dem "
        "Klima? Und auf welchen Annahmen beruht das alles? Wir legen es offen.")
    xi = LINKS + INNEN
    wi = BREITE - 2 * INNEN

    # Karte „Drei Strompreis-Szenarien“
    y0 = 57.0
    _karte(pdf, LINKS, y0, BREITE, 71)
    y = _kartentitel(pdf, xi, y0 + INNEN, wi,
                     f"{_anzahl_wort(len(e['szenarien']))} Strompreis-Szenarien",
                     f"Ersparnis in {e['n']} Jahren, in €")
    _szenarien(pdf, xi, y, wi, e)
    min_sz = min(e["szenarien"], key=lambda s: s["steigerung"]) if e["szenarien"] else None
    text = ""
    if min_sz is not None:
        if min_sz["break_even"]:
            text = (f"Selbst bei nur {_prozentzahl(min_sz['steigerung'])} % Preissteigerung "
                    f"pro Jahr bleibt es bei rund {min_sz['break_even']} Jahren bis zur "
                    "Amortisation.")
        else:
            text = (f"Bei nur {_prozentzahl(min_sz['steigerung'])} % Preissteigerung pro Jahr "
                    f"liegt die Amortisation außerhalb von {e['n']} Jahren.")
    if a["spot"]:
        text += (f" SpotDynamic ist mit Ø {_ct(p['spot_preis'])}/kWh angesetzt, der "
                 f"Kosten-Airbag deckelt bei {_ct(p['airbag'])}.")
    _text(pdf, xi, y0 + 71 - INNEN - 9.5, wi, text.strip(), "r", 9.5, TEXT, faktor=1.4)

    # Karte „Ihr Beitrag zum Klima“
    y1 = 132.0
    _karte(pdf, LINKS, y1, BREITE, 34)
    y = _kartentitel(pdf, xi, y1 + INNEN, wi, "Ihr Beitrag zum Klima")
    _zeile_co2(pdf, xi, y1 + INNEN + 0.6, wi,
               f"Netzstrom mit {_zahl(p['co2_faktor'])} g CO₂/kWh (Umweltbundesamt)",
               "r", 8.5, GRAU_TEXT, align="R")
    co2 = e["co2"]
    gap = 4.0
    kw = (wi - 3 * gap) / 4
    kacheln = [
        ("wolke", f"{_zahl(co2['t_jahr'], 1)} t CO₂", "pro Jahr vermieden"),
        ("blatt", f"{_zahl(co2['t_gesamt'])} t CO₂", f"in {e['n']} Jahren"),
        ("auto", f"{_zahl(round((co2['km'] or 0) / 100) * 100)} km", "Autofahrt pro Jahr"),
        ("baum", f"{_zahl(co2['baeume'] or 0)} Bäume", "gleiche Wirkung"),
    ]
    for i, (icon, wert, label) in enumerate(kacheln):
        kx = xi + i * (kw + gap)
        _karte(pdf, kx, y, kw, 17, KARTE, None, 2.5)
        _icon(pdf, icon, kx + 3.5, y + 3.5, 6.5)
        _zeile_co2(pdf, kx + 11.5, y + 2.5, kw - 13, wert, "b", 13, NAVY, h=_h(13, 1.15))
        _zeile(pdf, kx + 3.5, y + 11, kw - 5, label, "r", 8, GRAU_TEXT)

    # Karte „Unsere Annahmen – transparent“
    y2 = 170.0
    _karte(pdf, LINKS, y2, BREITE, 86)
    y = _kartentitel(pdf, xi, y2 + INNEN, wi, "Unsere Annahmen – transparent",
                     "Modellannahmen, keine Zusage")
    verbrauch = " + ".join(t for t in (
        f"{_zahl(a['hh_kwh'])} kWh Haushalt" if a["hh_kwh"] else "",
        f"{_zahl(a['wp_kwh'])} WP" if a["wp_kwh"] else "",
        f"{_zahl(a['wb_kwh'])} Wallbox" if a["wb_kwh"] else "") if t) or "–"
    links = [
        ("Ertrag", f"{_zahl(p['ertrag'])} kWh/kWp · Monatsprofil · "
                   f"−{_prozentzahl(p['degradation'])} %/Jahr"),
        ("Strompreis", f"{_ct(p['strompreis'])}/kWh · +{_prozentzahl(p['steigerung'])} %/Jahr"),
        ("Einspeisung", f"{_ct(p['verguetung'])}/kWh · {e['n']} Jahre fest"),
        ("Speicher", (f"{_zahl(p['wirkungsgrad'] * 100)} % Wirkungsgrad · "
                      f"{_zahl(p['zyklen'])} Zyklen") if a["speicher_kwh"] > 0
         else "nicht enthalten"),
    ]
    rechts = [
        ("Verbrauch", verbrauch + " · saisonal"),
        ("Friondo HEMS", "PV-optimierte WP und Speicher" if a["hems"] else "nicht enthalten"),
        ("SpotDynamic", (f"Ø {_ct(p['spot_preis'])}/kWh statt {_ct(p['strompreis'])} · "
                         f"Airbag {_ct(p['airbag'])}") if a["spot"] else "nicht enthalten"),
        ("Betrieb", f"{_eur(p['betriebskosten'])}/Jahr · {e['n']} Jahre ab {e['startjahr'] or ''}"),
    ]
    spalte_w = (wi - 6) / 2
    label_w = 26.0
    ende = y
    for spalte, zeilen in enumerate((links, rechts)):
        sx = xi + spalte * (spalte_w + 6)
        yy = y
        for name, wert in zeilen:
            zeilen_n = _zeilen(pdf, spalte_w - label_w, wert, "r", 8.5)
            hoehe = max(6.8, zeilen_n * _h(8.5, 1.3) + 2.2)
            _zeile(pdf, sx, yy, label_w, name, "r", 8.5, GRAU_TEXT, h=hoehe)
            _text(pdf, sx + label_w, yy + (hoehe - zeilen_n * _h(8.5, 1.3)) / 2,
                  spalte_w - label_w, wert, "r", 8.5, TEXT, faktor=1.3)
            pdf.set_draw_color(*LINIE)
            pdf.set_line_width(0.25)
            pdf.line(sx, yy + hoehe, sx + spalte_w, yy + hoehe)
            yy += hoehe
        ende = max(ende, yy)
    y = _text(pdf, xi, ende + 3, wi,
              "Modellrechnung auf Basis Ihrer Angaben und üblicher Erfahrungswerte. Erträge "
              "und Einsparungen hängen von Ausrichtung, Verschattung, Wetter, Verbrauch und "
              "Strompreisen ab und können abweichen. Keine Garantie, kein Vertragsbestandteil.",
              "r", 8, GRAU_TEXT, faktor=1.4)
    y = min(y + 3.5, y2 + 86 - INNEN - 13)
    _eyebrow(pdf, xi, y, wi, "SO GEHT ES WEITER")
    y += 6
    schritte = ["Angebot annehmen", "Feinplanung vor Ort",
                p.get("montage_text") or "Montage in 1–2 Tagen",
                "Inbetriebnahme & Einweisung"]
    sw = (wi - 3 * 2) / 4
    for i, schritt in enumerate(schritte):
        sx = xi + i * (sw + 2)
        pdf.set_fill_color(*BLAU)
        pdf.ellipse(sx, y, 6, 6, style="F")
        _zeile(pdf, sx, y, 6, str(i + 1), "b", 8, WEISS, align="C", h=6)
        _text(pdf, sx + 7.5, y - 0.3, sw - 7.5, schritt, "b", 8.5, NAVY, faktor=1.25)


def _anzahl_wort(n: int) -> str:
    return {1: "Ein", 2: "Zwei", 3: "Drei", 4: "Vier", 5: "Fünf"}.get(n, str(n))


def _szenarien(pdf, x: float, y: float, w: float, e: dict) -> None:
    sz = e["szenarien"]
    if not sz:
        return
    farben = [TINT2, BLAU, NAVY]
    n = len(sz)
    gap = 8.0
    cw = (w - gap * (n - 1)) / n
    maximum = max(s["summe"] for s in sz) or 1.0
    h_max = 22.0
    y_basis = y + 5 + h_max
    eigene = e["param"]["steigerung"]
    niedrig = min(s["steigerung"] for s in sz)
    hoch = max(s["steigerung"] for s in sz)
    for i, s in enumerate(sz):
        cx = x + i * (cw + gap)
        h = max(8.0, max(0.0, s["summe"]) / maximum * h_max)
        farbe = farben[min(i, len(farben) - 1)] if n <= 3 else farben[i % 3]
        pdf.set_fill_color(*farbe)
        pdf.rect(cx, y_basis - h, cw, h, style="F", round_corners=True, corner_radius=1.5)
        _zeile(pdf, cx, y_basis - h - 5, cw, _eur100(s["summe"]), "b", 10, NAVY, align="C")
        be = s["break_even"]
        _zeile(pdf, cx, y_basis - 6.5, cw,
               f"Amortisation {be} Jahre" if be else "keine Amortisation", "b", 9,
               NAVY if farbe == TINT2 else WEISS, align="C", h=6)
        _zeile(pdf, cx, y_basis + 2, cw, f"Strompreis +{_prozentzahl(s['steigerung'])} % pro Jahr",
               "b", 10, NAVY)
        if abs(s["steigerung"] - eigene) < 1e-9:
            note = "Ihre Rechnung"
        elif s["steigerung"] == niedrig:
            note = "vorsichtig gerechnet"
        elif s["steigerung"] == hoch:
            note = "bei stark steigenden Preisen"
        else:
            note = ""
        _zeile(pdf, cx, y_basis + 7, cw, note, "r", 9, GRAU_TEXT)
    pdf.set_draw_color(*LINIE)
    pdf.set_line_width(0.3)
    pdf.line(x, y_basis, x + w, y_basis)


def _icon(pdf, art: str, x: float, y: float, s: float) -> None:
    """Strich-Icons (Wolke, Blatt, Auto, Baum) aus einfachen Linienzügen."""
    pdf.set_draw_color(*BLAU_DUNKEL)
    pdf.set_line_width(0.45)
    if art == "wolke":
        pdf.ellipse(x + s * 0.05, y + s * 0.45, s * 0.5, s * 0.4, style="D")
        pdf.ellipse(x + s * 0.3, y + s * 0.2, s * 0.55, s * 0.6, style="D")
        pdf.ellipse(x + s * 0.5, y + s * 0.45, s * 0.45, s * 0.4, style="D")
        pdf.set_fill_color(*KARTE)
        pdf.set_draw_color(*KARTE)
        pdf.rect(x + s * 0.12, y + s * 0.5, s * 0.78, s * 0.3, style="F")
        pdf.set_draw_color(*BLAU_DUNKEL)
        pdf.line(x + s * 0.1, y + s * 0.85, x + s * 0.92, y + s * 0.85)
    elif art == "blatt":
        pdf.bezier([(x + s * 0.1, y + s * 0.9), (x + s * 0.05, y + s * 0.2),
                    (x + s * 0.95, y + s * 0.1)], closed=False, style="D")
        pdf.bezier([(x + s * 0.95, y + s * 0.1), (x + s * 0.9, y + s * 0.9),
                    (x + s * 0.1, y + s * 0.9)], closed=False, style="D")
        pdf.line(x + s * 0.15, y + s * 0.85, x + s * 0.7, y + s * 0.35)
    elif art == "auto":
        pdf.rect(x + s * 0.05, y + s * 0.45, s * 0.9, s * 0.32, style="D",
                 round_corners=True, corner_radius=s * 0.1)
        pdf.polyline([(x + s * 0.2, y + s * 0.45), (x + s * 0.35, y + s * 0.2),
                      (x + s * 0.7, y + s * 0.2), (x + s * 0.82, y + s * 0.45)])
        pdf.ellipse(x + s * 0.18, y + s * 0.68, s * 0.18, s * 0.18, style="D")
        pdf.ellipse(x + s * 0.64, y + s * 0.68, s * 0.18, s * 0.18, style="D")
    elif art == "baum":
        pdf.polygon([(x + s * 0.5, y + s * 0.05), (x + s * 0.2, y + s * 0.45),
                     (x + s * 0.35, y + s * 0.45), (x + s * 0.1, y + s * 0.75),
                     (x + s * 0.9, y + s * 0.75), (x + s * 0.65, y + s * 0.45),
                     (x + s * 0.8, y + s * 0.45)], style="D")
        pdf.line(x + s * 0.5, y + s * 0.75, x + s * 0.5, y + s * 0.95)
