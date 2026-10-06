# Lead-Management V2 (v23) – Router Handelsvertreter (PLAN_LEAD_V2 Phase 109,
# G1–G5, F13–F16). Eigener Router mit demselben Präfix; in app/main.py VOR dem
# V1-Router eingebunden. Gate: lead_v2.gate (Modul-Sichtbare ODER
# Handelsvertreter) – Handelsvertreter sehen ausschließlich eigene Leads
# (server-seitig, app/lead_handelsvertreter.py). Alle Zuweisungen laufen über
# lead_handelsvertreter.zuweisen → lead_v2.ad_zuweisen (Aktivität + Glocke).

from urllib.parse import quote_plus, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import lead_handelsvertreter as hv_modul
from app import lead_v2
from app import leadmanagement as kern
from app.db import get_session
from app.models import Benutzer, Vorgang
from app.templating import render
from app import anfrage   # v27: Formular/JSON in def-Routen

router = APIRouter(prefix="/lead-management")

BASIS = "/lead-management/handelsvertreter"


def _zurueck(wert: str | None) -> str:
    """Redirect-Ziel nur innerhalb des Moduls (kein offener Redirect)."""
    wert = (wert or "").strip()
    if wert.startswith("/lead-management") and "//" not in wert and "\n" not in wert:
        return wert
    return BASIS


def _mit_meldung(ziel: str, meldung: str) -> RedirectResponse:
    trenner = "&" if "?" in ziel else "?"
    return RedirectResponse(f"{ziel}{trenner}meldung={quote_plus(meldung)}", status_code=303)


def _vorgang(request: Request, session: Session, vorgang_id: int) -> Vorgang:
    """Gate + Vorgang (404 bei fremden Leads – auch für Handelsvertreter)."""
    lead_v2.gate(request, session)
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None or not hv_modul.darf_vorgang(session, request.state.benutzer, vorgang):
        raise HTTPException(status_code=404)
    return vorgang


def _kontext(request: Request, session: Session) -> dict:
    return dict(aktiv="/lead-management",
                demo_badge=kern.demo_aktiv(session),
                badge_text=kern.parameter_holen(session, "demo_badge_text",
                                                "Demo · Coming soon"),
                meldung=request.query_params.get("meldung", ""))


@router.get("/handelsvertreter")
def uebersicht(request: Request, session: Session = Depends(get_session)):
    """G1: Innendienst/Leadmanagement/Admin – alle Handelsvertreter-Leads
    gruppiert je Vertreter (einklappbar, Zähler, Filter, Suche); ein
    Handelsvertreter sieht nur seine eigenen Leads plus sein Dashboard (F16)."""
    lead_v2.gate(request, session)
    benutzer = request.state.benutzer
    gesamt = hv_modul.gesamtsicht(session, benutzer)
    f = hv_modul.filter_aus_query(request.query_params, gesamt)
    daten = hv_modul.ansicht(session, benutzer, f)
    # Rücksprungziel = aktuelle Filter, aber ohne die alte Meldung (sonst
    # hängen sich meldung=…-Parameter bei jeder Aktion aneinander)
    params = [(k, v) for k, v in request.query_params.multi_items() if k != "meldung"]
    zurueck = BASIS + (f"?{urlencode(params)}" if params else "")
    return render(request, "leadmanagement/hv_uebersicht.html",
                  zurueck=zurueck, benutzer=benutzer, ist_hv=not gesamt,
                  **daten, **_kontext(request, session))


@router.get("/handelsvertreter/dashboard")
def dashboard(request: Request, session: Session = Depends(get_session)):
    """F16: persönliches Dashboard des Handelsvertreters (fällige
    Wiedervorlagen, eigene Termine der nächsten 7 Tage, offene Leads,
    To-Dos). Innendienst/Admin wählen über ?hv=<id> einen Vertreter."""
    lead_v2.gate(request, session)
    benutzer = request.state.benutzer
    gesamt = hv_modul.gesamtsicht(session, benutzer)
    ziel = benutzer
    hv_liste = []
    if gesamt:
        # Auswahl nur aus dem HV-Kreis (gekennzeichnete plus namentlich bekannte
        # Vertreter ohne Kennzeichen) – ?hv=<fremde ID> fällt auf den ersten zurück
        kreis = hv_modul.hv_kreis(session)
        hv_liste = sorted((paar[0] for paar in kreis.values()), key=lambda b: b.name.lower())
        wert = (request.query_params.get("hv") or "").strip()
        ziel = kreis[int(wert)][0] if wert.isdigit() and int(wert) in kreis else None
        if ziel is None and hv_liste:
            ziel = hv_liste[0]
    daten = hv_modul.dashboard_daten(session, ziel) if ziel is not None else None
    return render(request, "leadmanagement/hv_dashboard.html",
                  dashboard=daten, ziel=ziel, gesamt=gesamt, hv_liste=hv_liste,
                  ist_hv=not gesamt, zurueck=f"{BASIS}/dashboard",
                  **_kontext(request, session))


@router.post("/handelsvertreter/{vorgang_id}/zuweisen")
def zuweisen(request: Request, vorgang_id: int,
                   session: Session = Depends(get_session)):
    """G3/F13: Dropdown „Vertreter“ – Innendienst/Admin weisen zu oder nehmen
    zurück (erzwingen=False: Ausschlussliste F14 greift immer); ein
    Handelsvertreter darf eigene Leads nur an einen anderen Handelsvertreter
    weitergeben (Aktivität + Glocke über lead_v2.ad_zuweisen)."""
    vorgang = _vorgang(request, session, vorgang_id)
    benutzer = request.state.benutzer
    form = anfrage.formular(request)
    ad_id = (form.get("ad_id") or "").strip()
    zurueck = _zurueck(form.get("zurueck"))
    if hv_modul.gesamtsicht(session, benutzer):
        meldung = hv_modul.zuweisen(session, vorgang, ad_id or None,
                                    benutzer=benutzer, erzwingen=False)
    else:
        if not ad_id.isdigit() or int(ad_id) not in hv_modul.hv_ids(session):
            meldung = ("Nicht möglich: Handelsvertreter geben Leads nur an "
                       "andere Handelsvertreter weiter.")
        else:
            meldung = hv_modul.zuweisen(session, vorgang, int(ad_id),
                                        benutzer=benutzer, erzwingen=False)
    session.commit()
    return _mit_meldung(zurueck, meldung)


@router.post("/handelsvertreter/{vorgang_id}/standard")
def an_standard(request: Request, vorgang_id: int,
                      session: Session = Depends(get_session)):
    """F13: Button „An Standard (Simon) geben“ – für Tool-Leads ohne Automatik
    und für Umverteilungen; Ausschluss und Sonderregel greifen."""
    vorgang = _vorgang(request, session, vorgang_id)
    form = anfrage.formular(request)
    meldung = hv_modul.an_standard(session, vorgang, benutzer=request.state.benutzer)
    session.commit()
    return _mit_meldung(_zurueck(form.get("zurueck")), meldung)


@router.post("/handelsvertreter/standard-nachziehen")
def standard_nachziehen(request: Request, session: Session = Depends(get_session)):
    """F13: Bestandsleads (monday) ohne ad_id nach Standardregel zuweisen –
    nur Innendienst/Leadmanagement/Admin."""
    lead_v2.gate(request, session)
    if not hv_modul.gesamtsicht(session, request.state.benutzer):
        raise HTTPException(status_code=404)
    form = anfrage.formular(request)
    anzahl = hv_modul.standard_nachziehen(session, benutzer=request.state.benutzer)
    session.commit()
    meldung = (f"Standard nachgezogen: {anzahl} Zuweisung(en) gesetzt."
               if anzahl else "Standard nachgezogen: keine offenen Bestandsleads.")
    return _mit_meldung(_zurueck(form.get("zurueck")), meldung)
