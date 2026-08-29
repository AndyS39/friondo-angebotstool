# Mobile Außendienst-Erfassung (Phase 13): eine Seite pro Kategorie, große
# Bedienelemente, Fortschritt, vor/zurück, Pflichtfeld-Prüfung. Der Außendienst
# sieht keine Preise, EKs, Deckungsbeiträge und keinen Angebotsbereich.

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import konfigurator as engine
from app import logik as logik_modul
from app.db import get_session
from app.logik import FREITEXT_TYPEN, logik_fuer_sparte
from app.models import INTERESSE_CODES, Erfassung, Kunde
from app.templating import render

router = APIRouter(prefix="/erfassung")

SPARTEN_NAMEN = {"WP": "Wärmepumpe", "PV": "Photovoltaik",
                 "KL": "Klima", "WB": "Wallbox"}


def _benutzer(request: Request):
    return request.state.benutzer


def _antworten(erfassung: Erfassung) -> dict:
    return json.loads(erfassung.antworten_json or "{}")


def _sparten_logik(session, erfassung: Erfassung):
    """v8: die Logik-Sicht für die Sparte der Erfassung (None = nur Freitext)."""
    logik, bericht = logik_modul.hole_logik(session)
    return logik_fuer_sparte(logik, erfassung.sparte or "WP"), bericht


def _fragen_der_seite(logik, seite: str, antworten: dict | None = None):
    """Fragen einer Katalogseite; Wiederholgruppen (v8, z. B. „je Raum“)
    werden anhand der Zählfrage zu Klonen KR01#1, KR01#2 … expandiert."""
    ergebnis = []
    for f in sorted(logik.fragen.values(), key=lambda f: f.reihenfolge):
        if f.seite != seite:
            continue
        if f.bedingung is not None and f.bedingung.art == "wiederholgruppe":
            ergebnis.extend(engine._wiederhol_klone(f, antworten or {}, logik.fragen))
        else:
            ergebnis.append(f)
    ergebnis.sort(key=lambda f: f.reihenfolge)
    return ergebnis


def _ist_optional(frage) -> bool:
    if frage.typ == "Freitext groß":
        return True
    return "leer" in frage.hinweis.lower()


def _client_regel(frage) -> str:
    """Sichtbarkeitsregel für das Seiten-JavaScript (Folgefragen derselben Seite)."""
    b = frage.bedingung
    if b is None or b.art == "immer":
        return json.dumps({"art": "immer"})
    if b.art == "antwort":
        return json.dumps({"art": "antwort", "frage": b.frage_id, "werte": b.werte},
                          ensure_ascii=False)
    if b.art == "ausgefuellt":
        return json.dumps({"art": "ausgefuellt", "frage": b.frage_id})
    if b.art == "selbstnutzung":
        return json.dumps({"art": "selbstnutzung"})
    if b.art == "klauseln":
        return json.dumps({"art": "klauseln",
                           "klauseln": [[{"frage": fid, "werte": werte}
                                         for fid, werte in klausel]
                                        for klausel in b.klauseln]}, ensure_ascii=False)
    return json.dumps({"art": "immer"})


@router.get("")
async def uebersicht(request: Request, session: Session = Depends(get_session)):
    benutzer = _benutzer(request)
    erfassungen = (session.query(Erfassung)
                   .filter(Erfassung.benutzer_id == benutzer.id)
                   .order_by(Erfassung.angelegt_am.desc()).limit(25).all())
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_([e.kunde_id for e in erfassungen] or [0]))}
    # v7: externe TAIFUN-Einträge haben kein PDF – kein Signieren-Knopf
    from app.models import Angebot
    extern_ids = {a.id for a in session.query(Angebot)
                  .filter(Angebot.id.in_([e.angebot_id for e in erfassungen
                                          if e.angebot_id] or [0]),
                          Angebot.extern.is_(True))}
    return render(request, "erfassung/uebersicht.html", aktiv=None, mobil=True,
                  benutzer=benutzer, erfassungen=erfassungen, kunden=kunden,
                  extern_ids=extern_ids)


@router.get("/neu")
async def neu_formular(request: Request, session: Session = Depends(get_session)):
    kunden = (session.query(Kunde).filter(Kunde.aktiv.is_(True))
              .order_by(Kunde.firma, Kunde.nachname).all())
    return render(request, "erfassung/neu.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), kunden=kunden, fehler="")


@router.post("/neu")
async def neu(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    kunde = None
    if form.get("kunde_id"):
        try:
            kunde = session.get(Kunde, int(form.get("kunde_id")))
        except ValueError:
            kunde = None
    elif (form.get("nachname") or "").strip() or (form.get("firma") or "").strip():
        kunde = Kunde(
            anrede=(form.get("anrede") or "").strip(),
            firma=(form.get("firma") or "").strip(),
            vorname=(form.get("vorname") or "").strip(),
            nachname=(form.get("nachname") or "").strip(),
            strasse=(form.get("strasse") or "").strip(),
            plz=(form.get("plz") or "").strip(),
            ort=(form.get("ort") or "").strip(),
            email=(form.get("email") or "").strip(),
            telefon=(form.get("telefon") or "").strip(),
        )
        session.add(kunde)
        session.flush()
    if kunde is None:
        kunden = (session.query(Kunde).filter(Kunde.aktiv.is_(True))
                  .order_by(Kunde.firma, Kunde.nachname).all())
        return render(request, "erfassung/neu.html", aktiv=None, mobil=True,
                      benutzer=_benutzer(request), kunden=kunden,
                      fehler="Bitte Kunden wählen oder Name/Firma eingeben.")
    session.commit()
    # v8: nach der Kundenwahl zuerst die Sparten-Auswahl
    return RedirectResponse(f"/erfassung/sparten?kunde_id={kunde.id}", status_code=303)


@router.get("/sparten")
async def sparten_auswahl(request: Request, kunde_id: int = 0, lead_id: int = 0,
                          session: Session = Depends(get_session)):
    """v8: Sparten-Auswahl beim Erfassungsstart – Lead-Interessen sind
    vorausgewählt, weitere Sparten zuwählbar; je Sparte entsteht eine
    eigene Erfassung."""
    from app.models import Lead
    lead = session.get(Lead, lead_id) if lead_id else None
    if lead is not None and not kunde_id:
        kunde_id = lead.kunde_id
    kunde = session.get(Kunde, kunde_id) if kunde_id else None
    if kunde is None:
        return RedirectResponse("/erfassung/neu", status_code=303)
    vorausgewaehlt = set(lead.sparten) if lead else {"WP"}
    erfasst: set[str] = set()
    entwuerfe: list[Erfassung] = []
    if lead is not None:
        for e in (session.query(Erfassung)
                  .filter(Erfassung.lead_id == lead.id)):
            if e.status == "Entwurf":
                entwuerfe.append(e)
            else:
                erfasst.add(e.sparte or "WP")
    return render(request, "erfassung/sparten.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), kunde=kunde, lead=lead,
                  sparten=INTERESSE_CODES, sparten_namen=SPARTEN_NAMEN,
                  vorausgewaehlt=vorausgewaehlt - erfasst, erfasst=erfasst,
                  entwuerfe=entwuerfe, fehler="")


@router.post("/sparten-start")
async def sparten_start(request: Request, session: Session = Depends(get_session)):
    """v8: legt je gewählter Sparte eine eigene Erfassung an und öffnet die
    erste (WB startet immer direkt im Freitext)."""
    from app.models import Lead
    form = await request.form()
    kunde = session.get(Kunde, int(form.get("kunde_id") or 0))
    lead = session.get(Lead, int(form.get("lead_id") or 0)) if form.get("lead_id") else None
    if kunde is None:
        return RedirectResponse("/erfassung/neu", status_code=303)
    gewaehlt = [s for s in INTERESSE_CODES if form.get(f"sparte_{s}") == "on"]
    if not gewaehlt:
        return RedirectResponse(
            f"/erfassung/sparten?kunde_id={kunde.id}&lead_id={lead.id if lead else 0}",
            status_code=303)
    neu: list[Erfassung] = []
    # v9: Enni-Profil → der WP-Bogen zeigt nur die HEMS-Frage; P02/P03 werden
    # mit "Nein" vorbelegt (bleiben unsichtbar, Katalog gilt als vollständig)
    from app import angebotsprofile
    kanal = (lead.vertriebskanal if lead else "") or kunde.vertriebskanal
    profil = angebotsprofile.profil_fuer_kanal(session, kanal)
    enni = profil is not None and profil.regel_kennung == "enni"
    for sparte in gewaehlt:
        erfassung = Erfassung(kunde_id=kunde.id, benutzer_id=_benutzer(request).id,
                              sparte=sparte, konfigurator_typ=sparte,
                              lead_id=lead.id if lead else None)
        if enni and sparte == "WP":
            erfassung.antworten_json = json.dumps({"P02": "Nein", "P03": "Nein"},
                                                  ensure_ascii=False)
        session.add(erfassung)
        neu.append(erfassung)
    session.flush()
    if lead is not None and lead.erfassung_id is None:
        lead.erfassung_id = neu[0].id   # Alt-Verknüpfung (erste Erfassung)
    session.commit()
    erste = neu[0]
    if erste.sparte == "WB":   # Wallbox: vorerst immer Freitext
        return RedirectResponse(f"/erfassung/{erste.id}/freitext", status_code=303)
    return RedirectResponse(f"/erfassung/{erste.id}/weiche", status_code=303)


@router.get("/{erfassung_id}/weiche")
async def weiche(request: Request, erfassung_id: int,
                 session: Session = Depends(get_session)):
    """Startweiche (v7): Erfassungsbogen (Katalog) oder Freitext-Erfassung.
    v8: je Sparte – WB (oder Sparten ohne Bogen) startet direkt im Freitext."""
    erfassung = _erfassung_laden(request, erfassung_id, session)
    if erfassung is None:
        return RedirectResponse("/erfassung", status_code=303)
    slogik, _ = _sparten_logik(session, erfassung)
    if slogik is None:   # WB o. Ä.: kein Katalog vorhanden
        return RedirectResponse(f"/erfassung/{erfassung.id}/freitext", status_code=303)
    kunde = session.get(Kunde, erfassung.kunde_id)
    return render(request, "erfassung/weiche.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), erfassung=erfassung, kunde=kunde,
                  sparten_namen=SPARTEN_NAMEN)


@router.get("/{erfassung_id}/freitext")
async def freitext_formular(request: Request, erfassung_id: int,
                            session: Session = Depends(get_session)):
    """Freitext-Erfassung (v7): großes Pflicht-Textfeld; bei Wechsel aus dem
    Katalog bleiben die bereits gegebenen Antworten im Protokoll erhalten."""
    erfassung = _erfassung_laden(request, erfassung_id, session)
    if erfassung is None:
        return RedirectResponse("/erfassung", status_code=303)
    kunde = session.get(Kunde, erfassung.kunde_id)
    hat_antworten = bool(_antworten(erfassung))
    return render(request, "erfassung/freitext.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), erfassung=erfassung, kunde=kunde,
                  hat_antworten=hat_antworten, fehler="")


@router.post("/{erfassung_id}/freitext")
async def freitext_absenden(request: Request, erfassung_id: int,
                            session: Session = Depends(get_session)):
    """Freitext absenden (v7): keine Vorprüfung – Ampel Individuell und
    Status direkt „In TAIFUN zu schreiben“."""
    erfassung = _erfassung_laden(request, erfassung_id, session)
    if erfassung is None:
        return RedirectResponse("/erfassung", status_code=303)
    form = await request.form()
    text = (form.get("freitext") or "").strip()
    if not text:
        kunde = session.get(Kunde, erfassung.kunde_id)
        return render(request, "erfassung/freitext.html", aktiv=None, mobil=True,
                      benutzer=_benutzer(request), erfassung=erfassung, kunde=kunde,
                      hat_antworten=bool(_antworten(erfassung)),
                      fehler="Bitte die Beschreibung ausfüllen.")
    erfassung.typ = "freitext"
    erfassung.freitext = text
    erfassung.ampel = "orange"
    erfassung.gruende_text = "vom Außendienst als individuell erfasst"
    erfassung.status = "In TAIFUN zu schreiben"
    erfassung.abgesendet_am = datetime.now()
    session.commit()
    return render(request, "erfassung/fertig.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), erfassung=erfassung)


def _erfassung_laden(request: Request, erfassung_id: int, session: Session):
    erfassung = session.get(Erfassung, erfassung_id)
    benutzer = _benutzer(request)
    if erfassung is None:
        return None
    if benutzer.rolle == "aussendienst" and erfassung.benutzer_id != benutzer.id:
        return None
    return erfassung


@router.get("/{erfassung_id}/seite/{nr}")
async def seite(request: Request, erfassung_id: int, nr: int,
                session: Session = Depends(get_session)):
    erfassung = _erfassung_laden(request, erfassung_id, session)
    if erfassung is None:
        return RedirectResponse("/erfassung", status_code=303)
    logik, bericht = _sparten_logik(session, erfassung)
    if logik is None:
        return RedirectResponse(f"/erfassung/{erfassung.id}/freitext", status_code=303)
    if not bericht.ok:
        return render(request, "konfigurator/logikfehler.html", aktiv=None,
                      bericht=bericht)
    seiten = logik.seiten
    nr = max(0, min(nr, len(seiten) - 1))
    antworten = _antworten(erfassung)
    kunde = session.get(Kunde, erfassung.kunde_id)
    fragen = _fragen_der_seite(logik, seiten[nr], antworten)
    # v9: Enni-Bogen zeigt nur die HEMS-Frage (P02/P03 sind mit Nein vorbelegt)
    from app import angebotsprofile
    if angebotsprofile.enni_bogen(session, erfassung):
        fragen = [f for f in fragen if f.id not in ("P02", "P03")]
    sichtbar = {f.id: engine.ist_sichtbar(f, antworten, logik.fragen) for f in fragen}
    werte = {}
    for f in fragen:
        wert = antworten.get(f.id)
        if wert is None and f.typ == "Auswahl" or wert is None:
            vor = engine.vorbelegung(f, antworten)
            if vor is not None:
                wert = vor
        werte[f.id] = wert
    return render(request, "erfassung/seite.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), erfassung=erfassung, kunde=kunde,
                  seiten=seiten, nr=nr, fragen=fragen, sichtbar=sichtbar,
                  werte=werte, fehler={}, client_regel=_client_regel,
                  wiederhol_id=engine.ID_WIEDERHOL_ANZAHL)


@router.post("/{erfassung_id}/seite/{nr}")
async def seite_speichern(request: Request, erfassung_id: int, nr: int,
                          session: Session = Depends(get_session)):
    erfassung = _erfassung_laden(request, erfassung_id, session)
    if erfassung is None:
        return RedirectResponse("/erfassung", status_code=303)
    logik, _ = _sparten_logik(session, erfassung)
    if logik is None:
        return RedirectResponse(f"/erfassung/{erfassung.id}/freitext", status_code=303)
    seiten = logik.seiten
    nr = max(0, min(nr, len(seiten) - 1))
    form = await request.form()
    antworten = _antworten(erfassung)
    antworten_vorher = dict(antworten)
    fragen = _fragen_der_seite(logik, seiten[nr], antworten)

    fehler: dict[str, str] = {}
    for frage in fragen:
        if not engine.ist_sichtbar(frage, antworten, logik.fragen):
            antworten.pop(frage.id, None)   # unsichtbar geworden -> Antwort verwerfen
            continue
        wert, problem = _wert_lesen(frage, form, antworten)
        if problem:
            if wert in (None, "", [], {}) and _ist_optional(frage):
                antworten[frage.id] = ""
                continue
            fehler[frage.id] = problem
            continue
        antworten[frage.id] = wert

    richtung = form.get("richtung", "weiter")
    if fehler and richtung == "weiter":
        kunde = session.get(Kunde, erfassung.kunde_id)
        sichtbar = {f.id: engine.ist_sichtbar(f, antworten, logik.fragen) for f in fragen}
        werte = {f.id: antworten.get(f.id) for f in fragen}
        return render(request, "erfassung/seite.html", aktiv=None, mobil=True,
                      benutzer=_benutzer(request), erfassung=erfassung, kunde=kunde,
                      seiten=seiten, nr=nr, fragen=fragen, sichtbar=sichtbar,
                      werte=werte, fehler=fehler, client_regel=_client_regel,
                      wiederhol_id=engine.ID_WIEDERHOL_ANZAHL)

    erfassung.antworten_json = json.dumps(antworten, ensure_ascii=False)
    _korrekturen_protokollieren(erfassung, antworten_vorher, antworten,
                                _benutzer(request), logik)
    if richtung == "freitext":   # v7: Wechsel in die Freitext-Erfassung –
        session.commit()         # bereits gegebene Antworten bleiben erhalten
        return RedirectResponse(f"/erfassung/{erfassung.id}/freitext", status_code=303)
    if richtung == "zurueck":
        ziel = max(0, nr - 1)
        erfassung.seite_index = ziel
        session.commit()
        return RedirectResponse(f"/erfassung/{erfassung.id}/seite/{ziel}", status_code=303)
    if nr + 1 < len(seiten):
        erfassung.seite_index = nr + 1
        session.commit()
        return RedirectResponse(f"/erfassung/{erfassung.id}/seite/{nr + 1}", status_code=303)
    session.commit()
    return RedirectResponse(f"/erfassung/{erfassung.id}/pruefen", status_code=303)


def _korrekturen_protokollieren(erfassung, vorher: dict, nachher: dict,
                                benutzer, logik) -> None:
    """Innendienst-Korrekturen an abgesendeten Erfassungen protokollieren
    und Ampel/Gründe neu berechnen (Phase 14)."""
    if erfassung.status == "Entwurf":
        return
    zeilen = []
    for frage_id in sorted(set(vorher) | set(nachher)):
        if vorher.get(frage_id) != nachher.get(frage_id):
            zeilen.append(f"{datetime.now().strftime('%d.%m.%Y %H:%M')} · "
                          f"{benutzer.name}: {frage_id}: "
                          f"{vorher.get(frage_id, '–')!r} → {nachher.get(frage_id, '–')!r}")
    if zeilen:
        erfassung.aenderungs_protokoll = (
            (erfassung.aenderungs_protokoll + "\n" if erfassung.aenderungs_protokoll else "")
            + "\n".join(zeilen))
        gruende = engine.ampel_gruende(logik, nachher)
        erfassung.ampel = "orange" if gruende else "gruen"
        erfassung.gruende_text = "\n".join(gruende)


def _wert_lesen(frage, form, antworten):
    """Feldnamen sind je Frage benannt (f_<ID>…); Pflicht, sofern nicht optional."""
    name = f"f_{frage.id}"
    if frage.typ == "Auswahl":
        wert = (form.get(name) or "").strip()
        if wert not in frage.antworten:
            return wert, "Bitte auswählen."
        return wert, ""
    if frage.typ in FREITEXT_TYPEN:
        wert = (form.get(name) or "").strip()
        if not wert and not _ist_optional(frage):
            return wert, "Bitte ausfüllen."
        return wert, ""
    if frage.typ == "Datum":   # v8: z. B. Wiedervorlage der Einschätzung
        wert = (form.get(name) or "").strip()
        if not wert:
            return "", ("" if _ist_optional(frage) else "Bitte ein Datum wählen.")
        try:
            datetime.strptime(wert, "%Y-%m-%d")
        except ValueError:
            return wert, "Ungültiges Datum."
        return wert, ""
    if frage.typ in ("Zahleneingabe", "Betragseingabe"):
        roh = (form.get(name) or "").strip()
        if not roh:
            return "", ("" if _ist_optional(frage) else "Bitte eine Zahl eingeben.")
        zahl = engine.zahl_parsen(roh)
        if zahl is None or zahl < 0:
            return roh, "Ungültige Zahl."
        return zahl, ""
    if frage.typ == "Mengenmaske":
        werte = {}
        for option in frage.antworten:
            roh = (form.get(f"{name}_{option}") or "").strip()
            zahl = engine.zahl_parsen(roh) if roh else 0
            if zahl is None or zahl < 0 or zahl != int(zahl):
                return werte, f"Ungültige Anzahl bei {option}."
            werte[option] = int(zahl)
        return werte, ""
    if frage.typ == "Wiederholfeld":
        anzahl = int(engine.zahl_parsen(antworten.get(engine.ID_WIEDERHOL_ANZAHL)) or 0)
        werte = []
        for i in range(1, max(anzahl, 1) + 1):
            roh = (form.get(f"{name}_{i}") or "").strip()
            zahl = engine.zahl_parsen(roh)
            if zahl is None or zahl <= 0 or zahl != int(zahl):
                return werte, f"Verteiler {i}: gültige Gruppenanzahl eingeben."
            werte.append(int(zahl))
        return werte, ""
    return None, f"Unbekannter Fragetyp {frage.typ}."


@router.get("/{erfassung_id}/pruefen")
async def pruefen(request: Request, erfassung_id: int,
                  session: Session = Depends(get_session)):
    erfassung = _erfassung_laden(request, erfassung_id, session)
    if erfassung is None:
        return RedirectResponse("/erfassung", status_code=303)
    logik, _ = _sparten_logik(session, erfassung)
    if logik is None:
        return RedirectResponse(f"/erfassung/{erfassung.id}/freitext", status_code=303)
    antworten = _antworten(erfassung)
    offen = engine.naechste_frage(logik, antworten)
    prot = engine.protokoll(logik, antworten)
    gruende = engine.ampel_gruende(logik, antworten)
    kunde = session.get(Kunde, erfassung.kunde_id)
    return render(request, "erfassung/pruefen.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), erfassung=erfassung, kunde=kunde,
                  protokoll=prot, gruende=gruende, offen=offen,
                  seiten=logik.seiten)


@router.post("/{erfassung_id}/absenden")
async def absenden(request: Request, erfassung_id: int,
                   session: Session = Depends(get_session)):
    erfassung = _erfassung_laden(request, erfassung_id, session)
    if erfassung is None:
        return RedirectResponse("/erfassung", status_code=303)
    logik, _ = _sparten_logik(session, erfassung)
    if logik is None:
        return RedirectResponse(f"/erfassung/{erfassung.id}/freitext", status_code=303)
    antworten = _antworten(erfassung)
    if engine.naechste_frage(logik, antworten) is not None:
        return RedirectResponse(f"/erfassung/{erfassung.id}/pruefen", status_code=303)
    if erfassung.sparte not in ("", "WP"):
        # v8: PV/KL sind reine Erfassungen – immer individuell, direkt in
        # die TAIFUN-Warteschlange (das Angebot entsteht extern)
        erfassung.ampel = "orange"
        erfassung.gruende_text = (f"reine {erfassung.sparte}-Erfassung – "
                                  "das Angebot wird in TAIFUN geschrieben")
        erfassung.status = "In TAIFUN zu schreiben"
        erfassung.abgesendet_am = datetime.now()
        session.commit()
        return render(request, "erfassung/fertig.html", aktiv=None, mobil=True,
                      benutzer=_benutzer(request), erfassung=erfassung)
    gruende = engine.ampel_gruende(logik, antworten)
    erfassung.ampel = "orange" if gruende else "gruen"
    erfassung.gruende_text = "\n".join(gruende)
    # v7: orange Katalog-Fälle landen zur Prüfung beim Innendienst
    erfassung.status = "Individuell – zu prüfen" if gruende else "Neu"
    erfassung.abgesendet_am = datetime.now()
    session.commit()
    return render(request, "erfassung/fertig.html", aktiv=None, mobil=True,
                  benutzer=_benutzer(request), erfassung=erfassung)
