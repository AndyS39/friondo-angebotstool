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
                        ProjektTermin, ProjektVerlauf, Vorgang)

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

# Phasen-Rangfolge für den abgeleiteten Projektstatus
_PHASEN_RANG = {"feinplanung": 0, "feinplanung_abgeschlossen": 1,
                "montage_geplant": 2, "in_ausfuehrung": 3, "abnahme_offen": 4}


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


def paket_aktivieren(session: Session, gewerk: Gewerk, paket: "object",
                     benutzer=None, quelle: str = "regel") -> AufgabenpaketInstanz | None:
    """Aktiviert eine Paket-Vorlage (aus projektierung_logik_v1.xlsx) am
    Gewerk: Instanz + Aufgaben mit Verantwortlichen und Fälligkeiten.
    Bereits aktive Pakete (nicht deaktiviert) werden nicht doppelt aktiviert."""
    vorhanden = (session.query(AufgabenpaketInstanz)
                 .filter(AufgabenpaketInstanz.gewerk_id == gewerk.id,
                         AufgabenpaketInstanz.paket_key == paket.key,
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
        status = "feinplanung"
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
        ausfuehrung_strasse=(adresse or {}).get("strasse",
                                                kunde.strasse if kunde else ""),
        ausfuehrung_plz=(adresse or {}).get("plz", kunde.plz if kunde else ""),
        ausfuehrung_ort=(adresse or {}).get("ort", kunde.ort if kunde else ""),
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
        projekt_id=projekt.id, sparte=sparte, phase="feinplanung",
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
