# Benutzerverwaltung (Phase 13; seit Phase 18 nur Rolle Admin): Name, Rolle,
# PIN, E-Mail (v5, Pflicht für Außendienst – CC in der Angebots-Mail).
# Löschen (v5) nur ohne zugeordnete Vorgänge, sonst deaktivieren.

import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import auth
from app.db import get_session
from app.models import (Benutzer, Erfassung, Lead, MondayPerson, MondayQuelle)
from app.templating import render

router = APIRouter(prefix="/benutzer")

ROLLEN = ["admin", "innendienst", "aussendienst"]
_EMAIL_MUSTER = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def verknuepfungen(session: Session, benutzer_id: int) -> dict[str, int]:
    """Was hängt an diesem Benutzer? Leer = löschbar."""
    zaehler = {
        "Erfassungen": session.query(Erfassung)
        .filter(Erfassung.benutzer_id == benutzer_id).count(),
        "Leads": session.query(Lead).filter(Lead.benutzer_id == benutzer_id).count(),
        "monday-Zuordnungen": session.query(MondayPerson)
        .filter(MondayPerson.benutzer_id == benutzer_id).count()
        + session.query(MondayQuelle)
        .filter(MondayQuelle.fester_benutzer_id == benutzer_id).count(),
    }
    return {k: v for k, v in zaehler.items() if v}


def _email_pruefen(rolle: str, email: str) -> str | None:
    if email and not _EMAIL_MUSTER.match(email):
        return "E-Mail-Adresse ist ungültig"
    if rolle == "aussendienst" and not email:
        return "Für Außendienst-Benutzer ist eine E-Mail-Adresse Pflicht (CC im Versand)"
    return None


@router.get("")
async def liste(request: Request, session: Session = Depends(get_session)):
    benutzer = session.query(Benutzer).order_by(Benutzer.name).all()
    loeschbar = {b.id: not verknuepfungen(session, b.id) for b in benutzer}
    return render(request, "benutzer/liste.html", aktiv="/benutzer",
                  benutzer=benutzer, rollen=ROLLEN, loeschbar=loeschbar,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/neu")
async def anlegen(request: Request, session: Session = Depends(get_session)):
    from urllib.parse import quote_plus
    form = await request.form()
    name = (form.get("name") or "").strip()
    rolle = form.get("rolle") if form.get("rolle") in ROLLEN else "aussendienst"
    pin = (form.get("pin") or "").strip()
    email = (form.get("email") or "").strip().lower()
    if not name or not pin.isdigit() or len(pin) < 4:
        return RedirectResponse(
            "/benutzer?meldung=Name+und+PIN+(mind.+4+Ziffern)+erforderlich", status_code=303)
    if session.query(Benutzer).filter(Benutzer.name == name).first():
        return RedirectResponse("/benutzer?meldung=Name+bereits+vergeben", status_code=303)
    fehler = _email_pruefen(rolle, email)
    if fehler:
        return RedirectResponse(f"/benutzer?meldung={quote_plus(fehler)}", status_code=303)
    session.add(Benutzer(name=name, rolle=rolle, pin_hash=auth.pin_hash(pin), email=email))
    session.commit()
    return RedirectResponse("/benutzer?meldung=Benutzer+angelegt", status_code=303)


@router.post("/{benutzer_id}/aendern")
async def aendern(request: Request, benutzer_id: int,
                  session: Session = Depends(get_session)):
    from urllib.parse import quote_plus
    form = await request.form()
    benutzer = session.get(Benutzer, benutzer_id)
    if benutzer is None:
        return RedirectResponse("/benutzer", status_code=303)
    neuer_name = (form.get("name") or "").strip()
    if neuer_name and neuer_name != benutzer.name:
        if session.query(Benutzer).filter(Benutzer.name == neuer_name,
                                          Benutzer.id != benutzer.id).first():
            return RedirectResponse("/benutzer?meldung=Name+bereits+vergeben", status_code=303)
        benutzer.name = neuer_name
    rolle = form.get("rolle") if form.get("rolle") in ROLLEN else benutzer.rolle
    email = (form.get("email") or "").strip().lower()
    fehler = _email_pruefen(rolle, email)
    if fehler:
        return RedirectResponse(f"/benutzer?meldung={quote_plus(fehler)}", status_code=303)
    benutzer.rolle = rolle
    benutzer.email = email
    pin = (form.get("pin") or "").strip()
    if pin:
        if not pin.isdigit() or len(pin) < 4:
            return RedirectResponse("/benutzer?meldung=PIN+mind.+4+Ziffern", status_code=303)
        benutzer.pin_hash = auth.pin_hash(pin)
    benutzer.aktiv = form.get("aktiv") == "on"
    session.commit()
    return RedirectResponse("/benutzer?meldung=Gespeichert", status_code=303)


@router.post("/{benutzer_id}/loeschen")
async def loeschen(request: Request, benutzer_id: int,
                   session: Session = Depends(get_session)):
    """Löschen nur ohne Vorgänge; sonst wird deaktiviert (Historie bleibt)."""
    from urllib.parse import quote_plus
    benutzer = session.get(Benutzer, benutzer_id)
    if benutzer is None:
        return RedirectResponse("/benutzer", status_code=303)
    if benutzer.id == request.state.benutzer.id:
        return RedirectResponse("/benutzer?meldung=" + quote_plus(
            "Der eigene Benutzer kann nicht gelöscht werden."), status_code=303)
    haengt = verknuepfungen(session, benutzer.id)
    if haengt:
        benutzer.aktiv = False
        session.commit()
        details = ", ".join(f"{n} {k}" for k, n in haengt.items())
        return RedirectResponse("/benutzer?meldung=" + quote_plus(
            f"{benutzer.name} wurde deaktiviert statt gelöscht – zugeordnet: {details}. "
            "Der Benutzer erscheint in keiner Auswahlliste mehr, die Historie bleibt lesbar."),
            status_code=303)
    name = benutzer.name
    session.delete(benutzer)
    session.commit()
    return RedirectResponse("/benutzer?meldung=" + quote_plus(f"{name} gelöscht"),
                            status_code=303)
