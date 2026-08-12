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
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    positionen: Mapped[list["AngebotsPosition"]] = relationship(
        back_populates="angebot", order_by="AngebotsPosition.sort",
        cascade="all, delete-orphan")

    def summen(self) -> dict:
        """Netto/USt/Brutto in Cent; EP-Positionen zählen nicht mit."""
        netto = 0
        for p in self.positionen:
            if not p.ep_flag:
                netto += p.gesamt_cent
        ust = int(Decimal(netto) * Decimal("0.19"))
        return {"netto": netto, "ust": ust, "brutto": netto + ust}

    def deckungsbeitrag(self) -> dict:
        """Σ VK netto − Σ Material-EK (ohne EP). Nur Innendienst, nie im PDF.
        Positionen ohne hinterlegten EK werden als Warnliste mitgeliefert."""
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
        db = vk - ek
        prozent = (db / vk * 100) if vk else 0.0
        return {"vk": vk, "ek": ek, "db": db, "prozent": prozent, "ohne_ek": ohne_ek}


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
