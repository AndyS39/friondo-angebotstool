# Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 106): Kundenkartei dreispaltig
# (B1–B8, F10 Vorab-Angebot, F11 Nachbearbeitung). Fachlogik der Kartei –
# Kontext für das Template, Stammdaten-Speichern mit Aktivität, Pflichtfeld-
# Status, Terminierung (B8, Vertrag mit Phase 108: Terminstatus „vorgemerkt“),
# Wiedervorlage/Zurückstellen/Nachbearbeitung. Router: app/routers/lm_kartei.py.
# Prozesswissen (Objektarten, Gründe, Status-Farben) kommt aus der Steuerdatei,
# Pflichtfelder und Fristen aus den LeadParametern.

import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import lead_v2
from app import leadmanagement as kern
from app.models import (AdProfil, Angebot, Benutzer, Erfassung, GalerieDatei,
                        Kampagne, KommunikationLog, Kunde, Lead, LeadAktivitaet,
                        LeadQuelle, Todo, Vorgang, VorgangsNotiz, VotTermin,
                        ANRUF_ERGEBNIS_NAMEN, INTERESSE_CODES, INTERESSEN,
                        LEAD_PHASEN_NAMEN, TERMIN_TYP_NAMEN, VOT_STATUS_NAMEN)

ANREDEN = ["", "Herr", "Frau", "Familie", "Firma"]

# Filtergruppen der Timeline (Reiter Mitte): Aktivitätstyp → Gruppe
TIMELINE_GRUPPEN = [("anruf", "Anrufe"), ("notiz", "Notizen"), ("mail", "E-Mails"),
                    ("termin", "Termine"), ("status", "Status"), ("system", "System")]
_TYP_GRUPPE = {"anruf": "anruf", "notiz": "notiz", "mail_aus": "mail", "mail_ein": "mail",
               "mail": "mail", "termin": "termin", "status": "status",
               "system": "system", "import": "system", "whatsapp": "mail", "sms": "mail"}
_TYP_TITEL = {"anruf": "Anruf", "notiz": "Notiz", "mail_aus": "E-Mail gesendet",
              "mail_ein": "E-Mail eingegangen", "termin": "Termin", "status": "Status",
              "system": "System", "import": "Import", "whatsapp": "WhatsApp", "sms": "SMS"}

# Anzeigenamen der Pflichtfeld-Keys (Parameter `pflichtfelder`) – die Zählung
# selbst liefert lead_v2.pflichtfelder_offen (B2).
PFLICHT_LABELS = {"anrede": "Anrede", "vorname": "Vorname", "nachname": "Nachname",
                  "telefon": "Telefon", "email": "E-Mail", "strasse": "Straße",
                  "plz": "PLZ", "ort": "Ort", "vertriebskanal": "Vertriebskanal",
                  "interesse": "Interesse", "objektart": "Objektart",
                  "parteien": "Anzahl Parteien", "rechnungsadresse": "Rechnungsadresse"}
# lead_v2.pflichtfelder_offen liefert feld.capitalize() („Strasse“, „Email“) –
# für Zähler-Tooltip, Fehlliste und Meldungen lesbar machen (nur Anzeige)
_PFLICHT_ANZEIGE = {"Strasse": "Straße", "Email": "E-Mail", "Plz": "PLZ"}


def pflicht_offen_namen(session: Session, kunde: Kunde | None,
                        vorgang: Vorgang | None = None) -> list:
    """Anzeigenamen der offenen Pflichtfelder (B2) – Zählung aus lead_v2."""
    if kunde is None:
        return []
    return [_PFLICHT_ANZEIGE.get(name, name)
            for name in lead_v2.pflichtfelder_offen(session, kunde, vorgang)]

# Terminstatus, die als „Termin gesetzt“ für die Terminierung (B8) zählen –
# vorgemerkt legt Phase 108 an, solange Pflichtfelder offen sind.
TERMIN_OFFEN = ("vorgemerkt", "geplant", "bestaetigt")
TERMIN_STATUS_NAMEN = dict(VOT_STATUS_NAMEN, vorgemerkt="Vorgemerkt")
TERMIN_MEDIUM_NAMEN = {"vor_ort": "vor Ort", "telefon": "Telefon", "teams": "Teams"}

# Objektart-Code (kunden.objektart) → Antwortcode O01/PO01 des Erfassungsbogens
# (konfigurator_logik Blatt Fragen: EFH | 2FH | REH | RMH | MFH | Gewerbe).
O01_CODES = {"EFH": "EFH", "RH": "RMH", "REH": "REH", "MFH": "MFH"}


# --- kleine Helfer -------------------------------------------------------------------

def initialen(name: str) -> str:
    """„Peter Testmann“ → „PT“, „K. Sarigiannis“ → „KS“, Firma → erste zwei Zeichen."""
    teile = [t for t in re.split(r"[\s,.\-]+", (name or "").strip()) if t]
    if not teile:
        return "?"
    if len(teile) == 1:
        return teile[0][:2].upper()
    return (teile[0][0] + teile[-1][0]).upper()


def kunden_initialen(kunde: Kunde | None) -> str:
    if kunde is None:
        return "?"
    if kunde.firma and not (kunde.vorname or kunde.nachname):
        return initialen(kunde.firma)
    return initialen(" ".join(t for t in (kunde.vorname, kunde.nachname) if t) or kunde.firma)


def dauer_text(sekunden) -> str:
    if not sekunden:
        return ""
    sekunden = int(sekunden)
    return f"{sekunden // 60}:{sekunden % 60:02d} Min"


def wv_tage(session: Session) -> int:
    """Standard-Wiedervorlage in Tagen (Parameter wv_meldet_sich_tage, F11/5a)."""
    try:
        return max(1, int(kern.parameter_holen(session, "wv_meldet_sich_tage", "14")))
    except ValueError:
        return 14


def nachbearbeitung_grund(session: Session | None = None) -> str:
    """Grundtext aus dem Blatt Gruende (phase zurueckgestellt) – Zeile, die mit
    „Nachbearbeitung“ beginnt; Rückfall auf den Plan-Wortlaut (A-4)."""
    from app import leadmanagement_logik
    for g in leadmanagement_logik.hole_logik().gruende_der_phase("zurueckgestellt"):
        if g.grund.lower().startswith("nachbearbeitung"):
            return g.grund
    return "Nachbearbeitung, noch nicht bereit für VOT"


def _benutzer_map(session: Session) -> dict:
    return {b.id: b for b in session.query(Benutzer)}


# --- Pflichtfelder (B2) --------------------------------------------------------------

def pflicht_status(session: Session, kunde: Kunde, vorgang: Vorgang | None = None) -> dict:
    """offen = Anzeigenamen (lead_v2.pflichtfelder_offen), keys = Feld-Keys für
    die rote Umrandung im Formular, labels = Anzeigename je Key."""
    offen = pflicht_offen_namen(session, kunde, vorgang)
    keys: set = set()
    for feld in lead_v2.pflichtfelder(session):
        if feld == "interesse":
            if not (kunde.interesse or "").strip():
                keys.add("interesse")
        elif feld == "vertriebskanal":
            if not (kunde.vertriebskanal or "").strip():
                keys.add("vertriebskanal")
        else:
            wert = getattr(kunde, feld, None)
            if wert is None or str(wert).strip() == "":
                keys.add(feld)
    if (kunde.objektart or "").upper() == "MFH":
        if not kunde.parteien:
            keys.add("parteien")
        if not ((kunde.rechnung_strasse or "").strip() and (kunde.rechnung_ort or "").strip()):
            keys.add("rechnungsadresse")
    pflicht_keys = set(lead_v2.pflichtfelder(session))
    # „offen_keys“ statt „keys“: Jinja löst pflicht.keys sonst als dict-Methode auf
    return {"offen": offen, "offen_keys": keys, "pflicht": pflicht_keys,
            "labels": PFLICHT_LABELS}


# --- Timeline / E-Mail-Verlauf (B4) --------------------------------------------------

def timeline(session: Session, vorgang: Vorgang, benutzer_map: dict | None = None) -> list:
    """Aktivitäten ∪ Notizen-Chat ∪ Kommunikations-Warteschlange als Karten
    (Titel, Zeit, Autor, Text, Gruppe für den Filter), neueste zuerst."""
    benutzer_map = benutzer_map or _benutzer_map(session)
    karten = []
    for a in (session.query(LeadAktivitaet)
              .filter(LeadAktivitaet.vorgang_id == vorgang.id)):
        typ = a.typ or "system"
        gruppe = _TYP_GRUPPE.get(typ, "system")
        titel = _TYP_TITEL.get(typ, typ.capitalize())
        if typ == "anruf" and a.ergebnis:
            titel = "Anruf: " + ANRUF_ERGEBNIS_NAMEN.get(a.ergebnis, a.ergebnis)
        elif typ in ("status", "termin", "system", "import"):
            kurz = (a.text or "").split(":")[0].strip()
            if kurz and len(kurz) <= 60:
                titel = kurz
        autor = benutzer_map.get(a.benutzer_id)
        karten.append({"id": f"a{a.id}", "quelle": "aktivitaet", "typ": typ,
                       "gruppe": gruppe, "titel": titel, "zeit": a.zeitpunkt,
                       "autor": autor.name if autor else "System",
                       "autor_id": a.benutzer_id, "text": a.text or "",
                       "ergebnis": a.ergebnis, "dauer_sek": a.dauer_sek,
                       "dauer": dauer_text(a.dauer_sek), "richtung": a.richtung,
                       "naechste": a.naechste_aktion_am})
    for n in (session.query(VorgangsNotiz)
              .filter(VorgangsNotiz.vorgang_id == vorgang.id)):
        karten.append({"id": f"n{n.id}", "quelle": "notiz", "typ": "notiz",
                       "gruppe": "notiz", "titel": "Notiz" + (f" · {n.herkunft}" if n.herkunft else ""),
                       "zeit": n.zeit, "autor": n.benutzer_name or "System",
                       "autor_id": n.benutzer_id, "text": n.text or "",
                       "ergebnis": None, "dauer_sek": None, "dauer": "",
                       "richtung": None, "naechste": None})
    for k in (session.query(KommunikationLog)
              .filter(KommunikationLog.vorgang_id == vorgang.id)):
        autor = benutzer_map.get(k.erstellt_von)
        karten.append({"id": f"k{k.id}", "quelle": "kommunikation", "typ": "mail",
                       "gruppe": "mail",
                       "titel": f"E-Mail {k.vorlage_key or k.kanal} · {k.status}",
                       "zeit": k.gesendet_am or k.geplant_am,
                       "autor": autor.name if autor else "Automatik",
                       "autor_id": k.erstellt_von,
                       "text": (k.betreff or "") + (f"\n{k.fehler_text}" if k.fehler_text else ""),
                       "ergebnis": k.status, "dauer_sek": None, "dauer": "",
                       "richtung": "aus", "naechste": None})
    karten.sort(key=lambda e: e["zeit"] or datetime.min, reverse=True)
    return karten


def mail_verlauf(session: Session, vorgang: Vorgang, benutzer, benutzer_map: dict,
                 angebote: list | None = None) -> list:
    """E-Mail-Verlauf: kommunikation_log (ausgehend; eigene = erstellt_von ich,
    automatisiert = ohne Benutzer, kollegen = anderer Benutzer) ∪ angebots_mails
    der Angebote des Vorgangs (ein-/ausgehend; Absender ↔ Benutzer-E-Mail)."""
    from app.models import AngebotsMail
    mails = []
    ich = benutzer.id if benutzer is not None else None
    for k in (session.query(KommunikationLog)
              .filter(KommunikationLog.vorgang_id == vorgang.id)):
        if k.erstellt_von is None:
            herkunft = "automatisiert"
        elif k.erstellt_von == ich:
            herkunft = "eigene"
        else:
            herkunft = "kollegen"
        autor = benutzer_map.get(k.erstellt_von)
        mails.append({"id": f"k{k.id}", "quelle": "kommunikation", "richtung": "aus",
                      "herkunft": herkunft, "zeit": k.gesendet_am or k.geplant_am,
                      "betreff": k.betreff or f"({k.vorlage_key})", "partner": k.an,
                      "status": k.status, "vorlage_key": k.vorlage_key,
                      "autor": autor.name if autor else "Automatik",
                      "text": k.body_html or "", "html": bool(k.body_html),
                      "anhang": bool(k.anhang_pfad), "fehler": k.fehler_text or "",
                      "log_id": k.id})
    if angebote is None:
        angebote = session.query(Angebot).filter(Angebot.vorgang_id == vorgang.id).all()
    if angebote:
        mail_zu_benutzer = {(b.email or "").strip().lower(): b for b in benutzer_map.values()
                            if (b.email or "").strip()}
        for m in (session.query(AngebotsMail)
                  .filter(AngebotsMail.angebot_id.in_([a.id for a in angebote]))):
            if m.eingehend:
                herkunft, richtung = "kunde", "ein"
            else:
                absender = mail_zu_benutzer.get((m.von_email or "").strip().lower())
                richtung = "aus"
                herkunft = ("eigene" if absender is not None and absender.id == ich
                            else "kollegen" if absender is not None else "automatisiert")
            mails.append({"id": f"m{m.id}", "quelle": "angebot", "richtung": richtung,
                          "herkunft": herkunft, "zeit": m.empfangen_am,
                          "betreff": m.betreff or "(ohne Betreff)",
                          "partner": m.von_name or m.von_email, "status": "",
                          "vorlage_key": "", "autor": m.von_name or m.von_email,
                          "text": m.vorschau or "", "html": False, "anhang": False,
                          "fehler": "", "log_id": None})
    mails.sort(key=lambda e: e["zeit"] or datetime.min, reverse=True)
    return mails


# --- Termine / Terminierung (B8) -----------------------------------------------------

def termine_des_vorgangs(session: Session, vorgang: Vorgang) -> list:
    return (session.query(VotTermin).filter(VotTermin.vorgang_id == vorgang.id)
            .order_by(VotTermin.beginn.desc().nullslast(), VotTermin.id.desc()).all())


def terminierung_pruefung(session: Session, kunde: Kunde, vorgang: Vorgang,
                          termine: list | None = None) -> dict:
    """B8: bereit, wenn kein Pflichtfeld offen UND ein Vor-Ort-Termin mit
    Status vorgemerkt/geplant existiert. fehlend = Liste für den Hinweis."""
    termine = termine if termine is not None else termine_des_vorgangs(session, vorgang)
    pflicht_fehlt = pflicht_offen_namen(session, kunde, vorgang) if kunde else ["Kunde"]
    kandidaten = [t for t in termine
                  if t.status in ("vorgemerkt", "geplant") and (t.typ or "vot") == "vot"]
    # vorgemerkte Termine zuerst (die löst der Button ein), sonst der nächste geplante
    kandidaten.sort(key=lambda t: (0 if t.status == "vorgemerkt" else 1,
                                   t.beginn or datetime.max))
    termin = kandidaten[0] if kandidaten else None
    fehlend = list(pflicht_fehlt)
    if termin is None:
        fehlend.append("Termin (vorgemerkt/geplant)")
    # schon erledigt: geplanter Termin, Phase terminiert, nichts offen
    erledigt = (termin is not None and termin.status == "geplant"
                and vorgang.lead_phase == "terminiert" and not pflicht_fehlt)
    return {"bereit": not fehlend and not erledigt, "fehlend": fehlend,
            "termin": termin, "erledigt": erledigt}


def _mail_geplant(session: Session, termin: VotTermin, vorlage_key: str) -> bool:
    return bool(session.query(KommunikationLog)
                .filter(KommunikationLog.termin_id == termin.id,
                        KommunikationLog.vorlage_key == vorlage_key,
                        KommunikationLog.status != "storniert").count())


def terminierung_ausfuehren(session: Session, vorgang: Vorgang, benutzer=None) -> tuple:
    """Button „Terminierung“ (B8) laut Vertrag im Briefing: Status vorgemerkt →
    geplant, Terminbestätigung (mit ICS) + Erinnerung planen, Kalender
    schreiben, Phase terminiert + terminiert_am, Aktivität, Glocke an den AD.
    Damit ist die Übergabe an „Leads VOT“ erledigt (Tool-Leads laufen über das
    Board Terminiert / Meine Termine). Liefert (ok, meldung)."""
    from app import kalender as kalender_modul
    kunde = session.get(Kunde, vorgang.kunde_id)
    pruefung = terminierung_pruefung(session, kunde, vorgang)
    if pruefung["erledigt"]:
        return False, "Bereits terminiert – Termin ist geplant und bestätigt."
    if pruefung["fehlend"]:
        return False, "Terminierung nicht möglich – es fehlt: " + ", ".join(pruefung["fehlend"])
    if kern.demo_aktiv(session) and not vorgang.demo:
        return False, ("Terminierung im Demo-Modus nur für Demo-Leads – "
                       "in monday terminieren.")
    termin = pruefung["termin"]
    ad = session.get(Benutzer, termin.ad_id) if termin.ad_id else None
    war = termin.status
    termin.status = "geplant"
    if termin.ende is None and termin.beginn is not None:
        profil = kern.ad_profil(session, termin.ad_id) if termin.ad_id else None
        termin.ende = termin.beginn + timedelta(minutes=(getattr(profil, "termin_dauer_min", 90) or 90))
    if not termin.demo:
        termin.demo = bool(vorgang.demo)
    # Mails nur einmal je Termin (Terminbestätigung mit ICS, Erinnerung −24 h)
    if not _mail_geplant(session, termin, "terminbestaetigung"):
        kern.mail_planen(session, vorgang, "terminbestaetigung", termin=termin)
    if termin.beginn is not None and not _mail_geplant(session, termin, "terminerinnerung"):
        kern.mail_planen(session, vorgang, "terminerinnerung", termin=termin,
                         geplant_am=termin.beginn - timedelta(hours=24))
    kalender_ok = False
    if kunde is not None:
        kalender_ok = kalender_modul.termin_schreiben(session, termin, vorgang, kunde, ad)
    vorgang.lead_phase = "terminiert"
    vorgang.terminiert_am = datetime.now()
    vorgang.naechste_aktion_am = None
    vorgang.zurueckgestellt_bis = None
    if vorgang.ad_id is None and termin.ad_id:
        vorgang.ad_id = termin.ad_id          # A-7: Zuständiger AD am Vorgang
    wann = termin.beginn.strftime("%d.%m.%Y %H:%M") if termin.beginn else "ohne Uhrzeit"
    kern.aktivitaet(session, vorgang.id, "termin",
                    f"Terminierung: Termin {wann}"
                    + (f" bei {ad.name}" if ad else "")
                    + (f" ({TERMIN_STATUS_NAMEN.get(war, war)} → geplant)" if war != "geplant" else "")
                    + " – Terminbestätigung geplant, Kalender "
                    + ("geschrieben" if kalender_ok else "nicht geschrieben (Sync aus)")
                    + ", Phase Terminiert.", benutzer=benutzer)
    if termin.ad_id:
        kern.benachrichtigen(session, [termin.ad_id],
                             f"VOT-Termin terminiert {termin.beginn.strftime('%d.%m. %H:%M') if termin.beginn else ''}: "
                             f"{kunde.anzeige_name if kunde else '?'}, {kunde.ort if kunde and kunde.ort else '?'}",
                             f"/lead-management/lead/{vorgang.id}")
    session.flush()
    return True, ("Terminiert: Terminbestätigung geplant, Kalender "
                  + ("geschrieben" if kalender_ok else "übersprungen (Sync aus)")
                  + ", Lead steht in Leads VOT / Board Terminiert.")


# --- Vorab-Angebot (F10, A-3) --------------------------------------------------------

def vorab_angebot_setzen(session: Session, vorgang: Vorgang, benutzer=None) -> tuple:
    """Kennzeichen vorab_angebot, Aktivität; Ziel = bestehende Erfassung mit
    kunde_id (+ lead_id bei monday-Leads). Demo-Leads: nur Kennzeichen/Badge.
    Liefert (meldung, ziel_url oder None)."""
    kunde = session.get(Kunde, vorgang.kunde_id)
    neu = not vorgang.vorab_angebot
    vorgang.vorab_angebot = True
    if neu:
        kern.aktivitaet(session, vorgang.id, "status",
                        "Vorab-Angebot: Erfassung ohne Vor-Ort-Termin gestartet "
                        "(keine Terminbestätigung, Lead springt nach Erfasst/Angebot)",
                        benutzer=benutzer)
    session.flush()
    if vorgang.demo or kunde is None:
        return ("Kennzeichen „Vorab-Angebot“ gesetzt. Demo-Lead – eine Erfassung ist im "
                "Demo-Modus nicht möglich (Badge in der Kartei).", None)
    ziel = f"/erfassung/sparten?kunde_id={kunde.id}"
    if vorgang.lead_id:
        ziel += f"&lead_id={vorgang.lead_id}"
    return "Kennzeichen „Vorab-Angebot“ gesetzt – Erfassung ohne Termin.", ziel


# --- Wiedervorlage / Zurückstellen / Nachbearbeitung (F11) ---------------------------

def grund_pruefen(phase: str, grund: str, text: str) -> str | None:
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    passend = next((g for g in logik.gruende_der_phase(phase) if g.grund == grund), None)
    if passend is None:
        return "Bitte einen Grund aus der Liste wählen."
    if passend.freitext_pflicht and not text:
        return f"Beim Grund „{grund}“ ist der Freitext Pflicht."
    return None


def zurueckstellen(session: Session, vorgang: Vorgang, bis: datetime, grund: str,
                   text: str = "", benutzer=None) -> str | None:
    """Wie die V1-Route (Datum + Grund aus dem Blatt Gruende), aber ohne
    Redirect – liefert einen Fehlertext oder None."""
    fehler = grund_pruefen("zurueckgestellt", grund, text)
    if fehler:
        return fehler
    vorgang.lead_phase = "zurueckgestellt"
    vorgang.zurueckgestellt_bis = bis
    vorgang.zurueckgestellt_grund = (grund + (f" – {text}" if text else ""))[:200]
    vorgang.naechste_aktion_am = None
    kern.aktivitaet(session, vorgang.id, "status",
                    f"Zurückgestellt bis {bis.strftime('%d.%m.%Y')}: "
                    f"{vorgang.zurueckgestellt_grund}", benutzer=benutzer)
    session.flush()
    return None


def wiedervorlage_setzen(session: Session, vorgang: Vorgang, wann: datetime,
                         notiz: str = "", benutzer=None) -> None:
    """Wiedervorlage ohne Phasenwechsel: naechste_aktion_am + Aktivität (die
    Anrufliste/das Dashboard zeigen sie als fällig)."""
    vorgang.naechste_aktion_am = wann
    kern.aktivitaet(session, vorgang.id, "status",
                    f"Wiedervorlage {wann.strftime('%d.%m.%Y %H:%M')}"
                    + (f": {notiz}" if notiz else ""),
                    benutzer=benutzer, naechste_aktion_am=wann)
    session.flush()


def nachbearbeitung(session: Session, vorgang: Vorgang, bis: datetime | None = None,
                    notiz: str = "", benutzer=None) -> datetime:
    """F11/A-4: Zurückgestellt mit Grund „Nachbearbeitung, noch nicht bereit für
    VOT“ + Pflicht-Wiedervorlage (Vorschlag heute + wv_meldet_sich_tage)."""
    bis = bis or (datetime.now() + timedelta(days=wv_tage(session)))
    bis = bis.replace(hour=0, minute=0, second=0, microsecond=0)
    grund = nachbearbeitung_grund(session)
    vorgang.lead_phase = "zurueckgestellt"
    vorgang.zurueckgestellt_bis = bis
    vorgang.zurueckgestellt_grund = grund[:200]
    vorgang.naechste_aktion_am = None
    kern.aktivitaet(session, vorgang.id, "status",
                    f"Nachbearbeitung – zurückgestellt bis {bis.strftime('%d.%m.%Y')}: {grund}"
                    + (f" – {notiz}" if notiz else ""), benutzer=benutzer)
    session.flush()
    return bis


# --- Stammdaten (B1/B3, C-Z5) ---------------------------------------------------------

def _text(form, name: str, laenge: int = 200) -> str:
    return (form.get(name) or "").strip()[:laenge]


def stammdaten_speichern(session: Session, vorgang: Vorgang, kunde: Kunde, form,
                         benutzer=None) -> tuple:
    """Inline-Speichern der Kontaktfelder: Anrede, Vor-/Nachname, Telefon,
    E-Mail, Adresse, Vertriebskanal (setzt kanden.kanal_manuell), Interessen,
    Objektart (+ Parteien, Rechnungsadresse bei MFH), Quelle/Kampagne,
    Eingangsdatum, Einwilligung Werbung. Jede Änderung als Aktivität.
    Liefert (meldung, fehlerliste)."""
    fehler = []
    aenderungen = []

    def setze(feld: str, neu, label: str):
        alt = getattr(kunde, feld)
        if (neu or "") != (alt or ""):
            setattr(kunde, feld, neu)
            aenderungen.append(f"{label}: „{alt or '–'}“ → „{neu or '–'}“")

    # Nur Felder ändern, die das Formular mitschickt (Teil-Formulare, z. B.
    # Inline-Bearbeitung aus Boards, löschen so nichts versehentlich)
    if "anrede" in form:
        anrede = _text(form, "anrede", 20)
        if anrede not in ANREDEN:
            fehler.append("Anrede unbekannt.")
        else:
            setze("anrede", anrede, "Anrede")
    if "nachname" in form or "firma" in form:
        nachname = _text(form, "nachname", 100) if "nachname" in form else (kunde.nachname or "")
        firma = _text(form, "firma", 200) if "firma" in form else (kunde.firma or "")
        if not nachname and not firma:
            fehler.append("Nachname (oder Firma) ist Pflicht.")
        else:
            if "nachname" in form:
                setze("nachname", nachname, "Nachname")
            if "firma" in form:
                setze("firma", firma, "Firma")
    if "vorname" in form:
        setze("vorname", _text(form, "vorname", 100), "Vorname")
    if "email" in form:
        email = _text(form, "email", 200)
        if email and ("@" not in email or "." not in email.split("@")[-1]):
            fehler.append("E-Mail-Adresse ist ungültig.")
        else:
            setze("email", email, "E-Mail")
    for feld, laenge, label in (("telefon", 50, "Telefon"), ("strasse", 200, "Straße"),
                                ("plz", 10, "PLZ"), ("ort", 100, "Ort")):
        if feld in form:
            setze(feld, _text(form, feld, laenge), label)

    if "vertriebskanal" in form:
        kanal = _text(form, "vertriebskanal", 100)
        if kanal != (kunde.vertriebskanal or ""):
            setze("vertriebskanal", kanal, "Vertriebskanal")
            kunde.kanal_manuell = True        # Sync-Schutz (v9/v21)
            # v23 (Phase 109, G4/OF-G5): Kanalwechsel auf Ausschlusskanal bei
            # zugewiesenem Handelsvertreter → Aktivität + Glocke an leadmanager_id/
            # Leitung, roter Hinweis; Zuweisung bleibt bis zur manuellen Rücknahme
            try:
                from app import lead_handelsvertreter
                session.flush()
                hinweis = lead_handelsvertreter.kanalwechsel_pruefen(session, vorgang, benutzer)
                if hinweis:
                    aenderungen.append(hinweis)
            except Exception:
                pass

    if "interesse_feld" in form:
        gewaehlt = [s for s in form.getlist("interesse") if s in INTERESSE_CODES] \
            if hasattr(form, "getlist") else [s for s in [form.get("interesse")] if s in INTERESSE_CODES]
        interesse = ",".join(s for s in INTERESSE_CODES if s in gewaehlt)
        setze("interesse", interesse, "Interessen")

    if "objektart" in form:
        codes = {code for code, _bez, _p in lead_v2.objektarten(session)}
        objektart = _text(form, "objektart", 10).upper()
        if objektart and objektart not in codes:
            fehler.append("Objektart unbekannt.")
        else:
            setze("objektart", objektart or None, "Objektart")
        roh = _text(form, "parteien", 5)
        if objektart == "MFH":
            if roh.isdigit() and int(roh) > 0:
                if kunde.parteien != int(roh):
                    aenderungen.append(f"Anzahl Parteien: {kunde.parteien or '–'} → {roh}")
                    kunde.parteien = int(roh)
            elif roh:
                fehler.append("Anzahl Parteien muss eine Zahl > 0 sein.")
            for feld, label in (("rechnung_name", "Rechnung Name"),
                                ("rechnung_strasse", "Rechnung Straße"),
                                ("rechnung_plz", "Rechnung PLZ"),
                                ("rechnung_ort", "Rechnung Ort")):
                if feld in form:
                    setze(feld, _text(form, feld, 200 if feld != "rechnung_plz" else 10), label)
        elif roh.isdigit() and int(roh) > 0 and kunde.parteien != int(roh):
            kunde.parteien = int(roh)
            aenderungen.append(f"Anzahl Parteien: {roh}")

    # Vorgangsfelder: Quelle / Kampagne / Eingangsdatum
    if "quelle_id" in form:
        roh = _text(form, "quelle_id", 10)
        neu = int(roh) if roh.isdigit() else None
        if neu != vorgang.quelle_id and (neu is None or session.get(LeadQuelle, neu) is not None):
            alt = session.get(LeadQuelle, vorgang.quelle_id) if vorgang.quelle_id else None
            neu_q = session.get(LeadQuelle, neu) if neu else None
            vorgang.quelle_id = neu
            aenderungen.append(f"Quelle: „{alt.name if alt else '–'}“ → „{neu_q.name if neu_q else '–'}“")
    if "kampagne_id" in form:
        roh = _text(form, "kampagne_id", 10)
        neu = int(roh) if roh.isdigit() else None
        if neu != vorgang.kampagne_id and (neu is None or session.get(Kampagne, neu) is not None):
            alt = session.get(Kampagne, vorgang.kampagne_id) if vorgang.kampagne_id else None
            neu_k = session.get(Kampagne, neu) if neu else None
            vorgang.kampagne_id = neu
            aenderungen.append(f"Kampagne: „{alt.name if alt else '–'}“ → „{neu_k.name if neu_k else '–'}“")
    if "eingang_am" in form:
        roh = _text(form, "eingang_am", 20)
        if roh:
            try:
                neu = datetime.strptime(roh, "%Y-%m-%dT%H:%M")
            except ValueError:
                try:
                    neu = datetime.strptime(roh, "%Y-%m-%d")
                except ValueError:
                    neu = None
                    fehler.append("Eingangsdatum ungültig.")
            if neu is not None and neu != vorgang.eingang_am:
                aenderungen.append("Eingangsdatum: "
                                   f"{vorgang.eingang_am.strftime('%d.%m.%Y %H:%M') if vorgang.eingang_am else '–'}"
                                   f" → {neu.strftime('%d.%m.%Y %H:%M')}")
                vorgang.eingang_am = neu

    # Einwilligung Werbung (C-Z2): Setzen/Widerrufen mit Datum + Quelle, eigene Aktivität
    einwilligung_text = None
    if "einwilligung_feld" in form:
        neu = form.get("einwilligung_werbung") in ("1", "on", "true")
        quelle = _text(form, "einwilligung_quelle", 20) or (vorgang.einwilligung_quelle or "manuell")
        roh = _text(form, "einwilligung_am", 10)
        datum = None
        if roh:
            try:
                datum = datetime.strptime(roh, "%Y-%m-%d")
            except ValueError:
                fehler.append("Datum der Einwilligung ungültig.")
        if neu != bool(vorgang.einwilligung_werbung) or (neu and datum and datum != vorgang.einwilligung_werbung_am) \
                or (neu and quelle != (vorgang.einwilligung_quelle or "")):
            vorgang.einwilligung_werbung = neu
            vorgang.einwilligung_werbung_am = (datum or datetime.now()) if neu else None
            vorgang.einwilligung_quelle = quelle if neu else vorgang.einwilligung_quelle
            einwilligung_text = ("Einwilligung Werbung: "
                                 + (f"ja ({vorgang.einwilligung_werbung_am.strftime('%d.%m.%Y')}, {quelle})"
                                    if neu else "nein (widerrufen)"))

    if fehler:
        return "Nicht gespeichert: " + " ".join(fehler), fehler
    if aenderungen:
        kern.aktivitaet(session, vorgang.id, "status",
                        "Stammdaten geändert: " + "; ".join(aenderungen), benutzer=benutzer)
    if einwilligung_text:
        kern.aktivitaet(session, vorgang.id, "status", einwilligung_text, benutzer=benutzer)
    session.flush()
    anzahl = len(aenderungen) + (1 if einwilligung_text else 0)
    if not anzahl:
        return "Keine Änderung.", []
    return f"Gespeichert ({anzahl} Änderung{'en' if anzahl != 1 else ''}).", []


# --- Vorbelegung WP-Bogen (B3/O01) ----------------------------------------------------

def objektart_vorbelegung(session: Session, vorgang: Vorgang, sparte: str = "WP") -> dict:
    """Weg (c) der Erfassungs-Vorbelegung: kunden.objektart → O01 (WP) bzw.
    PO01 (PV) als Antwortcode des Bogens (O01_CODES; das Blatt Objektarten
    liefert Texte, der Bogen erwartet Codes), kunden.parteien → O03 bei MFH.
    Format wie leadmanagement.erfassungs_vorbelegung ({key: {wert, info}});
    wird per hook_edit in routers/erfassung.py eingehängt."""
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang else None
    return objektart_vorbelegung_kunde(kunde, sparte)


def objektart_vorbelegung_kunde(kunde: Kunde | None, sparte: str = "WP") -> dict:
    """Wie objektart_vorbelegung, aber direkt vom Kunden (beim Anlegen einer
    Erfassung steht der Vorgang noch nicht fest)."""
    if kunde is None or not kunde.objektart:
        return {}
    code = O01_CODES.get(kunde.objektart.upper())
    if not code:
        return {}
    from app import leadmanagement_logik
    art = leadmanagement_logik.hole_logik().objektart(kunde.objektart.upper())
    info = f"aus Kundenkartei (Objektart {art.bezeichnung if art else kunde.objektart})"
    if (sparte or "WP").upper() == "PV":
        return {"PO01": {"wert": code, "info": info}}
    if (sparte or "WP").upper() != "WP":
        return {}
    ergebnis = {"O01": {"wert": code, "info": info}}
    if code == "MFH" and kunde.parteien:
        ergebnis["O03"] = {"wert": str(kunde.parteien), "info": info}
    return ergebnis


# --- Kontext für das Template --------------------------------------------------------

def _ad_auswahl(session: Session, vorgang: Vorgang, kunde: Kunde) -> list:
    """Außendienst-Dropdown: alle aktiven AD; Handelsvertreter-Einträge mit
    Ausschlussgrund (F14) werden im Template deaktiviert."""
    profile = {p.benutzer_id: p for p in session.query(AdProfil)}
    sperre = lead_v2.hv_ausgeschlossen(session, vorgang, kunde)
    auswahl = []
    for b in (session.query(Benutzer).filter(Benutzer.aktiv.is_(True),
                                             Benutzer.rolle == "aussendienst")
              .order_by(Benutzer.name)):
        profil = profile.get(b.id)
        hv = bool(profil is not None and profil.terminiert_selbst)
        ok, grund = lead_v2.kompetenz_passt(profil, kunde.interessen if kunde else [],
                                            kunde.objektart if kunde else None)
        auswahl.append({"benutzer": b, "hv": hv, "gesperrt": sperre if hv else "",
                        "kompetenz_ok": ok, "kompetenz_grund": grund,
                        "aktiv_terminierung": profil.aktiv_terminierung if profil else True})
    return auswahl


def kartei_kontext(session: Session, vorgang: Vorgang, benutzer, readonly: bool = False) -> dict:
    from app import galerie as galerie_modul
    from app import lead_mail, leadmanagement_logik
    from app import projektierung as projektierung_modul
    logik = leadmanagement_logik.hole_logik()
    kunde = session.get(Kunde, vorgang.kunde_id)
    lead = session.get(Lead, vorgang.lead_id) if vorgang.lead_id else None
    benutzer_map = _benutzer_map(session)
    akte = kern.akte_kontext(session, vorgang)
    angebote = (session.query(Angebot).filter(Angebot.vorgang_id == vorgang.id)
                .order_by(Angebot.nummer).all())
    erfassungen = (session.query(Erfassung).filter(Erfassung.vorgang_id == vorgang.id)
                   .order_by(Erfassung.id).all())
    termine = termine_des_vorgangs(session, vorgang)
    zeitstrahl = timeline(session, vorgang, benutzer_map)
    mails = mail_verlauf(session, vorgang, benutzer, benutzer_map, angebote)
    # Projekte (nur bei sichtbarem Modul)
    projekte = []
    projekt_modul_ok = False
    try:
        projekt_modul_ok = projektierung_modul.modul_sichtbar(session, benutzer)
    except Exception:
        projekt_modul_ok = False
    if projekt_modul_ok:
        from app.models import Gewerk, Projekt
        for projekt in (session.query(Projekt).filter(Projekt.vorgang_id == vorgang.id)
                        .order_by(Projekt.id)):
            gewerke = (session.query(Gewerk).filter(Gewerk.projekt_id == projekt.id)
                       .order_by(Gewerk.id).all())
            projekte.append({"projekt": projekt, "gewerke": gewerke})
    # Anhänge = Galerie über alle Sparten
    anhaenge = (session.query(GalerieDatei).filter(GalerieDatei.vorgang_id == vorgang.id)
                .order_by(GalerieDatei.hochgeladen_am.desc()).all())
    try:
        darf_hochladen = galerie_modul.darf_hochladen(session, vorgang, benutzer)
    except Exception:
        darf_hochladen = False
    todos = (session.query(Todo).filter(Todo.vorgang_id == vorgang.id)
             .order_by(Todo.status.desc(), Todo.faellig_am.asc().nullslast(), Todo.id).all())
    todos_offen = [t for t in todos if t.status == "offen"]
    pflicht = pflicht_status(session, kunde, vorgang) if kunde else {
        "offen": [], "offen_keys": set(), "pflicht": set(), "labels": PFLICHT_LABELS}
    terminierung = terminierung_pruefung(session, kunde, vorgang, termine)
    status_zeile = logik.status_zeile(vorgang.lead_phase or "neu")
    status_farben = {z.phase: z.farbe for z in logik.status_zeilen}
    kanal_werte = kern.kanal_werte(session)
    if kunde and kunde.vertriebskanal and kunde.vertriebskanal not in kanal_werte:
        kanal_werte.append(kunde.vertriebskanal)
    quellen = session.query(LeadQuelle).filter(LeadQuelle.aktiv.is_(True)).order_by(LeadQuelle.name).all()
    if akte["quelle"] is not None and akte["quelle"] not in quellen:
        quellen.append(akte["quelle"])
    kampagnen = session.query(Kampagne).order_by(Kampagne.name).all()
    aktiver_termin = next((t for t in termine if t.status in TERMIN_OFFEN), None)
    heute = datetime.now()
    hv = lead_v2.ist_handelsvertreter(session, benutzer)
    return {
        "vorgang": vorgang, "kunde": kunde, "lead": lead, "benutzer": benutzer,
        "benutzer_map": benutzer_map, "lead_kontext": akte, "readonly": readonly,
        "ist_hv": hv, "heute": heute,
        "lead_phasen_namen": LEAD_PHASEN_NAMEN, "status_zeile": status_zeile,
        "status_farben": status_farben,
        "initialen": kunden_initialen(kunde), "initialen_fn": initialen,
        "timeline": zeitstrahl, "timeline_gruppen": TIMELINE_GRUPPEN,
        "mails": mails, "anrufe": [e for e in zeitstrahl if e["typ"] == "anruf"],
        "termine": termine, "aktiver_termin": aktiver_termin,
        "termin_status_namen": TERMIN_STATUS_NAMEN, "termin_typ_namen": TERMIN_TYP_NAMEN,
        "termin_medium_namen": TERMIN_MEDIUM_NAMEN,
        "angebote": angebote, "erfassungen": erfassungen, "projekte": projekte,
        "projekt_modul_ok": projekt_modul_ok,
        "anhaenge": anhaenge, "anhaenge_bilder": [a for a in anhaenge if a.bild],
        "darf_hochladen": darf_hochladen,
        "todos": todos, "todos_offen": todos_offen,
        "pflicht": pflicht, "pflicht_offen": pflicht["offen"],
        "terminierung": terminierung,
        "objektarten": lead_v2.objektarten(session), "anreden": ANREDEN,
        "interessen": INTERESSEN, "kanal_werte": kanal_werte,
        "quellen": quellen, "kampagnen": kampagnen,
        "innendienst_wahl": akte["leadmanager_wahl"],
        "ad_wahl": _ad_auswahl(session, vorgang, kunde) if kunde else [],
        "hv_sperre": lead_v2.hv_ausgeschlossen(session, vorgang, kunde) if kunde else "",
        "demo": kern.demo_aktiv(session),
        "buchbar": not (kern.demo_aktiv(session) and not vorgang.demo),
        "anruf_gesperrt": kern.versuche_gesperrt(session, vorgang),
        "versuche_max": kern.versuche_max(session),
        "vorlagen": list(lead_mail.VORLAGEN_START.keys()),
        "zurueck_gruende": logik.gruende_der_phase("zurueckgestellt"),
        "unq_gruende": logik.gruende_der_phase("unqualifiziert"),   # C3-Dialog (Phase 107)
        "no_show_gruende": logik.gruende_der_phase("no_show"),
        "nachbearbeitung_grund": nachbearbeitung_grund(session),
        "nachbearbeitung_bis": (heute + timedelta(days=wv_tage(session))).strftime("%Y-%m-%d"),
        "wv_tage": wv_tage(session),
        "wv_vorschlag": (heute + timedelta(days=1)).replace(hour=9, minute=0).strftime("%Y-%m-%dT%H:%M"),
        "kartei_url": f"/lead-management/lead/{vorgang.id}",
        "notiz_url": (f"/vorgaenge/{vorgang.id}/notiz" if readonly
                      else f"/lead-management/lead/{vorgang.id}/notiz"),
        "erfassung_url": (f"/erfassung/sparten?kunde_id={kunde.id}"
                          + (f"&lead_id={vorgang.lead_id}" if vorgang.lead_id else "")) if kunde else "",
        "zaehler": {"termine": len(termine), "angebote": len(angebote),
                    "erfassungen": len(erfassungen), "projekte": len(projekte),
                    "anhaenge": len(anhaenge), "todos": len(todos_offen),
                    "timeline": len(zeitstrahl), "mails": len(mails),
                    "anrufe": sum(1 for e in zeitstrahl if e["typ"] == "anruf"),
                    "qualifizierungen": len(akte["qualifizierungen"])},
    }
