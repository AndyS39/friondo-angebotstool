# Login/Logout (Phase 13): Benutzer wählen + PIN, signiertes Cookie.

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import auth
from app.db import get_session
from app.models import Benutzer
from app.templating import render

router = APIRouter()


@router.get("/login")
async def login_formular(request: Request, session: Session = Depends(get_session)):
    benutzer = (session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
                .order_by(Benutzer.name).all())
    return render(request, "anmeldung/login.html", aktiv=None,
                  benutzer=benutzer, fehler="")


@router.post("/login")
async def login(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    try:
        benutzer_id = int(form.get("benutzer_id") or 0)
    except ValueError:
        benutzer_id = 0
    pin = (form.get("pin") or "").strip()
    benutzer = session.get(Benutzer, benutzer_id)
    if (benutzer is None or not benutzer.aktiv
            or benutzer.pin_hash != auth.pin_hash(pin)):
        alle = (session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
                .order_by(Benutzer.name).all())
        return render(request, "anmeldung/login.html", aktiv=None,
                      benutzer=alle, fehler="Benutzer oder PIN falsch.")
    # v9-Portal: Innendienst landet nach dem Login direkt im Angebotstool
    # (das Portal „/“ ist über den Home-Link im Kopf erreichbar)
    ziel = "/erfassung" if benutzer.rolle == "aussendienst" else "/angebotstool"
    antwort = RedirectResponse(ziel, status_code=303)
    antwort.set_cookie(auth.COOKIE_NAME, auth.cookie_wert(benutzer.id),
                       httponly=True, max_age=60 * 60 * 12)
    return antwort


@router.get("/logout")
async def logout():
    antwort = RedirectResponse("/login", status_code=303)
    antwort.delete_cookie(auth.COOKIE_NAME)
    return antwort
