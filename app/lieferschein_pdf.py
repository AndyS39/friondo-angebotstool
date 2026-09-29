# Lieferschein (v13, PLAN_V13 Phase 80): spartenübergreifend für Angebote im
# Status „Angenommen“. Friondo-Layout wie das Angebots-PDF (Logo-Leiste,
# Fußzeile), Ausführungsort, Positionsliste mit Nummer, Bezeichnung, gekürzter
# Beschreibung und Menge – OHNE Preise, Summen, Rabatte und Förderung.
# EP-, Alternativ- und bauseits-Positionen sowie reine Textzeilen (ohne
# Artikelnummer und ohne Preis, z. B. die Auslegungszeile) entfallen.
# Abschluss: Unterschriftszeile „Ware vollständig erhalten“ mit Datum.

from pathlib import Path

from fpdf.enums import XPos, YPos

from app import config
from app.models import Angebot, Kunde
from app.pdf_export import ABSENDERZEILE, AngebotsPdf, FOLGESEITEN_LOGO, ASSETS, _menge_text

MAX_BESCHREIBUNG_ZEILEN = 3
MAX_BESCHREIBUNG_ZEICHEN = 220


class LieferscheinPdf(AngebotsPdf):
    def header(self):
        if self.page_no() == 1:
            self._logo_leiste()
            return
        datei, x, y, breite = FOLGESEITEN_LOGO
        self.image(ASSETS / datei, x=x, y=y, w=breite)
        self.set_font("Arial", "B", 10)
        self.set_xy(self.l_margin, 46)
        self.cell(120, 6, f"L I E F E R S C H E I N  zu Angebot {self.nummer}")
        self.set_font("Arial", "", 10)
        self.set_x(169.4)
        self.cell(0, 6, f"Seite: {self.page_no()}")
        self.set_y(54.5)


def lieferschein_positionen(angebot: Angebot) -> list[tuple[str, object]]:
    """(Anzeigenummer, Position) der aufzuführenden Positionen."""
    ergebnis = []
    for position, nummer in zip(angebot.positionen, angebot.nummerierung()):
        if position.ep_flag or position.alternativ or position.bauseits:
            continue
        if not (position.pos_nr or "").strip() and not position.e_preis_cent:
            continue   # reine Textzeile (Auslegung, Vermerk)
        ergebnis.append((nummer, position))
    return ergebnis


def _kurztext(position) -> tuple[str, str]:
    """Bezeichnung (erste Zeile) + gekürzte Beschreibung."""
    zeilen = [z.strip() for z in (position.beschreibung or "").splitlines() if z.strip()]
    titel = (position.bezeichnung or "").strip()
    if not titel and zeilen:
        titel = zeilen.pop(0)
        if titel.lower().startswith("(optionale position") and zeilen:
            titel = zeilen.pop(0)
    elif zeilen and zeilen[0] == titel:
        zeilen.pop(0)
    rest = " · ".join(zeilen[:MAX_BESCHREIBUNG_ZEILEN])
    if len(rest) > MAX_BESCHREIBUNG_ZEICHEN or len(zeilen) > MAX_BESCHREIBUNG_ZEILEN:
        rest = rest[:MAX_BESCHREIBUNG_ZEICHEN].rstrip(" ·") + " …"
    return titel, rest


def erzeuge_lieferschein(angebot: Angebot, kunde: Kunde, ziel: Path | None = None) -> Path:
    pdf = LieferscheinPdf(angebot.nummer)
    pdf.add_page()
    pdf.set_font("Arial", "", 6.5)
    pdf.set_text_color(100, 100, 100)
    pdf.set_y(49.3)
    pdf.cell(0, 3, ABSENDERZEILE, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)

    y_start = pdf.get_y() + 3
    pdf.set_font("Arial", "", 10)
    pdf.set_xy(pdf.l_margin, y_start)
    # v20 (Phase 98): Lieferschein adressiert an die Lieferanschrift
    from app import anschriften
    empfaenger = anschriften.zeilen(anschriften.lieferung(angebot, kunde))
    pdf.multi_cell(100, 4.8, "\n".join(empfaenger))
    from datetime import date
    pdf.set_font("Arial", "", 9)
    rechts_x = pdf.w - pdf.r_margin - 55
    pdf.set_xy(rechts_x, y_start)
    pdf.cell(25, 4.6, "Datum")
    pdf.cell(30, 4.6, f": {date.today().strftime('%d.%m.%Y')}",
             new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.set_x(rechts_x)
    pdf.cell(25, 4.6, "Angebot")
    pdf.cell(30, 4.6, f": {angebot.nummer}", new_x=XPos.LEFT, new_y=YPos.NEXT)

    pdf.set_xy(pdf.l_margin, max(pdf.get_y(), y_start + 26) + 6)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, f"L I E F E R S C H E I N  zu Angebot {angebot.nummer}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Arial", "", 9)
    ausfuehrung = f"{kunde.strasse}, {kunde.plz} {kunde.ort}".strip(", ")
    pdf.cell(0, 5, f"Ausführungsort: {ausfuehrung}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if anschriften.lieferzeile(angebot, kunde):
        pdf.multi_cell(0, 5, "Lieferanschrift: "
                       + anschriften.einzeilig(anschriften.lieferung(angebot, kunde)))
    pdf.ln(4)

    breiten = {"pos": 14, "menge": 16, "einheit": 14, "text": 126}

    def kopf():
        pdf.set_font("Arial", "B", 8)
        pdf.cell(breiten["pos"], 4.5, "Position")
        pdf.cell(breiten["menge"], 4.5, "Menge", align="R")
        pdf.cell(breiten["einheit"], 4.5, " Einh.")
        pdf.cell(breiten["text"], 4.5, "Bezeichnung", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1.5)

    kopf()
    text_x = pdf.l_margin + breiten["pos"] + breiten["menge"] + breiten["einheit"]
    for nummer, position in lieferschein_positionen(angebot):
        titel, rest = _kurztext(position)
        pdf.set_font("Arial", "", 8)
        zeilen = pdf.multi_cell(breiten["text"], 3.7, titel + ("\n" + rest if rest else ""),
                                dry_run=True, output="LINES")
        if pdf.get_y() + len(zeilen) * 3.7 + 3 > pdf.page_break_trigger:
            pdf.add_page()
            kopf()
        y = pdf.get_y()
        pdf.set_font("Arial", "", 8)
        pdf.cell(breiten["pos"], 3.7, nummer)
        pdf.cell(breiten["menge"], 3.7, _menge_text(position.menge), align="R")
        pdf.cell(breiten["einheit"], 3.7, " " + (position.einheit or ""))
        pdf.set_xy(text_x, y)
        pdf.set_font("Arial", "B", 8)
        pdf.multi_cell(breiten["text"], 3.7, titel)
        if rest:
            pdf.set_x(text_x)
            pdf.set_font("Arial", "", 7.5)
            pdf.multi_cell(breiten["text"], 3.5, rest)
        pdf.ln(2)

    # Unterschrift „Ware vollständig erhalten“ – Block bleibt zusammen
    if pdf.get_y() + 32 > pdf.page_break_trigger:
        pdf.add_page()
    pdf.ln(8)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 5, "Ware vollständig erhalten", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(12)
    pdf.set_font("Arial", "", 9)
    pdf.cell(85, 4.5, "." * 47, new_x=XPos.RIGHT)
    pdf.cell(0, 4.5, "." * 54, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(85, 4.5, "Ort, Datum")
    pdf.cell(0, 4.5, "Unterschrift Empfänger", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    ordner = config.ANGEBOTE_PDF_ORDNER / "lieferscheine"
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ziel or ordner / f"LS-{angebot.nummer}.pdf"
    pdf.output(str(ziel))
    return ziel
