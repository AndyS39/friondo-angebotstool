# monday-Lesesync (Phase 22): liest Leads mit Vor-Ort-Termin aus den in der
# Parametrierung gepflegten Quellen (Board + Gruppentitel „Terminiert“).
# Nur lesend; Fehler werden gesammelt angezeigt und blockieren das Tool nie.
# Läuft alle 15 Minuten im Hintergrund plus Button „Jetzt aktualisieren“.
# v27 (PLAN_V17 Phase 128): der 15-Minuten-Lauf ist am Scheduler-Rahmen
# registriert (aktiv nur mit MONDAY_API_TOKEN) und arbeitet in kurzen Sitzungen
# (lesen → Sitzung zu → monday → kurze Sitzung schreiben); geschrieben wird in
# Blöcken mit Commit je 200 Items. Der manuelle Vollabgleich (Button, Request-
# Session) meldet sich als laufender Import (Betriebs-Status, /health).

import contextlib
import json
import re
import urllib.request
from datetime import datetime

from sqlalchemy.orm import Session

from app import config
from app.db import verbindung_freigeben
from app.models import (Benutzer, Lead, MondayMapping, MondayPerson,
                        MondayQuelle, MONDAY_FELDER)

API_URL = "https://api.monday.com/v2"
SYNC_INTERVALL_SEKUNDEN = 15 * 60
BLOCK_GROESSE = 200          # v27: Commit je 200 Items beim Schreiben

# Vorbelegte, verifizierte Quellen lt. CLAUDE.md v3
STANDARD_QUELLEN = [
    ("5080725439", "Deals (Blinno Working Space)", "Terminiert", None),
    ("5089971526", "Deals - Simon (Pool Working Space)", "Terminiert", None),
    ("5092657267", "Deals - Rene (Pool Working Space)", "Terminiert",
     "Rene Golaschewski"),   # Sonderregel: Verantwortlicher immer dieser Benutzer
]

status = {"letzter_sync": None, "fehler": [], "laeuft": False, "anzahl": 0,
          "quellen": 0, "quellen_fehler": 0}


def monday_aktiv():
    """aktiv-Bedingung des Scheduler-Laufs: Token in der .env vorhanden."""
    return True if config.MONDAY_API_TOKEN else "kein monday-Token"


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
    ("Kyriakos Sarigiannis, Niko Goritsas") zählt die erste Person.
    Automatisches Matching über Namensgleichheit ODER Benutzer-E-Mail
    (monday liefert z. T. E-Mail-Adressen als Personen-Namen, v6)."""
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
    if benutzer is None and "@" in name:
        benutzer = (session.query(Benutzer)
                    .filter(Benutzer.email == name.lower()).first())
    if benutzer is not None:
        zuordnung.benutzer_id = benutzer.id   # automatisch verknüpfen
        return benutzer.id
    return None


def zuordnung_anwenden(session: Session, person: MondayPerson) -> int:
    """v6-Bugfix: eine (neue) Personen-Zuordnung sofort rückwirkend auf alle
    vorhandenen Leads mit diesem monday-Namen anwenden – bisher griff sie erst
    beim nächsten Sync-Lauf (und ohne API-Token nie). Manuell zugeordnete
    Leads bleiben unberührt. Liefert die Zahl aktualisierter Leads."""
    if not person.benutzer_id:
        return 0
    anzahl = 0
    for lead in session.query(Lead).filter(Lead.benutzer_manuell.is_(False)):
        erster = (lead.monday_person or "").split(",")[0].strip()
        if erster == person.monday_name and lead.benutzer_id != person.benutzer_id:
            lead.benutzer_id = person.benutzer_id
            anzahl += 1
    return anzahl


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
                 "telefon", "email", "interesse", "vertriebskanal"):
        if feld == "vertriebskanal" and kunde.kanal_manuell:
            continue   # v9: manuell gesetzter Kunden-Kanal bleibt stehen
        wert = getattr(lead, feld)
        if wert:
            setattr(kunde, feld, wert)
    session.flush()
    lead.kunde_id = kunde.id
    return kunde


def _gesehen(session: Session) -> dict[tuple[str, str], str]:
    """(name, plz) -> monday_item_id aller Leads (Dedup über Boards hinweg)."""
    gesehen: dict[tuple[str, str], str] = {}
    for z in session.query(Lead.vorname, Lead.nachname, Lead.plz, Lead.monday_item_id):
        gesehen[(_normal(f"{z[0]} {z[1]}"), (z[2] or "").strip())] = z[3]
    return gesehen


def sync(session: Session | None = None, *, markieren: bool = True) -> dict:
    """Ein Sync-Lauf über alle aktiven Quellen. Fehler je Quelle, nie blockierend.
    v27 (PLAN_V17 Phase 128): mit übergebener Session (Button „Jetzt
    aktualisieren“) wird mit dieser gearbeitet – Freigabe vor jedem monday-Aufruf,
    Commit je Quelle und je 200 Items – und der Vollabgleich als laufender Import
    gemeldet (markieren=True, Betriebs-Status/health). Der 15-Minuten-Lauf
    (session=None, markieren=False) arbeitet in kurzen Sitzungen: lesen →
    Sitzung zu → monday → kurze Sitzung zum Schreiben in Blöcken."""
    from app import betrieb
    status["laeuft"] = True
    fehler: list[str] = []
    anzahl = quellen_gesamt = quellen_fehler = 0
    markierung = (betrieb.import_markieren("monday-Sync") if markieren
                  else contextlib.nullcontext())
    try:
        with markierung:
            if session is not None:
                anzahl, quellen_gesamt, quellen_fehler = _sync_mit_session(session, fehler)
            else:
                # netz-ohne-sitzung-ok: in diesem Zweig ist session None – der Lauf
                # arbeitet ausschließlich mit eigenen kurzen Sitzungen (db.kurz)
                anzahl, quellen_gesamt, quellen_fehler = _sync_in_bloecken(fehler)   # netz-ohne-sitzung-ok
    finally:
        status.update(letzter_sync=datetime.now(), fehler=fehler, laeuft=False,
                      anzahl=anzahl, quellen=quellen_gesamt, quellen_fehler=quellen_fehler)
    return dict(status)


def _nachlauf(session: Session, fehler: list[str]) -> None:
    """v12 (Phase 73): abgeleitete Lead-Phase der gesyncten Vorgänge – rein
    lesend gegenüber monday, Fehler blockieren den Sync nie (v27: werden aber
    als Hinweis genannt statt verschluckt)."""
    try:
        from app import leadmanagement
        leadmanagement.nach_sync(session)
    except Exception as problem:
        fehler.append(f"Nachlauf (Lead-Phasen): {problem}")


def _sync_mit_session(session: Session, fehler: list[str]) -> tuple[int, int, int]:
    """Request-Pfad (Button): Hotfix-Muster mit Freigabe vor jedem monday-Aufruf,
    Commit je Quelle (Block); eine gescheiterte Quelle wird zurückgerollt."""
    quellen_vorbelegen(session)
    gesehen = _gesehen(session)
    quellen = session.query(MondayQuelle).filter(MondayQuelle.aktiv.is_(True)).all()
    anzahl = quellen_fehler = 0
    for quelle in quellen:
        try:
            anzahl += _quelle_syncen(session, quelle, gesehen)
            session.commit()
        except Exception as problem:
            session.rollback()
            quellen_fehler += 1
            fehler.append(f"{quelle.board_name or quelle.board_id}: {problem}")
    _nachlauf(session, fehler)
    return anzahl, len(quellen), quellen_fehler


def _sync_in_bloecken(fehler: list[str]) -> tuple[int, int, int]:
    """Scheduler-Pfad: keine Sitzung während der monday-Abfragen (mehrere
    Seiten, bis 30 s je Aufruf); Schreiben je Quelle in einer kurzen Sitzung,
    Commit je 200 Items (in _items_schreiben) und am Ende der Quelle."""
    from app.db import kurz
    with kurz() as s:
        quellen_vorbelegen(s)
        gesehen = _gesehen(s)
        quellen = [(q.id, q.board_id, q.gruppen_titel, q.board_name) for q in
                   s.query(MondayQuelle).filter(MondayQuelle.aktiv.is_(True))]
    anzahl = quellen_fehler = 0
    for quelle_id, board_id, gruppen_titel, board_name_alt in quellen:
        try:
            with kurz() as s:
                zuordnung = _mapping(s, board_id)
            board_name, items = _items_der_gruppe(board_id, gruppen_titel)   # Netz ohne Sitzung
            with kurz() as s:
                quelle = s.get(MondayQuelle, quelle_id)
                if quelle is None:
                    continue   # inzwischen gelöscht
                quelle.board_name = quelle.board_name or board_name
                anzahl += _items_schreiben(s, quelle, zuordnung, board_name, items, gesehen)
        except Exception as problem:
            quellen_fehler += 1
            fehler.append(f"{board_name_alt or board_id}: {problem}")
    with kurz() as s:
        _nachlauf(s, fehler)
    return anzahl, len(quellen), quellen_fehler


def _quelle_syncen(session: Session, quelle: MondayQuelle,
                   gesehen: dict) -> int:
    """Eine Quelle mit übergebener Session (Button, Tests): Mapping lesen,
    Verbindung freigeben, monday abfragen, Items schreiben."""
    zuordnung = _mapping(session, quelle.board_id)
    board_id, gruppen_titel = quelle.board_id, quelle.gruppen_titel
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Mapping und Quelle
    # sind gelesen; der commit speichert die Leads der vorherigen Quelle – wie
    # bisher am Ende des Laufs; die Board-Abfrage läuft über mehrere Seiten)
    verbindung_freigeben(session)
    board_name, items = _items_der_gruppe(board_id, gruppen_titel)
    quelle.board_name = quelle.board_name or board_name
    return _items_schreiben(session, quelle, zuordnung, board_name, items, gesehen)


def _items_schreiben(session: Session, quelle: MondayQuelle, zuordnung: dict,
                     board_name: str, items: list[dict], gesehen: dict) -> int:
    """Items einer Quelle als Leads/Kunden/Vorgänge schreiben – v27: Commit je
    BLOCK_GROESSE Items (Schreibsperre nie lange am Stück); den Abschluss
    committet der Aufrufer."""
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
        if not lead.kanal_manuell:   # v9: manueller Kanal hat Vorrang
            lead.vertriebskanal = wert("vertriebskanal")[:100]    # v6
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
        # Prozess-Fix 27.09.2026: Vorgang sofort anlegen - sonst fehlen neue
        # monday-Leads in Board/Statistik/Karte und ihre VOT-Termine dem
        # Terminassistenten (Doppelbuchungs-Gefahr)
        try:
            from app.vorgaenge import vorgang_fuer_lead
            vorgang_fuer_lead(session, lead)
        except Exception:
            pass   # Sync nie an der Vorgangs-Anlage scheitern lassen
        anzahl += 1
        if anzahl % BLOCK_GROESSE == 0:
            session.commit()   # v27 (Phase 128): Block-Commit je 200 Items
    return anzahl


# --- Hintergrund-Scheduler (alle 15 Minuten, v27 am Rahmen registriert) ------

def scheduler_lauf() -> dict:
    """15-Minuten-Lauf: Fehler je Quelle stehen im Rückgabe-dict (fehler =
    Anzahl, hinweis = erster Fehler); scheitern ALLE Quellen, wird eine
    Ausnahme hochgeworfen (Lauf = fehler, Datei-Log)."""
    ergebnis = sync(markieren=False)
    fehler = list(ergebnis.get("fehler") or [])
    klein = {"anzahl": ergebnis.get("anzahl", 0), "quellen": ergebnis.get("quellen", 0),
             "fehler": fehler}
    if fehler:
        klein["hinweis"] = fehler[0][:120]
        quellen, quellen_fehler = klein["quellen"], ergebnis.get("quellen_fehler", 0)
        if quellen and quellen_fehler >= quellen:
            raise RuntimeError("Alle monday-Quellen fehlgeschlagen – "
                               + "; ".join(fehler)[:450])
    return klein


def scheduler_starten() -> None:
    """v27 (PLAN_V17 Phase 128): registriert den 15-Minuten-Lauf nur noch am
    Scheduler-Rahmen (aktiv nur mit MONDAY_API_TOKEN); Threads startet
    main.lifespan über scheduler.starten_alle()."""
    from app import scheduler
    scheduler.registrieren(
        "monday-sync", SYNC_INTERVALL_SEKUNDEN, scheduler_lauf,
        beschreibung="monday-Leads mit Vor-Ort-Termin aus den Quellen einlesen (Leads VOT)",
        aktiv=monday_aktiv)
