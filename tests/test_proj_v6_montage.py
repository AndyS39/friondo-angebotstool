# v28 (PLAN_PROJ_V6 Phase 137, Agent P2): Montage-Backend /montage –
# Besetzungs-Sicht (Besetzung je Termin, Fallback Team/Person), „Meine
# Einsätze“ + Team-Umschalter, Wochenkalender mit Initialen, Steckbrief
# vollständig (leere Felder „–“), neue Reihenfolge der Auftragsseite, Notizen
# read-only, Montage starten/beenden, automatisches Montage-Ende mit dem
# Abnahmeprotokoll, Vorbelegung „Mitarbeiter (Team)“.
# Nachtrag 08.10.2026 (Antwort Andreas, Agent PB): der Kurzbericht beim Beenden
# entfällt ganz (kein Feld auf der Auftragsseite; ein mitgeschicktes Feld
# „bericht“ wird nur noch aus Altgründen angenommen und landet im Verlauf, wenn
# es nicht leer ist).
import json
import unittest
import warnings

warnings.filterwarnings("ignore")

from app import montage_formulare, projektierung_logik
from app import projektierung as kern
from app.models import Benutzer, Gewerk, Kunde, Projekt, ProjektTermin, SteckbriefWert
from app.routers import montage as montage_router
from tests.proj_v6_p2_basis import Basis, client_fuer, png_daten_url


class Hilfsfunktionen(unittest.TestCase):
    def test_initialen_und_kurzname(self):
        self.assertEqual(montage_router.initialen("Max Müller"), "MM")
        self.assertEqual(montage_router.initialen("D. Jobelius"), "DJ")
        self.assertEqual(montage_router.initialen("Admin"), "AD")
        self.assertEqual(montage_router.initialen("Anna Maria Berg-Schmidt"), "AMB")
        self.assertEqual(montage_router.initialen(""), "?")
        self.assertEqual(montage_router.kurzname("Max Müller"), "M. Müller")
        self.assertEqual(montage_router.kurzname("Admin"), "Admin")

    def test_termin_art(self):
        t = ProjektTermin(typ="montage", zweck="wp")
        self.assertEqual(montage_router.termin_art(t), "Montage (WP)")
        self.assertEqual(montage_router.termin_art(ProjektTermin(typ="montage", zweck="elektro")),
                         "Elektro-Montage")
        self.assertEqual(montage_router.termin_art(ProjektTermin(typ="montage", zweck="")), "Montage")
        self.assertEqual(montage_router.termin_art(ProjektTermin(typ="feinplanung", zweck="")),
                         "Feinplanung VOT")
        self.assertEqual(montage_router.termin_art(ProjektTermin(typ="abnahme", zweck="")), "Abnahme")
        self.assertEqual(montage_router.termin_art(ProjektTermin(typ="sub", zweck="")), "Sub-Einsatz")


class Besetzung(Basis):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.a = cls.benutzer_neu("Monteur A", rolle="montage")
        cls.b = cls.benutzer_neu("Monteur B", rolle="montage")
        cls.c = cls.benutzer_neu("Monteur C", rolle="montage")
        cls.team = cls.team_neu("Team Eins", [cls.a, cls.b])
        cls.team2 = cls.team_neu("Team Zwei", [cls.c])
        cls.gewerk = cls.gewerk_neu()
        cls.termin = cls.termin_neu(cls.gewerk, cls.team, tage=2)

    def sieht(self, benutzer: Benutzer, termin: ProjektTermin) -> tuple[bool, bool]:
        """(in „Meine Einsätze“ gelistet, Auftragsseite erreichbar)."""
        c = client_fuer(benutzer.id)
        liste = c.get("/montage")
        self.assertEqual(liste.status_code, 200)
        seite = c.get(f"/montage/einsatz/{termin.id}", follow_redirects=False)
        return (f"/montage/einsatz/{termin.id}" in liste.text, seite.status_code == 200)

    def test_fallback_ohne_besetzung_teammitglieder(self):
        self.besetzung_setzen(self.termin, [])
        self.assertEqual(self.sieht(self.a, self.termin), (True, True))
        self.assertEqual(self.sieht(self.b, self.termin), (True, True))
        self.assertEqual(self.sieht(self.c, self.termin), (False, False))
        self.assertTrue(montage_router._einsatz_erlaubt(self.s, self.a, self.termin))
        self.assertFalse(montage_router._einsatz_erlaubt(self.s, self.c, self.termin))

    def test_besetzung_entscheidet(self):
        # Monteur C (nicht im Team 1) mit Besetzung → sieht den Einsatz;
        # Monteur B (Team 1, aus der Besetzung entfernt) → sieht ihn nicht
        self.besetzung_setzen(self.termin, [self.a, self.c])
        try:
            self.assertEqual(self.sieht(self.c, self.termin), (True, True))
            self.assertEqual(self.sieht(self.b, self.termin), (False, False))
            self.assertEqual(self.sieht(self.a, self.termin), (True, True))
            self.assertTrue(montage_router._einsatz_erlaubt(self.s, self.c, self.termin))
            self.assertFalse(montage_router._einsatz_erlaubt(self.s, self.b, self.termin))
            # Admin sieht alles; Projektierung (Hauptrolle) ebenfalls [ANNAHME]
            r = self.admin.get(f"/montage/einsatz/{self.termin.id}", follow_redirects=False)
            self.assertEqual(r.status_code, 200)
            pj = self.benutzer_neu("Projektierer M", rolle="projektierung")
            r = client_fuer(pj.id).get(f"/montage/einsatz/{self.termin.id}", follow_redirects=False)
            self.assertEqual(r.status_code, 200)
            # Teamansicht: alle Termine des Teams – B sieht ihn dort (Team 1), Besetzung als Chips
            r = client_fuer(self.b.id).get(f"/montage?team_id={self.team.id}")
            self.assertEqual(r.status_code, 200)
            self.assertIn(f"/montage/einsatz/{self.termin.id}", r.text)
            self.assertIn("V. Monteur C", r.text)   # Kurzname von „V28P2 Monteur C“
        finally:
            self.besetzung_setzen(self.termin, [])

    def test_meine_einsaetze_und_umschalter(self):
        # A ist in zwei Teams → Umschalter „Meine Einsätze | Team Eins | Team Zwei“
        from app.models import TeamMitglied
        self.s.add(TeamMitglied(team_id=self.team2.id, benutzer_id=self.a.id))
        self.s.commit()
        try:
            c = client_fuer(self.a.id)
            r = c.get("/montage")
            self.assertEqual(r.status_code, 200)
            self.assertIn("Meine Einsätze", r.text)
            self.assertIn(f"/montage?team_id={self.team.id}", r.text)
            self.assertIn(f"/montage?team_id={self.team2.id}", r.text)
            # Wochenkalender in der Teamansicht: Initialen der Besetzung
            self.besetzung_setzen(self.termin, [self.a, self.b])
            start = self.termin.beginn.date().isoformat()
            r = c.get(f"/montage?team_id={self.team.id}&ansicht=kalender&start={start}")
            self.assertEqual(r.status_code, 200)
            self.assertIn('class="pj-ini ich"', r.text)
            self.assertIn(">VMA<", r.text)    # Initialen von „V28P2 Monteur A“
        finally:
            self.besetzung_setzen(self.termin, [])
            self.s.query(TeamMitglied).filter_by(team_id=self.team2.id, benutzer_id=self.a.id).delete()
            self.s.commit()

    def test_monteur_ohne_team_nur_besetzung(self):
        # C ist in Team Zwei, der Termin gehört Team Eins: nur über Besetzung sichtbar
        self.besetzung_setzen(self.termin, [self.c])
        try:
            self.assertEqual(self.sieht(self.c, self.termin), (True, True))
        finally:
            self.besetzung_setzen(self.termin, [])


class Auftragsseite(Basis):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.a = cls.benutzer_neu("Monteur S", rolle="montage")
        cls.team = cls.team_neu("Team S", [cls.a])
        cls.gewerk = cls.gewerk_neu()
        cls.termin = cls.termin_neu(cls.gewerk, cls.team, tage=1, besetzung=[cls.a])

    def test_steckbrief_vollstaendig(self):
        c = client_fuer(self.a.id)
        r = c.get(f"/montage/einsatz/{self.termin.id}")
        self.assertEqual(r.status_code, 200)
        felder = kern.steckbrief_felder("WP")
        self.assertGreaterEqual(len(felder), 20)
        for _, name in felder:
            self.assertIn(f'<span class="k">{name}', r.text, name)
        werte = kern.steckbrief_daten(self.s, [self.gewerk.id])[self.gewerk.id]
        leer = sum(1 for feld, _ in felder if not (werte.get(feld) and werte[feld].wert))
        self.assertEqual(r.text.count('class="w leer">–<'), leer)
        self.assertGreater(leer, 0)
        zeilen = montage_router.steckbrief_zeilen(self.s, self.gewerk)
        self.assertEqual([z["feld"] for z in zeilen], [f for f, _ in felder])
        self.assertTrue(all(z["wert"] == "–" for z in zeilen if z["leer"]))

    def test_steckbrief_ableitung_wird_nachgeholt(self):
        g = self.gewerk_neu(positionen=[("047", 1), ("126", 3)])
        self.s.query(SteckbriefWert).filter_by(gewerk_id=g.id).delete()
        self.s.commit()
        zeilen = montage_router.steckbrief_zeilen(self.s, g)
        self.assertTrue(any(not z["leer"] for z in zeilen),
                        "Ableitung aus den Auftragspositionen fehlt")

    def test_demo_projekt_alle_wp_felder(self):
        kunde = self.s.query(Kunde).filter(Kunde.nachname == "Demo Montage").first()
        if kunde is None:
            self.skipTest("Demo-Projekt „Demo Montage, Bernd“ nicht in dieser Datenbank")
        projekt = self.s.query(Projekt).filter_by(kunde_id=kunde.id).first()
        termin = (self.s.query(ProjektTermin).filter_by(projekt_id=projekt.id, typ="montage")
                  .first())
        if termin is None:
            self.skipTest("Demo-Projekt ohne Montagetermin")
        r = self.admin.get(f"/montage/einsatz/{termin.id}")
        self.assertEqual(r.status_code, 200)
        for _, name in kern.steckbrief_felder("WP"):
            self.assertIn(f'<span class="k">{name}', r.text, name)

    def test_reihenfolge_und_bloecke(self):
        c = client_fuer(self.a.id)
        r = c.get(f"/montage/einsatz/{self.termin.id}")
        self.assertEqual(r.status_code, 200)
        marken = ["<summary>Steckbrief", "Gerät &amp; Positionen", "Teams &amp; Termine",
                  "Notizen der Projektierung", 'id="status"', "Formulare", "Restarbeiten",
                  'id="foto"']
        positionen = [r.text.index(m) for m in marken]
        self.assertEqual(positionen, sorted(positionen), marken)
        self.assertNotIn("Offene Montage-Aufgaben", r.text)
        self.assertNotIn("/montage/aufgabe/", r.text)
        self.assertIn("Bemerkungen bitte im Montagebericht eintragen.", r.text)
        self.assertNotIn('class="notiz-eingabe', r.text)    # Monteur liest nur
        self.assertIn('class="pj-ini ich"', r.text)         # eigene Besetzung im Kopf
        self.assertIn("Montage (WP)", r.text)
        self.assertIn("Montage starten", r.text)
        self.assertIn('id="pj-lightbox"', r.text)
        # Notizen des Vorgangs erscheinen read-only, letzte fünf direkt
        from app import notizen
        admin = self.s.get(Benutzer, 1)
        vorgang = self.vorgang_von(self.gewerk)
        for i in range(6):
            notizen.notiz_anlegen(self.s, vorgang.id, admin, f"V28P2 Montage-Notiz {i}",
                                  herkunft="projektierung")
        self.s.commit()
        r = c.get(f"/montage/einsatz/{self.termin.id}")
        self.assertIn("V28P2 Montage-Notiz 5", r.text)
        self.assertIn("alle anzeigen · 1 ältere", r.text)

    def test_montage_starten_und_beenden(self):
        g = self.gewerk_neu(phase="montagevorbereitung")
        t = self.termin_neu(g, self.team, tage=3, besetzung=[self.a])
        c = client_fuer(self.a.id)
        r = c.post(f"/montage/einsatz/{t.id}/phase", data={"aktion": "gestartet", "uhrzeit": "07:52"},
                   follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertEqual(g.phase, "montage")
        texte = self.verlauf_texte(g)
        self.assertTrue(any("Montage gestartet (mobil, " in x and "07:45" in x for x in texte), texte)
        # Nachtrag 08.10.2026: die Auftragsseite hat kein Kurzbericht-Feld mehr,
        # der Hinweis verweist auf den Montagebericht
        r = c.get(f"/montage/einsatz/{t.id}")
        self.assertIn("Montage beenden", r.text)
        self.assertNotIn('name="bericht"', r.text)
        self.assertNotIn("Kurzbericht", r.text)
        self.assertIn("Bemerkungen zur Montage bitte im", r.text)
        # Beenden (ohne Bericht) → Abnahme, montage_fertig_am gesetzt
        r = c.post(f"/montage/einsatz/{t.id}/phase", data={"aktion": "fertig", "uhrzeit": "15:52"},
                   follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertNotIn("Kurzbericht", r.headers["location"])
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertEqual(g.phase, "abnahme")
        self.assertEqual(g.montage_fertig_am.strftime("%H:%M"), "15:45")
        texte = self.verlauf_texte(g)
        self.assertTrue(any("Montage beendet (mobil, " in x for x in texte), texte)
        self.assertFalse(any("Montage-Kurzbericht" in x for x in texte))
        # Nach Abnahme nur Statuszeile
        r = c.get(f"/montage/einsatz/{t.id}")
        self.assertNotIn("Montage beenden", r.text)
        self.assertNotIn("Montage starten", r.text)
        self.assertIn("Montage beendet", r.text)
        # Altbestand: ein mitgeschicktes Feld „bericht“ (ältere Oberfläche, Alt-Test
        # test_projektierung_v4) landet weiterhin im Verlauf, wenn es nicht leer ist;
        # Alias „beenden“
        g2 = self.gewerk_neu(phase="montage")
        t2 = self.termin_neu(g2, self.team, tage=4, besetzung=[self.a])
        r = c.post(f"/montage/einsatz/{t2.id}/phase",
                   data={"aktion": "beenden", "bericht": "V28P2 alles gut"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        self.assertEqual(self.s.get(Gewerk, g2.id).phase, "abnahme")
        self.assertTrue(any("Montage-Kurzbericht: V28P2 alles gut" in x for x in self.verlauf_texte(g2)))
        # „starten“ in Phase abnahme nicht vorgesehen → Meldung, Phase bleibt
        r = c.post(f"/montage/einsatz/{t2.id}/phase", data={"aktion": "gestartet"},
                   follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("nicht+vorgesehen", r.headers["location"])
        self.s.expire_all()
        self.assertEqual(self.s.get(Gewerk, g2.id).phase, "abnahme")

    def test_abnahme_beendet_montage(self):
        g = self.gewerk_neu(phase="montage")
        self.assertIsNone(g.montage_fertig_am)
        logik = projektierung_logik.hole_logik(self.s)
        admin = self.s.get(Benutzer, 1)
        eintrag = montage_formulare.formular_holen(self.s, g, "abnahme", admin)
        eintrag.antworten_json = json.dumps({
            "ab_vollstaendig": "Ja", "ab_maengel": "keine", "ab_unterlagen": "Ja",
            "ab_einweisung_bestaetigt": "Ja", "ab_datum": "2026-10-08",
            "ab_unterschrift_kunde": png_daten_url(), "ab_unterschrift_monteur": png_daten_url()})
        ok, meldung = montage_formulare.abschliessen(self.s, logik, eintrag, g, admin)
        self.s.commit()
        self.assertTrue(ok, meldung)
        self.assertIn("Montage beendet", meldung)
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertEqual(g.phase, "abnahme")
        self.assertIsNotNone(g.montage_fertig_am)
        texte = self.verlauf_texte(g)
        self.assertIn("Montage beendet mit Abnahme", texte)
        self.assertTrue(any("Abnahmeprotokoll unterschrieben (mobil)" in x for x in texte), texte)
        self.assertTrue(any("Abnahmeprotokoll abgeschlossen" in x for x in texte), texte)
        # Gewerk bereits in abnahme: nichts weiter (kein zweiter Verlaufseintrag)
        fertig = g.montage_fertig_am
        ok, meldung = montage_formulare.abschliessen(self.s, logik, eintrag, g, admin)
        self.s.commit()
        self.assertTrue(ok)
        self.assertNotIn("Montage beendet", meldung)
        self.assertEqual(self.verlauf_texte(g).count("Montage beendet mit Abnahme"), 1)
        self.assertEqual(self.s.get(Gewerk, g.id).montage_fertig_am, fertig)

    def test_mitarbeiter_vorbelegt_aus_besetzung(self):
        c = client_fuer(self.a.id)
        r = c.get(f"/montage/einsatz/{self.termin.id}/formular/montagebericht?seite=0")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'name="mb_mitarbeiter" value="{self.a.name}"', r.text)
        # ohne Besetzung: Mitglieder des Termin-Teams
        self.besetzung_setzen(self.termin, [])
        try:
            self.assertEqual(montage_router._mitarbeiter_vorbelegung(self.s, self.termin), self.a.name)
        finally:
            self.besetzung_setzen(self.termin, [self.a])

    def test_keine_montage_aufgaben_im_blatt(self):
        """Gesamtübersicht: gibt es Aufgaben mit rolle = montage im Blatt?
        (heute keine – informativ, Route /montage/aufgabe/{id}/erledigt bleibt)"""
        logik = projektierung_logik.hole_logik(self.s)
        montage_schritte = [(p.key, s.nr) for p in logik.pakete.values()
                            for s in p.schritte if s.rolle == "montage"]
        self.assertIsInstance(montage_schritte, list)
        r = self.admin.post("/montage/aufgabe/0/erledigt", data={"termin_id": "0"},
                            follow_redirects=False)
        self.assertEqual(r.status_code, 303)


if __name__ == "__main__":
    unittest.main()
