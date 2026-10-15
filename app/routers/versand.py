# Versand-Verwaltung (Phase 17) → v33 (PLAN_V20 Phase 166): Verbindungs-Seite zu
# Microsoft 365 (Graph). Zeigt Modus (Anwendung | Delegiert) mit Grund, Mandant
# (maskiert), Ablauf des Geheimnisses, letzte erfolgreiche Aufrufe je Postfach, die
# Liste aller Postfächer, die das Tool braucht (Funktionspostfächer aus den Parametern +
# Mitarbeiter mit Terminen) zum Abgleich mit der Exchange-Zugriffsgruppe
# Friondo-Tool-Zugriff (Kopierliste für die IT), das Ergebnis des Verbindungstests und –
# als Rückfallebene – weiter die Microsoft-Anmeldung einer Person per Device-Code
# (Modus delegiert). Alle Routen `def`; Netzaufrufe (Verbindungstest, msal) erst nach
# verbindung_freigeben(session) (v27).

from datetime import datetime
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import config, graph_versand
from app.db import get_session, verbindung_freigeben
from app.templating import render

router = APIRouter(prefix="/versand")


def _ohne_zugriff(session) -> list[dict]:
    """Vertrag O → G: outlook_sync.postfaecher_ohne_zugriff(session) → [dict(benutzer_id,
    name, postfach, zeit)] – Personen mit Terminen, deren Postfach beim letzten Outlook-
    Lauf 403 lieferte. getattr-Rückfall leer, solange Agent O die Funktion nicht liefert."""
    try:
        from app import outlook_sync
    except ImportError:
        return []
    funktion = getattr(outlook_sync, "postfaecher_ohne_zugriff", None)
    if funktion is None:
        return []
    try:
        return [dict(e) for e in (funktion(session) or [])]
    except Exception:   # noqa: BLE001 – die Verbindungs-Seite rendert immer
        return []


def _zeit_text(wert) -> str:
    if not wert:
        return ""
    if isinstance(wert, (int, float)):
        wert = datetime.fromtimestamp(wert)
    if isinstance(wert, datetime):
        return wert.strftime("%d.%m.%Y %H:%M")
    return str(wert)


def seite_daten(session) -> dict:
    """Alle Werte der Verbindungs-Seite aus der Datenbank (kein Netz) – auch für Tests."""
    letzter = graph_versand.letzter_test(session)
    postfaecher = graph_versand.benoetigte_postfaecher(session)
    ohne_zugriff = _ohne_zugriff(session)
    modus = graph_versand.modus(session)
    grund = graph_versand.modus_grund(session)
    if (letzter is not None and not letzter.get("gruen") and modus != graph_versand.MODUS_ANWENDUNG
            and graph_versand.anwendung_konfiguriert()):
        grund = (f"Verbindungstest vom {_zeit_text(letzter.get('zeit_dt'))} nicht grün – "
                 "Funktionspostfächer in die Zugriffsgruppe aufnehmen und erneut testen")
    erfolge = graph_versand.letzte_erfolge()
    verweigert = dict(graph_versand.zugriff_verweigert_liste())
    je_postfach = letzter["je_postfach"] if letzter else {}
    fehlend: dict[str, str] = {}
    for eintrag in postfaecher:
        schluessel = eintrag["postfach"].lower()
        eintrag["erfolg_text"] = _zeit_text(erfolge.get(schluessel))
        eintrag["verweigert_text"] = _zeit_text(verweigert.get(schluessel))
        test = je_postfach.get(schluessel)
        eintrag["test_ok"] = test["ok"] if test else None
        eintrag["test_grund"] = (test["grund"] if test else "") or ""
        if test is not None and not test["ok"]:
            fehlend[schluessel] = eintrag["test_grund"]
        elif schluessel in verweigert:
            fehlend[schluessel] = f"HTTP 403 am {eintrag['verweigert_text']} – nicht in der Zugriffsgruppe"
    for schluessel, zeit in verweigert.items():
        if schluessel not in fehlend and schluessel not in {e["postfach"].lower() for e in postfaecher}:
            fehlend[schluessel] = f"HTTP 403 am {_zeit_text(zeit)} – nicht in der Zugriffsgruppe"
    for person in ohne_zugriff:
        adresse = str(person.get("postfach") or "").strip().lower()
        if adresse and adresse not in fehlend:
            fehlend[adresse] = (f"Outlook-Lauf: {person.get('name') or ''} – nicht in der "
                                f"Zugriffsgruppe ({_zeit_text(person.get('zeit'))})").strip()
    funktion = [e for e in postfaecher if e["art"] == graph_versand.ART_FUNKTIONSPOSTFACH]
    mitarbeiter = [e for e in postfaecher if e["art"] == graph_versand.ART_MITARBEITER]
    return {
        "modus": modus, "modus_name": graph_versand.modus_name(modus), "modus_grund": grund,
        "anwendung_konfiguriert": graph_versand.anwendung_konfiguriert(),
        "mandant": graph_versand.mandant_maskiert(),
        "client_id_gesetzt": bool(config.GRAPH_CLIENT_ID),
        "geheimnis_gesetzt": bool(config.GRAPH_CLIENT_SECRET),
        "zertifikat_gesetzt": bool(config.GRAPH_ZERTIFIKAT_PFAD),
        "geheimnis_ablauf": graph_versand.geheimnis_ablauf_datum(),
        "geheimnis_tage": graph_versand.geheimnis_ablauf_tage(),
        "geheimnis_warnung": graph_versand.geheimnis_warnung(),
        "zugriffsgruppe": graph_versand.ZUGRIFFSGRUPPE,
        "zugriffsgruppe_adresse": graph_versand.ZUGRIFFSGRUPPE_ADRESSE,
        "letzter_test": letzter, "letzter_test_zeit": _zeit_text(letzter.get("zeit_dt")) if letzter else "",
        "postfaecher": postfaecher, "funktionspostfaecher": funktion, "mitarbeiter": mitarbeiter,
        "kopierliste": "\n".join(e["postfach"] for e in postfaecher),
        "fehlend": [{"postfach": k, "grund": v} for k, v in sorted(fehlend.items())],
        "fehlend_liste": "\n".join(sorted(fehlend)),
        "ohne_zugriff": ohne_zugriff,
    }


@router.get("")
def status(request: Request, session: Session = Depends(get_session)):
    daten = seite_daten(session)
    # Hotfix-Muster (v27): Verbindung vor Netz-I/O freigeben – msal kann beim Lesen des
    # angemeldeten Kontos (Modus delegiert) das Token über das Netz erneuern
    verbindung_freigeben(session)
    konto = graph_versand.delegiertes_konto() if daten["client_id_gesetzt"] else None
    return render(request, "versand/status.html", aktiv="/versand",
                  konfiguriert=graph_versand.konfiguriert(),
                  konto=konto,
                  flow=graph_versand.anmeldestatus(),
                  meldung=request.query_params.get("meldung", ""),
                  **daten)


@router.post("/test")
def verbindung_testen(request: Request, session: Session = Depends(get_session)):
    """Knopf „Verbindung testen“: je Funktionspostfach ein Ordner, je Mitarbeiter ein
    Kalender (graph_versand.verbindungstest gibt die Sitzung vor den Netzaufrufen frei);
    alle Funktionspostfächer grün → Modus anwendung, sonst delegiert. Ergebnis bleibt in
    der Einstellung graph_letzter_test und erscheint nach der Umleitung in der Liste."""
    if not graph_versand.konfiguriert():
        return RedirectResponse("/versand?meldung=" + quote_plus(
            "Microsoft Graph ist nicht eingerichtet (GRAPH_CLIENT_ID fehlt in der .env)."),
            status_code=303)
    ergebnisse = graph_versand.verbindungstest(session)
    gruen = sum(1 for e in ergebnisse if e["ok"])
    modus = graph_versand.modus(session)
    meldung = (f"Verbindungstest: {gruen} von {len(ergebnisse)} Postfächern erreichbar – "
               f"Modus {graph_versand.modus_name(modus)}.")
    if gruen < len(ergebnisse):
        rot = [e for e in ergebnisse if not e["ok"]]
        meldung += (f" {len(rot)} rot: " + "; ".join(f"{e['postfach']} ({e['grund']})" for e in rot[:3])
                    + (" …" if len(rot) > 3 else "") + " – Kopierliste für die IT unten.")
    return RedirectResponse("/versand?meldung=" + quote_plus(meldung), status_code=303)


@router.post("/anmelden")
def anmelden():
    graph_versand.anmeldung_starten()
    return RedirectResponse("/versand", status_code=303)


@router.post("/abmelden")
def abmelden():
    graph_versand.abmelden()
    return RedirectResponse("/versand?meldung=Abgemeldet", status_code=303)
