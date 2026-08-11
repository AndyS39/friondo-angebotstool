# Erfassungsliste Innendienst (Phase 14): Ampel, Status, Filter/Suche,
# Detailansicht mit Korrekturmöglichkeit, Angebot erzeugen / manuelles Angebot.

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import angebot_aufbau
from app import konfigurator as engine
from app import logik as logik_modul
from app.db import get_session
from app.models import (ERFASSUNG_STATUS, Angebot, Benutzer, Erfassung, Kunde)
from app.templating import render

router = APIRouter(prefix="/erfassungen")


def _kontext(session: Session, erfassungen):
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_([e.kunde_id for e in erfassungen] or [0]))}
    benutzer = {b.id: b for b in session.query(Benutzer)}
    angebote = {a.id: a for a in session.query(Angebot)
                .filter(Angebot.id.in_([e.angebot_id for e in erfassungen
                                        if e.angebot_id] or [0]))}
    return kunden, benutzer, angebote


@router.get("")
async def liste(request: Request, q: str = "", status: str = "", ampel: str = "",
                session: Session = Depends(get_session)):
    abfrage = session.query(Erfassung).filter(Erfassung.status != "Entwurf")
    if status:
        abfrage = abfrage.filter(Erfassung.status == status)
    if ampel:
        abfrage = abfrage.filter(Erfassung.ampel == ampel)
    erfassungen = abfrage.order_by(Erfassung.abgesendet_am.desc()).all()
    kunden, benutzer, angebote = _kontext(session, erfassungen)
    if q:
        suchwort = q.lower()
        erfassungen = [e for e in erfassungen
                       if (e.kunde_id in kunden
                           and suchwort in kunden[e.kunde_id].anzeige_name.lower())
                       or (e.benutzer_id in benutzer
                           and suchwort in benutzer[e.benutzer_id].name.lower())]
    return render(request, "erfassungen/liste.html", aktiv="/erfassungen",
                  erfassungen=erfassungen, kunden=kunden, benutzer_map=benutzer,
                  angebote=angebote, q=q, status=status, ampel=ampel,
                  status_liste=ERFASSUNG_STATUS,
                  meldung=request.query_params.get("meldung", ""))


@router.get("/{erfassung_id}")
async def detail(request: Request, erfassung_id: int,
                 session: Session = Depends(get_session)):
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    logik, _ = logik_modul.hole_logik(session)
    antworten = json.loads(erfassung.antworten_json or "{}")
    prot = engine.protokoll(logik, antworten)
    kunde = session.get(Kunde, erfassung.kunde_id)
    vertriebler = session.get(Benutzer, erfassung.benutzer_id)
    angebot = session.get(Angebot, erfassung.angebot_id) if erfassung.angebot_id else None
    seiten = logik.seiten
    return render(request, "erfassungen/detail.html", aktiv="/erfassungen",
                  erfassung=erfassung, kunde=kunde, vertriebler=vertriebler,
                  protokoll=prot, angebot=angebot, seiten=seiten,
                  gruende=erfassung.gruende_text.splitlines(),
                  status_liste=ERFASSUNG_STATUS,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/{erfassung_id}/status")
async def status_aendern(request: Request, erfassung_id: int,
                         session: Session = Depends(get_session)):
    form = await request.form()
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is not None and form.get("status") in ERFASSUNG_STATUS:
        erfassung.status = form.get("status")
        session.commit()
    return RedirectResponse(f"/erfassungen/{erfassung_id}", status_code=303)


@router.get("/{erfassung_id}/angebot-erzeugen")
async def angebot_erzeugen(erfassung_id: int, session: Session = Depends(get_session)):
    """Grün: Antworten durch die Logik -> Angebotsentwurf; Erfassung verknüpfen."""
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    logik, bericht = logik_modul.hole_logik(session)
    if not bericht.ok:
        return RedirectResponse("/konfiguration", status_code=303)
    antworten = json.loads(erfassung.antworten_json or "{}")
    angebot = angebot_aufbau.angebot_anlegen(session, erfassung.kunde_id,
                                             antworten=antworten, logik=logik)
    erfassung.angebot_id = angebot.id
    if erfassung.status == "Neu":
        erfassung.status = "In Bearbeitung"
    session.commit()
    return RedirectResponse(f"/angebote/{angebot.id}", status_code=303)


@router.get("/{erfassung_id}/manuelles-angebot")
async def manuelles_angebot(erfassung_id: int, session: Session = Depends(get_session)):
    """Orange: leerer Editor mit Abfrageprotokoll als Seitenpanel."""
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    logik, _ = logik_modul.hole_logik(session)
    antworten = json.loads(erfassung.antworten_json or "{}")
    angebot = angebot_aufbau.angebot_anlegen(session, erfassung.kunde_id,
                                             antworten=antworten, logik=logik,
                                             nur_protokoll=True)
    erfassung.angebot_id = angebot.id
    if erfassung.status == "Neu":
        erfassung.status = "In Bearbeitung"
    session.commit()
    return RedirectResponse(f"/angebote/{angebot.id}", status_code=303)
