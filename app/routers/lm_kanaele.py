# v35 (PLAN_LEAD_V6 Phase 184, Agent K): Vertriebskanal-Stammdaten – Pflegeseite
# GET /lead-management/kanaele (Lead-Board-Layout, Liste Name · Farbe · aktiv · Anzahl Leads ·
# Verwendungen 90 Tage; Pflege nur Admin/Innendienst, andere Lead-Rollen lesen) und die
# Schreibrouten POST /kanaele (anlegen), /kanaele/{id} (umbenennen – wirkt überall),
# /kanaele/{id}/farbe, /kanaele/{id}/deaktivieren, /kanaele/{id}/aktivieren,
# /kanaele/{id}/loeschen (endgültig nur ohne Lead), /kanaele/abgleichen (Bestand gegen die
# Tabelle). Alle Routen `def` (v27), Formulare über anfrage.formular, Schreibzugriffe im
# _speichern-Muster (Rollback + eine Wiederholung bei „database is locked“), JSON bei
# Accept: application/json, sonst Redirect mit ?meldung=. Keine Glocken (v29-Sperre).
# Stammdaten-Logik: app/lead_kanaele.py. Jinja-Global lm_kanal_farbe (kanal_badge ohne Farbe
# holt die Tabellenfarbe über einen Prozess-Cache).
import time
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import anfrage, lead_kanaele, lead_v2
from app import leadmanagement as kern
from app.db import get_session
from app.models import Vertriebskanal
from app.templating import render, templates

router = APIRouter(prefix="/lead-management", tags=["leadmanagement"])
SEITE = "/lead-management/kanaele"

templates.env.globals.setdefault("lm_kanal_farbe", lead_kanaele.farbe_schnell)


def _json_gewuenscht(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "")


def _darf_pflegen(benutzer) -> bool:
    return benutzer is not None and benutzer.basisrolle in ("admin", "innendienst")


def _antwort(request: Request, ok: bool, meldung: str, status: int = 200, **zusatz):
    if _json_gewuenscht(request):
        return JSONResponse(dict({"ok": ok, "meldung": meldung}, **zusatz),
                            status_code=status if not ok else 200)
    return RedirectResponse(f"{SEITE}?meldung={quote_plus(meldung)}", status_code=303)


def _speichern(session: Session, aktion, wiederholungen: int = 1):
    """v27/v33: eine Wiederholung nach 0,7 s bei „database is locked“ (Vorbild lm_boards)."""
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


def _schreib_gate(request: Request, session: Session):
    lead_v2.gate(request, session)
    if not _darf_pflegen(request.state.benutzer):
        if _json_gewuenscht(request):
            raise HTTPException(status_code=403, detail="Vertriebskanäle pflegen nur Admin und Innendienst.")
        raise HTTPException(status_code=303, headers={
            "Location": f"{SEITE}?meldung={quote_plus('Vertriebskanäle pflegen nur Admin und Innendienst.')}"})


def _zeile(session: Session, kanal_id: int) -> Vertriebskanal:
    zeile = session.get(Vertriebskanal, kanal_id)
    if zeile is None:
        raise HTTPException(status_code=404, detail="Vertriebskanal nicht gefunden.")
    return zeile


def _seitendaten(session: Session) -> dict:
    nutzung = lead_kanaele.verwendungen(session)
    sortiert = lead_kanaele.kanal_sortiert(session)
    reihen = []
    for z in sortiert + [z for z in lead_kanaele.kanal_liste(session, nur_aktive=False) if not z.aktiv]:
        gesamt, tage90 = nutzung.get(lead_kanaele.schluessel(z.name), (0, 0))
        reihen.append({"zeile": z, "gesamt": gesamt, "tage90": tage90,
                       "kontrast": lead_kanaele.kontrast(z.farbe),
                       "unklar": lead_kanaele.ist_unklar(z.name),
                       "loeschbar": gesamt == 0 and not lead_kanaele.ist_unklar(z.name)})
    aktive = [r for r in reihen if r["zeile"].aktiv]
    inaktive = [r for r in reihen if not r["zeile"].aktiv]
    unklar_anzahl = next((r["gesamt"] for r in reihen if r["unklar"]), 0)
    return {"aktive": aktive, "inaktive": inaktive, "unklar_anzahl": unklar_anzahl,
            "gefuellt": lead_kanaele.tabelle_gefuellt(session)}


@router.get("/kanaele")
def kanaele_seite(request: Request, session: Session = Depends(get_session)):
    lead_v2.gate(request, session)
    benutzer = request.state.benutzer
    daten = _seitendaten(session)
    return render(request, "leadmanagement/kanaele.html", aktiv="/lead-management",
                  darf_pflegen=_darf_pflegen(benutzer),
                  demo_badge=kern.demo_aktiv(session),
                  badge_text=kern.parameter_holen(session, "demo_badge_text", "Demo · Coming soon"),
                  unklar_hinweis=lead_kanaele.UNKLAR_HINWEIS,
                  verwendung_tage=lead_kanaele.VERWENDUNG_TAGE,
                  meldung=request.query_params.get("meldung", ""),
                  fehler=request.query_params.get("fehler", "") == "1",
                  **daten)


@router.get("/kanaele.json")
def kanaele_json(request: Request, session: Session = Depends(get_session)):
    """Aktive Kanäle in Dropdown-Reihenfolge (Vertrag B/R: Inline-Dropdown der Boards)."""
    lead_v2.gate(request, session)
    aktuell = (request.query_params.get("aktuell") or "").strip()
    return JSONResponse({"ok": True, "kanaele": lead_kanaele.kanal_optionen(session, aktuell)})


@router.post("/kanaele")
def kanal_anlegen(request: Request, session: Session = Depends(get_session)):
    _schreib_gate(request, session)
    form = anfrage.formular(request)
    name = (form.get("name") or "").strip()
    farbe = (form.get("farbe") or "").strip()
    try:
        zeile = _speichern(session, lambda: lead_kanaele.kanal_anlegen(session, name, farbe))
    except ValueError as fehler:
        return _antwort(request, False, str(fehler), status=400)
    return _antwort(request, True, f"Kanal „{zeile.name}“ angelegt.", id=zeile.id,
                    name=zeile.name, farbe=zeile.farbe)


@router.post("/kanaele/abgleichen")
def kanaele_abgleichen(request: Request, session: Session = Depends(get_session)):
    """Bestand (Kunden, monday-Leads, Quellen) gegen die Tabelle abgleichen – wie die Migration."""
    _schreib_gate(request, session)
    meldungen = _speichern(session, lambda: lead_kanaele.bestand_abgleichen(session))
    text = ("Bestand abgeglichen: " + " · ".join(m.replace("Kanaele (v35): ", "") for m in meldungen)
            if meldungen else "Bestand abgeglichen – nichts zu ändern.")
    return _antwort(request, True, text, meldungen=meldungen)


@router.post("/kanaele/{kanal_id}")
def kanal_umbenennen(request: Request, kanal_id: int, session: Session = Depends(get_session)):
    _schreib_gate(request, session)
    form = anfrage.formular(request)
    zeile = _zeile(session, kanal_id)
    name = (form.get("name") or "").strip()
    ok, meldung = _speichern(session, lambda: lead_kanaele.kanal_umbenennen(session, zeile, name))
    return _antwort(request, ok, meldung, status=400, name=zeile.name)


@router.post("/kanaele/{kanal_id}/farbe")
def kanal_farbe(request: Request, kanal_id: int, session: Session = Depends(get_session)):
    _schreib_gate(request, session)
    form = anfrage.formular(request)
    zeile = _zeile(session, kanal_id)
    farbe = (form.get("farbe") or "").strip()
    ok, meldung = _speichern(session, lambda: lead_kanaele.farbe_setzen(session, zeile, farbe))
    return _antwort(request, ok, meldung, status=400, farbe=zeile.farbe,
                    kontrast=lead_kanaele.kontrast(zeile.farbe))


@router.post("/kanaele/{kanal_id}/deaktivieren")
def kanal_deaktivieren(request: Request, kanal_id: int, session: Session = Depends(get_session)):
    _schreib_gate(request, session)
    zeile = _zeile(session, kanal_id)
    ok, meldung = _speichern(session, lambda: lead_kanaele.kanal_deaktivieren(session, zeile))
    return _antwort(request, ok, meldung, status=400, aktiv=bool(zeile.aktiv))


@router.post("/kanaele/{kanal_id}/aktivieren")
def kanal_aktivieren(request: Request, kanal_id: int, session: Session = Depends(get_session)):
    _schreib_gate(request, session)
    zeile = _zeile(session, kanal_id)
    ok, meldung = _speichern(session, lambda: lead_kanaele.kanal_aktivieren(session, zeile))
    return _antwort(request, ok, meldung, status=400, aktiv=bool(zeile.aktiv))


@router.post("/kanaele/{kanal_id}/loeschen")
def kanal_loeschen(request: Request, kanal_id: int, session: Session = Depends(get_session)):
    _schreib_gate(request, session)
    zeile = _zeile(session, kanal_id)
    name = zeile.name
    geloescht, meldung = _speichern(session, lambda: lead_kanaele.kanal_loeschen(session, zeile))
    # „?“ ist nicht löschbar (Meldung), verwendete Kanäle werden deaktiviert (ok, nicht endgültig)
    ok = geloescht or not lead_kanaele.ist_unklar(name)
    return _antwort(request, ok, meldung, status=400, geloescht=geloescht)
