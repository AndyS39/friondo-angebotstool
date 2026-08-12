# Leichtgewichtige Anmeldung (Phase 13): Benutzerliste + PIN, signiertes
# Session-Cookie, Rollen-Durchsetzung per Middleware.
# Außendienst sieht ausschließlich die mobile Erfassung – nie Preise, EK,
# Deckungsbeitrag oder den Angebotsbereich.

import hashlib
import hmac
import secrets

from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app import config
from app.db import SessionLocal
from app.models import Benutzer

COOKIE_NAME = "angebotstool_sitzung"

# Pfade ohne Anmeldung; Außendienst-Pfade; Admin-exklusive Pfade
OFFENE_PFADE = ("/login", "/logout", "/static")
AUSSENDIENST_PFADE = ("/erfassung", "/leads", "/login", "/logout", "/static")
ADMIN_PFADE = ("/benutzer",)
BUERO_ROLLEN = ("admin", "innendienst")


def _geheimnis() -> bytes:
    """Signierschlüssel: aus .env (SESSION_SECRET) oder persistent aus data/."""
    aus_env = getattr(config, "SESSION_SECRET", "") or ""
    if aus_env:
        return aus_env.encode()
    pfad = config.DATA_ORDNER / ".session_secret"
    if not pfad.exists():
        config.DATA_ORDNER.mkdir(parents=True, exist_ok=True)
        pfad.write_text(secrets.token_hex(32), encoding="ascii")
    return pfad.read_text(encoding="ascii").strip().encode()


def pin_hash(pin: str) -> str:
    return hashlib.sha256(("friondo:" + pin).encode()).hexdigest()


def _signatur(benutzer_id: int) -> str:
    return hmac.new(_geheimnis(), str(benutzer_id).encode(), hashlib.sha256).hexdigest()


def cookie_wert(benutzer_id: int) -> str:
    return f"{benutzer_id}:{_signatur(benutzer_id)}"


def benutzer_aus_cookie(wert: str, session: Session):
    if not wert or ":" not in wert:
        return None
    kennung, signatur = wert.split(":", 1)
    if not kennung.isdigit() or not hmac.compare_digest(signatur, _signatur(int(kennung))):
        return None
    benutzer = session.get(Benutzer, int(kennung))
    if benutzer is None or not benutzer.aktiv:
        return None
    return benutzer


def standardbenutzer_anlegen() -> None:
    """Beim Start: ohne Benutzer wäre das Tool ausgesperrt – Admin (PIN 1234) anlegen.
    Migration Phase 18: gibt es noch keinen Benutzer mit Rolle admin, wird der
    Benutzer „Admin“ auf die neue Admin-Rolle gehoben."""
    session = SessionLocal()
    try:
        if session.query(Benutzer).count() == 0:
            session.add(Benutzer(name="Admin", rolle="admin",
                                 pin_hash=pin_hash("1234")))
            session.commit()
        elif not session.query(Benutzer).filter(Benutzer.rolle == "admin").count():
            admin = session.query(Benutzer).filter(Benutzer.name == "Admin").first()
            if admin is not None:
                admin.rolle = "admin"
                session.commit()
    finally:
        session.close()


class RollenMiddleware(BaseHTTPMiddleware):
    """Setzt request.state.benutzer und erzwingt die Rollen-Sicht:
    Außendienst nur /erfassung, Innendienst alles."""

    async def dispatch(self, request: Request, call_next):
        pfad = request.url.path
        session = SessionLocal()
        try:
            benutzer = benutzer_aus_cookie(request.cookies.get(COOKIE_NAME, ""), session)
            request.state.benutzer = benutzer
            if pfad.startswith(OFFENE_PFADE):
                return await call_next(request)
            if benutzer is None:
                return RedirectResponse("/login", status_code=303)
            if benutzer.rolle not in BUERO_ROLLEN and not pfad.startswith(AUSSENDIENST_PFADE):
                return RedirectResponse("/erfassung", status_code=303)
            if benutzer.rolle == "innendienst" and pfad.startswith(ADMIN_PFADE):
                return RedirectResponse("/", status_code=303)
            return await call_next(request)
        finally:
            session.close()
