# Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 108) – Router Termin. Eigener
# Router mit demselben Präfix, in app/main.py VOR dem V1-Router eingebunden:
# GET/POST /lead/{id}/termin (Assistent V2, übernimmt die V1-Pfade),
# POST …/termin/manuell (15-Min-Raster, Konfliktwarnung), GET/POST …/termin/vorab
# (Telefon/Teams, A-2), POST /termin/{tid}/absagen (+ Ersatzkunde-Dialog
# GET /termin/{tid}/ersatz), POST /termin/{tid}/bestaetigung-erneut (A-9),
# POST /termin/{tid}/verschieben (ICS-UID wird weitergetragen), GET /kalender
# (Terminarten farblich, vorgemerkt gestrichelt), GET /termin/konflikt (JSON).
# v25 (PLAN_LEAD_V3 Phase 119/120): GET /lead/{id}/termin/vorschlaege.json
# (Top 5 für den Block Termine der Kartei, Cache 10 Minuten, Zustände
# ok|adresse_fehlt|hv_lead|keine), Handelsvertreter sind für den Innendienst
# keine Kandidaten (manuelle Buchung bleibt möglich), kein Score/Klasse.
# Alle Routen laufen über lead_v2.gate (Handelsvertreter: nur eigene Leads,
# nur eigener Kalender).
# v29 (PLAN_LEAD_V4 Phase 143): drei Vorschläge (vorschlaege_anzahl), Vorschlag 1
# „Ideal“; Kalenderansicht nachgelagert per fetch GET /lead/{id}/termin/kalender.json
# (?woche=YYYY-MM-DD, ?neu=1); „Weitere Kalender“ POST /lead/{id}/termin/kalender/
# auswahl (JSON {ids}); manuelle Buchung auf einen Kalender außerhalb der
# Vorauswahl mit Warnhinweis (bestaetigt=1); Sperrzeiten der HV als belegte Slots.
# v31 (PLAN_LEAD_V5 Phase 153/158/159):
#  - Termine je Objekt: alle Assistenten-Routen nehmen ?objekt_id= (Vorschläge,
#    Kalender, Buchen, manuell); bei mehr als einem Objekt fragt die Seite das Objekt
#    ab. Neu POST /lead/{id}/termin/vormerken (objekt_id, ad_id, beginn – JSON oder
#    Formular) und POST /lead/{id}/terminierung (Vertrag mit K, Alias
#    /lead/{id}/termin/terminierung; bestaetigung=eine|je_objekt|auto) – bucht alle
#    vorgemerkten Objekttermine in einem Schritt über das _speichern-Muster (Rollback +
#    eine Wiederholung bei „database is locked“, Vorbild routers/angebote._speichern).
#    Hinweis Integration: lm_kartei.py (K) trägt denselben Pfad /lead/{id}/terminierung
#    und ist in main.py vor diesem Router eingebunden – K ruft dort
#    lead_termin.terminierung_ausfuehren auf oder entfernt die Route (Bericht T).
#  - ?ohne_ad_id= (Umbuchung ohne den kranken Vertriebler, B: „Fällig heute“).
#  - Testphase (terminierung_aktiv = aus): Vormerken, Buchen, manuell, Umbuchen,
#    Absagen, Terminierung, Vorab-Gespräche → 403 JSON {"ok": false, "meldung":
#    TESTPHASE_HINWEIS} bei Accept: application/json, sonst Redirect mit Meldung;
#    Knöpfe sichtbar/ausgegraut (Kontext testphase_kontext).
#  - Manuelle Buchung an einem Samstag bleibt mit Warnhinweis möglich [ANNAHME].
#  - Bestätigung erneut: bei mehreren Objekten Auswahl der Termine (termin_ids) und
#    „zusammen“ (eine Mail mit Objektliste).

import time
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import lead_termin, lead_v2, lead_v5
from app import leadmanagement as kern
from app import objekte as objekte_modul
from app.db import get_session
from app.models import (Benutzer, Kunde, Vorgang, VotTermin, TERMIN_TYP_NAMEN,
                        VOT_STATUS_NAMEN)
from app.templating import render
from app import anfrage   # v27: Formular/JSON in def-Routen

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


def _json_gewuenscht(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "")


def _gesperrt_antwort(request: Request, ziel: str, meldung: str | None = None):
    """v31 (Phase 159): Antwort der Testphase – 403 JSON {"ok": false, "meldung": …}
    bei Accept: application/json, sonst 303 mit Meldung."""
    meldung = meldung or lead_v5.TESTPHASE_HINWEIS
    if _json_gewuenscht(request):
        return JSONResponse({"ok": False, "meldung": meldung, "testphase": True}, status_code=403)
    return RedirectResponse(_mit_meldung(ziel, meldung), status_code=303)


def _speichern(session: Session, aktion, wiederholungen: int = 1) -> None:
    """v31 (v27-Regel): Aktion ausführen und committen; bei „database is locked“
    zurückrollen, kurz warten und einmal wiederholen (Vorbild routers/angebote.
    _speichern) – für die Terminierung mehrerer Objekttermine in einem Schritt."""
    from app import betrieb
    for versuch in range(wiederholungen + 1):
        start = time.perf_counter()
        try:
            aktion()
            session.commit()
            betrieb.schreibsperre_messen(int((time.perf_counter() - start) * 1000))
            return
        except OperationalError as problem:
            session.rollback()
            gesperrt = "locked" in str(problem).lower()
            betrieb.schreibsperre_messen(int((time.perf_counter() - start) * 1000), locked=gesperrt)
            if not gesperrt or versuch >= wiederholungen:
                raise
            time.sleep(0.7)


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


def _int_oder_none(wert) -> int | None:
    text = str(wert or "").strip()
    return int(text) if text.isdigit() else None


def _objekt_param(request: Request, form=None) -> int | None:
    """objekt_id aus Formular oder Query."""
    if form is not None and str(form.get("objekt_id") or "").strip():
        return _int_oder_none(form.get("objekt_id"))
    return _int_oder_none(request.query_params.get("objekt_id", ""))


def _objekt_waehlen(session: Session, vorgang: Vorgang, objekt_id: int | None):
    """(objekt, objekte, mehrere) – bei mehreren Objekten ohne Angabe kein Objekt
    (die Seite/Route fragt es ab)."""
    objekte = objekte_modul.objekte_fuer(session, vorgang.id)
    mehrere = len(objekte) > 1
    objekt = lead_termin.objekt_holen(session, vorgang, objekt_id, anlegen=True) if (objekt_id or not mehrere) else None
    if objekt is not None and objekt_id and objekt.id != objekt_id:
        objekt = None   # fremdes/inaktives Objekt
    return objekt, objekte, mehrere


def _geokodieren_bei_bedarf(session: Session, vorgang: Vorgang, objekt=None) -> None:
    """Adresse bei Bedarf synchron geokodieren (Cache). v27 (Phase 128): nach
    einem Fehlschlag greift der Backoff in geocoding.geokodieren (1 h / 6 h /
    24 h – in der Pause nur eine Cache-Abfrage), deshalb wird „fehler“ nicht
    mehr dauerhaft übersprungen. v31 (Phase 153): weitere Objekte werden über ihre
    eigene Adresse geokodiert (Felder lat/lon/geocode_status am Objekt); das
    Hauptobjekt teilt die Koordinaten des Vorgangs."""
    from app import geocoding
    if objekt is not None and objekt.reihenfolge != 1:
        if objekt.lat is None and objekt.geocode_status != "manuell":
            adresse = objekte_modul.objekt_text(objekt, mit_bezeichnung=False)
            if adresse:
                lat, lon, status = geocoding.geokodieren(session, adresse)
                objekt.lat, objekt.lon, objekt.geocode_status = lat, lon, status
                session.commit()
        return
    if vorgang.lat is None and vorgang.geocode_status != "manuell":
        adresse = geocoding.lead_adresse(session, vorgang)
        if adresse:
            lat, lon, status = geocoding.geokodieren(session, adresse)
            vorgang.lat, vorgang.lon, vorgang.geocode_status = lat, lon, status
            if objekt is not None and objekt.reihenfolge == 1:
                objekt.lat, objekt.lon, objekt.geocode_status = lat, lon, status
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


# --- v25: Terminvorschläge für den Block Termine der Kartei (Vertrag C/D) ----------

@router.get("/lead/{vorgang_id}/termin/vorschlaege.json")
def termin_vorschlaege_json(request: Request, vorgang_id: int,
                                  session: Session = Depends(get_session)):
    """Vorschläge des Assistenten als JSON (asynchron nach dem Seitenaufbau der
    Kartei): {status: ok|adresse_fehlt|hv_lead|keine, hinweis, anzahl, vorschlaege:
    [{ad_id, ad_name, beginn, beginn_text, begruendung, umweg_min, ideal,
    ideal_grund}]} – v29: genau vorschlaege_anzahl (Standard 3), der erste
    „Ideal“; Cache 10 Minuten je Lead (lead_termin.vorschlaege_cache), ?neu=1
    erzwingt die Neuberechnung. Buchen: POST /lead/{id}/termin (ad_id, beginn,
    quelle=assistent). v31: ?objekt_id= (Vorschläge je Objekt, Felder objekt_id/
    objekte/mehrere_objekte), ?ohne_ad_id=, buchbar = terminierung_aktiv,
    testphase_hinweis, vormerken_url."""
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    if request.query_params.get("neu") == "1":
        lead_termin.vorschlaege_cache_leeren(vorgang.id)
    objekt_id = _objekt_param(request)
    ohne_ad_id = _int_oder_none(request.query_params.get("ohne_ad_id", ""))
    kunde = session.get(Kunde, vorgang.kunde_id)
    objekt = lead_termin.objekt_holen(session, vorgang, objekt_id)
    if kunde is not None and not lead_termin.adresse_fehlt(kunde, objekt):
        _geokodieren_bei_bedarf(session, vorgang, objekt)
    antwort = lead_termin.vorschlaege_json(session, vorgang, benutzer=request.state.benutzer,
                                           objekt_id=objekt.id if objekt is not None else None,
                                           ohne_ad_id=ohne_ad_id)
    session.commit()   # Routing-/Geocode-Cache behalten
    antwort["vorgang_id"] = vorgang.id
    antwort["buchen_url"] = f"/lead-management/lead/{vorgang.id}/termin"
    antwort["vormerken_url"] = f"/lead-management/lead/{vorgang.id}/termin/vormerken"
    antwort["terminierung_url"] = f"/lead-management/lead/{vorgang.id}/termin/terminierung"
    antwort["assistent_url"] = f"/lead-management/lead/{vorgang.id}/termin"
    antwort["objekte_hinweis"] = lead_termin.objekte_hinweis(session, vorgang)
    return JSONResponse(antwort)


# --- v29 (Phase 143): Kalenderansicht + „Weitere Kalender“ ----------------------------

@router.get("/lead/{vorgang_id}/termin/kalender.json")
def termin_kalender_json(request: Request, vorgang_id: int,
                         session: Session = Depends(get_session)):
    """Wochenansicht des Assistenten (v31: Mo–Fr, 15-Minuten-Raster, Spalte je
    Kandidat + gewählte weitere Kalender): ?woche=YYYY-MM-DD (Standard = Woche
    des ersten Vorschlags), ?neu=1 erzwingt die Neuberechnung, ?objekt_id=,
    ?ohne_ad_id=. Outlook-Belegt nur bei kalender_sync = an und nie für
    Handelsvertreter – ohne offene Sitzung (lead_termin.kalender_json gibt die
    Verbindung vor dem Abruf frei)."""
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    q = request.query_params
    antwort = lead_termin.kalender_json(session, vorgang, benutzer=request.state.benutzer,
                                        woche=q.get("woche", ""), neu=q.get("neu") == "1",
                                        objekt_id=_objekt_param(request),
                                        ohne_ad_id=_int_oder_none(q.get("ohne_ad_id", "")))
    session.commit()   # Routing-/Geocode-Cache der Vorschläge behalten
    antwort["buchen_url"] = f"/lead-management/lead/{vorgang.id}/termin"
    return JSONResponse(antwort)


@router.post("/lead/{vorgang_id}/termin/kalender/auswahl")
def termin_kalender_auswahl(request: Request, vorgang_id: int,
                            session: Session = Depends(get_session)):
    """„Weitere Kalender“: JSON {ids: [benutzer_id, …]} → je Nutzer gemerkt
    (benutzer_einstellungen Key assistent_kalender); Antwort {ok, ids}."""
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    benutzer = request.state.benutzer
    if lead_termin.hv_nur_eigene(session, benutzer):
        return JSONResponse({"ok": False, "ids": [],
                             "meldung": "Handelsvertreter sehen nur den eigenen Kalender."},
                            status_code=403)
    try:
        daten = anfrage.json_lesen(request)
    except Exception:
        form = anfrage.formular(request)
        daten = {"ids": form.getlist("ids")}
    ids = daten.get("ids") if isinstance(daten, dict) else None
    if not isinstance(ids, list):
        ids = []
    gespeichert = lead_termin.weitere_kalender_setzen(session, benutzer, ids)
    session.commit()
    lead_termin.kalender_cache.pop(vorgang.id, None)
    return JSONResponse({"ok": True, "ids": gespeichert})


# --- Assistent (B6/E1/E2) -----------------------------------------------------------

@router.get("/lead/{vorgang_id}/termin")
def termin_assistent(request: Request, vorgang_id: int,
                           session: Session = Depends(get_session)):
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    benutzer = request.state.benutzer
    kunde = session.get(Kunde, vorgang.kunde_id)
    q = request.query_params
    # v31 (Phase 153): Objekt wählen – bei mehreren Objekten zeigt die Seite die Auswahl
    # (Vorschläge für das gewählte, Standard = Hauptobjekt)
    objekt_id = _objekt_param(request)
    objekte = objekte_modul.objekte_fuer(session, vorgang.id)
    mehrere = len(objekte) > 1
    objekt = lead_termin.objekt_holen(session, vorgang, objekt_id)
    _geokodieren_bei_bedarf(session, vorgang, objekt)
    nur_ad = q.get("ad_id", "")
    nur_ad_id = int(nur_ad) if nur_ad.isdigit() else None
    ohne_ad_id = _int_oder_none(q.get("ohne_ad_id", ""))   # v31 (Phase 158): ohne den Kranken
    hv_id = lead_termin.hv_nur_eigene(session, benutzer)
    # v35 (PLAN_LEAD_V6 Phase 185): Handelsvertreter rechnen mit den Kalendern der Gruppe –
    # ein ?ad_id= außerhalb der Gruppe wird verworfen (kandidaten filtert die Gruppe selbst)
    hv_gruppe = lead_termin.hv_gruppe_ids(session, benutzer)
    if hv_gruppe is not None:
        nur_ad_id = nur_ad_id if nur_ad_id in hv_gruppe else (hv_id if len(hv_gruppe) == 1 else None)
    ergebnis = lead_termin.vorschlaege(session, vorgang, nur_ad_id=nur_ad_id,
                                       benutzer=benutzer, objekt=objekt, ohne_ad_id=ohne_ad_id)
    session.commit()   # Routing-/Geocode-Cache behalten
    kandidaten = ergebnis["kandidaten"]
    kalender_ad = (nur_ad_id if nur_ad_id else (kandidaten[0].id if kandidaten else None))
    if kalender_ad and kalender_ad not in [k.id for k in kandidaten] and not hv_id:
        kalender_ad = kandidaten[0].id if kandidaten else kalender_ad
    # v29 (Phase 143): die Wochenansicht lädt nachgelagert per fetch (kalender.json);
    # „Weitere Kalender“ = aktive Vertriebler außerhalb des Kandidatenkreises
    weitere_wahl = lead_termin.weitere_kalender_wahl(session, [k.id for k in kandidaten], benutzer)
    weitere_aktiv = [w for w in weitere_wahl if w["gewaehlt"]]
    testphase = lead_termin.testphase_kontext(session)
    buchbar = testphase["terminierung_aktiv"]   # v31 (Phase 159): statt Demo-Sperre
    pflicht_offen = lead_v2.pflichtfelder_offen(session, kunde, vorgang) if kunde else []
    pflicht_offen = [f for f in pflicht_offen if str(f).lower() not in ("ad_id", "außendienst", "aussendienst")]
    umbuchen_id = q.get("umbuchen", "")
    umbuchen = session.get(VotTermin, int(umbuchen_id)) if umbuchen_id.isdigit() else None
    if umbuchen is not None and umbuchen.objekt_id and objekt_id is None:
        objekt = lead_termin.objekt_holen(session, vorgang, umbuchen.objekt_id)
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
    objekt_zeilen = lead_termin.objekt_termine(session, vorgang)
    vorgemerkte = lead_termin.vorgemerkte_objekttermine(session, vorgang)
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    phase_zeile = logik.status_zeile(vorgang.lead_phase or "neu")
    ohne_ad = session.get(Benutzer, ohne_ad_id) if ohne_ad_id else None
    return render(request, "leadmanagement/termin.html",
                  aktiv="/lead-management", vorgang=vorgang, kunde=kunde,
                  vorschlaege=ergebnis["vorschlaege"], hinweise=ergebnis["hinweise"],
                  kandidaten=kandidaten, kandidaten_info=ergebnis["kandidaten_info"],
                  ausgeschlossen=ergebnis["ausgeschlossen"],
                  # v25 (Phase 120): kein Score/Klasse (score_aktiv), HV-Hinweis für
                  # den Innendienst, HV nur manuell buchbar, Phasen-Label aus dem Blatt Status
                  score_aktiv=lead_v2.score_aktiv(session),
                  hv_lead=ergebnis["hv_lead"], hv_hinweis=ergebnis["hv_hinweis"],
                  hv_manuell=ergebnis["hv_manuell"] if not hv_id else [],
                  phase_label=(phase_zeile.label if phase_zeile else (vorgang.lead_phase or "")),
                  sparten=ergebnis["sparten"], kanal=ergebnis["kanal"],
                  kalender_ad=kalender_ad,
                  anzahl=ergebnis.get("anzahl", len(ergebnis["vorschlaege"])),
                  weitere_wahl=weitere_wahl, weitere_aktiv=weitere_aktiv,
                  kalender_url=f"/lead-management/lead/{vorgang.id}/termin/kalender.json",
                  auswahl_url=f"/lead-management/lead/{vorgang.id}/termin/kalender/auswahl",
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
                  # v31 (Phase 153/158/159)
                  objekt=objekt, objekte=objekte, mehrere_objekte=mehrere,
                  objekt_zeilen=objekt_zeilen, vorgemerkte=vorgemerkte,
                  objekte_hinweis=lead_termin.objekte_hinweis(session, vorgang),
                  bestaetigung_vorbelegung=lead_termin.bestaetigung_vorbelegung(vorgemerkte),
                  objekt_text=objekte_modul.objekt_text,
                  ohne_ad=ohne_ad, ohne_ad_id=ohne_ad_id or "",
                  samstag_warnung=lead_termin.SAMSTAG_WARNUNG,
                  meldung=q.get("meldung", ""), **testphase)


@router.post("/lead/{vorgang_id}/termin")
def termin_buchen(request: Request, vorgang_id: int,
                        session: Session = Depends(get_session)):
    """Buchen/Umbuchen aus den Vorschlägen (V1-kompatibel: beginn, ad_id,
    umweg, umbuchen_id; quelle=manuell läuft über die Konfliktprüfung). v31:
    objekt_id (Pflicht bei mehreren Objekten), Testphase → 403/Redirect."""
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    form = anfrage.formular(request)
    if not lead_v5.terminierung_aktiv(session):
        return _gesperrt_antwort(request, _assistent_url(vorgang.id))
    if (form.get("quelle") or "") == "manuell":
        return _manuell(request, session, vorgang, form)
    benutzer = request.state.benutzer
    beginn = _datum_uhrzeit(form)
    ad_id = int(form.get("ad_id") or 0) if str(form.get("ad_id") or "").isdigit() else 0
    if beginn is None or not ad_id:
        return RedirectResponse(_assistent_url(vorgang.id, "Beginn und Außendienstler sind Pflicht."),
                                status_code=303)
    # v35 (Phase 185): Handelsvertreter buchen die Kalender der eigenen Gruppe
    if not lead_termin.hv_ad_erlaubt(session, benutzer, ad_id):
        return RedirectResponse(_assistent_url(vorgang.id, lead_termin.HV_GRUPPE_KALENDER_TEXT),
                                status_code=303)
    umbuchen = form.get("umbuchen_id") or ""
    umweg = str(form.get("umweg") or "")
    objekt_id = _objekt_param(request, form)
    objekt, objekte, mehrere = _objekt_waehlen(session, vorgang, objekt_id)
    if mehrere and objekt is None and not umbuchen.isdigit():
        return RedirectResponse(_assistent_url(vorgang.id, "Bitte das Objekt für den Termin wählen."),
                                status_code=303)
    termin, meldung, vorgemerkt = lead_termin.termin_anlegen(
        session, vorgang, ad_id, beginn, benutzer=benutzer,
        quelle=form.get("quelle") or "assistent",
        umweg=int(umweg) if umweg.lstrip("-").isdigit() else None,
        umbuchen_id=int(umbuchen) if umbuchen.isdigit() else None,
        objekt_id=objekt.id if objekt is not None else None)
    if termin is None:
        session.rollback()
        return RedirectResponse(_assistent_url(vorgang.id, meldung), status_code=303)
    session.commit()
    if _json_gewuenscht(request):
        return JSONResponse({"ok": True, "meldung": meldung, "termin_id": termin.id,
                             "vorgemerkt": vorgemerkt, "objekt_id": termin.objekt_id})
    return RedirectResponse(_kartei(vorgang.id, meldung), status_code=303)


def _manuell(request: Request, session: Session, vorgang: Vorgang, form):
    """B7: Datum + Uhrzeit im 15-Minuten-Raster, AD aus den vorgefilterten
    Kandidaten, Konfliktwarnung (bestaetigt=1 übergeht Warnungen), Sperre bei
    voller Überlappung desselben AD. v31: Objekt (objekt_id), Samstag mit
    Warnhinweis [ANNAHME], Testphase gesperrt."""
    benutzer = request.state.benutzer
    if not lead_v5.terminierung_aktiv(session):
        return _gesperrt_antwort(request, _assistent_url(vorgang.id))
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
        if not lead_termin.hv_ad_erlaubt(session, benutzer, ad_id):   # v35: Gruppe
            return RedirectResponse(_kartei(vorgang.id, lead_termin.HV_GRUPPE_KALENDER_TEXT),
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
    objekt_id = _objekt_param(request, form)
    objekt, objekte, mehrere = _objekt_waehlen(session, vorgang, objekt_id)
    if mehrere and objekt is None and not umbuchen.isdigit():
        return RedirectResponse(_assistent_url(vorgang.id, "Bitte das Objekt für den Termin wählen.",
                                               datum=beginn.strftime("%Y-%m-%d"),
                                               uhrzeit=beginn.strftime("%H:%M"), form_ad=ad_id) + "#manuell",
                                status_code=303)
    raster = lead_termin._int(lead_termin.parameter(session, "vorschlag_raster_manuell_min", "15"), 15)
    beginn = lead_termin.viertelstunde(beginn, raster)
    if beginn < datetime.now():
        return RedirectResponse(_assistent_url(vorgang.id, "Der Termin liegt in der Vergangenheit."),
                                status_code=303)
    vorfilter = lead_termin.kandidaten(session, vorgang, benutzer=benutzer, objekt=objekt)
    erlaubt = {k["ad"].id for k in vorfilter["kandidaten"]}
    # v25 [ANNAHME]: manuelle Buchung durch den Innendienst auf einen
    # Handelsvertreter bleibt möglich – nur die Vorschläge schließen HV aus
    erlaubt |= {a.id for a in vorfilter["hv_manuell"]}
    # v29 (Phase 143): Kalender „außerhalb der Vorauswahl“ (Weitere Kalender des
    # Nutzers) sind buchbar – mit Warnhinweis (Kompetenz/Kanal/HV) und Bestätigung
    ausserhalb_warnung = ""
    if ad_id not in {k["ad"].id for k in vorfilter["kandidaten"]} \
            and not lead_termin.hv_nur_eigene(session, benutzer) \
            and ad_id in lead_termin.weitere_kalender_holen(session, benutzer):
        ausserhalb_warnung = ("Außerhalb der Vorauswahl: "
                              + lead_termin.ausschluss_grund(vorfilter, ad_id))
        erlaubt.add(ad_id)
    if ad_id not in erlaubt:
        grund = next((a["grund"] for a in vorfilter["ausgeschlossen"] if a["ad"].id == ad_id),
                     "nicht in der Vorauswahl")
        return RedirectResponse(_assistent_url(vorgang.id, f"Außendienstler nicht wählbar: {grund}."),
                                status_code=303)
    lead_ort = lead_termin.objekt_ort(session, vorgang, objekt)
    k = lead_termin.konflikte(session, ad_id, beginn, lead_ort=lead_ort,
                              ignorieren_id=int(umbuchen) if umbuchen.isdigit() else None)
    if ausserhalb_warnung:
        k["texte"] = [ausserhalb_warnung] + list(k["texte"])
        k["warnen"] = True
    # v31 (Phase 158): Samstag – der Assistent plant Mo–Fr, manuell nur mit Warnhinweis
    if beginn.weekday() >= lead_termin.WERKTAGE_MAX:
        k["texte"] = [lead_termin.SAMSTAG_WARNUNG if beginn.weekday() == 5
                      else "Sonntag: außerhalb der Arbeitstage"] + list(k["texte"])
        k["warnen"] = True
    modus = lead_termin.parameter(session, "termin_konflikt_modus", "warnen")
    if k["sperren"] or (modus == "sperren" and k["puffer"]):
        return RedirectResponse(_assistent_url(
            vorgang.id, "Nicht möglich – " + "; ".join(k["texte"]),
            datum=beginn.strftime("%Y-%m-%d"), uhrzeit=beginn.strftime("%H:%M"),
            form_ad=ad_id, objekt_id=objekt.id if objekt is not None else ""), status_code=303)
    if k["warnen"] and form.get("bestaetigt") != "1":
        url = _assistent_url(vorgang.id, "Bitte Konflikte prüfen und bestätigen.",
                             datum=beginn.strftime("%Y-%m-%d"),
                             uhrzeit=beginn.strftime("%H:%M"), form_ad=ad_id,
                             objekt_id=objekt.id if objekt is not None else "")
        url += "".join(f"&warnung={quote_plus(t)}" for t in k["texte"])
        return RedirectResponse(url + "#manuell", status_code=303)
    termin, meldung, vorgemerkt = lead_termin.termin_anlegen(
        session, vorgang, ad_id, beginn, benutzer=benutzer, quelle="manuell",
        umbuchen_id=int(umbuchen) if umbuchen.isdigit() else None,
        objekt_id=objekt.id if objekt is not None else None)
    if termin is None:
        session.rollback()
        return RedirectResponse(_assistent_url(vorgang.id, meldung), status_code=303)
    if k["warnen"]:
        meldung += " Hinweis: " + "; ".join(k["texte"]) + "."
    session.commit()
    return RedirectResponse(_kartei(vorgang.id, meldung), status_code=303)


@router.post("/lead/{vorgang_id}/termin/manuell")
def termin_manuell(request: Request, vorgang_id: int,
                         session: Session = Depends(get_session)):
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    form = anfrage.formular(request)
    return _manuell(request, session, vorgang, form)


# --- v31 (Phase 153): Vormerken je Objekt, Terminierung aller Objekttermine -------------

@router.post("/lead/{vorgang_id}/termin/vormerken")
def termin_vormerken(request: Request, vorgang_id: int,
                     session: Session = Depends(get_session)):
    """Vertrag mit K: Termin für EIN Objekt vormerken – JSON oder Formular mit
    objekt_id, ad_id, beginn (YYYY-MM-DDTHH:MM) bzw. vorschlag = „<beginn>|<ad_id>“,
    umweg. Antwort JSON {ok, meldung, termin_id, objekt_id, offen, gesamt,
    objekte_hinweis} bei Accept: application/json, sonst Redirect in die Kartei.
    Testphase → 403 / Meldung."""
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    try:
        daten = anfrage.json_lesen(request)
        if not isinstance(daten, dict):
            daten = {}
    except Exception:
        daten = dict(anfrage.formular(request))
    if not lead_v5.terminierung_aktiv(session):
        return _gesperrt_antwort(request, _kartei(vorgang.id))
    vorschlag = str(daten.get("vorschlag") or "")
    if "|" in vorschlag:
        beginn_text, ad_text = vorschlag.split("|", 1)
        daten.setdefault("beginn", beginn_text)
        daten.setdefault("ad_id", ad_text)
    beginn = _datum_uhrzeit(daten)
    ad_id = _int_oder_none(daten.get("ad_id")) or 0
    umweg = _int_oder_none(str(daten.get("umweg") or "").lstrip("-"))
    objekt_id = _int_oder_none(daten.get("objekt_id"))
    benutzer = request.state.benutzer
    if beginn is None or not ad_id:
        meldung = "Beginn und Außendienstler sind Pflicht."
        if _json_gewuenscht(request):
            return JSONResponse({"ok": False, "meldung": meldung}, status_code=400)
        return RedirectResponse(_kartei(vorgang.id, meldung), status_code=303)
    if not lead_termin.hv_ad_erlaubt(session, benutzer, ad_id):   # v35: Gruppe
        meldung = lead_termin.HV_GRUPPE_KALENDER_TEXT
        if _json_gewuenscht(request):
            return JSONResponse({"ok": False, "meldung": meldung}, status_code=403)
        return RedirectResponse(_kartei(vorgang.id, meldung), status_code=303)
    objekt, objekte, mehrere = _objekt_waehlen(session, vorgang, objekt_id)
    if mehrere and objekt is None:
        meldung = "Bitte das Objekt für den Termin wählen."
        if _json_gewuenscht(request):
            return JSONResponse({"ok": False, "meldung": meldung,
                                 "objekte": [{"id": o.id, "bezeichnung": o.bezeichnung,
                                              "adresse": objekte_modul.objekt_text(o, False)} for o in objekte]},
                                status_code=400)
        return RedirectResponse(_kartei(vorgang.id, meldung), status_code=303)
    termin, meldung = lead_termin.vormerken(session, vorgang, ad_id, beginn,
                                            objekt_id=objekt.id if objekt is not None else None,
                                            benutzer=benutzer, quelle=str(daten.get("quelle") or "assistent"),
                                            umweg=umweg)
    if termin is None:
        session.rollback()
        if _json_gewuenscht(request):
            return JSONResponse({"ok": False, "meldung": meldung}, status_code=400)
        return RedirectResponse(_kartei(vorgang.id, meldung), status_code=303)
    session.commit()
    if _json_gewuenscht(request):
        zeilen = lead_termin.objekt_termine(session, vorgang)
        return JSONResponse({"ok": True, "meldung": meldung, "termin_id": termin.id,
                             "objekt_id": termin.objekt_id,
                             "offen": len([z for z in zeilen if z["termin"] is None]),
                             "gesamt": len(zeilen),
                             "objekte_hinweis": lead_termin.objekte_hinweis(session, vorgang),
                             "bestaetigung_vorbelegung": lead_termin.bestaetigung_vorbelegung(
                                 lead_termin.vorgemerkte_objekttermine(session, vorgang))})
    return RedirectResponse(_kartei(vorgang.id, meldung), status_code=303)


@router.post("/lead/{vorgang_id}/terminierung")
@router.post("/lead/{vorgang_id}/termin/terminierung")
def terminierung(request: Request, vorgang_id: int,
                 session: Session = Depends(get_session)):
    """Button „Terminierung“ (B8, Vertrag mit K): bucht alle vorgemerkten Objekt-
    termine in einem Schritt (lead_termin.terminierung_ausfuehren) – Formular/JSON
    `bestaetigung` = eine | je_objekt | auto (Vorbelegung: gleicher Tag → eine,
    sonst je Objekt). _speichern-Muster (v27-Regel: Rollback + eine Wiederholung
    bei „database is locked“). Antwort: JSON {ok, meldung} bei Accept
    application/json, sonst Redirect in die Kartei (?tab=termin). Testphase → 403."""
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    try:
        daten = anfrage.json_lesen(request)
        if not isinstance(daten, dict):
            daten = {}
    except Exception:
        daten = dict(anfrage.formular(request))
    ziel = _kartei(vorgang.id) + "?tab=termin"
    # v35 (PLAN_LEAD_V6 Phase 183, Agent T): TAIFUN-Übergabe VOR der Testphase-Sperre – Pflichtfelder
    # und vorgemerkter Termin geprüft, Kanal nicht „?“; in der Testphase schreibt der Klick nur die
    # Datei (keine Buchung, keine Mail), mit taifun_export_aktiv = aus bleibt alles wie in v31
    # (Aktivität „TAIFUN-Übergabe nicht aktiv“). Datei-I/O und Commits liegen in taifun_export.
    from app import taifun_export
    taifun = taifun_export.terminierung_export(session, vorgang, request.state.benutzer)
    if not lead_v5.terminierung_aktiv(session):
        if taifun.get("exportiert"):
            meldung = f"{taifun_export.TESTPHASE_EXPORT_HINWEIS} – {taifun.get('meldung', '')}".strip(" –")
            if _json_gewuenscht(request):
                return JSONResponse({"ok": bool(taifun.get("ok")), "meldung": meldung, "testphase": True,
                                     "taifun": {"ok": bool(taifun.get("ok")),
                                                "datei": getattr(taifun.get("uebergabe"), "datei", "")}},
                                    status_code=200 if taifun.get("ok") else 422)
            return RedirectResponse(_mit_meldung(_kartei(vorgang.id), meldung), status_code=303)
        if taifun.get("uebersprungen") in ("pflicht", "rueckfrage", "kunde"):
            return _gesperrt_antwort(request, _kartei(vorgang.id),
                                     f"{lead_v5.TESTPHASE_HINWEIS} – {taifun.get('meldung', '')}")
        return _gesperrt_antwort(request, _kartei(vorgang.id))
    bestaetigung = str(daten.get("bestaetigung") or "auto").strip().lower()
    ergebnis: dict = {}

    def _aktion():
        ok, meldung = lead_termin.terminierung_ausfuehren(session, vorgang, benutzer=request.state.benutzer,
                                                          bestaetigung=bestaetigung)
        ergebnis["ok"], ergebnis["meldung"] = ok, meldung
        if not ok:
            raise _Abbruch()
    try:
        _speichern(session, _aktion)
    except _Abbruch:
        session.rollback()
    ok, meldung = ergebnis.get("ok", False), ergebnis.get("meldung", "Terminierung nicht möglich.")
    # v35 (Phase 183, Agent T): Ergebnis der TAIFUN-Übergabe mit in die Meldung (Export und Buchung
    # sind unabhängig – ein Export-Fehler blockiert die Terminierung nicht [ANNAHME])
    if taifun.get("exportiert") or taifun.get("uebersprungen") == "rueckfrage":
        meldung = f"{meldung} · {taifun.get('meldung', '')}".strip(" ·")
    if _json_gewuenscht(request):
        return JSONResponse({"ok": ok, "meldung": meldung,
                             "objekte_hinweis": lead_termin.objekte_hinweis(session, vorgang),
                             "taifun": {"exportiert": bool(taifun.get("exportiert")),
                                        "ok": bool(taifun.get("ok")),
                                        "datei": getattr(taifun.get("uebergabe"), "datei", "")}},
                            status_code=200 if ok else 422)
    return RedirectResponse(_mit_meldung(ziel, meldung), status_code=303)


class _Abbruch(Exception):
    """Fachlicher Abbruch der Terminierung (kein Commit, kein Wiederholversuch)."""


@router.get("/termin/konflikt")
def termin_konflikt(request: Request, session: Session = Depends(get_session)):
    """Live-Konfliktprüfung des manuellen Formulars (fetch aus lm_termin.js).
    v31: ?objekt_id= (Fahrzeit vom Objekt), Samstag-Hinweis."""
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
    lead_ort = None
    if vorgang is not None:
        objekt = lead_termin.objekt_holen(session, vorgang, _objekt_param(request), anlegen=False)
        lead_ort = lead_termin.objekt_ort(session, vorgang, objekt)
    raster = lead_termin._int(lead_termin.parameter(session, "vorschlag_raster_manuell_min", "15"), 15)
    beginn = lead_termin.viertelstunde(beginn, raster)
    k = lead_termin.konflikte(session, int(ad_id), beginn, lead_ort=lead_ort)
    texte = list(k["texte"])
    warnen = bool(k["warnen"])
    if beginn.weekday() >= lead_termin.WERKTAGE_MAX:
        texte.insert(0, lead_termin.SAMSTAG_WARNUNG if beginn.weekday() == 5 else "Sonntag: außerhalb der Arbeitstage")
        warnen = True
    return JSONResponse({"texte": texte, "sperren": k["sperren"],
                         "warnen": warnen, "beginn": beginn.strftime("%Y-%m-%dT%H:%M")})


# --- Vorab-Gespräch (H6/F12) --------------------------------------------------------

@router.get("/lead/{vorgang_id}/termin/vorab")
def vorab_formular(request: Request, vorgang_id: int,
                         session: Session = Depends(get_session)):
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    kunde = session.get(Kunde, vorgang.kunde_id)
    typ = request.query_params.get("typ", "telefon")
    typ = typ if typ in lead_termin.VORAB_TYPEN else "telefon"
    hv_id = lead_termin.hv_nur_eigene(session, request.state.benutzer)
    vertriebler = lead_termin.vorab_personen(session, "telefon")
    hv_gruppe = lead_termin.hv_gruppe_ids(session, request.state.benutzer)   # v35: Gruppe
    if hv_gruppe is not None:
        vertriebler = [b for b in vertriebler if b.id in hv_gruppe]
    kollegen = lead_termin.vorab_personen(session, "online")
    testphase = lead_termin.testphase_kontext(session)
    return render(request, "leadmanagement/termin_vorab.html",
                  aktiv="/lead-management", vorgang=vorgang, kunde=kunde, typ=typ,
                  vertriebler=vertriebler, kollegen=kollegen,
                  benutzer=request.state.benutzer,
                  vorgewaehlt=vorgang.ad_id or (hv_id or ""),
                  dauer=lead_termin._int(lead_termin.parameter(session, "vorab_dauer_min", "30"), 30),
                  buchbar=testphase["terminierung_aktiv"],
                  typ_namen=TERMIN_TYP_NAMEN, demo_badge=kern.demo_aktiv(session),
                  meldung=request.query_params.get("meldung", ""), **testphase)


@router.post("/lead/{vorgang_id}/termin/vorab")
def vorab_anlegen(request: Request, vorgang_id: int,
                        session: Session = Depends(get_session)):
    vorgang = _vorgang_oder_404(request, session, vorgang_id)
    form = anfrage.formular(request)
    typ = form.get("typ") or "telefon"
    if not lead_v5.terminierung_aktiv(session):
        return _gesperrt_antwort(request, f"/lead-management/lead/{vorgang.id}/termin/vorab?typ={typ}")
    person = str(form.get("person_id") or "")
    beginn = _datum_uhrzeit(form)
    dauer = str(form.get("dauer") or "")
    if typ == "telefon" and not lead_termin.hv_ad_erlaubt(session, request.state.benutzer, person):
        # v35 (Phase 185): Telefontermine nur für Mitglieder der eigenen Gruppe
        return RedirectResponse(
            f"/lead-management/lead/{vorgang.id}/termin/vorab?typ={typ}&meldung="
            + quote_plus(lead_termin.HV_GRUPPE_KALENDER_TEXT),
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
def termin_absagen(request: Request, termin_id: int,
                         session: Session = Depends(get_session)):
    termin, vorgang = _termin_oder_404(request, session, termin_id)
    form = anfrage.formular(request)
    ziel_fehler = _zurueck(request, _kartei(vorgang.id))
    if not lead_v5.terminierung_aktiv(session):
        return _gesperrt_antwort(request, ziel_fehler)
    grund = (form.get("grund") or "").strip()
    text = (form.get("grund_text") or "").strip()
    passend = next((g for g in _absage_gruende(session) if g.grund == grund), None)
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
        if _json_gewuenscht(request):
            return JSONResponse({"ok": False, "meldung": meldung}, status_code=422)
        return RedirectResponse(_mit_meldung(ziel_fehler, meldung), status_code=303)
    session.commit()
    if _json_gewuenscht(request):
        return JSONResponse({"ok": True, "meldung": meldung, "termin_id": termin.id,
                             "ersatz_url": f"/lead-management/termin/{termin.id}/ersatz" if war_vot else ""})
    if war_vot:
        return RedirectResponse(f"/lead-management/termin/{termin.id}/ersatz?meldung="
                                + quote_plus(meldung + " Der Kunde erhält die Absage mit "
                                             "Storno-ICS. Ersatzkunde für den Slot wählen:"),
                                status_code=303)
    return RedirectResponse(_kartei(vorgang.id, meldung), status_code=303)


@router.get("/termin/{termin_id}/ersatz")
def termin_ersatz(request: Request, termin_id: int,
                        session: Session = Depends(get_session)):
    termin, vorgang = _termin_oder_404(request, session, termin_id)
    kunde = session.get(Kunde, vorgang.kunde_id)
    daten = lead_termin.ersatz_kandidaten(session, termin)
    return render(request, "leadmanagement/termin_ersatz.html",
                  aktiv="/lead-management", termin=termin, vorgang=vorgang, kunde=kunde,
                  score_aktiv=lead_v2.score_aktiv(session),
                  ad=session.get(Benutzer, termin.ad_id) if termin.ad_id else None,
                  kandidaten=daten["kandidaten"], radius=daten["radius"],
                  stufen=daten["stufen"], ort=daten["ort"], alter_tage=daten["alter_tage"],
                  slot=termin.beginn.strftime("%Y-%m-%dT%H:%M") if termin.beginn else "",
                  status_namen=VOT_STATUS_NAMEN_V2, demo_badge=kern.demo_aktiv(session),
                  meldung=request.query_params.get("meldung", ""),
                  **lead_termin.testphase_kontext(session))


@router.post("/termin/{termin_id}/bestaetigung-erneut")
def termin_bestaetigung_erneut(request: Request, termin_id: int,
                                     session: Session = Depends(get_session)):
    """A-9; v31 (Phase 153): bei mehreren Objekten `termin_ids` (mehrfach) und
    `zusammen=1` (eine Mail mit Objektliste und ICS je Objekt), sonst je Termin."""
    termin, vorgang = _termin_oder_404(request, session, termin_id)
    form = anfrage.formular(request)
    ids = [int(x) for x in form.getlist("termin_ids") if str(x).isdigit()] if hasattr(form, "getlist") else []
    termine = [termin]
    if ids:
        termine = [t for t in session.query(VotTermin).filter(VotTermin.id.in_(ids))
                   if t.vorgang_id == vorgang.id]
        if termin.id not in ids and termin.vorgang_id == vorgang.id and not termine:
            termine = [termin]
    ok, meldung = lead_termin.bestaetigung_erneut(session, termin, benutzer=request.state.benutzer,
                                                  termine=termine, zusammen=form.get("zusammen") == "1")
    if ok:
        session.commit()
    else:
        session.rollback()
    if _json_gewuenscht(request):
        return JSONResponse({"ok": ok, "meldung": meldung}, status_code=200 if ok else 422)
    return RedirectResponse(_mit_meldung(_zurueck(request, _kartei(vorgang.id)), meldung),
                            status_code=303)


@router.post("/termin/{termin_id}/verschieben")
def termin_verschieben(request: Request, termin_id: int,
                             session: Session = Depends(get_session)):
    """Umbuchung aus Kalender (Drag & Drop) oder Kartei – wie V1, zusätzlich
    Konfliktsperre, Weitergabe der ICS-UID (SEQUENCE + 1) an den neuen Termin
    und Ersatzkunden-Dialog für den freigewordenen VOT-Slot (E3). v31: das
    Objekt des Termins bleibt (termin_anlegen übernimmt objekt_id), Testphase gesperrt."""
    termin, vorgang = _termin_oder_404(request, session, termin_id)
    form = anfrage.formular(request)
    ziel = _zurueck(request, "/lead-management/kalender")
    if not lead_v5.terminierung_aktiv(session):
        return _gesperrt_antwort(request, ziel)
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
    if not lead_termin.hv_ad_erlaubt(session, request.state.benutzer, ad_id):   # v35: Gruppe
        return RedirectResponse(_mit_meldung(ziel, lead_termin.HV_GRUPPE_KALENDER_TEXT),
                                status_code=303)
    if (termin.typ or "vot") == lead_termin.SPERRZEIT_TYP:
        return RedirectResponse(_mit_meldung(ziel, "Sperrzeiten werden in „Meine Termine“ gepflegt."),
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
                                 f"/lead-management/lead/{vorgang.id}", art="terminaenderung")   # v29
        session.commit()
        return RedirectResponse(_mit_meldung(
            ziel, f"{name} {'eingetragen' if war_vorgemerkt else 'verschoben'}."), status_code=303)
    objekt = lead_termin.objekt_holen(session, vorgang, termin.objekt_id, anlegen=False)
    lead_ort = lead_termin.objekt_ort(session, vorgang, objekt)
    k = lead_termin.konflikte(session, ad_id, beginn, lead_ort=lead_ort, ignorieren_id=termin.id)
    if k["sperren"]:
        return RedirectResponse(_mit_meldung(ziel, "Nicht möglich – " + "; ".join(k["texte"])),
                                status_code=303)
    # vorher geplant/bestätigt (nicht nur vorgemerkt) → der alte Slot wird frei
    war_gebucht = termin.status in lead_termin.AKTIVE_STATUS
    neu, meldung, vorgemerkt = lead_termin.termin_anlegen(
        session, vorgang, ad_id, beginn, benutzer=request.state.benutzer,
        quelle="manuell", umbuchen_id=termin.id, objekt_id=termin.objekt_id)
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
def terminkalender(request: Request, session: Session = Depends(get_session)):
    lead_v2.gate(request, session)
    benutzer = request.state.benutzer
    # v33 (PLAN_V20 Phase 169) [ANNAHME]: der Wochen-Terminkalender je AD (v12) ist im
    # zentralen Mitarbeiter-Kalender aufgegangen – Umleitung mit Person und Woche. Die alte
    # Ansicht bleibt über ?alt=1 erreichbar (Übergang, Kartei) und für Rückmeldungen
    # (?meldung=) der Absage-/Sperrzeit-Routen, die nur hier angezeigt werden.
    q = request.query_params
    if q.get("alt") != "1" and not q.get("meldung"):
        versatz = q.get("woche", "0")
        versatz = int(versatz) if versatz.lstrip("-").isdigit() else 0
        start = datetime.now() + timedelta(weeks=versatz)
        hv_id = lead_termin.hv_nur_eigene(session, benutzer)
        person = str(hv_id) if hv_id else q.get("ad_id", "")
        ziel = f"/kalender?gruppe=vertrieb&ansicht=woche&datum={start:%Y-%m-%d}"
        if person.isdigit():
            ziel += f"&person={int(person)}"
        return RedirectResponse(ziel, status_code=303)
    versatz = request.query_params.get("woche", "0")
    versatz = int(versatz) if versatz.lstrip("-").isdigit() else 0
    start = datetime.now() + timedelta(weeks=versatz)
    nur_ad = request.query_params.get("ad_id", "")
    hv_id = lead_termin.hv_nur_eigene(session, benutzer)   # Kennzeichen „ist Handelsvertreter“ (Template)
    hv_gruppe = lead_termin.hv_gruppe_ids(session, benutzer)
    alle_ad = lead_termin.ad_basis(session)
    if hv_gruppe is not None:
        # v35 (Phase 185): Wochenansicht der Gruppe; ?ad_id= außerhalb der Gruppe verworfen
        alle_ad = [b for b in alle_ad if b.id in hv_gruppe]
        if not (nur_ad.isdigit() and int(nur_ad) in hv_gruppe):
            nur_ad = str(benutzer.id) if len(hv_gruppe) == 1 else ""
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
                  typ_namen=lead_termin.TERMIN_TYP_NAMEN_V4, status_namen=VOT_STATUS_NAMEN_V2,
                  absage_gruende=_absage_gruende(session), hv_id=hv_id,
                  demo_badge=kern.demo_aktiv(session),
                  meldung=request.query_params.get("meldung", ""),
                  **lead_termin.testphase_kontext(session))
