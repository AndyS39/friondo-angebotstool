# Lead-Management V2 (v23) – Router info (PLAN_LEAD_V2 Phase 111: Reiter
# „Infoabend“ (bis v24 „Info-Veranstaltung“; Pfad /info-veranstaltung, Parameter info_*
# und Tabellennamen bleiben), Teil 2 I1–I5, A-8). Eigener Router mit demselben Präfix;
# in app/main.py VOR dem V1-Router eingebunden. Jede Route läuft über
# lead_v2.gate (404 im Demo-Modus für Nicht-Admins; Handelsvertreter sehen nur
# eigene Leads). Fachlogik in app/lead_info.py.
#
# Routen:
#   GET  /lead-management/info-veranstaltung                         Board (Gruppen je Termin, Archiv)
#   POST /lead-management/info-veranstaltung/sammelaktion            Status ändern · nächste Veranstaltung · Teilgenommen
#   POST /lead-management/info-veranstaltung/{vorgang_id}/teilgenommen  Ja/Nein/leer (Form oder JSON)
#   POST /lead-management/info-veranstaltung/{vorgang_id}/veranstaltung Dropdown je Lead
#   POST /lead-management/info-veranstaltung/{vorgang_id}/zeile      Inline-Felder der Tabelle (JSON)
#   GET/POST /lead-management/info-veranstaltung/termine             Veranstaltungs-Pflege
# Ergebnis-Buttons der Zeilen posten an POST /lead-management/anruf/{id}
# (Vertrag Phase 107) mit zurueck=/lead-management/info-veranstaltung.

from datetime import date, timedelta
from urllib.parse import quote_plus, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import lead_info, lead_v2
from app import leadmanagement as kern
from app.db import get_session
from app.models import InfoVeranstaltung, Vorgang, LEAD_PHASEN_NAMEN
from app.templating import render, templates
from app import anfrage   # v27: Formular/JSON in def-Routen

router = APIRouter(prefix="/lead-management")

BOARD_PFAD = "/lead-management/info-veranstaltung"
TERMINE_PFAD = BOARD_PFAD + "/termine"

# Sammelaktionen in der Registry von Phase 105 anmelden (Board „info“)
lead_info.sammelaktionen_registrieren()


# --- Helfer -------------------------------------------------------------------------------

def _template_vorhanden(name: str) -> bool:
    """Phase-105-/107-Templates sind optional (Rückfall eigene Tabelle/Dialoge)."""
    try:
        templates.env.get_template(name)
        return True
    except Exception:
        return False


def _json_gewuenscht(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "")


def _pfad_sicher(roh, standard: str = BOARD_PFAD) -> str:
    """Nur relative Pfade als Redirect-Ziel (Open-Redirect-Schutz)."""
    text = str(roh or "").strip()
    if not text.startswith("/") or text.startswith("//") or "\\" in text \
            or any(c in text for c in "\r\n"):
        return standard
    return text


def _mit_meldung(pfad: str, meldung: str, fehler: bool = False) -> str:
    return (pfad + ("&" if "?" in pfad else "?") + "meldung=" + quote_plus(meldung)
            + ("&fehler=1" if fehler else ""))


def _zurueck_aus_query(request: Request) -> str:
    """Aktueller Board-Pfad ohne Meldungsparameter (für Ergebnis-Buttons/Formulare)."""
    params = [(k, v) for k, v in request.query_params.multi_items()
              if k not in ("meldung", "fehler")]
    return BOARD_PFAD + ("?" + urlencode(params) if params else "")


def _daten(request: Request) -> dict:
    """JSON-Rumpf oder Formular → dict (Listen als Listen)."""
    if "application/json" in (request.headers.get("content-type") or ""):
        try:
            daten = anfrage.json_lesen(request)
        except Exception:
            daten = {}
        return daten if isinstance(daten, dict) else {}
    form = anfrage.formular(request)
    daten = {k: form.get(k) for k in form.keys()}
    daten["ids"] = form.getlist("ids") or form.getlist("ids[]")
    return daten


def _badge(session: Session) -> dict:
    return {"demo_badge": kern.demo_aktiv(session),
            "badge_text": kern.parameter_holen(session, "demo_badge_text", "Demo · Coming soon")}


def _ctx(session: Session, benutzer, zurueck: str) -> dict:
    ctx = lead_info.tabellen_kontext(session, benutzer)
    ctx["zurueck"] = zurueck
    ctx["tabelle_makro"] = _template_vorhanden("leadmanagement/_tabelle.html")
    ctx["dialoge_makro"] = _template_vorhanden("leadmanagement/anruf_dialoge.html")
    ctx["score_aktiv"] = lead_v2.score_aktiv(session)   # v25: Tooltip „Erreicht“ (Kartei statt Bogen)
    # v25 (Phase 118): gemerkte Sortierung des Nutzers (Board „info“) für aria-sort der Köpfe
    ctx["sortierung"] = lead_info.sortierung_fuer(session, benutzer)
    return ctx


def _zeile_html(session: Session, benutzer, vorgang: Vorgang, zurueck: str) -> str | None:
    """Eine Tabellenzeile neu rendern (nach Teilgenommen/Veranstaltung/Inline)."""
    try:
        z = lead_info.zeile_fuer(session, benutzer, vorgang)
        if z is None:
            return None
        ctx = _ctx(session, benutzer, zurueck)
        spalten = lead_info.spalten_fuer(session, benutzer.id, ctx["tabelle_makro"])
        modul = templates.env.get_template("leadmanagement/info_tabelle.html").module
        return str(modul.info_zeile(z, spalten, ctx))
    except Exception:
        return None


def _vorgang_laden(request: Request, session: Session, vorgang_id: int) -> Vorgang:
    vorgang = session.get(Vorgang, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    if vorgang is None:
        raise HTTPException(status_code=404)
    return vorgang


def _antwort(request: Request, session: Session, vorgang: Vorgang, ok: bool, meldung: str,
             zurueck: str, **zusatz):
    if _json_gewuenscht(request):
        antwort = {"ok": ok, "meldung": meldung, "vorgang_id": vorgang.id, **zusatz}
        if ok:
            html = _zeile_html(session, request.state.benutzer, vorgang, zurueck)
            if html:
                antwort["zeile_html"] = html
            antwort["gruppe"] = (f"v{vorgang.veranstaltung_id}" if vorgang.veranstaltung_id
                                 else lead_info.GRUPPE_OHNE)
        return JSONResponse(antwort, status_code=200 if ok else 422)
    return RedirectResponse(_mit_meldung(zurueck, meldung, fehler=not ok), status_code=303)


# --- Board (I2/I3) --------------------------------------------------------------------------

@router.get("/info-veranstaltung")
def info_board(request: Request, session: Session = Depends(get_session)):
    """Gruppen je Veranstaltung (Titel mit Datum/Uhrzeit/Ort, Kennzeichen
    „verschoben (Feiertag)“, Zähler, einklappbar), Filter Archiv, Spalten wie
    Hauptboard + Teilgenommen + Veranstaltung + Ergebnis-Buttons, roter Hinweis
    „Kunde bereits im System“ (I5), Sammelaktionen (H3). Beim Rendern werden
    Veranstaltungen rollierend nachgelegt und vergangene archiviert."""
    lead_v2.gate(request, session)
    benutzer = request.state.benutzer
    try:
        lead_info.veranstaltungen_anlegen(session)
        lead_info.archivieren(session)
        session.commit()
    except Exception:
        session.rollback()
    f = lead_info.filter_aus_query(request.query_params)
    zurueck = _zurueck_aus_query(request)
    ctx = _ctx(session, benutzer, zurueck)
    f["sort"] = ctx["sortierung"]          # v25: gemerkte Sortierung je Nutzer (Board „info“)
    daten = lead_info.board_daten(session, benutzer, f)
    p = lead_info.parameter(session)
    from app.models import INTERESSEN
    return render(request, "leadmanagement/info_board.html", aktiv="/lead-management",
                  gruppen=daten["gruppen"], anzahl=daten["anzahl"], jetzt=daten["jetzt"],
                  archiv=daten["archiv"], filter_werte=f, ctx=ctx, sparten_liste=INTERESSEN,
                  sortierung=ctx["sortierung"], konfig_board=lead_info.KONFIG_BOARD,
                  spalten=lead_info.spalten_fuer(session, benutzer.id, ctx["tabelle_makro"]),
                  sammelaktionen=lead_info.sammelaktionen() if ctx["sammel"] else [],
                  tabelle_makro=ctx["tabelle_makro"], dialoge_makro=ctx["dialoge_makro"],
                  zurueck_pfad=zurueck, phasen_namen=LEAD_PHASEN_NAMEN, parameter=p,
                  wochentag_name=["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag",
                                  "Samstag", "Sonntag"][p["wochentag"]],
                  meldung=request.query_params.get("meldung", ""),
                  fehler=request.query_params.get("fehler", "") == "1", **_badge(session))


# --- Sammelaktionen (H3) ---------------------------------------------------------------------

@router.post("/info-veranstaltung/sammelaktion")
def info_sammelaktion(request: Request, session: Session = Depends(get_session)):
    """ids[] + aktion (status | naechste | teilgenommen) + Parameter (status, grund,
    grund_text, bis, teilgenommen, zurueck). Formular → Redirect mit Meldung,
    Accept application/json → JSON. Je Lead eine Aktivität."""
    lead_v2.gate(request, session)
    benutzer = request.state.benutzer
    daten = _daten(request)
    ids = daten.get("ids") or []
    if isinstance(ids, str):
        ids = [ids]
    params = {k: v for k, v in daten.items() if k not in ("ids", "ids[]")}
    aktion = str(params.get("aktion") or "").strip()
    zurueck = _pfad_sicher(params.get("zurueck"))
    ok, meldung = lead_info.sammelaktion_ausfuehren(session, benutzer, aktion, ids, params)
    if ok:
        session.commit()
    else:
        session.rollback()
    if _json_gewuenscht(request):
        return JSONResponse({"ok": ok, "meldung": meldung}, status_code=200 if ok else 422)
    return RedirectResponse(_mit_meldung(zurueck, meldung, fehler=not ok), status_code=303)


# --- Teilgenommen (I3) ------------------------------------------------------------------------

@router.post("/info-veranstaltung/{vorgang_id}/teilgenommen")
def info_teilgenommen(request: Request, vorgang_id: int,
                            session: Session = Depends(get_session)):
    """wert (oder teilgenommen) = ja | nein | leer → vorgaenge.teilgenommen,
    Aktivität typ status. JSON-Antwort mit zeile_html bei Accept: application/json."""
    vorgang = _vorgang_laden(request, session, vorgang_id)
    daten = _daten(request)
    zurueck = _pfad_sicher(daten.get("zurueck"))
    gueltig, wert = lead_info.teilgenommen_lesen(
        daten.get("wert") if daten.get("wert") is not None else daten.get("teilgenommen"))
    if not gueltig:
        session.rollback()
        return _antwort(request, session, vorgang, False,
                        "Teilgenommen: Wert ja | nein | leer erwartet.", zurueck)
    meldung = lead_info.teilgenommen_setzen(session, vorgang, wert, benutzer=request.state.benutzer)
    session.commit()
    return _antwort(request, session, vorgang, True, meldung, zurueck,
                    teilgenommen={True: "ja", False: "nein", None: ""}[wert])


# --- Veranstaltung je Lead ändern (I4, manuell) ---------------------------------------------

@router.post("/info-veranstaltung/{vorgang_id}/veranstaltung")
def info_veranstaltung_setzen(request: Request, vorgang_id: int,
                                    session: Session = Depends(get_session)):
    """veranstaltung_id (leer = Zuordnung aufheben) → Aktivität je Lead."""
    vorgang = _vorgang_laden(request, session, vorgang_id)
    daten = _daten(request)
    zurueck = _pfad_sicher(daten.get("zurueck"))
    roh = str(daten.get("veranstaltung_id") or "").strip()
    veranstaltung = None
    if roh:
        if not roh.isdigit():
            return _antwort(request, session, vorgang, False, "Veranstaltung nicht lesbar.", zurueck)
        veranstaltung = session.get(InfoVeranstaltung, int(roh))
        if veranstaltung is None:
            return _antwort(request, session, vorgang, False, "Veranstaltung nicht gefunden.", zurueck)
    meldung = lead_info.veranstaltung_zuordnen(session, vorgang, veranstaltung,
                                               benutzer=request.state.benutzer,
                                               grund="manuell geändert")
    session.commit()
    return _antwort(request, session, vorgang, True, meldung, zurueck)


# --- Inline-Felder der Tabelle (Status/Notiz/AD/ID/Wiedervorlage) ----------------------------

@router.post("/info-veranstaltung/{vorgang_id}/zeile")
def info_zeile_aendern(request: Request, vorgang_id: int,
                             session: Session = Depends(get_session)):
    """JSON {feld, wert, grund?, grund_text?, bis?} → {ok, meldung, phase,
    zeile_html}. Nutzt lead_boards.zeile_aendern (Phase 105: Pflichtgründe,
    Zuweisung über lead_v2); ohne das Modul 422."""
    vorgang = _vorgang_laden(request, session, vorgang_id)
    daten = _daten(request)
    zurueck = _pfad_sicher(daten.get("zurueck"))
    try:
        from app import lead_boards
    except Exception:
        lead_boards = None
    if lead_boards is None:
        return JSONResponse({"ok": False, "meldung": "Inline-Bearbeitung ist ohne das "
                                                     "Board-Modul (Phase 105) nicht verfügbar."},
                            status_code=422)
    ok, meldung = lead_boards.zeile_aendern(session, vorgang, str(daten.get("feld") or ""),
                                            daten.get("wert"), benutzer=request.state.benutzer,
                                            daten=daten)
    if ok:
        session.commit()
    else:
        session.rollback()
    antwort = {"ok": ok, "meldung": meldung, "phase": vorgang.lead_phase, "vorgang_id": vorgang.id}
    if ok:
        html = _zeile_html(session, request.state.benutzer, vorgang, zurueck)
        if html:
            antwort["zeile_html"] = html
    if _json_gewuenscht(request) or "application/json" in (request.headers.get("content-type") or ""):
        return JSONResponse(antwort, status_code=200 if ok else 422)
    return RedirectResponse(_mit_meldung(zurueck, meldung, fehler=not ok), status_code=303)


# --- Veranstaltungs-Pflege --------------------------------------------------------------------

def _pflege_gate(request: Request, session: Session) -> None:
    lead_v2.gate(request, session)
    if lead_v2.ist_handelsvertreter(session, request.state.benutzer):
        raise HTTPException(status_code=404)


def _termine_seite(request: Request, session: Session):
    try:
        lead_info.veranstaltungen_anlegen(session)
        lead_info.archivieren(session)
        session.commit()
    except Exception:
        session.rollback()
    p = lead_info.parameter(session)
    heute = date.today()
    kontrolle = lead_info.termine_ab(heute.replace(day=1), 12, p["wochentag"], p["woche"],
                                     p["uhrzeit"])
    return render(request, "leadmanagement/info_termine.html", aktiv="/lead-management",
                  termine=lead_info.termine_liste(session), parameter=p,
                  wochentag_name=["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag",
                                  "Samstag", "Sonntag"][p["wochentag"]],
                  kontrolle=[(t, v, lead_info.ist_feiertag(t.date() - timedelta(days=7)) if v else "")
                             for t, v in kontrolle],
                  feiertage=sorted(lead_info.feiertage_nrw(heute.year).items()),
                  jahr=heute.year,
                  meldung=request.query_params.get("meldung", ""),
                  fehler=request.query_params.get("fehler", "") == "1", **_badge(session))


@router.get("/info-veranstaltung/termine")
def info_termine(request: Request, session: Session = Depends(get_session)):
    """Liste aller Veranstaltungen (kommend + archiviert) mit Zählern, Notiz,
    manuell verschieben/archivieren/anlegen; Parameter info_* nur anzeigen
    (Pflege in Parametrierung → Lead-Einstellungen)."""
    _pflege_gate(request, session)
    return _termine_seite(request, session)


@router.post("/info-veranstaltung/termine")
def info_termine_speichern(request: Request, session: Session = Depends(get_session)):
    """aktion = notiz | verschieben | archiv | anlegen | nachlegen (+ id, notiz,
    beginn, archiviert, ort)."""
    _pflege_gate(request, session)
    benutzer = request.state.benutzer
    form = anfrage.formular(request)
    aktion = (form.get("aktion") or "").strip()
    v = None
    if str(form.get("id") or "").isdigit():
        v = session.get(InfoVeranstaltung, int(form.get("id")))
    meldung, fehler = "", False
    if aktion == "nachlegen":
        neu = lead_info.veranstaltungen_anlegen(session)
        meldung = f"{neu} Veranstaltung(en) nachgelegt." if neu else "Alle Regeltermine sind bereits angelegt."
    elif aktion == "anlegen":
        beginn = lead_info.zeitpunkt_lesen(form.get("beginn"))
        neu, fehlertext = lead_info.veranstaltung_anlegen_manuell(
            session, beginn, (form.get("ort") or "").strip(), benutzer=benutzer)
        if fehlertext:
            meldung, fehler = fehlertext, True
        else:
            meldung = f"Veranstaltung {lead_info.titel(neu)} angelegt."
    elif v is None:
        meldung, fehler = "Veranstaltung nicht gefunden.", True
    elif aktion == "notiz":
        v.notiz = (form.get("notiz") or "").strip()[:4000]
        meldung = f"Notiz zu {lead_info.titel(v)} gespeichert."
    elif aktion == "verschieben":
        fehlertext = lead_info.veranstaltung_verschieben(
            session, v, lead_info.zeitpunkt_lesen(form.get("beginn")), benutzer=benutzer)
        if fehlertext:
            meldung, fehler = fehlertext, True
        else:
            meldung = f"Veranstaltung verschoben auf {lead_info.titel(v)} (Leads bleiben zugeordnet)."
    elif aktion == "archiv":
        v.archiviert = (form.get("archiviert") or "") in ("1", "on", "true")
        meldung = (f"{lead_info.titel(v)} archiviert." if v.archiviert
                   else f"{lead_info.titel(v)} wieder aktiv.")
    else:
        meldung, fehler = "Unbekannte Aktion.", True
    if fehler:
        session.rollback()
    else:
        session.commit()
    return RedirectResponse(_mit_meldung(TERMINE_PFAD, meldung, fehler=fehler), status_code=303)
