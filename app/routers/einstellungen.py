# v30 (PLAN_V18 Phase 145): Benutzer-Einstellungen, die jede Rolle selbst setzt.
# Bisher nur die Darstellung (Gerät · Hell · Dunkel) aus dem Umschalter im
# Kopfzeilen-Menü (base.html). JSON-Aufruf aus navigation.js; ohne JavaScript
# kommt ein normales Formular und die Antwort ist eine Umleitung zurück.
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import anfrage, darstellung
from app.db import get_session

router = APIRouter(prefix="/einstellungen")


def _zurueck_ziel(request: Request) -> str:
    """Nur eigene Seiten als Umleitungsziel (Referer ohne Host-Anteil)."""
    referer = request.headers.get("referer", "") or ""
    pfad = referer.split("://", 1)[-1]
    pfad = pfad[pfad.find("/"):] if "/" in pfad else "/"
    return pfad if pfad.startswith("/") and not pfad.startswith("//") else "/"


@router.post("/darstellung")
def darstellung_speichern(request: Request, session: Session = Depends(get_session)):
    """Speichert die Darstellung je Benutzer (benutzer_einstellungen, Key
    darstellung) und setzt das Cookie, das die Middleware vor dem Rendern liest."""
    benutzer = request.state.benutzer
    json_aufruf = "application/json" in (request.headers.get("content-type") or "")
    if json_aufruf:
        daten = anfrage.json_lesen(request) or {}
    else:
        daten = anfrage.formular(request)
    wert = daten.get("wert") or daten.get("darstellung") or ""
    gueltig = str(wert).strip().lower() in darstellung.WERTE
    wert = darstellung.speichern(session, benutzer.id, wert)
    session.commit()
    if json_aufruf or "application/json" in (request.headers.get("accept") or ""):
        antwort = JSONResponse({"ok": True, "darstellung": wert,
                                "hinweis": "" if gueltig else "Unbekannter Wert – auf „Gerät“ gesetzt."})
    else:
        antwort = RedirectResponse(_zurueck_ziel(request), status_code=303)
    darstellung.cookie_setzen(antwort, wert)
    return antwort


# --- v33 (PLAN_V20 Phase 174): Spalten je Nutzer für die Angebotstool-Tabellen -----------
# Alias der Lead-Route /lead-management/boards/spalten (gleiche Antworten, gleiche
# Ablage boards_spalten). Nötig, weil die Pfadtabelle der Projektierung (auth.py)
# /lead-management nicht enthält, /einstellungen aber seit v30 in jeder Rollenliste steht
# (GET und POST). lm_boards.js nimmt die Route aus data-lm-spalten-url
# (lead_boards.spalten_url). Logik und Rechte: app/routers/lm_boards.py.

@router.get("/spalten")
def spalten_holen(request: Request, session: Session = Depends(get_session)):
    from app.routers import lm_boards as lm_boards_router
    return lm_boards_router.spalten_holen_antwort(request, session)


@router.post("/spalten")
def spalten_speichern(request: Request, session: Session = Depends(get_session)):
    from app.routers import lm_boards as lm_boards_router
    return lm_boards_router.spalten_speichern_antwort(request, session)


# --- v33 (PLAN_V20 Phase 176, Agent N): eigene E-Mail-Signatur je Benutzer -----------------
# Der Außendienstler hinterlegt seine Outlook-Signatur selbst (Upload wie beim Innendienst,
# v6 [ANNAHME]) – sie steht unter der Nachfass-Mail aus seinem eigenen Postfach. Dieselbe
# Ablage (app/signaturen.py, data/signaturen/<benutzer_id>/) wie Parametrierung →
# Signaturen; hier aber NUR die eigene Signatur (keine fremden IDs, Rechte unverändert:
# /parametrierung bleibt Büro-Rollen vorbehalten). Rollen mit Mailversand: Außendienst,
# Innendienst, Admin – andere erhalten 403.

SIGNATUR_ROLLEN = ("aussendienst", "innendienst", "admin")


def _signatur_erlaubt(benutzer) -> bool:
    return benutzer is not None and benutzer.basisrolle in SIGNATUR_ROLLEN


def _signatur_seite(request: Request, meldung: str = ""):
    from fastapi.responses import Response
    from app import signaturen
    from app.templating import render
    benutzer = request.state.benutzer
    if not _signatur_erlaubt(benutzer):
        return Response("Kein Zugriff – Signaturen gibt es nur für Außendienst, Innendienst und Admin.",
                        status_code=403)
    html_vorschau, _bilder = signaturen.fuer_versand(benutzer.id)
    html_vorschau = html_vorschau.replace("cid:", "/einstellungen/signatur/bild/")
    return render(request, "einstellungen/signatur.html", aktiv="/einstellungen",
                  hochgeladen=signaturen.vorhanden(benutzer.id),
                  dateien=signaturen.dateien_auflisten(benutzer.id),
                  vorschau_html=html_vorschau, benutzer=benutzer,
                  mobil=benutzer.basisrolle == "aussendienst",
                  meldung=meldung or request.query_params.get("meldung", ""))


@router.get("/signatur")
def signatur_seite(request: Request):
    """Eigene Signatur ansehen/hochladen (Vorschau mit Inline-Bildern)."""
    return _signatur_seite(request)


@router.get("/signatur/bild/{cid}")
def signatur_bild(request: Request, cid: str):
    """Inline-Bild der eigenen Signatur für die Vorschau (cid → Datei)."""
    from fastapi.responses import FileResponse, Response
    from app import signaturen
    benutzer = request.state.benutzer
    if not _signatur_erlaubt(benutzer):
        return Response(status_code=403)
    _, bilder = signaturen.fuer_versand(benutzer.id)
    for bild_cid, pfad, mime in bilder:
        if bild_cid == cid:
            return FileResponse(pfad, media_type=mime)
    return Response(status_code=404)


@router.post("/signatur")
def signatur_speichern(request: Request):
    """Upload (.htm + Bilder, ersetzt die vorhandene) oder `aktion=entfernen` – immer nur
    die Signatur des angemeldeten Benutzers."""
    from urllib.parse import quote_plus
    from fastapi.responses import Response
    from app import signaturen
    benutzer = request.state.benutzer
    if not _signatur_erlaubt(benutzer):
        return Response(status_code=403)
    form = anfrage.formular(request)
    if form.get("aktion") == "entfernen":
        signaturen.entfernen(benutzer.id)
        return RedirectResponse("/einstellungen/signatur?meldung="
                                + quote_plus("Signatur entfernt – Standard-Signatur gilt"),
                                status_code=303)
    dateien = []
    for feld in form.getlist("dateien"):
        if hasattr(feld, "filename") and feld.filename:
            dateien.append((feld.filename, feld.file.read()))
    _ok, meldung = signaturen.speichern(benutzer.id, dateien)
    return RedirectResponse("/einstellungen/signatur?meldung=" + quote_plus(meldung),
                            status_code=303)
