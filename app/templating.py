# Jinja2-Templates und Basis-Render-Helfer (von main und allen Routern genutzt).

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

APP_ORDNER = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=APP_ORDNER / "templates")


def euro(cent) -> str:
    """Cent-Betrag in deutscher Formatierung: 123456 -> '1.234,56 €'."""
    if cent is None:
        return ""
    vz = "-" if cent < 0 else ""
    cent = abs(int(cent))
    euro_teil, cent_teil = divmod(cent, 100)
    return f"{vz}{euro_teil:,.0f}".replace(",", ".") + f",{cent_teil:02d} €"


def menge_format(wert) -> str:
    """Menge ohne unnötige Nachkommastellen: 1.0 -> '1', 2.5 -> '2,5'."""
    if wert is None:
        return ""
    if float(wert) == int(wert):
        return str(int(wert))
    return f"{wert}".replace(".", ",")


templates.env.filters["euro"] = euro
templates.env.filters["menge"] = menge_format

# Cache-Busting: Browser laden style.css nach jeder Änderung neu (Phase 18
# Nachfix). v14: pro Request frisch statt einmal beim Start – ein laufender
# Server lieferte sonst nach CSS-Änderungen weiter die alte Versionsnummer
# aus, und die Browser zeigten neue Templates mit gecachtem altem CSS.
def _css_version() -> int:
    try:
        return int((APP_ORDNER / "static" / "style.css").stat().st_mtime)
    except OSError:
        return 0


templates.env.globals["css_version"] = _css_version()   # Fallback

# Menü-Einträge (Phase 19: Dropdown oben rechts, rollenabhängig gefiltert)
NAVIGATION = [
    ("/leads", "Leads VOT"),
    ("/vorgaenge", "Vorgänge"),
    ("/erfassungen", "Erfassungen"),
    ("/angebote", "Angebote"),
    ("/statistik", "Statistik"),
    ("/kunden", "Kunden"),
    ("/artikel", "Artikel"),
    ("/benutzer", "Benutzer"),
    ("/versand", "Versand"),
    ("/parametrierung", "Parametrierung"),
]


def render(request: Request, template: str, **kontext):
    kontext.update({"request": request, "navigation": NAVIGATION,
                    "css_version": _css_version()})
    return templates.TemplateResponse(request, template, kontext)
