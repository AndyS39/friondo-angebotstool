# v27 (PLAN_V17 Phase 130): CSV-Import von Benutzern – reine Funktionen
# (Lesen, Prüfen, Start-PINs, Anlegen). Die Routen liegen in
# app/routers/benutzer.py (/benutzer/import: Vorschau → Ausführen).
#
# Spalten: Name;Rolle;E-Mail;Team;Vertriebskanal – Trennzeichen ; oder ,
# (an der Kopfzeile erkannt), UTF-8 mit/ohne BOM (Ersatz: Windows-1252, wie
# Excel „CSV (Trennzeichen-getrennt)“ schreibt), Kopfzeile Pflicht; Team und
# Vertriebskanal optional. Die Vorschau-Daten wandern als CSV-Text im Formular
# zwischen den beiden POSTs – nichts wird in der Datenbank zwischengespeichert.
# Start-PINs: zufällige Ziffern, die auth.pin_regel_pruefen bestehen; sie
# werden nur EINMAL auf der Ergebnisseite angezeigt (nicht gespeichert, nicht
# protokolliert) – jeder importierte Benutzer muss sie beim ersten Login ändern.

import csv
import io
import secrets
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app import auth

SPALTEN = ("Name", "Rolle", "E-Mail", "Team", "Vertriebskanal")
PFLICHTSPALTEN = ("Name", "Rolle", "E-Mail")
# Überschriften werden tolerant erkannt (Groß/Klein, Bindestrich, Varianten)
_SPALTEN_ALIAS = {
    "name": "Name", "benutzer": "Name", "benutzername": "Name",
    "rolle": "Rolle", "role": "Rolle",
    "e-mail": "E-Mail", "email": "E-Mail", "mail": "E-Mail", "e_mail": "E-Mail",
    "e-mail-adresse": "E-Mail",
    "team": "Team", "montageteam": "Team",
    "vertriebskanal": "Vertriebskanal", "kanal": "Vertriebskanal",
}
MAX_ZEILEN = 500
START_PIN_LAENGE = 6
BEISPIEL_CSV = (
    "Name;Rolle;E-Mail;Team;Vertriebskanal\r\n"
    "Max Mustermann;Außendienst;max.mustermann@friondo.de;;Enni\r\n"
    "Erika Beispiel;Innendienst;erika.beispiel@friondo.de;;\r\n"
    "Monteur Eins;Montage;;Montageteam 1;\r\n"
    "Petra Planung;Projektierung;petra.planung@friondo.de;;\r\n"
)


@dataclass
class Zeile:
    """Eine Datenzeile der CSV mit Prüfergebnis (fehler leer = anlegbar)."""
    nr: int                      # Zeilennummer in der Datei (Kopfzeile = 1)
    name: str = ""
    rolle: str = ""              # Rollenschlüssel (aussendienst, …) nach Zuordnung
    rolle_roh: str = ""          # Text aus der Datei
    email: str = ""
    team: str = ""
    kanal: str = ""
    team_id: int | None = None
    fehler: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.fehler

    @property
    def rolle_name(self) -> str:
        from app.routers.benutzer import ROLLEN_NAMEN
        return ROLLEN_NAMEN.get(self.rolle, self.rolle_roh or self.rolle)


# --- Lesen ----------------------------------------------------------------------------

def text_dekodieren(inhalt: bytes) -> str:
    """UTF-8 (mit/ohne BOM); schlägt das fehl, Windows-1252 (Excel-Export)."""
    try:
        return inhalt.decode("utf-8-sig")
    except UnicodeDecodeError:
        return inhalt.decode("cp1252", errors="replace")


def trennzeichen_erkennen(kopfzeile: str) -> str:
    """; oder , – das häufigere Zeichen der Kopfzeile gewinnt (Standard ;)."""
    return "," if kopfzeile.count(",") > kopfzeile.count(";") else ";"


def _spalte_zuordnen(ueberschrift: str) -> str | None:
    schluessel = (ueberschrift or "").strip().lstrip("﻿").strip().lower()
    schluessel = schluessel.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return _SPALTEN_ALIAS.get(schluessel)


def csv_lesen(text: str) -> tuple[list[Zeile], list[str]]:
    """CSV-Text → Datenzeilen und Datei-Fehler (fehlende Kopfzeile/Spalten,
    zu viele Zeilen). Leere Zeilen werden übersprungen."""
    text = (text or "").lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    zeilen_text = [z for z in text.split("\n")]
    while zeilen_text and not zeilen_text[0].strip():
        zeilen_text.pop(0)
    if not zeilen_text:
        return [], ["Die Datei ist leer – erwartet wird eine Kopfzeile "
                    "„Name;Rolle;E-Mail;Team;Vertriebskanal“ und je Benutzer eine Zeile."]
    trenner = trennzeichen_erkennen(zeilen_text[0])
    leser = csv.reader(io.StringIO("\n".join(zeilen_text)), delimiter=trenner)
    try:
        kopf = next(leser)
    except (StopIteration, csv.Error):
        return [], ["Die Kopfzeile konnte nicht gelesen werden."]
    zuordnung: dict[int, str] = {}
    for index, ueberschrift in enumerate(kopf):
        name = _spalte_zuordnen(ueberschrift)
        if name and name not in zuordnung.values():
            zuordnung[index] = name
    fehlend = [s for s in PFLICHTSPALTEN if s not in zuordnung.values()]
    if fehlend:
        gefunden = ", ".join(k.strip() for k in kopf if k.strip()) or "–"
        return [], [f"Kopfzeile unvollständig – es fehlt: {', '.join(fehlend)}. "
                    f"Erwartet: {';'.join(SPALTEN)} (gefunden: {gefunden})."]
    zeilen: list[Zeile] = []
    fehler: list[str] = []
    nr = 1
    try:
        for felder in leser:
            nr += 1
            if not any((f or "").strip() for f in felder):
                continue
            werte = {name: (felder[i].strip() if i < len(felder) else "")
                     for i, name in zuordnung.items()}
            zeilen.append(Zeile(nr=nr, name=werte.get("Name", ""),
                                rolle_roh=werte.get("Rolle", ""),
                                email=werte.get("E-Mail", "").lower(),
                                team=werte.get("Team", ""),
                                kanal=werte.get("Vertriebskanal", "")))
    except csv.Error as problem:
        fehler.append(f"Die Datei konnte ab Zeile {nr} nicht gelesen werden ({problem}).")
    if not zeilen and not fehler:
        fehler.append("Die Datei enthält außer der Kopfzeile keine Benutzerzeile.")
    if len(zeilen) > MAX_ZEILEN:
        fehler.append(f"Höchstens {MAX_ZEILEN} Benutzer je Import – die Datei enthält "
                      f"{len(zeilen)} Zeilen.")
    return zeilen, fehler


# --- Prüfen ---------------------------------------------------------------------------

def rolle_zuordnen(text: str) -> str | None:
    """Rollenschlüssel oder sprechender Name (Groß/Klein egal) → Schlüssel."""
    from app.routers.benutzer import ROLLEN, ROLLEN_NAMEN
    wert = (text or "").strip().lower()
    if not wert:
        return None
    for schluessel in ROLLEN:
        if wert in (schluessel, ROLLEN_NAMEN.get(schluessel, "").lower()):
            return schluessel
    # Schreibvarianten: „Aussendienst“, „Lead Management“, „Leadmanagement“
    vereinfacht = wert.replace("ß", "ss").replace(" ", "").replace("-", "")
    for schluessel in ROLLEN:
        if vereinfacht == ROLLEN_NAMEN.get(schluessel, "").lower().replace("-", "").replace(" ", ""):
            return schluessel
    return None


def kanal_werte_import(session: Session) -> list[str]:
    """Erlaubte Vertriebskanäle (wie im AD-Profil: ohne „Standard“)."""
    from app import leadmanagement
    return [k for k in leadmanagement.kanal_werte(session) if k.lower() != "standard"]


def pruefen(session: Session, zeilen: list[Zeile]) -> list[Zeile]:
    """Prüft jede Zeile und trägt die Fehlertexte ein: Name eindeutig (Datei
    und Datenbank), Rolle bekannt, E-Mail-Regel wie in der Benutzerverwaltung
    (Außendienst Pflicht), Team muss existieren, Vertriebskanal nur für
    Außendienst und nur bekannte Werte."""
    from app.models import Benutzer, Team
    from app.routers.benutzer import _email_pruefen
    vorhandene = {(b.name or "").strip().lower() for b in session.query(Benutzer.name)}
    teams = {(t.name or "").strip().lower(): t.id
             for t in session.query(Team).filter(Team.aktiv.is_(True))}
    kanaele = {k.lower(): k for k in kanal_werte_import(session)}
    gesehen: dict[str, int] = {}
    for zeile in zeilen:
        zeile.fehler = []
        name_klein = zeile.name.lower()
        if not zeile.name:
            zeile.fehler.append("Name fehlt")
        elif len(zeile.name) > 100:
            zeile.fehler.append("Name zu lang (höchstens 100 Zeichen)")
        elif name_klein in vorhandene:
            zeile.fehler.append("Name bereits vorhanden")
        elif name_klein in gesehen:
            zeile.fehler.append(f"Name doppelt in der Datei (Zeile {gesehen[name_klein]})")
        else:
            gesehen[name_klein] = zeile.nr
        rolle = rolle_zuordnen(zeile.rolle_roh)
        if rolle is None:
            zeile.fehler.append(f"Rolle unbekannt: „{zeile.rolle_roh or '–'}“ "
                                "(erlaubt: Admin, Innendienst, Außendienst, Projektierung, "
                                "Montage, Lead-Management)")
        else:
            zeile.rolle = rolle
            email_fehler = _email_pruefen(rolle, zeile.email)
            if email_fehler:
                zeile.fehler.append(email_fehler)
        if zeile.team:
            zeile.team_id = teams.get(zeile.team.lower())
            if zeile.team_id is None:
                zeile.fehler.append(f"Team unbekannt: „{zeile.team}“ (Parametrierung → Teams)")
        if zeile.kanal:
            if rolle is not None and rolle != "aussendienst":
                zeile.fehler.append("Vertriebskanal nur für Außendienst")
            elif zeile.kanal.lower() not in kanaele:
                erlaubt = ", ".join(kanaele.values()) or "keine Kanäle hinterlegt"
                zeile.fehler.append(f"Vertriebskanal unbekannt: „{zeile.kanal}“ (erlaubt: {erlaubt})")
            else:
                zeile.kanal = kanaele[zeile.kanal.lower()]
    return zeilen


# --- Start-PIN und Anlegen --------------------------------------------------------------

def start_pin(session: Session | None = None) -> str:
    """Zufällige Start-PIN (6 Ziffern, bei höherer Mindestlänge entsprechend
    länger), die alle PIN-Regeln besteht."""
    laenge = max(START_PIN_LAENGE, auth.pin_mindestlaenge(session))
    for _ in range(1000):
        pin = "".join(str(secrets.randbelow(10)) for _ in range(laenge))
        if auth.pin_regel_pruefen(pin, session) is None:
            return pin
    raise RuntimeError("Keine regelkonforme Start-PIN gefunden – PIN-Regeln prüfen.")


def anlegen(session: Session, zeilen: list[Zeile], erstellt_von: int | None) -> list[dict]:
    """Legt alle (fehlerfreien) Zeilen als Benutzer an: beide Hash-Spalten über
    auth.pin_setzen, pin_wechsel_noetig = True, Team-Mitgliedschaft,
    Kanal-Regel für Außendienst. Committet NICHT (macht die Route). Liefert
    [{name, rolle, rolle_name, pin}] für die einmalige Start-PIN-Liste."""
    from app import lead_termin
    from app.models import Benutzer, TeamMitglied
    ergebnis = []
    for zeile in zeilen:
        if zeile.fehler:
            continue
        pin = start_pin(session)
        neuer = Benutzer(name=zeile.name, rolle=zeile.rolle, email=zeile.email,
                         pin_wechsel_noetig=True)
        auth.pin_setzen(neuer, pin)
        session.add(neuer)
        session.flush()
        if zeile.team_id:
            session.add(TeamMitglied(team_id=zeile.team_id, benutzer_id=neuer.id,
                                     erstellt_von=erstellt_von))
        if zeile.kanal and zeile.rolle == "aussendienst":
            lead_termin.kanal_regel_ad_setzen(session, neuer.id, [zeile.kanal])
        ergebnis.append({"name": neuer.name, "rolle": neuer.rolle,
                         "rolle_name": zeile.rolle_name, "pin": pin})
    return ergebnis
