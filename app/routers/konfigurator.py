# Konfigurator-UI (Phase 4): geführter Fragenfluss F01–F36 mit Bedingungen,
# ABBRUCH-Logik und Konfigurationsprotokoll. Ein Schritt pro Frage,
# Zurückspringen und Ändern jederzeit möglich.

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import konfigurator as engine
from app import logik as logik_modul
from app.db import get_session
from app.models import Konfiguration, Kunde
from app.templating import render

router = APIRouter(prefix="/konfigurator")


def _antworten(konfig: Konfiguration) -> dict:
    return json.loads(konfig.antworten_json or "{}")


def _status_aktualisieren(konfig: Konfiguration, logik, antworten: dict) -> None:
    meldung = engine.abbruch_status(logik, antworten)
    if meldung:
        konfig.status, konfig.abbruch_meldung = "abbruch", meldung
    elif engine.naechste_frage(logik, antworten) is None:
        konfig.status, konfig.abbruch_meldung = "fertig", ""
    else:
        konfig.status, konfig.abbruch_meldung = "laufend", ""


@router.get("")
async def start(request: Request, kunde_id: int = 0,
                session: Session = Depends(get_session)):
    kunden = (session.query(Kunde).filter(Kunde.aktiv.is_(True))
              .order_by(Kunde.firma, Kunde.nachname).all())
    return render(request, "konfigurator/start.html", aktiv="/angebote",
                  kunden=kunden, kunde_id=kunde_id)


@router.post("/start")
async def starten(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    try:
        kunde_id = int(form.get("kunde_id") or 0)
    except ValueError:
        kunde_id = 0
    kunde = session.get(Kunde, kunde_id)
    if kunde is None:
        return RedirectResponse("/konfigurator", status_code=303)
    konfig = Konfiguration(kunde_id=kunde.id)
    session.add(konfig)
    session.commit()
    return RedirectResponse(f"/konfigurator/{konfig.id}", status_code=303)


@router.get("/{konfig_id}")
async def schritt(request: Request, konfig_id: int, frage: str = "",
                  session: Session = Depends(get_session)):
    konfig = session.get(Konfiguration, konfig_id)
    if konfig is None:
        return RedirectResponse("/konfigurator", status_code=303)
    logik, bericht = logik_modul.hole_logik(session)
    if not bericht.ok:
        return render(request, "konfigurator/logikfehler.html", aktiv="/angebote",
                      bericht=bericht)
    kunde = session.get(Kunde, konfig.kunde_id)
    antworten = _antworten(konfig)
    prot = engine.protokoll(logik, antworten)
    klasse = engine.leistungsklasse(logik, antworten)
    paket = engine.paket_aufloesen(logik, antworten)

    # gezieltes Ändern einer bereits beantworteten Frage
    aktuelle = None
    if frage and frage in logik.fragen:
        kandidat = logik.fragen[frage]
        if engine.ist_sichtbar(kandidat, antworten, logik.fragen):
            aktuelle = kandidat
    if aktuelle is None and konfig.status == "laufend":
        aktuelle = engine.naechste_frage(logik, antworten)

    anzahl_wiederhol = 0
    if aktuelle and aktuelle.typ == "Wiederholfeld je Verteiler":
        anzahl_wiederhol = int(engine.zahl_parsen(antworten.get("F19")) or 1)

    beantwortet = len([p for p in prot])
    gesamt = len(engine.sichtbare_fragen(logik, antworten))

    return render(request, "konfigurator/schritt.html", aktiv="/angebote",
                  konfig=konfig, kunde=kunde, frage=aktuelle,
                  wert=antworten.get(aktuelle.id) if aktuelle else None,
                  protokoll=prot, klasse=klasse, paket=paket,
                  anzahl_wiederhol=anzahl_wiederhol,
                  beantwortet=beantwortet, gesamt=gesamt, fehler="")


@router.post("/{konfig_id}/antwort")
async def antwort(request: Request, konfig_id: int,
                  session: Session = Depends(get_session)):
    konfig = session.get(Konfiguration, konfig_id)
    if konfig is None:
        return RedirectResponse("/konfigurator", status_code=303)
    logik, _ = logik_modul.hole_logik(session)
    form = await request.form()
    frage_id = form.get("frage_id", "")
    frage = logik.fragen.get(frage_id)
    if frage is None:
        return RedirectResponse(f"/konfigurator/{konfig.id}", status_code=303)
    antworten = _antworten(konfig)

    wert, fehler = _wert_lesen(frage, form, antworten)
    if fehler:
        kunde = session.get(Kunde, konfig.kunde_id)
        prot = engine.protokoll(logik, antworten)
        return render(request, "konfigurator/schritt.html", aktiv="/angebote",
                      konfig=konfig, kunde=kunde, frage=frage,
                      wert=wert, protokoll=prot,
                      klasse=engine.leistungsklasse(logik, antworten),
                      paket=engine.paket_aufloesen(logik, antworten),
                      anzahl_wiederhol=int(engine.zahl_parsen(antworten.get("F19")) or 1),
                      beantwortet=len(prot),
                      gesamt=len(engine.sichtbare_fragen(logik, antworten)),
                      fehler=fehler)

    antworten[frage_id] = wert
    konfig.antworten_json = json.dumps(antworten, ensure_ascii=False)
    _status_aktualisieren(konfig, logik, antworten)
    session.commit()
    return RedirectResponse(f"/konfigurator/{konfig.id}", status_code=303)


def _wert_lesen(frage, form, antworten):
    """Liest und validiert den Antwortwert je Fragetyp. Liefert (wert, fehlertext)."""
    if frage.typ == "Auswahl":
        wert = (form.get("wert") or "").strip()
        if wert not in frage.antworten:
            return wert, "Bitte eine der Antwortmöglichkeiten wählen."
        return wert, ""

    if frage.typ in ("Zahleneingabe", "Betragseingabe"):
        roh = (form.get("wert") or "").strip()
        optional = "leer" in frage.hinweis.lower()
        if not roh and optional:
            return "", ""
        zahl = engine.zahl_parsen(roh)
        if zahl is None or zahl < 0:
            return roh, "Bitte eine gültige Zahl eingeben."
        return zahl, ""

    if frage.typ == "Mengenmaske (4 Zahlenfelder)":
        werte = {}
        for option in frage.antworten:
            roh = (form.get(f"wert_{option}") or "").strip()
            zahl = engine.zahl_parsen(roh) if roh else 0
            if zahl is None or zahl < 0 or zahl != int(zahl):
                return werte, f"Ungültige Anzahl bei Größe {option}."
            werte[option] = int(zahl)
        return werte, ""

    if frage.typ == "Wiederholfeld je Verteiler":
        anzahl = int(engine.zahl_parsen(antworten.get("F19")) or 0)
        werte = []
        for i in range(1, max(anzahl, 1) + 1):
            roh = (form.get(f"wert_{i}") or "").strip()
            zahl = engine.zahl_parsen(roh)
            if zahl is None or zahl <= 0 or zahl != int(zahl):
                return werte, f"Bitte für Verteiler {i} eine gültige Gruppenanzahl eingeben."
            werte.append(int(zahl))
        return werte, ""

    return None, f"Unbekannter Fragetyp {frage.typ}."
