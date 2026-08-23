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
    from app import mail_sync
    from app.models import einstellung_holen
    logik, bericht = logik_modul.hole_logik(session)
    return render(request, "konfiguration/uebersicht.html", aktiv="/parametrierung",
                  logik=logik, bericht=bericht, dateifehler=None,
                  db_rot=einstellung_holen(session, "db_ampel_rot_unter", "9000"),
                  db_gruen=einstellung_holen(session, "db_ampel_gruen_ueber", "10000"),
                  fern_aktiv=einstellung_holen(session, "signatur_fern_aktiv", "0"),
                  fern_tage=einstellung_holen(session, "signatur_fern_gueltig_tage", "14"),
                  fern_basis=einstellung_holen(session, "signatur_fern_basis_url", ""),
                  mail_absender=einstellung_holen(session, "mail_absender", "angebot@friondo.de"),
                  mail_postfach=einstellung_holen(session, "mail_postfach", "angebot@friondo.de"),
                  mail_bcc=einstellung_holen(session, "mail_bcc", ""),
                  sync_status=mail_sync.status,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/einstellungen")
async def einstellungen_speichern(request: Request,
                                  session: Session = Depends(get_session)):
    """DB-Ampel-Schwellen (Phase 24) und weitere pflegbare Werte."""
    from app.models import einstellung_setzen
    form = await request.form()
    for name in ("db_ampel_rot_unter", "db_ampel_gruen_ueber"):
        wert = (form.get(name) or "").strip().replace(".", "")
        if wert.isdigit():
            einstellung_setzen(session, name, wert)
    # Fern-Signatur (Phase 28): Schalter, Gültigkeitsdauer, öffentliche Basis-URL
    if "fern_formular" in form:
        einstellung_setzen(session, "signatur_fern_aktiv",
                           "1" if form.get("signatur_fern_aktiv") else "0")
        tage = (form.get("signatur_fern_gueltig_tage") or "").strip()
        if tage.isdigit() and int(tage) > 0:
            einstellung_setzen(session, "signatur_fern_gueltig_tage", tage)
        einstellung_setzen(session, "signatur_fern_basis_url",
                           (form.get("signatur_fern_basis_url") or "").strip().rstrip("/"))
    # Versand (Phase 31): Absender „Senden als“, Abgleich-Postfach, BCC
    if "mail_formular" in form:
        for name in ("mail_absender", "mail_postfach", "mail_bcc"):
            einstellung_setzen(session, name, (form.get(name) or "").strip().lower())
    session.commit()
    return RedirectResponse("/parametrierung?meldung=Einstellungen+gespeichert",
                            status_code=303)


# --- E-Mail-Vorlagen (Phase 30) ------------------------------------------

@router.get("/vorlagen")
async def vorlagen_uebersicht(request: Request, benutzer_id: int = 0,
                              angebot_id: int = 0,
                              session: Session = Depends(get_session)):
    """Standard-Vorlage + optionale Vorlage je Außendienstler, mit Platzhalter-
    liste und Vorschau anhand eines echten Angebots."""
    from app import mail_vorlagen
    from app.models import Angebot, Benutzer, Kunde
    aussendienst = (session.query(Benutzer)
                    .filter(Benutzer.rolle == "aussendienst", Benutzer.aktiv.is_(True))
                    .order_by(Benutzer.name).all())
    ausgewaehlt = session.get(Benutzer, benutzer_id) if benutzer_id else None
    betreff, text, quelle = mail_vorlagen.vorlage_laden(session, benutzer_id or None)
    # Hat der AD eine eigene Vorlage? (sonst zeigen wir den Standard als Vorschlag)
    eigene = bool(benutzer_id) and quelle != "Standard-Vorlage"
    # Vorlagen-Status je AD für die Übersicht
    hat_vorlage = {b.id: mail_vorlagen.vorlage_laden(session, b.id)[2] != "Standard-Vorlage"
                   for b in aussendienst}
    # Vorschau: gewähltes oder neuestes Angebot
    angebote = (session.query(Angebot).filter(Angebot.archiviert.is_(False))
                .order_by(Angebot.nummer.desc()).limit(30).all())
    vorschau_angebot = session.get(Angebot, angebot_id) if angebot_id else (angebote[0] if angebote else None)
    vorschau = None
    if vorschau_angebot is not None:
        kunde = session.get(Kunde, vorschau_angebot.kunde_id)
        werte = mail_vorlagen.werte_fuer_angebot(session, vorschau_angebot, kunde,
                                                 request.state.benutzer.name)
        vorschau = {"betreff": mail_vorlagen.einsetzen(betreff, werte),
                    "text": mail_vorlagen.einsetzen(text, werte),
                    "werte": werte}
    return render(request, "konfiguration/vorlagen.html", aktiv="/parametrierung",
                  aussendienst=aussendienst, ausgewaehlt=ausgewaehlt,
                  benutzer_id=benutzer_id, betreff=betreff, text=text,
                  eigene=eigene, hat_vorlage=hat_vorlage,
                  platzhalter=mail_vorlagen.PLATZHALTER,
                  unbekannt=mail_vorlagen.unbekannte_platzhalter(betreff + text),
                  angebote=angebote, vorschau_angebot=vorschau_angebot,
                  vorschau=vorschau,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/vorlagen")
async def vorlagen_speichern(request: Request, session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app import mail_vorlagen
    form = await request.form()
    benutzer_id = form.get("benutzer_id") or ""
    bid = int(benutzer_id) if benutzer_id.isdigit() and int(benutzer_id) > 0 else None
    aktion = form.get("aktion") or "speichern"
    if aktion == "entfernen" and bid:
        # eigene AD-Vorlage löschen → Standard greift wieder
        mail_vorlagen.vorlage_speichern(session, bid, "", "")
        session.commit()
        return RedirectResponse(f"/parametrierung/vorlagen?benutzer_id={bid}&meldung="
                                + quote_plus("Eigene Vorlage entfernt – Standard gilt"),
                                status_code=303)
    betreff = (form.get("betreff") or "").strip()
    text = (form.get("text") or "").strip()
    if not betreff or not text:
        return RedirectResponse(f"/parametrierung/vorlagen?benutzer_id={bid or 0}&meldung="
                                + quote_plus("Betreff und Text dürfen nicht leer sein"),
                                status_code=303)
    mail_vorlagen.vorlage_speichern(session, bid, betreff, text)
    session.commit()
    unbekannt = mail_vorlagen.unbekannte_platzhalter(betreff + text)
    meldung = "Vorlage gespeichert"
    if unbekannt:
        meldung += " – unbekannte Platzhalter bleiben im Text stehen: " + ", ".join(unbekannt)
    return RedirectResponse(f"/parametrierung/vorlagen?benutzer_id={bid or 0}&meldung="
                            + quote_plus(meldung), status_code=303)


@router.get("/monday")
async def monday_uebersicht(request: Request, session: Session = Depends(get_session)):
    """monday-Anbindung (Phase 22): Quellen, Spalten-Mapping, Personen-Zuordnung."""
    from app import monday_sync
    from app.models import (Benutzer, MondayMapping, MondayPerson, MondayQuelle,
                            MONDAY_FELDER)
    monday_sync.quellen_vorbelegen(session)
    quellen = session.query(MondayQuelle).order_by(MondayQuelle.id).all()
    personen = session.query(MondayPerson).order_by(MondayPerson.monday_name).all()
    benutzer = session.query(Benutzer).filter(Benutzer.aktiv.is_(True)).all()
    mappings = {}
    spalten: dict[str, list] = {}
    gruppen: dict[str, list] = {}
    spalten_fehler = ""
    for quelle in quellen:
        mappings[quelle.board_id] = {
            m.feld: m.spalten_id for m in session.query(MondayMapping)
            .filter(MondayMapping.board_id == quelle.board_id)}
        if config.MONDAY_API_TOKEN:
            try:
                spalten[quelle.board_id] = monday_sync.spalten_laden(quelle.board_id)
                gruppen[quelle.board_id] = monday_sync.gruppen_laden(quelle.board_id)
            except Exception as problem:
                spalten_fehler = str(problem)
    return render(request, "konfiguration/monday.html", aktiv="/parametrierung",
                  quellen=quellen, personen=personen, benutzer=benutzer,
                  mappings=mappings, spalten=spalten, gruppen=gruppen,
                  felder=MONDAY_FELDER,
                  token_da=bool(config.MONDAY_API_TOKEN),
                  spalten_fehler=spalten_fehler,
                  sync_status=monday_sync.status,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/monday/quelle")
async def monday_quelle_speichern(request: Request,
                                  session: Session = Depends(get_session)):
    from app.models import MondayQuelle
    form = await request.form()
    quelle_id = form.get("quelle_id") or ""
    if quelle_id:
        quelle = session.get(MondayQuelle, int(quelle_id))
        if quelle is None:
            return RedirectResponse("/parametrierung/monday", status_code=303)
    else:
        if not (form.get("board_id") or "").strip():
            return RedirectResponse("/parametrierung/monday?meldung=Board-ID+fehlt",
                                    status_code=303)
        quelle = MondayQuelle(board_id=form.get("board_id").strip())
        session.add(quelle)
    quelle.board_name = (form.get("board_name") or "").strip()
    quelle.gruppen_titel = (form.get("gruppen_titel") or "Terminiert").strip()
    fester = form.get("fester_benutzer_id") or ""
    quelle.fester_benutzer_id = int(fester) if fester.isdigit() else None
    quelle.aktiv = form.get("aktiv") == "on"
    session.commit()
    return RedirectResponse("/parametrierung/monday?meldung=Quelle+gespeichert",
                            status_code=303)


@router.post("/monday/mapping/{board_id}")
async def monday_mapping_speichern(request: Request, board_id: str,
                                   session: Session = Depends(get_session)):
    from app.models import MondayMapping, MONDAY_FELDER
    form = await request.form()
    for feld in MONDAY_FELDER:
        eintrag = (session.query(MondayMapping)
                   .filter(MondayMapping.board_id == board_id,
                           MondayMapping.feld == feld).first())
        if eintrag is None:
            eintrag = MondayMapping(board_id=board_id, feld=feld)
            session.add(eintrag)
        eintrag.spalten_id = (form.get(feld) or "").strip()
    session.commit()
    return RedirectResponse("/parametrierung/monday?meldung=Mapping+gespeichert",
                            status_code=303)


@router.post("/monday/rueckspielung/{board_id}")
async def monday_rueckspielung_speichern(request: Request, board_id: str,
                                         session: Session = Depends(get_session)):
    """Rückspiel-Konfiguration je Quell-Board (Phase 32)."""
    from app.models import MondayQuelle
    form = await request.form()
    quelle = (session.query(MondayQuelle)
              .filter(MondayQuelle.board_id == board_id).first())
    if quelle is None:
        return RedirectResponse("/parametrierung/monday", status_code=303)
    modus = form.get("rueck_modus") or "aus"
    quelle.rueck_modus = modus if modus in ("aus", "status", "gruppe") else "aus"
    quelle.rueck_status_spalte = (form.get("rueck_status_spalte") or "").strip()
    quelle.rueck_status_wert = (form.get("rueck_status_wert") or "").strip() or "Angebot versendet"
    quelle.rueck_gruppe_id = (form.get("rueck_gruppe_id") or "").strip()
    quelle.rueck_wert_spalte = (form.get("rueck_wert_spalte") or "").strip()
    quelle.rueck_wert_basis = "netto" if form.get("rueck_wert_basis") == "netto" else "brutto"
    session.commit()
    return RedirectResponse("/parametrierung/monday?meldung=R%C3%BCckspielung+gespeichert",
                            status_code=303)


@router.post("/monday/person/{person_id}")
async def monday_person_zuordnen(request: Request, person_id: int,
                                 session: Session = Depends(get_session)):
    from app import monday_sync
    from urllib.parse import quote_plus

    from app.models import MondayPerson
    form = await request.form()
    person = session.get(MondayPerson, person_id)
    if person is None:
        return RedirectResponse("/parametrierung/monday", status_code=303)
    wert = form.get("benutzer_id") or ""
    person.benutzer_id = int(wert) if wert.isdigit() else None
    # v6-Bugfix: sofort rückwirkend auf vorhandene Leads anwenden
    anzahl = monday_sync.zuordnung_anwenden(session, person)
    session.commit()
    meldung = "Zuordnung gespeichert"
    if anzahl:
        meldung += f" – {anzahl} vorhandene Leads aktualisiert"
    return RedirectResponse("/parametrierung/monday?meldung=" + quote_plus(meldung),
                            status_code=303)


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
