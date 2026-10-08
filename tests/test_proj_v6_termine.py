# v28 (PLAN_PROJ_V6 Phase 135): ein Termin-Dialog, Routen termin/bearbeiten/loeschen,
# Besetzung je Termin, zweck (wp/elektro/sub) im Terminstatus, Kalender-Drag-Regel,
# Konflikte je Person, Terminvorschläge Stufe 1, migration_v28. Kontrollwerte (a)–(f)
# des Plans. Testdaten: Kunde „V28P1-Termine“, Benutzer/Teams mit Präfix „V28P1“.
import unittest
import warnings
from datetime import date, datetime, timedelta
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, auth
from app import projektierung as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Aufgabe, AufgabenpaketInstanz,
                        Benutzer, Gewerk, Kunde, Projekt, ProjektTermin, ProjektVerlauf,
                        SteckbriefWert, Team, TeamMitglied, TerminBesetzung, Vorgang,
                        angebot_status_setzen)

TEST_EMAIL = "v28p1-termine@test.local"
PRAEFIX = "V28P1 "


def aufraeumen(s):
    from app.models import Erfassung, GalerieDatei, ProjektMail, UglBestellung, VorgangsNotiz
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for p in s.query(Projekt).filter_by(kunde_id=k.id):
            for g in s.query(Gewerk).filter_by(projekt_id=p.id):
                s.query(UglBestellung).filter_by(gewerk_id=g.id).delete()
                s.query(Aufgabe).filter_by(gewerk_id=g.id).delete()
                s.query(AufgabenpaketInstanz).filter_by(gewerk_id=g.id).delete()
                s.query(SteckbriefWert).filter_by(gewerk_id=g.id).delete()
                s.delete(g)
            for t in s.query(ProjektTermin).filter_by(projekt_id=p.id):
                s.query(TerminBesetzung).filter_by(termin_id=t.id).delete()
                s.delete(t)
            s.query(ProjektVerlauf).filter_by(projekt_id=p.id).delete()
            s.query(ProjektMail).filter_by(projekt_id=p.id).delete()
            s.delete(p)
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(GalerieDatei).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.delete(k)
    for t in s.query(Team).filter(Team.name.like(PRAEFIX + "%")):
        s.query(TeamMitglied).filter_by(team_id=t.id).delete()
        for termin in s.query(ProjektTermin).filter_by(team_id=t.id):
            s.query(TerminBesetzung).filter_by(termin_id=termin.id).delete()
            s.delete(termin)
        s.delete(t)
    for b in s.query(Benutzer).filter(Benutzer.name.like(PRAEFIX + "%")):
        s.query(TeamMitglied).filter_by(benutzer_id=b.id).delete()
        s.query(TerminBesetzung).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        # Monteure A, B, C (Rolle Montage) und zwei Montage-Teams
        cls.monteure = {}
        for kuerzel in ("A", "B", "C"):
            b = Benutzer(name=f"{PRAEFIX}Monteur {kuerzel}", rolle="montage",
                         pin_hash=auth.pin_hash("4711"), aktiv=True)
            cls.s.add(b)
            cls.monteure[kuerzel] = b
        cls.s.flush()
        cls.team1 = Team(name=f"{PRAEFIX}Team 1", typ="montage", farbe="#2d6bd6")
        cls.team2 = Team(name=f"{PRAEFIX}Team 2", typ="montage", farbe="#1f9d55")
        # Teams 3–5 nur für die Terminvorschläge (keine fremden Termine)
        cls.team3 = Team(name=f"{PRAEFIX}Team 3", typ="montage", farbe="#c47a12")
        cls.team4 = Team(name=f"{PRAEFIX}Team 4 leer", typ="montage", farbe="#7a3fbf")
        cls.team5 = Team(name=f"{PRAEFIX}Team 5 Routing", typ="montage", farbe="#cf3b2c")
        cls.s.add_all([cls.team1, cls.team2, cls.team3, cls.team4, cls.team5])
        cls.s.flush()
        for kuerzel in ("A", "B"):
            cls.s.add(TeamMitglied(team_id=cls.team1.id,
                                   benutzer_id=cls.monteure[kuerzel].id))
        cls.s.add(TeamMitglied(team_id=cls.team2.id, benutzer_id=cls.monteure["C"].id))
        cls.s.add(TeamMitglied(team_id=cls.team3.id, benutzer_id=cls.monteure["C"].id))
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def setUp(self):
        self.s.expire_all()

    def gewerk_neu(self, sparte="WP", strasse="Teststr. 7", ort="Duisburg"):
        kunde = Kunde(anrede="Frau", vorname="Tanja", nachname="V28P1-Termine",
                      strasse=strasse, plz="47139", ort=ort,
                      email=TEST_EMAIL, telefon="0203 3")
        self.s.add(kunde)
        self.s.flush()
        angebot = angebot_aufbau.angebot_anlegen(self.s, kunde.id, sparte=sparte)
        angebot.positionen.append(AngebotsPosition(
            sort=1, pos_nr="047", bezeichnung="Pos 047", beschreibung="Pos 047",
            menge=1, e_preis_cent=10000))
        angebot_status_setzen(angebot, "Angenommen")
        self.s.commit()
        projekt = kern.projekt_anlegen(self.s, angebot, projektleiter_id=1)
        gewerk = kern.gewerk_anlegen(self.s, projekt, angebot, sparte)
        self.s.commit()
        return gewerk

    def aufgabe(self, gewerk, titel):
        return (self.s.query(Aufgabe)
                .filter(Aufgabe.gewerk_id == gewerk.id, Aufgabe.titel == titel).first())

    def termine(self, gewerk):
        return (self.s.query(ProjektTermin).filter_by(gewerk_id=gewerk.id)
                .order_by(ProjektTermin.id).all())

    def verlauf_texte(self, gewerk):
        return [v.text for v in self.s.query(ProjektVerlauf)
                .filter(ProjektVerlauf.gewerk_id == gewerk.id).order_by(ProjektVerlauf.id)]

    def ids(self, *kuerzel):
        return {self.monteure[k].id for k in kuerzel}

    def post_json(self, pfad, daten):
        return self.client.post(pfad, data=daten, headers={"Accept": "application/json"})


class TerminDialogRouten(Basis):
    def test_a_montage_ohne_team(self):
        g = self.gewerk_neu()
        r = self.post_json(f"/projektierung/gewerk/{g.id}/termin",
                           {"art": "montage", "beginn": "2026-11-09"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Montagetermine brauchen ein Team", r.json()["meldung"])
        self.assertEqual(self.termine(g), [])
        # Feinplanung ohne Person, Sub ohne Team/Sub
        r = self.post_json(f"/projektierung/gewerk/{g.id}/termin",
                           {"art": "feinplanung", "beginn": "2026-11-09", "uhrzeit": "09:00"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Person", r.json()["meldung"])
        r = self.post_json(f"/projektierung/gewerk/{g.id}/termin",
                           {"art": "sub", "beginn": "2026-11-09"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Subteam oder Subunternehmer", r.json()["meldung"])

    def test_b_anlage_mit_team_besetzung_zweck(self):
        g = self.gewerk_neu()
        r = self.post_json(f"/projektierung/gewerk/{g.id}/termin",
                           {"art": "montage", "team_id": str(self.team1.id),
                            "beginn": "2026-12-14", "kunde_bestaetigt": "on",
                            "notiz": "Kran vor Ort"})
        self.assertEqual(r.status_code, 200, r.text)
        daten = r.json()
        self.assertTrue(daten["ok"])
        self.assertEqual(daten["konflikte"], [])
        self.s.expire_all()
        termine = self.termine(g)
        self.assertEqual(len(termine), 1)
        t = termine[0]
        self.assertEqual((t.typ, t.zweck, t.team_id), ("montage", "wp", self.team1.id))
        self.assertEqual(t.beginn, datetime(2026, 12, 14))
        self.assertEqual(t.ende.date(), date(2026, 12, 18))      # Standarddauer 5 AT
        self.assertTrue(t.ganztaegig)
        self.assertTrue(t.kunde_bestaetigt)
        self.assertEqual(set(kern.besetzung_ids(self.s, t.id)), self.ids("A", "B"))
        self.assertEqual(self.s.get(Gewerk, g.id).wp_team_id, self.team1.id)
        self.assertEqual(self.aufgabe(g, "Montageteam zuweisen").status, "erledigt")
        self.assertEqual(kern.terminstatus(self.s, g)["status"], "terminiert")
        texte = self.verlauf_texte(g)
        self.assertTrue(any("Termin Montage (WP) 14.12.2026–18.12.2026 angelegt" in x
                            and "Besetzung:" in x for x in texte), texte)
        # Kurzform: erstes Wort abgekürzt („V28P1 Monteur A“ → „V. Monteur A“)
        self.assertEqual(kern.besetzung_namen(self.s, t.id), "V. Monteur A, V. Monteur B")
        self.assertEqual(kern.besetzung_namen(self.s, t.id, kurz=False),
                         f"{PRAEFIX}Monteur A, {PRAEFIX}Monteur B")
        # Akte zeigt den Block Termine mit Besetzung, Bearbeiten-/Löschen-Dialog
        r = self.client.get(f"/projektierung/projekt/{g.projekt_id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'id="termine-{g.id}"', r.text)
        self.assertIn("Montage (WP)", r.text)
        self.assertIn(f'id="dlg-termin-edit-{t.id}"', r.text)
        self.assertIn(f'id="dlg-termin-del-{t.id}"', r.text)
        self.assertIn('name="besetzung_gesetzt"', r.text)
        self.assertIn("Terminvorschläge", r.text)

    def test_c_bearbeiten_besetzung_und_teamwechsel(self):
        g = self.gewerk_neu()
        ok, _, _ = kern.team_termin_zuweisen(self.s, g, "wp", self.team1.id,
                                             datetime(2027, 1, 11), None, False)
        self.assertTrue(ok)
        self.s.commit()
        t = self.termine(g)[0]
        tid = t.id
        self.assertEqual(set(kern.besetzung_ids(self.s, tid)), self.ids("A", "B"))
        # Besetzung {A, C} – B raus, C rein (C ist nicht im Team 1)
        r = self.client.post(f"/projektierung/termin/{tid}/bearbeiten",
                             data={"art": "montage", "team_id": str(self.team1.id),
                                   "beginn": "2027-01-11", "ende": "2027-01-15",
                                   "besetzung_gesetzt": "1",
                                   "besetzung": [str(self.monteure["A"].id),
                                                 str(self.monteure["C"].id)]},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        self.assertEqual(set(kern.besetzung_ids(self.s, tid)), self.ids("A", "C"))
        self.assertTrue(any("Besetzung Termin Montage (WP)" in x and "Monteur C" in x
                            for x in self.verlauf_texte(g)))
        # Teamwechsel: Besetzung von Hand gesetzt → bleibt; Zuweisungsfeld folgt
        r = self.client.post(f"/projektierung/termin/{tid}/bearbeiten",
                             data={"team_id": str(self.team2.id), "beginn": "2027-01-18",
                                   "ende": "2027-01-22"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        t = self.s.get(ProjektTermin, tid)
        self.assertEqual((t.team_id, t.beginn.date()), (self.team2.id, date(2027, 1, 18)))
        self.assertEqual(self.s.get(Gewerk, g.id).wp_team_id, self.team2.id)
        self.assertEqual(set(kern.besetzung_ids(self.s, t.id)), self.ids("A", "C"))
        texte = self.verlauf_texte(g)
        self.assertTrue(any(f"Montageteam gewechselt: {PRAEFIX}Team 1 → {PRAEFIX}Team 2" in x
                            for x in texte), texte)
        self.assertTrue(any("Besetzung beibehalten (von Hand gesetzt)" in x for x in texte))
        # Art ist beim Bearbeiten gesperrt (bleibt Montage/WP)
        self.assertEqual((t.typ, t.zweck), ("montage", "wp"))
        # Termin, dessen Besetzung der Team-Vorlage entspricht, folgt dem neuen Team
        g2 = self.gewerk_neu()
        kern.team_termin_zuweisen(self.s, g2, "wp", self.team1.id, datetime(2027, 2, 1), None, False)
        self.s.commit()
        t2 = self.termine(g2)[0]
        ok, _, _ = kern.termin_speichern(self.s, g2, {"team_id": self.team2.id,
                                                      "beginn": date(2027, 2, 1)},
                                         termin=t2)
        self.assertTrue(ok)
        self.assertEqual(set(kern.besetzung_ids(self.s, t2.id)), self.ids("C"))
        self.s.commit()

    def test_d_loeschen_einziger_montagetermin(self):
        g = self.gewerk_neu()
        kern.team_termin_zuweisen(self.s, g, "wp", self.team1.id, datetime(2027, 2, 8), None, True)
        self.s.commit()
        tid = self.termine(g)[0].id
        self.assertEqual(self.aufgabe(g, "Montageteam zuweisen").status, "erledigt")
        r = self.post_json(f"/projektierung/termin/{tid}/loeschen", {"grund": ""})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["meldung"], "Bitte einen Grund angeben.")
        self.assertEqual(len(self.termine(g)), 1)
        r = self.post_json(f"/projektierung/termin/{tid}/loeschen", {"grund": "Kunde hat abgesagt"})
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        self.assertEqual(self.termine(g), [])
        self.assertEqual(self.s.query(TerminBesetzung).filter_by(termin_id=tid).count(), 0)
        self.assertEqual(kern.terminstatus(self.s, g)["status"], "unterminiert")
        self.assertEqual(self.aufgabe(g, "Montageteam zuweisen").status, "offen")
        texte = self.verlauf_texte(g)
        self.assertTrue(any("Termin Montage (WP) 08.02.2027–12.02.2027 gelöscht – Kunde hat abgesagt" in x
                            for x in texte), texte)
        self.assertTrue(any("Montageteam zuweisen“ wieder offen" in x for x in texte))
        # Board: Gewerk steht wieder unter „unterminiert“
        r = self.client.get("/projektierung?q=V28P1-Termine")
        self.assertEqual(r.status_code, 200)

    def test_e_elektro_termin_bestimmt_terminstatus_nicht(self):
        g = self.gewerk_neu()
        ok, _, _ = kern.team_termin_zuweisen(self.s, g, "elektro", self.team2.id,
                                             datetime(2027, 3, 20), None, True)
        self.assertTrue(ok)
        self.s.commit()
        elektro = self.termine(g)[0]
        self.assertEqual((elektro.typ, elektro.zweck), ("montage", "elektro"))
        self.assertEqual(self.s.get(Gewerk, g.id).elektro_team_id, self.team2.id)
        self.assertEqual(self.aufgabe(g, "Elektro-Montageteam zuweisen").status, "erledigt")
        self.assertEqual(self.aufgabe(g, "Montageteam zuweisen").status, "offen")
        self.assertEqual(kern.terminstatus(self.s, g)["status"], "unterminiert")
        kern.team_termin_zuweisen(self.s, g, "wp", self.team1.id, datetime(2027, 3, 10), None, True)
        self.s.commit()
        ts = kern.terminstatus(self.s, g)
        self.assertEqual(ts["status"], "terminiert")
        self.assertEqual(ts["termin"].beginn.date(), date(2027, 3, 10))
        # Löschen des Elektro-Termins öffnet „Elektro-Montageteam zuweisen“ wieder
        ok, _ = kern.termin_loeschen(self.s, elektro, "Sub übernimmt")
        self.assertTrue(ok)
        self.assertEqual(self.aufgabe(g, "Elektro-Montageteam zuweisen").status, "offen")
        self.assertEqual(kern.terminstatus(self.s, g)["status"], "terminiert")
        self.s.commit()

    def test_alte_formulare_und_sub_feinplanung(self):
        g = self.gewerk_neu()
        # Alias team-termin (altes Formular mit zweck/beginn als Datum)
        r = self.client.post(f"/projektierung/gewerk/{g.id}/team-termin", data={
            "zweck": "wp", "team_id": str(self.team1.id), "beginn": "2026-11-09",
            "zurueck": "/projektierung"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/projektierung?meldung="))
        self.s.expire_all()
        t = self.termine(g)[0]
        self.assertEqual((t.typ, t.zweck), ("montage", "wp"))
        self.assertEqual(set(kern.besetzung_ids(self.s, t.id)), self.ids("A", "B"))
        # altes Termin-Formular: typ + datetime-local
        r = self.client.post(f"/projektierung/gewerk/{g.id}/termin", data={
            "typ": "feinplanung", "beginn": "2026-10-20T09:07", "person_id": "1",
            "notiz": "VOT"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        fp = [x for x in self.termine(g) if x.typ == "feinplanung"][0]
        self.assertEqual(fp.beginn, datetime(2026, 10, 20, 9, 0))     # 15-Minuten-Takt
        self.assertFalse(fp.ganztaegig)
        self.assertEqual(fp.person_id, 1)
        # Sub-Einsatz mit Subteam (Besetzung aus dem Subteam, Zuweisungsfeld sub_team_id)
        sub_team = Team(name=f"{PRAEFIX}Sub", typ="sub")
        self.s.add(sub_team)
        self.s.commit()
        r = self.post_json(f"/projektierung/gewerk/{g.id}/termin",
                           {"art": "sub", "team_id": str(sub_team.id), "beginn": "2026-11-02"})
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        sub = [x for x in self.termine(g) if x.typ == "sub"][0]
        self.assertEqual((sub.zweck, sub.ende.date()), ("sub", date(2026, 11, 2)))
        self.assertEqual(self.s.get(Gewerk, g.id).sub_team_id, sub_team.id)
        # Terminübersicht + Kalender rendern mit Besetzung/Art
        r = self.client.get("/projektierung/termine?start=2026-11-09")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Montage (WP)", r.text)
        self.assertIn("Monteur A", r.text)
        self.assertIn('id="dlg-termin-uebersicht"', r.text)
        r = self.client.get("/projektierung/kalender?start=2026-11-09")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Besetzung: ", r.text)


class BesetzungRegeln(Basis):
    def test_kalender_drag_teamwechsel(self):
        g = self.gewerk_neu()
        kern.team_termin_zuweisen(self.s, g, "wp", self.team1.id, datetime(2027, 4, 5), None, False)
        self.s.commit()
        t = self.termine(g)[0]
        # Besetzung = Vorlage Team 1 → Drag auf Team 2 belegt neu (C)
        kern.termin_verschieben(self.s, t, date(2027, 4, 12), neues_team_id=self.team2.id)
        self.assertEqual(set(kern.besetzung_ids(self.s, t.id)), self.ids("C"))
        self.assertEqual(self.s.get(Gewerk, g.id).wp_team_id, self.team2.id)
        # von Hand gesetzt → bleibt + Verlauf
        kern.besetzung_setzen(self.s, t, [self.monteure["A"].id])
        kern.termin_verschieben(self.s, t, date(2027, 4, 19), neues_team_id=self.team1.id)
        self.assertEqual(set(kern.besetzung_ids(self.s, t.id)), self.ids("A"))
        self.assertTrue(any("Besetzung beibehalten (von Hand gesetzt)" in x
                            for x in self.verlauf_texte(g)))
        self.s.commit()

    def test_person_konflikte_warnung(self):
        g1, g2 = self.gewerk_neu(), self.gewerk_neu()
        kern.team_termin_zuweisen(self.s, g1, "wp", self.team1.id, datetime(2027, 5, 3), None, False)
        self.s.commit()
        ok, meldung, konflikte = kern.team_termin_zuweisen(
            self.s, g2, "wp", self.team1.id, datetime(2027, 5, 5), None, False)
        self.assertTrue(ok)
        self.s.commit()
        projekt1 = self.s.get(Projekt, g1.projekt_id)
        self.assertTrue(any(f"{PRAEFIX}Monteur A ist am 05.05. bereits bei {projekt1.nummer}" in k
                            for k in konflikte), konflikte)
        self.assertTrue(any(k.startswith(projekt1.nummer) for k in konflikte))   # Team-Konflikt
        self.assertEqual(len(self.termine(g2)), 1)                               # kein Verbot

    def test_besetzung_hilfsfunktionen(self):
        g = self.gewerk_neu()
        kern.team_termin_zuweisen(self.s, g, "wp", self.team1.id, datetime(2027, 6, 7), None, False)
        self.s.commit()
        t = self.termine(g)[0]
        kern.besetzung_setzen(self.s, t, [self.monteure["A"].id, self.monteure["B"].id,
                                          self.monteure["C"].id, self.monteure["C"].id])
        self.assertEqual(kern.besetzung_ids(self.s, t.id),
                         [self.monteure["A"].id, self.monteure["B"].id, self.monteure["C"].id])
        self.assertTrue(kern.besetzung_namen(self.s, t.id).endswith("+1"))
        self.assertEqual(kern._name_kurz("Rene Golaschewski"), "R. Golaschewski")
        self.assertEqual(kern._name_kurz("D. Jobelius"), "D. Jobelius")
        self.assertEqual(kern.besetzung_map(self.s, [t.id])[t.id][0], self.monteure["A"].id)
        self.s.commit()


class Vorschlaege(Basis):
    def test_f_terminvorschlaege(self):
        g = self.gewerk_neu()
        belegt = self.gewerk_neu()
        kern.team_termin_zuweisen(self.s, belegt, "wp", self.team3.id,
                                  datetime(2026, 11, 2), datetime(2026, 11, 6), True)
        self.s.commit()
        heute = datetime(2026, 10, 6, 10, 0)
        daten = kern.terminvorschlaege(self.s, g, team_id=self.team3.id, heute=heute)
        self.assertEqual(daten["dauer_tage"], 5)
        self.assertEqual(daten["fruehester"], "2026-11-09")
        v = daten["vorschlaege"]
        self.assertEqual([x["beginn"] for x in v[:2]], ["2026-11-09", "2026-11-16"])
        self.assertEqual(v[0]["ende"], "2026-11-13")
        self.assertEqual(v[0]["beginn_text"], "Mo 09.11.")
        self.assertEqual(v[0]["besetzung"], [self.monteure["C"].id])
        self.assertIn("frei nach", v[0]["begruendung"])
        self.assertEqual(len(v), 5)
        # Team ohne Termine → ebenfalls Mo 09.11.2026 (erster Montag ≥ 03.11.2026)
        daten = kern.terminvorschlaege(self.s, g, team_id=self.team4.id, heute=heute)
        self.assertEqual(daten["vorschlaege"][0]["beginn"], "2026-11-09")
        self.assertEqual(daten["vorschlaege"][0]["begruendung"], "erstes freies Fenster des Teams")
        self.assertEqual(daten["vorschlaege"][0]["besetzung"], [])
        # Team 3 belegt am 11./12.11. → erster Vorschlag rutscht auf den 16.11.
        kern.team_termin_zuweisen(self.s, belegt, "wp", self.team3.id,
                                  datetime(2026, 11, 11), datetime(2026, 11, 12), True)
        self.s.commit()
        daten = kern.terminvorschlaege(self.s, g, team_id=self.team3.id, heute=heute)
        self.assertEqual(daten["vorschlaege"][0]["beginn"], "2026-11-16")
        # ohne Routing-Anbieter: Umweg „–“ + Hinweis, keine Netzaufrufe
        self.assertEqual(daten["vorschlaege"][0]["umweg_text"], "–")
        self.assertEqual(daten["hinweis"], "Fahrzeiten: kein Routing-Anbieter konfiguriert")
        self.assertFalse(daten["routing"])
        # Lieferdatum der letzten UGL-Bestellung + 1 Arbeitstag schiebt den Beginn
        from app.models import UglBestellung
        self.s.add(UglBestellung(gewerk_id=g.id, nr=1, dateiname="x.ugl",
                                 lieferdatum=datetime(2026, 11, 20)))
        self.s.commit()
        daten = kern.terminvorschlaege(self.s, g, team_id=self.team4.id, heute=heute)
        self.assertEqual(daten["fruehester"], "2026-11-23")
        self.assertEqual(daten["vorschlaege"][0]["beginn"], "2026-11-23")
        self.assertEqual(kern.naechster_montag(date(2026, 11, 9)), date(2026, 11, 9))
        self.assertEqual(kern.naechster_montag(date(2026, 11, 3)), date(2026, 11, 9))
        # JSON-Route
        r = self.client.get(f"/projektierung/gewerk/{g.id}/terminvorschlaege.json?team_id={self.team4.id}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertTrue(r.json()["vorschlaege"])

    def test_vorschlaege_mit_routing_gemockt(self):
        """Mit Routing-Anbieter: Geocoding + Matrix laufen (gemockt, kein Netz) und
        liefern einen Umweg in Minuten; Sitzung ist vor dem Netzaufruf freigegeben."""
        from app import geocoding, routing
        g = self.gewerk_neu()
        vorher = self.gewerk_neu(strasse="Hafenstr. 12", ort="Moers")
        kern.team_termin_zuweisen(self.s, vorher, "wp", self.team5.id,
                                  datetime(2026, 11, 2), datetime(2026, 11, 6), True)
        self.s.commit()
        punkte = {}

        def geokodieren(session, adresse):
            punkte.setdefault(adresse, (51.4 + len(punkte) * 0.01, 6.7))
            return punkte[adresse][0], punkte[adresse][1], "ok"

        def fahrzeit(session, von, nach):
            if von == nach:
                return {"minuten": 0.0, "km": 0.0, "geschaetzt": False}
            return {"minuten": 20.0, "km": 15.0, "geschaetzt": False}

        with mock.patch.object(kern, "routing_konfiguriert", return_value=True), \
                mock.patch.object(geocoding, "geokodieren", side_effect=geokodieren), \
                mock.patch.object(routing, "matrix_fuellen") as matrix, \
                mock.patch.object(routing, "fahrzeit", side_effect=fahrzeit):
            daten = kern.terminvorschlaege(self.s, g, team_id=self.team5.id,
                                           heute=datetime(2026, 10, 6))
        self.assertTrue(daten["routing"])
        self.assertEqual(daten["hinweis"], "")
        # vorher (Moers) → Ziel 20 min, Ziel → Startadresse 20 min, direkt 20 min
        self.assertEqual(daten["vorschlaege"][0]["umweg_min"], 20)
        self.assertEqual(daten["vorschlaege"][0]["umweg_text"], "20 min")
        self.assertTrue(matrix.called)
        self.assertIn("Arnold-Overbeck-Str. 63-65, 47139 Duisburg", punkte)
        self.assertIn("Hafenstr. 12, 47139 Moers", punkte)


class Migration(Basis):
    def test_migration_v28_zweck_und_besetzung(self):
        kern.migration_v28(self.s)      # Bestand der Kopie einmal nachziehen
        self.s.commit()
        g = self.gewerk_neu()
        g.elektro_team_id = self.team2.id
        g.wp_team_id = self.team1.id
        alt_wp = ProjektTermin(projekt_id=g.projekt_id, gewerk_id=g.id, typ="montage",
                               beginn=datetime(2026, 11, 9), ende=datetime(2026, 11, 13),
                               team_id=self.team1.id, zweck="")
        alt_el = ProjektTermin(projekt_id=g.projekt_id, gewerk_id=g.id, typ="montage",
                               beginn=datetime(2026, 11, 20), team_id=self.team2.id, zweck="")
        ohne_team = ProjektTermin(projekt_id=g.projekt_id, gewerk_id=g.id, typ="montage",
                                  beginn=datetime(2026, 12, 1), zweck="")
        self.s.add_all([alt_wp, alt_el, ohne_team])
        self.s.commit()
        meldungen = kern.migration_v28(self.s)
        self.s.commit()
        self.assertTrue(any("3 Montagetermine mit Zweck" in m for m in meldungen), meldungen)
        self.assertTrue(any("Besetzung für 2 Termine" in m for m in meldungen), meldungen)
        self.s.expire_all()
        self.assertEqual(self.s.get(ProjektTermin, alt_wp.id).zweck, "wp")
        self.assertEqual(self.s.get(ProjektTermin, alt_el.id).zweck, "elektro")
        self.assertEqual(self.s.get(ProjektTermin, ohne_team.id).zweck, "wp")
        self.assertEqual(set(kern.besetzung_ids(self.s, alt_wp.id)), self.ids("A", "B"))
        self.assertEqual(set(kern.besetzung_ids(self.s, alt_el.id)), self.ids("C"))
        self.assertEqual(kern.besetzung_ids(self.s, ohne_team.id), [])
        self.assertEqual(kern.terminstatus(self.s, g)["termin"].id, alt_wp.id)   # Elektro zählt nicht
        # zweiter Lauf: keine Meldungen
        self.assertEqual(kern.migration_v28(self.s), [])


if __name__ == "__main__":
    unittest.main()
