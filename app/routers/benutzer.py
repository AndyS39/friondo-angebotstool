# Benutzerverwaltung (Phase 13; seit Phase 18 nur Rolle Admin): Name, Rolle,
# PIN, E-Mail (v5, Pflicht für Außendienst – CC in der Angebots-Mail).
# Löschen (v5) nur ohne zugeordnete Vorgänge, sonst deaktivieren.
# v27 (PLAN_V17 Phase 130): PIN-Regeln (auth.pin_regel_pruefen) statt „mind. 4
# Ziffern“, beide Hash-Spalten über auth.pin_setzen, Pflicht-PIN-Wechsel beim
# Anlegen/Reset, „Sperre aufheben“ und „Alle Sitzungen beenden“ je Benutzer,
# Filter Rolle/aktiv und Spalte „Letzter Login“, Einstellungen-Block (Sitzung,
# PIN-Regeln), CSV-Import mit Vorschau und einmaliger Start-PIN-Liste
# (app/benutzer_import.py), Login-Protokoll (/benutzer/login-protokoll).

import re
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app import auth
from app.db import get_session
from app.models import (Benutzer, Erfassung, Lead, MondayPerson, MondayQuelle,
                        einstellung_holen, einstellung_setzen)
from app.templating import render
from app import anfrage   # v27: Formular/JSON in def-Routen

router = APIRouter(prefix="/benutzer")

ROLLEN = ["admin", "innendienst", "aussendienst", "projektierung", "montage",
          "leadmanagement"]
# v11 (Phase 70): Zusatzrollen als Häkchen – die Hauptrolle steuert weiterhin
# die Grundsicht, Zusatzrollen schalten Projektierung/Montage frei
ZUSATZROLLEN = ["projektierung", "montage", "leadmanagement"]
# 27.09.2026: sprechende Namen fuer die neue Benutzer-Seite
ROLLEN_NAMEN = {"admin": "Admin", "innendienst": "Innendienst",
                "aussendienst": "Außendienst",
                "projektierung": "Projektierung", "montage": "Montage",
                "leadmanagement": "Lead-Management"}
_EMAIL_MUSTER = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# v27 (Phase 130): Einstellungen des Blocks „Sitzung & PIN-Regeln“ (Tabelle
# einstellungen; auth liest sie über einstellung_holen) – Name → (Standard,
# Minimum, Maximum) für die Zahlenfelder
EINSTELLUNGEN_ZAHLEN = {
    "sitzung_stunden_buero": (auth.SITZUNG_STUNDEN_BUERO, 1, 168),
    "sitzung_tage_mobil": (auth.SITZUNG_TAGE_MOBIL, 1, 365),
    "pin_mindestlaenge": (auth.PIN_MINDESTLAENGE_NEU, 4, 12),
}
EINSTELLUNGEN_NAMEN = {
    "sitzung_stunden_buero": "Sitzungsdauer Büro (Stunden)",
    "sitzung_tage_mobil": "Sitzungsdauer Außendienst/Montage (Tage)",
    "pin_mindestlaenge": "Mindestlänge neuer PINs",
    "pin_sperrliste": "PIN-Sperrliste",
}
SPERRLISTE_MAX_ZEICHEN = 300   # Spalte einstellungen.wert ist String(300)
# Login-Protokoll: Gründe aus auth.login_pruefen → Anzeigetext
GRUND_TEXTE = {"ok": "OK", "pin_falsch": "PIN falsch", "gesperrt": "gesperrt",
               "ip_limit": "IP-Grenze erreicht", "inaktiv": "Benutzer inaktiv",
               "unbekannt": "Benutzer unbekannt"}
LOGIN_PROTOKOLL_MAX = 500


def verknuepfungen(session: Session, benutzer_id: int) -> dict[str, int]:
    """Was hängt an diesem Benutzer? Leer = löschbar."""
    zaehler = {
        "Erfassungen": session.query(Erfassung)
        .filter(Erfassung.benutzer_id == benutzer_id).count(),
        "Leads": session.query(Lead).filter(Lead.benutzer_id == benutzer_id).count(),
        "monday-Zuordnungen": session.query(MondayPerson)
        .filter(MondayPerson.benutzer_id == benutzer_id).count()
        + session.query(MondayQuelle)
        .filter(MondayQuelle.fester_benutzer_id == benutzer_id).count(),
    }
    return {k: v for k, v in zaehler.items() if v}


def _email_pruefen(rolle: str, email: str) -> str | None:
    if email and not _EMAIL_MUSTER.match(email):
        return "E-Mail-Adresse ist ungültig"
    if rolle == "aussendienst" and not email:
        return "Für Außendienst-Benutzer ist eine E-Mail-Adresse Pflicht (CC im Versand)"
    return None


def _meldung(ziel: str, text: str) -> RedirectResponse:
    return RedirectResponse(f"{ziel}?meldung={quote_plus(text)}", status_code=303)


def einstellungen_lesen(session: Session) -> dict:
    """v27: Werte des Blocks „Sitzung & PIN-Regeln“ (Standard aus auth)."""
    werte = {name: einstellung_holen(session, name, str(standard))
             for name, (standard, _, _) in EINSTELLUNGEN_ZAHLEN.items()}
    werte["pin_sperrliste"] = einstellung_holen(session, "pin_sperrliste",
                                                auth.PIN_SPERRLISTE_STANDARD)
    return werte


@router.get("")
def liste(request: Request, session: Session = Depends(get_session)):
    from app.models import Team, TeamMitglied
    # v27 (Phase 130): Filter Rolle (Hauptrolle) und aktiv/inaktiv
    rolle_filter = request.query_params.get("rolle") or ""
    aktiv_filter = request.query_params.get("aktiv") or ""
    abfrage = session.query(Benutzer)
    if rolle_filter in ROLLEN:
        abfrage = abfrage.filter(Benutzer.rolle == rolle_filter)
    else:
        rolle_filter = ""
    if aktiv_filter == "1":
        abfrage = abfrage.filter(Benutzer.aktiv.is_(True))
    elif aktiv_filter == "0":
        abfrage = abfrage.filter(Benutzer.aktiv.is_(False))
    else:
        aktiv_filter = ""
    benutzer = abfrage.order_by(Benutzer.name).all()
    loeschbar = {b.id: not verknuepfungen(session, b.id) for b in benutzer}
    teams = (session.query(Team).filter(Team.aktiv.is_(True))
             .order_by(Team.typ, Team.name).all())
    team_je_benutzer: dict[int, set[int]] = {}
    for m in session.query(TeamMitglied):
        team_je_benutzer.setdefault(m.benutzer_id, set()).add(m.team_id)
    return render(request, "benutzer/liste.html", aktiv="/benutzer",
                  benutzer=benutzer, rollen=ROLLEN, loeschbar=loeschbar,
                  zusatzrollen=ZUSATZROLLEN, teams=teams,
                  rollen_namen=ROLLEN_NAMEN,
                  team_je_benutzer=team_je_benutzer,
                  rolle_filter=rolle_filter, aktiv_filter=aktiv_filter,
                  jetzt=datetime.now(), einstellungen=einstellungen_lesen(session),
                  pin_mindestlaenge=auth.pin_mindestlaenge(session),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/neu")
def anlegen(request: Request, session: Session = Depends(get_session)):
    form = anfrage.formular(request)
    name = (form.get("name") or "").strip()
    rolle = form.get("rolle") if form.get("rolle") in ROLLEN else "aussendienst"
    pin = (form.get("pin") or "").strip()
    email = (form.get("email") or "").strip().lower()
    if not name:
        return _meldung("/benutzer", "Name erforderlich")
    # v27 (Phase 130): PIN-Regeln (Mindestlänge, Sperrliste, Muster) statt „mind. 4 Ziffern“
    pin_fehler = auth.pin_regel_pruefen(pin, session)
    if pin_fehler:
        return _meldung("/benutzer", "PIN: " + pin_fehler)
    if session.query(Benutzer).filter(Benutzer.name == name).first():
        return _meldung("/benutzer", "Name bereits vergeben")
    fehler = _email_pruefen(rolle, email)
    if fehler:
        return _meldung("/benutzer", fehler)
    # Häkchen „PIN-Wechsel beim nächsten Login verlangen“ (beim Anlegen vorbelegt an)
    neuer = Benutzer(name=name, rolle=rolle, email=email,
                     pin_wechsel_noetig=form.get("pin_wechsel") == "on")
    auth.pin_setzen(neuer, pin)          # schreibt pin_hash_v2 UND pin_hash
    session.add(neuer)
    session.flush()
    # 27.09.2026: Montage-Benutzer direkt beim Anlegen einem Team zuordnen
    from app.models import Team, TeamMitglied
    gueltig = {t.id for t in session.query(Team)}
    for team_id in {int(t) for t in form.getlist("team_ids")
                    if str(t).isdigit()} & gueltig:
        session.add(TeamMitglied(team_id=team_id, benutzer_id=neuer.id,
                                 erstellt_von=request.state.benutzer.id))
    session.commit()
    return RedirectResponse("/benutzer?meldung=Benutzer+angelegt", status_code=303)


@router.post("/{benutzer_id}/aendern")
def aendern(request: Request, benutzer_id: int,
                  session: Session = Depends(get_session)):
    form = anfrage.formular(request)
    benutzer = session.get(Benutzer, benutzer_id)
    if benutzer is None:
        return RedirectResponse("/benutzer", status_code=303)
    neuer_name = (form.get("name") or "").strip()
    if neuer_name and neuer_name != benutzer.name:
        if session.query(Benutzer).filter(Benutzer.name == neuer_name,
                                          Benutzer.id != benutzer.id).first():
            return RedirectResponse("/benutzer?meldung=Name+bereits+vergeben", status_code=303)
        benutzer.name = neuer_name
    rolle = form.get("rolle") if form.get("rolle") in ROLLEN else benutzer.rolle
    email = (form.get("email") or "").strip().lower()
    fehler = _email_pruefen(rolle, email)
    if fehler:
        return _meldung("/benutzer", fehler)
    benutzer.rolle = rolle
    benutzer.email = email
    # v11 (Phase 69): E-Mail-Benachrichtigung aus Glocken-Ereignissen
    if form.get("benachrichtigung_mail") in ("aus", "sofort", "digest"):
        benutzer.benachrichtigung_mail = form.get("benachrichtigung_mail")
    # v11 (Phase 70): Mehrfachrollen (Häkchen), Kalkulation, Telefon, Teams
    zusatz = [r for r in ZUSATZROLLEN if form.get(f"zusatz_{r}") == "on"]
    benutzer.rollen = ",".join([rolle] + [r for r in zusatz if r != rolle])
    benutzer.kalkulation_sichtbar = form.get("kalkulation_sichtbar") == "on"
    benutzer.telefon = (form.get("telefon") or "").strip()
    # v12 (Phase 73): Leadmanager-Einstellungen (Round-Robin-Zuweisung)
    benutzer.lm_aktiv = form.get("lm_aktiv") == "on"
    benutzer.lm_arbeitszeit = (form.get("lm_arbeitszeit") or "").strip() or None
    from app.models import Team, TeamMitglied
    # 27.09.2026: Teams nur aendern, wenn das Formular sie mitschickt
    # (teams_dabei) - sonst wuerde ein Formular ohne Team-Block alle
    # Zuordnungen loeschen
    if form.get("teams_dabei") == "1":
        gewaehlt = {int(t) for t in form.getlist("team_ids") if str(t).isdigit()}
        gueltig = {t.id for t in session.query(Team)}
        gewaehlt &= gueltig
        for m in (session.query(TeamMitglied)
                  .filter(TeamMitglied.benutzer_id == benutzer.id)):
            if m.team_id in gewaehlt:
                gewaehlt.discard(m.team_id)
            else:
                session.delete(m)
        for team_id in gewaehlt:
            session.add(TeamMitglied(team_id=team_id, benutzer_id=benutzer.id,
                                     erstellt_von=request.state.benutzer.id))
    pin = (form.get("pin") or "").strip()
    if pin:
        # v27 (Phase 130): Admin-Reset – PIN-Regeln, beide Hash-Spalten,
        # Pflichtwechsel laut Häkchen (vorbelegt an); hebt eine Sperre mit auf
        pin_fehler = auth.pin_regel_pruefen(pin, session)
        if pin_fehler:
            return _meldung("/benutzer", "PIN: " + pin_fehler)
        auth.pin_setzen(benutzer, pin)
        benutzer.pin_wechsel_noetig = form.get("pin_wechsel") == "on"
    benutzer.aktiv = form.get("aktiv") == "on"
    session.commit()
    return RedirectResponse("/benutzer?meldung=Gespeichert", status_code=303)


@router.post("/{benutzer_id}/loeschen")
def loeschen(request: Request, benutzer_id: int,
                   session: Session = Depends(get_session)):
    """Löschen nur ohne Vorgänge; sonst wird deaktiviert (Historie bleibt)."""
    benutzer = session.get(Benutzer, benutzer_id)
    if benutzer is None:
        return RedirectResponse("/benutzer", status_code=303)
    if benutzer.id == request.state.benutzer.id:
        return RedirectResponse("/benutzer?meldung=" + quote_plus(
            "Der eigene Benutzer kann nicht gelöscht werden."), status_code=303)
    haengt = verknuepfungen(session, benutzer.id)
    if haengt:
        benutzer.aktiv = False
        session.commit()
        details = ", ".join(f"{n} {k}" for k, n in haengt.items())
        return RedirectResponse("/benutzer?meldung=" + quote_plus(
            f"{benutzer.name} wurde deaktiviert statt gelöscht – zugeordnet: {details}. "
            "Der Benutzer erscheint in keiner Auswahlliste mehr, die Historie bleibt lesbar."),
            status_code=303)
    name = benutzer.name
    # v27 (Phase 130): SQLite vergibt die ID eines gelöschten Benutzers neu –
    # Protokollzeilen bleiben (Name steht drin), verlieren aber die ID, damit
    # sie später keinem neuen Benutzer zugerechnet werden (Filter, Sperrfenster)
    from app.models import LoginProtokoll
    (session.query(LoginProtokoll).filter(LoginProtokoll.benutzer_id == benutzer.id)
     .update({"benutzer_id": None}, synchronize_session=False))
    session.delete(benutzer)
    session.commit()
    return RedirectResponse("/benutzer?meldung=" + quote_plus(f"{name} gelöscht"),
                            status_code=303)


# --- v27 (Phase 130): Sperre aufheben, Sitzungen beenden, Einstellungen ------------------

@router.post("/{benutzer_id}/sperre-aufheben")
def sperre_aufheben(request: Request, benutzer_id: int,
                    session: Session = Depends(get_session)):
    """Fehlversuchssperre vorzeitig aufheben (Benutzerliste und Login-Protokoll)."""
    form = anfrage.formular(request)
    ziel = "/benutzer/login-protokoll" if form.get("zurueck") == "protokoll" else "/benutzer"
    benutzer = session.get(Benutzer, benutzer_id)
    if benutzer is None:
        return RedirectResponse(ziel, status_code=303)
    auth.sperre_aufheben(benutzer)
    session.commit()
    return _meldung(ziel, f"Sperre für {benutzer.name} aufgehoben – Anmeldung wieder möglich.")


@router.post("/{benutzer_id}/anmelden-als")
def anmelden_als(request: Request, benutzer_id: int,
                 session: Session = Depends(get_session)):
    """v27-Nachtrag (Antwort Andreas 07.10.2026: „Admin soll immer Zugang zu allen
    Accounts haben“): der Admin meldet sich ohne PIN als beliebiger aktiver Benutzer
    an (Sicht des Benutzers, Hilfe am Telefon). Dauer 2 h [ANNAHME]; der Vorgang
    steht im Login-Protokoll (Grund admin_zugang:<Admin>). Zurück zum eigenen Konto
    über Abmelden + Anmelden."""
    from app.routers.anmeldung import startseite
    admin = request.state.benutzer
    benutzer = session.get(Benutzer, benutzer_id)
    if benutzer is None or not benutzer.aktiv:
        return _meldung("/benutzer", "Benutzer nicht gefunden oder inaktiv.")
    if benutzer.pin_wechsel_noetig:
        return _meldung("/benutzer", f"{benutzer.name}: Pflicht-PIN-Wechsel offen – der Benutzer "
                        "meldet sich zuerst selbst mit der Start-PIN an.")
    auth._protokollieren(session, benutzer, auth.client_ip(request), True,
                         f"admin_zugang:{admin.name}"[:100])
    session.commit()
    antwort = RedirectResponse(startseite(session, benutzer), status_code=303)
    auth.cookie_setzen(antwort, benutzer, 2 * 3600)
    return antwort


@router.post("/{benutzer_id}/sitzungen-beenden")
def sitzungen_beenden(request: Request, benutzer_id: int,
                      session: Session = Depends(get_session)):
    """Sitzungszähler erhöhen: alle bestehenden Cookies des Benutzers werden
    ungültig (Abmelden überall). Beim eigenen Benutzer bleibt dieses Gerät
    über ein frisches Cookie angemeldet [ANNAHME]."""
    benutzer = session.get(Benutzer, benutzer_id)
    if benutzer is None:
        return RedirectResponse("/benutzer", status_code=303)
    auth.alle_sitzungen_beenden(benutzer)
    session.commit()
    eigener = benutzer.id == request.state.benutzer.id
    antwort = _meldung("/benutzer", f"Alle Sitzungen von {benutzer.name} beendet"
                       + (" – dieses Gerät bleibt angemeldet." if eigener
                          else " – der Benutzer muss sich überall neu anmelden."))
    if eigener:
        auth.cookie_setzen(antwort, benutzer, auth.sitzungsdauer_s(session, benutzer, False))
    return antwort


def _sperrliste_normieren(text: str) -> str:
    """Komma/Semikolon/Leerzeichen/Zeilen → eindeutige Ziffernfolgen, kommagetrennt."""
    gesehen: list[str] = []
    for teil in re.split(r"[,;\s]+", text or ""):
        teil = teil.strip()
        if teil and teil.isdigit() and teil not in gesehen:
            gesehen.append(teil)
    return ",".join(gesehen)


@router.post("/einstellungen")
def einstellungen_speichern(request: Request, session: Session = Depends(get_session)):
    """Block „Sitzung & PIN-Regeln“: Zahlen plausibel (≥ 1, Mindestlänge 4–12),
    Sperrliste als kommagetrennte Ziffernfolgen (leer = Standardliste)."""
    form = anfrage.formular(request)
    fehler = []
    werte: dict[str, str] = {}
    for name, (standard, minimum, maximum) in EINSTELLUNGEN_ZAHLEN.items():
        roh = (form.get(name) or "").strip()
        try:
            zahl = int(roh)
        except ValueError:
            fehler.append(f"{EINSTELLUNGEN_NAMEN[name]}: bitte eine ganze Zahl eingeben")
            continue
        if not minimum <= zahl <= maximum:
            fehler.append(f"{EINSTELLUNGEN_NAMEN[name]}: erlaubt sind {minimum} bis {maximum}")
            continue
        werte[name] = str(zahl)
    sperrliste = _sperrliste_normieren(form.get("pin_sperrliste") or "")
    if len(sperrliste) > SPERRLISTE_MAX_ZEICHEN:
        fehler.append(f"PIN-Sperrliste: höchstens {SPERRLISTE_MAX_ZEICHEN} Zeichen")
    else:
        werte["pin_sperrliste"] = sperrliste
    if fehler:
        return _meldung("/benutzer", "Einstellungen nicht gespeichert – " + "; ".join(fehler))
    for name, wert in werte.items():
        einstellung_setzen(session, name, wert)
    session.commit()
    return RedirectResponse("/benutzer?meldung=" + quote_plus("Einstellungen gespeichert")
                            + "#einstellungen", status_code=303)


# --- v27 (Phase 130): CSV-Import mit Vorschau und Start-PIN-Liste ----------------------------

def _import_seite(request: Request, schritt: str, **kontext):
    from app import benutzer_import
    return render(request, "benutzer/import.html", aktiv="/benutzer", schritt=schritt,
                  spalten=benutzer_import.SPALTEN, beispiel=benutzer_import.BEISPIEL_CSV,
                  rollen_namen=ROLLEN_NAMEN, **kontext)


@router.get("/import")
def import_formular(request: Request, session: Session = Depends(get_session)):
    from app import benutzer_import
    return _import_seite(request, "formular", fehler="",
                         kanaele=benutzer_import.kanal_werte_import(session))


@router.get("/import/vorlage.csv")
def import_vorlage():
    """Beispiel-CSV zum Herunterladen (UTF-8 mit BOM – Excel öffnet sie korrekt)."""
    from app import benutzer_import
    return Response(benutzer_import.BEISPIEL_CSV.encode("utf-8-sig"),
                    media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             'attachment; filename="benutzer-import-vorlage.csv"'})


@router.post("/import")
def import_verarbeiten(request: Request, session: Session = Depends(get_session)):
    """aktion=vorschau: Datei (oder csv_text) lesen und prüfen, Tabelle zeigen;
    aktion=ausfuehren: erneut prüfen (die Datenbank kann sich geändert haben)
    und nur ohne Fehler anlegen – Ergebnis ist die einmalige Start-PIN-Liste."""
    from app import benutzer_import
    form = anfrage.formular(request)
    aktion = (form.get("aktion") or "vorschau").strip()
    datei = form.get("datei")
    if datei is not None and getattr(datei, "filename", ""):
        text = benutzer_import.text_dekodieren(datei.file.read())
    else:
        text = form.get("csv_text") or ""
    if not text.strip():
        return _import_seite(request, "formular", kanaele=benutzer_import.kanal_werte_import(session),
                             fehler="Bitte eine CSV-Datei auswählen.")
    zeilen, fehler_datei = benutzer_import.csv_lesen(text)
    if not fehler_datei:
        zeilen = benutzer_import.pruefen(session, zeilen)
    fehler_anzahl = len(fehler_datei) + sum(1 for z in zeilen if z.fehler)
    hinweis = ""
    if aktion == "ausfuehren":
        if fehler_anzahl == 0 and zeilen:
            ergebnis = benutzer_import.anlegen(session, zeilen, request.state.benutzer.id)
            session.commit()
            return _import_seite(request, "ergebnis", ergebnis=ergebnis)
        hinweis = ("Der Import wurde nicht ausgeführt – die Prüfung meldet inzwischen "
                   "Fehler (z. B. wurde ein Name zwischenzeitlich angelegt).")
    return _import_seite(request, "vorschau", zeilen=zeilen, fehler_datei=fehler_datei,
                         fehler_anzahl=fehler_anzahl, csv_text=text, hinweis=hinweis)


# --- v27 (Phase 130): Login-Protokoll -------------------------------------------------------

@router.get("/login-protokoll")
def login_protokoll(request: Request, session: Session = Depends(get_session)):
    """Letzte 500 Anmeldeversuche, Filter Benutzer / nur Fehler, Zähler 24 h,
    aktuell gesperrte Benutzer mit „Sperre aufheben“."""
    from app.models import LoginProtokoll
    jetzt = datetime.now()
    roh_id = request.query_params.get("benutzer_id") or ""
    benutzer_id = int(roh_id) if roh_id.isdigit() else None
    nur_fehler = request.query_params.get("nur_fehler") == "1"
    abfrage = session.query(LoginProtokoll)
    if benutzer_id:
        abfrage = abfrage.filter(LoginProtokoll.benutzer_id == benutzer_id)
    if nur_fehler:
        abfrage = abfrage.filter(LoginProtokoll.erfolg.is_(False))
    eintraege = (abfrage.order_by(LoginProtokoll.zeit.desc(), LoginProtokoll.id.desc())
                 .limit(LOGIN_PROTOKOLL_MAX).all())
    seit = jetzt - timedelta(hours=24)
    versuche_24h = (session.query(LoginProtokoll)
                    .filter(LoginProtokoll.zeit >= seit).count())
    fehlversuche_24h = (session.query(LoginProtokoll)
                        .filter(LoginProtokoll.zeit >= seit,
                                LoginProtokoll.erfolg.is_(False)).count())
    gesperrte = (session.query(Benutzer).filter(Benutzer.gesperrt_bis.isnot(None),
                                                Benutzer.gesperrt_bis > jetzt)
                 .order_by(Benutzer.name).all())
    alle_benutzer = session.query(Benutzer).order_by(Benutzer.name).all()
    return render(request, "benutzer/login_protokoll.html", aktiv="/benutzer",
                  eintraege=eintraege, versuche_24h=versuche_24h,
                  fehlversuche_24h=fehlversuche_24h, gesperrte=gesperrte,
                  alle_benutzer=alle_benutzer, benutzer_id=benutzer_id,
                  nur_fehler=nur_fehler, grund_texte=GRUND_TEXTE,
                  maximum=LOGIN_PROTOKOLL_MAX, sperre_minuten=auth.SPERRE_MINUTEN,
                  max_fehlversuche=auth.MAX_FEHLVERSUCHE,
                  meldung=request.query_params.get("meldung", ""))


# --- v12 (Phase 77): AD-Profil für den Terminassistenten ---------------------------

@router.get("/{benutzer_id}/ad-profil")
def ad_profil_seite(request: Request, benutzer_id: int,
                          session: Session = Depends(get_session)):
    import json as json_modul

    from app.models import AdProfil
    person = session.get(Benutzer, benutzer_id)
    if person is None:
        return RedirectResponse("/benutzer", status_code=303)
    profil = (session.query(AdProfil)
              .filter(AdProfil.benutzer_id == benutzer_id).first())
    try:
        zeiten = json_modul.loads(profil.arbeitszeiten) if profil else {}
    except ValueError:
        zeiten = {}
    try:
        gebiet = json_modul.loads(profil.gebiet_plz_praefixe) if profil else []
    except ValueError:
        gebiet = []
    # v23 (Phase 108, F3/F4/A-1): Produktkompetenz, Handelsvertreter-Kennzeichen,
    # Kanal-Regel, Buchungslink, Startwerte aus den Parametern
    from app import lead_termin, lead_v2
    from app import leadmanagement as kern
    from app.models import INTERESSEN
    return render(request, "benutzer/ad_profil.html", aktiv="/benutzer",
                  person=person, profil=profil, zeiten=zeiten,
                  gebiet=", ".join(str(p) for p in gebiet),
                  wochentage=[("mo", "Montag"), ("di", "Dienstag"),
                              ("mi", "Mittwoch"), ("do", "Donnerstag"),
                              ("fr", "Freitag"), ("sa", "Samstag")],
                  sparten=INTERESSEN,
                  kompetenz=lead_v2.kompetenz_sparten(profil) if profil else [],
                  startwerte=lead_v2.kompetenz_startwerte(person.name),
                  puffer_param=lead_termin._int(kern.parameter_holen(session, "puffer_min", "30"), 30),
                  max_start=lead_termin._int(kern.parameter_holen(session, "max_termine_tag_start", "3"), 3),
                  kanaele=[k for k in kern.kanal_werte(session) if k.lower() != "standard"],
                  kanal_zustaendig=lead_termin.kanal_regel_fuer_ad(session, person.id),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/{benutzer_id}/ad-profil")
def ad_profil_speichern(request: Request, benutzer_id: int,
                              session: Session = Depends(get_session)):
    import json as json_modul

    from app.models import AdProfil
    person = session.get(Benutzer, benutzer_id)
    if person is None:
        return RedirectResponse("/benutzer", status_code=303)
    form = anfrage.formular(request)
    profil = (session.query(AdProfil)
              .filter(AdProfil.benutzer_id == benutzer_id).first())
    if profil is None:
        profil = AdProfil(benutzer_id=benutzer_id,
                          erstellt_von=request.state.benutzer.id)
        session.add(profil)
    zeiten = {}
    for tag in ("mo", "di", "mi", "do", "fr", "sa"):
        von = (form.get(f"{tag}_von") or "").strip()
        bis = (form.get(f"{tag}_bis") or "").strip()
        if von and bis:
            zeiten[tag] = [von, bis]
    profil.arbeitszeiten = json_modul.dumps(zeiten)
    neue_adresse = (form.get("start_adresse") or "").strip()[:300]
    if neue_adresse != profil.start_adresse:
        profil.start_adresse = neue_adresse
        profil.start_lat = None   # Geokodierung läuft neu (Hintergrund/sofort)
        profil.start_lon = None
    def _zahl(name, standard):
        try:
            return max(1, int(form.get(name) or standard))
        except ValueError:
            return standard
    # v23 (Phase 108, F4/A-13): Startwerte aus den Parametern puffer_min (30)
    # und max_termine_tag_start (3)
    from app import lead_termin, leadmanagement as kern
    from app.models import INTERESSE_CODES
    puffer_start = lead_termin._int(kern.parameter_holen(session, "puffer_min", "30"), 30)
    max_start = lead_termin._int(kern.parameter_holen(session, "max_termine_tag_start", "3"), 3)
    profil.termin_dauer_min = _zahl("termin_dauer_min", 90)
    profil.puffer_min = _zahl("puffer_min", puffer_start)
    profil.max_termine_tag = _zahl("max_termine_tag", max_start)
    profil.gebiet_plz_praefixe = json_modul.dumps(
        [p.strip() for p in (form.get("gebiet") or "").split(",") if p.strip()])
    profil.kalender_postfach = (form.get("kalender_postfach") or "").strip() or None
    profil.aktiv_terminierung = form.get("aktiv_terminierung") == "on"
    # v23 (Phase 108, F3/A-1): Produktkompetenz (Sparten WP/PV/KL/WB/GW, Kombi
    # WP+PV(+KL), Objektkompetenz MFH, Gewerbe), Handelsvertreter, Kanal-Regel,
    # Buchungslink (Book with me) am Benutzer
    kompetenz = [code for code in INTERESSE_CODES if form.get(f"kompetenz_{code}") == "on"]
    profil.kompetenz_sparten = json_modul.dumps(kompetenz)
    profil.kompetenz_kombi = form.get("kompetenz_kombi") == "on"
    profil.kompetenz_mfh = form.get("kompetenz_mfh") == "on"
    profil.kompetenz_gewerbe = form.get("kompetenz_gewerbe") == "on" or "GW" in kompetenz
    if profil.kompetenz_gewerbe and "GW" not in kompetenz:
        kompetenz.append("GW")
        profil.kompetenz_sparten = json_modul.dumps(kompetenz)
    profil.terminiert_selbst = form.get("terminiert_selbst") == "on"
    if "buchungslink" in form:
        person.buchungslink = (form.get("buchungslink") or "").strip()[:500] or None
    # Kanal-Regel: der AD steht genau in den angehakten Kanälen (leer = keine)
    lead_termin.kanal_regel_ad_setzen(
        session, person.id, [str(k) for k in form.getlist("kanal_fest")])
    session.flush()
    if profil.start_adresse and profil.start_lat is None:
        try:   # Startadresse sofort geokodieren (best effort)
            from app import geocoding
            lat, lon, status = geocoding.geokodieren(session, profil.start_adresse)
            if status == "ok":
                profil.start_lat, profil.start_lon = lat, lon
        except Exception:
            pass
    session.commit()
    return RedirectResponse(f"/benutzer/{benutzer_id}/ad-profil?meldung="
                            + quote_plus("Profil gespeichert."),
                            status_code=303)
