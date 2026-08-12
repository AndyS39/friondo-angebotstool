# E-Signatur (Phase 23): Vor-Ort-Modus – PDF-Vorschau + Touch-Signaturfeld.
# Nach der Signatur: Bild + Name + Zeitstempel in die Unterschriften-Seite,
# signiertes PDF unter data/angebote/signiert/, Status "Angenommen",
# Signaturprotokoll (Zeit, Benutzer, Gerät/IP) am Angebot.
# Fern-Modus (Token-Link) ist vorbereitet, aber standardmäßig deaktiviert.

import base64
import re
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import config
from app.db import get_session
from app.models import Angebot, Erfassung, Kunde
from app.templating import render

router = APIRouter(prefix="/signatur")


def _berechtigt(request: Request, angebot: Angebot, session: Session) -> bool:
    """Innendienst/Admin immer; Außendienst nur für Angebote der eigenen Erfassung."""
    benutzer = request.state.benutzer
    if benutzer is None:
        return False
    if benutzer.rolle in ("admin", "innendienst"):
        return True
    erfassung = (session.query(Erfassung)
                 .filter(Erfassung.angebot_id == angebot.id).first())
    return erfassung is not None and erfassung.benutzer_id == benutzer.id


@router.get("/{angebot_id}")
async def seite(request: Request, angebot_id: int,
                session: Session = Depends(get_session)):
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or not _berechtigt(request, angebot, session):
        return RedirectResponse("/erfassung", status_code=303)
    kunde = session.get(Kunde, angebot.kunde_id)
    return render(request, "signatur/seite.html", aktiv=None, mobil=True,
                  angebot=angebot, kunde=kunde,
                  jetzt=datetime.now(), fehler="")


@router.get("/{angebot_id}/pdf")
async def pdf_vorschau(request: Request, angebot_id: int,
                       session: Session = Depends(get_session)):
    """PDF-Vorschau mit Signatur-Berechtigung (auch für den Außendienst)."""
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or not _berechtigt(request, angebot, session):
        return RedirectResponse("/erfassung", status_code=303)
    from app import pdf_export
    pfad = pdf_export.pdf_fuer_angebot(session, angebot)
    return FileResponse(pfad, media_type="application/pdf",
                        content_disposition_type="inline",
                        filename=f"{angebot.nummer}.pdf")


@router.post("/{angebot_id}")
async def signieren(request: Request, angebot_id: int,
                    session: Session = Depends(get_session)):
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or not _berechtigt(request, angebot, session):
        return RedirectResponse("/erfassung", status_code=303)
    form = await request.form()
    name = (form.get("name") or "").strip()
    daten_url = form.get("signatur") or ""
    m = re.match(r"data:image/png;base64,(.+)$", daten_url)
    kunde = session.get(Kunde, angebot.kunde_id)
    if not name or m is None:
        return render(request, "signatur/seite.html", aktiv=None, mobil=True,
                      angebot=angebot, kunde=kunde, jetzt=datetime.now(),
                      fehler="Bitte Name eingeben und unterschreiben.")
    try:
        png_bytes = base64.b64decode(m.group(1))
    except ValueError:
        png_bytes = b""
    if len(png_bytes) < 200:   # leere/zu kleine Signatur
        return render(request, "signatur/seite.html", aktiv=None, mobil=True,
                      angebot=angebot, kunde=kunde, jetzt=datetime.now(),
                      fehler="Die Unterschrift ist leer – bitte erneut unterschreiben.")

    from app import pdf_export
    zeit = datetime.now()
    benutzer = request.state.benutzer
    pfad = pdf_export.signiertes_pdf_erzeugen(session, angebot, png_bytes, name, zeit)

    angebot.signiert_am = zeit
    angebot.signatur_name = name
    angebot.signierte_datei = str(pfad)
    geraet = request.headers.get("user-agent", "")[:150]
    ip = request.client.host if request.client else ""
    angebot.signatur_protokoll = (
        f"{zeit.strftime('%d.%m.%Y %H:%M:%S')} · Unterzeichner: {name} · "
        f"erfasst von: {benutzer.name} · IP: {ip} · Gerät: {geraet}")
    angebot.status = "Angenommen"
    erfassung = (session.query(Erfassung)
                 .filter(Erfassung.angebot_id == angebot.id).first())
    if erfassung is not None:
        erfassung.status = "Erledigt"
    session.commit()
    return render(request, "signatur/fertig.html", aktiv=None, mobil=True,
                  angebot=angebot, kunde=kunde)


@router.get("/{angebot_id}/signiert.pdf")
async def signiertes_pdf(request: Request, angebot_id: int,
                         session: Session = Depends(get_session)):
    angebot = session.get(Angebot, angebot_id)
    if (angebot is None or not _berechtigt(request, angebot, session)
            or not angebot.signierte_datei):
        return RedirectResponse("/erfassung", status_code=303)
    return FileResponse(angebot.signierte_datei, media_type="application/pdf",
                        content_disposition_type="inline",
                        filename=f"{angebot.nummer}-signiert.pdf")


@router.get("/extern/{token}")
async def fern_signatur(request: Request, token: str):
    """Fern-Modus (Token-Link an den Kunden): vorbereitet, aber deaktiviert,
    bis der öffentliche Zugang bzw. ein Signatur-Anbieter entschieden ist."""
    if not config.SIGNATUR_FERN_AKTIV:
        return render(request, "signatur/fern_inaktiv.html", aktiv=None, mobil=True)
    # Aktivierter Fern-Modus (nach Entscheidung): Token prüfen und Signaturseite zeigen
    from app.db import SessionLocal
    session = SessionLocal()
    try:
        angebot = (session.query(Angebot)
                   .filter(Angebot.signatur_token == token).first())
        if (angebot is None or angebot.signatur_token_gueltig_bis is None
                or angebot.signatur_token_gueltig_bis < datetime.now()):
            return render(request, "signatur/fern_inaktiv.html", aktiv=None, mobil=True)
        kunde = session.get(Kunde, angebot.kunde_id)
        return render(request, "signatur/seite.html", aktiv=None, mobil=True,
                      angebot=angebot, kunde=kunde, jetzt=datetime.now(), fehler="")
    finally:
        session.close()