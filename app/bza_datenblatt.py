# BzA-Datenblatt (v19, PLAN_V14 Phasen 95–96): internes Arbeitsblatt zur
# Eingabe im KfW-Portal „Bestätigung zum Antrag“ (Programm 458), Abschnitte
# und Feldbezeichnungen wie im KfW-Muster. EIN Generator für beide Wege:
#   · Angebot (Tool- oder TAIFUN-WP-Angebot) → PDF „BzA-Datenblatt-<Nr>.pdf“
#   · Gewerk der Projektierung (v15-Seite mit Kopier-Knöpfen) → dieselben
#     Abschnitte + „Stand BzA / KfW“ (v17)
# Fehlende Pflichtangaben werden rot als „— fehlt: bitte beim Kunden
# erfragen“ ausgewiesen, das Datenblatt entsteht trotzdem.

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import Angebot, Benutzer, Erfassung, Kunde, einstellung_holen

FEHLT = "— fehlt: bitte beim Kunden erfragen"
FEHLT_ERSTELLER = "— fehlt: in der Benutzerverwaltung pflegen"
VERMERK = "Internes Arbeitsblatt zur Portaleingabe – keine KfW-Unterlage"
# Firmenblock (fest laut PLAN_V14; HWK-Betriebsnummer der Handwerkskammer)
FIRMA = {"name": "Friondo GmbH", "strasse": "Arnold-Overbeck-Str. 63-65",
         "plz_ort": "47139 Duisburg", "hwk": "1862718"}
# Portal-Wortlaut „Art des Wärmeerzeugers“ (Annahme, siehe nach-dem-update-v19)
WAERMEERZEUGER = {"Gas": "Gasheizung", "Öl": "Ölheizung",
                  "Nachtspeicher": "Nachtspeicherheizung", "Sonstiges": "Sonstiges"}
KLIMA_KATEGORIE_OEL = "Austausch Öl-, Kohle-, Gasetagen- oder Nachtspeicherheizung"
KLIMA_KATEGORIE_GAS = "Austausch mindestens 20 Jahre alte Gasheizung"


@dataclass
class Feld:
    name: str
    wert: str
    fehlt: bool = False
    hinweis: str = ""


@dataclass
class Datenblatt:
    angebot: Angebot
    kunde: Kunde | None
    nummer: str
    abschnitte: list[tuple[str, list[Feld]]] = field(default_factory=list)
    geraet_schluessel: str = ""
    geraet_auswahl_noetig: bool = False

    @property
    def fehlend(self) -> list[str]:
        return [f"{titel}: {f.name}" for titel, felder in self.abschnitte
                for f in felder if f.fehlt]


# --- Hilfen ----------------------------------------------------------------------

def ist_wp(angebot: Angebot) -> bool:
    return (angebot.konfigurator_typ or "WP") == "WP"


def erfassung_zum_angebot(session: Session, angebot: Angebot) -> Erfassung | None:
    """Erfassung des Angebots – bei Versionen (.2/.3) über die Vorgänger."""
    aktuell, gesehen = angebot, set()
    while aktuell is not None and aktuell.id not in gesehen:
        gesehen.add(aktuell.id)
        erfassung = (session.query(Erfassung)
                     .filter(Erfassung.angebot_id == aktuell.id).first())
        if erfassung is not None:
            return erfassung
        aktuell = (session.get(Angebot, aktuell.vorgaenger_id)
                   if aktuell.vorgaenger_id else None)
    return None


def strasse_hausnummer(text: str) -> tuple[str, str]:
    text = (text or "").strip()
    m = re.match(r"^(.*?)[\s,]+(\d+\s*[a-zA-Z]?(?:\s*[-/]\s*\d+\s*[a-zA-Z]?)?)$", text)
    if m:
        return m.group(1).strip(), m.group(2).replace(" ", "")
    return text, ""


def _zahl(wert) -> float | None:
    from app.konfigurator import zahl_parsen
    try:
        return zahl_parsen(wert)
    except Exception:
        return None


def _zahl_text(zahl: float, stellen: int = 0) -> str:
    text = f"{zahl:,.{stellen}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return text


def _euro(cent: int) -> str:
    return _zahl_text(cent / 100, 2) + " €"


def _feld(name: str, wert, pflicht: bool = True, hinweis: str = "",
          leer: str = FEHLT) -> Feld:
    text = "" if wert is None else str(wert).strip()
    if not text:
        return Feld(name, leer if pflicht else "–", fehlt=pflicht, hinweis=hinweis)
    return Feld(name, text, hinweis=hinweis)


def bafa_liste(session: Session):
    from app import logik as logik_modul
    logik, _ = logik_modul.hole_logik(session)
    return list(getattr(logik, "bafa_anlagen", []) or []) if logik else []


def _voll_berechnete_positionen(angebot: Angebot) -> set[str]:
    return {p.pos_nr for p in angebot.positionen
            if p.pos_nr and not (p.ep_flag or p.bauseits or p.alternativ)}


def ersteller_kandidaten(session: Session) -> list[Benutzer]:
    """ID-Benutzer (Innendienst + Admin) für den Ersteller-Block."""
    return (session.query(Benutzer)
            .filter(Benutzer.aktiv.is_(True),
                    Benutzer.rolle.in_(["innendienst", "admin"]))
            .order_by(Benutzer.name).all())


def ersteller_standard(session: Session, angemeldet) -> Benutzer | None:
    wert = einstellung_holen(session, "bza_ersteller_standard", "")
    if wert.isdigit():
        benutzer = session.get(Benutzer, int(wert))
        if benutzer is not None and benutzer.aktiv:
            return benutzer
    return angemeldet


# --- Daten ------------------------------------------------------------------------

def erstellen(session: Session, angebot: Angebot, gewerk=None,
              we_foerdern: int | None = None, ersteller: Benutzer | None = None,
              geraet_schluessel: str = "") -> Datenblatt:
    """Alle Abschnitte in KfW-Muster-Reihenfolge."""
    from app import kfw
    from app import konfigurator as engine
    from app import logik as logik_modul

    kunde = session.get(Kunde, angebot.kunde_id) if angebot.kunde_id else None
    erfassung = erfassung_zum_angebot(session, angebot)
    try:
        antworten = json.loads(erfassung.antworten_json or "{}") if erfassung else {}
    except ValueError:
        antworten = {}
    try:
        kfw_daten = json.loads(angebot.kfw_json or "{}")
    except ValueError:
        kfw_daten = {}
    if not kfw_daten.get("O01"):
        kfw_daten = {**engine.kfw_daten(antworten), **{k: v for k, v in kfw_daten.items() if v}}
    blatt = Datenblatt(angebot=angebot, kunde=kunde,
                       nummer=(angebot.taifun_nummer or angebot.nummer)
                       if angebot.extern else angebot.nummer)

    # 1. Investitionsobjekt (= Ausführungsort; am Gewerk: Projektadresse)
    if gewerk is not None:
        from app.models import Projekt
        projekt = session.get(Projekt, gewerk.projekt_id)
        roh_strasse = projekt.ausfuehrung_strasse if projekt else ""
        plz = projekt.ausfuehrung_plz if projekt else ""
        ort = projekt.ausfuehrung_ort if projekt else ""
    else:
        roh_strasse = kunde.strasse if kunde else ""
        plz, ort = (kunde.plz, kunde.ort) if kunde else ("", "")
    strasse, hausnummer = strasse_hausnummer(roh_strasse)
    objektart = str(kfw_daten.get("O01") or antworten.get("O01") or "")
    we_zahl = _zahl(kfw_daten.get("O03") or antworten.get("O03"))
    if objektart in ("EFH", "REH", "RMH") and not we_zahl:
        we_zahl = 1
    we_text = _zahl_text(we_zahl) if we_zahl else ""
    foerdern = we_foerdern if we_foerdern else (int(we_zahl) if we_zahl else None)
    flaeche = _zahl(antworten.get("O05") or kfw_daten.get("O05") or antworten.get("A17"))
    blatt.abschnitte.append(("1. Daten zum Investitionsobjekt", [
        _feld("Straße", strasse),
        _feld("Hausnummer", hausnummer),
        _feld("PLZ", plz),
        _feld("Ort", ort),
        Feld("Land", "Deutschland"),
        _feld("Wohneinheiten im Gebäude nach Abschluss des Vorhabens", we_text),
        _feld("Anzahl der zu fördernden Wohneinheiten", foerdern,
              hinweis="im Datenblatt-Dialog übersteuerbar" if foerdern else ""),
        _feld("Wohnfläche der zu fördernden Wohneinheiten",
              f"{_zahl_text(flaeche)} m²" if flaeche else "", pflicht=False),
    ]))

    # 2. Wärmeversorgung vor Sanierung
    traeger = str(antworten.get("A01") or "")
    jahr = _zahl(antworten.get("A02"))
    nenn = _zahl(antworten.get("A20"))
    verbrauch_roh = antworten.get("A03")
    verbrauch = _zahl(verbrauch_roh)
    if angebot.extern:
        ausgebaut = Feld("Im Zuge der Sanierung ausgebaut", "Ja",
                         hinweis="TAIFUN-Angebot: Demontage angenommen")
    else:
        demontage = any("demontage" in f"{p.bezeichnung} {p.beschreibung}".lower()
                        for p in angebot.positionen
                        if not (p.ep_flag or p.bauseits or p.alternativ))
        ausgebaut = Feld("Im Zuge der Sanierung ausgebaut", "Ja" if demontage else "Nein",
                         hinweis="" if demontage else "keine Demontage-Position im Angebot")
    blatt.abschnitte.append(("2. Wärmeversorgung vor Sanierung", [
        _feld("Art des Wärmeerzeugers", WAERMEERZEUGER.get(traeger, traeger)),
        _feld("Nennleistung", f"{_zahl_text(nenn, 1 if nenn % 1 else 0)} kW"
              if nenn else ""),
        (_feld("Inbetriebnahme", f"01.01.{int(jahr)}", hinweis="Jahr aus Erfassung")
         if jahr else Feld("Inbetriebnahme", "Jahr fehlt – bitte nachfragen", fehlt=True)),
        (Feld("Endenergieverbrauch", f"{_zahl_text(verbrauch)} kWh/a")
         if verbrauch else Feld("Endenergieverbrauch", "–",
                                hinweis="Flächen-Auslegung (Verbrauch unbekannt)"
                                if str(verbrauch_roh or "").startswith("Verbrauch") else "")),
        Feld("Endenergiebedarf", "–"),
        ausgebaut,
    ]))

    # 3. Geplante Wärmeversorgung
    anlagen = bafa_liste(session)
    nach_schluessel = {a.schluessel: a for a in anlagen}
    anlage = None
    if geraet_schluessel:
        anlage = nach_schluessel.get(geraet_schluessel)
    elif not angebot.extern:
        from app.logik import bafa_fuer_positionen
        logik, _ = logik_modul.hole_logik(session)
        if logik is not None:
            anlage = bafa_fuer_positionen(logik, _voll_berechnete_positionen(angebot))
    blatt.geraet_auswahl_noetig = bool(angebot.extern and anlage is None)
    blatt.geraet_schluessel = anlage.schluessel if anlage else ""
    heizflaechen = str(antworten.get("H02") or "")
    vorlauf = ("35 °C" if heizflaechen == "Fußbodenheizung"
               else "55 °C" if heizflaechen else "")
    contracting = str(antworten.get("N11") or "")
    pruefhinweis = anlage.hinweis if anlage and anlage.hinweis else ""
    blatt.abschnitte.append(("3. Geplante Wärmeversorgung", [
        Feld("Maßnahme", "Wärmepumpe"),
        Feld("Contracting", contracting or "Nein",
             hinweis="" if contracting else "Vorbelegung (Frage N11 nicht erfasst)"),
        _feld("Anlagennummer (BAFA-Liste)", anlage.nummer if anlage else "",
              hinweis=pruefhinweis),
        _feld("Hersteller", anlage.hersteller if anlage else ""),
        _feld("Gerätebezeichnung", anlage.bezeichnung if anlage else ""),
        Feld("Pumpentyp", "Luft / Wasser"),
        _feld("Nennwärmeleistung", f"{_zahl_text(anlage.kw, 2)} kW"
              if anlage and anlage.kw else ""),
        _feld("Vorlauftemperatur", vorlauf,
              hinweis=f"Heizflächen: {heizflaechen}" if heizflaechen else ""),
        Feld("Wärmequelle", "Luft"),
        Feld("Anzahl geplanter Anlagen", "1"),
    ]))

    # 4. Geplante Kosten
    endbetrag = (angebot.extern_endbetrag_cent or 0) if angebot.extern \
        else angebot.summen()["endbetrag"]
    kosten = [_feld("Geplante förderfähige Kosten", _euro(endbetrag) if endbetrag else "",
                    hinweis="Endbetrag brutto nach Rabatt – wie im KfW-Muster ungedeckelt")]
    ergebnis = None
    logik, bericht = logik_modul.hole_logik(session)
    eingaben = kfw.eingaben_aus_antworten(kfw_daten, endbetrag) if endbetrag else None
    parameter = None
    if bericht is not None and logik is not None and eingaben is not None:
        parameter, _ = kfw.parameter_lesen(logik)
        ergebnis = (kfw.berechnen(parameter, eingaben) if angebot.extern
                    else kfw.ergebnis_fuer_angebot(parameter, eingaben, angebot))
    if ergebnis is not None:
        kosten.append(Feld("nachrichtlich: davon förderfähig gemäß Höchstkostengrenze",
                           _euro(ergebnis.foerderfaehig_cent)))
        kosten.append(Feld("nachrichtlich: voraussichtlicher Zuschuss lt. Angebot",
                           _euro(ergebnis.zuschuss_cent)))
    else:
        kosten.append(Feld("nachrichtlich: Förderwerte", "–",
                           hinweis="keine Förderdaten (Objektart/K-Fragen) erfasst"))
    blatt.abschnitte.append(("4. Geplante Kosten", kosten))

    # 5. Boni
    selbst = objektart in ("EFH", "REH", "RMH") or (
        objektart in ("2FH", "MFH") and kfw_daten.get("K01") == "Ja")
    k02 = str(kfw_daten.get("K02") or "")
    kategorie = ""
    if selbst:
        if k02 and not k02.startswith("Andere"):
            kategorie = KLIMA_KATEGORIE_GAS if ("20" in k02 and "Gas" in k02) \
                else KLIMA_KATEGORIE_OEL
        elif not k02:
            if traeger in ("Öl", "Nachtspeicher"):
                kategorie = KLIMA_KATEGORIE_OEL
            elif traeger == "Gas" and jahr and date.today().year - int(jahr) >= 20:
                kategorie = KLIMA_KATEGORIE_GAS
    stufe = ""
    if selbst and eingaben is not None and eingaben.einkommen_eur > 0 and parameter:
        rest = max(0.0, eingaben.einkommen_eur
                   - (parameter.kind_freibetrag_eur if eingaben.kind else 0))
        for prozent, grenze in parameter.einkommens_stufen:
            if rest <= grenze:
                stufe = f"{_zahl_text(prozent)} %"
                break
    blatt.abschnitte.append(("5. Boni", [
        Feld("Klimageschwindigkeitsbonus", "Ja" if kategorie else "Nein",
             hinweis="" if selbst else "nur bei Selbstnutzung"),
        Feld("Kategorie Klimageschwindigkeitsbonus", kategorie or "–",
             hinweis="aus A01 + Inbetriebnahmejahr" if kategorie else ""),
        Feld("Einkommensbonus", f"Ja – Stufe {stufe}" if stufe else "Nein",
             hinweis="Nachweis: Einkommensteuerbescheide" if stufe else ""),
    ]))

    # 6. Ersteller
    person = ersteller
    blatt.abschnitte.append(("6. Ersteller", [
        Feld("Unternehmen", FIRMA["name"]),
        Feld("Anschrift", f"{FIRMA['strasse']}, {FIRMA['plz_ort']}"),
        Feld("Handwerkskammer-Betriebsnummer", FIRMA["hwk"]),
        _feld("Ansprechpartner", person.name if person else "", leer=FEHLT_ERSTELLER),
        _feld("E-Mail", (person.email if person else "") or "", leer=FEHLT_ERSTELLER),
        _feld("Telefon", (person.telefon if person else "") or "", leer=FEHLT_ERSTELLER),
    ]))
    return blatt


# --- PDF --------------------------------------------------------------------------

def pdf_bytes(blatt: Datenblatt) -> bytes:
    from fpdf.enums import XPos, YPos

    from app.pdf_export import ABSENDERZEILE, AngebotsPdf

    class DatenblattPdf(AngebotsPdf):
        def header(self):
            if self.page_no() == 1:
                self._logo_leiste()
                return
            self.set_font("Arial", "B", 9)
            self.set_y(12)
            self.cell(0, 5, f"BzA-Datenblatt zu {blatt.nummer} · Seite {self.page_no()}")
            self.set_y(22)

    pdf = DatenblattPdf(blatt.nummer)     # Umbruchrand 42 mm (Fußzeile) wie Angebot
    pdf.add_page()
    pdf.set_font("Arial", "", 6.5)
    pdf.set_text_color(100, 100, 100)
    pdf.set_y(49.3)
    pdf.cell(0, 3, ABSENDERZEILE, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 7, "BzA-Datenblatt (KfW 458 – Bestätigung zum Antrag)",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Arial", "", 9)
    kunde = blatt.kunde.anzeige_name if blatt.kunde else "?"
    pdf.cell(0, 5, f"Angebot {blatt.nummer} · {kunde} · erstellt am "
                   f"{datetime.now():%d.%m.%Y}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_fill_color(253, 236, 234)
    pdf.set_text_color(179, 38, 30)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 7, VERMERK, border=0, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    fehlend = blatt.fehlend
    if fehlend:
        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(179, 38, 30)
        pdf.multi_cell(0, 4, f"Fehlende Angaben ({len(fehlend)}): " + " · ".join(fehlend))
        pdf.set_text_color(0, 0, 0)
    breite_name, breite_wert = 70, pdf.inhaltsbreite - 70
    for titel, felder in blatt.abschnitte:
        if pdf.get_y() + 16 > pdf.page_break_trigger:
            pdf.add_page()
        pdf.ln(3)
        pdf.set_font("Arial", "B", 10.5)
        pdf.cell(0, 6, titel, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(1)
        for f in felder:
            wert = f.wert + (f"  ({f.hinweis})" if f.hinweis else "")
            pdf.set_font("Arial", "B" if f.fehlt else "", 8.5)
            zeilen = pdf.multi_cell(breite_wert, 4.4, wert, dry_run=True, output="LINES")
            pdf.set_font("Arial", "", 8.5)
            zeilen_name = pdf.multi_cell(breite_name, 4.4, f.name, dry_run=True,
                                         output="LINES")
            hoehe = 4.4 * max(len(zeilen), len(zeilen_name)) + 0.6
            if pdf.get_y() + hoehe > pdf.page_break_trigger:
                pdf.add_page()   # Zeile nie über den Seitenumbruch zerreißen
            y = pdf.get_y()
            pdf.set_text_color(90, 90, 90)
            pdf.multi_cell(breite_name, 4.4, f.name)
            y_name = pdf.get_y()
            pdf.set_xy(pdf.l_margin + breite_name, y)
            if f.fehlt:
                pdf.set_text_color(179, 38, 30)
                pdf.set_font("Arial", "B", 8.5)
            else:
                pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(breite_wert, 4.4, wert,
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_y(max(pdf.get_y(), y_name) + 0.6)
            pdf.set_text_color(0, 0, 0)
    return bytes(pdf.output())


def dateiname(blatt: Datenblatt) -> str:
    return f"BzA-Datenblatt-{re.sub(r'[^A-Za-z0-9._-]', '_', blatt.nummer)}.pdf"


# --- Gewerk-Seite (v15/v17): dieselben Abschnitte als (Gruppe, [(Name, Wert)]) ---

def fuer_gewerk_seite(blatt: Datenblatt) -> list[tuple[str, list[tuple[str, str]]]]:
    return [(titel, [(f.name, "" if f.fehlt else
                      f.wert + (f" ({f.hinweis})" if f.hinweis else ""))
                     for f in felder])
            for titel, felder in blatt.abschnitte]
