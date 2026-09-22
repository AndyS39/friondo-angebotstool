# FastAPI-Grundgerüst des Friondo Angebotstools.
# Start: start.bat  bzw.  venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.auth import RollenMiddleware, standardbenutzer_anlegen
from app.db import init_db
from app.routers import (angebote, anmeldung, artikel, benutzer, erfassung, vorgaenge,
                         projektierung as projektierung_router,
                         glocke, leadmanagement as leadmanagement_router,
                         leads_api,
                         meine_angebote, montage,
                         erfassungsliste, konfiguration, konfigurator, kunden,
                         leads, signatur, statistik, versand)
from app.templating import render

APP_ORDNER = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    standardbenutzer_anlegen()
    # monday-Lesesync (Phase 22): Quellen vorbelegen + 15-Minuten-Scheduler
    from app import monday_sync
    from app.db import SessionLocal
    sitzung = SessionLocal()
    try:
        monday_sync.quellen_vorbelegen(sitzung)
    finally:
        sitzung.close()
    monday_sync.scheduler_starten()
    # Mail-Verlauf (Phase 27): Antworten der Angebots-Konversationen abrufen
    from app import mail_sync
    mail_sync.scheduler_starten()
    # 90-Tage-Prüflauf (v8): versendete Angebote ohne Reaktion → Abgelehnt
    from app import ablauf_pruefung
    ablauf_pruefung.scheduler_starten()
    # v11 (Phase 69): täglicher Fälligkeits-Lauf 07:00 + Tagesdigest 07:15
    from app import benachrichtigungen
    benachrichtigungen.scheduler_starten()
    # v12 (Phase 75): Lead-Postfach-Abruf alle 2 Minuten (nur parser_modus=an)
    from app import lead_parser
    lead_parser.scheduler_starten()
    # v12 (Phase 76/81): Wiedervorlage-Lauf 07:00 + Löschlauf 03:00
    from app import leadmanagement
    leadmanagement.scheduler_starten()
    # v12 (Phase 77): Geokodierung im Hintergrund (alle 5 Minuten)
    from app import geocoding
    geocoding.scheduler_starten()
    # v12 (Phase 78): Mail-Warteschlange (jede Minute, Sendesperre je Modus)
    from app import lead_mail
    lead_mail.scheduler_starten()
    yield


app = FastAPI(title="Friondo Angebotstool", lifespan=lifespan)

app.add_middleware(RollenMiddleware)

app.mount("/static", StaticFiles(directory=APP_ORDNER / "static"), name="static")

app.include_router(anmeldung.router)
app.include_router(vorgaenge.router)
app.include_router(projektierung_router.router)
app.include_router(glocke.router)
app.include_router(montage.router)
app.include_router(leadmanagement_router.router)
app.include_router(leads_api.router)
app.include_router(benutzer.router)
app.include_router(erfassung.router)
app.include_router(erfassungsliste.router)
app.include_router(leads.router)
app.include_router(signatur.router)
app.include_router(kunden.router)
app.include_router(artikel.router)
app.include_router(konfiguration.router)
app.include_router(konfigurator.router)
app.include_router(angebote.router)
app.include_router(statistik.router)
app.include_router(meine_angebote.router)
app.include_router(versand.router)


def _start_kontext() -> dict:
    """Kennzahlen für die Angebotstool-Kacheln (Startseite + /angebotstool)."""
    from app.db import SessionLocal
    from app.models import Angebot, Erfassung
    session = SessionLocal()
    try:
        offene_leads = _offene_leads_anzahl(session)
        offene_erfassungen = (session.query(Erfassung)
                              .filter(Erfassung.status.in_(["Neu", "In Bearbeitung"]),
                                      Erfassung.archiviert.is_(False))
                              .count())
        versendete = (session.query(Angebot)
                      .filter(Angebot.status == "Versendet",
                              Angebot.archiviert.is_(False)).count())
        # v10 (Phase 60): fällige Wiedervorlagen zählen VORGÄNGE –
        # rollenbezogen die Innendienst-Sicht (Verantwortlicher ID/unbekannt)
        from app.models import Benutzer, Vorgang
        from datetime import datetime as dt
        buero = {b.id for b in session.query(Benutzer)
                 if b.rolle in ("admin", "innendienst")}
        from app import leadmanagement
        faellige = sum(
            1 for v in leadmanagement.ohne_demo(session.query(Vorgang))
            .filter(Vorgang.wiedervorlage_am.isnot(None),
                    Vorgang.wiedervorlage_am <= dt.now())
            if v.wiedervorlage_benutzer_id is None
            or v.wiedervorlage_benutzer_id in buero)
        # v7: offene Individuell-Fälle (zu prüfen + in TAIFUN zu schreiben)
        individuell_offen = (session.query(Erfassung)
                             .filter(Erfassung.status.in_(
                                 ["Individuell – zu prüfen", "In TAIFUN zu schreiben"]),
                                     Erfassung.archiviert.is_(False))
                             .count())
        # v10 (Phase 59): offene AD-Rabatt-Freigaben
        from app.models import RabattFreigabe
        rabatt_freigaben = (session.query(RabattFreigabe)
                            .filter(RabattFreigabe.status == "offen").count())
    finally:
        session.close()
    return dict(faellige=faellige, offene_leads=offene_leads,
                offene_erfassungen=offene_erfassungen,
                individuell_offen=individuell_offen, versendete=versendete,
                rabatt_freigaben=rabatt_freigaben)


@app.get("/")
async def startseite(request: Request):
    """Portal (v9-Finale): drei große klickbare Karten – Lead-Management und
    Projektierung als „Coming soon“, in der Mitte das Angebotstool mit den
    „Auf einen Blick“-Zahlen. Nur Innendienst/Admin; Außendienst leitet die
    Rollen-Middleware bei „/“ automatisch auf die mobile Erfassung um."""
    from fastapi.responses import RedirectResponse
    benutzer = request.state.benutzer
    if benutzer is not None and benutzer.rolle == "aussendienst":
        return RedirectResponse("/erfassung", status_code=303)
    # v11 (Phase 68/70): Projektierungs-Karte – Live-Kacheln nur, wenn das
    # Modul für den Benutzer sichtbar ist (Demo-Modus: nur Admin)
    from app import projektierung as projektierung_modul
    from app.db import SessionLocal
    sitzung = SessionLocal()
    try:
        projekt_kacheln = None
        demo_badge = projektierung_modul.freigabe_modus(sitzung) == "admin"
        if projektierung_modul.modul_sichtbar(sitzung, benutzer):
            projekt_kacheln = projektierung_modul.startseiten_kacheln(sitzung)
        # v12 (Phase 79): Lead-Management-Karte – live nur bei Sichtbarkeit
        from app import leadmanagement
        lead_kacheln = None
        lead_demo_badge = leadmanagement.demo_aktiv(sitzung)
        lead_badge_text = leadmanagement.parameter_holen(
            sitzung, "demo_badge_text", "Demo · Coming soon")
        if leadmanagement.lead_modul_sichtbar(sitzung, benutzer):
            lead_kacheln = leadmanagement.startseiten_kacheln_leads(sitzung)
    finally:
        sitzung.close()
    return render(request, "index.html", aktiv=None,
                  projekt_kacheln=projekt_kacheln, demo_badge=demo_badge,
                  lead_kacheln=lead_kacheln, lead_demo_badge=lead_demo_badge,
                  lead_badge_text=lead_badge_text,
                  **_start_kontext())


@app.get("/angebotstool")
async def angebotstool(request: Request):
    """Angebotstool-Startansicht (Ebene 2): Shortcuts + klickbare Kacheln."""
    return render(request, "angebotstool.html", aktiv=None, **_start_kontext())


# v12 (Phase 73): /lead-management ist jetzt der Einstieg des Lead-Moduls
# (Router leadmanagement); Nicht-Sichtbare sehen dort weiter die Platzhalterseite.


# v11 (Phase 68): /projektierung ist jetzt das Kanban-Board des
# Projektierungs-Routers; die v9-Platzhalterseite entfällt.


def _offene_leads_anzahl(session) -> int:
    """v8: Leads mit VOT-Datum, bei denen noch mindestens eine Sparte offen ist."""
    from app.routers.leads import offene_leads
    return len(offene_leads(session))


@app.get("/konfiguration")
async def konfiguration_umleitung():
    """Alte Adresse – der Bereich heißt seit Phase 18 „Parametrierung“."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/parametrierung", status_code=301)
