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
from app import anfrage   # v27: Formular/JSON in def-Routen

router = APIRouter(prefix="/kunden")

ANREDEN = ["", "Herr", "Frau", "Familie", "Firma"]

EMAIL_MUSTER = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _formular_lesen(form) -> dict:
    """Liest die Kundenfelder aus dem Formular (Whitespace bereinigt)."""
    felder = ["anrede", "firma", "vorname", "nachname", "strasse", "plz", "ort",
              "email", "telefon", "kunden_nr", "notizen"]
    daten = {f: (form.get(f) or "").strip() for f in felder}
    # Interesse (v5): Mehrfachauswahl als Checkboxen name="interesse"
    from app.models import interesse_text
    daten["interesse"] = interesse_text(form.getlist("interesse"))
    return daten


def _validieren(daten: dict) -> dict[str, str]:
    fehler = {}
    if not daten["nachname"] and not daten["firma"]:
        fehler["nachname"] = "Bitte Nachname oder Firma angeben."
    if daten["email"] and not EMAIL_MUSTER.match(daten["email"]):
        fehler["email"] = "Ungültige E-Mail-Adresse."
    if daten["anrede"] not in ANREDEN:
        fehler["anrede"] = "Unbekannte Anrede."
    return fehler


def _sortwert(k: Kunde, key: str):
    """v33 (PLAN_V20 Phase 174): Sortierwert je Spalte der Kundenliste (None = leer, ans Ende)."""
    from app import lead_boards
    if key == "lead":
        return lead_boards.sort_text(k.anzeige_name)
    if key == "adresse":
        return lead_boards.sort_text(f"{k.ort or ''} {k.plz or ''} {k.strasse or ''}")
    if key in ("email", "telefon", "kunden_nr", "objektart"):
        return lead_boards.sort_text(getattr(k, key, None))
    if key == "kanal":
        return lead_boards.sort_text(k.vertriebskanal)
    if key == "interessen":
        return lead_boards.sort_text(",".join(k.interessen))
    if key == "angelegt":
        return k.angelegt_am
    return None


@router.get("")
def liste(request: Request, q: str = "", inaktive: bool = False, kanal: str = "",
                objektart: str = "", session: Session = Depends(get_session)):
    """v33 (PLAN_V20 Phase 174): Lead-Board-Layout – Sticky-Filter (Suche, Kanal und
    Objektart als Chip-Selects, inaktive), Spalten je Nutzer (Katalog kunden), Sortierung per
    Spaltenkopf (gemerkt, vor dem Rendern angewendet; Standard bleibt Firma/Nachname/Vorname)."""
    abfrage = session.query(Kunde)
    from app import leadmanagement
    demo_kunden = leadmanagement.demo_kunden_ids(session)   # v12: Demo-Leads
    if demo_kunden:
        abfrage = abfrage.filter(Kunde.id.notin_(demo_kunden))
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
    if kanal:        # v33: Filter Vertriebskanal (Chip-Select)
        abfrage = abfrage.filter(Kunde.vertriebskanal == kanal)
    if objektart:    # v33: Filter Objektart (EFH/RH/REH/MFH, v23)
        abfrage = abfrage.filter(Kunde.objektart == objektart)
    kunden = abfrage.order_by(Kunde.firma, Kunde.nachname, Kunde.vorname).all()
    from app import lead_boards
    from app.models import OBJEKTART_CODES
    kanal_werte = sorted({w for (w,) in session.query(Kunde.vertriebskanal)
                          .filter(Kunde.vertriebskanal != "").distinct() if w}
                         | ({kanal} if kanal else set()))
    # Objektarten (Code, Bezeichnung) aus dem Blatt „Objektarten“ der Lead-Steuerdatei (v23),
    # Rückfall auf die Codes EFH/RH/REH/MFH
    try:
        from app import leadmanagement_logik
        objektart_werte = [(o.code, o.bezeichnung) for o in leadmanagement_logik.hole_logik().objektarten]
    except Exception:   # noqa: BLE001 – Steuerdatei fehlt/unlesbar: Codes reichen für den Filter
        objektart_werte = []
    if not objektart_werte:
        objektart_werte = [(code, code) for code in OBJEKTART_CODES]
    board = "kunden"
    benutzer = request.state.benutzer
    spalten = lead_boards.spalten_fuer(session, benutzer, board)
    sortierung = lead_boards.sortierung_fuer(session, benutzer, board)
    lead_boards.zeilen_sortieren(kunden, sortierung, wert=_sortwert)
    return render(request, "kunden/liste.html", aktiv="/kunden",
                  kunden=kunden, q=q, inaktive=inaktive, kanal=kanal, objektart=objektart,
                  kanal_werte=kanal_werte, objektart_werte=objektart_werte,
                  board=board, spalten=spalten, sortierung=sortierung,
                  ctx={"board": board, "sortierung": sortierung},
                  spalten_fest=lead_boards.spalten_fest(board),
                  nur_lesend=benutzer.basisrolle == "projektierung",
                  meldung=request.query_params.get("meldung", ""))


@router.get("/neu")
def neu_formular(request: Request):
    return render(request, "kunden/formular.html", aktiv="/kunden",
                  kunde=None, daten={}, fehler={}, anreden=ANREDEN)


@router.post("/neu")
def neu_speichern(request: Request, session: Session = Depends(get_session)):
    daten = _formular_lesen(anfrage.formular(request))
    fehler = _validieren(daten)
    if fehler:
        return render(request, "kunden/formular.html", aktiv="/kunden",
                      kunde=None, daten=daten, fehler=fehler, anreden=ANREDEN)
    kunde = Kunde(**daten)
    session.add(kunde)
    session.commit()
    return RedirectResponse("/kunden?meldung=Kunde+angelegt", status_code=303)


@router.get("/{kunde_id}/bearbeiten")
def bearbeiten_formular(request: Request, kunde_id: int,
                              session: Session = Depends(get_session)):
    kunde = session.get(Kunde, kunde_id)
    if kunde is None:
        return RedirectResponse("/kunden?meldung=Kunde+nicht+gefunden", status_code=303)
    return render(request, "kunden/formular.html", aktiv="/kunden",
                  kunde=kunde, daten={}, fehler={}, anreden=ANREDEN)


@router.post("/{kunde_id}/bearbeiten")
def bearbeiten_speichern(request: Request, kunde_id: int,
                               session: Session = Depends(get_session)):
    kunde = session.get(Kunde, kunde_id)
    if kunde is None:
        return RedirectResponse("/kunden?meldung=Kunde+nicht+gefunden", status_code=303)
    daten = _formular_lesen(anfrage.formular(request))
    fehler = _validieren(daten)
    if fehler:
        return render(request, "kunden/formular.html", aktiv="/kunden",
                      kunde=kunde, daten=daten, fehler=fehler, anreden=ANREDEN)
    for feld, wert in daten.items():
        setattr(kunde, feld, wert)
    # v31 (PLAN_LEAD_V5 Phase 153): Hauptobjekt(e) der Vorgänge dieses Kunden mitführen
    # (Hauptobjekt = Kundenadresse; Interessen/Objektart bleiben synchron)
    from app import objekte
    objekte.hauptobjekt_sync(session, kunde)
    session.commit()
    return RedirectResponse("/kunden?meldung=Kunde+gespeichert", status_code=303)


@router.post("/{kunde_id}/aktiv")
def aktiv_umschalten(kunde_id: int, aktiv: bool = Form(...),
                           session: Session = Depends(get_session)):
    kunde = session.get(Kunde, kunde_id)
    if kunde is not None:
        kunde.aktiv = aktiv
        session.commit()
        meldung = "Kunde+aktiviert" if aktiv else "Kunde+deaktiviert"
    else:
        meldung = "Kunde+nicht+gefunden"
    return RedirectResponse(f"/kunden?meldung={meldung}", status_code=303)
