# Projektierung V1 (v11): Router des Moduls – Phase 66: „Angebot → Projekt"
# (Dialog + Anlage + Versionsfolge + Storno), Phase 67: Projektakte,
# Phase 68: Kanban/Liste/Termine/Meine Aufgaben. Alle Routen laufen durch das
# Demo-Gate (freigabe_modus, Phase 70): Standard = nur Admin.

import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import projektierung as kern
from app import projektierung_logik
from app.db import get_session
from app.models import (Angebot, Aufgabe, AufgabenpaketInstanz, Benutzer,
                        Gewerk, Kunde, Lead, Projekt, ProjektDokument,
                        ProjektSub, ProjektTermin, ProjektVerlauf,
                        Subunternehmer, Team, Vorgang,
                        GEWERK_PHASEN, GEWERK_PHASEN_AKTIV, GEWERK_PHASEN_NAMEN,
                        AUFGABE_STATUS_NAMEN)
from app.templating import render, templates

router = APIRouter(prefix="/projektierung")

# Rollen, die Projekte anlegen/bearbeiten dürfen (nach Freischaltung)
_SCHREIB_ROLLEN = ("admin", "innendienst", "projektierung")


def _gate(request: Request, session: Session, schreiben: bool = False):
    """Server-seitiges Modul-Gate (Phase 70): im Demo-Modus nur Admin;
    nach Freischaltung die Rollentabelle. None = Zugriff erlaubt."""
    benutzer = request.state.benutzer
    if benutzer is None or not kern.modul_sichtbar(session, benutzer):
        return RedirectResponse("/", status_code=303)
    if schreiben and not any(benutzer.hat_rolle(r) for r in _SCHREIB_ROLLEN):
        return RedirectResponse("/", status_code=303)
    return None


def _benutzer_mit_rolle(session: Session, rolle: str) -> list[Benutzer]:
    """Dropdown-Kandidaten: Benutzer mit der Zusatz-/Hauptrolle, sonst Büro."""
    alle = session.query(Benutzer).filter(Benutzer.aktiv.is_(True)).all()
    treffer = [b for b in alle if b.hat_rolle(rolle)]
    return sorted(treffer or [b for b in alle
                              if b.rolle in ("admin", "innendienst")],
                  key=lambda b: b.name)


# --- V4 (Phase 90.5): Aktionen ohne Seitensprung (fetch + JSON) ------------------

def _json_gewuenscht(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "")


LINK_PARAMETER = ("url_bza_portal", "url_spotmyenergy", "url_heizreport",
                  "url_kfw_zuschussportal")


def _naechste_phase(phase: str) -> str:
    folge = GEWERK_PHASEN_AKTIV + ["abgeschlossen"]
    if phase == "abnahme_freigabe":
        phase = "abnahme"
    if phase in folge and folge.index(phase) + 1 < len(folge):
        return folge[folge.index(phase) + 1]
    return ""


def _waechter_hinweis(session: Session, gewerk: Gewerk) -> str:
    """Hinweis unter der Ampel: Wächter zur nächsten Phase erfüllt?"""
    ziel = _naechste_phase(gewerk.phase)
    if not ziel or ziel == "abgeschlossen":
        return ""
    if kern.waechter_pruefen(session, gewerk, ziel):
        return ""
    return (f"✓ Wächter für „{GEWERK_PHASEN_NAMEN.get(ziel, ziel)}“ erfüllt – "
            "Phase kann gewechselt werden.")


def _aufgabe_kontext(session: Session, aufgabe: Aufgabe) -> dict:
    gewerk = session.get(Gewerk, aufgabe.gewerk_id) if aufgabe.gewerk_id else None
    kommentare = (session.query(ProjektVerlauf)
                  .filter(ProjektVerlauf.aufgabe_id == aufgabe.id,
                          ProjektVerlauf.art == "kommentar").count())
    return {
        "g": gewerk, "projekt": session.get(Projekt, aufgabe.projekt_id),
        "benutzer_map": {b.id: b for b in session.query(Benutzer)},
        "status_namen": AUFGABE_STATUS_NAMEN, "heute": datetime.now(),
        "kommentar_zaehler": {aufgabe.id: kommentare} if kommentare else {},
        "link_parameter": {k: kern.parameter_holen(session, k, "")
                           for k in LINK_PARAMETER},
        "steckbrief_werte": (kern.steckbrief_daten(session, [gewerk.id])[gewerk.id]
                             if gewerk is not None else {}),
    }


def _aufgabe_zeile_html(session: Session, aufgabe: Aufgabe) -> str:
    kontext = _aufgabe_kontext(session, aufgabe)
    kontext["a"] = aufgabe
    kontext.update(_bza_kontext(session, kontext["g"]) if kontext["g"] else {})
    return templates.get_template("projektierung/_aufgabe.html").render(kontext)


def _bza_kontext(session: Session, gewerk: Gewerk) -> dict:
    """Platzhalter – ab Phase 92 BzA-Daten je Gewerk."""
    return {}


def _aufgabe_json(request: Request, session: Session, aufgabe: Aufgabe,
                  meldung: str = ""):
    """JSON-Antwort für fetch: neue Zeile(n), Paket-Zähler, Planungs-Ampel,
    Wächter-Hinweis. Alle Aufgaben desselben Pakets werden mitgeliefert
    (abhängige Schritte können sich mitändern)."""
    from fastapi.responses import JSONResponse
    gewerk = session.get(Gewerk, aufgabe.gewerk_id) if aufgabe.gewerk_id else None
    weitere = []
    pakete = []
    if aufgabe.paket_instanz_id:
        gruppe = (session.query(Aufgabe)
                  .filter(Aufgabe.paket_instanz_id == aufgabe.paket_instanz_id)
                  .order_by(Aufgabe.reihenfolge, Aufgabe.id).all())
        erledigt = sum(1 for a in gruppe if a.status == "erledigt")
        pakete.append({"instanz_id": aufgabe.paket_instanz_id,
                       "text": ("alle erledigt" if erledigt == len(gruppe)
                                else f"{erledigt} / {len(gruppe)}")})
        weitere = [{"aufgabe_id": a.id, "zeile_html": _aufgabe_zeile_html(session, a)}
                   for a in gruppe if a.id != aufgabe.id]
    daten = {"ok": True, "aufgabe_id": aufgabe.id,
             "zeile_html": _aufgabe_zeile_html(session, aufgabe),
             "pakete": pakete, "weitere": weitere, "meldung": meldung}
    if gewerk is not None:
        daten["gewerk_id"] = gewerk.id
        daten["ampel_html"] = templates.get_template(
            "projektierung/_planungsampel.html").render(
                ampel=kern.planungs_ampel(session, gewerk))
        daten["waechter"] = _waechter_hinweis(session, gewerk)
    return JSONResponse(daten)


def _meldung_json(meldung: str, ok: bool = True, **zusatz):
    from fastapi.responses import JSONResponse
    return JSONResponse({"ok": ok, "meldung": meldung, **zusatz})


# --- Phase 68: Kanban · Liste · Termine · Meine Aufgaben -------------------------

def _gewerk_zeilen(session: Session, benutzer, sparte: str = "",
                   projektleiter_id: int = 0, team_id: int = 0,
                   kanal: str = "", plz: str = "", q: str = "",
                   storniert: bool = False,
                   terminstatus: str = "", vorlauf: str = "") -> list[dict]:
    """Gefilterte Gewerk-Zeilen (Basis für Kanban, Liste, Kacheln): je Gewerk
    Projekt, Kunde, Ampel, nächster Termin, offene/überfällige Aufgaben."""
    projekte = {p.id: p for p in session.query(Projekt)}
    kunden = {k.id: k for k in session.query(Kunde)}
    jetzt = datetime.now()
    termine_je_gewerk: dict[int, datetime] = {}
    teams_je_gewerk: dict[int, set[int]] = {}
    for t in (session.query(ProjektTermin)
              .filter(ProjektTermin.beginn.isnot(None))
              .order_by(ProjektTermin.beginn)):
        if t.gewerk_id and t.beginn >= jetzt and t.gewerk_id not in termine_je_gewerk:
            termine_je_gewerk[t.gewerk_id] = t.beginn
        if t.gewerk_id and t.team_id:
            teams_je_gewerk.setdefault(t.gewerk_id, set()).add(t.team_id)
    offene_je_gewerk: dict[int, int] = {}
    ueberfaellig_je_gewerk: dict[int, int] = {}
    pflicht_je_gewerk: dict[int, list] = {}
    for a in session.query(Aufgabe).filter(Aufgabe.status != "entfaellt"):
        if not a.gewerk_id:
            continue
        if a.status != "erledigt":
            offene_je_gewerk[a.gewerk_id] = offene_je_gewerk.get(a.gewerk_id, 0) + 1
            if a.faellig_am is not None and a.faellig_am < jetzt:
                ueberfaellig_je_gewerk[a.gewerk_id] = (
                    ueberfaellig_je_gewerk.get(a.gewerk_id, 0) + 1)
        if a.pflicht:
            pflicht_je_gewerk.setdefault(a.gewerk_id, []).append(a)
    zeilen = []
    for g in session.query(Gewerk).order_by(Gewerk.id):
        projekt = projekte.get(g.projekt_id)
        if projekt is None:
            continue
        if not storniert and g.phase == "storniert":
            continue
        if sparte and g.sparte != sparte:
            continue
        if projektleiter_id and projekt.projektleiter_id != projektleiter_id:
            continue
        if team_id and team_id not in teams_je_gewerk.get(g.id, set()):
            continue
        if kanal and (projekt.kanal or "") != kanal:
            continue
        if plz and not (projekt.ausfuehrung_plz or "").startswith(plz):
            continue
        kunde = kunden.get(projekt.kunde_id)
        if q:
            suchwort = q.lower()
            if not (suchwort in projekt.nummer.lower()
                    or (kunde is not None
                        and suchwort in kunde.anzeige_name.lower())):
                continue
        pflicht = pflicht_je_gewerk.get(g.id, [])
        erledigt = sum(1 for a in pflicht if a.status == "erledigt")
        ueberfaellig = ueberfaellig_je_gewerk.get(g.id, 0)
        farbe = ("gruen" if pflicht and erledigt == len(pflicht)
                 else ("rot" if ueberfaellig else "gelb"))
        if not pflicht:
            farbe = "gruen"
        zeilen.append({
            "gewerk": g, "projekt": projekt, "kunde": kunde,
            "ampel": {"farbe": farbe, "erledigt": erledigt,
                      "gesamt": len(pflicht), "ueberfaellig": ueberfaellig},
            "naechster_termin": termine_je_gewerk.get(g.id),
            "offen": offene_je_gewerk.get(g.id, 0),
            "ueberfaellig": ueberfaellig,
        })
    # v15 (Phase 74): Terminstatus je Gewerk berechnen + optional filtern
    ts_map = kern.terminstatus_map(session, [z["gewerk"].id for z in zeilen])
    for z in zeilen:
        z["terminstatus"] = ts_map.get(z["gewerk"].id,
                                       {"status": "unterminiert", "termin": None})
    if terminstatus:
        zeilen = [z for z in zeilen
                  if z["terminstatus"]["status"] == terminstatus]
    # V4 (Phase 90.3): Vorlauf-Ampel je Gewerk (+ Filter grün/gelb/rot)
    schwellen = kern.vorlauf_schwellen(session)
    for z in zeilen:
        z["vorlauf"] = kern.vorlauf_ampel(session, z["gewerk"], z["terminstatus"],
                                          schwellen=schwellen, heute=jetzt)
    if vorlauf in ("gruen", "gelb", "rot"):
        zeilen = [z for z in zeilen if z["vorlauf"]["farbe"] == vorlauf]
    return zeilen


def _filter_werte(session: Session) -> dict:
    projekte = session.query(Projekt).all()
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    return {
        "benutzer_map": benutzer_map,
        "projektleiter_werte": sorted(
            {p.projektleiter_id for p in projekte if p.projektleiter_id},
            key=lambda i: benutzer_map[i].name if i in benutzer_map else ""),
        "kanal_werte": sorted({p.kanal for p in projekte if p.kanal}),
        "teams": (session.query(Team).filter(Team.aktiv.is_(True))
                  .order_by(Team.name).all()),
    }


@router.get("")
async def kanban(request: Request, sparte: str = "", projektleiter_id: int = 0,
                 team_id: int = 0, kanal: str = "", plz: str = "", q: str = "",
                 storniert: int = 0, terminstatus: str = "", vorlauf: str = "",
                 session: Session = Depends(get_session)):
    """Kanban (Phase 68): Karte = Projekt in der Spalte seines abgeleiteten
    Status; der Sparten-Filter schaltet auf Karte-je-Gewerk um."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    zeilen = _gewerk_zeilen(session, request.state.benutzer, sparte=sparte,
                            terminstatus=terminstatus, vorlauf=vorlauf,
                            projektleiter_id=projektleiter_id, team_id=team_id,
                            kanal=kanal, plz=plz, q=q,
                            storniert=bool(storniert))
    karte_je_gewerk = bool(sparte)
    spalten: dict[str, list] = {p: [] for p in GEWERK_PHASEN_AKTIV}
    spalten["abgeschlossen"] = []
    grenze_30 = datetime.now() - timedelta(days=30)
    if karte_je_gewerk:
        for zeile in zeilen:
            phase = zeile["gewerk"].phase
            if phase == "storniert":
                phase = zeile["projekt"].status_cache
                if bool(storniert):
                    spalten.setdefault("storniert", []).append(
                        {"projekt": zeile["projekt"], "zeilen": [zeile]})
                    continue
            if phase == "abgeschlossen" and (
                    zeile["gewerk"].phase_geaendert_am or datetime.now()) < grenze_30:
                continue
            spalten.setdefault(phase, []).append(
                {"projekt": zeile["projekt"], "zeilen": [zeile]})
    else:
        karten: dict[int, dict] = {}
        for zeile in zeilen:
            karte = karten.setdefault(zeile["projekt"].id,
                                      {"projekt": zeile["projekt"], "zeilen": []})
            karte["zeilen"].append(zeile)
        for karte in karten.values():
            status = karte["projekt"].status_cache
            if status == "abgeschlossen" and (
                    karte["projekt"].abgeschlossen_am or datetime.now()) < grenze_30:
                continue
            spalten.setdefault(status if status in spalten else "auftragseingang",
                               []).append(karte)
    # V4 (Phase 90.1): bestimmendes Gewerk je Karte (Phase = Spalte), Spalten
    # chronologisch nach Montagebeginn, Unterminierte unten; Auftragseingang
    # zweigeteilt in unterminiert | terminiert
    for phase, karten in spalten.items():
        for karte in karten:
            passende = [z for z in karte["zeilen"] if z["gewerk"].phase == phase]
            offene = [z for z in karte["zeilen"]
                      if z["gewerk"].phase not in ("abgeschlossen", "storniert")]
            karte["bestimmend"] = (passende or offene or karte["zeilen"])[0]
        karten.sort(key=lambda k: kern.sortierschluessel_chrono(k["bestimmend"]))
    ae = spalten.pop("auftragseingang", [])
    neu_spalten: dict[str, list] = {
        "auftragseingang_unterminiert": [
            k for k in ae
            if k["bestimmend"]["terminstatus"]["status"] == "unterminiert"],
        "auftragseingang_terminiert": [
            k for k in ae
            if k["bestimmend"]["terminstatus"]["status"] != "unterminiert"],
    }
    neu_spalten.update(spalten)
    spalten = neu_spalten
    spalten_namen = dict(GEWERK_PHASEN_NAMEN)
    spalten_namen["auftragseingang_unterminiert"] = "Auftragseingang · unterminiert"
    spalten_namen["auftragseingang_terminiert"] = "Auftragseingang · terminiert"
    from datetime import timedelta as _td
    return render(request, "projektierung/kanban.html", aktiv="/projektierung",
                  spalten=spalten, phasen_namen=spalten_namen,
                  vorlauf=vorlauf,
                  vorlauf_phasen=kern.VORLAUF_PHASEN,
                  karte_je_gewerk=karte_je_gewerk,
                  # v11b (Phase 73, nur Anzeige): Kachelzeile über dem Board
                  kacheln=kern.startseiten_kacheln(session),
                  sparte=sparte, projektleiter_id=projektleiter_id,
                  team_id=team_id, kanal=kanal, plz=plz, q=q,
                  storniert=bool(storniert), heute=datetime.now(),
                  terminstatus=terminstatus,
                  teams_map={te.id: te for te in session.query(Team)},
                  benutzer=request.state.benutzer,
                  **_filter_werte(session),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/gewerk/{gewerk_id}/feinplanung-erfasst")
async def feinplanung_erfasst(request: Request, gewerk_id: int,
                              session: Session = Depends(get_session)):
    """v15 (Phase 74): Häkchen „Feinplanung erfasst“ am Gewerk – Wächter
    Feinplanung VOT → Planung, bis die Feinplanungs-Erfassung (Phase 80)
    kommt. Toggle mit Verlaufseintrag."""
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()
    neu_wert = form.get("erfasst") == "1"
    if neu_wert != bool(gewerk.feinplanung_erfasst):
        gewerk.feinplanung_erfasst = neu_wert
        gewerk.feinplanung_erfasst_am = datetime.now() if neu_wert else None
        kern.verlauf(session, gewerk.projekt_id,
                     ("Feinplanung erfasst (Häkchen gesetzt)" if neu_wert
                      else "Häkchen „Feinplanung erfasst“ entfernt")
                     + f" – Gewerk {gewerk.sparte}",
                     benutzer=request.state.benutzer, gewerk_id=gewerk.id)
        session.commit()
    return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}",
                            status_code=303)


@router.post("/gewerk/{gewerk_id}/phase-drop")
async def phase_drop(request: Request, gewerk_id: int,
                     session: Session = Depends(get_session)):
    """Drag & Drop vom Board: wie Phasenwechsel, mit optionaler Begründung
    (der Wächter-Hinweis erscheint als Meldung über dem Board)."""
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()
    ziel = form.get("phase") or ""
    # V4 (Phase 90.1): die beiden Auftragseingangs-Spalten sind EINE Phase
    if ziel.startswith("auftragseingang_"):
        ziel = "auftragseingang"
    ok, meldung = kern.phase_wechseln(session, gewerk, ziel,
                                      form.get("begruendung") or "",
                                      benutzer=request.state.benutzer)
    if ok:
        session.commit()
    else:
        session.rollback()
        meldung += " – Override mit Begründung in der Projektakte."
    return RedirectResponse("/projektierung?meldung=" + quote_plus(meldung),
                            status_code=303)


@router.get("/liste")
async def liste(request: Request, sparte: str = "", projektleiter_id: int = 0,
                team_id: int = 0, kanal: str = "", plz: str = "", q: str = "",
                storniert: int = 0, sortierung: str = "chrono",
                export: str = "", terminstatus: str = "", vorlauf: str = "",
                session: Session = Depends(get_session)):
    """Gewerke als Tabelle (Phase 68) mit Summenzeile und CSV-Export."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    zeilen = _gewerk_zeilen(session, request.state.benutzer, sparte=sparte,
                            terminstatus=terminstatus, vorlauf=vorlauf,
                            projektleiter_id=projektleiter_id, team_id=team_id,
                            kanal=kanal, plz=plz, q=q, storniert=bool(storniert))
    if sortierung == "vorlauf":
        # V4 (Phase 90.3): Vorlauf aufsteigend (knapp zuerst), ohne Ampel unten
        zeilen.sort(key=lambda z: (z["vorlauf"]["farbe"] is None,
                                   z["vorlauf"]["wochen"] is not None,
                                   z["vorlauf"]["wochen"] or 0))
    elif sortierung == "projekt":
        zeilen.sort(key=lambda z: z["projekt"].nummer, reverse=True)
    elif sortierung == "kunde":
        zeilen.sort(key=lambda z: (z["kunde"].anzeige_name.lower()
                                   if z["kunde"] else "zzz"))
    elif sortierung == "phase":
        zeilen.sort(key=lambda z: GEWERK_PHASEN.index(z["gewerk"].phase))
    elif sortierung == "termin":
        zeilen.sort(key=lambda z: z["naechster_termin"] or datetime.max)
    elif sortierung == "wert":
        zeilen.sort(key=lambda z: -z["gewerk"].auftragswert_aktuell)
    else:
        # V4 (Phase 90.1): Standard chronologisch nach Montagebeginn,
        # Unterminierte unten nach Auftragsdatum
        sortierung = "chrono"
        zeilen.sort(key=kern.sortierschluessel_chrono)
    angebote = {a.id: a for a in session.query(Angebot)
                .filter(Angebot.id.in_([z["gewerk"].angebot_id for z in zeilen
                                        if z["gewerk"].angebot_id] or [0]))}
    summe = sum(z["gewerk"].auftragswert_aktuell for z in zeilen
                if z["gewerk"].phase != "storniert")
    if export == "csv":
        import csv
        import io
        from fastapi.responses import Response
        puffer = io.StringIO()
        schreiber = csv.writer(puffer, delimiter=";")
        schreiber.writerow(["PR-Nr.", "Kunde", "Ort", "Sparte", "Phase",
                            "Ampel", "Vorlauf", "Projektleiter", "Nächster Termin",
                            "Auftragswert (EUR)", "Überfällig", "Kanal",
                            "Angebotsnummer"])
        filter_werte = _filter_werte(session)
        for z in zeilen:
            angebot = angebote.get(z["gewerk"].angebot_id)
            pl = filter_werte["benutzer_map"].get(z["projekt"].projektleiter_id)
            schreiber.writerow([
                z["projekt"].nummer,
                z["kunde"].anzeige_name if z["kunde"] else "",
                z["projekt"].ausfuehrung_ort,
                z["gewerk"].sparte,
                GEWERK_PHASEN_NAMEN.get(z["gewerk"].phase, z["gewerk"].phase),
                z["ampel"]["farbe"],
                z["vorlauf"]["farbe"] or "",
                pl.name if pl else "",
                z["naechster_termin"].strftime("%d.%m.%Y %H:%M")
                if z["naechster_termin"] else "",
                f"{z['gewerk'].auftragswert_aktuell / 100:.2f}".replace(".", ","),
                z["ueberfaellig"],
                z["projekt"].kanal,
                (angebot.taifun_nummer or angebot.nummer) if angebot else "",
            ])
        return Response(puffer.getvalue().encode("utf-8-sig"),
                        media_type="text/csv",
                        headers={"Content-Disposition":
                                 'attachment; filename="projektierung.csv"'})
    return render(request, "projektierung/liste.html", aktiv="/projektierung",
                  zeilen=zeilen, angebote=angebote, summe=summe,
                  phasen_namen=GEWERK_PHASEN_NAMEN, sortierung=sortierung,
                  terminstatus=terminstatus, vorlauf=vorlauf,
                  teams_map={te.id: te for te in session.query(Team)},
                  sparte=sparte, projektleiter_id=projektleiter_id,
                  team_id=team_id, kanal=kanal, plz=plz, q=q,
                  storniert=bool(storniert), heute=datetime.now(),
                  benutzer=request.state.benutzer,
                  **_filter_werte(session),
                  meldung=request.query_params.get("meldung", ""))


@router.get("/termine")
async def termine(request: Request, ansicht: str = "woche", start: str = "",
                  team_id: int = 0, person_id: int = 0, typ: str = "",
                  session: Session = Depends(get_session)):
    """Terminübersicht (Phase 68): Wochen-/Monatsansicht, Filter Team/Person/Typ."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    from datetime import date, timedelta as _td
    try:
        start_datum = datetime.strptime(start, "%Y-%m-%d").date() if start else date.today()
    except ValueError:
        start_datum = date.today()
    if ansicht == "monat":
        von = start_datum.replace(day=1)
        bis = (von.replace(month=von.month + 1, day=1) if von.month < 12
               else von.replace(year=von.year + 1, month=1, day=1))
    else:
        ansicht = "woche"
        von = start_datum - _td(days=start_datum.weekday())
        bis = von + _td(days=7)
    abfrage = (session.query(ProjektTermin)
               .filter(ProjektTermin.beginn.isnot(None),
                       ProjektTermin.beginn >= datetime.combine(von, datetime.min.time()),
                       ProjektTermin.beginn < datetime.combine(bis, datetime.min.time())))
    if team_id:
        abfrage = abfrage.filter(ProjektTermin.team_id == team_id)
    if person_id:
        abfrage = abfrage.filter(ProjektTermin.person_id == person_id)
    if typ:
        abfrage = abfrage.filter(ProjektTermin.typ == typ)
    termine_liste = abfrage.order_by(ProjektTermin.beginn).all()
    tage: dict = {}
    for t in termine_liste:
        tage.setdefault(t.beginn.date(), []).append(t)
    projekte = {p.id: p for p in session.query(Projekt)}
    gewerke = {g.id: g for g in session.query(Gewerk)}
    kunden = {k.id: k for k in session.query(Kunde)}
    subs = {su.id: su for su in session.query(Subunternehmer)}
    alle_gewerke = [(g, projekte.get(g.projekt_id), kunden.get(
        projekte[g.projekt_id].kunde_id) if g.projekt_id in projekte else None)
        for g in gewerke.values()
        if g.phase not in ("abgeschlossen", "storniert")]
    return render(request, "projektierung/termine.html", aktiv="/projektierung",
                  tage=sorted(tage.items()), von=von, bis=bis, ansicht=ansicht,
                  team_id=team_id, person_id=person_id, typ=typ,
                  projekte=projekte, gewerke=gewerke, kunden=kunden, subs=subs,
                  alle_gewerke=sorted(alle_gewerke,
                                      key=lambda e: e[1].nummer if e[1] else ""),
                  vor=(von + (_td(days=7) if ansicht == "woche" else _td(days=32))
                       ).strftime("%Y-%m-%d"),
                  zurueck=(von - (_td(days=7) if ansicht == "woche" else _td(days=1))
                           ).strftime("%Y-%m-%d"),
                  benutzer=request.state.benutzer,
                  **_filter_werte(session),
                  meldung=request.query_params.get("meldung", ""))


@router.get("/meine-aufgaben")
async def meine_aufgaben(request: Request, ueberfaellig: int = 0,
                         session: Session = Depends(get_session)):
    """„Meine Aufgaben" (Phase 68): Überfällig · Heute · Diese Woche ·
    Später · Neu zugewiesen (7 Tage)."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    benutzer = request.state.benutzer
    from datetime import timedelta as _td
    jetzt = datetime.now()
    heute_ende = jetzt.replace(hour=23, minute=59, second=59)
    woche_ende = heute_ende + _td(days=6 - jetzt.weekday())
    aufgaben = (session.query(Aufgabe)
                .filter(Aufgabe.verantwortlich_id == benutzer.id,
                        Aufgabe.status.in_(["offen", "in_arbeit", "wartet"]))
                .order_by(Aufgabe.faellig_am.isnot(None).desc(),
                          Aufgabe.faellig_am).all())
    gruppen = {"ueberfaellig": [], "heute": [], "woche": [], "spaeter": []}
    for a in aufgaben:
        if a.faellig_am is not None and a.faellig_am < jetzt:
            gruppen["ueberfaellig"].append(a)
        elif a.faellig_am is not None and a.faellig_am <= heute_ende:
            gruppen["heute"].append(a)
        elif a.faellig_am is not None and a.faellig_am <= woche_ende:
            gruppen["woche"].append(a)
        else:
            gruppen["spaeter"].append(a)
    neu_zugewiesen = [a for a in aufgaben
                      if a.erstellt_am and a.erstellt_am >= jetzt - _td(days=7)]
    projekte = {p.id: p for p in session.query(Projekt)}
    gewerke = {g.id: g for g in session.query(Gewerk)}
    kunden = {k.id: k for k in session.query(Kunde)}
    return render(request, "projektierung/meine_aufgaben.html",
                  aktiv="/projektierung", gruppen=gruppen,
                  neu_zugewiesen=neu_zugewiesen, projekte=projekte,
                  gewerke=gewerke, kunden=kunden, heute=jetzt,
                  status_namen=AUFGABE_STATUS_NAMEN,
                  benutzer=benutzer,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/termine")
async def termin_aus_uebersicht(request: Request,
                                session: Session = Depends(get_session)):
    """Termin-Dialog aus der Übersicht: Gewerk wählen, dann wie in der Akte."""
    if (umleitung := _gate(request, session, schreiben=True)) is not None:
        return umleitung
    form = await request.form()
    try:
        gewerk_id = int(form.get("gewerk_id") or 0)
    except ValueError:
        gewerk_id = 0
    if not gewerk_id:
        return RedirectResponse("/projektierung/termine?meldung="
                                + quote_plus("Bitte ein Gewerk wählen."),
                                status_code=303)
    return await termin_anlegen(request, gewerk_id, session)


# --- Phase 66: Angebot → Projekt ------------------------------------------------

@router.get("/angebot/{angebot_id}/projekt")
async def projekt_dialog(request: Request, angebot_id: int,
                         session: Session = Depends(get_session)):
    """Dialog „Angebot → Projekt": Kopf mit Kunde + Ausführungsadresse
    (editierbar), Vorschlag „zu offenem Projekt des Vorgangs hinzufügen",
    Sparten-Häkchen, Zuweisungen, Bemerkung."""
    if (umleitung := _gate(request, session, schreiben=True)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or angebot.status != "Angenommen":
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "„Angebot → Projekt“ geht nur bei angenommenen Angeboten."),
            status_code=303)
    if angebot.projekt_gewerk_id:
        gewerk = session.get(Gewerk, angebot.projekt_gewerk_id)
        if gewerk is not None:
            return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}",
                                    status_code=303)
    from app import vorgaenge as vorgaenge_modul
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    session.commit()
    kunde = session.get(Kunde, angebot.kunde_id)
    offenes = kern.offenes_projekt_fuer_vorgang(session, vorgang.id)
    # Sparten: Tool-Angebot = seine Sparte; TAIFUN = alle Lead-Interessen wählbar
    sparte = angebot.konfigurator_typ or "WP"
    waehlbar = [sparte]
    if angebot.extern and vorgang.lead_id:
        lead = session.get(Lead, vorgang.lead_id)
        if lead is not None and lead.interessen:
            waehlbar = sorted(set(lead.interessen) | {sparte},
                              key=["WP", "PV", "KL", "WB"].index)
    belegt = set()
    if offenes is not None:
        belegt = {g.sparte for g in session.query(Gewerk)
                  .filter(Gewerk.projekt_id == offenes.id,
                          Gewerk.phase != "storniert")}
    def standard(name):
        wert = kern.parameter_holen(session, name, "")
        return int(wert) if wert.isdigit() else 0
    return render(request, "projektierung/dialog.html", aktiv="/projektierung",
                  angebot=angebot, kunde=kunde, vorgang=vorgang,
                  offenes=offenes, belegt=belegt,
                  sparten_waehlbar=waehlbar, sparte_vorbelegt=sparte,
                  projektleiter=_benutzer_mit_rolle(session, "projektierung"),
                  standard_pl=standard("standard_projektleiter"),
                  standard_fp=standard("standard_feinplaner"),
                  standard_ep=standard("standard_elektroplaner"),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/angebot/{angebot_id}/projekt")
async def projekt_anlegen(request: Request, angebot_id: int,
                          session: Session = Depends(get_session)):
    if (umleitung := _gate(request, session, schreiben=True)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or angebot.status != "Angenommen" or angebot.projekt_gewerk_id:
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    benutzer = request.state.benutzer
    form = await request.form()
    sparten = [s for s in ("WP", "PV", "KL", "WB")
               if form.get(f"sparte_{s}") == "on"]
    if not sparten:
        return RedirectResponse(
            f"/projektierung/angebot/{angebot_id}/projekt?meldung="
            + quote_plus("Bitte mindestens eine Sparte wählen."), status_code=303)
    try:
        projektleiter_id = int(form.get("projektleiter_id") or 0) or None
    except ValueError:
        projektleiter_id = None
    if projektleiter_id is None:
        return RedirectResponse(
            f"/projektierung/angebot/{angebot_id}/projekt?meldung="
            + quote_plus("Bitte einen Projektleiter wählen (Pflicht)."),
            status_code=303)
    def _id(name):
        try:
            return int(form.get(name) or 0) or None
        except ValueError:
            return None
    from app import vorgaenge as vorgaenge_modul
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    projekt = None
    if form.get("projekt_wahl", "") == "vorhanden":
        projekt = kern.offenes_projekt_fuer_vorgang(session, vorgang.id)
    if projekt is None:
        kunde = session.get(Kunde, angebot.kunde_id)
        if kunde is None:
            return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
                "Angebot ohne Kunden – Projekt kann nicht angelegt werden."),
                status_code=303)
        projekt = kern.projekt_anlegen(
            session, angebot, benutzer=benutzer,
            projektleiter_id=projektleiter_id,
            notiz_kopf=form.get("notiz_kopf") or "",
            adresse={"strasse": (form.get("strasse") or "").strip()[:200],
                     "plz": (form.get("plz") or "").strip()[:10],
                     "ort": (form.get("ort") or "").strip()[:100]})
        kern.verlauf(session, projekt.id,
                     f"Projekt {projekt.nummer} angelegt", benutzer=benutzer)
    else:
        projekt.projektleiter_id = projektleiter_id
        if (form.get("notiz_kopf") or "").strip():
            projekt.notiz_kopf = (form.get("notiz_kopf") or "").strip()[:500]
    belegt = {g.sparte for g in session.query(Gewerk)
              .filter(Gewerk.projekt_id == projekt.id,
                      Gewerk.phase != "storniert")}
    angelegt = []
    for sparte in sparten:
        if sparte in belegt:
            continue
        kern.gewerk_anlegen(session, projekt, angebot, sparte,
                            benutzer=benutzer,
                            feinplaner_id=_id("feinplaner_id"),
                            elektroplaner_id=_id("elektroplaner_id"))
        angelegt.append(sparte)
    session.commit()
    if not angelegt:
        return RedirectResponse(
            f"/projektierung/projekt/{projekt.id}?meldung=" + quote_plus(
                "Keine neuen Gewerke – die gewählten Sparten existieren bereits."),
            status_code=303)
    return RedirectResponse(f"/projektierung/projekt/{projekt.id}?meldung="
                            + quote_plus(f"Projekt {projekt.nummer}: Gewerk"
                                         f"{'e' if len(angelegt) > 1 else ''} "
                                         f"{', '.join(angelegt)} angelegt."),
                            status_code=303)


@router.get("/projekt/{projekt_id}")
async def akte(request: Request, projekt_id: int,
               session: Session = Depends(get_session)):
    """Projektakte (Phase 66 Basis, Phase 67 Vollausbau)."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    projekt = session.get(Projekt, projekt_id)
    if projekt is None:
        return RedirectResponse("/projektierung", status_code=303)
    kunde = session.get(Kunde, projekt.kunde_id)
    gewerke = (session.query(Gewerk)
               .filter(Gewerk.projekt_id == projekt.id)
               .order_by(Gewerk.id).all())
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    angebote = {a.id: a for a in session.query(Angebot)
                .filter(Angebot.id.in_([g.angebot_id for g in gewerke
                                        if g.angebot_id] or [0]))}
    aufgaben_je_gewerk: dict[int, list[Aufgabe]] = {}
    for aufgabe in (session.query(Aufgabe)
                    .filter(Aufgabe.projekt_id == projekt.id)
                    .order_by(Aufgabe.reihenfolge, Aufgabe.id)):
        aufgaben_je_gewerk.setdefault(aufgabe.gewerk_id or 0, []).append(aufgabe)
    # Aufgaben je Gewerk nach Paket-Instanz gruppiert (None = Einzelaufgaben,
    # ans Ende) – vorgruppiert, weil Jinja-groupby None nicht sortieren kann
    # v15 (Phase 78): Galerie-Aufgaben automatisch abhaken (alle Ordner belegt)
    galerie_haekchen = sum(kern.galerie_haekchen_pruefen(session, g)
                           for g in gewerke)
    if galerie_haekchen:
        session.commit()
        aufgaben_je_gewerk = {}
        for aufgabe in (session.query(Aufgabe)
                        .filter(Aufgabe.projekt_id == projekt.id)
                        .order_by(Aufgabe.reihenfolge, Aufgabe.id)):
            aufgaben_je_gewerk.setdefault(aufgabe.gewerk_id or 0, []).append(aufgabe)
    instanzen = {i.id: i for i in session.query(AufgabenpaketInstanz)
                 .filter(AufgabenpaketInstanz.gewerk_id.in_(
                     [g.id for g in gewerke] or [0]))}
    # v15 (Phase 78): Reihenfolge = Boardspalten, V1-Pakete ans Ende
    phasen_rang = {ph: i for i, ph in enumerate(GEWERK_PHASEN)}
    aufgaben_gruppen: dict[int, list[tuple[int, list[Aufgabe]]]] = {}
    paket_offen: dict[tuple[int, int], bool] = {}
    for gewerk_id, liste in aufgaben_je_gewerk.items():
        gruppen: dict[int, list[Aufgabe]] = {}
        for aufgabe in liste:
            gruppen.setdefault(aufgabe.paket_instanz_id or 0, []).append(aufgabe)

        def _sortier(paar):
            iid = paar[0]
            instanz = instanzen.get(iid)
            if iid == 0 or instanz is None:
                return (2, 99, iid)          # Einzelaufgaben ans Ende
            ist_v1 = (instanz.version or "") == "v1"
            return (1 if ist_v1 else 0, kern.paket_rang(instanz.paket_name), iid)
        aufgaben_gruppen[gewerk_id] = sorted(gruppen.items(), key=_sortier)
        gewerk_obj = next((g for g in gewerke if g.id == gewerk_id), None)
        rang = phasen_rang.get(gewerk_obj.phase, 0) if gewerk_obj else 0
        for iid, gruppe in gruppen.items():
            alle_erledigt = all(a.status in ("erledigt", "entfaellt")
                                for a in gruppe)
            instanz = instanzen.get(iid)
            if iid == 0 or instanz is None:
                paket_offen[(gewerk_id, iid)] = any(
                    a.pflicht and a.status not in ("erledigt", "entfaellt")
                    for a in gruppe)
            else:
                paket_offen[(gewerk_id, iid)] = (
                    not alle_erledigt
                    and kern.paket_rang(instanz.paket_name) == rang
                    and (instanz.version or "") != "v1")
    termine = (session.query(ProjektTermin)
               .filter(ProjektTermin.projekt_id == projekt.id)
               .order_by(ProjektTermin.beginn).all())
    verlauf_eintraege = (session.query(ProjektVerlauf)
                         .filter(ProjektVerlauf.projekt_id == projekt.id)
                         .order_by(ProjektVerlauf.erstellt_am.desc(),
                                   ProjektVerlauf.id.desc()).limit(200).all())
    ampeln = {g.id: kern.planungs_ampel(session, g) for g in gewerke}
    logik = projektierung_logik.hole_logik(session)
    benutzer = request.state.benutzer
    ek_sichtbar = (benutzer.rolle in ("admin", "innendienst")
                   or benutzer.kalkulation_sichtbar)
    gesamtwert = sum(g.auftragswert_aktuell for g in gewerke
                     if g.phase != "storniert")
    # Dokumente (Ordnerbaum) + Ordner-Auswahl aus Vorlage und Sparten
    dokumente: dict[str, list] = {}
    for d in (session.query(ProjektDokument)
              .filter(ProjektDokument.projekt_id == projekt.id)
              .order_by(ProjektDokument.ordner, ProjektDokument.dateiname)):
        dokumente.setdefault(d.ordner, []).append(d)
    dokument_ordner: list[str] = []
    for eintrag in kern.ordnervorlage(session):
        pfad = str(eintrag.get("pfad", "")).strip()
        if not pfad:
            continue
        if eintrag.get("ebene") == "gewerk":
            for g in gewerke:
                wert = f"{g.sparte}/{pfad}"
                if wert not in dokument_ordner:
                    dokument_ordner.append(wert)
        elif pfad not in dokument_ordner:
            dokument_ordner.append(pfad)
    # Subs & Bestellungen (V1: Zuordnung, Mail ab V2)
    projekt_subs = []
    subs_map = {su.id: su for su in session.query(Subunternehmer)}
    for eintrag in (session.query(ProjektSub)
                    .filter(ProjektSub.projekt_id == projekt.id)
                    .order_by(ProjektSub.id)):
        projekt_subs.append({"eintrag": eintrag,
                             "sub": subs_map.get(eintrag.sub_id)})
    subs_stamm = (session.query(Subunternehmer)
                  .filter(Subunternehmer.aktiv.is_(True))
                  .order_by(Subunternehmer.firma).all())
    # Vorgangs-Notizen (Vertriebsphase, read-only) + Kommentar-Zähler je Aufgabe
    from app.models import VorgangsNotiz
    vorgang_notizen = []
    if projekt.vorgang_id:
        vorgang_notizen = (session.query(VorgangsNotiz)
                           .filter(VorgangsNotiz.vorgang_id == projekt.vorgang_id)
                           .order_by(VorgangsNotiz.zeit).all())
    kommentar_zaehler: dict[int, int] = {}
    for e in verlauf_eintraege:
        if e.aufgabe_id and e.art == "kommentar":
            kommentar_zaehler[e.aufgabe_id] = kommentar_zaehler.get(e.aufgabe_id, 0) + 1
    return render(request, "projektierung/akte.html", aktiv="/projektierung",
                  dokumente=dokumente, dokument_ordner=dokument_ordner,
                  # v15 (Phase 78): Aktionstypen, V1-Pakete, Restarbeiten
                  paket_offen=paket_offen,
                  v1_vorhanden={g.id: any(
                      (i.version or "") == "v1" and i.gewerk_id == g.id
                      for i in instanzen.values()) for g in gewerke},
                  link_parameter={k: kern.parameter_holen(session, k, "")
                                  for k in LINK_PARAMETER},
                  # V4 (Phase 90): Stepper ohne Endzustände, Vorlauf-Ampel,
                  # Wächter-Hinweis unter der Planungs-Ampel
                  phasen_aktiv=GEWERK_PHASEN_AKTIV,
                  vorlauf={g.id: kern.vorlauf_ampel(session, g) for g in gewerke},
                  waechter_hinweis={g.id: _waechter_hinweis(session, g)
                                    for g in gewerke},
                  restarbeiten=_restarbeiten_je_gewerk(session, gewerke),
                  # v15 (Phase 79): Mail-Verlauf des Projekts (Sub-Anfragen)
                  projekt_mails=(session.query(
                      __import__("app.models", fromlist=["x"]).ProjektMail)
                      .filter_by(projekt_id=projekt.id)
                      .order_by(__import__("app.models", fromlist=["x"])
                                .ProjektMail.id.desc()).limit(100).all()),
                  # v15 (Phase 77): Projektsteckbrief über den To-dos
                  steckbrief_daten=kern.steckbrief_daten(
                      session, [g.id for g in gewerke]),
                  steckbrief_felder=kern.steckbrief_felder,
                  # v15 (Phase 76): Galerie des Vorgangs in der Projektakte
                  # 27.09.2026 (Andreas): Galerie je Gewerk-Sparte
                  galerie_sparten=[sp for sp in ("WP", "PV", "KL", "WB")
                                   if any(g.sparte == sp for g in gewerke)]
                  or ["WP"],
                  galerie_daten={sp: __import__("app.galerie", fromlist=["x"])
                                 .uebersicht(session, projekt.vorgang_id or 0, sp)
                                 for sp in ("WP", "PV", "KL", "WB")
                                 if any(g.sparte == sp for g in gewerke)}
                  or {"WP": __import__("app.galerie", fromlist=["x"])
                      .uebersicht(session, projekt.vorgang_id or 0, "WP")},
                  galerie_ordner={sp: __import__("app.galerie", fromlist=["x"])
                                  .ordner_liste(session, sp)
                                  for sp in ("WP", "PV", "KL", "WB")},
                  galerie_darf_loeschen=__import__("app.galerie", fromlist=["x"])
                  .darf_loeschen(request.state.benutzer),
                  projekt_subs=projekt_subs, subs_stamm=subs_stamm,
                  vorgang_notizen=vorgang_notizen,
                  kommentar_zaehler=kommentar_zaehler,
                  projekt=projekt, kunde=kunde, gewerke=gewerke,
                  benutzer=benutzer, benutzer_map=benutzer_map,
                  angebote=angebote, aufgaben_je_gewerk=aufgaben_je_gewerk,
                  instanzen=instanzen, termine=termine,
                  aufgaben_gruppen=aufgaben_gruppen,
                  verlauf=verlauf_eintraege, ampeln=ampeln,
                  phasen=GEWERK_PHASEN, phasen_namen=GEWERK_PHASEN_NAMEN,
                  status_namen=AUFGABE_STATUS_NAMEN,
                  storno_gruende=kern.storno_gruende(session),
                  pakete_je_sparte={g.id: logik.pakete_fuer_sparte(g.sparte)
                                    for g in gewerke},
                  ek_sichtbar=ek_sichtbar, gesamtwert=gesamtwert,
                  heute=datetime.now(),
                  # v11b (Phase 73, nur Anzeige): Team-Namen für die Montage-
                  # Zeile im Datenraster des Prototyp-Layouts
                  teams_map={t.id: t for t in session.query(Team)},
                  # Bugfix 27.09.2026: das Team-Dropdown im Dialog
                  # „Team + Termin" war LEER – die Liste fehlte im Kontext,
                  # dadurch ließ sich kein Montageteam zuweisen
                  teams=(session.query(Team).filter(Team.aktiv.is_(True))
                         .order_by(Team.typ, Team.name).all()),
                  meldung=request.query_params.get("meldung", ""))


# --- Phase 67: Aktionen der Projektakte -----------------------------------------

def _gewerk_laden(request: Request, session: Session, gewerk_id: int):
    umleitung = _gate(request, session, schreiben=True)
    if umleitung is not None:
        return None, umleitung
    gewerk = session.get(Gewerk, gewerk_id)
    if gewerk is None:
        return None, RedirectResponse("/projektierung", status_code=303)
    return gewerk, None


@router.post("/projekt/{projekt_id}/projektleiter")
async def projektleiter_aendern(request: Request, projekt_id: int,
                                session: Session = Depends(get_session)):
    if (umleitung := _gate(request, session, schreiben=True)) is not None:
        return umleitung
    projekt = session.get(Projekt, projekt_id)
    if projekt is None:
        return RedirectResponse("/projektierung", status_code=303)
    form = await request.form()
    try:
        neu = int(form.get("projektleiter_id") or 0) or None
    except ValueError:
        neu = None
    if neu and neu != projekt.projektleiter_id:
        alt = projekt.projektleiter_id
        projekt.projektleiter_id = neu
        benutzer_map = {b.id: b for b in session.query(Benutzer)}
        kern.verlauf(session, projekt.id,
                     f"Projektleiter geändert: "
                     f"{benutzer_map[alt].name if alt in benutzer_map else '–'} → "
                     f"{benutzer_map[neu].name if neu in benutzer_map else '?'}",
                     benutzer=request.state.benutzer)
        kern.benachrichtigen(session, [neu],
                             f"Du bist jetzt Projektleiter von {projekt.nummer}",
                             f"/projektierung/projekt/{projekt.id}", art="gewerk")
        session.commit()
    return RedirectResponse(f"/projektierung/projekt/{projekt_id}", status_code=303)


@router.post("/gewerk/{gewerk_id}/zuweisung")
async def zuweisung(request: Request, gewerk_id: int,
                    session: Session = Depends(get_session)):
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()
    geaendert = []
    for feld, name in (("feinplaner_id", "Feinplaner"),
                       ("elektroplaner_id", "Elektroplaner")):
        try:
            neu = int(form.get(feld) or 0) or None
        except ValueError:
            continue
        if neu != getattr(gewerk, feld):
            setattr(gewerk, feld, neu)
            geaendert.append((name, neu))
    for name, neu in geaendert:
        kern.verlauf(session, gewerk.projekt_id,
                     f"{name} des Gewerks {gewerk.sparte} geändert",
                     benutzer=request.state.benutzer, gewerk_id=gewerk.id)
        if neu:
            projekt = session.get(Projekt, gewerk.projekt_id)
            kern.benachrichtigen(session, [neu],
                                 f"Du bist {name} im Projekt "
                                 f"{projekt.nummer if projekt else '?'} ({gewerk.sparte})",
                                 f"/projektierung/projekt/{gewerk.projekt_id}",
                                 art="gewerk")
    session.commit()
    if _json_gewuenscht(request):
        return _meldung_json("Zuweisung gespeichert.")
    return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}",
                            status_code=303)


@router.post("/gewerk/{gewerk_id}/heizlast")
async def heizlast(request: Request, gewerk_id: int,
                   session: Session = Depends(get_session)):
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    from app.konfigurator import zahl_parsen
    form = await request.form()
    kw = zahl_parsen((form.get("heizlast_kw") or "").strip())
    if kw:
        gewerk.heizlast_kw = float(kw)
        gewerk.heizlast_datum = datetime.now()
    gewerk.heizlast_link = (form.get("heizlast_link") or "").strip()[:300]
    kern.verlauf(session, gewerk.projekt_id,
                 f"Heizlast aktualisiert: {form.get('heizlast_kw') or '–'} kW",
                 benutzer=request.state.benutzer, gewerk_id=gewerk.id)
    session.commit()
    if _json_gewuenscht(request):
        return _meldung_json("Heizlast gespeichert.")
    return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}",
                            status_code=303)


@router.post("/aufgabe/{aufgabe_id}/status")
async def aufgabe_status(request: Request, aufgabe_id: int,
                         session: Session = Depends(get_session)):
    """Checkbox „erledigt" oder Status-Dropdown; „Wartet" startet die
    Warte-Frist aus der Vorlage; Verantwortlicher änderbar (benachrichtigt)."""
    if (umleitung := _gate(request, session, schreiben=True)) is not None:
        return umleitung
    aufgabe = session.get(Aufgabe, aufgabe_id)
    if aufgabe is None:
        return RedirectResponse("/projektierung", status_code=303)
    benutzer = request.state.benutzer
    form = await request.form()
    from datetime import timedelta
    if "verantwortlich_id" in form:
        try:
            neu = int(form.get("verantwortlich_id") or 0) or None
        except ValueError:
            neu = None
        if neu != aufgabe.verantwortlich_id:
            aufgabe.verantwortlich_id = neu
            if neu:
                projekt = session.get(Projekt, aufgabe.projekt_id)
                kern.benachrichtigen(
                    session, [neu],
                    f"Aufgabe zugewiesen: {aufgabe.titel} "
                    f"({projekt.nummer if projekt else '?'})",
                    f"/projektierung/projekt/{aufgabe.projekt_id}", art="aufgabe")
    neuer_status = form.get("status") or ""
    if form.get("erledigt") == "on":
        neuer_status = "erledigt"
    elif "erledigt" not in form and "status" not in form:
        neuer_status = ""
    elif "erledigt" in form and form.get("erledigt") != "on":
        neuer_status = "offen"
    if neuer_status and neuer_status != aufgabe.status:
        # Checkbox-Formulare senden kein Feld, wenn abgehakt wird → der
        # Wechsel weg von „erledigt" läuft über das Status-Dropdown
        aufgabe.status = neuer_status
        if neuer_status == "erledigt":
            aufgabe.erledigt_am = datetime.now()
            aufgabe.erledigt_von = benutzer.id if benutzer else None
        else:
            aufgabe.erledigt_am = None
            aufgabe.erledigt_von = None
        if neuer_status == "wartet" and aufgabe.wartet_frist_tage:
            aufgabe.wartet_frist_am = (datetime.now()
                                       + timedelta(days=aufgabe.wartet_frist_tage))
        elif neuer_status != "wartet":
            aufgabe.wartet_frist_am = None
    session.commit()
    if _json_gewuenscht(request):
        return _aufgabe_json(request, session, aufgabe, "Aufgabe gespeichert.")
    return RedirectResponse(f"/projektierung/projekt/{aufgabe.projekt_id}"
                            f"#aufgabe-{aufgabe.id}", status_code=303)


@router.post("/aufgabe/{aufgabe_id}/erledigt-umschalten")
async def aufgabe_umschalten(request: Request, aufgabe_id: int,
                             session: Session = Depends(get_session)):
    """Checkbox in der Akte: erledigt ↔ offen (ein Klick, kein Formular-Mix)."""
    if (umleitung := _gate(request, session, schreiben=True)) is not None:
        return umleitung
    aufgabe = session.get(Aufgabe, aufgabe_id)
    if aufgabe is None:
        return RedirectResponse("/projektierung", status_code=303)
    benutzer = request.state.benutzer
    if aufgabe.status == "erledigt":
        aufgabe.status = "offen"
        aufgabe.erledigt_am = None
        aufgabe.erledigt_von = None
    else:
        aufgabe.status = "erledigt"
        aufgabe.erledigt_am = datetime.now()
        aufgabe.erledigt_von = benutzer.id if benutzer else None
    session.commit()
    if _json_gewuenscht(request):
        return _aufgabe_json(request, session, aufgabe)
    zurueck = request.query_params.get("zurueck") or ""
    if zurueck.startswith("/projektierung/meine-aufgaben"):
        return RedirectResponse(zurueck, status_code=303)
    return RedirectResponse(f"/projektierung/projekt/{aufgabe.projekt_id}"
                            f"#aufgabe-{aufgabe.id}", status_code=303)


@router.post("/gewerk/{gewerk_id}/aufgabe")
async def aufgabe_neu(request: Request, gewerk_id: int,
                      session: Session = Depends(get_session)):
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()
    titel = (form.get("titel") or "").strip()[:300]
    if titel:
        benutzer = request.state.benutzer
        session.add(Aufgabe(
            gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id, titel=titel,
            rolle="projektierer",
            verantwortlich_id=benutzer.id if benutzer else None,
            pflicht=False, reihenfolge=999,
            erstellt_von=benutzer.id if benutzer else None))
        session.commit()
    return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}",
                            status_code=303)


@router.post("/gewerk/{gewerk_id}/paket")
async def paket_aktivieren(request: Request, gewerk_id: int,
                           session: Session = Depends(get_session)):
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()
    logik = projektierung_logik.hole_logik(session)
    paket = logik.pakete.get(form.get("paket_key") or "")
    meldung = "Unbekanntes Paket."
    if paket is not None:
        instanz = kern.paket_aktivieren(session, gewerk, paket,
                                        benutzer=request.state.benutzer,
                                        quelle="manuell")
        if instanz is None:
            meldung = f"Paket „{paket.name}“ ist bereits aktiv."
        else:
            kern.verlauf(session, gewerk.projekt_id,
                         f"Paket „{paket.name}“ am Gewerk {gewerk.sparte} aktiviert",
                         benutzer=request.state.benutzer, gewerk_id=gewerk.id)
            session.commit()
            meldung = f"Paket „{paket.name}“ aktiviert."
    return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}"
                            f"?meldung=" + quote_plus(meldung), status_code=303)


@router.post("/gewerk/{gewerk_id}/termin")
async def termin_anlegen(request: Request, gewerk_id: int,
                         session: Session = Depends(get_session)):
    """Termin am Gewerk; Feinplanungs-/Montagetermine berechnen die
    FP+N/M-N-Fälligkeiten des Gewerks nach (Phase 68)."""
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()
    def _zeit(name):
        roh = (form.get(name) or "").strip()
        for muster in ("%Y-%m-%dT%H:%M", "%Y-%m-%d"):
            try:
                # V4 (Phase 90.4): Uhrzeiten serverseitig auf 15 Minuten runden
                wert = datetime.strptime(roh, muster)
                return kern.viertelstunde(wert) if "T" in roh else wert
            except ValueError:
                continue
        return None
    beginn = _zeit("beginn")
    if beginn is None:
        return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}"
                                "?meldung=" + quote_plus("Bitte einen Beginn angeben."),
                                status_code=303)
    typ = (form.get("typ") or "sonstige").lower()
    if typ not in ("feinplanung", "montage", "abnahme", "sub", "sonstige"):
        typ = "sonstige"
    def _id(name):
        try:
            return int(form.get(name) or 0) or None
        except ValueError:
            return None
    # v15 (Phase 75): Montagetermine brauchen ein Team
    if typ == "montage" and not _id("team_id"):
        return RedirectResponse(
            f"/projektierung/projekt/{gewerk.projekt_id}?meldung="
            + quote_plus("Montagetermine brauchen ein Team (Phase 75) – "
                         "bitte Team wählen."), status_code=303)
    ende = _zeit("ende")
    bestaetigt = form.get("kunde_bestaetigt") == "on"
    termin = ProjektTermin(
        gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id, typ=typ,
        beginn=beginn, ende=ende, team_id=_id("team_id"),
        person_id=_id("person_id"), sub_id=_id("sub_id"),
        kunde_bestaetigt=bestaetigt,
        bestaetigt_am=datetime.now() if bestaetigt else None,
        bestaetigt_quelle="manuell" if bestaetigt else "",
        dauer_tage=(max(1, (ende.date() - beginn.date()).days + 1)
                    if ende else 1),
        notiz=(form.get("notiz") or "").strip()[:500],
        erstellt_von=request.state.benutzer.id if request.state.benutzer else None)
    session.add(termin)
    session.flush()
    # v15 (Phase 81): Outlook-Sync (best effort, blockiert nie)
    from app import outlook_kalender
    outlook_kalender.event_senden(session, termin)
    nachberechnet = 0
    if typ in ("feinplanung", "montage"):
        nachberechnet = kern.faelligkeiten_nachberechnen(session, gewerk)
    kern.verlauf(session, gewerk.projekt_id,
                 f"Termin {typ} am {beginn.strftime('%d.%m.%Y %H:%M')} "
                 f"({gewerk.sparte}) angelegt"
                 + (f" – {nachberechnet} Fälligkeiten nachberechnet"
                    if nachberechnet else ""),
                 benutzer=request.state.benutzer, gewerk_id=gewerk.id)
    session.commit()
    return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}",
                            status_code=303)


@router.post("/termin/{termin_id}/outlook")
async def termin_outlook_senden(request: Request, termin_id: int,
                                session: Session = Depends(get_session)):
    """v15 (Phase 81): „Erneut senden“ am Termin mit Sync-Warnsymbol."""
    from app import outlook_kalender
    termin = session.get(ProjektTermin, termin_id)
    if termin is None:
        return RedirectResponse("/projektierung", status_code=303)
    ok, fehler = outlook_kalender.event_senden(session, termin)
    session.commit()
    meldung = "Termin nach Outlook übertragen." if ok else fehler
    return RedirectResponse(f"/projektierung/projekt/{termin.projekt_id}"
                            "?meldung=" + quote_plus(meldung), status_code=303)


@router.post("/termin/{termin_id}/kundenmail")
async def termin_kundenmail(request: Request, termin_id: int,
                            session: Session = Depends(get_session)):
    """v15 (Phase 81): Terminbestätigung an den Kunden (Vorlage in der
    Parametrierung); die Antwort setzt später den Bestätigungs-Vorschlag."""
    from app import terminmail
    termin = session.get(ProjektTermin, termin_id)
    if termin is None:
        return RedirectResponse("/projektierung", status_code=303)
    ok, meldung = terminmail.senden(session, termin,
                                    benutzer=request.state.benutzer)
    if ok:
        session.commit()
    else:
        session.rollback()
    return RedirectResponse(f"/projektierung/projekt/{termin.projekt_id}"
                            "?meldung=" + quote_plus(meldung), status_code=303)


@router.post("/termin/{termin_id}/kunde-bestaetigt")
async def termin_kunde_bestaetigt(request: Request, termin_id: int,
                                  session: Session = Depends(get_session)):
    termin = session.get(ProjektTermin, termin_id)
    if termin is None:
        return RedirectResponse("/projektierung", status_code=303)
    form = await request.form()
    termin.kunde_bestaetigt = True
    termin.bestaetigt_am = datetime.now()
    termin.bestaetigt_quelle = ("mail" if form.get("quelle") == "mail"
                                else "manuell")
    kern.verlauf(session, termin.projekt_id,
                 "Kunde hat den Termin bestätigt ("
                 + ("Mail-Antwort" if termin.bestaetigt_quelle == "mail"
                    else "manuell") + ")",
                 benutzer=request.state.benutzer, gewerk_id=termin.gewerk_id)
    session.commit()
    return RedirectResponse(f"/projektierung/projekt/{termin.projekt_id}",
                            status_code=303)


def _restarbeiten_je_gewerk(session: Session, gewerke) -> dict[int, list]:
    """v15 (Phase 78): Restarbeiten/Reklamationen je Gewerk (offene zuerst)."""
    from app.models import Restarbeit
    daten: dict[int, list] = {g.id: [] for g in gewerke}
    if not daten:
        return daten
    for r in (session.query(Restarbeit)
              .filter(Restarbeit.gewerk_id.in_(list(daten)))
              .order_by(Restarbeit.status.desc(), Restarbeit.id)):
        daten.setdefault(r.gewerk_id, []).append(r)
    return daten


@router.post("/aufgabe/{aufgabe_id}/auswahl")
async def aufgabe_auswahl(request: Request, aufgabe_id: int,
                          session: Session = Depends(get_session)):
    """v15 (Phase 78): Radio-Auswahl an einer Aufgabe (Option mit * im Blatt
    = erledigt, ohne * = entfaellt/beantwortet)."""
    aufgabe = session.get(Aufgabe, aufgabe_id)
    if aufgabe is None:
        return RedirectResponse("/projektierung", status_code=303)
    form = await request.form()
    meldung = ""
    if kern.aufgabe_auswahl_setzen(session, aufgabe,
                                   form.get("auswahl") or "",
                                   benutzer=request.state.benutzer):
        meldung = kern.auswahl_folgen(session, aufgabe,
                                      benutzer=request.state.benutzer)
        session.commit()
    if _json_gewuenscht(request):
        return _aufgabe_json(request, session, aufgabe, meldung)
    return RedirectResponse(f"/projektierung/projekt/{aufgabe.projekt_id}"
                            f"#aufgabe-{aufgabe.id}", status_code=303)


@router.post("/aufgabe/{aufgabe_id}/in-arbeit")
async def aufgabe_in_arbeit(request: Request, aufgabe_id: int,
                            session: Session = Depends(get_session)):
    """v15 (Phase 78): Link-Aufgaben setzen sich beim Klick auf "in Arbeit"
    (Aufruf per fetch aus der Akte, keine Navigation)."""
    aufgabe = session.get(Aufgabe, aufgabe_id)
    if aufgabe is not None and aufgabe.status == "offen":
        aufgabe.status = "in_arbeit"
        session.commit()
    return {"ok": True}


@router.get("/gewerk/{gewerk_id}/feinplanung")
async def feinplanung_erfassung(request: Request, gewerk_id: int,
                                session: Session = Depends(get_session)):
    """v15 (Phase 80): mobile Feinplanungs-Erfassung (Blatt Fragen FP-WP),
    vorbelegt aus der Vertriebs-Erfassung („vom Vertrieb“-Markierung)."""
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    logik = projektierung_logik.hole_logik(session)
    seiten = logik.fp_seiten()
    if not seiten:
        return RedirectResponse(
            f"/projektierung/projekt/{gewerk.projekt_id}?meldung="
            + quote_plus("Blatt „Fragen FP-WP“ ist leer – bitte in der "
                         "Logik-Excel pflegen."), status_code=303)
    if kern.fp_vorbelegen(session, gewerk):
        session.commit()
    try:
        seite = max(0, min(int(request.query_params.get("seite", gewerk.fp_seite_index or 0)),
                           len(seiten) - 1))
    except ValueError:
        seite = 0
    import json as json_modul
    return render(request, "projektierung/feinplanung.html",
                  aktiv="/projektierung",
                  gewerk=gewerk, projekt=session.get(Projekt, gewerk.projekt_id),
                  seiten=seiten, seite=seite,
                  seiten_name=seiten[seite][0], fragen=seiten[seite][1],
                  antworten=kern.fp_antworten(gewerk),
                  vorbelegt=json_modul.loads(gewerk.fp_vorbelegt_json or "{}"),
                  offene_pflicht=kern.fp_offene_pflicht(session, gewerk),
                  benutzer=request.state.benutzer,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/gewerk/{gewerk_id}/feinplanung")
async def feinplanung_speichern(request: Request, gewerk_id: int,
                                session: Session = Depends(get_session)):
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()
    logik = projektierung_logik.hole_logik(session)
    seiten = logik.fp_seiten()
    try:
        seite = max(0, min(int(form.get("seite") or 0), len(seiten) - 1))
    except ValueError:
        seite = 0
    kern.fp_seite_speichern(session, gewerk, seiten[seite][1], form)
    aktion = form.get("aktion") or "weiter"
    if aktion == "abschliessen":
        ok, meldung = kern.fp_abschliessen(session, gewerk,
                                           benutzer=request.state.benutzer)
        session.commit()
        if ok:
            return RedirectResponse(
                f"/projektierung/projekt/{gewerk.projekt_id}?meldung="
                + quote_plus(meldung), status_code=303)
        return RedirectResponse(
            f"/projektierung/gewerk/{gewerk.id}/feinplanung?seite={seite}"
            f"&meldung=" + quote_plus(meldung), status_code=303)
    ziel = seite - 1 if aktion == "zurueck" else min(seite + 1, len(seiten) - 1)
    gewerk.fp_seite_index = max(0, ziel)
    session.commit()
    return RedirectResponse(
        f"/projektierung/gewerk/{gewerk.id}/feinplanung?seite={max(0, ziel)}",
        status_code=303)


@router.get("/gewerk/{gewerk_id}/bza")
async def bza_datenblatt(request: Request, gewerk_id: int,
                         session: Session = Depends(get_session)):
    """v15 (Phase 80): BzA-Datenblatt – alle Antragsfelder aus Vorgang,
    Angebot und Förder-Editor in Portal-Reihenfolge mit Kopier-Buttons;
    fehlende Felder werden ausgewiesen. Druck über die Browser-Funktion."""
    import json as json_modul

    from app import kfw
    from app import logik as logik_modul
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    projekt = session.get(Projekt, gewerk.projekt_id)
    kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
    angebot = session.get(Angebot, gewerk.angebot_id) if gewerk.angebot_id else None
    kfw_daten = json_modul.loads(angebot.kfw_json or "{}") if angebot else {}
    antworten, _positionen, _profil = kern._steckbrief_quellen(session, gewerk)
    steck = kern.steckbrief_daten(session, [gewerk.id])[gewerk.id]

    def wert(*quellen, einheit=""):
        for q in quellen:
            if q not in (None, ""):
                return f"{q}{einheit}"
        return ""

    kfw_ergebnis = None
    if angebot is not None and not angebot.extern and kfw_daten.get("O01"):
        logik, bericht = logik_modul.hole_logik(session)
        if bericht is not None:
            parameter, _ = kfw.parameter_lesen(logik)
            eingaben = kfw.eingaben_aus_antworten(
                kfw_daten, angebot.summen()["endbetrag"])
            if eingaben is not None:
                kfw_ergebnis = kfw.ergebnis_fuer_angebot(parameter, eingaben,
                                                         angebot)
    geraet = " · ".join(steck[f].wert for f in ("hersteller", "leistungsklasse")
                          if f in steck and steck[f].wert)
    felder = [
        ("Antragsteller", [
            ("Name", kunde.anzeige_name if kunde else ""),
            ("Straße und Hausnummer", kunde.strasse if kunde else ""),
            ("PLZ / Ort", f"{kunde.plz} {kunde.ort}".strip() if kunde else ""),
            ("Telefon", kunde.telefon if kunde else ""),
            ("E-Mail", kunde.email if kunde else ""),
        ]),
        ("Ausführungsadresse (Investitionsobjekt)", [
            ("Straße und Hausnummer",
             projekt.ausfuehrung_strasse if projekt else ""),
            ("PLZ / Ort", f"{projekt.ausfuehrung_plz} "
                          f"{projekt.ausfuehrung_ort}".strip() if projekt else ""),
        ]),
        ("Gebäude", [
            ("Objektart", wert(kfw_daten.get("O01"), antworten.get("O01"))),
            ("Baujahr", wert(kfw_daten.get("O02"), antworten.get("O02"))),
            ("Wohneinheiten", wert(kfw_daten.get("O03"), antworten.get("O03"))),
            ("Beheizte Fläche", wert(kfw_daten.get("O05"),
                                        antworten.get("O05"), einheit=" m²")),
        ]),
        ("Maßnahme", [
            ("Maßnahme", "Heizungstausch: Einbau einer Wärmepumpe"
             if gewerk.sparte == "WP" else gewerk.sparte),
            ("Gerät", geraet),
            ("Alte Anlage", wert(steck["alte_anlage"].wert
                                 if "alte_anlage" in steck else "",
                                 antworten.get("A01"))),
        ]),
    ]
    if kfw_ergebnis is not None:
        felder.append(("Förderfähige Kosten & Zuschuss (Förder-Editor)", [
            (name, w) for name, w, _fett in kfw_ergebnis.zeilen]))
    else:
        felder.append(("Förderfähige Kosten & Zuschuss", [
            ("Hinweis", "Keine KfW-Daten am Angebot (TAIFUN-Auftrag oder "
                        "Förder-Editor nicht ausgefüllt)")]))
    felder.append(("Bonus-Bausteine", [
        ("Klimageschwindigkeits-Bonus", wert(kfw_daten.get("K02"))),
        ("Einkommensbonus (zu versteuerndes Einkommen)",
         wert(kfw_daten.get("K03"), einheit=" €")),
        ("Selbstnutzung", wert(kfw_daten.get("K01"))),
    ]))
    felder.append(("Fachunternehmer", [
        ("Fachunternehmer", kern.parameter_holen(
            session, "bza_fachunternehmer", "Friondo GmbH")),
    ]))
    fehlend = [f"{gruppe}: {name}" for gruppe, eintraege in felder
               for name, w in eintraege if not str(w).strip()]
    return render(request, "projektierung/bza.html",
                  aktiv="/projektierung",
                  gewerk=gewerk, projekt=projekt, felder=felder,
                  fehlend=fehlend,
                  url_bza=kern.parameter_holen(session, "url_bza_portal", ""),
                  benutzer=request.state.benutzer,
                  meldung=request.query_params.get("meldung", ""))


@router.get("/gewerk/{gewerk_id}/ugl")
async def ugl_seite(request: Request, gewerk_id: int,
                    session: Session = Depends(get_session)):
    """v15 (Phase 80): UGL-Bestellung Collin – Vorschau der Materialzeilen
    (Auftrag × Stücklisten-Blatt) mit fehlenden Zuordnungen + Erzeugen."""
    from app import ugl as ugl_modul
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    zeilen, fehlend = ugl_modul.material_fuer_gewerk(session, gewerk)
    ts = kern.terminstatus(session, gewerk)
    termin = ts.get("termin")
    lieferdatum = (ugl_modul.werktage_zurueck(termin.beginn, 3)
                   if termin is not None and termin.beginn else None)
    return render(request, "projektierung/ugl.html",
                  aktiv="/projektierung",
                  gewerk=gewerk, projekt=session.get(Projekt, gewerk.projekt_id),
                  zeilen=zeilen, fehlend=fehlend, lieferdatum=lieferdatum,
                  kundennummer=kern.parameter_holen(session,
                                                    "collin_kundennummer", ""),
                  lieferadresse=kern.parameter_holen(session, "ugl_lieferadresse",
                                                     "ausfuehrung"),
                  url_gc=kern.parameter_holen(session, "url_gc_online", ""),
                  benutzer=request.state.benutzer,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/gewerk/{gewerk_id}/ugl")
async def ugl_erzeugen(request: Request, gewerk_id: int,
                       session: Session = Depends(get_session)):
    """UGL-Datei erzeugen: Ablage in der Galerie „Montagedokumente“ +
    direkter Download; die zugehörige api-Aufgabe springt auf „in Arbeit“
    (Bestellung in GC Online Plus erfolgt manuell)."""
    from fastapi.responses import Response

    from app import galerie as galerie_modul
    from app import ugl as ugl_modul
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    inhalt, dateiname, _fehlend, fehler = ugl_modul.ugl_erzeugen(session, gewerk)
    if inhalt is None:
        return RedirectResponse(
            f"/projektierung/gewerk/{gewerk.id}/ugl?meldung=" + quote_plus(fehler),
            status_code=303)
    angebot = session.get(Angebot, gewerk.angebot_id) if gewerk.angebot_id else None
    if angebot is not None and angebot.vorgang_id:
        galerie_modul.speichern(session, angebot.vorgang_id, "Montagedokumente",
                                dateiname, inhalt,
                                benutzer=request.state.benutzer,
                                bemerkung="UGL-Bestelldatei (Collin)",
                                quelle="formular", sparte=gewerk.sparte)
    for aufgabe in (session.query(Aufgabe)
                    .filter(Aufgabe.gewerk_id == gewerk.id,
                            Aufgabe.aktion_typ == "api",
                            Aufgabe.aktion_wert == "ugl_collin",
                            Aufgabe.status == "offen")):
        aufgabe.status = "in_arbeit"
    kern.verlauf(session, gewerk.projekt_id,
                 f"UGL-Bestelldatei erzeugt ({dateiname})",
                 benutzer=request.state.benutzer, gewerk_id=gewerk.id)
    session.commit()
    return Response(content=inhalt, media_type="application/octet-stream",
                    headers={"Content-Disposition":
                             f'attachment; filename="{dateiname}"'})


@router.get("/aufgabe/{aufgabe_id}/sub-mail")
async def sub_mail_dialog(request: Request, aufgabe_id: int,
                          session: Session = Depends(get_session)):
    """v15 (Phase 79): Sub-Beauftragung per Mail – Vorlage vorbefüllt,
    Foto-Anhänge abwählbar, Steckbrief-PDF optional."""
    from app import sub_mail as sub_mail_modul
    aufgabe = session.get(Aufgabe, aufgabe_id)
    if aufgabe is None or aufgabe.gewerk_id is None:
        return RedirectResponse("/projektierung", status_code=303)
    gewerk, umleitung = _gewerk_laden(request, session, aufgabe.gewerk_id)
    if umleitung is not None:
        return umleitung
    projekt = session.get(Projekt, gewerk.projekt_id)
    sub_typ, ordner_fallback = sub_mail_modul.aktion_parsen(aufgabe.aktion_wert)
    logik = projektierung_logik.hole_logik(session)
    vorlage = logik.sub_vorlagen.get(sub_typ)
    if vorlage is None:
        return RedirectResponse(
            f"/projektierung/projekt/{gewerk.projekt_id}?meldung="
            + quote_plus(f"Keine Sub-Mailvorlage für „{sub_typ}“ im Blatt "
                         "Sub-Mailvorlagen – bitte in der Logik-Excel pflegen."),
            status_code=303)
    ordner = vorlage.ordner or ([ordner_fallback] if ordner_fallback else [])
    platzhalter = kern.sub_mail_platzhalter(session, gewerk)
    subs = (session.query(Subunternehmer)
            .filter(Subunternehmer.aktiv.is_(True))
            .order_by(Subunternehmer.typ != sub_typ, Subunternehmer.firma).all())
    return render(request, "projektierung/sub_mail.html",
                  aktiv="/projektierung",
                  aufgabe=aufgabe, gewerk=gewerk, projekt=projekt,
                  sub_typ=sub_typ, vorlage=vorlage,
                  betreff=kern.sub_mail_text(vorlage.betreff, platzhalter),
                  text=kern.sub_mail_text(vorlage.text, platzhalter),
                  fotos=sub_mail_modul.fotos_fuer(session, gewerk, ordner),
                  ordner=ordner, subs=subs,
                  standard_id=sub_mail_modul.standard_sub_id(session, sub_typ),
                  platzhalter=platzhalter,
                  benutzer=request.state.benutzer,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/aufgabe/{aufgabe_id}/sub-mail")
async def sub_mail_senden(request: Request, aufgabe_id: int,
                          session: Session = Depends(get_session)):
    from app import sub_mail as sub_mail_modul
    aufgabe = session.get(Aufgabe, aufgabe_id)
    if aufgabe is None or aufgabe.gewerk_id is None:
        return RedirectResponse("/projektierung", status_code=303)
    gewerk, umleitung = _gewerk_laden(request, session, aufgabe.gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()
    try:
        sub = session.get(Subunternehmer, int(form.get("sub_id") or 0))
    except ValueError:
        sub = None
    foto_ids = []
    for wert in form.getlist("foto_ids"):
        try:
            foto_ids.append(int(wert))
        except ValueError:
            continue
    ok, meldung = sub_mail_modul.senden(
        session, aufgabe, gewerk, sub,
        betreff=(form.get("betreff") or "").strip()[:300],
        text=(form.get("text") or "").strip()[:10000],
        foto_ids=foto_ids,
        mit_steckbrief=form.get("steckbrief") == "on",
        benutzer=request.state.benutzer)
    if ok:
        session.commit()
        return RedirectResponse(
            f"/projektierung/projekt/{gewerk.projekt_id}?meldung="
            + quote_plus(meldung) + "#subs", status_code=303)
    session.rollback()
    return RedirectResponse(
        f"/projektierung/aufgabe/{aufgabe_id}/sub-mail?meldung="
        + quote_plus(meldung), status_code=303)


@router.post("/gewerk/{gewerk_id}/v1-entfernen")
async def v1_entfernen(request: Request, gewerk_id: int,
                       session: Session = Depends(get_session)):
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    anzahl = kern.v1_aufgaben_entfernen(session, gewerk,
                                        benutzer=request.state.benutzer)
    session.commit()
    return RedirectResponse(
        f"/projektierung/projekt/{gewerk.projekt_id}?meldung="
        + quote_plus(f"{anzahl} V1-Aufgaben entfernt."), status_code=303)


@router.post("/gewerk/{gewerk_id}/restarbeit")
async def restarbeit_anlegen(request: Request, gewerk_id: int,
                             session: Session = Depends(get_session)):
    """v15 (Phase 78): Restarbeit/Reklamation am Gewerk – Text, optionales
    Foto (landet in der Galerie unter Inbetrieb-/Abnahme), Verantwortlicher."""
    from app.models import Restarbeit
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()
    text = (form.get("text") or "").strip()[:500]
    if not text:
        return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}",
                                status_code=303)
    try:
        verantwortlich_id = int(form.get("verantwortlich_id") or 0) or None
    except ValueError:
        verantwortlich_id = None
    eintrag = Restarbeit(gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id,
                         text=text, verantwortlich_id=verantwortlich_id,
                         erstellt_von=(request.state.benutzer.id
                                       if request.state.benutzer else None))
    datei = form.get("datei")
    if datei is not None and getattr(datei, "filename", ""):
        from app import galerie as galerie_modul
        angebot = (session.get(Angebot, gewerk.angebot_id)
                   if gewerk.angebot_id else None)
        if angebot is not None and angebot.vorgang_id:
            inhalt = await datei.read()
            galerie_datei = galerie_modul.speichern(
                session, angebot.vorgang_id, "Inbetrieb-/Abnahme",
                datei.filename, inhalt, benutzer=request.state.benutzer,
                bemerkung=f"Restarbeit: {text[:100]}", quelle="formular",
                sparte=gewerk.sparte)
            if galerie_datei is not None:
                eintrag.galerie_datei_id = galerie_datei.id
    session.add(eintrag)
    kern.verlauf(session, gewerk.projekt_id,
                 f"Restarbeit erfasst: {text[:120]} – Gewerk {gewerk.sparte}",
                 benutzer=request.state.benutzer, gewerk_id=gewerk.id)
    session.commit()
    return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}",
                            status_code=303)


@router.post("/restarbeit/{restarbeit_id}/status")
async def restarbeit_status(request: Request, restarbeit_id: int,
                            session: Session = Depends(get_session)):
    from app.models import Restarbeit
    eintrag = session.get(Restarbeit, restarbeit_id)
    if eintrag is None:
        return RedirectResponse("/projektierung", status_code=303)
    if eintrag.status == "erledigt":
        eintrag.status = "offen"
        eintrag.erledigt_am = None
    else:
        eintrag.status = "erledigt"
        eintrag.erledigt_am = datetime.now()
    session.commit()
    if _json_gewuenscht(request):
        return _meldung_json("", restarbeit={"id": eintrag.id,
                                             "erledigt": eintrag.status == "erledigt"})
    return RedirectResponse(f"/projektierung/projekt/{eintrag.projekt_id}"
                            f"#restarbeit-{eintrag.id}", status_code=303)


@router.post("/gewerk/{gewerk_id}/zaehlerwechsel")
async def zaehlerwechsel_setzen(request: Request, gewerk_id: int,
                                session: Session = Depends(get_session)):
    """v15 (Phase 78, Fit for Future): Zählerwechseltermin am Gewerk –
    erscheint als Marker im Team-Kalender."""
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()
    roh = (form.get("datum") or "").strip()
    if roh:
        try:
            gewerk.zaehlerwechsel_termin = datetime.strptime(roh, "%Y-%m-%d")
        except ValueError:
            pass
    else:
        gewerk.zaehlerwechsel_termin = None
    session.commit()
    return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}",
                            status_code=303)


@router.post("/gewerk/{gewerk_id}/steckbrief")
async def steckbrief_speichern(request: Request, gewerk_id: int,
                               session: Session = Depends(get_session)):
    """v15 (Phase 77): Steckbrief-Feld per Klick editieren – manuell
    geänderte Felder werden bei „Neu ableiten“ nicht überschrieben."""
    from app.models import SteckbriefWert
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()
    feld = (form.get("feld") or "").strip()[:60]
    wert = (form.get("wert") or "").strip()[:500]
    gueltig = {f for f, _ in kern.steckbrief_felder(gewerk.sparte)}
    if feld not in gueltig:
        return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}",
                                status_code=303)
    eintrag = (session.query(SteckbriefWert)
               .filter(SteckbriefWert.gewerk_id == gewerk.id,
                       SteckbriefWert.feld == feld).first())
    if eintrag is None:
        eintrag = SteckbriefWert(gewerk_id=gewerk.id, feld=feld)
        session.add(eintrag)
    eintrag.wert = wert
    eintrag.manuell = True
    eintrag.geaendert_von = (request.state.benutzer.id
                             if request.state.benutzer else None)
    session.commit()
    if _json_gewuenscht(request):
        return _meldung_json(f"Steckbrief: {feld} gespeichert.")
    zurueck = form.get("zurueck") or f"/projektierung/projekt/{gewerk.projekt_id}"
    return RedirectResponse(zurueck, status_code=303)


@router.post("/gewerk/{gewerk_id}/steckbrief-ableiten")
async def steckbrief_neu_ableiten(request: Request, gewerk_id: int,
                                  session: Session = Depends(get_session)):
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    anzahl = kern.steckbrief_ableiten(session, gewerk,
                                      benutzer=request.state.benutzer)
    session.commit()
    return RedirectResponse(
        f"/projektierung/projekt/{gewerk.projekt_id}?meldung="
        + quote_plus(f"Steckbrief neu abgeleitet ({anzahl} Felder aktualisiert; "
                     "manuell geänderte blieben stehen)."), status_code=303)


@router.post("/gewerk/{gewerk_id}/team-termin")
async def team_termin(request: Request, gewerk_id: int,
                      session: Session = Depends(get_session)):
    """v15 (Phase 75): Zuweisungsdialog „Team + Termin“ – Team ans Gewerk
    (WP-/Elektro-/Sub-Zuweisung) plus Montagetermin; Konflikt = Warnung."""
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()

    def _datum(name):
        roh = (form.get(name) or "").strip()
        try:
            return datetime.strptime(roh, "%Y-%m-%d")
        except ValueError:
            return None
    try:
        team_id = int(form.get("team_id") or 0)
    except ValueError:
        team_id = 0
    ok, meldung, konflikte = kern.team_termin_zuweisen(
        session, gewerk, (form.get("zweck") or "wp").lower(), team_id,
        _datum("beginn"), _datum("ende"),
        form.get("kunde_bestaetigt") == "on",
        benutzer=request.state.benutzer)
    if ok:
        session.commit()
        if konflikte:
            meldung += (" ⚠ Konflikt: Team am selben Tag auch bei "
                        + "; ".join(konflikte[:3]))
        # v15 (Phase 81): neuen Montagetermin nach Outlook spiegeln
        from app import outlook_kalender
        neuer_termin = (session.query(ProjektTermin)
                        .filter(ProjektTermin.gewerk_id == gewerk.id,
                                ProjektTermin.typ == "montage")
                        .order_by(ProjektTermin.id.desc()).first())
        if neuer_termin is not None:
            outlook_kalender.event_senden(session, neuer_termin)
            session.commit()
    else:
        session.rollback()
    # V4 (Phase 90.1): Drop auf „Auftragseingang · terminiert“ kommt vom Board
    zurueck = form.get("zurueck") or ""
    if zurueck.startswith("/projektierung") and "//" not in zurueck:
        trenner = "&" if "?" in zurueck else "?"
        return RedirectResponse(zurueck + trenner + "meldung=" + quote_plus(meldung),
                                status_code=303)
    return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}"
                            "?meldung=" + quote_plus(meldung), status_code=303)


@router.get("/kalender")
async def kalender(request: Request, ansicht: str = "woche", start: str = "",
                   team_id: int = 0, sparte: str = "", terminstatus: str = "",
                   session: Session = Depends(get_session)):
    """v15 (Phase 75): Kalender – Zeilen = Teams, Spalten = Tage, Projekte
    als Balken über ihre Dauer; Ansicht chrono = Gewerke nach Montagebeginn."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    heute = datetime.now().date()
    try:
        start_datum = datetime.strptime(start, "%Y-%m-%d").date() if start else heute
    except ValueError:
        start_datum = heute
    if ansicht not in ("woche", "monat", "chrono"):
        ansicht = "woche"
    if ansicht == "monat":
        von = start_datum.replace(day=1)
        if von.month == 12:
            bis = von.replace(year=von.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            bis = von.replace(month=von.month + 1, day=1) - timedelta(days=1)
        zurueck = (von - timedelta(days=1)).replace(day=1).isoformat()
        vor = (bis + timedelta(days=1)).isoformat()
    else:
        von = start_datum - timedelta(days=start_datum.weekday())
        bis = von + timedelta(days=6)
        zurueck = (von - timedelta(days=7)).isoformat()
        vor = (von + timedelta(days=7)).isoformat()
    tage = [von + timedelta(days=i) for i in range((bis - von).days + 1)]

    zeilen = _gewerk_zeilen(session, request.state.benutzer, sparte=sparte,
                            terminstatus=terminstatus, team_id=team_id)
    gewerk_map = {z["gewerk"].id: z for z in zeilen}
    projekte = {z["projekt"].id: z["projekt"] for z in zeilen}
    kunden = {z["gewerk"].id: z["kunde"] for z in zeilen}

    teams = (session.query(Team).filter(Team.aktiv.is_(True))
             .order_by(Team.typ.desc(), Team.id).all())
    montage_teams = [te for te in teams if te.typ != "sub"]
    sub_teams = [te for te in teams if te.typ == "sub"]

    balken: dict[int | None, list[dict]] = {}
    marker: dict[tuple, list[dict]] = {}
    for termin in (session.query(ProjektTermin)
                   .filter(ProjektTermin.beginn.isnot(None))
                   .order_by(ProjektTermin.beginn)):
        if termin.gewerk_id not in gewerk_map:
            continue
        t_beginn = termin.beginn.date()
        t_ende = (termin.ende or termin.beginn).date()
        if t_ende < von or t_beginn > bis:
            continue
        z = gewerk_map[termin.gewerk_id]
        if termin.typ == "montage":
            start_idx = max(0, (t_beginn - von).days)
            ende_idx = min(len(tage) - 1, (t_ende - von).days)
            balken.setdefault(termin.team_id, []).append({
                "termin": termin, "zeile": z,
                "start": start_idx + 1, "ende": ende_idx + 2,
                "links_offen": t_beginn < von, "rechts_offen": t_ende > bis,
            })
        elif termin.typ in ("feinplanung", "abnahme"):
            idx = (t_beginn - von).days
            if 0 <= idx < len(tage):
                marker.setdefault((termin.team_id, idx), []).append(
                    {"termin": termin, "zeile": z, "art": termin.typ})

    # v15 (Phase 78): Zählerwechseltermine (Fit for Future) als Marker
    for z in zeilen:
        g = z["gewerk"]
        if g.zaehlerwechsel_termin is None:
            continue
        idx = (g.zaehlerwechsel_termin.date() - von).days
        if 0 <= idx < len(tage):
            marker.setdefault((g.wp_team_id, idx), []).append(
                {"termin": None, "zeile": z, "art": "zaehlerwechsel"})

    # Chronologisch: Gewerke nach Montagebeginn, Unterminierte unten
    chrono = sorted(
        [z for z in zeilen if z["gewerk"].phase not in ("abgeschlossen", "storniert")],
        key=kern.sortierschluessel_chrono)

    return render(request, "projektierung/kalender.html",
                  aktiv="/projektierung", ansicht=ansicht,
                  von=von, bis=bis, tage=tage, heute=heute,
                  zurueck=zurueck, vor=vor,
                  montage_teams=montage_teams, sub_teams=sub_teams,
                  balken=balken, marker=marker, chrono=chrono,
                  # v15 (Phase 78): "ohne Team"-Zeile auch für Marker rendern
                  marker_ohne_team=any(k[0] is None for k in marker),
                  teams_map={te.id: te for te in teams},
                  phasen_namen=GEWERK_PHASEN_NAMEN,
                  team_id=team_id, sparte=sparte, terminstatus=terminstatus,
                  benutzer=request.state.benutzer,
                  **_filter_werte(session),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/termin/{termin_id}/kalender-drop")
async def kalender_drop(request: Request, termin_id: int,
                        session: Session = Depends(get_session)):
    """v15 (Phase 75): Balken per Drag verschoben (Datum/Team) oder Ende
    gezogen – protokolliert, Fälligkeiten nachberechnet."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    termin = session.get(ProjektTermin, termin_id)
    form = await request.form()
    zurueck_url = form.get("zurueck") or "/projektierung/kalender"
    if termin is None or termin.beginn is None:
        return RedirectResponse(zurueck_url, status_code=303)
    try:
        datum = datetime.strptime(form.get("datum") or "", "%Y-%m-%d").date()
    except ValueError:
        return RedirectResponse(zurueck_url, status_code=303)
    try:
        neues_team = int(form.get("team_id") or 0)
    except ValueError:
        neues_team = 0
    neu_text = kern.termin_verschieben(session, termin, datum,
                                       neues_team_id=neues_team,
                                       art=form.get("art") or "verschieben",
                                       benutzer=request.state.benutzer)
    konflikte = kern.team_konflikte(session, termin.team_id, termin.beginn,
                                    termin.ende, ausser_termin_id=termin.id)
    # v15 (Phase 81): verschobenen Termin nach Outlook spiegeln
    from app import outlook_kalender
    outlook_kalender.event_senden(session, termin)
    session.commit()
    meldung = f"Termin: {neu_text}"
    if konflikte:
        meldung += " ⚠ Konflikt: " + "; ".join(konflikte[:3])
    trenner = "&" if "?" in zurueck_url else "?"
    return RedirectResponse(zurueck_url + trenner + "meldung="
                            + quote_plus(meldung), status_code=303)


@router.post("/gewerk/{gewerk_id}/phase")
async def phase_aendern(request: Request, gewerk_id: int,
                        session: Session = Depends(get_session)):
    """Phasenwechsel mit Wächtern (Konzept 3.1): unerfüllte Bedingungen nur
    mit Begründung überschreibbar; rückwärts immer mit Begründung."""
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()
    ziel = form.get("phase") or ""
    begruendung = (form.get("begruendung") or "").strip()
    ok, meldung = kern.phase_wechseln(session, gewerk, ziel, begruendung,
                                      benutzer=request.state.benutzer)
    if ok:
        session.commit()
    else:
        session.rollback()
    return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}"
                            f"?meldung=" + quote_plus(meldung), status_code=303)


@router.post("/gewerk/{gewerk_id}/freigabe")
async def freigabe(request: Request, gewerk_id: int,
                   session: Session = Depends(get_session)):
    """Rechnung freigeben (Phase 67): Restarbeiten-Pflichtfrage → Phase
    Abgeschlossen, Benachrichtigung Buchhaltung, ggf. Restarbeiten-Aufgabe."""
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()
    ok, meldung = kern.rechnung_freigeben(
        session, gewerk, form.get("restarbeiten") or "",
        form.get("restarbeiten_text") or "", benutzer=request.state.benutzer)
    if ok:
        session.commit()
    else:
        session.rollback()
    return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}"
                            f"?meldung=" + quote_plus(meldung), status_code=303)


@router.post("/projekt/{projekt_id}/kommentar")
async def kommentar(request: Request, projekt_id: int,
                    session: Session = Depends(get_session)):
    """Kommentar mit @Erwähnung (auch aufgabenbezogen über aufgabe_id)."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    projekt = session.get(Projekt, projekt_id)
    if projekt is None:
        return RedirectResponse("/projektierung", status_code=303)
    form = await request.form()
    text = (form.get("text") or "").strip()
    if not text:
        return RedirectResponse(f"/projektierung/projekt/{projekt_id}",
                                status_code=303)
    def _id(name):
        try:
            return int(form.get(name) or 0) or None
        except ValueError:
            return None
    benutzer = request.state.benutzer
    erwaehnte = kern.erwaehnungen_finden(session, text)
    kern.verlauf(session, projekt.id, text[:4000], benutzer=benutzer,
                 gewerk_id=_id("gewerk_id"), aufgabe_id=_id("aufgabe_id"),
                 art="kommentar", erwaehnte=erwaehnte)
    if erwaehnte:
        kern.benachrichtigen(
            session, erwaehnte,
            f"{benutzer.name if benutzer else '?'} hat dich im Projekt "
            f"{projekt.nummer} erwähnt: {text[:120]}",
            f"/projektierung/projekt/{projekt.id}#verlauf", art="erwaehnung")
    session.commit()
    if _json_gewuenscht(request):
        aufgabe = session.get(Aufgabe, _id("aufgabe_id")) if _id("aufgabe_id") else None
        if aufgabe is not None:
            return _aufgabe_json(request, session, aufgabe, "Kommentar gespeichert.")
        return _meldung_json("Kommentar gespeichert.")
    return RedirectResponse(f"/projektierung/projekt/{projekt_id}#verlauf",
                            status_code=303)


@router.post("/projekt/{projekt_id}/dokument")
async def dokument_hochladen(request: Request, projekt_id: int,
                             session: Session = Depends(get_session)):
    """Upload in die Ordnerstruktur (auch Kamera/mobil); max. 20 MB."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    projekt = session.get(Projekt, projekt_id)
    if projekt is None:
        return RedirectResponse("/projektierung", status_code=303)
    form = await request.form()
    datei = form.get("datei")
    ziel_meldung = f"/projektierung/projekt/{projekt_id}?meldung="
    if datei is None or not getattr(datei, "filename", ""):
        return RedirectResponse(ziel_meldung + quote_plus(
            "Bitte eine Datei wählen."), status_code=303)
    inhalt = await datei.read()
    if len(inhalt) > 20 * 1024 * 1024:
        return RedirectResponse(ziel_meldung + quote_plus(
            "Datei größer als 20 MB – bitte verkleinern (z. B. Foto-Auflösung)."),
            status_code=303)
    ordner = (form.get("ordner") or "").strip().strip("/\\")
    if not ordner or ".." in ordner:
        ordner = "01 Angebot & Erfassung"
    def _id(name):
        try:
            return int(form.get(name) or 0) or None
        except ValueError:
            return None
    name = Path(datei.filename).name
    ziel_ordner = kern.projekt_ordner(projekt) / ordner
    ziel_ordner.mkdir(parents=True, exist_ok=True)
    ziel = ziel_ordner / name
    zaehler = 1
    while ziel.exists():
        zaehler += 1
        ziel = ziel_ordner / f"{Path(name).stem}_{zaehler}{Path(name).suffix}"
    ziel.write_bytes(inhalt)
    endung = ziel.suffix.lower()
    benutzer = request.state.benutzer
    session.add(ProjektDokument(
        projekt_id=projekt.id, gewerk_id=_id("gewerk_id"), ordner=ordner,
        dateiname=ziel.name, pfad=str(ziel),
        typ=("pdf" if endung == ".pdf"
             else "bild" if endung in (".jpg", ".jpeg", ".png", ".heic", ".webp")
             else "sonstige"),
        quelle="upload", hochgeladen_von=benutzer.id if benutzer else None,
        erstellt_von=benutzer.id if benutzer else None))
    session.commit()
    return RedirectResponse(f"/projektierung/projekt/{projekt_id}#dokumente",
                            status_code=303)


@router.get("/dokument/{dokument_id}")
async def dokument_anzeigen(request: Request, dokument_id: int,
                            session: Session = Depends(get_session)):
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    dokument = session.get(ProjektDokument, dokument_id)
    if dokument is None or not Path(dokument.pfad).exists():
        return RedirectResponse("/projektierung", status_code=303)
    medientyp = {"pdf": "application/pdf", "bild": "image/jpeg"}.get(
        dokument.typ, "application/octet-stream")
    if dokument.dateiname.lower().endswith(".png"):
        medientyp = "image/png"
    return FileResponse(dokument.pfad, media_type=medientyp,
                        content_disposition_type="inline",
                        filename=dokument.dateiname)


@router.post("/dokument/{dokument_id}/loeschen")
async def dokument_loeschen(request: Request, dokument_id: int,
                            session: Session = Depends(get_session)):
    """Löschen nur Projektierung/Admin, mit Protokoll im Verlauf."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    benutzer = request.state.benutzer
    if not (benutzer.rolle == "admin" or benutzer.hat_rolle("projektierung")):
        return RedirectResponse("/projektierung", status_code=303)
    dokument = session.get(ProjektDokument, dokument_id)
    if dokument is None:
        return RedirectResponse("/projektierung", status_code=303)
    projekt_id = dokument.projekt_id
    Path(dokument.pfad).unlink(missing_ok=True)
    kern.verlauf(session, projekt_id,
                 f"Dokument gelöscht: {dokument.ordner}/{dokument.dateiname}",
                 benutzer=benutzer)
    session.delete(dokument)
    session.commit()
    return RedirectResponse(f"/projektierung/projekt/{projekt_id}#dokumente",
                            status_code=303)


@router.post("/projekt/{projekt_id}/sub")
async def sub_zuordnen(request: Request, projekt_id: int,
                       session: Session = Depends(get_session)):
    if (umleitung := _gate(request, session, schreiben=True)) is not None:
        return umleitung
    projekt = session.get(Projekt, projekt_id)
    if projekt is None:
        return RedirectResponse("/projektierung", status_code=303)
    form = await request.form()
    def _id(name):
        try:
            return int(form.get(name) or 0) or None
        except ValueError:
            return None
    sub_id = _id("sub_id")
    sub = session.get(Subunternehmer, sub_id) if sub_id else None
    if sub is None:
        return RedirectResponse(f"/projektierung/projekt/{projekt_id}#subs",
                                status_code=303)
    termin = None
    if (form.get("termin") or "").strip():
        try:
            termin = datetime.strptime(form.get("termin"), "%Y-%m-%d")
        except ValueError:
            termin = None
    benutzer = request.state.benutzer
    session.add(ProjektSub(
        projekt_id=projekt.id, gewerk_id=_id("gewerk_id"), sub_id=sub.id,
        leistung=(form.get("leistung") or "").strip()[:300], termin=termin,
        notiz=(form.get("notiz") or "").strip()[:500],
        erstellt_von=benutzer.id if benutzer else None))
    kern.verlauf(session, projekt.id,
                 f"Sub zugeordnet: {sub.firma} – {form.get('leistung') or ''}",
                 benutzer=benutzer)
    session.commit()
    return RedirectResponse(f"/projektierung/projekt/{projekt_id}#subs",
                            status_code=303)


@router.post("/sub/{eintrag_id}/status")
async def sub_status(request: Request, eintrag_id: int,
                     session: Session = Depends(get_session)):
    if (umleitung := _gate(request, session, schreiben=True)) is not None:
        return umleitung
    eintrag = session.get(ProjektSub, eintrag_id)
    if eintrag is None:
        return RedirectResponse("/projektierung", status_code=303)
    form = await request.form()
    status = form.get("status") or ""
    if status in ("angefragt", "beauftragt", "bestaetigt", "erledigt"):
        eintrag.status = status
        session.commit()
    return RedirectResponse(f"/projektierung/projekt/{eintrag.projekt_id}#subs",
                            status_code=303)


@router.post("/gewerk/{gewerk_id}/storno")
async def gewerk_storno(request: Request, gewerk_id: int,
                        session: Session = Depends(get_session)):
    """Storno (Phase 66): Pflichtdialog Grund + Text; setzt das Angebot auf
    „Abgelehnt" (bestehende Ablehnungslogik inkl. monday-Rückspielung)."""
    if (umleitung := _gate(request, session, schreiben=True)) is not None:
        return umleitung
    gewerk = session.get(Gewerk, gewerk_id)
    if gewerk is None:
        return RedirectResponse("/projektierung", status_code=303)
    form = await request.form()
    ok, meldung = kern.gewerk_stornieren(
        session, gewerk, (form.get("grund") or "").strip(),
        form.get("text") or "", benutzer=request.state.benutzer)
    if ok:
        session.commit()
    else:
        session.rollback()
    return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}"
                            f"?meldung=" + quote_plus(meldung), status_code=303)
