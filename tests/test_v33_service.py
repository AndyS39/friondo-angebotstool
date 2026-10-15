# v33 (PLAN_V20 Phase 168 + Montage-Backend-Punkt aus Phase 167, Agent S): Service-Einsätze –
# Terminart service am Vorgang ohne Projekt (Vorgangsakte → „Service-Einsatz planen“),
# Service-Varianten sehen im Backend nur Service-Einsätze ihres Gewerks, Montage Heizung/
# Elektro-Filter, Montage-Benutzer sehen keinen Service, Servicebericht-PDF im Galerie-
# Ordner „Service“, Einsatz gestartet/beendet, Besetzungsvorschlag nach Gewerk (Dialog-
# Kontext + Markup), Verträge für den zentralen Kalender (termine_fuer_personen,
# termin_verschieben), Akten-Badges, Statistik, Migration idempotent.
# Testdaten mit Präfix „V33S“ (Kunde v33s@test.local), Outlook gemockt (kein Netz).
import json
import unittest
import warnings
from datetime import date, datetime, timedelta
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, auth, config, rollen
from app import montage_formulare, outlook_kalender, projektierung_logik
from app import projektierung as kern
from app import vorgaenge as vorgaenge_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Aufgabe, AufgabenpaketInstanz,
                        Benachrichtigung, Benutzer, Erfassung, GalerieDatei, Gewerk, Kunde,
                        MontageFormular, Projekt, ProjektTermin, ProjektVerlauf, Restarbeit,
                        SteckbriefWert, Team, TeamMitglied, TerminBesetzung, Vorgang,
                        VorgangNotizGelesen, VorgangsNotiz, angebot_status_setzen)
from tests.proj_v6_p2_basis import png_daten_url

TEST_EMAIL = "v33s@test.local"
PRAEFIX = "V33S"


def aufraeumen(s):
    """Alles mit Präfix V33S / Test-Mail entfernen (idempotent, inkl. Galerie-Dateien)."""
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
            s.query(MontageFormular).filter_by(projekt_id=p.id).delete()
            s.delete(p)
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            for t in s.query(ProjektTermin).filter_by(vorgang_id=v.id):
                s.query(TerminBesetzung).filter_by(termin_id=t.id).delete()
                for f in s.query(MontageFormular).filter_by(projekt_id=0):
                    if montage_formulare.antworten(f).get("_termin_id") == t.id:
                        s.delete(f)
                s.delete(t)
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
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.commit()


def client_fuer(benutzer_id: int) -> TestClient:
    c = TestClient(app)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        rollen.migration_v33_rollen(cls.s)
        cls.s.commit()
        rollen.cache_leeren()
        cls.admin = client_fuer(1)
        cls.adminb = cls.s.get(Benutzer, 1)
        cls.service_h = cls.benutzer_neu("Service H", "service_heizung")
        cls.service_e = cls.benutzer_neu("Service E", "service_elektro")
        cls.monteur_h = cls.benutzer_neu("Monteur H", "montage_heizung")
        cls.monteur_e = cls.benutzer_neu("Monteur E", "montage_elektro")
        cls.monteur = cls.benutzer_neu("Monteur Basis", "montage")
        cls.team_h = cls.team_neu("Team Heizung", [cls.monteur_h, cls.monteur], gewerk="heizung")
        cls.team_e = cls.team_neu("Team Elektro", [cls.monteur_e], gewerk="elektro")
        cls.team_s = cls.team_neu("Service-Team", [cls.service_h], gewerk="heizung")
        cls.kunde, cls.vorgang = cls.bestandskunde_neu()
        # Outlook: kein Netz – die Routen rufen event_senden best effort (gemockt)
        cls._outlook = mock.patch.object(outlook_kalender, "event_senden", return_value=(True, ""))
        cls._outlook.start()
        cls._freigabe_alt = kern.parameter_holen(cls.s, "freigabe_modus", "admin")
        kern.parameter_setzen(cls.s, "freigabe_modus", "alle")   # Innendienst/Vorgangsakte
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        cls._outlook.stop()
        kern.parameter_setzen(cls.s, "freigabe_modus", cls._freigabe_alt)
        cls.s.commit()
        aufraeumen(cls.s)
        cls.s.close()

    def setUp(self):
        self.s.expire_all()

    # --- Stammdaten --------------------------------------------------------------
    @classmethod
    def benutzer_neu(cls, name: str, rolle: str) -> Benutzer:
        b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                     pin_hash=auth.pin_hash("1234"),
                     email=f"{name.lower().replace(' ', '')}@v33s.test")
        cls.s.add(b)
        cls.s.commit()
        return b

    @classmethod
    def team_neu(cls, name: str, mitglieder=(), gewerk: str = "") -> Team:
        te = Team(name=f"{PRAEFIX} {name}", typ="montage", aktiv=True, farbe="#3f86c6",
                  gewerk=gewerk)
        cls.s.add(te)
        cls.s.flush()
        for b in mitglieder:
            cls.s.add(TeamMitglied(team_id=te.id, benutzer_id=b.id))
        cls.s.commit()
        return te

    @classmethod
    def bestandskunde_neu(cls) -> tuple[Kunde, Vorgang]:
        """Bestandskunde: Kunde + Vorgang OHNE Projekt (abgeschlossene Anlage)."""
        kunde = Kunde(anrede="Frau", vorname="Beate", nachname=f"{PRAEFIX} Bestand",
                      strasse="Servicestr. 9", plz="47139", ort="Duisburg",
                      email=TEST_EMAIL, telefon="0203 9")
        cls.s.add(kunde)
        cls.s.flush()
        vorgang = Vorgang(kunde_id=kunde.id)
        cls.s.add(vorgang)
        cls.s.commit()
        return kunde, vorgang

    @classmethod
    def gewerk_neu(cls, sparte="WP", phase="montagevorbereitung") -> Gewerk:
        kunde = Kunde(anrede="Herr", vorname="Paul", nachname=f"{PRAEFIX} Projekt",
                      strasse="Teststr. 5", plz="47139", ort="Duisburg",
                      email=TEST_EMAIL, telefon="0203 1")
        cls.s.add(kunde)
        cls.s.flush()
        angebot = angebot_aufbau.angebot_anlegen(cls.s, kunde.id, sparte=sparte)
        angebot.positionen.append(AngebotsPosition(
            sort=1, pos_nr="047", bezeichnung="Pos 047", beschreibung="Pos 047",
            menge=1, e_preis_cent=10000))
        angebot_status_setzen(angebot, "Angenommen")
        cls.s.commit()
        if not angebot.vorgang_id:
            vorgang = vorgaenge_modul.vorgang_fuer_angebot(cls.s, angebot)
            angebot.vorgang_id = vorgang.id
            cls.s.commit()
        projekt = kern.projekt_anlegen(cls.s, angebot, projektleiter_id=1)
        gewerk = kern.gewerk_anlegen(cls.s, projekt, angebot, sparte)
        gewerk.phase = phase
        gewerk.phase_auto = False   # Auto-Phase ist nicht Gegenstand dieser Datei
        cls.s.commit()
        return gewerk

    @classmethod
    def termin_neu(cls, gewerk, team=None, tage=1, besetzung=(), typ="montage", zweck="wp"):
        beginn = (datetime.now() + timedelta(days=tage)).replace(hour=7, minute=30,
                                                                 second=0, microsecond=0)
        t = ProjektTermin(gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id, typ=typ,
                          beginn=beginn, ende=beginn + timedelta(days=1),
                          team_id=team.id if team else None, kunde_bestaetigt=True, zweck=zweck)
        cls.s.add(t)
        cls.s.flush()
        cls.besetzung_setzen(t, besetzung)
        return t

    @classmethod
    def besetzung_setzen(cls, termin, benutzer) -> None:
        cls.s.query(TerminBesetzung).filter_by(termin_id=termin.id).delete()
        for b in benutzer:
            cls.s.add(TerminBesetzung(termin_id=termin.id, benutzer_id=b.id))
        cls.s.commit()

    @classmethod
    def service_neu(cls, gewerk_name="heizung", tage=2, besetzung=(), gewerk=None,
                    anlass="wartung", uhrzeit="09:00", dauer_min=90, vorgang=None):
        """Service-Einsatz über kern.termin_speichern (wie der Dialog)."""
        daten = {"art": "service", "service_gewerk": gewerk_name, "anlass": anlass,
                 "beginn": date.today() + timedelta(days=tage), "uhrzeit": uhrzeit,
                 "dauer_min": dauer_min, "besetzung": [b.id for b in besetzung],
                 "besetzung_gesetzt": True, "notiz": "Testeinsatz",
                 "vorgang_id": (vorgang or cls.vorgang).id if gewerk is None else None}
        ok, meldung, _ = kern.termin_speichern(cls.s, gewerk, daten, benutzer=cls.adminb)
        assert ok, meldung
        cls.s.commit()
        return cls.s.get(ProjektTermin, daten["termin_id"])

    def notizen(self, vorgang_id: int) -> list[str]:
        return [n.text for n in self.s.query(VorgangsNotiz)
                .filter(VorgangsNotiz.vorgang_id == vorgang_id).order_by(VorgangsNotiz.id)]

    def sieht(self, benutzer: Benutzer, termin: ProjektTermin) -> tuple[bool, bool]:
        """(in „Meine Einsätze“ gelistet, Einsatzseite erreichbar)."""
        c = client_fuer(benutzer.id)
        liste = c.get("/montage")
        self.assertEqual(liste.status_code, 200)
        seite = c.get(f"/montage/einsatz/{termin.id}", follow_redirects=False)
        return (f"/montage/einsatz/{termin.id}" in liste.text, seite.status_code == 200)


class ServiceAmVorgang(Basis):
    def test_service_einsatz_am_vorgang_ohne_projekt(self):
        heute = date.today() + timedelta(days=5)
        r = self.admin.post(f"/projektierung/vorgang/{self.vorgang.id}/service-termin",
                            data={"service_gewerk": "heizung", "anlass": "stoerung",
                                  "beginn": heute.isoformat(), "uhrzeit": "09:07",
                                  "dauer_stunden": "1", "dauer_minuten": "30",
                                  "besetzung": [str(self.service_h.id)], "besetzung_gesetzt": "1",
                                  "notiz": "Pumpe pfeift"},
                            headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        daten = r.json()
        self.assertTrue(daten["ok"], daten)
        self.assertIn("Service-Einsatz Störung (Heizung)", daten["meldung"])
        t = self.s.get(ProjektTermin, daten["termin_id"])
        self.assertEqual((t.typ, t.projekt_id, t.vorgang_id, t.gewerk_id),
                         ("service", 0, self.vorgang.id, None))
        self.assertEqual((t.service_gewerk, t.anlass, t.service_status), ("heizung", "stoerung", "geplant"))
        self.assertEqual(t.beginn, datetime.combine(heute, datetime.min.time()).replace(hour=9))
        self.assertEqual(t.ende - t.beginn, timedelta(minutes=90))   # 09:07 → 09:00, Dauer 1:30
        self.assertFalse(t.ganztaegig)
        self.assertEqual(kern.besetzung_ids(self.s, t.id), [self.service_h.id])
        self.assertEqual(kern.termin_art(t), "service")
        # Kunde/Adresse über den Vorgang (Bestandskunde ohne Projekt)
        self.assertEqual(kern.termin_kunde(self.s, t).id, self.kunde.id)
        self.assertIn("Servicestr. 9", kern.termin_adresse(self.s, t)["einzeilig"])
        # Chat-Notiz statt Projektverlauf (projekt_id 0)
        self.assertTrue(any("Service-Einsatz Störung (Heizung)" in n for n in self.notizen(self.vorgang.id)))
        self.assertEqual(self.s.query(ProjektVerlauf).filter_by(projekt_id=0).count(), 0)
        # Vorgangsakte: Block Termine mit Badge Service, Anlass, Knopf
        akte = self.admin.get(f"/vorgaenge/{self.vorgang.id}")
        self.assertEqual(akte.status_code, 200)
        self.assertIn("Service-Einsatz planen", akte.text)
        self.assertIn('pj-service">Service</span>', akte.text)
        self.assertIn("Störung", akte.text)
        self.assertIn(f"dlg-termin-edit-{t.id}", akte.text)
        # Bearbeiten über die gemeinsame Route (ohne Gewerk) – Anlass ändern, Dauer 2 h
        r = self.admin.post(f"/projektierung/termin/{t.id}/bearbeiten",
                            data={"art": "service", "service_gewerk": "heizung", "anlass": "wartung",
                                  "beginn": heute.isoformat(), "uhrzeit": "10:00",
                                  "dauer_stunden": "2", "dauer_minuten": "0",
                                  "besetzung": [str(self.service_h.id)], "besetzung_gesetzt": "1",
                                  "zurueck": f"/vorgaenge/{self.vorgang.id}"},
                            headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        t = self.s.get(ProjektTermin, t.id)
        self.assertEqual((t.anlass, t.beginn.hour, (t.ende - t.beginn)), ("wartung", 10, timedelta(hours=2)))
        # Terminübersicht der Projektierung verträgt Termine ohne Projekt (v32-Rückweg-Probe)
        r = self.admin.get(f"/projektierung/termine?start={heute.isoformat()}&typ=service")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Wartung", r.text)
        self.assertIn(f"/vorgaenge/{self.vorgang.id}#termine", r.text)
        # Löschen mit Pflichtgrund → Chat-Notiz
        termin_id = t.id
        self.s.expunge(t)
        r = self.admin.post(f"/projektierung/termin/{termin_id}/loeschen", data={"grund": "Kunde abgesagt"},
                            headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(self.s.query(ProjektTermin).filter_by(id=termin_id).first())
        self.assertTrue(any("gelöscht – Kunde abgesagt" in n for n in self.notizen(self.vorgang.id)))

    def test_pflichtfelder_und_mannschaft(self):
        ok, meldung, _ = kern.termin_speichern(self.s, None, {
            "art": "service", "vorgang_id": self.vorgang.id, "service_gewerk": "heizung",
            "anlass": "wartung", "beginn": date.today() + timedelta(days=3), "uhrzeit": "08:00"},
            benutzer=self.adminb)
        # Nachtrag 15.10.2026 (Entscheidung S-R5): ohne Team/Techniker erlaubt – Besetzung folgt in der Akte
        self.assertTrue(ok, meldung)
        ok, meldung, _ = kern.termin_speichern(self.s, None, {
            "art": "service", "vorgang_id": self.vorgang.id, "service_gewerk": "wasser",
            "anlass": "wartung", "beginn": date.today(), "besetzung": [self.service_h.id],
            "besetzung_gesetzt": True}, benutzer=self.adminb)
        self.assertFalse(ok)
        self.assertIn("Gewerk", meldung)
        ok, meldung, _ = kern.termin_speichern(self.s, None, {
            "art": "montage", "vorgang_id": self.vorgang.id, "beginn": date.today()},
            benutzer=self.adminb)
        self.assertFalse(ok)
        self.assertIn("nur Service-Einsätze", meldung)
        # Team als Mannschaft: Besetzung = Team-Mitglieder
        ok, meldung, _ = kern.termin_speichern(self.s, None, {
            "art": "service", "vorgang_id": self.vorgang.id, "service_gewerk": "heizung",
            "anlass": "nacharbeit", "beginn": date.today() + timedelta(days=4), "uhrzeit": "13:00",
            "team_id": self.team_s.id, "dauer_min": 60}, benutzer=self.adminb)
        self.assertTrue(ok, meldung)
        self.s.rollback()

    def test_service_dauer_minuten(self):
        self.assertEqual(kern.service_dauer_minuten({"dauer_stunden": "1", "dauer_minuten": "30"}), 90)
        self.assertEqual(kern.service_dauer_minuten({"dauer_min": "100"}), 105)
        self.assertEqual(kern.service_dauer_minuten({}), kern.SERVICE_DAUER_STANDARD_MIN)
        self.assertEqual(kern.service_dauer_minuten({"dauer_min": "0"}), kern.SERVICE_DAUER_STANDARD_MIN)
        self.assertEqual(kern.service_dauer_minuten({"dauer_min": "5"}), 15)

    def test_migration_idempotent(self):
        kern.migration_v33_service(self.s)
        self.s.commit()
        self.assertEqual(kern.migration_v33_service(self.s), [])
        self.assertEqual(kern.parameter_holen(self.s, "phase_auto", ""), "an")


class ServiceBackend(Basis):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.heizung = cls.service_neu("heizung", tage=2, besetzung=[cls.service_h])
        cls.elektro = cls.service_neu("elektro", tage=3, besetzung=[cls.service_e, cls.service_h])
        cls.gewerk = cls.gewerk_neu()
        cls.wp = cls.termin_neu(cls.gewerk, cls.team_h, tage=4,
                                besetzung=[cls.monteur_h, cls.monteur_e, cls.monteur, cls.service_h])
        cls.el = cls.termin_neu(cls.gewerk, cls.team_e, tage=5, besetzung=[cls.monteur_e, cls.monteur_h],
                                zweck="elektro")
        cls.sub = cls.termin_neu(cls.gewerk, cls.team_h, tage=6, besetzung=[cls.monteur_h], typ="sub",
                                 zweck="sub")
        cls.service_projekt = cls.service_neu("heizung", tage=7, besetzung=[cls.service_h, cls.monteur_h],
                                              gewerk=cls.gewerk)

    def test_service_benutzer_sieht_nur_service_seines_gewerks(self):
        # Service Heizung: Heizungs-Einsätze ja (am Vorgang und am Projekt), Elektro nein,
        # Montagetermin trotz Besetzung nein
        self.assertEqual(self.sieht(self.service_h, self.heizung), (True, True))
        self.assertEqual(self.sieht(self.service_h, self.service_projekt), (True, True))
        self.assertEqual(self.sieht(self.service_h, self.elektro), (False, False))
        self.assertEqual(self.sieht(self.service_h, self.wp), (False, False))
        # Service Elektro: nur der Elektro-Einsatz
        self.assertEqual(self.sieht(self.service_e, self.elektro), (True, True))
        self.assertEqual(self.sieht(self.service_e, self.heizung), (False, False))
        liste = client_fuer(self.service_h.id).get("/montage").text
        self.assertIn("Meine Service-Einsätze", liste)
        self.assertIn("Wartung", liste)
        self.assertIn(self.kunde.anzeige_name, liste)
        # Wochenkalender mit Service-Einträgen
        start = self.heizung.beginn.date().isoformat()
        r = client_fuer(self.service_h.id).get(f"/montage?ansicht=kalender&start={start}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f"/montage/einsatz/{self.heizung.id}", r.text)

    def test_montage_heizung_elektro_filter(self):
        # Montage Heizung: Montage (WP) + Sub, nicht Elektro
        self.assertEqual(self.sieht(self.monteur_h, self.wp), (True, True))
        self.assertEqual(self.sieht(self.monteur_h, self.sub), (True, True))
        self.assertEqual(self.sieht(self.monteur_h, self.el), (False, False))
        # Montage Elektro: nur Elektro-Montage
        self.assertEqual(self.sieht(self.monteur_e, self.el), (True, True))
        self.assertEqual(self.sieht(self.monteur_e, self.wp), (False, False))
        # Basisrolle montage ohne Gewerk: alles wie bisher (Besetzung entscheidet)
        self.assertEqual(self.sieht(self.monteur, self.wp), (True, True))
        self.assertEqual(self.sieht(self.monteur, self.el), (False, False))   # nicht in der Besetzung
        # Teamansicht Montage Heizung: Elektro-Termin des eigenen Teams? Team Heizung hat keinen
        r = client_fuer(self.monteur_h.id).get(f"/montage?team_id={self.team_h.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f"/montage/einsatz/{self.wp.id}", r.text)
        self.assertNotIn(f"/montage/einsatz/{self.el.id}", r.text)

    def test_montage_benutzer_sieht_keinen_service(self):
        # Montage Heizung steht in der Besetzung eines Service-Einsatzes → trotzdem unsichtbar
        self.assertEqual(self.sieht(self.monteur_h, self.service_projekt), (False, False))
        self.assertEqual(self.sieht(self.monteur, self.heizung), (False, False))
        self.assertFalse(kern.termin_bearbeiten_erlaubt(self.s, self.monteur_h))
        # Leitung (Admin) sieht alles, auch den Service am Vorgang
        r = self.admin.get(f"/montage/einsatz/{self.heizung.id}", follow_redirects=False)
        self.assertEqual(r.status_code, 200)

    def test_service_einsatzseite_und_status(self):
        c = client_fuer(self.service_h.id)
        r = c.get(f"/montage/einsatz/{self.heizung.id}")
        self.assertEqual(r.status_code, 200)
        for text in ("Service-Einsatz", "Wartung", "Heizung", self.kunde.anzeige_name,
                     "Servicestr. 9", "0203 9", "Einsatz gestartet", "Servicebericht"):
            self.assertIn(text, r.text)
        self.assertNotIn("Montage starten", r.text)
        self.assertNotIn("Preise", r.text.split("Keine Preise")[0][-200:] if "Keine Preise" in r.text else "")
        # Einsatz gestartet → Status, Zeit im 15-Minuten-Takt, Chat-Notiz (Herkunft montage)
        r = c.post(f"/montage/einsatz/{self.heizung.id}/service-status",
                   data={"aktion": "gestartet", "uhrzeit": "08:07"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        t = self.s.get(ProjektTermin, self.heizung.id)
        self.assertEqual(t.service_status, "gestartet")
        self.assertEqual((t.gestartet_am.hour, t.gestartet_am.minute), (8, 0))
        notizen = self.s.query(VorgangsNotiz).filter_by(vorgang_id=self.vorgang.id).all()
        self.assertTrue(any("Einsatz gestartet" in n.text and n.herkunft == "montage" for n in notizen))
        r = c.get(f"/montage/einsatz/{self.heizung.id}")
        self.assertIn("Einsatz beendet", r.text)
        self.assertNotIn('value="gestartet"', r.text)
        r = c.post(f"/montage/einsatz/{self.heizung.id}/service-status",
                   data={"aktion": "beendet", "uhrzeit": "11:20"}, follow_redirects=False)
        self.s.expire_all()
        t = self.s.get(ProjektTermin, self.heizung.id)
        self.assertEqual((t.service_status, t.beendet_am.minute), ("beendet", 15))
        ok, meldung = kern.service_status_setzen(self.s, t, "beendet", self.adminb)
        self.assertFalse(ok)
        # Verlauf am Projekt bei Service am Gewerk
        kern.service_status_setzen(self.s, self.service_projekt, "gestartet", self.adminb)
        self.s.commit()
        texte = [v.text for v in self.s.query(ProjektVerlauf).filter_by(projekt_id=self.gewerk.projekt_id)]
        self.assertTrue(any("Einsatz gestartet" in x for x in texte), texte)

    def test_servicebericht_pdf_in_galerie(self):
        termin = self.service_neu("elektro", tage=8, besetzung=[self.service_e])
        c = client_fuer(self.service_e.id)
        basis = f"/montage/einsatz/{termin.id}/formular/servicebericht"
        r = c.get(basis)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Servicebericht", r.text)
        import re
        self.assertRegex(r.text, r'value="Wartung"\s+checked')   # Anlass aus dem Termin vorbelegt
        self.assertIn('name="sb_zeit_von" step="900"', r.text)   # Typ zeit
        r = c.post(basis, data={"seite": "0", "aktion": "weiter", "sb_anlass": "Wartung",
                                "sb_zeit_von": "09:07", "sb_zeit_bis": "10:40"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        r = c.post(basis, data={"seite": "1", "aktion": "weiter", "sb_arbeiten": "Filter getauscht",
                                "sb_material": "1 Filter", "sb_ergebnis": "behoben"},
                   follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        # Abschluss ohne Unterschriften → Pflichtfelder offen
        r = c.post(basis, data={"seite": "2", "aktion": "abschliessen"}, follow_redirects=False)
        self.assertIn("Pflichtfelder", r.headers["location"])
        r = c.post(basis, data={"seite": "2", "aktion": "abschliessen",
                                "sb_unterschrift_kunde": png_daten_url(),
                                "sb_unterschrift_techniker": png_daten_url()}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Ordner+Service", r.headers["location"])
        self.s.expire_all()
        eintrag = montage_formulare.formular_holen_termin(self.s, termin, "servicebericht")
        self.assertEqual(eintrag.status, "abgeschlossen")
        self.assertEqual((eintrag.gewerk_id, eintrag.projekt_id), (0, 0))
        antworten = montage_formulare.antworten(eintrag)
        self.assertEqual(antworten["_termin_id"], termin.id)
        self.assertEqual(antworten["sb_zeit_von"], "09:00")          # 15-Minuten-Takt
        self.assertEqual(antworten["sb_zeit_bis"], "10:45")
        datei = self.s.get(GalerieDatei, eintrag.pdf_galerie_id)
        self.assertIsNotNone(datei)
        self.assertEqual((datei.vorgang_id, datei.ordner), (self.vorgang.id, "Service"))
        self.assertTrue(datei.dateiname.startswith("Servicebericht_V"), datei.dateiname)
        self.assertTrue((config.DATA_ORDNER / datei.pfad).exists())
        self.assertIn("Service", projektierung_logik.einlesen().formulare and
                      __import__("app.galerie", fromlist=["x"]).ordner_liste(self.s, "WP"))
        t = self.s.get(ProjektTermin, termin.id)
        self.assertEqual(t.service_status, "beendet")
        self.assertTrue(any("Servicebericht abgeschlossen" in n for n in self.notizen(self.vorgang.id)))
        r = c.get(f"/montage/einsatz/{termin.id}")
        self.assertIn("Servicebericht ✓", r.text)
        self.assertIn(f"/vorgaenge/galerie/datei/{datei.id}", r.text)
        # PDF-Inhalt: Kopf mit Kunde, Anlass, Techniker
        import io
        import pypdf
        text = "\n".join((s.extract_text() or "") for s in pypdf.PdfReader(
            io.BytesIO((config.DATA_ORDNER / datei.pfad).read_bytes())).pages)
        for erwartet in ("Servicebericht", "Wartung", "Filter getauscht", "Techniker"):
            self.assertIn(erwartet, text)
        # Montagebericht am Service-Einsatz ohne Gewerk: nicht verfügbar
        r = c.get(f"/montage/einsatz/{termin.id}/formular/montagebericht", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        # migration_v28_entwuerfe lässt den Servicebericht-Entwurf (Meta-Schlüssel) in Ruhe
        termin2 = self.service_neu("elektro", tage=9, besetzung=[self.service_e])
        entwurf = montage_formulare.formular_holen(self.s, None, "servicebericht", self.adminb,
                                                   termin=termin2)
        entwurf.antworten_json = json.dumps({"_termin_id": termin2.id, "sb_arbeiten": "x"})
        self.s.commit()
        montage_formulare.migration_v28_entwuerfe(self.s)
        self.s.commit()
        self.s.refresh(entwurf)
        self.assertEqual(montage_formulare.antworten(entwurf)["sb_arbeiten"], "x")


class DialogUndAkten(Basis):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gewerk = cls.gewerk_neu()
        cls.service = cls.service_neu("heizung", tage=3, besetzung=[cls.service_h], gewerk=cls.gewerk,
                                      anlass="nacharbeit")

    def test_besetzungsvorschlag_nach_gewerk(self):
        td = kern.termin_dialog_kontext(self.s)
        self.assertEqual([k for k, _ in td["arten"]][-1], "service")
        info = td["monteur_info"]
        self.assertEqual(info[self.service_h.id], {"gewerk": "heizung", "service": True})
        self.assertEqual(info[self.monteur_e.id], {"gewerk": "elektro", "service": False})
        self.assertEqual(info[self.monteur.id], {"gewerk": "", "service": False})
        self.assertEqual(td["service_gewerke"][0], ("heizung", "Heizung"))
        akte = self.admin.get(f"/projektierung/projekt/{self.gewerk.projekt_id}")
        self.assertEqual(akte.status_code, 200)
        self.assertIn(f'<option value="{self.service_h.id}" data-gewerk="heizung"\n                        data-service="1">', akte.text)
        self.assertIn(f'<option value="{self.monteur_e.id}" data-gewerk="elektro"', akte.text)
        self.assertIn(f'data-typ="montage" data-gewerk="elektro"', akte.text)   # Team Elektro
        self.assertIn('name="service_gewerk"', akte.text)
        self.assertIn('name="anlass"', akte.text)
        self.assertIn('name="dauer_stunden"', akte.text)
        js = (config.BASIS_ORDNER / "app" / "static" / "projektierung.js").read_text(encoding="utf-8") \
            if hasattr(config, "BASIS_ORDNER") else \
            open("app/static/projektierung.js", encoding="utf-8").read()
        self.assertIn("optionenNachGewerk", js)
        self.assertIn("(anderes Gewerk)", js)
        self.assertIn("pj-opt-fremd", js)

    def test_projektakte_badge_und_board_unveraendert(self):
        akte = self.admin.get(f"/projektierung/projekt/{self.gewerk.projekt_id}")
        self.assertIn('pj-service">Service</span>', akte.text)
        self.assertIn("Nacharbeit", akte.text)
        self.assertIn("automatisch weiterschalten", akte.text)
        self.assertIn("Outlook", akte.text)
        # Service hat keine Phase: Gewerk unverändert, Zuweisung unverändert, keine Aufgabe erledigt
        g = self.s.get(Gewerk, self.gewerk.id)
        self.assertEqual(g.phase, "montagevorbereitung")
        self.assertIsNone(g.wp_team_id)
        self.assertEqual(self.s.query(Aufgabe).filter_by(gewerk_id=g.id, status="erledigt").count(), 0)
        board = self.admin.get("/projektierung")
        self.assertEqual(board.status_code, 200)
        # Statistik: Service-Einsätze je Monat
        r = self.admin.get("/projektierung/statistik")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Service-Einsätze", r.text)
        monat = (self.service.beginn.date()).strftime("%m/%Y")
        self.assertIn(monat, r.text)
        zeilen = kern.service_statistik(self.s, 12)
        self.assertTrue(any(z["gesamt"] >= 1 and z["anlaesse"]["nacharbeit"] >= 1 for z in zeilen))

    def test_termine_fuer_personen(self):
        von = self.service.beginn - timedelta(days=1)
        bis = self.service.beginn + timedelta(days=1)
        liste = kern.termine_fuer_personen(self.s, [self.service_h.id], von, bis)
        eintrag = next(e for e in liste if e["id"] == self.service.id)
        self.assertEqual(eintrag["art"], "service")
        self.assertEqual(eintrag["art_name"], "Service-Einsatz")
        self.assertEqual(eintrag["status"], "geplant")
        self.assertEqual(eintrag["besetzung_ids"], [self.service_h.id])
        self.assertEqual(eintrag["personen_ids"], [self.service_h.id])
        self.assertEqual(eintrag["projekt_id"], self.gewerk.projekt_id)
        self.assertEqual(eintrag["gewerk_id"], self.gewerk.id)
        self.assertEqual(eintrag["anlass"], "nacharbeit")
        self.assertIn("Teststr. 5", eintrag["ort"])
        self.assertIn(f"/projektierung/projekt/{self.gewerk.projekt_id}", eintrag["link"])
        self.assertEqual(eintrag["einsatz_link"], f"/montage/einsatz/{self.service.id}")
        self.assertEqual(eintrag["kunde"], self.s.get(Kunde, self.s.get(Projekt, self.gewerk.projekt_id).kunde_id).anzeige_name)
        # Person über person_id (Feinplanung) zählt ebenfalls; andere Person sieht nichts
        fp = ProjektTermin(gewerk_id=self.gewerk.id, projekt_id=self.gewerk.projekt_id, typ="feinplanung",
                           beginn=self.service.beginn, person_id=self.monteur.id, ganztaegig=False)
        self.s.add(fp)
        self.s.commit()
        ids = {e["id"] for e in kern.termine_fuer_personen(self.s, [self.monteur.id], von, bis)}
        self.assertIn(fp.id, ids)
        self.assertNotIn(self.service.id, ids)
        self.assertEqual(kern.termine_fuer_personen(self.s, [], von, bis), [])
        # Zeitraum als Datum (date) und als Text
        self.assertTrue(kern.termine_fuer_personen(self.s, [self.service_h.id], von.date(), bis.date()))
        self.assertTrue(kern.termine_fuer_personen(self.s, [self.service_h.id], von.date().isoformat(),
                                                   bis.date().isoformat()))

    def test_termin_verschieben_vertrag(self):
        t = self.service_neu("heizung", tage=12, besetzung=[self.service_h], gewerk=self.gewerk)
        neu = t.beginn + timedelta(days=1, minutes=7)
        with mock.patch.object(outlook_kalender, "event_senden", return_value=(True, "")) as ev:
            ok, meldung, konflikte = kern.termin_verschieben(self.s, t, neu, None, self.adminb)
            self.assertTrue(ok, meldung)
            self.assertTrue(ev.called)
        self.assertEqual(t.beginn.minute, 0)                       # 15-Minuten-Takt
        self.assertEqual(t.ende - t.beginn, timedelta(minutes=90))  # Dauer bleibt
        self.assertEqual(konflikte, [])
        texte = [v.text for v in self.s.query(ProjektVerlauf).filter_by(projekt_id=self.gewerk.projekt_id)]
        self.assertTrue(any("im Kalender verschoben" in x for x in texte), texte)
        # Konfliktwarnung: zweiter Einsatz derselben Person am selben Tag
        t2 = self.service_neu("heizung", tage=20, besetzung=[self.service_h], gewerk=self.gewerk)
        ok, meldung, konflikte = kern.termin_verschieben(self.s, t2, t.beginn.replace(hour=14),
                                                         t.beginn.replace(hour=15), self.adminb)
        self.assertTrue(ok)
        self.assertTrue(konflikte and "ist am" in konflikte[0], konflikte)
        # Rechte wie im Dialog: Montage/Service dürfen nicht
        ok, meldung, _ = kern.termin_verschieben(self.s, t, neu, None, self.service_h)
        self.assertFalse(ok)
        self.assertIn("Keine Berechtigung", meldung)
        # alte Signatur (Kalender-Drag v15) läuft weiter über den Dispatcher
        montage = self.termin_neu(self.gewerk, self.team_h, tage=30, besetzung=[self.monteur_h])
        text = kern.termin_verschieben(self.s, montage, date.today() + timedelta(days=31),
                                       neues_team_id=self.team_h.id)
        self.assertIsInstance(text, str)
        self.assertEqual(montage.beginn.date(), date.today() + timedelta(days=31))
        self.s.commit()

    def test_outlook_status_vertrag(self):
        os = kern.outlook_status_fuer(self.s, self.service)
        self.assertIn(os["stand"], ("leer", "ausstehend", "ok", "fehler", "geloescht",
                                    "in_outlook_geloescht"))
        t = ProjektTermin(typ="service", outlook_fehler="kaputt", projekt_id=0)
        with mock.patch("app.outlook_sync.status_fuer", side_effect=RuntimeError("weg"), create=True):
            self.assertEqual(kern.outlook_status_fuer(self.s, t)["stand"], "fehler")


class KalenderEinbauten(Basis):
    """Einbauten aus K_ergebnis.md (4.2/4.3/4.5): Termin-Dialog aus dem zentralen Kalender
    vorbelegen (Query-Parameter), Kalender-Knopf im Montage-Backend."""

    def test_js_wertet_termin_neu_aus(self):
        js = open("app/static/projektierung.js", encoding="utf-8").read()
        self.assertIn("p.get('termin_neu')", js)
        self.assertIn("modus === 'service'", js)
        self.assertIn("dlg-service-vorgang", js)
        self.assertIn("besetzungSetzen(form, [person])", js)
        self.assertIn("history.replaceState(null, '', location.pathname + location.hash)", js)
        self.assertIn("[data-service-gewerk]", js)

    def test_vorgangsakte_mit_termin_neu_service(self):
        r = self.admin.get(f"/vorgaenge/{self.vorgang.id}?termin_neu=service&beginn=2026-11-02"
                           f"&uhrzeit=09:00&person={self.service_h.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn('id="dlg-service-vorgang"', r.text)
        self.assertIn(f'<option value="{self.service_h.id}" data-gewerk="heizung"', r.text)
        self.assertIn('data-service-gewerk', r.text)
        gewerk = self.gewerk_neu()
        r = self.admin.get(f"/projektierung/projekt/{gewerk.projekt_id}?termin_neu=1&beginn=2026-11-02"
                           f"&uhrzeit=09:00&person={self.monteur_h.id}&art=montage")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'id="dlg-termin-{gewerk.id}"', r.text)

    def test_kalender_knopf_im_montage_backend(self):
        for b in (self.monteur, self.service_h):
            r = client_fuer(b.id).get("/montage")
            self.assertEqual(r.status_code, 200)
            self.assertIn('href="/kalender"', r.text)
            self.assertIn("Mitarbeiter-Kalender", r.text)


if __name__ == "__main__":
    unittest.main()
