# Lead-Management V1 (v12, PLAN_LEAD_V1 Phasen 73-82) – Kernmodul.
# Lead = Vorgang (v10). Das gesamte Modul liegt hinter dem Demo-Schalter
# lead_freigabe_modus (admin = nur Admins, server-seitig; 404 für andere).
# monday-Sync und -Rückspielung bleiben unangetastet – dieses Modul liest die
# gesyncten Vorgänge nur mit und leitet ihre Lead-Phase ab.

import json
import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (Angebot, Benutzer, Erfassung, Kampagne, Kunde, Lead,
                        LeadAktivitaet, LeadParameter, LeadQualifizierung,
                        LeadQuelle, Vorgang, VotTermin,
                        LEAD_PHASEN_MANUELL)

# Startwerte der Parametrierung (Phase 73); Andreas passt sie später an
PARAMETER_START = {
    "lead_freigabe_modus": "admin",
    "mail_modus": "protokoll",
    "mail_testadresse": "",
    "parser_modus": "aus",
    "kalender_sync": "aus",
    "kalender_testpostfach": "",
    "routing_anbieter": "luftlinie",
    "ors_api_key": "",
    "google_api_key": "",
    "sla_gruen_min": "30",
    "sla_gelb_min": "60",
    "vorschlag_horizont_tage": "14",
    "vorschlag_raster_min": "30",
    "absender_postfach": "leads@friondo.de",
    "loeschlauf": "aus",
    "loeschfrist_monate": "12",
    "kerngebiet_plz": "",
    "zuweisung_lm": "round_robin",
    "arbeitszeit_lm": "08:00-17:00",
    "demo_badge_text": "Demo · Coming soon",
    "firmen_adresse": "Duisburg",
    # Erwartungswerte je Sparte (brutto, Cent) + Phasen-Quoten (Phase 79/80)
    "erwartungswert_WP": "3000000",
    "erwartungswert_PV": "2000000",
    "erwartungswert_KL": "800000",
    "erwartungswert_WB": "250000",
    "quote_neu": "5", "quote_in_kontaktierung": "8", "quote_qualifiziert": "15",
    "quote_terminiert": "30", "quote_erfasst": "40", "quote_angebot": "50",
}


def parameter_holen(session: Session, name: str, standard: str = "") -> str:
    zeile = (session.query(LeadParameter)
             .filter(LeadParameter.name == name).first())
    if zeile is not None:
        return zeile.wert
    return PARAMETER_START.get(name, standard)


def parameter_setzen(session: Session, name: str, wert: str) -> None:
    zeile = (session.query(LeadParameter)
             .filter(LeadParameter.name == name).first())
    if zeile is None:
        session.add(LeadParameter(name=name, wert=wert))
        session.flush()   # autoflush ist aus – sofort abfragbar
    else:
        zeile.wert = wert


def parameter_vorbelegen(session: Session) -> int:
    """Fehlende Startwerte anlegen (idempotent, migrate.py)."""
    vorhanden = {p.name for p in session.query(LeadParameter)}
    neu = 0
    for name, wert in PARAMETER_START.items():
        if name not in vorhanden:
            session.add(LeadParameter(name=name, wert=wert))
            neu += 1
    session.flush()
    return neu


# --- Demo-Schalter -----------------------------------------------------------------

def freigabe_modus(session: Session) -> str:
    wert = parameter_holen(session, "lead_freigabe_modus", "admin").strip().lower()
    return wert if wert in ("admin", "alle") else "admin"


def demo_aktiv(session: Session) -> bool:
    return freigabe_modus(session) == "admin"


def lead_modul_sichtbar(session: Session, benutzer) -> bool:
    """Server-seitige Sichtbarkeit des gesamten Moduls (Phase 73): im
    Demo-Modus nur Admins; bei 'alle' zusätzlich Innendienst/Leadmanagement."""
    if benutzer is None:
        return False
    if benutzer.rolle == "admin":
        return True
    if freigabe_modus(session) != "alle":
        return False
    return (benutzer.rolle in ("innendienst",)
            or benutzer.hat_rolle("leadmanagement"))


# --- Demo-Kennzeichen (Leitplanke 3: nirgends außerhalb des Moduls sichtbar) --------

def demo_vorgang_ids(session: Session) -> set[int]:
    return {v.id for v in session.query(Vorgang.id).filter(Vorgang.demo.is_(True))}


def demo_kunden_ids(session: Session) -> set[int]:
    """Kunden, die NUR an Demo-Vorgängen hängen – die bestehende Kundenliste
    blendet sie aus (ohne_demo)."""
    demo = {v.kunde_id for v in session.query(Vorgang)
            .filter(Vorgang.demo.is_(True))}
    if not demo:
        return set()
    echt = {v.kunde_id for v in session.query(Vorgang)
            .filter(Vorgang.kunde_id.in_(demo), Vorgang.demo.is_(False))}
    return demo - echt


def ohne_demo(query, spalte=None):
    """Bestehende Vorgangs-Abfragen um Demo-Vorgänge bereinigen (Phase 73):
    ohne_demo(session.query(Vorgang)) bzw. mit expliziter demo-Spalte."""
    spalte = spalte if spalte is not None else Vorgang.demo
    return query.filter((spalte.is_(False)) | (spalte.is_(None)))


# --- Aktivitäten / Benachrichtigung -------------------------------------------------

def aktivitaet(session: Session, vorgang_id: int, typ: str, text: str,
               benutzer=None, ergebnis: str | None = None,
               dauer_sek: int | None = None,
               naechste_aktion_am: datetime | None = None) -> LeadAktivitaet:
    eintrag = LeadAktivitaet(
        vorgang_id=vorgang_id, typ=typ, ergebnis=ergebnis,
        text=(text or "").strip()[:4000], dauer_sek=dauer_sek,
        benutzer_id=benutzer.id if benutzer else None,
        erstellt_von=benutzer.id if benutzer else None,
        naechste_aktion_am=naechste_aktion_am)
    session.add(eintrag)
    session.flush()
    return eintrag


def benachrichtigen(session: Session, benutzer_ids, text: str, link: str) -> None:
    """Glocken-Einträge mit art='lead' (Demo-Filter in app/benachrichtigungen)."""
    from app import projektierung as kern
    kern.benachrichtigen(session, benutzer_ids, text, link, art="lead")


def leadmanager_benutzer(session: Session) -> list[Benutzer]:
    return [b for b in session.query(Benutzer)
            .filter(Benutzer.aktiv.is_(True)).order_by(Benutzer.id)
            if b.lm_aktiv and (b.hat_rolle("leadmanagement")
                               or b.rolle in ("admin", "innendienst"))]


def naechster_leadmanager(session: Session, aktueller_benutzer=None) -> int | None:
    """Round-Robin über lm_aktiv-Benutzer (Zähler in lead_parameter); ohne
    aktive Leadmanager fällt die Zuweisung auf den Anleger (Admin) zurück."""
    kandidaten = leadmanager_benutzer(session)
    if not kandidaten:
        return aktueller_benutzer.id if aktueller_benutzer else None
    try:
        zeiger = int(parameter_holen(session, "rr_zeiger", "0"))
    except ValueError:
        zeiger = 0
    gewaehlt = kandidaten[zeiger % len(kandidaten)]
    parameter_setzen(session, "rr_zeiger", str((zeiger + 1) % len(kandidaten)))
    return gewaehlt.id


# --- SLA -----------------------------------------------------------------------------

def _arbeitszeit(session: Session) -> tuple[int, int]:
    """(startminute, endminute) aus arbeitszeit_lm '08:00-17:00'."""
    roh = parameter_holen(session, "arbeitszeit_lm", "08:00-17:00")
    treffer = re.match(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$", roh.strip())
    if not treffer:
        return 8 * 60, 17 * 60
    von = int(treffer.group(1)) * 60 + int(treffer.group(2))
    bis = int(treffer.group(3)) * 60 + int(treffer.group(4))
    return (von, bis) if von < bis else (8 * 60, 17 * 60)


def arbeitsminuten(session: Session, von: datetime, bis: datetime) -> int:
    """Minuten zwischen zwei Zeitpunkten innerhalb der LM-Arbeitszeit (Mo-Fr)."""
    if bis <= von:
        return 0
    start_min, ende_min = _arbeitszeit(session)
    minuten = 0
    tag = von.replace(hour=0, minute=0, second=0, microsecond=0)
    while tag <= bis:
        if tag.weekday() < 5:   # Mo-Fr
            fenster_von = tag + timedelta(minutes=start_min)
            fenster_bis = tag + timedelta(minutes=ende_min)
            von_eff = max(von, fenster_von)
            bis_eff = min(bis, fenster_bis)
            if bis_eff > von_eff:
                minuten += int((bis_eff - von_eff).total_seconds() // 60)
        tag += timedelta(days=1)
    return minuten


def sla_status(session: Session, vorgang: Vorgang,
               jetzt: datetime | None = None) -> dict:
    """Berechnet, nie gespeichert (Phase 75): Minuten seit Eingang innerhalb
    der Arbeitszeit bis zum ersten Versuch."""
    jetzt = jetzt or datetime.now()
    if vorgang.eingang_am is None:
        return {"farbe": "", "minuten": 0, "erfuellt": False}
    try:
        gruen = int(parameter_holen(session, "sla_gruen_min", "30"))
        gelb = int(parameter_holen(session, "sla_gelb_min", "60"))
    except ValueError:
        gruen, gelb = 30, 60
    ende = vorgang.erstkontakt_am or jetzt
    minuten = arbeitsminuten(session, vorgang.eingang_am, ende)
    if vorgang.erstkontakt_am is not None:
        return {"farbe": "erfuellt", "minuten": minuten, "erfuellt": True}
    farbe = "gruen" if minuten < gruen else ("gelb" if minuten < gelb else "rot")
    return {"farbe": farbe, "minuten": minuten, "erfuellt": False}


# --- monday-Quelle + abgeleitete Lead-Phase (Phase 73) -------------------------------

def monday_quelle(session: Session, board_id: str, board_name: str = "") -> LeadQuelle:
    """Automatisch angelegte Quelle monday_<board> (Typ monday); der Kanal
    lebt wie bisher am Kunden/Lead (kein Board-Kanal vorhanden)."""
    key = f"monday_{board_id or 'unbekannt'}"
    quelle = session.query(LeadQuelle).filter(LeadQuelle.key == key).first()
    if quelle is None:
        quelle = LeadQuelle(key=key, name=f"monday {board_name or board_id}",
                            typ="monday", aktiv=True)
        session.add(quelle)
        session.flush()
    return quelle


def lead_phase_berechnen(session: Session, vorgang: Vorgang) -> str:
    """Abgeleitete Lead-Phase (schreibt NUR vorgaenge.lead_phase, nie nach
    monday). Manuelle Seitenzustände haben Vorrang, bis sie aufgehoben werden."""
    if vorgang.lead_phase in LEAD_PHASEN_MANUELL:
        return vorgang.lead_phase
    angebote = (session.query(Angebot)
                .filter(Angebot.vorgang_id == vorgang.id,
                        Angebot.archiviert.is_(False)).all())
    phase = "neu"
    if any(a.status == "Angenommen" for a in angebote):
        phase = "gewonnen"
    elif angebote and all(a.status in ("Abgelehnt", "Überholt") for a in angebote):
        phase = "verloren"
    elif any(a.status in ("Versendet", "Versendet (extern)") for a in angebote):
        phase = "angebot"
    elif (session.query(Erfassung)
          .filter(Erfassung.vorgang_id == vorgang.id).count()):
        phase = "erfasst"
    else:
        lead = session.get(Lead, vorgang.lead_id) if vorgang.lead_id else None
        termin_aktiv = (session.query(VotTermin)
                        .filter(VotTermin.vorgang_id == vorgang.id,
                                VotTermin.status.in_(("geplant", "bestaetigt")))
                        .count())
        if (lead is not None and lead.vot_datum is not None) or termin_aktiv:
            phase = "terminiert"
        elif (session.query(LeadQualifizierung)
              .filter(LeadQualifizierung.vorgang_id == vorgang.id,
                      LeadQualifizierung.abgeschlossen_am.isnot(None)).count()):
            phase = "qualifiziert"
        elif (vorgang.versuch_nr or 0) >= 1:
            phase = "in_kontaktierung"
    vorgang.lead_phase = phase
    return phase


def phase_neu_berechnen(session: Session, vorgang_id: int | None) -> None:
    """Leichter Hook für Statuswechsel an Erfassung/Angebot (Plan 73, Punkt 9);
    Fehler blockieren den Bestand nie."""
    if not vorgang_id:
        return
    try:
        vorgang = session.get(Vorgang, vorgang_id)
        if vorgang is not None:
            lead_phase_berechnen(session, vorgang)
    except Exception:
        pass


def nach_sync(session: Session) -> int:
    """Nach jedem monday-Sync-Lauf: gesyncte Vorgänge bekommen Eingangsdaten
    (einmalig) und eine plausible Lead-Phase. Rein lesend gegenüber monday."""
    anzahl = 0
    leads = {l.id: l for l in session.query(Lead)}
    for vorgang in session.query(Vorgang).filter(Vorgang.lead_id.isnot(None)):
        lead = leads.get(vorgang.lead_id)
        if lead is None:
            continue
        if not vorgang.eingang_art:
            vorgang.eingang_art = "monday"
            vorgang.eingang_am = vorgang.eingang_am or vorgang.angelegt_am
            quelle = monday_quelle(session, lead.board_id, lead.board_name)
            vorgang.quelle_id = vorgang.quelle_id or quelle.id
        lead_phase_berechnen(session, vorgang)
        anzahl += 1
    session.commit()
    return anzahl
