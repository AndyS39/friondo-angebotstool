# Graph-Kalender (v12, Phase 77): Frei/Belegt lesen + VOT-Termine schreiben.
# NUR aktiv bei kalender_sync = an; im Demo-Modus (lead_freigabe_modus=admin)
# wird ausschließlich in das kalender_testpostfach geschrieben und gelesen –
# nie in echte AD-Kalender. Fehlende Berechtigung → der Assistent arbeitet
# nur mit Tool-Terminen. Gemeinsame Strecke – die Projektierung kann die
# Funktionen später für Montage-Termine nutzen.
# Berechtigung (M365-Admin): Calendars.ReadWrite (Application) mit
# Application Access Policy – siehe docs/graph-einrichtung.md.
#
# v33 (PLAN_V20 Phase 170): KEIN Graph-Aufruf mehr im Request. termin_schreiben /
# termin_aendern / termin_loeschen behalten ihre Signaturen, reihen aber nur noch
# Aufträge in outlook_auftraege ein (Lauf outlook-sync, app/outlook_sync.py);
# frei_belegt liest den Belegt-Cache outlook_belegt (Lauf outlook-ruecklesen).
# Der Schalter kalender_sync gilt weiter für VOT-Termine und den Belegt-Abgleich
# [ANNAHME O]; Demo-Termine (vot_termine.demo) gehen weiter ins Testpostfach.

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


import logging

_logger = logging.getLogger("angebotstool.kalender")


def _ist_handelsvertreter(session: Session, ad) -> bool:
    """v29 (PLAN_LEAD_V4 Phase 143, [OFFEN 3]): Handelsvertreter haben kein Friondo-
    Postfach – kein Outlook-Lesen/-Schreiben, Protokollzeile statt Fehler."""
    from app import lead_v2
    try:
        return ad is not None and lead_v2.ist_handelsvertreter(session, ad)
    except Exception:   # noqa: BLE001 – Kalender-Sync darf nie an der HV-Prüfung scheitern
        return False


def frei_belegt(session: Session, ad, von: datetime,
                bis: datetime) -> list[tuple[datetime, datetime]] | None:
    """Belegte Zeiten der Person; None = Kalender nicht verfügbar (kalender_sync aus,
    Handelsvertreter ohne Postfach) → Assistent nutzt nur Tool-Termine.
    v33 (PLAN_V20 Phase 170): liest den Cache outlook_belegt des Laufs
    outlook-ruecklesen – kein Graph-Aufruf im Request mehr (Signatur bleibt)."""
    from app import outlook_sync
    return outlook_sync.belegt_fuer(session, ad, von, bis)


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


def _auftrag(session: Session, aktion: str, termin, ad=None) -> bool:
    """v33: Auftrag für die Warteschlange outlook_auftraege einreihen (kein Netz);
    True = mindestens ein Auftrag angelegt. Der Lauf outlook-sync überträgt."""
    from app import outlook_sync
    if termin is None or getattr(termin, "id", None) is None:
        return False
    personen = [ad.id] if ad is not None else None
    try:
        auftraege = outlook_sync.auftrag_einreihen(session, aktion, outlook_sync.ART_VOT,
                                                   termin.id, personen)
        if auftraege:
            return True
        # kein neuer Auftrag nötig, wenn ein offener (z. B. „anlegen“) die Kopie schon abdeckt
        return outlook_sync.auftraege_offen(session, outlook_sync.ART_VOT, termin.id) > 0
    except Exception:   # noqa: BLE001 – die Buchung darf an Outlook nie scheitern
        _logger.exception("kalender: Outlook-Auftrag %s für Termin %s nicht eingereiht",
                          aktion, termin.id)
        return False


def termin_schreiben(session: Session, termin, vorgang, kunde, ad) -> bool:
    """Outlook-Ereignis im persönlichen Kalender des Vertrieblers anlegen – v33: reiht
    nur den Auftrag „anlegen“ ein (Lauf outlook-sync schreibt; Demo-Termine ins
    Testpostfach; Handelsvertreter ohne Friondo-Postfach → kein Auftrag, Hinweis
    „HV ohne Postfach“ am Termin). Signatur und Rückgabe (True = eingereiht) bleiben."""
    if not aktiv(session) or termin is None or termin.beginn is None:
        return False
    if _ist_handelsvertreter(session, ad):
        _logger.info("kalender_sync: Handelsvertreter %s – Kopie nur mit Friondo-Postfach",
                     getattr(ad, "name", "?"))
    from app import outlook_sync
    return _auftrag(session, outlook_sync.AKTION_ANLEGEN, termin, ad)


def termin_aendern(session: Session, termin, vorgang, kunde, ad) -> bool:
    """v33: Auftrag „aendern“ je Kopie (Personenwechsel: alte Kopie löschen, neue
    anlegen – macht outlook_sync.auftrag_einreihen); ohne vorhandene Kopie wird
    angelegt. Kein Graph-Aufruf im Request."""
    if not aktiv(session) or termin is None or termin.beginn is None:
        return False
    from app import outlook_sync
    return _auftrag(session, outlook_sync.AKTION_AENDERN, termin, ad)


def termin_loeschen(session: Session, termin) -> bool:
    """v33: Auftrag „loeschen“ für alle Kopien des Termins (auch wenn kalender_sync
    inzwischen aus ist – vorhandene Kopien sollen verschwinden). Das alte Feld
    outlook_event_id leert der Lauf nach dem erfolgreichen DELETE."""
    from app import outlook_sync
    return _auftrag(session, outlook_sync.AKTION_LOESCHEN, termin)
