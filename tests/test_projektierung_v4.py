# Tests PLAN_PROJ_V4 (Phasen 90–93): Board/Ampeln/Termine/fetch, Pakete,
# Sub-Mails, BzA, Heizreport, UGL. Laufen gegen die Entwicklungs-DB (wie die
# übrigen Tests) und räumen ihre Testdaten (Kunde „Projekt-V4-Test“) wieder auf.
import json
import unittest
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau
from app import projektierung as kern
from app import projektierung_logik
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Aufgabe, AufgabenpaketInstanz,
                        Gewerk, Kunde, Projekt, ProjektTermin, ProjektVerlauf,
                        SteckbriefWert, Team, Vorgang, angebot_status_setzen)

TEST_EMAIL = "projekt-v4@test.local"


def aufraeumen(s):
    from app.models import Erfassung, GalerieDatei, ProjektMail
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for p in s.query(Projekt).filter_by(kunde_id=k.id):
            for g in s.query(Gewerk).filter_by(projekt_id=p.id):
                s.query(Aufgabe).filter_by(gewerk_id=g.id).delete()
                s.query(AufgabenpaketInstanz).filter_by(gewerk_id=g.id).delete()
                s.query(SteckbriefWert).filter_by(gewerk_id=g.id).delete()
                s.delete(g)
            s.query(ProjektTermin).filter_by(projekt_id=p.id).delete()
            s.query(ProjektVerlauf).filter_by(projekt_id=p.id).delete()
            s.query(ProjektMail).filter_by(projekt_id=p.id).delete()
            s.delete(p)
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(GalerieDatei).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.delete(k)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def gewerk_neu(self, positionen=None, sparte="WP", kfw=None, erfassung=None):
        """Projekt + Gewerk aus einem angenommenen Tool-Angebot."""
        kunde = Kunde(anrede="Herr", vorname="Paul", nachname="Projekt-V4-Test",
                      strasse="Teststr. 5", plz="47139", ort="Duisburg",
                      email=TEST_EMAIL, telefon="0203 1")
        self.s.add(kunde)
        self.s.flush()
        angebot = angebot_aufbau.angebot_anlegen(self.s, kunde.id, sparte=sparte)
        for i, (nr, menge) in enumerate(positionen or [("047", 1)], 1):
            angebot.positionen.append(AngebotsPosition(
                sort=i, pos_nr=nr, bezeichnung=f"Pos {nr}", beschreibung=f"Pos {nr}",
                menge=menge, e_preis_cent=10000))
        if kfw is not None:
            angebot.kfw_json = json.dumps(kfw)
        angebot_status_setzen(angebot, "Angenommen")
        self.s.commit()
        if erfassung is not None:
            from app.models import Erfassung
            self.s.add(Erfassung(kunde_id=kunde.id, benutzer_id=1, sparte=sparte,
                                 angebot_id=angebot.id, status="Erledigt",
                                 antworten_json=json.dumps(erfassung)))
            self.s.commit()
        projekt = kern.projekt_anlegen(self.s, angebot, projektleiter_id=1)
        gewerk = kern.gewerk_anlegen(self.s, projekt, angebot, sparte)
        self.s.commit()
        return gewerk

    def team(self):
        kern.teams_vorbelegen(self.s)
        self.s.commit()
        return self.s.query(Team).filter(Team.typ == "montage").order_by(Team.id).first()

    def aufgaben(self, gewerk, paket_key):
        instanz = (self.s.query(AufgabenpaketInstanz)
                   .filter(AufgabenpaketInstanz.gewerk_id == gewerk.id,
                           AufgabenpaketInstanz.paket_key == paket_key,
                           AufgabenpaketInstanz.deaktiviert_am.is_(None)).first())
        if instanz is None:
            return []
        return (self.s.query(Aufgabe).filter(Aufgabe.paket_instanz_id == instanz.id)
                .order_by(Aufgabe.reihenfolge).all())


# --- Phase 90 ---------------------------------------------------------------

class Phase90Board(Basis):
    def test_phasen_getrennt(self):
        from app.models import GEWERK_PHASEN, GEWERK_PHASEN_AKTIV
        self.assertNotIn("abnahme_freigabe", GEWERK_PHASEN)
        self.assertEqual(GEWERK_PHASEN_AKTIV[-2:], ["abnahme", "freigabe"])
        logik = projektierung_logik.hole_logik(self.s, erzwingen=True)
        self.assertIn("abnahme", logik.pakete)
        self.assertIn("freigabe", logik.pakete)
        self.assertEqual([s.titel for s in logik.pakete["freigabe"].schritte],
                         ["Rechnung freigegeben", "BnD nach Abnahme erstellt"])

    def test_vorlauf_ampel_und_viertelstunde(self):
        g = self.gewerk_neu()
        team = self.team()
        heute = datetime(2026, 9, 29, 10, 0)
        self.assertEqual(kern.vorlauf_ampel(self.s, g, heute=heute)["farbe"], "rot")
        self.assertEqual(kern.vorlauf_ampel(self.s, g, heute=heute)["text"], "Unterminiert")
        for tage, farbe in ((70, "gruen"), (42, "gelb"), (20, "rot")):
            self.s.query(ProjektTermin).filter_by(gewerk_id=g.id).delete()
            kern.team_termin_zuweisen(self.s, g, "wp", team.id,
                                      datetime.now() + timedelta(days=tage), None, True)
            self.assertEqual(kern.vorlauf_ampel(self.s, g)["farbe"], farbe, tage)
        self.assertIn("bis Montagebeginn", kern.vorlauf_ampel(self.s, g)["tooltip"])
        g.phase = "montage"
        self.assertIsNone(kern.vorlauf_ampel(self.s, g)["farbe"])
        g.phase = "auftragseingang"
        self.s.commit()
        v = kern.viertelstunde
        self.assertEqual(v(datetime(2026, 1, 1, 7, 52)).strftime("%H:%M"), "07:45")
        self.assertEqual(v(datetime(2026, 1, 1, 7, 53)).strftime("%H:%M"), "08:00")
        self.assertEqual(v(datetime(2026, 1, 1, 7, 37, 30)).strftime("%H:%M"), "07:45")

    def test_board_spalten_und_drop(self):
        g1 = self.gewerk_neu()
        g2 = self.gewerk_neu()
        team = self.team()
        r = self.client.get("/projektierung")
        self.assertIn("Auftragseingang · unterminiert", r.text)
        self.assertIn("Auftragseingang · terminiert", r.text)
        self.assertIn(">Freigabe <", r.text)
        # Drop „unterminiert → terminiert“ = Team + Termin, zurück zum Board
        r = self.client.post(f"/projektierung/gewerk/{g1.id}/team-termin", data={
            "zweck": "wp", "team_id": str(team.id),
            "beginn": (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d"),
            "zurueck": "/projektierung"}, follow_redirects=False)
        self.assertTrue(r.headers["location"].startswith("/projektierung?meldung="))
        self.s.expire_all()
        g1 = self.s.get(Gewerk, g1.id)
        self.assertEqual(g1.phase, "auftragseingang")          # kein Phasenwechsel
        self.assertNotEqual(kern.terminstatus(self.s, g1)["status"], "unterminiert")
        # Aufgabe „Montageteam zuweisen“ erledigt sich durch Team + Termin
        erledigt = [a for a in self.aufgaben(g1, "auftragseingang")
                    if a.titel == "Montageteam zuweisen"]
        if erledigt:
            self.assertEqual(erledigt[0].status, "erledigt")
        # Chronologische Sortierung: terminiert vor unterminiert
        zeilen = [{"gewerk": g, "terminstatus": kern.terminstatus(self.s, g)}
                  for g in (g2, g1)]
        zeilen.sort(key=kern.sortierschluessel_chrono)
        self.assertEqual(zeilen[0]["gewerk"].id, g1.id)
        kacheln = kern.startseiten_kacheln(self.s)
        self.assertIn("unterminiert", kacheln["auftragseingang"]["untertitel"])
        self.assertIn("vorlauf_rot", kacheln)
        # Liste: Vorlauf-Spalte + Filter
        r = self.client.get("/projektierung/liste?vorlauf=rot")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Vorlauf", r.text)

    def test_waechter_abnahme_freigabe_und_rechnung(self):
        g = self.gewerk_neu()
        g.phase = "abnahme"
        g.montage_fertig_am = datetime.now()
        self.s.commit()
        offen = kern.waechter_pruefen(self.s, g, "freigabe")
        self.assertTrue(any("Paket Abnahme" in o for o in offen), offen)
        for a in self.aufgaben(g, "abnahme"):
            a.status = "erledigt"
        self.s.commit()
        # die Wächter sind kumulativ – der Abnahme-Punkt ist jetzt erfüllt
        offen = kern.waechter_pruefen(self.s, g, "freigabe")
        self.assertFalse(any("Paket Abnahme" in o for o in offen), offen)
        ok, _ = kern.phase_wechseln(self.s, g, "freigabe", "Test-Override", benutzer=None)
        self.assertTrue(ok)
        ok, meldung = kern.rechnung_freigeben(self.s, g, "keine", "")
        self.assertTrue(ok, meldung)
        self.assertEqual(g.phase, "abgeschlossen")
        rechnung = [a for a in self.aufgaben(g, "freigabe")
                    if a.titel == "Rechnung freigegeben"][0]
        self.assertEqual(rechnung.status, "erledigt")
        self.s.commit()

    def test_migration_split(self):
        import migrate
        g = self.gewerk_neu()
        # Altzustand herstellen: Phase + Paket „Abnahme & Freigabe“
        for key in ("abnahme", "freigabe"):
            for inst in (self.s.query(AufgabenpaketInstanz)
                         .filter_by(gewerk_id=g.id, paket_key=key)):
                self.s.query(Aufgabe).filter_by(paket_instanz_id=inst.id).delete()
                self.s.delete(inst)
        alt = AufgabenpaketInstanz(gewerk_id=g.id, paket_key="abnahme_freigabe",
                                   paket_name="Abnahme & Freigabe")
        self.s.add(alt)
        self.s.flush()
        titel = ["Montagebericht liegt vor", "Inbetriebnahmeprotokoll liegt vor",
                 "Abnahmeprotokoll mit Kundenunterschrift",
                 "Restarbeiten/Reklamationen erfasst",
                 "Abweichungen zum Angebot geprüft, ggf. Nachtrag",
                 "Rechnung freigegeben", "BnD nach Abnahme erstellt"]
        for i, t in enumerate(titel, 1):
            self.s.add(Aufgabe(gewerk_id=g.id, projekt_id=g.projekt_id,
                               paket_instanz_id=alt.id, titel=t, pflicht=True,
                               reihenfolge=i, status="erledigt" if i <= 5 else "offen"))
        g.phase = "abnahme_freigabe"
        self.s.commit()
        migrate._v4_abnahme_freigabe_split(self.s)
        self.s.commit()
        self.assertEqual(g.phase, "freigabe")                 # 1–5 erledigt
        self.assertEqual([a.titel for a in self.aufgaben(g, "freigabe")], titel[5:])
        self.assertEqual([a.reihenfolge for a in self.aufgaben(g, "freigabe")], [1, 2])
        self.assertEqual(len(self.aufgaben(g, "abnahme")), 5)
        self.assertIsNotNone(self.s.get(AufgabenpaketInstanz, alt.id).deaktiviert_am)
        self.assertTrue(self.s.query(ProjektVerlauf).filter(
            ProjektVerlauf.gewerk_id == g.id,
            ProjektVerlauf.text.like("Phase migriert (V4%")).count())

    def test_fetch_ohne_seitensprung(self):
        g = self.gewerk_neu()
        aufgaben = [a for a in self.s.query(Aufgabe).filter_by(gewerk_id=g.id)]
        self.assertGreaterEqual(len(aufgaben), 20)
        for a in aufgaben[:20]:
            r = self.client.post(f"/projektierung/aufgabe/{a.id}/erledigt-umschalten",
                                 headers={"Accept": "application/json"})
            self.assertEqual(r.status_code, 200)
            daten = r.json()
            self.assertIn(f'id="aufgabe-{a.id}"', daten["zeile_html"])
            self.assertIn("pj-bar", daten["ampel_html"])
            self.assertTrue(daten["pakete"])
        self.s.expire_all()
        erledigt = self.s.query(Aufgabe).filter(Aufgabe.gewerk_id == g.id,
                                                Aufgabe.status == "erledigt").count()
        self.assertEqual(erledigt, 20)
        # ohne JSON-Accept weiterhin Redirect mit Anker (Fallback ohne JS)
        r = self.client.post(f"/projektierung/aufgabe/{aufgaben[0].id}/erledigt-umschalten",
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn(f"#aufgabe-{aufgaben[0].id}", r.headers["location"])
        # Akte rendert mit Partial, Vorlauf- und Planungs-Ampel
        r = self.client.get(f"/projektierung/projekt/{g.projekt_id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'id="pj-ampel-{g.id}"', r.text)
        self.assertIn(">Vorlauf<", r.text)
        self.assertIn('step="900"', r.text)

    def test_montage_fertig_mit_uhrzeit(self):
        g = self.gewerk_neu()
        team = self.team()
        kern.team_termin_zuweisen(self.s, g, "wp", team.id, datetime.now(), None, True)
        g.phase = "montage"
        self.s.commit()
        termin = self.s.query(ProjektTermin).filter_by(gewerk_id=g.id).first()
        r = self.client.post(f"/montage/einsatz/{termin.id}/phase",
                             data={"aktion": "fertig", "bericht": "alles gut",
                                   "uhrzeit": "15:52"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertEqual(g.phase, "abnahme")
        self.assertEqual(g.montage_fertig_am.strftime("%H:%M"), "15:45")


# --- Phase 91 ---------------------------------------------------------------

class Phase91Pakete(Basis):
    def test_paketinhalte(self):
        wp = self.gewerk_neu()
        titel_ae = [a.titel for a in self.aufgaben(wp, "auftragseingang")]
        self.assertEqual(titel_ae[:2], ["Kunde kontaktieren, Ablauf erklären, "
                                        "Feinplanungstermin abstimmen",
                                        "Montageteam zuweisen"])
        self.assertFalse(any(t.startswith("Auftragsunterlagen") for t in titel_ae))
        pw = self.aufgaben(wp, "planung_wp")
        self.assertTrue(pw[0].titel.startswith("Auftragsunterlagen prüfen"))
        self.assertNotIn("Montageteam zuweisen", [a.titel for a in pw])
        self.assertIn("GaLa-Beauftragung (Fundament + Erdarbeiten)", [a.titel for a in pw])
        pv = self.gewerk_neu(positionen=[("PV001", 10)], sparte="PV")
        titel_pv = [a.titel for a in self.aufgaben(pv, "auftragseingang")]
        self.assertTrue(titel_pv[-1].startswith("Auftragsunterlagen prüfen"))
        self.assertIn("Montageteam zuweisen", titel_pv)
        # Wächter AE → Feinplanung VOT verlangt jetzt die Team-Zuweisung
        offen = kern.waechter_pruefen(self.s, wp, "feinplanung_vot")
        self.assertTrue(any("Auftragseingang" in o for o in offen))

    def test_fit_for_future_steckbrief(self):
        g = self.gewerk_neu(erfassung={"P01": "Ja", "P02": "Nein", "P03": "Ja"})
        steck = kern.steckbrief_daten(self.s, [g.id])[g.id]
        self.assertEqual(steck["hems"].wert, "ja")
        fff = self.aufgaben(g, "fit_for_future")
        hems, imsys, spot, ibn = fff[:4]
        self.assertEqual((hems.aktion_typ, hems.optionen), ("auswahl", "Ja* | Nein*"))
        self.assertEqual(ibn.sichtbar_wenn, "fit_for_future.1=Ja")
        # Akte: Vorbelegung aus dem Steckbrief + „Übernehmen“, noch nicht erledigt
        r = self.client.get(f"/projektierung/projekt/{g.projekt_id}")
        self.assertIn("aus Steckbrief", r.text)
        self.assertEqual(hems.status, "offen")
        # Übernehmen „Nein“ → Steckbrief manuell „nein“, HEMS-IBN entfällt
        r = self.client.post(f"/projektierung/aufgabe/{hems.id}/auswahl",
                             data={"auswahl": "Nein"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200)
        self.s.expire_all()
        steck = kern.steckbrief_daten(self.s, [g.id])[g.id]
        self.assertEqual((steck["hems"].wert, steck["hems"].manuell), ("nein", True))
        self.assertEqual(self.s.get(Aufgabe, hems.id).status, "erledigt")
        self.assertEqual(self.s.get(Aufgabe, ibn.id).status, "entfaellt")
        ids = [w["aufgabe_id"] for w in r.json()["weitere"]]
        self.assertIn(ibn.id, ids)                             # Zeile live ersetzt
        self.client.post(f"/projektierung/aufgabe/{hems.id}/auswahl",
                         data={"auswahl": "Ja"}, headers={"Accept": "application/json"})
        self.s.expire_all()
        self.assertEqual(self.s.get(Aufgabe, ibn.id).status, "offen")
        # iMSys/SpotDynamic mit Portal-Link-Bezug
        self.assertIn("param:url_spotmyenergy", imsys.aktion_wert)
        self.assertIn("steckbrief:dyn_tarif", spot.aktion_wert)

    def test_feinplanung_neue_fragen(self):
        g = self.gewerk_neu(erfassung={"P01": "Nein", "P02": "Ja", "A07": "Nein"})
        kern.fp_vorbelegen(self.s, g)
        antworten = kern.fp_antworten(g)
        self.assertEqual((antworten.get("FP-E05"), antworten.get("FP-E06")), ("Ja", "Nein"))
        offen = kern.fp_offene_pflicht(self.s, g)
        self.assertNotIn("Restöl im Tank (Liter, geschätzt)", offen)   # FP-O01 ≠ Ja
        antworten["FP-O01"] = "Ja"
        g.fp_antworten_json = json.dumps(antworten)
        self.assertIn("Restöl im Tank (Liter, geschätzt)", kern.fp_offene_pflicht(self.s, g))
        antworten["FP-O04"] = "400"
        g.fp_antworten_json = json.dumps(antworten)
        kern.steckbrief_ableiten(self.s, g, fp_antworten=antworten)
        steck = kern.steckbrief_daten(self.s, [g.id])[g.id]
        self.assertEqual(steck["imsys"].wert, "ja")
        self.assertEqual(steck["hems"].wert, "nein")
        self.assertEqual(steck["restoel_liter"].wert, "400")
        self.s.commit()

    def test_sub_mails_restoel_stemm_erd(self):
        from app import projektierung_logik as pl
        logik = pl.hole_logik(self.s)
        g = self.gewerk_neu(positionen=[("047", 1), ("126", 1), ("102", 5)],
                            erfassung={"A07": "Ja", "A08": "Stahl", "A09": "bis 3.000 L"})
        kern.steckbrief_ableiten(self.s, g, fp_antworten={"FP-O01": "Ja",
                                                          "FP-O04": "400"})
        steck = kern.steckbrief_daten(self.s, [g.id])[g.id]
        self.assertEqual(steck["stemmarbeiten"].wert, "ja (Pos. 126, Menge 1)")
        self.assertEqual(steck["erdleitung_m"].wert, "5 m (Pos. 102 Erdleitung)")
        daten = kern.sub_mail_platzhalter(self.s, g)
        self.assertEqual(daten["restoel"], "Restöl ca. 400 l")
        self.assertIn("Stemmarbeiten sind laut Angebot enthalten", daten["stemmarbeiten"])
        self.assertIn("Leitungsgraben ca. 5 m", daten["erdarbeiten"])
        entsorgung = kern.sub_mail_text(logik.sub_vorlagen["Entsorgung"].text, daten)
        gala = kern.sub_mail_text(logik.sub_vorlagen["GaLa-Bau"].text, daten)
        self.assertIn("Restöl ca. 400 l", entsorgung)
        self.assertIn("Pos. 126", entsorgung)
        self.assertIn("Leitungsgraben ca. 5 m", gala)
        # ohne Positionen → „nicht“-Varianten
        leer = self.gewerk_neu()
        daten = kern.sub_mail_platzhalter(self.s, leer)
        self.assertEqual(daten["restoel"], "kein Restöl angegeben")
        self.assertEqual(daten["stemmarbeiten"], "Stemmarbeiten nicht Teil des Auftrags")
        self.assertEqual(daten["erdarbeiten"], "keine Erdarbeiten laut Auftrag")
        self.assertEqual(kern.steckbrief_daten(self.s, [leer.id])[leer.id]["stemmarbeiten"].wert,
                         "nein")
        # Steckbrief-PDF zeigt die neuen Felder
        import io

        import pypdf

        from app.steckbrief_pdf import steckbrief_pdf_bytes
        text = "\n".join(s.extract_text() for s in pypdf.PdfReader(
            io.BytesIO(steckbrief_pdf_bytes(self.s, g))).pages)
        self.assertIn("Restöl", text)
        self.assertIn("Stemmarbeiten", text)

    def test_migration_pakete(self):
        import migrate
        g = self.gewerk_neu()
        ae = [a for a in self.aufgaben(g, "auftragseingang")]
        pw = [a for a in self.aufgaben(g, "planung_wp")]
        ae_inst, pw_inst = ae[0].paket_instanz_id, pw[0].paket_instanz_id
        # Altstand herstellen: Unterlagen im AE, Team in Planung WP, FfF als Link
        unterlagen = pw[0]
        unterlagen.paket_instanz_id, unterlagen.reihenfolge = ae_inst, 1
        team = [a for a in ae if a.titel == "Montageteam zuweisen"][0]
        team.paket_instanz_id, team.reihenfolge, team.status = pw_inst, 1, "erledigt"
        for a in self.aufgaben(g, "fit_for_future")[1:3]:
            a.aktion_typ, a.aktion_wert, a.optionen = "link", "param:url_spotmyenergy", ""
        self.s.commit()
        migrate._v4_pakete_umbauen(self.s)
        self.s.commit()
        self.assertEqual(self.s.get(Aufgabe, unterlagen.id).paket_instanz_id, pw_inst)
        self.assertEqual(self.s.get(Aufgabe, unterlagen.id).reihenfolge, 1)
        self.assertEqual(self.s.get(Aufgabe, team.id).paket_instanz_id, ae_inst)
        self.assertEqual(self.s.get(Aufgabe, team.id).status, "erledigt")   # Status bleibt
        self.assertTrue(all(a.aktion_typ == "auswahl"
                            for a in self.aufgaben(g, "fit_for_future")[:3]))
