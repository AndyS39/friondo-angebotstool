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
async def meine_einsaetze(request: Request, session: Session = Depends(get_session)):
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    benutzer = request.state.benutzer
    heute = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    bis = heute + timedelta(days=7)
    abfrage = (session.query(ProjektTermin)
               .filter(ProjektTermin.beginn.isnot(None),
                       ProjektTermin.beginn >= heute,
                       ProjektTermin.beginn < bis))
    if benutzer.rolle != "admin":
        team_ids = _eigene_teams(session, benutzer)
        abfrage = abfrage.filter(
            (ProjektTermin.team_id.in_(team_ids or [0]))
            | (ProjektTermin.person_id == benutzer.id))
    termine = abfrage.order_by(ProjektTermin.beginn).all()
    projekte = {p.id: p for p in session.query(Projekt)
                .filter(Projekt.id.in_({t.projekt_id for t in termine} or {0}))}
    gewerke = {g.id: g for g in session.query(Gewerk)
               .filter(Gewerk.id.in_({t.gewerk_id for t in termine if t.gewerk_id} or {0}))}
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({p.kunde_id for p in projekte.values()} or {0}))}
    heute_liste = [t for t in termine if t.beginn.date() == heute.date()]
    woche_liste = [t for t in termine if t.beginn.date() > heute.date()]
    return render(request, "montage/einsaetze.html", aktiv="/montage", mobil=True,
                  benutzer=benutzer, heute_liste=heute_liste, woche_liste=woche_liste,
                  projekte=projekte, gewerke=gewerke, kunden=kunden,
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
    return render(request, "montage/einsatz.html", aktiv="/montage", mobil=True,
                  benutzer=benutzer, termin=termin, projekt=projekt,
                  gewerk=gewerk, kunde=kunde, positionen=positionen,
                  aufgaben=aufgaben, dokumente=dokumente, adresse=adresse,
                  karten_link="https://www.google.com/maps/search/?api=1&query="
                              + quote_plus(adresse),
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
    if aktion == "gestartet":
        ok, meldung = kern.phase_wechseln(session, gewerk, "in_ausfuehrung",
                                          "Montage gestartet (mobil)",
                                          benutzer=benutzer)
    elif aktion == "fertig":
        if not bericht:
            return RedirectResponse(ziel_meldung + quote_plus(
                "Bitte einen Kurzbericht eintragen (Pflicht bei Montage fertig)."),
                status_code=303)
        ok, meldung = kern.phase_wechseln(session, gewerk, "abnahme_offen",
                                          "Montage fertig (mobil)",
                                          benutzer=benutzer)
        if ok:
            kern.verlauf(session, gewerk.projekt_id,
                         f"Montage-Kurzbericht: {bericht}", benutzer=benutzer,
                         gewerk_id=gewerk.id)
    else:
        return RedirectResponse(f"/montage/einsatz/{termin_id}", status_code=303)
    session.commit()
    return RedirectResponse(ziel_meldung + quote_plus(meldung), status_code=303)
