# Mail-Parser des Lead-Managements (v12, Phase 75): Parser-Regeln (zeilen /
# html_tabelle / json) gegen Betreff+Body, Standardregel „Formular-Standard“
# ([LEAD] <quelle> <kampagne> + Feld: Wert), Postfach-Abruf über Graph alle
# 2 Minuten – NUR bei parser_modus = an (Standard aus). Nicht erkannte Mails
# landen in „Posteingang unklar“. Fehler blockieren nie.

import json
import re
import threading
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (Kampagne, LeadPosteingang, LeadQuelle, ParserRegel,
                        Vorgang)

# Feldnamen der API/des Formular-Standards → Lead-Felder (Kleinschreibung)
STANDARD_FELDER = {
    "anrede": "anrede", "vorname": "vorname", "nachname": "nachname",
    "name": "nachname", "straße": "strasse", "strasse": "strasse",
    "plz": "plz", "ort": "ort", "telefon": "telefon", "e-mail": "email",
    "email": "email", "sparte": "sparten", "sparten": "sparten",
    "wunschzeit": "wunschzeiten", "wunschzeiten": "wunschzeiten",
    "nachricht": "nachricht", "utm_source": "utm_source",
    "utm_medium": "utm_medium", "utm_campaign": "utm_campaign",
    "utm_content": "utm_content", "einwilligung_werbung": "einwilligung_werbung",
}

_SPARTEN_ALIAS = {"wp": "WP", "wärmepumpe": "WP", "waermepumpe": "WP",
                  "pv": "PV", "photovoltaik": "PV", "kl": "KL", "klima": "KL",
                  "wb": "WB", "wallbox": "WB"}


def standardregel_anlegen(session: Session) -> bool:
    """Regel „Formular-Standard“ (Betreff [LEAD] <quelle> <kampagne>,
    Body Feld: Wert) – idempotent für migrate.py."""
    if session.query(ParserRegel).filter(
            ParserRegel.name == "Formular-Standard").count():
        return False
    session.add(ParserRegel(
        name="Formular-Standard", quelle_id=None, absender_muster="",
        betreff_muster=r"^\[LEAD\]", format="zeilen",
        feldzuordnung=json.dumps(STANDARD_FELDER, ensure_ascii=False),
        aktiv=True))
    session.flush()
    return True


def regel_finden(session: Session, absender: str, betreff: str) -> ParserRegel | None:
    for regel in (session.query(ParserRegel)
                  .filter(ParserRegel.aktiv.is_(True)).order_by(ParserRegel.id)):
        if regel.absender_muster:
            try:
                if not re.search(regel.absender_muster, absender or "",
                                 re.IGNORECASE):
                    continue
            except re.error:
                continue
        if regel.betreff_muster:
            try:
                if not re.search(regel.betreff_muster, betreff or "",
                                 re.IGNORECASE):
                    continue
            except re.error:
                continue
        if regel.absender_muster or regel.betreff_muster:
            return regel
    return None


def _html_zu_paaren(body: str) -> dict[str, str]:
    """2-spaltige HTML-Tabelle → {feld: wert} (bewusst einfach, kein Parser-Baum)."""
    paare: dict[str, str] = {}
    for zeile in re.findall(r"<tr[^>]*>(.*?)</tr>", body or "",
                            re.IGNORECASE | re.DOTALL):
        zellen = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", zeile,
                            re.IGNORECASE | re.DOTALL)
        if len(zellen) >= 2:
            feld = re.sub(r"<[^>]+>", "", zellen[0]).strip()
            wert = re.sub(r"<[^>]+>", "", zellen[1]).strip()
            if feld:
                paare[feld] = wert
    return paare


def _zeilen_zu_paaren(body: str) -> dict[str, str]:
    paare: dict[str, str] = {}
    for zeile in (body or "").splitlines():
        if ":" not in zeile:
            continue
        feld, wert = zeile.split(":", 1)
        feld = feld.strip()
        if feld and len(feld) <= 40:
            paare[feld] = wert.strip()
    return paare


def _sparten_liste(wert) -> list[str]:
    if isinstance(wert, list):
        roh = [str(w) for w in wert]
    else:
        roh = re.split(r"[,;|/]", str(wert or ""))
    sparten = []
    for eintrag in roh:
        schluessel = eintrag.strip().lower()
        sparte = _SPARTEN_ALIAS.get(schluessel, eintrag.strip().upper()
                                    if eintrag.strip().upper() in ("WP", "PV", "KL", "WB")
                                    else "")
        if sparte and sparte not in sparten:
            sparten.append(sparte)
    return sparten


def mail_parsen(regel: ParserRegel, betreff: str, body: str) -> dict:
    """Erkannte Lead-Felder einer Mail (ohne Anlage – auch für die
    Test-Funktion in der Parametrierung)."""
    try:
        zuordnung = json.loads(regel.feldzuordnung or "{}")
    except ValueError:
        zuordnung = {}
    if regel.format == "json":
        try:
            treffer = re.search(r"\{.*\}", body or "", re.DOTALL)
            roh = json.loads(treffer.group(0)) if treffer else {}
        except ValueError:
            roh = {}
        paare = {str(k): v for k, v in roh.items()} if isinstance(roh, dict) else {}
    elif regel.format == "html_tabelle":
        paare = _html_zu_paaren(body)
    else:
        paare = _zeilen_zu_paaren(body)

    daten: dict = {"rohdaten": paare}
    for feld, wert in paare.items():
        ziel = zuordnung.get(feld) or zuordnung.get(feld.lower()) \
               or STANDARD_FELDER.get(feld.lower())
        if not ziel:
            continue
        if ziel == "sparten":
            daten["sparten"] = _sparten_liste(wert)
        elif ziel == "wunschzeiten":
            daten["wunschzeiten"] = [w.strip() for w in
                                     re.split(r"[,;|/]", str(wert)) if w.strip()]
        elif ziel == "einwilligung_werbung":
            daten["einwilligung_werbung"] = str(wert).strip().lower() in (
                "ja", "yes", "true", "1", "x")
        else:
            daten[ziel] = str(wert).strip()
    # Formular-Standard: Quelle/Kampagne aus dem Betreff [LEAD] <quelle> <kampagne>
    treffer = re.match(r"^\[LEAD\]\s*(\S+)?\s*(\S+)?", betreff or "")
    if treffer:
        if treffer.group(1):
            daten.setdefault("quelle_key", treffer.group(1).strip().lower())
        if treffer.group(2):
            daten.setdefault("kampagne_name", treffer.group(2).strip())
    return daten


def mail_verarbeiten(session: Session, graph_id: str, absender: str,
                     betreff: str, body: str,
                     empfangen_am: datetime | None = None) -> str:
    """Eine Mail → Lead (erkannt) oder „Posteingang unklar“. Liefert
    'lead' | 'unklar' | 'bekannt' (Duplikat der graph_id)."""
    from app import leadmanagement as kern
    if (session.query(LeadPosteingang)
            .filter(LeadPosteingang.graph_id == graph_id).count()):
        return "bekannt"
    regel = regel_finden(session, absender, betreff)
    daten = mail_parsen(regel, betreff, body) if regel is not None else {}
    if regel is not None and (daten.get("nachname") or daten.get("telefon")
                              or daten.get("email")):
        regel.zuletzt_getroffen_am = datetime.now()
        quelle = None
        if daten.get("quelle_key"):
            quelle = (session.query(LeadQuelle)
                      .filter(LeadQuelle.key == daten["quelle_key"]).first())
        if quelle is None and regel.quelle_id:
            quelle = session.get(LeadQuelle, regel.quelle_id)
        kampagne_id = None
        if daten.get("kampagne_name"):
            kampagne = (session.query(Kampagne)
                        .filter(Kampagne.name == daten["kampagne_name"]).first())
            kampagne_id = kampagne.id if kampagne else None
        daten.setdefault("nachricht", "")
        daten["nachricht"] = (daten.get("nachricht") or body or "")[:4000]
        vorgang, _ = kern.lead_anlegen(session, daten, quelle, "mail")
        session.add(LeadPosteingang(graph_id=graph_id, absender=absender,
                                    betreff=betreff, body=(body or "")[:8000],
                                    empfangen_am=empfangen_am,
                                    status="angelegt", vorgang_id=vorgang.id))
        session.commit()
        return "lead"
    session.add(LeadPosteingang(graph_id=graph_id, absender=absender,
                                betreff=betreff, body=(body or "")[:8000],
                                empfangen_am=empfangen_am, status="offen"))
    session.commit()
    return "unklar"


def postfach_abrufen(session: Session) -> dict:
    """Ungelesene Mails aus dem Postfach absender_postfach (Graph) – nur bei
    parser_modus = an; best effort, nie blockierend."""
    from app import graph_versand
    from app import leadmanagement as kern
    if kern.parameter_holen(session, "parser_modus", "aus") != "an":
        return {"uebersprungen": True}
    token = graph_versand._token()
    if token is None:
        return {"fehler": "Nicht bei Microsoft angemeldet"}
    postfach = kern.parameter_holen(session, "absender_postfach",
                                    "leads@friondo.de")
    ergebnis = {"leads": 0, "unklar": 0}
    try:
        antwort = graph_versand._graph_aufruf(
            "GET", f"/users/{postfach}/mailFolders/inbox/messages"
                   "?$top=20&$filter=isRead eq false"
                   "&$select=id,subject,from,receivedDateTime,body", token)
        for nachricht in antwort.get("value", []):
            graph_id = nachricht.get("id", "")
            absender = (nachricht.get("from", {}).get("emailAddress", {})
                        .get("address", ""))
            betreff = nachricht.get("subject", "") or ""
            body = (nachricht.get("body", {}) or {}).get("content", "") or ""
            status = mail_verarbeiten(session, graph_id, absender, betreff, body)
            if status == "lead":
                ergebnis["leads"] += 1
            elif status == "unklar":
                ergebnis["unklar"] += 1
            try:   # als gelesen markieren, damit sie nicht erneut kommt
                graph_versand._graph_aufruf(
                    "PATCH", f"/users/{postfach}/messages/{graph_id}", token,
                    {"isRead": True})
            except Exception:
                pass
    except Exception as problem:
        ergebnis["fehler"] = str(problem)
    return ergebnis


_scheduler_laeuft = False


def scheduler_starten() -> None:
    """Abruf alle 2 Minuten (nur bei parser_modus = an; der Schalter wird je
    Lauf geprüft, damit das Umschalten ohne Neustart wirkt)."""
    global _scheduler_laeuft
    if _scheduler_laeuft:
        return
    _scheduler_laeuft = True

    def schleife():
        import time

        from app.db import SessionLocal
        time.sleep(240)
        while True:
            try:
                session = SessionLocal()
                try:
                    postfach_abrufen(session)
                finally:
                    session.close()
            except Exception:
                pass
            time.sleep(120)

    threading.Thread(target=schleife, daemon=True, name="lead-parser").start()
