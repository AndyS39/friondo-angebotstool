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
