# Montage-Formulare (v15, Phase 82): Montagebericht, Inbetriebnahme- und
# Abnahmeprotokoll – Felder aus dem Blatt "Formulare" der Logik-Excel,
# mobil seitenweise mit Zwischenspeichern; der Abschluss erzeugt ein PDF in
# der Galerie "Inbetrieb-/Abnahme", erledigt die passende Aufgabe im Paket
# "Abnahme" (V4) und legt Restarbeiten aus dem Abnahmeprotokoll an.
#
# v28 (PLAN_PROJ_V6 Phase 138): Foto-Felder nehmen mehrere Dateien
# (Wert „galerie:<id>:<name>|galerie:<id>:<name>“, Bestandswerte mit einem Foto
# bleiben lesbar), Typ `wiederhol` (JSON-Liste, Formularfelder `<key>[]`),
# Optionsform `pflicht_wenn:` in `offene_pflicht`, Restarbeiten aus Frage 10 des
# Inbetriebnahmeprotokolls (ohne Dubletten, „keine“ erzeugt nichts), PDF mit
# multi_cell, Frage 7 als vier Zeilen, Betriebswerte/Einstellungen als Tabelle,
# zwei Unterschriften nebeneinander. Phase 137: das Abnahmeprotokoll beendet die
# Montage automatisch (Phase montage → abnahme, montage_fertig_am).

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

# v28: Zeilen in Frage 10 / Mängelliste, die KEINE Restarbeit erzeugen
KEINE_RESTARBEIT = ("keine", "keine.", "-", "–", "—")
# v28: Frage 7 des Inbetriebnahmeprotokolls – im PDF als Block mit vier Zeilen
F7_TITEL = "7. Wurden die vorgesehenen Betriebsarten erfolgreich getestet?"
F7_FELDER = {"ib_f07_heizen": "Heizen", "ib_f07_warmwasser": "Warmwasser",
             "ib_f07_kuehlen": "Kühlen", "ib_f07_zusatzheizung": "Zusatzheizung"}
BEZEICHNUNG_KURZ = 52          # bis hierhin Bezeichnung + Antwort in einer Zeile
FOTO_PRAEFIX = "galerie:"
MAX_WIEDERHOL = 50


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
        daten = json.loads(eintrag.antworten_json or "{}")
    except ValueError:
        return {}
    return daten if isinstance(daten, dict) else {}


# --- Wertformen (v28) ----------------------------------------------------------

def foto_werte(wert) -> list[tuple[int | None, str]]:
    """„galerie:<id>:<name>|galerie:<id>:<name>“ → [(id, name), …]; Bestandswerte
    mit genau einem Foto und leere Werte sind ebenfalls lesbar."""
    ergebnis: list[tuple[int | None, str]] = []
    for teil in str(wert or "").split("|"):
        teil = teil.strip()
        if not teil.startswith(FOTO_PRAEFIX):
            continue
        rest = teil[len(FOTO_PRAEFIX):]
        nummer, _, name = rest.partition(":")
        try:
            datei_id: int | None = int(nummer)
        except ValueError:
            datei_id = None
        ergebnis.append((datei_id, name))
    return ergebnis


def foto_wert_bauen(fotos: list[tuple[int | None, str]]) -> str:
    return "|".join(f"{FOTO_PRAEFIX}{datei_id if datei_id is not None else ''}:{name}"
                    for datei_id, name in fotos)


def wiederhol_werte(wert) -> list[str]:
    """Wert eines wiederhol-Felds als Liste (JSON-Liste; Altwert als Text →
    eine Zeile je Zeilenumbruch)."""
    if wert is None:
        return []
    if isinstance(wert, (list, tuple)):
        return [str(w).strip() for w in wert if str(w).strip()]
    text = str(wert).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            geladen = json.loads(text)
            if isinstance(geladen, list):
                return [str(w).strip() for w in geladen if str(w).strip()]
        except ValueError:
            pass
    return [z.strip() for z in text.splitlines() if z.strip()]


def wert_leer(feld, wert) -> bool:
    if feld.typ == "wiederhol":
        return not wiederhol_werte(wert)
    if isinstance(wert, (list, tuple)):
        return not any(str(w).strip() for w in wert)
    return not str(wert or "").strip()


def seite_speichern(session, eintrag, gewerk, felder, form,
                          benutzer=None) -> None:
    """Feldwerte einer Seite übernehmen; Fotos landen sofort in der Galerie
    (Zielordner = optionen-Spalte, mehrere Dateien je Feld – neue Fotos werden
    an vorhandene angehängt [ANNAHME]), Unterschriften als PNG-Daten-URL,
    wiederhol-Felder (`<key>[]`) als JSON-Liste."""
    from app import galerie as galerie_modul
    from app.models import Angebot
    daten = antworten(eintrag)
    for feld in felder:
        if feld.typ == "foto":
            try:
                dateien = list(form.getlist(feld.feld_key))
            except AttributeError:
                einzel = form.get(feld.feld_key)
                dateien = [einzel] if einzel is not None else []
            dateien = [d for d in dateien if getattr(d, "filename", "")]
            if not dateien:
                continue
            angebot = (session.get(Angebot, gewerk.angebot_id)
                       if gewerk.angebot_id else None)
            if angebot is None or not angebot.vorgang_id:
                continue
            fotos = foto_werte(daten.get(feld.feld_key))
            for datei in dateien:
                galerie_datei = galerie_modul.speichern(
                    session, angebot.vorgang_id,
                    feld.optionen or "Inbetrieb-/Abnahme", datei.filename,
                    datei.file, benutzer=benutzer,   # v27: wird gestreamt
                    bemerkung=f"{feld.bezeichnung} ({eintrag.formular})",
                    quelle="formular", sparte=gewerk.sparte)
                if galerie_datei is not None:
                    fotos.append((galerie_datei.id, galerie_datei.dateiname))
            daten[feld.feld_key] = foto_wert_bauen(fotos)
        elif feld.typ == "unterschrift":
            wert = (form.get(feld.feld_key) or "").strip()
            if wert.startswith("data:image/png;base64,"):
                daten[feld.feld_key] = wert
        elif feld.typ == "wiederhol":
            try:
                roh = list(form.getlist(feld.feld_key + "[]"))
            except AttributeError:
                roh = []
            if not roh and form.get(feld.feld_key) is not None:
                roh = [form.get(feld.feld_key)]
            daten[feld.feld_key] = [str(w).strip()[:200] for w in roh
                                    if str(w).strip()][:MAX_WIEDERHOL]
        else:
            wert = (form.get(feld.feld_key) or "").strip()[:2000]
            if feld.typ == "zahl" and wert:
                wert = wert.replace(",", ".")
            daten[feld.feld_key] = wert
    eintrag.antworten_json = json.dumps(daten, ensure_ascii=False)
    session.flush()


def offene_pflicht(logik, eintrag) -> list[str]:
    """Bezeichnungen der offenen Pflichtfelder – Spalte `pflicht` und (v28) die
    Bedingung `pflicht_wenn:<feld>≠<wert>` bzw. `=<wert>` auf dem aktuellen
    Antwortstand."""
    daten = antworten(eintrag)
    return [f.bezeichnung for f in logik.formulare.get(eintrag.formular, [])
            if f.pflicht_erfuellt(daten) and wert_leer(f, daten.get(f.feld_key))]


def _wert_anzeige(feld, wert) -> str:
    if feld.typ == "foto":
        fotos = foto_werte(wert)
        if not fotos:
            return "–"
        namen = ", ".join(name for _, name in fotos)
        return ("Foto in Galerie: " if len(fotos) == 1 else "Fotos in Galerie: ") + namen
    if feld.typ == "wiederhol":
        werte = wiederhol_werte(wert)
        if not werte:
            return "–"
        return "\n".join(f"{feld.einzelfeld} {i}: {w}" for i, w in enumerate(werte, 1))
    if feld.typ == "unterschrift":
        return ""   # Bild wird eingebettet
    text = str(wert or "").strip()
    return text or "–"


def _unterschrift_png(wert: str) -> bytes | None:
    m = re.match(r"data:image/png;base64,(.+)$", wert or "")
    if not m:
        return None
    try:
        return base64.b64decode(m.group(1))
    except Exception:
        return None


def _unterschrift_beschriftung(feld) -> str:
    """„Unterschrift Techniker“ → „Techniker“; längere Bezeichnungen bleiben
    (z. B. „Betreiber – Einweisung und Unterlagenerhalt bestätigt“)."""
    text = (feld.bezeichnung or "").strip()
    if text.lower().startswith("unterschrift "):
        text = text[len("unterschrift "):].strip()
    return text or feld.feld_key


def _ist_tabellenseite(felder) -> bool:
    """Seiten nur aus kurzen Zahl-/Text-/Auswahlfeldern (Betriebswerte,
    Einstellungen) werden im PDF als zweispaltige Tabelle gesetzt."""
    return bool(felder) and all(
        f.typ in ("zahl", "text", "auswahl") and not f.gross
        and f.pflicht_wenn is None and len(f.bezeichnung) <= BEZEICHNUNG_KURZ
        for f in felder)


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

    # --- v28: Bausteine -------------------------------------------------------
    def platz_sichern(self, hoehe: float) -> None:
        if self.get_y() + hoehe > self.page_break_trigger:
            self.add_page()

    def feld(self, bezeichnung: str, wert: str) -> None:
        """Kurze Bezeichnung: links Bezeichnung (fett), rechts Antwort mit Umbruch.
        Lange Bezeichnung (> 52 Zeichen): Frage in voller Länge mit multi_cell,
        Antwort in der Folgezeile (eingerückt)."""
        self.platz_sichern(12)
        if len(bezeichnung) <= BEZEICHNUNG_KURZ:
            self.set_font("Arial", "B", 10)
            self.cell(80, 6, bezeichnung)
            self.set_font("Arial", "", 10)
            self.multi_cell(0, 6, wert, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            return
        self.set_font("Arial", "B", 10)
        self.multi_cell(0, 5.5, bezeichnung, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Arial", "", 10)
        self.set_x(self.l_margin + 6)
        self.multi_cell(0, 6, wert, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def tabelle(self, zeilen: list[tuple[str, str]]) -> None:
        """Zweispaltig: Bezeichnung | Wert (Betriebswerte, Einstellungen)."""
        breite = self.w - self.l_margin - self.r_margin
        links = 95
        self.set_font("Arial", "", 10)
        for bezeichnung, wert in zeilen:
            self.platz_sichern(8)
            self.set_font("Arial", "B", 10)
            self.cell(links, 7, bezeichnung, border=1)
            self.set_font("Arial", "", 10)
            self.cell(breite - links, 7, wert, border=1,
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def frage7(self, zeilen: list[tuple[str, str]]) -> None:
        self.platz_sichern(10 + 6 * len(zeilen))
        self.set_font("Arial", "B", 10)
        self.multi_cell(0, 5.5, F7_TITEL, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        for name, wert in zeilen:
            self.set_x(self.l_margin + 6)
            self.set_font("Arial", "", 10)
            self.cell(40, 6, name)
            self.cell(0, 6, wert, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def unterschriften(self, eintraege: list[tuple[str, bytes | None]]) -> None:
        """Zwei Unterschriften nebeneinander (Beschriftung über dem Bild);
        eine einzelne Unterschrift linksbündig."""
        self.platz_sichern(52)
        breite = (self.w - self.l_margin - self.r_margin - 8) / 2
        y0 = self.get_y()
        for i, (beschriftung, png) in enumerate(eintraege[:2]):
            x = self.l_margin + i * (breite + 8)
            self.set_xy(x, y0)
            self.set_font("Arial", "B", 9)
            self.multi_cell(breite, 4.5, beschriftung, new_x=XPos.LEFT, new_y=YPos.NEXT)
            y_bild = max(self.get_y(), y0 + 10)
            if png:
                try:
                    self.image(io.BytesIO(png), x=x, y=y_bild, w=min(breite, 70))
                except Exception:
                    self.set_xy(x, y_bild)
                    self.set_font("Arial", "", 9)
                    self.cell(breite, 6, "(Unterschrift nicht lesbar)")
            else:
                self.set_xy(x, y_bild)
                self.set_font("Arial", "", 9)
                self.cell(breite, 6, "(keine Unterschrift)")
        self.set_xy(self.l_margin, y0 + 42)
        self.set_font("Arial", "", 10)


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
        pdf.platz_sichern(20)
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(*DUNKELBLAU)
        pdf.cell(0, 7, seite, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
        if _ist_tabellenseite(felder):
            pdf.tabelle([(f.bezeichnung, _wert_anzeige(f, daten.get(f.feld_key)))
                         for f in felder])
            continue
        unterschriften = [f for f in felder if f.typ == "unterschrift"]
        f7_gesehen = False
        for feld in felder:
            if feld.typ == "unterschrift":
                continue
            wert = daten.get(feld.feld_key)
            if feld.feld_key in F7_FELDER:
                if not f7_gesehen:
                    f7_gesehen = True
                    pdf.frage7([(F7_FELDER[f.feld_key],
                                 _wert_anzeige(f, daten.get(f.feld_key)))
                                for f in felder if f.feld_key in F7_FELDER])
                continue
            pdf.feld(feld.bezeichnung, _wert_anzeige(feld, wert))
        if len(unterschriften) >= 2:
            pdf.unterschriften([(_unterschrift_beschriftung(f),
                                 _unterschrift_png(str(daten.get(f.feld_key) or "")))
                                for f in unterschriften])
        elif unterschriften:
            feld = unterschriften[0]
            png = _unterschrift_png(str(daten.get(feld.feld_key) or ""))
            pdf.platz_sichern(45)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(80, 6, _unterschrift_beschriftung(feld)[:BEZEICHNUNG_KURZ],
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Arial", "", 10)
            if png:
                try:
                    pdf.image(io.BytesIO(png), w=60)
                except Exception:
                    pdf.cell(0, 6, "(Unterschrift nicht lesbar)",
                             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            else:
                pdf.cell(0, 6, "(keine Unterschrift)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())


# --- Restarbeiten (v28) ----------------------------------------------------------

def ist_keine_restarbeit(zeile: str) -> bool:
    return (zeile or "").strip().lower() in KEINE_RESTARBEIT


def restarbeiten_zeilen(text: str) -> list[str]:
    """Zeilen der Mängel-/Restarbeiten-Angabe ohne Leer- und „keine“-Zeilen."""
    ergebnis = []
    for zeile in (text or "").splitlines():
        zeile = zeile.strip()
        if zeile and not ist_keine_restarbeit(zeile):
            ergebnis.append(zeile)
    return ergebnis


def _restarbeiten_uebernehmen(session, gewerk, zeilen: list[str], benutzer=None,
                              frist: str = "", foto_id: int | None = None) -> int:
    """Zeilen als Restarbeit anlegen – Zeilen, die bereits wörtlich als offene
    Restarbeit des Gewerks existieren (oder in dieser Liste doppelt sind),
    werden übersprungen. Das Foto hängt nur am ersten neuen Eintrag."""
    from app.models import Restarbeit
    vorhanden = {(r.text or "").strip().lower() for r in
                 session.query(Restarbeit)
                 .filter(Restarbeit.gewerk_id == gewerk.id,
                         Restarbeit.status != "erledigt")}
    neue = 0
    for zeile in zeilen:
        text = zeile[:450] + (f" (Frist: {frist})" if frist else "")
        text = text[:500]
        if text.strip().lower() in vorhanden:
            continue
        vorhanden.add(text.strip().lower())
        session.add(Restarbeit(
            gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id,
            text=text, galerie_datei_id=foto_id,
            erstellt_von=benutzer.id if benutzer else None))
        foto_id = None
        neue += 1
    return neue


def abschliessen(session, logik, eintrag, gewerk,
                 benutzer=None) -> tuple[bool, str]:
    """Pflicht prüfen → PDF in die Galerie → Aufgabe erledigen →
    Restarbeiten aus Abnahmeprotokoll (Mängel) bzw. Inbetriebnahme (Frage 10)
    → Verlauf. v28 (Phase 137): das unterschriebene Abnahmeprotokoll beendet die
    Montage (Phase montage → abnahme, montage_fertig_am)."""
    from app import galerie as galerie_modul
    from app import projektierung_logik
    from app.models import Angebot, Aufgabe, Projekt
    offen = offene_pflicht(logik, eintrag)
    if offen:
        return False, ("Pflichtfelder offen: " + " · ".join(offen[:4])
                       + (" …" if len(offen) > 4 else ""))
    projekt = session.get(Projekt, eintrag.projekt_id)
    inhalt = pdf_bytes(session, logik, eintrag, gewerk)
    angebot = (session.get(Angebot, gewerk.angebot_id)
               if gewerk.angebot_id else None)
    titel = projektierung_logik.FORMULAR_NAMEN.get(eintrag.formular, eintrag.formular)
    if angebot is not None and angebot.vorgang_id:
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
    daten = antworten(eintrag)
    neue_restarbeiten = 0
    if eintrag.formular == "abnahme":
        # Abnahme: Mängel-Zeilen -> Restarbeiten-Liste des Gewerks (Frist, Foto)
        frist = (daten.get("ab_frist") or "").strip()
        fotos = foto_werte(daten.get("ab_maengel_foto"))
        foto_id = fotos[0][0] if fotos else None
        neue_restarbeiten = _restarbeiten_uebernehmen(
            session, gewerk, restarbeiten_zeilen(daten.get("ab_maengel") or ""),
            benutzer=benutzer, frist=frist, foto_id=foto_id)
    elif eintrag.formular == "inbetriebnahme":
        # v28: Frage 10 (eine je Zeile; „keine“ erzeugt nichts), ohne Frist/Foto
        neue_restarbeiten = _restarbeiten_uebernehmen(
            session, gewerk, restarbeiten_zeilen(daten.get("ib_f10") or ""),
            benutzer=benutzer)
    meldung_zusatz = ""
    if eintrag.formular == "abnahme" and gewerk.phase == "montage":
        # v28 (Phase 137): Montage automatisch beenden, sobald das Abnahmeprotokoll
        # unterschrieben ist (Kundenunterschrift ist Pflichtfeld)
        if gewerk.montage_fertig_am is None:
            gewerk.montage_fertig_am = datetime.now()
        ok, phase_meldung = kern.phase_wechseln(
            session, gewerk, "abnahme", "Abnahmeprotokoll unterschrieben (mobil)",
            benutzer=benutzer)
        if ok:
            kern.verlauf(session, gewerk.projekt_id, "Montage beendet mit Abnahme",
                         benutzer=benutzer, gewerk_id=gewerk.id)
            meldung_zusatz = " Montage beendet – Gewerk steht in Abnahme."
        else:
            meldung_zusatz = f" (Phasenwechsel nicht möglich: {phase_meldung})"
    kern.verlauf(session, eintrag.projekt_id,
                 f"{titel} abgeschlossen (PDF in Galerie Inbetrieb-/Abnahme)"
                 + (f" – {neue_restarbeiten} Restarbeiten übernommen"
                    if neue_restarbeiten else ""),
                 benutzer=benutzer, gewerk_id=gewerk.id)
    session.flush()
    return True, "Formular abgeschlossen – PDF liegt in der Galerie." + meldung_zusatz
