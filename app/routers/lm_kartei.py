# Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 106) – Router Kundenkartei.
# Eigener Router mit demselben Präfix; in app/main.py VOR dem V1-Router
# eingebunden, damit GET /lead-management/lead/{vorgang_id} (V1: Weiterleitung
# auf die Vorgangsakte) hier die Kartei rendert.
# Rechte: lead_v2.gate (404 im Demo-Modus, Handelsvertreter nur an eigenen
# Vorgängen); die Außendienst-Lesesicht (kern.lead_ad_sicht) bleibt read-only.
# v25 (PLAN_LEAD_V3 Phase 119): Autospeichern POST /lead/{id}/feld (JSON),
# Reiter-Default Termin; POST /stammdaten bleibt als Fallback ohne JavaScript.

from datetime import datetime
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import lead_kartei, lead_v2
from app import leadmanagement as kern
from app import vorgaenge as vorgaenge_modul
from app.db import get_session
from app.models import Kunde, Vorgang, VorgangNotizGelesen
from app.templating import render
from app import anfrage   # v27: Formular/JSON in def-Routen

router = APIRouter(prefix="/lead-management")

# v25 (Phase 119): Reiter Termin (Standard) · Anrufnotizen · E-Mail-Verlauf ·
# Timeline; die v23-Reiter qualifizierung/vorgang gibt es nicht mehr (Blöcke
# bzw. abgeschaltet) – alte Links landen auf dem Standard-Reiter.
TABS = ("termin", "anrufe", "mails", "timeline")
TAB_STANDARD = "termin"


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
    tab = (form.get("tab") or "").strip()[:30]
    return tab if tab in TABS else ""


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
def kartei(request: Request, vorgang_id: int,
                 session: Session = Depends(get_session)):
    """Kundenkartei (B1–B8; v25: Kopf mit Statuskette, Kundeninfo-Block,
    Reiter, Blöcke) – übernimmt die V1-Weiterleitung."""
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
    # v29 (PLAN_LEAD_V4 Phase 142, Vertrag L2): roter Hinweisbalken „Mail nicht
    # gesendet“ / „E-Mail falsch“ – Inhalt liefert lead_mail.kartei_hinweis (L2)
    try:
        from app import lead_mail
        mail_hinweis = getattr(lead_mail, "kartei_hinweis", None)
        kontext["mail_hinweis"] = mail_hinweis(session, vorgang) if mail_hinweis else None
    except Exception:
        kontext["mail_hinweis"] = None
    # v28 (PLAN_PROJ_V6 Phase 136): gemeinsamer Notizen-Chat des Vorgangs (Makro
    # notizen_chat) – Block „Notizen“ in voller Breite unter den Blöcken, Kennzeichen „Lead“;
    # Schreibroute bleibt POST /vorgaenge/{id}/notiz
    from app import notizen
    kontext["notizen_ctx"] = notizen.kontext(
        session, vorgang.id, benutzer, vorgang=vorgang, herkunft="lead",
        zurueck=f"/lead-management/lead/{vorgang.id}#notizen")
    tab = request.query_params.get("tab", TAB_STANDARD)
    if tab not in TABS:
        tab = TAB_STANDARD
    return render(request, "leadmanagement/kartei.html", aktiv="/lead-management",
                  **kontext, tab=tab,
                  demo_badge=kern.demo_aktiv(session),
                  badge_text=kern.parameter_holen(session, "demo_badge_text",
                                                  "Demo · Coming soon"),
                  meldung=request.query_params.get("meldung", ""))


# --- Autospeichern (v25, Phase 119) --------------------------------------------------

def _json_oder_form(request: Request) -> dict:
    """Body als JSON ({feld, wert}) oder – Fallback – als Formular lesen."""
    typ = (request.headers.get("content-type") or "").lower()
    if "application/json" in typ:
        try:
            daten = anfrage.json_lesen(request)
        except ValueError:
            return {}
        return daten if isinstance(daten, dict) else {}
    form = anfrage.formular(request)
    daten = {k: form.get(k) for k in form.keys()}
    if hasattr(form, "getlist") and len(form.getlist("wert")) > 1:
        daten["wert"] = form.getlist("wert")
    return daten


def _pflicht_antwort(session: Session, vorgang: Vorgang, kunde: Kunde | None) -> dict:
    """Pflichtfeld-Zähler + Terminierungszustand (B8) für die JSON-Antwort,
    damit die Kartei Zähler, rote Umrandung und den Button ohne Neuladen
    nachführen kann."""
    if kunde is None:
        return {"pflicht_offen": [], "pflicht_anzahl": 0, "pflicht_keys": [],
                "terminierung": {"bereit": False, "fehlend": ["Kunde"], "erledigt": False}}
    status = lead_kartei.pflicht_status(session, kunde, vorgang)
    pruefung = lead_kartei.terminierung_pruefung(session, kunde, vorgang)
    return {"pflicht_offen": status["offen"], "pflicht_anzahl": len(status["offen"]),
            "pflicht_keys": sorted(status["offen_keys"]),
            "terminierung": {"bereit": pruefung["bereit"], "fehlend": pruefung["fehlend"],
                             "erledigt": pruefung["erledigt"]},
            "adresse_vollstaendig": lead_kartei.adresse_vollstaendig(kunde)}


@router.post("/lead/{vorgang_id}/feld")
def feld(request: Request, vorgang_id: int,
               session: Session = Depends(get_session)):
    """Autospeichern eines Feldes des Kundeninfo-Blocks (Vertrag Briefing):
    JSON {feld, wert} → {ok, wert (normalisiert), meldung, pflicht_offen,
    pflicht_anzahl}. Rechte wie bisher: lead_v2.gate (ID/LM/Admin alle,
    Handelsvertreter nur eigene Leads, Außendienst-Lesesicht 404). Fehler →
    HTTP 400, nichts gespeichert (alter Wert bleibt). Adressänderungen
    verwerfen den Cache der Terminvorschläge."""
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    benutzer = request.state.benutzer
    kunde = session.get(Kunde, vorgang.kunde_id)
    daten = _json_oder_form(request)
    feld_name = str(daten.get("feld") or "").strip()
    if feld_name not in lead_kartei.AUTOSPEICHER_FELDER:
        return JSONResponse({"ok": False, "feld": feld_name, "wert": "",
                             "meldung": "Feld unbekannt.", **_pflicht_antwort(session, vorgang, kunde)},
                            status_code=400)
    # v29 (PLAN_LEAD_V4 Phase 140): in der Handelsvertreter-Sicht ist das Feld
    # Innendienst/Leadmanager nur Anzeige
    if feld_name == "leadmanager_id" and lead_v2.hv_sicht(session, benutzer):
        return JSONResponse({"ok": False, "feld": feld_name,
                             "wert": str(vorgang.leadmanager_id or ""),
                             "meldung": "Innendienst wird vom Innendienst zugewiesen (nur Anzeige).",
                             **_pflicht_antwort(session, vorgang, kunde)}, status_code=400)
    erzwingen = (str(daten.get("erzwingen") or "") in ("1", "true", "on")
                 and benutzer.rolle in ("admin", "innendienst"))
    ergebnis = lead_kartei.feld_speichern(session, vorgang, kunde, feld_name,
                                          daten.get("wert"), benutzer=benutzer,
                                          erzwingen=erzwingen)
    if ergebnis["ok"]:
        session.commit()
        if feld_name in lead_kartei.ADRESS_FELDER and ergebnis["geaendert"]:
            lead_kartei.vorschlaege_cache_leeren(vorgang.id)
    else:
        session.rollback()
        vorgang = _vorgang(session, vorgang_id)
        kunde = session.get(Kunde, vorgang.kunde_id)
    antwort = {"ok": ergebnis["ok"], "feld": feld_name, "wert": ergebnis["wert"],
               "meldung": ergebnis["meldung"], "geaendert": ergebnis["geaendert"],
               **_pflicht_antwort(session, vorgang, kunde)}
    return JSONResponse(antwort, status_code=200 if ergebnis["ok"] else 400)


# --- Stammdaten / Zuweisungen (B1–B3) ------------------------------------------------

@router.post("/lead/{vorgang_id}/stammdaten")
def stammdaten(request: Request, vorgang_id: int,
                     session: Session = Depends(get_session)):
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    kunde = session.get(Kunde, vorgang.kunde_id)
    if kunde is None:
        return _zurueck(vorgang_id, "Kunde fehlt.")
    form = anfrage.formular(request)
    meldung, fehler = lead_kartei.stammdaten_speichern(session, vorgang, kunde, form,
                                                        benutzer=request.state.benutzer)
    if fehler:
        session.rollback()
    else:
        session.commit()
    return _zurueck(vorgang_id, meldung, _tab(form))


@router.post("/lead/{vorgang_id}/innendienst")
def innendienst(request: Request, vorgang_id: int,
                      session: Session = Depends(get_session)):
    """Innendienst-Dropdown → lead_v2.leadmanager_zuweisen (Aktivität + Glocke)."""
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    form = anfrage.formular(request)
    neu_id, gueltig = _id_lesen(form, "leadmanager_id")
    if not gueltig:
        return _zurueck(vorgang_id, "Innendienst: ungültige Auswahl – nichts geändert.", _tab(form))
    meldung = lead_v2.leadmanager_zuweisen(session, vorgang, neu_id,
                                           benutzer=request.state.benutzer)
    session.commit()
    return _zurueck(vorgang_id, meldung, _tab(form))


@router.post("/lead/{vorgang_id}/aussendienst")
def aussendienst(request: Request, vorgang_id: int,
                       session: Session = Depends(get_session)):
    """Außendienst-Dropdown → lead_v2.ad_zuweisen (Ausschlussprüfung F14,
    Aktivität, Glocke). erzwingen=1 nur Innendienst/Admin."""
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    form = anfrage.formular(request)
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
def notiz(request: Request, vorgang_id: int,
                session: Session = Depends(get_session)):
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    form = anfrage.formular(request)
    text = (form.get("text") or "").strip()
    if text:
        vorgaenge_modul.notiz_anlegen(session, vorgang.id, request.state.benutzer, text[:2000])
        session.commit()
        return _zurueck(vorgang_id, "Notiz gespeichert.", "timeline")
    return _zurueck(vorgang_id, "Notiz war leer.", "timeline")


# --- Wiedervorlage / Zurückstellen / Nachbearbeitung (F11) ---------------------------

@router.post("/lead/{vorgang_id}/wiedervorlage")
def wiedervorlage(request: Request, vorgang_id: int,
                        session: Session = Depends(get_session)):
    """Dialog „Wiedervorlage“: art=wiedervorlage (naechste_aktion_am) oder
    art=zurueckstellen (bis + Grund aus dem Blatt Gruende)."""
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    form = anfrage.formular(request)
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
def nachbearbeitung(request: Request, vorgang_id: int,
                          session: Session = Depends(get_session)):
    """Schnellaktion „Nachbearbeitung“ (F11/A-4): Zurückstellen mit Grund
    „Nachbearbeitung, noch nicht bereit für VOT“ + Pflicht-Wiedervorlage."""
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    form = anfrage.formular(request)
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
def terminierung(request: Request, vorgang_id: int,
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
def vorab_angebot(request: Request, vorgang_id: int,
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
    return _zurueck(vorgang_id, meldung)
