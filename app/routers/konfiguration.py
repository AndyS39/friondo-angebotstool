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
