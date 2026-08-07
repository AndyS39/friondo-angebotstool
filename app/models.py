# Datenbankmodelle des Angebotstools.
# Phase 1: Kunden · Phase 2: Artikel. Weitere Modelle folgen in späteren Phasen.

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

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
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                      onupdate=datetime.now)

    @property
    def titel(self) -> str:
        """Kurztitel für Listen: Bezeichnung, sonst erste Zeile der Beschreibung."""
        if self.bezeichnung:
            return self.bezeichnung
        return self.beschreibung.splitlines()[0] if self.beschreibung else ""
