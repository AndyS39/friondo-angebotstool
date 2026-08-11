# Benutzerverwaltung (Phase 13, nur Innendienst): Name, Rolle, PIN.

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import auth
from app.db import get_session
from app.models import Benutzer
from app.templating import render

router = APIRouter(prefix="/benutzer")

ROLLEN = ["innendienst", "aussendienst"]


@router.get("")
async def liste(request: Request, session: Session = Depends(get_session)):
    benutzer = session.query(Benutzer).order_by(Benutzer.name).all()
    return render(request, "benutzer/liste.html", aktiv="/benutzer",
                  benutzer=benutzer, rollen=ROLLEN,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/neu")
async def anlegen(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    name = (form.get("name") or "").strip()
    rolle = form.get("rolle") if form.get("rolle") in ROLLEN else "aussendienst"
    pin = (form.get("pin") or "").strip()
    if not name or not pin.isdigit() or len(pin) < 4:
        return RedirectResponse(
            "/benutzer?meldung=Name+und+PIN+(mind.+4+Ziffern)+erforderlich", status_code=303)
    if session.query(Benutzer).filter(Benutzer.name == name).first():
        return RedirectResponse("/benutzer?meldung=Name+bereits+vergeben", status_code=303)
    session.add(Benutzer(name=name, rolle=rolle, pin_hash=auth.pin_hash(pin)))
    session.commit()
    return RedirectResponse("/benutzer?meldung=Benutzer+angelegt", status_code=303)


@router.post("/{benutzer_id}/aendern")
async def aendern(request: Request, benutzer_id: int,
                  session: Session = Depends(get_session)):
    form = await request.form()
    benutzer = session.get(Benutzer, benutzer_id)
    if benutzer is None:
        return RedirectResponse("/benutzer", status_code=303)
    if form.get("rolle") in ROLLEN:
        benutzer.rolle = form.get("rolle")
    pin = (form.get("pin") or "").strip()
    if pin:
        if not pin.isdigit() or len(pin) < 4:
            return RedirectResponse("/benutzer?meldung=PIN+mind.+4+Ziffern", status_code=303)
        benutzer.pin_hash = auth.pin_hash(pin)
    benutzer.aktiv = form.get("aktiv") == "on"
    session.commit()
    return RedirectResponse("/benutzer?meldung=Gespeichert", status_code=303)
