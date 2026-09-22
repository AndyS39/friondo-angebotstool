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
                verfolgung: str = "", sparte: str = "",
                session: Session = Depends(get_session)):
    abfrage = session.query(Angebot).options(joinedload(Angebot.positionen))
    if sparte:   # Sparten-Filter (v8): Konfigurator-Typ des Angebots
        abfrage = abfrage.filter(Angebot.konfigurator_typ == sparte)
    # Archiv (v5): Standardansicht ohne archivierte, Filter „Archiv“ nur diese
    if status == "archiv":
        abfrage = abfrage.filter(Angebot.archiviert.is_(True))
    else:
        abfrage = abfrage.filter(Angebot.archiviert.is_(False))
        if status:
            abfrage = abfrage.filter(Angebot.status == status)
        else:
            # v9: überholte Versionen nur über den Status-Filter/die Historie
            abfrage = abfrage.filter(Angebot.status != "Überholt")
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
    # v11 (Phase 66): Projekt-Verknüpfung je Angebot (Zeilenaktion)
    from app import projektierung as projektierung_modul
    from app.models import Gewerk as GewerkModell, Projekt as ProjektModell
    gewerk_map = {g.id: g for g in session.query(GewerkModell)}
    projekt_map = {p.id: p for p in session.query(ProjektModell)}
    projekt_je_angebot = {}
    for a in angebote:
        if a.projekt_gewerk_id and a.projekt_gewerk_id in gewerk_map:
            g = gewerk_map[a.projekt_gewerk_id]
            if g.projekt_id in projekt_map:
                projekt_je_angebot[a.id] = projekt_map[g.projekt_id]
    projekt_modul_ok = projektierung_modul.modul_sichtbar(session, request.state.benutzer)
    # Verfolgung (v10): Ampel/Wiedervorlage des VORGANGS je Angebot
    from app.models import Vorgang
    vorgaenge_map = {v.id: v for v in session.query(Vorgang)}
    def vorgang_von(a):
        return vorgaenge_map.get(a.vorgang_id)
    if verfolgung == "faellig":   # fällige Vorgangs-Wiedervorlagen
        from datetime import datetime as dt
        angebote = [a for a in angebote
                    if (v := vorgang_von(a)) is not None
                    and v.wiedervorlage_am and v.wiedervorlage_am <= dt.now()]
    elif verfolgung in ("heiss", "warm", "kalt"):
        angebote = [a for a in angebote
                    if (v := vorgang_von(a)) is not None
                    and v.verfolgung_ampel == verfolgung]
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
                  kanal=kanal, verfolgung=verfolgung, sparte=sparte,
                  vorgaenge_map=vorgaenge_map,
                  projekt_je_angebot=projekt_je_angebot,
                  projekt_modul_ok=projekt_modul_ok,
                  heute=__import__("datetime").datetime.now(),
                  kanal_werte=sorted({kunden[a.kunde_id].vertriebskanal for a in angebote
                                      if a.kunde_id in kunden and kunden[a.kunde_id].vertriebskanal}
                                     | ({kanal} if kanal else set())),
                  vertriebler=vertriebler, angebot_vertriebler=angebot_vertriebler,
                  vertriebler_werte=vertriebler_werte,
                  status_liste=ANGEBOT_STATUS, mail_zaehler=mail_zaehler,
                  db_rot_cent=rot_unter * 100, db_gruen_cent=gruen_ueber * 100,
                  # v11 (Phase 70): Rolle projektierung sieht die Liste lesend –
                  # DB-Spalte nur mit kalkulation_sichtbar, Öffnen → PDF
                  kalk_sichtbar=(request.state.benutzer.rolle in ("admin", "innendienst")
                                 or request.state.benutzer.kalkulation_sichtbar),
                  nur_lesend=request.state.benutzer.rolle == "projektierung",
                  meldung=request.query_params.get("meldung", ""))


@router.get("/rabatt-freigaben")
async def rabatt_freigaben(request: Request, session: Session = Depends(get_session)):
    """v10 (Phase 59): offene AD-Rabatt-Anfragen – der Innendienst sieht die
    €-Auswirkung auf den DB und genehmigt oder lehnt mit Kommentar ab."""
    from app.models import Benutzer, RabattFreigabe
    from app.routers.meine_angebote import _db_ampel, _db_mit_rabatt
    freigaben = (session.query(RabattFreigabe)
                 .filter(RabattFreigabe.status == "offen")
                 .order_by(RabattFreigabe.angefragt_am).all())
    angebote = {a.id: a for a in session.query(Angebot)
                .filter(Angebot.id.in_([f.angebot_id for f in freigaben] or [0]))}
    kunden = _kunden_map(session, angebote.values())
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    zeilen = []
    for f in freigaben:
        angebot = angebote.get(f.angebot_id)
        if angebot is None:
            continue
        db_neu = _db_mit_rabatt(angebot, f.rabatt_cent, f.rabatt_prozent)
        zeilen.append({"freigabe": f, "angebot": angebot,
                       "kunde": kunden.get(angebot.kunde_id),
                       "ad": benutzer_map.get(f.benutzer_id),
                       "db_alt": angebot.deckungsbeitrag()["db"],
                       "db_neu": db_neu,
                       "ampel_neu": _db_ampel(session, db_neu)})
    return render(request, "angebote/rabatt_freigaben.html", aktiv="/angebote",
                  zeilen=zeilen,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/rabatt-freigaben/{freigabe_id}/entscheiden")
async def rabatt_entscheiden(request: Request, freigabe_id: int,
                             session: Session = Depends(get_session)):
    """Genehmigen wendet den Rabatt an (Entwurf direkt, versendet → neue
    Version); Ablehnen verlangt einen Kommentar. Beides landet im
    Notizen-Chat des Vorgangs."""
    from urllib.parse import quote_plus

    from app import vorgaenge as vorgaenge_modul
    from app.models import RabattFreigabe
    from app.routers.meine_angebote import rabatt_anwenden
    freigabe = session.get(RabattFreigabe, freigabe_id)
    if freigabe is None or freigabe.status != "offen":
        return RedirectResponse("/angebote/rabatt-freigaben", status_code=303)
    form = await request.form()
    aktion = form.get("aktion", "")
    kommentar = (form.get("kommentar") or "").strip()[:500]
    benutzer = request.state.benutzer
    angebot = session.get(Angebot, freigabe.angebot_id)
    rabatt_text = (f"{freigabe.rabatt_prozent:g} %" if freigabe.rabatt_prozent
                   else f"{(freigabe.rabatt_cent or 0) / 100:.2f} €".replace(".", ","))
    from datetime import datetime as dt
    if aktion == "genehmigen" and angebot is not None:
        ziel = rabatt_anwenden(session, angebot, freigabe.rabatt_cent,
                               freigabe.rabatt_prozent, freigabe.rabatt_bezeichnung)
        if ziel.id != angebot.id:
            from app import monday_rueckspielung
            monday_rueckspielung.wert_aktualisieren(session, ziel,
                                                    "neue Version (Rabatt-Freigabe)")
        freigabe.status = "genehmigt"
        freigabe.kommentar = kommentar
        freigabe.entschieden_am = dt.now()
        freigabe.entschieden_von = benutzer.id
        if freigabe.vorgang_id:
            vorgaenge_modul.notiz_anlegen(
                session, freigabe.vorgang_id, benutzer,
                f"Rabatt-Freigabe GENEHMIGT: {rabatt_text} auf {ziel.nummer}"
                + (f" (neue Version von {angebot.nummer})" if ziel.id != angebot.id else "")
                + (f" – {kommentar}" if kommentar else ""),
                herkunft="Rabatt-Workflow")
        session.commit()
        return RedirectResponse("/angebote/rabatt-freigaben?meldung=" + quote_plus(
            f"Genehmigt – Rabatt {rabatt_text} steht an {ziel.nummer}."),
            status_code=303)
    if aktion == "ablehnen":
        if not kommentar:
            return RedirectResponse("/angebote/rabatt-freigaben?meldung=" + quote_plus(
                "Bitte beim Ablehnen einen Kommentar für den Außendienst angeben."),
                status_code=303)
        freigabe.status = "abgelehnt"
        freigabe.kommentar = kommentar
        freigabe.entschieden_am = dt.now()
        freigabe.entschieden_von = benutzer.id
        if freigabe.vorgang_id:
            vorgaenge_modul.notiz_anlegen(
                session, freigabe.vorgang_id, benutzer,
                f"Rabatt-Freigabe ABGELEHNT ({rabatt_text}"
                + (f" auf {angebot.nummer}" if angebot else "") + f"): {kommentar}",
                herkunft="Rabatt-Workflow")
        session.commit()
        return RedirectResponse("/angebote/rabatt-freigaben?meldung=" + quote_plus(
            "Abgelehnt – der Kommentar steht im Notizen-Chat des Vorgangs."),
            status_code=303)
    return RedirectResponse("/angebote/rabatt-freigaben", status_code=303)


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
    # Externer TAIFUN-Eintrag (v7): eigene Detailseite statt Editor –
    # kein PDF, kein Versand, aber Verfolgung, Notizen und Statuspflege
    if angebot.extern:
        from app.models import AngebotsNotiz, Benutzer as BenutzerModell, EXTERN_STATUS, Erfassung
        kunde = session.get(Kunde, angebot.kunde_id)
        erfassung = (session.query(Erfassung)
                     .filter(Erfassung.angebot_id == angebot.id).first())
        vertriebler = (session.get(BenutzerModell, angebot.vertriebler_id)
                       if angebot.vertriebler_id else None)
        notizen = (session.query(AngebotsNotiz)
                   .filter(AngebotsNotiz.angebot_id == angebot.id)
                   .order_by(AngebotsNotiz.angelegt_am.desc()).all())
        from app.models import AblehnungsGrund
        gruende = (session.query(AblehnungsGrund)
                   .filter(AblehnungsGrund.aktiv.is_(True))
                   .order_by(AblehnungsGrund.sort, AblehnungsGrund.id).all())
        from app import vorgaenge as vorgaenge_modul
        vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
        session.commit()
        from app import projektierung as projektierung_modul
        projekt_obj, _gewerk = projektierung_modul.projekt_zu_angebot(session, angebot)
        projekt_modul_ok = projektierung_modul.modul_sichtbar(session, request.state.benutzer)
        return render(request, "angebote/extern.html", aktiv="/angebote",
                      projekt_obj=projekt_obj, projekt_modul_ok=projekt_modul_ok,
                      angebot=angebot, kunde=kunde, erfassung=erfassung,
                      vertriebler=vertriebler, notizen=notizen,
                      ablehnungsgruende=gruende, vorgang=vorgang,
                      status_liste=EXTERN_STATUS,
                      meldung=request.query_params.get("meldung", ""))
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
                kfw_ergebnis = kfw.ergebnis_fuer_angebot(parameter, eingaben, angebot)
                kfw_warnung = kfw.gueltigkeits_warnung(parameter)

    # Anhänge-Vorschau (Phase 15): was würde beim Versand mitgehen?
    from app import anhaenge as anhaenge_modul
    logik, _bericht = logik_modul.hole_logik(session)
    anhaenge_liste = anhaenge_modul.fuer_angebot(logik, angebot)
    vollmacht = anhaenge_modul.vollmacht_erforderlich(angebot)

    # Angebotsverfolgung: Alt-Notizen (Historie) + Vorgang (v10: die
    # Verfolgung lebt auf Vorgangsebene, der Chat in der Vorgangsakte)
    from app import vorgaenge as vorgaenge_modul
    from app.models import AngebotsNotiz
    notizen = (session.query(AngebotsNotiz)
               .filter(AngebotsNotiz.angebot_id == angebot.id)
               .order_by(AngebotsNotiz.angelegt_am.desc()).all())
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    session.commit()
    # v11 (Phase 66): „Angebot → Projekt"-Button bzw. Link zum Projekt
    from app import projektierung as projektierung_modul
    projekt_obj, _gewerk = projektierung_modul.projekt_zu_angebot(session, angebot)
    projekt_modul_ok = projektierung_modul.modul_sichtbar(session, request.state.benutzer)
    # v10 (Phase 61): Geschwister-Angebote als Verknüpfungsziele fürs
    # Alternativ-Kennzeichen (z. B. „PV-Angebot AN-…“)
    geschwister = [f"{(a.konfigurator_typ or 'WP')}-Angebot {a.nummer}"
                   for a in session.query(Angebot)
                   .filter(Angebot.vorgang_id == vorgang.id,
                           Angebot.id != angebot.id,
                           Angebot.status != "Überholt")]

    # Vertriebler des Vorgangs (v5-Nachtrag): anzeigen + änderbar
    from app import mail_vorlagen
    from app.models import Benutzer as BenutzerModell
    angebot_vertriebler = mail_vorlagen.vertriebler_fuer_angebot(session, angebot)
    aussendienst = (session.query(BenutzerModell)
                    .filter(BenutzerModell.rolle == "aussendienst",
                            BenutzerModell.aktiv.is_(True))
                    .order_by(BenutzerModell.name).all())

    from app.models import AblehnungsGrund
    ablehnungsgruende = (session.query(AblehnungsGrund)
                         .filter(AblehnungsGrund.aktiv.is_(True))
                         .order_by(AblehnungsGrund.sort, AblehnungsGrund.id).all())
    # v9: Angebotsprofil (Nachtext/Positions-/Versandregeln) + Vortext-Override
    from app import angebotsprofile
    from app.models import Profil
    profil = angebotsprofile.profil_fuer_angebot(session, angebot, kunde)
    profile = session.query(Profil).order_by(Profil.id).all()
    # v9: Versions-Historie über die Stammnummer
    stamm = angebot.stamm_nummer
    versionen = (session.query(Angebot)
                 .filter(or_(Angebot.nummer == stamm,
                             Angebot.nummer.like(f"{stamm}.%")))
                 .order_by(Angebot.nummer).all())
    # v9: fachliche Hinweise (z. B. Solarthermie-Widerspruch) aus dem Protokoll
    from app import konfigurator as engine_modul
    fachhinweise = engine_modul.hinweise_aus_protokoll(protokoll)
    profil_hinweise = {p_.id: angebotsprofile.regeln_beschreibung(p_) for p_ in profile}
    return render(request, "angebote/editor.html", aktiv="/angebote",
                  ablehnungsgruende=ablehnungsgruende,
                  profil=profil, profile=profile, profil_hinweise=profil_hinweise,
                  fachhinweise=fachhinweise, versionen=versionen,
                  vorgang=vorgang, geschwister=geschwister,
                  projekt_obj=projekt_obj, projekt_modul_ok=projekt_modul_ok,
                  vortext_standard=angebotsprofile.vortext_fuer_angebot(session, angebot),
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
    # v10 (Phase 61): „Alternativ – in anderem Angebot enthalten“ – zählt wie
    # EP nicht mit; die Verknüpfung nennt das Geschwister-Angebot (oder Text)
    position.alternativ = form.get("alternativ") == "on"
    if position.alternativ:
        position.alternativ_zu = (form.get("alternativ_zu") or "").strip()[:200]
    else:
        position.alternativ_zu = ""
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
    if angebot.extern:   # v7: externer TAIFUN-Eintrag hat kein PDF
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=Externer+Eintrag+ohne+PDF",
                                status_code=303)
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

    angebot_vorab = session.get(Angebot, angebot_id)
    if angebot_vorab is not None and angebot_vorab.extern:   # v7: kein Versand
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "Externer TAIFUN-Eintrag – Versand läuft außerhalb des Tools."),
            status_code=303)
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
    # Signatur des angemeldeten ID-Mitarbeiters (v6): HTML + Inline-Bilder
    from app import signaturen
    signatur_html, inline_bilder = signaturen.fuer_versand(request.state.benutzer.id)
    text += signatur_html
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
    # v9: Versandregeln des Angebotsprofils (Enni: CC energieberatung@enni.de;
    # SWD: Empfänger leer – der Innendienst trägt den SWD-Kontakt manuell ein)
    from app import angebotsprofile
    profil = angebotsprofile.profil_fuer_angebot(session, angebot, kunde)
    if profil is not None and profil.versand_cc:
        cc += [a.strip() for a in profil.versand_cc.split(",")
               if a.strip() and a.strip() not in cc]
    empfaenger_leer = bool(profil is not None and profil.empfaenger_leer)
    if empfaenger_leer:
        cc_hinweis += (" PFLICHT: Empfänger ist leer (SWD-Profil) – bitte den "
                       "SWD-Kontakt vor dem Senden in Outlook eintragen!")
    erfolg, meldung, weblink, conversation_id = graph_versand.entwurf_erstellen(
        kunde, angebot, pdf_pfad, betreff, text,
        weitere_anhaenge=[Path(a.pfad) for a in anhaenge if a.vorhanden],
        fehlende_anhaenge=[a.datei for a in anhaenge if not a.vorhanden],
        cc=cc, bcc=bcc, absender=absender, inline_bilder=inline_bilder,
        empfaenger_leer=empfaenger_leer)
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


@router.post("/{angebot_id}/profil")
async def profil_umschalten(request: Request, angebot_id: int,
                            session: Session = Depends(get_session)):
    """v9: Angebotsprofil manuell umschalten. Bei Entwürfen werden die
    Positionsregeln des neuen Profils direkt angewendet; sonst ändern sich
    nur Nachtext/Versandregeln (Meldung sagt, was passiert ist)."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    from urllib.parse import quote_plus

    from app import angebotsprofile
    from app.models import Profil
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = await request.form()
    profil = session.get(Profil, int(form.get("profil_id") or 0))
    if profil is None:
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    angebot.profil_id = profil.id
    meldungen = [f"Profil auf „{profil.name}“ umgestellt."]
    if angebot.status == "Entwurf":
        meldungen += angebotsprofile.positionsregeln_anwenden(session, angebot, profil)
    else:
        meldungen.append("Positionen unverändert (kein Entwurf) – es gelten "
                         "Nachtext und Versandregeln des neuen Profils.")
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        " ".join(meldungen)), status_code=303)


@router.post("/{angebot_id}/vortext")
async def vortext_speichern(request: Request, angebot_id: int,
                            session: Session = Depends(get_session)):
    """v9: Vortext am Angebot überschreiben (leer = Profil-/Standardtext)."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    from urllib.parse import quote_plus
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = await request.form()
    angebot.vortext_text = (form.get("vortext_text") or "").strip()
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "Vortext gespeichert" if angebot.vortext_text
        else "Vortext zurück auf den Profil-Standard"), status_code=303)


@router.post("/{angebot_id}/kanal")
async def kanal_aendern(request: Request, angebot_id: int,
                        session: Session = Depends(get_session)):
    """v9: Vertriebskanal des Kunden manuell setzen (Vorrang vor dem Sync);
    mit profil_auto=1 wird das Profil anhand des neuen Kanals neu bestimmt."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    from urllib.parse import quote_plus

    from app import angebotsprofile
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    kunde = session.get(Kunde, angebot.kunde_id)
    form = await request.form()
    kanal = (form.get("kanal") or "").strip()[:100]
    if kunde is not None:
        kunde.vertriebskanal = kanal
        kunde.kanal_manuell = bool(kanal)
    meldung = f"Vertriebskanal auf „{kanal or '–'}“ gesetzt."
    if form.get("profil_auto") == "1":
        angebot.profil_id = None   # Auto-Auswahl über den neuen Kanal
        profil = angebotsprofile.profil_fuer_angebot(session, angebot, kunde)
        if profil is not None:
            angebot.profil_id = profil.id
            meldung += f" Profil automatisch: „{profil.name}“."
            if angebot.status == "Entwurf":
                aenderungen = angebotsprofile.positionsregeln_anwenden(
                    session, angebot, profil)
                if aenderungen:
                    meldung += " " + " ".join(aenderungen)
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(meldung),
                            status_code=303)


@router.post("/{angebot_id}/verfolgung")
async def verfolgung_setzen(request: Request, angebot_id: int,
                            session: Session = Depends(get_session)):
    """Verfolgung (v10, Phase 60): lebt auf VORGANGSEBENE – EINE Hot-Ampel und
    Wiedervorlage je Kundenanfrage; die Notiz geht in den Vorgangs-Chat."""
    from urllib.parse import quote_plus

    from app import vorgaenge as vorgaenge_modul
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = await request.form()
    try:
        verantwortlicher_id = int(form.get("wv_verantwortlicher") or 0) or None
    except ValueError:
        verantwortlicher_id = None
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    vorgaenge_modul.verfolgung_setzen(
        session, vorgang, request.state.benutzer,
        form.get("verfolgung_ampel") or "", form.get("wiedervorlage_am") or "",
        notiz=form.get("notiz") or "", verantwortlicher_id=verantwortlicher_id)
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "Verfolgung aktualisiert (gilt für den gesamten Vorgang)"), status_code=303)


@router.post("/{angebot_id}/foerderung")
async def foerderung_setzen(request: Request, angebot_id: int,
                            session: Session = Depends(get_session)):
    """Förderung (v8): baustein-basierte Overrides – Grundförderung, Klima-Bonus,
    Einkommensbonus (je %), förderfähige Höchstkosten (€). Leeres Feld =
    automatisch. Speichern setzt einen alten Gesamt-Override (v6) zurück."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    from urllib.parse import quote_plus
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = await request.form()

    def prozent_lesen(name):
        roh = (form.get(name) or "").strip()
        if not roh:
            return None, ""
        from app.konfigurator import zahl_parsen
        zahl = zahl_parsen(roh)
        if zahl is None or zahl < 0 or zahl > 100:
            return None, f"Ungültiger Prozentwert bei {name}"
        return zahl, ""

    grund, f1 = prozent_lesen("grund_prozent")
    klima, f2 = prozent_lesen("klima_prozent")
    einkommen, f3 = prozent_lesen("einkommen_prozent")
    fehler = f1 or f2 or f3
    hoechst = None
    roh = (form.get("hoechstkosten") or "").strip()
    if roh:
        hoechst = preis_parsen(roh)
        if hoechst is None or hoechst <= 0:
            fehler = "Ungültige Höchstkosten"
    if fehler:
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(fehler),
                                status_code=303)
    angebot.foerder_grund_prozent = grund
    angebot.foerder_klima_prozent = klima
    angebot.foerder_einkommen_prozent = einkommen
    angebot.foerder_hoechstkosten_cent = hoechst
    angebot.foerderung_manuell_cent = None   # Alt-Override (v6) entfällt
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
        from app.models import EXTERN_STATUS, angebot_status_setzen
        if angebot.extern and neuer_status not in EXTERN_STATUS:
            return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
        # v8: Ablehnung nur mit Grund (Pflichtdialog, Tool + extern)
        if neuer_status == "Abgelehnt":
            from urllib.parse import quote_plus

            from app.models import AblehnungsGrund, AngebotsNotiz
            grund = (form.get("ablehnungsgrund") or "").strip()
            bekannt = {g.name for g in session.query(AblehnungsGrund)
                       .filter(AblehnungsGrund.aktiv.is_(True))}
            if grund not in bekannt:
                return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
                    "Bitte den Grund der Ablehnung angeben (Dialog beim Status „Abgelehnt“)."),
                    status_code=303)
            angebot.ablehnungsgrund = grund
            angebot.ablehnungsgrund_text = (form.get("ablehnungsgrund_text") or "").strip()[:500]
            benutzer = request.state.benutzer
            session.add(AngebotsNotiz(
                angebot_id=angebot.id,
                benutzer_name=benutzer.name if benutzer else "?",
                text="Abgelehnt – Grund: " + grund
                     + (f" ({angebot.ablehnungsgrund_text})" if angebot.ablehnungsgrund_text else "")))
        alter_status = angebot.status
        angebot_status_setzen(angebot, neuer_status)
        # v7: „Individuell“ archiviert NICHT mehr automatisch – individuelle
        # Fälle laufen über die Erfassungs-Statuskette (TAIFUN-Warteschlange)
        # verknüpfte Erfassung automatisch pflegen (Phase 14); eine als
        # „Erledigt (extern)“ abgeschlossene Erfassung bleibt unangetastet
        from app.models import Erfassung
        erfassung = (session.query(Erfassung)
                     .filter(Erfassung.angebot_id == angebot.id).first())
        if erfassung is not None and erfassung.status != "Erledigt (extern)":
            if neuer_status in ("Versendet", "Angenommen", "Abgelehnt"):
                erfassung.status = "Erledigt"
            elif erfassung.status == "Neu":
                erfassung.status = "In Bearbeitung"
        session.commit()
        # monday-Rückspielung (Phase 32): Trigger ist der Wechsel auf „Versendet“
        if neuer_status == "Versendet" and alter_status != "Versendet":
            from app import monday_rueckspielung
            monday_rueckspielung.bei_versand(session, angebot)
        # v10 (Phase 62): Ablehnung senkt die Vorgangssumme → Wert neu schreiben
        elif (neuer_status == "Abgelehnt"
              and alter_status in ("Versendet", "Versendet (extern)", "Angenommen")):
            from app import monday_rueckspielung
            monday_rueckspielung.wert_aktualisieren(session, angebot, "Ablehnung")
        # v11 (Phase 66): neue Version „Angenommen" → Gewerk nachziehen
        if neuer_status == "Angenommen":
            from app import projektierung as projektierung_modul
            projektierung_modul.version_nachziehen(session, angebot)
            session.commit()
        # v12 (Phase 73): abgeleitete Lead-Phase am Vorgang aktualisieren
        from app import leadmanagement
        leadmanagement.phase_neu_berechnen(session, angebot.vorgang_id)
        session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)


@router.post("/{angebot_id}/taifun-pdf")
async def taifun_pdf_hochladen(request: Request, angebot_id: int,
                               session: Session = Depends(get_session)):
    """v10 (Phase 62): PDF-Upload am externen TAIFUN-Eintrag (ersetzbar, mit
    Zeitstempel) – Übergangslösung, damit Kombi-Mails alle Angebote enthalten;
    Ziel bleibt die Erstellung im Tool."""
    from datetime import datetime as dt
    from urllib.parse import quote_plus

    from app import config
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or not angebot.extern:
        return RedirectResponse("/angebote", status_code=303)
    form = await request.form()
    datei = form.get("pdf_datei")
    if datei is None or not getattr(datei, "filename", ""):
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "Bitte eine PDF-Datei auswählen."), status_code=303)
    inhalt = await datei.read()
    if not inhalt.startswith(b"%PDF"):
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "Die Datei ist kein PDF."), status_code=303)
    ordner = config.ANGEBOTE_PDF_ORDNER / "extern"
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / f"{angebot.nummer}.pdf"
    ziel.write_bytes(inhalt)
    ersetzt = bool(angebot.extern_pdf_pfad)
    angebot.extern_pdf_pfad = str(ziel)
    angebot.extern_pdf_am = dt.now()
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        ("PDF ersetzt" if ersetzt else "PDF hinterlegt")
        + " – der Eintrag ist jetzt im Kombi-Versand wählbar."), status_code=303)


@router.get("/{angebot_id}/taifun-pdf")
async def taifun_pdf_anzeigen(angebot_id: int, session: Session = Depends(get_session)):
    """Hinterlegtes TAIFUN-PDF anzeigen."""
    from pathlib import Path as _Path
    angebot = session.get(Angebot, angebot_id)
    if (angebot is None or not angebot.extern or not angebot.extern_pdf_pfad
            or not _Path(angebot.extern_pdf_pfad).exists()):
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    return FileResponse(angebot.extern_pdf_pfad, media_type="application/pdf",
                        content_disposition_type="inline",
                        filename=f"{angebot.taifun_nummer or angebot.nummer}.pdf")


@router.post("/{angebot_id}/taifun-nummer")
async def taifun_nummer_setzen(request: Request, angebot_id: int,
                               session: Session = Depends(get_session)):
    """v7: TAIFUN-Angebotsnummer am externen Eintrag nachtragen."""
    from urllib.parse import quote_plus
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or not angebot.extern:
        return RedirectResponse("/angebote", status_code=303)
    form = await request.form()
    angebot.taifun_nummer = (form.get("taifun_nummer") or "").strip()[:30]
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "TAIFUN-Nummer gespeichert" if angebot.taifun_nummer else "TAIFUN-Nummer entfernt"),
        status_code=303)


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
    war_in_summe = angebot.status in ("Versendet", "Versendet (extern)", "Angenommen")
    session.delete(angebot)   # Positionen per Cascade
    session.commit()
    if war_in_summe:
        # v10 (Phase 62): Vorgangssumme ohne das gelöschte Angebot schreiben
        from app import monday_rueckspielung
        monday_rueckspielung.wert_aktualisieren(session, angebot, "Löschung",
                                                protokoll=False)
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


@router.post("/{angebot_id}/ueberarbeiten")
async def ueberarbeiten(request: Request, angebot_id: int,
                        session: Session = Depends(get_session)):
    """v9: neue Version (.2/.3 …) eines versendeten/angenommenen Angebots als
    Entwurf; das Original wird „Überholt“ (zählt nicht mehr in Statistik,
    Summenzeile und 90-Tage-Lauf). Verfolgung, Mail-Konversation und die
    Erfassungs-/Lead-Verknüpfung laufen an der neuen Version weiter."""
    from urllib.parse import quote_plus

    from app.models import Erfassung
    original = session.get(Angebot, angebot_id)
    if original is None:
        return RedirectResponse("/angebote", status_code=303)
    if original.extern or original.status not in ("Versendet", "Angenommen"):
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "Überarbeiten geht nur bei versendeten/angenommenen Tool-Angeboten."),
            status_code=303)
    version = angebot_aufbau.version_erzeugen(session, original)
    neue_nummer = version.nummer
    session.commit()
    # v10 (Phase 62): monday-Deal-Wert folgt der Vorgangssumme (Original
    # zählt als „Überholt" nicht mehr mit)
    from app import monday_rueckspielung
    monday_rueckspielung.wert_aktualisieren(session, version, "neue Version")
    return RedirectResponse(f"/angebote/{version.id}?meldung=" + quote_plus(
        f"Version {neue_nummer} als Entwurf erstellt – {original.nummer} ist "
        "jetzt „Überholt“."), status_code=303)


@router.post("/{angebot_id}/duplizieren")
async def duplizieren(angebot_id: int, session: Session = Depends(get_session)):
    original = session.get(Angebot, angebot_id)
    if original is None:
        return RedirectResponse("/angebote", status_code=303)
    if original.extern:   # v7: externe TAIFUN-Einträge werden nicht dupliziert
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=Externer+Eintrag+nicht+duplizierbar",
                                status_code=303)
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
