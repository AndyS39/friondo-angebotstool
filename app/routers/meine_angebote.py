# „Meine Angebote“ (v8, Phase 49): der Außendienst sieht die eigenen Angebote
# read-only – Kundenpreise (Brutto/Endbetrag) und PDF-Download ja, aber ohne
# EK/DB, ohne Editor, ohne Versand und ohne Löschen.
# v10 (Phase 59): Suchfeld, vollständige Angebotsansicht (Positionen, Preise,
# Summen, Status, Verlauf – weiterhin OHNE EK/DB) und der AD-Gesamtrabatt mit
# Freigabe-Workflow (Rückmeldung nur als DB-Ampel-FARBE, nie in Euro).

from datetime import datetime
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app import angebot_aufbau
from app import vorgaenge as vorgaenge_modul
from app.db import get_session
from app.models import (Angebot, Erfassung, Kunde, RabattFreigabe,
                        einstellung_holen)
from app.templating import render

router = APIRouter(prefix="/meine-angebote")


def _eigene_angebote(session: Session, benutzer_id: int) -> list[Angebot]:
    """Angebote des Außendienstlers: über die verknüpfte Erfassung, sonst
    über das Vertriebler-Feld (manuelle Angebote)."""
    ids = {e.angebot_id for e in session.query(Erfassung)
           .filter(Erfassung.benutzer_id == benutzer_id,
                   Erfassung.angebot_id.isnot(None))}
    ids |= {a.id for a in session.query(Angebot)
            .filter(Angebot.vertriebler_id == benutzer_id)}
    if not ids:
        return []
    return (session.query(Angebot).options(joinedload(Angebot.positionen))
            .filter(Angebot.id.in_(ids), Angebot.archiviert.is_(False))
            .order_by(Angebot.nummer.desc()).all())


def _gehoert_mir(session: Session, angebot: Angebot, benutzer_id: int) -> bool:
    if angebot.vertriebler_id == benutzer_id:
        return True
    return (session.query(Erfassung)
            .filter(Erfassung.angebot_id == angebot.id,
                    Erfassung.benutzer_id == benutzer_id).count() > 0)


def _db_ampel(session: Session, db_cent: int) -> str:
    """DB-Farbampel (Schwellen wie in der Angebotsliste, Parametrierung)."""
    rot = int(einstellung_holen(session, "db_ampel_rot_unter", "9000")) * 100
    gruen = int(einstellung_holen(session, "db_ampel_gruen_ueber", "10000")) * 100
    return "rot" if db_cent < rot else ("gruen" if db_cent > gruen else "orange")


def _db_mit_rabatt(angebot: Angebot, cent, prozent) -> int:
    """DB-Simulation mit hypothetischem Gesamtrabatt (ohne zu speichern)."""
    alt = (angebot.rabatt_cent, angebot.rabatt_prozent)
    angebot.rabatt_cent, angebot.rabatt_prozent = cent, prozent
    try:
        return angebot.deckungsbeitrag()["db"]
    finally:
        angebot.rabatt_cent, angebot.rabatt_prozent = alt


def rabatt_anwenden(session: Session, angebot: Angebot, cent, prozent,
                    bezeichnung: str) -> Angebot:
    """Wendet den Gesamtrabatt an: Entwürfe direkt, versendete/angenommene
    Angebote über eine neue Version (.2/.3 …, v9-Mechanik). Liefert das
    Angebot, an dem der Rabatt jetzt steht."""
    ziel = angebot
    if angebot.status in ("Versendet", "Angenommen"):
        ziel = angebot_aufbau.version_erzeugen(session, angebot)
    ziel.rabatt_cent = cent
    ziel.rabatt_prozent = prozent
    ziel.rabatt_bezeichnung = (bezeichnung or "").strip()[:200]
    return ziel


def _rabatt_lesen(form):
    """Formularwerte → (cent, prozent, bezeichnung, fehlertext).
    v11: leeres Feld oder 0 bedeutet „Rabatt entfernen“ (cent und prozent
    None bei leerem Fehlertext)."""
    from app.konfigurator import zahl_parsen
    from app.routers.artikel import preis_parsen
    wert = (form.get("rabatt_wert") or "").strip()
    bezeichnung = (form.get("rabatt_bezeichnung") or "").strip()
    if not wert:
        return None, None, bezeichnung, ""
    if form.get("rabatt_typ") == "prozent":
        prozent = zahl_parsen(wert)
        if prozent == 0:
            return None, None, bezeichnung, ""
        if prozent is None or not (0 < prozent <= 100):
            return None, None, bezeichnung, "Ungültiger Prozentwert."
        return None, float(prozent), bezeichnung, ""
    cent = preis_parsen(wert)
    if cent == 0:
        return None, None, bezeichnung, ""
    if cent is None or cent <= 0:
        return None, None, bezeichnung, "Ungültiger Betrag."
    return cent, None, bezeichnung, ""


def _projektstand(session: Session, angebot: Angebot, benutzer) -> dict | None:
    """v11 (Phase 70): Phase je Gewerk, Ampel, nächster Termin und
    Projektleiter (mit Telefon) für den Projektstand-Block am AD-Angebot."""
    from datetime import datetime as dt

    from app import projektierung as kern
    from app.models import (Benutzer, Gewerk, Projekt, ProjektTermin,
                            GEWERK_PHASEN_NAMEN)
    if not kern.modul_sichtbar(session, benutzer):
        return None
    gewerk = None
    if angebot.projekt_gewerk_id:
        gewerk = session.get(Gewerk, angebot.projekt_gewerk_id)
    if gewerk is None:
        gewerk = (session.query(Gewerk)
                  .filter(Gewerk.angebot_id == angebot.id).first())
    if gewerk is None:
        return None
    projekt = session.get(Projekt, gewerk.projekt_id)
    if projekt is None:
        return None
    gewerke = (session.query(Gewerk)
               .filter(Gewerk.projekt_id == projekt.id)
               .order_by(Gewerk.id).all())
    zeilen = []
    for g in gewerke:
        termin = (session.query(ProjektTermin)
                  .filter(ProjektTermin.gewerk_id == g.id,
                          ProjektTermin.beginn.isnot(None),
                          ProjektTermin.beginn >= dt.now())
                  .order_by(ProjektTermin.beginn).first())
        zeilen.append({"gewerk": g, "phase_name": GEWERK_PHASEN_NAMEN[g.phase],
                       "ampel": kern.planungs_ampel(session, g),
                       "termin": termin})
    projektleiter = (session.get(Benutzer, projekt.projektleiter_id)
                     if projekt.projektleiter_id else None)
    return {"projekt": projekt, "zeilen": zeilen, "projektleiter": projektleiter}


@router.post("/{angebot_id}/projekt-kommentar")
async def projekt_kommentar(request: Request, angebot_id: int,
                            session: Session = Depends(get_session)):
    """AD-Kommentar zum Projektstand → Projektverlauf + Info an den
    Projektleiter (Plan Phase 70)."""
    from app import projektierung as kern
    benutzer = request.state.benutzer
    angebot = session.get(Angebot, angebot_id)
    if (angebot is None or not _gehoert_mir(session, angebot, benutzer.id)):
        return RedirectResponse("/meine-angebote", status_code=303)
    stand = _projektstand(session, angebot, benutzer)
    form = await request.form()
    text = (form.get("text") or "").strip()
    if stand is None or not text:
        return RedirectResponse(f"/meine-angebote/{angebot_id}", status_code=303)
    projekt = stand["projekt"]
    kern.verlauf(session, projekt.id, f"Außendienst: {text}", benutzer=benutzer,
                 art="kommentar")
    if projekt.projektleiter_id:
        kern.benachrichtigen(
            session, [projekt.projektleiter_id],
            f"{benutzer.name} (Außendienst) hat im Projekt {projekt.nummer} "
            f"kommentiert: {text[:120]}",
            f"/projektierung/projekt/{projekt.id}#verlauf", art="kommentar")
    session.commit()
    return RedirectResponse(f"/meine-angebote/{angebot_id}?meldung="
                            + quote_plus("Kommentar an die Projektierung übermittelt."),
                            status_code=303)


@router.get("")
async def liste(request: Request, q: str = "",
                session: Session = Depends(get_session)):
    benutzer = request.state.benutzer
    angebote = _eigene_angebote(session, benutzer.id)
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_([a.kunde_id for a in angebote] or [0]))}
    if q:   # v10: Suche nach Name, Ort und Angebotsnummer
        suchwort = q.lower()
        angebote = [a for a in angebote
                    if suchwort in a.nummer.lower()
                    or suchwort in (a.taifun_nummer or "").lower()
                    or (a.kunde_id in kunden
                        and (suchwort in kunden[a.kunde_id].anzeige_name.lower()
                             or suchwort in (kunden[a.kunde_id].ort or "").lower()))]
    return render(request, "angebote/meine.html", aktiv=None, mobil=True,
                  benutzer=benutzer, angebote=angebote, kunden=kunden, q=q,
                  heute=datetime.now(),
                  meldung=request.query_params.get("meldung", ""))


@router.get("/{angebot_id}")
async def detail(request: Request, angebot_id: int,
                 session: Session = Depends(get_session)):
    """v10: vollständige Ansicht des eigenen Angebots – alle Positionen,
    Preise, Summen, Status und PDF; OHNE EK/DB-Werte und ohne Editor."""
    import json as json_modul

    from app import kfw
    from app import logik as logik_modul
    benutzer = request.state.benutzer
    angebot = session.get(Angebot, angebot_id)
    if (angebot is None or angebot.extern
            or not _gehoert_mir(session, angebot, benutzer.id)):
        return RedirectResponse("/meine-angebote", status_code=303)
    kunde = session.get(Kunde, angebot.kunde_id)
    for p, nummer in zip(angebot.positionen, angebot.nummerierung()):
        p.lfd_nr = nummer
    gruppen: list[dict] = []
    for p in angebot.positionen:
        if not gruppen or gruppen[-1]["name"] != p.gruppe or gruppen[-1]["block"] != p.block_nr:
            gruppen.append({"name": p.gruppe, "block": p.block_nr, "positionen": []})
        gruppen[-1]["positionen"].append(p)
    kfw_ergebnis = None
    kfw_daten = json_modul.loads(angebot.kfw_json or "{}")
    if kfw_daten.get("O01"):
        logik, bericht = logik_modul.hole_logik(session)
        if bericht is not None:
            parameter, _ = kfw.parameter_lesen(logik)
            eingaben = kfw.eingaben_aus_antworten(kfw_daten, angebot.summen()["endbetrag"])
            if eingaben is not None:
                kfw_ergebnis = kfw.ergebnis_fuer_angebot(parameter, eingaben, angebot)
    freigabe_offen = (session.query(RabattFreigabe)
                      .filter(RabattFreigabe.angebot_id == angebot.id,
                              RabattFreigabe.status == "offen").first())
    rabatt_erlaubt = (not angebot.extern and angebot.status in
                      ("Entwurf", "Versand vorbereitet", "Versendet", "Angenommen"))
    # v11 (Phase 70): Projektstand-Block am eigenen Angebot (read-only) –
    # nur wenn das Modul für den Benutzer sichtbar ist (Demo-Modus: Admin)
    projektstand = _projektstand(session, angebot, benutzer)
    # v11 (Phase 66): AD-Statuswechsel (Angenommen/Abgelehnt/zurück auf
    # Versendet) mit Pflichtdialog Ablehnungsgrund
    from app.models import AblehnungsGrund
    status_erlaubt = (not angebot.extern
                      and angebot.status in ("Versendet", "Angenommen", "Abgelehnt"))
    ablehnungsgruende = (session.query(AblehnungsGrund)
                         .filter(AblehnungsGrund.aktiv.is_(True))
                         .order_by(AblehnungsGrund.sort, AblehnungsGrund.id).all())
    return render(request, "angebote/meine_detail.html", aktiv=None, mobil=True,
                  projektstand=projektstand,
                  benutzer=benutzer, angebot=angebot, kunde=kunde,
                  gruppen=gruppen, summen=angebot.summen(),
                  kfw_ergebnis=kfw_ergebnis,
                  db_ampel=_db_ampel(session, angebot.deckungsbeitrag()["db"]),
                  freigabe_offen=freigabe_offen,
                  rabatt_erlaubt=rabatt_erlaubt and freigabe_offen is None,
                  status_erlaubt=status_erlaubt,
                  ablehnungsgruende=ablehnungsgruende,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/{angebot_id}/status")
async def status_setzen(request: Request, angebot_id: int,
                        session: Session = Depends(get_session)):
    """v11 (Phase 66): AD setzt eigene Angebote auf Angenommen / Abgelehnt /
    zurück auf Versendet („Offen“). Abgelehnt nur mit Pflichtgrund; jeder
    Wechsel landet im Notizen-Chat des Vorgangs; monday-Summenlogik und
    Statistik greifen wie beim Innendienst."""
    from app.models import AblehnungsGrund, angebot_status_setzen
    benutzer = request.state.benutzer
    angebot = session.get(Angebot, angebot_id)
    if (angebot is None or angebot.extern
            or not _gehoert_mir(session, angebot, benutzer.id)):
        return RedirectResponse("/meine-angebote", status_code=303)
    form = await request.form()
    neuer_status = form.get("status", "")
    if (neuer_status not in ("Versendet", "Angenommen", "Abgelehnt")
            or angebot.status not in ("Versendet", "Angenommen", "Abgelehnt")
            or neuer_status == angebot.status):
        return RedirectResponse(f"/meine-angebote/{angebot_id}", status_code=303)
    grund = ""
    if neuer_status == "Abgelehnt":
        grund = (form.get("ablehnungsgrund") or "").strip()
        bekannt = {g.name for g in session.query(AblehnungsGrund)
                   .filter(AblehnungsGrund.aktiv.is_(True))}
        if grund not in bekannt:
            return RedirectResponse(f"/meine-angebote/{angebot_id}?meldung="
                                    + quote_plus("Bitte den Grund der Ablehnung "
                                                 "angeben."), status_code=303)
        angebot.ablehnungsgrund = grund
        angebot.ablehnungsgrund_text = (form.get("ablehnungsgrund_text") or "").strip()[:500]
    alter_status = angebot.status
    angebot_status_setzen(angebot, neuer_status)
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    text = (f"Status von {angebot.nummer}: {alter_status} → {neuer_status}"
            + (f" – Grund: {grund}" if grund else "")
            + (f" ({angebot.ablehnungsgrund_text})"
               if grund and angebot.ablehnungsgrund_text else ""))
    vorgaenge_modul.notiz_anlegen(session, vorgang.id, benutzer, text,
                                  herkunft="AD-Statuswechsel")
    session.commit()
    # monday-Summenlogik wie beim Innendienst (app/routers/angebote.py)
    from app import monday_rueckspielung
    if neuer_status == "Versendet":
        monday_rueckspielung.bei_versand(session, angebot)
    elif neuer_status == "Abgelehnt" and alter_status in ("Versendet", "Angenommen"):
        monday_rueckspielung.wert_aktualisieren(session, angebot, "Ablehnung (AD)")
    if neuer_status == "Angenommen":
        from app import projektierung as projektierung_modul
        projektierung_modul.version_nachziehen(session, angebot)
        session.commit()
    from app import leadmanagement
    leadmanagement.phase_neu_berechnen(session, angebot.vorgang_id)
    session.commit()
    return RedirectResponse(f"/meine-angebote/{angebot_id}?meldung="
                            + quote_plus(f"Status auf „{neuer_status}“ gesetzt."),
                            status_code=303)


@router.post("/{angebot_id}/rabatt")
async def rabatt(request: Request, angebot_id: int,
                 session: Session = Depends(get_session)):
    """v10: AD-Gesamtrabatt (Brutto, v4-Mechanik). Zulässig, solange die
    DB-Ampel nicht auf Rot fällt – sonst Freigabe-Anfrage an den Innendienst.
    Entwürfe direkt, versendete Angebote über Version .2 (v9-Mechanik)."""
    benutzer = request.state.benutzer
    angebot = session.get(Angebot, angebot_id)
    if (angebot is None or angebot.extern
            or not _gehoert_mir(session, angebot, benutzer.id)):
        return RedirectResponse("/meine-angebote", status_code=303)
    if angebot.status not in ("Entwurf", "Versand vorbereitet",
                              "Versendet", "Angenommen"):
        return RedirectResponse(f"/meine-angebote/{angebot_id}?meldung=" + quote_plus(
            f"Rabatt bei Status „{angebot.status}“ nicht möglich."), status_code=303)
    if (session.query(RabattFreigabe)
            .filter(RabattFreigabe.angebot_id == angebot.id,
                    RabattFreigabe.status == "offen").count()):
        return RedirectResponse(f"/meine-angebote/{angebot_id}?meldung=" + quote_plus(
            "Es liegt bereits eine offene Rabatt-Freigabe beim Innendienst."),
            status_code=303)
    form = await request.form()
    cent, prozent, bezeichnung, fehler = _rabatt_lesen(form)
    if fehler:
        return RedirectResponse(f"/meine-angebote/{angebot_id}?meldung="
                                + quote_plus(fehler), status_code=303)
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    # v11: Eingabe 0 oder leeres Feld entfernt den Rabatt (statt Fehlermeldung)
    if cent is None and prozent is None:
        if not (angebot.rabatt_cent or angebot.rabatt_prozent):
            return RedirectResponse(f"/meine-angebote/{angebot_id}?meldung=" + quote_plus(
                "Kein Rabatt gesetzt."), status_code=303)
        ziel = rabatt_anwenden(session, angebot, None, None, "")
        if ziel.id != angebot.id:
            from app import monday_rueckspielung
            monday_rueckspielung.wert_aktualisieren(session, ziel,
                                                    "neue Version (Rabatt entfernt)")
        vorgaenge_modul.notiz_anlegen(
            session, vorgang.id, benutzer,
            f"Rabatt auf {ziel.nummer} entfernt"
            + (f" (neue Version von {angebot.nummer})" if ziel.id != angebot.id else "")
            + ".", herkunft="Rabatt-Workflow")
        session.commit()
        return RedirectResponse(f"/meine-angebote/{ziel.id}?meldung=" + quote_plus(
            "Rabatt entfernt."), status_code=303)
    rabatt_text = (f"{prozent:g} %" if prozent
                   else f"{cent / 100:.2f} €".replace(".", ","))
    db_neu = _db_mit_rabatt(angebot, cent, prozent)
    if _db_ampel(session, db_neu) == "rot":
        # Freigabe-Anfrage an den Innendienst – nichts wird geändert
        session.add(RabattFreigabe(
            angebot_id=angebot.id, vorgang_id=vorgang.id,
            benutzer_id=benutzer.id, rabatt_cent=cent, rabatt_prozent=prozent,
            rabatt_bezeichnung=bezeichnung))
        vorgaenge_modul.notiz_anlegen(
            session, vorgang.id, benutzer,
            f"Rabatt-Freigabe angefragt: {rabatt_text} auf {angebot.nummer} "
            "(DB-Ampel würde Rot) – wartet auf den Innendienst.",
            herkunft="Rabatt-Workflow")
        session.commit()
        return RedirectResponse(f"/meine-angebote/{angebot_id}?meldung=" + quote_plus(
            "Der Rabatt würde die DB-Ampel auf Rot drücken – Freigabe-Anfrage "
            "an den Innendienst gestellt."), status_code=303)
    ziel = rabatt_anwenden(session, angebot, cent, prozent, bezeichnung)
    if ziel.id != angebot.id:
        from app import monday_rueckspielung
        monday_rueckspielung.wert_aktualisieren(session, ziel, "neue Version (AD-Rabatt)")
    vorgaenge_modul.notiz_anlegen(
        session, vorgang.id, benutzer,
        f"Rabatt {rabatt_text} auf {ziel.nummer} gesetzt"
        + (f" (neue Version von {angebot.nummer})" if ziel.id != angebot.id else "")
        + f" – DB-Ampel {_db_ampel(session, db_neu)}.",
        herkunft="Rabatt-Workflow")
    session.commit()
    zusatz = (f" Neue Version {ziel.nummer} als Entwurf – bereit für "
              "Vor-Ort-Signatur oder ID-Versand." if ziel.id != angebot.id else "")
    return RedirectResponse(f"/meine-angebote/{ziel.id}?meldung=" + quote_plus(
        f"Rabatt {rabatt_text} übernommen.{zusatz}"), status_code=303)


@router.get("/{angebot_id}/pdf")
async def pdf_anzeigen(request: Request, angebot_id: int,
                       session: Session = Depends(get_session)):
    """PDF des eigenen Angebots (Kundenansicht – enthält ohnehin keine EKs)."""
    benutzer = request.state.benutzer
    angebot = session.get(Angebot, angebot_id)
    if (angebot is None or angebot.extern
            or not _gehoert_mir(session, angebot, benutzer.id)):
        return RedirectResponse("/meine-angebote", status_code=303)
    from app import pdf_export
    pfad = pdf_export.pdf_fuer_angebot(session, angebot)
    return FileResponse(pfad, media_type="application/pdf",
                        content_disposition_type="inline",
                        filename=f"{angebot.nummer}.pdf")
