# Lieferschein (v13, PLAN_V13 Phase 80): spartenübergreifend für Angebote im
# Status „Angenommen“. Friondo-Layout wie das Angebots-PDF (Logo-Leiste,
# Fußzeile), Ausführungsort, Positionsliste mit Nummer, Bezeichnung,
# Beschreibung und Menge – OHNE Preise, Summen, Rabatte und Förderung.
# EP-, Alternativ- und bauseits-Positionen sowie reine Textzeilen (ohne
# Artikelnummer und ohne Preis, z. B. die Auslegungszeile) entfallen.
# v24: Gruppen-Überschriften (z. B. „Klimaanlage Bosch“) wie im Angebots-PDF.
# Abschluss: Unterschriftszeile „Ware vollständig erhalten“ mit Datum.
# v30 (PLAN_V18 Phase 149): die Beschreibung erscheint VOLLSTÄNDIG (alle Zeilen,
# wie im Angebots-PDF inkl. editierter Texte/Textregeln, 7,5 pt; Seitenumbruch
# innerhalb langer Texte erlaubt, der Tabellenkopf wiederholt sich über header()) –
# die Kürzung (MAX_BESCHREIBUNG_ZEILEN/ZEICHEN) ist entfallen. EP-Folgepositionen:
# Parameter `lieferschein_folgepositionen` (eine Zeile je Hauptposition, Standard
# „014: 015, 016, 017“) – steht die Hauptposition im Angebot, aber nicht auf dem
# Lieferschein (EP, Alternativ, bauseits), entfallen auch ihre Folgepositionen.

import re
from pathlib import Path

from fpdf.enums import XPos, YPos

from app import config
from app.models import Angebot, Einstellung, Kunde
from app.pdf_export import ABSENDERZEILE, AngebotsPdf, FOLGESEITEN_LOGO, ASSETS, _menge_text

FOLGEPOSITIONEN_PARAMETER = "lieferschein_folgepositionen"
FOLGEPOSITIONEN_STANDARD = "014: 015, 016, 017"
FOLGE_HINWEIS = "folgt auf dem Lieferschein Pos. {haupt}"

BREITEN = {"pos": 14, "menge": 16, "einheit": 14, "text": 126}
ZEILE_TITEL = 3.7
ZEILE_TEXT = 3.5


class LieferscheinPdf(AngebotsPdf):
    tabelle_aktiv = False   # v30: Tabellenkopf auf Folgeseiten (auch bei Auto-Umbruch)

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
        if self.tabelle_aktiv:
            self.tabellenkopf()

    def tabellenkopf(self):
        self.set_x(self.l_margin)
        self.set_font("Arial", "B", 8)
        self.cell(BREITEN["pos"], 4.5, "Position")
        self.cell(BREITEN["menge"], 4.5, "Menge", align="R")
        self.cell(BREITEN["einheit"], 4.5, " Einh.")
        self.cell(BREITEN["text"], 4.5, "Bezeichnung", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1.5)


# --- v30: EP-Folgepositionen ----------------------------------------------------

def folgepositionen_parsen(text: str) -> dict[str, list[str]]:
    """„014: 015, 016, 017“ je Zeile (auch „;“ als Zeilentrenner) →
    {Hauptposition: [Folgepositionen]}; ungültige Zeilen werden übergangen."""
    regeln: dict[str, list[str]] = {}
    for zeile in (text or "").replace(";", "\n").splitlines():
        if ":" not in zeile:
            continue
        haupt, rest = zeile.split(":", 1)
        haupt = haupt.strip()
        folgen = [t.strip() for t in re.split(r"[,\s]+", rest) if t.strip()]
        if not haupt or not folgen:
            continue
        liste = regeln.setdefault(haupt, [])
        for folge in folgen:
            if folge != haupt and folge not in liste:
                liste.append(folge)
    return regeln


def folgepositionen_text(session) -> str:
    """Parameterwert (Rohtext); fehlt die Zeile → Standard, ein leerer Wert
    bedeutet bewusst „keine Abhängigkeit“ (daher nicht einstellung_holen)."""
    zeile = (session.query(Einstellung)
             .filter(Einstellung.name == FOLGEPOSITIONEN_PARAMETER).first())
    return FOLGEPOSITIONEN_STANDARD if zeile is None else (zeile.wert or "")


def folgepositionen_lesen(session) -> dict[str, list[str]]:
    return folgepositionen_parsen(folgepositionen_text(session))


def _folgepositionen_laden() -> dict[str, list[str]]:
    """Ohne übergebene Regeln (z. B. Tests, Aufrufe ohne Sitzung): kurze Lesesitzung."""
    from app import db
    with db.kurz() as s:
        return folgepositionen_lesen(s)


def _auf_lieferschein(position) -> bool:
    return not (position.ep_flag or position.alternativ or position.bauseits)


def entfallende_folgepositionen(angebot: Angebot,
                                regeln: dict[str, list[str]]) -> dict[str, str]:
    """{Folge-pos_nr: Haupt-pos_nr} der Positionen, die entfallen, weil ihre
    Hauptposition im Angebot steht, aber nicht auf dem Lieferschein (EP,
    Alternativ, bauseits). Fehlt die Hauptposition ganz, bleiben sie unberührt."""
    geliefert: dict[str, bool] = {}
    for p in angebot.positionen:
        nr = (p.pos_nr or "").strip()
        if nr in regeln:
            geliefert[nr] = geliefert.get(nr, False) or _auf_lieferschein(p)
    ergebnis: dict[str, str] = {}
    for haupt, auf_schein in geliefert.items():
        if not auf_schein:
            for folge in regeln[haupt]:
                ergebnis.setdefault(folge, haupt)
    return ergebnis


def folge_hinweise(angebot: Angebot, regeln: dict[str, list[str]]) -> dict[int, str]:
    """Editor (nur Anzeige, PLAN_V18 Phase 149 [ANNAHME]): position.id →
    Hauptposition für jede Folgeposition, deren Hauptposition im Angebot steht."""
    vorhanden = {(p.pos_nr or "").strip() for p in angebot.positionen}
    hinweise: dict[int, str] = {}
    for p in angebot.positionen:
        nr = (p.pos_nr or "").strip()
        if not nr:
            continue
        for haupt, folgen in regeln.items():
            if nr in folgen and haupt in vorhanden and nr != haupt:
                hinweise[p.id] = haupt
                break
    return hinweise


def lieferschein_positionen(angebot: Angebot,
                            folgepositionen: dict[str, list[str]] | None = None
                            ) -> list[tuple[str, object]]:
    """(Anzeigenummer, Position) der aufzuführenden Positionen. folgepositionen =
    Regeln aus folgepositionen_lesen(session); None = Parameter selbst lesen."""
    regeln = _folgepositionen_laden() if folgepositionen is None else folgepositionen
    entfallen = entfallende_folgepositionen(angebot, regeln) if regeln else {}
    ergebnis = []
    for position, nummer in zip(angebot.positionen, angebot.nummerierung()):
        if not _auf_lieferschein(position):
            continue
        if not (position.pos_nr or "").strip() and not position.e_preis_cent:
            continue   # reine Textzeile (Auslegung, Vermerk)
        if (position.pos_nr or "").strip() in entfallen:
            continue   # v30: Folgeposition einer nicht gelieferten Hauptposition
        ergebnis.append((nummer, position))
    return ergebnis


# --- Positionstext ---------------------------------------------------------------

def _positionstext(position) -> tuple[str, str]:
    """Bezeichnung (erste Zeile, fett) + vollständige Beschreibung (alle Zeilen,
    v30 – keine Kürzung mehr). Ohne Bezeichnung wird die erste Beschreibungszeile
    zur Überschrift; eine Doppelung der Bezeichnung in der Beschreibung entfällt."""
    zeilen = [z.rstrip() for z in (position.beschreibung or "").splitlines()]
    while zeilen and not zeilen[0].strip():
        zeilen.pop(0)
    while zeilen and not zeilen[-1].strip():
        zeilen.pop()
    titel = (position.bezeichnung or "").strip()
    if not titel and zeilen:
        titel = zeilen.pop(0).strip()
        if titel.lower().startswith("(optionale position") and zeilen:
            titel = zeilen.pop(0).strip()
    elif zeilen and zeilen[0].strip() == titel:
        zeilen.pop(0)
    while zeilen and not zeilen[0].strip():
        zeilen.pop(0)
    return titel, "\n".join(zeilen)


# Name aus v13 bleibt für Aufrufer erhalten – kürzt seit v30 nicht mehr
_kurztext = _positionstext


def erzeuge_lieferschein(angebot: Angebot, kunde: Kunde, ziel: Path | None = None,
                         folgepositionen: dict[str, list[str]] | None = None) -> Path:
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
    y_empfaenger = pdf.get_y()
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

    pdf.set_xy(pdf.l_margin, max(pdf.get_y(), y_empfaenger, y_start + 26) + 6)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, f"L I E F E R S C H E I N  zu Angebot {angebot.nummer}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Arial", "", 9)
    ausfuehrung = f"{kunde.strasse}, {kunde.plz} {kunde.ort}".strip(", ")
    if ausfuehrung:
        pdf.multi_cell(0, 5, f"Ausführungsort: {ausfuehrung}")
    if anschriften.lieferzeile(angebot, kunde):
        pdf.multi_cell(0, 5, "Lieferanschrift: "
                       + anschriften.einzeilig(anschriften.lieferung(angebot, kunde)))
    pdf.ln(4)

    pdf.tabellenkopf()
    pdf.tabelle_aktiv = True   # Folgeseiten (auch Auto-Umbruch) wiederholen den Kopf
    text_x = pdf.l_margin + BREITEN["pos"] + BREITEN["menge"] + BREITEN["einheit"]
    letzte_gruppe = None
    for nummer, position in lieferschein_positionen(angebot, folgepositionen):
        titel, rest = _positionstext(position)
        # v24: Gruppen-Überschrift (z. B. „Klimaanlage Bosch“, editierbar seit
        # v22) wie im Angebots-PDF einmal vor der ersten Position der Gruppe
        gruppe = (position.gruppe or "").strip()
        neue_gruppe = bool(gruppe) and gruppe != letzte_gruppe
        gruppen_hoehe = 4.2 + 1.5 if neue_gruppe else 0.0
        # v30: Positionsnummer/Menge/Einheit, Bezeichnung und mindestens die
        # ersten Zeilen der Beschreibung bleiben zusammen; längere Beschreibungen
        # dürfen über den Seitenumbruch laufen (multi_cell mit Auto-Umbruch)
        pdf.set_font("Arial", "B", 8)
        titel_zeilen = pdf.multi_cell(BREITEN["text"], ZEILE_TITEL, titel or " ",
                                      dry_run=True, output="LINES")
        rest_zeilen: list = []
        if rest:
            pdf.set_font("Arial", "", 7.5)
            rest_zeilen = pdf.multi_cell(BREITEN["text"], ZEILE_TEXT, rest,
                                         dry_run=True, output="LINES")
        mindest = (len(titel_zeilen) * ZEILE_TITEL
                   + min(len(rest_zeilen), 3) * ZEILE_TEXT + 3)
        if pdf.get_y() + gruppen_hoehe + mindest > pdf.page_break_trigger:
            pdf.add_page()   # header() wiederholt den Tabellenkopf
        if neue_gruppe:
            pdf.set_font("Arial", "B", 8.5)
            pdf.set_x(text_x)
            pdf.multi_cell(BREITEN["text"], 4.2, gruppe)
            pdf.ln(1.5)
            letzte_gruppe = gruppe
        y = pdf.get_y()
        pdf.set_font("Arial", "", 8)
        pdf.cell(BREITEN["pos"], ZEILE_TITEL, nummer)
        pdf.cell(BREITEN["menge"], ZEILE_TITEL, _menge_text(position.menge), align="R")
        pdf.cell(BREITEN["einheit"], ZEILE_TITEL, " " + (position.einheit or ""))
        pdf.set_xy(text_x, y)
        pdf.set_font("Arial", "B", 8)
        pdf.multi_cell(BREITEN["text"], ZEILE_TITEL, titel or " ")
        if rest:
            pdf.set_x(text_x)
            pdf.set_font("Arial", "", 7.5)
            pdf.multi_cell(BREITEN["text"], ZEILE_TEXT, rest)
        pdf.ln(2)
    pdf.tabelle_aktiv = False

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
