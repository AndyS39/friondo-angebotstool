# Artikelverwaltung (Phase 2): Liste mit Suche/Kategorie-Filter, manuelles
# Anlegen/Bearbeiten, Preislisten-Import mit Vorschau und Warnliste.

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import config, import_preisliste
from app.db import get_session
from app.models import Artikel, QUELLE_MANUELL
from app.templating import render

router = APIRouter(prefix="/artikel")


def preis_parsen(text: str):
    """'1.234,56' oder '1234.56' -> Cent; None bei ungültiger Eingabe."""
    text = text.strip().replace("€", "").strip()
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return int((Decimal(text) * 100).quantize(Decimal("1")))
    except InvalidOperation:
        return None


@router.get("")
async def liste(request: Request, q: str = "", kategorie: str = "", inaktive: bool = False,
                fehlend: bool = False, session: Session = Depends(get_session)):
    abfrage = session.query(Artikel)
    if not inaktive:
        abfrage = abfrage.filter(Artikel.aktiv.is_(True))
    if kategorie:
        abfrage = abfrage.filter(Artikel.kategorie == kategorie)
    if q:
        suchwort = f"%{q}%"
        abfrage = abfrage.filter(or_(
            Artikel.pos_nr.ilike(suchwort),
            Artikel.bezeichnung.ilike(suchwort),
            Artikel.beschreibung.ilike(suchwort),
            Artikel.kategorie.ilike(suchwort),
            Artikel.artikelnummer.ilike(suchwort),
        ))
    artikel = abfrage.order_by(Artikel.pos_nr, Artikel.id).all()
    # Phase 24: EK fehlt (leer) oder VK fehlt (0) markieren + Banner mit Filter
    ohne_preis = [a for a in artikel if a.ek_cent is None or not a.e_preis_cent]
    if fehlend:
        artikel = ohne_preis
    kategorien = [k for (k,) in session.query(Artikel.kategorie).distinct()
                  .order_by(Artikel.kategorie) if k]
    return render(request, "artikel/liste.html", aktiv="/artikel",
                  artikel=artikel, kategorien=kategorien, q=q,
                  kategorie=kategorie, inaktive=inaktive, fehlend=fehlend,
                  ohne_preis_anzahl=len(ohne_preis),
                  meldung=request.query_params.get("meldung", ""))


# --- Import ---------------------------------------------------------------

@router.get("/import")
async def import_vorschau(request: Request, session: Session = Depends(get_session)):
    fehlend = [str(p) for p in (config.PREISLISTE_PFAD, config.LOGIK_EXCEL_PFAD)
               if not p.exists()]
    if fehlend:
        return render(request, "artikel/import_vorschau.html", aktiv="/artikel",
                      diff=None, dateifehler=fehlend)
    ergebnis = import_preisliste.lese_dateien()
    diff = import_preisliste.berechne_diff(session, ergebnis)
    return render(request, "artikel/import_vorschau.html", aktiv="/artikel",
                  diff=diff, dateifehler=[])


@router.post("/import")
async def import_ausfuehren(session: Session = Depends(get_session)):
    diff, meldung = import_preisliste.import_ausfuehren(session)
    return RedirectResponse(f"/artikel?meldung=Import+abgeschlossen:+{meldung.replace(' ', '+')}",
                            status_code=303)


# --- Manuelles Anlegen / Bearbeiten --------------------------------------

def _formular_lesen(form) -> dict:
    felder = ["pos_nr", "kategorie", "bezeichnung", "beschreibung", "einheit"]
    daten = {f: (form.get(f) or "").strip() for f in felder}
    daten["e_preis"] = (form.get("e_preis") or "").strip()
    daten["ek_preis"] = (form.get("ek_preis") or "").strip()   # Phase 18: EK änderbar
    daten["menge_standard"] = (form.get("menge_standard") or "1").strip()
    daten["ep_flag"] = form.get("ep_flag") == "on"
    return daten


def _validieren(daten: dict) -> dict[str, str]:
    fehler = {}
    if not daten["bezeichnung"] and not daten["beschreibung"]:
        fehler["bezeichnung"] = "Bitte Bezeichnung oder Beschreibung angeben."
    if preis_parsen(daten["e_preis"]) is None:
        fehler["e_preis"] = "Ungültiger Preis (z. B. 1.234,56)."
    if daten["ek_preis"] and preis_parsen(daten["ek_preis"]) is None:
        fehler["ek_preis"] = "Ungültiger EK-Preis (z. B. 1.234,56, leer = kein EK)."
    try:
        float(daten["menge_standard"].replace(",", "."))
    except ValueError:
        fehler["menge_standard"] = "Ungültige Menge."
    return fehler


def _uebernehmen(artikel: Artikel, daten: dict) -> None:
    artikel.pos_nr = daten["pos_nr"]
    artikel.kategorie = daten["kategorie"]
    artikel.bezeichnung = daten["bezeichnung"]
    artikel.beschreibung = daten["beschreibung"]
    artikel.einheit = daten["einheit"]
    artikel.menge_standard = float(daten["menge_standard"].replace(",", "."))
    artikel.e_preis_cent = preis_parsen(daten["e_preis"])
    artikel.ek_cent = preis_parsen(daten["ek_preis"]) if daten["ek_preis"] else None
    artikel.ep_flag = daten["ep_flag"]


def _kategorien(session: Session) -> list[str]:
    return [k for (k,) in session.query(Artikel.kategorie).distinct()
            .order_by(Artikel.kategorie) if k]


@router.get("/neu")
async def neu_formular(request: Request, session: Session = Depends(get_session)):
    return render(request, "artikel/formular.html", aktiv="/artikel",
                  artikel=None, daten={}, fehler={}, kategorien=_kategorien(session))


@router.post("/neu")
async def neu_speichern(request: Request, session: Session = Depends(get_session)):
    daten = _formular_lesen(await request.form())
    fehler = _validieren(daten)
    if fehler:
        return render(request, "artikel/formular.html", aktiv="/artikel",
                      artikel=None, daten=daten, fehler=fehler,
                      kategorien=_kategorien(session))
    artikel = Artikel(quelle=QUELLE_MANUELL, aktiv=True)
    _uebernehmen(artikel, daten)
    session.add(artikel)
    session.commit()
    return RedirectResponse("/artikel?meldung=Artikel+angelegt", status_code=303)


@router.get("/{artikel_id}/bearbeiten")
async def bearbeiten_formular(request: Request, artikel_id: int,
                              session: Session = Depends(get_session)):
    artikel = session.get(Artikel, artikel_id)
    if artikel is None:
        return RedirectResponse("/artikel?meldung=Artikel+nicht+gefunden", status_code=303)
    return render(request, "artikel/formular.html", aktiv="/artikel",
                  artikel=artikel, daten={}, fehler={}, kategorien=_kategorien(session))


@router.post("/{artikel_id}/bearbeiten")
async def bearbeiten_speichern(request: Request, artikel_id: int,
                               session: Session = Depends(get_session)):
    artikel = session.get(Artikel, artikel_id)
    if artikel is None:
        return RedirectResponse("/artikel?meldung=Artikel+nicht+gefunden", status_code=303)
    form = await request.form()
    daten = _formular_lesen(form)
    fehler = _validieren(daten)
    if fehler:
        return render(request, "artikel/formular.html", aktiv="/artikel",
                      artikel=artikel, daten=daten, fehler=fehler,
                      kategorien=_kategorien(session))
    _uebernehmen(artikel, daten)
    artikel.aktiv = form.get("aktiv") == "on"
    session.commit()
    return RedirectResponse("/artikel?meldung=Artikel+gespeichert", status_code=303)
