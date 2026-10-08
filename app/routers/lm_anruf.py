# Lead-Management V2 (v23) – Router anruf (PLAN_LEAD_V2 Phase 107: Anruf-
# Workflow & Telefonie, Teil 2 C1–C4, D1–D3, F2, F9). Eigener Router mit
# demselben Präfix; in app/main.py VOR dem V1-Router eingebunden, damit
# gleiche Pfade hier Vorrang haben.
#
# Routen dieser Datei (die V1-Route POST /anruf/{id} und GET /anrufliste
# liegen weiter in app/routers/leadmanagement.py und wurden dort erweitert):
#   GET  /lead-management/anruf/meine                     – Meine Anrufe (D2)
#   GET  /lead-management/anruf/suche?q=                  – Rufnummernsuche (D3/H7)
#   GET  /lead-management/anruf/{vorgang_id}/vorschlag    – Kaskaden-Auskunft JSON (C2;
#        v25 PLAN_LEAD_V3 Phase 120: der „Nicht erreicht“-Dialog ist entfallen, die
#        Route bleibt erreichbar, wird von der Oberfläche aber nicht mehr aufgerufen)
#   POST /lead-management/anruf/aktivitaet/{id}/dauer     – Dauer nachträglich korrigieren (D1)
#
# =====================================================================================
# Vorbereitung CTI (D1 / F2 – bewusst KEINE Anbindung in diesem Schritt)
# -------------------------------------------------------------------------------------
# Heute: Click-to-Call ist ein reiner tel:-Link (href aus lead_anrufliste.tel_href,
# E.164), die Dauer wird manuell über die Stoppuhr (app/static/lm_anruf.js) in
# lead_aktivitaeten.dauer_sek erfasst und ist hier korrigierbar. Es verlassen
# keine Daten den Arbeitsplatz (kein AVV-Bedarf).
#
# Damit eine spätere Telefonanlage/ein Softphone ohne Umbau andocken kann, sind
# die Felder bereits angelegt (Phase 104, alle nullable, idempotent über
# db._NACHTRAEGLICHE_SPALTEN):
#   lead_aktivitaeten.call_id      VARCHAR(100)  externe Gesprächskennung der Anlage
#                                                (Dedup eingehender Ereignisse; heute leer)
#   lead_aktivitaeten.richtung     VARCHAR(5)    "aus" | "ein" – manuelles Protokoll
#                                                schreibt immer "aus" (POST /anruf/{id})
#   lead_aktivitaeten.nebenstelle  VARCHAR(20)   Nebenstelle, von der aus gewählt wurde
#                                                (heute benutzer.nebenstelle beim Protokoll)
#   lead_aktivitaeten.dauer_sek    INTEGER       Primärfeld der Dauer (heute Stoppuhr,
#                                                später ende − beginn aus der Anlage)
#   lead_aktivitaeten.zeitpunkt    DATETIME      Protokollzeitpunkt (= Gesprächsbeginn
#                                                beim manuellen Protokoll)
#   benutzer.nebenstelle           VARCHAR(20)   Durchwahl je Benutzer (Pflege Admin)
#
# Ereignisse, die eine Anlage später liefert, werden auf GENAU diese Felder
# abgebildet – das Ergebnis (Tasten 1–7) bleibt eine manuelle Entscheidung:
#   „Anruf gestartet“  → neue Aktivität typ anruf ohne ergebnis: call_id, richtung,
#                        nebenstelle → Benutzer (benutzer.nebenstelle), zeitpunkt = Beginn,
#                        Vorgang über die Rufnummernsuche (lead_anrufliste.rufnummer_suchen)
#   „Anruf beendet“    → dauer_sek = Ende − Beginn (statt Stoppuhr), call_id als Schlüssel
#   „Eingehend“        → richtung "ein", Treffer der Rufnummernsuche als Glocke/Sprung
#                        in die Kartei (GET /lead-management/anruf/suche?q=<Nummer>)
# Datenschutz: sobald eine (Cloud-)Anlage beteiligt ist, werden Rufnummer,
# Zeitstempel, Dauer und Nebenstelle übertragen → AVV nötig; Platzhalter-
# Parameter cti_modus (aus) ist noch NICHT angelegt (erst mit der Anbindung).
# =====================================================================================

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import lead_anrufliste, lead_v2, leadmanagement_logik
from app import leadmanagement as kern
from app.db import get_session
from app.models import LeadAktivitaet, Vorgang, ANRUF_ERGEBNIS_NAMEN
from app.templating import render
from app import anfrage   # v27: Formular/JSON in def-Routen

router = APIRouter(prefix="/lead-management")

WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

AKTION_TEXTE = {
    "keine": "",
    "mail_nicht_erreicht": "E-Mail „Nicht erreicht“ geht an den Kunden.",
    "mail_disqualifiziert": "Letzter Versuch: E-Mail „Disqualifiziert“ geht raus, "
                            "Lead steht auf „Nicht erreicht“.",   # v29: ohne Nurture-Mail
}
# v25 (Phase 120): Hinweis in der Kaskaden-Auskunft – kein Vorschlag mehr angewendet
VORSCHLAG_HINWEIS = ("Seit v25 setzt die Kaskade keine Wiedervorlage mehr – Wiedervorlagen "
                     "setzt der Nutzer über den Wiedervorlage-Button.")


def _json_gewuenscht(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "")


def _eigene_sicht(session: Session, benutzer) -> int | None:
    """Handelsvertreter (A-1) sehen nur Vorgänge mit vorgaenge.ad_id = eigene ID;
    Modul-Sichtbare alles. Liefert die ad_id-Einschränkung oder None."""
    if kern.lead_modul_sichtbar(session, benutzer):
        return None
    return benutzer.id if benutzer is not None else 0


# --- D2: Meine Anrufe ----------------------------------------------------------------

@router.get("/anruf/meine")
def meine_anrufe(request: Request, session: Session = Depends(get_session)):
    """Eigene protokollierte Anrufe (lead_aktivitaeten typ anruf, benutzer_id =
    ich) mit Datum, Nummer (tel:), Vorgang (Link Kartei), Ergebnis, Dauer;
    Filter Zeitraum/Ergebnis/Suche. alle=1 (nur Modul-Sichtbare): Team-Sicht."""
    lead_v2.gate(request, session)
    benutzer = request.state.benutzer
    q = request.query_params
    zeitraum = q.get("zeitraum", "30")
    if zeitraum not in dict(lead_anrufliste.ZEITRAEUME) and not zeitraum.isdigit():
        zeitraum = "30"
    ergebnis = q.get("ergebnis", "")
    if ergebnis not in ANRUF_ERGEBNIS_NAMEN:
        ergebnis = ""
    nur_ad = _eigene_sicht(session, benutzer)
    alle = q.get("alle") == "1" and nur_ad is None
    zeilen = lead_anrufliste.anrufe_liste(
        session, None if alle else benutzer.id, zeitraum=zeitraum, ergebnis=ergebnis,
        von=q.get("von", ""), bis=q.get("bis", ""), q=q.get("q", ""), nur_ad_id=nur_ad)
    return render(request, "leadmanagement/anruf_meine.html", aktiv="/lead-management",
                  zeilen=zeilen, summen=lead_anrufliste.anrufe_summen(zeilen),
                  zeitraeume=lead_anrufliste.ZEITRAEUME, zeitraum=zeitraum,
                  ergebnis=ergebnis, ergebnis_namen=ANRUF_ERGEBNIS_NAMEN,
                  von=q.get("von", ""), bis=q.get("bis", ""), suche=q.get("q", ""),
                  alle=alle, team_sicht_erlaubt=nur_ad is None,
                  demo_badge=kern.demo_aktiv(session),
                  meldung=q.get("meldung", ""),
                  zurueck_pfad=str(request.url.path) + (f"?{request.url.query}" if request.url.query else ""))


# --- D3 / H7: Rufnummernsuche --------------------------------------------------------

@router.get("/anruf/suche")
def rufnummer_suche(request: Request, session: Session = Depends(get_session)):
    """„Rufnummer eingeben“: E.164-normalisiert (kern.telefon_normalisieren),
    Ziffernfolge-Vergleich in kunden.telefon und leads.telefon (monday).
    Genau ein Kunde mit Vorgang → direkt in die Kartei, sonst Trefferliste."""
    lead_v2.gate(request, session)
    benutzer = request.state.benutzer
    eingabe = (request.query_params.get("q") or "").strip()
    nur_ad = _eigene_sicht(session, benutzer)
    ergebnis = lead_anrufliste.rufnummer_suchen(session, eingabe, nur_ad_id=nur_ad) \
        if eingabe else {"ziffern": "", "treffer": [], "zu_kurz": True}
    treffer = ergebnis["treffer"]
    if len(treffer) == 1 and treffer[0]["vorgang"] is not None \
            and request.query_params.get("liste") != "1":
        return RedirectResponse(f"/lead-management/lead/{treffer[0]['vorgang'].id}",
                                status_code=303)
    return render(request, "leadmanagement/anruf_suche.html", aktiv="/lead-management",
                  eingabe=eingabe, ziffern=ergebnis["ziffern"], zu_kurz=ergebnis["zu_kurz"],
                  treffer=treffer, min_ziffern=lead_anrufliste.SUCHE_MIN_ZIFFERN,
                  demo_badge=kern.demo_aktiv(session),
                  # v25 (Phase 118): Phasen-Label aus dem Blatt Status („Kontaktiert“)
                  phasen_namen=lead_anrufliste.phasen_labels(leadmanagement_logik.hole_logik()))


# --- C2: Kaskaden-Auskunft (v25: nur noch Auskunft, kein Dialog) --------------------

@router.get("/anruf/{vorgang_id}/vorschlag")
def anruf_vorschlag(request: Request, vorgang_id: int,
                          session: Session = Depends(get_session)):
    """JSON {zeitpunkt (YYYY-MM-DDTHH:MM | null), zeitpunkt_text, stufe, stufen,
    regel, aktion, aktion_text, letzte, gesperrt, versuch_nr, versuche_max,
    hinweis}. v25 (Phase 120): bleibt erreichbar (Kompatibilität), die
    Oberfläche ruft die Route nicht mehr auf – `zeitpunkt` wird nicht mehr als
    Wiedervorlage angewendet."""
    vorgang = session.get(Vorgang, vorgang_id)
    lead_v2.gate(request, session, vorgang)
    if vorgang is None:
        return JSONResponse({"fehler": "Vorgang nicht gefunden"}, status_code=404)
    v = lead_anrufliste.anruf_vorschlag(session, vorgang)
    z = v["zeitpunkt"]
    return JSONResponse({
        "zeitpunkt": z.strftime("%Y-%m-%dT%H:%M") if z else None,
        "zeitpunkt_text": (f"{WOCHENTAGE[z.weekday()]} {z.strftime('%d.%m.%Y %H:%M')}"
                           if z else ""),
        "stufe": v["stufe"], "stufen": v["stufen"], "regel": v["regel"],
        "aktion": v["aktion"], "aktion_text": AKTION_TEXTE.get(v["aktion"], v["aktion"]),
        "letzte": v["letzte"], "gesperrt": v["gesperrt"],
        "sperre_meldung": lead_anrufliste.SPERRE_MELDUNG if v["gesperrt"] else "",
        "versuch_nr": vorgang.versuch_nr or 0, "versuche_max": v["versuche_max"],
        "hinweis": VORSCHLAG_HINWEIS,
    })


# --- D1: Dauer nachträglich korrigieren ---------------------------------------------

@router.post("/anruf/aktivitaet/{aktivitaet_id}/dauer")
def dauer_korrigieren(request: Request, aktivitaet_id: int,
                            session: Session = Depends(get_session)):
    """Formfeld dauer_sek (Sekunden oder mm:ss), optional zurueck. Nur eigener
    Eintrag oder Admin, nur typ anruf; Änderung als Aktivität typ system.
    Antwort JSON bei Accept: application/json (v17-Muster), sonst Redirect."""
    form = anfrage.formular(request)
    akt = session.get(LeadAktivitaet, aktivitaet_id)
    vorgang = session.get(Vorgang, akt.vorgang_id) if akt is not None else None
    lead_v2.gate(request, session, vorgang)
    zurueck = lead_anrufliste.zurueck_pfad(form.get("zurueck"), "/lead-management/anruf/meine")
    neu = lead_anrufliste.dauer_lesen(form.get("dauer_sek"))
    if akt is None:
        fehler = "Eintrag nicht gefunden."
    else:
        fehler = lead_anrufliste.dauer_korrigieren(session, akt, neu, request.state.benutzer)
    if fehler:
        session.rollback()
        if _json_gewuenscht(request):
            return JSONResponse({"ok": False, "fehler": fehler}, status_code=400)
        return RedirectResponse(lead_anrufliste.mit_meldung(zurueck, fehler), status_code=303)
    session.commit()
    text = lead_anrufliste.dauer_text(akt.dauer_sek)
    if _json_gewuenscht(request):
        return JSONResponse({"ok": True, "dauer_sek": akt.dauer_sek, "dauer": text})
    return RedirectResponse(lead_anrufliste.mit_meldung(zurueck, f"Dauer auf {text} korrigiert."),
                            status_code=303)
