# v28 (PLAN_PROJ_V6 Phasen 136–138, Agent P2): gemeinsame Testbasis der Dateien
# test_proj_v6_notizen.py / _montage.py / _formulare.py (kein test_-Präfix: wird nicht gesammelt) – Testdaten mit Präfix
# „V28P2“ (Kunde proj-v6-p2@test.local), Anmeldung über das signierte Cookie
# (auth.cookie_wert), Aufräumen inkl. Galerie-Dateien auf der Platte.
# Keine Tests in dieser Datei.
import base64
import io

import unittest
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, auth, config
from app import projektierung as kern
from app import vorgaenge as vorgaenge_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Aufgabe, AufgabenpaketInstanz,
                        Benutzer, Erfassung, GalerieDatei, Gewerk, Kunde,
                        MontageFormular, Projekt, ProjektTermin, ProjektVerlauf,
                        Restarbeit, SteckbriefWert, Team, TeamMitglied,
                        TerminBesetzung, Vorgang, VorgangNotizGelesen, VorgangsNotiz,
                        angebot_status_setzen)

TEST_EMAIL = "proj-v6-p2@test.local"
PRAEFIX = "V28P2"


def aufraeumen(s):
    """Alles mit Präfix V28P2 / Test-Mail entfernen (idempotent)."""
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for p in s.query(Projekt).filter_by(kunde_id=k.id):
            for g in s.query(Gewerk).filter_by(projekt_id=p.id):
                s.query(Aufgabe).filter_by(gewerk_id=g.id).delete()
                s.query(AufgabenpaketInstanz).filter_by(gewerk_id=g.id).delete()
                s.query(SteckbriefWert).filter_by(gewerk_id=g.id).delete()
                s.query(MontageFormular).filter_by(gewerk_id=g.id).delete()
                s.query(Restarbeit).filter_by(gewerk_id=g.id).delete()
                s.delete(g)
            for t in s.query(ProjektTermin).filter_by(projekt_id=p.id):
                s.query(TerminBesetzung).filter_by(termin_id=t.id).delete()
                s.delete(t)
            s.query(ProjektVerlauf).filter_by(projekt_id=p.id).delete()
            s.delete(p)
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            # nur die eigenen Dateien löschen – data/vorgaenge/ wird bei parallelen
            # Testläufen (eigene DB-Kopien, gleiche IDs) gemeinsam genutzt
            for d in s.query(GalerieDatei).filter_by(vorgang_id=v.id):
                (config.DATA_ORDNER / d.pfad).unlink(missing_ok=True)
                s.delete(d)
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangNotizGelesen).filter_by(vorgang_id=v.id).delete()
            ordner = config.DATA_ORDNER / "vorgaenge" / str(v.id)
            if ordner.exists():
                for leer in sorted((p for p in ordner.rglob("*") if p.is_dir()), reverse=True):
                    try:
                        leer.rmdir()
                    except OSError:
                        pass
                try:
                    ordner.rmdir()
                except OSError:
                    pass
            s.delete(v)
        s.delete(k)
    for te in s.query(Team).filter(Team.name.like(f"{PRAEFIX}%")):
        s.query(TeamMitglied).filter_by(team_id=te.id).delete()
        s.delete(te)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(TerminBesetzung).filter_by(benutzer_id=b.id).delete()
        s.query(TeamMitglied).filter_by(benutzer_id=b.id).delete()
        s.query(VorgangNotizGelesen).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.commit()


def client_fuer(benutzer_id: int) -> TestClient:
    c = TestClient(app)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


def png_daten_url() -> str:
    """Kleine Unterschrift als PNG-Daten-URL (Pflichtfelder unterschrift)."""
    from PIL import Image, ImageDraw
    bild = Image.new("RGB", (160, 50), "white")
    ImageDraw.Draw(bild).line((10, 40, 60, 10, 110, 40, 150, 15), fill=(27, 42, 94), width=3)
    puffer = io.BytesIO()
    bild.save(puffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(puffer.getvalue()).decode("ascii")


def jpg_bytes(farbe=(200, 40, 40), groesse=(120, 80)) -> bytes:
    from PIL import Image
    puffer = io.BytesIO()
    Image.new("RGB", groesse, farbe).save(puffer, format="JPEG")
    return puffer.getvalue()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.admin = client_fuer(1)

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    # --- Stammdaten --------------------------------------------------------------
    @classmethod
    def benutzer_neu(cls, name: str, rolle: str = "montage", rollen: str = "") -> Benutzer:
        b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, rollen=rollen, aktiv=True,
                     pin_hash=auth.pin_hash("1234"), email=f"{name.lower().replace(' ', '')}@p2.test")
        cls.s.add(b)
        cls.s.commit()
        return b

    @classmethod
    def team_neu(cls, name: str, mitglieder=()) -> Team:
        te = Team(name=f"{PRAEFIX} {name}", typ="montage", aktiv=True, farbe="#3f86c6")
        cls.s.add(te)
        cls.s.flush()
        for b in mitglieder:
            cls.s.add(TeamMitglied(team_id=te.id, benutzer_id=b.id))
        cls.s.commit()
        return te

    @classmethod
    def gewerk_neu(cls, positionen=None, sparte="WP", phase="montagevorbereitung") -> Gewerk:
        """Kunde + Vorgang + angenommenes Angebot + Projekt + Gewerk."""
        kunde = Kunde(anrede="Herr", vorname="Paul", nachname=f"{PRAEFIX} Montage",
                      strasse="Teststr. 5", plz="47139", ort="Duisburg",
                      email=TEST_EMAIL, telefon="0203 1")
        cls.s.add(kunde)
        cls.s.flush()
        angebot = angebot_aufbau.angebot_anlegen(cls.s, kunde.id, sparte=sparte)
        for i, (nr, menge) in enumerate(positionen or [("047", 1)], 1):
            angebot.positionen.append(AngebotsPosition(
                sort=i, pos_nr=nr, bezeichnung=f"Pos {nr}", beschreibung=f"Pos {nr}",
                menge=menge, e_preis_cent=10000))
        angebot_status_setzen(angebot, "Angenommen")
        cls.s.commit()
        if not angebot.vorgang_id:
            vorgang = vorgaenge_modul.vorgang_fuer_angebot(cls.s, angebot)
            angebot.vorgang_id = vorgang.id
            cls.s.commit()
        projekt = kern.projekt_anlegen(cls.s, angebot, projektleiter_id=1)
        gewerk = kern.gewerk_anlegen(cls.s, projekt, angebot, sparte)
        gewerk.phase = phase
        cls.s.commit()
        return gewerk

    @classmethod
    def termin_neu(cls, gewerk: Gewerk, team: Team | None = None, tage: int = 1,
                   besetzung=(), typ: str = "montage", zweck: str = "wp") -> ProjektTermin:
        beginn = (datetime.now() + timedelta(days=tage)).replace(hour=7, minute=30,
                                                                 second=0, microsecond=0)
        t = ProjektTermin(gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id, typ=typ,
                          beginn=beginn, ende=beginn + timedelta(days=1),
                          team_id=team.id if team else None, kunde_bestaetigt=True,
                          zweck=zweck)
        cls.s.add(t)
        cls.s.flush()
        cls.besetzung_setzen(t, besetzung)
        cls.s.commit()
        return t

    @classmethod
    def besetzung_setzen(cls, termin: ProjektTermin, benutzer) -> None:
        cls.s.query(TerminBesetzung).filter_by(termin_id=termin.id).delete()
        for b in benutzer:
            cls.s.add(TerminBesetzung(termin_id=termin.id, benutzer_id=b.id))
        cls.s.commit()

    @classmethod
    def vorgang_von(cls, gewerk: Gewerk) -> Vorgang:
        angebot = cls.s.get(Angebot, gewerk.angebot_id)
        return cls.s.get(Vorgang, angebot.vorgang_id)

    @classmethod
    def verlauf_texte(cls, gewerk: Gewerk) -> list[str]:
        return [e.text for e in cls.s.query(ProjektVerlauf)
                .filter(ProjektVerlauf.gewerk_id == gewerk.id).order_by(ProjektVerlauf.id)]
