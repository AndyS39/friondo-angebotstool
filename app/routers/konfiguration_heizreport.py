# v26 (PLAN_PROJ_V5 Phase 122): Parametrierung → Heizreport (Admin).
# Eigene Router-Datei (Prefix /parametrierung wie konfiguration.py): Zugang
# (Modus v2 | generisch, Token maskiert, Verbindungstest), Kennzahlen
# (Phase 123, JSON-Parameter mit Vorlage und Vorschau), Ablage (Galerie-Ordner
# für das Heizreport-PDF), Portal-Link (url_heizreport, aus den Projektierung-
# Einstellungen umgezogen), Ergebnis-Pfad (heizreport_pfad_heizlast) und der
# aufklappbare generische Client (v17). Der Token wird nie ausgegeben – weder
# im Formular noch im Änderungsprotokoll.
import json
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import galerie, heizreport_api
from app import projektierung as kern
from app.db import get_session
from app.templating import render
from app import anfrage   # v27: Formular/JSON in def-Routen

router = APIRouter(prefix="/parametrierung")

GENERISCH_FELDER = tuple(n for n in heizreport_api.PARAMETER if n != "heizreport_api_key")


def _nur_admin(request: Request):
    benutzer = request.state.benutzer
    if benutzer is None or benutzer.rolle != "admin":
        return RedirectResponse("/parametrierung", status_code=303)
    return None


def _werte(session) -> dict:
    werte = {name: heizreport_api.p(session, name) for name in GENERISCH_FELDER}
    werte["heizreport_mapping_hin"] = (werte["heizreport_mapping_hin"]
                                       or heizreport_api.MAPPING_HIN_START)
    werte["heizreport_mapping_zurueck"] = (werte["heizreport_mapping_zurueck"]
                                           or heizreport_api.MAPPING_ZURUECK_START)
    werte["heizreport_auth_art"] = werte["heizreport_auth_art"] or "header"
    return werte


def _generisch_speichern(session, form) -> list[str]:
    """Felder des generischen Clients (v17) – nur wenn das Formular sie mitschickt."""
    aenderungen = []
    if "heizreport_api_url" not in form:
        return aenderungen
    for name in GENERISCH_FELDER:
        wert = (form.get(name) or "").strip()
        if name == "heizreport_auth_art" and wert not in ("header", "bearer", "basic", "body"):
            wert = "header"
        if name.startswith("heizreport_methode_") and wert not in ("", "GET", "POST", "PUT"):
            wert = ""
        if name.startswith("heizreport_mapping_") and wert:
            try:
                json.loads(wert)
            except ValueError:
                continue                       # ungültiges JSON nicht übernehmen
        alt = heizreport_api.p(session, name)
        if alt != wert:
            kern.parameter_setzen(session, name, wert[:5000])
            aenderungen.append(f"{name}: „{alt[:60]}“ → „{wert[:60]}“")
    return aenderungen


def _speichern(session, form, benutzer) -> tuple[str, str]:
    """Speichert alle Abschnitte; liefert (Meldung, Fehlertext)."""
    aenderungen: list[str] = []
    fehler = ""
    # Zugang
    modus = (form.get("heizreport_modus") or "").strip().lower()
    if modus in heizreport_api.MODI:
        alt = heizreport_api.modus(session)
        if alt != modus:
            kern.parameter_setzen(session, "heizreport_modus", modus)
            aenderungen.append(f"heizreport_modus: {alt} → {modus}")
    token_neu = (form.get("heizreport_api_key") or "").strip()
    if form.get("heizreport_token_entfernen"):
        if heizreport_api.token(session):
            kern.parameter_setzen(session, "heizreport_api_key", "")
            aenderungen.append("Token entfernt")
    elif token_neu:
        kern.parameter_setzen(session, "heizreport_api_key", token_neu[:500])
        aenderungen.append("Token gesetzt")
    # Kennzahlen (Phase 123)
    if "heizreport_kennzahlen" in form:
        text = (form.get("heizreport_kennzahlen") or "").strip()
        problem = heizreport_api.kennzahlen_pruefen(text)
        if problem:
            fehler = problem
        elif text != heizreport_api.kennzahlen_roh(session):
            kern.parameter_setzen(session, "heizreport_kennzahlen", text[:10000])
            aenderungen.append("heizreport_kennzahlen geändert")
    # Ablage
    if "heizreport_pdf_ordner" in form:
        ordner = (form.get("heizreport_pdf_ordner") or "").strip()
        if ordner and ordner in galerie.ordner_liste(session, "WP"):
            alt = heizreport_api.p(session, "heizreport_pdf_ordner")
            if alt != ordner:
                kern.parameter_setzen(session, "heizreport_pdf_ordner", ordner)
                aenderungen.append(f"heizreport_pdf_ordner: „{alt}“ → „{ordner}“")
    # Portal-Link + Ergebnis-Pfad
    for name, laenge in (("url_heizreport", 300), ("heizreport_pfad_heizlast", 200)):
        if name in form:
            wert = (form.get(name) or "").strip()[:laenge]
            alt = heizreport_api.p(session, name)
            if alt != wert:
                kern.parameter_setzen(session, name, wert)
                aenderungen.append(f"{name}: „{alt}“ → „{wert}“")
    aenderungen.extend(_generisch_speichern(session, form))
    heizreport_api.protokollieren(session, benutzer, aenderungen)
    meldung = "Heizreport-Einstellungen gespeichert." if aenderungen else "Keine Änderungen."
    if fehler:
        meldung = f"{fehler} – Kennzahlen nicht gespeichert."
    return meldung, fehler


@router.get("/heizreport")
def heizreport_seite(request: Request, session: Session = Depends(get_session)):
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    return render(request, "konfiguration/heizreport.html", aktiv="/parametrierung",
                  modus=heizreport_api.modus(session),
                  token_gesetzt=bool(heizreport_api.token(session)),
                  konfiguriert=heizreport_api.konfiguriert(session),
                  kennzahlen_text=heizreport_api.kennzahlen_roh(session),
                  kennzahlen_vorlage=json.dumps(heizreport_api.KENNZAHLEN_VORLAGE,
                                                ensure_ascii=False, indent=2),
                  kennzahlen_vorschau=heizreport_api.kennzahlen_vorschau(session),
                  pdf_ordner=heizreport_api.p(session, "heizreport_pdf_ordner",
                                              heizreport_api.PDF_ORDNER_STANDARD),
                  ordner_liste=galerie.ordner_liste(session, "WP"),
                  url_heizreport=heizreport_api.p(session, "url_heizreport"),
                  pfad_heizlast=heizreport_api.p(session, "heizreport_pfad_heizlast",
                                                 heizreport_api.PFAD_HEIZLAST_STANDARD),
                  pfad_standard=heizreport_api.PFAD_HEIZLAST_STANDARD,
                  generisch=_werte(session),
                  protokoll=heizreport_api.protokoll(session),
                  basis_url=heizreport_api.BASIS_V2,
                  test=request.query_params.get("test", ""),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/heizreport")
def heizreport_speichern(request: Request, session: Session = Depends(get_session)):
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    meldung, _fehler = _speichern(session, form, request.state.benutzer)
    session.commit()
    return RedirectResponse("/parametrierung/heizreport?meldung=" + quote_plus(meldung),
                            status_code=303)


@router.post("/heizreport/test")
def heizreport_verbindung_testen(request: Request,
                                       session: Session = Depends(get_session)):
    """Button „Verbindung testen“: Formularstand zuerst übernehmen, dann
    v2: GET /health → GET / → GET /reports (Meldung wörtlich laut Plan)."""
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    _speichern(session, form, request.state.benutzer)
    session.commit()
    _ok, text = heizreport_api.verbindung_testen(session)
    session.commit()
    return RedirectResponse("/parametrierung/heizreport?test=" + quote_plus(text)
                            + "#zugang", status_code=303)
