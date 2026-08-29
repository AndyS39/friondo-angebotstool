# Erfassungsliste Innendienst (Phase 14): Ampel, Status, Filter/Suche,
# Detailansicht mit Korrekturmöglichkeit, Angebot erzeugen / manuelles Angebot.

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import angebot_aufbau
from app import konfigurator as engine
from app import logik as logik_modul
from app.db import get_session
from app.models import (ERFASSUNG_STATUS, Angebot, Benutzer, Erfassung, Kunde)
from app.templating import render

router = APIRouter(prefix="/erfassungen")


def _kontext(session: Session, erfassungen):
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_([e.kunde_id for e in erfassungen] or [0]))}
    benutzer = {b.id: b for b in session.query(Benutzer)}
    angebote = {a.id: a for a in session.query(Angebot)
                .filter(Angebot.id.in_([e.angebot_id for e in erfassungen
                                        if e.angebot_id] or [0]))}
    return kunden, benutzer, angebote


@router.get("")
async def liste(request: Request, q: str = "", status: str = "", ampel: str = "",
                interesse: str = "", vertriebler_id: int = 0, sparte: str = "",
                session: Session = Depends(get_session)):
    abfrage = session.query(Erfassung).filter(Erfassung.status != "Entwurf")
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
        elif status:
            abfrage = abfrage.filter(Erfassung.status == status)
    if ampel:
        abfrage = abfrage.filter(Erfassung.ampel == ampel)
    erfassungen = abfrage.order_by(Erfassung.abgesendet_am.desc()).all()
    kunden, benutzer, angebote = _kontext(session, erfassungen)
    if q:
        suchwort = q.lower()
        erfassungen = [e for e in erfassungen
                       if (e.kunde_id in kunden
                           and suchwort in kunden[e.kunde_id].anzeige_name.lower())
                       or (e.benutzer_id in benutzer
                           and suchwort in benutzer[e.benutzer_id].name.lower())]
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
    return render(request, "erfassungen/liste.html", aktiv="/erfassungen",
                  erfassungen=erfassungen, kunden=kunden, benutzer_map=benutzer,
                  angebote=angebote, q=q, status=status, ampel=ampel,
                  interesse=interesse, vertriebler_id=vertriebler_id, sparte=sparte,
                  vertriebler_werte=vertriebler_werte,
                  bemerkungen=bemerkungen, fachhinweis_ids=fachhinweis_ids,
                  status_liste=ERFASSUNG_STATUS,
                  meldung=request.query_params.get("meldung", ""))


@router.get("/{erfassung_id}")
async def detail(request: Request, erfassung_id: int,
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
                    .filter(Benutzer.rolle == "aussendienst", Benutzer.aktiv.is_(True))
                    .order_by(Benutzer.name).all())
    from datetime import date
    fachhinweise = engine.fachliche_hinweise(antworten)   # v9
    return render(request, "erfassungen/detail.html", aktiv="/erfassungen",
                  fachhinweise=fachhinweise, benutzer=request.state.benutzer,
                  erfassung=erfassung, kunde=kunde, vertriebler=vertriebler,
                  aussendienst=aussendienst,
                  protokoll=prot, angebot=angebot, seiten=seiten,
                  gruende=erfassung.gruende_text.splitlines(),
                  status_liste=ERFASSUNG_STATUS,
                  heute=date.today().strftime("%Y-%m-%d"),
                  meldung=request.query_params.get("meldung", ""))


@router.get("/{erfassung_id}/protokoll.pdf")
async def protokoll_pdf(erfassung_id: int, session: Session = Depends(get_session)):
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
async def status_aendern(request: Request, erfassung_id: int,
                         session: Session = Depends(get_session)):
    form = await request.form()
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is not None and form.get("status") in ERFASSUNG_STATUS:
        erfassung.status = form.get("status")
        # v8: kein Auto-Archiv mehr – „Erledigt (extern)“ erscheint im
        # Reiter „Erledigt“, archiviert wird nur noch manuell
        session.commit()
    return RedirectResponse(f"/erfassungen/{erfassung_id}", status_code=303)


@router.post("/{erfassung_id}/freitext")
async def freitext_aendern(request: Request, erfassung_id: int,
                           session: Session = Depends(get_session)):
    """v9 (Phase 57): Freitext nachträglich editierbar – Innendienst/Admin
    überall, Außendienst nur an eigenen Erfassungen; jede Änderung wird mit
    Name und Zeit protokolliert. Läuft der Vorgang bereits (in Bearbeitung
    oder mit Angebot), erscheint zusätzlich der Hinweis „Freitext geändert“."""
    from urllib.parse import quote_plus
    form = await request.form()
    erfassung = session.get(Erfassung, erfassung_id)
    benutzer = request.state.benutzer
    if erfassung is None or erfassung.typ != "freitext":
        return RedirectResponse(f"/erfassungen/{erfassung_id}", status_code=303)
    if benutzer.rolle == "aussendienst" and erfassung.benutzer_id != benutzer.id:
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
    erfassung.freitext = neuer_text
    _kette_protokollieren(erfassung, benutzer,
                          "Freitext geändert"
                          + (" (Vorgang bereits in Bearbeitung/mit Angebot)"
                             if laeuft else ""))
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
async def doch_konfigurierbar(request: Request, erfassung_id: int,
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
async def extern_erledigt(request: Request, erfassung_id: int,
                          session: Session = Depends(get_session)):
    """v7: Dialog „Extern erledigt“ – das Angebot wurde in TAIFUN geschrieben.
    Erzeugt einen externen Angebotseintrag (Badge „TAIFUN“, kein PDF/Editor/
    Versand), stößt die monday-Rückspielung an und schließt die Erfassung als
    „Erledigt (extern)“ + Archiv ab."""
    from datetime import datetime
    from urllib.parse import quote_plus

    from app import monday_rueckspielung
    from app.models import angebot_status_setzen
    from app.routers.artikel import preis_parsen
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    if erfassung.angebot_id:
        return RedirectResponse(f"/erfassungen/{erfassung_id}?meldung=" + quote_plus(
            "Mit dieser Erfassung ist bereits ein Angebot verknüpft."), status_code=303)
    form = await request.form()
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
                      konfigurator_typ=erfassung.konfigurator_typ or "WP")
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
    erfassung.status = "Erledigt (extern)"   # v8: Archiv erst manuell
    _kette_protokollieren(erfassung, request.state.benutzer,
                          f"Extern erledigt – TAIFUN-Eintrag über {endbetrag / 100:.2f} €"
                          + (f", Nr. {angebot.taifun_nummer}" if angebot.taifun_nummer
                             else " (Nummer fehlt noch)"))
    session.commit()
    # monday-Rückspielung wie bei Tool-Angeboten (Fehler blockieren nie)
    monday_rueckspielung.bei_versand(session, angebot)
    return RedirectResponse(f"/angebote/{angebot.id}?meldung=" + quote_plus(
        "Externer Angebotseintrag angelegt – Erfassung ist erledigt (extern) und archiviert."),
        status_code=303)


@router.post("/{erfassung_id}/individuell-bestaetigt")
async def individuell_bestaetigt(request: Request, erfassung_id: int,
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
async def vertriebler_aendern(request: Request, erfassung_id: int,
                              session: Session = Depends(get_session)):
    """Vertriebler des Vorgangs ändern (v5-Nachtrag, nur Innendienst/Admin –
    die Erfassungsliste ist ohnehin Büro-only). Wirkt auf CC und Vorlagenwahl
    beim Versand des verknüpften Angebots."""
    from urllib.parse import quote_plus
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    form = await request.form()
    wert = form.get("benutzer_id") or ""
    if wert.isdigit() and session.get(Benutzer, int(wert)) is not None:
        erfassung.benutzer_id = int(wert)
        session.commit()
    return RedirectResponse(f"/erfassungen/{erfassung_id}?meldung=" + quote_plus(
        "Vertriebler geändert"), status_code=303)


@router.post("/{erfassung_id}/archivieren")
async def archivieren(erfassung_id: int, session: Session = Depends(get_session)):
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
async def loeschen(erfassung_id: int, session: Session = Depends(get_session)):
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
async def angebot_erzeugen(erfassung_id: int, session: Session = Depends(get_session)):
    """Grün: Antworten durch die Logik -> Angebotsentwurf; Erfassung verknüpfen."""
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    logik, bericht = logik_modul.hole_logik(session)
    if not bericht.ok:
        return RedirectResponse("/parametrierung", status_code=303)
    antworten = json.loads(erfassung.antworten_json or "{}")
    angebot = angebot_aufbau.angebot_anlegen(session, erfassung.kunde_id,
                                             antworten=antworten, logik=logik)
    angebot.konfigurator_typ = erfassung.konfigurator_typ or "WP"   # v5
    erfassung.angebot_id = angebot.id
    if erfassung.status == "Neu":
        erfassung.status = "In Bearbeitung"
    session.commit()
    return RedirectResponse(f"/angebote/{angebot.id}", status_code=303)


@router.get("/{erfassung_id}/manuelles-angebot")
async def manuelles_angebot(erfassung_id: int, session: Session = Depends(get_session)):
    """Orange: leerer Editor mit Abfrageprotokoll als Seitenpanel."""
    erfassung = session.get(Erfassung, erfassung_id)
    if erfassung is None:
        return RedirectResponse("/erfassungen", status_code=303)
    logik, _ = logik_modul.hole_logik(session)
    antworten = json.loads(erfassung.antworten_json or "{}")
    angebot = angebot_aufbau.angebot_anlegen(session, erfassung.kunde_id,
                                             antworten=antworten, logik=logik,
                                             nur_protokoll=True)
    angebot.konfigurator_typ = erfassung.konfigurator_typ or "WP"   # v5
    erfassung.angebot_id = angebot.id
    if erfassung.status == "Neu":
        erfassung.status = "In Bearbeitung"
    session.commit()
    return RedirectResponse(f"/angebote/{angebot.id}", status_code=303)
