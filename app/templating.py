# Jinja2-Templates und Basis-Render-Helfer (von main und allen Routern genutzt).

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

APP_ORDNER = Path(__file__).resolve().parent

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
