# Mobiler Montage-Bereich (v11, Phase 70, V1 reduziert): „Meine Einsätze“
# zeigt die Termine der eigenen Teams (heute/diese Woche); je Einsatz ein
# read-only-Steckbrief OHNE Preise, Foto-Upload und die Buttons „Montage
# gestartet“ / „Montage fertig“ (mit Pflicht-Kurzbericht → Verlauf).
# Zugriff: Rolle montage (oder Admin); im Demo-Modus nur Admin.

from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import projektierung as kern
from app.db import get_session
from app.models import (Angebot, Aufgabe, Benutzer, Gewerk, Kunde, Projekt,
                        ProjektDokument, ProjektTermin, Team, TeamMitglied,
                        AUFGABE_STATUS_NAMEN, GEWERK_PHASEN_NAMEN)
from app.templating import render

router = APIRouter(prefix="/montage")

FOTO_ORDNER = "03 Fotos/Neue Anlage"


def _gate(request: Request, session: Session):
    """Sichtbarkeit: Demo-Modus (nur Admin) + Rolle montage/admin."""
    benutzer = request.state.benutzer
    if benutzer is None:
        return RedirectResponse("/login", status_code=303)
    if not kern.modul_sichtbar(session, benutzer):
        return RedirectResponse("/", status_code=303)
    if not (benutzer.hat_rolle("montage") or benutzer.rolle == "admin"):
        return RedirectResponse("/", status_code=303)
    return None


def _eigene_teams(session: Session, benutzer) -> list[int]:
    return [m.team_id for m in session.query(TeamMitglied)
            .filter(TeamMitglied.benutzer_id == benutzer.id)]


def _einsatz_erlaubt(session: Session, benutzer, termin: ProjektTermin) -> bool:
    """Nur Einsätze der eigenen Teams (oder direkt zugeteilte Person);
    Admin sieht alles."""
    if benutzer.rolle == "admin":
        return True
    if termin.person_id == benutzer.id:
        return True
    return termin.team_id in _eigene_teams(session, benutzer)


@router.get("")
async def meine_einsaetze(request: Request, team_id: int = 0,
                          ansicht: str = "liste", start: str = "",
                          session: Session = Depends(get_session)):
    """v15 (Phase 82): Team-Auswahl → chronologische Liste (heute, diese
    Woche, danach; Vergangenes eingeklappt) oder Wochenkalender des Teams."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    benutzer = request.state.benutzer
    eigene = _eigene_teams(session, benutzer)
    if benutzer.rolle == "admin":
        teams = (session.query(Team).filter(Team.aktiv.is_(True))
                 .order_by(Team.typ, Team.name).all())
    else:
        teams = (session.query(Team).filter(Team.id.in_(eigene or [0]))
                 .order_by(Team.name).all())
    if team_id not in {te.id for te in teams}:
        team_id = 0
    if not team_id and len(teams) == 1:
        team_id = teams[0].id
    if not team_id:
        return render(request, "montage/einsaetze.html", aktiv="/montage",
                      mobil=True, benutzer=benutzer, teams=teams, team=None,
                      ansicht="liste",
                      meldung=request.query_params.get("meldung", ""))
    team = next(te for te in teams if te.id == team_id)
    abfrage = (session.query(ProjektTermin)
               .filter(ProjektTermin.beginn.isnot(None),
                       (ProjektTermin.team_id == team_id)
                       | (ProjektTermin.person_id == benutzer.id)))
    termine = abfrage.order_by(ProjektTermin.beginn).all()
    projekte = {p.id: p for p in session.query(Projekt)
                .filter(Projekt.id.in_({t.projekt_id for t in termine} or {0}))}
    gewerke = {g.id: g for g in session.query(Gewerk)
               .filter(Gewerk.id.in_({t.gewerk_id for t in termine if t.gewerk_id} or {0}))}
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({p.kunde_id for p in projekte.values()} or {0}))}
    steckbriefe = kern.steckbrief_daten(session, list(gewerke) or [0])
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
    return render(request, "montage/einsaetze.html", aktiv="/montage", mobil=True,
                  benutzer=benutzer, teams=teams, team=team,
                  ansicht=("kalender" if ansicht == "kalender" else "liste"),
                  vergangen=vergangen, heute_liste=heute_liste,
                  woche_liste=woche_liste, danach_liste=danach_liste,
                  tage=tage, kalender=kalender, heute=heute.date(),
                  zurueck=(montag - timedelta(days=7)).isoformat(),
                  vor=(montag + timedelta(days=7)).isoformat(),
                  projekte=projekte, gewerke=gewerke, kunden=kunden,
                  steckbriefe=steckbriefe, ts_map=ts_map,
                  meldung=request.query_params.get("meldung", ""))


@router.get("/einsatz/{termin_id}")
async def einsatz(request: Request, termin_id: int,
                  session: Session = Depends(get_session)):
    """Steckbrief read-only: Kunde, Ausführungsadresse (Karten-Link), Sparte,
    Positionen OHNE Preise, Bemerkung, Heizlast, Montage-Aufgaben, Fotos."""
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
    aufgaben = []
    if gewerk is not None:
        aufgaben = (session.query(Aufgabe)
                    .filter(Aufgabe.gewerk_id == gewerk.id,
                            Aufgabe.rolle == "montage",
                            Aufgabe.status.notin_(("erledigt", "entfaellt")))
                    .order_by(Aufgabe.faellig_am).all())
    dokumente = (session.query(ProjektDokument)
                 .filter(ProjektDokument.projekt_id == projekt.id,
                         ProjektDokument.typ == "bild")
                 .order_by(ProjektDokument.erstellt_am.desc()).limit(50).all())
    adresse = " ".join(x for x in (projekt.ausfuehrung_strasse,
                                   projekt.ausfuehrung_plz,
                                   projekt.ausfuehrung_ort) if x)
    # v15 (Phase 82): Steckbrief, Galerie, Ansprechpartner, Teams/Subs,
    # Restarbeiten, Formulare
    from app import galerie as galerie_modul
    from app.models import (MontageFormular, ProjektSub, Restarbeit,
                            Subunternehmer)
    from app import projektierung_logik
    steckbrief = (kern.steckbrief_daten(session, [gewerk.id])[gewerk.id]
                  if gewerk is not None else {})
    vorgang_id = angebot.vorgang_id if angebot is not None else None
    galerie_sparte = gewerk.sparte if gewerk is not None else "WP"
    galerie_daten = (galerie_modul.uebersicht(session, vorgang_id,
                                              galerie_sparte)
                     if vorgang_id else {})
    projektleiter = (session.get(Benutzer, projekt.projektleiter_id)
                     if projekt.projektleiter_id else None)
    team_termine = (session.query(ProjektTermin)
                    .filter(ProjektTermin.gewerk_id == gewerk.id,
                            ProjektTermin.beginn.isnot(None))
                    .order_by(ProjektTermin.beginn).all()
                    if gewerk is not None else [])
    teams_map = {te.id: te for te in session.query(Team)}
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
    return render(request, "montage/einsatz.html", aktiv="/montage", mobil=True,
                  benutzer=benutzer, termin=termin, projekt=projekt,
                  gewerk=gewerk, kunde=kunde, positionen=positionen,
                  aufgaben=aufgaben, dokumente=dokumente, adresse=adresse,
                  karten_link="https://www.google.com/maps/search/?api=1&query="
                              + quote_plus(adresse),
                  steckbrief=steckbrief,
                  steckbrief_felder=(kern.steckbrief_felder(gewerk.sparte)
                                     if gewerk is not None else []),
                  galerie_daten=galerie_daten, vorgang_id=vorgang_id,
                  galerie_sparte=galerie_sparte,
                  galerie_ordner=galerie_modul.ordner_liste(session,
                                                            galerie_sparte),
                  projektleiter=projektleiter,
                  team_termine=team_termine, teams_map=teams_map,
                  subs=subs, restarbeiten=restarbeiten, formulare=formulare,
                  phasen_namen=GEWERK_PHASEN_NAMEN,
                  status_namen=AUFGABE_STATUS_NAMEN,
                  meldung=request.query_params.get("meldung", ""))


@router.get("/dokument/{dokument_id}")
async def dokument_anzeigen(request: Request, dokument_id: int,
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
async def aufgabe_erledigt(request: Request, aufgabe_id: int,
                           session: Session = Depends(get_session)):
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    form = await request.form()
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
async def foto_hochladen(request: Request, termin_id: int,
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
    form = await request.form()
    datei = form.get("datei")
    ziel_meldung = f"/montage/einsatz/{termin_id}?meldung="
    if datei is None or not getattr(datei, "filename", ""):
        return RedirectResponse(ziel_meldung + quote_plus(
            "Bitte ein Foto wählen."), status_code=303)
    inhalt = await datei.read()
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


@router.get("/einsatz/{termin_id}/formular/{name}")
async def formular_seite(request: Request, termin_id: int, name: str,
                         session: Session = Depends(get_session)):
    """v15 (Phase 82): mobiles Formular (Blatt "Formulare"), seitenweise mit
    Zwischenspeichern; Felder inkl. Foto und Unterschrift (Canvas)."""
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
    return render(request, "montage/formular.html", aktiv="/montage", mobil=True,
                  benutzer=benutzer, termin=termin, gewerk=gewerk,
                  projekt=session.get(Projekt, termin.projekt_id),
                  name=name,
                  titel=projektierung_logik.FORMULAR_NAMEN.get(name, name),
                  eintrag=eintrag, seiten=seiten, seite=seite,
                  seiten_name=seiten[seite][0], felder=seiten[seite][1],
                  antworten=montage_formulare.antworten(eintrag),
                  offene_pflicht=montage_formulare.offene_pflicht(logik, eintrag),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/einsatz/{termin_id}/formular/{name}")
async def formular_speichern(request: Request, termin_id: int, name: str,
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
    form = await request.form()
    try:
        seite = max(0, min(int(form.get("seite") or 0), len(seiten) - 1))
    except ValueError:
        seite = 0
    await montage_formulare.seite_speichern(session, eintrag, gewerk,
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
    ziel = seite - 1 if aktion == "zurueck" else min(seite + 1, len(seiten) - 1)
    eintrag.seite_index = max(0, ziel)
    session.commit()
    return RedirectResponse(f"{basis}?seite={max(0, ziel)}", status_code=303)


@router.post("/einsatz/{termin_id}/restarbeit")
async def restarbeit_melden(request: Request, termin_id: int,
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
    form = await request.form()
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
            inhalt = await datei.read()
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
async def montage_phase(request: Request, termin_id: int,
                        session: Session = Depends(get_session)):
    """„Montage gestartet“ → In Ausführung; „Montage fertig“ → Abnahme offen
    (Pflichtfeld Kurzbericht → Verlauf)."""
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
    form = await request.form()
    aktion = form.get("aktion") or ""
    bericht = (form.get("bericht") or "").strip()
    ziel_meldung = f"/montage/einsatz/{termin_id}?meldung="
    # V4 (Phase 90.4): Uhrzeit im 15-Minuten-Takt (serverseitig gerundet)
    from datetime import datetime as _dt
    zeitpunkt = _dt.now()
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
        ok, meldung = kern.phase_wechseln(session, gewerk, "montage",
                                          f"Montage gestartet (mobil, {zeit_text})",
                                          benutzer=benutzer)
    elif aktion == "fertig":
        if not bericht:
            return RedirectResponse(ziel_meldung + quote_plus(
                "Bitte einen Kurzbericht eintragen (Pflicht bei Montage fertig)."),
                status_code=303)
        if gewerk.montage_fertig_am is None:
            gewerk.montage_fertig_am = zeitpunkt
        ok, meldung = kern.phase_wechseln(session, gewerk, "abnahme",
                                          f"Montage fertig (mobil, {zeit_text})",
                                          benutzer=benutzer)
        if ok:
            kern.verlauf(session, gewerk.projekt_id,
                         f"Montage-Kurzbericht: {bericht}", benutzer=benutzer,
                         gewerk_id=gewerk.id)
    else:
        return RedirectResponse(f"/montage/einsatz/{termin_id}", status_code=303)
    session.commit()
    return RedirectResponse(ziel_meldung + quote_plus(meldung), status_code=303)
