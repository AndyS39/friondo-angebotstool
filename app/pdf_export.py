# PDF-Export (Phase 7): baut das Angebots-PDF nach der visuellen Vorlage
# "Layout - Logo/Angebot-Nr. AN250096.pdf" – Logo-Leiste Seite 1, Folgeseiten
# mit Friondo-Logo rechts, 5-Spalten-Fußzeile, Positionstabelle mit Gruppen-
# Überschriften und Übertrag-Zeilen, Summen-/KfW-Block und die vier statischen
# Nachtext-Seiten aus ANGEBOTSTEXTE.md. Ablage: data/angebote/AN-C-<Nr>.pdf

import json
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app import config, kfw
from app.models import Angebot, Kunde

ASSETS = Path(__file__).resolve().parent / "static" / "pdf"
ARIAL = Path(r"C:\Windows\Fonts")

DUNKELBLAU = (27, 42, 94)

# Fußzeile: 5 Spalten lt. ANGEBOTSTEXTE.md
FUSSZEILE = [
    ("ANSCHRIFT", ["Friondo GmbH", "Arnold-Overbeck-Str. 63-65", "47139 Duisburg"]),
    ("GESCHÄFTSFÜHRUNG", ["Andreas Scheelen", "Charoula Scheelen", "Ioannis Simeonidis"]),
    ("KONTAKT", ["T: 0203 - 3965 710", "info@friondo.de", "www.friondo.de"]),
    ("BANKVERBINDUNG", ["Sparkasse Duisburg", "IBAN: DE98 3505 0000 0200 4064 03",
                        "BIC: DUISDE33XXX", "Sparkasse Krefeld",
                        "IBAN: DE06 3205 0000 0000 4974 53", "BIC: SPKRDE33"]),
    ("STEUERDATEN", ["Amtsgericht Duisburg", "HRB 34795", "USt-IdNr. DE350979869"]),
]

ABSENDERZEILE = "Friondo GmbH · Arnold-Overbeck-Str. 63-65 · 47139 Duisburg"

# Logo-Leiste Seite 1: Positionen/Größen exakt aus dem Referenz-PDF ausgelesen
# (pdfplumber-Image-BBoxen, Phase 26) – zweizeilige Anordnung wie im Original.
LOGO_LEISTE = [
    ("badge_innung.png",         20.8, 16.9, 29.9),   # (Datei, x, y, Breite in mm)
    ("badge_bosch_premium.png",  54.0, 16.9, 19.9),
    ("badge_energy_awards.png",  90.8, 16.4, 39.8),
    ("friondo_logo.png",        144.5, 13.8, 51.9),
    ("badge_bosch_split.png",    20.8, 37.2, 52.9),
    ("badge_fachbetrieb_wp.png", 160.5, 36.2, 32.4),
]
# Folgeseiten: Friondo-Logo rechts oben, Maße aus der Referenz (Seite 2)
FOLGESEITEN_LOGO = ("friondo_logo_gross.png", 119.0, 7.4, 79.4)


def _euro_betrag(cent: int) -> str:
    vz = "-" if cent < 0 else ""
    cent = abs(int(cent))
    e, c = divmod(cent, 100)
    return f"{vz}{e:,.0f}".replace(",", ".") + f",{c:02d}"


def _menge_text(menge: float) -> str:
    if menge == int(menge):
        return f"{int(menge)},00"
    return f"{menge:.2f}".replace(".", ",")


class AngebotsPdf(FPDF):
    """A4-Angebots-PDF im Friondo-Layout."""

    def __init__(self, nummer: str):
        super().__init__("P", "mm", "A4")
        self.nummer = nummer
        self.set_margins(20, 16, 20)
        self.set_auto_page_break(True, 42)
        self.add_font("Arial", "", ARIAL / "arial.ttf")
        self.add_font("Arial", "B", ARIAL / "arialbd.ttf")
        self.add_font("Arial", "I", ARIAL / "ariali.ttf")
        self.add_font("Arial", "BI", ARIAL / "arialbi.ttf")

    @property
    def inhaltsbreite(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def multi_cell(self, w, h=None, text="", **kwargs):
        # Fließtext-Standard: linksbündig (wie Referenz), danach zurück an den linken Rand
        kwargs.setdefault("align", "L")
        kwargs.setdefault("new_x", XPos.LMARGIN)
        kwargs.setdefault("new_y", YPos.NEXT)
        return super().multi_cell(w, h, text, **kwargs)

    # --- Kopf / Fuß -------------------------------------------------------

    def header(self):
        if self.page_no() == 1:
            self._logo_leiste()
        else:
            # Kopfzeile unterhalb des Logos, Positionen wie in der Referenz
            datei, x, y, breite = FOLGESEITEN_LOGO
            self.image(ASSETS / datei, x=x, y=y, w=breite)
            self.set_font("Arial", "B", 10)
            self.set_xy(self.l_margin, 46)
            self.cell(120, 6, f"A N G E B O T - Nr.: {self.nummer}")
            self.set_font("Arial", "", 10)
            self.set_x(169.4)
            self.cell(0, 6, f"Seite: {self.page_no()}")
            self.set_y(54.5)

    def _logo_leiste(self):
        """Logo-Leiste Seite 1: Positionen exakt wie im Referenz-PDF (Phase 26)."""
        for datei, x, y, breite in LOGO_LEISTE:
            self.image(ASSETS / datei, x=x, y=y, w=breite)
        self.set_y(47)

    def footer(self):
        self.set_y(-36)
        self.set_draw_color(*DUNKELBLAU)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_y(-34)
        breiten = [30, 32, 30, 50, 28]
        x = self.l_margin
        for (titel, zeilen), breite in zip(FUSSZEILE, breiten):
            self.set_xy(x, -34)
            self.set_font("Arial", "B", 5.6)
            self.set_text_color(*DUNKELBLAU)
            self.multi_cell(breite, 2.6, titel)
            self.set_font("Arial", "", 5.6)
            self.set_text_color(60, 60, 60)
            self.set_x(x)
            self.multi_cell(breite, 2.6, "\n".join(zeilen))
            x += breite
        self.set_text_color(0, 0, 0)

    # --- Hilfen -----------------------------------------------------------

    def haken_zeile(self, text: str, fett_bis: str = ""):
        """Aufzählungszeile mit grünem Haken; optional fetter Anfang bis zum Trennzeichen."""
        self.image(ASSETS / "haken.png", x=self.l_margin + 1, y=self.get_y() + 0.6, w=3.2)
        self.set_x(self.l_margin + 6)
        if fett_bis and fett_bis in text:
            fett, rest = text.split(fett_bis, 1)
            self.set_font("Arial", "B", 9)
            self.write(4.4, fett)
            self.set_font("Arial", "", 9)
            self.write(4.4, fett_bis + rest)
            self.ln(4.4)
        else:
            self.multi_cell(self.inhaltsbreite - 6, 4.4, text)
        self.ln(0.8)


def erzeuge_pdf(angebot: Angebot, kunde: Kunde,
                kfw_ergebnis: "kfw.KfwErgebnis | None" = None,
                mit_vollmacht: bool = True,
                signatur: dict | None = None,
                ziel: Path | None = None,
                vortext_text: str | None = None,
                nachtext_text: str | None = None,
                ersetzt_hinweis: str = "") -> Path:
    """signatur (Phase 23): {"png_pfad", "name", "zeit"} – wird auf der
    Unterschriften-Seite eingebettet; ziel überschreibt den Ablageort.
    v9: Vor- und Nachtext kommen als Textblöcke (Profil/Parametrierung);
    None = Standard-Blöcke aus app.angebotsprofile."""
    from app import angebotsprofile
    pdf = AngebotsPdf(angebot.nummer)
    _seite1(pdf, angebot, kunde,
            vortext_text if vortext_text is not None
            else angebotsprofile.STANDARD_VORTEXT,
            ersetzt_hinweis=ersetzt_hinweis)
    _positionsteil(pdf, angebot)
    _vermerke_rendern(pdf, angebot)
    _summen_und_kfw(pdf, angebot, kfw_ergebnis)
    _nachtext_rendern(pdf, nachtext_text if nachtext_text is not None
                      else angebotsprofile.STANDARD_NACHTEXT, signatur)
    if mit_vollmacht:
        # Nachtext D nur bei iMSys (P02) und/oder SpotDynamic (P03) – Phase 15
        _nachtext_d(pdf, kunde, angebot)

    config.ANGEBOTE_PDF_ORDNER.mkdir(parents=True, exist_ok=True)
    if ziel is None:
        ziel = config.ANGEBOTE_PDF_ORDNER / f"{angebot.nummer}.pdf"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(ziel))
    return ziel


def _vermerke_rendern(pdf: "AngebotsPdf", angebot: Angebot) -> None:
    """v9: bedingte Angebotsvermerke (Blatt "Vermerke") am Ende des
    Positionsteils vor dem Summenblock; erste Zeile des Textes = Überschrift."""
    for vermerk in json.loads(getattr(angebot, "vermerke_json", "[]") or "[]"):
        zeilen = vermerk.splitlines()
        pdf.ln(3)
        if pdf.get_y() > pdf.page_break_trigger - 30:
            pdf.add_page()
        pdf.set_font("Arial", "B", 9)
        pdf.multi_cell(0, 4.4, zeilen[0])
        pdf.set_font("Arial", "", 8.5)
        pdf.multi_cell(0, 4.2, "\n".join(zeilen[1:]).strip())


# --- Seite 1: Briefkopf + Vortext ----------------------------------------

def _seite1(pdf: AngebotsPdf, angebot: Angebot, kunde: Kunde, vortext_text: str,
            ersetzt_hinweis: str = ""):
    pdf.add_page()

    pdf.set_font("Arial", "", 6.5)
    pdf.set_text_color(100, 100, 100)
    pdf.set_y(49.3)   # unterhalb der zweizeiligen Logo-Leiste (wie Referenz: 49,6 mm)
    pdf.cell(0, 3, ABSENDERZEILE, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)

    # Empfängerblock links (v8: Rechnungsanschrift, falls abweichend),
    # Seite/Datum rechts (Kunden-Nr. entfällt seit v8)
    y_start = pdf.get_y() + 3
    pdf.set_font("Arial", "", 10)
    pdf.set_xy(pdf.l_margin, y_start)
    person = " ".join(t for t in (kunde.anrede if kunde.anrede != "Firma" else "",
                                  kunde.vorname, kunde.nachname) if t)
    abweichend = bool(angebot.rechnung_strasse or angebot.rechnung_ort)
    empfaenger = []
    if abweichend:
        empfaenger.append(angebot.rechnung_name or kunde.firma or person)
        if angebot.rechnung_strasse:
            empfaenger.append(angebot.rechnung_strasse)
        if angebot.rechnung_plz or angebot.rechnung_ort:
            empfaenger.append(f"{angebot.rechnung_plz} {angebot.rechnung_ort}".strip())
    else:
        if kunde.firma:
            empfaenger.append(kunde.firma)
        if person:
            empfaenger.append(person)
        if kunde.strasse:
            empfaenger.append(kunde.strasse)
        if kunde.plz or kunde.ort:
            empfaenger.append(f"{kunde.plz} {kunde.ort}".strip())
    pdf.multi_cell(100, 4.8, "\n".join(empfaenger))

    pdf.set_font("Arial", "", 9)
    rechts_x = pdf.w - pdf.r_margin - 55
    pdf.set_xy(rechts_x, y_start)
    pdf.cell(25, 4.6, "Seite")
    pdf.cell(30, 4.6, ": 1", new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.set_x(rechts_x)
    pdf.cell(25, 4.6, "Datum")
    pdf.cell(30, 4.6, f": {angebot.datum.strftime('%d.%m.%Y')}", new_x=XPos.LEFT, new_y=YPos.NEXT)

    pdf.set_xy(pdf.l_margin, max(pdf.get_y(), y_start + 26) + 6)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, f"A N G E B O T - Nr.: {angebot.nummer}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if abweichend:
        # v8: abweichender Ausführungsort (= Kundenadresse aus monday)
        pdf.set_font("Arial", "", 9)
        ausfuehrung = f"{kunde.strasse}, {kunde.plz} {kunde.ort}".strip(", ")
        pdf.cell(0, 5, f"Ausführungsort: {ausfuehrung}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if ersetzt_hinweis:
        # v9: neue Version ersetzt ein früheres Angebot
        pdf.set_font("Arial", "", 9)
        pdf.cell(0, 5, ersetzt_hinweis, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # Vortext (v9): editierbarer Textblock je Profil, Override am Angebot
    _vortext_rendern(pdf, vortext_text, kunde)


def _vortext_rendern(pdf: AngebotsPdf, text: str, kunde: Kunde) -> None:
    """Vortext-Blocktext rendern: "## " fette Titelzeile · "- " Haken-Zeile ·
    "* " Haken-Zeile mit fettem Anfang (bis " – ") · "**…**" fetter Absatz ·
    {briefanrede} = dynamische Anrede; Leerzeile trennt Absätze."""
    text = text.replace("{briefanrede}", kunde.briefanrede)
    puffer: list[str] = []

    def puffer_leeren():
        if puffer:
            pdf.set_font("Arial", "", 9)
            pdf.multi_cell(0, 4.4, "\n".join(puffer))
            pdf.ln(1.5)
            puffer.clear()

    for zeile in text.splitlines():
        zeile = zeile.rstrip()
        if not zeile.strip():
            puffer_leeren()
            continue
        if zeile.startswith("## "):
            puffer_leeren()
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 5, zeile[3:], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        elif zeile.startswith("- "):
            puffer_leeren()
            pdf.haken_zeile(zeile[2:])
        elif zeile.startswith("* "):
            puffer_leeren()
            pdf.haken_zeile(zeile[2:], fett_bis=" – ")
        elif zeile.startswith("**") and zeile.endswith("**"):
            puffer_leeren()
            pdf.set_font("Arial", "B", 9)
            pdf.multi_cell(0, 4.4, zeile[2:-2])
        else:
            puffer.append(zeile)
    puffer_leeren()


# --- Positionsteil ---------------------------------------------------------

SPALTEN = {"pos": 13, "menge": 13, "einheit": 12, "text": 92, "e_preis": 20, "g_preis": 20}


def _tabellenkopf(pdf: AngebotsPdf):
    pdf.set_font("Arial", "B", 8)
    pdf.cell(SPALTEN["pos"], 4.5, "Position")
    pdf.cell(SPALTEN["menge"], 4.5, "Menge", align="R")
    pdf.cell(SPALTEN["einheit"], 4.5, " Einh.")
    pdf.cell(SPALTEN["text"], 4.5, "Bezeichnung")
    pdf.cell(SPALTEN["e_preis"], 4.5, "E-Preis", align="R")
    pdf.cell(SPALTEN["g_preis"], 4.5, "G-Preis", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1.5)


def _uebertrag_zeile(pdf: AngebotsPdf, summe_cent: int):
    pdf.set_font("Arial", "", 8.5)
    pdf.set_x(pdf.l_margin)
    breite = sum(SPALTEN.values())
    pdf.cell(breite - SPALTEN["g_preis"], 4.5, "Übertrag:", align="R")
    pdf.cell(SPALTEN["g_preis"], 4.5, _euro_betrag(summe_cent), align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _positionsteil(pdf: AngebotsPdf, angebot: Angebot):
    pdf.add_page()
    _tabellenkopf(pdf)
    zeilenhoehe = 3.7
    text_breite = SPALTEN["text"]
    uebertrag_cent = 0
    letzte_gruppe = None

    # Nummerierung identisch mit dem Editor (Phase 18/v5): eigene Nummer oder
    # fortlaufend 001, 002, … in Sortierreihenfolge
    for position, nummer in zip(angebot.positionen, angebot.nummerierung()):
        text = position.beschreibung or ""
        if position.bezeichnung and position.bezeichnung not in text.splitlines()[:1]:
            text = position.bezeichnung + ("\n" + text if text else "")
        # Positionsrabatt (v5) sichtbar an der Position ausweisen
        if position.rabatt_effektiv_cent and not position.bauseits:
            text += (f"\nabzgl. Rabatt {position.rabatt_text}"
                     f" (− {_euro_betrag(position.rabatt_effektiv_cent)} €)")

        pdf.set_font("Arial", "", 8)
        zeilen = pdf.multi_cell(text_breite, zeilenhoehe, text, dry_run=True, output="LINES")
        block_hoehe = max(len(zeilen), 1) * zeilenhoehe + 2.5
        gruppen_hoehe = 0.0
        if position.gruppe and position.gruppe != letzte_gruppe:
            pdf.set_font("Arial", "B", 8.5)
            gruppen_zeilen = pdf.multi_cell(text_breite, 4.2, position.gruppe,
                                            dry_run=True, output="LINES")
            gruppen_hoehe = len(gruppen_zeilen) * 4.2 + 3

        if pdf.get_y() + gruppen_hoehe + min(block_hoehe, 40) > pdf.page_break_trigger:
            # Bugfix Leerseite (Phase 26): steht der Cursor näher als die
            # Zeilenhöhe an der Umbruchgrenze, würde cell() in der Übertrag-
            # Zeile selbst eine Seite anlegen und das add_page() darunter
            # eine (fast) leere Seite erzeugen. Der Platz bis zur Fußzeile
            # reicht immer aus, daher hier ohne automatischen Umbruch zeichnen.
            pdf.set_auto_page_break(False)
            _uebertrag_zeile(pdf, uebertrag_cent)
            pdf.set_auto_page_break(True, 42)
            pdf.add_page()
            _tabellenkopf(pdf)
            _uebertrag_zeile(pdf, uebertrag_cent)
            pdf.ln(2)

        if position.gruppe and position.gruppe != letzte_gruppe:
            pdf.set_font("Arial", "B", 8.5)
            pdf.set_x(pdf.l_margin + SPALTEN["pos"] + SPALTEN["menge"] + SPALTEN["einheit"])
            pdf.multi_cell(text_breite, 4.2, position.gruppe)
            pdf.ln(1.5)
            letzte_gruppe = position.gruppe

        y_start = pdf.get_y()
        pdf.set_font("Arial", "", 8)
        pdf.set_xy(pdf.l_margin, y_start)
        pdf.cell(SPALTEN["pos"], zeilenhoehe, nummer)
        pdf.cell(SPALTEN["menge"], zeilenhoehe, _menge_text(position.menge), align="R")
        pdf.cell(SPALTEN["einheit"], zeilenhoehe, " " + position.einheit)

        text_x = pdf.l_margin + SPALTEN["pos"] + SPALTEN["menge"] + SPALTEN["einheit"]
        pdf.set_xy(text_x, y_start)
        pdf.multi_cell(text_breite, zeilenhoehe, text)
        y_ende = pdf.get_y()

        # Preise auf Höhe der letzten Textzeile (wie im Referenz-PDF)
        pdf.set_xy(text_x + text_breite, y_ende - zeilenhoehe)
        if position.bauseits:
            # bauseits (v5): Leistung durch den Kunden – keine Preise, zählt nicht
            pdf.cell(SPALTEN["e_preis"], zeilenhoehe, "", align="R")
            pdf.cell(SPALTEN["g_preis"], zeilenhoehe, "bauseits", align="R")
        elif position.ep_flag:
            pdf.cell(SPALTEN["e_preis"], zeilenhoehe, _euro_betrag(position.e_preis_cent), align="R")
            pdf.cell(SPALTEN["g_preis"], zeilenhoehe, "EP.", align="R")
        else:
            pdf.cell(SPALTEN["e_preis"], zeilenhoehe, _euro_betrag(position.e_preis_cent), align="R")
            pdf.cell(SPALTEN["g_preis"], zeilenhoehe, _euro_betrag(position.gesamt_cent), align="R")
            uebertrag_cent += position.gesamt_cent
        pdf.set_xy(pdf.l_margin, y_ende + 2.5)


# --- Summen + KfW ----------------------------------------------------------

def _summen_zeile(pdf: AngebotsPdf, name: str, betrag_cent: int, fett=False):
    pdf.set_font("Arial", "B" if fett else "", 9)
    pdf.set_x(pdf.l_margin + 70)
    pdf.cell(60, 5, name)
    pdf.cell(10, 5, "€")
    pdf.cell(30, 5, _euro_betrag(betrag_cent), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _summen_und_kfw(pdf: AngebotsPdf, angebot: Angebot, ergebnis):
    summen = angebot.summen()
    if pdf.get_y() + 30 > pdf.page_break_trigger:
        pdf.add_page()
    pdf.ln(4)
    pdf.set_draw_color(120, 120, 120)
    pdf.line(pdf.l_margin + 70, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(1.5)
    # Phase 26: Netto → USt → Gesamt-Betrag → − Rabatt (brutto) → = Endbetrag
    _summen_zeile(pdf, "Netto-Summe", summen["netto"])
    _summen_zeile(pdf, "19,00 % USt.", summen["ust"])
    if summen.get("rabatt"):
        _summen_zeile(pdf, "Gesamt-Betrag", summen["brutto"])
        bezeichnung = angebot.rabatt_bezeichnung
        _summen_zeile(pdf, "− Rabatt" + (f" ({bezeichnung})" if bezeichnung else ""),
                      summen["rabatt"])
        _summen_zeile(pdf, "= Endbetrag", summen["endbetrag"], fett=True)
    else:
        _summen_zeile(pdf, "Gesamt-Betrag", summen["brutto"], fett=True)

    if ergebnis is None:
        return
    if pdf.get_y() + 75 > pdf.page_break_trigger:
        pdf.add_page()
    pdf.ln(6)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 5.5, "Voraussichtliche KfW-Förderung", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)
    for name, wert, fett in ergebnis.zeilen:
        pdf.set_font("Arial", "B" if fett else "", 9)
        pdf.cell(100, 5, name)
        pdf.cell(70, 5, wert, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_font("Arial", "", 9)
    pdf.cell(0, 5, ergebnis.satz_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    _summen_zeile(pdf, "Angebotssumme (Endbetrag)", summen["endbetrag"])
    _summen_zeile(pdf, "− voraussichtliche Förderung", ergebnis.zuschuss_cent)
    # Eigenanteil hervorheben (Phase 26): fett, größer, dezente Hinterlegung
    pdf.ln(1)
    y = pdf.get_y()
    pdf.set_fill_color(232, 244, 229)
    pdf.rect(pdf.l_margin + 68, y - 0.8, pdf.w - pdf.r_margin - pdf.l_margin - 68, 9, "F")
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(44, 107, 34)
    pdf.set_x(pdf.l_margin + 70)
    pdf.cell(60, 7.5, "= Eigenanteil")
    pdf.cell(10, 7.5, "€")
    pdf.cell(30, 7.5, _euro_betrag(ergebnis.eigenanteil_cent), align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 5, ergebnis.programm, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for hinweis in ergebnis.hinweise:
        pdf.set_font("Arial", "", 8)
        pdf.multi_cell(0, 4, hinweis)
        pdf.ln(0.5)
    if ergebnis.disclaimer:
        pdf.ln(1)
        pdf.set_font("Arial", "I", 8)
        pdf.multi_cell(0, 4, ergebnis.disclaimer)


# --- Nachtexte A–D ---------------------------------------------------------

def _ueberschrift(pdf: AngebotsPdf, text: str, groesse=12):
    pdf.set_font("Arial", "B", groesse)
    pdf.multi_cell(0, 6, text)
    pdf.ln(2)


def _absatz(pdf: AngebotsPdf, text: str, fett=False, groesse=9):
    pdf.set_font("Arial", "B" if fett else "", groesse)
    pdf.multi_cell(0, 4.4, text)
    pdf.ln(1.5)


def _nachtext_rendern(pdf: AngebotsPdf, text: str,
                      signatur: dict | None = None) -> None:
    """v9: Nachtext-Blocktext rendern. Konventionen: "# " Seitenüberschrift ·
    "## " fette Zwischenzeile (10 pt) · "### " fette Absatz-Überschrift ·
    "---" allein = Seitenumbruch · "~ " kleine kursive Fußnote ·
    "[UNTERSCHRIFT]" = Ort/Datum-Unterschriftenblock (inkl. elektronischer
    Signatur). Aufeinanderfolgende Zeilen bilden EINEN Absatz."""
    for seite in text.split("\n---\n"):
        pdf.add_page()
        puffer: list[str] = []

        def puffer_leeren():
            if puffer:
                _absatz(pdf, "\n".join(puffer))
                puffer.clear()

        for zeile in seite.splitlines():
            zeile = zeile.rstrip()
            if not zeile.strip():
                puffer_leeren()
                continue
            if zeile.strip() == "[UNTERSCHRIFT]":
                puffer_leeren()
                _unterschrift_block(pdf, signatur)
            elif zeile.startswith("# "):
                puffer_leeren()
                _ueberschrift(pdf, zeile[2:])
            elif zeile.startswith("## "):
                puffer_leeren()
                _absatz(pdf, zeile[3:], fett=True, groesse=10)
            elif zeile.startswith("### "):
                puffer_leeren()
                _absatz(pdf, zeile[4:], fett=True)
            elif zeile.startswith("~ "):
                puffer_leeren()
                pdf.set_font("Arial", "I", 7.5)
                pdf.multi_cell(0, 3.8, zeile[2:])
                pdf.ln(1)
            else:
                puffer.append(zeile)
        puffer_leeren()


def _unterschrift_block(pdf: AngebotsPdf, signatur: dict | None = None) -> None:
    """Ort/Datum + Unterschrift des Auftraggebers; mit elektronischer
    Signatur (Phase 23) wird Bild + Name + Zeitstempel eingebettet."""
    if signatur is None:
        pdf.ln(14)
        pdf.set_font("Arial", "", 9)
        pdf.cell(85, 4.5, "." * 47, new_x=XPos.RIGHT)
        pdf.cell(0, 4.5, "." * 54, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(85, 4.5, "Ort, Datum")
        pdf.cell(0, 4.5, "Unterschrift des Auftraggebers")
    else:
        pdf.ln(6)
        y = pdf.get_y()
        pdf.image(signatur["png_pfad"], x=pdf.l_margin + 85, y=y, w=60)
        pdf.set_xy(pdf.l_margin, y + 26)
        pdf.set_font("Arial", "", 9)
        pdf.cell(85, 4.5, signatur["zeit"].strftime("%d.%m.%Y, %H:%M Uhr"),
                 new_x=XPos.RIGHT)
        pdf.cell(0, 4.5, signatur["name"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(120, 120, 120)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 75, pdf.get_y())
        pdf.line(pdf.l_margin + 85, pdf.get_y(), pdf.l_margin + 160, pdf.get_y())
        pdf.cell(85, 4.5, "Ort, Datum")
        pdf.cell(0, 4.5, "Unterschrift des Auftraggebers", new_x=XPos.LMARGIN,
                 new_y=YPos.NEXT)
        pdf.ln(2)
        pdf.set_font("Arial", "I", 8)
        pdf.multi_cell(0, 4, f"Elektronisch signiert von {signatur['name']} am "
                             f"{signatur['zeit'].strftime('%d.%m.%Y um %H:%M Uhr')} "
                             "(einfache elektronische Signatur, erfasst im Friondo "
                             "Angebotstool).")


def _nachtext_d(pdf: AngebotsPdf, kunde: Kunde, angebot: Angebot | None = None):
    """Vollmacht-Seite (Nachtext D). Muss komplett – inklusive Ort/Datum und
    beider Unterschriftszeilen – auf EINER Seite bleiben (Referenz AN250096
    Seite 11): kompakte Zeilenhöhen plus Keep-together am Schluss (der
    Unterschriftenblock wird notfalls ohne automatischen Umbruch in die
    Reserve vor der Fußzeile gezeichnet, nie auf eine eigene Seite)."""
    from app import anhaenge as anhaenge_modul
    pdf.add_page()
    _ueberschrift(pdf, "Vollmacht zur Beauftragung der SpotmyEnergy GmbH sowie zur "
                       "Anmeldung und Inbetriebsetzung von Anlagen", groesse=11)

    def absatz(text, fett=False):
        pdf.set_font("Arial", "B" if fett else "", 8.5)
        pdf.multi_cell(0, 3.9, text)
        pdf.ln(1.2)

    absatz("Ich bevollmächtige als zukünftiger Anlagenbetreiber und "
           "Gebäudeeigentümer die Friondo GmbH, in meinem Namen alle erforderlichen "
           "Schritte zur Beauftragung der SpotmyEnergy GmbH als Messstellenbetreiber "
           "und/oder Stromlieferant einzuleiten und entsprechende Verträge "
           "abzuschließen. Dies umfasst auch die Erteilung eines "
           "SEPA-Lastschriftmandats für damit verbundene Zahlungen.")
    absatz("Die Vollmacht gilt ebenfalls für die Friondo GmbH sowie deren "
           "Nachunternehmer zur Anmeldung, Inbetriebnahme, Änderung, Erweiterung "
           "oder Abmeldung folgender Anlagen und Verbrauchseinrichtungen beim "
           "zuständigen Netzbetreiber oder Energieversorgungsunternehmen:")
    absatz("Photovoltaikanlagen, Wärmepumpen, Ladeeinrichtungen/Wallboxen sowie "
           "sonstige steuerbare Verbrauchseinrichtungen gemäß § 14a EnWG "
           "(Modul 1, 2 oder 3).")
    absatz("Die Vollmacht umfasst insbesondere die An- und Abmeldung von Zählern, "
           "die Beantragung neuer Zähler, die Einreichung und Entgegennahme "
           "erforderlicher Unterlagen, die Kommunikation mit Netzbetreibern, "
           "Messstellenbetreibern und Stromlieferanten, die Kündigung bestehender "
           "Verträge, die Durchführung eines Anbieterwechsels sowie die Beauftragung "
           "und Betreuung eines intelligenten Messsystems.")
    absatz("Die Vollmacht gilt ausschließlich für die genannten Zwecke und erlischt "
           "nach Abschluss des beauftragten Vorgangs. Sie kann jederzeit schriftlich "
           "widerrufen werden.")
    pdf.ln(1)
    absatz("Angaben zur Verbrauchsstelle", fett=True)
    name = kunde.firma or " ".join(t for t in (kunde.vorname, kunde.nachname) if t)
    adresse = f"{kunde.strasse}, {kunde.plz} {kunde.ort}".strip(", ")
    pdf.set_font("Arial", "", 8.5)
    for beschriftung, wert in [("Name:", name), ("Adresse:", adresse),
                               ("Geburtsdatum:", ""), ("Telefon:", kunde.telefon),
                               ("E-Mail:", kunde.email)]:
        pdf.cell(28, 5.2, beschriftung)
        pdf.cell(0, 5.2, wert if wert else "_" * 60, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)
    # Ankreuzfelder: seit v8 bewusst wieder ALLE leer – der Kunde kreuzt
    # selbst an (das v5-Auto-Vorbelegen entfällt auf Kundenwunsch)
    kreuze = {"messstellenbetreiber": False, "stromlieferant": False, "anmeldung": False}

    def kasten(gesetzt):
        return "[X]" if gesetzt else "[  ]"

    absatz("Bitte ankreuzen:", fett=True)
    absatz(f"{kasten(kreuze['messstellenbetreiber'])} Messstellenbetreiber und "
           f"{kasten(kreuze['stromlieferant'])} Stromlieferant\n"
           f"{kasten(kreuze['anmeldung'])} Anmeldung/Inbetriebnahme/Änderung/Erweiterung/Abmeldung")
    absatz("SEPA-Lastschriftmandat", fett=True)
    absatz("Ich ermächtige den Zahlungsempfänger, fällige Zahlungen mittels "
           "Lastschrift von folgendem Konto einzuziehen.")
    pdf.set_font("Arial", "", 8.5)
    for beschriftung in ["Kontoinhaber:", "Adresse:", "IBAN:", "Kreditinstitut:"]:
        pdf.cell(28, 5.2, beschriftung)
        pdf.cell(0, 5.2, "_" * 60, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Keep-together: Ort/Datum + beide Unterschriften als ein Block; passt er
    # nicht mehr vor die Umbruchgrenze, in die Reserve vor der Fußzeile
    # zeichnen (Auto-Umbruch aus – Platz bis zur Fußzeile reicht), damit der
    # Block nie allein auf einer letzten Seite steht.
    block_hoehe = 5.2 + 2.5 + 6 + 6
    if pdf.get_y() + block_hoehe > pdf.page_break_trigger:
        pdf.set_auto_page_break(False)
    pdf.cell(28, 5.2, "Ort, Datum:")
    pdf.cell(0, 5.2, "_" * 60, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2.5)
    pdf.cell(0, 6, "Unterschrift Vollmachtgeber: ______________________",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, "Unterschrift Kontoinhaber, sofern abweichend: ______________________",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_auto_page_break(True, 42)


# --- Einstieg für Router ---------------------------------------------------

def signiertes_pdf_erzeugen(session, angebot: Angebot, png_bytes: bytes,
                            name: str, zeit) -> Path:
    """Erzeugt das signierte PDF unter data/angebote/signiert/ (Phase 23)."""
    import tempfile

    from app import anhaenge
    from app import logik as logik_modul
    kunde = session.get(Kunde, angebot.kunde_id)
    ergebnis = None
    kfw_daten = json.loads(angebot.kfw_json or "{}")
    if kfw_daten.get("O01") and not angebot.foerderung_ausblenden:
        logik, _ = logik_modul.hole_logik(session)
        parameter, _warn = kfw.parameter_lesen(logik)
        eingaben = kfw.eingaben_aus_antworten(kfw_daten, angebot.summen()["endbetrag"])
        if eingaben is not None:
            ergebnis = kfw.ergebnis_fuer_angebot(parameter, eingaben, angebot)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as datei:
        datei.write(png_bytes)
        png_pfad = datei.name
    try:
        ziel = config.SIGNIERT_ORDNER / f"{angebot.nummer}-signiert.pdf"
        from app import angebotsprofile
        return erzeuge_pdf(angebot, kunde, ergebnis,
                           mit_vollmacht=(anhaenge.vollmacht_erforderlich(angebot)
                                          and angebotsprofile.vollmacht_erlaubt(session, angebot)),
                           signatur={"png_pfad": png_pfad, "name": name, "zeit": zeit},
                           ziel=ziel,
                           vortext_text=angebotsprofile.vortext_fuer_angebot(session, angebot),
                           nachtext_text=angebotsprofile.nachtext_fuer_angebot(session, angebot),
                           ersetzt_hinweis=_ersetzt_hinweis(session, angebot))
    finally:
        Path(png_pfad).unlink(missing_ok=True)


def _ersetzt_hinweis(session, angebot: Angebot) -> str:
    """v9: „Ersetzt Angebot <Nr.> vom <Datum>“ für neue Versionen."""
    if not getattr(angebot, "vorgaenger_id", None):
        return ""
    vorgaenger = session.get(Angebot, angebot.vorgaenger_id)
    if vorgaenger is None:
        return ""
    return (f"Ersetzt Angebot {vorgaenger.nummer} "
            f"vom {vorgaenger.datum.strftime('%d.%m.%Y')}")


def pdf_fuer_angebot(session, angebot: Angebot) -> Path:
    """Erzeugt das PDF inkl. KfW-Block (falls Konfigurator-Daten vorliegen);
    Vollmacht-Seite nur bei iMSys/SpotDynamic im Angebot."""
    from app import anhaenge
    from app import logik as logik_modul
    kunde = session.get(Kunde, angebot.kunde_id)
    ergebnis = None
    kfw_daten = json.loads(angebot.kfw_json or "{}")
    if kfw_daten.get("O01") and not angebot.foerderung_ausblenden:
        logik, _ = logik_modul.hole_logik(session)
        parameter, _warn = kfw.parameter_lesen(logik)
        eingaben = kfw.eingaben_aus_antworten(kfw_daten, angebot.summen()["endbetrag"])
        if eingaben is not None:
            ergebnis = kfw.ergebnis_fuer_angebot(parameter, eingaben, angebot)
    from app import angebotsprofile
    return erzeuge_pdf(angebot, kunde, ergebnis,
                       mit_vollmacht=(anhaenge.vollmacht_erforderlich(angebot)
                                      and angebotsprofile.vollmacht_erlaubt(session, angebot)),
                       vortext_text=angebotsprofile.vortext_fuer_angebot(session, angebot),
                       nachtext_text=angebotsprofile.nachtext_fuer_angebot(session, angebot),
                       ersetzt_hinweis=_ersetzt_hinweis(session, angebot))
