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


_WOCHENTAGE = [("Mon", "Monday", "Mo", "Montag"),
               ("Tue", "Tuesday", "Di", "Dienstag"),
               ("Wed", "Wednesday", "Mi", "Mittwoch"),
               ("Thu", "Thursday", "Do", "Donnerstag"),
               ("Fri", "Friday", "Fr", "Freitag"),
               ("Sat", "Saturday", "Sa", "Samstag"),
               ("Sun", "Sunday", "So", "Sonntag")]


def de_datum(wert, format="%d.%m.%Y"):
    """strftime mit deutschen Wochentagen (Design-Fix 27.09.2026): %a/%A
    liefern in der C-Locale englische Namen (MON/TUE) – dieser Filter
    ersetzt sie, z. B. {{ termin | de_datum('%a %d.%m.') }} -> 'Mo 28.09.'."""
    if wert is None:
        return ""
    text = wert.strftime(format)
    en_kurz, en_lang, kurz, lang = _WOCHENTAGE[wert.weekday()]
    return text.replace(en_lang, lang).replace(en_kurz, kurz)


templates.env.filters["euro"] = euro
templates.env.filters["menge"] = menge_format
templates.env.filters["de_datum"] = de_datum

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

# Phase 94: Titel der Montage-Formulare für Formular-Aktionen in der Projektakte
from app.projektierung_logik import FORMULAR_NAMEN as _FORMULAR_NAMEN  # noqa: E402
templates.env.globals["formular_namen"] = _FORMULAR_NAMEN

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
