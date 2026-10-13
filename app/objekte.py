# v31 (PLAN_LEAD_V5 Phase 153): Objekte am Vorgang und der Ausführungsort.
#
# Regeln (Einfügung AT-Chat 13.10.2026):
# - Jeder Vorgang hat mindestens ein Objekt; das Hauptobjekt (reihenfolge = 1) ist die
#   heutige Kundenadresse und bleibt mit den Kundenfeldern synchron (hauptobjekt_sync),
#   damit monday-Sync, Duplikatprüfung, Geocoding, Karte und Bestandslisten unverändert
#   funktionieren. Für Ein-Objekt-Vorgänge ändert sich nichts.
# - Angebotstool, Projektierung und Mails lesen den Ausführungsort NUR noch über
#   ausfuehrungsort(...): Objekt 2 → Objektadresse, sonst Kundenadresse.
# - Migration (migration_v31_objekte): je Vorgang ein Hauptobjekt aus der Kundenadresse;
#   objekt_id an vot_termine/erfassungen/angebote/gewerke = Hauptobjekt des Vorgangs.
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Angebot, Erfassung, Gewerk, Kunde, Vorgang, VorgangObjekt, VotTermin

FELDER_ADRESSE = ("strasse", "plz", "ort")


def interessen_liste(objekt: VorgangObjekt | None) -> list[str]:
    if objekt is None or not objekt.interessen:
        return []
    try:
        daten = json.loads(objekt.interessen)
    except ValueError:
        daten = [t.strip() for t in objekt.interessen.replace(";", ",").split(",")]
    return [str(d).strip().upper() for d in daten if str(d).strip()]


def interessen_setzen(objekt: VorgangObjekt, codes) -> None:
    from app import sparten
    objekt.interessen = json.dumps(sparten.codes(codes))


def objekte_fuer(session: Session, vorgang_id: int, nur_aktive: bool = True) -> list[VorgangObjekt]:
    abfrage = session.query(VorgangObjekt).filter(VorgangObjekt.vorgang_id == int(vorgang_id))
    if nur_aktive:
        abfrage = abfrage.filter(VorgangObjekt.aktiv.is_(True))
    return abfrage.order_by(VorgangObjekt.reihenfolge, VorgangObjekt.id).all()


def hauptobjekt(session: Session, vorgang_id: int, anlegen: bool = False,
                kunde: Kunde | None = None) -> VorgangObjekt | None:
    """Objekt mit reihenfolge = 1 (bei Lücken das erste aktive). Mit `anlegen=True`
    wird es aus der Kundenadresse angelegt, wenn der Vorgang noch keines hat."""
    objekte = objekte_fuer(session, vorgang_id, nur_aktive=False)
    haupt = next((o for o in objekte if o.reihenfolge == 1), None) or (objekte[0] if objekte else None)
    if haupt is None and anlegen:
        vorgang = session.get(Vorgang, int(vorgang_id))
        if vorgang is None:
            return None
        kunde = kunde or session.get(Kunde, vorgang.kunde_id)
        haupt = hauptobjekt_anlegen(session, vorgang, kunde)
    return haupt


def hauptobjekt_anlegen(session: Session, vorgang: Vorgang, kunde: Kunde | None) -> VorgangObjekt:
    from app import sparten
    objekt = VorgangObjekt(
        vorgang_id=vorgang.id, bezeichnung="Objekt 1", reihenfolge=1, aktiv=True,
        strasse=(kunde.strasse if kunde else "") or "", plz=(kunde.plz if kunde else "") or "",
        ort=(kunde.ort if kunde else "") or "",
        objektart=(kunde.objektart if kunde else None),
        parteien=(kunde.parteien if kunde else None),
        interessen=json.dumps(sparten.codes(kunde.interesse if kunde else "")),
        lat=vorgang.lat, lon=vorgang.lon, geocode_status=vorgang.geocode_status)
    session.add(objekt)
    session.flush()
    return objekt


def objekt_anlegen(session: Session, vorgang: Vorgang, strasse: str = "", plz: str = "",
                   ort: str = "", bezeichnung: str = "", objektart: str | None = None,
                   parteien: int | None = None, interessen=None) -> VorgangObjekt:
    """Weiteres Objekt (reihenfolge = nächste freie Nummer)."""
    from app import sparten
    vorhandene = objekte_fuer(session, vorgang.id, nur_aktive=False)
    if not vorhandene:
        hauptobjekt(session, vorgang.id, anlegen=True)
        vorhandene = objekte_fuer(session, vorgang.id, nur_aktive=False)
    nummer = max([o.reihenfolge for o in vorhandene] or [0]) + 1
    objekt = VorgangObjekt(
        vorgang_id=vorgang.id, bezeichnung=(bezeichnung or f"Objekt {nummer}")[:100],
        reihenfolge=nummer, aktiv=True, strasse=(strasse or "")[:200], plz=(plz or "")[:10],
        ort=(ort or "")[:100], objektart=objektart or None, parteien=parteien,
        interessen=json.dumps(sparten.codes(interessen)))
    session.add(objekt)
    session.flush()
    return objekt


def hauptobjekt_sync(session: Session, quelle, kunde: Kunde | None = None) -> None:
    """Hält Hauptobjekt und Kundenfelder synchron. `quelle` ist entweder das
    Hauptobjekt (→ Kundenfelder werden mitgeschrieben) oder der Kunde (→ Hauptobjekte
    aller seiner Vorgänge werden mitgeschrieben). Interessen am Kunden = Vereinigung
    der Objekt-Interessen des Vorgangs (Kunde.interesse als Kommaliste wie bisher)."""
    from app import sparten
    if isinstance(quelle, VorgangObjekt):
        if quelle.reihenfolge != 1:
            return
        vorgang = session.get(Vorgang, quelle.vorgang_id)
        kunde = kunde or (session.get(Kunde, vorgang.kunde_id) if vorgang else None)
        if kunde is None:
            return
        kunde.strasse, kunde.plz, kunde.ort = quelle.strasse or "", quelle.plz or "", quelle.ort or ""
        kunde.objektart = quelle.objektart
        kunde.parteien = quelle.parteien
        if vorgang is not None:
            alle = []
            for o in objekte_fuer(session, vorgang.id):
                alle.extend(interessen_liste(o))
            kunde.interesse = ",".join(sparten.codes(alle))[:50]
            if quelle.lat is not None:
                vorgang.lat, vorgang.lon, vorgang.geocode_status = quelle.lat, quelle.lon, quelle.geocode_status
        session.flush()
        return
    if isinstance(quelle, Kunde):
        for vorgang in session.query(Vorgang).filter(Vorgang.kunde_id == quelle.id):
            haupt = hauptobjekt(session, vorgang.id)
            if haupt is None:
                continue
            haupt.strasse, haupt.plz, haupt.ort = quelle.strasse or "", quelle.plz or "", quelle.ort or ""
            haupt.objektart = quelle.objektart
            haupt.parteien = quelle.parteien
            # Interessen des Hauptobjekts = Kundeninteressen, solange der Vorgang nur ein Objekt hat
            if len(objekte_fuer(session, vorgang.id)) == 1:
                haupt.interessen = json.dumps(sparten.codes(quelle.interesse))
        session.flush()


def vorgang_interessen(session: Session, vorgang_id: int) -> list[str]:
    """Interessen-Badges des Vorgangs = Vereinigung aller Objekt-Interessen."""
    from app import sparten
    alle = []
    for o in objekte_fuer(session, vorgang_id):
        alle.extend(interessen_liste(o))
    return sparten.codes(alle)


def _ort_dict(strasse: str, plz: str, ort: str, bezeichnung: str = "",
              objekt_id: int | None = None, mehrere: bool = False) -> dict:
    return {"strasse": strasse or "", "plz": plz or "", "ort": ort or "",
            "bezeichnung": bezeichnung or "", "objekt_id": objekt_id, "mehrere_objekte": mehrere,
            "einzeilig": ", ".join(t for t in (strasse or "", " ".join(x for x in (plz or "", ort or "") if x)) if t)}


def ausfuehrungsort(session: Session, objekt_id: int | None = None, angebot: Angebot | None = None,
                    erfassung: Erfassung | None = None, gewerk: Gewerk | None = None,
                    vorgang: Vorgang | None = None, kunde: Kunde | None = None,
                    termin: VotTermin | None = None) -> dict:
    """Straße/PLZ/Ort des Ausführungsorts: das Objekt (objekt_id bzw. Objekt von
    Angebot/Erfassung/Gewerk/Termin), sonst das Hauptobjekt des Vorgangs, sonst die
    Kundenadresse. Liefert ein Dict mit strasse, plz, ort, bezeichnung, objekt_id,
    mehrere_objekte, einzeilig – Aufrufer, die bisher kunde.strasse/plz/ort lasen,
    nutzen diese Schlüssel."""
    if objekt_id is None:
        if termin is not None:
            objekt_id = termin.objekt_id
        elif angebot is not None:
            objekt_id = angebot.objekt_id
            if objekt_id is None and getattr(angebot, "erfassung_id", None):
                e = session.get(Erfassung, angebot.erfassung_id)
                objekt_id = e.objekt_id if e is not None else None
        elif erfassung is not None:
            objekt_id = erfassung.objekt_id
        elif gewerk is not None:
            objekt_id = gewerk.objekt_id
            if objekt_id is None and gewerk.angebot_id:
                a = session.get(Angebot, gewerk.angebot_id)
                objekt_id = a.objekt_id if a is not None else None
    objekt = session.get(VorgangObjekt, int(objekt_id)) if objekt_id else None
    vorgang_id = None
    if objekt is not None:
        vorgang_id = objekt.vorgang_id
    elif vorgang is not None:
        vorgang_id = vorgang.id
    elif termin is not None:
        vorgang_id = termin.vorgang_id
    elif erfassung is not None:
        vorgang_id = erfassung.vorgang_id
    elif angebot is not None:
        vorgang_id = angebot.vorgang_id
    elif gewerk is not None:
        from app.models import Projekt
        projekt = session.get(Projekt, gewerk.projekt_id)
        vorgang_id = projekt.vorgang_id if projekt is not None else None
    mehrere = bool(vorgang_id) and len(objekte_fuer(session, vorgang_id)) > 1
    # Hauptobjekt: die Kundenfelder sind der Master (A-AT-1) – so stimmt die Adresse auch,
    # wenn der Kunde ohne hauptobjekt_sync geändert wurde (Import, Alt-Code, Tests)
    if objekt is not None and objekt.reihenfolge == 1:
        if kunde is None:
            v = session.get(Vorgang, objekt.vorgang_id)
            kunde = session.get(Kunde, v.kunde_id) if v is not None and v.kunde_id else None
        if kunde is not None and (kunde.strasse or kunde.ort):
            return _ort_dict(kunde.strasse, kunde.plz, kunde.ort,
                             objekt.bezeichnung if mehrere else "", objekt.id, mehrere)
    if objekt is not None and (objekt.strasse or objekt.ort):
        return _ort_dict(objekt.strasse, objekt.plz, objekt.ort, objekt.bezeichnung, objekt.id, mehrere)
    if objekt is None and vorgang_id:
        haupt = hauptobjekt(session, vorgang_id)
        if haupt is not None and (haupt.strasse or haupt.ort):
            return _ort_dict(haupt.strasse, haupt.plz, haupt.ort, haupt.bezeichnung if mehrere else "",
                             haupt.id, mehrere)
    if kunde is None:
        kunde_id = None
        for quelle in (angebot, erfassung, vorgang):
            if quelle is not None and getattr(quelle, "kunde_id", None):
                kunde_id = quelle.kunde_id
                break
        if kunde_id is None and gewerk is not None:
            from app.models import Projekt
            projekt = session.get(Projekt, gewerk.projekt_id)
            kunde_id = projekt.kunde_id if projekt is not None else None
        kunde = session.get(Kunde, kunde_id) if kunde_id else None
    if kunde is not None:
        return _ort_dict(kunde.strasse, kunde.plz, kunde.ort, "", objekt.id if objekt else None, mehrere)
    return _ort_dict("", "", "")


def objekt_text(objekt: VorgangObjekt | None, mit_bezeichnung: bool = True) -> str:
    if objekt is None:
        return ""
    adresse = ", ".join(t for t in (objekt.strasse, " ".join(x for x in (objekt.plz, objekt.ort) if x)) if t)
    if mit_bezeichnung and objekt.bezeichnung:
        return f"{objekt.bezeichnung}: {adresse}" if adresse else objekt.bezeichnung
    return adresse


def objekte_loeschen(session: Session, vorgang_id: int) -> int:
    """Alle Objekte eines Vorgangs entfernen – vor jeder Vorgangs-Löschung aufrufen
    (Löschlauf, Duplikat-Bereinigung, Tests), damit keine verwaisten Objekte bleiben."""
    return (session.query(VorgangObjekt).filter(VorgangObjekt.vorgang_id == vorgang_id)
            .delete(synchronize_session=False))


def migration_v31_objekte(session: Session) -> list[str]:
    """Je Vorgang ein Hauptobjekt aus der Kundenadresse; objekt_id an Terminen,
    Erfassungen, Angeboten und Gewerken auf das Hauptobjekt des Vorgangs setzen.
    Idempotent: nur Vorgänge ohne Objekt bzw. Zeilen ohne objekt_id."""
    meldungen: list[str] = []
    # Verwaiste Objekte (Vorgang gelöscht, SQLite vergibt die ID neu – ein neuer Vorgang
    # würde sonst fremde Objekte „erben“; Befund Agent AT 13.10.2026)
    verwaist = (session.query(VorgangObjekt)
                .filter(~VorgangObjekt.vorgang_id.in_(session.query(Vorgang.id)))
                .delete(synchronize_session=False))
    if verwaist:
        meldungen.append(f"v31: {verwaist} verwaiste Objekte ohne Vorgang entfernt")
    # Trigger: Objekte eines gelöschten Vorgangs mitlöschen – greift für ORM-, Bulk- und
    # SQL-Löschungen (Löschlauf, Duplikat-Bereinigung, Tests) und ist additiv (v30-Code
    # läuft unverändert weiter)
    from sqlalchemy import text as _text
    trigger = session.execute(_text(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name='trg_v31_vorgang_objekte'"
    )).fetchone()
    if trigger is None:
        session.execute(_text(
            "CREATE TRIGGER IF NOT EXISTS trg_v31_vorgang_objekte AFTER DELETE ON vorgaenge "
            "BEGIN DELETE FROM vorgang_objekte WHERE vorgang_id = OLD.id; END"))
        meldungen.append("v31: Trigger trg_v31_vorgang_objekte angelegt "
                         "(Objekte werden mit dem Vorgang gelöscht)")
    vorhanden = {v for (v,) in session.query(VorgangObjekt.vorgang_id).distinct()}
    neu = 0
    for vorgang, kunde in (session.query(Vorgang, Kunde)
                           .outerjoin(Kunde, Kunde.id == Vorgang.kunde_id)
                           .order_by(Vorgang.id)):
        if vorgang.id in vorhanden:
            continue
        hauptobjekt_anlegen(session, vorgang, kunde)
        neu += 1
    if neu:
        meldungen.append(f"v31: {neu} Hauptobjekt(e) aus der Kundenadresse angelegt (vorgang_objekte)")
    haupt_je_vorgang = {}
    for o in session.query(VorgangObjekt).filter(VorgangObjekt.reihenfolge == 1):
        haupt_je_vorgang[o.vorgang_id] = o.id
    zaehler = {"Termine": 0, "Erfassungen": 0, "Angebote": 0, "Gewerke": 0}
    for t in session.query(VotTermin).filter(VotTermin.objekt_id.is_(None)):
        if t.vorgang_id in haupt_je_vorgang:
            t.objekt_id = haupt_je_vorgang[t.vorgang_id]
            zaehler["Termine"] += 1
    for e in session.query(Erfassung).filter(Erfassung.objekt_id.is_(None), Erfassung.vorgang_id.isnot(None)):
        if e.vorgang_id in haupt_je_vorgang:
            e.objekt_id = haupt_je_vorgang[e.vorgang_id]
            zaehler["Erfassungen"] += 1
    for a in session.query(Angebot).filter(Angebot.objekt_id.is_(None), Angebot.vorgang_id.isnot(None)):
        if a.vorgang_id in haupt_je_vorgang:
            a.objekt_id = haupt_je_vorgang[a.vorgang_id]
            zaehler["Angebote"] += 1
    from app.models import Projekt
    for g, p in (session.query(Gewerk, Projekt).join(Projekt, Projekt.id == Gewerk.projekt_id)
                 .filter(Gewerk.objekt_id.is_(None))):
        if p.vorgang_id in haupt_je_vorgang:
            g.objekt_id = haupt_je_vorgang[p.vorgang_id]
            zaehler["Gewerke"] += 1
    gesamt = sum(zaehler.values())
    if gesamt:
        meldungen.append("v31: objekt_id auf das Hauptobjekt gesetzt – "
                         + ", ".join(f"{n} {k}" for k, n in zaehler.items() if n))
    session.flush()
    return meldungen
