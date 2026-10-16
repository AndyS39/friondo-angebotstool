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
from app import rollen as rollen_modul   # v33: Basisrolle/Rollen-Varianten

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
    """v33 (PLAN_V20 Phase 167): Rollen-Kennzeichen „handelsvertreter“ (Variante der
    Basisrolle Außendienst); das Profil-Kennzeichen terminiert_selbst bleibt gespiegelt
    und gilt weiter (v32-Code, Altbestand)."""
    if benutzer is None or benutzer.basisrolle != "aussendienst":
        return False
    hat = getattr(benutzer, "hat_kennzeichen", None)
    if hat is not None and hat("handelsvertreter"):
        return True
    profil = profil_fuer(session, benutzer.id)
    return bool(profil is not None and profil.terminiert_selbst)


def handelsvertreter_ids(session: Session, nur_aktive: bool = True) -> set:
    """v33 (PLAN_V20 Phase 167): Benutzer-IDs der Handelsvertreter – Rollen-Kennzeichen
    „handelsvertreter“ (Haupt- oder Zusatzrolle, Basisrolle Außendienst) ODER das
    gespiegelte Profil-Kennzeichen terminiert_selbst (Altbestand, v32-Code)."""
    ids = {p.benutzer_id for p in session.query(AdProfil)
           .filter(AdProfil.terminiert_selbst.is_(True))}
    abfrage = session.query(Benutzer).filter(rollen_modul.filter_basis("aussendienst"))
    if nur_aktive:
        abfrage = abfrage.filter(Benutzer.aktiv.is_(True))
    for b in abfrage:
        if b.id not in ids and b.hat_kennzeichen("handelsvertreter"):
            ids.add(b.id)
    return ids


def handelsvertreter_liste(session: Session) -> list:
    """Aktive Handelsvertreter (für Dropdowns, G3) – aus der Benutzerverwaltung:
    v33 Rollen-Kennzeichen oder Profil-Kennzeichen (handelsvertreter_ids)."""
    ids = handelsvertreter_ids(session)
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
    """Leerer Text = Vergabe an HV erlaubt; sonst der treffende Ausschlussgrund.
    v33 (PLAN_V20 Phase 175): Kanal alias-sicher („SWD“ = „Stadtwerke Düsseldorf“), die
    Meldung nennt den Anzeigewert („übersprungen: Kanal Stadtwerke Düsseldorf“)."""
    from app import leadmanagement as kern
    from app.models import LeadQuelle
    liste = hv_ausschluss_liste(session)
    if not liste:
        return ""
    kunde = kunde or session.get(Kunde, vorgang.kunde_id)
    kanal = (kunde.vertriebskanal or "").strip().lower() if kunde else ""
    if kanal and (kanal in liste
                  or any(a.lower() in liste for a in kern.kanal_aliase(kunde.vertriebskanal))):
        return f"Kanal „{kern.kanal_anzeige(kunde.vertriebskanal)}“ wird nur vom Innendienst terminiert."
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
    # v37 (PLAN_LEAD_V7 Phase 199, Agent L3): Merkmale (PVV „PV vorhanden“) sind keine
    # Sparte – keine Kompetenzprüfung (sparten.INTERESSEN_MERKMALE)
    from app import sparten as sparten_modul
    sparten = [s.upper() for s in sparten if s and s.upper() not in sparten_modul.INTERESSEN_MERKMALE]
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
    # v31 (PLAN_LEAD_V5 Phase 157): MS/WA/DMS sind Freitext-Sparten wie WB – keine
    # Pflicht-Kompetenz; der Admin kann sie trotzdem im AD-Profil (kompetenz_sparten)
    # hinterlegen [ANNAHME: frei, bis die Profile gepflegt sind]
    fehlend = [s for s in sparten
               if s not in koennen and s not in ("WB", "GW", "MS", "WA", "DMS")
               and s not in gedeckt]
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
            # v37 (PLAN_LEAD_V7 Phase 199, Agent L3): das Merkmal „PV vorhanden“ (PVV) erfüllt
            # das Pflichtfeld nicht – es zählt nur eine Erfassungs-Sparte [ANNAHME]
            from app import sparten as sparten_modul
            if not sparten_modul.erfassungs_codes(kunde.interesse):
                offen.append("Interesse")
            continue
        if feld == "vertriebskanal":
            if not (kunde.vertriebskanal or "").strip():
                offen.append("Vertriebskanal")
            continue
        if feld == "ad_id":
            # v31 (Phase 158, Vertrag T 4.8): der Außendienst steht am Vorgang (vorgang.ad_id),
            # nicht am Kunden – vorher getattr(kunde, "ad_id") → immer offen; ein zugewiesener
            # Handelsvertreter (HV-Lead) gilt als erfüllt, ohne Vorgang keine Aussage
            if vorgang is not None and not vorgang.ad_id:
                offen.append("Außendienst")
            continue
        wert = getattr(kunde, feld, None)
        if wert is None or str(wert).strip() == "":
            offen.append({"plz": "PLZ", "strasse": "Straße", "email": "E-Mail"}
                         .get(feld, feld.capitalize()))
    if (kunde.objektart or "").upper() == "MFH":
        if not kunde.parteien:
            offen.append("Anzahl Parteien")
        if not ((kunde.rechnung_strasse or "").strip() and (kunde.rechnung_ort or "").strip()):
            offen.append("Rechnungsadresse")
    # v35 (PLAN_LEAD_V6 Phase 184): Kanal „?“ = „Vertriebskanal unklar“ zählt immer als offenes
    # Pflichtfeld („Vertriebskanal klären“) – unabhängig vom Parameter pflichtfelder; sperrt
    # damit Terminierung (lead_kartei.terminierung_pruefung) und TAIFUN-Übergabe (Agent T)
    from app import lead_kanaele
    if lead_kanaele.kanal_unklar(kunde) and lead_kanaele.UNKLAR_HINWEIS not in offen:
        offen.append(lead_kanaele.UNKLAR_HINWEIS)
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
    for b in session.query(Benutzer).filter(rollen_modul.filter_basis("aussendienst")):
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


# --- Zugriff und Zuweisung (gemeinsam fuer Phasen 105-111) --------------------------

def zugriff_erlaubt(session: Session, benutzer, vorgang: Vorgang | None = None) -> bool:
    """Darf dieser Benutzer das Lead-Modul bzw. diesen Vorgang bearbeiten?
    Modul-Sichtbare (kern.lead_modul_sichtbar) immer; Handelsvertreter (A-1)
    ohne Vorgang ja (die Sicht filtert dann server-seitig auf die Gruppe).
    v35 (PLAN_LEAD_V6 Phase 185): mit Vorgang entscheidet bearbeiten_erlaubt –
    Handelsvertreter an allen Leads ihrer Gruppe (hv_gruppe_fuer), angestellte
    Außendienstler an Leads mit vorgaenge.ad_id = eigene ID; ohne Vorgang bleibt
    der angestellte Außendienst außen vor (Boards, Listen, Sammelaktionen)."""
    from app import leadmanagement as kern
    if benutzer is None:
        return False
    if kern.lead_modul_sichtbar(session, benutzer):
        return True
    if vorgang is not None:
        return bearbeiten_erlaubt(session, benutzer, vorgang)
    return ist_handelsvertreter(session, benutzer)


# --- v35 (PLAN_LEAD_V6 Phase 185): HV-Gruppen und Bearbeitungsrecht --------------------
# Ergänzung 4 von Andreas (15.10.2026): die HV-Gruppen sind die aus v31/v33 – Parameter
# hv_gruppe_rene, hv_gruppe_simon, hv_gruppe_simon_mitglieder (Lead-Einstellungen), gelesen
# über lead_dropdowns.hv_gruppe_mitglieder; hier keine zweite Gruppenlogik, nur EINE
# Funktion, die die Benutzer-IDs der Gruppe eines Vertreters liefert.

def hv_gruppe_fuer(session: Session, benutzer_id: int | None) -> set[int]:
    """Benutzer-IDs der HV-Gruppe eines Benutzers: Gruppe René = {René} (hv_gruppe_rene),
    Gruppe Simon = {Simon} ∪ hv_gruppe_simon_mitglieder (leer = alle Handelsvertreter außer
    der René-Gruppe – Rückfall aus v31). Ein Benutzer außerhalb beider Gruppen (angestellter
    AD, HV ohne Gruppe) bildet eine Gruppe nur mit sich selbst; ohne ID leere Menge."""
    if not benutzer_id:
        return set()
    from app import lead_dropdowns
    benutzer_id = int(benutzer_id)
    key = lead_dropdowns.hv_gruppe_fuer(session, benutzer_id)
    ids = {benutzer_id}
    if key:
        ids |= {int(i) for i in lead_dropdowns.hv_gruppe_mitglieder(session, key)}
    return ids


def hv_gruppe_sicht(session: Session, benutzer) -> set[int] | None:
    """Sichtfilter für Handelsvertreter: die IDs der eigenen Gruppe (für
    `Vorgang.ad_id.in_(...)` in Ansicht, Dashboard, Karte, Boards, Terminassistent) –
    None für alle anderen Benutzer (kein Filter)."""
    if benutzer is None or not ist_handelsvertreter(session, benutzer):
        return None
    return hv_gruppe_fuer(session, benutzer.id)


def bearbeiten_erlaubt(session: Session, benutzer, vorgang: Vorgang | None) -> bool:
    """Vertrag Phase 185 (B ruft es für jede Inline-Änderung auf): darf dieser Benutzer
    diesen Vorgang bearbeiten? Innendienst/Leadmanagement/Admin überall; angestellter
    Außendienst an Leads mit vorgaenge.ad_id = eigene ID; Handelsvertreter an Leads, deren
    ad_id in seiner Gruppe liegt (hv_gruppe_fuer) – zusätzlich an monday-Leads ohne ad_id,
    deren monday-Zuordnung (leads.benutzer_id) in der Gruppe liegt (wie
    lead_handelsvertreter.darf_vorgang). Fremde Leads bleiben für den Außendienst
    read-only (Lesesicht der Kartei, kern.lead_ad_sicht)."""
    from app import leadmanagement as kern
    if benutzer is None or vorgang is None:
        return False
    if kern.lead_modul_sichtbar(session, benutzer):
        return True
    if benutzer.basisrolle != "aussendienst":
        return False
    if ist_handelsvertreter(session, benutzer):
        gruppe = hv_gruppe_fuer(session, benutzer.id)
        if vorgang.ad_id:
            return vorgang.ad_id in gruppe
        if vorgang.lead_id:
            from app.models import Lead
            lead = session.get(Lead, vorgang.lead_id)
            return bool(lead is not None and lead.benutzer_id and lead.benutzer_id in gruppe)
        return False
    return bool(vorgang.ad_id) and vorgang.ad_id == benutzer.id


# --- v29 (PLAN_LEAD_V4 Phase 140): Handelsvertreter-Sicht und 404-Gate ----------------

# Seiten, die ein Handelsvertreter (Kennzeichen terminiert_selbst, ohne
# Innendienst-/Leadmanagement-/Admin-Rolle) weder im Menü noch per URL erreicht:
# Hauptboard, Deals, Kontaktiert, Infoabend und das komplette „Mehr …“
# (Anrufliste, Kanban, Kalender, E-Mail-Vorlagen, Übersicht, Statistik,
# Kanal-Report, Posteingang unklar, Import, Schnellanlage). Erreichbar bleiben
# Mein Dashboard · Karte · To-Dos · Handelsvertreter sowie die eigene Kartei,
# der Terminassistent eigener Leads, Anruf-/Inline-/Spalten-Routen (POST/JSON).
# Vergleich exakt bzw. als Präfix mit nachfolgendem „/“ oder „?“.
HV_GESPERRTE_PFADE = (
    "/lead-management/hauptboard", "/lead-management/boards/haupt",
    "/lead-management/terminiert", "/lead-management/kontaktiert",
    "/lead-management/info-veranstaltung", "/lead-management/anrufliste",
    "/lead-management/anruf/meine", "/lead-management/anruf/suche",
    "/lead-management/board", "/lead-management/kalender",
    "/lead-management/vorlagen", "/lead-management/uebersicht",
    "/lead-management/cockpit", "/lead-management/statistik",
    "/lead-management/posteingang", "/lead-management/import",
    "/lead-management/neu", "/lead-management/adressen",
    "/lead-management/kommunikation",
)
HV_STARTSEITE = "/lead-management/handelsvertreter"
# Nachtrag 08.10.2026 (Antwort Andreas): Direktlinks auf gesperrte Seiten werden
# IMMER (auch ohne Referer, auch JSON-Routen) mit 303 auf die HV-Ansicht umgeleitet –
# kein 404 mehr; der Hinweis steht als Meldung auf der Seite
HV_GATE_HINWEIS = ("Diese Seite gibt es in der Handelsvertreter-Sicht nicht – "
                   "Sie sehen hier Ihre eigenen Leads.")


def hv_sicht(session: Session, benutzer) -> bool:
    """v29 (Phase 140): Handelsvertreter-Sicht = Kennzeichen terminiert_selbst
    UND keine Modul-Sichtbarkeit (Innendienst/Leadmanagement/Admin sehen die
    volle Oberfläche, auch wenn sie ein AD-Profil mit Kennzeichen hätten).
    v35 (Phase 185): die Sicht zeigt und bearbeitet die Leads der ganzen Gruppe
    (hv_gruppe_fuer) – gesperrte Seiten und 303-Umleitung unverändert."""
    from app import leadmanagement as kern
    return (ist_handelsvertreter(session, benutzer)
            and not kern.lead_modul_sichtbar(session, benutzer))


def hv_pfad_gesperrt(pfad: str) -> bool:
    """Ist dieser Pfad für die Handelsvertreter-Sicht gesperrt (303 auf die
    HV-Ansicht, Nachtrag 08.10.2026)?"""
    pfad = (pfad or "").rstrip("/") or "/"
    for basis in HV_GESPERRTE_PFADE:
        if pfad == basis or pfad.startswith(basis + "/"):
            return True
    return False


def gate(request, session: Session, vorgang: Vorgang | None = None) -> None:
    """404 statt 403 (Demo-Modus: Modul unsichtbar) – Ersatz fuer _gate der
    V1-Router, zusaetzlich mit Handelsvertreter-Freigabe.
    v29 (PLAN_LEAD_V4 Phase 140): für die Handelsvertreter-Sicht sind die
    gesperrten Seiten (HV_GESPERRTE_PFADE) server-seitig zu – das Gate sitzt
    in der Route, also HINTER Login und PIN-Pflichtwechsel der v27-Middleware.
    Nachtrag 08.10.2026 (Antwort Andreas): jeder Aufruf einer gesperrten Seite
    (Lesezeichen, Mail-Link, Link aus dem Tool, auch JSON-Routen) führt mit 303
    auf die HV-Ansicht mit dem Hinweis HV_GATE_HINWEIS – unabhängig vom Referer,
    nie mehr 404 (vorher: 404 ohne Referer derselben Instanz)."""
    from fastapi import HTTPException
    hv_umleitung(request, session)
    if not zugriff_erlaubt(session, request.state.benutzer, vorgang):
        raise HTTPException(status_code=404)


def hv_umleitung(request, session: Session) -> None:
    """Nachtrag 08.10.2026 (Antwort Andreas): gesperrte Seite (HV_GESPERRTE_PFADE)
    in der Handelsvertreter-Sicht → 303 auf die HV-Ansicht mit Hinweis – immer,
    auch ohne Referer (Lesezeichen, Mail-Link) und für JSON-Routen; sonst keine
    Wirkung. Von gate() aufgerufen. Gates, die nicht über lead_v2.gate laufen
    (V1-Router routers/leadmanagement._gate – Anrufliste, Kanban, Kalender,
    Übersicht, Statistik, Posteingang, Import, Schnellanlage, Warteschlange),
    rufen diese Funktion als erste Zeile auf, sonst bleibt dort das 404 des
    Demo-Gates (Vorschlag im Bericht LC, Datei nicht in der Liste von LC)."""
    from fastapi import HTTPException
    from urllib.parse import quote_plus
    benutzer = getattr(request.state, "benutzer", None)
    if hv_pfad_gesperrt(request.url.path) and hv_sicht(session, benutzer):
        raise HTTPException(status_code=303, headers={
            "Location": f"{HV_STARTSEITE}?meldung={quote_plus(HV_GATE_HINWEIS)}"})


def hv_gruppen(session: Session) -> dict:
    """v29 (Phase 140): die zwei Ziele der Sammelaktion „An Handelsvertreter
    verschieben“ aus den Parametern hv_gruppe_rene / hv_gruppe_simon
    (Komma-Listen von Benutzer-IDs, Lead-Einstellungen; keine Namen im Code).
    Liefert {"rene": [ids], "simon": [ids]} – der erste Eintrag ist das Ziel."""
    from app import leadmanagement as kern
    gruppen = {}
    for key in ("rene", "simon"):
        roh = kern.parameter_holen(session, f"hv_gruppe_{key}", "") or ""
        gruppen[key] = [int(t) for t in roh.replace(";", ",").split(",") if t.strip().isdigit()]
    return gruppen


def hv_gruppe_ziel(session: Session, key: str):
    """Zielbenutzer (erster aktiver Eintrag) einer HV-Gruppe oder None."""
    for benutzer_id in hv_gruppen(session).get(key, []):
        person = session.get(Benutzer, benutzer_id)
        if person is not None and person.aktiv:
            return person
    return None


def hv_gruppen_wahl(session: Session) -> list[dict]:
    """Schaltflächen des Sammelaktions-Dialogs: [{key, name, zusatz, benutzer_id, ziel_name}]
    – nur Gruppen mit gültigem Ziel. v33 (PLAN_V20 Phase 175): die zweite Schaltfläche
    heißt „Simons Gruppe“ (HV_GRUPPE_SIMON_NAME) – der Lead hängt danach an der Gruppe
    (ad_id = Gruppenleiter + Kennzeichen „noch nicht verteilt“), Simon verteilt selbst."""
    wahl = []
    for key in ("rene", "simon"):
        ziel = hv_gruppe_ziel(session, key)
        if ziel is not None:
            name = HV_GRUPPE_SIMON_NAME if key == "simon" else ziel.name
            wahl.append({"key": key, "name": name, "zusatz": "", "benutzer_id": ziel.id,
                         "ziel_name": ziel.name})
    return wahl


# --- v33 (PLAN_V20 Phase 175): „Simons Gruppe“ – Kennzeichen „noch nicht verteilt“ -------
# [ANNAHME, einfachster Weg – Andreas kann die Alternative Spalte vorgaenge.hv_gruppe wählen]:
# Ziel der Sammelaktion ist der Gruppenleiter (erster Eintrag von hv_gruppe_simon, vorgaenge.
# ad_id = Simon); das Kennzeichen „Simons Gruppe (noch nicht verteilt)“ ist eine Marker-
# Aktivität (typ hv_gruppe_offen, ergebnis offen) – additiv, keine neue Spalte. Wählt
# Simon (oder der Innendienst) über das Zuständigen-Dropdown ein Mitglied, schließt
# ad_zuweisen den Marker (ergebnis verteilt) und schreibt „Zuständiger: <Name>“.
HV_GRUPPE_SIMON_NAME = "Simons Gruppe"
# v35 (PLAN_LEAD_V6 Phase 185): Meldungen der Gruppen-Sperre in ad_zuweisen (HV-Sicht)
HV_GRUPPE_ENTZIEHEN_TEXT = ("Nicht möglich: Handelsvertreter geben Leads nur an Mitglieder "
                            "der eigenen Gruppe weiter.")
HV_GRUPPE_FREMD_TEXT = ("Nicht möglich: Umverteilung nur innerhalb der eigenen Handelsvertreter-"
                        "Gruppe – der Wechsel in eine andere Gruppe läuft über den Innendienst "
                        "(Sammelaktion).")
HV_GRUPPE_MARKER = "hv_gruppe_offen"
HV_GRUPPE_OFFEN_TEXT = "An Simons Gruppe verschoben – noch nicht verteilt"
HV_GRUPPE_KENNZEICHEN = "Simons Gruppe (noch nicht verteilt)"


def _hv_gruppe_marker(session: Session, vorgang_id: int):
    from app.models import LeadAktivitaet
    return (session.query(LeadAktivitaet)
            .filter(LeadAktivitaet.vorgang_id == vorgang_id,
                    LeadAktivitaet.typ == HV_GRUPPE_MARKER)
            .order_by(LeadAktivitaet.id.desc()).first())


def hv_gruppe_offen(session: Session, vorgang) -> bool:
    """Liegt der Lead bei Simons Gruppe, ohne dass ein Mitglied gewählt wurde? (jüngster
    Marker offen UND ad_id = Gruppenleiter)."""
    if vorgang is None or not vorgang.ad_id:
        return False
    marker = _hv_gruppe_marker(session, vorgang.id)
    if marker is None or marker.ergebnis != "offen":
        return False
    leiter = hv_gruppe_ziel(session, "simon")
    return leiter is not None and vorgang.ad_id == leiter.id


def hv_gruppe_offen_ids(session: Session, vorgaenge) -> set:
    """IDs der Vorgänge mit offenem Kennzeichen (eine Abfrage für Listen)."""
    from app.models import LeadAktivitaet
    leiter = hv_gruppe_ziel(session, "simon")
    kandidaten = {v.id: v for v in vorgaenge if leiter is not None and v.ad_id == leiter.id}
    if not kandidaten:
        return set()
    juengste: dict[int, str] = {}
    for a in (session.query(LeadAktivitaet)
              .filter(LeadAktivitaet.vorgang_id.in_(list(kandidaten)),
                      LeadAktivitaet.typ == HV_GRUPPE_MARKER)
              .order_by(LeadAktivitaet.id)):
        juengste[a.vorgang_id] = a.ergebnis or ""
    return {vid for vid, erg in juengste.items() if erg == "offen"}


def hv_gruppe_offen_setzen(session: Session, vorgang, benutzer=None) -> bool:
    """Kennzeichen setzen (Sammelaktion „Simons Gruppe“); Aktivität „An Simons Gruppe
    verschoben“. Liefert False, wenn es schon offen ist."""
    from app import leadmanagement as kern
    if hv_gruppe_offen(session, vorgang):
        return False
    kern.aktivitaet(session, vorgang.id, HV_GRUPPE_MARKER, HV_GRUPPE_OFFEN_TEXT,
                    benutzer=benutzer, ergebnis="offen")
    return True


def hv_gruppe_verteilt(session: Session, vorgang, neu=None, benutzer=None) -> bool:
    """Kennzeichen schließen: alle offenen Marker auf „verteilt“ (bzw. „aufgehoben“ ohne
    neuen Zuständigen), Aktivität „Zuständiger: <Name>“. Liefert True, wenn ein Marker
    offen war."""
    from app import leadmanagement as kern
    from app.models import LeadAktivitaet
    offene = (session.query(LeadAktivitaet)
              .filter(LeadAktivitaet.vorgang_id == vorgang.id,
                      LeadAktivitaet.typ == HV_GRUPPE_MARKER,
                      LeadAktivitaet.ergebnis == "offen").all())
    if not offene:
        return False
    for marker in offene:
        marker.ergebnis = "verteilt" if neu is not None else "aufgehoben"
    if neu is not None:
        kern.aktivitaet(session, vorgang.id, "status", f"Zuständiger: {neu.name}",
                        benutzer=benutzer, ergebnis="verteilt")
    session.flush()
    return True


def hv_gruppe_von(session: Session, benutzer_id: int | None) -> str:
    """Gruppe eines Vertreters („rene“ | „simon“ | „“) für den Filter „Gruppe“
    der Handelsvertreter-Ansicht."""
    if not benutzer_id:
        return ""
    for key, ids in hv_gruppen(session).items():
        if benutzer_id in ids:
            return key
    return ""


def ad_zuweisen(session: Session, vorgang: Vorgang, ad_id: int | None,
                benutzer=None, erzwingen: bool = False) -> str:
    """Aussendienst/Handelsvertreter am Vorgang setzen (A-7, G3, F13):
    Ausschlussliste pruefen (F14; erzwingen=True nur Innendienst/Admin),
    Aktivitaet „zugewiesen an …“, Glocke an den neuen Zustaendigen.
    Liefert eine Meldung; leerer Text = Fehler bereits als Meldung."""
    from app import leadmanagement as kern
    alt_id = vorgang.ad_id
    # v35 (PLAN_LEAD_V6 Phase 185): in der Handelsvertreter-Sicht nur Umverteilung innerhalb
    # der eigenen Gruppe (Dropdown v31); kein Entziehen, kein Wechsel in die andere Gruppe –
    # das bleibt Innendienst/Admin über die Sammelaktion (v33)
    if benutzer is not None and hv_sicht(session, benutzer):
        if ad_id in (None, 0, ""):
            return HV_GRUPPE_ENTZIEHEN_TEXT
        if not str(ad_id).strip().isdigit() or int(ad_id) not in hv_gruppe_fuer(session, benutzer.id):
            return HV_GRUPPE_FREMD_TEXT
    # v33 (Phase 175): offenes Kennzeichen „Simons Gruppe (noch nicht verteilt)“ merken –
    # jede Änderung des Zuständigen löst es auf
    gruppe_offen = hv_gruppe_offen(session, vorgang)
    if ad_id in (None, 0, ""):
        vorgang.ad_id = None
        kern.aktivitaet(session, vorgang.id, "status", "Außendienst-Zuweisung entfernt",
                        benutzer=benutzer)
        if gruppe_offen:
            hv_gruppe_verteilt(session, vorgang, None, benutzer)
        session.flush()
        return "Zuweisung entfernt."
    neu = session.get(Benutzer, int(ad_id))
    if neu is None or not neu.aktiv:
        return "Außendienstler nicht gefunden."
    if ist_handelsvertreter(session, neu) and not erzwingen:
        grund = hv_ausgeschlossen(session, vorgang)
        if grund:
            return "Nicht möglich: " + grund
    if alt_id == neu.id:
        if gruppe_offen:
            # Simon wählt sich selbst: Lead bleibt bei ihm, Kennzeichen weg [ANNAHME]
            hv_gruppe_verteilt(session, vorgang, neu, benutzer)
            return f"{neu.name} behält den Lead ({HV_GRUPPE_SIMON_NAME} verteilt)."
        return f"{neu.name} ist bereits zugewiesen."
    vorgang.ad_id = neu.id
    wer = f" (vorher {session.get(Benutzer, alt_id).name})" if alt_id and session.get(Benutzer, alt_id) else ""
    kern.aktivitaet(session, vorgang.id, "status", f"Zugewiesen an {neu.name}{wer}",
                    benutzer=benutzer)
    if gruppe_offen:
        hv_gruppe_verteilt(session, vorgang, neu, benutzer)
    kunde = session.get(Kunde, vorgang.kunde_id)
    # v29 (PLAN_LEAD_V4 Phase 141): Glocken-Art „zuweisung“ – standardmäßig
    # abgeschaltet (glocke_lead_arten), die Aktivität bleibt in der Timeline
    kern.benachrichtigen(session, [neu.id],
                         f"Lead zugewiesen: {kunde.anzeige_name if kunde else '?'}"
                         f"{', ' + kunde.ort if kunde and kunde.ort else ''}",
                         f"/lead-management/lead/{vorgang.id}", art="zuweisung")
    session.flush()
    return f"Zugewiesen an {neu.name}."


def leadmanager_zuweisen(session: Session, vorgang: Vorgang, benutzer_id: int | None,
                         benutzer=None) -> str:
    """Innendienst/Leadmanager am Vorgang (A3-Spalte „Innendienst“)."""
    from app import leadmanagement as kern
    if benutzer_id in (None, 0, ""):
        vorgang.leadmanager_id = None
        kern.aktivitaet(session, vorgang.id, "status", "Leadmanager entfernt", benutzer=benutzer)
        session.flush()
        return "Leadmanager entfernt."
    neu = session.get(Benutzer, int(benutzer_id))
    if neu is None or not neu.aktiv:
        return "Benutzer nicht gefunden."
    if vorgang.leadmanager_id == neu.id:
        return f"{neu.name} ist bereits Leadmanager."
    vorgang.leadmanager_id = neu.id
    kern.aktivitaet(session, vorgang.id, "status", f"Leadmanager: {neu.name}", benutzer=benutzer)
    kunde = session.get(Kunde, vorgang.kunde_id)
    kern.benachrichtigen(session, [neu.id],
                         f"Lead übernommen: {kunde.anzeige_name if kunde else '?'}",
                         f"/lead-management/lead/{vorgang.id}", art="zuweisung")   # v29: Glocken-Art
    session.flush()
    return f"Leadmanager: {neu.name}."


# --- v25 (PLAN_LEAD_V3 Phase 120): zentraler Schalter Score/Qualifizierung ---------

def score_aktiv(session: Session) -> bool:
    """Parameter score_aktiv (an|aus, Standard aus): bei aus keine Score-
    Berechnung, keine Anzeige von Score/Klasse, kein Qualifizierungsbogen."""
    from app import leadmanagement as kern
    return kern.parameter_holen(session, "score_aktiv", "aus").strip().lower() in ("an", "ja", "1", "true")


# --- v31 (PLAN_LEAD_V5 Phase 159): Freischaltung – Prüfpunkte der Lead-Einstellungen ----

def freischaltung_pruefpunkte(session: Session) -> list[dict]:
    """Prüfpunkte vor dem Einschalten von terminierung_aktiv / mail_versand_aktiv
    (Lead-Einstellungen → „Freischaltung“): Senderecht termin@ (Graph eingerichtet),
    kalender_sync, Routing-Dienst, Leadmanager-Häkchen, HV-Gruppen, AD-Profile mit
    Arbeitszeiten Mo–Fr (ohne Samstag). Je Punkt {name, ok, text}."""
    from app import leadmanagement as kern
    punkte = []
    try:
        from app import graph_versand
        graph = bool(graph_versand.konfiguriert())
    except Exception:
        graph = False
    absender = kern.parameter_holen(session, "absender_lead_mails", "termin@friondo.de")
    punkte.append({"name": f"Senderecht {absender}", "ok": graph,
                   "text": ("Microsoft Graph eingerichtet – Prüfpunkt „Testmail aus dem Lead-Absender“ nutzen"
                            if graph else "Graph nicht eingerichtet (docs/graph-einrichtung.md) – ohne Senderecht bleibt jede Lead-Mail gesperrt")})
    kalender = kern.parameter_holen(session, "kalender_sync", "aus").strip().lower() == "an"
    punkte.append({"name": "Kalender-Sync (kalender_sync)", "ok": kalender,
                   "text": "an – Outlook-Frei/Belegt und Termineinträge für angestellte AD"
                   if kalender else "aus – der Assistent rechnet nur mit Tool-Terminen"})
    # v37 (PLAN_LEAD_V7 Phase 198, Agent L2): ORS-Key aus der .env hat Vorrang (routing.ors_schluessel)
    from app import routing
    anbieter = kern.parameter_holen(session, "routing_anbieter", "luftlinie").strip().lower()
    schluessel = (routing.ors_schluessel(session) if anbieter == "ors"
                  else kern.parameter_holen(session, "google_api_key", "") if anbieter == "google" else "")
    routing_ok = anbieter in ("ors", "google") and bool((schluessel or "").strip())
    quelle = routing.ors_schluessel_quelle(session)
    punkte.append({"name": "Routing-Dienst (Fahrzeiten)", "ok": routing_ok,
                   "text": (f"{anbieter} mit Schlüssel" + (" aus der .env (ORS_API_KEY)" if quelle == "env" else "")
                            + " – Prüfpunkt „Routing-Dienst antwortet“ in den Lead-Einstellungen") if routing_ok
                   else (f"{anbieter} – {routing.KEY_FEHLT_TEXT}" if anbieter == "ors" or not quelle
                         else f"{anbieter} – Key vorhanden, Anbieter auf „ors“ stellen (Lead-Routing)")})
    leadmanager = [b for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
                   if getattr(b, "leadmanager", False)]
    punkte.append({"name": "Leadmanager-Häkchen (Benutzerverwaltung)", "ok": bool(leadmanager),
                   "text": (", ".join(sorted(b.name for b in leadmanager)) if leadmanager
                            else "kein Benutzer mit Häkchen „Leadmanager“ – Innendienst-Dropdowns bleiben leer")})
    gruppen = hv_gruppen(session)
    hv_ok = bool(gruppen.get("rene")) and bool(gruppen.get("simon"))
    punkte.append({"name": "HV-Gruppen (hv_gruppe_rene / hv_gruppe_simon)", "ok": hv_ok,
                   "text": (f"René: {len(gruppen.get('rene', []))} · Simon-Gruppe: {len(gruppen.get('simon', []))} Benutzer"
                            + ("" if kern.parameter_holen(session, "hv_gruppe_simon_mitglieder", "").strip()
                               else " · Mitglieder = alle HV außer René [ANNAHME]"))
                   if hv_ok else "mindestens eine Gruppe ohne Ziel – Lead-Einstellungen → HV-Gruppen"})
    fehlend = []
    for profil in session.query(AdProfil).filter(AdProfil.aktiv_terminierung.is_(True)):
        if profil.terminiert_selbst:
            continue
        try:
            zeiten = json.loads(profil.arbeitszeiten or "{}")
        except ValueError:
            zeiten = {}
        tage = [t for t in ("mo", "di", "mi", "do", "fr") if zeiten.get(t)]
        samstag = any(str(k).lower() in ("sa", "samstag", "5", "6") for k in zeiten)
        if len(tage) < 5 or samstag:
            person = session.get(Benutzer, profil.benutzer_id)
            fehlend.append((person.name if person else str(profil.benutzer_id))
                           + (" (Samstag gesetzt)" if samstag else f" ({len(tage)}/5 Tage)"))
    punkte.append({"name": "AD-Profile mit Arbeitszeiten Mo–Fr", "ok": not fehlend,
                   "text": "alle angestellten AD mit Arbeitszeiten Montag bis Freitag"
                   if not fehlend else "unvollständig: " + ", ".join(fehlend)})
    return punkte


def mails_gesperrt_anzahl(session: Session) -> int:
    """Zähler „Mails gesperrt: n“ – lead_mail.gesperrte_anzahl (Agent T), Rückfall: Zählung
    KommunikationLog.status == „gesperrt“."""
    try:
        from app import lead_mail
        funktion = getattr(lead_mail, "gesperrte_anzahl", None)
        if callable(funktion):
            return int(funktion(session) or 0)
    except Exception:
        pass
    from app.models import KommunikationLog
    return int(session.query(KommunikationLog).filter(KommunikationLog.status == "gesperrt").count())


# --- v29 (PLAN_LEAD_V4 Phasen 140/141/143): Datenmigration Oberfläche -----------------

ROUTEN_START_STANDARD = "Arnold-Overbeck-Straße 63-65, 47139 Duisburg"
VORSCHLAEGE_ANZAHL_STANDARD = "3"
# Namensabgleich für die Startwerte der HV-Gruppen (nur Migration – im Betrieb
# kommen die Ziele ausschließlich aus den Parametern hv_gruppe_rene/_simon)
HV_GRUPPE_RENE_NAMEN = ("golaschewski",)
HV_GRUPPE_SIMON_LEITER = ("grady",)                       # O'Grady / O Grady
HV_GRUPPE_SIMON_TEAM = ("di blasi", "lind", "kinkel", "leinenbach")


def _parameter_leer(session: Session, name: str) -> bool:
    from app.models import LeadParameter
    zeile = session.query(LeadParameter).filter(LeadParameter.name == name).first()
    return zeile is None or not (zeile.wert or "").strip()


def _hv_nach_namen(session: Session, muster: tuple) -> list:
    """Aktive Handelsvertreter (Kennzeichen terminiert_selbst), deren Name eines
    der Muster enthält – Reihenfolge wie die Muster."""
    treffer = []
    hv = handelsvertreter_liste(session)
    for m in muster:
        for b in hv:
            if m in _normal(b.name) and b not in treffer:
                treffer.append(b)
    return treffer


def migration_v29_oberflaeche(session: Session) -> list:
    """migrate.py (v29): Startwerte per Namensabgleich für die HV-Gruppen der
    Sammelaktion (hv_gruppe_rene: René Golaschewski; hv_gruppe_simon: Simon
    O'Grady zuerst, danach sein Team), Standardwerte routen_start (Friondo
    Duisburg), vorschlaege_anzahl = 3 und glocke_lead_arten (nur wenn leer:
    die beiden To-Do-Arten). Idempotent: nur leere Parameter werden gesetzt,
    der zweite Lauf meldet nichts. Committet nicht selbst."""
    from app import leadmanagement as kern
    from app import lead_glocken
    meldungen = []
    if _parameter_leer(session, "hv_gruppe_rene"):
        rene = _hv_nach_namen(session, HV_GRUPPE_RENE_NAMEN)
        if rene:
            kern.parameter_setzen(session, "hv_gruppe_rene", ",".join(str(b.id) for b in rene[:1]))
            meldungen.append(f"hv_gruppe_rene = {rene[0].name} (Namensabgleich)")
        else:
            meldungen.append("hv_gruppe_rene: kein Handelsvertreter „Golaschewski“ gefunden – "
                             "in den Lead-Einstellungen setzen")
    if _parameter_leer(session, "hv_gruppe_simon"):
        leiter = _hv_nach_namen(session, HV_GRUPPE_SIMON_LEITER)
        if leiter:
            team = [b for b in _hv_nach_namen(session, HV_GRUPPE_SIMON_TEAM) if b not in leiter]
            ids = [b.id for b in leiter[:1] + team]
            kern.parameter_setzen(session, "hv_gruppe_simon", ",".join(str(i) for i in ids))
            meldungen.append(f"hv_gruppe_simon = {leiter[0].name}"
                             + (f" + {len(team)} Team" if team else "") + " (Namensabgleich)")
        else:
            meldungen.append("hv_gruppe_simon: kein Handelsvertreter „O'Grady“ gefunden – "
                             "in den Lead-Einstellungen setzen")
    if _parameter_leer(session, "routen_start"):
        kern.parameter_setzen(session, "routen_start", ROUTEN_START_STANDARD)
        meldungen.append(f"routen_start = {ROUTEN_START_STANDARD}")
    if _parameter_leer(session, "vorschlaege_anzahl"):
        kern.parameter_setzen(session, "vorschlaege_anzahl", VORSCHLAEGE_ANZAHL_STANDARD)
        meldungen.append("vorschlaege_anzahl = 3 (statt 5)")
    if _parameter_leer(session, lead_glocken.PARAMETER):
        kern.parameter_setzen(session, lead_glocken.PARAMETER, ",".join(lead_glocken.STANDARD_ARTEN))
        meldungen.append("glocke_lead_arten = " + ",".join(lead_glocken.STANDARD_ARTEN)
                         + " (Glocke nur To-Dos)")
    session.flush()
    return meldungen
