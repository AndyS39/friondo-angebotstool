# Lead-Management V2 – To-Dos (v23, PLAN_LEAD_V2 Phase 110, Diktat A2, F7).
# Abgrenzung: Wiedervorlage = Kundenkontakt zu einem Zeitpunkt (bleibt am
# Vorgang: naechste_aktion_am / zurueckgestellt_bis / wiedervorlage_am);
# To-Do = Arbeitsauftrag mit Empfänger, optionalem Vorgangsbezug, Fälligkeit
# und Erledigt-Status (Tabelle todos, Phase 104). Jeder darf jedem zuweisen
# (F7); Benachrichtigung ausschließlich über die Glocke (art=todo) – keine
# Mail, deshalb wird der Glocken-Eintrag hier direkt angelegt und nicht über
# projektierung.benachrichtigen (das die Sofort-Mail anstößt).

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Benachrichtigung, Benutzer, Kunde, Todo, Vorgang

ART = "todo"
TITEL_MAX = 300


# --- Glocke -------------------------------------------------------------------------

# v29 (PLAN_LEAD_V4 Phase 141) „Glocke nur To-Dos“: die beiden Lead-Glocken-
# Arten dieses Moduls – todo_zugewiesen (jemand anderes weist mir ein To-Do zu,
# auch die Fälligkeits-Glocke eines mir zugewiesenen To-Dos [ANNAHME]) und
# todo_aktualisiert (jemand anderes erledigt, öffnet oder löscht ein von mir
# erstelltes To-Do). Eigene Änderungen lösen nichts aus. Beide laufen über
# lead_glocken.glocke_erlaubt (Parameter glocke_lead_arten); der Eintrag selbst
# behält art=todo (Demo-Filter, Glocken-Link, bestehende Tests).
ART_ZUGEWIESEN = "todo_zugewiesen"
ART_AKTUALISIERT = "todo_aktualisiert"


def _glocke(session: Session, benutzer_id: int | None, text: str, link: str,
            von=None, art: str = ART_ZUGEWIESEN) -> bool:
    """Glocken-Eintrag art=todo ohne Mail (F7). Der Demo-Filter in
    app/benachrichtigungen.py greift nur für PROJEKT_ARTEN/LEAD_ARTEN, To-Dos
    kommen also auch bei Benutzern ohne Modul-Sichtbarkeit durch.
    v29: nur, wenn die Lead-Glocken-Art `art` erlaubt ist (lead_glocken);
    nie an den Handelnden selbst. Rückgabe True = Glocke angelegt."""
    from app import lead_glocken
    if not benutzer_id:
        return False
    if von is not None and getattr(von, "id", None) == benutzer_id:
        return False
    if not lead_glocken.glocke_erlaubt(session, art):
        return False
    session.add(Benachrichtigung(benutzer_id=benutzer_id, text=(text or "")[:500],
                                 link=(link or "")[:300], art=ART,
                                 erstellt_von=von.id if von is not None else None))
    session.flush()
    return True


def link_fuer(session: Session, benutzer_id: int, todo: Todo | None = None) -> str:
    """Ziel der Glocke: Außendienst sieht To-Dos in „Meine Termine“, alle
    anderen in der To-Do-Liste des Lead-Moduls. Handelsvertreter (A-1,
    Hauptrolle ebenfalls aussendienst) erreichen /lead-management/todos über
    lead_v2.zugriff_erlaubt – „Meine Termine“ wäre für sie im Demo-Modus 404."""
    empfaenger = session.get(Benutzer, benutzer_id) if benutzer_id else None
    anker = f"#todo-{todo.id}" if todo is not None and todo.id else ""
    if empfaenger is not None and empfaenger.rolle == "aussendienst":
        try:
            from app import lead_v2
            hv = lead_v2.ist_handelsvertreter(session, empfaenger)
        except Exception:
            hv = False
        if not hv:
            return "/lead-management/meine-termine" + anker
    return "/lead-management/todos" + anker


def _kunde_text(session: Session, vorgang_id: int | None) -> str:
    if not vorgang_id:
        return ""
    vorgang = session.get(Vorgang, vorgang_id)
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang else None
    return kunde.anzeige_name if kunde else ""


# --- Hilfen -------------------------------------------------------------------------

def faellig_parsen(text: str | None) -> datetime | None:
    """„YYYY-MM-DDTHH:MM“ (datetime-local) oder „YYYY-MM-DD“ → datetime;
    reines Datum = 09:00 Uhr. Ungültig/leer = keine Fälligkeit."""
    roh = (text or "").strip().replace(" ", "T")
    if not roh:
        return None
    for muster in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(roh, muster)
        except ValueError:
            continue
    try:
        return datetime.strptime(roh, "%Y-%m-%d").replace(hour=9)
    except ValueError:
        return None


def empfaenger_liste(session: Session) -> list[Benutzer]:
    """Jeder aktive Benutzer ist wählbar (F7) – auch Außendienst,
    Projektierung, Montage."""
    return (session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
            .order_by(Benutzer.name).all())


def darf_sehen(benutzer, todo: Todo) -> bool:
    if benutzer is None or todo is None:
        return False
    return (benutzer.rolle == "admin" or todo.an_benutzer_id == benutzer.id
            or todo.von_benutzer_id == benutzer.id)


def darf_erledigen(benutzer, todo: Todo) -> bool:
    """Empfänger, Ersteller und Admin dürfen erledigen/wieder öffnen."""
    return darf_sehen(benutzer, todo)


def darf_loeschen(benutzer, todo: Todo) -> bool:
    """Nur Ersteller oder Admin (Vertrag Phase 110)."""
    if benutzer is None or todo is None:
        return False
    return benutzer.rolle == "admin" or todo.von_benutzer_id == benutzer.id


def _aktivitaet(session: Session, todo: Todo, text: str, benutzer=None) -> None:
    if not todo.vorgang_id:
        return
    from app import leadmanagement as kern
    kern.aktivitaet(session, todo.vorgang_id, "system", text, benutzer=benutzer)


# --- Kernfunktionen (Vertrag Phase 110) ---------------------------------------------

def anlegen(session: Session, von, an_benutzer_id: int, titel: str,
            text: str = "", faellig_am: datetime | str | None = None,
            vorgang_id: int | None = None) -> Todo:
    """Neues To-Do: Glocke art=todo an den Empfänger (nicht an sich selbst),
    Aktivität am Vorgang (falls Vorgangsbezug). titel ist Pflicht."""
    titel = (titel or "").strip()
    if not titel:
        raise ValueError("Titel ist Pflicht.")
    empfaenger = session.get(Benutzer, int(an_benutzer_id or 0))
    if empfaenger is None or not empfaenger.aktiv:
        raise ValueError("Empfänger nicht gefunden.")
    if isinstance(faellig_am, str):
        faellig_am = faellig_parsen(faellig_am)
    if vorgang_id and session.get(Vorgang, int(vorgang_id)) is None:
        vorgang_id = None
    todo = Todo(vorgang_id=int(vorgang_id) if vorgang_id else None,
                titel=titel[:TITEL_MAX], text=(text or "").strip(),
                faellig_am=faellig_am, an_benutzer_id=empfaenger.id,
                von_benutzer_id=von.id if von is not None else None,
                status="offen", erstellt_von=von.id if von is not None else None)
    session.add(todo)
    session.flush()
    kunde = _kunde_text(session, todo.vorgang_id)
    wer = von.name if von is not None else "System"
    _aktivitaet(session, todo,
                f"To-Do für {empfaenger.name}: {titel}"
                + (f" (fällig {faellig_am.strftime('%d.%m.%Y %H:%M')})" if faellig_am else ""),
                benutzer=von)
    if von is None or von.id != empfaenger.id:
        _glocke(session, empfaenger.id,
                f"To-Do von {wer}: {titel}" + (f" – {kunde}" if kunde else ""),
                link_fuer(session, empfaenger.id, todo), von=von, art=ART_ZUGEWIESEN)
    return todo


def erledigen(session: Session, todo: Todo, benutzer=None) -> bool:
    """Status erledigt + Zeitstempel, Aktivität am Vorgang, Glocke an den
    Ersteller (wenn ein anderer erledigt). False, wenn schon erledigt."""
    if todo.status == "erledigt":
        return False
    todo.status = "erledigt"
    todo.erledigt_am = datetime.now()
    session.flush()
    wer = benutzer.name if benutzer is not None else "System"
    _aktivitaet(session, todo, f"To-Do erledigt: {todo.titel} ({wer})", benutzer=benutzer)
    if (todo.von_benutzer_id and benutzer is not None
            and todo.von_benutzer_id != benutzer.id):
        kunde = _kunde_text(session, todo.vorgang_id)
        _glocke(session, todo.von_benutzer_id,
                f"To-Do erledigt von {wer}: {todo.titel}" + (f" – {kunde}" if kunde else ""),
                link_fuer(session, todo.von_benutzer_id, todo), von=benutzer,
                art=ART_AKTUALISIERT)
    return True


def _ersteller_melden(session: Session, todo: Todo, benutzer, text: str) -> None:
    """v29: jemand anderes ändert ein von mir erstelltes To-Do → Glocke
    todo_aktualisiert an den Ersteller (nie an den Handelnden)."""
    if (todo.von_benutzer_id and benutzer is not None
            and todo.von_benutzer_id != benutzer.id):
        kunde = _kunde_text(session, todo.vorgang_id)
        _glocke(session, todo.von_benutzer_id,
                text + (f" – {kunde}" if kunde else ""),
                link_fuer(session, todo.von_benutzer_id, todo), von=benutzer,
                art=ART_AKTUALISIERT)


def wieder_oeffnen(session: Session, todo: Todo, benutzer=None) -> bool:
    if todo.status != "erledigt":
        return False
    todo.status = "offen"
    todo.erledigt_am = None
    session.flush()
    _aktivitaet(session, todo, f"To-Do wieder geöffnet: {todo.titel}", benutzer=benutzer)
    wer = benutzer.name if benutzer is not None else "System"
    _ersteller_melden(session, todo, benutzer, f"To-Do wieder geöffnet von {wer}: {todo.titel}")
    return True


def loeschen(session: Session, todo: Todo, benutzer=None) -> None:
    _aktivitaet(session, todo, f"To-Do gelöscht: {todo.titel}", benutzer=benutzer)
    wer = benutzer.name if benutzer is not None else "System"
    _ersteller_melden(session, todo, benutzer, f"To-Do gelöscht von {wer}: {todo.titel}")
    session.delete(todo)
    session.flush()


def _sortiert(abfrage):
    """Fällige zuerst (ältestes Datum oben), ohne Fälligkeit danach."""
    return abfrage.order_by(Todo.faellig_am.is_(None), Todo.faellig_am, Todo.erstellt_am)


def offene(session: Session, benutzer_id: int) -> list[Todo]:
    """Meine offenen To-Dos, fällig zuerst."""
    return _sortiert(session.query(Todo)
                     .filter(Todo.an_benutzer_id == benutzer_id,
                             Todo.status == "offen")).all()


def erledigte(session: Session, benutzer_id: int, limit: int = 50) -> list[Todo]:
    return (session.query(Todo)
            .filter(Todo.an_benutzer_id == benutzer_id, Todo.status == "erledigt")
            .order_by(Todo.erledigt_am.desc()).limit(limit).all())


def vergebene(session: Session, benutzer_id: int, status: str | None = "offen") -> list[Todo]:
    """Von mir an andere vergebene To-Dos."""
    abfrage = (session.query(Todo)
               .filter(Todo.von_benutzer_id == benutzer_id,
                       Todo.an_benutzer_id != benutzer_id))
    if status:
        abfrage = abfrage.filter(Todo.status == status)
    return _sortiert(abfrage).all()


def fuer_vorgang(session: Session, vorgang_id: int) -> list[Todo]:
    """Alle To-Dos eines Vorgangs, offene zuerst (Kartei B5 / Akte)."""
    return (session.query(Todo).filter(Todo.vorgang_id == vorgang_id)
            .order_by(Todo.status.desc(), Todo.faellig_am.is_(None),
                      Todo.faellig_am, Todo.erstellt_am).all())


def zaehler(session: Session, benutzer_id: int, jetzt: datetime | None = None) -> dict:
    """Kacheln/Portal: offen gesamt und davon fällig (bis jetzt)."""
    jetzt = jetzt or datetime.now()
    liste = offene(session, benutzer_id)
    return {"offen": len(liste),
            "faellig": sum(1 for t in liste if t.faellig_am and t.faellig_am <= jetzt)}


def zeilen(session: Session, todos: list[Todo], jetzt: datetime | None = None) -> list[dict]:
    """Anzeigezeilen: Namen von/an, Kunde, Fälligkeitsklasse."""
    jetzt = jetzt or datetime.now()
    heute = jetzt.date()
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    vorgang_ids = {t.vorgang_id for t in todos if t.vorgang_id}
    vorgaenge = ({v.id: v for v in session.query(Vorgang).filter(Vorgang.id.in_(vorgang_ids))}
                 if vorgang_ids else {})
    kunden_ids = {v.kunde_id for v in vorgaenge.values()}
    kunden = ({k.id: k for k in session.query(Kunde).filter(Kunde.id.in_(kunden_ids))}
              if kunden_ids else {})
    ergebnis = []
    for t in todos:
        v = vorgaenge.get(t.vorgang_id) if t.vorgang_id else None
        k = kunden.get(v.kunde_id) if v else None
        if t.faellig_am is None or t.status != "offen":
            klasse = ""
        elif t.faellig_am <= jetzt:
            klasse = "faellig"
        elif t.faellig_am.date() == heute:
            klasse = "heute"
        else:
            klasse = "geplant"
        an = benutzer_map.get(t.an_benutzer_id)
        von = benutzer_map.get(t.von_benutzer_id) if t.von_benutzer_id else None
        ergebnis.append({"todo": t, "vorgang": v, "kunde": k, "klasse": klasse,
                         "an": an.name if an else "?",
                         "von": von.name if von else "System",
                         "demo": bool(v and v.demo)})
    return ergebnis


# --- Fälligkeits-Glocke (einmal je To-Do, beim ersten Erreichen) -------------------

def faellige_glocken(session: Session, jetzt: datetime | None = None,
                     block: int = 0) -> int:
    """Glocke „To-Do fällig“ an den Empfänger, sobald faellig_am erreicht ist;
    dedupliziert über einen bestehenden Glocken-Eintrag mit demselben Link
    (kann aus dem 5-Minuten-Lead-Scheduler aufgerufen werden). v27 (PLAN_V17
    Phase 128): block > 0 → Commit je `block` Glocken (Scheduler-Lauf); die
    Liste wird vorab geladen, damit der Commit den Cursor nicht trifft.
    v29 (Phase 141): der Fälligkeits-Scheduler meldet nur noch To-Do-
    Fälligkeiten (Art todo_zugewiesen, abschaltbar über glocke_lead_arten)."""
    jetzt = jetzt or datetime.now()
    anzahl = 0
    for t in (session.query(Todo)
              .filter(Todo.status == "offen", Todo.faellig_am.isnot(None),
                      Todo.faellig_am <= jetzt)
              .order_by(Todo.id).all()):
        link = link_fuer(session, t.an_benutzer_id, t)
        schon = (session.query(Benachrichtigung)
                 .filter(Benachrichtigung.benutzer_id == t.an_benutzer_id,
                         Benachrichtigung.art == ART,
                         Benachrichtigung.link == link,
                         Benachrichtigung.text.like("To-Do fällig:%")).count())
        if schon:
            continue
        kunde = _kunde_text(session, t.vorgang_id)
        # v29: Fälligkeits-Glocke nur an den Empfänger, Art todo_zugewiesen [ANNAHME]
        if not _glocke(session, t.an_benutzer_id,
                       f"To-Do fällig: {t.titel}" + (f" – {kunde}" if kunde else ""), link,
                       art=ART_ZUGEWIESEN):
            continue
        anzahl += 1
        if block and anzahl % block == 0:
            session.commit()   # v27: Block-Commit im Scheduler-Lauf
    return anzahl
