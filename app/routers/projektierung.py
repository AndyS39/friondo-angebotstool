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
                        GEWERK_PHASEN, GEWERK_PHASEN_NAMEN, AUFGABE_STATUS_NAMEN)
from app.templating import render

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


# --- Phase 68: Kanban · Liste · Termine · Meine Aufgaben -------------------------

def _gewerk_zeilen(session: Session, benutzer, sparte: str = "",
                   projektleiter_id: int = 0, team_id: int = 0,
                   kanal: str = "", plz: str = "", q: str = "",
                   storniert: bool = False) -> list[dict]:
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
                 storniert: int = 0, session: Session = Depends(get_session)):
    """Kanban (Phase 68): Karte = Projekt in der Spalte seines abgeleiteten
    Status; der Sparten-Filter schaltet auf Karte-je-Gewerk um."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    zeilen = _gewerk_zeilen(session, request.state.benutzer, sparte=sparte,
                            projektleiter_id=projektleiter_id, team_id=team_id,
                            kanal=kanal, plz=plz, q=q,
                            storniert=bool(storniert))
    karte_je_gewerk = bool(sparte)
    spalten: dict[str, list] = {p: [] for p in GEWERK_PHASEN[:5]}
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
            spalten.setdefault(status if status in spalten else "feinplanung",
                               []).append(karte)
    from datetime import timedelta as _td
    return render(request, "projektierung/kanban.html", aktiv="/projektierung",
                  spalten=spalten, phasen_namen=GEWERK_PHASEN_NAMEN,
                  karte_je_gewerk=karte_je_gewerk,
                  # v11b (Phase 73, nur Anzeige): Kachelzeile über dem Board
                  kacheln=kern.startseiten_kacheln(session),
                  sparte=sparte, projektleiter_id=projektleiter_id,
                  team_id=team_id, kanal=kanal, plz=plz, q=q,
                  storniert=bool(storniert), heute=datetime.now(),
                  benutzer=request.state.benutzer,
                  **_filter_werte(session),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/gewerk/{gewerk_id}/phase-drop")
async def phase_drop(request: Request, gewerk_id: int,
                     session: Session = Depends(get_session)):
    """Drag & Drop vom Board: wie Phasenwechsel, mit optionaler Begründung
    (der Wächter-Hinweis erscheint als Meldung über dem Board)."""
    gewerk, umleitung = _gewerk_laden(request, session, gewerk_id)
    if umleitung is not None:
        return umleitung
    form = await request.form()
    ok, meldung = kern.phase_wechseln(session, gewerk, form.get("phase") or "",
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
                storniert: int = 0, sortierung: str = "projekt",
                export: str = "", session: Session = Depends(get_session)):
    """Gewerke als Tabelle (Phase 68) mit Summenzeile und CSV-Export."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    zeilen = _gewerk_zeilen(session, request.state.benutzer, sparte=sparte,
                            projektleiter_id=projektleiter_id, team_id=team_id,
                            kanal=kanal, plz=plz, q=q, storniert=bool(storniert))
    if sortierung == "kunde":
        zeilen.sort(key=lambda z: (z["kunde"].anzeige_name.lower()
                                   if z["kunde"] else "zzz"))
    elif sortierung == "phase":
        zeilen.sort(key=lambda z: GEWERK_PHASEN.index(z["gewerk"].phase))
    elif sortierung == "termin":
        zeilen.sort(key=lambda z: z["naechster_termin"] or datetime.max)
    elif sortierung == "wert":
        zeilen.sort(key=lambda z: -z["gewerk"].auftragswert_aktuell)
    else:
        sortierung = "projekt"
        zeilen.sort(key=lambda z: z["projekt"].nummer, reverse=True)
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
                            "Ampel", "Projektleiter", "Nächster Termin",
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
    aufgaben_gruppen: dict[int, list[tuple[int, list[Aufgabe]]]] = {}
    for gewerk_id, liste in aufgaben_je_gewerk.items():
        gruppen: dict[int, list[Aufgabe]] = {}
        for aufgabe in liste:
            gruppen.setdefault(aufgabe.paket_instanz_id or 0, []).append(aufgabe)
        aufgaben_gruppen[gewerk_id] = sorted(
            gruppen.items(), key=lambda paar: (paar[0] == 0, paar[0]))
    instanzen = {i.id: i for i in session.query(AufgabenpaketInstanz)
                 .filter(AufgabenpaketInstanz.gewerk_id.in_(
                     [g.id for g in gewerke] or [0]))}
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
    return RedirectResponse(f"/projektierung/projekt/{aufgabe.projekt_id}",
                            status_code=303)


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
    return RedirectResponse(f"/projektierung/projekt/{aufgabe.projekt_id}",
                            status_code=303)


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
                return datetime.strptime(roh, muster)
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
    session.add(ProjektTermin(
        gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id, typ=typ,
        beginn=beginn, ende=_zeit("ende"), team_id=_id("team_id"),
        person_id=_id("person_id"), sub_id=_id("sub_id"),
        kunde_bestaetigt=form.get("kunde_bestaetigt") == "on",
        notiz=(form.get("notiz") or "").strip()[:500],
        erstellt_von=request.state.benutzer.id if request.state.benutzer else None))
    session.flush()
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
