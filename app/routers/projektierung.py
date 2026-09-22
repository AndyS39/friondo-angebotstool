# Projektierung V1 (v11): Router des Moduls – Phase 66: „Angebot → Projekt"
# (Dialog + Anlage + Versionsfolge + Storno), Phase 67: Projektakte,
# Phase 68: Kanban/Liste/Termine/Meine Aufgaben. Alle Routen laufen durch das
# Demo-Gate (freigabe_modus, Phase 70): Standard = nur Admin.

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import projektierung as kern
from app import projektierung_logik
from app.db import get_session
from app.models import (Angebot, Aufgabe, AufgabenpaketInstanz, Benutzer,
                        Gewerk, Kunde, Lead, Projekt, ProjektDokument,
                        ProjektSub, ProjektTermin, ProjektVerlauf,
                        Subunternehmer, Team, Vorgang,
                        GEWERK_PHASEN, GEWERK_PHASEN_NAMEN, AUFGABE_STATUS_NAMEN)
from app.templating import render

router = APIRouter(prefix="/projektierung")

# Rollen, die Projekte anlegen/bearbeiten dürfen (nach Freischaltung)
_SCHREIB_ROLLEN = ("admin", "innendienst", "projektierung")


def _gate(request: Request, session: Session, schreiben: bool = False):
    """Server-seitiges Modul-Gate (Phase 70): im Demo-Modus nur Admin;
    nach Freischaltung die Rollentabelle. None = Zugriff erlaubt."""
    benutzer = request.state.benutzer
    if benutzer is None or not kern.modul_sichtbar(session, benutzer):
        return RedirectResponse("/", status_code=303)
    if schreiben and not any(benutzer.hat_rolle(r) for r in _SCHREIB_ROLLEN):
        return RedirectResponse("/", status_code=303)
    return None


def _benutzer_mit_rolle(session: Session, rolle: str) -> list[Benutzer]:
    """Dropdown-Kandidaten: Benutzer mit der Zusatz-/Hauptrolle, sonst Büro."""
    alle = session.query(Benutzer).filter(Benutzer.aktiv.is_(True)).all()
    treffer = [b for b in alle if b.hat_rolle(rolle)]
    return sorted(treffer or [b for b in alle
                              if b.rolle in ("admin", "innendienst")],
                  key=lambda b: b.name)


# --- Phase 66: Angebot → Projekt ------------------------------------------------

@router.get("/angebot/{angebot_id}/projekt")
async def projekt_dialog(request: Request, angebot_id: int,
                         session: Session = Depends(get_session)):
    """Dialog „Angebot → Projekt": Kopf mit Kunde + Ausführungsadresse
    (editierbar), Vorschlag „zu offenem Projekt des Vorgangs hinzufügen",
    Sparten-Häkchen, Zuweisungen, Bemerkung."""
    if (umleitung := _gate(request, session, schreiben=True)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or angebot.status != "Angenommen":
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "„Angebot → Projekt“ geht nur bei angenommenen Angeboten."),
            status_code=303)
    if angebot.projekt_gewerk_id:
        gewerk = session.get(Gewerk, angebot.projekt_gewerk_id)
        if gewerk is not None:
            return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}",
                                    status_code=303)
    from app import vorgaenge as vorgaenge_modul
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    session.commit()
    kunde = session.get(Kunde, angebot.kunde_id)
    offenes = kern.offenes_projekt_fuer_vorgang(session, vorgang.id)
    # Sparten: Tool-Angebot = seine Sparte; TAIFUN = alle Lead-Interessen wählbar
    sparte = angebot.konfigurator_typ or "WP"
    waehlbar = [sparte]
    if angebot.extern and vorgang.lead_id:
        lead = session.get(Lead, vorgang.lead_id)
        if lead is not None and lead.interessen:
            waehlbar = sorted(set(lead.interessen) | {sparte},
                              key=["WP", "PV", "KL", "WB"].index)
    belegt = set()
    if offenes is not None:
        belegt = {g.sparte for g in session.query(Gewerk)
                  .filter(Gewerk.projekt_id == offenes.id,
                          Gewerk.phase != "storniert")}
    def standard(name):
        wert = kern.parameter_holen(session, name, "")
        return int(wert) if wert.isdigit() else 0
    return render(request, "projektierung/dialog.html", aktiv="/projektierung",
                  angebot=angebot, kunde=kunde, vorgang=vorgang,
                  offenes=offenes, belegt=belegt,
                  sparten_waehlbar=waehlbar, sparte_vorbelegt=sparte,
                  projektleiter=_benutzer_mit_rolle(session, "projektierung"),
                  standard_pl=standard("standard_projektleiter"),
                  standard_fp=standard("standard_feinplaner"),
                  standard_ep=standard("standard_elektroplaner"),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/angebot/{angebot_id}/projekt")
async def projekt_anlegen(request: Request, angebot_id: int,
                          session: Session = Depends(get_session)):
    if (umleitung := _gate(request, session, schreiben=True)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or angebot.status != "Angenommen" or angebot.projekt_gewerk_id:
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    benutzer = request.state.benutzer
    form = await request.form()
    sparten = [s for s in ("WP", "PV", "KL", "WB")
               if form.get(f"sparte_{s}") == "on"]
    if not sparten:
        return RedirectResponse(
            f"/projektierung/angebot/{angebot_id}/projekt?meldung="
            + quote_plus("Bitte mindestens eine Sparte wählen."), status_code=303)
    try:
        projektleiter_id = int(form.get("projektleiter_id") or 0) or None
    except ValueError:
        projektleiter_id = None
    if projektleiter_id is None:
        return RedirectResponse(
            f"/projektierung/angebot/{angebot_id}/projekt?meldung="
            + quote_plus("Bitte einen Projektleiter wählen (Pflicht)."),
            status_code=303)
    def _id(name):
        try:
            return int(form.get(name) or 0) or None
        except ValueError:
            return None
    from app import vorgaenge as vorgaenge_modul
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    projekt = None
    if form.get("projekt_wahl", "") == "vorhanden":
        projekt = kern.offenes_projekt_fuer_vorgang(session, vorgang.id)
    if projekt is None:
        kunde = session.get(Kunde, angebot.kunde_id)
        if kunde is None:
            return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
                "Angebot ohne Kunden – Projekt kann nicht angelegt werden."),
                status_code=303)
        projekt = kern.projekt_anlegen(
            session, angebot, benutzer=benutzer,
            projektleiter_id=projektleiter_id,
            notiz_kopf=form.get("notiz_kopf") or "",
            adresse={"strasse": (form.get("strasse") or "").strip()[:200],
                     "plz": (form.get("plz") or "").strip()[:10],
                     "ort": (form.get("ort") or "").strip()[:100]})
        kern.verlauf(session, projekt.id,
                     f"Projekt {projekt.nummer} angelegt", benutzer=benutzer)
    else:
        projekt.projektleiter_id = projektleiter_id
        if (form.get("notiz_kopf") or "").strip():
            projekt.notiz_kopf = (form.get("notiz_kopf") or "").strip()[:500]
    belegt = {g.sparte for g in session.query(Gewerk)
              .filter(Gewerk.projekt_id == projekt.id,
                      Gewerk.phase != "storniert")}
    angelegt = []
    for sparte in sparten:
        if sparte in belegt:
            continue
        kern.gewerk_anlegen(session, projekt, angebot, sparte,
                            benutzer=benutzer,
                            feinplaner_id=_id("feinplaner_id"),
                            elektroplaner_id=_id("elektroplaner_id"))
        angelegt.append(sparte)
    session.commit()
    if not angelegt:
        return RedirectResponse(
            f"/projektierung/projekt/{projekt.id}?meldung=" + quote_plus(
                "Keine neuen Gewerke – die gewählten Sparten existieren bereits."),
            status_code=303)
    return RedirectResponse(f"/projektierung/projekt/{projekt.id}?meldung="
                            + quote_plus(f"Projekt {projekt.nummer}: Gewerk"
                                         f"{'e' if len(angelegt) > 1 else ''} "
                                         f"{', '.join(angelegt)} angelegt."),
                            status_code=303)


@router.get("/projekt/{projekt_id}")
async def akte(request: Request, projekt_id: int,
               session: Session = Depends(get_session)):
    """Projektakte (Phase 66 Basis, Phase 67 Vollausbau)."""
    if (umleitung := _gate(request, session)) is not None:
        return umleitung
    projekt = session.get(Projekt, projekt_id)
    if projekt is None:
        return RedirectResponse("/projektierung", status_code=303)
    kunde = session.get(Kunde, projekt.kunde_id)
    gewerke = (session.query(Gewerk)
               .filter(Gewerk.projekt_id == projekt.id)
               .order_by(Gewerk.id).all())
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    angebote = {a.id: a for a in session.query(Angebot)
                .filter(Angebot.id.in_([g.angebot_id for g in gewerke
                                        if g.angebot_id] or [0]))}
    aufgaben_je_gewerk: dict[int, list[Aufgabe]] = {}
    for aufgabe in (session.query(Aufgabe)
                    .filter(Aufgabe.projekt_id == projekt.id)
                    .order_by(Aufgabe.reihenfolge, Aufgabe.id)):
        aufgaben_je_gewerk.setdefault(aufgabe.gewerk_id or 0, []).append(aufgabe)
    instanzen = {i.id: i for i in session.query(AufgabenpaketInstanz)
                 .filter(AufgabenpaketInstanz.gewerk_id.in_(
                     [g.id for g in gewerke] or [0]))}
    termine = (session.query(ProjektTermin)
               .filter(ProjektTermin.projekt_id == projekt.id)
               .order_by(ProjektTermin.beginn).all())
    verlauf_eintraege = (session.query(ProjektVerlauf)
                         .filter(ProjektVerlauf.projekt_id == projekt.id)
                         .order_by(ProjektVerlauf.erstellt_am.desc(),
                                   ProjektVerlauf.id.desc()).limit(200).all())
    ampeln = {g.id: kern.planungs_ampel(session, g) for g in gewerke}
    logik = projektierung_logik.hole_logik(session)
    benutzer = request.state.benutzer
    ek_sichtbar = (benutzer.rolle in ("admin", "innendienst")
                   or benutzer.kalkulation_sichtbar)
    gesamtwert = sum(g.auftragswert_aktuell for g in gewerke
                     if g.phase != "storniert")
    return render(request, "projektierung/akte.html", aktiv="/projektierung",
                  projekt=projekt, kunde=kunde, gewerke=gewerke,
                  benutzer=benutzer, benutzer_map=benutzer_map,
                  angebote=angebote, aufgaben_je_gewerk=aufgaben_je_gewerk,
                  instanzen=instanzen, termine=termine,
                  verlauf=verlauf_eintraege, ampeln=ampeln,
                  phasen=GEWERK_PHASEN, phasen_namen=GEWERK_PHASEN_NAMEN,
                  status_namen=AUFGABE_STATUS_NAMEN,
                  storno_gruende=kern.storno_gruende(session),
                  pakete_je_sparte={g.id: logik.pakete_fuer_sparte(g.sparte)
                                    for g in gewerke},
                  ek_sichtbar=ek_sichtbar, gesamtwert=gesamtwert,
                  heute=datetime.now(),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/gewerk/{gewerk_id}/storno")
async def gewerk_storno(request: Request, gewerk_id: int,
                        session: Session = Depends(get_session)):
    """Storno (Phase 66): Pflichtdialog Grund + Text; setzt das Angebot auf
    „Abgelehnt" (bestehende Ablehnungslogik inkl. monday-Rückspielung)."""
    if (umleitung := _gate(request, session, schreiben=True)) is not None:
        return umleitung
    gewerk = session.get(Gewerk, gewerk_id)
    if gewerk is None:
        return RedirectResponse("/projektierung", status_code=303)
    form = await request.form()
    ok, meldung = kern.gewerk_stornieren(
        session, gewerk, (form.get("grund") or "").strip(),
        form.get("text") or "", benutzer=request.state.benutzer)
    if ok:
        session.commit()
    else:
        session.rollback()
    return RedirectResponse(f"/projektierung/projekt/{gewerk.projekt_id}"
                            f"?meldung=" + quote_plus(meldung), status_code=303)
