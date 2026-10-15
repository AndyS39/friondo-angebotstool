# v34 (PLAN_V21 Phase 180, Agent V): TAIFUN-Angebots-PDF lesen – Textextraktion mit pypdf
# (reine Python-Bibliothek, keine OCR: gescannte PDFs liefern keinen Text) und Erkennung der
# Felder für den Dialog „Extern erledigt“ (v7) bzw. das Ersetzen am TAIFUN-Eintrag (v10):
#   - TAIFUN-Angebotsnummer   Muster AN\d{6} hinter „ANGEBOT - Nr.:“
#   - Datum                   „Datum : TT.MM.JJJJ“ auf der ERSTEN Seite
#   - Endbetrag brutto        Zeile „Gesamt-Betrag € x.xxx,xx“; steht „= Endbetrag“ im PDF
#                             (Angebot mit Rabatt), gilt dieser Wert
#   - Sparte                  nur als Vorschlag aus Schlagwörtern der ersten Seite
#                             (Wallbox / Wärmepumpe / Klimaanlage / Photovoltaik) [ANNAHME]
# Nicht Erkanntes bleibt leer; jedes gelesene Feld trägt in der Oberfläche den Hinweis
# „aus PDF gelesen – bitte prüfen“ (taifun_pdf.js). Die Routen liegen in
# app/routers/taifun_pdf.py (POST /angebote/extern/pdf-lesen) und routers/angebote.py
# (POST /angebote/{id}/taifun-pdf, Ersetzen mit Sicherheitsabfrage + „übernehmen“-Häkchen).
# Kein Datenbankzugriff in diesem Modul außer eintrag_pdf_speichern (bekommt die Sitzung).

from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024          # Plan: ein PDF, höchstens 20 MB
SEITEN_TRENNER = "\f"                 # text_lesen trennt Seiten mit Formfeed
HINWEIS_PRUEFEN = "aus PDF gelesen – bitte prüfen"
HINWEIS_KEIN_TEXT = "Kein Text im PDF gefunden"
MELDUNG_KEIN_PDF = "Die Datei ist kein PDF."
MELDUNG_ZU_GROSS = "Das PDF ist größer als 20 MB – bitte eine kleinere Datei wählen."

# Muster (Groß-/Kleinschreibung egal, Leerraum auch über Zeilenumbrüche)
_NUMMER_BESCHRIFTET = re.compile(r"ANGEBOT\s*[-–]?\s*Nr\.?\s*:?\s*(AN\d{6})\b", re.IGNORECASE)
_NUMMER_FREI = re.compile(r"\bAN\d{6}\b")
_DATUM = re.compile(r"Datum\s*:?\s*(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{4})", re.IGNORECASE)
_BETRAG = r"(?:€|EUR)?\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})"
_ENDBETRAG = re.compile(r"=?\s*Endbetrag\s*:?\s*" + _BETRAG, re.IGNORECASE)
_GESAMT = re.compile(r"Gesamt\s*-?\s*Betrag\s*:?\s*" + _BETRAG, re.IGNORECASE)
# Sparten-Schlagwörter der ersten Seite [ANNAHME: Plan nennt die vier Grundbegriffe –
# ergänzt um gängige Synonyme der TAIFUN-Texte]
_SPARTEN_WOERTER = {
    "WB": ("wallbox", "ladestation", "amtron"),
    "WP": ("wärmepumpe", "waermepumpe", "wärmepumpen"),
    "KL": ("klimaanlage", "klimagerät", "klimageraet", "split-klima", "klimaanlagen"),
    "PV": ("photovoltaik", "pv-anlage", "solarmodul", "pv-module"),
}


def ist_pdf(inhalt: bytes) -> bool:
    """Grobe Prüfung über die Dateisignatur (wie v10/v18: „%PDF“)."""
    return isinstance(inhalt, (bytes, bytearray)) and bytes(inhalt[:5]).startswith(b"%PDF")


def groesse_pruefen(anzahl_bytes: int) -> str:
    """Leer = in Ordnung, sonst die Meldung für die Oberfläche."""
    if anzahl_bytes > MAX_BYTES:
        return MELDUNG_ZU_GROSS
    return ""


def _als_bytes(datei) -> bytes:
    if isinstance(datei, (bytes, bytearray)):
        return bytes(datei)
    if isinstance(datei, (str, Path)):
        return Path(datei).read_bytes()
    lesen = getattr(datei, "read", None)
    if lesen is None:
        raise TypeError("text_lesen erwartet bytes, einen Pfad oder ein Datei-Objekt")
    if hasattr(datei, "seek"):
        try:
            datei.seek(0)
        except (OSError, ValueError):
            pass
    inhalt = lesen()
    return inhalt if isinstance(inhalt, bytes) else bytes(inhalt)


def text_lesen(datei) -> str:
    """Text aller Seiten (pypdf), Seiten getrennt durch SEITEN_TRENNER. `datei` ist
    bytes, ein Pfad oder ein Datei-Objekt. Liefert „“ bei leeren Seiten (Scan ohne
    Textebene), bei unlesbaren/verschlüsselten PDFs und bei Nicht-PDFs – die Oberfläche
    meldet dann HINWEIS_KEIN_TEXT. Wirft nie (Lesen darf den Dialog nicht blockieren)."""
    try:
        inhalt = _als_bytes(datei)
    except (OSError, TypeError, ValueError):
        return ""
    if not ist_pdf(inhalt):
        return ""
    try:
        from pypdf import PdfReader
        leser = PdfReader(BytesIO(inhalt))
        if getattr(leser, "is_encrypted", False):
            try:
                leser.decrypt("")        # leeres Benutzerpasswort (nur Rechteverschlüsselung)
            except Exception:            # pragma: no cover – je nach pypdf-Version
                return ""
        seiten = []
        for seite in leser.pages:
            try:
                seiten.append(seite.extract_text() or "")
            except Exception:            # einzelne kaputte Seite überspringen
                seiten.append("")
    except Exception:
        return ""
    text = SEITEN_TRENNER.join(seiten)
    return text if text.strip() else ""


def _erste_seite(text: str) -> str:
    return (text or "").split(SEITEN_TRENNER, 1)[0]


def betrag_in_cent(wert: str) -> int | None:
    """„4.315,23“ → 431523; None bei Unsinn."""
    roh = (wert or "").strip().replace(" ", "")
    if not re.fullmatch(r"\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}", roh):
        return None
    euro, cent = roh.replace(".", "").split(",")
    return int(euro) * 100 + int(cent)


def cent_als_text(cent: int | None) -> str:
    """431523 → „4.315,23“ (Eingabeformat des Dialogs, wie preis_parsen es liest)."""
    if cent is None:
        return ""
    vorzeichen = "-" if cent < 0 else ""
    cent = abs(int(cent))
    euro, rest = divmod(cent, 100)
    return f"{vorzeichen}{euro:,}".replace(",", ".") + f",{rest:02d}"


def _datum_erkennen(erste_seite: str) -> str:
    for treffer in _DATUM.finditer(erste_seite):
        tag, monat, jahr = (int(treffer.group(1)), int(treffer.group(2)), int(treffer.group(3)))
        try:
            return datetime(jahr, monat, tag).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def _sparte_erkennen(erste_seite: str) -> tuple[str, str]:
    """(Sparte, Hinweis) – Sparte mit den meisten Treffern; Gleichstand → leer + Hinweis."""
    klein = (erste_seite or "").lower()
    zaehler = {}
    for sparte, woerter in _SPARTEN_WOERTER.items():
        anzahl = sum(klein.count(w) for w in woerter)
        if anzahl:
            zaehler[sparte] = anzahl
    if not zaehler:
        return "", ""
    geordnet = sorted(zaehler.items(), key=lambda e: (-e[1], e[0]))
    if len(geordnet) > 1 and geordnet[0][1] == geordnet[1][1]:
        return "", ("Mehrere Sparten im PDF erkannt ("
                    + ", ".join(s for s, _ in geordnet) + ") – Sparte bitte selbst prüfen")
    return geordnet[0][0], ""


def felder_erkennen(text: str) -> dict:
    """Felder aus dem PDF-Text: {nummer, datum (ISO „JJJJ-MM-TT“), endbetrag_cent, sparte,
    hinweise}. Nicht Erkanntes bleibt leer/None; `hinweise` ist eine Liste von Sätzen für
    die Oberfläche (leer = alles gefunden)."""
    text = text or ""
    hinweise: list[str] = []
    if not text.strip():
        return {"nummer": "", "datum": "", "endbetrag_cent": None, "sparte": "",
                "hinweise": [HINWEIS_KEIN_TEXT]}
    erste = _erste_seite(text)
    # Nummer: beschriftet (ganzes Dokument), sonst erstes freies AN-Muster der ersten Seite
    nummer = ""
    treffer = _NUMMER_BESCHRIFTET.search(text)
    if treffer:
        nummer = treffer.group(1).upper()
    else:
        frei = _NUMMER_FREI.search(erste)
        if frei:
            nummer = frei.group(0).upper()
            hinweise.append("Angebotsnummer ohne Beschriftung „ANGEBOT - Nr.:“ gefunden – bitte prüfen")
        else:
            hinweise.append("Angebotsnummer nicht erkannt")
    datum = _datum_erkennen(erste)
    if not datum:
        hinweise.append("Datum nicht erkannt")
    # Endbetrag: „= Endbetrag“ (Rabatt) geht vor „Gesamt-Betrag“; letzter Treffer zählt
    # (Summenblock steht am Ende des Positionsteils)
    endbetrag_cent = None
    for muster in (_ENDBETRAG, _GESAMT):
        treffer_liste = list(muster.finditer(text))
        if treffer_liste:
            endbetrag_cent = betrag_in_cent(treffer_liste[-1].group(1))
            if endbetrag_cent is not None:
                break
    if endbetrag_cent is None:
        hinweise.append("Endbetrag (Gesamt-Betrag) nicht erkannt")
    sparte, sparten_hinweis = _sparte_erkennen(erste)
    if sparten_hinweis:
        hinweise.append(sparten_hinweis)
    return {"nummer": nummer, "datum": datum, "endbetrag_cent": endbetrag_cent,
            "sparte": sparte, "hinweise": hinweise}


def formular_werte(text: str) -> dict:
    """JSON-fertige Werte für die Oberfläche (pdf-lesen): nummer, datum (ISO für
    <input type=date>), endbetrag („4.315,23“), sparte, hinweis (ein Satz oder leer),
    text_gefunden."""
    felder = felder_erkennen(text)
    return {
        "ok": True,
        "nummer": felder["nummer"],
        "datum": felder["datum"],
        "endbetrag": cent_als_text(felder["endbetrag_cent"]),
        "endbetrag_cent": felder["endbetrag_cent"],
        "sparte": felder["sparte"],
        "hinweis": " · ".join(felder["hinweise"]),
        "text_gefunden": bool((text or "").strip()),
        "pruefen": HINWEIS_PRUEFEN,
    }


# --- Ablage am externen TAIFUN-Eintrag (Sitzung vom Aufrufer) --------------------------

def pdf_ablegen(angebot, inhalt: bytes) -> Path:
    """PDF unter data/angebote/extern/<EXT-Nummer>.pdf speichern (ersetzt; wie v10) und
    die Felder extern_pdf_pfad/_am setzen. Rückgabe: Zielpfad."""
    from datetime import datetime as dt

    from app import config
    ordner = config.ANGEBOTE_PDF_ORDNER / "extern"
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / f"{angebot.nummer}.pdf"
    ziel.write_bytes(inhalt)
    angebot.extern_pdf_pfad = str(ziel)
    angebot.extern_pdf_am = dt.now()
    return ziel


def galerie_ablegen(session, angebot, inhalt: bytes, benutzer, sparte: str,
                    quelle: str, bemerkung: str):
    """Kopie des TAIFUN-PDFs in die Galerie „Allgemein“ des Vorgangs (wie v18 bei den
    Auftragsdaten). Liefert den Galerie-Eintrag oder None (ohne Vorgang)."""
    from app import galerie
    from app import vorgaenge as vorgaenge_modul
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    if vorgang is None:
        return None
    name = f"{(angebot.taifun_nummer or angebot.nummer).strip() or angebot.nummer}.pdf"
    return galerie.speichern(session, vorgang.id, "Allgemein", name, inhalt,
                             benutzer=benutzer, quelle=quelle, bemerkung=bemerkung,
                             sparte=sparte or (angebot.konfigurator_typ or "WP"))


UEBERNEHMBAR = ("nummer", "datum", "endbetrag")


def eintrag_pdf_speichern(session, angebot, inhalt: bytes, benutzer,
                          uebernehmen=(), felder: dict | None = None) -> dict:
    """Ersetzen/Hinterlegen am TAIFUN-Eintrag (v10-Feld extern_pdf_pfad) + Galerie-Kopie;
    `uebernehmen` ⊆ {nummer, datum, endbetrag} übernimmt die aus dem NEUEN PDF gelesenen
    Werte (serverseitig gelesen – Werte aus dem Browser werden nie übernommen).
    `felder` = Ergebnis von felder_erkennen(text_lesen(inhalt)); die Route liest es VOR dem
    ersten Datenbankzugriff (Entscheidung Orchestrator 15.10.2026, v33-Upload-Regel: kein
    pypdf-Parsen innerhalb der Schreibtransaktion) – ohne Übergabe wird hier gelesen.
    Rückgabe {ersetzt, felder, uebernommen: [Text je Feld], nicht_erkannt: [Feld]}."""
    from app.models import AngebotsNotiz
    ersetzt = bool(angebot.extern_pdf_pfad)
    pdf_ablegen(angebot, inhalt)
    if felder is None:
        felder = felder_erkennen(text_lesen(inhalt))
    uebernommen: list[str] = []
    nicht_erkannt: list[str] = []
    gewuenscht = {str(u).strip().lower() for u in (uebernehmen or ())}
    if "nummer" in gewuenscht:
        if felder["nummer"]:
            angebot.taifun_nummer = felder["nummer"][:30]
            uebernommen.append(f"Nummer {felder['nummer']}")
        else:
            nicht_erkannt.append("Nummer")
    if "datum" in gewuenscht:
        if felder["datum"]:
            angebot.datum = datetime.strptime(felder["datum"], "%Y-%m-%d")
            uebernommen.append(f"Datum {angebot.datum.strftime('%d.%m.%Y')}")
        else:
            nicht_erkannt.append("Datum")
    if "endbetrag" in gewuenscht:
        if felder["endbetrag_cent"]:
            angebot.extern_endbetrag_cent = felder["endbetrag_cent"]
            uebernommen.append(f"Endbetrag {cent_als_text(felder['endbetrag_cent'])} €")
        else:
            nicht_erkannt.append("Endbetrag")
    galerie_ablegen(session, angebot, inhalt, benutzer,
                    sparte=angebot.konfigurator_typ or "WP", quelle="taifun_pdf",
                    bemerkung="TAIFUN-Angebot" + (" (ersetzt)" if ersetzt else ""))
    text = ("TAIFUN-PDF ersetzt" if ersetzt else "TAIFUN-PDF hinterlegt")
    if uebernommen:
        text += " – aus dem PDF übernommen: " + ", ".join(uebernommen)
    session.add(AngebotsNotiz(angebot_id=angebot.id,
                              benutzer_name=benutzer.name if benutzer else "?", text=text))
    return {"ersetzt": ersetzt, "felder": felder, "uebernommen": uebernommen,
            "nicht_erkannt": nicht_erkannt}


def meldung_fuer(ergebnis: dict) -> str:
    """Meldungstext der Oberfläche nach eintrag_pdf_speichern."""
    text = ("PDF ersetzt" if ergebnis["ersetzt"] else "PDF hinterlegt") + \
        " – der Eintrag ist im Kombi-Versand wählbar."
    if ergebnis["uebernommen"]:
        text += " Aus dem PDF übernommen: " + ", ".join(ergebnis["uebernommen"]) + "."
    if ergebnis["nicht_erkannt"]:
        text += (" Nicht im PDF erkannt (unverändert): "
                 + ", ".join(ergebnis["nicht_erkannt"]) + ".")
    return text
