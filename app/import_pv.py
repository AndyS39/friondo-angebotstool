# PV-Artikelimport (v13-PV, PLAN_V13 Phase 75): liest die vier TAIFUN-
# Positionslisten im Ordner Artikel-Preislisten/PV/ (Layout wie die WP-
# Preisliste: GUID · Position · Menge · Einheit · Beschreibung · E-Preis ·
# G-Preis · Einkaufspreis Material; Kategoriezeilen ohne Position) und legt
# sie als eigenen PV-Artikelbereich an – fortlaufende Nummern PV001, PV002 …
#
# Nummernvergabe (wiederholbarer Import):
#   1. Blatt „PV-Artikel“ der Logik-Excel pinnt GUID → PV-Nr. (so bekommen
#      Entwicklungs-PC und Server garantiert dieselben Nummern, auf die das
#      Blatt „Aktionen PV“ verweist);
#   2. sonst: vorhandener PV-Artikel mit derselben GUID behält seine Nummer;
#   3. sonst: vorhandener PV-Artikel derselben Datei mit gleicher Bezeichnung
#      (erste Textzeile) – z. B. nach einem TAIFUN-Neuexport mit neuen GUIDs;
#   4. sonst: nächste freie Nummer.
# Der WP-Preislisten-Import fasst PV-Artikel nie an (eigene Quelle „pv“).

import re
from dataclasses import dataclass, field

import openpyxl
from sqlalchemy.orm import Session

from app import config
from app.import_preisliste import (Diff, FELD_NAMEN, _header_indizes,
                                   euro_zu_cent, kategorie_bereinigen,
                                   text_bereinigen)
from app.models import Artikel, QUELLE_PV

# Reihenfolge = Vergabereihenfolge der PV-Nummern (Positionslisten zuerst,
# das Musterangebot liefert nur die Positionen, die dort allein vorkommen)
PV_DATEIEN = [
    ("Ersatz Position PV.xlsx", "Ersatz Position PV"),
    ("Ersatz Sigenergy Position PV.xlsx", "Sigenergy"),
    ("Elektro Allgemein.xlsx", "Elektro Allgemein"),
    ("Musterangebot PV.xlsx", "Musterangebot PV"),
]

FELDER_PV = ["kategorie", "beschreibung", "menge_standard", "einheit",
             "e_preis_cent", "ep_flag", "ek_cent"]


def pv_ordner():
    return config.PV_PREISLISTEN_ORDNER


def pv_nummer(zahl: int) -> str:
    return f"PV{zahl:03d}"


def _nummer_zahl(pos_nr: str) -> int:
    m = re.fullmatch(r"PV(\d+)", pos_nr or "")
    return int(m.group(1)) if m else 0


def erste_zeile(text: str) -> str:
    """Bezeichnung = erste Textzeile; „(Optionale Position)“ davor zählt nicht."""
    zeilen = [z.strip() for z in (text or "").splitlines() if z.strip()]
    if len(zeilen) > 1 and zeilen[0].lower().startswith("(optionale position"):
        return zeilen[1]
    return zeilen[0] if zeilen else ""


def pins_lesen() -> dict[str, str]:
    """Blatt „PV-Artikel“ der Logik-Excel: GUID → PV-Nr. (leer = ohne Pins)."""
    pfad = config.LOGIK_EXCEL_PFAD
    if not pfad.exists():
        return {}
    wb = openpyxl.load_workbook(pfad, read_only=True, data_only=True)
    if "PV-Artikel" not in wb.sheetnames:
        return {}
    pins: dict[str, str] = {}
    zeilen = wb["PV-Artikel"].iter_rows(values_only=True)
    kopf = [str(z or "").strip() for z in next(zeilen, [])]
    try:
        i_nr, i_guid = kopf.index("PV-Nr."), kopf.index("GUID")
    except ValueError:
        return {}
    for row in zeilen:
        nr = str(row[i_nr] or "").strip()
        guid = str(row[i_guid] or "").strip()
        if nr and guid:
            pins[guid] = nr
    return pins


@dataclass
class PvLeseErgebnis:
    artikel: list[dict] = field(default_factory=list)
    warnungen: list[str] = field(default_factory=list)
    hinweistexte: dict[str, str] = field(default_factory=dict)   # Datei -> „*…“-Text


def lese_pv_dateien(pins: dict[str, str] | None = None) -> PvLeseErgebnis:
    """Liest alle PV-Positionslisten; pos_nr ist bei gepinnten GUIDs gesetzt,
    sonst leer (Vergabe erst beim Abgleich mit der Datenbank)."""
    pins = pins_lesen() if pins is None else pins
    ergebnis = PvLeseErgebnis()
    for dateiname, kurz in PV_DATEIEN:
        pfad = pv_ordner() / dateiname
        if not pfad.exists():
            ergebnis.warnungen.append(f"PV-Positionsliste fehlt: {pfad}")
            continue
        wb = openpyxl.load_workbook(pfad, data_only=True)
        ws = wb[wb.sheetnames[0]]
        zeilen = ws.iter_rows(values_only=True)
        spalten_warnungen: list[str] = []
        indizes = _header_indizes(next(zeilen), spalten_warnungen)

        def zelle(row, name):
            i = indizes.get(name)
            return row[i] if i is not None and i < len(row) else None

        kategorie = ""
        for zeile_nr, row in enumerate(zeilen, start=2):
            guid = zelle(row, "GUID")
            beschreibung = zelle(row, "Beschreibung")
            pos = zelle(row, "Position")
            if guid is None and beschreibung is None:
                continue
            if pos is None:
                text = kategorie_bereinigen(beschreibung)
                if text.startswith("*"):
                    # Hinweiszeile (z. B. Modul-Verfügbarkeit) – keine Kategorie
                    ergebnis.hinweistexte[kurz] = text_bereinigen(beschreibung)
                    continue
                kategorie = text
                continue
            text = text_bereinigen(beschreibung)
            if not text:
                ergebnis.warnungen.append(
                    f"{kurz} Pos. {pos}: leere Zeile ohne Beschreibung – übersprungen.")
                continue
            if guid is None:
                ergebnis.warnungen.append(f"{kurz} Pos. {pos}: ohne GUID – übersprungen.")
                continue
            e_preis = zelle(row, "E-Preis")
            g_preis = zelle(row, "G-Preis")
            ek = zelle(row, "Einkaufspreis Material")
            guid = str(guid).strip()
            ergebnis.artikel.append({
                "guid": guid,
                "pos_nr": pins.get(guid, ""),
                "kategorie": f"PV · {kurz}" + (f" · {kategorie}" if kategorie
                                               and not kategorie.startswith("Komplettpaket")
                                               else ""),
                "bezeichnung": "",
                "beschreibung": text,
                "menge_standard": 1.0,
                "einheit": str(zelle(row, "Einheit") or "").strip(),
                "e_preis_cent": euro_zu_cent(e_preis or 0),
                "ep_flag": isinstance(g_preis, str) and "EP" in g_preis,
                "ek_cent": euro_zu_cent(ek) if ek not in (None, "") else None,
                "quelle": QUELLE_PV,
                "_datei": kurz,
                "_position": str(pos).strip(),
            })
    _dubletten_melden(ergebnis)
    return ergebnis


def _dubletten_melden(ergebnis: PvLeseErgebnis) -> None:
    """Gleiche Bezeichnung in mehreren Listen mit abweichendem VK/EK – nur
    Hinweis (jede Zeile bleibt ein eigener Artikel; welche Zeile die Logik
    nutzt, steht im Blatt „Aktionen PV“)."""
    nach_titel: dict[str, list[dict]] = {}
    for a in ergebnis.artikel:
        nach_titel.setdefault(erste_zeile(a["beschreibung"]).lower(), []).append(a)
    for titel, liste in nach_titel.items():
        preise = {(a["e_preis_cent"], a["ek_cent"]) for a in liste}
        if len(liste) > 1 and len(preise) > 1:
            teile = ", ".join(
                f"{a['_datei']} Pos. {a['_position']}: VK {a['e_preis_cent'] / 100:.2f} / "
                f"EK {(a['ek_cent'] or 0) / 100:.2f}" for a in liste)
            ergebnis.warnungen.append(
                f"Abweichende Preise für „{erste_zeile(liste[0]['beschreibung'])}“ – {teile}")


def _zuordnen(session: Session, ergebnis: PvLeseErgebnis):
    """Ordnet jede gelesene Zeile einem Bestandsartikel zu und vergibt fehlende
    PV-Nummern. Liefert [(daten, bestand_oder_None)] + Bestand."""
    bestand = session.query(Artikel).filter(Artikel.quelle == QUELLE_PV).all()
    nach_nr = {a.pos_nr: a for a in bestand}
    nach_guid = {a.guid: a for a in bestand if a.guid}
    naechste = max([_nummer_zahl(a.pos_nr) for a in bestand]
                   + [_nummer_zahl(d["pos_nr"]) for d in ergebnis.artikel] + [0]) + 1
    vergeben: set[int] = set()
    paare = []
    for daten in ergebnis.artikel:
        vorhanden = None
        if daten["pos_nr"]:
            vorhanden = nach_nr.get(daten["pos_nr"]) or nach_guid.get(daten["guid"])
        else:
            vorhanden = nach_guid.get(daten["guid"])
            if vorhanden is None:
                titel = erste_zeile(daten["beschreibung"]).lower()
                for a in bestand:
                    if (a.id not in vergeben and a.kategorie.startswith(f"PV · {daten['_datei']}")
                            and erste_zeile(a.beschreibung).lower() == titel
                            and a.guid not in {d["guid"] for d in ergebnis.artikel}):
                        vorhanden = a
                        break
            if vorhanden is not None:
                daten["pos_nr"] = vorhanden.pos_nr
            else:
                daten["pos_nr"] = pv_nummer(naechste)
                naechste += 1
        if vorhanden is not None:
            vergeben.add(vorhanden.id)
        paare.append((daten, vorhanden))
    return paare, bestand


def berechne_diff(session: Session, ergebnis: PvLeseErgebnis | None = None) -> Diff:
    ergebnis = ergebnis or lese_pv_dateien()
    diff = Diff(warnungen=list(ergebnis.warnungen))
    paare, bestand = _zuordnen(session, ergebnis)
    gefunden = set()
    for daten, vorhanden in paare:
        if vorhanden is None:
            diff.neu.append(daten)
            continue
        gefunden.add(vorhanden.id)
        felder = [f for f in FELDER_PV if getattr(vorhanden, f) != daten[f]]
        if vorhanden.guid != daten["guid"]:
            felder.append("guid")
        if felder:
            diff.geaendert.append((vorhanden, daten,
                                   [FELD_NAMEN.get(f, "GUID") for f in felder]))
        else:
            diff.unveraendert += 1
        if not vorhanden.aktiv:
            diff.reaktiviert.append(vorhanden)
    diff.entfallen = [a for a in bestand if a.id not in gefunden and a.aktiv]
    for a in diff.entfallen:
        diff.warnungen.append(
            f"{a.pos_nr} „{a.titel[:60]}“ ist in keiner PV-Positionsliste mehr – wird deaktiviert.")
    return diff


def import_ausfuehren(session: Session) -> tuple[Diff, str]:
    ergebnis = lese_pv_dateien()
    diff = berechne_diff(session, ergebnis)
    # Abgleich erneut ausführen (berechne_diff vergibt Nummern nur in den Daten)
    ergebnis = lese_pv_dateien()
    paare, _bestand = _zuordnen(session, ergebnis)
    fremde_guids = {g for (g,) in session.query(Artikel.guid)
                    .filter(Artikel.quelle != QUELLE_PV, Artikel.guid.isnot(None))}
    for daten, vorhanden in paare:
        werte = {k: v for k, v in daten.items() if not k.startswith("_")}
        if werte["guid"] in fremde_guids:   # GUID gehört einem WP-Artikel
            werte["guid"] = None
        if vorhanden is None:
            session.add(Artikel(**werte, aktiv=True))
        else:
            for feld in FELDER_PV + ["pos_nr", "guid"]:
                setattr(vorhanden, feld, werte[feld])
            vorhanden.aktiv = True
    for artikel in diff.entfallen:
        artikel.aktiv = False
    session.commit()
    meldung = (f"PV: {len(diff.neu)} neu, {len(diff.geaendert)} geändert, "
               f"{diff.unveraendert} unverändert, {len(diff.entfallen)} deaktiviert")
    return diff, meldung
