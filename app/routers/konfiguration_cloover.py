# v36 (PLAN_V22 Phase 192, Agent B1): Parametrierung → Cloover (Admin).
# Eigene Router-Datei (Prefix /parametrierung wie konfiguration_heizreport.py): Zugang (Key-Stand nur als
# „gesetzt/fehlt“ – der Key steht ausschließlich in der .env und wird hier weder gesetzt noch angezeigt,
# Basis-URL, Modus aus | test | live, Standard-Konto), Finanzierung (Laufzeit, Anzahlung, Optionen,
# financingDuration, Sparten, KL-Anlagentyp), Textbausteine (Fußnote, Datenschutzsatz – Entwürfe),
# Knopf „Verbindung testen“ (Netz nur nach verbindung_freigeben), PDF-Ablage (Partial von Agent B3),
# Änderungsprotokoll cloover_protokoll (letzte 30). Innendienst und andere Rollen: 403.
import re
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import anfrage, cloover_api, cloover_pdf_ablage, cloover_texte
from app.db import get_session, verbindung_freigeben
from app.models import einstellung_setzen
from app.templating import render

router = APIRouter(prefix="/parametrierung")

SEITE = "/parametrierung/cloover"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TEXT_FELDER = (cloover_texte.KEY_FUSSNOTE, cloover_texte.KEY_DATENSCHUTZ)


def _nur_admin(request: Request):
    """Admin-exklusiv; andere Rollen bekommen 403 (Briefing B1), kein Key-Stand nach außen."""
    benutzer = request.state.benutzer
    if benutzer is None or benutzer.basisrolle != "admin":
        return PlainTextResponse("Nur Admin.", status_code=403)
    return None


def _zurueck(meldung: str = "", test: str = "", anker: str = "") -> RedirectResponse:
    ziel = SEITE
    teile = []
    if meldung:
        teile.append("meldung=" + quote_plus(meldung))
    if test:
        teile.append("test=" + quote_plus(test))
    if teile:
        ziel += "?" + "&".join(teile)
    return RedirectResponse(ziel + anker, status_code=303)


def _werte(session) -> dict:
    """Alle Parameter der Seite (ohne Key)."""
    return {
        "modus_gespeichert": cloover_api.modus_gespeichert(session),
        "modus": cloover_api.modus(session),
        "standard_email": cloover_api.standard_email(session),
        "laufzeit_jahre": cloover_api.laufzeit_jahre(session),
        "anzahlung_eur": cloover_api.eur_text(cloover_api.anzahlung_cent(session)),
        "optionen": cloover_api.optionen(session),
        "laufzeit_von_bis": cloover_api.laufzeit_von_bis(session),
        "sparten": cloover_api.sparten(session),
        "kl_typ": cloover_api.kl_typ(session),
    }


def _speichern(session, form, benutzer) -> tuple[str, list[str]]:
    """Speichert alle mitgeschickten Abschnitte; liefert (Meldung, Fehlerliste). Jede Änderung wird
    protokolliert; abgelehnte Werte bleiben unverändert."""
    aenderungen: list[str] = []
    fehler: list[str] = []
    # Zugang: Modus (live nur mit Live-URL), Standard-Konto
    if "cloover_modus" in form:
        gewuenscht = (form.get("cloover_modus") or "").strip().lower()
        alt = cloover_api.modus_gespeichert(session)
        if gewuenscht != alt:
            ok, meldung = cloover_api.modus_setzen(session, gewuenscht)
            if ok:
                aenderungen.append(f"cloover_modus: {alt} → {gewuenscht}")
            else:
                fehler.append(meldung)
    if "cloover_standard_email" in form:
        email = (form.get("cloover_standard_email") or "").strip().lower()
        alt = cloover_api.standard_email(session)
        if not email:
            fehler.append("Standard-Konto (Cloover-E-Mail) darf nicht leer sein.")
        elif not _EMAIL.match(email):
            fehler.append(f"Standard-Konto: „{email}“ ist keine E-Mail-Adresse.")
        elif email != alt:
            einstellung_setzen(session, cloover_api.EINSTELLUNG_STANDARD_EMAIL, email[:200])
            aenderungen.append(f"cloover_standard_email: {alt} → {email}")
    # Finanzierung
    if "cloover_laufzeit_jahre" in form:
        roh = (form.get("cloover_laufzeit_jahre") or "").strip()
        alt = cloover_api.laufzeit_jahre(session)
        if not roh.isdigit() or not cloover_api.LAUFZEIT_MIN_API <= int(roh) <= cloover_api.LAUFZEIT_MAX_API:
            fehler.append(f"Laufzeit: ganze Zahl zwischen {cloover_api.LAUFZEIT_MIN_API} und "
                          f"{cloover_api.LAUFZEIT_MAX_API} Jahren erwartet.")
        elif int(roh) != alt:
            einstellung_setzen(session, "cloover_laufzeit_jahre", str(int(roh)))
            aenderungen.append(f"cloover_laufzeit_jahre: {alt} → {int(roh)}")
    if "cloover_anzahlung_eur" in form:
        roh = (form.get("cloover_anzahlung_eur") or "").strip() or "0"
        cent = cloover_api.eur_parsen(roh)
        alt = cloover_api.anzahlung_cent(session)
        if cent is None or cent < 0:
            fehler.append(f"Anzahlung: Betrag in Euro erwartet (z. B. 1.500,00), nicht „{roh}“.")
        elif cent != alt:
            einstellung_setzen(session, "cloover_anzahlung_eur", cloover_api.eur_text(cent))
            aenderungen.append(f"cloover_anzahlung_eur: {cloover_api.eur_text(alt)} → {cloover_api.eur_text(cent)}")
    if form.get("cloover_formular") == "1":
        # Mehrfachauswahlen nur, wenn das vollständige Formular kommt (sonst würde ein Teil-POST sie leeren)
        gewaehlt = [o for o in cloover_api.OPTIONEN_API if o in set(form.getlist("cloover_optionen"))]
        alt = cloover_api.optionen(session)
        if not gewaehlt:
            fehler.append("Finanzierungsoptionen: mindestens eine Option wählen (Cash, Financing, ClooverPay).")
        elif gewaehlt != alt:
            einstellung_setzen(session, "cloover_optionen", ",".join(gewaehlt))
            aenderungen.append(f"cloover_optionen: {', '.join(alt)} → {', '.join(gewaehlt)}")
        sparten_neu = [s for s in cloover_api.SPARTEN_REIHENFOLGE
                       if s in {x.strip().upper() for x in form.getlist("cloover_sparten")}]
        alt_sparten = cloover_api.sparten(session)
        if sparten_neu != alt_sparten:
            # keine Sparte = KEINE_SPARTEN (leer hieße Standard = alle vier)
            einstellung_setzen(session, "cloover_sparten", ",".join(sparten_neu) or cloover_api.KEINE_SPARTEN)
            aenderungen.append(f"cloover_sparten: {', '.join(alt_sparten) or '–'} → {', '.join(sparten_neu) or '–'}")
    if "cloover_laufzeit_min" in form or "cloover_laufzeit_max" in form:
        alt_von, alt_bis = cloover_api.laufzeit_von_bis(session)
        roh_von = (form.get("cloover_laufzeit_min") or str(alt_von)).strip()
        roh_bis = (form.get("cloover_laufzeit_max") or str(alt_bis)).strip()
        if not (roh_von.isdigit() and roh_bis.isdigit()):
            fehler.append("financingDuration: ganze Jahreszahlen erwartet.")
        else:
            von, bis = int(roh_von), int(roh_bis)
            if not (cloover_api.LAUFZEIT_MIN_API <= von <= bis <= cloover_api.LAUFZEIT_MAX_API):
                fehler.append(f"financingDuration: {cloover_api.LAUFZEIT_MIN_API} ≤ von ≤ bis ≤ "
                              f"{cloover_api.LAUFZEIT_MAX_API} Jahre erwartet.")
            elif (von, bis) != (alt_von, alt_bis):
                einstellung_setzen(session, "cloover_laufzeit_min", str(von))
                einstellung_setzen(session, "cloover_laufzeit_max", str(bis))
                aenderungen.append(f"cloover_laufzeit_min/_max: {alt_von}–{alt_bis} → {von}–{bis}")
    if "cloover_kl_typ" in form:
        typ = (form.get("cloover_kl_typ") or "").strip()
        alt = cloover_api.kl_typ(session)
        if typ not in cloover_api.ASSET_TYPEN_API:
            fehler.append(f"Anlagentyp Klima: „{typ}“ ist kein Cloover-Anlagentyp.")
        elif typ != alt:
            einstellung_setzen(session, "cloover_kl_typ", typ)
            aenderungen.append(f"cloover_kl_typ: {alt} → {typ}")
    # Textbausteine (leer = Standard)
    for key in TEXT_FELDER:
        if key in form:
            neu = (form.get(key) or "").strip().replace("\r\n", "\n")
            war_standard = cloover_texte.ist_standard(session, key)
            alt_text = cloover_texte.text_holen(session, key)
            gespeichert = cloover_texte.text_setzen(session, key, neu)
            jetzt_standard = gespeichert == ""
            if (war_standard, alt_text) != (jetzt_standard, cloover_texte.text_holen(session, key)):
                aenderungen.append(f"{key}: {'Standard' if war_standard else 'eigener Text'} → "
                                   f"{'Standard' if jetzt_standard else 'eigener Text (' + str(len(gespeichert)) + ' Zeichen)'}")
    cloover_api.protokollieren(session, benutzer, aenderungen)
    meldung = "Cloover-Einstellungen gespeichert." if aenderungen else "Keine Änderungen."
    if fehler:
        meldung = " ".join(fehler) + (" Übrige Änderungen gespeichert." if aenderungen else " Nichts geändert.")
    return meldung, fehler


@router.get("/cloover")
def cloover_seite(request: Request, session: Session = Depends(get_session)):
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    werte = _werte(session)
    return render(request, "konfiguration/cloover.html", aktiv="/parametrierung",
                  key_gesetzt=cloover_api.konfiguriert(),
                  basis_url=cloover_api.basis_url(), ist_test_url=cloover_api.ist_test_url(),
                  test_url=cloover_api.TEST_URL, werte=werte, modi=cloover_api.MODI,
                  optionen_api=cloover_api.OPTIONEN_API, asset_typen_api=cloover_api.ASSET_TYPEN_API,
                  asset_typen=cloover_api.ASSET_TYPEN, sparten_namen=cloover_api.SPARTEN_NAMEN,
                  sparten_reihenfolge=cloover_api.SPARTEN_REIHENFOLGE,
                  laufzeit_min_api=cloover_api.LAUFZEIT_MIN_API, laufzeit_max_api=cloover_api.LAUFZEIT_MAX_API,
                  texte={key: {"text": cloover_texte.text_holen(session, key),
                               "standard": cloover_texte.standard(key),
                               "ist_standard": cloover_texte.ist_standard(session, key)}
                         for key in TEXT_FELDER},
                  platzhalter=cloover_texte.PLATZHALTER, hinweis_entwurf=cloover_texte.HINWEIS_ENTWURF,
                  letzter_test=cloover_api.letzter_test(session),
                  protokoll=cloover_api.protokoll(session),
                  # Phase 194 (Agent B3): Kontext des Partials _cloover_ablage.html aus der Request-Sitzung –
                  # POST/Test leiten hierher um, der Jinja-Global-Rückfall des Partials bleibt ungenutzt
                  ablage=cloover_pdf_ablage.seiten_kontext(session),
                  meldung=request.query_params.get("meldung", ""),
                  test=request.query_params.get("test", ""))


@router.post("/cloover")
def cloover_speichern(request: Request, session: Session = Depends(get_session)):
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    meldung, _fehler = _speichern(session, form, request.state.benutzer)
    session.commit()
    return _zurueck(meldung)


@router.post("/cloover/test")
def cloover_verbindung_testen(request: Request, session: Session = Depends(get_session)):
    """Knopf „Verbindung testen“: Formularstand zuerst übernehmen, dann v1-Beispielrate + v2-Probe je
    Sparte (cloover_api.verbindung_testen). Netz-I/O nur nach verbindung_freigeben (v27-Regel)."""
    if (umleitung := _nur_admin(request)) is not None:
        return umleitung
    form = anfrage.formular(request)
    meldung, fehler = _speichern(session, form, request.state.benutzer)
    session.commit()
    verbindung_freigeben(session)
    _ok, text = cloover_api.verbindung_testen(session)
    session.commit()
    return _zurueck(meldung if fehler else "", text, "#zugang")
