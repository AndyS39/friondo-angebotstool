# Montage-Formulare (v15, Phase 82): Montagebericht, Inbetriebnahme- und
# Abnahmeprotokoll – Felder aus dem Blatt "Formulare" der Logik-Excel,
# mobil seitenweise mit Zwischenspeichern; der Abschluss erzeugt ein PDF in
# der Galerie "Inbetrieb-/Abnahme", erledigt die passende Aufgabe im Paket
# "Abnahme" (V4) und legt Restarbeiten aus dem Abnahmeprotokoll an.

import base64
import io
import json
import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app import projektierung as kern

ARIAL = Path(r"C:\Windows\Fonts")
DUNKELBLAU = (27, 42, 94)
LOGO = Path(__file__).parent / "static" / "pdf" / "friondo_logo.png"

AUFGABEN_TITEL = {
    "montagebericht": "Montagebericht liegt vor",
    "inbetriebnahme": "Inbetriebnahmeprotokoll liegt vor",
    "abnahme": "Abnahmeprotokoll mit Kundenunterschrift",
}


def formular_holen(session, gewerk, name: str, benutzer=None):
    """Bestehenden Entwurf laden oder neu anlegen."""
    from app.models import MontageFormular
    eintrag = (session.query(MontageFormular)
               .filter(MontageFormular.gewerk_id == gewerk.id,
                       MontageFormular.formular == name).first())
    if eintrag is None:
        eintrag = MontageFormular(
            gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id, formular=name,
            erstellt_von=benutzer.id if benutzer else None)
        session.add(eintrag)
        session.flush()
    return eintrag


def antworten(eintrag) -> dict:
    try:
        return json.loads(eintrag.antworten_json or "{}")
    except ValueError:
        return {}


async def seite_speichern(session, eintrag, gewerk, felder, form,
                          benutzer=None) -> None:
    """Feldwerte einer Seite übernehmen; Fotos landen sofort in der Galerie
    (Zielordner = optionen-Spalte), Unterschriften als PNG-Daten-URL."""
    from app import galerie as galerie_modul
    from app.models import Angebot
    daten = antworten(eintrag)
    for feld in felder:
        if feld.typ == "foto":
            datei = form.get(feld.feld_key)
            if datei is None or not getattr(datei, "filename", ""):
                continue
            angebot = (session.get(Angebot, gewerk.angebot_id)
                       if gewerk.angebot_id else None)
            if angebot is None or not angebot.vorgang_id:
                continue
            inhalt = await datei.read()
            galerie_datei = galerie_modul.speichern(
                session, angebot.vorgang_id,
                feld.optionen or "Inbetrieb-/Abnahme", datei.filename,
                inhalt, benutzer=benutzer,
                bemerkung=f"{feld.bezeichnung} ({eintrag.formular})",
                quelle="formular", sparte=gewerk.sparte)
            if galerie_datei is not None:
                daten[feld.feld_key] = (f"galerie:{galerie_datei.id}:"
                                        f"{galerie_datei.dateiname}")
        elif feld.typ == "unterschrift":
            wert = (form.get(feld.feld_key) or "").strip()
            if wert.startswith("data:image/png;base64,"):
                daten[feld.feld_key] = wert
        else:
            wert = (form.get(feld.feld_key) or "").strip()[:2000]
            if feld.typ == "zahl" and wert:
                wert = wert.replace(",", ".")
            daten[feld.feld_key] = wert
    eintrag.antworten_json = json.dumps(daten, ensure_ascii=False)
    session.flush()


def offene_pflicht(logik, eintrag) -> list[str]:
    daten = antworten(eintrag)
    return [f.bezeichnung for f in logik.formulare.get(eintrag.formular, [])
            if f.pflicht and not str(daten.get(f.feld_key) or "").strip()]


def _wert_anzeige(feld, wert: str) -> str:
    if not wert:
        return "–"
    if feld.typ == "foto" and wert.startswith("galerie:"):
        return "Foto in Galerie: " + wert.split(":", 2)[2]
    if feld.typ == "unterschrift":
        return ""   # Bild wird eingebettet
    return wert


class _FormularPdf(FPDF):
    def __init__(self, titel: str):
        super().__init__(format="A4")
        self.titel = titel
        self.set_margins(20, 16, 20)
        self.set_auto_page_break(True, margin=20)
        for stil, datei in (("", "arial.ttf"), ("B", "arialbd.ttf")):
            self.add_font("Arial", stil, ARIAL / datei)

    def header(self):
        if LOGO.exists():
            self.image(str(LOGO), x=150, y=12, w=40)
        self.set_font("Arial", "B", 15)
        self.set_text_color(*DUNKELBLAU)
        self.cell(0, 10, self.titel, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def footer(self):
        self.set_y(-14)
        self.set_font("Arial", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, "Friondo GmbH · erstellt aus dem Angebotstool",
                  align="C")


def pdf_bytes(session, logik, eintrag, gewerk) -> bytes:
    from app import projektierung_logik
    from app.models import Kunde, Projekt
    projekt = session.get(Projekt, eintrag.projekt_id)
    kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
    titel = projektierung_logik.FORMULAR_NAMEN.get(eintrag.formular,
                                                   eintrag.formular)
    daten = antworten(eintrag)
    pdf = _FormularPdf(titel)
    pdf.add_page()
    pdf.set_font("Arial", "", 10)
    for name, wert in [("Projekt", projekt.nummer if projekt else "–"),
                       ("Kunde", kunde.anzeige_name if kunde else "–"),
                       ("Gewerk", gewerk.sparte),
                       ("Erstellt", datetime.now().strftime("%d.%m.%Y %H:%M"))]:
        pdf.set_font("Arial", "B", 10)
        pdf.cell(55, 6, name)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 6, str(wert), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for seite, felder in logik.formular_seiten(eintrag.formular):
        pdf.ln(3)
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(*DUNKELBLAU)
        pdf.cell(0, 7, seite, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
        for feld in felder:
            wert = str(daten.get(feld.feld_key) or "")
            pdf.set_font("Arial", "B", 10)
            pdf.cell(80, 6, feld.bezeichnung[:52])
            pdf.set_font("Arial", "", 10)
            if feld.typ == "unterschrift" and wert.startswith("data:image"):
                m = re.match(r"data:image/png;base64,(.+)$", wert)
                if m:
                    try:
                        png = base64.b64decode(m.group(1))
                        pdf.image(io.BytesIO(png), w=60)
                    except Exception:
                        pdf.cell(0, 6, "(Unterschrift nicht lesbar)",
                                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    continue
            pdf.multi_cell(0, 6, _wert_anzeige(feld, wert),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())


def abschliessen(session, logik, eintrag, gewerk,
                 benutzer=None) -> tuple[bool, str]:
    """Pflicht prüfen → PDF in die Galerie → Aufgabe erledigen →
    Restarbeiten aus dem Abnahmeprotokoll → Verlauf."""
    from app import galerie as galerie_modul
    from app import projektierung_logik
    from app.models import Angebot, Aufgabe, Projekt, Restarbeit
    offen = offene_pflicht(logik, eintrag)
    if offen:
        return False, ("Pflichtfelder offen: " + " · ".join(offen[:4])
                       + (" …" if len(offen) > 4 else ""))
    projekt = session.get(Projekt, eintrag.projekt_id)
    inhalt = pdf_bytes(session, logik, eintrag, gewerk)
    angebot = (session.get(Angebot, gewerk.angebot_id)
               if gewerk.angebot_id else None)
    if angebot is not None and angebot.vorgang_id:
        titel = projektierung_logik.FORMULAR_NAMEN.get(eintrag.formular,
                                                       eintrag.formular)
        galerie_datei = galerie_modul.speichern(
            session, angebot.vorgang_id, "Inbetrieb-/Abnahme",
            f"{titel}_{projekt.nummer if projekt else ''}.pdf", inhalt,
            benutzer=benutzer, bemerkung=titel, quelle="formular",
            sparte=gewerk.sparte)
        if galerie_datei is not None:
            eintrag.pdf_galerie_id = galerie_datei.id
    eintrag.status = "abgeschlossen"
    eintrag.abgeschlossen_am = datetime.now()
    titel_soll = AUFGABEN_TITEL.get(eintrag.formular, "")
    if titel_soll:
        for aufgabe in (session.query(Aufgabe)
                        .filter(Aufgabe.gewerk_id == gewerk.id,
                                Aufgabe.titel == titel_soll,
                                Aufgabe.status != "erledigt")):
            aufgabe.status = "erledigt"
            aufgabe.erledigt_am = datetime.now()
            aufgabe.erledigt_von = benutzer.id if benutzer else None
    # Abnahme: Mängel-Zeilen -> Restarbeiten-Liste des Gewerks
    neue_restarbeiten = 0
    if eintrag.formular == "abnahme":
        daten = antworten(eintrag)
        frist = (daten.get("ab_frist") or "").strip()
        foto = daten.get("ab_maengel_foto") or ""
        foto_id = None
        if foto.startswith("galerie:"):
            try:
                foto_id = int(foto.split(":")[1])
            except ValueError:
                foto_id = None
        for zeile in (daten.get("ab_maengel") or "").splitlines():
            zeile = zeile.strip()
            if not zeile:
                continue
            text = zeile[:450] + (f" (Frist: {frist})" if frist else "")
            session.add(Restarbeit(
                gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id,
                text=text[:500], galerie_datei_id=foto_id,
                erstellt_von=benutzer.id if benutzer else None))
            foto_id = None   # Foto nur an den ersten Eintrag
            neue_restarbeiten += 1
    kern.verlauf(session, eintrag.projekt_id,
                 f"{projektierung_logik.FORMULAR_NAMEN.get(eintrag.formular, eintrag.formular)}"
                 " abgeschlossen (PDF in Galerie Inbetrieb-/Abnahme)"
                 + (f" – {neue_restarbeiten} Restarbeiten übernommen"
                    if neue_restarbeiten else ""),
                 benutzer=benutzer, gewerk_id=gewerk.id)
    session.flush()
    return True, "Formular abgeschlossen – PDF liegt in der Galerie."
