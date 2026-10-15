# Angebotsverwaltung (Phase 5): Liste mit Status/Suche, Angebot aus Konfiguration
# oder manuell, Editor (Mengen, Positionen entfernen, Freitext, Artikel aus Stamm),
# Duplizieren, Statuspflege.

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app import angebot_aufbau, kfw, sperren
from app import logik as logik_modul
from app.db import get_session
from app.models import (ANGEBOT_STATUS, Angebot, AngebotsPosition, Artikel,
                        Konfiguration, Kunde)
from app.routers.artikel import preis_parsen
from app.templating import render
from app import anfrage   # v27: Formular/JSON in def-Routen
from app import rollen as rollen_modul   # v33: Basisrolle/Rollen-Varianten
from app import lead_boards   # v33 (PLAN_V20 Phase 174): Spalten je Nutzer, gemerkte Sortierung

router = APIRouter(prefix="/angebote")


def _sperr_umleitung(request: Request, angebot_id: int):
    """Bearbeitungssperre für POST-Routen: hält ein anderer Benutzer das
    Angebot gerade im Editor, wird die Änderung abgewiesen (None = frei)."""
    benutzer = request.state.benutzer
    halter = sperren.gesperrt_fuer(angebot_id, benutzer.id if benutzer else 0)
    if halter is None:
        return None
    from urllib.parse import quote_plus
    return RedirectResponse(
        f"/angebote/{angebot_id}?meldung=" + quote_plus(
            f"Keine Änderung möglich – wird gerade von {halter['name']} bearbeitet."),
        status_code=303)


def _speichern(session: Session, aktion, wiederholungen: int = 1) -> None:
    """v22 (PLAN_V15 Phase 103): aktion() ausführen und committen. Bei
    „database is locked“ (ein Hintergrundlauf hält die SQLite-Schreibsperre
    länger als der busy_timeout – bestätigte Ursache des sporadischen
    Internal Server Error beim Löschen/Verschieben) wird zurückgerollt, kurz
    gewartet und die Aktion einmal erneut ausgeführt. Bleibt die Sperre,
    läuft die Ausnahme in den globalen Handler (Fehlerprotokoll + Meldung
    „Datenbank kurz belegt“ statt Internal Server Error).
    v33 (PLAN_V20 Phase 172): die Sitzung einer POST-Route ist eine Schreibsitzung
    (BEGIN IMMEDIATE, app/db.py) – das Warten auf die Sperre passiert damit schon beim
    ersten Zugriff, und db._transaktion_eroeffnen wiederholt dort selbst einmal nach
    0,7 s. Kommt die Ausnahme von diesem bereits wiederholten BEGIN IMMEDIATE, wird
    hier nicht ein zweites Mal gewartet (Gesamtbudget bleibt ≈ 10,7 s wie bisher)."""
    import time

    from sqlalchemy.exc import OperationalError

    from app import betrieb
    for versuch in range(wiederholungen + 1):
        start = time.perf_counter()
        try:
            aktion()
            session.commit()
            # v27 (PLAN_V17 Phase 131): Wartezeit auf die Schreibsperre messen
            # (Commit-Dauer; Betriebs-Seite, /health, Lasttest-Bericht)
            betrieb.schreibsperre_messen(int((time.perf_counter() - start) * 1000))
            return
        except OperationalError as problem:
            session.rollback()
            gesperrt = "locked" in str(problem).lower()
            betrieb.schreibsperre_messen(int((time.perf_counter() - start) * 1000),
                                         locked=gesperrt)
            schon_wiederholt = "BEGIN IMMEDIATE" in str(problem)
            if not gesperrt or versuch >= wiederholungen or schon_wiederholt:
                raise
            time.sleep(0.7)


def _ganzzahl(text) -> int | None:
    """v22: robustes int() für Formularwerte (auch „−5“, Unicode-Ziffern)."""
    try:
        return int(str(text or "").strip())
    except (TypeError, ValueError):
        return None


def _kunden_map(session: Session, angebote) -> dict[int, Kunde]:
    ids = {a.kunde_id for a in angebote}
    if not ids:
        return {}
    return {k.id: k for k in session.query(Kunde).filter(Kunde.id.in_(ids))}


def _verfolgung_nachziehen(session: Session, angebot: Angebot, benutzer=None) -> None:
    """v32 (PLAN_V19 Phase 163, Vertrag N): Verfolgungsstufe des Vorgangs aus den
    Angebotsstatus ableiten (verfolgung.nach_angebotsstatus). Rückfall, solange das Modul
    fehlt: Angenommen → angenommen; Abgelehnt → abgelehnt nur, wenn kein weiteres Angebot
    des Vorgangs offen (Versand vorbereitet/Versendet/Angenommen) ist."""
    if angebot is None or not angebot.vorgang_id:
        return
    try:
        from app import verfolgung
        verfolgung.nach_angebotsstatus(session, angebot, benutzer)
        return
    except (ImportError, AttributeError):
        pass
    from app.models import Vorgang
    vorgang = session.get(Vorgang, angebot.vorgang_id)
    if vorgang is None:
        return
    if angebot.status == "Angenommen":
        vorgang.verfolgung_status = "angenommen"
    elif angebot.status == "Abgelehnt":
        offen = (session.query(Angebot.id)
                 .filter(Angebot.vorgang_id == vorgang.id, Angebot.id != angebot.id,
                         Angebot.archiviert.is_(False),
                         Angebot.status.in_(("Versand vorbereitet", "Versendet",
                                             "Versendet (extern)", "Angenommen"))).first())
        if offen is None:
            vorgang.verfolgung_status = "abgelehnt"


def _verfolgung_werte() -> list[tuple[str, str]]:
    """v32 (Phase 163): Werte des Filters „Verfolgung“ der Angebotsliste – aus
    verfolgung.STATUS/status_text (N), Rückfall mit den fünf Stufen des Plans."""
    try:
        from app import verfolgung
        return [(s, verfolgung.status_text(s) or s) for s in verfolgung.STATUS]
    except (ImportError, AttributeError):
        return [("versendet", "Versendet"), ("nachgefasst", "Nachgefasst"),
                ("bestellung_angekuendigt", "Bestellung angekündigt"),
                ("angenommen", "Angenommen"), ("abgelehnt", "Abgelehnt")]


def _inaktiv_tage(session: Session, angebote, vorgaenge_map: dict) -> dict[int, int]:
    """v33 (PLAN_V20 Phase 174/176, Vertrag N): Tage „ohne Kontakt“ je Angebot über
    `nachfassen.inaktiv_tage_fuer(session, vorgang)` (14 Tage, MFH 20 – Parameter inaktiv_tage/
    inaktiv_tage_mfh). Fehlt die Funktion (N noch nicht integriert) oder liefert sie nichts,
    bleibt das Kennzeichen leer; ein Fehler im Nachfass-Modul blockiert die Liste nie."""
    try:
        from app import nachfassen
    except ImportError:
        return {}
    # v33 (Phase 176, Vorschlag N 4c): Mengenabfrage für alle Vorgänge der Seite – kein Aufruf je Zeile
    mengen = getattr(nachfassen, "inaktiv_kennzeichen", None)
    if mengen is not None:
        try:
            vorgaenge = list({a.vorgang_id: vorgaenge_map.get(a.vorgang_id) for a in angebote
                              if a.vorgang_id and vorgaenge_map.get(a.vorgang_id) is not None}.values())
            tage_je_vorgang = mengen(session, vorgaenge) if vorgaenge else {}
            return {a.id: int(tage_je_vorgang[a.vorgang_id]) for a in angebote
                    if a.vorgang_id in tage_je_vorgang and tage_je_vorgang[a.vorgang_id]}
        except Exception:   # noqa: BLE001 – Rückfall auf den Einzelaufruf
            pass
    funktion = getattr(nachfassen, "inaktiv_tage_fuer", None)
    if funktion is None:
        return {}
    je_vorgang: dict[int, int | None] = {}
    ergebnis: dict[int, int] = {}
    for a in angebote:
        vorgang = vorgaenge_map.get(a.vorgang_id) if a.vorgang_id else None
        if vorgang is None:
            continue
        if vorgang.id not in je_vorgang:
            try:
                wert = funktion(session, vorgang)
            except TypeError:
                try:
                    wert = funktion(vorgang)
                except Exception:   # noqa: BLE001
                    wert = None
            except Exception:   # noqa: BLE001 – Nachfass-Modul darf die Liste nie blockieren
                wert = None
            if isinstance(wert, dict):
                wert = wert.get("tage")
            try:
                wert = int(wert) if wert not in (None, "", False) else None
            except (TypeError, ValueError):
                wert = None
            je_vorgang[vorgang.id] = wert if wert and wert > 0 else None
        if je_vorgang[vorgang.id]:
            ergebnis[a.id] = je_vorgang[vorgang.id]
    return ergebnis


@router.get("")
def liste(request: Request, q: str = "", status: str = "", interesse: str = "",
                vertriebler_id: int = 0, sortierung: str = "nummer", kanal: str = "",
                verfolgung: str = "", sparte: str = "", inaktiv: str = "",
                session: Session = Depends(get_session)):
    """Angebotsliste. v33 (PLAN_V20 Phase 174): Lead-Board-Layout – Spalten je Nutzer
    (Katalog `angebote`, EK/DB nur mit Kalkulationssicht), gemerkte Spaltensortierung vor dem
    Rendern (die Grundreihenfolge `sortierung` = nummer|datum|kunde|vertriebler gilt nur ohne
    gemerkte Spalte), Filter `inaktiv=1` = Kennzeichen „ohne Kontakt seit X Tagen“ (Phase 176,
    Vertrag N), Summenzeile folgt der gefilterten UND sortierten Liste."""
    abfrage = session.query(Angebot).options(joinedload(Angebot.positionen))
    if sparte:   # Sparten-Filter (v8): Konfigurator-Typ des Angebots
        abfrage = abfrage.filter(Angebot.konfigurator_typ == sparte)
    # Archiv (v5): Standardansicht ohne archivierte, Filter „Archiv“ nur diese
    if status == "archiv":
        abfrage = abfrage.filter(Angebot.archiviert.is_(True))
    else:
        abfrage = abfrage.filter(Angebot.archiviert.is_(False))
        if status:
            abfrage = abfrage.filter(Angebot.status == status)
        else:
            # v9: überholte Versionen nur über den Status-Filter/die Historie
            abfrage = abfrage.filter(Angebot.status != "Überholt")
    angebote = abfrage.order_by(Angebot.nummer.desc()).all()
    kunden = _kunden_map(session, angebote)
    if q:
        suchwort = q.lower()
        angebote = [a for a in angebote
                    if suchwort in a.nummer.lower()
                    or (a.kunde_id in kunden
                        and (suchwort in kunden[a.kunde_id].anzeige_name.lower()
                             or suchwort in (kunden[a.kunde_id].ort or "").lower()))]
    if interesse:   # Filter nach Interesse des Kunden (Phase 33)
        angebote = [a for a in angebote
                    if a.kunde_id in kunden and interesse in kunden[a.kunde_id].interessen]
    if kanal:       # Vertriebskanal des Kunden (v6)
        angebote = [a for a in angebote
                    if a.kunde_id in kunden and kunden[a.kunde_id].vertriebskanal == kanal]
    # v11 (Phase 66): Projekt-Verknüpfung je Angebot (Zeilenaktion)
    from app import projektierung as projektierung_modul
    from app.models import Gewerk as GewerkModell, Projekt as ProjektModell
    gewerk_map = {g.id: g for g in session.query(GewerkModell)}
    projekt_map = {p.id: p for p in session.query(ProjektModell)}
    projekt_je_angebot = {}
    for a in angebote:
        if a.projekt_gewerk_id and a.projekt_gewerk_id in gewerk_map:
            g = gewerk_map[a.projekt_gewerk_id]
            if g.projekt_id in projekt_map:
                projekt_je_angebot[a.id] = projekt_map[g.projekt_id]
    projekt_modul_ok = projektierung_modul.modul_sichtbar(session, request.state.benutzer)
    # Verfolgung (v10): Ampel/Wiedervorlage des VORGANGS je Angebot
    from app.models import Vorgang
    vorgaenge_map = {v.id: v for v in session.query(Vorgang)}
    def vorgang_von(a):
        return vorgaenge_map.get(a.vorgang_id)
    # v32 (PLAN_V19 Phase 163, Vertrag N): Filter „Verfolgungsstatus“ (?verfolgung=
    # versendet|nachgefasst|bestellung_angekuendigt|angenommen|abgelehnt) über
    # verfolgung.filter_anwenden (Liste von Angeboten + vorgaenge_map); Rückfall ohne
    # Modul: Vergleich mit vorgaenge.verfolgung_status
    verfolgung_werte = _verfolgung_werte()
    verfolgung_filter = verfolgung if verfolgung in dict(verfolgung_werte) else ""
    if verfolgung_filter:
        try:
            from app import verfolgung as verfolgung_modul
            angebote = list(verfolgung_modul.filter_anwenden(angebote, verfolgung_filter,
                                                             vorgaenge_map=vorgaenge_map))
        except (ImportError, AttributeError):
            angebote = [a for a in angebote
                        if (v := vorgang_von(a)) is not None
                        and (v.verfolgung_status or "") == verfolgung_filter]
    elif verfolgung == "faellig":   # fällige Vorgangs-Wiedervorlagen
        from datetime import datetime as dt
        angebote = [a for a in angebote
                    if (v := vorgang_von(a)) is not None
                    and v.wiedervorlage_am and v.wiedervorlage_am <= dt.now()]
    elif verfolgung in ("heiss", "warm", "kalt"):
        angebote = [a for a in angebote
                    if (v := vorgang_von(a)) is not None
                    and v.verfolgung_ampel == verfolgung]
    # Vertriebler je Angebot (v5-Nachtrag): über die verknüpfte Erfassung
    from app.models import Benutzer, Erfassung
    vertriebler = {b.id: b for b in session.query(Benutzer)}
    angebot_vertriebler: dict[int, int] = {}
    for a in angebote:            # Fallback: manuelles Angebot ohne Erfassung
        if a.vertriebler_id:
            angebot_vertriebler[a.id] = a.vertriebler_id
    for e in session.query(Erfassung).filter(Erfassung.angebot_id.isnot(None)):
        angebot_vertriebler[e.angebot_id] = e.benutzer_id   # Erfassung gewinnt
    vertriebler_werte = sorted({angebot_vertriebler[a.id] for a in angebote
                                if a.id in angebot_vertriebler},
                               key=lambda i: vertriebler[i].name if i in vertriebler else "")
    if vertriebler_id:
        angebote = [a for a in angebote if angebot_vertriebler.get(a.id) == vertriebler_id]
    # Sortierung (v5-Nachtrag): Nummer (Standard, absteigend), Datum, Kunde, Vertriebler
    def name_von(a):
        bid = angebot_vertriebler.get(a.id)
        return (vertriebler[bid].name if bid in vertriebler else "zzz").lower()
    if sortierung == "vertriebler":
        angebote.sort(key=lambda a: (name_von(a), a.nummer))
    elif sortierung == "kunde":
        angebote.sort(key=lambda a: (kunden[a.kunde_id].anzeige_name.lower()
                                     if a.kunde_id in kunden else "zzz", a.nummer))
    elif sortierung == "datum":
        from datetime import datetime as _dt
        angebote.sort(key=lambda a: a.datum or _dt.min, reverse=True)
    else:
        sortierung = "nummer"
    # DB-Farbampel (Phase 24): Schwellen in Euro, in der Parametrierung pflegbar
    # v13-PV (Phase 78): Schwellen je Sparte (leer = allgemeine Schwellen)
    from app import sparten as sparten_modul
    from app.models import DB_AMPEL_SPARTEN, db_schwellen
    rot_unter, gruen_ueber = db_schwellen(session)
    db_schwellen_cent = {sp: tuple(w * 100 for w in db_schwellen(session, sp))
                         for sp in DB_AMPEL_SPARTEN}
    # v31 (PLAN_LEAD_V5 Phase 157): Sparten ohne eigene Schwellen (GW, MS, WA, DMS)
    # fallen auf die WP-Schwellen zurück
    for sp in sparten_modul.SPARTEN:
        db_schwellen_cent.setdefault(sp, db_schwellen_cent.get("WP", (rot_unter * 100, gruen_ueber * 100)))
    # Mail-Verlauf (Phase 27): eingehende Antworten je Angebot zählen
    from sqlalchemy import func

    from app.models import AngebotsMail
    mail_zaehler = dict(session.query(AngebotsMail.angebot_id, func.count())
                        .filter(AngebotsMail.eingehend.is_(True))
                        .group_by(AngebotsMail.angebot_id))
    # v33 (Phase 174/176, Vertrag N): Kennzeichen „ohne Kontakt seit X Tagen“ als Spalte/Filter
    inaktiv_tage = _inaktiv_tage(session, angebote, vorgaenge_map)
    inaktiv_filter = inaktiv in ("1", "true", "ja")
    if inaktiv_filter:
        angebote = [a for a in angebote if inaktiv_tage.get(a.id)]
    # v33 (PLAN_V20 Phase 174): Spalten je Nutzer (Katalog nach Basisrolle und
    # Kalkulationssicht) und gemerkte Spaltensortierung – angewendet VOR der Summenzeile,
    # damit Summe und Reihenfolge zur gezeigten Liste gehören
    board = "angebote"
    benutzer_obj = request.state.benutzer
    spalten = lead_boards.spalten_fuer(session, benutzer_obj, board)
    spalten_sortierung = lead_boards.sortierung_fuer(session, benutzer_obj, board)
    vertriebler_namen = {a.id: vertriebler[angebot_vertriebler[a.id]].name for a in angebote
                         if angebot_vertriebler.get(a.id) in vertriebler}
    lead_boards.zeilen_sortieren(
        angebote, spalten_sortierung,
        wert=lambda a, key: lead_boards.angebot_sortwert(a, key, kunden, vorgaenge_map,
                                                         vertriebler_namen, inaktiv_tage))
    # Summenzeile (v6): über die aktuell gefilterte (und seit v33 sortierte) Liste
    summen_gesamt = {"netto": 0, "endbetrag": 0, "db": 0}
    for a in angebote:
        su = a.summen()
        summen_gesamt["netto"] += su["netto"]
        summen_gesamt["endbetrag"] += su["endbetrag"]
        summen_gesamt["db"] += a.deckungsbeitrag()["db"]
    return render(request, "angebote/liste.html", aktiv="/angebote",
                  summen_gesamt=summen_gesamt,
                  angebote=angebote, kunden=kunden, q=q, status=status,
                  interesse=interesse, vertriebler_id=vertriebler_id, sortierung=sortierung,
                  kanal=kanal, verfolgung=verfolgung, sparte=sparte,
                  # v33 (Phase 174): Lead-Board-Layout
                  board=board, spalten=spalten, spalten_sortierung=spalten_sortierung,
                  ctx={"board": board, "sortierung": spalten_sortierung},
                  spalten_fest=lead_boards.spalten_fest(board),
                  sparten_liste=sparten_modul.SPARTEN,
                  inaktiv=inaktiv_filter, inaktiv_tage=inaktiv_tage,
                  # v32 (Phase 163): Filter-Markup von N (templates/angebote/liste.html)
                  verfolgung_filter=verfolgung_filter, verfolgung_werte=verfolgung_werte,
                  vorgaenge_map=vorgaenge_map,
                  projekt_je_angebot=projekt_je_angebot,
                  projekt_modul_ok=projekt_modul_ok,
                  heute=__import__("datetime").datetime.now(),
                  kanal_werte=sorted({kunden[a.kunde_id].vertriebskanal for a in angebote
                                      if a.kunde_id in kunden and kunden[a.kunde_id].vertriebskanal}
                                     | ({kanal} if kanal else set())),
                  vertriebler=vertriebler, angebot_vertriebler=angebot_vertriebler,
                  vertriebler_werte=vertriebler_werte,
                  status_liste=ANGEBOT_STATUS, mail_zaehler=mail_zaehler,
                  db_rot_cent=rot_unter * 100, db_gruen_cent=gruen_ueber * 100,
                  db_schwellen_cent=db_schwellen_cent,
                  # v11 (Phase 70): Rolle projektierung sieht die Liste lesend –
                  # DB-Spalte nur mit kalkulation_sichtbar, Öffnen → PDF
                  kalk_sichtbar=(request.state.benutzer.basisrolle in ("admin", "innendienst")
                                 or request.state.benutzer.kalkulation_sichtbar),
                  nur_lesend=request.state.benutzer.basisrolle in ("projektierung",
                                                              "leadmanagement"),
                  meldung=request.query_params.get("meldung", ""))


@router.get("/rabatt-freigaben")
def rabatt_freigaben(request: Request, session: Session = Depends(get_session)):
    """v10 (Phase 59): offene AD-Rabatt-Anfragen – der Innendienst sieht die
    €-Auswirkung auf den DB und genehmigt oder lehnt mit Kommentar ab."""
    from app.models import Benutzer, RabattFreigabe
    from app.routers.meine_angebote import _db_ampel, _db_mit_rabatt
    freigaben = (session.query(RabattFreigabe)
                 .filter(RabattFreigabe.status == "offen")
                 .order_by(RabattFreigabe.angefragt_am).all())
    angebote = {a.id: a for a in session.query(Angebot)
                .filter(Angebot.id.in_([f.angebot_id for f in freigaben] or [0]))}
    kunden = _kunden_map(session, angebote.values())
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    zeilen = []
    for f in freigaben:
        angebot = angebote.get(f.angebot_id)
        if angebot is None:
            continue
        db_neu = _db_mit_rabatt(angebot, f.rabatt_cent, f.rabatt_prozent)
        zeilen.append({"freigabe": f, "angebot": angebot,
                       "kunde": kunden.get(angebot.kunde_id),
                       "ad": benutzer_map.get(f.benutzer_id),
                       "db_alt": angebot.deckungsbeitrag()["db"],
                       "db_neu": db_neu,
                       "ampel_neu": _db_ampel(session, db_neu,
                                              angebot.konfigurator_typ or "WP")})
    return render(request, "angebote/rabatt_freigaben.html", aktiv="/angebote",
                  zeilen=zeilen,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/rabatt-freigaben/{freigabe_id}/entscheiden")
def rabatt_entscheiden(request: Request, freigabe_id: int,
                             session: Session = Depends(get_session)):
    """Genehmigen wendet den Rabatt an (Entwurf direkt, versendet → neue
    Version); Ablehnen verlangt einen Kommentar. Beides landet im
    Notizen-Chat des Vorgangs."""
    from urllib.parse import quote_plus

    from app import vorgaenge as vorgaenge_modul
    from app.models import RabattFreigabe
    from app.routers.meine_angebote import rabatt_anwenden
    freigabe = session.get(RabattFreigabe, freigabe_id)
    if freigabe is None or freigabe.status != "offen":
        return RedirectResponse("/angebote/rabatt-freigaben", status_code=303)
    form = anfrage.formular(request)
    aktion = form.get("aktion", "")
    kommentar = (form.get("kommentar") or "").strip()[:500]
    benutzer = request.state.benutzer
    angebot = session.get(Angebot, freigabe.angebot_id)
    rabatt_text = (f"{freigabe.rabatt_prozent:g} %" if freigabe.rabatt_prozent
                   else f"{(freigabe.rabatt_cent or 0) / 100:.2f} €".replace(".", ","))
    from datetime import datetime as dt
    if aktion == "genehmigen" and angebot is not None:
        ziel = rabatt_anwenden(session, angebot, freigabe.rabatt_cent,
                               freigabe.rabatt_prozent, freigabe.rabatt_bezeichnung)
        if ziel.id != angebot.id:
            # v30 (Phase 150): neue Version übernimmt die Zahlungsbedingung
            _zahlungsbedingung_uebernehmen(ziel, angebot)
            from app import monday_rueckspielung
            monday_rueckspielung.wert_aktualisieren(session, ziel,
                                                    "neue Version (Rabatt-Freigabe)")
        freigabe.status = "genehmigt"
        freigabe.kommentar = kommentar
        freigabe.entschieden_am = dt.now()
        freigabe.entschieden_von = benutzer.id
        if freigabe.vorgang_id:
            vorgaenge_modul.notiz_anlegen(
                session, freigabe.vorgang_id, benutzer,
                f"Rabatt-Freigabe GENEHMIGT: {rabatt_text} auf {ziel.nummer}"
                + (f" (neue Version von {angebot.nummer})" if ziel.id != angebot.id else "")
                + (f" – {kommentar}" if kommentar else ""),
                herkunft="Rabatt-Workflow")
        session.commit()
        return RedirectResponse("/angebote/rabatt-freigaben?meldung=" + quote_plus(
            f"Genehmigt – Rabatt {rabatt_text} steht an {ziel.nummer}."),
            status_code=303)
    if aktion == "ablehnen":
        if not kommentar:
            return RedirectResponse("/angebote/rabatt-freigaben?meldung=" + quote_plus(
                "Bitte beim Ablehnen einen Kommentar für den Außendienst angeben."),
                status_code=303)
        freigabe.status = "abgelehnt"
        freigabe.kommentar = kommentar
        freigabe.entschieden_am = dt.now()
        freigabe.entschieden_von = benutzer.id
        if freigabe.vorgang_id:
            vorgaenge_modul.notiz_anlegen(
                session, freigabe.vorgang_id, benutzer,
                f"Rabatt-Freigabe ABGELEHNT ({rabatt_text}"
                + (f" auf {angebot.nummer}" if angebot else "") + f"): {kommentar}",
                herkunft="Rabatt-Workflow")
        session.commit()
        return RedirectResponse("/angebote/rabatt-freigaben?meldung=" + quote_plus(
            "Abgelehnt – der Kommentar steht im Notizen-Chat des Vorgangs."),
            status_code=303)
    return RedirectResponse("/angebote/rabatt-freigaben", status_code=303)


@router.get("/aus-konfiguration/{konfig_id}")
def aus_konfiguration(konfig_id: int, session: Session = Depends(get_session)):
    konfig = session.get(Konfiguration, konfig_id)
    if konfig is None or konfig.status != "fertig":
        return RedirectResponse("/angebote?meldung=Konfiguration+nicht+gefunden+oder+nicht+fertig",
                                status_code=303)
    logik, bericht = logik_modul.hole_logik(session)
    if not bericht.ok:
        return RedirectResponse("/parametrierung", status_code=303)
    angebot = angebot_aufbau.angebot_anlegen(
        session, konfig.kunde_id, antworten=json.loads(konfig.antworten_json or "{}"),
        logik=logik, konfiguration_id=konfig.id)
    return RedirectResponse(f"/angebote/{angebot.id}", status_code=303)


@router.get("/neu")
def neu(kunde_id: int = 0, session: Session = Depends(get_session)):
    kunde = session.get(Kunde, kunde_id)
    if kunde is None:
        return RedirectResponse("/konfigurator", status_code=303)
    angebot = angebot_aufbau.angebot_anlegen(session, kunde.id)
    return RedirectResponse(f"/angebote/{angebot.id}", status_code=303)


@router.get("/{angebot_id}")
def editor(request: Request, angebot_id: int,
                 session: Session = Depends(get_session)):
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote?meldung=Angebot+nicht+gefunden", status_code=303)
    # Externer TAIFUN-Eintrag (v7): eigene Detailseite statt Editor –
    # kein PDF, kein Versand, aber Verfolgung, Notizen und Statuspflege
    if angebot.extern:
        from app.models import AngebotsNotiz, Benutzer as BenutzerModell, EXTERN_STATUS, Erfassung
        kunde = session.get(Kunde, angebot.kunde_id)
        erfassung = (session.query(Erfassung)
                     .filter(Erfassung.angebot_id == angebot.id).first())
        vertriebler = (session.get(BenutzerModell, angebot.vertriebler_id)
                       if angebot.vertriebler_id else None)
        notizen = (session.query(AngebotsNotiz)
                   .filter(AngebotsNotiz.angebot_id == angebot.id)
                   .order_by(AngebotsNotiz.angelegt_am.desc()).all())
        from app.models import AblehnungsGrund
        gruende = (session.query(AblehnungsGrund)
                   .filter(AblehnungsGrund.aktiv.is_(True))
                   .order_by(AblehnungsGrund.sort, AblehnungsGrund.id).all())
        from app import vorgaenge as vorgaenge_modul
        vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
        session.commit()
        from app import projektierung as projektierung_modul
        projekt_obj, _gewerk = projektierung_modul.projekt_zu_angebot(session, angebot)
        projekt_modul_ok = projektierung_modul.modul_sichtbar(session, request.state.benutzer)
        return render(request, "angebote/extern.html", aktiv="/angebote",
                      projekt_obj=projekt_obj, projekt_modul_ok=projekt_modul_ok,
                      angebot=angebot, kunde=kunde, erfassung=erfassung,
                      vertriebler=vertriebler, notizen=notizen,
                      ablehnungsgruende=gruende, vorgang=vorgang,
                      status_liste=EXTERN_STATUS,
                      meldung=request.query_params.get("meldung", ""))
    # Bearbeitungssperre: Erster im Editor hält das Angebot, andere lesen nur
    benutzer = request.state.benutzer
    sperr_halter = sperren.erwerben(angebot.id, benutzer.id if benutzer else 0,
                                    benutzer.name if benutzer else "?")
    nur_lesen = sperr_halter is not None
    kunde = session.get(Kunde, angebot.kunde_id)
    artikel_liste = (session.query(Artikel).filter(Artikel.aktiv.is_(True))
                     .order_by(Artikel.pos_nr).all())
    # v11 (Phase 66): Zielkunden-Auswahl für „Für anderen Kunden kopieren"
    kunden_liste = (session.query(Kunde).filter(Kunde.aktiv.is_(True))
                    .order_by(Kunde.nachname, Kunde.firma).all())
    protokoll = json.loads(angebot.protokoll_json or "[]")

    # Anzeigenummern (Phase 18/v5): eigene Nummer oder fortlaufend 001, 002, …;
    # die interne TAIFUN-/Z-Referenz bleibt in pos_nr/guid gespeichert
    for p, nummer in zip(angebot.positionen, angebot.nummerierung()):
        p.lfd_nr = nummer

    # Positionen nach Gruppe (Blockreihenfolge) für die Anzeige bündeln
    gruppen: list[dict] = []
    for p in angebot.positionen:
        if not gruppen or gruppen[-1]["name"] != p.gruppe or gruppen[-1]["block"] != p.block_nr:
            gruppen.append({"name": p.gruppe, "block": p.block_nr, "positionen": []})
        gruppen[-1]["positionen"].append(p)

    # KfW-Aufschlüsselung: Kosten der Maßnahme = Angebotssumme brutto (automatisch)
    kfw_ergebnis = None
    kfw_warnung = None
    kfw_daten = json.loads(angebot.kfw_json or "{}")
    if kfw_daten.get("O01"):
        logik, bericht = logik_modul.hole_logik(session)
        if bericht is not None:
            parameter, _ = kfw.parameter_lesen(logik)
            eingaben = kfw.eingaben_aus_antworten(kfw_daten, angebot.summen()["endbetrag"])
            if eingaben is not None:
                kfw_ergebnis = kfw.ergebnis_fuer_angebot(parameter, eingaben, angebot)
                kfw_warnung = kfw.gueltigkeits_warnung(parameter)

    # Anhänge-Vorschau (Phase 15): was würde beim Versand mitgehen?
    from app import anhaenge as anhaenge_modul
    logik, _bericht = logik_modul.hole_logik(session)
    anhaenge_liste = anhaenge_modul.fuer_angebot(
        logik, angebot, anhaenge_modul.profilname_fuer(session, angebot))
    vollmacht = anhaenge_modul.vollmacht_erforderlich(angebot)

    # Angebotsverfolgung: Alt-Notizen (Historie) + Vorgang (v10: die
    # Verfolgung lebt auf Vorgangsebene, der Chat in der Vorgangsakte)
    from app import vorgaenge as vorgaenge_modul
    from app.models import AngebotsNotiz
    notizen = (session.query(AngebotsNotiz)
               .filter(AngebotsNotiz.angebot_id == angebot.id)
               .order_by(AngebotsNotiz.angelegt_am.desc()).all())
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    session.commit()
    # v11 (Phase 66): „Angebot → Projekt"-Button bzw. Link zum Projekt
    from app import projektierung as projektierung_modul
    projekt_obj, _gewerk = projektierung_modul.projekt_zu_angebot(session, angebot)
    projekt_modul_ok = projektierung_modul.modul_sichtbar(session, request.state.benutzer)
    # v10 (Phase 61): Geschwister-Angebote als Verknüpfungsziele fürs
    # Alternativ-Kennzeichen (z. B. „PV-Angebot AN-…“)
    geschwister = [f"{(a.konfigurator_typ or 'WP')}-Angebot {a.nummer}"
                   for a in session.query(Angebot)
                   .filter(Angebot.vorgang_id == vorgang.id,
                           Angebot.id != angebot.id,
                           Angebot.status != "Überholt")]
    # v34 (PLAN_V21 Phase 180, Agent E): Alternativ-Badge mit Link/Gültigkeit je Position,
    # Knopf „Elektroarbeiten ins PV-Angebot“ (nur WP/KL/WB-Entwurf mit PV-Angebot im Vorgang),
    # „zurückholen“, Hinweis „Geschwister-Angebot nicht mehr gültig“, Herkunft übernommener
    # Kopien im PV-Angebot, Hinweis „Auslegung (intern)“ nur Innendienst/Admin
    from app import elektro_pv
    alternativ_info = elektro_pv.alternativ_info(session, angebot)
    elektro_pv_ziel = elektro_pv.knopf_sichtbar(session, angebot)
    elektro_rueckholbar, elektro_rueckhol_grund = elektro_pv.rueckholbar(session, angebot)
    alternativ_ungueltig = [p for p in angebot.positionen
                            if p.alternativ and not alternativ_info[p.id]["gueltig"]]
    herkunft_ids = {p.uebernommen_von_angebot_id for p in angebot.positionen
                    if p.uebernommen_von_angebot_id}
    herkunft_map = {a.id: a for a in session.query(Angebot).filter(Angebot.id.in_(herkunft_ids))} \
        if herkunft_ids else {}
    uebernommen_von = {p.id: herkunft_map[p.uebernommen_von_angebot_id]
                       for p in angebot.positionen
                       if p.uebernommen_von_angebot_id in herkunft_map}
    auslegung_sichtbar = (benutzer is not None
                          and benutzer.basisrolle in ("admin", "innendienst")
                          and bool((angebot.auslegung_text or "").strip()))

    # Vertriebler des Vorgangs (v5-Nachtrag): anzeigen + änderbar
    from app import mail_vorlagen
    from app.models import Benutzer as BenutzerModell
    angebot_vertriebler = mail_vorlagen.vertriebler_fuer_angebot(session, angebot)
    aussendienst = (session.query(BenutzerModell)
                    .filter(rollen_modul.filter_basis("aussendienst"),
                            BenutzerModell.aktiv.is_(True))
                    .order_by(BenutzerModell.name).all())

    from app.models import AblehnungsGrund
    ablehnungsgruende = (session.query(AblehnungsGrund)
                         .filter(AblehnungsGrund.aktiv.is_(True))
                         .order_by(AblehnungsGrund.sort, AblehnungsGrund.id).all())
    # v9: Angebotsprofil (Nachtext/Positions-/Versandregeln) + Vortext-Override
    from app import angebotsprofile
    from app.models import Profil
    profil = angebotsprofile.profil_fuer_angebot(session, angebot, kunde)
    profile = session.query(Profil).order_by(Profil.id).all()
    # v9: Versions-Historie über die Stammnummer
    stamm = angebot.stamm_nummer
    versionen = (session.query(Angebot)
                 .filter(or_(Angebot.nummer == stamm,
                             Angebot.nummer.like(f"{stamm}.%")))
                 .order_by(Angebot.nummer).all())
    # v9: fachliche Hinweise (z. B. Solarthermie-Widerspruch) aus dem Protokoll
    from app import konfigurator as engine_modul
    fachhinweise = engine_modul.hinweise_aus_protokoll(protokoll)
    profil_hinweise = {p_.id: angebotsprofile.regeln_beschreibung(p_) for p_ in profile}
    # v20 (Phase 98): effektive Anschriften für die Karten
    from app import anschriften as anschriften_modul
    _re = anschriften_modul.rechnung(angebot, kunde)
    _li = anschriften_modul.lieferung(angebot, kunde)
    anschrift_kontext = dict(
        anschrift_rechnung=_re, anschrift_liefer=_li,
        anschrift_abweichend=bool(anschriften_modul.empfaenger(angebot, kunde)[1]
                                  or anschriften_modul.lieferzeile(angebot, kunde)),
        anschrift_rechnung_text=anschriften_modul.einzeilig(_re),
        anschrift_liefer_text=(anschriften_modul.einzeilig(_li)
                               if anschriften_modul.lieferzeile(angebot, kunde)
                               else "wie Ausführungsort"))
    # v30 (PLAN_V18 Phase 150): Zahlungsbedingung – Dropdown der aktiven Einträge,
    # Vorschau des Namens; Phase 149: Hinweis „folgt auf dem Lieferschein Pos. …“
    from app import lieferschein_pdf, zahlungsbedingungen
    zb_eintraege, zb_gewaehlt = zahlungsbedingungen.auswahl_fuer_editor(session, angebot)
    zb_name = zahlungsbedingungen.fuer_angebot(session, angebot)[0]
    folge_hinweise = lieferschein_pdf.folge_hinweise(
        angebot, lieferschein_pdf.folgepositionen_lesen(session))
    return render(request, "angebote/editor.html", aktiv="/angebote",
                  **anschrift_kontext,
                  zahlungsbedingungen=zb_eintraege, zahlungsbedingung_key=zb_gewaehlt,
                  zahlungsbedingung_name=zb_name,
                  zahlungsbedingung_freitext=zahlungsbedingungen.FREITEXT,
                  folge_hinweise=folge_hinweise,
                  folge_hinweis_text=lieferschein_pdf.FOLGE_HINWEIS,
                  ablehnungsgruende=ablehnungsgruende,
                  profil=profil, profile=profile, profil_hinweise=profil_hinweise,
                  fachhinweise=fachhinweise, versionen=versionen,
                  vorgang=vorgang, geschwister=geschwister,
                  alternativ_info=alternativ_info, elektro_pv_ziel=elektro_pv_ziel,   # v34
                  elektro_rueckholbar=elektro_rueckholbar,
                  elektro_rueckhol_grund=elektro_rueckhol_grund,
                  alternativ_ungueltig=alternativ_ungueltig, uebernommen_von=uebernommen_von,
                  auslegung_sichtbar=auslegung_sichtbar,
                  projekt_obj=projekt_obj, projekt_modul_ok=projekt_modul_ok,
                  vortext_standard=angebotsprofile.vortext_fuer_angebot(session, angebot),
                  angebot=angebot, kunde=kunde, gruppen=gruppen,
                  summen=angebot.summen(), artikel_liste=artikel_liste,
                  kunden_liste=kunden_liste,
                  deckung=angebot.deckungsbeitrag(),
                  protokoll=protokoll, status_liste=ANGEBOT_STATUS,
                  kfw_ergebnis=kfw_ergebnis, kfw_warnung=kfw_warnung,
                  anhaenge_liste=anhaenge_liste, vollmacht=vollmacht,
                  angebot_vertriebler=angebot_vertriebler, aussendienst=aussendienst,
                  notizen=notizen,
                  nur_lesen=nur_lesen, sperr_halter=sperr_halter,
                  versand=request.query_params.get("versand", ""),
                  weblink=request.query_params.get("weblink", ""),
                  meldung=request.query_params.get("meldung", ""))


@router.post("/{angebot_id}/anschriften")
def anschriften_setzen(request: Request, angebot_id: int,
                             session: Session = Depends(get_session)):
    """v20 (Phase 98): Rechnungs- und Lieferanschrift (Karten im Editor) –
    nur im Entwurf; versendete Angebote über „Überarbeiten“ (.2)."""
    from urllib.parse import quote_plus

    from app import anschriften
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    if angebot.status != "Entwurf" or angebot.extern:
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "Anschriften sind nur im Entwurf änderbar – bitte „Überarbeiten“ "
            "(neue Version) nutzen."), status_code=303)
    form = anfrage.formular(request)
    anschriften.setzen(angebot, "rechnung", anschriften.aus_formular(form, "rechnung"))
    anschriften.setzen(angebot, "liefer", anschriften.aus_formular(form, "liefer"))
    angebot.liefer_anschrift = ""        # Alt-Text v13 ist jetzt strukturiert
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "Anschriften gespeichert."), status_code=303)


@router.post("/{angebot_id}/lieferanschrift")
def lieferanschrift_setzen(request: Request, angebot_id: int,
                                 session: Session = Depends(get_session)):
    """v11 (Phase 66): abweichende Lieferanschrift (optional, z. B.
    Contracting) – eigene Zeile im PDF unter Rechnungs-/Ausführungsanschrift."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = anfrage.formular(request)
    angebot.liefer_anschrift = (form.get("liefer_anschrift") or "").strip()[:300]
    session.commit()
    return RedirectResponse(
        f"/angebote/{angebot_id}?meldung=Lieferanschrift+gespeichert", status_code=303)


@router.post("/{angebot_id}/ust")
def ust_setzen(request: Request, angebot_id: int,
                     session: Session = Depends(get_session)):
    """v13-PV (Phase 75): Steuersatz je Angebot (19 % oder 0 % nach
    § 12 Abs. 3 UStG) – wirkt auf Summen, Rabatt, DB, monday, Statistik."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or angebot.extern:
        return RedirectResponse("/angebote", status_code=303)
    form = anfrage.formular(request)
    wert = (form.get("ust_satz") or "").strip()
    if wert in ("0", "19"):
        angebot.ust_satz = float(wert)
        session.commit()
    return RedirectResponse(
        f"/angebote/{angebot_id}?meldung=Steuersatz+gespeichert", status_code=303)


@router.post("/{angebot_id}/wirtschaftlichkeit")
def wirtschaftlichkeit_setzen(request: Request, angebot_id: int,
                                    session: Session = Depends(get_session)):
    """v22 (PLAN_V15 Phase 102): Häkchen „Wirtschaftlichkeit im PDF
    ausblenden“ – nur bei PV-Angeboten; die drei Wirtschaftlichkeitsseiten
    entfallen dann im PDF (pdf_export.wirtschaftlichkeit_fuer liefert None).
    Überarbeiten/Duplizieren/Kopieren übernehmen das Häkchen."""
    from urllib.parse import quote_plus
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or angebot.extern:
        return RedirectResponse("/angebote", status_code=303)
    if (angebot.konfigurator_typ or "WP") != "PV":
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    form = anfrage.formular(request)
    angebot.wirtschaftlichkeit_ausblenden = form.get("ausblenden") == "on"
    session.commit()
    meldung = ("Wirtschaftlichkeit im PDF ausgeblendet"
               if angebot.wirtschaftlichkeit_ausblenden
               else "Wirtschaftlichkeit im PDF wieder eingeblendet")
    return RedirectResponse(
        f"/angebote/{angebot_id}?meldung=" + quote_plus(meldung), status_code=303)


@router.post("/{angebot_id}/sperre")
def sperre_verlaengern(request: Request, angebot_id: int):
    """Heartbeat des offenen Editors (alle 4 Minuten per JS)."""
    benutzer = request.state.benutzer
    ok = sperren.verlaengern(angebot_id, benutzer.id if benutzer else 0)
    from fastapi.responses import JSONResponse
    return JSONResponse({"ok": ok})


@router.post("/{angebot_id}/sperre-frei")
def sperre_freigeben(request: Request, angebot_id: int):
    """Freigabe beim Verlassen der Seite (sendBeacon); sonst läuft die
    Sperre nach 10 Minuten ohne Heartbeat von selbst ab."""
    benutzer = request.state.benutzer
    if benutzer is not None:
        sperren.freigeben(angebot_id, benutzer.id)
    from fastapi.responses import JSONResponse
    return JSONResponse({"ok": True})


@router.post("/{angebot_id}/position/{position_id}/menge")
def menge_aendern(request: Request, angebot_id: int, position_id: int,
                        session: Session = Depends(get_session)):
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    form = anfrage.formular(request)
    position = session.get(AngebotsPosition, position_id)
    if position and position.angebot_id == angebot_id:
        from app.konfigurator import zahl_parsen
        zahl = zahl_parsen(form.get("menge"))
        if zahl is not None and zahl > 0:
            def aktion():
                session.get(AngebotsPosition, position_id).menge = zahl
            _speichern(session, aktion)
    return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)


@router.post("/{angebot_id}/position/{position_id}/aendern")
def position_aendern(request: Request, angebot_id: int, position_id: int,
                           session: Session = Depends(get_session)):
    """Zeilen-Editor (v5, Phase 34): Anzeigenummer, Menge, Einzelpreis
    (Original bleibt erhalten), Positionsrabatt (% oder €), bauseits."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    from urllib.parse import quote_plus

    from app.konfigurator import zahl_parsen
    form = anfrage.formular(request)
    position = session.get(AngebotsPosition, position_id)
    if position is None or position.angebot_id != angebot_id:
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    fehler = []

    def aktion():
        # v22: bei Wiederholung nach „database is locked“ frisch laden
        fehler.clear()
        position = session.get(AngebotsPosition, position_id)
        position.anzeige_nr = (form.get("anzeige_nr") or "").strip()[:10]
        menge = zahl_parsen(form.get("menge"))
        if menge is not None and menge > 0:
            position.menge = menge
        elif (form.get("menge") or "").strip():
            fehler.append("Menge ungültig")
        preis_text = (form.get("e_preis") or "").strip()
        if preis_text:
            preis = preis_parsen(preis_text)
            if preis is None or preis < 0:
                fehler.append("Einzelpreis ungültig")
            elif preis != position.e_preis_cent:
                if position.original_preis_cent is None:
                    position.original_preis_cent = position.e_preis_cent
                position.e_preis_cent = preis
        # Positionsrabatt: leer = kein Rabatt
        rabatt_wert = (form.get("rabatt_wert") or "").strip()
        position.rabatt_cent = None
        position.rabatt_prozent = None
        if rabatt_wert:
            if form.get("rabatt_typ") == "prozent":
                prozent = zahl_parsen(rabatt_wert)
                if prozent is None or not 0 < prozent <= 100:
                    fehler.append("Rabatt-Prozent ungültig (0–100)")
                else:
                    position.rabatt_prozent = prozent
            else:
                cent = preis_parsen(rabatt_wert)
                if cent is None or cent <= 0:
                    fehler.append("Rabatt-Betrag ungültig")
                else:
                    position.rabatt_cent = cent
        position.bauseits = form.get("bauseits") == "on"
        position.ep_flag = form.get("ep_flag") == "on"   # v6: EP-Kästchen je Position
        # v10 (Phase 61): „Alternativ – in anderem Angebot enthalten“ – zählt wie
        # EP nicht mit; die Verknüpfung nennt das Geschwister-Angebot (oder Text)
        position.alternativ = form.get("alternativ") == "on"
        if position.alternativ:
            position.alternativ_zu = (form.get("alternativ_zu") or "").strip()[:200]
        else:
            position.alternativ_zu = ""

    _speichern(session, aktion)
    ziel = f"/angebote/{angebot_id}"
    if fehler:
        ziel += "?meldung=" + quote_plus("Position teilweise nicht übernommen: " + ", ".join(fehler))
    return RedirectResponse(ziel, status_code=303)


@router.post("/{angebot_id}/sortierung")
def sortierung(request: Request, angebot_id: int,
                     session: Session = Depends(get_session)):
    """Drag & Drop (v5): Reihenfolge aller Positions-IDs kommagetrennt."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    from urllib.parse import quote_plus
    form = anfrage.formular(request)
    # v22: robustes Parsen (int() nach isdigit() warf bei Unicode-Ziffern)
    ids = [z for z in (_ganzzahl(t) for t in (form.get("reihenfolge") or "").split(",")
                       if t.strip()) if z is not None]
    positionen = {p.id: p for p in session.query(AngebotsPosition)
                  .filter(AngebotsPosition.angebot_id == angebot_id)}
    if set(ids) != set(positionen) or len(ids) != len(set(ids)):
        # v22: vorher still ignoriert – jetzt Rückmeldung (Positionen wurden
        # zwischenzeitlich geändert/gelöscht, z. B. zweiter Tab)
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "Reihenfolge nicht übernommen – die Positionen haben sich zwischenzeitlich "
            "geändert, bitte erneut sortieren."), status_code=303)
    bewegt_id = _ganzzahl(form.get("bewegt_id"))
    ziel_block = _ganzzahl(form.get("ziel_block"))
    ziel_gruppe = form.get("ziel_gruppe") or ""

    def aktion():
        aktuell = {p.id: p for p in session.query(AngebotsPosition)
                   .filter(AngebotsPosition.angebot_id == angebot_id)}
        for index, pid in enumerate(ids, 1):
            if pid in aktuell:
                aktuell[pid].sort = index
        # v11 (AN-C-261127): Die verschobene Position übernimmt Block und
        # Gruppe ihres Ziel-Blocks – sonst zerreißt sie die Gruppenbildung
        # der Anzeige und die Blocküberschrift rutscht unter den Artikel.
        if bewegt_id in aktuell:
            bewegt = aktuell[bewegt_id]
            if ziel_block is not None:
                bewegt.block_nr = ziel_block
            bewegt.gruppe = ziel_gruppe

    _speichern(session, aktion)
    return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)


@router.post("/{angebot_id}/gruppe")
def gruppe_umbenennen(request: Request, angebot_id: int,
                            session: Session = Depends(get_session)):
    """v22 (PLAN_V15 Phase 103): Gruppen-Überschrift nur in diesem Angebot
    ändern. Der Text steht auf jeder Position des Blocks – alle Positionen mit
    (block_nr, bisheriger Text) bekommen den neuen Text; leer entfernt die
    Überschrift. Editor, PDF und AD-Ansicht gruppieren weiter nach dem Text,
    der Angebotsaufbau (Logik-Blätter) bleibt unberührt."""
    from urllib.parse import quote_plus
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    form = anfrage.formular(request)
    block_text = (form.get("block_nr") or "").strip()
    if not block_text.lstrip("-").isdigit():
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    alt = form.get("alt") or ""
    neu = (form.get("neu") or "").strip()[:300]
    # Gruppe ohne Namen: leerer Text oder (Altbestand) NULL
    alt_filter = (or_(AngebotsPosition.gruppe == "", AngebotsPosition.gruppe.is_(None))
                  if alt == "" else AngebotsPosition.gruppe == alt)
    (session.query(AngebotsPosition)
     .filter(AngebotsPosition.angebot_id == angebot_id,
             AngebotsPosition.block_nr == int(block_text), alt_filter)
     .update({"gruppe": neu}, synchronize_session=False))
    session.commit()
    meldung = "Überschrift gespeichert" if neu else "Überschrift entfernt"
    return RedirectResponse(
        f"/angebote/{angebot_id}?meldung=" + quote_plus(meldung), status_code=303)


@router.post("/{angebot_id}/neu-nummerieren")
def neu_nummerieren(request: Request, angebot_id: int,
                          session: Session = Depends(get_session)):
    """Eigene Nummern verwerfen → wieder fortlaufend 001, 002, … (v5)."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    def aktion():
        for p in session.query(AngebotsPosition).filter(AngebotsPosition.angebot_id == angebot_id):
            p.anzeige_nr = ""
    _speichern(session, aktion)
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=Neu+durchnummeriert", status_code=303)


@router.post("/{angebot_id}/position/{position_id}/entfernen")
def position_entfernen(request: Request, angebot_id: int, position_id: int,
                             session: Session = Depends(get_session)):
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    position = session.get(AngebotsPosition, position_id)
    if position and position.angebot_id == angebot_id:
        def aktion():
            aktuell = session.get(AngebotsPosition, position_id)
            if aktuell is not None:
                session.delete(aktuell)
        _speichern(session, aktion)
    return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)


@router.post("/{angebot_id}/position-neu")
def position_neu(request: Request, angebot_id: int,
                       session: Session = Depends(get_session)):
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = anfrage.formular(request)
    max_sort = max((p.sort for p in angebot.positionen), default=0)
    letzte_gruppe = angebot.positionen[-1].gruppe if angebot.positionen else ""
    letzter_block = angebot.positionen[-1].block_nr if angebot.positionen else 0

    # Autocomplete-Feld (Phase 24): "#<id> · <Pos> · <Titel> …" oder Alt-Feld artikel_id
    artikel_id = form.get("artikel_id") or ""
    suche = (form.get("artikel_suche") or "").strip()
    if not artikel_id and suche:
        import re as _re
        m = _re.match(r"#(\d+)\b", suche)
        if m:
            artikel_id = m.group(1)
        else:
            # Freitext ohne Auswahl aus der Liste: nach Pos-Nr./Artikelnummer suchen
            treffer = (session.query(Artikel)
                       .filter(Artikel.aktiv.is_(True))
                       .filter(or_(Artikel.pos_nr == suche,
                                   Artikel.artikelnummer == suche)).first())
            if treffer is not None:
                artikel_id = str(treffer.id)
            else:
                return RedirectResponse(
                    f"/angebote/{angebot_id}?meldung=Artikel+nicht+gefunden+–+bitte+aus+der+Vorschlagsliste+w%C3%A4hlen",
                    status_code=303)
    if artikel_id:
        artikel = session.get(Artikel, int(artikel_id))
        ziel = f"/angebote/{angebot_id}"
        if artikel is not None:
            position = AngebotsPosition(
                sort=max_sort + 1, block_nr=letzter_block, gruppe=letzte_gruppe,
                pos_nr=artikel.pos_nr, bezeichnung=artikel.bezeichnung,
                beschreibung=artikel.beschreibung, menge=artikel.menge_standard,
                einheit=artikel.einheit, e_preis_cent=artikel.e_preis_cent,
                ep_flag=artikel.ep_flag, ek_cent=artikel.ek_cent,
                guid=artikel.guid)
            # v11 (Phase 66): Z26 „Elektroarbeiten – im PV-Angebot enthalten"
            # kommt automatisch als Alternativ-Position mit Verknüpfung
            if artikel.pos_nr == "Z26":
                position.alternativ = True
                position.alternativ_zu = "PV-Angebot"
            angebot.positionen.append(position)
            session.commit()
            # v22 (Phase 103): direkt zur neuen Zeile springen (Anker = Zeilenform)
            ziel += f"#pos{position.id}"
        return RedirectResponse(ziel, status_code=303)

    # Freitextposition – v11: Bezeichnung optional (PDF zeigt dann nur die
    # Beschreibung), zusätzliches EK-Feld (netto) für den Deckungsbeitrag
    bezeichnung = (form.get("bezeichnung") or "").strip()
    beschreibung = (form.get("beschreibung") or "").strip()
    preis = preis_parsen(form.get("e_preis") or "")
    ek = preis_parsen(form.get("ek_preis") or "")
    from app.konfigurator import zahl_parsen
    menge = zahl_parsen(form.get("menge") or "1") or 1
    if (bezeichnung or beschreibung) and preis is not None:
        position = AngebotsPosition(
            sort=max_sort + 1, block_nr=letzter_block, gruppe=letzte_gruppe,
            bezeichnung=bezeichnung,
            beschreibung=beschreibung,
            menge=menge, einheit=(form.get("einheit") or "").strip(),
            e_preis_cent=preis, ep_flag=form.get("ep_flag") == "on",
            ek_cent=ek or 0)
        angebot.positionen.append(position)
        session.commit()
        # v22 (Phase 103): direkt zur neuen Zeile springen (Anker = Zeilenform)
        return RedirectResponse(f"/angebote/{angebot_id}#pos{position.id}", status_code=303)
    return RedirectResponse(
        f"/angebote/{angebot_id}?meldung=Freitextposition:+Bezeichnung+oder+Beschreibung+und+Preis+erforderlich",
        status_code=303)


@router.post("/{angebot_id}/rabatt")
def rabatt_setzen(request: Request, angebot_id: int,
                        session: Session = Depends(get_session)):
    """Rabatt (Phase 21): Betrag ODER Prozent + optionale Bezeichnung;
    leerer Wert entfernt den Rabatt. Nur Innendienst/Admin (Middleware).
    v33 (PLAN_V20 Phase 172): der Rabatt gilt bei jedem Steuersatz auf den
    Gesamtbetrag nach USt (0 % = Netto) – die Rechnung steckt in Angebot.summen();
    gespeichert wird über _speichern (Rollback + Wiederholung bei „database is
    locked“) wie bei den Positionsrouten."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = anfrage.formular(request)
    wert = (form.get("wert") or "").strip()
    typ = form.get("typ", "betrag")
    bezeichnung = (form.get("bezeichnung") or "").strip()
    cent = prozent = None
    meldung = "Rabatt+gespeichert"
    if wert:
        if typ == "prozent":
            from app.konfigurator import zahl_parsen
            prozent = zahl_parsen(wert)
            # v11: 0 = Rabatt entfernen (wie leeres Feld), keine Fehlermeldung
            if prozent == 0:
                prozent, meldung = None, "Rabatt+entfernt"
            elif prozent is None or not (0 < prozent <= 100):
                return RedirectResponse(
                    f"/angebote/{angebot_id}?meldung=Ung%C3%BCltiger+Prozentwert",
                    status_code=303)
        else:
            cent = preis_parsen(wert)
            if cent == 0:
                cent, meldung = None, "Rabatt+entfernt"
            elif cent is None or cent <= 0:
                return RedirectResponse(
                    f"/angebote/{angebot_id}?meldung=Ung%C3%BCltiger+Rabattbetrag",
                    status_code=303)

    def aktion():
        ziel = session.get(Angebot, angebot_id)   # nach einem Rollback frisch laden
        ziel.rabatt_bezeichnung = bezeichnung
        ziel.rabatt_cent = cent
        ziel.rabatt_prozent = prozent

    _speichern(session, aktion)
    return RedirectResponse(f"/angebote/{angebot_id}?meldung={meldung}", status_code=303)


@router.get("/{angebot_id}/protokoll.pdf")
def protokoll_pdf(angebot_id: int, session: Session = Depends(get_session)):
    """Abfrageprotokoll des Angebots als PDF (Phase 25)."""
    from app import protokoll_pdf as protokoll_modul
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    prot = json.loads(angebot.protokoll_json or "[]")
    if not prot:
        return RedirectResponse(
            f"/angebote/{angebot_id}?meldung=Kein+Abfrageprotokoll+vorhanden+(manuelles+Angebot)",
            status_code=303)
    kunde = session.get(Kunde, angebot.kunde_id)
    from app.models import Benutzer, Erfassung
    erfassung = (session.query(Erfassung)
                 .filter(Erfassung.angebot_id == angebot.id).first())
    vertriebler = session.get(Benutzer, erfassung.benutzer_id) if erfassung else None
    kopf = [
        ("Angebot", angebot.nummer),
        ("Kunde", kunde.anzeige_name if kunde else "?"),
        ("Adresse", f"{kunde.strasse}, {kunde.plz} {kunde.ort}".strip(", ") if kunde else ""),
        ("Vertriebler", vertriebler.name if vertriebler else "–"),
        ("Datum", angebot.datum.strftime("%d.%m.%Y")),
    ]
    gruende = [p["ampel_grund"] for p in prot if p.get("ampel_grund")]
    pfad = protokoll_modul.erzeuge_protokoll_pdf(
        f"protokoll-{angebot.nummer}.pdf",
        f"Angebot {angebot.nummer} · {kunde.anzeige_name if kunde else ''}",
        kopf, prot, sorted(set(gruende)))
    return FileResponse(pfad, media_type="application/pdf",
                        content_disposition_type="inline",
                        filename=f"Protokoll-{angebot.nummer}.pdf")


@router.get("/{angebot_id}/pdf")
def pdf_anzeigen(angebot_id: int, session: Session = Depends(get_session)):
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote?meldung=Angebot+nicht+gefunden", status_code=303)
    if angebot.extern:   # v7: externer TAIFUN-Eintrag hat kein PDF
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=Externer+Eintrag+ohne+PDF",
                                status_code=303)
    from app import pdf_export
    pfad = pdf_export.pdf_fuer_angebot(session, angebot)
    return FileResponse(pfad, media_type="application/pdf",
                        content_disposition_type="inline",
                        filename=f"{angebot.nummer}.pdf")


@router.get("/{angebot_id}/lieferschein.pdf")
def lieferschein(angebot_id: int, session: Session = Depends(get_session)):
    """v13 (PLAN_V13 Phase 80): Lieferschein ohne Preise – nur für Tool-
    Angebote im Status „Angenommen“; Dateiname LS-<Angebotsnummer>.pdf."""
    from urllib.parse import quote_plus
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote?meldung=Angebot+nicht+gefunden", status_code=303)
    if angebot.extern or angebot.status != "Angenommen":
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "Lieferschein nur für angenommene Tool-Angebote."), status_code=303)
    from app import anschriften, lieferschein_pdf
    # v30 (PLAN_V18 Phase 149): EP-Folgepositionen aus dem Parameter
    # lieferschein_folgepositionen (Angebotstool-Einstellungen)
    kunde = session.get(Kunde, angebot.kunde_id)
    pfad = lieferschein_pdf.erzeuge_lieferschein(
        angebot, kunde,
        folgepositionen=lieferschein_pdf.folgepositionen_lesen(session),
        # v31 (PLAN_LEAD_V5 Phase 153): Ausführungsort = Objekt des Angebots
        ausfuehrungsort=anschriften.ausfuehrungsort_fuer(session, angebot=angebot, kunde=kunde))
    return FileResponse(pfad, media_type="application/pdf",
                        content_disposition_type="inline",
                        filename=f"LS-{angebot.nummer}.pdf")


# --- v19 (PLAN_V14 Phase 96): BzA-Datenblatt am Angebot -------------------------

def _datenblatt_parameter(request: Request, session: Session, angebot):
    """v30 (PLAN_V18 Phase 148): ohne Ersteller-Auswahl (Abschnitt 6 entfällt);
    ein altes „ersteller“-Query-Feld wird ignoriert."""
    from app import bza_datenblatt
    q = request.query_params
    try:
        we = int(q.get("we") or 0) or None
    except ValueError:
        we = None
    # PLAN_V15 Phase 103: Übersteuerungen „f_<schluessel>“ aus dem Dialog –
    # statuslos, nur für dieses PDF; leer = automatischer Wert
    uebersteuert = {k[2:]: v.strip()[:bza_datenblatt.UEBERSTEUERUNG_MAX]
                    for k, v in q.multi_items() if k.startswith("f_") and v.strip()}
    return we, (q.get("geraet") or "").strip()[:40], uebersteuert


@router.get("/{angebot_id}/bza-datenblatt")
def bza_datenblatt_dialog(request: Request, angebot_id: int,
                                session: Session = Depends(get_session)):
    """Dialog + Vorschau: WE übersteuern, bei TAIFUN-WP das Gerät aus dem
    Blatt „BAFA-Anlagen“ (Pflicht). v30: Nennwärmeleistung als Zahlenfeld
    (Meldung bei ungültiger Eingabe), kein Ersteller mehr."""
    from urllib.parse import quote_plus

    from app import bza_datenblatt
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    if not bza_datenblatt.ist_wp(angebot):
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "BzA-Datenblatt gibt es nur für Wärmepumpen-Angebote."), status_code=303)
    we, geraet, uebersteuert = _datenblatt_parameter(request, session, angebot)
    blatt = bza_datenblatt.erstellen(session, angebot, we_foerdern=we,
                                     geraet_schluessel=geraet,
                                     uebersteuert=uebersteuert)
    # WE-Feld zeigt den automatischen/gewählten Wert – nicht eine f_-Übersteuerung
    we_vorbelegt = str(we) if we else next(
        (f.wert for titel, felder in blatt.abschnitte for f in felder
         if f.schluessel == "we_foerdern" and not f.fehlt
         and f.hinweis != bza_datenblatt.HINWEIS_MANUELL), "")
    meldungen = [m for m in [request.query_params.get("meldung", "")] if m]
    meldungen += [m for m in blatt.eingabefehler if m not in meldungen]
    # v30: Zahlenfeld zeigt die Eingabe (auch eine ungültige) bzw. die Vorbelegung
    nennwaerme_eingabe = (uebersteuert.get(bza_datenblatt.SCHLUESSEL_NENNWAERME)
                          or blatt.nennwaermeleistung_vorbelegung)
    return render(request, "angebote/bza_datenblatt.html", aktiv="/angebote",
                  angebot=angebot, blatt=blatt, we_vorbelegt=we_vorbelegt,
                  anlagen=bza_datenblatt.bafa_liste(session),
                  uebersteuert=uebersteuert,
                  ja_nein=bza_datenblatt.JA_NEIN_SCHLUESSEL,
                  abgeleitet=bza_datenblatt.DIALOG_ABGELEITET,
                  nennwaerme_schluessel=bza_datenblatt.SCHLUESSEL_NENNWAERME,
                  nennwaerme_eingabe=nennwaerme_eingabe,
                  meldung=" · ".join(meldungen))


@router.get("/{angebot_id}/bza-datenblatt.pdf")
def bza_datenblatt_pdf(request: Request, angebot_id: int,
                             session: Session = Depends(get_session)):
    from urllib.parse import quote_plus

    from fastapi.responses import Response

    from app import bza_datenblatt
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or not bza_datenblatt.ist_wp(angebot):
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    we, geraet, uebersteuert = _datenblatt_parameter(request, session, angebot)
    blatt = bza_datenblatt.erstellen(session, angebot, we_foerdern=we,
                                     geraet_schluessel=geraet,
                                     uebersteuert=uebersteuert)
    if blatt.geraet_auswahl_noetig or blatt.eingabefehler:
        # Phase 103: eingetippte Werte (we/f_…) über die Umleitung erhalten;
        # v30: ungültige Nennwärmeleistung → zurück in den Dialog mit Meldung
        meldung = (" · ".join(blatt.eingabefehler) if blatt.eingabefehler else
                   "TAIFUN-Angebot: bitte das Gerät aus der BAFA-Liste wählen (Pflicht).")
        ziel = f"/angebote/{angebot_id}/bza-datenblatt?meldung=" + quote_plus(meldung)
        if request.url.query:
            ziel += "&" + request.url.query
        return RedirectResponse(ziel, status_code=303)
    name = bza_datenblatt.dateiname(blatt)
    return Response(content=bza_datenblatt.pdf_bytes(blatt), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}"'})


@router.post("/{angebot_id}/kfw-gefoerdert")
def kfw_gefoerdert_setzen(request: Request, angebot_id: int,
                                session: Session = Depends(get_session)):
    """v19 (Phase 96): „KfW-gefördert“ am externen TAIFUN-Eintrag nachträglich
    ändern – steuert die BzA-Aufgabe der Projektierung (bza.ist_gefoerdert)."""
    from urllib.parse import quote_plus
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or not angebot.extern:
        return RedirectResponse("/angebote", status_code=303)
    form = anfrage.formular(request)
    wert = (form.get("kfw_gefoerdert") or "").strip().lower()
    angebot.kfw_gefoerdert = wert if wert in ("ja", "nein") else ""
    # v28 (PLAN_PROJ_V6 Phase 133): Schritte mit foerderung:ja|nein (BzA/BnD) nachziehen
    from app import projektierung as kern
    _projekt, gewerk = kern.projekt_zu_angebot(session, angebot)
    if gewerk is not None:
        kern.foerderung_schritte_nachziehen(session, gewerk, benutzer=request.state.benutzer)
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "KfW-gefördert: " + {"ja": "Ja", "nein": "Nein"}.get(angebot.kfw_gefoerdert,
                                                              "unbekannt")),
        status_code=303)


@router.post("/{angebot_id}/email")
def email_entwurf(request: Request, angebot_id: int,
                        session: Session = Depends(get_session)):
    """Versand vorbereiten (Phase 17): Entwurf per Microsoft Graph im Postfach
    des angemeldeten Innendienst-Nutzers; Fallback bleibt der PDF-Download."""
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote?meldung=Angebot+nicht+gefunden", status_code=303)
    kunde = session.get(Kunde, angebot.kunde_id)
    from pathlib import Path
    from urllib.parse import quote_plus

    from app import anhaenge as anhaenge_modul
    from app import graph_versand, pdf_export

    angebot_vorab = session.get(Angebot, angebot_id)
    if angebot_vorab is not None and angebot_vorab.extern:   # v7: kein Versand
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "Externer TAIFUN-Eintrag – Versand läuft außerhalb des Tools."),
            status_code=303)
    if not graph_versand.konfiguriert():
        return RedirectResponse(
            f"/angebote/{angebot_id}?meldung=" + quote_plus(
                "Microsoft Graph ist noch nicht eingerichtet "
                "(docs/graph-einrichtung.md). Übergangslösung: PDF anzeigen "
                "und manuell versenden."), status_code=303)
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Angebot und Kunde
    # sind geladen; msal kann das Token über das Netz erneuern)
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    # v33 (PLAN_V20 Phase 166): Modus anwendung braucht keine Anmeldung einer Person –
    # verbunden() prüft je Modus (Geheimnis + Verbindungstest bzw. angemeldete Person)
    if not graph_versand.verbunden(session):
        return RedirectResponse(
            "/versand?meldung=" + quote_plus(
                graph_versand.nicht_verbunden_text(session)
                + " Danach den Versand erneut vorbereiten."), status_code=303)

    pdf_pfad = pdf_export.pdf_fuer_angebot(session, angebot)
    # Anhänge (Phase 15/67, v27-Nachtrag 2): volle Logik für ALLE Sparten – das
    # Blatt „Anhänge“ gilt sparten- und profilübergreifend („immer“ vor Sparte/
    # Profil geprüft, KL nimmt denselben Pfad wie WP/PV); fehlende Dateien
    # erscheinen als „fehlt“ in der Versand-Meldung (anhaenge.fuer_angebot sucht
    # tolerant nach Dateinamen im Ordner anlagen/)
    logik, _ = logik_modul.hole_logik(session)
    anhaenge = anhaenge_modul.fuer_angebot(
        logik, angebot, anhaenge_modul.profilname_fuer(session, angebot))
    # Fern-Signatur (Phase 28): bei aktivem Schalter Einmal-Link in die Mail
    signatur_link = ""
    from app.routers.signatur import fern_aktiv, fern_token_ausstellen
    if fern_aktiv(session):
        from app.models import einstellung_holen
        token = fern_token_ausstellen(session, angebot)
        # v27 (PLAN_V17 Phase 129): BASIS_URL aus der .env geht vor (Reverse-Proxy),
        # sonst wie bisher Einstellung bzw. Adresse der Anfrage
        from app import config as konfig
        basis = konfig.BASIS_URL if konfig.BASIS_URL_AUS_ENV else ""
        if not basis:
            basis = einstellung_holen(session, "signatur_fern_basis_url", "").rstrip("/")
        if not basis:
            basis = str(request.base_url).rstrip("/")
        signatur_link = f"{basis}/signatur/extern/{token}"
        session.commit()
    # Vorlage (Phase 30, v27-Nachtrag 2, v34 Phase 180): WP = AD des Vorgangs → Sparten-
    # Vorlage → Standard; PV/KL/WB = Sparten-Vorlage → AD → Standard (mail_vorlagen.
    # vorlage_laden); Platzhalter füllen. Die Quelle („Sparten-Vorlage KL“ …) steht in
    # der Erfolgsmeldung.
    from app import mail_vorlagen
    from app.models import einstellung_holen
    betreff, text, vorlage_quelle = mail_vorlagen.mail_fuer_angebot(
        session, angebot, kunde, request.state.benutzer.name)
    text += graph_versand.signatur_absatz(signatur_link)
    # Signatur des angemeldeten ID-Mitarbeiters (v6): HTML + Inline-Bilder
    from app import signaturen
    signatur_html, inline_bilder = signaturen.fuer_versand(request.state.benutzer.id)
    text += signatur_html
    # Phase 31: Absender angebot@friondo.de, CC = AD des Vorgangs, BCC aus Parametrierung
    absender = einstellung_holen(session, "mail_absender", "angebot@friondo.de")
    bcc = [a.strip() for a in einstellung_holen(session, "mail_bcc", "").split(",") if a.strip()]
    vertriebler = mail_vorlagen.vertriebler_fuer_angebot(session, angebot)
    cc = [vertriebler.email] if vertriebler and vertriebler.email else []
    cc_hinweis = ""
    if vertriebler and not vertriebler.email:
        cc_hinweis = (f" ACHTUNG: {vertriebler.name} hat keine E-Mail-Adresse hinterlegt – "
                      "Entwurf ohne CC (Benutzerverwaltung ergänzen).")
    elif vertriebler is None:
        cc_hinweis = " Hinweis: kein Außendienstler zugeordnet – Entwurf ohne CC."
    # v9: Versandregeln des Angebotsprofils (Enni: CC energieberatung@enni.de;
    # SWD: Empfänger leer – der Innendienst trägt den SWD-Kontakt manuell ein)
    from app import angebotsprofile
    profil = angebotsprofile.profil_fuer_angebot(session, angebot, kunde)
    if profil is not None and profil.versand_cc:
        cc += [a.strip() for a in profil.versand_cc.split(",")
               if a.strip() and a.strip() not in cc]
    empfaenger_leer = bool(profil is not None and profil.empfaenger_leer)
    if empfaenger_leer:
        cc_hinweis += (" PFLICHT: Empfänger ist leer (SWD-Profil) – bitte den "
                       "SWD-Kontakt vor dem Senden in Outlook eintragen!")
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (PDF, Anhänge, Texte,
    # CC/BCC und Absender sind gelesen; Entwurf und Anhänge laufen über mehrere
    # Graph-Aufrufe)
    verbindung_freigeben(session)
    erfolg, meldung, weblink, conversation_id = graph_versand.entwurf_erstellen(
        kunde, angebot, pdf_pfad, betreff, text,
        weitere_anhaenge=[Path(a.pfad) for a in anhaenge if a.vorhanden],
        fehlende_anhaenge=[a.datei for a in anhaenge if not a.vorhanden],
        cc=cc, bcc=bcc, absender=absender, inline_bilder=inline_bilder,
        empfaenger_leer=empfaenger_leer)
    if erfolg:
        meldung += f" ({vorlage_quelle}, Absender {absender})" + cc_hinweis
        # Mail-Verlauf (Phase 27): Konversation der Angebots-Mail merken
        if conversation_id:
            angebot.graph_conversation_id = conversation_id
        # Status-Kette (Phase 31): „Versand vorbereitet“ → Graph-Abgleich → „Versendet“
        if angebot.status == "Entwurf":
            angebot.status = "Versand vorbereitet"
        session.commit()
    ziel = f"/angebote/{angebot_id}?meldung={quote_plus(meldung)}"
    if erfolg:
        ziel += "&versand=1"
        if weblink:
            ziel += f"&weblink={quote_plus(weblink)}"
    return RedirectResponse(ziel, status_code=303)


@router.post("/{angebot_id}/profil")
def profil_umschalten(request: Request, angebot_id: int,
                            session: Session = Depends(get_session)):
    """v9: Angebotsprofil manuell umschalten. Bei Entwürfen werden die
    Positionsregeln des neuen Profils direkt angewendet; sonst ändern sich
    nur Nachtext/Versandregeln (Meldung sagt, was passiert ist)."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    from urllib.parse import quote_plus

    from app import angebotsprofile
    from app.models import Profil
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = anfrage.formular(request)
    profil = session.get(Profil, int(form.get("profil_id") or 0))
    if profil is None:
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    angebot.profil_id = profil.id
    meldungen = [f"Profil auf „{profil.name}“ umgestellt."]
    if angebot.status == "Entwurf":
        meldungen += angebotsprofile.positionsregeln_anwenden(session, angebot, profil)
    else:
        meldungen.append("Positionen unverändert (kein Entwurf) – es gelten "
                         "Nachtext und Versandregeln des neuen Profils.")
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        " ".join(meldungen)), status_code=303)


@router.post("/{angebot_id}/vortext")
def vortext_speichern(request: Request, angebot_id: int,
                            session: Session = Depends(get_session)):
    """v9: Vortext am Angebot überschreiben (leer = Profil-/Standardtext)."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    from urllib.parse import quote_plus
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = anfrage.formular(request)
    angebot.vortext_text = (form.get("vortext_text") or "").strip()
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "Vortext gespeichert" if angebot.vortext_text
        else "Vortext zurück auf den Profil-Standard"), status_code=303)


@router.post("/{angebot_id}/kanal")
def kanal_aendern(request: Request, angebot_id: int,
                        session: Session = Depends(get_session)):
    """v9: Vertriebskanal des Kunden manuell setzen (Vorrang vor dem Sync);
    mit profil_auto=1 wird das Profil anhand des neuen Kanals neu bestimmt."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    from urllib.parse import quote_plus

    from app import angebotsprofile
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    kunde = session.get(Kunde, angebot.kunde_id)
    form = anfrage.formular(request)
    kanal = (form.get("kanal") or "").strip()[:100]
    if kunde is not None:
        kunde.vertriebskanal = kanal
        kunde.kanal_manuell = bool(kanal)
    meldung = f"Vertriebskanal auf „{kanal or '–'}“ gesetzt."
    if form.get("profil_auto") == "1":
        angebot.profil_id = None   # Auto-Auswahl über den neuen Kanal
        profil = angebotsprofile.profil_fuer_angebot(session, angebot, kunde)
        if profil is not None:
            angebot.profil_id = profil.id
            meldung += f" Profil automatisch: „{profil.name}“."
            if angebot.status == "Entwurf":
                aenderungen = angebotsprofile.positionsregeln_anwenden(
                    session, angebot, profil)
                if aenderungen:
                    meldung += " " + " ".join(aenderungen)
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(meldung),
                            status_code=303)


@router.post("/{angebot_id}/verfolgung")
def verfolgung_setzen(request: Request, angebot_id: int,
                            session: Session = Depends(get_session)):
    """Verfolgung (v10, Phase 60): lebt auf VORGANGSEBENE – EINE Hot-Ampel und
    Wiedervorlage je Kundenanfrage; die Notiz geht in den Vorgangs-Chat."""
    from urllib.parse import quote_plus

    from app import vorgaenge as vorgaenge_modul
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = anfrage.formular(request)
    try:
        verantwortlicher_id = int(form.get("wv_verantwortlicher") or 0) or None
    except ValueError:
        verantwortlicher_id = None
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    vorgaenge_modul.verfolgung_setzen(
        session, vorgang, request.state.benutzer,
        form.get("verfolgung_ampel") or "", form.get("wiedervorlage_am") or "",
        notiz=form.get("notiz") or "", verantwortlicher_id=verantwortlicher_id)
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "Verfolgung aktualisiert (gilt für den gesamten Vorgang)"), status_code=303)


@router.post("/{angebot_id}/foerderung")
def foerderung_setzen(request: Request, angebot_id: int,
                            session: Session = Depends(get_session)):
    """Förderung (v8): baustein-basierte Overrides – Grundförderung, Klima-Bonus,
    Einkommensbonus (je %), förderfähige Höchstkosten (€). Leeres Feld =
    automatisch. Speichern setzt einen alten Gesamt-Override (v6) zurück."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    from urllib.parse import quote_plus
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = anfrage.formular(request)

    def prozent_lesen(name):
        roh = (form.get(name) or "").strip()
        if not roh:
            return None, ""
        from app.konfigurator import zahl_parsen
        zahl = zahl_parsen(roh)
        if zahl is None or zahl < 0 or zahl > 100:
            return None, f"Ungültiger Prozentwert bei {name}"
        return zahl, ""

    grund, f1 = prozent_lesen("grund_prozent")
    klima, f2 = prozent_lesen("klima_prozent")
    einkommen, f3 = prozent_lesen("einkommen_prozent")
    fehler = f1 or f2 or f3
    hoechst = None
    roh = (form.get("hoechstkosten") or "").strip()
    if roh:
        hoechst = preis_parsen(roh)
        if hoechst is None or hoechst <= 0:
            fehler = "Ungültige Höchstkosten"
    if fehler:
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(fehler),
                                status_code=303)
    angebot.foerder_grund_prozent = grund
    angebot.foerder_klima_prozent = klima
    angebot.foerder_einkommen_prozent = einkommen
    angebot.foerder_hoechstkosten_cent = hoechst
    angebot.foerderung_manuell_cent = None   # Alt-Override (v6) entfällt
    angebot.foerderung_ausblenden = form.get("ausblenden") == "on"
    # v28 (PLAN_PROJ_V6 Phase 133): Förderung geändert → Schritte mit foerderung:ja|nein nachziehen
    from app import projektierung as kern
    _projekt, gewerk = kern.projekt_zu_angebot(session, angebot)
    if gewerk is not None:
        kern.foerderung_schritte_nachziehen(session, gewerk, benutzer=request.state.benutzer)
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "Förderung aktualisiert"), status_code=303)


@router.post("/{angebot_id}/position/{position_id}/text")
def position_text(request: Request, angebot_id: int, position_id: int,
                        session: Session = Depends(get_session)):
    """Artikeltext je Position editierbar (v6) – nur in diesem Angebot,
    der Artikelstamm bleibt unberührt."""
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    position = session.get(AngebotsPosition, position_id)
    if position and position.angebot_id == angebot_id:
        form = anfrage.formular(request)
        position.bezeichnung = (form.get("bezeichnung") or "").strip()[:300]
        position.beschreibung = (form.get("beschreibung") or "").strip()
        session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)


@router.post("/{angebot_id}/vertriebler")
def vertriebler_aendern(request: Request, angebot_id: int,
                              session: Session = Depends(get_session)):
    """Vertriebler des Angebots ändern (v5-Nachtrag): schreibt in die
    verknüpfte Erfassung (eine Quelle je Vorgang); nur bei manuellen
    Angeboten ohne Erfassung ins Feld angebot.vertriebler_id."""
    from urllib.parse import quote_plus

    from app.models import Benutzer, Erfassung
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    form = anfrage.formular(request)
    wert = form.get("benutzer_id") or ""
    if not (wert.isdigit() and session.get(Benutzer, int(wert)) is not None):
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    erfassung = (session.query(Erfassung)
                 .filter(Erfassung.angebot_id == angebot.id).first())
    if erfassung is not None:
        erfassung.benutzer_id = int(wert)
        angebot.vertriebler_id = None
    else:
        angebot.vertriebler_id = int(wert)
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "Vertriebler geändert – CC und Mail-Vorlage folgen der neuen Zuordnung."),
        status_code=303)


@router.get("/{angebot_id}/mails")
def mailverlauf(request: Request, angebot_id: int,
                      session: Session = Depends(get_session)):
    """Mail-Verlauf zur Angebots-Konversation (Phase 27, nur lesend)."""
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote?meldung=Angebot+nicht+gefunden", status_code=303)
    from app import mail_sync
    from app.models import AngebotsMail
    mails = (session.query(AngebotsMail)
             .filter(AngebotsMail.angebot_id == angebot.id)
             .order_by(AngebotsMail.empfangen_am.desc().nullslast()).all())
    kunde = session.get(Kunde, angebot.kunde_id)
    return render(request, "angebote/mails.html", aktiv="/angebote",
                  angebot=angebot, kunde=kunde, mails=mails,
                  sync_status=mail_sync.status)


@router.post("/{angebot_id}/status")
def status_aendern(request: Request, angebot_id: int,
                         session: Session = Depends(get_session)):
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    form = anfrage.formular(request)
    angebot = session.get(Angebot, angebot_id)
    neuer_status = form.get("status", "")
    if angebot is not None and neuer_status in ANGEBOT_STATUS:
        from app.models import EXTERN_STATUS, angebot_status_setzen
        if angebot.extern and neuer_status not in EXTERN_STATUS:
            return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
        # v8: Ablehnung nur mit Grund (Pflichtdialog, Tool + extern)
        if neuer_status == "Abgelehnt":
            from urllib.parse import quote_plus

            from app.models import AblehnungsGrund, AngebotsNotiz
            grund = (form.get("ablehnungsgrund") or "").strip()
            bekannt = {g.name: g for g in session.query(AblehnungsGrund)
                       .filter(AblehnungsGrund.aktiv.is_(True))}
            if grund not in bekannt:
                return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
                    "Bitte den Grund der Ablehnung angeben (Dialog beim Status „Abgelehnt“)."),
                    status_code=303)
            grund_text = (form.get("ablehnungsgrund_text") or "").strip()[:500]
            # v32 (PLAN_V19 Phase 163, Vorschlag N 4.1): Pflicht-Freitext bei Gründen mit
            # freitext_pflicht („Sonstiges“) serverseitig prüfen – 400 bei JSON, sonst Meldung
            if getattr(bekannt[grund], "freitext_pflicht", False) and not grund_text:
                meldung = f"Beim Grund „{grund}“ ist die Ergänzung (Freitext) Pflicht."
                if "application/json" in (request.headers.get("accept") or ""):
                    from fastapi.responses import JSONResponse
                    return JSONResponse({"ok": False, "meldung": meldung}, status_code=400)
                return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(meldung),
                                        status_code=303)
            angebot.ablehnungsgrund = grund
            angebot.ablehnungsgrund_text = grund_text
            benutzer = request.state.benutzer
            session.add(AngebotsNotiz(
                angebot_id=angebot.id,
                benutzer_name=benutzer.name if benutzer else "?",
                text="Abgelehnt – Grund: " + grund
                     + (f" ({angebot.ablehnungsgrund_text})" if angebot.ablehnungsgrund_text else "")))
        alter_status = angebot.status
        angebot_status_setzen(angebot, neuer_status)
        # v11 (AN-C-261083): manueller Fallback „Als versendet markieren" –
        # mit Protokolleintrag, damit nachvollziehbar bleibt, dass die
        # automatische Versand-Erkennung nicht griff
        if neuer_status == "Versendet" and alter_status == "Versand vorbereitet":
            from app.models import AngebotsNotiz
            benutzer = request.state.benutzer
            session.add(AngebotsNotiz(
                angebot_id=angebot.id,
                benutzer_name=benutzer.name if benutzer else "?",
                text="Manuell als versendet markiert (automatische "
                     "Versand-Erkennung griff nicht)."))
        # v32 (PLAN_V19 Phase 162): Versand-Hook – automatische Wiedervorlage am Vorgang
        # (auch „Als versendet markieren“ und ein externer Eintrag zurück auf
        # „Versendet (extern)“); reine DB-Arbeit vor dem Commit
        if (neuer_status in ("Versendet", "Versendet (extern)")
                and alter_status not in ("Versendet", "Versendet (extern)")):
            from app import nachfassen
            nachfassen.nach_versand(session, angebot, benutzer=request.state.benutzer)
        # v32 (PLAN_V19 Phase 163, Vertrag N 4.1): Verfolgungsstufe des Vorgangs nach JEDEM
        # Statuswechsel nachziehen (Angenommen → angenommen, Abgelehnt → abgelehnt, zurück auf
        # Versendet → versendet; Regel verfolgung.ableiten – idempotent)
        _verfolgung_nachziehen(session, angebot, request.state.benutzer)
        # v7: „Individuell“ archiviert NICHT mehr automatisch – individuelle
        # Fälle laufen über die Erfassungs-Statuskette (TAIFUN-Warteschlange)
        # verknüpfte Erfassung automatisch pflegen (Phase 14); eine als
        # „Erledigt (extern)“ abgeschlossene Erfassung bleibt unangetastet
        from app.models import Erfassung
        erfassung = (session.query(Erfassung)
                     .filter(Erfassung.angebot_id == angebot.id).first())
        if erfassung is not None and erfassung.status != "Erledigt (extern)":
            if neuer_status in ("Versendet", "Angenommen", "Abgelehnt"):
                erfassung.status = "Erledigt"
            elif erfassung.status == "Neu":
                erfassung.status = "In Bearbeitung"
        session.commit()
        # monday-Rückspielung (Phase 32): Trigger ist der Wechsel auf „Versendet“
        if neuer_status == "Versendet" and alter_status != "Versendet":
            from app import monday_rueckspielung
            monday_rueckspielung.bei_versand(session, angebot)
        # v10 (Phase 62): Ablehnung senkt die Vorgangssumme → Wert neu schreiben
        elif (neuer_status == "Abgelehnt"
              and alter_status in ("Versendet", "Versendet (extern)", "Angenommen")):
            from app import monday_rueckspielung
            monday_rueckspielung.wert_aktualisieren(session, angebot, "Ablehnung")
        # v11 (Phase 66): neue Version „Angenommen" → Gewerk nachziehen
        if neuer_status == "Angenommen":
            from app import projektierung as projektierung_modul
            projektierung_modul.version_nachziehen(session, angebot)
            session.commit()
        # v12 (Phase 73): abgeleitete Lead-Phase am Vorgang aktualisieren
        from app import leadmanagement
        leadmanagement.phase_neu_berechnen(session, angebot.vorgang_id)
        session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)


@router.post("/{angebot_id}/taifun-pdf")
def taifun_pdf_hochladen(request: Request, angebot_id: int,
                               session: Session = Depends(get_session)):
    """v10 (Phase 62): PDF-Upload am externen TAIFUN-Eintrag (ersetzbar, mit
    Zeitstempel) – Übergangslösung, damit Kombi-Mails alle Angebote enthalten;
    Ziel bleibt die Erstellung im Tool.
    v34 (PLAN_V21 Phase 180, Agent V): Drop-Zone statt Datei-Knopf (Akte, Angebotsliste,
    TAIFUN-Seite – taifun_pdf.js): ein vorhandenes PDF wird nur mit Sicherheitsabfrage
    ersetzt (Feld `bestaetigt=1`, sonst Meldung/409), Häkchen `uebernehmen_nummer` /
    `uebernehmen_datum` / `uebernehmen_endbetrag` übernehmen die serverseitig aus dem NEUEN
    PDF gelesenen Werte (app/taifun_pdf.py), Kopie in die Galerie „Allgemein“ (wie v18),
    Antwort als JSON bei Accept application/json, sonst Redirect auf `zurueck` (nur
    Tool-Pfade) bzw. den Eintrag. Upload-Regel: das Formular wird VOR dem ersten
    Datenbankzugriff gelesen (keine Schreibsperre während der Übertragung)."""
    from urllib.parse import quote_plus

    from fastapi.responses import JSONResponse

    from app import taifun_pdf
    form = anfrage.formular(request)
    json_gewuenscht = "application/json" in (request.headers.get("accept") or "")
    zurueck = (form.get("zurueck") or "").strip()
    if not (zurueck.startswith("/") and not zurueck.startswith("//")):
        zurueck = f"/angebote/{angebot_id}"
    zurueck, _, anker = zurueck.partition("#")   # Anker (z. B. #angebot-12) hinter die Meldung
    trenner = "&" if "?" in zurueck else "?"

    def antwort(meldung: str, status_code: int = 303, ok: bool = True):
        if json_gewuenscht:
            return JSONResponse({"ok": ok, "meldung": meldung},
                                status_code=200 if ok else status_code)
        return RedirectResponse(zurueck + trenner + "meldung=" + quote_plus(meldung)
                                + (f"#{anker}" if anker else ""), status_code=303)

    datei = form.get("pdf_datei")
    if datei is None or not getattr(datei, "filename", ""):
        return antwort("Bitte eine PDF-Datei auswählen.", 400, ok=False)
    inhalt = datei.file.read()
    fehler = taifun_pdf.groesse_pruefen(len(inhalt))
    if fehler:
        return antwort(fehler, 413, ok=False)
    if not taifun_pdf.ist_pdf(inhalt):
        return antwort(taifun_pdf.MELDUNG_KEIN_PDF, 415, ok=False)
    # Entscheidung Orchestrator (15.10.2026, v33-Upload-Regel): die pypdf-Textextraktion eines bis zu
    # 20 MB großen PDFs läuft VOR dem ersten Datenbankzugriff – die Schreibsitzung (BEGIN IMMEDIATE)
    # hält die SQLite-Schreibsperre damit nie während des Parsens; die Schreibtransaktion bekommt
    # die fertigen Felder (`felder=`) und schreibt nur noch Datei, Galerie-Kopie und Spalten
    felder = taifun_pdf.felder_erkennen(taifun_pdf.text_lesen(inhalt))
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or not angebot.extern:
        return RedirectResponse("/angebote", status_code=303)
    bestaetigt = "1" in [str(w) for w in form.getlist("bestaetigt")]
    if angebot.extern_pdf_pfad and not bestaetigt:
        return antwort("Am Eintrag liegt bereits ein PDF – das Ersetzen bitte bestätigen "
                       "(Sicherheitsabfrage).", 409, ok=False)
    uebernehmen = {feld for feld in taifun_pdf.UEBERNEHMBAR
                   if str(form.get(f"uebernehmen_{feld}") or "") in ("1", "on", "true")}
    ergebnis: dict = {}
    benutzer = request.state.benutzer

    def aktion():
        ergebnis.update(taifun_pdf.eintrag_pdf_speichern(session, angebot, inhalt, benutzer,
                                                        uebernehmen, felder=felder))

    _speichern(session, aktion)
    return antwort(taifun_pdf.meldung_fuer(ergebnis))


@router.get("/{angebot_id}/taifun-pdf")
def taifun_pdf_anzeigen(angebot_id: int, session: Session = Depends(get_session)):
    """Hinterlegtes TAIFUN-PDF anzeigen."""
    from pathlib import Path as _Path
    angebot = session.get(Angebot, angebot_id)
    if (angebot is None or not angebot.extern or not angebot.extern_pdf_pfad
            or not _Path(angebot.extern_pdf_pfad).exists()):
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    return FileResponse(angebot.extern_pdf_pfad, media_type="application/pdf",
                        content_disposition_type="inline",
                        filename=f"{angebot.taifun_nummer or angebot.nummer}.pdf")


@router.post("/{angebot_id}/taifun-nummer")
def taifun_nummer_setzen(request: Request, angebot_id: int,
                               session: Session = Depends(get_session)):
    """v7: TAIFUN-Angebotsnummer am externen Eintrag nachtragen."""
    from urllib.parse import quote_plus
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or not angebot.extern:
        return RedirectResponse("/angebote", status_code=303)
    form = anfrage.formular(request)
    angebot.taifun_nummer = (form.get("taifun_nummer") or "").strip()[:30]
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "TAIFUN-Nummer gespeichert" if angebot.taifun_nummer else "TAIFUN-Nummer entfernt"),
        status_code=303)


@router.post("/{angebot_id}/monday-rueckspielung")
def monday_erneut(request: Request, angebot_id: int,
                        session: Session = Depends(get_session)):
    """„Erneut übertragen“ nach fehlgeschlagener Rückspielung (Phase 32)."""
    from urllib.parse import quote_plus

    from app import monday_rueckspielung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    ok = monday_rueckspielung.uebertragen(session, angebot)
    meldung = ("monday-Rückspielung erfolgreich" if ok and angebot.monday_rueck_status == "ok"
               else ("monday-Rückspielung übersprungen – siehe Protokoll" if ok
                     else "monday-Rückspielung fehlgeschlagen – siehe Protokoll"))
    return RedirectResponse(f"/angebote/{angebot_id}?meldung={quote_plus(meldung)}",
                            status_code=303)


@router.post("/{angebot_id}/loeschen")
def loeschen(request: Request, angebot_id: int,
                   session: Session = Depends(get_session)):
    """Nur Entwürfe löschbar (v5); alles andere wird archiviert."""
    from pathlib import Path
    from urllib.parse import quote_plus

    from app.models import AngebotsMail, Erfassung
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    if angebot.status != "Entwurf":
        # v6: auch versendete/angenommene/abgelehnte löschbar (ID + Admin) –
        # mit Eintrag ins Lösch-Protokoll; die Nummer wird nie wiederverwendet
        from app.models import AngebotsLoeschung
        kunde = session.get(Kunde, angebot.kunde_id)
        benutzer = request.state.benutzer
        session.add(AngebotsLoeschung(
            nummer=angebot.nummer,
            kunde_name=kunde.anzeige_name if kunde else "",
            status_vorher=angebot.status,
            endbetrag_cent=angebot.summen()["endbetrag"],
            benutzer_name=benutzer.name if benutzer else "?"))
    nummer = angebot.nummer
    # Verknüpfte Erfassung lösen: sie ist wieder offen für ein neues Angebot
    for erfassung in session.query(Erfassung).filter(Erfassung.angebot_id == angebot.id):
        erfassung.angebot_id = None
        if erfassung.status == "In Bearbeitung":
            erfassung.status = "Neu"
    session.query(AngebotsMail).filter(AngebotsMail.angebot_id == angebot.id).delete()
    war_in_summe = angebot.status in ("Versendet", "Versendet (extern)", "Angenommen")
    session.delete(angebot)   # Positionen per Cascade
    session.commit()
    if war_in_summe:
        # v10 (Phase 62): Vorgangssumme ohne das gelöschte Angebot schreiben
        from app import monday_rueckspielung
        monday_rueckspielung.wert_aktualisieren(session, angebot, "Löschung",
                                                protokoll=False)
    from app import config
    Path(config.ANGEBOTE_PDF_ORDNER / f"{nummer}.pdf").unlink(missing_ok=True)
    benutzer = request.state.benutzer
    if benutzer is not None:
        sperren.freigeben(angebot_id, benutzer.id)
    return RedirectResponse("/angebote?meldung=" + quote_plus(f"Entwurf {nummer} gelöscht"),
                            status_code=303)


@router.post("/{angebot_id}/archivieren")
def archivieren(request: Request, angebot_id: int,
                      session: Session = Depends(get_session)):
    """Versendete/angenommene/abgelehnte Angebote ins Archiv bzw. zurück (v5)."""
    from urllib.parse import quote_plus
    angebot = session.get(Angebot, angebot_id)
    if angebot is None:
        return RedirectResponse("/angebote", status_code=303)
    if angebot.status == "Entwurf" and not angebot.archiviert:
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "Entwürfe werden nicht archiviert, sondern gelöscht."), status_code=303)
    angebot.archiviert = not angebot.archiviert
    session.commit()
    if angebot.archiviert:
        return RedirectResponse("/angebote?meldung=" + quote_plus(
            f"{angebot.nummer} archiviert – über den Filter „Archiv“ weiterhin erreichbar."),
            status_code=303)
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        "Aus dem Archiv zurückgeholt."), status_code=303)


@router.post("/{angebot_id}/ueberarbeiten")
def ueberarbeiten(request: Request, angebot_id: int,
                        session: Session = Depends(get_session)):
    """v9: neue Version (.2/.3 …) eines versendeten/angenommenen Angebots als
    Entwurf; das Original wird „Überholt“ (zählt nicht mehr in Statistik,
    Summenzeile und 90-Tage-Lauf). Verfolgung, Mail-Konversation und die
    Erfassungs-/Lead-Verknüpfung laufen an der neuen Version weiter."""
    from urllib.parse import quote_plus

    from app.models import Erfassung
    original = session.get(Angebot, angebot_id)
    if original is None:
        return RedirectResponse("/angebote", status_code=303)
    if original.extern or original.status not in ("Versendet", "Angenommen"):
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "Überarbeiten geht nur bei versendeten/angenommenen Tool-Angeboten."),
            status_code=303)
    # v30 (PLAN_V18 Phase 149): mit der v22-Wiederholung _speichern – Fehler
    # F-20261002-073115-9c9e: die Route starb ohne Wiederholung an „database is
    # locked“ (Schreibsperre eines Hintergrundlaufs, reproduziert auf der DB-Kopie).
    # v33 (Phase 172): version_erzeugen committet nicht selbst (nur flush) – die
    # Version entsteht vollständig in dieser einen Transaktion.
    ergebnis: dict = {}

    def aktion():
        original_neu = session.get(Angebot, angebot_id)
        version = angebot_aufbau.version_erzeugen(session, original_neu)
        # v30 (Phase 150): Zahlungsbedingung wandert in die neue Version
        _zahlungsbedingung_uebernehmen(version, original_neu)
        ergebnis["version"] = version
        ergebnis["original_nummer"] = original_neu.nummer

    _speichern(session, aktion)
    version = ergebnis["version"]
    neue_nummer = version.nummer
    # v10 (Phase 62): monday-Deal-Wert folgt der Vorgangssumme (Original
    # zählt als „Überholt" nicht mehr mit)
    from app import monday_rueckspielung
    monday_rueckspielung.wert_aktualisieren(session, version, "neue Version")
    return RedirectResponse(f"/angebote/{version.id}?meldung=" + quote_plus(
        f"Version {neue_nummer} als Entwurf erstellt – {ergebnis['original_nummer']} ist "
        "jetzt „Überholt“."), status_code=303)


def _zahlungsbedingung_uebernehmen(ziel: Angebot, quelle: Angebot) -> None:
    """v30 (PLAN_V18 Phase 150): Überarbeiten, Duplizieren und Kopieren nehmen
    Schlüssel und Freitext der Zahlungsbedingung mit."""
    from app import zahlungsbedingungen
    zahlungsbedingungen.uebernehmen(ziel, quelle)


def _positionen_kopieren(ziel: Angebot, quelle: Angebot) -> None:
    """Positions-Snapshots 1:1 mit allen Kennzeichen (Bugfix 30.09.2026: vorher
    gingen beim Duplizieren bauseits, Positionsrabatt, Sonderpreis, manuell
    geänderter Preis und Alternativ verloren – der Endbetrag stieg).
    v34 (PLAN_V21 Phase 180): die 0,00-€-Auslegungszeile eines Alt-Angebots wird nicht
    mitkopiert – ihr Text landet in ziel.auslegung_text (falls leer)."""
    for p in quelle.positionen:
        if angebot_aufbau.ist_auslegungs_position(p):
            if not (ziel.auslegung_text or "").strip():
                ziel.auslegung_text = (p.beschreibung or "").strip()
            continue
        ziel.positionen.append(AngebotsPosition(
            sort=p.sort, block_nr=p.block_nr, gruppe=p.gruppe, pos_nr=p.pos_nr,
            bezeichnung=p.bezeichnung, beschreibung=p.beschreibung, menge=p.menge,
            einheit=p.einheit, e_preis_cent=p.e_preis_cent, ep_flag=p.ep_flag,
            ek_cent=p.ek_cent, guid=p.guid,
            anzeige_nr=p.anzeige_nr, original_preis_cent=p.original_preis_cent,
            rabatt_prozent=p.rabatt_prozent, rabatt_cent=p.rabatt_cent,
            bauseits=p.bauseits, sonderpreis=p.sonderpreis,
            alternativ=p.alternativ, alternativ_zu=p.alternativ_zu))


@router.post("/{angebot_id}/duplizieren")
def duplizieren(angebot_id: int, session: Session = Depends(get_session)):
    """Duplikat beim selben Kunden (neue Nummer, Entwurf). v30 (PLAN_V18 Phase
    149): die Schreibschritte laufen über _speichern (Rollback + eine
    Wiederholung bei „database is locked“) – Ursache des Fehlers
    F-20261002-073115-9c9e nach „Überarbeiten → Version .2 → Duplizieren“:
    angebot_anlegen() committet das neue Angebot ohne Wiederholung und starb,
    während ein Hintergrundlauf die SQLite-Schreibsperre hielt (Beleg:
    Reproduktion mit gehaltener Sperre, tests/test_v30_duplizieren.py).
    v33 (PLAN_V20 Phase 172, v30-Nachtrag 22): angebot_anlegen(commit=False) –
    Anlage und Kopie der Positionen in EINER Transaktion, kein eigener Commit
    innerhalb der Wiederholung (kein halb angelegtes Angebot bei Rollback)."""
    original = session.get(Angebot, angebot_id)
    if original is None:
        return RedirectResponse("/angebote", status_code=303)
    if original.extern:   # v7: externe TAIFUN-Einträge werden nicht dupliziert
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=Externer+Eintrag+nicht+duplizierbar",
                                status_code=303)
    ergebnis: dict = {}

    def aktion():
        # nach einem Rollback ist das Original abgelaufen → frisch laden
        quelle = session.get(Angebot, angebot_id)
        kopie = angebot_aufbau.angebot_anlegen(
            session, quelle.kunde_id, sparte=quelle.konfigurator_typ or "WP",
            commit=False)
        kopie.protokoll_json = quelle.protokoll_json
        kopie.kfw_json = quelle.kfw_json
        kopie.ust_satz = quelle.ust_satz   # v13-PV
        kopie.pv_json = quelle.pv_json
        kopie.kl_json = quelle.kl_json     # v24 (fehlte beim Duplizieren)
        kopie.wb_json = quelle.wb_json     # v34 (PLAN_V21 Phase 179)
        kopie.auslegung_text = quelle.auslegung_text   # v34 (PLAN_V21 Phase 180)
        kopie.wirtschaftlichkeit_ausblenden = quelle.wirtschaftlichkeit_ausblenden   # v22
        kopie.objekt_id = quelle.objekt_id   # v31 (PLAN_LEAD_V5 Phase 153): gleiches Objekt
        _zahlungsbedingung_uebernehmen(kopie, quelle)   # v30 (Phase 150)
        _positionen_kopieren(kopie, quelle)
        ergebnis["kopie"] = kopie

    _speichern(session, aktion)
    kopie = ergebnis["kopie"]
    return RedirectResponse(f"/angebote/{kopie.id}?meldung=Angebot+dupliziert", status_code=303)


@router.post("/{angebot_id}/kopieren")
def fuer_anderen_kunden_kopieren(request: Request, angebot_id: int,
                                       session: Session = Depends(get_session)):
    """v11 (Phase 66): Angebot für einen ANDEREN Kunden kopieren – neuer
    Vorgang beim Zielkunden (bzw. dessen Sammel-Vorgang, v10-Regel: ein
    Sammel-Vorgang je Kunde), neue Nummer als Entwurf, alle Positionen,
    Texte und Einstellungen; Anrede/Adressen kommen vom Zielkunden. Die
    KfW-Eingaben werden übernommen und als „Förderdaten prüfen (kopiert)“
    gekennzeichnet (kopie_von in der Detailansicht)."""
    import re as _re
    from urllib.parse import quote_plus
    original = session.get(Angebot, angebot_id)
    if original is None:
        return RedirectResponse("/angebote", status_code=303)
    if original.extern:
        return RedirectResponse(
            f"/angebote/{angebot_id}?meldung=Externer+Eintrag+nicht+kopierbar",
            status_code=303)
    form = anfrage.formular(request)
    # Zielkunde: Auswahl aus dem Bestand ("#<id> · Name …") oder Neuanlage
    ziel_id = None
    suche = (form.get("kunde_suche") or "").strip()
    m = _re.match(r"#(\d+)\b", suche)
    if m:
        ziel_id = int(m.group(1))
        if session.get(Kunde, ziel_id) is None:
            ziel_id = None
    neu_kunde = None
    if ziel_id is None:
        nachname = (form.get("neu_nachname") or "").strip()
        firma = (form.get("neu_firma") or "").strip()
        if not (nachname or firma):
            return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
                "Kopieren: bitte einen Kunden aus der Liste wählen oder "
                "Nachname/Firma für die Neuanlage angeben."), status_code=303)
        neu_kunde = dict(anrede=(form.get("neu_anrede") or "").strip(),
                         firma=firma,
                         vorname=(form.get("neu_vorname") or "").strip(),
                         nachname=nachname,
                         strasse=(form.get("neu_strasse") or "").strip(),
                         plz=(form.get("neu_plz") or "").strip(),
                         ort=(form.get("neu_ort") or "").strip(),
                         email=(form.get("neu_email") or "").strip(),
                         telefon=(form.get("neu_telefon") or "").strip())
    elif ziel_id == original.kunde_id:
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "Kopieren: bitte einen ANDEREN Kunden wählen – für denselben "
            "Kunden gibt es „Duplizieren“."), status_code=303)

    # v30 (PLAN_V18 Phase 149): Neuanlage des Kunden, Kopie, Vorgang und Notiz in
    # EINER Transaktion über _speichern (Wiederholung bei „database is locked“);
    # v33 (Phase 172): angebot_anlegen(commit=False) committet nicht mehr mittendrin
    benutzer = request.state.benutzer
    ergebnis: dict = {}

    def aktion():
        quelle = session.get(Angebot, angebot_id)
        if neu_kunde is not None:
            ziel = Kunde(**neu_kunde)
            session.add(ziel)
            session.flush()
            kunde_id = ziel.id
        else:
            kunde_id = ziel_id
        kopie = angebot_aufbau.angebot_anlegen(
            session, kunde_id, sparte=quelle.konfigurator_typ or "WP", commit=False)
        kopie.protokoll_json = quelle.protokoll_json
        kopie.kfw_json = quelle.kfw_json
        kopie.vermerke_json = quelle.vermerke_json
        kopie.konfigurator_typ = quelle.konfigurator_typ
        kopie.ust_satz = quelle.ust_satz   # v13-PV
        kopie.pv_json = quelle.pv_json
        kopie.kl_json = quelle.kl_json     # v24
        kopie.wb_json = quelle.wb_json     # v34 (PLAN_V21 Phase 179)
        kopie.auslegung_text = quelle.auslegung_text   # v34 (PLAN_V21 Phase 180)
        kopie.profil_id = quelle.profil_id
        kopie.vortext_text = quelle.vortext_text
        kopie.rabatt_cent = quelle.rabatt_cent
        kopie.rabatt_prozent = quelle.rabatt_prozent
        kopie.rabatt_bezeichnung = quelle.rabatt_bezeichnung
        kopie.foerderung_manuell_cent = quelle.foerderung_manuell_cent
        kopie.foerderung_ausblenden = quelle.foerderung_ausblenden
        kopie.wirtschaftlichkeit_ausblenden = quelle.wirtschaftlichkeit_ausblenden   # v22
        kopie.foerder_grund_prozent = quelle.foerder_grund_prozent
        kopie.foerder_klima_prozent = quelle.foerder_klima_prozent
        kopie.foerder_einkommen_prozent = quelle.foerder_einkommen_prozent
        kopie.foerder_hoechstkosten_cent = quelle.foerder_hoechstkosten_cent
        kopie.kopie_von = quelle.nummer
        _zahlungsbedingung_uebernehmen(kopie, quelle)   # v30 (Phase 150)
        # bewusst NICHT kopiert: rechnung_*/liefer_anschrift (gehören zum alten
        # Kunden), Vertriebler, Versand-/monday-Zustand
        kopie.positionen.clear()   # Profil-Positionsregeln liefen bereits im Original
        _positionen_kopieren(kopie, quelle)
        from app import vorgaenge as vorgaenge_modul
        vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, kopie)
        vorgaenge_modul.notiz_anlegen(
            session, vorgang.id, benutzer,
            f"Angebot {kopie.nummer} als Kopie von {quelle.nummer} angelegt – "
            "Förderdaten prüfen (kopiert).", herkunft="Kopie")
        ergebnis["kopie"] = kopie
        ergebnis["original_nummer"] = quelle.nummer

    _speichern(session, aktion)
    kopie = ergebnis["kopie"]
    return RedirectResponse(f"/angebote/{kopie.id}?meldung=" + quote_plus(
        f"Kopie von {ergebnis['original_nummer']} angelegt – Förderdaten prüfen."),
        status_code=303)


# --- v30 (PLAN_V18 Phase 150): Zahlungsbedingung je Angebot ----------------------

@router.post("/{angebot_id}/zahlungsbedingung")
def zahlungsbedingung_setzen(request: Request, angebot_id: int,
                             session: Session = Depends(get_session)):
    """Auswahl im Editor (Kopfkarte): Schlüssel eines aktiven Eintrags der
    Tabelle zahlungsbedingungen (Standard-Eintrag → leer gespeichert = Standard)
    oder „freitext“ mit Textfeld. Nur im Entwurf, nur Innendienst/Admin (der
    Außendienst erreicht den Editor nicht). Überarbeiten/Duplizieren/Kopieren
    übernehmen beide Felder; das PDF druckt den gewählten Text im Nachtext."""
    from urllib.parse import quote_plus

    from app import zahlungsbedingungen
    if (umleitung := _sperr_umleitung(request, angebot_id)) is not None:
        return umleitung
    benutzer = request.state.benutzer
    if benutzer is None or benutzer.basisrolle not in ("admin", "innendienst"):
        return RedirectResponse(f"/angebote/{angebot_id}", status_code=303)
    angebot = session.get(Angebot, angebot_id)
    if angebot is None or angebot.extern:
        return RedirectResponse("/angebote", status_code=303)
    if angebot.status != "Entwurf":
        return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
            "Die Zahlungsbedingung ist nur im Entwurf änderbar – bei versendeten "
            "Angeboten über „Überarbeiten“ (neue Version)."), status_code=303)
    form = anfrage.formular(request)
    key = (form.get("key") or "").strip()[:50]
    text = (form.get("text") or "").strip()[:zahlungsbedingungen.TEXT_MAX]
    if key == zahlungsbedingungen.FREITEXT:
        if not text:
            return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
                "Zahlungsbedingung: bitte den abweichenden Text eingeben."), status_code=303)
        angebot.zahlungsbedingung_key = zahlungsbedingungen.FREITEXT
        angebot.zahlungsbedingung_text = text
        name = zahlungsbedingungen.FREITEXT_NAME
    else:
        eintrag = zahlungsbedingungen.nach_schluessel(session, key) if key else None
        if key and (eintrag is None or not eintrag.aktiv):
            return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
                "Zahlungsbedingung: unbekannter oder deaktivierter Eintrag."), status_code=303)
        standard = zahlungsbedingungen.standard(session)
        # Standard-Eintrag → leer speichern (leer = Standard, folgt später einem
        # geänderten Standard); jeder andere Eintrag mit seinem Schlüssel
        if eintrag is None or (standard is not None and eintrag.id == standard.id):
            angebot.zahlungsbedingung_key = ""
        else:
            angebot.zahlungsbedingung_key = eintrag.schluessel
        angebot.zahlungsbedingung_text = ""
        name = zahlungsbedingungen.fuer_angebot(session, angebot)[0]
    session.commit()
    return RedirectResponse(f"/angebote/{angebot_id}?meldung=" + quote_plus(
        f"Zahlungsbedingung: {name}"), status_code=303)
