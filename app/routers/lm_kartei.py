# Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 106) – Router Kundenkartei.
# Eigener Router mit demselben Präfix; in app/main.py VOR dem V1-Router
# eingebunden, damit GET /lead-management/lead/{vorgang_id} (V1: Weiterleitung
# auf die Vorgangsakte) hier die Kartei rendert.
# Rechte: lead_v2.gate (404 im Demo-Modus, Handelsvertreter nur an eigenen
# Vorgängen); die Außendienst-Lesesicht (kern.lead_ad_sicht) bleibt read-only.
# v25 (PLAN_LEAD_V3 Phase 119): Autospeichern POST /lead/{id}/feld (JSON),
# Reiter-Default Termin; POST /stammdaten bleibt als Fallback ohne JavaScript.
# v31 (PLAN_LEAD_V5 Phasen 153/155/157/158): Reiter nur noch Anruf · E-Mail · Timeline
# (?tab=termin springt zum Block Termine), Objekt-Routen POST /lead/{id}/objekt[/{oid}
# [/deaktivieren|/aktivieren|/reihenfolge]] (JSON bei Accept: application/json),
# Status aus der Kartei POST /lead/{id}/status (_speichern-Muster), E-Mail-Dialog
# GET /lead/{id}/mail-dialog.json + POST /lead/{id}/mail-senden, Wiedervorlage in
# 5-Minuten-Schritten (lead_v5.runden_5min), Terminierung in der Testphase gesperrt.

import time
from datetime import datetime
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app import lead_kartei, lead_v2, lead_v5
from app import leadmanagement as kern
from app import objekte as objekte_modul
from app import vorgaenge as vorgaenge_modul
from app.db import get_session
from app.models import Kunde, Vorgang, VorgangNotizGelesen, VorgangObjekt
from app.templating import render
from app import anfrage   # v27: Formular/JSON in def-Routen

router = APIRouter(prefix="/lead-management")

# v25 (Phase 119): Reiter Termin (Standard) · Anrufnotizen · E-Mail-Verlauf ·
# Timeline; die v23-Reiter qualifizierung/vorgang gibt es nicht mehr (Blöcke
# bzw. abgeschaltet) – alte Links landen auf dem Standard-Reiter.
# v31 (Phase 155): Reiter Anruf · E-Mail · Timeline – der Reiter „Termin“ ist im Block
# Termine aufgegangen; ?tab=termin (Links aus Anrufliste/„Erreicht“) öffnet den
# Standard-Reiter und springt zum Block Termine (springe_zu).
TABS = ("anrufe", "mails", "timeline")
TAB_STANDARD = "anrufe"
TAB_ALIAS = {"termin": "termine"}


def _vorgang(session: Session, vorgang_id: int) -> Vorgang:
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        raise HTTPException(status_code=404)
    return vorgang


def _speichern(session: Session, aktion, wiederholungen: int = 1):
    """v31 (v27-Regel): schreibende Routen, die mehrere Zeilen anfassen (Objekt-Sync,
    Status aus der Kartei, Terminierung) – aktion() ausführen und committen; bei
    „database is locked“ Rollback, kurz warten, einmal wiederholen (Vorbild
    routers/angebote._speichern). Liefert den Rückgabewert von aktion()."""
    from app import betrieb
    for versuch in range(wiederholungen + 1):
        start = time.perf_counter()
        try:
            ergebnis = aktion()
            session.commit()
            betrieb.schreibsperre_messen(int((time.perf_counter() - start) * 1000))
            return ergebnis
        except OperationalError as problem:
            session.rollback()
            gesperrt = "locked" in str(problem).lower()
            betrieb.schreibsperre_messen(int((time.perf_counter() - start) * 1000), locked=gesperrt)
            if not gesperrt or versuch >= wiederholungen:
                raise
            time.sleep(0.7)
    return None


def _json_gewuenscht(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "").lower()


def _antwort(request: Request, vorgang_id: int, ok: bool, meldung: str, zusatz: dict | None = None,
             anker: str = "", status_fehler: int = 400):
    """JSON bei Accept: application/json, sonst Redirect in die Kartei mit Meldung."""
    if _json_gewuenscht(request):
        daten = {"ok": ok, "meldung": meldung}
        if zusatz:
            daten.update(zusatz)
        return JSONResponse(daten, status_code=200 if ok else status_fehler)
    antwort = _zurueck(vorgang_id, meldung)
    if anker:
        antwort.headers["location"] = antwort.headers["location"] + "#" + anker
    return antwort


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
        # v31 (PLAN_LEAD_V5 Phase 153): jeder Vorgang hat ein Hauptobjekt (= Kundenadresse) –
        # Leads, die nach der Migration ohne Objekt entstanden sind, bekommen es beim ersten
        # Öffnen der Kartei (derselbe kleine Schreibzugriff wie der Gelesen-Marker)
        objekte_modul.hauptobjekt(session, vorgang.id, anlegen=True)
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
    # v31 (PLAN_LEAD_V5 Phase 154, Vorschlag B 4.1): Archiv-Banner und Kopie-Verweise
    try:
        from app import lead_archiv
        archiv_fn = getattr(lead_archiv, "archiv_text", None)
        kontext["archiv_text"] = archiv_fn(session, vorgang) if archiv_fn else ""
    except Exception:   # noqa: BLE001 – die Kartei darf daran nie scheitern
        kontext["archiv_text"] = ""
    kontext["kopie_von"] = (session.get(Vorgang, vorgang.kopie_von_id)
                            if getattr(vorgang, "kopie_von_id", None) else None)
    kontext["kopien"] = session.query(Vorgang).filter(Vorgang.kopie_von_id == vorgang.id).all()
    tab_roh = request.query_params.get("tab", TAB_STANDARD)
    springe_zu = TAB_ALIAS.get(tab_roh, "")
    tab = tab_roh if tab_roh in TABS else TAB_STANDARD
    return render(request, "leadmanagement/kartei.html", aktiv="/lead-management",
                  **kontext, tab=tab, springe_zu=springe_zu,
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
            # v31 (Phase 153/157): offene Keys je Objekt-Karte (Objekt-ID → Keys)
            "objekt_pflicht_keys": {str(oid): sorted(keys) for oid, keys in status.get("objekte", {}).items()},
            "terminierung": {"bereit": pruefung["bereit"], "fehlend": pruefung["fehlend"],
                             "erledigt": pruefung["erledigt"],
                             "aktiv": lead_v5.terminierung_aktiv(session)},
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
                 and benutzer.basisrolle in ("admin", "innendienst"))
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
                 and benutzer.basisrolle in ("admin", "innendienst"))
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
    # v31 (PLAN_LEAD_V5 Phase 158): Uhrzeit nur in 5-Minuten-Schritten (Dialog step=300,
    # serverseitige Rundung 14:07 → 14:05, 14:08 → 14:10)
    wann = lead_v5.runden_5min(wann)
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

# v31 (PLAN_LEAD_V5 Phase 153, Vertrag T): POST /lead/{id}/terminierung liegt in
# routers/lm_termin.py (bucht alle vorgemerkten Objekttermine, Wahl der Bestätigung,
# Testphase → 403/Meldung, _speichern-Muster) – die frühere Kartei-Route ist entfernt,
# damit nicht die alte Ein-Termin-Logik gewinnt (Router-Reihenfolge in main.py).


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


# --- v31 (PLAN_LEAD_V5 Phase 153/157): Objekte am Vorgang ---------------------------------

class _FormWrap(dict):
    """JSON-Body wie ein Formular lesen (getlist für Listenfelder wie interesse)."""

    def getlist(self, name):
        wert = self.get(name)
        if wert is None or wert == "":
            return []
        if isinstance(wert, (list, tuple)):
            return [str(w) for w in wert]
        return [str(w).strip() for w in str(wert).split(",") if str(w).strip()]


def _objekt(session: Session, vorgang: Vorgang, objekt_id: int) -> VorgangObjekt:
    objekt = session.get(VorgangObjekt, objekt_id)
    if objekt is None or objekt.vorgang_id != vorgang.id:
        raise HTTPException(status_code=404)
    return objekt


def _objekt_form(request: Request):
    """Formular oder JSON – immer mit getlist (interesse-Häkchen)."""
    typ = (request.headers.get("content-type") or "").lower()
    if "application/json" in typ:
        try:
            daten = anfrage.json_lesen(request)
        except ValueError:
            daten = {}
        return _FormWrap(daten if isinstance(daten, dict) else {})
    return anfrage.formular(request)


@router.post("/lead/{vorgang_id}/objekt")
def objekt_anlegen(request: Request, vorgang_id: int,
                   session: Session = Depends(get_session)):
    """„Objekt hinzufügen“: Formular (bezeichnung, strasse, plz, ort, objektart, parteien,
    interesse[], rechnung_identisch ja|nein, rechnung_*) → neues vorgang_objekte-Objekt
    (reihenfolge = nächste Nummer), Aktivität; JSON bei Accept: application/json."""
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    kunde = session.get(Kunde, vorgang.kunde_id)
    form = _objekt_form(request)
    ergebnis: dict = {}

    def aktion():
        objekt, meldung = lead_kartei.objekt_anlegen_aus_form(session, vorgang, kunde, form,
                                                              benutzer=request.state.benutzer)
        ergebnis.update(objekt=objekt, meldung=meldung)
        if objekt is None:
            session.rollback()
    _speichern(session, aktion)
    objekt = ergebnis.get("objekt")
    return _antwort(request, vorgang_id, objekt is not None, ergebnis.get("meldung", ""),
                    {"objekt_id": objekt.id if objekt is not None else None}, anker="lk-objekte")


@router.post("/lead/{vorgang_id}/objekt/{objekt_id}")
def objekt_feld(request: Request, vorgang_id: int, objekt_id: int,
                session: Session = Depends(get_session)):
    """Autospeichern eines Objektfelds (JSON {feld, wert}) – Antwort wie POST /feld plus
    objekt_id; Hauptobjekt-Felder laufen über die Kundenfelder (hauptobjekt_sync)."""
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    objekt = _objekt(session, vorgang, objekt_id)
    kunde = session.get(Kunde, vorgang.kunde_id)
    daten = _json_oder_form(request)
    feld_name = str(daten.get("feld") or "").strip()
    if feld_name not in lead_kartei.OBJEKT_FELDER:
        return JSONResponse({"ok": False, "feld": feld_name, "wert": "", "meldung": "Feld unbekannt.",
                             "objekt_id": objekt.id, **_pflicht_antwort(session, vorgang, kunde)},
                            status_code=400)
    ergebnis: dict = {}

    def aktion():
        ergebnis.update(lead_kartei.objekt_feld_speichern(session, vorgang, kunde, objekt, feld_name,
                                                          daten.get("wert"), benutzer=request.state.benutzer))
        if not ergebnis["ok"]:
            session.rollback()
    _speichern(session, aktion)
    if not ergebnis["ok"]:
        vorgang = _vorgang(session, vorgang_id)
        kunde = session.get(Kunde, vorgang.kunde_id)
    antwort = {"ok": ergebnis["ok"], "feld": feld_name, "wert": ergebnis["wert"],
               "meldung": ergebnis["meldung"], "geaendert": ergebnis["geaendert"],
               "objekt_id": objekt.id, **_pflicht_antwort(session, vorgang, kunde)}
    return JSONResponse(antwort, status_code=200 if ergebnis["ok"] else 400)


@router.post("/lead/{vorgang_id}/objekt/{objekt_id}/deaktivieren")
def objekt_deaktivieren(request: Request, vorgang_id: int, objekt_id: int,
                        session: Session = Depends(get_session)):
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    objekt = _objekt(session, vorgang, objekt_id)
    ergebnis: dict = {}

    def aktion():
        ok, meldung = lead_kartei.objekt_deaktivieren(session, vorgang, objekt,
                                                      benutzer=request.state.benutzer)
        ergebnis.update(ok=ok, meldung=meldung)
    _speichern(session, aktion)
    return _antwort(request, vorgang_id, ergebnis["ok"], ergebnis["meldung"], anker="lk-objekte")


@router.post("/lead/{vorgang_id}/objekt/{objekt_id}/aktivieren")
def objekt_aktivieren(request: Request, vorgang_id: int, objekt_id: int,
                      session: Session = Depends(get_session)):
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    objekt = _objekt(session, vorgang, objekt_id)
    ergebnis: dict = {}

    def aktion():
        ok, meldung = lead_kartei.objekt_aktivieren(session, vorgang, objekt,
                                                    benutzer=request.state.benutzer)
        ergebnis.update(ok=ok, meldung=meldung)
    _speichern(session, aktion)
    return _antwort(request, vorgang_id, ergebnis["ok"], ergebnis["meldung"], anker="lk-objekte")


@router.post("/lead/{vorgang_id}/objekt/{objekt_id}/reihenfolge")
def objekt_reihenfolge(request: Request, vorgang_id: int, objekt_id: int,
                       session: Session = Depends(get_session)):
    """Pfeil hoch/runter (Feld richtung = hoch | runter); das Hauptobjekt bleibt an erster Stelle."""
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    objekt = _objekt(session, vorgang, objekt_id)
    daten = _json_oder_form(request)
    richtung = ("hoch" if str(daten.get("richtung") or "").strip().lower() in ("hoch", "up", "-1")
                else "runter")
    ergebnis: dict = {}

    def aktion():
        ok, meldung = lead_kartei.objekt_reihenfolge(session, vorgang, objekt, richtung,
                                                     benutzer=request.state.benutzer)
        ergebnis.update(ok=ok, meldung=meldung)
    _speichern(session, aktion)
    return _antwort(request, vorgang_id, ergebnis["ok"], ergebnis["meldung"], anker="lk-objekte")


# --- v31 (PLAN_LEAD_V5 Phase 157): Status aus der Kartei -----------------------------------

@router.post("/lead/{vorgang_id}/status")
def status_setzen(request: Request, vorgang_id: int,
                  session: Session = Depends(get_session)):
    """Statuskette/Dropdown im Kopf: JSON {wert, grund?, grund_text?, bis?} → dieselben
    Regeln wie der Inline-Edit der Boards (lead_boards.status_setzen; Zurückgestellt
    Datum + Grund, Disqualifiziert/Verloren Pflichtgrund, abgeleitete Phasen gesperrt),
    _speichern-Muster. Antwort {ok, meldung, phase, label}; 422 bei Ablehnung."""
    vorgang = _vorgang(session, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    daten = _json_oder_form(request)
    ziel = str(daten.get("wert") or daten.get("status") or "").strip()
    ergebnis: dict = {}

    def aktion():
        ok, meldung = lead_kartei.status_aus_kartei(
            session, vorgang, ziel, benutzer=request.state.benutzer,
            grund=str(daten.get("grund") or ""), grund_text=str(daten.get("grund_text") or ""),
            bis=daten.get("bis"))
        ergebnis.update(ok=ok, meldung=meldung)
        if not ok:
            session.rollback()
    _speichern(session, aktion)
    vorgang = _vorgang(session, vorgang_id)
    from app import leadmanagement_logik
    label = lead_kartei.phasen_label(leadmanagement_logik.hole_logik(), vorgang.lead_phase or "neu")
    return _antwort(request, vorgang_id, ergebnis["ok"], ergebnis["meldung"],
                    {"phase": vorgang.lead_phase, "label": label}, status_fehler=422)


# --- v31 (PLAN_LEAD_V5 Phase 158): E-Mail aus der Kundenkartei mit Vorlage ------------------
# Vorschau und Senden des Kartei-Dialogs laufen über T's Routen in routers/lm_mail.py
# (GET /lead/{id}/mail/vorschau.json, POST /lead/{id}/mail/senden) – keine eigenen Wege.
