# Angebots-Zusammenbau (Phase 5): erzeugt aus einer fertigen Konfiguration die
# Angebotspositionen laut Blatt "Angebotsaufbau" – Blockreihenfolge, Gruppen-
# Überschriften (inkl. dynamischer Überschrift Block 1), Gruppen-Trigger Pos. 014,
# Heizkörper-Pauschale 129 × Gesamtanzahl, Verteiler-Pauschale 108 × Anzahl, EP-Regel.
# Außerdem: transaktionssicherer Nummernkreis AN-C-<JJ><NNNN> ab AN-C-261000.

import json
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config
from app import konfigurator as engine
from app.logik import Logik
from app.models import Angebot, AngebotsPosition, Artikel, Konfiguration


@dataclass
class GewaehlterArtikel:
    ref: str            # Pos-Nr. ("045") oder Z-Nr. ("Z01")
    menge: float
    ep: bool
    quelle_frage: str   # "F06", "paket", "puffer", "grundpaket", "trigger", ...


# --- Artikel aus den Antworten ermitteln ----------------------------------

def _menge_aufloesen(menge_roh: str, antwort) -> float:
    """Mengen-Ausdruck einer Aktionszeile: Zahl direkt ('1', '2'), sonst der
    eingegebene Zahlenwert ('eingegebene Meter', 'Anzahl Verteiler')."""
    zahl = engine.zahl_parsen(menge_roh)
    if zahl is not None:
        return zahl
    antwortzahl = antwort if isinstance(antwort, (int, float)) else engine.zahl_parsen(antwort)
    return float(antwortzahl) if antwortzahl is not None else 1.0


def artikel_ermitteln(logik: Logik, antworten: dict) -> list[GewaehlterArtikel]:
    gewaehlt: list[GewaehlterArtikel] = []

    for frage in engine.sichtbare_fragen(logik, antworten):
        if frage.id not in antworten:
            continue
        wert = antworten[frage.id]

        if frage.typ == "Mengenmaske (4 Zahlenfelder)":
            # F17: je Größe die passende Aktionszeile ("Anzahl S" -> Z18 × Anzahl)
            gesamt = 0
            for groesse, anzahl in wert.items():
                if not anzahl:
                    continue
                gesamt += int(anzahl)
                for aktion in logik.aktionen:
                    if (aktion.frage == frage.id
                            and re.fullmatch(rf"Anzahl\s+{groesse}", aktion.antwort)):
                        for ref in aktion.artikel:
                            gewaehlt.append(GewaehlterArtikel(
                                ref.ref, float(anzahl), ref.ep, frage.id))
            if gesamt:
                # Heizkörper-Pauschale: Pos. 129 × Gesamtanzahl aller Heizkörper
                gewaehlt.append(GewaehlterArtikel("129", float(gesamt), False, frage.id))
            continue

        if frage.typ == "Wiederholfeld je Verteiler":
            # F20: je Verteiler die passende Größen-Zeile; gleiche Artikel zusammenfassen
            zaehler: dict[str, float] = {}
            for gruppenzahl in wert:
                aktion = engine.aktion_finden(logik, frage, gruppenzahl, antworten)
                if aktion and aktion.typ == "normal":
                    for ref in aktion.artikel:
                        zaehler[ref.ref] = zaehler.get(ref.ref, 0) + 1
            for ref_nr, anzahl in zaehler.items():
                gewaehlt.append(GewaehlterArtikel(ref_nr, anzahl, False, frage.id))
            continue

        aktion = engine.aktion_finden(logik, frage, wert, antworten)
        if aktion is None or aktion.typ != "normal":
            continue
        for ref in aktion.artikel:
            gewaehlt.append(GewaehlterArtikel(
                ref.ref, _menge_aufloesen(ref.menge, wert), ref.ep, frage.id))

    # Paket laut Paketmatrix (F02 + F03/F04)
    for ref in (engine.paket_aufloesen(logik, antworten) or []):
        gewaehlt.append(GewaehlterArtikel(ref.ref, 1.0, ref.ep, "paket"))

    # Grundpaket und Gruppen-Trigger aus den Spezial-Aktionszeilen
    friondo_ja = any(antworten.get(f) == "Ja" for f in ("F27", "F28", "F29"))
    for aktion in logik.aktionen:
        if aktion.frage == "Grundpaket":
            for ref in aktion.artikel:
                gewaehlt.append(GewaehlterArtikel(ref.ref, 1.0, ref.ep, "grundpaket"))
        elif aktion.frage == "Gruppen-Trigger" and friondo_ja:
            for ref in aktion.artikel:
                gewaehlt.append(GewaehlterArtikel(ref.ref, 1.0, ref.ep, "trigger"))
    return gewaehlt


# --- Blockzuordnung laut Angebotsaufbau -----------------------------------

def _block_sichtbar(block, antworten: dict, logik: Logik) -> bool:
    b = block.wann
    if b is None or b.art == "immer":
        return True
    if b.art == "friondo_ja":
        return any(antworten.get(f) == "Ja" for f in ("F27", "F28", "F29"))
    if b.art == "antwort":
        return str(antworten.get(b.frage_id) or "") in b.werte
    return True


def _position_im_inhalt(block, artikel: GewaehlterArtikel) -> int:
    """Zeichenindex der Referenz bzw. Quell-Frage im Block-Inhalt; -1 = nicht enthalten."""
    inhalt = block.inhalt_roh
    ref = artikel.ref
    if ref.startswith("Z"):
        m = re.search(rf"\b{ref}\b", inhalt)
        if m:
            return m.start()
        # Z-Bereiche wie "Z01–Z14"
        for m in re.finditer(r"\bZ(\d{2})\s*[–-]\s*Z(\d{2})", inhalt):
            if int(m.group(1)) <= int(ref[1:]) <= int(m.group(2)):
                return m.start()
    else:
        for m in re.finditer(r"Pos\.\s*((?:\d{1,3}(?:\s*\(EP\))?\s*(?:[,/]\s*)?)+)", inhalt):
            nummern = re.findall(r"\d{1,3}", m.group(1))
            if ref.lstrip("0") in [n.lstrip("0") for n in nummern]:
                versatz = m.group(0).find(ref)
                if versatz < 0:
                    versatz = m.group(0).find(ref.lstrip("0"))
                return m.start() + max(versatz, 0)
    if artikel.quelle_frage.startswith("F"):
        m = re.search(rf"\b{artikel.quelle_frage}\b", inhalt)
        if m:
            return m.start()
    if artikel.quelle_frage == "paket" and "Paketmatrix" in inhalt:
        return inhalt.find("Paketmatrix")
    return -1


def _block_ueberschrift(block, antworten: dict, erste_kategorie: str) -> str:
    u = block.ueberschrift
    if u.startswith("(ohne"):
        return ""
    if "aus der Preisliste" in u:
        return erste_kategorie
    if u.startswith("DYNAMISCH"):
        zitate = re.findall(r"'([^']+)'", u)
        basis = zitate[0] if zitate else ""
        if antworten.get("F03") == "Ja" and len(zitate) > 1 and zitate[1].startswith("…"):
            kopf = basis.split(" mit ")[0]
            return kopf + " " + zitate[1].lstrip("… ").strip()
        return basis
    return u


def positionen_zusammenstellen(logik: Logik, antworten: dict,
                               session: Session) -> list[dict]:
    """Liefert die fertigen Positions-Snapshots in Blockreihenfolge."""
    gewaehlt = artikel_ermitteln(logik, antworten)

    # Artikel-Stammdaten laden
    artikel_map: dict[str, Artikel] = {}
    for a in session.query(Artikel).filter(Artikel.aktiv.is_(True)):
        if a.pos_nr:
            artikel_map[a.pos_nr] = a

    # jedem gewählten Artikel seinen Block + Sortierindex zuweisen
    zugeordnet: list[tuple[int, int, GewaehlterArtikel]] = []
    for artikel in gewaehlt:
        platziert = False
        for block in logik.bloecke:
            if "Summenblock" in block.ueberschrift:
                continue
            if not _block_sichtbar(block, antworten, logik):
                continue
            index = _position_im_inhalt(block, artikel)
            if index >= 0:
                zugeordnet.append((block.nr, index, artikel))
                platziert = True
                break
        if not platziert:
            # Fallback: letzter Block ohne Überschrift vor dem Summenblock
            zugeordnet.append((7, 9999, artikel))

    zugeordnet.sort(key=lambda t: (t[0], t[1]))

    # gleiche Artikel im selben Block zusammenfassen
    positionen: list[dict] = []
    gesehen: dict[tuple[int, str], dict] = {}
    bloecke_map = {b.nr: b for b in logik.bloecke}
    for block_nr, _, gw in zugeordnet:
        schluessel = (block_nr, gw.ref)
        if schluessel in gesehen:
            gesehen[schluessel]["menge"] += gw.menge
            continue
        stamm = artikel_map.get(gw.ref)
        if stamm is None:
            continue  # Validierung meldet fehlende Artikel bereits im Adminbereich
        eintrag = {
            "block_nr": block_nr,
            "gruppe": "",
            "pos_nr": stamm.pos_nr,
            "bezeichnung": stamm.bezeichnung,
            "beschreibung": stamm.beschreibung,
            "menge": gw.menge,
            "einheit": stamm.einheit,
            "e_preis_cent": stamm.e_preis_cent,
            "ep_flag": stamm.ep_flag or gw.ep,
        }
        gesehen[schluessel] = eintrag
        positionen.append(eintrag)

    # Gruppen-Überschriften setzen; bei "aus der Preisliste" zählt die Kategorie
    # des ersten Preislisten-Artikels im Block (Z-Artikel stehen unter "Zusatzartikel")
    for block_nr in sorted({p["block_nr"] for p in positionen}):
        block = bloecke_map.get(block_nr)
        if block is None:
            continue
        kategorie = ""
        for p in positionen:
            if p["block_nr"] != block_nr:
                continue
            stamm = artikel_map.get(p["pos_nr"])
            if stamm is None:
                continue
            kategorie = stamm.kategorie
            if stamm.quelle == "preisliste":
                break
        ueberschrift = _block_ueberschrift(block, antworten, kategorie)
        for p in positionen:
            if p["block_nr"] == block_nr:
                p["gruppe"] = ueberschrift

    for sort, p in enumerate(positionen, 1):
        p["sort"] = sort
    return positionen


# --- Nummernkreis ---------------------------------------------------------

def naechste_angebotsnummer(session: Session) -> str:
    jj = datetime.now().year % 100
    praefix = f"{config.NUMMERNKREIS_PREFIX}{jj}"
    letzte = (session.query(Angebot.nummer)
              .filter(Angebot.nummer.like(f"{praefix}%"))
              .order_by(Angebot.nummer.desc()).first())
    if letzte:
        zaehler = int(letzte[0][len(praefix):]) + 1
    else:
        zaehler = config.NUMMERNKREIS_START_ZAEHLER
    return f"{praefix}{zaehler}"


def angebot_anlegen(session: Session, kunde_id: int,
                    konfiguration: Konfiguration | None = None,
                    logik: Logik | None = None) -> Angebot:
    """Legt ein Angebot mit transaktionssicherer Nummer an (Retry bei Kollision)."""
    protokoll_json = "[]"
    kfw_json = "{}"
    positionen: list[dict] = []
    if konfiguration is not None and logik is not None:
        antworten = json.loads(konfiguration.antworten_json or "{}")
        protokoll_json = json.dumps(engine.protokoll(logik, antworten), ensure_ascii=False)
        kfw_json = json.dumps(
            {f: antworten.get(f) for f in ("F30", "F31", "F32", "F33", "F34", "F35", "F36")
             if f in antworten}, ensure_ascii=False)
        positionen = positionen_zusammenstellen(logik, antworten, session)

    for _versuch in range(5):
        angebot = Angebot(
            nummer=naechste_angebotsnummer(session),
            kunde_id=kunde_id,
            konfiguration_id=konfiguration.id if konfiguration else None,
            protokoll_json=protokoll_json,
            kfw_json=kfw_json,
        )
        for p in positionen:
            angebot.positionen.append(AngebotsPosition(**p))
        session.add(angebot)
        try:
            session.commit()
            return angebot
        except IntegrityError:
            session.rollback()
    raise RuntimeError("Angebotsnummer konnte nicht vergeben werden (Nummernkreis-Kollision).")
