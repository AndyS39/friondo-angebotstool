# Login/Logout (Phase 13): Benutzer wählen + PIN, signiertes Cookie.
# v27 (PLAN_V17 Phase 130): Fehlversuchssperre, IP-Grenze und Login-Protokoll
# über auth.login_pruefen, Cookie v2 mit Ablauf (auth.cookie_setzen), Häkchen
# „Auf diesem Gerät angemeldet bleiben“ (v27: nur Außendienst/Montage; v34, PLAN_V21
# Phase 181: auf Mobilgeräten für alle Rollen – User-Agent oder Feld mobil=1,
# auth.sitzungsdauer_s entscheidet, Büro-Rollen am PC 12 h) und der
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

# v37 (PLAN_LEAD_V7 Phase 198, Agent L2): zuletzt verwendeter Benutzer je Browser – Cookie mit
# der Benutzer-ID (nie die PIN, nie der Name), 90 Tage, HttpOnly, SameSite=Lax, Secure bei
# HTTPS_AKTIV; die Login-Seite belegt die Benutzerwahl vor und setzt den Fokus in die PIN,
# „Anderer Benutzer“ (GET /login?anderer=1) leert das Cookie; Abmelden behält es.
BENUTZER_COOKIE = "angebotstool_benutzer"
BENUTZER_COOKIE_TAGE = 90


def benutzer_cookie_setzen(antwort, benutzer_id: int) -> None:
    from datetime import datetime, timedelta, timezone

    from app import config
    dauer_s = BENUTZER_COOKIE_TAGE * 86400
    antwort.set_cookie(BENUTZER_COOKIE, str(int(benutzer_id)), httponly=True, max_age=dauer_s,
                       expires=datetime.now(timezone.utc) + timedelta(seconds=dauer_s),
                       path="/", samesite="lax", secure=bool(config.HTTPS_AKTIV))


def benutzer_cookie_loeschen(antwort) -> None:
    from app import config
    antwort.delete_cookie(BENUTZER_COOKIE, path="/", samesite="lax", secure=bool(config.HTTPS_AKTIV))


def gemerkter_benutzer(request: Request, benutzer: list[Benutzer]) -> int | None:
    """ID aus dem Cookie, wenn sie zu einem aktiven Benutzer der Auswahl gehört."""
    wert = (request.cookies.get(BENUTZER_COOKIE) or "").strip()
    if not wert.isdigit():
        return None
    nr = int(wert)
    return nr if any(b.id == nr for b in benutzer) else None


# v9-Portal: Innendienst landet nach dem Login direkt im Angebotstool
# (das Portal „/“ ist über den Home-Link im Kopf erreichbar)
STARTSEITEN = {"aussendienst": "/erfassung", "projektierung": "/projektierung",
               "montage": "/montage", "leadmanagement": "/lead-management"}


def startseite(session: Session, benutzer) -> str:
    """Rollen-Startseite nach Login und PIN-Wechsel (gleiche Zuordnung)."""
    # v33 (PLAN_V20 Phase 167): Basisrolle – Varianten (Montage Heizung, Service Elektro …)
    # landen direkt auf der Startseite ihrer Basisrolle
    ziel = STARTSEITEN.get(getattr(benutzer, "basisrolle", None) or benutzer.rolle, "/angebotstool")
    # v23 (Phase 109): Handelsvertreter landen nach dem Login im Lead-Modul
    # (Modul-Einstieg → persönliches Dashboard mit eigenen Leads)
    try:
        from app import lead_v2
        if lead_v2.ist_handelsvertreter(session, benutzer):
            ziel = "/lead-management"
    except Exception:
        pass
    return ziel


def _login_kontext(session: Session, request: Request | None = None) -> dict:
    """Hinweistext unter dem Häkchen: Sitzungsdauern aus den Parametern.
    v27-Nachtrag 2: mobile_rollen (auth.MOBILE_ROLLEN) – das Template markiert
    Außendienst/Montage in der Benutzerwahl (data-mobil); für diese Rollen gilt das
    Häkchen „angemeldet bleiben“ auf jedem Gerät.
    v34 (PLAN_V21 Phase 181): mobil_geraet – Mobilgerät laut User-Agent; dann zeigt
    die Seite das Häkchen für ALLE Rollen (das Skript ergänzt Breite < 600 px /
    Touch über das Feld mobil=1); die Sitzungsdauer entscheidet auth.sitzungsdauer_s."""
    mobil = auth.sitzungsdauer_s(session, SimpleNamespace(rolle="aussendienst"), True)
    buero = auth.sitzungsdauer_s(session, SimpleNamespace(rolle="innendienst"), True)
    user_agent = request.headers.get("user-agent", "") if request is not None else ""
    return {"tage_mobil": max(1, mobil // 86400), "stunden_buero": max(1, buero // 3600),
            "mobile_rollen": tuple(auth.MOBILE_ROLLEN),
            "mobil_geraet": auth.ist_mobilgeraet(user_agent)}


def _aktive_benutzer(session: Session) -> list[Benutzer]:
    return (session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
            .order_by(Benutzer.name).all())


@router.get("/login")
def login_formular(request: Request, session: Session = Depends(get_session)):
    benutzer = _aktive_benutzer(session)
    # v37 (Phase 198): ?anderer=1 leert das Cookie des gemerkten Benutzers (Fokus auf die Auswahl)
    anderer = request.query_params.get("anderer") == "1"
    vorgewaehlt = None if anderer else gemerkter_benutzer(request, benutzer)
    antwort = render(request, "anmeldung/login.html", aktiv=None,
                     benutzer=benutzer, fehler="",
                     angemeldet_bleiben=False, vorgewaehlt=vorgewaehlt, anderer=anderer,
                     **_login_kontext(session, request))
    if anderer:
        benutzer_cookie_loeschen(antwort)
    return antwort


@router.post("/login")
def login(request: Request, session: Session = Depends(get_session)):
    form = anfrage.formular(request)
    try:
        benutzer_id = int(form.get("benutzer_id") or 0)
    except ValueError:
        benutzer_id = 0
    pin = (form.get("pin") or "").strip()
    angemeldet_bleiben = (form.get("angemeldet_bleiben") or "") in ("on", "1", "true")
    # v34 (PLAN_V21 Phase 181): Mobilgerät = User-Agent ODER Feld mobil=1 (Skript der
    # Anmeldeseite bei Breite < 600 px / Touch) – dann 30 Tage für jede Rolle mit Häkchen
    mobil = auth.ist_mobilgeraet(request.headers.get("user-agent", ""), form.get("mobil"))
    benutzer = session.get(Benutzer, benutzer_id) if benutzer_id else None
    # v27 (Phase 130): PIN-Prüfung mit Sperre (5 Fehlversuche/15 min), IP-Grenze,
    # Protokoll und stiller Hash-Umstellung – committet selbst
    ok, text = auth.login_pruefen(session, benutzer, pin, auth.client_ip(request))
    if not ok:
        return render(request, "anmeldung/login.html", aktiv=None,
                      benutzer=_aktive_benutzer(session), fehler=text,
                      angemeldet_bleiben=angemeldet_bleiben,
                      vorgewaehlt=benutzer_id or None, anderer=False,
                      **_login_kontext(session, request))
    # Pflichtwechsel (erster Login, Admin-Reset, Import): direkt auf /pin-wechsel –
    # die Middleware leitet zusätzlich jede andere Seite dorthin um
    if benutzer.pin_wechsel_noetig:
        ziel = auth.PIN_WECHSEL_PFAD
    else:
        ziel = startseite(session, benutzer)
    antwort = RedirectResponse(ziel, status_code=303)
    auth.cookie_setzen(antwort, benutzer,
                       auth.sitzungsdauer_s(session, benutzer, angemeldet_bleiben, mobil=mobil))
    # v30 (PLAN_V18 Phase 145): gespeicherte Darstellung des Benutzers als Cookie
    # mitgeben – an einem anderen Browser stimmt der Modus so ab der ersten Seite
    # (nie gewählt = „Gerät“, ein fremdes Cookie derselben Maschine wird ersetzt)
    from app import darstellung
    darstellung.cookie_setzen(antwort, darstellung.lesen(session, benutzer.id)
                              or darstellung.STANDARD)
    # v37 (PLAN_LEAD_V7 Phase 198): Benutzer je Browser merken (nur die ID, nie die PIN)
    benutzer_cookie_setzen(antwort, benutzer.id)
    return antwort


@router.get("/logout")
def logout():
    # v37: das Sitzungs-Cookie geht, der gemerkte Benutzername (angebotstool_benutzer) bleibt
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
