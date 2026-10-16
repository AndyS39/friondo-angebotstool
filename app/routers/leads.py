# Leads VOT (Phase 19 Liste; Phase 22 füllt sie per monday-Lesesync):
# Leads mit Vor-Ort-Termin und ohne abgesendete Erfassung, chronologisch.
# Außendienst sieht nur eigene, Innendienst/Admin alle.
# v32 (PLAN_V19 Phase 161/162): GET /leads ist für den Außendienst die Vertriebler-Ansicht
# „Mein Tag“ (Daten in app/mein_tag.py und app/nachfassen.py).
# v33 (PLAN_V20 Phase 173/174, Protokoll Claudia Castro 14.10.2026 Teil A): „Mein Tag“ gilt
# nur mobil – der Server liefert dem Außendienst Karten (.mt-mobil, unter 600 px) UND die
# Tabelle „Leads VOT“ (.mt-desktop, ab 600 px) im selben HTML, die Media-Query blendet um
# [ANNAHME: einfachster Weg ohne User-Agent-Weiche]; Innendienst/Admin/Leadmanagement sehen
# nur die Tabelle. Der v32-Umschalter „Karten | Tabelle“ (Einstellung leads_darstellung)
# entfällt. Die Tabelle gruppiert nach Termintag (Überfällig · Heute · je Folgetag), hat die
# Sticky-Filterleiste, Spalten je Nutzer und Spaltensortierung aus den Lead-Board-Bausteinen
# (Phase 174, Vertrag T – Endstand: lead_boards.KATALOGE["leads_vot"], spalten_fuer/sortierung_fuer/
# spalten_fest/zeilen_sortieren, Jinja-Globals lm_spalten_url/lm_spalten_fest). Neu: GET /leads/wiedervorlagen (Seite „Wiedervorlage“
# mobil, nur Außendienst – andere Rollen → Angebotsliste mit Verfolgungsfilter).

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Benutzer, Erfassung, Kunde, Lead, Vorgang
from app.templating import render
from app import anfrage   # v27: Formular/JSON in def-Routen
from app import import_preisliste   # v27: Hinweis/Bestätigung monday-Vollabgleich
from app import rollen as rollen_modul   # v33: Basisrolle/Rollen-Varianten
from app import leadmanagement as lead_kern   # v35 (Phase 184): Kanal-Dropdown aus den Stammdaten

router = APIRouter(prefix="/leads")

WIEDERVORLAGE_ZIEL = "/leads/wiedervorlagen"
WIEDERVORLAGE_ID_ZIEL = "/angebote?verfolgung=versendet"   # [ANNAHME] ID/Admin: Angebotsliste mit Verfolgungsfilter
PRIORITAETEN = ("hoch", "mittel", "niedrig")


def erfasste_sparten(session: Session, leads) -> dict[int, set[str]]:
    """v8: je Lead die Sparten mit abgesendeter Erfassung (Entwürfe zählen nicht)."""
    ids = [l.id for l in leads]
    if not ids:
        return {}
    ergebnis: dict[int, set[str]] = {}
    for e in (session.query(Erfassung)
              .filter(Erfassung.lead_id.in_(ids), Erfassung.status != "Entwurf")):
        ergebnis.setdefault(e.lead_id, set()).add(e.sparte or "WP")
    return ergebnis


def sparten_chips(lead, erfasst: set[str]) -> list[tuple[str, str]]:
    """v8: Chip-Status je Interesse – (Sparte, erfasst|ausgeblendet|offen)."""
    ausgeblendet = set(lead.ausgeblendete_sparten)
    return [(s, "erfasst" if s in erfasst
             else ("ausgeblendet" if s in ausgeblendet else "offen"))
            for s in lead.sparten]


def offene_leads(session: Session, benutzer=None, ausgeblendet: bool = False):
    """Offene Leads (VOT-Datum): seit v8 verlässt ein Lead die Liste erst,
    wenn ALLE Interessen (Sparten) erfasst oder ausgeblendet sind. Standard
    ohne ganz ausgeblendete; ausgeblendet=True liefert nur diese."""
    abfrage = (session.query(Lead)
               .filter(Lead.vot_datum.isnot(None))
               .filter(Lead.ausgeblendet.is_(ausgeblendet)))
    if benutzer is not None and benutzer.basisrolle == "aussendienst":
        abfrage = abfrage.filter(Lead.benutzer_id == benutzer.id)
    kandidaten = abfrage.order_by(Lead.vot_datum).all()
    erfasst = erfasste_sparten(session, kandidaten)
    if ausgeblendet:
        return kandidaten
    return [l for l in kandidaten
            if any(status == "offen"
                   for _, status in sparten_chips(l, erfasst.get(l.id, set())))]


# --- Wiedervorlage (Phase 173) ------------------------------------------------------------

def _wiedervorlage_kontext(session: Session, benutzer, ziel: str, heute=None) -> dict:
    """Karten des Abschnitts „Wiedervorlage“ (nachfassen.wiedervorlage_liste) samt Kontext des
    Dialogs „Nächster Schritt“ (Partial von N) und Chip-Zählern."""
    from app import mein_tag, nachfassen
    karten = nachfassen.wiedervorlage_liste(session, benutzer.id, heute)
    schritt_kontext = {k["vorgang"].id: mein_tag.naechster_schritt_kontext(session, k["vorgang"], ziel, heute,
                                                                           benutzer=benutzer)
                       for k in karten}
    try:   # Vertrag N: Chip-Text des Verfolgungsstatus (Makro verfolgung_chip, sonst Text)
        from app import verfolgung
        status_text = verfolgung.status_text
    except (ImportError, AttributeError):
        status_text = (lambda s: s or "")
    try:
        from app import lead_boards
        grosskunde_farbe = lead_boards.grosskunde_farbe(session)
    except Exception:   # noqa: BLE001
        grosskunde_farbe = ""
    return {"wiedervorlagen": karten, "wv_zaehler": nachfassen.wiedervorlage_zaehler(karten),
            "schritt_kontext": schritt_kontext, "partial_da": mein_tag.partial_vorhanden(),
            "ziel": ziel, "verfolgung_status_text": status_text,
            "grosskunde_farbe": grosskunde_farbe, "prioritaeten": PRIORITAETEN}


@router.get("/wiedervorlagen")
def wiedervorlagen(request: Request, session: Session = Depends(get_session)):
    """v33 (PLAN_V20 Phase 173): Seite „Wiedervorlage“ mobil (Basisrolle Außendienst):
    Zurück-Pfeil „Mein Tag“, Titel mit Zähler „n offen“, Suchfeld, Chips Alle/Hoch/Mittel/
    Niedrig (Anzahl bezogen auf die Suchtreffer, clientseitig), Sortierung mit Richtungspfeil,
    alle Vorgänge ohne Begrenzung, Leerzustand. Innendienst/Admin → Angebotsliste mit
    Verfolgungsfilter (303)."""
    from app import mein_tag
    benutzer = request.state.benutzer
    if not mein_tag.ist_aussendienst(benutzer):
        return RedirectResponse(WIEDERVORLAGE_ID_ZIEL, status_code=303)
    kontext = _wiedervorlage_kontext(session, benutzer, WIEDERVORLAGE_ZIEL)
    return render(request, "leads/wiedervorlagen.html", aktiv="/leads", mobil=True,
                  benutzer=benutzer, aussendienst=True, heute=datetime.now(),
                  meldung=request.query_params.get("meldung", ""), **kontext)


# --- GET /leads: Mein Tag (mobil, AD) + Tabelle Leads VOT (Desktop, alle Rollen) ----------

@router.get("")
def liste(request: Request, q: str = "", interesse: str = "",
          vertriebler_id: int = 0, lead_status: str = "", sortierung: str = "",
          ansicht: str = "", kanal: str = "", prioritaet: str = "",
          session: Session = Depends(get_session)):
    """v33 (PLAN_V20 Phase 173): Außendienst → templates/leads/mein_tag.html mit beiden
    Darstellungen (Karten mobil, Tabelle ab 600 px); übrige Rollen → templates/leads/
    liste.html (nur Tabelle). Filter der Tabelle: q, interesse, vertriebler_id, lead_status,
    kanal, prioritaet (hoch|mittel|niedrig = Hot-Ampel), ansicht (ausgeblendet |
    ueberfaellig); `sortierung` (v5: termin|vertriebler|status) sortiert innerhalb der
    Gruppen, sonst gilt die je Nutzer gemerkte Spaltensortierung (T)."""
    from app import mein_tag
    benutzer = request.state.benutzer
    tabelle = _tabelle_kontext(session, benutzer, q, interesse, vertriebler_id, lead_status,
                               sortierung, ansicht, kanal, prioritaet)
    meldung = request.query_params.get("meldung", "")
    if mein_tag.ist_aussendienst(benutzer):
        kontext = dict(tabelle)
        kontext.update(_mein_tag_kontext(session, benutzer))   # gleiche Schlüssel: Karten gewinnen
        return render(request, "leads/mein_tag.html", aktiv="/leads", meldung=meldung, **kontext)
    return render(request, "leads/liste.html", aktiv="/leads", meldung=meldung, **tabelle)


def _mein_tag_kontext(session: Session, benutzer, heute=None) -> dict:
    """Kartenansicht „Mein Tag“ (Phase 173): Kopf (Datum ausgeschrieben, Initialen), Karte
    „Als Nächstes“, Liste „Heute“ mit Zeitstrahl, Abschnitt „Wiedervorlage“, „Kommende
    Tage“ (14 Tage); Daten aus app/mein_tag.py und app/nachfassen.py."""
    from app import mein_tag
    jetzt = heute if isinstance(heute, datetime) else datetime.now()
    termine = mein_tag.termine(session, benutzer, heute=jetzt)
    kontext = _wiedervorlage_kontext(session, benutzer, "/leads#wiedervorlage", jetzt.date())
    kontext.update({
        "mobil": True, "aussendienst": True, "benutzer": benutzer,
        "heute": jetzt, "heute_lang": mein_tag.datum_lang(jetzt),
        "initialen": mein_tag.initialen(benutzer),
        "naechster": termine["naechster"],
        "termine_heute": termine["heute"], "termine_weitere": termine["weitere"],
        "termine_heute_nur": termine["heute_nur"], "termine_ueberfaellig": termine["ueberfaellige"],
        "kommende": termine["kommende"], "spaeter": termine["spaeter"],
        "grenze_text": termine["grenze"].strftime("%d.%m."),
        "ueberfaellig_anzahl": termine["ueberfaellig"],
        "termine_anzahl": termine["anzahl"], "termine_gesamt": termine["gesamt"],
        "wv_max": 4,
    })
    return kontext


def _tabelle_kontext(session: Session, benutzer, q: str, interesse: str, vertriebler_id: int,
                     lead_status: str, sortierung: str, ansicht: str, kanal: str,
                     prioritaet: str = "", heute=None) -> dict:
    """Tabelle „Leads VOT“ (Lead-basiert wie seit v1/v8) mit Gruppen je Termintag,
    Priorität = Hot-Ampel des Vorgangs, Spalten je Nutzer (Vertrag T) und Sortierung
    innerhalb der Gruppen (Phase 174)."""
    from app import mein_tag, monday_sync
    jetzt = heute if isinstance(heute, datetime) else datetime.now()
    aussendienst_sicht = benutzer.basisrolle == "aussendienst"
    ausgeblendet = ansicht == "ausgeblendet"   # Filter „Ausgeblendet“ (v5-Nachtrag)
    alle = offene_leads(session, benutzer, ausgeblendet=ausgeblendet)
    vertriebler = {b.id: b for b in session.query(Benutzer)}
    # Auswahlwerte für die Filter aus der ungefilterten Liste
    status_werte = sorted({l.status_text for l in alle if l.status_text})
    kanal_werte = sorted({l.vertriebskanal for l in alle if l.vertriebskanal})
    # Warnhinweis (v6): offene Leads ohne Vertriebler-Zuordnung (nur Büro)
    ohne_ad = 0 if (ausgeblendet or aussendienst_sicht) else sum(
        1 for l in alle if not l.benutzer_id)
    vertriebler_werte = sorted({l.benutzer_id for l in alle if l.benutzer_id},
                               key=lambda i: vertriebler[i].name if i in vertriebler else "")
    # Vorgang je Lead: Hot-Ampel = Priorität (Phase 173/174), Großkunde am Kunden
    vorgaenge = {v.lead_id: v for v in session.query(Vorgang)
                 .filter(Vorgang.lead_id.in_([l.id for l in alle] or [0]))}
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({l.kunde_id for l in alle if l.kunde_id} or {0}))}
    leads = alle
    if q:
        suchwort = q.lower()
        leads = [l for l in leads
                 if suchwort in l.anzeige_name.lower()
                 or suchwort in (l.ort or "").lower()
                 or suchwort in (l.plz or "")]
    if interesse:   # Filter nach Interesse (Phase 33)
        leads = [l for l in leads if interesse in l.interessen]
    # Filter Vertriebler + Status (v5, Phase 35) – kombinierbar mit Suche
    if vertriebler_id:
        leads = [l for l in leads if l.benutzer_id == vertriebler_id]
    if lead_status:
        leads = [l for l in leads if l.status_text == lead_status]
    if kanal:   # Vertriebskanal (v6)
        leads = [l for l in leads if l.vertriebskanal == kanal]
    prioritaet = prioritaet if prioritaet in PRIORITAETEN else ""
    if prioritaet:   # v33 (Phase 174): Priorität = Hot-Ampel des Vorgangs
        leads = [l for l in leads
                 if mein_tag.prioritaet_von(getattr(vorgaenge.get(l.id), "verfolgung_ampel", "") or "")
                 == prioritaet]
    # Prozess-Fix 27.09.2026: VOT liegt in der Vergangenheit, aber keine
    # Sparte ist erfasst - vorher stand so ein Lead wochenlang unauffaellig
    # als "Terminiert" in der Liste
    ueberfaellige = [l for l in leads
                     if l.vot_datum is not None and l.vot_datum < jetzt]
    if ansicht == "ueberfaellig":
        leads = ueberfaellige
    aussendienst = (session.query(Benutzer)
                    .filter(rollen_modul.filter_basis("aussendienst"), Benutzer.aktiv.is_(True))
                    .order_by(Benutzer.name).all())
    # v8: Status-Chips je Interesse („WP ✓ · PV offen“)
    erfasst = erfasste_sparten(session, leads)
    chips = {l.id: sparten_chips(l, erfasst.get(l.id, set())) for l in leads}
    zeilen = []
    for l in leads:
        vorgang = vorgaenge.get(l.id)
        kunde = kunden.get(l.kunde_id) if l.kunde_id else None
        ampel = (getattr(vorgang, "verfolgung_ampel", "") or "") if vorgang is not None else ""
        prio = mein_tag.prioritaet_von(ampel)
        vname = (vertriebler[l.benutzer_id].name if l.benutzer_id in vertriebler
                 else (l.monday_person or ""))
        zeilen.append({
            "id": l.id, "lead": l, "vorgang": vorgang, "kunde": kunde,
            "termin": l.vot_datum,
            "termin_text": l.vot_datum.strftime("%d.%m.%Y %H:%M") if l.vot_datum else "",
            "uhr": l.vot_datum.strftime("%H:%M") if l.vot_datum else "",
            "ueberfaellig": l.vot_datum is not None and l.vot_datum < jetzt,
            "name": l.anzeige_name, "ort": " ".join(x for x in (l.plz or "", l.ort or "") if x),
            "kanal": l.vertriebskanal or "", "vertriebler": vname,
            "vertriebler_id": l.benutzer_id, "status": l.status_text or "",
            "prioritaet": prio, "prioritaet_text": mein_tag.PRIORITAET_TEXTE[prio], "ampel": ampel,
            "sparten": list(l.sparten), "chips": chips.get(l.id, []),
            "grosskunde": bool(getattr(kunde, "grosskunde", False)) if kunde is not None else False,
        })
    # Spaltensortierung je Nutzer (T) – der v5-Parameter `sortierung` übersteuert sie
    sort = mein_tag.sortierung_fuer(session, benutzer)
    if sortierung in ("vertriebler", "status"):
        sort = {"key": sortierung, "richtung": "auf"}
    elif sortierung == "termin":
        sort = None
    gruppen = mein_tag.gruppen_sortieren(mein_tag.gruppen_bilden(zeilen, jetzt), sort)
    spalten = mein_tag.spalten_fuer(session, benutzer)   # Vertrag T: Katalog leads_vot, Rollen-Katalog
    from app import lead_boards
    grosskunde_farbe = lead_boards.grosskunde_farbe(session)
    return {"mobil": aussendienst_sicht, "ad_sicht": aussendienst_sicht,
            "aussendienst_liste": aussendienst, "chips": chips,
            "leads": leads, "zeilen": zeilen, "gruppen": gruppen, "spalten": spalten,
            "sortierung_spalte": sort, "board_key": mein_tag.BOARD_KEY,
            "tabellen_ctx": {"board": mein_tag.BOARD_KEY, "sortierung": sort},
            "vertriebler": vertriebler, "benutzer": benutzer,
            "q": q, "interesse": interesse, "vertriebler_id": vertriebler_id,
            "lead_status": lead_status, "sortierung": sortierung or "termin", "ansicht": ansicht,
            "ausgeblendet": ausgeblendet, "kanal": kanal, "kanal_werte": kanal_werte,
            # v35 (PLAN_LEAD_V6 Phase 184): Dropdown „Kanal manuell setzen“ aus den Stammdaten
            "kanal_wahl": lead_kern.kanal_werte(session),
            "prioritaet": prioritaet, "prioritaeten": PRIORITAETEN,
            "prioritaet_texte": mein_tag.PRIORITAET_TEXTE,
            "ohne_ad": ohne_ad, "ueberfaellig_anzahl": len(ueberfaellige),
            "heute": jetzt, "grosskunde_farbe": grosskunde_farbe,
            "status_werte": status_werte, "vertriebler_werte": vertriebler_werte,
            "sync_status": monday_sync.status,
            # v27 (Phase 128): Hinweistext vor dem monday-Vollabgleich
            "monday_hinweis": import_preisliste.import_hinweis(session, "monday"),
            "filter_aktiv": bool(q or interesse or vertriebler_id or lead_status or kanal
                                 or prioritaet or ansicht or (sortierung and sortierung != "termin"))}


@router.post("/notiz/{vorgang_id}")
def notiz_zum_gespraech(request: Request, vorgang_id: int,
                        session: Session = Depends(get_session)):
    """v32 (PLAN_V19 Phase 162): Notizfeld „Notiz zum Gespräch“ der Anruf-Karte – EIN
    Eintrag im Notizen-Chat des Vorgangs (notizen-Modul, keine zweite Notizspur), Autor =
    angemeldeter Benutzer, Rechte wie die Akte (notizen.schreiben_erlaubt). JSON bei
    Accept: application/json, sonst Redirect zurück nach Mein Tag."""
    from app import notizen
    from app.models import Vorgang
    benutzer = request.state.benutzer
    json_antwort = "application/json" in (request.headers.get("accept") or "")
    vorgang = session.get(Vorgang, vorgang_id)
    form = anfrage.formular(request)
    zurueck = (form.get("zurueck") or "/leads#wiedervorlage")   # v33: Abschnitt „Wiedervorlage“
    if not zurueck.startswith("/") or zurueck.startswith("//"):
        zurueck = "/leads#wiedervorlage"
    if vorgang is None or not notizen.schreiben_erlaubt(session, vorgang, benutzer):
        if json_antwort:
            return JSONResponse({"ok": False, "meldung": "Keine Berechtigung für diesen Vorgang."},
                                status_code=403)
        return RedirectResponse(zurueck, status_code=303)
    text = (form.get("text") or "").strip()
    if not text:
        if json_antwort:
            return JSONResponse({"ok": False, "meldung": "Bitte eine Notiz eingeben."}, status_code=400)
        return RedirectResponse(zurueck, status_code=303)
    eintrag = notizen.notiz_anlegen(session, vorgang.id, benutzer, text,
                                    herkunft=notizen.herkunft_fuer(benutzer, "vertrieb"))
    session.commit()
    if json_antwort:
        return JSONResponse({"ok": True, "eintrag": notizen.eintrag_json(eintrag),
                             "meldung": "Notiz gespeichert."})
    from urllib.parse import quote_plus
    trenner = "&" if "?" in zurueck else "?"
    pfad, _, anker = zurueck.partition("#")
    return RedirectResponse(f"{pfad}{trenner}meldung={quote_plus('Notiz gespeichert.')}"
                            + (f"#{anker}" if anker else ""), status_code=303)


@router.post("/sync")
def jetzt_aktualisieren(request: Request, session: Session = Depends(get_session)):
    """Button „Jetzt aktualisieren“ – Fehler werden angezeigt, blockieren nichts.
    v27 (PLAN_V17 Phase 128): Vollabgleich ist ein Import – Hinweis mit Bestätigung
    (Feld bestaetigt), Dauer wird als import_dauer_monday gemerkt, der Lauf steht
    währenddessen im Betriebs-Status (monday_sync.sync markiert ihn)."""
    import time
    from urllib.parse import quote_plus

    from app import monday_sync
    if not import_preisliste.import_bestaetigt(anfrage.formular(request)):
        return RedirectResponse(
            "/leads?meldung=" + quote_plus(import_preisliste.HINWEIS_BESTAETIGEN), status_code=303)
    start = time.perf_counter()
    ergebnis = monday_sync.sync(session)
    import_preisliste.import_dauer_merken(session, "monday", start)
    if ergebnis["fehler"]:
        meldung = "Sync mit Hinweisen: " + " · ".join(ergebnis["fehler"])[:300]
    else:
        meldung = f"Sync abgeschlossen – {ergebnis['anzahl']} Leads aktualisiert."
    return RedirectResponse(f"/leads?meldung={quote_plus(meldung)}", status_code=303)


@router.post("/{lead_id}/vertriebler")
def vertriebler_aendern(request: Request, lead_id: int,
                              session: Session = Depends(get_session)):
    """Innendienst/Admin ordnet den Lead einem anderen Außendienstler zu
    (v5-Nachtrag); der monday-Sync überschreibt das beim nächsten Lauf nur,
    wenn sich die Personen-Spalte in monday ändert – daher wird zusätzlich
    die Personen-Zuordnung nicht angefasst, nur dieser Lead."""
    from urllib.parse import quote_plus
    benutzer = request.state.benutzer
    if benutzer.basisrolle == "aussendienst":
        return RedirectResponse("/leads", status_code=303)
    lead = session.get(Lead, lead_id)
    if lead is None:
        return RedirectResponse("/leads", status_code=303)
    form = anfrage.formular(request)
    wert = form.get("benutzer_id") or ""
    if wert.isdigit() and int(wert) > 0:
        lead.benutzer_id = int(wert)
        lead.benutzer_manuell = True    # Sync überschreibt nicht mehr
    else:
        lead.benutzer_id = None
        lead.benutzer_manuell = False   # zurück zur monday-Zuordnung beim nächsten Sync
    session.commit()
    neuer = session.get(Benutzer, lead.benutzer_id) if lead.benutzer_id else None
    return RedirectResponse("/leads?meldung=" + quote_plus(
        f"{lead.anzeige_name} → Vertriebler: {neuer.name if neuer else 'nicht zugeordnet'}"),
        status_code=303)


@router.post("/{lead_id}/ausblenden")
def ausblenden(request: Request, lead_id: int,
                     session: Session = Depends(get_session)):
    """Lead aus „Leads VOT“ nehmen (optional mit Grund); nicht löschen – der
    Sync lässt das Kennzeichen stehen, der Lead taucht nicht erneut auf."""
    from urllib.parse import quote_plus
    benutzer = request.state.benutzer
    lead = session.get(Lead, lead_id)
    if lead is None or (benutzer.basisrolle == "aussendienst" and lead.benutzer_id != benutzer.id):
        return RedirectResponse("/leads", status_code=303)
    form = anfrage.formular(request)
    lead.ausgeblendet = True
    lead.ausgeblendet_grund = (form.get("grund") or "").strip()[:300]
    lead.ausgeblendet_am = datetime.now()
    session.commit()
    return RedirectResponse("/leads?meldung=" + quote_plus(
        f"{lead.anzeige_name} ausgeblendet – über die Ansicht „Ausgeblendet“ zurückholbar."),
        status_code=303)


@router.post("/{lead_id}/kanal")
def kanal_aendern(request: Request, lead_id: int,
                        session: Session = Depends(get_session)):
    """v9: Vertriebskanal manuell setzen (Vorrang vor dem monday-Sync);
    wirkt auf Lead UND Kunden. Leer = zurück zur Sync-Automatik."""
    from urllib.parse import quote_plus

    from app.models import Kunde
    benutzer = request.state.benutzer
    if benutzer.basisrolle == "aussendienst":
        return RedirectResponse("/leads", status_code=303)
    lead = session.get(Lead, lead_id)
    if lead is None:
        return RedirectResponse("/leads", status_code=303)
    form = anfrage.formular(request)
    kanal = (form.get("kanal") or "").strip()[:100]
    lead.vertriebskanal = kanal
    lead.kanal_manuell = bool(kanal)
    kunde = session.get(Kunde, lead.kunde_id) if lead.kunde_id else None
    if kunde is not None:
        kunde.vertriebskanal = kanal
        kunde.kanal_manuell = bool(kanal)
    # v23 (Phase 109, G4): Vorgang des Leads auf Ausschlusskanal prüfen
    try:
        from app import lead_handelsvertreter
        from app.models import Vorgang
        vorgang = session.query(Vorgang).filter(Vorgang.lead_id == lead.id).first()
        if vorgang is not None:
            lead_handelsvertreter.kanalwechsel_pruefen(session, vorgang, request.state.benutzer)
    except Exception:
        pass
    session.commit()
    return RedirectResponse("/leads?meldung=" + quote_plus(
        f"{lead.anzeige_name}: Kanal "
        + (f"manuell auf „{kanal}“ gesetzt (Sync überschreibt nicht mehr)."
           if kanal else "zurück auf Sync-Automatik.")), status_code=303)


@router.post("/{lead_id}/sparte-ausblenden")
def sparte_ausblenden(request: Request, lead_id: int,
                            session: Session = Depends(get_session)):
    """v8: eine einzelne Sparte (Interesse) des Leads ausblenden bzw.
    zurückholen – der Lead bleibt sichtbar, solange andere Sparten offen sind."""
    from urllib.parse import quote_plus

    from app.models import interesse_text
    benutzer = request.state.benutzer
    lead = session.get(Lead, lead_id)
    if lead is None or (benutzer.basisrolle == "aussendienst" and lead.benutzer_id != benutzer.id):
        return RedirectResponse("/leads", status_code=303)
    form = anfrage.formular(request)
    sparte = (form.get("sparte") or "").strip().upper()
    if sparte not in lead.sparten:
        return RedirectResponse("/leads", status_code=303)
    ausgeblendet = set(lead.ausgeblendete_sparten)
    if sparte in ausgeblendet:
        ausgeblendet.discard(sparte)
        meldung = f"{lead.anzeige_name}: Sparte {sparte} wieder offen."
    else:
        ausgeblendet.add(sparte)
        meldung = f"{lead.anzeige_name}: Sparte {sparte} ausgeblendet."
    lead.ausgeblendet_sparten = interesse_text(ausgeblendet)
    session.commit()
    return RedirectResponse("/leads?meldung=" + quote_plus(meldung), status_code=303)


@router.post("/{lead_id}/zurueckholen")
def zurueckholen(request: Request, lead_id: int,
                       session: Session = Depends(get_session)):
    from urllib.parse import quote_plus
    benutzer = request.state.benutzer
    lead = session.get(Lead, lead_id)
    if lead is None or (benutzer.basisrolle == "aussendienst" and lead.benutzer_id != benutzer.id):
        return RedirectResponse("/leads", status_code=303)
    lead.ausgeblendet = False
    lead.ausgeblendet_grund = ""
    lead.ausgeblendet_am = None
    session.commit()
    return RedirectResponse("/leads?meldung=" + quote_plus(
        f"{lead.anzeige_name} wieder in Leads VOT."), status_code=303)


@router.get("/{lead_id}/erfassen")
def erfassen(request: Request, lead_id: int, objekt_id: int = 0,
                   session: Session = Depends(get_session)):
    """Klick auf den Lead: Erfassung mit dem (per Sync angelegten) Kunden
    starten, Lead ↔ Kunde ↔ Erfassung verknüpfen.
    v31 (PLAN_LEAD_V5 Phase 153): `objekt_id` übergibt das Objekt des Vorgangs an
    die Sparten-Auswahl (Ausführungsort = Objektadresse, Objektart belegt
    O01/O03/PO01 vor); ohne Angabe gilt das Hauptobjekt."""
    benutzer = request.state.benutzer
    lead = session.get(Lead, lead_id)
    if lead is None:
        return RedirectResponse("/leads", status_code=303)
    if benutzer.basisrolle == "aussendienst" and lead.benutzer_id != benutzer.id:
        # v32 (PLAN_V19 Phase 161): der Vertriebler des Termins (vot_termine.ad_id bzw.
        # vorgaenge.ad_id) darf die Erfassung starten, auch wenn er vom Lead-Vertriebler
        # abweicht – Prüfung wie die Vorgangsakte (vorgaenge.gehoert_benutzer)
        from app import vorgaenge as vorgaenge_modul
        from app.models import Vorgang
        vorgang = session.query(Vorgang).filter(Vorgang.lead_id == lead.id).first()
        if vorgang is None or not vorgaenge_modul.gehoert_benutzer(session, vorgang, benutzer.id):
            return RedirectResponse("/leads", status_code=303)

    # Kunde ist seit Phase 24 schon per Sync angelegt; Abgleich hier als Fallback
    from app.monday_sync import kunde_fuer_lead
    kunde_fuer_lead(session, lead)
    session.commit()
    # v8: erst die Sparten-Auswahl (Lead-Interessen vorausgewählt); dort sind
    # auch offene Entwürfe des Leads zum Fortsetzen verlinkt
    ziel = f"/erfassung/sparten?lead_id={lead.id}"
    if objekt_id:
        ziel += f"&objekt_id={int(objekt_id)}"
    return RedirectResponse(ziel, status_code=303)
