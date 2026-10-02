# Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 108) – Router Termin. Eigener
# Router mit demselben Präfix, in app/main.py VOR dem V1-Router eingebunden:
# GET/POST /lead/{id}/termin (Assistent V2, übernimmt die V1-Pfade),
# POST …/termin/manuell (15-Min-Raster, Konfliktwarnung), GET/POST …/termin/vorab
# (Telefon/Teams, A-2), POST /termin/{tid}/absagen (+ Ersatzkunde-Dialog
# GET /termin/{tid}/ersatz), POST /termin/{tid}/bestaetigung-erneut (A-9),
# POST /termin/{tid}/verschieben (ICS-UID wird weitergetragen), GET /kalender
# (Terminarten farblich, vorgemerkt gestrichelt), GET /termin/konflikt (JSON).
# Alle Routen laufen über lead_v2.gate (Handelsvertreter: nur eigene Leads,
# nur eigener Kalender).

from datetime import datetime, timedelta
from urllib.parse import quote_plus, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import lead_termin, lead_v2
from app import leadmanagement as kern
from app.db import get_session
from app.models import (Benutzer, Kunde, Vorgang, VotTermin, TERMIN_TYP_NAMEN,
                        VOT_STATUS_NAMEN)
from app.templating import render

router = APIRouter(prefix="/lead-management")

VOT_STATUS_NAMEN_V2 = dict(VOT_STATUS_NAMEN, vorgemerkt="Vorgemerkt")


def _kartei(vorgang_id: int, meldung: str = "") -> str:
    url = f"/lead-management/lead/{vorgang_id}"
    return url + (f"?meldung={quote_plus(meldung)}" if meldung else "")


def _assistent_url(vorgang_id: int, meldung: str = "", **params) -> str:
    werte = {k: v for k, v in params.items() if v not in (None, "")}
    if meldung:
        werte["meldung"] = meldung
    return (f"/lead-management/lead/{vorgang_id}/termin"
            + (f"?{urlencode(werte)}" if werte else ""))


def _vorgang_oder_404(request: Request, session: Session, vorgang_id: int) -> Vorgang:
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        raise HTTPException(status_code=404)
    lead_v2.gate(request, session, vorgang)
    return vorgang


def _termin_oder_404(request: Request, session: Session, termin_id: int
                     ) -> tuple[VotTermin, Vorgang]:
    termin = session.get(VotTermin, termin_id)
    if termin is None:
        raise HTTPException(status_code=404)
    vorgang = _vorgang_oder_404(request, session, termin.vorgang_id)
    return termin, vorgang


def _zurueck(request: Request, standard: str) -> str:
    """Redirect-Ziel: Formularfeld zurueck, sonst Referer (nur eigene Pfade)."""
    ziel = request.headers.get("referer", "")
    if ziel.startswith(str(request.base_url)):
        ziel = "/" + ziel[len(str(request.base_url)):]
    return ziel if ziel.startswith("/") else standard


def _mit_meldung(url: str, meldung: str) -> str:
    trenner = "&" if "?" in url else "?"
    return f"{url}{trenner}meldung={quote_plus(meldung)}"


def _datum_uhrzeit(form) -> datetime | None:
    """beginn (datetime-local) oder datum + uhrzeit → datetime."""
    roh = (form.get("beginn") or "").strip()
    if roh:
        try:
            return datetime.strptime(roh[:16], "%Y-%m-%dT%H:%M")
        except ValueError:
            return None
    datum = (form.get("datum") or "").strip()
    uhrzeit = (form.get("uhrzeit") or "").strip()
    if not datum or not uhrzeit:
        return None
    try:
        return datetime.strptime(f"{datum}T{uhrzeit[:5]}", "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def _geokodieren_bei_bedarf(session: Session, vorgang: Vorgang) -> None:
    """Wie V1: Adresse einmalig synchron geokodieren (Cache), nie erneut
    nach einem Fehlschlag (Hintergrundlauf/„Adresse prüfen“ übernehmen)."""
    if vorgang.lat is None and vorgang.geocode_status not in ("manuell", "fehler"):
        from app import geocoding
        adresse = geocoding.lead_adresse(session, vorgang)
        if adresse:
            lat, lon, status = geocoding.geokodieren(session, adresse)
            vorgang.lat, vorgang.lon, vorgang.geocode_status = lat, lon, status
            session.commit()


def _absage_gruende(session: Session) -> list:
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    gruende = []
    for phase in ("no_show", "verloren_vor_termin"):
        for g in logik.gruende_der_phase(phase):
            if g.grund not in [x.grund for x in gruende]:
                gruende.append(g)
    return gruende


def _termine_des_vorgangs(session: Session, vorgang_id: int) -> list[VotTermin]:
    return (session.query(VotTermin).filter(VotTermin.vorgang_id == vorgang_id)
            .order_by(VotTermin.beginn.desc()).all())


# --- Assistent (B6/E1/E2) -----------------------------------------------------------

@router.get("/lead/{vorgang_id}/termin")
async def termin_assistent(request: Request, vorgang_id: int,
                           session: Session = Depends(get_session)):
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    benutzer = request.state.benutzer
    kunde = session.get(Kunde, vorgang.kunde_id)
    _geokodieren_bei_bedarf(session, vorgang)
    q = request.query_params
    nur_ad = q.get("ad_id", "")
    nur_ad_id = int(nur_ad) if nur_ad.isdigit() else None
    hv_id = lead_termin.hv_nur_eigene(session, benutzer)
    if hv_id:
        nur_ad_id = hv_id
    ergebnis = lead_termin.vorschlaege(session, vorgang, nur_ad_id=nur_ad_id,
                                       benutzer=benutzer)
    session.commit()   # Routing-/Geocode-Cache behalten
    kandidaten = ergebnis["kandidaten"]
    kalender_ad = (nur_ad_id if nur_ad_id else (kandidaten[0].id if kandidaten else None))
    if kalender_ad and kalender_ad not in [k.id for k in kandidaten] and not hv_id:
        kalender_ad = kandidaten[0].id if kandidaten else kalender_ad
    woche = lead_termin.kalender_woche(session, [kalender_ad] if kalender_ad else [])
    buchbar = not (kern.demo_aktiv(session) and not vorgang.demo)
    pflicht_offen = lead_v2.pflichtfelder_offen(session, kunde, vorgang) if kunde else []
    umbuchen_id = q.get("umbuchen", "")
    umbuchen = session.get(VotTermin, int(umbuchen_id)) if umbuchen_id.isdigit() else None
    # Vorbelegung des manuellen Formulars (Ersatzkunde-Slot oder Rücksprung)
    slot = q.get("slot", "")
    datum, uhrzeit = q.get("datum", ""), q.get("uhrzeit", "")
    if slot and "T" in slot and not datum:
        datum, uhrzeit = slot.split("T", 1)[0], slot.split("T", 1)[1][:5]
    ersatz = None
    ersatz_fuer = q.get("ersatz_fuer", "")
    if ersatz_fuer.isdigit():
        alt = session.get(VotTermin, int(ersatz_fuer))
        if alt is not None:
            ersatz = {"termin": alt, "ad": session.get(Benutzer, alt.ad_id) if alt.ad_id else None,
                      "kunde": session.get(Kunde, session.get(Vorgang, alt.vorgang_id).kunde_id)
                      if session.get(Vorgang, alt.vorgang_id) else None}
    warnungen = [w for w in q.getlist("warnung") if w]
    termine = _termine_des_vorgangs(session, vorgang.id)
    aktive = [t for t in termine if t.status in lead_termin.BELEGT_STATUS]
    return render(request, "leadmanagement/termin.html",
                  aktiv="/lead-management", vorgang=vorgang, kunde=kunde,
                  vorschlaege=ergebnis["vorschlaege"], hinweise=ergebnis["hinweise"],
                  kandidaten=kandidaten, kandidaten_info=ergebnis["kandidaten_info"],
                  ausgeschlossen=ergebnis["ausgeschlossen"],
                  sparten=ergebnis["sparten"], kanal=ergebnis["kanal"],
                  kalender_ad=kalender_ad, woche=woche,
                  wunschzeiten=kern.wunschzeiten_liste(vorgang), buchbar=buchbar,
                  pflicht_offen=pflicht_offen, umbuchen=umbuchen,
                  umbuchen_id=umbuchen_id if umbuchen else "",
                  datum=datum, uhrzeit=uhrzeit, ersatz=ersatz, warnungen=warnungen,
                  form_ad=q.get("form_ad", ""), hv_id=hv_id,
                  termine=termine, aktive_termine=aktive,
                  absage_gruende=_absage_gruende(session),
                  typ_namen=TERMIN_TYP_NAMEN, status_namen=VOT_STATUS_NAMEN_V2,
                  benutzer_map={b.id: b for b in session.query(Benutzer)},
                  raster_manuell=lead_termin._int(
                      lead_termin.parameter(session, "vorschlag_raster_manuell_min", "15"), 15),
                  demo_badge=kern.demo_aktiv(session), now=datetime.now(),
                  meldung=q.get("meldung", ""))


@router.post("/lead/{vorgang_id}/termin")
async def termin_buchen(request: Request, vorgang_id: int,
                        session: Session = Depends(get_session)):
    """Buchen/Umbuchen aus den Vorschlägen (V1-kompatibel: beginn, ad_id,
    umweg, umbuchen_id; quelle=manuell läuft über die Konfliktprüfung)."""
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    form = await request.form()
    if (form.get("quelle") or "") == "manuell":
        return await _manuell(request, session, vorgang, form)
    benutzer = request.state.benutzer
    beginn = _datum_uhrzeit(form)
    ad_id = int(form.get("ad_id") or 0) if str(form.get("ad_id") or "").isdigit() else 0
    if beginn is None or not ad_id:
        return RedirectResponse(_assistent_url(vorgang.id, "Beginn und Außendienstler sind Pflicht."),
                                status_code=303)
    hv_id = lead_termin.hv_nur_eigene(session, benutzer)
    if hv_id and ad_id != hv_id:
        return RedirectResponse(_assistent_url(vorgang.id, "Handelsvertreter buchen nur den eigenen Kalender."),
                                status_code=303)
    umbuchen = form.get("umbuchen_id") or ""
    umweg = str(form.get("umweg") or "")
    termin, meldung, vorgemerkt = lead_termin.termin_anlegen(
        session, vorgang, ad_id, beginn, benutzer=benutzer,
        quelle=form.get("quelle") or "assistent",
        umweg=int(umweg) if umweg.lstrip("-").isdigit() else None,
        umbuchen_id=int(umbuchen) if umbuchen.isdigit() else None)
    if termin is None:
        session.rollback()
        return RedirectResponse(_assistent_url(vorgang.id, meldung), status_code=303)
    session.commit()
    return RedirectResponse(_kartei(vorgang.id, meldung), status_code=303)


async def _manuell(request: Request, session: Session, vorgang: Vorgang, form):
    """B7: Datum + Uhrzeit im 15-Minuten-Raster, AD aus den vorgefilterten
    Kandidaten, Konfliktwarnung (bestaetigt=1 übergeht Warnungen), Sperre bei
    voller Überlappung desselben AD."""
    benutzer = request.state.benutzer
    beginn = _datum_uhrzeit(form)
    ad_id = int(form.get("ad_id") or 0) if str(form.get("ad_id") or "").isdigit() else 0
    umbuchen = str(form.get("umbuchen_id") or "")
    if beginn is None or not ad_id:
        return RedirectResponse(_assistent_url(vorgang.id, "Datum, Uhrzeit und Außendienstler sind Pflicht."),
                                status_code=303)
    typ = (form.get("typ") or "vot").strip().lower()
    if typ in lead_termin.VORAB_TYPEN:
        # Kartei-Dialog „Termin manuell“ (Phase 106) schickt die Terminart mit:
        # Telefon/Teams sind Vorab-Gespräche (A-2) – kein VOT, keine Phase
        hv_id = lead_termin.hv_nur_eigene(session, benutzer)
        if hv_id and ad_id != hv_id:
            return RedirectResponse(_kartei(vorgang.id, "Handelsvertreter tragen nur eigene Termine ein."),
                                    status_code=303)
        dauer = str(form.get("dauer") or "")
        termin, meldung = lead_termin.vorab_anlegen(
            session, vorgang, typ, ad_id, beginn,
            dauer_min=int(dauer) if dauer.isdigit() else None, benutzer=benutzer)
        if termin is None:
            session.rollback()
            return RedirectResponse(_kartei(vorgang.id, meldung), status_code=303)
        session.commit()
        return RedirectResponse(_kartei(vorgang.id, meldung), status_code=303)
    raster = lead_termin._int(lead_termin.parameter(session, "vorschlag_raster_manuell_min", "15"), 15)
    beginn = lead_termin.viertelstunde(beginn, raster)
    if beginn < datetime.now():
        return RedirectResponse(_assistent_url(vorgang.id, "Der Termin liegt in der Vergangenheit."),
                                status_code=303)
    vorfilter = lead_termin.kandidaten(session, vorgang, benutzer=benutzer)
    erlaubt = {k["ad"].id for k in vorfilter["kandidaten"]}
    if ad_id not in erlaubt:
        grund = next((a["grund"] for a in vorfilter["ausgeschlossen"] if a["ad"].id == ad_id),
                     "nicht in der Vorauswahl")
        return RedirectResponse(_assistent_url(vorgang.id, f"Außendienstler nicht wählbar: {grund}."),
                                status_code=303)
    lead_ort = (vorgang.lat, vorgang.lon) if vorgang.lat is not None else None
    k = lead_termin.konflikte(session, ad_id, beginn, lead_ort=lead_ort,
                              ignorieren_id=int(umbuchen) if umbuchen.isdigit() else None)
    modus = lead_termin.parameter(session, "termin_konflikt_modus", "warnen")
    if k["sperren"] or (modus == "sperren" and k["puffer"]):
        return RedirectResponse(_assistent_url(
            vorgang.id, "Nicht möglich – " + "; ".join(k["texte"]),
            datum=beginn.strftime("%Y-%m-%d"), uhrzeit=beginn.strftime("%H:%M"),
            form_ad=ad_id), status_code=303)
    if k["warnen"] and form.get("bestaetigt") != "1":
        url = _assistent_url(vorgang.id, "Bitte Konflikte prüfen und bestätigen.",
                             datum=beginn.strftime("%Y-%m-%d"),
                             uhrzeit=beginn.strftime("%H:%M"), form_ad=ad_id)
        url += "".join(f"&warnung={quote_plus(t)}" for t in k["texte"])
        return RedirectResponse(url + "#manuell", status_code=303)
    termin, meldung, vorgemerkt = lead_termin.termin_anlegen(
        session, vorgang, ad_id, beginn, benutzer=benutzer, quelle="manuell",
        umbuchen_id=int(umbuchen) if umbuchen.isdigit() else None)
    if termin is None:
        session.rollback()
        return RedirectResponse(_assistent_url(vorgang.id, meldung), status_code=303)
    if k["warnen"]:
        meldung += " Hinweis: " + "; ".join(k["texte"]) + "."
    session.commit()
    return RedirectResponse(_kartei(vorgang.id, meldung), status_code=303)


@router.post("/lead/{vorgang_id}/termin/manuell")
async def termin_manuell(request: Request, vorgang_id: int,
                         session: Session = Depends(get_session)):
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    form = await request.form()
    return await _manuell(request, session, vorgang, form)


@router.get("/termin/konflikt")
async def termin_konflikt(request: Request, session: Session = Depends(get_session)):
    """Live-Konfliktprüfung des manuellen Formulars (fetch aus lm_termin.js)."""
    lead_v2.gate(request, session)
    q = request.query_params
    ad_id = q.get("ad_id", "")
    vorgang_id = q.get("vorgang_id", "")
    try:
        beginn = datetime.strptime(q.get("beginn", "")[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return JSONResponse({"texte": [], "sperren": False, "warnen": False})
    if not ad_id.isdigit():
        return JSONResponse({"texte": [], "sperren": False, "warnen": False})
    vorgang = session.get(Vorgang, int(vorgang_id)) if vorgang_id.isdigit() else None
    lead_ort = ((vorgang.lat, vorgang.lon)
                if vorgang is not None and vorgang.lat is not None else None)
    raster = lead_termin._int(lead_termin.parameter(session, "vorschlag_raster_manuell_min", "15"), 15)
    beginn = lead_termin.viertelstunde(beginn, raster)
    k = lead_termin.konflikte(session, int(ad_id), beginn, lead_ort=lead_ort)
    return JSONResponse({"texte": k["texte"], "sperren": k["sperren"],
                         "warnen": k["warnen"], "beginn": beginn.strftime("%Y-%m-%dT%H:%M")})


# --- Vorab-Gespräch (H6/F12) --------------------------------------------------------

@router.get("/lead/{vorgang_id}/termin/vorab")
async def vorab_formular(request: Request, vorgang_id: int,
                         session: Session = Depends(get_session)):
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    kunde = session.get(Kunde, vorgang.kunde_id)
    typ = request.query_params.get("typ", "telefon")
    typ = typ if typ in lead_termin.VORAB_TYPEN else "telefon"
    hv_id = lead_termin.hv_nur_eigene(session, request.state.benutzer)
    vertriebler = lead_termin.vorab_personen(session, "telefon")
    if hv_id:
        vertriebler = [b for b in vertriebler if b.id == hv_id]
    kollegen = lead_termin.vorab_personen(session, "online")
    return render(request, "leadmanagement/termin_vorab.html",
                  aktiv="/lead-management", vorgang=vorgang, kunde=kunde, typ=typ,
                  vertriebler=vertriebler, kollegen=kollegen,
                  benutzer=request.state.benutzer,
                  vorgewaehlt=vorgang.ad_id or (hv_id or ""),
                  dauer=lead_termin._int(lead_termin.parameter(session, "vorab_dauer_min", "30"), 30),
                  buchbar=not (kern.demo_aktiv(session) and not vorgang.demo),
                  typ_namen=TERMIN_TYP_NAMEN, demo_badge=kern.demo_aktiv(session),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/lead/{vorgang_id}/termin/vorab")
async def vorab_anlegen(request: Request, vorgang_id: int,
                        session: Session = Depends(get_session)):
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    form = await request.form()
    typ = form.get("typ") or "telefon"
    person = str(form.get("person_id") or "")
    beginn = _datum_uhrzeit(form)
    dauer = str(form.get("dauer") or "")
    hv_id = lead_termin.hv_nur_eigene(session, request.state.benutzer)
    if typ == "telefon" and hv_id and person != str(hv_id):
        return RedirectResponse(
            f"/lead-management/lead/{vorgang.id}/termin/vorab?typ={typ}&meldung="
            + quote_plus("Handelsvertreter tragen nur eigene Telefontermine ein."),
            status_code=303)
    termin, meldung = lead_termin.vorab_anlegen(
        session, vorgang, typ, int(person) if person.isdigit() else 0, beginn,
        dauer_min=int(dauer) if dauer.isdigit() else None,
        benutzer=request.state.benutzer,
        buchungslink_senden=form.get("buchungslink_senden") == "1")
    if termin is None:
        session.rollback()
        return RedirectResponse(
            f"/lead-management/lead/{vorgang.id}/termin/vorab?typ={typ}&meldung="
            + quote_plus(meldung), status_code=303)
    session.commit()
    return RedirectResponse(_kartei(vorgang.id, meldung), status_code=303)


# --- Absage, Ersatzkunde, Bestätigung erneut, Umbuchung (E3/E4/F8/A-9) --------------

@router.post("/termin/{termin_id}/absagen")
async def termin_absagen(request: Request, termin_id: int,
                         session: Session = Depends(get_session)):
    termin, vorgang = _termin_oder_404(request, session, termin_id)
    form = await request.form()
    grund = (form.get("grund") or "").strip()
    text = (form.get("grund_text") or "").strip()
    passend = next((g for g in _absage_gruende(session) if g.grund == grund), None)
    ziel_fehler = _zurueck(request, _kartei(vorgang.id))
    if passend is None:
        if not text:
            return RedirectResponse(_mit_meldung(
                ziel_fehler, "Bitte einen Grund wählen oder einen Freitext angeben."),
                status_code=303)
        grund = grund or "Sonstiges"
    elif passend.freitext_pflicht and not text:
        return RedirectResponse(_mit_meldung(
            ziel_fehler, f"Beim Grund „{grund}“ ist der Freitext Pflicht."), status_code=303)
    war_vot = (termin.typ or "vot") == "vot" and termin.status != lead_termin.STATUS_VORGEMERKT
    ok, meldung = lead_termin.absagen(session, termin, grund, text,
                                      benutzer=request.state.benutzer)
    if not ok:
        session.rollback()
        return RedirectResponse(_mit_meldung(ziel_fehler, meldung), status_code=303)
    session.commit()
    if war_vot:
        return RedirectResponse(f"/lead-management/termin/{termin.id}/ersatz?meldung="
                                + quote_plus(meldung + " Der Kunde erhält die Absage mit "
                                             "Storno-ICS. Ersatzkunde für den Slot wählen:"),
                                status_code=303)
    return RedirectResponse(_kartei(vorgang.id, meldung), status_code=303)


@router.get("/termin/{termin_id}/ersatz")
async def termin_ersatz(request: Request, termin_id: int,
                        session: Session = Depends(get_session)):
    termin, vorgang = _termin_oder_404(request, session, termin_id)
    kunde = session.get(Kunde, vorgang.kunde_id)
    daten = lead_termin.ersatz_kandidaten(session, termin)
    return render(request, "leadmanagement/termin_ersatz.html",
                  aktiv="/lead-management", termin=termin, vorgang=vorgang, kunde=kunde,
                  ad=session.get(Benutzer, termin.ad_id) if termin.ad_id else None,
                  kandidaten=daten["kandidaten"], radius=daten["radius"],
                  stufen=daten["stufen"], ort=daten["ort"], alter_tage=daten["alter_tage"],
                  slot=termin.beginn.strftime("%Y-%m-%dT%H:%M") if termin.beginn else "",
                  status_namen=VOT_STATUS_NAMEN_V2, demo_badge=kern.demo_aktiv(session),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/termin/{termin_id}/bestaetigung-erneut")
async def termin_bestaetigung_erneut(request: Request, termin_id: int,
                                     session: Session = Depends(get_session)):
    termin, vorgang = _termin_oder_404(request, session, termin_id)
    ok, meldung = lead_termin.bestaetigung_erneut(session, termin,
                                                  benutzer=request.state.benutzer)
    if ok:
        session.commit()
    else:
        session.rollback()
    return RedirectResponse(_mit_meldung(_zurueck(request, _kartei(vorgang.id)), meldung),
                            status_code=303)


@router.post("/termin/{termin_id}/verschieben")
async def termin_verschieben(request: Request, termin_id: int,
                             session: Session = Depends(get_session)):
    """Umbuchung aus Kalender (Drag & Drop) oder Kartei – wie V1, zusätzlich
    Konfliktsperre, Weitergabe der ICS-UID (SEQUENCE + 1) an den neuen Termin
    und Ersatzkunden-Dialog für den freigewordenen VOT-Slot (E3)."""
    termin, vorgang = _termin_oder_404(request, session, termin_id)
    form = await request.form()
    ziel = _zurueck(request, "/lead-management/kalender")
    if termin.quelle == "monday":
        return RedirectResponse(_mit_meldung(ziel, "monday-Termin – bitte in monday ändern."),
                                status_code=303)
    if termin.status not in lead_termin.BELEGT_STATUS:
        return RedirectResponse(_mit_meldung(ziel, "Termin ist nicht mehr aktiv."), status_code=303)
    beginn = _datum_uhrzeit(form)
    ad_roh = str(form.get("ad_id") or termin.ad_id or "")
    ad_id = int(ad_roh) if ad_roh.isdigit() else 0
    if beginn is None or not ad_id:
        return RedirectResponse(_mit_meldung(ziel, "Neuer Beginn ist Pflicht."), status_code=303)
    hv_id = lead_termin.hv_nur_eigene(session, request.state.benutzer)
    if hv_id and ad_id != hv_id:
        return RedirectResponse(_mit_meldung(ziel, "Handelsvertreter buchen nur den eigenen Kalender."),
                                status_code=303)
    if (termin.typ or "vot") != "vot":
        # Vorab-Gespräch: Zeit direkt ändern (kein Kundentermin mit ICS); ein
        # vorgemerkter Online-Termin (Kunde wählt über den Buchungslink) wird
        # mit der eingetragenen Zeit „geplant“ – manueller Rückweg aus Outlook (F12)
        from app import kalender as kalender_modul
        dauer_standard = lead_termin._int(lead_termin.parameter(session, "vorab_dauer_min", "30"), 30)
        dauer = ((termin.ende - termin.beginn) if termin.ende and termin.beginn
                 else timedelta(minutes=dauer_standard))
        war_vorgemerkt = termin.status == lead_termin.STATUS_VORGEMERKT
        termin.beginn, termin.ende, termin.ad_id = beginn, beginn + dauer, ad_id
        if war_vorgemerkt:
            termin.status = "geplant"
        kunde = session.get(Kunde, vorgang.kunde_id)
        person = session.get(Benutzer, ad_id)
        kalender_modul.termin_aendern(session, termin, vorgang, kunde, person)
        name = TERMIN_TYP_NAMEN.get(termin.typ, termin.typ)
        kern.aktivitaet(session, vorgang.id, "termin",
                        f"{name} {'eingetragen für' if war_vorgemerkt else 'verschoben auf'} "
                        f"{beginn:%d.%m.%Y %H:%M}", benutzer=request.state.benutzer)
        if person is not None and kunde is not None:
            kern.benachrichtigen(session, [person.id],
                                 f"{name} {beginn:%d.%m. %H:%M}: {kunde.anzeige_name}",
                                 f"/lead-management/lead/{vorgang.id}")
        session.commit()
        return RedirectResponse(_mit_meldung(
            ziel, f"{name} {'eingetragen' if war_vorgemerkt else 'verschoben'}."), status_code=303)
    lead_ort = (vorgang.lat, vorgang.lon) if vorgang.lat is not None else None
    k = lead_termin.konflikte(session, ad_id, beginn, lead_ort=lead_ort, ignorieren_id=termin.id)
    if k["sperren"]:
        return RedirectResponse(_mit_meldung(ziel, "Nicht möglich – " + "; ".join(k["texte"])),
                                status_code=303)
    # vorher geplant/bestätigt (nicht nur vorgemerkt) → der alte Slot wird frei
    war_gebucht = termin.status in lead_termin.AKTIVE_STATUS
    neu, meldung, vorgemerkt = lead_termin.termin_anlegen(
        session, vorgang, ad_id, beginn, benutzer=request.state.benutzer,
        quelle="manuell", umbuchen_id=termin.id)
    if neu is None:
        session.rollback()
        return RedirectResponse(_mit_meldung(ziel, meldung), status_code=303)
    if war_gebucht and termin.beginn and termin.beginn > datetime.now():
        lead_termin.slot_frei_melden(session, termin, benutzer=request.state.benutzer)
    session.commit()
    text = "Termin umgebucht." if not vorgemerkt else meldung
    if k["warnen"]:
        text += " Hinweis: " + "; ".join(k["texte"]) + "."
    if war_gebucht and termin.beginn and termin.beginn > datetime.now():
        # E3: der alte Slot ist frei – Ersatzkunden in der Umgebung vorschlagen
        return RedirectResponse(_mit_meldung(
            f"/lead-management/termin/{termin.id}/ersatz",
            text + " Der alte Slot ist frei – Ersatzkunde wählen:"), status_code=303)
    return RedirectResponse(_mit_meldung(ziel, text), status_code=303)


# --- Kalender (Terminarten, vorgemerkt) ---------------------------------------------

@router.get("/kalender")
async def terminkalender(request: Request, session: Session = Depends(get_session)):
    lead_v2.gate(request, session)
    benutzer = request.state.benutzer
    versatz = request.query_params.get("woche", "0")
    versatz = int(versatz) if versatz.lstrip("-").isdigit() else 0
    start = datetime.now() + timedelta(weeks=versatz)
    nur_ad = request.query_params.get("ad_id", "")
    hv_id = lead_termin.hv_nur_eigene(session, benutzer)
    alle_ad = lead_termin.ad_basis(session)
    if hv_id:
        alle_ad = [b for b in alle_ad if b.id == hv_id]
        nur_ad = str(hv_id)
    ad_ids = [int(nur_ad)] if nur_ad.isdigit() else [b.id for b in alle_ad]
    woche = lead_termin.kalender_woche(session, ad_ids,
                                       start=start - timedelta(days=start.weekday()))
    vorgang_ids = {t.vorgang_id for r in woche["je_ad"].values()
                   for liste in r["termine"].values() for t in liste}
    vorgaenge = {v.id: v for v in session.query(Vorgang)
                 .filter(Vorgang.id.in_(vorgang_ids or {0}))}
    kunden_map = {k.id: k for k in session.query(Kunde)
                  .filter(Kunde.id.in_({v.kunde_id for v in vorgaenge.values()} or {0}))}
    return render(request, "leadmanagement/kalender.html",
                  aktiv="/lead-management", woche=woche, alle_ad=alle_ad,
                  ad_ids=ad_ids, nur_ad=nur_ad, versatz=versatz,
                  vorgaenge=vorgaenge, kunden_map=kunden_map,
                  benutzer_map={b.id: b for b in session.query(Benutzer)},
                  typ_namen=TERMIN_TYP_NAMEN, status_namen=VOT_STATUS_NAMEN_V2,
                  absage_gruende=_absage_gruende(session), hv_id=hv_id,
                  demo_badge=kern.demo_aktiv(session),
                  meldung=request.query_params.get("meldung", ""))
