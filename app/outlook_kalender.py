# Outlook-Kalender-Sync (v15, Phase 81): Montage-/Feinplanungs-/Abnahme-
# Termine als Kalendereintraege in Team-Postfaechern ODER einem gemeinsamen
# Kalender mit Kategorie je Team (Parameter outlook_kalender_modus:
# postfach | kategorien; Einrichtung: docs/graph-einrichtung.md).
# Fehler blockieren nie – sie landen als Warnsymbol am Termin
# (ProjektTermin.outlook_fehler) mit Knopf "Erneut senden".

import urllib.parse
from datetime import datetime, timedelta

from app import projektierung as kern

RELEVANTE_TYPEN = ("montage", "feinplanung", "abnahme")
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
    ort = " ".join(t for t in [
        projekt.ausfuehrung_strasse if projekt else "",
        f"{projekt.ausfuehrung_plz} {projekt.ausfuehrung_ort}".strip()
        if projekt else ""] if t)
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
    """Anlegen oder Aktualisieren – wirft nie; Fehlertext landet am Termin."""
    from app import graph_versand
    from app.db import verbindung_freigeben
    if termin.typ not in RELEVANTE_TYPEN or termin.beginn is None:
        return True, ""
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (msal kann das Token
    # über das Netz erneuern; der commit speichert den bereits angelegten bzw.
    # geänderten Termin – wie bisher beim commit des Aufrufers)
    verbindung_freigeben(session)
    token = graph_versand._token()
    if token is None:
        termin.outlook_fehler = "Nicht bei Microsoft angemeldet"
        return False, termin.outlook_fehler
    adresse, kategorien, fehler = _kalender_ziel(session, termin)
    if fehler:
        termin.outlook_fehler = fehler
        return False, fehler
    basis = f"/users/{urllib.parse.quote(adresse)}/calendar/events"
    daten = _event_daten(session, termin, kategorien)
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Ziel und
    # Ereignisdaten sind gelesen)
    verbindung_freigeben(session)
    try:
        if termin.outlook_event_id:
            graph_versand._graph_aufruf(
                "PATCH", f"{basis}/{termin.outlook_event_id}", token, daten)
        else:
            antwort = graph_versand._graph_aufruf("POST", basis, token, daten)
            termin.outlook_event_id = antwort.get("id", "")
        termin.outlook_fehler = ""
        return True, ""
    except Exception as problem:
        termin.outlook_fehler = f"Outlook-Sync fehlgeschlagen: {problem}"[:300]
        return False, termin.outlook_fehler


def event_loeschen(session, termin) -> bool:
    from app import graph_versand
    from app.db import verbindung_freigeben
    if not termin.outlook_event_id:
        return True
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (msal kann das Token
    # über das Netz erneuern)
    verbindung_freigeben(session)
    token = graph_versand._token()
    if token is None:
        return False
    adresse, _kategorien, fehler = _kalender_ziel(session, termin)
    if fehler:
        return False
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Ziel ist gelesen)
    verbindung_freigeben(session)
    try:
        graph_versand._graph_aufruf(
            "DELETE", f"/users/{urllib.parse.quote(adresse)}/calendar/events/"
                      f"{termin.outlook_event_id}", token)
        termin.outlook_event_id = ""
        return True
    except Exception:
        return False


def _zeit_parsen(daten: dict) -> datetime | None:
    roh = (daten or {}).get("dateTime") or ""
    try:
        return datetime.fromisoformat(roh[:19])
    except ValueError:
        return None


def ruecklesen() -> int:
    """Outlook → Tool (15-Minuten-Scheduler): Datum/Dauer-Änderungen der
    gesyncten Termine zurücklesen; Verlaufseintrag je Änderung."""
    from app import graph_versand
    from app.db import SessionLocal, verbindung_freigeben
    from app.models import Gewerk, ProjektTermin
    token = graph_versand._token()
    if token is None:
        return 0
    session = SessionLocal()
    geaendert = 0
    fehler: list[str] = []
    try:
        termine = (session.query(ProjektTermin)
                   .filter(ProjektTermin.outlook_event_id != "",
                           ProjektTermin.beginn.isnot(None)).all())
        for termin in termine:
            adresse, _kategorien, ziel_fehler = _kalender_ziel(session, termin)
            if ziel_fehler:
                continue
            # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (vor JEDEM
            # Graph-Abruf; Ziel ist gelesen, der commit speichert die Änderungen
            # des vorherigen Termins – wie bisher am Ende des Laufs)
            verbindung_freigeben(session)
            try:
                event = graph_versand._graph_aufruf(
                    "GET", f"/users/{urllib.parse.quote(adresse)}/calendar/"
                           f"events/{termin.outlook_event_id}"
                           "?$select=start,end,isCancelled", token)
            except Exception as problem:
                fehler.append(f"Termin {termin.id}: {problem}")
                continue
            neu_beginn = _zeit_parsen(event.get("start"))
            neu_ende = _zeit_parsen(event.get("end"))
            if neu_beginn is None:
                continue
            if (neu_beginn == termin.beginn
                    and (neu_ende is None or neu_ende == termin.ende)):
                continue
            alt_text = termin.beginn.strftime("%d.%m.%Y %H:%M")
            termin.beginn = neu_beginn
            if neu_ende is not None:
                termin.ende = neu_ende
                termin.dauer_tage = max(1, (neu_ende.date()
                                            - neu_beginn.date()).days + 1)
            kern.verlauf(session, termin.projekt_id,
                         f"Termin in Outlook verschoben von {alt_text} auf "
                         f"{neu_beginn.strftime('%d.%m.%Y %H:%M')} ({termin.typ})",
                         gewerk_id=termin.gewerk_id)
            gewerk = (session.get(Gewerk, termin.gewerk_id)
                      if termin.gewerk_id else None)
            if gewerk is not None and termin.typ in ("feinplanung", "montage"):
                kern.faelligkeiten_nachberechnen(session, gewerk)
            geaendert += 1
        session.commit()
    finally:
        session.close()
    status.update(letzter_ruecklauf=datetime.now(), geaendert=geaendert,
                  fehler=fehler)
    return geaendert
