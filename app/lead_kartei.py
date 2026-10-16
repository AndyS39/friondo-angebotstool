# Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 106): Kundenkartei
# (B1–B8, F10 Vorab-Angebot, F11 Nachbearbeitung). Fachlogik der Kartei –
# Kontext für das Template, Stammdaten-Speichern mit Aktivität, Pflichtfeld-
# Status, Terminierung (B8, Vertrag mit Phase 108: Terminstatus „vorgemerkt“),
# Wiedervorlage/Zurückstellen/Nachbearbeitung. Router: app/routers/lm_kartei.py.
# Prozesswissen (Objektarten, Gründe, Status-Farben) kommt aus der Steuerdatei,
# Pflichtfelder und Fristen aus den LeadParametern.
# v25 (PLAN_LEAD_V3 Phase 119): Kartei neu aufgeteilt (Kopf mit Statuskette,
# Kundeninfo-Block, Reiter Termin · Anrufnotizen · E-Mail-Verlauf · Timeline,
# Blöcke darunter), Autospeichern je Feld (feld_speichern, Aktivität typ
# `aenderung` „<Feld>: „alt“ → „neu““), Terminvorschläge im Block Termine
# (Zustand adresse_fehlt / hv_lead / laden; Vorschläge liefert lm_termin
# GET /lead/{id}/termin/vorschlaege.json), Score/Qualifizierung/Quelle/
# Einwilligung aus der Kartei entfernt.
# v31 (PLAN_LEAD_V5 Phasen 153/155/157/158): Objekte am Vorgang (Block „Objekte“ im
# Kundeninfo-Bereich, Karten je Objekt, Autospeichern je Objektfeld, Hauptobjekt ↔
# Kundenfelder über objekte.hauptobjekt_sync), Großkunde-Häkchen, Kartei neu geordnet
# (Notizen/To-Dos vor dem Kundeninfo-Block, Reiter Anruf · E-Mail · Timeline, Block
# Termine mit Terminen je Objekt), Pflichtfeld Außendienst (ad_id, HV gilt als erfüllt),
# MFH-Frage „Rechnungsadresse identisch?“, Status aus der Kartei (dieselben Regeln wie
# lead_boards.status_setzen), E-Mail-Dialog mit Vorlagenwahl/Vorschau/ICS, Timeline mit
# Herkunfts-Badge (vorgang_verlauf.eintraege – Vertrag AT, Rückfall LeadAktivitaet),
# Testphase (lead_v5.terminierung_aktiv / mail_versand_aktiv).

import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import lead_kanaele   # v35 (Phase 184): Kanal-Stammdaten, Kanal „?“
from app import lead_v2, lead_v5
from app import leadmanagement as kern
from app import objekte as objekte_modul
from app import sparten as sparten_modul
from app.models import (AdProfil, Angebot, Benutzer, Erfassung, GalerieDatei,
                        Kampagne, KommunikationLog, Kunde, Lead, LeadAktivitaet,
                        LeadQuelle, Todo, Vorgang, VorgangObjekt, VorgangsNotiz, VotTermin,
                        ANRUF_ERGEBNIS_NAMEN, INTERESSE_CODES, INTERESSEN,
                        LEAD_PHASEN_NAMEN, TERMIN_TYP_NAMEN, VOT_STATUS_NAMEN)
from app import rollen as rollen_modul   # v33: Basisrolle/Rollen-Varianten
# Kampagne/LeadQuelle bleiben für stammdaten_speichern (Fallback-Route, Boards-Inline)

ANREDEN = ["", "Herr", "Frau", "Familie", "Firma"]
# v31 (Phase 157): Interessen-Häkchen inkl. MS/WA/DMS – Codes und Langnamen aus app/sparten.py
INTERESSEN_WAHL = [(code, sparten_modul.SPARTEN_LANG.get(code, code)) for code in sparten_modul.SPARTEN]
INTERESSE_CODES_V31 = list(sparten_modul.SPARTEN)

# Filtergruppen der Timeline (Reiter Mitte): Aktivitätstyp → Gruppe
TIMELINE_GRUPPEN = [("anruf", "Anrufe"), ("notiz", "Notizen"), ("mail", "E-Mails"),
                    ("termin", "Termine"), ("status", "Status"),
                    ("aenderung", "Änderungen"), ("system", "System")]
_TYP_GRUPPE = {"anruf": "anruf", "notiz": "notiz", "mail_aus": "mail", "mail_ein": "mail",
               "mail": "mail", "termin": "termin", "status": "status",
               "system": "system", "import": "system", "whatsapp": "mail", "sms": "mail",
               "aenderung": "aenderung"}   # v25: Autospeichern „<Feld>: „alt“ → „neu““
_TYP_TITEL = {"anruf": "Anruf", "notiz": "Notiz", "mail_aus": "E-Mail gesendet",
              "mail_ein": "E-Mail eingegangen", "termin": "Termin", "status": "Status",
              "system": "System", "import": "Import", "whatsapp": "WhatsApp", "sms": "SMS",
              "aenderung": "Änderung"}

# Anzeigenamen der Pflichtfeld-Keys (Parameter `pflichtfelder`) – die Zählung
# selbst liefert lead_v2.pflichtfelder_offen (B2).
PFLICHT_LABELS = {"anrede": "Anrede", "vorname": "Vorname", "nachname": "Nachname",
                  "telefon": "Telefon", "email": "E-Mail", "strasse": "Straße",
                  "plz": "PLZ", "ort": "Ort", "vertriebskanal": "Vertriebskanal",
                  "interesse": "Interesse", "objektart": "Objektart",
                  "parteien": "Anzahl Parteien", "rechnungsadresse": "Rechnungsadresse",
                  "ad_id": "Außendienst"}   # v31 (Phase 157): Pflichtfeld Außendienst
# lead_v2.pflichtfelder_offen liefert feld.capitalize() („Strasse“, „Email“, „Ad_id“) –
# für Zähler-Tooltip, Fehlliste und Meldungen lesbar machen (nur Anzeige)
_PFLICHT_ANZEIGE = {"Strasse": "Straße", "Email": "E-Mail", "Plz": "PLZ", "Ad_id": "Außendienst"}
AD_PFLICHT_HINWEIS = "Bitte Außendienst zuweisen"
# v31 (Phase 157): Pflichtfelder je weiterem Objekt (Objekt 2 …) – Anzeigename je Key
OBJEKT_PFLICHT_LABELS = {"strasse": "Straße", "plz": "PLZ", "ort": "Ort", "objektart": "Objektart",
                         "interesse": "Interesse", "parteien": "Anzahl Parteien",
                         "rechnungsadresse": "Rechnungsadresse"}


def ad_pflicht_erfuellt(session: Session, vorgang: Vorgang | None) -> bool:
    """v31 (Phase 157): Pflichtfeld Außendienst gilt als erfüllt, sobald ein Außendienstler
    ODER ein Handelsvertreter am Vorgang hängt (vorgaenge.ad_id) – HV-Leads sind damit
    automatisch erfüllt (der zugewiesene Vertreter ist der Außendienst)."""
    return bool(vorgang is not None and vorgang.ad_id)


def rechnung_abweichend(session: Session, vorgang: Vorgang | None, kunde: Kunde | None = None) -> bool:
    """v31 (Phase 157): Antwort auf „Rechnungsadresse identisch mit der Objektadresse?“ für
    das Hauptobjekt (Ja = False, Nein = True). Gemerkt in vorgang_objekte.rechnung_abweichend
    des Hauptobjekts; ohne Objekt gilt: eine bereits gepflegte Kunden-Rechnungsadresse
    (v20) = Nein, sonst Vorbelegung Ja."""
    haupt = objekte_modul.hauptobjekt(session, vorgang.id) if vorgang is not None else None
    if haupt is not None:
        return bool(haupt.rechnung_abweichend)
    return bool(kunde is not None and ((kunde.rechnung_strasse or "").strip()
                                       or (kunde.rechnung_ort or "").strip()))


def _objekt_pflicht_keys(session: Session, objekt: VorgangObjekt, pflicht_keys: set) -> set:
    """Offene Pflichtfelder eines weiteren Objekts (nicht Hauptobjekt): Adresse immer,
    Objektart/Interesse nach Parameter pflichtfelder, Parteien bei MFH, Rechnungsadresse
    bei MFH nur bei „Nein“ (abweichend)."""
    offen: set = set()
    for feld in ("strasse", "plz", "ort"):
        if not (getattr(objekt, feld, "") or "").strip():
            offen.add(feld)
    if "objektart" in pflicht_keys and not (objekt.objektart or "").strip():
        offen.add("objektart")
    if "interesse" in pflicht_keys and not objekte_modul.interessen_liste(objekt):
        offen.add("interesse")
    if (objekt.objektart or "").upper() == "MFH":
        if not objekt.parteien:
            offen.add("parteien")
        if objekt.rechnung_abweichend and not ((objekt.rechnung_strasse or "").strip()
                                               and (objekt.rechnung_ort or "").strip()):
            offen.add("rechnungsadresse")
    return offen


def pflicht_offen_namen(session: Session, kunde: Kunde | None,
                        vorgang: Vorgang | None = None) -> list:
    """Anzeigenamen der offenen Pflichtfelder (B2) – Zählung aus lead_v2, v31 ergänzt:
    „Außendienst“ (ad_id; HV gilt als erfüllt), Rechnungsadresse bei MFH nur bei
    „Nein“ auf die Frage „Rechnungsadresse identisch?“, Pflichtfelder weiterer Objekte
    („Objekt 2: Straße“)."""
    if kunde is None:
        return []
    namen = []
    for name in lead_v2.pflichtfelder_offen(session, kunde, vorgang):
        name = _PFLICHT_ANZEIGE.get(name, name)
        if name == "Außendienst":
            if ad_pflicht_erfuellt(session, vorgang):
                continue
        elif name == "Rechnungsadresse" and vorgang is not None \
                and not rechnung_abweichend(session, vorgang, kunde):
            continue
        if name not in namen:
            namen.append(name)
    # Pflichtfeld Außendienst auch dann, wenn lead_v2 (B) den Key noch nicht kennt
    if "ad_id" in lead_v2.pflichtfelder(session) and not ad_pflicht_erfuellt(session, vorgang) \
            and "Außendienst" not in namen:
        namen.append("Außendienst")
    if vorgang is not None:
        pflicht_keys = set(lead_v2.pflichtfelder(session))
        for objekt in objekte_modul.objekte_fuer(session, vorgang.id):
            if objekt.reihenfolge == 1:
                continue
            for key in sorted(_objekt_pflicht_keys(session, objekt, pflicht_keys),
                              key=lambda k: list(OBJEKT_PFLICHT_LABELS).index(k)):
                namen.append(f"{objekt.bezeichnung or 'Objekt'}: {OBJEKT_PFLICHT_LABELS[key]}")
    return namen

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
    die rote Umrandung im Formular, labels = Anzeigename je Key.
    v31: Key `ad_id` (Außendienst, HV erfüllt), `rechnungsadresse` bei MFH nur bei
    „Nein“ (abweichend), `objekte` = offene Keys je weiterem Objekt (Objekt-Karten)."""
    offen = pflicht_offen_namen(session, kunde, vorgang)
    keys: set = set()
    pflicht_keys = set(lead_v2.pflichtfelder(session))
    for feld in pflicht_keys:
        if feld == "interesse":
            if not (kunde.interesse or "").strip():
                keys.add("interesse")
        elif feld == "vertriebskanal":
            if not (kunde.vertriebskanal or "").strip():
                keys.add("vertriebskanal")
        elif feld == "ad_id":
            if not ad_pflicht_erfuellt(session, vorgang):
                keys.add("ad_id")
        else:
            wert = getattr(kunde, feld, None)
            if wert is None or str(wert).strip() == "":
                keys.add(feld)
    # v35 (PLAN_LEAD_V6 Phase 184): Kanal „?“ → Kanalfeld rot („Vertriebskanal klären“), auch
    # wenn vertriebskanal nicht in den Pflichtfeldern steht (lead_v2.pflichtfelder_offen zählt mit)
    if lead_kanaele.kanal_unklar(kunde):
        keys.add("vertriebskanal")
    if (kunde.objektart or "").upper() == "MFH":
        if not kunde.parteien:
            keys.add("parteien")
        if rechnung_abweichend(session, vorgang, kunde) and not (
                (kunde.rechnung_strasse or "").strip() and (kunde.rechnung_ort or "").strip()):
            keys.add("rechnungsadresse")
    objekte: dict = {}
    if vorgang is not None:
        for objekt in objekte_modul.objekte_fuer(session, vorgang.id):
            if objekt.reihenfolge == 1:
                objekte[objekt.id] = {k for k in keys
                                      if k in ("strasse", "plz", "ort", "interesse", "objektart",
                                               "parteien", "rechnungsadresse")}
            else:
                objekte[objekt.id] = _objekt_pflicht_keys(session, objekt, pflicht_keys)
    # „offen_keys“ statt „keys“: Jinja löst pflicht.keys sonst als dict-Methode auf
    return {"offen": offen, "offen_keys": keys, "pflicht": pflicht_keys,
            "labels": PFLICHT_LABELS, "objekte": objekte,
            "ad_hinweis": AD_PFLICHT_HINWEIS}


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
        elif typ == "aenderung":
            # v25: „Telefon: „alt“ → „neu““ → Titel „Änderung: Telefon“
            kurz = (a.text or "").split(":")[0].strip()
            if kurz and len(kurz) <= 60:
                titel = f"Änderung: {kurz}"
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
                       "naechste": a.naechste_aktion_am, "herkunft": "lead"})
    for n in (session.query(VorgangsNotiz)
              .filter(VorgangsNotiz.vorgang_id == vorgang.id)):
        karten.append({"id": f"n{n.id}", "quelle": "notiz", "typ": "notiz",
                       "gruppe": "notiz", "titel": "Notiz" + (f" · {n.herkunft}" if n.herkunft else ""),
                       "zeit": n.zeit, "autor": n.benutzer_name or "System",
                       "autor_id": n.benutzer_id, "text": n.text or "",
                       "ergebnis": None, "dauer_sek": None, "dauer": "",
                       "richtung": None, "naechste": None,
                       "herkunft": notiz_herkunft(n.herkunft)})
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
                       "richtung": "aus", "naechste": None, "herkunft": "lead"})
    karten.sort(key=lambda e: e["zeit"] or datetime.min, reverse=True)
    return karten


# --- v31 (PLAN_LEAD_V5 Phase 155/158): Timeline mit Herkunfts-Badge Lead · Angebot · Projekt ---

HERKUNFT_NAMEN = {"lead": "Lead", "angebot": "Angebot", "projekt": "Projekt"}
# Badge-Klassen des Notizen-Chats (akte_v28.css, v28) – keine neuen Farben nötig
HERKUNFT_KLASSEN = {"lead": "nc-lead", "angebot": "nc-vertrieb", "projekt": "nc-projektierung"}
_VERLAUF_ART_GRUPPE = dict(_TYP_GRUPPE, kommentar="notiz", verlauf="system", projekt="system")
_VERLAUF_ART_TITEL = dict(_TYP_TITEL, kommentar="Kommentar (Projektakte)", verlauf="Projekt-Verlauf")


def notiz_herkunft(herkunft: str | None) -> str:
    """Herkunft einer Notiz → lead | angebot | projekt (Badge im Reiter Timeline)."""
    h = (herkunft or "").strip().lower()
    if "projekt" in h or "montage" in h:
        return "projekt"
    if "lead" in h or "anruf" in h:
        return "lead"
    return "angebot"


def _verlauf_karte(e: dict, nr: int) -> dict:
    """Eintrag aus vorgang_verlauf.eintraege (Vertrag AT: zeit, quelle, art, text, autor,
    link) → Karte des Reiters Timeline (Felder wie timeline())."""
    art = str(e.get("art") or "notiz")
    quelle = str(e.get("quelle") or "lead")
    if quelle not in HERKUNFT_NAMEN:
        quelle = notiz_herkunft(quelle)
    titel = str(e.get("titel") or _VERLAUF_ART_TITEL.get(art, art.capitalize()))
    text = str(e.get("text") or "")
    if art in ("status", "termin", "system", "import", "aenderung", "anruf") and not e.get("titel"):
        kurz = text.split(":")[0].strip()
        if kurz and len(kurz) <= 60:
            titel = f"Änderung: {kurz}" if art == "aenderung" else kurz
    return {"id": f"v{nr}", "quelle": "verlauf", "typ": art,
            "gruppe": _VERLAUF_ART_GRUPPE.get(art, "system"), "titel": titel,
            "zeit": e.get("zeit"), "autor": str(e.get("autor") or "System"),
            "autor_id": e.get("autor_id"), "text": text, "ergebnis": e.get("ergebnis"),
            "dauer_sek": e.get("dauer_sek"), "dauer": dauer_text(e.get("dauer_sek")),
            "richtung": e.get("richtung"), "naechste": e.get("naechste"),
            "herkunft": quelle, "link": e.get("link") or ""}


def verlauf(session: Session, vorgang: Vorgang, benutzer_map: dict | None = None) -> list:
    """Reiter Timeline: alle Einträge über `vorgang_verlauf.eintraege(session, vorgang_id)`
    (Vertrag AT – Lead-Aktivitäten, Notizen-Chat, Projekt-Verlauf/-Kommentare, chronologisch,
    mit Herkunft). Rückfall, solange AT fehlt: timeline() mit Herkunft aus der Notiz-Spur."""
    try:
        from app import vorgang_verlauf
        fn = getattr(vorgang_verlauf, "eintraege", None)
    except Exception:   # noqa: BLE001
        fn = None
    if callable(fn):
        try:
            roh = fn(session, vorgang.id)
            karten = [_verlauf_karte(e, i) for i, e in enumerate(roh) if isinstance(e, dict)]
            karten.sort(key=lambda e: e["zeit"] or datetime.min, reverse=True)
            return karten
        except Exception:   # noqa: BLE001 – Rückfall auf die eigene Liste
            pass
    return timeline(session, vorgang, benutzer_map)


def projekt_block(session: Session, vorgang: Vorgang) -> dict | None:
    """Block „Projekt“: Projektphase, Montagetermin, offene Projekt-To-Dos über
    vorgang_verlauf.projekt_block (Vertrag AT); None, solange die Funktion fehlt."""
    try:
        from app import vorgang_verlauf
        fn = getattr(vorgang_verlauf, "projekt_block", None)
        if callable(fn):
            ergebnis = fn(session, vorgang.id)
            return ergebnis if isinstance(ergebnis, dict) else None
    except Exception:   # noqa: BLE001
        return None
    return None


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
    # v31 (Phase 153, Vertrag T): „bereit“, wenn mindestens ein Objekttermin vorgemerkt ist
    # (lead_termin.vorgemerkte_objekttermine) und kein Pflichtfeld offen – die Terminierung
    # bucht alle vorgemerkten Objekttermine in einem Schritt
    vorgemerkte = vorgemerkte_termine(session, vorgang, termine)
    geplante = [t for t in termine if t.status in ("geplant", "bestaetigt") and (t.typ or "vot") == "vot"]
    geplante.sort(key=lambda t: t.beginn or datetime.max)
    termin = vorgemerkte[0] if vorgemerkte else (geplante[0] if geplante else None)
    fehlend = list(pflicht_fehlt)
    if not vorgemerkte:
        fehlend.append("Termin (vorgemerkt/geplant)")
    # schon erledigt: geplanter Termin, Phase terminiert, nichts offen, nichts mehr vorgemerkt
    erledigt = (not vorgemerkte and termin is not None and termin.status in ("geplant", "bestaetigt")
                and vorgang.lead_phase == "terminiert" and not pflicht_fehlt)
    return {"bereit": not fehlend and not erledigt, "fehlend": fehlend,
            "termin": termin, "erledigt": erledigt, "vorgemerkte": vorgemerkte}


def vorgemerkte_termine(session: Session, vorgang: Vorgang, termine: list | None = None) -> list:
    """Vorgemerkte Vor-Ort-Termine (einer je Objekt) über lead_termin.vorgemerkte_objekttermine
    (Vertrag T); Rückfall: eigene Filterung der Vorgangstermine."""
    try:
        from app import lead_termin as termin_modul
        fn = getattr(termin_modul, "vorgemerkte_objekttermine", None)
        if callable(fn):
            return list(fn(session, vorgang))
    except Exception:   # noqa: BLE001
        pass
    termine = termine if termine is not None else termine_des_vorgangs(session, vorgang)
    liste = [t for t in termine if t.status == "vorgemerkt" and (t.typ or "vot") == "vot"]
    liste.sort(key=lambda t: (t.beginn or datetime.max, t.id))
    return liste


def terminierung_ausfuehren(session: Session, vorgang: Vorgang, benutzer=None,
                            bestaetigung_modus: str = "", bestaetigung: str = "") -> tuple:
    """Button „Terminierung“ (B8). v31 (PLAN_LEAD_V5 Phase 153, Vertrag T): Einzeiler auf
    lead_termin.terminierung_ausfuehren – bucht alle vorgemerkten Objekttermine in einem
    Schritt (vorgemerkt → geplant, Outlook je Termin, Terminbestätigung „eine“ |
    „je_objekt“ | „auto“, Erinnerung, Phase Terminiert, Aktivität, Glocke), prüft
    Pflichtfelder inkl. Außendienst und die Testphase (lead_v5.terminierung_aktiv →
    TESTPHASE_HINWEIS). Die Route liegt in routers/lm_termin.py (POST /lead/{id}/terminierung);
    der Aufrufer committet. Liefert (ok, meldung)."""
    from app import lead_termin
    return lead_termin.terminierung_ausfuehren(
        session, vorgang, benutzer=benutzer,
        bestaetigung=(bestaetigung or bestaetigung_modus or "auto"))


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
    if aenderungen and any(f in form for f in HAUPTOBJEKT_FELDER + ("interesse_feld",)):
        hauptobjekt_nachziehen(session, vorgang, kunde)   # v31 (Phase 153)
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


# --- v25 (Phase 119): Statuskette, Autospeichern, Vorschläge-Zustand -----------------

# Felder des Kundeninfo-Blocks, die POST /lead/{id}/feld annimmt → Anzeigename
# für die Änderungs-Aktivität. Quelle/Kampagne/Einwilligung/Eingangsdatum sind
# bewusst nicht dabei (aus der Kartei entfernt bzw. nur Anzeige).
FELD_LABELS = {"anrede": "Anrede", "vorname": "Vorname", "nachname": "Nachname",
               "firma": "Firma", "telefon": "Telefon", "email": "E-Mail",
               "strasse": "Straße", "plz": "PLZ", "ort": "Ort",
               "vertriebskanal": "Vertriebskanal", "interesse": "Interessen",
               "objektart": "Objektart", "parteien": "Anzahl Parteien",
               "rechnung_name": "Rechnung Name", "rechnung_strasse": "Rechnung Straße",
               "rechnung_plz": "Rechnung PLZ", "rechnung_ort": "Rechnung Ort",
               "leadmanager_id": "Innendienst", "ad_id": "Außendienst",
               # v31 (Phase 153/157): Großkunde-Häkchen, MFH-Frage „Rechnungsadresse
               # identisch mit der Objektadresse?“ (Hauptobjekt)
               "grosskunde": "Großkunde", "rechnung_abweichend": "Rechnungsadresse abweichend",
               # v35 (PLAN_LEAD_V6 Phase 183, Agent T): TAIFUN-Kundennummer (manuell nachgetragen)
               "taifun_kundennr": "TAIFUN-Kundennummer"}
AUTOSPEICHER_FELDER = tuple(FELD_LABELS)
ADRESS_FELDER = ("strasse", "plz", "ort")
# v31 (Phase 153): Kundenfelder, die das Hauptobjekt spiegelt (objekte.hauptobjekt_sync)
HAUPTOBJEKT_FELDER = ("strasse", "plz", "ort", "objektart", "parteien", "interesse")
GROSSKUNDE_TEXT = "als Großkunde gekennzeichnet"
GROSSKUNDE_ENTFERNT_TEXT = "Großkunde-Kennzeichen entfernt"
_TEXT_LAENGEN = {"vorname": 100, "nachname": 100, "firma": 200, "telefon": 50,
                 "email": 200, "strasse": 200, "ort": 100, "rechnung_name": 200,
                 "rechnung_strasse": 200, "rechnung_plz": 10, "rechnung_ort": 100,
                 "taifun_kundennr": 30}   # v35 (Phase 183, Agent T)
_EMAIL_MUSTER = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
SEITENZUSTAENDE = ("zurueckgestellt", "nicht_erreicht", "unqualifiziert", "verloren")

# Texte des Blocks Termine (Plan-Wortlaut)
VORSCHLAEGE_TEXTE = {
    "laden": "Vorschläge werden berechnet …",
    "adresse_fehlt": "Adresse fehlt – Straße, PLZ und Ort eintragen",
    "nicht_verfuegbar": "Vorschläge derzeit nicht verfügbar",
}


def phasen_label(logik, phase: str) -> str:
    """Anzeigename einer Phase aus dem Blatt Status (v25: in_kontaktierung und
    qualifiziert tragen beide „Kontaktiert“), Fallback LEAD_PHASEN_NAMEN."""
    zeile = logik.status_zeile(phase or "") if logik is not None else None
    if zeile is not None and (zeile.label or "").strip():
        return zeile.label.strip()
    return LEAD_PHASEN_NAMEN.get(phase, phase or "–")


def phasen_kette(logik, aktuelle_phase: str | None) -> list:
    """Statuskette des Kopfbereichs: die Anzeige-Phasen (kern.LEAD_PHASEN_ANZEIGE)
    mit Label/Farbe aus dem Blatt Status. Aufeinanderfolgende Phasen mit
    demselben Label (In Kontaktierung + Qualifiziert → „Kontaktiert“) werden zu
    EINEM Schritt zusammengefasst [ANNAHME: wie die Kanban-Spalte]; der Schritt
    ist aktiv, wenn die aktuelle Phase eine seiner Phasen ist. Seitenzustände
    (zurückgestellt …) hängt das Template als eigenen Schritt an."""
    schritte = []
    for phase in kern.LEAD_PHASEN_ANZEIGE:
        zeile = logik.status_zeile(phase) if logik is not None else None
        label = phasen_label(logik, phase)
        farbe = (zeile.farbe if zeile is not None else "") or ""
        if schritte and schritte[-1]["label"] == label:
            schritte[-1]["phasen"].append(phase)
            if not schritte[-1]["farbe"]:
                schritte[-1]["farbe"] = farbe
        else:
            schritte.append({"label": label, "phasen": [phase], "farbe": farbe})
    aktiv = next((i for i, s in enumerate(schritte) if aktuelle_phase in s["phasen"]), None)
    for i, s in enumerate(schritte):
        s["aktiv"] = aktiv is not None and i == aktiv
        s["fertig"] = aktiv is not None and i < aktiv
    return schritte


def _norm_text(wert, laenge: int) -> str:
    if wert is None:
        return ""
    if isinstance(wert, (list, tuple)):
        wert = ",".join(str(w) for w in wert)
    return re.sub(r"\s+", " ", str(wert)).strip()[:laenge]


def telefon_pruefen(wert: str) -> str | None:
    """Fehlertext oder None: die Nummer muss sich nach E.164 normalisieren
    lassen (kern.telefon_normalisieren) und mindestens 6 nationale Ziffern
    haben; nur erlaubte Zeichen (Ziffern, + / - ( ) . Leerzeichen)."""
    if not wert:
        return None
    if re.search(r"[^\d+\s/().\-]", wert):
        return "Telefonnummer enthält ungültige Zeichen."
    norm = kern.telefon_normalisieren(wert)
    ziffern = re.sub(r"\D", "", norm)
    national = ziffern[2:] if ziffern.startswith("49") else ziffern
    if len(national) < 6:
        return "Telefonnummer ist zu kurz – bitte mit Vorwahl eintragen."
    return None


def _aenderung(session: Session, vorgang: Vorgang, label: str, alt, neu, benutzer=None) -> None:
    """Aktivität typ aenderung „<Feld>: „alt“ → „neu““ (Vertrag Briefing)."""
    kern.aktivitaet(session, vorgang.id, "aenderung",
                    f"{label}: „{alt if alt not in (None, '') else '–'}“ → "
                    f"„{neu if neu not in (None, '') else '–'}“", benutzer=benutzer)


def feld_speichern(session: Session, vorgang: Vorgang, kunde: Kunde, feld: str, wert,
                   benutzer=None, erzwingen: bool = False) -> dict:
    """Autospeichern eines Feldes (POST /lead/{id}/feld). Serverseitige
    Validierung: PLZ 5 Ziffern, E-Mail-Form, Telefon normalisierbar, Objektart
    aus dem Blatt Objektarten, Parteien Zahl > 0, Kanal aus kern.kanal_werte,
    Interessen aus INTERESSE_CODES, Innendienst/Außendienst über
    lead_v2.leadmanager_zuweisen / ad_zuweisen (schreiben ihre eigene
    Aktivität + Glocke). Jede tatsächliche Änderung an Kundenfeldern schreibt
    eine Aktivität `aenderung` mit Alt → Neu; derselbe Wert erneut → keine
    Aktivität. Liefert {ok, wert (normalisiert), meldung, geaendert}."""
    label = FELD_LABELS.get(feld)
    if label is None:
        return {"ok": False, "wert": "", "meldung": "Feld unbekannt.", "geaendert": False}
    if feld == "leadmanager_id" and lead_v2.hv_sicht(session, benutzer):
        # v29 (Phase 140): Handelsvertreter sehen das Feld Innendienst nur als Anzeige
        return {"ok": False, "wert": str(vorgang.leadmanager_id or ""),
                "meldung": "Innendienst wird vom Innendienst zugewiesen (nur Anzeige).",
                "geaendert": False}
    if kunde is None and feld not in ("leadmanager_id", "ad_id"):
        return {"ok": False, "wert": "", "meldung": "Kunde fehlt.", "geaendert": False}

    def fehler(text: str, alt=""):
        return {"ok": False, "wert": "" if alt is None else alt, "meldung": text, "geaendert": False}

    def ok(neu, meldung: str = "", geaendert: bool = True):
        return {"ok": True, "wert": "" if neu is None else neu,
                "meldung": meldung or ("Gespeichert." if geaendert else "Keine Änderung."),
                "geaendert": geaendert}

    # --- Zuweisungen (eigene Helfer, eigene Aktivität) ---
    if feld in ("leadmanager_id", "ad_id"):
        roh = _norm_text(wert, 10)
        if roh and not roh.isdigit():
            return fehler(f"{label}: ungültige Auswahl – nichts geändert.",
                          str(getattr(vorgang, feld) or ""))
        neu_id = int(roh) if roh else None
        if neu_id == (getattr(vorgang, feld) or None):
            # v33 (PLAN_V20 Phase 175): Simon wählt sich selbst → Kennzeichen „Simons Gruppe
            # (noch nicht verteilt)“ aufheben (lead_v2.ad_zuweisen schließt den Marker)
            if feld == "ad_id" and neu_id and lead_v2.hv_gruppe_offen(session, vorgang):
                meldung = lead_v2.ad_zuweisen(session, vorgang, neu_id, benutzer=benutzer,
                                              erzwingen=erzwingen)
                session.flush()
                return ok(str(neu_id), meldung, geaendert=True)
            return ok(str(neu_id or ""), "Keine Änderung.", geaendert=False)
        if feld == "leadmanager_id":
            meldung = lead_v2.leadmanager_zuweisen(session, vorgang, neu_id, benutzer=benutzer)
        else:
            meldung = lead_v2.ad_zuweisen(session, vorgang, neu_id, benutzer=benutzer,
                                          erzwingen=erzwingen)
        wert_neu = getattr(vorgang, feld)
        if (neu_id or None) != (wert_neu or None):
            # Helfer hat abgelehnt (nicht gefunden / Ausschluss F14)
            return fehler(meldung, str(wert_neu or ""))
        return ok(str(wert_neu or ""), meldung)

    # --- v31 (Phase 153): Großkunde-Häkchen (ID/LM/Admin) – Aktivität statt „Änderung“ ---
    if feld == "grosskunde":
        if benutzer is not None and not (benutzer.basisrolle in ("admin", "innendienst")
                                         or benutzer.hat_rolle("leadmanagement")):
            return fehler("Großkunde darf nur Innendienst, Leadmanagement oder Admin setzen.",
                          "1" if kunde.grosskunde else "")
        neu_bool = str(wert if not isinstance(wert, (list, tuple)) else (wert[0] if wert else "")
                       ).strip().lower() in ("1", "true", "on", "ja")
        if bool(kunde.grosskunde) == neu_bool:
            return ok("1" if neu_bool else "", "Keine Änderung.", geaendert=False)
        kunde.grosskunde = neu_bool
        kern.aktivitaet(session, vorgang.id, "status",
                        GROSSKUNDE_TEXT if neu_bool else GROSSKUNDE_ENTFERNT_TEXT, benutzer=benutzer)
        session.flush()
        return ok("1" if neu_bool else "", "Großkunde gesetzt." if neu_bool else "Großkunde entfernt.")

    # --- v31 (Phase 157): MFH-Frage „Rechnungsadresse identisch?“ am Hauptobjekt ---
    if feld == "rechnung_abweichend":
        haupt = objekte_modul.hauptobjekt(session, vorgang.id, anlegen=True, kunde=kunde)
        neu_bool = str(wert or "").strip().lower() in ("1", "true", "on", "nein", "abweichend")
        if haupt is None:
            return fehler("Hauptobjekt fehlt.", "")
        if bool(haupt.rechnung_abweichend) == neu_bool:
            return ok("1" if neu_bool else "", "Keine Änderung.", geaendert=False)
        haupt.rechnung_abweichend = neu_bool
        _aenderung(session, vorgang, "Rechnungsadresse identisch mit der Objektadresse",
                   "nein" if not neu_bool else "ja", "nein" if neu_bool else "ja", benutzer)
        session.flush()
        return ok("1" if neu_bool else "",
                  "Rechnungsadresse abweichend – bitte Felder füllen." if neu_bool
                  else "Rechnungsadresse = Objektadresse.")

    # --- Kundenfelder ---
    if feld.startswith("rechnung_") or feld in HAUPTOBJEKT_FELDER:
        # v31 (Phase 153/157): Hauptobjekt sicherstellen – die MFH-Frage (Ja/Nein) hängt daran
        try:
            objekte_modul.hauptobjekt(session, vorgang.id, anlegen=True, kunde=kunde)
        except Exception:   # noqa: BLE001
            pass
    alt = getattr(kunde, feld, None)
    if feld == "anrede":
        neu = _norm_text(wert, 20)
        if neu not in ANREDEN:
            return fehler("Anrede unbekannt.", alt or "")
    elif feld == "nachname":
        neu = _norm_text(wert, 100)
        if not neu and not (kunde.firma or "").strip():
            return fehler("Nachname (oder Firma) ist Pflicht.", alt or "")
    elif feld == "firma":
        neu = _norm_text(wert, 200)
        if not neu and not (kunde.nachname or "").strip():
            return fehler("Firma (oder Nachname) ist Pflicht.", alt or "")
    elif feld == "telefon":
        neu = _norm_text(wert, 50)
        text = telefon_pruefen(neu)
        if text:
            return fehler(text, alt or "")
    elif feld == "email":
        neu = _norm_text(wert, 200)
        if neu and not _EMAIL_MUSTER.match(neu):
            return fehler("E-Mail-Adresse ist ungültig.", alt or "")
    elif feld == "plz":
        neu = _norm_text(wert, 10).replace(" ", "")
        if neu and not re.fullmatch(r"\d{5}", neu):
            return fehler("PLZ muss aus 5 Ziffern bestehen.", alt or "")
    elif feld == "vertriebskanal":
        # v35 (PLAN_LEAD_V6 Phase 184): wählbar sind die aktiven Stammdaten-Kanäle (kern.kanal_werte,
        # nach Häufigkeit) und „?“; alte Schreibweisen/Aliase („SWD“) werden auf den Listennamen
        # abgebildet; der bisherige (auch inaktive) Wert bleibt erlaubt
        neu = _norm_text(wert, 100)
        if neu and neu != (alt or ""):
            neu = lead_kanaele.name_aufloesen(session, neu) or neu
        werte = kern.kanal_werte(session)
        if neu and neu not in werte and neu != (alt or "") and not lead_kanaele.ist_unklar(neu):
            return fehler("Vertriebskanal unbekannt.", alt or "")
    elif feld == "interesse":
        if isinstance(wert, (list, tuple)):
            codes = [str(w).strip().upper() for w in wert if str(w).strip()]
        else:
            codes = [c.strip().upper() for c in str(wert or "").split(",") if c.strip()]
        # v31 (Phase 157): MS/WA/DMS zusätzlich zu WP/PV/KL/WB/GW (app/sparten.py)
        fremd = [c for c in codes if c not in INTERESSE_CODES_V31]
        if fremd:
            return fehler("Interesse unbekannt: " + ", ".join(fremd), alt or "")
        neu = ",".join(c for c in INTERESSE_CODES_V31 if c in codes)
    elif feld == "objektart":
        neu = _norm_text(wert, 10).upper() or None
        codes = {code for code, _bez, _p in lead_v2.objektarten(session)}
        if neu and neu not in codes:
            return fehler("Objektart unbekannt.", alt or "")
    elif feld == "parteien":
        roh = _norm_text(wert, 5)
        if not roh:
            neu = None
        elif roh.isdigit() and int(roh) > 0:
            neu = int(roh)
        else:
            return fehler("Anzahl Parteien muss eine Zahl > 0 sein.",
                          str(alt) if alt else "")
    else:
        neu = _norm_text(wert, _TEXT_LAENGEN.get(feld, 200))

    # Vergleich auf dem gespeicherten Format (None/"" gleichwertig)
    alt_vgl = "" if alt is None else str(alt)
    neu_vgl = "" if neu is None else str(neu)
    if alt_vgl == neu_vgl:
        return ok(neu_vgl, "Keine Änderung.", geaendert=False)
    setattr(kunde, feld, neu)
    meldung = ""
    if feld == "vertriebskanal":
        kunde.kanal_manuell = True        # Sync-Schutz (v9/v21)
    if feld == "interesse":
        alt_text = ", ".join(a.strip() for a in alt_vgl.split(",") if a.strip())
        neu_text = ", ".join(n.strip() for n in neu_vgl.split(",") if n.strip())
        _aenderung(session, vorgang, label, alt_text, neu_text, benutzer)
    else:
        _aenderung(session, vorgang, label, alt_vgl, neu_vgl, benutzer)
    if feld == "vertriebskanal":
        # v23 (Phase 109, G4/OF-G5): Kanalwechsel auf Ausschlusskanal bei
        # zugewiesenem Handelsvertreter → Hinweis + Glocke (wie stammdaten_speichern)
        try:
            from app import lead_handelsvertreter
            session.flush()
            hinweis = lead_handelsvertreter.kanalwechsel_pruefen(session, vorgang, benutzer)
            if hinweis:
                meldung = hinweis
        except Exception:
            pass
    session.flush()
    if feld == "email":
        # v29 (PLAN_LEAD_V4 Phase 142, Vertrag L2): neue Adresse → email_status („E-Mail
        # falsch“) zurücksetzen und wartende Warteschlangen-Einträge (wartet_adresse) freigeben
        from app import lead_mail
        freigegeben = lead_mail.adresse_geaendert(session, vorgang)
        if freigegeben:
            meldung = (meldung or "Gespeichert.") + f" {freigegeben} wartende Mail(s) freigegeben."
    if feld in HAUPTOBJEKT_FELDER:
        # v31 (Phase 153): Kundenadressfelder ↔ Hauptobjekt synchron halten
        hauptobjekt_nachziehen(session, vorgang, kunde)
    return ok(neu_vgl, meldung or "Gespeichert.")


def hauptobjekt_nachziehen(session: Session, vorgang: Vorgang, kunde: Kunde | None) -> None:
    """v31 (Phase 153): nach einer Änderung an Kundenadressfeldern/Objektart/Parteien/
    Interessen das Hauptobjekt des Vorgangs mitschreiben (objekte.hauptobjekt_sync mit
    Kunde als Quelle; legt das Hauptobjekt bei Altbestand ohne Objekt an)."""
    if kunde is None or vorgang is None:
        return
    try:
        objekte_modul.hauptobjekt(session, vorgang.id, anlegen=True, kunde=kunde)
        objekte_modul.hauptobjekt_sync(session, kunde)
    except Exception:   # noqa: BLE001 – Sync ist Komfort, das Kundenfeld ist gespeichert
        pass


def adresse_vollstaendig(kunde: Kunde | None) -> bool:
    return bool(kunde is not None and all((getattr(kunde, f, "") or "").strip()
                                          for f in ADRESS_FELDER))


def hv_am_vorgang(session: Session, vorgang: Vorgang):
    """Zugewiesener Außendienstler, falls Handelsvertreter (terminiert_selbst),
    sonst None."""
    if not vorgang.ad_id:
        return None
    ad = session.get(Benutzer, vorgang.ad_id)
    if ad is not None and lead_v2.ist_handelsvertreter(session, ad):
        return ad
    return None


def vorschlaege_zustand(session: Session, vorgang: Vorgang, kunde: Kunde | None,
                        benutzer=None) -> dict:
    """Startzustand des Blocks Termine (serverseitig, ohne Assistentenlauf) in
    derselben Reihenfolge wie lead_termin.vorschlaege_json (Agent D):
    hv_lead (Lead liegt bei einem Handelsvertreter und der Betrachter ist nicht
    dieser HV – die Adresse ist dann zweitrangig) · adresse_fehlt (Straße/PLZ/
    Ort leer) · laden (das Template holt GET /lead/{id}/termin/vorschlaege.json
    nach dem Seitenaufbau). Liefert {status, hinweis, hv_name}."""
    hv = hv_am_vorgang(session, vorgang)
    # v35 (PLAN_LEAD_V6 Phase 185): Mitglieder der Gruppe des zuständigen HV sehen die
    # normalen Vorschläge (lead_termin.hv_gruppe_ids), nicht den Hinweis „liegt bei …“
    try:
        from app import lead_termin as _termin_modul
        gruppe_ich = _termin_modul.hv_gruppe_ids(session, benutzer)
    except Exception:   # noqa: BLE001
        gruppe_ich = None
    if hv is not None and (benutzer is None
                           or (hv.id not in gruppe_ich if gruppe_ich is not None else benutzer.id != hv.id)):
        return {"status": "hv_lead", "hv_name": hv.name,
                "hinweis": f"Lead liegt bei {hv.name} (Handelsvertreter), "
                           "Terminierung durch den Vertreter"}
    if not adresse_vollstaendig(kunde):
        return {"status": "adresse_fehlt", "hinweis": VORSCHLAEGE_TEXTE["adresse_fehlt"],
                "hv_name": hv.name if hv is not None else ""}
    return {"status": "laden", "hinweis": VORSCHLAEGE_TEXTE["laden"],
            "hv_name": hv.name if hv is not None else ""}


def vorschlaege_cache_leeren(vorgang_id: int) -> None:
    """Nach einer Adressänderung per Autospeichern den 10-Minuten-Cache der
    Terminvorschläge verwerfen (Vertrag Agent D: lead_termin.vorschlaege_cache).
    Defensiv gegen die konkrete Form: Funktion vorschlaege_cache_leeren/
    _invalidieren, dict (Schlüssel = vorgang_id oder Tupel damit) oder Objekt
    mit leeren/invalidieren/pop – fehlt alles, passiert nichts."""
    try:
        from app import lead_termin
    except Exception:
        return
    for name in ("vorschlaege_cache_leeren", "vorschlaege_cache_invalidieren",
                 "cache_invalidieren", "cache_leeren"):
        fn = getattr(lead_termin, name, None)
        if callable(fn):
            try:
                fn(vorgang_id)
            except Exception:
                pass
            return
    cache = getattr(lead_termin, "vorschlaege_cache", None)
    if cache is None:
        return
    if isinstance(cache, dict):
        for key in [k for k in list(cache)
                    if k == vorgang_id or k == str(vorgang_id)
                    or (isinstance(k, tuple) and vorgang_id in k)]:
            cache.pop(key, None)
        return
    for name in ("leeren", "invalidieren", "entfernen", "pop"):
        fn = getattr(cache, name, None)
        if callable(fn):
            try:
                fn(vorgang_id)
                return
            except Exception:
                continue


# --- v31 (PLAN_LEAD_V5 Phase 153/157): Objekte am Vorgang ---------------------------------

OBJEKT_FELD_LABELS = {"bezeichnung": "Bezeichnung", "strasse": "Straße", "plz": "PLZ", "ort": "Ort",
                      "objektart": "Objektart", "parteien": "Anzahl Parteien",
                      "interesse": "Interessen", "rechnung_abweichend": "Rechnungsadresse abweichend",
                      "rechnung_name": "Rechnung Name", "rechnung_strasse": "Rechnung Straße",
                      "rechnung_plz": "Rechnung PLZ", "rechnung_ort": "Rechnung Ort"}
OBJEKT_FELDER = tuple(OBJEKT_FELD_LABELS)
# Felder des Hauptobjekts, die über die Kundenfelder laufen (Sync, eine Wahrheit)
_HAUPT_UEBER_KUNDE = ("strasse", "plz", "ort", "objektart", "parteien", "interesse",
                      "rechnung_abweichend", "rechnung_name", "rechnung_strasse",
                      "rechnung_plz", "rechnung_ort")
OBJEKT_TERMIN_STATUS = ("vorgemerkt", "geplant", "bestaetigt")


def _wahr(wert) -> bool:
    if isinstance(wert, (list, tuple)):
        wert = wert[0] if wert else ""
    return str(wert if wert is not None else "").strip().lower() in ("1", "true", "on", "ja", "nein_identisch", "abweichend")


def objekt_termine(session: Session, vorgang: Vorgang, objekte: list | None = None) -> list[dict]:
    """Vertrag T: lead_termin.objekt_termine(session, vorgang) → je Objekt {objekt, termin,
    vorgemerkt}. Rückfall, solange T fehlt: aktiver Vor-Ort-Termin (vorgemerkt/geplant/
    bestätigt) mit objekt_id; Termine ohne objekt_id (Altbestand) zählen zum Hauptobjekt."""
    try:
        from app import lead_termin as termin_modul
        fn = getattr(termin_modul, "objekt_termine", None)
        if callable(fn):
            ergebnis = fn(session, vorgang)
            if isinstance(ergebnis, list):
                return ergebnis
    except Exception:   # noqa: BLE001 – Rückfall
        pass
    objekte = objekte if objekte is not None else objekte_modul.objekte_fuer(session, vorgang.id)
    termine = [t for t in termine_des_vorgangs(session, vorgang)
               if t.status in OBJEKT_TERMIN_STATUS and (t.typ or "vot") == "vot"]
    termine.sort(key=lambda t: (0 if t.status != "vorgemerkt" else 1, t.beginn or datetime.max))
    ergebnis = []
    for o in objekte:
        aktiv = next((t for t in termine if t.objekt_id == o.id), None)
        if aktiv is None and o.reihenfolge == 1:
            aktiv = next((t for t in termine if not t.objekt_id), None)
        ergebnis.append({"objekt": o, "termin": aktiv,
                         "vorgemerkt": bool(aktiv is not None and aktiv.status == "vorgemerkt")})
    return ergebnis


def objekt_rechnung(objekt: VorgangObjekt, kunde: Kunde | None) -> dict:
    """Rechnungsadresse eines Objekts: Hauptobjekt → kunden.rechnung_* (v20), weitere
    Objekte → vorgang_objekte.rechnung_* [ANNAHME Einfügung AT-Chat]."""
    quelle = kunde if (objekt.reihenfolge == 1 and kunde is not None) else objekt
    return {f: (getattr(quelle, f"rechnung_{f}", "") or "") for f in ("name", "strasse", "plz", "ort")}


def objekt_haengt(session: Session, vorgang: Vorgang, objekt: VorgangObjekt) -> str:
    """Grund, warum ein Objekt nicht deaktiviert werden darf (Termin/Erfassung/Angebot
    hängt daran) – leer = frei."""
    gruende = []
    if (session.query(VotTermin).filter(VotTermin.vorgang_id == vorgang.id,
                                        VotTermin.objekt_id == objekt.id,
                                        VotTermin.status.in_(OBJEKT_TERMIN_STATUS)).count()):
        gruende.append("aktiver Termin")
    if (session.query(Erfassung).filter(Erfassung.objekt_id == objekt.id,
                                        Erfassung.archiviert.is_(False)).count()):
        gruende.append("Erfassung")
    if (session.query(Angebot).filter(Angebot.objekt_id == objekt.id,
                                      Angebot.archiviert.is_(False)).count()):
        gruende.append("Angebot")
    return ", ".join(gruende)


def objekte_kontext(session: Session, vorgang: Vorgang, kunde: Kunde | None, pflicht: dict,
                    benutzer_map: dict | None = None, erfassungen: list | None = None,
                    angebote: list | None = None) -> dict:
    """Block „Objekte“ (Phase 153): Karten je aktivem Objekt mit Termin-Status
    (objekt_termine), Erfassungs-/Angebots-Chips, offenen Pflicht-Keys, Deaktivieren-
    Sperre und Pfeil-Zuständen; `mehrere` steuert, ob die Kartei Karten zeigt (sonst nur die
    bekannten Adressfelder + „Weiteres Objekt hinzufügen“)."""
    benutzer_map = benutzer_map or {}
    alle = objekte_modul.objekte_fuer(session, vorgang.id, nur_aktive=False)
    aktive = [o for o in alle if o.aktiv]
    if erfassungen is None:
        erfassungen = session.query(Erfassung).filter(Erfassung.vorgang_id == vorgang.id).all()
    if angebote is None:
        angebote = session.query(Angebot).filter(Angebot.vorgang_id == vorgang.id).all()
    termin_je: dict = {}
    for eintrag in objekt_termine(session, vorgang, aktive):
        o = eintrag.get("objekt") if isinstance(eintrag, dict) else None
        oid = getattr(o, "id", o)
        if oid is not None:
            termin_je[int(oid)] = eintrag
    haupt_id = next((o.id for o in alle if o.reihenfolge == 1), aktive[0].id if aktive else None)
    je_objekt = pflicht.get("objekte", {}) if pflicht else {}
    liste = []
    for pos, o in enumerate(aktive):
        ist_haupt = o.id == haupt_id
        eintrag = termin_je.get(o.id) or {}
        termin = eintrag.get("termin")
        erf = [e for e in erfassungen if e.objekt_id == o.id or (ist_haupt and not e.objekt_id)]
        ang = [a for a in angebote if a.objekt_id == o.id or (ist_haupt and not a.objekt_id)]
        liste.append({
            "objekt": o, "id": o.id, "haupt": ist_haupt, "nummer": pos + 1,
            "interessen": objekte_modul.interessen_liste(o),
            "rechnung": objekt_rechnung(o, kunde),
            "rechnung_abweichend": bool(o.rechnung_abweichend),
            "termin": termin, "vorgemerkt": bool(eintrag.get("vorgemerkt")),
            "termin_ad": benutzer_map.get(termin.ad_id) if termin is not None else None,
            "erfassungen": erf, "angebote": ang,
            "pflicht_keys": sorted(je_objekt.get(o.id, set())),
            "deaktivieren_grund": "" if ist_haupt else objekt_haengt(session, vorgang, o),
            "kann_hoch": (not ist_haupt) and pos > 1,
            "kann_runter": (not ist_haupt) and pos < len(aktive) - 1,
            "feld_url": f"/lead-management/lead/{vorgang.id}/objekt/{o.id}",
            "text": objekte_modul.objekt_text(o),
        })
    return {"liste": liste, "inaktive": [o for o in alle if not o.aktiv],
            "anzahl": len(liste), "mehrere": len(liste) > 1,
            "ohne_termin": sum(1 for e in liste if e["termin"] is None)}


def objekt_feld_speichern(session: Session, vorgang: Vorgang, kunde: Kunde | None,
                          objekt: VorgangObjekt, feld: str, wert, benutzer=None) -> dict:
    """Autospeichern eines Objektfelds (POST /lead/{id}/objekt/{objekt_id}, JSON {feld, wert}).
    Hauptobjekt: Adresse/Objektart/Parteien/Interessen/Rechnungsadresse laufen über die
    Kundenfelder (feld_speichern → hauptobjekt_sync); weitere Objekte schreiben
    vorgang_objekte direkt, Interessen des Vorgangs = Vereinigung (Kunde.interesse)."""
    label = OBJEKT_FELD_LABELS.get(feld)
    if label is None or objekt.vorgang_id != vorgang.id:
        return {"ok": False, "wert": "", "meldung": "Feld unbekannt.", "geaendert": False}
    if objekt.reihenfolge == 1 and kunde is not None and feld in _HAUPT_UEBER_KUNDE:
        ergebnis = feld_speichern(session, vorgang, kunde, feld, wert, benutzer=benutzer)
        ergebnis["objekt_id"] = objekt.id
        return ergebnis
    praefix = f"{objekt.bezeichnung or 'Objekt'} – "

    def fehler(text: str, alt=""):
        return {"ok": False, "wert": "" if alt is None else alt, "meldung": text,
                "geaendert": False, "objekt_id": objekt.id}

    def ok(neu, meldung: str = "", geaendert: bool = True):
        return {"ok": True, "wert": "" if neu is None else neu,
                "meldung": meldung or ("Gespeichert." if geaendert else "Keine Änderung."),
                "geaendert": geaendert, "objekt_id": objekt.id}

    if feld == "interesse":
        alt_liste = objekte_modul.interessen_liste(objekt)
        if isinstance(wert, (list, tuple)):
            codes = [str(w).strip().upper() for w in wert if str(w).strip()]
        else:
            codes = [c.strip().upper() for c in str(wert or "").split(",") if c.strip()]
        fremd = [c for c in codes if c not in INTERESSE_CODES_V31]
        if fremd:
            return fehler("Interesse unbekannt: " + ", ".join(fremd), ",".join(alt_liste))
        neu_liste = sparten_modul.codes(codes)
        if neu_liste == alt_liste:
            return ok(",".join(neu_liste), "Keine Änderung.", geaendert=False)
        objekte_modul.interessen_setzen(objekt, neu_liste)
        _aenderung(session, vorgang, praefix + label, ", ".join(alt_liste), ", ".join(neu_liste), benutzer)
        haupt = objekte_modul.hauptobjekt(session, vorgang.id)
        if haupt is not None:
            objekte_modul.hauptobjekt_sync(session, haupt, kunde=kunde)   # Kunde.interesse = Vereinigung
        session.flush()
        return ok(",".join(neu_liste))
    alt = getattr(objekt, feld, None)
    if feld == "bezeichnung":
        neu = _norm_text(wert, 100)
        if not neu:
            return fehler("Bezeichnung darf nicht leer sein.", alt or "")
    elif feld in ("plz", "rechnung_plz"):
        neu = _norm_text(wert, 10).replace(" ", "")
        if neu and not re.fullmatch(r"\d{5}", neu):
            return fehler("PLZ muss aus 5 Ziffern bestehen.", alt or "")
    elif feld == "objektart":
        neu = _norm_text(wert, 10).upper() or None
        codes = {code for code, _bez, _p in lead_v2.objektarten(session)}
        if neu and neu not in codes:
            return fehler("Objektart unbekannt.", alt or "")
    elif feld == "parteien":
        roh = _norm_text(wert, 5)
        if not roh:
            neu = None
        elif roh.isdigit() and int(roh) > 0:
            neu = int(roh)
        else:
            return fehler("Anzahl Parteien muss eine Zahl > 0 sein.", str(alt) if alt else "")
    elif feld == "rechnung_abweichend":
        neu = _wahr(wert)
        if bool(alt) == neu:
            return ok("1" if neu else "", "Keine Änderung.", geaendert=False)
        objekt.rechnung_abweichend = neu
        _aenderung(session, vorgang, praefix + "Rechnungsadresse identisch mit der Objektadresse",
                   "nein" if alt else "ja", "nein" if neu else "ja", benutzer)
        session.flush()
        return ok("1" if neu else "", "Rechnungsadresse abweichend – bitte Felder füllen." if neu
                  else "Rechnungsadresse = Objektadresse.")
    else:
        neu = _norm_text(wert, {"strasse": 200, "ort": 100, "rechnung_name": 200,
                                "rechnung_strasse": 200, "rechnung_ort": 100}.get(feld, 200))
    alt_vgl = "" if alt is None else str(alt)
    neu_vgl = "" if neu is None else str(neu)
    if alt_vgl == neu_vgl:
        return ok(neu_vgl, "Keine Änderung.", geaendert=False)
    setattr(objekt, feld, neu)
    if feld in ("strasse", "plz", "ort"):
        # Adresse geändert → Geocoding je Objekt (AT, Lauf geocoding) neu; Koordinaten verwerfen
        objekt.lat, objekt.lon, objekt.geocode_status = None, None, None
        vorschlaege_cache_leeren(vorgang.id)
    if feld == "bezeichnung":
        # v35 (PLAN_LEAD_V6 Phase 186, Agent G): Galerie-Ordner „Objekt <Bezeichnung>“ folgt der
        # Umbenennung (nur das Feld ordner der Fotos, Dateien bleiben liegen)
        from app import galerie as galerie_modul
        galerie_modul.objekt_umbenannt(session, objekt, alt_vgl)
    _aenderung(session, vorgang, praefix + label, alt_vgl, neu_vgl, benutzer)
    session.flush()
    return ok(neu_vgl)


def objekt_anlegen_aus_form(session: Session, vorgang: Vorgang, kunde: Kunde | None, form,
                            benutzer=None) -> tuple[VorgangObjekt | None, str]:
    """„Objekt hinzufügen“ (POST /lead/{id}/objekt): Pflicht Straße/PLZ/Ort, Objektart aus dem
    Blatt Objektarten, Parteien bei MFH, Interessen (inkl. MS/WA/DMS), MFH-Frage
    Rechnungsadresse; Aktivität „Objekt hinzugefügt“. Liefert (objekt, meldung)."""
    getlist = form.getlist if hasattr(form, "getlist") else (lambda name: [form.get(name)] if form.get(name) else [])
    strasse = _text(form, "strasse", 200)
    plz = _text(form, "plz", 10).replace(" ", "")
    ort = _text(form, "ort", 100)
    if not (strasse and plz and ort):
        return None, "Objekt nicht angelegt: Straße, PLZ und Ort sind Pflicht."
    if not re.fullmatch(r"\d{5}", plz):
        return None, "Objekt nicht angelegt: PLZ muss aus 5 Ziffern bestehen."
    objektart = _text(form, "objektart", 10).upper() or None
    if objektart and objektart not in {code for code, _b, _p in lead_v2.objektarten(session)}:
        return None, "Objekt nicht angelegt: Objektart unbekannt."
    roh = _text(form, "parteien", 5)
    parteien = int(roh) if roh.isdigit() and int(roh) > 0 else None
    if objektart == "MFH" and roh and parteien is None:
        return None, "Objekt nicht angelegt: Anzahl Parteien muss eine Zahl > 0 sein."
    interessen = [str(c).strip().upper() for c in getlist("interesse") if str(c).strip()]
    fremd = [c for c in interessen if c not in INTERESSE_CODES_V31]
    if fremd:
        return None, "Objekt nicht angelegt: Interesse unbekannt: " + ", ".join(fremd)
    objekt = objekte_modul.objekt_anlegen(session, vorgang, strasse, plz, ort,
                                          _text(form, "bezeichnung", 100), objektart, parteien, interessen)
    if objektart == "MFH":
        objekt.rechnung_abweichend = _text(form, "rechnung_identisch", 10).lower() in ("nein", "0", "false")
        for f in ("rechnung_name", "rechnung_strasse", "rechnung_plz", "rechnung_ort"):
            setattr(objekt, f, _text(form, f, 10 if f == "rechnung_plz" else 200))
    haupt = objekte_modul.hauptobjekt(session, vorgang.id)
    if haupt is not None:
        objekte_modul.hauptobjekt_sync(session, haupt, kunde=kunde)   # Kunde.interesse = Vereinigung
    kern.aktivitaet(session, vorgang.id, "aenderung",
                    f"Objekt hinzugefügt: {objekte_modul.objekt_text(objekt)}"
                    + (f" ({objektart}{', ' + str(parteien) + ' Parteien' if parteien else ''})" if objektart else "")
                    + (f" – Interessen {', '.join(objekte_modul.interessen_liste(objekt))}"
                       if objekte_modul.interessen_liste(objekt) else ""), benutzer=benutzer)
    session.flush()
    vorschlaege_cache_leeren(vorgang.id)
    return objekt, f"Objekt „{objekt.bezeichnung}“ angelegt."


def objekt_deaktivieren(session: Session, vorgang: Vorgang, objekt: VorgangObjekt,
                        benutzer=None) -> tuple[bool, str]:
    """Deaktivieren statt Löschen – gesperrt, wenn Termin/Erfassung/Angebot daran hängt."""
    if objekt.reihenfolge == 1:
        return False, "Das Hauptobjekt (Kundenadresse) kann nicht deaktiviert werden."
    if not objekt.aktiv:
        return False, "Objekt ist bereits deaktiviert."
    grund = objekt_haengt(session, vorgang, objekt)
    if grund:
        return False, f"Objekt kann nicht deaktiviert werden – daran hängt: {grund}."
    objekt.aktiv = False
    haupt = objekte_modul.hauptobjekt(session, vorgang.id)
    if haupt is not None:
        objekte_modul.hauptobjekt_sync(session, haupt)
    kern.aktivitaet(session, vorgang.id, "aenderung",
                    f"Objekt deaktiviert: {objekte_modul.objekt_text(objekt)}", benutzer=benutzer)
    session.flush()
    vorschlaege_cache_leeren(vorgang.id)
    return True, f"Objekt „{objekt.bezeichnung}“ deaktiviert."


def objekt_aktivieren(session: Session, vorgang: Vorgang, objekt: VorgangObjekt,
                      benutzer=None) -> tuple[bool, str]:
    if objekt.aktiv:
        return False, "Objekt ist bereits aktiv."
    objekt.aktiv = True
    haupt = objekte_modul.hauptobjekt(session, vorgang.id)
    if haupt is not None:
        objekte_modul.hauptobjekt_sync(session, haupt)
    kern.aktivitaet(session, vorgang.id, "aenderung",
                    f"Objekt wieder aktiviert: {objekte_modul.objekt_text(objekt)}", benutzer=benutzer)
    session.flush()
    return True, f"Objekt „{objekt.bezeichnung}“ wieder aktiv."


def objekt_reihenfolge(session: Session, vorgang: Vorgang, objekt: VorgangObjekt,
                       richtung: str, benutzer=None) -> tuple[bool, str]:
    """Reihenfolge per Pfeil. Das Hauptobjekt (reihenfolge 1 = Kundenadresse, Sync mit den
    Kundenfeldern) bleibt immer an erster Stelle – die Pfeile ordnen nur Objekt 2 … n
    [Entscheidung K, Rückfrage im Bericht]."""
    aktive = objekte_modul.objekte_fuer(session, vorgang.id)
    try:
        idx = [o.id for o in aktive].index(objekt.id)
    except ValueError:
        return False, "Objekt nicht gefunden."
    if idx == 0 or objekt.reihenfolge == 1:
        return False, "Das Hauptobjekt bleibt an erster Stelle (Kundenadresse)."
    ziel = idx - 1 if richtung == "hoch" else idx + 1
    if ziel < 1 or ziel >= len(aktive):
        return False, "Keine Änderung – das Objekt steht bereits am Rand."
    # lückenlos durchnummerieren (Hauptobjekt bleibt 1), dann tauschen
    for i, o in enumerate(aktive):
        o.reihenfolge = i + 1
    anderes = aktive[ziel]
    objekt.reihenfolge, anderes.reihenfolge = anderes.reihenfolge, objekt.reihenfolge
    kern.aktivitaet(session, vorgang.id, "aenderung",
                    f"Objekt-Reihenfolge: {objekt.bezeichnung} nach {'oben' if richtung == 'hoch' else 'unten'}",
                    benutzer=benutzer)
    session.flush()
    return True, "Reihenfolge geändert."


# --- v31 (PLAN_LEAD_V5 Phase 157): Status aus der Kartei -----------------------------------

def status_wahl(session: Session, vorgang: Vorgang) -> dict:
    """Statuswechsel in der Statuskette/Dropdown des Kopfs: manuell setzbare Phasen mit
    Label aus dem Blatt Status (lead_boards.auswahl_listen – dieselben Regeln, Gründe und
    Pflichtangaben wie der Inline-Edit der Boards), abgeleitete Phasen nicht wählbar,
    Verloren nur mit Grund-Dialog, Nachbearbeitung über die bestehende Route; der
    Seitenzustand „Nicht erreicht“ entsteht nur über die Anruf-Kaskade [ANNAHME]."""
    from app import lead_boards
    listen = lead_boards.auswahl_listen(session)
    aktuell = vorgang.lead_phase or "neu"
    eintraege = []
    for s in listen["status_wahl"]:
        if not s.get("setzbar") or s.get("doppelt") or s["key"] == "nicht_erreicht":
            continue
        eintraege.append({"key": s["key"], "label": s["label"], "grund": s.get("grund", ""),
                          "farbe": s.get("farbe", ""),
                          "aktiv": aktuell == s["key"] or aktuell in (s.get("gleiche") or [])})
        if s["key"] == "zurueckgestellt":
            eintraege.append({"key": "nachbearbeitung", "label": "Nachbearbeitung", "grund": "",
                              "farbe": "", "aktiv": False, "dialog": "dlg-nachbearbeitung"})
    return {"eintraege": eintraege, "gruende": listen.get("gruende", {}), "aktuell": aktuell,
            "setzbar": [e["key"] for e in eintraege]}


def status_aus_kartei(session: Session, vorgang: Vorgang, ziel: str, benutzer=None,
                      grund: str = "", grund_text: str = "", bis=None) -> tuple[bool, str]:
    """Statuswechsel aus der Kartei → lead_boards.status_setzen (Pflichtgründe, Verloren mit
    Angebots-Ablehnung); Nachbearbeitung → bestehende Funktion nachbearbeitung()."""
    from app import lead_boards
    ziel = (ziel or "").strip()
    if ziel == "nachbearbeitung":
        datum = None
        if bis:
            try:
                datum = datetime.strptime(str(bis)[:10], "%Y-%m-%d")
            except ValueError:
                return False, "Nachbearbeitung: Wiedervorlage-Datum ungültig."
        wann = nachbearbeitung(session, vorgang, datum, grund_text, benutzer=benutzer)
        return True, f"Nachbearbeitung – Wiedervorlage {wann.strftime('%d.%m.%Y')}."
    return lead_boards.status_setzen(session, vorgang, ziel, benutzer=benutzer, grund=grund,
                                     grund_text=grund_text, bis=bis, quelle="Kartei")


# --- v31 (PLAN_LEAD_V5 Phase 158): E-Mail aus der Kundenkartei mit Vorlage ------------------
# Vorschau und Senden laufen über T's Endpunkte (routers/lm_mail.py):
#   GET  /lead-management/lead/{id}/mail/vorschau.json?vorlage=&objekt_id=&termin_id=
#   POST /lead-management/lead/{id}/mail/senden  (JSON {vorlage, betreff, text, objekt_id, termin_id})
# Hier nur die Auswahlliste der Vorlagen für den Dialog (Erstaufbau ohne JavaScript).

TERMIN_VORLAGEN = ("terminbestaetigung", "terminerinnerung", "terminaenderung", "terminabsage",
                   "terminbestaetigung_objekte")
_PLATZHALTER_REST = re.compile(r"\{[a-z_]{3,}\}")


def ist_termin_vorlage(key: str) -> bool:
    key = key or ""
    return key in TERMIN_VORLAGEN or key.startswith("terminbestaetigung")


def mail_vorlagen_liste(session: Session) -> list[dict]:
    """Alle Lead-Vorlagen für den Dialog: Baum des Editors (lead_mail.vorlagen_katalog –
    Eingang · Kontakt · Terminbestätigung je Vertriebler · Termin · Sonstige, inkl.
    terminbestaetigung_objekte sobald T sie führt); ausgeblendete (nurture, nicht_erreicht)
    und nicht angelegte Vertriebler-Vorlagen fehlen."""
    from app import lead_mail
    ausgeblendet = set(getattr(lead_mail, "VORLAGEN_AUSGEBLENDET", ())) | {"nicht_erreicht"}
    liste = []
    try:
        katalog = lead_mail.vorlagen_katalog(session)
    except Exception:   # noqa: BLE001
        katalog = []
    for kat in katalog:
        for e in kat.get("eintraege", []):
            key = e.get("key", "")
            if not key or key in ausgeblendet or not e.get("vorhanden", True):
                continue
            name = e.get("name") or key
            if key == getattr(lead_mail, "TERMIN_VORLAGE", "terminbestaetigung"):
                name = "Terminbestätigung (Standard)"
            liste.append({"key": key, "name": name, "kategorie": kat.get("name", ""),
                          "termin": ist_termin_vorlage(key)})
    if not liste:
        for key, (name, _b, _t) in lead_mail.VORLAGEN_START.items():
            if key not in ausgeblendet:
                liste.append({"key": key, "name": name, "kategorie": "", "termin": ist_termin_vorlage(key)})
    return liste


# --- v31 (PLAN_LEAD_V5 Phase 156): Dropdowns Innendienst/Außendienst (Vertrag B) ------------

def innendienst_auswahl(session: Session, vorgang: Vorgang) -> list[dict]:
    """Innendienst-Dropdown der Kartei: nur Benutzer mit Häkchen „Leadmanager“
    (lead_dropdowns.leadmanager_auswahl – Vertrag B, Rückfall: aktive Benutzer mit
    benutzer.leadmanager, nach Vorname); der aktuelle Zuständige ohne Häkchen bleibt als
    „(nicht mehr wählbar)“ sichtbar."""
    aktuell = vorgang.leadmanager_id
    try:
        from app import lead_dropdowns
        fn = getattr(lead_dropdowns, "leadmanager_auswahl", None)
        if callable(fn):
            liste = []
            for e in fn(session, aktuell_id=aktuell):
                if isinstance(e, dict):
                    liste.append({"id": e.get("id"), "name": e.get("name", ""),
                                  "waehlbar": e.get("waehlbar", True)})
                else:
                    liste.append({"id": e[0], "name": e[1], "waehlbar": e[2] if len(e) > 2 else True})
            return liste
    except Exception:   # noqa: BLE001 – Rückfall
        pass
    kandidaten = [b for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
                  if getattr(b, "leadmanager", False)]
    kandidaten.sort(key=lambda b: ((b.vorname or b.name or "").lower(), (b.name or "").lower()))
    liste = [{"id": b.id, "name": b.name, "waehlbar": True} for b in kandidaten]
    if aktuell and aktuell not in {b.id for b in kandidaten}:
        b = session.get(Benutzer, aktuell)
        if b is not None:
            liste.append({"id": b.id, "name": f"{b.name} (nicht mehr wählbar)", "waehlbar": False})
    return liste


# --- Kontext für das Template --------------------------------------------------------

def _vorschlaege_anzahl(session: Session) -> int:
    """v29 (PLAN_LEAD_V4 Phase 143): Anzahl der Vorschläge im Block Termine
    (Parameter vorschlaege_anzahl, Standard 3) – dieselbe Zahl wie im Assistenten."""
    try:
        from app import lead_termin
        return lead_termin.vorschlaege_anzahl(session)
    except Exception:
        return 3


def _ad_auswahl(session: Session, vorgang: Vorgang, kunde: Kunde) -> list:
    """Außendienst-Dropdown. v31 (Phase 156, Vertrag B): lead_dropdowns.ad_auswahl(session,
    vorgang) → nur angestellte AD ohne terminiert_selbst; liegt der Lead bei einem
    Handelsvertreter, nur dessen Gruppe (René → René; Simon-Gruppe). Rückfall bis B fertig
    ist: angestellte AD, bei HV-Lead die HV derselben Gruppe (lead_v2.hv_gruppe_von).
    Der aktuelle Zuständige bleibt immer wählbar; Handelsvertreter-Einträge mit
    Ausschlussgrund (F14) werden im Template deaktiviert."""
    profile = {p.benutzer_id: p for p in session.query(AdProfil)}
    sperre = lead_v2.hv_ausgeschlossen(session, vorgang, kunde)
    erlaubt: list[int] | None = None
    try:
        from app import lead_dropdowns
        fn = getattr(lead_dropdowns, "ad_auswahl", None)
        if callable(fn):
            erlaubt = []
            for e in fn(session, vorgang):
                erlaubt.append(int(e["id"] if isinstance(e, dict) else e[0]))
    except Exception:   # noqa: BLE001 – Rückfall
        erlaubt = None
    alle = (session.query(Benutzer).filter(Benutzer.aktiv.is_(True),
                                           rollen_modul.filter_basis("aussendienst"))
            .order_by(Benutzer.name).all())
    if erlaubt is None:
        hv_aktuell = hv_am_vorgang(session, vorgang)
        if hv_aktuell is None:
            erlaubt = [b.id for b in alle
                       if not (profile.get(b.id) is not None and profile[b.id].terminiert_selbst)]
        else:
            gruppe = lead_v2.hv_gruppe_von(session, hv_aktuell.id)
            erlaubt = [b.id for b in alle
                       if profile.get(b.id) is not None and profile[b.id].terminiert_selbst
                       and lead_v2.hv_gruppe_von(session, b.id) == gruppe]
    if vorgang.ad_id and vorgang.ad_id not in erlaubt:
        erlaubt.append(vorgang.ad_id)
    kandidaten = [b for b in alle if b.id in erlaubt]
    fehlend = [i for i in erlaubt if i not in {b.id for b in alle}]
    if fehlend:
        kandidaten += [b for b in session.query(Benutzer).filter(Benutzer.id.in_(fehlend))]
    auswahl = []
    for b in kandidaten:
        profil = profile.get(b.id)
        # v33 (Phase 167): HV über Rollen-Kennzeichen oder gespiegeltes Profil-Kennzeichen
        hv = bool(profil is not None and profil.terminiert_selbst) or b.hat_kennzeichen("handelsvertreter")
        ok, grund = lead_v2.kompetenz_passt(profil, kunde.interessen if kunde else [],
                                            kunde.objektart if kunde else None)
        auswahl.append({"benutzer": b, "hv": hv, "gesperrt": sperre if hv else "",
                        "kompetenz_ok": ok, "kompetenz_grund": grund,
                        "aktiv_terminierung": profil.aktiv_terminierung if profil else True})
    return auswahl


def _taifun_kontext(session: Session, vorgang: Vorgang, kunde, benutzer, readonly: bool) -> dict | None:
    """v35 (Phase 183, Agent T): Kontext `taifun` aus app/taifun_export.kartei_kontext."""
    try:
        from app import taifun_export
        return taifun_export.kartei_kontext(session, vorgang, kunde, benutzer, readonly)
    except Exception:   # noqa: BLE001 – die Kartei darf daran nie scheitern
        return None


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
        "offen": [], "offen_keys": set(), "pflicht": set(), "labels": PFLICHT_LABELS,
        "objekte": {}, "ad_hinweis": AD_PFLICHT_HINWEIS}
    terminierung = terminierung_pruefung(session, kunde, vorgang, termine)
    status_zeile = logik.status_zeile(vorgang.lead_phase or "neu")
    status_farben = {z.phase: z.farbe for z in logik.status_zeilen}
    kanal_werte = kern.kanal_werte(session)
    # v35 (PLAN_LEAD_V6 Phase 184): Dropdown nach Häufigkeit; der aktuelle Wert bleibt wählbar –
    # inaktiv/unbekannt als „(nicht mehr wählbar)“, „?“ als „Vertriebskanal unklar“ (kanal_labels)
    kanal_labels: dict = {}
    if kunde and kunde.vertriebskanal and kunde.vertriebskanal not in kanal_werte:
        kanal_werte.append(kunde.vertriebskanal)
        if lead_kanaele.ist_unklar(kunde.vertriebskanal):
            kanal_labels[kunde.vertriebskanal] = f"? – {lead_kanaele.UNKLAR_HINWEIS}"
        else:
            kanal_labels[kunde.vertriebskanal] = f"{kunde.vertriebskanal} (nicht mehr wählbar)"
    aktiver_termin = next((t for t in termine if t.status in TERMIN_OFFEN), None)
    heute = datetime.now()
    hv = lead_v2.ist_handelsvertreter(session, benutzer)
    # v25 (Phase 119): Statuskette mit Labels aus dem Blatt Status (beide
    # Kontakt-Phasen „Kontaktiert“), Score-Schalter, Startzustand Block Termine
    from app import lead_anrufliste, lead_todos
    phase = vorgang.lead_phase or "neu"
    seitenzustand = None
    if phase in SEITENZUSTAENDE:
        seitenzustand = {"phase": phase, "label": phasen_label(logik, phase),
                         "farbe": status_farben.get(phase, "")}
    # v31 (PLAN_LEAD_V5): Objekte, Großkunde, Testphase-Schalter, Status aus der Kartei,
    # Timeline mit Herkunft (vorgang_verlauf), To-Do-Zeilen für die schmale Spalte
    objekte = objekte_kontext(session, vorgang, kunde, pflicht, benutzer_map, erfassungen, angebote)
    # v35 (PLAN_LEAD_V6 Phase 186, Agent G): Fotos je Objekt – Block an der Objektkarte
    # (kartei_objekte.html, Makro objekt_fotos); Kontext aus galerie.objektfotos_kontext
    try:
        objektfotos = galerie_modul.objektfotos_kontext(session, vorgang, benutzer)
    except Exception:   # noqa: BLE001 – die Kartei darf daran nie scheitern
        objektfotos = dict(galerie_modul.OBJEKTFOTOS_LEER)
    try:
        vorgang_interessen = objekte_modul.vorgang_interessen(session, vorgang.id) or (kunde.interessen if kunde else [])
    except Exception:   # noqa: BLE001
        vorgang_interessen = kunde.interessen if kunde else []
    terminierung_aktiv = lead_v5.terminierung_aktiv(session)
    mail_versand_aktiv = lead_v5.mail_versand_aktiv(session)
    demo_sperre = kern.demo_aktiv(session) and not vorgang.demo
    langnamen = sparten_modul.langnamen_laden(kern.parameter_holen(session, "sparten_langnamen", ""))
    try:
        todo_zeilen = lead_todos.zeilen(session, todos, heute)
    except Exception:   # noqa: BLE001
        todo_zeilen = []
    verlauf_karten = verlauf(session, vorgang, benutzer_map)
    wv_vorschlag = lead_v5.runden_5min((heute + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0))
    # v31 (Phase 153/159, Vertrag T): Testphase-Flags, Termin je Objekt, Hinweis „n von m Objekten
    # ohne Termin“, vorgemerkte Objekttermine und Vorbelegung der Bestätigungs-Wahl
    testphase = {"terminierung_aktiv": terminierung_aktiv, "testphase_hinweis": lead_v5.TESTPHASE_HINWEIS,
                 "mail_versand_aktiv": mail_versand_aktiv, "mailsperre_hinweis": lead_v5.MAILSPERRE_HINWEIS}
    objekt_zeilen, objekte_hinweis_text, bestaetigung_vorbelegung = [], "", "auto"
    vorgemerkte = terminierung.get("vorgemerkte") or []
    try:
        from app import lead_termin as termin_modul
        fn = getattr(termin_modul, "testphase_kontext", None)
        if callable(fn):
            testphase.update(fn(session))
        objekt_zeilen = objekt_termine(session, vorgang)
        fn = getattr(termin_modul, "objekte_hinweis", None)
        objekte_hinweis_text = fn(session, vorgang) if callable(fn) else ""
        fn = getattr(termin_modul, "bestaetigung_vorbelegung", None)
        bestaetigung_vorbelegung = fn(vorgemerkte) if callable(fn) else "auto"
    except Exception:   # noqa: BLE001 – Kartei bleibt ohne T's Zusatzdaten lauffähig
        pass
    if not objekte_hinweis_text and objekte["mehrere"] and objekte["ohne_termin"]:
        objekte_hinweis_text = f"{objekte['ohne_termin']} von {objekte['anzahl']} Objekten ohne Termin"
    try:
        mail_absender = lead_mail.absender(session)
    except Exception:   # noqa: BLE001
        mail_absender = "termin@friondo.de"
    return {
        **testphase,
        "objekt_zeilen": objekt_zeilen, "objekte_hinweis": objekte_hinweis_text,
        "vorgemerkte": vorgemerkte, "bestaetigung_vorbelegung": bestaetigung_vorbelegung,
        "termine_aktiv": [t for t in termine if t.status in TERMIN_OFFEN],
        "mail_absender": mail_absender,
        "vorgang": vorgang, "kunde": kunde, "lead": lead, "benutzer": benutzer,
        "benutzer_map": benutzer_map, "lead_kontext": akte, "readonly": readonly,
        "ist_hv": hv, "heute": heute,
        "lead_phasen_namen": LEAD_PHASEN_NAMEN, "status_zeile": status_zeile,
        "status_farben": status_farben,
        "phasen_kette": phasen_kette(logik, phase), "seitenzustand": seitenzustand,
        "phase_label": phasen_label(logik, phase),
        "score_aktiv": lead_v2.score_aktiv(session),
        "telefon_href": lead_anrufliste.tel_href(kunde.telefon) if kunde and kunde.telefon else "",
        "vorschlaege": vorschlaege_zustand(session, vorgang, kunde, benutzer),
        "vorschlaege_texte": VORSCHLAEGE_TEXTE,
        "vorschlaege_anzahl": _vorschlaege_anzahl(session),   # v29 (Phase 143): 3 statt 5
        "feld_url": f"/lead-management/lead/{vorgang.id}/feld",
        "vorschlaege_url": f"/lead-management/lead/{vorgang.id}/termin/vorschlaege.json",
        "kalender_url": f"/lead-management/lead/{vorgang.id}/termin/kalender.json",
        "buchen_url": f"/lead-management/lead/{vorgang.id}/termin",
        "wunschzeiten": akte.get("wunschzeiten") or [],
        "initialen": kunden_initialen(kunde), "initialen_fn": initialen,
        "timeline": verlauf_karten, "timeline_gruppen": TIMELINE_GRUPPEN,
        "herkunft_namen": HERKUNFT_NAMEN, "herkunft_klassen": HERKUNFT_KLASSEN,
        "mails": mails, "anrufe": [e for e in zeitstrahl if e["typ"] == "anruf"],
        "termine": termine, "aktiver_termin": aktiver_termin,
        "termin_status_namen": TERMIN_STATUS_NAMEN, "termin_typ_namen": TERMIN_TYP_NAMEN,
        "termin_medium_namen": TERMIN_MEDIUM_NAMEN,
        "angebote": angebote, "erfassungen": erfassungen, "projekte": projekte,
        "projekt_modul_ok": projekt_modul_ok,
        "projekt_block": projekt_block(session, vorgang) if projekt_modul_ok else None,
        "anhaenge": anhaenge, "anhaenge_bilder": [a for a in anhaenge if a.bild],
        "darf_hochladen": darf_hochladen,
        "todos": todos, "todos_offen": todos_offen, "todo_zeilen": todo_zeilen,
        "todo_empfaenger": lead_todos.empfaenger_liste(session),
        "pflicht": pflicht, "pflicht_offen": pflicht["offen"],
        "terminierung": terminierung,
        # v35 (PLAN_LEAD_V6 Phase 183, Agent T): TAIFUN-Übergabe (Knopf, Badge, Rückfrage,
        # Hinweisbalken, Testphase-Export) – die Kartei bleibt ohne das Modul lauffähig
        "taifun": _taifun_kontext(session, vorgang, kunde, benutzer, readonly),
        "objektarten": lead_v2.objektarten(session), "anreden": ANREDEN,
        "interessen": INTERESSEN, "interessen_wahl": INTERESSEN_WAHL,
        "sparten_langnamen": langnamen, "kanal_werte": kanal_werte,
        "kanal_labels": kanal_labels,   # v35 (Phase 184): „(nicht mehr wählbar)“ / „? – Vertriebskanal klären“
        "innendienst_wahl": innendienst_auswahl(session, vorgang),
        "ad_wahl": _ad_auswahl(session, vorgang, kunde) if kunde else [],
        "hv_sperre": lead_v2.hv_ausgeschlossen(session, vorgang, kunde) if kunde else "",
        # v33 (PLAN_V20 Phase 175): Kennzeichen „Simons Gruppe (noch nicht verteilt)“
        "hv_gruppe_offen": lead_v2.hv_gruppe_offen(session, vorgang),
        "hv_gruppe_kennzeichen": lead_v2.HV_GRUPPE_KENNZEICHEN,
        "demo": kern.demo_aktiv(session),
        # v31 (Phase 159): Buchen/Vormerken nur in der Freischaltung (Schalter) – im Demo-
        # Modus (bis zur Umstellung) weiter nur Demo-Leads
        "buchbar": terminierung_aktiv and not demo_sperre,
        "terminierung_aktiv": terminierung_aktiv, "mail_versand_aktiv": mail_versand_aktiv,
        "testphase_hinweis": lead_v5.TESTPHASE_HINWEIS, "mailsperre_hinweis": lead_v5.MAILSPERRE_HINWEIS,
        "sperre_text": ("Demo-Modus: Buchung nur für Demo-Leads" if demo_sperre
                        else (lead_v5.TESTPHASE_HINWEIS if not terminierung_aktiv else "")),
        "objekte": objekte, "vorgang_interessen": vorgang_interessen,
        "objektfotos": objektfotos,   # v35 (Phase 186, Agent G): Fotos je Objekt
        "rechnung_abweichend": rechnung_abweichend(session, vorgang, kunde),
        "grosskunde": bool(kunde is not None and kunde.grosskunde),
        "grosskunde_farbe": (kern.parameter_holen(session, "grosskunde_farbe", "") or "").strip(),
        "status_wahl": status_wahl(session, vorgang) if not readonly else {"eintraege": [], "gruende": {}, "aktuell": phase, "setzbar": []},
        "status_url": f"/lead-management/lead/{vorgang.id}/status",
        "objekt_url": f"/lead-management/lead/{vorgang.id}/objekt",
        # v31 (Phase 158, Vertrag T): Vorschau/Senden des Dialogs über T's Routen (lm_mail.py)
        "mail_dialog_url": f"/lead-management/lead/{vorgang.id}/mail/vorschau.json",
        "mail_senden_url": f"/lead-management/lead/{vorgang.id}/mail/senden",
        "anruf_gesperrt": kern.versuche_gesperrt(session, vorgang),
        "versuche_max": kern.versuche_max(session),
        "vorlagen": [v["key"] for v in mail_vorlagen_liste(session)],
        "zurueck_gruende": logik.gruende_der_phase("zurueckgestellt"),
        "unq_gruende": logik.gruende_der_phase("unqualifiziert"),   # C3-Dialog (Phase 107)
        "no_show_gruende": logik.gruende_der_phase("no_show"),
        "nachbearbeitung_grund": nachbearbeitung_grund(session),
        "nachbearbeitung_bis": (heute + timedelta(days=wv_tage(session))).strftime("%Y-%m-%d"),
        "wv_tage": wv_tage(session),
        "wv_vorschlag": wv_vorschlag.strftime("%Y-%m-%dT%H:%M"),
        "kartei_url": f"/lead-management/lead/{vorgang.id}",
        # Prüfung F (Phase 118): die Icon-Leiste markiert das Board des Leads
        # (Hauptboard bzw. Deals laut Blatt Status), nicht pauschal das Hauptboard
        "nav_key": ("terminiert" if logik.board_fuer(vorgang.lead_phase or "neu")[0] == "terminiert"
                    else "hauptboard"),
        "notiz_url": (f"/vorgaenge/{vorgang.id}/notiz" if readonly
                      else f"/lead-management/lead/{vorgang.id}/notiz"),
        "erfassung_url": (f"/erfassung/sparten?kunde_id={kunde.id}"
                          + (f"&lead_id={vorgang.lead_id}" if vorgang.lead_id else "")) if kunde else "",
        "zaehler": {"termine": len(termine), "angebote": len(angebote),
                    "erfassungen": len(erfassungen), "projekte": len(projekte),
                    "anhaenge": len(anhaenge), "todos": len(todos_offen),
                    "timeline": len(verlauf_karten), "mails": len(mails),
                    "anrufe": sum(1 for e in zeitstrahl if e["typ"] == "anruf"),
                    "objekte": objekte["anzahl"]},
    }
