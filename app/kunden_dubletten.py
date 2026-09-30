# Kunden-Dubletten zusammenführen (30.09.2026, Rückfrage 1 zum Bestandsimport):
# Gruppen gleicher Kunden über Nachname + Vorname + PLZ (derselbe Abgleich wie
# monday-Sync und Bestandsimport). Je Gruppe wählt der Admin den Haupt-
# datensatz (Vorschlag: ältester); alle Verweise der übrigen (Vorgänge,
# Angebote, Erfassungen, Leads, Projekte, Konfigurationen) wandern auf ihn,
# leere Felder des Hauptdatensatzes werden aus den Dubletten ergänzt, die
# Dubletten werden gelöscht. Jede Zusammenführung wird protokolliert.

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (Angebot, Erfassung, Konfiguration, Kunde, Lead,
                        Projekt, Vorgang, einstellung_holen, einstellung_setzen)

VERWEISE = [(Vorgang, "Vorgänge"), (Angebot, "Angebote"), (Erfassung, "Erfassungen"),
            (Lead, "Leads"), (Projekt, "Projekte"), (Konfiguration, "Konfigurationen")]
# Felder, die aus Dubletten ergänzt werden, wenn sie am Hauptdatensatz leer sind
ERGAENZEN = ("anrede", "firma", "strasse", "ort", "email", "telefon", "kunden_nr",
             "vertriebskanal")
# Standard-Anschriften nur als GANZE Gruppe übernehmen (keine Mischanschrift
# aus Name von A und Straße von B)
ANSCHRIFT_GRUPPEN = {praefix: tuple(f"{praefix}_{f}" for f in
                                    ("name", "zusatz", "strasse", "plz", "ort"))
                     for praefix in ("rechnung", "liefer")}
PROTOKOLL = "kunden_zusammenfuehrung_protokoll"


def _normal(text: str) -> str:
    from app.monday_sync import _normal as monday_normal
    return monday_normal(text or "")


def _schluessel(k: Kunde) -> tuple[str, str, str]:
    return (_normal(k.nachname), _normal(k.vorname), (k.plz or "").strip())


def verweise_zaehlen(session: Session, kunde_id: int) -> dict[str, int]:
    return {name: session.query(modell).filter(modell.kunde_id == kunde_id).count()
            for modell, name in VERWEISE}


def gruppen(session: Session) -> list[dict]:
    """Alle Dubletten-Gruppen (mind. 2 Kunden, Nachname + PLZ nicht leer).
    Hinweis „Straße abweichend“, wenn die Adressen nicht übereinstimmen –
    dann könnten es verschiedene Personen sein (bitte einzeln prüfen)."""
    from app import leadmanagement
    demo = leadmanagement.demo_kunden_ids(session)
    je_schluessel: dict[tuple, list[Kunde]] = {}
    for k in session.query(Kunde).order_by(Kunde.id):
        schluessel = _schluessel(k)
        if not schluessel[0] or not schluessel[2]:
            continue
        je_schluessel.setdefault(schluessel, []).append(k)
    ergebnis = []
    for schluessel, kunden in je_schluessel.items():
        if len(kunden) < 2:
            continue
        from app.anschriften import _norm as strasse_normal   # „Str.“ = „Straße“
        strassen = {strasse_normal(k.strasse) for k in kunden if (k.strasse or "").strip()}
        ergebnis.append({
            "schluessel": "|".join(schluessel),
            "kunden": [{"kunde": k, "verweise": verweise_zaehlen(session, k.id),
                        "demo": k.id in demo} for k in kunden],
            "vorschlag": kunden[0].id,
            "strasse_abweichend": len(strassen) > 1,
        })
    ergebnis.sort(key=lambda g: (g["strasse_abweichend"], g["kunden"][0]["kunde"].nachname.lower()))
    return ergebnis


def zusammenfuehren(session: Session, haupt_id: int, dubletten_ids: list[int],
                    benutzer=None) -> dict:
    """Verweise der Dubletten auf den Hauptdatensatz umhängen, leere Felder
    ergänzen, Interessen/Notizen mischen, Dubletten löschen, protokollieren."""
    haupt = session.get(Kunde, haupt_id)
    if haupt is None:
        raise ValueError("Hauptdatensatz nicht gefunden")
    dubletten = [session.get(Kunde, i) for i in dubletten_ids if i != haupt_id]
    dubletten = [d for d in dubletten if d is not None]
    for d in dubletten:
        if _schluessel(d) != _schluessel(haupt):
            raise ValueError(f"Kunde #{d.id} gehört nicht zur Gruppe von #{haupt.id}")
    umgehaengt: dict[str, int] = {}
    for d in dubletten:
        for modell, name in VERWEISE:
            anzahl = (session.query(modell).filter(modell.kunde_id == d.id)
                      .update({modell.kunde_id: haupt.id}, synchronize_session=False))
            umgehaengt[name] = umgehaengt.get(name, 0) + anzahl
        for feld in ERGAENZEN:
            if not (getattr(haupt, feld, "") or "").strip() and (getattr(d, feld, "") or "").strip():
                setattr(haupt, feld, getattr(d, feld))
        for felder in ANSCHRIFT_GRUPPEN.values():
            if (not any((getattr(haupt, f, "") or "").strip() for f in felder)
                    and any((getattr(d, f, "") or "").strip() for f in felder)):
                for f in felder:
                    setattr(haupt, f, getattr(d, f, "") or "")
        interessen = [s for s in (haupt.interesse or "").split(",") if s.strip()]
        for s in (d.interesse or "").split(","):
            if s.strip() and s.strip() not in interessen:
                interessen.append(s.strip())
        haupt.interesse = ",".join(interessen)
        if d.kanal_manuell and not haupt.kanal_manuell:
            haupt.kanal_manuell, haupt.vertriebskanal = True, d.vertriebskanal
        if (d.notizen or "").strip():
            haupt.notizen = ((haupt.notizen or "").rstrip() + "\n\n"
                             f"[aus Kunde #{d.id} zusammengeführt]\n{d.notizen.strip()}").strip()
        if d.aktiv and not haupt.aktiv:
            haupt.aktiv = True
    session.flush()
    for d in dubletten:
        session.delete(d)
    session.flush()
    zeile = (f"{datetime.now():%d.%m.%Y %H:%M} · {benutzer.name if benutzer else 'System'}: "
             f"#{', #'.join(str(d.id) for d in dubletten)} → #{haupt.id} "
             f"({haupt.anzeige_name}, {haupt.plz}) – "
             + ", ".join(f"{n} {name}" for name, n in umgehaengt.items() if n))
    alt = einstellung_holen(session, PROTOKOLL, "")
    einstellung_setzen(session, PROTOKOLL, (zeile + "\n" + alt)[:20000])
    return {"haupt": haupt.id, "entfernt": [d.id for d in dubletten], "umgehaengt": umgehaengt}
