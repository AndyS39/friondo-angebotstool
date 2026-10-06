# Go-live-Checkliste der Projektierung (PLAN_PROJ_V3 Phase 86): Seite in der
# Parametrierung mit Live-Prüfung je Punkt (grün/rot + Link zur Stelle).
# Die Prüfpunkte der Stücklisten-Seite (V4 Phase 93: ≥ 90 % zugeordnet,
# Collin-Testdatei bestätigt) sind hierher umgezogen.

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app import projektierung as kern

EINSTELLUNGEN = "/parametrierung/projektierung-einstellungen"
PORTAL_URLS = [("url_bza_portal", "BzA-Portal"),
               ("url_kfw_zuschussportal", "KfW-Zuschussportal"),
               ("url_spotmyenergy", "SpotmyEnergy"),
               ("url_heizreport", "Heizreport"),
               ("url_gc_online", "GC Online Plus")]


@dataclass
class Pruefpunkt:
    titel: str
    ok: bool
    detail: str
    link: str
    haekchen: str = ""        # Parametername, wenn der Punkt ein Admin-Häkchen ist


def _benutzer_mit_rolle(session: Session, rolle: str) -> list:
    from app.models import Benutzer
    return [b for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
            if b.hat_rolle(rolle)]


def pruefen(session: Session) -> list[Pruefpunkt]:
    from app import stuecklisten
    from app.models import (Bestandsimport, ProjektTermin, Subunternehmer, Team,
                            TeamMitglied)
    from app import projektierung_logik
    punkte: list[Pruefpunkt] = []
    # 1 Absender-Postfach + Testmail
    absender = kern.parameter_holen(session, "absender_postfach", "").strip()
    testmail = kern.parameter_holen(session, "golive_testmail", "")
    punkte.append(Pruefpunkt(
        "Absender-Postfach hinterlegt und Testmail erfolgreich",
        bool(absender and testmail),
        (f"{absender or 'kein Postfach hinterlegt'} · "
         + (f"Testmail {testmail}" if testmail else "Testmail noch nicht erfolgreich")),
        EINSTELLUNGEN))
    # 2 Kalender-Modus + Test-Termin in Outlook
    modus = kern.parameter_holen(session, "outlook_kalender_modus", "").strip()
    mit_outlook = (session.query(ProjektTermin)
                   .filter(ProjektTermin.outlook_event_id != "").count())
    punkte.append(Pruefpunkt(
        "Kalender-Modus gewählt und Test-Termin in Outlook angelegt",
        bool(modus and mit_outlook),
        f"Modus: {modus or 'nicht gewählt'} · {mit_outlook} Termine in Outlook",
        EINSTELLUNGEN))
    # 3 Benutzer je Rolle
    projektierer = _benutzer_mit_rolle(session, "projektierung")
    monteure = _benutzer_mit_rolle(session, "montage")
    punkte.append(Pruefpunkt(
        "Mindestens ein Benutzer je Rolle Projektierung / Montage",
        bool(projektierer and monteure),
        f"Projektierung: {len(projektierer)} · Montage: {len(monteure)}",
        "/benutzer"))
    # 4 Teams mit Mitgliedern
    teams = session.query(Team).filter(Team.aktiv.is_(True), Team.typ == "montage").all()
    mit_mitgliedern = {m.team_id for m in session.query(TeamMitglied)}
    besetzt = [t for t in teams if t.id in mit_mitgliedern]
    punkte.append(Pruefpunkt(
        "Montageteams mit Mitgliedern", bool(besetzt),
        f"{len(besetzt)} von {len(teams)} Montageteams besetzt", "/parametrierung/teams"))
    # 5 Standard-Sub je Typ (Parametrierung → Subunternehmer, Spalte „Standard“;
    #   muss aktiv sein und eine E-Mail haben)
    from app import sub_mail
    typen = projektierung_logik.sub_typen(session)
    fehlend = []
    for typ in typen:
        sub = session.get(Subunternehmer, sub_mail.standard_sub_id(session, typ) or 0)
        if sub is None or not sub.aktiv or not (sub.email or "").strip():
            fehlend.append(typ)
    punkte.append(Pruefpunkt(
        "Standard-Subunternehmer (aktiv, mit E-Mail) je Sub-Typ", not fehlend,
        "alle Typen belegt" if not fehlend else "fehlt: " + ", ".join(fehlend),
        "/parametrierung/subunternehmer"))
    # 6 Portal-URLs
    ohne = [name for key, name in PORTAL_URLS
            if not kern.parameter_holen(session, key, "").strip()]
    punkte.append(Pruefpunkt(
        "Portal-URLs gepflegt", not ohne,
        "alle gepflegt" if not ohne else "fehlt: " + ", ".join(ohne), EINSTELLUNGEN))
    # 7 Collin-Kundennummer
    kundennummer = kern.parameter_holen(session, "collin_kundennummer", "").strip()
    punkte.append(Pruefpunkt("Collin-Kundennummer", bool(kundennummer),
                             kundennummer or "fehlt", EINSTELLUNGEN))
    # 8 Stücklisten (≥ 90 % zugeordnet, keine BEISPIEL-Nummern)
    zugeordnet, gesamt = stuecklisten.fortschritt(session)
    quote = zugeordnet / gesamt if gesamt else 0.0
    logik = projektierung_logik.hole_logik(session)
    beispiele = sum(1 for zeilen in logik.stuecklisten.values() for z in zeilen
                    if "BEISPIEL" in str(getattr(z, "lieferant_artnr", "")).upper())
    punkte.append(Pruefpunkt(
        "Stücklisten ≥ 90 % zugeordnet, ohne Beispielnummern",
        quote >= stuecklisten.GO_LIVE_QUOTE and not beispiele,
        f"{zugeordnet} von {gesamt} Positionen ({quote * 100:.0f} %) · "
        f"{beispiele} BEISPIEL-Artikelnummern", "/parametrierung/stuecklisten"))
    # 9 Collin-Testdatei (Häkchen, früher auf der Stücklisten-Seite)
    testdatei = kern.parameter_holen(session, "ugl_testdatei_bestaetigt", "")
    punkte.append(Pruefpunkt(
        "UGL-Testdatei von Collin bestätigt", bool(testdatei),
        testdatei or "offen – docs/ugl-beispiel.ugl an Collin senden",
        "/parametrierung/golive", haekchen="ugl_testdatei_bestaetigt"))
    # 10 Formulare abgenommen (Häkchen)
    formulare = kern.parameter_holen(session, "golive_formulare_abgenommen", "")
    punkte.append(Pruefpunkt(
        "Montage-Formulare abgenommen (Blatt „Formulare“)", bool(formulare),
        formulare or "offen – mit einem Monteur durchgehen",
        "/parametrierung/projektierung-logik", haekchen="golive_formulare_abgenommen"))
    # 11 Bestandsimport
    importe = (session.query(Bestandsimport)
               .filter(Bestandsimport.rueckgaengig_am.is_(None),
                       Bestandsimport.angelegt + Bestandsimport.aktualisiert > 0).count())
    punkte.append(Pruefpunkt("Bestandsimport durchgeführt", bool(importe),
                             f"{importe} Import(e) aktiv",
                             "/parametrierung/bestandsimport"))
    return punkte


def haekchen_setzen(session: Session, name: str, an: bool, benutzer) -> None:
    kern.parameter_setzen(session, name,
                          f"{datetime.now():%d.%m.%Y} · {benutzer.name}" if an else "")


def testmail_senden(session: Session, benutzer) -> tuple[bool, str]:
    """Testmail über das Projektierungs-Absenderpostfach an den Admin selbst."""
    from app import benachrichtigungen, graph_versand
    ziel = (getattr(benutzer, "email", "") or "").strip()
    if not ziel:
        return False, "Ihr Benutzer hat keine E-Mail-Adresse (Benutzerverwaltung)."
    absender = benachrichtigungen._absender(session)
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Absender ist gelesen;
    # msal kann das Token über das Netz erneuern)
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    # bewusst OHNE Fallback auf angebot@ – geprüft wird das Absender-Postfach
    ok, fehler = graph_versand.text_mail_senden(
        ziel, "Testmail Projektierung – Go-live-Checkliste",
        "Diese Testmail wurde aus der Go-live-Checkliste der Projektierung "
        f"über {absender} gesendet. Wenn sie ankommt, ist das Absender-Postfach "
        "eingerichtet.", absender)
    if not ok:
        return False, f"Testmail über {absender} fehlgeschlagen: {fehler}"
    if ok:
        kern.parameter_setzen(session, "golive_testmail",
                              f"{datetime.now():%d.%m.%Y %H:%M} an {ziel}")
        return True, f"Testmail an {ziel} versendet."
