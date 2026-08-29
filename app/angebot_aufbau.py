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
from app.logik import (Logik, antwort_teile as logik_antwort_teile,
                       refs_extrahieren as logik_refs_extrahieren)
from app.models import Angebot, AngebotsPosition, Artikel, Konfiguration, Kunde


def _mengenmaske_ref(zeilen, option: str):
    """Artikel-Referenz zu einem Mengenmasken-Feld: paarweise Slash-Liste
    ("Anzahl S / M / L / XL") oder eigene Zeile je Feld (D05)."""
    for zeile in zeilen:
        teile = [re.sub(r"^Anzahl\s+", "", t)
                 for t in logik_antwort_teile(zeile.antwort)]
        if option in teile:
            index = teile.index(option)
            if len(teile) > 1 and len(zeile.artikel) == len(teile):
                return zeile.artikel[index]
            if zeile.artikel:
                return zeile.artikel[0]
    return None


@dataclass
class GewaehlterArtikel:
    ref: str            # Pos-Nr. ("045") oder Z-Nr. ("Z01")
    menge: float
    ep: bool
    quelle_frage: str   # "F06", "paket", "puffer", "grundpaket", "trigger", ...
    kein_ep: bool = False   # v8: "(kein EP)" – überschreibt das EP-Flag des Stamms


# --- Artikel aus den Antworten ermitteln ----------------------------------

def _menge_aufloesen(menge_roh: str, antwort) -> float:
    """Mengen-Ausdruck einer Aktionszeile: Zahl direkt ('1', '2'), Formel
    '(Eingabe − 3)' (Erdleitung: nie unter 0) oder der eingegebene Zahlenwert."""
    zahl = engine.zahl_parsen(menge_roh)
    if zahl is not None:
        return zahl
    antwortzahl = antwort if isinstance(antwort, (int, float)) else engine.zahl_parsen(antwort)
    if antwortzahl is None:
        return 1.0
    m = re.search(r"Eingabe\s*[−–-]\s*([\d.,]+)", menge_roh)
    if m:
        return max(0.0, float(antwortzahl) - engine.zahl_parsen(m.group(1)))
    return float(antwortzahl)


def artikel_ermitteln(logik: Logik, antworten: dict) -> list[GewaehlterArtikel]:
    gewaehlt: list[GewaehlterArtikel] = []

    for frage in engine.sichtbare_fragen(logik, antworten):
        if frage.id not in antworten:
            continue
        wert = antworten[frage.id]

        if frage.typ == "Mengenmaske":
            # H04: eine Zeile "Anzahl S / M / L / XL" mit paarweisen Artikeln;
            # D05 (v3): eine Zeile je Feld ("Heizung VL/RL (m)" -> Pos. 139 × Eingabe)
            zeilen = [a for a in logik.aktionen if a.frage == frage.id]
            gesamt = 0.0
            for option, anzahl in wert.items():
                if not anzahl:
                    continue
                gesamt += float(anzahl)
                ref = _mengenmaske_ref(zeilen, option)
                if ref is not None:
                    gewaehlt.append(GewaehlterArtikel(ref.ref, float(anzahl),
                                                     False, frage.id))
            if gesamt:
                # Pauschalen aus der Bemerkung ("zusätzlich Pos. 129 × Gesamtanzahl")
                gesehen_pauschale: set[str] = set()
                for zeile in zeilen:
                    for ref in logik_refs_extrahieren(zeile.bemerkung):
                        if ("Gesamtanzahl" in ref.menge
                                and ref.ref not in gesehen_pauschale):
                            gesehen_pauschale.add(ref.ref)
                            gewaehlt.append(GewaehlterArtikel(
                                ref.ref, float(gesamt), False, frage.id))
            continue

        if frage.typ == "Wiederholfeld":
            # H07: je Verteiler die passende Größenstufe; gleiche Artikel zusammenfassen
            zaehler: dict[str, float] = {}
            for gruppenzahl in wert:
                treffer = engine.aktion_finden(logik, frage, gruppenzahl, antworten)
                if treffer and treffer[0].typ == "normal":
                    for ref in engine.refs_fuer_treffer(*treffer):
                        zaehler[ref.ref] = zaehler.get(ref.ref, 0) + 1
            for ref_nr, anzahl in zaehler.items():
                gewaehlt.append(GewaehlterArtikel(ref_nr, anzahl, False, frage.id))
            continue

        if isinstance(wert, (dict, list)) or frage.typ in ("Freitext", "Freitext groß"):
            continue

        treffer = engine.aktion_finden(logik, frage, wert, antworten)
        if treffer is None or treffer[0].typ != "normal":
            continue
        for ref in engine.refs_fuer_treffer(*treffer):
            menge = _menge_aufloesen(ref.menge, wert)
            if menge <= 0:
                continue  # z. B. Erdleitung: (Eingabe − 3) = 0 -> keine Position
            gewaehlt.append(GewaehlterArtikel(ref.ref, menge, ref.ep, frage.id,
                                              ref.kein_ep))

    # Paket laut Paketmatrix (A03 + N02/N03)
    for ref in (engine.paket_aufloesen(logik, antworten) or []):
        gewaehlt.append(GewaehlterArtikel(ref.ref, 1.0, ref.ep, "paket"))

    # Grundpaket und Gruppen-Trigger aus den Spezial-Aktionszeilen
    friondo_ja = any(antworten.get(f) == "Ja" for f in engine.FRIONDO_FRAGEN)
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
        return any(antworten.get(f) == "Ja" for f in engine.FRIONDO_FRAGEN)
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
        # v2: Positionsnummern stehen auch ohne "Pos."-Präfix im Inhalt
        # ("Pos. 005 · 006 · 007 (EP)") – nacktes Token genügt
        m = re.search(rf"\b{re.escape(ref)}\b", inhalt)
        if m is None and ref.lstrip("0") != ref:
            m = re.search(rf"\b{re.escape(ref.lstrip('0'))}\b", inhalt)
        if m:
            return m.start()
    if re.fullmatch(r"[A-Z]{1,2}\d{2}", artikel.quelle_frage):
        m = re.search(rf"\b{artikel.quelle_frage}\b", inhalt)
        if m:
            return m.start()
    if artikel.quelle_frage == "paket" and "Paketmatrix" in inhalt:
        return inhalt.find("Paketmatrix")
    return -1


def _block_ueberschrift(block, antworten: dict, erste_kategorie: str,
                        logik: Logik | None = None) -> str:
    u = block.ueberschrift
    if u.startswith("(ohne"):
        return ""
    if "aus der Preisliste" in u:
        return erste_kategorie
    if u.startswith("DYNAMISCH"):
        zitate = re.findall(r"'([^']+)'", u)
        basis = zitate[0] if zitate else ""
        # v9: Serie CS8800i bei Leistungsklasse 15 kW
        if logik is not None:
            zeile = engine.leistungsklasse(logik, antworten)
            if zeile is not None and zeile.leistungsklasse == "15 kW":
                basis = basis.replace("CS3800i", "CS8800i")
                zitate = [z.replace("CS3800i", "CS8800i") for z in zitate]
        if antworten.get(engine.ID_WARMWASSER) == "Ja" and len(zitate) > 1 and zitate[1].startswith("…"):
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
            # v8: "(kein EP)" in der Aktionszeile erzwingt eine normale Position
            "ep_flag": (stamm.ep_flag or gw.ep) and not gw.kein_ep,
            "ek_cent": stamm.ek_cent,   # EK-Snapshot für den Deckungsbeitrag
            "guid": stamm.guid,         # interne Referenz (Phase 18)
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
        ueberschrift = _block_ueberschrift(block, antworten, kategorie, logik)
        for p in positionen:
            if p["block_nr"] == block_nr:
                p["gruppe"] = ueberschrift

    for sort, p in enumerate(positionen, 1):
        p["sort"] = sort
    return positionen


# --- Nummernkreis ---------------------------------------------------------

def naechste_angebotsnummer(session: Session) -> str:
    """Fortlaufend je Jahr; berücksichtigt seit v6 auch das Lösch-Protokoll,
    damit die Nummer eines gelöschten Angebots nie wiederverwendet wird."""
    from app.models import AngebotsLoeschung
    jj = datetime.now().year % 100
    praefix = f"{config.NUMMERNKREIS_PREFIX}{jj}"
    kandidaten = [n for (n,) in
                  session.query(Angebot.nummer)
                  .filter(Angebot.nummer.like(f"{praefix}%"))]
    kandidaten += [n for (n,) in
                   session.query(AngebotsLoeschung.nummer)
                   .filter(AngebotsLoeschung.nummer.like(f"{praefix}%"))]
    zaehler = config.NUMMERNKREIS_START_ZAEHLER
    for nummer in kandidaten:
        rest = nummer[len(praefix):]
        if rest.isdigit():
            zaehler = max(zaehler, int(rest) + 1)
    return f"{praefix}{zaehler}"


def angebot_anlegen(session: Session, kunde_id: int,
                    antworten: dict | None = None,
                    logik: Logik | None = None,
                    konfiguration_id: int | None = None,
                    nur_protokoll: bool = False) -> Angebot:
    """Legt ein Angebot mit transaktionssicherer Nummer an (Retry bei Kollision).
    Mit Antworten + Logik werden Positionen, Protokoll und KfW-Daten erzeugt;
    nur_protokoll=True übernimmt Protokoll/KfW ohne Positionen (manuelles Angebot
    zu einer orangen Erfassung)."""
    protokoll_json = "[]"
    kfw_json = "{}"
    positionen: list[dict] = []
    vermerke_json = "[]"
    if antworten is not None and logik is not None:
        protokoll_json = json.dumps(engine.protokoll(logik, antworten), ensure_ascii=False)
        kfw_json = json.dumps(engine.kfw_daten(antworten), ensure_ascii=False)
        # v9: bedingte Angebotsvermerke (Blatt "Vermerke") am Angebot ablegen
        vermerke_json = json.dumps(engine.vermerke_fuer(logik, antworten),
                                   ensure_ascii=False)
        if not nur_protokoll:
            positionen = positionen_zusammenstellen(logik, antworten, session)
    # v8: Einschätzung (S01/S02) als Startwerte der Verfolgung; abweichende
    # Rechnungsanschrift aus O06/O09–O12 (monday-Adresse = Ausführungsort)
    verfolgung_ampel = {"heiß": "heiss", "warm": "warm", "kalt": "kalt"}.get(
        str((antworten or {}).get("S01") or ""), "")
    wiedervorlage = None
    if (antworten or {}).get("S02"):
        try:
            wiedervorlage = datetime.strptime(str(antworten["S02"]), "%Y-%m-%d")
        except ValueError:
            pass
    rechnung = {}
    if (antworten or {}).get("O06") == "Nein":
        rechnung = {"rechnung_name": str(antworten.get("O09") or "")[:200],
                    "rechnung_strasse": str(antworten.get("O10") or "")[:200],
                    "rechnung_plz": str(antworten.get("O11") or "")[:10],
                    "rechnung_ort": str(antworten.get("O12") or "")[:100]}

    for _versuch in range(5):
        angebot = Angebot(
            nummer=naechste_angebotsnummer(session),
            kunde_id=kunde_id,
            konfiguration_id=konfiguration_id,
            protokoll_json=protokoll_json,
            kfw_json=kfw_json,
            vermerke_json=vermerke_json,
            verfolgung_ampel=verfolgung_ampel,
            wiedervorlage_am=wiedervorlage,
            **rechnung,
        )
        for p in positionen:
            angebot.positionen.append(AngebotsPosition(**p))
        # v9: Angebotsprofil über den Kanal des Kunden + Positionsregeln
        from app import angebotsprofile
        profil = angebotsprofile.profil_fuer_kanal(
            session, getattr(session.get(Kunde, kunde_id), "vertriebskanal", ""))
        if profil is not None:
            angebot.profil_id = profil.id
            angebotsprofile.positionsregeln_anwenden(session, angebot, profil)
        session.add(angebot)
        try:
            session.commit()
            return angebot
        except IntegrityError:
            session.rollback()
    raise RuntimeError("Angebotsnummer konnte nicht vergeben werden (Nummernkreis-Kollision).")
