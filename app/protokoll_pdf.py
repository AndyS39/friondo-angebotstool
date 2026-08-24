# Protokoll-PDF (Phase 25): schlichtes Abfrageprotokoll zum Download an
# Erfassung und Angebot – Kopf mit Kunde/Datum/Vertriebler, Fragen je
# Kategorie, AMPEL-Auslöser farblich hervorgehoben mit Grund.

from datetime import datetime
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app import config

ASSETS = Path(__file__).resolve().parent / "static" / "pdf"
ARIAL = Path(r"C:\Windows\Fonts")
DUNKELBLAU = (27, 42, 94)
AMPEL_ROT = (192, 57, 43)
AMPEL_HINTERGRUND = (253, 236, 236)


class ProtokollPdf(FPDF):
    def __init__(self, titelzeile: str):
        super().__init__("P", "mm", "A4")
        self.titelzeile = titelzeile
        self.set_margins(20, 16, 20)
        self.set_auto_page_break(True, 20)
        self.add_font("Arial", "", ARIAL / "arial.ttf")
        self.add_font("Arial", "B", ARIAL / "arialbd.ttf")
        self.add_font("Arial", "I", ARIAL / "ariali.ttf")

    def header(self):
        self.image(ASSETS / "friondo_logo.png", x=self.w - self.r_margin - 30, y=10, w=30)
        self.set_font("Arial", "B", 12)
        self.set_text_color(*DUNKELBLAU)
        self.set_xy(self.l_margin, 12)
        self.cell(0, 6, "Abfrageprotokoll", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Arial", "", 9)
        self.set_text_color(90, 90, 90)
        self.cell(0, 5, self.titelzeile, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)
        self.ln(3)

    def footer(self):
        self.set_y(-14)
        self.set_font("Arial", "", 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, f"Friondo GmbH · internes Abfrageprotokoll · Seite {self.page_no()}",
                  align="C")


def erzeuge_protokoll_pdf(dateiname: str, titelzeile: str, kopfdaten: list[tuple[str, str]],
                          protokoll: list[dict], gruende: list[str],
                          freitext: str = "") -> Path:
    pdf = ProtokollPdf(titelzeile)
    pdf.add_page()

    # Kopfdaten (Kunde, Datum, Vertriebler, Ampel, ...)
    pdf.set_font("Arial", "", 9.5)
    for name, wert in kopfdaten:
        pdf.set_font("Arial", "B", 9.5)
        pdf.cell(42, 5.5, name)
        pdf.set_font("Arial", "", 9.5)
        pdf.multi_cell(0, 5.5, wert, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if gruende:
        pdf.ln(2)
        pdf.set_text_color(*AMPEL_ROT)
        pdf.set_font("Arial", "B", 9.5)
        pdf.multi_cell(0, 5, "Ampel: Individuell – " + " · ".join(gruende),
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    # Freitext-Erfassung (v7): freie Beschreibung als eigener Block – der
    # Übergabezettel für TAIFUN; ggf. folgen darunter die Teilantworten
    if freitext:
        pdf.set_font("Arial", "B", 10.5)
        pdf.set_text_color(*DUNKELBLAU)
        pdf.cell(0, 6, "Freitext-Erfassung", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
        pdf.set_draw_color(200, 205, 215)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(1.5)
        pdf.set_font("Arial", "", 9.5)
        pdf.multi_cell(0, 5, freitext, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if protokoll:
            pdf.ln(3)
            pdf.set_font("Arial", "B", 10.5)
            pdf.set_text_color(*DUNKELBLAU)
            pdf.cell(0, 6, "Teilantworten aus dem Katalog (vor dem Wechsel in den Freitext)",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    # Fragen je Kategorie
    aktuelle_seite = None
    for eintrag in protokoll:
        if pdf.get_y() > pdf.page_break_trigger - 16:
            pdf.add_page()
            aktuelle_seite = None
        if eintrag["seite"] != aktuelle_seite:
            aktuelle_seite = eintrag["seite"]
            pdf.ln(2)
            pdf.set_font("Arial", "B", 10.5)
            pdf.set_text_color(*DUNKELBLAU)
            pdf.cell(0, 6, aktuelle_seite, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
            pdf.set_draw_color(200, 205, 215)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(1.5)

        ampel = bool(eintrag.get("ampel_grund"))
        if ampel:
            # AMPEL-Auslöser: rot hinterlegt + Grund (Phase 25)
            y_start = pdf.get_y()
            text = (f"{eintrag['frage_id']} · {eintrag['frage']}\n"
                    f"Antwort: {eintrag['antwort']}\n"
                    f"AMPEL – individuell: {eintrag['ampel_grund']}")
            zeilen = pdf.multi_cell(pdf.epw, 4.6, text, dry_run=True, output="LINES")
            pdf.set_fill_color(*AMPEL_HINTERGRUND)
            pdf.rect(pdf.l_margin, y_start - 0.5, pdf.epw, len(zeilen) * 4.6 + 1.5, "F")
            pdf.set_font("Arial", "", 8.5)
            pdf.set_text_color(*AMPEL_ROT)
            pdf.multi_cell(0, 4.6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1.2)
        else:
            pdf.set_font("Arial", "", 8.5)
            pdf.set_text_color(90, 90, 90)
            pdf.multi_cell(0, 4.4, f"{eintrag['frage_id']} · {eintrag['frage']}",
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Arial", "B", 9)
            pdf.multi_cell(0, 4.6, eintrag["antwort"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1.2)

    config.ANGEBOTE_PDF_ORDNER.mkdir(parents=True, exist_ok=True)
    ziel = config.ANGEBOTE_PDF_ORDNER / dateiname
    pdf.output(str(ziel))
    return ziel
