# monday-Lesesync (Phase 22): liest Leads mit Vor-Ort-Termin aus den in der
# Parametrierung gepflegten Quellen (Board + Gruppentitel „Terminiert“).
# Nur lesend; Fehler werden gesammelt angezeigt und blockieren das Tool nie.
# Läuft alle 15 Minuten im Hintergrund plus Button „Jetzt aktualisieren“.

import json
import re
import threading
import urllib.request
from datetime import datetime

from sqlalchemy.orm import Session

from app import config
from app.db import SessionLocal
from app.models import (Benutzer, Lead, MondayMapping, MondayPerson,
                        MondayQuelle, MONDAY_FELDER)

API_URL = "https://api.monday.com/v2"
SYNC_INTERVALL_SEKUNDEN = 15 * 60

# Vorbelegte, verifizierte Quellen lt. CLAUDE.md v3
STANDARD_QUELLEN = [
    ("5080725439", "Deals (Blinno Working Space)", "Terminiert", None),
    ("5089971526", "Deals - Simon (Pool Working Space)", "Terminiert", None),
    ("5092657267", "Deals - Rene (Pool Working Space)", "Terminiert",
     "Rene Golaschewski"),   # Sonderregel: Verantwortlicher immer dieser Benutzer
]

status = {"letzter_sync": None, "fehler": [], "laeuft": False, "anzahl": 0}


def _api(query: str, variablen: dict | None = None) -> dict:
    token = config.MONDAY_API_TOKEN
    if not token:
        raise RuntimeError("Kein monday-API-Token in der .env (MONDAY_API_TOKEN).")
    anfrage = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": query, "variables": variablen or {}}).encode(),
        headers={"Authorization": token, "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(anfrage, timeout=30) as antwort:
        daten = json.loads(antwort.read())
    if "errors" in daten:
        raise RuntimeError(str(daten["errors"])[:300])
    return daten["data"]


def quellen_vorbelegen(session: Session) -> None:
    """Legt die drei verifizierten Standard-Quellen an (einmalig)."""
    if session.query(MondayQuelle).count():
        return
    for board_id, name, gruppe, fester_name in STANDARD_QUELLEN:
        fester_id = None
        if fester_name:
            benutzer = (session.query(Benutzer)
                        .filter(Benutzer.name == fester_name).first())
            fester_id = benutzer.id if benutzer else None
        session.add(MondayQuelle(board_id=board_id, board_name=name,
                                 gruppen_titel=gruppe,
                                 fester_benutzer_id=fester_id))
    session.commit()


def spalten_laden(board_id: str) -> list[dict]:
    """Spalten eines Boards live von monday (für die Mapping-Dropdowns)."""
    daten = _api("query($id: [ID!]) { boards(ids: $id) { columns { id title type } } }",
                 {"id": [board_id]})
    boards = daten.get("boards") or []
    return boards[0]["columns"] if boards else []


def gruppen_laden(board_id: str) -> list[dict]:
    """Gruppen eines Boards (für die Zielgruppe der Rückspielung, Phase 32)."""
    daten = _api("query($id: [ID!]) { boards(ids: $id) { groups { id title } } }",
                 {"id": [board_id]})
    boards = daten.get("boards") or []
    return boards[0]["groups"] if boards else []


def _mapping(session: Session, board_id: str) -> dict[str, str]:
    return {m.feld: m.spalten_id
            for m in session.query(MondayMapping).filter(MondayMapping.board_id == board_id)
            if m.spalten_id}


def _datum_parsen(text: str):
    text = (text or "").strip()
    for muster in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:16] if " " in text else text[:10], muster)
        except ValueError:
            continue
    return None


def _items_der_gruppe(board_id: str, gruppen_titel: str) -> tuple[str, list[dict]]:
    """Alle Items der Gruppe (über den Titel aufgelöst); liefert (Boardname, Items)."""
    daten = _api("query($id: [ID!]) { boards(ids: $id) { name groups { id title } } }",
                 {"id": [board_id]})
    boards = daten.get("boards") or []
    if not boards:
        raise RuntimeError(f"Board {board_id} nicht gefunden.")
    board_name = boards[0]["name"]
    gruppe = next((g for g in boards[0]["groups"]
                   if g["title"].strip().lower() == gruppen_titel.strip().lower()), None)
    if gruppe is None:
        raise RuntimeError(f"Board {board_name}: Gruppe „{gruppen_titel}“ nicht gefunden.")

    items: list[dict] = []
    cursor = None
    for _ in range(20):  # max. 2.000 Items
        daten = _api(
            "query($id: [ID!], $gid: [String!], $cursor: String) {"
            " boards(ids: $id) { groups(ids: $gid) {"
            "  items_page(limit: 100, cursor: $cursor) {"
            "   cursor items { id name column_values { id text } } } } } }",
            {"id": [board_id], "gid": [gruppe["id"]], "cursor": cursor})
        seite = daten["boards"][0]["groups"][0]["items_page"]
        items.extend(seite["items"])
        cursor = seite.get("cursor")
        if not cursor:
            break
    return board_name, items


def _benutzer_fuer_person(session: Session, name: str):
    """Personen-Spalte -> Tool-Benutzer. Bei Mehrfach-Zuweisung
    ("Kyriakos Sarigiannis, Niko Goritsas") zählt die erste Person."""
    name = (name or "").split(",")[0].strip()
    if not name:
        return None
    zuordnung = (session.query(MondayPerson)
                 .filter(MondayPerson.monday_name == name).first())
    if zuordnung and zuordnung.benutzer_id:
        return zuordnung.benutzer_id
    if zuordnung is None:
        zuordnung = MondayPerson(monday_name=name)   # zur Zuordnung anbieten
        session.add(zuordnung)
        session.flush()   # sofort sichtbar machen (Session läuft ohne Autoflush)
    benutzer = session.query(Benutzer).filter(Benutzer.name == name).first()
    if benutzer is not None:
        zuordnung.benutzer_id = benutzer.id   # Namensgleichheit -> automatisch verknüpfen
        return benutzer.id
    return None


def _plz_ort_trennen(plz: str, ort: str) -> tuple[str, str]:
    """monday pflegt die PLZ oft im Ort-Feld ("47169 Duisburg", "46149- Oberhausen");
    ohne eigene PLZ-Spalte wird sie hier herausgelöst."""
    plz, ort = plz.strip(), ort.strip()
    if not plz:
        m = re.match(r"^(\d{5})\s*-?\s*(.*)$", ort)
        if m:
            return m.group(1), m.group(2).strip()
    return plz, ort


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


# monday-Interessen-Labels -> Tool-Codes (Phase 33); Vergleich ohne Groß/Klein.
# Nicht aufgeführte Labels (HEMS, FBH, Gewerbe, ...) werden ignoriert.
_INTERESSE_LABELS = {
    "WP": ("wp", "wärmepumpe", "waermepumpe", "wp mfh", "wärmepumpe mfh", "heizung"),
    "PV": ("pv", "photovoltaik", "pv mieterstrom", "solar", "speicher", "speichererweiterung"),
    "KL": ("kl", "klima", "klimaanlage", "klimaanlagen"),
    "WB": ("wb", "wallbox", "ladestation"),
}


def interesse_aus_text(text: str) -> str:
    """"Klimaanlage, WP, HEMS" -> "WP,KL" (kanonische Reihenfolge)."""
    from app.models import interesse_text
    labels = {_normal(t) for t in re.split(r"[,;/|]", text or "") if t.strip()}
    codes = [code for code, varianten in _INTERESSE_LABELS.items()
             if labels & set(varianten)]
    return interesse_text(codes)


def kunde_fuer_lead(session: Session, lead: Lead):
    """Phase 24: der Sync legt jeden Lead sofort als Kunden an bzw. aktualisiert
    ihn (Duplikatabgleich Name + PLZ); nicht-leere monday-Werte gewinnen."""
    from app.models import Kunde
    kunde = session.get(Kunde, lead.kunde_id) if lead.kunde_id else None
    if kunde is None:
        for kandidat in session.query(Kunde).filter(Kunde.plz == lead.plz):
            if (_normal(kandidat.nachname) == _normal(lead.nachname)
                    and _normal(kandidat.vorname) == _normal(lead.vorname)):
                kunde = kandidat
                break
    if kunde is None:
        kunde = Kunde()
        session.add(kunde)
    for feld in ("anrede", "vorname", "nachname", "strasse", "plz", "ort",
                 "telefon", "email", "interesse"):
        wert = getattr(lead, feld)
        if wert:
            setattr(kunde, feld, wert)
    session.flush()
    lead.kunde_id = kunde.id
    return kunde


def sync(session: Session | None = None) -> dict:
    """Ein Sync-Lauf über alle aktiven Quellen. Fehler je Quelle, nie blockierend."""
    eigen = session is None
    if eigen:
        session = SessionLocal()
    status["laeuft"] = True
    fehler: list[str] = []
    anzahl = 0
    try:
        quellen_vorbelegen(session)
        gesehen: dict[tuple[str, str], str] = {}   # (name, plz) -> monday_item_id (Dedup)
        for lead in session.query(Lead):
            gesehen[(_normal(f"{lead.vorname} {lead.nachname}"), lead.plz.strip())] = \
                lead.monday_item_id
        for quelle in session.query(MondayQuelle).filter(MondayQuelle.aktiv.is_(True)):
            try:
                anzahl += _quelle_syncen(session, quelle, gesehen)
            except Exception as problem:
                fehler.append(f"{quelle.board_name or quelle.board_id}: {problem}")
        session.commit()
    finally:
        if eigen:
            session.close()
        status.update(letzter_sync=datetime.now(), fehler=fehler,
                      laeuft=False, anzahl=anzahl)
    return dict(status)


def _quelle_syncen(session: Session, quelle: MondayQuelle,
                   gesehen: dict) -> int:
    zuordnung = _mapping(session, quelle.board_id)
    board_name, items = _items_der_gruppe(quelle.board_id, quelle.gruppen_titel)
    quelle.board_name = quelle.board_name or board_name
    anzahl = 0
    for item in items:
        spalten = {c["id"]: (c.get("text") or "") for c in item["column_values"]}

        def wert(feld):
            return spalten.get(zuordnung.get(feld, ""), "").strip()

        lead = (session.query(Lead)
                .filter(Lead.monday_item_id == str(item["id"])).first())
        neu = lead is None
        if neu:
            lead = Lead(monday_item_id=str(item["id"]))
        # Hinweis (v5-Nachtrag): der Sync aktualisiert nur Stammdaten – das
        # Kennzeichen „ausgeblendet“ bleibt stehen, ausgeblendete Leads tauchen
        # also nicht erneut in „Leads VOT“ auf.

        lead.board_id = quelle.board_id
        lead.board_name = board_name
        lead.vot_datum = _datum_parsen(wert("vot_datum"))
        lead.status_text = wert("status")
        lead.anrede = wert("anrede")
        vorname, nachname = wert("vorname"), wert("nachname")
        if not (vorname or nachname):
            teile = (item.get("name") or "").rsplit(" ", 1)
            vorname, nachname = (teile[0], teile[1]) if len(teile) == 2 else ("", item.get("name") or "")
        lead.vorname, lead.nachname = vorname, nachname
        lead.strasse = wert("strasse")
        lead.plz, lead.ort = _plz_ort_trennen(wert("plz"), wert("ort"))
        lead.telefon = wert("telefon")
        lead.email = wert("email")
        lead.interesse = interesse_aus_text(wert("interesse"))   # Phase 33
        lead.monday_person = wert("verantwortlicher")
        if lead.benutzer_manuell:
            pass   # manuelle Zuordnung durch den Innendienst hat Vorrang (v5-Nachtrag)
        elif quelle.fester_benutzer_id:
            # Sonderregel (z. B. Deals - Rene): Verantwortlicher immer dieser Benutzer
            lead.benutzer_id = quelle.fester_benutzer_id
        else:
            lead.benutzer_id = _benutzer_fuer_person(session, lead.monday_person)

        schluessel = (_normal(f"{lead.vorname} {lead.nachname}"), lead.plz.strip())
        if neu:
            vorhanden = gesehen.get(schluessel)
            if vorhanden and vorhanden != lead.monday_item_id:
                continue   # Dedup: derselbe Kunde ist bereits aus einem anderen Board da
            session.add(lead)
            gesehen[schluessel] = lead.monday_item_id
        kunde_fuer_lead(session, lead)   # Kunden sofort anlegen/aktualisieren (Phase 24)
        anzahl += 1
    return anzahl


# --- Hintergrund-Scheduler (alle 15 Minuten) ------------------------------

_scheduler_gestartet = False


def scheduler_starten() -> None:
    global _scheduler_gestartet
    if _scheduler_gestartet:
        return
    _scheduler_gestartet = True

    def schleife():
        import time
        while True:
            if config.MONDAY_API_TOKEN:
                try:
                    sync()
                except Exception as problem:   # nie durchschlagen lassen
                    status["fehler"] = [f"Sync-Lauf fehlgeschlagen: {problem}"]
            time.sleep(SYNC_INTERVALL_SEKUNDEN)

    threading.Thread(target=schleife, daemon=True).start()
