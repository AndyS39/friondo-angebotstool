# Parametrierung (ehemals "Konfiguration", Phase 18): Logik-Excel einlesen,
# Validierungsbericht anzeigen, "Neu einlesen".

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import config, logik as logik_modul
from app.db import get_session
from app.templating import render
from app import anfrage   # v27: Formular/JSON in def-Routen

router = APIRouter(prefix="/parametrierung")


# --- v26 (PLAN_PROJ_V5 Phase 125): Parametrierung neu gegliedert ---------------------
# Die Übersicht ist eine reine Verteilerseite (fünf Bereichskarten); die
# Inline-Abschnitte der alten Übersicht liegen auf /parametrierung/angebotstool
# (Einstellungen) und /parametrierung/logik (Logik-Excel, Importe). Der Kontext
# der alten Route wird nur umverteilt – eine Hilfsfunktion, drei Routen.

def _zurueck_ziel(request: Request, fallback: str = "/parametrierung") -> str:
    """Pfad der Seite, von der ein Parametrierungs-Formular kam (Referer) –
    nur Pfade unter /parametrierung, ohne Query/Fragment; sonst der Fallback."""
    import re
    from urllib.parse import urlsplit
    pfad = urlsplit(request.headers.get("referer", "") or "").path
    if re.fullmatch(r"/parametrierung(/[A-Za-z0-9_\-]+)*/?", pfad or ""):
        return pfad.rstrip("/") or "/parametrierung"
    return fallback


def _parametrierung_kontext(session: Session) -> dict:
    """Kontext der früheren Übersicht (v25) – Logik-Excel, Validierung, PV-/KL-
    Parameter und die pflegbaren Einstellungen. Fehlt die Logik-Excel, fehlen
    nur die Logik-Werte (`dateifehler`); die Einstellungen bleiben erreichbar."""
    from app import mail_sync, wirtschaftlichkeit
    from app.models import AblehnungsGrund, AngebotsLoeschung, einstellung_holen
    if config.LOGIK_EXCEL_PFAD.exists():
        logik, bericht = logik_modul.hole_logik(session)
        # v22 (Phase 102): fehlende Wirtschaftlichkeits-Parameter mit Standardwert
        _pv_param, pv_fehlende = wirtschaftlichkeit.parameter_lesen(logik.pv_parameter)
        pv_neue = {zeile[0] for zeile in wirtschaftlichkeit.NEUE_PARAMETER_ZEILEN}
        pv_fehlende = [name for name in pv_fehlende if name in pv_neue]
        # v24 (PLAN_V16 Phase 113/115): fehlende KL-Parameter mit Standardwert
        kl_fehlende = logik_modul.kl_parameter_fehlende(logik) if logik.kl_aktionen else []
        logik_werte = dict(
            logik=logik, bericht=bericht, dateifehler=None,
            pv_fehlende=pv_fehlende,
            pv_standard={name: wirtschaftlichkeit.standardwert_text(name)
                         for name in pv_fehlende},
            kl_fehlende=kl_fehlende,
            kl_standard={name: logik_modul.kl_standardwert_text(name)
                         for name in kl_fehlende})
    else:
        logik_werte = dict(logik=None, bericht=None, dateifehler=str(config.LOGIK_EXCEL_PFAD),
                           pv_fehlende=[], pv_standard={}, kl_fehlende=[], kl_standard={})
    return dict(
        **logik_werte,
        kl_import_ok=_import_klima() is not None,
        ablehnungsgruende=(session.query(AblehnungsGrund)
                           .order_by(AblehnungsGrund.sort, AblehnungsGrund.id).all()),
        ablehnung_tage=einstellung_holen(session, "ablehnung_auto_tage", "90"),
        ablehnung_protokoll=einstellung_holen(session, "ablehnung_auto_protokoll", ""),
        db_rot=einstellung_holen(session, "db_ampel_rot_unter", "9000"),
        db_gruen=einstellung_holen(session, "db_ampel_gruen_ueber", "10000"),
        # v13-PV (Phase 78): eigene Schwellen je Sparte (leer = allgemein)
        db_sparten={sp: (einstellung_holen(session, f"db_ampel_rot_unter_{sp}", ""),
                         einstellung_holen(session, f"db_ampel_gruen_ueber_{sp}", ""))
                    for sp in ("WP", "PV", "KL", "WB")},
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
                     .limit(50).all()))


def _golive_stand(request: Request, session: Session):
    """Badge „<n>/11 grün“ am Eintrag Go-live-Checkliste (nur Admin) –
    (grün, gesamt) oder None; ein Fehler der Prüfung blockiert die Übersicht nie."""
    benutzer = request.state.benutzer
    if benutzer is None or benutzer.rolle != "admin":
        return None
    try:
        from app import golive
        punkte = golive.pruefen(session)
    except Exception:
        return None
    return sum(1 for p in punkte if p.ok), len(punkte)


@router.get("")
def uebersicht(request: Request, session: Session = Depends(get_session)):
    """Verteilerseite: Suchfeld + fünf Bereichskarten (Allgemein · Angebotstool ·
    Projektierung · Lead-Management · System & Protokolle). Rendert auch ohne
    Logik-Excel (dateifehler → Hinweis, Karten ohne Logik-Daten)."""
    from app import import_preisliste
    return render(request, "konfiguration/uebersicht.html", aktiv="/parametrierung",
                  dateifehler=(None if config.LOGIK_EXCEL_PFAD.exists()
                               else str(config.LOGIK_EXCEL_PFAD)),
                  golive_stand=_golive_stand(request, session),
                  # v27 (Phase 128): Hinweistext für den Knopf „Parametrierung neu einlesen“
                  import_hinweise=import_preisliste.import_hinweise(session),
                  meldung=request.query_params.get("meldung", ""))


@router.get("/angebotstool")
def angebotstool_seite(request: Request, session: Session = Depends(get_session)):
    """Angebotstool-Einstellungen: DB-Ampel, E-Mail-/Kombi-Versand, gewerke-
    übergreifende Artikel, Fern-Signatur, Abgelehnt-Prozess, Lösch-Protokoll –
    die Inline-Abschnitte der alten Übersicht, Formulare unverändert."""
    return render(request, "konfiguration/angebotstool.html", aktiv="/parametrierung",
                  **_parametrierung_kontext(session),
                  meldung=request.query_params.get("meldung", ""))


@router.get("/logik")
def logik_seite(request: Request, session: Session = Depends(get_session)):
    """Logik & Importe: Quelle/zuletzt eingelesen, Validierungsbericht, „Neu
    einlesen“, Tabellen der Logik-Excel (Fragen, Angebotsaufbau, KfW-/PV-/KL-
    Parameter) und der Klima-Import – 1:1 aus der alten Übersicht."""
    from app import import_preisliste
    return render(request, "konfiguration/logik.html", aktiv="/parametrierung",
                  **_parametrierung_kontext(session),
                  # v27 (Phase 128): Hinweis „Dauer etwa <n> s …“ je Import-Button
                  import_hinweise=import_preisliste.import_hinweise(session),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/einstellungen")
def einstellungen_speichern(request: Request,
                                  session: Session = Depends(get_session)):
    """DB-Ampel-Schwellen (Phase 24) und weitere pflegbare Werte."""
    from app.models import einstellung_setzen
    form = anfrage.formular(request)
    for name in ("db_ampel_rot_unter", "db_ampel_gruen_ueber"):
        wert = (form.get(name) or "").strip().replace(".", "")
        if wert.isdigit():
            einstellung_setzen(session, name, wert)
    # v13-PV: Schwellen je Sparte – leer = allgemeine Schwellen
    if "db_sparten_formular" in form:
        for sp in ("WP", "PV", "KL", "WB"):
            for name in (f"db_ampel_rot_unter_{sp}", f"db_ampel_gruen_ueber_{sp}"):
                wert = (form.get(name) or "").strip().replace(".", "")
                if wert == "" or wert.isdigit():
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
    # v26 (Phase 125): zurück auf die Seite, von der das Formular kam
    # (Angebotstool-Einstellungen), Fallback Übersicht
    return RedirectResponse(_zurueck_ziel(request) + "?meldung=Einstellungen+gespeichert",
                            status_code=303)


@router.get("/profile")
def profile_seite(request: Request, block_id: int = 0,
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
def profil_speichern(request: Request, profil_id: int,
                           session: Session = Depends(get_session)):
    """v9: Kanal-Zuordnung, Textblöcke und Versandregeln eines Profils."""
    from urllib.parse import quote_plus

    from app.models import Profil
    profil = session.get(Profil, profil_id)
    if profil is None:
        return RedirectResponse("/parametrierung/profile", status_code=303)
    form = anfrage.formular(request)
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
def textblock_speichern(request: Request,
                              session: Session = Depends(get_session)):
    """v9: Textblock bearbeiten oder neu anlegen."""
    from urllib.parse import quote_plus

    from app.models import Textblock
    form = anfrage.formular(request)
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
def ablehnungsgruende_pflegen(request: Request,
                                    session: Session = Depends(get_session)):
    """v8: Auswahlliste „Grund der Ablehnung“ pflegen (hinzufügen bzw.
    deaktivieren/aktivieren – gelöscht wird nicht, Altdaten bleiben lesbar)."""
    from urllib.parse import quote_plus

    from app.models import AblehnungsGrund
    form = anfrage.formular(request)
    # v26 (Phase 125): zurück auf die Seite, von der das Formular kam – auf der
    # Angebotstool-Seite direkt zum Abschnitt „Abgelehnt-Prozess“
    zurueck = _zurueck_ziel(request)
    anker = "#ablehnung" if zurueck != "/parametrierung" else ""
    if form.get("aktion") == "hinzufuegen":
        name = (form.get("name") or "").strip()[:100]
        if name and session.query(AblehnungsGrund).filter_by(name=name).count() == 0:
            session.add(AblehnungsGrund(
                name=name, sort=session.query(AblehnungsGrund).count()))
            session.commit()
            return RedirectResponse(zurueck + "?meldung=" + quote_plus(
                f"Ablehnungsgrund „{name}“ hinzugefügt") + anker, status_code=303)
    elif form.get("aktion") == "umschalten":
        grund = session.get(AblehnungsGrund, int(form.get("id") or 0))
        if grund is not None:
            grund.aktiv = not grund.aktiv
            session.commit()
    return RedirectResponse(zurueck + anker, status_code=303)


# --- E-Mail-Vorlagen (Phase 30) ------------------------------------------

def _vorlagen_sparte(wert: str) -> str:
    """v27-Nachtrag 2: Reiter-Parameter „sparte“ (WP/PV/KL/WB), sonst leer."""
    from app import mail_vorlagen
    wert = (wert or "").strip().upper()
    return wert if wert in mail_vorlagen.SPARTEN else ""


@router.get("/vorlagen")
def vorlagen_uebersicht(request: Request, benutzer_id: int = 0,
                              angebot_id: int = 0, sparte: str = "",
                              session: Session = Depends(get_session)):
    """Standard-Vorlage + optionale Vorlage je Außendienstler, mit Platzhalter-
    liste und Vorschau anhand eines echten Angebots.
    v27-Nachtrag 2: Reiter je Sparte (?sparte=WP|PV|KL|WB) – die Sparten-Vorlage
    greift beim Versand nach der AD-Vorlage und vor dem Standard."""
    from app import mail_vorlagen
    from app.models import Angebot, Benutzer, Kunde
    sparte = _vorlagen_sparte(sparte)
    if sparte:
        benutzer_id = 0           # Reiter Sparte und AD-Auswahl schließen sich aus
    aussendienst = (session.query(Benutzer)
                    .filter(Benutzer.rolle == "aussendienst", Benutzer.aktiv.is_(True))
                    .order_by(Benutzer.name).all())
    ausgewaehlt = session.get(Benutzer, benutzer_id) if benutzer_id else None
    if sparte:
        betreff, text, quelle = mail_vorlagen.vorlage_laden(session, None, sparte)
        # Hat die Sparte eine eigene Vorlage? (sonst Standard als Ausgangspunkt)
        eigene = quelle != "Standard-Vorlage"
    else:
        betreff, text, quelle = mail_vorlagen.vorlage_laden(session, benutzer_id or None)
        # Hat der AD eine eigene Vorlage? (sonst zeigen wir den Standard als Vorschlag)
        eigene = bool(benutzer_id) and quelle != "Standard-Vorlage"
    # Vorlagen-Status je AD für die Übersicht
    hat_vorlage = {b.id: mail_vorlagen.vorlage_laden(session, b.id)[2] != "Standard-Vorlage"
                   for b in aussendienst}
    # Vorschau: gewähltes Angebot, im Sparten-Reiter das neueste Angebot der
    # Sparte, sonst das neueste Angebot
    angebote = (session.query(Angebot).filter(Angebot.archiviert.is_(False))
                .order_by(Angebot.nummer.desc()).limit(30).all())
    if angebot_id:
        vorschau_angebot = session.get(Angebot, angebot_id)
    else:
        vorschau_angebot = angebote[0] if angebote else None
        if sparte:
            vorschau_angebot = next((a for a in angebote
                                     if (a.konfigurator_typ or "WP").upper() == sparte),
                                    vorschau_angebot)
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
                  sparte=sparte, sparten=mail_vorlagen.SPARTEN,
                  sparten_namen=mail_vorlagen.SPARTEN_NAMEN,
                  sparten_status=mail_vorlagen.sparten_status(session),
                  platzhalter=mail_vorlagen.PLATZHALTER,
                  unbekannt=mail_vorlagen.unbekannte_platzhalter(betreff + text),
                  angebote=angebote, vorschau_angebot=vorschau_angebot,
                  vorschau=vorschau,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/vorlagen")
def vorlagen_speichern(request: Request, session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app import mail_vorlagen
    form = anfrage.formular(request)
    benutzer_id = form.get("benutzer_id") or ""
    bid = int(benutzer_id) if benutzer_id.isdigit() and int(benutzer_id) > 0 else None
    # v27-Nachtrag 2: Sparten-Vorlage (Reiter) – Ziel nach dem Speichern bleibt der Reiter
    sparte = _vorlagen_sparte(form.get("sparte") or "")
    if sparte:
        bid = None
    zurueck = (f"/parametrierung/vorlagen?sparte={sparte}" if sparte
               else f"/parametrierung/vorlagen?benutzer_id={bid or 0}")
    aktion = form.get("aktion") or "speichern"
    if aktion == "entfernen" and sparte:
        # Sparten-Vorlage löschen → Standard greift wieder
        mail_vorlagen.sparten_vorlage_speichern(session, sparte, "", "")
        session.commit()
        return RedirectResponse(zurueck + "&meldung=" + quote_plus(
            f"Sparten-Vorlage {sparte} entfernt – Standard gilt"), status_code=303)
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
        return RedirectResponse(zurueck + "&meldung="
                                + quote_plus("Betreff und Text dürfen nicht leer sein"),
                                status_code=303)
    mail_vorlagen.vorlage_speichern(session, bid, betreff, text, sparte=sparte)
    session.commit()
    unbekannt = mail_vorlagen.unbekannte_platzhalter(betreff + text)
    meldung = f"Sparten-Vorlage {sparte} gespeichert" if sparte else "Vorlage gespeichert"
    if unbekannt:
        meldung += " – unbekannte Platzhalter bleiben im Text stehen: " + ", ".join(unbekannt)
    return RedirectResponse(zurueck + "&meldung=" + quote_plus(meldung), status_code=303)


# --- E-Mail-Signaturen (v6, Phase 42) --------------------------------------

@router.get("/signaturen")
def signaturen_uebersicht(request: Request, benutzer_id: int = 0,
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
def signatur_bild(benutzer_id: int, cid: str):
    """Inline-Bild der Signatur für die Vorschau (cid → Datei)."""
    from fastapi.responses import FileResponse, Response

    from app import signaturen
    _, bilder = signaturen.fuer_versand(benutzer_id)
    for bild_cid, pfad, mime in bilder:
        if bild_cid == cid:
            return FileResponse(pfad, media_type=mime)
    return Response(status_code=404)


@router.post("/signaturen/{benutzer_id}")
def signatur_hochladen(request: Request, benutzer_id: int,
                             session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app import signaturen
    form = anfrage.formular(request)
    if form.get("aktion") == "entfernen":
        signaturen.entfernen(benutzer_id)
        return RedirectResponse(f"/parametrierung/signaturen?benutzer_id={benutzer_id}"
                                "&meldung=Signatur+entfernt+%E2%80%93+Standard+gilt",
                                status_code=303)
    dateien = []
    for feld in form.getlist("dateien"):
        if hasattr(feld, "filename") and feld.filename:
            dateien.append((feld.filename, feld.file.read()))
    ok, meldung = signaturen.speichern(benutzer_id, dateien)
    return RedirectResponse(f"/parametrierung/signaturen?benutzer_id={benutzer_id}"
                            f"&meldung={quote_plus(meldung)}", status_code=303)


@router.get("/monday")
def monday_uebersicht(request: Request, session: Session = Depends(get_session)):
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
    if config.MONDAY_API_TOKEN and quellen:
        # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben – die
        # Board-Abfragen (Spalten/Gruppen je Quelle) dauern je bis zu 30 s
        from app.db import verbindung_freigeben
        verbindung_freigeben(session)
        board_ids = [q.board_id for q in quellen]
        for board_id in board_ids:
            try:
                spalten[board_id] = monday_sync.spalten_laden(board_id)
                gruppen[board_id] = monday_sync.gruppen_laden(board_id)
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
def monday_quelle_speichern(request: Request,
                                  session: Session = Depends(get_session)):
    from app.models import MondayQuelle
    form = anfrage.formular(request)
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
def monday_mapping_speichern(request: Request, board_id: str,
                                   session: Session = Depends(get_session)):
    from app.models import MondayMapping, MONDAY_FELDER
    form = anfrage.formular(request)
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
def monday_rueckspielung_speichern(request: Request, board_id: str,
                                         session: Session = Depends(get_session)):
    """Rückspiel-Konfiguration je Quell-Board (Phase 32)."""
    from app.models import MondayQuelle
    form = anfrage.formular(request)
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
def monday_person_zuordnen(request: Request, person_id: int,
                                 session: Session = Depends(get_session)):
    from app import monday_sync
    from urllib.parse import quote_plus

    from app.models import MondayPerson
    form = anfrage.formular(request)
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
def projektierung_logik_seite(request: Request,
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
def projektierung_logik_upload(request: Request,
                                     session: Session = Depends(get_session)):
    """Upload wie beim Logik-Import: Backup der alten Datei, ersetzen,
    neu einlesen; bei Fehlern wird die alte Datei wiederhergestellt."""
    import shutil
    from datetime import datetime as dt
    from urllib.parse import quote_plus

    from app import projektierung_logik
    form = anfrage.formular(request)
    datei = form.get("datei")
    if datei is None or not getattr(datei, "filename", ""):
        return RedirectResponse("/parametrierung/projektierung-logik?meldung="
                                + quote_plus("Bitte eine .xlsx-Datei wählen."),
                                status_code=303)
    inhalt = datei.file.read()
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
def neu_einlesen(request: Request, session: Session = Depends(get_session)):
    import time
    from urllib.parse import quote_plus

    from app import import_preisliste
    # v26 (Phase 125): zurück auf die Seite mit dem Button (Übersicht oder
    # Logik & Importe); ohne Referer auf Logik & Importe, wo der Bericht steht
    zurueck = _zurueck_ziel(request, "/parametrierung/logik")
    if not config.LOGIK_EXCEL_PFAD.exists():
        return RedirectResponse(zurueck, status_code=303)
    # v27 (PLAN_V17 Phase 128): Hinweis vor dem Start muss bestätigt sein
    # (Häkchen/verstecktes Feld „bestaetigt“); Dauer des Laufs wird gemerkt
    if not import_preisliste.import_bestaetigt(anfrage.formular(request)):
        return RedirectResponse(
            f"{zurueck}?meldung={quote_plus(import_preisliste.HINWEIS_BESTAETIGEN)}",
            status_code=303)
    start = time.perf_counter()
    _, bericht = logik_modul.neu_einlesen(session)
    import_preisliste.import_dauer_merken(session, "logik", start)
    if bericht.ok:
        meldung = "Parametrierung+neu+eingelesen+–+keine+Fehler"
    else:
        meldung = f"Parametrierung+neu+eingelesen+–+{len(bericht.fehler)}+Fehler+gefunden"
    return RedirectResponse(f"{zurueck}?meldung={meldung}", status_code=303)


# --- v24 (PLAN_V16 Phase 113/115): Klimakonfigurator -------------------------------

def _import_klima():
    """Klima-Import (app/import_klima.py, Agent A) lazy laden – fehlt das Modul,
    bleibt die Parametrierung nutzbar und der Button meldet es."""
    try:
        from app import import_klima
    except ImportError:
        return None
    return import_klima


def _kl_zurueck(meldung: str, ziel: str = "/parametrierung/logik") -> RedirectResponse:
    """v26: Klima-Import kehrt nach Logik & Importe zurück (dort stehen die
    Import-Buttons und KL-Parameter der früheren Übersicht)."""
    from urllib.parse import quote_plus
    return RedirectResponse(f"{ziel}?meldung={quote_plus(meldung)}", status_code=303)


def _ist_kl_meldung(text: str) -> bool:
    """Prüfmeldungen des Klimakonfigurators (Lesesicht zeigt nur diese)."""
    import re
    return bool(re.search(r"\bKL\b|KL\d{3}|Klima|Fragen KL|Montagematrix|Paketmatrix KL|"
                          r"Kombinationen KL|KL-Parameter|KL-Artikel", text))


@router.get("/artikel/kl-import")
def kl_import_vorschau(request: Request, session: Session = Depends(get_session)):
    """Vorschau „Artikel → Klima-Positionslisten importieren“ (Ordner
    Artikel-Preislisten/Klima/): wie der PV-Import erst das Diff zeigen,
    gespeichert wird erst mit „Import ausführen“ (POST)."""
    from app import import_preisliste
    modul = _import_klima()
    # v27 (Phase 128): Hinweis „Dauer etwa <n> s …“ + Bestätigungs-Häkchen
    hinweis = import_preisliste.import_hinweis(session, "klima")
    meldung = request.query_params.get("meldung", "")
    if modul is None:
        return render(request, "konfiguration/kl_import.html", aktiv="/parametrierung",
                      diff=None, dateifehler=[], modul_fehlt=True, ordner="",
                      hinweis=hinweis, meldung=meldung)
    ordner = modul.kl_ordner()
    if not ordner.exists():
        return render(request, "konfiguration/kl_import.html", aktiv="/parametrierung",
                      diff=None, dateifehler=[str(ordner)], modul_fehlt=False,
                      ordner=str(ordner), hinweis=hinweis, meldung=meldung)
    return render(request, "konfiguration/kl_import.html", aktiv="/parametrierung",
                  diff=modul.berechne_diff(session), dateifehler=[], modul_fehlt=False,
                  ordner=str(ordner), hinweis=hinweis, meldung=meldung)


@router.post("/artikel/kl-import")
def kl_import_ausfuehren(request: Request, session: Session = Depends(get_session)):
    """Button „Artikel → Klima-Positionslisten importieren“: KL001–KL050 anlegen/
    aktualisieren (GUID-Anker Blatt „KL-Artikel“), danach die Logik neu einlesen,
    damit die KL-Referenzen gegen den Artikelstamm geprüft werden.
    v27 (PLAN_V17 Phase 128): nur mit bestätigtem Hinweis (Feld „bestaetigt“);
    die Dauer des Laufs wird als Einstellung import_dauer_klima gemerkt."""
    import time

    from app import import_preisliste
    modul = _import_klima()
    if modul is None:
        return _kl_zurueck("Klima-Import nicht verfügbar – app/import_klima.py fehlt.")
    if not import_preisliste.import_bestaetigt(anfrage.formular(request)):
        return _kl_zurueck(import_preisliste.HINWEIS_BESTAETIGEN)
    start = time.perf_counter()
    try:
        _diff, meldung = modul.import_ausfuehren(session)
    except OSError as exc:        # Positionsliste nicht lesbar – kein Absturz der Seite
        session.rollback()
        return _kl_zurueck(f"Klima-Import fehlgeschlagen: {exc}")
    logik_modul.neu_einlesen(session)
    import_preisliste.import_dauer_merken(session, "klima", start)
    return _kl_zurueck(f"Klima-Import abgeschlossen: {meldung}")


@router.get("/kl-logik")
def kl_logik_seite(request: Request, session: Session = Depends(get_session)):
    """Lesesicht des Klimakonfigurators: Paketmatrix KL, Montagematrix KL,
    Kombinationen KL, Aktionen KL, KL-Parameter und die KL-Artikel (Blatt +
    Artikelstamm, Filter Sparte KL = pos_nr KL*). Nur Anzeige – Live-Master
    bleibt die Logik-Excel; AD sieht nie EK."""
    if not config.LOGIK_EXCEL_PFAD.exists():
        return RedirectResponse("/parametrierung", status_code=303)
    from app import import_preisliste
    from app.models import Artikel
    logik, bericht = logik_modul.hole_logik(session)
    kombis = []
    for name, je_anzahl in logik.kl_kombis.items():
        for anzahl in sorted(je_anzahl):
            kombis.append((name, logik.kl_kombi_artikel.get(name, ""), anzahl,
                           sorted(je_anzahl[anzahl],
                                  key=lambda k: [int(c) for c in k.split("+")])))
    bestand: dict[str, Artikel] = {}
    for artikel in (session.query(Artikel).filter(Artikel.pos_nr.like("KL%"))
                    .order_by(Artikel.aktiv.desc(), Artikel.pos_nr, Artikel.id)):
        bestand.setdefault(artikel.pos_nr, artikel)
    benutzer = request.state.benutzer
    kl_fehlende = logik_modul.kl_parameter_fehlende(logik) if logik.kl_aktionen else []
    return render(request, "konfiguration/kl_logik.html", aktiv="/parametrierung",
                  logik=logik, bericht=bericht, kombis=kombis, bestand=bestand,
                  kl_fehler=[f for f in bericht.fehler if _ist_kl_meldung(f)],
                  kl_warnungen=[w for w in bericht.warnungen if _ist_kl_meldung(w)],
                  kl_fehlende=kl_fehlende,
                  kl_standard={name: logik_modul.kl_standardwert_text(name)
                               for name in kl_fehlende},
                  ek_sichtbar=benutzer is not None and benutzer.rolle != "aussendienst",
                  kl_import_ok=_import_klima() is not None,
                  # v27 (Phase 128): Hinweis „Dauer etwa <n> s …“ für die Import-Buttons
                  import_hinweise=import_preisliste.import_hinweise(session),
                  meldung=request.query_params.get("meldung", ""))


# --- v11 (Phase 70): Stammseiten der Projektierung --------------------------------

def _nur_admin(request: Request):
    """Projektierung-Einstellungen (Demo-Schalter usw.) sind Admin-exklusiv."""
    benutzer = request.state.benutzer
    if benutzer is None or benutzer.rolle != "admin":
        return RedirectResponse("/parametrierung", status_code=303)
    return None


@router.get("/teams")
def teams_seite(request: Request, session: Session = Depends(get_session)):
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
                  benutzer_liste=sorted(
                      [b for b in benutzer_map.values() if b.aktiv],
                      key=lambda b: b.name),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/teams")
def team_speichern(request: Request, session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app.models import Team
    form = anfrage.formular(request)
    team_id = form.get("team_id") or ""
    name = (form.get("name") or "").strip()
    # v15 (Phase 75): Typen montage | sub (Altwerte bleiben lesbar)
    typ = (form.get("typ") if form.get("typ")
           in ("montage", "sub", "SHK", "Elektro", "Sonstige") else "montage")
    leiter = form.get("leiter_id") or "0"
    farbe = (form.get("farbe") or "").strip()[:20]
    outlook = (form.get("outlook_adresse") or "").strip()[:200]
    if team_id.isdigit():
        team = session.get(Team, int(team_id))
        if team is not None:
            if name:
                team.name = name
            team.typ = typ
            team.aktiv = form.get("aktiv") == "on"
            team.leiter_id = int(leiter) if leiter.isdigit() and int(leiter) else None
            team.farbe = farbe
            team.outlook_adresse = outlook
    elif name:
        session.add(Team(name=name, typ=typ, aktiv=True, farbe=farbe,
                         leiter_id=int(leiter) if leiter.isdigit() and int(leiter) else None,
                         outlook_adresse=outlook,
                         erstellt_von=request.state.benutzer.id))
    else:
        return RedirectResponse("/parametrierung/teams?meldung="
                                + quote_plus("Bitte einen Namen angeben."),
                                status_code=303)
    session.commit()
    return RedirectResponse("/parametrierung/teams?meldung=Gespeichert",
                            status_code=303)


@router.get("/subunternehmer")
def subs_seite(request: Request, session: Session = Depends(get_session)):
    import json as json_modul

    from app import projektierung, projektierung_logik
    from app.models import Subunternehmer
    # v15 (Phase 79): Standard-Sub je Typ (Vorbelegung im Mail-Dialog)
    try:
        standards = {str(k): int(v) for k, v in json_modul.loads(
            projektierung.parameter_holen(session, "sub_standards", "{}")).items()}
    except (ValueError, TypeError):
        standards = {}
    return render(request, "konfiguration/subunternehmer.html",
                  aktiv="/parametrierung", standards=standards,
                  subs=session.query(Subunternehmer)
                  .order_by(Subunternehmer.firma).all(),
                  typen=projektierung_logik.sub_typen(session),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/subunternehmer")
def sub_speichern(request: Request, session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app.models import Subunternehmer
    form = anfrage.formular(request)
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
        sub = Subunternehmer(aktiv=True,
                             erstellt_von=request.state.benutzer.id,
                             **felder)
        session.add(sub)
    else:
        return RedirectResponse("/parametrierung/subunternehmer?meldung="
                                + quote_plus("Bitte eine Firma angeben."),
                                status_code=303)
    session.flush()
    # v15 (Phase 79): Standard-Sub je Typ (Vorbelegung im Mail-Dialog)
    if sub is not None:
        from app import sub_mail as sub_mail_modul
        if form.get("standard") == "on":
            sub_mail_modul.standard_sub_setzen(session, sub.typ, sub.id)
        elif sub_mail_modul.standard_sub_id(session, sub.typ) == sub.id:
            sub_mail_modul.standard_sub_setzen(session, sub.typ, None)
    session.commit()
    return RedirectResponse("/parametrierung/subunternehmer?meldung=Gespeichert",
                            status_code=303)


# v26 (PLAN_PROJ_V5 Phase 122): die Heizreport-Helfer der Phase 93 sind nach
# app/routers/konfiguration_heizreport.py umgezogen (Parametrierung → Heizreport).


def _proj_protokoll(session, kern, zeile: str, benutzer) -> None:
    """v28: Verlauf der Projektierungs-Parametrierung (letzte 20 Zeilen im
    Parameter einstellungs_protokoll) – wie das Protokoll der Lead-Einstellungen."""
    from datetime import datetime as _dt
    alt = kern.parameter_holen(session, "einstellungs_protokoll", "")
    wer = getattr(benutzer, "name", "") or "System"
    zeilen = [f"{_dt.now():%d.%m.%Y %H:%M} {wer}: {zeile}"]
    zeilen += [z for z in alt.splitlines() if z.strip()]
    kern.parameter_setzen(session, "einstellungs_protokoll", "\n".join(zeilen[:20]))


@router.get("/projektierung-einstellungen")
def projektierung_einstellungen(request: Request,
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
                  pilot_ids=kern.pilot_benutzer_ids(session),
                  galerie_zusatzordner=kern.parameter_holen(
                      session, "galerie_zusatzordner", ""),
                  galerie_original=kern.parameter_holen(
                      session, "galerie_original_behalten", "aus"),
                  # v15 (Phase 78): Portal-URLs für Link-Aufgaben
                  url_bza_portal=kern.parameter_holen(session, "url_bza_portal", ""),
                  # V4 (Phase 92): KfW-Zuschussportal, Test-Adresse, BzA-Mail
                  url_kfw_zuschussportal=kern.parameter_holen(
                      session, "url_kfw_zuschussportal", ""),
                  projekt_testadresse=kern.parameter_holen(session, "projekt_testadresse", ""),
                  bza_mail_aktiv=__import__("app.bza", fromlist=["x"]).mail_aktiv(session),
                  bza_mail_betreff=kern.parameter_holen(session, "bza_mail_betreff", "")
                  or __import__("app.bza", fromlist=["x"]).BETREFF_STANDARD,
                  bza_mail_text=kern.parameter_holen(session, "bza_mail_text", "")
                  or __import__("app.bza", fromlist=["x"]).TEXT_STANDARD,
                  url_spotmyenergy=kern.parameter_holen(session,
                                                        "url_spotmyenergy", ""),
                  url_heizreport=kern.parameter_holen(session,
                                                      "url_heizreport", ""),
                  # v15 (Phase 80): UGL/Collin + GC Online Plus
                  url_gc_online=kern.parameter_holen(session, "url_gc_online", ""),
                  collin_kundennummer=kern.parameter_holen(
                      session, "collin_kundennummer", ""),
                  # V4 (Phase 93.2): Lieferantennummer (KOP 14–23) + Standard-Lieferant
                  collin_lieferantennummer=kern.parameter_holen(
                      session, "collin_lieferantennummer", ""),
                  standard_lieferant=kern.parameter_holen(
                      session, "stueckliste_standard_lieferant", "Collin"),
                  ugl_lieferadresse=kern.parameter_holen(
                      session, "ugl_lieferadresse", "ausfuehrung"),
                  lager_adresse=kern.parameter_holen(session, "lager_adresse", ""),
                  bza_fachunternehmer=kern.parameter_holen(
                      session, "bza_fachunternehmer", "Friondo GmbH"),
                  # v15 (Phase 81): Outlook-Kalender + Terminmail
                  outlook_kalender_modus=kern.parameter_holen(
                      session, "outlook_kalender_modus", "postfach"),
                  outlook_kalender_adresse=kern.parameter_holen(
                      session, "outlook_kalender_adresse", ""),
                  basis_url=kern.parameter_holen(session, "basis_url", ""),
                  terminmail_betreff=kern.parameter_holen(
                      session, "terminmail_betreff",
                      __import__("app.terminmail", fromlist=["x"]).BETREFF_STANDARD),
                  terminmail_text=kern.parameter_holen(
                      session, "terminmail_text",
                      __import__("app.terminmail", fromlist=["x"]).TEXT_STANDARD),
                  terminmail_vorbereitung=kern.parameter_holen(
                      session, "terminmail_vorbereitung",
                      __import__("app.terminmail",
                                 fromlist=["x"]).VORBEREITUNG_STANDARD),
                  benutzer_liste=benutzer_liste,
                  # V4 (Phase 90.3): Vorlauf-Ampel-Schwellen (Wochen)
                  vorlauf_gruen=kern.parameter_holen(session, "vorlauf_gruen_ab_wochen", "8"),
                  vorlauf_gelb=kern.parameter_holen(session, "vorlauf_gelb_ab_wochen", "4"),
                  standard_pl=kern.parameter_holen(session, "standard_projektleiter"),
                  standard_fp=kern.parameter_holen(session, "standard_feinplaner"),
                  standard_ep=kern.parameter_holen(session, "standard_elektroplaner"),
                  buchhaltung=kern.parameter_holen(session, "buchhaltung_benutzer"),
                  absender=kern.parameter_holen(session, "absender_postfach",
                                                mail_modul.ABSENDER_STANDARD),
                  gruende="\n".join(kern.storno_gruende(session)),
                  vorlage=kern.ordnervorlage(session),
                  mail_protokoll=kern.parameter_holen(session, "mail_protokoll"),
                  # v28 (PLAN_PROJ_V6 Phase 133/135): Wächter-Modus, Terminvorschläge
                  waechter_modus=kern.parameter_holen(session, "waechter_modus", "warnen"),
                  montage_dauer_tage_standard=kern.parameter_holen(
                      session, "montage_dauer_tage_standard", "5"),
                  vorschlag_vorlauf_wochen=kern.parameter_holen(
                      session, "vorschlag_vorlauf_wochen", "4"),
                  montage_startadresse=kern.parameter_holen(
                      session, "montage_startadresse",
                      "Arnold-Overbeck-Str. 63-65, 47139 Duisburg"),
                  vorschlag_outlook=kern.parameter_holen(session, "vorschlag_outlook", "aus"),
                  einstellungs_protokoll=kern.parameter_holen(
                      session, "einstellungs_protokoll", ""),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/projektierung-einstellungen")
def projektierung_einstellungen_speichern(
        request: Request, session: Session = Depends(get_session)):
    import json as json_modul
    from urllib.parse import quote_plus

    from app import projektierung as kern
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    # v15 (Phase 76): Galerie-Zusatzordner (Standardordner nicht löschbar)
    kern.parameter_setzen(session, "galerie_zusatzordner",
                          (form.get("galerie_zusatzordner") or "").strip()[:500])
    kern.parameter_setzen(session, "galerie_original_behalten",
                          "an" if form.get("galerie_original") == "on" else "aus")
    # v15 (Phase 78): Portal-URLs (BzA, SpotmyEnergy, Heizreport)
    # v26 (Phase 125): nur Schlüssel setzen, die das Formular mitschickt –
    # url_heizreport wird auf /parametrierung/heizreport gepflegt und würde
    # sonst beim Speichern dieser Seite geleert
    for schluessel in ("url_bza_portal", "url_spotmyenergy", "url_heizreport",
                       "url_gc_online", "collin_kundennummer",
                       "url_kfw_zuschussportal", "projekt_testadresse"):
        if schluessel in form:
            kern.parameter_setzen(session, schluessel,
                                  (form.get(schluessel) or "").strip()[:300])
    if form.get("ugl_lieferadresse") in ("ausfuehrung", "lager"):
        kern.parameter_setzen(session, "ugl_lieferadresse",
                              form.get("ugl_lieferadresse"))
    # V4 (Phase 93.2): Lieferantennummer + Standard-Lieferant
    kern.parameter_setzen(session, "collin_lieferantennummer",
                          (form.get("collin_lieferantennummer") or "").strip()[:10])
    if (form.get("stueckliste_standard_lieferant") or "").strip():
        kern.parameter_setzen(session, "stueckliste_standard_lieferant",
                              form.get("stueckliste_standard_lieferant").strip()[:60])
    # v26: Heizreport-Parameter werden unter /parametrierung/heizreport gepflegt
    kern.parameter_setzen(session, "lager_adresse",
                          (form.get("lager_adresse") or "").strip()[:500])
    if (form.get("bza_fachunternehmer") or "").strip():
        kern.parameter_setzen(session, "bza_fachunternehmer",
                              form.get("bza_fachunternehmer").strip()[:300])
    # v15 (Phase 81): Outlook-Kalender + Terminmail-Vorlage
    if form.get("outlook_kalender_modus") in ("postfach", "kategorien"):
        kern.parameter_setzen(session, "outlook_kalender_modus",
                              form.get("outlook_kalender_modus"))
    for schluessel, laenge in (("outlook_kalender_adresse", 200),
                               ("basis_url", 300),
                               ("terminmail_betreff", 300),
                               ("terminmail_vorbereitung", 500)):
        wert = (form.get(schluessel) or "").strip()
        if schluessel in form:
            kern.parameter_setzen(session, schluessel, wert[:laenge])
    # V4 (Phase 92): Vorlage Kundenmail „BzA“
    if form.get("bza_mail_dabei"):
        kern.parameter_setzen(session, "bza_mail_aktiv",
                              "an" if form.get("bza_mail_aktiv") == "on" else "aus")
    if (form.get("bza_mail_betreff") or "").strip():
        kern.parameter_setzen(session, "bza_mail_betreff",
                              form.get("bza_mail_betreff").strip()[:300])
    if (form.get("bza_mail_text") or "").strip():
        kern.parameter_setzen(session, "bza_mail_text",
                              form.get("bza_mail_text").strip()[:5000])
    if (form.get("terminmail_text") or "").strip():
        kern.parameter_setzen(session, "terminmail_text",
                              form.get("terminmail_text").strip()[:5000])
    # v28 (PLAN_PROJ_V6 Phase 133/135): Wächter-Modus (protokolliert) + Terminvorschläge
    if form.get("waechter_modus") in ("warnen", "sperren"):
        alt = kern.parameter_holen(session, "waechter_modus", "warnen")
        if alt != form.get("waechter_modus"):
            _proj_protokoll(session, kern, f"waechter_modus {alt} → {form.get('waechter_modus')}",
                            request.state.benutzer)
        kern.parameter_setzen(session, "waechter_modus", form.get("waechter_modus"))
    if form.get("vorschlag_outlook") in ("an", "aus"):
        kern.parameter_setzen(session, "vorschlag_outlook", form.get("vorschlag_outlook"))
    for schluessel, laenge in (("montage_dauer_tage_standard", 3),
                               ("vorschlag_vorlauf_wochen", 4)):
        wert = (form.get(schluessel) or "").strip().replace(",", ".")
        if wert and wert.replace(".", "", 1).isdigit():
            kern.parameter_setzen(session, schluessel, wert[:laenge])
    if "montage_startadresse" in form:
        kern.parameter_setzen(session, "montage_startadresse",
                              (form.get("montage_startadresse") or "").strip()[:300])
    if form.get("freigabe_modus") in ("admin", "pilot", "alle"):
        kern.parameter_setzen(session, "freigabe_modus", form.get("freigabe_modus"))
    # V3 (Phase 86): Pilotliste (nur wenn das Formular sie mitschickt)
    if form.get("pilot_dabei"):
        kern.parameter_setzen(session, "pilot_benutzer", ",".join(
            str(int(w)) for w in form.getlist("pilot_benutzer") if str(w).isdigit()))
    # V4 (Phase 90.3): Vorlauf-Schwellen (Wochen, Dezimal erlaubt)
    for schluessel in ("vorlauf_gruen_ab_wochen", "vorlauf_gelb_ab_wochen"):
        wert = (form.get(schluessel) or "").strip().replace(",", ".")
        try:
            if wert and float(wert) >= 0:
                kern.parameter_setzen(session, schluessel, wert)
        except ValueError:
            pass
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


# --- V4 (PLAN_PROJ_V4 Phase 93.2): Stücklisten-Pflege ------------------------------

def _stuecklisten_zurueck(meldung: str, anker: str = ""):
    from urllib.parse import quote_plus
    return RedirectResponse("/parametrierung/stuecklisten?meldung=" + quote_plus(meldung)
                            + (f"&pos={quote_plus(anker)}#editor" if anker else ""),
                            status_code=303)


# --- v19 (PLAN_V14 Phase 95): BzA-Ersteller ------------------------------------------

@router.get("/bza-ersteller")
def bza_ersteller_seite(request: Request, session: Session = Depends(get_session)):
    from app import bza_datenblatt
    from app.models import einstellung_holen
    return render(request, "konfiguration/bza_ersteller.html", aktiv="/parametrierung",
                  firma=bza_datenblatt.FIRMA,
                  kandidaten=bza_datenblatt.ersteller_kandidaten(session),
                  standard=einstellung_holen(session, "bza_ersteller_standard", ""),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/bza-ersteller")
def bza_ersteller_speichern(request: Request, session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app.models import einstellung_setzen
    form = anfrage.formular(request)
    wert = (form.get("standard") or "").strip()
    einstellung_setzen(session, "bza_ersteller_standard", wert if wert.isdigit() else "")
    session.commit()
    return RedirectResponse("/parametrierung/bza-ersteller?meldung="
                            + quote_plus("BzA-Ersteller gespeichert."), status_code=303)


# --- 30.09.2026: Kunden-Dubletten zusammenführen (Admin) ------------------------------

@router.get("/kunden-dubletten")
def kunden_dubletten_seite(request: Request, session: Session = Depends(get_session)):
    from app import kunden_dubletten
    from app.models import einstellung_holen
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    return render(request, "konfiguration/kunden_dubletten.html", aktiv="/parametrierung",
                  gruppen=kunden_dubletten.gruppen(session),
                  protokoll=einstellung_holen(session, kunden_dubletten.PROTOKOLL, ""),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/kunden-dubletten")
def kunden_dubletten_zusammenfuehren(request: Request,
                                           session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app import kunden_dubletten
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    try:
        haupt_id = int(form.get("haupt_id") or 0)
        dubletten = [int(x) for x in form.getlist("dublette_id") if str(x).isdigit()]
    except ValueError:
        haupt_id, dubletten = 0, []
    dubletten = [d for d in dubletten if d != haupt_id]
    if not haupt_id or not dubletten:
        return RedirectResponse("/parametrierung/kunden-dubletten?meldung=" + quote_plus(
            "Bitte einen Hauptdatensatz und mindestens eine Dublette wählen."), status_code=303)
    try:
        ergebnis = kunden_dubletten.zusammenfuehren(session, haupt_id, dubletten,
                                                    benutzer=request.state.benutzer)
    except ValueError as fehler:
        session.rollback()
        return RedirectResponse("/parametrierung/kunden-dubletten?meldung="
                                + quote_plus(str(fehler)), status_code=303)
    session.commit()
    return RedirectResponse("/parametrierung/kunden-dubletten?meldung=" + quote_plus(
        f"Zusammengeführt in #{ergebnis['haupt']}: "
        + ", ".join(f"#{i}" for i in ergebnis["entfernt"]) + " entfernt."), status_code=303)


# --- V3 (PLAN_PROJ_V3 Phase 86): Go-live-Checkliste ---------------------------------

def _golive_zurueck(meldung: str):
    from urllib.parse import quote_plus
    return RedirectResponse("/parametrierung/golive?meldung=" + quote_plus(meldung),
                            status_code=303)


@router.get("/golive")
def golive_seite(request: Request, session: Session = Depends(get_session)):
    from app import golive
    from app import projektierung as kern
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    punkte = golive.pruefen(session)
    return render(request, "konfiguration/golive.html", aktiv="/parametrierung",
                  punkte=punkte, freigabe_modus=kern.freigabe_modus(session),
                  pilot_anzahl=len(kern.pilot_benutzer_ids(session)),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/golive/haekchen")
def golive_haekchen(request: Request, session: Session = Depends(get_session)):
    from app import golive
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    name = form.get("name") or ""
    if name not in ("ugl_testdatei_bestaetigt", "golive_formulare_abgenommen"):
        return _golive_zurueck("Unbekannter Prüfpunkt.")
    golive.haekchen_setzen(session, name, form.get("an") == "on", request.state.benutzer)
    session.commit()
    return _golive_zurueck("Prüfpunkt gespeichert.")


@router.post("/golive/testmail")
def golive_testmail(request: Request, session: Session = Depends(get_session)):
    from app import golive
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    _ok, meldung = golive.testmail_senden(session, request.state.benutzer)
    session.commit()
    return _golive_zurueck(meldung)


# --- V3 (PLAN_PROJ_V3 Phase 85): Bestandsimport laufender Projekte ------------------

def _bestand_ordner():
    from app import config
    ordner = config.BACKUP_ORDNER / "bestandsimport"
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def _bestand_zurueck(meldung: str):
    from urllib.parse import quote_plus
    return RedirectResponse("/parametrierung/bestandsimport?meldung=" + quote_plus(meldung),
                            status_code=303)


@router.get("/bestandsimport")
def bestandsimport_seite(request: Request, session: Session = Depends(get_session)):
    from app.models import Bestandsimport, Benutzer
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    from app import import_preisliste
    importe = (session.query(Bestandsimport)
               .order_by(Bestandsimport.id.desc()).limit(30).all())
    return render(request, "konfiguration/bestandsimport.html", aktiv="/parametrierung",
                  importe=importe, vorschau=None,
                  benutzer_map={b.id: b for b in session.query(Benutzer)},
                  # v27 (Phase 128): Hinweis „Dauer etwa <n> s …“ vor dem Import
                  hinweis=import_preisliste.import_hinweis(session, "bestand"),
                  meldung=request.query_params.get("meldung", ""))


@router.get("/bestandsimport/vorlage.xlsx")
def bestandsimport_vorlage(request: Request):
    from fastapi.responses import Response

    from app import bestandsimport
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    return Response(
        content=bestandsimport.vorlage_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="bestandsimport_vorlage.xlsx"'})


@router.post("/bestandsimport/vorschau")
def bestandsimport_vorschau(request: Request, session: Session = Depends(get_session)):
    """Upload → Prüfung je Zeile; die Datei wird für den Import-Schritt
    zwischengespeichert (data/backups/bestandsimport/<kennung>.xlsx)."""
    from uuid import uuid4

    from app import bestandsimport
    from app.models import Benutzer
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    datei = form.get("datei")
    if datei is None or not getattr(datei, "filename", ""):
        return _bestand_zurueck("Bitte eine Excel-Datei (Vorlage) wählen.")
    inhalt = datei.file.read()
    zeilen, fehler = bestandsimport.einlesen(inhalt)
    if fehler:
        return _bestand_zurueck(fehler)
    if not zeilen:
        return _bestand_zurueck("Keine Datenzeilen gefunden (Beispielzeile wird ignoriert).")
    kennung = uuid4().hex
    (_bestand_ordner() / f"{kennung}.xlsx").write_bytes(inhalt)
    bestandsimport.pruefen(session, zeilen)
    from app import import_preisliste
    return render(request, "konfiguration/bestandsimport.html", aktiv="/parametrierung",
                  importe=[], vorschau=zeilen, kennung=kennung,
                  dateiname=datei.filename, spalten=bestandsimport.SPALTEN,
                  benutzer_map={b.id: b for b in session.query(Benutzer)},
                  # v27 (Phase 128): Hinweis + Bestätigungs-Häkchen am Import-Knopf
                  hinweis=import_preisliste.import_hinweis(session, "bestand"),
                  meldung="")


@router.post("/bestandsimport/ausfuehren")
def bestandsimport_ausfuehren(request: Request, session: Session = Depends(get_session)):
    import time

    from app import bestandsimport, import_preisliste
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    kennung = "".join(z for z in (form.get("kennung") or "") if z.isalnum())[:40]
    pfad = _bestand_ordner() / f"{kennung}.xlsx"
    if not kennung or not pfad.exists():
        return _bestand_zurueck("Vorschau abgelaufen – bitte die Datei erneut hochladen.")
    if form.get("abbrechen"):
        pfad.unlink(missing_ok=True)
        return _bestand_zurueck("Import abgebrochen – nichts geändert.")
    # v27 (PLAN_V17 Phase 128): Hinweis vor dem Start muss bestätigt sein; die
    # zwischengespeicherte Datei bleibt liegen – Vorschau erneut aufrufen
    if not import_preisliste.import_bestaetigt(form):
        return _bestand_zurueck(import_preisliste.HINWEIS_BESTAETIGEN
                                + " – bitte die Datei erneut hochladen und das Häkchen setzen.")
    start = time.perf_counter()
    zeilen, fehler = bestandsimport.einlesen(pfad.read_bytes())
    if fehler:
        return _bestand_zurueck(fehler)
    bestandsimport.pruefen(session, zeilen)
    imp = bestandsimport.importieren(session, zeilen,
                                     (form.get("dateiname") or pfad.name)[:200],
                                     benutzer=request.state.benutzer)
    session.commit()
    import_preisliste.import_dauer_merken(session, "bestand", start)
    return _bestand_zurueck(
        f"Import #{imp.id}: {imp.angelegt} angelegt, {imp.aktualisiert} aktualisiert, "
        f"{imp.uebersprungen} übersprungen (Fehlerzeilen).")


@router.post("/bestandsimport/{import_id}/rueckgaengig")
def bestandsimport_rueckgaengig(request: Request, import_id: int,
                                      session: Session = Depends(get_session)):
    from app import bestandsimport
    from app.models import Bestandsimport
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    imp = session.get(Bestandsimport, import_id)
    if imp is None or imp.rueckgaengig_am is not None:
        return _bestand_zurueck("Import nicht gefunden oder bereits rückgängig gemacht.")
    entfernt, behalten = bestandsimport.rueckgaengig(session, imp)
    session.commit()
    return _bestand_zurueck(
        f"Import #{imp.id} rückgängig: {entfernt} Gewerke entfernt"
        + (f", {len(behalten)} Zeilen bleiben (geändert oder nur aktualisiert)"
           if behalten else "") + ".")


@router.get("/stuecklisten")
def stuecklisten_seite(request: Request, session: Session = Depends(get_session)):
    """Stücklisten je Angebotsposition (Artikelstamm) – Excel bleibt Master,
    die Maske schreibt ins Blatt „Stücklisten“ zurück."""
    from app import projektierung as kern
    from app import projektierung_logik, stuecklisten
    ohne = request.query_params.get("ohne") == "1"
    suche = (request.query_params.get("suche") or "").strip()
    zugeordnet, gesamt = stuecklisten.fortschritt(session)
    quote = zugeordnet / gesamt if gesamt else 0.0
    pos = (request.query_params.get("pos") or "").strip()
    editor = next((p for p in stuecklisten.positionen(session) if p["pos_nr"] == pos), None)
    session.commit()
    return render(request, "konfiguration/stuecklisten.html", aktiv="/parametrierung",
                  positionen=stuecklisten.positionen(session, nur_ohne=ohne, suche=suche),
                  editor=editor,
                  ohne=ohne, suche=suche, zugeordnet=zugeordnet, gesamt=gesamt,
                  quote=quote, quote_ok=quote >= stuecklisten.GO_LIVE_QUOTE,
                  testdatei_bestaetigt=kern.parameter_holen(
                      session, "ugl_testdatei_bestaetigt", ""),
                  kundennummer=kern.parameter_holen(session, "collin_kundennummer", ""),
                  standard_lieferant=kern.parameter_holen(
                      session, "stueckliste_standard_lieferant", "Collin"),
                  stand=projektierung_logik.hole_logik(session).stand,
                  darf_admin=request.state.benutzer.rolle == "admin",
                  meldung=request.query_params.get("meldung", ""))


@router.get("/stuecklisten/export.csv")
def stuecklisten_export(session: Session = Depends(get_session)):
    from fastapi.responses import Response

    from app import stuecklisten
    return Response(content=stuecklisten.csv_export(session).encode("utf-8"),
                    media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             'attachment; filename="stuecklisten.csv"'})


@router.post("/stuecklisten/import")
def stuecklisten_import(request: Request, session: Session = Depends(get_session)):
    from app import stuecklisten
    form = anfrage.formular(request)
    datei = form.get("datei")
    if datei is None or not getattr(datei, "filename", ""):
        return _stuecklisten_zurueck("Bitte eine CSV-Datei wählen.")
    meldung = stuecklisten.csv_import(session, datei.file.read())
    session.commit()
    return _stuecklisten_zurueck(meldung)


@router.post("/stuecklisten/golive")
def stuecklisten_golive(request: Request, session: Session = Depends(get_session)):
    """Go-live-Prüfpunkt „Testdatei von Collin bestätigt“ (Häkchen, Admin)."""
    from datetime import datetime as dt

    from app import projektierung as kern
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    kern.parameter_setzen(session, "ugl_testdatei_bestaetigt",
                          f"{dt.now():%d.%m.%Y} · {request.state.benutzer.name}"
                          if form.get("bestaetigt") == "on" else "")
    session.commit()
    return _stuecklisten_zurueck("Go-live-Prüfpunkt gespeichert.")


@router.post("/stuecklisten/{pos_nr}")
def stueckliste_speichern(request: Request, pos_nr: str,
                                session: Session = Depends(get_session)):
    from app import stuecklisten
    form = anfrage.formular(request)
    zeilen = []
    for i in range(int(form.get("anzahl") or 0)):
        zeilen.append({feld: form.get(f"{feld}_{i}", "")
                       for feld in ("artnr", "menge", "bezeichnung", "lieferant", "einheit")})
    meldung = stuecklisten.position_speichern(session, pos_nr, zeilen)
    session.commit()
    return _stuecklisten_zurueck(meldung, pos_nr)


# --- v12 (Phase 74): Lead-Management – Steuerdatei ---------------------------------

@router.get("/lead-logik")
def lead_logik_seite(request: Request,
                           session: Session = Depends(get_session)):
    """Steuerdatei des Lead-Managements: Blätter als Tabellen, Versionsstand,
    Upload. Änderungen wirken auf neue Qualifizierungen; abgeschlossene
    behalten ihre Antworten."""
    from fastapi import HTTPException

    from app import leadmanagement, leadmanagement_logik
    if not leadmanagement.lead_modul_sichtbar(session, request.state.benutzer):
        raise HTTPException(status_code=404)   # Demo-Modus: unsichtbar
    logik = leadmanagement_logik.hole_logik()
    # v25 (PLAN_LEAD_V3 Phase 120): Blätter Qualifizierung/Scoring/Klassen werden
    # eingelesen, aber bei score_aktiv = aus nicht angewendet; Blatt Status mit
    # Hinweis „zwei Phasen dürfen dasselbe Label tragen“
    return render(request, "konfiguration/lead_logik.html",
                  aktiv="/parametrierung", logik=logik,
                  pfad=str(leadmanagement_logik.LOGIK_PFAD),
                  score_aktiv=leadmanagement.score_aktiv(session),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/lead-logik")
def lead_logik_upload(request: Request,
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
    form = anfrage.formular(request)
    datei = form.get("datei")
    if datei is None or not getattr(datei, "filename", ""):
        return RedirectResponse("/parametrierung/lead-logik?meldung="
                                + quote_plus("Bitte eine .xlsx-Datei wählen."),
                                status_code=303)
    inhalt = datei.file.read()
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
               f"{len(logik.kaskade)} Kaskaden-Stufen, "
               f"{len(logik.status_zeilen)} Status-Zeilen"
               + (f", {len(logik.warnungen)} Warnungen" if logik.warnungen else "")
               + (f". Backup: {sicherung.name}" if sicherung else "."))
    # v25 (Phase 120): Import-Hinweise – Score aus, Labels dürfen doppelt sein
    if not leadmanagement.score_aktiv(session):
        meldung += " Blätter Qualifizierung/Scoring/Klassen vorhanden, nicht aktiv (score_aktiv = aus)."
    labels = [z.label for z in logik.status_zeilen]
    if len(labels) != len(set(labels)):
        meldung += " Hinweis Blatt Status: zwei Phasen dürfen dasselbe Label tragen."
    return RedirectResponse("/parametrierung/lead-logik?meldung="
                            + quote_plus(meldung), status_code=303)


# --- v12 (Phase 75): Lead-Management – Quellen & Kampagnen, Parser, Demo-Daten -----

def _lead_gate(request: Request, session: Session):
    from fastapi import HTTPException

    from app import leadmanagement
    if not leadmanagement.lead_modul_sichtbar(session, request.state.benutzer):
        raise HTTPException(status_code=404)


@router.get("/lead-quellen")
def lead_quellen_seite(request: Request,
                             session: Session = Depends(get_session)):
    from datetime import datetime as dt, timedelta

    from app import leadmanagement as lead_kern
    from app.models import Kampagne, LeadQuelle, Vorgang
    _lead_gate(request, session)
    # v21 (Phase 87): Eingänge 7/30 Tage, zuletzt, Kosten je Lead (Kampagne)
    jetzt = dt.now()
    morgen = (jetzt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    q7 = lead_kern.eingaenge_zaehlen(session, morgen - timedelta(days=7), morgen, "quelle")
    q30 = lead_kern.eingaenge_zaehlen(session, morgen - timedelta(days=30), morgen, "quelle")
    k30 = lead_kern.eingaenge_zaehlen(session, morgen - timedelta(days=30), morgen, "kampagne")
    zuletzt: dict[int, dt] = {}
    for v in session.query(Vorgang).filter(Vorgang.eingang_am.isnot(None)):
        if v.quelle_id and (v.quelle_id not in zuletzt or v.eingang_am > zuletzt[v.quelle_id]):
            zuletzt[v.quelle_id] = v.eingang_am
    kampagnen = session.query(Kampagne).all()
    kpl: dict[int, int | None] = {}
    for k in kampagnen:
        if not k.budget_cent:
            kpl[k.id] = None
            continue
        von = k.von or dt(2000, 1, 1)
        bis = (k.bis + timedelta(days=1)) if k.bis else morgen
        anzahl = lead_kern.eingaenge_zaehlen(session, von, bis, "kampagne").get(k.id, 0)
        kpl[k.id] = round(k.budget_cent / anzahl) if anzahl else None
    kampagnen.sort(key=lambda k: (not k.aktiv, -k30.get(k.id, 0), k.name.lower()))
    quellen = session.query(LeadQuelle).all()
    quellen.sort(key=lambda q: (not q.aktiv, -q30.get(q.id, 0), q.name.lower()))
    return render(request, "konfiguration/lead_quellen.html",
                  aktiv="/parametrierung", quellen=quellen, kampagnen=kampagnen,
                  q7=q7, q30=q30, k30=k30, zuletzt=zuletzt, kpl=kpl,
                  gruppe=lead_kern.quelle_gruppe,
                  kanal_werte=lead_kern.kanal_werte(session),
                  profil_zum_kanal=lambda kanal: lead_kern.profil_zum_kanal(session, kanal),
                  # v25 (Rückfrage 6): Spalte Score-Bonus bei score_aktiv = aus kennzeichnen
                  score_aktiv=lead_kern.score_aktiv(session),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/lead-quellen")
def lead_quelle_speichern(request: Request,
                                session: Session = Depends(get_session)):
    import json as json_modul
    import re as re_modul
    import secrets
    from urllib.parse import quote_plus

    from app.models import Kampagne, LeadQuelle
    _lead_gate(request, session)
    form = anfrage.formular(request)
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
            # Bugfix 30.09.2026: „1.500,00“ warf ValueError (500)
            budget_cent=__import__("app.routers.artikel", fromlist=["x"]).preis_parsen(
                form.get("budget") or ""),
            utm_campaign=(form.get("utm_campaign") or "").strip()[:200],
            aktiv=form.get("aktiv") == "on")
        if kampagne_id.isdigit():
            kampagne = session.get(Kampagne, int(kampagne_id))
            if kampagne is not None:
                for feld, wert in werte.items():
                    if feld == "name" and not wert:
                        continue
                    setattr(kampagne, feld, wert)
                kampagne.auto_angelegt = False   # v21: einmal gespeichert = geprüft
        elif werte["name"]:
            session.add(Kampagne(erstellt_von=request.state.benutzer.id,
                                 **dict(werte, aktiv=True)))
        session.commit()
        return RedirectResponse("/parametrierung/lead-quellen?meldung=Gespeichert",
                                status_code=303)

    quelle_id = form.get("id") or ""
    schluessel = (form.get("key") or "").strip().lower()
    schluessel = re_modul.sub(r"[^a-z0-9_]", "_", schluessel)[:100]
    from app.models import INTERESSE_CODES
    sparten = [s for s in form.getlist("standard_sparten") if s in INTERESSE_CODES]   # v23: inkl. GW
    werte = dict(
        name=(form.get("name") or "").strip()[:200],
        typ=(form.get("typ") if form.get("typ") in
             ("website", "landingpage", "portal", "partner", "telefon",
              "empfehlung", "bestand", "veranstaltung", "monday") else "website"),   # v23: Info-Veranstaltung
        # v21 (Phase 87): Kanal als Dropdown; „Standard“ = kein eigener Kanal
        kanal=(None if (form.get("kanal") or "").strip() in ("", "Standard")
               else (form.get("kanal") or "").strip()[:100]),
        kosten_je_lead_cent=__import__("app.routers.artikel", fromlist=["x"]).preis_parsen(
            form.get("kosten") or ""),
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
            quelle.auto_angelegt = False     # v21: einmal gespeichert = geprüft
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
def lead_parser_seite(request: Request,
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
def lead_parser_speichern(request: Request,
                                session: Session = Depends(get_session)):
    import json as json_modul
    from urllib.parse import quote_plus

    from app import lead_parser
    from app.models import LeadQuelle, ParserRegel
    _lead_gate(request, session)
    form = anfrage.formular(request)

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
def lead_demo_seite(request: Request,
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
def lead_demo_aktion(request: Request,
                           session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app import leadmanagement
    _lead_gate(request, session)
    if request.state.benutzer.rolle != "admin":
        return RedirectResponse("/parametrierung", status_code=303)
    form = anfrage.formular(request)
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
def lead_routing_seite(request: Request,
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
def lead_routing_speichern(request: Request,
                                 session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app import leadmanagement as lead_kern
    from app import routing
    _lead_gate(request, session)
    form = anfrage.formular(request)
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
def lead_vorlagen_seite(request: Request,
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
def lead_vorlagen_speichern(request: Request,
                                  session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app import lead_mail
    from app.models import einstellung_setzen
    _lead_gate(request, session)
    form = anfrage.formular(request)
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
def lead_einstellungen(request: Request,
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
                  "firmen_adresse", "demo_badge_text", "lm_startseite",
                  "erwartungswert_WP", "erwartungswert_PV",
                  "erwartungswert_KL", "erwartungswert_WB",
                  "quote_neu", "quote_in_kontaktierung", "quote_qualifiziert",
                  "quote_terminiert", "quote_erfasst", "quote_angebot",
                  # v23 (Lead-Management V2, Phase 104/112)
                  "erwartungswert_GW", "versuche_max", "wv_meldet_sich_tage",
                  "rueckruf_telefon", "kanal_farben", "pflichtfelder",
                  "hv_ausschluss", "hv_standard_benutzer",
                  "ersatz_radius_stufen", "ersatz_alter_tage",
                  "info_wochentag", "info_woche", "info_uhrzeit", "info_ort",
                  "info_vorlauf_tage", "info_rollierend_monate", "puffer_min",
                  "max_termine_tag_start", "dashboard_horizont_tage",
                  "kanal_ad_regel", "vorab_dauer_min", "ersatz_min_treffer",
                  "termin_konflikt_modus", "vorschlag_raster_manuell_min",
                  # v25 (Lead-Management V3, Phase 120)
                  "score_aktiv", "ohne_schritt_tage",
                  # v29 (PLAN_LEAD_V4 Phasen 140–143)
                  "absender_lead_mails", "hv_gruppe_rene", "hv_gruppe_simon",
                  "hv_versandweg", "glocke_lead_arten", "routen_start",
                  "vorschlaege_anzahl"]
    werte = {name: lead_kern.parameter_holen(session, name)
             for name in schluessel}
    from app import lead_v2
    handelsvertreter = lead_v2.handelsvertreter_liste(session)
    # v29 (Phase 141/142): Glocken-Arten, offene Lead-Mails mit Fehler
    from app import lead_glocken
    from app.models import KommunikationLog
    glocke_arten = lead_glocken.erlaubte_arten(session)
    mail_fehler_anzahl = (session.query(KommunikationLog)
                          .filter(KommunikationLog.status == "fehler").count())
    vorschau = None
    if request.query_params.get("loeschvorschau") == "1":
        vorschau = lead_kern.loeschlauf(session, trocken=True)
    return render(request, "konfiguration/lead_einstellungen.html",
                  aktiv="/parametrierung", werte=werte,
                  handelsvertreter=handelsvertreter,
                  demo_anzahl=session.query(Vorgang)
                  .filter(Vorgang.demo.is_(True)).count(),
                  protokoll=lead_kern.parameter_holen(
                      session, "einstellungs_protokoll"),
                  loesch_protokoll=lead_kern.parameter_holen(
                      session, "loeschlauf_protokoll"),
                  loeschvorschau=vorschau,
                  glocke_arten=glocke_arten, glocke_alle=lead_glocken.ALLE_ARTEN,
                  glocke_namen=lead_glocken.ARTEN_NAMEN,
                  mail_fehler_anzahl=mail_fehler_anzahl,
                  umstellung=request.query_params.get("umstellung", ""),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/lead-einstellungen")
def lead_einstellungen_speichern(request: Request,
                                       session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from app import leadmanagement as lead_kern
    from app.models import Vorgang
    _lead_gate(request, session)
    benutzer = request.state.benutzer
    if benutzer.rolle != "admin":
        return RedirectResponse("/parametrierung", status_code=303)
    form = anfrage.formular(request)

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
                "demo_badge_text",
                # v23 (Lead-Management V2)
                "rueckruf_telefon", "kanal_farben", "pflichtfelder",
                "hv_ausschluss", "hv_standard_benutzer",
                "ersatz_radius_stufen", "info_uhrzeit", "info_ort",
                "kanal_ad_regel",
                # v29 (PLAN_LEAD_V4): Absender termin@, Routenplaner-Start
                "absender_lead_mails", "routen_start"]
    # v29 (Phase 140–142): HV-Gruppen (Mehrfachauswahl → Komma-Liste), Versandweg HV,
    # Glocken-Arten (Häkchen → Komma-Liste); Änderungen protokolliert
    for name in ("hv_gruppe_rene", "hv_gruppe_simon"):
        if form.get(name + "_dabei"):
            ids = ",".join(str(int(w)) for w in form.getlist(name) if str(w).isdigit())
            lead_kern.parameter_setzen(session, name, ids)
    if form.get("hv_versandweg") in ("offen", "smtp", "entwurf", "leads_im_namen"):
        alt = lead_kern.parameter_holen(session, "hv_versandweg", "offen")
        if alt != form.get("hv_versandweg"):
            lead_kern.einstellungs_protokoll(
                session, f"hv_versandweg {alt} → {form.get('hv_versandweg')}", benutzer)
        lead_kern.parameter_setzen(session, "hv_versandweg", form.get("hv_versandweg"))
    if form.get("glocke_dabei"):
        from app import lead_glocken
        arten = ",".join(a for a in lead_glocken.ALLE_ARTEN if a in form.getlist("glocke_lead_arten"))
        alt = lead_kern.parameter_holen(session, "glocke_lead_arten", "")
        if alt != arten:
            lead_kern.einstellungs_protokoll(session, f"glocke_lead_arten → {arten or '(keine)'}", benutzer)
        lead_kern.parameter_setzen(session, "glocke_lead_arten", arten)
    absender_neu = (form.get("absender_lead_mails") or "").strip()
    if "absender_lead_mails" in form:
        alt = lead_kern.parameter_holen(session, "absender_lead_mails", "")
        if alt != absender_neu:
            lead_kern.einstellungs_protokoll(session, f"absender_lead_mails {alt or '(leer)'} → {absender_neu or '(leer)'}", benutzer)
    if form.get("termin_konflikt_modus") in ("warnen", "sperren"):
        lead_kern.parameter_setzen(session, "termin_konflikt_modus",
                                   form.get("termin_konflikt_modus"))
    # v21 (Phase 88) / v23: Modul-Einstieg
    if form.get("lm_startseite") in ("", "uebersicht", "anrufliste",
                                     "dashboard", "hauptboard"):
        lead_kern.parameter_setzen(session, "lm_startseite", form.get("lm_startseite") or "")
    zahlen = ["sla_gruen_min", "sla_gelb_min", "vorschlag_horizont_tage",
              "vorschlag_raster_min", "loeschfrist_monate",
              "erwartungswert_WP", "erwartungswert_PV", "erwartungswert_KL",
              "erwartungswert_WB", "quote_neu", "quote_in_kontaktierung",
              "quote_qualifiziert", "quote_terminiert", "quote_erfasst",
              "quote_angebot",
              # v23 (Lead-Management V2)
              "erwartungswert_GW", "versuche_max", "wv_meldet_sich_tage",
              "ersatz_alter_tage", "info_wochentag", "info_woche",
              "info_vorlauf_tage", "info_rollierend_monate", "puffer_min",
              "max_termine_tag_start", "dashboard_horizont_tage",
              "vorab_dauer_min", "ersatz_min_treffer", "vorschlag_raster_manuell_min",
              # v25 (Phase 120): Dashboard „Ohne nächsten Schritt“
              "ohne_schritt_tage"]
    # v25 (Phase 120): zentraler Schalter Score/Qualifizierung (an|aus), protokolliert
    if form.get("score_aktiv") in ("an", "aus"):
        alt = lead_kern.parameter_holen(session, "score_aktiv", "aus")
        if form.get("score_aktiv") != alt:
            lead_kern.einstellungs_protokoll(
                session, f"score_aktiv {alt} → {form.get('score_aktiv')}", benutzer)
        lead_kern.parameter_setzen(session, "score_aktiv", form.get("score_aktiv"))
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


# --- v22 (PLAN_V15 Phase 103): Fehlerprotokoll ---------------------------------

def _fehlerprotokoll_gate(request: Request):
    """Nur Admin/Innendienst (die RollenMiddleware sperrt /parametrierung
    bereits für AD/Montage/Projektierung/Leadmanagement – doppelt hält besser)."""
    from app.auth import BUERO_ROLLEN
    benutzer = request.state.benutzer
    if benutzer is None or benutzer.rolle not in BUERO_ROLLEN:
        return RedirectResponse("/", status_code=303)
    return None


def _fehlerprotokoll_zurueck(form, meldung: str) -> RedirectResponse:
    """Zurück zur Liste – Filter (offen/pfad) aus dem Formular übernehmen."""
    from urllib.parse import urlencode
    parameter = {"meldung": meldung}
    if (form.get("offen") or "") == "1":
        parameter["offen"] = "1"
    if (form.get("pfad") or "").strip():
        parameter["pfad"] = form.get("pfad").strip()
    return RedirectResponse("/parametrierung/fehlerprotokoll?" + urlencode(parameter),
                            status_code=303)


@router.get("/fehlerprotokoll")
def fehlerprotokoll_seite(request: Request,
                                session: Session = Depends(get_session)):
    """Fehlerprotokoll: unbehandelte Ausnahmen mit Fehler-Nr., neueste zuerst
    (max. 200). Filter ?offen=1 (nur offene) und ?pfad= (Teilstring)."""
    from app import fehlerprotokoll as fp_modul
    from app.models import Fehlerprotokoll
    sperre = _fehlerprotokoll_gate(request)
    if sperre is not None:
        return sperre
    offen = request.query_params.get("offen") == "1"
    pfad = (request.query_params.get("pfad") or "").strip()
    abfrage = session.query(Fehlerprotokoll)
    if offen:
        abfrage = abfrage.filter(Fehlerprotokoll.erledigt.is_(False))
    if pfad:
        abfrage = abfrage.filter(Fehlerprotokoll.pfad.contains(pfad))
    eintraege = (abfrage.order_by(Fehlerprotokoll.zeit.desc(), Fehlerprotokoll.id.desc())
                 .limit(200).all())
    from app import db as db_modul
    return render(request, "konfiguration/fehlerprotokoll.html",
                  aktiv="/parametrierung", eintraege=eintraege, offen=offen, pfad=pfad,
                  # Hotfix 06.10.2026: Pool-Belegung oben auf der Seite
                  pool_status=db_modul.pool_status(),
                  pool_groesse=f"{db_modul.POOL_SIZE} + {db_modul.MAX_OVERFLOW} Überlauf, "
                               f"Timeout {db_modul.POOL_TIMEOUT} s",
                  offen_anzahl=(session.query(Fehlerprotokoll)
                                .filter(Fehlerprotokoll.erledigt.is_(False)).count()),
                  gesamt_anzahl=session.query(Fehlerprotokoll).count(),
                  log_pfad=str(fp_modul.log_pfad()),
                  darf_admin=request.state.benutzer.rolle == "admin",
                  meldung=request.query_params.get("meldung", ""))


@router.post("/fehlerprotokoll/{eintrag_id}/erledigt")
def fehlerprotokoll_erledigt(request: Request, eintrag_id: int,
                                   session: Session = Depends(get_session)):
    """Eintrag als erledigt markieren (Admin/Innendienst)."""
    from app.models import Fehlerprotokoll
    sperre = _fehlerprotokoll_gate(request)
    if sperre is not None:
        return sperre
    form = anfrage.formular(request)
    eintrag = session.get(Fehlerprotokoll, eintrag_id)
    if eintrag is None:
        return _fehlerprotokoll_zurueck(form, "Eintrag nicht gefunden.")
    eintrag.erledigt = True
    session.commit()
    return _fehlerprotokoll_zurueck(form, f"{eintrag.fehler_nr} als erledigt markiert.")


@router.post("/fehlerprotokoll/leeren")
def fehlerprotokoll_leeren(request: Request,
                                 session: Session = Depends(get_session)):
    """Alle erledigten Einträge löschen (nur Admin; Datei-Log bleibt)."""
    from app.models import Fehlerprotokoll
    sperre = _fehlerprotokoll_gate(request) or _nur_admin(request)
    if sperre is not None:
        return sperre
    form = anfrage.formular(request)
    anzahl = (session.query(Fehlerprotokoll)
              .filter(Fehlerprotokoll.erledigt.is_(True)).delete())
    session.commit()
    return _fehlerprotokoll_zurueck(form, f"{anzahl} erledigte Einträge gelöscht.")
