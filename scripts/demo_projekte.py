# -*- coding: utf-8 -*-
# Demo-Projekte fuer die Projektierung (Andreas, 27.09.2026): zwei
# realistische Beispielprojekte zum Testen - idempotent (laeuft nur, wenn
# die Demo-Kunden noch nicht existieren).
#
#   venv\Scripts\python scripts\demo_projekte.py
#
# Projekt A "Demo Planung, Petra":  WP in Feinplanung VOT, Steckbrief aus
#   der Erfassung vorbelegt, FP-Termin naechste Woche. Kunde hat auch
#   PV-Interesse -> die Vorgangsakte zeigt die neuen Galerie-Reiter WP/PV.
# Projekt B "Demo Montage, Bernd":  WP in Phase Montage, Montageteam 1 mit
#   Termin uebermorgen (Kunde bestaetigt), Steckbrief + Heizlast aus der
#   abgeschlossenen Feinplanungs-Erfassung, Fotos in vier Galerie-Ordnern
#   -> sichtbar im Team-Kalender UND im Montage-Backend (/montage).

import io
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw

from app.db import SessionLocal
from app import galerie as galerie_modul
from app import projektierung as kern
from app.models import (Angebot, AngebotsPosition, Erfassung, Kunde, Team,
                        Vorgang)


def bild(text: str, farbe) -> bytes:
    puffer = io.BytesIO()
    b = Image.new("RGB", (1200, 900), farbe)
    zeichnung = ImageDraw.Draw(b)
    zeichnung.rectangle([40, 40, 1160, 860], outline=(255, 255, 255), width=6)
    zeichnung.text((80, 80), f"DEMO\n{text}", fill=(255, 255, 255))
    b.save(puffer, "JPEG", quality=80)
    return puffer.getvalue()


def kunde_anlegen(s, vorname, nachname, ort, plz, strasse, interesse):
    kunde = Kunde(vorname=vorname, nachname=nachname, ort=ort, plz=plz,
                  strasse=strasse, telefon="0201 555123",
                  email=f"{vorname.lower()}@demo.example", interesse=interesse)
    s.add(kunde)
    s.flush()
    return kunde


def angebot_anlegen(s, kunde, nummer, positionen):
    vorgang = Vorgang(kunde_id=kunde.id)
    s.add(vorgang)
    s.flush()
    angebot = Angebot(nummer=nummer, kunde_id=kunde.id, vorgang_id=vorgang.id,
                      status="Angenommen", konfigurator_typ="WP")
    s.add(angebot)
    s.flush()
    for nr, bez, preis in positionen:
        s.add(AngebotsPosition(angebot_id=angebot.id, pos_nr=nr,
                               bezeichnung=bez, menge=1, e_preis_cent=preis))
    return vorgang, angebot


def main() -> int:
    s = SessionLocal()
    try:
        if s.query(Kunde).filter(Kunde.nachname == "Demo Planung").count():
            print("Demo-Projekte existieren bereits - nichts zu tun.")
            return 0

        # ---------------- Projekt A: Planung ----------------
        kunde_a = kunde_anlegen(s, "Petra", "Demo Planung", "Essen", "45127",
                                "Beispielweg 12", "WP,PV")
        vorgang_a, angebot_a = angebot_anlegen(s, kunde_a, "AN-DEMO-2601", [
            ("047", "Bosch WP-Paket 7 kW (CS3800i, AWM)", 1850000),
            ("010", "Fundament Aussengeraet", 95000),
            ("065", "300-l-Warmwasserspeicher", 165000),
            ("152", "Unterverteilung setzen", 88000),
        ])
        s.add(Erfassung(
            kunde_id=kunde_a.id, benutzer_id=1, vorgang_id=vorgang_a.id,
            angebot_id=angebot_a.id, sparte="WP", status="Erledigt",
            antworten_json=json.dumps({
                "A01": "Gasheizung", "A04": "Keller", "A07": "Nein",
                "N02": "Ja", "N04": "an der Hauswand", "N09": "Nein",
                "P01": "Ja", "P02": "Ja", "P03": "Nein",
                "E02": "Ja", "E03": "2-Feld"}, ensure_ascii=False)))
        s.flush()
        projekt_a = kern.projekt_anlegen(s, angebot_a, projektleiter_id=1)
        gewerk_a = kern.gewerk_anlegen(s, projekt_a, angebot_a, "WP")
        ok, meldung = kern.phase_wechseln(
            s, gewerk_a, "feinplanung_vot", "Demo-Daten", benutzer=None)
        print(f"Projekt A {projekt_a.nummer}: Phase -> feinplanung_vot ({meldung})")
        from app.models import ProjektTermin
        fp_beginn = datetime.now() + timedelta(days=5)
        s.add(ProjektTermin(projekt_id=projekt_a.id, gewerk_id=gewerk_a.id,
                            typ="feinplanung",
                            beginn=fp_beginn.replace(hour=9, minute=0),
                            ende=fp_beginn.replace(hour=10, minute=30)))

        # ---------------- Projekt B: Montage ----------------
        kunde_b = kunde_anlegen(s, "Bernd", "Demo Montage", "Duisburg",
                                "47051", "Musterallee 8", "WP")
        vorgang_b, angebot_b = angebot_anlegen(s, kunde_b, "AN-DEMO-2602", [
            ("048", "Bosch WP-Paket 10 kW (CS3800i, AWM)", 2050000),
            ("010", "Fundament Aussengeraet", 95000),
            ("135", "Mobiler Kran (Eventualposition)", 120000),
        ])
        s.add(Erfassung(
            kunde_id=kunde_b.id, benutzer_id=1, vorgang_id=vorgang_b.id,
            angebot_id=angebot_b.id, sparte="WP", status="Erledigt",
            antworten_json=json.dumps({
                "A01": "Oelheizung", "A04": "Keller", "A07": "Ja",
                "A08": "Stahl, geschweisst", "A09": "5000 l",
                "N02": "Ja", "N09": "Ja", "P01": "Ja", "P02": "Ja",
                "P03": "Ja", "E03": "3-Feld"}, ensure_ascii=False)))
        s.flush()
        projekt_b = kern.projekt_anlegen(s, angebot_b, projektleiter_id=1)
        gewerk_b = kern.gewerk_anlegen(s, projekt_b, angebot_b, "WP")
        # Feinplanungs-Erfassung abgeschlossen (schreibt Steckbrief+Heizlast)
        gewerk_b.fp_antworten_json = json.dumps({
            "FP-A01": "Boden", "FP-A02": "Ja", "FP-A03": "8",
            "FP-A04": "Keller", "FP-A14": "Ja", "FP-A15": "Hofeinfahrt",
            "FP-E01": "Dreifeld", "FP-E02": "Ja", "FP-E03": "Ja",
            "FP-E04": "Ja", "FP-O01": "Ja", "FP-O02": "5000",
            "FP-O03": "Stahl, Kellerzugang eng", "FP-H01": "",
            "FP-H02": "Ja", "FP-L01": "9,5", "FP-L02": "Heizreport"},
            ensure_ascii=False)
        ok, meldung = kern.fp_abschliessen(s, gewerk_b)
        print(f"Projekt B FP-Abschluss: {ok} ({meldung})")
        # Montageteam 1 + Termin uebermorgen, Kunde bestaetigt
        team = (s.query(Team).filter(Team.name == "Montageteam 1").first()
                or s.query(Team).filter(Team.typ != "sub").first())
        beginn = (datetime.now() + timedelta(days=2)).replace(hour=7, minute=30)
        ok, meldung, konflikte = kern.team_termin_zuweisen(
            s, gewerk_b, "wp", team.id, beginn, None, True)
        print(f"Projekt B Team+Termin: {meldung}")
        for ziel in ("feinplanung_vot", "planung", "montagevorbereitung",
                     "montage"):
            ok, meldung = kern.phase_wechseln(s, gewerk_b, ziel, "Demo-Daten")
        print(f"Projekt B {projekt_b.nummer}: Phase -> {gewerk_b.phase}")
        # Fotos in vier Galerie-Ordner (WP)
        for ordner, farbe in [("Alte Heizung", (140, 60, 40)),
                              ("Elektro", (40, 80, 150)),
                              ("Außengerät", (40, 130, 80)),
                              ("Allgemein", (110, 110, 110))]:
            for nr in (1, 2):
                galerie_modul.speichern(
                    s, vorgang_b.id, ordner, f"demo_{nr}.jpg",
                    bild(f"{ordner} {nr}", farbe), quelle="upload",
                    sparte="WP", bemerkung="Demo-Foto")
        s.commit()
        print("Fertig: AN-DEMO-2601/2602 ->",
              projekt_a.nummer, "und", projekt_b.nummer)
        return 0
    finally:
        s.close()


if __name__ == "__main__":
    raise SystemExit(main())
