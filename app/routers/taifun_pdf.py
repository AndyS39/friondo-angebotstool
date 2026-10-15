# v34 (PLAN_V21 Phase 180, Agent V): TAIFUN-Angebots-PDF lesen (pypdf) für „Extern erledigt“ und den
# TAIFUN-Eintrag – eigener Router (Präfix /angebote).
#
# POST /angebote/extern/pdf-lesen  (JSON, Formular mit Datei `pdf_datei`)
#   → {ok, nummer, datum, endbetrag, sparte, hinweis, text_gefunden, pruefen}
#   Die Oberfläche (app/static/taifun_pdf.js) ruft die Route beim Ablegen/Auswählen eines PDFs
#   auf und belegt die Felder des Dialogs „Extern erledigt“ vor bzw. zeigt am TAIFUN-Eintrag
#   die „übernehmen“-Häkchen. Es wird NICHTS gespeichert – reines Lesen.
#   Upload-Regel (v33 Phase 172): kein Datenbankzugriff vor dem Lesen des Formulars – diese Route
#   braucht gar keine Sitzung (keine Schreibsperre während der Übertragung).
#   Grenzen: nur PDF, höchstens 20 MB; ohne Textebene (Scan) → „Kein Text im PDF gefunden“.
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import anfrage, taifun_pdf

router = APIRouter(prefix="/angebote", tags=["angebote"])

# Rollen, die externe TAIFUN-Einträge anlegen/pflegen (ID/Admin; Projektierung pflegt die
# Auftragsdaten mit demselben PDF – v18) [ANNAHME]
LESEN_ROLLEN = ("admin", "innendienst", "projektierung")


@router.post("/extern/pdf-lesen")
def pdf_lesen(request: Request):
    """Text des hochgeladenen TAIFUN-PDFs lesen und die erkannten Felder als JSON liefern."""
    benutzer = getattr(request.state, "benutzer", None)
    if benutzer is None or benutzer.basisrolle not in LESEN_ROLLEN:
        return JSONResponse({"ok": False, "meldung": "Kein Zugriff."}, status_code=403)
    form = anfrage.formular(request)
    datei = form.get("pdf_datei")
    if datei is None or not getattr(datei, "filename", ""):
        return JSONResponse({"ok": False, "meldung": "Bitte eine PDF-Datei auswählen."},
                            status_code=400)
    inhalt = datei.file.read()
    fehler = taifun_pdf.groesse_pruefen(len(inhalt))
    if fehler:
        return JSONResponse({"ok": False, "meldung": fehler}, status_code=413)
    if not taifun_pdf.ist_pdf(inhalt):
        return JSONResponse({"ok": False, "meldung": taifun_pdf.MELDUNG_KEIN_PDF},
                            status_code=415)
    werte = taifun_pdf.formular_werte(taifun_pdf.text_lesen(inhalt))
    werte["dateiname"] = (getattr(datei, "filename", "") or "")[:200]
    return JSONResponse(werte)
