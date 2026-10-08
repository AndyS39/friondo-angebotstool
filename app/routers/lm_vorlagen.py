# Lead-Management V4 (v29) – Router Vorlagen-Editor (PLAN_LEAD_V4 Phase 142):
# GET/POST /lead-management/vorlagen – Vorlagenliste als Baum in der linken
# Spalte (Kategorien Eingang · Kontakt · Terminbestätigung (ausklappbar: Standard
# + je Vertriebler) · Termin · Sonstige, Suche über Vorlagennamen), rechts der
# Editor (Betreff, HTML-Text mit Formatierungsleiste, Platzhalterliste, Vorschau
# mit Demo-Lead), „Rahmen für alle Terminbestätigungen übernehmen“ (Sicherheits-
# abfrage mit Anzahl, Protokoll in der Parametrierung). Speicherung weiter in den
# Einstellungen lead_vorlage_<key>[_<sparte>]_betreff/_text (+ _quelle/_hash).
# In app/main.py VOR den V2-/V1-Routern eingebunden (gleicher Pfad wie der alte
# Editor in lm_boards.py, den der Orchestrator am Ende entfernt). Rechte wie
# bisher: Admin/Innendienst pflegen, alle anderen Modul-Sichtbaren lesen,
# Handelsvertreter 404. Alle Routen `def`, kein Netzaufruf.

from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import anfrage, lead_mail, lead_v2, leadmanagement_logik
from app import leadmanagement as kern
from app.db import get_session
from app.models import Benutzer
from app.templating import render

router = APIRouter(prefix="/lead-management")

TERMIN_KEYS = ("terminbestaetigung", "terminerinnerung", "terminaenderung", "terminabsage",
               "online_termin_einladung")
STANDARD_KEY = "eingangsbestaetigung"
# Formatierungsleiste des Editors: (Knopf, Tag-Anfang, Tag-Ende)
FORMATE = [("Fett", "<strong>", "</strong>"), ("Kursiv", "<em>", "</em>"),
           ("Absatz", "<p>", "</p>"), ("Zeilenumbruch", "<br>", ""),
           ("Liste", "<ul>\n<li>", "</li>\n</ul>"), ("Listenpunkt", "<li>", "</li>"),
           ("Link", '<a href="https://">', "</a>")]


def _pflege_erlaubt(benutzer) -> bool:
    """Rechte wie heute: Admin/Innendienst pflegen; Hauptrolle leadmanagement
    (und alle anderen Modul-Sichtbaren) nur lesen."""
    return benutzer is not None and benutzer.rolle in ("admin", "innendienst")


def _gate(request: Request, session: Session) -> None:
    lead_v2.gate(request, session)
    # Handelsvertreter haben keinen Zugriff auf die Vorlagenpflege (Phase 140: 404)
    if lead_v2.ist_handelsvertreter(session, request.state.benutzer):
        raise HTTPException(status_code=404)


def _badge(session: Session) -> dict:
    return {"demo_badge": kern.demo_aktiv(session),
            "badge_text": kern.parameter_holen(session, "demo_badge_text", "Demo · Coming soon")}


def _key_lesen(session: Session, roh: str) -> str:
    key = (roh or "").strip()
    if (not key or key in lead_mail.VORLAGEN_AUSGEBLENDET
            or not lead_mail.schluessel_gueltig(session, key)):
        return STANDARD_KEY
    return key


def _ist_terminvorlage(key: str) -> bool:
    return key in TERMIN_KEYS or lead_mail.ist_vertriebler_key(key)


def _vorschau(session: Session, key: str, sparte: str, betreff: str, text: str) -> dict:
    """Vorschau mit Demo-Lead: {betreff, html, text}; Terminvorlagen bekommen einen
    transienten Termin beim Vertriebler der Vorlage (sonst dem ersten AD)."""
    ad_id = lead_mail.vertriebler_id_aus_key(key)
    vorgang, termin, kunde = lead_mail.demo_lead_fuer_vorschau(session, ad_id)
    try:
        betreff_v, html, _ = lead_mail.vorlage_rendern(
            session, key, vorgang, termin if _ist_terminvorlage(key) else None, sparte,
            vorschau=True, text_vorgabe=(betreff, text), kunde=kunde)
    except Exception as problem:   # Vorschau darf den Editor nie blockieren
        return {"betreff": betreff, "html": f"<p class=\"lm-rot\">Vorschau nicht möglich: {problem}</p>",
                "text": ""}
    return {"betreff": betreff_v, "html": html, "text": lead_mail.html_zu_text(html),
            "kunde": kunde.anzeige_name if kunde else ""}


@router.get("/vorlagen")
def vorlagen(request: Request, session: Session = Depends(get_session)):
    """Vorlagen-Editor mit Baum (links) und Editor + Vorschau (rechts)."""
    _gate(request, session)
    benutzer = request.state.benutzer
    key = _key_lesen(session, request.query_params.get("vorlage", STANDARD_KEY))
    sparte = request.query_params.get("sparte", "")
    if sparte not in leadmanagement_logik.SPARTEN or lead_mail.ist_vertriebler_key(key):
        sparte = ""
    betreff, text = lead_mail.vorlage_laden(session, key, sparte)
    vertriebler_id = lead_mail.vertriebler_id_aus_key(key)
    vertriebler = session.get(Benutzer, vertriebler_id) if vertriebler_id else None
    hv = vertriebler is not None and lead_v2.ist_handelsvertreter(session, vertriebler)
    katalog = lead_mail.vorlagen_katalog(session)
    terminvorlage = key == lead_mail.TERMIN_VORLAGE or lead_mail.ist_vertriebler_key(key)
    vorschau = _vorschau(session, key, sparte, betreff, text)
    logik = leadmanagement_logik.hole_logik()
    hinweise_fehlen = [s for s in leadmanagement_logik.SPARTEN
                       if not logik.hinweise_der_sparte(s)
                       or logik.hinweise_der_sparte(s) == ["(Punkte folgen)"]]
    return render(request, "leadmanagement/vorlagen.html", aktiv="/lead-management",
                  katalog=katalog, schluessel=key, sparte=sparte,
                  sparten=leadmanagement_logik.SPARTEN if not lead_mail.ist_vertriebler_key(key) else (),
                  name=lead_mail.vorlage_name(session, key), betreff=betreff, text=text,
                  eigene=lead_mail.vorlage_vorhanden(session, key),
                  quelle=lead_mail.vorlage_quelle(session, key),
                  vertriebler=vertriebler, hv=hv,
                  bild_vorhanden=lead_mail.bild_pfad(vertriebler) is not None if vertriebler else False,
                  terminvorlage=terminvorlage,
                  ziel_anzahl=lead_mail.ziel_anzahl(session, key) if terminvorlage else 0,
                  platzhalter=lead_mail.PLATZHALTER_NEU + ["{rueckruf_telefon}", "{buchungslink}", "{kollege}"],
                  formate=FORMATE, vorschau=vorschau, hinweise_fehlen=hinweise_fehlen,
                  html_vorlage=lead_mail.ist_html(text),
                  block_start=lead_mail.BLOCK_START, block_ende=lead_mail.BLOCK_ENDE,
                  pflege=_pflege_erlaubt(benutzer), suche=request.query_params.get("q", ""),
                  meldung=request.query_params.get("meldung", ""),
                  fehler=request.query_params.get("fehler", "") == "1", **_badge(session))


@router.post("/vorlagen")
def vorlagen_speichern(request: Request, session: Session = Depends(get_session)):
    """Speichern (Betreff/Text, Quelle editor), Sparten-Variante entfernen,
    Standard-Kopie für eine Vertreter-Vorlage, „Rahmen für alle übernehmen“."""
    _gate(request, session)
    benutzer = request.state.benutzer
    form = anfrage.formular(request)
    key = _key_lesen(session, form.get("vorlage") or "")
    zurueck = f"/lead-management/vorlagen?vorlage={key}"
    if not _pflege_erlaubt(benutzer):
        return RedirectResponse(zurueck + "&fehler=1&meldung="
                                + quote_plus("Vorlagen pflegen dürfen Admin und Innendienst – "
                                             "für Sie ist die Ansicht nur lesend."),
                                status_code=303)
    sparte = form.get("sparte") if form.get("sparte") in leadmanagement_logik.SPARTEN else ""
    if lead_mail.ist_vertriebler_key(key):
        sparte = ""
    aktion = (form.get("aktion") or "speichern").strip()
    if aktion == "entfernen" and sparte:
        lead_mail.vorlage_speichern(session, key, "", "", sparte=sparte)
        session.commit()
        return RedirectResponse(zurueck + "&meldung=" + quote_plus("Sparten-Variante entfernt – allgemein gilt."),
                                status_code=303)
    if aktion == "standard_kopie" and lead_mail.ist_vertriebler_key(key):
        betreff, text = lead_mail.vorlage_laden(session, lead_mail.TERMIN_VORLAGE)
        lead_mail.vorlage_speichern(session, key, betreff, text, quelle="standard_kopie")
        kern.einstellungs_protokoll(session, f"Vorlage {lead_mail.vorlage_name(session, key)} "
                                             "auf die Standard-Terminbestätigung zurückgesetzt", benutzer)
        session.commit()
        return RedirectResponse(zurueck + "&meldung=" + quote_plus("Standard-Kopie neu angelegt."),
                                status_code=303)
    betreff = (form.get("betreff") or "").strip()
    text = (form.get("text") or "").strip()
    if not betreff or not text:
        return RedirectResponse(zurueck + (f"&sparte={sparte}" if sparte else "")
                                + "&fehler=1&meldung=" + quote_plus("Betreff und Text sind Pflicht."),
                                status_code=303)
    lead_mail.vorlage_speichern(session, key, betreff, text, sparte=sparte, quelle="editor")
    meldung = "Gespeichert."
    terminvorlage = key == lead_mail.TERMIN_VORLAGE or lead_mail.ist_vertriebler_key(key)
    if terminvorlage and not sparte and form.get("rahmen_alle") in ("on", "1"):
        if form.get("bestaetigt") == "1":
            anzahl = lead_mail.rahmen_uebernehmen(session, key)
            kern.einstellungs_protokoll(
                session, f"Rahmen der Vorlage „{lead_mail.vorlage_name(session, key)}“ für "
                         f"{anzahl} Terminbestätigung(en) übernommen (individuelle Blöcke unverändert)",
                benutzer)
            meldung = f"Gespeichert – Rahmen für {anzahl} weitere Terminbestätigung(en) übernommen."
        else:
            meldung = "Gespeichert – Rahmen NICHT übernommen (Sicherheitsabfrage nicht bestätigt)."
    session.commit()
    return RedirectResponse(zurueck + (f"&sparte={sparte}" if sparte else "")
                            + "&meldung=" + quote_plus(meldung), status_code=303)


@router.post("/vorlagen/vorschau")
def vorlagen_vorschau(request: Request, session: Session = Depends(get_session)):
    """JSON {vorlage, sparte?, betreff, text} → {betreff, html, text} – Vorschau
    des ungespeicherten Editor-Texts mit einem Demo-Lead (kein Netzaufruf)."""
    _gate(request, session)
    try:
        daten = anfrage.json_lesen(request)
    except Exception:
        form = anfrage.formular(request)
        daten = dict(form)
    if not isinstance(daten, dict):
        return JSONResponse({"ok": False, "meldung": "Ungültige Anfrage."}, status_code=400)
    key = _key_lesen(session, str(daten.get("vorlage") or ""))
    sparte = daten.get("sparte") if daten.get("sparte") in leadmanagement_logik.SPARTEN else ""
    betreff = str(daten.get("betreff") or "")
    text = str(daten.get("text") or "")
    if not betreff and not text:
        betreff, text = lead_mail.vorlage_laden(session, key, sparte)
    ergebnis = _vorschau(session, key, sparte, betreff, text)
    ergebnis["ok"] = True
    return JSONResponse(ergebnis)
