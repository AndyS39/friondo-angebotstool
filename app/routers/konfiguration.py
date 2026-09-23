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
    from app.models import AblehnungsGrund, AngebotsLoeschung, einstellung_holen
    logik, bericht = logik_modul.hole_logik(session)
    return render(request, "konfiguration/uebersicht.html", aktiv="/parametrierung",
                  logik=logik, bericht=bericht, dateifehler=None,
                  ablehnungsgruende=(session.query(AblehnungsGrund)
                                     .order_by(AblehnungsGrund.sort, AblehnungsGrund.id).all()),
                  ablehnung_tage=einstellung_holen(session, "ablehnung_auto_tage", "90"),
                  ablehnung_protokoll=einstellung_holen(session, "ablehnung_auto_protokoll", ""),
                  db_rot=einstellung_holen(session, "db_ampel_rot_unter", "9000"),
                  db_gruen=einstellung_holen(session, "db_ampel_gruen_ueber", "10000"),
                  fern_aktiv=einstellung_holen(session, "signatur_fern_aktiv", "0"),
                  fern_tage=einstellung_holen(session, "signatur_fern_gueltig_tage", "14"),
                  fern_basis=einstellung_holen(session, "signatur_fern_basis_url", ""),
                  mail_absender=einstellung_holen(session, "mail_absender", "angebot@friondo.de"),
                  mail_postfach=einstellung_holen(session, "mail_postfach", "angebot@friondo.de"),
                  mail_bcc=einstellung_holen(session, "mail_bcc", ""),
                  gewerke_artikel=einstellung_holen(
                      session, "gewerke_artikel",
                      __import__("app.kombi_versand", fromlist=["x"]).GEWERKE_ARTIKEL_START),
                  kombi_betreff=einstellung_holen(session, "kombi_vorlage_betreff", "")
                  or __import__("app.mail_vorlagen", fromlist=["x"]).KOMBI_BETREFF,
                  kombi_text=einstellung_holen(session, "kombi_vorlage_text", "")
                  or __import__("app.mail_vorlagen", fromlist=["x"]).KOMBI_TEXT,
                  sync_status=mail_sync.status,
                  versand_protokoll=__import__("json").loads(
                      einstellung_holen(session, "versand_erkennung_protokoll", "[]")),
                  loeschungen=(session.query(AngebotsLoeschung)
                               .order_by(AngebotsLoeschung.geloescht_am.desc())
                               .limit(50).all()),
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
    # v10 (Phase 61): gewerkeübergreifende Artikel + Kombi-Vorlage
    if "gewerke_formular" in form:
        einstellung_setzen(session, "gewerke_artikel",
                           (form.get("gewerke_artikel") or "").strip())
    if "kombi_formular" in form:
        einstellung_setzen(session, "kombi_vorlage_betreff",
                           (form.get("kombi_vorlage_betreff") or "").strip())
        einstellung_setzen(session, "kombi_vorlage_text",
                           (form.get("kombi_vorlage_text") or "").strip())
    # Abgelehnt-Prozess (v8): Frist des täglichen Prüflaufs
    if "ablehnung_formular" in form:
        tage = (form.get("ablehnung_auto_tage") or "").strip()
        if tage.isdigit() and int(tage) > 0:
            einstellung_setzen(session, "ablehnung_auto_tage", tage)
    session.commit()
    return RedirectResponse("/parametrierung?meldung=Einstellungen+gespeichert",
                            status_code=303)


@router.get("/profile")
async def profile_seite(request: Request, block_id: int = 0,
                        session: Session = Depends(get_session)):
    """v9: Angebotsprofile + Textblock-Verwaltung (Nach-/Vortexte)."""
    from app import angebotsprofile
    from app.models import Profil, Textblock
    profile = session.query(Profil).order_by(Profil.id).all()
    bloecke = (session.query(Textblock)
               .order_by(Textblock.art.desc(), Textblock.name).all())
    block = session.get(Textblock, block_id) if block_id else None
    return render(request, "konfiguration/profile.html", aktiv="/parametrierung",
                  profile=profile, bloecke=bloecke, block=block,
                  hinweise={p.id: angebotsprofile.regeln_beschreibung(p)
                            for p in profile},
                  bloecke_nachtext=[b for b in bloecke if b.art == "nachtext"],
                  bloecke_vortext=[b for b in bloecke if b.art == "vortext"],
                  meldung=request.query_params.get("meldung", ""))


@router.post("/profile/{profil_id}")
async def profil_speichern(request: Request, profil_id: int,
                           session: Session = Depends(get_session)):
    """v9: Kanal-Zuordnung, Textblöcke und Versandregeln eines Profils."""
    from urllib.parse import quote_plus

    from app.models import Profil
    profil = session.get(Profil, profil_id)
    if profil is None:
        return RedirectResponse("/parametrierung/profile", status_code=303)
    form = await request.form()
    profil.kanalwerte = (form.get("kanalwerte") or "").strip()[:200]
    profil.versand_cc = (form.get("versand_cc") or "").strip()[:200]
    profil.empfaenger_leer = form.get("empfaenger_leer") == "on"
    profil.ohne_vollmacht = form.get("ohne_vollmacht") == "on"
    for feld in ("nachtext_id", "vortext_id"):
        wert = form.get(feld) or ""
        setattr(profil, feld, int(wert) if wert.isdigit() and int(wert) else None)
    session.commit()
    return RedirectResponse("/parametrierung/profile?meldung=" + quote_plus(
        f"Profil „{profil.name}“ gespeichert"), status_code=303)


@router.post("/textbloecke")
async def textblock_speichern(request: Request,
                              session: Session = Depends(get_session)):
    """v9: Textblock bearbeiten oder neu anlegen."""
    from urllib.parse import quote_plus

    from app.models import Textblock
    form = await request.form()
    if form.get("aktion") == "neu":
        name = (form.get("name") or "").strip()[:100]
        art = form.get("art") if form.get("art") in ("nachtext", "vortext") else "nachtext"
        if name:
            block = Textblock(art=art, name=name, text="")
            session.add(block)
            session.commit()
            return RedirectResponse(
                f"/parametrierung/profile?block_id={block.id}&meldung="
                + quote_plus(f"Block „{name}“ angelegt – Text unten pflegen"),
                status_code=303)
        return RedirectResponse("/parametrierung/profile", status_code=303)
    block = session.get(Textblock, int(form.get("block_id") or 0))
    if block is None:
        return RedirectResponse("/parametrierung/profile", status_code=303)
    block.text = form.get("text") or ""
    session.commit()
    return RedirectResponse(
        f"/parametrierung/profile?block_id={block.id}&meldung="
        + quote_plus(f"Block „{block.name}“ gespeichert"), status_code=303)


@router.post("/ablehnungsgruende")
async def ablehnungsgruende_pflegen(request: Request,
                                    session: Session = Depends(get_session)):
    """v8: Auswahlliste „Grund der Ablehnung“ pflegen (hinzufügen bzw.
    deaktivieren/aktivieren – gelöscht wird nicht, Altdaten bleiben lesbar)."""
    from urllib.parse import quote_plus

    from app.models import AblehnungsGrund
    form = await request.form()
    if form.get("aktion") == "hinzufuegen":
        name = (form.get("name") or "").strip()[:100]
        if name and session.query(AblehnungsGrund).filter_by(name=name).count() == 0:
            session.add(AblehnungsGrund(
                name=name, sort=session.query(AblehnungsGrund).count()))
            session.commit()
            return RedirectResponse("/parametrierung?meldung=" + quote_plus(
                f"Ablehnungsgrund „{name}“ hinzugefügt"), status_code=303)
    elif form.get("aktion") == "umschalten":
        grund = session.get(AblehnungsGrund, int(form.get("id") or 0))
        if grund is not None:
            grund.aktiv = not grund.aktiv
            session.commit()
    return RedirectResponse("/parametrierung", status_code=303)


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
                    "text_html": mail_vorlagen.einsetzen_html(
                        mail_vorlagen.als_html(text), werte),
                    "werte": werte}
    return render(request, "konfiguration/vorlagen.html", aktiv="/parametrierung",
                  aussendienst=aussendienst, ausgewaehlt=ausgewaehlt,
                  benutzer_id=benutzer_id, betreff=betreff, text=text,
                  text_html=mail_vorlagen.als_html(text),
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


# --- E-Mail-Signaturen (v6, Phase 42) --------------------------------------

@router.get("/signaturen")
async def signaturen_uebersicht(request: Request, benutzer_id: int = 0,
                                session: Session = Depends(get_session)):
    """Outlook-Signatur je Innendienst-Benutzer hochladen/prüfen."""
    from app import signaturen
    from app.models import Benutzer
    innendienst = (session.query(Benutzer)
                   .filter(Benutzer.rolle.in_(["admin", "innendienst"]),
                           Benutzer.aktiv.is_(True))
                   .order_by(Benutzer.name).all())
    if not benutzer_id:
        benutzer_id = request.state.benutzer.id
    ausgewaehlt = session.get(Benutzer, benutzer_id)
    html_vorschau, _bilder = signaturen.fuer_versand(benutzer_id)
    # Vorschau: cid-Bilder über die Bild-Route auflösen
    html_vorschau = html_vorschau.replace(
        "cid:", f"/parametrierung/signaturen/{benutzer_id}/bild/")
    return render(request, "konfiguration/signaturen.html", aktiv="/parametrierung",
                  innendienst=innendienst, benutzer_id=benutzer_id,
                  ausgewaehlt=ausgewaehlt,
                  hochgeladen=signaturen.vorhanden(benutzer_id),
                  dateien=signaturen.dateien_auflisten(benutzer_id),
                  hat_signatur={b.id: signaturen.vorhanden(b.id) for b in innendienst},
                  vorschau_html=html_vorschau,
                  meldung=request.query_params.get("meldung", ""))


@router.get("/signaturen/{benutzer_id}/bild/{cid}")
async def signatur_bild(benutzer_id: int, cid: str):
    """Inline-Bild der Signatur für die Vorschau (cid → Datei)."""
    from fastapi.responses import FileResponse, Response

    from app import signaturen
    _, bilder = signaturen.fuer_versand(benutzer_id)
    for bild_cid, pfad, mime in bilder:
        if bild_cid == cid:
            return FileResponse(pfad, media_type=mime)
    return Response(status_code=404)


@router.post("/signaturen/{benutzer_id}")
async def signatur_hochladen(request: Request, benutzer_id: int,
                             session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app import signaturen
    form = await request.form()
    if form.get("aktion") == "entfernen":
        signaturen.entfernen(benutzer_id)
        return RedirectResponse(f"/parametrierung/signaturen?benutzer_id={benutzer_id}"
                                "&meldung=Signatur+entfernt+%E2%80%93+Standard+gilt",
                                status_code=303)
    dateien = []
    for feld in form.getlist("dateien"):
        if hasattr(feld, "filename") and feld.filename:
            dateien.append((feld.filename, await feld.read()))
    ok, meldung = signaturen.speichern(benutzer_id, dateien)
    return RedirectResponse(f"/parametrierung/signaturen?benutzer_id={benutzer_id}"
                            f"&meldung={quote_plus(meldung)}", status_code=303)


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


@router.get("/projektierung-logik")
async def projektierung_logik_seite(request: Request,
                                    session: Session = Depends(get_session)):
    """v11 (Phase 65): Steuerdatei der Projektierung – Pakete-Tabelle,
    Versionsstand, Upload. Änderungen wirken auf NEUE Aktivierungen."""
    from app import projektierung_logik
    logik = projektierung_logik.hole_logik(session)
    session.commit()
    return render(request, "konfiguration/projektierung_logik.html",
                  aktiv="/parametrierung", logik=logik,
                  pfad=str(projektierung_logik.LOGIK_PFAD),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/projektierung-logik")
async def projektierung_logik_upload(request: Request,
                                     session: Session = Depends(get_session)):
    """Upload wie beim Logik-Import: Backup der alten Datei, ersetzen,
    neu einlesen; bei Fehlern wird die alte Datei wiederhergestellt."""
    import shutil
    from datetime import datetime as dt
    from urllib.parse import quote_plus

    from app import projektierung_logik
    form = await request.form()
    datei = form.get("datei")
    if datei is None or not getattr(datei, "filename", ""):
        return RedirectResponse("/parametrierung/projektierung-logik?meldung="
                                + quote_plus("Bitte eine .xlsx-Datei wählen."),
                                status_code=303)
    inhalt = await datei.read()
    ziel = projektierung_logik.LOGIK_PFAD
    sicherung = None
    if ziel.exists():
        sicherung = (config.BACKUP_ORDNER
                     / f"projektierung_logik_{dt.now():%Y%m%d_%H%M%S}.xlsx")
        shutil.copyfile(ziel, sicherung)
    ziel.write_bytes(inhalt)
    logik = projektierung_logik.hole_logik(session, erzwingen=True)
    if logik.fehler:
        if sicherung is not None:
            shutil.copyfile(sicherung, ziel)
            projektierung_logik.hole_logik(session, erzwingen=True)
        return RedirectResponse("/parametrierung/projektierung-logik?meldung="
                                + quote_plus("Import abgewiesen: "
                                             + " · ".join(logik.fehler)),
                                status_code=303)
    session.commit()
    meldung = (f"Steuerdatei übernommen – {len(logik.pakete)} Pakete, "
               f"{len(logik.regeln)} Regeln"
               + (f", {len(logik.warnungen)} Warnungen" if logik.warnungen else "")
               + (f". Backup: {sicherung.name}" if sicherung else "."))
    return RedirectResponse("/parametrierung/projektierung-logik?meldung="
                            + quote_plus(meldung), status_code=303)


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


# --- v11 (Phase 70): Stammseiten der Projektierung --------------------------------

def _nur_admin(request: Request):
    """Projektierung-Einstellungen (Demo-Schalter usw.) sind Admin-exklusiv."""
    benutzer = request.state.benutzer
    if benutzer is None or benutzer.rolle != "admin":
        return RedirectResponse("/parametrierung", status_code=303)
    return None


@router.get("/teams")
async def teams_seite(request: Request, session: Session = Depends(get_session)):
    from app.models import Benutzer, Team, TeamMitglied
    teams = session.query(Team).order_by(Team.name).all()
    mitglieder: dict[int, list[str]] = {}
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    for m in session.query(TeamMitglied):
        if m.benutzer_id in benutzer_map:
            mitglieder.setdefault(m.team_id, []).append(
                benutzer_map[m.benutzer_id].name)
    return render(request, "konfiguration/teams.html", aktiv="/parametrierung",
                  teams=teams, mitglieder=mitglieder,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/teams")
async def team_speichern(request: Request, session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app.models import Team
    form = await request.form()
    team_id = form.get("team_id") or ""
    name = (form.get("name") or "").strip()
    typ = form.get("typ") if form.get("typ") in ("SHK", "Elektro", "Sonstige") else "SHK"
    if team_id.isdigit():
        team = session.get(Team, int(team_id))
        if team is not None:
            if name:
                team.name = name
            team.typ = typ
            team.aktiv = form.get("aktiv") == "on"
    elif name:
        session.add(Team(name=name, typ=typ, aktiv=True,
                         erstellt_von=request.state.benutzer.id))
    else:
        return RedirectResponse("/parametrierung/teams?meldung="
                                + quote_plus("Bitte einen Namen angeben."),
                                status_code=303)
    session.commit()
    return RedirectResponse("/parametrierung/teams?meldung=Gespeichert",
                            status_code=303)


@router.get("/subunternehmer")
async def subs_seite(request: Request, session: Session = Depends(get_session)):
    from app import projektierung_logik
    from app.models import Subunternehmer
    return render(request, "konfiguration/subunternehmer.html",
                  aktiv="/parametrierung",
                  subs=session.query(Subunternehmer)
                  .order_by(Subunternehmer.firma).all(),
                  typen=projektierung_logik.sub_typen(session),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/subunternehmer")
async def sub_speichern(request: Request, session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app.models import Subunternehmer
    form = await request.form()
    sub_id = form.get("sub_id") or ""
    felder = {name: (form.get(name) or "").strip()
              for name in ("firma", "typ", "ansprechpartner", "email",
                           "telefon", "notiz")}
    if sub_id.isdigit():
        sub = session.get(Subunternehmer, int(sub_id))
        if sub is not None:
            for name, wert in felder.items():
                if name == "firma" and not wert:
                    continue
                setattr(sub, name, wert)
            sub.aktiv = form.get("aktiv") == "on"
    elif felder["firma"]:
        session.add(Subunternehmer(aktiv=True,
                                   erstellt_von=request.state.benutzer.id,
                                   **felder))
    else:
        return RedirectResponse("/parametrierung/subunternehmer?meldung="
                                + quote_plus("Bitte eine Firma angeben."),
                                status_code=303)
    session.commit()
    return RedirectResponse("/parametrierung/subunternehmer?meldung=Gespeichert",
                            status_code=303)


@router.get("/projektierung-einstellungen")
async def projektierung_einstellungen(request: Request,
                                      session: Session = Depends(get_session)):
    """Demo-Schalter, Standard-Verantwortliche, Absender, Storno-Gründe,
    Ordnervorlage (Anzeige) – nur Admin (Plan Phase 70)."""
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    from app import benachrichtigungen as mail_modul
    from app import projektierung as kern
    from app.models import Benutzer
    benutzer_liste = (session.query(Benutzer)
                      .filter(Benutzer.aktiv.is_(True))
                      .order_by(Benutzer.name).all())
    return render(request, "konfiguration/projektierung_einstellungen.html",
                  aktiv="/parametrierung",
                  freigabe_modus=kern.freigabe_modus(session),
                  benutzer_liste=benutzer_liste,
                  standard_pl=kern.parameter_holen(session, "standard_projektleiter"),
                  standard_fp=kern.parameter_holen(session, "standard_feinplaner"),
                  standard_ep=kern.parameter_holen(session, "standard_elektroplaner"),
                  buchhaltung=kern.parameter_holen(session, "buchhaltung_benutzer"),
                  absender=kern.parameter_holen(session, "absender_postfach",
                                                mail_modul.ABSENDER_STANDARD),
                  gruende="\n".join(kern.storno_gruende(session)),
                  vorlage=kern.ordnervorlage(session),
                  mail_protokoll=kern.parameter_holen(session, "mail_protokoll"),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/projektierung-einstellungen")
async def projektierung_einstellungen_speichern(
        request: Request, session: Session = Depends(get_session)):
    import json as json_modul
    from urllib.parse import quote_plus

    from app import projektierung as kern
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = await request.form()
    if form.get("freigabe_modus") in ("admin", "alle"):
        kern.parameter_setzen(session, "freigabe_modus", form.get("freigabe_modus"))
    for feld, name in (("standard_pl", "standard_projektleiter"),
                       ("standard_fp", "standard_feinplaner"),
                       ("standard_ep", "standard_elektroplaner"),
                       ("buchhaltung", "buchhaltung_benutzer")):
        wert = form.get(feld) or ""
        kern.parameter_setzen(session, name, wert if wert.isdigit() else "")
    absender = (form.get("absender") or "").strip()
    if absender:
        kern.parameter_setzen(session, "absender_postfach", absender)
    gruende = [z.strip() for z in (form.get("gruende") or "").splitlines()
               if z.strip()]
    if gruende:
        kern.parameter_setzen(session, "storno_gruende",
                              json_modul.dumps(gruende, ensure_ascii=False))
    session.commit()
    return RedirectResponse("/parametrierung/projektierung-einstellungen?meldung="
                            + quote_plus("Einstellungen gespeichert."),
                            status_code=303)


# --- v12 (Phase 74): Lead-Management – Steuerdatei ---------------------------------

@router.get("/lead-logik")
async def lead_logik_seite(request: Request,
                           session: Session = Depends(get_session)):
    """Steuerdatei des Lead-Managements: Blätter als Tabellen, Versionsstand,
    Upload. Änderungen wirken auf neue Qualifizierungen; abgeschlossene
    behalten ihre Antworten."""
    from fastapi import HTTPException

    from app import leadmanagement, leadmanagement_logik
    if not leadmanagement.lead_modul_sichtbar(session, request.state.benutzer):
        raise HTTPException(status_code=404)   # Demo-Modus: unsichtbar
    logik = leadmanagement_logik.hole_logik()
    return render(request, "konfiguration/lead_logik.html",
                  aktiv="/parametrierung", logik=logik,
                  pfad=str(leadmanagement_logik.LOGIK_PFAD),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/lead-logik")
async def lead_logik_upload(request: Request,
                            session: Session = Depends(get_session)):
    """Upload wie beim Logik-Import: Backup, ersetzen, neu einlesen; bei
    Fehlern wird die alte Datei wiederhergestellt."""
    import shutil
    from datetime import datetime as dt
    from urllib.parse import quote_plus

    from fastapi import HTTPException

    from app import leadmanagement, leadmanagement_logik
    if not leadmanagement.lead_modul_sichtbar(session, request.state.benutzer):
        raise HTTPException(status_code=404)
    form = await request.form()
    datei = form.get("datei")
    if datei is None or not getattr(datei, "filename", ""):
        return RedirectResponse("/parametrierung/lead-logik?meldung="
                                + quote_plus("Bitte eine .xlsx-Datei wählen."),
                                status_code=303)
    inhalt = await datei.read()
    ziel = leadmanagement_logik.LOGIK_PFAD
    sicherung = None
    if ziel.exists():
        sicherung = (config.BACKUP_ORDNER
                     / f"leadmanagement_logik_{dt.now():%Y%m%d_%H%M%S}.xlsx")
        shutil.copyfile(ziel, sicherung)
    ziel.write_bytes(inhalt)
    logik = leadmanagement_logik.hole_logik(erzwingen=True)
    if logik.fehler:
        if sicherung is not None:
            shutil.copyfile(sicherung, ziel)
            leadmanagement_logik.hole_logik(erzwingen=True)
        return RedirectResponse("/parametrierung/lead-logik?meldung="
                                + quote_plus("Import abgewiesen: "
                                             + " · ".join(logik.fehler)),
                                status_code=303)
    meldung = (f"Steuerdatei übernommen – {len(logik.fragen)} Fragen, "
               f"{len(logik.scoring)} Scoring-Regeln, "
               f"{len(logik.kaskade)} Kaskaden-Stufen"
               + (f", {len(logik.warnungen)} Warnungen" if logik.warnungen else "")
               + (f". Backup: {sicherung.name}" if sicherung else "."))
    return RedirectResponse("/parametrierung/lead-logik?meldung="
                            + quote_plus(meldung), status_code=303)


# --- v12 (Phase 75): Lead-Management – Quellen & Kampagnen, Parser, Demo-Daten -----

def _lead_gate(request: Request, session: Session):
    from fastapi import HTTPException

    from app import leadmanagement
    if not leadmanagement.lead_modul_sichtbar(session, request.state.benutzer):
        raise HTTPException(status_code=404)


@router.get("/lead-quellen")
async def lead_quellen_seite(request: Request,
                             session: Session = Depends(get_session)):
    from app.models import Kampagne, LeadQuelle
    _lead_gate(request, session)
    return render(request, "konfiguration/lead_quellen.html",
                  aktiv="/parametrierung",
                  quellen=session.query(LeadQuelle).order_by(LeadQuelle.name).all(),
                  kampagnen=session.query(Kampagne).order_by(Kampagne.name).all(),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/lead-quellen")
async def lead_quelle_speichern(request: Request,
                                session: Session = Depends(get_session)):
    import json as json_modul
    import re as re_modul
    import secrets
    from urllib.parse import quote_plus

    from app.models import Kampagne, LeadQuelle
    _lead_gate(request, session)
    form = await request.form()
    art = form.get("art") or "quelle"

    if art == "kampagne":
        from datetime import datetime as dt
        kampagne_id = form.get("kampagne_id") or ""
        def _datum(name):
            wert = (form.get(name) or "").strip()
            try:
                return dt.strptime(wert, "%Y-%m-%d") if wert else None
            except ValueError:
                return None
        werte = dict(
            name=(form.get("name") or "").strip()[:200],
            quelle_id=(int(form.get("quelle_id"))
                       if str(form.get("quelle_id") or "").isdigit() else None),
            von=_datum("von"), bis=_datum("bis"),
            budget_cent=(int(float((form.get("budget") or "0").replace(",", ".")) * 100)
                         if (form.get("budget") or "").strip() else None),
            utm_campaign=(form.get("utm_campaign") or "").strip()[:200],
            aktiv=form.get("aktiv") == "on")
        if kampagne_id.isdigit():
            kampagne = session.get(Kampagne, int(kampagne_id))
            if kampagne is not None:
                for feld, wert in werte.items():
                    if feld == "name" and not wert:
                        continue
                    setattr(kampagne, feld, wert)
        elif werte["name"]:
            session.add(Kampagne(erstellt_von=request.state.benutzer.id,
                                 **dict(werte, aktiv=True)))
        session.commit()
        return RedirectResponse("/parametrierung/lead-quellen?meldung=Gespeichert",
                                status_code=303)

    quelle_id = form.get("id") or ""
    schluessel = (form.get("key") or "").strip().lower()
    schluessel = re_modul.sub(r"[^a-z0-9_]", "_", schluessel)[:100]
    sparten = [s for s in form.getlist("standard_sparten")
               if s in ("WP", "PV", "KL", "WB")]
    werte = dict(
        name=(form.get("name") or "").strip()[:200],
        typ=(form.get("typ") if form.get("typ") in
             ("website", "landingpage", "portal", "partner", "telefon",
              "empfehlung", "bestand", "monday") else "website"),
        kanal=(form.get("kanal") or "").strip()[:100] or None,
        kosten_je_lead_cent=(int(float((form.get("kosten") or "0").replace(",", ".")) * 100)
                             if (form.get("kosten") or "").strip() else None),
        standard_sparten=json_modul.dumps(sparten),
        score_bonus=(int(form.get("score_bonus"))
                     if str(form.get("score_bonus") or "").lstrip("-").isdigit() else 0),
        aktiv=form.get("aktiv") == "on")
    if quelle_id.isdigit():
        quelle = session.get(LeadQuelle, int(quelle_id))
        if quelle is not None:
            for feld, wert in werte.items():
                if feld == "name" and not wert:
                    continue
                setattr(quelle, feld, wert)
            if form.get("api_key_neu") == "on":
                quelle.api_key = secrets.token_hex(24)
    elif werte["name"] and schluessel:
        if session.query(LeadQuelle).filter(LeadQuelle.key == schluessel).count():
            return RedirectResponse("/parametrierung/lead-quellen?meldung="
                                    + quote_plus(f"Key {schluessel} existiert schon."),
                                    status_code=303)
        session.add(LeadQuelle(key=schluessel,
                               erstellt_von=request.state.benutzer.id,
                               **dict(werte, aktiv=True)))
    else:
        return RedirectResponse("/parametrierung/lead-quellen?meldung="
                                + quote_plus("Name und Key sind Pflicht."),
                                status_code=303)
    session.commit()
    return RedirectResponse("/parametrierung/lead-quellen?meldung=Gespeichert",
                            status_code=303)


@router.get("/lead-parser")
async def lead_parser_seite(request: Request,
                            session: Session = Depends(get_session)):
    from app.models import LeadQuelle, ParserRegel
    _lead_gate(request, session)
    return render(request, "konfiguration/lead_parser.html",
                  aktiv="/parametrierung",
                  regeln=session.query(ParserRegel).order_by(ParserRegel.id).all(),
                  quellen=session.query(LeadQuelle)
                  .filter(LeadQuelle.aktiv.is_(True)).order_by(LeadQuelle.name).all(),
                  test_ergebnis=None, test_betreff="", test_body="",
                  meldung=request.query_params.get("meldung", ""))


@router.post("/lead-parser")
async def lead_parser_speichern(request: Request,
                                session: Session = Depends(get_session)):
    import json as json_modul
    from urllib.parse import quote_plus

    from app import lead_parser
    from app.models import LeadQuelle, ParserRegel
    _lead_gate(request, session)
    form = await request.form()

    if form.get("art") == "test":
        betreff = form.get("test_betreff") or ""
        body = form.get("test_body") or ""
        regel = lead_parser.regel_finden(session, form.get("test_absender") or "",
                                         betreff)
        ergebnis = {"regel": regel.name if regel else None, "felder": {}}
        if regel is not None:
            felder = lead_parser.mail_parsen(regel, betreff, body)
            felder.pop("rohdaten", None)
            ergebnis["felder"] = felder
        return render(request, "konfiguration/lead_parser.html",
                      aktiv="/parametrierung",
                      regeln=session.query(ParserRegel).order_by(ParserRegel.id).all(),
                      quellen=session.query(LeadQuelle)
                      .filter(LeadQuelle.aktiv.is_(True)).order_by(LeadQuelle.name).all(),
                      test_ergebnis=ergebnis, test_betreff=betreff,
                      test_body=body, meldung="")

    regel_id = form.get("id") or ""
    zuordnung = (form.get("feldzuordnung") or "").strip() or "{}"
    try:
        json_modul.loads(zuordnung)
    except ValueError:
        return RedirectResponse("/parametrierung/lead-parser?meldung="
                                + quote_plus("Feldzuordnung ist kein gültiges JSON."),
                                status_code=303)
    werte = dict(
        name=(form.get("name") or "").strip()[:200],
        quelle_id=(int(form.get("quelle_id"))
                   if str(form.get("quelle_id") or "").isdigit() else None),
        absender_muster=(form.get("absender_muster") or "").strip()[:300],
        betreff_muster=(form.get("betreff_muster") or "").strip()[:300],
        format=(form.get("format") if form.get("format") in
                ("zeilen", "html_tabelle", "json") else "zeilen"),
        feldzuordnung=zuordnung,
        aktiv=form.get("aktiv") == "on")
    if regel_id.isdigit():
        regel = session.get(ParserRegel, int(regel_id))
        if regel is not None:
            for feld, wert in werte.items():
                if feld == "name" and not wert:
                    continue
                setattr(regel, feld, wert)
    elif werte["name"]:
        session.add(ParserRegel(erstellt_von=request.state.benutzer.id,
                                **dict(werte, aktiv=True)))
    session.commit()
    return RedirectResponse("/parametrierung/lead-parser?meldung=Gespeichert",
                            status_code=303)


@router.get("/lead-demo")
async def lead_demo_seite(request: Request,
                          session: Session = Depends(get_session)):
    from app import leadmanagement
    from app.models import Vorgang
    _lead_gate(request, session)
    if request.state.benutzer.rolle != "admin":
        return RedirectResponse("/parametrierung", status_code=303)
    return render(request, "konfiguration/lead_demo.html",
                  aktiv="/parametrierung",
                  demo_aktiv=leadmanagement.demo_aktiv(session),
                  anzahl=session.query(Vorgang)
                  .filter(Vorgang.demo.is_(True)).count(),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/lead-demo")
async def lead_demo_aktion(request: Request,
                           session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app import leadmanagement
    _lead_gate(request, session)
    if request.state.benutzer.rolle != "admin":
        return RedirectResponse("/parametrierung", status_code=303)
    form = await request.form()
    if form.get("aktion") == "erzeugen":
        ergebnis = leadmanagement.demo_leads_erzeugen(session,
                                                      request.state.benutzer)
        meldung = (ergebnis.get("fehler")
                   or f"{ergebnis.get('angelegt', 0)} Demo-Leads erzeugt.")
    elif form.get("aktion") == "loeschen":
        ergebnis = leadmanagement.demo_leads_loeschen(session)
        meldung = (f"{ergebnis['vorgaenge']} Demo-Vorgänge und "
                   f"{ergebnis['kunden']} Demo-Kunden gelöscht.")
    else:
        meldung = "Unbekannte Aktion."
    return RedirectResponse("/parametrierung/lead-demo?meldung="
                            + quote_plus(meldung), status_code=303)


@router.get("/lead-routing")
async def lead_routing_seite(request: Request,
                             session: Session = Depends(get_session)):
    from datetime import datetime as dt

    from app import leadmanagement as lead_kern
    _lead_gate(request, session)
    heute = dt.now().date().isoformat()
    zaehler = {dienst: lead_kern.parameter_holen(
        session, f"aufrufe_{dienst}_{heute}", "0")
        for dienst in ("ors_geocode", "ors_matrix", "google_geocode",
                       "google_matrix", "nominatim")}
    return render(request, "konfiguration/lead_routing.html",
                  aktiv="/parametrierung",
                  anbieter=lead_kern.parameter_holen(session, "routing_anbieter",
                                                     "luftlinie"),
                  ors_key=lead_kern.parameter_holen(session, "ors_api_key"),
                  google_key=lead_kern.parameter_holen(session, "google_api_key"),
                  zaehler=zaehler,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/lead-routing")
async def lead_routing_speichern(request: Request,
                                 session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app import leadmanagement as lead_kern
    from app import routing
    _lead_gate(request, session)
    form = await request.form()
    if form.get("aktion") == "testen":
        meldung = routing.verbindung_testen(session)
        return RedirectResponse("/parametrierung/lead-routing?meldung="
                                + quote_plus(meldung), status_code=303)
    if form.get("routing_anbieter") in ("ors", "google", "luftlinie"):
        lead_kern.parameter_setzen(session, "routing_anbieter",
                                   form.get("routing_anbieter"))
    lead_kern.parameter_setzen(session, "ors_api_key",
                               (form.get("ors_api_key") or "").strip())
    lead_kern.parameter_setzen(session, "google_api_key",
                               (form.get("google_api_key") or "").strip())
    session.commit()
    return RedirectResponse("/parametrierung/lead-routing?meldung=Gespeichert",
                            status_code=303)


@router.get("/lead-vorlagen")
async def lead_vorlagen_seite(request: Request,
                              session: Session = Depends(get_session)):
    """Vorlagen-Gruppe „Lead-Management“ (Phase 78): sechs Schlüssel, je
    Vorlage Betreff + Text, optional je Sparte (Fallback allgemein)."""
    from app import lead_mail
    _lead_gate(request, session)
    schluessel = request.query_params.get("vorlage", "eingangsbestaetigung")
    if schluessel not in lead_mail.VORLAGEN_START:
        schluessel = "eingangsbestaetigung"
    sparte = request.query_params.get("sparte", "")
    betreff, text = lead_mail.vorlage_laden(session, schluessel, sparte)
    return render(request, "konfiguration/lead_vorlagen.html",
                  aktiv="/parametrierung", vorlagen=lead_mail.VORLAGEN_START,
                  schluessel=schluessel, sparte=sparte,
                  betreff=betreff, text=text,
                  platzhalter=lead_mail.PLATZHALTER_NEU,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/lead-vorlagen")
async def lead_vorlagen_speichern(request: Request,
                                  session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app import lead_mail
    from app.models import einstellung_setzen
    _lead_gate(request, session)
    form = await request.form()
    schluessel = form.get("vorlage") or ""
    if schluessel not in lead_mail.VORLAGEN_START:
        return RedirectResponse("/parametrierung/lead-vorlagen", status_code=303)
    sparte = form.get("sparte") if form.get("sparte") in ("WP", "PV", "KL", "WB") else ""
    zusatz = f"_{sparte}" if sparte else ""
    betreff = (form.get("betreff") or "").strip()
    text = (form.get("text") or "").strip()
    if form.get("aktion") == "entfernen" and sparte:
        einstellung_setzen(session, f"lead_vorlage_{schluessel}{zusatz}_betreff", "")
        einstellung_setzen(session, f"lead_vorlage_{schluessel}{zusatz}_text", "")
        session.commit()
        return RedirectResponse(f"/parametrierung/lead-vorlagen?vorlage={schluessel}"
                                "&meldung=Sparten-Vorlage+entfernt", status_code=303)
    if not betreff or not text:
        return RedirectResponse(f"/parametrierung/lead-vorlagen?vorlage={schluessel}"
                                "&meldung=Betreff+und+Text+sind+Pflicht",
                                status_code=303)
    einstellung_setzen(session, f"lead_vorlage_{schluessel}{zusatz}_betreff", betreff)
    einstellung_setzen(session, f"lead_vorlage_{schluessel}{zusatz}_text", text)
    session.commit()
    return RedirectResponse(f"/parametrierung/lead-vorlagen?vorlage={schluessel}"
                            + (f"&sparte={sparte}" if sparte else "")
                            + "&meldung=Gespeichert", status_code=303)


@router.get("/lead-einstellungen")
async def lead_einstellungen(request: Request,
                             session: Session = Depends(get_session)):
    """Lead-Management → Einstellungen (nur Admin, Plan 81)."""
    from app import leadmanagement as lead_kern
    from app.models import Vorgang
    _lead_gate(request, session)
    if request.state.benutzer.rolle != "admin":
        return RedirectResponse("/parametrierung", status_code=303)
    schluessel = ["lead_freigabe_modus", "mail_modus", "mail_testadresse",
                  "parser_modus", "kalender_sync", "kalender_testpostfach",
                  "sla_gruen_min", "sla_gelb_min", "arbeitszeit_lm",
                  "zuweisung_lm", "vorschlag_horizont_tage",
                  "vorschlag_raster_min", "absender_postfach",
                  "kerngebiet_plz", "loeschlauf", "loeschfrist_monate",
                  "firmen_adresse", "demo_badge_text",
                  "erwartungswert_WP", "erwartungswert_PV",
                  "erwartungswert_KL", "erwartungswert_WB",
                  "quote_neu", "quote_in_kontaktierung", "quote_qualifiziert",
                  "quote_terminiert", "quote_erfasst", "quote_angebot"]
    werte = {name: lead_kern.parameter_holen(session, name)
             for name in schluessel}
    vorschau = None
    if request.query_params.get("loeschvorschau") == "1":
        vorschau = lead_kern.loeschlauf(session, trocken=True)
    return render(request, "konfiguration/lead_einstellungen.html",
                  aktiv="/parametrierung", werte=werte,
                  demo_anzahl=session.query(Vorgang)
                  .filter(Vorgang.demo.is_(True)).count(),
                  protokoll=lead_kern.parameter_holen(
                      session, "einstellungs_protokoll"),
                  loesch_protokoll=lead_kern.parameter_holen(
                      session, "loeschlauf_protokoll"),
                  loeschvorschau=vorschau,
                  umstellung=request.query_params.get("umstellung", ""),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/lead-einstellungen")
async def lead_einstellungen_speichern(request: Request,
                                       session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app import leadmanagement as lead_kern
    from app.models import Vorgang
    _lead_gate(request, session)
    benutzer = request.state.benutzer
    if benutzer.rolle != "admin":
        return RedirectResponse("/parametrierung", status_code=303)
    form = await request.form()

    # Demo-Umstellung auf „alle": Dialog erzwingt eine Entscheidung über
    # die vorhandenen Demo-Leads (Plan 73/81)
    neuer_modus = form.get("lead_freigabe_modus") or ""
    if (neuer_modus == "alle"
            and lead_kern.freigabe_modus(session) == "admin"):
        demo_anzahl = (session.query(Vorgang)
                       .filter(Vorgang.demo.is_(True)).count())
        entscheidung = form.get("demo_entscheidung") or ""
        if demo_anzahl and entscheidung not in ("loeschen", "behalten"):
            return RedirectResponse(
                "/parametrierung/lead-einstellungen?umstellung=1&meldung="
                + quote_plus(f"{demo_anzahl} Demo-Leads vorhanden – bitte "
                             "unten entscheiden: löschen oder behalten."),
                status_code=303)
        if entscheidung == "loeschen":
            ergebnis = lead_kern.demo_leads_loeschen(session)
            lead_kern.einstellungs_protokoll(
                session, f"Umstellung auf alle – {ergebnis['vorgaenge']} "
                         "Demo-Leads gelöscht", benutzer)
        elif entscheidung == "behalten":
            lead_kern.demo_kennzeichen_entfernen(session, benutzer)
        lead_kern.parameter_setzen(session, "lead_freigabe_modus", "alle")
        lead_kern.einstellungs_protokoll(session,
                                         "lead_freigabe_modus → alle", benutzer)
    elif neuer_modus == "admin":
        if lead_kern.freigabe_modus(session) != "admin":
            lead_kern.einstellungs_protokoll(session,
                                             "lead_freigabe_modus → admin",
                                             benutzer)
        lead_kern.parameter_setzen(session, "lead_freigabe_modus", "admin")

    # mail_modus: live ist server-seitig nur bei Freigabe „alle" zulässig
    mail_modus = form.get("mail_modus") or ""
    if mail_modus in ("protokoll", "test", "live"):
        if mail_modus == "live" and lead_kern.demo_aktiv(session):
            return RedirectResponse(
                "/parametrierung/lead-einstellungen?meldung="
                + quote_plus("mail_modus=live ist im Demo-Modus nicht "
                             "zulässig (Sendesperre) – erst Freigabe auf "
                             "„alle“ stellen."), status_code=303)
        alt = lead_kern.parameter_holen(session, "mail_modus")
        if mail_modus != alt:
            lead_kern.einstellungs_protokoll(
                session, f"mail_modus {alt} → {mail_modus}", benutzer)
        lead_kern.parameter_setzen(session, "mail_modus", mail_modus)

    einfache = ["mail_testadresse", "kalender_testpostfach", "arbeitszeit_lm",
                "absender_postfach", "kerngebiet_plz", "firmen_adresse",
                "demo_badge_text"]
    zahlen = ["sla_gruen_min", "sla_gelb_min", "vorschlag_horizont_tage",
              "vorschlag_raster_min", "loeschfrist_monate",
              "erwartungswert_WP", "erwartungswert_PV", "erwartungswert_KL",
              "erwartungswert_WB", "quote_neu", "quote_in_kontaktierung",
              "quote_qualifiziert", "quote_terminiert", "quote_erfasst",
              "quote_angebot"]
    for name in einfache:
        if form.get(name) is not None:
            lead_kern.parameter_setzen(session, name,
                                       (form.get(name) or "").strip())
    for name in zahlen:
        wert = (form.get(name) or "").strip()
        if wert.isdigit():
            lead_kern.parameter_setzen(session, name, wert)
    for name in ("parser_modus", "kalender_sync", "loeschlauf"):
        if form.get(name) in ("an", "aus"):
            alt = lead_kern.parameter_holen(session, name)
            if form.get(name) != alt:
                lead_kern.einstellungs_protokoll(
                    session, f"{name} {alt} → {form.get(name)}", benutzer)
            lead_kern.parameter_setzen(session, name, form.get(name))
    if form.get("zuweisung_lm") in ("round_robin",):
        lead_kern.parameter_setzen(session, "zuweisung_lm",
                                   form.get("zuweisung_lm"))
    session.commit()
    return RedirectResponse("/parametrierung/lead-einstellungen?meldung="
                            + quote_plus("Einstellungen gespeichert."),
                            status_code=303)
