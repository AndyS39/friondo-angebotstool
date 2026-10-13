# v32 (PLAN_V19 Phase 164): Allgemeine Kundensuche im Hauptmenü.
#
# Sucht in `kunden` nach Vorname, Nachname, „Vorname Nachname“, Firma und Ort
# (Wortanfänge, Groß-/Kleinschreibung egal) sowie nach Telefon-Endziffern (ab
# vier Ziffern, Normalisierung wie die Rufnummernsuche des Lead-Managements).
# Rechte: Admin, Innendienst und Lead-Management sehen alle Kunden; der
# Außendienst nur Kunden mit mindestens einem eigenen Vorgang (vorgaenge.ad_id);
# Montage und Projektierung haben keine Suche (403 in der Route).
# Treffer enthalten nur Name, Ort, Sparten und den Verfolgungs-Chip des jüngsten
# Vorgangs – keine Preise, kein EK, kein DB. Der Link öffnet die Vorgangsakte des
# jüngsten offenen Vorgangs, sonst die Kundenakte.
#
# Leistung: die Namenssuche grenzt in SQL zuerst über einen Bereichsvergleich auf
# den Anfangsbuchstaben ein (nutzt die Indizes ix_v32_kunden_nachname /
# ix_v32_kunden_ort aus app/db.py – ein LIKE allein würde den Index in SQLite
# nicht verwenden), filtert dann mit LIKE auf den Wortanfang und prüft die Treffer
# in Python exakt (Groß-/Kleinschreibung, Umlaute). Die Rufnummernsuche liest nur
# die Telefonspalte.
import re

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.leadmanagement import telefon_normalisieren, vorgang_offen
from app.models import Kunde, Vorgang

ROLLEN_MIT_SUCHE = ("admin", "innendienst", "leadmanagement", "aussendienst")
MIN_ZEICHEN = 2
MIN_ZIFFERN = 4            # [ANNAHME] Telefon-Endziffern ab vier Ziffern
MAX_VORSCHLAEGE = 8
MAX_SEITE = 200
_RUFNUMMER_RE = re.compile(r"^[\d\s+/().-]+$")
_OBERGRENZE = "￿"

# Texte des Verfolgungs-Chips (v32 Phase 163 liefert app/verfolgung.py; bis dahin
# bzw. als Rückfall eine lesbare Form des Schlüssels).
_VERFOLGUNG_TEXTE = {
    "bestellung_angekuendigt": "Bestellung angekündigt",
    "nachfassen": "Nachfassen",
    "abgelehnt": "Abgelehnt",
    "angebot_nachfassen": "Angebot nachfassen",
}


def darf_suchen(benutzer) -> bool:
    return bool(benutzer) and getattr(benutzer, "rolle", "") in ROLLEN_MIT_SUCHE


def ist_rufnummer(q: str) -> bool:
    """Nur Ziffern/Trennzeichen und mindestens MIN_ZIFFERN Ziffern → Rufnummernsuche."""
    return bool(_RUFNUMMER_RE.match(q or "")) and len(re.sub(r"\D", "", q or "")) >= MIN_ZIFFERN


def verfolgung_text(status: str) -> str:
    if not status:
        return ""
    try:
        from app import verfolgung   # v32 Phase 163
        text = verfolgung.status_text(status)
        if text:
            return text
    except (ImportError, AttributeError):
        pass
    return _VERFOLGUNG_TEXTE.get(status, status.replace("_", " ").capitalize())


def _varianten(token: str) -> list[str]:
    """Schreibweisen für den SQL-Vorfilter (Bereichsvergleich ist case-sensitiv)."""
    return list(dict.fromkeys([token, token.lower(), token.capitalize(), token.upper()]))


def _bereich(spalte, token: str):
    """SQL-Vorfilter: Index-Bereich auf den Anfangsbuchstaben (in allen
    Schreibweisen) plus LIKE auf den ganzen Wortanfang; die exakte Prüfung
    (auch gemischte Schreibweisen wie „McDonald“) folgt in Python."""
    erster = token[:1]
    bereich = or_(*[and_(spalte >= v, spalte < v + _OBERGRENZE) for v in _varianten(erster)])
    anfang = or_(*[spalte.like(v + "%") for v in _varianten(token)])
    return and_(bereich, anfang)


def _passt(kunde: Kunde, tokens: list[str]) -> bool:
    felder = [(kunde.nachname or "").lower(), (kunde.vorname or "").lower(),
              (kunde.firma or "").lower(), (kunde.ort or "").lower()]
    woerter = [w for feld in felder for w in feld.replace("-", " ").split()] + felder
    return all(any(w.startswith(t) for w in woerter) for t in tokens)


def _rang(kunde: Kunde, tokens: list[str]) -> tuple:
    erster = tokens[0]
    nachname = (kunde.nachname or "").lower()
    vorname = (kunde.vorname or "").lower()
    firma = (kunde.firma or "").lower()
    if nachname.startswith(erster):
        stufe = 0
    elif vorname.startswith(erster):
        stufe = 1
    elif firma.startswith(erster):
        stufe = 2
    else:
        stufe = 3
    return (stufe, nachname, vorname, kunde.id)


def _per_name(session: Session, q: str) -> list[Kunde]:
    tokens = [re.sub(r"[%_]", "", t) for t in q.lower().replace(",", " ").split()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return []
    bedingungen = []
    for t in tokens:
        bedingungen.append(or_(_bereich(Kunde.nachname, t), _bereich(Kunde.vorname, t),
                               _bereich(Kunde.firma, t), _bereich(Kunde.ort, t)))
    kandidaten = (session.query(Kunde)
                  .filter(Kunde.aktiv.is_(True), and_(*bedingungen))
                  .limit(MAX_SEITE * 4).all())
    # Doppelnamen („Müller-Lüdenscheid“) und Wortanfänge im Ort erfasst der
    # Bereichsvergleich nicht – deshalb ergänzend ein LIKE-Lauf mit Wortgrenze
    # für den ersten Token, falls der Vorfilter wenig liefert.
    if len(kandidaten) < MAX_VORSCHLAEGE:
        t = tokens[0]
        muster = [f"% {v}%" for v in _varianten(t)] + [f"%-{v}%" for v in _varianten(t)]
        zusatz = (session.query(Kunde)
                  .filter(Kunde.aktiv.is_(True),
                          or_(*[Kunde.nachname.like(m) for m in muster],
                              *[Kunde.ort.like(m) for m in muster],
                              *[Kunde.firma.like(m) for m in muster]))
                  .limit(MAX_SEITE).all())
        bekannt = {k.id for k in kandidaten}
        kandidaten += [k for k in zusatz if k.id not in bekannt]
    treffer = [k for k in kandidaten if _passt(k, tokens)]
    treffer.sort(key=lambda k: _rang(k, tokens))
    return treffer


def _per_rufnummer(session: Session, q: str) -> list[Kunde]:
    ziffern = re.sub(r"\D", "", q)
    varianten = {ziffern}
    if q.strip().startswith(("0", "+")):
        varianten.add(telefon_normalisieren(q).lstrip("+"))
    zeilen = (session.query(Kunde.id, Kunde.telefon)
              .filter(Kunde.aktiv.is_(True), Kunde.telefon != "").all())
    endet, enthaelt = [], []
    for kunde_id, telefon in zeilen:
        normal = telefon_normalisieren(telefon).lstrip("+")
        roh = re.sub(r"\D", "", telefon or "")
        if any(normal.endswith(v) or roh.endswith(v) for v in varianten if v):
            endet.append(kunde_id)
        elif any(v in normal or v in roh for v in varianten if v):
            enthaelt.append(kunde_id)
    ids = endet + enthaelt
    if not ids:
        return []
    kunden = {k.id: k for k in session.query(Kunde).filter(Kunde.id.in_(ids[:MAX_SEITE])).all()}
    return [kunden[i] for i in ids if i in kunden]


def _rechte_filter(session: Session, kunden: list[Kunde], benutzer) -> list[Kunde]:
    """Außendienst: nur Kunden mit mindestens einem eigenen Vorgang."""
    if not kunden or getattr(benutzer, "rolle", "") != "aussendienst":
        return kunden
    ids = [k.id for k in kunden]
    eigene = {z[0] for z in session.query(Vorgang.kunde_id)
              .filter(Vorgang.ad_id == benutzer.id, Vorgang.kunde_id.in_(ids)).all()}
    return [k for k in kunden if k.id in eigene]


def _treffer_aufbauen(session: Session, kunden: list[Kunde], benutzer) -> list[dict]:
    if not kunden:
        return []
    ids = [k.id for k in kunden]
    je_kunde: dict[int, list[Vorgang]] = {}
    for v in (session.query(Vorgang).filter(Vorgang.kunde_id.in_(ids))
              .order_by(Vorgang.id.desc()).all()):
        je_kunde.setdefault(v.kunde_id, []).append(v)
    aussendienst = getattr(benutzer, "rolle", "") == "aussendienst"
    treffer = []
    for k in kunden:
        vorgaenge = je_kunde.get(k.id, [])
        if aussendienst:
            vorgaenge = [v for v in vorgaenge if v.ad_id == benutzer.id]
        juengster = vorgaenge[0] if vorgaenge else None
        offen = next((v for v in vorgaenge
                      if vorgang_offen(v) and getattr(v, "archiviert_am", None) is None), None)
        if offen is not None:
            link = f"/vorgaenge/{offen.id}"
        elif aussendienst and juengster is not None:
            # [ANNAHME] Außendienst hat keine Kundenakte – jüngster eigener Vorgang
            link = f"/vorgaenge/{juengster.id}"
        else:
            link = f"/kunden/{k.id}/bearbeiten"
        status = (getattr(juengster, "verfolgung_status", "") or "") if juengster else ""
        treffer.append({
            "kunde_id": k.id,
            "name": k.anzeige_name or f"Kunde {k.id}",
            "vorname": k.vorname or "",
            "nachname": k.nachname or "",
            "firma": k.firma or "",
            "plz": k.plz or "",
            "ort": k.ort or "",
            "sparten": list(k.interessen),
            "verfolgung": status,
            "verfolgung_text": verfolgung_text(status),
            "vorgang_id": (offen or juengster).id if (offen or juengster) else None,
            "link": link,
        })
    return treffer


def suchen(session: Session, q: str, benutzer, limit: int = MAX_VORSCHLAEGE) -> list[dict]:
    """Treffer (höchstens `limit`) für den Suchbegriff `q` im Rahmen der Rechte."""
    q = " ".join((q or "").split())
    if len(q) < MIN_ZEICHEN or not darf_suchen(benutzer):
        return []
    if ist_rufnummer(q):
        kunden = _per_rufnummer(session, q)
    else:
        kunden = _per_name(session, q)
    kunden = _rechte_filter(session, kunden, benutzer)
    return _treffer_aufbauen(session, kunden[:max(1, min(limit, MAX_SEITE))], benutzer)
