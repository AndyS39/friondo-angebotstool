# Outlook-Kalender-Sync (v15, Phase 81): Montage-/Feinplanungs-/Abnahme-
# Termine als Kalendereintraege in Team-Postfaechern ODER einem gemeinsamen
# Kalender mit Kategorie je Team (Parameter outlook_kalender_modus:
# postfach | kategorien; Einrichtung: docs/graph-einrichtung.md).
# Fehler blockieren nie – sie landen als Warnsymbol am Termin
# (ProjektTermin.outlook_fehler) mit Knopf "Erneut senden".
#
# v33 (PLAN_V20 Phase 170): Outlook je Mitarbeiter. event_senden / event_loeschen
# behalten ihre Signaturen, reihen aber nur noch Aufträge für app/outlook_sync.py ein
# (je Person der Besetzung bzw. Person eine Kopie im persönlichen Kalender; der
# Team-Kalender nur zusätzlich, wenn teams.outlook_adresse gesetzt ist [ANNAHME
# optional]); kein Graph-Aufruf im Request. ruecklesen() ruft den Lauf
# outlook-ruecklesen. _kalender_ziel/_event_daten bleiben für den Altbestand
# (Migration, Storno alter Team-Ereignisse) erhalten.

import urllib.parse
from datetime import datetime, timedelta

from app import projektierung as kern

# v33: alle Terminarten des Dialogs, zusätzlich Service-Einsätze (Phase 168)
RELEVANTE_TYPEN = ("montage", "sub", "feinplanung", "abnahme", "sonstige", "service")
GRAPH = "https://graph.microsoft.com/v1.0"
ZEITZONE = "W. Europe Standard Time"

status: dict = {"letzter_ruecklauf": None, "geaendert": 0, "fehler": []}


def modus(session) -> str:
    wert = kern.parameter_holen(session, "outlook_kalender_modus", "postfach")
    return wert if wert in ("postfach", "kategorien") else "postfach"


def _kalender_ziel(session, termin) -> tuple[str, list[str], str]:
    """(Postfach-Adresse, Kategorien, fehler)."""
    from app.models import Team
    team = session.get(Team, termin.team_id) if termin.team_id else None
    if modus(session) == "kategorien":
        adresse = kern.parameter_holen(session, "outlook_kalender_adresse", "")
        if not adresse:
            return "", [], ("Gemeinsamer Kalender: outlook_kalender_adresse "
                            "in der Parametrierung fehlt.")
        return adresse, ([team.name] if team is not None else []), ""
    if team is None or not (team.outlook_adresse or "").strip():
        return "", [], ("Team ohne Outlook-Adresse – in der Parametrierung "
                        "(Teams) pflegen.")
    return team.outlook_adresse.strip(), [], ""


def _event_daten(session, termin, kategorien: list[str]) -> dict:
    from app.models import Gewerk, Kunde, Projekt
    projekt = session.get(Projekt, termin.projekt_id)
    gewerk = session.get(Gewerk, termin.gewerk_id) if termin.gewerk_id else None
    kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
    betreff = " · ".join(t for t in [
        projekt.nummer if projekt else "",
        kunde.anzeige_name if kunde else "",
        gewerk.sparte if gewerk else ""] if t)
    if termin.typ != "montage":
        betreff = f"{termin.typ.capitalize()}: {betreff}"
    # v31 (PLAN_LEAD_V5 Phase 153): Ausführungsort über projekt_ausfuehrungsort
    ort = (kern.projekt_ausfuehrungsort(session, projekt, gewerk)["zeile"]
           if projekt is not None else "")
    # Steckbrief-Kurzfassung + Link ins Tool
    zeilen = []
    if gewerk is not None:
        werte = kern.steckbrief_daten(session, [gewerk.id])[gewerk.id]
        for feld, name in kern.steckbrief_felder(gewerk.sparte)[:8]:
            if feld in werte and werte[feld].wert:
                zeilen.append(f"{name}: {werte[feld].wert}")
    basis = kern.parameter_holen(session, "basis_url", "").rstrip("/")
    if basis and projekt is not None:
        zeilen.append(f"Akte: {basis}/projektierung/projekt/{projekt.id}")
    ende = termin.ende or (termin.beginn + timedelta(hours=8))
    daten = {
        "subject": betreff or "Friondo-Termin",
        "location": {"displayName": ort},
        "body": {"contentType": "text", "content": "\n".join(zeilen)},
        "start": {"dateTime": termin.beginn.strftime("%Y-%m-%dT%H:%M:%S"),
                  "timeZone": ZEITZONE},
        "end": {"dateTime": ende.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": ZEITZONE},
    }
    if kategorien:
        daten["categories"] = kategorien
    return daten


def event_senden(session, termin) -> tuple[bool, str]:
    """Anlegen oder Aktualisieren – wirft nie; Fehlertext landet am Termin.
    v33 (PLAN_V20 Phase 170): reiht je Person der Besetzung bzw. Person einen Auftrag
    ein (anlegen für neue Kopien, aendern für vorhandene, loeschen für Personen, die
    nicht mehr eingeteilt sind – Besetzungsdifferenz vergleicht outlook_sync mit der
    Tabelle outlook_ereignisse); kein Graph-Aufruf im Request. True = eingereiht."""
    from app import outlook_sync
    if termin is None or termin.typ not in RELEVANTE_TYPEN or termin.beginn is None:
        return True, ""
    if getattr(termin, "id", None) is None:
        return True, ""
    try:
        outlook_sync.auftrag_einreihen(session, outlook_sync.AKTION_AENDERN,
                                       outlook_sync.ART_PROJEKT, termin.id)
    except Exception as problem:   # noqa: BLE001 – Termin speichern darf nie scheitern
        termin.outlook_fehler = f"Outlook-Sync fehlgeschlagen: {problem}"[:300]
        return False, termin.outlook_fehler
    termin.outlook_fehler = ""
    return True, ""


def event_loeschen(session, termin) -> bool:
    """v33: Aufträge „loeschen“ für alle Kopien des Termins (persönliche Kalender und
    – Altbestand – der Team-Kalender); die Aufträge tragen Postfach und Event-ID, der
    Termin darf danach gelöscht werden. Kein Graph-Aufruf im Request."""
    from app import outlook_sync
    if termin is None or getattr(termin, "id", None) is None:
        return True
    try:
        outlook_sync.auftrag_einreihen(session, outlook_sync.AKTION_LOESCHEN,
                                       outlook_sync.ART_PROJEKT, termin.id)
    except Exception:   # noqa: BLE001 – Storno-Fehler blockieren das Löschen nie
        return False
    return True


def _zeit_parsen(daten: dict) -> datetime | None:
    roh = (daten or {}).get("dateTime") or ""
    try:
        return datetime.fromisoformat(roh[:19])
    except ValueError:
        return None


def ruecklesen() -> int:
    """Outlook → Tool. v33 (PLAN_V20 Phase 170): ruft den Lauf outlook-ruecklesen
    (calendarView je Person mit Terminen, acht Wochen; verschobene Kopien ziehen den
    Tool-Termin nach, fehlende setzen „in Outlook gelöscht“, fremde Einträge füllen den
    Belegt-Cache). Signatur und Rückgabe (Anzahl geänderter Termine) bleiben für den
    Teilschritt von mail_sync erhalten; läuft der registrierte Lauf gerade, wird nichts
    doppelt gelesen. Sitzungsdisziplin liegt im Lauf (Token und Graph ohne Sitzung)."""
    from app import outlook_sync, scheduler
    lauf = scheduler.holen(outlook_sync.LAUF_RUECKLESEN)
    if lauf is not None and lauf.sperre.locked():
        return 0
    ergebnis = outlook_sync.ruecklesen_lauf()
    geaendert = int(ergebnis.get("geaendert", 0) or 0)
    fehler: list[str] = []
    if ergebnis.get("ergebnis"):
        fehler.append(str(ergebnis["ergebnis"]))
    if ergebnis.get("fehler"):
        fehler.append(f"{ergebnis['fehler']} Postfächer nicht gelesen")
    if ergebnis.get("ohne_zugriff"):
        fehler.append(f"{ergebnis['ohne_zugriff']} Postfächer ohne Zugriff (403)")
    status.update(letzter_ruecklauf=datetime.now(), geaendert=geaendert, fehler=fehler)
    return geaendert
