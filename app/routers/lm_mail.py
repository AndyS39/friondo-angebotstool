# Lead-Management V4 (v29) – Router Lead-Mails (PLAN_LEAD_V4 Phase 142):
#  POST /lead-management/mail/{eintrag_id}/erneut   „Erneut senden“ – setzt den
#       Warteschlangen-Eintrag auf geplant/sofort fällig (Versuche 0); gesendet
#       wird durch den Lauf lead-mail (≤ 60 s) – KEIN Versand im Request.
#  POST /lead-management/testmail                   Prüfpunkt „Testmail aus
#       termin@“ (Admin): einzige Ausnahme, die im Request senden darf –
#       Sitzung vorher freigeben (db.verbindung_freigeben), Demo nur Testpostfach.
#  POST /lead-management/vorlagen/einspielen        Terminbestätigungen aus
#       docs/vorlagen/terminbestaetigung/ einspielen (wiederholbar, Admin).
#  GET  /lead-management/lead/{id}/termin/{tid}/vorschau   fertige Terminbestätigung
#       (Text + HTML + ICS-Download) – hv_versandweg = offen; Nachtrag 08.10.2026
#       (Antwort Andreas): ?eml=1 liefert die Mail als .eml (message/rfc822,
#       Absender = E-Mail des HV, ICS + Inline-Bilder enthalten) für den Versandweg
#       `entwurf` (Standard) – Download, in Outlook/Mail öffnen, prüfen, senden.
#  GET  /lead-management/benutzer/{id}/bild         Benutzerbild (Vorschau/Editor).
# v31 (PLAN_LEAD_V5 Phase 158/159, Vertrag mit K – Kartei-Dialog „E-Mail senden“):
#  GET  /lead-management/lead/{id}/mail/vorschau.json?vorlage=&objekt_id=&termin_id=
#       → {ok, betreff, html, text, fehlende, vorlage_key, anhaenge, mail_versand_aktiv}
#  POST /lead-management/lead/{id}/mail/senden  (JSON/Formular: vorlage, betreff, text,
#       objekt_id, termin_id) → lead_mail.in_warteschlange (Doppelversand-Schutz, HV-
#       Versandweg, ICS bei Terminvorlagen); bei mail_versand_aktiv = aus endet der
#       Eintrag im Lauf lead-mail als `gesperrt` (kein Graph-Aufruf). Kein Versand im
#       Request. Die Vorschau-Route der HV-Terminbestätigung liefert bei
#       terminbestaetigung_objekte alle ICS (?ics=1&nr=).

from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app import anfrage, config, lead_mail, lead_v2, lead_v5
from app import leadmanagement as kern
from app import objekte as objekte_modul
from app.db import get_session, verbindung_freigeben
from app.models import Benutzer, KommunikationLog, Kunde, Vorgang, VotTermin
from app.templating import render

router = APIRouter(prefix="/lead-management")

WARTESCHLANGE_FEHLER = "/lead-management/kommunikation?status=fehler"
LEAD_EINSTELLUNGEN = "/parametrierung/lead-einstellungen"


def _json_gewuenscht(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "")


def _zurueck(request: Request, standard: str) -> str:
    """Redirect-Ziel: Pfad (+ Query) des Referers – nur relative Ziele dieses
    Tools (Open-Redirect-Schutz), sonst Standard."""
    from urllib.parse import urlsplit
    referer = request.headers.get("referer") or ""
    if not referer:
        return standard
    teile = urlsplit(referer)
    pfad = teile.path or ""
    if not pfad.startswith("/") or pfad.startswith("//") or "\\" in pfad:
        return standard
    return pfad + (f"?{teile.query}" if teile.query else "")


def _mit_meldung(pfad: str, meldung: str, fehler: bool = False) -> str:
    trenner = "&" if "?" in pfad else "?"
    return pfad + trenner + "meldung=" + quote_plus(meldung) + ("&fehler=1" if fehler else "")


def _nur_admin(request: Request) -> None:
    benutzer = request.state.benutzer
    if benutzer is None or benutzer.rolle != "admin":
        raise HTTPException(status_code=404)


# --- Erneut senden -------------------------------------------------------------------

@router.post("/mail/{eintrag_id}/erneut")
def mail_erneut(request: Request, eintrag_id: int, session: Session = Depends(get_session)):
    """Kartei-Hinweis / Warteschlange: Eintrag auf geplant mit sofortiger
    Fälligkeit, Versuchszähler 0; Rückmeldung „Erneuter Versand angestoßen –
    Ergebnis in etwa einer Minute“. Redirect zurück zum Referer bzw. zur
    Warteschlange mit Filter fehler; JSON bei Accept: application/json."""
    eintrag = session.get(KommunikationLog, eintrag_id)
    if eintrag is None:
        raise HTTPException(status_code=404)
    vorgang = session.get(Vorgang, eintrag.vorgang_id)
    lead_v2.gate(request, session, vorgang)
    ok, meldung = lead_mail.erneut_senden(session, eintrag, benutzer=request.state.benutzer)
    if ok:
        session.commit()
    else:
        session.rollback()
    if _json_gewuenscht(request):
        return JSONResponse({"ok": ok, "meldung": meldung, "eintrag_id": eintrag.id,
                             "status": eintrag.status}, status_code=200 if ok else 422)
    return RedirectResponse(_mit_meldung(_zurueck(request, WARTESCHLANGE_FEHLER), meldung, not ok),
                            status_code=303)


# --- Prüfpunkte der Lead-Parametrierung -------------------------------------------------

@router.post("/testmail")
def testmail(request: Request, session: Session = Depends(get_session)):
    """„Testmail aus termin@“ (Admin): sendet eine kurze Mail als absender_lead_mails
    an die Testadresse (Demo-Modus: ausschließlich mail_testadresse; sonst
    Formularfeld `an`, Standard = Testadresse bzw. eigene E-Mail). Alle Daten
    werden vor dem Netzaufruf gelesen, die Sitzung freigegeben; das Ergebnis
    steht danach im Einstellungs-Protokoll."""
    _nur_admin(request)
    form = anfrage.formular(request)
    benutzer = request.state.benutzer
    absender = lead_mail.absender(session)
    testadresse = (kern.parameter_holen(session, "mail_testadresse", "") or "").strip()
    demo = kern.demo_aktiv(session)
    an = (form.get("an") or "").strip() if not demo else ""
    if not an:
        an = testadresse or (benutzer.email or "").strip()
    if demo and not testadresse:
        return RedirectResponse(_mit_meldung(LEAD_EINSTELLUNGEN,
                                             "Im Demo-Modus geht die Testmail nur an das Testpostfach – "
                                             "bitte zuerst mail_testadresse eintragen.", True),
                                status_code=303)
    if not an or "@" not in an:
        return RedirectResponse(_mit_meldung(LEAD_EINSTELLUNGEN,
                                             "Keine Empfängeradresse (Testadresse oder eigene E-Mail fehlt).",
                                             True), status_code=303)
    from app import graph_versand
    if not graph_versand.konfiguriert():
        return RedirectResponse(_mit_meldung(LEAD_EINSTELLUNGEN,
                                             "Graph ist nicht eingerichtet (GRAPH_CLIENT_ID fehlt).", True),
                                status_code=303)
    # einzige Ausnahme von „kein Request sendet Mails“ – mit geschlossener Sitzung
    verbindung_freigeben(session)
    ok, fehler = lead_mail.testmail_senden(absender, an)
    if ok:
        text = f"Testmail aus {absender} an {an} gesendet"
    else:
        text = f"Testmail aus {absender} an {an} fehlgeschlagen: {fehler} (kein Fallback)"
    kern.einstellungs_protokoll(session, text[:300], benutzer)
    session.commit()
    return RedirectResponse(_mit_meldung(LEAD_EINSTELLUNGEN, text, not ok), status_code=303)


@router.post("/vorlagen/einspielen")
def vorlagen_einspielen(request: Request, session: Session = Depends(get_session)):
    """Knopf „Terminbestätigungen aus docs/vorlagen einspielen“ (Admin) – der
    wiederholbare Schritt aus lead_mail.zulieferung_einspielen."""
    _nur_admin(request)
    ergebnis = lead_mail.zulieferung_einspielen(session)
    session.commit()
    return RedirectResponse(_mit_meldung(LEAD_EINSTELLUNGEN, ergebnis["meldung"]), status_code=303)


# --- Vorschau der fertigen Terminbestätigung (HV-Zwischenlösung) ------------------------

@router.get("/lead/{vorgang_id}/termin/{termin_id}/vorschau")
def termin_vorschau(request: Request, vorgang_id: int, termin_id: int,
                    session: Session = Depends(get_session)):
    """Fertige Terminbestätigung (Betreff, Text zum Kopieren, HTML-Ansicht) und
    ICS-Download (?ics=1) bzw. Text-Download (?txt=1) – für Handelsvertreter,
    die ihre Terminbestätigung selbst senden (hv_versandweg = offen). Keine
    Warteschlange, kein Netzaufruf. ?vorlage=terminabsage|terminaenderung|
    terminerinnerung rendert die anderen Termin-Mails.
    Nachtrag 08.10.2026 (Antwort Andreas): ?eml=1 liefert die fertige Mail als
    RFC-822-Datei (message/rfc822, Terminbestaetigung_<Kunde>.eml) – Versandweg
    `entwurf`: Absender = E-Mail des HV, HTML + Text, ICS, Inline-Bilder."""
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        raise HTTPException(status_code=404)
    lead_v2.gate(request, session, vorgang)
    termin = session.get(VotTermin, termin_id)
    if termin is None or termin.vorgang_id != vorgang.id:
        raise HTTPException(status_code=404)
    vorlage = request.query_params.get("vorlage", lead_mail.TERMIN_VORLAGE)
    if vorlage not in lead_mail.HV_TERMIN_VORLAGEN:
        vorlage = lead_mail.TERMIN_VORLAGE
    if request.query_params.get("eml") == "1":
        eml = lead_mail.eml_erstellen(session, vorgang, termin, vorlage)
        session.commit()   # ics_uid kann gesetzt worden sein
        return Response(eml["bytes"], media_type="message/rfc822",
                        headers={"Content-Disposition": f'attachment; filename="{eml["dateiname"]}"',
                                 "X-Friondo-Absender": eml["absender"] or "-"})
    daten = lead_mail.termin_vorschau(session, vorgang, termin, vorlage)
    session.commit()   # ics_uid kann gesetzt worden sein
    kunde = session.get(Kunde, vorgang.kunde_id)
    if request.query_params.get("ics") == "1":
        # v31: Objekt-Terminbestätigung – ?nr= wählt das ICS des n-ten Objekttermins
        pfade = daten.get("ics_pfade") or ([daten["ics_pfad"]] if daten.get("ics_pfad") else [])
        nr = request.query_params.get("nr", "1")
        index = int(nr) - 1 if nr.isdigit() and int(nr) >= 1 else 0
        if index >= len(pfade) or not Path(pfade[index]).exists():
            raise HTTPException(status_code=404)
        return FileResponse(pfade[index], media_type="text/calendar",
                            filename=Path(pfade[index]).name)
    if request.query_params.get("txt") == "1":
        inhalt = f"Betreff: {daten['betreff']}\nAn: {kunde.email if kunde else ''}\n\n{daten['text']}\n"
        return Response(inhalt.encode("utf-8"), media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition":
                                 f'attachment; filename="{vorlage}_{termin.id}.txt"'})
    ad = session.get(Benutzer, termin.ad_id) if termin.ad_id else None
    hv = lead_mail.hv_benutzer(session, vorgang, termin)
    return render(request, "leadmanagement/_vorlagen_termin_vorschau.html",
                  aktiv="/lead-management", vorgang=vorgang, termin=termin, kunde=kunde,
                  ad=ad, daten=daten, vorlage=vorlage,
                  vorlage_name=lead_mail.vorlage_name(session, vorlage),
                  absender=lead_mail.absender(session), hv_versandweg=lead_mail.hv_versandweg(session),
                  # Nachtrag 08.10.2026: Versandweg entwurf – Absender des HV und .eml-Download
                  hv=hv, absender_hv=(hv.email or "").strip() if hv is not None else "",
                  eml_dateiname=lead_mail.eml_dateiname(vorlage, kunde),
                  demo_badge=kern.demo_aktiv(session),
                  ics_anzahl=len(daten.get("ics_pfade") or []),
                  meldung=request.query_params.get("meldung", ""))


# --- v31 (Phase 158): Vorschau und Versand aus der Kundenkartei (Vertrag mit K) ----------

def _mail_parameter(request: Request):
    try:
        daten = anfrage.json_lesen(request)
        if not isinstance(daten, dict):
            daten = {}
    except Exception:
        daten = dict(anfrage.formular(request))
    return daten


def _termin_fuer_mail(session: Session, vorgang: Vorgang, termin_id, objekt_id):
    """Aktiver Vor-Ort-Termin für die Vorlage: termin_id, sonst der aktive Termin des
    Objekts, sonst der nächste aktive Termin des Vorgangs."""
    from app import lead_termin
    if str(termin_id or "").isdigit():
        t = session.get(VotTermin, int(termin_id))
        if t is not None and t.vorgang_id == vorgang.id:
            return t
    objekt = lead_termin.objekt_holen(session, vorgang, objekt_id, anlegen=False) if objekt_id else None
    for z in lead_termin.objekt_termine(session, vorgang):
        if z["termin"] is not None and (objekt is None or z["objekt"].id == objekt.id):
            return z["termin"]
    aktive = lead_mail.objekttermine_aktiv(session, vorgang)
    return aktive[0] if aktive else None


@router.get("/lead/{vorgang_id}/mail/vorschau.json")
def mail_vorschau_json(request: Request, vorgang_id: int, session: Session = Depends(get_session)):
    """Vorschau einer Lead-Vorlage für einen echten Lead (Kartei-Dialog, K):
    ?vorlage=<key>&objekt_id=&termin_id= → {ok, vorlage_key, betreff, html, text,
    fehlende, anhaenge, termin_id, objekt_id, mail_versand_aktiv, mailsperre_hinweis,
    vorlagen (Auswahlliste)}. Kein Netzaufruf, nichts wird gespeichert."""
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        raise HTTPException(status_code=404)
    lead_v2.gate(request, session, vorgang)
    q = request.query_params
    key = (q.get("vorlage") or "eingangsbestaetigung").strip()
    if key in lead_mail.VORLAGEN_AUSGEBLENDET or not lead_mail.schluessel_gueltig(session, key):
        return JSONResponse({"ok": False, "meldung": "Unbekannte Vorlage."}, status_code=400)
    objekt_id = q.get("objekt_id", "")
    from app import lead_termin
    objekt = lead_termin.objekt_holen(session, vorgang, objekt_id, anlegen=False) if objekt_id.isdigit() else None
    termin = _termin_fuer_mail(session, vorgang, q.get("termin_id", ""), objekt.id if objekt else None)
    termine = lead_mail.objekttermine_aktiv(session, vorgang) if key == lead_mail.OBJEKT_VORLAGE else None
    betreff, html, fehlende = lead_mail.vorlage_rendern(session, key, vorgang, termin, vorschau=True,
                                                        objekt=objekt, benutzer=request.state.benutzer,
                                                        termine=termine)
    anhaenge = []
    basis = key if not lead_mail.ist_vertriebler_key(key) else lead_mail.TERMIN_VORLAGE
    if basis in lead_mail.TERMIN_PFLICHT_VORLAGEN and not fehlende:
        ziel = termine if key == lead_mail.OBJEKT_VORLAGE else ([termin] if termin else [])
        anhaenge = [Path(p).name for p in (lead_mail.ics_erstellen(session, t, vorgang) for t in ziel) if p]
    session.commit()   # ics_uid kann gesetzt worden sein
    katalog = [{"key": e["key"], "name": (kat["name"] + " – " + e["name"]) if kat["key"] == "terminbestaetigung" else e["name"],
                "kategorie": kat["name"]}
               for kat in lead_mail.vorlagen_katalog(session) for e in kat["eintraege"]]
    return JSONResponse({"ok": True, "vorlage_key": lead_mail.verwendeter_vorlagen_key(session, key, termin, termine),
                         "vorlage": key, "betreff": betreff, "html": html, "text": lead_mail.html_zu_text(html),
                         "fehlende": fehlende, "anhaenge": anhaenge,
                         "termin_id": termin.id if termin is not None else None,
                         "objekt_id": objekt.id if objekt is not None else None,
                         "mail_versand_aktiv": lead_v5.mail_versand_aktiv(session),
                         "mailsperre_hinweis": lead_v5.MAILSPERRE_HINWEIS,
                         "vorlagen": katalog})


@router.post("/lead/{vorgang_id}/mail/senden")
def mail_senden(request: Request, vorgang_id: int, session: Session = Depends(get_session)):
    """Nachbearbeitete Vorlagen-Mail aus der Kartei in die Warteschlange stellen
    (JSON/Formular: vorlage, betreff, text, objekt_id, termin_id). Antwort JSON
    {ok, meldung, eintrag_id, status} bzw. Redirect zur Kartei. Gesendet wird nur
    durch den Lauf lead-mail (bei Mailsperre: Status gesperrt)."""
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        raise HTTPException(status_code=404)
    lead_v2.gate(request, session, vorgang)
    daten = _mail_parameter(request)
    key = str(daten.get("vorlage") or "").strip()
    json_antwort = _json_gewuenscht(request)

    def _fehler(meldung: str, status: int = 400):
        if json_antwort:
            return JSONResponse({"ok": False, "meldung": meldung}, status_code=status)
        return RedirectResponse(_mit_meldung(f"/lead-management/lead/{vorgang.id}", meldung, True),
                                status_code=303)
    if key in lead_mail.VORLAGEN_AUSGEBLENDET or not lead_mail.schluessel_gueltig(session, key):
        return _fehler("Unbekannte Vorlage.")
    from app import lead_termin
    objekt_id = str(daten.get("objekt_id") or "")
    objekt = lead_termin.objekt_holen(session, vorgang, objekt_id, anlegen=False) if objekt_id.isdigit() else None
    termin = _termin_fuer_mail(session, vorgang, daten.get("termin_id"), objekt.id if objekt else None)
    termine = lead_mail.objekttermine_aktiv(session, vorgang) if key == lead_mail.OBJEKT_VORLAGE else None
    fehlende = lead_mail.fehlende_pflichtdaten(session, key, vorgang, termin, termine=termine)
    if fehlende:
        return _fehler("Senden gesperrt – es fehlt: " + ", ".join(fehlende), 422)
    betreff = str(daten.get("betreff") or "").strip()
    text = str(daten.get("text") or "").strip()
    if not betreff or not text:
        betreff_v, html_v, _ = lead_mail.vorlage_rendern(session, key, vorgang, termin, objekt=objekt,
                                                         benutzer=request.state.benutzer, termine=termine)
        betreff, text = betreff or betreff_v, text or html_v
    eintrag = lead_mail.in_warteschlange(session, vorgang, key, betreff, text, termin=termin,
                                         benutzer=request.state.benutzer)
    if eintrag is None:
        session.commit()   # HV-Entwurf/Aktivität ggf. geschrieben
        return _fehler("Keine Mail geplant (ohne E-Mail-Adresse, bereits geplant oder HV-Entwurf – "
                       "siehe Timeline).", 422)
    session.commit()
    meldung = f"E-Mail „{lead_mail.vorlage_name(session, key)}“ geplant an {eintrag.an}."
    if not lead_v5.mail_versand_aktiv(session):
        meldung += f" {lead_v5.MAILSPERRE_HINWEIS} – Eintrag bleibt gesperrt in der Warteschlange."
    if json_antwort:
        return JSONResponse({"ok": True, "meldung": meldung, "eintrag_id": eintrag.id, "status": eintrag.status})
    return RedirectResponse(_mit_meldung(f"/lead-management/lead/{vorgang.id}", meldung), status_code=303)


# --- Benutzerbild ----------------------------------------------------------------------

@router.get("/benutzer/{benutzer_id}/bild")
def benutzer_bild(request: Request, benutzer_id: int, session: Session = Depends(get_session)):
    """Bild des Vertrieblers (data/benutzerbilder/…) für Editor-Vorschau und
    Benutzerverwaltung; 404 ohne Bild. Zugriff: angemeldete Benutzer."""
    if request.state.benutzer is None:
        raise HTTPException(status_code=404)
    person = session.get(Benutzer, benutzer_id)
    pfad = lead_mail.bild_pfad(person) if person is not None else None
    if pfad is None:
        raise HTTPException(status_code=404)
    return FileResponse(str(pfad), media_type=lead_mail.bild_mime(pfad),
                        headers={"Cache-Control": "private, max-age=300"})
