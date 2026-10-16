# v36 (PLAN_V22 Phase 188/190, Agent A3): Parametrierung → Angebots-PDF (Admin).
# Eigene Router-Datei (Prefix /parametrierung wie konfiguration_heizreport.py): Browser des
# Druckers (Kanal/Pfad, Version, Stand aus pdf_html.status()), Knopf „Test-PDF erzeugen“
# (Demo-Angebot über die Sparten-Vorlage, sobald sie vorliegt – sonst die Probeseite; Dauer in ms,
# Download), Engine-Schalter html | fpdf2, Hinweis auf fehlende Bilder/Schriften, Ergebnis des
# letzten Browser-Tests (Einstellung pdf_letzter_test – Go-live-Punkt), Änderungsprotokoll
# (Einstellung pdf_protokoll, letzte 30). Der Browser-Druck ist Prozess-I/O und läuft nach
# verbindung_freigeben (v27-Regel) – nie mit gehaltener Datenbankverbindung.
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import anfrage, config, pdf_html
from app.db import get_session, verbindung_freigeben
from app.templating import render

router = APIRouter(prefix="/parametrierung")

SEITE = "/parametrierung/angebots-pdf"


def _nur_admin(request: Request):
    benutzer = request.state.benutzer
    if benutzer is None or benutzer.basisrolle != "admin":
        return RedirectResponse("/parametrierung", status_code=303)
    return None


def _zurueck(meldung: str, anker: str = "") -> RedirectResponse:
    return RedirectResponse(f"{SEITE}?meldung={quote_plus(meldung)}{anker}", status_code=303)


def _edge_pfade() -> list[dict]:
    """Standardpfade von Edge/Chrome auf Windows – nur Anzeige (Vorhanden ja/nein)."""
    import os
    kandidaten = []
    for basis in (os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                  os.environ.get("ProgramFiles", r"C:\Program Files")):
        kandidaten.append(("Edge", rf"{basis}\Microsoft\Edge\Application\msedge.exe"))
        kandidaten.append(("Chrome", rf"{basis}\Google\Chrome\Application\chrome.exe"))
    from pathlib import Path
    return [{"name": name, "pfad": pfad, "vorhanden": Path(pfad).is_file()} for name, pfad in kandidaten]


@router.get("/angebots-pdf")
def angebots_pdf_seite(request: Request, session: Session = Depends(get_session)):
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    engine = pdf_html.engine(session)
    letzter = pdf_html.letzter_test(session)
    return render(request, "konfiguration/angebots_pdf.html", aktiv="/parametrierung",
                  engine=engine, engine_namen=pdf_html.ENGINE_NAMEN,
                  status=pdf_html.status(), letzter_test=letzter,
                  browser_pfad_env=config.PDF_BROWSER_PFAD, edge_pfade=_edge_pfade(),
                  dateien=pdf_html.dateien_pruefen(), vorlagen=pdf_html.vorlagen_stand(),
                  test_pdf_vorhanden=pdf_html.TEST_PDF_PFAD.is_file(),
                  temp_ordner=str(pdf_html.TEMP_ORDNER),
                  parallel=pdf_html.PARALLEL, timeout_s=pdf_html.TIMEOUT_S,
                  zielzeit_s=pdf_html.ZIELZEIT_S,
                  protokoll=pdf_html.protokoll(session),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/angebots-pdf")
def angebots_pdf_speichern(request: Request, session: Session = Depends(get_session)):
    """Engine-Schalter html | fpdf2 (protokolliert)."""
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    gewuenscht = (form.get("pdf_engine") or "").strip().lower()
    if gewuenscht not in (pdf_html.ENGINE_HTML, pdf_html.ENGINE_FPDF2):
        return _zurueck("Unbekannte Engine – nichts geändert.")
    alt = pdf_html.engine(session)
    if alt == gewuenscht:
        return _zurueck("Keine Änderungen.")
    neu = pdf_html.engine_setzen(session, gewuenscht)
    pdf_html.protokollieren(session, request.state.benutzer, [f"pdf_engine: {alt} → {neu}"])
    session.commit()
    return _zurueck(f"Angebots-PDF: Engine auf „{neu}“ gestellt – {pdf_html.ENGINE_NAMEN[neu]}.")


@router.post("/angebots-pdf/test")
def angebots_pdf_test(request: Request, session: Session = Depends(get_session)):
    """Knopf „Test-PDF erzeugen“: Demo-Angebot (pdf_kontext.demo_kontext) über die Sparten-Vorlage,
    solange sie fehlt die Probeseite; Ergebnis in pdf_letzter_test, PDF zum Download im Temp-Ordner."""
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    sparte = (form.get("sparte") or "WP").strip().upper()
    benutzer = request.state.benutzer
    verbindung_freigeben(session)          # Browser-Druck = Prozess-I/O ohne gehaltene Verbindung
    ergebnis = pdf_html.browser_test(sparte, vollstaendig=True)
    if ergebnis["ok"] and ergebnis.get("pdf"):
        try:
            pdf_html.TEST_PDF_PFAD.parent.mkdir(parents=True, exist_ok=True)
            pdf_html.TEST_PDF_PFAD.write_bytes(ergebnis["pdf"])
        except OSError:
            pass
    daten = pdf_html.letzten_test_merken(session, ergebnis)
    if ergebnis["ok"]:
        text = (f"Test-PDF erzeugt: {ergebnis['vorlage']}, {ergebnis['seiten']} Seite(n), "
                f"{ergebnis['bytes'] // 1024} KB in {ergebnis['dauer_ms']} ms "
                f"({ergebnis['browser']} {ergebnis['version']}).")
        pdf_html.protokollieren(session, benutzer, [f"Test-PDF ok: {ergebnis['vorlage']}, {ergebnis['dauer_ms']} ms"])
    else:
        text = f"Test-PDF fehlgeschlagen: {ergebnis['fehler']}"
        pdf_html.protokollieren(session, benutzer, [f"Test-PDF fehlgeschlagen: {ergebnis['fehler'][:160]}"])
    session.commit()
    return _zurueck(text + f" (Stand {daten['zeit']})", "#test")


@router.get("/angebots-pdf/test.pdf")
def angebots_pdf_test_download(request: Request):
    """Download des zuletzt erzeugten Test-PDFs (ohne Datenbank)."""
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    if not pdf_html.TEST_PDF_PFAD.is_file():
        return _zurueck("Noch kein Test-PDF erzeugt – zuerst „Test-PDF erzeugen“.", "#test")
    return FileResponse(pdf_html.TEST_PDF_PFAD, media_type="application/pdf",
                        content_disposition_type="inline", filename="Angebots-PDF-Test.pdf")
