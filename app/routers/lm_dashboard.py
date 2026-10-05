# Lead-Management V2 (v23) – Router Dashboard & To-Dos (PLAN_LEAD_V2 Phase 110,
# Diktat A1/A2, F6/F7/F16). Eigener Router mit demselben Präfix; in app/main.py
# VOR dem V1-Router eingebunden, damit gleiche Pfade hier Vorrang haben
# (Modul-Einstieg „“ und /meine-termine werden hier übernommen).
# Gate: lead_v2.gate (404 im Demo-Modus, Handelsvertreter-Freigabe); Außendienst
# ohne HV-Kennzeichen → Weiterleitung auf „Meine Termine“ (F6).

from datetime import datetime
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import lead_dashboard, lead_todos, lead_v2
from app import leadmanagement as kern
from app.db import get_session
from app.models import Kunde, Todo, Vorgang
from app.templating import render

router = APIRouter(prefix="/lead-management")

DASHBOARD = "/lead-management/dashboard"
TODOS = "/lead-management/todos"


# --- Hilfen -------------------------------------------------------------------------

def _ad_ohne_hv(session: Session, benutzer) -> bool:
    """Außendienst ohne Handelsvertreter-Kennzeichen bleibt bei Meine Termine."""
    return (benutzer is not None and benutzer.rolle == "aussendienst"
            and not lead_v2.ist_handelsvertreter(session, benutzer))


def _zugang_todos(session: Session, benutzer) -> bool:
    """To-Do-Seiten: Modul-Sichtbare und Handelsvertreter (lead_v2) sowie der
    Außendienst mit AD-Sicht (Freigabe „alle“); im Demo-Modus bleibt alles
    unter /lead-management für Nicht-Admins unsichtbar (404)."""
    return (lead_v2.zugriff_erlaubt(session, benutzer)
            or kern.lead_ad_sicht(session, benutzer))


def _vorgang_zugriff(session: Session, benutzer, vorgang: Vorgang | None) -> bool:
    """Darf der Benutzer To-Dos zu diesem Vorgang sehen/anlegen? Modul-Sichtbare
    immer, Handelsvertreter nur an eigenen Vorgängen (lead_v2.zugriff_erlaubt),
    Außendienst mit AD-Sicht an Vorgängen, die ihm gehören (Lead, Erfassung,
    Termin, Angebot – vorgaenge.gehoert_benutzer – oder vorgaenge.ad_id)."""
    if vorgang is None or benutzer is None:
        return False
    if lead_v2.zugriff_erlaubt(session, benutzer, vorgang):
        return True
    if kern.lead_ad_sicht(session, benutzer):
        if vorgang.ad_id == benutzer.id:
            return True
        try:
            from app import vorgaenge as vorgaenge_modul
            return vorgaenge_modul.gehoert_benutzer(session, vorgang, benutzer.id)
        except Exception:
            return False
    return False


def _ohne_meldung(url: str) -> str:
    teile = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(teile.query, keep_blank_values=True)
             if k != "meldung"]
    return urlunsplit((teile.scheme, teile.netloc, teile.path, urlencode(query), teile.fragment))


def _zurueck(request: Request, form, standard: str) -> str:
    """Redirect-Ziel: Parameter zurueck (nur interne Pfade), sonst Referer,
    sonst Standard – vorhandene meldung-Parameter werden entfernt."""
    basis = str(request.base_url)
    for kandidat in ((form.get("zurueck") or "").strip(),
                     request.headers.get("referer", "")):
        if not kandidat:
            continue
        if kandidat.startswith(basis):
            kandidat = "/" + kandidat[len(basis):]
        if kandidat.startswith("/") and not kandidat.startswith("//"):
            return _ohne_meldung(kandidat)
    return standard


def _redirect(ziel: str, meldung: str = "") -> RedirectResponse:
    if meldung:
        teile = urlsplit(ziel)
        query = teile.query + ("&" if teile.query else "") + "meldung=" + quote_plus(meldung)
        ziel = urlunsplit((teile.scheme, teile.netloc, teile.path, query, teile.fragment))
    return RedirectResponse(ziel, status_code=303)


def _int(wert) -> int | None:
    try:
        zahl = int(str(wert or "").strip() or 0)
    except ValueError:
        return None
    return zahl or None


# --- Modul-Einstieg (übernimmt GET /lead-management) --------------------------------

@router.get("")
async def einstieg(request: Request, session: Session = Depends(get_session)):
    """Einstieg: Sichtbare nach lm_startseite (Standard dashboard, Phase 110);
    Handelsvertreter direkt ins Dashboard (F16); alle anderen sehen die
    Platzhalterseite – exakt wie der V1-Router."""
    benutzer = request.state.benutzer
    if kern.lead_modul_sichtbar(session, benutzer):
        from app import lead_uebersicht
        ziel = lead_uebersicht.startseite(session, benutzer)
        return RedirectResponse(f"/lead-management/{ziel}", status_code=303)
    if lead_v2.ist_handelsvertreter(session, benutzer):
        return RedirectResponse(DASHBOARD, status_code=303)
    return render(request, "platzhalter.html", aktiv=None,
                  titel="Lead-Management",
                  hinweis="Dieser Bereich ist im Aufbau (Coming soon). "
                          "Die Lead-Arbeit läuft bis dahin wie gewohnt über "
                          "das Angebotstool (Leads VOT).")


# --- Dashboard ----------------------------------------------------------------------

@router.get("/dashboard")
async def dashboard(request: Request, session: Session = Depends(get_session)):
    """A1: persönliche Startseite – Wiedervorlagen (beide Mechaniken), mir
    zugeteilte Vorgänge, Termine der nächsten Tage, To-Dos, Kacheln."""
    benutzer = request.state.benutzer
    if _ad_ohne_hv(session, benutzer):
        return RedirectResponse("/lead-management/meine-termine", status_code=303)
    lead_v2.gate(request, session)
    termine_alle = request.query_params.get("termine") == "alle"
    daten = lead_dashboard.daten(session, benutzer, termine_alle=termine_alle)
    # v25: Board-Namen immer aus dem Blatt Status (Hauptboard / Deals), kein Score
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    return render(request, "leadmanagement/dashboard.html",
                  aktiv="/lead-management", benutzer=benutzer, **daten,
                  hauptboard_label=logik.board_label("hauptboard"),
                  deals_label=logik.board_label("terminiert"),
                  score_aktiv=lead_v2.score_aktiv(session),
                  demo_badge=kern.demo_aktiv(session),
                  badge_text=kern.parameter_holen(session, "demo_badge_text",
                                                  "Demo · Coming soon"),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/dashboard/wiedervorlage/{vorgang_id}")
async def wiedervorlage_aktion(request: Request, vorgang_id: int,
                               session: Session = Depends(get_session)):
    """Schnellaktion: art=lead|angebot, aktion=erledigt|verschieben (+ datum)."""
    benutzer = request.state.benutzer
    if _ad_ohne_hv(session, benutzer):
        raise HTTPException(status_code=404)
    lead_v2.gate(request, session)
    form = await request.form()
    zurueck = _zurueck(request, form, DASHBOARD)
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        return _redirect(zurueck, "Vorgang nicht gefunden.")
    art = "angebot" if form.get("art") == "angebot" else "lead"
    aktion = "verschieben" if form.get("aktion") == "verschieben" else "erledigt"
    meldung = lead_dashboard.wiedervorlage_aktion(
        session, vorgang, benutzer, art, aktion, form.get("datum") or "")
    session.commit()
    return _redirect(zurueck, meldung)


# --- To-Dos -------------------------------------------------------------------------

def _todos_seite(request: Request, session: Session, neu: bool = False):
    benutzer = request.state.benutzer
    if not _zugang_todos(session, benutzer):
        raise HTTPException(status_code=404)
    q = request.query_params
    sicht = q.get("sicht", "meine")
    if sicht not in ("meine", "vergeben", "erledigt"):
        sicht = "meine"
    suche = (q.get("q") or "").strip().lower()
    meldung = q.get("meldung", "")
    vorgang = None
    kunde = None
    vorgang_id = _int(q.get("vorgang_id"))
    if vorgang_id:
        vorgang = session.get(Vorgang, vorgang_id)
        if vorgang is None:
            meldung = meldung or f"Vorgang {vorgang_id} nicht gefunden – alle eigenen To-Dos."
            vorgang_id = None
        elif not _vorgang_zugriff(session, benutzer, vorgang):
            # Prüfung Phase 110: Handelsvertreter/Außendienst sehen fremde
            # Vorgänge (Kundenname) nicht über den Filter vorgang_id
            vorgang = None
            vorgang_id = None
            meldung = meldung or "Kein Zugriff auf diesen Vorgang – alle eigenen To-Dos."
        kunde = session.get(Kunde, vorgang.kunde_id) if vorgang else None
    jetzt = datetime.now()
    # v25 (PLAN_LEAD_V3 Phase 118): Filter fällig/alle – fällig = offen mit Fälligkeit bis jetzt
    faellig = q.get("faellig") == "1"
    meine = lead_todos.offene(session, benutzer.id)
    vergeben = lead_todos.vergebene(session, benutzer.id, status=None)
    erledigt = lead_todos.erledigte(session, benutzer.id)

    def _ist_faellig(t) -> bool:
        return t.status == "offen" and t.faellig_am is not None and t.faellig_am <= jetzt
    zaehler = {"meine": len(meine),
               "vergeben": sum(1 for t in vergeben if t.status == "offen"),
               "erledigt": len(erledigt),
               "faellig": sum(1 for t in meine if _ist_faellig(t))}
    if vorgang is not None:
        liste = lead_todos.fuer_vorgang(session, vorgang.id)
        if not lead_v2.zugriff_erlaubt(session, benutzer):
            liste = [t for t in liste if lead_todos.darf_sehen(benutzer, t)]
    else:
        liste = {"meine": meine, "vergeben": vergeben, "erledigt": erledigt}[sicht]
    if faellig:
        liste = [t for t in liste if _ist_faellig(t)]
    if suche:
        liste = [t for t in liste if suche in (t.titel or "").lower()
                 or suche in (t.text or "").lower()]
    zurueck = _ohne_meldung(str(request.url.path) + ("?" + str(request.url.query)
                                                     if request.url.query else ""))
    if zurueck.endswith("/neu"):
        zurueck = TODOS
    return render(request, "leadmanagement/todos.html",
                  aktiv="/lead-management", benutzer=benutzer,
                  modul=lead_v2.zugriff_erlaubt(session, benutzer),
                  hv=lead_v2.ist_handelsvertreter(session, benutzer),
                  sicht=sicht, suche=q.get("q") or "", zaehler=zaehler, faellig=faellig,
                  zeilen=lead_todos.zeilen(session, liste, jetzt),
                  vorgang=vorgang, kunde=kunde, heute=jetzt.date(), jetzt=jetzt,
                  empfaenger=lead_todos.empfaenger_liste(session),
                  formular_offen=neu or bool(vorgang_id), zurueck=zurueck,
                  demo_badge=kern.demo_aktiv(session),
                  badge_text=kern.parameter_holen(session, "demo_badge_text",
                                                  "Demo · Coming soon"),
                  meldung=meldung)


@router.get("/todos")
async def todos(request: Request, session: Session = Depends(get_session)):
    """A2: meine offenen / von mir vergebenen / erledigten To-Dos, Filter
    vorgang_id und q; Formular „To-Do anlegen“ (jeder an jeden, F7)."""
    return _todos_seite(request, session)


@router.get("/todos/neu")
async def todo_neu(request: Request, session: Session = Depends(get_session)):
    """Formular geöffnet (z. B. aus Kartei/Akte mit ?vorgang_id=…)."""
    return _todos_seite(request, session, neu=True)


@router.post("/todos/neu")
async def todo_anlegen(request: Request, session: Session = Depends(get_session)):
    """Felder laut Vertrag: vorgang_id (optional), titel (Pflicht), text,
    faellig_am, an_benutzer_id (Pflicht), zurueck (Redirect-Ziel)."""
    benutzer = request.state.benutzer
    if not _zugang_todos(session, benutzer):
        raise HTTPException(status_code=404)
    form = await request.form()
    zurueck = _zurueck(request, form, TODOS)
    an_id = _int(form.get("an_benutzer_id"))
    if not an_id:
        return _redirect(zurueck, "To-Do: bitte einen Empfänger wählen.")
    vorgang_id = _int(form.get("vorgang_id"))
    if vorgang_id:
        vorgang = session.get(Vorgang, vorgang_id)
        if vorgang is None:
            return _redirect(zurueck, f"To-Do: Vorgang {vorgang_id} nicht gefunden.")
        if not _vorgang_zugriff(session, benutzer, vorgang):
            # Prüfung Phase 110: kein Vorgangsbezug (und keine Aktivität) an
            # fremden Vorgängen für Handelsvertreter/Außendienst
            return _redirect(zurueck, "To-Do: kein Zugriff auf diesen Vorgang.")
    try:
        todo = lead_todos.anlegen(session, benutzer, an_id, form.get("titel") or "",
                                  text=form.get("text") or "",
                                  faellig_am=form.get("faellig_am") or "",
                                  vorgang_id=vorgang_id)
    except ValueError as fehler:
        session.rollback()
        return _redirect(zurueck, f"To-Do: {fehler}")
    session.commit()
    from app.models import Benutzer
    empfaenger = session.get(Benutzer, todo.an_benutzer_id)
    return _redirect(zurueck, f"To-Do angelegt für {empfaenger.name if empfaenger else '?'}: "
                              f"{todo.titel}")


def _todo_laden(session: Session, benutzer, todo_id: int) -> Todo:
    todo = session.get(Todo, todo_id)
    if benutzer is None or todo is None or not lead_todos.darf_sehen(benutzer, todo):
        raise HTTPException(status_code=404)
    return todo


@router.post("/todos/{todo_id}/erledigt")
async def todo_erledigt(request: Request, todo_id: int,
                        session: Session = Depends(get_session)):
    """Erledigt-Häkchen – Empfänger, Ersteller oder Admin (auch der
    Außendienst aus „Meine Termine“)."""
    benutzer = request.state.benutzer
    todo = _todo_laden(session, benutzer, todo_id)
    if not lead_todos.darf_erledigen(benutzer, todo):
        raise HTTPException(status_code=404)
    form = await request.form()
    zurueck = _zurueck(request, form, TODOS)
    geaendert = lead_todos.erledigen(session, todo, benutzer)
    session.commit()
    return _redirect(zurueck, f"To-Do erledigt: {todo.titel}" if geaendert
                     else "To-Do war bereits erledigt.")


@router.post("/todos/{todo_id}/offen")
async def todo_offen(request: Request, todo_id: int,
                     session: Session = Depends(get_session)):
    benutzer = request.state.benutzer
    todo = _todo_laden(session, benutzer, todo_id)
    if not lead_todos.darf_erledigen(benutzer, todo):
        raise HTTPException(status_code=404)
    form = await request.form()
    zurueck = _zurueck(request, form, TODOS)
    lead_todos.wieder_oeffnen(session, todo, benutzer)
    session.commit()
    return _redirect(zurueck, f"To-Do wieder geöffnet: {todo.titel}")


@router.post("/todos/{todo_id}/loeschen")
async def todo_loeschen(request: Request, todo_id: int,
                        session: Session = Depends(get_session)):
    """Nur Ersteller oder Admin."""
    benutzer = request.state.benutzer
    todo = _todo_laden(session, benutzer, todo_id)
    if not lead_todos.darf_loeschen(benutzer, todo):
        raise HTTPException(status_code=404)
    form = await request.form()
    zurueck = _zurueck(request, form, TODOS)
    titel = todo.titel
    lead_todos.loeschen(session, todo, benutzer)
    session.commit()
    return _redirect(zurueck, f"To-Do gelöscht: {titel}")


# --- Meine Termine (Außendienst) + To-Dos ------------------------------------------

@router.get("/meine-termine")
async def meine_termine(request: Request, session: Session = Depends(get_session)):
    """Übernimmt die V1-Seite (Gate lead_ad_sicht, Karten heute/Woche) und
    ergänzt den Block „Meine To-Dos“ – der Außendienst sieht seine To-Dos hier
    und in der Vorgangsakte (F7), ohne Zugriff auf das Lead-Modul."""
    from app.routers import leadmanagement as v1
    antwort = await v1.meine_termine(request, session)
    kontext = getattr(antwort, "context", None)
    if not isinstance(kontext, dict):
        return antwort
    benutzer = request.state.benutzer
    jetzt = datetime.now()
    kontext = {k: v for k, v in kontext.items() if k != "request"}
    kontext.update(todos=lead_todos.zeilen(session, lead_todos.offene(session, benutzer.id), jetzt),
                   heute=jetzt.date(), empfaenger=lead_todos.empfaenger_liste(session))
    return render(request, "leadmanagement/meine_termine.html", **kontext)
