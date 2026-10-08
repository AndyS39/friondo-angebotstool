# v28 (PLAN_PROJ_V6 Phase 133): Wächter „warnen“ / „sperren“, Aufgabe „entfällt“
# mit Grund, Bedingungen steckbrief:/foerderung: in der Live-Excel, JSON-Route
# GET /projektierung/gewerk/{id}/waechter. Läuft gegen die Entwicklungs-DB
# (DB_PFAD_OVERRIDE) und räumt die Testdaten (Kunde „V28P1-Waechter“) auf.
import json
import unittest
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau
from app import projektierung as kern
from app import projektierung_logik
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Aufgabe, AufgabenpaketInstanz,
                        Gewerk, Kunde, Projekt, ProjektTermin, ProjektVerlauf,
                        SteckbriefWert, TerminBesetzung, Vorgang, angebot_status_setzen)

TEST_EMAIL = "v28p1-waechter@test.local"


def aufraeumen(s):
    from app.models import Erfassung, GalerieDatei, ProjektMail, VorgangsNotiz
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for p in s.query(Projekt).filter_by(kunde_id=k.id):
            for g in s.query(Gewerk).filter_by(projekt_id=p.id):
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
    s.commit()


def parameter(name, wert):
    """Parameter über eine frische Sitzung schreiben (Briefing-Regel)."""
    s = SessionLocal()
    try:
        alt = kern.parameter_holen(s, name, "")
        kern.parameter_setzen(s, name, wert)
        s.commit()
        return alt
    finally:
        s.close()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        cls.modus_alt = parameter("waechter_modus", "warnen")

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        parameter("waechter_modus", cls.modus_alt or "warnen")
        cls.s.close()

    def setUp(self):
        parameter("waechter_modus", "warnen")
        self.s.expire_all()

    def gewerk_neu(self, positionen=None, sparte="WP", kfw=None, erfassung=None,
                   ausblenden=False):
        kunde = Kunde(anrede="Herr", vorname="Walter", nachname="V28P1-Waechter",
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
        angebot.foerderung_ausblenden = ausblenden
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

    def aufgaben(self, gewerk, paket_key):
        instanz = (self.s.query(AufgabenpaketInstanz)
                   .filter(AufgabenpaketInstanz.gewerk_id == gewerk.id,
                           AufgabenpaketInstanz.paket_key == paket_key,
                           AufgabenpaketInstanz.deaktiviert_am.is_(None)).first())
        if instanz is None:
            return []
        return (self.s.query(Aufgabe).filter(Aufgabe.paket_instanz_id == instanz.id)
                .order_by(Aufgabe.reihenfolge).all())

    def aufgabe(self, gewerk, titel):
        return (self.s.query(Aufgabe)
                .filter(Aufgabe.gewerk_id == gewerk.id, Aufgabe.titel == titel).first())

    def verlauf_texte(self, gewerk):
        return [v.text for v in self.s.query(ProjektVerlauf)
                .filter(ProjektVerlauf.gewerk_id == gewerk.id)
                .order_by(ProjektVerlauf.id)]

    def planung_mit_drei_offenen(self):
        """Gewerk in Phase planung, Planungs-Pakete bis auf drei Pflichtaufgaben erledigt."""
        g = self.gewerk_neu()
        g.phase = "planung"
        g.feinplanung_erfasst = True
        for key in ("auftragseingang", "feinplanung_vot"):
            for a in self.aufgaben(g, key):
                a.status = "erledigt"
        offen = []
        for key in ("planung_wp", "planung_elektro", "fit_for_future"):
            for a in self.aufgaben(g, key):
                if a.pflicht and len(offen) < 3:
                    offen.append(a)
                else:
                    a.status = "erledigt"
        self.s.commit()
        self.assertEqual(len(offen), 3)
        return g, offen


class WaechterModus(Basis):
    def test_warnen_laesst_wechsel_zu_und_vermerkt(self):
        g, offen = self.planung_mit_drei_offenen()
        self.assertEqual(kern.waechter_modus(self.s), "warnen")
        ok, meldung = kern.phase_wechseln(self.s, g, "montagevorbereitung", "")
        self.assertTrue(ok, meldung)
        self.assertEqual(g.phase, "montagevorbereitung")
        texte = self.verlauf_texte(g)
        self.assertTrue(any("mit offenen Punkten: Planungs-Pakete: 3 von" in t for t in texte),
                        texte)
        self.assertFalse(any("trotz offener Punkte" in t for t in texte))
        # Rückwärts ohne Begründung bleibt gesperrt – mit Begründung erlaubt
        ok, meldung = kern.phase_wechseln(self.s, g, "planung", "")
        self.assertFalse(ok)
        self.assertIn("Rückwärts-Wechsel nur mit Begründung", meldung)
        ok, _ = kern.phase_wechseln(self.s, g, "planung", "Kunde hat Material storniert")
        self.assertTrue(ok)
        # Begründung im Modus warnen wird mitprotokolliert
        ok, _ = kern.phase_wechseln(self.s, g, "montagevorbereitung", "Material kommt")
        self.assertTrue(ok)
        self.assertTrue(any("mit offenen Punkten" in t and "Begründung: Material kommt" in t
                            for t in self.verlauf_texte(g)))
        self.s.commit()

    def test_sperren_wie_bisher(self):
        g, offen = self.planung_mit_drei_offenen()
        parameter("waechter_modus", "sperren")
        self.assertEqual(kern.waechter_modus(self.s), "sperren")
        ok, meldung = kern.phase_wechseln(self.s, g, "montagevorbereitung", "")
        self.assertFalse(ok)
        self.assertTrue(meldung.startswith("Wächter: "), meldung)
        self.assertIn("Override nur mit Begründung", meldung)
        self.assertEqual(g.phase, "planung")
        ok, _ = kern.phase_wechseln(self.s, g, "montagevorbereitung", "Override Test")
        self.assertTrue(ok)
        self.assertTrue(any("trotz offener Punkte: Override Test" in t
                            for t in self.verlauf_texte(g)))
        ok, meldung = kern.phase_wechseln(self.s, g, "planung", "")
        self.assertFalse(ok)
        self.s.commit()

    def test_abgeschlossen_nur_ueber_rechnung(self):
        g = self.gewerk_neu()
        g.phase = "freigabe"
        g.montage_fertig_am = datetime.now()
        self.s.commit()
        for modus in ("warnen", "sperren"):
            parameter("waechter_modus", modus)
            ok, meldung = kern.phase_wechseln(self.s, g, "abgeschlossen", "Begründung egal")
            self.assertFalse(ok, modus)
            self.assertIn("Rechnung freigeben", meldung)
        ok, _ = kern.rechnung_freigeben(self.s, g, "keine", "")
        self.assertTrue(ok)
        self.assertEqual(g.phase, "abgeschlossen")
        self.s.commit()

    def test_waechter_json_route(self):
        g, offen = self.planung_mit_drei_offenen()
        r = self.client.get(f"/projektierung/gewerk/{g.id}/waechter?ziel=montage")
        self.assertEqual(r.status_code, 200)
        daten = r.json()
        self.assertEqual(daten["modus"], "warnen")
        self.assertFalse(daten["rueckwaerts"])
        self.assertFalse(daten["begruendung_pflicht"])
        ids = {p["aufgabe_id"] for p in daten["offen"] if p["aufgabe_id"]}
        self.assertTrue({a.id for a in offen} <= ids)
        self.assertTrue(all("text" in p and "pflicht" in p for p in daten["offen"]))
        self.assertTrue(any(p["aufgabe_id"] is None for p in daten["offen"]))   # Termin fehlt
        self.assertIn("blockieren nicht", daten["hinweis"])
        parameter("waechter_modus", "sperren")
        daten = self.client.get(f"/projektierung/gewerk/{g.id}/waechter?ziel=montage").json()
        self.assertEqual(daten["modus"], "sperren")
        self.assertTrue(daten["begruendung_pflicht"])
        # rückwärts: Begründung Pflicht in beiden Modi
        parameter("waechter_modus", "warnen")
        daten = self.client.get(f"/projektierung/gewerk/{g.id}/waechter?ziel=auftragseingang").json()
        self.assertTrue(daten["rueckwaerts"])
        self.assertTrue(daten["begruendung_pflicht"])
        self.assertEqual(daten["offen"], [])
        r = self.client.get(f"/projektierung/gewerk/{g.id}/waechter?ziel=unsinn")
        self.assertEqual(r.status_code, 400)

    def test_phase_dialog_in_akte(self):
        g = self.gewerk_neu()
        r = self.client.get(f"/projektierung/projekt/{g.projekt_id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'id="dlg-phase-{g.id}"', r.text)
        self.assertIn("data-offen", r.text)
        self.assertIn('placeholder="optional"', r.text)
        self.assertIn("blockieren nicht", r.text)


class Entfaellt(Basis):
    def test_route_entfaellt_und_wieder_aufnehmen(self):
        g = self.gewerk_neu()
        a = self.aufgabe(g, "Auftrag in TAIFUN anlegen")
        r = self.client.post(f"/projektierung/aufgabe/{a.id}/entfaellt", data={"grund": ""},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["meldung"], "Bitte einen Grund angeben.")
        r = self.client.post(f"/projektierung/aufgabe/{a.id}/entfaellt",
                             data={"grund": "Auftrag läuft über TAIFUN-Import"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200)
        daten = r.json()
        self.assertTrue(daten["ok"])
        self.assertIn("entfällt · Auftrag läuft über", daten["zeile_html"])
        self.assertIn("wieder aufnehmen", daten["zeile_html"])
        self.s.expire_all()
        a = self.s.get(Aufgabe, a.id)
        self.assertEqual(a.status, "entfaellt")
        self.assertEqual(a.entfaellt_grund, "Auftrag läuft über TAIFUN-Import")
        self.assertIsNotNone(a.erledigt_am)
        self.assertEqual(a.erledigt_von, 1)
        self.assertTrue(any("entfällt – Auftrag läuft über TAIFUN-Import" in t
                            for t in self.verlauf_texte(g)))
        # zählt nicht mehr als offen (Wächter AE → FP)
        offen = kern.waechter_pruefen(self.s, g, "feinplanung_vot")
        self.assertFalse(any("4 von 4" in o for o in offen), offen)
        ampel = kern.planungs_ampel(self.s, g)
        self.assertNotIn(a.id, [x.id for x in self.s.query(Aufgabe)
                                .filter(Aufgabe.gewerk_id == g.id, Aufgabe.pflicht.is_(True),
                                        Aufgabe.status != "entfaellt")])
        self.assertGreater(ampel["gesamt"], 0)
        r = self.client.post(f"/projektierung/aufgabe/{a.id}/wieder-aufnehmen",
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200)
        self.s.expire_all()
        a = self.s.get(Aufgabe, a.id)
        self.assertEqual((a.status, a.entfaellt_grund, a.erledigt_am), ("offen", "", None))
        self.assertTrue(any("wieder aufgenommen" in t for t in self.verlauf_texte(g)))
        # klassischer POST ohne Grund → Redirect mit Meldung
        r = self.client.post(f"/projektierung/aufgabe/{a.id}/entfaellt", data={"grund": ""},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Grund", r.headers["location"])

    def test_auswahl_ohne_stern_traegt_grund(self):
        g = self.gewerk_neu()
        a = [x for x in self.aufgaben(g, "planung_wp") if x.aktion_typ == "auswahl"][0]
        option_ohne = next(t for t, erledigt in
                           projektierung_logik.PaketSchritt(
                               nr=1, titel="", beschreibung="", rolle="projektierer",
                               pflicht=True, faellig_regel="", wartet_frist_tage=None,
                               optionen=a.optionen).optionen_liste() if not erledigt)
        self.assertTrue(kern.aufgabe_auswahl_setzen(self.s, a, option_ohne))
        self.assertEqual((a.status, a.entfaellt_grund), ("entfaellt", option_ohne))
        self.assertTrue(kern.aufgabe_auswahl_setzen(self.s, a, ""))
        self.assertEqual((a.status, a.entfaellt_grund), ("offen", ""))
        self.s.commit()

    def test_status_dropdown_entfaellt_mit_grund(self):
        g = self.gewerk_neu()
        a = self.aufgabe(g, "Auftrag in TAIFUN anlegen")
        r = self.client.post(f"/projektierung/aufgabe/{a.id}/status",
                             data={"status": "entfaellt", "grund": "nicht nötig"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200)
        self.s.expire_all()
        self.assertEqual(self.s.get(Aufgabe, a.id).entfaellt_grund, "nicht nötig")
        r = self.client.post(f"/projektierung/aufgabe/{a.id}/status",
                             data={"status": "offen"}, headers={"Accept": "application/json"})
        self.s.expire_all()
        self.assertEqual(self.s.get(Aufgabe, a.id).entfaellt_grund, "")

    def test_meine_aufgaben_zeigt_entfaellt_knopf(self):
        g = self.gewerk_neu()
        r = self.client.get("/projektierung/meine-aufgaben")
        self.assertEqual(r.status_code, 200)
        self.assertIn("/entfaellt?zurueck=/projektierung/meine-aufgaben", r.text)
        self.assertIn('main class="breit pj-voll"', r.text)


class Bedingungen(Basis):
    def test_oeltank_steckbrief_bedingung(self):
        g = self.gewerk_neu(erfassung={"A07": "Ja"})
        steck = kern.steckbrief_daten(self.s, [g.id])[g.id]
        self.assertEqual(steck["oeltank"].wert, "ja")
        a = self.aufgabe(g, "Öltank-Entsorgung")
        self.assertIsNotNone(a)
        self.assertEqual(a.status, "offen")
        self.assertEqual(a.sichtbar_wenn, "steckbrief:oeltank=ja")   # v28: gespeichert
        steck["oeltank"].wert = "nein"
        steck["oeltank"].manuell = True
        self.s.flush()
        ergebnis = kern.bedingungen_nachziehen(self.s, g)
        self.assertEqual(ergebnis["entfaellt"], 1)
        self.s.expire_all()
        a = self.s.get(Aufgabe, a.id)
        self.assertEqual(a.status, "entfaellt")
        self.assertEqual(a.entfaellt_grund, "Bedingung nicht erfüllt (steckbrief:oeltank=ja)")
        self.assertTrue(any("Öltank-Entsorgung“ entfällt – Bedingung nicht erfüllt" in t
                            for t in self.verlauf_texte(g)))
        steck = kern.steckbrief_daten(self.s, [g.id])[g.id]
        steck["oeltank"].wert = "ja"
        self.s.flush()
        ergebnis = kern.bedingungen_nachziehen(self.s, g)
        self.assertEqual(ergebnis["offen"], 1)
        self.s.expire_all()
        self.assertEqual(self.s.get(Aufgabe, a.id).status, "offen")
        # von Hand gesetztes „entfällt“ bleibt beim Nachziehen stehen
        a = self.s.get(Aufgabe, a.id)
        kern.aufgabe_entfaellt(self.s, a, "Kunde entsorgt selbst")
        ergebnis = kern.bedingungen_nachziehen(self.s, g)
        self.assertEqual(ergebnis["offen"], 0)
        self.assertEqual(self.s.get(Aufgabe, a.id).status, "entfaellt")
        self.s.commit()
        # Gewerk ohne Öltank: Schritt wird gar nicht erst angelegt, nachziehen legt ihn an
        g2 = self.gewerk_neu(erfassung={"A07": "Nein"})
        self.assertIsNone(self.aufgabe(g2, "Öltank-Entsorgung"))
        steck = kern.steckbrief_daten(self.s, [g2.id])[g2.id]
        steck["oeltank"].wert = "ja"
        steck["oeltank"].manuell = True
        self.s.flush()
        self.assertEqual(kern.steckbrief_schritte_nachziehen(self.s, g2), 1)
        self.assertEqual(self.aufgabe(g2, "Öltank-Entsorgung").status, "offen")
        self.s.commit()

    def test_foerderung_bedingung(self):
        from app import bza
        gefoerdert = self.gewerk_neu(kfw={"O01": True, "O02": "1990"})
        self.assertTrue(bza.ist_gefoerdert(self.s, gefoerdert))
        bza_aufgabe = self.aufgabe(gefoerdert, "BzA erstellen und an Kunden senden")
        self.assertIsNotNone(bza_aufgabe)
        self.assertEqual(bza_aufgabe.sichtbar_wenn, "foerderung:ja")
        ohne = self.gewerk_neu()
        self.assertFalse(bza.ist_gefoerdert(self.s, ohne))
        self.assertIsNone(self.aufgabe(ohne, "BzA erstellen und an Kunden senden"))
        # Förderung am Angebot abgeschaltet → Hook zieht nach: entfällt mit Grund
        angebot = self.s.get(Angebot, gefoerdert.angebot_id)
        angebot.foerderung_ausblenden = True
        self.s.flush()
        ergebnis = kern.foerderung_schritte_nachziehen(self.s, gefoerdert)
        self.assertEqual(ergebnis["entfaellt"], 2)       # BzA (AE 4) + BnD (Freigabe 2)
        self.s.expire_all()
        bza_aufgabe = self.s.get(Aufgabe, bza_aufgabe.id)
        self.assertEqual(bza_aufgabe.status, "entfaellt")
        self.assertEqual(bza_aufgabe.entfaellt_grund, "Bedingung nicht erfüllt (foerderung:ja)")
        bnd = self.aufgabe(gefoerdert, "BnD nach Abnahme erstellt")
        self.assertEqual(bnd.status, "entfaellt")
        angebot.foerderung_ausblenden = False
        self.s.flush()
        ergebnis = kern.foerderung_schritte_nachziehen(self.s, gefoerdert)
        self.assertEqual(ergebnis["offen"], 2)
        # TAIFUN ohne Antwort = unbekannt → Schritt bleibt sichtbar
        taifun = self.gewerk_neu()
        a = self.s.get(Angebot, taifun.angebot_id)
        a.extern = True
        a.kfw_gefoerdert = ""
        self.s.flush()
        self.assertIsNone(bza.ist_gefoerdert(self.s, taifun))
        self.assertTrue(kern._schritt_sichtbar(self.s, taifun, "foerderung:ja"))
        self.assertTrue(kern._schritt_sichtbar(self.s, taifun, "foerderung:nein"))
        self.s.commit()

    def test_laufzeit_bedingungen_aus_excel(self):
        """Blatt Aufgabenpakete v28: Anzahlung bezahlt hängt an Anzahlung geschrieben,
        Elektro-Montageteam an Elektro-Sub, Gerüst an steckbrief:geruest (PV)."""
        logik = projektierung_logik.hole_logik(self.s, erzwingen=True)
        self.assertFalse(logik.fehler, logik.fehler)
        self.assertFalse([w for w in logik.warnungen if "sichtbar_wenn" in w], logik.warnungen)
        mv = logik.pakete["montagevorbereitung"].schritte
        self.assertEqual((mv[0].aktion_typ, mv[0].optionen), ("auswahl", "keine Anzahlung | geschrieben*"))
        self.assertEqual(mv[1].sichtbar_wenn, "montagevorbereitung.1=geschrieben")
        self.assertEqual(logik.pakete["planung_elektro"].schritte[0].sichtbar_wenn,
                         "planung_elektro.3=erfolgt über Friondo")
        self.assertEqual(logik.pakete["auftragseingang"].schritte[3].sichtbar_wenn, "foerderung:ja")
        self.assertEqual(logik.pakete["freigabe"].schritte[1].sichtbar_wenn, "foerderung:ja")
        self.assertEqual(logik.pakete["pv_standard"].schritte[2].sichtbar_wenn, "steckbrief:geruest=ja")
        g = self.gewerk_neu()
        geschrieben = self.aufgabe(g, "Anzahlung geschrieben")
        bezahlt = self.aufgabe(g, "Anzahlung bezahlt")
        self.assertEqual(bezahlt.sichtbar_wenn, "montagevorbereitung.1=geschrieben")
        kern.aufgabe_auswahl_setzen(self.s, geschrieben, "keine Anzahlung")
        kern.auswahl_folgen(self.s, geschrieben)
        self.s.expire_all()
        bezahlt = self.s.get(Aufgabe, bezahlt.id)
        self.assertEqual(bezahlt.status, "entfaellt")
        self.assertTrue(bezahlt.entfaellt_grund.startswith("Bedingung nicht erfüllt"))
        geschrieben = self.s.get(Aufgabe, geschrieben.id)
        kern.aufgabe_auswahl_setzen(self.s, geschrieben, "geschrieben")
        kern.auswahl_folgen(self.s, geschrieben)
        self.s.expire_all()
        self.assertEqual(self.s.get(Aufgabe, bezahlt.id).status, "offen")
        # Elektro-Sub „Sub beauftragt“ → Elektro-Montageteam entfällt
        elektro_sub = self.aufgabe(g, "Elektro-Sub")
        elektro_team = self.aufgabe(g, "Elektro-Montageteam zuweisen")
        kern.aufgabe_auswahl_setzen(self.s, elektro_sub, "Sub beauftragt")
        kern.auswahl_folgen(self.s, elektro_sub)
        self.s.expire_all()
        self.assertEqual(self.s.get(Aufgabe, elektro_team.id).status, "entfaellt")
        self.s.commit()

    def test_logik_pruefen_kennt_formen(self):
        pruefen = projektierung_logik.sichtbar_wenn_pruefen
        for ok in ("", "foerderung:ja", "foerderung:nein", "steckbrief:oeltank=ja",
                   "sparte:PV|KL|WB", "planung_elektro.3=erfolgt über Friondo"):
            self.assertEqual(pruefen(ok), "", ok)
        self.assertIn("foerderung:ja", pruefen("foerderung:vielleicht"))
        self.assertIn("unbekannte Form", pruefen("irgendwas"))
        self.assertIn("Sparte", pruefen("sparte:XY"))
        # unbekannte Form blockiert nie
        g = self.gewerk_neu()
        self.assertTrue(kern._schritt_sichtbar(self.s, g, "irgendwas"))


class MigrationBedingungen(Basis):
    def test_migration_v28_traegt_bedingungen_nach(self):
        g = self.gewerk_neu()
        bezahlt = self.aufgabe(g, "Anzahlung bezahlt")
        bezahlt.sichtbar_wenn = ""      # Altbestand vor v28
        self.s.commit()
        meldungen = kern.migration_v28(self.s)
        self.s.commit()
        self.assertTrue(any("sichtbar_wenn" in m for m in meldungen), meldungen)
        self.s.expire_all()
        self.assertEqual(self.s.get(Aufgabe, bezahlt.id).sichtbar_wenn,
                         "montagevorbereitung.1=geschrieben")
        self.assertEqual(self.s.get(Aufgabe, bezahlt.id).status, "offen")   # Status unverändert
        self.assertEqual(kern.migration_v28(self.s), [])                     # zweiter Lauf leer


if __name__ == "__main__":
    unittest.main()
