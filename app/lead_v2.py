# Lead-Management V2 – gemeinsame Helfer (v23, PLAN_LEAD_V2 Phase 104).
# Hier liegt, was mehrere Fachphasen brauchen und nicht in app/leadmanagement.py
# (V1-Kern) wachsen soll: Handelsvertreter-Kennzeichen (A-1), Produktkompetenz
# (F3) mit Startwerten, Objektart-Hilfen (B3), Pflichtfelder (B2),
# benutzerindividuelle Einstellungen (A-14), Ausschlussliste (F14).

import json
import re
import unicodedata
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import AdProfil, Benutzer, BenutzerEinstellung, Kunde, Vorgang

# Produktkompetenz laut F3 (Startwerte; Pflege danach im AD-Profil durch Admin).
# Schlüssel = Namensbestandteile (klein, ohne Punkte), Wert = (Sparten, Kombi,
# MFH, Gewerbe). Abgleich über benutzer.name – Tool-Benutzer heißen z. B.
# „H. Becker“, „Detlev Burkhardt“, „K. Sarigiannis“, „R. Wilhelm“.
KOMPETENZ_START = [
    (("horst", "becker"), (["WP", "WB"], True, False, False)),
    (("detlev", "burkhardt"), (["WP", "PV", "WB"], True, False, False)),
    (("detlef", "jobelius"), (["WP", "PV", "KL", "WB"], True, False, False)),
    (("kyriakos", "sarigiannis"), (["WP", "KL", "WB"], True, True, True)),
    (("rudi", "wilhelm"), (["WP", "PV", "KL"], False, False, False)),
]

# Handelsvertreter laut G3 (Startwerte für terminiert_selbst; danach Pflege im
# AD-Profil). Abgleich über Nachnamen, Schreibweise egal (O Grady / O'Grady).
HANDELSVERTRETER_START = ["golaschewski", "grady", "di blasi", "lind",
                          "kinkel", "leinenbach"]


def _normal(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z ]", "", text.lower().replace("-", " ")).strip()


def _namensteile(name: str) -> set:
    return set(_normal(name).split())


# --- Handelsvertreter (A-1) --------------------------------------------------------

def profil_fuer(session: Session, benutzer_id: int) -> AdProfil | None:
    return (session.query(AdProfil)
            .filter(AdProfil.benutzer_id == benutzer_id).first())


def ist_handelsvertreter(session: Session, benutzer) -> bool:
    """Kennzeichen „terminiert selbst“ am AD-Profil (Hauptrolle aussendienst)."""
    if benutzer is None or benutzer.rolle != "aussendienst":
        return False
    profil = profil_fuer(session, benutzer.id)
    return bool(profil is not None and profil.terminiert_selbst)


def handelsvertreter_liste(session: Session) -> list:
    """Aktive Handelsvertreter (für Dropdowns, G3) – aus der Benutzerverwaltung."""
    ids = {p.benutzer_id for p in session.query(AdProfil)
           .filter(AdProfil.terminiert_selbst.is_(True))}
    return [b for b in session.query(Benutzer)
            .filter(Benutzer.aktiv.is_(True), Benutzer.id.in_(ids or {0}))
            .order_by(Benutzer.name)]


def hv_standard_benutzer(session: Session):
    """F13: Verantwortlicher für neue Handelsvertreter-Leads – Parameter
    hv_standard_benutzer (ID), sonst Namenssuche „Simon“ unter den HV."""
    from app import leadmanagement as kern
    wert = kern.parameter_holen(session, "hv_standard_benutzer", "").strip()
    if wert.isdigit():
        person = session.get(Benutzer, int(wert))
        if person is not None and person.aktiv:
            return person
    for hv in handelsvertreter_liste(session):
        if "simon" in _namensteile(hv.name):
            return hv
    return None


def hv_ausschluss_liste(session: Session) -> list:
    """F14: Quellen-Keys und Kanalnamen, die nicht an Handelsvertreter gehen
    (Parameter hv_ausschluss, Semikolon-Liste, klein verglichen)."""
    from app import leadmanagement as kern
    roh = kern.parameter_holen(session, "hv_ausschluss", "")
    return [t.strip().lower() for t in roh.split(";") if t.strip()]


def hv_ausgeschlossen(session: Session, vorgang: Vorgang, kunde: Kunde | None = None) -> str:
    """Leerer Text = Vergabe an HV erlaubt; sonst der treffende Ausschlussgrund."""
    from app.models import LeadQuelle
    liste = hv_ausschluss_liste(session)
    if not liste:
        return ""
    kunde = kunde or session.get(Kunde, vorgang.kunde_id)
    kanal = (kunde.vertriebskanal or "").strip().lower() if kunde else ""
    if kanal and kanal in liste:
        return f"Kanal „{kunde.vertriebskanal}“ wird nur vom Innendienst terminiert."
    quelle = session.get(LeadQuelle, vorgang.quelle_id) if vorgang.quelle_id else None
    if quelle is not None:
        for kandidat in (quelle.key, quelle.name, quelle.kanal or ""):
            if kandidat and kandidat.strip().lower() in liste:
                return f"Quelle „{quelle.name}“ wird nur vom Innendienst terminiert."
    return ""


# --- Produktkompetenz (F3) -----------------------------------------------------------

def kompetenz_sparten(profil) -> list:
    try:
        werte = json.loads(getattr(profil, "kompetenz_sparten", "[]") or "[]")
    except ValueError:
        werte = []
    return [str(w).upper() for w in werte if str(w).strip()]


def kompetenz_passt(profil, sparten: list, objektart: str | None = None) -> tuple:
    """(ok, grund): darf der AD diesen Lead? Kombi aus ≥ 2 Sparten mit WP und
    PV braucht die Kombi-Kompetenz, MFH/Gewerbe die Objektkompetenz, jede
    Sparte muss einzeln hinterlegt sein (WB ist frei, GW = Gewerbe-Kompetenz)."""
    if profil is None:
        return True, "kein AD-Profil – keine Einschränkung"
    sparten = [s.upper() for s in sparten if s]
    koennen = kompetenz_sparten(profil)
    if not koennen and not getattr(profil, "kompetenz_kombi", False):
        return True, "keine Kompetenzen gepflegt – keine Einschränkung"
    kombi = bool(getattr(profil, "kompetenz_kombi", False))
    kombi_lead = "WP" in sparten and "PV" in sparten
    if kombi_lead and not kombi:
        return False, "Kombination WP+PV nur mit Kombi-Kompetenz"
    # Kombi WP+PV(+KL) deckt PV und KL im Kombi-Lead ab, auch wenn sie einzeln
    # nicht hinterlegt sind (F3: Horst darf WP+PV(+KL), aber kein PV allein)
    gedeckt = {"WP", "PV", "KL"} if (kombi_lead and kombi) else set()
    fehlend = [s for s in sparten
               if s not in koennen and s not in ("WB", "GW") and s not in gedeckt]
    if fehlend:
        return False, "Sparte(n) " + ", ".join(fehlend) + " nicht in der Kompetenz"
    if "GW" in sparten and not getattr(profil, "kompetenz_gewerbe", False):
        return False, "Gewerbe nur mit Gewerbe-Kompetenz"
    if (objektart or "").upper() == "MFH" and not getattr(profil, "kompetenz_mfh", False):
        return False, "Mehrfamilienhaus nur mit MFH-Kompetenz"
    return True, "Kompetenz passt"


def kompetenz_startwerte(name: str):
    """F3-Startwerte für einen Benutzernamen oder None."""
    teile = _namensteile(name)
    for schluessel, werte in KOMPETENZ_START:
        if teile & set(schluessel):
            return werte
    return None


def ist_handelsvertreter_name(name: str) -> bool:
    n = _normal(name)
    return any(hv in n for hv in HANDELSVERTRETER_START)


# --- Objektart (B3) / Pflichtfelder (B2) --------------------------------------------

def objektarten(session: Session | None = None) -> list:
    """[(code, bezeichnung, parteien_pflicht)] aus dem Blatt Objektarten."""
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    return [(o.code, o.bezeichnung, o.parteien_pflicht) for o in logik.objektarten]


def objektart_aus_text(text: str) -> str | None:
    """Antwort „Einfamilienhaus|Doppelhaushälfte|Reihenhaus|Mehrfamilienhaus|
    Gewerbe“ (Q-W02/Q-P02) → Objektart-Code."""
    t = (text or "").strip().lower()
    if not t:
        return None
    if t.startswith("mehrfamilien"):
        return "MFH"
    if t.startswith("reihenend"):
        return "REH"
    if t.startswith("reihen"):
        return "RH"
    if t.startswith("einfamilien") or t.startswith("doppelhaus"):
        return "EFH"
    return None


def pflichtfelder(session: Session) -> list:
    from app import leadmanagement as kern
    roh = kern.parameter_holen(session, "pflichtfelder", "")
    return [f.strip() for f in roh.split(";") if f.strip()]


def pflichtfelder_offen(session: Session, kunde: Kunde, vorgang: Vorgang | None = None) -> list:
    """Namen der leeren Pflichtfelder (B2) – bei MFH zusätzlich Parteien und
    Rechnungsadresse."""
    offen = []
    for feld in pflichtfelder(session):
        if feld == "interesse":
            if not (kunde.interesse or "").strip():
                offen.append("Interesse")
            continue
        if feld == "vertriebskanal":
            if not (kunde.vertriebskanal or "").strip():
                offen.append("Vertriebskanal")
            continue
        wert = getattr(kunde, feld, None)
        if wert is None or str(wert).strip() == "":
            offen.append(feld.capitalize() if feld != "plz" else "PLZ")
    if (kunde.objektart or "").upper() == "MFH":
        if not kunde.parteien:
            offen.append("Anzahl Parteien")
        if not ((kunde.rechnung_strasse or "").strip() and (kunde.rechnung_ort or "").strip()):
            offen.append("Rechnungsadresse")
    return offen


# --- Benutzereinstellungen (A-14) ----------------------------------------------------

def einstellung_holen(session: Session, benutzer_id: int, key: str, standard=None):
    zeile = (session.query(BenutzerEinstellung)
             .filter(BenutzerEinstellung.benutzer_id == benutzer_id,
                     BenutzerEinstellung.key == key).first())
    if zeile is None or not zeile.wert:
        return standard
    try:
        return json.loads(zeile.wert)
    except ValueError:
        return standard


def einstellung_setzen(session: Session, benutzer_id: int, key: str, wert) -> None:
    zeile = (session.query(BenutzerEinstellung)
             .filter(BenutzerEinstellung.benutzer_id == benutzer_id,
                     BenutzerEinstellung.key == key).first())
    if zeile is None:
        zeile = BenutzerEinstellung(benutzer_id=benutzer_id, key=key)
        session.add(zeile)
    zeile.wert = json.dumps(wert, ensure_ascii=False)
    session.flush()


# --- Migration v23 (Bestand nachziehen) ---------------------------------------------

def bestand_nachziehen(session: Session) -> list:
    """Einmalig (migrate.py, Schalter migration_v23_leads): vorgaenge.ad_id aus
    aktiven Terminen, Objektart aus Qualifizierungsantworten, Kompetenz-
    Startwerte F3 und Handelsvertreter-Kennzeichen per Namensabgleich,
    max_termine_tag_start für Profile ohne Wert."""
    from app.models import LeadQualifizierung, VotTermin
    meldungen = []
    # ad_id aus aktiven/letzten Terminen
    nachgezogen = 0
    for v in session.query(Vorgang).filter(Vorgang.ad_id.is_(None),
                                           Vorgang.lead_phase.isnot(None)):
        termin = (session.query(VotTermin)
                  .filter(VotTermin.vorgang_id == v.id, VotTermin.ad_id.isnot(None))
                  .order_by(VotTermin.status.in_(("geplant", "bestaetigt")).desc(),
                            VotTermin.beginn.desc()).first())
        if termin is not None:
            v.ad_id = termin.ad_id
            nachgezogen += 1
    if nachgezogen:
        meldungen.append(f"{nachgezogen} Vorgänge mit Außendienst aus Terminen (ad_id)")
    # Objektart aus Q-W02 / Q-P02
    objekt = 0
    for q in session.query(LeadQualifizierung):
        try:
            antworten = json.loads(q.antworten or "{}")
        except ValueError:
            continue
        code = objektart_aus_text(antworten.get("Q-W02") or antworten.get("Q-P02") or "")
        if not code:
            continue
        v = session.get(Vorgang, q.vorgang_id)
        kunde = session.get(Kunde, v.kunde_id) if v else None
        if kunde is not None and not kunde.objektart:
            kunde.objektart = code
            objekt += 1
    if objekt:
        meldungen.append(f"{objekt} Kunden mit Objektart aus der Qualifizierung")
    # Kompetenzen + Handelsvertreter
    kompetenz = 0
    hv = 0
    for b in session.query(Benutzer).filter(Benutzer.rolle == "aussendienst"):
        start = kompetenz_startwerte(b.name)
        ist_hv = ist_handelsvertreter_name(b.name)
        if start is None and not ist_hv:
            continue
        profil = profil_fuer(session, b.id)
        if profil is None:
            from app import leadmanagement as kern
            try:
                max_tag = int(kern.parameter_holen(session, "max_termine_tag_start", "3"))
            except ValueError:
                max_tag = 3
            profil = AdProfil(benutzer_id=b.id, max_termine_tag=max_tag,
                              puffer_min=30, aktiv_terminierung=True)
            session.add(profil)
            session.flush()
        if start is not None and not kompetenz_sparten(profil):
            sparten, kombi, mfh, gewerbe = start
            profil.kompetenz_sparten = json.dumps(sparten)
            profil.kompetenz_kombi = kombi
            profil.kompetenz_mfh = mfh
            profil.kompetenz_gewerbe = gewerbe
            kompetenz += 1
        if ist_hv and not profil.terminiert_selbst:
            profil.terminiert_selbst = True
            hv += 1
    if kompetenz:
        meldungen.append(f"Produktkompetenz (F3) an {kompetenz} AD-Profilen vorbelegt")
    if hv:
        meldungen.append(f"{hv} Handelsvertreter gekennzeichnet (terminiert selbst)")
    session.flush()
    return meldungen
