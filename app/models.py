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
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    @property
    def anzeige_name(self) -> str:
        """Name für Listen und Auswahlfelder: Firma bzw. 'Nachname, Vorname'."""
        person = ", ".join(t for t in (self.nachname, self.vorname) if t)
        if self.firma and person:
            return f"{self.firma} ({person})"
        return self.firma or person


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
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


ERFASSUNG_STATUS = ["Neu", "In Bearbeitung", "Erledigt"]


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


# Felder, die je Board auf monday-Spalten gemappt werden (Phase 22)
MONDAY_FELDER = ["vot_datum", "verantwortlicher", "anrede", "vorname", "nachname",
                 "strasse", "plz", "ort", "telefon", "email", "status"]


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
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                     onupdate=datetime.now)

    @property
    def anzeige_name(self) -> str:
        person = " ".join(t for t in (self.vorname, self.nachname) if t)
        return person or self.email or f"monday-Item {self.monday_item_id}"


ANGEBOT_STATUS = ["Entwurf", "Versendet", "Angenommen", "Abgelehnt"]


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
            if not p.ep_flag:
                netto += p.gesamt_cent
        ust = int(Decimal(netto) * Decimal("0.19"))
        brutto = netto + ust
        rabatt = self.rabatt_effektiv_cent(brutto)
        return {"netto": netto, "ust": ust, "brutto": brutto,
                "rabatt": rabatt, "endbetrag": brutto - rabatt}

    def deckungsbeitrag(self) -> dict:
        """Σ VK netto − Σ Material-EK (ohne EP). Nur Innendienst, nie im PDF.
        Der Brutto-Rabatt mindert den DB um seinen Netto-Anteil (÷ 1,19; Phase 26)."""
        vk = 0
        ek = 0
        ohne_ek = []
        for p in self.positionen:
            if p.ep_flag:
                continue
            vk += p.gesamt_cent
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

    angebot: Mapped["Angebot"] = relationship(back_populates="positionen")

    @property
    def gesamt_cent(self) -> int:
        return int((Decimal(str(self.menge)) * Decimal(self.e_preis_cent))
                   .quantize(Decimal("1")))

    @property
    def titel(self) -> str:
        if self.bezeichnung:
            return self.bezeichnung
        return self.beschreibung.splitlines()[0] if self.beschreibung else ""


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
