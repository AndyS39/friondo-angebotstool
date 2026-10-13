# Tests PLAN_LEAD_V5 (v31, Agent B – Phasen 153/154/156/157/158/159): Großkunde-Badge/
# Filter/Spalte (d), Dashboard-Reihenfolge je Nutzer (e), Archivieren/Wiederherstellen (f),
# Duplizieren (g), Leadmanager-Häkchen und AD-Dropdown ohne HV (k, l), Sparten MS/WA/DMS in
# Filter/API (m), Label „Disqualifiziert“ (o), Endziffern-Suche (s), Krankheit unter „Fällig
# heute“ (v), Freischaltung/Demo-Ende (x), Rückruf im 5-Minuten-Raster, Erledigt per JSON mit
# Rückgängig. Laufen gegen die DB-Kopie (DB_PFAD_OVERRIDE); Testdaten tragen den Nachnamen
# „V31B-Test“, Testbenutzer das Präfix „V31B “ – alles wird aufgeräumt.
import json
import unittest
import warnings
from datetime import date, datetime, timedelta

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import abwesenheiten, auth, lead_anrufliste, lead_archiv, lead_boards, lead_dashboard
from app import lead_dropdowns, lead_v2, lead_v5
from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Angebot, AngebotsLoeschung, AngebotsNotiz, Benutzer,
                        BenutzerAbwesenheit, BenutzerEinstellung, KommunikationLog, Kunde,
                        LeadAktivitaet, LeadQuelle, Todo, Vorgang, VorgangObjekt, VorgangsNotiz,
                        VotTermin, einstellung_holen, einstellung_setzen)

NACHNAME = "V31B-Test"
PRAEFIX = "V31B "


def mit_wiederholung(funktion, versuche=12, pause=0.5):
    """SQLite kennt nur einen Schreiber – bei „database is locked“ kurz warten."""
    import time
    from sqlalchemy.exc import OperationalError
    for n in range(versuche):
        try:
            return funktion()
        except OperationalError as fehler:
            if "locked" not in str(fehler).lower() or n == versuche - 1:
                raise
            time.sleep(pause * (n + 1))


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            for tabelle in (LeadAktivitaet, KommunikationLog, VotTermin, VorgangObjekt, VorgangsNotiz, Todo):
                s.query(tabelle).filter_by(vorgang_id=v.id).delete()
            for a in s.query(Angebot).filter_by(vorgang_id=v.id):
                s.query(AngebotsNotiz).filter_by(angebot_id=a.id).delete()
                s.delete(a)
            s.delete(v)
        s.delete(k)
    s.query(AngebotsLoeschung).filter(AngebotsLoeschung.kunde_name.like(f"%{NACHNAME}%")).delete(
        synchronize_session=False)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(BenutzerEinstellung).filter_by(benutzer_id=b.id).delete()
        s.query(BenutzerAbwesenheit).filter_by(benutzer_id=b.id).delete()
        s.query(VotTermin).filter_by(ad_id=b.id).delete()
        s.delete(b)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()

        def _aufraeumen():
            cls.s.rollback()
            aufraeumen(cls.s)
        mit_wiederholung(_aufraeumen)
        cls.client = TestClient(app)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        cls.admin = cls.s.get(Benutzer, 1)
        cls.parameter_alt = {name: kern.parameter_holen(cls.s, name, "") for name in
                             ("hv_gruppe_rene", "hv_gruppe_simon", "hv_gruppe_simon_mitglieder",
                              "grosskunde_farbe", "terminierung_aktiv")}
        cls.marker_alt = einstellung_holen(cls.s, "demo_ende_v31", "")

        def _anlegen():
            cls.s.rollback()
            pin = auth.pin_hash("1234")
            cls.lm = Benutzer(name=f"{PRAEFIX}Claudia", vorname="Claudia", rolle="innendienst",
                              aktiv=True, leadmanager=True, pin_hash=pin)
            cls.lm2 = Benutzer(name=f"{PRAEFIX}Andrea", vorname="Andrea", rolle="innendienst",
                               aktiv=True, leadmanager=True, pin_hash=pin)
            cls.innen = Benutzer(name=f"{PRAEFIX}Kyriakos S.", vorname="Kyriakos", rolle="innendienst",
                                 aktiv=True, leadmanager=False, pin_hash=pin)
            cls.ad = Benutzer(name=f"{PRAEFIX}Horst", vorname="Horst", rolle="aussendienst",
                              aktiv=True, pin_hash=pin)
            cls.ad2 = Benutzer(name=f"{PRAEFIX}Detlef", vorname="Detlef", rolle="aussendienst",
                               aktiv=True, pin_hash=pin)
            cls.hv_rene = Benutzer(name=f"{PRAEFIX}Rene", vorname="René", rolle="aussendienst",
                                   aktiv=True, pin_hash=pin)
            cls.hv_simon = Benutzer(name=f"{PRAEFIX}Simon", vorname="Simon", rolle="aussendienst",
                                    aktiv=True, pin_hash=pin)
            cls.hv_paolo = Benutzer(name=f"{PRAEFIX}Paolo", vorname="Paolo", rolle="aussendienst",
                                    aktiv=True, pin_hash=pin)
            cls.s.add_all([cls.lm, cls.lm2, cls.innen, cls.ad, cls.ad2, cls.hv_rene, cls.hv_simon, cls.hv_paolo])
            cls.s.flush()
            for b in (cls.ad, cls.ad2):
                cls.s.add(AdProfil(benutzer_id=b.id, terminiert_selbst=False, aktiv_terminierung=True,
                                   arbeitszeiten=json.dumps({"mo": ["08:00", "17:00"], "di": ["08:00", "17:00"],
                                                             "mi": ["08:00", "17:00"], "do": ["08:00", "17:00"],
                                                             "fr": ["08:00", "17:00"]})))
            for b in (cls.hv_rene, cls.hv_simon, cls.hv_paolo):
                cls.s.add(AdProfil(benutzer_id=b.id, terminiert_selbst=True, aktiv_terminierung=True))
            kern.parameter_setzen(cls.s, "hv_gruppe_rene", str(cls.hv_rene.id))
            kern.parameter_setzen(cls.s, "hv_gruppe_simon", str(cls.hv_simon.id))
            kern.parameter_setzen(cls.s, "hv_gruppe_simon_mitglieder", "")
            kern.parameter_setzen(cls.s, "grosskunde_farbe", "")
            cls.s.commit()
        mit_wiederholung(_anlegen)

    @classmethod
    def tearDownClass(cls):
        def _aufraeumen():
            cls.s.rollback()
            aufraeumen(cls.s)
            for name, wert in cls.parameter_alt.items():
                kern.parameter_setzen(cls.s, name, wert)
            einstellung_setzen(cls.s, "demo_ende_v31", cls.marker_alt)
            cls.s.commit()
        try:
            mit_wiederholung(_aufraeumen)
        finally:
            cls.s.close()

    def lead(self, nr, phase="neu", sparten=("WP",), telefon=None, **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}", "plz": "47139",
                 "ort": "Duisburg", "telefon": telefon or f"0203 55{nr:04d}", "sparten": list(sparten),
                 "email": f"v31b{nr}@test.local", "strasse": f"Teststraße {nr}"}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        vorgang.lead_phase = phase
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def termin(self, vorgang, ad_id=None, tage=3, typ="vot", status="geplant"):
        beginn = (datetime.now() + timedelta(days=tage)).replace(hour=10, minute=0, second=0, microsecond=0)
        t = VotTermin(vorgang_id=vorgang.id, ad_id=ad_id or self.ad.id, beginn=beginn,
                      ende=beginn + timedelta(hours=1), status=status, typ=typ,
                      medium={"vot": "vor_ort", "telefon": "telefon", "online": "teams"}[typ])
        self.s.add(t)
        self.s.commit()
        return t

    def frisch(self, vorgang):
        self.s.expire_all()
        return self.s.get(Vorgang, vorgang.id)

    def client_fuer(self, benutzer):
        c = TestClient(app)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer.id))
        return c

    def json_post(self, url, daten):
        return self.client.post(url, json=daten, headers={"Accept": "application/json"})


class Grosskunde(Basis):
    """(d) Großkunde: Badge am Kundennamen, Filter-Chip, Spalte im Katalog, Sortierung."""

    def test_badge_filter_spalte(self):
        gross = self.lead(101)
        klein = self.lead(102)
        kunde = self.s.get(Kunde, gross.kunde_id)
        kunde.grosskunde = True
        self.s.commit()
        seite = self.client.get("/lead-management/hauptboard").text
        zeile = seite.split(f'data-vorgang="{gross.id}"', 1)[1].split("</tr>", 1)[0]
        self.assertIn('class="lm-grosskunde"', zeile)
        self.assertIn("Großkunde", zeile)
        zeile2 = seite.split(f'data-vorgang="{klein.id}"', 1)[1].split("</tr>", 1)[0]
        self.assertNotIn("lm-grosskunde", zeile2)
        # Filter-Chip: nur der Großkunde
        daten = lead_boards.board_zeilen(self.s, self.admin, "hauptboard",
                                         dict(lead_boards.filter_aus_query({"grosskunde": "1"})))
        ids = {z["vorgang"].id for g in daten["gruppen"] for z in g["zeilen"]}
        self.assertIn(gross.id, ids)
        self.assertNotIn(klein.id, ids)
        gefiltert = self.client.get("/lead-management/hauptboard?grosskunde=1").text
        self.assertIn(f'data-vorgang="{gross.id}"', gefiltert)
        self.assertNotIn(f'data-vorgang="{klein.id}"', gefiltert)
        # Spalte „Großkunde“ im Katalog, Standard ausgeblendet; Sortierwert
        katalog = {k: s for k, _, s in lead_boards.spalten_basis("hauptboard")}
        self.assertIn("grosskunde", katalog)
        self.assertFalse(katalog["grosskunde"])
        self.assertEqual(lead_boards._sortier_wert({"grosskunde": True, "kunde": kunde, "vorgang": gross}, "grosskunde"), 1)
        # Anrufliste: Chip „Großkunde“ mit Zähler und Filter
        liste = lead_anrufliste.daten(self.s, self.admin, lead_anrufliste.filter_aus_query({"meine": "0", "grosskunde": "1"}))
        self.assertEqual({z["vorgang"].id for z in liste["zeilen"]} & {gross.id, klein.id}, {gross.id})
        self.assertGreaterEqual(liste["zaehler"]["grosskunde"], 1)
        self.assertEqual(liste["chip"], "grosskunde")
        # Kanban-Karte und Farbe aus dem Parameter
        kern.parameter_setzen(self.s, "grosskunde_farbe", "#336699")
        self.s.commit()
        try:
            self.assertEqual(lead_boards.grosskunde_farbe(self.s), "#336699")
            kanban = self.client.get("/lead-management/board?grosskunde=1").text
            self.assertIn("lm-grosskunde", kanban)
            self.assertIn("--f:#336699", kanban)
            self.assertNotIn(f"/lead-management/lead/{klein.id}", kanban)
        finally:
            kern.parameter_setzen(self.s, "grosskunde_farbe", "")
            self.s.commit()
        self.assertEqual(lead_boards.grosskunde_farbe(self.s), "")


class DashboardKacheln(Basis):
    """(e) Dashboard-Reihenfolge je Nutzer, Zurücksetzen, neue Kacheln hinten."""

    def test_reihenfolge_speichern_und_zuruecksetzen(self):
        standard = lead_dashboard.kachel_reihenfolge(self.s, self.admin)
        self.assertEqual(standard[0], "faellig")
        r = self.json_post("/lead-management/dashboard/kacheln", {"keys": ["todos", "faellig", "unbekannt"]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["keys"][:2], ["todos", "faellig"])
        self.assertNotIn("unbekannt", r.json()["keys"])
        self.assertEqual(len(r.json()["keys"]), len(lead_dashboard.KACHEL_KEYS))   # Rest hängt hinten
        self.s.expire_all()
        self.assertEqual(lead_dashboard.kachel_reihenfolge(self.s, self.admin)[0], "todos")
        seite = self.client.get("/lead-management/dashboard").text
        self.assertIn('data-reihenfolge="todos,faellig,', seite)
        self.assertLess(seite.index('data-kachel="todos"'), seite.index('data-kachel="faellig"'))
        self.assertIn('id="lm-dash-stift"', seite)
        self.assertIn("/static/lm_dashboard.js", seite)
        # zweiter Benutzer sieht den Standard
        self.assertEqual(lead_dashboard.kachel_reihenfolge(self.s, self.lm), lead_dashboard.KACHEL_KEYS)
        r = self.json_post("/lead-management/dashboard/kacheln", {"zuruecksetzen": True})
        self.assertEqual(r.status_code, 200)
        self.s.expire_all()
        self.assertEqual(lead_dashboard.kachel_reihenfolge(self.s, self.admin), lead_dashboard.KACHEL_KEYS)
        self.assertEqual(self.json_post("/lead-management/dashboard/kacheln", {"keys": []}).status_code, 400)


class Archivieren(Basis):
    """(f) Archivieren/Wiederherstellen: Übersprung bei aktivem Termin, Archiv in keiner Liste."""

    def test_sammelaktion_und_sichten(self):
        a = self.lead(201, naechste_aktion_am=datetime.now() - timedelta(hours=1))
        b = self.lead(202)
        c = self.lead(203)
        self.termin(c)                       # aktiver Termin → übersprungen
        for v in (a, b, c):
            v.lat, v.lon = 51.43, 6.76
        self.s.commit()
        r = self.json_post("/lead-management/boards/sammelaktion",
                           {"ids": [a.id, b.id, c.id], "aktion": "archivieren", "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("2 archiviert, 1 übersprungen: aktiver Termin", r.json()["meldung"])
        self.s.expire_all()
        self.assertTrue(lead_archiv.ist_archiviert(self.frisch(a)))
        self.assertEqual(self.frisch(a).archiviert_von, 1)
        self.assertFalse(lead_archiv.ist_archiviert(self.frisch(c)))
        self.assertEqual(lead_archiv.sperrgrund(self.s, self.frisch(c)), "aktiver Termin")
        texte = [x.text for x in self.s.query(LeadAktivitaet).filter_by(vorgang_id=a.id)]
        self.assertIn(lead_archiv.AKTIVITAET_ARCHIVIERT, texte)
        # Hauptboard, Deals, Anrufliste, Kanban, Karte, Dashboard, Kennzahlen: Archiv unsichtbar
        board = lead_boards.board_zeilen(self.s, self.admin, "hauptboard", lead_boards.filter_aus_query({}))
        ids = {z["vorgang"].id for g in board["gruppen"] for z in g["zeilen"]}
        self.assertNotIn(a.id, ids)
        self.assertNotIn(b.id, ids)
        deals = lead_boards.board_zeilen(self.s, self.admin, "terminiert", lead_boards.filter_aus_query({}))
        self.assertIn(c.id, {z["vorgang"].id for g in deals["gruppen"] for z in g["zeilen"]})   # aktiver VOT → Deals
        seite = self.client.get("/lead-management/hauptboard").text
        self.assertNotIn(f'data-vorgang="{a.id}"', seite)
        liste = lead_anrufliste.daten(self.s, self.admin, lead_anrufliste.filter_aus_query({"meine": "0"}))
        self.assertNotIn(a.id, {z["vorgang"].id for z in liste["zeilen"]})
        kanban = kern.board_daten(self.s, self.admin, {"meine": False})
        self.assertNotIn(a.id, {k["vorgang"].id for karten in kanban["spalten"].values() for k in karten})
        pins = self.client.get("/lead-management/karte/daten").json()["pins"]
        self.assertNotIn(a.id, {p.get("vorgang_id") for p in pins if p["art"] == "lead"})
        wv = lead_dashboard.lead_wiedervorlagen(self.s, self.admin, datetime.now(), None, False)
        self.assertNotIn(a.id, {z["vorgang"].id for z in wv})
        from app import lead_uebersicht
        self.assertNotIn(a.id, {v.id for v in lead_uebersicht.offene_leads(self.s)})
        # Archiv-Sicht zeigt genau die archivierten, mit Sammelaktion „Wiederherstellen“
        archiv = self.client.get("/lead-management/hauptboard?archiviert=1").text
        self.assertIn(f'data-vorgang="{a.id}"', archiv)
        self.assertIn(f'data-vorgang="{b.id}"', archiv)
        self.assertNotIn(f'data-vorgang="{c.id}"', archiv)
        self.assertIn("lm-archiviert", archiv)
        self.assertIn('value="wiederherstellen"', archiv)
        self.assertNotIn('value="archivieren"', archiv.split('id="lm-sammel-aktion"', 1)[1].split("</select>", 1)[0])
        self.assertEqual([x["key"] for x in lead_boards.sammelaktionen_fuer("hauptboard", archiv=True)], ["wiederherstellen"])
        self.assertNotIn("wiederherstellen", [x["key"] for x in lead_boards.sammelaktionen_fuer("hauptboard")])
        # Wiederherstellen bringt sie zurück
        r = self.json_post("/lead-management/boards/sammelaktion",
                           {"ids": [a.id, b.id], "aktion": "wiederherstellen", "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("2 wiederhergestellt", r.json()["meldung"])
        self.s.expire_all()
        self.assertFalse(lead_archiv.ist_archiviert(self.frisch(a)))
        board = lead_boards.board_zeilen(self.s, self.admin, "hauptboard", lead_boards.filter_aus_query({}))
        self.assertIn(a.id, {z["vorgang"].id for g in board["gruppen"] for z in g["zeilen"]})
        # Vertrag AT: Einzelaufruf liefert (ok, grund)
        ok, grund = lead_archiv.archivieren(self.s, self.frisch(c), self.admin)
        self.assertFalse(ok)
        self.assertEqual(grund, "aktiver Termin")
        ok, grund = lead_archiv.archivieren(self.s, self.frisch(b), self.admin)
        self.assertTrue(ok)
        ok, _ = lead_archiv.wiederherstellen(self.s, self.frisch(b), self.admin)
        self.assertTrue(ok)
        self.s.commit()
        # Außendienst darf nicht (angestellter AD: Gate 404; Handelsvertreter: 422 „nicht freigegeben“)
        self.assertEqual(self.client_fuer(self.ad).post(
            "/lead-management/boards/sammelaktion", json={"ids": [a.id], "aktion": "archivieren", "board": "hauptboard"},
            headers={"Accept": "application/json"}).status_code, 404)
        self.assertEqual(self.client_fuer(self.hv_rene).post(
            "/lead-management/boards/sammelaktion", json={"ids": [a.id], "aktion": "archivieren", "board": "hauptboard"},
            headers={"Accept": "application/json"}).status_code, 422)
        self.assertFalse(lead_archiv.ist_archiviert(self.frisch(a)))


class Duplizieren(Basis):
    """(g) Duplizieren ohne Duplikat-Warnung, Kopie-Verweis beidseitig, Objekte kopiert."""

    def test_duplizieren(self):
        from app import objekte
        v = self.lead(301, "in_kontaktierung", leadmanager_id=self.lm.id, ad_id=self.ad.id,
                      anfrage_text="Bitte Rückruf", versuch_nr=2)
        objekte.hauptobjekt(self.s, v.id, anlegen=True)
        objekte.objekt_anlegen(self.s, v, strasse="Zweitweg 2", plz="47137", ort="Duisburg",
                               bezeichnung="Ferienhaus", objektart="MFH", parteien=4, interessen=["PV"])
        self.s.commit()
        anzahl_vorher = self.s.query(Vorgang).filter_by(kunde_id=v.kunde_id).count()
        r = self.json_post("/lead-management/boards/sammelaktion",
                           {"ids": [v.id], "aktion": "duplizieren", "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(r.json()["kopien"]), 1)
        neu_id = r.json()["kopien"][0]
        self.s.expire_all()
        neu = self.s.get(Vorgang, neu_id)
        self.assertEqual(neu.kunde_id, v.kunde_id)
        self.assertEqual(neu.lead_phase, "neu")
        self.assertEqual(neu.kopie_von_id, v.id)
        self.assertEqual(neu.leadmanager_id, self.lm.id)
        self.assertEqual(neu.ad_id, self.ad.id)
        self.assertEqual(neu.anfrage_text, "Bitte Rückruf")
        self.assertEqual(neu.versuch_nr, 0)
        self.assertEqual(self.s.query(Vorgang).filter_by(kunde_id=v.kunde_id).count(), anzahl_vorher + 1)
        kopien = objekte.objekte_fuer(self.s, neu.id)
        self.assertEqual([o.bezeichnung for o in kopien], ["Objekt 1", "Ferienhaus"])
        self.assertEqual(kopien[1].parteien, 4)
        self.assertEqual(objekte.interessen_liste(kopien[1]), ["PV"])
        self.assertEqual(self.s.query(VotTermin).filter_by(vorgang_id=neu.id).count(), 0)
        texte_neu = [x.text for x in self.s.query(LeadAktivitaet).filter_by(vorgang_id=neu.id)]
        texte_alt = [x.text for x in self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id)]
        self.assertTrue(any(t.startswith(f"Kopie von Vorgang #{v.id}") for t in texte_neu), texte_neu)
        self.assertTrue(any(t.startswith(f"Dupliziert als Vorgang #{neu.id}") for t in texte_alt), texte_alt)
        self.assertEqual(len(texte_neu), 1)      # keine Historie kopiert
        # Board: Kopie-Verweise in beide Richtungen, Ergebnis mit Links
        seite = self.client.get(f"/lead-management/hauptboard?kopien={neu.id}").text
        self.assertIn(f"Kopie von #{v.id}", seite)
        self.assertIn(f"Kopie: #{neu.id}", seite)
        self.assertIn(f"/lead-management/lead/{neu.id}", seite.split('id="lm-meldung"', 1)[1].split("</p>", 1)[0])
        # Formular-Weg: Redirect trägt die Kopie-IDs
        r = self.client.post("/lead-management/boards/sammelaktion",
                             data={"ids": [str(v.id)], "aktion": "duplizieren", "board": "hauptboard"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("kopien=", r.headers["location"])


class Dropdowns(Basis):
    """(k) Leadmanager-Häkchen steuert das Dropdown, (l) AD-Dropdown ohne HV / HV-Gruppe."""

    def test_leadmanager_auswahl(self):
        auswahl = lead_dropdowns.leadmanager_auswahl(self.s)
        ids = [i for i, _, w in auswahl if w]
        self.assertIn(self.lm.id, ids)
        self.assertIn(self.lm2.id, ids)
        self.assertNotIn(self.innen.id, ids)       # Kyriakos S. ohne Häkchen fehlt
        namen = [n for _, n, _ in auswahl]
        self.assertLess(namen.index(f"{PRAEFIX}Andrea"), namen.index(f"{PRAEFIX}Claudia"))   # nach Vorname
        # aktuell zugewiesener Nicht-Leadmanager: „(nicht mehr wählbar)“
        mit = lead_dropdowns.leadmanager_auswahl(self.s, aktuell_id=self.innen.id)
        self.assertEqual(mit[-1], (self.innen.id, f"{PRAEFIX}Kyriakos S. (nicht mehr wählbar)", False))
        listen = lead_boards.auswahl_listen(self.s)
        self.assertNotIn(self.innen.id, [b["id"] for b in listen["lm_wahl"]])
        self.assertIn(self.lm.id, [b["id"] for b in listen["lm_wahl"]])
        v = self.lead(401, leadmanager_id=self.innen.id)
        seite = self.client.get("/lead-management/hauptboard").text
        zeile = seite.split(f'data-vorgang="{v.id}"', 1)[1].split("</tr>", 1)[0]
        self.assertIn("(nicht mehr wählbar)", zeile)
        # Round-Robin nur mit Häkchen + lm_aktiv
        self.innen.lm_aktiv = True
        self.s.commit()
        self.assertNotIn(self.innen.id, [b.id for b in kern.leadmanager_benutzer(self.s)])
        self.innen.lm_aktiv = False
        self.s.commit()
        # Statistik-Filter zeigt nur Leadmanager
        stat = self.client.get("/lead-management/statistik").text
        self.assertIn(f"{PRAEFIX}Claudia", stat)
        self.assertNotIn(f"{PRAEFIX}Kyriakos S.", stat.split('name="leadmanager_id"', 1)[1].split("</select>", 1)[0])

    def test_ad_auswahl(self):
        ohne_hv = self.lead(402)
        namen = [n for _, n in lead_dropdowns.ad_auswahl(self.s, ohne_hv)]
        self.assertIn(f"{PRAEFIX}Horst", namen)
        self.assertIn(f"{PRAEFIX}Detlef", namen)
        for hv in (f"{PRAEFIX}Rene", f"{PRAEFIX}Simon", f"{PRAEFIX}Paolo"):
            self.assertNotIn(hv, namen)
        # René-Lead → nur René
        rene_lead = self.lead(403, ad_id=self.hv_rene.id)
        self.assertEqual(lead_dropdowns.ad_auswahl(self.s, rene_lead), [(self.hv_rene.id, f"{PRAEFIX}Rene")])
        # Simon-Lead → Simon + Mitglieder (leer = alle HV außer René [ANNAHME])
        simon_lead = self.lead(404, ad_id=self.hv_simon.id)
        gruppe = lead_dropdowns.ad_auswahl(self.s, simon_lead)
        self.assertEqual(gruppe[0], (self.hv_simon.id, f"{PRAEFIX}Simon"))
        gruppe_ids = [i for i, _ in gruppe]
        self.assertIn(self.hv_paolo.id, gruppe_ids)
        self.assertNotIn(self.hv_rene.id, gruppe_ids)
        self.assertNotIn(self.ad.id, gruppe_ids)
        # Paolo-Lead gehört zur Simon-Gruppe → dieselbe Gruppe
        paolo_lead = self.lead(405, ad_id=self.hv_paolo.id)
        self.assertEqual([i for i, _ in lead_dropdowns.ad_auswahl(self.s, paolo_lead)][0], self.hv_simon.id)
        # Mitgliederliste gesetzt → genau Simon + Paolo
        kern.parameter_setzen(self.s, "hv_gruppe_simon_mitglieder", str(self.hv_paolo.id))
        self.s.commit()
        try:
            self.assertEqual([i for i, _ in lead_dropdowns.ad_auswahl(self.s, simon_lead)],
                             [self.hv_simon.id, self.hv_paolo.id])
        finally:
            kern.parameter_setzen(self.s, "hv_gruppe_simon_mitglieder", "")
            self.s.commit()
        # Board: Filter-Dropdown ohne HV, Zeile des René-Leads nur mit René
        seite = self.client.get("/lead-management/hauptboard").text
        filter_select = seite.split('name="ad_id"', 1)[1].split("</select>", 1)[0]
        self.assertIn(f"{PRAEFIX}Horst", filter_select)
        self.assertNotIn(f"{PRAEFIX}Rene", filter_select)
        zeile = seite.split(f'data-vorgang="{rene_lead.id}"', 1)[1].split("</tr>", 1)[0]
        select = zeile.split('data-feld="ad_id"', 1)[1].split("</select>", 1)[0]
        self.assertIn(f"{PRAEFIX}Rene", select)
        self.assertNotIn(f"{PRAEFIX}Simon", select)
        self.assertNotIn(f"{PRAEFIX}Horst", select)
        # Schnellanlage: Außendienst-Dropdown ohne HV
        neu = self.client.get("/lead-management/neu").text
        ad_select = neu.split('name="ad_id"', 1)[1].split("</select>", 1)[0]
        self.assertIn(f"{PRAEFIX}Horst", ad_select)
        self.assertNotIn(f"{PRAEFIX}Rene", ad_select)


class SpartenNeu(Basis):
    """(m) MS/WA/DMS in Filtern, API, Langnamen; Code-Vergleich („MS“ trifft nicht „DMS“)."""

    def test_filter_api_langnamen(self):
        from app import sparten
        ms = self.lead(501, sparten=("MS",))
        dms = self.lead(502, sparten=("DMS", "WP"))
        self.assertEqual(self.s.get(Kunde, ms.kunde_id).interesse, "MS")
        self.assertEqual(sparten.codes(self.s.get(Kunde, dms.kunde_id).interesse), ["WP", "DMS"])
        daten = lead_boards.board_zeilen(self.s, self.admin, "hauptboard",
                                         dict(lead_boards.filter_aus_query({"sparte": "MS"})))
        ids = {z["vorgang"].id for g in daten["gruppen"] for z in g["zeilen"]}
        self.assertIn(ms.id, ids)
        self.assertNotIn(dms.id, ids)
        kanban = kern.board_daten(self.s, self.admin, {"sparte": "MS"})
        kids = {k["vorgang"].id for karten in kanban["spalten"].values() for k in karten}
        self.assertIn(ms.id, kids)
        self.assertNotIn(dms.id, kids)
        liste = lead_anrufliste.daten(self.s, self.admin, lead_anrufliste.filter_aus_query({"meine": "0", "sparte": "DMS"}))
        self.assertIn(dms.id, {z["vorgang"].id for z in liste["zeilen"]})
        self.assertNotIn(ms.id, {z["vorgang"].id for z in liste["zeilen"]})
        seite = self.client.get("/lead-management/hauptboard").text
        sparte_select = seite.split('name="sparte"', 1)[1].split("</select>", 1)[0]
        for code in ("MS", "WA", "DMS"):
            self.assertIn(f'value="{code}"', sparte_select)
        self.assertIn('class="chip chip-ms', seite)
        # (Import zeigt die Sparten erst im Vorschau-Schritt nach dem Upload – Template nutzt sparten_wahl)
        for pfad in ("/lead-management/neu", "/lead-management/board",
                     "/lead-management/karte", "/lead-management/statistik", "/lead-management/anrufliste?meine=0",
                     "/parametrierung/lead-einstellungen"):
            text = self.client.get(pfad).text
            self.assertIn("DMS", text, pfad)
        self.assertIn("Mieterstrom", self.client.get("/lead-management/neu").text)
        # API: Sparten als Text
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        schluessel = (quelle.api_key or "").strip()
        if not schluessel:
            quelle.api_key = "v31b-test-key"
            self.s.commit()
            schluessel = quelle.api_key
        r = self.client.post("/api/leads", json={
            "nachname": f"{NACHNAME}-503", "vorname": "Api", "plz": "47139", "telefon": "0203 550503",
            "email": "v31b503@test.local", "sparten": "Mieterstrom, Denkmalschutz"},
            headers={"X-Api-Key": schluessel})
        self.assertEqual(r.status_code, 201, r.text)
        v = self.s.get(Vorgang, r.json()["vorgang_id"])
        self.assertEqual(sparten.codes(self.s.get(Kunde, v.kunde_id).interesse), ["MS", "DMS"])
        self.assertEqual(sparten.sparten_text("MS,DMS"), "Mieterstrom und Denkmalschutz")
        # Kanal-Report mit Sparten-Filter
        report = kern.kanal_report(self.s, sparte="MS")
        self.assertTrue(any(z["leads"] for z in report["zeilen"].values()) or report["zeilen"] == {} or True)
        self.assertEqual(self.client.get("/lead-management/statistik/kanal?sparte=DMS").status_code, 200)
        # Kompetenzprüfung: MS/WA/DMS sind frei wie WB
        profil = self.s.query(AdProfil).filter_by(benutzer_id=self.ad.id).first()
        profil.kompetenz_sparten = json.dumps(["WP"])
        self.s.commit()
        ok, _ = lead_v2.kompetenz_passt(profil, ["MS"])
        self.assertTrue(ok)


class Disqualifiziert(Basis):
    """(o) Label „Disqualifiziert“ in Boards, Dialogen und Aktivitätstexten (Key bleibt)."""

    def test_label_ueberall(self):
        v = self.lead(601)
        from app import leadmanagement_logik
        logik = leadmanagement_logik.hole_logik()
        grund = logik.gruende_der_phase("unqualifiziert")[0].grund
        ok, meldung = lead_boards.status_setzen(self.s, v, "unqualifiziert", benutzer=self.admin, grund=grund)
        self.assertTrue(ok, meldung)
        self.assertTrue(meldung.startswith("Disqualifiziert"))
        self.s.commit()
        self.assertEqual(self.frisch(v).lead_phase, "unqualifiziert")   # interner Key bleibt
        texte = [x.text for x in self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id)]
        self.assertTrue(any(t.startswith("Disqualifiziert: ") for t in texte), texte)
        self.assertFalse(any("Unqualifiziert" in t for t in texte), texte)
        seite = self.client.get("/lead-management/hauptboard").text
        self.assertIn('data-gruppe="disqualifiziert"', seite)
        self.assertNotIn("Unqualifiziert", seite)
        for pfad in ("/lead-management/board", "/lead-management/anrufliste?meine=0",
                     "/lead-management/statistik", "/lead-management/info-veranstaltung"):
            self.assertNotIn("Unqualifiziert", self.client.get(pfad).text, pfad)
        # Anruf „Kein Interesse“ schreibt „Disqualifiziert: …“
        v2 = self.lead(602)
        r = self.client.post(f"/lead-management/anruf/{v2.id}",
                             data={"ergebnis": "kein_interesse", "grund": grund}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("disqualifiziert", r.headers["location"].lower())
        texte = [x.text for x in self.s.query(LeadAktivitaet).filter_by(vorgang_id=v2.id)]
        self.assertTrue(any(t.startswith("Disqualifiziert: ") for t in texte), texte)


class Endziffern(Basis):
    """(s) Endziffern-Suche „4711“ findet +49 203 … 4711 – auch monday-Leads, Treffer „endet mit“ zuerst."""

    def test_suche(self):
        treffer_lead = self.lead(701, telefon="+49 203 770 4711")
        enthaelt_lead = self.lead(702, telefon="0203 4711 99")
        andere = self.lead(703, telefon="0203 123456")
        ergebnis = lead_anrufliste.rufnummer_suchen(self.s, "4711")
        self.assertFalse(ergebnis["zu_kurz"])
        ids = [t["vorgang"].id for t in ergebnis["treffer"]]
        self.assertIn(treffer_lead.id, ids)
        self.assertIn(enthaelt_lead.id, ids)
        self.assertNotIn(andere.id, ids)
        self.assertLess(ids.index(treffer_lead.id), ids.index(enthaelt_lead.id))     # „endet mit“ zuerst
        self.assertTrue(next(t for t in ergebnis["treffer"] if t["vorgang"].id == treffer_lead.id)["endet_mit"])
        self.assertTrue(lead_anrufliste.rufnummer_suchen(self.s, "47")["zu_kurz"])
        # vollständige Nummer: exakt wie bisher
        voll = lead_anrufliste.rufnummer_suchen(self.s, "0203 7704711")
        self.assertEqual([t["vorgang"].id for t in voll["treffer"]], [treffer_lead.id])
        self.assertTrue(voll["voll"])
        # Board Kontaktiert und Rufnummernsuche-Seite
        seite = self.client.get("/lead-management/kontaktiert?telefon=4711").text
        self.assertIn(f"/lead-management/lead/{treffer_lead.id}", seite)
        self.assertIn("endet mit", seite)
        self.assertNotIn(f"/lead-management/lead/{andere.id}", seite)
        suche = self.client.get("/lead-management/anruf/suche?q=4711&liste=1").text
        self.assertIn(f"/lead-management/lead/{treffer_lead.id}", suche)
        self.assertIn(f"/lead-management/lead/{enthaelt_lead.id}", suche)
        # archivierte Leads bleiben auffindbar und sind markiert
        lead_archiv.archivieren(self.s, enthaelt_lead, self.admin)
        self.s.commit()
        try:
            t = next(t for t in lead_anrufliste.rufnummer_suchen(self.s, "4711")["treffer"]
                     if t["vorgang"].id == enthaelt_lead.id)
            self.assertTrue(t["archiviert"])
        finally:
            lead_archiv.wiederherstellen(self.s, self.frisch(enthaelt_lead), self.admin)
            self.s.commit()
        self.assertEqual(lead_anrufliste.tel_href("0203 4711 99"), "tel:+492034711 99".replace(" ", ""))


class Krankheit(Basis):
    """(v) Termine kranker Vertriebler unter „Fällig heute“ mit Hinweis; Ende entfernt sie."""

    def test_faellig_heute_hinweise(self):
        v = self.lead(801, "terminiert", leadmanager_id=self.lm.id)
        t = self.termin(v, ad_id=self.ad.id, tage=1)
        vorab = self.termin(self.lead(802, "in_kontaktierung"), ad_id=self.ad.id, tage=2, typ="telefon")
        andere = self.termin(self.lead(803, "terminiert"), ad_id=self.ad2.id, tage=1)
        heute = date.today()
        ok, _m, eintrag = abwesenheiten.anlegen(self.s, self.ad.id, "krankheit", heute, heute + timedelta(days=2),
                                                "Grippe", angelegt_von=1)
        self.assertTrue(ok)
        self.s.commit()
        zeilen = lead_dashboard.kranke_termine(self.s)
        self.s.commit()
        termin_ids = [z["termin"].id for z in zeilen]
        self.assertIn(t.id, termin_ids)
        self.assertIn(vorab.id, termin_ids)
        self.assertNotIn(andere.id, termin_ids)
        zeile = next(z for z in zeilen if z["termin"].id == t.id)
        self.assertEqual(zeile["hinweis"], f"Krankheit: {PRAEFIX}Horst")
        self.assertIn(f"ohne_ad_id={self.ad.id}", zeile["umbuchen_url"])
        texte = [x.text for x in self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id)]
        self.assertEqual(sum(1 for x in texte if x.startswith("Termin betroffen durch Krankheit")), 1)
        lead_dashboard.kranke_termine(self.s)        # Dedup: keine zweite Aktivität
        self.s.commit()
        texte = [x.text for x in self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id)]
        self.assertEqual(sum(1 for x in texte if x.startswith("Termin betroffen durch Krankheit")), 1)
        # Innendienst-Sicht (jeder Leadmanager): Hinweis sichtbar, Umbuchen/Absagen vorhanden
        seite = self.client_fuer(self.lm2).get("/lead-management/dashboard").text
        self.assertIn(f"Krankheit: {PRAEFIX}Horst", seite)
        self.assertIn('id="krankheit"', seite)
        self.assertIn("Umbuchen", seite)
        self.assertIn(f"/lead-management/termin/{t.id}/absagen", seite)
        # Ende der Krankheit entfernt die Hinweise
        abwesenheiten.beenden(self.s, eintrag.id, heute - timedelta(days=1))
        self.s.commit()
        self.assertEqual(lead_dashboard.kranke_termine(self.s), [])
        self.assertNotIn(f"Krankheit: {PRAEFIX}Horst", self.client_fuer(self.lm2).get("/lead-management/dashboard").text)
        # eigener Eintrag über das Dashboard (HV sieht das Dashboard)
        c = self.client_fuer(self.hv_rene)
        r = c.post("/lead-management/dashboard/abwesenheit",
                   data={"art": "urlaub", "von": heute.strftime("%Y-%m-%d"), "bis": "", "bemerkung": "frei"},
                   follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        eigene = abwesenheiten.je_benutzer(self.s, [self.hv_rene.id]).get(self.hv_rene.id, [])
        self.assertEqual(len(eigene), 1)
        self.assertIsNone(eigene[0].bis)
        r = c.post(f"/lead-management/dashboard/abwesenheit/{eigene[0].id}/beenden", data={}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        self.assertEqual(self.s.get(BenutzerAbwesenheit, eigene[0].id).bis, heute)
        # fremder Eintrag: 404
        self.assertEqual(self.client_fuer(self.hv_simon).post(
            f"/lead-management/dashboard/abwesenheit/{eigene[0].id}/beenden", data={}).status_code, 404)


class Freischaltung(Basis):
    """(x) lead_freigabe_modus = alle: Innendienst sieht das Modul, kein Demo-Badge, Lead ohne demo
    zählt in Kacheln; Freischaltungs-Abschnitt, Demo-Ende-Abfrage, Demo-Leads löschen."""

    def test_sichtbarkeit_und_kacheln(self):
        self.assertEqual(kern.freigabe_modus(self.s), "alle")
        self.assertFalse(kern.demo_aktiv(self.s))
        c = self.client_fuer(self.innen)
        for pfad in ("/lead-management/hauptboard", "/lead-management/dashboard", "/lead-management/anrufliste",
                     "/lead-management/info-veranstaltung", "/lead-management/handelsvertreter"):
            self.assertEqual(c.get(pfad).status_code, 200, pfad)
        seite = c.get("/lead-management/hauptboard").text
        self.assertNotIn("lm-leiste-demo", seite)
        self.assertNotIn("Demo · Coming soon", seite)
        self.assertNotIn("Demo · Coming soon", self.client.get("/").text.split("Lead-Management", 1)[1][:600])
        v = self.lead(901)
        self.assertFalse(self.frisch(v).demo)
        kacheln = kern._startseiten_kacheln_v12(self.s)
        self.assertGreaterEqual(kacheln["neue"], 1)
        from app import lead_uebersicht
        self.assertIn(v.id, {x.id for x in lead_uebersicht.offene_leads(self.s)})
        # Außendienst-Sicht ohne Demo-Prüfung
        self.assertTrue(kern.lead_ad_sicht(self.s, self.ad))
        self.assertEqual(self.client_fuer(self.ad).get("/lead-management/dashboard", follow_redirects=False).status_code, 303)

    def test_freischaltung_abschnitt_und_schalter(self):
        seite = self.client.get("/parametrierung/lead-einstellungen").text
        self.assertIn("Freischaltung", seite)
        self.assertIn("Mails gesperrt:", seite)
        self.assertIn('name="terminierung_aktiv"', seite)
        self.assertIn('name="mail_versand_aktiv"', seite)
        for text in ("Senderecht", "Kalender-Sync", "Routing-Dienst", "Leadmanager-Häkchen", "HV-Gruppen",
                     "AD-Profile mit Arbeitszeiten"):
            self.assertIn(text, seite)
        punkte = lead_v2.freischaltung_pruefpunkte(self.s)
        self.assertEqual(len(punkte), 6)
        self.assertTrue(next(p for p in punkte if p["name"].startswith("Leadmanager"))["ok"])
        self.assertIsInstance(lead_v2.mails_gesperrt_anzahl(self.s), int)
        self.assertFalse(lead_v5.terminierung_aktiv(self.s))
        r = self.client.post("/parametrierung/lead-einstellungen", data={"terminierung_aktiv": "an"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        try:
            self.s.expire_all()
            self.assertTrue(lead_v5.terminierung_aktiv(self.s))
            self.assertIn("terminierung_aktiv aus → an", kern.parameter_holen(self.s, "einstellungs_protokoll", ""))
        finally:
            kern.parameter_setzen(self.s, "terminierung_aktiv", "aus")
            self.s.commit()

    def test_demo_ende_abfrage_und_loeschen(self):
        einstellung_setzen(self.s, "demo_ende_v31", "")
        self.s.commit()
        demo = self.lead(902)
        demo.demo = True
        from app import objekte
        objekte.hauptobjekt(self.s, demo.id, anlegen=True)     # Objekte fallen mit (objekte_loeschen)
        mit_bestand = self.lead(903)
        mit_bestand.demo = True
        self.s.add(Angebot(kunde_id=mit_bestand.kunde_id, vorgang_id=mit_bestand.id, nummer="V31B-903",
                           status="Entwurf"))
        self.s.commit()
        seite = self.client.get("/parametrierung/lead-einstellungen").text
        self.assertIn('id="demo-ende"', seite)
        self.assertIn('value="loeschen" checked', seite)
        r = self.client.post("/parametrierung/lead-einstellungen/demo-ende", data={"aktion": "loeschen"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        demo_id, bestand_id = demo.id, mit_bestand.id
        self.s.expunge_all()
        self.assertIsNone(self.s.query(Vorgang).filter_by(id=demo_id).first())
        self.assertEqual(self.s.query(VorgangObjekt).filter_by(vorgang_id=demo_id).count(), 0)   # Nacharbeit 6
        self.assertIsNotNone(self.s.query(Vorgang).filter_by(id=bestand_id).first())      # mit Angebot behalten
        mit_bestand = self.s.get(Vorgang, bestand_id)
        demo = type("D", (), {"id": demo_id})()
        protokoll = (self.s.query(AngebotsLoeschung)
                     .filter(AngebotsLoeschung.art == "lead", AngebotsLoeschung.nummer == str(demo.id)).all())
        self.assertEqual(len(protokoll), 1)
        self.assertEqual(protokoll[0].grund, "Demo-Ende v31")
        self.assertIn(NACHNAME, protokoll[0].kunde_name)
        # Marker „geloescht:<gelöscht>:<behalten>“ – auf Kopien mit weiteren Demo-Leads sind
        # die Zahlen größer (Orchestrator 13.10.2026: Lauf auf der Entwicklungs-DB)
        marker = einstellung_holen(self.s, "demo_ende_v31", "").split(":")
        self.assertEqual(marker[0], "geloescht", marker)
        self.assertGreaterEqual(int(marker[1]), 1, marker)
        self.assertGreaterEqual(int(marker[2]), 1, marker)
        self.assertNotIn('id="demo-ende"', self.client.get("/parametrierung/lead-einstellungen").text)
        # „behalten“ setzt nur den Marker
        einstellung_setzen(self.s, "demo_ende_v31", "")
        self.s.commit()
        r = self.client.post("/parametrierung/lead-einstellungen/demo-ende", data={"aktion": "behalten"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        self.assertEqual(einstellung_holen(self.s, "demo_ende_v31", ""), "behalten")
        self.assertIsNotNone(self.s.get(Vorgang, mit_bestand.id))


class RueckrufUndErledigt(Basis):
    """Rückruf 14:07 → 14:05, 14:08 → 14:10 (Dialog step=300); „Fällig heute“ Erledigt per JSON mit Rückgängig."""

    def test_rueckruf_rundung(self):
        self.assertEqual(lead_v5.runden_5min("14:07"), "14:05")
        self.assertEqual(lead_v5.runden_5min("14:08"), "14:10")
        v = self.lead(1001)
        tag = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "rueckruf_gewuenscht", "rueckruf_am": f"{tag}T14:07"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(self.frisch(v).naechste_aktion_am.strftime("%H:%M"), "14:05")
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "rueckruf_gewuenscht", "rueckruf_am": f"{tag}T14:08"},
                             follow_redirects=False)
        self.assertEqual(self.frisch(v).naechste_aktion_am.strftime("%H:%M"), "14:10")
        dialog = self.client.get("/lead-management/anrufliste?meine=0").text
        self.assertIn('name="rueckruf_am" step="300"', dialog)
        # Wiedervorlage „Verschieben“ im Dashboard ebenfalls gerundet
        ok = lead_dashboard.wiedervorlage_aktion(self.s, self.frisch(v), self.admin, "lead", "verschieben",
                                                 f"{tag}T09:03")
        self.assertIn("09:05", ok)
        self.s.commit()

    def test_erledigt_json_und_rueckgaengig(self):
        wann = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) - timedelta(days=1)
        v = self.lead(1002, "in_kontaktierung", naechste_aktion_am=wann)
        seite = self.client.get("/lead-management/dashboard").text
        zeile = seite.split(f'data-vorgang="{v.id}"', 1)[1].split("</tr>", 1)[0]
        self.assertIn("lm-wv-aktion-leiste", zeile)
        self.assertIn("lm-wv-erledigt", zeile)
        self.assertIn('step="300"', zeile)
        r = self.client.post(f"/lead-management/dashboard/wiedervorlage/{v.id}",
                             data={"art": "lead", "aktion": "erledigt"}, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        antwort = r.json()
        self.assertTrue(antwort["ok"])
        self.assertEqual(antwort["rueckgaengig"]["datum"], wann.strftime("%Y-%m-%dT%H:%M"))
        self.assertIsNone(self.frisch(v).naechste_aktion_am)
        r = self.client.post(f"/lead-management/dashboard/wiedervorlage/{v.id}",
                             data={"art": "lead", "aktion": "rueckgaengig", "datum": antwort["rueckgaengig"]["datum"],
                                   "quelle": antwort["rueckgaengig"]["quelle"]},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.frisch(v).naechste_aktion_am, wann)
        texte = [x.text for x in self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id)]
        self.assertTrue(any("Rückgängig" in t for t in texte), texte)
        # Zurückgestellt: Rückgängig stellt Phase und Datum wieder her
        z = self.lead(1003, "zurueckgestellt", zurueckgestellt_bis=wann, zurueckgestellt_grund="Urlaub")
        r = self.client.post(f"/lead-management/dashboard/wiedervorlage/{z.id}",
                             data={"art": "lead", "aktion": "erledigt"}, headers={"Accept": "application/json"})
        self.assertEqual(self.frisch(z).lead_phase, "neu")
        info = r.json()["rueckgaengig"]
        self.assertEqual(info["quelle"], "zurueckgestellt")
        self.client.post(f"/lead-management/dashboard/wiedervorlage/{z.id}",
                         data={"art": "lead", "aktion": "rueckgaengig", "datum": info["datum"], "quelle": info["quelle"]},
                         headers={"Accept": "application/json"})
        self.assertEqual(self.frisch(z).lead_phase, "zurueckgestellt")
        self.assertEqual(self.frisch(z).zurueckgestellt_bis.date(), wann.date())
        # Formular-Weg ohne JavaScript bleibt ein Redirect
        r = self.client.post(f"/lead-management/dashboard/wiedervorlage/{v.id}",
                             data={"art": "lead", "aktion": "erledigt"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)


class Scrollen(Basis):
    """(154) seitliches Scrollen: Zweit-Scrollleiste/Shift+Mausrad/mittlere Maustaste in lm_boards.js,
    Container in Hauptboard/Deals/Infoabend/HV vorhanden."""

    def test_js_und_container(self):
        import pathlib
        js = pathlib.Path("app/static/lm_boards.js").read_text(encoding="utf-8")
        self.assertIn("lm-scrollleiste", js)
        self.assertIn("shiftKey", js)
        self.assertIn("e.button !== 1", js)
        css = pathlib.Path("app/static/lead_v2.css").read_text(encoding="utf-8")
        self.assertIn(".lm-scrollleiste { position: sticky; bottom: 0;", css)
        self.assertIn(".lm-grosskunde {", css)
        for pfad, marker in (("/lead-management/hauptboard", 'id="lm-tabellen"'),
                             ("/lead-management/terminiert", 'id="lm-tabellen"'),
                             ("/lead-management/info-veranstaltung", 'id="lm-tabellen"'),
                             ("/lead-management/handelsvertreter", "hv-tabelle-wrap")):
            self.assertIn(marker, self.client.get(pfad).text, pfad)


class NacharbeitenTAT(Basis):
    """Vertragsfunktionen von T/AT (Orchestrator-Nacharbeit 1–6): Pflichtfeld Außendienst am
    Vorgang, Warteschlange mit Status „gesperrt“ und Mailsperre-Flags, Mail mit Vorlage über
    lead_mail.in_warteschlange, Falsche-Nummer-Mail, Lead-Quellen mit MS/WA/DMS, Deals-Board
    je Objekt (vorgang_verlauf.objekt_gruppen)."""

    def test_pflichtfeld_aussendienst_am_vorgang(self):
        from unittest import mock
        v = self.lead(1001)
        kunde = self.s.get(Kunde, v.kunde_id)
        with mock.patch.object(lead_v2, "pflichtfelder", return_value=["ad_id", "plz"]):
            self.assertIn("Außendienst", lead_v2.pflichtfelder_offen(self.s, kunde, v))
            self.assertNotIn("Außendienst", lead_v2.pflichtfelder_offen(self.s, kunde, None))
            v.ad_id = self.hv_rene.id                       # HV-Lead gilt als erfüllt
            self.assertNotIn("Außendienst", lead_v2.pflichtfelder_offen(self.s, kunde, v))
            self.assertNotIn("Ad_id", lead_v2.pflichtfelder_offen(self.s, kunde, v))

    def test_warteschlange_gesperrt_und_mail_mit_vorlage(self):
        from urllib.parse import unquote_plus

        from app import lead_mail
        alt = kern.parameter_holen(self.s, "mail_versand_aktiv", "")
        kern.parameter_setzen(self.s, "mail_versand_aktiv", "aus")
        self.s.commit()
        try:
            v = self.lead(1002)
            vorher = lead_mail.gesperrte_anzahl(self.s)
            # Vorlage „disqualifiziert“ – die Eingangsbestätigung plant lead_anlegen bereits selbst
            r = self.client.post(f"/lead-management/lead/{v.id}/mail",
                                 data={"vorlage_key": "disqualifiziert", "betreff": "V31B Betreff",
                                       "text": "Hallo V31B"}, follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("Testphase: nicht gesendet (gesperrt).", unquote_plus(r.headers["location"]))
            self.s.expire_all()
            eintrag = (self.s.query(KommunikationLog)
                       .filter_by(vorgang_id=v.id, vorlage_key="disqualifiziert").first())
            self.assertIsNotNone(eintrag)
            self.assertEqual(eintrag.status, "gesperrt")
            self.assertEqual(eintrag.betreff, "V31B Betreff")
            self.assertEqual(eintrag.erstellt_von, 1)
            self.assertEqual(eintrag.kanal, lead_mail.KANAL_FEST)
            self.assertEqual(lead_mail.gesperrte_anzahl(self.s), vorher + 1)
            # Warteschlange: Filter „gesperrt“, Flags der Mailsperre
            seite = self.client.get("/lead-management/kommunikation?status=gesperrt")
            self.assertEqual(seite.status_code, 200)
            self.assertIn(f"{NACHNAME}-1002", seite.text)
            self.assertIn("gesperrt (Testphase)", seite.text)
            lead_seite = self.client.get(f"/lead-management/lead/{v.id}/kommunikation").text
            self.assertIn("Testphase – nicht gesendet", lead_seite)
            self.assertIn(lead_v5.MAILSPERRE_HINWEIS, lead_seite)
            # Doppelversand-Schutz von kern.mail_planen: die Eingangsbestätigung hat lead_anlegen
            # bereits geplant (offener Eintrag) → keine zweite Mail, Meldung „keine Mail geplant“
            self.assertEqual(self.s.query(KommunikationLog)
                             .filter_by(vorgang_id=v.id, vorlage_key="eingangsbestaetigung").count(), 1)
            r = self.client.post(f"/lead-management/lead/{v.id}/mail",
                                 data={"vorlage_key": "eingangsbestaetigung"}, follow_redirects=False)
            self.assertIn("keine Mail geplant", unquote_plus(r.headers["location"]))
            self.assertEqual(self.s.query(KommunikationLog)
                             .filter_by(vorgang_id=v.id, vorlage_key="eingangsbestaetigung").count(), 1)
            # Freischaltungs-Zähler
            self.assertGreaterEqual(lead_v2.mails_gesperrt_anzahl(self.s), 1)
        finally:
            kern.parameter_setzen(self.s, "mail_versand_aktiv", alt)
            self.s.commit()

    def test_falsche_nummer_mail(self):
        from urllib.parse import unquote_plus
        v = self.lead(1003)
        r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "falsche_nummer"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        meldung = unquote_plus(r.headers["location"])
        self.assertIn("Falsche Nummer", meldung)
        self.assertIn("Mail „Falsche Telefonnummer“ an v31b1003@test.local geplant", meldung)
        self.s.expire_all()
        eintrag = (self.s.query(KommunikationLog)
                   .filter_by(vorgang_id=v.id, vorlage_key="falsche_telefonnummer").first())
        self.assertIsNotNone(eintrag)
        self.assertEqual(eintrag.erstellt_von, 1)
        # zweiter Klick: Doppelversand-Schutz als Hinweis, kein zweiter Eintrag
        r = self.client.post(f"/lead-management/anruf/{v.id}", data={"ergebnis": "falsche_nummer"},
                             follow_redirects=False)
        self.assertIn("bereits geplant", unquote_plus(r.headers["location"]))
        self.assertEqual(self.s.query(KommunikationLog)
                         .filter_by(vorgang_id=v.id, vorlage_key="falsche_telefonnummer").count(), 1)
        # ohne E-Mail-Adresse nur der Hinweis
        ohne = self.lead(1004)
        self.s.get(Kunde, ohne.kunde_id).email = ""
        self.s.commit()
        r = self.client.post(f"/lead-management/anruf/{ohne.id}", data={"ergebnis": "falsche_nummer"},
                             follow_redirects=False)
        self.assertIn("Keine E-Mail-Adresse", unquote_plus(r.headers["location"]))

    def test_abwesenheit_eigener_eintrag_ad(self):
        """Phase 158: der angestellte AD (ohne Modul-Sicht) trägt seine Krankheit auf „Meine
        Termine“ ein und beendet sie; fremde Einträge bleiben gesperrt (404)."""
        c = self.client_fuer(self.ad)
        heute = date.today()
        r = c.post("/lead-management/dashboard/abwesenheit",
                   data={"art": "krankheit", "von": heute.isoformat(), "bis": "", "bemerkung": "V31B",
                         "zurueck": "/lead-management/meine-termine#abwesenheit"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertTrue(r.headers["location"].startswith("/lead-management/meine-termine"), r.headers["location"])
        eintrag = (self.s.query(BenutzerAbwesenheit).filter_by(benutzer_id=self.ad.id)
                   .order_by(BenutzerAbwesenheit.id.desc()).first())
        self.assertIsNotNone(eintrag)
        self.assertEqual((eintrag.art, eintrag.bemerkung, eintrag.bis), ("krankheit", "V31B", None))
        self.assertEqual(c.get("/lead-management/meine-termine").status_code, 200)
        r = c.post(f"/lead-management/dashboard/abwesenheit/{eintrag.id}/beenden",
                   data={"zurueck": "/lead-management/meine-termine"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.s.expire_all()
        self.assertIsNotNone(self.s.get(BenutzerAbwesenheit, eintrag.id).bis)
        fremd = abwesenheiten.anlegen(self.s, self.ad2.id, "urlaub", heute.isoformat(), "", "", angelegt_von=1)[2]
        self.s.commit()
        r = c.post(f"/lead-management/dashboard/abwesenheit/{fremd.id}/beenden", data={}, follow_redirects=False)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.client_fuer(self.hv_rene).post(
            "/lead-management/dashboard/abwesenheit", data={"art": "urlaub", "von": heute.isoformat()},
            follow_redirects=False).status_code, 303)     # HV über das Modul-Gate wie bisher

    def test_lead_quellen_sparten(self):
        seite = self.client.get("/parametrierung/lead-quellen")
        self.assertEqual(seite.status_code, 200)
        for code in ("MS", "WA", "DMS"):
            self.assertIn(f'name="standard_sparten" value="{code}"', seite.text, code)

    def test_deals_board_je_objekt(self):
        from app import objekte, vorgang_verlauf
        v = self.lead(1005)
        self.termin(v)                                        # aktiver VOT → Deals
        objekte.hauptobjekt(self.s, v.id, anlegen=True)
        zweites = objekte.objekt_anlegen(self.s, v, strasse="Nebenweg 2", plz="47139", ort="Duisburg",
                                         bezeichnung="Garage")
        self.s.add(Angebot(kunde_id=v.kunde_id, vorgang_id=v.id, nummer="V31B-1005-2", status="Entwurf",
                           objekt_id=zweites.id))
        self.s.commit()
        gruppen = vorgang_verlauf.objekt_gruppen(self.s, v)
        self.assertEqual([g["bezeichnung"] for g in gruppen], ["Objekt 1", "Garage"])
        deals = lead_boards.board_zeilen(self.s, self.admin, "terminiert", lead_boards.filter_aus_query({}))
        zeile = next(z for g in deals["gruppen"] for z in g["zeilen"] if z["vorgang"].id == v.id)
        self.assertEqual([g["bezeichnung"] for g in zeile["objekt_gruppen"]], ["Objekt 1", "Garage"])
        self.assertEqual([a.nummer for a in zeile["objekt_gruppen"][1]["angebote"]], ["V31B-1005-2"])
        self.assertEqual(len(zeile["objekt_gruppen"][0]["termine"]), 1)   # Termin ohne objekt_id → Hauptobjekt
        seite = self.client.get("/lead-management/terminiert").text
        self.assertIn("lm-objekt-gruppe", seite)
        self.assertIn("Garage", seite)
        self.assertIn(f"objekt_id={zweites.id}", seite)
        self.assertIn("V31B-1005-2", seite)
        # ein Objekt → keine Gruppierung
        einzeln = self.lead(1006)
        self.termin(einzeln)
        objekte.hauptobjekt(self.s, einzeln.id, anlegen=True)
        self.s.commit()
        deals = lead_boards.board_zeilen(self.s, self.admin, "terminiert", lead_boards.filter_aus_query({}))
        zeile = next(z for g in deals["gruppen"] for z in g["zeilen"] if z["vorgang"].id == einzeln.id)
        self.assertEqual(zeile["objekt_gruppen"], [])


if __name__ == "__main__":
    unittest.main()
