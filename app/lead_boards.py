# Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 105): Boards als Tabelle nach
# monday-Vorbild (A3/A4), Status → Board → Gruppe (H2, Blatt Status),
# Hauptboard (H4) und Board Deals (H5, bis v24 „Terminiert“), generische
# Sammelaktionen (H3), Reiter Kontaktiert mit Rufnummernsuche E.164 (H7/D3),
# Spaltenkonfiguration je Nutzer (A-14). Die Lead-Phase bleibt die einzige
# Quelle der Wahrheit – die Gruppe ist eine Sicht darauf (logik.board_fuer)
# plus Terminprüfung.
# v25 (PLAN_LEAD_V3 Phase 118): Board-Anzeigenamen aus logik.board_label
# (Hauptboard / Deals), Phasen-Labels nur aus dem Blatt Status (beide Kontakt-
# Phasen „Kontaktiert“), Spaltenkonfiguration je Nutzer mit Umbenennen,
# gemerkter Sortierung, Aus-/Einblenden und Reihenfolge (Struktur
# {"<board>": {"spalten": [{key, sichtbar, name}], "sort": {key, richtung}}},
# die v23-Liste [[key, sichtbar]] wird weiter gelesen), Standard ohne Anrede/
# Vorname/Nachname mit fester Spalte „Kundenname“, Spalte Score nur bei
# lead_v2.score_aktiv.
# v29 (PLAN_LEAD_V4 Phasen 140–142): Spaltenbreite je Nutzer (Eintrag `breite`
# in boards_spalten, 60–600 px, Standard = leer; Ziehgriff im Spaltenkopf,
# lm_boards.js), Rang 0 für Leads mit Mail-Fehler / ungültiger E-Mail (Vertrag
# mit Agent L2: vorgang.mail_fehler, vorgang.email_status – Zeile ganz oben,
# rote Labels in der Notiz-Spalte), Sammelaktion „An Handelsvertreter
# verschieben“ (Ziele aus hv_gruppe_rene/hv_gruppe_simon, Ausschluss F14).
# v31 (PLAN_LEAD_V5 Phasen 153/154/156/157/158): Spalte/Badge/Filter/Sortierung
# „Großkunde“ (kunden.grosskunde, Farbe aus Parameter grosskunde_farbe, CSS-Klasse
# .lm-grosskunde), Archiv als Lead-Sicht (app/lead_archiv.py: Sammelaktionen
# „Archivieren“/„Wiederherstellen“, Filter-Chip „Archiv“, archivierte Leads raus aus
# board_zeilen/kontaktiert), Sammelaktion „Duplizieren“ (vorgang_duplizieren: neuer
# Vorgang am selben Kunden, Phase Neu, kopierte Objekte/Interessen/Kanal/Zuständige,
# kopie_von_id beidseitig verlinkt, keine Duplikatprüfung), Dropdowns aus
# app/lead_dropdowns.py (Leadmanager-Häkchen, AD ohne HV bzw. HV-Gruppe je Zeile),
# Sparten MS/WA/DMS (app/sparten.py), Label „Disqualifiziert“ in Texten,
# Rufnummernsuche mit Endziffern (lead_anrufliste.rufnummer_suchen), Rückruf-/
# Wiedervorlage-Zeiten auf 5 Minuten gerundet (lead_v5.runden_5min).
# v35 (PLAN_LEAD_V6 Phase 186, Agent B): Inline-Bearbeitung erweitert auf Interessen,
# Vertriebskanal, Großkunde, Objektart (neue Spalte, Standard ausgeblendet), Telefon,
# E-Mail und Teilgenommen – Validierung und Aktivität über lead_kartei.feld_speichern
# (dieselbe Funktion wie das Autospeichern der Kartei), Rechte je Zeile über
# lead_v2.bearbeiten_erlaubt (Vertrag R); Pflichtfeld-Verletzungen je Zeile
# (pflicht_zellen, Kanal „?“ = unklar); gespeicherte Filter je Nutzer und Board
# (benutzer_einstellungen Key boards_filter, Freigabe „für alle“ im globalen Eintrag
# boards_filter_geteilt), Standardfilter beim Öffnen (filter_query), Sofortsuche-
# Fragmente (fragment_ziele), Rufnummernsuche in der einen Suchleiste von „Kontaktiert“.

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from html.parser import HTMLParser

from sqlalchemy.orm import Session

from app import lead_archiv, lead_dropdowns, lead_v2, lead_v5
from app import leadmanagement as kern
from app import leadmanagement_logik
from app import sparten as sparten_modul
from app.models import (Angebot, AngebotsNotiz, Benutzer, Erfassung, Kunde, Lead,
                        LeadAktivitaet, LeadQuelle, Vorgang, VorgangObjekt, VotTermin,
                        ANRUF_ERGEBNIS_NAMEN, LEAD_PHASEN, LEAD_PHASEN_NAMEN,
                        angebot_status_setzen)

# --- Boards, Gruppen, Spalten ------------------------------------------------------

# Board-Keys bleiben (Pfade /hauptboard, /terminiert); der Anzeigename kommt
# seit v25 aus logik.board_label (Blatt Status, Spalte board_label) – die Titel
# hier sind nur der statische Rückfall, siehe board_label()/board_info().
BOARDS = {
    "hauptboard": {"titel": "Hauptboard", "untertitel": "Leads ohne Vor-Ort-Termin",
                   "gruppen": ["neu", "pausiert", "disqualifiziert"]},
    "terminiert": {"titel": "Deals", "untertitel": "Leads mit Vor-Ort-Termin – Angebot nachverfolgen",
                   "gruppen": ["angebotserstellung", "angebotsversand", "gewonnen", "verloren"]},
}


def board_label(board: str, logik=None) -> str:
    """v25: Anzeigename eines Boards – IMMER hierüber (Vertrag): Blatt Status
    Spalte board_label, Fallback Hauptboard / Deals."""
    try:
        logik = logik or leadmanagement_logik.hole_logik()
        return logik.board_label(board)
    except Exception:
        return BOARDS.get(board, {}).get("titel", board)


def board_info(board: str) -> dict:
    """BOARDS-Eintrag mit aufgelöstem Anzeigenamen (Titel, Breadcrumb, Kanban)."""
    basis = BOARDS.get(board) or BOARDS["hauptboard"]
    return {**basis, "key": board if board in BOARDS else "hauptboard",
            "titel": board_label(board if board in BOARDS else "hauptboard")}
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
# Kanal. Nutzer ordnen/blenden/benennen je Board um (benutzer_einstellungen).
# v25: die feste erste Spalte heißt „Kundenname“ (Anrede Vorname Nachname,
# Anrede nur wenn gesetzt; Key bleibt „lead“ – gespeicherte Konfigurationen und
# die Makros der Infoabend-/HV-Tabellen kennen ihn); Anrede/Vorname/Nachname
# sind standardmäßig ausgeblendet und einblendbar. Gespeicherte v23-Einträge
# mit sichtbaren Namensspalten bleiben unverändert (der Standard greift nur
# für Spalten ohne Eintrag).
SPALTEN = [
    ("lead", "Kundenname", True), ("anrede", "Anrede", False), ("vorname", "Vorname", False),
    ("nachname", "Nachname", False), ("status", "Status", True),
    ("kanal", "Vertriebskanal", True), ("interessen", "Interessen", True),
    # v31 (PLAN_LEAD_V5 Phase 153): Spalte „Großkunde“ – Standard ausgeblendet, das Badge
    # steht zusätzlich am Kundennamen (Zelle lead); Filter-Chip und Sortierung möglich
    ("grosskunde", "Großkunde", False),
    # v35 (PLAN_LEAD_V6 Phase 186): Objektart als Spalte (Standard ausgeblendet, Inline-Dropdown)
    ("objektart", "Objektart", False),
    ("versuche", "Kontaktversuche", True), ("letzter_kontakt", "Letzter Kontakt", True),
    ("eingang", "Eingangsdatum", True), ("notiz", "Notiz", True),
    ("ad", "Außendienst", True), ("innendienst", "Innendienst", True),
    ("ort", "Ort", True), ("strasse", "Straße", True), ("telefon", "Telefon", True),
    ("email", "E-Mail", True), ("termin", "Vor-Ort-Termin", True),
    ("wiedervorlage", "Wiedervorlage", True),
    # v35 (PLAN_LEAD_V6 Phase 183, Agent T): Spalte „TAIFUN-Übergabe“ (Standard ausgeblendet,
    # sortierbar nach Übergabedatum; Filter-Chip taifun=1, Rang 0 + rotes Label bei Status fehler)
    ("taifun", "TAIFUN-Übergabe", False),
]
# Board Deals: bis v36 zusätzlich die Spalte „Erfassung / Angebot“ (Knöpfe „Erfassung starten“/
# „Angebot öffnen“ + Sparten-Chips). v37 (PLAN_LEAD_V7 Phase 199, Agent L3): die Spalte entfällt –
# derselbe Katalog wie das Hauptboard; gespeicherte Konfigurationen (v25, boards_spalten) mit dem
# Key „angebot“ verlieren ihn beim Lesen ohne Fehler (spalten_fuer wirft unbekannte Keys weg).
# Der Name bleibt als Alias (Alt-Tests, Infoabend/HV lesen spalten_basis).
SPALTEN_TERMINIERT = SPALTEN
# Spalte Score steht nur im Katalog, wenn lead_v2.score_aktiv(session) (v25, Standard aus)
SPALTE_SCORE = ("score", "Score", True)
SPALTEN_FEST = ("lead",)          # immer sichtbar, immer vorn
EINSTELLUNG_KEY = "boards_spalten"
# v35 (PLAN_LEAD_V6 Phase 186): gespeicherte Filter je Nutzer und Board (benutzer_einstellungen);
# „für alle freigeben“ legt eine schreibgeschützte Kopie im globalen Eintrag (benutzer_id 0) ab
FILTER_KEY = "boards_filter"
FILTER_GETEILT_KEY = "boards_filter_geteilt"
FILTER_GLOBAL_BENUTZER = 0
FILTER_NAME_MAX = 60
FILTER_MAX_JE_BOARD = 30
# Query-Parameter, die KEIN Filter sind (Standardfilter greift trotzdem)
FILTER_NEUTRALE_PARAMETER = ("meldung", "fehler", "kopien", "seite", "filter", "fragment", "board")
# Kanal „?“ = Vertriebskanal unklar (Phase 184, Agent K): rotes Pflichtfeld in der Zelle
KANAL_UNKLAR = "?"
# Inline-Felder der Tabelle, die über lead_kartei.feld_speichern laufen (Phase 186):
# Tabellen-Feldname → Kartei-Feldname (Validierung, Aktivität „<Feld>: „alt“ → „neu““)
INLINE_KARTEI_FELDER = {
    "interessen": "interesse", "interesse": "interesse",
    "kanal": "vertriebskanal", "vertriebskanal": "vertriebskanal",
    "grosskunde": "grosskunde", "objektart": "objektart",
    "telefon": "telefon", "email": "email",
}
# Pflichtfeld-Namen (lead_v2.pflichtfelder_offen) → Spalten-Key der roten Markierung
# (Name/Anrede haben keine eigene Zelle – die Kundenname-Zelle bleibt unmarkiert, Alt-Tests
# prüfen dort class="sp-lead" exakt; die Markierung steht als Attribut data-pflicht am <td>)
PFLICHT_ZELLEN = {
    "Vertriebskanal": "kanal", "Vertriebskanal klären": "kanal",   # v35 K: Kanal „?“ (lead_kanaele.UNKLAR_HINWEIS)
    "Außendienst": "ad", "Interesse": "interessen",
    "Telefon": "telefon", "E-Mail": "email", "Objektart": "objektart",
    "PLZ": "ort", "Ort": "ort", "Straße": "strasse",
}
# Boards mit eigener Spaltenkonfiguration je Nutzer (Hauptboard, Deals,
# Infoabend, Handelsvertreter – Infoabend/HV nutzen den Hauptboard-Katalog)
KONFIG_BOARDS = ("hauptboard", "terminiert", "info", "handelsvertreter")
SORT_RICHTUNGEN = ("auf", "ab")

# --- v33 (PLAN_V20 Phase 174, Protokoll Claudia Castro 14.10.2026 Teil A.4): -------------
# Lead-Board-Layout für alle Tabellen des Angebotstools. Je Tabelle ein Board-Key in
# benutzer_einstellungen → boards_spalten (gleiche Ablage wie die Lead-Boards) und ein
# Spaltenkatalog als Konstante (key, Standardtitel, Standard sichtbar); der
# Standard-Spaltensatz ist die heutige Spaltenfolge der jeweiligen Tabelle, die feste
# erste Spalte ist der Kundenname (Key lead) bzw. die Erfassung (Warteschlange).
# Die Seiten selbst liegen bei den Routern (angebote, erfassungsliste, meine_angebote,
# kunden; leads_vot baut Agent M in routers/leads.py auf diesen Bausteinen) – hier
# liegen nur Katalog, Rollenregel, Ablage, Sortierung. KONFIG_BOARDS bleibt die Liste der
# Lead-Boards (Alt-Tests), TABELLEN_BOARDS die der Angebotstool-Tabellen, ALLE_BOARDS beides.
TABELLEN_BOARDS = ("leads_vot", "erfassungen", "angebote", "meine_angebote",
                   "taifun_warteschlange", "kunden")
ALLE_BOARDS = KONFIG_BOARDS + TABELLEN_BOARDS
KATALOGE = {
    # Leads VOT Desktop (Phase 173/174, Seite von M): Reihenfolge wie M's Rückfallliste in
    # app/mein_tag.py (Kundenname fest vorn; Priorität = Hot-Ampel, Sparten = Chips)
    "leads_vot": [
        ("lead", "Kundenname", True), ("termin", "Termin", True),
        ("prioritaet", "Priorität", True), ("sparten", "Sparten", True),
        ("ort", "Ort", True), ("kanal", "Kanal", True),
        ("vertriebler", "Vertriebler", True), ("status", "Status", True),
    ],
    # Erfassungen (/erfassungen): heutige Folge Datum · Kunde · Vertriebler · Ampel · Status ·
    # Angebot – der Kundenname rückt als feste Spalte nach vorn; Sparte/Kanal/Typ stehen heute
    # als Chips in der Kundenzelle und sind zusätzlich als eigene Spalten einblendbar
    "erfassungen": [
        ("lead", "Kunde", True), ("datum", "Datum", True), ("vertriebler", "Vertriebler", True),
        ("ampel", "Ampel", True), ("status", "Status", True), ("angebot", "Angebot", True),
        ("sparte", "Sparte", False), ("typ", "Art", False), ("kanal", "Kanal", False),
        ("ort", "Ort", False), ("telefon", "Telefon", False),
    ],
    # Angebotsliste (/angebote): heutige Folge Angebots-Nr. · Kunde · Kanal · Vertriebler ·
    # Datum · Status · Verfolgung · Endbetrag (A 4b: Gesamtbetrag nach USt und Rabatt statt
    # „Brutto“) · DB (nur mit Kalkulation); „inaktiv“ = Kennzeichen „ohne Kontakt seit X
    # Tagen“ von N (Phase 176, nachfassen.inaktiv_tage_fuer – Rückfall leer)
    "angebote": [
        ("lead", "Kunde", True), ("nummer", "Angebots-Nr.", True), ("kanal", "Kanal", True),
        ("vertriebler", "Vertriebler", True), ("datum", "Datum", True), ("status", "Status", True),
        ("verfolgung", "Verfolgung", True), ("endbetrag", "Endbetrag", True),
        ("db", "DB", True), ("inaktiv", "Ohne Kontakt", False),
        ("sparte", "Sparte", False), ("netto", "Netto", False), ("ort", "Ort", False),
        ("wiedervorlage", "Wiedervorlage", False), ("ampel", "Hot-Ampel", False),
        ("cloover", "Cloover", False),   # v36 (PLAN_V22 Phase 194, B3): Vertrag/Barzahlung/Link [ANNAHME: Standard aus]
    ],
    # Meine Angebote (/meine-angebote, Außendienst): Kundenpreise, nie EK/DB
    "meine_angebote": [
        ("lead", "Kunde", True), ("nummer", "Angebots-Nr.", True), ("datum", "Datum", True),
        ("status", "Status", True), ("verfolgung", "Verfolgung", True),
        ("endbetrag", "Endbetrag", True), ("wiedervorlage", "Wiedervorlage", False),
        ("sparte", "Sparte", False), ("ort", "Ort", False),
    ],
    # TAIFUN-Warteschlange (/erfassungen?status=In TAIFUN zu schreiben bzw. individuell-offen):
    # feste erste Spalte „Erfassung“ (Datum + Sparte + Art, Link), dann Kunde …
    "taifun_warteschlange": [
        ("erfassung", "Erfassung", True), ("lead", "Kunde", True), ("sparte", "Sparte", True),
        ("vertriebler", "Vertriebler", True), ("status", "Status", True),
        ("angebot", "Angebot", True), ("ampel", "Ampel", False), ("kanal", "Kanal", False),
        ("ort", "Ort", False), ("telefon", "Telefon", False),
    ],
    # Kunden (/kunden): heutige Folge Name/Firma · Adresse · E-Mail · Telefon · Kunden-Nr.
    "kunden": [
        ("lead", "Name / Firma", True), ("adresse", "Adresse", True), ("email", "E-Mail", True),
        ("telefon", "Telefon", True), ("kunden_nr", "Kunden-Nr.", True),
        ("kanal", "Vertriebskanal", False), ("objektart", "Objektart", False),
        ("interessen", "Interessen", False), ("angelegt", "Angelegt am", False),
    ],
}
# Feste erste Spalte je Tabelle (immer sichtbar, immer vorn, kein Ablageziel)
SPALTEN_FEST_JE_BOARD = {"taifun_warteschlange": ("erfassung",)}
# Rollenregel (fest, keine Rückfrage): EK, Deckungsbeitrag, DB-Ampel und Rabatt-Interna
# stehen für die Basisrolle Außendienst (und ihre Varianten, Phase 167) in keinem Katalog –
# auch nicht ausgeblendet; gespeicherte Keys werden beim Lesen gegen den Rollen-Katalog
# gefiltert. Dieselben Spalten fehlen jeder Rolle ohne Kalkulationssicht (Projektierung,
# Leadmanagement ohne Häkchen kalkulation_sichtbar – v11-Regel der Angebotsliste).
INTERNE_SPALTEN = ("ek", "db", "db_ampel", "rabatt_intern")
# Speicher-Route der Spaltenwerkzeuge (lm_boards.js): Standard im Lead-Modul; Alias unter
# /einstellungen für Rollen, deren Pfadtabelle /lead-management nicht enthält (Projektierung –
# auth.PROJEKTIERUNG_PFADE/_SCHREIBEN; /einstellungen steht seit v30 in jeder Rollenliste)
SPALTEN_URL = "/lead-management/boards/spalten"
SPALTEN_URL_ALIAS = "/einstellungen/spalten"
# v29 (Phase 141): Spaltenbreite je Nutzer in Pixeln (leer = Standardbreite)
BREITE_MIN = 60
BREITE_MAX = 600
# v29 (Phase 142, Vertrag L2): rote Labels der Notiz-Spalte, Reihenfolge fest
MAIL_LABEL_UNGUELTIG = "E-Mail falsch"
MAIL_LABEL_FEHLER = "Mail nicht gesendet"
TAIFUN_LABEL_FEHLER = "TAIFUN-Übergabe fehlgeschlagen"   # v35 (Phase 183, Agent T) = taifun_export.LABEL_FEHLER

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


# Standard-Sichtbarkeit je Board, wo sie vom Hauptboard abweicht (v25, Prüfung F):
# die Handelsvertreter-Ansicht zeigt standardmäßig die v23-Spalten; Außendienst
# (dort die feste Spalte „Vertreter“), Innendienst, Notiz, Straße, E-Mail und
# Wiedervorlage sind über den Spaltenwähler einblendbar.
STANDARD_SICHTBAR = {
    "handelsvertreter": {"lead", "status", "kanal", "versuche", "letzter_kontakt",
                         "eingang", "ort", "interessen", "telefon", "termin"},
}


def spalten_basis(board: str, score: bool = False) -> list:
    """Spaltenkatalog eines Boards (info/handelsvertreter nutzen den Hauptboard-
    Katalog, ggf. mit eigener Standard-Sichtbarkeit); Score nur bei aktivem
    Scoring (v25)."""
    basis = SPALTEN_TERMINIERT if board == "terminiert" else SPALTEN
    if score:
        stelle = next((i for i, (k, _, _) in enumerate(basis) if k == "status"), 0) + 1
        basis = basis[:stelle] + [SPALTE_SCORE] + basis[stelle:]
    sichtbar = STANDARD_SICHTBAR.get(board)
    if sichtbar is not None:
        basis = [(k, t, bool(s and k in sichtbar)) for k, t, s in basis]
    return basis


def _benutzer_id(benutzer) -> int:
    """Vertrag v25: spalten_fuer(session, benutzer, board) nimmt den Benutzer
    oder (v23) seine ID."""
    if benutzer is None:
        return 0
    return int(getattr(benutzer, "id", benutzer) or 0)


# --- v33 (Phase 174): Kataloge der Angebotstool-Tabellen, Rollenregel ------------------

def board_bekannt(board: str) -> bool:
    """Lead-Board (KONFIG_BOARDS) oder Angebotstool-Tabelle (TABELLEN_BOARDS)?"""
    return board in ALLE_BOARDS


def ist_tabelle(board: str) -> bool:
    """Angebotstool-Tabelle (Phase 174) – kein Lead-Gate, Katalog nach Basisrolle."""
    return board in TABELLEN_BOARDS


def spalten_fest(board: str) -> tuple:
    """Feste Spalten je Board: immer sichtbar, immer vorn, kein Ablageziel beim Ziehen
    (Kundenname; bei der TAIFUN-Warteschlange die Erfassung)."""
    return SPALTEN_FEST_JE_BOARD.get(board, SPALTEN_FEST)


def _benutzer_objekt(session, benutzer):
    """Benutzer-Objekt für die Rollenregel (v23-Aufrufer übergeben nur die ID)."""
    if benutzer is None or hasattr(benutzer, "basisrolle"):
        return benutzer
    if session is None:
        return None
    try:
        return session.get(Benutzer, int(benutzer))
    except (TypeError, ValueError):
        return None


def kalkulation_sichtbar(benutzer) -> bool:
    """Darf dieser Benutzer EK/DB sehen? Admin und Innendienst immer, Außendienst (und
    Varianten) nie, Projektierung/Leadmanagement nur mit Häkchen kalkulation_sichtbar
    (v11-Regel der Angebotsliste)."""
    if benutzer is None:
        return False
    basis = getattr(benutzer, "basisrolle", "") or ""
    if basis == "aussendienst":
        return False
    if basis in ("admin", "innendienst"):
        return True
    return bool(getattr(benutzer, "kalkulation_sichtbar", False))


def katalog_fuer(board: str, benutzer, session=None, score: bool = False) -> list:
    """Spaltenkatalog eines Boards NACH Rollenregel: (key, Standardtitel, Standard sichtbar).
    Angebotstool-Tabellen aus KATALOGE – für die Basisrolle Außendienst (und jede Rolle
    ohne Kalkulationssicht) fehlen EK/DB/DB-Ampel/Rabatt-Interna komplett (auch nicht
    ausgeblendet); Lead-Boards weiter über spalten_basis (Score nur bei aktivem Scoring).
    `benutzer` = Benutzer oder Benutzer-ID (dann wird er über die Session geladen)."""
    if not ist_tabelle(board):
        return spalten_basis(board, score=score)
    basis = list(KATALOGE[board])
    if not kalkulation_sichtbar(_benutzer_objekt(session, benutzer)):
        basis = [(k, t, s) for k, t, s in basis if k not in INTERNE_SPALTEN]
    return basis


def spalten_url(benutzer) -> str:
    """Speicher-Route der Spaltenwerkzeuge für diese Rolle (data-lm-spalten-url): die
    Projektierung erreicht /lead-management nicht (Pfadtabellen in auth.py, dort tabu) und
    nutzt den Alias unter /einstellungen; alle anderen Rollen die Lead-Route."""
    basis = getattr(benutzer, "basisrolle", "") or ""
    return SPALTEN_URL_ALIAS if basis in ("projektierung", "montage") else SPALTEN_URL


def breite_normieren(wert) -> int | None:
    """v29: Spaltenbreite in Pixeln (60–600) oder None (= Standard)."""
    if wert in (None, "", 0, "0"):
        return None
    try:
        px = int(float(str(wert).strip()))
    except (TypeError, ValueError):
        return None
    return max(BREITE_MIN, min(BREITE_MAX, px))


def _konfig_normieren(konfig) -> dict:
    """Gespeicherte Board-Konfiguration in die v25-Struktur bringen:
    {"spalten": [{key, sichtbar, name, breite}], "sort": {key, richtung} | None}.
    Liest die v23-Liste [[key, sichtbar]] bzw. [{key, sichtbar}] weiter;
    v29: `breite` (px) je Spalte, v25-Einträge ohne Breite = Standard (None)."""
    spalten, sort = [], None
    roh = None
    if isinstance(konfig, dict):
        roh = konfig.get("spalten")
        s = konfig.get("sort")
        if isinstance(s, dict) and s.get("key"):
            sort = {"key": str(s["key"]),
                    "richtung": "ab" if str(s.get("richtung", "auf")) == "ab" else "auf"}
    elif isinstance(konfig, (list, tuple)):
        roh = konfig
    for eintrag in roh or []:
        breite = None
        try:
            if isinstance(eintrag, dict):
                key, sichtbar, name = eintrag.get("key"), eintrag.get("sichtbar", True), eintrag.get("name", "")
                breite = breite_normieren(eintrag.get("breite"))
            else:
                key, sichtbar = eintrag[0], eintrag[1]
                name = eintrag[2] if len(eintrag) > 2 else ""
        except (TypeError, IndexError, KeyError):
            continue
        if not key:
            continue
        spalten.append({"key": str(key), "sichtbar": bool(sichtbar),
                        "name": str(name or "").strip()[:60], "breite": breite})
    return {"spalten": spalten, "sort": sort}


def spalten_konfig(session: Session, benutzer, board: str) -> dict:
    """Rohkonfiguration des Nutzers für ein Board (normiert, ohne Katalogabgleich)."""
    alle = lead_v2.einstellung_holen(session, _benutzer_id(benutzer), EINSTELLUNG_KEY, {}) or {}
    konfig = alle.get(board) if isinstance(alle, dict) else None
    return _konfig_normieren(konfig)


def spalten_fuer(session: Session, benutzer, board: str) -> list[dict]:
    """Spaltenreihenfolge, Sichtbarkeit und eigener Anzeigename des Nutzers
    (A-14, v25); unbekannte Keys fallen weg, neue Spalten hängen sich hinten
    an, ‚lead' (Kundenname) bleibt vorn. Je Eintrag: key, titel (Anzeige =
    eigener Name oder Standard), standard (Standardtitel), name (eigener
    Name oder ''), sichtbar, breite (px oder None = Standard, v29).
    `benutzer` = Benutzer oder Benutzer-ID.
    v33 (Phase 174): Angebotstool-Tabellen (TABELLEN_BOARDS) nutzen den Katalog der
    Basisrolle (katalog_fuer) – gespeicherte Keys außerhalb des Rollen-Katalogs (EK/DB
    eines Außendienstlers) fallen beim Lesen weg; feste Spalte je Board (spalten_fest)."""
    basis = katalog_fuer(board, benutzer, session, score=lead_v2.score_aktiv(session))
    fest = spalten_fest(board)
    titel = {k: t for k, t, _ in basis}
    konfig = spalten_konfig(session, benutzer, board)
    ergebnis, gesehen = [], set()
    for sp in konfig["spalten"]:
        key = sp["key"]
        if key in titel and key not in gesehen:
            gesehen.add(key)
            ergebnis.append({"key": key, "titel": sp["name"] or titel[key], "standard": titel[key],
                             "name": sp["name"], "sichtbar": sp["sichtbar"] or key in fest,
                             "breite": sp.get("breite")})
    for key, t, s in basis:
        if key not in gesehen:
            ergebnis.append({"key": key, "titel": t, "standard": t, "name": "", "sichtbar": s,
                             "breite": None})
    ergebnis.sort(key=lambda sp: 0 if sp["key"] in fest else 1)
    return ergebnis


def sortierung_fuer(session: Session, benutzer, board: str) -> dict | None:
    """Gemerkte Sortierung {key, richtung} des Nutzers für das Board (oder None);
    Keys außerhalb des AKTIVEN Katalogs zählen nicht (eine gemerkte Score-
    Sortierung ruht, solange score_aktiv aus ist – gespeichert bleibt sie;
    v33: eine gemerkte DB-Sortierung zählt für den Außendienst nicht)."""
    sort = spalten_konfig(session, benutzer, board)["sort"]
    if not sort:
        return None
    gueltig = {k for k, _, _ in katalog_fuer(board, benutzer, session,
                                             score=lead_v2.score_aktiv(session))}
    return sort if sort["key"] in gueltig else None


_BEHALTEN = object()


def spalten_speichern(session: Session, benutzer, board: str, liste=_BEHALTEN,
                      sort=_BEHALTEN, umbenennen=None, zuruecksetzen: bool = False,
                      breite=None) -> list[dict]:
    """Konfiguration des Nutzers schreiben (nur dieser Nutzer, je Board):
    liste = [{key, sichtbar, name?}] oder [[key, sichtbar]] in gewünschter
    Reihenfolge (weggelassen = Reihenfolge/Sichtbarkeit bleiben),
    sort = {key, richtung} | None (weggelassen = bleibt), umbenennen =
    (key, name) mit leer = Standard, zuruecksetzen = alles auf Standard,
    v29: breite = (key, px | None) – None = Standardbreite (Doppelklick).
    v33 (Phase 174): Angebotstool-Tabellen speichern nur Keys des Rollen-Katalogs
    (ein Außendienstler kann EK/DB auch nicht „mitspeichern“); feste Spalte je Board."""
    benutzer_id = _benutzer_id(benutzer)
    fest = spalten_fest(board)
    katalog = katalog_fuer(board, benutzer, session, score=True)
    gueltig = {k for k, _, _ in katalog}
    alt = spalten_konfig(session, benutzer_id, board)
    namen = {sp["key"]: sp["name"] for sp in alt["spalten"] if sp["name"]}
    breiten = {sp["key"]: sp.get("breite") for sp in alt["spalten"] if sp.get("breite")}
    if zuruecksetzen:
        neu_spalten, neu_sort, namen, breiten = [], None, {}, {}
    else:
        neu_sort = alt["sort"]
        if liste is _BEHALTEN:
            neu_spalten = [dict(sp) for sp in alt["spalten"]]
        else:
            neu_spalten = []
            for sp in _konfig_normieren(liste if isinstance(liste, (list, tuple)) else [])["spalten"]:
                if sp["key"] in gueltig and sp["key"] not in [n["key"] for n in neu_spalten]:
                    neu_spalten.append({"key": sp["key"],
                                        "sichtbar": sp["sichtbar"] or sp["key"] in fest,
                                        "name": sp["name"] or namen.get(sp["key"], ""),
                                        "breite": sp.get("breite") or breiten.get(sp["key"])})
        if sort is not _BEHALTEN:
            if isinstance(sort, dict) and sort.get("key") in gueltig:
                neu_sort = {"key": str(sort["key"]),
                            "richtung": "ab" if str(sort.get("richtung", "auf")) == "ab" else "auf"}
            else:
                neu_sort = None
        if umbenennen:
            key, name = umbenennen
            name = str(name or "").strip()[:60]
            if key in gueltig:
                if key not in [n["key"] for n in neu_spalten]:
                    # Spalte noch ohne Eintrag: Katalogreihenfolge/-sichtbarkeit übernehmen
                    for k, _, s in katalog:
                        if k not in [n["key"] for n in neu_spalten]:
                            neu_spalten.append({"key": k, "sichtbar": s, "name": namen.get(k, "")})
                for sp in neu_spalten:
                    if sp["key"] == key:
                        sp["name"] = name
        if breite:
            # v29 (Phase 141): Breite einer Spalte setzen (px) oder auf Standard (None)
            key, px = breite
            px = breite_normieren(px)
            if key in gueltig:
                if key not in [n["key"] for n in neu_spalten]:
                    for k, _, s in katalog:
                        if k not in [n["key"] for n in neu_spalten]:
                            neu_spalten.append({"key": k, "sichtbar": s, "name": namen.get(k, ""),
                                                "breite": breiten.get(k)})
                for sp in neu_spalten:
                    if sp["key"] == key:
                        sp["breite"] = px
    alle = lead_v2.einstellung_holen(session, benutzer_id, EINSTELLUNG_KEY, {}) or {}
    if not isinstance(alle, dict):
        alle = {}
    gespeichert = []
    for sp in neu_spalten:
        eintrag = {"key": sp["key"], "sichtbar": bool(sp["sichtbar"]), "name": sp.get("name", "")}
        if sp.get("breite"):
            eintrag["breite"] = int(sp["breite"])
        gespeichert.append(eintrag)
    alle[board] = {"spalten": gespeichert, "sort": neu_sort}
    lead_v2.einstellung_setzen(session, benutzer_id, EINSTELLUNG_KEY, alle)
    return spalten_fuer(session, benutzer_id, board)


def kundenname(kunde) -> str:
    """v25: „Anrede Vorname Nachname“ (Anrede nur wenn gesetzt); Firma davor,
    falls vorhanden."""
    if kunde is None:
        return ""
    person = " ".join(t.strip() for t in (kunde.anrede, kunde.vorname, kunde.nachname)
                      if t and t.strip())
    firma = (kunde.firma or "").strip()
    if firma and person:
        return f"{firma} ({person})"
    return firma or person


def phasen_labels(logik=None) -> dict:
    """v25: Phase → Label ausschließlich aus dem Blatt Status (beide Kontakt-
    Phasen „Kontaktiert“); Fallback Phasenname."""
    logik = logik or leadmanagement_logik.hole_logik()
    return {phase: status_label(logik, phase)[0] for phase in LEAD_PHASEN}


def phasen_mit_label(logik, phase: str) -> set:
    """Alle Phasen, die dasselbe Label tragen wie `phase` (mindestens sie selbst)."""
    if not phase:
        return set()
    label = status_label(logik, phase)[0]
    return {p for p in LEAD_PHASEN if status_label(logik, p)[0] == label} | {phase}


# Sortierwert je Spalte (serverseitig, gemerkte Sortierung); None = ans Ende
def _sortier_wert(z: dict, key: str):
    k, v = z["kunde"], z["vorgang"]
    if key == "lead":
        return ((k.nachname or k.firma or "") + " " + (k.vorname or "")).strip().lower() or None
    if key in ("anrede", "vorname", "nachname", "strasse", "telefon", "email"):
        wert = getattr(k, key, None) or (k.firma if key == "nachname" else None)
        return (wert or "").strip().lower() or None
    if key == "status":
        return (z.get("status_label") or "").lower() or None
    if key == "score":
        return v.score_punkte if v.score_punkte is not None else None
    if key == "kanal":
        return (z.get("kanal") or "").lower() or None
    if key == "interessen":
        return ",".join(z.get("sparten") or []) or None
    if key == "grosskunde":
        return 1 if z.get("grosskunde") else 0     # v31 (Phase 153): Großkunden zuerst bei „ab“
    if key == "objektart":
        return (k.objektart or "").strip().lower() or None   # v35 (Phase 186)
    if key == "angebot":
        angebote = z.get("angebote") or []
        return angebote[0].nummer if angebote else None
    if key == "versuche":
        return z.get("versuche", 0)
    if key == "letzter_kontakt":
        return z["letzter"].zeitpunkt if z.get("letzter") else None
    if key == "eingang":
        return z.get("eingang")
    if key == "notiz":
        return (k.notizen or "").strip().lower() or None
    if key == "ad":
        return z["ad"].name.lower() if z.get("ad") else None
    if key == "innendienst":
        return z["leadmanager"].name.lower() if z.get("leadmanager") else None
    if key == "ort":
        return ((k.plz or "") + " " + (k.ort or "")).strip().lower() or None
    if key == "termin":
        return z["termin"].beginn if z.get("termin") and z["termin"].beginn else None
    if key == "wiedervorlage":
        return z.get("wiedervorlage")
    if key == "taifun":
        return z.get("taifun_am")   # v35 (Phase 183, Agent T): nach Übergabedatum
    return None


def zeilen_sortieren(zeilen: list, sort: dict | None, jetzt=None, wert=None) -> list:
    """Zeilen einer Gruppe nach der gemerkten Spalte sortieren (auf/ab, leere
    Werte immer ans Ende); ohne Sortierung Eingang neueste zuerst.
    v29 (Phase 142, Vertrag L2): Zeilen mit Rang 0 (Mail nicht gesendet /
    E-Mail falsch) stehen immer ganz oben – vor jeder Sortierung.
    v33 (Phase 174, Vertrag T): generisch für jede Tabelle – `wert(zeile, key)` liefert
    den Sortierwert einer Zeile (None = leer, ans Ende; gemischte Typen fallen auf Text
    zurück); mit `wert` bleibt ohne Sortierung die übergebene Reihenfolge erhalten
    (Standardsortierung der Route), Zeilen dürfen Modelle oder Dicts sein."""
    jetzt = jetzt or datetime.now()
    if not sort or not sort.get("key"):
        if wert is None:
            zeilen.sort(key=lambda z: z["eingang"] or jetzt, reverse=True)
    else:
        key, ab = sort["key"], sort.get("richtung") == "ab"
        holen = wert or _sortier_wert
        mit = [(z, holen(z, key)) for z in zeilen]
        voll = [p for p in mit if p[1] is not None]
        leer = [p[0] for p in mit if p[1] is None]
        try:
            voll.sort(key=lambda p: p[1], reverse=ab)
        except TypeError:
            voll.sort(key=lambda p: str(p[1]), reverse=ab)
        zeilen[:] = [p[0] for p in voll] + leer
    if wert is None:
        zeilen.sort(key=lambda z: 0 if z.get("rang0") else 1)   # stabil: Rang 0 zuerst
    return zeilen


def sort_text(wert) -> str | None:
    """Sortierwert für Text (klein, ohne Rand); leer → None (ans Ende). Vertrag T."""
    if wert is None:
        return None
    text = str(wert).strip().lower()
    return text or None


def sort_zahl(wert):
    """Sortierwert für Zahlen/Cent; None oder nicht lesbar → None (ans Ende). Vertrag T."""
    if wert is None or wert == "":
        return None
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def angebot_sortwert(a, key: str, kunden: dict | None = None, vorgaenge: dict | None = None,
                     vertriebler_namen: dict | None = None, extra: dict | None = None):
    """v33 (Phase 174): Sortierwert je Spalte der Angebotslisten (Angebotsliste und Meine
    Angebote, Kataloge angebote/meine_angebote). kunden = {id: Kunde}, vorgaenge = {id: Vorgang},
    vertriebler_namen = {angebot_id: Name}, extra = {angebot_id: Wert} für die Spalte inaktiv
    (Kennzeichen von N). None = leer (ans Ende)."""
    kunde = (kunden or {}).get(a.kunde_id)
    vorgang = (vorgaenge or {}).get(a.vorgang_id) if a.vorgang_id else None
    if key == "lead":
        return sort_text(kunde.anzeige_name if kunde else None)
    if key == "nummer":
        return sort_text((a.taifun_nummer or "") if a.extern else a.nummer)
    if key == "kanal":
        return sort_text(kunde.vertriebskanal if kunde else None)
    if key == "vertriebler":
        return sort_text((vertriebler_namen or {}).get(a.id))
    if key == "datum":
        return a.datum
    if key == "status":
        return sort_text(a.status)
    if key == "verfolgung":
        status = (vorgang.verfolgung_status if vorgang else "") or ""
        if not status:
            return None
        try:
            from app import verfolgung as verfolgung_modul
            return list(verfolgung_modul.STATUS).index(status)
        except (ImportError, AttributeError, ValueError):
            return sort_text(status)
    if key == "endbetrag":
        return a.summen()["endbetrag"]
    if key == "netto":
        return None if a.extern else a.summen()["netto"]
    if key == "db":
        return None if a.extern else a.deckungsbeitrag()["db"]
    if key == "inaktiv":
        return sort_zahl((extra or {}).get(a.id))
    if key == "sparte":
        return sort_text(a.konfigurator_typ or "WP")
    if key == "ort":
        return sort_text(f"{kunde.plz or ''} {kunde.ort or ''}" if kunde else None)
    if key == "wiedervorlage":
        return (vorgang.wiedervorlage_am if vorgang else None) or getattr(a, "wiedervorlage_am", None)
    if key == "ampel":
        ampel = (vorgang.verfolgung_ampel if vorgang else "") or getattr(a, "verfolgung_ampel", "") or ""
        return {"heiss": 0, "warm": 1, "kalt": 2}.get(ampel)
    if key == "cloover":   # v36 (PLAN_V22 Phase 194, B3): 0 Vertrag · 1 Barzahlung · 2 Link · leer
        from app import cloover_projekt
        return cloover_projekt.sortwert(a)
    return None


def mail_labels(vorgang) -> list[str]:
    """v29 (Phase 142, Vertrag L2): rote Labels vorn in der Notiz-Spalte –
    „E-Mail falsch“ (vorgang.email_status = ungueltig) zuerst, dann
    „Mail nicht gesendet“ (vorgang.mail_fehler)."""
    labels = []
    if (getattr(vorgang, "email_status", None) or "") == "ungueltig":
        labels.append(MAIL_LABEL_UNGUELTIG)
    if getattr(vorgang, "mail_fehler", False):
        labels.append(MAIL_LABEL_FEHLER)
    # v35 (PLAN_LEAD_V6 Phase 183, Agent T): „TAIFUN-Übergabe fehlgeschlagen“ – gleiches Muster
    if (getattr(vorgang, "taifun_export_status", "") or "") == "fehler":
        labels.append(TAIFUN_LABEL_FEHLER)
    return labels


def _taifun_text(vorgang) -> str:
    """v35 (Phase 183, Agent T): Tooltip der Spalte „TAIFUN-Übergabe“ (taifun_export.board_text)."""
    try:
        from app import taifun_export
        return taifun_export.board_text(vorgang)
    except Exception:   # noqa: BLE001
        return ""


def label_titel(vorgang) -> dict:
    """Tooltip je rotem Label der Notiz-Spalte (v35, Agent T – _tabelle.html liest z.label_titel)."""
    return {MAIL_LABEL_UNGUELTIG: (getattr(vorgang, "email_status_grund", "") or ""),
            MAIL_LABEL_FEHLER: (getattr(vorgang, "mail_fehler_text", "") or ""),
            TAIFUN_LABEL_FEHLER: (getattr(vorgang, "taifun_export_grund", "") or "")}


# --- Farben, Avatare -----------------------------------------------------------------

def _hash_index(text: str, n: int) -> int:
    return int(hashlib.md5((text or "").lower().encode("utf-8")).hexdigest(), 16) % n


def kanal_farben(session: Session) -> dict:
    """{kanal klein: #hex} – v35 (PLAN_LEAD_V6 Phase 184): aus den Stammdaten
    `vertriebskanaele` (lead_kanaele.kanal_farben_map, inkl. Aliase „swd“); der Parameter
    kanal_farben (v23, jetzt aus der Tabelle gespiegelt) füllt nur noch Werte ohne Zeile."""
    from app import lead_kanaele
    farben = dict(lead_kanaele.kanal_farben_map(session))
    roh = kern.parameter_holen(session, "kanal_farben", "") or ""
    try:
        werte = json.loads(roh) if roh.strip() else {}
    except ValueError:
        werte = {}
    if isinstance(werte, dict):
        for k, v in werte.items():
            if str(v).strip():
                farben.setdefault(str(k).strip().lower(), str(v).strip())
    return farben


def kanal_farbe(farben: dict, kanal: str) -> str:
    kanal = (kanal or "").strip()
    if not kanal:
        return ""
    return farben.get(kanal.lower()) or KANAL_PALETTE[_hash_index(kanal, len(KANAL_PALETTE))]


def grosskunde_farbe(session: Session) -> str:
    """v31 (PLAN_LEAD_V5 Phase 153): Badge-Farbe „Großkunde“ aus dem Parameter
    grosskunde_farbe (Hex, kanal_farben-Mechanik); leer = Paar --status-violett aus
    der CSS-Klasse .lm-grosskunde (lead_v2.css)."""
    wert = (kern.parameter_holen(session, "grosskunde_farbe", "") or "").strip()
    return wert if re.fullmatch(r"#[0-9a-fA-F]{6}", wert) else ""


# --- v35 (PLAN_LEAD_V6 Phase 186): Rechte je Zeile, Kanal-Auswahl, Pflichtfelder ----------

def bearbeiten_erlaubt(session: Session, benutzer, vorgang) -> bool:
    """Darf dieser Benutzer diese Zeile inline bearbeiten? Vertrag mit Agent R (Phase 185):
    lead_v2.bearbeiten_erlaubt(session, benutzer, vorgang) entscheidet – Innendienst/
    Leadmanagement/Admin alle Leads, angestellter Außendienst nur Leads mit vorgaenge.ad_id =
    eigene ID, Handelsvertreter nur Leads ihrer Gruppe (lead_v2.hv_gruppe_fuer). Jede
    Inline-Änderung (POST /boards/zeile/{id}) und jede Zeile der Boards (z.bearbeitbar) läuft
    hierüber – keine zweite Rechtelogik."""
    if benutzer is None or vorgang is None:
        return False
    return bool(lead_v2.bearbeiten_erlaubt(session, benutzer, vorgang))


def kanal_auswahl(session: Session, aktuell: str = "") -> list[dict]:
    """Einträge des Kanal-Dropdowns der Inline-Bearbeitung: [{wert, farbe, waehlbar}].
    Vertrag K (Phase 184): lead_kanaele.kanal_sortiert(session) liefert die aktiven Kanäle
    nach Häufigkeit (als Namen, Dicts oder Objekte); ohne das Modul die Kanalwerte der
    Angebotsprofile (kern.kanal_werte) ohne „Standard“ (entfällt als Label, Plan 184).
    Der aktuelle Wert steht immer in der Liste – ein inaktiver Kanal als „(nicht mehr
    wählbar)“; „?“ (unklar) ist wählbar und wird in der Zelle rot markiert."""
    farben = kanal_farben(session)
    eintraege: list[dict] = []
    gesehen: set[str] = set()

    def _zufuegen(wert, farbe="", waehlbar=True):
        wert = str(wert or "").strip()
        if not wert or wert.lower() in gesehen:
            return
        gesehen.add(wert.lower())
        eintraege.append({"wert": wert, "farbe": farbe or kanal_farbe(farben, wert),
                          "waehlbar": bool(waehlbar)})
    try:
        from app import lead_kanaele   # Agent K (Phase 184)
        sortiert = getattr(lead_kanaele, "kanal_sortiert", None)
        liste = sortiert(session) if sortiert is not None else []
        farbe_fn = getattr(lead_kanaele, "kanal_farbe", None)
    except Exception:   # noqa: BLE001 – ohne Kanal-Stammdaten der v23-Weg
        liste, farbe_fn = [], None
    for eintrag in liste or []:
        if isinstance(eintrag, dict):
            name = eintrag.get("name") or eintrag.get("wert") or eintrag.get("key") or ""
            farbe = eintrag.get("farbe") or ""
            waehlbar = eintrag.get("aktiv", True)
        elif isinstance(eintrag, str):
            name, farbe, waehlbar = eintrag, "", True
        else:
            name = getattr(eintrag, "name", "") or getattr(eintrag, "key", "")
            farbe = getattr(eintrag, "farbe", "") or ""
            waehlbar = getattr(eintrag, "aktiv", True)
        if not farbe and farbe_fn is not None:
            try:
                farbe = farbe_fn(session, name) or ""
            except Exception:   # noqa: BLE001
                farbe = ""
        _zufuegen(name, farbe, waehlbar)
    if not eintraege:
        for wert in kern.kanal_werte(session):
            if wert.lower() != "standard":
                _zufuegen(wert)
    if KANAL_UNKLAR.lower() not in gesehen:
        _zufuegen(KANAL_UNKLAR, farben.get(KANAL_UNKLAR, ""))
    aktuell = (aktuell or "").strip()
    if aktuell and aktuell.lower() not in gesehen:
        _zufuegen(aktuell, "", False)
    return eintraege


def pflicht_zellen(session: Session, kunde, vorgang) -> set:
    """Spalten-Keys mit Pflichtfeld-Verletzung (rote Zelle): leere Pflichtfelder aus
    lead_v2.pflichtfelder_offen (Parameter pflichtfelder) plus Kanal „?“ (unklar)."""
    keys: set = set()
    if kunde is None:
        return keys
    try:
        for name in lead_v2.pflichtfelder_offen(session, kunde, vorgang):
            key = PFLICHT_ZELLEN.get(str(name))
            if key:
                keys.add(key)
    except Exception:   # noqa: BLE001 – Markierung ist Komfort, die Tabelle bleibt
        pass
    if (kunde.vertriebskanal or "").strip() == KANAL_UNKLAR:
        keys.add("kanal")
    return keys


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
    Vor-Ort-Termin zieht einen Hauptboard-Lead ins Board Deals (Key
    terminiert, Angebotserstellung), auch wenn die Phase noch nicht
    nachgezogen ist."""
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
        # v31 (Phase 153/154): Filter-Chips „Großkunde“ und „Archiv“ (archivierte Leads)
        "grosskunde": q.get("grosskunde", "") == "1",
        "archiviert": q.get("archiviert", "") == "1",
        # v35 (PLAN_LEAD_V6 Phase 184): Filter-Chip „Kanal unklar“ (Kanal „?“)
        "kanal_unklar": q.get("kanal_unklar", "") == "1",
        "taifun": q.get("taifun", "") == "1",   # v35 (Phase 183, Agent T): Chip „an TAIFUN übergeben“
        "sort": None,        # v25: gemerkte Sortierung des Nutzers (lm_boards setzt sie)
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
    # v31 (PLAN_LEAD_V5 Phase 154): Archiv ist eine Lead-Sicht – Standard nur nicht
    # archivierte Leads; archiviert=True zeigt NUR das Archiv (Filter-Chip „Archiv“),
    # archiviert="alle" beide (Nachladen einer Zeile nach Archivieren/Wiederherstellen)
    archiv_sicht = f.get("archiviert")
    if archiv_sicht is True or archiv_sicht == "1":
        abfrage = abfrage.filter(Vorgang.archiviert_am.isnot(None))
    elif archiv_sicht != "alle":
        abfrage = lead_archiv.filter_aktiv(abfrage)
    if hv:
        # v35 (PLAN_LEAD_V6 Phase 185, Agent R): Handelsvertreter sehen die Leads ihrer Gruppe
        abfrage = abfrage.filter(Vorgang.ad_id.in_(lead_v2.hv_gruppe_fuer(session, benutzer.id) or {benutzer.id}))
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
    # v31 (PLAN_LEAD_V5 Phase 153, Vertrag AT 4.8): Deals-Board gruppiert Erfassungen,
    # Angebote und Termine je Objekt – nur für Vorgänge mit mehr als einem aktiven Objekt
    # (eine Zählabfrage, dann vorgang_verlauf.objekt_gruppen je betroffenem Vorgang)
    objekt_gruppen: dict[int, list] = {}
    if board == "terminiert":
        from sqlalchemy import func

        from app import vorgang_verlauf
        from app.models import VorgangObjekt
        for vid, anzahl in (session.query(VorgangObjekt.vorgang_id, func.count(VorgangObjekt.id))
                            .filter(VorgangObjekt.vorgang_id.in_(ids), VorgangObjekt.aktiv.is_(True))
                            .group_by(VorgangObjekt.vorgang_id)):
            if anzahl > 1:
                objekt_gruppen[vid] = vorgang_verlauf.objekt_gruppen(session, vid)
    farben = kanal_farben(session)
    maximum = kern.versuche_max(session)
    grenze = jetzt - timedelta(days=ARCHIV_TAGE)
    suche = f.get("q", "")
    # v31 (Phase 154): Kopie-Verweise beidseitig (kopie_von_id) – „Kopie von V123“ am
    # neuen Vorgang, „Kopie: V124“ am Ursprung
    kopien: dict[int, list] = {}
    for (kid, von) in session.query(Vorgang.id, Vorgang.kopie_von_id).filter(
            Vorgang.kopie_von_id.in_(ids)):
        kopien.setdefault(von, []).append(kid)
    hv_alle = {b.id for b in lead_v2.handelsvertreter_liste(session)}
    # v33 (Phase 175, Vorschlag R 4c): Kennzeichen „Simons Gruppe (noch nicht verteilt)“ je
    # Zeile – eine Abfrage je Board (lead_v2.hv_gruppe_offen_ids), Badge in der AD-Zelle
    gruppe_offen = lead_v2.hv_gruppe_offen_ids(session, vorgaenge)
    # v25: Status-Filter trifft alle Phasen mit demselben Label („Kontaktiert“
    # = in_kontaktierung + qualifiziert)
    status_filter = phasen_mit_label(logik, f.get("status") or "")

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
        if status_filter and v.lead_phase not in status_filter:
            continue
        if f.get("kanal") and (kunde.vertriebskanal or "").lower() != f["kanal"].lower():
            continue
        sparten = sparten_modul.codes(kunde.interesse)   # v31 (Phase 157): inkl. MS/WA/DMS
        if f.get("sparte") and f["sparte"] not in sparten:
            continue
        if f.get("grosskunde") and not getattr(kunde, "grosskunde", False):
            continue   # v31 (Phase 153): Filter-Chip „Großkunde“
        if f.get("taifun") and not getattr(v, "taifun_export_am", None):
            continue   # v35 (Phase 183, Agent T): Filter-Chip „an TAIFUN übergeben“
        if f.get("kanal_unklar") and (kunde.vertriebskanal or "").strip() != "?":
            continue   # v35 (Phase 184): Filter-Chip „Kanal unklar“ (lead_kanaele.KANAL_UNKLAR)
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
            "objekt_gruppen": objekt_gruppen.get(v.id, []),   # v31 (Phase 153): leer = ein Objekt
            # v29 (Phase 142, Vertrag L2): Mail-Fehler / ungültige E-Mail → Rang 0 + Labels
            "mail_labels": mail_labels(v),
            "rang0": bool(mail_labels(v)),
            "label_titel": label_titel(v),   # v35 (Phase 183, Agent T): Tooltips der roten Labels
            # v35 (Phase 183, Agent T): Spalte „TAIFUN-Übergabe“ (Datum, Status, Tooltip)
            "taifun_am": getattr(v, "taifun_export_am", None),
            "taifun_status": getattr(v, "taifun_export_status", "") or "",
            "taifun_text": _taifun_text(v),
            "mail_fehler_text": (getattr(v, "mail_fehler_text", "") or "") if getattr(v, "mail_fehler", False) else "",
            "email_status_grund": (getattr(v, "email_status_grund", "") or "")
            if (getattr(v, "email_status", None) or "") == "ungueltig" else "",
            # v31 (Phase 153/154/156): Großkunde, Archiv-Sicht, Kopie-Verweise, HV-Lead
            "grosskunde": bool(getattr(kunde, "grosskunde", False)),
            "archiviert": lead_archiv.ist_archiviert(v),
            "archiv_text": (f"Archiviert am {v.archiviert_am.strftime('%d.%m.%Y %H:%M')}"
                            + (f" von {benutzer_map[v.archiviert_von].name}"
                               if v.archiviert_von in benutzer_map else "")
                            ) if lead_archiv.ist_archiviert(v) else "",
            "kopie_von": v.kopie_von_id,
            "kopien": kopien.get(v.id, []),
            "hv_lead": bool(v.ad_id and v.ad_id in hv_alle),
            "hv_gruppe_offen": v.id in gruppe_offen,   # v33 (Phase 175, R 4c)
            # v35 (PLAN_LEAD_V6 Phase 186): Rechte je Zeile, Pflichtfeld-Verletzungen (rote
            # Zelle), Kanal „?“ = unklar, Objektart für die neue Spalte
            "bearbeitbar": bearbeiten_erlaubt(session, benutzer, v),
            "pflicht_zellen": pflicht_zellen(session, kunde, v),
            "kanal_unklar": (kunde.vertriebskanal or "").strip() == KANAL_UNKLAR,
            "objektart": (kunde.objektart or "").strip().upper(),
        }
        if not _suche_passt(zeile, suche):
            continue
        gruppen[gruppe].append(zeile)
    ergebnis = []
    for key in BOARDS[board]["gruppen"]:
        zeilen = gruppen[key]
        zeilen_sortieren(zeilen, f.get("sort"), jetzt)
        ergebnis.append({"key": key, "titel": GRUPPEN_NAMEN[key],
                         "erkl": GRUPPEN_ERKLAERUNG.get(key, ""), "zeilen": zeilen,
                         "eingeklappt": key in GRUPPEN_EINGEKLAPPT and not f.get("gruppe")})
    return {"board": board, "gruppen": ergebnis, "jetzt": jetzt, "hv": hv,
            "anzahl": sum(len(g["zeilen"]) for g in ergebnis), "versuche_max": maximum}


def zeile_fuer(session: Session, benutzer, vorgang: Vorgang) -> dict | None:
    """Eine einzelne Zeile (nach Inline-Änderung) – sucht den Vorgang in
    beiden Boards; None, wenn er in keiner Gruppe mehr sichtbar ist."""
    for board in BOARDS:
        daten = board_zeilen(session, benutzer, board,
                             {"archiv": True, "archiviert": "alle", "ids": [vorgang.id]})
        for g in daten["gruppen"]:
            for z in g["zeilen"]:
                if z["vorgang"].id == vorgang.id:
                    return z
    return None


def hv_zeile_fuer(session: Session, benutzer, vorgang: Vorgang) -> dict | None:
    """v35 (PLAN_LEAD_V6 Phase 186): Zeile der Handelsvertreter-Ansicht nach einer Inline-
    Änderung – Hauptboard-Zeile (zeile_fuer) plus die HV-Felder aus
    lead_handelsvertreter.zeilen_bauen (Vertreter, Sperren, Hinweise); None, wenn der
    Vorgang in keiner Gruppe mehr sichtbar ist. Liefert {zeile, hv_liste, standard, gesamt}
    für das Makro hv_zeile (leadmanagement/_hv_zeile.html)."""
    from app import lead_handelsvertreter as hv_modul
    basis = hv_modul.zeilen_bauen(session, [vorgang], hv_modul.hv_kreis(session))
    if not basis:
        return None
    z105 = zeile_fuer(session, benutzer, vorgang)
    zeilen = hv_modul.zeilen_zusammenfuehren(basis, {vorgang.id: z105} if z105 else None)
    zeile = zeilen[0]
    if z105 is None:
        zeile["phase105"] = False
    zeile.setdefault("bearbeitbar", bearbeiten_erlaubt(session, benutzer, vorgang))
    return {"zeile": zeile, "hv_liste": lead_v2.handelsvertreter_liste(session),
            "standard": lead_v2.hv_standard_benutzer(session),
            "gesamt": hv_modul.gesamtsicht(session, benutzer)}


def auswahl_listen(session: Session) -> dict:
    """Dropdown-Inhalte: Außendienst, Innendienst (Leadmanager), Status (manuell
    setzbar), Kanäle. v31 (PLAN_LEAD_V5 Phase 156, app/lead_dropdowns.py): ad_wahl =
    angestellte AD ohne Handelsvertreter; liegt ein Lead bei einem HV, zeigt die Zeile
    stattdessen dessen Gruppe (ad_gruppen[hv_id], Template: ctx.ad_gruppen.get(v.ad_id)
    or ctx.ad_wahl); lm_wahl = nur Benutzer mit Häkchen „Leadmanager“ (nach Vorname)."""
    hv_ids = {b.id for b in lead_v2.handelsvertreter_liste(session)}
    ad_gruppen: dict[int, list] = {}
    for hv_id in hv_ids:
        gruppe = lead_dropdowns.hv_gruppe_fuer(session, hv_id)
        ids = lead_dropdowns.hv_gruppe_mitglieder(session, gruppe) if gruppe else [hv_id]
        if hv_id not in ids:
            ids = [hv_id] + ids
        namen = {b.id: b for b in session.query(Benutzer).filter(Benutzer.id.in_(ids))}
        ad_gruppen[hv_id] = [{"id": i, "name": namen[i].name, "hv": True}
                             for i in ids if i in namen and (namen[i].aktiv or i == hv_id)]
    logik = leadmanagement_logik.hole_logik()
    status = []
    gesehene_labels: dict[str, str] = {}
    for phase in LEAD_PHASEN:
        label, farbe = status_label(logik, phase)
        # v25: zwei Phasen dürfen dasselbe Label tragen („Kontaktiert“) – in den
        # Auswahlfeldern erscheint das Label nur einmal (erste Phase), die
        # Templates blenden Einträge mit doppelt=True aus, außer sie sind der
        # aktuelle Wert; gleiche = die anderen Phasen desselben Labels.
        status.append({"key": phase, "label": label, "farbe": farbe,
                       "setzbar": phase not in PHASEN_ABGELEITET,
                       "grund": PHASEN_MIT_GRUND.get(phase, ""),
                       "doppelt": label in gesehene_labels,
                       "gleiche": [p for p in LEAD_PHASEN
                                   if p != phase and status_label(logik, p)[0] == label]})
        gesehene_labels.setdefault(label, phase)
    return {
        "ad_wahl": lead_dropdowns.ad_auswahl_dicts(session),
        "ad_gruppen": ad_gruppen,
        "lm_wahl": [{"id": i, "name": n} for i, n, w in lead_dropdowns.leadmanager_auswahl(session) if w],
        "status_wahl": status,
        "kanaele": kern.kanal_werte(session),
        "sparten": list(sparten_modul.SPARTEN),           # v31 (Phase 157): Filter-Chips
        "grosskunde_farbe": grosskunde_farbe(session),     # v31 (Phase 153): Badge-Farbe
        # v35 (PLAN_LEAD_V6 Phase 186): Inline-Dropdowns Kanal (nach Häufigkeit, Vertrag K)
        # und Objektart (Blatt Objektarten), Langnamen der Sparten für das Interessen-Popover
        "kanal_wahl": kanal_auswahl(session),
        "objektarten": [{"code": c, "name": n} for c, n, _p in lead_v2.objektarten(session)],
        "sparten_lang": dict(sparten_modul.SPARTEN_LANG),
        # v37 (PLAN_LEAD_V7 Phase 199, Agent L3): Interessen-Popover (Plus) mit allen Häkchen
        # inkl. Merkmal „PV vorhanden“ (PVV) – Filter-Chip „Sparte“ ebenso; Merkmale tragen
        # ihren Langnamen als Badge-Titel
        "interessen": list(sparten_modul.INTERESSEN_ALLE),
        "interessen_lang": dict(sparten_modul.INTERESSEN_LANG),
        "interessen_merkmale": list(sparten_modul.INTERESSEN_MERKMALE),
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
                 + f" · Lead verloren (Board {board_label('terminiert')})"))
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
    Bestandsdialoge: Zurückgestellt Datum+Grund, Disqualifiziert (Key unqualifiziert) Grund,
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
        # v31 (PLAN_LEAD_V5 Phase 157): Label „Disqualifiziert“ (interner Key bleibt)
        kern.aktivitaet(session, vorgang.id, "status",
                        f"{praefix}Disqualifiziert: {grund}"
                        + (f" – {grund_text}" if grund_text else ""), benutzer=benutzer)
        session.flush()
        return True, f"Disqualifiziert ({grund})."
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
                and benutzer.basisrolle in ("admin", "innendienst"))
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
        datum = lead_v5.runden_5min(datum)   # v31 (Phase 158): Wiedervorlage im 5-Minuten-Raster
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
    if feld in INLINE_KARTEI_FELDER:
        # v35 (PLAN_LEAD_V6 Phase 186): Interessen, Vertriebskanal, Großkunde, Objektart,
        # Telefon, E-Mail – dieselbe Validierung und Aktivität wie das Autospeichern der
        # Kartei (lead_kartei.feld_speichern: Alt → Neu, kein Eintrag ohne Änderung)
        from app import lead_kartei
        kunde = session.get(Kunde, vorgang.kunde_id)
        if kunde is None:
            return False, "Kunde fehlt."
        kartei_feld = INLINE_KARTEI_FELDER[feld]
        if kartei_feld == "interesse" and isinstance(wert, str) and wert.strip().startswith("["):
            try:
                wert = json.loads(wert)
            except ValueError:
                pass
        erzwingen = (bool(daten.get("erzwingen")) and benutzer is not None
                     and benutzer.basisrolle in ("admin", "innendienst"))
        ergebnis = lead_kartei.feld_speichern(session, vorgang, kunde, kartei_feld, wert,
                                              benutzer=benutzer, erzwingen=erzwingen)
        if ergebnis["ok"] and ergebnis.get("geaendert") and kartei_feld in ("telefon", "email"):
            try:
                lead_kartei.vorschlaege_cache_leeren(vorgang.id)
            except Exception:   # noqa: BLE001
                pass
        return bool(ergebnis["ok"]), ergebnis["meldung"]
    if feld == "teilgenommen":
        # Infoabend (Phase 111): ja | nein | leer über lead_info (Aktivität je Lead)
        from app import lead_info
        gueltig, teil = lead_info.teilgenommen_lesen(wert)
        if not gueltig:
            return False, "Teilgenommen: Wert ja | nein | leer erwartet."
        return True, lead_info.teilgenommen_setzen(session, vorgang, teil, benutzer=benutzer)
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


def _ausschluss_kurz(meldung: str) -> str:
    """„Nicht möglich: Kanal „Enni“ wird nur vom Innendienst terminiert.“ →
    „Kanal Enni“; Quelle analog; sonst der Text ohne Präfix."""
    text = (meldung or "").strip()
    if text.startswith("Nicht möglich:"):
        text = text[len("Nicht möglich:"):].strip()
    m = re.match(r'^(Kanal|Quelle)\s+[„"]([^“"]+)[“"]', text)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return text.rstrip(".")


def _sammel_hv_verschieben(session: Session, vorgaenge: list, params: dict, benutzer) -> tuple:
    """v29 (PLAN_LEAD_V4 Phase 140): „An Handelsvertreter verschieben“ – Ziel
    „rene“ oder „simon“ (Parameter hv_gruppe_rene/_simon, erster Eintrag =
    Zielbenutzer). Je Lead lead_handelsvertreter.zuweisen (Sonderregel monday,
    Ausschlussliste F14 greift: übersprungen und im Ergebnis genannt, Aktivität
    „Zugewiesen an Y (vorher X)“ je Lead, keine Glocke). Liefert (ok, fehler,
    meldung) mit Meldung „3 verschoben, 1 übersprungen: Kanal Enni“."""
    from app import lead_handelsvertreter
    ziel_key = str(params.get("ziel") or "").strip().lower()
    ziel = lead_v2.hv_gruppe_ziel(session, ziel_key) if ziel_key in ("rene", "simon") else None
    if ziel is None:
        return 0, ["Ziel-Handelsvertreter nicht gesetzt (Lead-Einstellungen → HV-Gruppen)"], \
            "Nicht möglich: Ziel-Handelsvertreter nicht gesetzt (Lead-Einstellungen → HV-Gruppen)."
    # v33 (PLAN_V20 Phase 175): Ziel „Simons Gruppe“ statt eines festen Mitglieds – der Lead
    # hängt am Gruppenleiter (ad_id = Simon) mit Kennzeichen „noch nicht verteilt“ (Marker-
    # Aktivität lead_v2.hv_gruppe_offen_setzen), Simon verteilt über das Zuständigen-Dropdown
    gruppe = ziel_key == "simon"
    ziel_label = lead_v2.HV_GRUPPE_SIMON_NAME if gruppe else ziel.name
    ok, fehler, gruende = 0, [], []
    for v in vorgaenge:
        if v.ad_id == ziel.id:
            ok += 1          # liegt schon beim Ziel – zählt als verschoben, keine Zuweisungs-Aktivität
            if gruppe:
                lead_v2.hv_gruppe_offen_setzen(session, v, benutzer)
            continue
        meldung = lead_handelsvertreter.zuweisen(session, v, ziel.id, benutzer=benutzer,
                                                 erzwingen=False)
        if meldung.startswith("Zugewiesen an"):
            ok += 1
            if gruppe:
                lead_v2.hv_gruppe_offen_setzen(session, v, benutzer)
        else:
            kunde = session.get(Kunde, v.kunde_id)
            fehler.append(f"{kunde.anzeige_name if kunde else v.id}: {meldung}")
            kurz = _ausschluss_kurz(meldung)
            if kurz and kurz not in gruende:
                gruende.append(kurz)
    text = f"{ok} verschoben"
    if fehler:
        text += f", {len(fehler)} übersprungen: " + ", ".join(gruende[:5])
    text += f" (Ziel {ziel_label})."
    return ok, fehler, text


# --- v31 (PLAN_LEAD_V5 Phase 154): Archivieren, Wiederherstellen, Duplizieren -------------

def _sammel_archivieren(session: Session, vorgaenge: list, params: dict, benutzer) -> tuple:
    """„Archivieren“ (Lead-Sicht, app/lead_archiv.py): Leads mit aktivem Termin, offener
    Erfassung oder offenem Angebot werden übersprungen und gemeldet
    („2 archiviert, 1 übersprungen: aktiver Termin“); Aktivität je Lead."""
    archiviert, uebersprungen = lead_archiv.archivieren(session, list(vorgaenge), benutzer)
    fehler = [f"{vid}: {grund}" for vid, grund in uebersprungen]
    return len(archiviert), fehler, lead_archiv.meldung(archiviert, uebersprungen) + "."


def _sammel_wiederherstellen(session: Session, vorgaenge: list, params: dict, benutzer) -> tuple:
    """„Wiederherstellen“ aus der Archiv-Sicht (Filter-Chip „Archiv“)."""
    ok, gruende = 0, []
    for v in vorgaenge:
        erfolg, grund = lead_archiv.wiederherstellen(session, v, benutzer)
        if erfolg:
            ok += 1
        else:
            gruende.append(grund)
    text = f"{ok} wiederhergestellt"
    if gruende:
        text += f", {len(gruende)} übersprungen: " + ", ".join(dict.fromkeys(gruende))
    return ok, [g for g in gruende], text + "."


def vorgang_duplizieren(session: Session, vorgang: Vorgang, benutzer=None) -> Vorgang:
    """Sammelaktion „Duplizieren“ [ANNAHME: zweiter Vorgang für denselben Kunden, z. B.
    neue Anfrage nach Abschluss – nicht für Mehrobjekt-Fälle]: neuer Vorgang am selben
    Kunden mit Phase Neu, kopierten Objekten (vorgang_objekte), Interessen/Kanal (am
    Kunden), Zuständigen (Leadmanager, Außendienst), Anfragetext/Notiz, Quelle/Kampagne/
    UTM, Wunschzeiten, Koordinaten; OHNE Aktivitäten, Termine, Erfassungen, Angebote,
    Wiedervorlagen. kopie_von_id verweist auf den Ursprung, Aktivität in beiden; die
    Duplikatprüfung greift nicht (bewusste Kopie)."""
    jetzt = datetime.now()
    neu = Vorgang(
        kunde_id=vorgang.kunde_id, lead_phase="neu", eingang_am=jetzt,
        eingang_art=vorgang.eingang_art if vorgang.eingang_art and vorgang.eingang_art != "monday" else "manuell",
        quelle_id=vorgang.quelle_id, kampagne_id=vorgang.kampagne_id,
        utm_source=vorgang.utm_source, utm_medium=vorgang.utm_medium,
        utm_campaign=vorgang.utm_campaign, utm_content=vorgang.utm_content,
        anfrage_text=vorgang.anfrage_text, wunschzeiten=vorgang.wunschzeiten,
        leadmanager_id=vorgang.leadmanager_id, ad_id=vorgang.ad_id,
        lat=vorgang.lat, lon=vorgang.lon, geocode_status=vorgang.geocode_status,
        einwilligung_werbung=vorgang.einwilligung_werbung,
        einwilligung_werbung_am=vorgang.einwilligung_werbung_am,
        einwilligung_quelle=vorgang.einwilligung_quelle,
        demo=bool(vorgang.demo), kopie_von_id=vorgang.id, versuch_nr=0)
    session.add(neu)
    session.flush()
    # Objekte kopieren (Phase 153): gleiche Reihenfolge, Hauptobjekt bleibt Nr. 1
    objekte = (session.query(VorgangObjekt).filter(VorgangObjekt.vorgang_id == vorgang.id)
               .order_by(VorgangObjekt.reihenfolge, VorgangObjekt.id).all())
    if objekte:
        for o in objekte:
            session.add(VorgangObjekt(
                vorgang_id=neu.id, bezeichnung=o.bezeichnung, strasse=o.strasse, plz=o.plz,
                ort=o.ort, objektart=o.objektart, parteien=o.parteien, interessen=o.interessen,
                lat=o.lat, lon=o.lon, geocode_status=o.geocode_status,
                reihenfolge=o.reihenfolge, aktiv=o.aktiv,
                rechnung_abweichend=o.rechnung_abweichend, rechnung_name=o.rechnung_name,
                rechnung_strasse=o.rechnung_strasse, rechnung_plz=o.rechnung_plz,
                rechnung_ort=o.rechnung_ort))
    else:
        from app import objekte as objekte_modul
        objekte_modul.hauptobjekt(session, neu.id, anlegen=True)
    session.flush()
    kern.aktivitaet(session, neu.id, "system",
                    f"Kopie von Vorgang #{vorgang.id} (Sammelaktion Duplizieren)", benutzer=benutzer)
    kern.aktivitaet(session, vorgang.id, "system",
                    f"Dupliziert als Vorgang #{neu.id} (Sammelaktion Duplizieren)", benutzer=benutzer)
    session.flush()
    return neu


def _sammel_duplizieren(session: Session, vorgaenge: list, params: dict, benutzer) -> tuple:
    """„Duplizieren“: je markiertem Lead ein neuer Vorgang; Ergebnis mit Links (extra.kopien)."""
    kopien = []
    for v in vorgaenge:
        neu = vorgang_duplizieren(session, v, benutzer)
        kopien.append({"id": neu.id, "von": v.id})
    text = f"{len(kopien)} Kopie(n) angelegt – neue Vorgänge: " + ", ".join(f"#{k['id']}" for k in kopien) + "."
    return len(kopien), [], text, {"kopien": kopien}


# Registry: board → [(key, Titel, Handler(session, vorgaenge, params, benutzer)
# → (anzahl_ok, fehlerliste[, meldung[, extra]]))]. Weitere Aktionen (Phase 111: Infoabend)
# registrieren sich über sammelaktion_registrieren().
# v29 (Phase 140): „An Handelsvertreter verschieben“ auf Hauptboard und Deals;
# der Infoabend registriert denselben Handler (lead_info.sammelaktionen_registrieren).
# v31 (Phase 154): „Archivieren“, „Duplizieren“ (Hauptboard, Deals, Infoabend – der
# Infoabend registriert die Handler über lead_info) und „Wiederherstellen“ (nur in der
# Archiv-Sicht angeboten, sammelaktionen_fuer(board, archiv=True)).
SAMMELAKTION_HV = ("hv_verschieben", "An Handelsvertreter verschieben", _sammel_hv_verschieben)
SAMMELAKTION_ARCHIV = ("archivieren", "Archivieren", _sammel_archivieren)
SAMMELAKTION_DUPLIZIEREN = ("duplizieren", "Duplizieren", _sammel_duplizieren)
SAMMELAKTION_WIEDERHERSTELLEN = ("wiederherstellen", "Wiederherstellen", _sammel_wiederherstellen)
SAMMELAKTIONEN: dict[str, list] = {
    "hauptboard": [("status", "Status ändern", _sammel_status), SAMMELAKTION_HV,
                   SAMMELAKTION_ARCHIV, SAMMELAKTION_DUPLIZIEREN, SAMMELAKTION_WIEDERHERSTELLEN],
    "terminiert": [SAMMELAKTION_HV, SAMMELAKTION_ARCHIV, SAMMELAKTION_DUPLIZIEREN,
                   SAMMELAKTION_WIEDERHERSTELLEN],
}
# Sammelaktionen, die nur in der Archiv-Sicht angeboten werden
NUR_ARCHIV = ("wiederherstellen",)


def sammelaktion_registrieren(board: str, key: str, titel: str, handler) -> None:
    liste = SAMMELAKTIONEN.setdefault(board, [])
    liste[:] = [e for e in liste if e[0] != key]
    liste.append((key, titel, handler))


def sammelaktionen_fuer(board: str, archiv: bool = False) -> list[dict]:
    """Angebotene Sammelaktionen: in der Archiv-Sicht nur „Wiederherstellen“, sonst alle
    übrigen."""
    return [{"key": k, "titel": t} for k, t, _ in SAMMELAKTIONEN.get(board, [])
            if (k in NUR_ARCHIV) == bool(archiv)]


def sammelaktion_ausfuehren_voll(session: Session, benutzer, board: str, aktion: str,
                                 ids: list, params: dict | None = None) -> tuple[bool, str, dict]:
    """Führt eine registrierte Aktion je Lead aus (Handler schreibt je Lead
    eine Aktivität); (ok, meldung, extra) – extra z. B. {"kopien": [...]} beim
    Duplizieren (Links in der Ergebnis-Meldung). Handelsvertreter/AD: nicht erlaubt."""
    params = params or {}
    if benutzer is None or benutzer.basisrolle == "aussendienst":
        return False, "Sammelaktionen sind für den Außendienst nicht freigegeben.", {}
    eintrag = next((e for e in SAMMELAKTIONEN.get(board, []) if e[0] == aktion), None)
    if eintrag is None:
        return False, f"Sammelaktion „{aktion}“ gibt es auf diesem Board nicht.", {}
    sauber = []
    for wert in ids or []:
        try:
            sauber.append(int(wert))
        except (TypeError, ValueError):
            continue
    if not sauber:
        return False, "Keine Leads markiert.", {}
    vorgaenge = [v for v in session.query(Vorgang).filter(Vorgang.id.in_(sauber))
                 if lead_v2.zugriff_erlaubt(session, benutzer, v)]
    if not vorgaenge:
        return False, "Keine zugänglichen Leads markiert.", {}
    ergebnis = eintrag[2](session, vorgaenge, params, benutzer)
    session.flush()
    extra = ergebnis[3] if len(ergebnis) >= 4 and isinstance(ergebnis[3], dict) else {}
    # v29: Handler dürfen eine eigene Meldung liefern (ok, fehler, meldung)
    if len(ergebnis) >= 3 and ergebnis[2]:
        ok, fehler = ergebnis[0], ergebnis[1]
        return ok > 0, f"{eintrag[1]}: {ergebnis[2]}", extra
    ok, fehler = ergebnis[0], ergebnis[1]
    meldung = f"{eintrag[1]}: {ok} von {len(vorgaenge)} Leads geändert."
    if fehler:
        meldung += f" {len(fehler)} übersprungen: " + "; ".join(fehler[:5])
        if len(fehler) > 5:
            meldung += " …"
    return ok > 0, meldung, extra


def sammelaktion_ausfuehren(session: Session, benutzer, board: str, aktion: str,
                            ids: list, params: dict | None = None) -> tuple[bool, str]:
    """Vertrag v23/v29 (Infoabend, Tests): (ok, meldung) – Rest wie sammelaktion_ausfuehren_voll."""
    ok, meldung, _extra = sammelaktion_ausfuehren_voll(session, benutzer, board, aktion, ids, params)
    return ok, meldung


# --- Reiter Kontaktiert (H7) + Rufnummernsuche (D3) ---------------------------------------

def telefon_treffer(session: Session, nummer: str, benutzer=None) -> list[dict]:
    """Alle Kunden/Vorgänge und monday-Leads zu dieser Nummer. v31 (PLAN_LEAD_V5
    Phase 158, Endziffern-Suche): ab 3 Ziffern – Treffer, deren normalisierte Nummer
    (E.164) mit der Folge ENDET, stehen zuerst, danach „enthält“; Schreibweise egal
    (lead_anrufliste.rufnummer_suchen). Treffer verlinken auf die Kartei; archivierte
    Leads sind markiert (archiviert=True)."""
    from app import lead_anrufliste
    hv = lead_v2.ist_handelsvertreter(session, benutzer)
    ergebnis = lead_anrufliste.rufnummer_suchen(
        session, nummer, nur_ad_id=benutzer.id if hv and benutzer is not None else None)
    if ergebnis["zu_kurz"]:
        return []
    treffer = []
    for t in ergebnis["treffer"]:
        kunde, v = t["kunde"], t["vorgang"]
        if hv and v is None:
            continue
        treffer.append({
            "art": t["herkunft"], "kunde": kunde, "vorgang": v, "lead": t.get("lead"),
            "name": kunde.anzeige_name, "ort": kunde.ort or "", "telefon": kunde.telefon,
            "phase": v.lead_phase if v else None,
            "link": f"/lead-management/lead/{v.id}" if v else f"/kunden/{kunde.id}",
            "anzahl_vorgaenge": len(t["vorgaenge"]),
            "endet_mit": t.get("endet_mit", False),
            "archiviert": bool(v is not None and lead_archiv.ist_archiviert(v)),
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
    # Nummer im Suchfeld erkennt sich selbst – v31 (Phase 158): ab 3 Ziffern (Endziffern)
    if not telefon and q and len(re.sub(r"\D", "", q)) >= 3 and not re.search(r"[A-Za-zÄÖÜäöü]", q):
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
    # v31 (Phase 154): Kontaktversuche archivierter Leads nicht in der Liste
    archivierte = {v.id for v in session.query(Vorgang.id).filter(Vorgang.archiviert_am.isnot(None))}
    if archivierte:
        abfrage = abfrage.filter(~LeadAktivitaet.vorgang_id.in_(archivierte))
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
            # v35 (Phase 186): EINE Suchleiste – Name, Ort, PLZ, E-Mail, Notiz, Ergebnis, Benutzer
            # (reine Ziffernfolgen ab 3 Ziffern laufen als Rufnummernsuche, siehe oben)
            text = " ".join((kunde.vorname or "", kunde.nachname or "", kunde.firma or "",
                             kunde.ort or "", kunde.plz or "", kunde.email or "",
                             kunde.telefon or "", ergebnis_name,
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


# --- v33 (PLAN_V20 Phase 174): Migration ------------------------------------------------

def migration_v33_tabellen(session: Session) -> list[str]:
    """Hook aus migrate.py (idempotent, zweiter Lauf still): nichts Zwingendes – die neuen
    Board-Keys entstehen erst beim ersten Speichern je Nutzer. Bereinigt gespeicherte
    Konfigurationen der Angebotstool-Tabellen um Keys, die kein Katalog kennt (z. B. aus
    einer Vorabversion), und entfernt die v32-Einstellung `leads_darstellung` nicht
    (gehört zu Phase 173/M). Liefert Meldungen nur bei Änderungen."""
    from app.models import BenutzerEinstellung
    meldungen: list[str] = []
    bekannt = {board: {k for k, _, _ in KATALOGE[board]} for board in TABELLEN_BOARDS}
    for zeile in session.query(BenutzerEinstellung).filter(BenutzerEinstellung.key == EINSTELLUNG_KEY):
        try:
            alle = json.loads(zeile.wert or "{}")
        except ValueError:
            continue
        if not isinstance(alle, dict):
            continue
        geaendert = False
        for board, keys in bekannt.items():
            konfig = alle.get(board)
            if not isinstance(konfig, dict):
                continue
            spalten = konfig.get("spalten")
            if isinstance(spalten, list):
                bereinigt = [sp for sp in spalten
                             if not (isinstance(sp, dict) and sp.get("key") not in keys)]
                if len(bereinigt) != len(spalten):
                    konfig["spalten"] = bereinigt
                    geaendert = True
            sort = konfig.get("sort")
            if isinstance(sort, dict) and sort.get("key") not in keys:
                konfig["sort"] = None
                geaendert = True
        if geaendert:
            zeile.wert = json.dumps(alle, ensure_ascii=False)
            meldungen.append(f"Tabellen (v33): Spaltenkonfiguration von Benutzer {zeile.benutzer_id} "
                             "um unbekannte Spalten bereinigt")
    if meldungen:
        session.flush()
    return meldungen


# --- v35 (PLAN_LEAD_V6 Phase 186): gespeicherte Filter je Nutzer und Board ------------------
# Ablage benutzer_einstellungen Key boards_filter:
#   {"<board>": {"filter": [{id, name, werte, erstellt_am, geteilt_id?}], "standard_id": "<id>|null"}}
# „für alle freigeben“ (Innendienst/Admin): schreibgeschützte Kopie im globalen Eintrag
# (benutzer_id 0, Key boards_filter_geteilt):
#   {"<board>": {"filter": [{id, name, werte, von, von_name, erstellt_am}]}}
# werte = Formularwerte des Filterblocks (q, status, kanal, sparte, ad_id, leadmanager_id,
# meine, grosskunde, archiviert, archiv, gruppe, …), dazu sort {key, richtung} und
# gruppen_zu [Gruppen-Keys, die eingeklappt sind]. Keine Kundendaten, nur Filterwerte.

_FILTER_KEY_MUSTER = re.compile(r"^[a-z0-9_]{1,40}$")


class FilterWerte(dict):
    """Gespeicherte Filterwerte als Query-Ersatz (get/getlist/multi_items/keys wie
    starlette.QueryParams) – für filter_aus_query der Boards, des Infoabends und der HV-Ansicht."""

    def get(self, name, standard=None):   # type: ignore[override]
        wert = super().get(name, None)
        if wert is None:
            return standard
        if isinstance(wert, list):
            return wert[0] if wert else standard
        return wert

    def getlist(self, name) -> list:
        wert = super().get(name, None)
        if wert is None:
            return []
        return list(wert) if isinstance(wert, list) else [wert]

    def multi_items(self) -> list:
        items = []
        for k, v in super().items():
            for teil in (v if isinstance(v, list) else [v]):
                items.append((k, str(teil)))
        return items


def _filter_id() -> str:
    return hashlib.md5(f"{datetime.now().isoformat()}{id(object())}".encode("utf-8")).hexdigest()[:10]


def werte_normieren(werte) -> dict:
    """Filterwerte für die Ablage bereinigen: nur Schlüssel [a-z0-9_], Werte als Text (≤ 200
    Zeichen) oder Textlisten (≤ 20), `sort` als {key, richtung}, `gruppen_zu` als Liste; leere
    Werte und neutrale Parameter (meldung, seite, …) fallen weg."""
    sauber: dict = {}
    if not isinstance(werte, dict):
        return sauber
    for key, wert in werte.items():
        key = str(key or "").strip().lower()
        if not _FILTER_KEY_MUSTER.match(key) or key in FILTER_NEUTRALE_PARAMETER:
            continue
        if key == "sort":
            if isinstance(wert, dict) and str(wert.get("key") or "").strip():
                sauber["sort"] = {"key": str(wert["key"]).strip()[:40],
                                  "richtung": "ab" if str(wert.get("richtung", "auf")) == "ab" else "auf"}
            continue
        if key == "gruppen_zu":
            liste = wert if isinstance(wert, (list, tuple)) else [wert]
            keys = [str(k).strip()[:40] for k in liste if str(k).strip()]
            if keys:
                sauber["gruppen_zu"] = keys[:40]
            continue
        if isinstance(wert, bool):
            wert = "1" if wert else ""
        if isinstance(wert, (list, tuple)):
            texte = [str(t).strip()[:200] for t in wert if str(t).strip()][:20]
            if texte:
                sauber[key] = texte if len(texte) > 1 else texte[0]
            continue
        text = str(wert if wert is not None else "").strip()[:200]
        if text:
            sauber[key] = text
    return sauber


def _filter_ablage(session: Session, benutzer_id: int, key: str) -> dict:
    alle = lead_v2.einstellung_holen(session, benutzer_id, key, {}) or {}
    return alle if isinstance(alle, dict) else {}


def _filter_board(ablage: dict, board: str) -> dict:
    eintrag = ablage.get(board)
    if not isinstance(eintrag, dict):
        eintrag = {"filter": [], "standard_id": None}
        ablage[board] = eintrag
    if not isinstance(eintrag.get("filter"), list):
        eintrag["filter"] = []
    return eintrag


def filter_freigabe_erlaubt(benutzer) -> bool:
    """„Für alle freigeben“ – Innendienst und Admin (Plan 186, bestätigt 15.10.2026)."""
    return benutzer is not None and getattr(benutzer, "basisrolle", "") in ("admin", "innendienst")


def filter_liste(session: Session, benutzer, board: str) -> list[dict]:
    """Gespeicherte Filter des Nutzers (bearbeitbar) plus die für alle freigegebenen
    (schreibgeschützt, Kennzeichen geteilt=True, von_name); je Eintrag standard=True, wenn er
    der Standardfilter des Nutzers beim Öffnen ist."""
    benutzer_id = _benutzer_id(benutzer)
    eigene = _filter_board(_filter_ablage(session, benutzer_id, FILTER_KEY), board)
    geteilt = _filter_board(_filter_ablage(session, FILTER_GLOBAL_BENUTZER, FILTER_GETEILT_KEY), board)
    standard_id = eigene.get("standard_id")
    liste = []
    for f in eigene["filter"]:
        if not isinstance(f, dict) or not f.get("id"):
            continue
        liste.append({"id": str(f["id"]), "name": str(f.get("name") or "")[:FILTER_NAME_MAX],
                      "werte": werte_normieren(f.get("werte")), "geteilt": False,
                      "geteilt_id": f.get("geteilt_id"), "von": benutzer_id, "von_name": "",
                      "standard": str(f["id"]) == str(standard_id), "loeschbar": True,
                      "erstellt_am": f.get("erstellt_am", "")})
    eigene_geteilt = {f.get("geteilt_id") for f in eigene["filter"] if isinstance(f, dict)}
    for f in geteilt["filter"]:
        if not isinstance(f, dict) or not f.get("id") or f["id"] in eigene_geteilt:
            continue
        liste.append({"id": str(f["id"]), "name": str(f.get("name") or "")[:FILTER_NAME_MAX],
                      "werte": werte_normieren(f.get("werte")), "geteilt": True, "geteilt_id": None,
                      "von": f.get("von"), "von_name": str(f.get("von_name") or ""),
                      "standard": str(f["id"]) == str(standard_id),
                      "loeschbar": bool(benutzer is not None and (
                          f.get("von") == benutzer_id or getattr(benutzer, "basisrolle", "") == "admin")),
                      "erstellt_am": f.get("erstellt_am", "")})
    return liste


def filter_kontext(session: Session, benutzer, board: str) -> dict:
    """Kontext des Makros filter_speicher (Filterleiste): Liste, Standard-ID, Freigaberecht."""
    liste = filter_liste(session, benutzer, board)
    return {"liste": liste, "standard_id": next((f["id"] for f in liste if f["standard"]), None),
            "darf_freigeben": filter_freigabe_erlaubt(benutzer), "board": board}


def filter_speichern(session: Session, benutzer, board: str, name: str, werte,
                     standard: bool = False, filter_id: str | None = None) -> tuple[dict | None, str]:
    """Neuen Filter anlegen oder (mit filter_id) einen eigenen überschreiben; standard=True
    macht ihn zum Standardfilter beim Öffnen. Liefert (Eintrag, Meldung)."""
    benutzer_id = _benutzer_id(benutzer)
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:FILTER_NAME_MAX]
    if not name:
        return None, "Bitte einen Namen für den Filter eingeben."
    if not board_bekannt(board):
        return None, "Unbekanntes Board."
    ablage = _filter_ablage(session, benutzer_id, FILTER_KEY)
    eintrag = _filter_board(ablage, board)
    sauber = werte_normieren(werte)
    ziel = None
    if filter_id:
        ziel = next((f for f in eintrag["filter"] if isinstance(f, dict) and str(f.get("id")) == str(filter_id)), None)
        if ziel is None:
            return None, "Filter nicht gefunden (freigegebene Filter anderer Nutzer sind schreibgeschützt)."
        ziel["name"], ziel["werte"] = name, sauber
    else:
        if len(eintrag["filter"]) >= FILTER_MAX_JE_BOARD:
            return None, f"Höchstens {FILTER_MAX_JE_BOARD} Filter je Board."
        # gleicher Name → überschreiben statt doppelt anlegen
        ziel = next((f for f in eintrag["filter"] if isinstance(f, dict)
                     and str(f.get("name") or "").lower() == name.lower()), None)
        if ziel is None:
            ziel = {"id": _filter_id(), "name": name, "werte": sauber,
                    "erstellt_am": datetime.now().strftime("%Y-%m-%d %H:%M")}
            eintrag["filter"].append(ziel)
        else:
            ziel["werte"] = sauber
    if standard:
        eintrag["standard_id"] = ziel["id"]
    elif eintrag.get("standard_id") == ziel["id"] and standard is False and filter_id is None:
        pass   # bestehender Standard bleibt, wenn nur überschrieben wird
    lead_v2.einstellung_setzen(session, benutzer_id, FILTER_KEY, ablage)
    return ({**ziel, "geteilt": False, "standard": eintrag.get("standard_id") == ziel["id"]},
            f"Filter „{name}“ gespeichert" + (" – Standard beim Öffnen." if standard else "."))


def filter_umbenennen(session: Session, benutzer, board: str, filter_id: str, name: str) -> tuple[bool, str]:
    benutzer_id = _benutzer_id(benutzer)
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:FILTER_NAME_MAX]
    if not name:
        return False, "Bitte einen Namen eingeben."
    ablage = _filter_ablage(session, benutzer_id, FILTER_KEY)
    eintrag = _filter_board(ablage, board)
    ziel = next((f for f in eintrag["filter"] if isinstance(f, dict) and str(f.get("id")) == str(filter_id)), None)
    if ziel is None:
        return False, "Filter nicht gefunden (freigegebene Filter anderer Nutzer sind schreibgeschützt)."
    ziel["name"] = name
    lead_v2.einstellung_setzen(session, benutzer_id, FILTER_KEY, ablage)
    return True, f"Filter in „{name}“ umbenannt."


def filter_loeschen(session: Session, benutzer, board: str, filter_id: str) -> tuple[bool, str]:
    """Eigenen Filter löschen (eine Freigabe dieses Filters bleibt für die anderen bestehen,
    bis sie über „Freigabe entfernen“ zurückgenommen wird [ANNAHME])."""
    benutzer_id = _benutzer_id(benutzer)
    ablage = _filter_ablage(session, benutzer_id, FILTER_KEY)
    eintrag = _filter_board(ablage, board)
    vorher = len(eintrag["filter"])
    eintrag["filter"] = [f for f in eintrag["filter"]
                         if not (isinstance(f, dict) and str(f.get("id")) == str(filter_id))]
    if len(eintrag["filter"]) == vorher:
        # freigegebener Filter? nur Ersteller/Admin über filter_freigabe_entfernen
        return filter_freigabe_entfernen(session, benutzer, board, filter_id)
    if str(eintrag.get("standard_id")) == str(filter_id):
        eintrag["standard_id"] = None
    lead_v2.einstellung_setzen(session, benutzer_id, FILTER_KEY, ablage)
    return True, "Filter gelöscht."


def filter_standard_setzen(session: Session, benutzer, board: str, filter_id: str | None) -> tuple[bool, str]:
    """Standardfilter beim Öffnen setzen (eigener oder freigegebener Filter) bzw. aufheben (None)."""
    benutzer_id = _benutzer_id(benutzer)
    ablage = _filter_ablage(session, benutzer_id, FILTER_KEY)
    eintrag = _filter_board(ablage, board)
    if filter_id:
        bekannt = {f["id"] for f in filter_liste(session, benutzer, board)}
        if str(filter_id) not in bekannt:
            return False, "Filter nicht gefunden."
        eintrag["standard_id"] = str(filter_id)
        meldung = "Standard beim Öffnen gesetzt."
    else:
        eintrag["standard_id"] = None
        meldung = "Kein Standardfilter mehr – das Board öffnet ungefiltert."
    lead_v2.einstellung_setzen(session, benutzer_id, FILTER_KEY, ablage)
    return True, meldung


def filter_freigeben(session: Session, benutzer, board: str, filter_id: str) -> tuple[bool, str]:
    """Innendienst/Admin: eigenen Filter für alle freigeben – Kopie im globalen Eintrag
    (schreibgeschützt bei den anderen Nutzern), eigener Eintrag merkt geteilt_id."""
    if not filter_freigabe_erlaubt(benutzer):
        return False, "Freigeben dürfen nur Innendienst und Admin."
    benutzer_id = _benutzer_id(benutzer)
    ablage = _filter_ablage(session, benutzer_id, FILTER_KEY)
    eintrag = _filter_board(ablage, board)
    quelle = next((f for f in eintrag["filter"] if isinstance(f, dict) and str(f.get("id")) == str(filter_id)), None)
    if quelle is None:
        return False, "Nur eigene Filter lassen sich freigeben."
    global_ablage = _filter_ablage(session, FILTER_GLOBAL_BENUTZER, FILTER_GETEILT_KEY)
    global_eintrag = _filter_board(global_ablage, board)
    geteilt = next((f for f in global_eintrag["filter"] if isinstance(f, dict)
                    and str(f.get("id")) == str(quelle.get("geteilt_id"))), None)
    if geteilt is None:
        geteilt = {"id": _filter_id(), "von": benutzer_id,
                   "erstellt_am": datetime.now().strftime("%Y-%m-%d %H:%M")}
        global_eintrag["filter"].append(geteilt)
    geteilt.update({"name": quelle.get("name", ""), "werte": werte_normieren(quelle.get("werte")),
                    "von_name": getattr(benutzer, "name", "") or ""})
    quelle["geteilt_id"] = geteilt["id"]
    lead_v2.einstellung_setzen(session, FILTER_GLOBAL_BENUTZER, FILTER_GETEILT_KEY, global_ablage)
    lead_v2.einstellung_setzen(session, benutzer_id, FILTER_KEY, ablage)
    return True, f"Filter „{quelle.get('name', '')}“ für alle freigegeben."


def filter_freigabe_entfernen(session: Session, benutzer, board: str, filter_id: str) -> tuple[bool, str]:
    """Freigabe zurücknehmen – Ersteller oder Admin; filter_id = ID der Freigabe oder des
    eigenen Filters, der freigegeben wurde."""
    benutzer_id = _benutzer_id(benutzer)
    global_ablage = _filter_ablage(session, FILTER_GLOBAL_BENUTZER, FILTER_GETEILT_KEY)
    global_eintrag = _filter_board(global_ablage, board)
    ablage = _filter_ablage(session, benutzer_id, FILTER_KEY)
    eintrag = _filter_board(ablage, board)
    eigener = next((f for f in eintrag["filter"] if isinstance(f, dict) and str(f.get("id")) == str(filter_id)), None)
    ziel_id = str(eigener.get("geteilt_id")) if eigener and eigener.get("geteilt_id") else str(filter_id)
    ziel = next((f for f in global_eintrag["filter"] if isinstance(f, dict) and str(f.get("id")) == ziel_id), None)
    if ziel is None:
        return False, "Freigabe nicht gefunden."
    if not (ziel.get("von") == benutzer_id or getattr(benutzer, "basisrolle", "") == "admin"):
        return False, "Freigabe zurücknehmen darf nur der Ersteller oder ein Admin."
    global_eintrag["filter"] = [f for f in global_eintrag["filter"] if f is not ziel]
    lead_v2.einstellung_setzen(session, FILTER_GLOBAL_BENUTZER, FILTER_GETEILT_KEY, global_ablage)
    # Freigabe-Verweis beim Ersteller lösen – auch wenn ein Admin die Freigabe entfernt
    ersteller_id = ziel.get("von") if isinstance(ziel.get("von"), int) else benutzer_id
    for nutzer_id in {benutzer_id, ersteller_id}:
        nutzer_ablage = ablage if nutzer_id == benutzer_id else _filter_ablage(session, nutzer_id, FILTER_KEY)
        nutzer_eintrag = _filter_board(nutzer_ablage, board)
        geaendert = False
        for f in nutzer_eintrag["filter"]:
            if isinstance(f, dict) and str(f.get("geteilt_id")) == ziel_id:
                f.pop("geteilt_id", None)
                geaendert = True
        if geaendert:
            lead_v2.einstellung_setzen(session, nutzer_id, FILTER_KEY, nutzer_ablage)
    return True, "Freigabe entfernt."


def standard_filter(session: Session, benutzer, board: str) -> dict | None:
    """Der Standardfilter des Nutzers für dieses Board (eigener oder freigegebener) oder None."""
    return next((f for f in filter_liste(session, benutzer, board) if f["standard"]), None)


def filter_query(query_params, session: Session, benutzer, board: str):
    """Query für filter_aus_query: trägt die Anfrage Filterparameter (alles außer
    FILTER_NEUTRALE_PARAMETER) oder ?filter=0, gilt die URL; sonst greift der Standardfilter
    des Nutzers beim Öffnen (Plan 186: „URL-Parameter überschreiben ihn“).
    Liefert (query, aktiver_filter | None)."""
    try:
        keys = [k for k, _ in query_params.multi_items()]
    except AttributeError:
        keys = list(query_params.keys())
    if any(k not in FILTER_NEUTRALE_PARAMETER for k in keys) or query_params.get("filter", "") == "0":
        return query_params, None
    standard = standard_filter(session, benutzer, board)
    if standard is None or not standard.get("werte"):
        return query_params, None
    return FilterWerte(standard["werte"]), standard


# --- v35 (Phase 186): Sofortsuche – Fragmente einer gerenderten Seite ---------------------

class _ZielParser(HTMLParser):
    """Findet Elemente mit data-lm-sofort-ziel="<name>" und ihre Zeichen-Spannen im HTML."""

    def __init__(self, html: str):
        super().__init__(convert_charrefs=False)
        self.html = html
        self.zeilen_start = [0]
        for i, zeichen in enumerate(html):
            if zeichen == "\n":
                self.zeilen_start.append(i + 1)
        self.offen: list[dict] = []
        self.ziele: dict[str, str] = {}

    def _pos(self) -> int:
        zeile, spalte = self.getpos()
        return self.zeilen_start[zeile - 1] + spalte

    def handle_starttag(self, tag, attrs):
        name = next((v for k, v in attrs if k == "data-lm-sofort-ziel"), None)
        for eintrag in self.offen:
            if eintrag["tag"] == tag:
                eintrag["tiefe"] += 1
        if name:
            self.offen.append({"tag": tag, "name": name, "tiefe": 1, "start": self._pos()})

    def handle_startendtag(self, tag, attrs):
        return   # <x/> – keine Tiefe

    def handle_endtag(self, tag):
        for eintrag in reversed(self.offen):
            if eintrag["tag"] == tag:
                eintrag["tiefe"] -= 1
                if eintrag["tiefe"] == 0:
                    ende = self.html.find(">", self._pos())
                    self.ziele.setdefault(eintrag["name"], self.html[eintrag["start"]:ende + 1])
                    self.offen.remove(eintrag)
                break


def fragment_ziele(html: str) -> dict[str, str]:
    """Alle Bereiche data-lm-sofort-ziel="<name>" einer gerenderten Seite als {name: html}
    (äußeres Element eingeschlossen) – Antwort der Boards bei ?fragment=1 (JSON),
    lm_sofort.js tauscht die Inhalte ohne Seitenneuladen."""
    parser = _ZielParser(html)
    parser.feed(html)
    parser.close()
    return parser.ziele
