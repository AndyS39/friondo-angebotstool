# Datenbankmodelle des Angebotstools.
# Phase 1: Kunden · Phase 2: Artikel. Weitere Modelle folgen in späteren Phasen.

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
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
    if neuer_status == "Versendet" and angebot.versendet_am is None:
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


# „Individuell“ (v6): Vorgang wird außerhalb des Tools geschrieben –
# Setzen archiviert automatisch, damit keine „Leichen“ in den Listen liegen.
# „In TAIFUN zu schreiben“ (v7): Warteschlange des Zwei-Wege-Prozesses –
# Freitext-Erfassungen landen direkt hier.
ERFASSUNG_STATUS = ["Neu", "In Bearbeitung", "Erledigt", "Individuell",
                    "In TAIFUN zu schreiben"]


class Erfassung(Base):
    """Mobile Außendienst-Erfassung (Phase 13): Antworten + Ampel; der Innendienst
    verarbeitet sie in der Erfassungsliste (Phase 14) weiter."""
    __tablename__ = "erfassungen"

    id: Mapped[int] = mapped_column(primary_key=True)
    kunde_id: Mapped[int] = mapped_column(Integer, index=True)
    benutzer_id: Mapped[int] = mapped_column(Integer, index=True)      # Vertriebler
    antworten_json: Mapped[str] = mapped_column(Text, default="{}")
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
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                     onupdate=datetime.now)

    @property
    def interessen(self) -> list[str]:
        return interesse_liste(self.interesse)

    @property
    def anzeige_name(self) -> str:
        person = " ".join(t for t in (self.vorname, self.nachname) if t)
        return person or self.email or f"monday-Item {self.monday_item_id}"


# „Versand vorbereitet“ (v5): Entwurf liegt in Outlook; der Graph-Abgleich
# stellt nach dem tatsächlichen Senden automatisch auf „Versendet“.
# „Individuell“ (v6): wird außerhalb des Tools geschrieben → Auto-Archiv.
ANGEBOT_STATUS = ["Entwurf", "Versand vorbereitet", "Versendet", "Angenommen",
                  "Abgelehnt", "Individuell"]


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
    # Förderung (v6): manuell überschriebener Zuschuss (Cent; None = automatisch)
    # und Schalter, den KfW-Block im PDF komplett auszublenden
    foerderung_manuell_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    foerderung_ausblenden: Mapped[bool] = mapped_column(Boolean, default=False)
    # Angebotsverfolgung (v6): Hot-Ampel (heiss/warm/kalt/""), Wiedervorlage
    verfolgung_ampel: Mapped[str] = mapped_column(String(10), default="")
    wiedervorlage_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Statistik (v6): Zeitpunkte der Statuswechsel (über angebot_status_setzen)
    versendet_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    angenommen_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    abgelehnt_am: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    positionen: Mapped[list["AngebotsPosition"]] = relationship(
        back_populates="angebot", order_by="AngebotsPosition.sort",
        cascade="all, delete-orphan")

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
        (Phase 26); EP-Positionen zählen nicht mit, der Rabatt ist keine Position."""
        netto = 0
        for p in self.positionen:
            if not p.ep_flag and not p.bauseits:   # bauseits (v5) zählt nie mit
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
        Der Brutto-Rabatt mindert den DB um seinen Netto-Anteil (÷ 1,19; Phase 26)."""
        vk = 0
        ek = 0
        ohne_ek = []
        for p in self.positionen:
            if p.ep_flag or p.bauseits:
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
    ek_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # EK-Snapshot (Phase 11)
    # Angebots-Editor v5 (Phase 34):
    anzeige_nr: Mapped[str] = mapped_column(String(10), default="")      # eigene Positionsnummer (leer = fortlaufend)
    original_preis_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # vor manueller Änderung
    rabatt_prozent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)       # Positionsrabatt %
    rabatt_cent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)          # Positionsrabatt €
    bauseits: Mapped[bool] = mapped_column(Boolean, default=False)       # PDF „bauseits“, zählt nirgends

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
