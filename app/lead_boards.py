# Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 105): Boards als Tabelle nach
# monday-Vorbild (A3/A4), Status → Board → Gruppe (H2, Blatt Status),
# Hauptboard (H4) und Board Terminiert (H5), generische Sammelaktionen (H3),
# Reiter Kontaktiert mit Rufnummernsuche E.164 (H7/D3), Spaltenkonfiguration
# je Nutzer (A-14). Die Lead-Phase bleibt die einzige Quelle der Wahrheit –
# die Gruppe ist eine Sicht darauf (logik.board_fuer) plus Terminprüfung.

import hashlib
import json
import re
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app import lead_v2
from app import leadmanagement as kern
from app import leadmanagement_logik
from app.models import (Angebot, AngebotsNotiz, Benutzer, Erfassung, Kunde, Lead,
                        LeadAktivitaet, LeadQuelle, Vorgang, VotTermin,
                        ANRUF_ERGEBNIS_NAMEN, LEAD_PHASEN, LEAD_PHASEN_NAMEN,
                        angebot_status_setzen)

# --- Boards, Gruppen, Spalten ------------------------------------------------------

BOARDS = {
    "hauptboard": {"titel": "Hauptboard", "untertitel": "Leads ohne Vor-Ort-Termin",
                   "gruppen": ["neu", "pausiert", "disqualifiziert"]},
    "terminiert": {"titel": "Terminiert", "untertitel": "Leads mit Vor-Ort-Termin – Angebot nachverfolgen",
                   "gruppen": ["angebotserstellung", "angebotsversand", "gewonnen", "verloren"]},
}
GRUPPEN_NAMEN = {
    "neu": "Neu", "pausiert": "Pausiert", "disqualifiziert": "Disqualifiziert",
    "angebotserstellung": "Angebotserstellung", "angebotsversand": "Angebotsversand",
    "gewonnen": "Gewonnen", "verloren": "Verloren",
}
GRUPPEN_ERKLAERUNG = {
    "neu": "noch nicht oder noch nicht erfolgreich kontaktiert – hier wird telefoniert",
    "pausiert": "zurückgestellt bis zur Wiedervorlage (kein Handlungsbedarf)",
    "disqualifiziert": "Kaskade ausgeschöpft oder kein Interesse (Pflichtgrund)",
    "angebotserstellung": "terminiert bzw. erfasst – Angebot wird geschrieben",
    "angebotsversand": "Angebot versendet – nachfassen (Hot-Ampel, Wiedervorlage)",
    "gewonnen": "Angebot angenommen (letzte 30 Tage, sonst Archiv)",
    "verloren": "mit Pflichtgrund verloren (letzte 30 Tage, sonst Archiv)",
}
# Standard eingeklappt: Endzustände und Disqualifiziert
GRUPPEN_EINGEKLAPPT = {"disqualifiziert", "gewonnen", "verloren"}

# Spalten (key, Titel, Standard sichtbar). Reihenfolge nach Screenshot 1
# (monday-Zeile); Interessen laut A3 „so weit vorn wie möglich“ nach dem
# Kanal. Nutzer ordnen/blenden je Board um (benutzer_einstellungen).
SPALTEN = [
    ("lead", "Lead", True), ("anrede", "Anrede", True), ("vorname", "Vorname", True),
    ("nachname", "Nachname", True), ("status", "Status", True),
    ("kanal", "Vertriebskanal", True), ("interessen", "Interessen", True),
    ("versuche", "Kontaktversuche", True), ("letzter_kontakt", "Letzter Kontakt", True),
    ("eingang", "Eingangsdatum", True), ("notiz", "Notiz", True),
    ("ad", "Außendienst", True), ("innendienst", "Innendienst", True),
    ("ort", "Ort", True), ("strasse", "Straße", True), ("telefon", "Telefon", True),
    ("email", "E-Mail", True), ("termin", "Vor-Ort-Termin", True),
    ("wiedervorlage", "Wiedervorlage", True),
]
# Board Terminiert: zusätzlich Erfassung/Angebot (Buttons + Sparten-Chips)
SPALTEN_TERMINIERT = SPALTEN[:5] + [("angebot", "Erfassung / Angebot", True)] + SPALTEN[5:]
SPALTEN_FEST = ("lead",)          # immer sichtbar, immer vorn
EINSTELLUNG_KEY = "boards_spalten"

# Abgeleitete Phasen sind nicht manuell setzbar (Termin/Erfassung/Angebot)
PHASEN_ABGELEITET = ("terminiert", "erfasst", "angebot", "gewonnen")
# Phasen mit Pflichtangaben im Dialog
PHASEN_MIT_GRUND = {"zurueckgestellt": "zurueckgestellt",
                    "unqualifiziert": "unqualifiziert", "verloren": "verloren"}
ANGEBOT_OFFEN = ("Entwurf", "Versand vorbereitet", "Versendet", "Versendet (extern)",
                 "Individuell")
KONTAKT_TYPEN = ("anruf", "mail_aus", "mail_ein", "whatsapp")
KONTAKT_ART = {"anruf": "Anruf", "mail_aus": "E-Mail ausgehend",
               "mail_ein": "E-Mail eingehend", "whatsapp": "WhatsApp"}
# Farbe der Versuchs-Punkte nach Ergebnis (CSS-Klassen in lead_v2.css)
ERGEBNIS_KLASSEN = {
    "erreicht": "ok", "rueckruf_gewuenscht": "blau", "nicht_erreicht": "grau",
    "besetzt": "grau", "mailbox": "warn", "falsche_nummer": "warn",
    "kein_interesse": "rot",
}
# Automatik-Palette für Kanäle ohne Eintrag in kanal_farben (Hash über den Namen)
KANAL_PALETTE = ["#e87ba4", "#2a78d6", "#1baf7a", "#eda100", "#8e44ad",
                 "#eb6834", "#5b6b8a", "#c9a227"]
AVATAR_PALETTE = ["#3f86c6", "#1baf7a", "#8e44ad", "#eb6834", "#c9a227",
                  "#2c6cb0", "#e05c8a", "#5b6b8a", "#a0714f", "#326ea5"]
ARCHIV_TAGE = 30


def spalten_basis(board: str) -> list:
    return SPALTEN_TERMINIERT if board == "terminiert" else SPALTEN


def spalten_fuer(session: Session, benutzer_id: int, board: str) -> list[dict]:
    """Spaltenreihenfolge + Sichtbarkeit des Nutzers (A-14); unbekannte Keys
    fallen weg, neue Spalten hängen sich hinten an. ‚lead' bleibt vorn."""
    basis = spalten_basis(board)
    titel = {k: t for k, t, _ in basis}
    standard = {k: s for k, _, s in basis}
    alle = lead_v2.einstellung_holen(session, benutzer_id, EINSTELLUNG_KEY, {}) or {}
    konfig = alle.get(board) if isinstance(alle, dict) else None
    ergebnis, gesehen = [], set()
    for eintrag in konfig or []:
        try:
            key, sichtbar = eintrag[0], bool(eintrag[1])
        except (TypeError, IndexError, KeyError):
            continue
        if key in titel and key not in gesehen:
            gesehen.add(key)
            ergebnis.append({"key": key, "titel": titel[key],
                             "sichtbar": sichtbar or key in SPALTEN_FEST})
    for key, t, s in basis:
        if key not in gesehen:
            ergebnis.append({"key": key, "titel": t, "sichtbar": s})
    ergebnis.sort(key=lambda sp: 0 if sp["key"] in SPALTEN_FEST else 1)
    return ergebnis


def spalten_speichern(session: Session, benutzer_id: int, board: str, liste) -> list[dict]:
    """liste = [{key, sichtbar}] oder [[key, sichtbar]] in gewünschter Reihenfolge."""
    gueltig = {k for k, _, _ in spalten_basis(board)}
    neu = []
    if not isinstance(liste, (list, tuple)):
        liste = []
    for eintrag in liste:
        if isinstance(eintrag, dict):
            key, sichtbar = eintrag.get("key"), eintrag.get("sichtbar", True)
        else:
            try:
                key, sichtbar = eintrag[0], eintrag[1]
            except (TypeError, IndexError):
                continue
        if key in gueltig and key not in [n[0] for n in neu]:
            neu.append([key, bool(sichtbar) or key in SPALTEN_FEST])
    alle = lead_v2.einstellung_holen(session, benutzer_id, EINSTELLUNG_KEY, {}) or {}
    if not isinstance(alle, dict):
        alle = {}
    alle[board] = neu
    lead_v2.einstellung_setzen(session, benutzer_id, EINSTELLUNG_KEY, alle)
    return spalten_fuer(session, benutzer_id, board)


# --- Farben, Avatare -----------------------------------------------------------------

def _hash_index(text: str, n: int) -> int:
    return int(hashlib.md5((text or "").lower().encode("utf-8")).hexdigest(), 16) % n


def kanal_farben(session: Session) -> dict:
    """Parameter kanal_farben (JSON {kanal: #hex}, Schlüssel klein)."""
    roh = kern.parameter_holen(session, "kanal_farben", "") or ""
    try:
        werte = json.loads(roh) if roh.strip() else {}
    except ValueError:
        werte = {}
    return {str(k).strip().lower(): str(v).strip() for k, v in werte.items()
            if str(v).strip()} if isinstance(werte, dict) else {}


def kanal_farbe(farben: dict, kanal: str) -> str:
    kanal = (kanal or "").strip()
    if not kanal:
        return ""
    return farben.get(kanal.lower()) or KANAL_PALETTE[_hash_index(kanal, len(KANAL_PALETTE))]


def status_label(logik, phase: str) -> tuple[str, str]:
    """(Label, Farbe) aus dem Blatt Status; Fallback Phasenname + Grau."""
    zeile = logik.status_zeile(phase or "")
    if zeile is not None:
        return zeile.label or LEAD_PHASEN_NAMEN.get(phase, phase), zeile.farbe or "#9aa4b2"
    return LEAD_PHASEN_NAMEN.get(phase, phase or "–"), "#9aa4b2"


def initialen(name: str) -> str:
    teile = [t for t in re.split(r"[\s\-]+", (name or "").strip()) if t]
    teile = [t for t in teile if t.rstrip(".")] or teile
    if not teile:
        return "?"
    if len(teile) == 1:
        return teile[0][:2].upper()
    return (teile[0][0] + teile[-1][0]).upper()


def avatar_farbe(benutzer_id) -> str:
    try:
        return AVATAR_PALETTE[int(benutzer_id or 0) % len(AVATAR_PALETTE)]
    except (TypeError, ValueError):
        return AVATAR_PALETTE[0]


# --- Zuordnung Status → Board → Gruppe (H2) ----------------------------------------

def board_gruppe(logik, vorgang: Vorgang, aktiver_vot=None) -> tuple[str, str]:
    """Gruppe eines Vorgangs: Blatt Status entscheidet; ein aktiver
    Vor-Ort-Termin zieht einen Hauptboard-Lead ins Board Terminiert
    (Angebotserstellung), auch wenn die Phase noch nicht nachgezogen ist."""
    board, gruppe = logik.board_fuer(vorgang.lead_phase or "neu")
    if board == "hauptboard" and aktiver_vot is not None \
            and vorgang.lead_phase not in ("zurueckgestellt", "unqualifiziert", "nicht_erreicht"):
        return "terminiert", "angebotserstellung"
    return board, gruppe


def zuordnung_tabelle(logik=None) -> list[dict]:
    """Vollständige Tabelle Phase → Board → Gruppe (für Doku/Tests)."""
    logik = logik or leadmanagement_logik.hole_logik()
    zeilen = []
    for phase in LEAD_PHASEN:
        board, gruppe = logik.board_fuer(phase)
        label, farbe = status_label(logik, phase)
        zeilen.append({"phase": phase, "label": label, "farbe": farbe,
                       "board": board, "gruppe": gruppe})
    return zeilen


# --- Zeilen der Boards -----------------------------------------------------------------

def _telefon_ziffern(text: str) -> str:
    return kern.telefon_normalisieren(text or "")


def versuche_punkte(anrufe: list, maximum: int, benutzer_map: dict) -> list[dict]:
    """Punkte je Versuch (Farbe nach Ergebnis, Tooltip Datum/Uhrzeit/Ergebnis/
    Benutzer); mehr Versuche als Maximum → die letzten `maximum` Punkte."""
    maximum = max(1, maximum)
    letzte = anrufe[-maximum:] if len(anrufe) > maximum else anrufe
    punkte = []
    for a in letzte:
        wer = benutzer_map.get(a.benutzer_id)
        punkte.append({
            "klasse": ERGEBNIS_KLASSEN.get(a.ergebnis or "", "grau"),
            "titel": (a.zeitpunkt.strftime("%d.%m.%Y %H:%M") + " · "
                      + ANRUF_ERGEBNIS_NAMEN.get(a.ergebnis or "", a.ergebnis or "Anruf")
                      + (f" · {wer.name}" if wer else "")),
        })
    while len(punkte) < maximum:
        punkte.append({"klasse": "", "titel": "noch kein Versuch"})
    return punkte


def filter_aus_query(q) -> dict:
    def _int(name):
        wert = str(q.get(name, "") or "")
        return int(wert) if wert.isdigit() else None
    return {
        "q": (q.get("q", "") or "").strip(),
        "status": q.get("status", "") or "",
        "kanal": q.get("kanal", "") or "",
        "sparte": (q.get("sparte", "") or "").upper(),
        "ad_id": _int("ad_id"), "leadmanager_id": _int("leadmanager_id"),
        "gruppe": q.get("gruppe", "") or "",
        "archiv": q.get("archiv", "") == "1",
        "meine": q.get("meine", "") == "1",
    }


def _suche_passt(z: dict, suche: str) -> bool:
    if not suche:
        return True
    k = z["kunde"]
    text = " ".join((k.vorname or "", k.nachname or "", k.firma or "", k.ort or "",
                     k.plz or "", k.email or "", k.telefon or "")).lower()
    if suche.lower() in text:
        return True
    ziffern = re.sub(r"\D", "", suche)
    if len(ziffern) >= 4 and k.telefon:
        # Rufnummer in jeder Schreibweise: Teilnummer über die reinen Ziffern
        # („770 501“ trifft „0203 770501“), ganze Nummer zusätzlich E.164-gleich
        return (ziffern in re.sub(r"\D", "", k.telefon)
                or _telefon_ziffern(suche) == _telefon_ziffern(k.telefon))
    return False


def board_zeilen(session: Session, benutzer, board: str, f: dict | None = None) -> dict:
    """Gruppen mit Zeilen für ein Board (Tabelle A3). Handelsvertreter sehen
    nur Vorgänge mit ad_id = eigene ID (F16)."""
    f = f or {}
    if board not in BOARDS:
        board = "hauptboard"
    logik = leadmanagement_logik.hole_logik()
    jetzt = datetime.now()
    hv = lead_v2.ist_handelsvertreter(session, benutzer)
    abfrage = session.query(Vorgang).filter(Vorgang.lead_phase.isnot(None))
    if hv:
        abfrage = abfrage.filter(Vorgang.ad_id == benutzer.id)
    elif f.get("meine") and benutzer is not None:
        abfrage = abfrage.filter(Vorgang.leadmanager_id == benutzer.id)
    if f.get("ad_id"):
        abfrage = abfrage.filter(Vorgang.ad_id == f["ad_id"])
    if f.get("leadmanager_id"):
        abfrage = abfrage.filter(Vorgang.leadmanager_id == f["leadmanager_id"])
    if f.get("ids"):
        # Nachladen einzelner Zeilen (Inline-Bearbeitung): nur diese Vorgänge
        abfrage = abfrage.filter(Vorgang.id.in_(list(f["ids"])))
    vorgaenge = abfrage.all()
    ids = {v.id for v in vorgaenge} or {0}
    kunden_ids = {v.kunde_id for v in vorgaenge} or {0}
    kunden = {k.id: k for k in session.query(Kunde).filter(Kunde.id.in_(kunden_ids))}
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    quellen = {q.id: q for q in session.query(LeadQuelle)}
    mehrfach: dict[int, int] = {}
    for (kid,) in session.query(Vorgang.kunde_id).filter(Vorgang.kunde_id.in_(kunden_ids)):
        mehrfach[kid] = mehrfach.get(kid, 0) + 1
    termine: dict[int, list] = {}
    for t in (session.query(VotTermin).filter(VotTermin.vorgang_id.in_(ids))
              .order_by(VotTermin.beginn)):
        termine.setdefault(t.vorgang_id, []).append(t)
    anrufe: dict[int, list] = {}
    kontakte: dict[int, LeadAktivitaet] = {}
    letzte_akt: dict[int, datetime] = {}
    letzte_status: dict[int, LeadAktivitaet] = {}
    for a in (session.query(LeadAktivitaet).filter(LeadAktivitaet.vorgang_id.in_(ids))
              .order_by(LeadAktivitaet.zeitpunkt)):
        letzte_akt[a.vorgang_id] = a.zeitpunkt
        if a.typ == "anruf":
            anrufe.setdefault(a.vorgang_id, []).append(a)
        if a.typ in KONTAKT_TYPEN:
            kontakte[a.vorgang_id] = a
        if a.typ == "status":
            letzte_status[a.vorgang_id] = a
    angebote: dict[int, list] = {}
    erfassungen: dict[int, list] = {}
    if board == "terminiert":
        for a in (session.query(Angebot).filter(Angebot.vorgang_id.in_(ids),
                                                Angebot.archiviert.is_(False))
                  .order_by(Angebot.datum.desc())):
            angebote.setdefault(a.vorgang_id, []).append(a)
        for e in (session.query(Erfassung).filter(Erfassung.vorgang_id.in_(ids),
                                                  Erfassung.archiviert.is_(False))):
            erfassungen.setdefault(e.vorgang_id, []).append(e)
    farben = kanal_farben(session)
    maximum = kern.versuche_max(session)
    grenze = jetzt - timedelta(days=ARCHIV_TAGE)
    suche = f.get("q", "")

    gruppen = {g: [] for g in BOARDS[board]["gruppen"]}
    for v in vorgaenge:
        kunde = kunden.get(v.kunde_id)
        if kunde is None:
            continue
        eigene = termine.get(v.id, [])
        aktiver_vot = next((t for t in eigene if (t.typ or "vot") == "vot"
                            and t.status in ("geplant", "bestaetigt")), None)
        vorab = next((t for t in eigene if (t.typ or "vot") in ("telefon", "online")
                      and t.status in ("geplant", "bestaetigt", "vorgemerkt")), None)
        ziel_board, gruppe = board_gruppe(logik, v, aktiver_vot)
        if ziel_board != board or gruppe not in gruppen:
            continue
        if f.get("gruppe") and gruppe != f["gruppe"]:
            continue
        if f.get("status") and v.lead_phase != f["status"]:
            continue
        if f.get("kanal") and (kunde.vertriebskanal or "").lower() != f["kanal"].lower():
            continue
        sparten = [s.strip() for s in (kunde.interesse or "").split(",") if s.strip()]
        if f.get("sparte") and f["sparte"] not in sparten:
            continue
        if v.lead_phase in ("gewonnen", "verloren") and not f.get("archiv"):
            stand = letzte_akt.get(v.id) or v.eingang_am or v.angelegt_am
            if stand is not None and stand < grenze:
                continue
        liste = anrufe.get(v.id, [])
        label, farbe = status_label(logik, v.lead_phase)
        naechster = next((t for t in eigene if t.status in ("geplant", "bestaetigt", "vorgemerkt")
                          and (t.beginn is None or t.beginn >= jetzt - timedelta(hours=3))), None) \
            or aktiver_vot or vorab
        letzter_status = letzte_status.get(v.id)
        zurueck = bool(letzter_status is not None and gruppe == "neu"
                       and (letzter_status.text or "").startswith("Wiedervorlage fällig")
                       and (not liste or liste[-1].zeitpunkt < letzter_status.zeitpunkt))
        hv_grund = lead_v2.hv_ausgeschlossen(session, v, kunde)
        kontakt = kontakte.get(v.id)
        zeile = {
            "vorgang": v, "kunde": kunde, "gruppe": gruppe, "board": board,
            "status_label": label, "status_farbe": farbe,
            "kanal": kunde.vertriebskanal or "", "kanal_farbe": kanal_farbe(farben, kunde.vertriebskanal),
            "sparten": sparten,
            "versuche": len(liste), "punkte": versuche_punkte(liste, maximum, benutzer_map),
            "gesperrt": kern.versuche_gesperrt(session, v),
            "letzter": kontakt,
            "letzter_art": (KONTAKT_ART.get(kontakt.typ, kontakt.typ)
                            + (" · " + ANRUF_ERGEBNIS_NAMEN.get(kontakt.ergebnis, kontakt.ergebnis)
                               if kontakt.typ == "anruf" and kontakt.ergebnis else "")) if kontakt else "",
            "letzter_benutzer": benutzer_map.get(kontakt.benutzer_id) if kontakt else None,
            "eingang": v.eingang_am or v.angelegt_am,
            "ad": benutzer_map.get(v.ad_id), "leadmanager": benutzer_map.get(v.leadmanager_id),
            "hv_grund": hv_grund,
            "termin": naechster, "termin_ad": benutzer_map.get(naechster.ad_id) if naechster else None,
            "telefongespraech": vorab is not None and gruppe == "neu",
            "vorab": vorab,
            "vor_termin": (v.lead_phase == "verloren"
                           and not any((t.typ or "vot") == "vot" for t in eigene)),
            "wiedervorlage": (v.zurueckgestellt_bis if v.lead_phase == "zurueckgestellt"
                              else v.naechste_aktion_am or v.wiedervorlage_am),
            "weitere": max(0, mehrfach.get(v.kunde_id, 1) - 1),
            "monday": v.eingang_art == "monday",
            "quelle": quellen.get(v.quelle_id),
            "zurueck": zurueck,
            "angebote": angebote.get(v.id, []),
            "erfassungen": erfassungen.get(v.id, []),
            "sparten_status": {s: ("erfasst" if any(e.sparte == s for e in erfassungen.get(v.id, []))
                                   else "offen") for s in sparten},
            "offene_angebote": [a for a in angebote.get(v.id, []) if a.status in ANGEBOT_OFFEN],
        }
        if not _suche_passt(zeile, suche):
            continue
        gruppen[gruppe].append(zeile)
    ergebnis = []
    for key in BOARDS[board]["gruppen"]:
        zeilen = gruppen[key]
        zeilen.sort(key=lambda z: z["eingang"] or jetzt, reverse=True)
        ergebnis.append({"key": key, "titel": GRUPPEN_NAMEN[key],
                         "erkl": GRUPPEN_ERKLAERUNG.get(key, ""), "zeilen": zeilen,
                         "eingeklappt": key in GRUPPEN_EINGEKLAPPT and not f.get("gruppe")})
    return {"board": board, "gruppen": ergebnis, "jetzt": jetzt, "hv": hv,
            "anzahl": sum(len(g["zeilen"]) for g in ergebnis), "versuche_max": maximum}


def zeile_fuer(session: Session, benutzer, vorgang: Vorgang) -> dict | None:
    """Eine einzelne Zeile (nach Inline-Änderung) – sucht den Vorgang in
    beiden Boards; None, wenn er in keiner Gruppe mehr sichtbar ist."""
    for board in BOARDS:
        daten = board_zeilen(session, benutzer, board, {"archiv": True, "ids": [vorgang.id]})
        for g in daten["gruppen"]:
            for z in g["zeilen"]:
                if z["vorgang"].id == vorgang.id:
                    return z
    return None


def auswahl_listen(session: Session) -> dict:
    """Dropdown-Inhalte: Außendienst (inkl. Handelsvertreter, markiert),
    Innendienst (Leadmanager), Status (manuell setzbar), Kanäle."""
    hv_ids = {b.id for b in lead_v2.handelsvertreter_liste(session)}
    ad = [b for b in session.query(Benutzer)
          .filter(Benutzer.aktiv.is_(True), Benutzer.rolle == "aussendienst")
          .order_by(Benutzer.name)]
    for b in session.query(Benutzer).filter(Benutzer.id.in_(hv_ids or {0})):
        if b not in ad:
            ad.append(b)
    logik = leadmanagement_logik.hole_logik()
    status = []
    for phase in LEAD_PHASEN:
        label, farbe = status_label(logik, phase)
        status.append({"key": phase, "label": label, "farbe": farbe,
                       "setzbar": phase not in PHASEN_ABGELEITET,
                       "grund": PHASEN_MIT_GRUND.get(phase, "")})
    return {
        "ad_wahl": [{"id": b.id, "name": b.name, "hv": b.id in hv_ids} for b in ad],
        "lm_wahl": [{"id": b.id, "name": b.name} for b in kern.leadmanager_benutzer(session)],
        "status_wahl": status,
        "kanaele": kern.kanal_werte(session),
        "gruende": {phase: [{"grund": g.grund, "freitext": g.freitext_pflicht}
                            for g in logik.gruende_der_phase(phase)]
                    for phase in ("zurueckgestellt", "unqualifiziert", "verloren")},
    }


# --- Statuswechsel, Inline-Bearbeitung --------------------------------------------------

def _grund_pruefen(logik, phase: str, grund: str, text: str) -> str:
    passend = next((g for g in logik.gruende_der_phase(phase) if g.grund == grund), None)
    if passend is None:
        return "Bitte einen Grund aus der Liste wählen."
    if passend.freitext_pflicht and not text:
        return f"Beim Grund „{grund}“ ist der Freitext Pflicht."
    return ""


def _datum(wert) -> datetime | None:
    if isinstance(wert, datetime):
        return wert
    if isinstance(wert, date):
        return datetime(wert.year, wert.month, wert.day)
    roh = str(wert or "").strip()
    for muster in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(roh, muster)
        except ValueError:
            continue
    return None


def angebote_ablehnen(session: Session, vorgang: Vorgang, grund: str, text: str = "",
                      benutzer=None) -> int:
    """H5: Verloren setzt alle offenen Angebote des Vorgangs auf Abgelehnt mit
    dem Grund (Felder angebote.ablehnungsgrund/_text, Notiz, Erfassung erledigt,
    monday-Wert); Rückgabe Anzahl."""
    anzahl = 0
    for angebot in (session.query(Angebot)
                    .filter(Angebot.vorgang_id == vorgang.id, Angebot.archiviert.is_(False),
                            Angebot.status.in_(ANGEBOT_OFFEN))):
        alter_status = angebot.status
        angebot.ablehnungsgrund = (grund or "Lead verloren")[:100]
        angebot.ablehnungsgrund_text = (text or "")[:500]
        angebot_status_setzen(angebot, "Abgelehnt")
        session.add(AngebotsNotiz(
            angebot_id=angebot.id, benutzer_name=benutzer.name if benutzer else "System",
            text="Abgelehnt – Grund: " + angebot.ablehnungsgrund
                 + (f" ({angebot.ablehnungsgrund_text})" if angebot.ablehnungsgrund_text else "")
                 + " · Lead verloren (Board Terminiert)"))
        erfassung = session.query(Erfassung).filter(Erfassung.angebot_id == angebot.id).first()
        if erfassung is not None and erfassung.status != "Erledigt (extern)":
            erfassung.status = "Erledigt"
        if alter_status in ("Versendet", "Versendet (extern)"):
            try:
                from app import monday_rueckspielung
                monday_rueckspielung.wert_aktualisieren(session, angebot, "Ablehnung")
            except Exception:
                pass
        anzahl += 1
    session.flush()
    return anzahl


def lead_verloren_mit_angeboten(session: Session, vorgang: Vorgang, grund: str,
                                text: str = "", benutzer=None) -> int:
    """Bestandsfunktion kern.lead_verloren (Phase, Termine stornieren, Mails,
    Aktivität) + Angebote Abgelehnt (H5). Liefert Anzahl abgelehnter Angebote.
    Idempotent gegenüber dem vorgeschlagenen hook_edit in kern.lead_verloren
    (zählt vorher, angebote_ablehnen findet danach nichts Offenes mehr)."""
    offen = (session.query(Angebot)
             .filter(Angebot.vorgang_id == vorgang.id, Angebot.archiviert.is_(False),
                     Angebot.status.in_(ANGEBOT_OFFEN)).count())
    kern.lead_verloren(session, vorgang, grund, text, benutzer=benutzer)
    angebote_ablehnen(session, vorgang, grund, text, benutzer)
    vorgang.lead_phase = "verloren"      # bleibt auch nach Ableitung konsistent
    session.flush()
    return offen


def status_setzen(session: Session, vorgang: Vorgang, ziel: str, benutzer=None,
                  grund: str = "", grund_text: str = "", bis=None,
                  quelle: str = "") -> tuple[bool, str]:
    """Manueller Statuswechsel (Tabelle/Sammelaktion) mit den Pflichten der
    Bestandsdialoge: Zurückgestellt Datum+Grund, Unqualifiziert Grund,
    Verloren Grund (Blatt Gruende, Phase verloren) + Angebote Abgelehnt.
    Abgeleitete Phasen sind nicht setzbar. Schreibt je Lead eine Aktivität."""
    logik = leadmanagement_logik.hole_logik()
    ziel = (ziel or "").strip()
    grund = (grund or "").strip()
    grund_text = (grund_text or "").strip()
    praefix = f"{quelle} – " if quelle else ""
    if ziel not in LEAD_PHASEN:
        return False, "Unbekannter Status."
    if ziel in PHASEN_ABGELEITET:
        return False, (f"„{LEAD_PHASEN_NAMEN[ziel]}“ wird aus Termin/Erfassung/Angebot "
                       "abgeleitet und nicht manuell gesetzt.")
    alt = vorgang.lead_phase or "neu"
    if ziel == alt and ziel != "zurueckgestellt":
        return False, f"Status ist bereits „{LEAD_PHASEN_NAMEN[ziel]}“."
    alt_name = LEAD_PHASEN_NAMEN.get(alt, alt)
    if ziel == "zurueckgestellt":
        datum = _datum(bis)
        if datum is None and grund == "Kunde meldet sich selbst":
            try:
                tage = int(kern.parameter_holen(session, "wv_meldet_sich_tage", "14"))
            except ValueError:
                tage = 14
            datum = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) \
                + timedelta(days=tage)
        if datum is None:
            return False, "Zurückstellen: Datum ist Pflicht."
        fehler = _grund_pruefen(logik, "zurueckgestellt", grund, grund_text)
        if fehler:
            return False, fehler
        vorgang.lead_phase = "zurueckgestellt"
        vorgang.zurueckgestellt_bis = datum
        vorgang.zurueckgestellt_grund = grund + (f" – {grund_text}" if grund_text else "")
        vorgang.naechste_aktion_am = None
        kern.aktivitaet(session, vorgang.id, "status",
                        f"{praefix}Zurückgestellt bis {datum.strftime('%d.%m.%Y')}: "
                        f"{vorgang.zurueckgestellt_grund}", benutzer=benutzer)
        session.flush()
        return True, f"Zurückgestellt bis {datum.strftime('%d.%m.%Y')} ({grund})."
    if ziel == "unqualifiziert":
        fehler = _grund_pruefen(logik, "unqualifiziert", grund, grund_text)
        if fehler:
            return False, fehler
        vorgang.lead_phase = "unqualifiziert"
        vorgang.unqualifiziert_grund = grund
        vorgang.unqualifiziert_text = grund_text
        vorgang.naechste_aktion_am = None
        vorgang.zurueckgestellt_bis = None
        kern.aktivitaet(session, vorgang.id, "status",
                        f"{praefix}Unqualifiziert: {grund}"
                        + (f" – {grund_text}" if grund_text else ""), benutzer=benutzer)
        session.flush()
        return True, f"Unqualifiziert ({grund})."
    if ziel == "verloren":
        fehler = _grund_pruefen(logik, "verloren", grund, grund_text)
        if fehler:
            return False, fehler
        anzahl = lead_verloren_mit_angeboten(session, vorgang, grund, grund_text, benutzer)
        if quelle:
            kern.aktivitaet(session, vorgang.id, "status",
                            f"{praefix}Status Verloren gesetzt ({grund})", benutzer=benutzer)
        return True, (f"Verloren ({grund})"
                      + (f" – {anzahl} Angebot(e) auf Abgelehnt gesetzt" if anzahl else "") + ".")
    if ziel == "nicht_erreicht":
        vorgang.lead_phase = "nicht_erreicht"
        vorgang.zurueckgestellt_bis = None
        if vorgang.naechste_aktion_am is None:
            vorgang.naechste_aktion_am = datetime.now() + timedelta(days=30)
        kern.aktivitaet(session, vorgang.id, "status",
                        f"{praefix}Status: {alt_name} → Nicht erreicht"
                        + (f" ({grund_text})" if grund_text else ""), benutzer=benutzer)
        session.flush()
        return True, "Nicht erreicht gesetzt (Wiedervorlage +30 Tage)."
    # neu | in_kontaktierung | qualifiziert: aus Seitenzuständen = Reaktivieren
    vorgang.lead_phase = ziel
    vorgang.zurueckgestellt_bis = None
    vorgang.unqualifiziert_grund = None
    vorgang.unqualifiziert_text = None
    if alt in ("zurueckgestellt", "nicht_erreicht", "unqualifiziert", "verloren"):
        vorgang.naechste_aktion_am = datetime.now()
    kern.aktivitaet(session, vorgang.id, "status",
                    f"{praefix}Status: {alt_name} → {LEAD_PHASEN_NAMEN[ziel]}"
                    + (f" ({grund_text})" if grund_text else ""), benutzer=benutzer)
    session.flush()
    return True, f"Status {LEAD_PHASEN_NAMEN[ziel]}."


def zeile_aendern(session: Session, vorgang: Vorgang, feld: str, wert, benutzer=None,
                  daten: dict | None = None) -> tuple[bool, str]:
    """Inline-Bearbeitung der Tabelle: status, notiz, ad_id, leadmanager_id,
    wiedervorlage. Zuweisungen immer über lead_v2.ad_zuweisen /
    leadmanager_zuweisen (Ausschlussliste, Aktivität, Glocke)."""
    daten = daten or {}
    feld = (feld or "").strip()
    if feld == "notiz":
        kunde = session.get(Kunde, vorgang.kunde_id)
        if kunde is None:
            return False, "Kunde fehlt."
        kunde.notizen = str(wert or "").strip()[:4000]
        session.flush()
        return True, "Notiz gespeichert."
    if feld in ("ad_id", "leadmanager_id"):
        # Dropdown-Wert: leer = Zuweisung entfernen, sonst Benutzer-ID (Zahl)
        roh = str(wert or "").strip()
        if roh and not roh.isdigit():
            return False, "Ungültige Benutzer-Auswahl."
        ziel_id = int(roh) if roh else None
        if feld == "ad_id":
            # v23 (Phase 109): über lead_handelsvertreter.zuweisen – Sonderregel
            # „Deals - Rene“ sperrt, monday-Abgleich (leads.benutzer_id + benutzer_manuell)
            from app import lead_handelsvertreter
            meldung = lead_handelsvertreter.zuweisen(
                session, vorgang, ziel_id, benutzer=benutzer,
                erzwingen=bool(daten.get("erzwingen"))
                and benutzer is not None
                and benutzer.rolle in ("admin", "innendienst"))
            ok = not meldung.startswith(("Nicht möglich", "Außendienstler nicht"))
            return ok, meldung
        meldung = lead_v2.leadmanager_zuweisen(session, vorgang, ziel_id, benutzer=benutzer)
        return not meldung.startswith("Benutzer nicht"), meldung
    if feld == "wiedervorlage":
        roh = str(wert or "").strip()
        if not roh:
            vorgang.naechste_aktion_am = None
            if vorgang.lead_phase == "zurueckgestellt":
                return False, "Zurückgestellte Leads brauchen ein Wiedervorlage-Datum."
            kern.aktivitaet(session, vorgang.id, "status", "Wiedervorlage entfernt",
                            benutzer=benutzer)
            session.flush()
            return True, "Wiedervorlage entfernt."
        datum = _datum(roh)
        if datum is None:
            return False, "Datum nicht lesbar."
        if datum.hour == 0 and datum.minute == 0 and "T" not in roh and " " not in roh:
            datum = datum.replace(hour=9)
        if vorgang.lead_phase == "zurueckgestellt":
            vorgang.zurueckgestellt_bis = datum
        else:
            vorgang.naechste_aktion_am = datum
        kern.aktivitaet(session, vorgang.id, "status",
                        f"Wiedervorlage {datum.strftime('%d.%m.%Y %H:%M')}",
                        benutzer=benutzer, naechste_aktion_am=datum)
        session.flush()
        return True, f"Wiedervorlage {datum.strftime('%d.%m.%Y %H:%M')}."
    if feld == "status":
        return status_setzen(session, vorgang, str(wert or ""), benutzer=benutzer,
                             grund=daten.get("grund", ""), grund_text=daten.get("grund_text", ""),
                             bis=daten.get("bis"))
    return False, f"Feld „{feld}“ ist nicht bearbeitbar."


# --- Sammelaktionen (H3, generisch) ------------------------------------------------------

def _sammel_status(session: Session, vorgaenge: list, params: dict, benutzer) -> tuple[int, list]:
    ziel = params.get("status", "")
    ok, fehler = 0, []
    for v in vorgaenge:
        erfolg, meldung = status_setzen(session, v, ziel, benutzer=benutzer,
                                        grund=params.get("grund", ""),
                                        grund_text=params.get("grund_text", ""),
                                        bis=params.get("bis"), quelle="Sammelaktion")
        if erfolg:
            ok += 1
        else:
            kunde = session.get(Kunde, v.kunde_id)
            fehler.append(f"{kunde.anzeige_name if kunde else v.id}: {meldung}")
    return ok, fehler


# Registry: board → [(key, Titel, Handler(session, vorgaenge, params, benutzer)
# → (anzahl_ok, fehlerliste))]. Weitere Aktionen (Phase 111: Info-Veranstaltung)
# registrieren sich über sammelaktion_registrieren().
SAMMELAKTIONEN: dict[str, list] = {
    "hauptboard": [("status", "Status ändern", _sammel_status)],
    "terminiert": [],
}


def sammelaktion_registrieren(board: str, key: str, titel: str, handler) -> None:
    liste = SAMMELAKTIONEN.setdefault(board, [])
    liste[:] = [e for e in liste if e[0] != key]
    liste.append((key, titel, handler))


def sammelaktionen_fuer(board: str) -> list[dict]:
    return [{"key": k, "titel": t} for k, t, _ in SAMMELAKTIONEN.get(board, [])]


def sammelaktion_ausfuehren(session: Session, benutzer, board: str, aktion: str,
                            ids: list, params: dict | None = None) -> tuple[bool, str]:
    """Führt eine registrierte Aktion je Lead aus (Handler schreibt je Lead
    eine Aktivität); Meldung mit Zählern. Handelsvertreter/AD: nicht erlaubt."""
    params = params or {}
    if benutzer is None or benutzer.rolle == "aussendienst":
        return False, "Sammelaktionen sind für den Außendienst nicht freigegeben."
    eintrag = next((e for e in SAMMELAKTIONEN.get(board, []) if e[0] == aktion), None)
    if eintrag is None:
        return False, f"Sammelaktion „{aktion}“ gibt es auf diesem Board nicht."
    sauber = []
    for wert in ids or []:
        try:
            sauber.append(int(wert))
        except (TypeError, ValueError):
            continue
    if not sauber:
        return False, "Keine Leads markiert."
    vorgaenge = [v for v in session.query(Vorgang).filter(Vorgang.id.in_(sauber))
                 if lead_v2.zugriff_erlaubt(session, benutzer, v)]
    if not vorgaenge:
        return False, "Keine zugänglichen Leads markiert."
    ok, fehler = eintrag[2](session, vorgaenge, params, benutzer)
    session.flush()
    meldung = f"{eintrag[1]}: {ok} von {len(vorgaenge)} Leads geändert."
    if fehler:
        meldung += f" {len(fehler)} übersprungen: " + "; ".join(fehler[:5])
        if len(fehler) > 5:
            meldung += " …"
    return ok > 0, meldung


# --- Reiter Kontaktiert (H7) + Rufnummernsuche (D3) ---------------------------------------

def telefon_treffer(session: Session, nummer: str, benutzer=None) -> list[dict]:
    """Alle Kunden/Vorgänge und monday-Leads mit dieser Nummer, Schreibweise
    egal (E.164 wie in der Duplikatprüfung). Treffer verlinken auf die Kartei."""
    gesucht = kern.telefon_normalisieren(nummer)
    if not gesucht or len(re.sub(r"\D", "", gesucht)) < 5:
        return []
    hv = lead_v2.ist_handelsvertreter(session, benutzer)
    treffer = []
    kunden = [k for k in session.query(Kunde).filter(Kunde.telefon != "")
              if kern.telefon_normalisieren(k.telefon) == gesucht]
    for kunde in kunden:
        vorgaenge = (session.query(Vorgang).filter(Vorgang.kunde_id == kunde.id)
                     .order_by(Vorgang.angelegt_am.desc()).all())
        if hv:
            vorgaenge = [v for v in vorgaenge if v.ad_id == benutzer.id]
            if not vorgaenge:
                continue
        v = vorgaenge[0] if vorgaenge else None
        treffer.append({
            "art": "kunde", "kunde": kunde, "vorgang": v, "lead": None,
            "name": kunde.anzeige_name, "ort": kunde.ort or "", "telefon": kunde.telefon,
            "phase": v.lead_phase if v else None,
            "link": f"/lead-management/lead/{v.id}" if v else f"/kunden/{kunde.id}",
            "anzahl_vorgaenge": len(vorgaenge),
        })
    kunden_ids = {k.id for k in kunden}
    if not hv:
        for lead in [lt for lt in session.query(Lead).filter(Lead.telefon != "")
                     if kern.telefon_normalisieren(lt.telefon) == gesucht]:
            if lead.kunde_id in kunden_ids:
                continue
            v = session.query(Vorgang).filter(Vorgang.lead_id == lead.id).first()
            treffer.append({
                "art": "monday", "kunde": None, "vorgang": v, "lead": lead,
                "name": lead.anzeige_name, "ort": lead.ort or "", "telefon": lead.telefon,
                "phase": v.lead_phase if v else None,
                "link": f"/lead-management/lead/{v.id}" if v else "/leads",
                "anzahl_vorgaenge": 1 if v else 0,
            })
    return treffer


def kontaktiert_daten(session: Session, benutzer, q: str = "", telefon: str = "",
                      seite: int = 1, je_seite: int = 100) -> dict:
    """Alle Kontaktversuche (lead_aktivitaeten typ anruf) mit Datum, Uhrzeit,
    Ergebnis, Benutzer, Lead – neueste zuerst; Suche Name/Nummer/Benutzer/
    Ergebnis; Rufnummernsuche normalisiert gegen kunden + leads."""
    q = (q or "").strip()
    telefon = (telefon or "").strip()
    hv = lead_v2.ist_handelsvertreter(session, benutzer)
    # Nummer im Suchfeld erkennt sich selbst
    if not telefon and q and len(re.sub(r"\D", "", q)) >= 5 and not re.search(r"[A-Za-zÄÖÜäöü]", q):
        telefon = q
    treffer = telefon_treffer(session, telefon, benutzer) if telefon else []
    abfrage = (session.query(LeadAktivitaet).filter(LeadAktivitaet.typ == "anruf")
               .order_by(LeadAktivitaet.zeitpunkt.desc()))
    if hv:
        eigene = {v.id for v in session.query(Vorgang.id).filter(Vorgang.ad_id == benutzer.id)}
        abfrage = abfrage.filter(LeadAktivitaet.vorgang_id.in_(eigene or {0}))
    if telefon:
        vorgang_ids = {t["vorgang"].id for t in treffer if t["vorgang"] is not None}
        abfrage = abfrage.filter(LeadAktivitaet.vorgang_id.in_(vorgang_ids or {0}))
    aktivitaeten = abfrage.limit(3000).all()
    vorgaenge = {v.id: v for v in session.query(Vorgang)
                 .filter(Vorgang.id.in_({a.vorgang_id for a in aktivitaeten} or {0}))}
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({v.kunde_id for v in vorgaenge.values()} or {0}))}
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    suche = q.lower() if (q and not telefon) else ""
    zeilen = []
    for a in aktivitaeten:
        v = vorgaenge.get(a.vorgang_id)
        kunde = kunden.get(v.kunde_id) if v else None
        if kunde is None:
            continue
        wer = benutzer_map.get(a.benutzer_id)
        ergebnis_name = ANRUF_ERGEBNIS_NAMEN.get(a.ergebnis or "", a.ergebnis or "")
        if suche:
            text = " ".join((kunde.vorname or "", kunde.nachname or "", kunde.firma or "",
                             kunde.ort or "", kunde.telefon or "", ergebnis_name,
                             wer.name if wer else "", a.text or "")).lower()
            if suche not in text:
                continue
        zeilen.append({"aktivitaet": a, "vorgang": v, "kunde": kunde, "benutzer": wer,
                       "ergebnis": ergebnis_name,
                       "ergebnis_klasse": ERGEBNIS_KLASSEN.get(a.ergebnis or "", "grau"),
                       "notiz": re.sub(r"^Anruf: [^–]*–\s*", "", a.text or "")
                       if (a.text or "").startswith("Anruf:") and "–" in (a.text or "") else
                       ("" if (a.text or "").startswith("Anruf:") else (a.text or ""))})
    gesamt = len(zeilen)
    seiten = max(1, (gesamt + je_seite - 1) // je_seite)
    seite = min(max(1, int(seite or 1)), seiten)
    start = (seite - 1) * je_seite
    return {"zeilen": zeilen[start:start + je_seite], "gesamt": gesamt, "seite": seite,
            "seiten": seiten, "q": q, "telefon": telefon, "treffer": treffer,
            "telefon_norm": kern.telefon_normalisieren(telefon) if telefon else "", "hv": hv}
