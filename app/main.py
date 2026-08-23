# FastAPI-Grundgerüst des Friondo Angebotstools.
# Start: start.bat  bzw.  venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.auth import RollenMiddleware, standardbenutzer_anlegen
from app.db import init_db
from app.routers import (angebote, anmeldung, artikel, benutzer, erfassung,
                         erfassungsliste, konfiguration, konfigurator, kunden,
                         leads, signatur, versand)
from app.templating import render

APP_ORDNER = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    standardbenutzer_anlegen()
    # monday-Lesesync (Phase 22): Quellen vorbelegen + 15-Minuten-Scheduler
    from app import monday_sync
    from app.db import SessionLocal
    sitzung = SessionLocal()
    try:
        monday_sync.quellen_vorbelegen(sitzung)
    finally:
        sitzung.close()
    monday_sync.scheduler_starten()
    # Mail-Verlauf (Phase 27): Antworten der Angebots-Konversationen abrufen
    from app import mail_sync
    mail_sync.scheduler_starten()
    yield


app = FastAPI(title="Friondo Angebotstool", lifespan=lifespan)

app.add_middleware(RollenMiddleware)

app.mount("/static", StaticFiles(directory=APP_ORDNER / "static"), name="static")

app.include_router(anmeldung.router)
app.include_router(benutzer.router)
app.include_router(erfassung.router)
app.include_router(erfassungsliste.router)
app.include_router(leads.router)
app.include_router(signatur.router)
app.include_router(kunden.router)
app.include_router(artikel.router)
app.include_router(konfiguration.router)
app.include_router(konfigurator.router)
app.include_router(angebote.router)
app.include_router(versand.router)


@app.get("/")
async def startseite(request: Request):
    """Startseite (Phase 19): drei Shortcuts + klickbare Statistik-Kacheln."""
    from sqlalchemy import or_

    from app.db import SessionLocal
    from app.models import Angebot, Erfassung, Lead
    session = SessionLocal()
    try:
        offene_leads = _offene_leads_anzahl(session)
        offene_erfassungen = (session.query(Erfassung)
                              .filter(Erfassung.status.in_(["Neu", "In Bearbeitung"]),
                                      Erfassung.archiviert.is_(False))
                              .count())
        versendete = (session.query(Angebot)
                      .filter(Angebot.status == "Versendet",
                              Angebot.archiviert.is_(False)).count())
        from datetime import datetime as dt
        faellige = (session.query(Angebot)
                    .filter(Angebot.wiedervorlage_am.isnot(None),
                            Angebot.wiedervorlage_am <= dt.now(),
                            Angebot.archiviert.is_(False)).count())
    finally:
        session.close()
    return render(request, "index.html", aktiv=None,
                  faellige=faellige,
                  offene_leads=offene_leads,
                  offene_erfassungen=offene_erfassungen,
                  versendete=versendete)


def _offene_leads_anzahl(session) -> int:
    """Leads mit VOT-Datum, deren Erfassung fehlt oder noch Entwurf ist."""
    from sqlalchemy import or_

    from app.models import Erfassung, Lead
    return (session.query(Lead)
            .outerjoin(Erfassung, Lead.erfassung_id == Erfassung.id)
            .filter(Lead.vot_datum.isnot(None))
            .filter(Lead.ausgeblendet.is_(False))
            .filter(or_(Lead.erfassung_id.is_(None), Erfassung.status == "Entwurf"))
            .count())


@app.get("/konfiguration")
async def konfiguration_umleitung():
    """Alte Adresse – der Bereich heißt seit Phase 18 „Parametrierung“."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/parametrierung", status_code=301)
