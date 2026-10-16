# v35 (PLAN_LEAD_V6 Phase 186, Agent G): Fotos je Objekt – Upload direkt an der Objektkarte der
# Kundenkartei (mehrere Dateien, mobil per Kamera; JPG/PNG/HEIC → JPG, max. 10 MB je Bild) und
# Löschen durch Hochladenden/Innendienst/Admin. Die Fachlogik liegt in app/galerie.py
# (Abschnitt „Fotos je Objekt“: Ordner „Objekt <Bezeichnung>“ je aktivem Objekt des Vorgangs).
#
# v27/v33-Regeln: def-Routen; der Request-Body (Upload) ist Netz-I/O – die Schreibsitzung gibt
# die Verbindung VOR anfrage.formular(request) frei (Wächter
# tests/test_v33_fundament.py::UploadRoutenOhneSchreibsperre); die Dateien werden ohne
# gehaltene Sitzung geschrieben/gewandelt, die Zeilen in einer kurzen Schreibtransaktion
# angelegt (galerie.objektfotos_speichern). Rechte: galerie.objektfotos_erlaubt – Galerie-Rechte
# (Innendienst/Admin/Projektierung, Außendienst am eigenen Vorgang, Montage in der Besetzung)
# oder Bearbeiten-Rechte des Lead-Moduls (Vertrag Agent R: lead_v2.bearbeiten_erlaubt; bis dahin
# Übergangsprüfung lead_v2.zugriff_erlaubt). JSON bei Accept: application/json
# (objektfotos_v35.js), sonst Redirect in die Kartei (#objekt-<id>) – ohne JavaScript bleibt das
# normale Formular nutzbar.
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import anfrage   # v27: Formular in def-Routen
from app import galerie as galerie_modul
from app.db import get_session, verbindung_freigeben
from app.models import GalerieDatei, Vorgang, VorgangObjekt

router = APIRouter(prefix="/lead-management", tags=["leadmanagement"])


def _json_gewuenscht(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "").lower()


def _kartei_url(vorgang_id: int, objekt_id: int | None = None, meldung: str = "") -> str:
    url = f"/lead-management/lead/{vorgang_id}"
    if meldung:
        url += "?meldung=" + quote_plus(meldung)
    if objekt_id:
        url += f"#objekt-{objekt_id}"
    return url


def _ziel_pruefen(zurueck: str, vorgang_id: int, objekt_id: int) -> str:
    """Nur relative Pfade des Tools als Rücksprungziel (kein //host, kein http)."""
    ziel = (zurueck or "").strip()
    if not ziel.startswith("/") or ziel.startswith("//"):
        return _kartei_url(vorgang_id)
    return ziel.split("#", 1)[0]


def _antwort(request: Request, vorgang_id: int, objekt_id: int | None, ok: bool, meldung: str,
             zusatz: dict | None = None, status_fehler: int = 400, zurueck: str = ""):
    if _json_gewuenscht(request):
        daten = {"ok": ok, "meldung": meldung}
        if zusatz:
            daten.update(zusatz)
        return JSONResponse(daten, status_code=200 if ok else status_fehler)
    ziel = _ziel_pruefen(zurueck, vorgang_id, objekt_id or 0) if zurueck else _kartei_url(vorgang_id)
    trenner = "&" if "?" in ziel else "?"
    ziel = ziel + trenner + "meldung=" + quote_plus(meldung)
    if objekt_id:
        ziel += f"#objekt-{objekt_id}"
    return RedirectResponse(ziel, status_code=303)


def _objekt_laden(session: Session, vorgang_id: int, objekt_id: int):
    """(vorgang, objekt) oder (None, None), wenn das Objekt nicht (aktiv) zum Vorgang gehört."""
    vorgang = session.get(Vorgang, vorgang_id)
    objekt = session.get(VorgangObjekt, objekt_id) if vorgang is not None else None
    if vorgang is None or objekt is None or objekt.vorgang_id != vorgang.id or not objekt.aktiv:
        return None, None
    return vorgang, objekt


@router.post("/lead/{vorgang_id}/objekt/{objekt_id}/fotos")
def objektfotos_hochladen(request: Request, vorgang_id: int, objekt_id: int,
                          session: Session = Depends(get_session)):
    """Mehrere Dateien (Feld `dateien`, mobil per Kamera) in den Objekt-Ordner der Galerie;
    JPG/PNG/HEIC, HEIC → JPG, max. 10 MB je Bild; Teilerfolg je Datei in der Meldung.
    JSON: {ok, anzahl, abgelegt[], fehler[], meldung, ordner, objekt_id, fotos[]} – `fotos` ist
    die vollständige, neu geladene Fotoliste des Objekts (foto_daten) zum Neuzeichnen der
    Kacheln ohne Seitenneuladen."""
    benutzer = request.state.benutzer
    vorgang, objekt = _objekt_laden(session, vorgang_id, objekt_id)
    if vorgang is None:
        return _antwort(request, vorgang_id, None, False, "Objekt nicht gefunden.", status_fehler=404)
    if not galerie_modul.objektfotos_erlaubt(session, vorgang, benutzer):
        return _antwort(request, vorgang_id, objekt_id, False,
                        "Kein Upload-Recht für dieses Objekt.", status_fehler=403)
    # v33 (Phase 172, Befund 15.10.2026): der Request-Body ist Netz-I/O – Verbindung und
    # Schreibsperre freigeben, bevor das Formular (die Dateien) gelesen wird
    verbindung_freigeben(session)
    form = anfrage.formular(request)
    dateien = form.getlist("dateien") or form.getlist("dateien[]")
    zurueck = form.get("zurueck") or ""
    ergebnis = galerie_modul.objektfotos_speichern(session, vorgang, objekt, dateien, benutzer)
    meldung = galerie_modul.meldung_fuer(ergebnis, ergebnis.get("ordner", ""))
    if not dateien or all(not getattr(d, "filename", "") for d in dateien):
        meldung = "Keine Datei ausgewählt."
    if _json_gewuenscht(request):
        fotos = galerie_modul.objektfotos_daten(session, vorgang.id, objekt, benutzer)
        return JSONResponse({"ok": not ergebnis["fehler"] and bool(ergebnis["abgelegt"]),
                             "anzahl": len(ergebnis["abgelegt"]),
                             "abgelegt": ergebnis["abgelegt"], "fehler": ergebnis["fehler"],
                             "meldung": meldung, "ordner": ergebnis.get("ordner", ""),
                             "objekt_id": objekt.id, "fotos": fotos})
    return _antwort(request, vorgang.id, objekt.id, True, meldung, zurueck=zurueck)


@router.post("/lead/{vorgang_id}/objekt/{objekt_id}/fotos/{datei_id}/loeschen")
def objektfoto_loeschen(request: Request, vorgang_id: int, objekt_id: int, datei_id: int,
                        session: Session = Depends(get_session)):
    """Löschen durch den Hochladenden, Innendienst oder Admin (galerie.objektfoto_loeschen_erlaubt);
    nur Fotos, die zu diesem Objekt gehören. Zeile + Chat-Notiz in einer kurzen
    Schreibtransaktion, Datei danach ohne Sitzung. JSON: {ok, meldung, objekt_id, fotos[]}."""
    benutzer = request.state.benutzer
    vorgang, objekt = _objekt_laden(session, vorgang_id, objekt_id)
    if vorgang is None:
        return _antwort(request, vorgang_id, None, False, "Objekt nicht gefunden.", status_fehler=404)
    if not galerie_modul.objektfotos_erlaubt(session, vorgang, benutzer):
        return _antwort(request, vorgang_id, objekt_id, False, "Kein Zugriff auf diesen Vorgang.",
                        status_fehler=403)
    datei = session.get(GalerieDatei, datei_id)
    gehoert = (datei is not None and datei.vorgang_id == vorgang.id
               and any(d.id == datei.id for d in galerie_modul.objektfotos(session, vorgang.id, objekt)))
    if not gehoert:
        return _antwort(request, vorgang.id, objekt.id, False, "Foto nicht gefunden.", status_fehler=404)
    if not galerie_modul.objektfoto_loeschen_erlaubt(datei, benutzer):
        return _antwort(request, vorgang.id, objekt.id, False,
                        "Löschen nur durch den Hochladenden, Innendienst oder Admin.",
                        status_fehler=403)
    form = anfrage.formular(request)
    zurueck = form.get("zurueck") or ""
    name = galerie_modul.objektfoto_loeschen(session, datei, benutzer)
    meldung = f"Foto „{name}“ gelöscht."
    if _json_gewuenscht(request):
        return JSONResponse({"ok": True, "meldung": meldung, "objekt_id": objekt.id,
                             "fotos": galerie_modul.objektfotos_daten(session, vorgang.id, objekt, benutzer)})
    return _antwort(request, vorgang.id, objekt.id, True, meldung, zurueck=zurueck)
