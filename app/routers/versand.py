# Versand-Verwaltung (Phase 17): Microsoft-Anmeldung des Innendienst-Nutzers
# per Device-Code, Statusanzeige, Abmelden.

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app import graph_versand
from app.templating import render

router = APIRouter(prefix="/versand")


@router.get("")
async def status(request: Request):
    return render(request, "versand/status.html", aktiv="/versand",
                  konfiguriert=graph_versand.konfiguriert(),
                  konto=graph_versand.angemeldeter_benutzer(),
                  flow=graph_versand.anmeldestatus(),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/anmelden")
async def anmelden():
    graph_versand.anmeldung_starten()
    return RedirectResponse("/versand", status_code=303)


@router.post("/abmelden")
async def abmelden():
    graph_versand.abmelden()
    return RedirectResponse("/versand?meldung=Abgemeldet", status_code=303)
