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

from app import vorgaenge as vorgaenge_modul
from app.db import get_session
from app.models import (Angebot, AngebotsMail, Benutzer, Erfassung, Kunde,
                        Lead, Vorgang, VorgangNotizGelesen, VorgangsNotiz)
from app.templating import render

router = APIRouter(prefix="/vorgaenge")


def _eigener(session: Session, vorgang: Vorgang, benutzer) -> bool:
    if benutzer is None:
        return False
    if benutzer.rolle in ("admin", "innendienst"):
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
async def liste(request: Request, q: str = "", verfolgung: str = "",
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
    kunden = {k.id: k for k in session.query(Kunde)}
    leads = {l.id: l for l in session.query(Lead)}
    erf_je_vorgang: dict[int, list[Erfassung]] = {}
    for e in session.query(Erfassung).filter(Erfassung.vorgang_id.isnot(None)):
        erf_je_vorgang.setdefault(e.vorgang_id, []).append(e)
    ang_je_vorgang: dict[int, list[Angebot]] = {}
    for a in session.query(Angebot).filter(Angebot.vorgang_id.isnot(None)):
        ang_je_vorgang.setdefault(a.vorgang_id, []).append(a)
    if benutzer.rolle == "aussendienst":
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
                  mobil=benutzer.rolle == "aussendienst",
                  vorgaenge=vorgaenge, kunden=kunden, leads=leads,
                  erf_je_vorgang=erf_je_vorgang, ang_je_vorgang=ang_je_vorgang,
                  chips=chips, neue_notizen=neue_notizen, q=q,
                  verfolgung=verfolgung, benutzer=benutzer,
                  meldung=request.query_params.get("meldung", ""))


@router.get("/zu-lead/{lead_id}")
async def zu_lead(lead_id: int, session: Session = Depends(get_session)):
    lead = session.get(Lead, lead_id)
    if lead is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    vorgang = vorgaenge_modul.vorgang_fuer_lead(session, lead)
    session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang.id}", status_code=303)


@router.get("/zu-erfassung/{erfassung_id}")
async def zu_erfassung(erfassung_id: int, session: Session = Depends(get_session)):
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    vorgang = vorgaenge_modul.vorgang_fuer_erfassung(session, erfassung)
    session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang.id}", status_code=303)


@router.get("/zu-angebot/{angebot_id}")
async def zu_angebot(angebot_id: int, session: Session = Depends(get_session)):
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang.id}", status_code=303)


@router.get("/{vorgang_id}")
async def akte(request: Request, vorgang_id: int,
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
                    if b.rolle == "aussendienst" and b.aktiv]
    # v11 (Phase 66): Projektstand + „Angebot → Projekt" je angenommenem Angebot
    from app import projektierung as projektierung_modul
    from app.models import Gewerk as GewerkModell, Projekt as ProjektModell
    projekt_modul_ok = projektierung_modul.modul_sichtbar(session, benutzer)
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
    return render(request, "vorgaenge/akte.html", aktiv="/vorgaenge",
                  mobil=benutzer.rolle == "aussendienst",
                  lead_kontext=lead_kontext, lead_readonly=lead_readonly,
                  lead_phasen_namen=__import__("app.models", fromlist=["x"]).LEAD_PHASEN_NAMEN,
                  vorgang=vorgang, kunde=kunde, lead=lead, kanal=kanal,
                  profil=profil, erfassungen=erfassungen, angebote=angebote,
                  mails=mails, notizen=notizen, benutzer=benutzer,
                  benutzer_map=benutzer_map,
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
async def kombi_versand(request: Request, vorgang_id: int,
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
    if vorgang is None or benutzer.rolle not in ("admin", "innendienst"):
        return RedirectResponse("/vorgaenge", status_code=303)
    form = await request.form()
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
    if graph_versand.angemeldeter_benutzer() is None:
        return RedirectResponse("/versand?meldung=" + quote_plus(
            "Bitte zuerst mit Microsoft anmelden, dann den Kombi-Versand "
            "erneut starten."), status_code=303)
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
        for anhang in anhaenge_modul.fuer_angebot(logik, angebot):
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


@router.post("/{vorgang_id}/verfolgung")
async def verfolgung(request: Request, vorgang_id: int,
                     session: Session = Depends(get_session)):
    """Phase 60: Verfolgung des Vorgangs aus der Akte setzen (ID überall,
    AD an eigenen Vorgängen; den Verantwortlichen ändert nur der ID)."""
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None or not _eigener(session, vorgang, benutzer):
        return RedirectResponse("/vorgaenge", status_code=303)
    form = await request.form()
    verantwortlicher_id = None
    if benutzer.rolle in ("admin", "innendienst"):
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


@router.post("/{vorgang_id}/notiz")
async def notiz(request: Request, vorgang_id: int,
                session: Session = Depends(get_session)):
    """Notizen-Chat: append-only – jeder Eintrag mit Autor + Zeitstempel,
    kein Bearbeiten/Löschen. AD nur an eigenen Vorgängen."""
    benutzer = request.state.benutzer
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        return RedirectResponse("/vorgaenge", status_code=303)
    if not _eigener(session, vorgang, benutzer):
        return RedirectResponse("/vorgaenge", status_code=303)
    form = await request.form()
    text = (form.get("text") or "").strip()
    if text:
        vorgaenge_modul.notiz_anlegen(session, vorgang.id, benutzer, text[:2000])
        # der eigene Eintrag gilt sofort als gelesen
        marker = (session.query(VorgangNotizGelesen)
                  .filter(VorgangNotizGelesen.vorgang_id == vorgang.id,
                          VorgangNotizGelesen.benutzer_id == benutzer.id).first())
        if marker is not None:
            marker.gelesen_bis = datetime.now()
        session.commit()
    return RedirectResponse(f"/vorgaenge/{vorgang_id}#notizen", status_code=303)
