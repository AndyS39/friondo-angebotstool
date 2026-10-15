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
from app.models import Angebot, AngebotsPosition, Artikel, Konfiguration, Kunde, VorgangObjekt


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

    # v34 (PLAN_V21 Phase 180): keine 0,00-€-Auslegungszeile „Auslegung der Wärmepumpe“
    # mehr am Ende von Block 1 (v11–v33) – der Text (engine.auslegungs_text) wandert
    # beim Anlegen in angebote.auslegung_text (Editor „Auslegung (intern)“, nur
    # Innendienst/Admin) und bleibt im Konfigurationsprotokoll; Bestand: migration_v34_auslegung.

    # v11: tatsächliche Tankgröße (A19, ab 9.000 L) als Zusatz im Text der
    # Öltank-Entsorgung – greift, falls doch eine Entsorgungsposition vorliegt
    tank = engine.zahl_parsen(antworten.get(engine.ID_TANKGROESSE))
    if tank:
        tank_text = f"{int(tank):,}".replace(",", ".")
        for p in positionen:
            if p["pos_nr"] in [f"Z{n:02d}" for n in range(1, 15)] or p["pos_nr"] == "107":
                p["beschreibung"] = (p["beschreibung"].rstrip()
                                     + f"\nTatsächliche Tankgröße: {tank_text} Liter")

    for sort, p in enumerate(positionen, 1):
        p["sort"] = sort
    return positionen


# --- v34 (PLAN_V21 Phase 180): Auslegungstext statt 0,00-€-Auslegungs-Position -------------

# Bezeichnungen der bisherigen Auslegungs-Positionen (WP v11, PV v16, KL v24) – Kennung für
# Bestand (Migration), Versionen/Duplikate/Kopien (Zeile wird beim Kopieren weggelassen)
AUSLEGUNGS_BEZEICHNUNGEN = ("Auslegung der Wärmepumpe", "Auslegung der Klimaanlage",
                            "Auslegung der PV-Anlage")


def ist_auslegungs_position(position) -> bool:
    """Reine 0,00-€-Textzeile „Auslegung …“ ohne Artikelnummer (Snapshot-dict oder
    AngebotsPosition): Bezeichnung aus AUSLEGUNGS_BEZEICHNUNGEN oder PV-Beschreibung
    „Auslegung: …“ (v16)."""
    if isinstance(position, dict):
        pos_nr, preis = position.get("pos_nr") or "", position.get("e_preis_cent") or 0
        bezeichnung = (position.get("bezeichnung") or "").strip()
        beschreibung = (position.get("beschreibung") or "").lstrip()
    else:
        pos_nr, preis = position.pos_nr or "", position.e_preis_cent or 0
        bezeichnung = (position.bezeichnung or "").strip()
        beschreibung = (position.beschreibung or "").lstrip()
    if pos_nr.strip() or preis:
        return False
    return bezeichnung in AUSLEGUNGS_BEZEICHNUNGEN or beschreibung.startswith("Auslegung: ")


def auslegungs_text_fuer(logik: Logik | None, antworten: dict | None, sparte: str,
                         session: Session | None = None) -> str:
    """Auslegungstext je Sparte für angebote.auslegung_text (Editor „Auslegung (intern)“):
    WP über konfigurator.auslegungs_text, PV über pv_auslegung.auslegungs_text, KL über
    kl_auslegung.auslegungs_text (Gerätenamen aus dem Artikelstamm, falls Session vorhanden);
    WB über wb_auslegung.auslegungs_text/auslegen, sofern das Modul (Agent W) sie bietet.
    Leer, wenn keine Auslegung ermittelbar ist."""
    if logik is None or antworten is None:
        return ""
    sparte = (sparte or "WP").upper()
    try:
        if sparte == "PV":
            if not getattr(logik, "pv_aktionen", None):
                return ""
            from app import pv_auslegung
            return pv_auslegung.auslegungs_text(pv_auslegung.auslegen(logik, antworten)) or ""
        if sparte == "KL":
            if not getattr(logik, "kl_aktionen", None):
                return ""
            from app import kl_auslegung
            namen = kl_auslegung.artikel_namen(session) if session is not None else None
            return kl_auslegung.auslegungs_text(
                kl_auslegung.auslegen(logik, antworten, namen)) or ""
        if sparte == "WB":
            try:
                from app import wb_auslegung   # v34 Phase 179 (Agent W) – optional
            except ImportError:
                return ""
            auslegen = getattr(wb_auslegung, "auslegen", None)
            text_fn = getattr(wb_auslegung, "auslegungs_text", None)
            if auslegen is None or text_fn is None:
                return ""
            return text_fn(auslegen(logik, antworten)) or ""
        if sparte == "WP":
            return engine.auslegungs_text(logik, antworten) or ""
    except Exception:   # Auslegungstext ist Zusatzinfo – nie ein Grund, das Angebot nicht anzulegen
        return ""
    return ""


def migration_v34_auslegung(session: Session) -> list[str]:
    """Bestand (Entscheidung R5): entfernt die 0,00-€-Auslegungs-Position aus allen Angeboten
    im Status Entwurf (WP „Auslegung der Wärmepumpe“, KL „Auslegung der Klimaanlage“, PV
    „Auslegung der PV-Anlage“ / Beschreibung „Auslegung: …“), übernimmt den Text in
    angebote.auslegung_text (falls leer) und nummeriert die Positionen wie der Editor-Knopf
    „Neu durchnummerieren“ (sort fortlaufend, eigene Nummern verworfen). Versendete/
    angenommene/überholte Angebote bleiben unverändert. Idempotent: zweiter Lauf meldet nichts."""
    meldungen: list[str] = []
    kandidaten = (session.query(AngebotsPosition)
                  .join(Angebot, Angebot.id == AngebotsPosition.angebot_id)
                  .filter(Angebot.status == "Entwurf",
                          AngebotsPosition.e_preis_cent == 0,
                          AngebotsPosition.bezeichnung.in_(AUSLEGUNGS_BEZEICHNUNGEN)
                          | AngebotsPosition.beschreibung.like("Auslegung: %"))
                  .order_by(AngebotsPosition.angebot_id, AngebotsPosition.sort).all())
    je_angebot: dict[int, list[AngebotsPosition]] = {}
    for p in kandidaten:
        if ist_auslegungs_position(p):
            je_angebot.setdefault(p.angebot_id, []).append(p)
    for angebot_id, zeilen in je_angebot.items():
        angebot = session.get(Angebot, angebot_id)
        if angebot is None:
            continue
        texte = [(z.beschreibung or "").strip() for z in zeilen if (z.beschreibung or "").strip()]
        if not (angebot.auslegung_text or "").strip() and texte:
            angebot.auslegung_text = "\n".join(texte)
        for z in zeilen:
            session.delete(z)
        session.flush()
        rest = (session.query(AngebotsPosition)
                .filter(AngebotsPosition.angebot_id == angebot_id)
                .order_by(AngebotsPosition.sort, AngebotsPosition.id).all())
        for sort, p in enumerate(rest, 1):
            p.sort = sort
            p.anzeige_nr = ""
        meldungen.append(f"{angebot.nummer}: {len(zeilen)} Auslegungs-Position(en) entfernt, "
                         f"Text nach „Auslegung (intern)“, {len(rest)} Positionen neu nummeriert (v34)")
    if meldungen:
        meldungen.append(f"{len(je_angebot)} Entwürfe ohne 0,00-€-Auslegungszeile (v34)")
    return meldungen


def version_erzeugen(session: Session, original: Angebot) -> Angebot:
    """v9/v10: erzeugt die nächste Version (<Stamm>.2/.3 …) eines versendeten/
    angenommenen Angebots als Entwurf; das Original wird „Überholt“ und die
    Erfassungs-Verknüpfung wandert zur neuen Version. Wird vom Überarbeiten-
    Button und vom AD-Rabatt-Workflow (Phase 59) genutzt."""
    from sqlalchemy import or_

    from app.models import AngebotsPosition, Erfassung
    stamm = original.stamm_nummer
    hoechste = 1
    for (nummer,) in (session.query(Angebot.nummer)
                      .filter(or_(Angebot.nummer == stamm,
                                  Angebot.nummer.like(f"{stamm}.%")))):
        _, punkt, rest = nummer.rpartition(".")
        if punkt and rest.isdigit():
            hoechste = max(hoechste, int(rest))
    version = Angebot(
        nummer=f"{stamm}.{hoechste + 1}", kunde_id=original.kunde_id,
        protokoll_json=original.protokoll_json, kfw_json=original.kfw_json,
        vermerke_json=original.vermerke_json,
        rabatt_cent=original.rabatt_cent, rabatt_prozent=original.rabatt_prozent,
        rabatt_bezeichnung=original.rabatt_bezeichnung,
        konfigurator_typ=original.konfigurator_typ,
        ust_satz=original.ust_satz, pv_json=original.pv_json,
        kl_json=original.kl_json,   # v24
        wb_json=original.wb_json,   # v34 (PLAN_V21 Phase 179)
        auslegung_text=original.auslegung_text,   # v34 (PLAN_V21 Phase 180)
        vertriebler_id=original.vertriebler_id,
        profil_id=original.profil_id, vortext_text=original.vortext_text,
        rechnung_name=original.rechnung_name,
        rechnung_strasse=original.rechnung_strasse,
        rechnung_plz=original.rechnung_plz, rechnung_ort=original.rechnung_ort,
        # v20 (Phase 98): Zusatz + strukturierte Lieferanschrift
        rechnung_zusatz=original.rechnung_zusatz,
        liefer_anschrift=original.liefer_anschrift,
        liefer_name=original.liefer_name, liefer_zusatz=original.liefer_zusatz,
        liefer_strasse=original.liefer_strasse, liefer_plz=original.liefer_plz,
        liefer_ort=original.liefer_ort,
        foerderung_manuell_cent=original.foerderung_manuell_cent,
        foerderung_ausblenden=original.foerderung_ausblenden,
        wirtschaftlichkeit_ausblenden=original.wirtschaftlichkeit_ausblenden,   # v22
        foerder_grund_prozent=original.foerder_grund_prozent,
        foerder_klima_prozent=original.foerder_klima_prozent,
        foerder_einkommen_prozent=original.foerder_einkommen_prozent,
        foerder_hoechstkosten_cent=original.foerder_hoechstkosten_cent,
        verfolgung_ampel=original.verfolgung_ampel,
        wiedervorlage_am=original.wiedervorlage_am,
        graph_conversation_id=original.graph_conversation_id,
        vorgaenger_id=original.id,
        vorgang_id=original.vorgang_id,
        # v30 (PLAN_V18 Phase 150): Zahlungsbedingung wandert in die neue Version
        # (deckt auch den AD-Rabatt-Pfad in routers/meine_angebote.py ab)
        zahlungsbedingung_key=original.zahlungsbedingung_key or "",
        zahlungsbedingung_text=original.zahlungsbedingung_text or "",
        # v31 (PLAN_LEAD_V5 Phase 153): Objekt des Vorgangs wandert mit
        objekt_id=original.objekt_id,
    )
    for p in original.positionen:
        # v34 (PLAN_V21 Phase 180): die 0,00-€-Auslegungszeile eines versendeten
        # Angebots entfällt in der neuen Version – ihr Text wandert ins Feld
        if ist_auslegungs_position(p):
            if not (version.auslegung_text or "").strip():
                version.auslegung_text = (p.beschreibung or "").strip()
            continue
        version.positionen.append(AngebotsPosition(
            sort=p.sort, block_nr=p.block_nr, gruppe=p.gruppe, pos_nr=p.pos_nr,
            bezeichnung=p.bezeichnung, beschreibung=p.beschreibung, menge=p.menge,
            einheit=p.einheit, e_preis_cent=p.e_preis_cent, ep_flag=p.ep_flag,
            ek_cent=p.ek_cent, guid=p.guid, anzeige_nr=p.anzeige_nr,
            original_preis_cent=p.original_preis_cent,
            rabatt_prozent=p.rabatt_prozent, rabatt_cent=p.rabatt_cent,
            bauseits=p.bauseits, sonderpreis=p.sonderpreis,
            # Bugfix 30.09.2026: fehlte seit v10 – die Version berechnete
            # Alternativ-Positionen voll (Endbetrag stieg)
            alternativ=p.alternativ, alternativ_zu=p.alternativ_zu))
    session.add(version)
    session.flush()
    original.status = "Überholt"
    for erfassung in session.query(Erfassung).filter(
            Erfassung.angebot_id == original.id):
        erfassung.angebot_id = version.id
    return version


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
                    nur_protokoll: bool = False,
                    sparte: str = "WP",
                    erfassung=None,
                    commit: bool = True) -> Angebot:
    """Legt ein Angebot mit transaktionssicherer Nummer an (Retry bei Kollision).
    Mit Antworten + Logik werden Positionen, Protokoll und KfW-Daten erzeugt;
    nur_protokoll=True übernimmt Protokoll/KfW ohne Positionen (manuelles Angebot
    zu einer orangen Erfassung). v13-PV: sparte steuert Steuersatz (PV 0 %)
    und bei PV die Positionslogik aus den PV-Blättern (app.pv_auslegung).
    v33 (PLAN_V20 Phase 172, v30-Nachtrag 22): ``commit=False`` legt das Angebot
    innerhalb der Transaktion des Aufrufers an (duplizieren/ueberarbeiten/kopieren
    über routers/angebote._speichern – Rollback und Wiederholung bei „database is
    locked“ gelten dann für den ganzen Vorgang, es bleibt kein halb angelegtes
    Angebot zurück); eine Nummernkollision wird dabei über einen SAVEPOINT
    abgefangen, der Rest der Transaktion bleibt bestehen. ``commit=True`` (Standard,
    z. B. GET-Routen „Neues Angebot“/„aus Konfiguration“, Erfassungsliste, Tests)
    committet wie bisher selbst."""
    from app.models import ust_standard
    sparte = (sparte or "WP").upper()
    protokoll_json = "[]"
    kfw_json = "{}"
    positionen: list[dict] = []
    vermerke_json = "[]"
    pv_json = ""
    kl_json = ""
    wb_json = ""          # v34 (PLAN_V21 Phase 179)
    auslegung_text = ""   # v34 (PLAN_V21 Phase 180)
    # v24 (PLAN_V16 Phase 114): Klimakonfigurator – nur mit KL-Aktionen
    # (sonst bleibt KL reiner Bogen / manuelles Angebot)
    kl_konfigurator = sparte == "KL" and bool(getattr(logik, "kl_aktionen", None))
    # v34 (PLAN_V21 Phase 179): Wallbox-Konfigurator – nur mit WB-Aktionen (WB-Sicht aus
    # logik_fuer_sparte; ohne importierte WB-Artikel bleibt WB reiner Bogen)
    wb_konfigurator = sparte == "WB" and bool(getattr(logik, "wb_aktionen", None))
    if antworten is not None and logik is not None:
        protokoll_json = json.dumps(engine.protokoll(logik, antworten), ensure_ascii=False)
        # v13-PV / v24-KL / v34-WB: kein KfW-/Förderblock (keine KfW-Daten am Angebot)
        kfw_json = ("{}" if sparte in ("PV", "KL", "WB")
                    else json.dumps(engine.kfw_daten(antworten), ensure_ascii=False))
        # v9: bedingte Angebotsvermerke (Blatt "Vermerke") am Angebot ablegen
        vermerke_json = json.dumps(engine.vermerke_fuer(logik, antworten),
                                   ensure_ascii=False)
        if not nur_protokoll:
            if sparte == "PV":
                from app import pv_auslegung
                positionen = pv_auslegung.positionen_zusammenstellen(
                    logik, antworten, session, erfassung=erfassung)
            elif kl_konfigurator:
                from app import kl_auslegung
                positionen = kl_auslegung.positionen_zusammenstellen(
                    logik, antworten, session, erfassung=erfassung)
            elif wb_konfigurator:
                from app import wb_auslegung
                positionen = wb_auslegung.positionen_zusammenstellen(
                    logik, antworten, session, erfassung=erfassung)
            else:
                positionen = positionen_zusammenstellen(logik, antworten, session)
        if sparte == "PV" and getattr(logik, "pv_aktionen", None):
            from app import pv_auslegung
            pv_json = json.dumps(pv_auslegung.auslegen(logik, antworten).als_dict(),
                                 ensure_ascii=False)
        if kl_konfigurator:
            from app import kl_auslegung
            kl_json = json.dumps(
                kl_auslegung.auslegen(logik, antworten,
                                      kl_auslegung.artikel_namen(session)).als_dict(),
                ensure_ascii=False)
        if wb_konfigurator:
            from app import wb_auslegung
            wb_json = json.dumps(wb_auslegung.auslegen(logik, antworten).als_dict(),
                                 ensure_ascii=False)
        # v34 (PLAN_V21 Phase 180): Auslegungstext statt 0,00-€-Position (Editor „Auslegung
        # (intern)“, nur Innendienst/Admin; Versionen/Duplikate/Kopien übernehmen das Feld)
        auslegung_text = auslegungs_text_fuer(logik, antworten, sparte, session)
    # v10 (Phase 60): Die Verfolgung lebt auf VORGANGSEBENE – die Felder am
    # Angebot sind stillgelegt (Bestand bleibt lesbar). Die Einschätzung
    # (S01/S02) schreibt ihre Startwerte beim Absenden der Erfassung auf den
    # Vorgang (app/routers/erfassung.py). Abweichende Rechnungsanschrift aus
    # O06/O09–O12 (monday-Adresse = Ausführungsort).
    verfolgung_ampel = ""
    wiedervorlage = None
    rechnung = {}
    if (antworten or {}).get("O06") == "Nein":
        rechnung = {"rechnung_name": str(antworten.get("O09") or "")[:200],
                    "rechnung_strasse": str(antworten.get("O10") or "")[:200],
                    "rechnung_plz": str(antworten.get("O11") or "")[:10],
                    "rechnung_ort": str(antworten.get("O12") or "")[:100]}
    # v11 (Phase 66): abweichende Lieferanschrift aus der Erfassung (O13)
    if (antworten or {}).get("O13"):
        rechnung["liefer_anschrift"] = str(antworten.get("O13") or "")[:300]
        # v20 (Phase 98): zusätzlich strukturiert (Editor-Karte „Lieferanschrift“)
        from app import anschriften as _anschriften
        for feld, wert in _anschriften.alt_text_parsen(rechnung["liefer_anschrift"]).items():
            rechnung[f"liefer_{feld}"] = wert

    # v31 (PLAN_LEAD_V5 Phase 153): das Angebot erhält das Objekt der Erfassung
    # (Ausführungsort über objekte.ausfuehrungsort; leer = Hauptobjekt/Kundenadresse);
    # die Rechnungsadresse eines MFH-Objekts (nicht Hauptobjekt) geht dem Kunden-Standard vor
    objekt_id = getattr(erfassung, "objekt_id", None) if erfassung is not None else None
    objekt = session.get(VorgangObjekt, objekt_id) if objekt_id else None
    for _versuch in range(5):
        angebot = Angebot(
            nummer=naechste_angebotsnummer(session),
            kunde_id=kunde_id,
            konfiguration_id=konfiguration_id,
            protokoll_json=protokoll_json,
            kfw_json=kfw_json,
            vermerke_json=vermerke_json,
            konfigurator_typ=sparte,
            ust_satz=ust_standard(sparte),      # KL: 19 % (models.ust_standard)
            pv_json=pv_json,
            kl_json=kl_json,                    # v24
            wb_json=wb_json,                    # v34 (PLAN_V21 Phase 179)
            auslegung_text=auslegung_text,      # v34 (PLAN_V21 Phase 180)
            verfolgung_ampel=verfolgung_ampel,
            wiedervorlage_am=wiedervorlage,
            objekt_id=objekt_id,                # v31
            **rechnung,
        )
        # v20 (Phase 98): ohne Erfassungs-Anschriften → Kunden-Standards
        from app import anschriften as _anschriften_v20
        _anschriften_v20.angebot_vorbelegen(angebot, session.get(Kunde, kunde_id),
                                            antworten, objekt=objekt)
        for p in positionen:
            angebot.positionen.append(AngebotsPosition(**p))
        # v9: Angebotsprofil über den Kanal des Kunden + Positionsregeln
        from app import angebotsprofile
        profil = angebotsprofile.profil_fuer_kanal(
            session, getattr(session.get(Kunde, kunde_id), "vertriebskanal", ""))
        if profil is not None:
            angebot.profil_id = profil.id
            angebotsprofile.positionsregeln_anwenden(session, angebot, profil)
        if not commit:
            # v33 (Phase 172): in der Transaktion des Aufrufers. Läuft schon eine
            # Transaktion (Schreibsitzung mit BEGIN IMMEDIATE – der Regelfall über
            # _speichern), schützt ein SAVEPOINT nur das Anlegen: bei einer Nummern-
            # kollision rollt SQLAlchemy den Savepoint zurück (das Angebot ist wieder aus
            # der Sitzung ausgetragen), die nächste Nummer wird versucht, die äußere
            # Transaktion (z. B. neuer Kunde beim Kopieren) bleibt bestehen. Ohne offene
            # Transaktion (Legacy-Modus des Treibers, erst das INSERT eröffnet sie) gäbe
            # es nichts zu schützen – dann reicht flush + rollback wie beim Commit-Pfad.
            treiber = session.connection().connection.dbapi_connection
            if getattr(treiber, "in_transaction", False):
                try:
                    with session.begin_nested():
                        session.add(angebot)
                        session.flush()
                    return angebot
                except IntegrityError:
                    continue
            session.add(angebot)
            try:
                session.flush()
                return angebot
            except IntegrityError:
                session.rollback()
                continue
        session.add(angebot)
        try:
            session.commit()
            return angebot
        except IntegrityError:
            session.rollback()
    raise RuntimeError("Angebotsnummer konnte nicht vergeben werden (Nummernkreis-Kollision).")
