# Parametrierung (ehemals "Konfiguration", Phase 18): Logik-Excel einlesen,
# Validierungsbericht anzeigen, "Neu einlesen".

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import config, logik as logik_modul
from app.db import get_session
from app.templating import render

router = APIRouter(prefix="/parametrierung")


@router.get("")
async def uebersicht(request: Request, session: Session = Depends(get_session)):
    if not config.LOGIK_EXCEL_PFAD.exists():
        return render(request, "konfiguration/uebersicht.html", aktiv="/parametrierung",
                      logik=None, bericht=None, dateifehler=str(config.LOGIK_EXCEL_PFAD),
                      meldung="")
    from app.models import einstellung_holen
    logik, bericht = logik_modul.hole_logik(session)
    return render(request, "konfiguration/uebersicht.html", aktiv="/parametrierung",
                  logik=logik, bericht=bericht, dateifehler=None,
                  db_rot=einstellung_holen(session, "db_ampel_rot_unter", "9000"),
                  db_gruen=einstellung_holen(session, "db_ampel_gruen_ueber", "10000"),
                  fern_aktiv=einstellung_holen(session, "signatur_fern_aktiv", "0"),
                  fern_tage=einstellung_holen(session, "signatur_fern_gueltig_tage", "14"),
                  fern_basis=einstellung_holen(session, "signatur_fern_basis_url", ""),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/einstellungen")
async def einstellungen_speichern(request: Request,
                                  session: Session = Depends(get_session)):
    """DB-Ampel-Schwellen (Phase 24) und weitere pflegbare Werte."""
    from app.models import einstellung_setzen
    form = await request.form()
    for name in ("db_ampel_rot_unter", "db_ampel_gruen_ueber"):
        wert = (form.get(name) or "").strip().replace(".", "")
        if wert.isdigit():
            einstellung_setzen(session, name, wert)
    # Fern-Signatur (Phase 28): Schalter, Gültigkeitsdauer, öffentliche Basis-URL
    if "fern_formular" in form:
        einstellung_setzen(session, "signatur_fern_aktiv",
                           "1" if form.get("signatur_fern_aktiv") else "0")
        tage = (form.get("signatur_fern_gueltig_tage") or "").strip()
        if tage.isdigit() and int(tage) > 0:
            einstellung_setzen(session, "signatur_fern_gueltig_tage", tage)
        einstellung_setzen(session, "signatur_fern_basis_url",
                           (form.get("signatur_fern_basis_url") or "").strip().rstrip("/"))
    session.commit()
    return RedirectResponse("/parametrierung?meldung=Einstellungen+gespeichert",
                            status_code=303)


@router.get("/monday")
async def monday_uebersicht(request: Request, session: Session = Depends(get_session)):
    """monday-Anbindung (Phase 22): Quellen, Spalten-Mapping, Personen-Zuordnung."""
    from app import monday_sync
    from app.models import (Benutzer, MondayMapping, MondayPerson, MondayQuelle,
                            MONDAY_FELDER)
    monday_sync.quellen_vorbelegen(session)
    quellen = session.query(MondayQuelle).order_by(MondayQuelle.id).all()
    personen = session.query(MondayPerson).order_by(MondayPerson.monday_name).all()
    benutzer = session.query(Benutzer).filter(Benutzer.aktiv.is_(True)).all()
    mappings = {}
    spalten: dict[str, list] = {}
    spalten_fehler = ""
    for quelle in quellen:
        mappings[quelle.board_id] = {
            m.feld: m.spalten_id for m in session.query(MondayMapping)
            .filter(MondayMapping.board_id == quelle.board_id)}
        if config.MONDAY_API_TOKEN:
            try:
                spalten[quelle.board_id] = monday_sync.spalten_laden(quelle.board_id)
            except Exception as problem:
                spalten_fehler = str(problem)
    return render(request, "konfiguration/monday.html", aktiv="/parametrierung",
                  quellen=quellen, personen=personen, benutzer=benutzer,
                  mappings=mappings, spalten=spalten, felder=MONDAY_FELDER,
                  token_da=bool(config.MONDAY_API_TOKEN),
                  spalten_fehler=spalten_fehler,
                  sync_status=monday_sync.status,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/monday/quelle")
async def monday_quelle_speichern(request: Request,
                                  session: Session = Depends(get_session)):
    from app.models import MondayQuelle
    form = await request.form()
    quelle_id = form.get("quelle_id") or ""
    if quelle_id:
        quelle = session.get(MondayQuelle, int(quelle_id))
        if quelle is None:
            return RedirectResponse("/parametrierung/monday", status_code=303)
    else:
        if not (form.get("board_id") or "").strip():
            return RedirectResponse("/parametrierung/monday?meldung=Board-ID+fehlt",
                                    status_code=303)
        quelle = MondayQuelle(board_id=form.get("board_id").strip())
        session.add(quelle)
    quelle.board_name = (form.get("board_name") or "").strip()
    quelle.gruppen_titel = (form.get("gruppen_titel") or "Terminiert").strip()
    fester = form.get("fester_benutzer_id") or ""
    quelle.fester_benutzer_id = int(fester) if fester.isdigit() else None
    quelle.aktiv = form.get("aktiv") == "on"
    session.commit()
    return RedirectResponse("/parametrierung/monday?meldung=Quelle+gespeichert",
                            status_code=303)


@router.post("/monday/mapping/{board_id}")
async def monday_mapping_speichern(request: Request, board_id: str,
                                   session: Session = Depends(get_session)):
    from app.models import MondayMapping, MONDAY_FELDER
    form = await request.form()
    for feld in MONDAY_FELDER:
        eintrag = (session.query(MondayMapping)
                   .filter(MondayMapping.board_id == board_id,
                           MondayMapping.feld == feld).first())
        if eintrag is None:
            eintrag = MondayMapping(board_id=board_id, feld=feld)
            session.add(eintrag)
        eintrag.spalten_id = (form.get(feld) or "").strip()
    session.commit()
    return RedirectResponse("/parametrierung/monday?meldung=Mapping+gespeichert",
                            status_code=303)


@router.post("/monday/person/{person_id}")
async def monday_person_zuordnen(request: Request, person_id: int,
                                 session: Session = Depends(get_session)):
    from app.models import MondayPerson
    form = await request.form()
    person = session.get(MondayPerson, person_id)
    if person is not None:
        wert = form.get("benutzer_id") or ""
        person.benutzer_id = int(wert) if wert.isdigit() else None
        session.commit()
    return RedirectResponse("/parametrierung/monday?meldung=Zuordnung+gespeichert",
                            status_code=303)


@router.post("/neu-einlesen")
async def neu_einlesen(session: Session = Depends(get_session)):
    if not config.LOGIK_EXCEL_PFAD.exists():
        return RedirectResponse("/parametrierung", status_code=303)
    _, bericht = logik_modul.neu_einlesen(session)
    if bericht.ok:
        meldung = "Parametrierung+neu+eingelesen+–+keine+Fehler"
    else:
        meldung = f"Parametrierung+neu+eingelesen+–+{len(bericht.fehler)}+Fehler+gefunden"
    return RedirectResponse(f"/parametrierung?meldung={meldung}", status_code=303)
