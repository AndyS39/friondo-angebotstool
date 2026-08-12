# Parametrierung (ehemals "Konfiguration", Phase 18): Logik-Excel einlesen,
# Validierungsbericht anzeigen, "Neu einlesen".

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import config, logik as logik_modul
from app.db import get_session
from app.templating import render

router = APIRouter(prefix="/parametrierung")


@router.get("")
async def uebersicht(request: Request, session: Session = Depends(get_session)):
    if not config.LOGIK_EXCEL_PFAD.exists():
        return render(request, "konfiguration/uebersicht.html", aktiv="/parametrierung",
                      logik=None, bericht=None, dateifehler=str(config.LOGIK_EXCEL_PFAD),
                      meldung="")
    logik, bericht = logik_modul.hole_logik(session)
    return render(request, "konfiguration/uebersicht.html", aktiv="/parametrierung",
                  logik=logik, bericht=bericht, dateifehler=None,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/neu-einlesen")
async def neu_einlesen(session: Session = Depends(get_session)):
    if not config.LOGIK_EXCEL_PFAD.exists():
        return RedirectResponse("/parametrierung", status_code=303)
    _, bericht = logik_modul.neu_einlesen(session)
    if bericht.ok:
        meldung = "Parametrierung+neu+eingelesen+–+keine+Fehler"
    else:
        meldung = f"Parametrierung+neu+eingelesen+–+{len(bericht.fehler)}+Fehler+gefunden"
    return RedirectResponse(f"/parametrierung?meldung={meldung}", status_code=303)
