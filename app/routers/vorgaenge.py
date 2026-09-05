# Vorgangsakte (v10, Phase 59): Liste mit Suche + Detailakte je Vorgang –
# Kopf (Kunde, Ausführungsort, Kanal/Profil, Sparten-Chips, Vertriebler),
# Bereiche Erfassungen · Angebote · Mail-Verlauf · Verfolgung · Notizen-Chat.
# Außendienst sieht ausschließlich die eigenen Vorgänge (read-only + Notizen).

from datetime import datetime
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import vorgaenge as vorgaenge_modul
from app.db import get_session
from app.models import (Angebot, AngebotsMail, Benutzer, Erfassung, Kunde,
                        Lead, Vorgang, VorgangNotizGelesen, VorgangsNotiz)
from app.templating import render

router = APIRouter(prefix="/vorgaenge")


def _eigener(session: Session, vorgang: Vorgang, benutzer) -> bool:
    if benutzer is None:
        return False
    if benutzer.rolle in ("admin", "innendienst"):
        return True
    return vorgaenge_modul.gehoert_benutzer(session, vorgang, benutzer.id)


def _chips_fuer_vorgang(session: Session, vorgang: Vorgang,
                        erfassungen: list[Erfassung]) -> list[tuple[str, str]]:
    """Sparten-Chips: beim Lead-Vorgang wie in „Leads VOT“, sonst aus den
    tatsächlich vorhandenen Erfassungen (alle erfasst)."""
    from app.routers.leads import sparten_chips
    erfasst = {e.sparte or "WP" for e in erfassungen if e.status != "Entwurf"}
    if vorgang.lead_id:
        lead = session.get(Lead, vorgang.lead_id)
        if lead is not None:
            return sparten_chips(lead, erfasst)
    return [(s, "erfasst") for s in sorted(erfasst)]


@router.get("")
async def liste(request: Request, q: str = "", verfolgung: str = "",
                session: Session = Depends(get_session)):
    """Vorgangsliste mit Suche (Kunde, Ort, Angebotsnummer); AD nur eigene.
    verfolgung=faellig zeigt rollenbezogen die fälligen Wiedervorlagen."""
    from datetime import datetime as dt
    benutzer = request.state.benutzer
    vorgaenge = (session.query(Vorgang)
                 .order_by(Vorgang.angelegt_am.desc()).all())
    if verfolgung == "faellig":   # Phase 60: rollenbezogene Fälligkeit
        vorgaenge = [v for v in vorgaenge
                     if v.wiedervorlage_am and v.wiedervorlage_am <= dt.now()
                     and vorgaenge_modul.wiedervorlage_gehoert(session, v, benutzer)]
    elif verfolgung in ("heiss", "warm", "kalt"):
        vorgaenge = [v for v in vorgaenge if v.verfolgung_ampel == verfolgung]
    kunden = {k.id: k for k in session.query(Kunde)}
    leads = {l.id: l for l in session.query(Lead)}
    erf_je_vorgang: dict[int, list[Erfassung]] = {}
    for e in session.query(Erfassung).filter(Erfassung.vorgang_id.isnot(None)):
        erf_je_vorgang.setdefault(e.vorgang_id, []).append(e)
    ang_je_vorgang: dict[int, list[Angebot]] = {}
    for a in session.query(Angebot).filter(Angebot.vorgang_id.isnot(None)):
        ang_je_vorgang.setdefault(a.vorgang_id, []).append(a)
    if benutzer.rolle == "aussendienst":
        vorgaenge = [v for v in vorgaenge
                     if vorgaenge_modul.gehoert_benutzer(session, v, benutzer.id)]
    if q:
        suchwort = q.lower()
        def passt(v: Vorgang) -> bool:
            kunde = kunden.get(v.kunde_id)
            if kunde is not None and (suchwort in kunde.anzeige_name.lower()
                                      or suchwort in (kunde.ort or "").lower()
                                      or suchwort in (kunde.plz or "")):
                return True
            return any(suchwort in a.nummer.lower()
                       or suchwort in (a.taifun_nummer or "").lower()
                       for a in ang_je_vorgang.get(v.id, []))
        vorgaenge = [v for v in vorgaenge if passt(v)]
    chips = {v.id: _chips_fuer_vorgang(session, v, erf_je_vorgang.get(v.id, []))
             for v in vorgaenge}
    # „Neue Notizen“-Punkt (Phase 60): letzte Notiz nach dem Gelesen-Stand?
    gelesen = {g.vorgang_id: g.gelesen_bis for g in
               session.query(VorgangNotizGelesen)
               .filter(VorgangNotizGelesen.benutzer_id == benutzer.id)}
    neue_notizen: set[int] = set()
    for notiz in session.query(VorgangsNotiz):
        stand = gelesen.get(notiz.vorgang_id)
        if (stand is None or notiz.zeit > stand) and notiz.benutzer_id != benutzer.id:
            neue_notizen.add(notiz.vorgang_id)
    return render(request, "vorgaenge/liste.html", aktiv="/vorgaenge",
                  mobil=benutzer.rolle == "aussendienst",
                  vorgaenge=vorgaenge, kunden=kunden, leads=leads,
                  erf_je_vorgang=erf_je_vorgang, ang_je_vorgang=ang_je_vorgang,
                  chips=chips, neue_notizen=neue_notizen, q=q,
                  verfolgung=verfolgung, benutzer=benutzer,
                  meldung=request.query_params.get("meldung", ""))


@router.get("/zu-lead/{lead_id}")
async def zu_lead(lead_id: int, session: Session = Depends(get_session)):
    lead = session.get(Lead, lead_id)
    if lead is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    vorgang = vorgaenge_modul.vorgang_fuer_lead(session, lead)
    session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang.id}", status_code=303)


@router.get("/zu-erfassung/{erfassung_id}")
async def zu_erfassung(erfassung_id: int, session: Session = Depends(get_session)):
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    vorgang = vorgaenge_modul.vorgang_fuer_erfassung(session, erfassung)
    session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang.id}", status_code=303)


@router.get("/zu-angebot/{angebot_id}")
async def zu_angebot(angebot_id: int, session: Session = Depends(get_session)):
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang.id}", status_code=303)


@router.get("/{vorgang_id}")
async def akte(request: Request, vorgang_id: int,
               session: Session = Depends(get_session)):
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    if not _eigener(session, vorgang, benutzer):
        return RedirectResponse("/vorgaenge?meldung=" + quote_plus(
            "Kein Zugriff – der Vorgang gehört einem anderen Vertriebler."),
            status_code=303)
    kunde = session.get(Kunde, vorgang.kunde_id)
    lead = session.get(Lead, vorgang.lead_id) if vorgang.lead_id else None
    erfassungen = (session.query(Erfassung)
                   .filter(Erfassung.vorgang_id == vorgang.id)
                   .order_by(Erfassung.id).all())
    angebote = (session.query(Angebot)
                .filter(Angebot.vorgang_id == vorgang.id)
                .order_by(Angebot.nummer).all())
    mails = (session.query(AngebotsMail)
             .filter(AngebotsMail.angebot_id.in_([a.id for a in angebote] or [0]))
             .order_by(AngebotsMail.empfangen_am.desc().nullslast()).all())
    notizen = (session.query(VorgangsNotiz)
               .filter(VorgangsNotiz.vorgang_id == vorgang.id)
               .order_by(VorgangsNotiz.zeit, VorgangsNotiz.id).all())
    # Gelesen-Stand fortschreiben (Phase 60: „Neue Notizen“-Punkt)
    marker = (session.query(VorgangNotizGelesen)
              .filter(VorgangNotizGelesen.vorgang_id == vorgang.id,
                      VorgangNotizGelesen.benutzer_id == benutzer.id).first())
    if marker is None:
        session.add(VorgangNotizGelesen(vorgang_id=vorgang.id,
                                        benutzer_id=benutzer.id))
    else:
        marker.gelesen_bis = datetime.now()
    session.commit()
    kanal = ((lead.vertriebskanal if lead else "")
             or (kunde.vertriebskanal if kunde else ""))
    from app import angebotsprofile
    profil = angebotsprofile.profil_fuer_kanal(session, kanal)
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    vertriebler_ids = ({lead.benutzer_id} if lead and lead.benutzer_id else set())
    vertriebler_ids |= {e.benutzer_id for e in erfassungen if e.benutzer_id}
    vertriebler_ids |= {a.vertriebler_id for a in angebote if a.vertriebler_id}
    erfassung_offen = next((e for e in erfassungen if e.status == "Entwurf"), None)
    aussendienst = [b for b in benutzer_map.values()
                    if b.rolle == "aussendienst" and b.aktiv]
    return render(request, "vorgaenge/akte.html", aktiv="/vorgaenge",
                  mobil=benutzer.rolle == "aussendienst",
                  vorgang=vorgang, kunde=kunde, lead=lead, kanal=kanal,
                  profil=profil, erfassungen=erfassungen, angebote=angebote,
                  mails=mails, notizen=notizen, benutzer=benutzer,
                  benutzer_map=benutzer_map,
                  chips=_chips_fuer_vorgang(session, vorgang, erfassungen),
                  vertriebler=[benutzer_map[i] for i in sorted(vertriebler_ids)
                               if i in benutzer_map],
                  erfassung_offen=erfassung_offen,
                  aussendienst=sorted(aussendienst, key=lambda b: b.name),
                  heute=datetime.now(),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/{vorgang_id}/verfolgung")
async def verfolgung(request: Request, vorgang_id: int,
                     session: Session = Depends(get_session)):
    """Phase 60: Verfolgung des Vorgangs aus der Akte setzen (ID überall,
    AD an eigenen Vorgängen; den Verantwortlichen ändert nur der ID)."""
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None or not _eigener(session, vorgang, benutzer):
        return RedirectResponse("/vorgaenge", status_code=303)
    form = await request.form()
    verantwortlicher_id = None
    if benutzer.rolle in ("admin", "innendienst"):
        try:
            verantwortlicher_id = int(form.get("wv_verantwortlicher") or 0) or None
        except ValueError:
            verantwortlicher_id = None
    vorgaenge_modul.verfolgung_setzen(
        session, vorgang, benutzer,
        form.get("verfolgung_ampel") or "", form.get("wiedervorlage_am") or "",
        notiz=form.get("notiz") or "", verantwortlicher_id=verantwortlicher_id)
    session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang_id}?meldung=" + quote_plus(
        "Verfolgung aktualisiert."), status_code=303)


@router.post("/{vorgang_id}/notiz")
async def notiz(request: Request, vorgang_id: int,
                session: Session = Depends(get_session)):
    """Notizen-Chat: append-only – jeder Eintrag mit Autor + Zeitstempel,
    kein Bearbeiten/Löschen. AD nur an eigenen Vorgängen."""
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    if not _eigener(session, vorgang, benutzer):
        return RedirectResponse("/vorgaenge", status_code=303)
    form = await request.form()
    text = (form.get("text") or "").strip()
    if text:
        vorgaenge_modul.notiz_anlegen(session, vorgang.id, benutzer, text[:2000])
        # der eigene Eintrag gilt sofort als gelesen
        marker = (session.query(VorgangNotizGelesen)
                  .filter(VorgangNotizGelesen.vorgang_id == vorgang.id,
                          VorgangNotizGelesen.benutzer_id == benutzer.id).first())
        if marker is not None:
            marker.gelesen_bis = datetime.now()
        session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang_id}#notizen", status_code=303)
