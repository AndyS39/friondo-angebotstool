# Lead-Management V2 (v23) – Router boards (PLAN_LEAD_V2 Phase 105): Hauptboard,
# Board Deals (Key terminiert; Tabelle A3 mit Gruppen H4/H5), Kanban nur für das
# aktive Board, Inline-Bearbeitung per fetch, Sammelaktionen (H3), Spalten-
# konfiguration je Nutzer (A-14), Reiter Kontaktiert (H7, Rufnummernsuche D3)
# und der Modul-Einstieg zu den E-Mail-Vorlagen (H8). Eigener Router mit
# demselben Präfix; in app/main.py VOR dem V1-Router eingebunden, damit gleiche
# Pfade (GET /board) hier Vorrang haben. Jede Route läuft über lead_v2.gate (404).
# v25 (PLAN_LEAD_V3 Phase 118): Board-Namen über lead_boards.board_label,
# Phasen-Labels aus dem Blatt Status, Kanban-Spalte „Kontaktiert“ (in_kontaktierung
# + qualifiziert), Score nur bei lead_v2.score_aktiv, Spaltenkonfiguration mit
# Umbenennen/Sortierung/Zurücksetzen (GET/POST /boards/spalten).

import json
from datetime import datetime
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import lead_boards, lead_v2
from app import leadmanagement as kern
from app.db import SessionLocal, get_session
from app.models import Benutzer, Vorgang
from app.templating import render, templates
from app import anfrage   # v27: Formular/JSON in def-Routen

router = APIRouter(prefix="/lead-management")


# --- Jinja-Globals: Icon-Leiste (_nav.html) läuft ohne Kontext ---------------------------

def lm_demo_badge() -> dict:
    """Demo-Badge zentral in der Icon-Leiste: Parameter lead_freigabe_modus +
    demo_badge_text. v27 (Befund B7 der Inventur): den Wert liefert die
    RollenMiddleware über anfrage.KONTEXT (gelesen mit ihrer Sitzung) – keine
    zweite Verbindung je Lead-Seite mehr; die eigene kurze Sitzung bleibt nur
    als Rückfallweg (Rendern ohne Middleware, z. B. in Tests). Fehler blenden
    den Badge aus, nie die Seite."""
    aus_kontext = anfrage.kontext_wert("lm_demo_badge")
    if aus_kontext is not None:
        return aus_kontext
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
# v25: Board-Anzeigenamen (Hauptboard / Deals) und Kundenname für Makros ohne Kontext
templates.env.globals.setdefault("lm_board_label", lead_boards.board_label)
templates.env.globals.setdefault("lm_kundenname", lead_boards.kundenname)


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
        "score_aktiv": lead_v2.score_aktiv(session),
        "sortierung": lead_boards.sortierung_fuer(session, benutzer, board),
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
    f["sort"] = lead_boards.sortierung_fuer(session, benutzer, board)     # v25: gemerkt
    daten = lead_boards.board_zeilen(session, benutzer, board, f)
    ctx = _tabellen_kontext(session, benutzer, board)
    return render(request, "leadmanagement/hauptboard.html" if board == "hauptboard"
                  else "leadmanagement/terminiert.html",
                  aktiv="/lead-management", board=board, board_info=lead_boards.board_info(board),
                  gruppen=daten["gruppen"], anzahl=daten["anzahl"], filter_werte=f,
                  spalten=lead_boards.spalten_fuer(session, benutzer, board),
                  sortierung=f["sort"], score_aktiv=ctx["score_aktiv"],
                  sammelaktionen=lead_boards.sammelaktionen_fuer(board), ctx=ctx,
                  # v29 (Phase 140): Ziele der Sammelaktion „An Handelsvertreter verschieben“
                  hv_gruppen_wahl=lead_v2.hv_gruppen_wahl(session) if ctx["sammel"] else [],
                  phasen_namen=lead_boards.phasen_labels(), jetzt=daten["jetzt"],
                  meldung=request.query_params.get("meldung", ""),
                  fehler=request.query_params.get("fehler", "") == "1", **_badge(session))


@router.get("/hauptboard")
def hauptboard(request: Request, session: Session = Depends(get_session)):
    """H4: Leads ohne Vor-Ort-Termin – Gruppen Neu · Pausiert · Disqualifiziert."""
    return _board_seite(request, session, "hauptboard")


@router.get("/boards/haupt")
def hauptboard_alias(request: Request, session: Session = Depends(get_session)):
    """v25: Pfad aus PLAN_LEAD_V3 (Phase 118) – Weiterleitung auf das bestehende
    /lead-management/hauptboard (Pfad bleibt, kein Einstieg geht verloren)."""
    lead_v2.gate(request, session)
    ziel = "/lead-management/hauptboard"
    if request.url.query:
        ziel += "?" + request.url.query
    return RedirectResponse(ziel, status_code=303)


@router.get("/terminiert")
def terminiert(request: Request, session: Session = Depends(get_session)):
    """H5: Board Deals (Key terminiert) – Leads mit Vor-Ort-Termin:
    Angebotserstellung · Angebotsversand · Gewonnen · Verloren."""
    return _board_seite(request, session, "terminiert")


# --- Kanban: nur das aktive Board (übernimmt GET /board vom V1-Router) ------------------

# v25: Anzeige-Spalte „kontaktiert“ fasst in_kontaktierung + qualifiziert zusammen
# (interne Phasen bleiben, kern.board_daten liefert sie weiter getrennt).
KANBAN_SPALTEN = {"hauptboard": ["neu", "kontaktiert"],
                  "terminiert": ["terminiert", "erfasst", "angebot", "gewonnen"]}
KANBAN_ZUSAMMEN = {"kontaktiert": ("in_kontaktierung", "qualifiziert")}


def kanban_spalten_zusammenfassen(spalten: dict, koepfe: dict) -> tuple[dict, dict]:
    """Phasen-Karten zu Anzeige-Spalten zusammenfassen (Kontaktiert); Karten
    nach Eingang neueste zuerst, Zähler summiert, Summe nur wenn vorhanden."""
    spalten = dict(spalten)
    koepfe = dict(koepfe)
    for ziel, phasen in KANBAN_ZUSAMMEN.items():
        karten = [k for p in phasen for k in spalten.get(p, [])]
        karten.sort(key=lambda k: (k["vorgang"].eingang_am or k["vorgang"].angelegt_am
                                   or datetime.min), reverse=True)
        summen = [koepfe[p]["summe"] for p in phasen if p in koepfe and koepfe[p].get("summe") is not None]
        spalten[ziel] = karten
        koepfe[ziel] = {"anzahl": len(karten), "summe": sum(summen) if summen else None}
    return spalten, koepfe


@router.get("/board")
def board_kanban(request: Request, session: Session = Depends(get_session)):
    lead_v2.gate(request, session)
    from app import leadmanagement_logik
    benutzer = request.state.benutzer
    board = request.query_params.get("board", "hauptboard")
    if board not in KANBAN_SPALTEN:
        board = "hauptboard"
    score_aktiv = lead_v2.score_aktiv(session)

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
        # Score-Klasse nur filterbar, wenn das Scoring aktiv ist (v25)
        "klasse": request.query_params.get("klasse", "") if score_aktiv else "",
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
    spalten, koepfe = kanban_spalten_zusammenfassen(spalten, koepfe)
    logik = leadmanagement_logik.hole_logik()
    # Phasen-Labels ausschließlich aus dem Blatt Status; die Sammelspalte trägt
    # das Label ihrer ersten Phase („Kontaktiert“)
    phasen_namen = lead_boards.phasen_labels(logik)
    for ziel, phasen in KANBAN_ZUSAMMEN.items():
        phasen_namen[ziel] = phasen_namen.get(phasen[0], ziel)
    from app.models import LeadQuelle
    quellen = (session.query(LeadQuelle).filter(LeadQuelle.aktiv.is_(True))
               .order_by(LeadQuelle.name).all())
    return render(request, "leadmanagement/board.html",
                  aktiv="/lead-management", spalten=spalten, koepfe=koepfe,
                  filter_werte=filter_werte, quellen=quellen, board=board,
                  board_info=lead_boards.board_info(board), score_aktiv=score_aktiv,
                  spalten_reihenfolge=KANBAN_SPALTEN[board],
                  seiten_phasen=kern.SEITEN_PHASEN if board == "hauptboard" else (),
                  phasen_namen=phasen_namen,
                  unq_gruende=logik.gruende_der_phase("unqualifiziert"),
                  zurueck_gruende=logik.gruende_der_phase("zurueckgestellt"),
                  meldung=request.query_params.get("meldung", ""), **_badge(session))


# --- Inline-Bearbeitung (fetch, JSON) ----------------------------------------------------

@router.post("/boards/zeile/{vorgang_id}")
def zeile_aendern(request: Request, vorgang_id: int,
                        session: Session = Depends(get_session)):
    """JSON {feld, wert, grund?, grund_text?, bis?, board?} → {ok, meldung,
    zeile_html?}. Felder: status, notiz, ad_id, leadmanager_id, wiedervorlage."""
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        raise HTTPException(status_code=404)
    lead_v2.gate(request, session, vorgang)
    benutzer = request.state.benutzer
    try:
        daten = anfrage.json_lesen(request)
    except Exception:
        form = anfrage.formular(request)
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
                    z, lead_boards.spalten_fuer(session, benutzer, board),
                    _tabellen_kontext(session, benutzer, board))
            else:
                antwort["verschoben"] = (f"Lead liegt jetzt im Board "
                                         f"„{lead_boards.board_label(z['board'])}“ · "
                                         f"{lead_boards.GRUPPEN_NAMEN[z['gruppe']]}")
        else:
            antwort["verschoben"] = "Lead ist in keiner Gruppe mehr sichtbar."
    except Exception:
        pass
    return JSONResponse(antwort, status_code=200 if ok else 422)


# --- Sammelaktionen (H3) -------------------------------------------------------------------

@router.post("/boards/sammelaktion")
def sammelaktion(request: Request, session: Session = Depends(get_session)):
    """ids[] + aktion + board + Parameter (status, grund, grund_text, bis);
    Formular → Redirect mit Meldung, Accept application/json → JSON."""
    lead_v2.gate(request, session)
    benutzer = request.state.benutzer
    if "application/json" in (request.headers.get("content-type") or ""):
        daten = anfrage.json_lesen(request)
        ids = daten.get("ids") or []
        params = {k: v for k, v in daten.items() if k not in ("ids",)}
    else:
        form = anfrage.formular(request)
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


# --- Spaltenkonfiguration je Nutzer (A-14, v25 erweitert) ------------------------------------

@router.get("/boards/spalten")
def spalten_holen(request: Request, session: Session = Depends(get_session)):
    """{board, spalten: [{key, titel, standard, name, sichtbar}], sort: {key, richtung} | null}"""
    lead_v2.gate(request, session)
    board = request.query_params.get("board", "hauptboard")
    if board not in lead_boards.KONFIG_BOARDS:
        board = "hauptboard"
    benutzer = request.state.benutzer
    return JSONResponse({"board": board,
                         "spalten": lead_boards.spalten_fuer(session, benutzer, board),
                         "sort": lead_boards.sortierung_fuer(session, benutzer, board)})


@router.post("/boards/spalten")
def spalten_speichern(request: Request, session: Session = Depends(get_session)):
    """JSON {board, spalten?: [{key, sichtbar, name?}] in Reihenfolge,
    sort?: {key, richtung: auf|ab} | null, umbenennen?: {key, name} (leer =
    Standard), zuruecksetzen?: true} → gespeicherte Liste + Sortierung. Gilt
    nur für den angemeldeten Nutzer. Mindestens eine Angabe ist Pflicht;
    kaputte Daten setzen die Konfiguration nie still zurück."""
    lead_v2.gate(request, session)
    try:
        daten = anfrage.json_lesen(request)
    except Exception:
        form = anfrage.formular(request)
        try:
            daten = json.loads(form.get("daten") or "{}")
        except ValueError:
            daten = {}
    if not isinstance(daten, dict):
        return JSONResponse({"ok": False, "meldung": "Ungültige Anfrage."}, status_code=400)
    board = daten.get("board") or "hauptboard"
    if board not in lead_boards.KONFIG_BOARDS:
        return JSONResponse({"ok": False, "meldung": "Unbekanntes Board."}, status_code=400)
    benutzer = request.state.benutzer
    zuruecksetzen = bool(daten.get("zuruecksetzen"))
    liste = daten.get("spalten", lead_boards._BEHALTEN)
    sort = daten.get("sort", lead_boards._BEHALTEN) if "sort" in daten else lead_boards._BEHALTEN
    umbenennen = daten.get("umbenennen")
    # v29 (Phase 141): Spaltenbreite je Nutzer – {breite: {key, px}} (px leer/null = Standard)
    breite = daten.get("breite")
    if breite is not None and not (isinstance(breite, dict) and breite.get("key")):
        return JSONResponse({"ok": False, "meldung": "Breite braucht einen Spalten-Key."},
                            status_code=400)
    if zuruecksetzen:
        liste = []
        sort, umbenennen, breite = lead_boards._BEHALTEN, None, None
    if liste is not lead_boards._BEHALTEN and not isinstance(liste, list):
        return JSONResponse({"ok": False, "meldung": "Spaltenliste fehlt oder ist ungültig."},
                            status_code=400)
    if sort is not lead_boards._BEHALTEN and sort is not None and not (
            isinstance(sort, dict) and sort.get("key")):
        return JSONResponse({"ok": False, "meldung": "Sortierung ist ungültig."}, status_code=400)
    if umbenennen is not None and not (isinstance(umbenennen, dict) and umbenennen.get("key")):
        return JSONResponse({"ok": False, "meldung": "Umbenennen braucht einen Spalten-Key."},
                            status_code=400)
    if (liste is lead_boards._BEHALTEN and sort is lead_boards._BEHALTEN
            and umbenennen is None and breite is None and not zuruecksetzen):
        return JSONResponse({"ok": False, "meldung": "Spaltenliste fehlt oder ist ungültig."},
                            status_code=400)
    spalten = lead_boards.spalten_speichern(
        session, benutzer, board, liste=liste, sort=sort,
        umbenennen=(umbenennen["key"], umbenennen.get("name", "")) if umbenennen else None,
        zuruecksetzen=zuruecksetzen,
        breite=(breite["key"], breite.get("px")) if breite else None)
    session.commit()
    meldung = ("Spalten zurückgesetzt." if zuruecksetzen
               else ("Spaltenbreite gespeichert." if breite.get("px") else "Standardbreite.")
               if breite and liste is lead_boards._BEHALTEN
               else "Spalte umbenannt." if umbenennen and liste is lead_boards._BEHALTEN
               else "Sortierung gemerkt." if sort is not lead_boards._BEHALTEN and liste is lead_boards._BEHALTEN
               else "Spalten gespeichert.")
    return JSONResponse({"ok": True, "board": board, "spalten": spalten,
                         "sort": lead_boards.sortierung_fuer(session, benutzer, board),
                         "meldung": meldung})


# --- Reiter Kontaktiert (H7) ----------------------------------------------------------------

@router.get("/kontaktiert")
def kontaktiert(request: Request, session: Session = Depends(get_session)):
    lead_v2.gate(request, session)
    q = request.query_params
    try:
        seite = int(q.get("seite", "1"))
    except ValueError:
        seite = 1
    daten = lead_boards.kontaktiert_daten(session, request.state.benutzer,
                                          q.get("q", ""), q.get("telefon", ""), seite)
    # v25: Phasen-Labels nur aus dem Blatt Status (beide Kontakt-Phasen „Kontaktiert“)
    return render(request, "leadmanagement/kontaktiert.html", aktiv="/lead-management",
                  **daten, phasen_namen=lead_boards.phasen_labels(),
                  score_aktiv=lead_v2.score_aktiv(session),
                  meldung=q.get("meldung", ""), **_badge(session))


# --- E-Mail-Vorlagen im Modul --------------------------------------------------------------
# v29 (PLAN_LEAD_V4 Phase 142): Der Vorlagen-Editor (Baum links, Terminbestätigung je
# Vertriebler) lebt in app/routers/lm_vorlagen.py; der v23-Editor (H8) ist entfernt.
