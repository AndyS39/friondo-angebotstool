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
# v35 (PLAN_LEAD_V6 Phase 186, Agent B): Inline-Bearbeitung mit Rechten je Zeile
# (lead_boards.bearbeiten_erlaubt → lead_v2.bearbeiten_erlaubt, Vertrag R) und
# Zeilen-Rendern auch für die Handelsvertreter-Ansicht (board=handelsvertreter),
# gespeicherte Filter (GET/POST /boards/filter, Standardfilter beim Öffnen über
# lead_boards.filter_query), Sofortsuche: ?fragment=1 liefert die Bereiche
# data-lm-sofort-ziel der Seite als JSON (lead_boards.fragment_ziele) für lm_sofort.js;
# „Kontaktiert“ mit einer Suchleiste (Rufnummer in q, telefon= bleibt als Alias).

import json
from datetime import datetime
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import lead_boards, lead_v2
from app import leadmanagement as kern
from app import sparten as sparten_modul   # v31 (Phase 157): Sparten-Listen der Filter
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
# v31 (PLAN_LEAD_V5 Phase 157): Sparten-Codes und Langnamen (inkl. MS/WA/DMS) für alle
# Filter-Selects, Häkchen und Badges der Modul-Templates – keine festen Listen mehr
templates.env.globals.setdefault("lm_sparten", tuple(sparten_modul.SPARTEN))
templates.env.globals.setdefault("lm_sparten_lang", dict(sparten_modul.SPARTEN_LANG))
# v37 (PLAN_LEAD_V7 Phase 199, Agent L3): Interessen-Häkchen inkl. Merkmal „PV vorhanden“ (PVV) für
# das Plus-Popover der Boards und den Filter „Sparte“ im Hauptboard/Deals; lm_sparten bleibt die
# Erfassungs-Liste (Kanban, Karte, Anrufliste, Statistik)
templates.env.globals.setdefault("lm_interessen", tuple(sparten_modul.INTERESSEN_ALLE))
templates.env.globals.setdefault("lm_interessen_lang", dict(sparten_modul.INTERESSEN_LANG))
templates.env.globals.setdefault("lm_interessen_merkmale", tuple(sparten_modul.INTERESSEN_MERKMALE))
# v33 (PLAN_V20 Phase 174): Speicher-Route der Spaltenwerkzeuge je Rolle (data-lm-spalten-url
# der Angebotstool-Tabellen; Projektierung → Alias /einstellungen/spalten)
templates.env.globals.setdefault("lm_spalten_url", lead_boards.spalten_url)
templates.env.globals.setdefault("lm_spalten_fest", lead_boards.spalten_fest)


def _speichern(session: Session, aktion, wiederholungen: int = 1):
    """v31 (v27-Regel): schreibende Sammelaktionen über mehrere Zeilen (Archivieren,
    Duplizieren, Wiederherstellen) – Rollback und eine Wiederholung bei „database is
    locked“ (Vorbild routers/angebote._speichern). Liefert das Ergebnis von aktion()."""
    import time

    from sqlalchemy.exc import OperationalError

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
        "sammel": not hv and benutzer is not None and benutzer.basisrolle != "aussendienst",
        "erzwingen": benutzer is not None and benutzer.basisrolle in ("admin", "innendienst"),
        "versuche_max": kern.versuche_max(session),
        "score_aktiv": lead_v2.score_aktiv(session),
        "sortierung": lead_boards.sortierung_fuer(session, benutzer, board),
        # v35 (Phase 186): Großkunde-Häkchen inline nur für Innendienst/Leadmanagement/Admin
        # (dieselbe Regel wie lead_kartei.feld_speichern)
        "grosskunde_setzbar": benutzer is not None and (
            benutzer.basisrolle in ("admin", "innendienst") or benutzer.hat_rolle("leadmanagement")),
        **listen,
    }


def _zeile_html(z: dict, spalten: list, ctx: dict) -> str:
    modul = templates.env.get_template("leadmanagement/_tabelle.html").module
    return str(modul.lead_zeile(z, spalten, ctx))


def _hv_zeile_html(session: Session, benutzer, vorgang: Vorgang, zurueck: str) -> str | None:
    """v35 (Phase 186): Zeile der Handelsvertreter-Ansicht neu rendern (Makro hv_zeile in
    leadmanagement/_hv_zeile.html) – Spalten je Nutzer unter dem Board-Key handelsvertreter."""
    from app import lead_handelsvertreter as hv_modul
    daten = lead_boards.hv_zeile_fuer(session, benutzer, vorgang)
    if daten is None:
        return None
    jetzt = datetime.now()
    ctx = {"nur_lesen": False, "board": "hauptboard", "jetzt": jetzt, "heute": jetzt.date(),
           "hv": not daten["gesamt"], "sammel": False, "versuche_max": kern.versuche_max(session),
           "sortierung": lead_boards.sortierung_fuer(session, benutzer, hv_modul.KONFIG_BOARD),
           **lead_boards.auswahl_listen(session)}
    spalten = lead_boards.spalten_fuer(session, benutzer, hv_modul.KONFIG_BOARD)
    modul = templates.env.get_template("leadmanagement/_hv_zeile.html").module
    return str(modul.hv_zeile(daten["zeile"], spalten, ctx, daten["hv_liste"], zurueck,
                              daten["gesamt"], daten["standard"], jetzt, True))


def fragment_antwort(antwort, **zusatz) -> JSONResponse:
    """v35 (Phase 186, Sofortsuche): aus der gerenderten Seite nur die Bereiche
    data-lm-sofort-ziel als JSON {ziele: {name: html}, …} – lm_sofort.js tauscht die Inhalte
    ohne Seitenneuladen; ohne Fragment-Unterstützung fällt das Skript auf die ganze Seite zurück."""
    html = antwort.body.decode("utf-8") if isinstance(antwort.body, bytes) else str(antwort.body)
    return JSONResponse({"ok": True, "ziele": lead_boards.fragment_ziele(html), **zusatz})


def fragment_gewuenscht(request: Request) -> bool:
    return request.query_params.get("fragment", "") == "1"


# --- Boards als Tabelle -----------------------------------------------------------------

def _board_seite(request: Request, session: Session, board: str):
    lead_v2.gate(request, session)
    benutzer = request.state.benutzer
    # v35 (Phase 186): Standardfilter des Nutzers beim Öffnen ohne Filterparameter
    query, aktiver_filter = lead_boards.filter_query(request.query_params, session, benutzer, board)
    f = lead_boards.filter_aus_query(query)
    f["sort"] = lead_boards.sortierung_fuer(session, benutzer, board)     # v25: gemerkt
    gruppen_zu: list = []
    if aktiver_filter is not None:
        werte = aktiver_filter.get("werte") or {}
        if isinstance(werte.get("sort"), dict) and werte["sort"].get("key"):
            f["sort"] = werte["sort"]
        gruppen_zu = list(werte.get("gruppen_zu") or [])
    daten = lead_boards.board_zeilen(session, benutzer, board, f)
    if gruppen_zu:
        for g in daten["gruppen"]:
            g["eingeklappt"] = g["key"] in gruppen_zu
    ctx = _tabellen_kontext(session, benutzer, board)
    ctx["archiv_sicht"] = bool(f.get("archiviert"))     # v31 (Phase 154): Filter-Chip „Archiv“
    # v31 (Phase 154): Ergebnis „Duplizieren“ mit Links auf die neuen Vorgänge (?kopien=1,2)
    kopien = [int(t) for t in (request.query_params.get("kopien") or "").split(",") if t.strip().isdigit()]
    antwort = render(request, "leadmanagement/hauptboard.html" if board == "hauptboard"
                     else "leadmanagement/terminiert.html",
                     aktiv="/lead-management", board=board, board_info=lead_boards.board_info(board),
                     gruppen=daten["gruppen"], anzahl=daten["anzahl"], filter_werte=f,
                     spalten=lead_boards.spalten_fuer(session, benutzer, board),
                     sortierung=f["sort"], score_aktiv=ctx["score_aktiv"],
                     sammelaktionen=lead_boards.sammelaktionen_fuer(board, archiv=ctx["archiv_sicht"]),
                     ctx=ctx, kopien=kopien,
                     # v29 (Phase 140): Ziele der Sammelaktion „An Handelsvertreter verschieben“
                     hv_gruppen_wahl=lead_v2.hv_gruppen_wahl(session) if ctx["sammel"] else [],
                     phasen_namen=lead_boards.phasen_labels(), jetzt=daten["jetzt"],
                     # v35 (Phase 186): gespeicherte Filter (Leiste), aktiver Standardfilter
                     filter_kontext=lead_boards.filter_kontext(session, benutzer, board),
                     aktiver_filter=aktiver_filter,
                     meldung=request.query_params.get("meldung", ""),
                     fehler=request.query_params.get("fehler", "") == "1", **_badge(session))
    if fragment_gewuenscht(request):
        return fragment_antwort(antwort, anzahl=daten["anzahl"],
                                gruppen={g["key"]: len(g["zeilen"]) for g in daten["gruppen"]})
    return antwort


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
        "grosskunde": request.query_params.get("grosskunde", "") == "1",   # v31 (Phase 153)
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
                  grosskunde_farbe=lead_boards.grosskunde_farbe(session),   # v31 (Phase 153)
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
    zeile_html?}. Felder: status, notiz, ad_id, leadmanager_id, wiedervorlage;
    v35 (Phase 186): interessen, kanal, grosskunde, objektart, telefon, email,
    teilgenommen – Rechte je Zeile über lead_boards.bearbeiten_erlaubt (Innendienst/
    Leadmanagement/Admin alle, Außendienst und Handelsvertreter nur eigene Leads: fremde
    Leads 404, lesbare ohne Bearbeitungsrecht 403); board=handelsvertreter liefert die Zeile
    der HV-Ansicht (Makro hv_zeile)."""
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        raise HTTPException(status_code=404)
    lead_v2.hv_umleitung(request, session)
    benutzer = request.state.benutzer
    if not lead_boards.bearbeiten_erlaubt(session, benutzer, vorgang):
        if lead_v2.zugriff_erlaubt(session, benutzer, vorgang):
            return JSONResponse({"ok": False, "meldung": "Diese Zeile dürfen Sie nur lesen."},
                                status_code=403)
        raise HTTPException(status_code=404)
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
        if board == "handelsvertreter":
            # v35 (Phase 186): Zeile der HV-Ansicht (Spalten je Nutzer + Vertreter-Spalte)
            zurueck = str(daten.get("zurueck") or "/lead-management/handelsvertreter")
            if not zurueck.startswith("/lead-management") or "//" in zurueck or "\n" in zurueck:
                zurueck = "/lead-management/handelsvertreter"
            html = _hv_zeile_html(session, benutzer, vorgang, zurueck)
            if html:
                antwort["board"] = "handelsvertreter"
                antwort["zeile_html"] = html
            else:
                antwort["verschoben"] = "Lead ist in der Handelsvertreter-Ansicht nicht mehr sichtbar."
            return JSONResponse(antwort, status_code=200 if ok else 422)
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


# --- v35 (PLAN_LEAD_V6 Phase 186): gespeicherte Filter je Nutzer und Board --------------------

@router.get("/boards/filter")
def filter_holen(request: Request, session: Session = Depends(get_session)):
    """{board, filter: [{id, name, werte, geteilt, von_name, standard, loeschbar}], standard_id,
    darf_freigeben} – eigene Filter plus die für alle freigegebenen (schreibgeschützt)."""
    board = request.query_params.get("board", "hauptboard")
    if not lead_boards.board_bekannt(board):
        board = "hauptboard"
    _spalten_gate(request, session, board)
    kontext = lead_boards.filter_kontext(session, request.state.benutzer, board)
    return JSONResponse({"ok": True, "board": board, "filter": kontext["liste"],
                         "standard_id": kontext["standard_id"],
                         "darf_freigeben": kontext["darf_freigeben"]})


@router.post("/boards/filter")
def filter_aendern(request: Request, session: Session = Depends(get_session)):
    """JSON {board, aktion: speichern | umbenennen | loeschen | standard | freigeben |
    freigabe_entfernen, id?, name?, werte?, standard?} → {ok, meldung, filter: [...],
    standard_id}. Nur für den angemeldeten Nutzer; „freigeben“ Innendienst/Admin."""
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
    board = str(daten.get("board") or "hauptboard")
    if not lead_boards.board_bekannt(board):
        return JSONResponse({"ok": False, "meldung": "Unbekanntes Board."}, status_code=400)
    _spalten_gate(request, session, board)
    benutzer = request.state.benutzer
    aktion = str(daten.get("aktion") or "speichern").strip()
    filter_id = str(daten.get("id") or "").strip() or None
    ok, meldung = False, "Unbekannte Aktion."
    if aktion == "speichern":
        eintrag, meldung = lead_boards.filter_speichern(
            session, benutzer, board, daten.get("name", ""), daten.get("werte") or {},
            standard=bool(daten.get("standard")), filter_id=filter_id)
        ok = eintrag is not None
    elif aktion == "umbenennen":
        ok, meldung = lead_boards.filter_umbenennen(session, benutzer, board, filter_id or "", daten.get("name", ""))
    elif aktion == "loeschen":
        ok, meldung = lead_boards.filter_loeschen(session, benutzer, board, filter_id or "")
    elif aktion == "standard":
        ok, meldung = lead_boards.filter_standard_setzen(session, benutzer, board, filter_id)
    elif aktion == "freigeben":
        ok, meldung = lead_boards.filter_freigeben(session, benutzer, board, filter_id or "")
    elif aktion == "freigabe_entfernen":
        ok, meldung = lead_boards.filter_freigabe_entfernen(session, benutzer, board, filter_id or "")
    if ok:
        session.commit()
    else:
        session.rollback()
    kontext = lead_boards.filter_kontext(session, benutzer, board)
    return JSONResponse({"ok": ok, "meldung": meldung, "board": board, "filter": kontext["liste"],
                         "standard_id": kontext["standard_id"],
                         "darf_freigeben": kontext["darf_freigeben"]},
                        status_code=200 if ok else 400)


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
    # v31 (Phase 154, v27-Regel): Archivieren/Duplizieren/Wiederherstellen fassen mehrere
    # Zeilen an → _speichern-Muster (Rollback + eine Wiederholung bei „database is locked“)
    ergebnis = {}

    def _ausfuehren():
        ok_, meldung_, extra_ = lead_boards.sammelaktion_ausfuehren_voll(
            session, benutzer, board, aktion, ids, params)
        ergebnis.update(ok=ok_, meldung=meldung_, extra=extra_)
        if not ok_:
            session.rollback()
        return ok_
    if aktion in ("archivieren", "duplizieren", "wiederherstellen"):
        _speichern(session, _ausfuehren)
    else:
        if _ausfuehren():
            session.commit()
    ok, meldung, extra = ergebnis["ok"], ergebnis["meldung"], ergebnis.get("extra") or {}
    kopien = [k["id"] for k in extra.get("kopien", [])]
    if _json_gewuenscht(request):
        return JSONResponse({"ok": ok, "meldung": meldung, "kopien": kopien},
                            status_code=200 if ok else 422)
    ziel = f"/lead-management/{board if board in lead_boards.BOARDS else 'hauptboard'}"
    zusatz = ""
    if aktion == "wiederherstellen":
        zusatz = "&archiviert=1"          # in der Archiv-Sicht bleiben
    if kopien:
        zusatz += "&kopien=" + ",".join(str(k) for k in kopien)
    return RedirectResponse(f"{ziel}?meldung={quote_plus(meldung)}"
                            + ("" if ok else "&fehler=1") + zusatz, status_code=303)


# --- Spaltenkonfiguration je Nutzer (A-14, v25 erweitert) ------------------------------------

def _spalten_gate(request: Request, session: Session, board: str) -> None:
    """v33 (PLAN_V20 Phase 174): die Spaltenwerkzeuge der Angebotstool-Tabellen
    (lead_boards.TABELLEN_BOARDS) stehen jeder angemeldeten Rolle offen – auch dem
    Außendienst für meine_angebote/leads_vot (Katalog nach Basisrolle, lead_boards.
    katalog_fuer); nur die Lead-Boards laufen weiter über lead_v2.gate (404/HV-Sicht)."""
    if not lead_boards.ist_tabelle(board):
        lead_v2.gate(request, session)


def spalten_holen_antwort(request: Request, session: Session) -> JSONResponse:
    """Antwort von GET …/spalten – auch vom Alias /einstellungen/spalten genutzt (v33)."""
    board = request.query_params.get("board", "hauptboard")
    if not lead_boards.board_bekannt(board):
        board = "hauptboard"
    _spalten_gate(request, session, board)
    benutzer = request.state.benutzer
    return JSONResponse({"board": board,
                         "spalten": lead_boards.spalten_fuer(session, benutzer, board),
                         "sort": lead_boards.sortierung_fuer(session, benutzer, board)})


@router.get("/boards/spalten")
def spalten_holen(request: Request, session: Session = Depends(get_session)):
    """{board, spalten: [{key, titel, standard, name, sichtbar}], sort: {key, richtung} | null}"""
    return spalten_holen_antwort(request, session)


@router.post("/boards/spalten")
def spalten_speichern(request: Request, session: Session = Depends(get_session)):
    """JSON {board, spalten?: [{key, sichtbar, name?}] in Reihenfolge,
    sort?: {key, richtung: auf|ab} | null, umbenennen?: {key, name} (leer =
    Standard), zuruecksetzen?: true} → gespeicherte Liste + Sortierung. Gilt
    nur für den angemeldeten Nutzer. Mindestens eine Angabe ist Pflicht;
    kaputte Daten setzen die Konfiguration nie still zurück."""
    return spalten_speichern_antwort(request, session)


def spalten_speichern_antwort(request: Request, session: Session) -> JSONResponse:
    """Antwort von POST …/spalten – auch vom Alias /einstellungen/spalten genutzt (v33)."""
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
    if not lead_boards.board_bekannt(board):
        return JSONResponse({"ok": False, "meldung": "Unbekanntes Board."}, status_code=400)
    _spalten_gate(request, session, board)
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
    # v35 (Phase 186): EINE Suchleiste – die Rufnummer steht im Feld q (Endziffern ab 3,
    # lead_anrufliste.rufnummer_suchen); telefon= bleibt als Alias für alte Links
    daten = lead_boards.kontaktiert_daten(session, request.state.benutzer,
                                          q.get("q", ""), q.get("telefon", ""), seite)
    # v25: Phasen-Labels nur aus dem Blatt Status (beide Kontakt-Phasen „Kontaktiert“)
    antwort = render(request, "leadmanagement/kontaktiert.html", aktiv="/lead-management",
                     **daten, phasen_namen=lead_boards.phasen_labels(),
                     score_aktiv=lead_v2.score_aktiv(session),
                     meldung=q.get("meldung", ""), **_badge(session))
    if fragment_gewuenscht(request):
        return fragment_antwort(antwort, gesamt=daten["gesamt"], treffer=len(daten["treffer"]),
                                telefon=daten["telefon"])
    return antwort


# --- E-Mail-Vorlagen im Modul --------------------------------------------------------------
# v29 (PLAN_LEAD_V4 Phase 142): Der Vorlagen-Editor (Baum links, Terminbestätigung je
# Vertriebler) lebt in app/routers/lm_vorlagen.py; der v23-Editor (H8) ist entfernt.
