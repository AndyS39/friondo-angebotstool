# REST-Eingang POST /api/leads (v12, Phase 75): Auth über X-Api-Key
# (Schlüssel je Quelle in der Parametrierung), Rate-Limit 60/min.
# Antworten: 201 angelegt, 409 an offenen Vorgang angehängt (mit ID),
# 422 fehlende Pflichtfelder, 401 falscher Schlüssel, 429 Limit.
# Doku mit curl-Beispiel: docs/leads-api.md

import time
from collections import deque

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import leadmanagement as kern
from app.db import get_session
from app.models import Kampagne, LeadQuelle

router = APIRouter(prefix="/api/leads")

_aufrufe: dict[str, deque] = {}
RATE_LIMIT = 60   # Aufrufe je Minute je Schlüssel


def _rate_ok(schluessel: str) -> bool:
    jetzt = time.monotonic()
    fenster = _aufrufe.setdefault(schluessel, deque())
    while fenster and jetzt - fenster[0] > 60:
        fenster.popleft()
    if len(fenster) >= RATE_LIMIT:
        return False
    fenster.append(jetzt)
    return True


@router.post("")
async def lead_anlegen(request: Request, session: Session = Depends(get_session)):
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
        daten = await request.json()
        assert isinstance(daten, dict)
    except Exception:
        return JSONResponse({"fehler": "Rumpf muss ein JSON-Objekt sein"},
                            status_code=422)

    # Bugfix 30.09.2026: Agenturen senden PLZ/Telefon oft als Zahl und Sparten
    # als Text – vorher 500 (int hat kein .strip / ist nicht iterierbar)
    for feld in ("anrede", "vorname", "nachname", "strasse", "plz", "ort", "telefon",
                 "email", "nachricht", "quelle", "kampagne", "utm_source", "utm_medium",
                 "utm_campaign", "utm_content"):
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
    fehlend = []
    if not (daten.get("nachname") or "").strip():
        fehlend.append("nachname")
    if not (daten.get("plz") or "").strip():
        fehlend.append("plz")
    if not (daten.get("telefon") or "").strip() and not (daten.get("email") or "").strip():
        fehlend.append("telefon oder email")
    sparten = [str(s).strip().upper() for s in (daten.get("sparten") or [])
               if str(s).strip().upper() in ("WP", "PV", "KL", "WB")]
    if not sparten:
        fehlend.append("sparten (WP/PV/KL/WB)")
    if fehlend:
        return JSONResponse({"fehler": "Pflichtfelder fehlen",
                             "felder": fehlend}, status_code=422)

    # Quelle im Rumpf darf die Schlüssel-Quelle präzisieren (gleicher
    # Betreiber); v21 (Phase 87): unbekannte Keys/Kampagnen legen sich an,
    # utm_campaign ordnet die Kampagne zu
    quelle, kampagne_id = kern.quelle_kampagne_aufloesen(
        session, str(daten.get("quelle") or ""), str(daten.get("kampagne") or ""),
        str(daten.get("utm_campaign") or ""), standard_quelle=quelle)

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
    vorgang, status = kern.lead_anlegen(session, eingabe, quelle, "api",
                                        kampagne_id=kampagne_id)
    session.commit()
    if status == "angehaengt":
        return JSONResponse({"vorgang_id": vorgang.id, "status": status,
                             "hinweis": "An offenen Vorgang angehängt "
                                        "(Duplikat)"}, status_code=409)
    return JSONResponse({"vorgang_id": vorgang.id, "status": status},
                        status_code=201)
