# Projektsteckbrief als einseitige PDF (v15, Phase 79) – Anhang der
# Sub-Mails und später des Montage-Backends. Muster wie protokoll_pdf.py
# (Arial-TTF für Umlaute, Friondo-Logo, schlichte Label/Wert-Tabelle).

from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

ARIAL = Path(r"C:\Windows\Fonts")
DUNKELBLAU = (27, 42, 94)
LOGO = Path(__file__).parent / "static" / "pdf" / "friondo_logo.png"


class _SteckbriefPdf(FPDF):
    def __init__(self):
        super().__init__(format="A4")
        self.set_margins(20, 16, 20)
        self.set_auto_page_break(True, margin=20)
        for stil, datei in (("", "arial.ttf"), ("B", "arialbd.ttf"),
                            ("I", "ariali.ttf")):
            self.add_font("Arial", stil, ARIAL / datei)

    def header(self):
        if LOGO.exists():
            self.image(str(LOGO), x=150, y=12, w=40)
        self.set_font("Arial", "B", 15)
        self.set_text_color(*DUNKELBLAU)
        self.cell(0, 10, "Projektsteckbrief",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def footer(self):
        self.set_y(-14)
        self.set_font("Arial", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, "Friondo GmbH · automatisch erstellt aus dem "
                        "Angebotstool", align="C")


def steckbrief_pdf_bytes(session, gewerk) -> bytes:
    """Eine Seite: Projektkopf + Steckbrief-Felder der Sparte als Tabelle."""
    from app import projektierung as kern
    from app.models import Kunde, Projekt

    projekt = session.get(Projekt, gewerk.projekt_id)
    kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
    werte = kern.steckbrief_daten(session, [gewerk.id])[gewerk.id]

    pdf = _SteckbriefPdf()
    pdf.add_page()
    pdf.set_font("Arial", "", 10)
    kopf = [
        ("Projekt", projekt.nummer if projekt else "–"),
        ("Kunde", kunde.anzeige_name if kunde else "–"),
        ("Ausführungsadresse",
         " ".join(t for t in [projekt.ausfuehrung_strasse,
                              f"{projekt.ausfuehrung_plz} "
                              f"{projekt.ausfuehrung_ort}".strip()]
                  if t) if projekt else "–"),
        ("Telefon Kunde", (kunde.telefon if kunde else "") or "–"),
        ("Gewerk", gewerk.sparte),
    ]
    for name, wert in kopf:
        pdf.set_font("Arial", "B", 10)
        pdf.cell(55, 6, name)
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 6, str(wert), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*DUNKELBLAU)
    pdf.cell(0, 7, "Steckbrief", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    for feld, name in kern.steckbrief_felder(gewerk.sparte):
        eintrag = werte.get(feld)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(55, 6, name)
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 6, (eintrag.wert if eintrag else "") or "–",
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())
