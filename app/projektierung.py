# Projektierung V1 (v11, Phasen 64–71): Kernlogik des Moduls – Nummernkreis
# PR-JJNNNN, Parameter (Key-Value), Projekt-/Gewerk-Anlage aus angenommenen
# Angeboten, Aufgabenpakete mit Fälligkeitsregeln (+N / FP+N / M-N),
# Planungs-Ampel, abgeleiteter Projektstatus, Ordnerstruktur unter
# data/projekte/<PR>/, Verlauf (append-only) und Benachrichtigungen.

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app import config
from app.models import (Angebot, Aufgabe, AufgabenpaketInstanz, Benachrichtigung,
                        Benutzer, Gewerk, Kunde, Projekt, ProjektDokument,
                        ProjektTermin, ProjektVerlauf, Team, TeamMitglied,
                        TerminBesetzung, Vorgang)

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
                "montagevorbereitung": 3, "montage": 4, "abnahme": 5,
                "freigabe": 6, "abnahme_freigabe": 5}


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
    """Demo-Schalter (Phase 70): admin (Standard) = Modul nur für Admins.
    V3 (Phase 86): pilot = Admin + ausgewählte Benutzer (Pilotliste)."""
    wert = parameter_holen(session, "freigabe_modus", "admin").strip().lower()
    return wert if wert in ("admin", "pilot", "alle") else "admin"


def waechter_modus(session: Session) -> str:
    """v28 (PLAN_PROJ_V6 Phase 133): Wächter-Modus beim Phasenwechsel –
    „warnen“ (Standard: Wechsel immer möglich, offene Pflichtaufgaben werden
    gezeigt und im Verlauf vermerkt) oder „sperren“ (bisheriges Verhalten:
    Override nur mit Begründung). Parameter aus der Parametrierung
    (Abschnitt „Board & Wächter“)."""
    wert = parameter_holen(session, "waechter_modus", "warnen").strip().lower()
    return wert if wert in ("warnen", "sperren") else "warnen"


def pilot_benutzer_ids(session: Session) -> set[int]:
    """V3 (Phase 86): Benutzer-IDs der Pilotliste (Parameter pilot_benutzer)."""
    roh = parameter_holen(session, "pilot_benutzer", "")
    return {int(t) for t in roh.replace(";", ",").split(",") if t.strip().isdigit()}


def portal_badge(session: Session) -> str:
    """Startportal-Badge: Demo bei admin, „Pilot“ bei pilot, keins bei alle."""
    return {"admin": "Demo · Coming soon", "pilot": "Pilot"}.get(
        freigabe_modus(session), "")


def modul_sichtbar(session: Session, benutzer) -> bool:
    """Server-seitige Sichtbarkeitsprüfung des gesamten Moduls (Phase 70)."""
    if benutzer is None:
        return False
    if benutzer.rolle == "admin":
        return True
    # Bugfix 27.09.2026: HAUPTROLLE projektierung/montage sieht ihr Modul
    # auch im Demo-Modus - wer diese Rolle bekommt, wurde bewusst angelegt;
    # ein Monteur landete sonst nach dem Login auf dem leeren Portal.
    # Der Demo-Schalter versteckt das Modul weiter vor Innendienst/Vertrieb.
    if benutzer.rolle in ("projektierung", "montage"):
        return True
    modus = freigabe_modus(session)
    if modus == "pilot":
        # V3 (Phase 86): Stufe 1 – nur die Benutzer der Pilotliste
        return benutzer.id in pilot_benutzer_ids(session)
    if modus != "alle":
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
        from app import benachrichtigungen as mail_modul
        # v27 (PLAN_V17 Phase 128, Antwort Andreas 06.10.2026): Sofort-Mails gehen
        # in die Ausgangs-Warteschlange mail_ausgang (gleiche Transaktion wie die
        # Glocke, kein Netzaufruf hier); der Scheduler-Lauf „mail-ausgang“ sendet
        # nach dem Commit. Der Hotfix-Commit mitten in der Anfrage entfällt damit.
        try:
            mail_modul.sofort_versenden(session, sorted(gesehen), text, link, art)
        except Exception:
            pass   # Warteschlangen-Fehler blockieren das Tool nie


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
    "abnahme": 5, "abnahme & freigabe": 5,
    "freigabe": 6,
}


def paket_rang(paket_name: str) -> int:
    """Rang eines Pakets in der Boardspalten-Reihenfolge (unbekannt = 4,
    zwischen Montage und Abnahme, damit Sonderpakete nicht oben landen)."""
    return PAKET_PHASEN_RANG.get((paket_name or "").strip().lower(), 4)


def _schritt_sichtbar(session: Session, gewerk: Gewerk, bedingung: str) -> bool:
    """sichtbar_wenn "steckbrief:<feld>=<wert>": Schritt nur anlegen, wenn das
    Steckbrief-Feld den Wert hat (Vergleich ohne Gross/Klein).
    V4 (Phase 91.1): "sparte:PV|KL|WB" – Schritt nur für diese Sparten.
    v28 (PLAN_PROJ_V6 Phase 133): "foerderung:ja|nein" wertet
    bza.ist_gefoerdert(gewerk) aus; „unbekannt“ (None, z. B. TAIFUN ohne
    Antwort) blockiert nie – der Schritt bleibt sichtbar.
    Bedingungen der Form "<paket>.<nr>=<wert>" hängen an einer anderen
    Aufgabe und werden erst zur Laufzeit ausgewertet (abhaengige_pruefen)."""
    bedingung = (bedingung or "").strip()
    if not bedingung:
        return True
    if bedingung.lower().startswith("sparte:"):
        erlaubt = {s.strip().upper() for s in bedingung[7:].split("|")}
        return (gewerk.sparte or "").upper() in erlaubt
    if bedingung.lower().startswith("foerderung:"):
        soll = bedingung[len("foerderung:"):].strip().lower()
        if soll not in ("ja", "nein"):
            return True   # unbekannte Form – Warnung kommt aus „Logik prüfen“
        from app import bza as bza_modul
        ist = bza_modul.ist_gefoerdert(session, gewerk)
        if ist is None:
            return True
        return bool(ist) == (soll == "ja")
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
        aufgabe.entfaellt_grund = ""
    elif gueltige[auswahl]:
        aufgabe.status = "erledigt"
        aufgabe.erledigt_am = datetime.now()
        aufgabe.erledigt_von = benutzer.id if benutzer else None
        aufgabe.entfaellt_grund = ""
    else:
        aufgabe.status = "entfaellt"
        aufgabe.erledigt_am = None
        # v28 (PLAN_PROJ_V6 Phase 133): die gewählte Option ist der Grund
        aufgabe.entfaellt_grund = auswahl[:300]
    session.flush()
    return True


# --- v28 (PLAN_PROJ_V6 Phase 133): Zustand „entfällt“ mit Grund -----------------

ENTFAELLT_BEDINGUNG_PRAEFIX = "Bedingung nicht erfüllt"


def aufgabe_entfaellt(session: Session, aufgabe: Aufgabe, grund: str,
                      benutzer=None) -> tuple[bool, str]:
    """Aufgabe mit Pflicht-Grund (max. 300 Zeichen) auf „entfällt“ setzen –
    zählt für Wächter, Ampel und Kacheln nicht mehr als offen. Verlauf
    „Aufgabe „<Titel>“ entfällt – <Grund>“."""
    grund = " ".join((grund or "").split())[:300]
    if not grund:
        return False, "Bitte einen Grund angeben."
    if aufgabe.status == "entfaellt" and aufgabe.entfaellt_grund == grund:
        return True, "Aufgabe entfällt bereits."
    aufgabe.status = "entfaellt"
    aufgabe.entfaellt_grund = grund
    aufgabe.erledigt_am = datetime.now()
    aufgabe.erledigt_von = benutzer.id if benutzer else None
    aufgabe.wartet_frist_am = None
    verlauf(session, aufgabe.projekt_id,
            f"Aufgabe „{aufgabe.titel}“ entfällt – {grund}",
            benutzer=benutzer, gewerk_id=aufgabe.gewerk_id, aufgabe_id=aufgabe.id)
    session.flush()
    return True, f"Aufgabe „{aufgabe.titel}“ entfällt."


def aufgabe_wieder_aufnehmen(session: Session, aufgabe: Aufgabe,
                             benutzer=None) -> tuple[bool, str]:
    """Gegenstück: zurück auf „offen“, Grund geleert, Verlaufseintrag."""
    if aufgabe.status != "entfaellt":
        return False, "Die Aufgabe ist nicht auf „entfällt“."
    aufgabe.status = "offen"
    aufgabe.entfaellt_grund = ""
    aufgabe.erledigt_am = None
    aufgabe.erledigt_von = None
    verlauf(session, aufgabe.projekt_id,
            f"Aufgabe „{aufgabe.titel}“ wieder aufgenommen",
            benutzer=benutzer, gewerk_id=aufgabe.gewerk_id, aufgabe_id=aufgabe.id)
    session.flush()
    return True, f"Aufgabe „{aufgabe.titel}“ wieder offen."


def auswahl_folgen(session: Session, aufgabe: Aufgabe, benutzer=None) -> str:
    """V4 (Phase 91.2): Folgen einer Radio-Auswahl – Rückschreiben in den
    Steckbrief (aktion_wert „steckbrief:<feld>“, Kennzeichen manuell) und
    abhängige Schritte (sichtbar_wenn „<paket>.<nr>=<wert>“) nachziehen."""
    from app.models import SteckbriefWert
    meldung = ""
    wert = (aufgabe.aktion_wert or "")
    if "steckbrief:" in wert and aufgabe.gewerk_id:
        feld = wert.split("steckbrief:")[1].split(";")[0].strip()
        neu = {"ja": "ja", "nein": "nein"}.get((aufgabe.auswahl or "").lower())
        if feld and neu:
            eintrag = (session.query(SteckbriefWert)
                       .filter(SteckbriefWert.gewerk_id == aufgabe.gewerk_id,
                               SteckbriefWert.feld == feld).first())
            if eintrag is None:
                eintrag = SteckbriefWert(gewerk_id=aufgabe.gewerk_id, feld=feld)
                session.add(eintrag)
            if eintrag.wert != neu:
                eintrag.wert = neu
                eintrag.manuell = True
                eintrag.geaendert_von = benutzer.id if benutzer else None
                meldung = f"Steckbrief {feld} = {neu} übernommen."
    gewerk = session.get(Gewerk, aufgabe.gewerk_id) if aufgabe.gewerk_id else None
    if gewerk is not None:
        abhaengige_pruefen(session, gewerk)
    session.flush()
    return meldung


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
        verantwortlich = _aufgabe_aus_schritt(session, gewerk, projekt, instanz,
                                              schritt, jetzt, fp_termin,
                                              montage_termin, benutzer)
        if verantwortlich:
            zugewiesene.add(verantwortlich)
    session.flush()
    abhaengige_pruefen(session, gewerk)
    if zugewiesene and projekt is not None:
        benachrichtigen(session, zugewiesene,
                        f"Neue Aufgaben ({paket.name}) im Projekt {projekt.nummer}",
                        f"/projektierung/projekt/{projekt.id}", art="aufgabe")
    return instanz


def _aufgabe_aus_schritt(session: Session, gewerk: Gewerk, projekt, instanz,
                         schritt, jetzt, fp_termin, montage_termin,
                         benutzer=None) -> int | None:
    """Legt die Aufgabe zu einem Paket-Schritt an; liefert den Verantwortlichen."""
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
        sichtbar_wenn=_laufzeit_bedingung(getattr(schritt, "sichtbar_wenn", "")),
        erstellt_von=benutzer.id if benutzer else None))
    return verantwortlich


def steckbrief_schritte_nachziehen(session: Session, gewerk: Gewerk,
                                   benutzer=None) -> int:
    """V3 (Phase 84): Schritte mit Bedingung „steckbrief:<feld>=<wert>“ (v28:
    auch „foerderung:ja|nein“), die bei der Paket-Aktivierung fehlten (TAIFUN:
    Steckbrief kommt erst mit den Auftragsdaten), nachträglich anlegen.
    Bestehende Aufgaben bleiben; nicht mehr erfüllte Bedingungen setzen die
    Aufgabe auf „entfällt“ (abhaengige_pruefen). Liefert die Anzahl neu
    angelegter Schritte."""
    return bedingungen_nachziehen(session, gewerk, benutzer=benutzer)["neu"]


def foerderung_schritte_nachziehen(session: Session, gewerk: Gewerk,
                                   benutzer=None) -> dict:
    """v28 (PLAN_PROJ_V6 Phase 133): Hook nach einer Änderung von
    `kfw_gefoerdert` (Angebot/Auftragsdaten) bzw. des Förderblocks – zieht die
    Schritte mit `foerderung:ja|nein` (und alle anderen Bedingungen) nach."""
    return bedingungen_nachziehen(session, gewerk, benutzer=benutzer)


def _statische_bedingung(bedingung: str) -> bool:
    """Bedingungen, die beim Anlegen geprüft werden und sich später ändern
    können (Steckbrief, Förderung) – nicht sparte:, nicht <paket>.<nr>=."""
    b = (bedingung or "").strip().lower()
    return b.startswith("steckbrief:") or b.startswith("foerderung:")


def bedingungen_nachziehen(session: Session, gewerk: Gewerk,
                           benutzer=None) -> dict:
    """v28 (PLAN_PROJ_V6 Phase 133): Schritte mit Steckbrief-/Förder-Bedingung
    nachziehen – fehlende, jetzt erfüllte Schritte anlegen (wie V3), die
    Bedingung an bestehenden Aufgaben aus der Logik nachtragen (Altbestand vor
    v28 trägt sie nicht) und über abhaengige_pruefen nicht (mehr) erfüllte
    Schritte auf „entfällt“ mit Grund „Bedingung nicht erfüllt (<Bedingung>)“
    setzen bzw. wieder öffnen. Liefert {neu, entfaellt, offen}."""
    from app import projektierung_logik
    logik = projektierung_logik.hole_logik(session)
    projekt = session.get(Projekt, gewerk.projekt_id)
    jetzt = datetime.now()
    fp_termin = _erster_termin(session, gewerk, "feinplanung")
    montage_termin = _erster_termin(session, gewerk, "montage")
    angelegt = 0
    for instanz in (session.query(AufgabenpaketInstanz)
                    .filter(AufgabenpaketInstanz.gewerk_id == gewerk.id,
                            AufgabenpaketInstanz.version != "v1",
                            AufgabenpaketInstanz.deaktiviert_am.is_(None)).all()):
        paket = logik.pakete.get(instanz.paket_key)
        if paket is None:
            continue
        vorhandene = {a.reihenfolge: a for a in session.query(Aufgabe)
                      .filter(Aufgabe.paket_instanz_id == instanz.id)}
        for schritt in paket.schritte:
            bedingung = (getattr(schritt, "sichtbar_wenn", "") or "").strip()
            if not bedingung:
                continue
            aufgabe = vorhandene.get(schritt.nr)
            if aufgabe is not None:
                # Altbestand: Bedingung an der Aufgabe nachtragen (Laufzeit)
                if not (aufgabe.sichtbar_wenn or "") and _laufzeit_bedingung(bedingung):
                    aufgabe.sichtbar_wenn = _laufzeit_bedingung(bedingung)
                continue
            if not _statische_bedingung(bedingung):
                continue
            if not _schritt_sichtbar(session, gewerk, bedingung):
                continue
            _aufgabe_aus_schritt(session, gewerk, projekt, instanz, schritt,
                                 jetzt, fp_termin, montage_termin, benutzer)
            angelegt += 1
    if angelegt:
        session.flush()
    geaendert = abhaengige_pruefen(session, gewerk, benutzer=benutzer)
    return {"neu": angelegt, **geaendert}


# --- V3 (Phase 84): Auftragsdaten für TAIFUN-Aufträge ---------------------------

def ist_taifun_gewerk(session: Session, gewerk: Gewerk) -> bool:
    angebot = session.get(Angebot, gewerk.angebot_id) if gewerk.angebot_id else None
    return bool(angebot is not None and angebot.extern)


def auftragsdaten_felder(session: Session, sparte: str) -> list:
    from app import projektierung_logik
    return projektierung_logik.hole_logik(session).auftragsdaten_felder(sparte)


def auftragsdaten_normalisieren(feld, roh: str) -> str:
    """Formularwert → Steckbrief-Text (ja/nein klein, Zahl ohne Einheit)."""
    wert = (roh or "").strip()
    if feld.typ == "ja_nein":
        return {"ja": "ja", "nein": "nein"}.get(wert.lower(), "")
    if feld.typ == "auswahl" and feld.optionen and wert not in feld.optionen:
        return ""
    if feld.typ == "zahl":
        zahl = _zahl_aus(wert)
        return _menge_text(zahl) if zahl is not None else ""
    return wert[:500]


def auftragsdaten_werte(session: Session, gewerk: Gewerk) -> dict[str, str]:
    """Aktuelle Steckbrief-Werte für die Vorbelegung des Formulars."""
    return {f: w.wert for f, w in steckbrief_daten(session, [gewerk.id])[gewerk.id].items()}


def auftragsdaten_speichern(session: Session, gewerk: Gewerk, werte: dict,
                            benutzer=None) -> int:
    """Schreibt die Auftragsdaten als Steckbrief (quelle = auftragsdaten, nicht
    manuell – die FP-Erfassung darf sie später überschreiben). Manuell in der
    Akte geänderte Felder bleiben unangetastet. Danach werden steckbrief-
    abhängige Paketschritte nachgezogen."""
    from app.models import SteckbriefWert
    vorhanden = {w.feld: w for w in session.query(SteckbriefWert)
                 .filter(SteckbriefWert.gewerk_id == gewerk.id)}
    geaendert = 0
    for feld in auftragsdaten_felder(session, gewerk.sparte):
        if feld.feld not in werte:
            continue
        wert = auftragsdaten_normalisieren(feld, werte.get(feld.feld) or "")
        eintrag = vorhanden.get(feld.feld)
        if eintrag is not None and eintrag.manuell:
            continue
        if eintrag is None:
            if not wert:
                continue
            session.add(SteckbriefWert(gewerk_id=gewerk.id, feld=feld.feld,
                                       wert=wert, manuell=False,
                                       quelle="auftragsdaten",
                                       geaendert_von=benutzer.id if benutzer else None))
            geaendert += 1
        elif eintrag.wert != wert or eintrag.quelle != "auftragsdaten":
            eintrag.wert = wert
            eintrag.quelle = "auftragsdaten"
            eintrag.geaendert_von = benutzer.id if benutzer else None
            geaendert += 1
    session.flush()
    neu = steckbrief_schritte_nachziehen(session, gewerk, benutzer=benutzer)
    verlauf(session, gewerk.projekt_id,
            f"Auftragsdaten erfasst (Gewerk {gewerk.sparte}, {geaendert} Felder"
            + (f", {neu} Schritte nachgezogen" if neu else "") + ")",
            benutzer=benutzer, gewerk_id=gewerk.id)
    return geaendert


def auftragsdaten_aus_pdf(pdf) -> dict:
    """Stufe 2 (vorbereitet, nicht gebaut): Text aus dem TAIFUN-Angebots-PDF
    lesen und das Auftragsdaten-Formular vorbelegen ({feld: wert}). Bis dahin
    leer – das Formular wird von Hand ausgefüllt."""
    return {}


def _laufzeit_bedingung(bedingung: str) -> str:
    """Bedingungen, die an der Aufgabe gespeichert und zur Laufzeit erneut
    ausgewertet werden: "<paket_key>.<nr>=<wert>" (V4) sowie seit v28
    "steckbrief:<feld>=<wert>" und "foerderung:ja|nein" (Phase 133 – damit
    abhaengige_pruefen nicht mehr erfüllte Schritte auf „entfällt“ setzt).
    sparte: wirkt nur beim Anlegen."""
    import re
    bedingung = (bedingung or "").strip()
    if re.fullmatch(r"[\w-]+\.\d+\s*=\s*.+", bedingung):
        return bedingung[:100]
    if _statische_bedingung(bedingung):
        return bedingung[:100]
    return ""


def abhaengige_pruefen(session: Session, gewerk: Gewerk, benutzer=None) -> dict:
    """V4 (Phase 91.2): Aufgaben mit Laufzeit-Bedingung "<paket>.<nr>=<wert>"
    (z. B. HEMS-Inbetriebnahme nur bei fit_for_future.1 = Ja): trifft die
    Auswahl der Bezugsaufgabe nicht zu, steht die Aufgabe auf „entfällt“;
    trifft sie (wieder) zu, geht sie auf „offen“ zurück.
    v28 (PLAN_PROJ_V6 Phase 133): zusätzlich "steckbrief:<feld>=<wert>" und
    "foerderung:ja|nein" (bza.ist_gefoerdert; unbekannt = sichtbar). Nicht
    erfüllt → „entfällt“ mit Grund „Bedingung nicht erfüllt (<Bedingung>)“ und
    Verlaufseintrag; wieder erfüllt → „offen“ (nur, wenn der Grund der
    automatische war – von Hand gesetztes „entfällt“ bleibt). Rückgabe
    {entfaellt, offen} (Anzahl der Änderungen)."""
    import re
    ergebnis = {"entfaellt": 0, "offen": 0}
    aufgaben = (session.query(Aufgabe)
                .filter(Aufgabe.gewerk_id == gewerk.id).all())
    instanzen = {i.id: i for i in session.query(AufgabenpaketInstanz)
                 .filter(AufgabenpaketInstanz.gewerk_id == gewerk.id)}
    for aufgabe in aufgaben:
        bedingung = (aufgabe.sichtbar_wenn or "").strip()
        if not bedingung:
            continue
        instanz = instanzen.get(aufgabe.paket_instanz_id or 0)
        if instanz is not None and instanz.deaktiviert_am is not None:
            continue
        m = re.fullmatch(r"([\w-]+)\.(\d+)\s*=\s*(.+)", bedingung)
        if m:
            paket_key, nr, soll = m.group(1), int(m.group(2)), m.group(3).strip().lower()
            bezug = next((a for a in aufgaben
                          if a.reihenfolge == nr and a.paket_instanz_id in instanzen
                          and instanzen[a.paket_instanz_id].paket_key == paket_key
                          and instanzen[a.paket_instanz_id].deaktiviert_am is None), None)
            if bezug is None:
                continue
            erfuellt = (bezug.auswahl or "").strip().lower() == soll
            # ohne Antwort an der Bezugsaufgabe bleibt alles wie es ist
            entscheidbar = bool(bezug.auswahl or "")
        elif _statische_bedingung(bedingung):
            erfuellt = _schritt_sichtbar(session, gewerk, bedingung)
            entscheidbar = True
        else:
            continue
        automatisch = (not (aufgabe.entfaellt_grund or "")
                       or aufgabe.entfaellt_grund.startswith(ENTFAELLT_BEDINGUNG_PRAEFIX))
        if entscheidbar and not erfuellt and aufgabe.status not in ("entfaellt", "erledigt"):
            aufgabe.status = "entfaellt"
            aufgabe.entfaellt_grund = f"{ENTFAELLT_BEDINGUNG_PRAEFIX} ({bedingung})"[:300]
            aufgabe.erledigt_am = datetime.now()
            aufgabe.erledigt_von = benutzer.id if benutzer else None
            verlauf(session, aufgabe.projekt_id,
                    f"Aufgabe „{aufgabe.titel}“ entfällt – {aufgabe.entfaellt_grund}",
                    benutzer=benutzer, gewerk_id=gewerk.id, aufgabe_id=aufgabe.id)
            ergebnis["entfaellt"] += 1
        elif erfuellt and aufgabe.status == "entfaellt" and automatisch:
            aufgabe.status = "offen"
            aufgabe.entfaellt_grund = ""
            aufgabe.erledigt_am = None
            aufgabe.erledigt_von = None
            ergebnis["offen"] += 1
    if ergebnis["entfaellt"] or ergebnis["offen"]:
        session.flush()
    return ergebnis


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
                   quelle: str = "manuell",
                   benachrichtigen_an: bool = True) -> Gewerk:
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
               if quelle == "migration" else "")
            + (" (Bestandsimport)" if quelle == "bestand" else ""),
            benutzer=benutzer, gewerk_id=gewerk.id)
    if not benachrichtigen_an:
        return gewerk      # V3 (Phase 85): Massenimport ohne Glocken-Flut
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
           ("restoel_liter", "Öltank: Restöl (Liter)"),          # V4 Phase 91.3
           ("stemmarbeiten", "Stemmarbeiten"),                    # V4 Phase 91.3
           ("erdleitung_m", "Erdleitung / Erdarbeiten (m)"),      # V4 Phase 91.3
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
    """Feste Felder der Sparte + zusätzliche Felder, die das Blatt Steckbrief
    (Spalten eingabe/bezeichnung, V3 Phase 84) für die Auftragsdaten definiert."""
    felder = list(STECKBRIEF_FELDER.get(sparte, STECKBRIEF_FELDER["KL"]))
    try:
        from app import projektierung_logik
        bekannt = {f for f, _ in felder}
        for zusatz in projektierung_logik.hole_logik().auftragsdaten_felder(sparte):
            if zusatz.feld not in bekannt:
                # vor „Besonderheiten“ einsortieren (bleibt letzte Zeile)
                stelle = next((i for i, (f, _) in enumerate(felder)
                               if f == "besonderheiten"), len(felder))
                felder.insert(stelle, (zusatz.feld, zusatz.bezeichnung))
                bekannt.add(zusatz.feld)
    except Exception:
        pass
    return felder


def _positions_mengen(session: Session, gewerk: Gewerk) -> dict[str, float]:
    """V4 (Phase 91.3): Menge je Positionsnummer des Auftrags (voll
    berechnete Positionen; EP/bauseits/alternativ zählen nicht)."""
    angebot = session.get(Angebot, gewerk.angebot_id) if gewerk.angebot_id else None
    mengen: dict[str, float] = {}
    if angebot is None:
        return mengen
    for p in angebot.positionen:
        if not p.pos_nr or p.ep_flag or p.bauseits or p.alternativ:
            continue
        mengen[p.pos_nr] = mengen.get(p.pos_nr, 0.0) + float(p.menge or 0)
    return mengen


def _menge_text(zahl: float) -> str:
    return (str(int(zahl)) if zahl == int(zahl) else f"{zahl:g}".replace(".", ","))


def _quelle_mengen(quelle: str, mengen: dict[str, float]) -> float:
    """Summe der Mengen aller Positionen der Quelle („126“, „139/140“)."""
    summe = 0.0
    for teil in (quelle or "").split("/"):
        teil = teil.strip()
        if teil:
            summe += mengen.get(teil, 0.0) or mengen.get(teil.zfill(3), 0.0)
    return summe


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
    if isinstance(roh_wert, float):
        roh_wert = _menge_text(roh_wert)     # V4: 8.0 -> "8"
    wert = "" if roh_wert is None else str(roh_wert).strip()
    regel_text = (regel_text or "").strip()
    if not regel_text:
        return wert or None
    stern = None
    for teil in regel_text.split("|"):
        teil = teil.strip()
        if "→" not in teil:
            # fester Text ohne Mapping (Positionsregeln)
            return teil.replace("{wert}", wert)
        links, _, rechts = teil.partition("→")
        links, rechts = links.strip(), rechts.strip()
        if links == "*":
            stern = rechts.replace("{wert}", wert) if wert else None
        elif links.lower() == wert.lower():
            return rechts.replace("{wert}", wert)
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
    mengen = _positions_mengen(session, gewerk)
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
        if regel.quelle_typ == "auftragsdaten":
            continue                  # V3: reine Formular-Definition
        # V3 (Phase 84): TAIFUN-Auftragsdaten überschreibt nur die FP-Erfassung
        if (eintrag is not None and (eintrag.quelle or "") == "auftragsdaten"
                and regel.quelle_typ != "fp_frage"):
            gesetzt.add(regel.feld)
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
                # V4 (Phase 91.3): {menge} = Summe der Positionsmengen
                if wert and "{menge}" in wert:
                    menge = _quelle_mengen(regel.quelle, mengen)
                    if menge <= 0:
                        continue
                    wert = wert.replace("{menge}", _menge_text(menge))
        elif regel.quelle_typ == "fest":
            wert = regel.regel
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
        elif eintrag.wert != wert or (eintrag.quelle or ""):
            eintrag.wert = wert
            eintrag.quelle = ""       # FP-Wert ersetzt Auftragsdaten
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
        "geraet": steck("hersteller", "serie_modell", "leistungsklasse",
                        "innengeraet") or "–",
        "aussengeraet_details": steck("aufstellort", "kran") or "–",
        "oeltank": steck("oeltank", "oeltank_groesse", "oeltank_material") or "–",
        "zaehlerschrank": steck("zaehlerschrank") or "–",
        # V4 (Phase 91.3): Restöl, Stemmarbeiten, Erdarbeiten
        "restoel": _restoel_text(steck("restoel_liter")),
        "stemmarbeiten": ("Stemmarbeiten sind laut Angebot enthalten (Pos. 126) – "
                          "bitte mit anbieten"
                          if steck("stemmarbeiten").lower().startswith("ja")
                          else "Stemmarbeiten nicht Teil des Auftrags"),
        "erdarbeiten": _erdarbeiten_text(steck("erdleitung_m")),
        "montagetermin": montagetermin,
        "ansprechpartner_friondo": projektleiter.name if projektleiter else "Friondo-Team",
        "bemerkung": (bemerkung or "").strip(),
    }
    return daten


def _zahl_aus(text: str) -> float | None:
    import re
    m = re.search(r"\d+(?:[.,]\d+)*", text or "")
    if not m:
        return None
    roh = m.group(0)
    if "," in roh:
        roh = roh.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", roh):
        roh = roh.replace(".", "")      # Tausenderpunkte (3.000)
    try:
        return float(roh)
    except ValueError:
        return None


def _restoel_text(wert: str) -> str:
    zahl = _zahl_aus(wert)
    if zahl is None or zahl <= 0:
        return "kein Restöl angegeben"
    return f"Restöl ca. {_menge_text(zahl)} l"


def _erdarbeiten_text(wert: str) -> str:
    zahl = _zahl_aus(wert)
    if zahl is None or zahl <= 0:
        return "keine Erdarbeiten laut Auftrag"
    return (f"Erdarbeiten: Leitungsgraben ca. {_menge_text(zahl)} m für die "
            "Erdleitung Außengerät ↔ Haus")


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
    # V4 (Phase 91.3): ausgeblendete Fragen (sichtbar_wenn) sind nie Pflicht
    return [f.frage for f in logik.fp_fragen
            if f.pflicht and f.sichtbar(antworten)
            and not str(antworten.get(f.key) or "").strip()]


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


# --- v28 (PLAN_PROJ_V6 Phase 135): ein Termin-Dialog, Besetzung je Termin -------

# Art im Dialog → (typ, zweck, Anzeigename, Zuweisungszweck am Gewerk)
TERMIN_ARTEN = {
    "montage": ("montage", "wp", "Montage (WP)", "wp"),
    "elektro": ("montage", "elektro", "Elektro-Montage", "elektro"),
    "sub": ("sub", "sub", "Sub-Einsatz", "sub"),
    "feinplanung": ("feinplanung", "", "Feinplanung VOT", ""),
    "abnahme": ("abnahme", "", "Abnahme", ""),
    "sonstige": ("sonstige", "", "Sonstiges", ""),
}
TERMIN_ARTEN_REIHENFOLGE = ("montage", "elektro", "sub", "feinplanung", "abnahme",
                            "sonstige")
# Rollen, die als „Person“ an Feinplanung/Abnahme/Sonstiges stehen können
# [ANNAHME Plan: Projektierung + Innendienst + Admin]
PERSON_ROLLEN = ("projektierung", "innendienst", "admin")


def termin_art(termin: ProjektTermin) -> str:
    """Art-Schlüssel eines Termins aus typ/zweck (Altbestand: montage ohne
    zweck = wp; sub-Termine = Sub-Einsatz)."""
    if termin.typ == "montage":
        return "elektro" if (termin.zweck or "") == "elektro" else "montage"
    if termin.typ == "sub":
        return "sub"
    return termin.typ if termin.typ in TERMIN_ARTEN else "sonstige"


def termin_art_name(termin: ProjektTermin) -> str:
    return TERMIN_ARTEN[termin_art(termin)][2]


def termin_zeitraum_text(termin: ProjektTermin) -> str:
    """„13.10.2026–15.10.2026“ bzw. „13.10.2026 09:00“ für Verlauf/Meldungen."""
    if termin.beginn is None:
        return "–"
    text = termin.beginn.strftime("%d.%m.%Y")
    if not termin.ganztaegig or termin.beginn.time() != datetime.min.time():
        text += termin.beginn.strftime(" %H:%M")
    if termin.ende and termin.ende.date() != termin.beginn.date():
        text += "–" + termin.ende.strftime("%d.%m.%Y")
    return text


def team_mitglieder_ids(session: Session, team_id: int | None) -> list[int]:
    """Benutzer-IDs der Team-Mitglieder (Stammdaten = Vorlage der Besetzung)."""
    if not team_id:
        return []
    return [m.benutzer_id for m in (session.query(TeamMitglied)
                                    .filter(TeamMitglied.team_id == team_id)
                                    .order_by(TeamMitglied.id))]


def montage_benutzer(session: Session) -> list[Benutzer]:
    """Alle aktiven Benutzer mit Rolle Montage (Haupt- oder Zusatzrolle) –
    Mehrfachauswahl „Besetzung“ im Termin-Dialog."""
    return sorted([b for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
                   if b.hat_rolle("montage")], key=lambda b: b.name.lower())


def personen_benutzer(session: Session) -> list[Benutzer]:
    """Benutzer, die als „Person“ an einem Termin stehen können."""
    return sorted([b for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
                   if any(b.hat_rolle(r) for r in PERSON_ROLLEN)],
                  key=lambda b: b.name.lower())


def besetzung_ids(session: Session, termin_id: int) -> list[int]:
    """Benutzer-IDs der Besetzung eines Termins (Reihenfolge = Anlage)."""
    return [b.benutzer_id for b in (session.query(TerminBesetzung)
                                    .filter(TerminBesetzung.termin_id == termin_id)
                                    .order_by(TerminBesetzung.id))]


def besetzung_map(session: Session, termin_ids: list[int]) -> dict[int, list[int]]:
    """Besetzung mehrerer Termine in einer Abfrage (Akte, Kalender, Montage)."""
    ergebnis: dict[int, list[int]] = {tid: [] for tid in termin_ids}
    if not termin_ids:
        return ergebnis
    for b in (session.query(TerminBesetzung)
              .filter(TerminBesetzung.termin_id.in_(termin_ids))
              .order_by(TerminBesetzung.id)):
        ergebnis.setdefault(b.termin_id, []).append(b.benutzer_id)
    return ergebnis


def _name_kurz(name: str) -> str:
    """„Rene Golaschewski“ → „R. Golaschewski“; „D. Jobelius“ bleibt."""
    teile = (name or "").split()
    if len(teile) >= 2 and len(teile[0].rstrip(".")) > 1:
        return f"{teile[0][0]}. {' '.join(teile[1:])}"
    return name or ""


def besetzung_namen(session: Session, termin_id: int, kurz: bool = True,
                    benutzer_map: dict | None = None) -> str:
    """Namen der Besetzung: kurz = „A. Müller, B. Schmidt +2“, sonst alle
    vollen Namen kommagetrennt (Montagebericht, Tooltip)."""
    ids = besetzung_ids(session, termin_id)
    if not ids:
        return ""
    if benutzer_map is None:
        benutzer_map = {b.id: b for b in session.query(Benutzer)
                        .filter(Benutzer.id.in_(ids))}
    namen = [benutzer_map[i].name for i in ids if i in benutzer_map]
    if not kurz:
        return ", ".join(namen)
    kurze = [_name_kurz(n) for n in namen]
    if len(kurze) > 2:
        return ", ".join(kurze[:2]) + f" +{len(kurze) - 2}"
    return ", ".join(kurze)


def besetzung_setzen(session: Session, termin: ProjektTermin, benutzer_ids,
                     benutzer=None) -> None:
    """Ersetzt die Besetzung eines Termins (nur aktive Montage-Benutzer,
    Dubletten entfallen) und protokolliert die Änderung im Verlauf."""
    alt = besetzung_ids(session, termin.id)
    neu: list[int] = []
    for wert in benutzer_ids or []:
        try:
            bid = int(wert)
        except (TypeError, ValueError):
            continue
        if bid and bid not in neu:
            neu.append(bid)
    if set(neu) == set(alt):
        return
    (session.query(TerminBesetzung)
     .filter(TerminBesetzung.termin_id == termin.id).delete())
    for bid in neu:
        session.add(TerminBesetzung(termin_id=termin.id, benutzer_id=bid,
                                    erstellt_von=benutzer.id if benutzer else None))
    session.flush()
    namen = besetzung_namen(session, termin.id, kurz=False) or "–"
    verlauf(session, termin.projekt_id,
            f"Besetzung Termin {termin_art_name(termin)} "
            f"{termin_zeitraum_text(termin)}: {namen}",
            benutzer=benutzer, gewerk_id=termin.gewerk_id)


def person_konflikte(session: Session, benutzer_ids, beginn: datetime, ende,
                     ausser_termin_id: int = 0) -> list[str]:
    """Warnung je Person (kein Verbot): „<Name> ist am 12.11. bereits bei
    PR-26… (Kunde)“ – andere Termine, in denen die Person eingeteilt ist."""
    ids = [int(b) for b in (benutzer_ids or []) if str(b).strip().lstrip("-").isdigit()]
    if not ids or beginn is None:
        return []
    ende = ende or beginn
    treffer: list[str] = []
    namen = {b.id: b.name for b in session.query(Benutzer).filter(Benutzer.id.in_(ids))}
    zeilen = (session.query(TerminBesetzung, ProjektTermin)
              .join(ProjektTermin, ProjektTermin.id == TerminBesetzung.termin_id)
              .filter(TerminBesetzung.benutzer_id.in_(ids),
                      ProjektTermin.beginn.isnot(None),
                      ProjektTermin.id != ausser_termin_id)
              .order_by(ProjektTermin.beginn).all())
    for besetzung, t in zeilen:
        t_ende = t.ende or t.beginn
        if not (t.beginn.date() <= ende.date() and beginn.date() <= t_ende.date()):
            continue
        projekt = session.get(Projekt, t.projekt_id)
        kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
        treffer.append(f"{namen.get(besetzung.benutzer_id, '?')} ist am "
                       f"{max(t.beginn.date(), beginn.date()).strftime('%d.%m.')} bereits bei "
                       f"{projekt.nummer if projekt else '?'}"
                       + (f" ({kunde.anzeige_name})" if kunde else ""))
    return treffer


def montage_dauer_standard(session: Session) -> int:
    """Parameter montage_dauer_tage_standard (Arbeitstage, Standard 5)."""
    try:
        return max(1, int(str(parameter_holen(session, "montage_dauer_tage_standard",
                                              "5")).strip() or 5))
    except ValueError:
        return 5


def _zuweisungs_aufgabe_setzen(session: Session, gewerk: Gewerk, name: str,
                               status: str, benutzer=None) -> int:
    """Aufgabe „<Team> zuweisen“ (kalender/montage) erledigen bzw. wieder
    öffnen (V4 Phase 91.1 / v28 Phase 135 Löschen)."""
    geaendert = 0
    for aufgabe in (session.query(Aufgabe)
                    .filter(Aufgabe.gewerk_id == gewerk.id,
                            Aufgabe.aktion_typ == "kalender",
                            Aufgabe.aktion_wert == "montage",
                            Aufgabe.titel == f"{name} zuweisen")):
        if status == "erledigt" and aufgabe.status in ("offen", "in_arbeit", "wartet"):
            aufgabe.status = "erledigt"
            aufgabe.erledigt_am = datetime.now()
            aufgabe.erledigt_von = benutzer.id if benutzer else None
            geaendert += 1
        elif status == "offen" and aufgabe.status == "erledigt":
            aufgabe.status = "offen"
            aufgabe.erledigt_am = None
            aufgabe.erledigt_von = None
            geaendert += 1
    return geaendert


def termin_speichern(session: Session, gewerk: Gewerk, daten: dict,
                     benutzer=None, termin: ProjektTermin | None = None
                     ) -> tuple[bool, str, list[str]]:
    """v28 (PLAN_PROJ_V6 Phase 135): EINE Anlage-/Bearbeiten-Funktion für alle
    Terminarten des Dialogs. `daten`: art (montage|elektro|sub|feinplanung|
    abnahme|sonstige), team_id, sub_id, person_id, beginn (date), uhrzeit
    (HH:MM oder leer = ganztägig), ende (date|None), besetzung (Liste IDs),
    besetzung_gesetzt (bool – False = Vorbelegung aus dem Team), kunde_bestaetigt,
    notiz, dauer_tage (optional). Beim Bearbeiten (termin gesetzt) bleibt die Art
    gesperrt; Teamwechsel setzt das Zuweisungsfeld am Gewerk um („Montageteam
    gewechselt: alt → neu“). Montage/Elektro-Montage: Team Pflicht, Aufgabe
    „<Team> zuweisen“ erledigt, Fälligkeiten nachberechnet. Liefert
    (ok, meldung, konflikte) – Konflikte (Team und je Person) sind Warnungen."""
    bearbeiten = termin is not None
    art = (daten.get("art") or "").strip().lower()
    if bearbeiten:
        art = termin_art(termin)
    if art not in TERMIN_ARTEN:
        return False, "Bitte eine Terminart wählen.", []
    typ, zweck, art_name, zuweisung = TERMIN_ARTEN[art]

    def _id(name):
        try:
            return int(daten.get(name) or 0) or None
        except (TypeError, ValueError):
            return None
    team_id, sub_id, person_id = _id("team_id"), _id("sub_id"), _id("person_id")
    team = session.get(Team, team_id) if team_id else None
    if art in ("montage", "elektro"):
        if team is None:
            return False, "Montagetermine brauchen ein Team – bitte Team wählen.", []
        sub_id = None
    elif art == "sub":
        if team is None and not sub_id:
            return False, "Sub-Einsatz: bitte Subteam oder Subunternehmer wählen.", []
    elif art in ("feinplanung", "abnahme"):
        if not person_id:
            return False, f"{art_name}: bitte eine Person wählen.", []
        team = None
    beginn_datum = daten.get("beginn")
    if isinstance(beginn_datum, datetime):
        beginn_datum = beginn_datum.date()
    if beginn_datum is None:
        return False, "Bitte einen Beginn angeben.", []
    uhrzeit = (daten.get("uhrzeit") or "").strip()
    ganztaegig = not uhrzeit
    if uhrzeit:
        try:
            stunde, _, minute = uhrzeit.partition(":")
            beginn = viertelstunde(datetime.combine(
                beginn_datum, datetime.min.time()).replace(
                hour=int(stunde), minute=int(minute or 0)))
        except ValueError:
            return False, "Uhrzeit nicht lesbar (HH:MM).", []
    else:
        beginn = datetime.combine(beginn_datum, datetime.min.time())
    ende_datum = daten.get("ende")
    if isinstance(ende_datum, datetime):
        ende_datum = ende_datum.date()
    if ende_datum is None:
        if art in ("montage", "elektro"):
            dauer = daten.get("dauer_tage") or montage_dauer_standard(session)
            try:
                dauer = max(1, int(dauer))
            except (TypeError, ValueError):
                dauer = montage_dauer_standard(session)
            ende_datum = arbeitstage_addieren(beginn, dauer - 1).date()
        else:
            ende_datum = beginn_datum
    if ende_datum < beginn_datum:
        ende_datum = beginn_datum
    if ganztaegig:
        ende = datetime.combine(ende_datum, datetime.min.time())
    elif ende_datum == beginn_datum:
        ende = None          # Termin mit Uhrzeit an einem Tag: kein Ende (wie bisher)
    else:
        ende = datetime.combine(ende_datum, beginn.time())
    kunde_bestaetigt = bool(daten.get("kunde_bestaetigt"))
    notiz = (daten.get("notiz") or "").strip()[:500]
    # Konflikte (Warnung): Team und je Person
    konflikte: list[str] = []
    if team is not None and typ == "montage":
        konflikte += team_konflikte(session, team.id, beginn, ende or beginn,
                                    ausser_termin_id=termin.id if bearbeiten else 0)
    alt_team_id = termin.team_id if bearbeiten else None
    if bearbeiten:
        alt_text = termin_zeitraum_text(termin)
        termin.beginn, termin.ende = beginn, ende
        termin.team_id = team.id if team is not None else None
        termin.sub_id, termin.person_id = sub_id, person_id
        termin.ganztaegig = ganztaegig
        termin.notiz = notiz
        if kunde_bestaetigt and not termin.kunde_bestaetigt:
            termin.kunde_bestaetigt = True
            termin.bestaetigt_am = datetime.now()
            termin.bestaetigt_quelle = "manuell"
        elif not kunde_bestaetigt and termin.kunde_bestaetigt:
            termin.kunde_bestaetigt = False
            termin.bestaetigt_am = None
            termin.bestaetigt_quelle = ""
        if not termin.zweck and zweck:
            termin.zweck = zweck
    else:
        termin = ProjektTermin(
            projekt_id=gewerk.projekt_id, gewerk_id=gewerk.id, typ=typ, zweck=zweck,
            beginn=beginn, ende=ende, team_id=team.id if team is not None else None,
            sub_id=sub_id, person_id=person_id, ganztaegig=ganztaegig,
            kunde_bestaetigt=kunde_bestaetigt,
            bestaetigt_am=datetime.now() if kunde_bestaetigt else None,
            bestaetigt_quelle="manuell" if kunde_bestaetigt else "",
            notiz=notiz, erstellt_von=benutzer.id if benutzer else None)
        session.add(termin)
        session.flush()
    termin.dauer_tage = max(1, ((termin.ende or termin.beginn).date()
                                - termin.beginn.date()).days + 1)
    # Zuweisungsfeld am Gewerk + Aufgabe „<Team> zuweisen“
    if zuweisung and team is not None:
        feld, name = ZUWEISUNGS_FELDER[zuweisung]
        alt = getattr(gewerk, feld)
        setattr(gewerk, feld, team.id)
        if bearbeiten and alt_team_id and alt_team_id != team.id:
            alt_team = session.get(Team, alt_team_id)
            verlauf(session, gewerk.projekt_id,
                    f"{name} gewechselt: {alt_team.name if alt_team else alt_team_id} "
                    f"→ {team.name}", benutzer=benutzer, gewerk_id=gewerk.id)
        if typ == "montage":
            _zuweisungs_aufgabe_setzen(session, gewerk, name, "erledigt", benutzer)
    # Besetzung: explizit gesetzt → übernehmen; sonst Vorlage aus dem Team
    # (neu) bzw. bei Teamwechsel neu belegen, wenn sie der alten Vorlage entsprach
    if team is not None and typ in ("montage", "sub"):
        if daten.get("besetzung_gesetzt"):
            besetzung_setzen(session, termin, daten.get("besetzung") or [], benutzer)
        elif not bearbeiten:
            besetzung_setzen(session, termin, team_mitglieder_ids(session, team.id),
                             benutzer)
        elif alt_team_id != team.id:
            bisher = set(besetzung_ids(session, termin.id))
            if not bisher or bisher == set(team_mitglieder_ids(session, alt_team_id)):
                besetzung_setzen(session, termin, team_mitglieder_ids(session, team.id),
                                 benutzer)
            else:
                verlauf(session, gewerk.projekt_id,
                        "Besetzung beibehalten (von Hand gesetzt)",
                        benutzer=benutzer, gewerk_id=gewerk.id)
    elif bearbeiten and team is None:
        besetzung_setzen(session, termin, [], benutzer)
    konflikte += person_konflikte(session, besetzung_ids(session, termin.id),
                                  beginn, ende or beginn,
                                  ausser_termin_id=termin.id)
    nachberechnet = 0
    if typ in ("feinplanung", "montage"):
        nachberechnet = faelligkeiten_nachberechnen(session, gewerk)
    wer = ""
    if team is not None:
        wer = f" · {team.name}"
    elif sub_id:
        from app.models import Subunternehmer
        sub = session.get(Subunternehmer, sub_id)
        wer = f" · {sub.firma}" if sub else ""
    elif person_id:
        person = session.get(Benutzer, person_id)
        wer = f" · {person.name}" if person else ""
    if bearbeiten:
        verlauf(session, gewerk.projekt_id,
                f"Termin {art_name} bearbeitet: {alt_text} → "
                f"{termin_zeitraum_text(termin)}{wer}"
                + (" · Kunde bestätigt" if termin.kunde_bestaetigt else "")
                + (f" – {nachberechnet} Fälligkeiten nachberechnet" if nachberechnet else ""),
                benutzer=benutzer, gewerk_id=gewerk.id)
        meldung = f"Termin {art_name} {termin_zeitraum_text(termin)} gespeichert."
    else:
        verlauf(session, gewerk.projekt_id,
                f"Termin {art_name} {termin_zeitraum_text(termin)} angelegt ({gewerk.sparte})"
                + wer + (" · Kunde bestätigt" if kunde_bestaetigt else "")
                + (f" · Besetzung: {besetzung_namen(session, termin.id, kurz=False)}"
                   if typ in ("montage", "sub") and besetzung_ids(session, termin.id) else "")
                + (f" – {nachberechnet} Fälligkeiten nachberechnet" if nachberechnet else ""),
                benutzer=benutzer, gewerk_id=gewerk.id)
        if zuweisung and team is not None:
            meldung = f"{ZUWEISUNGS_FELDER[zuweisung][1]} {team.name} zugewiesen, Termin angelegt."
        else:
            meldung = f"Termin {art_name} {termin_zeitraum_text(termin)} angelegt."
    session.flush()
    daten["termin_id"] = termin.id      # für den Aufrufer (Outlook, JSON)
    return True, meldung, konflikte


def termin_loeschen(session: Session, termin: ProjektTermin, grund: str,
                    benutzer=None) -> tuple[bool, str]:
    """v28 (PLAN_PROJ_V6 Phase 135): Termin mit Pflicht-Grund löschen –
    Besetzung mit, Verlauf „Termin <Art> <Datum> gelöscht – <Grund>“; war es
    der maßgebliche Montagetermin (Terminstatus), wird die Aufgabe
    „Montageteam zuweisen“ wieder offen und das Gewerk steht im Board unter
    „unterminiert“. Outlook-Storno macht die Route vorher (best effort)."""
    grund = " ".join((grund or "").split())[:300]
    if not grund:
        return False, "Bitte einen Grund angeben."
    gewerk = session.get(Gewerk, termin.gewerk_id) if termin.gewerk_id else None
    art = termin_art(termin)
    typ = termin.typ
    text = f"Termin {termin_art_name(termin)} {termin_zeitraum_text(termin)} gelöscht – {grund}"
    massgeblich = False
    if gewerk is not None and typ == "montage":
        ts = terminstatus(session, gewerk)
        massgeblich = ts.get("termin") is not None and ts["termin"].id == termin.id
    (session.query(TerminBesetzung)
     .filter(TerminBesetzung.termin_id == termin.id).delete())
    projekt_id, gewerk_id = termin.projekt_id, termin.gewerk_id
    session.delete(termin)
    session.flush()
    if gewerk is not None and typ == "montage":
        zuweisung = "elektro" if art == "elektro" else "wp"
        name = ZUWEISUNGS_FELDER[zuweisung][1]
        weitere = (session.query(ProjektTermin)
                   .filter(ProjektTermin.gewerk_id == gewerk.id,
                           ProjektTermin.typ == "montage",
                           ProjektTermin.zweck.in_(["elektro"] if art == "elektro"
                                                   else ["wp", ""])).count())
        if (massgeblich or art == "elektro") and not weitere:
            if _zuweisungs_aufgabe_setzen(session, gewerk, name, "offen", benutzer):
                text += f" · Aufgabe „{name} zuweisen“ wieder offen"
        faelligkeiten_nachberechnen(session, gewerk)
    verlauf(session, projekt_id, text, benutzer=benutzer, gewerk_id=gewerk_id)
    return True, "Termin gelöscht."


def team_termin_zuweisen(session: Session, gewerk: Gewerk, zweck: str,
                         team_id: int, beginn: datetime, ende,
                         kunde_bestaetigt: bool, benutzer=None
                         ) -> tuple[bool, str, list[str]]:
    """v15 (Phase 75): Zuweisungsdialog „Team + Termin“ – seit v28 ein dünner
    Aufruf von termin_speichern (Besetzung = Team-Mitglieder, zweck gesetzt).
    Bleibt für Bestandsimport und Alt-Formulare erhalten. Ende leer = Beginn +
    (Standarddauer − 1) Arbeitstage."""
    if zweck not in ZUWEISUNGS_FELDER:
        return False, "Unbekannter Zuweisungszweck.", []
    feld, name = ZUWEISUNGS_FELDER[zweck]
    if not team_id or session.get(Team, team_id) is None:
        return False, f"{name}: bitte ein Team wählen.", []
    if beginn is None:
        return False, "Bitte einen Beginn wählen.", []
    art = {"wp": "montage", "elektro": "elektro", "sub": "sub"}[zweck]
    return termin_speichern(session, gewerk, {
        "art": art, "team_id": team_id, "beginn": beginn,
        "ende": ende, "kunde_bestaetigt": kunde_bestaetigt}, benutzer=benutzer)


def termin_verschieben(session: Session, termin: ProjektTermin,
                       neues_datum, neues_team_id: int = 0,
                       art: str = "verschieben", benutzer=None) -> str:
    """Kalender-Drag (v15): Balken verschieben (Beginn-Delta auf Beginn+Ende,
    optional Teamwechsel) oder Ende ziehen. Protokolliert im Verlauf.
    v28 (PLAN_PROJ_V6 Phase 135): bei Teamwechsel wird die Besetzung aus dem
    neuen Team neu vorbelegt, falls sie der Mitgliederliste des alten Teams
    entsprach (oder leer war); sonst bleibt sie – Verlauf „Besetzung
    beibehalten (von Hand gesetzt)“. Das Zuweisungsfeld am Gewerk folgt."""
    alt_text = termin.beginn.strftime("%d.%m.%Y")
    if termin.ende and termin.ende.date() != termin.beginn.date():
        alt_text += "–" + termin.ende.strftime("%d.%m.%Y")
    gewerk = session.get(Gewerk, termin.gewerk_id) if termin.gewerk_id else None
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
                alt_team_id = termin.team_id
                termin.team_id = neues_team.id
                bisher = set(besetzung_ids(session, termin.id))
                if not bisher or bisher == set(team_mitglieder_ids(session, alt_team_id)):
                    besetzung_setzen(session, termin,
                                     team_mitglieder_ids(session, neues_team.id),
                                     benutzer)
                else:
                    verlauf(session, termin.projekt_id,
                            "Besetzung beibehalten (von Hand gesetzt)",
                            benutzer=benutzer, gewerk_id=termin.gewerk_id)
                if gewerk is not None and termin.typ == "montage":
                    zuweisung = "elektro" if (termin.zweck or "") == "elektro" else "wp"
                    if termin.zweck == "sub":
                        zuweisung = "sub"
                    setattr(gewerk, ZUWEISUNGS_FELDER[zuweisung][0], neues_team.id)
    termin.dauer_tage = max(1, ((termin.ende or termin.beginn).date()
                                - termin.beginn.date()).days + 1)
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


# --- v28 (PLAN_PROJ_V6 Phase 135): Terminvorschläge Stufe 1 (Tool-Daten) ---------

VORSCHLAG_WOCHEN = 26


def naechster_montag(datum) -> date:
    """Erster Montag ≥ datum [ANNAHME Plan: Vorschläge beginnen montags]."""
    if isinstance(datum, datetime):
        datum = datum.date()
    return datum + timedelta(days=(7 - datum.weekday()) % 7)


def _adresse_text(strasse: str, plz: str, ort: str) -> str:
    return ", ".join(t for t in [(strasse or "").strip(),
                                 f"{plz or ''} {ort or ''}".strip()] if t)


def routing_konfiguriert(session: Session) -> bool:
    """Routing-Anbieter des Lead-Moduls (ors/google mit Schlüssel); Luftlinie
    gilt als „kein Anbieter“ – dann Umweg „–“ (Hinweis im Dialog)."""
    from app import leadmanagement
    anbieter = (leadmanagement.parameter_holen(session, "routing_anbieter", "luftlinie")
                or "luftlinie").strip().lower()
    if anbieter == "ors":
        return bool(leadmanagement.parameter_holen(session, "ors_api_key", ""))
    if anbieter == "google":
        return bool(leadmanagement.parameter_holen(session, "google_api_key", ""))
    return False


def terminvorschlaege(session: Session, gewerk: Gewerk, team_id: int | None = None,
                      dauer_tage: int | None = None, heute=None) -> dict:
    """Stufe 1 aus Tool-Daten: je aktivem Montage-Team (oder nur team_id) die
    ersten freien Fenster (max. 5) ohne Überschneidung mit dessen Terminen im
    Tool, Suche bis 26 Wochen voraus, Beginn montags. Frühester Beginn =
    max(heute + vorschlag_vorlauf_wochen, Lieferdatum der letzten UGL-Bestellung
    + 1 Arbeitstag). Bewertung Umweg = Fahrzeit vom letzten Einsatz des Teams
    vor dem Fenster zur Ausführungsadresse und weiter zum ersten Einsatz danach
    (ersatzweise Startadresse `montage_startadresse`), über app/routing.py –
    ohne Routing-Anbieter Umweg „–“. Netzaufrufe (Geocoding, Matrix) laufen
    nur nach `verbindung_freigeben` (die Routing-/Geocoding-Funktionen geben
    die Sitzung selbst frei). Stufe 2 (`vorschlag_outlook`) wird nur angelegt,
    nicht ausgewertet. Liefert {vorschlaege: [...], hinweis, dauer_tage,
    fruehester, routing}."""
    from app.models import UglBestellung
    heute = heute or datetime.now()
    heute_datum = heute.date() if isinstance(heute, datetime) else heute
    dauer = dauer_tage or montage_dauer_standard(session)
    try:
        dauer = max(1, int(dauer))
    except (TypeError, ValueError):
        dauer = montage_dauer_standard(session)
    try:
        vorlauf = float(str(parameter_holen(session, "vorschlag_vorlauf_wochen", "4")
                            ).replace(",", ".") or 4)
    except ValueError:
        vorlauf = 4.0
    fruehester = heute_datum + timedelta(days=int(round(vorlauf * 7)))
    letzte = (session.query(UglBestellung)
              .filter(UglBestellung.gewerk_id == gewerk.id,
                      UglBestellung.lieferdatum.isnot(None))
              .order_by(UglBestellung.lieferdatum.desc()).first())
    if letzte is not None and letzte.lieferdatum is not None:
        nach_lieferung = arbeitstage_addieren(letzte.lieferdatum, 1).date()
        fruehester = max(fruehester, nach_lieferung)
    start = naechster_montag(fruehester)
    teams = (session.query(Team)
             .filter(Team.aktiv.is_(True), Team.typ == "montage")
             .order_by(Team.id).all())
    if team_id:
        teams = [t for t in teams if t.id == team_id]
    projekt = session.get(Projekt, gewerk.projekt_id)
    ziel_adresse = _adresse_text(projekt.ausfuehrung_strasse, projekt.ausfuehrung_plz,
                                 projekt.ausfuehrung_ort) if projekt else ""
    start_adresse = parameter_holen(session, "montage_startadresse",
                                    "Arnold-Overbeck-Str. 63-65, 47139 Duisburg")
    routing_an = routing_konfiguriert(session)
    # Termine aller Teams (Tool) einmal lesen – Fenster, Vor-/Nach-Einsätze
    termine_je_team: dict[int, list] = {t.id: [] for t in teams}
    adressen: dict[int, str] = {}
    for t in (session.query(ProjektTermin)
              .filter(ProjektTermin.typ == "montage",
                      ProjektTermin.beginn.isnot(None),
                      ProjektTermin.team_id.in_([te.id for te in teams] or [0]))
              .order_by(ProjektTermin.beginn)):
        termine_je_team.setdefault(t.team_id, []).append(t)
        if routing_an and t.projekt_id not in adressen:
            p = session.get(Projekt, t.projekt_id)
            adressen[t.projekt_id] = _adresse_text(
                p.ausfuehrung_strasse, p.ausfuehrung_plz, p.ausfuehrung_ort) if p else ""
    fenster: list[dict] = []
    ende_suche = start + timedelta(weeks=VORSCHLAG_WOCHEN)
    for team in teams:
        gefunden = 0
        montag = start
        while montag < ende_suche and gefunden < 5:
            beginn = datetime.combine(montag, datetime.min.time())
            ende = arbeitstage_addieren(beginn, dauer - 1)
            belegt = [t for t in termine_je_team.get(team.id, [])
                      if t.beginn.date() <= ende.date()
                      and beginn.date() <= (t.ende or t.beginn).date()]
            if not belegt:
                vorher = max((t for t in termine_je_team.get(team.id, [])
                              if (t.ende or t.beginn).date() < beginn.date()),
                             key=lambda t: (t.ende or t.beginn), default=None)
                nachher = min((t for t in termine_je_team.get(team.id, [])
                               if t.beginn.date() > ende.date()),
                              key=lambda t: t.beginn, default=None)
                fenster.append({"team": team, "beginn": beginn, "ende": ende,
                                "vorher": vorher, "nachher": nachher})
                gefunden += 1
            montag += timedelta(days=7)
    # Fahrzeiten (nur mit Routing-Anbieter): Adressen lesen ist erledigt →
    # Sitzung freigeben, dann Geocoding/Matrix (beide geben selbst frei)
    punkte: dict[str, tuple] = {}
    hinweis = ""
    if routing_an and fenster and ziel_adresse:
        from app import geocoding, routing
        from app.db import verbindung_freigeben
        noetig = {ziel_adresse, start_adresse} | {
            adressen.get(f[k].projekt_id, "") for f in fenster for k in ("vorher", "nachher")
            if f[k] is not None}
        verbindung_freigeben(session)
        for adresse in sorted(a for a in noetig if a):
            lat, lon, status = geocoding.geokodieren(session, adresse)
            if lat is not None:
                punkte[adresse] = (lat, lon)
        orte = list(dict.fromkeys(punkte.values()))
        if len(orte) >= 2:
            routing.matrix_fuellen(session, orte, orte)
        if ziel_adresse not in punkte:
            hinweis = "Fahrzeiten: Ausführungsadresse konnte nicht geokodiert werden."
    elif not routing_an:
        hinweis = "Fahrzeiten: kein Routing-Anbieter konfiguriert"
    vorschlaege: list[dict] = []
    for f in fenster:
        team = f["team"]
        umweg = None
        geschaetzt = False
        begruendung = "erstes freies Fenster des Teams"
        if f["vorher"] is not None or f["nachher"] is not None:
            teile = []
            if f["vorher"] is not None:
                p = session.get(Projekt, f["vorher"].projekt_id)
                teile.append(f"nach {p.nummer if p else '?'} "
                             f"({(f['vorher'].ende or f['vorher'].beginn).strftime('%d.%m.')})")
            if f["nachher"] is not None:
                p = session.get(Projekt, f["nachher"].projekt_id)
                teile.append(f"vor {p.nummer if p else '?'} "
                             f"({f['nachher'].beginn.strftime('%d.%m.')})")
            begruendung = "frei " + ", ".join(teile)
        if routing_an and ziel_adresse in punkte:
            from app import routing
            ziel = punkte[ziel_adresse]
            von = punkte.get(adressen.get(f["vorher"].projekt_id, "")) if f["vorher"] else None
            nach = punkte.get(adressen.get(f["nachher"].projekt_id, "")) if f["nachher"] else None
            von = von or punkte.get(start_adresse)
            nach = nach or punkte.get(start_adresse)
            if von is not None and nach is not None:
                hin = routing.fahrzeit(session, von, ziel)
                weg = routing.fahrzeit(session, ziel, nach)
                direkt = routing.fahrzeit(session, von, nach)
                umweg = int(round(max(0.0, hin["minuten"] + weg["minuten"]
                                      - direkt["minuten"])))
                geschaetzt = bool(hin["geschaetzt"] or weg["geschaetzt"]
                                  or direkt["geschaetzt"])
        vorschlaege.append({
            "team_id": team.id, "team_name": team.name,
            "beginn": f["beginn"].date().isoformat(), "ende": f["ende"].date().isoformat(),
            "beginn_text": _wochentag_kurz(f["beginn"]) + f["beginn"].strftime(" %d.%m."),
            "ende_text": _wochentag_kurz(f["ende"]) + f["ende"].strftime(" %d.%m."),
            "umweg_min": umweg,
            "umweg_text": ("–" if umweg is None
                           else f"{umweg} min" + (" (geschätzt)" if geschaetzt else "")),
            "begruendung": begruendung,
            "besetzung": team_mitglieder_ids(session, team.id),
        })
    vorschlaege.sort(key=lambda v: (v["beginn"], v["umweg_min"] if v["umweg_min"]
                                    is not None else 10 ** 6, v["team_name"]))
    return {"vorschlaege": vorschlaege, "hinweis": hinweis, "dauer_tage": dauer,
            "fruehester": start.isoformat(), "routing": routing_an}


def _wochentag_kurz(wert: datetime) -> str:
    return ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][wert.weekday()]


def startseiten_kacheln(session: Session) -> dict:
    """Phase 68: Kacheln zählen GEWERKE je Phase (mit Sparten-Untertitel)
    plus überfällige Aufgaben."""
    zaehler = {p: {"anzahl": 0, "sparten": {}} for p in
               ("auftragseingang", "feinplanung_vot", "planung",
                "montagevorbereitung", "montage", "abnahme", "freigabe")}
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
    # V4 (Phase 90.1): Auftragseingang „x unterminiert · y terminiert“
    ae = [g for g in gewerke if g.phase == "auftragseingang"]
    ae_unterminiert = sum(1 for g in ae
                          if ts.get(g.id, {}).get("status") == "unterminiert")
    zaehler["auftragseingang"]["untertitel"] = (
        f"{ae_unterminiert} unterminiert · {len(ae) - ae_unterminiert} terminiert")
    # V4 (Phase 90.3): terminierte Gewerke mit roter Vorlauf-Ampel (< 4 Wochen)
    zaehler["vorlauf_rot"] = sum(
        1 for g in gewerke
        if g.phase in VORLAUF_PHASEN
        and ts.get(g.id, {}).get("status") != "unterminiert"
        and vorlauf_ampel(session, g, ts.get(g.id))["farbe"] == "rot")
    return zaehler


# --- V4 (PLAN_PROJ_V4 Phase 90.3): Vorlauf-Ampel zum Montagetermin -------------

VORLAUF_PHASEN = ("auftragseingang", "feinplanung_vot", "planung",
                  "montagevorbereitung")


def vorlauf_schwellen(session: Session) -> tuple[float, float]:
    """(grün ab Wochen, gelb ab Wochen) – Parameter der Projektierung."""
    def _zahl(name, standard):
        try:
            return float(str(parameter_holen(session, name, str(standard))
                             ).replace(",", "."))
        except ValueError:
            return float(standard)
    return (_zahl("vorlauf_gruen_ab_wochen", 8), _zahl("vorlauf_gelb_ab_wochen", 4))


def vorlauf_ampel(session: Session, gewerk: Gewerk, ts: dict | None = None,
                  schwellen: tuple[float, float] | None = None,
                  heute: datetime | None = None) -> dict:
    """Vorlauf bis Montagebeginn: grün > 8 Wochen · gelb 4–8 · rot < 4 bzw.
    unterminiert. Gilt nur Auftragseingang bis Montagevorbereitung (sonst
    farbe None). Liefert farbe, wochen (Dezimal), text, tooltip."""
    if gewerk.phase not in VORLAUF_PHASEN:
        return {"farbe": None, "wochen": None, "text": "", "tooltip": ""}
    ts = ts if ts is not None else terminstatus(session, gewerk)
    termin = (ts or {}).get("termin")
    if termin is None or termin.beginn is None:
        return {"farbe": "rot", "wochen": None, "text": "Unterminiert",
                "tooltip": "Unterminiert – kein Montagetermin"}
    gruen_ab, gelb_ab = schwellen or vorlauf_schwellen(session)
    heute = heute or datetime.now()
    tage = (termin.beginn.date() - heute.date()).days
    wochen = tage / 7
    farbe = "gruen" if wochen > gruen_ab else ("gelb" if wochen >= gelb_ab else "rot")
    if tage < 0:
        tooltip = f"Montagebeginn war vor {-tage} Tagen"
    else:
        w, t = divmod(tage, 7)
        tooltip = ("noch " + (f"{w} Woche{'n' if w != 1 else ''}" if w else "")
                   + (" und " if w and t else "")
                   + (f"{t} Tag{'e' if t != 1 else ''}" if t or not w else "")
                   + " bis Montagebeginn")
    return {"farbe": farbe, "wochen": round(wochen, 1),
            "text": f"{wochen:.1f} Wo.".replace(".", ","), "tooltip": tooltip}


def viertelstunde(zeit: datetime | None) -> datetime | None:
    """V4 (Phase 90.4): Uhrzeit kaufmännisch auf 15 Minuten runden
    (7:52 → 7:45, 7:53 → 8:00; ab 7:30 Sekunden zählt zur Hälfte)."""
    if zeit is None:
        return None
    minuten = zeit.hour * 60 + zeit.minute + zeit.second / 60
    gerundet = int((minuten + 7.5) // 15) * 15
    basis = zeit.replace(hour=0, minute=0, second=0, microsecond=0)
    return basis + timedelta(minutes=gerundet)


def sortierschluessel_chrono(zeile: dict) -> tuple:
    """V4 (Phase 90.1): Karten/Zeilen mit Montagetermin nach Beginn
    aufsteigend, unterminierte darunter nach Auftragsdatum (älteste oben)."""
    termin = (zeile.get("terminstatus") or {}).get("termin")
    if termin is not None and termin.beginn is not None:
        return (0, termin.beginn)
    gewerk = zeile["gewerk"]
    return (1, gewerk.erstellt_am or datetime.min)


# --- Phasenwechsel + Freigabe (Phase 67) --------------------------------------------

def _pflicht_aufgaben_in_paketen(session: Session, gewerk: Gewerk,
                                 paket_namen: tuple[str, ...]
                                 ) -> tuple[list[Aufgabe], int, bool]:
    """(offene Pflichtaufgaben, gesamt, paket_vorhanden) in aktiven
    Paket-Instanzen, deren Name einem der übergebenen entspricht (v15;
    v28: liefert die Aufgaben selbst, damit der Dialog sie abhaken kann)."""
    instanzen = [i for i in (session.query(AufgabenpaketInstanz)
                             .filter(AufgabenpaketInstanz.gewerk_id == gewerk.id,
                                     AufgabenpaketInstanz.deaktiviert_am.is_(None)))
                 if (i.paket_name or "").strip().lower()
                 in {n.lower() for n in paket_namen}]
    if not instanzen:
        return [], 0, False
    ids = {i.id for i in instanzen}
    aufgaben = [a for a in (session.query(Aufgabe)
                            .filter(Aufgabe.gewerk_id == gewerk.id,
                                    Aufgabe.pflicht.is_(True),
                                    Aufgabe.status != "entfaellt")
                            .order_by(Aufgabe.paket_instanz_id, Aufgabe.reihenfolge,
                                      Aufgabe.id))
                if a.paket_instanz_id in ids]
    offen = [a for a in aufgaben if a.status != "erledigt"]
    return offen, len(aufgaben), True


def _pflicht_offen_in_paketen(session: Session, gewerk: Gewerk,
                              paket_namen: tuple[str, ...]) -> tuple[int, int, bool]:
    """(offen, gesamt, paket_vorhanden) – Zählvariante (v15)."""
    offen, gesamt, da = _pflicht_aufgaben_in_paketen(session, gewerk, paket_namen)
    return len(offen), gesamt, da


def waechter_bloecke(session: Session, gewerk: Gewerk, ziel: str) -> list[dict]:
    """v28 (PLAN_PROJ_V6 Phase 133): unerfüllte Bedingungen für den Wechsel
    NACH RECHTS als Blöcke {text, aufgaben: [Aufgabe, …], aufgabe: Aufgabe|None}
    – `text` ist die bisherige Wächter-Zeile (Verlauf/Meldung), `aufgaben`
    die offenen Pflichtaufgaben dahinter (Dialog „Phase ändern“: Häkchen
    „erledigt“ / Knopf „entfällt“ je Aufgabe). Leer = Wechsel frei;
    rückwärts liefert [] (Begründung regelt phase_wechseln).
    Solange die V2-Pakete (Phase 78) nicht existieren, greift je Stufe der
    dokumentierte Fallback (docs/projektierung-entscheidungen.md)."""
    reihen = {p: i for i, p in enumerate(
        ["auftragseingang", "feinplanung_vot", "planung",
         "montagevorbereitung", "montage", "abnahme", "freigabe",
         "abgeschlossen"])}
    reihen["abnahme_freigabe"] = reihen["abnahme"]   # Altwert vor Migration
    if ziel not in reihen or reihen.get(gewerk.phase, 0) >= reihen[ziel]:
        return []
    bloecke: list[dict] = []

    def _block(text: str, aufgaben=None, aufgabe=None) -> None:
        bloecke.append({"text": text, "aufgaben": list(aufgaben or []),
                        "aufgabe": aufgabe})

    def _paket_block(namen: tuple[str, ...], titel: str) -> None:
        offen, gesamt, da = _pflicht_aufgaben_in_paketen(session, gewerk, namen)
        if da and offen:
            _block(f"{titel}: {len(offen)} von {gesamt} Pflichtaufgaben offen", offen)

    # Auftragseingang → Feinplanung VOT: Pflichtaufgaben Paket "Auftragseingang"
    if reihen[ziel] >= reihen["feinplanung_vot"]:
        _paket_block(("Auftragseingang",), "Paket Auftragseingang")
    # Feinplanung VOT → Planung: Feinplanung erfasst (Häkchen bis Phase 80)
    # + Pflichtaufgaben des V2-Pakets "Feinplanung VOT" (Phase 78)
    if reihen[ziel] >= reihen["planung"]:
        if not gewerk.feinplanung_erfasst:
            _block("Feinplanung nicht erfasst (Häkchen „Feinplanung "
                   "erfasst“ in der Akte)")
        _paket_block(("Feinplanung VOT",), "Paket Feinplanung VOT")
    # Planung → Montagevorbereitung: Pflicht der Planungs-Pakete; ohne diese
    # Pakete (V1-Bestand) zählen alle Pflichtaufgaben (bisheriges Verhalten)
    if reihen[ziel] >= reihen["montagevorbereitung"]:
        offen, gesamt, da = _pflicht_aufgaben_in_paketen(
            session, gewerk, ("Planung WP", "Planung Elektro",
                              "Friondo Fit for Future", "Fit for Future"))
        if da:
            if offen:
                _block(f"Planungs-Pakete: {len(offen)} von {gesamt} "
                       "Pflichtaufgaben offen", offen)
        else:
            alle = [a for a in (session.query(Aufgabe)
                                .filter(Aufgabe.gewerk_id == gewerk.id,
                                        Aufgabe.pflicht.is_(True),
                                        Aufgabe.status != "entfaellt")
                                .order_by(Aufgabe.reihenfolge, Aufgabe.id))]
            offen = [a for a in alle if a.status != "erledigt"]
            if offen:
                _block(f"{len(offen)} Pflichtaufgaben offen "
                       f"({len(alle) - len(offen)} von {len(alle)} erledigt)", offen)
    # Montagevorbereitung → Montage: Freigabe-Aufgabe erledigt UND Termin
    if reihen[ziel] >= reihen["montage"]:
        freigabe = (session.query(Aufgabe)
                    .filter(Aufgabe.gewerk_id == gewerk.id,
                            Aufgabe.titel == "Projekt zur Montage freigegeben",
                            Aufgabe.status != "entfaellt").first())
        if freigabe is not None and freigabe.status != "erledigt":
            _block("Aufgabe „Projekt zur Montage freigegeben“ offen",
                   aufgabe=freigabe)
        termin = (session.query(ProjektTermin)
                  .filter(ProjektTermin.gewerk_id == gewerk.id,
                          ProjektTermin.typ == "montage",
                          ProjektTermin.beginn.isnot(None)).first())
        if termin is None:
            _block("Kein Montagetermin angelegt")
        elif not (termin.team_id or termin.person_id):
            _block("Montagetermin ohne Team/Person")
    # Montage → Abnahme: Häkchen "Montage fertig"
    if reihen[ziel] >= reihen["abnahme"] and gewerk.montage_fertig_am is None:
        _block("Montage nicht fertig gemeldet (Montage-Backend oder "
               "Projektierer)")
    # V4 (Phase 90.2): Abnahme → Freigabe: Pflichtaufgaben des Pakets Abnahme
    if reihen[ziel] >= reihen["freigabe"]:
        _paket_block(("Abnahme",), "Paket Abnahme")
    # Abgeschlossen nur über die Rechnungsfreigabe
    if ziel == "abgeschlossen" and gewerk.freigabe_am is None:
        _block("Rechnung nicht freigegeben – bitte „Rechnung freigeben“ nutzen")
    return bloecke


def waechter_pruefen(session: Session, gewerk: Gewerk, ziel: str) -> list[str]:
    """Unerfüllte Bedingungen für den Wechsel NACH RECHTS (v15, Phase 74) als
    Textliste; leer = Wechsel frei. Rückwärts liefert []."""
    return [b["text"] for b in waechter_bloecke(session, gewerk, ziel)]


def waechter_details(session: Session, gewerk: Gewerk, ziel: str) -> dict:
    """v28 (PLAN_PROJ_V6 Phase 133): JSON für die Dialoge „Phase ändern“
    (Akte und Board): {modus, rueckwaerts, offen: [{text, aufgabe_id|null,
    pflicht}], begruendung_pflicht, hinweis, sperre}. Jede offene
    Pflichtaufgabe erscheint einzeln (abhakbar), Bedingungen ohne Aufgabe
    (Termin, Montage fertig, Rechnung) als Textzeile."""
    from app.models import GEWERK_PHASEN, GEWERK_PHASEN_NAMEN
    modus = waechter_modus(session)
    reihen = {p: i for i, p in enumerate(GEWERK_PHASEN)}
    rueckwaerts = (ziel in reihen and gewerk.phase in reihen
                   and reihen[ziel] < reihen[gewerk.phase])
    offen: list[dict] = []
    for block in waechter_bloecke(session, gewerk, ziel):
        if block["aufgaben"]:
            for a in block["aufgaben"]:
                offen.append({"text": a.titel, "aufgabe_id": a.id,
                              "pflicht": bool(a.pflicht), "gruppe": block["text"]})
        elif block["aufgabe"] is not None:
            a = block["aufgabe"]
            offen.append({"text": a.titel, "aufgabe_id": a.id,
                          "pflicht": bool(a.pflicht), "gruppe": block["text"]})
        else:
            offen.append({"text": block["text"], "aufgabe_id": None,
                          "pflicht": True, "gruppe": ""})
    sperre = ""
    if ziel == "abgeschlossen" and gewerk.freigabe_am is None:
        sperre = "„Abgeschlossen“ ist nur über „Rechnung freigeben“ erreichbar."
    elif gewerk.phase == "storniert":
        sperre = "Storniertes Gewerk – Phasenwechsel nicht möglich."
    begruendung_pflicht = bool(rueckwaerts or (modus == "sperren" and offen))
    if rueckwaerts:
        hinweis = "Rückwärts-Wechsel nur mit Begründung (wird im Verlauf protokolliert)."
    elif modus == "warnen":
        hinweis = ("Offene Punkte blockieren nicht – sie werden im Verlauf vermerkt."
                   if offen else "Wächter erfüllt – keine offenen Punkte.")
    else:
        hinweis = ("Modus „sperren“: Wechsel mit offenen Punkten nur mit Begründung "
                   "(Override, protokolliert)." if offen
                   else "Wächter erfüllt – keine offenen Punkte.")
    return {"modus": modus, "rueckwaerts": rueckwaerts, "offen": offen,
            "begruendung_pflicht": begruendung_pflicht, "hinweis": hinweis,
            "sperre": sperre, "ziel": ziel,
            "ziel_name": GEWERK_PHASEN_NAMEN.get(ziel, ziel),
            "phase": gewerk.phase,
            "phase_name": GEWERK_PHASEN_NAMEN.get(gewerk.phase, gewerk.phase),
            "anzahl": len(offen)}


def terminstatus_map(session: Session, gewerk_ids: list[int]) -> dict[int, dict]:
    """v15 (Phase 74): Terminstatus je Gewerk (berechnet).
    terminiert = Montagetermin mit Team UND Kunde bestätigt · unbestaetigt =
    Montagetermin vorhanden (ohne Bestätigung oder ohne Team) · unterminiert =
    kein Montagetermin. Maßgeblich ist der früheste zukünftige Montagetermin,
    sonst der letzte. v28 (PLAN_PROJ_V6 Phase 135): nur Montagetermine mit
    zweck „wp“ oder leer – Elektro-/Sub-Termine bestimmen den Status nicht."""
    ergebnis: dict[int, dict] = {
        gid: {"status": "unterminiert", "termin": None} for gid in gewerk_ids}
    if not gewerk_ids:
        return ergebnis
    jetzt = datetime.now()
    beste: dict[int, ProjektTermin] = {}
    for t in (session.query(ProjektTermin)
              .filter(ProjektTermin.typ == "montage",
                      ProjektTermin.zweck.in_(["wp", ""]),
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
    """Phasenwechsel mit Wächtern. v28 (PLAN_PROJ_V6 Phase 133): Modus
    `waechter_modus` – „warnen“ (Standard): offene Punkte blockieren nicht,
    sie stehen im Verlauf („… – mit offenen Punkten: <Liste>“, mit Begründung
    „… – Begründung: <Text>“); „sperren“: Override nur mit Begründung wie
    bisher. Rückwärts in beiden Modi nur mit Begründung; „abgeschlossen“ in
    beiden Modi nur über „Rechnung freigeben“; `montage_fertig_am` wird beim
    Wechsel nach Abnahme/Freigabe gesetzt. Stornierte Gewerke sind gesperrt.
    Signatur und Rückgabe (ok, meldung) bleiben (Aufrufer: Akte, Board,
    Montage-Backend)."""
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
    modus = waechter_modus(session)
    if rueckwaerts and not begruendung:
        return False, ("Rückwärts-Wechsel nur mit Begründung "
                       "(Feld „Begründung“ ausfüllen).")
    if ziel == "abgeschlossen" and gewerk.freigabe_am is None:
        return False, ("„Abgeschlossen“ ist nur über „Rechnung freigeben“ "
                       "erreichbar (in beiden Wächter-Modi).")
    if offen and modus == "sperren" and not begruendung:
        return False, ("Wächter: " + " · ".join(offen)
                       + " – Override nur mit Begründung.")
    alt = gewerk.phase
    gewerk.phase = ziel
    gewerk.phase_geaendert_am = datetime.now()
    if ziel in ("abnahme", "freigabe") and gewerk.montage_fertig_am is None:
        gewerk.montage_fertig_am = datetime.now()   # Häkchen „Montage fertig" (Override)
    projekt = session.get(Projekt, gewerk.projekt_id)
    if projekt is not None:
        projektstatus_berechnen(session, projekt)
    text = (f"Phase des Gewerks {gewerk.sparte} geändert: "
            f"{GEWERK_PHASEN_NAMEN[alt]} → {GEWERK_PHASEN_NAMEN[ziel]}")
    if offen and modus == "sperren":
        # Verhalten wie bisher: Override mit Begründung
        text += f" – trotz offener Punkte: {begruendung} ({' · '.join(offen)})"
    elif offen:
        text += f" – mit offenen Punkten: {' · '.join(offen)}"
        if begruendung:
            text += f" – Begründung: {begruendung}"
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
    meldung = f"Gewerk {gewerk.sparte}: {GEWERK_PHASEN_NAMEN[ziel]}."
    if offen and modus == "warnen":
        meldung += (f" {len(offen)} offene{'r' if len(offen) == 1 else ''} "
                    f"Punkt{'' if len(offen) == 1 else 'e'} im Verlauf vermerkt.")
    return True, meldung


def rechnung_freigeben(session: Session, gewerk: Gewerk, restarbeiten: str,
                       restarbeiten_text: str, benutzer=None) -> tuple[bool, str]:
    """„Rechnung freigeben“ (Phase 67): Restarbeiten-Pflichtfrage, Phase
    Abgeschlossen, Benachrichtigung an die Buchhaltung, Verlaufseintrag;
    Restarbeiten erzeugen automatisch eine Pflicht-Aufgabe (+14)."""
    if gewerk.phase not in ("freigabe", "abnahme_freigabe"):
        return False, "Rechnung freigeben nur in Phase „Freigabe“ möglich."
    restarbeiten_text = (restarbeiten_text or "").strip()[:1000]
    if restarbeiten == "ja" and not restarbeiten_text:
        return False, "Bitte die Restarbeiten/Reklamationen beschreiben (Pflicht)."
    if restarbeiten not in ("keine", "ja"):
        return False, "Bitte angeben, ob Restarbeiten offen sind."
    gewerk.freigabe_am = datetime.now()
    gewerk.freigabe_von = benutzer.id if benutzer else None
    gewerk.restarbeiten_text = restarbeiten_text if restarbeiten == "ja" else ""
    # V4 (Phase 90.2): Aufgabe „Rechnung freigegeben“ (Paket Freigabe) erledigen
    for aufgabe in (session.query(Aufgabe)
                    .filter(Aufgabe.gewerk_id == gewerk.id,
                            Aufgabe.titel == "Rechnung freigegeben",
                            Aufgabe.status != "erledigt")):
        aufgabe.status = "erledigt"
        aufgabe.erledigt_am = datetime.now()
        aufgabe.erledigt_von = benutzer.id if benutzer else None
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


# --- v28 (PLAN_PROJ_V6 Phasen 133/135): Datenmigration ------------------------------

def migration_v28(session: Session) -> list[str]:
    """Von migrate.py aufgerufen (idempotent, committet nicht selbst):
    1. `projekt_termine.zweck` für Montagetermine ohne Zweck: wp / elektro /
       sub je nachdem, mit welchem Zuweisungsfeld des Gewerks (`wp_team_id` /
       `elektro_team_id` / `sub_team_id`) `team_id` übereinstimmt, sonst wp.
    2. Besetzung je Termin: für Termine mit Team ohne Besetzung die Mitglieder
       aus `team_mitglieder` eintragen.
    3. Bedingungen (`sichtbar_wenn`) an bestehenden Aufgaben aus der Logik
       nachtragen (Altbestand vor v28 trägt nur `<paket>.<nr>=`); die Statuswerte
       bleiben unverändert – „entfällt“ setzt erst der nächste Nachzieh-Lauf
       (abhaengige_pruefen) [ANNAHME]. Zweiter Lauf: keine Meldungen."""
    meldungen: list[str] = []
    # 1. zweck
    gewerke = {g.id: g for g in session.query(Gewerk)}
    zweck_neu = 0
    for t in (session.query(ProjektTermin)
              .filter(ProjektTermin.typ == "montage",
                      ProjektTermin.zweck == "")):
        g = gewerke.get(t.gewerk_id)
        zweck = "wp"
        if g is not None and t.team_id:
            if t.team_id == g.elektro_team_id and t.team_id != g.wp_team_id:
                zweck = "elektro"
            elif t.team_id == g.sub_team_id and t.team_id not in (g.wp_team_id,
                                                                  g.elektro_team_id):
                zweck = "sub"
        t.zweck = zweck
        zweck_neu += 1
    if zweck_neu:
        session.flush()
        meldungen.append(f"Projektierung V6: {zweck_neu} Montagetermine mit Zweck "
                         "(wp/elektro/sub) belegt")
    # 2. Besetzung aus Team-Mitgliedern
    mit_besetzung = {z[0] for z in session.query(TerminBesetzung.termin_id).distinct()}
    mitglieder: dict[int, list[int]] = {}
    for m in session.query(TeamMitglied).order_by(TeamMitglied.id):
        mitglieder.setdefault(m.team_id, []).append(m.benutzer_id)
    besetzt = 0
    for t in (session.query(ProjektTermin)
              .filter(ProjektTermin.team_id.isnot(None)).order_by(ProjektTermin.id)):
        if t.id in mit_besetzung:
            continue
        ids = mitglieder.get(t.team_id, [])
        if not ids:
            continue
        for bid in dict.fromkeys(ids):
            session.add(TerminBesetzung(termin_id=t.id, benutzer_id=bid))
        besetzt += 1
    if besetzt:
        session.flush()
        meldungen.append(f"Projektierung V6: Besetzung für {besetzt} Termine aus den "
                         "Team-Mitgliedern übernommen")
    # 3. Bedingungen an bestehenden Aufgaben nachtragen
    try:
        from app import projektierung_logik
        logik = projektierung_logik.hole_logik(session)
    except Exception:
        logik = None
    if logik is not None and not logik.fehler:
        instanzen = {i.id: i for i in session.query(AufgabenpaketInstanz)
                     .filter(AufgabenpaketInstanz.deaktiviert_am.is_(None),
                             AufgabenpaketInstanz.version != "v1")}
        nachgetragen = 0
        for a in (session.query(Aufgabe)
                  .filter(Aufgabe.sichtbar_wenn == "",
                          Aufgabe.paket_instanz_id.isnot(None))):
            instanz = instanzen.get(a.paket_instanz_id)
            paket = logik.pakete.get(instanz.paket_key) if instanz is not None else None
            if paket is None:
                continue
            schritt = next((s for s in paket.schritte if s.nr == a.reihenfolge), None)
            if schritt is None:
                continue
            bedingung = _laufzeit_bedingung(getattr(schritt, "sichtbar_wenn", ""))
            if bedingung:
                a.sichtbar_wenn = bedingung
                nachgetragen += 1
        if nachgetragen:
            session.flush()
            meldungen.append(f"Projektierung V6: Bedingung (sichtbar_wenn) an "
                             f"{nachgetragen} bestehenden Aufgaben aus der Logik nachgetragen")
    return meldungen
