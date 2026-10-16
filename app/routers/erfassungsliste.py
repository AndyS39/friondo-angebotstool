# Erfassungsliste Innendienst (Phase 14): Ampel, Status, Filter/Suche,
# Detailansicht mit Korrekturmöglichkeit, Angebot erzeugen / manuelles Angebot.

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import angebot_aufbau
from app import erfassung_korrektur as korrektur_modul   # v38 (PLAN_V23 Phase 202/204)
from app import konfigurator as engine
from app import logik as logik_modul
from app.db import get_session
from app.models import (ERFASSUNG_STATUS, Angebot, Benutzer, Erfassung, Kunde)
from app.templating import render
from app import anfrage   # v27: Formular/JSON in def-Routen
from app import rollen as rollen_modul   # v33: Basisrolle/Rollen-Varianten
from app import lead_boards   # v33 (PLAN_V20 Phase 174): Spalten je Nutzer, gemerkte Sortierung
from app import sparten as sparten_modul

router = APIRouter(prefix="/erfassungen")


def _sortwert(e: Erfassung, key: str, kunden: dict, benutzer: dict, angebote: dict,
              objekt_zeilen: dict | None = None):
    """v33 (Phase 174): Sortierwert je Spalte der Erfassungsliste bzw. TAIFUN-Warteschlange
    (None = leer, steht immer am Ende – lead_boards.zeilen_sortieren).
    v38 (Phase 204): Spalte „Objekt“ (Objektbezeichnung · Adresse)."""
    kunde = kunden.get(e.kunde_id)
    if key == "lead":
        return lead_boards.sort_text(kunde.anzeige_name if kunde else None)
    if key == "objekt":
        oz = (objekt_zeilen or {}).get(e.id)
        return lead_boards.sort_text(oz["text"] if oz and oz.get("text") else None)
    if key in ("datum", "erfassung"):
        return e.abgesendet_am
    if key == "vertriebler":
        b = benutzer.get(e.benutzer_id)
        return lead_boards.sort_text(b.name if b else None)
    if key == "ampel":
        return 1 if e.ampel == "orange" else 0
    if key == "status":
        return lead_boards.sort_text(e.status)
    if key == "angebot":
        a = angebote.get(e.angebot_id) if e.angebot_id else None
        if a is None:
            return None
        return lead_boards.sort_text((a.taifun_nummer or a.nummer) if a.extern else a.nummer)
    if key == "sparte":
        return lead_boards.sort_text(e.sparte or "WP")
    if key == "typ":
        return lead_boards.sort_text(e.typ)
    if key == "kanal":
        return lead_boards.sort_text(kunde.vertriebskanal if kunde else None)
    if key == "ort":
        return lead_boards.sort_text(f"{kunde.plz or ''} {kunde.ort or ''}" if kunde else None)
    if key == "telefon":
        return lead_boards.sort_text(kunde.telefon if kunde else None)
    return None


def _kontext(session: Session, erfassungen):
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_([e.kunde_id for e in erfassungen] or [0]))}
    benutzer = {b.id: b for b in session.query(Benutzer)}
    angebote = {a.id: a for a in session.query(Angebot)
                .filter(Angebot.id.in_([e.angebot_id for e in erfassungen
                                        if e.angebot_id] or [0]))}
    return kunden, benutzer, angebote


@router.get("")
def liste(request: Request, q: str = "", status: str = "", ampel: str = "",
                interesse: str = "", vertriebler_id: int = 0, sparte: str = "",
                session: Session = Depends(get_session)):
    # v38 (PLAN_V23 Phase 202): Entwürfe (nicht abgesendete Bögen) stehen im Reiter „Entwürfe“ und in
    # „Alle“ mit Badge „Entwurf · Frage 12 von 31“ (Warnfarbe ab 30 Tagen) [ANNAHME: „Alle“ zeigt
    # sie mit]; die übrigen Reiter/Kacheln bleiben wie bisher ohne Entwürfe
    abfrage = session.query(Erfassung)
    if status == "entwuerfe":
        abfrage = abfrage.filter(Erfassung.status == "Entwurf")
    elif status:
        abfrage = abfrage.filter(Erfassung.status != "Entwurf")
    if sparte:   # Sparten-Filter (v8)
        abfrage = abfrage.filter(Erfassung.sparte == sparte)
    # Archiv (v6): Standardansicht ohne archivierte, Filter „Archiv“ nur diese;
    # v7: Tabs Offen · Individuell – zu prüfen · In TAIFUN zu schreiben ·
    # Erledigt · Archiv (Sammelwerte offen/erledigt/individuell-offen)
    if status == "archiv":
        abfrage = abfrage.filter(Erfassung.archiviert.is_(True))
    else:
        abfrage = abfrage.filter(Erfassung.archiviert.is_(False))
        if status == "offen":   # Statistik-Kachel der Startseite (Phase 19)
            abfrage = abfrage.filter(Erfassung.status.in_(["Neu", "In Bearbeitung"]))
        elif status == "erledigt":
            abfrage = abfrage.filter(Erfassung.status.in_(["Erledigt", "Erledigt (extern)"]))
        elif status == "individuell-offen":   # Startseiten-Kachel (v7)
            abfrage = abfrage.filter(Erfassung.status.in_(
                ["Individuell – zu prüfen", "In TAIFUN zu schreiben"]))
        elif status == "entwuerfe":           # v38: Reiter „Entwürfe“ (Filter steht oben)
            pass
        elif status:
            abfrage = abfrage.filter(Erfassung.status == status)
    if ampel:
        abfrage = abfrage.filter(Erfassung.ampel == ampel)
    erfassungen = abfrage.order_by(Erfassung.abgesendet_am.desc()).all()
    kunden, benutzer, angebote = _kontext(session, erfassungen)
    # v38 (PLAN_V23 Phase 204): Objektzeile je Erfassung (eine Abfrage je Liste) – Spalte „Objekt“,
    # Zeile unter dem Kundennamen (< 600 px), Suche findet die Objektbezeichnung
    objekt_map = korrektur_modul.objekt_zeilen(session, erfassungen, kunden)
    if q:
        suchwort = q.lower()
        erfassungen = [e for e in erfassungen
                       if (e.kunde_id in kunden
                           and suchwort in kunden[e.kunde_id].anzeige_name.lower())
                       or (e.benutzer_id in benutzer
                           and suchwort in benutzer[e.benutzer_id].name.lower())
                       or (e.id in objekt_map and suchwort in objekt_map[e.id]["text"].lower())]
    if interesse:   # Filter nach Interesse des Kunden (Phase 33)
        erfassungen = [e for e in erfassungen
                       if e.kunde_id in kunden and interesse in kunden[e.kunde_id].interessen]
    if vertriebler_id:   # Filter nach Vertriebler (v6)
        erfassungen = [e for e in erfassungen if e.benutzer_id == vertriebler_id]
    # Bemerkungs-Symbol (Phase 24): O08 (Objekt) / A12 (alte Anlage) gefüllt?
    bemerkungen = {}
    fachhinweis_ids = {}   # v9: Warnsymbol bei fachlichen Hinweisen
    for e in erfassungen:
        antworten = json.loads(e.antworten_json or "{}")
        texte = [t for t in (antworten.get("O08"), antworten.get("A12"))
                 if t and str(t).strip()]
        if texte:
            bemerkungen[e.id] = " · ".join(str(t) for t in texte)
        hinweise = engine.fachliche_hinweise(antworten)
        if hinweise:
            fachhinweis_ids[e.id] = " · ".join(hinweise)
    vertriebler_werte = sorted({e.benutzer_id for e in erfassungen if e.benutzer_id}
                               | ({vertriebler_id} if vertriebler_id else set()),
                               key=lambda i: benutzer[i].name if i in benutzer else "")
    # v33 (PLAN_V20 Phase 174): Lead-Board-Layout – Board-Key je Sicht (der Reiter „In TAIFUN
    # zu schreiben“ und die Startseiten-Kachel individuell-offen sind die TAIFUN-Warteschlange
    # mit fester erster Spalte „Erfassung“), Spalten je Nutzer (Katalog nach Basisrolle) und
    # die gemerkte Spaltensortierung vor dem Rendern (ohne gemerkte Sortierung bleibt die
    # bisherige Reihenfolge: zuletzt abgesendet zuerst)
    board = ("taifun_warteschlange" if status in ("In TAIFUN zu schreiben", "individuell-offen")
             else "erfassungen")
    benutzer_obj = request.state.benutzer
    spalten = lead_boards.spalten_fuer(session, benutzer_obj, board)
    sortierung = lead_boards.sortierung_fuer(session, benutzer_obj, board)
    lead_boards.zeilen_sortieren(erfassungen, sortierung,
                                 wert=lambda e, key: _sortwert(e, key, kunden, benutzer, angebote,
                                                               objekt_map))
    return render(request, "erfassungen/liste.html", aktiv="/erfassungen",
                  erfassungen=erfassungen, kunden=kunden, benutzer_map=benutzer,
                  objekt_zeilen=objekt_map,                                        # v38 Phase 204
                  entwurf_badges=korrektur_modul.entwurf_badges(session, erfassungen),   # v38 Phase 202
                  korrektur_badge=korrektur_modul.badge_text,
                  angebote=angebote, q=q, status=status, ampel=ampel,
                  interesse=interesse, vertriebler_id=vertriebler_id, sparte=sparte,
                  vertriebler_werte=vertriebler_werte,
                  bemerkungen=bemerkungen, fachhinweis_ids=fachhinweis_ids,
                  status_liste=ERFASSUNG_STATUS,
                  board=board, spalten=spalten, sortierung=sortierung,
                  ctx={"board": board, "sortierung": sortierung},
                  spalten_fest=lead_boards.spalten_fest(board),
                  sparten_liste=sparten_modul.SPARTEN,
                  meldung=request.query_params.get("meldung", ""))


@router.get("/{erfassung_id}")
def detail(request: Request, erfassung_id: int,
                 session: Session = Depends(get_session)):
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    from app.logik import logik_fuer_sparte
    logik, _ = logik_modul.hole_logik(session)
    logik = logik_fuer_sparte(logik, erfassung.sparte or "WP") or logik   # v8
    antworten = json.loads(erfassung.antworten_json or "{}")
    prot = engine.protokoll(logik, antworten)
    kunde = session.get(Kunde, erfassung.kunde_id)
    vertriebler = session.get(Benutzer, erfassung.benutzer_id)
    angebot = session.get(Angebot, erfassung.angebot_id) if erfassung.angebot_id else None
    seiten = logik.seiten
    aussendienst = (session.query(Benutzer)
                    .filter(rollen_modul.filter_basis("aussendienst"), Benutzer.aktiv.is_(True))
                    .order_by(Benutzer.name).all())
    from datetime import date
    fachhinweise = engine.fachliche_hinweise(antworten)   # v9
    # v38 (PLAN_V23 Phase 202/204): Korrektur-Kontext (Knopf/Sperre/Badge/Angebots-Hinweis),
    # Entwurf-Badge „Frage x von y“, Objektzeile
    kctx = korrektur_modul.kontext(session, request.state.benutzer, erfassung)
    entwurf_badge = (korrektur_modul.entwurf_badge(logik, erfassung, antworten)
                     if erfassung.status == korrektur_modul.STATUS_ENTWURF else None)
    return render(request, "erfassungen/detail.html", aktiv="/erfassungen",
                  fachhinweise=fachhinweise, benutzer=request.state.benutzer,
                  erfassung=erfassung, kunde=kunde, vertriebler=vertriebler,
                  aussendienst=aussendienst,
                  protokoll=prot, angebot=angebot, seiten=seiten,
                  gruende=erfassung.gruende_text.splitlines(),
                  status_liste=ERFASSUNG_STATUS,
                  heute=date.today().strftime("%Y-%m-%d"),
                  kctx=kctx, entwurf_badge=entwurf_badge,
                  objekt=korrektur_modul.objekt_zeile(session, erfassung, kunde),
                  meldung=request.query_params.get("meldung", ""))


@router.get("/{erfassung_id}/protokoll.pdf")
def protokoll_pdf(erfassung_id: int, session: Session = Depends(get_session)):
    """Abfrageprotokoll als PDF (Phase 25)."""
    from fastapi.responses import FileResponse

    from app import protokoll_pdf as protokoll_modul
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    from app.logik import logik_fuer_sparte
    logik, _ = logik_modul.hole_logik(session)
    logik = logik_fuer_sparte(logik, erfassung.sparte or "WP") or logik   # v8
    antworten = json.loads(erfassung.antworten_json or "{}")
    prot = engine.protokoll(logik, antworten)
    kunde = session.get(Kunde, erfassung.kunde_id)
    vertriebler = session.get(Benutzer, erfassung.benutzer_id)
    kopf = [
        ("Sparte", erfassung.sparte or "WP"),
        ("Kunde", kunde.anzeige_name if kunde else "?"),
        ("Adresse", f"{kunde.strasse}, {kunde.plz} {kunde.ort}".strip(", ") if kunde else ""),
        ("Vertriebler", vertriebler.name if vertriebler else "?"),
        ("Erfasst am", erfassung.abgesendet_am.strftime("%d.%m.%Y %H:%M")
         if erfassung.abgesendet_am else "Entwurf"),
        ("Status", erfassung.status),
        ("Erfassungsart", "Freitext" if erfassung.typ == "freitext" else "Katalog"),
    ]
    pfad = protokoll_modul.erzeuge_protokoll_pdf(
        f"protokoll-erfassung-{erfassung.id}.pdf",
        f"Erfassung {erfassung.id} · {kunde.anzeige_name if kunde else ''}",
        kopf, prot, [g for g in erfassung.gruende_text.splitlines() if g],
        freitext=erfassung.freitext if erfassung.typ == "freitext" else "")
    return FileResponse(pfad, media_type="application/pdf",
                        content_disposition_type="inline",
                        filename=f"Protokoll-Erfassung-{erfassung.id}.pdf")


@router.post("/{erfassung_id}/status")
def status_aendern(request: Request, erfassung_id: int,
                         session: Session = Depends(get_session)):
    form = anfrage.formular(request)
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is not None and form.get("status") in ERFASSUNG_STATUS:
        erfassung.status = form.get("status")
        # v8: kein Auto-Archiv mehr – „Erledigt (extern)“ erscheint im
        # Reiter „Erledigt“, archiviert wird nur noch manuell
        session.commit()
    return RedirectResponse(f"/erfassungen/{erfassung_id}", status_code=303)


@router.post("/{erfassung_id}/freitext")
def freitext_aendern(request: Request, erfassung_id: int,
                           session: Session = Depends(get_session)):
    """v9 (Phase 57): Freitext nachträglich editierbar – Innendienst/Admin
    überall, Außendienst nur an eigenen Erfassungen; jede Änderung wird mit
    Name und Zeit protokolliert. Läuft der Vorgang bereits (in Bearbeitung
    oder mit Angebot), erscheint zusätzlich der Hinweis „Freitext geändert“."""
    from urllib.parse import quote_plus
    form = anfrage.formular(request)
    erfassung = session.get(Erfassung, erfassung_id)
    benutzer = request.state.benutzer
    if erfassung is None or erfassung.typ != "freitext":
        return RedirectResponse(f"/erfassungen/{erfassung_id}", status_code=303)
    if benutzer.basisrolle == "aussendienst" and erfassung.benutzer_id != benutzer.id:
        return RedirectResponse(f"/erfassungen/{erfassung_id}?meldung=" + quote_plus(
            "Keine Berechtigung – der Freitext gehört zu einer fremden Erfassung."),
            status_code=303)
    neuer_text = (form.get("freitext") or "").strip()
    if not neuer_text:
        return RedirectResponse(f"/erfassungen/{erfassung_id}?meldung=" + quote_plus(
            "Der Freitext darf nicht leer sein."), status_code=303)
    if neuer_text == (erfassung.freitext or "").strip():
        return RedirectResponse(f"/erfassungen/{erfassung_id}", status_code=303)
    laeuft = erfassung.status != "Neu" or erfassung.angebot_id is not None
    alter_text = erfassung.freitext or ""
    erfassung.freitext = neuer_text
    _kette_protokollieren(erfassung, benutzer,
                          "Freitext geändert"
                          + (" (Vorgang bereits in Bearbeitung/mit Angebot)"
                             if laeuft else ""))
    # v38 (PLAN_V23 Phase 202): derselbe Eintrag wie die Katalog-Korrektur – Änderungsnotiz im
    # Notizen-Chat des Vorgangs + Badge „nachträglich geändert (TT.MM.)“
    korrektur_modul.freitext_aenderung(session, erfassung, benutzer, alter_text, neuer_text)
    session.commit()
    return RedirectResponse(f"/erfassungen/{erfassung_id}?meldung=" + quote_plus(
        "Freitext gespeichert – die Änderung steht im Änderungsprotokoll."),
        status_code=303)


def _kette_protokollieren(erfassung: Erfassung, benutzer, text: str) -> None:
    from datetime import datetime
    zeile = (f"{datetime.now().strftime('%d.%m.%Y %H:%M')} · "
             f"{benutzer.name if benutzer else '?'}: {text}")
    erfassung.aenderungs_protokoll = (
        (erfassung.aenderungs_protokoll + "\n" if erfassung.aenderungs_protokoll else "")
        + zeile)


@router.post("/{erfassung_id}/doch-konfigurierbar")
def doch_konfigurierbar(request: Request, erfassung_id: int,
                              session: Session = Depends(get_session)):
    """v7: „Individuell – zu prüfen“ zurück auf den normalen Tool-Weg –
    die Antworten sind korrigierbar, danach „Angebot erzeugen“ wie gewohnt."""
    from urllib.parse import quote_plus
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    erfassung.status = "Neu"
    _kette_protokollieren(erfassung, request.state.benutzer,
                          "als „Doch konfigurierbar“ eingestuft – normaler Tool-Weg")
    session.commit()
    return RedirectResponse(f"/erfassungen/{erfassung_id}?meldung=" + quote_plus(
        "Zurück auf dem normalen Weg – Antworten prüfen/korrigieren, dann Angebot erzeugen."),
        status_code=303)


@router.post("/{erfassung_id}/extern-erledigt")
def extern_erledigt(request: Request, erfassung_id: int,
                          session: Session = Depends(get_session)):
    """v7: Dialog „Extern erledigt“ – das Angebot wurde in TAIFUN geschrieben.
    Erzeugt einen externen Angebotseintrag (Badge „TAIFUN“, kein PDF/Editor/
    Versand), stößt die monday-Rückspielung an und schließt die Erfassung als
    „Erledigt (extern)“ + Archiv ab.
    v34 (PLAN_V21 Phase 180, Agent V): optionales TAIFUN-Angebots-PDF (`pdf_datei`, Drop-Zone
    des Dialogs; Nummer/Datum/Endbetrag belegt taifun_pdf.js vorher über POST
    /angebote/extern/pdf-lesen vor) – das PDF wird am Eintrag gespeichert (v10-Feld
    extern_pdf_pfad → Kombi-Versand) und als Kopie in die Galerie „Allgemein“ gelegt (wie
    v18). Upload-Regel (v33 Phase 172): Formular VOR dem ersten Datenbankzugriff lesen."""
    from datetime import datetime
    from urllib.parse import quote_plus

    from app import monday_rueckspielung, taifun_pdf
    from app.models import angebot_status_setzen
    from app.routers.artikel import preis_parsen
    form = anfrage.formular(request)
    pdf_inhalt = b""
    pdf_datei = form.get("pdf_datei")
    if pdf_datei is not None and getattr(pdf_datei, "filename", ""):
        pdf_inhalt = pdf_datei.file.read() or b""
        fehler = taifun_pdf.groesse_pruefen(len(pdf_inhalt))
        if fehler or not taifun_pdf.ist_pdf(pdf_inhalt):
            return RedirectResponse(f"/erfassungen/{erfassung_id}?meldung=" + quote_plus(
                fehler or taifun_pdf.MELDUNG_KEIN_PDF), status_code=303)
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    if erfassung.angebot_id:
        return RedirectResponse(f"/erfassungen/{erfassung_id}?meldung=" + quote_plus(
            "Mit dieser Erfassung ist bereits ein Angebot verknüpft."), status_code=303)
    endbetrag = preis_parsen((form.get("endbetrag") or "").strip())
    if endbetrag is None or endbetrag <= 0:
        return RedirectResponse(f"/erfassungen/{erfassung_id}?meldung=" + quote_plus(
            "Bitte einen gültigen Endbetrag (brutto) eingeben."), status_code=303)
    try:
        datum = datetime.strptime((form.get("datum") or "").strip(), "%Y-%m-%d")
    except ValueError:
        return RedirectResponse(f"/erfassungen/{erfassung_id}?meldung=" + quote_plus(
            "Bitte ein Datum wählen."), status_code=303)
    from uuid import uuid4
    angebot = Angebot(nummer=f"EXT-{uuid4().hex[:10]}", kunde_id=erfassung.kunde_id,
                      extern=True,
                      taifun_nummer=(form.get("taifun_nummer") or "").strip()[:30],
                      extern_endbetrag_cent=endbetrag, datum=datum,
                      vertriebler_id=erfassung.benutzer_id,
                      konfigurator_typ=erfassung.konfigurator_typ or "WP",
                      # v19 (Phase 96): KfW-gefördert (ja/nein, sonst unbekannt)
                      kfw_gefoerdert=({"ja": "ja", "nein": "nein"}.get(
                          (form.get("kfw_gefoerdert") or "").strip().lower(), "")))
    session.add(angebot)
    session.flush()
    angebot.nummer = f"EXT-{angebot.id}"   # interne Kennung, nie AN-C-Kreis
    angebot_status_setzen(angebot, "Versendet (extern)")
    angebot.versendet_am = datum           # Zeitstempel = Dialog-Datum
    # v8: Einschätzung (S01/S02) aus dem Katalog als Startwerte der Verfolgung
    antworten_kat = json.loads(erfassung.antworten_json or "{}")
    angebot.verfolgung_ampel = {"heiß": "heiss", "warm": "warm", "kalt": "kalt"}.get(
        str(antworten_kat.get("S01") or ""), "")
    if antworten_kat.get("S02"):
        try:
            angebot.wiedervorlage_am = datetime.strptime(
                str(antworten_kat["S02"]), "%Y-%m-%d")
        except ValueError:
            pass
    erfassung.angebot_id = angebot.id
    from app import vorgaenge as vorgaenge_modul
    vorgaenge_modul.vorgang_fuer_angebot(session, angebot)   # v10: Akte
    # v34 (Phase 180): TAIFUN-PDF am Eintrag + Galerie „Allgemein“ (Sparte der Erfassung)
    pdf_hinweis = ""
    if pdf_inhalt:
        taifun_pdf.pdf_ablegen(angebot, pdf_inhalt)
        taifun_pdf.galerie_ablegen(session, angebot, pdf_inhalt, request.state.benutzer,
                                   sparte=erfassung.sparte or "WP", quelle="extern_erledigt",
                                   bemerkung="TAIFUN-Angebot (Extern erledigt)")
        pdf_hinweis = " PDF am Eintrag und in der Galerie „Allgemein“ abgelegt."
    # v32 (PLAN_V19 Phase 162): „Extern erledigt“ zählt als Versand am Datum des Eintrags
    # [ANNAHME] – automatische Wiedervorlage am Vorgang (reine DB-Arbeit, vor dem Commit)
    from app import nachfassen
    nachfassen.nach_versand(session, angebot, benutzer=request.state.benutzer, versandtag=datum)
    erfassung.status = "Erledigt (extern)"   # v8: Archiv erst manuell
    _kette_protokollieren(erfassung, request.state.benutzer,
                          f"Extern erledigt – TAIFUN-Eintrag über {endbetrag / 100:.2f} €"
                          + (f", Nr. {angebot.taifun_nummer}" if angebot.taifun_nummer
                             else " (Nummer fehlt noch)")
                          + (" – TAIFUN-PDF hinterlegt" if pdf_inhalt else ""))
    session.commit()
    # monday-Rückspielung wie bei Tool-Angeboten (Fehler blockieren nie)
    monday_rueckspielung.bei_versand(session, angebot)
    return RedirectResponse(f"/angebote/{angebot.id}?meldung=" + quote_plus(
        "Externer Angebotseintrag angelegt – Erfassung ist erledigt (extern) und archiviert."
        + pdf_hinweis),
        status_code=303)


@router.post("/{erfassung_id}/erneut-pruefen")
def erneut_pruefen(request: Request, erfassung_id: int,
                         session: Session = Depends(get_session)):
    """v13-PV (Phase 79): Katalog-Erfassung mit der aktuellen Logik neu
    auswerten. Vollständig + grün → normaler Weg („Neu“, Angebot erzeugen);
    orange → „Individuell – zu prüfen“; unvollständig (z. B. PV-Altfälle ohne
    die neuen v13-Fragen) → Hinweis mit Link zum Bogen, Status bleibt."""
    from urllib.parse import quote_plus

    from app.logik import logik_fuer_sparte
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    ziel = f"/erfassungen/{erfassung_id}?meldung="
    if erfassung.angebot_id or erfassung.typ != "katalog":
        return RedirectResponse(ziel + quote_plus(
            "Erneut prüfen ist nur für Katalog-Erfassungen ohne Angebot möglich."),
            status_code=303)
    logik, _ = logik_modul.hole_logik(session)
    slogik = logik_fuer_sparte(logik, erfassung.sparte or "WP")
    # v24: PV (v16) und KL (v24) sind Konfiguratoren, sobald ihre Aktionen geladen sind;
    # v34 (PLAN_V21 Phase 179): WB ebenso (WB-Sicht trägt die Aktionen WB)
    if slogik is None or (erfassung.sparte in ("PV", "KL", "WB")
                          and not (slogik.aktionen or getattr(slogik, "kl_aktionen", None)
                                   or getattr(slogik, "wb_aktionen", None))):
        return RedirectResponse(ziel + quote_plus(
            "Für diese Sparte gibt es keine Konfigurator-Logik."), status_code=303)
    antworten = json.loads(erfassung.antworten_json or "{}")
    if erfassung.sparte == "PV":
        from app import pv_auslegung
        pv_auslegung.wp_ableitung_aktualisieren(session, erfassung, antworten, slogik)
        erfassung.antworten_json = json.dumps(antworten, ensure_ascii=False)
    offen = engine.naechste_pflichtfrage(slogik, antworten)   # v27-Nachtrag: optionale Fragen blockieren nicht
    if offen is not None:
        seite = slogik.seiten.index(offen.seite) if offen.seite in slogik.seiten else 0
        _kette_protokollieren(erfassung, request.state.benutzer,
                              f"Erneut geprüft – Bogen unvollständig ({offen.id})")
        session.commit()
        return RedirectResponse(ziel + quote_plus(
            f"Bogen unvollständig: {offen.id} – {offen.text}. Bitte über "
            f"/erfassung/{erfassung.id}/seite/{seite} ergänzen und erneut prüfen."),
            status_code=303)
    gruende = engine.ampel_gruende(slogik, antworten)
    erfassung.ampel = "orange" if gruende else "gruen"
    erfassung.gruende_text = "\n".join(gruende)
    erfassung.status = "Individuell – zu prüfen" if gruende else "Neu"
    _kette_protokollieren(erfassung, request.state.benutzer,
                          "Erneut geprüft – " + ("individuell: " + "; ".join(gruende)
                                                 if gruende else "konfigurierbar (grün)"))
    session.commit()
    return RedirectResponse(ziel + quote_plus(
        "Erneut geprüft: " + ("weiterhin individuell – " + "; ".join(gruende)
                              if gruende else "grün – Angebot kann erzeugt werden.")),
        status_code=303)


@router.post("/{erfassung_id}/individuell-bestaetigt")
def individuell_bestaetigt(request: Request, erfassung_id: int,
                                 session: Session = Depends(get_session)):
    """v7: Prüfung abgeschlossen – der Fall wandert in die TAIFUN-Warteschlange."""
    from urllib.parse import quote_plus
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    erfassung.status = "In TAIFUN zu schreiben"
    _kette_protokollieren(erfassung, request.state.benutzer,
                          "Individuell bestätigt – in TAIFUN zu schreiben")
    session.commit()
    return RedirectResponse(f"/erfassungen/{erfassung_id}?meldung=" + quote_plus(
        "Individuell bestätigt – der Fall steht jetzt in der Warteschlange „In TAIFUN zu schreiben“."),
        status_code=303)


@router.post("/{erfassung_id}/vertriebler")
def vertriebler_aendern(request: Request, erfassung_id: int,
                              session: Session = Depends(get_session)):
    """Vertriebler des Vorgangs ändern (v5-Nachtrag, nur Innendienst/Admin –
    die Erfassungsliste ist ohnehin Büro-only). Wirkt auf CC und Vorlagenwahl
    beim Versand des verknüpften Angebots."""
    from urllib.parse import quote_plus
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    form = anfrage.formular(request)
    wert = form.get("benutzer_id") or ""
    if wert.isdigit() and session.get(Benutzer, int(wert)) is not None:
        erfassung.benutzer_id = int(wert)
        session.commit()
    return RedirectResponse(f"/erfassungen/{erfassung_id}?meldung=" + quote_plus(
        "Vertriebler geändert"), status_code=303)


@router.post("/{erfassung_id}/archivieren")
def archivieren(erfassung_id: int, session: Session = Depends(get_session)):
    """Erfassung ins Archiv bzw. zurück (v6, Innendienst/Admin)."""
    from urllib.parse import quote_plus
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    erfassung.archiviert = not erfassung.archiviert
    session.commit()
    if erfassung.archiviert:
        return RedirectResponse("/erfassungen?meldung=" + quote_plus(
            f"Erfassung {erfassung_id} archiviert – über den Filter „Archiv“ erreichbar."),
            status_code=303)
    return RedirectResponse(f"/erfassungen/{erfassung_id}?meldung=" + quote_plus(
        "Aus dem Archiv zurückgeholt."), status_code=303)


@router.post("/{erfassung_id}/loeschen")
def loeschen(erfassung_id: int, session: Session = Depends(get_session)):
    """Erfassung löschen (v5, Innendienst/Admin): gesperrt, sobald ein Angebot
    verknüpft ist. Ein verknüpfter Lead wird gelöst und erscheint wieder in
    „Leads VOT“."""
    from urllib.parse import quote_plus

    from app.models import Lead
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    if erfassung.angebot_id:
        return RedirectResponse(
            f"/erfassungen/{erfassung_id}?meldung=" + quote_plus(
                "Löschen nicht möglich – mit dieser Erfassung ist ein Angebot verknüpft."),
            status_code=303)
    for lead in session.query(Lead).filter(Lead.erfassung_id == erfassung.id):
        lead.erfassung_id = None
    session.delete(erfassung)
    session.commit()
    return RedirectResponse("/erfassungen?meldung=" + quote_plus(
        f"Erfassung {erfassung_id} gelöscht"), status_code=303)


@router.get("/{erfassung_id}/angebot-erzeugen")
def angebot_erzeugen(erfassung_id: int, session: Session = Depends(get_session)):
    """Grün: Antworten durch die Logik -> Angebotsentwurf; Erfassung verknüpfen."""
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    if erfassung.status == korrektur_modul.STATUS_ENTWURF:
        # v38: Entwürfe stehen jetzt in der Liste – kein Angebot aus einem nicht abgesendeten Bogen
        from urllib.parse import quote_plus
        return RedirectResponse(f"/erfassungen/{erfassung.id}?meldung=" + quote_plus(
            "Entwurf – die Erfassung ist noch nicht abgesendet. Angebot erst nach dem Absenden."),
            status_code=303)
    logik, bericht = logik_modul.hole_logik(session)
    if not bericht.ok:
        return RedirectResponse("/parametrierung", status_code=303)
    sparte = (erfassung.sparte or "WP").upper()
    # v13-PV: PV-Katalog-Erfassungen erzeugen echte Tool-Angebote; v24: KL ebenso
    # (sobald die KL-Logik geladen ist); v34 (PLAN_V21 Phase 179): WB ebenso (WB-Sicht
    # mit Aktionen WB und importierten WB-Artikeln); GW bleibt reine Erfassung (TAIFUN)
    slogik = logik_modul.logik_fuer_sparte(logik, sparte)
    konfigurator = sparte == "WP" or (
        sparte in ("PV", "KL", "WB") and slogik is not None
        and bool(slogik.aktionen or getattr(slogik, "kl_aktionen", None)
                 or getattr(slogik, "wb_aktionen", None)))
    if not konfigurator:
        from urllib.parse import quote_plus
        return RedirectResponse(f"/erfassungen/{erfassung.id}?meldung=" + quote_plus(
            f"Für die Sparte {sparte} erzeugt das Tool kein Angebot – bitte in TAIFUN "
            "schreiben („Extern erledigt“)."), status_code=303)
    logik = slogik or logik
    antworten = json.loads(erfassung.antworten_json or "{}")
    # v11 (AN-C-261127): Wächter gegen unvollständige Antworten – z. B. wenn
    # nach einer Logik-Aktualisierung neue Fragen gelten (Klasse 15: N07/N08)
    # oder Antworten nachträglich in eine andere Klasse korrigiert wurden.
    # Ohne diesen Check entstand ein Angebot OHNE Außen-/Inneneinheit.
    offen = engine.naechste_pflichtfrage(logik, antworten)   # v27-Nachtrag: optionale Fragen blockieren nicht
    if offen is not None:
        from urllib.parse import quote_plus
        return RedirectResponse("/erfassungen?meldung=" + quote_plus(
            f"Angebot nicht erzeugt: In Erfassung {erfassung.id} fehlen Antworten "
            f"(z. B. {offen.id} – {offen.text}). Bitte die Erfassung öffnen und "
            "vervollständigen."), status_code=303)
    angebot = angebot_aufbau.angebot_anlegen(session, erfassung.kunde_id,
                                             antworten=antworten, logik=logik,
                                             sparte=sparte, erfassung=erfassung)
    erfassung.angebot_id = angebot.id
    from app import vorgaenge as vorgaenge_modul
    vorgaenge_modul.vorgang_fuer_angebot(session, angebot)   # v10: Akte
    if erfassung.status == "Neu":
        erfassung.status = "In Bearbeitung"
    session.commit()
    return RedirectResponse(f"/angebote/{angebot.id}", status_code=303)


@router.get("/{erfassung_id}/manuelles-angebot")
def manuelles_angebot(erfassung_id: int, session: Session = Depends(get_session)):
    """Orange: leerer Editor mit Abfrageprotokoll als Seitenpanel."""
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    if erfassung.status == korrektur_modul.STATUS_ENTWURF:   # v38: kein Angebot aus einem Entwurf
        from urllib.parse import quote_plus
        return RedirectResponse(f"/erfassungen/{erfassung.id}?meldung=" + quote_plus(
            "Entwurf – die Erfassung ist noch nicht abgesendet. Angebot erst nach dem Absenden."),
            status_code=303)
    logik, _ = logik_modul.hole_logik(session)
    sparte = (erfassung.konfigurator_typ or erfassung.sparte or "WP").upper()
    logik = logik_modul.logik_fuer_sparte(logik, sparte) or logik   # v13-PV
    antworten = json.loads(erfassung.antworten_json or "{}")
    angebot = angebot_aufbau.angebot_anlegen(session, erfassung.kunde_id,
                                             antworten=antworten, logik=logik,
                                             nur_protokoll=True, sparte=sparte,
                                             erfassung=erfassung)   # v31: Objekt mitnehmen
    erfassung.angebot_id = angebot.id
    from app import vorgaenge as vorgaenge_modul
    vorgaenge_modul.vorgang_fuer_angebot(session, angebot)   # v10: Akte
    if erfassung.status == "Neu":
        erfassung.status = "In Bearbeitung"
    session.commit()
    return RedirectResponse(f"/angebote/{angebot.id}", status_code=303)
