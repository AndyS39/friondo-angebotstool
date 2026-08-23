# Angebotsverwaltung (Phase 5): Liste mit Status/Suche, Angebot aus Konfiguration
# oder manuell, Editor (Mengen, Positionen entfernen, Freitext, Artikel aus Stamm),
# Duplizieren, Statuspflege.

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app import angebot_aufbau, kfw, sperren
from app import logik as logik_modul
from app.db import get_session
from app.models import (ANGEBOT_STATUS, Angebot, AngebotsPosition, Artikel,
                        Konfiguration, Kunde)
from app.routers.artikel import preis_parsen
from app.templating import render

router = APIRouter(prefix="/angebote")


def _sperr_umleitung(request: Request, angebot_id: int):
    """Bearbeitungssperre für POST-Routen: hält ein anderer Benutzer das
    Angebot gerade im Editor, wird die Änderung abgewiesen (None = frei)."""
    benutzer = request.state.benutzer
    halter = sperren.gesperrt_fuer(angebot_id, benutzer.id if benutzer else 0)
    if halter is None:
        return None
    from urllib.parse import quote_plus
    return RedirectResponse(
        f"/angebote/{angebot_id}?meldung=" + quote_plus(
            f"Keine Änderung möglich – wird gerade von {halter['name']} bearbeitet."),
        status_code=303)


def _kunden_map(session: Session, angebote) -> dict[int, Kunde]:
    ids = {a.kunde_id for a in angebote}
    if not ids:
        return {}
    return {k.id: k for k in session.query(Kunde).filter(Kunde.id.in_(ids))}


@router.get("")
async def liste(request: Request, q: str = "", status: str = "", interesse: str = "",
                vertriebler_id: int = 0, sortierung: str = "nummer", kanal: str = "",
                verfolgung: str = "", session: Session = Depends(get_session)):
    abfrage = session.query(Angebot).options(joinedload(Angebot.positionen))
    # Archiv (v5): Standardansicht ohne archivierte, Filter „Archiv“ nur diese
    if status == "archiv":
        abfrage = abfrage.filter(Angebot.archiviert.is_(True))
    else:
        abfrage = abfrage.filter(Angebot.archiviert.is_(False))
        if status:
            abfrage = abfrage.filter(Angebot.status == status)
    angebote = abfrage.order_by(Angebot.nummer.desc()).all()
    kunden = _kunden_map(session, angebote)
    if q:
        suchwort = q.lower()
        angebote = [a for a in angebote
                    if suchwort in a.nummer.lower()
                    or (a.kunde_id in kunden
                        and (suchwort in kunden[a.kunde_id].anzeige_name.lower()
                             or suchwort in (kunden[a.kunde_id].ort or "").lower()))]
    if interesse:   # Filter nach Interesse des Kunden (Phase 33)
        angebote = [a for a in angebote
                    if a.kunde_id in kunden and interesse in kunden[a.kunde_id].interessen]
    if kanal:       # Vertriebskanal des Kunden (v6)
        angebote = [a for a in angebote
                    if a.kunde_id in kunden and kunden[a.kunde_id].vertriebskanal == kanal]
    if verfolgung == "faellig":   # Verfolgung (v6): fällige Wiedervorlagen
        from datetime import datetime as dt
        angebote = [a for a in angebote
                    if a.wiedervorlage_am and a.wiedervorlage_am <= dt.now()]
    elif verfolgung in ("heiss", "warm", "kalt"):
        angebote = [a for a in angebote if a.verfolgung_ampel == verfolgung]
    # Vertriebler je Angebot (v5-Nachtrag): über die verknüpfte Erfassung
    from app.models import Benutzer, Erfassung
    vertriebler = {b.id: b for b in session.query(Benutzer)}
    angebot_vertriebler: dict[int, int] = {}
    for a in angebote:            # Fallback: manuelles Angebot ohne Erfassung
        if a.vertriebler_id:
            angebot_vertriebler[a.id] = a.vertriebler_id
    for e in session.query(Erfassung).filter(Erfassung.angebot_id.isnot(None)):
        angebot_vertriebler[e.angebot_id] = e.benutzer_id   # Erfassung gewinnt
    vertriebler_werte = sorted({angebot_vertriebler[a.id] for a in angebote
                                if a.id in angebot_vertriebler},
                               key=lambda i: vertriebler[i].name if i in vertriebler else "")
    if vertriebler_id:
        angebote = [a for a in angebote if angebot_vertriebler.get(a.id) == vertriebler_id]
    # Sortierung (v5-Nachtrag): Nummer (Standard, absteigend), Datum, Kunde, Vertriebler
    def name_von(a):
        bid = angebot_vertriebler.get(a.id)
        return (vertriebler[bid].name if bid in vertriebler else "zzz").lower()
    if sortierung == "vertriebler":
        angebote.sort(key=lambda a: (name_von(a), a.nummer))
    elif sortierung == "kunde":
        angebote.sort(key=lambda a: (kunden[a.kunde_id].anzeige_name.lower()
                                     if a.kunde_id in kunden else "zzz", a.nummer))
    elif sortierung == "datum":
        from datetime import datetime as _dt
        angebote.sort(key=lambda a: a.datum or _dt.min, reverse=True)
    else:
        sortierung = "nummer"
    # DB-Farbampel (Phase 24): Schwellen in Euro, in der Parametrierung pflegbar
    from app.models import einstellung_holen
    rot_unter = int(einstellung_holen(session, "db_ampel_rot_unter", "9000"))
    gruen_ueber = int(einstellung_holen(session, "db_ampel_gruen_ueber", "10000"))
    # Mail-Verlauf (Phase 27): eingehende Antworten je Angebot zählen
    from sqlalchemy import func

    from app.models import AngebotsMail
    mail_zaehler = dict(session.query(AngebotsMail.angebot_id, func.count())
                        .filter(AngebotsMail.eingehend.is_(True))
                        .group_by(AngebotsMail.angebot_id))
    # Summenzeile (v6): über die aktuell gefilterte Liste
    summen_gesamt = {"netto": 0, "endbetrag": 0, "db": 0}
    for a in angebote:
        su = a.summen()
        summen_gesamt["netto"] += su["netto"]
        summen_gesamt["endbetrag"] += su["endbetrag"]
        summen_gesamt["db"] += a.deckungsbeitrag()["db"]
    return render(request, "angebote/liste.html", aktiv="/angebote",
                  summen_gesamt=summen_gesamt,
                  angebote=angebote, kunden=kunden, q=q, status=status,
                  interesse=interesse, vertriebler_id=vertriebler_id, sortierung=sortierung,
                  kanal=kanal, verfolgung=verfolgung,
                  heute=__import__("datetime").datetime.now(),
                  kanal_werte=sorted({kunden[a.kunde_id].vertriebskanal for a in angebote
                                      if a.kunde_id in kunden and kunden[a.kunde_id].vertriebskanal}
                                     | ({kanal} if kanal else set())),
                  vertriebler=vertriebler, angebot_vertriebler=angebot_vertriebler,
                  vertriebler_werte=vertriebler_werte,
                  status_liste=ANGEBOT_STATUS, mail_zaehler=mail_zaehler,
                  db_rot_cent=rot_unter * 100, db_gruen_cent=gruen_ueber * 100,
                  meldung=request.query_params.get("meldung", ""))


@router.get("/aus-konfiguration/{konfig_id}")
async def aus_konfiguration(konfig_id: int, session: Session = Depends(get_session)):
    konfig = session.get(Konfiguration, konfig_id)
    if konfig is None or konfig.status != "fertig":
        return RedirectResponse("/angebote?meldung=Konfiguration+nicht+gefunden+oder+nicht+fertig",
                                status_code=303)
    logik, bericht = logik_modul.hole_logik(session)
    if not bericht.ok:
        return RedirectResponse("/parametrierung", status_code=303)
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
    # Bearbeitungssperre: Erster im Editor hält das Angebot, andere lesen nur
    benutzer = request.state.benutzer
    sperr_halter = sperren.erwerben(angebot.id, benutzer.id if benutzer else 0,
                                    benutzer.name if benutzer else "?")
    nur_lesen = sperr_halter is not None
    kunde = session.get(Kunde, angebot.kunde_id)
    artikel_liste = (session.query(Artikel).filter(Artikel.aktiv.is_(True))
                     .order_by(Artikel.pos_nr).all())
    protokoll = json.loads(angebot.protokoll_json or "[]")

    # Anzeigenummern (Phase 18/v5): eigene Nummer oder fortlaufend 001, 002, …;
    # die interne TAIFUN-/Z-Referenz bleibt in pos_nr/guid gespeichert
    for p, nummer in zip(angebot.positionen, angebot.nummerierung()):
        p.lfd_nr = nummer

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
            eingaben = kfw.eingaben_aus_antworten(kfw_daten, angebot.summen()["endbetrag"])
            if eingaben is not None:
                kfw_ergebnis = kfw.ergebnis_mit_override(
                    kfw.berechnen(parameter, eingaben),
                    angebot.foerderung_manuell_cent, angebot.summen()["endbetrag"])
                kfw_warnung = kfw.gueltigkeits_warnung(parameter)

    # Anhänge-Vorschau (Phase 15): was würde beim Versand mitgehen?
    from app import anhaenge as anhaenge_modul
    logik, _bericht = logik_modul.hole_logik(session)
    anhaenge_liste = anhaenge_modul.fuer_angebot(logik, angebot)
    vollmacht = anhaenge_modul.vollmacht_erforderlich(angebot)

    # Angebotsverfolgung (v6): Notizen-Verlauf
    from app.models import AngebotsNotiz
    notizen = (session.query(AngebotsNotiz)
               .filter(AngebotsNotiz.angebot_id == angebot.id)
               .order_by(AngebotsNotiz.angelegt_am.desc()).all())

    # Vertriebler des Vorgangs (v5-Nachtrag): anzeigen + änderbar
    from app import mail_vorlagen
    from app.models import Benutzer as BenutzerModell
    angebot_vertriebler = mail_vorlagen.vertriebler_fuer_angebot(session, angebot)
    aussendienst = (session.query(BenutzerModell)
                    .filter(BenutzerModell.rolle == "aussendienst",
                            BenutzerModell.aktiv.is_(True))
                    .order_by(BenutzerModell.name).all())

    return render(request, "angebote/editor.html", aktiv="/angebote",
                  angebot=angebot, kunde=kunde, gruppen=gruppen,
                  summen=angebot.summen(), artikel_liste=artikel_liste,
                  deckung=angebot.deckungsbeitrag(),
                  protokoll=protokoll, status_liste=ANGEBOT_STATUS,
                  kfw_ergebnis=kfw_ergebnis, kfw_warnung=kfw_warnung,
                  anhaenge_liste=anhaenge_liste, vollmacht=vollmacht,
                  angebot_vertriebler=angebot_vertriebler, aussendienst=aussendienst,
                  notizen=notizen,
                  nur_lesen=nur_lesen, sperr_halter=sperr_halter,
                  versand=request.query_params.get("versand", ""),
                  weblink=request.query_params.get("weblink", ""),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/{angebot_id}/sperre")
async def sperre_verlaengern(request: Request, angebot_id: int):
    """Heartbeat des offenen Editors (alle 4 Minuten per JS)."""
    benutzer = request.state.benutzer
    ok = sperren.verlaengern(angebot_id, benutzer.id if benutzer else 0)
    from fastapi.responses import JSONResponse
    return JSONResponse({"ok": ok})


@router.post("/{angebot_id}/sperre-frei")
async def sperre_freigeben(request: Request, angebot_id: int):
    """Freigabe beim Verlassen der Seite (sendBeacon); sonst läuft die
    Sperre nach 10 Minuten ohne Heartbeat von selbst ab."""
    benutzer = request.state.benutzer
    if benutzer is not None:
        sperren.freigeben(angebot_id, benutzer.id)
    from fastapi.responses import JSONResponse
    return JSONResponse({"ok": True})


@router.post("/{angebot_id}/position/{position_id}/menge")
async def menge_aendern(request: Request, angebot_id: int, position_id: int,
                        session: Session = Depends(get_session)):
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    form = await request.form()
    position = session.get(AngebotsPosition, position_id)
    if position and position.angebot_id == angebot_id:
        from app.konfigurator import zahl_parsen
        zahl = zahl_parsen(form.get("menge"))
        if zahl is not None and zahl > 0:
            position.menge = zahl
            session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)


@router.post("/{angebot_id}/position/{position_id}/aendern")
async def position_aendern(request: Request, angebot_id: int, position_id: int,
                           session: Session = Depends(get_session)):
    """Zeilen-Editor (v5, Phase 34): Anzeigenummer, Menge, Einzelpreis
    (Original bleibt erhalten), Positionsrabatt (% oder €), bauseits."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    from urllib.parse import quote_plus

    from app.konfigurator import zahl_parsen
    form = await request.form()
    position = session.get(AngebotsPosition, position_id)
    if position is None or position.angebot_id != angebot_id:
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    fehler = []
    position.anzeige_nr = (form.get("anzeige_nr") or "").strip()[:10]
    menge = zahl_parsen(form.get("menge"))
    if menge is not None and menge > 0:
        position.menge = menge
    elif (form.get("menge") or "").strip():
        fehler.append("Menge ungültig")
    preis_text = (form.get("e_preis") or "").strip()
    if preis_text:
        preis = preis_parsen(preis_text)
        if preis is None or preis < 0:
            fehler.append("Einzelpreis ungültig")
        elif preis != position.e_preis_cent:
            if position.original_preis_cent is None:
                position.original_preis_cent = position.e_preis_cent
            position.e_preis_cent = preis
    # Positionsrabatt: leer = kein Rabatt
    rabatt_wert = (form.get("rabatt_wert") or "").strip()
    position.rabatt_cent = None
    position.rabatt_prozent = None
    if rabatt_wert:
        if form.get("rabatt_typ") == "prozent":
            prozent = zahl_parsen(rabatt_wert)
            if prozent is None or not 0 < prozent <= 100:
                fehler.append("Rabatt-Prozent ungültig (0–100)")
            else:
                position.rabatt_prozent = prozent
        else:
            cent = preis_parsen(rabatt_wert)
            if cent is None or cent <= 0:
                fehler.append("Rabatt-Betrag ungültig")
            else:
                position.rabatt_cent = cent
    position.bauseits = form.get("bauseits") == "on"
    position.ep_flag = form.get("ep_flag") == "on"   # v6: EP-Kästchen je Position
    session.commit()
    ziel = f"/angebote/{angebot_id}"
    if fehler:
        ziel += "?meldung=" + quote_plus("Position teilweise nicht übernommen: " + ", ".join(fehler))
    return RedirectResponse(ziel, status_code=303)


@router.post("/{angebot_id}/sortierung")
async def sortierung(request: Request, angebot_id: int,
                     session: Session = Depends(get_session)):
    """Drag & Drop (v5): Reihenfolge aller Positions-IDs kommagetrennt."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    form = await request.form()
    ids = [int(t) for t in (form.get("reihenfolge") or "").split(",") if t.strip().isdigit()]
    positionen = {p.id: p for p in session.query(AngebotsPosition)
                  .filter(AngebotsPosition.angebot_id == angebot_id)}
    if set(ids) == set(positionen):
        for index, pid in enumerate(ids, 1):
            positionen[pid].sort = index
        session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)


@router.post("/{angebot_id}/neu-nummerieren")
async def neu_nummerieren(request: Request, angebot_id: int,
                          session: Session = Depends(get_session)):
    """Eigene Nummern verwerfen → wieder fortlaufend 001, 002, … (v5)."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    for p in session.query(AngebotsPosition).filter(AngebotsPosition.angebot_id == angebot_id):
        p.anzeige_nr = ""
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=Neu+durchnummeriert", status_code=303)


@router.post("/{angebot_id}/position/{position_id}/entfernen")
async def position_entfernen(request: Request, angebot_id: int, position_id: int,
                             session: Session = Depends(get_session)):
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    position = session.get(AngebotsPosition, position_id)
    if position and position.angebot_id == angebot_id:
        session.delete(position)
        session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)


@router.post("/{angebot_id}/position-neu")
async def position_neu(request: Request, angebot_id: int,
                       session: Session = Depends(get_session)):
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = await request.form()
    max_sort = max((p.sort for p in angebot.positionen), default=0)
    letzte_gruppe = angebot.positionen[-1].gruppe if angebot.positionen else ""
    letzter_block = angebot.positionen[-1].block_nr if angebot.positionen else 0

    # Autocomplete-Feld (Phase 24): "#<id> · <Pos> · <Titel> …" oder Alt-Feld artikel_id
    artikel_id = form.get("artikel_id") or ""
    suche = (form.get("artikel_suche") or "").strip()
    if not artikel_id and suche:
        import re as _re
        m = _re.match(r"#(\d+)\b", suche)
        if m:
            artikel_id = m.group(1)
        else:
            # Freitext ohne Auswahl aus der Liste: nach Pos-Nr./Artikelnummer suchen
            treffer = (session.query(Artikel)
                       .filter(Artikel.aktiv.is_(True))
                       .filter(or_(Artikel.pos_nr == suche,
                                   Artikel.artikelnummer == suche)).first())
            if treffer is not None:
                artikel_id = str(treffer.id)
            else:
                return RedirectResponse(
                    f"/angebote/{angebot_id}?meldung=Artikel+nicht+gefunden+–+bitte+aus+der+Vorschlagsliste+w%C3%A4hlen",
                    status_code=303)
    if artikel_id:
        artikel = session.get(Artikel, int(artikel_id))
        if artikel is not None:
            angebot.positionen.append(AngebotsPosition(
                sort=max_sort + 1, block_nr=letzter_block, gruppe=letzte_gruppe,
                pos_nr=artikel.pos_nr, bezeichnung=artikel.bezeichnung,
                beschreibung=artikel.beschreibung, menge=artikel.menge_standard,
                einheit=artikel.einheit, e_preis_cent=artikel.e_preis_cent,
                ep_flag=artikel.ep_flag, ek_cent=artikel.ek_cent,
                guid=artikel.guid))
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


@router.post("/{angebot_id}/rabatt")
async def rabatt_setzen(request: Request, angebot_id: int,
                        session: Session = Depends(get_session)):
    """Rabatt (Phase 21): Betrag ODER Prozent + optionale Bezeichnung;
    leerer Wert entfernt den Rabatt. Nur Innendienst/Admin (Middleware)."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = await request.form()
    wert = (form.get("wert") or "").strip()
    typ = form.get("typ", "betrag")
    angebot.rabatt_bezeichnung = (form.get("bezeichnung") or "").strip()
    angebot.rabatt_cent = None
    angebot.rabatt_prozent = None
    if wert:
        if typ == "prozent":
            from app.konfigurator import zahl_parsen
            prozent = zahl_parsen(wert)
            if prozent is None or not (0 < prozent <= 100):
                return RedirectResponse(
                    f"/angebote/{angebot_id}?meldung=Ung%C3%BCltiger+Prozentwert",
                    status_code=303)
            angebot.rabatt_prozent = prozent
        else:
            betrag = preis_parsen(wert)
            if betrag is None or betrag <= 0:
                return RedirectResponse(
                    f"/angebote/{angebot_id}?meldung=Ung%C3%BCltiger+Rabattbetrag",
                    status_code=303)
            angebot.rabatt_cent = betrag
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=Rabatt+gespeichert",
                            status_code=303)


@router.get("/{angebot_id}/protokoll.pdf")
async def protokoll_pdf(angebot_id: int, session: Session = Depends(get_session)):
    """Abfrageprotokoll des Angebots als PDF (Phase 25)."""
    from app import protokoll_pdf as protokoll_modul
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    prot = json.loads(angebot.protokoll_json or "[]")
    if not prot:
        return RedirectResponse(
            f"/angebote/{angebot_id}?meldung=Kein+Abfrageprotokoll+vorhanden+(manuelles+Angebot)",
            status_code=303)
    kunde = session.get(Kunde, angebot.kunde_id)
    from app.models import Benutzer, Erfassung
    erfassung = (session.query(Erfassung)
                 .filter(Erfassung.angebot_id == angebot.id).first())
    vertriebler = session.get(Benutzer, erfassung.benutzer_id) if erfassung else None
    kopf = [
        ("Angebot", angebot.nummer),
        ("Kunde", kunde.anzeige_name if kunde else "?"),
        ("Adresse", f"{kunde.strasse}, {kunde.plz} {kunde.ort}".strip(", ") if kunde else ""),
        ("Vertriebler", vertriebler.name if vertriebler else "–"),
        ("Datum", angebot.datum.strftime("%d.%m.%Y")),
    ]
    gruende = [p["ampel_grund"] for p in prot if p.get("ampel_grund")]
    pfad = protokoll_modul.erzeuge_protokoll_pdf(
        f"protokoll-{angebot.nummer}.pdf",
        f"Angebot {angebot.nummer} · {kunde.anzeige_name if kunde else ''}",
        kopf, prot, sorted(set(gruende)))
    return FileResponse(pfad, media_type="application/pdf",
                        content_disposition_type="inline",
                        filename=f"Protokoll-{angebot.nummer}.pdf")


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
async def email_entwurf(request: Request, angebot_id: int,
                        session: Session = Depends(get_session)):
    """Versand vorbereiten (Phase 17): Entwurf per Microsoft Graph im Postfach
    des angemeldeten Innendienst-Nutzers; Fallback bleibt der PDF-Download."""
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote?meldung=Angebot+nicht+gefunden", status_code=303)
    kunde = session.get(Kunde, angebot.kunde_id)
    from pathlib import Path
    from urllib.parse import quote_plus

    from app import anhaenge as anhaenge_modul
    from app import graph_versand, pdf_export

    if not graph_versand.konfiguriert():
        return RedirectResponse(
            f"/angebote/{angebot_id}?meldung=" + quote_plus(
                "Microsoft Graph ist noch nicht eingerichtet "
                "(docs/graph-einrichtung.md). Übergangslösung: PDF anzeigen "
                "und manuell versenden."), status_code=303)
    if graph_versand.angemeldeter_benutzer() is None:
        return RedirectResponse(
            "/versand?meldung=" + quote_plus(
                "Bitte zuerst mit Microsoft anmelden, dann den Versand erneut "
                "vorbereiten."), status_code=303)

    pdf_pfad = pdf_export.pdf_fuer_angebot(session, angebot)
    logik, _ = logik_modul.hole_logik(session)
    anhaenge = anhaenge_modul.fuer_angebot(logik, angebot)
    # Fern-Signatur (Phase 28): bei aktivem Schalter Einmal-Link in die Mail
    signatur_link = ""
    from app.routers.signatur import fern_aktiv, fern_token_ausstellen
    if fern_aktiv(session):
        from app.models import einstellung_holen
        token = fern_token_ausstellen(session, angebot)
        basis = einstellung_holen(session, "signatur_fern_basis_url", "").rstrip("/")
        if not basis:
            basis = str(request.base_url).rstrip("/")
        signatur_link = f"{basis}/signatur/extern/{token}"
        session.commit()
    # Vorlage (Phase 30): AD des Vorgangs, sonst Standard; Platzhalter füllen
    from app import mail_vorlagen
    from app.models import einstellung_holen
    betreff, text, vorlage_quelle = mail_vorlagen.mail_fuer_angebot(
        session, angebot, kunde, request.state.benutzer.name)
    text += graph_versand.signatur_absatz(signatur_link)
    # Phase 31: Absender angebot@friondo.de, CC = AD des Vorgangs, BCC aus Parametrierung
    absender = einstellung_holen(session, "mail_absender", "angebot@friondo.de")
    bcc = [a.strip() for a in einstellung_holen(session, "mail_bcc", "").split(",") if a.strip()]
    vertriebler = mail_vorlagen.vertriebler_fuer_angebot(session, angebot)
    cc = [vertriebler.email] if vertriebler and vertriebler.email else []
    cc_hinweis = ""
    if vertriebler and not vertriebler.email:
        cc_hinweis = (f" ACHTUNG: {vertriebler.name} hat keine E-Mail-Adresse hinterlegt – "
                      "Entwurf ohne CC (Benutzerverwaltung ergänzen).")
    elif vertriebler is None:
        cc_hinweis = " Hinweis: kein Außendienstler zugeordnet – Entwurf ohne CC."
    erfolg, meldung, weblink, conversation_id = graph_versand.entwurf_erstellen(
        kunde, angebot, pdf_pfad, betreff, text,
        weitere_anhaenge=[Path(a.pfad) for a in anhaenge if a.vorhanden],
        fehlende_anhaenge=[a.datei for a in anhaenge if not a.vorhanden],
        cc=cc, bcc=bcc, absender=absender)
    if erfolg:
        meldung += f" ({vorlage_quelle}, Absender {absender})" + cc_hinweis
        # Mail-Verlauf (Phase 27): Konversation der Angebots-Mail merken
        if conversation_id:
            angebot.graph_conversation_id = conversation_id
        # Status-Kette (Phase 31): „Versand vorbereitet“ → Graph-Abgleich → „Versendet“
        if angebot.status == "Entwurf":
            angebot.status = "Versand vorbereitet"
        session.commit()
    ziel = f"/angebote/{angebot_id}?meldung={quote_plus(meldung)}"
    if erfolg:
        ziel += "&versand=1"
        if weblink:
            ziel += f"&weblink={quote_plus(weblink)}"
    return RedirectResponse(ziel, status_code=303)


@router.post("/{angebot_id}/verfolgung")
async def verfolgung_setzen(request: Request, angebot_id: int,
                            session: Session = Depends(get_session)):
    """Angebotsverfolgung (v6): Hot-Ampel + Wiedervorlage-Datum; optional
    eine Notiz an den Verlauf anhängen (append-only)."""
    from urllib.parse import quote_plus

    from app.models import AngebotsNotiz
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = await request.form()
    ampel = form.get("verfolgung_ampel") or ""
    if ampel in ("", "heiss", "warm", "kalt"):
        angebot.verfolgung_ampel = ampel
    datum = (form.get("wiedervorlage_am") or "").strip()
    if datum:
        from datetime import datetime as dt
        try:
            angebot.wiedervorlage_am = dt.strptime(datum, "%Y-%m-%d")
        except ValueError:
            pass
    else:
        angebot.wiedervorlage_am = None
    notiz = (form.get("notiz") or "").strip()
    if notiz:
        benutzer = request.state.benutzer
        session.add(AngebotsNotiz(angebot_id=angebot.id, text=notiz[:2000],
                                  benutzer_name=benutzer.name if benutzer else "?"))
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "Verfolgung aktualisiert"), status_code=303)


@router.post("/{angebot_id}/foerderung")
async def foerderung_setzen(request: Request, angebot_id: int,
                            session: Session = Depends(get_session)):
    """Förderung (v6): Zuschuss manuell überschreiben (leer = automatisch)
    und den KfW-Block im PDF ausblenden."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    from urllib.parse import quote_plus
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = await request.form()
    wert = (form.get("betrag") or "").strip()
    if wert:
        cent = preis_parsen(wert)
        if cent is None or cent < 0:
            return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
                "Förderbetrag ungültig"), status_code=303)
        angebot.foerderung_manuell_cent = cent
    else:
        angebot.foerderung_manuell_cent = None   # zurück zur Automatik
    angebot.foerderung_ausblenden = form.get("ausblenden") == "on"
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "Förderung aktualisiert"), status_code=303)


@router.post("/{angebot_id}/position/{position_id}/text")
async def position_text(request: Request, angebot_id: int, position_id: int,
                        session: Session = Depends(get_session)):
    """Artikeltext je Position editierbar (v6) – nur in diesem Angebot,
    der Artikelstamm bleibt unberührt."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    position = session.get(AngebotsPosition, position_id)
    if position and position.angebot_id == angebot_id:
        form = await request.form()
        position.bezeichnung = (form.get("bezeichnung") or "").strip()[:300]
        position.beschreibung = (form.get("beschreibung") or "").strip()
        session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)


@router.post("/{angebot_id}/vertriebler")
async def vertriebler_aendern(request: Request, angebot_id: int,
                              session: Session = Depends(get_session)):
    """Vertriebler des Angebots ändern (v5-Nachtrag): schreibt in die
    verknüpfte Erfassung (eine Quelle je Vorgang); nur bei manuellen
    Angeboten ohne Erfassung ins Feld angebot.vertriebler_id."""
    from urllib.parse import quote_plus

    from app.models import Benutzer, Erfassung
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = await request.form()
    wert = form.get("benutzer_id") or ""
    if not (wert.isdigit() and session.get(Benutzer, int(wert)) is not None):
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    erfassung = (session.query(Erfassung)
                 .filter(Erfassung.angebot_id == angebot.id).first())
    if erfassung is not None:
        erfassung.benutzer_id = int(wert)
        angebot.vertriebler_id = None
    else:
        angebot.vertriebler_id = int(wert)
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "Vertriebler geändert – CC und Mail-Vorlage folgen der neuen Zuordnung."),
        status_code=303)


@router.get("/{angebot_id}/mails")
async def mailverlauf(request: Request, angebot_id: int,
                      session: Session = Depends(get_session)):
    """Mail-Verlauf zur Angebots-Konversation (Phase 27, nur lesend)."""
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote?meldung=Angebot+nicht+gefunden", status_code=303)
    from app import mail_sync
    from app.models import AngebotsMail
    mails = (session.query(AngebotsMail)
             .filter(AngebotsMail.angebot_id == angebot.id)
             .order_by(AngebotsMail.empfangen_am.desc().nullslast()).all())
    kunde = session.get(Kunde, angebot.kunde_id)
    return render(request, "angebote/mails.html", aktiv="/angebote",
                  angebot=angebot, kunde=kunde, mails=mails,
                  sync_status=mail_sync.status)


@router.post("/{angebot_id}/status")
async def status_aendern(request: Request, angebot_id: int,
                         session: Session = Depends(get_session)):
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    form = await request.form()
    angebot = session.get(Angebot, angebot_id)
    neuer_status = form.get("status", "")
    if angebot is not None and neuer_status in ANGEBOT_STATUS:
        from app.models import angebot_status_setzen
        alter_status = angebot.status
        angebot_status_setzen(angebot, neuer_status)
        if neuer_status == "Individuell":
            angebot.archiviert = True   # v6: Individuell → automatisch ins Archiv
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
        # monday-Rückspielung (Phase 32): Trigger ist der Wechsel auf „Versendet“
        if neuer_status == "Versendet" and alter_status != "Versendet":
            from app import monday_rueckspielung
            monday_rueckspielung.bei_versand(session, angebot)
    return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)


@router.post("/{angebot_id}/monday-rueckspielung")
async def monday_erneut(request: Request, angebot_id: int,
                        session: Session = Depends(get_session)):
    """„Erneut übertragen“ nach fehlgeschlagener Rückspielung (Phase 32)."""
    from urllib.parse import quote_plus

    from app import monday_rueckspielung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    ok = monday_rueckspielung.uebertragen(session, angebot)
    meldung = ("monday-Rückspielung erfolgreich" if ok and angebot.monday_rueck_status == "ok"
               else ("monday-Rückspielung übersprungen – siehe Protokoll" if ok
                     else "monday-Rückspielung fehlgeschlagen – siehe Protokoll"))
    return RedirectResponse(f"/angebote/{angebot_id}?meldung={quote_plus(meldung)}",
                            status_code=303)


@router.post("/{angebot_id}/loeschen")
async def loeschen(request: Request, angebot_id: int,
                   session: Session = Depends(get_session)):
    """Nur Entwürfe löschbar (v5); alles andere wird archiviert."""
    from pathlib import Path
    from urllib.parse import quote_plus

    from app.models import AngebotsMail, Erfassung
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    if angebot.status != "Entwurf":
        # v6: auch versendete/angenommene/abgelehnte löschbar (ID + Admin) –
        # mit Eintrag ins Lösch-Protokoll; die Nummer wird nie wiederverwendet
        from app.models import AngebotsLoeschung
        kunde = session.get(Kunde, angebot.kunde_id)
        benutzer = request.state.benutzer
        session.add(AngebotsLoeschung(
            nummer=angebot.nummer,
            kunde_name=kunde.anzeige_name if kunde else "",
            status_vorher=angebot.status,
            endbetrag_cent=angebot.summen()["endbetrag"],
            benutzer_name=benutzer.name if benutzer else "?"))
    nummer = angebot.nummer
    # Verknüpfte Erfassung lösen: sie ist wieder offen für ein neues Angebot
    for erfassung in session.query(Erfassung).filter(Erfassung.angebot_id == angebot.id):
        erfassung.angebot_id = None
        if erfassung.status == "In Bearbeitung":
            erfassung.status = "Neu"
    session.query(AngebotsMail).filter(AngebotsMail.angebot_id == angebot.id).delete()
    session.delete(angebot)   # Positionen per Cascade
    session.commit()
    from app import config
    Path(config.ANGEBOTE_PDF_ORDNER / f"{nummer}.pdf").unlink(missing_ok=True)
    benutzer = request.state.benutzer
    if benutzer is not None:
        sperren.freigeben(angebot_id, benutzer.id)
    return RedirectResponse("/angebote?meldung=" + quote_plus(f"Entwurf {nummer} gelöscht"),
                            status_code=303)


@router.post("/{angebot_id}/archivieren")
async def archivieren(request: Request, angebot_id: int,
                      session: Session = Depends(get_session)):
    """Versendete/angenommene/abgelehnte Angebote ins Archiv bzw. zurück (v5)."""
    from urllib.parse import quote_plus
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    if angebot.status == "Entwurf" and not angebot.archiviert:
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "Entwürfe werden nicht archiviert, sondern gelöscht."), status_code=303)
    angebot.archiviert = not angebot.archiviert
    session.commit()
    if angebot.archiviert:
        return RedirectResponse("/angebote?meldung=" + quote_plus(
            f"{angebot.nummer} archiviert – über den Filter „Archiv“ weiterhin erreichbar."),
            status_code=303)
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "Aus dem Archiv zurückgeholt."), status_code=303)


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
            ek_cent=p.ek_cent, guid=p.guid))
    session.commit()
    return RedirectResponse(f"/angebote/{kopie.id}?meldung=Angebot+dupliziert", status_code=303)
