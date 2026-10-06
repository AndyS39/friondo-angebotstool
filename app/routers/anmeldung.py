# Login/Logout (Phase 13): Benutzer wählen + PIN, signiertes Cookie.
# v27 (PLAN_V17 Phase 130): Fehlversuchssperre, IP-Grenze und Login-Protokoll
# über auth.login_pruefen, Cookie v2 mit Ablauf (auth.cookie_setzen), Häkchen
# „Auf diesem Gerät angemeldet bleiben“ (wirkt nur für Außendienst/Montage –
# auth.sitzungsdauer_s entscheidet, Büro-Rollen bekommen immer 12 h) und der
# Pflicht-PIN-Wechsel /pin-wechsel (erster Login, Admin-Reset, CSV-Import).

from types import SimpleNamespace

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import auth
from app.db import get_session
from app.models import Benutzer
from app.templating import render
from app import anfrage   # v27: Formular/JSON in def-Routen

router = APIRouter()

# v9-Portal: Innendienst landet nach dem Login direkt im Angebotstool
# (das Portal „/“ ist über den Home-Link im Kopf erreichbar)
STARTSEITEN = {"aussendienst": "/erfassung", "projektierung": "/projektierung",
               "montage": "/montage", "leadmanagement": "/lead-management"}


def startseite(session: Session, benutzer) -> str:
    """Rollen-Startseite nach Login und PIN-Wechsel (gleiche Zuordnung)."""
    ziel = STARTSEITEN.get(benutzer.rolle, "/angebotstool")
    # v23 (Phase 109): Handelsvertreter landen nach dem Login im Lead-Modul
    # (Modul-Einstieg → persönliches Dashboard mit eigenen Leads)
    try:
        from app import lead_v2
        if lead_v2.ist_handelsvertreter(session, benutzer):
            ziel = "/lead-management"
    except Exception:
        pass
    return ziel


def _login_kontext(session: Session) -> dict:
    """Hinweistext unter dem Häkchen: Sitzungsdauern aus den Parametern."""
    mobil = auth.sitzungsdauer_s(session, SimpleNamespace(rolle="aussendienst"), True)
    buero = auth.sitzungsdauer_s(session, SimpleNamespace(rolle="innendienst"), True)
    return {"tage_mobil": max(1, mobil // 86400), "stunden_buero": max(1, buero // 3600)}


def _aktive_benutzer(session: Session) -> list[Benutzer]:
    return (session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
            .order_by(Benutzer.name).all())


@router.get("/login")
def login_formular(request: Request, session: Session = Depends(get_session)):
    return render(request, "anmeldung/login.html", aktiv=None,
                  benutzer=_aktive_benutzer(session), fehler="",
                  angemeldet_bleiben=False, **_login_kontext(session))


@router.post("/login")
def login(request: Request, session: Session = Depends(get_session)):
    form = anfrage.formular(request)
    try:
        benutzer_id = int(form.get("benutzer_id") or 0)
    except ValueError:
        benutzer_id = 0
    pin = (form.get("pin") or "").strip()
    angemeldet_bleiben = (form.get("angemeldet_bleiben") or "") in ("on", "1", "true")
    benutzer = session.get(Benutzer, benutzer_id) if benutzer_id else None
    # v27 (Phase 130): PIN-Prüfung mit Sperre (5 Fehlversuche/15 min), IP-Grenze,
    # Protokoll und stiller Hash-Umstellung – committet selbst
    ok, text = auth.login_pruefen(session, benutzer, pin, auth.client_ip(request))
    if not ok:
        return render(request, "anmeldung/login.html", aktiv=None,
                      benutzer=_aktive_benutzer(session), fehler=text,
                      angemeldet_bleiben=angemeldet_bleiben, **_login_kontext(session))
    # Pflichtwechsel (erster Login, Admin-Reset, Import): direkt auf /pin-wechsel –
    # die Middleware leitet zusätzlich jede andere Seite dorthin um
    if benutzer.pin_wechsel_noetig:
        ziel = auth.PIN_WECHSEL_PFAD
    else:
        ziel = startseite(session, benutzer)
    antwort = RedirectResponse(ziel, status_code=303)
    auth.cookie_setzen(antwort, benutzer,
                       auth.sitzungsdauer_s(session, benutzer, angemeldet_bleiben))
    return antwort


@router.get("/logout")
def logout():
    antwort = RedirectResponse("/login", status_code=303)
    antwort.delete_cookie(auth.COOKIE_NAME)
    return antwort


# --- v27 (Phase 130): PIN-Wechsel (jede Rolle, mobil tauglich) ---------------------------

def _pin_wechsel_seite(request: Request, session: Session, benutzer, fehler: str = ""):
    return render(request, "anmeldung/pin_wechsel.html", aktiv=None, fehler=fehler,
                  pflicht=bool(getattr(benutzer, "pin_wechsel_noetig", False)),
                  mindestlaenge=auth.pin_mindestlaenge(session),
                  zurueck=startseite(session, benutzer))


@router.get(auth.PIN_WECHSEL_PFAD)
def pin_wechsel_formular(request: Request, session: Session = Depends(get_session)):
    benutzer = getattr(request.state, "benutzer", None)
    if benutzer is None:
        return RedirectResponse("/login", status_code=303)
    return _pin_wechsel_seite(request, session, benutzer)


@router.post(auth.PIN_WECHSEL_PFAD)
def pin_wechsel(request: Request, session: Session = Depends(get_session)):
    angemeldet = getattr(request.state, "benutzer", None)
    if angemeldet is None:
        return RedirectResponse("/login", status_code=303)
    # request.state.benutzer ist ein abgelöstes Objekt (Middleware-Sitzung
    # geschlossen) – für das Schreiben in der Request-Sitzung neu laden
    benutzer = session.get(Benutzer, angemeldet.id)
    if benutzer is None or not benutzer.aktiv:
        return RedirectResponse("/login", status_code=303)
    form = anfrage.formular(request)
    alt = (form.get("pin_alt") or "").strip()
    neu = (form.get("pin_neu") or "").strip()
    neu2 = (form.get("pin_neu2") or "").strip()
    if not auth.pin_pruefen(benutzer, alt):
        fehler = "Die aktuelle PIN ist falsch."
    elif neu != neu2:
        fehler = "Die neue PIN wurde nicht zweimal gleich eingegeben."
    else:
        fehler = auth.pin_regel_pruefen(neu, session)
        if fehler is None and neu == alt:
            fehler = "Die neue PIN muss sich von der aktuellen PIN unterscheiden."
    if fehler:
        return _pin_wechsel_seite(request, session, benutzer, fehler)
    auth.pin_setzen(benutzer, neu)          # schreibt pin_hash_v2 UND pin_hash
    benutzer.pin_wechsel_noetig = False
    session.commit()
    return RedirectResponse(startseite(session, benutzer), status_code=303)
