# Vorgangsakte (v10, Phase 59): Liste mit Suche + Detailakte je Vorgang –
# Kopf (Kunde, Ausführungsort, Kanal/Profil, Sparten-Chips, Vertriebler),
# Bereiche Erfassungen · Angebote · Mail-Verlauf · Verfolgung · Notizen-Chat.
# Außendienst sieht ausschließlich die eigenen Vorgänge (read-only + Notizen).

from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import notizen as notizen_modul   # v28 (Phase 136): gemeinsamer Notizen-Chat
from app import verfolgung as verfolgung_modul   # v32 (Phase 163): Nächster Schritt / Verfolgungsstatus
from app import vorgaenge as vorgaenge_modul
from app.db import get_session
from app.models import (Angebot, AngebotsMail, Benutzer, Erfassung, Kunde,
                        Lead, Vorgang, VorgangNotizGelesen, VorgangsNotiz)
from app.templating import render
from app import anfrage   # v27: Formular/JSON in def-Routen

router = APIRouter(prefix="/vorgaenge")


def _eigener(session: Session, vorgang: Vorgang, benutzer) -> bool:
    if benutzer is None:
        return False
    if benutzer.basisrolle in ("admin", "innendienst"):
        return True
    return vorgaenge_modul.gehoert_benutzer(session, vorgang, benutzer.id)


def _chips_fuer_vorgang(session: Session, vorgang: Vorgang,
                        erfassungen: list[Erfassung]) -> list[tuple[str, str]]:
    """Sparten-Chips: beim Lead-Vorgang wie in „Leads VOT“, sonst aus den
    tatsächlich vorhandenen Erfassungen (alle erfasst)."""
    from app.routers.leads import sparten_chips
    erfasst = {e.sparte or "WP" for e in erfassungen if e.status != "Entwurf"}
    if vorgang.lead_id:
        lead = session.get(Lead, vorgang.lead_id)
        if lead is not None:
            return sparten_chips(lead, erfasst)
    return [(s, "erfasst") for s in sorted(erfasst)]


@router.get("")
def liste(request: Request, q: str = "", verfolgung: str = "",
                session: Session = Depends(get_session)):
    """Vorgangsliste mit Suche (Kunde, Ort, Angebotsnummer); AD nur eigene.
    verfolgung=faellig zeigt rollenbezogen die fälligen Wiedervorlagen."""
    from datetime import datetime as dt
    benutzer = request.state.benutzer
    from app import leadmanagement
    vorgaenge = (leadmanagement.ohne_demo(session.query(Vorgang))
                 .order_by(Vorgang.angelegt_am.desc()).all())
    if verfolgung == "faellig":   # Phase 60: rollenbezogene Fälligkeit
        vorgaenge = [v for v in vorgaenge
                     if v.wiedervorlage_am and v.wiedervorlage_am <= dt.now()
                     and vorgaenge_modul.wiedervorlage_gehoert(session, v, benutzer)]
    elif verfolgung in ("heiss", "warm", "kalt"):
        vorgaenge = [v for v in vorgaenge if v.verfolgung_ampel == verfolgung]
    elif verfolgung in verfolgung_modul.STATUS:
        # v32 (PLAN_V19 Phase 163): Verfolgungsstufe (versendet … abgelehnt)
        vorgaenge = verfolgung_modul.filter_anwenden(vorgaenge, verfolgung)
    kunden = {k.id: k for k in session.query(Kunde)}
    leads = {l.id: l for l in session.query(Lead)}
    erf_je_vorgang: dict[int, list[Erfassung]] = {}
    for e in session.query(Erfassung).filter(Erfassung.vorgang_id.isnot(None)):
        erf_je_vorgang.setdefault(e.vorgang_id, []).append(e)
    ang_je_vorgang: dict[int, list[Angebot]] = {}
    for a in session.query(Angebot).filter(Angebot.vorgang_id.isnot(None)):
        ang_je_vorgang.setdefault(a.vorgang_id, []).append(a)
    if benutzer.basisrolle == "aussendienst":
        vorgaenge = [v for v in vorgaenge
                     if vorgaenge_modul.gehoert_benutzer(session, v, benutzer.id)]
    if q:
        suchwort = q.lower()
        def passt(v: Vorgang) -> bool:
            kunde = kunden.get(v.kunde_id)
            if kunde is not None and (suchwort in kunde.anzeige_name.lower()
                                      or suchwort in (kunde.ort or "").lower()
                                      or suchwort in (kunde.plz or "")):
                return True
            return any(suchwort in a.nummer.lower()
                       or suchwort in (a.taifun_nummer or "").lower()
                       for a in ang_je_vorgang.get(v.id, []))
        vorgaenge = [v for v in vorgaenge if passt(v)]
    chips = {v.id: _chips_fuer_vorgang(session, v, erf_je_vorgang.get(v.id, []))
             for v in vorgaenge}
    # „Neue Notizen“-Punkt (Phase 60): letzte Notiz nach dem Gelesen-Stand?
    gelesen = {g.vorgang_id: g.gelesen_bis for g in
               session.query(VorgangNotizGelesen)
               .filter(VorgangNotizGelesen.benutzer_id == benutzer.id)}
    neue_notizen: set[int] = set()
    for notiz in session.query(VorgangsNotiz):
        stand = gelesen.get(notiz.vorgang_id)
        if (stand is None or notiz.zeit > stand) and notiz.benutzer_id != benutzer.id:
            neue_notizen.add(notiz.vorgang_id)
    return render(request, "vorgaenge/liste.html", aktiv="/vorgaenge",
                  mobil=benutzer.basisrolle == "aussendienst",
                  vorgaenge=vorgaenge, kunden=kunden, leads=leads,
                  erf_je_vorgang=erf_je_vorgang, ang_je_vorgang=ang_je_vorgang,
                  chips=chips, neue_notizen=neue_notizen, q=q,
                  verfolgung=verfolgung, benutzer=benutzer,
                  meldung=request.query_params.get("meldung", ""))


@router.get("/zu-lead/{lead_id}")
def zu_lead(lead_id: int, session: Session = Depends(get_session)):
    lead = session.get(Lead, lead_id)
    if lead is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    vorgang = vorgaenge_modul.vorgang_fuer_lead(session, lead)
    session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang.id}", status_code=303)


@router.get("/zu-erfassung/{erfassung_id}")
def zu_erfassung(erfassung_id: int, session: Session = Depends(get_session)):
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    vorgang = vorgaenge_modul.vorgang_fuer_erfassung(session, erfassung)
    session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang.id}", status_code=303)


@router.get("/zu-angebot/{angebot_id}")
def zu_angebot(angebot_id: int, session: Session = Depends(get_session)):
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang.id}", status_code=303)


@router.get("/{vorgang_id}")
def akte(request: Request, vorgang_id: int,
               session: Session = Depends(get_session)):
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    if not _eigener(session, vorgang, benutzer):
        return RedirectResponse("/vorgaenge?meldung=" + quote_plus(
            "Kein Zugriff – der Vorgang gehört einem anderen Vertriebler."),
            status_code=303)
    kunde = session.get(Kunde, vorgang.kunde_id)
    lead = session.get(Lead, vorgang.lead_id) if vorgang.lead_id else None
    erfassungen = (session.query(Erfassung)
                   .filter(Erfassung.vorgang_id == vorgang.id)
                   .order_by(Erfassung.id).all())
    angebote = (session.query(Angebot)
                .filter(Angebot.vorgang_id == vorgang.id)
                .order_by(Angebot.nummer).all())
    mails = (session.query(AngebotsMail)
             .filter(AngebotsMail.angebot_id.in_([a.id for a in angebote] or [0]))
             .order_by(AngebotsMail.empfangen_am.desc().nullslast()).all())
    notizen = (session.query(VorgangsNotiz)
               .filter(VorgangsNotiz.vorgang_id == vorgang.id)
               .order_by(VorgangsNotiz.zeit, VorgangsNotiz.id).all())
    # v28 (PLAN_PROJ_V6 Phase 136): Kontext für das gemeinsame Makro notizen_chat
    # (Chat-Optik, Kennzeichen je Spur, Senden per fetch) – Rechte wie bisher
    # (ID/Admin überall, AD bei eigenen Vorgängen) über notizen.schreiben_erlaubt
    # v31 (PLAN_LEAD_V5 Phase 158): verlauf=True blendet Lead-/Projekt-Aktivitäten
    # neben dem Chat ein (Filter „nur Notizen“ / „alles“ in akte.html)
    notizen_ctx = notizen_modul.kontext(session, vorgang.id, benutzer, vorgang=vorgang,
                                        verlauf=True)
    # Gelesen-Stand fortschreiben (Phase 60: „Neue Notizen“-Punkt)
    marker = (session.query(VorgangNotizGelesen)
              .filter(VorgangNotizGelesen.vorgang_id == vorgang.id,
                      VorgangNotizGelesen.benutzer_id == benutzer.id).first())
    if marker is None:
        session.add(VorgangNotizGelesen(vorgang_id=vorgang.id,
                                        benutzer_id=benutzer.id))
    else:
        marker.gelesen_bis = datetime.now()
    session.commit()
    kanal = ((lead.vertriebskanal if lead else "")
             or (kunde.vertriebskanal if kunde else ""))
    from app import angebotsprofile
    profil = angebotsprofile.profil_fuer_kanal(session, kanal)
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    vertriebler_ids = ({lead.benutzer_id} if lead and lead.benutzer_id else set())
    vertriebler_ids |= {e.benutzer_id for e in erfassungen if e.benutzer_id}
    vertriebler_ids |= {a.vertriebler_id for a in angebote if a.vertriebler_id}
    erfassung_offen = next((e for e in erfassungen if e.status == "Entwurf"), None)
    aussendienst = [b for b in benutzer_map.values()
                    if b.basisrolle == "aussendienst" and b.aktiv]
    # v11 (Phase 66): Projektstand + „Angebot → Projekt" je angenommenem Angebot
    from app import projektierung as projektierung_modul
    from app.models import Gewerk as GewerkModell, Projekt as ProjektModell
    projekt_modul_ok = projektierung_modul.modul_sichtbar(session, benutzer)
    # v15 (Phase 76): Galerie am Vorgang
    from app import galerie as galerie_modul
    # 27.09.2026 (Andreas): eigene Galerie je Sparte - Reiter fuer jede
    # Sparte aus Gewerken, Kunden-Interessen oder vorhandenen Dateien
    from app.models import GalerieDatei as _GalerieDatei
    _datei_sparten = {z[0] for z in session.query(_GalerieDatei.sparte)
                      .filter(_GalerieDatei.vorgang_id == vorgang.id)
                      .distinct()}
    # v31 (PLAN_LEAD_V5 Phase 157): gemeinsame Sparten-Liste (inkl. GW/MS/WA/DMS);
    # Interessen = Vereinigung der Objekt-Interessen (objekte.vorgang_interessen)
    from app import objekte as objekte_modul
    from app import sparten as sparten_modul
    _interessen = set(objekte_modul.vorgang_interessen(session, vorgang.id)
                      or (kunde.interessen if kunde else []))
    galerie_sparten = [sp for sp in sparten_modul.SPARTEN
                       if sp in _interessen or sp in _datei_sparten]
    if not galerie_sparten:
        galerie_sparten = ["WP"]
    galerie_daten = {sp: galerie_modul.uebersicht(session, vorgang.id, sp)
                     for sp in galerie_sparten}
    galerie_ordner = {sp: galerie_modul.ordner_liste(session, sp)
                      for sp in galerie_sparten}
    galerie_darf_loeschen = galerie_modul.darf_loeschen(benutzer)
    vorgang_projekte = []
    if projekt_modul_ok:
        for projekt in (session.query(ProjektModell)
                        .filter(ProjektModell.vorgang_id == vorgang.id)
                        .order_by(ProjektModell.id)):
            projekt_gewerke = (session.query(GewerkModell)
                               .filter(GewerkModell.projekt_id == projekt.id)
                               .order_by(GewerkModell.id).all())
            vorgang_projekte.append({"projekt": projekt, "gewerke": projekt_gewerke})
    projekt_je_angebot = {}
    for a in angebote:
        if a.projekt_gewerk_id:
            gewerk = session.get(GewerkModell, a.projekt_gewerk_id)
            if gewerk is not None:
                projekt_je_angebot[a.id] = gewerk.projekt_id
    # v33 (PLAN_V20 Phase 168): Block „Termine“ – Service-Einsätze des Vorgangs (direkt
    # am Vorgang ohne Projekt oder an seinen Projekten) mit Badge „Service“, Anlass,
    # Status, Outlook-Stand; „Service-Einsatz planen“ für ID/Admin/Projektierung
    # (Rechte wie der Termin-Dialog, Modul sichtbar); Dialog-Kontext aus dem Kern
    service_termine: list = []
    service_planen_erlaubt = False
    td = None
    service_besetzung: dict = {}
    service_besetzung_ids: dict = {}
    outlook_stand: dict = {}
    if projekt_modul_ok:
        service_termine = projektierung_modul.service_termine(
            session, vorgang_id=vorgang.id,
            projekt_ids=[e["projekt"].id for e in vorgang_projekte])
        service_planen_erlaubt = projektierung_modul.termin_bearbeiten_erlaubt(session, benutzer)
        if service_planen_erlaubt:
            td = projektierung_modul.termin_dialog_kontext(session)
        service_besetzung_ids = projektierung_modul.besetzung_map(
            session, [t.id for t in service_termine])
        service_besetzung = {t.id: projektierung_modul.besetzung_namen(
            session, t.id, kurz=True, benutzer_map=benutzer_map) for t in service_termine}
        outlook_stand = {t.id: projektierung_modul.outlook_status_fuer(session, t)
                         for t in service_termine}
    service_ctx = {
        "service_termine": service_termine,
        "service_planen_erlaubt": service_planen_erlaubt,
        "td": td,
        "service_besetzung": service_besetzung,
        "service_besetzung_ids": service_besetzung_ids,
        "outlook_stand": outlook_stand,
        "outlook_makro_da": projektierung_modul.outlook_makro_vorhanden(),
        "service_anlass_namen": projektierung_modul.SERVICE_ANLASS_NAMEN,
        "service_gewerk_namen": projektierung_modul.SERVICE_GEWERK_NAMEN,
        "service_status_namen": projektierung_modul.SERVICE_STATUS_NAMEN,
        "projekte_map": {e["projekt"].id: e["projekt"] for e in vorgang_projekte},
        "termin_art_name": projektierung_modul.termin_art_name,
    }
    # Kombi-Versand (Phase 61): Wählbarkeit je Angebot + fachliche Hinweise
    from app import kombi_versand as kombi_modul
    kombi_info = {a.id: kombi_modul.waehlbar(a) for a in angebote}
    gewerke_hinweise = kombi_modul.gewerke_hinweise(session, vorgang, angebote)
    kombi_doppelt = kombi_modul.doppelte_artikel(
        [a for a in angebote if kombi_info[a.id][0]])
    # v12 (Phase 79): Lead-Kopfblock + Reiter, nur bei Modul-Sichtbarkeit
    lead_kontext = None
    lead_readonly = False
    try:
        from app import leadmanagement
        if leadmanagement.lead_modul_sichtbar(session, benutzer):
            lead_kontext = leadmanagement.akte_kontext(session, vorgang)
        elif leadmanagement.lead_ad_sicht(session, benutzer):
            # Phase 81: AD-Sicht read-only + No-Show/Verschieben (eigene Termine)
            lead_kontext = leadmanagement.akte_kontext(session, vorgang)
            lead_readonly = True
    except Exception:
        lead_kontext = None
    # v23 (Phase 110, A2/F7): To-Dos zum Vorgang – auch in der read-only-Akte des Außendienstes
    try:
        from app import lead_todos
        akte_todos = lead_todos.zeilen(session, lead_todos.fuer_vorgang(session, vorgang.id))
        todo_empfaenger = lead_todos.empfaenger_liste(session)
    except Exception:
        akte_todos, todo_empfaenger = [], []
    # v20 (Phase 98): Standard-Anschriften des Kunden (leer = Name + Ausführungsort)
    from app import anschriften as anschriften_modul
    anschrift_kontext = {}
    if kunde is not None:
        _re = anschriften_modul.standard_rechnung(kunde)
        _li = anschriften_modul.standard_lieferung(kunde)
        hinweise = []
        if any(getattr(kunde, f"rechnung_{f}", "") for f in anschriften_modul.FELDER):
            hinweise.append("Rechnung abweichend")
        if any(getattr(kunde, f"liefer_{f}", "") for f in anschriften_modul.FELDER):
            hinweise.append("Lieferung abweichend")
        anschrift_kontext = {"kunde_rechnung": _re, "kunde_liefer": _li,
                             "kunde_anschrift_hinweis": " · ".join(hinweise)}
    # v31 (PLAN_LEAD_V5 Phase 153): Erfassungen/Angebote je Objekt gruppieren
    # (Überschrift nur bei mehr als einem Objekt); Phase 154: Archiv-Banner der
    # Lead-Sicht mit „Wiederherstellen“ (ID/LM/Admin) – Akte sonst unverändert
    from app import vorgang_verlauf
    objekt_gruppen = vorgang_verlauf.objekt_gruppen(session, vorgang)
    archiviert_von_name = ""
    if vorgang.archiviert_von and vorgang.archiviert_von in benutzer_map:
        archiviert_von_name = benutzer_map[vorgang.archiviert_von].name
    archiv_wiederherstellen_erlaubt = _archiv_recht(benutzer)
    # v32 (PLAN_V19 Phase 163): Dialog „Nächster Schritt“ im Verfolgungs-Block (ID und AD) –
    # Variablen des Partials vorgaenge/_naechster_schritt.html (gruende, naechster_3wt, ziel)
    # v33 (PLAN_V20 Phase 176): + Einwand-Chips, Zähler, Kontext der Nachfass-Mail (benutzer =
    # Absender aus dem eigenen Postfach)
    verfolgung_ctx = verfolgung_modul.dialog_kontext(session, vorgang,
                                                     zurueck=f"/vorgaenge/{vorgang.id}",
                                                     benutzer=benutzer)
    naechster_schritt_erlaubt = _naechster_schritt_recht(session, vorgang, benutzer)
    return render(request, "vorgaenge/akte.html", aktiv="/vorgaenge",
                  **service_ctx,   # v33 (Phase 168): Block Termine / Service-Einsatz planen
                  gruende=verfolgung_ctx["gruende"], naechster_3wt=verfolgung_ctx["naechster_3wt"],
                  ziel=verfolgung_ctx["ziel"], heute_iso=verfolgung_ctx["heute_iso"],
                  einwaende=verfolgung_ctx.get("einwaende", []),
                  letzter_einwand=verfolgung_ctx.get("letzter_einwand", ""),
                  nachfass_versuche=verfolgung_ctx.get("nachfass_versuche", 0),
                  nachfass_mail=verfolgung_ctx.get("nachfass_mail"),
                  naechster_schritt_erlaubt=naechster_schritt_erlaubt,
                  akte_todos=akte_todos, todo_empfaenger=todo_empfaenger,   # v23 (Phase 110)
                  objekt_gruppen=objekt_gruppen, archiviert_von_name=archiviert_von_name,
                  archiv_wiederherstellen_erlaubt=archiv_wiederherstellen_erlaubt,
                  **anschrift_kontext,
                  mobil=benutzer.basisrolle == "aussendienst",
                  galerie_daten=galerie_daten, galerie_ordner=galerie_ordner,
                  galerie_sparten=galerie_sparten,
                  galerie_darf_loeschen=galerie_darf_loeschen,
                  steckbrief_daten=(projektierung_modul.steckbrief_daten(
                      session, [g.id for e in vorgang_projekte for g in e["gewerke"]])
                      if vorgang_projekte else {}),
                  steckbrief_felder=projektierung_modul.steckbrief_felder,
                  steckbrief_nur_lesen=benutzer.basisrolle == "aussendienst",
                  lead_kontext=lead_kontext, lead_readonly=lead_readonly,
                  lead_phasen_namen=__import__("app.models", fromlist=["x"]).LEAD_PHASEN_NAMEN,
                  vorgang=vorgang, kunde=kunde, lead=lead, kanal=kanal,
                  profil=profil, erfassungen=erfassungen, angebote=angebote,
                  mails=mails, notizen=notizen, notizen_ctx=notizen_ctx,
                  benutzer=benutzer, benutzer_map=benutzer_map,
                  chips=_chips_fuer_vorgang(session, vorgang, erfassungen),
                  vertriebler=[benutzer_map[i] for i in sorted(vertriebler_ids)
                               if i in benutzer_map],
                  erfassung_offen=erfassung_offen,
                  kombi_info=kombi_info, gewerke_hinweise=gewerke_hinweise,
                  kombi_doppelt=kombi_doppelt,
                  projekt_modul_ok=projekt_modul_ok,
                  vorgang_projekte=vorgang_projekte,
                  projekt_je_angebot=projekt_je_angebot,
                  aussendienst=sorted(aussendienst, key=lambda b: b.name),
                  heute=datetime.now(),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/{vorgang_id}/kombi-versand")
def kombi_versand(request: Request, vorgang_id: int,
                        session: Session = Depends(get_session)):
    """Kombi-Versand (v10, Phase 61): EINE Mail mit mehreren Angebots-PDFs.
    Nur Innendienst/Admin; Betreff/Text aus der Kombi-Vorlage; die Versand-
    Erkennung stellt später alle enthaltenen Tool-Angebote auf „Versendet"."""
    from app import (anhaenge as anhaenge_modul, graph_versand,
                     kombi_versand as kombi_modul)
    from app import logik as logik_modul
    from app import mail_vorlagen, signaturen
    from app.models import einstellung_holen
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None or benutzer.basisrolle not in ("admin", "innendienst"):
        return RedirectResponse("/vorgaenge", status_code=303)
    form = anfrage.formular(request)
    ids = [int(w) for w in form.getlist("angebot_ids") if str(w).isdigit()]
    angebote = [a for a in session.query(Angebot)
                .filter(Angebot.id.in_(ids or [0]),
                        Angebot.vorgang_id == vorgang.id)
                .order_by(Angebot.nummer)]
    ziel = f"/vorgaenge/{vorgang_id}?meldung="
    if len(angebote) < 2:
        return RedirectResponse(ziel + quote_plus(
            "Bitte mindestens zwei Angebote für den Kombi-Versand wählen "
            "(Einzelversand läuft weiter über das Angebot)."), status_code=303)
    for angebot in angebote:
        ok, grund = kombi_modul.waehlbar(angebot)
        if not ok:
            return RedirectResponse(ziel + quote_plus(
                f"{angebot.nummer}: {grund}"), status_code=303)
    if not graph_versand.konfiguriert():
        return RedirectResponse(ziel + quote_plus(
            "Microsoft Graph ist noch nicht eingerichtet "
            "(docs/graph-einrichtung.md)."), status_code=303)
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Vorgang und
    # Angebote sind geladen; msal kann das Token über das Netz erneuern)
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    # v33 (PLAN_V20 Phase 166): Modus anwendung braucht keine Anmeldung einer Person –
    # verbunden() prüft je Modus (Geheimnis + Verbindungstest bzw. angemeldete Person)
    if not graph_versand.verbunden(session):
        return RedirectResponse("/versand?meldung=" + quote_plus(
            graph_versand.nicht_verbunden_text(session)
            + " Danach den Kombi-Versand erneut starten."), status_code=303)
    kunde = session.get(Kunde, vorgang.kunde_id)
    # PDFs: je Angebot ein Anhang (Tool frisch erzeugt, TAIFUN aus dem Upload)
    pdfs = [kombi_modul.pdf_fuer(session, a) for a in angebote]
    # Broschüren über alle Tool-Angebote dedupliziert (je Dateiname einmal)
    logik, _ = logik_modul.hole_logik(session)
    broschueren: list = []
    fehlende: list[str] = []
    gesehen: set[str] = set()
    for angebot in angebote:
        if angebot.extern:
            continue
        for anhang in anhaenge_modul.fuer_angebot(
                logik, angebot, anhaenge_modul.profilname_fuer(session, angebot)):
            if anhang.datei in gesehen:
                continue
            gesehen.add(anhang.datei)
            if anhang.vorhanden:
                broschueren.append(Path(anhang.pfad))
            else:
                fehlende.append(anhang.datei)
    # Kombi-Vorlage + Signatur des angemeldeten ID-Mitarbeiters
    betreff, text = mail_vorlagen.kombi_mail_fuer_vorgang(
        session, angebote, kunde, benutzer.name)
    signatur_html, inline_bilder = signaturen.fuer_versand(benutzer.id)
    text += signatur_html
    # Versandregeln des Vorgangs-Profils (Enni-CC, SWD leer, Mehrfach-BCC)
    from app import angebotsprofile
    kanal = ""
    if vorgang.lead_id:
        lead = session.get(Lead, vorgang.lead_id)
        kanal = lead.vertriebskanal if lead else ""
    kanal = kanal or (kunde.vertriebskanal if kunde else "")
    profil = angebotsprofile.profil_fuer_kanal(session, kanal)
    absender = einstellung_holen(session, "mail_absender", "angebot@friondo.de")
    bcc = [a.strip() for a in einstellung_holen(session, "mail_bcc", "").split(",")
           if a.strip()]
    vertriebler = mail_vorlagen.vertriebler_fuer_angebot(session, angebote[0])
    cc = [vertriebler.email] if vertriebler and vertriebler.email else []
    if profil is not None and profil.versand_cc:
        cc += [a.strip() for a in profil.versand_cc.split(",")
               if a.strip() and a.strip() not in cc]
    empfaenger_leer = bool(profil is not None and profil.empfaenger_leer)
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (PDFs, Broschüren,
    # Texte, CC/BCC und Absender sind gelesen; Entwurf und Anhänge laufen über
    # mehrere Graph-Aufrufe)
    verbindung_freigeben(session)
    erfolg, meldung, weblink, conversation_id = graph_versand.entwurf_erstellen(
        kunde, angebote[0], pdfs[0], betreff, text,
        weitere_anhaenge=pdfs[1:] + broschueren,
        fehlende_anhaenge=fehlende, cc=cc, bcc=bcc, absender=absender,
        inline_bilder=inline_bilder, empfaenger_leer=empfaenger_leer)
    if erfolg:
        nummern = ", ".join(a.nummer for a in angebote)
        for angebot in angebote:
            if conversation_id:
                angebot.graph_conversation_id = conversation_id
            if not angebot.extern and angebot.status == "Entwurf":
                angebot.status = "Versand vorbereitet"
        vorgaenge_modul.notiz_anlegen(
            session, vorgang.id, benutzer,
            f"Kombi-Versand vorbereitet: {nummern} in einer Mail "
            f"({len(pdfs)} Angebots-PDFs, {len(broschueren)} Broschüren).",
            herkunft="Kombi-Versand")
        session.commit()
        # Warnung: dieselbe Artikelnummer in mehreren Tool-Angeboten voll berechnet
        doppelt = kombi_modul.doppelte_artikel(angebote)
        if doppelt:
            meldung += (f" ACHTUNG: Pos. {', '.join(doppelt)} sind in mehreren "
                        "Angeboten voll berechnet – bitte prüfen "
                        "(Alternativ-Kennzeichen?). TAIFUN-PDFs sind nicht prüfbar.")
        if empfaenger_leer:
            meldung += (" PFLICHT: Empfänger ist leer (SWD-Profil) – bitte den "
                        "SWD-Kontakt vor dem Senden in Outlook eintragen!")
        return RedirectResponse(ziel + quote_plus(
            f"Kombi-Entwurf für {nummern} erstellt. " + meldung), status_code=303)
    return RedirectResponse(ziel + quote_plus(meldung), status_code=303)


@router.post("/{vorgang_id}/anschriften")
def anschriften_standard(request: Request, vorgang_id: int,
                               session: Session = Depends(get_session)):
    """v20 (Phase 98): Standard-Rechnungs-/Lieferanschrift am Kunden –
    ID/Admin überall, Außendienst an eigenen Vorgängen (30.09.2026).
    Werte, die dem Kundennamen/Ausführungsort entsprechen, werden nicht
    gespeichert (leer = Standard)."""
    from app import anschriften
    from app.models import Kunde
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    if (vorgang is None or benutzer is None
            or benutzer.basisrolle not in ("admin", "innendienst", "aussendienst")
            or not _eigener(session, vorgang, benutzer)):
        return RedirectResponse("/vorgaenge", status_code=303)
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang.kunde_id else None
    if kunde is None:
        return RedirectResponse(f"/vorgaenge/{vorgang_id}", status_code=303)
    form = anfrage.formular(request)
    for praefix in ("rechnung", "liefer"):
        werte = anschriften.aus_formular(form, praefix)
        gleich = (not anschriften.adresse_abweichend(werte, kunde)
                  and not anschriften.name_abweichend(werte, kunde)
                  and not werte.get("zusatz"))
        anschriften.setzen(kunde, praefix, {} if gleich else werte)
    session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang_id}?meldung=" + quote_plus(
        "Standard-Anschriften gespeichert."), status_code=303)


def _archiv_recht(benutzer) -> bool:
    """v31 (Phase 154): Wiederherstellen aus der Vorgangsakte – Innendienst,
    Leadmanagement (Haupt- oder Zusatzrolle) und Admin."""
    if benutzer is None:
        return False
    if benutzer.basisrolle in ("admin", "innendienst", "leadmanagement"):
        return True
    hat = getattr(benutzer, "hat_rolle", None)
    return bool(hat and hat("leadmanagement"))


def archiv_wiederherstellen_ausfuehren(session: Session, vorgang: Vorgang,
                                       benutzer) -> tuple[bool, str]:
    """v31 (PLAN_LEAD_V5 Phase 154): Vertrag mit Agent B – lead_archiv.wiederherstellen
    (Aktivität, Kennzeichen zurücksetzen); solange das Modul fehlt, wird das
    Kennzeichen hier zurückgesetzt und eine System-Aktivität geschrieben."""
    try:
        from app import lead_archiv
    except ImportError:
        lead_archiv = None
    if lead_archiv is not None and hasattr(lead_archiv, "wiederherstellen"):
        ergebnis = lead_archiv.wiederherstellen(session, vorgang, benutzer)
        if isinstance(ergebnis, tuple):
            return bool(ergebnis[0]), str(ergebnis[1] if len(ergebnis) > 1 else "")
        return (ergebnis is None or bool(ergebnis)), ""
    from app.models import LeadAktivitaet
    vorgang.archiviert_am = None
    vorgang.archiviert_von = None
    session.add(LeadAktivitaet(
        vorgang_id=vorgang.id, typ="system",
        text="Aus dem Lead-Archiv wiederhergestellt (Vorgangsakte)",
        benutzer_id=getattr(benutzer, "id", None), erstellt_von=getattr(benutzer, "id", None)))
    session.flush()
    return True, ""


@router.post("/{vorgang_id}/archiv-wiederherstellen")
def archiv_wiederherstellen(request: Request, vorgang_id: int,
                            session: Session = Depends(get_session)):
    """v31 (PLAN_LEAD_V5 Phase 154): Knopf „Wiederherstellen“ im Archiv-Banner der
    Vorgangsakte (Archivieren ist eine Lead-Sicht – Angebotstool/Projektierung
    zeigen den Vorgang ohnehin). Läuft über das _speichern-Muster (Rollback + eine
    Wiederholung bei „database is locked“)."""
    from app.routers.angebote import _speichern
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    ziel = f"/vorgaenge/{vorgang_id}?meldung="
    if not _archiv_recht(benutzer):
        return RedirectResponse(ziel + quote_plus(
            "Wiederherstellen nur für Innendienst, Leadmanagement und Admin."), status_code=303)
    if not vorgang.archiviert_am:
        return RedirectResponse(ziel + quote_plus("Der Vorgang ist nicht archiviert."),
                                status_code=303)
    ergebnis: dict = {}

    def aktion():
        v = session.get(Vorgang, vorgang_id)
        ok, grund = archiv_wiederherstellen_ausfuehren(session, v, benutzer)
        ergebnis.update(ok=ok, grund=grund)

    _speichern(session, aktion)
    if ergebnis.get("ok"):
        return RedirectResponse(ziel + quote_plus(
            "Vorgang im Lead-Management wiederhergestellt."), status_code=303)
    return RedirectResponse(ziel + quote_plus(
        "Wiederherstellen nicht möglich: " + (ergebnis.get("grund") or "unbekannter Grund")),
        status_code=303)


@router.post("/{vorgang_id}/verfolgung")
def verfolgung(request: Request, vorgang_id: int,
                     session: Session = Depends(get_session)):
    """Phase 60: Verfolgung des Vorgangs aus der Akte setzen (ID überall,
    AD an eigenen Vorgängen; den Verantwortlichen ändert nur der ID)."""
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None or not _eigener(session, vorgang, benutzer):
        return RedirectResponse("/vorgaenge", status_code=303)
    form = anfrage.formular(request)
    verantwortlicher_id = None
    if benutzer.basisrolle in ("admin", "innendienst"):
        try:
            verantwortlicher_id = int(form.get("wv_verantwortlicher") or 0) or None
        except ValueError:
            verantwortlicher_id = None
    vorgaenge_modul.verfolgung_setzen(
        session, vorgang, benutzer,
        form.get("verfolgung_ampel") or "", form.get("wiedervorlage_am") or "",
        notiz=form.get("notiz") or "", verantwortlicher_id=verantwortlicher_id)
    session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang_id}?meldung=" + quote_plus(
        "Verfolgung aktualisiert."), status_code=303)


def _json_gewuenscht(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "")


def _naechster_schritt_recht(session: Session, vorgang: Vorgang, benutzer) -> bool:
    """v32 (PLAN_V19 Phase 163): Innendienst/Admin überall, Außendienst nur am eigenen
    Vorgang (vorgaenge.gehoert_benutzer); andere Rollen nicht."""
    if benutzer is None or vorgang is None:
        return False
    if benutzer.basisrolle in ("admin", "innendienst"):
        return True
    if benutzer.basisrolle == "aussendienst":
        return vorgaenge_modul.gehoert_benutzer(session, vorgang, benutzer.id)
    return False


def _rueckweg(zurueck: str, vorgang_id: int, meldung: str) -> str:
    ziel = (zurueck or "").strip()
    if not ziel.startswith("/") or ziel.startswith("//"):
        ziel = f"/vorgaenge/{vorgang_id}"
    return ziel + ("&" if "?" in ziel else "?") + "meldung=" + quote_plus(meldung)


@router.post("/{vorgang_id}/naechster-schritt")
def naechster_schritt(request: Request, vorgang_id: int,
                      session: Session = Depends(get_session)):
    """v32 (PLAN_V19 Phase 163): Dialog „Nächster Schritt“ nach dem Anruf. Felder:
    `schritt` ∈ abgelehnt | bestellung | nochmal (| rueckgaengig + `token`), `grund_id`
    (+ `freitext` bei Pflicht-Freitext, sonst 400), `wann` ∈ 3wt | datum (+ `datum`
    TT.MM.JJJJ bzw. JJJJ-MM-TT), `notiz` (Chat-Eintrag vor der System-Aktivität),
    `zurueck`. JSON bei Accept: application/json ({"ok", "meldung", "status",
    "wiedervorlage_am", …}), sonst Redirect auf `zurueck` (Standard: Akte). Rechte: AD nur
    eigener Vorgang → sonst 403, ID/Admin überall. Läuft über das _speichern-Muster
    (mehrere Zeilen: Angebote, Erfassungen, Notizen, Glocken; Rollback + eine
    Wiederholung bei „database is locked“)."""
    from fastapi.responses import JSONResponse

    from app.routers.angebote import _speichern
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    json_antwort = _json_gewuenscht(request)

    def antwort(ok: bool, meldung: str, daten: dict | None = None, status_code: int = 200,
                zurueck: str = ""):
        if json_antwort:
            inhalt = {"ok": ok, "meldung": meldung}
            inhalt.update(daten or {})
            return JSONResponse(inhalt, status_code=status_code)
        return RedirectResponse(_rueckweg(zurueck, vorgang_id, meldung), status_code=303)

    if vorgang is None:
        return antwort(False, "Vorgang nicht gefunden.", status_code=404)
    if not _naechster_schritt_recht(session, vorgang, benutzer):
        return antwort(False, "Kein Zugriff – der Vorgang gehört einem anderen Vertriebler.",
                       status_code=403)
    form = anfrage.formular(request)
    schritt = (form.get("schritt") or "").strip()
    zurueck = form.get("zurueck") or ""
    ergebnis: dict = {}

    def aktion():
        v = session.get(Vorgang, vorgang_id)
        if schritt == "rueckgaengig":
            ok, meldung, daten = verfolgung_modul.rueckgaengig(
                session, v, form.get("token") or "", benutzer)
        else:
            ok, meldung, daten = verfolgung_modul.naechster_schritt(
                session, v, schritt, benutzer,
                grund_id=form.get("grund_id"), freitext=form.get("freitext") or "",
                wann=form.get("wann") or "", datum=form.get("datum") or "",
                notiz=form.get("notiz") or "",
                einwand_id=form.get("einwand_id") or "")   # v33 (Phase 176): Einwand-Chip
        if not ok:
            session.rollback()
        ergebnis.update(ok=ok, meldung=meldung, daten=daten)

    _speichern(session, aktion)
    if not ergebnis.get("ok"):
        return antwort(False, ergebnis.get("meldung") or "Nicht gespeichert.",
                       status_code=400, zurueck=zurueck)
    return antwort(True, ergebnis["meldung"], ergebnis.get("daten"), zurueck=zurueck)


# --- v33 (PLAN_V20 Phase 176, Agent N): Nachfass-Mail aus dem eigenen Postfach ----------

@router.get("/{vorgang_id}/nachfass-mail/vorschau")
def nachfass_mail_vorschau(request: Request, vorgang_id: int, vorlage: str = "1",
                           session: Session = Depends(get_session)):
    """Vorschau der Nachfass-Mail (JSON): betreff, html (Signatur-Bilder eingebettet),
    text, empfaenger, absender, fehlende[]. Rechte wie „Nächster Schritt“ (AD nur eigener
    Vorgang → 403). Kein Netzaufruf."""
    from fastapi.responses import JSONResponse

    from app import nachfassen
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        return JSONResponse({"ok": False, "meldung": "Vorgang nicht gefunden."}, status_code=404)
    if not _naechster_schritt_recht(session, vorgang, benutzer):
        return JSONResponse({"ok": False, "meldung": "Kein Zugriff – der Vorgang gehört einem "
                                                    "anderen Vertriebler."}, status_code=403)
    daten = nachfassen.nachfass_mail_rendern(session, vorgang, benutzer, vorlage)
    kontext = nachfassen.nachfass_mail_kontext(session, vorgang, benutzer)
    return JSONResponse({
        "ok": True, "vorlage": daten["vorlage_nr"], "vorlage_name": daten["vorlage_name"],
        "betreff": daten["betreff"], "html": daten["html_vorschau"], "text": daten["text"],
        "empfaenger": kontext["empfaenger"], "absender": kontext["absender"],
        "erlaubt": kontext["erlaubt"], "hinweis": kontext["hinweis"],
        "fehlende": daten["fehlende"]})


@router.post("/{vorgang_id}/nachfass-mail")
def nachfass_mail(request: Request, vorgang_id: int,
                  session: Session = Depends(get_session)):
    """Nachfass-Mail senden: Felder `vorlage` (1|2), `pdf` (1 = Angebots-PDF anhängen),
    `zurueck`. Versand aus dem Postfach des angemeldeten Benutzers über
    graph_versand.mail_senden_als (nur Modus anwendung – sonst 409 mit Hinweis); AD nur
    eigener Vorgang (403). JSON bei Accept: application/json, sonst Redirect mit Meldung.
    nachfassen.nachfass_mail_senden gibt die Sitzung vor dem Graph-Aufruf frei (v27) und
    schreibt danach Mail-Verlauf + Notiz; Commit über das _speichern-Muster."""
    from fastapi.responses import JSONResponse

    from app import nachfassen
    from app.routers.angebote import _speichern
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    json_antwort = _json_gewuenscht(request)

    def antwort(ok: bool, meldung: str, daten: dict | None = None, status_code: int = 200,
                zurueck: str = ""):
        if json_antwort:
            inhalt = {"ok": ok, "meldung": meldung}
            inhalt.update({k: v for k, v in (daten or {}).items() if k != "status_code"})
            return JSONResponse(inhalt, status_code=status_code)
        return RedirectResponse(_rueckweg(zurueck, vorgang_id, meldung), status_code=303)

    if vorgang is None:
        return antwort(False, "Vorgang nicht gefunden.", status_code=404)
    if not _naechster_schritt_recht(session, vorgang, benutzer):
        return antwort(False, "Kein Zugriff – der Vorgang gehört einem anderen Vertriebler.",
                       status_code=403)
    form = anfrage.formular(request)
    zurueck = form.get("zurueck") or ""
    vorlage = form.get("vorlage") or "1"
    pdf_anhaengen = (form.get("pdf") or "") in ("1", "on", "true")
    # Schritt 1 (Sitzung): prüfen, rendern, Signatur-Bilder und PDF lesen
    ok, meldung, paket = nachfassen.nachfass_mail_vorbereiten(session, vorgang, benutzer,
                                                              vorlage, pdf_anhaengen)
    if not ok:
        return antwort(False, meldung, paket, status_code=int(paket.get("status_code") or 400),
                       zurueck=zurueck)
    # Schritt 2 (Netz): Verbindung freigeben (v27), dann Graph – außerhalb von _speichern,
    # damit eine Wiederholung wegen Schreibsperre die Mail nie ein zweites Mal sendet
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    gesendet, fehler, conversation_id = nachfassen.nachfass_mail_absenden(paket)
    if not gesendet:
        return antwort(False, f"Nachfass-Mail nicht gesendet: {fehler}", status_code=502,
                       zurueck=zurueck)
    # Schritt 3 (Sitzung): Mail-Verlauf + Notiz, Commit über das _speichern-Muster
    ergebnis: dict = {}

    def aktion():
        meldung_ok, daten = nachfassen.nachfass_mail_verbuchen(session, paket, conversation_id)
        ergebnis.update(meldung=meldung_ok, daten=daten)

    _speichern(session, aktion)
    return antwort(True, ergebnis["meldung"], ergebnis.get("daten"), zurueck=zurueck)


@router.post("/{vorgang_id}/notiz")
def notiz(request: Request, vorgang_id: int,
                session: Session = Depends(get_session)):
    """Notizen-Chat: append-only – jeder Eintrag mit Autor + Zeitstempel,
    kein Bearbeiten/Löschen.
    v28 (PLAN_PROJ_V6 Phase 136): gemeinsame Schreibroute für Vorgangsakte,
    Projektakte-Makro und Kundenkartei. Rechte über notizen.schreiben_erlaubt
    (ID/Admin überall, AD bei eigenen Vorgängen, Projektierung/Leadmanagement
    mit Zugriff, Hauptrolle Montage nur lesen – die Middleware leitet sie
    ohnehin nach /montage um). Bei `Accept: application/json` antwortet die
    Route mit {"ok": true, "eintrag": {...}} (Format laut Makro) bzw. 403/400
    mit {"ok": false, "meldung"}; sonst Redirect in die Akte (#notizen).
    Optionales Feld `herkunft` (projektierung | vertrieb | lead | montage) setzt
    das Kennzeichen, sonst folgt es der Hauptrolle des Schreibers."""
    from fastapi.responses import JSONResponse
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    json_antwort = _json_gewuenscht(request)
    if vorgang is None:
        if json_antwort:
            return JSONResponse({"ok": False, "meldung": "Vorgang nicht gefunden."},
                                status_code=404)
        return RedirectResponse("/vorgaenge", status_code=303)
    if not notizen_modul.schreiben_erlaubt(session, vorgang, benutzer):
        if json_antwort:
            return JSONResponse({"ok": False, "meldung": "Keine Berechtigung – Notizen "
                                 "sind für diese Rolle nur lesbar."}, status_code=403)
        return RedirectResponse("/vorgaenge", status_code=303)
    form = anfrage.formular(request)
    text = (form.get("text") or "").strip()
    if not text:
        if json_antwort:
            return JSONResponse({"ok": False, "meldung": "Bitte einen Text eingeben."},
                                status_code=400)
        return RedirectResponse(f"/vorgaenge/{vorgang_id}#notizen", status_code=303)
    eintrag = notizen_modul.notiz_anlegen(
        session, vorgang.id, benutzer, text,
        herkunft=notizen_modul.herkunft_fuer(benutzer, form.get("herkunft") or ""))
    # der eigene Eintrag gilt sofort als gelesen
    marker = (session.query(VorgangNotizGelesen)
              .filter(VorgangNotizGelesen.vorgang_id == vorgang.id,
                      VorgangNotizGelesen.benutzer_id == benutzer.id).first())
    if marker is not None:
        marker.gelesen_bis = datetime.now()
    session.commit()
    if json_antwort:
        return JSONResponse({"ok": True, "eintrag": notizen_modul.eintrag_json(eintrag)})
    ziel = form.get("zurueck") or f"/vorgaenge/{vorgang_id}#notizen"
    if not ziel.startswith("/") or ziel.startswith("//"):
        ziel = f"/vorgaenge/{vorgang_id}#notizen"
    return RedirectResponse(ziel, status_code=303)


# --- Galerie am Vorgang (v15, Phase 76) -------------------------------------

@router.post("/{vorgang_id}/galerie/upload")
def galerie_upload(request: Request, vorgang_id: int,
                         session: Session = Depends(get_session)):
    """Upload in einen Galerie-Ordner (mehrere Dateien, mobil per Kamera);
    Vertrieb in eigenen Vorgängen auch ohne Auftrag."""
    from app import galerie as galerie_modul
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    if not galerie_modul.darf_hochladen(session, vorgang, benutzer):
        return RedirectResponse(f"/vorgaenge/{vorgang_id}?meldung="
                                + quote_plus("Kein Upload-Recht für diesen Vorgang."),
                                status_code=303)
    # v33 (PLAN_V20 Phase 172, Befund 15.10.2026): der Request-Body (Upload) ist Netz-I/O – die
    # Schreibsitzung darf die SQLite-Schreibsperre nicht während der Übertragung halten
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    form = anfrage.formular(request)
    ordner = form.get("ordner") or "Allgemein"
    sparte = form.get("sparte") or "WP"
    bemerkung = form.get("bemerkung") or ""
    # 27.09.2026 (Andreas): Foto-Sammelbox schickt je Datei einen eigenen
    # Zielordner (datei_ordner parallel zur Dateireihenfolge)
    je_datei_ordner = form.getlist("datei_ordner")
    anzahl = 0
    ordner_benutzt: set[str] = set()
    for nr, datei in enumerate(form.getlist("dateien")):
        if getattr(datei, "filename", ""):
            inhalt = datei.file   # v27 (Phase 128): wird in galerie.speichern gestreamt
            ziel_ordner = (je_datei_ordner[nr]
                           if nr < len(je_datei_ordner)
                           and je_datei_ordner[nr] else ordner)
            if galerie_modul.speichern(session, vorgang_id, ziel_ordner,
                                       datei.filename, inhalt,
                                       benutzer=benutzer, bemerkung=bemerkung,
                                       sparte=sparte):
                anzahl += 1
                ordner_benutzt.add(ziel_ordner)
    session.commit()
    ziel = form.get("zurueck") or f"/vorgaenge/{vorgang_id}"
    trenner = "&" if "?" in ziel else "?"
    return RedirectResponse(ziel + trenner + "meldung=" + quote_plus(
        f"{anzahl} Datei(en) abgelegt ({', '.join(sorted(ordner_benutzt)) or ordner}).")
        + "#galerie", status_code=303)


@router.get("/galerie/datei/{datei_id}")
def galerie_datei(request: Request, datei_id: int,
                        session: Session = Depends(get_session)):
    from fastapi.responses import FileResponse

    from app import config as config_modul
    from app import galerie as galerie_modul
    from app.models import GalerieDatei
    datei = session.get(GalerieDatei, datei_id)
    if datei is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    vorgang = session.get(Vorgang, datei.vorgang_id)
    if not galerie_modul.darf_hochladen(session, vorgang, request.state.benutzer):
        return RedirectResponse("/vorgaenge", status_code=303)
    pfad = config_modul.DATA_ORDNER / datei.pfad
    if not pfad.exists():
        return RedirectResponse(f"/vorgaenge/{datei.vorgang_id}", status_code=303)
    # v28 (PLAN_PROJ_V6 Phase 136): Befund „Sofort-Download“ – FileResponse mit
    # filename= liefert Content-Disposition: attachment; jeder Klick, der nicht
    # von der Lightbox abgefangen wurde (Seiten ohne galerie_fuss(), Strg-Klick,
    # Handy-Browser mit target=_blank), lud die Datei herunter. Bilder (und PDFs
    # [ANNAHME: „PDF ansehen“ im Formular) kommen jetzt `inline`; der Download
    # läuft nur noch über den Knopf „Herunterladen“ (?download=1 → attachment).
    herunterladen = (request.query_params.get("download") or "") in ("1", "ja", "true")
    disposition = ("attachment" if herunterladen
                   or not galerie_modul.inline_anzeige(datei.dateiname) else "inline")
    return FileResponse(str(pfad), filename=datei.dateiname,
                        content_disposition_type=disposition)


@router.post("/galerie/datei/{datei_id}/verschieben")
def galerie_verschieben(request: Request, datei_id: int,
                              session: Session = Depends(get_session)):
    from app import galerie as galerie_modul
    from app.models import GalerieDatei
    datei = session.get(GalerieDatei, datei_id)
    if datei is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    vorgang = session.get(Vorgang, datei.vorgang_id)
    benutzer = request.state.benutzer
    if not galerie_modul.darf_hochladen(session, vorgang, benutzer):
        return RedirectResponse("/vorgaenge", status_code=303)
    form = anfrage.formular(request)
    if galerie_modul.verschieben(session, datei, form.get("ordner") or ""):
        session.commit()
    return RedirectResponse(f"/vorgaenge/{datei.vorgang_id}#galerie",
                            status_code=303)


@router.post("/galerie/datei/{datei_id}/loeschen")
def galerie_loeschen(request: Request, datei_id: int,
                           session: Session = Depends(get_session)):
    """Löschen nur Innendienst/Projektierung/Admin – protokolliert im Chat."""
    from app import galerie as galerie_modul
    from app import vorgaenge as vorgaenge_modul
    from app.models import GalerieDatei
    benutzer = request.state.benutzer
    datei = session.get(GalerieDatei, datei_id)
    if datei is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    vorgang_id = datei.vorgang_id
    if not galerie_modul.darf_loeschen(benutzer):
        return RedirectResponse(f"/vorgaenge/{vorgang_id}?meldung="
                                + quote_plus("Löschen nur für Innendienst/"
                                             "Projektierung/Admin."),
                                status_code=303)
    name, ordner = datei.dateiname, datei.ordner
    galerie_modul.loeschen(session, datei)
    vorgaenge_modul.notiz_anlegen(
        session, vorgang_id, benutzer,
        f"Galerie: „{name}“ aus Ordner {ordner} gelöscht.",
        herkunft="Galerie")
    session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang_id}#galerie", status_code=303)
