# Lead-Management V1 (v12) – Router unter /lead-management (Ziel der
# bestehenden Startportal-Karte). Der Plan nennt /leads; dort liegt aber die
# unveränderliche Leads-VOT-Liste (Leitplanke 2) – Entscheidung in
# docs/leadmanagement-entscheidungen.md. /api/leads (Phase 75) bleibt wie geplant.
# Demo-Schalter: Nicht-Sichtbare bekommen auf der Einstiegsseite die alte
# Platzhalterseite (Verhalten wie bisher), auf allen anderen Routen 404.

from datetime import datetime, timedelta
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import leadmanagement as kern
from app.db import get_session
from app.models import (Benutzer, Kampagne, Kunde, LeadAktivitaet,
                        LeadQualifizierung, LeadQuelle, Vorgang, VotTermin,
                        ANRUF_ERGEBNIS_NAMEN, LEAD_PHASEN, LEAD_PHASEN_NAMEN)
from app.templating import render

router = APIRouter(prefix="/lead-management")


def _gate(request: Request, session: Session) -> None:
    """404 statt 403 – im Demo-Modus soll das Modul unsichtbar sein."""
    if not kern.lead_modul_sichtbar(session, request.state.benutzer):
        raise HTTPException(status_code=404)


@router.get("")
async def startseite(request: Request, session: Session = Depends(get_session)):
    """Einstieg: Sichtbare landen auf der Anrufliste (Phase 76); alle anderen
    sehen die alte Platzhalterseite – exakt wie vor dem Modul."""
    if not kern.lead_modul_sichtbar(session, request.state.benutzer):
        return render(request, "platzhalter.html", aktiv=None,
                      titel="Lead-Management",
                      hinweis="Dieser Bereich ist im Aufbau (Coming soon). "
                              "Die Lead-Arbeit läuft bis dahin wie gewohnt über "
                              "das Angebotstool (Leads VOT).")
    return RedirectResponse("/lead-management/anrufliste", status_code=303)


@router.get("/anrufliste")
async def anrufliste(request: Request, session: Session = Depends(get_session)):
    """Arbeitsliste des Leadmanagements (Phase 76 baut sie voll aus)."""
    _gate(request, session)
    return render(request, "leadmanagement/anrufliste.html",
                  aktiv="/lead-management",
                  zeilen=[], filter_werte={}, phasen_namen=LEAD_PHASEN_NAMEN,
                  ergebnis_namen=ANRUF_ERGEBNIS_NAMEN,
                  meldung=request.query_params.get("meldung", ""))


# --- Phase 75: Schnellanlage, Import, Posteingang unklar ---------------------------

SPARTEN = ("WP", "PV", "KL", "WB")


def _quellen(session: Session) -> list[LeadQuelle]:
    return (session.query(LeadQuelle).filter(LeadQuelle.aktiv.is_(True))
            .order_by(LeadQuelle.name).all())


def _wunschzeiten_liste() -> list:
    from app import leadmanagement_logik
    return leadmanagement_logik.hole_logik().wunschzeiten


@router.get("/lead/{vorgang_id}")
async def lead_akte(request: Request, vorgang_id: int,
                    session: Session = Depends(get_session)):
    """Lead-Akte = Vorgangsakte (v10) mit Lead-Kopf (Phase 79) – bis dahin
    Weiterleitung auf die bestehende Akte."""
    _gate(request, session)
    return RedirectResponse(f"/vorgaenge/{vorgang_id}", status_code=303)


@router.get("/neu")
async def schnellanlage_formular(request: Request,
                                 session: Session = Depends(get_session)):
    _gate(request, session)
    return render(request, "leadmanagement/neu.html", aktiv="/lead-management",
                  mobil=True, quellen=_quellen(session),
                  kampagnen=session.query(Kampagne)
                  .filter(Kampagne.aktiv.is_(True)).order_by(Kampagne.name).all(),
                  wunschzeiten=_wunschzeiten_liste(), sparten=SPARTEN,
                  daten={}, duplikat=None,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/neu")
async def schnellanlage(request: Request, session: Session = Depends(get_session)):
    _gate(request, session)
    form = await request.form()
    benutzer = request.state.benutzer
    daten = {feld: (form.get(feld) or "").strip()
             for feld in ("anrede", "vorname", "nachname", "telefon", "email",
                          "strasse", "plz", "ort", "nachricht")}
    daten["sparten"] = [s for s in form.getlist("sparten") if s in SPARTEN]
    daten["wunschzeiten"] = [w for w in form.getlist("wunschzeiten")]
    daten["einwilligung_werbung"] = form.get("einwilligung_werbung") == "on"
    daten["einwilligung_quelle"] = form.get("einwilligung_quelle") or "telefonisch"

    fehler = []
    if not daten["nachname"]:
        fehler.append("Nachname ist Pflicht.")
    if not daten["telefon"] and not daten["email"]:
        fehler.append("Telefon ist Pflicht (ersatzweise E-Mail).")
    if not daten["plz"]:
        fehler.append("PLZ ist Pflicht.")
    if not daten["sparten"]:
        fehler.append("Mindestens eine Sparte wählen.")
    quelle = None
    if str(form.get("quelle_id") or "").isdigit():
        quelle = session.get(LeadQuelle, int(form.get("quelle_id")))
    if quelle is None:
        fehler.append("Bitte eine Quelle wählen.")
    kampagne_id = (int(form.get("kampagne_id"))
                   if str(form.get("kampagne_id") or "").isdigit() else None)

    entscheidung = form.get("entscheidung") or ""
    duplikat = None
    if not fehler and not entscheidung:
        duplikat = kern.duplikat_pruefen(
            session, telefon=daten["telefon"], email=daten["email"],
            name=f"{daten['vorname']} {daten['nachname']}",
            plz=daten["plz"], strasse=daten["strasse"])
    if fehler or duplikat is not None:
        return render(request, "leadmanagement/neu.html",
                      aktiv="/lead-management", mobil=True,
                      quellen=_quellen(session),
                      kampagnen=session.query(Kampagne)
                      .filter(Kampagne.aktiv.is_(True)).order_by(Kampagne.name).all(),
                      wunschzeiten=_wunschzeiten_liste(), sparten=SPARTEN,
                      daten=dict(daten, quelle_id=form.get("quelle_id"),
                                 kampagne_id=form.get("kampagne_id")),
                      duplikat=duplikat, phasen_namen=LEAD_PHASEN_NAMEN,
                      meldung=" ".join(fehler))
    vorgang, status = kern.lead_anlegen(session, daten, quelle, "manuell",
                                        benutzer=benutzer,
                                        kampagne_id=kampagne_id,
                                        entscheidung=entscheidung)
    session.commit()
    from urllib.parse import quote_plus
    texte = {"neu": "Lead angelegt.",
             "angehaengt": "An den bestehenden Vorgang angehängt (neue Sparte).",
             "wiederkehrer": "Neuer Vorgang am bestehenden Kunden (Wiederkehrer)."}
    return RedirectResponse("/lead-management/anrufliste?meldung="
                            + quote_plus(texte.get(status, "Lead angelegt.")),
                            status_code=303)


# --- CSV/Excel-Import ---------------------------------------------------------------

_IMPORT_FELDER = ["anrede", "vorname", "nachname", "strasse", "plz", "ort",
                  "telefon", "email", "nachricht"]


def _import_ablage() -> "Path":
    from pathlib import Path

    from app import config
    ordner = config.DATA_ORDNER / "lead_import_tmp"
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def _import_lesen(pfad) -> list[list[str]]:
    """CSV (;, , oder Tab) oder XLSX → Zeilenliste (max. 2000)."""
    from pathlib import Path
    pfad = Path(pfad)
    if pfad.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook
        wb = load_workbook(pfad, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        zeilen = [[("" if z is None else str(z)).strip() for z in reihe]
                  for reihe in ws.iter_rows(values_only=True)]
        wb.close()
    else:
        import csv
        text = pfad.read_text(encoding="utf-8-sig", errors="replace")
        trenner = ";" if text.count(";") >= text.count(",") else ","
        if text.count("\t") > max(text.count(";"), text.count(",")):
            trenner = "\t"
        zeilen = [[(z or "").strip() for z in reihe]
                  for reihe in csv.reader(text.splitlines(), delimiter=trenner)]
    return [z for z in zeilen if any(z)][:2000]


@router.get("/import")
async def import_formular(request: Request,
                          session: Session = Depends(get_session)):
    _gate(request, session)
    return render(request, "leadmanagement/import.html",
                  aktiv="/lead-management", quellen=_quellen(session),
                  kampagnen=session.query(Kampagne)
                  .filter(Kampagne.aktiv.is_(True)).order_by(Kampagne.name).all(),
                  sparten=SPARTEN, schritt="upload", zeilen=[], kopf=[],
                  zuordnung={}, felder=_IMPORT_FELDER, token="", form_daten={},
                  duplikate={}, protokoll=None,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/import")
async def import_verarbeiten(request: Request,
                             session: Session = Depends(get_session)):
    """Zweistufig: Upload → Vorschau (Spaltenzuordnung, Duplikat-Markierung)
    → Import mit Protokoll. Die Datei liegt kurz unter data/lead_import_tmp."""
    import json as json_modul
    import secrets
    from pathlib import Path
    from urllib.parse import quote_plus
    _gate(request, session)
    form = await request.form()
    benutzer = request.state.benutzer
    schritt = form.get("schritt") or "upload"
    kontext = dict(aktiv="/lead-management", quellen=_quellen(session),
                   kampagnen=session.query(Kampagne)
                   .filter(Kampagne.aktiv.is_(True)).order_by(Kampagne.name).all(),
                   sparten=SPARTEN, felder=_IMPORT_FELDER, protokoll=None,
                   duplikate={}, meldung="")

    if schritt == "upload":
        datei = form.get("datei")
        if datei is None or not getattr(datei, "filename", ""):
            return RedirectResponse("/lead-management/import?meldung="
                                    + quote_plus("Bitte eine Datei wählen."),
                                    status_code=303)
        inhalt = await datei.read()
        token = secrets.token_hex(8)
        endung = ".xlsx" if datei.filename.lower().endswith(".xlsx") else ".csv"
        (_import_ablage() / f"{token}{endung}").write_bytes(inhalt)
        pfad = _import_ablage() / f"{token}{endung}"
        zeilen = _import_lesen(pfad)
        if not zeilen:
            return RedirectResponse("/lead-management/import?meldung="
                                    + quote_plus("Datei ist leer oder unlesbar."),
                                    status_code=303)
        kopf = zeilen[0]
        # gespeicherte Zuordnung je Quelle vorschlagen, sonst Namensabgleich
        zuordnung = {}
        quelle_id = form.get("quelle_id") or ""
        if quelle_id.isdigit():
            quelle = session.get(LeadQuelle, int(quelle_id))
            if quelle is not None:
                try:
                    zuordnung = json_modul.loads(kern.parameter_holen(
                        session, f"import_mapping_{quelle.key}", "{}"))
                except ValueError:
                    zuordnung = {}
        if not zuordnung:
            for i, name in enumerate(kopf):
                schluessel = name.strip().lower().replace("-", "").replace("ß", "ss")
                for feld in _IMPORT_FELDER:
                    if feld in schluessel or schluessel in feld:
                        zuordnung[str(i)] = feld
                        break
        duplikate = {}
        for nr, zeile in enumerate(zeilen[1:21]):
            werte = {feld: (zeile[int(i)] if int(i) < len(zeile) else "")
                     for i, feld in zuordnung.items()}
            if kern.duplikat_pruefen(session, telefon=werte.get("telefon", ""),
                                     email=werte.get("email", ""),
                                     name=f"{werte.get('vorname', '')} "
                                          f"{werte.get('nachname', '')}",
                                     plz=werte.get("plz", ""),
                                     strasse=werte.get("strasse", "")):
                duplikate[nr] = True
        return render(request, "leadmanagement/import.html", schritt="vorschau",
                      zeilen=zeilen[1:21], kopf=kopf, zuordnung=zuordnung,
                      token=pfad.name, form_daten=dict(form), **{**kontext,
                      "duplikate": duplikate})

    # schritt == "ausfuehren"
    token = Path(form.get("token") or "").name
    pfad = _import_ablage() / token
    if not token or not pfad.exists():
        return RedirectResponse("/lead-management/import?meldung="
                                + quote_plus("Upload abgelaufen – bitte erneut "
                                             "hochladen."), status_code=303)
    zeilen = _import_lesen(pfad)
    kopf, datenzeilen = zeilen[0], zeilen[1:]
    zuordnung = {}
    for i in range(len(kopf)):
        feld = form.get(f"spalte_{i}") or ""
        if feld in _IMPORT_FELDER:
            zuordnung[str(i)] = feld
    quelle = (session.get(LeadQuelle, int(form.get("quelle_id")))
              if str(form.get("quelle_id") or "").isdigit() else None)
    kampagne_id = (int(form.get("kampagne_id"))
                   if str(form.get("kampagne_id") or "").isdigit() else None)
    sparten = [s for s in form.getlist("sparten") if s in SPARTEN]
    if quelle is not None:   # Zuordnung je Quelle merken
        kern.parameter_setzen(session, f"import_mapping_{quelle.key}",
                              json_modul.dumps(zuordnung))
    protokoll = {"angelegt": 0, "angehaengt": 0, "uebersprungen": []}
    for nr, zeile in enumerate(datenzeilen, start=2):
        try:
            werte = {feld: (zeile[int(i)] if int(i) < len(zeile) else "")
                     for i, feld in zuordnung.items()}
            werte["sparten"] = sparten
            werte["einwilligung_quelle"] = "portal"
            if not werte.get("nachname"):
                protokoll["uebersprungen"].append(f"Zeile {nr}: Nachname fehlt")
                continue
            if not werte.get("plz"):
                protokoll["uebersprungen"].append(f"Zeile {nr}: PLZ fehlt")
                continue
            if not werte.get("telefon") and not werte.get("email"):
                protokoll["uebersprungen"].append(
                    f"Zeile {nr}: weder Telefon noch E-Mail")
                continue
            _, status = kern.lead_anlegen(session, werte, quelle, "import",
                                          benutzer=benutzer,
                                          kampagne_id=kampagne_id)
            protokoll["angelegt" if status != "angehaengt"
                      else "angehaengt"] += 1
        except Exception as problem:
            protokoll["uebersprungen"].append(f"Zeile {nr}: {problem}")
    session.commit()
    try:
        pfad.unlink()
    except OSError:
        pass
    return render(request, "leadmanagement/import.html", schritt="fertig",
                  zeilen=[], kopf=[], zuordnung={}, token="", form_daten={},
                  **{**kontext, "protokoll": protokoll})


# --- Posteingang unklar ---------------------------------------------------------------

@router.get("/posteingang")
async def posteingang(request: Request, session: Session = Depends(get_session)):
    _gate(request, session)
    from app.models import LeadPosteingang
    eintraege = (session.query(LeadPosteingang)
                 .filter(LeadPosteingang.status == "offen")
                 .order_by(LeadPosteingang.erstellt_am.desc()).limit(100).all())
    return render(request, "leadmanagement/posteingang.html",
                  aktiv="/lead-management", eintraege=eintraege,
                  meldung=request.query_params.get("meldung", ""))


@router.post("/posteingang/{eintrag_id}/ignorieren")
async def posteingang_ignorieren(request: Request, eintrag_id: int,
                                 session: Session = Depends(get_session)):
    _gate(request, session)
    from app.models import LeadPosteingang
    eintrag = session.get(LeadPosteingang, eintrag_id)
    if eintrag is not None:
        eintrag.status = "ignoriert"
        session.commit()
    return RedirectResponse("/lead-management/posteingang", status_code=303)


@router.get("/posteingang/{eintrag_id}/anlegen")
async def posteingang_anlegen(request: Request, eintrag_id: int,
                              session: Session = Depends(get_session)):
    """„Als Lead anlegen“: Schnellanlage-Formular, soweit möglich vorbefüllt."""
    _gate(request, session)
    from app import lead_parser
    from app.models import LeadPosteingang, ParserRegel
    eintrag = session.get(LeadPosteingang, eintrag_id)
    if eintrag is None:
        return RedirectResponse("/lead-management/posteingang", status_code=303)
    hilfsregel = ParserRegel(format="zeilen", feldzuordnung="{}")
    daten = lead_parser.mail_parsen(hilfsregel, eintrag.betreff, eintrag.body)
    daten.setdefault("email", eintrag.absender)
    daten.setdefault("nachricht", eintrag.body[:1000])
    daten.pop("rohdaten", None)
    return render(request, "leadmanagement/neu.html", aktiv="/lead-management",
                  mobil=True, quellen=_quellen(session),
                  kampagnen=session.query(Kampagne)
                  .filter(Kampagne.aktiv.is_(True)).order_by(Kampagne.name).all(),
                  wunschzeiten=_wunschzeiten_liste(), sparten=SPARTEN,
                  daten=daten, duplikat=None,
                  meldung=f"Vorbefüllt aus Posteingang: {eintrag.betreff}")
