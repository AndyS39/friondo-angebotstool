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
            # Phase 77: Erfassung abgesendet → aktiver VOT-Termin „erfolgt“
            if vorgang.lead_phase in ("erfasst", "angebot", "gewonnen"):
                for termin in (session.query(VotTermin)
                               .filter(VotTermin.vorgang_id == vorgang.id,
                                       VotTermin.status.in_(("geplant",
                                                             "bestaetigt")))):
                    termin.status = "erfolgt"
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
    try:
        monday_termine_ableiten(session)   # Phase 77: VOT-Datum → vot_termine
    except Exception:
        pass
    session.commit()
    return anzahl


# --- Phase 75: Eingang – Duplikate, Anlage, Startquellen, Demo-Daten ---------------

STARTQUELLEN = [
    ("website", "Website/Förderrechner", "website", None),
    ("landingpage", "Landingpages", "landingpage", None),
    ("portal", "Lead-Portal", "portal", None),
    ("partner_enni", "Partner Enni", "partner", "Enni"),
    ("partner_swd", "Partner SWD", "partner", "SWD"),
    ("partner_sparkasse_du", "Partner Sparkasse DU", "partner", "Sparkasse"),
    ("telefon", "Telefon", "telefon", None),
    ("empfehlung", "Empfehlung", "empfehlung", None),
    ("bestand", "Bestand", "bestand", None),
]


def quellen_vorbelegen(session: Session) -> int:
    """Startquellen anlegen (idempotent, migrate.py); monday_<board> entsteht
    automatisch beim Sync (Phase 73)."""
    vorhanden = {q.key for q in session.query(LeadQuelle)}
    neu = 0
    for key, name, typ, kanal in STARTQUELLEN:
        if key not in vorhanden:
            session.add(LeadQuelle(key=key, name=name, typ=typ, kanal=kanal,
                                   aktiv=True))
            neu += 1
    session.flush()
    return neu


def telefon_normalisieren(telefon: str) -> str:
    """E.164 für den Duplikatabgleich: 0203… → +49203…, Trennzeichen raus."""
    ziffern = re.sub(r"[^\d+]", "", telefon or "")
    if not ziffern:
        return ""
    if ziffern.startswith("00"):
        return "+" + ziffern[2:]
    if ziffern.startswith("0"):
        return "+49" + ziffern[1:]
    if not ziffern.startswith("+"):
        return "+49" + ziffern
    return ziffern


def _name_normal(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def vorgang_offen(vorgang: Vorgang) -> bool:
    """Konzept 4: offen = nicht Gewonnen/Verloren/Unqualifiziert."""
    return (vorgang.lead_phase or "neu") not in ("gewonnen", "verloren",
                                                 "unqualifiziert")


def duplikat_pruefen(session: Session, telefon: str = "", email: str = "",
                     name: str = "", plz: str = "", strasse: str = "") -> dict | None:
    """Treffer über Telefon (E.164), E-Mail, Name+PLZ oder Straße+PLZ.
    Liefert {kunde, vorgang, offen} des jüngsten Vorgangs oder None."""
    telefon_norm = telefon_normalisieren(telefon)
    email_norm = (email or "").strip().lower()
    treffer: Kunde | None = None
    for kunde in session.query(Kunde).filter(Kunde.aktiv.is_(True)):
        if telefon_norm and telefon_normalisieren(kunde.telefon) == telefon_norm:
            treffer = kunde
            break
        if email_norm and (kunde.email or "").strip().lower() == email_norm:
            treffer = kunde
            break
        if (plz and kunde.plz == plz.strip()
                and name and _name_normal(kunde.nachname) in _name_normal(name)
                and _name_normal(kunde.nachname)):
            treffer = kunde
            break
        if (plz and kunde.plz == plz.strip() and strasse
                and _name_normal(kunde.strasse) == _name_normal(strasse)
                and _name_normal(strasse)):
            treffer = kunde
            break
    if treffer is None:
        return None
    vorgang = (session.query(Vorgang)
               .filter(Vorgang.kunde_id == treffer.id)
               .order_by(Vorgang.angelegt_am.desc()).first())
    return {"kunde": treffer, "vorgang": vorgang,
            "offen": vorgang is not None and vorgang_offen(vorgang)}


def _sparten_mischen(kunde: Kunde, sparten: list[str]) -> None:
    vorhanden = [s.strip() for s in (kunde.interesse or "").split(",") if s.strip()]
    for s in sparten:
        if s not in vorhanden:
            vorhanden.append(s)
    kunde.interesse = ",".join(vorhanden)


def lead_anlegen(session: Session, daten: dict, quelle: LeadQuelle | None,
                 eingang_art: str, benutzer=None,
                 kampagne_id: int | None = None,
                 entscheidung: str = "") -> tuple[Vorgang, str]:
    """Zentrale Anlage (Schnellanlage, Import, API, Parser, Demo-Generator).
    Duplikat-Regel (Konzept 4): offener Vorgang → anhängen (neue Sparte);
    abgeschlossener → neuer Vorgang „Wiederkehrer“; entscheidung='neu'
    erzwingt einen eigenen Vorgang. Liefert (vorgang, status) mit status
    neu | angehaengt | wiederkehrer."""
    sparten = [s for s in (daten.get("sparten") or []) if s in ("WP", "PV", "KL", "WB")]
    duplikat = duplikat_pruefen(
        session, telefon=daten.get("telefon", ""), email=daten.get("email", ""),
        name=f"{daten.get('vorname', '')} {daten.get('nachname', '')}",
        plz=daten.get("plz", ""), strasse=daten.get("strasse", ""))
    status = "neu"
    kunde = None
    vorgang = None
    if duplikat is not None and entscheidung != "neu":
        kunde = duplikat["kunde"]
        if duplikat["offen"]:
            vorgang = duplikat["vorgang"]
            status = "angehaengt"
        else:
            status = "wiederkehrer"
    if kunde is None:
        kunde = Kunde(anrede=daten.get("anrede", ""),
                      vorname=(daten.get("vorname") or "").strip()[:100],
                      nachname=(daten.get("nachname") or "").strip()[:100],
                      strasse=(daten.get("strasse") or "").strip()[:200],
                      plz=(daten.get("plz") or "").strip()[:10],
                      ort=(daten.get("ort") or "").strip()[:100],
                      telefon=(daten.get("telefon") or "").strip()[:50],
                      email=(daten.get("email") or "").strip().lower()[:200])
        if quelle is not None and quelle.kanal and not kunde.kanal_manuell:
            kunde.vertriebskanal = quelle.kanal
        session.add(kunde)
        session.flush()
    else:
        # nicht-leere neue Werte ergänzen (nie überschreiben)
        for feld in ("telefon", "email", "strasse", "ort"):
            if not getattr(kunde, feld) and daten.get(feld):
                setattr(kunde, feld, str(daten[feld]).strip())
    _sparten_mischen(kunde, sparten)

    if vorgang is None:
        vorgang = Vorgang(kunde_id=kunde.id, lead_phase="neu")
        session.add(vorgang)
        session.flush()
    jetzt = datetime.now()
    if not vorgang.eingang_am:
        vorgang.eingang_am = jetzt
        vorgang.eingang_art = eingang_art
    if quelle is not None and not vorgang.quelle_id:
        vorgang.quelle_id = quelle.id
    if kampagne_id and not vorgang.kampagne_id:
        vorgang.kampagne_id = kampagne_id
    for utm in ("utm_source", "utm_medium", "utm_campaign", "utm_content"):
        if daten.get(utm) and not getattr(vorgang, utm):
            setattr(vorgang, utm, str(daten[utm]).strip()[:200])
    if daten.get("wunschzeiten"):
        vorgang.wunschzeiten = json.dumps(list(daten["wunschzeiten"]),
                                          ensure_ascii=False)
    if daten.get("nachricht"):
        vorgang.anfrage_text = ((vorgang.anfrage_text + "\n\n---\n\n")
                                if vorgang.anfrage_text else "") \
                               + str(daten["nachricht"]).strip()[:4000]
    if daten.get("rohdaten") is not None:
        vorgang.anfrage_rohdaten = json.dumps(daten["rohdaten"],
                                              ensure_ascii=False, default=str)[:8000]
    if daten.get("einwilligung_werbung"):
        vorgang.einwilligung_werbung = True
        vorgang.einwilligung_werbung_am = jetzt
        vorgang.einwilligung_quelle = daten.get("einwilligung_quelle", "formular")
    # Leitplanke 3: im Demo-Modus tragen Modul-Leads demo=1
    if demo_aktiv(session) and status != "angehaengt":
        vorgang.demo = True
    if status == "angehaengt":
        aktivitaet(session, vorgang.id, "import",
                   f"Neue Anfrage {quelle.name if quelle else eingang_art} "
                   f"angehängt ({', '.join(sparten) or 'ohne Sparte'})",
                   benutzer=benutzer)
    else:
        quelle_name = quelle.name if quelle else eingang_art
        zusatz = " – Wiederkehrer" if status == "wiederkehrer" else ""
        aktivitaet(session, vorgang.id, "system",
                   f"Lead angelegt ({quelle_name}, {eingang_art}){zusatz}",
                   benutzer=benutzer)
        # Phase 78: Eingangsbestätigung sofort (nur mit E-Mail; der
        # Versand-Job entscheidet nach mail_modus – Sendesperre im Demo)
        mail_planen(session, vorgang, "eingangsbestaetigung")
        # vorläufiger Score (nur Systemregeln) + Zuweisung + Benachrichtigung
        score_vorlaeufig(session, vorgang)
        if vorgang.leadmanager_id is None:
            vorgang.leadmanager_id = naechster_leadmanager(session, benutzer)
        ziele = ([vorgang.leadmanager_id] if vorgang.leadmanager_id
                 else [b.id for b in session.query(Benutzer)
                       .filter(Benutzer.aktiv.is_(True))
                       if b.rolle == "admin" or b.hat_rolle("leadmanagement")])
        benachrichtigen(session, ziele,
                        f"Neuer Lead: {kunde.anzeige_name}, {kunde.ort or '?'} – "
                        f"{', '.join(sparten) or '–'} – {quelle_name}",
                        f"/lead-management/lead/{vorgang.id}")
    lead_phase_berechnen(session, vorgang)
    session.flush()
    return vorgang, status


def score_vorlaeufig(session: Session, vorgang: Vorgang) -> None:
    """Systemregeln vor der Qualifizierung: Kerngebiet-PLZ + Quellen-Bonus."""
    from app import leadmanagement_logik
    punkte = 0
    kunde = session.get(Kunde, vorgang.kunde_id)
    kerngebiet = [p.strip() for p in
                  parameter_holen(session, "kerngebiet_plz", "").split(",")
                  if p.strip()]
    if kunde is not None and kunde.plz and any(
            kunde.plz.startswith(p) for p in kerngebiet):
        punkte += 10
    if vorgang.quelle_id:
        quelle = session.get(LeadQuelle, vorgang.quelle_id)
        if quelle is not None:
            punkte += quelle.score_bonus or 0
    vorgang.score_punkte = punkte
    logik = leadmanagement_logik.hole_logik()
    vorgang.score_klasse = logik.klasse_fuer(punkte)


# --- Demo-Daten-Generator (Phase 75, nur Admin, nur Demo-Modus) ---------------------

_DEMO_VORNAMEN = ["Lena", "Jonas", "Miriam", "Torben", "Sina", "Malte", "Ricarda",
                  "Nils", "Annika", "Fabio", "Greta", "Ole", "Tessa", "Bendix",
                  "Ronja", "Yannick", "Carla", "Mattis", "Ida", "Levke", "Thies",
                  "Femke", "Jost", "Alva", "Rasmus"]
_DEMO_NACHNAMEN = ["Demolead", "Testinger", "Musterfrau", "Beispieler", "Probst-Demo",
                   "Fiktivius", "Demohaus", "Testerling", "Beispielmann", "Demovic"]
_DEMO_ORTE = [("Duisburg", "47051", "Sonnenwall"), ("Moers", "47441", "Homberger Straße"),
              ("Oberhausen", "46045", "Marktstraße"), ("Mülheim an der Ruhr", "45468", "Schloßstraße"),
              ("Dinslaken", "46535", "Neustraße"), ("Krefeld", "47798", "Rheinstraße")]
_DEMO_SPARTEN = [["WP"], ["PV"], ["WP", "PV"], ["KL"], ["WB"], ["WP"], ["PV"]]


def _demo_werktag(basis: datetime, werktage: int) -> datetime:
    tag = basis
    while werktage > 0:
        tag += timedelta(days=1)
        if tag.weekday() < 5:
            werktage -= 1
    return tag


def demo_leads_erzeugen(session: Session, benutzer=None) -> dict:
    """25 fiktive Demo-Leads (Plan Phase 75): 10 neu, 6 in Kontaktierung,
    5 qualifiziert, 4 terminiert (nächste 10 Werktage, vorhandene AD)."""
    from app import leadmanagement_logik
    if not demo_aktiv(session):
        return {"fehler": "Nur im Demo-Modus möglich."}
    quellen = [q for q in session.query(LeadQuelle)
               .filter(LeadQuelle.aktiv.is_(True), LeadQuelle.typ != "monday")]
    ad_liste = [b for b in session.query(Benutzer)
                .filter(Benutzer.aktiv.is_(True), Benutzer.rolle == "aussendienst")]
    logik = leadmanagement_logik.hole_logik()
    jetzt = datetime.now()
    angelegt = 0
    for i in range(25):
        ort, plz, strasse = _DEMO_ORTE[i % len(_DEMO_ORTE)]
        daten = {
            "anrede": "Frau" if i % 2 else "Herr",
            "vorname": _DEMO_VORNAMEN[i % len(_DEMO_VORNAMEN)],
            "nachname": f"{_DEMO_NACHNAMEN[i % len(_DEMO_NACHNAMEN)]}-{i + 1:02d}",
            "telefon": f"0203 000 {i + 10:02d}",
            "email": f"demo.lead{i + 1:02d}@example.invalid",
            "strasse": strasse, "plz": plz, "ort": ort,
            "sparten": _DEMO_SPARTEN[i % len(_DEMO_SPARTEN)],
            "nachricht": "Demo-Anfrage (Generator) – bitte Rückruf.",
            "wunschzeiten": ["vormittags", "abends"][i % 2:i % 2 + 1],
        }
        quelle = quellen[i % len(quellen)] if quellen else None
        vorgang, _ = lead_anlegen(session, daten, quelle, "manuell",
                                  benutzer=benutzer, entscheidung="neu")
        vorgang.demo = True
        vorgang.eingang_am = jetzt - timedelta(days=i % 14, hours=(i * 3) % 9)
        if 10 <= i < 16:   # in Kontaktierung mit Versuchen
            vorgang.versuch_nr = (i % 3) + 1
            vorgang.erstkontakt_am = vorgang.eingang_am + timedelta(hours=1)
            vorgang.naechste_aktion_am = jetzt + timedelta(days=(i % 3) - 1)
            aktivitaet(session, vorgang.id, "anruf", "Demo: nicht erreicht",
                       benutzer=benutzer, ergebnis="nicht_erreicht")
        elif 16 <= i < 21:   # qualifiziert
            vorgang.versuch_nr = 1
            vorgang.erstkontakt_am = vorgang.eingang_am + timedelta(hours=1)
            vorgang.erreicht_am = vorgang.erstkontakt_am
            sparte = daten["sparten"][0]
            session.add(LeadQualifizierung(
                vorgang_id=vorgang.id, sparte=sparte,
                antworten=json.dumps({"Q-DEMO": "ja"}),
                score_punkte=40 + i, score_klasse=logik.klasse_fuer(40 + i),
                abgeschlossen_am=jetzt,
                benutzer_id=benutzer.id if benutzer else None))
            vorgang.score_punkte = 40 + i
            vorgang.score_klasse = logik.klasse_fuer(40 + i)
        elif i >= 21:   # terminiert, nächste 10 Werktage
            vorgang.versuch_nr = 1
            vorgang.erstkontakt_am = vorgang.eingang_am + timedelta(hours=1)
            vorgang.erreicht_am = vorgang.erstkontakt_am
            beginn = _demo_werktag(jetzt, (i - 20) * 2).replace(
                hour=9 + (i % 3) * 3, minute=0, second=0, microsecond=0)
            ad = ad_liste[i % len(ad_liste)] if ad_liste else None
            session.add(VotTermin(
                vorgang_id=vorgang.id, ad_id=ad.id if ad else None,
                beginn=beginn, ende=beginn + timedelta(minutes=90),
                adresse=f"{strasse}, {plz} {ort}", status="geplant",
                quelle="manuell", demo=True,
                erstellt_von=benutzer.id if benutzer else None))
            vorgang.terminiert_am = jetzt
        session.flush()   # autoflush aus: Qualifizierung/Termin sichtbar machen
        lead_phase_berechnen(session, vorgang)
        angelegt += 1
    session.commit()
    return {"angelegt": angelegt}


def demo_leads_loeschen(session: Session) -> dict:
    """Alle Demo-Leads restlos entfernen (Vorgänge, Kunden ohne andere
    Vorgänge, Aktivitäten, Termine, Kommunikation, Qualifizierungen)."""
    from app.models import KommunikationLog
    vorgaenge = session.query(Vorgang).filter(Vorgang.demo.is_(True)).all()
    kunden_ids = {v.kunde_id for v in vorgaenge}
    anzahl = len(vorgaenge)
    for v in vorgaenge:
        session.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
        session.query(LeadQualifizierung).filter_by(vorgang_id=v.id).delete()
        session.query(VotTermin).filter_by(vorgang_id=v.id).delete()
        session.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
        session.delete(v)
    session.flush()
    geloeschte_kunden = 0
    for kunde_id in kunden_ids:
        if not session.query(Vorgang).filter(Vorgang.kunde_id == kunde_id).count():
            kunde = session.get(Kunde, kunde_id)
            if kunde is not None:
                session.delete(kunde)
                geloeschte_kunden += 1
    session.commit()
    return {"vorgaenge": anzahl, "kunden": geloeschte_kunden}


# --- Phase 76: Anruf-Ergebnisse, Kaskade, Qualifizierung, Score ---------------------

def _arbeitsfenster_schieben(session: Session, zeitpunkt: datetime) -> datetime:
    """Zeitpunkt in das nächste LM-Arbeitsfenster (Mo-Fr) schieben; liegt er
    hinter dem Arbeitsende, gilt der nächste Arbeitsbeginn."""
    start_min, ende_min = _arbeitszeit(session)
    while True:
        tages_start = zeitpunkt.replace(hour=0, minute=0, second=0,
                                        microsecond=0) + timedelta(minutes=start_min)
        tages_ende = zeitpunkt.replace(hour=0, minute=0, second=0,
                                       microsecond=0) + timedelta(minutes=ende_min)
        if zeitpunkt.weekday() >= 5 or zeitpunkt > tages_ende:
            zeitpunkt = (zeitpunkt.replace(hour=0, minute=0, second=0,
                                           microsecond=0)
                         + timedelta(days=1, minutes=start_min))
            continue
        if zeitpunkt < tages_start:
            zeitpunkt = tages_start
        return zeitpunkt


def kaskade_zeitpunkt(session: Session, regel: str,
                      jetzt: datetime | None = None) -> datetime:
    """`+2h` (innerhalb der Arbeitszeit, sonst nächster Arbeitsbeginn),
    `+1d 18:00` (nächster Werktag 18:00, außerhalb → Arbeitsende), `+3d`, `+7d`."""
    jetzt = jetzt or datetime.now()
    treffer = re.match(r"^\+(\d+)([hd])(?:\s+(\d{1,2}):(\d{2}))?$",
                       (regel or "").strip())
    if not treffer:
        return _arbeitsfenster_schieben(session, jetzt + timedelta(days=1))
    anzahl = int(treffer.group(1))
    if treffer.group(2) == "h":
        return _arbeitsfenster_schieben(session, jetzt + timedelta(hours=anzahl))
    ziel = jetzt + timedelta(days=anzahl)
    while ziel.weekday() >= 5:   # auf Werktag schieben
        ziel += timedelta(days=1)
    if treffer.group(3):
        start_min, ende_min = _arbeitszeit(session)
        stunde, minute = int(treffer.group(3)), int(treffer.group(4))
        gewuenscht = stunde * 60 + minute
        if gewuenscht > ende_min:   # 18:00 außerhalb → Arbeitsende
            stunde, minute = divmod(ende_min, 60)
        return ziel.replace(hour=stunde, minute=minute, second=0, microsecond=0)
    return _arbeitsfenster_schieben(session, ziel)


def mail_planen(session: Session, vorgang: Vorgang, vorlage_key: str,
                termin=None, geplant_am: datetime | None = None):
    """Eintrag in die Kommunikations-Warteschlange (Phase 78 verarbeitet ihn);
    ohne Kunden-E-Mail passiert nichts."""
    from app.models import KommunikationLog
    kunde = session.get(Kunde, vorgang.kunde_id)
    if kunde is None or not kunde.email:
        return None
    eintrag = KommunikationLog(
        vorgang_id=vorgang.id, termin_id=termin.id if termin else None,
        kanal="mail", vorlage_key=vorlage_key, an=kunde.email,
        geplant_am=geplant_am or datetime.now(), status="geplant",
        modus=parameter_holen(session, "mail_modus", "protokoll"))
    session.add(eintrag)
    session.flush()
    return eintrag


def kaskade_anwenden(session: Session, vorgang: Vorgang, benutzer=None) -> str:
    """Nach Nicht erreicht / Besetzt / Mailbox: Wiedervorlage + Aktion aus dem
    Blatt Kaskade; nach dem letzten Versuch Phase „Nicht erreicht“ (+30 Tage,
    mail_nurture). Liefert einen Meldungstext."""
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    stufe = logik.stufe(vorgang.versuch_nr)
    if stufe is not None and not stufe.letzter:
        vorgang.naechste_aktion_am = kaskade_zeitpunkt(
            session, stufe.wiedervorlage_nach)
        if stufe.aktion == "mail_nicht_erreicht":
            mail_planen(session, vorgang, "nicht_erreicht")
        return ("Wiedervorlage "
                + vorgang.naechste_aktion_am.strftime("%d.%m.%Y %H:%M"))
    # letzter Versuch (oder Versuch über der Kaskade)
    if stufe is not None and stufe.aktion == "mail_nicht_erreicht":
        mail_planen(session, vorgang, "nicht_erreicht")
    vorgang.lead_phase = "nicht_erreicht"
    vorgang.naechste_aktion_am = datetime.now() + timedelta(days=30)
    mail_planen(session, vorgang, "nurture")
    aktivitaet(session, vorgang.id, "status",
               "Kaskade ausgeschöpft – Phase Nicht erreicht, Wiedervorlage +30 Tage",
               benutzer=benutzer)
    return "Kaskade ausgeschöpft – Lead steht auf „Nicht erreicht“ (+30 Tage)."


def score_berechnen(session: Session, vorgang: Vorgang) -> tuple[int, str]:
    """Summe aus Blatt Scoring über alle Sparten-Antworten (je Frage nur die
    erste zutreffende Zeile) + Systemregeln (Kerngebiet, Quellen-Bonus)."""
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    antworten: dict = {}
    for q in (session.query(LeadQualifizierung)
              .filter(LeadQualifizierung.vorgang_id == vorgang.id)):
        try:
            antworten.update(json.loads(q.antworten or "{}"))
        except ValueError:
            pass
    punkte = 0
    bepunktete_keys: set[str] = set()
    bepunktete_texte: set[str] = set()   # gemeinsame Fragen (Übernahme in
    for regel in logik.scoring:          # andere Sparten) zählen nur einmal
        if regel.frage_key in bepunktete_keys:
            continue   # je Frage nur die erste zutreffende Zeile
        if regel.frage_key not in antworten:
            continue
        frage = logik.frage(regel.frage_key)
        fragetext = frage.frage if frage is not None else regel.frage_key
        if fragetext in bepunktete_texte:
            continue
        if leadmanagement_logik.bedingung_trifft(regel.bedingung,
                                                 antworten[regel.frage_key]):
            punkte += regel.punkte
            bepunktete_keys.add(regel.frage_key)
            bepunktete_texte.add(fragetext)
    kunde = session.get(Kunde, vorgang.kunde_id)
    kerngebiet = [p.strip() for p in
                  parameter_holen(session, "kerngebiet_plz", "").split(",")
                  if p.strip()]
    if kunde is not None and kunde.plz and any(
            kunde.plz.startswith(p) for p in kerngebiet):
        punkte += 10
    if vorgang.quelle_id:
        quelle = session.get(LeadQuelle, vorgang.quelle_id)
        if quelle is not None:
            punkte += quelle.score_bonus or 0
    klasse = logik.klasse_fuer(punkte)
    vorgang.score_punkte = punkte
    vorgang.score_klasse = klasse
    return punkte, klasse


def qualifizierung_abschliessen(session: Session, vorgang: Vorgang, sparte: str,
                                antworten: dict, benutzer=None) -> LeadQualifizierung:
    """Bogen speichern: Score, Phase, Wunschzeiten, Zusatzinteressen,
    Übernahme gemeinsamer Fragen in die anderen Sparten (gleicher Fragetext)."""
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    zeile = (session.query(LeadQualifizierung)
             .filter(LeadQualifizierung.vorgang_id == vorgang.id,
                     LeadQualifizierung.sparte == sparte).first())
    if zeile is None:
        zeile = LeadQualifizierung(vorgang_id=vorgang.id, sparte=sparte)
        session.add(zeile)
    vorher = {}
    try:
        vorher = json.loads(zeile.antworten or "{}")
    except ValueError:
        pass
    vorher.update(antworten)
    zeile.antworten = json.dumps(vorher, ensure_ascii=False)
    zeile.abgeschlossen_am = datetime.now()
    zeile.benutzer_id = benutzer.id if benutzer else None
    session.flush()

    # gemeinsame Fragen (gleicher Fragetext) in die anderen Interessen-Sparten
    kunde = session.get(Kunde, vorgang.kunde_id)
    interessen = [s.strip() for s in (kunde.interesse or "").split(",")
                  if s.strip() in ("WP", "PV", "KL", "WB")]
    for frage in logik.fragen_der_sparte(sparte):
        if frage.key not in antworten:
            continue
        for andere in interessen:
            if andere == sparte:
                continue
            ziel_frage = next((f for f in logik.fragen_der_sparte(andere)
                               if f.frage == frage.frage), None)
            if ziel_frage is None:
                continue
            ziel = (session.query(LeadQualifizierung)
                    .filter(LeadQualifizierung.vorgang_id == vorgang.id,
                            LeadQualifizierung.sparte == andere).first())
            if ziel is None:
                ziel = LeadQualifizierung(vorgang_id=vorgang.id, sparte=andere)
                session.add(ziel)
                session.flush()
            try:
                ziel_antworten = json.loads(ziel.antworten or "{}")
            except ValueError:
                ziel_antworten = {}
            ziel_antworten.setdefault(ziel_frage.key, antworten[frage.key])
            ziel.antworten = json.dumps(ziel_antworten, ensure_ascii=False)

    # Wunschzeiten + Zusatzinteressen an den Vorgang/Kunden
    for frage in logik.fragen_der_sparte(sparte):
        wert = antworten.get(frage.key)
        if wert is None:
            continue
        if frage.frage == "Wunschzeiten" and isinstance(wert, list):
            vorgang.wunschzeiten = json.dumps(wert, ensure_ascii=False)
        if frage.frage == "Zusätzliches Interesse" and isinstance(wert, list):
            zusatz = {"PV": "PV", "Klima": "KL", "Wallbox": "WB",
                      "Speicher": ""}
            neue = [zusatz.get(w, "") for w in wert if zusatz.get(w)]
            if neue and kunde is not None:
                _sparten_mischen(kunde, neue)
    if vorgang.erreicht_am is None:
        vorgang.erreicht_am = datetime.now()
    punkte, klasse = score_berechnen(session, vorgang)
    zeile.score_punkte = punkte
    zeile.score_klasse = klasse
    if vorgang.lead_phase not in ("terminiert", "erfasst", "angebot",
                                  "gewonnen", "verloren"):
        vorgang.lead_phase = "qualifiziert"
    aktivitaet(session, vorgang.id, "status",
               f"Qualifiziert {sparte} ({klasse}, {punkte} Punkte)",
               benutzer=benutzer)
    session.flush()
    return zeile


def erfassungs_vorbelegung(session: Session, vorgang: Vorgang) -> dict:
    """Mapping Qualifizierung → Erfassungsbogen über `erfassungs_frage`
    (Phase 76; aktiv erst bei lead_freigabe_modus = alle): liefert
    {erfassungs_key: {"wert": …, "info": "aus Qualifizierung …"}}."""
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    ergebnis: dict = {}
    for q in (session.query(LeadQualifizierung)
              .filter(LeadQualifizierung.vorgang_id == vorgang.id,
                      LeadQualifizierung.abgeschlossen_am.isnot(None))):
        try:
            antworten = json.loads(q.antworten or "{}")
        except ValueError:
            continue
        lm = session.get(Benutzer, q.benutzer_id) if q.benutzer_id else None
        info = (f"aus Qualifizierung {q.sparte} vom "
                f"{q.abgeschlossen_am.strftime('%d.%m.%Y')}"
                + (f" ({lm.name})" if lm else ""))
        for frage in logik.fragen_der_sparte(q.sparte):
            if not frage.erfassungs_frage or frage.key not in antworten:
                continue
            wert = antworten[frage.key]
            if frage.typ == "janein":
                wert = "Ja" if str(wert).strip().lower() in ("ja", "true", "1") \
                    else "Nein"
            elif isinstance(wert, list):
                wert = ", ".join(str(w) for w in wert)
            else:
                wert = str(wert)
            ergebnis.setdefault(frage.erfassungs_frage,
                                {"wert": wert, "info": info})
    return ergebnis


# --- Täglicher Lauf 07:00: fällige Zurückgestellte reaktivieren ---------------------

def taeglicher_lauf_leads(session: Session | None = None,
                          erzwingen: bool = False) -> dict:
    from app.db import SessionLocal
    eigen = session is None
    if eigen:
        session = SessionLocal()
    try:
        heute = datetime.now().date()
        if (not erzwingen and parameter_holen(session, "lm_lauf_datum")
                == heute.isoformat()):
            return {"uebersprungen": True}
        anzahl = 0
        for vorgang in (session.query(Vorgang)
                        .filter(Vorgang.lead_phase == "zurueckgestellt",
                                Vorgang.zurueckgestellt_bis.isnot(None),
                                Vorgang.zurueckgestellt_bis
                                <= datetime.now())):
            vorgang.lead_phase = "neu"
            vorgang.naechste_aktion_am = datetime.now()
            aktivitaet(session, vorgang.id, "status",
                       "Wiedervorlage fällig – zurück auf Neu "
                       f"(war zurückgestellt: {vorgang.zurueckgestellt_grund or '-'})")
            if vorgang.leadmanager_id:
                kunde = session.get(Kunde, vorgang.kunde_id)
                benachrichtigen(session, [vorgang.leadmanager_id],
                                f"Wiedervorlage fällig: {kunde.anzeige_name if kunde else '?'}",
                                f"/lead-management/lead/{vorgang.id}")
            anzahl += 1
        parameter_setzen(session, "lm_lauf_datum", heute.isoformat())
        session.commit()
        return {"reaktiviert": anzahl}
    finally:
        if eigen:
            session.close()


_scheduler_laeuft = False


def scheduler_starten() -> None:
    """5-Minuten-Schleife: ab 07:00 der Wiedervorlage-Lauf (Datums-Schalter);
    der Löschlauf 03:00 (Phase 81) hängt an derselben Schleife."""
    global _scheduler_laeuft
    if _scheduler_laeuft:
        return
    _scheduler_laeuft = True

    def schleife():
        import threading as _t   # noqa: F401 (Muster wie die anderen Scheduler)
        import time

        from app.db import SessionLocal
        time.sleep(200)
        while True:
            try:
                jetzt = datetime.now()
                if jetzt.hour >= 7:
                    taeglicher_lauf_leads()
                if jetzt.hour >= 3:
                    session = SessionLocal()
                    try:
                        loeschlauf(session)
                    finally:
                        session.close()
            except Exception:
                pass
            time.sleep(300)

    import threading
    threading.Thread(target=schleife, daemon=True, name="leadmanagement").start()


def loeschlauf(session: Session, erzwingen: bool = False,
               trocken: bool = False) -> dict:
    """DSGVO-Anonymisierung (Phase 81, täglich 03:00, nur bei loeschlauf=an):
    unqualifiziert / nicht_erreicht / verloren, letzte Aktivität älter als
    loeschfrist_monate, kein angenommenes Angebot, kein Projekt. Im Demo-Modus
    zusätzlich nur Demo-Leads."""
    if not trocken and not erzwingen:
        if parameter_holen(session, "loeschlauf", "aus") != "an":
            return {"uebersprungen": True}
        if parameter_holen(session, "loeschlauf_datum") == \
                datetime.now().date().isoformat():
            return {"uebersprungen": True}
    try:
        monate = int(parameter_holen(session, "loeschfrist_monate", "12"))
    except ValueError:
        monate = 12
    grenze = datetime.now() - timedelta(days=monate * 30)
    from app.models import Projekt
    kandidaten = []
    for vorgang in (session.query(Vorgang)
                    .filter(Vorgang.lead_phase.in_(
                        ("unqualifiziert", "nicht_erreicht", "verloren")))):
        if demo_aktiv(session) and not vorgang.demo:
            continue
        kunde = session.get(Kunde, vorgang.kunde_id)
        if kunde is not None and kunde.nachname == "Gelöscht":
            continue
        letzte = (session.query(LeadAktivitaet)
                  .filter(LeadAktivitaet.vorgang_id == vorgang.id)
                  .order_by(LeadAktivitaet.zeitpunkt.desc()).first())
        letzter_zeitpunkt = (letzte.zeitpunkt if letzte else
                             vorgang.eingang_am or vorgang.angelegt_am)
        if letzter_zeitpunkt is None or letzter_zeitpunkt > grenze:
            continue
        if (session.query(Angebot)
                .filter(Angebot.vorgang_id == vorgang.id,
                        Angebot.status == "Angenommen").count()):
            continue
        if (session.query(Projekt)
                .filter(Projekt.vorgang_id == vorgang.id).count()):
            continue
        kandidaten.append(vorgang)
    if trocken:
        return {"kandidaten": [v.id for v in kandidaten]}
    for vorgang in kandidaten:
        kunde = session.get(Kunde, vorgang.kunde_id)
        vorgang.anfrage_text = ""
        vorgang.anfrage_rohdaten = ""
        for a in (session.query(LeadAktivitaet)
                  .filter(LeadAktivitaet.vorgang_id == vorgang.id)):
            a.text = ""
        if kunde is not None and not (
                session.query(Vorgang)
                .filter(Vorgang.kunde_id == kunde.id,
                        Vorgang.id != vorgang.id).count()):
            kunde.vorname = ""
            kunde.nachname = "Gelöscht"
            kunde.strasse = ""
            kunde.telefon = ""
            kunde.email = ""
            kunde.notizen = ""
            kunde.aktiv = False
        aktivitaet(session, vorgang.id, "system",
                   "Anonymisiert (Löschlauf)")
    parameter_setzen(session, "loeschlauf_datum",
                     datetime.now().date().isoformat())
    if kandidaten:
        protokoll = parameter_holen(session, "loeschlauf_protokoll", "")
        zeile = (f"{datetime.now().strftime('%d.%m.%Y %H:%M')} · "
                 f"{len(kandidaten)} Vorgänge anonymisiert")
        parameter_setzen(session, "loeschlauf_protokoll",
                         "\n".join(([zeile] + protokoll.splitlines())[:20]))
    session.commit()
    return {"anonymisiert": len(kandidaten)}


# --- Phase 77: AD-Profile, Terminassistent, Buchen ----------------------------------

_WOCHENTAGE = ("mo", "di", "mi", "do", "fr", "sa", "so")
STANDARD_ARBEITSZEITEN = {t: ["08:00", "18:00"] for t in _WOCHENTAGE[:5]}


def ad_profil(session: Session, benutzer_id: int):
    """Profil des AD oder Standardwerte (Mo–Fr 08–18, Start = Firmenadresse,
    90/15/4) als leichtes Objekt."""
    from app.models import AdProfil
    profil = (session.query(AdProfil)
              .filter(AdProfil.benutzer_id == benutzer_id).first())
    if profil is not None:
        return profil

    class _Standard:
        pass
    standard = _Standard()
    standard.benutzer_id = benutzer_id
    standard.start_adresse = parameter_holen(session, "firmen_adresse", "Duisburg")
    standard.start_lat = None
    standard.start_lon = None
    standard.arbeitszeiten = json.dumps(STANDARD_ARBEITSZEITEN)
    standard.termin_dauer_min = 90
    standard.puffer_min = 15
    standard.max_termine_tag = 4
    standard.gebiet_plz_praefixe = "[]"
    standard.kalender_postfach = None
    standard.aktiv_terminierung = True
    return standard


def _arbeitszeiten_von_bis(profil, tag: datetime) -> tuple[int, int] | None:
    """(startminute, endminute) des AD an diesem Tag oder None (frei)."""
    try:
        zeiten = json.loads(profil.arbeitszeiten or "{}")
    except ValueError:
        zeiten = {}
    fenster = zeiten.get(_WOCHENTAGE[tag.weekday()])
    if not fenster or len(fenster) < 2:
        return None
    try:
        von = int(fenster[0][:2]) * 60 + int(fenster[0][3:5])
        bis = int(fenster[1][:2]) * 60 + int(fenster[1][3:5])
    except (ValueError, IndexError):
        return None
    return (von, bis) if von < bis else None


def ad_kandidaten(session: Session, vorgang: Vorgang,
                  nur_ad_id: int | None = None) -> list[Benutzer]:
    """Gebiets-PLZ der Profile → sonst alle mit aktiv_terminierung; manuell
    einschränkbar. (Kanal-feste AD folgen mit den Zuweisungsregeln in V2 –
    Entscheidung dokumentiert.)"""
    from app.models import AdProfil
    kunde = session.get(Kunde, vorgang.kunde_id)
    plz = (kunde.plz or "") if kunde else ""
    alle_ad = [b for b in session.query(Benutzer)
               .filter(Benutzer.aktiv.is_(True), Benutzer.rolle == "aussendienst")]
    if nur_ad_id:
        return [b for b in alle_ad if b.id == nur_ad_id]
    profile = {p.benutzer_id: p for p in session.query(AdProfil)}
    aktive = [b for b in alle_ad
              if b.id not in profile or profile[b.id].aktiv_terminierung]
    gebiet = []
    for b in aktive:
        profil = profile.get(b.id)
        if profil is None:
            continue
        try:
            praefixe = json.loads(profil.gebiet_plz_praefixe or "[]")
        except ValueError:
            praefixe = []
        if plz and any(plz.startswith(str(p)) for p in praefixe):
            gebiet.append(b)
    return gebiet or aktive


def _wunschzeit_fenster(session: Session, vorgang: Vorgang) -> list:
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    try:
        gewuenscht = json.loads(vorgang.wunschzeiten or "[]")
    except ValueError:
        gewuenscht = []
    return [w for w in logik.wunschzeiten if w.key in gewuenscht]


def _im_wunschfenster(fenster, beginn: datetime) -> bool:
    tag = _WOCHENTAGE[beginn.weekday()]
    for w in fenster:
        tage = ("mo", "di", "mi", "do", "fr") if w.wochentage == "mo-fr" \
            else (w.wochentage,)
        if tag not in tage:
            continue
        if w.von <= beginn.strftime("%H:%M") < w.bis:
            return True
    return False


def termin_vorschlaege(session: Session, vorgang: Vorgang,
                       nur_ad_id: int | None = None,
                       anzahl: int = 5) -> dict:
    """Vorschlagsmaschine (Konzept 6.1): Top-Slots über AD-Kalender,
    Tool-Termine, Fahrzeiten (Cache; Luftlinie = „geschätzt“)."""
    from app import kalender as kalender_modul
    from app import routing
    jetzt = datetime.now()
    try:
        horizont = int(parameter_holen(session, "vorschlag_horizont_tage", "14"))
        raster = int(parameter_holen(session, "vorschlag_raster_min", "30"))
    except ValueError:
        horizont, raster = 14, 30
    lead_ort = (vorgang.lat, vorgang.lon) if vorgang.lat is not None else None
    kandidaten = ad_kandidaten(session, vorgang, nur_ad_id)
    hinweise = []
    if lead_ort is None:
        hinweise.append("Lead-Adresse ohne Koordinaten („Adresse prüfen“) – "
                        "Umwege werden ohne Fahrzeit bewertet.")

    # Werktage des Horizonts
    tage = []
    tag = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    while len(tage) < horizont:
        tag += timedelta(days=1)
        if tag.weekday() < 6:   # Samstag erlaubt (Wunschzeit samstag)
            tage.append(tag)

    # Bestehende Termine + Startadressen einsammeln → EIN Matrix-Aufruf
    termine_je_ad: dict[int, list[VotTermin]] = {}
    punkte = set()
    for ad in kandidaten:
        termine_je_ad[ad.id] = (session.query(VotTermin)
                                .filter(VotTermin.ad_id == ad.id,
                                        VotTermin.status.in_(("geplant", "bestaetigt")),
                                        VotTermin.beginn >= jetzt,
                                        VotTermin.beginn <= tage[-1] + timedelta(days=1))
                                .order_by(VotTermin.beginn).all())
        for t in termine_je_ad[ad.id]:
            if t.lat is not None:
                punkte.add((t.lat, t.lon))
        profil = ad_profil(session, ad.id)
        if profil.start_lat is not None:
            punkte.add((profil.start_lat, profil.start_lon))
    if lead_ort is not None and punkte:
        routing.matrix_fuellen(session, [lead_ort], list(punkte))
        routing.matrix_fuellen(session, list(punkte), [lead_ort])

    fenster = _wunschzeit_fenster(session, vorgang)
    vorschlaege = []
    for ad in kandidaten:
        profil = ad_profil(session, ad.id)
        dauer = timedelta(minutes=profil.termin_dauer_min or 90)
        puffer = timedelta(minutes=profil.puffer_min or 15)
        start_ort = ((profil.start_lat, profil.start_lon)
                     if profil.start_lat is not None else None)
        belegt_extern = kalender_modul.frei_belegt(
            session, ad, jetzt, tage[-1] + timedelta(days=1))
        for tag in tage:
            zeiten = _arbeitszeiten_von_bis(profil, tag)
            if zeiten is None:
                continue
            tages_termine = [t for t in termine_je_ad[ad.id]
                             if t.beginn.date() == tag.date()]
            if len(tages_termine) >= (profil.max_termine_tag or 4):
                continue
            leerer_tag = not tages_termine
            tour_tag = (lead_ort is not None and any(
                t.lat is not None
                and routing.luftlinie_km(lead_ort, (t.lat, t.lon)) <= 10
                for t in tages_termine))
            minute = zeiten[0]
            while minute + int(dauer.total_seconds() // 60) <= zeiten[1]:
                beginn = tag + timedelta(minutes=minute)
                minute += raster
                if beginn < jetzt + timedelta(hours=2):
                    continue
                ende = beginn + dauer
                # Kollision mit Tool-Terminen (inkl. Puffer)
                belegt = any(
                    beginn < (t.ende or t.beginn + dauer) + puffer
                    and t.beginn - puffer < ende
                    for t in tages_termine)
                if not belegt and belegt_extern:
                    belegt = any(beginn < b_ende and b_von < ende
                                 for b_von, b_ende in belegt_extern)
                if belegt:
                    continue
                # Nachbarn für den Umweg
                vorher = max((t for t in tages_termine
                              if (t.ende or t.beginn) <= beginn),
                             key=lambda t: t.beginn, default=None)
                nachher = min((t for t in tages_termine if t.beginn >= ende),
                              key=lambda t: t.beginn, default=None)
                geschaetzt = False
                if lead_ort is None:
                    umweg = 0.0
                else:
                    def _ort(t):
                        return (t.lat, t.lon) if t is not None and t.lat is not None \
                            else start_ort
                    hin = routing.fahrzeit(session, _ort(vorher), lead_ort)
                    weg = routing.fahrzeit(session, lead_ort, _ort(nachher))
                    direkt = routing.fahrzeit(session, _ort(vorher), _ort(nachher))
                    umweg = max(0.0, hin["minuten"] + weg["minuten"]
                                - direkt["minuten"])
                    geschaetzt = (hin["geschaetzt"] or weg["geschaetzt"]
                                  or direkt["geschaetzt"])
                bewertung = umweg
                wunsch = _im_wunschfenster(fenster, beginn) if fenster else False
                if wunsch:
                    bewertung -= 30
                if tour_tag:
                    bewertung -= 15
                if leerer_tag:
                    bewertung += 20
                if beginn.hour < 9 or beginn.hour >= 17:
                    bewertung += 10
                if (vorgang.score_klasse or "") == "A":
                    bewertung += (beginn.date() - jetzt.date()).days * 2
                vorschlaege.append({
                    "ad": ad, "beginn": beginn, "ende": ende,
                    "umweg": round(umweg), "geschaetzt": geschaetzt,
                    "wunsch": wunsch, "tour_tag": tour_tag,
                    "leerer_tag": leerer_tag, "bewertung": bewertung,
                    "vorher": vorher, "nachher": nachher,
                    "tages_termine": tages_termine,
                })
    vorschlaege.sort(key=lambda v: (v["bewertung"], v["beginn"]))
    # höchstens zwei Slots je AD und Tag in den Top-N (Vielfalt)
    gewaehlt = []
    je_tag: dict = {}
    for v in vorschlaege:
        schluessel = (v["ad"].id, v["beginn"].date())
        if je_tag.get(schluessel, 0) >= 2:
            continue
        je_tag[schluessel] = je_tag.get(schluessel, 0) + 1
        gewaehlt.append(v)
        if len(gewaehlt) >= anzahl:
            break
    return {"vorschlaege": gewaehlt, "hinweise": hinweise,
            "kandidaten": kandidaten}


def termin_buchen(session: Session, vorgang: Vorgang, ad_id: int,
                  beginn: datetime, benutzer=None,
                  quelle: str = "assistent", umweg: int | None = None,
                  umbuchen_id: int | None = None) -> tuple[VotTermin | None, str]:
    """Buchen (Plan 77): Termin, Phase, Kalender, Bestätigung + Erinnerung,
    Benachrichtigung an den AD. Umbuchen setzt den alten Termin auf
    „verschoben“ und plant die Terminänderungs-Mail."""
    from app import geocoding
    from app import kalender as kalender_modul
    ad = session.get(Benutzer, ad_id)
    kunde = session.get(Kunde, vorgang.kunde_id)
    if ad is None or kunde is None:
        return None, "Außendienstler oder Kunde fehlt."
    # Leitplanke 3: im Demo-Modus nur Demo-Leads buchen
    if demo_aktiv(session) and not vorgang.demo:
        return None, ("Terminierung im Demo-Modus nur für Demo-Leads – "
                      "in monday terminieren.")
    profil = ad_profil(session, ad_id)
    adresse = geocoding.lead_adresse(session, vorgang)
    alter_termin = session.get(VotTermin, umbuchen_id) if umbuchen_id else None
    termin = VotTermin(
        vorgang_id=vorgang.id, ad_id=ad_id, beginn=beginn,
        ende=beginn + timedelta(minutes=profil.termin_dauer_min or 90),
        adresse=adresse, lat=vorgang.lat, lon=vorgang.lon,
        status="geplant", quelle=quelle, umweg_min=umweg,
        demo=bool(vorgang.demo),
        erstellt_von=benutzer.id if benutzer else None)
    session.add(termin)
    session.flush()
    if alter_termin is not None:
        alter_termin.status = "verschoben"
        kalender_modul.termin_loeschen(session, alter_termin)
        mail_planen(session, vorgang, "terminaenderung", termin=termin)
        aktivitaet(session, vorgang.id, "termin",
                   f"Termin umgebucht auf {beginn.strftime('%d.%m.%Y %H:%M')} "
                   f"bei {ad.name}", benutzer=benutzer)
    else:
        aktivitaet(session, vorgang.id, "termin",
                   f"Termin gebucht {beginn.strftime('%d.%m.%Y %H:%M')} bei "
                   f"{ad.name}"
                   + (f" (+{umweg} Min)" if umweg is not None else ""),
                   benutzer=benutzer)
        mail_planen(session, vorgang, "terminbestaetigung", termin=termin)
    mail_planen(session, vorgang, "terminerinnerung", termin=termin,
                geplant_am=beginn - timedelta(hours=24))
    kalender_modul.termin_schreiben(session, termin, vorgang, kunde, ad)
    vorgang.lead_phase = "terminiert"
    vorgang.terminiert_am = datetime.now()
    vorgang.naechste_aktion_am = None
    benachrichtigen(session, [ad_id],
                    f"Neuer VOT-Termin {beginn.strftime('%d.%m. %H:%M')}: "
                    f"{kunde.anzeige_name}, {kunde.ort or '?'}",
                    f"/lead-management/lead/{vorgang.id}")
    session.flush()
    return termin, "Termin gebucht."


def termin_no_show(session: Session, termin: VotTermin, grund: str,
                   text: str, status: str = "no_show",
                   benutzer=None) -> None:
    """No-Show / Absage: Termin-Status, Lead zurück auf Qualifiziert,
    sofortige nächste Aktion, Info an den Leadmanager."""
    from app import kalender as kalender_modul
    termin.status = status
    termin.grund_text = grund + (f" – {text}" if text else "")
    kalender_modul.termin_loeschen(session, termin)
    vorgang = session.get(Vorgang, termin.vorgang_id)
    if vorgang is not None:
        vorgang.lead_phase = "qualifiziert"
        vorgang.naechste_aktion_am = datetime.now()
        aktivitaet(session, vorgang.id, "termin",
                   f"Termin {VOT_STATUS_NAMEN_LOKAL.get(status, status)}: "
                   f"{termin.grund_text}", benutzer=benutzer)
        if vorgang.leadmanager_id:
            kunde = session.get(Kunde, vorgang.kunde_id)
            benachrichtigen(session, [vorgang.leadmanager_id],
                            f"Termin {VOT_STATUS_NAMEN_LOKAL.get(status, status)}: "
                            f"{kunde.anzeige_name if kunde else '?'} – "
                            f"{termin.grund_text}",
                            f"/lead-management/lead/{vorgang.id}")
    session.flush()


VOT_STATUS_NAMEN_LOKAL = {"no_show": "No-Show", "abgesagt": "abgesagt",
                          "erfolgt": "erfolgt"}


def monday_termine_ableiten(session: Session) -> int:
    """Beim Sync-Lauf: VOT-Datum der monday-Leads → vot_termine
    (quelle=monday, rein lesend; Änderung in monday überschreibt den
    Tool-Eintrag, solange quelle=monday bleibt)."""
    anzahl = 0
    leads = {l.id: l for l in session.query(Lead)
             if l.vot_datum is not None}
    for vorgang in (session.query(Vorgang)
                    .filter(Vorgang.lead_id.in_(set(leads) or {0}))):
        lead = leads[vorgang.lead_id]
        profil = ad_profil(session, lead.benutzer_id or 0)
        dauer = timedelta(minutes=profil.termin_dauer_min or 90)
        termin = (session.query(VotTermin)
                  .filter(VotTermin.vorgang_id == vorgang.id,
                          VotTermin.quelle == "monday").first())
        if termin is None:
            termin = VotTermin(vorgang_id=vorgang.id, quelle="monday",
                               status="geplant", demo=False)
            session.add(termin)
        if termin.beginn != lead.vot_datum or termin.ad_id != lead.benutzer_id:
            termin.beginn = lead.vot_datum
            termin.ende = lead.vot_datum + dauer
            termin.ad_id = lead.benutzer_id
            termin.adresse = ", ".join(x for x in (
                lead.strasse, f"{lead.plz} {lead.ort}".strip()) if x)
            anzahl += 1
    session.flush()
    return anzahl


# --- Phase 79: Board, Lead-Akte-Kontext, Startportal-Kacheln, Cockpit ---------------

BOARD_SPALTEN = ["neu", "in_kontaktierung", "qualifiziert", "terminiert",
                 "erfasst", "angebot", "gewonnen"]
SEITEN_PHASEN = ("zurueckgestellt", "nicht_erreicht", "unqualifiziert")


def erwartungswert(session: Session, kunde: Kunde | None) -> int:
    """Erwarteter Auftragswert (Cent, brutto) über die Interessen-Sparten."""
    if kunde is None:
        return 0
    summe = 0
    for sparte in (kunde.interesse or "").split(","):
        sparte = sparte.strip()
        if sparte in ("WP", "PV", "KL", "WB"):
            try:
                summe += int(parameter_holen(session,
                                             f"erwartungswert_{sparte}", "0"))
            except ValueError:
                pass
    return summe


def board_daten(session: Session, benutzer, filter_werte: dict) -> dict:
    """Karten je Spalte (Karte = Vorgang) + Kopfzahlen/-summen (Plan 79)."""
    jetzt = datetime.now()
    abfrage = session.query(Vorgang).filter(Vorgang.lead_phase.isnot(None))
    if filter_werte.get("meine") and benutzer is not None:
        abfrage = abfrage.filter(Vorgang.leadmanager_id == benutzer.id)
    if filter_werte.get("quelle_id"):
        abfrage = abfrage.filter(Vorgang.quelle_id == int(filter_werte["quelle_id"]))
    if filter_werte.get("klasse"):
        abfrage = abfrage.filter(Vorgang.score_klasse == filter_werte["klasse"])
    vorgaenge = abfrage.all()
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({v.kunde_id for v in vorgaenge} or {0}))}
    quellen = {q.id: q for q in session.query(LeadQuelle)}
    benutzer_alle = {b.id: b for b in session.query(Benutzer)}
    mehrfach: dict[int, int] = {}
    for v in session.query(Vorgang):
        mehrfach[v.kunde_id] = mehrfach.get(v.kunde_id, 0) + 1
    aktive_termine: dict[int, VotTermin] = {}
    for t in (session.query(VotTermin)
              .filter(VotTermin.status.in_(("geplant", "bestaetigt")))
              .order_by(VotTermin.beginn)):
        aktive_termine.setdefault(t.vorgang_id, t)

    spalten = {s: [] for s in BOARD_SPALTEN + ["verloren"]
               + list(SEITEN_PHASEN)}
    grenze_30 = jetzt - timedelta(days=30)
    for v in vorgaenge:
        kunde = kunden.get(v.kunde_id)
        if kunde is None or v.lead_phase not in spalten:
            continue
        if filter_werte.get("sparte") and \
                filter_werte["sparte"] not in (kunde.interesse or ""):
            continue
        if filter_werte.get("plz") and \
                not (kunde.plz or "").startswith(filter_werte["plz"]):
            continue
        suche = (filter_werte.get("q") or "").lower()
        if suche and suche not in " ".join(
                (kunde.vorname or "", kunde.nachname or "",
                 kunde.ort or "")).lower():
            continue
        if filter_werte.get("eingang_von") and (
                v.eingang_am is None
                or v.eingang_am < filter_werte["eingang_von"]):
            continue
        if filter_werte.get("eingang_bis") and (
                v.eingang_am is None
                or v.eingang_am > filter_werte["eingang_bis"]):
            continue
        if (v.lead_phase in ("gewonnen", "verloren")
                and (v.eingang_am or v.angelegt_am) < grenze_30
                and not filter_werte.get("seiten")):
            pass   # Endzustände bleiben (eingeklappte Spalte zeigt 30 Tage)
        termin = aktive_termine.get(v.id)
        spalten[v.lead_phase].append({
            "vorgang": v, "kunde": kunde,
            "quelle": quellen.get(v.quelle_id),
            "sparten": [s.strip() for s in (kunde.interesse or "").split(",")
                        if s.strip()],
            "sla": sla_status(session, v, jetzt) if v.lead_phase == "neu" else None,
            "wiederkehrer": mehrfach.get(v.kunde_id, 0) > 1,
            "monday": v.eingang_art == "monday",
            "ueberfaellig": (v.naechste_aktion_am is not None
                             and v.naechste_aktion_am < jetzt),
            "leadmanager": benutzer_alle.get(v.leadmanager_id),
            "ad": benutzer_alle.get(termin.ad_id) if termin else None,
            "termin": termin,
            "wert": erwartungswert(session, kunde),
        })
    for karten in spalten.values():
        karten.sort(key=lambda k: (k["vorgang"].eingang_am
                                   or k["vorgang"].angelegt_am), reverse=True)
    koepfe = {}
    for phase, karten in spalten.items():
        summe = (sum(k["wert"] for k in karten)
                 if phase in ("terminiert", "erfasst", "angebot", "gewonnen")
                 else None)
        koepfe[phase] = {"anzahl": len(karten), "summe": summe}
    return {"spalten": spalten, "koepfe": koepfe}


def akte_kontext(session: Session, vorgang: Vorgang) -> dict:
    """Lead-Kopfblock + Reiter für die Vorgangsakte (Phase 79)."""
    import json as json_modul

    from app import leadmanagement_logik
    from app.models import KommunikationLog, VorgangsNotiz
    logik = leadmanagement_logik.hole_logik()
    kunde = session.get(Kunde, vorgang.kunde_id)
    quelle = session.get(LeadQuelle, vorgang.quelle_id) if vorgang.quelle_id else None
    kampagne = session.get(Kampagne, vorgang.kampagne_id) if vorgang.kampagne_id else None
    benutzer_map = {b.id: b for b in session.query(Benutzer)}

    # Timeline: Aktivitäten ∪ Notizen-Chat (chronologisch absteigend)
    timeline = []
    for a in (session.query(LeadAktivitaet)
              .filter(LeadAktivitaet.vorgang_id == vorgang.id)):
        timeline.append({"zeit": a.zeitpunkt, "typ": a.typ,
                         "ergebnis": a.ergebnis, "text": a.text,
                         "benutzer": benutzer_map.get(a.benutzer_id)})
    for n in (session.query(VorgangsNotiz)
              .filter(VorgangsNotiz.vorgang_id == vorgang.id)):
        timeline.append({"zeit": n.zeit, "typ": "notiz", "ergebnis": None,
                         "text": n.text,
                         "benutzer": benutzer_map.get(n.benutzer_id)})
    timeline.sort(key=lambda e: e["zeit"], reverse=True)

    # Qualifizierung je Sparte mit Fragetexten
    qualifizierungen = []
    for q in (session.query(LeadQualifizierung)
              .filter(LeadQualifizierung.vorgang_id == vorgang.id)
              .order_by(LeadQualifizierung.sparte)):
        try:
            antworten = json_modul.loads(q.antworten or "{}")
        except ValueError:
            antworten = {}
        zeilen = []
        for frage in logik.fragen_der_sparte(q.sparte):
            if frage.key in antworten:
                wert = antworten[frage.key]
                zeilen.append((frage.frage,
                               ", ".join(wert) if isinstance(wert, list)
                               else str(wert)))
        qualifizierungen.append({"zeile": q, "antworten": zeilen})

    # Score-Aufschlüsselung (Tooltip)
    score_teile = []
    antworten_alle: dict = {}
    for q in (session.query(LeadQualifizierung)
              .filter(LeadQualifizierung.vorgang_id == vorgang.id)):
        try:
            antworten_alle.update(json_modul.loads(q.antworten or "{}"))
        except ValueError:
            pass
    benutzt_keys: set = set()
    benutzt_texte: set = set()
    for regel in logik.scoring:
        if regel.frage_key in benutzt_keys or regel.frage_key not in antworten_alle:
            continue
        frage = logik.frage(regel.frage_key)
        text = frage.frage if frage else regel.frage_key
        if text in benutzt_texte:
            continue
        if leadmanagement_logik.bedingung_trifft(regel.bedingung,
                                                 antworten_alle[regel.frage_key]):
            score_teile.append(f"{text} {regel.bedingung}: "
                               f"{regel.punkte:+d}")
            benutzt_keys.add(regel.frage_key)
            benutzt_texte.add(text)
    kerngebiet = [p.strip() for p in
                  parameter_holen(session, "kerngebiet_plz", "").split(",")
                  if p.strip()]
    if kunde is not None and kunde.plz and any(
            kunde.plz.startswith(p) for p in kerngebiet):
        score_teile.append("Kerngebiet-PLZ: +10")
    if quelle is not None and quelle.score_bonus:
        score_teile.append(f"Quelle {quelle.name}: {quelle.score_bonus:+d}")

    termine = (session.query(VotTermin)
               .filter(VotTermin.vorgang_id == vorgang.id)
               .order_by(VotTermin.beginn.desc()).all())
    aktiver_termin = next((t for t in termine
                           if t.status in ("geplant", "bestaetigt")), None)
    try:
        wunschzeiten = json_modul.loads(vorgang.wunschzeiten or "[]")
    except ValueError:
        wunschzeiten = []
    kommunikation = (session.query(KommunikationLog)
                     .filter(KommunikationLog.vorgang_id == vorgang.id)
                     .order_by(KommunikationLog.geplant_am.desc())
                     .limit(20).all())
    mehrfach = (session.query(Vorgang)
                .filter(Vorgang.kunde_id == vorgang.kunde_id).count() > 1)
    return {
        "quelle": quelle, "kampagne": kampagne,
        "sla": sla_status(session, vorgang),
        "score_teile": score_teile,
        "leadmanager": benutzer_map.get(vorgang.leadmanager_id),
        "ad": (benutzer_map.get(aktiver_termin.ad_id)
               if aktiver_termin else None),
        "phasen": LEAD_PHASEN_ANZEIGE,
        "wunschzeiten": wunschzeiten,
        "timeline": timeline,
        "qualifizierungen": qualifizierungen,
        "termine": termine, "aktiver_termin": aktiver_termin,
        "kommunikation": kommunikation,
        "wiederkehrer": mehrfach,
        "leadmanager_wahl": [b for b in benutzer_map.values()
                             if b.aktiv and (b.lm_aktiv or b.rolle == "admin"
                                             or b.hat_rolle("leadmanagement")
                                             or b.rolle == "innendienst")],
        "no_show_gruende": logik.gruende_der_phase("no_show"),
        "sparten": [s.strip() for s in ((kunde.interesse or "") if kunde else "").split(",")
                    if s.strip()],
    }


LEAD_PHASEN_ANZEIGE = ["neu", "in_kontaktierung", "qualifiziert", "terminiert",
                       "erfasst", "angebot", "gewonnen"]


def startseiten_kacheln_leads(session: Session) -> dict:
    """Portal-Karte Lead-Management (Phase 79): Neue Leads (+SLA rot),
    Jetzt anrufen, Wiedervorlagen heute, Termine diese Woche (je AD),
    Posteingang unklar."""
    from app.models import LeadPosteingang
    jetzt = datetime.now()
    neue = (session.query(Vorgang)
            .filter(Vorgang.lead_phase == "neu").all())
    sla_rot = sum(1 for v in neue
                  if sla_status(session, v, jetzt)["farbe"] == "rot")
    faellig = (session.query(Vorgang)
               .filter(Vorgang.lead_phase.in_(("neu", "in_kontaktierung")),
                       Vorgang.naechste_aktion_am.isnot(None),
                       Vorgang.naechste_aktion_am <= jetzt).count())
    heute_ende = jetzt.replace(hour=23, minute=59, second=59)
    wiedervorlagen = (session.query(Vorgang)
                      .filter(Vorgang.lead_phase == "zurueckgestellt",
                              Vorgang.zurueckgestellt_bis.isnot(None),
                              Vorgang.zurueckgestellt_bis <= heute_ende)
                      .count())
    woche_ende = jetzt + timedelta(days=7 - jetzt.weekday())
    termine = (session.query(VotTermin)
               .filter(VotTermin.status.in_(("geplant", "bestaetigt")),
                       VotTermin.beginn >= jetzt.replace(hour=0, minute=0),
                       VotTermin.beginn < woche_ende).all())
    je_ad: dict[int, int] = {}
    for t in termine:
        if t.ad_id:
            je_ad[t.ad_id] = je_ad.get(t.ad_id, 0) + 1
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    untertitel = " / ".join(
        f"{anzahl} {benutzer_map[ad_id].name.split()[0] if ad_id in benutzer_map else '?'}"
        for ad_id, anzahl in sorted(je_ad.items(), key=lambda x: -x[1])[:3])
    posteingang = (session.query(LeadPosteingang)
                   .filter(LeadPosteingang.status == "offen").count())
    return {
        "neue": len(neue), "sla_rot": sla_rot, "faellig": faellig,
        "wiedervorlagen": wiedervorlagen, "termine_woche": len(termine),
        "termine_untertitel": untertitel, "posteingang": posteingang,
    }


def cockpit_daten(session: Session) -> dict:
    """Cockpit (Phase 79): heute/diese Woche je Leadmanager + je AD."""
    jetzt = datetime.now()
    heute_start = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    woche_start = heute_start - timedelta(days=heute_start.weekday())
    benutzer_map = {b.id: b for b in session.query(Benutzer)}

    def _lm_zahlen(seit: datetime) -> dict:
        zahlen: dict[int, dict] = {}
        for a in (session.query(LeadAktivitaet)
                  .filter(LeadAktivitaet.zeitpunkt >= seit)):
            if a.benutzer_id is None:
                continue
            eintrag = zahlen.setdefault(a.benutzer_id, {
                "anrufe": 0, "erreicht": 0, "qualifiziert": 0,
                "terminiert": 0})
            if a.typ == "anruf":
                eintrag["anrufe"] += 1
                if a.ergebnis == "erreicht":
                    eintrag["erreicht"] += 1
            elif a.typ == "status" and a.text.startswith("Qualifiziert"):
                eintrag["qualifiziert"] += 1
            elif a.typ == "termin" and a.text.startswith("Termin gebucht"):
                eintrag["terminiert"] += 1
        return zahlen

    ueberfaellig: dict[int, int] = {}
    for v in (session.query(Vorgang)
              .filter(Vorgang.naechste_aktion_am.isnot(None),
                      Vorgang.naechste_aktion_am < jetzt,
                      Vorgang.lead_phase.in_(("neu", "in_kontaktierung",
                                              "qualifiziert")))):
        if v.leadmanager_id:
            ueberfaellig[v.leadmanager_id] = \
                ueberfaellig.get(v.leadmanager_id, 0) + 1

    ad_zahlen: dict[int, dict] = {}
    for t in (session.query(VotTermin)
              .filter(VotTermin.beginn >= woche_start)):
        if not t.ad_id:
            continue
        eintrag = ad_zahlen.setdefault(t.ad_id, {"termine": 0, "no_shows": 0})
        eintrag["termine"] += 1
        if t.status == "no_show":
            eintrag["no_shows"] += 1

    sla_rot = [v for v in session.query(Vorgang)
               .filter(Vorgang.lead_phase == "neu")
               if sla_status(session, v, jetzt)["farbe"] == "rot"]
    return {
        "heute": _lm_zahlen(heute_start), "woche": _lm_zahlen(woche_start),
        "ueberfaellig": ueberfaellig, "ad": ad_zahlen,
        "sla_rot": sla_rot, "benutzer_map": benutzer_map,
        "kunden_map": {k.id: k for k in session.query(Kunde)},
    }
