# REST-Eingang POST /api/leads (v12, Phase 75): Auth über X-Api-Key
# (Schlüssel je Quelle in der Parametrierung), Rate-Limit 60/min.
# Antworten: 201 angelegt, 409 an offenen Vorgang angehängt (mit ID),
# 422 fehlende Pflichtfelder, 401 falscher Schlüssel, 429 Limit.
# Doku mit curl-Beispiel: docs/leads-api.md
#
# v23 (PLAN_LEAD_V2 Phase 111, I4/I5, A-8):
# - Sparte GW (Gewerbe) zulässig; fehlen Sparten, gelten lead_quellen.
#   standard_sparten der Quelle (sonst wie bisher 422).
# - Optionales Feld veranstaltung (YYYY-MM-DD) → Info-Veranstaltung am selben
#   Tag, sonst 422 mit den nächsten Terminen. Ohne Feld ordnet eine Quelle vom
#   Typ veranstaltung (Key info_veranstaltung) die nächste Veranstaltung ab
#   Eingang + info_vorlauf_tage zu (A-8 [OFFEN 1]).
# - Info-Leads werden IMMER als eigener Vorgang angelegt (kein Anhängen, kein
#   409); Abgleich I5 ((E-Mail ODER Telefon E.164) UND Nachname) schreibt eine
#   Aktivität „Kunde bereits im System: Vorgang #…“ (roter Hinweis im Board).
#   Die bestehende Duplikatprüfung (kern.duplikat_pruefen, 409) bleibt für
#   alle anderen Quellen unverändert.
# - 201 enthält zusätzlich veranstaltung (Datum oder null) und hinweis_bestand.

import re
import time
from collections import deque

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import lead_info
from app import leadmanagement as kern
from app.db import get_session
from app.models import Kampagne, LeadQuelle
from app import anfrage   # v27: Formular/JSON in def-Routen

router = APIRouter(prefix="/api/leads")

_aufrufe: dict[str, deque] = {}
RATE_LIMIT = 60   # Aufrufe je Minute je Schlüssel
SPARTEN_API = ("WP", "PV", "KL", "WB", "GW")
# Aliase der Agenturen (Formular-Standard): Klartext → Code
SPARTEN_ALIAS = {"WAERMEPUMPE": "WP", "WÄRMEPUMPE": "WP", "PHOTOVOLTAIK": "PV", "SOLAR": "PV",
                 "KLIMA": "KL", "KLIMAANLAGE": "KL", "WALLBOX": "WB", "GEWERBE": "GW",
                 "GEWERBLICH": "GW"}


def _rate_ok(schluessel: str) -> bool:
    jetzt = time.monotonic()
    fenster = _aufrufe.setdefault(schluessel, deque())
    while fenster and jetzt - fenster[0] > 60:
        fenster.popleft()
    if len(fenster) >= RATE_LIMIT:
        return False
    fenster.append(jetzt)
    return True


def _sparten_lesen(werte) -> list[str]:
    ergebnis = []
    for s in werte or []:
        code = str(s).strip().upper()
        code = SPARTEN_ALIAS.get(code, code)
        if code in SPARTEN_API and code not in ergebnis:
            ergebnis.append(code)
    return ergebnis


def _standard_sparten(quelle: LeadQuelle | None) -> list[str]:
    """lead_quellen.standard_sparten (JSON-Liste) – gilt, wenn keine Sparte mitkommt."""
    import json
    if quelle is None:
        return []
    try:
        werte = json.loads(quelle.standard_sparten or "[]")
    except ValueError:
        werte = []
    return _sparten_lesen(werte if isinstance(werte, list) else [])


def _quelle_vorab(session: Session, quelle_key: str, schluessel_quelle: LeadQuelle) -> LeadQuelle:
    """Quelle für Standard-Sparten/Info-Erkennung VOR der Anlage bestimmen –
    ohne Auto-Anlage (die macht quelle_kampagne_aufloesen nach der Prüfung)."""
    key = re.sub(r"[^a-z0-9_-]", "_", (quelle_key or "").strip().lower())[:100]
    if key:
        treffer = session.query(LeadQuelle).filter(LeadQuelle.key == key).first()
        if treffer is not None:
            return treffer
    return schluessel_quelle


@router.post("")
def lead_anlegen(request: Request, session: Session = Depends(get_session)):
    schluessel = request.headers.get("X-Api-Key", "").strip()
    quelle = None
    if schluessel:
        quelle = (session.query(LeadQuelle)
                  .filter(LeadQuelle.api_key == schluessel,
                          LeadQuelle.aktiv.is_(True)).first())
    if quelle is None:
        return JSONResponse({"fehler": "Ungültiger oder fehlender X-Api-Key"},
                            status_code=401)
    if not _rate_ok(schluessel):
        return JSONResponse({"fehler": "Rate-Limit erreicht (60/min)"},
                            status_code=429)
    try:
        daten = anfrage.json_lesen(request)
        assert isinstance(daten, dict)
    except Exception:
        return JSONResponse({"fehler": "Rumpf muss ein JSON-Objekt sein"},
                            status_code=422)

    # Bugfix 30.09.2026: Agenturen senden PLZ/Telefon oft als Zahl und Sparten
    # als Text – vorher 500 (int hat kein .strip / ist nicht iterierbar)
    for feld in ("anrede", "vorname", "nachname", "strasse", "plz", "ort", "telefon",
                 "email", "nachricht", "quelle", "kampagne", "utm_source", "utm_medium",
                 "utm_campaign", "utm_content", "veranstaltung", "firma"):
        wert = daten.get(feld)
        if wert is not None and not isinstance(wert, str):
            daten[feld] = "" if isinstance(wert, (dict, list, bool)) else str(wert)
    for feld in ("sparten", "wunschzeiten"):
        wert = daten.get(feld)
        if isinstance(wert, str):
            daten[feld] = [t.strip() for t in wert.replace(";", ",").split(",") if t.strip()]
        elif not isinstance(wert, list):
            daten[feld] = []
    if len(str(daten.get("plz") or "")) == 4 and str(daten["plz"]).isdigit():
        daten["plz"] = "0" + str(daten["plz"])   # führende Null ging als Zahl verloren

    # v23: Quelle vorab (ohne Anlage) für Standard-Sparten und Info-Erkennung
    quelle_vorab = _quelle_vorab(session, str(daten.get("quelle") or ""), quelle)
    sparten = _sparten_lesen(daten.get("sparten") or [])
    sparten_aus_quelle = False
    if not sparten:
        sparten = _standard_sparten(quelle_vorab)
        sparten_aus_quelle = bool(sparten)

    fehlend = []
    if not (daten.get("nachname") or "").strip():
        fehlend.append("nachname")
    if not (daten.get("plz") or "").strip():
        fehlend.append("plz")
    if not (daten.get("telefon") or "").strip() and not (daten.get("email") or "").strip():
        fehlend.append("telefon oder email")
    if not sparten:
        fehlend.append("sparten (WP/PV/KL/WB/GW)")
    if fehlend:
        return JSONResponse({"fehler": "Pflichtfelder fehlen",
                             "felder": fehlend}, status_code=422)

    # v23 (I4): optionales Feld veranstaltung (YYYY-MM-DD) → Veranstaltung am
    # selben Tag, sonst 422 mit den nächsten Terminen
    veranstaltung = None
    veranstaltung_text = (daten.get("veranstaltung") or "").strip()
    if veranstaltung_text:
        tag = lead_info.datum_lesen(veranstaltung_text)
        if tag is None:
            return JSONResponse({"fehler": "veranstaltung: Datum im Format YYYY-MM-DD erwartet",
                                 "felder": ["veranstaltung"]}, status_code=422)
        try:
            lead_info.veranstaltungen_anlegen(session)
        except Exception:
            session.rollback()
        veranstaltung = lead_info.veranstaltung_am_tag(session, tag)
        if veranstaltung is None:
            return JSONResponse({
                "fehler": f"Keine Info-Veranstaltung am {tag.strftime('%d.%m.%Y')}",
                "felder": ["veranstaltung"],
                "naechste_termine": [v.beginn.strftime("%Y-%m-%d") for v in lead_info.kommende(session)],
            }, status_code=422)

    # Quelle im Rumpf darf die Schlüssel-Quelle präzisieren (gleicher
    # Betreiber); v21 (Phase 87): unbekannte Keys/Kampagnen legen sich an,
    # utm_campaign ordnet die Kampagne zu
    quelle, kampagne_id = kern.quelle_kampagne_aufloesen(
        session, str(daten.get("quelle") or ""), str(daten.get("kampagne") or ""),
        str(daten.get("utm_campaign") or ""), standard_quelle=quelle)
    info_lead = veranstaltung is not None or lead_info.ist_info_quelle(quelle)

    eingabe = {
        "anrede": str(daten.get("anrede") or "").strip(),
        "vorname": str(daten.get("vorname") or "").strip(),
        "nachname": str(daten.get("nachname") or "").strip(),
        "strasse": str(daten.get("strasse") or "").strip(),
        "plz": str(daten.get("plz") or "").strip(),
        "ort": str(daten.get("ort") or "").strip(),
        "telefon": str(daten.get("telefon") or "").strip(),
        "email": str(daten.get("email") or "").strip(),
        "sparten": sparten,
        "wunschzeiten": [str(w) for w in (daten.get("wunschzeiten") or [])],
        "nachricht": str(daten.get("nachricht") or "").strip(),
        "utm_source": str(daten.get("utm_source") or "").strip(),
        "utm_medium": str(daten.get("utm_medium") or "").strip(),
        "utm_campaign": str(daten.get("utm_campaign") or "").strip(),
        "utm_content": str(daten.get("utm_content") or "").strip(),
        "einwilligung_werbung": bool(daten.get("einwilligung_werbung")),
        "einwilligung_quelle": "portal",
        "rohdaten": daten.get("rohdaten", daten),
    }
    # v23 (I5): Info-Leads immer als eigener Vorgang (kein Anhängen, kein 409);
    # Duplikat-Regel für alle anderen Quellen unverändert
    vorgang, status = kern.lead_anlegen(session, eingabe, quelle, "api",
                                        kampagne_id=kampagne_id,
                                        entscheidung="neu" if info_lead else "")
    hinweis_bestand = None
    if info_lead:
        if veranstaltung is not None:
            lead_info.veranstaltung_zuordnen(session, vorgang, veranstaltung,
                                             grund="API-Feld veranstaltung")
        else:
            veranstaltung = lead_info.zuordnen_bei_eingang(session, vorgang, quelle,
                                                           eingang=vorgang.eingang_am)
        treffer = lead_info.bestand_abgleich(
            session, telefon=eingabe["telefon"], email=eingabe["email"],
            nachname=eingabe["nachname"], ausser_vorgang_id=vorgang.id,
            ausser_kunde_id=vorgang.kunde_id)
        if treffer is not None:
            text = lead_info.bestand_hinweis_schreiben(session, vorgang, treffer)
            hinweis_bestand = {"vorgang_id": treffer["vorgang"].id,
                               "phase": treffer["vorgang"].lead_phase or "",
                               "text": text}
    session.commit()
    if status == "angehaengt":
        return JSONResponse({"vorgang_id": vorgang.id, "status": status,
                             "hinweis": "An offenen Vorgang angehängt "
                                        "(Duplikat)"}, status_code=409)
    antwort = {"vorgang_id": vorgang.id, "status": status,
               "veranstaltung": veranstaltung.beginn.strftime("%Y-%m-%d") if veranstaltung else None,
               "hinweis_bestand": hinweis_bestand}
    if sparten_aus_quelle:
        antwort["sparten"] = sparten
        antwort["hinweis"] = "Sparten aus den Standard-Sparten der Quelle übernommen"
    return JSONResponse(antwort, status_code=201)
