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

# Logo-Leiste Seite 1 (Reihenfolge lt. ANGEBOTSTEXTE.md)
LOGO_LEISTE = ["badge_innung.png", "badge_bosch_premium.png", "badge_energy_awards.png",
               "friondo_logo.png", "badge_fachbetrieb_wp.png", "badge_bosch_split.png"]


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
            self.set_font("Arial", "B", 10)
            self.set_xy(self.l_margin, 12)
            self.cell(110, 6, f"A N G E B O T - Nr.: {self.nummer}")
            self.set_font("Arial", "", 10)
            self.cell(30, 6, f"Seite: {self.page_no()}")
            self.image(ASSETS / "friondo_logo_gross.png", x=self.w - 58, y=8, w=38)
            self.set_y(26)

    def _logo_leiste(self):
        """Sechs Badges nebeneinander am oberen Rand von Seite 1 (in Box eingepasst)."""
        hoehe = 13.0
        max_breite = 32.0
        luecke = 3.0
        masse = []
        for name in LOGO_LEISTE:
            from PIL import Image
            with Image.open(ASSETS / name) as im:
                b, h = im.size
            seitenverhaeltnis = b / h
            breite = hoehe * seitenverhaeltnis
            if breite > max_breite:
                breite = max_breite
            masse.append((name, breite, breite / seitenverhaeltnis))
        gesamt = sum(b for _, b, _ in masse) + luecke * (len(masse) - 1)
        x = self.l_margin + max(0.0, (self.inhaltsbreite - gesamt) / 2)
        for name, breite, bild_hoehe in masse:
            self.image(ASSETS / name, x=x, y=10 + (hoehe - bild_hoehe) / 2, w=breite)
            x += breite + luecke
        self.set_y(28)

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
                kfw_ergebnis: "kfw.KfwErgebnis | None" = None) -> Path:
    pdf = AngebotsPdf(angebot.nummer)
    _seite1(pdf, angebot, kunde)
    _positionsteil(pdf, angebot)
    _summen_und_kfw(pdf, angebot, kfw_ergebnis)
    _nachtext_a(pdf)
    _nachtext_b(pdf)
    _nachtext_c(pdf)
    _nachtext_d(pdf, kunde)

    config.ANGEBOTE_PDF_ORDNER.mkdir(parents=True, exist_ok=True)
    ziel = config.ANGEBOTE_PDF_ORDNER / f"{angebot.nummer}.pdf"
    pdf.output(str(ziel))
    return ziel


# --- Seite 1: Briefkopf + Vortext ----------------------------------------

def _seite1(pdf: AngebotsPdf, angebot: Angebot, kunde: Kunde):
    pdf.add_page()

    pdf.set_font("Arial", "", 6.5)
    pdf.set_text_color(100, 100, 100)
    pdf.set_y(34)
    pdf.cell(0, 3, ABSENDERZEILE, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)

    # Empfängerblock links, Seite/Datum/Kunden-Nr. rechts
    y_start = pdf.get_y() + 3
    pdf.set_font("Arial", "", 10)
    pdf.set_xy(pdf.l_margin, y_start)
    empfaenger = []
    if kunde.firma:
        empfaenger.append(kunde.firma)
    person = " ".join(t for t in (kunde.anrede if kunde.anrede != "Firma" else "",
                                  kunde.vorname, kunde.nachname) if t)
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
    pdf.set_x(rechts_x)
    pdf.cell(25, 4.6, "Kunden-Nr.")
    pdf.cell(30, 4.6, f": {kunde.kunden_nr}", new_x=XPos.LEFT, new_y=YPos.NEXT)

    pdf.set_xy(pdf.l_margin, max(pdf.get_y(), y_start + 26) + 6)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, f"A N G E B O T - Nr.: {angebot.nummer}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # Vortext lt. ANGEBOTSTEXTE.md
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 5, "Ihr individuelles Wärmepumpen-Angebot zum Festpreis",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 5, "Effizienz, Komfort und zukunftssicher",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)
    pdf.set_font("Arial", "", 9)
    pdf.multi_cell(0, 4.4,
                   "Sehr geehrte Damen und Herren,\n\n"
                   "vielen Dank für Ihr Vertrauen in die Friondo GmbH. Sie haben eine "
                   "zukunftssichere Entscheidung getroffen – eine moderne Wärmepumpe senkt "
                   "Ihre Energiekosten, steigert den Wohnkomfort und macht Sie unabhängiger "
                   "von fossilen Brennstoffen.\n\n"
                   "Anbei erhalten Sie Ihr maßgeschneidertes Angebot. Darin enthalten sind:")
    pdf.ln(1.5)
    for text in [
        "Ihre individuelle Wärmepumpe – optimal dimensioniert für Ihre Immobilie",
        "Detaillierte Installationsleistungen – fachgerecht, sauber und termingerecht",
        "Transparent und Festpreis – klar verständlich und ohne versteckte Kosten",
        "Unser Rundum-Sorglos-Service – von der Planung bis zur Inbetriebnahme",
    ]:
        pdf.haken_zeile(text)
    pdf.ln(2)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 5, "Warum Friondo?", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)
    pdf.set_font("Arial", "", 9)
    for text in [
        "Fachkompetenz & Qualität – Als Meisterbetrieb, Mitglied der Innung und "
        "VDI-zertifiziertes Fachunternehmen setzen wir auf höchste Standards.",
        "Zertifizierte Sachkundige für Wärmepumpensysteme nach VDI 4650 – Fundiertes "
        "Fachwissen und tiefgehender Expertise der Wärmepumpentechnik.",
        "Persönliche Beratung – Wir begleiten Sie von der ersten Idee bis zur perfekten "
        "Lösung für Ihr Zuhause.",
        "Effizienz & Nachhaltigkeit – Unsere Systeme senken Ihren Energieverbrauch spürbar "
        "und steigern den Wert Ihrer Immobilie.",
        "Fördermittel-Check & Unterstützung – Wir helfen Ihnen, maximale staatliche "
        "Zuschüsse zu nutzen.",
    ]:
        pdf.haken_zeile(text, fett_bis=" – ")
    pdf.ln(2)
    pdf.set_font("Arial", "B", 9)
    pdf.multi_cell(0, 4.4, "Wir sind auf Wärmepumpen spezialisiert und gehören in der "
                           "Region zu den führenden Anbieter.")
    pdf.set_font("Arial", "", 9)
    pdf.multi_cell(0, 4.4, "Lassen Sie uns gemeinsam Ihre Heizung zukunftsfähig machen!\n\n"
                           "Ihr Friondo-Team")


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

    for position in angebot.positionen:
        text = position.beschreibung or ""
        if position.bezeichnung and position.bezeichnung not in text.splitlines()[:1]:
            text = position.bezeichnung + ("\n" + text if text else "")

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
            _uebertrag_zeile(pdf, uebertrag_cent)
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
        pdf.cell(SPALTEN["pos"], zeilenhoehe, position.pos_nr)
        pdf.cell(SPALTEN["menge"], zeilenhoehe, _menge_text(position.menge), align="R")
        pdf.cell(SPALTEN["einheit"], zeilenhoehe, " " + position.einheit)

        text_x = pdf.l_margin + SPALTEN["pos"] + SPALTEN["menge"] + SPALTEN["einheit"]
        pdf.set_xy(text_x, y_start)
        pdf.multi_cell(text_breite, zeilenhoehe, text)
        y_ende = pdf.get_y()

        # Preise auf Höhe der letzten Textzeile (wie im Referenz-PDF)
        pdf.set_xy(text_x + text_breite, y_ende - zeilenhoehe)
        pdf.cell(SPALTEN["e_preis"], zeilenhoehe, _euro_betrag(position.e_preis_cent), align="R")
        if position.ep_flag:
            pdf.cell(SPALTEN["g_preis"], zeilenhoehe, "EP.", align="R")
        else:
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
    _summen_zeile(pdf, "Netto-Summe", summen["netto"])
    _summen_zeile(pdf, "19,00 % USt.", summen["ust"])
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
    _summen_zeile(pdf, "Angebotssumme (brutto)", summen["brutto"])
    _summen_zeile(pdf, "− voraussichtliche Förderung", ergebnis.zuschuss_cent)
    _summen_zeile(pdf, "= Eigenanteil", ergebnis.eigenanteil_cent, fett=True)
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


def _nachtext_a(pdf: AngebotsPdf):
    pdf.add_page()
    _ueberschrift(pdf, "Ihre Zahlungsoptionen bei Friondo")
    _absatz(pdf, "Barkauf oder Finanzierung", fett=True, groesse=10)
    _absatz(pdf, "Saubere Energie. Faire Raten. Maximale Freiheit.")
    _absatz(pdf, "Finanzierung mit Cloover", fett=True, groesse=10)
    _absatz(pdf, "Investieren Sie jetzt in Ihre Energie- oder Wärmelösung – ohne hohe "
                 "Einmalzahlung und bequem in festen Monatsraten über bis zu 20 Jahre.")
    _absatz(pdf, "Sofort starten", fett=True)
    _absatz(pdf, "• Keine Anzahlung, Keine Grundbuchbelastung, Schnelle - digitale Prüfung, "
                 "Finanzierungszusage in wenigen Minuten, 100 % digital, Kein Papierkram "
                 "und keine Banktermine")
    _absatz(pdf, "Planbare Monatsraten – Zum Beispiel:", fett=True)
    _absatz(pdf, "• Wärmepumpe ab 129 € pro Monat mit Förderung*\n"
                 "• Oder ab 250 € pro Monat ohne Förderung")
    _absatz(pdf, "So bleibt Ihr Budget flexibel und Ihre Energiekosten sinken langfristig.")
    _absatz(pdf, "Maximale Flexibilität", fett=True)
    _absatz(pdf, "• Kostenlose Sondertilgungen\n"
                 "• Vorzeitige Rückzahlung ohne Strafgebühren\n"
                 "• Individuell anpassbare Laufzeiten")
    _absatz(pdf, "Ihre Vorteile", fett=True)
    _absatz(pdf, "• Sofort investieren · Monatlich entspannt zahlen · Energiekosten senken · "
                 "Unabhängiger werden")
    _absatz(pdf, "Kundenzufriedenheit: 4,8 von 5", fett=True)
    _absatz(pdf, "„Dank Cloover konnten wir unsere Wärmepumpe einfach, fair und transparent "
                 "finanzieren.“")
    _absatz(pdf, "Starten Sie jetzt mit Friondo und Cloover in eine nachhaltige Zukunft.")
    pdf.set_font("Arial", "I", 7.5)
    pdf.multi_cell(0, 3.8, "*Beispielrate auf Basis einer Angebotssumme von 29.000 €, einer "
                           "Förderung von 56 %, gedeckelt auf 28.000 €, und einer Laufzeit "
                           "von 20 Jahren.")


def _nachtext_b(pdf: AngebotsPdf):
    pdf.add_page()
    _ueberschrift(pdf, "Installationsvoraussetzungen")
    _absatz(pdf, "Haftungsbegrenzung", fett=True)
    _absatz(pdf, "Technische und kaufmännische Angaben sind freibleibend. Sie werden erst "
                 "durch eine nachfolgende Auftragsbestätigung verbindlich.")
    _absatz(pdf, "Rücktrittsrecht im Zusammenhang mit Technischer Feinplanung", fett=True)
    _absatz(pdf, "Die in diesem Vertrag vorgesehenen Verpflichtungen und (Liefer-)Leistungen "
                 "setzen eine eingehende technische Feinplanung voraus, um sicherzustellen, "
                 "dass das Vorhaben zu den vereinbarten Bedingungen umgesetzt werden kann. "
                 "Sollte die technische Feinplanung ergeben, dass die Umsetzung des Vorhabens "
                 "technisch nicht möglich ist oder nur mit erheblichem Mehraufwand erfolgen "
                 "kann, ist jede Vertragspartei – abweichend der AGB von Friondo – berechtigt, "
                 "von dem Vertrag zurückzutreten. Ein entsprechender Rücktritt ist innerhalb "
                 "von sechs (6) Wochen ab Kenntnisnahme in Textform gegenüber der jeweils "
                 "anderen Vertragspartei zu erklären.")
    _absatz(pdf, "Zahlung", fett=True)
    _absatz(pdf, "Eine Anzahlung von 50% des Angebotsbetrags ist spätestens 14 Tage vor "
                 "Arbeitsbeginn zu zahlen. Die Restzahlung wird mit der "
                 "Schlussrechnungsstellung fällig. Die Rechnung erhalten Sie im Anschluss "
                 "zur Installation.")
    _absatz(pdf, "Hinweis zur KfW-Förderung", fett=True)
    _absatz(pdf, "Der Wechsel zu einer klimafreundlichen Heizlösung kann unter bestimmten "
                 "Voraussetzungen durch Förderprogramme der Bundesregierung unterstützt "
                 "werden. Im Rahmen des Programms „Heizungsförderung für Privatpersonen – "
                 "Wohngebäude“ (Programmnummer 458) erfolgt die Förderung über die "
                 "Kreditanstalt für Wiederaufbau (KfW).")
    _absatz(pdf, "Bitte beachten Sie, dass weder der Anspruch auf Fördermittel noch deren "
                 "konkrete Höhe garantiert werden kann. Die abschließende Entscheidung über "
                 "Bewilligung und Umfang der Förderung liegt ausschließlich bei der KfW.")
    _absatz(pdf, "Die Ihnen kommunizierte, voraussichtliche Förderhöhe basiert auf den "
                 "Angaben, die im Beratungsgespräch erfasst wurden. Für die Richtigkeit und "
                 "Vollständigkeit dieser Informationen übernimmt Friondo keine Haftung. "
                 "Zudem wird bestätigt, dass sich die Antragsteller bei mehreren am Vorhaben "
                 "beteiligten Investoren über die Verteilung der Förderbeträge einvernehmlich "
                 "verständigt haben.")
    _absatz(pdf, "Eine Kombination bzw. Kumulierung der KfW-Förderung mit der steuerlichen "
                 "Förderung gemäß § 35 EStG ist ausgeschlossen. Antragsteller sind "
                 "verpflichtet, für dieselbe Maßnahme keinen zusätzlichen Antrag auf "
                 "steuerliche Förderung zu stellen. Voraussetzung für die Förderung von "
                 "Wärmepumpen ist außerdem, dass am vorgesehenen Installationsort kein "
                 "Anschluss- oder Benutzungszwang an ein Wärmenetz besteht. Die Prüfung "
                 "dieser Voraussetzung obliegt dem Kunden und muss vor Auftragserteilung "
                 "erfolgen.")
    _absatz(pdf, "Wir halten uns freibleibend 30 Tage an dieses Angebot gebunden.\n"
                 "Es gelten unsere Allgemeinen Geschäftsbedingungen, diese sind zu finden "
                 "unter: https://friondo.de/AGB\n"
                 "Informationen zu unserem Datenschutz finden Sie unter: "
                 "https://friondo.de/Datenschutz")


def _nachtext_c(pdf: AngebotsPdf):
    pdf.add_page()
    _absatz(pdf, "Wir sichern Ihnen eine fach- und zeitgerechte Ausführung aller "
                 "angebotenen Leistungen zu.")
    _absatz(pdf, "Sie haben Fragen oder wünschen weitere Informationen? Rufen Sie uns an - "
                 "wir sind für Sie da.")
    _absatz(pdf, "Mit freundlichen Grüßen,")
    _absatz(pdf, "Ihr Friondo-Team")
    pdf.ln(4)
    _absatz(pdf, "Sollte Ihnen das Angebot zusagen, senden Sie uns bitte zur "
                 "Auftragserteilung das unterschriebene Angebot zurück.")
    _absatz(pdf, "Aufschiebende Bedingung:", fett=True)
    _absatz(pdf, "Dieser Vertrag tritt hinsichtlich der Liefer- und Leistungspflichten zur "
                 "Umsetzung, erst und nur insoweit in Kraft, wenn und soweit die KfW den "
                 "Antrag zur Förderung Heizungstausch BEG EM bewilligt und die Förderung "
                 "mit einer Zusage gegenüber der antragstellenden Vertragspartei zugesagt "
                 "hat (aufschiebende Bedingung). Die antragstellende Vertragspartei wird "
                 "die jeweils andere Vertragspartei über den Eintritt und den Umfang des "
                 "Eintritts der Bedingung unverzüglich in Kenntnis setzen. Die Förderzusage "
                 "löst dann direkt den Vorhabensbeginn aus.")
    _absatz(pdf, "Voraussichtliches Datum der Umsetzung: ______________ ,liegt innerhalb "
                 "des Bewilligungszeitraum nach Nummer 9.4.1.")
    pdf.ln(14)
    pdf.set_font("Arial", "", 9)
    pdf.cell(85, 4.5, "." * 47, new_x=XPos.RIGHT)
    pdf.cell(0, 4.5, "." * 54, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(85, 4.5, "Ort, Datum")
    pdf.cell(0, 4.5, "Unterschrift des Auftraggebers")


def _nachtext_d(pdf: AngebotsPdf, kunde: Kunde):
    pdf.add_page()
    _ueberschrift(pdf, "Vollmacht zur Beauftragung der SpotmyEnergy GmbH sowie zur "
                       "Anmeldung und Inbetriebsetzung von Anlagen", groesse=11)
    _absatz(pdf, "Ich bevollmächtige als zukünftiger Anlagenbetreiber und "
                 "Gebäudeeigentümer die Friondo GmbH, in meinem Namen alle erforderlichen "
                 "Schritte zur Beauftragung der SpotmyEnergy GmbH als Messstellenbetreiber "
                 "und/oder Stromlieferant einzuleiten und entsprechende Verträge "
                 "abzuschließen. Dies umfasst auch die Erteilung eines "
                 "SEPA-Lastschriftmandats für damit verbundene Zahlungen.")
    _absatz(pdf, "Die Vollmacht gilt ebenfalls für die Friondo GmbH sowie deren "
                 "Nachunternehmer zur Anmeldung, Inbetriebnahme, Änderung, Erweiterung "
                 "oder Abmeldung folgender Anlagen und Verbrauchseinrichtungen beim "
                 "zuständigen Netzbetreiber oder Energieversorgungsunternehmen:")
    _absatz(pdf, "Photovoltaikanlagen, Wärmepumpen, Ladeeinrichtungen/Wallboxen sowie "
                 "sonstige steuerbare Verbrauchseinrichtungen gemäß § 14a EnWG "
                 "(Modul 1, 2 oder 3).")
    _absatz(pdf, "Die Vollmacht umfasst insbesondere die An- und Abmeldung von Zählern, "
                 "die Beantragung neuer Zähler, die Einreichung und Entgegennahme "
                 "erforderlicher Unterlagen, die Kommunikation mit Netzbetreibern, "
                 "Messstellenbetreibern und Stromlieferanten, die Kündigung bestehender "
                 "Verträge, die Durchführung eines Anbieterwechsels sowie die Beauftragung "
                 "und Betreuung eines intelligenten Messsystems.")
    _absatz(pdf, "Die Vollmacht gilt ausschließlich für die genannten Zwecke und erlischt "
                 "nach Abschluss des beauftragten Vorgangs. Sie kann jederzeit schriftlich "
                 "widerrufen werden.")
    pdf.ln(2)
    _absatz(pdf, "Angaben zur Verbrauchsstelle", fett=True)
    name = kunde.firma or " ".join(t for t in (kunde.vorname, kunde.nachname) if t)
    adresse = f"{kunde.strasse}, {kunde.plz} {kunde.ort}".strip(", ")
    pdf.set_font("Arial", "", 9)
    for beschriftung, wert in [("Name:", name), ("Adresse:", adresse),
                               ("Geburtsdatum:", ""), ("Telefon:", kunde.telefon),
                               ("E-Mail:", kunde.email)]:
        pdf.cell(30, 6, beschriftung)
        pdf.cell(0, 6, wert if wert else "_" * 60, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)
    _absatz(pdf, "Bitte ankreuzen:", fett=True)
    _absatz(pdf, "[  ] Messstellenbetreiber und [  ] Stromlieferant\n"
                 "[  ] Anmeldung/Inbetriebnahme/Änderung/Erweiterung/Abmeldung")
    pdf.ln(1)
    _absatz(pdf, "SEPA-Lastschriftmandat", fett=True)
    _absatz(pdf, "Ich ermächtige den Zahlungsempfänger, fällige Zahlungen mittels "
                 "Lastschrift von folgendem Konto einzuziehen.")
    for beschriftung in ["Kontoinhaber:", "Adresse:", "IBAN:", "Kreditinstitut:", "Ort, Datum:"]:
        pdf.cell(30, 6, beschriftung)
        pdf.cell(0, 6, "_" * 60, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
    pdf.cell(0, 6, "Unterschrift Vollmachtgeber: ______________________",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, "Unterschrift Kontoinhaber, sofern abweichend: ______________________",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)


# --- Einstieg für Router ---------------------------------------------------

def pdf_fuer_angebot(session, angebot: Angebot) -> Path:
    """Erzeugt das PDF inkl. KfW-Block (falls Konfigurator-Daten vorliegen)."""
    from app import logik as logik_modul
    kunde = session.get(Kunde, angebot.kunde_id)
    ergebnis = None
    kfw_daten = json.loads(angebot.kfw_json or "{}")
    if kfw_daten.get("O01"):
        logik, _ = logik_modul.hole_logik(session)
        parameter, _warn = kfw.parameter_lesen(logik)
        eingaben = kfw.eingaben_aus_antworten(kfw_daten, angebot.summen()["brutto"])
        if eingaben is not None:
            ergebnis = kfw.berechnen(parameter, eingaben)
    return erzeuge_pdf(angebot, kunde, ergebnis)
