# Lead-Management V2 (v23) – Router boards (PLAN_LEAD_V2 Phase 105): Hauptboard,
# Board Terminiert (Tabelle A3 mit Gruppen H4/H5), Kanban nur für das aktive
# Board, Inline-Bearbeitung per fetch, Sammelaktionen (H3), Spaltenkonfiguration
# je Nutzer (A-14), Reiter Kontaktiert (H7, Rufnummernsuche D3) und der
# Modul-Einstieg zu den E-Mail-Vorlagen (H8). Eigener Router mit demselben
# Präfix; in app/main.py VOR dem V1-Router eingebunden, damit gleiche Pfade
# (GET /board) hier Vorrang haben. Jede Route läuft über lead_v2.gate (404).

import json
from datetime import datetime
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import lead_boards, lead_v2
from app import leadmanagement as kern
from app.db import SessionLocal, get_session
from app.models import Benutzer, Vorgang, LEAD_PHASEN_NAMEN
from app.templating import render, templates

router = APIRouter(prefix="/lead-management")


# --- Jinja-Globals: Icon-Leiste (_nav.html) läuft ohne Kontext ---------------------------

def lm_demo_badge() -> dict:
    """Demo-Badge zentral in der Icon-Leiste: Parameter lead_freigabe_modus +
    demo_badge_text (eigene kurze Sitzung, da Makros keinen Request-Kontext
    haben). Fehler blenden den Badge aus, nie die Seite."""
    sitzung = SessionLocal()
    try:
        return {"aktiv": kern.demo_aktiv(sitzung),
                "text": kern.parameter_holen(sitzung, "demo_badge_text", "Demo · Coming soon")}
    except Exception:
        return {"aktiv": False, "text": ""}
    finally:
        sitzung.close()


templates.env.globals.setdefault("lm_demo_badge", lm_demo_badge)
templates.env.globals.setdefault("lm_initialen", lead_boards.initialen)
templates.env.globals.setdefault("lm_avatar_farbe", lead_boards.avatar_farbe)


def _json_gewuenscht(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "")


def _badge(session: Session) -> dict:
    return {"demo_badge": kern.demo_aktiv(session),
            "badge_text": kern.parameter_holen(session, "demo_badge_text", "Demo · Coming soon")}


def _tabellen_kontext(session: Session, benutzer, board: str) -> dict:
    listen = lead_boards.auswahl_listen(session)
    hv = lead_v2.ist_handelsvertreter(session, benutzer)
    jetzt = datetime.now()
    return {
        "board": board, "jetzt": jetzt, "heute": jetzt.date(), "hv": hv,
        "sammel": not hv and benutzer is not None and benutzer.rolle != "aussendienst",
        "erzwingen": benutzer is not None and benutzer.rolle in ("admin", "innendienst"),
        "versuche_max": kern.versuche_max(session),
        **listen,
    }


def _zeile_html(z: dict, spalten: list, ctx: dict) -> str:
    modul = templates.env.get_template("leadmanagement/_tabelle.html").module
    return str(modul.lead_zeile(z, spalten, ctx))


# --- Boards als Tabelle -----------------------------------------------------------------

def _board_seite(request: Request, session: Session, board: str):
    lead_v2.gate(request, session)
    benutzer = request.state.benutzer
    f = lead_boards.filter_aus_query(request.query_params)
    daten = lead_boards.board_zeilen(session, benutzer, board, f)
    ctx = _tabellen_kontext(session, benutzer, board)
    return render(request, "leadmanagement/hauptboard.html" if board == "hauptboard"
                  else "leadmanagement/terminiert.html",
                  aktiv="/lead-management", board=board, board_info=lead_boards.BOARDS[board],
                  gruppen=daten["gruppen"], anzahl=daten["anzahl"], filter_werte=f,
                  spalten=lead_boards.spalten_fuer(session, benutzer.id, board),
                  sammelaktionen=lead_boards.sammelaktionen_fuer(board), ctx=ctx,
                  phasen_namen=LEAD_PHASEN_NAMEN, jetzt=daten["jetzt"],
                  meldung=request.query_params.get("meldung", ""),
                  fehler=request.query_params.get("fehler", "") == "1", **_badge(session))


@router.get("/hauptboard")
async def hauptboard(request: Request, session: Session = Depends(get_session)):
    """H4: Leads ohne Vor-Ort-Termin – Gruppen Neu · Pausiert · Disqualifiziert."""
    return _board_seite(request, session, "hauptboard")


@router.get("/terminiert")
async def terminiert(request: Request, session: Session = Depends(get_session)):
    """H5: Leads mit Vor-Ort-Termin – Angebotserstellung · Angebotsversand ·
    Gewonnen · Verloren."""
    return _board_seite(request, session, "terminiert")


# --- Kanban: nur das aktive Board (übernimmt GET /board vom V1-Router) ------------------

KANBAN_SPALTEN = {"hauptboard": ["neu", "in_kontaktierung", "qualifiziert"],
                  "terminiert": ["terminiert", "erfasst", "angebot", "gewonnen"]}


@router.get("/board")
async def board_kanban(request: Request, session: Session = Depends(get_session)):
    lead_v2.gate(request, session)
    from app import leadmanagement_logik
    benutzer = request.state.benutzer
    board = request.query_params.get("board", "hauptboard")
    if board not in KANBAN_SPALTEN:
        board = "hauptboard"

    def _datum(name):
        wert = request.query_params.get(name, "")
        try:
            return datetime.strptime(wert, "%Y-%m-%d") if wert else None
        except ValueError:
            return None
    filter_werte = {
        "meine": request.query_params.get("meine", "0") == "1",
        "quelle_id": request.query_params.get("quelle_id", ""),
        "sparte": request.query_params.get("sparte", ""),
        "klasse": request.query_params.get("klasse", ""),
        "plz": request.query_params.get("plz", ""),
        "q": request.query_params.get("q", ""),
        "eingang_von": _datum("eingang_von"),
        "eingang_bis": _datum("eingang_bis"),
        "seiten": request.query_params.get("seiten", "") == "1" and board == "hauptboard",
        "board": board,
    }
    daten = kern.board_daten(session, benutzer, filter_werte)
    spalten = daten["spalten"]
    if lead_v2.ist_handelsvertreter(session, benutzer):
        spalten = {p: [k for k in karten if k["vorgang"].ad_id == benutzer.id]
                   for p, karten in spalten.items()}
    koepfe = {p: {"anzahl": len(k), "summe": daten["koepfe"][p]["summe"] if p in daten["koepfe"] else None}
              for p, k in spalten.items()}
    logik = leadmanagement_logik.hole_logik()
    from app.models import LeadQuelle
    quellen = (session.query(LeadQuelle).filter(LeadQuelle.aktiv.is_(True))
               .order_by(LeadQuelle.name).all())
    return render(request, "leadmanagement/board.html",
                  aktiv="/lead-management", spalten=spalten, koepfe=koepfe,
                  filter_werte=filter_werte, quellen=quellen, board=board,
                  board_info=lead_boards.BOARDS[board],
                  spalten_reihenfolge=KANBAN_SPALTEN[board],
                  seiten_phasen=kern.SEITEN_PHASEN if board == "hauptboard" else (),
                  phasen_namen=LEAD_PHASEN_NAMEN,
                  unq_gruende=logik.gruende_der_phase("unqualifiziert"),
                  zurueck_gruende=logik.gruende_der_phase("zurueckgestellt"),
                  meldung=request.query_params.get("meldung", ""), **_badge(session))


# --- Inline-Bearbeitung (fetch, JSON) ----------------------------------------------------

@router.post("/boards/zeile/{vorgang_id}")
async def zeile_aendern(request: Request, vorgang_id: int,
                        session: Session = Depends(get_session)):
    """JSON {feld, wert, grund?, grund_text?, bis?, board?} → {ok, meldung,
    zeile_html?}. Felder: status, notiz, ad_id, leadmanager_id, wiedervorlage."""
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        raise HTTPException(status_code=404)
    lead_v2.gate(request, session, vorgang)
    benutzer = request.state.benutzer
    try:
        daten = await request.json()
    except Exception:
        form = await request.form()
        daten = dict(form)
    if not isinstance(daten, dict):
        return JSONResponse({"ok": False, "meldung": "Ungültige Anfrage."}, status_code=400)
    ok, meldung = lead_boards.zeile_aendern(session, vorgang, daten.get("feld", ""),
                                            daten.get("wert"), benutzer=benutzer, daten=daten)
    if ok:
        session.commit()
    else:
        session.rollback()
    antwort = {"ok": ok, "meldung": meldung, "phase": vorgang.lead_phase}
    board = daten.get("board") or "hauptboard"
    try:
        z = lead_boards.zeile_fuer(session, benutzer, vorgang)
        if z is not None:
            antwort["board"] = z["board"]
            antwort["gruppe"] = z["gruppe"]
            if z["board"] == board:
                antwort["zeile_html"] = _zeile_html(
                    z, lead_boards.spalten_fuer(session, benutzer.id, board),
                    _tabellen_kontext(session, benutzer, board))
            else:
                antwort["verschoben"] = (f"Lead liegt jetzt im Board "
                                         f"„{lead_boards.BOARDS[z['board']]['titel']}“ · "
                                         f"{lead_boards.GRUPPEN_NAMEN[z['gruppe']]}")
        else:
            antwort["verschoben"] = "Lead ist in keiner Gruppe mehr sichtbar."
    except Exception:
        pass
    return JSONResponse(antwort, status_code=200 if ok else 422)


# --- Sammelaktionen (H3) -------------------------------------------------------------------

@router.post("/boards/sammelaktion")
async def sammelaktion(request: Request, session: Session = Depends(get_session)):
    """ids[] + aktion + board + Parameter (status, grund, grund_text, bis);
    Formular → Redirect mit Meldung, Accept application/json → JSON."""
    lead_v2.gate(request, session)
    benutzer = request.state.benutzer
    if "application/json" in (request.headers.get("content-type") or ""):
        daten = await request.json()
        ids = daten.get("ids") or []
        params = {k: v for k, v in daten.items() if k not in ("ids",)}
    else:
        form = await request.form()
        ids = form.getlist("ids") or form.getlist("ids[]")
        params = {k: form.get(k) for k in form.keys() if k not in ("ids", "ids[]")}
    board = (params.get("board") or "hauptboard").strip()
    aktion = (params.get("aktion") or "").strip()
    ok, meldung = lead_boards.sammelaktion_ausfuehren(session, benutzer, board, aktion, ids, params)
    if ok:
        session.commit()
    else:
        session.rollback()
    if _json_gewuenscht(request):
        return JSONResponse({"ok": ok, "meldung": meldung}, status_code=200 if ok else 422)
    ziel = f"/lead-management/{board if board in lead_boards.BOARDS else 'hauptboard'}"
    return RedirectResponse(f"{ziel}?meldung={quote_plus(meldung)}"
                            + ("" if ok else "&fehler=1"), status_code=303)


# --- Spaltenkonfiguration je Nutzer (A-14) ---------------------------------------------------

@router.get("/boards/spalten")
async def spalten_holen(request: Request, session: Session = Depends(get_session)):
    lead_v2.gate(request, session)
    board = request.query_params.get("board", "hauptboard")
    if board not in lead_boards.BOARDS:
        board = "hauptboard"
    return JSONResponse({"board": board,
                         "spalten": lead_boards.spalten_fuer(session, request.state.benutzer.id, board)})


@router.post("/boards/spalten")
async def spalten_speichern(request: Request, session: Session = Depends(get_session)):
    """JSON {board, spalten: [{key, sichtbar}] in Reihenfolge} → gespeicherte Liste."""
    lead_v2.gate(request, session)
    try:
        daten = await request.json()
    except Exception:
        form = await request.form()
        try:
            daten = json.loads(form.get("daten") or "{}")
        except ValueError:
            daten = {}
    if not isinstance(daten, dict):
        return JSONResponse({"ok": False, "meldung": "Ungültige Anfrage."}, status_code=400)
    board = daten.get("board") or "hauptboard"
    if board not in lead_boards.BOARDS:
        return JSONResponse({"ok": False, "meldung": "Unbekanntes Board."}, status_code=400)
    liste = daten.get("spalten")
    if daten.get("zuruecksetzen"):
        liste = []
    if not isinstance(liste, list):
        # kein stilles Zurücksetzen der Nutzerkonfiguration bei kaputten Daten
        return JSONResponse({"ok": False, "meldung": "Spaltenliste fehlt oder ist ungültig."},
                            status_code=400)
    spalten = lead_boards.spalten_speichern(session, request.state.benutzer.id, board, liste)
    session.commit()
    return JSONResponse({"ok": True, "board": board, "spalten": spalten,
                         "meldung": "Spalten gespeichert."})


# --- Reiter Kontaktiert (H7) ----------------------------------------------------------------

@router.get("/kontaktiert")
async def kontaktiert(request: Request, session: Session = Depends(get_session)):
    lead_v2.gate(request, session)
    q = request.query_params
    try:
        seite = int(q.get("seite", "1"))
    except ValueError:
        seite = 1
    daten = lead_boards.kontaktiert_daten(session, request.state.benutzer,
                                          q.get("q", ""), q.get("telefon", ""), seite)
    return render(request, "leadmanagement/kontaktiert.html", aktiv="/lead-management",
                  **daten, phasen_namen=LEAD_PHASEN_NAMEN,
                  meldung=q.get("meldung", ""), **_badge(session))


# --- E-Mail-Vorlagen im Modul (H8) -----------------------------------------------------------

def _vorlagen_pflege_erlaubt(benutzer) -> bool:
    """Rechte wie heute: Admin/Innendienst pflegen; Hauptrolle leadmanagement
    (und alle anderen) nur lesen."""
    return benutzer is not None and benutzer.rolle in ("admin", "innendienst")


def _vorlagen_gate(request: Request, session: Session) -> None:
    lead_v2.gate(request, session)
    # Handelsvertreter haben keinen Zugriff auf die Vorlagenpflege
    if lead_v2.ist_handelsvertreter(session, request.state.benutzer):
        raise HTTPException(status_code=404)


@router.get("/vorlagen")
async def vorlagen(request: Request, session: Session = Depends(get_session)):
    """Bestehender Lead-Vorlagen-Editor (Parametrierung) im Modul: gleiche
    Schlüssel/Ablage (lead_vorlage_<key>[_<Sparte>]_betreff/_text)."""
    from app import lead_mail, leadmanagement_logik
    _vorlagen_gate(request, session)
    schluessel = request.query_params.get("vorlage", "eingangsbestaetigung")
    if schluessel not in lead_mail.VORLAGEN_START:
        schluessel = "eingangsbestaetigung"
    sparte = request.query_params.get("sparte", "")
    if sparte not in leadmanagement_logik.SPARTEN:
        sparte = ""
    betreff, text = lead_mail.vorlage_laden(session, schluessel, sparte)
    return render(request, "leadmanagement/vorlagen.html", aktiv="/lead-management",
                  vorlagen=lead_mail.VORLAGEN_START, schluessel=schluessel, sparte=sparte,
                  sparten=leadmanagement_logik.SPARTEN, betreff=betreff, text=text,
                  platzhalter=lead_mail.PLATZHALTER_NEU,
                  pflege=_vorlagen_pflege_erlaubt(request.state.benutzer),
                  meldung=request.query_params.get("meldung", ""),
                  fehler=request.query_params.get("fehler", "") == "1", **_badge(session))


@router.post("/vorlagen")
async def vorlagen_speichern(request: Request, session: Session = Depends(get_session)):
    from app import lead_mail, leadmanagement_logik
    from app.models import einstellung_setzen
    _vorlagen_gate(request, session)
    form = await request.form()
    schluessel = form.get("vorlage") or ""
    if schluessel not in lead_mail.VORLAGEN_START:
        return RedirectResponse("/lead-management/vorlagen", status_code=303)
    zurueck = f"/lead-management/vorlagen?vorlage={schluessel}"
    if not _vorlagen_pflege_erlaubt(request.state.benutzer):
        return RedirectResponse(zurueck + "&fehler=1&meldung="
                                + quote_plus("Vorlagen pflegen dürfen Admin und Innendienst – "
                                             "für Sie ist die Ansicht nur lesend."),
                                status_code=303)
    sparte = form.get("sparte") if form.get("sparte") in leadmanagement_logik.SPARTEN else ""
    zusatz = f"_{sparte}" if sparte else ""
    betreff = (form.get("betreff") or "").strip()
    text = (form.get("text") or "").strip()
    if form.get("aktion") == "entfernen" and sparte:
        einstellung_setzen(session, f"lead_vorlage_{schluessel}{zusatz}_betreff", "")
        einstellung_setzen(session, f"lead_vorlage_{schluessel}{zusatz}_text", "")
        session.commit()
        return RedirectResponse(zurueck + "&meldung=Sparten-Vorlage+entfernt", status_code=303)
    if not betreff or not text:
        return RedirectResponse(zurueck + (f"&sparte={sparte}" if sparte else "")
                                + "&fehler=1&meldung=Betreff+und+Text+sind+Pflicht", status_code=303)
    einstellung_setzen(session, f"lead_vorlage_{schluessel}{zusatz}_betreff", betreff)
    einstellung_setzen(session, f"lead_vorlage_{schluessel}{zusatz}_text", text)
    session.commit()
    return RedirectResponse(zurueck + (f"&sparte={sparte}" if sparte else "")
                            + "&meldung=Gespeichert", status_code=303)
