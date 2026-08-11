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
                         versand)
from app.templating import render

APP_ORDNER = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    standardbenutzer_anlegen()
    yield


app = FastAPI(title="Friondo Angebotstool", lifespan=lifespan)

app.add_middleware(RollenMiddleware)

app.mount("/static", StaticFiles(directory=APP_ORDNER / "static"), name="static")

app.include_router(anmeldung.router)
app.include_router(benutzer.router)
app.include_router(erfassung.router)
app.include_router(erfassungsliste.router)
app.include_router(kunden.router)
app.include_router(artikel.router)
app.include_router(konfiguration.router)
app.include_router(konfigurator.router)
app.include_router(angebote.router)
app.include_router(versand.router)


@app.get("/")
async def startseite(request: Request):
    return render(request, "index.html", aktiv=None)
