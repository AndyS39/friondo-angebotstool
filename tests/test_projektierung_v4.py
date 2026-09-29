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
                from app.models import UglBestellung
                s.query(UglBestellung).filter_by(gewerk_id=g.id).delete()
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


# --- Phase 92 ---------------------------------------------------------------

class Phase92Bza(Basis):
    def gefoerdert(self):
        from app import konfigurator as engine
        from tests.test_regression import KONTROLL_SZENARIO
        return self.gewerk_neu(positionen=[("047", 1)],
                               kfw=engine.kfw_daten(dict(KONTROLL_SZENARIO)))

    def bza_aufgabe(self, g):
        return [a for a in self.aufgaben(g, "auftragseingang") if a.aktion_typ == "bza"][0]

    def test_bza_erfassen_mail_und_kfw(self):
        from unittest import mock

        from app import bza as bza_modul
        from app.models import GalerieDatei, ProjektMail
        g = self.gefoerdert()
        self.assertTrue(bza_modul.ist_gefoerdert(self.s, g))
        betrag = bza_modul.foerderbetrag_cent(self.s, g)
        self.assertTrue(betrag and betrag > 0)
        aufgabe = self.bza_aufgabe(g)
        self.assertEqual(aufgabe.titel, "BzA erstellen und an Kunden senden")
        r = self.client.get(f"/projektierung/projekt/{g.projekt_id}")
        for text in ("BzA-Portal ↗", "📋 Datenblatt", "BzA erfassen"):
            self.assertIn(text, r.text)
        # Pflichtprüfung: ohne PDF kein Speichern
        r = self.client.post(f"/projektierung/gewerk/{g.id}/bza-erfassen",
                             data={"bza_id": "BZA-4711"}, follow_redirects=False)
        self.assertIn("PDF", r.headers["location"].encode().decode())
        r = self.client.post(f"/projektierung/gewerk/{g.id}/bza-erfassen",
                             data={"bza_id": "BZA-4711", "datum": "2026-09-29",
                                   "sofort_senden": "on"},
                             files={"datei": ("bza.pdf", b"%PDF-1.4 Test-BzA", "application/pdf")},
                             follow_redirects=False)
        self.assertEqual(r.headers["location"], f"/projektierung/gewerk/{g.id}/bza-mail")
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertEqual(g.bza_id, "BZA-4711")
        datei = self.s.get(GalerieDatei, g.bza_datei_id)
        self.assertEqual(datei.ordner, "Förderung")
        # Vorschau: ID, Betrag, KfW-Link; Demo-Modus ohne Test-Adresse → gesperrt
        kern.parameter_setzen(self.s, "projekt_testadresse", "")
        kern.parameter_setzen(self.s, "url_kfw_zuschussportal", "https://kfw.test/zuschuss")
        self.s.commit()
        r = self.client.get(f"/projektierung/gewerk/{g.id}/bza-mail")
        self.assertIn("BZA-4711", r.text)
        self.assertIn("https://kfw.test/zuschuss", r.text)
        self.assertIn("vor Beginn der Arbeiten", r.text)
        from app.templating import euro
        self.assertIn(euro(betrag), r.text)
        modus = kern.freigabe_modus(self.s)
        if modus == "admin":
            self.assertIn("keine Test-Adresse", r.text)
            kern.parameter_setzen(self.s, "projekt_testadresse", "test@friondo.test")
            self.s.commit()
        with mock.patch("app.graph_versand.mail_mit_anhaengen_senden",
                        return_value=(True, "", "konv-1")) as senden:
            r = self.client.post(f"/projektierung/gewerk/{g.id}/bza-mail",
                                 data={"betreff": "BzA Test", "text": "Hallo BZA-4711"},
                                 follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        empfaenger, betreff, text, anhaenge = senden.call_args.args[:4]
        self.assertEqual(empfaenger, "test@friondo.test" if modus == "admin" else TEST_EMAIL)
        self.assertEqual(anhaenge[0][2], "application/pdf")
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertIsNotNone(g.bza_gesendet_am)
        self.assertEqual(self.s.get(Aufgabe, aufgabe.id).status, "erledigt")
        self.assertTrue(self.s.query(ProjektMail).filter(
            ProjektMail.projekt_id == g.projekt_id, ProjektMail.betreff == "BzA Test").count())
        kern.parameter_setzen(self.s, "projekt_testadresse", "")
        kern.parameter_setzen(self.s, "url_kfw_zuschussportal", "")
        self.s.commit()
        # KfW-Antragsnummer/Zusage (Montagevorbereitung, nicht Pflicht)
        kfw_aufgabe = [a for a in self.aufgaben(g, "montagevorbereitung")
                       if a.aktion_wert == "kfw"][0]
        self.assertFalse(kfw_aufgabe.pflicht)
        r = self.client.post(f"/projektierung/gewerk/{g.id}/kfw",
                             data={"kfw_antragsnummer": "KFW-123", "kfw_zusage_am": "2026-10-05",
                                   "aufgabe_id": str(kfw_aufgabe.id)},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200)
        self.s.expire_all()
        self.assertEqual(self.s.get(Aufgabe, kfw_aufgabe.id).status, "erledigt")
        # Anzeige: Steckbrief-Block, Datenblatt, Steckbrief-PDF
        r = self.client.get(f"/projektierung/projekt/{g.projekt_id}")
        self.assertIn("KFW-123", r.text)
        r = self.client.get(f"/projektierung/gewerk/{g.id}/bza")
        self.assertIn("Stand BzA / KfW", r.text)
        self.assertIn("BZA-4711", r.text)
        import io

        import pypdf

        from app.steckbrief_pdf import steckbrief_pdf_bytes
        text = "\n".join(s.extract_text() for s in pypdf.PdfReader(io.BytesIO(
            steckbrief_pdf_bytes(self.s, self.s.get(Gewerk, g.id)))).pages)
        self.assertIn("BZA-4711", text)
        self.assertIn("KFW-123", text)

    def test_ungefoerdert_entfaellt(self):
        from app import bza as bza_modul
        from app.routers.projektierung import _aufgabe_zeile_html
        g = self.gewerk_neu()               # Angebot ohne KfW-Daten
        self.assertIs(bza_modul.ist_gefoerdert(self.s, g), False)
        zeile = _aufgabe_zeile_html(self.s, self.bza_aufgabe(g))
        self.assertIn("entfällt (nicht gefördert)", zeile)
        self.assertNotIn("dlg-bza-", zeile)
        # Portal-URL fehlt → Hinweis-Button zu den Einstellungen (gefördert)
        g2 = self.gefoerdert()
        kern.parameter_setzen(self.s, "url_bza_portal", "")
        self.s.commit()
        zeile = _aufgabe_zeile_html(self.s, self.bza_aufgabe(g2))
        self.assertIn("/parametrierung/projektierung-einstellungen", zeile)
        self.assertNotIn('name="status" value="entfaellt"', zeile)   # kein Entfällt-Knopf


# --- Phase 93 ---------------------------------------------------------------

class _Antwort:
    """Minimaler Ersatz für urlopen()-Antworten."""
    def __init__(self, status, daten):
        self.status = status
        self._roh = json.dumps(daten).encode()

    def read(self):
        return self._roh

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Phase93Heizreport(Basis):
    PARAMETER = {"heizreport_api_url": "https://heizreport.test/api/",
                 "heizreport_auth_art": "body", "heizreport_auth_header": "apiKey",
                 "heizreport_api_key": "geheim-123",
                 "heizreport_mapping_zurueck": json.dumps(
                     {"projekt_key": "projektKey", "heizlast_kw": "ergebnis.heizlast"})}

    def setUp(self):
        from app import heizreport_api
        self.alt = {n: kern.parameter_holen(self.s, n, "") for n in heizreport_api.PARAMETER}

    def tearDown(self):
        for name, wert in self.alt.items():
            kern.parameter_setzen(self.s, name, wert)
        self.s.commit()

    def heizlast_aufgabe(self, g):
        return [a for a in self.aufgaben(g, "feinplanung_vot")
                if a.aktion_wert == "heizreport"][0]

    def test_ohne_konfiguration_link_und_upload(self):
        from app.routers.projektierung import _aufgabe_zeile_html
        kern.parameter_setzen(self.s, "heizreport_api_url", "")
        self.s.commit()
        g = self.gewerk_neu()
        zeile = _aufgabe_zeile_html(self.s, self.heizlast_aufgabe(g))
        self.assertIn("API nicht konfiguriert", zeile)
        self.assertNotIn("Projekt im Heizreport anlegen", zeile)

    def test_anlegen_ergebnis_und_verbindungstest(self):
        import urllib.error
        from unittest import mock

        from app.routers.projektierung import _aufgabe_zeile_html
        for name, wert in self.PARAMETER.items():
            kern.parameter_setzen(self.s, name, wert)
        self.s.commit()
        g = self.gewerk_neu()
        aufgabe = self.heizlast_aufgabe(g)
        self.assertIn("Projekt im Heizreport anlegen", _aufgabe_zeile_html(self.s, aufgabe))
        gesendet = []

        def urlopen(anfrage, timeout=None):
            gesendet.append((anfrage.full_url, anfrage.get_method(),
                             json.loads(anfrage.data or b"{}")))
            if len(gesendet) == 1:
                return _Antwort(200, {"projektKey": "123456789"})
            return _Antwort(200, {"ergebnis": {"heizlast": "9,4"}})
        with mock.patch("urllib.request.urlopen", side_effect=urlopen):
            r = self.client.post(f"/projektierung/gewerk/{g.id}/heizreport/anlegen",
                                 data={"aufgabe_id": str(aufgabe.id)},
                                 headers={"Accept": "application/json"})
            self.assertEqual(r.status_code, 200)
            self.assertIn("123456789", r.json()["meldung"])
            r = self.client.post(f"/projektierung/gewerk/{g.id}/heizreport/ergebnis",
                                 follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        # Auth im Body, Mapping hin mit Adresse
        url, methode, koerper = gesendet[0]
        self.assertEqual((url, methode), ("https://heizreport.test/api/", "POST"))
        self.assertEqual(koerper["apiKey"], "geheim-123")
        self.assertEqual(koerper["projekt"]["name"], self.s.get(Projekt, g.projekt_id).nummer)
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertEqual(g.heizreport_projekt_key, "123456789")
        self.assertAlmostEqual(g.heizlast_kw, 9.4)
        self.assertEqual(g.heizlast_quelle, "Heizreport API")
        self.assertEqual(self.s.get(Aufgabe, aufgabe.id).status, "erledigt")
        r = self.client.get(f"/projektierung/projekt/{g.projekt_id}")
        self.assertIn("Quelle Heizreport API", r.text)
        # Verbindungstest: HTTP-Code landet in der Meldung
        fehler = urllib.error.HTTPError("https://heizreport.test/api/", 400, "Bad", {}, None)
        fehler.read = lambda: "kein JSON Object empfangen".encode()
        with mock.patch("urllib.request.urlopen", side_effect=fehler):
            r = self.client.post("/parametrierung/projektierung-einstellungen/heizreport-test",
                                 data={"heizreport_api_url": "https://heizreport.test/api/",
                                       "heizreport_auth_art": "body"})
        self.assertIn("HTTP 400", r.text)
        self.assertIn("kein JSON Object", r.text)
        # Schlüssel bleibt beim Speichern mit leerem Feld erhalten
        self.assertEqual(kern.parameter_holen(self.s, "heizreport_api_key", ""), "geheim-123")


class Phase93Ugl(Basis):
    def test_satzformat(self):
        from app import ugl
        kop = ugl.kop_satz("12345", "L9", "PR-2026-0001-2", "Kommission",
                           datetime(2026, 10, 5), "Admin", datetime(2026, 9, 29))
        poa = ugl.poa_satz(10, "ART-1", 12.5, "Kupferrohr", "", "m")
        pot = ugl.pot_satz(10, "Angebotsposition 047")
        adr = ugl.adr_satz("Baustelle Müller", "Kommission", "", "Weg 1", "41836", "Hückelhoven")
        end = ugl.end_satz("Bestellung")
        for satz in (kop, poa, pot, adr, end):
            self.assertEqual(len(satz), 200)
        self.assertEqual(kop[0:3], "KOP")
        self.assertEqual(kop[3:13], "12345     ")
        self.assertEqual(kop[13:23], "L9        ")
        self.assertEqual(kop[23:25], "BE")
        self.assertEqual(kop[25:40].strip(), "PR-2026-0001-2")
        self.assertEqual(kop[105:113], "20261005")
        self.assertEqual(kop[113:121], "EUR04.00")
        self.assertEqual(kop[161:169], "20260929")
        self.assertEqual(poa[3:13], "0000000010")
        self.assertEqual(poa[23:38], "ART-1          ")
        self.assertEqual(poa[38:49], "00000012500")
        self.assertEqual(poa[181], "H")
        self.assertEqual(poa[183:186], "M  ")
        self.assertEqual(pot[23:63].strip(), "Angebotsposition 047")
        self.assertEqual(adr[126:132], "41836 ")
        self.assertEqual(adr[132:162].strip(), "Hückelhoven")
        self.assertEqual("ü".encode(ugl.ZEICHENSATZ), bytes([0x81]))
        with open("docs/ugl-beispiel.ugl", "rb") as datei:
            zeilen = datei.read().split(bytes([13, 10]))
        self.assertEqual(zeilen[-1], b"")
        self.assertTrue(all(len(z) == 200 for z in zeilen[:-1]))
        self.assertEqual([z[:3] for z in zeilen[:3]], [b"KOP", b"ADR", b"POA"])

    def test_bestellung_nachbestellung_hochgeladen(self):
        from app import ugl
        from app.models import UglBestellung
        alt = kern.parameter_holen(self.s, "collin_kundennummer", "")
        kern.parameter_setzen(self.s, "collin_kundennummer", "0000123456")
        self.s.commit()
        try:
            g = self.gewerk_neu(positionen=[("047", 2), ("998", 1)])
            r = self.client.get(f"/projektierung/gewerk/{g.id}/ugl")
            self.assertIn("998 · Pos 998", r.text)
            self.assertIn("/parametrierung/stuecklisten?pos=998", r.text)
            r = self.client.post(f"/projektierung/gewerk/{g.id}/ugl",
                                 data={"lieferdatum": "2026-10-12", "lieferadresse": "lager",
                                       "bemerkung": "Kran vor Ort"})
            self.assertEqual(r.status_code, 200)
            projekt = self.s.get(Projekt, g.projekt_id)
            self.assertIn(f'filename="{projekt.nummer}.ugl"', r.headers["content-disposition"])
            text = r.content.decode(ugl.ZEICHENSATZ)
            saetze = text.split("\r\n")
            self.assertEqual(saetze[0][105:113], "20261012")
            self.assertIn("Kran vor Ort", text)
            # 047 × 2: Dämpfer-Set 2 je Einheit → 4
            daempfer = [z for z in saetze if z.startswith("POA") and "BEISPIEL-108001" in z][0]
            self.assertEqual(daempfer[38:49], "00000004000")
            r = self.client.post(f"/projektierung/gewerk/{g.id}/ugl", data={})
            self.assertIn(f'filename="{projekt.nummer}-2.ugl"', r.headers["content-disposition"])
            self.assertIn("Nachbestellung", r.content.decode(ugl.ZEICHENSATZ))
            self.s.expire_all()
            bestellungen = (self.s.query(UglBestellung).filter_by(gewerk_id=g.id)
                            .order_by(UglBestellung.nr).all())
            self.assertEqual([b.nr for b in bestellungen], [1, 2])
            self.assertEqual(bestellungen[0].lieferadresse, "lager")
            aufgabe = [a for a in self.aufgaben(g, "planung_wp")
                       if a.aktion_wert == "ugl_collin"][0]
            self.assertEqual(aufgabe.status, "in_arbeit")
            self.client.post(f"/projektierung/gewerk/{g.id}/ugl/{bestellungen[0].id}/hochgeladen",
                             data={"datum": "2026-09-30"})
            self.s.expire_all()
            self.assertEqual(self.s.get(Aufgabe, aufgabe.id).status, "erledigt")
            self.assertEqual(self.s.get(UglBestellung, bestellungen[0].id).hochgeladen_am,
                             datetime(2026, 9, 30))
            self.assertTrue(self.s.query(ProjektVerlauf).filter(
                ProjektVerlauf.projekt_id == g.projekt_id,
                ProjektVerlauf.text.like("UGL-Nachbestellung 2%")).count())
            r = self.client.get(f"/projektierung/gewerk/{g.id}/ugl")
            self.assertIn("Nachbestellung 3", r.text)
        finally:
            kern.parameter_setzen(self.s, "collin_kundennummer", alt)
            self.s.commit()

    def test_stuecklisten_pflege(self):
        import shutil
        import tempfile
        from pathlib import Path
        from unittest import mock

        from app import config, stuecklisten
        ordner = Path(tempfile.mkdtemp())
        kopie = ordner / "logik.xlsx"
        shutil.copyfile(projektierung_logik.LOGIK_PFAD, kopie)
        try:
            with mock.patch.object(projektierung_logik, "LOGIK_PFAD", kopie), \
                    mock.patch.object(config, "BACKUP_ORDNER", ordner / "backup"):
                projektierung_logik.hole_logik(self.s, erzwingen=True)
                _vorher, gesamt = stuecklisten.fortschritt(self.s)
                self.assertGreater(gesamt, 0)
                r = self.client.post("/parametrierung/stuecklisten/998",
                                     data={"anzahl": "3",
                                           "artnr_0": "COL-4711", "menge_0": "2,5",
                                           "bezeichnung_0": "Kabel", "lieferant_0": "Collin",
                                           "einheit_0": "m", "artnr_1": "", "artnr_2": ""},
                                     follow_redirects=False)
                self.assertIn("pos=998", r.headers["location"])
                logik = projektierung_logik.hole_logik(self.s)
                zeile = logik.stuecklisten["998"][0]
                self.assertEqual((zeile.lieferant_artnr, zeile.menge_je_einheit,
                                  zeile.mengeneinheit), ("COL-4711", 2.5, "M"))
                self.assertTrue(list((ordner / "backup").glob("projektierung_logik_*.xlsx")))
                # übrige Blätter unverändert lesbar
                self.assertFalse(logik.fehler)
                self.assertIn("abnahme", logik.pakete)
                r = self.client.get("/parametrierung/stuecklisten?ohne=1")
                self.assertIn("Go-live-Prüfpunkte", r.text)
                self.assertNotIn('id="pos-998"', r.text)
                csv_text = self.client.get("/parametrierung/stuecklisten/export.csv").text
                self.assertIn("998;COL-4711;2,5;Kabel;Collin;M", csv_text)
                # Import ersetzt das Blatt
                neu = ("position;lieferant_artnr;menge_je_einheit;bezeichnung;lieferant;"
                       "mengeneinheit\n047;X-1;1;Test;Collin;ST\n")
                r = self.client.post("/parametrierung/stuecklisten/import",
                                     files={"datei": ("s.csv", neu.encode("utf-8"), "text/csv")})
                self.assertIn("1 Stücklisten-Zeilen importiert", r.text)
                self.assertEqual(list(projektierung_logik.hole_logik(self.s).stuecklisten),
                                 ["047"])
                # Zuordnung entfernen (leere Artikelnummer)
                self.client.post("/parametrierung/stuecklisten/047",
                                 data={"anzahl": "1", "artnr_0": ""})
                self.assertEqual(projektierung_logik.hole_logik(self.s).stuecklisten, {})
        finally:
            projektierung_logik.hole_logik(self.s, erzwingen=True)
            shutil.rmtree(ordner, ignore_errors=True)
