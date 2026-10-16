# v35 (PLAN_LEAD_V6 Phase 183, Agent T): TAIFUN-Kundenübergabe – Routen (Präfix /lead-management):
#  POST /lead/{id}/taifun                  „Erneut übergeben“ / „Trotzdem übergeben“ je Zeile der
#                                           Übergabeliste (ID/LM/Admin; v35-Nachtrag 3, 16.10.2026:
#                                           kein Kartei-Knopf mehr). Rückfrage (Dublette / bereits
#                                           übergeben) ohne bestaetigt=1 → 409 JSON {rueckfrage} bzw.
#                                           Redirect auf die Liste mit ?taifun_rueckfrage=<Vorgang>
#                                           (Balken „Trotzdem übergeben“ ohne JavaScript); JSON bei
#                                           Accept: application/json; Rücksprung über `zurueck`
#  GET  /lead/{id}/taifun/{uebergabe_id}/xml   Download der Protokoll-Kopie (data/taifun_export)
#  GET  /taifun-uebergaben?status=           Übergabeliste (Datum, Vorgang, Datei, Benutzer, Status)
#  POST /taifun-uebergaben/{id}/importiert   „Als importiert markieren“
#  POST /taifun/testdatei                    „Testdatei schreiben“ (Admin, funktioniert immer)
#  POST /taifun/ordner-pruefen               „Ordner prüfen“ (Admin, Dienstkonto-Hinweis)
# v27-Regel: def-Routen, Datei-I/O erst nach db.verbindung_freigeben (in taifun_export), Formular
# über anfrage.formular; keine Glocke, keine Kundenmail.

from urllib.parse import quote_plus, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import anfrage, lead_v2, taifun_export
from app import leadmanagement as kern
from app.db import get_session, verbindung_freigeben
from app.models import Kunde, TaifunUebergabe, Vorgang
from app.templating import render

router = APIRouter(prefix="/lead-management", tags=["leadmanagement"])

LISTE = "/lead-management/taifun-uebergaben"
LEAD_EINSTELLUNGEN = "/parametrierung/lead-einstellungen"


def _json_gewuenscht(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "").lower()


def _mit_meldung(pfad: str, meldung: str, **params) -> str:
    teile = ["meldung=" + quote_plus(meldung)] + [f"{k}={quote_plus(str(v))}" for k, v in params.items() if v]
    return pfad + ("&" if "?" in pfad else "?") + "&".join(teile)


def _zurueck(request: Request, form, standard: str) -> str:
    """Rücksprungziel: Formularfeld `zurueck`, sonst Referer-Pfad (nur relative Ziele dieses
    Tools), sonst Standard."""
    ziel = (form.get("zurueck") or "").strip() if form is not None else ""
    if not ziel:
        referer = request.headers.get("referer") or ""
        if referer:
            teile = urlsplit(referer)
            if (teile.path or "").startswith("/") and not teile.path.startswith("//"):
                ziel = teile.path + (f"?{teile.query}" if teile.query else "")
    if not ziel.startswith("/") or ziel.startswith("//") or "\\" in ziel:
        return standard
    return ziel


def _modul_gate(request: Request, session: Session) -> None:
    """Übergabeliste/Download: Innendienst, Leadmanagement, Admin (Handelsvertreter-Sicht → 303
    auf die HV-Ansicht, andere 404)."""
    lead_v2.hv_umleitung(request, session)
    if not kern.lead_modul_sichtbar(session, request.state.benutzer):
        raise HTTPException(status_code=404)


def _admin_gate(request: Request) -> None:
    benutzer = request.state.benutzer
    if benutzer is None or benutzer.basisrolle != "admin":
        raise HTTPException(status_code=404)


def _formular_oder_json(request: Request) -> dict:
    typ = (request.headers.get("content-type") or "").lower()
    if "application/json" in typ:
        try:
            daten = anfrage.json_lesen(request)
        except ValueError:
            return {}
        return daten if isinstance(daten, dict) else {}
    try:
        form = anfrage.formular(request)
    except Exception:   # noqa: BLE001 – leerer Body
        return {}
    return {k: form.get(k) for k in form.keys()}


# --- Erneute Übergabe aus der Übergabeliste ------------------------------------------------------

@router.post("/lead/{vorgang_id}/taifun")
def lead_uebergeben(request: Request, vorgang_id: int, session: Session = Depends(get_session)):
    """Knopf „Erneut übergeben“ / „Trotzdem übergeben“ je Zeile der Übergabeliste (ID/LM/Admin).
    Rückfrage (Kunde vermutlich schon in TAIFUN / bereits übergeben) nur mit `bestaetigt=1`
    übergehbar – ohne JavaScript Redirect auf die Liste mit dem Rückfrage-Balken; Schalter aus
    oder Kanal „?“ → keine Übergabe (409). Rücksprung = Formularfeld `zurueck` (Liste mit Filter),
    sonst Referer, sonst die Übergabeliste."""
    vorgang = session.get(Vorgang, vorgang_id)
    if vorgang is None:
        raise HTTPException(status_code=404)
    lead_v2.gate(request, session, vorgang)
    benutzer = request.state.benutzer
    daten = _formular_oder_json(request)
    ziel = _zurueck(request, daten, LISTE)
    if not taifun_export.darf_uebergeben(session, benutzer):
        return _antwort(request, False, "Die TAIFUN-Übergabe ist dem Innendienst, Leadmanagement und Admin "
                        "vorbehalten.", ziel, status=403)
    kunde = session.get(Kunde, vorgang.kunde_id)
    zustand = taifun_export.pruefung(session, vorgang, kunde)
    if not zustand["aktiv"]:
        return _antwort(request, False, taifun_export.NICHT_AKTIV_TEXT
                        + " – Lead-Einstellungen → TAIFUN-Übergabe.", ziel, status=409)
    if zustand["kanal_unklar"]:
        return _antwort(request, False, taifun_export.KANAL_UNKLAR_TEXT, ziel, status=409)
    bestaetigt = str(daten.get("bestaetigt") or "").strip().lower() in ("1", "true", "ja", "on")
    if zustand["rueckfrage"] and not bestaetigt:
        if _json_gewuenscht(request):
            return JSONResponse({"ok": False, "rueckfrage": zustand["rueckfrage"],
                                 "meldung": zustand["rueckfrage"]}, status_code=409)
        # ohne JavaScript: zurück auf die Übergabeliste, dort der Balken „Trotzdem übergeben“
        liste_ziel = ziel if ziel.split("?", 1)[0] == LISTE else LISTE
        return RedirectResponse(_mit_meldung(liste_ziel, zustand["rueckfrage"], taifun_rueckfrage=vorgang.id),
                                status_code=303)
    ok, meldung, uebergabe = taifun_export.exportieren(session, vorgang.id, benutzer.id,
                                                       taifun_export.GRUND_MANUELL)
    zusatz = {"datei": uebergabe.datei if uebergabe is not None else "",
              "status": uebergabe.status if uebergabe is not None else "",
              "uebergabe_id": uebergabe.id if uebergabe is not None else None}
    return _antwort(request, ok, meldung, ziel, zusatz=zusatz, status=422)


def _antwort(request: Request, ok: bool, meldung: str, ziel: str, zusatz: dict | None = None,
             status: int = 400):
    if _json_gewuenscht(request):
        daten = {"ok": ok, "meldung": meldung}
        if zusatz:
            daten.update(zusatz)
        return JSONResponse(daten, status_code=200 if ok else status)
    return RedirectResponse(_mit_meldung(ziel, meldung, fehler=0 if ok else 1), status_code=303)


# --- Download der Protokoll-Kopie -----------------------------------------------------------------

@router.get("/lead/{vorgang_id}/taifun/{uebergabe_id}/xml")
def xml_herunterladen(request: Request, vorgang_id: int, uebergabe_id: int,
                      session: Session = Depends(get_session)):
    """XML anzeigen/herunterladen – Kopie unter data/taifun_export/<Datei> (ID/LM/Admin)."""
    _modul_gate(request, session)
    eintrag = session.get(TaifunUebergabe, uebergabe_id)
    if eintrag is None or (eintrag.vorgang_id or 0) != vorgang_id:
        raise HTTPException(status_code=404)
    pfad = taifun_export.kopie_pfad(eintrag.datei)
    if pfad is None:
        raise HTTPException(status_code=404, detail="Keine Kopie dieser Übergabe vorhanden.")
    verbindung_freigeben(session)
    return FileResponse(str(pfad), media_type="application/xml", filename=eintrag.datei)


# --- Übergabeliste -----------------------------------------------------------------------------

@router.get("/taifun-uebergaben")
def uebergabeliste(request: Request, session: Session = Depends(get_session)):
    """Liste aller Exporte (Datum, Vorgang, Datei, Benutzer, Status) mit Filter ?status=
    geschrieben|abgeholt|fehler|importiert|uebersprungen; Knöpfe „Als importiert markieren“, „XML“ und
    je Zeile mit Vorgang „Erneut übergeben“ bzw. „Trotzdem übergeben“ (Rückfrage mit dem Datum der
    letzten Übergabe). ?taifun_rueckfrage=<Vorgang> zeigt den Rückfrage-Balken ohne JavaScript."""
    _modul_gate(request, session)
    status = (request.query_params.get("status") or "").strip().lower()
    if status not in taifun_export.STATUS_NAMEN:
        status = ""
    zeilen = taifun_export.liste(session, status)
    rueckfrage = None
    try:
        rueckfrage_id = int(request.query_params.get("taifun_rueckfrage") or 0)
    except ValueError:
        rueckfrage_id = 0
    if rueckfrage_id:
        vorgang = session.get(Vorgang, rueckfrage_id)
        if vorgang is not None:
            kunde = session.get(Kunde, vorgang.kunde_id)
            text = taifun_export.rueckfrage_text(session, vorgang, kunde)
            if text:
                rueckfrage = {"vorgang": vorgang, "kunde": kunde, "text": text,
                              "url": f"/lead-management/lead/{vorgang.id}/taifun"}
    return render(request, "leadmanagement/taifun_uebergaben.html", aktiv="/lead-management",
                  zeilen=zeilen, status=status, zaehler=taifun_export.status_zaehler(session),
                  status_namen=taifun_export.STATUS_NAMEN, aktiv_schalter=taifun_export.aktiv(session),
                  ordner=taifun_export.import_ordner(session), lauf=taifun_export.LAUF_NAME,
                  ist_admin=request.state.benutzer.basisrolle == "admin",
                  rueckfrage=rueckfrage, liste_url=LISTE,
                  meldung=request.query_params.get("meldung", ""),
                  fehler=request.query_params.get("fehler", "") == "1")


@router.post("/taifun-uebergaben/{uebergabe_id}/importiert")
def importiert_markieren(request: Request, uebergabe_id: int, session: Session = Depends(get_session)):
    """„Als importiert markieren“ (manueller Import in TAIFUN bestätigt)."""
    _modul_gate(request, session)
    eintrag = session.get(TaifunUebergabe, uebergabe_id)
    if eintrag is None:
        raise HTTPException(status_code=404)
    daten = _formular_oder_json(request)
    ok, meldung = taifun_export.als_importiert(session, eintrag, benutzer=request.state.benutzer)
    if ok:
        session.commit()
    else:
        session.rollback()
    return _antwort(request, ok, meldung, _zurueck(request, daten, LISTE),
                    zusatz={"uebergabe_id": eintrag.id, "status": eintrag.status}, status=409)


# --- Parametrierung: Testdatei, Ordner prüfen -------------------------------------------------------

@router.post("/taifun/testdatei")
def testdatei(request: Request, session: Session = Depends(get_session)):
    """„Testdatei schreiben“ – Demo-Lead „Max Mustermann“ als LM_TEST_<Zeit>.xml in den
    Import-Ordner (auch bei taifun_export_aktiv = aus). Datei-I/O nach Sitzungsfreigabe."""
    _admin_gate(request)
    daten = _formular_oder_json(request)
    ok, meldung, uebergabe = taifun_export.testdatei_schreiben(session, request.state.benutzer.id)
    return _antwort(request, ok, meldung, _zurueck(request, daten, LEAD_EINSTELLUNGEN),
                    zusatz={"datei": uebergabe.datei if uebergabe is not None else ""}, status=422)


@router.post("/taifun/ordner-pruefen")
def ordner_pruefen(request: Request, session: Session = Depends(get_session)):
    """„Ordner prüfen“: existiert, beschreibbar (Testdatei schreiben und entfernen) – Ergebnis im
    Parameter taifun_ordner_geprueft (Prüfpunkt „Ordner erreichbar“)."""
    _admin_gate(request)
    daten = _formular_oder_json(request)
    ordner = (daten.get("taifun_import_ordner") or "").strip() or taifun_export.import_ordner(session)
    verbindung_freigeben(session)
    ok, text = taifun_export.ordner_pruefen(ordner)
    taifun_export.ordner_pruefung_speichern(session, ok, text)
    session.commit()
    return _antwort(request, ok, text, _zurueck(request, daten, LEAD_EINSTELLUNGEN), status=422)
