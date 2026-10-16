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


# --- v35 (PLAN_LEAD_V6 Phase 185, Agent R): „Mein Profil“ – Profilbild je Benutzer -----------
# Jede Rolle (Menüpunkt in base.html): Bild hochladen (JPG/PNG, max. 2 MB, quadratischer
# Zuschnitt im Browser über profil_v35.js UND serverseitig mit Pillow, app/profilbild.py),
# Vorschau, Entfernen. Ablage wie v29 (data/benutzerbilder/<id>.jpg, benutzer.bild_datei) –
# das Bild ersetzt die Initialen-Avatare (Makros avatar/_tabelle/Kartei/HV-Ansicht/Mein Tag)
# und steht in der Terminbestätigung ({vertriebler_block}). Admin setzt Bilder weiterhin in
# der Benutzerverwaltung (AD-Profil). Zusätzlich [ANNAHME]: Vorname und Telefon pflegt der
# Benutzer hier selbst (beide erscheinen in der Terminbestätigung/„Hallo, <Vorname>“); Name,
# E-Mail und Rolle bleiben Sache des Admins.
# v27-Regel: die Upload-Route liest das Formular VOR dem ersten Datenbankzugriff und schreibt
# die Datei ohne offene Sitzung; erst danach die kurze Schreibtransaktion (bild_datei).

from urllib.parse import quote_plus  # noqa: E402 – Meldungen der Profil-Routen

PROFIL_PFAD = "/einstellungen/profil"


def _rollen_text(benutzer) -> str:
    """Anzeigename(n) der Rollen aus dem Katalog (v33), z. B. „Außendienst · Handelsvertreter“."""
    try:
        from app import rollen as rollen_modul
        namen = rollen_modul.namen()
    except Exception:   # noqa: BLE001
        namen = {}
    return " · ".join(namen.get(r, r) for r in benutzer.rollen_liste)


@router.get("/profil")
def profil_seite(request: Request, session: Session = Depends(get_session)):
    """Eigenes Profil: Bild (Vorschau/Upload/Entfernen), Vorname, Telefon; Name, E-Mail und
    Rolle nur zur Anzeige."""
    from app import profilbild
    from app.models import Benutzer
    from app.templating import render
    benutzer = request.state.benutzer
    person = session.get(Benutzer, benutzer.id) if benutzer is not None else None
    if person is None:
        return RedirectResponse("/login", status_code=303)
    anzeige = (f"{person.vorname} {person.name}".strip() if person.vorname
               and person.vorname.lower() not in person.name.lower() else person.name)
    return render(request, "einstellungen/profil.html", aktiv="/einstellungen",
                  person=person, anzeige_name=anzeige, rollen_text=_rollen_text(person),
                  bild_url=profilbild.url_fuer(person.id),
                  mobil=person.basisrolle in ("aussendienst", "montage"),
                  max_mb=profilbild.MAX_BYTES // (1024 * 1024), kante=profilbild.KANTE,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/profil")
def profil_speichern(request: Request, session: Session = Depends(get_session)):
    """Vorname und Telefon des angemeldeten Benutzers [ANNAHME: Selbstpflege dieser
    beiden Felder]; Name/E-Mail/Rolle ändert nur der Admin (Benutzerverwaltung)."""
    from app.models import Benutzer
    form = anfrage.formular(request)
    benutzer = request.state.benutzer
    person = session.get(Benutzer, benutzer.id) if benutzer is not None else None
    if person is None:
        return RedirectResponse("/login", status_code=303)
    if form.get("vorname") is not None:
        person.vorname = (form.get("vorname") or "").strip()[:100]
    if form.get("telefon") is not None:
        person.telefon = (form.get("telefon") or "").strip()[:50]
    session.commit()
    return RedirectResponse(PROFIL_PFAD + "?meldung=" + quote_plus("Profil gespeichert."),
                            status_code=303)


@router.post("/profil/bild")
def profil_bild_speichern(request: Request, session: Session = Depends(get_session)):
    """Upload (Feld `bild`, JPG/PNG ≤ 2 MB) oder `aktion=entfernen` – immer nur das eigene
    Bild. Formular und Bilddatei VOR dem ersten Datenbankzugriff (Upload = Netz-I/O, v27),
    Datei ohne offene Sitzung schreiben, danach nur bild_datei setzen."""
    from app import profilbild
    from app.models import Benutzer
    form = anfrage.formular(request)
    benutzer = request.state.benutzer
    if benutzer is None:
        return RedirectResponse("/login", status_code=303)
    if form.get("aktion") == "entfernen":
        profilbild.entfernen(benutzer.id)
        person = session.get(Benutzer, benutzer.id)
        if person is not None:
            person.bild_datei = ""
            session.commit()
        return RedirectResponse(PROFIL_PFAD + "?meldung=" + quote_plus("Profilbild entfernt."),
                                status_code=303)
    datei = form.get("bild")
    daten = b""
    if datei is not None and getattr(datei, "filename", ""):
        daten = datei.file.read(profilbild.MAX_BYTES + 1)
    ok, meldung, rel = profilbild.speichern(benutzer.id, daten)
    if ok:
        person = session.get(Benutzer, benutzer.id)
        if person is not None:
            person.bild_datei = rel
            session.commit()
    return RedirectResponse(PROFIL_PFAD + "?meldung=" + quote_plus(meldung), status_code=303)


@router.get("/profil/bild/{benutzer_id}")
def profil_bild(request: Request, benutzer_id: int):
    """Profilbild eines Benutzers für die Avatare (jede angemeldete Rolle); 404 ohne Bild.
    Cache-Header: privat, ein Tag – die Avatar-URL trägt ?v=<Änderungszeit> (profilbild.url_fuer),
    nach einem Upload laden Browser also sofort das neue Bild. Kein Datenbankzugriff."""
    from fastapi.responses import FileResponse, Response
    from app import profilbild
    if getattr(request.state, "benutzer", None) is None:
        return Response(status_code=404)
    pfad = profilbild.pfad_fuer(benutzer_id)
    if pfad is None:
        return Response(status_code=404)
    return FileResponse(str(pfad), media_type=profilbild.mime_fuer(pfad),
                        headers={"Cache-Control": "private, max-age=86400"})
