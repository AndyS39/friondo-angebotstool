# Mobile Außendienst-Erfassung (Phase 13): eine Seite pro Kategorie, große
# Bedienelemente, Fortschritt, vor/zurück, Pflichtfeld-Prüfung. Der Außendienst
# sieht keine Preise, EKs, Deckungsbeiträge und keinen Angebotsbereich.

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import konfigurator as engine
from app import logik as logik_modul
from app.db import get_session
from app.logik import FREITEXT_TYPEN
from app.models import Erfassung, Kunde
from app.templating import render

router = APIRouter(prefix="/erfassung")


def _benutzer(request: Request):
    return request.state.benutzer


def _antworten(erfassung: Erfassung) -> dict:
    return json.loads(erfassung.antworten_json or "{}")


def _fragen_der_seite(logik, seite: str):
    return [f for f in sorted(logik.fragen.values(), key=lambda f: f.reihenfolge)
            if f.seite == seite]


def _ist_optional(frage) -> bool:
    if frage.typ == "Freitext groß":
        return True
    return "leer" in frage.hinweis.lower()


def _client_regel(frage) -> str:
    """Sichtbarkeitsregel für das Seiten-JavaScript (Folgefragen derselben Seite)."""
    b = frage.bedingung
    if b is None or b.art == "immer":
        return json.dumps({"art": "immer"})
    if b.art == "antwort":
        return json.dumps({"art": "antwort", "frage": b.frage_id, "werte": b.werte},
                          ensure_ascii=False)
    if b.art == "ausgefuellt":
        return json.dumps({"art": "ausgefuellt", "frage": b.frage_id})
    if b.art == "selbstnutzung":
        return json.dumps({"art": "selbstnutzung"})
    if b.art == "klauseln":
        return json.dumps({"art": "klauseln",
                           "klauseln": [[{"frage": fid, "werte": werte}
                                         for fid, werte in klausel]
                                        for klausel in b.klauseln]}, ensure_ascii=False)
    return json.dumps({"art": "immer"})


@router.get("")
async def uebersicht(request: Request, session: Session = Depends(get_session)):
    benutzer = _benutzer(request)
    erfassungen = (session.query(Erfassung)
                   .filter(Erfassung.benutzer_id == benutzer.id)
                   .order_by(Erfassung.angelegt_am.desc()).limit(25).all())
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_([e.kunde_id for e in erfassungen] or [0]))}
    return render(request, "erfassung/uebersicht.html", aktiv=None, mobil=True,
                  benutzer=benutzer, erfassungen=erfassungen, kunden=kunden)


@router.get("/neu")
async def neu_formular(request: Request, session: Session = Depends(get_session)):
    kunden = (session.query(Kunde).filter(Kunde.aktiv.is_(True))
              .order_by(Kunde.firma, Kunde.nachname).all())
    return render(request, "erfassung/neu.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), kunden=kunden, fehler="")


@router.post("/neu")
async def neu(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    kunde = None
    if form.get("kunde_id"):
        try:
            kunde = session.get(Kunde, int(form.get("kunde_id")))
        except ValueError:
            kunde = None
    elif (form.get("nachname") or "").strip() or (form.get("firma") or "").strip():
        kunde = Kunde(
            anrede=(form.get("anrede") or "").strip(),
            firma=(form.get("firma") or "").strip(),
            vorname=(form.get("vorname") or "").strip(),
            nachname=(form.get("nachname") or "").strip(),
            strasse=(form.get("strasse") or "").strip(),
            plz=(form.get("plz") or "").strip(),
            ort=(form.get("ort") or "").strip(),
            email=(form.get("email") or "").strip(),
            telefon=(form.get("telefon") or "").strip(),
        )
        session.add(kunde)
        session.flush()
    if kunde is None:
        kunden = (session.query(Kunde).filter(Kunde.aktiv.is_(True))
                  .order_by(Kunde.firma, Kunde.nachname).all())
        return render(request, "erfassung/neu.html", aktiv=None, mobil=True,
                      benutzer=_benutzer(request), kunden=kunden,
                      fehler="Bitte Kunden wählen oder Name/Firma eingeben.")
    erfassung = Erfassung(kunde_id=kunde.id, benutzer_id=_benutzer(request).id)
    session.add(erfassung)
    session.commit()
    return RedirectResponse(f"/erfassung/{erfassung.id}/weiche", status_code=303)


@router.get("/{erfassung_id}/weiche")
async def weiche(request: Request, erfassung_id: int,
                 session: Session = Depends(get_session)):
    """Startweiche (v7): Erfassungsbogen (Katalog) oder Freitext-Erfassung."""
    erfassung = _erfassung_laden(request, erfassung_id, session)
    if erfassung is None:
        return RedirectResponse("/erfassung", status_code=303)
    kunde = session.get(Kunde, erfassung.kunde_id)
    return render(request, "erfassung/weiche.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), erfassung=erfassung, kunde=kunde)


@router.get("/{erfassung_id}/freitext")
async def freitext_formular(request: Request, erfassung_id: int,
                            session: Session = Depends(get_session)):
    """Freitext-Erfassung (v7): großes Pflicht-Textfeld; bei Wechsel aus dem
    Katalog bleiben die bereits gegebenen Antworten im Protokoll erhalten."""
    erfassung = _erfassung_laden(request, erfassung_id, session)
    if erfassung is None:
        return RedirectResponse("/erfassung", status_code=303)
    kunde = session.get(Kunde, erfassung.kunde_id)
    hat_antworten = bool(_antworten(erfassung))
    return render(request, "erfassung/freitext.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), erfassung=erfassung, kunde=kunde,
                  hat_antworten=hat_antworten, fehler="")


@router.post("/{erfassung_id}/freitext")
async def freitext_absenden(request: Request, erfassung_id: int,
                            session: Session = Depends(get_session)):
    """Freitext absenden (v7): keine Vorprüfung – Ampel Individuell und
    Status direkt „In TAIFUN zu schreiben“."""
    erfassung = _erfassung_laden(request, erfassung_id, session)
    if erfassung is None:
        return RedirectResponse("/erfassung", status_code=303)
    form = await request.form()
    text = (form.get("freitext") or "").strip()
    if not text:
        kunde = session.get(Kunde, erfassung.kunde_id)
        return render(request, "erfassung/freitext.html", aktiv=None, mobil=True,
                      benutzer=_benutzer(request), erfassung=erfassung, kunde=kunde,
                      hat_antworten=bool(_antworten(erfassung)),
                      fehler="Bitte die Beschreibung ausfüllen.")
    erfassung.typ = "freitext"
    erfassung.freitext = text
    erfassung.ampel = "orange"
    erfassung.gruende_text = "vom Außendienst als individuell erfasst"
    erfassung.status = "In TAIFUN zu schreiben"
    erfassung.abgesendet_am = datetime.now()
    session.commit()
    return render(request, "erfassung/fertig.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), erfassung=erfassung)


def _erfassung_laden(request: Request, erfassung_id: int, session: Session):
    erfassung = session.get(Erfassung, erfassung_id)
    benutzer = _benutzer(request)
    if erfassung is None:
        return None
    if benutzer.rolle == "aussendienst" and erfassung.benutzer_id != benutzer.id:
        return None
    return erfassung


@router.get("/{erfassung_id}/seite/{nr}")
async def seite(request: Request, erfassung_id: int, nr: int,
                session: Session = Depends(get_session)):
    erfassung = _erfassung_laden(request, erfassung_id, session)
    if erfassung is None:
        return RedirectResponse("/erfassung", status_code=303)
    logik, bericht = logik_modul.hole_logik(session)
    if not bericht.ok:
        return render(request, "konfigurator/logikfehler.html", aktiv=None,
                      bericht=bericht)
    seiten = logik.seiten
    nr = max(0, min(nr, len(seiten) - 1))
    antworten = _antworten(erfassung)
    kunde = session.get(Kunde, erfassung.kunde_id)
    fragen = _fragen_der_seite(logik, seiten[nr])
    sichtbar = {f.id: engine.ist_sichtbar(f, antworten, logik.fragen) for f in fragen}
    werte = {}
    for f in fragen:
        wert = antworten.get(f.id)
        if wert is None and f.typ == "Auswahl" or wert is None:
            vor = engine.vorbelegung(f, antworten)
            if vor is not None:
                wert = vor
        werte[f.id] = wert
    return render(request, "erfassung/seite.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), erfassung=erfassung, kunde=kunde,
                  seiten=seiten, nr=nr, fragen=fragen, sichtbar=sichtbar,
                  werte=werte, fehler={}, client_regel=_client_regel,
                  wiederhol_id=engine.ID_WIEDERHOL_ANZAHL)


@router.post("/{erfassung_id}/seite/{nr}")
async def seite_speichern(request: Request, erfassung_id: int, nr: int,
                          session: Session = Depends(get_session)):
    erfassung = _erfassung_laden(request, erfassung_id, session)
    if erfassung is None:
        return RedirectResponse("/erfassung", status_code=303)
    logik, _ = logik_modul.hole_logik(session)
    seiten = logik.seiten
    nr = max(0, min(nr, len(seiten) - 1))
    form = await request.form()
    antworten = _antworten(erfassung)
    antworten_vorher = dict(antworten)
    fragen = _fragen_der_seite(logik, seiten[nr])

    fehler: dict[str, str] = {}
    for frage in fragen:
        if not engine.ist_sichtbar(frage, antworten, logik.fragen):
            antworten.pop(frage.id, None)   # unsichtbar geworden -> Antwort verwerfen
            continue
        wert, problem = _wert_lesen(frage, form, antworten)
        if problem:
            if wert in (None, "", [], {}) and _ist_optional(frage):
                antworten[frage.id] = ""
                continue
            fehler[frage.id] = problem
            continue
        antworten[frage.id] = wert

    richtung = form.get("richtung", "weiter")
    if fehler and richtung == "weiter":
        kunde = session.get(Kunde, erfassung.kunde_id)
        sichtbar = {f.id: engine.ist_sichtbar(f, antworten, logik.fragen) for f in fragen}
        werte = {f.id: antworten.get(f.id) for f in fragen}
        return render(request, "erfassung/seite.html", aktiv=None, mobil=True,
                      benutzer=_benutzer(request), erfassung=erfassung, kunde=kunde,
                      seiten=seiten, nr=nr, fragen=fragen, sichtbar=sichtbar,
                      werte=werte, fehler=fehler, client_regel=_client_regel,
                      wiederhol_id=engine.ID_WIEDERHOL_ANZAHL)

    erfassung.antworten_json = json.dumps(antworten, ensure_ascii=False)
    _korrekturen_protokollieren(erfassung, antworten_vorher, antworten,
                                _benutzer(request), logik)
    if richtung == "freitext":   # v7: Wechsel in die Freitext-Erfassung –
        session.commit()         # bereits gegebene Antworten bleiben erhalten
        return RedirectResponse(f"/erfassung/{erfassung.id}/freitext", status_code=303)
    if richtung == "zurueck":
        ziel = max(0, nr - 1)
        erfassung.seite_index = ziel
        session.commit()
        return RedirectResponse(f"/erfassung/{erfassung.id}/seite/{ziel}", status_code=303)
    if nr + 1 < len(seiten):
        erfassung.seite_index = nr + 1
        session.commit()
        return RedirectResponse(f"/erfassung/{erfassung.id}/seite/{nr + 1}", status_code=303)
    session.commit()
    return RedirectResponse(f"/erfassung/{erfassung.id}/pruefen", status_code=303)


def _korrekturen_protokollieren(erfassung, vorher: dict, nachher: dict,
                                benutzer, logik) -> None:
    """Innendienst-Korrekturen an abgesendeten Erfassungen protokollieren
    und Ampel/Gründe neu berechnen (Phase 14)."""
    if erfassung.status == "Entwurf":
        return
    zeilen = []
    for frage_id in sorted(set(vorher) | set(nachher)):
        if vorher.get(frage_id) != nachher.get(frage_id):
            zeilen.append(f"{datetime.now().strftime('%d.%m.%Y %H:%M')} · "
                          f"{benutzer.name}: {frage_id}: "
                          f"{vorher.get(frage_id, '–')!r} → {nachher.get(frage_id, '–')!r}")
    if zeilen:
        erfassung.aenderungs_protokoll = (
            (erfassung.aenderungs_protokoll + "\n" if erfassung.aenderungs_protokoll else "")
            + "\n".join(zeilen))
        gruende = engine.ampel_gruende(logik, nachher)
        erfassung.ampel = "orange" if gruende else "gruen"
        erfassung.gruende_text = "\n".join(gruende)


def _wert_lesen(frage, form, antworten):
    """Feldnamen sind je Frage benannt (f_<ID>…); Pflicht, sofern nicht optional."""
    name = f"f_{frage.id}"
    if frage.typ == "Auswahl":
        wert = (form.get(name) or "").strip()
        if wert not in frage.antworten:
            return wert, "Bitte auswählen."
        return wert, ""
    if frage.typ in FREITEXT_TYPEN:
        wert = (form.get(name) or "").strip()
        if not wert and not _ist_optional(frage):
            return wert, "Bitte ausfüllen."
        return wert, ""
    if frage.typ in ("Zahleneingabe", "Betragseingabe"):
        roh = (form.get(name) or "").strip()
        if not roh:
            return "", ("" if _ist_optional(frage) else "Bitte eine Zahl eingeben.")
        zahl = engine.zahl_parsen(roh)
        if zahl is None or zahl < 0:
            return roh, "Ungültige Zahl."
        return zahl, ""
    if frage.typ == "Mengenmaske":
        werte = {}
        for option in frage.antworten:
            roh = (form.get(f"{name}_{option}") or "").strip()
            zahl = engine.zahl_parsen(roh) if roh else 0
            if zahl is None or zahl < 0 or zahl != int(zahl):
                return werte, f"Ungültige Anzahl bei {option}."
            werte[option] = int(zahl)
        return werte, ""
    if frage.typ == "Wiederholfeld":
        anzahl = int(engine.zahl_parsen(antworten.get(engine.ID_WIEDERHOL_ANZAHL)) or 0)
        werte = []
        for i in range(1, max(anzahl, 1) + 1):
            roh = (form.get(f"{name}_{i}") or "").strip()
            zahl = engine.zahl_parsen(roh)
            if zahl is None or zahl <= 0 or zahl != int(zahl):
                return werte, f"Verteiler {i}: gültige Gruppenanzahl eingeben."
            werte.append(int(zahl))
        return werte, ""
    return None, f"Unbekannter Fragetyp {frage.typ}."


@router.get("/{erfassung_id}/pruefen")
async def pruefen(request: Request, erfassung_id: int,
                  session: Session = Depends(get_session)):
    erfassung = _erfassung_laden(request, erfassung_id, session)
    if erfassung is None:
        return RedirectResponse("/erfassung", status_code=303)
    logik, _ = logik_modul.hole_logik(session)
    antworten = _antworten(erfassung)
    offen = engine.naechste_frage(logik, antworten)
    prot = engine.protokoll(logik, antworten)
    gruende = engine.ampel_gruende(logik, antworten)
    kunde = session.get(Kunde, erfassung.kunde_id)
    return render(request, "erfassung/pruefen.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), erfassung=erfassung, kunde=kunde,
                  protokoll=prot, gruende=gruende, offen=offen,
                  seiten=logik.seiten)


@router.post("/{erfassung_id}/absenden")
async def absenden(request: Request, erfassung_id: int,
                   session: Session = Depends(get_session)):
    erfassung = _erfassung_laden(request, erfassung_id, session)
    if erfassung is None:
        return RedirectResponse("/erfassung", status_code=303)
    logik, _ = logik_modul.hole_logik(session)
    antworten = _antworten(erfassung)
    if engine.naechste_frage(logik, antworten) is not None:
        return RedirectResponse(f"/erfassung/{erfassung.id}/pruefen", status_code=303)
    gruende = engine.ampel_gruende(logik, antworten)
    erfassung.ampel = "orange" if gruende else "gruen"
    erfassung.gruende_text = "\n".join(gruende)
    # v7: orange Katalog-Fälle landen zur Prüfung beim Innendienst
    erfassung.status = "Individuell – zu prüfen" if gruende else "Neu"
    erfassung.abgesendet_am = datetime.now()
    session.commit()
    return render(request, "erfassung/fertig.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), erfassung=erfassung)
