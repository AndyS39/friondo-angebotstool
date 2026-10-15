# Outlook-Sync je Mitarbeiter – v33 (PLAN_V20 Phase 170, Agent O).
#
# Jeder Tool-Termin steht als Kopie im persönlichen Outlook-Kalender jeder eingeteilten
# Person (TAIFUN liest von dort). Schreiben läuft NIE im Request: `auftrag_einreihen`
# legt je Kopie einen `OutlookAuftrag` (anlegen | aendern | loeschen) an, der Lauf
# `outlook-sync` (60 s) arbeitet die Warteschlange über Graph ab (`/users/<upn>/events`,
# Modus anwendung; im Modus delegiert dieselben Pfade über das Token der Anmeldung).
# Der Lauf `outlook-ruecklesen` (300 s) liest je Person mit Terminen in den nächsten
# acht Wochen die `calendarView`: Tool-Kopien (Kennzeichen `friondoTerminId`) mit
# verändertem Zeitraum ziehen den Tool-Termin nach (erste Änderung gewinnt, übrige
# Kopien werden per Auftrag angeglichen), fehlende Kopien setzen den Stand
# `in_outlook_geloescht` (kein stilles Löschen, Glocke), fremde Einträge landen nur als
# Belegtzeit im Cache `outlook_belegt` (Terminassistent, /kalender – nie Graph im Request).
#
# Wahrheit ist die Tabelle `outlook_ereignisse`; die alten Felder `outlook_event_id`
# (vot_termine, projekt_termine) bleiben gespiegelt (erste Kopie). Sitzungsdisziplin v27:
# lesen (db.kurz) → Sitzung zu → Graph → kurze Sitzung schreiben. Kein Geheimnis im Code.
# Einrichtung und Vorab-Abgleich TAIFUN: docs/outlook-sync.md.

import logging
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import config
from app.models import (AdProfil, Benutzer, Kunde, OutlookAuftrag, OutlookBelegt,
                        OutlookEreignis, ProjektTermin, Team, Vorgang, VotTermin)

_logger = logging.getLogger("angebotstool.outlook_sync")

# --- Konstanten -----------------------------------------------------------------------
LAUF_SYNC = "outlook-sync"
LAUF_RUECKLESEN = "outlook-ruecklesen"
SYNC_INTERVALL_S = 60
RUECKLESEN_INTERVALL_S = 300
SYNC_START_VERZOEGERUNG_S = 60
RUECKLESEN_START_VERZOEGERUNG_S = 330
BLOCK_GROESSE = 50              # offene Aufträge je Lauf
VERSUCHE_MAX = 3
ZUGRIFF_WIEDERHOLUNG_S = 3600   # 403-Aufträge stündlich erneut versuchen …
ZUGRIFF_WIEDERHOLUNG_TAGE = 7   # … bis zu sieben Tage lang
ZUGRIFFSGRUPPE_TEXT = "nicht in der Zugriffsgruppe"   # Fehlertext von GraphZugriffVerweigert
RUECKLESE_WOCHEN = 8
CALENDARVIEW_TOP = 500
CALENDARVIEW_SEITEN_MAX = 10

ART_VOT = "vot"
ART_PROJEKT = "projekt"
TERMIN_ARTEN = (ART_VOT, ART_PROJEKT)

AKTION_ANLEGEN = "anlegen"
AKTION_AENDERN = "aendern"
AKTION_LOESCHEN = "loeschen"

STAND_AUSSTEHEND = "ausstehend"
STAND_OK = "ok"
STAND_FEHLER = "fehler"
STAND_GELOESCHT = "geloescht"
STAND_IN_OUTLOOK_GELOESCHT = "in_outlook_geloescht"
STAND_LEER = "leer"            # keine Kopie möglich (z. B. HV ohne Postfach) – nur Hinweis
STAENDE = (STAND_AUSSTEHEND, STAND_OK, STAND_FEHLER, STAND_GELOESCHT,
           STAND_IN_OUTLOOK_GELOESCHT, STAND_LEER)
STAND_TEXTE = {
    STAND_AUSSTEHEND: "ausstehend", STAND_OK: "ok", STAND_FEHLER: "Fehler",
    STAND_GELOESCHT: "gelöscht", STAND_IN_OUTLOOK_GELOESCHT: "in Outlook gelöscht",
    STAND_LEER: "kein Eintrag",
}

STATUS_OFFEN = "offen"
STATUS_ERLEDIGT = "erledigt"
STATUS_FEHLER = "fehler"

# TAIFUN-Vorab-Abgleich steht noch aus – bis zur Entscheidung Andreas [ANNAHME Plan]:
# Tool-Termine sind für TAIFUN sichtbar (showAs busy), Betreff „<Art>: <Kunde>, <PLZ Ort>
# (<Nummer>)“, Kategorie „Friondo-Tool“. Das Kennzeichen ist eine feste erweiterte
# Eigenschaft; Einträge ohne Kennzeichen fasst das Tool nie an.
KATEGORIE = "Friondo-Tool"
PROPERTY_GUID = "{7f3a2c1e-5b64-4d8e-9a1f-2c6b8e4d9f10}"       # fest, nie ändern
PROPERTY_ID = f"String {PROPERTY_GUID} Name friondoTerminId"
ZEITZONE = "W. Europe Standard Time"
SHOW_AS = "busy"
HV_OHNE_POSTFACH = "HV ohne Postfach"
TESTPOSTFACH_FEHLT = "Testpostfach fehlt (Parameter kalender_testpostfach)"
KEIN_POSTFACH = "kein Postfach (E-Mail fehlt)"
NICHT_ANGEMELDET = "Nicht bei Microsoft angemeldet"
TERMIN_WEG = "Termin nicht mehr vorhanden"
PERSON_WEG = "Person nicht mehr eingeteilt"
TEAM_KOPIE_ID = 0              # benutzer_id der optionalen Team-Kalender-Kopie
VOT_ART_NAMEN = {"vot": "VOT", "telefon": "Telefongespräch", "online": "Teams",
                 "sperrzeit": "Sperrzeit"}

# Postfächer, die beim letzten Lauf HTTP 403 lieferten (Vertrag G: Verbindungs-Seite)
_OHNE_ZUGRIFF: dict[str, dict] = {}


# --- Postfach und Personen -------------------------------------------------------------

def _friondo_domain() -> str:
    from app import graph_versand
    try:
        return graph_versand.standard_postfach().rsplit("@", 1)[-1].strip().lower()
    except Exception:   # noqa: BLE001 – ohne Datenbank gilt der Standard
        return "friondo.de"


def ist_handelsvertreter(session: Session, benutzer) -> bool:
    from app import lead_v2
    try:
        return benutzer is not None and lead_v2.ist_handelsvertreter(session, benutzer)
    except Exception:   # noqa: BLE001 – der Sync darf nie an der HV-Prüfung scheitern
        return False


def postfach_fuer(session: Session, benutzer, demo: bool = False) -> tuple[str, str]:
    """(Postfach, Grund) der Person: Demo-/Test-Termine → `kalender_testpostfach`;
    sonst `AdProfil.kalender_postfach`, sonst `Benutzer.email`. Handelsvertreter ohne
    Friondo-Postfach (kein kalender_postfach, E-Mail außerhalb der Friondo-Domain) →
    kein Postfach, Grund „HV ohne Postfach“."""
    from app import leadmanagement as kern
    if demo:
        test = (kern.parameter_holen(session, "kalender_testpostfach", "") or "").strip()
        return (test, "") if test else ("", TESTPOSTFACH_FEHLT)
    if benutzer is None:
        return "", "Person fehlt"
    profil = (session.query(AdProfil).filter(AdProfil.benutzer_id == benutzer.id).first())
    kalender_postfach = (profil.kalender_postfach or "").strip() if profil is not None else ""
    email = (benutzer.email or "").strip()
    if ist_handelsvertreter(session, benutzer):
        if kalender_postfach:
            return kalender_postfach, ""
        if email and email.rsplit("@", 1)[-1].lower() == _friondo_domain():
            return email, ""
        return "", HV_OHNE_POSTFACH
    if kalender_postfach:
        return kalender_postfach, ""
    if email:
        return email, ""
    return "", KEIN_POSTFACH


def _termin_laden(session: Session, termin_art: str, termin_id: int):
    if termin_art == ART_VOT:
        return session.get(VotTermin, int(termin_id))
    return session.get(ProjektTermin, int(termin_id))


def personen_fuer(session: Session, termin_art: str, termin) -> list[int]:
    """Benutzer-IDs, die eine Kopie bekommen: VOT → ad_id; Montage/Elektro/Sub/Service →
    jede Person der Besetzung (ohne Besetzung: person_id); Feinplanung/Abnahme/Sonstiges
    → person_id. Abwesenheiten/Sperrzeiten bekommen keine Kopie."""
    if termin is None:
        return []
    if termin_art == ART_VOT:
        if (getattr(termin, "typ", "vot") or "vot") == "sperrzeit":
            return []
        return [termin.ad_id] if termin.ad_id else []
    from app import projektierung as kern
    if termin.typ in ("montage", "sub", "service"):
        ids = kern.besetzung_ids(session, termin.id)
        if not ids and termin.person_id:
            ids = [termin.person_id]
        return ids
    return [termin.person_id] if termin.person_id else []


def team_postfach_fuer(session: Session, termin_art: str, termin) -> str:
    """[ANNAHME Plan: optional] Team-Kalender nur zusätzlich, wenn teams.outlook_adresse
    gesetzt ist – keine Pflicht."""
    if termin_art != ART_PROJEKT or termin is None or not termin.team_id:
        return ""
    team = session.get(Team, termin.team_id)
    return (team.outlook_adresse or "").strip() if team is not None else ""


# --- Warteschlange (im Request, ohne Netz) ---------------------------------------------

def _ereignisse_des_termins(session: Session, termin_art: str, termin_id: int) -> list[OutlookEreignis]:
    return (session.query(OutlookEreignis)
            .filter(OutlookEreignis.termin_art == termin_art,
                    OutlookEreignis.termin_id == int(termin_id))
            .order_by(OutlookEreignis.id).all())


def _offene_auftraege(session: Session, termin_art: str, termin_id: int) -> list[OutlookAuftrag]:
    return (session.query(OutlookAuftrag)
            .filter(OutlookAuftrag.termin_art == termin_art,
                    OutlookAuftrag.termin_id == int(termin_id),
                    OutlookAuftrag.status == STATUS_OFFEN)
            .order_by(OutlookAuftrag.id).all())


def auftraege_offen(session: Session, termin_art: str, termin_id: int) -> int:
    """Anzahl offener Aufträge eines Termins (Kopie wird noch übertragen)."""
    return (session.query(OutlookAuftrag)
            .filter(OutlookAuftrag.termin_art == termin_art,
                    OutlookAuftrag.termin_id == int(termin_id),
                    OutlookAuftrag.status == STATUS_OFFEN).count())


def _fehler_auftraege_ueberholen(session: Session, neue: list) -> None:
    """Vor einem neuen Auftrag derselben Kopie gelten ältere Aufträge im Status fehler als
    überholt – sonst würde die stündliche 403-Wiederholung die Kopie doppelt anlegen."""
    for n in neue:
        for a in (session.query(OutlookAuftrag)
                  .filter(OutlookAuftrag.termin_art == n.termin_art,
                          OutlookAuftrag.termin_id == n.termin_id,
                          OutlookAuftrag.status == STATUS_FEHLER)):
            if ((a.benutzer_id or 0) == (n.benutzer_id or 0)
                    and (a.postfach or "").lower() == (n.postfach or "").lower()):
                a.status = STATUS_ERLEDIGT
                a.fehler_text = f"{a.fehler_text} · überholt (neuer Auftrag)"[:300]
                a.erledigt_am = datetime.now()


def _zugriff_erneut_oeffnen(session: Session) -> int:
    """403-Aufträge (Postfach nicht in der Zugriffsgruppe) nach einer Stunde erneut versuchen,
    bis zu sieben Tage lang: Sobald die IT das Postfach aufgenommen hat, laufen sie ohne
    erneutes Speichern durch; scheitern sie wieder, bleibt die Liste der Verbindungs-Seite
    aktuell (neue Zeit). Übersprungen, wenn ein offener Auftrag dieselbe Kopie abdeckt."""
    jetzt = datetime.now()
    grenze = jetzt - timedelta(seconds=ZUGRIFF_WIEDERHOLUNG_S)
    alt = jetzt - timedelta(days=ZUGRIFF_WIEDERHOLUNG_TAGE)
    anzahl = 0
    for a in (session.query(OutlookAuftrag)
              .filter(OutlookAuftrag.status == STATUS_FEHLER,
                      OutlookAuftrag.fehler_text.like(f"%{ZUGRIFFSGRUPPE_TEXT}%"),
                      OutlookAuftrag.erledigt_am.isnot(None), OutlookAuftrag.erledigt_am < grenze,
                      OutlookAuftrag.angelegt_am >= alt)
              .order_by(OutlookAuftrag.id)):
        offene = _offene_auftraege(session, a.termin_art, a.termin_id)
        if any((o.benutzer_id or 0) == (a.benutzer_id or 0)
               and (o.postfach or "").lower() == (a.postfach or "").lower() for o in offene):
            continue
        a.status = STATUS_OFFEN
        anzahl += 1
    if anzahl:
        session.flush()
    return anzahl


def verwaiste_aufraeumen(session: Session) -> int:
    """Ereignis- und Auftragszeilen gelöschter Termine entfernen (älter als eine Stunde, Aufträge
    nicht offen – offene erledigt der Lauf selbst). SQLite vergibt die ID eines gelöschten
    Termins neu; verwaiste Zeilen dürfen einem neuen Termin nichts vererben."""
    from sqlalchemy import select
    grenze = datetime.now() - timedelta(hours=1)
    anzahl = 0
    for art, modell in ((ART_VOT, VotTermin), (ART_PROJEKT, ProjektTermin)):
        vorhandene = select(modell.id)
        anzahl += (session.query(OutlookEreignis)
                   .filter(OutlookEreignis.termin_art == art, OutlookEreignis.letzte_aenderung < grenze,
                           ~OutlookEreignis.termin_id.in_(vorhandene))
                   .delete(synchronize_session=False))
        anzahl += (session.query(OutlookAuftrag)
                   .filter(OutlookAuftrag.termin_art == art, OutlookAuftrag.status != STATUS_OFFEN,
                           OutlookAuftrag.angelegt_am < grenze,
                           ~OutlookAuftrag.termin_id.in_(vorhandene))
                   .delete(synchronize_session=False))
    return anzahl


def fremde_auftraege_abschliessen(session: Session, termin_ids=(), termin_art: str | None = None,
                                  grund: str = "übersprungen (Testlauf)") -> int:
    """Offene Aufträge, die NICHT zu `termin_ids` gehören, als erledigt markieren – für Tests,
    die den Lauf gezielt auf eigene Aufträge messen (andere Testmodule legen Termine über die
    Routen an und räumen die Warteschlange nicht auf), und für den Rollout-Handlauf."""
    ids = {int(t) for t in (termin_ids or [])}
    jetzt = datetime.now()
    anzahl = 0
    for a in session.query(OutlookAuftrag).filter(OutlookAuftrag.status == STATUS_OFFEN):
        if a.termin_id in ids and (termin_art is None or a.termin_art == termin_art):
            continue
        a.status = STATUS_ERLEDIGT
        a.fehler_text = grund[:300]
        a.erledigt_am = jetzt
        anzahl += 1
    if anzahl:
        session.flush()
    return anzahl


def _auftrag_offen(offene, aktion: str, benutzer_id: int, postfach: str) -> bool:
    return any(a.aktion == aktion and (a.benutzer_id or 0) == benutzer_id
               and (a.postfach or "").lower() == (postfach or "").lower()
               for a in offene if a.status == STATUS_OFFEN)


def _auftrag_ueberholen(offene, benutzer_id: int, postfach: str, grund: str) -> None:
    for a in offene:
        if (a.status == STATUS_OFFEN and a.aktion != AKTION_LOESCHEN
                and (a.benutzer_id or 0) == benutzer_id
                and (a.postfach or "").lower() == (postfach or "").lower()):
            a.status = STATUS_ERLEDIGT
            a.fehler_text = grund[:300]
            a.erledigt_am = datetime.now()


def _neuer_auftrag(aktion: str, termin_art: str, termin_id: int, benutzer_id: int,
                   postfach: str, event_id: str = "") -> OutlookAuftrag:
    return OutlookAuftrag(aktion=aktion, termin_art=termin_art, termin_id=int(termin_id),
                          benutzer_id=benutzer_id, postfach=postfach, event_id=event_id or "",
                          status=STATUS_OFFEN)


def _termin_zeiten(termin_art: str, termin) -> tuple[datetime | None, datetime | None]:
    if termin is None:
        return None, None
    return termin.beginn, termin.ende


def auftrag_einreihen(session: Session, aktion: str, termin_art: str, termin_id: int,
                      benutzer_ids=None) -> list[OutlookAuftrag]:
    """Je eingeteilter Person einen Auftrag einreihen (kein Graph-Aufruf). `aktion`
    anlegen | aendern legt fehlende Kopien an, aktualisiert vorhandene und löscht Kopien
    von Personen, die nicht mehr eingeteilt sind; loeschen entfernt alle Kopien.
    `benutzer_ids` = None → Personen aus Besetzung/ad_id/person_id. Personen ohne
    Postfach (HV ohne Friondo-Postfach, fehlende E-Mail, fehlendes Testpostfach) bekommen
    keinen Auftrag, sondern ein Ereignis im Stand „leer“ mit dem Hinweistext. Liefert die
    NEU angelegten Aufträge; der Aufrufer committet (flush hier)."""
    if termin_art not in TERMIN_ARTEN:
        return []
    termin = _termin_laden(session, termin_art, termin_id)
    if termin is None:
        return []
    ereignisse = _ereignisse_des_termins(session, termin_art, termin_id)
    # Altbestand ohne Ereigniszeile (nur outlook_event_id, Stand vor der Migration): als Kopie
    # aufnehmen – Projekt → Team-/Sammelkalender (benutzer_id 0), VOT → Person/„postfach|id“
    alt = _altbestand_aufnehmen(session, termin_art, termin, ereignisse)
    if alt is not None:
        ereignisse.append(alt)
    je_kopie: dict[tuple[int, str], OutlookEreignis] = {}
    for e in ereignisse:
        je_kopie[(e.benutzer_id or 0, (e.postfach or "").lower())] = e
    offene = _offene_auftraege(session, termin_art, termin_id)
    jetzt = datetime.now()
    neu: list[OutlookAuftrag] = []

    if aktion == AKTION_LOESCHEN:
        for e in ereignisse:
            if e.stand == STAND_GELOESCHT:
                continue
            if e.stand == STAND_LEER:
                e.stand = STAND_GELOESCHT
                continue
            _auftrag_ueberholen(offene, e.benutzer_id or 0, e.postfach, "überholt (Termin gelöscht)")
            if not e.event_id or e.stand == STAND_IN_OUTLOOK_GELOESCHT:
                e.stand = STAND_GELOESCHT          # nie angelegt bzw. in Outlook schon weg
                continue
            if _auftrag_offen(offene, AKTION_LOESCHEN, e.benutzer_id or 0, e.postfach):
                continue
            neu.append(_neuer_auftrag(AKTION_LOESCHEN, termin_art, termin_id, e.benutzer_id or 0,
                                      e.postfach, e.event_id))
        _fehler_auftraege_ueberholen(session, neu)
        session.add_all(neu)
        session.flush()
        return neu

    if aktion not in (AKTION_ANLEGEN, AKTION_AENDERN):
        return []
    ziel_ids = [int(b) for b in (benutzer_ids if benutzer_ids is not None
                                 else personen_fuer(session, termin_art, termin)) if b]
    demo = bool(getattr(termin, "demo", False)) if termin_art == ART_VOT else False
    ziele: list[tuple[int, str]] = []
    ohne_postfach: list[tuple[int, str]] = []
    gesehen: set[int] = set()
    for bid in ziel_ids:
        if bid in gesehen:
            continue
        gesehen.add(bid)
        postfach, grund = postfach_fuer(session, session.get(Benutzer, bid), demo=demo)
        if postfach:
            ziele.append((bid, postfach))
        else:
            ohne_postfach.append((bid, grund))
    team_postfach = team_postfach_fuer(session, termin_art, termin)
    if team_postfach:
        ziele.append((TEAM_KOPIE_ID, team_postfach))
    ziel_schluessel = {(bid, pf.lower()) for bid, pf in ziele}
    ziel_personen = {bid for bid, _ in ziele}
    # 1. Kopien, die nicht mehr gebraucht werden (Person aus der Besetzung genommen,
    #    Postfach gewechselt): löschen
    for (bid, pf_klein), e in je_kopie.items():
        if (bid, pf_klein) in ziel_schluessel or e.stand == STAND_GELOESCHT:
            continue
        if e.stand in (STAND_LEER, STAND_IN_OUTLOOK_GELOESCHT) or not e.event_id:
            _auftrag_ueberholen(offene, bid, e.postfach, "überholt (Person nicht mehr eingeteilt)")
            e.stand = STAND_GELOESCHT
            continue
        _auftrag_ueberholen(offene, bid, e.postfach, "überholt (Person nicht mehr eingeteilt)")
        if not _auftrag_offen(offene, AKTION_LOESCHEN, bid, e.postfach):
            neu.append(_neuer_auftrag(AKTION_LOESCHEN, termin_art, termin_id, bid, e.postfach,
                                      e.event_id))
    # 2. Zielkopien: vorhanden → aendern, sonst anlegen
    for bid, postfach in ziele:
        e = je_kopie.get((bid, postfach.lower()))
        if e is not None and e.stand in (STAND_OK, STAND_AUSSTEHEND, STAND_FEHLER):
            if e.event_id:
                if not (_auftrag_offen(offene, AKTION_AENDERN, bid, postfach)
                        or _auftrag_offen(offene, AKTION_ANLEGEN, bid, postfach)):
                    neu.append(_neuer_auftrag(AKTION_AENDERN, termin_art, termin_id, bid, postfach,
                                              e.event_id))
                if e.stand == STAND_FEHLER:
                    e.stand = STAND_AUSSTEHEND
                    e.fehler_text = ""
            else:
                # noch nie angelegt: ein offener anlegen-Auftrag nimmt die aktuellen Daten
                if not _auftrag_offen(offene, AKTION_ANLEGEN, bid, postfach):
                    neu.append(_neuer_auftrag(AKTION_ANLEGEN, termin_art, termin_id, bid, postfach))
                e.stand = STAND_AUSSTEHEND
                e.fehler_text = ""
            continue
        if e is None:
            e = OutlookEreignis(termin_art=termin_art, termin_id=int(termin_id), benutzer_id=bid,
                                postfach=postfach, event_id="", stand=STAND_AUSSTEHEND)
            session.add(e)
            je_kopie[(bid, postfach.lower())] = e
        else:                                   # geloescht / in Outlook gelöscht / leer → neu
            e.postfach = postfach
            e.event_id = ""
            e.stand = STAND_AUSSTEHEND
            e.fehler_text = ""
        e.beginn, e.ende = _termin_zeiten(termin_art, termin)
        e.letzte_aenderung = jetzt
        if not _auftrag_offen(offene, AKTION_ANLEGEN, bid, postfach):
            neu.append(_neuer_auftrag(AKTION_ANLEGEN, termin_art, termin_id, bid, postfach))
    # 3. Personen ohne Postfach: Hinweis am Termin (Stand „leer“), kein Auftrag
    for bid, grund in ohne_postfach:
        vorhandene = [e for (b, _pf), e in je_kopie.items() if b == bid]
        if any(e.stand in (STAND_OK, STAND_AUSSTEHEND, STAND_FEHLER) for e in vorhandene):
            continue                            # hat bereits eine echte Kopie (z. B. Postfach gelöscht)
        leer = next((e for e in vorhandene if e.stand in (STAND_LEER, STAND_GELOESCHT)), None)
        if leer is None:
            session.add(OutlookEreignis(termin_art=termin_art, termin_id=int(termin_id),
                                        benutzer_id=bid, postfach="", event_id="",
                                        stand=STAND_LEER, fehler_text=grund[:300],
                                        beginn=termin.beginn, ende=termin.ende))
        else:
            leer.stand = STAND_LEER
            leer.fehler_text = grund[:300]
    _ = ziel_personen
    _fehler_auftraege_ueberholen(session, neu)
    session.add_all(neu)
    session.flush()
    return neu


def _alt_event(session: Session, termin_art: str, termin) -> tuple[str, str]:
    """Postfach und Event-ID aus dem alten Feld outlook_event_id (v12/v15)."""
    wert = (getattr(termin, "outlook_event_id", "") or "").strip()
    if not wert:
        return "", ""
    if termin_art == ART_VOT:
        postfach, _, event_id = wert.partition("|")
        return (postfach.strip(), event_id.strip()) if event_id else ("", "")
    from app import outlook_kalender
    adresse, _kategorien, fehler = outlook_kalender._kalender_ziel(session, termin)
    return ("", "") if fehler else (adresse, wert)


def _alt_benutzer_id(session: Session, termin_art: str, termin) -> int:
    if termin_art == ART_VOT:
        return termin.ad_id or 0
    return TEAM_KOPIE_ID       # alte Projekt-Ereignisse lagen im Team-/Sammelkalender


def _altbestand_aufnehmen(session: Session, termin_art: str, termin, ereignisse) -> OutlookEreignis | None:
    """Altes Feld outlook_event_id ohne passende Ereigniszeile (Stand vor der Migration) als
    Kopie mit Stand ok aufnehmen, damit Änderung/Löschung den alten Eintrag erreichen."""
    wert = (getattr(termin, "outlook_event_id", "") or "").strip()
    if not wert:
        return None
    postfach, event_id = _alt_event(session, termin_art, termin)
    if not postfach or not event_id:
        return None
    if any((e.event_id or "") == event_id for e in ereignisse):
        return None
    e = OutlookEreignis(termin_art=termin_art, termin_id=int(termin.id),
                        benutzer_id=_alt_benutzer_id(session, termin_art, termin),
                        postfach=postfach, event_id=event_id, stand=STAND_OK,
                        beginn=termin.beginn, ende=termin.ende)
    session.add(e)
    session.flush()
    return e


# --- Ereignis-Inhalt (Betreff-Regel, Body, Kennzeichen) --------------------------------

def _plz_ort(plz: str, ort: str) -> str:
    return " ".join(t for t in ((plz or "").strip(), (ort or "").strip()) if t)


def betreff_bilden(art_name: str, kunde_name: str, plz_ort: str, nummer: str) -> str:
    """[ANNAHME Plan] „<Art>: <Kunde>, <PLZ Ort> (<Nummer>)“ – leere Teile entfallen."""
    kopf = ", ".join(t for t in ((kunde_name or "").strip(), (plz_ort or "").strip()) if t)
    text = f"{art_name}: {kopf}" if kopf else art_name
    if (nummer or "").strip():
        text += f" ({nummer.strip()})"
    return text[:255]


def kennzeichen_wert(termin_art: str, termin_id: int, benutzer_id: int) -> str:
    return f"{termin_art}:{int(termin_id)}:{int(benutzer_id or 0)}"


def _zeitfenster(beginn: datetime, ende: datetime | None, ganztaegig: bool,
                 standard_dauer: timedelta) -> tuple[dict, dict, bool]:
    if ganztaegig:
        start = beginn.replace(hour=0, minute=0, second=0, microsecond=0)
        letzter = (ende or beginn).replace(hour=0, minute=0, second=0, microsecond=0)
        if letzter < start:
            letzter = start
        schluss = letzter + timedelta(days=1)
        return ({"dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": ZEITZONE},
                {"dateTime": schluss.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": ZEITZONE}, True)
    schluss = ende if (ende is not None and ende > beginn) else beginn + standard_dauer
    return ({"dateTime": beginn.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": ZEITZONE},
            {"dateTime": schluss.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": ZEITZONE}, False)


def _daten_vot(session: Session, termin: VotTermin) -> dict:
    from app import kalender
    from app import objekte as objekte_modul
    vorgang = session.get(Vorgang, termin.vorgang_id) if termin.vorgang_id else None
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang is not None else None
    typ = (termin.typ or "vot")
    art_name = VOT_ART_NAMEN.get(typ, "VOT")
    zeilen: list[str] = []
    plz_ort, kunde_name, nummer = "", "", ""
    ort_text = termin.adresse or ""
    if kunde is not None and vorgang is not None:
        kunde_name = kunde.anzeige_name
        try:
            satz = objekte_modul.ausfuehrungsort(session, termin=termin, vorgang=vorgang, kunde=kunde)
            plz_ort = _plz_ort(satz.get("plz", ""), satz.get("ort", ""))
            ort_text = ort_text or satz.get("einzeilig", "")
        except Exception:   # noqa: BLE001 – Adresse ist Beiwerk
            plz_ort = _plz_ort(kunde.plz, kunde.ort)
        nummer = (kunde.kunden_nr or "").strip() or f"V-{vorgang.id}"
        rumpf = kalender._ereignis_rumpf(session, termin, vorgang, kunde)
        zeilen.append(f"Kunde: {kunde_name}")
        zeilen.append(f"Adresse: {ort_text or '-'}")
        zeilen.append(rumpf["body"]["content"])
    else:
        rumpf = {"location": {"displayName": ort_text}}
        zeilen.append(f"Adresse: {ort_text or '-'}")
    start, ende, ganztaegig = _zeitfenster(termin.beginn, termin.ende, False, timedelta(minutes=30))
    sparten = ((kunde.interesse or "").replace(",", "/") if kunde is not None else "")
    art_text = f"{art_name} {sparten}".strip()
    return {
        "subject": betreff_bilden(art_text, kunde_name, plz_ort, nummer),
        "body": {"contentType": "text", "content": "\n".join(zeilen)},
        "location": {"displayName": (rumpf.get("location") or {}).get("displayName", ort_text)},
        "start": start, "end": ende, "isAllDay": ganztaegig,
    }


def _daten_projekt(session: Session, termin: ProjektTermin) -> dict:
    from app import projektierung as kern
    from app.models import Gewerk, Projekt
    projekt = session.get(Projekt, termin.projekt_id) if termin.projekt_id else None
    gewerk = session.get(Gewerk, termin.gewerk_id) if termin.gewerk_id else None
    vorgang = None
    if projekt is not None and projekt.vorgang_id:
        vorgang = session.get(Vorgang, projekt.vorgang_id)
    elif getattr(termin, "vorgang_id", None):
        vorgang = session.get(Vorgang, termin.vorgang_id)
    # Kunde/Ort über die Kern-Helfer von Agent S (Service am Vorgang ohne Projekt: projekt_id 0
    # + vorgang_id → projektierung.termin_kunde / termin_adresse), Rückfall direkt über
    # Projekt/Vorgang/Kunde, solange die Helfer fehlen
    kunde = None
    termin_kunde = getattr(kern, "termin_kunde", None)
    if callable(termin_kunde):
        try:
            kunde = termin_kunde(session, termin)
        except Exception:   # noqa: BLE001 – Rückfall unten
            kunde = None
    if kunde is None:
        if projekt is not None:
            kunde = session.get(Kunde, projekt.kunde_id)
        elif vorgang is not None:
            kunde = session.get(Kunde, vorgang.kunde_id)
    art_name = kern.termin_art_name(termin)
    if termin.typ == "service":
        # Vorschlag S (4.2): „Service <Anlass>: <Kunde>, <PLZ Ort>“ (+ Projektnummer bei Projekt)
        anlass_namen = getattr(kern, "SERVICE_ANLASS_NAMEN", None) or dict(kern.SERVICE_ANLAESSE)
        art_name = f"Service {anlass_namen.get(termin.anlass or '', '')}".strip()
    plz_ort, ort_text = "", ""
    try:
        termin_adresse = getattr(kern, "termin_adresse", None)
        if callable(termin_adresse):
            satz = termin_adresse(session, termin)
            plz_ort, ort_text = satz.get("plz_ort", ""), satz.get("einzeilig", "")
        elif projekt is not None:
            satz = kern.projekt_ausfuehrungsort(session, projekt, gewerk)
            plz_ort, ort_text = satz.get("plz_ort", ""), satz.get("einzeilig", "")
        elif vorgang is not None:
            from app import objekte as objekte_modul
            satz = objekte_modul.ausfuehrungsort(session, vorgang=vorgang, kunde=kunde)
            plz_ort, ort_text = _plz_ort(satz.get("plz", ""), satz.get("ort", "")), satz.get("einzeilig", "")
    except Exception:   # noqa: BLE001 – Adresse ist Beiwerk
        pass
    if not plz_ort and kunde is not None:
        plz_ort = _plz_ort(kunde.plz, kunde.ort)
    if not ort_text and kunde is not None:
        ort_text = ", ".join(t for t in ((kunde.strasse or ""), _plz_ort(kunde.plz, kunde.ort)) if t)
    # Nummer: Projektnummer; Service ohne Projekt ohne Nummer (Vorschlag S); übrige Termine
    # ohne Projekt mit der Vorgangsnummer
    if projekt is not None:
        nummer = projekt.nummer
    elif termin.typ == "service" or vorgang is None:
        nummer = ""
    else:
        nummer = f"V-{vorgang.id}"
    zeilen = []
    if kunde is not None:
        zeilen.append(f"Kunde: {kunde.anzeige_name}" + (f", Telefon {kunde.telefon}" if kunde.telefon else ""))
    zeilen.append(f"Adresse: {ort_text or '-'}")
    if gewerk is not None:
        zeilen.append(f"Sparte: {gewerk.sparte}")
    if termin.typ == "service":
        anlass = dict(kern.SERVICE_ANLAESSE).get(termin.anlass or "", termin.anlass or "")
        if anlass:
            zeilen.append(f"Anlass: {anlass}")
    besetzung = kern.besetzung_namen(session, termin.id, kurz=False) if termin.typ in ("montage", "sub", "service") else ""
    if besetzung:
        zeilen.append(f"Besetzung: {besetzung}")
    if termin.notiz:
        zeilen.append(f"Notiz: {termin.notiz}")
    if gewerk is not None:
        try:
            werte = kern.steckbrief_daten(session, [gewerk.id])[gewerk.id]
            for feld, name in kern.steckbrief_felder(gewerk.sparte)[:8]:
                if feld in werte and werte[feld].wert:
                    zeilen.append(f"{name}: {werte[feld].wert}")
        except Exception:   # noqa: BLE001 – Steckbrief ist Beiwerk
            pass
    basis = config.BASIS_URL.rstrip("/")
    if projekt is not None:
        zeilen.append(f"Projektakte: {basis}/projektierung/projekt/{projekt.id}#termine")
    elif vorgang is not None:
        zeilen.append(f"Vorgangsakte: {basis}/vorgaenge/{vorgang.id}#termine")
    ganztaegig = bool(termin.ganztaegig) and termin.beginn.time() == datetime.min.time()
    start, ende, ganz = _zeitfenster(termin.beginn, termin.ende, ganztaegig, timedelta(hours=8))
    return {
        "subject": betreff_bilden(art_name, kunde.anzeige_name if kunde is not None else "", plz_ort, nummer),
        "body": {"contentType": "text", "content": "\n".join(zeilen)},
        "location": {"displayName": ort_text},
        "start": start, "end": ende, "isAllDay": ganz,
    }


def ereignis_daten(session: Session, termin_art: str, termin, benutzer_id: int = 0) -> dict:
    """Graph-Ereignis für eine Kopie: Betreff nach Regel, Body (Kunde, Adresse, Link ins
    Tool), location, Kategorie „Friondo-Tool“, Kennzeichen friondoTerminId, showAs busy.
    Nur Datenbankarbeit – kein Netz."""
    daten = _daten_vot(session, termin) if termin_art == ART_VOT else _daten_projekt(session, termin)
    daten["categories"] = [KATEGORIE]
    daten["showAs"] = SHOW_AS
    daten["singleValueExtendedProperties"] = [
        {"id": PROPERTY_ID, "value": kennzeichen_wert(termin_art, termin.id, benutzer_id)}]
    return daten


# --- Lauf outlook-sync (Warteschlange → Graph) -----------------------------------------

def graph_aktiv():
    """aktiv-Bedingung beider Läufe: Graph in der .env eingerichtet (GRAPH_CLIENT_ID)."""
    from app import graph_versand
    return True if graph_versand.konfiguriert() else "Graph nicht eingerichtet"


def _nicht_verbunden() -> str:
    """Zustandstext ohne Token je Modus (graph_versand.nicht_verbunden_text, Agent G) –
    ein Zustand, kein Fehler; Rückfall auf den festen Text."""
    from app import graph_versand
    funktion = getattr(graph_versand, "nicht_verbunden_text", None)
    try:
        return str(funktion()) if funktion is not None else NICHT_ANGEMELDET
    except Exception:   # noqa: BLE001
        return NICHT_ANGEMELDET


def _basis(postfach: str) -> str:
    from app import graph_versand
    return graph_versand.basis_pfad(postfach)


def _ohne_zugriff_merken(postfach: str, benutzer_id: int | None) -> None:
    schluessel = (postfach or "").strip().lower()
    if not schluessel:
        return
    _OHNE_ZUGRIFF[schluessel] = {"benutzer_id": benutzer_id or None, "zeit": datetime.now(),
                                 "postfach": (postfach or "").strip()}


def _ohne_zugriff_entfernen(postfach: str) -> None:
    _OHNE_ZUGRIFF.pop((postfach or "").strip().lower(), None)


def ohne_zugriff_leeren() -> None:
    _OHNE_ZUGRIFF.clear()


def _spiegel_setzen(session: Session, termin_art: str, termin_id: int) -> None:
    """Altes Feld outlook_event_id = erste Kopie mit Stand ok (gespiegelt, v12/v15-Leser)."""
    termin = _termin_laden(session, termin_art, termin_id)
    if termin is None:
        return
    session.flush()                     # SessionLocal hat autoflush=False – Stand erst schreiben
    erste = (session.query(OutlookEreignis)
             .filter(OutlookEreignis.termin_art == termin_art,
                     OutlookEreignis.termin_id == int(termin_id),
                     OutlookEreignis.stand == STAND_OK,
                     OutlookEreignis.event_id != "")
             .order_by(OutlookEreignis.id).first())
    if termin_art == ART_VOT:
        termin.outlook_event_id = f"{erste.postfach}|{erste.event_id}" if erste is not None else None
    else:
        termin.outlook_event_id = erste.event_id if erste is not None else ""
        if erste is not None and termin.outlook_fehler and not termin.outlook_fehler.startswith("in Outlook"):
            termin.outlook_fehler = ""


def _ereignis_zum_auftrag(session: Session, auftrag: OutlookAuftrag) -> OutlookEreignis | None:
    return (session.query(OutlookEreignis)
            .filter(OutlookEreignis.termin_art == auftrag.termin_art,
                    OutlookEreignis.termin_id == auftrag.termin_id,
                    OutlookEreignis.benutzer_id == (auftrag.benutzer_id or 0),
                    OutlookEreignis.stand != STAND_GELOESCHT)
            .order_by(OutlookEreignis.id.desc()).first())


def _auftraege_lesen(session: Session) -> list[dict]:
    """Lesephase: offene Aufträge (Block) samt fertigem Ereignis-Inhalt – ohne Netz."""
    liste = []
    for a in (session.query(OutlookAuftrag)
              .filter(OutlookAuftrag.status == STATUS_OFFEN)
              .order_by(OutlookAuftrag.id).limit(BLOCK_GROESSE)):
        eintrag = {"id": a.id, "aktion": a.aktion, "termin_art": a.termin_art,
                   "termin_id": a.termin_id, "benutzer_id": a.benutzer_id or 0,
                   "postfach": a.postfach, "event_id": a.event_id or "", "daten": None,
                   "fehler": ""}
        if a.aktion in (AKTION_ANLEGEN, AKTION_AENDERN):
            termin = _termin_laden(session, a.termin_art, a.termin_id)
            if termin is None or termin.beginn is None:
                # Termin inzwischen gelöscht: eine schon angelegte Kopie wird entfernt
                # (verwaiste Kopie), sonst gilt der Auftrag als erledigt (kein Fehler)
                ereignis = _ereignis_zum_auftrag(session, a)
                if ereignis is not None and ereignis.event_id and ereignis.stand in (STAND_OK, STAND_FEHLER):
                    eintrag["aktion"] = AKTION_LOESCHEN
                    eintrag["event_id"] = ereignis.event_id
                    eintrag["postfach"] = ereignis.postfach or eintrag["postfach"]
                else:
                    eintrag["fehler"] = TERMIN_WEG
            else:
                ereignis = _ereignis_zum_auftrag(session, a)
                bid = a.benutzer_id or 0
                if bid:
                    passt = bid in personen_fuer(session, a.termin_art, termin)
                else:
                    team_pf = team_postfach_fuer(session, a.termin_art, termin)
                    passt = bool(team_pf) and team_pf.lower() == (a.postfach or "").lower()
                if not passt:
                    # Person nicht (mehr) eingeteilt – etwa ein Auftrag eines gelöschten Termins,
                    # dessen ID SQLite neu vergeben hat: vorhandene Kopie löschen, sonst erledigt
                    if (ereignis is not None and ereignis.event_id
                            and ereignis.stand in (STAND_OK, STAND_FEHLER, STAND_AUSSTEHEND)):
                        eintrag["aktion"] = AKTION_LOESCHEN
                        eintrag["event_id"] = ereignis.event_id
                        eintrag["postfach"] = ereignis.postfach or eintrag["postfach"]
                    else:
                        eintrag["fehler"] = PERSON_WEG
                    liste.append(eintrag)
                    continue
                if a.aktion == AKTION_AENDERN:
                    eintrag["event_id"] = a.event_id or (ereignis.event_id if ereignis is not None else "")
                    if not eintrag["event_id"]:
                        eintrag["aktion"] = AKTION_ANLEGEN
                try:
                    eintrag["daten"] = ereignis_daten(session, a.termin_art, termin, a.benutzer_id or 0)
                except Exception as problem:   # noqa: BLE001 – Inhalt nicht baubar = Fehler des Auftrags
                    eintrag["fehler"] = f"Ereignis-Inhalt: {problem}"[:300]
        liste.append(eintrag)
    return liste


def _graph_auftrag(token: str, eintrag: dict) -> dict:
    """Netzphase je Auftrag (ohne Sitzung): POST / PATCH / DELETE am Postfach."""
    from app import graph_versand
    basis = _basis(eintrag["postfach"])
    aktion = eintrag["aktion"]
    if aktion == AKTION_LOESCHEN:
        if not eintrag["event_id"]:
            return {"ok": True, "event_id": ""}
        try:
            graph_versand._graph_aufruf(
                "DELETE", f"{basis}/events/{urllib.parse.quote(eintrag['event_id'])}", token)
        except urllib.error.HTTPError as fehler:
            if fehler.code != 404:          # schon weg = erledigt
                raise
        return {"ok": True, "event_id": eintrag["event_id"]}
    if aktion == AKTION_AENDERN:
        try:
            graph_versand._graph_aufruf(
                "PATCH", f"{basis}/events/{urllib.parse.quote(eintrag['event_id'])}", token,
                eintrag["daten"])
        except urllib.error.HTTPError as fehler:
            if fehler.code == 404:
                return {"ok": False, "in_outlook_geloescht": True}
            raise
        return {"ok": True, "event_id": eintrag["event_id"]}
    antwort = graph_versand._graph_aufruf("POST", f"{basis}/events", token, eintrag["daten"])
    return {"ok": True, "event_id": str(antwort.get("id", "") or "")}


def _auftrag_abschliessen(session: Session, eintrag: dict, ergebnis: dict | None,
                          fehler_text: str, zugriff_verweigert: bool = False) -> str:
    """Schreibphase (kurze Sitzung): Auftrag + Ereignis + Spiegel. Liefert erledigt |
    fehler | wiederholen."""
    auftrag = session.get(OutlookAuftrag, eintrag["id"])
    if auftrag is None:
        return "fehler"
    ereignis = _ereignis_zum_auftrag(session, auftrag)
    jetzt = datetime.now()
    if ergebnis is not None and ergebnis.get("ok"):
        auftrag.status = STATUS_ERLEDIGT
        auftrag.erledigt_am = jetzt
        auftrag.fehler_text = ""
        if ereignis is not None:
            if eintrag["aktion"] == AKTION_LOESCHEN:
                ereignis.stand = STAND_GELOESCHT
                if _termin_laden(session, auftrag.termin_art, auftrag.termin_id) is None:
                    # Termin im Tool schon gelöscht: Ereigniszeile entfernen, damit eine neu
                    # vergebene Termin-ID (SQLite) keine verwaiste Kopie erbt
                    session.delete(ereignis)
                    session.flush()
                    return "erledigt"
            else:
                ereignis.event_id = ergebnis.get("event_id") or ereignis.event_id
                ereignis.stand = STAND_OK
                ereignis.fehler_text = ""
                termin = _termin_laden(session, auftrag.termin_art, auftrag.termin_id)
                if termin is not None:
                    ereignis.beginn, ereignis.ende = termin.beginn, termin.ende
            ereignis.letzte_aenderung = jetzt
        _spiegel_setzen(session, auftrag.termin_art, auftrag.termin_id)
        return "erledigt"
    if ergebnis is not None and ergebnis.get("in_outlook_geloescht"):
        auftrag.status = STATUS_ERLEDIGT
        auftrag.erledigt_am = jetzt
        auftrag.fehler_text = "Ereignis in Outlook nicht mehr vorhanden"
        if ereignis is not None and ereignis.stand != STAND_IN_OUTLOOK_GELOESCHT:
            _in_outlook_geloescht(session, ereignis, "")
        _spiegel_setzen(session, auftrag.termin_art, auftrag.termin_id)
        return "fehler"
    if fehler_text in (TERMIN_WEG, PERSON_WEG):
        # Termin gelöscht bzw. Person nicht mehr eingeteilt, bevor die Kopie angelegt wurde:
        # nichts zu übertragen
        auftrag.status = STATUS_ERLEDIGT
        auftrag.erledigt_am = jetzt
        auftrag.fehler_text = fehler_text
        if ereignis is not None and not ereignis.event_id:
            session.delete(ereignis)        # nie angelegt – Zeile weg (ID kann neu vergeben werden)
            session.flush()
        return "erledigt"
    auftrag.versuche = (auftrag.versuche or 0) + 1
    auftrag.fehler_text = fehler_text[:300]
    # Vertrag G: HTTP 403 (Postfach nicht in der Zugriffsgruppe) → sofort Status „fehler“ mit
    # dem Postfach aus der Ausnahme – die Verbindungs-Seite listet es (postfaecher_ohne_zugriff);
    # der Lauf versucht solche Aufträge stündlich erneut (_zugriff_erneut_oeffnen), bis die IT
    # das Postfach aufgenommen hat (kein erneutes Speichern nötig). Andere Fehler: 3 Versuche.
    if auftrag.versuche >= VERSUCHE_MAX or zugriff_verweigert:
        auftrag.status = STATUS_FEHLER
        auftrag.erledigt_am = jetzt
        if ereignis is not None:
            ereignis.stand = STAND_FEHLER
            ereignis.fehler_text = fehler_text[:300]
            ereignis.letzte_aenderung = jetzt
        termin = _termin_laden(session, auftrag.termin_art, auftrag.termin_id)
        if termin is not None and auftrag.termin_art == ART_PROJEKT:
            termin.outlook_fehler = f"Outlook-Sync fehlgeschlagen: {fehler_text}"[:300]
        if not zugriff_verweigert:        # 403 steht bereits einmal je Stunde im Protokoll
            try:
                from app import fehlerprotokoll
                fehlerprotokoll.eintragen_text(
                    "Outlook-Sync",
                    f"Auftrag {auftrag.id} ({auftrag.aktion} {auftrag.termin_art}:{auftrag.termin_id}) "
                    f"für {auftrag.postfach} nach {VERSUCHE_MAX} Versuchen fehlgeschlagen",
                    detail=fehler_text[:1000])
            except Exception:   # noqa: BLE001 – Protokoll darf den Lauf nie stören
                pass
        return "fehler"
    if ereignis is not None:
        ereignis.fehler_text = f"Versuch {auftrag.versuche}/{VERSUCHE_MAX}: {fehler_text}"[:300]
    return "wiederholen"


def sync_lauf() -> dict:
    """Lauf outlook-sync (60 s): offene Aufträge (Block ≤ 50) lesen → Sitzung zu → je
    Auftrag Graph → kurze Sitzung schreiben. Ohne Token bleiben die Aufträge offen."""
    from app import graph_versand
    from app.db import kurz
    with kurz() as s:
        verwaiste_aufraeumen(s)
        _zugriff_erneut_oeffnen(s)
        eintraege = _auftraege_lesen(s)
    if not eintraege:
        return {"offen": 0, "erledigt": 0, "fehler": 0, "wiederholen": 0}
    token = graph_versand._token()
    if token is None:
        return {"ergebnis": _nicht_verbunden(), "offen": len(eintraege)}
    zaehler = {"offen": len(eintraege), "erledigt": 0, "fehler": 0, "wiederholen": 0}
    for eintrag in eintraege:
        ergebnis, fehler_text, verweigert = None, eintrag.get("fehler") or "", False
        if not fehler_text:
            try:
                ergebnis = _graph_auftrag(token, eintrag)
                _ohne_zugriff_entfernen(eintrag["postfach"])
            except graph_versand.GraphZugriffVerweigert as problem:
                fehler_text, verweigert = str(problem), True
                _ohne_zugriff_merken(eintrag["postfach"], eintrag["benutzer_id"] or None)
            except Exception as problem:   # noqa: BLE001 – je Auftrag abgesichert
                fehler_text = f"{type(problem).__name__}: {problem}"
        try:
            with kurz() as s:
                stand = _auftrag_abschliessen(s, eintrag, ergebnis, fehler_text, verweigert)
        except Exception as problem:   # noqa: BLE001 – Schreibfehler eines Auftrags blockiert nicht
            _logger.error("outlook-sync: Auftrag %s nicht gespeichert: %s", eintrag["id"], problem,
                          exc_info=True)
            stand = "fehler"
        zaehler[stand] = zaehler.get(stand, 0) + 1
    return zaehler


# --- Lauf outlook-ruecklesen (Graph → Tool) --------------------------------------------

def _zeit_aus_graph(daten: dict | None, ganztaegig: bool = False) -> datetime | None:
    """Graph liefert dateTime + timeZone (ohne Prefer-Header UTC) → lokale Zeit."""
    roh = (daten or {}).get("dateTime") or ""
    zone = ((daten or {}).get("timeZone") or "").strip().upper()
    try:
        wert = datetime.fromisoformat(roh[:19])
    except ValueError:
        return None
    if ganztaegig:
        return wert.replace(hour=0, minute=0, second=0, microsecond=0)
    if zone == "UTC":
        wert = wert.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
    return wert.replace(microsecond=0)


def _kennzeichen_aus_event(eintrag: dict) -> str:
    for p in eintrag.get("singleValueExtendedProperties") or []:
        if str(p.get("id", "")).strip().lower() == PROPERTY_ID.lower():
            return str(p.get("value", "") or "").strip()
    return ""


def _calendar_view(token: str, postfach: str, von: datetime, bis: datetime) -> list[dict]:
    """Netzphase (ohne Sitzung): calendarView mit Kennzeichen, seitenweise."""
    from app import graph_versand
    pfad = (f"{_basis(postfach)}/calendarView?"
            f"startDateTime={von.strftime('%Y-%m-%dT%H:%M:%S')}"
            f"&endDateTime={bis.strftime('%Y-%m-%dT%H:%M:%S')}"
            f"&$top={CALENDARVIEW_TOP}"
            "&$select=id,start,end,subject,showAs,isCancelled,isAllDay,singleValueExtendedProperties"
            "&$expand=singleValueExtendedProperties($filter=id%20eq%20'"
            + urllib.parse.quote(PROPERTY_ID) + "')")
    eintraege: list[dict] = []
    for _ in range(CALENDARVIEW_SEITEN_MAX):
        antwort = graph_versand._graph_aufruf("GET", pfad, token)
        eintraege.extend(antwort.get("value", []) or [])
        weiter = antwort.get("@odata.nextLink") or ""
        if not weiter:
            break
        pfad = weiter[len(graph_versand.GRAPH):] if weiter.startswith(graph_versand.GRAPH) else weiter
        if not pfad.startswith("/"):
            break
    return eintraege


def _personen_mit_terminen(session: Session, von: datetime, bis: datetime) -> dict:
    """Lesephase: je Person (bzw. Team-Postfach) Postfach, Name und die erwarteten
    Tool-Kopien im Zeitfenster – ohne Netz."""
    personen: dict = {}
    ids: set[int] = set()
    for t in (session.query(VotTermin)
              .filter(VotTermin.ad_id.isnot(None), VotTermin.beginn >= von, VotTermin.beginn < bis,
                      VotTermin.status.in_(("geplant", "bestaetigt", "vorgemerkt")),
                      VotTermin.typ != "sperrzeit")):
        ids.add(t.ad_id)
    projekt_ids = [t.id for t in session.query(ProjektTermin.id)
                   .filter(ProjektTermin.beginn >= von, ProjektTermin.beginn < bis)]
    if projekt_ids:
        from app import projektierung as kern
        for liste in kern.besetzung_map(session, projekt_ids).values():
            ids.update(liste)
        for t in (session.query(ProjektTermin)
                  .filter(ProjektTermin.id.in_(projekt_ids), ProjektTermin.person_id.isnot(None))):
            ids.add(t.person_id)
    ereignisse = (session.query(OutlookEreignis)
                  .filter(OutlookEreignis.stand == STAND_OK, OutlookEreignis.event_id != "",
                          OutlookEreignis.beginn >= von, OutlookEreignis.beginn < bis)
                  .order_by(OutlookEreignis.id).all())
    for e in ereignisse:
        if e.benutzer_id:
            ids.add(e.benutzer_id)
    for bid in sorted(i for i in ids if i):
        benutzer = session.get(Benutzer, bid)
        if benutzer is None or not benutzer.aktiv:
            continue
        postfach, _grund = postfach_fuer(session, benutzer)
        if not postfach:
            continue
        personen[bid] = {"benutzer_id": bid, "name": benutzer.name, "postfach": postfach,
                         "kopien": {}, "kennzeichen": {}}
    for e in ereignisse:
        if e.benutzer_id and e.benutzer_id in personen:
            ziel = personen[e.benutzer_id]
        elif not e.benutzer_id and e.postfach:
            schluessel = f"team:{e.postfach.lower()}"
            ziel = personen.setdefault(schluessel, {"benutzer_id": 0, "name": f"Team-Kalender {e.postfach}",
                                                     "postfach": e.postfach, "kopien": {}, "kennzeichen": {}})
        else:
            continue
        ziel["kopien"][e.event_id] = e.id
        ziel["kennzeichen"][kennzeichen_wert(e.termin_art, e.termin_id, e.benutzer_id or 0)] = e.id
    return personen


def _name_von(session: Session, benutzer_id: int) -> str:
    b = session.get(Benutzer, benutzer_id) if benutzer_id else None
    return b.name if b is not None else "Outlook"


def _termin_nachziehen(session: Session, ereignis: OutlookEreignis, beginn: datetime,
                       ende: datetime | None, ganztaegig: bool, name: str,
                       bereits: set) -> bool:
    """Tool-Termin aus Outlook übernehmen (erste Änderung je Termin gewinnt; übrige Kopien
    werden per Auftrag aendern angeglichen). Verlauf/Aktivität „aus Outlook übernommen“."""
    schluessel = (ereignis.termin_art, ereignis.termin_id)
    if schluessel in bereits:
        return False
    termin = _termin_laden(session, ereignis.termin_art, ereignis.termin_id)
    if termin is None or termin.beginn is None:
        return False
    if ereignis.termin_art == ART_PROJEKT and ganztaegig:
        neu_ende = (ende - timedelta(days=1)) if ende is not None else None
        if neu_ende is not None and neu_ende < beginn:
            neu_ende = beginn
    else:
        neu_ende = ende
    if termin.beginn == beginn and (neu_ende is None or termin.ende == neu_ende):
        ereignis.beginn, ereignis.ende = termin.beginn, termin.ende
        return False
    bereits.add(schluessel)
    alt_text = termin.beginn.strftime("%d.%m.%Y %H:%M")
    termin.beginn = beginn
    if neu_ende is not None:
        termin.ende = neu_ende
    neu_text = beginn.strftime("%d.%m.%Y %H:%M")
    text = f"Termin aus Outlook übernommen von {name}: {alt_text} → {neu_text}"
    if ereignis.termin_art == ART_PROJEKT:
        from app import projektierung as kern
        from app.models import Gewerk
        termin.dauer_tage = max(1, ((termin.ende or termin.beginn).date() - termin.beginn.date()).days + 1)
        if termin.projekt_id:
            kern.verlauf(session, termin.projekt_id, f"{text} ({kern.termin_art_name(termin)})",
                         gewerk_id=termin.gewerk_id)
        elif getattr(termin, "vorgang_id", None):
            from app import leadmanagement as lm
            lm.aktivitaet(session, termin.vorgang_id, "termin", f"{text} ({kern.termin_art_name(termin)})")
        gewerk = session.get(Gewerk, termin.gewerk_id) if termin.gewerk_id else None
        if gewerk is not None and termin.typ in ("feinplanung", "montage"):
            kern.faelligkeiten_nachberechnen(session, gewerk)
    else:
        from app import leadmanagement as lm
        if termin.vorgang_id:
            lm.aktivitaet(session, termin.vorgang_id, "termin", text)
            # Nachtrag 15.10.2026 (O-R5): keine automatische Kundenmail – Glocke an den Leadmanager
            # (Rückfall Leitung), damit die Terminänderung bewusst an den Kunden geht
            vorgang = session.get(Vorgang, termin.vorgang_id)
            empfaenger = [vorgang.leadmanager_id] if vorgang is not None and vorgang.leadmanager_id else []
            if not empfaenger:
                from app import lead_termin
                empfaenger = lead_termin.leitung_ids(session)
            if empfaenger:
                lm.benachrichtigen(session, empfaenger,
                                   (text + " – bitte den Kunden über die Terminänderung informieren")[:500],
                                   f"/lead-management/lead/{termin.vorgang_id}", art="terminaenderung")
    ereignis.beginn, ereignis.ende = termin.beginn, termin.ende
    ereignis.letzte_aenderung = datetime.now()
    session.flush()
    # übrige Kopien angleichen (die gewinnende Kopie bekommt denselben Stand – idempotent)
    auftrag_einreihen(session, AKTION_AENDERN, ereignis.termin_art, ereignis.termin_id)
    return True


def _in_outlook_geloescht(session: Session, ereignis: OutlookEreignis, name: str) -> None:
    """Kopie fehlt in Outlook: Stand setzen, Termin im Tool markieren (kein stilles
    Löschen), Glocke an Projektierung bzw. Leadmanager."""
    if ereignis.stand == STAND_IN_OUTLOOK_GELOESCHT:
        return
    ereignis.stand = STAND_IN_OUTLOOK_GELOESCHT
    ereignis.fehler_text = (f"in Outlook gelöscht ({name})" if name else "in Outlook gelöscht")[:300]
    ereignis.letzte_aenderung = datetime.now()
    termin = _termin_laden(session, ereignis.termin_art, ereignis.termin_id)
    if termin is None:
        return
    wer = f" von {name}" if name else ""
    if ereignis.termin_art == ART_PROJEKT:
        from app import projektierung as kern
        from app.models import Projekt
        termin.outlook_fehler = "in Outlook gelöscht"
        zeit = termin.beginn.strftime("%d.%m.%Y") if termin.beginn else "?"
        text = (f"Outlook-Kopie des Termins {kern.termin_art_name(termin)} {zeit} wurde in Outlook"
                f"{wer} gelöscht – der Termin im Tool bleibt bestehen, bitte prüfen")
        empfaenger: list[int] = []
        link = "/projektierung"
        if termin.projekt_id:
            kern.verlauf(session, termin.projekt_id, text, gewerk_id=termin.gewerk_id)
            projekt = session.get(Projekt, termin.projekt_id)
            if projekt is not None and projekt.projektleiter_id:
                empfaenger.append(projekt.projektleiter_id)
            link = f"/projektierung/projekt/{termin.projekt_id}#termine"
        elif getattr(termin, "vorgang_id", None):
            from app import leadmanagement as lm
            lm.aktivitaet(session, termin.vorgang_id, "termin", text)
            link = f"/vorgaenge/{termin.vorgang_id}"
        if termin.erstellt_von:
            empfaenger.append(termin.erstellt_von)
        if not empfaenger:
            empfaenger = [b.id for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
                          if b.basisrolle == "projektierung"]
        if empfaenger:
            # [ANNAHME O] bestehende Projekt-Glockenart „kommentar“ (keine neue Art)
            kern.benachrichtigen(session, empfaenger, text[:500], link, art="kommentar")
    else:
        from app import leadmanagement as lm
        zusatz = f"in Outlook gelöscht{wer}"
        termin.grund_text = ((termin.grund_text or "").strip() + (" · " if termin.grund_text else "") + zusatz)[:500]
        vorgang = session.get(Vorgang, termin.vorgang_id) if termin.vorgang_id else None
        zeit = termin.beginn.strftime("%d.%m.%Y %H:%M") if termin.beginn else "?"
        text = (f"Outlook-Kopie des Termins {zeit} wurde in Outlook{wer} gelöscht – der Termin im "
                "Tool bleibt bestehen, bitte prüfen")
        if vorgang is not None:
            lm.aktivitaet(session, vorgang.id, "termin", text)
            empfaenger = [vorgang.leadmanager_id] if vorgang.leadmanager_id else []
            if not empfaenger:
                from app import lead_termin
                empfaenger = lead_termin.leitung_ids(session)
            lm.benachrichtigen(session, empfaenger, text[:500], f"/lead-management/lead/{vorgang.id}",
                               art="terminaenderung")
    session.flush()


def _person_verarbeiten(session: Session, info: dict, eintraege: list[dict], bereits: set) -> dict:
    """Schreibphase je Person: Tool-Kopien abgleichen, fremde Einträge als Belegtzeit."""
    bid = info["benutzer_id"]
    name = info["name"]
    kopien: dict = dict(info["kopien"])
    kennzeichen: dict = dict(info["kennzeichen"])
    gefunden: set[int] = set()
    belegt: list[tuple[datetime, datetime, str]] = []
    zaehler = {"geaendert": 0, "fremd": 0}
    jetzt = datetime.now()
    for eintrag in eintraege:
        event_id = str(eintrag.get("id", "") or "")
        marke = _kennzeichen_aus_event(eintrag)
        ereignis_id = kopien.get(event_id) or (kennzeichen.get(marke) if marke else None)
        ganztaegig = bool(eintrag.get("isAllDay"))
        beginn = _zeit_aus_graph(eintrag.get("start"), ganztaegig)
        ende = _zeit_aus_graph(eintrag.get("end"), ganztaegig)
        if ereignis_id is None and not marke:
            if eintrag.get("isCancelled") or str(eintrag.get("showAs", "")).lower() == "free":
                continue
            if beginn is not None and ende is not None and ende > beginn:
                belegt.append((beginn, ende, event_id))
            continue
        if ereignis_id is None:
            continue                            # fremdes Kennzeichen (anderer Mandant) – nie anfassen
        if eintrag.get("isCancelled"):
            continue                            # gilt als gelöscht
        gefunden.add(ereignis_id)
        ereignis = session.get(OutlookEreignis, ereignis_id)
        if ereignis is None or ereignis.stand != STAND_OK:
            continue
        if event_id and ereignis.event_id != event_id:
            ereignis.event_id = event_id
        if beginn is None:
            continue
        if _termin_nachziehen(session, ereignis, beginn, ende, ganztaegig, name, bereits):
            zaehler["geaendert"] += 1
    for event_id, ereignis_id in kopien.items():
        if ereignis_id in gefunden:
            continue
        ereignis = session.get(OutlookEreignis, ereignis_id)
        if ereignis is not None and ereignis.stand == STAND_OK:
            _in_outlook_geloescht(session, ereignis, name if bid else "")
            zaehler["geloescht"] = zaehler.get("geloescht", 0) + 1
    if bid:
        session.query(OutlookBelegt).filter(OutlookBelegt.benutzer_id == bid).delete(
            synchronize_session=False)
        for von, bis, event_id in belegt:
            session.add(OutlookBelegt(benutzer_id=bid, von=von, bis=bis, event_id=event_id[:300],
                                      stand=jetzt))
        zaehler["fremd"] = len(belegt)
    session.flush()
    return zaehler


def ruecklesen_lauf() -> dict:
    """Lauf outlook-ruecklesen (300 s): Token → Personen lesen (kurze Sitzung) → je Person
    calendarView ohne Sitzung → kurze Sitzung schreiben. 403 je Person → Liste für die
    Verbindungs-Seite (postfaecher_ohne_zugriff)."""
    from app import graph_versand
    from app.db import kurz
    token = graph_versand._token()
    if token is None:
        return {"ergebnis": _nicht_verbunden()}
    von = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    bis = von + timedelta(weeks=RUECKLESE_WOCHEN)
    with kurz() as s:
        personen = _personen_mit_terminen(s, von, bis)
    zaehler = {"personen": len(personen), "geaendert": 0, "geloescht": 0, "belegt": 0,
               "fehler": 0, "ohne_zugriff": 0}
    bereits: set = set()
    for info in personen.values():
        try:
            eintraege = _calendar_view(token, info["postfach"], von, bis)
        except graph_versand.GraphZugriffVerweigert:
            _ohne_zugriff_merken(info["postfach"], info["benutzer_id"] or None)
            zaehler["ohne_zugriff"] += 1
            continue
        except Exception as problem:   # noqa: BLE001 – je Person abgesichert
            _logger.error("outlook-ruecklesen: %s nicht gelesen: %s", info["postfach"], problem)
            zaehler["fehler"] += 1
            continue
        _ohne_zugriff_entfernen(info["postfach"])
        try:
            with kurz() as s:
                teil = _person_verarbeiten(s, info, eintraege, bereits)
        except Exception as problem:   # noqa: BLE001 – Schreibfehler einer Person blockiert nicht
            _logger.error("outlook-ruecklesen: %s nicht verarbeitet: %s", info["postfach"], problem,
                          exc_info=True)
            zaehler["fehler"] += 1
            continue
        zaehler["geaendert"] += teil.get("geaendert", 0)
        zaehler["geloescht"] += teil.get("geloescht", 0)
        zaehler["belegt"] += teil.get("fremd", 0)
    return zaehler


# --- Belegt-Cache, Status, Zugriffsgruppe (Verträge K, S, G) -----------------------------

def belegt(session: Session, benutzer_ids, von: datetime, bis: datetime) -> dict[int, list]:
    """Belegtzeiten fremder Outlook-Einträge aus dem Cache: {benutzer_id: [(von, bis), …]}
    – nie Graph im Request (Vertrag K / Terminassistent)."""
    ids = [int(b) for b in (benutzer_ids or []) if b]
    ergebnis: dict[int, list] = {bid: [] for bid in ids}
    if not ids:
        return ergebnis
    for z in (session.query(OutlookBelegt)
              .filter(OutlookBelegt.benutzer_id.in_(ids), OutlookBelegt.von < bis,
                      OutlookBelegt.bis > von)
              .order_by(OutlookBelegt.von)):
        ergebnis.setdefault(z.benutzer_id, []).append((z.von, z.bis))
    return ergebnis


def belegt_fuer(session: Session, ad, von: datetime, bis: datetime) -> list | None:
    """Wie kalender.frei_belegt (Signatur-Ersatz im Terminassistenten): None, wenn
    kalender_sync aus ist oder die Person Handelsvertreter ohne Postfach ist; sonst die
    Belegtzeiten aus dem Cache (leer = nichts belegt)."""
    from app import kalender
    if ad is None or not kalender.aktiv(session):
        return None
    if ist_handelsvertreter(session, ad):
        postfach, _grund = postfach_fuer(session, ad)
        if not postfach:
            return None
    return belegt(session, [ad.id], von, bis).get(ad.id, [])


def letzter_lauf(name: str) -> datetime | None:
    try:
        from app import scheduler
        lauf = scheduler.holen(name)
        return lauf.letzter_start if lauf is not None else None
    except Exception:   # noqa: BLE001
        return None


def status_map(session: Session, termin_art: str, termin_ids) -> dict[int, dict]:
    """{termin_id: {stand, text, kopien[{name, stand, fehler, postfach}]}} für mehrere
    Termine (eine Abfrage). Kopien im Stand „geloescht“ zählen nicht."""
    ids = sorted({int(t) for t in (termin_ids or []) if t})
    ergebnis: dict[int, dict] = {tid: {"stand": STAND_LEER, "text": "kein Outlook-Eintrag", "kopien": []}
                                 for tid in ids}
    if not ids:
        return ergebnis
    ereignisse = (session.query(OutlookEreignis)
                  .filter(OutlookEreignis.termin_art == termin_art,
                          OutlookEreignis.termin_id.in_(ids),
                          OutlookEreignis.stand != STAND_GELOESCHT)
                  .order_by(OutlookEreignis.id).all())
    benutzer_ids = {e.benutzer_id for e in ereignisse if e.benutzer_id}
    namen = {b.id: b.name for b in session.query(Benutzer).filter(Benutzer.id.in_(benutzer_ids or {0}))}
    je_termin: dict[int, list] = {}
    for e in ereignisse:
        je_termin.setdefault(e.termin_id, []).append({
            "name": namen.get(e.benutzer_id, "Team-Kalender" if not e.benutzer_id else "?"),
            "stand": e.stand, "fehler": e.fehler_text or "", "postfach": e.postfach or "",
            "benutzer_id": e.benutzer_id or 0})
    for tid, kopien in je_termin.items():
        staende = [k["stand"] for k in kopien]
        echte = [k for k in kopien if k["stand"] != STAND_LEER]
        if STAND_FEHLER in staende:
            stand = STAND_FEHLER
            fehler = next(k for k in kopien if k["stand"] == STAND_FEHLER)
            text = f"Outlook: Fehler – {fehler['fehler'] or 'Übertragung fehlgeschlagen'}"
        elif STAND_IN_OUTLOOK_GELOESCHT in staende:
            stand = STAND_IN_OUTLOOK_GELOESCHT
            k = next(k for k in kopien if k["stand"] == STAND_IN_OUTLOOK_GELOESCHT)
            text = f"Outlook: in Outlook gelöscht ({k['name']}) – Termin im Tool prüfen"
        elif STAND_AUSSTEHEND in staende:
            stand = STAND_AUSSTEHEND
            text = "Outlook: ausstehend (Übertragung in etwa einer Minute)"
        elif echte:
            stand = STAND_OK
            text = "Outlook: ok" + (f" ({len(echte)} Kopien)" if len(echte) > 1 else "")
        else:
            stand = STAND_LEER
            hinweis = next((k["fehler"] for k in kopien if k["fehler"]), "")
            text = hinweis or "kein Outlook-Eintrag"
        if stand != STAND_LEER:
            leere = [k for k in kopien if k["stand"] == STAND_LEER and k["fehler"]]
            if leere:
                text += " · " + "; ".join(f"{k['name']}: {k['fehler']}" for k in leere)
        ergebnis[tid] = {"stand": stand, "text": text, "kopien": kopien}
    return ergebnis


def status_fuer(session: Session, termin_art: str, termin_id: int) -> dict:
    """Vertrag K/S: {stand, text, kopien[{name, stand, fehler}]} eines Termins."""
    return status_map(session, termin_art, [termin_id]).get(
        int(termin_id), {"stand": STAND_LEER, "text": "kein Outlook-Eintrag", "kopien": []})


def hinweis_person(session: Session, benutzer_id: int) -> str:
    """„HV ohne Postfach“ (oder anderer Grund), wenn die Person keine Outlook-Kopie
    bekommen kann – für Terminlisten vor der Buchung."""
    if not benutzer_id:
        return ""
    _postfach, grund = postfach_fuer(session, session.get(Benutzer, int(benutzer_id)))
    return grund


def postfaecher_ohne_zugriff(session: Session) -> list[dict]:
    """Vertrag G: Personen (und Funktionspostfächer), deren Postfach beim letzten Lauf
    HTTP 403 lieferte – [{benutzer_id, name, postfach, zeit}], nach Name sortiert.
    Quellen: (1) outlook_auftraege mit Status fehler und Text „nicht in der Zugriffsgruppe“
    (dauerhaft, auch nach Neustart; ein späterer erfolgreicher Auftrag desselben Postfachs
    nimmt es aus der Liste), (2) 403 des Rücklesens (im Speicher), (3) die 403-Liste von
    graph_versand (andere Module). Betrachtet werden die letzten sieben Tage."""
    from app import graph_versand
    grenze = datetime.now() - timedelta(days=ZUGRIFF_WIEDERHOLUNG_TAGE)
    erfolge: dict[str, datetime] = {}
    for a in (session.query(OutlookAuftrag)
              .filter(OutlookAuftrag.status == STATUS_ERLEDIGT, OutlookAuftrag.fehler_text == "",
                      OutlookAuftrag.erledigt_am >= grenze)):
        schluessel = (a.postfach or "").strip().lower()
        if schluessel and (schluessel not in erfolge or a.erledigt_am > erfolge[schluessel]):
            erfolge[schluessel] = a.erledigt_am
    eintraege: dict[str, dict] = {}
    for a in (session.query(OutlookAuftrag)
              .filter(OutlookAuftrag.status == STATUS_FEHLER,
                      OutlookAuftrag.fehler_text.like(f"%{ZUGRIFFSGRUPPE_TEXT}%"),
                      OutlookAuftrag.angelegt_am >= grenze)
              .order_by(OutlookAuftrag.id)):
        schluessel = (a.postfach or "").strip().lower()
        zeit = a.erledigt_am or a.angelegt_am
        if not schluessel or (schluessel in erfolge and zeit is not None and erfolge[schluessel] > zeit):
            continue
        alt = eintraege.get(schluessel)
        if alt is None or (zeit is not None and (alt["zeit"] is None or zeit > alt["zeit"])):
            eintraege[schluessel] = {"benutzer_id": a.benutzer_id or None, "zeit": zeit,
                                     "postfach": (a.postfach or "").strip()}
    for schluessel, daten in _OHNE_ZUGRIFF.items():
        alt = eintraege.get(schluessel)
        if alt is None or (daten.get("zeit") and (alt["zeit"] is None or daten["zeit"] > alt["zeit"])):
            eintraege[schluessel] = dict(daten)
    for postfach, zeit in graph_versand.zugriff_verweigert_liste():
        schluessel = (postfach or "").strip().lower()
        if schluessel and schluessel not in eintraege:
            eintraege[schluessel] = {"benutzer_id": None, "zeit": datetime.fromtimestamp(zeit),
                                     "postfach": schluessel}
    if not eintraege:
        return []
    benutzer = {b.id: b for b in session.query(Benutzer)}
    je_postfach: dict[str, Benutzer] = {}
    for b in benutzer.values():
        if (b.email or "").strip():
            je_postfach.setdefault(b.email.strip().lower(), b)
    for p in session.query(AdProfil).filter(AdProfil.kalender_postfach.isnot(None)):
        if (p.kalender_postfach or "").strip() and p.benutzer_id in benutzer:
            je_postfach.setdefault(p.kalender_postfach.strip().lower(), benutzer[p.benutzer_id])
    ergebnis = []
    for schluessel, daten in eintraege.items():
        b = benutzer.get(daten.get("benutzer_id") or 0) or je_postfach.get(schluessel)
        ergebnis.append({"benutzer_id": b.id if b is not None else None,
                         "name": b.name if b is not None else "",
                         "postfach": daten.get("postfach") or schluessel,
                         "zeit": daten.get("zeit")})
    return sorted(ergebnis, key=lambda z: ((z["name"] or "~").lower(), z["postfach"]))


def zusammenfassung(session: Session) -> dict:
    """Kennzahlen für Listen/Betrieb: offene und fehlgeschlagene Aufträge, Termine ohne
    Postfach (HV), Postfächer ohne Zugriff, letzte Läufe."""
    offen = session.query(OutlookAuftrag).filter(OutlookAuftrag.status == STATUS_OFFEN).count()
    grenze = datetime.now() - timedelta(hours=24)
    fehler = (session.query(OutlookAuftrag)
              .filter(OutlookAuftrag.status == STATUS_FEHLER, OutlookAuftrag.angelegt_am >= grenze).count())
    heute = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ohne_postfach = (session.query(OutlookEreignis)
                     .filter(OutlookEreignis.stand == STAND_LEER, OutlookEreignis.beginn >= heute).count())
    in_outlook_geloescht = (session.query(OutlookEreignis)
                            .filter(OutlookEreignis.stand == STAND_IN_OUTLOOK_GELOESCHT,
                                    OutlookEreignis.beginn >= heute).count())
    return {"offen": offen, "fehler_24h": fehler, "ohne_postfach": ohne_postfach,
            "in_outlook_geloescht": in_outlook_geloescht,
            "ohne_zugriff": len(postfaecher_ohne_zugriff(session)),
            "letzter_sync": letzter_lauf(LAUF_SYNC), "letztes_ruecklesen": letzter_lauf(LAUF_RUECKLESEN)}


# --- Migration, Scheduler ----------------------------------------------------------------

def migration_v33_outlook(session: Session) -> list:
    """migrate.py-Hook (idempotent): alte outlook_event_id-Felder als OutlookEreignis
    (Stand ok) spiegeln – VOT: Person = ad_id, Postfach aus „postfach|id“; Projekt:
    Team-/Sammelkalender-Adresse (Kopie benutzer_id 0) –, damit Rücklesen und
    Änderungen den Altbestand kennen. Zweiter Lauf: keine Meldung."""
    meldungen = []
    vorhanden = {(e.termin_art, e.termin_id, (e.postfach or "").lower(), e.event_id)
                 for e in session.query(OutlookEreignis)}
    vorhanden_termine = {(e.termin_art, e.termin_id) for e in session.query(OutlookEreignis)}
    vot_neu = vot_ohne = 0
    for t in (session.query(VotTermin)
              .filter(VotTermin.outlook_event_id.isnot(None), VotTermin.outlook_event_id != "")):
        if (ART_VOT, t.id) in vorhanden_termine:
            continue
        postfach, event_id = _alt_event(session, ART_VOT, t)
        if not postfach or not event_id:
            vot_ohne += 1
            continue
        if (ART_VOT, t.id, postfach.lower(), event_id) in vorhanden:
            continue
        session.add(OutlookEreignis(termin_art=ART_VOT, termin_id=t.id, benutzer_id=t.ad_id or 0,
                                    postfach=postfach, event_id=event_id, stand=STAND_OK,
                                    beginn=t.beginn, ende=t.ende))
        vot_neu += 1
    projekt_neu = projekt_ohne = 0
    for t in session.query(ProjektTermin).filter(ProjektTermin.outlook_event_id != ""):
        if (ART_PROJEKT, t.id) in vorhanden_termine:
            continue
        postfach, event_id = _alt_event(session, ART_PROJEKT, t)
        if not postfach or not event_id:
            projekt_ohne += 1
            continue
        if (ART_PROJEKT, t.id, postfach.lower(), event_id) in vorhanden:
            continue
        session.add(OutlookEreignis(termin_art=ART_PROJEKT, termin_id=t.id, benutzer_id=TEAM_KOPIE_ID,
                                    postfach=postfach, event_id=event_id, stand=STAND_OK,
                                    beginn=t.beginn, ende=t.ende))
        projekt_neu += 1
    session.flush()
    if vot_neu or projekt_neu:
        meldungen.append(f"Outlook (v33): Altbestand gespiegelt – {vot_neu} VOT-Termine, "
                         f"{projekt_neu} Projekt-Termine als outlook_ereignisse (Stand ok)")
    if vot_ohne or projekt_ohne:
        meldungen.append(f"Outlook (v33): {vot_ohne + projekt_ohne} alte Outlook-Einträge ohne "
                         "zuordenbares Postfach (Team ohne Outlook-Adresse) – nicht gespiegelt")
    return meldungen


def scheduler_starten() -> None:
    """Läufe outlook-sync (60 s) und outlook-ruecklesen (300 s) am Scheduler-Rahmen anmelden
    (aktiv nur mit eingerichtetem Graph); Threads startet main.lifespan."""
    from app import scheduler
    scheduler.registrieren(
        LAUF_SYNC, SYNC_INTERVALL_S, sync_lauf,
        beschreibung="Outlook je Mitarbeiter: Warteschlange outlook_auftraege (anlegen/ändern/"
                     "löschen der Termin-Kopien) über Graph abarbeiten",
        start_verzoegerung_s=SYNC_START_VERZOEGERUNG_S, aktiv=graph_aktiv)
    scheduler.registrieren(
        LAUF_RUECKLESEN, RUECKLESEN_INTERVALL_S, ruecklesen_lauf,
        beschreibung="Outlook → Tool: Kalender der Personen mit Terminen (8 Wochen) lesen – "
                     "verschobene/gelöschte Kopien nachziehen, Belegtzeiten-Cache",
        start_verzoegerung_s=RUECKLESEN_START_VERZOEGERUNG_S, aktiv=graph_aktiv)


# --- Jinja-Globals (Terminlisten ohne Router-Änderung) --------------------------------------

def _ids_sammeln(objekte, gesammelt: list) -> None:
    if objekte is None:
        return
    if isinstance(objekte, bool):
        return
    if isinstance(objekte, int):
        gesammelt.append(objekte)
        return
    if isinstance(objekte, dict):
        for schluessel in ("termin", "id"):
            if schluessel in objekte:
                _ids_sammeln(objekte[schluessel], gesammelt)
                return
        return
    if isinstance(objekte, (list, tuple, set)):
        for o in objekte:
            _ids_sammeln(o, gesammelt)
        return
    tid = getattr(objekte, "id", None)
    if isinstance(tid, int):
        gesammelt.append(tid)


def _status_map_global(termin_art: str, objekte) -> dict:
    """Template-Global: Stände mehrerer Termine (IDs, Objekte, Zeilen-Dicts, verschachtelte
    Listen) in EINER kurzen Sitzung – nie eine Ausnahme ins Rendern."""
    ids: list = []
    _ids_sammeln(objekte, ids)
    if not ids:
        return {}
    try:
        from app.db import kurz
        with kurz(schreibend=False) as s:   # v33 (Phase 172): nur lesen - keine Schreibtransaktion
            return status_map(s, termin_art, ids)
    except Exception:   # noqa: BLE001 – Statusanzeige darf keine Seite brechen
        return {}


def _hinweis_global(benutzer_id) -> str:
    try:
        from app.db import kurz
        with kurz(schreibend=False) as s:   # v33 (Phase 172): nur lesen - keine Schreibtransaktion
            return hinweis_person(s, int(benutzer_id or 0))
    except Exception:   # noqa: BLE001
        return ""


def _zusammenfassung_global() -> dict | None:
    try:
        from app.db import kurz
        with kurz(schreibend=False) as s:   # v33 (Phase 172): nur lesen - keine Schreibtransaktion
            return zusammenfassung(s)
    except Exception:   # noqa: BLE001
        return None


try:   # Terminlisten lesen den Stand als Template-Global (Router bleiben unverändert)
    from app.templating import templates as _templates
    _templates.env.globals["outlook_status_map"] = _status_map_global
    _templates.env.globals["outlook_hinweis_person"] = _hinweis_global
    _templates.env.globals["outlook_zusammenfassung"] = _zusammenfassung_global
except Exception:   # noqa: BLE001
    pass
