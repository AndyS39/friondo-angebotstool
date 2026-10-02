# Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 106) – Router Kundenkartei.
# Eigener Router mit demselben Präfix; in app/main.py VOR dem V1-Router
# eingebunden, damit GET /lead-management/lead/{vorgang_id} (V1: Weiterleitung
# auf die Vorgangsakte) hier die dreispaltige Kartei rendert.
# Rechte: lead_v2.gate (404 im Demo-Modus, Handelsvertreter nur an eigenen
# Vorgängen); die Außendienst-Lesesicht (kern.lead_ad_sicht) bleibt read-only.

from datetime import datetime
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import lead_kartei, lead_v2
from app import leadmanagement as kern
from app import vorgaenge as vorgaenge_modul
from app.db import get_session
from app.models import Kunde, Vorgang, VorgangNotizGelesen
from app.templating import render

router = APIRouter(prefix="/lead-management")


def _vorgang(session: Session, vorgang_id: int) -> Vorgang:
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        raise HTTPException(status_code=404)
    return vorgang


def _lesegate(request: Request, session: Session, vorgang: Vorgang) -> bool:
    """GET-Gate: volle Sicht über lead_v2.zugriff_erlaubt (Modul-Sichtbare,
    Handelsvertreter am eigenen Vorgang); Außendienst-Lesesicht (nur bei
    lead_freigabe_modus = alle, eigener Vorgang) read-only; sonst 404.
    Liefert readonly."""
    benutzer = request.state.benutzer
    if lead_v2.zugriff_erlaubt(session, benutzer, vorgang):
        return False
    if (kern.lead_ad_sicht(session, benutzer)
            and vorgaenge_modul.gehoert_benutzer(session, vorgang, benutzer.id)):
        return True
    raise HTTPException(status_code=404)


def _zurueck(vorgang_id: int, meldung: str = "", tab: str = "") -> RedirectResponse:
    url = f"/lead-management/lead/{vorgang_id}"
    teile = []
    if meldung:
        teile.append("meldung=" + quote_plus(meldung))
    if tab:
        teile.append("tab=" + quote_plus(tab))
    if teile:
        url += "?" + "&".join(teile)
    return RedirectResponse(url, status_code=303)


def _tab(form) -> str:
    return (form.get("tab") or "").strip()[:30]


def _id_lesen(form, name: str):
    """Formfeld als ID: (wert, gueltig). Leer = Zuweisung entfernen (None, True);
    Ziffern = ID; alles andere ist ungültig und darf nichts löschen."""
    roh = (form.get(name) or "").strip()
    if not roh:
        return None, True
    if roh.isdigit():
        return int(roh), True
    return None, False


# --- Kartei --------------------------------------------------------------------------

@router.get("/lead/{vorgang_id}")
async def kartei(request: Request, vorgang_id: int,
                 session: Session = Depends(get_session)):
    """Dreispaltige Kundenkartei (B1–B8) – übernimmt die V1-Weiterleitung."""
    vorgang = _vorgang(session, vorgang_id)
    readonly = _lesegate(request, session, vorgang)
    benutzer = request.state.benutzer
    # Gelesen-Stand des Notizen-Chats fortschreiben (wie die Vorgangsakte, v10) –
    # nur Komfort: schlägt das Schreiben fehl (z. B. SQLite „database is locked“
    # durch parallele Läufe), wird die Kartei trotzdem gerendert
    try:
        marker = (session.query(VorgangNotizGelesen)
                  .filter(VorgangNotizGelesen.vorgang_id == vorgang.id,
                          VorgangNotizGelesen.benutzer_id == benutzer.id).first())
        if marker is None:
            session.add(VorgangNotizGelesen(vorgang_id=vorgang.id, benutzer_id=benutzer.id))
        else:
            marker.gelesen_bis = datetime.now()
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        vorgang = _vorgang(session, vorgang_id)
    kontext = lead_kartei.kartei_kontext(session, vorgang, benutzer, readonly)
    tab = request.query_params.get("tab", "timeline")
    if tab not in ("timeline", "mails", "anrufe", "qualifizierung", "termin", "vorgang"):
        tab = "timeline"
    return render(request, "leadmanagement/kartei.html", aktiv="/lead-management",
                  **kontext, tab=tab,
                  demo_badge=kern.demo_aktiv(session),
                  badge_text=kern.parameter_holen(session, "demo_badge_text",
                                                  "Demo · Coming soon"),
                  meldung=request.query_params.get("meldung", ""))


# --- Stammdaten / Zuweisungen (B1–B3) ------------------------------------------------

@router.post("/lead/{vorgang_id}/stammdaten")
async def stammdaten(request: Request, vorgang_id: int,
                     session: Session = Depends(get_session)):
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    kunde = session.get(Kunde, vorgang.kunde_id)
    if kunde is None:
        return _zurueck(vorgang_id, "Kunde fehlt.")
    form = await request.form()
    meldung, fehler = lead_kartei.stammdaten_speichern(session, vorgang, kunde, form,
                                                        benutzer=request.state.benutzer)
    if fehler:
        session.rollback()
    else:
        session.commit()
    return _zurueck(vorgang_id, meldung, _tab(form))


@router.post("/lead/{vorgang_id}/innendienst")
async def innendienst(request: Request, vorgang_id: int,
                      session: Session = Depends(get_session)):
    """Innendienst-Dropdown → lead_v2.leadmanager_zuweisen (Aktivität + Glocke)."""
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    form = await request.form()
    neu_id, gueltig = _id_lesen(form, "leadmanager_id")
    if not gueltig:
        return _zurueck(vorgang_id, "Innendienst: ungültige Auswahl – nichts geändert.", _tab(form))
    meldung = lead_v2.leadmanager_zuweisen(session, vorgang, neu_id,
                                           benutzer=request.state.benutzer)
    session.commit()
    return _zurueck(vorgang_id, meldung, _tab(form))


@router.post("/lead/{vorgang_id}/aussendienst")
async def aussendienst(request: Request, vorgang_id: int,
                       session: Session = Depends(get_session)):
    """Außendienst-Dropdown → lead_v2.ad_zuweisen (Ausschlussprüfung F14,
    Aktivität, Glocke). erzwingen=1 nur Innendienst/Admin."""
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    form = await request.form()
    benutzer = request.state.benutzer
    neu_id, gueltig = _id_lesen(form, "ad_id")
    if not gueltig:
        return _zurueck(vorgang_id, "Außendienst: ungültige Auswahl – nichts geändert.", _tab(form))
    erzwingen = (form.get("erzwingen") == "1"
                 and benutzer.rolle in ("admin", "innendienst"))
    meldung = lead_v2.ad_zuweisen(session, vorgang, neu_id,
                                  benutzer=benutzer, erzwingen=erzwingen)
    session.commit()
    return _zurueck(vorgang_id, meldung, _tab(form))


# --- Notiz (Notizen-Chat des Vorgangs, Rücksprung in die Kartei) ---------------------

@router.post("/lead/{vorgang_id}/notiz")
async def notiz(request: Request, vorgang_id: int,
                session: Session = Depends(get_session)):
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    form = await request.form()
    text = (form.get("text") or "").strip()
    if text:
        vorgaenge_modul.notiz_anlegen(session, vorgang.id, request.state.benutzer, text[:2000])
        session.commit()
        return _zurueck(vorgang_id, "Notiz gespeichert.", "timeline")
    return _zurueck(vorgang_id, "Notiz war leer.", "timeline")


# --- Wiedervorlage / Zurückstellen / Nachbearbeitung (F11) ---------------------------

@router.post("/lead/{vorgang_id}/wiedervorlage")
async def wiedervorlage(request: Request, vorgang_id: int,
                        session: Session = Depends(get_session)):
    """Dialog „Wiedervorlage“: art=wiedervorlage (naechste_aktion_am) oder
    art=zurueckstellen (bis + Grund aus dem Blatt Gruende)."""
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    form = await request.form()
    benutzer = request.state.benutzer
    art = (form.get("art") or "wiedervorlage").strip()
    if art == "zurueckstellen":
        try:
            bis = datetime.strptime((form.get("bis") or "").strip(), "%Y-%m-%d")
        except ValueError:
            return _zurueck(vorgang_id, "Zurückstellen: Datum ist Pflicht.")
        fehler = lead_kartei.zurueckstellen(session, vorgang, bis,
                                            (form.get("grund") or "").strip(),
                                            (form.get("grund_text") or "").strip(),
                                            benutzer=benutzer)
        if fehler:
            session.rollback()
            return _zurueck(vorgang_id, fehler)
        session.commit()
        return _zurueck(vorgang_id, f"Zurückgestellt bis {bis.strftime('%d.%m.%Y')}.")
    roh = (form.get("wann") or "").strip()
    wann = None
    for muster in ("%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            wann = datetime.strptime(roh, muster)
            break
        except ValueError:
            continue
    if wann is None:
        return _zurueck(vorgang_id, "Wiedervorlage: Datum/Uhrzeit ist Pflicht.")
    lead_kartei.wiedervorlage_setzen(session, vorgang, wann,
                                     (form.get("notiz") or "").strip()[:500], benutzer=benutzer)
    session.commit()
    return _zurueck(vorgang_id, f"Wiedervorlage {wann.strftime('%d.%m.%Y %H:%M')} gemerkt.")


@router.post("/lead/{vorgang_id}/nachbearbeitung")
async def nachbearbeitung(request: Request, vorgang_id: int,
                          session: Session = Depends(get_session)):
    """Schnellaktion „Nachbearbeitung“ (F11/A-4): Zurückstellen mit Grund
    „Nachbearbeitung, noch nicht bereit für VOT“ + Pflicht-Wiedervorlage."""
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    form = await request.form()
    roh = (form.get("bis") or "").strip()
    bis = None
    if roh:
        try:
            bis = datetime.strptime(roh, "%Y-%m-%d")
        except ValueError:
            return _zurueck(vorgang_id, "Nachbearbeitung: Wiedervorlage-Datum ungültig.")
    if bis is not None and bis.date() < datetime.now().date():
        return _zurueck(vorgang_id, "Nachbearbeitung: Wiedervorlage darf nicht in der "
                                    "Vergangenheit liegen.")
    bis = lead_kartei.nachbearbeitung(session, vorgang, bis,
                                      (form.get("notiz") or "").strip()[:500],
                                      benutzer=request.state.benutzer)
    session.commit()
    return _zurueck(vorgang_id, f"Nachbearbeitung – Wiedervorlage {bis.strftime('%d.%m.%Y')}.")


# --- Terminierung (B8) / Vorab-Angebot (F10) -----------------------------------------

@router.post("/lead/{vorgang_id}/terminierung")
async def terminierung(request: Request, vorgang_id: int,
                       session: Session = Depends(get_session)):
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    ok, meldung = lead_kartei.terminierung_ausfuehren(session, vorgang,
                                                      benutzer=request.state.benutzer)
    if ok:
        session.commit()
    else:
        session.rollback()
    return _zurueck(vorgang_id, meldung, "termin")


@router.post("/lead/{vorgang_id}/vorab-angebot")
async def vorab_angebot(request: Request, vorgang_id: int,
                        session: Session = Depends(get_session)):
    """„Erfassung ohne Termin“ (A-3/F10): Kennzeichen + Aktivität, dann in die
    bestehende Erfassung; Demo-Leads bekommen nur Kennzeichen/Badge."""
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    meldung, ziel = lead_kartei.vorab_angebot_setzen(session, vorgang,
                                                     benutzer=request.state.benutzer)
    session.commit()
    if ziel:
        return RedirectResponse(ziel, status_code=303)
    return _zurueck(vorgang_id, meldung, "vorgang")
