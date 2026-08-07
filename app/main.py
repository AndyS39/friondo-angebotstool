# FastAPI-Grundgerüst des Friondo Angebotstools.
# Start: start.bat  bzw.  venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import init_db

APP_ORDNER = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Friondo Angebotstool", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=APP_ORDNER / "static"), name="static")
templates = Jinja2Templates(directory=APP_ORDNER / "templates")

# Navigation: (URL-Pfad, Beschriftung) – wird im Basis-Layout gerendert.
NAVIGATION = [
    ("/kunden", "Kunden"),
    ("/artikel", "Artikel"),
    ("/angebote", "Angebote"),
    ("/konfiguration", "Konfiguration"),
]


def render(request: Request, template: str, **kontext):
    kontext.update({"request": request, "navigation": NAVIGATION})
    return templates.TemplateResponse(request, template, kontext)


@app.get("/")
async def startseite(request: Request):
    return render(request, "index.html", aktiv=None)


@app.get("/kunden")
async def kunden(request: Request):
    return render(request, "platzhalter.html", aktiv="/kunden",
                  titel="Kunden", hinweis="Die Kundenverwaltung folgt in Phase 1.")


@app.get("/artikel")
async def artikel(request: Request):
    return render(request, "platzhalter.html", aktiv="/artikel",
                  titel="Artikel", hinweis="Der Preislisten-Import folgt in Phase 2.")


@app.get("/angebote")
async def angebote(request: Request):
    return render(request, "platzhalter.html", aktiv="/angebote",
                  titel="Angebote", hinweis="Die Angebotserstellung folgt in Phase 5.")


@app.get("/konfiguration")
async def konfiguration(request: Request):
    return render(request, "platzhalter.html", aktiv="/konfiguration",
                  titel="Konfiguration",
                  hinweis="Der Import der Logik-Excel folgt in Phase 3.")
