# v31 (PLAN_LEAD_V5): gemeinsame Helfer der Feedback-Runde 3 und die Datenmigration des
# Orchestrators (Leadmanager-Häkchen, Parameter, Samstag-Arbeitszeiten, Freischaltung).
# Modul-eigene Migrationen: app.objekte.migration_v31_objekte (Objekte),
# app.lead_mail.migration_v31_mails (Vorlagen, Kürzel → Langform, nicht_erreicht).
import json
import re
import unicodedata
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import AdProfil, Benutzer

# Phase 156: Startwerte des Häkchens „Leadmanager“ (korrigierte Schreibweisen 12.10.2026);
# Abgleich tolerant gegen Groß-/Kleinschreibung, Umlaute und Reihenfolge Vor-/Nachname
LEADMANAGER_START = ("Andreas Scheelen", "Claudia Castro", "Paula Köhler",
                     "Nikolaos Goritsas", "Ioannis Simeonidis", "Dimi Chatzis")
# Phase 159: Schalter der Testphase (Standard aus) – Lead-Einstellungen → Freischaltung
SCHALTER = {"terminierung_aktiv": "aus", "mail_versand_aktiv": "aus"}
TESTPHASE_HINWEIS = "Testphase: Terminierung noch nicht freigeschaltet"
MAILSPERRE_HINWEIS = "Testphase: Mailversand noch nicht freigeschaltet"


def _norm(text: str) -> str:
    """Kleinschreibung, Umlaute aufgelöst, nur Buchstaben – für den Namensabgleich."""
    text = (text or "").lower().replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("ae", "a").replace("oe", "o").replace("ue", "u")
    return re.sub(r"[^a-z ]+", " ", text).strip()


def _namensteile(text: str) -> set[str]:
    return {t for t in _norm(text).split() if t}


def name_passt(benutzer: Benutzer, vollname: str) -> bool:
    """Benutzer passt zum Vollnamen, wenn Vor- und Nachname (Feld vorname + name bzw.
    name allein) alle Teile des Vollnamens enthalten – Reihenfolge egal."""
    soll = _namensteile(vollname)
    ist = _namensteile(f"{benutzer.vorname or ''} {benutzer.name or ''}")
    return bool(soll) and soll <= ist


def runden_5min(wert: datetime | str | None):
    """Phase 158: Rückruf-Uhrzeit auf volle 5 Minuten runden (kaufmännisch: 14:07 → 14:05,
    14:08 → 14:10). Nimmt datetime oder „HH:MM“; gibt denselben Typ zurück."""
    if wert is None or wert == "":
        return wert
    if isinstance(wert, datetime):
        rest = wert.minute % 5
        basis = wert.replace(second=0, microsecond=0) - timedelta(minutes=rest)
        return basis + timedelta(minutes=5) if rest >= 3 else basis
    text = str(wert).strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if not m:
        return wert
    stunde, minute = int(m.group(1)), int(m.group(2))
    rest = minute % 5
    minute = minute - rest + (5 if rest >= 3 else 0)
    if minute == 60:
        stunde, minute = (stunde + 1) % 24, 0
    return f"{stunde:02d}:{minute:02d}"


def schalter(session: Session, name: str) -> bool:
    """Phase 159: terminierung_aktiv / mail_versand_aktiv (Standard aus)."""
    from app import leadmanagement as kern
    wert = (kern.parameter_holen(session, name, SCHALTER.get(name, "aus")) or "aus").strip().lower()
    return wert in ("an", "ja", "1", "true", "ein")


def terminierung_aktiv(session: Session) -> bool:
    return schalter(session, "terminierung_aktiv")


def mail_versand_aktiv(session: Session) -> bool:
    return schalter(session, "mail_versand_aktiv")


def migration_v31_lead(session: Session) -> list[str]:
    """Idempotent: Leadmanager-Häkchen für die sechs Startnamen (nicht gefundene Namen als
    Meldung), Parameter-Startwerte (Schalter aus, Langnamen, Großkunden-Farbe,
    HV-Gruppen-Mitglieder), Samstag aus den AD-Arbeitszeiten entfernen,
    lead_freigabe_modus = alle (einmalig, Marker)."""
    from app import leadmanagement as kern
    from app.models import einstellung_holen, einstellung_setzen
    meldungen: list[str] = []
    # Leadmanager-Häkchen (nur beim ersten Lauf vergeben – Marker, damit spätere
    # Abwahl durch den Admin nicht überschrieben wird)
    if einstellung_holen(session, "migration_v31_leadmanager", "") != "erledigt":
        benutzer = session.query(Benutzer).all()
        gesetzt, fehlend = [], []
        for vollname in LEADMANAGER_START:
            treffer = [b for b in benutzer if name_passt(b, vollname)]
            if not treffer:
                # zweiter Versuch: nur der Nachname (z. B. Benutzername „Goritsas“)
                nachname = vollname.split()[-1]
                treffer = [b for b in benutzer if _namensteile(nachname) <= _namensteile(b.name)]
            if not treffer:
                fehlend.append(vollname)
                continue
            for b in treffer:
                b.leadmanager = True
            gesetzt.append(f"{vollname} → {', '.join(b.name for b in treffer)}")
        meldungen.append("v31: Leadmanager-Häkchen gesetzt für " + ("; ".join(gesetzt) if gesetzt else "niemanden"))
        if fehlend:
            meldungen.append("v31: Leadmanager-Namen NICHT gefunden (Admin-To-do, Benutzerverwaltung): "
                             + ", ".join(fehlend))
        einstellung_setzen(session, "migration_v31_leadmanager", "erledigt")
    # Parameter-Startwerte
    for name, wert in (("terminierung_aktiv", "aus"), ("mail_versand_aktiv", "aus"),
                       ("sparten_langnamen", ""), ("grosskunde_farbe", ""),
                       ("hv_gruppe_simon_mitglieder", "")):
        if kern.parameter_holen(session, name, None) is None:
            kern.parameter_setzen(session, name, wert)
            meldungen.append(f"v31: Parameter {name} = {wert or '(leer)'} angelegt")
    # Phase 158: kein Samstag mehr in den AD-Arbeitszeiten
    geleert = 0
    for profil in session.query(AdProfil):
        try:
            zeiten = json.loads(profil.arbeitszeiten or "{}")
        except ValueError:
            continue
        if not isinstance(zeiten, dict):
            continue
        geaendert = False
        for key in list(zeiten):
            if str(key).lower() in ("sa", "samstag", "5", "6"):
                zeiten.pop(key)
                geaendert = True
        if geaendert:
            profil.arbeitszeiten = json.dumps(zeiten)
            geleert += 1
    if geleert:
        meldungen.append(f"v31: Samstags-Arbeitszeit bei {geleert} AD-Profil(en) entfernt")
    # Phase 159: Freischaltung – einmalig, Marker (Andreas kann danach zurückstellen)
    if einstellung_holen(session, "migration_v31_freischaltung", "") != "erledigt":
        alt = kern.parameter_holen(session, "lead_freigabe_modus", "admin")
        kern.parameter_setzen(session, "lead_freigabe_modus", "alle")
        meldungen.append(f"v31: lead_freigabe_modus = alle (vorher {alt}); Terminierung und "
                         "Mailversand bleiben gesperrt (terminierung_aktiv / mail_versand_aktiv = aus)")
        einstellung_setzen(session, "migration_v31_freischaltung", "erledigt")
    # Phase 157: Pflichtfeld Außendienst
    pflicht = kern.parameter_holen(session, "pflichtfelder", "") or ""
    if pflicht and "ad_id" not in pflicht:
        kern.parameter_setzen(session, "pflichtfelder", pflicht.rstrip("; ") + "; ad_id")
        meldungen.append("v31: Pflichtfelder um ad_id (Außendienst) ergänzt")
    session.flush()
    return meldungen
