# Kundenverwaltung (Phase 1): Liste mit Suche, Anlegen, Bearbeiten, Deaktivieren.
# Kunden werden nie gelöscht, nur deaktiviert (Angebote müssen erhalten bleiben).

import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Kunde
from app.templating import render

router = APIRouter(prefix="/kunden")

ANREDEN = ["", "Herr", "Frau", "Familie", "Firma"]

EMAIL_MUSTER = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _formular_lesen(form) -> dict:
    """Liest die Kundenfelder aus dem Formular (Whitespace bereinigt)."""
    felder = ["anrede", "firma", "vorname", "nachname", "strasse", "plz", "ort",
              "email", "telefon", "kunden_nr", "notizen"]
    return {f: (form.get(f) or "").strip() for f in felder}


def _validieren(daten: dict) -> dict[str, str]:
    fehler = {}
    if not daten["nachname"] and not daten["firma"]:
        fehler["nachname"] = "Bitte Nachname oder Firma angeben."
    if daten["email"] and not EMAIL_MUSTER.match(daten["email"]):
        fehler["email"] = "Ungültige E-Mail-Adresse."
    if daten["anrede"] not in ANREDEN:
        fehler["anrede"] = "Unbekannte Anrede."
    return fehler


@router.get("")
async def liste(request: Request, q: str = "", inaktive: bool = False,
                session: Session = Depends(get_session)):
    abfrage = session.query(Kunde)
    if not inaktive:
        abfrage = abfrage.filter(Kunde.aktiv.is_(True))
    if q:
        suchwort = f"%{q}%"
        abfrage = abfrage.filter(or_(
            Kunde.firma.ilike(suchwort),
            Kunde.nachname.ilike(suchwort),
            Kunde.vorname.ilike(suchwort),
            Kunde.ort.ilike(suchwort),
            Kunde.kunden_nr.ilike(suchwort),
            Kunde.email.ilike(suchwort),
        ))
    kunden = abfrage.order_by(Kunde.firma, Kunde.nachname, Kunde.vorname).all()
    return render(request, "kunden/liste.html", aktiv="/kunden",
                  kunden=kunden, q=q, inaktive=inaktive,
                  meldung=request.query_params.get("meldung", ""))


@router.get("/neu")
async def neu_formular(request: Request):
    return render(request, "kunden/formular.html", aktiv="/kunden",
                  kunde=None, daten={}, fehler={}, anreden=ANREDEN)


@router.post("/neu")
async def neu_speichern(request: Request, session: Session = Depends(get_session)):
    daten = _formular_lesen(await request.form())
    fehler = _validieren(daten)
    if fehler:
        return render(request, "kunden/formular.html", aktiv="/kunden",
                      kunde=None, daten=daten, fehler=fehler, anreden=ANREDEN)
    kunde = Kunde(**daten)
    session.add(kunde)
    session.commit()
    return RedirectResponse("/kunden?meldung=Kunde+angelegt", status_code=303)


@router.get("/{kunde_id}/bearbeiten")
async def bearbeiten_formular(request: Request, kunde_id: int,
                              session: Session = Depends(get_session)):
    kunde = session.get(Kunde, kunde_id)
    if kunde is None:
        return RedirectResponse("/kunden?meldung=Kunde+nicht+gefunden", status_code=303)
    return render(request, "kunden/formular.html", aktiv="/kunden",
                  kunde=kunde, daten={}, fehler={}, anreden=ANREDEN)


@router.post("/{kunde_id}/bearbeiten")
async def bearbeiten_speichern(request: Request, kunde_id: int,
                               session: Session = Depends(get_session)):
    kunde = session.get(Kunde, kunde_id)
    if kunde is None:
        return RedirectResponse("/kunden?meldung=Kunde+nicht+gefunden", status_code=303)
    daten = _formular_lesen(await request.form())
    fehler = _validieren(daten)
    if fehler:
        return render(request, "kunden/formular.html", aktiv="/kunden",
                      kunde=kunde, daten=daten, fehler=fehler, anreden=ANREDEN)
    for feld, wert in daten.items():
        setattr(kunde, feld, wert)
    session.commit()
    return RedirectResponse("/kunden?meldung=Kunde+gespeichert", status_code=303)


@router.post("/{kunde_id}/aktiv")
async def aktiv_umschalten(kunde_id: int, aktiv: bool = Form(...),
                           session: Session = Depends(get_session)):
    kunde = session.get(Kunde, kunde_id)
    if kunde is not None:
        kunde.aktiv = aktiv
        session.commit()
        meldung = "Kunde+aktiviert" if aktiv else "Kunde+deaktiviert"
    else:
        meldung = "Kunde+nicht+gefunden"
    return RedirectResponse(f"/kunden?meldung={meldung}", status_code=303)
