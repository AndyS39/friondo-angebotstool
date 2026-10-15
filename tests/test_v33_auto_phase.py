# v33 (PLAN_V20 Phase 171, Agent S): automatischer Phasenwechsel – letzte Pflichtaufgabe
# erledigt → nächste Phase mit Verlauf/Glocke; optionale Aufgaben zählen nicht; Modus
# sperren (und warnen) mit offenem Wächter-Punkt → kein Wechsel; Parameter phase_auto = aus
# bzw. Gewerk-Häkchen aus → kein Wechsel; manueller Rückschritt pausiert die Automatik in
# dieser Phase; Abnahme → Freigabe nur mit allen Abnahme-Pflichtaufgaben; Freigabe →
# abgeschlossen nie; Montagevorbereitung/Montage nicht automatisch (Ereignis-Phasen);
# Hooks (Checkbox-Route, entfällt-Route, Formular-Abschluss, Termin). Präfix „V33A“.
import unittest
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, auth, montage_formulare, projektierung_logik
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

TEST_EMAIL = "v33a@test.local"
PRAEFIX = "V33A"
RANG = {"auftragseingang": 0, "feinplanung_vot": 1, "planung": 2, "montagevorbereitung": 3,
        "abnahme": 5, "freigabe": 6}


def aufraeumen(s):
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
            s.query(GalerieDatei).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangNotizGelesen).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.delete(k)
    for te in s.query(Team).filter(Team.name.like(f"{PRAEFIX}%")):
        s.query(TeamMitglied).filter_by(team_id=te.id).delete()
        s.delete(te)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(TeamMitglied).filter_by(benutzer_id=b.id).delete()
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
        cls.admin = client_fuer(1)
        cls.adminb = cls.s.get(Benutzer, 1)
        cls.alt = {name: kern.parameter_holen(cls.s, name, "") for name in ("phase_auto", "waechter_modus")}
        kern.parameter_setzen(cls.s, "phase_auto", "an")
        kern.parameter_setzen(cls.s, "waechter_modus", "warnen")
        cls.monteur = Benutzer(name=f"{PRAEFIX} Monteur", rolle="montage", aktiv=True,
                               pin_hash=auth.pin_hash("1234"))
        cls.s.add(cls.monteur)
        cls.s.flush()
        cls.team = Team(name=f"{PRAEFIX} Team", typ="montage", aktiv=True, gewerk="heizung")
        cls.s.add(cls.team)
        cls.s.flush()
        cls.s.add(TeamMitglied(team_id=cls.team.id, benutzer_id=cls.monteur.id))
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        for name, wert in cls.alt.items():
            kern.parameter_setzen(cls.s, name, wert or ("an" if name == "phase_auto" else "warnen"))
        cls.s.commit()
        aufraeumen(cls.s)
        cls.s.close()

    def setUp(self):
        kern.parameter_setzen(self.s, "phase_auto", "an")
        kern.parameter_setzen(self.s, "waechter_modus", "warnen")
        self.s.commit()
        self.s.expire_all()

    # --- Helfer -------------------------------------------------------------------
    def gewerk_neu(self, phase="auftragseingang") -> Gewerk:
        kunde = Kunde(anrede="Herr", vorname="Auto", nachname=f"{PRAEFIX} Phase",
                      strasse="Teststr. 5", plz="47139", ort="Duisburg",
                      email=TEST_EMAIL, telefon="0203 1")
        self.s.add(kunde)
        self.s.flush()
        angebot = angebot_aufbau.angebot_anlegen(self.s, kunde.id, sparte="WP")
        angebot.positionen.append(AngebotsPosition(
            sort=1, pos_nr="047", bezeichnung="Pos 047", beschreibung="Pos 047",
            menge=1, e_preis_cent=10000))
        angebot_status_setzen(angebot, "Angenommen")
        self.s.commit()
        if not angebot.vorgang_id:
            angebot.vorgang_id = vorgaenge_modul.vorgang_fuer_angebot(self.s, angebot).id
            self.s.commit()
        projekt = kern.projekt_anlegen(self.s, angebot, projektleiter_id=1)
        gewerk = kern.gewerk_anlegen(self.s, projekt, angebot, "WP")
        gewerk.phase = phase
        self.s.commit()
        self.assertTrue(self.pflicht(gewerk, 0), "Paket Auftragseingang fehlt – Logik nicht geladen?")
        return gewerk

    def pflicht(self, gewerk: Gewerk, rang: int) -> list[Aufgabe]:
        instanzen = {i.id: i for i in self.s.query(AufgabenpaketInstanz).filter_by(gewerk_id=gewerk.id)}
        return [a for a in self.s.query(Aufgabe)
                .filter(Aufgabe.gewerk_id == gewerk.id, Aufgabe.pflicht.is_(True))
                .order_by(Aufgabe.id)
                if a.paket_instanz_id in instanzen
                and kern.paket_rang(instanzen[a.paket_instanz_id].paket_name) == rang]

    def erledigen(self, aufgaben) -> None:
        for a in aufgaben:
            a.status = "erledigt"
            a.erledigt_am = datetime.now()
        self.s.commit()

    def vorbereiten_bis(self, gewerk: Gewerk, phase: str) -> None:
        """Alle Bedingungen der Phasen VOR `phase` erfüllen (Wächter-Blöcke)."""
        rang = RANG[phase]
        for r in range(0, rang):
            self.erledigen(self.pflicht(gewerk, r))
        if rang >= 2:
            gewerk.feinplanung_erfasst = True
        if rang >= 4:
            for a in self.s.query(Aufgabe).filter(Aufgabe.gewerk_id == gewerk.id,
                                                  Aufgabe.titel == "Projekt zur Montage freigegeben"):
                a.status = "erledigt"
            if not self.s.query(ProjektTermin).filter_by(gewerk_id=gewerk.id, typ="montage").first():
                beginn = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)
                self.s.add(ProjektTermin(gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id,
                                         typ="montage", zweck="wp", beginn=beginn,
                                         ende=beginn + timedelta(days=2), team_id=self.team.id,
                                         kunde_bestaetigt=True))
        if rang >= 5:
            gewerk.montage_fertig_am = datetime.now()
        gewerk.phase = phase
        self.s.commit()

    def verlauf(self, gewerk: Gewerk) -> list[str]:
        return [v.text for v in self.s.query(ProjektVerlauf)
                .filter(ProjektVerlauf.gewerk_id == gewerk.id).order_by(ProjektVerlauf.id)]

    def post_json(self, pfad, daten=None):
        return self.admin.post(pfad, data=daten or {}, headers={"Accept": "application/json"})


class AutoPhase(Basis):
    def test_letzte_pflichtaufgabe_erledigt_naechste_phase_mit_verlauf(self):
        g = self.gewerk_neu()
        offen = self.pflicht(g, 0)
        self.assertGreaterEqual(len(offen), 2)
        self.erledigen(offen[:-1])
        self.s.refresh(g)
        self.assertEqual(g.phase, "auftragseingang")
        # letzte Pflichtaufgabe über die Checkbox-Route der Akte
        r = self.post_json(f"/projektierung/aufgabe/{offen[-1].id}/erledigt-umschalten")
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertEqual(g.phase, "feinplanung_vot")
        texte = self.verlauf(g)
        self.assertTrue(any("Auftragseingang → Feinplanung VOT – automatisch – alle Pflichtaufgaben erledigt" in t
                            for t in texte), texte)
        glocken = [b.text for b in self.s.query(Benachrichtigung).filter_by(benutzer_id=1)
                   .order_by(Benachrichtigung.id.desc()).limit(5)]
        self.assertTrue(any("Feinplanung VOT" in t and "automatisch" in t for t in glocken), glocken)
        # Nur eine Phase je Auslöser: Feinplanung-Pflichtaufgaben sind offen → bleibt
        gewechselt, meldung = kern.auto_weiterschalten(self.s, g, self.adminb)
        self.assertFalse(gewechselt)
        self.assertIn("offen", meldung)

    def test_optionale_aufgaben_zaehlen_nicht(self):
        g = self.gewerk_neu()
        self.vorbereiten_bis(g, "planung")
        instanz = (self.s.query(AufgabenpaketInstanz)
                   .filter(AufgabenpaketInstanz.gewerk_id == g.id,
                           AufgabenpaketInstanz.paket_key == "planung_wp").first())
        self.assertIsNotNone(instanz)
        optional = Aufgabe(gewerk_id=g.id, projekt_id=g.projekt_id, paket_instanz_id=instanz.id,
                           titel=f"{PRAEFIX} optional", pflicht=False, reihenfolge=99)
        self.s.add(optional)
        self.s.commit()
        pflicht = self.pflicht(g, 2)
        self.erledigen(pflicht[:-1])
        # Steckbrief-Nachzug als Auslöser (Hook in steckbrief_schritte_nachziehen)
        kern.steckbrief_schritte_nachziehen(self.s, g, benutzer=self.adminb)
        self.s.commit()
        self.assertEqual(self.s.get(Gewerk, g.id).phase, "planung")
        self.erledigen(pflicht[-1:])
        kern.steckbrief_schritte_nachziehen(self.s, g, benutzer=self.adminb)
        self.s.commit()
        self.s.expire_all()
        self.assertEqual(self.s.get(Gewerk, g.id).phase, "montagevorbereitung")
        self.assertEqual(self.s.get(Aufgabe, optional.id).status, "offen")

    def test_entfaellt_zaehlt_wie_erledigt(self):
        g = self.gewerk_neu()
        offen = self.pflicht(g, 0)
        self.erledigen(offen[:-1])
        r = self.post_json(f"/projektierung/aufgabe/{offen[-1].id}/entfaellt", {"grund": "nicht nötig"})
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        self.assertEqual(self.s.get(Gewerk, g.id).phase, "feinplanung_vot")

    def test_sperren_und_warnen_mit_offenem_punkt_kein_wechsel(self):
        for modus in ("sperren", "warnen"):
            kern.parameter_setzen(self.s, "waechter_modus", modus)
            self.s.commit()
            g = self.gewerk_neu()
            self.vorbereiten_bis(g, "feinplanung_vot")
            g.feinplanung_erfasst = False          # offener Wächter-Punkt (Häkchen)
            self.s.commit()
            self.erledigen(self.pflicht(g, 1))
            gewechselt, meldung = kern.auto_weiterschalten(self.s, g, self.adminb)
            self.assertFalse(gewechselt, modus)
            self.assertIn("Wächter", meldung)
            self.assertIn("Feinplanung nicht erfasst", meldung)
            self.assertEqual(self.s.get(Gewerk, g.id).phase, "feinplanung_vot")
            g.feinplanung_erfasst = True
            self.s.commit()
            gewechselt, meldung = kern.auto_weiterschalten(self.s, g, self.adminb)
            self.assertTrue(gewechselt, meldung)
            self.assertEqual(self.s.get(Gewerk, g.id).phase, "planung")

    def test_parameter_aus_und_gewerk_haekchen(self):
        g = self.gewerk_neu()
        self.erledigen(self.pflicht(g, 0))
        kern.parameter_setzen(self.s, "phase_auto", "aus")
        self.s.commit()
        gewechselt, meldung = kern.auto_weiterschalten(self.s, g, self.adminb)
        self.assertFalse(gewechselt)
        self.assertIn("Parametrierung", meldung)
        kern.parameter_setzen(self.s, "phase_auto", "an")
        self.s.commit()
        # Häkchen am Gewerk über die Route aus → kein Wechsel; an → Wechsel beim nächsten Auslöser
        r = self.post_json(f"/projektierung/gewerk/{g.id}/phase-auto", {"phase_auto": "0"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(r.json()["phase_auto"])
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertFalse(g.phase_auto)
        self.assertFalse(kern.auto_weiterschalten(self.s, g, self.adminb)[0])
        self.assertEqual(g.phase, "auftragseingang")
        self.assertTrue(any("ausgeschaltet" in t for t in self.verlauf(g)))
        r = self.post_json(f"/projektierung/gewerk/{g.id}/phase-auto", {"phase_auto": "1"})
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertTrue(g.phase_auto)
        self.assertTrue(kern.auto_weiterschalten(self.s, g, self.adminb)[0])
        self.s.commit()
        self.assertEqual(g.phase, "feinplanung_vot")
        akte = self.admin.get(f"/projektierung/projekt/{g.projekt_id}")
        self.assertIn("automatisch weiterschalten", akte.text)

    def test_rueckschritt_pausiert_kein_vorspringen(self):
        g = self.gewerk_neu()
        self.erledigen(self.pflicht(g, 0))
        self.assertTrue(kern.auto_weiterschalten(self.s, g, self.adminb)[0])
        self.s.commit()
        self.assertEqual(g.phase, "feinplanung_vot")
        # manueller Rückschritt mit Begründung → Pause in auftragseingang
        ok, meldung = kern.phase_wechseln(self.s, g, "auftragseingang", "Auftrag unklar", benutzer=self.adminb)
        self.assertTrue(ok, meldung)
        self.s.commit()
        self.assertEqual(g.phase_auto_pause, "auftragseingang")
        gewechselt, meldung = kern.auto_weiterschalten(self.s, g, self.adminb)
        self.assertFalse(gewechselt)
        self.assertIn("Pausiert", meldung)
        self.assertEqual(g.phase, "auftragseingang")
        # Hinweis im Dialog „Phase ändern“ (JSON des Wächters) bei Rückwärts-Wechsel
        g.phase = "feinplanung_vot"
        self.s.commit()
        r = self.admin.get(f"/projektierung/gewerk/{g.id}/waechter?ziel=auftragseingang")
        self.assertEqual(r.status_code, 200)
        daten = r.json()
        self.assertIn("pausiert", daten["hinweis"])
        self.assertEqual(daten["phase_auto_pause"], "auftragseingang")
        g.phase = "auftragseingang"
        self.s.commit()
        # Häkchen neu setzen hebt die Pause auf; manuell vorwärts verlassen ebenfalls
        kern.phase_auto_setzen(self.s, g, True, benutzer=self.adminb)
        self.s.commit()
        self.assertEqual(g.phase_auto_pause, "")
        self.assertTrue(kern.auto_weiterschalten(self.s, g, self.adminb)[0])
        self.s.commit()
        ok, _ = kern.phase_wechseln(self.s, g, "auftragseingang", "nochmal", benutzer=self.adminb)
        self.s.commit()
        self.assertEqual(g.phase_auto_pause, "auftragseingang")
        ok, _ = kern.phase_wechseln(self.s, g, "feinplanung_vot", "", benutzer=self.adminb)
        self.assertTrue(ok)
        self.s.commit()
        self.assertEqual(g.phase_auto_pause, "")

    def test_abnahme_freigabe_nur_mit_allen_pflichtaufgaben_freigabe_nie_abgeschlossen(self):
        g = self.gewerk_neu()
        self.vorbereiten_bis(g, "abnahme")
        abnahme = self.pflicht(g, 5)
        self.assertGreaterEqual(len(abnahme), 2)
        self.erledigen(abnahme[:-1])
        gewechselt, meldung = kern.auto_weiterschalten(self.s, g, self.adminb)
        self.assertFalse(gewechselt)
        self.assertEqual(g.phase, "abnahme")
        self.erledigen(abnahme[-1:])
        gewechselt, meldung = kern.auto_weiterschalten(self.s, g, self.adminb)
        self.assertTrue(gewechselt, meldung)
        self.s.commit()
        self.assertEqual(g.phase, "freigabe")
        # Freigabe → abgeschlossen nie automatisch (nur „Rechnung freigeben“)
        self.erledigen(self.pflicht(g, 6))
        gewechselt, meldung = kern.auto_weiterschalten(self.s, g, self.adminb)
        self.assertFalse(gewechselt)
        self.assertIn("nicht automatisch verlassen", meldung)
        self.assertEqual(g.phase, "freigabe")
        self.assertIsNone(g.freigabe_am)

    def test_montagevorbereitung_und_montage_nicht_automatisch(self):
        g = self.gewerk_neu()
        self.vorbereiten_bis(g, "montagevorbereitung")
        self.erledigen(self.pflicht(g, 3))
        gewechselt, meldung = kern.auto_weiterschalten(self.s, g, self.adminb)
        self.assertFalse(gewechselt)
        self.assertEqual(g.phase, "montagevorbereitung")
        g.phase = "montage"
        g.montage_fertig_am = datetime.now()
        self.s.commit()
        self.assertFalse(kern.auto_weiterschalten(self.s, g, self.adminb)[0])
        self.assertEqual(g.phase, "montage")

    def test_formular_und_termin_als_ausloeser(self):
        # Abnahmeprotokoll erledigt die Pflichtaufgabe „Abnahmeprotokoll mit Kundenunterschrift“
        g = self.gewerk_neu()
        self.vorbereiten_bis(g, "abnahme")
        abnahme = self.pflicht(g, 5)
        self.erledigen([a for a in abnahme if a.titel != "Abnahmeprotokoll mit Kundenunterschrift"])
        logik = projektierung_logik.hole_logik(self.s)
        eintrag = montage_formulare.formular_holen(self.s, g, "abnahme", self.adminb)
        import json
        eintrag.antworten_json = json.dumps({
            "ab_vollstaendig": "Ja", "ab_unterlagen": "Ja", "ab_einweisung_bestaetigt": "Ja",
            "ab_datum": "2026-10-14", "ab_unterschrift_kunde": png_daten_url(),
            "ab_unterschrift_monteur": png_daten_url()})
        ok, meldung = montage_formulare.abschliessen(self.s, logik, eintrag, g, self.adminb)
        self.s.commit()
        self.assertTrue(ok, meldung)
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertEqual(g.phase, "freigabe")
        self.assertIn("automatisch", meldung)
        # Termin als Auslöser: Auftragseingang mit nur noch „Montageteam zuweisen“ offen
        g2 = self.gewerk_neu()
        offen = self.pflicht(g2, 0)
        zuweisen = next((a for a in offen if a.titel == "Montageteam zuweisen"), None)
        self.assertIsNotNone(zuweisen)
        self.erledigen([a for a in offen if a.id != zuweisen.id])
        ok, meldung, _ = kern.termin_speichern(self.s, g2, {
            "art": "montage", "team_id": self.team.id,
            "beginn": datetime.now().date() + timedelta(days=40)}, benutzer=self.adminb)
        self.assertTrue(ok, meldung)
        self.s.commit()
        self.s.expire_all()
        self.assertEqual(self.s.get(Gewerk, g2.id).phase, "feinplanung_vot")
        self.assertEqual(self.s.get(Aufgabe, zuweisen.id).status, "erledigt")

    def test_ohne_pflichtaufgaben_kein_wechsel(self):
        g = self.gewerk_neu()
        for instanz in self.s.query(AufgabenpaketInstanz).filter_by(gewerk_id=g.id):
            instanz.deaktiviert_am = datetime.now()
        self.s.commit()
        gewechselt, meldung = kern.auto_weiterschalten(self.s, g, self.adminb)
        self.assertFalse(gewechselt)
        self.assertIn("Keine Pflichtaufgaben", meldung)
        self.assertEqual(g.phase, "auftragseingang")


if __name__ == "__main__":
    unittest.main()
