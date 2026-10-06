# Graph-Kalender (v12, Phase 77): Frei/Belegt lesen + VOT-Termine schreiben.
# NUR aktiv bei kalender_sync = an; im Demo-Modus (lead_freigabe_modus=admin)
# wird ausschließlich in das kalender_testpostfach geschrieben und gelesen –
# nie in echte AD-Kalender. Fehlende Berechtigung → der Assistent arbeitet
# nur mit Tool-Terminen. Gemeinsame Strecke – die Projektierung kann die
# Funktionen später für Montage-Termine nutzen.
# Berechtigung (M365-Admin): Calendars.ReadWrite (Application) mit
# Application Access Policy – siehe docs/graph-einrichtung.md.

from datetime import datetime

from sqlalchemy.orm import Session

from app import config

BASIS_URL = config.BASIS_URL   # v27: aus der .env (BASIS_URL), Standard wie bisher


def aktiv(session: Session) -> bool:
    from app import leadmanagement as kern
    return kern.parameter_holen(session, "kalender_sync", "aus") == "an"


def _postfach(session: Session, ad) -> str | None:
    """Ziel-Postfach: im Demo-Modus IMMER das Testpostfach."""
    from app import leadmanagement as kern
    from app.models import AdProfil
    if kern.demo_aktiv(session):
        return (kern.parameter_holen(session, "kalender_testpostfach", "")
                or None)
    if ad is None:
        return None
    profil = (session.query(AdProfil)
              .filter(AdProfil.benutzer_id == ad.id).first())
    if profil is not None and profil.kalender_postfach:
        return profil.kalender_postfach
    return ad.email or None


def _token():
    from app import graph_versand
    return graph_versand._token()


def frei_belegt(session: Session, ad, von: datetime,
                bis: datetime) -> list[tuple[datetime, datetime]] | None:
    """Belegte Zeiten aus calendarView; None = Kalender nicht verfügbar
    (aus, kein Postfach, kein Recht) → Assistent nutzt nur Tool-Termine."""
    if not aktiv(session):
        return None
    postfach = _postfach(session, ad)
    if not postfach:
        return None
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Token-Erneuerung
    # über msal und calendarView dauern bis zu 60 s)
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    token = _token()
    if token is None:
        return None
    from app import graph_versand
    try:
        antwort = graph_versand._graph_aufruf(
            "GET",
            f"/users/{postfach}/calendarView?"
            f"startDateTime={von.strftime('%Y-%m-%dT%H:%M:%S')}"
            f"&endDateTime={bis.strftime('%Y-%m-%dT%H:%M:%S')}"
            "&$top=100&$select=start,end,showAs", token)
        belegt = []
        for eintrag in antwort.get("value", []):
            if eintrag.get("showAs") in ("free",):
                continue
            beginn = datetime.fromisoformat(
                eintrag["start"]["dateTime"][:19])
            ende = datetime.fromisoformat(eintrag["end"]["dateTime"][:19])
            belegt.append((beginn, ende))
        return belegt
    except Exception:
        return None


def _ereignis_rumpf(session: Session, termin, vorgang, kunde) -> dict:
    from app.models import LeadQualifizierung
    import json as json_modul
    steckbrief = []
    for q in (session.query(LeadQualifizierung)
              .filter(LeadQualifizierung.vorgang_id == vorgang.id,
                      LeadQualifizierung.abgeschlossen_am.isnot(None))):
        try:
            antworten = json_modul.loads(q.antworten or "{}")
        except ValueError:
            antworten = {}
        steckbrief.append(f"{q.sparte}: " + "; ".join(
            f"{k}={v}" for k, v in list(antworten.items())[:8]))
    sparten = (kunde.interesse or "").replace(",", "/")
    text = "\n".join(filter(None, [
        f"Telefon: {kunde.telefon or '-'}",
        f"Anfrage: {(vorgang.anfrage_text or '')[:300]}",
        *steckbrief,
        f"Lead-Akte: {BASIS_URL}/lead-management/lead/{vorgang.id}",
    ]))
    # v23 (Phase 108, A-2): Betreff je Terminart – Vorab-Gespräche (Telefon/
    # Teams) erscheinen nicht als VOT im Kalender des Vertrieblers
    typ = getattr(termin, "typ", "vot") or "vot"
    praefix = {"vot": "VOT", "telefon": "Telefongespräch",
               "online": "Teams"}.get(typ, "VOT")
    ort = termin.adresse or {"telefon": "Telefon", "online": "Microsoft Teams"}.get(typ, "")
    from datetime import timedelta
    ende = termin.ende or (termin.beginn + timedelta(minutes=30))
    return {
        "subject": f"{praefix} {sparten} – {kunde.nachname}, {kunde.ort or '?'}",
        "body": {"contentType": "text", "content": text},
        "location": {"displayName": ort},
        "start": {"dateTime": termin.beginn.strftime("%Y-%m-%dT%H:%M:%S"),
                  "timeZone": "W. Europe Standard Time"},
        "end": {"dateTime": ende.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "W. Europe Standard Time"},
    }


def termin_schreiben(session: Session, termin, vorgang, kunde, ad) -> bool:
    """Outlook-Ereignis anlegen (best effort; speichert outlook_event_id)."""
    if not aktiv(session):
        return False
    postfach = _postfach(session, ad)
    if not postfach:
        return False
    rumpf = _ereignis_rumpf(session, termin, vorgang, kunde)
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Rumpf ist gelesen;
    # der commit speichert den bereits angelegten Termin – wie bisher am Ende)
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    token = _token()
    if token is None:
        return False
    from app import graph_versand
    try:
        antwort = graph_versand._graph_aufruf(
            "POST", f"/users/{postfach}/events", token, rumpf)
        termin.outlook_event_id = f"{postfach}|{antwort.get('id', '')}"
        return True
    except Exception:
        return False


def termin_aendern(session: Session, termin, vorgang, kunde, ad) -> bool:
    if not aktiv(session) or not termin.outlook_event_id:
        return termin_schreiben(session, termin, vorgang, kunde, ad)
    rumpf = _ereignis_rumpf(session, termin, vorgang, kunde)
    postfach, _, ereignis_id = termin.outlook_event_id.partition("|")
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    token = _token()
    if token is None:
        return False
    from app import graph_versand
    try:
        graph_versand._graph_aufruf(
            "PATCH", f"/users/{postfach}/events/{ereignis_id}", token, rumpf)
        return True
    except Exception:
        return False


def termin_loeschen(session: Session, termin) -> bool:
    if not aktiv(session) or not termin.outlook_event_id:
        return False
    postfach, _, ereignis_id = termin.outlook_event_id.partition("|")
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    token = _token()
    if token is None:
        return False
    from app import graph_versand
    try:
        graph_versand._graph_aufruf(
            "DELETE", f"/users/{postfach}/events/{ereignis_id}", token)
        termin.outlook_event_id = None
        return True
    except Exception:
        return False
