# Angebotsverwaltung (Phase 5): Liste mit Status/Suche, Angebot aus Konfiguration
# oder manuell, Editor (Mengen, Positionen entfernen, Freitext, Artikel aus Stamm),
# Duplizieren, Statuspflege.

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app import angebot_aufbau, kfw
from app import logik as logik_modul
from app.db import get_session
from app.models import (ANGEBOT_STATUS, Angebot, AngebotsPosition, Artikel,
                        Konfiguration, Kunde)
from app.routers.artikel import preis_parsen
from app.templating import render

router = APIRouter(prefix="/angebote")


def _kunden_map(session: Session, angebote) -> dict[int, Kunde]:
    ids = {a.kunde_id for a in angebote}
    if not ids:
        return {}
    return {k.id: k for k in session.query(Kunde).filter(Kunde.id.in_(ids))}


@router.get("")
async def liste(request: Request, q: str = "", status: str = "",
                session: Session = Depends(get_session)):
    abfrage = session.query(Angebot).options(joinedload(Angebot.positionen))
    if status:
        abfrage = abfrage.filter(Angebot.status == status)
    angebote = abfrage.order_by(Angebot.nummer.desc()).all()
    kunden = _kunden_map(session, angebote)
    if q:
        suchwort = q.lower()
        angebote = [a for a in angebote
                    if suchwort in a.nummer.lower()
                    or (a.kunde_id in kunden
                        and suchwort in kunden[a.kunde_id].anzeige_name.lower())]
    return render(request, "angebote/liste.html", aktiv="/angebote",
                  angebote=angebote, kunden=kunden, q=q, status=status,
                  status_liste=ANGEBOT_STATUS,
                  meldung=request.query_params.get("meldung", ""))


@router.get("/aus-konfiguration/{konfig_id}")
async def aus_konfiguration(konfig_id: int, session: Session = Depends(get_session)):
    konfig = session.get(Konfiguration, konfig_id)
    if konfig is None or konfig.status != "fertig":
        return RedirectResponse("/angebote?meldung=Konfiguration+nicht+gefunden+oder+nicht+fertig",
                                status_code=303)
    logik, bericht = logik_modul.hole_logik(session)
    if not bericht.ok:
        return RedirectResponse("/konfiguration", status_code=303)
    angebot = angebot_aufbau.angebot_anlegen(
        session, konfig.kunde_id, antworten=json.loads(konfig.antworten_json or "{}"),
        logik=logik, konfiguration_id=konfig.id)
    return RedirectResponse(f"/angebote/{angebot.id}", status_code=303)


@router.get("/neu")
async def neu(kunde_id: int = 0, session: Session = Depends(get_session)):
    kunde = session.get(Kunde, kunde_id)
    if kunde is None:
        return RedirectResponse("/konfigurator", status_code=303)
    angebot = angebot_aufbau.angebot_anlegen(session, kunde.id)
    return RedirectResponse(f"/angebote/{angebot.id}", status_code=303)


@router.get("/{angebot_id}")
async def editor(request: Request, angebot_id: int,
                 session: Session = Depends(get_session)):
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote?meldung=Angebot+nicht+gefunden", status_code=303)
    kunde = session.get(Kunde, angebot.kunde_id)
    artikel_liste = (session.query(Artikel).filter(Artikel.aktiv.is_(True))
                     .order_by(Artikel.pos_nr).all())
    protokoll = json.loads(angebot.protokoll_json or "[]")

    # Positionen nach Gruppe (Blockreihenfolge) für die Anzeige bündeln
    gruppen: list[dict] = []
    for p in angebot.positionen:
        if not gruppen or gruppen[-1]["name"] != p.gruppe or gruppen[-1]["block"] != p.block_nr:
            gruppen.append({"name": p.gruppe, "block": p.block_nr, "positionen": []})
        gruppen[-1]["positionen"].append(p)

    # KfW-Aufschlüsselung: Kosten der Maßnahme = Angebotssumme brutto (automatisch)
    kfw_ergebnis = None
    kfw_warnung = None
    kfw_daten = json.loads(angebot.kfw_json or "{}")
    if kfw_daten.get("O01"):
        logik, bericht = logik_modul.hole_logik(session)
        if bericht is not None:
            parameter, _ = kfw.parameter_lesen(logik)
            eingaben = kfw.eingaben_aus_antworten(kfw_daten, angebot.summen()["brutto"])
            if eingaben is not None:
                kfw_ergebnis = kfw.berechnen(parameter, eingaben)
                kfw_warnung = kfw.gueltigkeits_warnung(parameter)

    # Anhänge-Vorschau (Phase 15): was würde beim Versand mitgehen?
    from app import anhaenge as anhaenge_modul
    logik, _bericht = logik_modul.hole_logik(session)
    anhaenge_liste = anhaenge_modul.fuer_angebot(logik, angebot)
    vollmacht = anhaenge_modul.vollmacht_erforderlich(angebot)

    return render(request, "angebote/editor.html", aktiv="/angebote",
                  angebot=angebot, kunde=kunde, gruppen=gruppen,
                  summen=angebot.summen(), artikel_liste=artikel_liste,
                  deckung=angebot.deckungsbeitrag(),
                  protokoll=protokoll, status_liste=ANGEBOT_STATUS,
                  kfw_ergebnis=kfw_ergebnis, kfw_warnung=kfw_warnung,
                  anhaenge_liste=anhaenge_liste, vollmacht=vollmacht,
                  versand=request.query_params.get("versand", ""),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/{angebot_id}/position/{position_id}/menge")
async def menge_aendern(request: Request, angebot_id: int, position_id: int,
                        session: Session = Depends(get_session)):
    form = await request.form()
    position = session.get(AngebotsPosition, position_id)
    if position and position.angebot_id == angebot_id:
        from app.konfigurator import zahl_parsen
        zahl = zahl_parsen(form.get("menge"))
        if zahl is not None and zahl > 0:
            position.menge = zahl
            session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)


@router.post("/{angebot_id}/position/{position_id}/entfernen")
async def position_entfernen(angebot_id: int, position_id: int,
                             session: Session = Depends(get_session)):
    position = session.get(AngebotsPosition, position_id)
    if position and position.angebot_id == angebot_id:
        session.delete(position)
        session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)


@router.post("/{angebot_id}/position-neu")
async def position_neu(request: Request, angebot_id: int,
                       session: Session = Depends(get_session)):
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = await request.form()
    max_sort = max((p.sort for p in angebot.positionen), default=0)
    letzte_gruppe = angebot.positionen[-1].gruppe if angebot.positionen else ""
    letzter_block = angebot.positionen[-1].block_nr if angebot.positionen else 0

    artikel_id = form.get("artikel_id") or ""
    if artikel_id:
        artikel = session.get(Artikel, int(artikel_id))
        if artikel is not None:
            angebot.positionen.append(AngebotsPosition(
                sort=max_sort + 1, block_nr=letzter_block, gruppe=letzte_gruppe,
                pos_nr=artikel.pos_nr, bezeichnung=artikel.bezeichnung,
                beschreibung=artikel.beschreibung, menge=artikel.menge_standard,
                einheit=artikel.einheit, e_preis_cent=artikel.e_preis_cent,
                ep_flag=artikel.ep_flag, ek_cent=artikel.ek_cent))
            session.commit()
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)

    # Freitextposition
    bezeichnung = (form.get("bezeichnung") or "").strip()
    preis = preis_parsen(form.get("e_preis") or "")
    from app.konfigurator import zahl_parsen
    menge = zahl_parsen(form.get("menge") or "1") or 1
    if bezeichnung and preis is not None:
        angebot.positionen.append(AngebotsPosition(
            sort=max_sort + 1, block_nr=letzter_block, gruppe=letzte_gruppe,
            bezeichnung=bezeichnung,
            beschreibung=(form.get("beschreibung") or "").strip(),
            menge=menge, einheit=(form.get("einheit") or "").strip(),
            e_preis_cent=preis, ep_flag=form.get("ep_flag") == "on"))
        session.commit()
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    return RedirectResponse(
        f"/angebote/{angebot_id}?meldung=Freitextposition:+Bezeichnung+und+Preis+erforderlich",
        status_code=303)


@router.get("/{angebot_id}/pdf")
async def pdf_anzeigen(angebot_id: int, session: Session = Depends(get_session)):
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote?meldung=Angebot+nicht+gefunden", status_code=303)
    from app import pdf_export
    pfad = pdf_export.pdf_fuer_angebot(session, angebot)
    return FileResponse(pfad, media_type="application/pdf",
                        content_disposition_type="inline",
                        filename=f"{angebot.nummer}.pdf")


@router.post("/{angebot_id}/email")
async def email_entwurf(angebot_id: int, session: Session = Depends(get_session)):
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote?meldung=Angebot+nicht+gefunden", status_code=303)
    kunde = session.get(Kunde, angebot.kunde_id)
    from pathlib import Path

    from app import anhaenge as anhaenge_modul
    from app import outlook_versand, pdf_export
    pdf_pfad = pdf_export.pdf_fuer_angebot(session, angebot)
    logik, _ = logik_modul.hole_logik(session)
    anhaenge = anhaenge_modul.fuer_angebot(logik, angebot)
    erfolg, meldung = outlook_versand.entwurf_oeffnen(
        kunde, angebot, pdf_pfad,
        weitere_anhaenge=[Path(a.pfad) for a in anhaenge if a.vorhanden],
        fehlende_anhaenge=[a.datei for a in anhaenge if not a.vorhanden])
    from urllib.parse import quote_plus
    ziel = f"/angebote/{angebot_id}?meldung={quote_plus(meldung)}"
    if erfolg:
        ziel += "&versand=1"
    return RedirectResponse(ziel, status_code=303)


@router.post("/{angebot_id}/status")
async def status_aendern(request: Request, angebot_id: int,
                         session: Session = Depends(get_session)):
    form = await request.form()
    angebot = session.get(Angebot, angebot_id)
    neuer_status = form.get("status", "")
    if angebot is not None and neuer_status in ANGEBOT_STATUS:
        angebot.status = neuer_status
        # verknüpfte Erfassung automatisch pflegen (Phase 14)
        from app.models import Erfassung
        erfassung = (session.query(Erfassung)
                     .filter(Erfassung.angebot_id == angebot.id).first())
        if erfassung is not None:
            if neuer_status in ("Versendet", "Angenommen", "Abgelehnt"):
                erfassung.status = "Erledigt"
            elif erfassung.status == "Neu":
                erfassung.status = "In Bearbeitung"
        session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)


@router.post("/{angebot_id}/duplizieren")
async def duplizieren(angebot_id: int, session: Session = Depends(get_session)):
    original = session.get(Angebot, angebot_id)
    if original is None:
        return RedirectResponse("/angebote", status_code=303)
    kopie = angebot_aufbau.angebot_anlegen(session, original.kunde_id)
    kopie.protokoll_json = original.protokoll_json
    kopie.kfw_json = original.kfw_json
    for p in original.positionen:
        kopie.positionen.append(AngebotsPosition(
            sort=p.sort, block_nr=p.block_nr, gruppe=p.gruppe, pos_nr=p.pos_nr,
            bezeichnung=p.bezeichnung, beschreibung=p.beschreibung, menge=p.menge,
            einheit=p.einheit, e_preis_cent=p.e_preis_cent, ep_flag=p.ep_flag,
            ek_cent=p.ek_cent))
    session.commit()
    return RedirectResponse(f"/angebote/{kopie.id}?meldung=Angebot+dupliziert", status_code=303)
