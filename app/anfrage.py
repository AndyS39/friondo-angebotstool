# v27 (PLAN_V17 Phase 128, „Blockierende Arbeit außerhalb der Event-Loop“):
# Alle Endpunkte des Tools sind seit v27 synchrone `def`-Routen und laufen im
# Starlette-Threadpool (WORKER_THREADS aus der .env) – Datenbank, PDF-Erzeugung,
# Excel-Importe und Datei-Uploads blockieren die Event-Loop damit nicht mehr.
# Formular und JSON einer Anfrage werden mit diesen Helfern gelesen: sie führen
# die asynchrone Starlette-Lesefunktion über anyio.from_thread in der Event-Loop
# aus (der Body liegt nach der RollenMiddleware ohnehin gepuffert vor).
#
# Muster:   form = anfrage.formular(request)        statt  await request.form()
#           daten = anfrage.json_lesen(request)      statt  await request.json()
#           inhalt = datei.file.read()              statt  await datei.read()

import asyncio
import contextvars

import anyio

# v27 (Befund B7 der Inventur): Werte, die Jinja-Globals ohne Request-Kontext
# brauchen (z. B. der Demo-Badge der Lead-Icon-Leiste), setzt die Middleware vor
# call_next in diese Kontextvariable – sie reicht bis in den Worker-Thread der
# def-Route und ins Rendern. So öffnet kein Global eine zweite Sitzung je Anfrage.
KONTEXT: contextvars.ContextVar[dict | None] = contextvars.ContextVar("anfrage_kontext", default=None)


def kontext_wert(name: str, standard=None):
    daten = KONTEXT.get()
    if daten is None:
        return standard
    return daten.get(name, standard)


def _in_loop(coro_funktion):
    """Coroutine-Funktion ohne Argumente in der Event-Loop ausführen.
    Aus einem anyio-Worker-Thread (FastAPI-Threadpool, TestClient) über
    from_thread.run; ohne Loop (direkter Aufruf in Tests) über asyncio.run."""
    try:
        return anyio.from_thread.run(coro_funktion)
    except RuntimeError:
        return asyncio.run(coro_funktion())


def formular(request):
    """Formulardaten (Starlette FormData, inkl. UploadFile) einer Anfrage."""
    return _in_loop(request.form)


def json_lesen(request):
    """JSON-Body einer Anfrage (wirft wie request.json bei ungültigem JSON)."""
    return _in_loop(request.json)


def body_lesen(request) -> bytes:
    return _in_loop(request.body)
