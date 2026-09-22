# Datenbankmodelle des Angebotstools.
# Phase 1: Kunden · Phase 2: Artikel. Weitere Modelle folgen in späteren Phasen.

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Integer, String,
                        Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Kunde(Base):
    __tablename__ = "kunden"

    id: Mapped[int] = mapped_column(primary_key=True)
    anrede: Mapped[str] = mapped_column(String(20), default="")        # Herr / Frau / Firma
    firma: Mapped[str] = mapped_column(String(200), default="")
    vorname: Mapped[str] = mapped_column(String(100), default="")
    nachname: Mapped[str] = mapped_column(String(100), default="")
    strasse: Mapped[str] = mapped_column(String(200), default="")
    plz: Mapped[str] = mapped_column(String(10), default="")
    ort: Mapped[str] = mapped_column(String(100), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    telefon: Mapped[str] = mapped_column(String(50), default="")
    kunden_nr: Mapped[str] = mapped_column(String(50), default="")     # Nummer aus TAIFUN, optional
    notizen: Mapped[str] = mapped_column(Text, default="")
    # Interesse (v5): Mehrfach-Feld, Codes kommagetrennt, z. B. "WP,PV"
    interesse: Mapped[str] = mapped_column(String(50), default="")
    vertriebskanal: Mapped[str] = mapped_column(String(100), default="")   # v6, aus monday
    kanal_manuell: Mapped[bool] = mapped_column(Boolean, default=False)    # v9: Sync-Schutz
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    @property
    def interessen(self) -> list[str]:
        return interesse_liste(self.interesse)

    @property
    def briefanrede(self) -> str:
        """Briefanrede (v5) – identischer Baustein für PDF-Vortext und
        Mail-Platzhalter {briefanrede}: Herr/Frau + Nachname, Familie,
        sonst „Sehr geehrte Damen und Herren,“."""
        if self.anrede == "Herr" and self.nachname:
            return f"Sehr geehrter Herr {self.nachname},"
        if self.anrede == "Frau" and self.nachname:
            return f"Sehr geehrte Frau {self.nachname},"
        if self.anrede == "Familie" and self.nachname:
            return f"Sehr geehrte Familie {self.nachname},"
        return "Sehr geehrte Damen und Herren,"

    @property
    def anzeige_name(self) -> str:
        """Name für Listen und Auswahlfelder: Firma bzw. 'Nachname, Vorname'."""
        person = ", ".join(t for t in (self.nachname, self.vorname) if t)
        if self.firma and person:
            return f"{self.firma} ({person})"
        return self.firma or person


# Interesse (v5): Codes und Anzeigenamen; Reihenfolge = Anzeigereihenfolge
INTERESSEN = [("WP", "Wärmepumpe"), ("PV", "Photovoltaik"), ("KL", "Klima"), ("WB", "Wallbox")]
INTERESSE_CODES = [code for code, _ in INTERESSEN]

# Konfigurator-Typ (v5): aktuell nur WP; PV/Klima docken später als eigene
# Kataloge an – jeder Vorgang trägt den Typ bereits mit.
KONFIGURATOR_TYPEN = ["WP", "PV", "KL"]


def angebot_status_setzen(angebot, neuer_status: str) -> None:
    """Zentraler Statuswechsel (v6): setzt den Status und stempelt den
    Zeitpunkt für die Statistik (nur beim ersten Erreichen des Status)."""
    angebot.status = neuer_status
    jetzt = datetime.now()
    if neuer_status in ("Versendet", "Versendet (extern)") and angebot.versendet_am is None:
        angebot.versendet_am = jetzt
    elif neuer_status == "Angenommen" and angebot.angenommen_am is None:
        angebot.angenommen_am = jetzt
    elif neuer_status == "Abgelehnt" and angebot.abgelehnt_am is None:
        angebot.abgelehnt_am = jetzt


def interesse_liste(wert: str) -> list[str]:
    """"WP,PV" -> ["WP", "PV"] in kanonischer Reihenfolge."""
    gesetzt = {t.strip().upper() for t in (wert or "").split(",") if t.strip()}
    return [code for code in INTERESSE_CODES if code in gesetzt]


def interesse_text(codes) -> str:
    return ",".join(interesse_liste(",".join(codes)))


# Herkunft eines Artikels – steuert, was der Re-Import anfassen darf.
QUELLE_PREISLISTE = "preisliste"   # TAIFUN-Preisliste (Anker: GUID)
QUELLE_ZUSATZ = "zusatz"           # Zusatzartikel Z01–Z22 aus der Logik-Excel (Anker: Pos-Nr.)
QUELLE_MANUELL = "manuell"         # im Tool angelegt, wird vom Import nie verändert


class Artikel(Base):
    __tablename__ = "artikel"

    id: Mapped[int] = mapped_column(primary_key=True)
    guid: Mapped[Optional[str]] = mapped_column(String(40), unique=True, nullable=True)
    pos_nr: Mapped[str] = mapped_column(String(10), default="", index=True)  # "045", "Z01", leer bei manuell
    kategorie: Mapped[str] = mapped_column(String(300), default="")
    bezeichnung: Mapped[str] = mapped_column(String(300), default="")        # Kurztitel (Z-Artikel/manuell)
    beschreibung: Mapped[str] = mapped_column(Text, default="")
    menge_standard: Mapped[float] = mapped_column(Float, default=1.0)
    einheit: Mapped[str] = mapped_column(String(20), default="")
    e_preis_cent: Mapped[int] = mapped_column(Integer, default=0)            # Einzelpreis netto in Cent
    ep_flag: Mapped[bool] = mapped_column(Boolean, default=False)            # Eventualposition ("EP.")
    quelle: Mapped[str] = mapped_column(String(20), default=QUELLE_MANUELL)
    # Preisliste v2 (Phase 11): Einkaufsdaten – nur Innendienst, nie im PDF
    artikelnummer: Mapped[str] = mapped_column(String(50), default="")
    multi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)     # VK = EK × Multi
    ek_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)   # Einkaufspreis Material
    ek_datum: Mapped[str] = mapped_column(String(20), default="")
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                      onupdate=datetime.now)

    @property
    def titel(self) -> str:
        """Kurztitel für Listen: Bezeichnung, sonst erste Zeile der Beschreibung."""
        if self.bezeichnung:
            return self.bezeichnung
        return self.beschreibung.splitlines()[0] if self.beschreibung else ""


class Konfiguration(Base):
    """Laufender oder abgeschlossener Konfigurator-Durchlauf (Phase 4)."""
    __tablename__ = "konfigurationen"

    id: Mapped[int] = mapped_column(primary_key=True)
    kunde_id: Mapped[int] = mapped_column(Integer, index=True)
    antworten_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(20), default="laufend")  # laufend | abbruch | fertig
    abbruch_meldung: Mapped[str] = mapped_column(Text, default="")
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Benutzer(Base):
    """Leichtgewichtige Benutzerverwaltung (Phase 13): Name, Rolle, PIN-Hash."""
    __tablename__ = "benutzer"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    rolle: Mapped[str] = mapped_column(String(20), default="aussendienst")  # innendienst | aussendienst
    pin_hash: Mapped[str] = mapped_column(String(64), default="")
    # E-Mail (v5): Pflicht für Außendienst – landet als CC in der Angebots-Mail
    email: Mapped[str] = mapped_column(String(200), default="")
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # v11 (Projektierung, Phase 64): Mehrfachrollen als Komma-Liste – `rolle`
    # bleibt die Hauptrolle (steuert die bisherigen Sichten), `rollen` trägt
    # die vollständige Liste inkl. neuer Rollen projektierung/montage
    rollen: Mapped[str] = mapped_column(String(100), default="")
    kalkulation_sichtbar: Mapped[bool] = mapped_column(Boolean, default=False)
    benachrichtigung_mail: Mapped[str] = mapped_column(String(10), default="aus")  # aus|sofort|digest
    # v11 (Phase 70): Telefon des Projektleiters im AD-Projektstand-Block
    telefon: Mapped[str] = mapped_column(String(50), default="")
    # v12 (Lead-Management, Phase 73): Leadmanager-Einstellungen
    lm_aktiv: Mapped[bool] = mapped_column(Boolean, default=False)   # Round-Robin
    lm_arbeitszeit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    @property
    def rollen_liste(self) -> list[str]:
        """Alle Rollen des Benutzers (Hauptrolle immer enthalten)."""
        zusatz = [r.strip() for r in (self.rollen or "").split(",") if r.strip()]
        return [self.rolle] + [r for r in zusatz if r != self.rolle]

    def hat_rolle(self, name: str) -> bool:
        return name in self.rollen_liste


# Statuskette v7 (ersetzt das v6-Auto-Archiv von „Individuell“):
# Katalog-Fälle mit oranger Ampel starten als „Individuell – zu prüfen“
# (Buttons „Doch konfigurierbar“ / „Individuell bestätigt“); bestätigte und
# Freitext-Fälle stehen als Arbeitsliste „In TAIFUN zu schreiben“; nach dem
# Dialog „Extern erledigt“ → „Erledigt (extern)“ + Archiv.
ERFASSUNG_STATUS = ["Neu", "In Bearbeitung", "Individuell – zu prüfen",
                    "In TAIFUN zu schreiben", "Erledigt", "Erledigt (extern)"]


class Erfassung(Base):
    """Mobile Außendienst-Erfassung (Phase 13): Antworten + Ampel; der Innendienst
    verarbeitet sie in der Erfassungsliste (Phase 14) weiter."""
    __tablename__ = "erfassungen"

    id: Mapped[int] = mapped_column(primary_key=True)
    kunde_id: Mapped[int] = mapped_column(Integer, index=True)
    benutzer_id: Mapped[int] = mapped_column(Integer, index=True)      # Vertriebler
    antworten_json: Mapped[str] = mapped_column(Text, default="{}")
    # v12 (Lead-Management, Phase 76): Kennzeichen „aus Qualifizierung“
    vorbelegt_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ampel: Mapped[str] = mapped_column(String(10), default="gruen")    # gruen | orange
    gruende_text: Mapped[str] = mapped_column(Text, default="")        # AMPEL-Gründe (je Zeile)
    status: Mapped[str] = mapped_column(String(20), default="Entwurf") # Entwurf -> Neu -> ...
    seite_index: Mapped[int] = mapped_column(Integer, default=0)       # Fortschritt beim Ausfüllen
    angebot_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    aenderungs_protokoll: Mapped[str] = mapped_column(Text, default="")  # Korrekturen Innendienst
    konfigurator_typ: Mapped[str] = mapped_column(String(10), default="WP")   # v5
    archiviert: Mapped[bool] = mapped_column(Boolean, default=False)          # v6
    # Zwei-Wege-Prozess (v7): "katalog" (Fragenkatalog) oder "freitext"
    # (Freitext-Erfassung bzw. Wechsel aus dem Katalog – Teilantworten bleiben)
    typ: Mapped[str] = mapped_column(String(10), default="katalog")
    freitext: Mapped[str] = mapped_column(Text, default="")
    # Multi-Sparten (v8): je Sparte (WP/PV/KL/WB) eine eigene Erfassung;
    # lead_id verknüpft ALLE Erfassungen eines Leads (Lead.erfassung_id
    # bleibt als Alt-Verknüpfung der ersten/WP-Erfassung bestehen)
    sparte: Mapped[str] = mapped_column(String(4), default="WP")
    lead_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    # v10: Vorgangszugehörigkeit (Akte); Migration setzt sie rückwirkend
    vorgang_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    abgesendet_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Einstellung(Base):
    """Pflegbare Schlüssel/Wert-Einstellungen (Phase 24), z. B. DB-Ampel-Schwellen."""
    __tablename__ = "einstellungen"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    wert: Mapped[str] = mapped_column(String(300), default="")


def einstellung_holen(session, name: str, standard: str) -> str:
    zeile = session.query(Einstellung).filter(Einstellung.name == name).first()
    return zeile.wert if zeile and zeile.wert != "" else standard


def einstellung_setzen(session, name: str, wert: str) -> None:
    zeile = session.query(Einstellung).filter(Einstellung.name == name).first()
    if zeile is None:
        zeile = Einstellung(name=name)
        session.add(zeile)
    zeile.wert = wert


class MondayQuelle(Base):
    """monday-Quelle (Phase 22): Board + Gruppentitel; Gruppe wird über den
    Titel aufgelöst (robust bei Board-Kopien). fester_benutzer_id bildet die
    Sonderregel „Deals - Rene“ ab (Verantwortlicher immer dieser Benutzer)."""
    __tablename__ = "monday_quellen"

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[str] = mapped_column(String(30), unique=True)
    board_name: Mapped[str] = mapped_column(String(200), default="")
    gruppen_titel: Mapped[str] = mapped_column(String(100), default="Terminiert")
    fester_benutzer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    # Rückspielung (v5, Phase 32) je Quell-Board bei Statuswechsel „Versendet“:
    #   rueck_modus: aus | status (Status-Spaltenwert setzen) | gruppe (Item verschieben)
    rueck_modus: Mapped[str] = mapped_column(String(10), default="aus")
    rueck_status_spalte: Mapped[str] = mapped_column(String(100), default="")
    rueck_status_wert: Mapped[str] = mapped_column(String(100), default="Angebot versendet")
    rueck_gruppe_id: Mapped[str] = mapped_column(String(100), default="")
    rueck_wert_spalte: Mapped[str] = mapped_column(String(100), default="")   # Deal-Wert
    rueck_wert_basis: Mapped[str] = mapped_column(String(10), default="brutto")  # brutto | netto


# Felder, die je Board auf monday-Spalten gemappt werden (Phase 22)
MONDAY_FELDER = ["vot_datum", "verantwortlicher", "anrede", "vorname", "nachname",
                 "strasse", "plz", "ort", "telefon", "email", "status", "interesse",
                 "vertriebskanal"]


class MondayMapping(Base):
    """Spalten-Mapping je Board: Tool-Feld -> monday-Spalten-ID."""
    __tablename__ = "monday_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[str] = mapped_column(String(30), index=True)
    feld: Mapped[str] = mapped_column(String(30))
    spalten_id: Mapped[str] = mapped_column(String(100), default="")


class MondayPerson(Base):
    """Zuordnung monday-Person (Anzeigename) -> Tool-Benutzer (für AD-Filter)."""
    __tablename__ = "monday_personen"

    id: Mapped[int] = mapped_column(primary_key=True)
    monday_name: Mapped[str] = mapped_column(String(200), unique=True)
    benutzer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class Lead(Base):
    """monday-Lead mit Vor-Ort-Termin (Phase 19 Modell, Phase 22 Lesesync)."""
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    monday_item_id: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    board_id: Mapped[str] = mapped_column(String(30), default="")
    board_name: Mapped[str] = mapped_column(String(200), default="")
    vot_datum: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status_text: Mapped[str] = mapped_column(String(100), default="")
    anrede: Mapped[str] = mapped_column(String(20), default="")
    vorname: Mapped[str] = mapped_column(String(100), default="")
    nachname: Mapped[str] = mapped_column(String(100), default="")
    strasse: Mapped[str] = mapped_column(String(200), default="")
    plz: Mapped[str] = mapped_column(String(10), default="")
    ort: Mapped[str] = mapped_column(String(100), default="")
    telefon: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    monday_person: Mapped[str] = mapped_column(String(200), default="")  # Verantwortlicher
    benutzer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Tool-Benutzer
    kunde_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    erfassung_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    interesse: Mapped[str] = mapped_column(String(50), default="")   # v5, aus monday
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)  # v6 Statistik
    # Ausblenden (v5-Nachtrag): aus „Leads VOT“ nehmen ohne zu löschen; der Sync
    # lässt das Kennzeichen stehen, der Lead taucht also nicht erneut auf
    ausgeblendet: Mapped[bool] = mapped_column(Boolean, default=False)
    ausgeblendet_grund: Mapped[str] = mapped_column(String(300), default="")
    ausgeblendet_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Vertriebler manuell zugeordnet (v5-Nachtrag): der Sync überschreibt
    # benutzer_id dann nicht mehr aus der monday-Personen-Spalte
    benutzer_manuell: Mapped[bool] = mapped_column(Boolean, default=False)
    vertriebskanal: Mapped[str] = mapped_column(String(100), default="")   # v6, aus monday
    # Multi-Sparten (v8): einzelne Interessen ausblendbar (Kommaliste, z. B.
    # "PV,WB"); der Lead verschwindet erst, wenn alle Interessen erfasst
    # oder ausgeblendet sind. Ganz ausblenden weiterhin über `ausgeblendet`.
    ausgeblendet_sparten: Mapped[str] = mapped_column(String(50), default="")
    # v9: Vertriebskanal manuell gesetzt – der Sync überschreibt ihn nicht mehr
    kanal_manuell: Mapped[bool] = mapped_column(Boolean, default=False)
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                     onupdate=datetime.now)

    @property
    def interessen(self) -> list[str]:
        return interesse_liste(self.interesse)

    @property
    def sparten(self) -> list[str]:
        """v8: die zu erfassenden Sparten – die Lead-Interessen, sonst WP."""
        return self.interessen or ["WP"]

    @property
    def ausgeblendete_sparten(self) -> list[str]:
        return interesse_liste(self.ausgeblendet_sparten)

    @property
    def anzeige_name(self) -> str:
        person = " ".join(t for t in (self.vorname, self.nachname) if t)
        return person or self.email or f"monday-Item {self.monday_item_id}"


class Vorgang(Base):
    """v10: Der VORGANG (= Kundenanfrage) ist die Arbeitseinheit. Anker ist
    der Lead; für Kunden ohne Lead entsteht beim ersten Erfassen automatisch
    ein Vorgang. Er bündelt Erfassungen, Angebote (inkl. Versionen/TAIFUN),
    Mail-Verlauf, die Verfolgung (EINE Ampel + Wiedervorlage je Vorgang,
    Phase 60) und den chronologischen Notizen-Chat."""
    __tablename__ = "vorgaenge"

    id: Mapped[int] = mapped_column(primary_key=True)
    kunde_id: Mapped[int] = mapped_column(Integer, index=True)
    lead_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True,
                                                   unique=True, index=True)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # Verfolgung auf Vorgangsebene (Phase 60): ersetzt die Angebots-Felder
    verfolgung_ampel: Mapped[str] = mapped_column(String(10), default="")
    wiedervorlage_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Verantwortlicher der Wiedervorlage (Vorbelegung: Ersteller)
    wiedervorlage_benutzer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # v12 (Lead-Management, Phase 73): Lead-Kopf am Vorgang – alle nullable,
    # idempotent über db._NACHTRAEGLICHE_SPALTEN
    lead_phase: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    quelle_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    kampagne_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    utm_source: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    utm_medium: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    utm_campaign: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    utm_content: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    eingang_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    eingang_art: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    anfrage_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    anfrage_rohdaten: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    erstkontakt_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    erreicht_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    terminiert_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    leadmanager_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_punkte: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_klasse: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    wunschzeiten: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)  # JSON
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geocode_status: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    einwilligung_werbung: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    einwilligung_werbung_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    einwilligung_quelle: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    zurueckgestellt_bis: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    zurueckgestellt_grund: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    unqualifiziert_grund: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    unqualifiziert_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    versuch_nr: Mapped[int] = mapped_column(Integer, default=0)
    naechste_aktion_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    loeschen_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    demo: Mapped[bool] = mapped_column(Boolean, default=False)


class VorgangsNotiz(Base):
    """v10: Notizen-Chat am Vorgang – chronologisch, Einträge unveränderlich
    (kein Bearbeiten/Löschen). herkunft kennzeichnet migrierte Alt-Notizen
    und automatische Protokolleinträge (z. B. Rabatt-Freigaben)."""
    __tablename__ = "vorgangs_notizen"

    id: Mapped[int] = mapped_column(primary_key=True)
    vorgang_id: Mapped[int] = mapped_column(Integer, index=True)
    benutzer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    benutzer_name: Mapped[str] = mapped_column(String(100), default="")
    zeit: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    text: Mapped[str] = mapped_column(Text, default="")
    herkunft: Mapped[str] = mapped_column(String(200), default="")


class VorgangNotizGelesen(Base):
    """v10: „Neue Notizen“-Punkt je Benutzer – merkt, bis wann ein Benutzer
    den Notizen-Chat eines Vorgangs zuletzt gesehen hat."""
    __tablename__ = "vorgang_notiz_gelesen"

    id: Mapped[int] = mapped_column(primary_key=True)
    vorgang_id: Mapped[int] = mapped_column(Integer, index=True)
    benutzer_id: Mapped[int] = mapped_column(Integer, index=True)
    gelesen_bis: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class RabattFreigabe(Base):
    """v10: AD-Rabatt mit Freigabe-Workflow – würde der gewünschte
    Gesamtrabatt die DB-Ampel auf Rot drücken, entsteht eine Anfrage an den
    Innendienst (genehmigen → Rabatt/Version wird angelegt, oder ablehnen
    mit Kommentar); alles wird im Notizen-Chat des Vorgangs protokolliert."""
    __tablename__ = "rabatt_freigaben"

    id: Mapped[int] = mapped_column(primary_key=True)
    angebot_id: Mapped[int] = mapped_column(Integer, index=True)
    vorgang_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    benutzer_id: Mapped[int] = mapped_column(Integer)          # anfragender AD
    rabatt_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rabatt_prozent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rabatt_bezeichnung: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="offen")  # offen | genehmigt | abgelehnt
    kommentar: Mapped[str] = mapped_column(String(500), default="")
    angefragt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    entschieden_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    entschieden_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


# ===================== Projektierung V1 (v11, Phase 64) =====================
# Projekt = Bauvorhaben am v10-Vorgang (höchstens ein offenes Projekt je
# Vorgang, Nummer PR-JJNNNN); je Sparte ein Gewerk mit eigener Phase,
# Aufgaben (aus Paket-Vorlagen der projektierung_logik_v1.xlsx), Terminen,
# Dokumenten (data/projekte/<PR>/…), Verlauf und Benachrichtigungen.

GEWERK_PHASEN = ["feinplanung", "feinplanung_abgeschlossen", "montage_geplant",
                 "in_ausfuehrung", "abnahme_offen", "abgeschlossen", "storniert"]
GEWERK_PHASEN_NAMEN = {
    "feinplanung": "Feinplanung",
    "feinplanung_abgeschlossen": "Feinplanung abgeschlossen",
    "montage_geplant": "Montage geplant",
    "in_ausfuehrung": "In Ausführung",
    "abnahme_offen": "Abnahme offen",
    "abgeschlossen": "Abgeschlossen",
    "storniert": "Storniert",
}
AUFGABE_STATUS = ["offen", "in_arbeit", "wartet", "erledigt", "entfaellt"]
AUFGABE_STATUS_NAMEN = {"offen": "Offen", "in_arbeit": "In Arbeit",
                        "wartet": "Wartet auf Dritte", "erledigt": "Erledigt",
                        "entfaellt": "Entfällt"}
PROJEKT_ROLLEN = ["projektierer", "elektroplaner", "feinplaner",
                  "innendienst", "buchhaltung", "montage"]


class Projekt(Base):
    """Bauvorhaben (PR-JJNNNN) am v10-Vorgang; Status abgeleitet vom am
    wenigsten fortgeschrittenen offenen Gewerk (status_cache)."""
    __tablename__ = "projekte"

    id: Mapped[int] = mapped_column(primary_key=True)
    nummer: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    vorgang_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    kunde_id: Mapped[int] = mapped_column(Integer, index=True)
    ausfuehrung_strasse: Mapped[str] = mapped_column(String(200), default="")
    ausfuehrung_plz: Mapped[str] = mapped_column(String(10), default="")
    ausfuehrung_ort: Mapped[str] = mapped_column(String(100), default="")
    projektleiter_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vertriebler_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    kanal: Mapped[str] = mapped_column(String(100), default="")
    status_cache: Mapped[str] = mapped_column(String(30), default="feinplanung")
    abgeschlossen_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notiz_kopf: Mapped[str] = mapped_column(String(500), default="")
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class Gewerk(Base):
    """Ausführungseinheit je Sparte (WP/PV/KL/WB) mit eigener Phase; Auftrag =
    angenommenes Angebot (folgt Versionen .2/.3)."""
    __tablename__ = "gewerke"

    id: Mapped[int] = mapped_column(primary_key=True)
    projekt_id: Mapped[int] = mapped_column(Integer, index=True)
    sparte: Mapped[str] = mapped_column(String(4), default="WP")
    phase: Mapped[str] = mapped_column(String(30), default="feinplanung")
    angebot_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    angebot_id_original: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    auftragswert_original: Mapped[int] = mapped_column(Integer, default=0)  # Cent brutto
    auftragswert_aktuell: Mapped[int] = mapped_column(Integer, default=0)
    feinplaner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    elektroplaner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    storno_grund: Mapped[str] = mapped_column(String(100), default="")
    storno_text: Mapped[str] = mapped_column(String(500), default="")
    montage_fertig_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    freigabe_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    freigabe_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    restarbeiten_text: Mapped[str] = mapped_column(String(1000), default="")
    heizlast_kw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    heizlast_datum: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    heizlast_link: Mapped[str] = mapped_column(String(300), default="")
    phase_geaendert_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class Aufgabe(Base):
    """Aufgabe am Gewerk (oder projektbezogen, gewerk_id leer)."""
    __tablename__ = "aufgaben"

    id: Mapped[int] = mapped_column(primary_key=True)
    gewerk_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    projekt_id: Mapped[int] = mapped_column(Integer, index=True)
    paket_instanz_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    titel: Mapped[str] = mapped_column(String(300), default="")
    beschreibung: Mapped[str] = mapped_column(Text, default="")
    rolle: Mapped[str] = mapped_column(String(20), default="projektierer")
    verantwortlich_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    faellig_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Fälligkeitsregel der Vorlage (+N / FP+N / M-N) – für Nachberechnung,
    # sobald der Feinplanungs-/Montagetermin angelegt wird
    faellig_regel: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(20), default="offen")
    pflicht: Mapped[bool] = mapped_column(Boolean, default=False)
    reihenfolge: Mapped[int] = mapped_column(Integer, default=0)
    wartet_frist_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    wartet_frist_tage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    erledigt_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    erledigt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class AufgabenpaketInstanz(Base):
    """Aktiviertes Aufgabenpaket an einem Gewerk (Quelle: Regel/manuell/Migration)."""
    __tablename__ = "aufgabenpaket_instanzen"

    id: Mapped[int] = mapped_column(primary_key=True)
    gewerk_id: Mapped[int] = mapped_column(Integer, index=True)
    paket_key: Mapped[str] = mapped_column(String(50), default="")
    paket_name: Mapped[str] = mapped_column(String(200), default="")
    aktiviert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    aktiviert_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quelle: Mapped[str] = mapped_column(String(20), default="regel")  # regel | manuell | migration
    deaktiviert_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class ProjektTermin(Base):
    """Termin am Gewerk (V1: einfache Liste, kein Kalender-Sync)."""
    __tablename__ = "projekt_termine"

    id: Mapped[int] = mapped_column(primary_key=True)
    gewerk_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    projekt_id: Mapped[int] = mapped_column(Integer, index=True)
    typ: Mapped[str] = mapped_column(String(20), default="sonstige")  # feinplanung|montage|abnahme|sub|sonstige
    beginn: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ende: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    team_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    person_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    kunde_bestaetigt: Mapped[bool] = mapped_column(Boolean, default=False)
    notiz: Mapped[str] = mapped_column(String(500), default="")
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class ProjektDokument(Base):
    """Datei in der Projekt-Ordnerstruktur data/projekte/<PR>/…"""
    __tablename__ = "projekt_dokumente"

    id: Mapped[int] = mapped_column(primary_key=True)
    projekt_id: Mapped[int] = mapped_column(Integer, index=True)
    gewerk_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ordner: Mapped[str] = mapped_column(String(300), default="")
    dateiname: Mapped[str] = mapped_column(String(300), default="")
    pfad: Mapped[str] = mapped_column(String(500), default="")
    typ: Mapped[str] = mapped_column(String(10), default="sonstige")  # pdf | bild | sonstige
    hochgeladen_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quelle: Mapped[str] = mapped_column(String(10), default="upload")  # auto | upload
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class ProjektVerlauf(Base):
    """Verlauf + Kommentare (append-only; art = kommentar | system)."""
    __tablename__ = "projekt_verlauf"

    id: Mapped[int] = mapped_column(primary_key=True)
    projekt_id: Mapped[int] = mapped_column(Integer, index=True)
    gewerk_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    aufgabe_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    art: Mapped[str] = mapped_column(String(10), default="system")  # kommentar | system
    text: Mapped[str] = mapped_column(Text, default="")
    benutzer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    erwaehnte_ids: Mapped[str] = mapped_column(String(200), default="[]")  # JSON-Liste
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class Benachrichtigung(Base):
    """Glocke in der Kopfzeile (Phase 69); art z. B. aufgabe/erwaehnung/phase."""
    __tablename__ = "benachrichtigungen"

    id: Mapped[int] = mapped_column(primary_key=True)
    benutzer_id: Mapped[int] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(String(500), default="")
    link: Mapped[str] = mapped_column(String(300), default="")
    gelesen_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    art: Mapped[str] = mapped_column(String(30), default="")
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class Team(Base):
    """Montage-Teams (SHK/Elektro/Sonstige) als Stammdaten."""
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    typ: Mapped[str] = mapped_column(String(20), default="SHK")  # SHK | Elektro | Sonstige
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class TeamMitglied(Base):
    __tablename__ = "team_mitglieder"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    benutzer_id: Mapped[int] = mapped_column(Integer, index=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class Subunternehmer(Base):
    """Sub-Stammdaten (Mailversand erst V2)."""
    __tablename__ = "subunternehmer"

    id: Mapped[int] = mapped_column(primary_key=True)
    firma: Mapped[str] = mapped_column(String(200), default="")
    typ: Mapped[str] = mapped_column(String(30), default="Sonstige")
    ansprechpartner: Mapped[str] = mapped_column(String(100), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    telefon: Mapped[str] = mapped_column(String(50), default="")
    notiz: Mapped[str] = mapped_column(String(500), default="")
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class ProjektSub(Base):
    """V1: Sub-Zuordnung am Projekt/Gewerk (Leistung, Status, Termin, Notiz)."""
    __tablename__ = "projekt_subs"

    id: Mapped[int] = mapped_column(primary_key=True)
    projekt_id: Mapped[int] = mapped_column(Integer, index=True)
    gewerk_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_id: Mapped[int] = mapped_column(Integer)
    leistung: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(20), default="angefragt")  # angefragt|beauftragt|bestaetigt|erledigt
    termin: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notiz: Mapped[str] = mapped_column(String(500), default="")
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class ProjektierungParameter(Base):
    """Key-Value der Projektierung (Standard-Zuweisungen, Nummernkreis-Zähler,
    Ordnervorlage JSON, Storno-Gründe JSON, Absender-Postfach, freigabe_modus)."""
    __tablename__ = "projektierung_parameter"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    wert: Mapped[str] = mapped_column(Text, default="")
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


# „Versand vorbereitet“ (v5): Entwurf liegt in Outlook; der Graph-Abgleich
# stellt nach dem tatsächlichen Senden automatisch auf „Versendet“.
# „Individuell“ (v6): wird außerhalb des Tools geschrieben – seit v7 ohne
# Auto-Archiv (individuelle Fälle laufen über die Erfassungs-Statuskette).
# „Versendet (extern)“ (v7): Start-Status externer TAIFUN-Einträge.
# „Überholt“ (v9): durch eine neue Version (.2/.3 …) ersetzt – zählt nicht
# mehr in Statistik, Summenzeile und 90-Tage-Prüflauf.
ANGEBOT_STATUS = ["Entwurf", "Versand vorbereitet", "Versendet", "Angenommen",
                  "Abgelehnt", "Individuell", "Versendet (extern)", "Überholt"]

# Status, die ein externer TAIFUN-Eintrag durchlaufen darf (Abschlussquote)
EXTERN_STATUS = ["Versendet (extern)", "Angenommen", "Abgelehnt"]


class Angebot(Base):
    """Angebot mit Positions-Snapshots (Phase 5)."""
    __tablename__ = "angebote"

    id: Mapped[int] = mapped_column(primary_key=True)
    nummer: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    kunde_id: Mapped[int] = mapped_column(Integer, index=True)
    konfiguration_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="Entwurf")
    datum: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    protokoll_json: Mapped[str] = mapped_column(Text, default="[]")   # Konfigurationsprotokoll
    kfw_json: Mapped[str] = mapped_column(Text, default="{}")         # KfW-Eingaben (F30–F36)
    # Rabatt (Phase 21, nur Innendienst/Admin): Betrag ODER Prozent, keine Position
    rabatt_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rabatt_prozent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rabatt_bezeichnung: Mapped[str] = mapped_column(String(200), default="")
    # E-Signatur (Phase 23): Vor-Ort-Signatur + vorbereiteter Fern-Modus
    signiert_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    signatur_name: Mapped[str] = mapped_column(String(200), default="")
    signatur_protokoll: Mapped[str] = mapped_column(Text, default="")
    signierte_datei: Mapped[str] = mapped_column(String(300), default="")
    signatur_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    signatur_token_gueltig_bis: Mapped[Optional[datetime]] = mapped_column(DateTime,
                                                                           nullable=True)
    # Mail-Verlauf (Phase 27): Konversations-ID der Angebots-Mail aus Graph
    graph_conversation_id: Mapped[Optional[str]] = mapped_column(String(200),
                                                                 nullable=True)
    # Archiv (v5): versendete/angenommene/abgelehnte Angebote werden nicht
    # gelöscht (Aufbewahrung), sondern aus der Standardansicht genommen
    archiviert: Mapped[bool] = mapped_column(Boolean, default=False)
    # monday-Rückspielung (v5, Phase 32): "" | ok | fehler | uebersprungen;
    # Protokoll = eine Zeile je Versuch mit Zeitstempel
    monday_rueck_status: Mapped[str] = mapped_column(String(20), default="")
    monday_rueck_protokoll: Mapped[str] = mapped_column(Text, default="")
    konfigurator_typ: Mapped[str] = mapped_column(String(10), default="WP")   # v5
    # Vertriebler (v5-Nachtrag): normalerweise über die verknüpfte Erfassung;
    # dieses Feld greift nur bei manuellen Angeboten ohne Erfassung
    vertriebler_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Förderung (v6): manuell überschriebener Gesamt-Zuschuss (Cent; None =
    # automatisch). Seit v8 nur noch Altbestand – die Baustein-Overrides unten
    # ersetzen das Eingabefeld; ein gesetzter Altwert wird weiter angezeigt
    # und beim Speichern der Bausteine zurückgesetzt.
    foerderung_manuell_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    foerderung_ausblenden: Mapped[bool] = mapped_column(Boolean, default=False)
    # Förder-Bausteine (v8): einzelne Overrides, None = automatisch
    foerder_grund_prozent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    foerder_klima_prozent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    foerder_einkommen_prozent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    foerder_hoechstkosten_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Rechnungsanschrift (v8): abweichend vom Ausführungsort (= Kundenadresse
    # aus monday); leer = identisch. Gefüllt aus den Katalog-Antworten O06/O09–O12.
    rechnung_name: Mapped[str] = mapped_column(String(200), default="")
    rechnung_strasse: Mapped[str] = mapped_column(String(200), default="")
    rechnung_plz: Mapped[str] = mapped_column(String(10), default="")
    rechnung_ort: Mapped[str] = mapped_column(String(100), default="")
    # Angebotsverfolgung (v6): Hot-Ampel (heiss/warm/kalt/""), Wiedervorlage
    verfolgung_ampel: Mapped[str] = mapped_column(String(10), default="")
    wiedervorlage_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Externe Angebotseinträge (v7): in TAIFUN geschriebene Angebote – nur
    # Eintrag mit Endbetrag (brutto), ohne PDF/Editor/Versand; die
    # TAIFUN-Nummer ist optional nachtragbar (Badge „Nummer fehlt“)
    extern: Mapped[bool] = mapped_column(Boolean, default=False)
    taifun_nummer: Mapped[str] = mapped_column(String(30), default="")
    extern_endbetrag_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Versionierung (v9): „Überarbeiten“ erzeugt <Stamm>.2/.3 … als Entwurf;
    # vorgaenger_id zeigt auf die ersetzte Version (Status „Überholt“)
    vorgaenger_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # v10: Vorgangszugehörigkeit (Akte); Migration setzt sie rückwirkend
    vorgang_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    # v10 (Phase 61/62): externer TAIFUN-Eintrag kann übergangsweise ein PDF
    # tragen – nur damit ist er im Kombi-Versand wählbar
    extern_pdf_pfad: Mapped[str] = mapped_column(String(300), default="")
    extern_pdf_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # v11 (Projektierung, Phase 64): Verknüpfung zum Gewerk nach „Angebot → Projekt"
    projekt_gewerk_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    # Bedingte Angebotsvermerke (v9, Blatt "Vermerke"): beim Anlegen
    # ausgewertete Texte für das PDF (Ende Positionsteil vor Summenblock)
    vermerke_json: Mapped[str] = mapped_column(Text, default="[]")
    # Angebotsprofil (v9): None = automatisch über den Kanal des Kunden;
    # vortext_text überschreibt den Profil-Vortext (leer = Standard)
    profil_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vortext_text: Mapped[str] = mapped_column(Text, default="")
    # Abgelehnt-Prozess (v8): Pflicht-Grund (Auswahlliste der Parametrierung
    # bzw. "90 Tage Ablauf" aus dem täglichen Prüflauf) + optionaler Freitext
    ablehnungsgrund: Mapped[str] = mapped_column(String(100), default="")
    ablehnungsgrund_text: Mapped[str] = mapped_column(String(500), default="")
    # Statistik (v6): Zeitpunkte der Statuswechsel (über angebot_status_setzen)
    versendet_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    angenommen_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    abgelehnt_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    positionen: Mapped[list["AngebotsPosition"]] = relationship(
        back_populates="angebot", order_by="AngebotsPosition.sort",
        cascade="all, delete-orphan")

    @property
    def stamm_nummer(self) -> str:
        """v9: Angebotsnummer ohne Versionssuffix (AN-C-261079.2 → AN-C-261079)."""
        basis, punkt, rest = self.nummer.rpartition(".")
        return basis if punkt and rest.isdigit() else self.nummer

    def rabatt_effektiv_cent(self, brutto_cent: int) -> int:
        """Rabatt in Cent (Betrag direkt, Prozent vom Brutto), nie über dem Brutto.
        Seit Phase 26 ist der Rabatt ein BRUTTO-Abzug nach dem Gesamt-Betrag."""
        if self.rabatt_cent:
            return min(self.rabatt_cent, brutto_cent)
        if self.rabatt_prozent:
            betrag = int((Decimal(brutto_cent) * Decimal(str(self.rabatt_prozent))
                          / 100).quantize(Decimal("1")))
            return min(betrag, brutto_cent)
        return 0

    def summen(self) -> dict:
        """Netto → 19 % USt → Gesamt-Betrag → − Rabatt (brutto) → = Endbetrag
        (Phase 26); EP-Positionen zählen nicht mit, der Rabatt ist keine Position.
        Externe TAIFUN-Einträge (v7) haben nur einen festen Endbetrag brutto –
        Netto/USt sind dort unbekannt und bleiben 0."""
        if self.extern:
            betrag = self.extern_endbetrag_cent or 0
            return {"netto": 0, "ust": 0, "brutto": betrag,
                    "rabatt": 0, "endbetrag": betrag}
        netto = 0
        for p in self.positionen:
            # bauseits (v5) und Alternativ-Positionen (v10) zählen nie mit
            if not p.ep_flag and not p.bauseits and not p.alternativ:
                netto += p.gesamt_cent
        ust = int(Decimal(netto) * Decimal("0.19"))
        brutto = netto + ust
        rabatt = self.rabatt_effektiv_cent(brutto)
        return {"netto": netto, "ust": ust, "brutto": brutto,
                "rabatt": rabatt, "endbetrag": brutto - rabatt}

    def nummerierung(self) -> list[str]:
        """Anzeigenummer je Position (v5) in Sortierreihenfolge: eigene Nummer,
        sonst fortlaufend 001, 002, … – Editor und PDF nutzen dieselbe Liste."""
        return [((p.anzeige_nr or "").strip() or f"{lfd:03d}")
                for lfd, p in enumerate(self.positionen, 1)]

    def deckungsbeitrag(self) -> dict:
        """Σ VK netto − Σ Material-EK (ohne EP). Nur Innendienst, nie im PDF.
        Der Brutto-Rabatt mindert den DB um seinen Netto-Anteil (÷ 1,19; Phase 26).
        Externe TAIFUN-Einträge (v7) haben keinen DB im Tool."""
        if self.extern:
            return {"vk": 0, "ek": 0, "db": 0, "prozent": 0.0,
                    "rabatt": 0, "ohne_ek": []}
        vk = 0
        ek = 0
        ohne_ek = []
        for p in self.positionen:
            if p.ep_flag or p.bauseits or p.alternativ:
                continue
            vk += p.gesamt_cent   # enthält Positionsrabatt und geänderte Preise (v5)
            if p.ek_cent is None:
                ohne_ek.append(p)
            else:
                ek += int((Decimal(str(p.menge)) * Decimal(p.ek_cent))
                          .quantize(Decimal("1")))
        rabatt_brutto = self.rabatt_effektiv_cent(self.summen()["brutto"])
        rabatt_netto = int((Decimal(rabatt_brutto) / Decimal("1.19"))
                           .quantize(Decimal("1")))
        vk_nach_rabatt = max(0, vk - rabatt_netto)
        db = vk_nach_rabatt - ek
        prozent = (db / vk_nach_rabatt * 100) if vk_nach_rabatt else 0.0
        return {"vk": vk_nach_rabatt, "ek": ek, "db": db, "prozent": prozent,
                "rabatt": rabatt_netto, "ohne_ek": ohne_ek}


class AngebotsPosition(Base):
    """Snapshot einer Angebotsposition – unabhängig vom Artikelstamm."""
    __tablename__ = "angebotspositionen"

    id: Mapped[int] = mapped_column(primary_key=True)
    angebot_id: Mapped[int] = mapped_column(ForeignKey("angebote.id"), index=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    block_nr: Mapped[int] = mapped_column(Integer, default=0)
    gruppe: Mapped[str] = mapped_column(String(300), default="")      # Gruppen-Überschrift
    # Interne Referenz (Phase 18): TAIFUN-Pos./Z-Nr. + GUID; die angezeigte
    # Positionsnummer ist die fortlaufende Nummer (001, 002, ...) je Angebot.
    pos_nr: Mapped[str] = mapped_column(String(10), default="")
    guid: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    bezeichnung: Mapped[str] = mapped_column(String(300), default="")
    beschreibung: Mapped[str] = mapped_column(Text, default="")
    menge: Mapped[float] = mapped_column(Float, default=1.0)
    einheit: Mapped[str] = mapped_column(String(20), default="")
    e_preis_cent: Mapped[int] = mapped_column(Integer, default=0)
    ep_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    # v9: Profil-Sonderpreis (z. B. Enni: Pos. 015 zu 599 €) –
    # Kennzeichen für die Anzeige; der DB rechnet mit dem echten EK
    sonderpreis: Mapped[bool] = mapped_column(Boolean, default=False)
    ek_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # EK-Snapshot (Phase 11)
    # Angebots-Editor v5 (Phase 34):
    anzeige_nr: Mapped[str] = mapped_column(String(10), default="")      # eigene Positionsnummer (leer = fortlaufend)
    original_preis_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # vor manueller Änderung
    rabatt_prozent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)       # Positionsrabatt %
    rabatt_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)          # Positionsrabatt €
    bauseits: Mapped[bool] = mapped_column(Boolean, default=False)       # PDF „bauseits“, zählt nirgends
    # v10 (Phase 61): „Alternativ – in anderem Angebot enthalten“: Preis wird
    # ausgewiesen, zählt aber nicht in Summe/KfW-Basis/DB; alternativ_zu
    # verweist auf das Geschwister-Angebot des Vorgangs (oder Freitext)
    alternativ: Mapped[bool] = mapped_column(Boolean, default=False)
    alternativ_zu: Mapped[str] = mapped_column(String(200), default="")

    angebot: Mapped["Angebot"] = relationship(back_populates="positionen")

    @property
    def zeilen_cent(self) -> int:
        """Menge × Einzelpreis vor Positionsrabatt."""
        return int((Decimal(str(self.menge)) * Decimal(self.e_preis_cent))
                   .quantize(Decimal("1")))

    @property
    def rabatt_effektiv_cent(self) -> int:
        """Positionsrabatt in Cent (Betrag oder Prozent vom Zeilenwert), nie > Zeilenwert."""
        zeile = self.zeilen_cent
        if self.rabatt_cent:
            return max(0, min(self.rabatt_cent, zeile))
        if self.rabatt_prozent:
            betrag = int((Decimal(zeile) * Decimal(str(self.rabatt_prozent)) / 100)
                         .quantize(Decimal("1")))
            return max(0, min(betrag, zeile))
        return 0

    @property
    def rabatt_text(self) -> str:
        """Kurzform für Editor/PDF: „10 %“ oder „50,00 €“; leer ohne Rabatt."""
        if self.rabatt_cent:
            euro = Decimal(self.rabatt_cent) / 100
            return f"{euro:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        if self.rabatt_prozent:
            p = Decimal(str(self.rabatt_prozent)).normalize()
            return f"{p:f}".replace(".", ",") + " %"
        return ""

    @property
    def preis_geaendert(self) -> bool:
        return (self.original_preis_cent is not None
                and self.original_preis_cent != self.e_preis_cent)

    @property
    def gesamt_cent(self) -> int:
        """Zeilenwert nach Positionsrabatt – Basis für Summen, KfW und DB."""
        return self.zeilen_cent - self.rabatt_effektiv_cent

    @property
    def titel(self) -> str:
        if self.bezeichnung:
            return self.bezeichnung
        return self.beschreibung.splitlines()[0] if self.beschreibung else ""


class AngebotsNotiz(Base):
    """Notizen-Verlauf zur Angebotsverfolgung (v6): nur anhängen."""
    __tablename__ = "angebots_notizen"

    id: Mapped[int] = mapped_column(primary_key=True)
    angebot_id: Mapped[int] = mapped_column(ForeignKey("angebote.id"), index=True)
    benutzer_name: Mapped[str] = mapped_column(String(100), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Textblock(Base):
    """v9: editierbare Nach-/Vortext-Blöcke (Parametrierung). Konventionen im
    Text: "# " = große Überschrift, "## " = fette Absatz-Überschrift,
    "---" allein = Seitenumbruch, "[UNTERSCHRIFT]" = Ort/Datum-Unterschriften-
    block (inkl. elektronischer Signatur), "- " = Haken-Aufzählung (Vortext),
    {briefanrede} = Anrede-Platzhalter (Vortext)."""
    __tablename__ = "textbloecke"

    id: Mapped[int] = mapped_column(primary_key=True)
    art: Mapped[str] = mapped_column(String(10), default="nachtext")  # nachtext | vortext
    name: Mapped[str] = mapped_column(String(100))
    text: Mapped[str] = mapped_column(Text, default="")
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                      onupdate=datetime.now)


# Regel-Kennungen der Profile: steuern die fest programmierten Positions-
# und Bogenregeln (Enni: nur P01, 015 zum Sonderpreis + 162, kein 014;
# SWD: P01–P03 nur Protokoll). "standard"/"sparkasse" haben keine Regeln.
PROFIL_KENNUNGEN = ["standard", "enni", "swd", "sparkasse"]


class Profil(Base):
    """v9: Angebotsprofil je Vertriebskanal – bündelt Nachtext-Block,
    Positionsregeln (regel_kennung) und Versandregeln. Auto-Auswahl über
    kanalwerte (kommagetrennt, Teilstring-Abgleich), Fallback Standard."""
    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    regel_kennung: Mapped[str] = mapped_column(String(20), default="standard")
    nachtext_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vortext_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    kanalwerte: Mapped[str] = mapped_column(String(200), default="")
    versand_cc: Mapped[str] = mapped_column(String(200), default="")      # zusätzl. CC
    empfaenger_leer: Mapped[bool] = mapped_column(Boolean, default=False)  # SWD
    ohne_vollmacht: Mapped[bool] = mapped_column(Boolean, default=False)


ABLEHNUNGSGRUND_STARTWERTE = [
    "Preis zu hoch", "Wettbewerber beauftragt", "Förderung unsicher/abgelehnt",
    "Projekt verschoben", "Finanzierung gescheitert", "Kunde nicht erreichbar",
    "Technisch nicht umsetzbar", "Sonstiges"]


class AblehnungsGrund(Base):
    """v8: pflegbare Auswahlliste für den Pflichtdialog „Grund der Ablehnung“
    (Parametrierung); der Prüflauf nutzt zusätzlich den festen Grund
    „90 Tage Ablauf“."""
    __tablename__ = "ablehnungsgruende"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class AngebotsLoeschung(Base):
    """Lösch-Protokoll (v6): jede Löschung eines Angebots jenseits von
    „Entwurf“ wird festgehalten – einsehbar in der Parametrierung."""
    __tablename__ = "angebots_loeschungen"

    id: Mapped[int] = mapped_column(primary_key=True)
    nummer: Mapped[str] = mapped_column(String(20))
    kunde_name: Mapped[str] = mapped_column(String(300), default="")
    status_vorher: Mapped[str] = mapped_column(String(20), default="")
    endbetrag_cent: Mapped[int] = mapped_column(Integer, default=0)
    benutzer_name: Mapped[str] = mapped_column(String(100), default="")
    geloescht_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AngebotsMail(Base):
    """Nachricht aus der Angebots-Konversation (Phase 27, nur lesend).
    Wird alle 15 Minuten über Microsoft Graph abgerufen; graph_id dedupliziert."""
    __tablename__ = "angebots_mails"

    id: Mapped[int] = mapped_column(primary_key=True)
    angebot_id: Mapped[int] = mapped_column(ForeignKey("angebote.id"), index=True)
    graph_id: Mapped[str] = mapped_column(String(300), unique=True)
    von_name: Mapped[str] = mapped_column(String(200), default="")
    von_email: Mapped[str] = mapped_column(String(200), default="")
    empfangen_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    betreff: Mapped[str] = mapped_column(String(500), default="")
    vorschau: Mapped[str] = mapped_column(Text, default="")   # bodyPreview aus Graph
    # True = Antwort des Kunden (nicht vom eigenen Postfach gesendet)
    eingehend: Mapped[bool] = mapped_column(Boolean, default=True)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


# ================= v12: Lead-Management V1 (PLAN_LEAD_V1, Phasen 73-82) =============
# Lead = Vorgang (v10) – keine eigene Lead-Tabelle; der Vorgang trägt den
# Lead-Kopf (Spalten via db._NACHTRAEGLICHE_SPALTEN) und die Lead-Phase.

LEAD_PHASEN = ["neu", "in_kontaktierung", "qualifiziert", "terminiert",
               "erfasst", "angebot", "gewonnen", "verloren",
               "zurueckgestellt", "nicht_erreicht", "unqualifiziert"]
LEAD_PHASEN_NAMEN = {
    "neu": "Neu", "in_kontaktierung": "In Kontaktierung",
    "qualifiziert": "Qualifiziert", "terminiert": "Terminiert",
    "erfasst": "Erfasst", "angebot": "Angebot", "gewonnen": "Gewonnen",
    "verloren": "Verloren", "zurueckgestellt": "Zurückgestellt",
    "nicht_erreicht": "Nicht erreicht", "unqualifiziert": "Unqualifiziert",
}
# Manuelle Seitenzustände haben Vorrang vor der Ableitung (Konzept 3.1)
LEAD_PHASEN_MANUELL = ("zurueckgestellt", "nicht_erreicht", "unqualifiziert")

ANRUF_ERGEBNISSE = ["erreicht", "nicht_erreicht", "besetzt", "mailbox",
                    "rueckruf_gewuenscht", "falsche_nummer", "kein_interesse"]
ANRUF_ERGEBNIS_NAMEN = {
    "erreicht": "Erreicht", "nicht_erreicht": "Nicht erreicht",
    "besetzt": "Besetzt", "mailbox": "Mailbox",
    "rueckruf_gewuenscht": "Rückruf gewünscht",
    "falsche_nummer": "Falsche Nummer", "kein_interesse": "Kein Interesse",
}

VOT_STATUS = ["geplant", "bestaetigt", "verschoben", "no_show", "erfolgt", "abgesagt"]
VOT_STATUS_NAMEN = {"geplant": "Geplant", "bestaetigt": "Bestätigt",
                    "verschoben": "Verschoben", "no_show": "No-Show",
                    "erfolgt": "Erfolgt", "abgesagt": "Abgesagt"}


class LeadQuelle(Base):
    """Woher der Lead kommt (Website, Landingpage, Portal, Partner, monday …)."""
    __tablename__ = "lead_quellen"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    typ: Mapped[str] = mapped_column(String(20), default="website")
    kanal: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    kosten_je_lead_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    standard_sparten: Mapped[str] = mapped_column(String(100), default="[]")  # JSON
    score_bonus: Mapped[int] = mapped_column(Integer, default=0)
    parser_regel_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    api_key: Mapped[str] = mapped_column(String(64), default="")   # REST-Endpunkt
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class Kampagne(Base):
    __tablename__ = "kampagnen"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    quelle_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    von: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    bis: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    budget_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    utm_campaign: Mapped[str] = mapped_column(String(200), default="")
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class LeadAktivitaet(Base):
    """Timeline-Eintrag (Anruf, Mail, Status …); der v10-Notizen-Chat bleibt in
    seiner Tabelle – die Timeline liest beide zusammen (Union nach Zeit)."""
    __tablename__ = "lead_aktivitaeten"

    id: Mapped[int] = mapped_column(primary_key=True)
    vorgang_id: Mapped[int] = mapped_column(Integer, index=True)
    typ: Mapped[str] = mapped_column(String(20), default="notiz")
    ergebnis: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    dauer_sek: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    benutzer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    zeitpunkt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    naechste_aktion_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class LeadQualifizierung(Base):
    __tablename__ = "lead_qualifizierung"

    id: Mapped[int] = mapped_column(primary_key=True)
    vorgang_id: Mapped[int] = mapped_column(Integer, index=True)
    sparte: Mapped[str] = mapped_column(String(4), default="WP")
    antworten: Mapped[str] = mapped_column(Text, default="{}")   # JSON {frage_key: wert}
    score_punkte: Mapped[int] = mapped_column(Integer, default=0)
    score_klasse: Mapped[str] = mapped_column(String(1), default="C")
    abgeschlossen_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    benutzer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class VotTermin(Base):
    """Vor-Ort-Termin des Lead-Moduls (auch aus dem monday-VOT-Datum abgeleitet)."""
    __tablename__ = "vot_termine"

    id: Mapped[int] = mapped_column(primary_key=True)
    vorgang_id: Mapped[int] = mapped_column(Integer, index=True)
    ad_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    beginn: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ende: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    adresse: Mapped[str] = mapped_column(String(300), default="")
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="geplant")
    outlook_event_id: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    bestaetigung_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    erinnerung_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fahrzeit_hin_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    umweg_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quelle: Mapped[str] = mapped_column(String(10), default="manuell")  # assistent|manuell|monday
    grund_text: Mapped[str] = mapped_column(String(500), default="")
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class AdProfil(Base):
    """Terminierungs-Profil des Außendienstlers (Assistent, Phase 77)."""
    __tablename__ = "ad_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    benutzer_id: Mapped[int] = mapped_column(Integer, unique=True)
    start_adresse: Mapped[str] = mapped_column(String(300), default="")
    start_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    start_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    arbeitszeiten: Mapped[str] = mapped_column(Text, default="{}")   # JSON je Wochentag
    termin_dauer_min: Mapped[int] = mapped_column(Integer, default=90)
    puffer_min: Mapped[int] = mapped_column(Integer, default=15)
    max_termine_tag: Mapped[int] = mapped_column(Integer, default=4)
    gebiet_plz_praefixe: Mapped[str] = mapped_column(String(300), default="[]")  # JSON
    kalender_postfach: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    aktiv_terminierung: Mapped[bool] = mapped_column(Boolean, default=False)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class KommunikationLog(Base):
    """Warteschlange + Protokoll der Kunden-Mails (Phase 78, Sendesperre)."""
    __tablename__ = "kommunikation_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    vorgang_id: Mapped[int] = mapped_column(Integer, index=True)
    termin_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    kanal: Mapped[str] = mapped_column(String(10), default="mail")
    vorlage_key: Mapped[str] = mapped_column(String(50), default="")
    an: Mapped[str] = mapped_column(String(200), default="")
    betreff: Mapped[str] = mapped_column(String(300), default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    anhang_pfad: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    geplant_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    gesendet_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="geplant")
    fehler_text: Mapped[str] = mapped_column(String(500), default="")
    modus: Mapped[str] = mapped_column(String(10), default="protokoll")
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class ParserRegel(Base):
    """Mail-Parser-Regel (Phase 75): Muster + Feldzuordnung je Quelle."""
    __tablename__ = "parser_regeln"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    quelle_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    absender_muster: Mapped[str] = mapped_column(String(300), default="")
    betreff_muster: Mapped[str] = mapped_column(String(300), default="")
    format: Mapped[str] = mapped_column(String(15), default="zeilen")
    feldzuordnung: Mapped[str] = mapped_column(Text, default="{}")   # JSON
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    zuletzt_getroffen_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class GeocodeCache(Base):
    __tablename__ = "geocode_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    adresse_norm: Mapped[str] = mapped_column(String(300), unique=True)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    anbieter: Mapped[str] = mapped_column(String(20), default="")
    stand: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    status: Mapped[str] = mapped_column(String(10), default="ok")   # ok | fehler
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class RoutingCache(Base):
    __tablename__ = "routing_cache"
    __table_args__ = (UniqueConstraint("von_key", "nach_key",
                                       name="uq_routing_von_nach"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    von_key: Mapped[str] = mapped_column(String(30))
    nach_key: Mapped[str] = mapped_column(String(30))
    minuten: Mapped[float] = mapped_column(Float, default=0)
    km: Mapped[float] = mapped_column(Float, default=0)
    anbieter: Mapped[str] = mapped_column(String(20), default="")
    gueltig_bis: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class LeadParameter(Base):
    """Key-Value des Lead-Managements (Demo-Schalter, SLA, Routing, Absender …)."""
    __tablename__ = "lead_parameter"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    wert: Mapped[str] = mapped_column(Text, default="")
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)


class LeadPosteingang(Base):
    """„Posteingang unklar“ (Phase 75): Mails aus leads@, die keine
    Parser-Regel treffen – mit Ein-Klick-Anlage. (Tabelle nicht im Plan
    gelistet; Entscheidung in docs/leadmanagement-entscheidungen.md.)"""
    __tablename__ = "lead_posteingang"

    id: Mapped[int] = mapped_column(primary_key=True)
    graph_id: Mapped[str] = mapped_column(String(300), unique=True)
    absender: Mapped[str] = mapped_column(String(200), default="")
    betreff: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    empfangen_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="offen")  # offen|ignoriert|angelegt
    vorgang_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    erstellt_von: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                  onupdate=datetime.now)
