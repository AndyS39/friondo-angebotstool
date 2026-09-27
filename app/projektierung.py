# Projektierung V1 (v11, Phasen 64–71): Kernlogik des Moduls – Nummernkreis
# PR-JJNNNN, Parameter (Key-Value), Projekt-/Gewerk-Anlage aus angenommenen
# Angeboten, Aufgabenpakete mit Fälligkeitsregeln (+N / FP+N / M-N),
# Planungs-Ampel, abgeleiteter Projektstatus, Ordnerstruktur unter
# data/projekte/<PR>/, Verlauf (append-only) und Benachrichtigungen.

import json
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app import config
from app.models import (Angebot, Aufgabe, AufgabenpaketInstanz, Benachrichtigung,
                        Benutzer, Gewerk, Kunde, Projekt, ProjektDokument,
                        ProjektTermin, ProjektVerlauf, Team, Vorgang)

PROJEKT_PREFIX = "PR-"
PROJEKTE_ORDNER = config.DATA_ORDNER / "projekte"

# Storno-Gründe (Phase 64) – Standardliste, in der Parametrierung pflegbar;
# bei „Sonstiges" ist der Freitext Pflicht
STORNO_GRUENDE_STANDARD = ["Kunde widerrufen",
                           "Finanzierung/Förderung nicht erhalten",
                           "Technisch nicht umsetzbar",
                           "Kunde hat anderen Anbieter gewählt",
                           "Sonstiges"]

# Ordnervorlage (Konzept 3.5): Ebene projekt = einmal je Projekt,
# Ebene gewerk = je Gewerk unter <Sparte>/…
ORDNERVORLAGE_STANDARD = [
    {"pfad": "01 Angebot & Erfassung", "ebene": "projekt"},
    {"pfad": "02 Feinplanung & Heizlast", "ebene": "gewerk"},
    {"pfad": "03 Fotos/Außengerät", "ebene": "gewerk"},
    {"pfad": "03 Fotos/Innengerät & Heizungsraum", "ebene": "gewerk"},
    {"pfad": "03 Fotos/Öltank", "ebene": "gewerk"},
    {"pfad": "03 Fotos/Zählerschrank", "ebene": "gewerk"},
    {"pfad": "03 Fotos/Dach", "ebene": "gewerk"},
    {"pfad": "03 Fotos/Alte Anlage", "ebene": "gewerk"},
    {"pfad": "03 Fotos/Neue Anlage", "ebene": "gewerk"},
    {"pfad": "03 Fotos/Mängel", "ebene": "gewerk"},
    {"pfad": "04 Bestellungen & Subs", "ebene": "projekt"},
    {"pfad": "05 Montage & Protokolle", "ebene": "gewerk"},
    {"pfad": "06 Rechnungen", "ebene": "projekt"},
]

SUB_TYPEN_STANDARD = ["GaLa-Bau", "Elektro", "Dachdecker", "Entsorgung",
                      "Lift-Kran", "Gerüst", "Sonstige"]

# Phasen-Rangfolge für den abgeleiteten Projektstatus (v15: neue Phasen)
_PHASEN_RANG = {"auftragseingang": 0, "feinplanung_vot": 1, "planung": 2,
                "montagevorbereitung": 3, "montage": 4, "abnahme_freigabe": 5}


# --- Parameter (Key-Value) --------------------------------------------------

def parameter_holen(session: Session, name: str, standard: str = "") -> str:
    from app.models import ProjektierungParameter
    zeile = (session.query(ProjektierungParameter)
             .filter(ProjektierungParameter.name == name).first())
    return zeile.wert if zeile is not None else standard


def parameter_setzen(session: Session, name: str, wert: str) -> None:
    from app.models import ProjektierungParameter
    zeile = (session.query(ProjektierungParameter)
             .filter(ProjektierungParameter.name == name).first())
    if zeile is None:
        session.add(ProjektierungParameter(name=name, wert=wert))
        session.flush()   # autoflush ist aus – sofort abfragbar machen
    else:
        zeile.wert = wert


def storno_gruende(session: Session) -> list[str]:
    roh = parameter_holen(session, "storno_gruende",
                          json.dumps(STORNO_GRUENDE_STANDARD, ensure_ascii=False))
    try:
        werte = json.loads(roh)
        return [str(w) for w in werte] or STORNO_GRUENDE_STANDARD
    except (ValueError, TypeError):
        return STORNO_GRUENDE_STANDARD


def ordnervorlage(session: Session) -> list[dict]:
    roh = parameter_holen(session, "ordnervorlage",
                          json.dumps(ORDNERVORLAGE_STANDARD, ensure_ascii=False))
    try:
        werte = json.loads(roh)
        return werte or ORDNERVORLAGE_STANDARD
    except (ValueError, TypeError):
        return ORDNERVORLAGE_STANDARD


def freigabe_modus(session: Session) -> str:
    """Demo-Schalter (Phase 70): admin (Standard) = Modul nur für Admins."""
    wert = parameter_holen(session, "freigabe_modus", "admin").strip().lower()
    return wert if wert in ("admin", "alle") else "admin"


def modul_sichtbar(session: Session, benutzer) -> bool:
    """Server-seitige Sichtbarkeitsprüfung des gesamten Moduls (Phase 70)."""
    if benutzer is None:
        return False
    if benutzer.rolle == "admin":
        return True
    if freigabe_modus(session) != "alle":
        return False
    return (benutzer.rolle in ("innendienst",)
            or benutzer.hat_rolle("projektierung") or benutzer.hat_rolle("montage")
            or benutzer.rolle == "aussendienst")


# --- Nummernkreis PR-JJNNNN ---------------------------------------------------

def naechste_projektnummer(session: Session) -> str:
    """Fortlaufend je Jahr (PR-<JJ><NNNN>), Zähler in projektierung_parameter;
    Jahreswechsel setzt auf 0001. Vergibt die Nummer verbrauchend."""
    jj = datetime.now().year % 100
    gespeichert_jj = parameter_holen(session, "pr_zaehler_jj", "")
    zaehler = int(parameter_holen(session, "pr_zaehler", "0") or 0)
    if gespeichert_jj != str(jj):
        zaehler = 0
    zaehler += 1
    # Kollisionen (z. B. manuell angelegte Nummern) überspringen
    while (session.query(Projekt)
           .filter(Projekt.nummer == f"{PROJEKT_PREFIX}{jj}{zaehler:04d}").count()):
        zaehler += 1
    parameter_setzen(session, "pr_zaehler_jj", str(jj))
    parameter_setzen(session, "pr_zaehler", str(zaehler))
    return f"{PROJEKT_PREFIX}{jj}{zaehler:04d}"


# --- Ordnerstruktur -----------------------------------------------------------

def projekt_ordner(projekt: Projekt) -> Path:
    return PROJEKTE_ORDNER / projekt.nummer


def ordner_anlegen(session: Session, projekt: Projekt,
                   sparten: list[str] | None = None) -> None:
    """Legt die Ordnervorlage unter data/projekte/<PR>/ an – Ebene projekt
    direkt, Ebene gewerk je Sparte unter <Sparte>/…; idempotent."""
    basis = projekt_ordner(projekt)
    if sparten is None:
        sparten = [g.sparte for g in session.query(Gewerk)
                   .filter(Gewerk.projekt_id == projekt.id)]
    for eintrag in ordnervorlage(session):
        pfad = str(eintrag.get("pfad", "")).strip().strip("/\\")
        if not pfad:
            continue
        if eintrag.get("ebene") == "gewerk":
            for sparte in sparten or ["WP"]:
                (basis / sparte / pfad).mkdir(parents=True, exist_ok=True)
        else:
            (basis / pfad).mkdir(parents=True, exist_ok=True)


# --- Verlauf + Benachrichtigungen ----------------------------------------------

def verlauf(session: Session, projekt_id: int, text: str, benutzer=None,
            gewerk_id: int | None = None, aufgabe_id: int | None = None,
            art: str = "system", erwaehnte: list[int] | None = None) -> ProjektVerlauf:
    eintrag = ProjektVerlauf(
        projekt_id=projekt_id, gewerk_id=gewerk_id, aufgabe_id=aufgabe_id,
        art=art, text=(text or "").strip()[:4000],
        benutzer_id=benutzer.id if benutzer else None,
        erstellt_von=benutzer.id if benutzer else None,
        erwaehnte_ids=json.dumps(erwaehnte or []))
    session.add(eintrag)
    session.flush()
    return eintrag


def benachrichtigen(session: Session, benutzer_ids, text: str, link: str,
                    art: str = "") -> None:
    """Glocken-Einträge (dedupliziert je Aufruf); der Mail-Teil (sofort/digest)
    hängt in app/benachrichtigungen.py an denselben Einträgen."""
    gesehen: set[int] = set()
    for bid in benutzer_ids:
        if not bid or bid in gesehen:
            continue
        gesehen.add(bid)
        session.add(Benachrichtigung(benutzer_id=bid, text=(text or "")[:500],
                                     link=(link or "")[:300], art=art))
    session.flush()
    if gesehen:
        try:
            from app import benachrichtigungen as mail_modul
            mail_modul.sofort_versenden(session, sorted(gesehen), text, link, art)
        except Exception:
            pass   # Mail-Fehler blockieren das Tool nie


# --- Aufgabenpakete + Fälligkeiten ----------------------------------------------

def _standard_benutzer(session: Session, rolle: str, gewerk: Gewerk,
                       projekt: Projekt) -> int | None:
    """Verantwortlichen je Paket-Rolle bestimmen: Gewerk-Zuweisung, sonst
    Standard aus der Parametrierung, sonst Projektleiter."""
    if rolle == "feinplaner" and gewerk.feinplaner_id:
        return gewerk.feinplaner_id
    if rolle == "elektroplaner" and gewerk.elektroplaner_id:
        return gewerk.elektroplaner_id
    schluessel = {"projektierer": "standard_projektleiter",
                  "feinplaner": "standard_feinplaner",
                  "elektroplaner": "standard_elektroplaner",
                  "innendienst": "buchhaltung_benutzer",
                  "buchhaltung": "buchhaltung_benutzer"}.get(rolle, "")
    if schluessel:
        wert = parameter_holen(session, schluessel, "")
        if wert.isdigit() and session.get(Benutzer, int(wert)) is not None:
            return int(wert)
    if rolle in ("innendienst", "buchhaltung"):
        buero = (session.query(Benutzer)
                 .filter(Benutzer.rolle.in_(["innendienst", "admin"]),
                         Benutzer.aktiv.is_(True))
                 .order_by(Benutzer.id).first())
        if buero is not None:
            return buero.id
    return projekt.projektleiter_id


def faelligkeit_berechnen(regel: str, aktiviert_am: datetime,
                          fp_termin: datetime | None,
                          montage_termin: datetime | None) -> datetime | None:
    """Fälligkeitsregeln (Phase 65): +N = N Tage nach Aktivierung ·
    FP+N = N Tage nach Feinplanungs-Termin · M-N/M+N = relativ zum ersten
    Montagetermin. FP/M ohne Termin → None (wird beim Termin nachberechnet)."""
    regel = (regel or "").strip().upper().replace(" ", "")
    if not regel:
        return None
    try:
        if regel.startswith("FP"):
            if fp_termin is None:
                return None
            return fp_termin + timedelta(days=int(regel[2:] or 0))
        if regel.startswith("M"):
            if montage_termin is None:
                return None
            return montage_termin + timedelta(days=int(regel[1:] or 0))
        return aktiviert_am + timedelta(days=int(regel))
    except ValueError:
        return None


def _erster_termin(session: Session, gewerk: Gewerk, typ: str) -> datetime | None:
    termin = (session.query(ProjektTermin)
              .filter(ProjektTermin.gewerk_id == gewerk.id,
                      ProjektTermin.typ == typ,
                      ProjektTermin.beginn.isnot(None))
              .order_by(ProjektTermin.beginn).first())
    return termin.beginn if termin is not None else None


# v15 (Phase 78): Paket-Rang = Boardspalte (Sortierung + Aufklapp-Logik)
PAKET_PHASEN_RANG = {
    "auftragseingang": 0,
    "feinplanung vot": 1,
    "planung wp": 2, "planung elektro": 2, "friondo fit for future": 2,
    "fit for future": 2,
    "montagevorbereitung": 3,
    "abnahme & freigabe": 5,
}


def paket_rang(paket_name: str) -> int:
    """Rang eines Pakets in der Boardspalten-Reihenfolge (unbekannt = 4,
    zwischen Montage und Abnahme, damit Sonderpakete nicht oben landen)."""
    return PAKET_PHASEN_RANG.get((paket_name or "").strip().lower(), 4)


def _schritt_sichtbar(session: Session, gewerk: Gewerk, bedingung: str) -> bool:
    """sichtbar_wenn "steckbrief:<feld>=<wert>": Schritt nur anlegen, wenn das
    Steckbrief-Feld den Wert hat (Vergleich ohne Gross/Klein)."""
    bedingung = (bedingung or "").strip()
    if not bedingung:
        return True
    if bedingung.lower().startswith("steckbrief:") and "=" in bedingung:
        feld, _, soll = bedingung[len("steckbrief:"):].partition("=")
        from app.models import SteckbriefWert
        eintrag = (session.query(SteckbriefWert)
                   .filter(SteckbriefWert.gewerk_id == gewerk.id,
                           SteckbriefWert.feld == feld.strip()).first())
        ist = (eintrag.wert if eintrag is not None else "").strip().lower()
        return ist == soll.strip().lower()
    return True   # unbekannte Bedingung blockiert nie (Warnung kommt im Blatt)


def aufgabe_auswahl_setzen(session: Session, aufgabe: Aufgabe, auswahl: str,
                           benutzer=None) -> bool:
    """v15 (Phase 78): Radio-Auswahl an einer Aufgabe. Option mit * im Blatt
    gilt als erledigt, Optionen ohne * setzen "entfaellt" (beantwortet, nichts
    zu tun). Leere Auswahl -> zurueck auf offen."""
    gueltige = {}
    for teil in (aufgabe.optionen or "").split("|"):
        teil = teil.strip()
        if teil:
            gueltige[teil.rstrip("*").strip()] = teil.endswith("*")
    auswahl = (auswahl or "").strip()
    if auswahl and auswahl not in gueltige:
        return False
    aufgabe.auswahl = auswahl
    if not auswahl:
        aufgabe.status = "offen"
        aufgabe.erledigt_am = None
        aufgabe.erledigt_von = None
    elif gueltige[auswahl]:
        aufgabe.status = "erledigt"
        aufgabe.erledigt_am = datetime.now()
        aufgabe.erledigt_von = benutzer.id if benutzer else None
    else:
        aufgabe.status = "entfaellt"
        aufgabe.erledigt_am = None
    session.flush()
    return True


def galerie_haekchen_pruefen(session: Session, gewerk: Gewerk) -> int:
    """v15 (Phase 78): offene Galerie-Aufgaben automatisch erledigen, wenn in
    allen geforderten Ordnern (aktion_wert "A|B|C") mindestens ein Bild des
    Vorgangs liegt. Laeuft beim Oeffnen der Projektakte."""
    from app.models import GalerieDatei
    angebot = session.get(Angebot, gewerk.angebot_id) if gewerk.angebot_id else None
    vorgang_id = angebot.vorgang_id if angebot is not None else None
    if not vorgang_id:
        return 0
    belegt = {zeile[0] for zeile in
              session.query(GalerieDatei.ordner)
              .filter(GalerieDatei.vorgang_id == vorgang_id,
                      GalerieDatei.sparte == gewerk.sparte,   # 27.09.2026
                      GalerieDatei.bild.is_(True)).distinct()}
    erledigt = 0
    for aufgabe in (session.query(Aufgabe)
                    .filter(Aufgabe.gewerk_id == gewerk.id,
                            Aufgabe.aktion_typ == "galerie",
                            Aufgabe.status.in_(["offen", "in_arbeit", "wartet"]))):
        ordner = [o.strip() for o in (aufgabe.aktion_wert or "").split("|")
                  if o.strip()]
        if ordner and all(o in belegt for o in ordner):
            aufgabe.status = "erledigt"
            aufgabe.erledigt_am = datetime.now()
            erledigt += 1
    if erledigt:
        session.flush()
    return erledigt


def v1_aufgaben_entfernen(session: Session, gewerk: Gewerk, benutzer=None) -> int:
    """v15 (Phase 78): alle als V1 gekennzeichneten Paket-Instanzen samt
    Aufgaben am Gewerk loeschen (Knopf in der Akte)."""
    instanzen = (session.query(AufgabenpaketInstanz)
                 .filter(AufgabenpaketInstanz.gewerk_id == gewerk.id,
                         AufgabenpaketInstanz.version == "v1").all())
    geloescht = 0
    for instanz in instanzen:
        for aufgabe in (session.query(Aufgabe)
                        .filter(Aufgabe.paket_instanz_id == instanz.id)):
            session.delete(aufgabe)
            geloescht += 1
        session.delete(instanz)
    if instanzen:
        verlauf(session, gewerk.projekt_id,
                f"V1-Aufgaben entfernt ({len(instanzen)} Pakete, "
                f"{geloescht} Aufgaben) – Gewerk {gewerk.sparte}",
                benutzer=benutzer, gewerk_id=gewerk.id)
        session.flush()
    return geloescht


def paket_aktivieren(session: Session, gewerk: Gewerk, paket: "object",
                     benutzer=None, quelle: str = "regel") -> AufgabenpaketInstanz | None:
    """Aktiviert eine Paket-Vorlage (aus projektierung_logik_v1.xlsx) am
    Gewerk: Instanz + Aufgaben mit Verantwortlichen und Fälligkeiten.
    Bereits aktive Pakete (nicht deaktiviert) werden nicht doppelt aktiviert."""
    vorhanden = (session.query(AufgabenpaketInstanz)
                 .filter(AufgabenpaketInstanz.gewerk_id == gewerk.id,
                         AufgabenpaketInstanz.paket_key == paket.key,
                         AufgabenpaketInstanz.version != "v1",   # v15 Phase 78
                         AufgabenpaketInstanz.deaktiviert_am.is_(None)).first())
    if vorhanden is not None:
        return None
    projekt = session.get(Projekt, gewerk.projekt_id)
    instanz = AufgabenpaketInstanz(
        gewerk_id=gewerk.id, paket_key=paket.key, paket_name=paket.name,
        quelle=quelle, aktiviert_von=benutzer.id if benutzer else None,
        erstellt_von=benutzer.id if benutzer else None)
    session.add(instanz)
    session.flush()
    jetzt = datetime.now()
    fp_termin = _erster_termin(session, gewerk, "feinplanung")
    montage_termin = _erster_termin(session, gewerk, "montage")
    zugewiesene: set[int] = set()
    for schritt in paket.schritte:
        # v15 (Phase 78): Sichtbarkeitsbedingung (steckbrief:<feld>=<wert>) -
        # nicht erfuellte Schritte werden gar nicht erst angelegt
        if not _schritt_sichtbar(session, gewerk, getattr(schritt,
                                                          "sichtbar_wenn", "")):
            continue
        verantwortlich = _standard_benutzer(session, schritt.rolle, gewerk, projekt)
        session.add(Aufgabe(
            gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id,
            paket_instanz_id=instanz.id, titel=schritt.titel,
            beschreibung=schritt.beschreibung, rolle=schritt.rolle,
            verantwortlich_id=verantwortlich,
            faellig_am=faelligkeit_berechnen(schritt.faellig_regel, jetzt,
                                             fp_termin, montage_termin),
            faellig_regel=schritt.faellig_regel, pflicht=schritt.pflicht,
            reihenfolge=schritt.nr, wartet_frist_tage=schritt.wartet_frist_tage,
            aktion_typ=getattr(schritt, "aktion_typ", "") or "",
            aktion_wert=getattr(schritt, "aktion_wert", "") or "",
            optionen=getattr(schritt, "optionen", "") or "",
            erstellt_von=benutzer.id if benutzer else None))
        if verantwortlich:
            zugewiesene.add(verantwortlich)
    session.flush()
    if zugewiesene and projekt is not None:
        benachrichtigen(session, zugewiesene,
                        f"Neue Aufgaben ({paket.name}) im Projekt {projekt.nummer}",
                        f"/projektierung/projekt/{projekt.id}", art="aufgabe")
    return instanz


def faelligkeiten_nachberechnen(session: Session, gewerk: Gewerk) -> int:
    """Beim Anlegen/Ändern eines Feinplanungs-/Montage-Termins: alle offenen
    Aufgaben mit FP+N/M±N-Regel (nach)berechnen (Phase 68)."""
    fp_termin = _erster_termin(session, gewerk, "feinplanung")
    montage_termin = _erster_termin(session, gewerk, "montage")
    geaendert = 0
    for aufgabe in (session.query(Aufgabe)
                    .filter(Aufgabe.gewerk_id == gewerk.id,
                            Aufgabe.status.in_(["offen", "in_arbeit", "wartet"]))):
        regel = (aufgabe.faellig_regel or "").strip().upper()
        if not (regel.startswith("FP") or regel.startswith("M")):
            continue
        neu = faelligkeit_berechnen(aufgabe.faellig_regel,
                                    aufgabe.erstellt_am or datetime.now(),
                                    fp_termin, montage_termin)
        if neu is not None and neu != aufgabe.faellig_am:
            aufgabe.faellig_am = neu
            geaendert += 1
    return geaendert


# --- Ampel + Status -------------------------------------------------------------

def planungs_ampel(session: Session, gewerk: Gewerk) -> dict:
    """Pflichtaufgaben-Stand (Konzept 3.2): gruen = alle erledigt, gelb =
    offen ohne Überfällige, rot = überfällig oder Warte-Frist gerissen."""
    aufgaben = (session.query(Aufgabe)
                .filter(Aufgabe.gewerk_id == gewerk.id,
                        Aufgabe.pflicht.is_(True),
                        Aufgabe.status != "entfaellt").all())
    gesamt = len(aufgaben)
    erledigt = sum(1 for a in aufgaben if a.status == "erledigt")
    jetzt = datetime.now()
    ueberfaellig = sum(
        1 for a in aufgaben if a.status != "erledigt"
        and ((a.faellig_am is not None and a.faellig_am < jetzt)
             or (a.status == "wartet" and a.wartet_frist_am is not None
                 and a.wartet_frist_am < jetzt)))
    farbe = ("gruen" if gesamt and erledigt == gesamt
             else ("rot" if ueberfaellig else "gelb"))
    if gesamt == 0:
        farbe = "gruen"
    return {"farbe": farbe, "erledigt": erledigt, "gesamt": gesamt,
            "ueberfaellig": ueberfaellig}


def projektstatus_berechnen(session: Session, projekt: Projekt) -> str:
    """Abgeleitet: Phase des am wenigsten fortgeschrittenen OFFENEN Gewerks;
    abgeschlossen, wenn alle Gewerke abgeschlossen/storniert sind."""
    gewerke = (session.query(Gewerk)
               .filter(Gewerk.projekt_id == projekt.id).all())
    offene = [g for g in gewerke if g.phase not in ("abgeschlossen", "storniert")]
    if not gewerke:
        status = "auftragseingang"
    elif not offene:
        status = "abgeschlossen"
    else:
        status = min(offene, key=lambda g: _PHASEN_RANG.get(g.phase, 0)).phase
    projekt.status_cache = status
    if status == "abgeschlossen" and projekt.abgeschlossen_am is None:
        projekt.abgeschlossen_am = datetime.now()
    elif status != "abgeschlossen":
        projekt.abgeschlossen_am = None
    return status


def projekt_zu_angebot(session: Session, angebot: Angebot):
    """(Projekt, Gewerk) zum Angebot über projekt_gewerk_id – sonst (None, None)."""
    if not angebot.projekt_gewerk_id:
        return None, None
    gewerk = session.get(Gewerk, angebot.projekt_gewerk_id)
    if gewerk is None:
        return None, None
    return session.get(Projekt, gewerk.projekt_id), gewerk


def offenes_projekt_fuer_vorgang(session: Session, vorgang_id: int | None) -> Projekt | None:
    """Pro Vorgang höchstens ein OFFENES Projekt (Konzept 3)."""
    if not vorgang_id:
        return None
    for projekt in (session.query(Projekt)
                    .filter(Projekt.vorgang_id == vorgang_id)
                    .order_by(Projekt.id.desc())):
        if projekt.status_cache != "abgeschlossen":
            return projekt
    return None


# --- Projekt-/Gewerk-Anlage -------------------------------------------------------

def projekt_anlegen(session: Session, angebot: Angebot, benutzer=None,
                    projektleiter_id: int | None = None,
                    notiz_kopf: str = "",
                    adresse: dict | None = None) -> Projekt:
    """Neues Projekt zum Vorgang des Angebots (Kopf aus Vorgang/Kunde)."""
    from app import vorgaenge as vorgaenge_modul
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    kunde = session.get(Kunde, angebot.kunde_id)
    kanal = kunde.vertriebskanal if kunde else ""
    if vorgang.lead_id:
        from app.models import Lead
        lead = session.get(Lead, vorgang.lead_id)
        kanal = (lead.vertriebskanal if lead else "") or kanal
    standard_pl = parameter_holen(session, "standard_projektleiter", "")
    if projektleiter_id is None and standard_pl.isdigit():
        projektleiter_id = int(standard_pl)
    from app import mail_vorlagen
    vertriebler = mail_vorlagen.vertriebler_fuer_angebot(session, angebot)
    projekt = Projekt(
        nummer=naechste_projektnummer(session),
        vorgang_id=vorgang.id, kunde_id=angebot.kunde_id,
        ausfuehrung_strasse=((adresse or {}).get("strasse")
                             or (kunde.strasse if kunde else "")),
        ausfuehrung_plz=((adresse or {}).get("plz")
                         or (kunde.plz if kunde else "")),
        ausfuehrung_ort=((adresse or {}).get("ort")
                         or (kunde.ort if kunde else "")),
        projektleiter_id=projektleiter_id,
        vertriebler_id=vertriebler.id if vertriebler else angebot.vertriebler_id,
        kanal=kanal or "", notiz_kopf=(notiz_kopf or "").strip()[:500],
        erstellt_von=benutzer.id if benutzer else None)
    session.add(projekt)
    session.flush()
    return projekt


def _dokument_ablegen(session: Session, projekt: Projekt, quelle_pfad: Path,
                      ordner: str, gewerk_id: int | None = None,
                      benutzer=None) -> None:
    """Kopiert eine Datei in die Projektablage und registriert sie."""
    import shutil
    if quelle_pfad is None or not Path(quelle_pfad).exists():
        return
    ziel_ordner = projekt_ordner(projekt) / ordner
    ziel_ordner.mkdir(parents=True, exist_ok=True)
    ziel = ziel_ordner / Path(quelle_pfad).name
    shutil.copyfile(quelle_pfad, ziel)
    session.add(ProjektDokument(
        projekt_id=projekt.id, gewerk_id=gewerk_id, ordner=ordner,
        dateiname=ziel.name, pfad=str(ziel),
        typ="pdf" if ziel.suffix.lower() == ".pdf" else "sonstige",
        quelle="auto", hochgeladen_von=benutzer.id if benutzer else None,
        erstellt_von=benutzer.id if benutzer else None))


def gewerk_anlegen(session: Session, projekt: Projekt, angebot: Angebot,
                   sparte: str, benutzer=None,
                   feinplaner_id: int | None = None,
                   elektroplaner_id: int | None = None,
                   quelle: str = "manuell") -> Gewerk:
    """Gewerk aus einem angenommenen Angebot: Phase Feinplanung, Auftragswert
    = Endbetrag brutto, IMMER-Pakete (Sparte + ALLE) aktivieren, Dokumente
    automatisch ablegen, Verlauf + Benachrichtigungen."""
    def _standard(schluessel):
        wert = parameter_holen(session, schluessel, "")
        return int(wert) if wert.isdigit() else None

    endbetrag = angebot.summen()["endbetrag"]
    gewerk = Gewerk(
        projekt_id=projekt.id, sparte=sparte, phase="auftragseingang",
        angebot_id=angebot.id, angebot_id_original=angebot.id,
        auftragswert_original=endbetrag, auftragswert_aktuell=endbetrag,
        feinplaner_id=feinplaner_id or _standard("standard_feinplaner"),
        elektroplaner_id=elektroplaner_id or _standard("standard_elektroplaner"),
        phase_geaendert_am=datetime.now(),
        erstellt_von=benutzer.id if benutzer else None)
    session.add(gewerk)
    session.flush()
    angebot.projekt_gewerk_id = gewerk.id
    if projekt.vertriebler_id is None and angebot.vertriebler_id:
        projekt.vertriebler_id = angebot.vertriebler_id
    # v15 (Phase 77): Steckbrief aus Erfassung + Auftragspositionen ableiten
    try:
        steckbrief_ableiten(session, gewerk, benutzer=benutzer)
    except Exception:
        pass   # Ableitung darf die Projektanlage nie blockieren
    # Ordner + automatische Ablage (Angebots-PDF nur bei Tool-Angeboten)
    ordner_anlegen(session, projekt)
    try:
        if not angebot.extern:
            from app import pdf_export
            _dokument_ablegen(session, projekt,
                              pdf_export.pdf_fuer_angebot(session, angebot),
                              "01 Angebot & Erfassung", gewerk.id, benutzer)
        elif angebot.extern_pdf_pfad:
            _dokument_ablegen(session, projekt, Path(angebot.extern_pdf_pfad),
                              "01 Angebot & Erfassung", gewerk.id, benutzer)
        _erfassungsprotokoll_ablegen(session, projekt, gewerk, angebot, benutzer)
    except Exception:
        pass   # Dokument-Ablage darf die Anlage nie blockieren
    # IMMER-Pakete der Sparte + ALLE aktivieren (Phase 65/66)
    try:
        from app import projektierung_logik
        logik = projektierung_logik.hole_logik(session)
        for paket in logik.immer_pakete(sparte):
            paket_aktivieren(session, gewerk, paket, benutzer=benutzer,
                             quelle=quelle if quelle == "migration" else "regel")
    except Exception:
        pass   # ohne importierte Logik bleibt das Gewerk ohne Startpakete
    projektstatus_berechnen(session, projekt)
    kunde = session.get(Kunde, projekt.kunde_id)
    verlauf(session, projekt.id,
            f"Gewerk {sparte} angelegt aus Angebot "
            f"{angebot.taifun_nummer or angebot.nummer}"
            + (" (automatisch aus Altbestand angelegt)"
               if quelle == "migration" else ""),
            benutzer=benutzer, gewerk_id=gewerk.id)
    benachrichtigen(
        session,
        [projekt.projektleiter_id, gewerk.feinplaner_id, gewerk.elektroplaner_id],
        f"Neues Gewerk {sparte} im Projekt {projekt.nummer} – "
        f"{kunde.anzeige_name if kunde else '?'}, {projekt.ausfuehrung_ort or '?'}",
        f"/projektierung/projekt/{projekt.id}", art="gewerk")
    return gewerk


def _erfassungsprotokoll_ablegen(session: Session, projekt: Projekt,
                                 gewerk: Gewerk, angebot: Angebot,
                                 benutzer=None) -> None:
    """Erfassungsprotokoll-PDF der verknüpften Erfassung automatisch ablegen."""
    from app.models import Erfassung
    erfassung = (session.query(Erfassung)
                 .filter(Erfassung.angebot_id == angebot.id).first())
    if erfassung is None:
        return
    from app import konfigurator as engine
    from app import logik as logik_modul
    from app import protokoll_pdf as protokoll_modul
    from app.logik import logik_fuer_sparte
    logik, bericht = logik_modul.hole_logik(session)
    if bericht is None or not getattr(bericht, "ok", False):
        return
    logik = logik_fuer_sparte(logik, erfassung.sparte or "WP") or logik
    antworten = json.loads(erfassung.antworten_json or "{}")
    kunde = session.get(Kunde, erfassung.kunde_id)
    pfad = protokoll_modul.erzeuge_protokoll_pdf(
        f"protokoll-erfassung-{erfassung.id}.pdf",
        f"Erfassung {erfassung.id} · {kunde.anzeige_name if kunde else ''}",
        [("Sparte", erfassung.sparte or "WP"),
         ("Kunde", kunde.anzeige_name if kunde else "?"),
         ("Status", erfassung.status)],
        engine.protokoll(logik, antworten),
        [g for g in (erfassung.gruende_text or "").splitlines() if g],
        freitext=erfassung.freitext if erfassung.typ == "freitext" else "")
    _dokument_ablegen(session, projekt, Path(pfad), "01 Angebot & Erfassung",
                      gewerk.id, benutzer)


# --- Projektsteckbrief (v15, Phase 77) ---------------------------------------

# Felder je Sparte (Reihenfolge = Anzeige im KV-Raster, zweispaltig)
STECKBRIEF_FELDER = {
    "WP": [("hersteller", "Hersteller"),
           ("leistungsklasse", "Leistungsklasse"),
           ("innengeraet", "Innengerät-Variante"),
           ("warmwasser", "Warmwasser"),
           ("aufstellort", "Aufstellort Außengerät"),
           ("zaehlerschrank", "Zählerschrank"),
           ("oeltank", "Öltankentsorgung"),
           ("oeltank_groesse", "Öltank: Größe"),
           ("oeltank_material", "Öltank: Material/Zugang"),
           ("alte_anlage", "Alte Anlage"),
           ("alte_anlage_standort", "Standort alte Anlage"),
           ("dyn_tarif", "Dynamischer Tarif"),
           ("imsys", "iMSys"),
           ("hems", "HEMS"),
           ("folierung", "Folierung"),
           ("kran", "Materiallift/Kran"),
           ("besonderheiten", "Besonderheiten")],
    "PV": [("module_kwp", "Module / kWp"),
           ("speicher", "Speicher"),
           ("wechselrichter", "Wechselrichter"),
           ("dach", "Dach"),
           ("geruest", "Gerüst"),
           ("besonderheiten", "Besonderheiten")],
    "KL": [("geraete", "Geräte"), ("besonderheiten", "Besonderheiten")],
    "WB": [("geraet", "Wallbox"), ("besonderheiten", "Besonderheiten")],
}


def steckbrief_felder(sparte: str) -> list[tuple[str, str]]:
    return STECKBRIEF_FELDER.get(sparte, STECKBRIEF_FELDER["KL"])


def _steckbrief_quellen(session: Session, gewerk: Gewerk) -> tuple[dict, set, str]:
    """(Erfassungs-Antworten, Positionsnummern des Auftrags, Profilname)."""
    from app.models import Erfassung
    antworten: dict = {}
    positionen: set[str] = set()
    profil_name = ""
    angebot = session.get(Angebot, gewerk.angebot_id) if gewerk.angebot_id else None
    if angebot is not None:
        import json as _json
        erfassung = (session.query(Erfassung)
                     .filter(Erfassung.angebot_id == angebot.id).first())
        if erfassung is not None and erfassung.antworten_json:
            try:
                antworten = _json.loads(erfassung.antworten_json)
            except ValueError:
                antworten = {}
        positionen = {p.pos_nr for p in angebot.positionen if p.pos_nr}
        from app import anhaenge as anhaenge_modul
        profil_name = anhaenge_modul.profilname_fuer(session, angebot)
    return antworten, positionen, profil_name


def _positions_treffer(quelle: str, positionen: set[str]) -> bool:
    """Quelle "030/031/045-056": Slash-Liste, Bereiche mit Bindestrich."""
    for teil in (quelle or "").split("/"):
        teil = teil.strip()
        if not teil:
            continue
        if "-" in teil:
            von, _, bis = teil.partition("-")
            if von.strip().isdigit() and bis.strip().isdigit():
                for n in range(int(von), int(bis) + 1):
                    if f"{n:03d}" in positionen:
                        return True
                continue
        if teil in positionen or teil.zfill(3) in positionen:
            return True
    return False


def _regel_anwenden(regel_text: str, roh_wert) -> str | None:
    """Mapping "Antwort→Text | Antwort2→Text2 | *→Text"; leer = Antwort 1:1.
    None = Regel passt nicht (keine Zuordnung gefunden)."""
    wert = "" if roh_wert is None else str(roh_wert).strip()
    regel_text = (regel_text or "").strip()
    if not regel_text:
        return wert or None
    stern = None
    for teil in regel_text.split("|"):
        teil = teil.strip()
        if "→" not in teil:
            # fester Text ohne Mapping (Positionsregeln)
            return teil
        links, _, rechts = teil.partition("→")
        links, rechts = links.strip(), rechts.strip()
        if links == "*":
            stern = rechts
        elif links.lower() == wert.lower():
            return rechts
    return stern


def steckbrief_ableiten(session: Session, gewerk: Gewerk, benutzer=None,
                        fp_antworten: dict | None = None) -> int:
    """v15 (Phase 77): Steckbrief aus Erfassungsantworten, Auftragspositionen
    und (ab Phase 80) FP-Antworten ableiten. Erste passende Regel je Feld
    gewinnt; manuell geänderte Felder werden nie überschrieben."""
    from app import projektierung_logik
    from app.models import SteckbriefWert
    logik = projektierung_logik.hole_logik(session)
    antworten, positionen, profil_name = _steckbrief_quellen(session, gewerk)
    fp_antworten = fp_antworten or {}
    vorhanden = {w.feld: w for w in
                 session.query(SteckbriefWert)
                 .filter(SteckbriefWert.gewerk_id == gewerk.id)}
    gesetzt: set[str] = set()
    geaendert = 0
    for regel in logik.steckbrief:
        if regel.sparte not in ("ALLE", gewerk.sparte):
            continue
        if regel.feld in gesetzt:
            continue
        eintrag = vorhanden.get(regel.feld)
        if eintrag is not None and eintrag.manuell:
            gesetzt.add(regel.feld)   # manuell hat Vorrang – Feld ist erledigt
            continue
        wert = None
        if regel.quelle_typ == "frage":
            if regel.quelle in antworten:
                wert = _regel_anwenden(regel.regel, antworten.get(regel.quelle))
        elif regel.quelle_typ == "fp_frage":
            if regel.quelle in fp_antworten:
                wert = _regel_anwenden(regel.regel, fp_antworten.get(regel.quelle))
        elif regel.quelle_typ == "position":
            if _positions_treffer(regel.quelle, positionen):
                wert = _regel_anwenden(regel.regel, "")
        elif regel.quelle_typ == "profil":
            wert = _regel_anwenden(regel.regel, profil_name)
        if wert is None or wert == "":
            continue
        wert = str(wert)[:500]
        if eintrag is None:
            session.add(SteckbriefWert(gewerk_id=gewerk.id, feld=regel.feld,
                                       wert=wert, manuell=False,
                                       geaendert_von=benutzer.id if benutzer else None))
            geaendert += 1
        elif eintrag.wert != wert:
            eintrag.wert = wert
            geaendert += 1
        gesetzt.add(regel.feld)
    session.flush()
    return geaendert


def steckbrief_daten(session: Session, gewerk_ids: list[int]) -> dict[int, dict]:
    """Feld → SteckbriefWert je Gewerk (für Akte, Sub-Mails, Montage)."""
    from app.models import SteckbriefWert
    daten: dict[int, dict] = {gid: {} for gid in gewerk_ids}
    if not gewerk_ids:
        return daten
    for w in (session.query(SteckbriefWert)
              .filter(SteckbriefWert.gewerk_id.in_(gewerk_ids))):
        daten.setdefault(w.gewerk_id, {})[w.feld] = w
    return daten


def sub_mail_platzhalter(session: Session, gewerk: Gewerk,
                         bemerkung: str = "") -> dict[str, str]:
    """v15 (Phase 79): Platzhalter der Sub-Mailvorlagen aus Projekt, Kunde,
    Steckbrief und Montagetermin. Fehlende Werte werden zu „–“, damit die
    Vorlage nie mit leeren Platzhaltern rausgeht."""
    projekt = session.get(Projekt, gewerk.projekt_id)
    kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
    werte = steckbrief_daten(session, [gewerk.id])[gewerk.id]

    def steck(*felder) -> str:
        teile = [werte[f].wert for f in felder if f in werte and werte[f].wert]
        return " · ".join(teile)

    ts = terminstatus(session, gewerk)
    termin = ts.get("termin")
    if termin is not None and termin.beginn:
        montagetermin = termin.beginn.strftime("%d.%m.%Y")
        if termin.ende and termin.ende.date() != termin.beginn.date():
            montagetermin += " – " + termin.ende.strftime("%d.%m.%Y")
        if not termin.kunde_bestaetigt:
            montagetermin += " (unbestätigt)"
    else:
        montagetermin = "noch nicht terminiert"
    projektleiter = (session.get(Benutzer, projekt.projektleiter_id)
                     if projekt and projekt.projektleiter_id else None)
    adresse = " ".join(t for t in [
        projekt.ausfuehrung_strasse if projekt else "",
        f"{projekt.ausfuehrung_plz} {projekt.ausfuehrung_ort}".strip()
        if projekt else ""] if t).strip()
    daten = {
        "kunde": kunde.anzeige_name if kunde else "–",
        "ausfuehrungsadresse": adresse or "–",
        "telefon_kunde": (kunde.telefon if kunde else "") or "–",
        "projektnummer": projekt.nummer if projekt else "–",
        "geraet": steck("hersteller", "leistungsklasse", "innengeraet") or "–",
        "aussengeraet_details": steck("aufstellort", "kran") or "–",
        "oeltank": steck("oeltank", "oeltank_groesse", "oeltank_material") or "–",
        "zaehlerschrank": steck("zaehlerschrank") or "–",
        "montagetermin": montagetermin,
        "ansprechpartner_friondo": projektleiter.name if projektleiter else "Friondo-Team",
        "bemerkung": (bemerkung or "").strip(),
    }
    return daten


def sub_mail_text(vorlage_text: str, platzhalter: dict[str, str]) -> str:
    """Platzhalter {name} ersetzen; unbekannte bleiben sichtbar stehen."""
    text = vorlage_text or ""
    for name, wert in platzhalter.items():
        text = text.replace("{" + name + "}", wert)
    return text


# --- Feinplanungs-Erfassung (v15, Phase 80) ----------------------------------

def fp_antworten(gewerk: Gewerk) -> dict:
    import json as _json
    try:
        return _json.loads(gewerk.fp_antworten_json or "{}")
    except ValueError:
        return {}


def fp_vorbelegen(session: Session, gewerk: Gewerk) -> int:
    """Beim ersten Öffnen: Antworten aus der Vertriebs-Erfassung übernehmen
    (Spalte vorbelegung_aus); vorbelegte Felder sind „vom Vertrieb“ markiert
    und müssen bestätigt oder geändert werden (Speichern der Seite hebt die
    Markierung auf)."""
    import json as _json

    from app import projektierung_logik
    logik = projektierung_logik.hole_logik(session)
    antworten = fp_antworten(gewerk)
    vertrieb, _positionen, _profil = _steckbrief_quellen(session, gewerk)
    try:
        vorbelegt = _json.loads(gewerk.fp_vorbelegt_json or "{}")
    except ValueError:
        vorbelegt = {}
    neu = 0
    for frage in logik.fp_fragen:
        if not frage.vorbelegung_aus or frage.key in antworten:
            continue
        wert = vertrieb.get(frage.vorbelegung_aus)
        if wert in (None, ""):
            continue
        antworten[frage.key] = str(wert)
        vorbelegt[frage.key] = "vom Vertrieb"
        neu += 1
    if neu:
        gewerk.fp_antworten_json = _json.dumps(antworten, ensure_ascii=False)
        gewerk.fp_vorbelegt_json = _json.dumps(vorbelegt, ensure_ascii=False)
        session.flush()
    return neu


def fp_seite_speichern(session: Session, gewerk: Gewerk, fragen,
                       form) -> None:
    """Antworten einer Seite übernehmen; bestätigte Felder verlieren das
    „vom Vertrieb“-Kennzeichen."""
    import json as _json
    antworten = fp_antworten(gewerk)
    try:
        vorbelegt = _json.loads(gewerk.fp_vorbelegt_json or "{}")
    except ValueError:
        vorbelegt = {}
    for frage in fragen:
        wert = (form.get(frage.key) or "").strip()[:500]
        if frage.typ == "zahl" and wert:
            wert = wert.replace(",", ".")
        antworten[frage.key] = wert
        vorbelegt.pop(frage.key, None)
    gewerk.fp_antworten_json = _json.dumps(antworten, ensure_ascii=False)
    gewerk.fp_vorbelegt_json = _json.dumps(vorbelegt, ensure_ascii=False)
    session.flush()


def fp_offene_pflicht(session: Session, gewerk: Gewerk) -> list[str]:
    from app import projektierung_logik
    logik = projektierung_logik.hole_logik(session)
    antworten = fp_antworten(gewerk)
    return [f.frage for f in logik.fp_fragen
            if f.pflicht and not str(antworten.get(f.key) or "").strip()]


def fp_abschliessen(session: Session, gewerk: Gewerk,
                    benutzer=None) -> tuple[bool, str]:
    """Abschluss der Feinplanungs-Erfassung: Pflichtfragen prüfen, Steckbrief
    aus den FP-Antworten ableiten (fp-Regeln stehen im Blatt zuerst), Heizlast
    übernehmen, Häkchen „Feinplanung erfasst“ setzen, Formular-Aufgabe
    erledigen und bedingte Pakete (bedingung KEY=Wert) aktivieren."""
    offen = fp_offene_pflicht(session, gewerk)
    if offen:
        return False, ("Pflichtfragen offen: " + " · ".join(offen[:4])
                       + (" …" if len(offen) > 4 else ""))
    from app import projektierung_logik
    logik = projektierung_logik.hole_logik(session)
    antworten = fp_antworten(gewerk)
    steckbrief_ableiten(session, gewerk, benutzer=benutzer,
                        fp_antworten=antworten)
    # Heizlast (FP-L01) in die bestehenden Gewerk-Felder übernehmen
    try:
        kw = float(str(antworten.get("FP-L01") or "").replace(",", "."))
        if kw > 0:
            gewerk.heizlast_kw = kw
            gewerk.heizlast_datum = datetime.now()
    except ValueError:
        pass
    gewerk.fp_abgeschlossen_am = datetime.now()
    if not gewerk.feinplanung_erfasst:
        gewerk.feinplanung_erfasst = True
        gewerk.feinplanung_erfasst_am = datetime.now()
    # Formular-Aufgabe "Feinplanungs-Erfassung" erledigen
    for aufgabe in (session.query(Aufgabe)
                    .filter(Aufgabe.gewerk_id == gewerk.id,
                            Aufgabe.aktion_typ == "formular",
                            Aufgabe.aktion_wert == "feinplanung_wp",
                            Aufgabe.status != "erledigt")):
        aufgabe.status = "erledigt"
        aufgabe.erledigt_am = datetime.now()
        aufgabe.erledigt_von = benutzer.id if benutzer else None
    # Bedingte Pakete: Paketregeln mit "KEY=Wert" auf die FP-Antworten
    aktiviert = []
    for regel in logik.regeln:
        bedingung = (regel.bedingung or "").strip()
        if bedingung.upper() == "IMMER" or "=" not in bedingung:
            continue
        if regel.sparte not in ("ALLE", gewerk.sparte):
            continue
        key, _, soll = bedingung.partition("=")
        ist = str(antworten.get(key.strip()) or "").strip().lower()
        if ist == soll.strip().lower():
            paket = logik.pakete.get(regel.paket_key)
            if paket is not None and paket_aktivieren(
                    session, gewerk, paket, benutzer=benutzer) is not None:
                aktiviert.append(paket.name)
    verlauf(session, gewerk.projekt_id,
            "Feinplanungs-Erfassung abgeschlossen"
            + (f" – Pakete aktiviert: {', '.join(aktiviert)}" if aktiviert else "")
            + f" (Gewerk {gewerk.sparte})",
            benutzer=benutzer, gewerk_id=gewerk.id)
    session.flush()
    return True, "Feinplanung erfasst – Steckbrief aktualisiert."


# --- Teams & Kalender (v15, Phase 75) ---------------------------------------

TEAM_FARBEN = ["#2d6bd6", "#1f9d55", "#c47a12", "#7a3fbf", "#cf3b2c",
               "#0f6e56", "#b0567a", "#5a6478", "#8a6d00", "#2a8fbd"]
SUB_FARBEN = ["#7d8f69", "#a8763e", "#6b7aa1", "#9a5b88", "#708090"]


def teams_vorbelegen(session: Session) -> int:
    """Stammdaten fest anlegen (idempotent je Name): Montageteam 1–10
    (Typ montage) und Subteam 1–5 (Typ sub); umbenennbar/deaktivierbar."""
    vorhanden = {t.name for t in session.query(Team)}
    neu = 0
    for i in range(1, 11):
        name = f"Montageteam {i}"
        if name not in vorhanden:
            session.add(Team(name=name, typ="montage",
                             farbe=TEAM_FARBEN[(i - 1) % len(TEAM_FARBEN)]))
            neu += 1
    for i in range(1, 6):
        name = f"Subteam {i}"
        if name not in vorhanden:
            session.add(Team(name=name, typ="sub",
                             farbe=SUB_FARBEN[(i - 1) % len(SUB_FARBEN)]))
            neu += 1
    session.flush()
    return neu


def arbeitstage_addieren(start: datetime, tage: int) -> datetime:
    """Beginn + N Arbeitstage (Mo–Fr); Standard-Vorbelegung Ende = +4."""
    aktuell = start
    rest = tage
    while rest > 0:
        aktuell += timedelta(days=1)
        if aktuell.weekday() < 5:
            rest -= 1
    return aktuell


def team_konflikte(session: Session, team_id: int, beginn: datetime,
                   ende: datetime, ausser_termin_id: int = 0) -> list[str]:
    """Konflikthinweis (kein Verbot): Termine desselben Teams, die sich mit
    dem Zeitraum überschneiden – als Textliste „PR-… (Kunde) 13.10.–16.10.“."""
    if not team_id or beginn is None:
        return []
    ende = ende or beginn
    treffer = []
    for t in (session.query(ProjektTermin)
              .filter(ProjektTermin.team_id == team_id,
                      ProjektTermin.typ == "montage",
                      ProjektTermin.beginn.isnot(None),
                      ProjektTermin.id != ausser_termin_id)):
        t_ende = t.ende or t.beginn
        if t.beginn.date() <= ende.date() and beginn.date() <= t_ende.date():
            projekt = session.get(Projekt, t.projekt_id)
            kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
            zeitraum = t.beginn.strftime("%d.%m.")
            if t_ende.date() != t.beginn.date():
                zeitraum += "–" + t_ende.strftime("%d.%m.")
            treffer.append(f"{projekt.nummer if projekt else '?'} "
                           f"({kunde.anzeige_name if kunde else '?'}) {zeitraum}")
    return treffer


ZUWEISUNGS_FELDER = {"wp": ("wp_team_id", "Montageteam"),
                     "elektro": ("elektro_team_id", "Elektro-Montageteam"),
                     "sub": ("sub_team_id", "Subteam")}


def team_termin_zuweisen(session: Session, gewerk: Gewerk, zweck: str,
                         team_id: int, beginn: datetime, ende,
                         kunde_bestaetigt: bool, benutzer=None
                         ) -> tuple[bool, str, list[str]]:
    """v15 (Phase 75): Zuweisungsdialog „Team + Termin“ – setzt das
    Zuweisungsfeld am Gewerk und legt einen (ganztägigen) Montagetermin an.
    Liefert (ok, meldung, konflikte). Ende leer = Beginn + 4 Arbeitstage."""
    if zweck not in ZUWEISUNGS_FELDER:
        return False, "Unbekannter Zuweisungszweck.", []
    feld, name = ZUWEISUNGS_FELDER[zweck]
    team = session.get(Team, team_id) if team_id else None
    if team is None:
        return False, f"{name}: bitte ein Team wählen.", []
    if beginn is None:
        return False, "Bitte einen Beginn wählen.", []
    if ende is None:
        ende = arbeitstage_addieren(beginn, 4)
    konflikte = team_konflikte(session, team.id, beginn, ende)
    setattr(gewerk, feld, team.id)
    termin = ProjektTermin(
        projekt_id=gewerk.projekt_id, gewerk_id=gewerk.id, typ="montage",
        beginn=beginn, ende=ende, team_id=team.id, ganztaegig=True,
        dauer_tage=max(1, (ende.date() - beginn.date()).days + 1),
        kunde_bestaetigt=bool(kunde_bestaetigt),
        bestaetigt_am=datetime.now() if kunde_bestaetigt else None,
        bestaetigt_quelle="manuell" if kunde_bestaetigt else "",
        erstellt_von=benutzer.id if benutzer else None)
    session.add(termin)
    session.flush()
    faelligkeiten_nachberechnen(session, gewerk)
    verlauf(session, gewerk.projekt_id,
            f"{name} zugewiesen: {team.name} · Montagetermin "
            f"{beginn.strftime('%d.%m.%Y')}–{ende.strftime('%d.%m.%Y')}"
            + (" · Kunde bestätigt" if kunde_bestaetigt else ""),
            benutzer=benutzer, gewerk_id=gewerk.id)
    meldung = f"{name} {team.name} zugewiesen, Termin angelegt."
    return True, meldung, konflikte


def termin_verschieben(session: Session, termin: ProjektTermin,
                       neues_datum, neues_team_id: int = 0,
                       art: str = "verschieben", benutzer=None) -> str:
    """Kalender-Drag (v15): Balken verschieben (Beginn-Delta auf Beginn+Ende,
    optional Teamwechsel) oder Ende ziehen. Protokolliert im Verlauf."""
    alt_text = termin.beginn.strftime("%d.%m.%Y")
    if termin.ende and termin.ende.date() != termin.beginn.date():
        alt_text += "–" + termin.ende.strftime("%d.%m.%Y")
    if art == "ende":
        neues_ende = datetime.combine(neues_datum, (termin.ende or termin.beginn).time())
        if neues_ende.date() < termin.beginn.date():
            neues_ende = datetime.combine(termin.beginn.date(), neues_ende.time())
        termin.ende = neues_ende
    else:
        delta = neues_datum - termin.beginn.date()
        termin.beginn = termin.beginn + delta
        if termin.ende:
            termin.ende = termin.ende + delta
        if neues_team_id and neues_team_id != (termin.team_id or 0):
            neues_team = session.get(Team, neues_team_id)
            if neues_team is not None:
                termin.team_id = neues_team.id
    termin.dauer_tage = max(1, ((termin.ende or termin.beginn).date()
                                - termin.beginn.date()).days + 1)
    gewerk = session.get(Gewerk, termin.gewerk_id) if termin.gewerk_id else None
    if gewerk is not None:
        faelligkeiten_nachberechnen(session, gewerk)
    neu_text = termin.beginn.strftime("%d.%m.%Y")
    if termin.ende and termin.ende.date() != termin.beginn.date():
        neu_text += "–" + termin.ende.strftime("%d.%m.%Y")
    verlauf(session, termin.projekt_id,
            f"Termin im Kalender {'verlängert' if art == 'ende' else 'verschoben'}: "
            f"{alt_text} → {neu_text}", benutzer=benutzer,
            gewerk_id=termin.gewerk_id)
    return neu_text


def startseiten_kacheln(session: Session) -> dict:
    """Phase 68: Kacheln zählen GEWERKE je Phase (mit Sparten-Untertitel)
    plus überfällige Aufgaben."""
    zaehler = {p: {"anzahl": 0, "sparten": {}} for p in
               ("auftragseingang", "feinplanung_vot", "planung",
                "montagevorbereitung", "montage", "abnahme_freigabe")}
    gewerke = session.query(Gewerk).all()
    for g in gewerke:
        if g.phase not in zaehler:
            continue
        zaehler[g.phase]["anzahl"] += 1
        zaehler[g.phase]["sparten"][g.sparte] = (
            zaehler[g.phase]["sparten"].get(g.sparte, 0) + 1)
    for eintrag in zaehler.values():
        eintrag["untertitel"] = " / ".join(
            f"{n} {s}" for s, n in sorted(eintrag["sparten"].items(),
                                          key=lambda kv: -kv[1]))
    jetzt = datetime.now()
    ueberfaellig = (session.query(Aufgabe)
                    .filter(Aufgabe.status.in_(["offen", "in_arbeit", "wartet"]),
                            Aufgabe.faellig_am.isnot(None),
                            Aufgabe.faellig_am < jetzt).count())
    zaehler["ueberfaellig"] = ueberfaellig
    # v15 (Phase 74): Unterminiert = Gewerke ab Phase Planung ohne Montagetermin
    ts = terminstatus_map(session, [g.id for g in gewerke])
    zaehler["unterminiert"] = sum(
        1 for g in gewerke
        if g.phase in ("planung", "montagevorbereitung", "montage")
        and ts.get(g.id, {}).get("status") == "unterminiert")
    return zaehler


# --- Phasenwechsel + Freigabe (Phase 67) --------------------------------------------

def _pflicht_offen_in_paketen(session: Session, gewerk: Gewerk,
                              paket_namen: tuple[str, ...]) -> tuple[int, int, bool]:
    """(offen, gesamt, paket_vorhanden) der Pflichtaufgaben in aktiven
    Paket-Instanzen, deren Name einem der übergebenen entspricht (v15)."""
    instanzen = [i for i in (session.query(AufgabenpaketInstanz)
                             .filter(AufgabenpaketInstanz.gewerk_id == gewerk.id,
                                     AufgabenpaketInstanz.deaktiviert_am.is_(None)))
                 if (i.paket_name or "").strip().lower()
                 in {n.lower() for n in paket_namen}]
    if not instanzen:
        return 0, 0, False
    ids = {i.id for i in instanzen}
    aufgaben = [a for a in session.query(Aufgabe)
                .filter(Aufgabe.gewerk_id == gewerk.id,
                        Aufgabe.pflicht.is_(True),
                        Aufgabe.status != "entfaellt")
                if a.paket_instanz_id in ids]
    offen = sum(1 for a in aufgaben if a.status != "erledigt")
    return offen, len(aufgaben), True


def waechter_pruefen(session: Session, gewerk: Gewerk, ziel: str) -> list[str]:
    """Unerfüllte Bedingungen für den Wechsel NACH RECHTS (v15, Phase 74);
    leer = Wechsel frei. Rückwärts liefert [] (Begründung regelt die Route).
    Solange die V2-Pakete (Phase 78) nicht existieren, greift je Stufe der
    dokumentierte Fallback (docs/projektierung-entscheidungen.md)."""
    reihen = {p: i for i, p in enumerate(
        ["auftragseingang", "feinplanung_vot", "planung",
         "montagevorbereitung", "montage", "abnahme_freigabe", "abgeschlossen"])}
    if ziel not in reihen or reihen.get(gewerk.phase, 0) >= reihen[ziel]:
        return []
    offen: list[str] = []
    # Auftragseingang → Feinplanung VOT: Pflichtaufgaben Paket "Auftragseingang"
    if reihen[ziel] >= reihen["feinplanung_vot"]:
        anz_offen, gesamt, da = _pflicht_offen_in_paketen(
            session, gewerk, ("Auftragseingang",))
        if da and anz_offen:
            offen.append(f"Paket Auftragseingang: {anz_offen} von {gesamt} "
                         "Pflichtaufgaben offen")
    # Feinplanung VOT → Planung: Feinplanung erfasst (Häkchen bis Phase 80)
    # + Pflichtaufgaben des V2-Pakets "Feinplanung VOT" (Phase 78)
    if reihen[ziel] >= reihen["planung"]:
        if not gewerk.feinplanung_erfasst:
            offen.append("Feinplanung nicht erfasst (Häkchen „Feinplanung "
                         "erfasst“ in der Akte)")
        anz_offen, gesamt, da = _pflicht_offen_in_paketen(
            session, gewerk, ("Feinplanung VOT",))
        if da and anz_offen:
            offen.append(f"Paket Feinplanung VOT: {anz_offen} von {gesamt} "
                         "Pflichtaufgaben offen")
    # Planung → Montagevorbereitung: Pflicht der Planungs-Pakete; ohne diese
    # Pakete (V1-Bestand) zählen alle Pflichtaufgaben (bisheriges Verhalten)
    if reihen[ziel] >= reihen["montagevorbereitung"]:
        anz_offen, gesamt, da = _pflicht_offen_in_paketen(
            session, gewerk, ("Planung WP", "Planung Elektro",
                              "Friondo Fit for Future", "Fit for Future"))
        if da:
            if anz_offen:
                offen.append(f"Planungs-Pakete: {anz_offen} von {gesamt} "
                             "Pflichtaufgaben offen")
        else:
            ampel = planungs_ampel(session, gewerk)
            if ampel["erledigt"] < ampel["gesamt"]:
                offen.append(f"{ampel['gesamt'] - ampel['erledigt']} Pflichtaufgaben "
                             f"offen ({ampel['erledigt']} von {ampel['gesamt']} erledigt)")
    # Montagevorbereitung → Montage: Freigabe-Aufgabe erledigt UND Termin
    if reihen[ziel] >= reihen["montage"]:
        freigabe = (session.query(Aufgabe)
                    .filter(Aufgabe.gewerk_id == gewerk.id,
                            Aufgabe.titel == "Projekt zur Montage freigegeben",
                            Aufgabe.status != "entfaellt").first())
        if freigabe is not None and freigabe.status != "erledigt":
            offen.append("Aufgabe „Projekt zur Montage freigegeben“ offen")
        termin = (session.query(ProjektTermin)
                  .filter(ProjektTermin.gewerk_id == gewerk.id,
                          ProjektTermin.typ == "montage",
                          ProjektTermin.beginn.isnot(None)).first())
        if termin is None:
            offen.append("Kein Montagetermin angelegt")
        elif not (termin.team_id or termin.person_id):
            offen.append("Montagetermin ohne Team/Person")
    # Montage → Abnahme & Freigabe: Häkchen "Montage fertig"
    if reihen[ziel] >= reihen["abnahme_freigabe"] and gewerk.montage_fertig_am is None:
        offen.append("Montage nicht fertig gemeldet (Montage-Backend oder "
                     "Projektierer)")
    # Abgeschlossen nur über die Rechnungsfreigabe
    if ziel == "abgeschlossen" and gewerk.freigabe_am is None:
        offen.append("Rechnung nicht freigegeben – bitte „Rechnung freigeben“ nutzen")
    return offen


def terminstatus_map(session: Session, gewerk_ids: list[int]) -> dict[int, dict]:
    """v15 (Phase 74): Terminstatus je Gewerk (berechnet).
    terminiert = Montagetermin mit Team UND Kunde bestätigt · unbestaetigt =
    Montagetermin vorhanden (ohne Bestätigung oder ohne Team) · unterminiert =
    kein Montagetermin. Maßgeblich ist der früheste zukünftige Montagetermin,
    sonst der letzte."""
    ergebnis: dict[int, dict] = {
        gid: {"status": "unterminiert", "termin": None} for gid in gewerk_ids}
    if not gewerk_ids:
        return ergebnis
    jetzt = datetime.now()
    beste: dict[int, ProjektTermin] = {}
    for t in (session.query(ProjektTermin)
              .filter(ProjektTermin.typ == "montage",
                      ProjektTermin.beginn.isnot(None),
                      ProjektTermin.gewerk_id.in_(gewerk_ids))
              .order_by(ProjektTermin.beginn)):
        aktuell = beste.get(t.gewerk_id)
        if aktuell is None:
            beste[t.gewerk_id] = t
        elif aktuell.beginn < jetzt:
            # spätere Termine gewinnen, bis der erste zukünftige gefunden ist
            beste[t.gewerk_id] = t
        # aktuell ist bereits der früheste zukünftige → behalten
    for gid, termin in beste.items():
        if termin.team_id and termin.kunde_bestaetigt:
            status = "terminiert"
        else:
            status = "unbestaetigt"
        ergebnis[gid] = {"status": status, "termin": termin}
    return ergebnis


def terminstatus(session: Session, gewerk: Gewerk) -> dict:
    """Terminstatus eines einzelnen Gewerks (v15, Phase 74)."""
    return terminstatus_map(session, [gewerk.id])[gewerk.id]


def phase_wechseln(session: Session, gewerk: Gewerk, ziel: str,
                   begruendung: str, benutzer=None) -> tuple[bool, str]:
    """Phasenwechsel mit Wächtern; Override und Rückwärts nur mit Begründung
    (immer protokolliert). Stornierte Gewerke sind gesperrt."""
    from app.models import GEWERK_PHASEN, GEWERK_PHASEN_NAMEN
    if gewerk.phase == "storniert":
        return False, "Storniertes Gewerk – Phasenwechsel nicht möglich."
    if ziel not in GEWERK_PHASEN or ziel == "storniert":
        return False, "Unbekannte Zielphase."
    if ziel == gewerk.phase:
        return False, "Das Gewerk ist bereits in dieser Phase."
    reihen = {p: i for i, p in enumerate(GEWERK_PHASEN)}
    rueckwaerts = reihen[ziel] < reihen[gewerk.phase]
    offen = waechter_pruefen(session, gewerk, ziel)
    begruendung = (begruendung or "").strip()[:500]
    if (offen or rueckwaerts) and not begruendung:
        if rueckwaerts:
            return False, ("Rückwärts-Wechsel nur mit Begründung "
                           "(Feld „Begründung“ ausfüllen).")
        return False, ("Wächter: " + " · ".join(offen)
                       + " – Override nur mit Begründung.")
    alt = gewerk.phase
    gewerk.phase = ziel
    gewerk.phase_geaendert_am = datetime.now()
    if ziel == "abnahme_freigabe" and gewerk.montage_fertig_am is None:
        gewerk.montage_fertig_am = datetime.now()   # Häkchen „Montage fertig" (Override)
    projekt = session.get(Projekt, gewerk.projekt_id)
    if projekt is not None:
        projektstatus_berechnen(session, projekt)
    text = (f"Phase des Gewerks {gewerk.sparte} geändert: "
            f"{GEWERK_PHASEN_NAMEN[alt]} → {GEWERK_PHASEN_NAMEN[ziel]}")
    if offen and begruendung:
        text += f" – trotz offener Punkte: {begruendung} ({' · '.join(offen)})"
    elif begruendung:
        text += f" – Begründung: {begruendung}"
    verlauf(session, gewerk.projekt_id, text, benutzer=benutzer,
            gewerk_id=gewerk.id)
    # Benachrichtigung an die Zugewiesenen des Gewerks (Phase 69)
    if projekt is not None:
        benachrichtigen(
            session,
            [projekt.projektleiter_id, gewerk.feinplaner_id,
             gewerk.elektroplaner_id],
            f"{projekt.nummer} {gewerk.sparte}: {GEWERK_PHASEN_NAMEN[ziel]}",
            f"/projektierung/projekt/{projekt.id}", art="phase")
    return True, f"Gewerk {gewerk.sparte}: {GEWERK_PHASEN_NAMEN[ziel]}."


def rechnung_freigeben(session: Session, gewerk: Gewerk, restarbeiten: str,
                       restarbeiten_text: str, benutzer=None) -> tuple[bool, str]:
    """„Rechnung freigeben“ (Phase 67): Restarbeiten-Pflichtfrage, Phase
    Abgeschlossen, Benachrichtigung an die Buchhaltung, Verlaufseintrag;
    Restarbeiten erzeugen automatisch eine Pflicht-Aufgabe (+14)."""
    if gewerk.phase != "abnahme_freigabe":
        return False, "Freigabe nur in Phase „Abnahme & Freigabe“ möglich."
    restarbeiten_text = (restarbeiten_text or "").strip()[:1000]
    if restarbeiten == "ja" and not restarbeiten_text:
        return False, "Bitte die Restarbeiten/Reklamationen beschreiben (Pflicht)."
    if restarbeiten not in ("keine", "ja"):
        return False, "Bitte angeben, ob Restarbeiten offen sind."
    gewerk.freigabe_am = datetime.now()
    gewerk.freigabe_von = benutzer.id if benutzer else None
    gewerk.restarbeiten_text = restarbeiten_text if restarbeiten == "ja" else ""
    gewerk.phase = "abgeschlossen"
    gewerk.phase_geaendert_am = datetime.now()
    projekt = session.get(Projekt, gewerk.projekt_id)
    if projekt is not None:
        projektstatus_berechnen(session, projekt)
    if restarbeiten == "ja":
        session.add(Aufgabe(
            gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id,
            titel=f"Restarbeiten: {restarbeiten_text[:250]}",
            rolle="projektierer",
            verantwortlich_id=_standard_benutzer(session, "projektierer",
                                                 gewerk, projekt),
            faellig_am=datetime.now() + timedelta(days=14),
            faellig_regel="+14", pflicht=True, reihenfolge=998,
            erstellt_von=benutzer.id if benutzer else None))
    verlauf(session, gewerk.projekt_id,
            f"Rechnung freigegeben ({gewerk.sparte}) – Restarbeiten: "
            + (restarbeiten_text or "keine"), benutzer=benutzer,
            gewerk_id=gewerk.id)
    # Buchhaltung benachrichtigen (Parametrierung „Buchhaltungs-Benutzer",
    # sonst alle Innendienst-Benutzer)
    buchhaltung = parameter_holen(session, "buchhaltung_benutzer", "")
    if buchhaltung.isdigit():
        ziele = [int(buchhaltung)]
    else:
        ziele = [b.id for b in session.query(Benutzer)
                 .filter(Benutzer.rolle == "innendienst",
                         Benutzer.aktiv.is_(True))]
    if projekt is not None:
        benachrichtigen(session, ziele,
                        f"Rechnung freigegeben: {projekt.nummer} "
                        f"({gewerk.sparte}) – bitte in TAIFUN abrechnen",
                        f"/projektierung/projekt/{projekt.id}", art="freigabe")
    return True, f"Rechnung freigegeben – Gewerk {gewerk.sparte} abgeschlossen."


def erwaehnungen_finden(session: Session, text: str) -> list[int]:
    """@Erwähnungen im Kommentartext: längster passender Benutzername nach
    jedem @ (Namen können Leerzeichen enthalten)."""
    treffer: list[int] = []
    if "@" not in (text or ""):
        return treffer
    text_klein = text.lower()
    for benutzer in session.query(Benutzer).filter(Benutzer.aktiv.is_(True)):
        if f"@{benutzer.name.lower()}" in text_klein and benutzer.id not in treffer:
            treffer.append(benutzer.id)
    return treffer


# --- Versionsfolge + Storno (Phase 66) ---------------------------------------------

def version_nachziehen(session: Session, angebot: Angebot) -> None:
    """Wenn eine neue Version „Angenommen" wird: Gewerk auf die neue Version
    und den neuen Auftragswert umhängen (Verlaufseintrag)."""
    if angebot.projekt_gewerk_id or not angebot.vorgaenger_id:
        return
    vorgaenger = session.get(Angebot, angebot.vorgaenger_id)
    kette = set()
    while vorgaenger is not None and vorgaenger.id not in kette:
        kette.add(vorgaenger.id)
        if vorgaenger.projekt_gewerk_id:
            break
        vorgaenger = (session.get(Angebot, vorgaenger.vorgaenger_id)
                      if vorgaenger.vorgaenger_id else None)
    if vorgaenger is None or not vorgaenger.projekt_gewerk_id:
        return
    gewerk = session.get(Gewerk, vorgaenger.projekt_gewerk_id)
    if gewerk is None or gewerk.phase == "storniert":
        return
    alt_wert = gewerk.auftragswert_aktuell
    neu_wert = angebot.summen()["endbetrag"]
    gewerk.angebot_id = angebot.id
    gewerk.auftragswert_aktuell = neu_wert
    angebot.projekt_gewerk_id = gewerk.id
    version = angebot.nummer.rpartition(".")[2]
    from app.templating import euro
    verlauf(session, gewerk.projekt_id,
            f"Auftragswert geändert von {euro(alt_wert)} auf {euro(neu_wert)} "
            f"(Version .{version if version.isdigit() else '?'} angenommen, "
            f"{angebot.nummer})", gewerk_id=gewerk.id)


def gewerk_stornieren(session: Session, gewerk: Gewerk, grund: str, text: str,
                      benutzer=None) -> tuple[bool, str]:
    """Storno (Phase 66): Gewerk „Storniert", verknüpftes Angebot „Abgelehnt"
    mit Grund „Storno nach Auftrag: <Grund>" inkl. monday-Rückspielung."""
    if gewerk.phase == "abgeschlossen":
        return False, "Abgeschlossene Gewerke können nicht storniert werden."
    if gewerk.phase == "storniert":
        return False, "Das Gewerk ist bereits storniert."
    if grund not in storno_gruende(session):
        return False, "Bitte einen Storno-Grund wählen."
    if grund == "Sonstiges" and not (text or "").strip():
        return False, "Bei „Sonstiges“ ist der Freitext Pflicht."
    gewerk.phase = "storniert"
    gewerk.phase_geaendert_am = datetime.now()
    gewerk.storno_grund = grund
    gewerk.storno_text = (text or "").strip()[:500]
    angebot = session.get(Angebot, gewerk.angebot_id) if gewerk.angebot_id else None
    if angebot is not None and angebot.status != "Abgelehnt":
        from app.models import angebot_status_setzen
        alter_status = angebot.status
        angebot_status_setzen(angebot, "Abgelehnt")
        angebot.ablehnungsgrund = f"Storno nach Auftrag: {grund}"
        angebot.ablehnungsgrund_text = gewerk.storno_text
        try:   # Prozess-Fix 27.09.2026: Lead-Phase mitziehen (Storno)
            from app import leadmanagement
            leadmanagement.phase_neu_berechnen(session, angebot.vorgang_id)
        except Exception:
            pass
        session.flush()
        if alter_status in ("Versendet", "Versendet (extern)", "Angenommen"):
            try:
                from app import monday_rueckspielung
                monday_rueckspielung.wert_aktualisieren(session, angebot,
                                                        "Storno nach Auftrag")
            except Exception:
                pass
    projekt = session.get(Projekt, gewerk.projekt_id)
    if projekt is not None:
        projektstatus_berechnen(session, projekt)
    verlauf(session, gewerk.projekt_id,
            f"Gewerk {gewerk.sparte} storniert – Grund: {grund}"
            + (f" ({gewerk.storno_text})" if gewerk.storno_text else ""),
            benutzer=benutzer, gewerk_id=gewerk.id)
    return True, f"Gewerk {gewerk.sparte} storniert."


# --- Migration Altbestand (Phase 66) ----------------------------------------------

def altbestand_migrieren(session: Session) -> list[str]:
    """Einmalig (Schalter): alle angenommenen Angebote ohne Gewerk → Projekt +
    Gewerk (Phase Feinplanung); Angebote desselben Vorgangs in EIN Projekt."""
    from app.models import einstellung_holen, einstellung_setzen
    if einstellung_holen(session, "migration_v11_projekte", "") == "erledigt":
        return []
    standard_pl = parameter_holen(session, "standard_projektleiter", "")
    projektleiter_id = int(standard_pl) if standard_pl.isdigit() else None
    if projektleiter_id is None:
        admin = (session.query(Benutzer)
                 .filter(Benutzer.rolle == "admin", Benutzer.aktiv.is_(True))
                 .order_by(Benutzer.id).first())
        projektleiter_id = admin.id if admin is not None else None
    angebote = (session.query(Angebot)
                .filter(Angebot.status == "Angenommen",
                        Angebot.projekt_gewerk_id.is_(None))
                .order_by(Angebot.id).all())
    projekte_neu = 0
    gewerke_neu = 0
    for angebot in angebote:
        from app import vorgaenge as vorgaenge_modul
        vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
        projekt = offenes_projekt_fuer_vorgang(session, vorgang.id)
        if projekt is None:
            projekt = projekt_anlegen(session, angebot,
                                      projektleiter_id=projektleiter_id)
            projekte_neu += 1
        gewerk_anlegen(session, projekt, angebot,
                       angebot.konfigurator_typ or "WP", quelle="migration")
        gewerke_neu += 1
    einstellung_setzen(session, "migration_v11_projekte", "erledigt")
    if gewerke_neu:
        return [f"Projektierung (v11): {projekte_neu} Projekte und {gewerke_neu} "
                "Gewerke aus dem Altbestand angelegt (Status Angenommen)"]
    return []
