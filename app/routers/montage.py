# Mobiler Montage-Bereich (v11, Phase 70, V1 reduziert): „Meine Einsätze“
# zeigt die Termine der eigenen Teams (heute/diese Woche); je Einsatz ein
# read-only-Steckbrief OHNE Preise, Foto-Upload und die Buttons „Montage
# gestartet“ / „Montage fertig“.
# Zugriff: Rolle montage (oder Admin); im Demo-Modus nur Admin.
#
# v28 (PLAN_PROJ_V6 Phase 137): Besetzung je Termin (Tabelle termin_besetzung) –
# „Meine Einsätze“ = Termine mit eigener Besetzung (Fallback für Termine ohne
# Besetzung: Team-Mitgliedschaft oder person_id), Team-Umschalter für Benutzer
# mit mehreren Teams und Admin/Projektierung [ANNAHME: Projektierung darf das
# Montage-Backend lesend öffnen – Team-Umschalter laut Plan]; Auftragsseite in
# neuer Reihenfolge (Kopf · Steckbrief vollständig · Teams & Termine · Notizen
# read-only · Montage starten/beenden · Formulare · Restarbeiten · Galerie),
# Block „Offene Montage-Aufgaben“ entfällt (Route /aufgabe/{id}/erledigt bleibt
# für den Übergang erreichbar, wird nicht mehr verlinkt), Kurzbericht beim
# Beenden optional [ANNAHME: Bemerkungen stehen im Montagebericht mb_bemerkung].

from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import notizen as notizen_modul
from app import projektierung as kern
from app.db import get_session
from app.models import (Angebot, Aufgabe, Benutzer, Gewerk, Kunde, Projekt,
                        ProjektDokument, ProjektTermin, Team, TeamMitglied,
                        TerminBesetzung, AUFGABE_STATUS_NAMEN, GEWERK_PHASEN_NAMEN)
from app.templating import render
from app import anfrage   # v27: Formular/JSON in def-Routen

router = APIRouter(prefix="/montage")

FOTO_ORDNER = "03 Fotos/Neue Anlage"
NOTIZEN_HINWEIS = "Bemerkungen bitte im Montagebericht eintragen."
NOTIZEN_LIMIT = 5
PHASEN_VOR_MONTAGE = ("auftragseingang", "feinplanung_vot", "planung",
                      "montagevorbereitung")
# Art eines Termins aus typ + zweck (Phase 135: zweck wp | elektro | sub | leer)
TERMIN_ARTEN = {("montage", "wp"): "Montage (WP)", ("montage", ""): "Montage",
                ("montage", "elektro"): "Elektro-Montage", ("montage", "sub"): "Sub-Einsatz",
                ("sub", ""): "Sub-Einsatz", ("sub", "sub"): "Sub-Einsatz",
                ("feinplanung", ""): "Feinplanung VOT", ("abnahme", ""): "Abnahme",
                ("sonstige", ""): "Sonstiges"}


def _ist_leitung(benutzer) -> bool:
    """Admin und Projektierung sehen alle Einsätze (Team-Umschalter)."""
    return benutzer is not None and (
        benutzer.rolle == "admin" or benutzer.hat_rolle("projektierung"))


def _gate(request: Request, session: Session):
    """Sichtbarkeit: Demo-Modus (nur Admin) + Rolle montage/admin
    (v28: Projektierung lesend, siehe Kopfkommentar)."""
    benutzer = request.state.benutzer
    if benutzer is None:
        return RedirectResponse("/login", status_code=303)
    if not kern.modul_sichtbar(session, benutzer):
        return RedirectResponse("/", status_code=303)
    if not (benutzer.hat_rolle("montage") or _ist_leitung(benutzer)):
        return RedirectResponse("/", status_code=303)
    return None


def _eigene_teams(session: Session, benutzer) -> list[int]:
    return [m.team_id for m in session.query(TeamMitglied)
            .filter(TeamMitglied.benutzer_id == benutzer.id)]


# --- Besetzung je Termin (v28, Vertrag mit P1: kern.besetzung_ids/-namen, sonst
#     eigene Leseabfrage auf termin_besetzung) ---------------------------------

def _besetzung_ids(session: Session, termin_id: int) -> list[int]:
    funktion = getattr(kern, "besetzung_ids", None)
    if callable(funktion):
        try:
            return [int(i) for i in funktion(session, termin_id)]
        except Exception:
            pass
    return [b.benutzer_id for b in session.query(TerminBesetzung)
            .filter(TerminBesetzung.termin_id == termin_id)
            .order_by(TerminBesetzung.id)]


def _besetzung_map(session: Session, termin_ids) -> dict[int, list[int]]:
    ergebnis: dict[int, list[int]] = {tid: [] for tid in termin_ids}
    if not termin_ids:
        return ergebnis
    for b in (session.query(TerminBesetzung)
              .filter(TerminBesetzung.termin_id.in_(list(termin_ids)))
              .order_by(TerminBesetzung.id)):
        ergebnis.setdefault(b.termin_id, []).append(b.benutzer_id)
    return ergebnis


def initialen(name: str) -> str:
    """„Max Müller“ → MM · „D. Jobelius“ → DJ · „Admin“ → AD (max. 3 Zeichen)."""
    teile = [t for t in (name or "").replace("-", " ").split() if t]
    if not teile:
        return "?"
    if len(teile) == 1:
        return teile[0][:2].upper()
    return "".join(t[0] for t in teile)[:3].upper()


def kurzname(name: str) -> str:
    """„Max Müller“ → „M. Müller“ (Chips in Terminzeilen)."""
    teile = [t for t in (name or "").split() if t]
    if len(teile) < 2:
        return name or ""
    return f"{teile[0][0]}. {' '.join(teile[1:])}"


def _personen(ids, benutzer_map: dict, ich_id=None) -> list[dict]:
    liste = []
    for bid in ids:
        b = benutzer_map.get(bid)
        name = b.name if b is not None else f"Benutzer {bid}"
        liste.append({"id": bid, "name": name, "kurz": kurzname(name),
                      "initialen": initialen(name), "ich": bid == ich_id})
    return liste


def _einsatz_erlaubt(session: Session, benutzer, termin: ProjektTermin,
                     besetzung: list[int] | None = None) -> bool:
    """v28: Benutzer steht in der Besetzung des Termins ODER (Fallback für
    Termine ohne Besetzung) ist Mitglied des Termin-Teams bzw. die zugeteilte
    Person; Admin/Projektierung alles."""
    if _ist_leitung(benutzer):
        return True
    ids = besetzung if besetzung is not None else _besetzung_ids(session, termin.id)
    if ids:
        return benutzer.id in ids
    if termin.person_id == benutzer.id:
        return True
    return termin.team_id in _eigene_teams(session, benutzer)


def termin_art(termin: ProjektTermin) -> str:
    typ = (termin.typ or "sonstige").lower()
    zweck = (getattr(termin, "zweck", "") or "").lower()
    return TERMIN_ARTEN.get((typ, zweck)) or TERMIN_ARTEN.get((typ, "")) or typ.capitalize()


def _termin_zeit(termin: ProjektTermin) -> str:
    if termin.beginn is None:
        return "–"
    text = termin.beginn.strftime("%d.%m.%Y")
    if not termin.ganztaegig or termin.beginn.strftime("%H:%M") != "00:00":
        text += f" {termin.beginn.strftime('%H:%M')} Uhr"
    if termin.ende and termin.ende.date() != termin.beginn.date():
        text += f" – {termin.ende.strftime('%d.%m.%Y')}"
    elif termin.ende and termin.ende.strftime("%H:%M") not in ("00:00", termin.beginn.strftime("%H:%M")):
        text += f" – {termin.ende.strftime('%H:%M')} Uhr"
    return text


@router.get("")
def meine_einsaetze(request: Request, team_id: int = 0,
                          ansicht: str = "liste", start: str = "",
                          session: Session = Depends(get_session)):
    """v15 (Phase 82): chronologische Liste (heute, diese Woche, danach;
    Vergangenes eingeklappt) oder Wochenkalender.
    v28 (Phase 137): Standardansicht „Meine Einsätze“ (Termine mit eigener
    Besetzung + Fallback), Team-Umschalter („Team <Name>“ = alle Termine des
    Teams) für Benutzer mit mehreren Teams und Admin/Projektierung."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    benutzer = request.state.benutzer
    eigene = _eigene_teams(session, benutzer)
    leitung = _ist_leitung(benutzer)
    if leitung:
        teams = (session.query(Team).filter(Team.aktiv.is_(True))
                 .order_by(Team.typ, Team.name).all())
    else:
        teams = (session.query(Team).filter(Team.id.in_(eigene or [0]))
                 .order_by(Team.name).all())
    team = next((te for te in teams if te.id == team_id), None) if team_id else None
    if team is None:
        # Meine Einsätze: eigene Besetzung ∪ (Termine ohne Besetzung: eigenes
        # Team oder eigene Person); vergangene bleiben für die Liste erhalten
        meine_termin_ids = {b.termin_id for b in session.query(TerminBesetzung)
                            .filter(TerminBesetzung.benutzer_id == benutzer.id)}
        bedingung = ((ProjektTermin.id.in_(meine_termin_ids or {0}))
                     | (ProjektTermin.person_id == benutzer.id))
        if eigene:
            bedingung = bedingung | ProjektTermin.team_id.in_(eigene)
        kandidaten = (session.query(ProjektTermin)
                      .filter(ProjektTermin.beginn.isnot(None), bedingung)
                      .order_by(ProjektTermin.beginn).all())
        besetzung = _besetzung_map(session, [t.id for t in kandidaten])
        termine = [t for t in kandidaten
                   if (benutzer.id in besetzung.get(t.id, []))
                   or (not besetzung.get(t.id)
                       and (t.person_id == benutzer.id or t.team_id in eigene))]
    else:
        termine = (session.query(ProjektTermin)
                   .filter(ProjektTermin.beginn.isnot(None),
                           ProjektTermin.team_id == team.id)
                   .order_by(ProjektTermin.beginn).all())
        besetzung = _besetzung_map(session, [t.id for t in termine])
    projekte = {p.id: p for p in session.query(Projekt)
                .filter(Projekt.id.in_({t.projekt_id for t in termine} or {0}))}
    gewerke = {g.id: g for g in session.query(Gewerk)
               .filter(Gewerk.id.in_({t.gewerk_id for t in termine if t.gewerk_id} or {0}))}
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({p.kunde_id for p in projekte.values()} or {0}))}
    steckbriefe = kern.steckbrief_daten(session, list(gewerke) or [0])
    benutzer_ids = {bid for ids in besetzung.values() for bid in ids}
    benutzer_map = {b.id: b for b in session.query(Benutzer)
                    .filter(Benutzer.id.in_(benutzer_ids or {0}))}
    besetzung_namen = {tid: _personen(ids, benutzer_map, benutzer.id)
                       for tid, ids in besetzung.items()}
    heute = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    woche_ende = heute + timedelta(days=7 - heute.weekday())
    vergangen = [t for t in termine
                 if (t.ende or t.beginn).date() < heute.date()]
    heute_liste = [t for t in termine
                   if t.beginn.date() <= heute.date() <= (t.ende or t.beginn).date()]
    woche_liste = [t for t in termine
                   if heute.date() < t.beginn.date() < woche_ende.date()]
    danach_liste = [t for t in termine if t.beginn.date() >= woche_ende.date()]
    # Wochenkalender: 7 Tage ab Montag (start = YYYY-MM-DD)
    try:
        start_datum = (datetime.strptime(start, "%Y-%m-%d").date()
                       if start else heute.date())
    except ValueError:
        start_datum = heute.date()
    montag = start_datum - timedelta(days=start_datum.weekday())
    tage = [montag + timedelta(days=i) for i in range(7)]
    kalender = {tag: [] for tag in tage}
    for t in termine:
        t_beginn = t.beginn.date()
        t_ende = (t.ende or t.beginn).date()
        for tag in tage:
            if t_beginn <= tag <= t_ende:
                kalender[tag].append(t)
    ts_map = {g.id: kern.terminstatus(session, g) for g in gewerke.values()}
    teams_map = {te.id: te for te in session.query(Team)}
    return render(request, "montage/einsaetze.html", aktiv="/montage", mobil=True,
                  benutzer=benutzer, teams=teams, team=team, meine=team is None,
                  leitung=leitung, eigene_teams=eigene, teams_map=teams_map,
                  ansicht=("kalender" if ansicht == "kalender" else "liste"),
                  vergangen=vergangen, heute_liste=heute_liste,
                  woche_liste=woche_liste, danach_liste=danach_liste,
                  tage=tage, kalender=kalender, heute=heute.date(),
                  zurueck=(montag - timedelta(days=7)).isoformat(),
                  vor=(montag + timedelta(days=7)).isoformat(),
                  projekte=projekte, gewerke=gewerke, kunden=kunden,
                  steckbriefe=steckbriefe, ts_map=ts_map,
                  besetzung_namen=besetzung_namen, termin_art=termin_art,
                  meldung=request.query_params.get("meldung", ""))


def steckbrief_zeilen(session: Session, gewerk: Gewerk) -> list[dict]:
    """v28 (Phase 137): alle Felder der Sparte in der Reihenfolge von
    kern.steckbrief_felder(sparte) (inkl. Auftragsdaten-Felder), leere als „–“ –
    derselbe Datenstand wie der Steckbrief der Projektakte. Hat das Gewerk noch
    gar keine Steckbrief-Werte (z. B. älterer Bestand), wird die Ableitung
    einmal nachgeholt (überschreibt nie manuelle Werte)."""
    from app.models import SteckbriefWert
    werte = kern.steckbrief_daten(session, [gewerk.id])[gewerk.id]
    if not werte and gewerk.angebot_id:
        try:
            if kern.steckbrief_ableiten(session, gewerk):
                session.commit()
                werte = kern.steckbrief_daten(session, [gewerk.id])[gewerk.id]
        except Exception:
            session.rollback()
            werte = kern.steckbrief_daten(session, [gewerk.id])[gewerk.id]
    zeilen = []
    for feld, name in kern.steckbrief_felder(gewerk.sparte):
        w = werte.get(feld)
        wert = (w.wert or "").strip() if w is not None else ""
        zeilen.append({"feld": feld, "name": name, "wert": wert or "–", "leer": not wert,
                       "manuell": bool(w is not None and w.manuell),
                       "auftragsdaten": bool(w is not None and (w.quelle or "") == "auftragsdaten")})
    return zeilen


def _termin_zeilen(session: Session, gewerk: Gewerk, benutzer_map: dict,
                   ich_id=None) -> list[dict]:
    termine = (session.query(ProjektTermin)
               .filter(ProjektTermin.gewerk_id == gewerk.id,
                       ProjektTermin.beginn.isnot(None))
               .order_by(ProjektTermin.beginn).all())
    besetzung = _besetzung_map(session, [t.id for t in termine])
    teams_map = {te.id: te for te in session.query(Team)}
    zeilen = []
    for t in termine:
        team = teams_map.get(t.team_id) if t.team_id else None
        person = benutzer_map.get(t.person_id) if t.person_id else None
        zeilen.append({"termin": t, "art": termin_art(t), "zeit": _termin_zeit(t),
                       "team": team.name if team else "",
                       "team_farbe": (team.farbe if team else "") or "",
                       "person": person.name if person else "",
                       "besetzung": _personen(besetzung.get(t.id, []), benutzer_map, ich_id),
                       "kunde_bestaetigt": bool(t.kunde_bestaetigt)})
    return zeilen


@router.get("/einsatz/{termin_id}")
def einsatz(request: Request, termin_id: int,
                  session: Session = Depends(get_session)):
    """Auftragsseite (v28-Reihenfolge): Kopf · Steckbrief vollständig · Gerät &
    Positionen (eingeklappt, ohne Preise) · Teams & Termine · Notizen der
    Projektierung (read-only) · Montage starten/beenden · Formulare ·
    Restarbeiten · Galerie."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    benutzer = request.state.benutzer
    termin = session.get(ProjektTermin, termin_id)
    if termin is None or not _einsatz_erlaubt(session, benutzer, termin):
        return RedirectResponse("/montage", status_code=303)
    projekt = session.get(Projekt, termin.projekt_id)
    gewerk = session.get(Gewerk, termin.gewerk_id) if termin.gewerk_id else None
    kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
    if projekt is None or kunde is None:
        return RedirectResponse("/montage", status_code=303)
    angebot = (session.get(Angebot, gewerk.angebot_id)
               if gewerk is not None and gewerk.angebot_id else None)
    positionen = list(angebot.positionen) if angebot is not None else []
    adresse = " ".join(x for x in (projekt.ausfuehrung_strasse,
                                   projekt.ausfuehrung_plz,
                                   projekt.ausfuehrung_ort) if x)
    from app import galerie as galerie_modul
    from app.models import (MontageFormular, ProjektSub, Restarbeit,
                            Subunternehmer)
    from app import projektierung_logik
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    steckbrief = steckbrief_zeilen(session, gewerk) if gewerk is not None else []
    vorgang_id = angebot.vorgang_id if angebot is not None else None
    galerie_sparte = gewerk.sparte if gewerk is not None else "WP"
    galerie_daten = (galerie_modul.uebersicht(session, vorgang_id,
                                              galerie_sparte)
                     if vorgang_id else {})
    projektleiter = (session.get(Benutzer, projekt.projektleiter_id)
                     if projekt.projektleiter_id else None)
    termin_zeilen = (_termin_zeilen(session, gewerk, benutzer_map, benutzer.id)
                     if gewerk is not None else [])
    diese = next((z for z in termin_zeilen if z["termin"].id == termin.id), None)
    if diese is None:
        team = session.get(Team, termin.team_id) if termin.team_id else None
        diese = {"termin": termin, "art": termin_art(termin), "zeit": _termin_zeit(termin),
                 "team": team.name if team else "", "team_farbe": (team.farbe if team else "") or "",
                 "person": "", "besetzung": _personen(_besetzung_ids(session, termin.id),
                                                      benutzer_map, benutzer.id),
                 "kunde_bestaetigt": bool(termin.kunde_bestaetigt)}
    subs = []
    if gewerk is not None:
        for eintrag in (session.query(ProjektSub)
                        .filter(ProjektSub.gewerk_id == gewerk.id)):
            subs.append({"eintrag": eintrag,
                         "sub": session.get(Subunternehmer, eintrag.sub_id)})
    restarbeiten = ((session.query(Restarbeit)
                     .filter(Restarbeit.gewerk_id == gewerk.id)
                     .order_by(Restarbeit.status.desc(), Restarbeit.id).all())
                    if gewerk is not None else [])
    logik = projektierung_logik.hole_logik(session)
    formulare = []
    if gewerk is not None:
        vorhandene = {f.formular: f for f in
                      session.query(MontageFormular)
                      .filter(MontageFormular.gewerk_id == gewerk.id)}
        for name, titel in projektierung_logik.FORMULAR_NAMEN.items():
            if name in logik.formulare:
                formulare.append({"name": name, "titel": titel,
                                  "eintrag": vorhandene.get(name)})
    # v28 (Phase 136/137): Notizen-Chat des Vorgangs – nur lesen, letzte fünf
    notizen_ctx = (notizen_modul.kontext(session, vorgang_id, benutzer,
                                         limit=NOTIZEN_LIMIT, nur_lesen=True,
                                         hinweis=NOTIZEN_HINWEIS)
                   if vorgang_id else None)
    return render(request, "montage/einsatz.html", aktiv="/montage", mobil=True,
                  benutzer=benutzer, termin=termin, projekt=projekt,
                  gewerk=gewerk, kunde=kunde, positionen=positionen,
                  adresse=adresse,
                  karten_link="https://www.google.com/maps/search/?api=1&query="
                              + quote_plus(adresse),
                  steckbrief=steckbrief, dieser_termin=diese,
                  galerie_daten=galerie_daten, vorgang_id=vorgang_id,
                  galerie_sparte=galerie_sparte,
                  galerie_ordner=galerie_modul.ordner_liste(session,
                                                            galerie_sparte),
                  projektleiter=projektleiter,
                  termin_zeilen=termin_zeilen, subs=subs,
                  restarbeiten=restarbeiten, formulare=formulare,
                  notizen_ctx=notizen_ctx, notizen_hinweis=NOTIZEN_HINWEIS,
                  phasen_namen=GEWERK_PHASEN_NAMEN,
                  phasen_vor_montage=PHASEN_VOR_MONTAGE,
                  status_namen=AUFGABE_STATUS_NAMEN,
                  meldung=request.query_params.get("meldung", ""))


@router.get("/dokument/{dokument_id}")
def dokument_anzeigen(request: Request, dokument_id: int,
                            session: Session = Depends(get_session)):
    """Fotos/Dokumente ansehen – die Rolle montage darf /projektierung nicht
    aufrufen, deshalb ein eigener Lesepfad."""
    from fastapi.responses import FileResponse
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    dokument = session.get(ProjektDokument, dokument_id)
    if dokument is None or not Path(dokument.pfad).exists():
        return RedirectResponse("/montage", status_code=303)
    medientyp = {"pdf": "application/pdf", "bild": "image/jpeg"}.get(
        dokument.typ, "application/octet-stream")
    if dokument.dateiname.lower().endswith(".png"):
        medientyp = "image/png"
    return FileResponse(dokument.pfad, media_type=medientyp,
                        content_disposition_type="inline",
                        filename=dokument.dateiname)


@router.post("/aufgabe/{aufgabe_id}/erledigt")
def aufgabe_erledigt(request: Request, aufgabe_id: int,
                           session: Session = Depends(get_session)):
    """Übergang (v28): der Block „Offene Montage-Aufgaben“ ist von der
    Auftragsseite verschwunden; die Route bleibt für alte Verweise erreichbar."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    form = anfrage.formular(request)
    zurueck = f"/montage/einsatz/{form.get('termin_id', '')}"
    aufgabe = session.get(Aufgabe, aufgabe_id)
    if aufgabe is None or aufgabe.rolle != "montage":
        return RedirectResponse("/montage", status_code=303)
    benutzer = request.state.benutzer
    aufgabe.status = "erledigt"
    aufgabe.erledigt_am = datetime.now()
    aufgabe.erledigt_von = benutzer.id
    kern.verlauf(session, aufgabe.projekt_id,
                 f"Montage-Aufgabe erledigt: {aufgabe.titel}",
                 benutzer=benutzer, gewerk_id=aufgabe.gewerk_id,
                 aufgabe_id=aufgabe.id)
    session.commit()
    # V4 (Phase 90.5): fetch-Antwort ohne Seitensprung
    if "application/json" in (request.headers.get("accept") or ""):
        from fastapi.responses import JSONResponse
        return JSONResponse({"ok": True, "meldung": f"Erledigt: {aufgabe.titel}"})
    return RedirectResponse(zurueck, status_code=303)


@router.post("/einsatz/{termin_id}/foto")
def foto_hochladen(request: Request, termin_id: int,
                         session: Session = Depends(get_session)):
    """Foto-Upload vom Handy in den Foto-Ordner des Gewerks (max. 20 MB)."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    benutzer = request.state.benutzer
    termin = session.get(ProjektTermin, termin_id)
    if termin is None or not _einsatz_erlaubt(session, benutzer, termin):
        return RedirectResponse("/montage", status_code=303)
    projekt = session.get(Projekt, termin.projekt_id)
    gewerk = session.get(Gewerk, termin.gewerk_id) if termin.gewerk_id else None
    form = anfrage.formular(request)
    datei = form.get("datei")
    ziel_meldung = f"/montage/einsatz/{termin_id}?meldung="
    if datei is None or not getattr(datei, "filename", ""):
        return RedirectResponse(ziel_meldung + quote_plus(
            "Bitte ein Foto wählen."), status_code=303)
    inhalt = datei.file.read()
    if len(inhalt) > 20 * 1024 * 1024:
        return RedirectResponse(ziel_meldung + quote_plus(
            "Datei größer als 20 MB – bitte kleinere Auflösung wählen."),
            status_code=303)
    ordner = FOTO_ORDNER
    if gewerk is not None:
        ordner = f"{gewerk.sparte}/{FOTO_ORDNER}"
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
    session.add(ProjektDokument(
        projekt_id=projekt.id, gewerk_id=gewerk.id if gewerk else None,
        ordner=ordner, dateiname=ziel.name, pfad=str(ziel),
        typ=("bild" if endung in (".jpg", ".jpeg", ".png", ".heic", ".webp")
             else "sonstige"),
        quelle="upload", hochgeladen_von=benutzer.id, erstellt_von=benutzer.id))
    session.commit()
    return RedirectResponse(ziel_meldung + quote_plus("Foto gespeichert."),
                            status_code=303)


def _mitarbeiter_vorbelegung(session: Session, termin: ProjektTermin) -> str:
    """v28 (Phase 138): „Mitarbeiter (Team)“ des Montageberichts mit der
    Besetzung des Termins vorbelegen (Namen, kommagetrennt); ohne Besetzung
    die Mitglieder des Termin-Teams."""
    ids = _besetzung_ids(session, termin.id)
    if not ids and termin.team_id:
        ids = [m.benutzer_id for m in session.query(TeamMitglied)
               .filter(TeamMitglied.team_id == termin.team_id).order_by(TeamMitglied.id)]
    if not ids:
        return ""
    namen = {b.id: b.name for b in session.query(Benutzer).filter(Benutzer.id.in_(ids))}
    return ", ".join(namen[i] for i in ids if i in namen)


@router.get("/einsatz/{termin_id}/formular/{name}")
def formular_seite(request: Request, termin_id: int, name: str,
                         session: Session = Depends(get_session)):
    """v15 (Phase 82): mobiles Formular (Blatt "Formulare"), seitenweise mit
    Zwischenspeichern; Felder inkl. Foto und Unterschrift (Canvas).
    v28 (Phase 138): wiederhol, gross, pflicht_wenn, Fotos mehrfach,
    mb_mitarbeiter mit der Besetzung vorbelegt."""
    from app import montage_formulare, projektierung_logik
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    benutzer = request.state.benutzer
    termin = session.get(ProjektTermin, termin_id)
    if termin is None or not _einsatz_erlaubt(session, benutzer, termin):
        return RedirectResponse("/montage", status_code=303)
    gewerk = session.get(Gewerk, termin.gewerk_id) if termin.gewerk_id else None
    logik = projektierung_logik.hole_logik(session)
    seiten = logik.formular_seiten(name)
    if gewerk is None or not seiten:
        return RedirectResponse(f"/montage/einsatz/{termin_id}?meldung="
                                + quote_plus("Formular nicht verfügbar."),
                                status_code=303)
    eintrag = montage_formulare.formular_holen(session, gewerk, name, benutzer)
    session.commit()
    try:
        seite = max(0, min(int(request.query_params.get(
            "seite", eintrag.seite_index or 0)), len(seiten) - 1))
    except ValueError:
        seite = 0
    antworten = montage_formulare.antworten(eintrag)
    if name == "montagebericht" and not str(antworten.get("mb_mitarbeiter") or "").strip():
        vorbelegung = _mitarbeiter_vorbelegung(session, termin)
        if vorbelegung:
            antworten["mb_mitarbeiter"] = vorbelegung
    felder_namen = {f.feld_key: f.bezeichnung for f in logik.formulare.get(name, [])}
    return render(request, "montage/formular.html", aktiv="/montage", mobil=True,
                  benutzer=benutzer, termin=termin, gewerk=gewerk,
                  projekt=session.get(Projekt, termin.projekt_id),
                  name=name,
                  titel=projektierung_logik.FORMULAR_NAMEN.get(name, name),
                  eintrag=eintrag, seiten=seiten, seite=seite,
                  seiten_name=seiten[seite][0], felder=seiten[seite][1],
                  antworten=antworten, felder_namen=felder_namen,
                  foto_werte=montage_formulare.foto_werte,
                  wiederhol_werte=montage_formulare.wiederhol_werte,
                  offene_pflicht=montage_formulare.offene_pflicht(logik, eintrag),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/einsatz/{termin_id}/formular/{name}")
def formular_speichern(request: Request, termin_id: int, name: str,
                             session: Session = Depends(get_session)):
    from app import montage_formulare, projektierung_logik
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    benutzer = request.state.benutzer
    termin = session.get(ProjektTermin, termin_id)
    if termin is None or not _einsatz_erlaubt(session, benutzer, termin):
        return RedirectResponse("/montage", status_code=303)
    gewerk = session.get(Gewerk, termin.gewerk_id) if termin.gewerk_id else None
    logik = projektierung_logik.hole_logik(session)
    seiten = logik.formular_seiten(name)
    if gewerk is None or not seiten:
        return RedirectResponse(f"/montage/einsatz/{termin_id}", status_code=303)
    eintrag = montage_formulare.formular_holen(session, gewerk, name, benutzer)
    form = anfrage.formular(request)
    try:
        seite = max(0, min(int(form.get("seite") or 0), len(seiten) - 1))
    except ValueError:
        seite = 0
    montage_formulare.seite_speichern(session, eintrag, gewerk,
                                            seiten[seite][1], form, benutzer)
    aktion = form.get("aktion") or "weiter"
    basis = f"/montage/einsatz/{termin_id}/formular/{name}"
    if aktion == "abschliessen":
        ok, meldung = montage_formulare.abschliessen(session, logik, eintrag,
                                                     gewerk, benutzer)
        session.commit()
        if ok:
            return RedirectResponse(f"/montage/einsatz/{termin_id}?meldung="
                                    + quote_plus(meldung), status_code=303)
        return RedirectResponse(f"{basis}?seite={seite}&meldung="
                                + quote_plus(meldung), status_code=303)
    if aktion == "bleiben":
        ziel = seite
    else:
        ziel = seite - 1 if aktion == "zurueck" else min(seite + 1, len(seiten) - 1)
    eintrag.seite_index = max(0, ziel)
    session.commit()
    return RedirectResponse(f"{basis}?seite={max(0, ziel)}", status_code=303)


@router.post("/einsatz/{termin_id}/restarbeit")
def restarbeit_melden(request: Request, termin_id: int,
                            session: Session = Depends(get_session)):
    """v15 (Phase 82): Restarbeit/Reklamation aus der Montage (Text + Foto
    in die Galerie Inbetrieb-/Abnahme)."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    benutzer = request.state.benutzer
    termin = session.get(ProjektTermin, termin_id)
    if termin is None or not _einsatz_erlaubt(session, benutzer, termin):
        return RedirectResponse("/montage", status_code=303)
    gewerk = session.get(Gewerk, termin.gewerk_id) if termin.gewerk_id else None
    if gewerk is None:
        return RedirectResponse(f"/montage/einsatz/{termin_id}", status_code=303)
    form = anfrage.formular(request)
    text = (form.get("text") or "").strip()[:500]
    if not text:
        return RedirectResponse(f"/montage/einsatz/{termin_id}?meldung="
                                + quote_plus("Bitte die Restarbeit beschreiben."),
                                status_code=303)
    from app.models import Restarbeit
    eintrag = Restarbeit(gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id,
                         text=text, erstellt_von=benutzer.id)
    datei = form.get("datei")
    if datei is not None and getattr(datei, "filename", ""):
        from app import galerie as galerie_modul
        angebot = (session.get(Angebot, gewerk.angebot_id)
                   if gewerk.angebot_id else None)
        if angebot is not None and angebot.vorgang_id:
            inhalt = datei.file   # v27 (Phase 128): wird in galerie.speichern gestreamt
            galerie_datei = galerie_modul.speichern(
                session, angebot.vorgang_id, "Inbetrieb-/Abnahme",
                datei.filename, inhalt, benutzer=benutzer,
                bemerkung=f"Restarbeit: {text[:100]}", quelle="formular",
                sparte=gewerk.sparte)
            if galerie_datei is not None:
                eintrag.galerie_datei_id = galerie_datei.id
    session.add(eintrag)
    kern.verlauf(session, gewerk.projekt_id,
                 f"Restarbeit gemeldet (Montage): {text[:120]}",
                 benutzer=benutzer, gewerk_id=gewerk.id)
    session.commit()
    return RedirectResponse(f"/montage/einsatz/{termin_id}?meldung="
                            + quote_plus("Restarbeit gemeldet."),
                            status_code=303)


@router.post("/einsatz/{termin_id}/phase")
def montage_phase(request: Request, termin_id: int,
                        session: Session = Depends(get_session)):
    """„Montage starten“ (Phasen auftragseingang … montagevorbereitung →
    montage, Begründung „Montage gestartet (mobil, <Zeit>)“ – im Modus warnen
    ohne Rückfrage, offene Punkte landen im Verlauf) und „Montage beenden“
    (Phase montage → abnahme, setzt montage_fertig_am; Kurzbericht optional
    → Verlauf). Aktionen: gestartet · fertig (Alias beenden)."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    benutzer = request.state.benutzer
    termin = session.get(ProjektTermin, termin_id)
    if termin is None or not _einsatz_erlaubt(session, benutzer, termin):
        return RedirectResponse("/montage", status_code=303)
    gewerk = session.get(Gewerk, termin.gewerk_id) if termin.gewerk_id else None
    if gewerk is None:
        return RedirectResponse(f"/montage/einsatz/{termin_id}?meldung="
                                + quote_plus("Kein Gewerk am Termin."),
                                status_code=303)
    form = anfrage.formular(request)
    aktion = form.get("aktion") or ""
    bericht = (form.get("bericht") or "").strip()[:1000]
    ziel_meldung = f"/montage/einsatz/{termin_id}?meldung="
    # V4 (Phase 90.4): Uhrzeit im 15-Minuten-Takt (serverseitig gerundet)
    zeitpunkt = datetime.now()
    try:
        stunde, _, minute = (form.get("uhrzeit") or "").partition(":")
        if stunde:
            zeitpunkt = zeitpunkt.replace(hour=int(stunde), minute=int(minute or 0),
                                          second=0, microsecond=0)
    except ValueError:
        pass
    zeitpunkt = kern.viertelstunde(zeitpunkt)
    zeit_text = zeitpunkt.strftime("%d.%m.%Y %H:%M")
    if aktion == "gestartet":
        if gewerk.phase not in PHASEN_VOR_MONTAGE:
            return RedirectResponse(ziel_meldung + quote_plus(
                f"Montage starten ist in Phase „{GEWERK_PHASEN_NAMEN.get(gewerk.phase, gewerk.phase)}“ "
                "nicht vorgesehen."), status_code=303)
        ok, meldung = kern.phase_wechseln(session, gewerk, "montage",
                                          f"Montage gestartet (mobil, {zeit_text})",
                                          benutzer=benutzer)
    elif aktion in ("fertig", "beenden"):
        if gewerk.phase != "montage":
            return RedirectResponse(ziel_meldung + quote_plus(
                "Montage beenden ist nur in der Phase „Montage“ möglich."), status_code=303)
        fertig_vorher = gewerk.montage_fertig_am
        if gewerk.montage_fertig_am is None:
            gewerk.montage_fertig_am = zeitpunkt
        ok, meldung = kern.phase_wechseln(session, gewerk, "abnahme",
                                          f"Montage beendet (mobil, {zeit_text})",
                                          benutzer=benutzer)
        if ok and bericht:
            kern.verlauf(session, gewerk.projekt_id,
                         f"Montage-Kurzbericht: {bericht}", benutzer=benutzer,
                         gewerk_id=gewerk.id)
        if not ok:
            gewerk.montage_fertig_am = fertig_vorher
    else:
        return RedirectResponse(f"/montage/einsatz/{termin_id}", status_code=303)
    session.commit()
    return RedirectResponse(ziel_meldung + quote_plus(meldung), status_code=303)
