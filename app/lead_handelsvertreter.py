# Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 109) – Handelsvertreter
# (Diktat G1–G5, Festlegungen F13–F16). Kapselt ALLE Handelsvertreter-Rechte
# an einer Stelle (A-1: Kennzeichen ad_profile.terminiert_selbst statt eigener
# Rolle), baut die Ansicht „Handelsvertreter“ (Gesamtsicht Innendienst/LM/
# Admin bzw. eigene Leads des Vertreters), das HV-Dashboard (F16), die
# Zuweisung/Umverteilung (G3, F13) mit Ausschlussliste (F14) und die Regel
# bei nachträglichem Kanalwechsel (G4, OF-G5).
#
# Rechte-Matrix Handelsvertreter (Hauptrolle aussendienst + Kennzeichen):
#   DARF   eigene Leads sehen (Ansicht + Dashboard, server-seitig gefiltert)
#   DARF   eigene Leads anrufen / Ergebnisse protokollieren (Phase 107, Gate
#          lead_v2.gate → vorgaenge.ad_id = eigene ID)
#   DARF   Kartei eigener Leads bearbeiten (Phase 106)
#   DARF   Termine über Assistent/manuell setzen – nur eigener Kalender
#          (Phase 108 erzwingt nur_ad_id = eigene ID), Terminierung (B8) auslösen
#   DARF   Vorlagen-Mails an eigene Leads senden
#   DARF   eigene Leads an jeden anderen Handelsvertreter umverteilen
#          (Aktivität + Glocke, F13) – nicht entziehen, nicht an Angestellte
#   NICHT  fremde Leads (404), Gesamtsicht, „Standard nachziehen“
#   NICHT  Schnellanlage, Import, Posteingang, Vorlagenpflege, Parametrierung
#          (V1-_gate bzw. lead_modul_sichtbar → 404)
#   NICHT  Preise/EK/DB/Angebotseditor (Middleware wie Außendienst, auth.py)
# Zugriff zentral: ist_hv · eigene_vorgaenge · darf_vorgang · gate.

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import lead_v2
from app import leadmanagement as kern
from app.models import (AdProfil, Benutzer, Kunde, Lead, LeadAktivitaet,
                        LeadQuelle, MondayQuelle, Todo, Vorgang, VotTermin,
                        ANRUF_ERGEBNIS_NAMEN, LEAD_PHASEN_NAMEN,
                        TERMIN_TYP_NAMEN)

# Rechte-Matrix als Daten (für Doku/Abnahme; Reihenfolge = Anzeige)
RECHTE_MATRIX = [
    ("Eigene Leads sehen (Ansicht Handelsvertreter, Dashboard)", True,
     "server-seitig gefiltert: vorgaenge.ad_id bzw. monday leads.benutzer_id"),
    ("Eigene Leads anrufen, Ergebnisse protokollieren", True,
     "POST /lead-management/anruf/{id} (Phase 107, lead_v2.gate)"),
    ("Kartei eigener Leads bearbeiten", True, "Phase 106, lead_v2.gate"),
    ("Termine setzen (Assistent/manuell) – nur eigener Kalender", True,
     "Phase 108 (nur_ad_id = eigene ID)"),
    ("Terminierung (B8) auslösen", True, "Phase 106"),
    ("Vorlagen-Mails senden", True, "nur eigene Leads"),
    ("Umverteilen an andere Handelsvertreter", True,
     "POST /lead-management/handelsvertreter/{id}/zuweisen, Aktivität + Glocke"),
    ("Fremde Leads", False, "404 (lead_v2.gate / darf_vorgang)"),
    ("Gesamtsicht aller Vertreter, Standard nachziehen", False,
     "nur Innendienst/Leadmanagement/Admin (lead_modul_sichtbar)"),
    ("Schnellanlage, Import, Posteingang", False, "V1-_gate → 404"),
    ("Vorlagenpflege, Parametrierung", False, "Middleware/Gate"),
    ("Preise, EK, DB, Angebotseditor", False, "Middleware wie Außendienst"),
]

# Die sechs Handelsvertreter laut Plan G3 (Anzeigename für den Admin-Hinweis
# „Noch nicht als Benutzer angelegt“); Abgleich wortweise über lead_v2._normal.
HV_NAMEN = [("golaschewski", "René Golaschewski"), ("grady", "Simon O'Grady"),
            ("di blasi", "Paolo Di Blasi"), ("lind", "André Lind"),
            ("kinkel", "Ralf Kinkel"), ("leinenbach", "Hartmut Leinenbach")]

OFFENE_PHASEN = ("neu", "in_kontaktierung", "qualifiziert", "zurueckgestellt")
KONTAKT_TYPEN = {"anruf": "Anruf", "mail_aus": "E-Mail", "mail_ein": "E-Mail (Eingang)",
                 "whatsapp": "WhatsApp"}


# --- Rechte ------------------------------------------------------------------------

def ist_hv(session: Session, benutzer) -> bool:
    """Kennzeichen „terminiert selbst“ (A-1) – Hauptrolle aussendienst."""
    return lead_v2.ist_handelsvertreter(session, benutzer)


def gesamtsicht(session: Session, benutzer) -> bool:
    """Innendienst/Leadmanagement/Admin sehen alle Handelsvertreter-Leads."""
    return kern.lead_modul_sichtbar(session, benutzer)


def hv_ids(session: Session) -> set:
    return {b.id for b in lead_v2.handelsvertreter_liste(session)}


def hv_kreis(session: Session) -> dict:
    """Alle Benutzer, die als Handelsvertreter gelten: gekennzeichnete (AD-
    Profil) plus namentlich bekannte Außendienstler ohne Kennzeichen (Rene/
    Simon vor der Migration) – {id: (benutzer, gekennzeichnet)}."""
    kreis = {b.id: (b, True) for b in lead_v2.handelsvertreter_liste(session)}
    for b in session.query(Benutzer).filter(Benutzer.rolle == "aussendienst",
                                            Benutzer.aktiv.is_(True)):
        if b.id not in kreis and lead_v2.ist_handelsvertreter_name(b.name):
            kreis[b.id] = (b, False)
    return kreis


def _monday_lead(session: Session, vorgang: Vorgang) -> Lead | None:
    return session.get(Lead, vorgang.lead_id) if vorgang.lead_id else None


def zustaendiger_id(session: Session, vorgang: Vorgang, lead: Lead | None = None,
                    kreis: dict | None = None) -> int | None:
    """Zuständiger Handelsvertreter eines Vorgangs: vorgaenge.ad_id (A-7);
    bei monday-Leads ohne ad_id die monday-Zuordnung leads.benutzer_id,
    sofern diese Person zum HV-Kreis gehört."""
    if vorgang.ad_id:
        return vorgang.ad_id
    lead = lead if lead is not None else _monday_lead(session, vorgang)
    if lead is not None and lead.benutzer_id:
        kreis = kreis if kreis is not None else hv_kreis(session)
        if lead.benutzer_id in kreis:
            return lead.benutzer_id
    return None


def eigene_vorgaenge(session: Session, benutzer) -> list:
    """Leads des Handelsvertreters: vorgaenge.ad_id = ich, zusätzlich monday-
    Leads mit leads.benutzer_id = ich über vorgaenge.lead_id (noch nicht
    nachgezogen). Reihenfolge: Eingang absteigend."""
    if benutzer is None:
        return []
    treffer = {v.id: v for v in session.query(Vorgang)
               .filter(Vorgang.ad_id == benutzer.id)}
    lead_ids = [l.id for l in session.query(Lead.id)
                .filter(Lead.benutzer_id == benutzer.id)]
    if lead_ids:
        for v in session.query(Vorgang).filter(Vorgang.lead_id.in_(lead_ids)):
            if v.ad_id in (None, benutzer.id):
                treffer.setdefault(v.id, v)
    return sorted(treffer.values(),
                  key=lambda v: v.eingang_am or v.angelegt_am or datetime.min,
                  reverse=True)


def darf_vorgang(session: Session, benutzer, vorgang: Vorgang | None) -> bool:
    """Modul-Sichtbare immer; Handelsvertreter nur eigene Vorgänge (ad_id =
    ich oder monday-Zuordnung = ich, solange kein anderer ad_id trägt)."""
    if vorgang is None:
        return lead_v2.zugriff_erlaubt(session, benutzer, None)
    if lead_v2.zugriff_erlaubt(session, benutzer, vorgang):
        return True
    if not ist_hv(session, benutzer) or vorgang.ad_id:
        return False
    lead = _monday_lead(session, vorgang)
    return bool(lead is not None and lead.benutzer_id == benutzer.id)


def gate(request, session: Session, vorgang: Vorgang | None = None) -> None:
    """404-Gate der HV-Routen: lead_v2.gate (Modul oder Handelsvertreter) plus
    Vorgangsprüfung inkl. monday-Zuordnung."""
    from fastapi import HTTPException
    lead_v2.gate(request, session)
    if vorgang is not None and not darf_vorgang(session, request.state.benutzer, vorgang):
        raise HTTPException(status_code=404)


# --- monday-Sonderregeln (G5, F13) --------------------------------------------------

def _monday_quelle(session: Session, lead: Lead | None) -> MondayQuelle | None:
    if lead is None or not lead.board_id:
        return None
    return (session.query(MondayQuelle)
            .filter(MondayQuelle.board_id == str(lead.board_id)).first())


def _board_name(session: Session, vorgang: Vorgang, lead: Lead | None,
                quelle: MondayQuelle | None) -> str:
    name = (lead.board_name if lead is not None else "") or \
           (quelle.board_name if quelle is not None else "")
    if not name and vorgang.quelle_id:
        lq = session.get(LeadQuelle, vorgang.quelle_id)
        if lq is not None and lq.typ == "monday":
            name = lq.name
    return (name or "").lower()


def rene_benutzer(session: Session):
    """René Golaschewski (Sonderregel „Deals - Rene“): Name enthält
    „golaschewski“, sonst fester_benutzer_id der monday-Quelle „… Rene“."""
    for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True)):
        if "golaschewski" in lead_v2._namensteile(b.name):
            return b
    for q in session.query(MondayQuelle).filter(MondayQuelle.fester_benutzer_id.isnot(None)):
        if "rene" in (q.board_name or "").lower():
            person = session.get(Benutzer, q.fester_benutzer_id)
            if person is not None and person.aktiv:
                return person
    return None


def sonderregel_rene(session: Session, vorgang: Vorgang, lead: Lead | None = None) -> str:
    """Leer = keine Sonderregel; sonst Hinweistext (Dropdown gesperrt)."""
    lead = lead if lead is not None else _monday_lead(session, vorgang)
    if lead is None:
        return ""
    quelle = _monday_quelle(session, lead)
    if (quelle is not None and quelle.fester_benutzer_id) or \
            "rene" in _board_name(session, vorgang, lead, quelle):
        return "Sonderregel monday (Deals - Rene): Verantwortlicher ist immer René Golaschewski."
    return ""


def standard_ziel(session: Session, vorgang: Vorgang, lead: Lead | None = None,
                  kreis: dict | None = None):
    """(benutzer, erzwingen) der Standard-Zuweisung F13 oder (None, False):
    „Deals - Rene“ → René (Sonderregel, erzwingt); monday-Personenzuordnung
    auf einen Handelsvertreter → dieser (monday-Wahrheit, erzwingt);
    „Deals“/„Deals - Simon“ ohne Person → hv_standard_benutzer (Simon,
    Ausschluss greift); Tool-Leads → keine Automatik."""
    lead = lead if lead is not None else _monday_lead(session, vorgang)
    if lead is None:
        return None, False
    quelle = _monday_quelle(session, lead)
    name = _board_name(session, vorgang, lead, quelle)
    if quelle is not None and quelle.fester_benutzer_id:
        person = session.get(Benutzer, quelle.fester_benutzer_id)
        if person is not None and person.aktiv:
            return person, True
    if "rene" in name:
        return rene_benutzer(session), True
    if lead.benutzer_id:
        person = session.get(Benutzer, lead.benutzer_id)
        kreis = kreis if kreis is not None else hv_kreis(session)
        if person is not None and person.aktiv and (
                person.id in kreis or "simon" in name):
            return person, True
        return None, False
    if "deals" in name:
        return lead_v2.hv_standard_benutzer(session), False
    return None, False


def standard_zuweisung(session: Session, vorgang: Vorgang, benutzer=None) -> str:
    """F13: Standard nach monday-Quelle setzen, wenn noch kein ad_id – liefert
    die Meldung von lead_v2.ad_zuweisen oder "" (nichts zu tun)."""
    if vorgang.ad_id:
        return ""
    ziel, erzwingen = standard_ziel(session, vorgang)
    if ziel is None:
        return ""
    text = lead_v2.ad_zuweisen(session, vorgang, ziel.id, benutzer=benutzer,
                               erzwingen=erzwingen)
    _monday_abgleichen(session, vorgang)
    return text


def standard_kandidaten(session: Session) -> list:
    """Bestandsleads (monday) ohne ad_id, für die F13 ein Ziel kennt."""
    treffer = []
    kreis = hv_kreis(session)
    leads = {l.id: l for l in session.query(Lead)}
    for v in session.query(Vorgang).filter(Vorgang.lead_id.isnot(None),
                                           Vorgang.ad_id.is_(None)):
        ziel, _ = standard_ziel(session, v, leads.get(v.lead_id), kreis)
        if ziel is not None:
            treffer.append(v)
    return treffer


def standard_nachziehen(session: Session, benutzer=None) -> int:
    """Aktion „Standard nachziehen“ (Admin/Innendienst) und Hook nach dem
    monday-Sync: alle Kandidaten zuweisen; Anzahl der gesetzten Zuweisungen."""
    anzahl = 0
    for v in standard_kandidaten(session):
        vorher = v.ad_id
        standard_zuweisung(session, v, benutzer=benutzer)
        if v.ad_id and v.ad_id != vorher:
            anzahl += 1
    session.flush()
    return anzahl


def an_standard(session: Session, vorgang: Vorgang, benutzer=None) -> str:
    """Button „An Standard (Simon) geben“ – auch für Tool-Leads (manuell)."""
    standard = lead_v2.hv_standard_benutzer(session)
    if standard is None:
        return "Kein Standard-Handelsvertreter hinterlegt (Parameter hv_standard_benutzer)."
    return zuweisen(session, vorgang, standard.id, benutzer=benutzer)


# --- Zuweisung / Umverteilung (G3, F13, F14) -----------------------------------------

def _monday_abgleichen(session: Session, vorgang: Vorgang) -> None:
    """Zwei Wahrheiten vermeiden (OF-G2/OF-G3): Tool-Zuweisung an einem
    gesyncten Lead schreibt leads.benutzer_id + benutzer_manuell."""
    lead = _monday_lead(session, vorgang)
    if lead is None or not vorgang.ad_id or lead.benutzer_id == vorgang.ad_id:
        return
    lead.benutzer_id = vorgang.ad_id
    lead.benutzer_manuell = True


def zuweisen(session: Session, vorgang: Vorgang, ad_id, benutzer=None,
             erzwingen: bool = False) -> str:
    """Zuweisung/Umverteilung IMMER hierüber: Sonderregel Deals - Rene sperrt,
    dann lead_v2.ad_zuweisen (Ausschluss F14 greift bei erzwingen=False –
    Innendienst/Admin erzwingen in der HV-Ansicht nicht), danach monday-
    Abgleich. Liefert die Meldung."""
    # Robustheit: nur leer (= entziehen) oder eine Benutzer-ID – alles andere
    # (manipuliertes Formular) als Meldung statt ValueError/500
    if ad_id in (None, "", 0):
        ad_id = None
    elif str(ad_id).strip().isdigit():
        ad_id = int(str(ad_id).strip())
    else:
        return "Nicht möglich: ungültige Auswahl für den Vertreter."
    grund = sonderregel_rene(session, vorgang)
    if grund:
        rene = rene_benutzer(session)
        if not (rene is not None and ad_id == rene.id):
            return "Nicht möglich: " + grund
    text = lead_v2.ad_zuweisen(session, vorgang, ad_id, benutzer=benutzer,
                               erzwingen=erzwingen)
    _monday_abgleichen(session, vorgang)
    session.flush()
    return text


def dropdown_sperre(session: Session, vorgang: Vorgang, kunde: Kunde | None = None,
                    lead: Lead | None = None) -> tuple:
    """(sperrgrund, kurztext) für das Zuweisungs-Dropdown: Sonderregel monday
    oder Ausschlussliste – leer = frei wählbar."""
    grund = sonderregel_rene(session, vorgang, lead)
    if grund:
        return grund, "Sonderregel monday"
    grund = lead_v2.hv_ausgeschlossen(session, vorgang, kunde)
    if grund:
        return grund, "nur Innendienst"
    return "", ""


# --- Kanalwechsel auf Ausschlusskanal (G4, OF-G5) -----------------------------------

def _leitung_ids(session: Session) -> list:
    return [b.id for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
            if b.rolle == "admin" or b.hat_rolle("leadmanagement")]


def kanal_hinweis(session: Session, vorgang: Vorgang, kunde: Kunde | None = None,
                  ids_hv: set | None = None, grund: str | None = None) -> str:
    """Nur lesen: roter Hinweis, wenn ein Handelsvertreter zugewiesen ist und
    Kanal/Quelle inzwischen auf der Ausschlussliste stehen. ids_hv/grund
    optional vorberechnet (Tabellen mit vielen Zeilen)."""
    if not vorgang.ad_id:
        return ""
    if ids_hv is not None:
        if vorgang.ad_id not in ids_hv:
            return ""
        hv = session.get(Benutzer, vorgang.ad_id)
    else:
        hv = session.get(Benutzer, vorgang.ad_id)
        if hv is None or not ist_hv(session, hv):
            return ""
    if hv is None:
        return ""
    if grund is None:
        grund = lead_v2.hv_ausgeschlossen(session, vorgang, kunde)
    if not grund:
        return ""
    return f"Ausschlusskanal: {grund} Zuweisung an {hv.name} bleibt bis zur manuellen Rücknahme."


def kanalwechsel_pruefen(session: Session, vorgang: Vorgang, benutzer=None) -> str:
    """Nach einer Kanal-/Quellenänderung aufrufen (Kartei Phase 106, Leads VOT
    Kanal setzen): zugewiesener Handelsvertreter + Ausschlusskanal → Aktivität
    + Glocke an leadmanager_id (sonst Leitung); die Zuweisung bleibt bis zur
    manuellen Rücknahme (Annahme OF-G5). Liefert den Hinweistext oder "".
    Kein Doppelalarm: nur einmal je Zuweisung."""
    hinweis = kanal_hinweis(session, vorgang)
    if not hinweis:
        return ""
    letzter_hinweis = (session.query(LeadAktivitaet)
                       .filter(LeadAktivitaet.vorgang_id == vorgang.id,
                               LeadAktivitaet.text.like("Ausschlusskanal:%"))
                       .order_by(LeadAktivitaet.zeitpunkt.desc(), LeadAktivitaet.id.desc())
                       .first())
    letzte_zuweisung = (session.query(LeadAktivitaet)
                        .filter(LeadAktivitaet.vorgang_id == vorgang.id,
                                LeadAktivitaet.text.like("Zugewiesen an %"))
                        .order_by(LeadAktivitaet.zeitpunkt.desc(), LeadAktivitaet.id.desc())
                        .first())
    if letzter_hinweis is not None and (
            letzte_zuweisung is None or letzter_hinweis.id > letzte_zuweisung.id):
        return hinweis
    kern.aktivitaet(session, vorgang.id, "status", hinweis, benutzer=benutzer)
    kunde = session.get(Kunde, vorgang.kunde_id)
    hv = session.get(Benutzer, vorgang.ad_id)
    ziele = [vorgang.leadmanager_id] if vorgang.leadmanager_id else _leitung_ids(session)
    kern.benachrichtigen(session, ziele,
                         f"Ausschlusskanal bei Handelsvertreter-Lead: "
                         f"{kunde.anzeige_name if kunde else '?'} – zugewiesen an "
                         f"{hv.name if hv else '?'}, bitte prüfen",
                         f"/lead-management/lead/{vorgang.id}")
    session.flush()
    return hinweis


# --- Benutzerabgleich (G3/F15) --------------------------------------------------------

def benutzer_abgleich(session: Session) -> dict:
    """Admin-Hinweis: welche der sechs Handelsvertreter fehlen als Benutzer,
    welche sind da, aber ohne Kennzeichen am AD-Profil."""
    alle = session.query(Benutzer).all()
    profile = {p.benutzer_id: p for p in session.query(AdProfil)}
    fehlen, ohne_kennzeichen = [], []
    for key, anzeige in HV_NAMEN:
        woerter = set(key.split())
        treffer = [b for b in alle if lead_v2.ist_handelsvertreter_name(b.name)
                   and woerter <= lead_v2._namensteile(b.name)]
        if not treffer:
            fehlen.append(anzeige)
            continue
        for b in treffer:
            p = profile.get(b.id)
            if b.aktiv and b.rolle == "aussendienst" and not (p and p.terminiert_selbst):
                ohne_kennzeichen.append(b.name)
    return {"fehlen": fehlen, "ohne_kennzeichen": ohne_kennzeichen}


# --- Ansicht (G1) ---------------------------------------------------------------------

def filter_aus_query(q, gesamt: bool) -> dict:
    def _int(name):
        wert = (q.get(name) or "").strip()
        return int(wert) if wert.isdigit() else None
    return {"vertreter": _int("vertreter") if gesamt else None,
            "status": (q.get("status") or "").strip(),
            "kanal": (q.get("kanal") or "").strip(),
            "q": (q.get("q") or "").strip(),
            "offen": (q.get("offen") or "") == "1"}


def _kanal_farben(session: Session) -> dict:
    try:
        werte = json.loads(kern.parameter_holen(session, "kanal_farben", "") or "{}")
    except ValueError:
        werte = {}
    return {str(k).strip().lower(): str(v) for k, v in werte.items()} if isinstance(werte, dict) else {}


def _hex(farbe: str) -> str:
    f = (farbe or "").strip()
    return f if len(f) == 7 and f.startswith("#") else ""


def zeilen_bauen(session: Session, vorgaenge: list, kreis: dict | None = None) -> list:
    """Zeilen wie im Hauptboard (A3-Pflichtspalten in Kurzform): Kunde, Status
    (Blatt Status: Label + Farbe), Kanal, Versuche, letzter Kontakt, Eingang,
    Ort, Interessen, Telefon, Termin, Vertreter + Sperren/Hinweise."""
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    kreis = kreis if kreis is not None else hv_kreis(session)
    ids = [v.id for v in vorgaenge]
    if not ids:
        return []
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({v.kunde_id for v in vorgaenge}))}
    quellen = {q.id: q for q in session.query(LeadQuelle)}
    benutzer_alle = {b.id: b for b in session.query(Benutzer)}
    leads = {l.id: l for l in session.query(Lead)
             .filter(Lead.id.in_({v.lead_id for v in vorgaenge if v.lead_id} or {0}))}
    termine: dict = {}
    for t in (session.query(VotTermin)
              .filter(VotTermin.vorgang_id.in_(ids),
                      VotTermin.status.in_(("geplant", "bestaetigt")))
              .order_by(VotTermin.beginn)):
        termine.setdefault(t.vorgang_id, t)
    kontakte: dict = {}
    for a in (session.query(LeadAktivitaet)
              .filter(LeadAktivitaet.vorgang_id.in_(ids),
                      LeadAktivitaet.typ.in_(tuple(KONTAKT_TYPEN)))
              .order_by(LeadAktivitaet.zeitpunkt.desc(), LeadAktivitaet.id.desc())):
        kontakte.setdefault(a.vorgang_id, a)
    farben = _kanal_farben(session)
    ids_hv = {b for b, (_, gekennzeichnet) in kreis.items() if gekennzeichnet}
    zeilen = []
    for v in vorgaenge:
        kunde = kunden.get(v.kunde_id)
        if kunde is None:
            continue
        lead = leads.get(v.lead_id) if v.lead_id else None
        phase = v.lead_phase or "neu"
        zeile = logik.status_zeile(phase)
        hv_id = zustaendiger_id(session, v, lead, kreis)
        hv = benutzer_alle.get(hv_id) if hv_id else None
        # Ausschlussgrund einmal je Zeile (Sperre des Dropdowns + roter Hinweis)
        aus_grund = lead_v2.hv_ausgeschlossen(session, v, kunde)
        sperre = sonderregel_rene(session, v, lead)
        sperre_kurz = "Sonderregel monday" if sperre else ""
        if not sperre and aus_grund:
            sperre, sperre_kurz = aus_grund, "nur Innendienst"
        kontakt = kontakte.get(v.id)
        termin = termine.get(v.id)
        quelle = quellen.get(v.quelle_id)
        kanal = (kunde.vertriebskanal or "").strip()
        zeilen.append({
            "vorgang": v, "kunde": kunde, "lead": lead,
            "status_label": zeile.label if zeile else LEAD_PHASEN_NAMEN.get(phase, phase),
            "status_farbe": _hex(zeile.farbe) if zeile else "",
            "kanal": kanal, "kanal_farbe": _hex(farben.get(kanal.lower(), "")),
            "sparten": [s.strip() for s in (kunde.interesse or "").split(",") if s.strip()],
            "kontakt": kontakt,
            "kontakt_text": (f"{kontakt.zeitpunkt.strftime('%d.%m. %H:%M')} · "
                             f"{ANRUF_ERGEBNIS_NAMEN.get(kontakt.ergebnis, KONTAKT_TYPEN.get(kontakt.typ, kontakt.typ))}"
                             if kontakt is not None else ""),
            "eingang": v.eingang_am or v.angelegt_am,
            "termin": termin,
            "termin_text": (f"{termin.beginn.strftime('%d.%m. %H:%M')} · "
                            f"{TERMIN_TYP_NAMEN.get(termin.typ, termin.typ)}"
                            + (f" ({benutzer_alle[termin.ad_id].name})"
                               if termin.ad_id in benutzer_alle and termin.ad_id != hv_id else "")
                            if termin is not None and termin.beginn else ""),
            "hv": hv, "hv_id": hv_id,
            "aus_monday": bool(hv_id and not v.ad_id),
            "sperre": sperre, "sperre_kurz": sperre_kurz,
            "kanal_hinweis": kanal_hinweis(session, v, kunde, ids_hv=ids_hv, grund=aus_grund),
            "quelle": quelle, "quelle_gruppe": kern.quelle_gruppe(quelle),
            "offen": phase in OFFENE_PHASEN,
            "wiedervorlage": v.naechste_aktion_am or v.wiedervorlage_am,
        })
    return zeilen


def zeilen_filtern(zeilen: list, f: dict) -> list:
    treffer = []
    suche = (f.get("q") or "").lower()
    for z in zeilen:
        if f.get("vertreter") and z["hv_id"] != f["vertreter"]:
            continue
        if f.get("status") and (z["vorgang"].lead_phase or "neu") != f["status"]:
            continue
        if f.get("kanal") and z["kanal"].lower() != f["kanal"].lower():
            continue
        if f.get("offen") and not z["offen"]:
            continue
        if suche:
            k = z["kunde"]
            heuhaufen = " ".join((k.vorname or "", k.nachname or "", k.firma or "",
                                  k.ort or "", k.plz or "", k.telefon or "",
                                  k.email or "")).lower()
            if suche not in heuhaufen and suche.replace(" ", "") not in \
                    kern.telefon_normalisieren(k.telefon or ""):
                continue
        treffer.append(z)
    return treffer


def alle_hv_vorgaenge(session: Session, kreis: dict | None = None) -> list:
    """Gesamtsicht: alle Vorgänge mit Handelsvertreter (ad_id im HV-Kreis
    oder monday-Zuordnung auf einen HV ohne ad_id)."""
    kreis = kreis if kreis is not None else hv_kreis(session)
    if not kreis:
        return []
    treffer = {v.id: v for v in session.query(Vorgang)
               .filter(Vorgang.ad_id.in_(list(kreis)))}
    lead_ids = [l.id for l in session.query(Lead.id).filter(Lead.benutzer_id.in_(list(kreis)))]
    if lead_ids:
        for v in session.query(Vorgang).filter(Vorgang.lead_id.in_(lead_ids),
                                               Vorgang.ad_id.is_(None)):
            treffer.setdefault(v.id, v)
    return sorted(treffer.values(),
                  key=lambda v: v.eingang_am or v.angelegt_am or datetime.min,
                  reverse=True)


def gruppieren(zeilen: list, kreis: dict) -> list:
    """Je Vertreter eine einklappbare Gruppe (Reihenfolge: Name), Zähler =
    Zeilen, offene Zeilen gesondert."""
    gruppen = {}
    for z in zeilen:
        gruppen.setdefault(z["hv_id"], []).append(z)
    ergebnis = []
    reihenfolge = sorted(kreis.values(), key=lambda t: t[0].name.lower())
    for benutzer, gekennzeichnet in reihenfolge:
        liste = gruppen.pop(benutzer.id, [])
        ergebnis.append({"key": benutzer.id, "name": benutzer.name, "benutzer": benutzer,
                         "gekennzeichnet": gekennzeichnet, "zeilen": liste,
                         "offen": sum(1 for z in liste if z["offen"])})
    for hv_id, liste in gruppen.items():
        name = liste[0]["hv"].name if liste[0]["hv"] else "Nicht zugewiesen"
        ergebnis.append({"key": hv_id or 0, "name": name, "benutzer": liste[0]["hv"],
                         "gekennzeichnet": False, "zeilen": liste,
                         "offen": sum(1 for z in liste if z["offen"])})
    return ergebnis


HV_ZEILEN_KEYS = ("hv", "hv_id", "aus_monday", "sperre", "sperre_kurz", "kanal_hinweis",
                  "offen", "wiedervorlage")


def tabelle_makro_vorhanden() -> bool:
    """Gibt es das Tabellen-Makro leadmanagement/_tabelle.html (Phase 105)?"""
    try:
        from app.templating import templates
        templates.env.get_template("leadmanagement/_tabelle.html")
        return True
    except Exception:
        return False


def zeilen_phase105(session: Session, benutzer) -> dict | None:
    """Zeilen des Hauptboards (Phase 105, app/lead_boards.board_zeilen) je
    Vorgangs-ID – None, wenn das Modul fehlt oder scheitert (Rückfall auf die
    eigene Tabelle). Für Handelsvertreter filtert board_zeilen bereits auf
    ad_id = eigene ID."""
    try:
        from app import lead_boards
    except ImportError:
        return None
    try:
        index = {}
        for board in ("hauptboard", "terminiert"):
            daten = lead_boards.board_zeilen(session, benutzer, board, {"archiv": True})
            for g in daten["gruppen"]:
                for z in g["zeilen"]:
                    index[z["vorgang"].id] = z
        return index
    except Exception:
        return None


def zeilen_zusammenfuehren(zeilen: list, index: dict | None) -> list:
    """Phase-105-Zeile als Basis (gleiche Darstellung wie das Hauptboard),
    HV-Felder dieser Phase obendrauf; ohne Treffer bleibt die eigene Zeile."""
    if not index:
        return zeilen
    ergebnis = []
    for z in zeilen:
        basis = index.get(z["vorgang"].id)
        if basis is None:
            ergebnis.append(z)
            continue
        neu = dict(basis)
        neu.update({k: z[k] for k in HV_ZEILEN_KEYS if k in z})
        neu["phase105"] = True
        ergebnis.append(neu)
    return ergebnis


def ansicht(session: Session, benutzer, f: dict, mit_phase105: bool = True) -> dict:
    """Daten der Seite /lead-management/handelsvertreter: Gesamtsicht (ID/LM/
    Admin) gruppiert je Vertreter oder – für den Handelsvertreter – nur die
    eigenen Leads (server-seitig). Zeilen kommen, wenn vorhanden, aus dem
    Hauptboard (Phase 105, Makro _tabelle.html), sonst aus zeilen_bauen."""
    gesamt = gesamtsicht(session, benutzer)
    kreis = hv_kreis(session)
    hv_liste = lead_v2.handelsvertreter_liste(session)
    if gesamt:
        vorgaenge = alle_hv_vorgaenge(session, kreis)
    else:
        vorgaenge = eigene_vorgaenge(session, benutzer)
    zeilen = zeilen_bauen(session, vorgaenge, kreis)
    index = None
    phase105 = bool(mit_phase105 and tabelle_makro_vorhanden())
    if phase105:
        index = zeilen_phase105(session, benutzer)
        phase105 = index is not None
        zeilen = zeilen_zusammenfuehren(zeilen, index)
    gefiltert = zeilen_filtern(zeilen, f)
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    status_optionen = [(z.phase, z.label) for z in logik.status_zeilen] or \
        list(LEAD_PHASEN_NAMEN.items())
    kanal_optionen = sorted({z["kanal"] for z in zeilen if z["kanal"]}, key=str.lower)
    jetzt = datetime.now()
    daten = {"gesamt": gesamt, "hv_liste": hv_liste, "kreis": kreis,
             "zeilen": gefiltert, "anzahl_gesamt": len(zeilen),
             "status_optionen": status_optionen, "kanal_optionen": kanal_optionen,
             "standard": lead_v2.hv_standard_benutzer(session),
             "filter_werte": f, "jetzt": jetzt, "phase105": phase105,
             # Kontext für die Zellen-Makros aus _tabelle.html (nur lesen –
             # die Vertreter-Spalte kommt aus hv_zuweisung.html)
             "ctx": {"nur_lesen": True, "board": "hauptboard", "jetzt": jetzt,
                     "heute": jetzt.date(), "hv": not gesamt, "sammel": False,
                     "versuche_max": kern.versuche_max(session)}}
    if gesamt:
        daten["gruppen"] = gruppieren(gefiltert, kreis)
        daten["hinweise"] = benutzer_abgleich(session)
        # F13: Bestandsleads aus monday ohne Vertreter – eigene, zugeklappte
        # Gruppe mit Button „An Standard geben“ je Lead + Sammelaktion
        kandidaten = standard_kandidaten(session)
        daten["standard_offen"] = len(kandidaten)
        if kandidaten and not f.get("vertreter"):
            k_zeilen = zeilen_filtern(
                zeilen_zusammenfuehren(zeilen_bauen(session, kandidaten, kreis), index), f)
            daten["gruppen"].append({
                "key": "standard", "name": "Ohne Vertreter (monday-Bestand)",
                "benutzer": None, "gekennzeichnet": True, "zeilen": k_zeilen,
                "offen": sum(1 for z in k_zeilen if z["offen"]), "aufgeklappt": False,
                "erkl": "Standardregel F13 greift über „Standard nachziehen“ oder je Lead"})
        daten["dashboard"] = None
    else:
        daten["gruppen"] = [{"key": benutzer.id, "name": "Meine Leads", "benutzer": benutzer,
                             "gekennzeichnet": True, "zeilen": gefiltert,
                             "offen": sum(1 for z in gefiltert if z["offen"])}]
        daten["hinweise"] = None
        daten["standard_offen"] = 0
        daten["dashboard"] = dashboard_daten(session, benutzer)
    return daten


# --- Dashboard (F16) ------------------------------------------------------------------

def dashboard_daten(session: Session, benutzer) -> dict:
    """Persönliches HV-Dashboard: fällige/kommende Wiedervorlagen, eigene
    Termine der nächsten 7 Tage, offene Leads, offene To-Dos."""
    jetzt = datetime.now()
    horizont = jetzt + timedelta(days=7)
    eigene = eigene_vorgaenge(session, benutzer)
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({v.kunde_id for v in eigene} or {0}))}

    def _wv(v):
        return v.naechste_aktion_am or v.wiedervorlage_am

    faellig = sorted([v for v in eigene if _wv(v) and _wv(v) <= jetzt
                      and (v.lead_phase or "neu") in OFFENE_PHASEN], key=_wv)
    kommend = sorted([v for v in eigene if _wv(v) and jetzt < _wv(v) <= horizont
                      and (v.lead_phase or "neu") in OFFENE_PHASEN], key=_wv)
    offen = [v for v in eigene if (v.lead_phase or "neu") in OFFENE_PHASEN]
    termine = (session.query(VotTermin)
               .filter(VotTermin.ad_id == benutzer.id,
                       VotTermin.status.in_(("geplant", "bestaetigt")),
                       VotTermin.beginn >= jetzt - timedelta(hours=2),
                       VotTermin.beginn <= horizont)
               .order_by(VotTermin.beginn).all())
    termin_kunden = {}
    for t in termine:
        v = session.get(Vorgang, t.vorgang_id)
        termin_kunden[t.id] = (v, session.get(Kunde, v.kunde_id) if v else None)
    todos = (session.query(Todo)
             .filter(Todo.an_benutzer_id == benutzer.id, Todo.status == "offen")
             .order_by(Todo.faellig_am.is_(None), Todo.faellig_am).limit(20).all())
    return {
        "jetzt": jetzt, "benutzer": benutzer,
        "kacheln": {"faellig": len(faellig), "kommend": len(kommend),
                    "termine": len(termine), "offen": len(offen), "todos": len(todos)},
        "faellig": [{"vorgang": v, "kunde": kunden.get(v.kunde_id), "wann": _wv(v)}
                    for v in faellig[:15]],
        "kommend": [{"vorgang": v, "kunde": kunden.get(v.kunde_id), "wann": _wv(v)}
                    for v in kommend[:15]],
        "termine": [{"termin": t, "vorgang": termin_kunden[t.id][0],
                     "kunde": termin_kunden[t.id][1],
                     # Terminart aus der Konstante (A-2), nicht hart im Template
                     "typ_text": TERMIN_TYP_NAMEN.get(t.typ or "vot", t.typ or "Vor Ort")}
                    for t in termine],
        "offen": [{"vorgang": v, "kunde": kunden.get(v.kunde_id),
                   "eingang": v.eingang_am or v.angelegt_am} for v in offen[:15]],
        "todos": todos,
    }
