# FastAPI-Grundgerüst des Friondo Angebotstools.
# Start: start.bat  bzw.  venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import artikel, konfiguration, konfigurator, kunden
from app.templating import render

APP_ORDNER = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Friondo Angebotstool", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=APP_ORDNER / "static"), name="static")

app.include_router(kunden.router)
app.include_router(artikel.router)
app.include_router(konfiguration.router)
app.include_router(konfigurator.router)


@app.get("/")
async def startseite(request: Request):
    return render(request, "index.html", aktiv=None)


@app.get("/angebote")
async def angebote(request: Request):
    return render(request, "platzhalter.html", aktiv="/angebote",
                  titel="Angebote", hinweis="Die Angebotserstellung folgt in Phase 5.")
